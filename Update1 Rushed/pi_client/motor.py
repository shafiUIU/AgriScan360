"""
motor.py — NEMA 17 Stepper Motor Controller via A4988 Driver
=============================================================
Hardware:  NEMA 17 (4S42Q-P0404S), 1.8°/step, 200 steps/rev
Driver:    A4988  (STEP=GPIO17, DIR=GPIO27, ENABLE=GPIO22)
Logic:     Open-loop step-counting. No Hall sensor needed.
           25 steps × 8 stops = 200 steps = exactly 1 full 360° revolution.
"""

import time
import logging

log = logging.getLogger(__name__)

try:
    from gpiozero import DigitalOutputDevice
    GPIOZERO_AVAILABLE = True
except ImportError:
    GPIOZERO_AVAILABLE = False
    log.warning("gpiozero not available. Motor running in simulation mode.")

from config import (
    PIN_STEP, PIN_DIR, PIN_ENABLE,
    STEPS_PER_STOP, NUM_SCAN_STOPS,
    PULSE_DELAY, RAMP_STEPS, RAMP_START_DELAY, SETTLE_DELAY
)


class StepperMotor:
    """
    Controls the NEMA 17 motor via A4988 for the 8-stop turntable scan.

    Enable pin is ACTIVE LOW:
        enable_pin.off()  →  motor coils energized  (motor holds/moves)
        enable_pin.on()   →  motor coils released   (motor free, stays cool)
    """

    def __init__(self, simulate: bool = False):
        self._simulate = simulate or not GPIOZERO_AVAILABLE
        if not self._simulate:
            self.step_pin   = DigitalOutputDevice(PIN_STEP,   initial_value=False)
            self.dir_pin    = DigitalOutputDevice(PIN_DIR,    initial_value=False)
            self.enable_pin = DigitalOutputDevice(PIN_ENABLE, initial_value=True)   # starts OFF
        self._stop_requested = False

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _pulse(self, delay: float = PULSE_DELAY):
        """Send one STEP pulse."""
        if self._simulate:
            time.sleep(0.001)
            return
        self.step_pin.on()
        time.sleep(delay / 2)
        self.step_pin.off()
        time.sleep(delay / 2)

    def _ramp_steps(self, count: int, start_delay: float, end_delay: float):
        """Pulse `count` steps while ramping delay from start_delay → end_delay."""
        for i in range(count):
            frac = i / max(count - 1, 1)
            delay = start_delay + (end_delay - start_delay) * frac
            self._pulse(delay)

    # ── Public API ─────────────────────────────────────────────────────────────

    def enable(self):
        """Energize motor coils (motor can move)."""
        if not self._simulate:
            self.enable_pin.off()   # Active LOW
        time.sleep(0.05)        # Brief settle

    def disable(self):
        """
        De-energize motor coils (motor free, no heat, holds last position passively).
        Always call after scan is complete.
        """
        if not self._simulate:
            self.step_pin.off()     # Ensure STEP pin is low — prevents ghost steps
            self.enable_pin.on()    # Release coils

    def set_direction(self, clockwise: bool = True):
        """Set rotation direction. True = clockwise (looking down at turntable)."""
        if not self._simulate:
            self.dir_pin.value = clockwise

    def move_steps(self, steps: int, smooth: bool = True):
        """
        Move exactly `steps` steps with optional soft ramp up/down.
        For 45°: steps=25. For full 360°: steps=200.
        """
        self.enable()
        if smooth and steps > RAMP_STEPS * 2:
            ramp = min(RAMP_STEPS, steps // 3)
            self._ramp_steps(ramp, RAMP_START_DELAY, PULSE_DELAY)       # ramp UP
            for _ in range(steps - ramp * 2):                            # cruise
                self._pulse(PULSE_DELAY)
            self._ramp_steps(ramp, PULSE_DELAY, RAMP_START_DELAY)        # ramp DOWN
        else:
            for _ in range(steps):
                self._pulse(PULSE_DELAY)

    def advance_45_degrees(self):
        """
        Move turntable exactly 45° (one scan stop).
        Includes settle delay so the turntable is stable before image capture.
        """
        self.move_steps(STEPS_PER_STOP, smooth=True)
        time.sleep(SETTLE_DELAY)

    def full_scan_positions(self):
        """
        Generator: yields stop index (0–7) after moving to each 45° position.
        Use in a for loop — motor advances automatically between yields.
        Example:
            for stop in motor.full_scan_positions():
                capture_images(stop)
        """
        self.set_direction(clockwise=True)
        self.enable()
        try:
            for stop in range(NUM_SCAN_STOPS):
                if stop > 0:
                    self.advance_45_degrees()
                else:
                    time.sleep(SETTLE_DELAY)   # Settle at starting position
                yield stop
        finally:
            self.disable()

    def home(self):
        """
        Complete any remaining rotation to return to the true 0° start.
        Only needed if a scan was aborted mid-cycle.
        """
        pass   # Open-loop: restart = just begin next scan from current position

    def cleanup(self):
        """Release all GPIO resources cleanly."""
        self.disable()
        if not self._simulate:
            self.step_pin.close()
            self.dir_pin.close()
            self.enable_pin.close()
