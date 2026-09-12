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
    MODEL_PATH, USE_AI_MODEL,
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
    """Wrapper around ONNX Runtime for trained model inference."""

    def __init__(self):
        self._session = None
        if USE_AI_MODEL and ONNX_AVAILABLE:
            try:
                self._session = ort.InferenceSession(
                    MODEL_PATH,
                    providers=["CPUExecutionProvider"]
                )
                log.info("ONNX model loaded from %s", MODEL_PATH)
            except Exception as exc:
                log.error("ONNX model load failed: %s", exc)

    @property
    def available(self):
        return self._session is not None

    def predict(self, image_bytes: bytes) -> Tuple[str, float]:
        """
        Run inference on a single image.
        Returns (class_label, confidence_0_to_1).
        Expects model to output softmax probabilities for [HEALTHY, ROTTEN, UNCERTAIN].
        """
        if not self.available:
            return "UNKNOWN", 0.0

        import numpy as np
        try:
            arr = ImageAnalyzer._load_as_array(image_bytes)
            if arr is None:
                return "UNKNOWN", 0.0
            # Resize and normalize for model input (224×224, ImageNet stats)
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
            probs      = np.exp(outputs) / np.exp(outputs).sum()   # softmax
            labels     = ["HEALTHY", "ROTTEN", "UNCERTAIN"]
            idx        = int(np.argmax(probs))
            return labels[idx], float(probs[idx])
        except Exception as exc:
            log.error("ONNX inference error: %s", exc)
            return "UNKNOWN", 0.0


# =============================================================================
# Multi-Modal Fusion Classifier (main entry point)
# =============================================================================

class AIClassifier:
    """
    The main classifier. Fuses three sensor pillars:
        Pillar 1: RGB surface analysis
        Pillar 2: UV-A fluorescence analysis
        Pillar 3: BME688 gas resistance delta

    When a trained ONNX model is available, Pillar 1+2 defer to neural inference.
    Pillar 3 (gas) always uses the rule-based approach (own dataset needed).
    """

    CLASS_LABELS = ["HEALTHY", "ROTTEN", "UNCERTAIN"]

    def __init__(self):
        self._onnx = ONNXClassifier()
        self._analyzer = ImageAnalyzer()
        log.info("AIClassifier initialized. ONNX model: %s",
                 "loaded" if self._onnx.available else "NOT loaded (rule-based mode)")

    def classify(
        self,
        rgb_images:  List[bytes],   # 8 JPEG bytes (white light, 8 angles)
        uv_images:   List[bytes],   # 8 JPEG bytes (UV light, 8 angles)
        gas_delta:   float,         # kΩ drop from BME688
        rot_suspicion: str,         # LOW / MEDIUM / HIGH
    ) -> dict:
        """
        Full multi-modal classification.
        Returns dict: {status, confidence, reason, pillar_scores, model_used}
        """
        start = time.time()

        if self._onnx.available:
            result = self._neural_classify(rgb_images, uv_images, gas_delta, rot_suspicion)
        else:
            result = self._rule_classify(rgb_images, uv_images, gas_delta, rot_suspicion)

        result["inference_ms"] = round((time.time() - start) * 1000, 1)
        log.info("Classification complete: %s (%.1f%%) in %.0fms",
                 result["status"], result["confidence"], result["inference_ms"])
        return result

    # ── Rule-Based Classifier ─────────────────────────────────────────────────

    def _rule_classify(self, rgb_images, uv_images, gas_delta, rot_suspicion) -> dict:
        """
        Heuristic multi-pillar fusion without a trained model.
        Active until you download datasets and train the ONNX model.
        """
        # Analyse all 8 angles
        rgb_feats = [ImageAnalyzer.analyze_rgb(img) for img in rgb_images]
        uv_feats  = [ImageAnalyzer.analyze_uv(img)  for img in uv_images]
        agg       = ImageAnalyzer.aggregate_features(rgb_feats, uv_feats)

        # Pillar scores (0–1, higher = worse)
        p1_score = agg["rgb_rot_score"]            # RGB surface rot
        p2_score = agg["uv_fluorescence_score"]    # UV fluorescence
        p3_score = self._gas_score(gas_delta)      # Gas VOC

        # Weighted fusion
        fused = p1_score * 0.40 + p2_score * 0.35 + p3_score * 0.25
        confidence_rotten  = fused * 100.0
        confidence_healthy = (1.0 - fused) * 100.0

        # Decision
        if fused >= 0.55:
            status     = "ROTTEN"
            confidence = confidence_rotten
        elif fused <= 0.30:
            status     = "HEALTHY"
            confidence = confidence_healthy
        else:
            status     = "UNCERTAIN"
            confidence = 100.0 - abs(confidence_rotten - 50.0) * 2

        # Clamp confidence
        confidence = round(min(99.9, max(50.1, confidence)), 1)

        # Human-readable reason
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

    def _neural_classify(self, rgb_images, uv_images, gas_delta, rot_suspicion) -> dict:
        """
        ONNX model-based classification (active when model file is present).
        Runs inference on each of the 16 images and votes.
        """
        import numpy as np
        votes = {"HEALTHY": 0, "ROTTEN": 0, "UNCERTAIN": 0}
        confs = []

        for img in rgb_images + uv_images:
            label, conf = self._onnx.predict(img)
            if label in votes:
                votes[label] += conf
                confs.append(conf)

        # Majority vote by accumulated confidence
        status = max(votes, key=votes.get)
        confidence = round((votes[status] / max(sum(confs), 1e-9)) * 100, 1)

        # Gas override: if gas strongly says rotten, don't override to healthy
        p3 = self._gas_score(gas_delta)
        if p3 > 0.7 and status == "HEALTHY":
            status = "UNCERTAIN"
            confidence = min(confidence, 70.0)
            reason = (f"Neural model voted HEALTHY but gas sensor detected strong VOC "
                      f"signal (ΔGas={gas_delta:.1f} kΩ). Result degraded to UNCERTAIN.")
        else:
            reason = (f"Neural model consensus: {status} ({confidence:.1f}% confidence). "
                      f"Gas sensor suspicion: {rot_suspicion} (ΔGas={gas_delta:.1f} kΩ).")

        return {
            "status":      status,
            "confidence":  confidence,
            "reason":      reason,
            "model_used":  "onnx_agriscan360_v1",
            "pillar_scores": {"gas_voc": round(p3, 3), "neural_votes": votes},
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _gas_score(gas_delta: float) -> float:
        """Convert gas kΩ delta to 0–1 rot probability score."""
        if gas_delta >= ROTTEN_GAS_DELTA_HIGH:
            return min(1.0, gas_delta / 10.0)   # Saturates at 10 kΩ drop
        elif gas_delta >= ROTTEN_GAS_DELTA_MED:
            return 0.4
        elif gas_delta > 0:
            return 0.1
        return 0.0   # No gas change (healthy or baseline error)

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
                f"{agg['uv_yellow_ratio']*100:.0f}% yellow glow — fungal mould indicator "
                f"(Pillar 2 UV-A 365nm)"
            )
        if p3 > 0.1:
            parts.append(
                f"BME688 VOC gas resistance dropped {gas_delta:.1f} kΩ "
                f"({rot_suspicion} suspicion) — internal decomposition indicator (Pillar 3)"
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
