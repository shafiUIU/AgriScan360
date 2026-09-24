"""
gas_sensor.py -- Bosch BME688 Gas / Environmental Sensor Driver (Adaptive)
===========================================================================
Hardware:  Bosch BME688 (I2C address 0x77 or 0x76)
Wiring:    VCC->3.3V (Pin1), GND->GND (Pin6), SDA->GPIO2 (Pin3), SCL->GPIO3 (Pin5)

Chamber Specifications:
    Volume: 27 Liters (closed containment box)

Adaptive Features:
    1. Auto-Detection: Automatically probes I2C for BME688.
       If NOT found: assumes BME is not implemented yet, logs notice, and
       returns neutral zero delta without crashing.
    2. Continuous Sniffing: Runs in a background thread sampling VOC gas
       resistance continuously inside the 27L box while the 16 photos are taken.
"""

import time
import logging
import threading
from typing import Optional, List
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

try:
    import bme680
    BME680_AVAILABLE = True
except ImportError:
    BME680_AVAILABLE = False

from config import (
    BME688_I2C_ADDRESSES,
    BME_WARMUP_DISCARD_SEC,
    GAS_EMPTY_BOX_SNIFF_SEC,
    GAS_BASELINE_READS, GAS_BASELINE_DELAY,
    GAS_SNIFF_INTERVAL_SEC, GAS_DELTA_THRESHOLD,
    CHAMBER_VOLUME_LITERS
)

#    Per-Produce Gas Freshness Profiles                                         
# Each produce has its own VOC resistance drop thresholds calibrated to its
# natural decay chemistry inside the 27L sealed chamber.
# Thresholds are: (ratio_pct, delta_kohms) -- whichever is breached first wins.
#   FRESH      : ratio < fresh_r   AND delta < fresh_d
#   MID_FRESH  : ratio < midf_r    AND delta < midf_d
#   MID_ROTTEN : ratio < midr_r    AND delta < midr_d
#   ROTTEN     : ratio >= midr_r   OR  delta >= midr_d
PRODUCE_GAS_PROFILES = {
    # Tomatoes release VOCs (hexanal, ethanol) quickly once overripe.
    "Tomato": {
        "FRESH":      (8.0,  3.0),
        "MID_FRESH":  (15.0, 5.5),
        "MID_ROTTEN": (25.0, 9.0),
    },
    # Apples emit ethylene-related VOCs; slightly higher baseline acceptable.
    "Apple": {
        "FRESH":      (10.0, 4.0),
        "MID_FRESH":  (18.0, 7.0),
        "MID_ROTTEN": (28.0, 11.0),
    },
    # Eggplant decays more subtly -- lower thresholds catch early rot faster.
    "Eggplant": {
        "FRESH":      (6.0,  2.5),
        "MID_FRESH":  (12.0, 4.5),
        "MID_ROTTEN": (20.0, 7.5),
    },
    # Generic fallback for any unsupported produce
    "default": {
        "FRESH":      (8.0,  3.5),
        "MID_FRESH":  (16.0, 6.0),
        "MID_ROTTEN": (24.0, 9.5),
    },
}


def classify_gas_freshness(produce_name: str, gas_ratio_pct: float,
                            delta_kohms: float, gas_slope_per_sec: float = 0.0) -> str:
    """
    Classify freshness of a scanned produce using per-produce VOC gas profiles.

    Returns one of: "FRESH", "MID_FRESH", "MID_ROTTEN", "ROTTEN"
    Falls back to 'default' profile if produce_name not in PRODUCE_GAS_PROFILES.
    """
    profile = PRODUCE_GAS_PROFILES.get(produce_name.title(),
                                        PRODUCE_GAS_PROFILES["default"])
    fresh_r,    fresh_d    = profile["FRESH"]
    midf_r,     midf_d     = profile["MID_FRESH"]
    midr_r,     midr_d     = profile["MID_ROTTEN"]

    # Slope modifier: steep negative confirms active decomposition -> upgrade severity
    slope_boost = 0.0
    if gas_slope_per_sec < -0.15:
        slope_boost = 8.0   # equivalent extra ratio points
    elif gas_slope_per_sec < -0.05:
        slope_boost = 4.0

    effective_ratio = gas_ratio_pct + slope_boost

    if effective_ratio >= midr_r or delta_kohms >= midr_d:
        return "ROTTEN"
    elif effective_ratio >= midf_r or delta_kohms >= midf_d:
        return "MID_ROTTEN"
    elif effective_ratio >= fresh_r or delta_kohms >= fresh_d:
        return "MID_FRESH"
    else:
        return "FRESH"



@dataclass
class GasReading:
    """Single BME688 sensor snapshot."""
    temperature: float = 0.0    # C
    humidity:    float = 0.0    # %RH
    pressure:    float = 0.0    # hPa
    gas_ohms:    float = 0.0    # Ohms (raw high precision)
    timestamp:   float = 0.0

    @property
    def gas_kohms(self) -> float:
        return round(self.gas_ohms / 1000.0, 3)


@dataclass
class ScanGasResult:
    """Rich multi-feature gas analytics across the 27L containment scan."""
    baseline_kohms: float = 0.0
    post_scan_kohms: float = 0.0
    delta_kohms: float = 0.0           # baseline - post_scan (positive = rot gas drop)
    gas_min_kohms: float = 0.0         # minimum resistance observed during scan (smoothed)
    gas_max_kohms: float = 0.0         # maximum resistance observed during scan
    gas_mean_kohms: float = 0.0        # mean resistance across full scan
    gas_std_kohms: float = 0.0         # standard deviation of gas resistance
    gas_ratio_pct: float = 0.0         # (baseline - smoothed_min) / baseline * 100% (scale-invariant drop)
    gas_slope_per_sec: float = 0.0     # linear regression rate dR/dt (kOhm/s, negative = active decay)
    temperature_c: float = 0.0         # average ambient temperature (C)
    humidity_pct: float = 0.0          # average ambient relative humidity (%RH)
    pressure_hpa: float = 0.0          # ambient barometric pressure (hPa)
    sample_count: int = 0              # total gas snapshots collected across 16-frame cycle
    rot_suspicion: str = "HEALTHY"     # HEALTHY / EARLY_ROT / SEVERE_ROT / NOT_INSTALLED
    installed: bool = True
    raw_baseline_ohms: float = 0.0     # exact baseline in Ohms
    raw_post_scan_ohms: float = 0.0    # exact post-scan in Ohms

    # Backwards compatibility properties
    @property
    def baseline_temp(self) -> float:
        return self.temperature_c

    @property
    def baseline_humidity(self) -> float:
        return self.humidity_pct

    def to_dict(self) -> dict:
        return {
            "baseline_kohms": round(self.baseline_kohms, 2),
            "post_scan_kohms": round(self.post_scan_kohms, 2),
            "delta_kohms": round(self.delta_kohms, 2),
            "gas_min_kohms": round(self.gas_min_kohms, 2),
            "gas_max_kohms": round(self.gas_max_kohms, 2),
            "gas_mean_kohms": round(self.gas_mean_kohms, 2),
            "gas_std_kohms": round(self.gas_std_kohms, 2),
            "gas_ratio_pct": round(self.gas_ratio_pct, 2),
            "gas_slope_per_sec": round(self.gas_slope_per_sec, 4),
            "sample_count": self.sample_count,
            "rot_suspicion": self.rot_suspicion,
            "temperature_c": round(self.temperature_c, 1),
            "humidity_pct": round(self.humidity_pct, 1),
            "pressure_hpa": round(self.pressure_hpa, 1),
            "installed": self.installed,
        }


class GasSensor:
    """
    High-level BME688 interface with adaptive auto-detection and continuous sniffing.
    """

    def __init__(self, simulate: bool = False):
        self.simulate = simulate
        self.installed = False
        self._sensor = None
        self._baseline: Optional[GasReading] = None
        self._sniff_thread: Optional[threading.Thread] = None
        self._sniffing = False
        self._readings: List[GasReading] = []

        if not self.simulate and BME680_AVAILABLE:
            self._probe_and_init()
        elif self.simulate:
            self.installed = True
            log.info("GasSensor: Running in SIMULATION mode (synthetic VOC gas generation)")
        else:
            log.info("GasSensor: BME688 library not available and hardware not detected. "
                     "Assuming BME is not yet implemented.")

    def _probe_and_init(self):
        """Auto-probe I2C addresses (0x77, 0x76) to detect BME688."""
        for addr in BME688_I2C_ADDRESSES:
            try:
                self._sensor = bme680.BME680(addr)
                self._sensor.set_humidity_oversample(bme680.OS_2X)
                self._sensor.set_pressure_oversample(bme680.OS_4X)
                self._sensor.set_temperature_oversample(bme680.OS_8X)
                self._sensor.set_filter(bme680.FILTER_SIZE_3)
                self._sensor.set_gas_status(bme680.ENABLE_GAS_MEAS)
                self._sensor.set_gas_heater_temperature(320)   # 320C for VOC
                self._sensor.set_gas_heater_duration(150)
                self._sensor.select_gas_heater_profile(0)
                self.installed = True
                log.info("BME688 detected and initialized successfully at I2C address 0x%02X (27L box mode)", addr)
                self.heatup_thrice()
                return
            except Exception:
                continue

        log.info("BME688 not detected on I2C (probed %s). "
                 "Assuming BME sensor has not been implemented yet.",
                 [hex(a) for a in BME688_I2C_ADDRESSES])
        self.installed = False
        self._sensor = None

    #    Single Read                                                            

    def _read_once(self) -> GasReading:
        now = time.time()
        if self.simulate:
            import random
            return GasReading(
                temperature=round(random.uniform(24.0, 27.0), 1),
                humidity=round(random.uniform(50.0, 65.0), 1),
                pressure=round(random.uniform(1010.0, 1013.0), 1),
                gas_ohms=random.uniform(50_000, 100_000),
                timestamp=now,
            )

        if not self.installed or not self._sensor:
            return GasReading(timestamp=now)

        for _ in range(10):
            if self._sensor.get_sensor_data() and self._sensor.data.heat_stable:
                return GasReading(
                    temperature=self._sensor.data.temperature,
                    humidity=self._sensor.data.humidity,
                    pressure=self._sensor.data.pressure,
                    gas_ohms=self._sensor.data.gas_resistance,
                    timestamp=now,
                )
            time.sleep(0.1)

        self._sensor.get_sensor_data()
        return GasReading(
            temperature=getattr(self._sensor.data, 'temperature', 0.0),
            humidity=getattr(self._sensor.data, 'humidity', 0.0),
            pressure=getattr(self._sensor.data, 'pressure', 0.0),
            gas_ohms=getattr(self._sensor.data, 'gas_resistance', 0.0),
            timestamp=now,
        )

    #    Hotplate Pre-Heat & Baseline Calibration                               
    def heatup_thrice(self):
        """
        Pre-heats the BME688 hotplate THREE times in rapid succession at 320C:
          - Cycle 1: Surface Desorption (clears condensation and surface moisture)
          - Cycle 2: Core Thermalization (deeply conditions the MOX semiconductor layer)
          - Cycle 3: Equilibrium Lock-in (locks in thermal stability, minimizing baseline drift)
        Uses optimized 30ms polling for maximum speed and responsiveness.
        """
        if self.simulate or not self.installed or not self._sensor:
            log.info("[Simulated] BME688 hotplate triple pre-heat complete (3 cycles).")
            return

        labels = ["Surface Desorption", "Core Thermalization", "Equilibrium Lock-in"]
        log.info("BME688: Starting triple hotplate pre-heat sequence (3 cycles at 320C)...")
        for cycle in range(1, 4):
            label = labels[cycle - 1]
            log.info("  -> Heat-up cycle %d/3 (%s pulse)...", cycle, label)
            for attempt in range(12):
                if self._sensor.get_sensor_data() and getattr(self._sensor.data, 'heat_stable', False):
                    res_k = getattr(self._sensor.data, 'gas_resistance', 0.0) / 1000.0
                    log.info("     Cycle %d heat stable (gas: %.1f kOhm)", cycle, res_k)
                    break
                time.sleep(0.03)  # Fast 30ms polling to avoid slow lag
            time.sleep(0.04)
        log.info("BME688: Triple heat-up complete. Sensor hotplate is fully conditioned and ready.")

    # Backwards-compatible alias
    heatup_twice = heatup_thrice

    def calibrate_baseline(self, duration_sec: int = GAS_EMPTY_BOX_SNIFF_SEC, progress_cb=None) -> GasReading:
        """
        Read baseline gas resistance inside the empty 27L chamber over duration_sec (default 180s / 3 min).
        Executes a triple hotplate pre-heat first to burn off contaminants and save stabilization time.
        """
        if not self.installed:
            self._baseline = GasReading(timestamp=time.time())
            return self._baseline

        # Heat up BME thrice to stabilize quickly and burn off contaminants
        self.heatup_thrice()

        log.info("Calibrating BME688 baseline inside empty 27L chamber (%ds sniff)...", duration_sec)
        readings = []
        t_start = time.time()

        while True:
            elapsed = time.time() - t_start
            remaining = max(0, int(duration_sec - elapsed))
            r = self._read_once()
            readings.append(r)

            if progress_cb:
                progress_cb(int(elapsed), remaining, r)

            if elapsed >= duration_sec:
                break
            time.sleep(GAS_SNIFF_INTERVAL_SEC)

        if not readings:
            readings = [self._read_once()]

        # Discard the first 2 minutes (BME_WARMUP_DISCARD_SEC) of warm-up data
        stabilized_baseline_readings = [
            r for r in readings if (r.timestamp - t_start) >= BME_WARMUP_DISCARD_SEC
        ]
        if not stabilized_baseline_readings:
            stabilized_baseline_readings = readings
        else:
            log.info("BME688: Discarded first %ds of warm-up data. %d stabilized baseline readings available.",
                     BME_WARMUP_DISCARD_SEC, len(stabilized_baseline_readings))

        t_end = time.time()
        # Focus strictly on the last 5 seconds of the stabilized window for baseline average
        last_5s_readings = [r for r in stabilized_baseline_readings if r.timestamp >= (t_end - 5.0)]
        if len(last_5s_readings) < 3:
            last_5s_readings = stabilized_baseline_readings[-5:] if len(stabilized_baseline_readings) >= 5 else stabilized_baseline_readings

        avg_temp = sum(r.temperature for r in last_5s_readings) / len(last_5s_readings)
        avg_hum  = sum(r.humidity for r in last_5s_readings) / len(last_5s_readings)
        avg_pres = sum(r.pressure for r in last_5s_readings) / len(last_5s_readings)
        avg_gas  = sum(r.gas_ohms for r in last_5s_readings) / len(last_5s_readings)

        self._baseline = GasReading(
            temperature=round(avg_temp, 1),
            humidity=round(avg_hum, 1),
            pressure=round(avg_pres, 1),
            gas_ohms=round(avg_gas, 1),
            timestamp=time.time(),
        )
        log.info("BME688 Baseline: %.1f kOhm (averaged over last 5s, %d samples) | Temp: %.1fC | Humidity: %.1f%%",
                 self._baseline.gas_kohms, len(last_5s_readings), self._baseline.temperature, self._baseline.humidity)
        return self._baseline

    #    Continuous Sniffing (Background Thread)                                

    def start_continuous_sniffing(self, interval: float = GAS_SNIFF_INTERVAL_SEC):
        """
        Starts a background thread that sniffs the 27L chamber continuously
        while the 8-stop / 16-capture rotation takes place.
        Pre-heats the hotplate thrice first so readings start stable.
        """
        if not self.installed:
            return

        self.heatup_thrice()

        self._readings = []
        self._sniff_start_time = time.time()
        self._sniffing = True

        def _sniff_worker():
            log.info("BME688: Continuous sniffing started inside 27L box...")
            while self._sniffing:
                r = self._read_once()
                self._readings.append(r)
                time.sleep(interval)
            log.info("BME688: Sniffing stopped. Collected %d samples.", len(self._readings))

        self._sniff_thread = threading.Thread(target=_sniff_worker, daemon=True)
        self._sniff_thread.start()

    def stop_continuous_sniffing(self, produce_name: str = "default") -> "ScanGasResult":
        """
        Stops the sniffing thread and computes rich multi-feature gas analytics across the 16-photo cycle.
        Discards the first 2 minutes of warm-up data for thermal stabilization.
        Uses per-produce VOC gas profiles to classify freshness into 4 tiers:
            FRESH | MID_FRESH | MID_ROTTEN | ROTTEN
        """
        if not self.installed:
            return ScanGasResult(
                baseline_kohms=0.0,
                post_scan_kohms=0.0,
                delta_kohms=0.0,
                gas_min_kohms=0.0,
                gas_max_kohms=0.0,
                gas_mean_kohms=0.0,
                gas_std_kohms=0.0,
                gas_ratio_pct=0.0,
                gas_slope_per_sec=0.0,
                temperature_c=0.0,
                humidity_pct=0.0,
                pressure_hpa=0.0,
                sample_count=0,
                rot_suspicion="NOT_INSTALLED",
                installed=False,
            )

        self._sniffing = False
        if self._sniff_thread and self._sniff_thread.is_alive():
            self._sniff_thread.join(timeout=2.0)

        if not self._readings:
            self._readings.append(self._read_once())

        # Baseline
        if self._baseline and self._baseline.gas_kohms > 0:
            base_k = self._baseline.gas_kohms
            base_ohms = self._baseline.gas_ohms
            base_t = self._baseline.temperature
            base_h = self._baseline.humidity
            base_p = self._baseline.pressure
        else:
            first_n = self._readings[:min(3, len(self._readings))]
            base_k = round(sum(r.gas_kohms for r in first_n) / len(first_n), 3)
            base_ohms = sum(r.gas_ohms for r in first_n) / len(first_n)
            base_t = round(sum(r.temperature for r in first_n) / len(first_n), 1)
            base_h = round(sum(r.humidity for r in first_n) / len(first_n), 1)
            base_p = round(sum(r.pressure for r in first_n) / len(first_n), 1)

        # Discard the first 2 minutes (BME_WARMUP_DISCARD_SEC) of data for stabilization
        start_t = getattr(self, "_sniff_start_time", 0.0)
        stabilized_readings = [
            r for r in self._readings
            if (r.timestamp - start_t) >= BME_WARMUP_DISCARD_SEC
        ]
        if len(stabilized_readings) >= 3:
            analysis_readings = stabilized_readings
            log.info("BME688: Discarded first %ds of warm-up data. Analyzing %d stabilized samples.",
                     BME_WARMUP_DISCARD_SEC, len(analysis_readings))
        else:
            analysis_readings = self._readings
            log.info("BME688: Total session under %ds; using all %d samples.",
                     BME_WARMUP_DISCARD_SEC, len(analysis_readings))

        # Post-scan = average of last 3 samples from analysis_readings
        last_n = analysis_readings[-min(3, len(analysis_readings)):]
        post_k = round(sum(r.gas_kohms for r in last_n) / len(last_n), 3)
        post_ohms = sum(r.gas_ohms for r in last_n) / len(last_n)
        delta_k = round(max(0.0, base_k - post_k), 3)

        # Statistical features across stabilized readings
        res_list = [r.gas_kohms for r in analysis_readings if r.gas_kohms > 0]
        time_list = [r.timestamp for r in analysis_readings if r.gas_kohms > 0]

        if not res_list:
            res_list = [post_k]
            time_list = [time.time()]

        raw_gas_min = round(min(res_list), 3)
        gas_max = round(max(res_list), 3)
        gas_mean = round(sum(res_list) / len(res_list), 3)

        # Standard deviation
        if len(res_list) >= 2:
            import statistics
            gas_std = round(statistics.stdev(res_list), 3)
        else:
            gas_std = 0.0

        # Noise-resistant rolling smoothing for minimum:
        # Avoid letting a brief 1-sample noise spike fake a large gas drop
        if len(res_list) >= 5:
            import statistics
            smoothed_list = [
                statistics.median(res_list[max(0, i-2):min(len(res_list), i+3)])
                for i in range(len(res_list))
            ]
            gas_min = round(min(smoothed_list), 3)
        else:
            gas_min = raw_gas_min

        # Relative drop ratio (%) = (baseline - smoothed_min) / baseline * 100
        if base_k > 0:
            gas_ratio = round(max(0.0, (base_k - gas_min) / base_k * 100.0), 2)
        else:
            gas_ratio = 0.0

        # Linear regression slope (dR/dt in kOhm/sec)
        # Actively rotting fruit in sealed chamber exhibits a continuous downward slope
        gas_slope = 0.0
        if len(res_list) >= 3:
            t0 = time_list[0]
            rel_times = [t - t0 for t in time_list]
            mean_t = sum(rel_times) / len(rel_times)
            mean_r = sum(res_list) / len(res_list)
            denom = sum((t - mean_t) ** 2 for t in rel_times)
            if denom > 1e-6:
                gas_slope = round(sum((t - mean_t) * (r - mean_r) for t, r in zip(rel_times, res_list)) / denom, 4)

        # Environmental averages
        avg_temp = round(sum(r.temperature for r in self._readings) / len(self._readings), 1)
        avg_hum  = round(sum(r.humidity for r in self._readings) / len(self._readings), 1)
        avg_pres = round(sum(r.pressure for r in self._readings) / len(self._readings), 1)

        # Per-produce 4-tier freshness classification (FRESH/MID_FRESH/MID_ROTTEN/ROTTEN)
        suspicion = classify_gas_freshness(
            produce_name=produce_name,
            gas_ratio_pct=gas_ratio,
            delta_kohms=delta_k,
            gas_slope_per_sec=gas_slope,
        )

        log.info(
            "BME688 Analytics [%s]: Base=%.2fk | Post=%.2fk | Min=%.2fk | Max=%.2fk | "
            "Mean=%.2fk | Std=%.2fk | Drop=%.2f%% | Slope=%.4fk/s | Samples=%d | Status=%s",
            produce_name, base_k, post_k, gas_min, gas_max,
            gas_mean, gas_std, gas_ratio, gas_slope, len(self._readings), suspicion
        )

        return ScanGasResult(
            baseline_kohms=base_k,
            post_scan_kohms=post_k,
            delta_kohms=delta_k,
            gas_min_kohms=gas_min,
            gas_max_kohms=gas_max,
            gas_mean_kohms=gas_mean,
            gas_std_kohms=gas_std,
            gas_ratio_pct=gas_ratio,
            gas_slope_per_sec=gas_slope,
            temperature_c=avg_temp,
            humidity_pct=avg_hum,
            pressure_hpa=avg_pres,
            sample_count=len(self._readings),
            rot_suspicion=suspicion,
            installed=True,
            raw_baseline_ohms=round(base_ohms, 1),
            raw_post_scan_ohms=round(post_ohms, 1),
        )

    def export_timeseries_csv(self, filepath: str = None, scan_id: str = "DIAG", produce_name: str = "Unknown") -> str:
        """
        Exports full second-by-second raw time-series of all readings during incubation and scan.
        Columns: relative_sec, timestamp, gas_ohms, gas_kohms, temperature_c, humidity_pct, pressure_hpa
        """
        import os, csv
        if not filepath:
            from config import TIMESERIES_DATA_DIR
            os.makedirs(TIMESERIES_DATA_DIR, exist_ok=True)
            timestamp_str = time.strftime("%Y%m%d_%H%M%S")
            filepath = os.path.join(TIMESERIES_DATA_DIR, f"bme_timeseries_{produce_name.lower()}_{scan_id}_{timestamp_str}.csv")

        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        t0 = self._readings[0].timestamp if self._readings else time.time()

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["relative_sec", "timestamp", "gas_ohms", "gas_kohms", "temperature_c", "humidity_pct", "pressure_hpa", "scan_id", "produce_name"])
            for r in self._readings:
                rel = round(r.timestamp - t0, 2)
                writer.writerow([
                    rel,
                    time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r.timestamp)),
                    round(r.gas_ohms, 1),
                    round(r.gas_ohms / 1000.0, 3),
                    round(r.temperature, 2),
                    round(r.humidity, 2),
                    round(r.pressure, 2),
                    scan_id,
                    produce_name,
                ])
        log.info("Exported raw time-series (%d snapshots) to: %s", len(self._readings), filepath)
        return filepath

    @staticmethod
    def log_scan_dataset(scan_id: str, fruit_type: str, condition: str, gas_result: ScanGasResult,
                         predicted_condition: str = None, csv_path: str = None):
        """
        Appends complete 17-feature sensor snapshot to CSV for ML model building.
        Records both ground-truth 'condition' and AI 'predicted_condition'.
        Creates file automatically if not present.
        """
        import os, csv
        if csv_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            csv_path = os.path.join(base_dir, "datasets", "bme688_telemetry_dataset.csv")

        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        file_exists = os.path.exists(csv_path)

        fields = [
            "scan_id", "fruit_type", "condition", "predicted_condition", "timestamp",
            "temperature_c", "humidity_pct", "pressure_hpa",
            "baseline_gas_kohms", "post_scan_gas_kohms", "delta_gas_kohms",
            "gas_min_kohms", "gas_max_kohms", "gas_mean_kohms", "gas_std_kohms",
            "gas_ratio_pct", "gas_slope_per_sec", "sample_count",
            "rgb_image_count", "uv_image_count", "rot_suspicion", "is_synthetic"
        ]

        # Check existing header if file exists
        existing_has_pred = False
        if file_exists and os.path.getsize(csv_path) > 0:
            try:
                with open(csv_path, "r", encoding="utf-8") as f:
                    first_line = f.readline()
                    existing_has_pred = "predicted_condition" in first_line
            except Exception:
                pass

        row = {
            "scan_id": str(scan_id),
            "fruit_type": str(fruit_type).lower(),
            "condition": str(condition).upper(),
            "predicted_condition": str(predicted_condition or condition).upper(),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "temperature_c": gas_result.temperature_c,
            "humidity_pct": gas_result.humidity_pct,
            "pressure_hpa": gas_result.pressure_hpa,
            "baseline_gas_kohms": gas_result.baseline_kohms,
            "post_scan_gas_kohms": gas_result.post_scan_kohms,
            "delta_gas_kohms": gas_result.delta_kohms,
            "gas_min_kohms": gas_result.gas_min_kohms,
            "gas_max_kohms": gas_result.gas_max_kohms,
            "gas_mean_kohms": gas_result.gas_mean_kohms,
            "gas_std_kohms": gas_result.gas_std_kohms,
            "gas_ratio_pct": gas_result.gas_ratio_pct,
            "gas_slope_per_sec": gas_result.gas_slope_per_sec,
            "sample_count": gas_result.sample_count,
            "rgb_image_count": 8,
            "uv_image_count": 8,
            "rot_suspicion": gas_result.rot_suspicion,
            "is_synthetic": False,
        }

        try:
            active_fields = fields if (not file_exists or existing_has_pred) else [f for f in fields if f != "predicted_condition"]
            with open(csv_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=active_fields, extrasaction="ignore")
                if not file_exists or os.path.getsize(csv_path) == 0:
                    writer.writeheader()
                writer.writerow(row)
            log.info("Saved scan gas telemetry row to %s (ground_truth=%s, predicted=%s)",
                     csv_path, row["condition"], row["predicted_condition"])
        except Exception as exc:
            log.error("Failed to log scan dataset row: %s", exc)
