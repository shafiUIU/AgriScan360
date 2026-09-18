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
# Two separate ONNX models — RGB (white-light) and UV-A (fluorescence).
# Both are auto-detected from the models/ folder.
# Place trained .onnx files from Google Colab here to activate neural mode.
MODELS_DIR      = os.path.join(BASE_DIR, "models")
RGB_MODEL_PATH  = os.path.join(MODELS_DIR, "rgb_agriscan_v1.onnx")
UV_MODEL_PATH   = os.path.join(MODELS_DIR, "uv_agriscan_v1.onnx")
USE_RGB_MODEL   = os.path.exists(RGB_MODEL_PATH)   # Auto-detects RGB model
USE_UV_MODEL    = os.path.exists(UV_MODEL_PATH)    # Auto-detects UV model
USE_AI_MODEL    = USE_RGB_MODEL or USE_UV_MODEL    # True if at least one model present

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
