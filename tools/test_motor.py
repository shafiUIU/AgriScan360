"""
test_motor.py -- Standalone NEMA 17 & A4988 Hardware Diagnostic Tool
====================================================================
Use this tool on the Raspberry Pi 5 to diagnose stepper motor issues
without needing the camera, LEDs, or laptop server running.

Usage on Raspberry Pi:
    python tools/test_motor.py

Diagnostic Menu:
    1. Check Coil Lock (Test if ENABLE pin energizes coils)
    2. Step 1 step (Click test)
    3. Step 25 steps (Exact 45 degree turntable advance)
    4. Step 200 steps (Exact 360 degree full revolution)
    5. Continuous slow rotation (Forward & Reverse)
    6. Speed/Delay sweep (Test different pulse delays)
"""

import sys
import os
import time

# Add pi_client to path
PI_CLIENT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pi_client")
sys.path.insert(0, PI_CLIENT_DIR)

try:
    from gpiozero import DigitalOutputDevice
    GPIO_OK = True
except ImportError:
    GPIO_OK = False
    print("[!] Warning: gpiozero not found. Running in simulation mode.")

import config as cfg


def get_motor_pins():
    """Initializes and returns the 3 motor GPIO pins."""
    if not GPIO_OK:
        return None, None, None
    step_pin   = DigitalOutputDevice(cfg.PIN_STEP,   initial_value=False)
    dir_pin    = DigitalOutputDevice(cfg.PIN_DIR,    initial_value=False)
    enable_pin = DigitalOutputDevice(cfg.PIN_ENABLE, initial_value=True)  # True = disabled
    return step_pin, dir_pin, enable_pin


def pulse_steps(step_pin, count, delay=0.005):
    """Sends step pulses with specified delay."""
    for _ in range(count):
        step_pin.on()
        time.sleep(delay / 2.0)
        step_pin.off()
        time.sleep(delay / 2.0)


def test_coil_lock(enable_pin):
    """Tests if the motor coils lock up when ENABLE is active."""
    print("\n--- TEST 1: Coil Energize / Holding Torque Test ---")
    print("When ENABLE is active, the motor shaft should lock and resist manual turning.")
    print("Energizing coils (holding torque ON for 5 seconds)...")
    enable_pin.off()  # Active LOW = ON
    print("  -> COILS ENERGIZED. Try gently turning the shaft by hand.")
    print("  -> Is it stiff/locked? (It should be hard to turn).")
    for sec in range(5, 0, -1):
        print(f"     Releasing in {sec}s...", end="\r", flush=True)
        time.sleep(1.0)
    enable_pin.on()   # Active LOW = OFF
    print("\n  -> COILS RELEASED. Motor is now free to turn by hand.")
    print("Result check:")
    print("  - If the motor NEVER locked: Check 12V VMOT power, VDD (3.3V), and RESET-SLEEP bridge.")
    print("  - If the motor locked properly: Driver power and coils are healthy!")


def test_single_step(step_pin, dir_pin, enable_pin):
    """Sends a single step pulse."""
    print("\n--- TEST 2: Single Step Pulse ---")
    enable_pin.off()
    time.sleep(0.05)
    dir_pin.on()
    print("Sending 1 pulse...")
    pulse_steps(step_pin, 1, delay=0.01)
    time.sleep(0.5)
    enable_pin.on()
    print("1 pulse sent. You should hear a distinct micro-click or feel a nudge.")


def test_45_degrees(step_pin, dir_pin, enable_pin):
    """Moves 25 steps (45 degrees) forward, settles, then moves back."""
    print("\n--- TEST 3: 25 Steps (45 Degree Scan Stop) ---")
    enable_pin.off()
    time.sleep(0.05)

    print("Rotating 25 steps CLOCKWISE (45 deg)...")
    dir_pin.on()
    pulse_steps(step_pin, 25, delay=cfg.PULSE_DELAY)
    time.sleep(1.0)

    print("Rotating 25 steps COUNTER-CLOCKWISE (back to 0 deg)...")
    dir_pin.off()
    pulse_steps(step_pin, 25, delay=cfg.PULSE_DELAY)
    time.sleep(0.5)

    enable_pin.on()
    print("Done. Turntable should have rotated 45 deg and returned.")


def test_full_revolution(step_pin, dir_pin, enable_pin):
    """Moves 200 steps (360 degrees)."""
    print("\n--- TEST 4: 200 Steps (Full 360 Degree Revolution) ---")
    enable_pin.off()
    time.sleep(0.05)

    print(f"Rotating 200 steps at {cfg.PULSE_DELAY}s pulse delay (approx 1 rev/sec)...")
    dir_pin.on()
    pulse_steps(step_pin, 200, delay=cfg.PULSE_DELAY)
    time.sleep(0.5)

    enable_pin.on()
    print("Done. Turntable should have made exactly one full 360 deg turn.")


def test_continuous(step_pin, dir_pin, enable_pin):
    """Rotates continuously until Ctrl+C."""
    print("\n--- TEST 5: Continuous Rotation (Press Ctrl+C to Stop) ---")
    enable_pin.off()
    time.sleep(0.05)
    dir_pin.on()
    print("Running motor... Press Ctrl+C to stop.")
    try:
        step_count = 0
        while True:
            pulse_steps(step_pin, 10, delay=cfg.PULSE_DELAY)
            step_count += 10
            deg = (step_count % 200) * 1.8
            sys.stdout.write(f"\r  Steps: {step_count} | Angle: {deg:5.1f} deg  ")
            sys.stdout.flush()
    except KeyboardInterrupt:
        print("\nStopping motor...")
    finally:
        enable_pin.on()
        print("Motor stopped and coils released.")


def print_wiring_reference():
    """Prints the pinout reference."""
    print("\n============================================================")
    print("  A4988 to RASPBERRY PI 5 PINOUT REFERENCE")
    print("============================================================")
    print("  A4988 Pin     Pi 5 Pin (Physical)     Pi GPIO (BCM)")
    print("  ----------------------------------------------------------")
    print("  STEP          Physical Pin 11         GPIO 17")
    print("  DIR           Physical Pin 13         GPIO 27")
    print("  ENABLE        Physical Pin 15         GPIO 22")
    print("  VDD (Logic)   Physical Pin 1          3.3V (NOT 5V!)")
    print("  GND (Logic)   Physical Pin 6 or 9     GND")
    print("  ----------------------------------------------------------")
    print("  CRITICAL JUMPERS ON A4988:")
    print("  RESET -> Connect directly to SLEEP with a jumper wire!")
    print("           (Without this, the A4988 driver will NOT wake up)")
    print("  ----------------------------------------------------------")
    print("  EXTERNAL 12V POWER:")
    print("  VMOT          12V DC Positive (External Power Supply)")
    print("  GND (Motor)   12V DC Negative (External Power Supply)")
    print("  COMMON GND    Pi GND must be connected to 12V PSU GND!")
    print("  ----------------------------------------------------------")
    print("  MOTOR COILS (4 Wires):")
    print("  1A & 1B       Coil A (Pair 1)")
    print("  2A & 2B       Coil B (Pair 2)")
    print("============================================================\n")


def main():
    print_wiring_reference()
    if not GPIO_OK:
        print("[!] Cannot run hardware test on PC without GPIO.")
        print("[!] Copy this tool to the Raspberry Pi to test live hardware.")
        return

    step_pin, dir_pin, enable_pin = get_motor_pins()

    while True:
        print("\n+-- Stepper Motor Diagnostic Menu ------------------+")
        print("|  1. Test Coil Lock (Check if driver energizes)   |")
        print("|  2. Single Step (Click test)                     |")
        print("|  3. 25 Steps (45 Degree Scan Stop)               |")
        print("|  4. 200 Steps (Full 360 Degree Revolution)       |")
        print("|  5. Continuous Rotation (Speed / Stall Test)     |")
        print("|  6. Print Wiring Diagram & Troubleshooting Guide |")
        print("|  0. Exit                                         |")
        print("+---------------------------------------------------+")

        try:
            choice = input("Select an option [0-6]: ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if choice == "1":
            test_coil_lock(enable_pin)
        elif choice == "2":
            test_single_step(step_pin, dir_pin, enable_pin)
        elif choice == "3":
            test_45_degrees(step_pin, dir_pin, enable_pin)
        elif choice == "4":
            test_full_revolution(step_pin, dir_pin, enable_pin)
        elif choice == "5":
            test_continuous(step_pin, dir_pin, enable_pin)
        elif choice == "6":
            print_wiring_reference()
        elif choice in ("0", "q", "exit"):
            break
        else:
            print("Invalid option. Enter 0-6.")

    # Cleanup
    if GPIO_OK:
        enable_pin.on()  # Ensure coils released on exit
    print("\nMotor diagnostic closed. Coils de-energized.")


if __name__ == "__main__":
    main()
