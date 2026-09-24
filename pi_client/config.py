# =============================================================================
# AgriScan 360 -- Raspberry Pi 5 Configuration
# =============================================================================
# Edit LAPTOP_SERVER_URL to match your laptop's local IP address before running.
# Run `ipconfig` (Windows) or `ip a` (Linux) on the laptop to find its LAN IP.

# -- Network ------------------------------------------------------------------
# Default to loopback (127.0.0.1) for Single-Device Standalone Pi operation.
# Can be overridden by setting the AGRISCAN_SERVER_URL environment variable.
import os
LAPTOP_SERVER_URL = os.getenv("AGRISCAN_SERVER_URL", "http://10.210.73.32:8000")
API_SCAN_ENDPOINT = f"{LAPTOP_SERVER_URL}/api/scan"
API_HEALTH_ENDPOINT = f"{LAPTOP_SERVER_URL}/api/health"
REQUEST_TIMEOUT_SEC = 30                            # seconds before declaring server offline

# -- GPIO Pins (BCM numbering) ------------------------------------------------
# Motor -- A4988 Driver
PIN_STEP   = 17
PIN_DIR    = 27
PIN_ENABLE = 22   # Active LOW: off() = motor ON, on() = motor OFF (coils de-energized)

# LEDs via IRLZ44N MOSFETs
PIN_LED_WHITE = 18   # MOSFET #1 Gate -> White Diffused LED Array
PIN_LED_UV    = 24   # MOSFET #2 Gate -> 365nm UV-A LED Array

# SG90 Micro Servo -- Pipe Feed Door
PIN_SERVO = 23   # PWM Signal -> GPIO 23 (Physical Pin 16)
                 # 0 deg = Door CLOSED, 90 deg = Door OPEN (2s duration)

# -- I2C Devices --------------------------------------------------------------
# BME688 Gas Sensor  -> SDA=GPIO2 (Pin3), SCL=GPIO3 (Pin5), address 0x77
# SSD1306 OLED 1.3"  -> SDA=GPIO2 (Pin3), SCL=GPIO3 (Pin5), address 0x3C
BME688_ADDRESS  = 0x77
SSD1306_ADDRESS = 0x3C
OLED_WIDTH  = 128
OLED_HEIGHT = 64

# -- Motor Settings -----------------------------------------------------------
STEPS_PER_REV      = 200     # NEMA 17 at full-step = 200 steps / 360 deg
STEPS_PER_STOP     = 25      # 25 steps = exactly 45 deg
NUM_SCAN_STOPS     = 8       # 8 stops x 45 deg = 360 deg
PULSE_DELAY        = 0.005   # seconds between step pulses (safe, smooth)
RAMP_STEPS         = 10      # Number of steps to ramp up/down speed softly
RAMP_START_DELAY   = 0.015   # Starting pulse delay during ramp
SETTLE_DELAY       = 1.5     # seconds to let turntable settle before capture

# -- Camera Settings ----------------------------------------------------------
CAPTURE_RESOLUTION = (1920, 1080)   # Full HD capture
JPEG_QUALITY       = 100             # JPEG quality 0-100
WHITE_WARMUP_SEC   = 0.3            # time to let White LEDs warm up before capture (manual mode)
UV_WARMUP_SEC      = 0.5            # time to let UV LEDs warm up before capture (manual mode)
MOSFET_WHITE_HOLD_SEC = 5.0         # White LED ON hold time in MOSFET auto mode (seconds before snap)
MOSFET_UV_HOLD_SEC    = 5.0         # UV-A LED ON hold time in MOSFET auto mode (seconds before snap)

# -- Gas Sensor & Chamber Settings --------------------------------------------
CHAMBER_VOLUME_LITERS    = 27.0  # 27L closed container volume
BME688_I2C_ADDRESSES     = [0x77, 0x76]  # Auto-probes both Bosch I2C addresses
BME_WARMUP_DISCARD_SEC   = 120   # Discard first 2 minutes (120s) of BME data for stabilization
GAS_EMPTY_BOX_SNIFF_SEC  = 180   # 3 minutes (180s) empty box clean-air baseline sniff
GAS_PRE_SCAN_INCUBATION_SEC = 180  # 3 minutes (180s) produce gas accumulation incubation
GAS_BASELINE_READS       = 10    # baseline averaging count (fallback)
GAS_BASELINE_DELAY       = 0.5   # seconds between baseline reads
GAS_SNIFF_INTERVAL_SEC   = 0.5   # continuous sniffing sample interval during scan
GAS_DELTA_THRESHOLD      = 5.0   # kOhm drop indicating high rot suspicion
GAS_LOG_RAW_TIMESERIES   = True  # Save high-resolution per-second raw ohm timeseries
TIMESERIES_DATA_DIR      = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "datasets", "timeseries")

# -- Produce List (Strict Focus on 3 Target Produce Items) --------------------
SUPPORTED_PRODUCE = [
    "Tomato", "Apple", "Eggplant"
]
DEFAULT_PRODUCE = "Tomato"
