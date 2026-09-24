"""
servo.py -- SG90 Micro Servo Pipe Feeder Door Controller
=========================================================
Hardware:  SG90 Micro Servo (180 Degree Rotation)
Wiring:
    Brown / Black Wire  -> GND (Physical Pin 14 or 20)
    Red Wire            -> 5V  (Physical Pin 2 or 4)
    Orange / Yellow     -> GPIO 23 (Physical Pin 16)

Door Logic:
    CLOSED = 90 deg   (pipe sealed, nothing drops through)
    OPEN   = 180 deg  (pipe open, produce slides onto turntable)
    Duration = 2.0 seconds (time held open for item to drop)
"""

import logging
import time
from typing import Optional

log = logging.getLogger(__name__)

try:
    from gpiozero import AngularServo
    GPIOZERO_AVAILABLE = True
except ImportError:
    GPIOZERO_AVAILABLE = False
    log.warning("gpiozero not available. PipeDoor running in simulation mode.")

from config import PIN_SERVO

# Configured door angles (degrees)
_CLOSED_ANGLE   = 90
_OPEN_ANGLE     = 180
_OPEN_DURATION  = 2.0   # seconds to hold door open

# Standard SG90 pulse widths
_MIN_PULSE = 0.0005   # 500 us
_MAX_PULSE = 0.0024   # 2400 us


class PipeDoor:
    """
    Controls the SG90 servo that acts as the pipe feeder door.

    Usage:
        door = PipeDoor(simulate=False)
        door.drop_item()   # opens to 180 deg for 2s, then closes to 90 deg
        door.close()       # explicit close
        door.cleanup()     # release PWM
    """

    def __init__(self, simulate: bool = False):
        self._simulate = simulate or not GPIOZERO_AVAILABLE
        self._servo: Optional[object] = None

        if not self._simulate:
            self._init_servo()

    def _init_servo(self):
        try:
            self._servo = AngularServo(
                PIN_SERVO,
                min_angle=0,
                max_angle=180,
                min_pulse_width=_MIN_PULSE,
                max_pulse_width=_MAX_PULSE,
            )
            # Park to closed position immediately on init
            self._servo.angle = _CLOSED_ANGLE
            time.sleep(0.5)
            self._servo.value = None   # Detach to stop buzzing
            log.info("PipeDoor servo initialized on GPIO %d (closed at %d deg)", PIN_SERVO, _CLOSED_ANGLE)
        except Exception as exc:
            log.error("PipeDoor servo init failed: %s -- simulation mode", exc)
            self._simulate = True

    def _move(self, angle: int, hold: float = 0.8):
        """Move servo to angle, hold for hold seconds, then detach PWM."""
        if self._simulate:
            log.info("[Simulated] PipeDoor -> %d deg (hold %.1fs)", angle, hold)
            time.sleep(min(hold, 0.2))   # brief delay in sim mode
            return
        if self._servo is None:
            return
        try:
            self._servo.angle = angle
            time.sleep(hold)
            self._servo.value = None   # Detach: prevents jitter and current drain at rest
        except Exception as exc:
            log.error("PipeDoor move error: %s", exc)

    def open(self):
        """Open the pipe door to 180 deg."""
        log.info("PipeDoor: OPENING to %d deg", _OPEN_ANGLE)
        self._move(_OPEN_ANGLE, hold=0.3)   # Just move, don't block

    def close(self):
        """Close the pipe door to 90 deg."""
        log.info("PipeDoor: CLOSING to %d deg", _CLOSED_ANGLE)
        self._move(_CLOSED_ANGLE, hold=0.6)

    def drop_item(self):
        """
        Full drop sequence:
          1. Open door to 180 deg
          2. Hold open for 2.0 seconds (item slides through pipe onto turntable)
          3. Close door to 90 deg

        Blocks for approximately OPEN_DURATION + settle time (~2.8s total).
        """
        log.info("PipeDoor: Starting DROP sequence (open %ds, close)", _OPEN_DURATION)
        self._move(_OPEN_ANGLE, hold=_OPEN_DURATION)   # Open and hold 2s
        self._move(_CLOSED_ANGLE, hold=0.6)             # Close and settle
        log.info("PipeDoor: DROP sequence complete -- door CLOSED")

    def cleanup(self):
        """Close door and release servo resources."""
        self.close()
        if not self._simulate and self._servo is not None:
            try:
                self._servo.close()
            except Exception:
                pass
