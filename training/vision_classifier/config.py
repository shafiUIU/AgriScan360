"""
config.py -- AgriScan 360 Vision Classifier Configuration
==========================================================
Central config for the produce identification pipeline.
Change MODEL_NAME to switch architectures without touching training code.

Supported MODEL_NAME values:
    "efficientnet_b0"    -- 5.3M params, fastest, good baseline
    "efficientnet_b2"    -- 9.1M params, RECOMMENDED best accuracy/speed trade-off
    "efficientnetv2_s"   -- 21.5M params, highest accuracy, slightly slower
    "convnext_tiny"      -- 28.6M params, strong modern alternative
    "resnet50"           -- 25.3M params, classic baseline comparison

Dataset note:
    The HuggingFace repo SHAFI6196UIU/agriscan360-dataset stores images under:
      Apple/RGB_Images/...
      Eggplant/RGB_Images/...
      Tomato/RGB_Images/...
    The dataset.py will walk all subfolders and assign the top-level
    produce folder (Apple, Eggplant, Tomato) as the class label,
    ignoring the sub-condition structure for this produce-ID task.
"""

import os

# =============================================================================
# PATHS
# =============================================================================

HERE          = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT  = os.path.dirname(os.path.dirname(HERE))

# Where the raw images will be downloaded/cached from HuggingFace
DATA_ROOT     = os.path.join(PROJECT_ROOT, "datasets", "vision_produce")

# Organised flat ImageFolder layout built by dataset.py
PREPARED_DIR  = os.path.join(DATA_ROOT, "prepared")
TRAIN_DIR     = os.path.join(PREPARED_DIR, "train")
VAL_DIR       = os.path.join(PREPARED_DIR, "val")
TEST_DIR      = os.path.join(PREPARED_DIR, "test")

# Checkpoints and outputs
CHECKPOINT_DIR = os.path.join(HERE, "checkpoints")
RESULTS_DIR    = os.path.join(HERE, "results")

# =============================================================================
# DATASET
# =============================================================================

HF_REPO_ID     = "SHAFI6196UIU/agriscan360-dataset"

# Top-level folder names in the HuggingFace repo that map to produce classes.
# Only images under these folders are collected.
PRODUCE_CLASSES = ["Apple", "Eggplant", "Tomato"]
NUM_CLASSES     = len(PRODUCE_CLASSES)

# Sub-folder fragments to SKIP during image collection (UV, gas, diagnostics)
SKIP_SUBFOLDER_KEYWORDS = [
    "UV_Images",
    "Gas_Sensor",
    "ENose",
    "metadata",
    "README",
]

# Images that match these extensions are loaded
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# Train / Val / Test split ratios (must sum to 1.0)
SPLIT_TRAIN = 0.70
SPLIT_VAL   = 0.15
SPLIT_TEST  = 0.15

RANDOM_SEED = 42

# =============================================================================
# MODEL
# =============================================================================

# "efficientnet_b0" | "efficientnet_b2" | "efficientnetv2_s" | "convnext_tiny" | "resnet50"
MODEL_NAME   = "efficientnet_b2"

# ImageNet pretrained weights
PRETRAINED   = True

# Input image size (height, width) -- efficientnet_b2 native is 260
IMAGE_SIZE   = 260

# =============================================================================
# TRAINING HYPERPARAMETERS
# =============================================================================

BATCH_SIZE      = 32
NUM_EPOCHS      = 50
LEARNING_RATE   = 3e-4
WEIGHT_DECAY    = 1e-4

# Cosine Annealing LR schedule
LR_T_MAX        = 10     # Restart period in epochs
LR_ETA_MIN      = 1e-6   # Minimum LR

# Early stopping
EARLY_STOP_PATIENCE = 10  # Stop if val accuracy doesn't improve for N epochs

# Gradient clipping
GRAD_CLIP_NORM  = 1.0

# Mixed precision training (AMP) -- requires CUDA
USE_AMP         = True

# Number of DataLoader workers (set 0 on Windows if you hit multiprocess issues)
NUM_WORKERS     = 4

# Label smoothing for cross-entropy loss
LABEL_SMOOTHING = 0.1

# =============================================================================
# AUGMENTATION
# =============================================================================

# All augmentations are realistic for produce on a fixed turntable

# Training augmentations
AUG_ROTATION_DEGREES    = 15       # +/- 15 deg rotation
AUG_HFLIP_PROB          = 0.5      # 50% horizontal flip
AUG_BRIGHTNESS          = 0.30     # +/- 30% brightness
AUG_CONTRAST            = 0.30     # +/- 30% contrast
AUG_SATURATION          = 0.20     # +/- 20% saturation
AUG_SCALE_MIN           = 0.85     # Zoom range min (15% zoom-in)
AUG_SCALE_MAX           = 1.0      # Zoom range max
AUG_TRANSLATE_H         = 0.10     # +/- 10% horizontal shift
AUG_TRANSLATE_V         = 0.10     # +/- 10% vertical shift

# ImageNet normalisation (used for both train and inference)
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD  = [0.229, 0.224, 0.225]

# =============================================================================
# EXPORT
# =============================================================================

# Best checkpoint filename
BEST_CHECKPOINT = os.path.join(CHECKPOINT_DIR, "best_model.pth")

# ONNX export
ONNX_PATH       = os.path.join(PROJECT_ROOT, "laptop_server", "models", "produce_classifier.onnx")
ONNX_OPSET     = 17

# =============================================================================
# LOGGING
# =============================================================================

TRAINING_LOG_CSV = os.path.join(RESULTS_DIR, "training_log.csv")
CONFUSION_MATRIX_PNG = os.path.join(RESULTS_DIR, "confusion_matrix.png")
