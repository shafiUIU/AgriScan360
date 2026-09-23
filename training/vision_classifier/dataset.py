"""
dataset.py -- HuggingFace Dataset Downloader, Organiser & DataLoader Builder
=============================================================================
Steps:
  1. Download raw files from SHAFI6196UIU/agriscan360-dataset using huggingface_hub.
  2. Walk the repo's top-level produce folders (Apple, Eggplant, Tomato).
  3. Collect all RGB images under each folder (skip UV/Gas/ENose sub-folders).
  4. Create a stratified 70/15/15 train/val/test split.
  5. Copy images into a flat ImageFolder layout:
       prepared/train/Apple/  prepared/train/Eggplant/  prepared/train/Tomato/
       prepared/val/...
       prepared/test/...
  6. Build PyTorch DataLoaders with appropriate augmentations.
"""

import os
import shutil
import random
import logging
from collections import defaultdict
from typing import Tuple

import torch
from torch.utils.data import DataLoader, WeightedRandomSampler
import torchvision.transforms as T
from torchvision.datasets import ImageFolder

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Step 1: Download from HuggingFace
# ---------------------------------------------------------------------------

def download_dataset(repo_id: str, local_dir: str) -> str:
    """
    Downloads the full HuggingFace dataset repo to local_dir.
    Skips re-download if already present.
    Returns the local directory path.
    """
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        raise RuntimeError(
            "huggingface_hub is not installed. Run: pip install huggingface_hub"
        )

    if os.path.isdir(local_dir) and len(os.listdir(local_dir)) > 5:
        log.info("Dataset already downloaded at: %s -- skipping download.", local_dir)
        return local_dir

    log.info("Downloading dataset '%s' to '%s' ...", repo_id, local_dir)
    os.makedirs(local_dir, exist_ok=True)
    snapshot_download(
        repo_id=repo_id,
        repo_type="dataset",
        local_dir=local_dir,
        ignore_patterns=["*.parquet", "*.json", "*.csv", "*.md", "*.txt"],
    )
    log.info("Download complete.")
    return local_dir


# ---------------------------------------------------------------------------
# Step 2-4: Collect images and create stratified splits
# ---------------------------------------------------------------------------

def _collect_images(raw_dir: str, produce_classes: list, skip_keywords: list,
                    image_extensions: set) -> dict:
    """
    Walk raw_dir and collect all image paths per produce class.
    Only processes top-level folders matching produce_classes.
    Skips any path containing a skip_keywords substring.

    Returns: {class_name: [abs_image_path, ...]}
    """
    collected = defaultdict(list)

    for cls in produce_classes:
        cls_root = os.path.join(raw_dir, cls)
        if not os.path.isdir(cls_root):
            log.warning("Produce folder not found: %s", cls_root)
            continue

        for dirpath, dirnames, filenames in os.walk(cls_root):
            # Skip unwanted sub-folders
            rel = os.path.relpath(dirpath, cls_root)
            if any(kw.lower() in rel.lower() for kw in skip_keywords):
                continue

            for fname in filenames:
                ext = os.path.splitext(fname)[1].lower()
                if ext in image_extensions:
                    collected[cls].append(os.path.join(dirpath, fname))

    for cls, paths in collected.items():
        log.info("  Class %-12s : %d images found", cls, len(paths))

    return dict(collected)


def prepare_splits(raw_dir: str, prepared_dir: str, produce_classes: list,
                   skip_keywords: list, image_extensions: set,
                   split_train: float, split_val: float, seed: int) -> dict:
    """
    Creates the flat ImageFolder directory structure with train/val/test splits.
    Skips if already prepared.

    Returns: {"train": path, "val": path, "test": path}
    """
    split_dirs = {
        "train": os.path.join(prepared_dir, "train"),
        "val":   os.path.join(prepared_dir, "val"),
        "test":  os.path.join(prepared_dir, "test"),
    }

    # Check if already prepared
    already_done = all(
        os.path.isdir(os.path.join(sd, cls))
        for sd in split_dirs.values()
        for cls in produce_classes
    )
    if already_done:
        counts = {
            split: sum(
                len(os.listdir(os.path.join(sd, cls)))
                for cls in produce_classes
                if os.path.isdir(os.path.join(sd, cls))
            )
            for split, sd in split_dirs.items()
        }
        log.info("Splits already prepared: %s", counts)
        return split_dirs

    log.info("Preparing image splits ...")
    collected = _collect_images(raw_dir, produce_classes, skip_keywords, image_extensions)

    rng = random.Random(seed)
    total_copied = 0

    for cls, paths in collected.items():
        rng.shuffle(paths)
        n      = len(paths)
        n_train = int(n * split_train)
        n_val   = int(n * split_val)
        # Remaining goes to test
        splits_paths = {
            "train": paths[:n_train],
            "val":   paths[n_train : n_train + n_val],
            "test":  paths[n_train + n_val :],
        }
        for split, spaths in splits_paths.items():
            dest_dir = os.path.join(split_dirs[split], cls)
            os.makedirs(dest_dir, exist_ok=True)
            for i, src in enumerate(spaths):
                ext  = os.path.splitext(src)[1].lower()
                dest = os.path.join(dest_dir, f"{cls}_{split}_{i:05d}{ext}")
                shutil.copy2(src, dest)
            total_copied += len(spaths)
            log.info("  %s / %-12s : %d images", split.ljust(5), cls, len(spaths))

    log.info("Total images copied: %d", total_copied)
    return split_dirs


# ---------------------------------------------------------------------------
# Step 5: Transforms
# ---------------------------------------------------------------------------

def build_transforms(image_size: int, cfg) -> Tuple[T.Compose, T.Compose]:
    """
    Returns (train_transform, eval_transform).
    eval_transform is used for both val and test splits.
    """
    mean = cfg.IMAGENET_MEAN
    std  = cfg.IMAGENET_STD

    train_tf = T.Compose([
        T.Resize((image_size + 32, image_size + 32)),
        T.RandomResizedCrop(
            image_size,
            scale=(cfg.AUG_SCALE_MIN, cfg.AUG_SCALE_MAX),
        ),
        T.RandomHorizontalFlip(p=cfg.AUG_HFLIP_PROB),
        T.RandomRotation(degrees=cfg.AUG_ROTATION_DEGREES),
        T.RandomAffine(
            degrees=0,
            translate=(cfg.AUG_TRANSLATE_H, cfg.AUG_TRANSLATE_V),
        ),
        T.ColorJitter(
            brightness=cfg.AUG_BRIGHTNESS,
            contrast=cfg.AUG_CONTRAST,
            saturation=cfg.AUG_SATURATION,
        ),
        T.ToTensor(),
        T.Normalize(mean=mean, std=std),
    ])

    eval_tf = T.Compose([
        T.Resize((image_size + 32, image_size + 32)),
        T.CenterCrop(image_size),
        T.ToTensor(),
        T.Normalize(mean=mean, std=std),
    ])

    return train_tf, eval_tf


# ---------------------------------------------------------------------------
# Step 6: DataLoaders
# ---------------------------------------------------------------------------

def build_dataloaders(split_dirs: dict, cfg) -> Tuple[DataLoader, DataLoader, DataLoader, list]:
    """
    Builds train, val, test DataLoaders.
    Uses WeightedRandomSampler on the training set to handle class imbalance.

    Returns: (train_loader, val_loader, test_loader, class_names)
    """
    train_tf, eval_tf = build_transforms(cfg.IMAGE_SIZE, cfg)

    train_ds = ImageFolder(root=split_dirs["train"], transform=train_tf)
    val_ds   = ImageFolder(root=split_dirs["val"],   transform=eval_tf)
    test_ds  = ImageFolder(root=split_dirs["test"],  transform=eval_tf)

    class_names = train_ds.classes
    log.info("Classes: %s", class_names)
    log.info("Train: %d  |  Val: %d  |  Test: %d",
             len(train_ds), len(val_ds), len(test_ds))

    # Build WeightedRandomSampler for class balance
    class_counts = [0] * len(class_names)
    for _, label in train_ds.samples:
        class_counts[label] += 1
    class_weights = [1.0 / max(c, 1) for c in class_counts]
    sample_weights = [class_weights[label] for _, label in train_ds.samples]
    sampler = WeightedRandomSampler(
        weights=sample_weights,
        num_samples=len(sample_weights),
        replacement=True,
    )

    # Pin memory for GPU speed
    pin = torch.cuda.is_available()

    train_loader = DataLoader(
        train_ds,
        batch_size=cfg.BATCH_SIZE,
        sampler=sampler,
        num_workers=cfg.NUM_WORKERS,
        pin_memory=pin,
        drop_last=True,
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=cfg.BATCH_SIZE,
        shuffle=False,
        num_workers=cfg.NUM_WORKERS,
        pin_memory=pin,
    )
    test_loader = DataLoader(
        test_ds,
        batch_size=cfg.BATCH_SIZE,
        shuffle=False,
        num_workers=cfg.NUM_WORKERS,
        pin_memory=pin,
    )

    return train_loader, val_loader, test_loader, class_names


# ---------------------------------------------------------------------------
# Convenience: one-stop setup
# ---------------------------------------------------------------------------

def setup_data(cfg) -> Tuple[DataLoader, DataLoader, DataLoader, list]:
    """
    Full pipeline: download -> prepare splits -> build dataloaders.
    Safe to call multiple times (skips already-done steps).

    Returns: (train_loader, val_loader, test_loader, class_names)
    """
    raw_dir = download_dataset(cfg.HF_REPO_ID, cfg.DATA_ROOT)

    split_dirs = prepare_splits(
        raw_dir       = raw_dir,
        prepared_dir  = cfg.PREPARED_DIR,
        produce_classes = cfg.PRODUCE_CLASSES,
        skip_keywords = cfg.SKIP_SUBFOLDER_KEYWORDS,
        image_extensions = cfg.IMAGE_EXTENSIONS,
        split_train   = cfg.SPLIT_TRAIN,
        split_val     = cfg.SPLIT_VAL,
        seed          = cfg.RANDOM_SEED,
    )

    return build_dataloaders(split_dirs, cfg)
