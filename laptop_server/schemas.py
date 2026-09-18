"""
schemas.py — Pydantic Request/Response Models
=============================================
FastAPI uses these for automatic validation, serialization, and OpenAPI docs.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


# ── Image Schema ───────────────────────────────────────────────────────────────

class ScanImageOut(BaseModel):
    """One captured image from a scan stop."""
    id:         int
    scan_id:    int
    angle_deg:  int
    light_type: str   # "rgb" or "uv"
    filename:   str
    url_path:   str   # Web-accessible URL: /static/scans/{scan_id}/filename

    model_config = ConfigDict(from_attributes=True)


# ── Scan Schemas ───────────────────────────────────────────────────────────────

class ScanResult(BaseModel):
    """
    Response returned to the Raspberry Pi after classification.
    Also used by the WebSocket live push.
    """
    scan_id:             int
    produce_name:        str
    status:              str    # HEALTHY | ROTTEN | UNCERTAIN | ERROR
    confidence:          float  # 0.0 – 100.0
    reason:              str
    gas_delta:           float  # kOhm drop (positive = rot gases)
    rot_suspicion:       str    # HEALTHY | EARLY_ROT | SEVERE_ROT | NOT_INSTALLED
    gas_ratio_pct:       Optional[float] = None
    gas_slope_per_sec:   Optional[float] = None
    gas_min_kohms:       Optional[float] = None
    gas_max_kohms:       Optional[float] = None
    gas_mean_kohms:      Optional[float] = None
    gas_std_kohms:       Optional[float] = None
    model_used:          str
    created_at:          datetime


class ScanSummary(BaseModel):
    """Compact row for the scan history table."""
    id:                  int
    produce_name:        str
    status:              str
    confidence:          float
    gas_delta:           float
    rot_suspicion:       str
    gas_ratio_pct:       Optional[float] = None
    gas_slope_per_sec:   Optional[float] = None
    temperature_c:       Optional[float] = None
    humidity_pct:        Optional[float] = None
    pressure_hpa:        Optional[float] = None
    created_at:          datetime
    image_count:         int = 0

    model_config = ConfigDict(from_attributes=True)


class ScanDetail(BaseModel):
    """Full scan detail including all 16 images — for the detail modal."""
    id:                  int
    produce_name:        str
    status:              str
    confidence:          float
    reason:              Optional[str]
    gas_delta:           float
    rot_suspicion:       str
    baseline_gas_kohms:  Optional[float] = None
    post_scan_gas_kohms: Optional[float] = None
    gas_min_kohms:       Optional[float] = None
    gas_max_kohms:       Optional[float] = None
    gas_mean_kohms:      Optional[float] = None
    gas_std_kohms:       Optional[float] = None
    gas_ratio_pct:       Optional[float] = None
    gas_slope_per_sec:   Optional[float] = None
    sample_count:        Optional[int] = None
    temperature_c:       Optional[float] = None
    humidity_pct:        Optional[float] = None
    pressure_hpa:        Optional[float] = None
    scan_duration_s:     Optional[float] = None
    model_used:          Optional[str] = None
    is_simulated:        bool
    created_at:          datetime
    completed_at:        Optional[datetime]
    images:         List[ScanImageOut] = []

    model_config = ConfigDict(from_attributes=True)


# ── Stats Schema ───────────────────────────────────────────────────────────────

class ScanStats(BaseModel):
    """Aggregated statistics for the dashboard stats bar."""
    total_scans:       int
    healthy_count:     int
    rotten_count:      int
    uncertain_count:   int
    healthy_pct:       float
    rotten_pct:        float
    uncertain_pct:     float
    avg_confidence:    float
    avg_gas_delta:     float
    produce_breakdown: dict   # {"Tomato": 12, "Banana": 5, ...}


# ── Paginated History ──────────────────────────────────────────────────────────

class PaginatedHistory(BaseModel):
    """Paginated list of scan summaries for the history table."""
    total:   int
    page:    int
    limit:   int
    items:   List[ScanSummary]


# ── Health Check ──────────────────────────────────────────────────────────────

class HealthCheck(BaseModel):
    status:     str = "ok"
    version:    str = "1.0.0"
    model_loaded: bool = False
    db_ok:      bool = True
