"""
tools/run_bme_diagnostic.py -- BME688 27L Containment Chamber Diagnostic Suite
================================================================================
Empirical testing tool to answer:
  "Can one BME688 detect a measurable and repeatable gas-response change
   inside this 27 L closed chamber?"

Supported Diagnostic Protocols:
  TEST A: Empty Box Baseline (10-15 min continuous clean-air recording)
  TEST B: Whole Produce Test  (5 min incubation + 15 min recording = 20 min total)
  TEST C: Freshly Cut Produce (5 min incubation + 15 min recording = 20 min total)

Data Recorded:
  - Raw Ohms (to single-ohm precision, no lossy kOhm rounding)
  - Temperature (C), Relative Humidity (%RH), Pressure (hPa)
  - Checkpoint analysis at 1m, 3m, 5m, 10m, 15m, 20m
  - Time-series exported to: datasets/diagnostic_experiments/

Usage:
  python tools/run_bme_diagnostic.py                    # Interactive menu
  python tools/run_bme_diagnostic.py --test A           # Run Test A (15m empty box)
  python tools/run_bme_diagnostic.py --test B --produce tomato
  python tools/run_bme_diagnostic.py --test C --produce tomato
  python tools/run_bme_diagnostic.py --simulate         # Simulation test mode
"""

import os
import sys
import time
import csv
import argparse
import statistics
from datetime import datetime

# Add pi_client to path to reuse BME688 hardware driver
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "pi_client"))

try:
    from gas_sensor import GasSensor, GasReading
except ImportError:
    GasSensor = None

DIAG_OUT_DIR = os.path.join(ROOT, "datasets", "diagnostic_experiments")
DEFAULT_CHECKPOINTS = [60, 180, 300, 600, 900, 1200]  # 1m, 3m, 5m, 10m, 15m, 20m


def run_experiment(test_type: str, produce_name: str, total_duration_sec: int,
                   incubation_sec: int, interval_sec: float, simulate: bool,
                   no_prompt: bool = False):
    os.makedirs(DIAG_OUT_DIR, exist_ok=True)
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    produce_clean = (produce_name or "produce").lower()
    filename = f"exp_test{test_type}_{produce_clean}_{timestamp_str}.csv"
    filepath = os.path.join(DIAG_OUT_DIR, filename)

    print("\n" + "=" * 66)
    print(f"  BME688 27L CHAMBER DIAGNOSTIC EXPERIMENT: TEST {test_type.upper()}")
    print("=" * 66)
    print(f"  Target Produce     : {produce_name}")
    print(f"  Chamber Volume     : 27.0 Liters (Sealed Box)")
    print(f"  Total Duration     : {total_duration_sec}s ({total_duration_sec // 60}m {total_duration_sec % 60}s)")
    if incubation_sec > 0:
        print(f"  Incubation Phase   : {incubation_sec}s ({incubation_sec // 60}m)")
        print(f"  Measurement Phase  : {total_duration_sec - incubation_sec}s ({(total_duration_sec - incubation_sec) // 60}m)")
    print(f"  Sampling Interval  : {interval_sec}s (recording raw Ohms)")
    print(f"  Output CSV File    : {filepath}")
    print("=" * 66)

    # Initialise sensor
    sensor = GasSensor(simulate=simulate)
    if not sensor.installed and not simulate:
        print("\n[!] ERROR: BME688 sensor not detected on I2C bus (0x77 or 0x76).")
        print("    Check wiring or run with --simulate to test in simulated mode.")
        return

    if not no_prompt:
        print("\n[>] Prompt: Ensure box lid is tightly closed and sealed.")
        try:
            input("    Press [Enter] to begin recording...")
        except (EOFError, KeyboardInterrupt):
            pass

    readings = []
    t_start = time.time()

    # Dynamic checkpoints based on duration
    active_checkpoints = [cp for cp in DEFAULT_CHECKPOINTS if cp < total_duration_sec]
    checkpoint_idx = 0
    next_checkpoint = active_checkpoints[checkpoint_idx] if active_checkpoints else None

    # CSV File header
    csv_file = open(filepath, "w", newline="", encoding="utf-8")
    csv_writer = csv.writer(csv_file)
    csv_writer.writerow([
        "relative_sec", "timestamp", "gas_ohms", "gas_kohms",
        "temperature_c", "humidity_pct", "pressure_hpa", "phase"
    ])

    print("\n" + "-" * 66)
    print("  Time    Phase         Raw Ohms      kOhm       Delta-R      Temp     RH")
    print("-" * 66)

    initial_baseline_ohms = None
    checkpoint_results = []

    try:
        while True:
            t_now = time.time()
            elapsed = t_now - t_start
            if elapsed >= total_duration_sec:
                break

            # Phase detection
            if incubation_sec > 0 and elapsed < incubation_sec:
                phase = "INCUBATING"
            else:
                phase = "RECORDING"

            r = sensor._read_once()
            if r.gas_ohms > 0:
                readings.append(r)

                # Update baseline with rolling median of first 5 samples
                if initial_baseline_ohms is None or len(readings) <= 5:
                    initial_baseline_ohms = statistics.median([x.gas_ohms for x in readings])

                delta_r = initial_baseline_ohms - r.gas_ohms
                ratio_pct = (delta_r / initial_baseline_ohms * 100.0) if initial_baseline_ohms > 0 else 0.0

                csv_writer.writerow([
                    round(elapsed, 2),
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    round(r.gas_ohms, 1),
                    round(r.gas_ohms / 1000.0, 3),
                    round(r.temperature, 2),
                    round(r.humidity, 2),
                    round(r.pressure, 2),
                    phase,
                ])
                csv_file.flush()

                # Live terminal update
                rel_min = int(elapsed // 60)
                rel_sec = int(elapsed % 60)
                time_str = f"{rel_min:02d}:{rel_sec:02d}"
                delta_str = f"{delta_r:+8.0f} Ohm ({ratio_pct:+5.2f}%)"

                sys.stdout.write(
                    f"\r  {time_str}  [{phase:<10}] {r.gas_ohms:10.1f} Ohm   {r.gas_ohms/1000:7.3f}k   "
                    f"{delta_str:<18} {r.temperature:4.1f}C  {r.humidity:4.1f}%"
                )
                sys.stdout.flush()

                # Checkpoint evaluation
                if next_checkpoint is not None and elapsed >= next_checkpoint:
                    window = [x.gas_ohms for x in readings[-min(10, len(readings)):]]
                    cp_ohms = statistics.median(window)
                    cp_delta = initial_baseline_ohms - cp_ohms
                    cp_pct = (cp_delta / initial_baseline_ohms * 100.0)
                    checkpoint_results.append({
                        "checkpoint_sec": next_checkpoint,
                        "checkpoint_min": next_checkpoint // 60,
                        "gas_ohms": cp_ohms,
                        "delta_ohms": cp_delta,
                        "ratio_pct": cp_pct,
                        "temp": r.temperature,
                        "humidity": r.humidity,
                    })
                    checkpoint_idx += 1
                    next_checkpoint = active_checkpoints[checkpoint_idx] if checkpoint_idx < len(active_checkpoints) else None

            time.sleep(interval_sec)

    except KeyboardInterrupt:
        print("\n[!] Experiment halted early by operator (Ctrl+C). Saving accumulated data...")
    finally:
        csv_file.close()

    print("\n" + "-" * 66)

    # -- Checkpoint Summary Table -----------------------------------------------
    if checkpoint_results:
        print("\n" + "=" * 66)
        print("  TIMED CHECKPOINT ANALYSIS (1m, 3m, 5m, 10m, 15m, 20m)")
        print("=" * 66)
        print("  Time    Resistance (kOhm)   Raw Ohms      Delta from Start   Drop %")
        print("  " + "-" * 60)
        for cp in checkpoint_results:
            cp_k = cp["gas_ohms"] / 1000.0
            print(f"  {cp['checkpoint_min']:2d} min   {cp_k:8.3f} kOhm    {cp['gas_ohms']:9.1f} Ohm    "
                  f"{cp['delta_ohms']:+8.1f} Ohm       {cp['ratio_pct']:+5.2f}%")
        print("=" * 66)

    # -- Statistical Analysis --------------------------------------------------
    if len(readings) >= 5:
        all_ohms = [x.gas_ohms for x in readings]
        mean_ohms = statistics.mean(all_ohms)
        std_ohms  = statistics.stdev(all_ohms) if len(all_ohms) > 1 else 0.0
        min_ohms  = min(all_ohms)
        max_ohms  = max(all_ohms)
        range_ohms = max_ohms - min_ohms
        final_drop_pct = ((initial_baseline_ohms - all_ohms[-1]) / initial_baseline_ohms * 100.0) if initial_baseline_ohms else 0.0

        print("\n" + "=" * 66)
        print("  EMPIRICAL EXPERIMENT RESULTS SUMMARY")
        print("=" * 66)
        print(f"  Samples Recorded   : {len(readings)} snapshots")
        print(f"  Initial Reference  : {initial_baseline_ohms:10.1f} Ohm ({initial_baseline_ohms/1000:.3f} kOhm)")
        print(f"  Final Resistance   : {all_ohms[-1]:10.1f} Ohm ({all_ohms[-1]/1000:.3f} kOhm)")
        print(f"  Mean +/- StdDev    : {mean_ohms:10.1f} Ohm +/- {std_ohms:6.1f} Ohm")
        print(f"  Min / Max Observed : {min_ohms:10.1f} Ohm / {max_ohms:10.1f} Ohm (Spread: {range_ohms:.1f} Ohm)")
        print(f"  Net Shift          : {initial_baseline_ohms - all_ohms[-1]:+10.1f} Ohm ({final_drop_pct:+5.2f}%)")
        print("=" * 66)

        # Interpret results
        print("  DIAGNOSTIC CONCLUSION:")
        if test_type.upper() == "A":
            print(f"  - Clean Chamber Noise Level: +/-{std_ohms:.1f} Ohm (Spread: {range_ohms:.1f} Ohm)")
            print(f"  - Any produce signal MUST exceed 3x standard deviation ({std_ohms*3:.1f} Ohm)")
            print(f"    to be statistically distinguishable from chamber baseline noise.")
        else:
            if abs(initial_baseline_ohms - all_ohms[-1]) > (std_ohms * 3):
                print(f"  - [POSITIVE] Measurable response detected!")
                print(f"    Resistance shifted by {abs(initial_baseline_ohms - all_ohms[-1]):.1f} Ohm (> 3-sigma noise threshold).")
                print(f"    Confirms BME688 detects volatile accumulation in this 27L chamber.")
            else:
                print(f"  - [INCONCLUSIVE / LOW SIGNAL]")
                print(f"    Resistance change did not significantly exceed clean-air baseline drift.")
                if test_type.upper() == "B":
                    print("    Next Step: Run TEST C (Freshly Cut Produce) as a stronger volatile source.")
                elif test_type.upper() == "C":
                    print("    Next Step: Verify BME heater temperature (320C), heater duration (150ms),")
                    print("    breakout module supply voltage, or check chamber lid sealing.")
        print("=" * 66)

    print(f"\n[+] Raw time-series CSV saved to:\n    {filepath}\n")


def main():
    parser = argparse.ArgumentParser(description="AgriScan 360 BME688 27L Chamber Diagnostic Suite")
    parser.add_argument("--test", choices=["A", "B", "C", "a", "b", "c"], default=None,
                        help="Test protocol: A (Empty Box), B (Whole Produce), C (Cut Produce)")
    parser.add_argument("--produce", type=str, default="Tomato",
                        help="Produce name under test (default: Tomato)")
    parser.add_argument("--duration-min", type=int, default=None,
                        help="Total test duration in minutes (default: 15m for A, 20m for B/C)")
    parser.add_argument("--duration-sec", type=int, default=None,
                        help="Total test duration in seconds (overrides --duration-min, useful for testing)")
    parser.add_argument("--interval", type=float, default=0.5,
                        help="Sampling interval in seconds (default: 0.5s)")
    parser.add_argument("--simulate", action="store_true",
                        help="Run in simulation mode without physical hardware")
    parser.add_argument("--no-prompt", action="store_true",
                        help="Skip interactive Enter prompt before starting recording")
    args = parser.parse_args()

    test_type = args.test.upper() if args.test else None

    # Interactive prompt if no test argument specified
    if not test_type:
        print("\n+==================================================================+")
        print("|   AgriScan 360 -- BME688 27L Chamber Diagnostic Suite            |")
        print("+==================================================================+")
        print("|  A. TEST A -- EMPTY BOX BASELINE (15 min continuous clean air)   |")
        print("|  B. TEST B -- WHOLE PRODUCE (5 min incubation + 15 min record)   |")
        print("|  C. TEST C -- FRESHLY CUT PRODUCE (5 min incubation + 15 min)    |")
        print("+==================================================================+")
        try:
            choice = input("Select Test Protocol [A/B/C] (Default A): ").strip().upper()
            test_type = choice if choice in ("A", "B", "C") else "A"
        except (KeyboardInterrupt, EOFError):
            test_type = "A"

    # Default durations
    if args.duration_sec is not None:
        total_sec = args.duration_sec
        inc_sec = 0 if test_type == "A" else min(total_sec // 4, 300)
    elif args.duration_min is not None:
        total_sec = args.duration_min * 60
        inc_sec = 0 if test_type == "A" else 300
    else:
        if test_type == "A":
            total_sec = 900   # 15 min
            inc_sec   = 0
        elif test_type == "B":
            total_sec = 1200  # 20 min (5m inc + 15m rec)
            inc_sec   = 300   # 5 min
        else:  # C
            total_sec = 1200  # 20 min (5m inc + 15m rec)
            inc_sec   = 300   # 5 min

    if test_type == "A":
        p_name = "Empty_Box"
    elif test_type == "B":
        p_name = f"Whole_{args.produce.strip().title()}"
    else:
        p_name = f"Cut_{args.produce.strip().title()}"

    run_experiment(
        test_type=test_type,
        produce_name=p_name,
        total_duration_sec=total_sec,
        incubation_sec=inc_sec,
        interval_sec=args.interval,
        simulate=args.simulate,
        no_prompt=args.no_prompt,
    )


if __name__ == "__main__":
    main()
