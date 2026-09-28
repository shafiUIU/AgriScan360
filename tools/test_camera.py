"""
test_camera.py -- Pi Camera Module 2 ROI Crop Diagnostic Tool
==============================================================
Tests the camera capture and verifies that the field of view (FOV)
is properly narrowed down to the turntable center (as calibrated
from CUTScreenshot).

Usage on Raspberry Pi:
    python tools/test_camera.py

Outputs:
    tools/camera_test_cropped.jpg -- Narrowed view of turntable (sent to server/AI)
    tools/camera_test_full.jpg    -- Full wide camera FOV for comparison
"""

import sys
import os
import time

# Add pi_client to path to import config and camera
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PI_CLIENT_DIR = os.path.join(BASE_DIR, "pi_client")
if PI_CLIENT_DIR not in sys.path:
    sys.path.insert(0, PI_CLIENT_DIR)

from PIL import Image

try:
    from camera import CameraController
    import config as cfg
except ImportError as exc:
    print(f"[!] Import error: {exc}")
    sys.exit(1)


def main():
    print("=" * 62)
    print("  AgriScan 360 -- Camera ROI Center Crop Verification")
    print("=" * 62)
    print(f"  Capture Resolution : {cfg.CAPTURE_RESOLUTION}")
    print(f"  Crop Enabled       : {cfg.CAMERA_CROP_ENABLED}")
    print(f"  Crop ROI (L,T,R,B) : {cfg.CAMERA_ROI_CROP}")
    print(f"    - Left margin    : {cfg.CAMERA_ROI_CROP[0]*100:.1f}% (cuts styrofoam wall)")
    print(f"    - Top margin     : {cfg.CAMERA_ROI_CROP[1]*100:.1f}% (cuts BME sensor & ceiling)")
    print(f"    - Right edge     : {cfg.CAMERA_ROI_CROP[2]*100:.1f}% (cuts pipe feeder chute)")
    print(f"    - Bottom edge    : {cfg.CAMERA_ROI_CROP[3]*100:.1f}% (turntable front edge)")
    print("=" * 62)

    cam = CameraController(simulate=False)

    try:
        # 1. Capture with ROI Crop enabled (production behavior)
        cfg.CAMERA_CROP_ENABLED = True
        print("\n[1/2] Capturing with ROI CROP enabled...")
        cropped_bytes = cam.capture_jpeg()
        cropped_path = os.path.join(BASE_DIR, "tools", "camera_test_cropped.jpg")
        with open(cropped_path, "wb") as f:
            f.write(cropped_bytes)
        img_c = Image.open(cropped_path)
        print(f"  -> Saved: {cropped_path}")
        print(f"  -> Dimensions: {img_c.size[0]} x {img_c.size[1]} pixels")

        # 2. Capture full uncropped frame for comparison
        cfg.CAMERA_CROP_ENABLED = False
        print("\n[2/2] Capturing FULL uncropped frame for comparison...")
        full_bytes = cam.capture_jpeg()
        full_path = os.path.join(BASE_DIR, "tools", "camera_test_full.jpg")
        with open(full_path, "wb") as f:
            f.write(full_bytes)
        img_f = Image.open(full_path)
        print(f"  -> Saved: {full_path}")
        print(f"  -> Dimensions: {img_f.size[0]} x {img_f.size[1]} pixels")

        # Restore setting
        cfg.CAMERA_CROP_ENABLED = True

        print("\n" + "=" * 62)
        print("  VERIFICATION COMPLETE")
        print("=" * 62)
        print(f"  Full FOV    : {img_f.size[0]} x {img_f.size[1]}")
        print(f"  Narrowed ROI: {img_c.size[0]} x {img_c.size[1]} (Turntable Only)")
        print("\n  To calibrate or adjust the crop margins:")
        print("  Edit 'CAMERA_ROI_CROP' in pi_client/config.py:")
        print("    CAMERA_ROI_CROP = (left, top, right, bottom)")
        print("=" * 62)

    finally:
        cam.cleanup()


if __name__ == "__main__":
    main()
