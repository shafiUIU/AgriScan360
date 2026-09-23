"""
model.py -- AgriScan 360 Produce Classifier Model Factory
==========================================================
Builds one of 5 supported architectures with:
  - ImageNet pretrained weights
  - Replaced final classifier head for NUM_CLASSES outputs
  - Feature extractor accessible for future fusion (UV / gas branches)

Supported names (set in config.py -> MODEL_NAME):
    "efficientnet_b0"
    "efficientnet_b2"      <- RECOMMENDED
    "efficientnetv2_s"
    "convnext_tiny"
    "resnet50"

Future expansion hook:
    build_model() returns a ProduceClassifier wrapper that exposes:
      - model.backbone      : feature extractor (before final head)
      - model.head          : final linear classifier
    Later, you can add a MultiModalFusionModel that combines backbone
    features with UV-A features and BME688 gas vectors.
"""

import logging
from typing import Tuple

import torch
import torch.nn as nn
import torchvision.models as tv_models

log = logging.getLogger(__name__)


# =============================================================================
# Architecture specs table (for logging / comparison script)
# =============================================================================

ARCH_SPECS = {
    "efficientnet_b0": {
        "params_m": 5.3,
        "imagenet_top1": 77.1,
        "native_size": 224,
        "description": "Fastest, smallest. Good baseline.",
    },
    "efficientnet_b2": {
        "params_m": 9.1,
        "imagenet_top1": 80.1,
        "native_size": 260,
        "description": "RECOMMENDED. Best accuracy/speed/size for RTX 4060.",
    },
    "efficientnetv2_s": {
        "params_m": 21.5,
        "imagenet_top1": 83.9,
        "native_size": 300,
        "description": "Highest accuracy. Slightly heavier.",
    },
    "convnext_tiny": {
        "params_m": 28.6,
        "imagenet_top1": 82.1,
        "native_size": 224,
        "description": "Strong modern architecture. Large params.",
    },
    "resnet50": {
        "params_m": 25.3,
        "imagenet_top1": 76.1,
        "native_size": 224,
        "description": "Classic baseline. Well-understood.",
    },
}


# =============================================================================
# ProduceClassifier wrapper
# =============================================================================

class ProduceClassifier(nn.Module):
    """
    Thin wrapper around a torchvision backbone.

    Attributes:
        backbone  : Feature extractor (everything except final head).
                    Future: replace/extend with multi-modal fusion.
        head      : Final linear layer -> num_classes logits.
        name      : Architecture name string.
        num_classes: Number of produce classes.
    """

    def __init__(self, backbone: nn.Module, head: nn.Module, name: str, num_classes: int):
        super().__init__()
        self.backbone   = backbone
        self.head       = head
        self.name       = name
        self.num_classes = num_classes

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        features = self.backbone(x)
        return self.head(features)

    def get_feature_dim(self) -> int:
        """Returns the feature dimension before the head (useful for fusion)."""
        # Run a dummy forward pass through backbone only
        device = next(self.backbone.parameters()).device
        dummy = torch.zeros(1, 3, 224, 224, device=device)
        with torch.no_grad():
            feats = self.backbone(dummy)
        return feats.shape[-1]


# =============================================================================
# Architecture builders
# =============================================================================

def _build_efficientnet_b0(num_classes: int, pretrained: bool) -> Tuple[nn.Module, nn.Module]:
    weights = tv_models.EfficientNet_B0_Weights.IMAGENET1K_V1 if pretrained else None
    m = tv_models.efficientnet_b0(weights=weights)
    in_features = m.classifier[1].in_features
    m.classifier = nn.Identity()
    head = nn.Sequential(
        nn.Dropout(p=0.3, inplace=True),
        nn.Linear(in_features, num_classes),
    )
    return m, head


def _build_efficientnet_b2(num_classes: int, pretrained: bool) -> Tuple[nn.Module, nn.Module]:
    weights = tv_models.EfficientNet_B2_Weights.IMAGENET1K_V1 if pretrained else None
    m = tv_models.efficientnet_b2(weights=weights)
    in_features = m.classifier[1].in_features
    m.classifier = nn.Identity()
    head = nn.Sequential(
        nn.Dropout(p=0.3, inplace=True),
        nn.Linear(in_features, num_classes),
    )
    return m, head


def _build_efficientnetv2_s(num_classes: int, pretrained: bool) -> Tuple[nn.Module, nn.Module]:
    weights = tv_models.EfficientNet_V2_S_Weights.IMAGENET1K_V1 if pretrained else None
    m = tv_models.efficientnet_v2_s(weights=weights)
    in_features = m.classifier[1].in_features
    m.classifier = nn.Identity()
    head = nn.Sequential(
        nn.Dropout(p=0.2, inplace=True),
        nn.Linear(in_features, num_classes),
    )
    return m, head


def _build_convnext_tiny(num_classes: int, pretrained: bool) -> Tuple[nn.Module, nn.Module]:
    weights = tv_models.ConvNeXt_Tiny_Weights.IMAGENET1K_V1 if pretrained else None
    m = tv_models.convnext_tiny(weights=weights)
    # ConvNeXt classifier is m.classifier[2]
    in_features = m.classifier[2].in_features
    m.classifier[2] = nn.Identity()
    # Wrap backbone so output is flat
    backbone = nn.Sequential(m.features, m.avgpool, m.classifier)
    head = nn.Sequential(
        nn.Flatten(1),
        nn.LayerNorm(in_features),
        nn.Dropout(p=0.2),
        nn.Linear(in_features, num_classes),
    )
    return backbone, head


def _build_resnet50(num_classes: int, pretrained: bool) -> Tuple[nn.Module, nn.Module]:
    weights = tv_models.ResNet50_Weights.IMAGENET1K_V2 if pretrained else None
    m = tv_models.resnet50(weights=weights)
    in_features = m.fc.in_features
    m.fc = nn.Identity()
    head = nn.Sequential(
        nn.Dropout(p=0.4),
        nn.Linear(in_features, num_classes),
    )
    return m, head


# =============================================================================
# Public factory
# =============================================================================

_BUILDERS = {
    "efficientnet_b0":  _build_efficientnet_b0,
    "efficientnet_b2":  _build_efficientnet_b2,
    "efficientnetv2_s": _build_efficientnetv2_s,
    "convnext_tiny":    _build_convnext_tiny,
    "resnet50":         _build_resnet50,
}


def build_model(model_name: str, num_classes: int, pretrained: bool = True) -> ProduceClassifier:
    """
    Build and return a ProduceClassifier for the given architecture.

    Args:
        model_name  : One of the ARCH_SPECS keys.
        num_classes : Number of output classes (3 for Apple/Tomato/Eggplant).
        pretrained  : If True, initialise backbone with ImageNet weights.

    Returns:
        ProduceClassifier instance (not moved to device yet).
    """
    model_name = model_name.lower().strip()
    if model_name not in _BUILDERS:
        raise ValueError(
            f"Unknown model '{model_name}'. "
            f"Choose from: {list(_BUILDERS.keys())}"
        )

    builder = _BUILDERS[model_name]
    backbone, head = builder(num_classes=num_classes, pretrained=pretrained)

    model = ProduceClassifier(
        backbone=backbone,
        head=head,
        name=model_name,
        num_classes=num_classes,
    )

    spec = ARCH_SPECS[model_name]
    total_params = sum(p.numel() for p in model.parameters()) / 1e6
    log.info(
        "Built model: %-20s | Params: %.1fM | ImageNet top-1: %.1f%% | %s",
        model_name, total_params, spec["imagenet_top1"], spec["description"],
    )
    return model


def count_parameters(model: nn.Module) -> int:
    """Returns number of trainable parameters."""
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def print_model_summary(model_name: str):
    """Print a summary table of all supported architectures."""
    print("\n+-- Supported Architectures -------------------------+")
    print(f"{'Model':<20} {'Params':<10} {'ImageNet':>8} {'Native':>8}")
    print("-" * 52)
    for name, spec in ARCH_SPECS.items():
        marker = "  <-- SELECTED" if name == model_name else ""
        print(
            f"{name:<20} {spec['params_m']:<10.1f} "
            f"{spec['imagenet_top1']:>7.1f}% "
            f"{spec['native_size']:>7}px"
            f"{marker}"
        )
    print("+----------------------------------------------------+\n")
