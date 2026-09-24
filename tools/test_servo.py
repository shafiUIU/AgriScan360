"""
test_servo.py -- SG90 Micro Servo Pipe Feed Door Test Tool
===========================================================
Hardware: SG90 Micro Servo (Pipe Feeder Door)
Wiring:
    Brown / Black Wire  -> GND (Physical Pin 14 or 20)
    Red Wire            -> 5V (Physical Pin 2 or 4)
    Orange / Yellow Wire-> GPIO 23 (Physical Pin 16)

Configured Door Logic:
    Starting Position = 0 Degree  -> Door CLOSED
    Ending Position   = 90 Degree -> Door OPEN
    Open Duration     = 2.0 Seconds
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

# Exact Door Positions and Timing
DOOR_CLOSED_ANGLE = 0
DOOR_OPEN_ANGLE = 90
DOOR_OPEN_DURATION = 2.0


def get_servo():
    if not GPIOZERO_OK:
        return None
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
        print(f"[Simulated] Servo moved to {angle} deg (held {hold_time}s)")
        return

    servo.angle = angle
    time.sleep(hold_time)
    # Detach PWM to silence motor hum and avoid continuous current draw
    servo.value = None


def test_feed_drop(servo, closed_angle=DOOR_CLOSED_ANGLE, open_angle=DOOR_OPEN_ANGLE, open_time=DOOR_OPEN_DURATION):
    """
    Simulates real item drop sequence:
      1. Starting at 0 deg (CLOSED)
      2. Open door to 90 deg (OPEN)
      3. Hold open for 2.0 seconds
      4. Close door back to 0 deg (CLOSED)
    """
    print(f"\n--- Testing Feed Drop Sequence ({open_time}s duration) ---")
    print(f"1. Opening door to {open_angle} deg...")
    move_and_relax(servo, open_angle, hold_time=open_time)
    print(f"   -> Door held open for {open_time}s. Item drops onto table.")
    print(f"2. Closing door back to {closed_angle} deg...")
    move_and_relax(servo, closed_angle, hold_time=0.8)
    print(f"   -> Door is now CLOSED ({closed_angle} deg).\n")


def test_sweep(servo, start_angle=DOOR_CLOSED_ANGLE, end_angle=DOOR_OPEN_ANGLE):
    """Slowly sweeps between closed (0 deg) and open (90 deg)."""
    print(f"\n--- Sweeping {start_angle} deg <-> {end_angle} deg ---")
    if servo is None:
        print(f"[Simulated] Sweeping {start_angle} -> {end_angle} -> {start_angle}...")
        return

    step = -5 if end_angle < start_angle else 5
    for a in range(start_angle, end_angle + (1 if step > 0 else -1), step):
        servo.angle = a
        time.sleep(0.04)
    time.sleep(0.5)
    for a in range(end_angle, start_angle - (1 if step > 0 else -1), -step):
        servo.angle = a
        time.sleep(0.04)
    servo.value = None
    print("Sweep complete.\n")


def main():
    print("============================================================")
    print("  AgriScan 360 -- SG90 Pipe Door Servo Controller")
    print("  Signal Pin       : GPIO 23 (Physical Pin 16)")
    print(f"  Closed Position  : {DOOR_CLOSED_ANGLE} deg")
    print(f"  Open Position    : {DOOR_OPEN_ANGLE} deg")
    print(f"  Open Duration    : {DOOR_OPEN_DURATION} seconds")
    print("============================================================")

    servo = get_servo()

    # Default to closed position (0 deg) on start
    print(f"Setting initial state: CLOSED ({DOOR_CLOSED_ANGLE} deg)...")
    move_and_relax(servo, DOOR_CLOSED_ANGLE, hold_time=0.8)

    while True:
        print("\n+-- SG90 Door Servo Menu ---------------------------+")
        print(f"|  1. CLOSE Door ({DOOR_CLOSED_ANGLE} deg)                              |")
        print(f"|  2. OPEN Door ({DOOR_OPEN_ANGLE} deg)                              |")
        print(f"|  3. Simulate Produce Drop (0 deg -> 90 deg -> 2s -> 0 deg)|")
        print(f"|  4. Sweep Test (0 deg <-> 90 deg)                 |")
        print(f"|  5. Set Custom Angle (0 - 180)                    |")
        print(f"|  0. Exit                                          |")
        print("+---------------------------------------------------+")

        try:
            choice = input("Select [0-5]: ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if choice == "1":
            print(f"Closing door ({DOOR_CLOSED_ANGLE} deg)...")
            move_and_relax(servo, DOOR_CLOSED_ANGLE)
            print("Door closed.")
        elif choice == "2":
            print(f"Opening door ({DOOR_OPEN_ANGLE} deg)...")
            move_and_relax(servo, DOOR_OPEN_ANGLE)
            print("Door opened.")
        elif choice == "3":
            test_feed_drop(servo, closed_angle=DOOR_CLOSED_ANGLE, open_angle=DOOR_OPEN_ANGLE, open_time=DOOR_OPEN_DURATION)
        elif choice == "4":
            test_sweep(servo, start_angle=DOOR_CLOSED_ANGLE, end_angle=DOOR_OPEN_ANGLE)
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

    # Always ensure door is closed at 0 deg on exit
    print(f"Ensuring door is closed ({DOOR_CLOSED_ANGLE} deg) on exit...")
    move_and_relax(servo, DOOR_CLOSED_ANGLE, hold_time=0.5)
    print("Test finished.")


if __name__ == "__main__":
    main()
