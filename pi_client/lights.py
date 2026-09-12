"""
lights.py — Dual LED Array Controller via IRLZ44N MOSFETs
===========================================================
Hardware:
    MOSFET #1 (GPIO 18) → White Diffused LED Array  (visible light scan)
    MOSFET #2 (GPIO 24) → 365nm UV-A LED Array      (fungal fluorescence scan)

Wiring reminder:
    Gate  → Raspberry Pi GPIO (+ 10kΩ pull-down to GND)
    Drain → LED Array (-) terminal
    Source → Common GND
    LED (+) → 12V or 5V power rail
"""

import time
from gpiozero import DigitalOutputDevice
from config import PIN_LED_WHITE, PIN_LED_UV, WHITE_WARMUP_SEC, UV_WARMUP_SEC


class LightController:
    """
    Controls two LED arrays through IRLZ44N low-side MOSFET switches.
    Always call off_all() before switching between light types to avoid
    cross-contamination (UV glow affecting the white-light capture).
    """

    def __init__(self):
        self.white = DigitalOutputDevice(PIN_LED_WHITE, initial_value=False)
        self.uv    = DigitalOutputDevice(PIN_LED_UV,    initial_value=False)

    # ── Basic ON/OFF ───────────────────────────────────────────────────────────

    def white_on(self):
        """Turn on white diffused LED array."""
        self.uv.off()                         # Ensure UV is OFF first
        time.sleep(0.05)
        self.white.on()
        time.sleep(WHITE_WARMUP_SEC)           # Warm-up before capture

    def white_off(self):
        self.white.off()

    def uv_on(self):
        """Turn on 365nm UV-A LED array."""
        self.white.off()                       # Ensure White is OFF first
        time.sleep(0.05)
        self.uv.on()
        time.sleep(UV_WARMUP_SEC)             # UV-A needs slightly longer warm-up

    def uv_off(self):
        self.uv.off()

    def off_all(self):
        """Kill all lights. Always call between light-type switches."""
        self.white.off()
        self.uv.off()

    # ── Context managers for safe capture sequences ───────────────────────────

    def capture_white(self):
        """
        Context manager for white-light capture.
        Usage:
            with lights.capture_white():
                image = camera.capture()
        """
        return _LightContext(self, mode="white")

    def capture_uv(self):
        """
        Context manager for UV capture.
        Usage:
            with lights.capture_uv():
                image = camera.capture()
        """
        return _LightContext(self, mode="uv")

    def cleanup(self):
        """Release GPIO resources."""
        self.off_all()
        self.white.close()
        self.uv.close()


class _LightContext:
    """Internal context manager — turns light on before enter, off on exit."""

    def __init__(self, controller: LightController, mode: str):
        self._ctrl = controller
        self._mode = mode

    def __enter__(self):
        if self._mode == "white":
            self._ctrl.white_on()
        else:
            self._ctrl.uv_on()
        return self

    def __exit__(self, *_):
        self._ctrl.off_all()
