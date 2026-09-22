"""
tools/export_training_data.py  —  AgriScan 360 Training Data Exporter
=======================================================================
Exports ALL scan telemetry from the laptop's SQLite database to a CSV
file that 'training/train_bme_only.py' can directly read.

Run this ON YOUR LAPTOP (not on the Pi) after collecting scans.

Usage:
    python tools/export_training_data.py
    python tools/export_training_data.py --out datasets/my_export.csv
    python tools/export_training_data.py --stats          # print summary only
    python tools/export_training_data.py --only-labelled  # skip rows without ground truth
"""

import os
import sys
import sqlite3
import csv
import argparse
from datetime import datetime

# ── Paths ─────────────────────────────────────────────────────────────────────
HERE       = os.path.dirname(os.path.abspath(__file__))
ROOT       = os.path.dirname(HERE)
DB_PATH    = os.path.join(ROOT, "laptop_server", "db", "agriscan360.db")
DEFAULT_OUT = os.path.join(ROOT, "datasets", "bme688_telemetry_dataset.csv")

# ── CSV column order (matches what train_bme_only.py expects) ─────────────────
FIELDNAMES = [
    "scan_id",
    "fruit_type",
    "condition",          # ground_truth if available, else status
    "predicted_condition", # AI's original prediction (status)
    "timestamp",
    "temperature_c",
    "humidity_pct",
    "pressure_hpa",
    "baseline_gas_kohms",
    "post_scan_gas_kohms",
    "delta_gas_kohms",
    "gas_min_kohms",
    "gas_max_kohms",
    "gas_mean_kohms",
    "gas_std_kohms",
    "gas_ratio_pct",
    "gas_slope_per_sec",
    "sample_count",
    "rgb_image_count",
    "uv_image_count",
    "rot_suspicion",
    "is_synthetic",
]


def export(db_path: str, out_path: str, only_labelled: bool = False, stats_only: bool = False):
    if not os.path.exists(db_path):
        print(f"[!] Database not found at: {db_path}")
        print("    Make sure the laptop server has been run at least once.")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Pull all scan rows with gas analytics
    query = """
        SELECT
            id,
            produce_name,
            status,
            ground_truth,
            gas_delta,
            baseline_gas_kohms,
            post_scan_gas_kohms,
            gas_min_kohms,
            gas_max_kohms,
            gas_mean_kohms,
            gas_std_kohms,
            gas_ratio_pct,
            gas_slope_per_sec,
            sample_count,
            rot_suspicion,
            temperature_c,
            humidity_pct,
            pressure_hpa,
            created_at
        FROM scans
        WHERE status NOT IN ('PENDING', 'ERROR', 'CANCELLED')
        ORDER BY id ASC
    """
    cur.execute(query)
    rows = cur.fetchall()
    conn.close()

    total = len(rows)
    labelled = sum(1 for r in rows if r["ground_truth"] and r["ground_truth"].strip())
    unlabelled = total - labelled

    # Count images per scan from scan_images table
    conn2 = sqlite3.connect(db_path)
    conn2.row_factory = sqlite3.Row
    cur2 = conn2.cursor()
    cur2.execute("SELECT scan_id, light_type, COUNT(*) as cnt FROM scan_images GROUP BY scan_id, light_type")
    img_counts = {}
    for irow in cur2.fetchall():
        sid = irow["scan_id"]
        if sid not in img_counts:
            img_counts[sid] = {"rgb": 0, "uv": 0}
        img_counts[sid][irow["light_type"]] = irow["cnt"]
    conn2.close()

    # ── Stats summary ──────────────────────────────────────────────────────────
    print("\n" + "=" * 62)
    print("  AgriScan 360 — Training Data Export Summary")
    print("=" * 62)
    print(f"  Database          : {db_path}")
    print(f"  Total Scans       : {total}")
    print(f"  Ground-Truth Set  : {labelled}  (rows with your verified label)")
    print(f"  Unlabelled        : {unlabelled} (AI prediction used as label)")

    from collections import Counter
    fruit_counts = Counter(r["produce_name"].lower() if r["produce_name"] else "unknown" for r in rows)
    label_counts = Counter(
        (r["ground_truth"] or r["status"] or "UNKNOWN").upper()
        for r in rows
    )
    print(f"\n  Produce breakdown:")
    for fruit, cnt in sorted(fruit_counts.items()):
        print(f"    {fruit:<12} : {cnt} scans")
    print(f"\n  Label breakdown (condition to train on):")
    for lbl, cnt in sorted(label_counts.items()):
        print(f"    {lbl:<14}: {cnt} rows")
    print("=" * 62 + "\n")

    if stats_only:
        return

    if total == 0:
        print("[!] No completed scans in the database yet. Collect some scans first.")
        return

    if only_labelled and labelled == 0:
        print("[!] No ground-truth labelled rows found. Use main.py Step E to label scans.")
        return

    # ── Export CSV ─────────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    written = 0

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()

        for row in rows:
            gt      = (row["ground_truth"] or "").strip().upper()
            status  = (row["status"] or "").strip().upper()

            # Use ground truth if set; otherwise fall back to AI prediction
            condition = gt if gt else status

            if only_labelled and not gt:
                continue  # Skip rows that the operator hasn't confirmed yet

            sid = row["id"]
            imgs = img_counts.get(sid, {"rgb": 8, "uv": 8})

            writer.writerow({
                "scan_id":             sid,
                "fruit_type":          (row["produce_name"] or "unknown").lower(),
                "condition":           condition,
                "predicted_condition": status,
                "timestamp":           row["created_at"] or "",
                "temperature_c":       row["temperature_c"] or 0.0,
                "humidity_pct":        row["humidity_pct"]  or 0.0,
                "pressure_hpa":        row["pressure_hpa"]  or 1013.25,
                "baseline_gas_kohms":  row["baseline_gas_kohms"]  or 0.0,
                "post_scan_gas_kohms": row["post_scan_gas_kohms"] or 0.0,
                "delta_gas_kohms":     row["gas_delta"]           or 0.0,
                "gas_min_kohms":       row["gas_min_kohms"]       or 0.0,
                "gas_max_kohms":       row["gas_max_kohms"]       or 0.0,
                "gas_mean_kohms":      row["gas_mean_kohms"]      or 0.0,
                "gas_std_kohms":       row["gas_std_kohms"]       or 0.0,
                "gas_ratio_pct":       row["gas_ratio_pct"]       or 0.0,
                "gas_slope_per_sec":   row["gas_slope_per_sec"]   or 0.0,
                "sample_count":        row["sample_count"]        or 0,
                "rgb_image_count":     imgs["rgb"],
                "uv_image_count":      imgs["uv"],
                "rot_suspicion":       (row["rot_suspicion"] or "UNKNOWN").upper(),
                "is_synthetic":        False,
            })
            written += 1

    print(f"[+] Exported {written} rows to:")
    print(f"    {out_path}")
    print(f"\n[>] Next step: run the trainer:")
    print(f"    python training/train_bme_only.py")
    print()


def main():
    parser = argparse.ArgumentParser(description="Export AgriScan 360 training data from SQLite to CSV")
    parser.add_argument("--db",  default=DB_PATH,     help="Path to agriscan360.db")
    parser.add_argument("--out", default=DEFAULT_OUT,  help="Output CSV path")
    parser.add_argument("--only-labelled", action="store_true",
                        help="Only export rows where you personally verified the label")
    parser.add_argument("--stats", action="store_true",
                        help="Print summary only, do not write CSV")
    args = parser.parse_args()

    export(
        db_path=args.db,
        out_path=args.out,
        only_labelled=args.only_labelled,
        stats_only=args.stats,
    )


if __name__ == "__main__":
    main()
