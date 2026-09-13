# =============================================================================
# AgriScan 360 — "Update1 Rushed" Configuration
# =============================================================================
# CHANGES FROM FULL VERSION:
#   - LEDs (White + UV) are controlled MANUALLY by hand (no GPIO, no MOSFETs)
#   - BME688 gas sensor is REMOVED (no I2C gas measurement)
#   - Motor + Camera remain 100% functional
#   - 16 images captured per scan (8 RGB + 8 UV via manual external switch)

# ── Network (Single-Device Standalone Pi) ────────────────────────────────────
# In Single-Device mode, the server runs on the Pi itself at 127.0.0.1:8000.
# No external IP or Wi-Fi matching required!
SERVER_URL          = "http://127.0.0.1:8000"
LAPTOP_SERVER_URL   = SERVER_URL   # Backwards compatibility alias
API_SCAN_ENDPOINT   = f"{SERVER_URL}/api/scan"
API_HEALTH_ENDPOINT = f"{SERVER_URL}/api/health"
REQUEST_TIMEOUT_SEC = 30

# ── GPIO Pins (BCM numbering) ─────────────────────────────────────────────────
# Motor — A4988 Driver (ACTIVE — fully working)
PIN_STEP   = 17
PIN_DIR    = 27
PIN_ENABLE = 22   # Active LOW: off()=ON, on()=OFF

# ── LEDs — MANUALLY controlled by operator (no GPIO needed) ───────────────────
# PIN_LED_WHITE = 18   # REMOVED — White LED turned on by hand before scan
# PIN_LED_UV    = 24   # REMOVED — UV LED turned on by hand (independent of scan)
# WHITE_WARMUP_SEC = 0.3   # REMOVED — no software warm-up needed
# UV_WARMUP_SEC    = 0.5   # REMOVED — UV is manual

# ── I2C Devices ───────────────────────────────────────────────────────────────
# BME688_ADDRESS  = 0x77   # REMOVED — gas sensor not used in this version
SSD1306_ADDRESS = 0x3C
OLED_WIDTH  = 128
OLED_HEIGHT = 64

# ── Motor Settings ─────────────────────────────────────────────────────────────
STEPS_PER_REV      = 200
STEPS_PER_STOP     = 25      # 25 steps = 45°
NUM_SCAN_STOPS     = 8       # 8 stops × 45° = 360°
PULSE_DELAY        = 0.005
RAMP_STEPS         = 10
RAMP_START_DELAY   = 0.015
SETTLE_DELAY       = 0.5     # seconds to let turntable settle before capture

# ── Camera Settings ────────────────────────────────────────────────────────────
CAPTURE_RESOLUTION = (1920, 1080)
JPEG_QUALITY       = 85
CAPTURE_DELAY      = 0.2     # brief pause before capturing (replaces warmup)

# ── Gas Sensor Settings — REMOVED ─────────────────────────────────────────────
# GAS_BASELINE_READS  = 5    # REMOVED — no BME688
# GAS_BASELINE_DELAY  = 1.0  # REMOVED
# GAS_DELTA_THRESHOLD = 5.0  # REMOVED

# ── Produce List (11 supported items) ─────────────────────────────────────────
SUPPORTED_PRODUCE = [
    "Tomato", "Banana", "Eggplant", "Apple", "Carrot",
    "Grape", "Cucumber", "Guava", "Orange", "Potato", "Pomegranate"
]
DEFAULT_PRODUCE = "Unknown"
