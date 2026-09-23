#!/bin/bash
# =============================================================================
# AgriScan 360 -- Raspberry Pi 5 Client Launcher
# =============================================================================
# Run this on your Raspberry Pi 5 terminal to start scanning:
#   chmod +x start_pi.sh
#   ./start_pi.sh
# =============================================================================

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo ""
echo "+----------------------------------------------------------+"
echo "|         AgriScan 360 -- Raspberry Pi Client              |"
echo "+----------------------------------------------------------+"
echo ""

# 1. Activate venv if present
if [ -d "venv" ]; then
    echo "[AgriScan] Activating virtual environment (venv)..."
    source venv/bin/activate
elif [ -d "../venv" ]; then
    echo "[AgriScan] Activating virtual environment (../venv)..."
    source ../venv/bin/activate
else
    echo "[AgriScan] Warning: No virtual environment found. Running with system python."
    echo "           (Tip: Run ./setup_pi_venv.sh once to set up venv)"
fi

# 2. Show Pi IP
echo "Pi Network IP Address:"
hostname -I || true
echo ""

# 3. Launch main orchestrator
cd "$SCRIPT_DIR/pi_client"
echo "Starting AgriScan 360 client..."
echo "Press Ctrl+C to stop."
echo ""

python3 main.py "$@"
