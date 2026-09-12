"""
camera.py — Raspberry Pi Camera Module 2 Controller (Picamera2)
================================================================
Hardware:  RPi Camera Module 2 (Sony IMX219, 8MP, CSI-2 ribbon)
Library:   picamera2  (pre-installed on RPi OS Bookworm)

Capture strategy per scan stop:
    1. White light ON  → capture RGB image  → White light OFF
    2. UV light ON     → capture UV image   → UV light OFF
    3. Store both as JPEG bytes in memory

Images are kept as raw JPEG bytes (not saved to disk on Pi).
The uploader.py module sends them directly to the laptop server.
"""

import io
import logging
import time
from typing import Optional, Tuple

log = logging.getLogger(__name__)

try:
    from picamera2 import Picamera2
    PICAMERA2_AVAILABLE = True
except ImportError:
    PICAMERA2_AVAILABLE = False
    log.warning("picamera2 not available. Using simulation mode (white noise images).")

from config import CAPTURE_RESOLUTION, JPEG_QUALITY


class CameraController:
    """
    Manages the RPi Camera Module 2 via Picamera2.
    Falls back to generating dummy test images when running on a PC (no camera).
    """

    def __init__(self, simulate: bool = False):
        self._simulate = simulate or not PICAMERA2_AVAILABLE
        self._cam: Optional["Picamera2"] = None
        self._running = False

        if not self._simulate:
            self._init_camera()

    def _init_camera(self):
        """Configure and start the camera."""
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
            log.info("Camera started: %s @ %s", CAPTURE_RESOLUTION, "RGB888")
        except Exception as exc:
            log.error("Camera init failed: %s — switching to simulation mode", exc)
            self._simulate = True
            self._cam = None

    def _sim_image(self, label: str = "") -> bytes:
        """Generate a small JPEG test image with PIL for simulation."""
        try:
            from PIL import Image, ImageDraw, ImageFont
            import random
            w, h = 320, 240
            img = Image.new("RGB", (w, h),
                            color=(random.randint(0, 40), random.randint(0, 40), random.randint(0, 40)))
            draw = ImageDraw.Draw(img)
            draw.text((10, 10), f"AgriScan360\n{label}", fill=(200, 200, 200))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=JPEG_QUALITY)
            return buf.getvalue()
        except ImportError:
            # Absolute fallback: 1×1 valid JPEG
            return (
                b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
                b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t'
                b'\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a'
                b'\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\x1e'
                b'1=- @=A9@ 2<.342\x1e1=- @=A9@ 2<'
                b'\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4'
                b'\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00'
                b'\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b'
                b'\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xfb\xff\xd9'
            )

    def capture_jpeg(self) -> bytes:
        """
        Capture a single JPEG image.
        Assumes the correct light is already ON before calling.
        Returns raw JPEG bytes.
        """
        if self._simulate:
            time.sleep(0.1)   # Simulate capture latency
            return self._sim_image()

        try:
            buf = io.BytesIO()
            arr = self._cam.capture_array("main")
            from PIL import Image
            img = Image.fromarray(arr)
            img.save(buf, format="JPEG", quality=JPEG_QUALITY)
            return buf.getvalue()
        except Exception as exc:
            log.error("Capture failed: %s", exc)
            return self._sim_image("CAPTURE ERROR")

    def capture_pair(self, lights, stop_index: int) -> Tuple[bytes, bytes]:
        """
        Capture one White-light image and one UV image at the current scan stop.
        Uses the lights module context managers to ensure safe light switching.

        Args:
            lights:      LightController instance
            stop_index:  Current turntable stop (0–7), used only for logging

        Returns:
            (rgb_jpeg_bytes, uv_jpeg_bytes)
        """
        log.debug("Capturing pair at stop %d/8", stop_index + 1)

        with lights.capture_white():
            rgb_bytes = self.capture_jpeg()

        # Brief pause to ensure UV-A LEDs are fully off before UV capture
        time.sleep(0.1)

        with lights.capture_uv():
            uv_bytes = self.capture_jpeg()

        return rgb_bytes, uv_bytes

    def stop(self):
        """Stop and release the camera."""
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
