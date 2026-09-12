"""
AgriScan 360 - Stepper Motor Controller Module
Controls NEMA 17 Stepper Motor via A4988 Driver using open-loop step-counting.
"""

import time
from gpiozero import DigitalOutputDevice
from config import PIN_STEP, PIN_DIR, PIN_ENABLE, STEPS_PER_STOP, PULSE_DELAY


class MotorController:
    def __init__(self):
        self.step_pin   = DigitalOutputDevice(PIN_STEP, initial_value=False)
        self.dir_pin    = DigitalOutputDevice(PIN_DIR, initial_value=False)
        self.enable_pin = DigitalOutputDevice(PIN_ENABLE, initial_value=True) # Motor OFF initially
        print("[Motor] MotorController initialized successfully.")

    def enable(self):
        """Energize motor coils (pull ENABLE low)."""
        self.enable_pin.off()
        time.sleep(0.05)

    def disable(self):
        """De-energize motor coils to keep motor cool while idle."""
        self.step_pin.off()
        self.enable_pin.on()

    def step(self, steps, clockwise=True, delay=PULSE_DELAY):
        """Send exact step pulses."""
        self.dir_pin.value = 1 if clockwise else 0
        for _ in range(steps):
            self.step_pin.on()
            time.sleep(delay)
            self.step_pin.off()
            time.sleep(delay)

    def advance_one_stop(self):
        """Advance turntable by exactly 45 degrees (25 steps)."""
        self.enable()
        self.step(STEPS_PER_STOP, clockwise=True)
        time.sleep(0.1)


# Quick standalone test
if __name__ == "__main__":
    motor = MotorController()
    try:
        print("Testing 1 advance (45 deg)...")
        motor.advance_one_stop()
        print("Done.")
    finally:
        motor.disable()
