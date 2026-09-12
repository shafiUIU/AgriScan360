"""
gas_sensor.py — Bosch BME688 Gas / Environmental Sensor Driver
================================================================
Hardware:  Bosch BME688 (I2C address 0x77)
Wiring:    VCC→3.3V (Pin1), GND→GND (Pin6), SDA→GPIO2 (Pin3), SCL→GPIO3 (Pin5)

Measures:
    - Temperature (°C)
    - Humidity    (% RH)
    - Pressure    (hPa)
    - Gas resistance (kΩ)  ← Primary freshness/rot indicator

Strategy:
    1. Baseline = read gas resistance BEFORE placing fruit (empty chamber)
    2. Post-scan = read gas resistance AFTER 8-angle scan (~20 seconds)
    3. Delta = baseline − post_scan  (positive drop = VOC gas buildup = rot)

Library: pip install bme680   (works for BME688 in basic mode without AI features)
"""

import time
import logging
from typing import Optional
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

try:
    import bme680
    BME680_AVAILABLE = True
except ImportError:
    BME680_AVAILABLE = False
    log.warning("bme680 library not found. Using simulation mode.")

from config import (
    BME688_ADDRESS,
    GAS_BASELINE_READS, GAS_BASELINE_DELAY, GAS_DELTA_THRESHOLD
)


@dataclass
class GasReading:
    """Single BME688 sensor snapshot."""
    temperature: float = 0.0    # °C
    humidity:    float = 0.0    # %RH
    pressure:    float = 0.0    # hPa
    gas_ohms:    float = 0.0    # Ohms (raw)

    @property
    def gas_kohms(self) -> float:
        """Gas resistance in kΩ for human-readable display."""
        return round(self.gas_ohms / 1000, 2)


@dataclass
class ScanGasResult:
    """Gas delta computed across one full scan cycle."""
    baseline_kohms: float = 0.0
    post_scan_kohms: float = 0.0
    delta_kohms: float = 0.0           # baseline − post_scan (positive = gas detected)
    rot_suspicion: str = "LOW"         # LOW / MEDIUM / HIGH
    baseline_temp: float = 0.0
    baseline_humidity: float = 0.0

    def to_dict(self) -> dict:
        return {
            "baseline_kohms": self.baseline_kohms,
            "post_scan_kohms": self.post_scan_kohms,
            "delta_kohms": self.delta_kohms,
            "rot_suspicion": self.rot_suspicion,
            "temperature_c": self.baseline_temp,
            "humidity_pct": self.baseline_humidity,
        }


class GasSensor:
    """
    High-level BME688 interface with baseline/delta gas analysis.
    Falls back to simulation mode if hardware is not connected (useful for testing on PC).
    """

    def __init__(self, simulate: bool = False):
        self._simulate = simulate or not BME680_AVAILABLE
        self._sensor = None
        self._baseline: Optional[GasReading] = None

        if not self._simulate:
            self._init_sensor()

    def _init_sensor(self):
        """Initialize and configure BME688."""
        try:
            self._sensor = bme680.BME680(bme680.I2C_ADDR_PRIMARY)
            self._sensor.set_humidity_oversample(bme680.OS_2X)
            self._sensor.set_pressure_oversample(bme680.OS_4X)
            self._sensor.set_temperature_oversample(bme680.OS_8X)
            self._sensor.set_filter(bme680.FILTER_SIZE_3)
            self._sensor.set_gas_status(bme680.ENABLE_GAS_MEAS)
            self._sensor.set_gas_heater_temperature(320)   # °C  (optimal for VOC)
            self._sensor.set_gas_heater_duration(150)      # ms
            self._sensor.select_gas_heater_profile(0)
            log.info("BME688 initialized successfully at address 0x%02X", BME688_ADDRESS)
        except Exception as exc:
            log.error("BME688 init failed: %s — switching to simulation mode", exc)
            self._simulate = True
            self._sensor = None

    # ── Core read ─────────────────────────────────────────────────────────────

    def _read_once(self) -> GasReading:
        """Read one snapshot from the sensor (or simulate)."""
        if self._simulate:
            import random
            return GasReading(
                temperature=random.uniform(25, 32),
                humidity=random.uniform(55, 70),
                pressure=random.uniform(1008, 1013),
                gas_ohms=random.uniform(40_000, 120_000),
            )

        # Wait for valid data
        for _ in range(10):
            if self._sensor.get_sensor_data() and self._sensor.data.heat_stable:
                return GasReading(
                    temperature=self._sensor.data.temperature,
                    humidity=self._sensor.data.humidity,
                    pressure=self._sensor.data.pressure,
                    gas_ohms=self._sensor.data.gas_resistance,
                )
            time.sleep(0.3)

        # Fallback if heat never stabilized
        self._sensor.get_sensor_data()
        return GasReading(
            temperature=getattr(self._sensor.data, 'temperature', 0),
            humidity=getattr(self._sensor.data, 'humidity', 0),
            pressure=getattr(self._sensor.data, 'pressure', 0),
            gas_ohms=getattr(self._sensor.data, 'gas_resistance', 0),
        )

    def read_averaged(self, count: int = GAS_BASELINE_READS,
                      delay: float = GAS_BASELINE_DELAY) -> GasReading:
        """Take `count` readings and return the averaged result."""
        readings = []
        for _ in range(count):
            readings.append(self._read_once())
            time.sleep(delay)
        return GasReading(
            temperature=sum(r.temperature for r in readings) / count,
            humidity=sum(r.humidity    for r in readings) / count,
            pressure=sum(r.pressure    for r in readings) / count,
            gas_ohms=sum(r.gas_ohms    for r in readings) / count,
        )

    # ── Baseline management ───────────────────────────────────────────────────

    def calibrate_baseline(self) -> GasReading:
        """
        Read baseline gas resistance from EMPTY chamber.
        Call this BEFORE placing fruit on the turntable.
        """
        log.info("Calibrating BME688 baseline (chamber must be empty)...")
        self._baseline = self.read_averaged()
        log.info("Baseline: %.1f kΩ  T=%.1f°C  RH=%.1f%%",
                 self._baseline.gas_kohms, self._baseline.temperature, self._baseline.humidity)
        return self._baseline

    def compute_delta(self) -> ScanGasResult:
        """
        Read post-scan gas and compute delta vs baseline.
        Call AFTER completing the full 8-angle scan.
        """
        if self._baseline is None:
            log.warning("No baseline set — running quick baseline now")
            self.calibrate_baseline()

        post = self.read_averaged(count=3, delay=0.5)
        delta = self._baseline.gas_kohms - post.gas_kohms   # positive = gas drop = rot

        # Classify suspicion level
        if delta < 2.0:
            suspicion = "LOW"
        elif delta < GAS_DELTA_THRESHOLD:
            suspicion = "MEDIUM"
        else:
            suspicion = "HIGH"

        result = ScanGasResult(
            baseline_kohms=self._baseline.gas_kohms,
            post_scan_kohms=post.gas_kohms,
            delta_kohms=round(delta, 2),
            rot_suspicion=suspicion,
            baseline_temp=self._baseline.temperature,
            baseline_humidity=self._baseline.humidity,
        )
        log.info("Gas delta: %.2f kΩ  Suspicion: %s", delta, suspicion)
        return result
