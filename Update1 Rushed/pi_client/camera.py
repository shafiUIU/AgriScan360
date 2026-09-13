"""
camera.py — Raspberry Pi Camera Module 2 Controller (Simplified)
=================================================================
UPDATE1 RUSHED CHANGES:
    - Removed UV/White paired capture. LEDs are manually controlled.
    - Each scan stop now captures ONE RGB image only.
    - Operator has White LEDs already ON before the scan starts.
    - capture_pair() is commented out and replaced with capture_single().
"""

import io
import logging
import time
from typing import Optional

log = logging.getLogger(__name__)

try:
    from picamera2 import Picamera2
    PICAMERA2_AVAILABLE = True
except ImportError:
    PICAMERA2_AVAILABLE = False
    log.warning("picamera2 not available. Using simulation mode.")

from config import CAPTURE_RESOLUTION, JPEG_QUALITY, CAPTURE_DELAY


class CameraController:
    """
    Manages the RPi Camera Module 2 via Picamera2.
    Update1 Rushed: captures a single RGB image per stop.
    LEDs are ON manually before the scan begins.
    """

    def __init__(self, simulate: bool = False):
        self._simulate = simulate or not PICAMERA2_AVAILABLE
        self._cam: Optional["Picamera2"] = None
        self._running = False

        if not self._simulate:
            self._init_camera()

    def _init_camera(self):
        try:
            self._cam = Picamera2()
            config = self._cam.create_still_configuration(
                main={"size": CAPTURE_RESOLUTION, "format": "RGB888"},
                buffer_count=2,
            )
            self._cam.configure(config)
            self._cam.start()
            self._running = True
            time.sleep(1.0)   # Allow AGC/AWB to stabilize
            log.info("Camera started: %s", CAPTURE_RESOLUTION)
        except Exception as exc:
            log.error("Camera init failed: %s — simulation mode", exc)
            self._simulate = True
            self._cam = None

    def _sim_image(self, label: str = "") -> bytes:
        """Generate a small JPEG test image for simulation."""
        try:
            from PIL import Image, ImageDraw
            import random
            w, h = 320, 240
            img  = Image.new("RGB", (w, h),
                             color=(random.randint(20, 80), random.randint(20, 60), random.randint(10, 40)))
            draw = ImageDraw.Draw(img)
            draw.text((10, 10), f"AgriScan360\n{label}", fill=(200, 200, 200))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=JPEG_QUALITY)
            return buf.getvalue()
        except ImportError:
            return b'\xff\xd8\xff\xd9'   # Minimal valid JPEG bytes

    def capture_jpeg(self) -> bytes:
        """Capture one JPEG image. LEDs should already be ON manually."""
        if self._simulate:
            time.sleep(0.1)
            return self._sim_image("SIM")

        try:
            time.sleep(CAPTURE_DELAY)   # Brief settle before capture
            buf = io.BytesIO()
            arr = self._cam.capture_array("main")
            from PIL import Image
            img = Image.fromarray(arr)
            img.save(buf, format="JPEG", quality=JPEG_QUALITY)
            return buf.getvalue()
        except Exception as exc:
            log.error("Capture failed: %s", exc)
            return self._sim_image("ERROR")

    def capture_single(self, stop_index: int) -> bytes:
        """
        Capture one RGB image at the current scan stop.
        LEDs are already ON manually — no switching needed.

        Args:
            stop_index: Current turntable stop (0–7) for logging.
        Returns:
            JPEG bytes of the captured image.
        """
        log.debug("Capturing RGB image at stop %d/8", stop_index + 1)
        return self.capture_jpeg()

    # ── REMOVED in Update1 Rushed ─────────────────────────────────────────────
    # def capture_pair(self, lights, stop_index):
    #     """Removed: LED pair capture (White + UV) no longer needed.
    #     LEDs are manually controlled. Only RGB capture remains."""
    #     pass

    def stop(self):
        if self._cam and self._running:
            try:
                self._cam.stop()
                self._cam.close()
            except Exception:
                pass
            self._running = False
            log.info("Camera stopped.")

    def cleanup(self):
        self.stop()
