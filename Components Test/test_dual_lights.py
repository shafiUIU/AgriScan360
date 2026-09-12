#!/usr/bin/env python3
"""
AgriScan 360 - Dual Light Alternating Test (White LED & UV LED)
Hardware:
  - Raspberry Pi 5
  - 2x IRLZ44N N-Channel MOSFETs
  - White LED Chunk
  - UV LED Chunk
  - External Power Supply (5V or 12V DC)

Behavior:
  - White LED: ON for 5 seconds -> OFF
  - UV LED   : ON for 5 seconds -> OFF
  - Repeats infinitely until you press Ctrl+C.
"""

import time
from gpiozero import DigitalOutputDevice

# ==============================================================================
# GPIO PIN ASSIGNMENTS (BCM Numbers)
# ==============================================================================
# GPIO 18 (Physical Pin 12) -> Gate of MOSFET #1 (White LED)
PIN_WHITE_LED = 18

# GPIO 24 (Physical Pin 18) -> Gate of MOSFET #2 (UV LED)
PIN_UV_LED = 24

# Time each light stays ON (in seconds)
HOLD_SECONDS = 5.0


def main():
    print("==================================================")
    print("  AgriScan 360 - Dual Light Test (IRLZ44N)")
    print("  White LED Pin : GPIO 18 (Physical Pin 12)")
    print("  UV LED Pin    : GPIO 24 (Physical Pin 18)")
    print(f"  Cycle Duration: {HOLD_SECONDS} seconds each")
    print("  Press [Ctrl + C] anytime to stop.")
    print("==================================================\n")

    # Initialize GPIO output devices (initial_value=False keeps them OFF on start)
    white_light = DigitalOutputDevice(PIN_WHITE_LED, initial_value=False)
    uv_light    = DigitalOutputDevice(PIN_UV_LED,    initial_value=False)

    cycle = 1

    try:
        while True:
            print(f"--- [Cycle {cycle}] ---")

            # ----------------------------------------------------
            # 1. WHITE LED ON (UV OFF)
            # ----------------------------------------------------
            uv_light.off()
            white_light.on()
            print(f"  [1/2] 💡 WHITE LED is ON  (holding for {HOLD_SECONDS}s)...")
            time.sleep(HOLD_SECONDS)

            # Turn White OFF
            white_light.off()
            print("        WHITE LED is OFF.")
            time.sleep(0.5)  # Brief pause between switches

            # ----------------------------------------------------
            # 2. UV LED ON (WHITE OFF)
            # ----------------------------------------------------
            uv_light.on()
            print(f"  [2/2] 🟣 UV LED is ON     (holding for {HOLD_SECONDS}s)...")
            time.sleep(HOLD_SECONDS)

            # Turn UV OFF
            uv_light.off()
            print("        UV LED is OFF.\n")
            time.sleep(0.5)

            cycle += 1

    except KeyboardInterrupt:
        print("\n[STOPPED] Ctrl+C pressed by user.")

    finally:
        # Emergency shutoff: Ensure both lights are completely OFF on exit
        white_light.off()
        uv_light.off()
        print("[SAFE] Both lights turned OFF completely. Done.")


if __name__ == "__main__":
    main()
