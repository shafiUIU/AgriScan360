"""
main.py — AgriScan 360 "Update1 Rushed" — Pi Orchestrator
===========================================================
UPDATE1 RUSHED CHANGES:
    - No gas sensor: BME688 calibration and delta steps REMOVED.
    - No LED switching: lights.py is a stub (do-nothing).
    - Camera captures ONE RGB image per stop (LEDs are on manually).
    - Upload sends 8 RGB images only.
    - Full motor + camera scan loop 100% operational.

Scan sequence:
    1. Operator selects produce name.
    2. Operator ensures White LEDs are ON manually inside the chamber.
    3. Press Enter to start.
    4. Motor rotates 8× 45° → camera captures 1 RGB image per stop.
    5. 8 RGB images uploaded to laptop server.
    6. AI classifies (RGB only) → result on OLED + dashboard.

Usage:
    python main.py
    python main.py --simulate
    python main.py --produce Tomato
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

parser = argparse.ArgumentParser(description="AgriScan 360 Update1 Rushed — Pi Orchestrator")
parser.add_argument("--simulate", action="store_true", help="Run without hardware")
parser.add_argument("--produce",  type=str, default=None)
parser.add_argument("--no-loop",  action="store_true")
args = parser.parse_args()
SIM = args.simulate

# ── Imports ────────────────────────────────────────────────────────────────────
from motor    import StepperMotor
from camera   import CameraController
from display  import OLEDDisplay
from uploader import ScanUploader
# from lights     import LightController   # Imported but stub only — no GPIO used
# from gas_sensor import GasSensor         # Imported but stub only — no sensor

from config import SUPPORTED_PRODUCE, NUM_SCAN_STOPS


def prompt_produce() -> str:
    if args.produce:
        name = args.produce.strip().title()
        return name if name in SUPPORTED_PRODUCE else name

    print("\n+-- Select Produce ----------------------------+")
    for i, name in enumerate(SUPPORTED_PRODUCE, 1):
        print(f"|  {i:2d}. {name:<38} |")
    print(f"|  {len(SUPPORTED_PRODUCE)+1:2d}. Other / Unknown{'':24} |")
    print("+----------------------------------------------+")
    while True:
        try:
            choice = int(input("Enter number: ").strip())
            if 1 <= choice <= len(SUPPORTED_PRODUCE):
                return SUPPORTED_PRODUCE[choice - 1]
            elif choice == len(SUPPORTED_PRODUCE) + 1:
                return input("Enter produce name: ").strip().title() or "Unknown"
        except (ValueError, KeyboardInterrupt):
            print("Invalid input.")


def run_scan(motor, camera, display, uploader, produce_name: str) -> dict:
    """
    Execute complete 360° dual-spectral scan:
    Pass 1: 8 RGB images under White light (toggled manually)
    Pass 2: 8 UV images under 365nm UV light (toggled manually)
    Uploads all 16 frames to laptop server.
    """
    rgb_images = []
    uv_images  = []

    log.info("=== Starting scan: %s ===", produce_name)

    # ── PASS 1: White Light (RGB) ──────────────────────────────────────────────
    display.show_ready()
    print(f"\n[>] STEP 1 (RGB): Turn ON White LEDs manually.")
    print(f"[>] Place '{produce_name}' on the turntable.")
    print(f"[>] Press Enter when ready for RGB scan...")

    try:
        input()
    except EOFError:
        pass

    log.info("Starting Pass 1: 8-stop RGB scan...")
    try:
        for stop in motor.full_scan_positions():
            display.show_scanning(stop=stop, total=NUM_SCAN_STOPS)
            log.info("  -> [RGB] Stop %d/8  (%d deg)", stop + 1, stop * 45)
            rgb_bytes = camera.capture_single(stop_index=stop)
            rgb_images.append(rgb_bytes)
    except KeyboardInterrupt:
        log.warning("Scan interrupted.")
        motor.cleanup()
        display.show_error("Scan cancelled")
        return {"status": "CANCELLED", "confidence": 0.0, "reason": "Interrupted"}

    # ── PASS 2: 365nm UV Light ────────────────────────────────────────────────
    print(f"\n[>] STEP 2 (UV): Turn OFF White LEDs, Turn ON 365nm UV LEDs manually.")
    print(f"[>] Press Enter to capture UV fluorescence (or 's' + Enter to skip UV)...")

    skip_uv = False
    try:
        user_choice = input().strip().lower()
        if user_choice == 's':
            skip_uv = True
            log.info("Skipping UV pass on operator request.")
    except EOFError:
        pass

    if not skip_uv:
        log.info("Starting Pass 2: 8-stop UV-A scan...")
        try:
            for stop in motor.full_scan_positions():
                display.show_scanning(stop=stop, total=NUM_SCAN_STOPS)
                log.info("  -> [UV] Stop %d/8  (%d deg)", stop + 1, stop * 45)
                uv_bytes = camera.capture_single(stop_index=stop)
                uv_images.append(uv_bytes)
        except KeyboardInterrupt:
            log.warning("Scan interrupted during UV pass.")
            motor.cleanup()

    # ── Upload to Server (16 frames: 8 RGB + 8 UV) ─────────────────────────────
    display.show_uploading()
    result = uploader.upload_scan(
        rgb_images   = rgb_images,
        uv_images    = uv_images,
        produce_name = produce_name,
    )

    # ── Display Result on OLED ────────────────────────────────────────────────
    status     = result.get("status", "UNKNOWN")
    confidence = result.get("confidence", 0.0)

    if status == "SERVER_OFFLINE":
        display.show_server_offline()
    else:
        # gas_delta passed as 0 since sensor not present
        display.show_result(status=status, confidence=confidence, gas_delta=0.0)

    log.info("=== Result: %s  (%.1f%% confidence) ===", status, confidence)
    return result


def main():
    log.info("AgriScan 360 Update1 Rushed — Starting (simulate=%s)", SIM)
    log.info("Mode: Motor=ACTIVE | Camera=ACTIVE | LEDs=MANUAL | Gas=REMOVED")

    motor    = StepperMotor()
    camera   = CameraController(simulate=SIM)
    display  = OLEDDisplay(simulate=SIM)
    uploader = ScanUploader()

    # ── REMOVED hardware that isn't in this build ─────────────────────────────
    # lights   = LightController()   # Stub — no GPIO used, LEDs are manual
    # gas      = GasSensor(simulate=True)  # Stub — no BME688

    if SIM:
        from unittest.mock import MagicMock
        motor = MagicMock()
        motor.full_scan_positions.return_value = iter(range(NUM_SCAN_STOPS))
        motor.cleanup = MagicMock()

    display.show_splash()

    if not uploader.check_server():
        log.warning("Laptop server not reachable at startup.")

    try:
        while True:
            produce = prompt_produce()
            result  = run_scan(motor, camera, display, uploader, produce)
            log.info("Scan done: %s", result)
            time.sleep(3)

            if args.no_loop:
                break

            again = input("\nScan another? [Y/n]: ").strip().lower()
            if again == "n":
                break

    except KeyboardInterrupt:
        log.info("Shutdown requested.")
    finally:
        log.info("Cleaning up...")
        try:
            motor.cleanup()
        except Exception:
            pass
        camera.cleanup()
        display.clear()
        uploader.close()
        log.info("Shutdown complete.")


if __name__ == "__main__":
    main()
