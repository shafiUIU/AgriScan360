"""
test_oled.py -- Interactive 1.3-inch SSD1306 OLED Hardware Test Tool
====================================================================
Run this directly on the Raspberry Pi 5 to verify every display screen:

    python tools/test_oled.py

Works in simulation mode on a PC (prints to terminal) if no OLED is connected.
"""

import sys
import os
import time

PI_CLIENT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pi_client"
)
sys.path.insert(0, PI_CLIENT_DIR)

from display import OLEDDisplay


def print_menu():
    print("\n+-- 1.3-inch OLED Test Menu --------------------------------+")
    print("|  1. Splash Screen (Startup)                               |")
    print("|  2. BME688 Sniffing Empty Box (Baseline Phase)            |")
    print("|  3. Apple Detected                                        |")
    print("|  4. Tomato Detected                                       |")
    print("|  5. Eggplant Detected                                     |")
    print("|  6. Incubation Countdown (300s countdown demo)            |")
    print("|  7. SCANNING... (cycle all 8 stops)                       |")
    print("|  8. Uploading to Server                                   |")
    print("|  9. Result: HEALTHY (FRESH)                               |")
    print("| 10. Result: FAIRLY FRESH (MID_FRESH)                      |")
    print("| 11. Result: EARLY ROT (MID_ROTTEN)                        |")
    print("| 12. Result: ROTTEN                                        |")
    print("| 13. SERVER OFFLINE                                        |")
    print("| 14. ERROR Screen                                          |")
    print("| 15. READY (Idle)                                          |")
    print("| 16. Full Workflow Demo (all screens in sequence)          |")
    print("|  0. Exit                                                  |")
    print("+-----------------------------------------------------------+")


def full_demo(disp: OLEDDisplay):
    """Runs through the entire AgriScan 360 scan workflow on the OLED."""
    print("\n>>> Running full workflow demo...")

    print("  [1] Splash screen (1.5s)")
    disp.show_splash()
    time.sleep(1.0)

    print("  [2] BME688 sniffing empty box (3s)")
    disp.show_bme_sniffing_empty()
    time.sleep(3.0)

    print("  [3] Item detected: Apple (2s)")
    disp.show_item_detected("Apple")
    time.sleep(2.0)

    print("  [4] Incubation countdown (10s fast demo)")
    for secs in range(10, 0, -1):
        disp.show_incubating(secs)
        time.sleep(0.5)

    print("  [5] Scanning 8 stops")
    for stop in range(8):
        disp.show_scanning(stop=stop, total=8)
        print(f"       Stop {stop + 1}/8")
        time.sleep(0.6)

    print("  [6] Uploading (2s)")
    disp.show_uploading()
    time.sleep(2.0)

    print("  [7] Result: HEALTHY")
    disp.show_result("FRESH", confidence=96.4, gas_delta=-1.2)
    time.sleep(3.0)

    print("  [8] Ready screen")
    disp.show_ready()
    time.sleep(2.0)

    print(">>> Full demo complete.")


def main():
    print("============================================================")
    print("  AgriScan 360 -- 1.3-inch OLED Display Hardware Test")
    print("  SDA -> GPIO 2 (Physical Pin 3)")
    print("  SCL -> GPIO 3 (Physical Pin 5)")
    print("  VCC -> 3.3V  (Physical Pin 1)")
    print("  GND -> GND   (Physical Pin 6)")
    print("  I2C Address: 0x3C (default) or 0x3D")
    print("============================================================")

    disp = OLEDDisplay()

    while True:
        print_menu()
        try:
            choice = input("Select [0-16]: ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if choice == "1":
            disp.show_splash()
        elif choice == "2":
            disp.show_bme_sniffing_empty()
            print("  Showing BME sniffing screen for 3 seconds...")
            time.sleep(3)
        elif choice == "3":
            disp.show_item_detected("Apple")
        elif choice == "4":
            disp.show_item_detected("Tomato")
        elif choice == "5":
            disp.show_item_detected("Eggplant")
        elif choice == "6":
            print("  Running 10-second incubation countdown demo...")
            for secs in range(10, 0, -1):
                disp.show_incubating(secs)
                time.sleep(0.5)
        elif choice == "7":
            print("  Cycling all 8 scan stops...")
            for stop in range(8):
                disp.show_scanning(stop=stop, total=8)
                print(f"  Stop {stop + 1}/8")
                time.sleep(0.8)
        elif choice == "8":
            disp.show_uploading()
        elif choice == "9":
            disp.show_result("FRESH", confidence=96.4, gas_delta=-0.8)
        elif choice == "10":
            disp.show_result("MID_FRESH", confidence=78.2, gas_delta=-3.2)
        elif choice == "11":
            disp.show_result("MID_ROTTEN", confidence=82.1, gas_delta=-12.4)
        elif choice == "12":
            disp.show_result("ROTTEN", confidence=94.7, gas_delta=-31.5)
        elif choice == "13":
            disp.show_server_offline()
        elif choice == "14":
            disp.show_error("BME sensor init fail")
        elif choice == "15":
            disp.show_ready()
        elif choice == "16":
            full_demo(disp)
        elif choice in ("0", "q", "exit"):
            break
        else:
            print("Invalid option. Enter 0-16.")

    disp.cleanup()
    print("\nOLED display cleared. Test complete.")


if __name__ == "__main__":
    main()
