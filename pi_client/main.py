"""
main.py — AgriScan 360 Master Orchestrator (Adaptive Multi-Modal Scan)
========================================================================
Supports:
  - Produce Focus: Tomato, Apple, Eggplant (Brinjal)
  - 27L Closed Box Environment
  - Turntable Stepper Motor (8 stops x 45 deg = 360 deg)
  - Sequential Illumination:
      White LED ON  -> RGB Snap  -> White LED OFF
      UV-A LED ON   -> UV Snap   -> UV-A LED OFF
      Motor rotates 45 deg
  - Continuous BME688 Sniffing:
      Sniffs VOC gas resistance the entire duration while the 16 photos are taken.
  - Adaptive Fallbacks:
      1. If no MOSFET connected: prompts operator to switch White & UV-A LEDs manually.
      2. If no BME688 connected: assumes sensor not yet implemented and proceeds in vision-only mode.

New Scan Flow (v2):
  OUTER LOOP:
    Step A: Empty box -> press Enter -> BME calibrates clean-air baseline
    Step B: Place fruit -> close box -> press Enter
            -> Camera takes detect snapshot -> auto-classifies produce by color heuristic
               * If confidence >= 70%: auto-proceed
               * If confidence < 70% : ask operator to confirm
               * If unrecognised      : warn + loop back to Step B
    Step C: BME starts sniffing (background thread)
            MOSFET mode (zero keypresses):
              White LED ON (5s) -> snap -> OFF -> UV LED ON (5s) -> snap -> OFF -> motor 45deg
              x 8 stops = 16 photos, fully automatic
            Manual mode (unchanged):
              Operator switches LEDs and presses Enter per stop
    Step D: BME stops -> per-produce 4-tier freshness result -> upload -> loop to Step A
"""

import argparse
import colorsys
import io
import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("agriscan.main")

parser = argparse.ArgumentParser(description="AgriScan 360 -- Adaptive Master Orchestrator")
parser.add_argument("--simulate",    action="store_true", help="Run without hardware (PC test mode)")
parser.add_argument("--produce",     type=str, default=None, help="Force produce name (Tomato, Apple, Eggplant)")
parser.add_argument("--manual-leds", action="store_true", help="Force manual operator LED switching")
parser.add_argument("--mosfet",      action="store_true", help="Force automatic MOSFET GPIO LED switching")
parser.add_argument("--no-loop",     action="store_true", help="Run single scan then exit")
args = parser.parse_args()

SIM = args.simulate

from motor      import StepperMotor
from lights     import LightController
from gas_sensor import GasSensor, ScanGasResult
from camera     import CameraController
from display    import OLEDDisplay
from uploader   import ScanUploader
import config as cfg
from config     import SUPPORTED_PRODUCE, NUM_SCAN_STOPS, CHAMBER_VOLUME_LITERS

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    log.warning("Pillow not installed. Produce auto-detection will be unavailable.")


# ─────────────────────────────────────────────────────────────────────────────
# LED MODE SELECTION
# ─────────────────────────────────────────────────────────────────────────────

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
    print("|  2. MOSFET (IRLZ44N auto GPIO 18 & 24)      |")
    print("+----------------------------------------------+")
    try:
        ans = input("Select mode [1/2] (Default 1 = Manual): ").strip()
        if ans == "2":
            return "auto"
    except (KeyboardInterrupt, EOFError):
        pass
    return "manual"


# ─────────────────────────────────────────────────────────────────────────────
# PRODUCE AUTO-DETECTION (Color Heuristic — Pillow)
# ─────────────────────────────────────────────────────────────────────────────

def _classify_image_bytes(img_bytes: bytes):
    """
    Analyse a JPEG snapshot and classify the centre-crop by dominant color.

    Returns (produce_name: str | None, confidence_pct: int)
      - produce_name: 'Tomato', 'Apple', 'Eggplant', or None if unrecognised
      - confidence_pct: 0-97 integer

    Color heuristics (HSV space):
      Eggplant : > 35% of centre pixels are very dark (V < 0.25)
      Tomato   : > 25% of centre pixels are red hue (0-30 or 330-360 deg), high saturation
      Apple    : > 20% of centre pixels are green hue (90-150 deg), high saturation
                 OR red-dominant but brighter/rounder than typical tomato
    """
    if not PIL_AVAILABLE or not img_bytes:
        return None, 0

    try:
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        w, h = img.size
        # Centre 40% region
        margin_w, margin_h = w // 5, h // 5
        region = img.crop((
            max(0, w // 2 - margin_w),
            max(0, h // 2 - margin_h),
            min(w, w // 2 + margin_w),
            min(h, h // 2 + margin_h),
        ))
        pixels = list(region.getdata())
        n = len(pixels)
        if n == 0:
            return None, 0

        dark_count = red_count = green_count = 0

        for r, g, b in pixels:
            hf, sf, vf = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
            hue_deg = hf * 360.0

            if vf < 0.25:                                   # Very dark → Eggplant
                dark_count += 1
            elif sf > 0.30:                                 # Saturated colour
                if hue_deg <= 30 or hue_deg >= 330:        # Red hue band
                    red_count += 1
                elif 90 <= hue_deg <= 150:                  # Green hue band
                    green_count += 1

        dark_pct  = dark_count  / n * 100
        red_pct   = red_count   / n * 100
        green_pct = green_count / n * 100

        log.info("Detect snapshot analysis — dark=%.1f%% red=%.1f%% green=%.1f%%",
                 dark_pct, red_pct, green_pct)

        if dark_pct >= 35:
            conf = int(min(dark_pct * 1.8, 97))
            return "Eggplant", conf
        elif red_pct >= 25:
            # Distinguish Tomato vs Apple (red variety):
            # Tomatoes are darker red (lower V avg in red pixels vs apple)
            conf = int(min(red_pct * 2.2, 97))
            return "Tomato", conf
        elif green_pct >= 20:
            conf = int(min(green_pct * 2.8, 97))
            return "Apple", conf
        else:
            return None, 0

    except Exception as exc:
        log.warning("Produce detection image analysis failed: %s", exc)
        return None, 0


def detect_produce(camera: "CameraController", lights: "LightController"):
    """
    Take a single detection snapshot and auto-classify the produce on the turntable.

    MOSFET mode: White LED turns ON briefly (0.5s), snap, OFF.
    Manual mode: Prompt operator to turn White LED ON, press Enter, snap.

    Returns (produce_name: str | None, confidence_pct: int)
    """
    if args.produce:
        return args.produce.strip().title(), 99

    if not PIL_AVAILABLE:
        log.warning("Pillow not installed — produce auto-detection skipped.")
        return None, 0

    # ── Light management for detection snapshot ────────────────────────────
    if lights.mode == "auto" and lights._white_dev:
        if lights._uv_dev:
            lights._uv_dev.off()
        lights._white_dev.on()
        time.sleep(0.5)   # Short warmup for detection only (not the full 5s scan hold)
        img_bytes = camera.capture_jpeg()
        lights._white_dev.off()
    elif lights.mode == "manual":
        print("\n[>] PRODUCE DETECTION: Make sure the White LED is switched ON.")
        print("[>] Press [Enter] when the light is on and fruit is visible...", end="", flush=True)
        try:
            input()
        except EOFError:
            pass
        img_bytes = camera.capture_jpeg()
        print("    [Detection snapshot taken — you may turn off the White LED now]")
    else:
        # Simulate mode — capture test image
        img_bytes = camera.capture_jpeg()
        detected, conf = _classify_image_bytes(img_bytes)
        if detected is None:
            return "Tomato", 95
        return detected, conf

    return _classify_image_bytes(img_bytes)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN SCAN FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def run_scan(motor:   "StepperMotor",
             lights:  "LightController",
             camera:  "CameraController",
             gas:     "GasSensor",
             display: "OLEDDisplay",
             uploader: "ScanUploader") -> dict:
    """
    Execute one complete AgriScan 360 cycle:
      Step A — Empty-box BME688 baseline calibration
      Step B — Place produce, close box, auto-detect produce type
      Step C — 8-stop 360-deg turntable scan (MOSFET: fully automatic / Manual: Enter-per-stop)
      Step D — Gas analytics, upload, per-produce freshness result
    """
    rgb_images: list = []
    uv_images:  list = []

    display.show_ready()
    print("\n" + "=" * 62)
    print(f"  AgriScan 360  |  Chamber: {CHAMBER_VOLUME_LITERS}L Box  |  "
          f"LED: {'MOSFET Auto' if lights.mode == 'auto' else 'Manual'}")
    print(f"  Gas Sensor: {'Active' if gas.installed else 'Not Installed (Vision Only)'}")
    print("=" * 62)

    # ── Step A: Empty chamber — BME688 clean-air baseline ────────────────────
    if gas.installed:
        print("\n[>] STEP A: Remove all produce from the box.")
        print("[>] Close the lid tightly, then press [Enter] to calibrate clean air...",
              end="", flush=True)
        try:
            input()
        except EOFError:
            pass
        display.show_scanning(stop=-1)
        gas.calibrate_baseline()
        print(f"    -> Clean-air baseline: {gas._baseline.gas_kohms:.2f} kOhm  "
              f"| {gas._baseline.temperature:.1f}C  "
              f"| {gas._baseline.humidity:.1f}%RH")

        # Automatically log empty closed box reading for baseline training
        try:
            empty_res = ScanGasResult(
                baseline_kohms=gas._baseline.gas_kohms,
                post_scan_kohms=gas._baseline.gas_kohms,
                delta_kohms=0.0,
                gas_min_kohms=gas._baseline.gas_kohms,
                gas_max_kohms=gas._baseline.gas_kohms,
                gas_mean_kohms=gas._baseline.gas_kohms,
                gas_std_kohms=0.0,
                gas_ratio_pct=0.0,
                gas_slope_per_sec=0.0,
                temperature_c=gas._baseline.temperature,
                humidity_pct=gas._baseline.humidity,
                pressure_hpa=gas._baseline.pressure,
                sample_count=1,
                rot_suspicion="EMPTY_BOX",
                installed=True,
            )
            gas.log_scan_dataset(
                scan_id=f"BASE_{int(time.time())}",
                fruit_type="empty_box",
                condition="EMPTY_BOX",
                predicted_condition="EMPTY_BOX",
                gas_result=empty_res,
            )
        except Exception as exc:
            log.warning("Could not log empty box baseline: %s", exc)
    else:
        print("\n[>] BME688 not installed — skipping gas baseline calibration.")

    # ── Step B: Place produce, auto-detect ───────────────────────────────────
    produce_name = None
    if args.produce:
        produce_name = args.produce.strip().title()
        print(f"\n[>] Produce forced via argument: {produce_name}")

    while produce_name is None:
        print(f"\n[>] STEP B: Place the produce on the turntable.")
        print("[>] Close the box lid tightly.")
        print("[>] Press [Enter] when ready for detection...", end="", flush=True)
        try:
            input()
        except EOFError:
            pass

        detected, confidence = detect_produce(camera, lights)

        if detected is None:
            # Could not identify any supported produce
            print("\n[!] CANNOT IDENTIFY PRODUCE.")
            print("[!] Supported items: Tomato, Apple, Eggplant")
            print("[!] Make sure the produce is centred on the turntable and visible.")
            print("    1. Try scanning/detecting again")
            print("    2. Select produce manually")
            try:
                choice = input("Select [1/2] (Default 1 = Try again): ").strip()
            except EOFError:
                choice = "1"
            if choice == "2":
                print("\nSelect Produce:")
                print("  1. Tomato\n  2. Apple\n  3. Eggplant")
                sel = input("Enter number [1-3]: ").strip()
                mapping = {"1": "Tomato", "2": "Apple", "3": "Eggplant"}
                produce_name = mapping.get(sel, "Tomato")
                break
            continue  # Loop back to Step B

        if confidence >= 70:
            # Auto-proceed — high confidence
            print(f"\n[>] Detected: {detected}  ({confidence}% confidence) — proceeding automatically.")
            produce_name = detected
        else:
            # Low confidence — ask operator
            print(f"\n[?] Detected: {detected}  ({confidence}% confidence — LOW)")
            try:
                ans = input("[?] Is this correct? [Y/n]: ").strip().lower()
            except EOFError:
                ans = "y"
            if ans in ("", "y", "yes"):
                produce_name = detected
            else:
                print("[!] Not confirmed. Remove item and try again.\n")
                # Loop back to Step B

    log.info("Produce confirmed: %s", produce_name)
    display.show_scanning(stop=0, total=NUM_SCAN_STOPS)

    # Optional pre-scan incubation (default 0 — disabled)
    if cfg.GAS_PRE_SCAN_INCUBATION_SEC > 0:
        print(f"[>] Incubating chamber for {cfg.GAS_PRE_SCAN_INCUBATION_SEC}s "
              "(set GAS_PRE_SCAN_INCUBATION_SEC=0 in config.py to skip)...")
        time.sleep(cfg.GAS_PRE_SCAN_INCUBATION_SEC)

    # ── Step C: BME starts sniffing + 8-stop turntable scan ──────────────────
    gas.start_continuous_sniffing()

    log.info("=== Starting scan for %s (Chamber %.1fL) ===", produce_name, CHAMBER_VOLUME_LITERS)
    motor.set_direction(clockwise=True)
    motor.enable()

    try:
        for stop in range(NUM_SCAN_STOPS):
            angle = stop * 45
            display.show_scanning(stop=stop, total=NUM_SCAN_STOPS)
            print(f"\n--- [Stop {stop + 1}/{NUM_SCAN_STOPS}  ({angle} deg)] ---")

            # A. White LED ON → RGB snap → White LED OFF
            with lights.capture_white(stop_index=stop, angle=angle):
                rgb_bytes = camera.capture_jpeg()
                rgb_images.append(rgb_bytes)
                log.info("  -> [RGB] Stop %d/8 (%d deg)", stop + 1, angle)

            time.sleep(0.1)   # brief settle between LEDs

            # B. UV-A LED ON → UV snap → UV-A LED OFF
            with lights.capture_uv(stop_index=stop, angle=angle):
                uv_bytes = camera.capture_jpeg()
                uv_images.append(uv_bytes)
                log.info("  -> [UV-A] Stop %d/8 (%d deg)", stop + 1, angle)

            # C. Rotate 45 deg (every stop — including last stop returns to 0 deg home)
            if stop < NUM_SCAN_STOPS - 1:
                next_angle = (stop + 1) * 45
                print(f"[>] Rotating 45 deg to Stop {stop + 2}/{NUM_SCAN_STOPS} ({next_angle} deg)...")
            else:
                print("[>] All 16 photos done. Returning turntable to home position (0 deg)...")
            motor.advance_45_degrees()

    except KeyboardInterrupt:
        log.warning("Scan interrupted by operator (Ctrl+C).")
        gas.stop_continuous_sniffing(produce_name=produce_name)
        motor.cleanup()
        lights.off_all()
        display.show_error("Scan cancelled")
        return {"status": "CANCELLED", "confidence": 0.0, "reason": "Interrupted by user"}
    finally:
        motor.disable()
        lights.off_all()

    # ── Step D: Stop BME sniffing — per-produce gas analytics ────────────────
    gas_result = gas.stop_continuous_sniffing(produce_name=produce_name)

    if gas.installed:
        _print_gas_table(gas_result, produce_name)
    else:
        log.info("Gas sensing bypassed (BME688 not installed). Proceeding vision-only.")

    # ── Upload all 16 frames + gas result ────────────────────────────────────
    display.show_uploading()
    result = uploader.upload_scan(
        rgb_images=rgb_images,
        uv_images=uv_images,
        gas_result=gas_result,
        produce_name=produce_name,
    )

    # ── Show final result ─────────────────────────────────────────────────────
    status     = result.get("status",     "UNKNOWN")
    confidence = result.get("confidence", 0.0)
    gas_delta  = result.get("gas_delta",  gas_result.delta_kohms)
    scan_id    = result.get("scan_id",    "SCAN_0000")

    if status == "SERVER_OFFLINE":
        display.show_server_offline()
        # In offline mode, use gas rot_suspicion as the assumption
        if gas.installed and gas_result.rot_suspicion not in ("NOT_INSTALLED", "UNKNOWN"):
            status = gas_result.rot_suspicion
    else:
        display.show_result(status=status, confidence=confidence, gas_delta=gas_delta)

    _print_result(produce_name, status, confidence, gas_delta, gas_result)
    log.info("=== System Assumption: %s (%.1f%%) | Gas Delta: %.2f kOhm ===",
             status, confidence, gas_delta)

    # ── Step E: Ground-Truth Verification & Feedback Loop ─────────────────────
    # "You assume, I correct" — Operator verifies or corrects the AI's judgment
    actual_condition = prompt_ground_truth_correction(assumed_status=status)

    # Record to dataset CSV for ML training (records both ground truth and prediction)
    if gas.installed:
        gas.log_scan_dataset(
            scan_id=scan_id,
            fruit_type=produce_name,
            condition=actual_condition,
            predicted_condition=status,
            gas_result=gas_result,
        )

    # Sync ground-truth label to laptop server database
    if scan_id and scan_id != "SCAN_0000":
        uploader.send_ground_truth(scan_id=scan_id, ground_truth=actual_condition)

    return result


def prompt_ground_truth_correction(assumed_status: str) -> str:
    """
    Operator Ground-Truth Feedback Loop:
    The AI system assumes a condition ('FRESH', 'MID_FRESH', 'MID_ROTTEN', 'ROTTEN').
    The operator inspects the produce and either confirms or corrects the assumption.
    This ground-truth label is recorded for training the user's personal models.
    """
    options = ["FRESH", "MID_FRESH", "MID_ROTTEN", "ROTTEN"]
    clean_assumed = assumed_status.upper().strip()
    if clean_assumed not in options:
        clean_assumed = "FRESH"

    print("\n" + "-" * 62)
    print("  [GROUND TRUTH VERIFICATION & DATASET LABELING]")
    print(f"  System Assumption: [{clean_assumed}]")
    print("  Press [Enter] if correct, or 'c' to correct: ", end="", flush=True)
    try:
        choice = input().strip().lower()
    except EOFError:
        choice = ""

    if choice in ("", "y", "yes"):
        print(f"  -> Confirmed Ground Truth: [{clean_assumed}]")
        return clean_assumed

    # Operator wants to correct the label
    print("\n  Select ACTUAL produce condition for training:")
    for idx, opt in enumerate(options, 1):
        print(f"    {idx}. {opt}")
    while True:
        try:
            sel = input("  Enter number [1-4] (or press Enter to keep assumption): ").strip()
            if sel == "":
                return clean_assumed
            val = int(sel)
            if 1 <= val <= len(options):
                corrected = options[val - 1]
                print(f"  -> Corrected Ground Truth: [{corrected}] (Overrode assumption: {clean_assumed})")
                return corrected
        except (ValueError, KeyboardInterrupt):
            pass
        print("  Invalid selection. Please enter 1, 2, 3, or 4.")


# ─────────────────────────────────────────────────────────────────────────────
# DISPLAY HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _print_gas_table(gas_result: "ScanGasResult", produce_name: str):
    """Pretty-print the BME688 headspace gas analytics table."""
    print("\n+--- BME688 Headspace Gas Analytics -------------------+")
    print(f"|  Produce             : {produce_name:<30} |")
    print(f"|  Baseline Resistance : {gas_result.baseline_kohms:6.2f} kOhm                    |")
    print(f"|  Post-Scan Resistance: {gas_result.post_scan_kohms:6.2f} kOhm                    |")
    print(f"|  Min / Max Observed  : {gas_result.gas_min_kohms:6.2f} / {gas_result.gas_max_kohms:6.2f} kOhm        |")
    print(f"|  Mean / Std Dev      : {gas_result.gas_mean_kohms:6.2f} +/- {gas_result.gas_std_kohms:5.2f} kOhm       |")
    print(f"|  Relative Drop Ratio : {gas_result.gas_ratio_pct:5.1f}%                         |")
    print(f"|  Decay Rate (dR/dt)  : {gas_result.gas_slope_per_sec:+7.4f} kOhm/s                  |")
    print(f"|  Environmental       : {gas_result.temperature_c:4.1f}C | "
          f"{gas_result.humidity_pct:4.1f}%RH | {gas_result.pressure_hpa:6.1f}hPa |")
    print(f"|  Samples Collected   : {gas_result.sample_count:<4d} snapshots                  |")
    print(f"|  Freshness Status    : {gas_result.rot_suspicion:<28s} |")
    print("+------------------------------------------------------+")


def _print_result(produce_name: str, status: str, confidence: float,
                  gas_delta: float, gas_result: "ScanGasResult"):
    """Print the final scan result banner."""
    # Status emoji mapping (ASCII-safe)
    icons = {
        "FRESH":      "[FRESH]",
        "MID_FRESH":  "[MID-FRESH]",
        "MID_ROTTEN": "[MID-ROTTEN]",
        "ROTTEN":     "[ROTTEN]",
        "HEALTHY":    "[HEALTHY]",
        "UNCERTAIN":  "[UNCERTAIN]",
    }
    icon = icons.get(status, "[UNKNOWN]")

    print("\n" + "=" * 62)
    print(f"  {icon}  {produce_name}")
    print(f"  Visual Confidence : {confidence:.1f}%")
    print(f"  Gas Freshness     : {gas_result.rot_suspicion}")
    print(f"  Gas Delta         : {gas_delta:.2f} kOhm")
    print("=" * 62)
    print("[>] Scan complete. Emptying box for next cycle...")
    print("=" * 62)


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main():
    log.info("AgriScan 360 v2 — Adaptive Master Orchestrator starting (simulate=%s)", SIM)

    led_mode = prompt_led_mode()

    # Initialise hardware modules with adaptive fallbacks
    motor    = StepperMotor(simulate=SIM)
    lights   = LightController(mode=led_mode, simulate=SIM)
    gas      = GasSensor(simulate=SIM)
    camera   = CameraController(simulate=SIM)
    display  = OLEDDisplay(simulate=SIM)
    uploader = ScanUploader()

    if SIM:
        from unittest.mock import MagicMock
        motor = MagicMock()
        motor.advance_45_degrees = MagicMock()
        motor.set_direction      = MagicMock()
        motor.enable             = MagicMock()
        motor.disable            = MagicMock()
        motor.cleanup            = MagicMock()

    display.show_splash()

    if not uploader.check_server():
        log.warning("Laptop server not reachable at startup. Will retry per scan.")

    try:
        while True:
            result = run_scan(motor, lights, camera, gas, display, uploader)
            log.info("Scan session complete: %s", result)

            # Brief pause between scans — gives operator time to see the result
            time.sleep(3)

            if args.no_loop:
                log.info("--no-loop flag set. Exiting after single scan.")
                break
            # No "scan another?" prompt — automatically loops back to Step A

    except KeyboardInterrupt:
        log.info("Shutdown requested by operator (Ctrl+C).")
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
