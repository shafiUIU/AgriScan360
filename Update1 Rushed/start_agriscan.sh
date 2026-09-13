#!/usr/bin/env bash
# =============================================================================
# AgriScan 360 — Single-Device Standalone Pi Startup Script
# =============================================================================
# Run on the Raspberry Pi terminal:
#   chmod +x start_agriscan.sh
#   ./start_agriscan.sh
# Or pass --simulate to run without hardware:
#   ./start_agriscan.sh --simulate
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
