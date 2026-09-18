#!/usr/bin/env bash
# =============================================================================
# AgriScan 360 — Standalone Pi 5 Startup Script
# =============================================================================
# Run on the Raspberry Pi terminal:
#   chmod +x start_agriscan.sh
#   ./start_agriscan.sh
#
# Pass any custom flags (e.g. simulation or manual leds):
#   ./start_agriscan.sh --simulate
#   ./start_agriscan.sh --manual-leds
#   ./start_agriscan.sh --produce Tomato
# =============================================================================

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# 1. Activate virtual environment if present
if [ -d "venv" ]; then
    echo "[AgriScan] Activating virtual environment (venv)..."
    source venv/bin/activate
elif [ -d "../venv" ]; then
    echo "[AgriScan] Activating virtual environment (../venv)..."
    source ../venv/bin/activate
fi

# 2. Run the single-device master launcher
python3 run_single_device.py "$@"
