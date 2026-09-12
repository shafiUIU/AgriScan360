#!/bin/bash
# ============================================================
#  AgriScan 360 — Raspberry Pi 5 Scan Launcher
#  Run this on the RASPBERRY PI to start scanning.
# ============================================================

echo ""
echo " ╔══════════════════════════════════════════════╗"
echo " ║     AgriScan 360 — Pi Scan Client            ║"
echo " ║     UIU CSE 4326  -  Stage 1                 ║"
echo " ╚══════════════════════════════════════════════╝"
echo ""

# Navigate to pi_client folder
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/pi_client" || exit 1

# Show Pi's IP so you can verify it's on same network
echo "Pi network IP:"
hostname -I
echo ""

# Install dependencies if first run (uncomment if needed):
# pip install -r requirements_pi.txt

echo "Starting AgriScan 360 Pi client..."
echo "Press Ctrl+C to stop."
echo ""

python main.py "$@"
