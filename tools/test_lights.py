"""
test_lights.py -- Standalone Dual LED & MOSFET Hardware Test Tool
==================================================================
Use this tool on the Raspberry Pi 5 to test White and UV-A LEDs
via MOSFETs (GPIO 18 & GPIO 24) without running the full scan cycle.

Usage on Raspberry Pi:
    python tools/test_lights.py
"""

import sys
import os
import time

PI_CLIENT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pi_client")
sys.path.insert(0, PI_CLIENT_DIR)

try:
    from gpiozero import DigitalOutputDevice
    GPIO_OK = True
except ImportError:
    GPIO_OK = False
    print("[!] Warning: gpiozero not found. Running in simulation mode.")

import config as cfg


def main():
    print("============================================================")
    print("  AGRISCAN 360 -- DUAL LED & MOSFET HARDWARE TEST")
    print("============================================================")
    print("  White LED:  GPIO 18  ->  Physical Header Pin 12")
    print("  UV-A LED:   GPIO 24  ->  Physical Header Pin 18")
    print("  MOSFET:     IRLZ44N (Pin 1=Gate, Pin 2=Drain, Pin 3=Source)")
    print("============================================================\n")

    if not GPIO_OK:
        print("[!] Cannot test GPIO on PC without hardware.")
        print("[!] Run this script directly on your Raspberry Pi 5.")
        return

    white = DigitalOutputDevice(cfg.PIN_LED_WHITE, initial_value=False)
    uv    = DigitalOutputDevice(cfg.PIN_LED_UV,    initial_value=False)

    while True:
        print("\n+-- LED & MOSFET Test Menu ------------------------+")
        print("|  1. Toggle White LED ON / OFF (GPIO 18)          |")
        print("|  2. Toggle UV-A LED ON / OFF (GPIO 24)           |")
        print("|  3. Alternate Blink Test (White 2s <-> UV 2s)    |")
        print("|  4. Turn Both ON for 5 seconds                   |")
        print("|  5. Turn All OFF                                 |")
        print("|  0. Exit                                         |")
        print("+--------------------------------------------------+")

        try:
            choice = input("Select an option [0-5]: ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if choice == "1":
            if white.value:
                white.off()
                print("  -> White LED turned [OFF]")
            else:
                white.on()
                print("  -> White LED turned [ON]")
        elif choice == "2":
            if uv.value:
                uv.off()
                print("  -> UV-A LED turned [OFF]")
            else:
                uv.on()
                print("  -> UV-A LED turned [ON]")
        elif choice == "3":
            print("  Running 3-cycle alternate blink test...")
            for i in range(3):
                print(f"    Cycle {i+1}/3: White ON (2s)...")
                uv.off()
                white.on()
                time.sleep(2.0)
                print(f"    Cycle {i+1}/3: UV-A ON (2s)...")
                white.off()
                uv.on()
                time.sleep(2.0)
            uv.off()
            print("  Blink test complete. All lights OFF.")
        elif choice == "4":
            print("  Both White & UV-A LEDs ON for 5 seconds...")
            white.on()
            uv.on()
            time.sleep(5.0)
            white.off()
            uv.off()
            print("  Both turned OFF.")
        elif choice == "5":
            white.off()
            uv.off()
            print("  All LEDs turned [OFF].")
        elif choice in ("0", "q", "exit"):
            break
        else:
            print("Invalid option. Enter 0-5.")

    white.off()
    uv.off()
    print("\nLights turned off. Diagnostic complete.")


if __name__ == "__main__":
    main()
