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


def scan_i2c_buses():
    """Scans all active /dev/i2c-* buses for any responding device."""
    import glob
    bus_paths = sorted(glob.glob("/dev/i2c-*"))
    if not bus_paths:
        print("[!] No /dev/i2c-* interfaces found. Please enable I2C via 'sudo raspi-config' and reboot.")
        return {}

    found = {}
    try:
        from smbus2 import SMBus
    except ImportError:
        SMBus = None

    if not SMBus:
        print("[!] smbus2 not installed. Testing directly with bme680 library.")
        return {}

    print("\n--- Scanning all available I2C buses on Raspberry Pi 5 ---")
    for bpath in bus_paths:
        try:
            bnum = int(bpath.split("-")[-1])
            devices = []
            with SMBus(bnum) as bus:
                for addr in range(0x03, 0x78):
                    try:
                        bus.read_byte(addr)
                        devices.append(addr)
                    except Exception:
                        pass
            if devices:
                found[bnum] = devices
                print(f"  [+] Bus {bnum} ({bpath}): Found device(s) at: {[hex(a) for a in devices]}")
            else:
                print(f"  [-] Bus {bnum} ({bpath}): No devices responding")
        except Exception as err:
            print(f"  [?] Bus {bpath}: Could not probe ({err})")
    print("----------------------------------------------------------\n")
    return found


def initialize_sensor():
    """Initializes and configures the BME688 sensor over I2C with multi-bus probe."""
    # First, run a quick hardware scan across all buses
    bus_map = scan_i2c_buses()

    # Search for standard BME addresses 0x76 or 0x77
    target_bus = 1
    target_addr = None

    for bnum, addrs in bus_map.items():
        if 0x76 in addrs:
            target_bus = bnum
            target_addr = 0x76
            break
        elif 0x77 in addrs:
            target_bus = bnum
            target_addr = 0x77
            break

    # If not found via scan, try standard address list on bus 1
    addrs_to_try = [target_addr] if target_addr else [bme680.I2C_ADDR_PRIMARY, bme680.I2C_ADDR_SECONDARY]

    sensor = None
    last_err = None

    for addr in addrs_to_try:
        if addr is None:
            continue
        try:
            # Note: bme680 supports passing an i2c_device (e.g. SMBus(target_bus))
            try:
                from smbus2 import SMBus
                i2c_dev = SMBus(target_bus)
                sensor = bme680.BME680(addr, i2c_device=i2c_dev)
            except Exception:
                sensor = bme680.BME680(addr)

            print(f"[INFO] BME688 successfully connected at address 0x{addr:02X} on bus {target_bus}!")
            break
        except Exception as e:
            last_err = e
            continue

    if sensor is None:
        print(f"\n[FATAL ERROR] Could not connect to BME688: {last_err}")
        print("\nPhysical Hardware Diagnosis Checklist:")
        print("  1. Silk-Screen Pin Order Check:")
        print("     Read the actual text printed on your sensor board next to each pin.")
        print("     Make sure SDI (SDA) is Pin 3 and SCK (SCL) is Pin 5.")
        print("  2. Did you tie CS to 3.3V?")
        print("     If CS is disconnected, Bosch sensors default to SPI and ignore I2C.")
        print("  3. Check Power:")
        print("     Connect 3.3V directly to the '3V' / '3V3' pin (NOT 'vin').")
        print("  4. Check Ground:")
        print("     GND must be connected to Pi Pin 9 or Pin 6.")
        sys.exit(1)

    # Configure oversampling rates
    sensor.set_humidity_oversample(bme680.OS_2X)
    sensor.set_pressure_oversample(bme680.OS_4X)
    sensor.set_temperature_oversample(bme680.OS_8X)
    sensor.set_filter(bme680.FILTER_SIZE_3)

    # Configure the gas heater profile (320°C for 150ms for VOC detection)
    sensor.set_gas_status(bme680.ENABLE_GAS_MEAS)
    sensor.set_gas_heater_temperature(320)
    sensor.set_gas_heater_duration(150)
    sensor.select_gas_heater_profile(0)

    return sensor


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
