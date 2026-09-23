#!/usr/bin/env bash
# =============================================================================
# AgriScan 360 -- Raspberry Pi 5 Virtual Environment Setup Script
# =============================================================================
# Run this script on your Raspberry Pi 5 to automatically configure the lightweight
# client virtual environment (no heavy PyTorch or CUDA downloads needed):
#
#   chmod +x setup_pi_venv.sh
#   ./setup_pi_venv.sh
# =============================================================================

set -e

echo ""
echo "============================================================"
echo "  AgriScan 360 -- Raspberry Pi 5 Environment Setup"
echo "  (Lightweight Edge Mode -- Training on Laptop)"
echo "============================================================"
echo ""

# 1. Update APT and install essential hardware libraries
echo "[1/4] Installing system hardware packages (I2C, Camera, Python Venv)..."
sudo apt-get update -y
sudo apt-get install -y \
    python3-pip \
    python3-venv \
    python3-picamera2 \
    python3-libcamera \
    i2c-tools \
    libjpeg-dev \
    zlib1g-dev \
    libopenblas-dev

# 2. Enable I2C interface if not already active
echo "[2/4] Ensuring I2C bus is enabled..."
if ! grep -q "^dtparam=i2c_arm=on" /boot/firmware/config.txt 2>/dev/null && \
   ! grep -q "^dtparam=i2c_arm=on" /boot/config.txt 2>/dev/null; then
    sudo raspi-config nonint do_i2c 0 || true
    echo "  -> I2C enabled."
else
    echo "  -> I2C already enabled."
fi

# 3. Create virtual environment with --system-site-packages
# CRITICAL: --system-site-packages is required so the venv can access
# python3-picamera2 and libcamera installed by Debian/Raspberry Pi OS.
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

echo "[3/4] Creating Python virtual environment (venv) with system site packages..."
if [ -d "venv" ]; then
    echo "  -> Existing venv directory found. Refreshing..."
else
    python3 -m venv --system-site-packages venv
fi

# Activate venv
source venv/bin/activate

# Upgrade pip inside venv
python3 -m pip install --upgrade pip setuptools wheel

# 4. Install lightweight client dependencies
echo "[4/4] Installing lightweight edge dependencies from pi_client/requirements_pi.txt..."
python3 -m pip install -r pi_client/requirements_pi.txt

echo ""
echo "============================================================"
echo "  Setup Complete! Raspberry Pi 5 is Ready for AgriScan 360"
echo "============================================================"
echo ""
echo "To run the scanner:"
echo "  1. Activate the environment:"
echo "     source venv/bin/activate"
echo ""
echo "  2. Test hardware (optional):"
echo "     python tools/test_motor.py      # Test stepper turntable"
echo "     python tools/test_lights.py     # Test White and UV LEDs"
echo "     python tools/run_bme_diagnostic.py # Test BME688 sensor"
echo ""
echo "  3. Launch the full scan orchestrator:"
echo "     cd pi_client"
echo "     python main.py"
echo ""
