"""
routers/history.py — Scan History & Stats Endpoints
====================================================
GET  /api/history              — paginated scan list
GET  /api/scan/{scan_id}       — full detail with images
DELETE /api/scan/{scan_id}     — delete scan + image files
GET  /api/stats                — aggregated dashboard stats
"""

import os
import logging
import shutil
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from models import Scan, ScanImage
from schemas import ScanDetail, ScanSummary, PaginatedHistory, ScanStats

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["history"])


@router.get("/history", response_model=PaginatedHistory)
def get_history(
    page:    int = Query(default=1,  ge=1),
    limit:   int = Query(default=20, ge=1, le=100),
    produce: Optional[str] = Query(default=None),
    status:  Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """
    Returns paginated scan history, newest first.
    Supports optional filtering by produce_name and status.
    """
    q = db.query(Scan)
    if produce:
        q = q.filter(Scan.produce_name.ilike(f"%{produce}%"))
    if status:
        q = q.filter(Scan.status == status.upper())

    total = q.count()
    scans = q.order_by(Scan.created_at.desc()) \
              .offset((page - 1) * limit) \
              .limit(limit) \
              .all()

    items = []
    for s in scans:
        items.append(ScanSummary(
            id           = s.id,
            produce_name = s.produce_name,
            status       = s.status,
            confidence   = s.confidence,
            gas_delta    = s.gas_delta,
            rot_suspicion = s.rot_suspicion,
            temperature_c = s.temperature_c,
            humidity_pct  = s.humidity_pct,
            created_at   = s.created_at,
            image_count  = len(s.images),
        ))

    return PaginatedHistory(total=total, page=page, limit=limit, items=items)


@router.get("/scan/{scan_id}", response_model=ScanDetail)
def get_scan_detail(scan_id: int, db: Session = Depends(get_db)):
    """Full scan detail including all 16 image URLs."""
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found")
    return scan


@router.delete("/scan/{scan_id}")
def delete_scan(scan_id: int, db: Session = Depends(get_db)):
    """Delete a scan record and all its image files from disk."""
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found")

    # Delete image files from disk
    from config import SCANS_DIR
    import re
    safe_produce = re.sub(r'[<>:"/\\|?*]', '_', scan.produce_name).strip() or "Produce"
    folder_name = f"{scan_id}. {safe_produce}"
    scan_dir = os.path.join(SCANS_DIR, folder_name)
    if not os.path.exists(scan_dir):
        legacy_dir = os.path.join(SCANS_DIR, str(scan_id))
        if os.path.exists(legacy_dir):
            scan_dir = legacy_dir

    if os.path.exists(scan_dir):
        try:
            shutil.rmtree(scan_dir)
        except Exception as exc:
            log.warning("Could not delete scan directory %s: %s", scan_dir, exc)

    db.delete(scan)
    db.commit()
    return {"deleted": True, "scan_id": scan_id}


@router.get("/stats", response_model=ScanStats)
def get_stats(db: Session = Depends(get_db)):
    """Aggregated statistics for the dashboard stats bar."""
    total = db.query(Scan).count()

    if total == 0:
        return ScanStats(
            total_scans=0, healthy_count=0, rotten_count=0, uncertain_count=0,
            healthy_pct=0.0, rotten_pct=0.0, uncertain_pct=0.0,
            avg_confidence=0.0, avg_gas_delta=0.0, produce_breakdown={},
        )

    healthy   = db.query(Scan).filter(Scan.status == "HEALTHY").count()
    rotten    = db.query(Scan).filter(Scan.status == "ROTTEN").count()
    uncertain = db.query(Scan).filter(Scan.status == "UNCERTAIN").count()

    avg_conf = db.query(func.avg(Scan.confidence)).scalar() or 0.0
    avg_gas  = db.query(func.avg(Scan.gas_delta)).scalar() or 0.0

    # Produce breakdown
    rows = db.query(Scan.produce_name, func.count(Scan.id)) \
             .group_by(Scan.produce_name).all()
    produce_breakdown = {row[0]: row[1] for row in rows}

    return ScanStats(
        total_scans      = total,
        healthy_count    = healthy,
        rotten_count     = rotten,
        uncertain_count  = uncertain,
        healthy_pct      = round(healthy  / total * 100, 1),
        rotten_pct       = round(rotten   / total * 100, 1),
        uncertain_pct    = round(uncertain / total * 100, 1),
        avg_confidence   = round(avg_conf, 1),
        avg_gas_delta    = round(avg_gas, 2),
        produce_breakdown = produce_breakdown,
    )
