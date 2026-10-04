"""
tools/set_demo_mode.py
Controls the Showcase Demo Mode queue for AgriScan 360.
Guarantees the exact required outputs:
  Scan 1: Tomato -> HEALTHY -> 70% confidence
  Scan 2: Apple  -> ROTTEN  -> 100% confidence
"""

import os
import sys
import json
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
QUEUE_FILE = os.path.join(ROOT, "laptop_server", "demo_queue.json")
PI_STEP_FILE = os.path.join(ROOT, "pi_client", ".demo_step")

DEMO_PRESETS = [
    {
        "produce_name": "Tomato",
        "status": "HEALTHY",
        "confidence": 70.0,
        "reason": "Surface RGB reflectance uniform; baseline headspace VOC stability verified.",
        "rot_suspicion": "HEALTHY",
    },
    {
        "produce_name": "Apple",
        "status": "ROTTEN",
        "confidence": 100.0,
        "reason": "Severe fungal autofluorescence detected under 365nm UV; internal decay gas threshold exceeded.",
        "rot_suspicion": "ROTTEN",
    },
]


def enable_demo():
    data = {
        "active": True,
        "queue": list(DEMO_PRESETS),
    }
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    # Reset Pi step counter to 1
    try:
        with open(PI_STEP_FILE, "w", encoding="utf-8") as f:
            f.write("1")
    except Exception:
        pass

    print("\n" + "=" * 62)
    print("  AGRISCAN 360 -- SHOWCASE DEMO MODE: ENABLED")
    print("=" * 62)
    print("  The next 2 scans are 100% GUARANTEED:")
    print("    Scan 1: Tomato -> HEALTHY -> 70% Confidence")
    print("    Scan 2: Apple  -> ROTTEN  -> 100% Confidence")
    print("=" * 62)
    print(f"  Queue file: {QUEUE_FILE}")
    print("  After Scan 2 finishes, the server returns to normal AI mode.\n")


def disable_demo():
    if os.path.exists(QUEUE_FILE):
        try:
            with open(QUEUE_FILE, "w", encoding="utf-8") as f:
                json.dump({"active": False, "queue": []}, f, indent=2)
        except Exception as e:
            print("Error disabling:", e)
    print("\n[+] Showcase demo mode DISABLED. Normal AI classifier active.\n")


def status_demo():
    if not os.path.exists(QUEUE_FILE):
        print("\n[i] Demo queue file does not exist. Normal AI classifier is active.\n")
        return

    try:
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print("[!] Error reading demo queue:", e)
        return

    active = data.get("active", False)
    queue = data.get("queue", [])

    print("\n" + "=" * 62)
    print(f"  AGRISCAN 360 -- DEMO MODE STATUS: {'ACTIVE' if active else 'INACTIVE'}")
    print("=" * 62)
    if active and queue:
        print(f"  Remaining queued demo scans: {len(queue)}")
        for idx, item in enumerate(queue, 1):
            print(f"    Next {idx}: {item.get('produce_name')} -> {item.get('status')} ({item.get('confidence')}%)")
    else:
        print("  Queue is empty. Next scans will use real sensor AI classification.")
    print("=" * 62 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Manage AgriScan 360 video showcase demo mode")
    parser.add_argument("--enable", action="store_true", help="Arm the 2 guaranteed demo scans")
    parser.add_argument("--disable", action="store_true", help="Turn off demo mode immediately")
    parser.add_argument("--status", action="store_true", help="Check current demo queue status")
    args = parser.parse_args()

    if args.disable:
        disable_demo()
    elif args.status:
        status_demo()
    else:
        # Default action is to enable
        enable_demo()


if __name__ == "__main__":
    main()
