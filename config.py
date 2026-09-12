"""
AgriScan 360 - System Configuration File
Central configuration for all GPIO pins, thresholds, timings, and paths.
"""

import os

# ==============================================================================
# 1. GPIO PIN DEFINITIONS (BCM Numbering)
# ==============================================================================
# Stepper Motor (A4988)
PIN_STEP   = 17   # Physical Pin 11 -> A4988 STEP
PIN_DIR    = 27   # Physical Pin 13 -> A4988 DIR
PIN_ENABLE = 22   # Physical Pin 15 -> A4988 ENABLE (Active LOW)

# Dual Illumination (IRLZ44N MOSFET Gates)
PIN_WHITE_LED = 18  # Physical Pin 12 -> MOSFET #1 (White Surface Light)
PIN_UV_LED    = 24  # Physical Pin 18 -> MOSFET #2 (365nm UV Light)

# I2C Bus (Used by both Bosch BME688 and SSD1306 OLED)
# GPIO 2 (Physical Pin 3) = SDA
# GPIO 3 (Physical Pin 5) = SCL

# ==============================================================================
# 2. MOTOR & SCANNING PARAMETERS
# ==============================================================================
# NEMA 17 (1.8 deg/step) in Full Step mode: 200 steps = 360 degrees
# 8 stops per full circle = 200 / 8 = 25 steps per stop
STEPS_PER_STOP = 25
TOTAL_STOPS    = 8
PULSE_DELAY    = 0.005  # Seconds per step pulse (safe, smooth speed)

# ==============================================================================
# 3. TIMINGS & THRESHOLDS
# ==============================================================================
EXPOSURE_PAUSE_SEC  = 1.0   # Time light stays on for photo exposure
GAS_WARMUP_CYCLES   = 3     # Sensor stabilization seconds before scan
VOC_ROT_THRESHOLD   = 12.0  # kOhms drop from baseline that flags internal decay

# ==============================================================================
# 4. PATHS & SYSTEM DIRECTORIES
# ==============================================================================
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CAPTURE_DIR = os.path.join(BASE_DIR, "captured_scans")
os.makedirs(CAPTURE_DIR, exist_ok=True)

# Web Dashboard Port
WEB_PORT = 5000
