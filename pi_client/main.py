"""
main.py -- AgriScan 360 Master Orchestrator (Adaptive Multi-Modal Scan)
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
from servo      import PipeDoor
import config as cfg
from config     import SUPPORTED_PRODUCE, NUM_SCAN_STOPS, CHAMBER_VOLUME_LITERS

try:
    from PIL import Image, ImageOps
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    log.warning("Pillow not installed. Produce auto-detection will be unavailable.")


# -----------------------------------------------------------------------------
# LED MODE SELECTION
# -----------------------------------------------------------------------------

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


# -----------------------------------------------------------------------------
# PRODUCE AUTO-DETECTION (Color Heuristic -- Pillow)
# -----------------------------------------------------------------------------

def _classify_image_bytes(img_bytes: bytes):
    """
    Analyse a JPEG snapshot and classify the centre-crop by dominant color & feature heuristics.

    Returns (produce_name: str | None, confidence_pct: int)
      - produce_name: 'Tomato', 'Apple', 'Eggplant', or None if unrecognised
      - confidence_pct: 0-97 integer

    Classification Logic:
      1. Background & Shadow Rejection:
         Pixels with very low brightness (V < 0.12) or neutral grey/dark background
         (V < 0.32 and S < 0.20) are turntable surface or shadows and are NOT counted
         towards produce identification.
      2. Eggplant (Brinjal):
         Must show true purple/violet chromatic presence:
           - Hue in purple/violet band (240 - 335 deg) with visible saturation (S >= 0.18), OR
           - Deep purple where R > G + 8 and B > G + 4 with S >= 0.15.
         Pure black/grey items (R ~ G ~ B, low saturation, shadows) are rejected.
      3. Green / Yellow-Green Apple:
         Vibrant green hue (75 - 155 deg) or gold/yellow (40 - 75 deg) with S >= 0.22, V >= 0.20.
      4. Red Produce (Tomato vs Red Apple):
         Red hue (0 - 30 deg or 335 - 360 deg) with S >= 0.28, V >= 0.18.
         - Red Apple: Features yellow/green undertones or higher green ratio (G/R > 0.36 or yellow+green >= 8%).
         - Tomato: Uniform deep crimson red with low green ratio (G/R <= 0.36) and high saturation.
      5. Unrecognised / Non-Produce (None):
         - Items dominated by blue/cyan hues (160 - 245 deg) -> vetoed as non-produce.
         - Neutral objects (grey, white, black, brown cardboard, phone, keys, empty turntable).
         - Objects lacking sufficient produce-characteristic pixels (< 18-20%).
    """
    if not PIL_AVAILABLE or not img_bytes:
        return None, 0

    try:
        # Save snapshot to disk for debugging / inspection
        try:
            with open("last_detect.jpg", "wb") as f:
                f.write(img_bytes)
        except Exception:
            pass

        raw_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        w, h = raw_img.size

        # Dynamic histogram stretch to handle dim 3.7V LED illumination
        try:
            img = ImageOps.autocontrast(raw_img, cutoff=1)
        except Exception:
            img = raw_img

        # Crop central 60% region (covers turntable even if fruit rolls off-center)
        margin_w = int(w * 0.20)
        margin_h = int(h * 0.20)
        region = img.crop((margin_w, margin_h, w - margin_w, h - margin_h))

        # Downsample for fast and noise-smoothed pixel voting
        region = region.resize((160, 120), Image.Resampling.BILINEAR if hasattr(Image, "Resampling") else Image.BILINEAR)
        pixels = list(region.getdata())
        n = len(pixels)
        if n == 0:
            return None, 0

        eggplant_purple_count = 0
        tomato_red_count = 0
        apple_green_count = 0
        apple_yellow_count = 0
        red_apple_count = 0
        neutral_dark_count = 0
        blue_cyan_count = 0
        red_pixel_g_r_ratios = []

        for r, g, b in pixels:
            hf, sf, vf = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
            hue_deg = hf * 360.0

            # 1. Background & Deep Shadow rejection:
            is_dark_bg = (vf < 0.12) or (vf < 0.22 and sf < 0.14)
            if is_dark_bg:
                neutral_dark_count += 1
                continue

            # 2. Eggplant (Purple / Violet):
            is_purple_hue = (235 <= hue_deg <= 335) and (sf >= 0.14)
            is_rgb_purple = (r > g + 4) and (b > g + 2) and (r >= 20 or b >= 20) and (sf >= 0.12)
            if is_purple_hue or is_rgb_purple:
                eggplant_purple_count += 1
                continue

            # 3. Green Apple:
            if (70 <= hue_deg <= 160) and (sf >= 0.15) and (vf >= 0.14):
                apple_green_count += 1
                continue

            # 4. Yellow / Golden Apple:
            if (35 <= hue_deg < 70) and (sf >= 0.18) and (vf >= 0.18):
                apple_yellow_count += 1
                continue

            # 5. Red pixels (Tomato vs Red Apple):
            if ((hue_deg <= 30) or (hue_deg >= 335)) and (sf >= 0.20) and (vf >= 0.14):
                g_r = g / max(1, r)
                red_pixel_g_r_ratios.append(g_r)
                if g_r > 0.38:
                    red_apple_count += 1
                else:
                    tomato_red_count += 1
                continue

            # 6. Blue / Cyan (non-produce reject)
            if (165 <= hue_deg <= 235) and (sf >= 0.30):
                blue_cyan_count += 1
                continue

        purple_pct = (eggplant_purple_count / n) * 100.0
        green_pct  = (apple_green_count / n) * 100.0
        yellow_pct = (apple_yellow_count / n) * 100.0
        red_pct    = ((tomato_red_count + red_apple_count) / n) * 100.0
        blue_pct   = (blue_cyan_count / n) * 100.0
        dark_pct   = (neutral_dark_count / n) * 100.0

        total_chromatic = eggplant_purple_count + tomato_red_count + red_apple_count + apple_green_count + apple_yellow_count
        chromatic_pct = (total_chromatic / n) * 100.0

        log.info(
            "Detect snapshot analysis -- chromatic=%.1f%% (red=%.1f%% green=%.1f%% yellow=%.1f%% purple=%.1f%% blue=%.1f%% dark=%.1f%%)",
            chromatic_pct, red_pct, green_pct, yellow_pct, purple_pct, blue_pct, dark_pct,
        )
        print(f"    [Camera Analysis: Red={red_pct:.1f}% | Green/Yellow={green_pct + yellow_pct:.1f}% | Purple={purple_pct:.1f}%]")

        # Non-produce veto: If strong blue/cyan presence dominates
        if blue_pct >= 20.0 and blue_pct > chromatic_pct:
            log.info("Non-produce blue/cyan pixels dominant (%.1f%%) -- rejecting object.", blue_pct)
            return None, 0

        # If practically no chromatic pixels exist (< 3.0%), chamber is truly empty or object has no color
        if chromatic_pct < 3.0:
            log.info("Insufficient chromatic pixels (%.1f%%) -- no recognizable produce found.", chromatic_pct)
            return None, 0

        # Calculate votes among chromatic pixels
        score_tomato   = tomato_red_count
        score_apple    = red_apple_count + apple_green_count + apple_yellow_count
        score_eggplant = eggplant_purple_count

        scores = {
            "Tomato": score_tomato,
            "Apple": score_apple,
            "Eggplant": score_eggplant,
        }
        winner = max(scores, key=scores.get)
        winner_score = scores[winner]

        if winner_score == 0:
            return None, 0

        # Confidence based on dominance of the winning category
        dominance_ratio = winner_score / max(1, total_chromatic)
        conf = int(min(96, max(60, dominance_ratio * 100.0)))

        # Specific tie-breaking / validation:
        if winner == "Tomato" and (yellow_pct + green_pct >= 6.0):
            # Apple undertones present
            mean_gr = sum(red_pixel_g_r_ratios) / len(red_pixel_g_r_ratios) if red_pixel_g_r_ratios else 0.0
            if mean_gr > 0.38:
                return "Apple", max(65, conf)

        return winner, conf

    except Exception as exc:
        log.warning("Produce detection image analysis failed: %s", exc)
        return None, 0


def detect_produce(camera: "CameraController", lights: "LightController"):
    """
    Take a single detection snapshot and auto-classify the produce on the turntable.

    MOSFET mode: White LED turns ON briefly (1.5s for camera AEC/AWB warmup), snap, OFF.
    Manual mode: Prompt operator to turn White LED ON, press Enter, snap.

    Returns (produce_name: str | None, confidence_pct: int)
    """
    if args.produce:
        return args.produce.strip().title(), 99

    if not PIL_AVAILABLE:
        log.warning("Pillow not installed -- produce auto-detection skipped.")
        return None, 0

    # -- Light management for detection snapshot ----------------------------
    if lights.mode == "auto" and lights._white_dev:
        if lights._uv_dev:
            lights._uv_dev.off()
        lights._white_dev.on()
        time.sleep(1.5)   # 1.5s warmup allows Pi Camera AEC & AWB to adapt from darkness
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
        print("    [Detection snapshot taken -- you may turn off the White LED now]")
    else:
        # Simulate mode -- capture test image
        img_bytes = camera.capture_jpeg()
        detected, conf = _classify_image_bytes(img_bytes)
        if detected is None:
            return "Tomato", 95
        return detected, conf

    return _classify_image_bytes(img_bytes)


# -----------------------------------------------------------------------------
# MAIN SCAN FUNCTION
# -----------------------------------------------------------------------------

def run_scan(motor:   "StepperMotor",
             lights:  "LightController",
             camera:  "CameraController",
             gas:     "GasSensor",
             display: "OLEDDisplay",
             uploader: "ScanUploader",
             door:    "PipeDoor") -> dict:
    """
    Execute one complete AgriScan 360 cycle:
      Step A -- Empty-box BME688 baseline calibration
      Step B -- Drop produce through pipe, auto-detect produce type
      Step C -- 8-stop 360-deg turntable scan (MOSFET: fully automatic / Manual: Enter-per-stop)
      Step D -- Gas analytics, upload, per-produce freshness result
    """
    rgb_images: list = []
    uv_images:  list = []

    display.show_ready()
    print("\n" + "=" * 62)
    print(f"  AgriScan 360  |  Chamber: {CHAMBER_VOLUME_LITERS}L Box  |  "
          f"LED: {'MOSFET Auto' if lights.mode == 'auto' else 'Manual'}")
    print(f"  Gas Sensor: {'Active' if gas.installed else 'Not Installed (Vision Only)'}")
    print("=" * 62)

    # -- Step A: Empty chamber -- BME688 clean-air baseline --------------------
    if gas.installed:
        print("\n[>] STEP A: Remove all produce from the box.")
        print("[>] Close the lid tightly, then press [Enter] to calibrate clean air...",
              end="", flush=True)
        try:
            input()
        except EOFError:
            pass

        display.show_bme_sniffing_empty()
        sniff_time = getattr(cfg, "GAS_EMPTY_BOX_SNIFF_SEC", 180)
        print(f"\n[>] BME688: Pre-heating hotplate thrice & sniffing empty box for {sniff_time}s ({sniff_time // 60} min)...")
        print("[>] (First 2 minutes are discarded for thermal stabilization; last 5s are averaged)")
        print("[>] Keep the box closed and EMPTY.")

        def _baseline_progress(elapsed, remaining, reading):
            cur_k = f"{reading.gas_kohms:6.2f} kOhm" if reading.gas_kohms > 0 else "measuring..."
            sys.stdout.write(f"\r    [Sniffing Empty Box] {elapsed:2d}s / {sniff_time}s | Gas: {cur_k} | {reading.temperature:.1f}C | {reading.humidity:.1f}%RH  ")
            sys.stdout.flush()

        try:
            gas.calibrate_baseline(duration_sec=sniff_time, progress_cb=_baseline_progress)
        except KeyboardInterrupt:
            print("\n[!] Empty box sniffing interrupted by user -- using current readings.")

        print(f"\n    -> Clean-air baseline (last 5s avg): {gas._baseline.gas_kohms:.2f} kOhm  "
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
        print("\n[>] BME688 not installed -- skipping gas baseline calibration.")

    # -- Step B: Drop produce through pipe, auto-detect -----------------------
    produce_name = None
    if args.produce:
        produce_name = args.produce.strip().title()
        print(f"\n[>] Produce forced via argument: {produce_name}")

    # Item entrance via pipe happens ONCE when entering Step B:
    if produce_name is None:
        print(f"\n[>] STEP B: Load item into the pipe above the turntable.")
        print("[>] Press [Enter] to OPEN the pipe door (90 deg) and drop item...")
        try:
            input()
        except EOFError:
            pass

        # --- Pipe door drop sequence ---
        display.show_item_detected("Dropping...")
        print("[>] Opening pipe door (180 deg)...")
        door.drop_item()   # Opens to 180 deg, holds 2s, closes to 90 deg
        print("[>] Pipe door closed (90 deg). Item is now on the turntable.")

        # --- Ask operator to close the box lid ---
        print("\n[>] Close the box lid tightly.")
        print("[>] Press [Enter] when box is sealed and ready for detection...", end="", flush=True)
        try:
            input()
        except EOFError:
            pass

    # Produce identification loop (item is ALREADY inside the box on turntable!):
    while produce_name is None:
        print("\n[>] Detecting produce on turntable with camera...")
        detected, confidence = detect_produce(camera, lights)

        if detected is None:
            # Could not identify any supported produce
            print("\n[!] CANNOT IDENTIFY PRODUCE.")
            print("[!] Supported items: Tomato, Apple, Eggplant")
            print("[!] Item is on the turntable. What would you like to do?")
            print("    1. Rescan item on turntable (retake detection photo)")
            print("    2. Rotate turntable 45 deg & rescan")
            print("    3. Select produce manually")
            try:
                choice = input("Select [1/2/3] (Default 1 = Rescan): ").strip()
            except EOFError:
                choice = "1"

            if choice == "2":
                print("[>] Rotating turntable 45 degrees to present a different angle...")
                motor.advance_45_degrees()
                continue
            elif choice == "3":
                print("\nSelect Produce:")
                print("  1. Tomato\n  2. Apple\n  3. Eggplant")
                sel = input("Enter number [1-3]: ").strip()
                mapping = {"1": "Tomato", "2": "Apple", "3": "Eggplant"}
                produce_name = mapping.get(sel, "Tomato")
                display.show_item_detected(produce_name)
                break
            else:
                # Option 1: Just rescan on the turntable!
                continue

        if confidence >= 70:
            # Auto-proceed -- high confidence
            print(f"\n[>] Detected: {detected}  ({confidence}% confidence) -- proceeding automatically.")
            produce_name = detected
            display.show_item_detected(detected)
        else:
            # Low confidence -- ask operator
            print(f"\n[?] Detected: {detected}  ({confidence}% confidence -- LOW)")
            try:
                ans = input("[?] Is this correct? [Y/n]: ").strip().lower()
            except EOFError:
                ans = "y"
            if ans in ("", "y", "yes"):
                produce_name = detected
                display.show_item_detected(detected)
            else:
                print("\n[!] Not confirmed. What would you like to do?")
                print("    1. Rescan item on turntable")
                print("    2. Rotate turntable 45 deg & rescan")
                print("    3. Select produce manually")
                try:
                    choice = input("Select [1/2/3] (Default 1 = Rescan): ").strip()
                except EOFError:
                    choice = "1"
                if choice == "2":
                    print("[>] Rotating turntable 45 degrees...")
                    motor.advance_45_degrees()
                elif choice == "3":
                    print("\nSelect Produce:")
                    print("  1. Tomato\n  2. Apple\n  3. Eggplant")
                    sel = input("Enter number [1-3]: ").strip()
                    mapping = {"1": "Tomato", "2": "Apple", "3": "Eggplant"}
                    produce_name = mapping.get(sel, "Tomato")
                    display.show_item_detected(produce_name)
                    break

    log.info("Produce confirmed: %s", produce_name)
    display.show_scanning(stop=0, total=NUM_SCAN_STOPS)

    # -- Step C: Start continuous BME sniffing (Incubation + 8-Stop Scan) ----
    gas.start_continuous_sniffing()

    # Pre-scan incubation with live progress feedback
    if cfg.GAS_PRE_SCAN_INCUBATION_SEC > 0:
        inc_total = cfg.GAS_PRE_SCAN_INCUBATION_SEC
        print(f"\n[>] Chamber Sealed: Incubating for {inc_total}s ({inc_total // 60} min) to accumulate VOCs...")
        print(f"[>] (First 2 minutes are discarded for thermal stabilization; interval: {cfg.GAS_SNIFF_INTERVAL_SEC}s).")
        t_inc_start = time.time()
        try:
            while True:
                elapsed = int(time.time() - t_inc_start)
                remaining = max(0, inc_total - elapsed)
                latest = gas._readings[-1] if gas._readings else None
                cur_k = f"{latest.gas_kohms:6.2f} kOhm ({int(latest.gas_ohms)} Ohm)" if latest else "measuring..."
                cur_t = f"{latest.temperature:.1f}C" if latest else "--"
                cur_h = f"{latest.humidity:.1f}%" if latest else "--"

                sys.stdout.write(f"\r    [Incubating] {elapsed:3d}s / {inc_total}s | Gas: {cur_k} | {cur_t} | {cur_h}  ")
                sys.stdout.flush()

                if elapsed % 2 == 0:
                    display.show_incubating(remaining)

                if remaining <= 0:
                    break
                time.sleep(1.0)
        except KeyboardInterrupt:
            print("\n[!] Incubation skipped by operator.")
        print("\n[>] Incubation complete. Starting 8-stop multi-spectral scan...")

    log.info("=== Starting scan for %s (Chamber %.1fL) ===", produce_name, CHAMBER_VOLUME_LITERS)
    motor.set_direction(clockwise=True)
    motor.enable()

    try:
        for stop in range(NUM_SCAN_STOPS):
            angle = stop * 45
            display.show_scanning(stop=stop, total=NUM_SCAN_STOPS)
            print(f"\n--- [Stop {stop + 1}/{NUM_SCAN_STOPS}  ({angle} deg)] ---")

            # A. White LED ON -> RGB snap -> White LED OFF
            with lights.capture_white(stop_index=stop, angle=angle):
                rgb_bytes = camera.capture_jpeg()
                rgb_images.append(rgb_bytes)
                log.info("  -> [RGB] Stop %d/8 (%d deg)", stop + 1, angle)

            time.sleep(0.1)   # brief settle between LEDs

            # B. UV-A LED ON -> UV snap -> UV-A LED OFF
            with lights.capture_uv(stop_index=stop, angle=angle):
                uv_bytes = camera.capture_jpeg()
                uv_images.append(uv_bytes)
                log.info("  -> [UV-A] Stop %d/8 (%d deg)", stop + 1, angle)

            # C. Rotate 45 deg (every stop -- including last stop returns to 0 deg home)
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

    # -- Step D: Stop BME sniffing -- per-produce gas analytics ----------------
    gas_result = gas.stop_continuous_sniffing(produce_name=produce_name)

    if gas.installed:
        _print_gas_table(gas_result, produce_name)
        # Save raw high-resolution timeseries CSV
        if getattr(cfg, "GAS_LOG_RAW_TIMESERIES", True):
            try:
                scan_tag = f"SCAN_{int(time.time())}"
                ts_path = gas.export_timeseries_csv(scan_id=scan_tag, produce_name=produce_name)
                print(f"[+] Raw time-series logged: {ts_path}")
            except Exception as exc:
                log.warning("Could not export raw timeseries: %s", exc)
    else:
        log.info("Gas sensing bypassed (BME688 not installed). Proceeding vision-only.")

    # -- Upload all 16 frames + gas result ------------------------------------
    display.show_uploading()
    result = uploader.upload_scan(
        rgb_images=rgb_images,
        uv_images=uv_images,
        gas_result=gas_result,
        produce_name=produce_name,
    )

    # -- Show final result -----------------------------------------------------
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

    # -- Step E: Ground-Truth Verification & Feedback Loop ---------------------
    # "You assume, I correct" -- Operator verifies or corrects the AI's judgment
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


# -----------------------------------------------------------------------------
# DISPLAY HELPERS
# -----------------------------------------------------------------------------

def _print_gas_table(gas_result: "ScanGasResult", produce_name: str):
    """Pretty-print the BME688 headspace gas analytics table with raw Ohm precision."""
    print("\n+--- BME688 Headspace Gas Analytics -------------------+")
    print(f"|  Produce             : {produce_name:<30} |")
    print(f"|  Baseline Resistance : {gas_result.baseline_kohms:6.3f} kOhm ({gas_result.raw_baseline_ohms:8.0f} Ohm)        |")
    print(f"|  Post-Scan Resistance: {gas_result.post_scan_kohms:6.3f} kOhm ({gas_result.raw_post_scan_ohms:8.0f} Ohm)        |")
    print(f"|  Min (Smoothed) / Max: {gas_result.gas_min_kohms:6.3f} / {gas_result.gas_max_kohms:6.3f} kOhm        |")
    print(f"|  Mean / Std Dev      : {gas_result.gas_mean_kohms:6.3f} +/- {gas_result.gas_std_kohms:5.3f} kOhm       |")
    print(f"|  Relative Drop Ratio : {gas_result.gas_ratio_pct:5.2f}%                         |")
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


# -----------------------------------------------------------------------------
# ENTRY POINT
# -----------------------------------------------------------------------------

def main():
    log.info("AgriScan 360 v2 -- Adaptive Master Orchestrator starting (simulate=%s)", SIM)

    led_mode = prompt_led_mode()

    # Initialise hardware modules with adaptive fallbacks
    motor    = StepperMotor(simulate=SIM)
    lights   = LightController(mode=led_mode, simulate=SIM)
    gas      = GasSensor(simulate=SIM)
    camera   = CameraController(simulate=SIM)
    display  = OLEDDisplay(simulate=SIM)
    door     = PipeDoor(simulate=SIM)
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
            result = run_scan(motor, lights, camera, gas, display, uploader, door)
            log.info("Scan session complete: %s", result)

            # Brief pause between scans -- gives operator time to see the result
            time.sleep(3)

            if args.no_loop:
                log.info("--no-loop flag set. Exiting after single scan.")
                break
            # No "scan another?" prompt -- automatically loops back to Step A

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
        door.cleanup()
        uploader.close()
        log.info("AgriScan 360 shutdown complete.")


if __name__ == "__main__":
    main()
