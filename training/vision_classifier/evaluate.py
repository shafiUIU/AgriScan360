"""
evaluate.py -- AgriScan 360 Produce Classifier Evaluation Script
=================================================================
Loads best checkpoint and runs a full evaluation on the test set.

Usage:
    python training/vision_classifier/evaluate.py
    python training/vision_classifier/evaluate.py --checkpoint path/to/model.pth
    python training/vision_classifier/evaluate.py --show-mistakes  # print misclassified images

Outputs:
    - Full classification report (precision/recall/F1 per class)
    - Confusion matrix (saved as PNG)
    - Per-class accuracy breakdown
    - Top misclassification pairs
"""

import argparse
import logging
import os
import sys

import torch
import torch.nn as nn
from torch.cuda.amp import autocast

import numpy as np
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    accuracy_score,
)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as cfg
from dataset import setup_data
from model import build_model

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("agriscan.evaluate")


# =============================================================================
# Load checkpoint
# =============================================================================

def load_checkpoint(checkpoint_path: str, device: torch.device):
    """Load a saved checkpoint and rebuild the model."""
    log.info("Loading checkpoint: %s", checkpoint_path)
    ckpt = torch.load(checkpoint_path, map_location=device)

    model_name  = ckpt.get("model_name",  cfg.MODEL_NAME)
    num_classes = ckpt.get("num_classes", cfg.NUM_CLASSES)
    class_names = ckpt.get("class_names", cfg.PRODUCE_CLASSES)
    image_size  = ckpt.get("image_size",  cfg.IMAGE_SIZE)
    best_val    = ckpt.get("best_val_acc", 0.0)

    model = build_model(model_name=model_name, num_classes=num_classes, pretrained=False)
    model.load_state_dict(ckpt["model_state"])
    model = model.to(device)
    model.eval()

    log.info(
        "Loaded: %s | Val Acc at save: %.4f | Classes: %s",
        model_name, best_val, class_names,
    )
    return model, class_names, image_size


# =============================================================================
# Full evaluation
# =============================================================================

@torch.no_grad()
def run_evaluation(model, test_loader, device, use_amp, class_names, show_mistakes=False):
    all_preds   = []
    all_labels  = []
    all_paths   = []

    for batch_idx, batch in enumerate(test_loader):
        if len(batch) == 3:
            images, labels, paths = batch
        else:
            images, labels = batch
            paths = [f"batch{batch_idx}_img{i}" for i in range(len(labels))]

        images = images.to(device, non_blocking=True)
        with autocast(enabled=use_amp):
            logits = model(images)

        preds = logits.argmax(dim=1).cpu().tolist()
        all_preds.extend(preds)
        all_labels.extend(labels.tolist())
        all_paths.extend(paths if isinstance(paths, list) else list(paths))

    # ------------------------------------------------------------------
    # Classification report
    # ------------------------------------------------------------------
    print("\n" + "=" * 65)
    print("  AGRISCAN 360 -- PRODUCE CLASSIFIER -- TEST EVALUATION")
    print("=" * 65)

    report = classification_report(
        all_labels, all_preds,
        target_names=class_names,
        digits=4,
    )
    print(report)

    overall_acc = accuracy_score(all_labels, all_preds)
    print(f"  Overall Accuracy : {overall_acc:.4f}  ({overall_acc*100:.2f}%)")

    # ------------------------------------------------------------------
    # Per-class accuracy
    # ------------------------------------------------------------------
    print("\n  Per-Class Accuracy:")
    cm = confusion_matrix(all_labels, all_preds)
    per_class_acc = cm.diagonal() / cm.sum(axis=1)
    for cls, acc in zip(class_names, per_class_acc):
        bar = "#" * int(acc * 30)
        print(f"    {cls:<12} : {acc:.4f}  [{bar}]")

    # ------------------------------------------------------------------
    # Misclassification analysis
    # ------------------------------------------------------------------
    print("\n  Common Misclassifications (predicted != actual):")
    mistakes = {}
    for label, pred in zip(all_labels, all_preds):
        if pred != label:
            key = (class_names[label], class_names[pred])
            mistakes[key] = mistakes.get(key, 0) + 1

    if mistakes:
        sorted_mistakes = sorted(mistakes.items(), key=lambda x: x[1], reverse=True)
        for (actual, predicted), count in sorted_mistakes[:10]:
            print(f"    Actual: {actual:<12} -> Predicted: {predicted:<12} | Count: {count}")
    else:
        print("    None! Perfect classification on test set.")

    # Show specific misclassified image paths
    if show_mistakes and mistakes:
        print("\n  Misclassified image paths (first 20):")
        count = 0
        for i, (label, pred) in enumerate(zip(all_labels, all_preds)):
            if pred != label and count < 20:
                path = all_paths[i] if i < len(all_paths) else "unknown"
                print(
                    f"    [{class_names[label]} -> {class_names[pred]}] {path}"
                )
                count += 1

    # ------------------------------------------------------------------
    # Confusion matrix plot
    # ------------------------------------------------------------------
    os.makedirs(cfg.RESULTS_DIR, exist_ok=True)
    fig, ax = plt.subplots(figsize=(6, 5))
    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        cmap="Blues",
        xticklabels=class_names,
        yticklabels=class_names,
        ax=ax,
    )
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    ax.set_title("Produce ID -- Confusion Matrix (Test Set)")
    plt.tight_layout()
    out_path = cfg.CONFUSION_MATRIX_PNG
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"\n  Confusion matrix saved: {out_path}")
    print("=" * 65 + "\n")

    return overall_acc, cm


# =============================================================================
# Entry point
# =============================================================================

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="AgriScan 360 -- Evaluate Produce Classifier")
    ap.add_argument(
        "--checkpoint",
        type=str,
        default=cfg.BEST_CHECKPOINT,
        help="Path to .pth checkpoint file (default: %(default)s)",
    )
    ap.add_argument(
        "--show-mistakes",
        action="store_true",
        help="Print paths of misclassified images",
    )
    ap.add_argument(
        "--no-amp",
        action="store_true",
        help="Disable mixed precision during evaluation",
    )
    args = ap.parse_args()

    if not os.path.isfile(args.checkpoint):
        log.error("Checkpoint not found: %s", args.checkpoint)
        log.error("Run train.py first to generate a checkpoint.")
        sys.exit(1)

    device  = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    use_amp = torch.cuda.is_available() and not args.no_amp

    model, class_names, image_size = load_checkpoint(args.checkpoint, device)

    # Rebuild data with same config
    # Only need test loader but setup_data returns all three
    _, _, test_loader, _ = setup_data(cfg)

    run_evaluation(
        model=model,
        test_loader=test_loader,
        device=device,
        use_amp=use_amp,
        class_names=class_names,
        show_mistakes=args.show_mistakes,
    )
