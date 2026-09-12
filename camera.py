"""
AgriScan 360 - Camera Controller Module
Manages Raspberry Pi Camera Module 2 via Picamera2 or OpenCV.
Captures high-resolution frames synchronized with White & UV illumination.
"""

import os
import time
from config import CAPTURE_DIR

# Try importing Picamera2
try:
    from picamera2 import Picamera2
    PICAM2_AVAILABLE = True
except ImportError:
    PICAM2_AVAILABLE = False


class CameraController:
    def __init__(self):
        self.picam2 = None
        self.is_ready = False

        if PICAM2_AVAILABLE:
            try:
                self.picam2 = Picamera2()
                config = self.picam2.create_still_configuration(main={"size": (1920, 1080)})
                self.picam2.configure(config)
                self.picam2.start()
                self.is_ready = True
                print("[Camera] Picamera2 started successfully.")
            except Exception as e:
                print(f"[Camera] Picamera2 init warning: {e}. Running in software fallback mode.")
                self.is_ready = False
        else:
            print("[Camera] Picamera2 not found. Running in software fallback mode.")

    def capture_frame(self, filename_prefix="scan", angle_idx=0, light_type="white"):
        """Captures a photo and saves to the captures directory."""
        filename = f"{filename_prefix}_angle{angle_idx}_{light_type}_{int(time.time())}.jpg"
        filepath = os.path.join(CAPTURE_DIR, filename)

        if self.is_ready and self.picam2:
            try:
                self.picam2.capture_file(filepath)
                print(f"[Camera] Saved: {filename}")
                return filepath
            except Exception as e:
                print(f"[Camera] Capture error: {e}")

        # Fallback: create a dummy placeholder file if camera is not physically attached yet
        with open(filepath, "wb") as f:
            f.write(b"") # Placeholder
        print(f"[Camera] [Simulated] Saved placeholder: {filename}")
        return filepath

    def close(self):
        if self.is_ready and self.picam2:
            self.picam2.stop()
            self.picam2.close()
