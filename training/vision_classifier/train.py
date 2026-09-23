"""
train.py -- AgriScan 360 Produce Classifier Training Script
============================================================
Usage:
    python training/vision_classifier/train.py
    python training/vision_classifier/train.py --model efficientnetv2_s
    python training/vision_classifier/train.py --model resnet50 --epochs 30
    python training/vision_classifier/train.py --no-amp   # disable mixed precision

Outputs:
    checkpoints/best_model.pth          -- best val accuracy checkpoint
    results/training_log.csv            -- per-epoch metrics
    results/confusion_matrix.png        -- confusion matrix on test set (after training)
"""

import argparse
import csv
import logging
import os
import sys
import time

import torch
import torch.nn as nn
import torch.optim as optim
from torch.cuda.amp import GradScaler, autocast

from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as cfg
from dataset import setup_data
from model import build_model, count_parameters, print_model_summary

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("agriscan.train")


# =============================================================================
# Training epoch
# =============================================================================

def train_one_epoch(model, loader, criterion, optimizer, scaler, device, use_amp):
    model.train()
    running_loss = 0.0
    all_preds, all_labels = [], []

    for images, labels in loader:
        images = images.to(device, non_blocking=True)
        labels = labels.to(device, non_blocking=True)

        optimizer.zero_grad(set_to_none=True)

        with autocast(enabled=use_amp):
            logits = model(images)
            loss   = criterion(logits, labels)

        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        nn.utils.clip_grad_norm_(model.parameters(), cfg.GRAD_CLIP_NORM)
        scaler.step(optimizer)
        scaler.update()

        running_loss += loss.item() * images.size(0)
        preds = logits.argmax(dim=1).cpu().tolist()
        all_preds.extend(preds)
        all_labels.extend(labels.cpu().tolist())

    n   = len(loader.dataset)
    avg_loss = running_loss / n
    acc  = accuracy_score(all_labels, all_preds)
    return avg_loss, acc


# =============================================================================
# Validation / Test epoch
# =============================================================================

@torch.no_grad()
def evaluate(model, loader, criterion, device, use_amp, class_names=None):
    model.eval()
    running_loss = 0.0
    all_preds, all_labels = [], []

    for images, labels in loader:
        images = images.to(device, non_blocking=True)
        labels = labels.to(device, non_blocking=True)

        with autocast(enabled=use_amp):
            logits = model(images)
            loss   = criterion(logits, labels)

        running_loss += loss.item() * images.size(0)
        preds = logits.argmax(dim=1).cpu().tolist()
        all_preds.extend(preds)
        all_labels.extend(labels.cpu().tolist())

    n        = len(loader.dataset)
    avg_loss = running_loss / n
    acc  = accuracy_score(all_labels, all_preds)
    prec = precision_score(all_labels, all_preds, average="weighted", zero_division=0)
    rec  = recall_score(all_labels, all_preds, average="weighted", zero_division=0)
    f1   = f1_score(all_labels, all_preds, average="weighted", zero_division=0)

    return avg_loss, acc, prec, rec, f1, all_preds, all_labels


# =============================================================================
# Main training loop
# =============================================================================

def train(model_name=None, num_epochs=None, use_amp=None):
    model_name = model_name or cfg.MODEL_NAME
    num_epochs = num_epochs or cfg.NUM_EPOCHS
    use_amp    = use_amp if use_amp is not None else cfg.USE_AMP

    os.makedirs(cfg.CHECKPOINT_DIR, exist_ok=True)
    os.makedirs(cfg.RESULTS_DIR, exist_ok=True)

    # -------------------------------------------------------------------------
    # Device
    # -------------------------------------------------------------------------
    if torch.cuda.is_available():
        device = torch.device("cuda")
        log.info("GPU detected: %s", torch.cuda.get_device_name(0))
    else:
        device = torch.device("cpu")
        log.warning("No GPU detected -- training on CPU (much slower).")
        use_amp = False

    # -------------------------------------------------------------------------
    # Data
    # -------------------------------------------------------------------------
    log.info("Setting up dataset ...")
    train_loader, val_loader, test_loader, class_names = setup_data(cfg)

    # -------------------------------------------------------------------------
    # Model
    # -------------------------------------------------------------------------
    print_model_summary(model_name)
    model = build_model(
        model_name  = model_name,
        num_classes = cfg.NUM_CLASSES,
        pretrained  = cfg.PRETRAINED,
    )
    model = model.to(device)
    log.info("Trainable parameters: %s", f"{count_parameters(model):,}")

    # -------------------------------------------------------------------------
    # Loss, Optimizer, Scheduler, Scaler
    # -------------------------------------------------------------------------
    criterion = nn.CrossEntropyLoss(label_smoothing=cfg.LABEL_SMOOTHING)
    optimizer = optim.AdamW(
        model.parameters(),
        lr=cfg.LEARNING_RATE,
        weight_decay=cfg.WEIGHT_DECAY,
    )
    scheduler = optim.lr_scheduler.CosineAnnealingWarmRestarts(
        optimizer,
        T_0=cfg.LR_T_MAX,
        eta_min=cfg.LR_ETA_MIN,
    )
    scaler = GradScaler(enabled=use_amp)

    # -------------------------------------------------------------------------
    # Training log CSV
    # -------------------------------------------------------------------------
    csv_fields = [
        "epoch", "lr",
        "train_loss", "train_acc",
        "val_loss",   "val_acc", "val_prec", "val_rec", "val_f1",
    ]
    csv_fh  = open(cfg.TRAINING_LOG_CSV, "w", newline="")
    writer  = csv.DictWriter(csv_fh, fieldnames=csv_fields)
    writer.writeheader()

    # -------------------------------------------------------------------------
    # Training loop with early stopping
    # -------------------------------------------------------------------------
    best_val_acc   = 0.0
    patience_count = 0

    log.info("Starting training: %s | %d epochs | AMP=%s", model_name, num_epochs, use_amp)
    log.info("Classes: %s", class_names)

    for epoch in range(1, num_epochs + 1):
        t0 = time.time()
        current_lr = optimizer.param_groups[0]["lr"]

        train_loss, train_acc = train_one_epoch(
            model, train_loader, criterion, optimizer, scaler, device, use_amp
        )

        val_loss, val_acc, val_prec, val_rec, val_f1, _, _ = evaluate(
            model, val_loader, criterion, device, use_amp, class_names
        )

        scheduler.step()
        elapsed = time.time() - t0

        # Log
        log.info(
            "Epoch %3d/%d | LR: %.2e | "
            "Train Loss: %.4f Acc: %.4f | "
            "Val Loss: %.4f Acc: %.4f P: %.4f R: %.4f F1: %.4f | "
            "%.1fs",
            epoch, num_epochs, current_lr,
            train_loss, train_acc,
            val_loss, val_acc, val_prec, val_rec, val_f1,
            elapsed,
        )

        writer.writerow({
            "epoch":      epoch,
            "lr":         f"{current_lr:.2e}",
            "train_loss": f"{train_loss:.6f}",
            "train_acc":  f"{train_acc:.6f}",
            "val_loss":   f"{val_loss:.6f}",
            "val_acc":    f"{val_acc:.6f}",
            "val_prec":   f"{val_prec:.6f}",
            "val_rec":    f"{val_rec:.6f}",
            "val_f1":     f"{val_f1:.6f}",
        })
        csv_fh.flush()

        # Save best checkpoint
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            patience_count = 0
            torch.save({
                "epoch":       epoch,
                "model_name":  model_name,
                "class_names": class_names,
                "num_classes": cfg.NUM_CLASSES,
                "image_size":  cfg.IMAGE_SIZE,
                "model_state": model.state_dict(),
                "optimizer_state": optimizer.state_dict(),
                "best_val_acc": best_val_acc,
            }, cfg.BEST_CHECKPOINT)
            log.info("  -> New best checkpoint saved! Val Acc: %.4f", best_val_acc)
        else:
            patience_count += 1
            log.info(
                "  -> No improvement. Patience: %d/%d",
                patience_count, cfg.EARLY_STOP_PATIENCE,
            )
            if patience_count >= cfg.EARLY_STOP_PATIENCE:
                log.info("Early stopping triggered at epoch %d.", epoch)
                break

    csv_fh.close()
    log.info("Training complete. Best Val Acc: %.4f", best_val_acc)
    log.info("Checkpoint saved to: %s", cfg.BEST_CHECKPOINT)

    # -------------------------------------------------------------------------
    # Final evaluation on test set
    # -------------------------------------------------------------------------
    log.info("Loading best checkpoint for test evaluation ...")
    ckpt = torch.load(cfg.BEST_CHECKPOINT, map_location=device)
    model.load_state_dict(ckpt["model_state"])

    test_loss, test_acc, test_prec, test_rec, test_f1, test_preds, test_labels = evaluate(
        model, test_loader, criterion, device, use_amp, class_names
    )

    log.info("=== TEST SET RESULTS ===")
    log.info("  Accuracy  : %.4f", test_acc)
    log.info("  Precision : %.4f", test_prec)
    log.info("  Recall    : %.4f", test_rec)
    log.info("  F1 Score  : %.4f", test_f1)

    # Save confusion matrix
    try:
        _save_confusion_matrix(test_labels, test_preds, class_names)
    except Exception as exc:
        log.warning("Could not save confusion matrix: %s", exc)

    return model, class_names


# =============================================================================
# Helpers
# =============================================================================

def _save_confusion_matrix(labels, preds, class_names):
    import matplotlib.pyplot as plt
    import seaborn as sns
    from sklearn.metrics import confusion_matrix

    cm = confusion_matrix(labels, preds)
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
    ax.set_title("Confusion Matrix -- Test Set")
    plt.tight_layout()
    os.makedirs(cfg.RESULTS_DIR, exist_ok=True)
    fig.savefig(cfg.CONFUSION_MATRIX_PNG, dpi=150)
    plt.close(fig)
    log.info("Confusion matrix saved: %s", cfg.CONFUSION_MATRIX_PNG)


# =============================================================================
# CLI entry point
# =============================================================================

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="AgriScan 360 Produce Classifier Trainer")
    ap.add_argument(
        "--model",
        type=str,
        default=cfg.MODEL_NAME,
        choices=["efficientnet_b0", "efficientnet_b2", "efficientnetv2_s",
                 "convnext_tiny", "resnet50"],
        help="Model architecture (default: %(default)s)",
    )
    ap.add_argument(
        "--epochs",
        type=int,
        default=cfg.NUM_EPOCHS,
        help="Max training epochs (default: %(default)s)",
    )
    ap.add_argument(
        "--no-amp",
        action="store_true",
        help="Disable mixed precision training (AMP)",
    )
    args = ap.parse_args()

    train(
        model_name=args.model,
        num_epochs=args.epochs,
        use_amp=not args.no_amp,
    )
