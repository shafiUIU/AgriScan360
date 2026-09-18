"""
uploader.py — Pi → Laptop HTTP Client
=======================================
Packages 16 captured JPEG images + gas sensor data + metadata into a
multipart/form-data POST request and sends it to the FastAPI laptop server.

Returns the classification result JSON from the server,
or a fallback dict if the server is unreachable.
"""

import logging
import time
from typing import List, Optional

import requests

from config import API_SCAN_ENDPOINT, API_HEALTH_ENDPOINT, REQUEST_TIMEOUT_SEC

log = logging.getLogger(__name__)

# Fallback result when server is offline
_OFFLINE_RESULT = {
    "status": "SERVER_OFFLINE",
    "confidence": 0.0,
    "reason": "Could not reach laptop server. Check Wi-Fi connection.",
    "scan_id": None,
    "gas_delta": 0.0,
    "rot_suspicion": "UNKNOWN",
}


class ScanUploader:
    """
    Handles all network communication from the Raspberry Pi to the laptop FastAPI server.
    """

    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({"Accept": "application/json"})

    def check_server(self) -> bool:
        """
        Ping the server health endpoint.
        Returns True if server is reachable and alive.
        """
        try:
            resp = self._session.get(API_HEALTH_ENDPOINT, timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def upload_scan(
        self,
        rgb_images: List[bytes],      # 8 RGB JPEG bytes, angles 0°–315°
        uv_images: List[bytes],       # 8 UV  JPEG bytes, angles 0°–315°
        gas_result,                    # ScanGasResult dataclass from gas_sensor.py
        produce_name: str = "Unknown",
    ) -> dict:
        """
        POST all scan data to FastAPI /api/scan endpoint.

        Multipart form fields:
            produce_name   : str
            gas_delta      : float (kΩ drop)
            rot_suspicion  : str (LOW/MEDIUM/HIGH)
            temperature_c  : float
            humidity_pct   : float
            images         : 16× JPEG files, named rgb_000 … rgb_315 / uv_000 … uv_315

        Returns:
            dict with keys: status, confidence, reason, scan_id, gas_delta, rot_suspicion
        """
        ANGLES = [0, 45, 90, 135, 180, 225, 270, 315]

        # Build multipart files list
        files = []
        for i, (rgb, uv) in enumerate(zip(rgb_images, uv_images)):
            angle = ANGLES[i]
            files.append(("images", (f"rgb_{angle:03d}.jpg", rgb, "image/jpeg")))
            files.append(("images", (f"uv_{angle:03d}.jpg",  uv,  "image/jpeg")))

        # Build form data with comprehensive gas analytics
        data = {
            "produce_name":        produce_name,
            "gas_delta":           str(round(gas_result.delta_kohms, 3)),
            "baseline_gas_kohms":  str(round(getattr(gas_result, 'baseline_kohms', 0.0), 2)),
            "post_scan_gas_kohms": str(round(getattr(gas_result, 'post_scan_gas_kohms', 0.0), 2)),
            "gas_min_kohms":       str(round(getattr(gas_result, 'gas_min_kohms', 0.0), 2)),
            "gas_max_kohms":       str(round(getattr(gas_result, 'gas_max_kohms', 0.0), 2)),
            "gas_mean_kohms":      str(round(getattr(gas_result, 'gas_mean_kohms', 0.0), 2)),
            "gas_std_kohms":       str(round(getattr(gas_result, 'gas_std_kohms', 0.0), 2)),
            "gas_ratio_pct":       str(round(getattr(gas_result, 'gas_ratio_pct', 0.0), 2)),
            "gas_slope_per_sec":   str(round(getattr(gas_result, 'gas_slope_per_sec', 0.0), 4)),
            "sample_count":        str(getattr(gas_result, 'sample_count', 0)),
            "rot_suspicion":       gas_result.rot_suspicion,
            "temperature_c":       str(round(getattr(gas_result, 'temperature_c', gas_result.baseline_temp), 1)),
            "humidity_pct":        str(round(getattr(gas_result, 'humidity_pct', gas_result.baseline_humidity), 1)),
            "pressure_hpa":        str(round(getattr(gas_result, 'pressure_hpa', 1013.25), 1)),
        }

        log.info("Uploading scan to %s  (produce=%s, gas_delta=%.2f kOhm)",
                 API_SCAN_ENDPOINT, produce_name, gas_result.delta_kohms)

        try:
            resp = self._session.post(
                API_SCAN_ENDPOINT,
                data=data,
                files=files,
                timeout=REQUEST_TIMEOUT_SEC,
            )
            resp.raise_for_status()
            result = resp.json()
            log.info("Server returned: status=%s  confidence=%.1f%%",
                     result.get("status"), result.get("confidence", 0))
            return result

        except requests.exceptions.ConnectionError:
            log.error("Server unreachable: %s", API_SCAN_ENDPOINT)
            return _OFFLINE_RESULT

        except requests.exceptions.Timeout:
            log.error("Server timed out after %ds", REQUEST_TIMEOUT_SEC)
            return {**_OFFLINE_RESULT, "reason": "Server timed out. AI inference took too long."}

        except requests.exceptions.HTTPError as exc:
            log.error("HTTP error from server: %s", exc)
            return {**_OFFLINE_RESULT, "status": "SERVER_ERROR", "reason": str(exc)}

        except Exception as exc:
            log.error("Unexpected upload error: %s", exc)
            return {**_OFFLINE_RESULT, "reason": f"Unexpected error: {exc}"}

    def close(self):
        self._session.close()
