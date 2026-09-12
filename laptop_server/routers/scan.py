"""
routers/scan.py — POST /api/scan  (Core Scan Ingestion Endpoint)
=================================================================
Receives multipart form from Raspberry Pi containing:
    - 16 JPEG images (8 RGB + 8 UV)
    - gas_delta, rot_suspicion, temperature_c, humidity_pct
    - produce_name
Runs AI classification, saves to DB, pushes WebSocket event.
"""

import os
import time
import logging
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from database import get_db
from models import Scan, ScanImage
from schemas import ScanResult
from ai_engine import get_classifier
from config import SCANS_DIR

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["scan"])

# WebSocket manager is imported from main_server at runtime to avoid circular imports
_ws_manager = None


def set_ws_manager(manager):
    global _ws_manager
    _ws_manager = manager


@router.post("/scan", response_model=ScanResult)
async def ingest_scan(
    produce_name:   str  = Form(default="Unknown"),
    gas_delta:      float = Form(default=0.0),
    rot_suspicion:  str  = Form(default="LOW"),
    temperature_c:  float = Form(default=0.0),
    humidity_pct:   float = Form(default=0.0),
    images:         List[UploadFile] = File(...),
    db:             Session = Depends(get_db),
):
    """
    Main scan ingestion endpoint.
    Called by the Raspberry Pi after completing the 8-stop 360° scan.
    """
    t_start = time.time()
    log.info("Received scan: produce=%s, %d images, gas_delta=%.2f kΩ",
             produce_name, len(images), gas_delta)

    if len(images) < 2:
        raise HTTPException(status_code=422, detail="At least 2 images required (1 RGB + 1 UV)")

    # ── 1. Create pending Scan record ──────────────────────────────────────────
    scan = Scan(
        produce_name  = produce_name.strip().title() or "Unknown",
        status        = "PENDING",
        gas_delta     = gas_delta,
        rot_suspicion = rot_suspicion,
        temperature_c = temperature_c,
        humidity_pct  = humidity_pct,
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)
    scan_id = scan.id

    # ── 2. Save images to disk & DB ────────────────────────────────────────────
    import re
    safe_produce = re.sub(r'[<>:"/\\|?*]', '_', scan.produce_name).strip() or "Produce"
    folder_name = f"{scan_id}. {safe_produce}"
    scan_dir = os.path.join(SCANS_DIR, folder_name)
    os.makedirs(scan_dir, exist_ok=True)

    rgb_bytes_list = []
    uv_bytes_list  = []

    for upload in images:
        raw = await upload.read()
        filename = upload.filename or "image.jpg"
        filepath = os.path.join(scan_dir, filename)

        with open(filepath, "wb") as f:
            f.write(raw)

        # Parse angle and type from filename: rgb_045.jpg or uv_135.jpg
        name_part = filename.replace(".jpg", "").replace(".jpeg", "")
        parts     = name_part.split("_")
        light_type = parts[0].lower() if len(parts) >= 1 else "rgb"
        try:
            angle_deg = int(parts[1]) if len(parts) >= 2 else 0
        except ValueError:
            angle_deg = 0

        url_path = f"/static/scans/{folder_name}/{filename}"

        img_record = ScanImage(
            scan_id    = scan_id,
            angle_deg  = angle_deg,
            light_type = light_type,
            filename   = filename,
            file_path  = filepath,
            url_path   = url_path,
        )
        db.add(img_record)

        if light_type == "rgb":
            rgb_bytes_list.append(raw)
        else:
            uv_bytes_list.append(raw)

    db.commit()

    # ── 3. Run AI Classification ───────────────────────────────────────────────
    try:
        classifier = get_classifier()
        ai_result  = classifier.classify(
            rgb_images    = rgb_bytes_list,
            uv_images     = uv_bytes_list,
            gas_delta     = gas_delta,
            rot_suspicion = rot_suspicion,
        )
    except Exception as exc:
        log.error("AI classification error: %s", exc)
        ai_result = {
            "status":     "UNCERTAIN",
            "confidence": 50.0,
            "reason":     f"Classification error: {exc}",
            "model_used": "error",
        }

    # ── 4. Update Scan record with result ─────────────────────────────────────
    scan.status       = ai_result["status"]
    scan.confidence   = ai_result["confidence"]
    scan.reason       = ai_result.get("reason", "")
    scan.model_used   = ai_result.get("model_used", "rule_based_v1")
    scan.scan_duration_s = round(time.time() - t_start, 2)
    scan.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(scan)

    # ── 5. Push WebSocket live event ──────────────────────────────────────────
    ws_payload = {
        "event":        "scan_complete",
        "scan_id":      scan_id,
        "produce_name": scan.produce_name,
        "status":       scan.status,
        "confidence":   scan.confidence,
        "reason":       scan.reason,
        "gas_delta":    gas_delta,
        "rot_suspicion": rot_suspicion,
    }
    if _ws_manager:
        await _ws_manager.broadcast(ws_payload)

    log.info("Scan %d complete: %s (%.1f%%) in %.1fs",
             scan_id, scan.status, scan.confidence, scan.scan_duration_s)

    return ScanResult(
        scan_id      = scan_id,
        produce_name = scan.produce_name,
        status       = scan.status,
        confidence   = scan.confidence,
        reason       = scan.reason or "",
        gas_delta    = gas_delta,
        rot_suspicion = rot_suspicion,
        model_used   = scan.model_used or "rule_based_v1",
        created_at   = scan.created_at,
    )
