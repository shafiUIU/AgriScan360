# =============================================================================
# AgriScan 360 — Laptop Server Configuration
# =============================================================================

import os

# ── Server ────────────────────────────────────────────────────────────────────
HOST = "0.0.0.0"        # Bind to all interfaces so RPi can reach it over LAN
PORT = 8000
RELOAD = False          # Set True during development only

# ── Database ──────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'db', 'agriscan360.db')}"

# ── Static / Media Files ──────────────────────────────────────────────────────
STATIC_DIR = os.path.join(BASE_DIR, "static")
SCANS_DIR  = os.path.join(STATIC_DIR, "scans")   # Scan images saved here: scans/{scan_id}/

# ── AI Engine ─────────────────────────────────────────────────────────────────
# When you train a real model, put the ONNX file here and update MODEL_PATH
MODEL_PATH = os.path.join(BASE_DIR, "model", "agriscan360.onnx")
USE_AI_MODEL = os.path.exists(MODEL_PATH)         # Auto-detects if model file is present

# ── Classification Thresholds ─────────────────────────────────────────────────
# These control the rule-based classifier (used until a real model is trained)
HEALTHY_CONFIDENCE_MIN  = 70.0    # % — below this → UNCERTAIN
ROTTEN_GAS_DELTA_HIGH   = 5.0    # kΩ — HIGH gas drop strongly suggests rot
ROTTEN_GAS_DELTA_MED    = 2.0    # kΩ — MEDIUM gas drop raises suspicion

# RGB image color analysis thresholds (simple heuristics)
ROT_DARK_PIXEL_RATIO    = 0.15   # >15% very dark/brown pixels → rot indicator
ROT_HUE_VARIANCE_LOW    = 20.0   # low hue variance = uniform rot color spread

# ── Supported Produce ─────────────────────────────────────────────────────────
SUPPORTED_PRODUCE = [
    "Tomato", "Banana", "Eggplant", "Apple", "Carrot",
    "Grape", "Cucumber", "Guava", "Orange", "Potato", "Pomegranate"
]

# ── API Settings ──────────────────────────────────────────────────────────────
MAX_IMAGES_PER_SCAN  = 16     # 8 RGB + 8 UV
MAX_IMAGE_SIZE_MB    = 10     # per image upload limit
API_PREFIX           = "/api"

# ── CORS ─────────────────────────────────────────────────────────────────────
# Add your Pi's LAN IP here if you want strict CORS:
CORS_ORIGINS = ["*"]          # Allow all origins for local LAN use
