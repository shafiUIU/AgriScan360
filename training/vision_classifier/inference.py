"""
inference.py -- AgriScan 360 Produce Classifier Inference Engine
=================================================================
Runs produce identification on a single image using the ONNX model.

Usage (command line):
    python training/vision_classifier/inference.py --image path/to/apple.jpg
    python training/vision_classifier/inference.py --image photo.jpg --model produce_classifier.onnx

Usage (Python import):
    from training.vision_classifier.inference import ProduceInferenceEngine
    engine = ProduceInferenceEngine()
    result = engine.predict_file("apple.jpg")
    # -> {"class": "Apple", "confidence": 0.97, "all_scores": {...}}

    result = engine.predict_bytes(jpeg_bytes)
    # -> same format, from raw JPEG bytes (used by laptop_server/ai_engine.py)

Output format:
    {
        "class":      "Apple",          # or "Tomato", "Eggplant", or "Unknown"
        "confidence": 0.97,             # 0.0 - 1.0 float
        "all_scores": {
            "Apple":    0.97,
            "Eggplant": 0.02,
            "Tomato":   0.01,
        }
    }

Integration note:
    This replaces the fragile _classify_image_bytes() color heuristic in
    pi_client/main.py. After training:
      1. Run export.py -> places produce_classifier.onnx in laptop_server/models/
      2. laptop_server/ai_engine.py loads ProduceInferenceEngine()
      3. Pi sends detect snapshot to laptop, engine returns produce name
"""

import argparse
import io
import json
import logging
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as cfg

log = logging.getLogger(__name__)

# ImageNet normalization constants (must match training)
_MEAN = np.array(cfg.IMAGENET_MEAN, dtype=np.float32).reshape(3, 1, 1)
_STD  = np.array(cfg.IMAGENET_STD,  dtype=np.float32).reshape(3, 1, 1)


# =============================================================================
# Inference Engine
# =============================================================================

class ProduceInferenceEngine:
    """
    ONNX-based produce classifier.
    Lazy-loads the model on first inference call.
    Thread-safe for concurrent inference requests.
    """

    def __init__(self, onnx_path: str = None, class_names: list = None):
        self._onnx_path   = onnx_path or cfg.ONNX_PATH
        self._class_names = class_names or cfg.PRODUCE_CLASSES
        self._image_size  = cfg.IMAGE_SIZE
        self._session     = None

    def _load_session(self):
        """Lazy-load ONNX session on first call."""
        if self._session is not None:
            return

        if not os.path.isfile(self._onnx_path):
            raise FileNotFoundError(
                f"ONNX model not found: {self._onnx_path}\n"
                "Run training/vision_classifier/export.py first."
            )

        try:
            import onnxruntime as ort
        except ImportError:
            raise RuntimeError(
                "onnxruntime not installed. "
                "Run: pip install onnxruntime-gpu"
            )

        providers = (
            ["CUDAExecutionProvider", "CPUExecutionProvider"]
            if _has_cuda()
            else ["CPUExecutionProvider"]
        )
        self._session = ort.InferenceSession(
            self._onnx_path,
            providers=providers,
        )
        actual = self._session.get_providers()
        log.info(
            "ProduceInferenceEngine loaded: %s | Provider: %s | Classes: %s",
            os.path.basename(self._onnx_path),
            actual[0],
            self._class_names,
        )

    def _preprocess(self, img_rgb: "PIL.Image.Image") -> np.ndarray:
        """
        Preprocess a PIL RGB image to model input tensor.
        Matches the eval_transform from training.
        """
        size = self._image_size + 32

        # Resize then centre crop
        img_rgb = img_rgb.resize((size, size), resample=3)  # LANCZOS=1, BICUBIC=3
        left  = (size - self._image_size) // 2
        top   = (size - self._image_size) // 2
        img_rgb = img_rgb.crop((
            left, top,
            left + self._image_size,
            top  + self._image_size,
        ))

        # HWC -> CHW float32
        arr = np.array(img_rgb, dtype=np.float32) / 255.0
        arr = arr.transpose(2, 0, 1)

        # ImageNet normalization
        arr = (arr - _MEAN) / _STD

        # Add batch dimension
        return arr[np.newaxis, :, :, :]    # [1, 3, H, W]

    def _run(self, tensor: np.ndarray) -> dict:
        """Run ONNX session and return result dict."""
        self._load_session()
        logits = self._session.run(None, {"image": tensor})[0][0]  # [num_classes]

        # Softmax
        e = np.exp(logits - logits.max())
        probs = e / e.sum()

        top_idx  = int(np.argmax(probs))
        top_conf = float(probs[top_idx])
        top_cls  = self._class_names[top_idx]

        all_scores = {
            cls: float(probs[i])
            for i, cls in enumerate(self._class_names)
        }

        return {
            "class":      top_cls,
            "confidence": round(top_conf, 4),
            "all_scores": {k: round(v, 4) for k, v in all_scores.items()},
        }

    def predict_file(self, image_path: str) -> dict:
        """
        Classify a produce image from a file path.

        Returns:
            {"class": "Apple", "confidence": 0.97, "all_scores": {...}}
        """
        from PIL import Image
        try:
            img = Image.open(image_path).convert("RGB")
            tensor = self._preprocess(img)
            return self._run(tensor)
        except Exception as exc:
            log.error("Inference failed for %s: %s", image_path, exc)
            return {"class": "Unknown", "confidence": 0.0, "all_scores": {}}

    def predict_bytes(self, image_bytes: bytes) -> dict:
        """
        Classify a produce image from raw JPEG/PNG bytes.
        Used by laptop_server/ai_engine.py when the Pi sends a detect snapshot.

        Returns:
            {"class": "Apple", "confidence": 0.97, "all_scores": {...}}
        """
        from PIL import Image
        try:
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            tensor = self._preprocess(img)
            return self._run(tensor)
        except Exception as exc:
            log.error("Inference failed (bytes input): %s", exc)
            return {"class": "Unknown", "confidence": 0.0, "all_scores": {}}

    def is_loaded(self) -> bool:
        return self._session is not None

    def warmup(self):
        """Pre-load the session and run a dummy forward pass."""
        self._load_session()
        dummy = np.zeros((1, 3, self._image_size, self._image_size), dtype=np.float32)
        self._session.run(None, {"image": dummy})
        log.info("ProduceInferenceEngine warmup complete.")


# =============================================================================
# Helpers
# =============================================================================

def _has_cuda() -> bool:
    try:
        import onnxruntime as ort
        return "CUDAExecutionProvider" in ort.get_available_providers()
    except ImportError:
        return False


# =============================================================================
# CLI entry point
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    ap = argparse.ArgumentParser(
        description="AgriScan 360 -- Produce Classifier Inference"
    )
    ap.add_argument(
        "--image",
        type=str,
        required=True,
        help="Path to a produce image file (JPEG/PNG)",
    )
    ap.add_argument(
        "--model",
        type=str,
        default=cfg.ONNX_PATH,
        help="Path to ONNX model file (default: %(default)s)",
    )
    ap.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON only (for scripting)",
    )
    args = ap.parse_args()

    engine = ProduceInferenceEngine(onnx_path=args.model)
    result = engine.predict_file(args.image)

    if args.json:
        print(json.dumps(result))
    else:
        print("\n+--- AgriScan 360 Produce Identification ---+")
        print(f"  Image      : {args.image}")
        print(f"  Prediction : {result['class']}")
        print(f"  Confidence : {result['confidence']*100:.1f}%")
        print("  All scores :")
        for cls, score in sorted(result["all_scores"].items(),
                                  key=lambda x: x[1], reverse=True):
            bar = "#" * int(score * 30)
            print(f"    {cls:<12} : {score:.4f}  [{bar}]")
        print("+-------------------------------------------+\n")
