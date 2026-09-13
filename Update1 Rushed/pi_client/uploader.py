"""
uploader.py — Pi → Laptop HTTP Client (Simplified)
====================================================
UPDATE1 RUSHED CHANGES:
    - gas_result parameter removed from upload_scan().
    - Gas fields sent as zeros / "N/A" (server accepts optional fields).
    - Only RGB images are sent (no UV images).
    - Everything else unchanged.
"""

import logging
import requests
from typing import List

from config import API_SCAN_ENDPOINT, API_HEALTH_ENDPOINT, REQUEST_TIMEOUT_SEC

log = logging.getLogger(__name__)

_OFFLINE_RESULT = {
    "status":       "SERVER_OFFLINE",
    "confidence":   0.0,
    "reason":       "Could not reach laptop server. Check Wi-Fi connection.",
    "scan_id":      None,
    "gas_delta":    0.0,
    "rot_suspicion":"N/A",
}


class ScanUploader:
    """Handles HTTP upload from Pi to laptop FastAPI server."""

    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({"Accept": "application/json"})

    def check_server(self) -> bool:
        try:
            resp = self._session.get(API_HEALTH_ENDPOINT, timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def upload_scan(
        self,
        rgb_images: List[bytes],        # 8 RGB JPEG bytes, angles 0°–315°
        uv_images:  List[bytes] = [],   # 8 UV JPEG bytes, angles 0°–315°
        produce_name: str = "Unknown",
    ) -> dict:
        """
        POST 8 RGB + 8 UV images + produce name to FastAPI /api/scan.
        Gas fields are sent as zero/N/A defaults (BME688 disabled).
        """
        ANGLES = [0, 45, 90, 135, 180, 225, 270, 315]

        # Build multipart files list (RGB + UV)
        files = []
        for i, rgb in enumerate(rgb_images):
            angle = ANGLES[i] if i < len(ANGLES) else i * 45
            files.append(("images", (f"rgb_{angle:03d}.jpg", rgb, "image/jpeg")))

        for i, uv in enumerate(uv_images):
            angle = ANGLES[i] if i < len(ANGLES) else i * 45
            files.append(("images", (f"uv_{angle:03d}.jpg", uv, "image/jpeg")))

        # Gas fields sent as zero (BME688 sensor removed)
        data = {
            "produce_name":  produce_name,
            "gas_delta":     "0.0",
            "rot_suspicion": "N/A",
            "temperature_c": "0.0",
            "humidity_pct":  "0.0",
        }

        total_frames = len(rgb_images) + len(uv_images)
        log.info("Uploading %d frames (%d RGB + %d UV) to %s (produce=%s)",
                 total_frames, len(rgb_images), len(uv_images), API_SCAN_ENDPOINT, produce_name)

        try:
            resp = self._session.post(
                API_SCAN_ENDPOINT,
                data=data,
                files=files,
                timeout=REQUEST_TIMEOUT_SEC,
            )
            resp.raise_for_status()
            result = resp.json()
            log.info("Server result: status=%s  confidence=%.1f%%",
                     result.get("status"), result.get("confidence", 0))
            return result

        except requests.exceptions.ConnectionError:
            log.error("Server unreachable: %s", API_SCAN_ENDPOINT)
            return _OFFLINE_RESULT
        except requests.exceptions.Timeout:
            log.error("Server timed out after %ds", REQUEST_TIMEOUT_SEC)
            return {**_OFFLINE_RESULT, "reason": "Server timed out."}
        except requests.exceptions.HTTPError as exc:
            log.error("HTTP error: %s", exc)
            return {**_OFFLINE_RESULT, "status": "SERVER_ERROR", "reason": str(exc)}
        except Exception as exc:
            log.error("Unexpected upload error: %s", exc)
            return {**_OFFLINE_RESULT, "reason": f"Unexpected error: {exc}"}

    def close(self):
        self._session.close()
