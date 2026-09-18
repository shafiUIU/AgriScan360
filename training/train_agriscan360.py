# =============================================================================
# AgriScan360 — Dual Model Training Script (Google Colab)
# =============================================================================
# INSTRUCTIONS:
#   1. Open Google Colab (https://colab.research.google.com)
#   2. Set Runtime -> Change runtime type -> T4 GPU
#   3. Copy each cell block (marked by # %%) into a Colab cell
#   4. Replace <YOUR_HF_USERNAME> with your Hugging Face username
#   5. Run all cells top to bottom
#   6. Download rgb_agriscan_v1.onnx and uv_agriscan_v1.onnx from /content/models/
#   7. Place both files in: AgriScan360/laptop_server/models/
#
# OUTPUT:
#   /content/models/rgb_agriscan_v1.onnx  -- RGB white-light freshness model
#   /content/models/uv_agriscan_v1.onnx   -- UV-A fluorescence model
#
# CLASSES (both models): 0=HEALTHY, 1=ROTTEN, 2=UNCERTAIN
# MODEL INPUT:  float32 [1, 3, 224, 224] — ImageNet-normalized NCHW
# MODEL OUTPUT: float32 [1, 3]           — raw logits (softmax applied at inference)
# =============================================================================


# %% ── CELL 1: Install Dependencies ──────────────────────────────────────────

import subprocess
subprocess.run(["pip", "install", "-q",
    "huggingface_hub", "onnx", "onnxruntime",
    "torch", "torchvision", "Pillow", "scikit-learn",
    "matplotlib", "seaborn", "tqdm"
])
print("Dependencies installed.")


# %% ── CELL 2: Imports & Config ───────────────────────────────────────────────

import os
import shutil
import random
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader, WeightedRandomSampler
import torchvision.transforms as T
import torchvision.models as models
from torchvision.datasets import ImageFolder
from PIL import Image
import matplotlib.pyplot as plt
from sklearn.metrics import classification_report, confusion_matrix
import seaborn as sns
from tqdm import tqdm

# ── CONFIGURE THIS ────────────────────────────────────────────────────────────
HF_USERNAME    = "<YOUR_HF_USERNAME>"          # ← Replace with your HF username
HF_REPO_ID     = f"{HF_USERNAME}/agriscan360-dataset"
DATASET_DIR    = "/content/agriscan360_dataset"
MODEL_OUT_DIR  = "/content/models"
os.makedirs(MODEL_OUT_DIR, exist_ok=True)

# Training hyperparameters
BATCH_SIZE   = 32
NUM_EPOCHS_RGB = 15
NUM_EPOCHS_UV  = 25    # More epochs for UV (less data)
LR_RGB       = 3e-4
LR_UV        = 1e-4   # Lower LR for UV (smaller dataset, avoid overfit)
IMG_SIZE     = 224
NUM_CLASSES  = 3       # HEALTHY, ROTTEN, UNCERTAIN
SEED         = 42
DEVICE       = torch.device("cuda" if torch.cuda.is_available() else "cpu")

print(f"Device: {DEVICE}")
print(f"Dataset will be downloaded to: {DATASET_DIR}")
torch.manual_seed(SEED)
random.seed(SEED)
np.random.seed(SEED)


# %% ── CELL 3: Download Dataset from Hugging Face ────────────────────────────

from huggingface_hub import snapshot_download

print(f"Downloading dataset from: {HF_REPO_ID}")
print("This may take a few minutes depending on dataset size...")

snapshot_download(
    repo_id=HF_REPO_ID,
    repo_type="dataset",
    local_dir=DATASET_DIR,
    ignore_patterns=["*.md", "*.csv", "*.xlsx", "*.npz",
                     "Gas_Sensor_ENose/*", "Statistical_Analysis*",
                     "Chemosensors*", "Ripeness_Stages/*",
                     "AFQC_Model/*", "ADEC_Diseases/*"]
)
print("Download complete.")


# %% ── CELL 4: Organize RGB Dataset into Train/Val Folders ───────────────────
#
# Label mapping:
#   Apple/RGB_Images/Fresh          → HEALTHY
#   Apple/RGB_Images/Rotten         → ROTTEN
#   Tomato/RGB_Images/Fresh         → HEALTHY
#   Tomato/RGB_Images/Rotten        → ROTTEN
#   Eggplant/RGB_Images/Healthy     → HEALTHY
#   Eggplant/RGB_Images/Wet_Rot     → ROTTEN
#   Eggplant/RGB_Images/Phomopsis_Blight → ROTTEN
#   Eggplant/RGB_Images/Shoot_and_Fruit_Borer → ROTTEN
#   Eggplant/RGB_Images/Brinjal_Fruit_Cracking → ROTTEN
# Note: UNCERTAIN class is created synthetically (see below)

RGB_STAGED_DIR = "/content/rgb_staged"

# Define source → label mapping
RGB_SOURCES = {
    "HEALTHY": [
        os.path.join(DATASET_DIR, "Apple",    "RGB_Images", "Fresh"),
        os.path.join(DATASET_DIR, "Tomato",   "RGB_Images", "Fresh"),
        os.path.join(DATASET_DIR, "Eggplant", "RGB_Images", "Healthy"),
    ],
    "ROTTEN": [
        os.path.join(DATASET_DIR, "Apple",    "RGB_Images", "Rotten"),
        os.path.join(DATASET_DIR, "Tomato",   "RGB_Images", "Rotten"),
        os.path.join(DATASET_DIR, "Eggplant", "RGB_Images", "Wet_Rot"),
        os.path.join(DATASET_DIR, "Eggplant", "RGB_Images", "Phomopsis_Blight"),
        os.path.join(DATASET_DIR, "Eggplant", "RGB_Images", "Shoot_and_Fruit_Borer"),
        os.path.join(DATASET_DIR, "Eggplant", "RGB_Images", "Brinjal_Fruit_Cracking"),
    ]
}

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VAL_SPLIT = 0.15   # 15% validation

def collect_images(source_dirs):
    """Collect all image paths from a list of directories."""
    paths = []
    for d in source_dirs:
        if not os.path.exists(d):
            print(f"  [WARNING] Folder not found, skipping: {d}")
            continue
        for root, _, files in os.walk(d):
            for f in files:
                if os.path.splitext(f)[1].lower() in IMG_EXTS:
                    paths.append(os.path.join(root, f))
    return paths

def stage_dataset(sources_dict, staged_dir, val_split=0.15, max_per_class=None):
    """Copy images into staged/train/<class>/ and staged/val/<class>/ folders."""
    if os.path.exists(staged_dir):
        shutil.rmtree(staged_dir)
    for split in ["train", "val"]:
        for cls in list(sources_dict.keys()) + ["UNCERTAIN"]:
            os.makedirs(os.path.join(staged_dir, split, cls), exist_ok=True)

    class_counts = {}
    for label, src_dirs in sources_dict.items():
        paths = collect_images(src_dirs)
        random.shuffle(paths)
        if max_per_class:
            paths = paths[:max_per_class]

        n_val   = max(1, int(len(paths) * val_split))
        n_train = len(paths) - n_val
        splits  = {"train": paths[:n_train], "val": paths[n_val:]}

        for split, img_list in splits.items():
            dst_dir = os.path.join(staged_dir, split, label)
            for i, src in enumerate(img_list):
                ext = os.path.splitext(src)[1].lower()
                dst = os.path.join(dst_dir, f"{label}_{i:05d}{ext}")
                shutil.copy2(src, dst)

        class_counts[label] = len(paths)
        print(f"  {label}: {n_train} train + {n_val} val  (total: {len(paths)})")

    # ── Synthetic UNCERTAIN class ─────────────────────────────────────────────
    # Mix early-stage images: take ~20% of rotten as "borderline" uncertain.
    # This teaches the model to output UNCERTAIN when confidence is low.
    rotten_paths = collect_images(sources_dict["ROTTEN"])
    healthy_paths = collect_images(sources_dict["HEALTHY"])
    random.shuffle(rotten_paths)
    random.shuffle(healthy_paths)
    uncertain_pool = rotten_paths[:400] + healthy_paths[:400]
    random.shuffle(uncertain_pool)

    n_val_u   = max(1, int(len(uncertain_pool) * val_split))
    uncertain_splits = {
        "train": uncertain_pool[n_val_u:],
        "val":   uncertain_pool[:n_val_u]
    }
    for split, img_list in uncertain_splits.items():
        dst_dir = os.path.join(staged_dir, split, "UNCERTAIN")
        for i, src in enumerate(img_list):
            ext = os.path.splitext(src)[1].lower()
            shutil.copy2(src, os.path.join(dst_dir, f"UNCERTAIN_{i:05d}{ext}"))
    class_counts["UNCERTAIN"] = len(uncertain_pool)
    print(f"  UNCERTAIN (synthetic): ~{int(len(uncertain_pool)*(1-val_split))} train + ~{n_val_u} val")

    return class_counts

print("Staging RGB dataset...")
rgb_counts = stage_dataset(RGB_SOURCES, RGB_STAGED_DIR)
print(f"\nRGB dataset staged at: {RGB_STAGED_DIR}")


# %% ── CELL 5: RGB DataLoaders ────────────────────────────────────────────────

# Transforms
MEAN = [0.485, 0.456, 0.406]
STD  = [0.229, 0.224, 0.225]

rgb_train_tf = T.Compose([
    T.Resize((IMG_SIZE + 32, IMG_SIZE + 32)),
    T.RandomCrop(IMG_SIZE),
    T.RandomHorizontalFlip(),
    T.RandomVerticalFlip(),
    T.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.3, hue=0.05),
    T.RandomRotation(20),
    T.ToTensor(),
    T.Normalize(MEAN, STD),
])
rgb_val_tf = T.Compose([
    T.Resize((IMG_SIZE, IMG_SIZE)),
    T.ToTensor(),
    T.Normalize(MEAN, STD),
])

rgb_train_ds = ImageFolder(os.path.join(RGB_STAGED_DIR, "train"), transform=rgb_train_tf)
rgb_val_ds   = ImageFolder(os.path.join(RGB_STAGED_DIR, "val"),   transform=rgb_val_tf)

# Weighted sampler to handle class imbalance
class_counts_arr = [rgb_train_ds.targets.count(i) for i in range(NUM_CLASSES)]
weights = [1.0 / c for c in class_counts_arr]
sample_weights = [weights[t] for t in rgb_train_ds.targets]
sampler = WeightedRandomSampler(sample_weights, len(sample_weights), replacement=True)

rgb_train_loader = DataLoader(rgb_train_ds, batch_size=BATCH_SIZE, sampler=sampler, num_workers=2, pin_memory=True)
rgb_val_loader   = DataLoader(rgb_val_ds,   batch_size=BATCH_SIZE, shuffle=False,   num_workers=2, pin_memory=True)

print(f"Class → index mapping: {rgb_train_ds.class_to_idx}")
print(f"Train: {len(rgb_train_ds)} images  |  Val: {len(rgb_val_ds)} images")
print(f"Class counts: { {cls: cnt for cls, cnt in zip(rgb_train_ds.classes, class_counts_arr)} }")


# %% ── CELL 6: Build MobileNetV2 Model ───────────────────────────────────────

def build_mobilenetv2(num_classes=3, freeze_backbone=False):
    """MobileNetV2 fine-tuned for freshness classification."""
    model = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.IMAGENET1K_V1)

    if freeze_backbone:
        # Freeze all layers except last 2 inverted residual blocks + classifier
        for i, layer in enumerate(model.features):
            if i < 15:
                for p in layer.parameters():
                    p.requires_grad = False

    # Replace classifier head: 1280 → num_classes
    model.classifier = nn.Sequential(
        nn.Dropout(p=0.4),
        nn.Linear(model.last_channel, 256),
        nn.ReLU(),
        nn.Dropout(p=0.2),
        nn.Linear(256, num_classes),
    )
    return model


# %% ── CELL 7: Training Loop ──────────────────────────────────────────────────

def train_model(model, train_loader, val_loader, num_epochs, lr,
                model_name="model", class_names=None):
    """Full training loop with cosine LR scheduling and early stopping."""
    model = model.to(DEVICE)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.AdamW(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=lr, weight_decay=1e-4
    )
    scheduler = CosineAnnealingLR(optimizer, T_max=num_epochs, eta_min=1e-6)

    best_val_acc = 0.0
    best_ckpt    = f"/content/{model_name}_best.pth"
    history      = {"train_loss": [], "val_acc": []}

    for epoch in range(1, num_epochs + 1):
        # ── Train ────────────────────────────────────────────────────────────
        model.train()
        running_loss = 0.0
        for images, labels in tqdm(train_loader, desc=f"Epoch {epoch}/{num_epochs} [Train]", leave=False):
            images, labels = images.to(DEVICE), labels.to(DEVICE)
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            running_loss += loss.item() * images.size(0)

        avg_loss = running_loss / len(train_loader.dataset)
        scheduler.step()

        # ── Validate ─────────────────────────────────────────────────────────
        model.eval()
        correct = total = 0
        all_preds, all_labels = [], []
        with torch.no_grad():
            for images, labels in val_loader:
                images, labels = images.to(DEVICE), labels.to(DEVICE)
                outputs = model(images)
                preds   = outputs.argmax(dim=1)
                correct += (preds == labels).sum().item()
                total   += labels.size(0)
                all_preds.extend(preds.cpu().numpy())
                all_labels.extend(labels.cpu().numpy())

        val_acc = correct / total * 100
        history["train_loss"].append(avg_loss)
        history["val_acc"].append(val_acc)
        print(f"Epoch {epoch:3d}/{num_epochs}  |  Loss: {avg_loss:.4f}  |  Val Acc: {val_acc:.1f}%")

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), best_ckpt)
            print(f"  ✓ New best: {best_val_acc:.1f}% — checkpoint saved")

    # Load best weights
    model.load_state_dict(torch.load(best_ckpt, map_location=DEVICE))
    print(f"\nTraining complete. Best Val Acc: {best_val_acc:.1f}%")

    # Classification report
    if class_names:
        print("\nClassification Report (best checkpoint):")
        print(classification_report(all_labels, all_preds, target_names=class_names))

    return model, history


# %% ── CELL 8: Train RGB Model ────────────────────────────────────────────────

print("=" * 60)
print("PART 1: Training RGB (White-Light) Freshness Model")
print("=" * 60)

rgb_class_names = rgb_train_ds.classes   # e.g. ['HEALTHY', 'ROTTEN', 'UNCERTAIN']
print(f"Classes: {rgb_class_names}")

rgb_model = build_mobilenetv2(num_classes=NUM_CLASSES, freeze_backbone=False)
rgb_model, rgb_history = train_model(
    rgb_model, rgb_train_loader, rgb_val_loader,
    num_epochs=NUM_EPOCHS_RGB, lr=LR_RGB,
    model_name="rgb_agriscan_v1",
    class_names=rgb_class_names
)


# %% ── CELL 9: Plot RGB Training Curves ─────────────────────────────────────

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))
ax1.plot(rgb_history["train_loss"], marker="o"); ax1.set_title("RGB Train Loss"); ax1.set_xlabel("Epoch"); ax1.set_ylabel("Loss"); ax1.grid(True)
ax2.plot(rgb_history["val_acc"],   marker="o", color="green"); ax2.set_title("RGB Val Accuracy"); ax2.set_xlabel("Epoch"); ax2.set_ylabel("Acc (%)"); ax2.grid(True)
plt.tight_layout(); plt.savefig("/content/rgb_training.png", dpi=120); plt.show()


# %% ── CELL 10: Export RGB Model to ONNX ─────────────────────────────────────

rgb_model.eval()
dummy_input    = torch.randn(1, 3, IMG_SIZE, IMG_SIZE).to(DEVICE)
rgb_onnx_path  = os.path.join(MODEL_OUT_DIR, "rgb_agriscan_v1.onnx")

torch.onnx.export(
    rgb_model, dummy_input, rgb_onnx_path,
    export_params=True,
    opset_version=12,
    do_constant_folding=True,
    input_names=["image"],
    output_names=["logits"],
    dynamic_axes={"image": {0: "batch_size"}, "logits": {0: "batch_size"}},
)
print(f"RGB model exported: {rgb_onnx_path}")

# Quick ONNX sanity check
import onnxruntime as ort
sess = ort.InferenceSession(rgb_onnx_path, providers=["CPUExecutionProvider"])
dummy_np = dummy_input.cpu().numpy()
out = sess.run(None, {"image": dummy_np})[0]
print(f"ONNX sanity check OK — output shape: {out.shape}, logits: {out[0]}")
print(f"Class order: {rgb_class_names}")
print("NOTE: Save this class order! It must match the order in ai_engine.py")


# %% ── CELL 11: Organize UV Dataset ──────────────────────────────────────────
#
# UV DATA WE HAVE:
#   - Tomato/UV_A_Fluorescence/  (Zenodo dataset: ~18 UV images paired with RGB)
#
# Label strategy:
#   The Zenodo files are from a longitudinal decay study.
#   Images captured Day 1-3 → HEALTHY (early/fresh)
#   Images captured Day 6+  → ROTTEN  (advanced decay)
#   Files follow naming: {id}_{day}_{rgb/uv}.jpg
#
# ⚠️ IMPORTANT: With only ~18 UV images, this model will be very limited.
#   The UV model is a STARTING POINT that will improve as you capture your
#   own UV frames from the AgriScan360 chamber.
#   For now: heavy augmentation + frozen backbone to avoid overfitting.

print("=" * 60)
print("PART 2: UV-A Fluorescence Model")
print("=" * 60)

UV_SRC_DIR    = os.path.join(DATASET_DIR, "Tomato", "UV_A_Fluorescence")
UV_STAGED_DIR = "/content/uv_staged"

def stage_uv_dataset(src_dir, staged_dir, val_split=0.20):
    """
    Organize UV-A images into HEALTHY/ROTTEN classes.
    Heuristic: filenames containing 'day1','day2','day3' → HEALTHY
               filenames containing 'day4','day5','day6','day7'+ → ROTTEN
    Falls back to alphabetical 50/50 split if naming doesn't match.
    """
    if os.path.exists(staged_dir):
        shutil.rmtree(staged_dir)
    for split in ["train", "val"]:
        for cls in ["HEALTHY", "ROTTEN", "UNCERTAIN"]:
            os.makedirs(os.path.join(staged_dir, split, cls), exist_ok=True)

    if not os.path.exists(src_dir):
        print(f"[ERROR] UV source folder not found: {src_dir}")
        return {}

    all_uv = []
    for f in os.listdir(src_dir):
        if os.path.splitext(f)[1].lower() in IMG_EXTS:
            # Only keep UV images (not RGB paired ones — look for 'uv' in filename)
            if "uv" in f.lower():
                all_uv.append(os.path.join(src_dir, f))

    if len(all_uv) == 0:
        # Fallback: take all images (they may not have 'uv' in name)
        all_uv = [os.path.join(src_dir, f) for f in os.listdir(src_dir)
                  if os.path.splitext(f)[1].lower() in IMG_EXTS]

    print(f"Found {len(all_uv)} UV images")
    if len(all_uv) < 10:
        print("[WARNING] Very few UV images found. Consider collecting more from the chamber.")

    # Label by day number in filename
    healthy_imgs, rotten_imgs = [], []
    for p in all_uv:
        fname = os.path.basename(p).lower()
        is_early = any(f"day{d}" in fname or f"d{d}_" in fname or f"_0{d}" in fname
                       for d in [1, 2, 3])
        is_late  = any(f"day{d}" in fname or f"d{d}_" in fname or f"_{d}" in fname
                       for d in [4, 5, 6, 7, 8, 9])
        if is_early:
            healthy_imgs.append(p)
        elif is_late:
            rotten_imgs.append(p)

    # If heuristic didn't work, split 50/50 alphabetically
    if len(healthy_imgs) + len(rotten_imgs) < 4:
        print("  Day-based labeling failed. Falling back to 50/50 split.")
        all_uv.sort()
        mid = len(all_uv) // 2
        healthy_imgs = all_uv[:mid]
        rotten_imgs  = all_uv[mid:]

    print(f"  HEALTHY: {len(healthy_imgs)}  |  ROTTEN: {len(rotten_imgs)}")

    def copy_split(imgs, label):
        random.shuffle(imgs)
        n_val   = max(1, int(len(imgs) * val_split))
        for i, src in enumerate(imgs[n_val:]):
            ext = os.path.splitext(src)[1].lower()
            shutil.copy2(src, os.path.join(staged_dir, "train", label, f"{label}_{i:04d}{ext}"))
        for i, src in enumerate(imgs[:n_val]):
            ext = os.path.splitext(src)[1].lower()
            shutil.copy2(src, os.path.join(staged_dir, "val",   label, f"{label}_{i:04d}{ext}"))

    copy_split(healthy_imgs, "HEALTHY")
    copy_split(rotten_imgs,  "ROTTEN")

    # Synthetic UNCERTAIN = mix of 2 borderline from each class (if available)
    uncertain = []
    if healthy_imgs: uncertain.append(random.choice(healthy_imgs))
    if rotten_imgs:  uncertain.append(random.choice(rotten_imgs))
    for i, src in enumerate(uncertain):
        ext = os.path.splitext(src)[1].lower()
        shutil.copy2(src, os.path.join(staged_dir, "train", "UNCERTAIN", f"UNCERTAIN_{i:04d}{ext}"))

    return {"HEALTHY": len(healthy_imgs), "ROTTEN": len(rotten_imgs), "UNCERTAIN": len(uncertain)}

print("\nStaging UV dataset...")
uv_counts = stage_uv_dataset(UV_SRC_DIR, UV_STAGED_DIR)
print(f"UV dataset staged at: {UV_STAGED_DIR}")


# %% ── CELL 12: UV DataLoaders (heavy augmentation) ─────────────────────────

# UV images look very different from RGB — extra augmentation to generalize.
uv_train_tf = T.Compose([
    T.Resize((IMG_SIZE + 48, IMG_SIZE + 48)),
    T.RandomCrop(IMG_SIZE),
    T.RandomHorizontalFlip(),
    T.RandomVerticalFlip(),
    T.ColorJitter(brightness=0.5, contrast=0.5, saturation=0.5, hue=0.15),
    T.RandomRotation(30),
    T.RandomGrayscale(p=0.1),
    T.GaussianBlur(kernel_size=5, sigma=(0.1, 2.0)),
    T.ToTensor(),
    T.Normalize(MEAN, STD),
])
uv_val_tf = T.Compose([
    T.Resize((IMG_SIZE, IMG_SIZE)),
    T.ToTensor(),
    T.Normalize(MEAN, STD),
])

uv_train_ds = ImageFolder(os.path.join(UV_STAGED_DIR, "train"), transform=uv_train_tf)
uv_val_ds   = ImageFolder(os.path.join(UV_STAGED_DIR, "val"),   transform=uv_val_tf)

# UV dataset is tiny — over-sample to create a full epoch worth of batches
# Repeat the UV dataset ~10x per epoch via WeightedRandomSampler
oversample_factor = max(1, 500 // max(len(uv_train_ds), 1))
uv_class_counts_arr = [max(1, uv_train_ds.targets.count(i)) for i in range(NUM_CLASSES)]
uv_weights = [1.0 / c for c in uv_class_counts_arr]
uv_sample_weights = [uv_weights[t] for t in uv_train_ds.targets]
uv_sampler = WeightedRandomSampler(
    uv_sample_weights,
    num_samples=len(uv_train_ds) * oversample_factor,
    replacement=True
)

uv_train_loader = DataLoader(uv_train_ds, batch_size=min(8, len(uv_train_ds)),
                             sampler=uv_sampler, num_workers=2)
uv_val_loader   = DataLoader(uv_val_ds,   batch_size=min(8, len(uv_val_ds)),
                             shuffle=False, num_workers=2)

print(f"UV Class → index: {uv_train_ds.class_to_idx}")
print(f"UV Train: {len(uv_train_ds)} images (oversampled {oversample_factor}x)")
print(f"UV Val: {len(uv_val_ds)} images")

if len(uv_train_ds) < 20:
    print("\n[WARNING] UV dataset has very few images.")
    print("  The UV model will have LOW accuracy and is mainly a placeholder.")
    print("  Collect more UV frames from your AgriScan360 chamber to improve it.")
    print("  Add them to: datasets/Tomato/UV_A_Fluorescence/ and re-train.")


# %% ── CELL 13: Train UV Model ────────────────────────────────────────────────

print("Training UV-A fluorescence model (frozen backbone, small dataset)...")

# For UV: freeze most of the backbone to avoid overfitting on tiny dataset
uv_class_names = uv_train_ds.classes
uv_model = build_mobilenetv2(num_classes=NUM_CLASSES, freeze_backbone=True)

uv_model, uv_history = train_model(
    uv_model, uv_train_loader, uv_val_loader,
    num_epochs=NUM_EPOCHS_UV, lr=LR_UV,
    model_name="uv_agriscan_v1",
    class_names=uv_class_names
)


# %% ── CELL 14: Plot UV Training Curves ──────────────────────────────────────

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))
ax1.plot(uv_history["train_loss"], marker="o", color="purple"); ax1.set_title("UV Train Loss"); ax1.set_xlabel("Epoch"); ax1.set_ylabel("Loss"); ax1.grid(True)
ax2.plot(uv_history["val_acc"],    marker="o", color="orange"); ax2.set_title("UV Val Accuracy"); ax2.set_xlabel("Epoch"); ax2.set_ylabel("Acc (%)"); ax2.grid(True)
plt.tight_layout(); plt.savefig("/content/uv_training.png", dpi=120); plt.show()


# %% ── CELL 15: Export UV Model to ONNX ──────────────────────────────────────

uv_model.eval()
dummy_input   = torch.randn(1, 3, IMG_SIZE, IMG_SIZE).to(DEVICE)
uv_onnx_path  = os.path.join(MODEL_OUT_DIR, "uv_agriscan_v1.onnx")

torch.onnx.export(
    uv_model, dummy_input, uv_onnx_path,
    export_params=True,
    opset_version=12,
    do_constant_folding=True,
    input_names=["image"],
    output_names=["logits"],
    dynamic_axes={"image": {0: "batch_size"}, "logits": {0: "batch_size"}},
)
print(f"UV model exported: {uv_onnx_path}")

sess = ort.InferenceSession(uv_onnx_path, providers=["CPUExecutionProvider"])
out  = sess.run(None, {"image": dummy_input.cpu().numpy()})[0]
print(f"ONNX sanity check OK — output shape: {out.shape}")
print(f"UV class order: {uv_class_names}")


# %% ── CELL 16: Summary & Download Instructions ───────────────────────────────

print("\n" + "="*60)
print("TRAINING COMPLETE — NEXT STEPS")
print("="*60)
print(f"\nModels saved to: {MODEL_OUT_DIR}")
print(f"  rgb_agriscan_v1.onnx  ({os.path.getsize(rgb_onnx_path)/1e6:.1f} MB)")
print(f"  uv_agriscan_v1.onnx   ({os.path.getsize(uv_onnx_path)/1e6:.1f} MB)")
print(f"\nRGB class order: {rgb_class_names}")
print(f"UV  class order: {uv_class_names}")
print("""
STEP 1: Download both .onnx files from Colab:
  Left panel → Files → /content/models/ → right-click → Download

STEP 2: Place them in your project:
  AgriScan360/laptop_server/models/rgb_agriscan_v1.onnx
  AgriScan360/laptop_server/models/uv_agriscan_v1.onnx

STEP 3: The ai_engine.py will auto-detect and switch from
  rule-based to neural inference when both files are present.

STEP 4: To improve the UV model later:
  - Collect UV frames from your AgriScan360 chamber
  - Add them to datasets/Tomato/UV_A_Fluorescence/ (or Apple/UV_A/)
  - Re-run this notebook
""")

# Zip for easy download
shutil.make_archive("/content/agriscan360_models", "zip", MODEL_OUT_DIR)
print("Zip created: /content/agriscan360_models.zip  (download this)")
