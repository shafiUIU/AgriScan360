"""
display.py — SSD1306 OLED 0.96" Display Driver (I2C)
=====================================================
Hardware:  SSD1306 0.96" OLED, 128×64 pixels
I2C:       SDA→GPIO2 (Pin3), SCL→GPIO3 (Pin5), address 0x3C
Library:   pip install luma.oled

Displays:
    - Startup splash
    - "SCANNING... Stop X/8"
    - Classification result (HEALTHY / ROTTEN / UNCERTAIN)
    - Gas delta reading
    - "SERVER OFFLINE" fallback
"""

import logging
import time
from typing import Optional

log = logging.getLogger(__name__)

try:
    from luma.core.interface.serial import i2c
    from luma.oled.device import ssd1306
    from luma.core.render import canvas
    from PIL import ImageFont
    LUMA_AVAILABLE = True
except ImportError:
    LUMA_AVAILABLE = False
    log.warning("luma.oled not found. OLED display in simulation mode (prints to console).")

from config import SSD1306_ADDRESS, OLED_WIDTH, OLED_HEIGHT


# Attempt to load a slightly larger font; fall back to default if unavailable
def _load_font(size: int):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except Exception:
        return ImageFont.load_default()


class OLEDDisplay:
    """
    SSD1306 OLED interface with structured display methods.
    Falls back to console print in simulation mode (PC / no hardware).
    """

    def __init__(self, simulate: bool = False):
        self._simulate = simulate or not LUMA_AVAILABLE
        self._device: Optional[object] = None

        if not self._simulate:
            self._init_device()

    def _init_device(self):
        try:
            serial = i2c(port=1, address=SSD1306_ADDRESS)
            self._device = ssd1306(serial, width=OLED_WIDTH, height=OLED_HEIGHT)
            log.info("SSD1306 OLED initialized at 0x%02X", SSD1306_ADDRESS)
        except Exception as exc:
            log.error("OLED init failed: %s — simulation mode", exc)
            self._simulate = True

    def _draw(self, callback):
        """Run a luma canvas draw callback."""
        if self._simulate:
            return
        try:
            with canvas(self._device) as draw:
                callback(draw)
        except Exception as exc:
            log.error("OLED draw error: %s", exc)

    def _sim_print(self, *lines):
        """Print OLED content to console in simulation mode."""
        print("\n+--- OLED DISPLAY ---------------+")
        for line in lines:
            safe_line = str(line).encode("ascii", errors="replace").decode("ascii")
            print(f"|  {safe_line:<30} |")
        print("+--------------------------------+")

    # ── Display methods ────────────────────────────────────────────────────────

    def show_splash(self):
        """AgriScan 360 startup screen."""
        def draw_fn(draw):
            f_title = _load_font(14)
            f_sub   = _load_font(10)
            draw.text((8,  4), "AgriScan 360",    font=f_title, fill="white")
            draw.text((12, 22), "UIU  CSE 4326",   font=f_sub,   fill="white")
            draw.text((8,  36), "Initializing...", font=f_sub,   fill="white")
            draw.text((4,  50), "Stage 1 — Chamber Scan", font=_load_font(8), fill="white")

        if self._simulate:
            self._sim_print("AgriScan 360", "UIU  CSE 4326", "Initializing...")
        else:
            self._draw(draw_fn)
        time.sleep(1.5)

    def show_ready(self):
        """Waiting-for-fruit idle screen."""
        def draw_fn(draw):
            f = _load_font(11)
            draw.text((20, 10), "READY", font=_load_font(18), fill="white")
            draw.text((4,  38), "Place fruit &",  font=f, fill="white")
            draw.text((4,  52), "press SCAN btn", font=f, fill="white")

        if self._simulate:
            self._sim_print("READY", "Place fruit &", "press SCAN btn")
        else:
            self._draw(draw_fn)

    def show_scanning(self, stop: int, total: int = 8):
        """Scanning progress update — call once per motor stop."""
        msg = f"Stop {stop + 1}/{total}"

        def draw_fn(draw):
            draw.text((4,  2),  "SCANNING...",  font=_load_font(14), fill="white")
            draw.text((4, 22),  msg,            font=_load_font(12), fill="white")
            # Simple progress bar
            bar_width = int((stop + 1) / total * 118)
            draw.rectangle([(4, 44), (122, 56)], outline="white")
            draw.rectangle([(4, 44), (4 + bar_width, 56)], fill="white")

        if self._simulate:
            bar = "█" * (stop + 1) + "░" * (total - stop - 1)
            self._sim_print("SCANNING...", msg, bar)
        else:
            self._draw(draw_fn)

    def show_uploading(self):
        """Displayed while images are being uploaded to the laptop server."""
        def draw_fn(draw):
            draw.text((4,  8), "Uploading...",   font=_load_font(13), fill="white")
            draw.text((4, 28), "Sending to",     font=_load_font(11), fill="white")
            draw.text((4, 44), "laptop server",  font=_load_font(11), fill="white")

        if self._simulate:
            self._sim_print("Uploading...", "Sending to laptop server")
        else:
            self._draw(draw_fn)

    def show_result(self, status: str, confidence: float, gas_delta: float):
        """
        Display final classification result.
        Status: "HEALTHY" | "ROTTEN" | "UNCERTAIN"
        """
        conf_str   = f"Conf: {confidence:.0f}%"
        gas_str    = f"Gas: {gas_delta:+.1f} kohm"

        def draw_fn(draw):
            status_font = _load_font(16)
            sub_font    = _load_font(10)
            draw.text((4,  2),  status,   font=status_font, fill="white")
            draw.text((4, 24),  conf_str, font=sub_font,    fill="white")
            draw.text((4, 38),  gas_str,  font=sub_font,    fill="white")
            draw.text((4, 52),  "AgriScan 360", font=_load_font(8), fill="white")

        if self._simulate:
            self._sim_print(f">> {status} <<", conf_str, gas_str)
        else:
            self._draw(draw_fn)

    def show_server_offline(self):
        """Displayed when the laptop server cannot be reached."""
        def draw_fn(draw):
            draw.text((4,  4),  "SERVER",   font=_load_font(18), fill="white")
            draw.text((4, 26),  "OFFLINE",  font=_load_font(18), fill="white")
            draw.text((4, 50),  "Check Wi-Fi / laptop", font=_load_font(8), fill="white")

        if self._simulate:
            self._sim_print("!! SERVER OFFLINE !!", "Check Wi-Fi / laptop")
        else:
            self._draw(draw_fn)

    def show_error(self, message: str):
        """Generic error screen."""
        short = message[:20]   # Truncate to fit

        def draw_fn(draw):
            draw.text((4,  4),  "ERROR",  font=_load_font(16), fill="white")
            draw.text((4, 28),  short,   font=_load_font(10),  fill="white")

        if self._simulate:
            self._sim_print("ERROR", short)
        else:
            self._draw(draw_fn)

    def clear(self):
        """Clear OLED screen."""
        if not self._simulate and self._device:
            try:
                self._device.clear()
            except Exception:
                pass

    def cleanup(self):
        self.clear()
