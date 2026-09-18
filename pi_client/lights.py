"""
lights.py — Dual LED Array Controller (Adaptive: MOSFET Hardware or Manual Operator)
=====================================================================================
Hardware Mode (MOSFETs connected):
    MOSFET #1 (GPIO 18) → White Diffused LED Array  (visible light scan)
    MOSFET #2 (GPIO 24) → 365nm UV-A LED Array      (fungal fluorescence scan)

Manual Mode (No MOSFETs connected):
    Lights are toggled by hand using an external switch.
    The system interactively prompts the operator at each stop:
        1. Turn ON White LED -> [Enter] -> capture snap -> Turn OFF White LED
        2. Turn ON UV-A LED  -> [Enter] -> capture snap -> Turn OFF UV-A LED
"""

import time
import logging

log = logging.getLogger(__name__)

try:
    from gpiozero import DigitalOutputDevice
    GPIOZERO_AVAILABLE = True
except ImportError:
    GPIOZERO_AVAILABLE = False

from config import PIN_LED_WHITE, PIN_LED_UV, WHITE_WARMUP_SEC, UV_WARMUP_SEC


class LightController:
    """
    Controls White and UV-A illumination.
    Automatically supports both MOSFET GPIO switching and Manual human switching.
    """

    def __init__(self, mode: str = "auto", simulate: bool = False):
        """
        Args:
            mode: "auto" (attempt MOSFET GPIO control), "manual" (human toggles switches),
                  or "simulate" (no-op for PC testing).
            simulate: Flag forcing simulated mode.
        """
        self.simulate = simulate
        self.mode = mode.lower()
        self._white_dev = None
        self._uv_dev = None
        self._manual_active_light = None  # Tracks state in manual mode

        if self.mode == "auto" and not self.simulate and GPIOZERO_AVAILABLE:
            try:
                self._white_dev = DigitalOutputDevice(PIN_LED_WHITE, initial_value=False)
                self._uv_dev    = DigitalOutputDevice(PIN_LED_UV,    initial_value=False)
                log.info("LightController: MOSFET mode active on GPIO %d (White) & GPIO %d (UV)",
                         PIN_LED_WHITE, PIN_LED_UV)
            except Exception as exc:
                log.warning("Could not initialize MOSFET GPIOs (%s). Falling back to MANUAL mode.", exc)
                self.mode = "manual"
        elif self.mode != "manual":
            self.mode = "manual" if not self.simulate else "simulate"

        if self.mode == "manual":
            log.info("LightController: MANUAL mode active (operator switches lights by hand)")
        elif self.mode == "simulate":
            log.info("LightController: SIMULATION mode active")

    @property
    def is_manual(self) -> bool:
        return self.mode == "manual"

    # ── White Light Control ───────────────────────────────────────────────────

    def white_on(self, stop_index: int = 0, angle: int = 0):
        """Turn on white diffused LED array."""
        if self.mode == "auto" and self._white_dev:
            if self._uv_dev:
                self._uv_dev.off()
            time.sleep(0.05)
            self._white_dev.on()
            time.sleep(WHITE_WARMUP_SEC)
        elif self.mode == "manual":
            print(f"\n[>] [Stop {stop_index + 1}/8 ({angle}°)] Turn ON White LED switch.")
            print(f"    Press [Enter] when ready to capture RGB...", end="", flush=True)
            try:
                input()
            except EOFError:
                pass
            self._manual_active_light = "white"
        else:
            time.sleep(0.05)

    def white_off(self):
        """Turn off white diffused LED array."""
        if self.mode == "auto" and self._white_dev:
            self._white_dev.off()
        elif self.mode == "manual":
            if self._manual_active_light == "white":
                print("    [White LED -> OFF]")
                self._manual_active_light = None

    # ── UV-A Light Control ────────────────────────────────────────────────────

    def uv_on(self, stop_index: int = 0, angle: int = 0):
        """Turn on 365nm UV-A LED array."""
        if self.mode == "auto" and self._uv_dev:
            if self._white_dev:
                self._white_dev.off()
            time.sleep(0.05)
            self._uv_dev.on()
            time.sleep(UV_WARMUP_SEC)
        elif self.mode == "manual":
            print(f"\n[>] [Stop {stop_index + 1}/8 ({angle}°)] Turn OFF White LED, Turn ON 365nm UV-A LED switch.")
            print(f"    Press [Enter] when ready to capture UV...", end="", flush=True)
            try:
                input()
            except EOFError:
                pass
            self._manual_active_light = "uv"
        else:
            time.sleep(0.05)

    def uv_off(self):
        """Turn off 365nm UV-A LED array."""
        if self.mode == "auto" and self._uv_dev:
            self._uv_dev.off()
        elif self.mode == "manual":
            if self._manual_active_light == "uv":
                print("    [UV-A LED -> OFF]")
                self._manual_active_light = None

    def off_all(self):
        """Turn off all lights."""
        if self.mode == "auto":
            if self._white_dev:
                self._white_dev.off()
            if self._uv_dev:
                self._uv_dev.off()
        elif self.mode == "manual":
            self._manual_active_light = None

    # ── Context Managers ──────────────────────────────────────────────────────

    def capture_white(self, stop_index: int = 0, angle: int = 0):
        return _LightContext(self, mode="white", stop_index=stop_index, angle=angle)

    def capture_uv(self, stop_index: int = 0, angle: int = 0):
        return _LightContext(self, mode="uv", stop_index=stop_index, angle=angle)

    def cleanup(self):
        """Release GPIO resources cleanly."""
        self.off_all()
        if self._white_dev:
            try:
                self._white_dev.close()
            except Exception:
                pass
        if self._uv_dev:
            try:
                self._uv_dev.close()
            except Exception:
                pass


class _LightContext:
    def __init__(self, controller: LightController, mode: str, stop_index: int = 0, angle: int = 0):
        self._ctrl = controller
        self._mode = mode
        self._stop = stop_index
        self._angle = angle

    def __enter__(self):
        if self._mode == "white":
            self._ctrl.white_on(stop_index=self._stop, angle=self._angle)
        else:
            self._ctrl.uv_on(stop_index=self._stop, angle=self._angle)
        return self

    def __exit__(self, *_):
        if self._mode == "white":
            self._ctrl.white_off()
        else:
            self._ctrl.uv_off()
