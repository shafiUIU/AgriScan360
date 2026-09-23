# AgriScan 360 Vision Classifier -- Production Pipeline

Deep-learning based produce identification for **Apple, Eggplant (Brinjal), and Tomato**.
Trained on the curated multi-condition dataset `SHAFI6196UIU/agriscan360-dataset` from Hugging Face.
Replaces color-based heuristics with deep feature extraction (shapes, calyx patterns, skin textures, stem contours, edges).

---

## 1. Project Structure

```
training/vision_classifier/
  config.py             Central configuration (hyperparameters, paths, model selection)
  dataset.py            HuggingFace dataset downloader, stratified splits, augmentations
  model.py              Model factory supporting 5 architectures with ImageNet weights
  train.py              PyTorch training loop with mixed precision (AMP) and early stopping
  evaluate.py           Test evaluation, classification report, confusion matrix visualization
  export.py             Exporter to PyTorch (.pth) and ONNX (opset 17)
  inference.py          Production ONNX inference engine (single file / raw JPEG bytes)
  compare_models.py     Architecture benchmark & comparison tool for RTX 4060
  requirements.txt      Dependencies specification
  README.md             This guide
```

---

## 2. Model Architectures & Recommendation

| Model Architecture | Parameters | ImageNet Top-1 | RTX 4060 Latency | Role |
|---|---|---|---|---|
| **EfficientNet-B2** | **9.1M** | **80.1%** | **~2.8 ms** | **RECOMMENDED PRIMARY** |
| EfficientNet-B0 | 5.3M | 77.1% | ~1.8 ms | Lightweight baseline |
| EfficientNetV2-S | 21.5M | 83.9% | ~4.5 ms | High-capacity alternative |
| ConvNeXt-Tiny | 28.6M | 82.1% | ~4.1 ms | Modern ConvNet baseline |
| ResNet50 | 25.3M | 76.1% | ~3.2 ms | Classic standard benchmark |

### Why EfficientNet-B2?
1. **Geometric & Texture Feature Extraction**: Compound scaling balances resolution (260x260), network depth, and feature width. It captures calyx/stem textures and fruit curvature rather than relying on color alone.
2. **RTX 4060 Performance**: Inference latency is under 3 ms (~350 FPS) using Tensor Cores and FP16 mixed precision.
3. **Memory Footprint**: Only 9.1M parameters (~35 MB ONNX file), ideal for low latency laptop server execution.

---

## 3. Environment Setup (HP Victus 16 / RTX 4060)

To use your NVIDIA GeForce RTX 4060 Laptop GPU with mixed precision (AMP) and CUDA acceleration:

```powershell
# 1. Install PyTorch with CUDA 12.1 support
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# 2. Install required dependencies
pip install -r training/vision_classifier/requirements.txt
```

Verify GPU detection:
```powershell
python -c "import torch; print('CUDA available:', torch.cuda.is_available()); print('Device:', torch.cuda.get_device_name(0))"
```

---

## 4. Model Comparison Benchmark

To benchmark inference latency and parameter counts of all 5 architectures on your hardware:

```powershell
# Latency & parameter benchmark only (no training required):
python training/vision_classifier/compare_models.py --benchmark-only

# Full multi-model comparative training (10 epochs each):
python training/vision_classifier/compare_models.py --epochs 10
```

Results are saved to:
- `training/vision_classifier/results/model_comparison.csv`
- `training/vision_classifier/results/model_comparison.md`

---

## 5. Training the Recommended Model

Train the primary EfficientNet-B2 model:

```powershell
# Train EfficientNet-B2 (default 50 epochs with early stopping & AMP):
python training/vision_classifier/train.py

# Or train another architecture:
python training/vision_classifier/train.py --model efficientnetv2_s
python training/vision_classifier/train.py --model resnet50 --epochs 35
```

Features included:
- **HuggingFace Hub Integration**: Automatically downloads and parses `SHAFI6196UIU/agriscan360-dataset`.
- **Stratified Split**: 70% Train, 15% Validation, 15% Test.
- **WeightedRandomSampler**: Overcomes class sample imbalance across Apple, Eggplant, and Tomato.
- **Realistic Augmentations**: +/-15 deg rotation, horizontal flip, brightness/contrast jitter, slight scale/zoom. No vertical flips or unnatural color inversions.
- **Mixed Precision (AMP)**: Accelerates training on RTX 4060 Tensor Cores.
- **Cosine Annealing LR & Early Stopping**: Halts if validation accuracy does not improve for 10 epochs.
- **Checkpoints**: Best model saved to `training/vision_classifier/checkpoints/best_model.pth`.

---

## 6. Evaluation

Evaluate the saved checkpoint against the held-out test split:

```powershell
python training/vision_classifier/evaluate.py

# To inspect any specific misclassified images:
python training/vision_classifier/evaluate.py --show-mistakes
```

Outputs:
- Per-class precision, recall, and F1-score breakdown.
- Top misclassification confusion pairs.
- Heatmap confusion matrix saved to `training/vision_classifier/results/confusion_matrix.png`.

---

## 7. Model Export (.pth and ONNX)

Export the trained PyTorch checkpoint into both a clean `.pth` state dict and an optimized ONNX model:

```powershell
python training/vision_classifier/export.py
```

- ONNX target: `laptop_server/models/produce_classifier.onnx`
- Opset version: 17
- Input specification: `float32 [batch_size, 3, 260, 260]` (ImageNet normalized)
- Output specification: `float32 [batch_size, 3]` (Raw logits)
- Automatic numerical consistency verification between PyTorch and ONNX outputs.

---

## 8. Inference

### CLI Test on a Single Image:
```powershell
python training/vision_classifier/inference.py --image path/to/sample.jpg
```

Output:
```json
{
  "class": "Tomato",
  "confidence": 0.9842,
  "all_scores": {
    "Tomato": 0.9842,
    "Apple": 0.0121,
    "Eggplant": 0.0037
  }
}
```

### Python API (for laptop server integration):
```python
from training.vision_classifier.inference import ProduceInferenceEngine

engine = ProduceInferenceEngine()

# From file path:
result = engine.predict_file("path/to/image.jpg")

# From raw bytes (received from Raspberry Pi 5 camera):
result = engine.predict_bytes(jpeg_bytes)
print(result["class"], result["confidence"])
```

---

## 9. Future Multi-Modal Expansion

The architecture is designed modularly to support multi-modal sensory fusion:
1. **Backbone Feature Hook**: `ProduceClassifier.backbone` extracts high-level spatial visual features (e.g., 1408 dimensions for EfficientNet-B2).
2. **UV-A Multi-Spectral Branch**: Add a second backbone or 4th channel for 365nm UV-A fluorescence.
3. **BME688 Gas Sensor Branch**: Pass the 12 BME688 features (`baseline_kohms`, `decay_slope`, `gas_ratio_pct`, `temperature`, `humidity`, etc.) through an MLP projection layer and concatenate with visual feature embeddings before the final classification head.
4. **Freshness & Rot Severity**: The same pipeline architecture can be trained directly on the dataset's condition labels (`Damaged`, `Old`, `Ripe`, `Unripe`) by updating `NUM_CLASSES = 4`.
