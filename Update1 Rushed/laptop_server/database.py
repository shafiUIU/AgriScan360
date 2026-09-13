"""
database.py — SQLAlchemy SQLite Engine & Session Management
============================================================
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from config import DATABASE_URL, BASE_DIR

# Ensure DB directory exists
os.makedirs(os.path.join(BASE_DIR, "db"), exist_ok=True)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},   # Required for SQLite + FastAPI threading
    echo=False,                                   # Set True to log all SQL queries
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


def get_db():
    """
    FastAPI dependency: yields a DB session per request, closes on completion.
    Usage in route:
        def my_route(db: Session = Depends(get_db)):
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all_tables():
    """Create all ORM-defined tables. Called once at server startup."""
    from models import Scan, ScanImage   # noqa: F401 — must import to register
    Base.metadata.create_all(bind=engine)
