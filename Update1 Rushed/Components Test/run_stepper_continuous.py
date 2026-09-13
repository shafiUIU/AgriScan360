#!/usr/bin/env python3
"""
AgriScan 360 - Continuous Stepper Rotation
Components:
  - Raspberry Pi 5
  - A4988 Stepper Driver
  - Stepper Motor: 4S42Q-P0404S (NEMA 17, 1.8 deg/step)

Wiring Summary:
  A4988 STEP    --> Raspberry Pi GPIO 17 (Physical Pin 11)
  A4988 DIR     --> Raspberry Pi GPIO 27 (Physical Pin 13)
  A4988 ENABLE  --> Raspberry Pi GPIO 22 (Physical Pin 15)
  A4988 VDD     --> Raspberry Pi 3.3V    (Physical Pin 1)
  A4988 GND     --> Raspberry Pi GND     (Physical Pin 6 or 9)
  A4988 RST+SLP --> Bridge together with a jumper wire!
  A4988 VMOT    --> External 12V Supply (+)
  A4988 GND     --> External 12V Supply (-) AND connect to Pi GND!

Motor Socket (Left to Right: 1 to 6) to A4988:
  Pin 1 (Leftmost) --> A4988 1A
  Pin 3            --> A4988 1B
  Pin 4            --> A4988 2A
  Pin 6 (Rightmost)--> A4988 2B
  (Pins 2 & 5 are skipped / empty)
"""

import time
from gpiozero import DigitalOutputDevice

# ==============================================================================
# PIN CONFIGURATION
# ==============================================================================
PIN_STEP   = 17   # GPIO 17 -> A4988 STEP
PIN_DIR    = 27   # GPIO 27 -> A4988 DIR
PIN_ENABLE = 22   # GPIO 22 -> A4988 ENABLE (Active LOW)

# ==============================================================================
# SPEED & DIRECTION
# ==============================================================================
# TARGET_DELAY: Time in seconds between step pulses
# 0.0020 = Slow & very smooth (Best for first test)
# 0.0015 = Medium turntable speed
# 0.0008 = Fast rotation
TARGET_DELAY = 0.0015

# Direction: 1 = Clockwise, 0 = Counter-Clockwise
DIRECTION = 1


def main():
    print("==================================================")
    print("  AgriScan 360 - Continuous Stepper Test")
    print("  Motor: 4S42Q-P0404S  |  Driver: A4988")
    print("==================================================")
    print(f"  Target Delay : {TARGET_DELAY}s")
    print(f"  Direction    : {'Clockwise' if DIRECTION == 1 else 'Counter-Clockwise'}")
    print("  Status       : Press [Ctrl + C] anytime to STOP safely.")
    print("==================================================\n")

    # Initialize pins with native Raspberry Pi 5 gpiozero library
    step_pin = DigitalOutputDevice(PIN_STEP)
    dir_pin = DigitalOutputDevice(PIN_DIR)
    
    # Active LOW: initial_value=True holds ENABLE high (motor OFF initially)
    enable_pin = DigitalOutputDevice(PIN_ENABLE, initial_value=True)

    try:
        # 1. Set Direction
        dir_pin.value = DIRECTION
        time.sleep(0.01)

        # 2. Energize motor coils (pull ENABLE pin to LOW / 0V)
        print("[1/2] Energizing motor coils...")
        enable_pin.off()
        time.sleep(0.1)

        # 3. Soft Ramp-up (prevents motor stalling/buzzing on start)
        print("[2/2] Ramping up speed smoothly...")
        current_delay = 0.006  # Start gentle
        while current_delay > TARGET_DELAY:
            step_pin.on()
            time.sleep(current_delay)
            step_pin.off()
            time.sleep(current_delay)
            current_delay *= 0.96  # Accelerate smoothly

        print("\n>>> MOTOR RUNNING CONTINUOUSLY <<<")
        print("Press Ctrl+C to stop.\n")

        # 4. Continuous steady-speed loop
        step_count = 0
        while True:
            step_pin.on()
            time.sleep(TARGET_DELAY)
            step_pin.off()
            time.sleep(TARGET_DELAY)
            
            step_count += 1
            if step_count % 1000 == 0:
                print(f"  -> Spinning steadily... ({step_count} steps)", end="\r")

    except KeyboardInterrupt:
        print("\n\n[HALT] Ctrl+C pressed by user! Stopping motor...")

    except Exception as e:
        print(f"\n[ERROR] An error occurred: {e}")

    finally:
        # 5. Disable motor coils so the 0.4A motor stays completely cool!
        enable_pin.on()
        print("[SAFE] Motor coils de-energized. Safe to power off.")


if __name__ == "__main__":
    main()
