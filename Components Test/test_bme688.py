#!/usr/bin/env python3
"""
AgriScan 360 - Bosch BME688 AI Gas Sensor Test Script
Hardware:
  - Raspberry Pi 5
  - Bosch BME688 (or BME680) Breakout Board (I2C Interface)

Outputs:
  - Temperature (°C)
  - Relative Humidity (%)
  - Atmospheric Pressure (hPa)
  - Gas Resistance (kΩ / Ohms) -> Primary indicator for fruit VOC emission

Installation Prerequisites:
  sudo apt install -y python3-smbus i2c-tools python3-pip
  pip install bme680 smbus2 --break-system-packages
"""

import time
import sys

# Attempt importing bme680 library
try:
    import bme680
except ImportError:
    print("[ERROR] 'bme680' library not found!")
    print("Please install it on your Raspberry Pi using:")
    print("  pip install bme680 smbus2 --break-system-packages")
    sys.exit(1)


def initialize_sensor():
    """Initializes and configures the BME688 sensor over I2C."""
    try:
        # BME688 standard I2C addresses are 0x77 (primary) or 0x76 (secondary)
        try:
            sensor = bme680.BME680(bme680.I2C_ADDR_PRIMARY)
            print("[INFO] BME688 connected at primary address 0x77.")
        except (RuntimeError, IOError):
            sensor = bme680.BME680(bme680.I2C_ADDR_SECONDARY)
            print("[INFO] BME688 connected at secondary address 0x76.")

        # Configure oversampling rates
        sensor.set_humidity_oversample(bme680.OS_2X)
        sensor.set_pressure_oversample(bme680.OS_4X)
        sensor.set_temperature_oversample(bme680.OS_8X)
        sensor.set_filter(bme680.FILTER_SIZE_3)

        # Configure the gas heater profile (320°C for 150ms for VOC / rotting gas detection)
        sensor.set_gas_status(bme680.ENABLE_GAS_MEAS)
        sensor.set_gas_heater_temperature(320)
        sensor.set_gas_heater_duration(150)
        sensor.select_gas_heater_profile(0)

        return sensor

    except Exception as e:
        print(f"\n[FATAL ERROR] Could not connect to BME688: {e}")
        print("Check:")
        print("  1. Are SDA (Pin 3) and SCL (Pin 5) wired correctly?")
        print("  2. Is I2C enabled in Raspberry Pi? (Run: sudo raspi-config -> Interfaces -> I2C)")
        print("  3. Run 'i2cdetect -y 1' in terminal to verify device is detected at 0x76 or 0x77.")
        sys.exit(1)


def main():
    print("==================================================")
    print("  AgriScan 360 - Bosch BME688 Gas Sensor Test")
    print("==================================================")
    print("Initializing sensor and warming up gas heater...")
    
    sensor = initialize_sensor()

    print("\nStarting continuous read loop (Press Ctrl+C to stop)...")
    print("--------------------------------------------------------------------------------")
    print(f"{'Time':<10} | {'Temp (°C)':<10} | {'Humidity (%)':<14} | {'Pressure (hPa)':<15} | {'Gas Res (kΩ)':<14} | {'Status'}")
    print("--------------------------------------------------------------------------------")

    # Burn-in / Warm-up: The MOX heater needs ~5 seconds to stabilize
    warmup_cycles = 5
    for i in range(warmup_cycles, 0, -1):
        print(f"Heater stabilizing... {i}s remaining", end="\r")
        time.sleep(1)
    print("                                                  ", end="\r")

    baseline_gas = None

    try:
        while True:
            if sensor.get_sensor_data():
                temp = sensor.data.temperature
                hum = sensor.data.humidity
                press = sensor.data.pressure

                # Check if gas reading is valid and heated
                if sensor.data.heat_stable:
                    gas_res_kohm = sensor.data.gas_resistance / 1000.0  # Convert to kOhms
                    
                    if baseline_gas is None:
                        baseline_gas = gas_res_kohm
                    
                    # Evaluate change from baseline
                    # Rotting fruit releases VOCs -> Resistance drops significantly!
                    diff = baseline_gas - gas_res_kohm
                    if diff > 15.0:
                        status = "⚠️ GAS SPIKE! (Rot scent detected)"
                    elif diff > 5.0:
                        status = "🟡 Elevated VOCs"
                    else:
                        status = "🟢 Clean / Baseline Air"

                    timestamp = time.strftime("%H:%M:%S")
                    print(f"{timestamp:<10} | {temp:<10.2f} | {hum:<14.2f} | {press:<15.2f} | {gas_res_kohm:<14.2f} | {status}")

                else:
                    print(f"{time.strftime('%H:%M:%S'):<10} | Heating up sensor plate...")

            time.sleep(1.0)

    except KeyboardInterrupt:
        print("\n[STOPPED] BME688 test completed by user.")


if __name__ == "__main__":
    main()
