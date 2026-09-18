# Drop your trained ONNX models here:
#
#   rgb_agriscan_v1.onnx  — RGB white-light freshness model (Pillar 1)
#   uv_agriscan_v1.onnx   — UV-A fluorescence model (Pillar 2)
#
# Both are trained and exported from:
#   AgriScan360/training/train_agriscan360.py  (run in Google Colab)
#
# When both files are present, the AI engine automatically switches from
# rule-based to neural inference.  If only one is present, that pillar
# uses neural inference and the other falls back to heuristics.
