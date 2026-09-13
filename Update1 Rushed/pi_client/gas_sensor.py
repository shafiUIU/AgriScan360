"""
gas_sensor.py — BME688 Gas Sensor (REMOVED IN UPDATE1 RUSHED)
==============================================================
UPDATE1 RUSHED CHANGES:
    - BME688 gas sensor is NOT used in this version.
    - Module is kept as a STUB returning zeroed/neutral dummy data
      so that imports in main.py still work without modification.
    - All real I2C communication is commented out.

When the BME688 is re-integrated (full version), swap back to the
original gas_sensor.py from the AgriScan360 folder.
"""

import logging
log = logging.getLogger(__name__)


# --- Real BME688 imports REMOVED ---
# import bme680
# BME680_AVAILABLE = True/False


class GasReading:
    """Dummy gas reading — returns neutral zeros."""
    temperature: float = 0.0
    humidity:    float = 0.0
    pressure:    float = 0.0
    gas_ohms:    float = 0.0

    @property
    def gas_kohms(self) -> float:
        return 0.0


class ScanGasResult:
    """
    Dummy gas result — all zeros.
    Returned so that uploader.py and main.py don't need to be changed.
    """
    baseline_kohms: float  = 0.0
    post_scan_kohms: float = 0.0
    delta_kohms: float     = 0.0
    rot_suspicion: str     = "N/A"    # Marked N/A since sensor not present
    baseline_temp: float   = 0.0
    baseline_humidity: float = 0.0

    def to_dict(self) -> dict:
        return {
            "baseline_kohms":  0.0,
            "post_scan_kohms": 0.0,
            "delta_kohms":     0.0,
            "rot_suspicion":   "N/A",
            "temperature_c":   0.0,
            "humidity_pct":    0.0,
        }


class GasSensor:
    """
    STUB — BME688 removed from this build.
    All methods return neutral dummy ScanGasResult().
    """

    def __init__(self, simulate: bool = False):
        log.info("GasSensor: STUB MODE — BME688 not installed in Update1 Rushed.")

    def calibrate_baseline(self) -> GasReading:
        """STUB — returns dummy GasReading."""
        log.info("GasSensor: Skipping baseline calibration (sensor removed).")
        return GasReading()

    def read_averaged(self, count: int = 1, delay: float = 0.0) -> GasReading:
        """STUB — returns dummy GasReading."""
        return GasReading()

    def compute_delta(self) -> ScanGasResult:
        """STUB — returns zeroed ScanGasResult."""
        log.info("GasSensor: Returning dummy gas result (sensor removed).")
        return ScanGasResult()
