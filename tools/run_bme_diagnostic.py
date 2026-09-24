"""
tools/run_bme_diagnostic.py -- BME688 27L Containment Chamber Diagnostic Suite
================================================================================
Empirical testing tool to answer:
  "Can one BME688 detect a measurable and repeatable gas-response change
   inside this 27 L closed chamber?"

Supported Diagnostic Protocols:
  TEST A: Empty Box Baseline (5 min continuous clean-air recording)
  TEST B: Whole Produce Test (3 min incubation + 4 min recording = 7 min total)

Data Recorded:
  - Raw Ohms (to single-ohm precision, no lossy kOhm rounding)
  - Temperature (C), Relative Humidity (%RH), Pressure (hPa)
  - Checkpoint analysis at 1m, 2m, 3m, 4m, 5m, 6m, 7m
  - Time-series exported to: datasets/diagnostic_experiments/

Usage:
  python tools/run_bme_diagnostic.py                    # Interactive menu
  python tools/run_bme_diagnostic.py --test A           # Run Test A (5m empty box)
  python tools/run_bme_diagnostic.py --test B --produce tomato # Run Test B (7m produce)
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
DEFAULT_CHECKPOINTS = [60, 120, 180, 240, 300, 360, 420]  # 1m, 2m, 3m, 4m, 5m, 6m, 7m


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
    print(f"  Warm-up Policy     : First 120s (2m) discarded for stabilization")
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
        "temperature_c", "humidity_pct", "pressure_hpa", "phase", "stabilized"
    ])

    print("\n[>] Pre-heating BME688 hotplate thrice for rapid thermal stabilization...")
    sensor.heatup_thrice()

    print("[>] Starting diagnostic recording...")
    initial_baseline_ohms = None
    checkpoint_results = []

    try:
        while True:
            t_now = time.time()
            elapsed_sec = int(t_now - t_start)
            if elapsed_sec >= total_duration_sec:
                break

            r = sensor._read_once()
            readings.append(r)

            if initial_baseline_ohms is None and r.gas_ohms > 0:
                initial_baseline_ohms = r.gas_ohms

            # Phase determination
            if incubation_sec > 0 and elapsed_sec < incubation_sec:
                phase = "INCUBATION"
            else:
                phase = "MEASUREMENT" if incubation_sec > 0 else "BASELINE"

            is_stabilized = elapsed_sec >= 120

            # Write row
            csv_writer.writerow([
                elapsed_sec,
                f"{r.timestamp:.3f}",
                f"{r.gas_ohms:.1f}",
                f"{r.gas_kohms:.3f}",
                f"{r.temperature:.2f}",
                f"{r.humidity:.2f}",
                f"{r.pressure:.2f}",
                phase,
                is_stabilized,
            ])
            csv_file.flush()

            # Checkpoint capture
            if next_checkpoint and elapsed_sec >= next_checkpoint:
                delta_ohms = (initial_baseline_ohms - r.gas_ohms) if initial_baseline_ohms else 0.0
                ratio_pct = (delta_ohms / initial_baseline_ohms * 100.0) if initial_baseline_ohms else 0.0
                checkpoint_results.append({
                    "checkpoint_sec": next_checkpoint,
                    "checkpoint_min": next_checkpoint // 60,
                    "gas_ohms": r.gas_ohms,
                    "delta_ohms": delta_ohms,
                    "ratio_pct": ratio_pct,
                })
                checkpoint_idx += 1
                next_checkpoint = active_checkpoints[checkpoint_idx] if checkpoint_idx < len(active_checkpoints) else None

            # Terminal progress line
            delta_live = (initial_baseline_ohms - r.gas_ohms) if initial_baseline_ohms else 0.0
            cur_k = f"{r.gas_kohms:6.2f}k"
            status_tag = "STABILIZED" if is_stabilized else "WARM-UP"
            sys.stdout.write(
                f"\r  [{phase:11s} | {status_tag}] {elapsed_sec:3d}s/{total_duration_sec}s | "
                f"Gas: {cur_k} ({int(r.gas_ohms):6d} Ohm) | "
                f"Delta: {delta_live:+7.0f} Ohm | "
                f"{r.temperature:.1f}C | {r.humidity:.1f}%RH  "
            )
            sys.stdout.flush()

            time.sleep(interval_sec)

    except KeyboardInterrupt:
        print("\n\n[!] Experiment halted early by operator.")
    finally:
        csv_file.close()

    print("\n\n[+] Recording session complete.")

    # -- Checkpoint Summary Table ----------------------------------------------
    if checkpoint_results:
        print("\n" + "=" * 66)
        print("  TIMED CHECKPOINT ANALYSIS")
        print("=" * 66)
        print("  Time      Gas (kOhm)     Gas (Ohm)      Delta (Ohm)    Drop Ratio")
        print("  ----------------------------------------------------------------")
        for cp in checkpoint_results:
            cp_k = cp["gas_ohms"] / 1000.0
            print(f"  {cp['checkpoint_min']:2d} min   {cp_k:8.3f} kOhm    {cp['gas_ohms']:9.1f} Ohm    "
                  f"{cp['delta_ohms']:+8.1f} Ohm       {cp['ratio_pct']:+5.2f}%")
        print("=" * 66)

    # -- Statistical Analysis (Post-Warmup / Stabilized) ----------------------
    if len(readings) >= 5:
        # Separate full readings vs post-120s stabilized readings
        all_ohms = [x.gas_ohms for x in readings if x.gas_ohms > 0]
        stab_readings = [x for i, x in enumerate(readings) if i * interval_sec >= 120 and x.gas_ohms > 0]
        eval_ohms = [x.gas_ohms for x in stab_readings] if len(stab_readings) >= 5 else all_ohms

        mean_ohms = statistics.mean(eval_ohms)
        std_ohms  = statistics.stdev(eval_ohms) if len(eval_ohms) > 1 else 0.0
        min_ohms  = min(eval_ohms)
        max_ohms  = max(eval_ohms)
        range_ohms = max_ohms - min_ohms
        initial_ref = eval_ohms[0] if eval_ohms else initial_baseline_ohms
        final_drop_pct = ((initial_ref - eval_ohms[-1]) / initial_ref * 100.0) if initial_ref else 0.0

        print("\n" + "=" * 66)
        print("  EMPIRICAL EXPERIMENT RESULTS SUMMARY (Stabilized Data: >120s)")
        print("=" * 66)
        print(f"  Total Snapshots    : {len(readings)} (Stabilized: {len(eval_ohms)})")
        print(f"  Initial Stabilized : {initial_ref:10.1f} Ohm ({initial_ref/1000:.3f} kOhm)")
        print(f"  Final Resistance   : {eval_ohms[-1]:10.1f} Ohm ({eval_ohms[-1]/1000:.3f} kOhm)")
        print(f"  Mean +/- StdDev    : {mean_ohms:10.1f} Ohm +/- {std_ohms:6.1f} Ohm")
        print(f"  Min / Max Observed : {min_ohms:10.1f} Ohm / {max_ohms:10.1f} Ohm (Spread: {range_ohms:.1f} Ohm)")
        print(f"  Net Shift          : {initial_ref - eval_ohms[-1]:+10.1f} Ohm ({final_drop_pct:+5.2f}%)")
        print("=" * 66)

        # Interpret results
        print("  DIAGNOSTIC CONCLUSION:")
        if test_type.upper() == "A":
            print(f"  - Clean Chamber Noise Level: +/-{std_ohms:.1f} Ohm (Spread: {range_ohms:.1f} Ohm)")
            print(f"  - Any produce signal MUST exceed 3x standard deviation ({std_ohms*3:.1f} Ohm)")
            print(f"    to be statistically distinguishable from chamber baseline noise.")
        else:
            shift = abs(initial_ref - eval_ohms[-1])
            if shift > (std_ohms * 3):
                print(f"  - [POSITIVE] Measurable response detected!")
                print(f"    Resistance shifted by {shift:.1f} Ohm (> 3-sigma noise threshold).")
                print(f"    Confirms BME688 detects volatile accumulation in this 27L chamber.")
            else:
                print(f"  - [INCONCLUSIVE / LOW SIGNAL]")
                print(f"    Resistance change did not significantly exceed clean-air baseline drift.")
                print("    Next Step: Verify BME heater temperature (320C), heater duration (150ms),")
                print("    breakout module supply voltage, or check chamber lid sealing.")
        print("=" * 66)

    print(f"\n[+] Raw time-series CSV saved to:\n    {filepath}\n")


def main():
    parser = argparse.ArgumentParser(description="AgriScan 360 BME688 27L Chamber Diagnostic Suite")
    parser.add_argument("--test", choices=["A", "B", "a", "b"], default=None,
                        help="Test protocol: A (Empty Box 5m), B (Whole Produce 7m)")
    parser.add_argument("--produce", type=str, default="Tomato",
                        help="Produce name under test (default: Tomato)")
    parser.add_argument("--duration-min", type=int, default=None,
                        help="Total test duration in minutes (default: 5m for A, 7m for B)")
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
        print("|  A. TEST A -- EMPTY BOX BASELINE (5 min continuous clean air)    |")
        print("|  B. TEST B -- WHOLE PRODUCE (3 min incubation + 4 min rec = 7m)  |")
        print("+==================================================================+")
        try:
            choice = input("Select Test Protocol [A/B] (Default A): ").strip().upper()
            test_type = choice if choice in ("A", "B") else "A"
        except (KeyboardInterrupt, EOFError):
            test_type = "A"

    # Default durations
    if args.duration_sec is not None:
        total_sec = args.duration_sec
        inc_sec = 0 if test_type == "A" else min(total_sec // 2, 180)
    elif args.duration_min is not None:
        total_sec = args.duration_min * 60
        inc_sec = 0 if test_type == "A" else min(total_sec // 2, 180)
    else:
        if test_type == "A":
            total_sec = 300   # 5 min
            inc_sec   = 0
        else:  # B
            total_sec = 420   # 7 min (3m incubation + 4m recording)
            inc_sec   = 180   # 3 min

    if test_type == "A":
        p_name = "Empty_Box"
    else:
        p_name = f"Whole_{args.produce.strip().title()}"

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
