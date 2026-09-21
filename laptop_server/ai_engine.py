"""
ai_engine.py — Multi-Modal AI Classification Engine
=====================================================
Stage 1: Rule-based classifier (no dataset needed to run NOW).
          Uses image colour analysis + gas delta + structured fusion.
          Drop-in slot: when your ONNX model is trained, set MODEL_PATH
          in config.py and the engine auto-switches to neural inference.

Detection Pillars:
    Pillar 1 (RGB)  — Surface rot, bruising, necrosis via colour heuristics
    Pillar 2 (UV-A) — Fungal fluorescence: mould glows green/yellow under 365nm
    Pillar 3 (Gas)  — Internal rot/core decay via BME688 VOC resistance drop

Datasets to train real model (DO NOT DOWNLOAD YET — user will do manually):
    Primary:   Freshness44, BrinjalFruitX, Fruits-360 (turntable geometry match)
    Supplemental: Guava Disease, Pomegranate Disease, 3-Level Decay (zijianchen98)
    UV branch: Longitudinal RGB+UV-A Tomato (Zenodo) + own chamber captures
    Gas branch: Own BME688 dataset (must collect with hardware)
"""

import io
import logging
import os
import time
from typing import List, Tuple

log = logging.getLogger(__name__)

# Optional: OpenCV for image analysis
try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    log.warning("opencv-python not found. Using Pillow-only fallback for image analysis.")

# Optional: PIL for fallback
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# Optional: ONNX Runtime for trained model inference
try:
    import onnxruntime as ort
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False

from config import (
    RGB_MODEL_PATH, UV_MODEL_PATH,
    USE_RGB_MODEL, USE_UV_MODEL, USE_AI_MODEL,
    HEALTHY_CONFIDENCE_MIN,
    ROTTEN_GAS_DELTA_HIGH, ROTTEN_GAS_DELTA_MED,
    ROT_DARK_PIXEL_RATIO, ROT_HUE_VARIANCE_LOW,
)


# =============================================================================
# Image Feature Extraction
# =============================================================================

class ImageAnalyzer:
    """
    Extracts rot-relevant features from JPEG image bytes.
    Works with OpenCV (preferred) or Pillow (fallback).
    """

    @staticmethod
    def _load_as_array(jpeg_bytes: bytes):
        """Load JPEG bytes into an RGB numpy array."""
        if CV2_AVAILABLE:
            arr = np.frombuffer(jpeg_bytes, np.uint8)
            bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        elif PIL_AVAILABLE:
            import numpy as np
            img = Image.open(io.BytesIO(jpeg_bytes)).convert("RGB")
            return np.array(img)
        return None

    @staticmethod
    def analyze_rgb(jpeg_bytes: bytes) -> dict:
        """
        Analyse a white-light (RGB) image for surface rot indicators.
        Returns feature dict with rot_score (0–1).
        """
        features = {
            "dark_pixel_ratio": 0.0,
            "brown_ratio": 0.0,
            "hue_variance": 50.0,
            "saturation_mean": 100.0,
            "rot_score": 0.0,
        }

        arr = ImageAnalyzer._load_as_array(jpeg_bytes)
        if arr is None:
            return features

        import numpy as np
        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

        # Dark pixel ratio — very dark patches suggest surface rot / necrosis
        brightness = (r.astype(float) + g + b) / 3.0
        dark_mask  = brightness < 40
        features["dark_pixel_ratio"] = float(dark_mask.mean())

        # Brown pixel ratio — browning is the #1 surface rot indicator
        # Brown: R > G, R > B, moderate saturation
        brown_mask = (r.astype(int) - g.astype(int) > 20) & \
                     (r.astype(int) - b.astype(int) > 20) & \
                     (r > 60) & (r < 200)
        features["brown_ratio"] = float(brown_mask.mean())

        # Hue variance (needs HSV conversion)
        if CV2_AVAILABLE:
            hsv = cv2.cvtColor(arr, cv2.COLOR_RGB2HSV)
            features["hue_variance"]     = float(np.std(hsv[:, :, 0].astype(float)))
            features["saturation_mean"]  = float(np.mean(hsv[:, :, 1].astype(float)))
        else:
            # Simple approximation without OpenCV
            features["hue_variance"]    = float(np.std(r.astype(float) - g.astype(float)))
            features["saturation_mean"] = 100.0

        # Composite rot score (0–1, higher = more likely rotten)
        score = (
            features["dark_pixel_ratio"]  * 0.35 +
            features["brown_ratio"]       * 0.40 +
            max(0, (ROT_HUE_VARIANCE_LOW - features["hue_variance"]) / ROT_HUE_VARIANCE_LOW) * 0.25
        )
        features["rot_score"] = min(1.0, score)
        return features

    @staticmethod
    def analyze_uv(jpeg_bytes: bytes) -> dict:
        """
        Analyse a 365nm UV image for fungal fluorescence.
        Mould/aflatoxin glows bright green–yellow under 365nm UV.
        Healthy fruit appears dark or very faintly bluish.
        Returns feature dict with fluorescence_score (0–1).
        """
        features = {
            "bright_green_ratio": 0.0,
            "bright_yellow_ratio": 0.0,
            "overall_brightness": 0.0,
            "fluorescence_score": 0.0,
        }

        arr = ImageAnalyzer._load_as_array(jpeg_bytes)
        if arr is None:
            return features

        import numpy as np
        r, g, b = arr[:, :, 0].astype(float), arr[:, :, 1].astype(float), arr[:, :, 2].astype(float)

        # Bright green pixels: green channel dominant, moderate brightness
        green_dominant = (g > r * 1.2) & (g > b * 1.2) & (g > 60)
        features["bright_green_ratio"] = float(green_dominant.mean())

        # Bright yellow: both R and G high, B low
        yellow_dominant = (r > 100) & (g > 100) & (b < 60) & ((r + g) > 200)
        features["bright_yellow_ratio"] = float(yellow_dominant.mean())

        # Overall brightness of UV image (healthy fruit = dark, mould = bright)
        features["overall_brightness"] = float((r + g + b).mean() / 3.0 / 255.0)

        # Fluorescence score
        score = (
            features["bright_green_ratio"]  * 0.50 +
            features["bright_yellow_ratio"] * 0.35 +
            features["overall_brightness"]  * 0.15
        )
        features["fluorescence_score"] = min(1.0, score)
        return features

    @staticmethod
    def aggregate_features(rgb_features: List[dict], uv_features: List[dict]) -> dict:
        """Average features across all 8 angles for each light type."""
        def avg(lst, key):
            vals = [d[key] for d in lst if key in d]
            return sum(vals) / len(vals) if vals else 0.0

        return {
            "rgb_rot_score":        avg(rgb_features, "rot_score"),
            "rgb_dark_ratio":       avg(rgb_features, "dark_pixel_ratio"),
            "rgb_brown_ratio":      avg(rgb_features, "brown_ratio"),
            "rgb_hue_variance":     avg(rgb_features, "hue_variance"),
            "uv_fluorescence_score": avg(uv_features, "fluorescence_score"),
            "uv_green_ratio":       avg(uv_features, "bright_green_ratio"),
            "uv_yellow_ratio":      avg(uv_features, "bright_yellow_ratio"),
        }


# =============================================================================
# ONNX Neural Model Inference (used when model file is present)
# =============================================================================

class ONNXClassifier:
    """
    Wrapper around ONNX Runtime for a single trained model.
    Instantiated separately for RGB and UV models.
    """

    def __init__(self, model_path: str, label: str = "model"):
        self._session = None
        self._label   = label
        if ONNX_AVAILABLE and model_path:
            try:
                self._session = ort.InferenceSession(
                    model_path,
                    providers=["CPUExecutionProvider"]
                )
                log.info("%s ONNX model loaded from %s", label, model_path)
            except Exception as exc:
                log.error("%s ONNX model load failed: %s", label, exc)

    @property
    def available(self):
        return self._session is not None

    def predict(self, image_bytes: bytes) -> Tuple[str, float]:
        """
        Run inference on a single image.
        Returns (class_label, confidence_0_to_1).
        Model output: raw logits for [HEALTHY, ROTTEN, UNCERTAIN] — softmax applied here.
        """
        if not self.available:
            return "UNKNOWN", 0.0

        import numpy as np
        try:
            arr = ImageAnalyzer._load_as_array(image_bytes)
            if arr is None:
                return "UNKNOWN", 0.0
            # Resize and normalize for model input (224x224, ImageNet stats)
            if CV2_AVAILABLE:
                arr = cv2.resize(arr, (224, 224))
            else:
                arr = np.array(Image.open(io.BytesIO(image_bytes)).resize((224, 224)))

            mean = np.array([0.485, 0.456, 0.406])
            std  = np.array([0.229, 0.224, 0.225])
            arr  = (arr.astype(np.float32) / 255.0 - mean) / std
            arr  = arr.transpose(2, 0, 1)[np.newaxis]   # NCHW

            input_name = self._session.get_inputs()[0].name
            outputs    = self._session.run(None, {input_name: arr})[0][0]
            exp_out    = np.exp(outputs - outputs.max())  # numerically stable softmax
            probs      = exp_out / exp_out.sum()
            labels     = ["HEALTHY", "ROTTEN", "UNCERTAIN"]
            idx        = int(np.argmax(probs))
            return labels[idx], float(probs[idx])
        except Exception as exc:
            log.error("%s ONNX inference error: %s", self._label, exc)
            return "UNKNOWN", 0.0


# =============================================================================
# Multi-Modal Fusion Classifier (main entry point)
# =============================================================================

# ── Per-Produce Gas Freshness Profiles (Server-Side) ─────────────────────────
PRODUCE_GAS_PROFILES = {
    "Tomato": {
        "FRESH":      (8.0,  3.0),
        "MID_FRESH":  (15.0, 5.5),
        "MID_ROTTEN": (25.0, 9.0),
    },
    "Apple": {
        "FRESH":      (10.0, 4.0),
        "MID_FRESH":  (18.0, 7.0),
        "MID_ROTTEN": (28.0, 11.0),
    },
    "Eggplant": {
        "FRESH":      (6.0,  2.5),
        "MID_FRESH":  (12.0, 4.5),
        "MID_ROTTEN": (20.0, 7.5),
    },
    "default": {
        "FRESH":      (8.0,  3.5),
        "MID_FRESH":  (16.0, 6.0),
        "MID_ROTTEN": (24.0, 9.5),
    },
}


class AIClassifier:
    """
    The main classifier. Fuses three sensor pillars:
        Pillar 1: RGB surface analysis
        Pillar 2: UV-A fluorescence analysis
        Pillar 3: BME688 gas resistance delta

    When a trained ONNX model is available, Pillar 1+2 defer to neural inference.
    Pillar 3 (gas) always uses the rule-based approach (own dataset needed).
    """

    CLASS_LABELS = ["FRESH", "MID_FRESH", "MID_ROTTEN", "ROTTEN"]

    def __init__(self):
        # Load RGB model (Pillar 1) and UV model (Pillar 2) separately
        self._rgb_onnx = ONNXClassifier(
            model_path=RGB_MODEL_PATH if USE_RGB_MODEL else "",
            label="RGB"
        )
        self._uv_onnx = ONNXClassifier(
            model_path=UV_MODEL_PATH if USE_UV_MODEL else "",
            label="UV"
        )
        self._analyzer = ImageAnalyzer()
        log.info(
            "AIClassifier initialized. RGB model: %s | UV model: %s",
            "loaded" if self._rgb_onnx.available else "rule-based",
            "loaded" if self._uv_onnx.available  else "rule-based",
        )

    @property
    def model_loaded(self) -> bool:
        """True if either the RGB or UV neural model is loaded."""
        return self._rgb_onnx.available or self._uv_onnx.available

    @property
    def _onnx(self):
        """Backward-compatibility property for legacy calls to classifier._onnx.available."""
        class _LegacyWrapper:
            def __init__(self, is_avail):
                self.available = is_avail
        return _LegacyWrapper(self.model_loaded)

    def classify(
        self,
        rgb_images:  List[bytes],   # 8 JPEG bytes (white light, 8 angles)
        uv_images:   List[bytes],   # 8 JPEG bytes (UV light, 8 angles)
        gas_delta:   float,         # kOhm drop from BME688
        rot_suspicion: str,         # FRESH / MID_FRESH / MID_ROTTEN / ROTTEN
        gas_ratio_pct: float = 0.0, # relative percentage drop (scale-invariant)
        gas_slope_per_sec: float = 0.0, # rate of change dR/dt (kOhm/s)
        produce_name: str = "default",
    ) -> dict:
        """
        Full multi-modal classification.
        Returns dict: {status, confidence, reason, pillar_scores, model_used}
        """
        start = time.time()

        # Choose mode based on which models are available
        if self._rgb_onnx.available or self._uv_onnx.available:
            result = self._neural_classify(rgb_images, uv_images, gas_delta, rot_suspicion, gas_ratio_pct, gas_slope_per_sec, produce_name)
        else:
            result = self._rule_classify(rgb_images, uv_images, gas_delta, rot_suspicion, gas_ratio_pct, gas_slope_per_sec, produce_name)

        result["inference_ms"] = round((time.time() - start) * 1000, 1)
        log.info("Classification complete [%s]: %s (%.1f%%) in %.0fms",
                 produce_name, result["status"], result["confidence"], result["inference_ms"])
        return result

    # ── Rule-Based Classifier ─────────────────────────────────────────────────

    def _rule_classify(self, rgb_images, uv_images, gas_delta, rot_suspicion, gas_ratio_pct=0.0, gas_slope_per_sec=0.0, produce_name="default") -> dict:
        """
        Heuristic multi-pillar fusion without a trained model.
        Active until you download datasets and train the ONNX model.
        """
        # Analyse all 8 angles
        rgb_feats = [ImageAnalyzer.analyze_rgb(img) for img in rgb_images]
        uv_feats  = [ImageAnalyzer.analyze_uv(img)  for img in uv_images]
        agg       = ImageAnalyzer.aggregate_features(rgb_feats, uv_feats)

        # Pillar scores (0-1, higher = more rotten)
        p1_score = agg["rgb_rot_score"]            # RGB surface rot
        p2_score = agg["uv_fluorescence_score"]    # UV fluorescence
        p3_score = self._gas_score(gas_delta, gas_ratio_pct, gas_slope_per_sec, produce_name)  # Enhanced Gas VOC

        # Weighted fusion
        fused = p1_score * 0.40 + p2_score * 0.35 + p3_score * 0.25
        confidence_rotten  = fused * 100.0
        confidence_healthy = (1.0 - fused) * 100.0

        # 4-tier decision matching per-produce gas analytics
        if fused >= 0.60:
            status     = "ROTTEN"
            confidence = confidence_rotten
        elif fused >= 0.40:
            status     = "MID_ROTTEN"
            confidence = confidence_rotten
        elif fused >= 0.18:
            status     = "MID_FRESH"
            confidence = confidence_healthy
        else:
            status     = "FRESH"
            confidence = confidence_healthy

        # Clamp confidence
        confidence = round(min(99.9, max(50.1, confidence)), 1)

        # Gas override: strong VOC signal overrules FRESH/MID_FRESH
        if p3_score > 0.7 and status in ("FRESH", "MID_FRESH"):
            status     = "MID_ROTTEN"
            confidence = min(confidence, 70.0)
            reason = (
                f"Vision heuristic estimated {status} (RGB: {p1_score:.2f}, UV: {p2_score:.2f}) "
                f"but gas sensor detected elevated VOC levels ({rot_suspicion}, DeltaGas={gas_delta:.1f} kOhm, "
                f"Drop={gas_ratio_pct:.1f}%, Slope={gas_slope_per_sec:+.4f}). Status adjusted to MID_ROTTEN."
            )
        else:
            reason = self._build_reason(status, p1_score, p2_score, p3_score,
                                        agg, gas_delta, rot_suspicion)

        return {
            "status":      status,
            "confidence":  confidence,
            "reason":      reason,
            "model_used":  "rule_based_v1",
            "pillar_scores": {
                "rgb_surface": round(p1_score, 3),
                "uv_fluorescence": round(p2_score, 3),
                "gas_voc": round(p3_score, 3),
                "fused": round(fused, 3),
            },
            "agg_features": agg,
        }

    def _neural_classify(self, rgb_images, uv_images, gas_delta, rot_suspicion, gas_ratio_pct=0.0, gas_slope_per_sec=0.0, produce_name="default") -> dict:
        """
        Dual-model ONNX classification (Pillar 1 = RGB model, Pillar 2 = UV model).

        - RGB model runs on the 8 white-light frames -> p1_score
        - UV  model runs on the 8 UV-A frames        -> p2_score
        - If a model is missing, that pillar falls back to rule-based heuristic
        - Gas sensor (BME688) uses enhanced multi-feature analytics -> p3_score
        - Final fusion: p1*0.40 + p2*0.35 + p3*0.25
        """
        import numpy as np

        LABEL_ROT_SCORE = {
            # Legacy 3-tier (kept for backward compatibility)
            "HEALTHY":      0.0,
            "EARLY_ROT":    0.55,
            "SEVERE_ROT":   0.95,
            # New 4-tier per-produce labels
            "FRESH":        0.0,
            "MID_FRESH":    0.20,
            "MID_ROTTEN":   0.65,
            "ROTTEN":       0.95,
            # Generic fallbacks
            "UNCERTAIN":    0.5,
            "UNKNOWN":      0.5,
            "NOT_INSTALLED": 0.0,
        }

        # ── Pillar 1: RGB model ───────────────────────────────────────────────
        if self._rgb_onnx.available and rgb_images:
            rgb_scores = [LABEL_ROT_SCORE.get(self._rgb_onnx.predict(img)[0], 0.5)
                          for img in rgb_images]
            p1_score = float(np.mean(rgb_scores))
            p1_source = "rgb_onnx_v1"
        else:
            # Fallback to heuristic for RGB
            rgb_feats = [ImageAnalyzer.analyze_rgb(img) for img in rgb_images]
            uv_feats  = [ImageAnalyzer.analyze_uv(img)  for img in uv_images]
            agg       = ImageAnalyzer.aggregate_features(rgb_feats, uv_feats)
            p1_score  = agg["rgb_rot_score"]
            p1_source = "rgb_rule_based"

        # ── Pillar 2: UV model ────────────────────────────────────────────────
        if self._uv_onnx.available and uv_images:
            uv_scores = [LABEL_ROT_SCORE.get(self._uv_onnx.predict(img)[0], 0.5)
                         for img in uv_images]
            p2_score = float(np.mean(uv_scores))
            p2_source = "uv_onnx_v1"
        else:
            # Fallback to heuristic for UV
            if not self._rgb_onnx.available:
                # agg already computed above
                p2_score = agg.get("uv_fluorescence_score", 0.0)
            else:
                uv_feats  = [ImageAnalyzer.analyze_uv(img) for img in uv_images]
                rgb_feats = [ImageAnalyzer.analyze_rgb(img) for img in rgb_images]
                agg       = ImageAnalyzer.aggregate_features(rgb_feats, uv_feats)
                p2_score  = agg["uv_fluorescence_score"]
            p2_source = "uv_rule_based"

        # ── Pillar 3: BME688 gas — enhanced multi-feature analytics ───────────
        p3_score = self._gas_score(gas_delta, gas_ratio_pct, gas_slope_per_sec, produce_name)

        # ── Weighted fusion ───────────────────────────────────────────────────
        fused = p1_score * 0.40 + p2_score * 0.35 + p3_score * 0.25

        confidence_rotten  = fused * 100.0
        confidence_healthy = (1.0 - fused) * 100.0

        # 4-tier status mapping from fused score
        if fused >= 0.60:
            status     = "ROTTEN"
            confidence = confidence_rotten
        elif fused >= 0.40:
            status     = "MID_ROTTEN"
            confidence = confidence_rotten
        elif fused >= 0.18:
            status     = "MID_FRESH"
            confidence = confidence_healthy
        else:
            status     = "FRESH"
            confidence = confidence_healthy

        confidence = round(min(99.9, max(50.1, confidence)), 1)

        # Gas override: strong VOC signal overrules a FRESH/MID_FRESH neural decision
        if p3_score > 0.7 and status in ("FRESH", "MID_FRESH"):
            status     = "MID_ROTTEN"
            confidence = min(confidence, 70.0)
            reason = (
                f"Neural models voted {status} (RGB: {p1_score:.2f}, UV: {p2_score:.2f}) "
                f"but gas sensor detected strong VOC signal "
                f"(DeltaGas={gas_delta:.1f} kOhm, Drop={gas_ratio_pct:.1f}%, "
                f"Slope={gas_slope_per_sec:+.4f}, {rot_suspicion}). "
                f"Result upgraded to MID_ROTTEN."
            )
        else:
            reason = (
                f"RGB model ({p1_source}) rot score: {p1_score:.2f}. "
                f"UV model ({p2_source}) fluorescence score: {p2_score:.2f}. "
                f"Gas sensor: {rot_suspicion} (DeltaGas={gas_delta:.1f} kOhm, Drop={gas_ratio_pct:.1f}%, Slope={gas_slope_per_sec:+.4f}). "
                f"Fused score: {fused:.2f} -> {status}."
            )

        model_used = f"rgb={p1_source},uv={p2_source},gas=enhanced_analytics"

        return {
            "status":      status,
            "confidence":  confidence,
            "reason":      reason,
            "model_used":  model_used,
            "pillar_scores": {
                "rgb_neural": round(p1_score, 3),
                "uv_neural":  round(p2_score, 3),
                "gas_voc":    round(p3_score, 3),
                "fused":      round(fused, 3),
            },
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _gas_score(gas_delta: float, gas_ratio_pct: float = 0.0, gas_slope_per_sec: float = 0.0, produce_name: str = "default") -> float:
        """
        Convert gas analytics (delta, percentage drop, slope) to 0–1 rot probability score.
        Uses PRODUCE_GAS_PROFILES for produce-specific thresholds (Tomato, Apple, Eggplant).
        """
        profile = PRODUCE_GAS_PROFILES.get((produce_name or "").title(), PRODUCE_GAS_PROFILES["default"])
        fresh_r, fresh_d = profile["FRESH"]
        midf_r,  midf_d  = profile["MID_FRESH"]
        midr_r,  midr_d  = profile["MID_ROTTEN"]

        if gas_ratio_pct > 0:
            if gas_ratio_pct >= midr_r:
                base_score = 0.95
            elif gas_ratio_pct >= midf_r:
                base_score = 0.65
            elif gas_ratio_pct >= fresh_r:
                base_score = 0.30
            else:
                base_score = 0.05
        else:
            if gas_delta >= midr_d:
                base_score = 0.95
            elif gas_delta >= midf_d:
                base_score = 0.65
            elif gas_delta >= fresh_d:
                base_score = 0.30
            else:
                base_score = 0.05

        # Rate of change modifier: steep negative slope confirms active fruit decomposition
        if gas_slope_per_sec < -0.15:
            base_score = min(1.0, base_score + 0.15)
        elif gas_slope_per_sec < -0.05:
            base_score = min(1.0, base_score + 0.08)
        elif gas_slope_per_sec > 0.04 and base_score > 0.2:
            base_score = max(0.05, base_score - 0.12)

        return round(base_score, 3)

    @staticmethod
    def _build_reason(status, p1, p2, p3, agg, gas_delta, rot_suspicion) -> str:
        parts = []
        if p1 > 0.4:
            parts.append(
                f"Surface analysis detected {agg['rgb_brown_ratio']*100:.0f}% browning "
                f"and {agg['rgb_dark_ratio']*100:.0f}% dark necrotic patches (Pillar 1 RGB)"
            )
        if p2 > 0.3:
            parts.append(
                f"UV fluorescence detected {agg['uv_green_ratio']*100:.0f}% green and "
                f"{agg['uv_yellow_ratio']*100:.0f}% yellow glow -- fungal mould indicator "
                f"(Pillar 2 UV-A 365nm)"
            )
        if p3 > 0.1:
            parts.append(
                f"BME688 VOC gas resistance dropped {gas_delta:.1f} kOhm "
                f"({rot_suspicion} suspicion) -- internal decomposition indicator (Pillar 3)"
            )
        if not parts:
            parts.append("No significant rot indicators detected across all three sensor pillars")
        return ". ".join(parts) + "."


# Global singleton
_classifier: AIClassifier = None


def get_classifier() -> AIClassifier:
    """Get or create the singleton AIClassifier instance."""
    global _classifier
    if _classifier is None:
        _classifier = AIClassifier()
    return _classifier
