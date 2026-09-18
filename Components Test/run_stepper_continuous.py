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
# SPEED & ROTATION CONFIGURATION
# ==============================================================================
# 200 steps/rev at full-step (1.8° per step): 25 steps = exactly 45°
STEPS_PER_45_DEG = 25       # Steps per 45° rotation (Full-step mode)
STEP_PULSE_DELAY = 0.004    # Seconds between steps during movement (smooth, no slip)
PAUSE_SEC        = 3.0      # Pause duration at each 45° stop (seconds)
DIRECTION        = 1        # 1 = Clockwise, 0 = Counter-Clockwise


def step_45_degrees(step_pin, steps=STEPS_PER_45_DEG, delay=STEP_PULSE_DELAY):
    """Executes exactly 45 degrees rotation (25 steps)."""
    for _ in range(steps):
        step_pin.on()
        time.sleep(delay)
        step_pin.off()
        time.sleep(delay)


def main():
    print("==================================================")
    print("  AgriScan 360 - 45° Stepper Turntable Test")
    print("  Motor: 4S42Q-P0404S  |  Driver: A4988")
    print("==================================================")
    print(f"  Rotation : 45° ({STEPS_PER_45_DEG} steps)")
    print(f"  Interval : Every {PAUSE_SEC} seconds")
    print(f"  Direction: {'Clockwise' if DIRECTION == 1 else 'Counter-Clockwise'}")
    print("  Status   : Press [Ctrl + C] anytime to STOP safely.")
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
        print("[>] Energizing motor coils...")
        enable_pin.off()
        time.sleep(0.1)

        total_stops = 0
        current_angle = 0

        print(f"\n>>> STARTING 45° ROTATION EVERY {PAUSE_SEC} SECONDS <<<")
        print("Press Ctrl+C to stop.\n")

        while True:
            total_stops += 1
            current_angle = (current_angle + 45) % 360
            stop_in_revolution = ((total_stops - 1) % 8) + 1

            print(f"[{time.strftime('%H:%M:%S')}] Rotating 45° -> Stop #{stop_in_revolution}/8 (Total: {current_angle}°)...", end="", flush=True)
            step_45_degrees(step_pin)
            print(" Done! Settling.")

            print(f"    Waiting {PAUSE_SEC}s before next move...")
            time.sleep(PAUSE_SEC)

    except KeyboardInterrupt:
        print("\n\n[HALT] Ctrl+C pressed by user! Stopping motor...")

    except Exception as e:
        print(f"\n[ERROR] An error occurred: {e}")

    finally:
        # Disable motor coils so the motor stays cool
        enable_pin.on()
        print("[SAFE] Motor coils de-energized. Safe to power off.")


if __name__ == "__main__":
    main()
