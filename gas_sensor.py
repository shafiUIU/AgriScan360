"""
AgriScan 360 - Bosch BME688 Gas & Environmental Sensor Module
Measures Chamber Headspace VOCs, Temperature, and Humidity.
Computes Delta Gas (ΔGas) to detect internal fermentation / rotting gases.
"""

import time

try:
    import bme680
    BME_AVAILABLE = True
except ImportError:
    BME_AVAILABLE = False


class GasSensorController:
    def __init__(self):
        self.sensor = None
        self.baseline_resistance = None
        self.is_connected = False

        if BME_AVAILABLE:
            self._connect()
        else:
            print("[GasSensor] 'bme680' module not installed. Running in simulation mode.")

    def _connect(self):
        try:
            try:
                self.sensor = bme680.BME680(bme680.I2C_ADDR_PRIMARY)
            except (RuntimeError, IOError):
                self.sensor = bme680.BME680(bme680.I2C_ADDR_SECONDARY)

            self.sensor.set_humidity_oversample(bme680.OS_2X)
            self.sensor.set_pressure_oversample(bme680.OS_4X)
            self.sensor.set_temperature_oversample(bme680.OS_8X)
            self.sensor.set_filter(bme680.FILTER_SIZE_3)

            self.sensor.set_gas_status(bme680.ENABLE_GAS_MEAS)
            self.sensor.set_gas_heater_temperature(320)
            self.sensor.set_gas_heater_duration(150)
            self.sensor.select_gas_heater_profile(0)

            self.is_connected = True
            print("[GasSensor] BME688 initialized and gas heater armed.")
        except Exception as e:
            print(f"[GasSensor] Hardware connection failed: {e}. Falling back to mock mode.")
            self.is_connected = False

    def read_metrics(self):
        """Returns dict of (temp, humidity, pressure, gas_resistance_kohm)."""
        if not self.is_connected:
            # Mock fallback for offline testing
            return {"temp": 26.5, "humidity": 60.0, "pressure": 1012.0, "gas_kohm": 85.0}

        try:
            if self.sensor.get_sensor_data():
                gas_kohm = self.sensor.data.gas_resistance / 1000.0 if self.sensor.data.heat_stable else 0.0
                return {
                    "temp": round(self.sensor.data.temperature, 2),
                    "humidity": round(self.sensor.data.humidity, 2),
                    "pressure": round(self.sensor.data.pressure, 2),
                    "gas_kohm": round(gas_kohm, 2)
                }
        except Exception as e:
            print(f"[GasSensor] Read error: {e}")

        return {"temp": 0.0, "humidity": 0.0, "pressure": 0.0, "gas_kohm": 0.0}

    def calibrate_baseline(self, duration_sec=3):
        """Records initial clean air baseline before fruit gas accumulates."""
        print(f"[GasSensor] Calibrating chamber baseline for {duration_sec}s...")
        samples = []
        for _ in range(duration_sec):
            metrics = self.read_metrics()
            if metrics["gas_kohm"] > 0:
                samples.append(metrics["gas_kohm"])
            time.sleep(1)

        self.baseline_resistance = sum(samples) / len(samples) if samples else 80.0
        print(f"[GasSensor] Baseline locked at: {self.baseline_resistance:.2f} kΩ")
        return self.baseline_resistance

    def compute_gas_delta(self, current_gas_kohm):
        """
        Computes Drop in Gas Resistance from Baseline:
        ΔGas = Baseline - Current
        (Higher positive value indicates heavy rotting VOC buildup).
        """
        if self.baseline_resistance is None:
            return 0.0
        delta = self.baseline_resistance - current_gas_kohm
        return max(0.0, round(delta, 2))
