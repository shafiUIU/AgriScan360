"""
display.py -- SSD1306 1.3" OLED Display Driver (I2C, 128x64 Blue)
==================================================================
Hardware:  1.3 Inch I2C SSD1306 OLED, 128x64 pixels, Blue color
I2C Pins:  SDA -> GPIO 2 (Physical Pin 3)
           SCL -> GPIO 3 (Physical Pin 5)
           VCC -> 3.3V  (Physical Pin 1)
           GND -> GND   (Physical Pin 6)
I2C Addr:  0x3C (default) -- if not found, try 0x3D

Library:   pip install luma.oled pillow

Screen States (in scan order):
  1. show_splash()                          -- AgriScan startup
  2. show_bme_sniffing_empty()             -- "BME sniffing empty box..."
  3. show_item_detected(produce_name)      -- "APPLE DETECTED!" in big text
  4. show_incubating(seconds_remaining)    -- "Incubating... Xs left"
  5. show_scanning(stop, total)            -- "SCANNING..." fills whole display
  6. show_uploading()                      -- "Sending to server..."
  7. show_result(status, confidence)       -- "HEALTHY" / "ROTTEN" fills whole display
  8. show_server_offline()                 -- Server unreachable
  9. show_error(message)                   -- Generic error
 10. show_ready()                          -- Idle / waiting for fruit
"""

import logging
import time
from typing import Optional

log = logging.getLogger(__name__)

try:
    from luma.core.interface.serial import i2c
    from luma.oled.device import ssd1306
    from luma.core.render import canvas
    from PIL import ImageFont, ImageDraw
    LUMA_AVAILABLE = True
except ImportError:
    LUMA_AVAILABLE = False
    log.warning("luma.oled not found. OLED display running in console simulation mode.")

from config import SSD1306_ADDRESS, OLED_WIDTH, OLED_HEIGHT


# =============================================================================
# Font Loader
# =============================================================================

# Font paths (DejaVu is pre-installed on Raspberry Pi OS Bookworm)
_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]

def _font(size: int) -> "ImageFont":
    """Load a bold TrueType font at given pixel size. Falls back to default."""
    for path in _FONT_PATHS:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _center_x(draw, text, font, width=128) -> int:
    """Return x position to center text horizontally."""
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
    except AttributeError:
        # Older Pillow fallback
        text_width = font.getsize(text)[0]
    return max(0, (width - text_width) // 2)


def _center_y(text_height, height=64) -> int:
    """Return y position to center text vertically."""
    return max(0, (height - text_height) // 2)


# =============================================================================
# OLEDDisplay Class
# =============================================================================

class OLEDDisplay:
    """
    SSD1306 1.3" OLED controller with full AgriScan 360 scan workflow screens.
    Falls back to ASCII console simulation on PC (no hardware required).

    Usage:
        disp = OLEDDisplay()
        disp.show_splash()
        disp.show_bme_sniffing_empty()
        disp.show_item_detected("Apple")
        disp.show_scanning(stop=0, total=8)
        disp.show_result("HEALTHY", confidence=96.4)
    """

    def __init__(self, simulate: bool = False, i2c_port: int = 1):
        self._simulate = simulate or not LUMA_AVAILABLE
        self._device: Optional[object] = None
        self._i2c_port = i2c_port

        if not self._simulate:
            self._init_device()

    def _init_device(self):
        """Initialize the SSD1306 over I2C."""
        try:
            serial = i2c(port=self._i2c_port, address=SSD1306_ADDRESS)
            self._device = ssd1306(serial, width=OLED_WIDTH, height=OLED_HEIGHT)
            log.info(
                "SSD1306 1.3-inch OLED initialized at I2C address 0x%02X (port %d)",
                SSD1306_ADDRESS, self._i2c_port,
            )
        except Exception as exc:
            log.error("OLED init failed (%s) -- switching to console simulation.", exc)
            self._simulate = True

    def _draw(self, callback):
        """Execute a luma canvas draw callback. Swallows draw errors gracefully."""
        if self._simulate:
            return
        try:
            with canvas(self._device) as draw:
                callback(draw)
        except Exception as exc:
            log.error("OLED draw error: %s", exc)

    def _sim(self, *lines):
        """Render screen content to terminal when no OLED hardware is present."""
        border = "+" + "-" * 34 + "+"
        print("\n" + border)
        for line in lines:
            print("|  {:<32}  |".format(str(line)[:32]))
        print(border)

    # =========================================================================
    # 1. STARTUP SPLASH
    # =========================================================================

    def show_splash(self):
        """AgriScan 360 power-on startup screen."""
        def draw_fn(draw):
            draw.text((_center_x(draw, "AgriScan 360", _font(16)), 2),
                      "AgriScan 360", font=_font(16), fill="white")
            draw.line([(0, 22), (128, 22)], fill="white", width=1)
            draw.text((_center_x(draw, "UIU CSE 4326", _font(10)), 26),
                      "UIU CSE 4326", font=_font(10), fill="white")
            draw.text((_center_x(draw, "Initializing...", _font(10)), 40),
                      "Initializing...", font=_font(10), fill="white")
            draw.text((_center_x(draw, "Stage 1 - Chamber", _font(9)), 53),
                      "Stage 1 - Chamber", font=_font(9), fill="white")

        if self._simulate:
            self._sim("AgriScan 360", "UIU CSE 4326", "Initializing...")
        else:
            self._draw(draw_fn)
        time.sleep(1.5)

    # =========================================================================
    # 2. BME688 SNIFFING EMPTY BOX (Baseline Phase)
    # =========================================================================

    def show_bme_sniffing_empty(self):
        """
        Displayed while the BME688 takes clean-air baseline readings.
        The box must be empty during this phase.
        """
        def draw_fn(draw):
            draw.text((_center_x(draw, "BME688", _font(18)), 2),
                      "BME688", font=_font(18), fill="white")
            draw.line([(0, 24), (128, 24)], fill="white", width=1)
            draw.text((_center_x(draw, "Sniffing empty", _font(10)), 28),
                      "Sniffing empty", font=_font(10), fill="white")
            draw.text((_center_x(draw, "box baseline...", _font(10)), 42),
                      "box baseline...", font=_font(10), fill="white")
            draw.text((_center_x(draw, "Keep box EMPTY", _font(9)), 54),
                      "Keep box EMPTY", font=_font(9), fill="white")

        if self._simulate:
            self._sim("BME688", "Sniffing empty", "box baseline...", "Keep box EMPTY")
        else:
            self._draw(draw_fn)

    # =========================================================================
    # 3. ITEM DETECTED -- fills most of screen with produce name
    # =========================================================================

    def show_item_detected(self, produce_name: str):
        """
        Displayed after the Pi camera detects the produce type.
        The produce name is shown in large text centered on screen.

        Args:
            produce_name: "Apple", "Tomato", "Eggplant", or "Unknown"
        """
        name_upper = produce_name.upper()
        tag_line   = "DETECTED!"

        def draw_fn(draw):
            # Big produce name centered
            f_big = _font(20)
            f_tag = _font(13)
            x_name = _center_x(draw, name_upper, f_big)
            x_tag  = _center_x(draw, tag_line, f_tag)
            draw.text((x_name, 4),  name_upper, font=f_big, fill="white")
            draw.text((x_tag,  30), tag_line,   font=f_tag, fill="white")
            draw.line([(0, 48), (128, 48)], fill="white", width=1)
            draw.text((_center_x(draw, "Place in chamber", _font(9)), 52),
                      "Place in chamber", font=_font(9), fill="white")

        if self._simulate:
            self._sim(f">>> {name_upper} <<<", "DETECTED!", "Place in chamber")
        else:
            self._draw(draw_fn)

    # =========================================================================
    # 4. INCUBATION COUNTDOWN (Gas accumulation phase)
    # =========================================================================

    def show_incubating(self, seconds_remaining: int):
        """
        Displayed during the 5-minute pre-scan gas incubation period.
        Call repeatedly to update the countdown.

        Args:
            seconds_remaining: Seconds left in the incubation period.
        """
        mins = seconds_remaining // 60
        secs = seconds_remaining % 60
        time_str = f"{mins}m {secs:02d}s"

        def draw_fn(draw):
            draw.text((_center_x(draw, "INCUBATING", _font(14)), 2),
                      "INCUBATING", font=_font(14), fill="white")
            draw.line([(0, 20), (128, 20)], fill="white", width=1)
            draw.text((_center_x(draw, "VOC accumulating", _font(9)), 24),
                      "VOC accumulating", font=_font(9), fill="white")
            # Big countdown timer
            draw.text((_center_x(draw, time_str, _font(20)), 32),
                      time_str, font=_font(20), fill="white")
            draw.text((_center_x(draw, "remaining", _font(9)), 56),
                      "remaining", font=_font(9), fill="white")

        if self._simulate:
            self._sim("INCUBATING", f"VOC accumulating", f"  {time_str} left")
        else:
            self._draw(draw_fn)

    # =========================================================================
    # 5. SCANNING -- fills whole display, big bold text
    # =========================================================================

    def show_scanning(self, stop: int = 0, total: int = 8):
        """
        Displayed at each 45-degree turntable stop during the scan.
        'SCANNING...' fills the top half in large text.
        A progress bar fills the bottom.

        Args:
            stop:  Current stop index (0-based, 0..7).
            total: Total number of stops (default 8).
        """
        stop_num  = stop + 1
        stop_str  = f"Stop  {stop_num} / {total}"

        def draw_fn(draw):
            # BIG "SCANNING..." -- top half
            f_big = _font(22)
            draw.text((_center_x(draw, "SCANNING", f_big), 0),
                      "SCANNING", font=f_big, fill="white")
            draw.text((_center_x(draw, "...", f_big), 24),
                      "...", font=f_big, fill="white")
            # Stop indicator
            draw.text((_center_x(draw, stop_str, _font(10)), 48),
                      stop_str, font=_font(10), fill="white")
            # Progress bar (full width)
            filled = int(stop_num / total * 126)
            draw.rectangle([(0, 58), (127, 63)], outline="white")
            draw.rectangle([(0, 58), (filled, 63)], fill="white")

        if self._simulate:
            bar = ("#" * stop_num) + ("-" * (total - stop_num))
            self._sim("SCANNING...", stop_str, f"[{bar}]")
        else:
            self._draw(draw_fn)

    # =========================================================================
    # 6. UPLOADING TO SERVER
    # =========================================================================

    def show_uploading(self):
        """Displayed while images + gas telemetry are sent to the laptop server."""
        def draw_fn(draw):
            draw.text((_center_x(draw, "Sending...", _font(16)), 4),
                      "Sending...", font=_font(16), fill="white")
            draw.line([(0, 26), (128, 26)], fill="white", width=1)
            draw.text((_center_x(draw, "Images + Gas", _font(10)), 30),
                      "Images + Gas", font=_font(10), fill="white")
            draw.text((_center_x(draw, "to laptop server", _font(10)), 44),
                      "to laptop server", font=_font(10), fill="white")

        if self._simulate:
            self._sim("Sending...", "Images + Gas", "to laptop server")
        else:
            self._draw(draw_fn)

    # =========================================================================
    # 7. FINAL RESULT -- fills whole display in BIG LETTERS
    # =========================================================================

    def show_result(self, status: str, confidence: float = 0.0,
                    gas_delta: float = 0.0):
        """
        Displays the final freshness classification in BIG text occupying
        the whole display.

        Status values:
            "FRESH"       -> Shows "HEALTHY" in large centered text
            "MID_FRESH"   -> Shows "FAIRLY" + "FRESH" stacked
            "MID_ROTTEN"  -> Shows "EARLY" + "ROT" stacked
            "ROTTEN"      -> Shows "ROTTEN" in large centered text
            "HEALTHY"     -> Same as FRESH
            "UNCERTAIN"   -> Shows "UNCERTAIN"

        Args:
            status:     Freshness tier string from AI engine.
            confidence: 0.0-100.0 confidence percentage.
            gas_delta:  kOhm gas resistance drop (for info line).
        """
        # Map internal status codes to display-friendly labels
        _STATUS_MAP = {
            "FRESH":      ("HEALTHY",   "  FRESH!"),
            "MID_FRESH":  ("FAIRLY",    "  FRESH"),
            "HEALTHY":    ("HEALTHY",   "  FRESH!"),
            "MID_ROTTEN": ("EARLY",     "   ROT"),
            "ROTTEN":     ("ROTTEN",    "  BAD!"),
            "SEVERE_ROT": ("ROTTEN",    "  BAD!"),
            "UNCERTAIN":  ("UNCERTAIN", ""),
            "UNKNOWN":    ("UNCERTAIN", ""),
        }
        line1, line2 = _STATUS_MAP.get(status.upper(), (status.upper(), ""))
        conf_str = f"Conf: {confidence:.0f}%"

        def draw_fn(draw):
            f_huge = _font(26)
            f_big  = _font(22)
            f_sub  = _font(9)

            if line2:
                # Two stacked words
                draw.text((_center_x(draw, line1, f_big), 0),
                          line1, font=f_big, fill="white")
                draw.text((_center_x(draw, line2, f_huge), 20),
                          line2, font=f_huge, fill="white")
            else:
                # One large word, vertically centered in top 50px
                draw.text((_center_x(draw, line1, f_huge), 8),
                          line1, font=f_huge, fill="white")

            # Thin separator
            draw.line([(0, 50), (128, 50)], fill="white", width=1)
            # Small confidence + gas line at bottom
            draw.text((2, 53), conf_str, font=f_sub, fill="white")
            if gas_delta != 0.0:
                gas_str = f"Gas:{gas_delta:+.1f}k"
                draw.text((128 - 60, 53), gas_str, font=f_sub, fill="white")

        if self._simulate:
            marker = ">>" if "ROT" in status.upper() else "**"
            self._sim(
                f"{marker} {line1} {line2} {marker}",
                conf_str,
                f"Gas delta: {gas_delta:+.1f} kohm",
            )
        else:
            self._draw(draw_fn)

    # =========================================================================
    # 8. SERVER OFFLINE
    # =========================================================================

    def show_server_offline(self):
        """Displayed when the laptop AI server cannot be reached."""
        def draw_fn(draw):
            f_big = _font(22)
            draw.text((_center_x(draw, "SERVER", f_big), 2),
                      "SERVER", font=f_big, fill="white")
            draw.text((_center_x(draw, "OFFLINE", f_big), 26),
                      "OFFLINE", font=f_big, fill="white")
            draw.line([(0, 52), (128, 52)], fill="white", width=1)
            draw.text((_center_x(draw, "Check Wi-Fi/laptop", _font(9)), 54),
                      "Check Wi-Fi/laptop", font=_font(9), fill="white")

        if self._simulate:
            self._sim("!! SERVER !!", "!! OFFLINE !!", "Check Wi-Fi/laptop")
        else:
            self._draw(draw_fn)

    # =========================================================================
    # 9. GENERIC ERROR
    # =========================================================================

    def show_error(self, message: str):
        """Generic error screen. Truncates to fit."""
        short = message[:18]

        def draw_fn(draw):
            draw.text((_center_x(draw, "ERROR", _font(22)), 2),
                      "ERROR", font=_font(22), fill="white")
            draw.line([(0, 30), (128, 30)], fill="white", width=1)
            draw.text((_center_x(draw, short, _font(10)), 35),
                      short, font=_font(10), fill="white")

        if self._simulate:
            self._sim("!! ERROR !!", short)
        else:
            self._draw(draw_fn)

    # =========================================================================
    # 10. READY (Idle waiting screen)
    # =========================================================================

    def show_ready(self):
        """Idle screen - waiting for produce to be placed."""
        def draw_fn(draw):
            f_big = _font(22)
            f_sub = _font(10)
            draw.text((_center_x(draw, "READY", f_big), 4),
                      "READY", font=f_big, fill="white")
            draw.line([(0, 32), (128, 32)], fill="white", width=1)
            draw.text((_center_x(draw, "Place produce", f_sub), 36),
                      "Place produce", font=f_sub, fill="white")
            draw.text((_center_x(draw, "& close box", f_sub), 50),
                      "& close box", font=f_sub, fill="white")

        if self._simulate:
            self._sim("READY", "Place produce", "& close box")
        else:
            self._draw(draw_fn)

    # =========================================================================
    # Utility
    # =========================================================================

    def clear(self):
        """Clear OLED to all-black."""
        if not self._simulate and self._device:
            try:
                self._device.clear()
            except Exception:
                pass

    def cleanup(self):
        """Clear screen and release hardware resources."""
        self.clear()
