"""
train_bme_only.py — Personal BME688 Gas Sensor Freshness & Chamber Baseline Trainer
=====================================================================================
Trains lightweight machine-learning models directly on your logged gas telemetry data
in datasets/bme688_telemetry_dataset.csv.

Supported Training Tasks:
  1. Train Empty Closed Box BME Data (Clean chamber headspace baseline & anomaly profile)
  2. Train Tomato BME Model (Random Forest freshness classifier)
  3. Train Apple BME Model (Random Forest freshness classifier)
  4. Train Eggplant BME Model (Random Forest freshness classifier)
  5. Train Unified BME Model (All produce combined)
  6. Generate Synthetic / Mock Data (For rapid pipeline verification)
"""

import os
import sys
import argparse
import logging
import pickle
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("train_bme")

DEFAULT_CSV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "datasets", "bme688_telemetry_dataset.csv")
MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "laptop_server", "models")

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


# ─────────────────────────────────────────────────────────────────────────────
# 1. EMPTY CLOSED BOX BME BASELINE TRAINER
# ─────────────────────────────────────────────────────────────────────────────

def train_empty_box_baseline(csv_path: str):
    """
    Trains a statistical baseline model & clean-air anomaly detector
    specifically for the empty, sealed 27L containment box.

    Learns:
      - Expected clean-air baseline resistance distribution (mean, variance)
      - Ambient temperature and humidity compensation
      - Anomaly detection boundary to flag chamber contamination (e.g. leftover rot fumes)
    """
    try:
        from sklearn.ensemble import IsolationForest
    except ImportError:
        log.error("scikit-learn is required. Run: pip install scikit-learn pandas numpy")
        return

    if not os.path.exists(csv_path) or os.path.getsize(csv_path) < 50:
        log.warning("Dataset CSV not found or empty at: %s", csv_path)
        log.info("Run scans in main.py Step A or select Option 6 to generate test data.")
        return

    df = pd.read_csv(csv_path)
    df["fruit_type"] = df["fruit_type"].astype(str).str.lower().str.strip()
    df["condition"]  = df["condition"].astype(str).str.upper().str.strip()

    # Filter for empty box recordings
    mask_empty = (df["fruit_type"] == "empty_box") | (df["condition"] == "EMPTY_BOX")
    df_empty = df[mask_empty]

    if len(df_empty) == 0:
        print("\n[!] No 'empty_box' recordings found in the dataset.")
        print("[!] To collect empty box data:")
        print("    1. Run 'python pi_client/main.py' and perform Step A with the box closed and empty.")
        print("    2. Or choose option 6 to generate synthetic test data.\n")
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

    # Train Isolation Forest on [baseline_gas_kohms, temperature_c, humidity_pct]
    feature_matrix = df_empty[["baseline_gas_kohms", "temperature_c", "humidity_pct"]].fillna(0).values
    detector = IsolationForest(contamination=0.05, random_state=42)
    detector.fit(feature_matrix)

    # Save baseline model artifact
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

    print("\n" + "=" * 62)
    print("  EMPTY CLOSED BOX BME BASELINE PROFILE TRAINED")
    print("=" * 62)
    print(f"  Chamber Volume       : 27.0 Liters (Sealed Box)")
    print(f"  Calibration Samples  : {len(df_empty)} recordings")
    print(f"  Mean Clean Baseline  : {mean_res:.2f} kOhm  (+/- {std_res:.2f} kOhm)")
    print(f"  Normal Clean Range   : {max(0.0, mean_res - 2*std_res):.2f} kOhm - {mean_res + 2*std_res:.2f} kOhm")
    print(f"  Ambient Temp / RH    : {mean_temp:.1f}C  |  {mean_hum:.1f}% RH")
    print(f"  Clean-Air Anomaly ML : IsolationForest trained (Contamination=5%)")
    print(f"  Model Saved To       : {model_path}")
    print("=" * 62)
    print("  -> System can now verify if the empty chamber is genuinely clean")
    print("     before starting fruit decay analysis.")
    print("=" * 62 + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# 2. PRODUCE FRESHNESS MODEL TRAINER (Random Forest)
# ─────────────────────────────────────────────────────────────────────────────

def train_fruit_model(csv_path: str, fruit: str = None):
    try:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import classification_report
    except ImportError:
        log.error("scikit-learn is required. Run: pip install scikit-learn pandas numpy")
        return

    if not os.path.exists(csv_path) or os.path.getsize(csv_path) < 100:
        log.warning("Dataset CSV not found or empty at: %s", csv_path)
        log.info("Use Option 6 to generate test data, or perform scans in main.py first.")
        return

    df = pd.read_csv(csv_path)
    df["condition"]  = df["condition"].astype(str).str.upper().str.strip()
    df["fruit_type"] = df["fruit_type"].astype(str).str.lower().str.strip()

    # Filter out empty_box calibration records for fruit freshness training
    df = df[df["fruit_type"] != "empty_box"]
    df = df[df["condition"] != "EMPTY_BOX"]

    # Filter by fruit if specified
    if fruit:
        fruit_clean = fruit.lower().strip()
        df = df[df["fruit_type"] == fruit_clean]
        if len(df) == 0:
            log.error("No samples found for fruit: '%s' in dataset.", fruit)
            return

    log.info("Loaded %d samples for training (Fruit: %s)", len(df), fruit or "ALL PRODUCE")
    class_counts = df["condition"].value_counts()
    print("\nClass distribution:")
    print(class_counts.to_string())

    if len(class_counts) < 2:
        log.error("At least 2 distinct classes required to train a classifier. Found: %d", len(class_counts))
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

    print("\n" + "=" * 62)
    print(f"  BME688 Random Forest Model Results ({fruit or 'Unified'})")
    print(f"  Training Accuracy : {train_acc:.1f}%")
    print(f"  Testing Accuracy  : {test_acc:.1f}%")
    print("=" * 62)

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

    print("\n" + "=" * 62)
    print(f"  Successfully saved trained model to:")
    print(f"  {model_path}")
    print("=" * 62 + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# 3. SYNTHETIC DATA GENERATOR (With Empty Box Baselines)
# ─────────────────────────────────────────────────────────────────────────────

def generate_mock_dataset(csv_path: str, count_per_class: int = 25):
    """
    Generate realistic synthetic training data including both empty closed box
    readings and fruit rot progressions.
    """
    fruits = ["tomato", "apple", "eggplant"]
    classes = ["FRESH", "MID_FRESH", "MID_ROTTEN", "ROTTEN"]
    rows = []

    # 1. Generate Empty Closed Box baseline samples
    for i in range(count_per_class * 2):
        base_k = np.random.uniform(65.0, 95.0)
        temp   = np.random.uniform(22.0, 26.5)
        hum    = np.random.uniform(50.0, 68.0)
        rows.append({
            "scan_id": f"BASE_MOCK_{i:04d}",
            "fruit_type": "empty_box",
            "condition": "EMPTY_BOX",
            "predicted_condition": "EMPTY_BOX",
            "timestamp": "2026-09-22 00:00:00",
            "temperature_c": round(temp, 1),
            "humidity_pct": round(hum, 1),
            "pressure_hpa": round(np.random.uniform(1011.0, 1014.0), 1),
            "baseline_gas_kohms": round(base_k, 2),
            "post_scan_gas_kohms": round(base_k, 2),
            "delta_gas_kohms": 0.0,
            "gas_min_kohms": round(base_k - 0.2, 2),
            "gas_max_kohms": round(base_k + 0.2, 2),
            "gas_mean_kohms": round(base_k, 2),
            "gas_std_kohms": round(np.random.uniform(0.1, 0.4), 2),
            "gas_ratio_pct": 0.0,
            "gas_slope_per_sec": round(np.random.uniform(-0.005, 0.005), 4),
            "sample_count": 1,
            "rgb_image_count": 0,
            "uv_image_count": 0,
            "rot_suspicion": "EMPTY_BOX",
        })

    # 2. Generate Fruit samples across freshness stages
    for fruit in fruits:
        for cond in classes:
            for i in range(count_per_class):
                if cond == "FRESH":
                    base_k = np.random.uniform(50.0, 90.0)
                    ratio  = np.random.uniform(1.0, 7.0)
                    slope  = np.random.uniform(-0.02, 0.01)
                    delta  = base_k * (ratio / 100.0)
                elif cond == "MID_FRESH":
                    base_k = np.random.uniform(45.0, 85.0)
                    ratio  = np.random.uniform(7.0, 15.0)
                    slope  = np.random.uniform(-0.06, -0.01)
                    delta  = base_k * (ratio / 100.0)
                elif cond == "MID_ROTTEN":
                    base_k = np.random.uniform(40.0, 80.0)
                    ratio  = np.random.uniform(15.0, 26.0)
                    slope  = np.random.uniform(-0.14, -0.05)
                    delta  = base_k * (ratio / 100.0)
                else:  # ROTTEN
                    base_k = np.random.uniform(35.0, 75.0)
                    ratio  = np.random.uniform(25.0, 50.0)
                    slope  = np.random.uniform(-0.35, -0.12)
                    delta  = base_k * (ratio / 100.0)

                post_k = base_k - delta
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
                })

    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    df.to_csv(csv_path, index=False)
    log.info("Generated %d synthetic rows (including %d empty box baselines) in %s",
             len(df), count_per_class * 2, csv_path)


# ─────────────────────────────────────────────────────────────────────────────
# 4. INTERACTIVE MENU & CLI ENTRYPOINT
# ─────────────────────────────────────────────────────────────────────────────

def show_interactive_menu() -> str:
    """Print the selection menu at the beginning of the terminal."""
    print("\n+============================================================+")
    print("|   AgriScan 360 -- BME688 Gas Sensor Training Suite         |")
    print("+============================================================+")
    print("|  1. Train Empty Closed Box BME Data (Chamber Baseline)     |")
    print("|  2. Train Tomato BME Model                                 |")
    print("|  3. Train Apple BME Model                                  |")
    print("|  4. Train Eggplant BME Model                               |")
    print("|  5. Train Unified BME Model (All Fruits Combined)          |")
    print("|  6. Generate Synthetic Test Data (Fruits + Empty Box)      |")
    print("+============================================================+")
    try:
        choice = input("Select an option [1-6] (Default 1 = Empty Box): ").strip()
        return choice or "1"
    except (KeyboardInterrupt, EOFError):
        return "1"


def main():
    parser = argparse.ArgumentParser(description="Train personal BME688 gas freshness and chamber baseline models")
    parser.add_argument("--csv", type=str, default=DEFAULT_CSV, help="Path to telemetry CSV")
    parser.add_argument("--empty-box", action="store_true", help="Train empty closed box chamber baseline model")
    parser.add_argument("--fruit", type=str, default=None, help="Target fruit: tomato, apple, or eggplant")
    parser.add_argument("--all", action="store_true", help="Train unified model across all produce")
    parser.add_argument("--generate-mock-data", action="store_true", help="Generate synthetic test data")
    parser.add_argument("--count", type=int, default=25, help="Samples per class for mock data")
    args = parser.parse_args()

    # If any specific CLI flag is provided, execute directly
    if args.generate_mock_data:
        generate_mock_dataset(args.csv, count_per_class=args.count)
        return
    elif args.empty_box:
        train_empty_box_baseline(args.csv)
        return
    elif args.fruit or args.all:
        train_fruit_model(args.csv, fruit=args.fruit)
        return

    # Otherwise, present the interactive menu at the beginning of the terminal
    choice = show_interactive_menu()

    if choice == "1":
        train_empty_box_baseline(args.csv)
    elif choice == "2":
        train_fruit_model(args.csv, fruit="tomato")
    elif choice == "3":
        train_fruit_model(args.csv, fruit="apple")
    elif choice == "4":
        train_fruit_model(args.csv, fruit="eggplant")
    elif choice == "5":
        train_fruit_model(args.csv, fruit=None)
    elif choice == "6":
        generate_mock_dataset(args.csv, count_per_class=args.count)
        print("\n[+] Synthetic data created. You can now train Option 1 or Options 2-5!")
    else:
        print("Invalid selection. Exiting.")


if __name__ == "__main__":
    main()
