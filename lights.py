"""
AgriScan 360 - Dual Lighting Controller Module
Controls White LED and 365nm UV LED via IRLZ44N MOSFET low-side switches.
"""

import time
from gpiozero import DigitalOutputDevice
from config import PIN_WHITE_LED, PIN_UV_LED


class LightingController:
    def __init__(self):
        self.white_led = DigitalOutputDevice(PIN_WHITE_LED, initial_value=False)
        self.uv_led    = DigitalOutputDevice(PIN_UV_LED,    initial_value=False)
        self.all_off()
        print("[Lighting] LightingController initialized successfully.")

    def white_on(self):
        """Turn on White surface lighting only."""
        self.uv_led.off()
        self.white_led.on()

    def uv_on(self):
        """Turn on 365nm UV fluorescence lighting only."""
        self.white_led.off()
        self.uv_led.on()

    def all_off(self):
        """Turn off all illumination sources."""
        self.white_led.off()
        self.uv_led.off()


# Quick standalone test
if __name__ == "__main__":
    lights = LightingController()
    try:
        print("Testing White light (2s)...")
        lights.white_on()
        time.sleep(2)
        print("Testing UV light (2s)...")
        lights.uv_on()
        time.sleep(2)
    finally:
        lights.all_off()
        print("All lights OFF.")
