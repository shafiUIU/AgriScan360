"""
main.py — AgriScan 360 Raspberry Pi 5 Master Orchestrator
===========================================================
Run this script on the Raspberry Pi to start the scan cycle.

Scan sequence per fruit:
    1.  Prompt operator for produce name (keyboard or auto-detect in Stage 2)
    2.  Calibrate BME688 gas baseline (empty chamber)
    3.  Place fruit on turntable — display "READY" on OLED
    4.  Wait for operator confirmation (press Enter or button)
    5.  For each of 8 turntable stops (0°, 45°, …, 315°):
            a. Advance motor 45°
            b. Capture RGB image (white light)
            c. Capture UV image  (365nm UV-A light)
    6.  Compute gas delta (post-scan vs baseline)
    7.  Upload all 16 images + gas data to laptop server
    8.  Display classification result on OLED
    9.  De-energize motor coils
    10. Repeat or exit

Usage:
    cd /path/to/pi_client
    python main.py
    python main.py --simulate          # Run without hardware (PC testing)
    python main.py --produce Tomato    # Skip produce name prompt
"""

import argparse
import logging
import sys
import time

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("agriscan.main")

# ---------------------------------------------------------------------------
# Argument Parsing
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(description="AgriScan 360 — Pi Scan Orchestrator")
parser.add_argument("--simulate", action="store_true",
                    help="Run in simulation mode (no hardware required)")
parser.add_argument("--produce",  type=str, default=None,
                    help="Produce name (skips interactive prompt)")
parser.add_argument("--no-loop",  action="store_true",
                    help="Run a single scan then exit")
args = parser.parse_args()

SIM = args.simulate

# ---------------------------------------------------------------------------
# Module Imports
# ---------------------------------------------------------------------------
from motor      import StepperMotor
from lights     import LightController
from gas_sensor import GasSensor
from camera     import CameraController
from display    import OLEDDisplay
from uploader   import ScanUploader
from config     import SUPPORTED_PRODUCE, NUM_SCAN_STOPS


def prompt_produce() -> str:
    """Ask operator to select the produce type being scanned."""
    if args.produce:
        name = args.produce.strip().title()
        if name in SUPPORTED_PRODUCE:
            return name
        log.warning("'%s' not in supported list. Using as-is.", name)
        return name

    print("\n┌─ Select Produce ─────────────────────────────┐")
    for i, name in enumerate(SUPPORTED_PRODUCE, 1):
        print(f"│  {i:2d}. {name:<38} │")
    print(f"│  {len(SUPPORTED_PRODUCE)+1:2d}. Other / Unknown{'':24} │")
    print("└───────────────────────────────────────────────┘")

    while True:
        try:
            choice = int(input("Enter number: ").strip())
            if 1 <= choice <= len(SUPPORTED_PRODUCE):
                return SUPPORTED_PRODUCE[choice - 1]
            elif choice == len(SUPPORTED_PRODUCE) + 1:
                return input("Enter produce name: ").strip().title() or "Unknown"
        except (ValueError, KeyboardInterrupt):
            print("Invalid input. Please enter a number.")


def run_scan(motor: StepperMotor,
             lights: LightController,
             camera: CameraController,
             gas: GasSensor,
             display: OLEDDisplay,
             uploader: ScanUploader,
             produce_name: str) -> dict:
    """
    Execute one complete 360° scan cycle.
    Returns the classification result dict from the server.
    """
    rgb_images = []
    uv_images  = []

    # ── Step 1: Gas Baseline ──────────────────────────────────────────────────
    log.info("=== Starting scan for: %s ===", produce_name)
    display.show_uploading()   # Repurpose as "Calibrating..."
    display.show_scanning(stop=-1)
    gas_baseline = gas.calibrate_baseline()

    # ── Step 2: Wait for fruit placement ─────────────────────────────────────
    display.show_ready()
    log.info("Place '%s' on the turntable. Press Enter when ready...", produce_name)
    try:
        input()
    except EOFError:
        pass   # Non-interactive mode

    # ── Step 3: 8-Stop Scan Cycle ─────────────────────────────────────────────
    log.info("Starting 8-stop 360° scan cycle...")
    try:
        for stop in motor.full_scan_positions():
            display.show_scanning(stop=stop, total=NUM_SCAN_STOPS)
            log.info("  → Stop %d/8  (%.0f°)", stop + 1, stop * 45)

            rgb_bytes, uv_bytes = camera.capture_pair(lights, stop_index=stop)
            rgb_images.append(rgb_bytes)
            uv_images.append(uv_bytes)

    except KeyboardInterrupt:
        log.warning("Scan interrupted by user.")
        motor.cleanup()
        lights.off_all()
        display.show_error("Scan cancelled")
        return {"status": "CANCELLED", "confidence": 0.0, "reason": "User interrupted"}

    # ── Step 4: Gas Delta ─────────────────────────────────────────────────────
    gas_result = gas.compute_delta()
    log.info("Gas delta: %.2f kΩ  Suspicion: %s",
             gas_result.delta_kohms, gas_result.rot_suspicion)

    # ── Step 5: Upload to Laptop Server ───────────────────────────────────────
    display.show_uploading()
    result = uploader.upload_scan(
        rgb_images=rgb_images,
        uv_images=uv_images,
        gas_result=gas_result,
        produce_name=produce_name,
    )

    # ── Step 6: Display Result ────────────────────────────────────────────────
    status     = result.get("status", "UNKNOWN")
    confidence = result.get("confidence", 0.0)
    gas_delta  = result.get("gas_delta", gas_result.delta_kohms)

    if status == "SERVER_OFFLINE":
        display.show_server_offline()
    else:
        display.show_result(status=status, confidence=confidence, gas_delta=gas_delta)

    log.info("=== Result: %s  (%.1f%% confidence) ===", status, confidence)
    return result


def main():
    """Main entry point — initialize hardware, run scan loop."""
    log.info("AgriScan 360 — Pi Orchestrator Starting (simulate=%s)", SIM)

    # Initialize all hardware modules
    motor    = StepperMotor()         if not SIM else StepperMotor.__new__(StepperMotor)
    lights   = LightController()
    camera   = CameraController(simulate=SIM)
    gas      = GasSensor(simulate=SIM)
    display  = OLEDDisplay(simulate=SIM)
    uploader = ScanUploader()

    if SIM:
        # Provide stub motor for simulation
        from unittest.mock import MagicMock
        motor = MagicMock()
        motor.full_scan_positions.return_value = iter(range(NUM_SCAN_STOPS))

    display.show_splash()

    # Check server connectivity once at startup
    if not uploader.check_server():
        log.warning("Laptop server not reachable at startup. Will retry per scan.")

    try:
        while True:
            produce = prompt_produce()
            result  = run_scan(motor, lights, camera, gas, display, uploader, produce)

            log.info("Result summary: %s", result)
            time.sleep(3)   # Show result on OLED for 3 seconds

            if args.no_loop:
                log.info("--no-loop flag set. Exiting.")
                break

            again = input("\nScan another fruit? [Y/n]: ").strip().lower()
            if again == "n":
                break

    except KeyboardInterrupt:
        log.info("Shutdown requested by user.")

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
