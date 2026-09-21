"""
models.py — SQLAlchemy ORM Table Definitions
=============================================

Tables:
    scans      — One row per scan session (result, produce, gas, timestamp)
    scan_images — One row per captured image (16 rows per scan)
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
)
from sqlalchemy.orm import relationship

from database import Base


class Scan(Base):
    """
    Master record for a single 360° scan session.
    One scan produces 16 images (8 RGB + 8 UV) stored in ScanImage.
    """
    __tablename__ = "scans"

    id              = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Produce info
    produce_name    = Column(String(64),  nullable=False, default="Unknown")

    # Classification result
    status          = Column(String(16),  nullable=False, default="PENDING")
    # status ∈ {"FRESH", "MID_FRESH", "MID_ROTTEN", "ROTTEN", "HEALTHY", "UNCERTAIN", "PENDING", "ERROR"}
    ground_truth    = Column(String(32),  nullable=True)                  # Human verified condition
    confidence      = Column(Float,       nullable=False, default=0.0)   # 0.0–100.0
    reason          = Column(Text,        nullable=True)                  # Human-readable explanation

    # Gas sensor analytics
    gas_delta           = Column(Float,       nullable=False, default=0.0)   # kOhm drop
    baseline_gas_kohms  = Column(Float,       nullable=True)
    post_scan_gas_kohms = Column(Float,       nullable=True)
    gas_min_kohms       = Column(Float,       nullable=True)
    gas_max_kohms       = Column(Float,       nullable=True)
    gas_mean_kohms      = Column(Float,       nullable=True)
    gas_std_kohms       = Column(Float,       nullable=True)
    gas_ratio_pct       = Column(Float,       nullable=True)
    gas_slope_per_sec   = Column(Float,       nullable=True)
    sample_count        = Column(Integer,     nullable=True, default=0)
    rot_suspicion       = Column(String(32),  nullable=False, default="HEALTHY")
    temperature_c       = Column(Float,       nullable=True)
    humidity_pct        = Column(Float,       nullable=True)
    pressure_hpa        = Column(Float,       nullable=True)

    # Scan metadata
    scan_duration_s = Column(Float,       nullable=True)                  # Total scan time in seconds
    model_used      = Column(String(64),  nullable=True, default="rule_based")
    is_simulated    = Column(Boolean,     nullable=False, default=False)

    # Timestamps
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at    = Column(DateTime, nullable=True)

    # Relationship: one scan → many images
    images          = relationship("ScanImage", back_populates="scan",
                                   cascade="all, delete-orphan", lazy="select")

    def __repr__(self):
        return f"<Scan id={self.id} produce={self.produce_name!r} status={self.status!r}>"


class ScanImage(Base):
    """
    One captured image from a scan stop.
    Each scan generates exactly 16 rows (8 RGB + 8 UV).
    """
    __tablename__ = "scan_images"

    id          = Column(Integer, primary_key=True, index=True, autoincrement=True)
    scan_id     = Column(Integer, ForeignKey("scans.id", ondelete="CASCADE"),
                         nullable=False, index=True)

    # Image metadata
    angle_deg   = Column(Integer, nullable=False)   # 0, 45, 90, 135, 180, 225, 270, 315
    light_type  = Column(String(8), nullable=False)  # "rgb" or "uv"
    filename    = Column(String(128), nullable=False) # e.g. "rgb_000.jpg"
    file_path   = Column(String(256), nullable=False) # absolute disk path
    url_path    = Column(String(256), nullable=False) # web-accessible URL path

    # Relationship back to scan
    scan        = relationship("Scan", back_populates="images")

    def __repr__(self):
        return f"<ScanImage scan={self.scan_id} angle={self.angle_deg}° type={self.light_type!r}>"
