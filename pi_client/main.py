"""
main.py — AgriScan 360 Master Orchestrator (Adaptive Multi-Modal Scan)
========================================================================
Supports:
  - Produce Focus: Tomato, Apple, Eggplant (Brinjal)
  - 27L Closed Box Environment
  - Turntable Stepper Motor (8 stops x 45° = 360°)
  - Sequential Illumination:
      White LED ON -> RGB Snap -> White LED OFF
      UV-A LED ON  -> UV Snap  -> UV-A LED OFF
      Motor rotates 45°
  - Continuous BME688 Sniffing:
      Sniffs VOC gas resistance the entire duration while the 16 photos are taken.
  - Adaptive Fallbacks:
      1. If no MOSFET connected: prompts operator to switch White & UV-A LEDs manually.
      2. If no BME688 connected: assumes sensor not yet implemented and proceeds in vision-only mode.
"""

import argparse
import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("agriscan.main")

parser = argparse.ArgumentParser(description="AgriScan 360 — Adaptive Master Orchestrator")
parser.add_argument("--simulate", action="store_true", help="Run without hardware (PC test mode)")
parser.add_argument("--produce",  type=str, default=None, help="Produce name (Tomato, Apple, Eggplant)")
parser.add_argument("--manual-leds", action="store_true", help="Force manual operator LED switching")
parser.add_argument("--mosfet", action="store_true", help="Force automatic MOSFET GPIO LED switching")
parser.add_argument("--no-loop", action="store_true", help="Run single scan then exit")
args = parser.parse_args()

SIM = args.simulate

from motor      import StepperMotor
from lights     import LightController
from gas_sensor import GasSensor, ScanGasResult
from camera     import CameraController
from display    import OLEDDisplay
from uploader   import ScanUploader
from config     import SUPPORTED_PRODUCE, NUM_SCAN_STOPS, CHAMBER_VOLUME_LITERS


def prompt_produce() -> str:
    """Prompt operator to select the target produce."""
    if args.produce:
        name = args.produce.strip().title()
        return name

    print("\n+-- Select Produce (AgriScan 360 Focus) -------+")
    for i, name in enumerate(SUPPORTED_PRODUCE, 1):
        print(f"|  {i:2d}. {name:<38} |")
    print(f"|  {len(SUPPORTED_PRODUCE)+1:2d}. Other Produce{'':26} |")
    print("+----------------------------------------------+")

    while True:
        try:
            choice = int(input("Enter number: ").strip())
            if 1 <= choice <= len(SUPPORTED_PRODUCE):
                return SUPPORTED_PRODUCE[choice - 1]
            elif choice == len(SUPPORTED_PRODUCE) + 1:
                return input("Enter custom produce name: ").strip().title() or "Tomato"
        except (ValueError, KeyboardInterrupt):
            print("Invalid input. Please enter a number.")


def prompt_led_mode() -> str:
    """Determine whether to use MOSFET or manual lighting."""
    if args.manual_leds:
        return "manual"
    if args.mosfet:
        return "auto"
    if SIM:
        return "simulate"

    print("\n+-- LED Control Setup -------------------------+")
    print("|  1. Manual (I will switch White & UV by hand)|")
    print("|  2. MOSFET (IRLZ44N automatic GPIO 18 & 24)  |")
    print("+----------------------------------------------+")
    try:
        ans = input("Select mode [1/2] (Default: 1 = Manual): ").strip()
        if ans == "2":
            return "auto"
    except (KeyboardInterrupt, EOFError):
        pass
    return "manual"


def run_scan(motor: StepperMotor,
             lights: LightController,
             camera: CameraController,
             gas: GasSensor,
             display: OLEDDisplay,
             uploader: ScanUploader,
             produce_name: str) -> dict:
    """
    Execute complete 360° multi-spectral scan with continuous BME688 sniffing inside 27L box:
      1. Place fruit & close 27L box lid.
      2. Start continuous BME688 sniffing thread.
      3. For 8 stops:
           - White LED ON -> RGB snap -> White LED OFF
           - UV-A LED ON  -> UV snap  -> UV-A LED OFF
           - Motor rotates 45°
      4. Stop BME688 sniffing thread & compute VOC resistance delta.
      5. Upload 16 frames + gas delta to server -> display result.
    """
    rgb_images = []
    uv_images  = []

    log.info("=== Starting scan for %s (Chamber: %.1fL) ===", produce_name, CHAMBER_VOLUME_LITERS)
    display.show_ready()

    print("\n" + "=" * 62)
    print(f"  Produce: {produce_name}")
    print(f"  Chamber: {CHAMBER_VOLUME_LITERS}L Containment Box")
    print(f"  Lighting: {'Manual Operator' if lights.is_manual else 'MOSFET Auto (GPIO 18 & 24)'}")
    print(f"  Gas Sensor: {'Active (Continuous Sniffing)' if gas.installed else 'Not Installed (Vision Only)'}")
    print("=" * 62)

    # ── Step 1: Empty Chamber Baseline Calibration ────────────────────────────
    if gas.installed:
        print("\n[>] STEP 1: Ensure chamber is EMPTY (fresh clean air).")
        print("[>] Press [Enter] to calibrate clean air baseline...", end="", flush=True)
        try:
            input()
        except EOFError:
            pass
        display.show_uploading()
        display.show_scanning(stop=-1)
        gas.calibrate_baseline()
        print(f"    -> Clean Baseline Recorded: {gas._baseline.gas_kohms:.2f} kOhm")

    # ── Step 2: Place fruit and seal chamber ──────────────────────────────────
    print(f"\n[>] STEP 2: Place '{produce_name}' on the turntable plate shaft.")
    print(f"[>] STEP 3: Close the 27L container box lid tightly.")
    print(f"[>] Press [Enter] when the box is sealed to start scanning...", end="", flush=True)
    try:
        input()
    except EOFError:
        pass

    # ── Step 2: Optional pre-scan incubation (let VOC accumulate) ────────────
    if cfg.GAS_PRE_SCAN_INCUBATION_SEC > 0:
        print(f"[>] Incubating chamber for {cfg.GAS_PRE_SCAN_INCUBATION_SEC}s "
              f"(set GAS_PRE_SCAN_INCUBATION_SEC=0 in config.py to skip)...")
        time.sleep(cfg.GAS_PRE_SCAN_INCUBATION_SEC)

    # ── Step 3: Start continuous BME688 sniffing ──────────────────────────────
    gas.start_continuous_sniffing()

    # ── Step 3: 8-Stop Scan Cycle (16 Photos Total) ───────────────────────────
    log.info("Starting 8-stop turntable scan (16 images total)...")
    motor.set_direction(clockwise=True)
    motor.enable()

    try:
        for stop in range(NUM_SCAN_STOPS):
            angle = stop * 45
            display.show_scanning(stop=stop, total=NUM_SCAN_STOPS)
            print(f"\n--- [Stop {stop + 1}/{NUM_SCAN_STOPS} ({angle}°)] ---")

            # A. Normal LED ON -> RGB snap -> Normal LED OFF
            with lights.capture_white(stop_index=stop, angle=angle):
                rgb_bytes = camera.capture_jpeg()
                rgb_images.append(rgb_bytes)
                log.info("  -> [RGB] Captured Stop %d/8 (%d°)", stop + 1, angle)

            time.sleep(0.1)

            # B. UV-A LED ON -> UV snap -> UV-A LED OFF
            with lights.capture_uv(stop_index=stop, angle=angle):
                uv_bytes = camera.capture_jpeg()
                uv_images.append(uv_bytes)
                log.info("  -> [UV-A] Captured Stop %d/8 (%d°)", stop + 1, angle)

            # C. Rotate 45° to next stop
            if stop < NUM_SCAN_STOPS - 1:
                next_angle = (stop + 1) * 45
                print(f"[>] Rotating turntable 45° to Stop {stop + 2}/{NUM_SCAN_STOPS} ({next_angle}°)...")
                motor.advance_45_degrees()
            else:
                print("[>] Scan complete! Returning turntable 45° to 0° home position...")
                motor.advance_45_degrees()

    except KeyboardInterrupt:
        log.warning("Scan interrupted by operator.")
        gas.stop_continuous_sniffing()
        motor.cleanup()
        lights.off_all()
        display.show_error("Scan cancelled")
        return {"status": "CANCELLED", "confidence": 0.0, "reason": "Interrupted by user"}
    finally:
        motor.disable()
        lights.off_all()

    # ── Step 4: Stop continuous BME688 sniffing ───────────────────────────────
    gas_result = gas.stop_continuous_sniffing()
    if gas.installed:
        print("\n+--- BME688 Headspace Gas Analytics -------------------+")
        print(f"|  Baseline Resistance : {gas_result.baseline_kohms:6.2f} kOhm                    |")
        print(f"|  Post-Scan Resistance: {gas_result.post_scan_kohms:6.2f} kOhm                    |")
        print(f"|  Min / Max Observed  : {gas_result.gas_min_kohms:6.2f} / {gas_result.gas_max_kohms:6.2f} kOhm        |")
        print(f"|  Mean / Std Dev      : {gas_result.gas_mean_kohms:6.2f} +/- {gas_result.gas_std_kohms:5.2f} kOhm       |")
        print(f"|  Relative Drop Ratio : {gas_result.gas_ratio_pct:5.1f}%                         |")
        print(f"|  Decay Rate (dR/dt)  : {gas_result.gas_slope_per_sec:+7.4f} kOhm/s                  |")
        print(f"|  Environmental Cond. : {gas_result.temperature_c:4.1f}C | {gas_result.humidity_pct:4.1f}%RH | {gas_result.pressure_hpa:6.1f}hPa |")
        print(f"|  Samples Collected   : {gas_result.sample_count:<4d} snapshots                  |")
        print(f"|  Gas Rot Suspicion   : {gas_result.rot_suspicion:<28s} |")
        print("+------------------------------------------------------+")
    else:
        log.info("Gas sensing bypassed (BME688 not installed). Delta = 0.0 kOhm.")

    # ── Step 5: Upload all 16 frames + gas delta ──────────────────────────────
    display.show_uploading()
    result = uploader.upload_scan(
        rgb_images=rgb_images,
        uv_images=uv_images,
        gas_result=gas_result,
        produce_name=produce_name,
    )

    # ── Step 6: Display Prediction Result ─────────────────────────────────────
    status     = result.get("status", "UNKNOWN")
    confidence = result.get("confidence", 0.0)
    gas_delta  = result.get("gas_delta", gas_result.delta_kohms)
    scan_id    = result.get("scan_id", "SCAN_0000")

    # Automatically record to dataset CSV for machine learning
    if gas.installed:
        gas.log_scan_dataset(scan_id=scan_id, fruit_type=produce_name, condition=status, gas_result=gas_result)

    if status == "SERVER_OFFLINE":
        display.show_server_offline()
    else:
        display.show_result(status=status, confidence=confidence, gas_delta=gas_delta)

    log.info("=== Result: %s (%.1f%% confidence) | Gas Delta: %.2f kOhm ===", status, confidence, gas_delta)
    return result


def main():
    log.info("AgriScan 360 — Adaptive Master Orchestrator Starting (simulate=%s)", SIM)

    led_mode = prompt_led_mode()

    # Initialize Hardware Modules with Adaptive Fallbacks
    motor    = StepperMotor(simulate=SIM)
    lights   = LightController(mode=led_mode, simulate=SIM)
    gas      = GasSensor(simulate=SIM)
    camera   = CameraController(simulate=SIM)
    display  = OLEDDisplay(simulate=SIM)
    uploader = ScanUploader()

    if SIM:
        from unittest.mock import MagicMock
        motor = MagicMock()
        motor.full_scan_positions.return_value = iter(range(NUM_SCAN_STOPS))
        motor.advance_45_degrees = MagicMock()
        motor.set_direction = MagicMock()
        motor.enable = MagicMock()
        motor.disable = MagicMock()
        motor.cleanup = MagicMock()

    display.show_splash()

    if not uploader.check_server():
        log.warning("Laptop server not reachable at startup. Will retry per scan.")

    try:
        while True:
            produce = prompt_produce()
            result  = run_scan(motor, lights, camera, gas, display, uploader, produce)

            log.info("Scan session complete: %s", result)
            time.sleep(3)

            if args.no_loop:
                break

            again = input("\nScan another produce? [Y/n]: ").strip().lower()
            if again == "n":
                break

    except KeyboardInterrupt:
        log.info("Shutdown requested by operator.")
    finally:
        log.info("Cleaning up hardware resources...")
        try:
            motor.cleanup()
        except Exception:
            pass
        lights.cleanup()
        camera.cleanup()
        display.clear()
        uploader.close()
        log.info("AgriScan 360 shutdown complete.")


if __name__ == "__main__":
    main()
