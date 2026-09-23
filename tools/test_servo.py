"""
test_servo.py -- SG90 Micro Servo Pipe Feed Door Test Tool
===========================================================
Hardware: SG90 Micro Servo (180 Degree Rotation)
Wiring:
    Brown / Black Wire  -> GND (Physical Pin 14 or 20)
    Red Wire            -> 5V (Physical Pin 2 or 4)
    Orange / Yellow Wire-> GPIO 23 (Physical Pin 16)

Logic:
    0 Degree   = Door CLOSED
    180 Degree = Door OPEN (Item drops through pipe onto turntable)
"""

import sys
import time
import os

try:
    from gpiozero import AngularServo
    GPIOZERO_OK = True
except ImportError:
    GPIOZERO_OK = False
    print("[!] Warning: gpiozero not found. Running in simulation mode.")

SERVO_PIN = 23

# Standard SG90 pulse timings (500us to 2400us at 50Hz)
MIN_PULSE_WIDTH = 0.0005
MAX_PULSE_WIDTH = 0.0024


def get_servo():
    if not GPIOZERO_OK:
        return None
    # Configure AngularServo for 0 to 180 degrees
    return AngularServo(
        SERVO_PIN,
        min_angle=0,
        max_angle=180,
        min_pulse_width=MIN_PULSE_WIDTH,
        max_pulse_width=MAX_PULSE_WIDTH,
    )


def move_and_relax(servo, angle, hold_time=0.8):
    """
    Moves servo to angle and relaxes (detaches) after hold_time.
    Detaching prevents the SG90 from jittering or buzzing when resting.
    """
    if servo is None:
        print(f"[Simulated] Servo moved to {angle} deg")
        return

    servo.angle = angle
    time.sleep(hold_time)
    # Set value to None to detach PWM and stop motor hum/strain
    servo.value = None


def test_feed_drop(servo, open_time=2.0):
    """Simulates a real item drop: opens door, waits for item to fall, closes door."""
    print(f"\n--- Testing Feed Drop Sequence ---")
    print("1. Opening door to 180 deg...")
    move_and_relax(servo, 180, hold_time=open_time)
    print("   -> Item should have dropped onto scanning table.")
    print("2. Closing door to 0 deg...")
    move_and_relax(servo, 0, hold_time=0.8)
    print("   -> Door is now CLOSED.\n")


def test_sweep(servo):
    """Slowly sweeps between 0 and 180 degrees."""
    print("\n--- Sweeping 0 to 180 and back ---")
    if servo is None:
        print("[Simulated] Sweeping 0 to 180...")
        return

    for a in range(0, 181, 10):
        servo.angle = a
        time.sleep(0.05)
    time.sleep(0.5)
    for a in range(180, -1, -10):
        servo.angle = a
        time.sleep(0.05)
    servo.value = None
    print("Sweep complete.\n")


def main():
    print("============================================================")
    print("  AgriScan 360 -- SG90 Pipe Door Servo Test")
    print("  Signal Pin: GPIO 23 (Physical Pin 16)")
    print("  0 deg   = CLOSED")
    print("  180 deg = OPEN")
    print("============================================================")

    servo = get_servo()

    # Default to closed position on start
    print("Setting initial state: CLOSED (0 deg)...")
    move_and_relax(servo, 0, hold_time=0.8)

    while True:
        print("\n+-- SG90 Servo Menu --------------------------------+")
        print("|  1. CLOSE Door (0 deg)                            |")
        print("|  2. OPEN Door (180 deg)                           |")
        print("|  3. Simulate Produce Drop (Open 2s -> Close)      |")
        print("|  4. Slow Sweep Test (0 -> 180 -> 0 deg)           |")
        print("|  5. Set Custom Angle (0 - 180)                    |")
        print("|  0. Exit                                          |")
        print("+---------------------------------------------------+")

        try:
            choice = input("Select [0-5]: ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if choice == "1":
            print("Closing door (0 deg)...")
            move_and_relax(servo, 0)
            print("Door closed.")
        elif choice == "2":
            print("Opening door (180 deg)...")
            move_and_relax(servo, 180)
            print("Door opened.")
        elif choice == "3":
            test_feed_drop(servo, open_time=2.0)
        elif choice == "4":
            test_sweep(servo)
        elif choice == "5":
            try:
                ang = float(input("Enter angle [0 to 180]: ").strip())
                if 0 <= ang <= 180:
                    print(f"Moving to {ang} deg...")
                    move_and_relax(servo, ang)
                else:
                    print("Angle must be between 0 and 180.")
            except ValueError:
                print("Invalid number.")
        elif choice in ("0", "q", "exit"):
            break
        else:
            print("Invalid option. Enter 0-5.")

    # Always ensure door is closed when exiting
    print("Ensuring door is closed on exit...")
    move_and_relax(servo, 0, hold_time=0.5)
    print("Test finished.")


if __name__ == "__main__":
    main()
