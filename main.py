#!/usr/bin/env python3
"""
AgriScan 360 - Master System Orchestrator (main.py)
Course: Microprocessors & Microcontrollers Laboratory (CSE 4326) - UIU

Controls:
  - NEMA 17 Stepper Motor via A4988 (8-stop 360-degree rotation)
  - Dual Illumination (White LED & 365nm UV LED via IRLZ44N MOSFETs)
  - Raspberry Pi Camera Module 2 (Multi-spectral photo captures)
  - Bosch BME688 AI Gas Sensor (VOC scent analysis for internal rot)
  - SSD1306 OLED (On-device physical display)
  - Flask IoT Server (Wireless live web dashboard on port 5000)
"""

import time
import sys
from config import TOTAL_STOPS, EXPOSURE_PAUSE_SEC, GAS_WARMUP_CYCLES
from motor import MotorController
from lights import LightingController
from gas_sensor import GasSensorController
from camera import CameraController
from display import DisplayController
from ai_classifier import QualityClassifier
import web_server


class AgriScanStation:
    def __init__(self):
        print("\n=======================================================")
        print("   AGRISCAN 360 - INITIALIZING SYSTEM SUBSYSTEMS")
        print("=======================================================")

        # 1. Start background IoT Web Dashboard (Port 5000)
        web_server.start_server_background()

        # 2. Initialize Hardware Modules
        self.motor   = MotorController()
        self.lights  = LightingController()
        self.gas     = GasSensorController()
        self.camera  = CameraController()
        self.display = DisplayController()
        self.ai      = QualityClassifier()

        self.display.show_message("AgriScan 360", "SYSTEM READY", "Press ENTER to scan")
        print("[System] All subsystems online and ready.")

    def run_inspection_cycle(self, produce_name="Eggplant"):
        """Executes a full 360-degree multi-modal quality scan."""
        print(f"\n=======================================================")
        print(f"   STARTING INSPECTION CYCLE: {produce_name.upper()}")
        print("=======================================================")

        self.display.show_message(produce_name.upper(), "SCANNING...", "Calibrating gas")
        captured_images = []

        try:
            # ----------------------------------------------------
            # STEP 1: Chamber Baseline Gas Calibration
            # ----------------------------------------------------
            self.gas.calibrate_baseline(duration_sec=GAS_WARMUP_CYCLES)

            # ----------------------------------------------------
            # STEP 2: 360-Degree 8-Stop Multi-Spectral Capture
            # ----------------------------------------------------
            self.motor.enable()

            for stop_idx in range(TOTAL_STOPS):
                angle_deg = stop_idx * 45
                print(f"\n[Stop {stop_idx + 1}/{TOTAL_STOPS}] Angle: {angle_deg}°")

                # A. Visible RGB Capture under White Light
                self.lights.white_on()
                time.sleep(EXPOSURE_PAUSE_SEC)
                rgb_path = self.camera.capture_frame(filename_prefix=produce_name, angle_idx=stop_idx, light_type="white")
                captured_images.append(rgb_path)
                self.lights.all_off()

                # B. UV Fluorescence Capture under 365nm UV Light
                self.lights.uv_on()
                time.sleep(EXPOSURE_PAUSE_SEC)
                uv_path = self.camera.capture_frame(filename_prefix=produce_name, angle_idx=stop_idx, light_type="uv")
                captured_images.append(uv_path)
                self.lights.all_off()

                # C. Advance Turntable +45 degrees to next angle
                if stop_idx < (TOTAL_STOPS - 1):
                    print("  -> Advancing turntable +45°...")
                    self.motor.advance_one_stop()
                    time.sleep(0.3)

            # Final step to return back to exact 0° start position
            print("  -> Turntable returning to 0° reference position...")
            self.motor.advance_one_stop()

            # ----------------------------------------------------
            # STEP 3: Gas Scent Measurement (Internal Rot Detection)
            # ----------------------------------------------------
            print("\n[Gas] Sampling accumulated chamber VOC headspace gases...")
            final_metrics = self.gas.read_metrics()
            current_gas_kohm = final_metrics["gas_kohm"]
            gas_delta = self.gas.compute_gas_delta(current_gas_kohm)
            print(f"[Gas] Final Reading: {current_gas_kohm:.2f} kΩ | ΔGas Drop: {gas_delta:.2f} kΩ")

            # ----------------------------------------------------
            # STEP 4: Multi-Modal AI Decision Fusion
            # ----------------------------------------------------
            result = self.ai.evaluate(captured_images, gas_delta, produce_name=produce_name)
            result["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")

            # ----------------------------------------------------
            # STEP 5: Dual Output (OLED Screen + Wireless Web Dashboard)
            # ----------------------------------------------------
            # Update OLED
            self.display.show_result(
                produce_name=result["produce"],
                classification=result["status"],
                confidence=result["confidence"],
                gas_delta=result["gas_delta_kohm"]
            )

            # Update Web Dashboard
            web_server.update_web_result(result)

            print("\n=======================================================")
            print(f"   SCAN COMPLETE: {result['status']} ({result['confidence']}%)")
            print(f"   Web Dashboard updated at: http://localhost:{web_server.WEB_PORT}")
            print("=======================================================\n")

        except KeyboardInterrupt:
            print("\n[ABORTED] Scan interrupted by user.")

        finally:
            # Safe shutdown: always de-energize coils and turn off lights
            self.motor.disable()
            self.lights.all_off()

    def shutdown(self):
        print("\nShutting down AgriScan 360 safely...")
        self.motor.disable()
        self.lights.all_off()
        self.camera.close()
        self.display.show_message("AgriScan 360", "SYSTEM STANDBY", "Power Safe")


def main():
    station = AgriScanStation()

    try:
        while True:
            prompt = input("\nEnter produce name to scan (e.g. 'Eggplant', 'Mango', 'Apple') or 'q' to quit: ").strip()
            if prompt.lower() in ['q', 'quit', 'exit']:
                break
            
            item_name = prompt if prompt else "Eggplant"
            station.run_inspection_cycle(produce_name=item_name)

    except KeyboardInterrupt:
        pass
    finally:
        station.shutdown()
        print("Goodbye!")


if __name__ == "__main__":
    main()
