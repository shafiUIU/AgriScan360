"""
train_bme_only.py -- Standalone BME688 Gas Sensor Data Collector & Personal Model Trainer
===========================================================================================
Allows you to use ONLY the BME688 gas sensor (without running motors, LEDs, or cameras)
to collect chamber baseline and produce telemetry data, and train your personal models.

Supported Actions:
  --- LIVE BME-ONLY DATA COLLECTION (No Motor / No LEDs / No Camera) ---
  1. Collect Empty Closed Box Baseline (Chamber calibration data)
  2. Collect Produce Gas Telemetry (Tomato / Apple / Eggplant with ground-truth condition)

  --- PERSONAL MACHINE LEARNING TRAINING ---
  3. Train Empty Closed Box Baseline Profile (IsolationForest anomaly detector)
  4. Train Tomato Freshness Model (Random Forest 4-tier classifier)
  5. Train Apple Freshness Model (Random Forest 4-tier classifier)
  6. Train Eggplant Freshness Model (Random Forest 4-tier classifier)
  7. Train Unified Freshness Model (All produce combined)

  --- DATASET UTILITIES ---
  8. View Dataset Statistics (Samples per class & readiness)
  9. Generate Synthetic Mock Dataset (For pipeline verification)
"""

import os
import sys
import time
import argparse
import logging
import pickle
from datetime import datetime

import numpy as np
import pandas as pd

# Add pi_client to path to reuse BME688 hardware driver
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PI_CLIENT_DIR = os.path.join(ROOT, "pi_client")
if PI_CLIENT_DIR not in sys.path:
    sys.path.insert(0, PI_CLIENT_DIR)

try:
    from gas_sensor import GasSensor, ScanGasResult
except ImportError:
    GasSensor = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("train_bme")

DEFAULT_CSV = os.path.join(ROOT, "datasets", "bme688_telemetry_dataset.csv")
MODEL_DIR = os.path.join(ROOT, "laptop_server", "models")

FEATURE_COLUMNS = [
    "gas_ratio_pct",
    "delta_gas_kohms",
    "gas_slope_per_sec",
    "gas_min_kohms",
    "gas_mean_kohms",
    "gas_std_kohms",
    "temperature_c",
    "humidity_pct",
]


# =============================================================================
# PART 1: LIVE BME-ONLY DATA COLLECTION (No Motors, No LEDs, No Camera)
# =============================================================================

def collect_empty_box_data(csv_path: str, duration_sec: int = 300, simulate: bool = False):
    """
    Collects clean-air baseline data inside the sealed, empty 27L box.
    Operates the BME688 sensor ONLY -- turntable motor and LEDs remain OFF.
    """
    if GasSensor is None:
        log.error("Could not import GasSensor from pi_client/gas_sensor.py")
        return

    print("\n" + "=" * 64)
    print("  COLLECT EMPTY CLOSED BOX BME BASELINE DATA (No Motors / No LEDs)")
    print("=" * 64)
    print("  Chamber Volume   : 27.0 Liters (Sealed Box)")
    print(f"  Collection Time  : {duration_sec} seconds ({duration_sec // 60}m {duration_sec % 60}s)")
    print(f"  Target CSV File  : {csv_path}")
    print("=" * 64)

    sensor = GasSensor(simulate=simulate)
    if not sensor.installed and not simulate:
        print("\n[!] ERROR: BME688 sensor not detected on I2C (0x77 or 0x76).")
        print("    Check wiring or use --simulate.")
        return

    print("\n[>] Step 1: Remove all produce. Clean the chamber.")
    print("[>] Step 2: Seal the box lid tightly.")
    try:
        input("    Press [Enter] to start clean-air calibration...")
    except (KeyboardInterrupt, EOFError):
        pass

    print("\n[>] Calibrating clean baseline (10 samples)...")
    baseline = sensor.calibrate_baseline()
    print(f"    Clean Baseline: {baseline.gas_kohms:.3f} kOhm ({int(baseline.gas_ohms)} Ohm) | "
          f"{baseline.temperature:.1f}C | {baseline.humidity:.1f}%RH")

    print(f"\n[>] Sniffing empty chamber continuously for {duration_sec}s...")
    sensor.start_continuous_sniffing()
    t_start = time.time()

    try:
        while True:
            elapsed = int(time.time() - t_start)
            remaining = max(0, duration_sec - elapsed)
            latest = sensor._readings[-1] if sensor._readings else None
            cur_k = f"{latest.gas_kohms:6.2f} kOhm ({int(latest.gas_ohms)} Ohm)" if latest else "measuring..."
            cur_t = f"{latest.temperature:.1f}C" if latest else "--"
            cur_h = f"{latest.humidity:.1f}%" if latest else "--"

            sys.stdout.write(f"\r    [Empty Box] {elapsed:3d}s / {duration_sec}s | Gas: {cur_k} | {cur_t} | {cur_h}  ")
            sys.stdout.flush()

            if remaining <= 0:
                break
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n[!] Collection halted early by operator.")

    gas_res = sensor.stop_continuous_sniffing(produce_name="empty_box")
    print("\n")

    # Save to telemetry dataset
    scan_id = f"EMPTY_{int(time.time())}"
    GasSensor.log_scan_dataset(
        scan_id=scan_id,
        fruit_type="empty_box",
        condition="EMPTY_BOX",
        predicted_condition="EMPTY_BOX",
        gas_result=gas_res,
        csv_path=csv_path,
    )

    # Export high-resolution time-series
    try:
        ts_path = sensor.export_timeseries_csv(scan_id=scan_id, produce_name="empty_box")
        print(f"[+] Raw time-series curve saved to: {ts_path}")
    except Exception as exc:
        log.warning("Could not export timeseries: %s", exc)

    print("\n" + "=" * 64)
    print("  EMPTY BOX CALIBRATION LOGGED SUCCESSFULLY")
    print("=" * 64)
    print(f"  Baseline Recorded : {gas_res.baseline_kohms:.3f} kOhm ({gas_res.raw_baseline_ohms:.0f} Ohm)")
    print(f"  Chamber Stability : +/- {gas_res.gas_std_kohms:.3f} kOhm (noise spread)")
    print(f"  Appended to       : {csv_path}")
    print("=" * 64 + "\n")


def collect_produce_gas_data(csv_path: str, produce_name: str = None,
                             condition: str = None, duration_sec: int = 300,
                             simulate: bool = False):
    """
    Collects gas accumulation data for a specific produce item in the 27L box.
    Operates BME688 ONLY -- motors, LEDs, and camera remain completely OFF.
    """
    if GasSensor is None:
        log.error("Could not import GasSensor from pi_client/gas_sensor.py")
        return

    # Select produce if not specified
    if not produce_name:
        print("\nSelect Produce:")
        print("  1. Tomato\n  2. Apple\n  3. Eggplant")
        try:
            p_sel = input("Enter selection [1-3] (Default 1 = Tomato): ").strip()
        except (KeyboardInterrupt, EOFError):
            p_sel = "1"
        mapping = {"1": "Tomato", "2": "Apple", "3": "Eggplant"}
        produce_name = mapping.get(p_sel, "Tomato")

    # Select ground-truth condition if not specified
    if not condition:
        print(f"\nSelect Known Condition of this {produce_name} for Ground Truth:")
        print("  1. FRESH      (firm, freshly bought, no decay)")
        print("  2. MID_FRESH  (ripe, slight softening, no mould)")
        print("  3. MID_ROTTEN (soft spots, browning, early spoilage)")
        print("  4. ROTTEN     (obvious decay, fungal odour, severe rot)")
        try:
            c_sel = input("Enter condition [1-4] (Default 1 = FRESH): ").strip()
        except (KeyboardInterrupt, EOFError):
            c_sel = "1"
        c_map = {"1": "FRESH", "2": "MID_FRESH", "3": "MID_ROTTEN", "4": "ROTTEN"}
        condition = c_map.get(c_sel, "FRESH")

    print("\n" + "=" * 64)
    print(f"  COLLECT {produce_name.upper()} GAS DATA (Condition: {condition})")
    print("  [Sensor Only -- Turntable Motor & LEDs Remain OFF]")
    print("=" * 64)
    print(f"  Chamber Volume   : 27.0 Liters (Sealed Box)")
    print(f"  Incubation Time  : {duration_sec} seconds ({duration_sec // 60}m {duration_sec % 60}s)")
    print(f"  Target CSV File  : {csv_path}")
    print("=" * 64)

    sensor = GasSensor(simulate=simulate)
    if not sensor.installed and not simulate:
        print("\n[!] ERROR: BME688 sensor not detected on I2C (0x77 or 0x76).")
        print("    Check wiring or use --simulate.")
        return

    print(f"\n[>] Step 1: Place {produce_name} inside the chamber.")
    print("[>] Step 2: Seal the box lid tightly.")
    try:
        input("    Press [Enter] to begin gas exposure logging...")
    except (KeyboardInterrupt, EOFError):
        pass

    print("\n[>] Measuring starting baseline...")
    baseline = sensor.calibrate_baseline()
    print(f"    Initial Resistance: {baseline.gas_kohms:.3f} kOhm ({int(baseline.gas_ohms)} Ohm) | "
          f"{baseline.temperature:.1f}C | {baseline.humidity:.1f}%RH")

    print(f"\n[>] Incubating chamber for {duration_sec}s with continuous sniffing...")
    sensor.start_continuous_sniffing()
    t_start = time.time()

    try:
        while True:
            elapsed = int(time.time() - t_start)
            remaining = max(0, duration_sec - elapsed)
            latest = sensor._readings[-1] if sensor._readings else None
            cur_k = f"{latest.gas_kohms:6.2f} kOhm ({int(latest.gas_ohms)} Ohm)" if latest else "measuring..."
            delta = (baseline.gas_kohms - latest.gas_kohms) if latest else 0.0
            ratio = (delta / baseline.gas_kohms * 100.0) if latest and baseline.gas_kohms > 0 else 0.0

            sys.stdout.write(
                f"\r    [{produce_name}] {elapsed:3d}s/{duration_sec}s | Gas: {cur_k} | "
                f"Drop: {ratio:+5.2f}% ({delta:+5.2f}k)  "
            )
            sys.stdout.flush()

            if remaining <= 0:
                break
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n[!] Exposure halted early by operator.")

    gas_res = sensor.stop_continuous_sniffing(produce_name=produce_name)
    print("\n")

    # Save to telemetry dataset
    scan_id = f"BME_{int(time.time())}"
    GasSensor.log_scan_dataset(
        scan_id=scan_id,
        fruit_type=produce_name,
        condition=condition,
        predicted_condition=gas_res.rot_suspicion,
        gas_result=gas_res,
        csv_path=csv_path,
    )

    # Export high-resolution time-series
    try:
        ts_path = sensor.export_timeseries_csv(scan_id=scan_id, produce_name=produce_name)
        print(f"[+] Raw time-series curve saved to: {ts_path}")
    except Exception as exc:
        log.warning("Could not export timeseries: %s", exc)

    print("\n" + "=" * 64)
    print("  SAMPLE LOGGED SUCCESSFULLY")
    print("=" * 64)
    print(f"  Produce & State   : {produce_name} -- [{condition}]")
    print(f"  Baseline -> Final : {gas_res.baseline_kohms:.2f} kOhm -> {gas_res.post_scan_kohms:.2f} kOhm")
    print(f"  Relative Drop     : {gas_res.gas_ratio_pct:.2f}% (Delta: {gas_res.delta_kohms:.2f} kOhm)")
    print(f"  Decay Rate (dR/dt): {gas_res.gas_slope_per_sec:+.4f} kOhm/s")
    print(f"  Appended to       : {csv_path}")
    print("=" * 64 + "\n")


# =============================================================================
# PART 2: MACHINE LEARNING MODEL TRAINING (Scikit-Learn)
# =============================================================================

def train_empty_box_baseline(csv_path: str):
    """
    Trains a statistical baseline model & clean-air anomaly detector
    specifically for the empty, sealed 27L containment box.
    """
    try:
        from sklearn.ensemble import IsolationForest
    except ImportError:
        log.error("scikit-learn is required. Run: pip install scikit-learn pandas numpy")
        return

    if not os.path.exists(csv_path) or os.path.getsize(csv_path) < 50:
        log.warning("Dataset CSV not found or empty at: %s", csv_path)
        log.info("Use Option 1 to collect empty box data, or Option 9 to generate test data.")
        return

    df = pd.read_csv(csv_path)
    df["fruit_type"] = df["fruit_type"].astype(str).str.lower().str.strip()
    df["condition"]  = df["condition"].astype(str).str.upper().str.strip()

    mask_empty = (df["fruit_type"] == "empty_box") | (df["condition"] == "EMPTY_BOX")
    df_empty = df[mask_empty]

    if len(df_empty) == 0:
        print("\n[!] No 'empty_box' recordings found in the dataset.")
        print("[!] Select Option 1 to collect empty box baseline data first.\n")
        return

    log.info("Found %d empty closed box baseline recordings.", len(df_empty))

    base_k = df_empty["baseline_gas_kohms"].dropna().values
    temps  = df_empty["temperature_c"].dropna().values
    hums   = df_empty["humidity_pct"].dropna().values

    mean_res = float(np.mean(base_k))
    std_res  = float(np.std(base_k)) if len(base_k) > 1 else 3.0
    min_res  = float(np.min(base_k))
    max_res  = float(np.max(base_k))
    mean_temp = float(np.mean(temps)) if len(temps) else 24.0
    mean_hum  = float(np.mean(hums))  if len(hums) else 60.0

    feature_matrix = df_empty[["baseline_gas_kohms", "temperature_c", "humidity_pct"]].fillna(0).values
    detector = IsolationForest(contamination=0.05, random_state=42)
    detector.fit(feature_matrix)

    os.makedirs(MODEL_DIR, exist_ok=True)
    model_path = os.path.join(MODEL_DIR, "bme_empty_box_model.pkl")

    profile_data = {
        "model_type":           "empty_box_chamber_baseline",
        "sample_count":         int(len(df_empty)),
        "mean_baseline_kohms":  round(mean_res, 2),
        "std_baseline_kohms":   round(std_res, 2),
        "min_clean_kohms":      round(min_res, 2),
        "max_clean_kohms":      round(max_res, 2),
        "mean_temperature_c":   round(mean_temp, 1),
        "mean_humidity_pct":    round(mean_hum, 1),
        "anomaly_detector":     detector,
    }

    with open(model_path, "wb") as f:
        pickle.dump(profile_data, f)

    print("\n" + "=" * 64)
    print("  EMPTY CLOSED BOX BME BASELINE PROFILE TRAINED")
    print("=" * 64)
    print(f"  Chamber Volume       : 27.0 Liters (Sealed Box)")
    print(f"  Calibration Samples  : {len(df_empty)} recordings")
    print(f"  Mean Clean Baseline  : {mean_res:.2f} kOhm  (+/- {std_res:.2f} kOhm)")
    print(f"  Normal Clean Range   : {max(0.0, mean_res - 2*std_res):.2f} kOhm - {mean_res + 2*std_res:.2f} kOhm")
    print(f"  Ambient Temp / RH    : {mean_temp:.1f}C  |  {mean_hum:.1f}% RH")
    print(f"  Clean-Air Anomaly ML : IsolationForest trained (Contamination=5%)")
    print(f"  Model Saved To       : {model_path}")
    print("=" * 64 + "\n")


def train_fruit_model(csv_path: str, fruit: str = None):
    """
    Trains a Random Forest freshness classifier for a specific fruit or unified produce.
    """
    try:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import classification_report
    except ImportError:
        log.error("scikit-learn is required. Run: pip install scikit-learn pandas numpy")
        return

    if not os.path.exists(csv_path) or os.path.getsize(csv_path) < 100:
        log.warning("Dataset CSV not found or empty at: %s", csv_path)
        log.info("Use Option 2 to collect produce data first.")
        return

    df = pd.read_csv(csv_path)
    df["condition"]  = df["condition"].astype(str).str.upper().str.strip()
    df["fruit_type"] = df["fruit_type"].astype(str).str.lower().str.strip()

    # Exclude empty box rows from fruit freshness training
    df = df[df["fruit_type"] != "empty_box"]
    df = df[df["condition"] != "EMPTY_BOX"]

    if fruit:
        fruit_clean = fruit.lower().strip()
        df = df[df["fruit_type"] == fruit_clean]
        if len(df) == 0:
            log.error("No samples found for fruit: '%s' in dataset.", fruit)
            return

    log.info("Loaded %d samples for training (Produce: %s)", len(df), (fruit or "ALL PRODUCE").title())
    class_counts = df["condition"].value_counts()
    print("\nClass distribution:")
    print(class_counts.to_string())

    if len(class_counts) < 2:
        log.error("At least 2 distinct condition classes required to train a classifier. Found: %d", len(class_counts))
        return

    available_feats = [c for c in FEATURE_COLUMNS if c in df.columns]
    X = df[available_feats].fillna(0)
    y = df["condition"]

    test_size = 0.2 if len(df) >= 20 else 0.1
    stratify = y if y.value_counts().min() >= 2 else None
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=42, stratify=stratify)

    model = RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42)
    model.fit(X_train, y_train)

    train_acc = model.score(X_train, y_train) * 100
    test_acc  = model.score(X_test, y_test) * 100

    print("\n" + "=" * 64)
    print(f"  BME688 Random Forest Model Results ({(fruit or 'Unified').title()})")
    print(f"  Training Accuracy : {train_acc:.1f}%")
    print(f"  Testing Accuracy  : {test_acc:.1f}%")
    print("=" * 64)

    y_pred = model.predict(X_test)
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, zero_division=0))

    importances = pd.Series(model.feature_importances_, index=available_feats).sort_values(ascending=False)
    print("Feature Importance:")
    for feat, imp in importances.items():
        print(f"  - {feat:<20}: {imp*100:5.1f}%")

    os.makedirs(MODEL_DIR, exist_ok=True)
    model_filename = f"bme_model_{fruit.lower()}.pkl" if fruit else "bme_model_unified.pkl"
    model_path = os.path.join(MODEL_DIR, model_filename)

    with open(model_path, "wb") as f:
        pickle.dump({"model": model, "features": available_feats, "classes": list(model.classes_)}, f)

    print("\n" + "=" * 64)
    print(f"  Successfully saved trained model to:")
    print(f"  {model_path}")
    print("=" * 64 + "\n")


# =============================================================================
# PART 3: DATASET STATS & MOCK GENERATOR
# =============================================================================

def view_dataset_stats(csv_path: str):
    """Display summary count of all collected samples in the dataset."""
    if not os.path.exists(csv_path) or os.path.getsize(csv_path) < 50:
        print(f"\n[!] Dataset file does not exist or is empty at:\n    {csv_path}")
        print("    Use Option 1 (Empty Box) or Option 2 (Produce) to start collecting data.")
        return

    df = pd.read_csv(csv_path)
    print("\n" + "=" * 64)
    print("  AGRISCAN 360 -- BME688 TELEMETRY DATASET SUMMARY")
    print("=" * 64)
    print(f"  Location     : {csv_path}")
    print(f"  Total Rows   : {len(df)}")

    # Real vs. Synthetic breakdown
    if "scan_id" in df.columns:
        is_mock = df["scan_id"].astype(str).str.startswith("MOCK")
        if "is_synthetic" in df.columns:
            is_mock = is_mock | df["is_synthetic"].astype(str).str.lower().isin(["true", "1"])
        synth_cnt = int(is_mock.sum())
        real_cnt = len(df) - synth_cnt
        print(f"  Real Scans   : {real_cnt} (from physical hardware)")
        print(f"  Synthetic    : {synth_cnt} (mock generated)")

    if "fruit_type" in df.columns:
        print("\n  Produce Breakdown:")
        f_counts = df["fruit_type"].str.lower().value_counts()
        for f, cnt in f_counts.items():
            print(f"    - {f:<15}: {cnt} samples")

    if "condition" in df.columns:
        print("\n  Condition Breakdown:")
        c_counts = df["condition"].str.upper().value_counts()
        for c, cnt in c_counts.items():
            print(f"    - {c:<15}: {cnt} samples")

    print("=" * 64 + "\n")


def purge_synthetic_data(csv_path: str):
    """
    Deletes all synthetic / mock data rows from the dataset CSV,
    preserving all real hardware scans.
    Identifies synthetic data by:
      1. is_synthetic == True
      2. scan_id starting with 'MOCK'
    """
    if not os.path.exists(csv_path) or os.path.getsize(csv_path) < 50:
        print(f"\n[!] Dataset file not found or empty at:\n    {csv_path}")
        return

    df = pd.read_csv(csv_path)
    total_before = len(df)

    is_mock_id = df["scan_id"].astype(str).str.startswith("MOCK")
    is_synth_col = df["is_synthetic"].astype(str).str.lower().isin(["true", "1"]) if "is_synthetic" in df.columns else False
    mask_synthetic = is_mock_id | is_synth_col

    synthetic_count = int(mask_synthetic.sum())
    if synthetic_count == 0:
        print("\n[+] No synthetic data found in the dataset. All rows are real scans!")
        return

    real_df = df[~mask_synthetic]
    real_count = len(real_df)

    real_df.to_csv(csv_path, index=False)

    print("\n" + "=" * 64)
    print("  SYNTHETIC DATA PURGE COMPLETE")
    print("=" * 64)
    print(f"  Dataset File       : {csv_path}")
    print(f"  Total Rows Before  : {total_before}")
    print(f"  Synthetic Removed  : {synthetic_count} (all MOCK_ rows deleted)")
    print(f"  Real Rows Kept     : {real_count}")
    print("=" * 64 + "\n")


def generate_mock_dataset(csv_path: str, count_per_class: int = 25):
    """Generates synthetic multi-produce telemetry data including empty box records."""
    np.random.seed(42)
    rows = []

    # 1. Empty closed box baseline recordings
    for i in range(count_per_class * 2):
        base_res = np.random.normal(198.0, 3.5)
        post_res = base_res + np.random.normal(0.0, 0.5)
        delta    = max(0.0, base_res - post_res)
        rows.append({
            "scan_id": f"MOCK_EMPTY_{i:04d}",
            "fruit_type": "empty_box",
            "condition": "EMPTY_BOX",
            "predicted_condition": "EMPTY_BOX",
            "timestamp": "2026-09-22 00:00:00",
            "temperature_c": round(np.random.uniform(22.0, 26.0), 1),
            "humidity_pct": round(np.random.uniform(55.0, 65.0), 1),
            "pressure_hpa": round(np.random.uniform(1011.0, 1014.0), 1),
            "baseline_gas_kohms": round(base_res, 2),
            "post_scan_gas_kohms": round(post_res, 2),
            "delta_gas_kohms": round(delta, 2),
            "gas_min_kohms": round(min(base_res, post_res), 2),
            "gas_max_kohms": round(max(base_res, post_res), 2),
            "gas_mean_kohms": round((base_res + post_res) / 2.0, 2),
            "gas_std_kohms": round(abs(np.random.normal(0.3, 0.1)), 2),
            "gas_ratio_pct": round(max(0.0, (base_res - post_res) / base_res * 100.0), 1),
            "gas_slope_per_sec": round(np.random.normal(0.0, 0.005), 4),
            "sample_count": 20,
            "rgb_image_count": 0,
            "uv_image_count": 0,
            "rot_suspicion": "EMPTY_BOX",
            "is_synthetic": True,
        })

    # 2. Fruit condition telemetry
    fruits = {
        "tomato":   {"FRESH": (2.0, 4.0),  "MID_FRESH": (6.0, 10.0),  "MID_ROTTEN": (12.0, 18.0), "ROTTEN": (20.0, 35.0)},
        "apple":    {"FRESH": (2.0, 5.0),  "MID_FRESH": (7.0, 12.0),  "MID_ROTTEN": (14.0, 22.0), "ROTTEN": (25.0, 45.0)},
        "eggplant": {"FRESH": (1.5, 3.5),  "MID_FRESH": (5.0, 9.0),   "MID_ROTTEN": (10.0, 16.0), "ROTTEN": (18.0, 30.0)},
    }

    for fruit, conditions in fruits.items():
        for cond, (min_drop, max_drop) in conditions.items():
            for _ in range(count_per_class):
                base_k = np.random.uniform(185.0, 215.0)
                ratio  = np.random.uniform(min_drop, max_drop)
                delta  = base_k * (ratio / 100.0)
                post_k = max(10.0, base_k - delta)
                slope  = -np.random.uniform(0.005, 0.15) if ratio > 10 else -np.random.uniform(0.0, 0.02)
                min_k  = post_k - np.random.uniform(0.5, 2.0)
                mean_k = (base_k + post_k) / 2.0
                std_k  = np.random.uniform(0.5, 3.5)

                rows.append({
                    "scan_id": f"MOCK_{len(rows):04d}",
                    "fruit_type": fruit,
                    "condition": cond,
                    "predicted_condition": cond,
                    "timestamp": "2026-09-22 00:00:00",
                    "temperature_c": round(np.random.uniform(22.0, 27.0), 1),
                    "humidity_pct": round(np.random.uniform(55.0, 75.0), 1),
                    "pressure_hpa": round(np.random.uniform(1010.0, 1015.0), 1),
                    "baseline_gas_kohms": round(base_k, 2),
                    "post_scan_gas_kohms": round(post_k, 2),
                    "delta_gas_kohms": round(delta, 2),
                    "gas_min_kohms": round(min_k, 2),
                    "gas_max_kohms": round(base_k, 2),
                    "gas_mean_kohms": round(mean_k, 2),
                    "gas_std_kohms": round(std_k, 2),
                    "gas_ratio_pct": round(ratio, 1),
                    "gas_slope_per_sec": round(slope, 4),
                    "sample_count": 16,
                    "rgb_image_count": 8,
                    "uv_image_count": 8,
                    "rot_suspicion": cond,
                    "is_synthetic": True,
                })

    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    df.to_csv(csv_path, index=False)
    log.info("Generated %d synthetic rows (including %d empty box baselines) in %s",
             len(df), count_per_class * 2, csv_path)


# =============================================================================
# PART 4: INTERACTIVE TERMINAL MENU & CLI
# =============================================================================

def show_interactive_menu() -> str:
    """Displays the master menu for data collection and model training."""
    print("\n+============================================================+")
    print("|   AgriScan 360 -- BME688 Standalone Suite & Trainer        |")
    print("+============================================================+")
    print("|  -- LIVE BME-ONLY DATA COLLECTION (No Motors / No LEDs) -- |")
    print("|  1. Collect Empty Closed Box Baseline (Clean chamber data) |")
    print("|  2. Collect Produce Gas Data (Tomato / Apple / Eggplant)   |")
    print("|                                                            |")
    print("|  -- MACHINE LEARNING MODEL TRAINING (Scikit-Learn) ------- |")
    print("|  3. Train Empty Closed Box Baseline Profile                |")
    print("|  4. Train Tomato Freshness Model                           |")
    print("|  5. Train Apple Freshness Model                            |")
    print("|  6. Train Eggplant Freshness Model                         |")
    print("|  7. Train Unified Freshness Model (All Fruits Combined)    |")
    print("|                                                            |")
    print("|  -- DATASET UTILITIES ------------------------------------ |")
    print("|  8. View Current Dataset Statistics (Real vs Synthetic)    |")
    print("|  9. Generate Synthetic Mock Dataset (Pipeline test)        |")
    print("|  10. Purge / Delete All Synthetic Mock Data from CSV       |")
    print("+============================================================+")
    try:
        choice = input("Select an option [1-10] (Default 1): ").strip()
        return choice or "1"
    except (KeyboardInterrupt, EOFError):
        return "1"


def main():
    parser = argparse.ArgumentParser(description="AgriScan 360 BME688 Standalone Sensor Suite & Trainer")
    parser.add_argument("--csv", type=str, default=DEFAULT_CSV, help="Path to telemetry CSV")
    parser.add_argument("--collect-empty", action="store_true", help="Collect empty box baseline data (no motors/LEDs)")
    parser.add_argument("--collect-fruit", action="store_true", help="Collect produce gas data (no motors/LEDs)")
    parser.add_argument("--fruit", type=str, default=None, help="Target fruit: tomato, apple, or eggplant")
    parser.add_argument("--condition", type=str, default=None, help="Condition: FRESH, MID_FRESH, MID_ROTTEN, ROTTEN")
    parser.add_argument("--duration", type=int, default=300, help="Incubation duration in seconds (default: 300s / 5 min)")
    parser.add_argument("--train-empty", action="store_true", help="Train empty closed box baseline profile")
    parser.add_argument("--train-fruit", action="store_true", help="Train fruit freshness model")
    parser.add_argument("--all", action="store_true", help="Train unified model across all produce")
    parser.add_argument("--stats", action="store_true", help="Display dataset statistics")
    parser.add_argument("--generate-mock-data", action="store_true", help="Generate synthetic test data")
    parser.add_argument("--purge-synthetic", action="store_true", help="Delete all synthetic/mock data from the CSV")
    parser.add_argument("--simulate", action="store_true", help="Run with simulated sensor (no physical hardware)")
    args = parser.parse_args()

    # CLI Direct Triggers
    if args.collect_empty:
        collect_empty_box_data(args.csv, duration_sec=args.duration, simulate=args.simulate)
        return
    elif args.collect_fruit:
        collect_produce_gas_data(args.csv, produce_name=args.fruit, condition=args.condition,
                                 duration_sec=args.duration, simulate=args.simulate)
        return
    elif args.train_empty:
        train_empty_box_baseline(args.csv)
        return
    elif args.train_fruit or args.all:
        train_fruit_model(args.csv, fruit=args.fruit)
        return
    elif args.stats:
        view_dataset_stats(args.csv)
        return
    elif args.generate_mock_data:
        generate_mock_dataset(args.csv)
        return
    elif args.purge_synthetic:
        purge_synthetic_data(args.csv)
        return

    # Interactive Menu
    choice = show_interactive_menu()

    if choice == "1":
        collect_empty_box_data(args.csv, duration_sec=args.duration, simulate=args.simulate)
    elif choice == "2":
        collect_produce_gas_data(args.csv, produce_name=args.fruit, condition=args.condition,
                                 duration_sec=args.duration, simulate=args.simulate)
    elif choice == "3":
        train_empty_box_baseline(args.csv)
    elif choice == "4":
        train_fruit_model(args.csv, fruit="tomato")
    elif choice == "5":
        train_fruit_model(args.csv, fruit="apple")
    elif choice == "6":
        train_fruit_model(args.csv, fruit="eggplant")
    elif choice == "7":
        train_fruit_model(args.csv, fruit=None)
    elif choice == "8":
        view_dataset_stats(args.csv)
    elif choice == "9":
        generate_mock_dataset(args.csv)
        print("\n[+] Synthetic data created. You can now inspect with Option 8 or train with Options 3-7!")
    elif choice == "10":
        purge_synthetic_data(args.csv)
    else:
        print("Invalid selection. Exiting.")


if __name__ == "__main__":
    main()
