# =============================================================================
# AgriScan 360 — Raspberry Pi 5 Configuration
# =============================================================================
# Edit LAPTOP_SERVER_URL to match your laptop's local IP address before running.
# Run `ipconfig` (Windows) or `ip a` (Linux) on the laptop to find its LAN IP.

# ── Network ──────────────────────────────────────────────────────────────────
LAPTOP_SERVER_URL = "http://192.168.1.100:8000"   # ← CHANGE THIS to your laptop's IP
API_SCAN_ENDPOINT = f"{LAPTOP_SERVER_URL}/api/scan"
API_HEALTH_ENDPOINT = f"{LAPTOP_SERVER_URL}/api/health"
REQUEST_TIMEOUT_SEC = 30                            # seconds before declaring server offline

# ── GPIO Pins (BCM numbering) ─────────────────────────────────────────────────
# Motor — A4988 Driver
PIN_STEP   = 17
PIN_DIR    = 27
PIN_ENABLE = 22   # Active LOW: off() = motor ON, on() = motor OFF (coils de-energized)

# LEDs via IRLZ44N MOSFETs
PIN_LED_WHITE = 18   # MOSFET #1 Gate → White Diffused LED Array
PIN_LED_UV    = 24   # MOSFET #2 Gate → 365nm UV-A LED Array

# ── I2C Devices ───────────────────────────────────────────────────────────────
# BME688 Gas Sensor  → SDA=GPIO2 (Pin3), SCL=GPIO3 (Pin5), address 0x77
# SSD1306 OLED 0.96" → SDA=GPIO2 (Pin3), SCL=GPIO3 (Pin5), address 0x3C
BME688_ADDRESS  = 0x77
SSD1306_ADDRESS = 0x3C
OLED_WIDTH  = 128
OLED_HEIGHT = 64

# ── Motor Settings ─────────────────────────────────────────────────────────────
STEPS_PER_REV      = 200     # NEMA 17 at full-step = 200 steps / 360°
STEPS_PER_STOP     = 25      # 25 steps = exactly 45°
NUM_SCAN_STOPS     = 8       # 8 stops × 45° = 360°
PULSE_DELAY        = 0.005   # seconds between step pulses (safe, smooth)
RAMP_STEPS         = 10      # Number of steps to ramp up/down speed softly
RAMP_START_DELAY   = 0.015   # Starting pulse delay during ramp
SETTLE_DELAY       = 0.5     # seconds to let turntable settle before capture

# ── Camera Settings ────────────────────────────────────────────────────────────
CAPTURE_RESOLUTION = (1920, 1080)   # Full HD capture
JPEG_QUALITY       = 85             # JPEG quality 0-100
WHITE_WARMUP_SEC   = 0.3            # time to let White LEDs warm up before capture
UV_WARMUP_SEC      = 0.5            # time to let UV LEDs warm up before capture

# ── Gas Sensor Settings ────────────────────────────────────────────────────────
GAS_BASELINE_READS  = 5     # number of reads to average for baseline
GAS_BASELINE_DELAY  = 1.0   # seconds between baseline reads
GAS_DELTA_THRESHOLD = 5.0   # kΩ drop that triggers elevated-rot suspicion

# ── Produce List (11 supported items) ─────────────────────────────────────────
SUPPORTED_PRODUCE = [
    "Tomato", "Banana", "Eggplant", "Apple", "Carrot",
    "Grape", "Cucumber", "Guava", "Orange", "Potato", "Pomegranate"
]
DEFAULT_PRODUCE = "Unknown"
