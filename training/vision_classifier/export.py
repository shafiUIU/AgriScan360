"""
export.py -- AgriScan 360 Produce Classifier Model Exporter
============================================================
Exports the trained model checkpoint to:
  1. .pth  -- PyTorch state dict (for continued training or loading in Python)
  2. .onnx -- ONNX (for onnxruntime inference on laptop without PyTorch)

Usage:
    python training/vision_classifier/export.py
    python training/vision_classifier/export.py --checkpoint path/to/model.pth
    python training/vision_classifier/export.py --onnx-path custom/path/model.onnx

The ONNX model will be placed in laptop_server/models/produce_classifier.onnx
by default, ready to be loaded by the inference engine.

ONNX model spec:
    Input:  float32 [1, 3, IMAGE_SIZE, IMAGE_SIZE]  -- ImageNet-normalized NCHW
    Output: float32 [1, NUM_CLASSES]                -- raw logits
    Apply softmax at inference to get probabilities.
"""

import argparse
import logging
import os
import sys

import torch
import torch.nn as nn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as cfg
from model import build_model

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("agriscan.export")


# =============================================================================
# ONNX export
# =============================================================================

def export_onnx(model: nn.Module, onnx_path: str, image_size: int, opset: int):
    """Export model to ONNX and verify output matches PyTorch."""
    os.makedirs(os.path.dirname(os.path.abspath(onnx_path)), exist_ok=True)

    model.eval()
    device = next(model.parameters()).device
    dummy  = torch.zeros(1, 3, image_size, image_size, device=device)

    log.info("Exporting to ONNX: %s", onnx_path)
    log.info("  Input shape : [1, 3, %d, %d]", image_size, image_size)
    log.info("  ONNX opset  : %d", opset)

    with torch.no_grad():
        torch.onnx.export(
            model,
            dummy,
            onnx_path,
            opset_version=opset,
            input_names=["image"],
            output_names=["logits"],
            dynamic_axes={
                "image":  {0: "batch_size"},
                "logits": {0: "batch_size"},
            },
            do_constant_folding=True,
            export_params=True,
            verbose=False,
        )

    # Verify ONNX model integrity
    try:
        import onnx
        onnx_model = onnx.load(onnx_path)
        onnx.checker.check_model(onnx_model)
        log.info("  ONNX model check: PASS")
    except ImportError:
        log.warning("  onnx package not installed -- skipping integrity check.")
    except Exception as exc:
        log.error("  ONNX model check FAILED: %s", exc)
        return False

    # Verify numerical consistency: PyTorch output vs ONNX output
    try:
        import onnxruntime as ort
        import numpy as np

        sess = ort.InferenceSession(
            onnx_path,
            providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
        )
        dummy_np = dummy.cpu().numpy()
        with torch.no_grad():
            pt_out = model(dummy).cpu().numpy()
        ort_out = sess.run(None, {"image": dummy_np})[0]

        max_diff = float(np.abs(pt_out - ort_out).max())
        log.info("  PyTorch vs ONNX max output diff: %.6f", max_diff)
        if max_diff < 1e-4:
            log.info("  Numerical consistency check: PASS")
        else:
            log.warning(
                "  Numerical consistency: diff %.6f > 1e-4. "
                "Check model architecture.",
                max_diff,
            )
    except ImportError:
        log.warning("  onnxruntime not installed -- skipping numerical check.")

    file_mb = os.path.getsize(onnx_path) / (1024 * 1024)
    log.info("  ONNX file size: %.1f MB", file_mb)
    return True


# =============================================================================
# PTH export
# =============================================================================

def export_pth(model: nn.Module, pth_path: str, class_names: list,
               model_name: str, image_size: int, best_val_acc: float):
    """Save final state dict as a clean .pth file for distribution."""
    os.makedirs(os.path.dirname(os.path.abspath(pth_path)), exist_ok=True)
    payload = {
        "model_name":   model_name,
        "num_classes":  len(class_names),
        "class_names":  class_names,
        "image_size":   image_size,
        "best_val_acc": best_val_acc,
        "model_state":  model.state_dict(),
    }
    torch.save(payload, pth_path)
    file_mb = os.path.getsize(pth_path) / (1024 * 1024)
    log.info("  .pth saved: %s  (%.1f MB)", pth_path, file_mb)


# =============================================================================
# Main
# =============================================================================

def export(checkpoint_path: str = None, onnx_path: str = None):
    checkpoint_path = checkpoint_path or cfg.BEST_CHECKPOINT
    onnx_path       = onnx_path       or cfg.ONNX_PATH

    if not os.path.isfile(checkpoint_path):
        log.error("Checkpoint not found: %s", checkpoint_path)
        log.error("Run train.py first.")
        sys.exit(1)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    log.info("Export device: %s", device)

    # Load checkpoint
    ckpt = torch.load(checkpoint_path, map_location=device)
    model_name  = ckpt.get("model_name",  cfg.MODEL_NAME)
    class_names = ckpt.get("class_names", cfg.PRODUCE_CLASSES)
    num_classes = ckpt.get("num_classes", cfg.NUM_CLASSES)
    image_size  = ckpt.get("image_size",  cfg.IMAGE_SIZE)
    best_val    = ckpt.get("best_val_acc", 0.0)

    model = build_model(model_name=model_name, num_classes=num_classes, pretrained=False)
    model.load_state_dict(ckpt["model_state"])
    model = model.to(device)
    model.eval()

    log.info("Loaded checkpoint: %s | Val Acc: %.4f", model_name, best_val)
    log.info("Classes: %s", class_names)

    print("\n+--- Exporting Model -------------------------------------------+")

    # 1. Clean .pth
    pth_path = checkpoint_path.replace(".pth", "_final.pth")
    export_pth(model, pth_path, class_names, model_name, image_size, best_val)

    # 2. ONNX
    success = export_onnx(model, onnx_path, image_size, cfg.ONNX_OPSET)

    print("+--------------------------------------------------------------+")
    if success:
        print(f"\n  ONNX model ready at: {onnx_path}")
        print("  -> Place this file in laptop_server/models/")
        print("  -> The inference engine will auto-load it.")
        print()
        print("  Input spec  : float32 [batch, 3, {}, {}]".format(image_size, image_size))
        print("  Output spec : float32 [batch, {}]  (raw logits)".format(num_classes))
        print("  Classes     : {}".format(class_names))
        print()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="AgriScan 360 -- Export Produce Classifier")
    ap.add_argument(
        "--checkpoint",
        type=str,
        default=cfg.BEST_CHECKPOINT,
        help="Checkpoint .pth file to export",
    )
    ap.add_argument(
        "--onnx-path",
        type=str,
        default=cfg.ONNX_PATH,
        help="Output ONNX file path",
    )
    args = ap.parse_args()
    export(checkpoint_path=args.checkpoint, onnx_path=args.onnx_path)
