"""
main_server.py — FastAPI Application Entry Point
=================================================
Run with:
    cd laptop_server
    uvicorn main_server:app --host 0.0.0.0 --port 8000 --reload

Or use the provided start_server.bat script.
"""

import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from config import HOST, PORT, CORS_ORIGINS, STATIC_DIR, SCANS_DIR
from database import create_all_tables
from schemas import HealthCheck
from ai_engine import get_classifier

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("agriscan.server")


# =============================================================================
# WebSocket Connection Manager
# =============================================================================

class WebSocketManager:
    """Manages all active WebSocket connections for real-time dashboard push."""

    def __init__(self):
        self._active: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._active.add(ws)
        log.info("WebSocket client connected. Total: %d", len(self._active))

    def disconnect(self, ws: WebSocket):
        self._active.discard(ws)
        log.info("WebSocket client disconnected. Total: %d", len(self._active))

    async def broadcast(self, data: dict):
        """Send JSON payload to all connected dashboard clients."""
        payload = json.dumps(data)
        dead = set()
        for ws in self._active:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)
        self._active -= dead


ws_manager = WebSocketManager()


# =============================================================================
# App Lifespan (startup / shutdown)
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    log.info("=== AgriScan 360 Server Starting ===")

    # Ensure required directories exist
    os.makedirs(SCANS_DIR, exist_ok=True)

    # Create DB tables
    create_all_tables()
    log.info("Database tables verified / created.")

    # Pre-load AI classifier
    classifier = get_classifier()
    log.info("AI classifier ready. Model: %s",
             "ONNX" if classifier._onnx.available else "rule_based")

    # Wire WebSocket manager into scan router
    from routers.scan import set_ws_manager
    set_ws_manager(ws_manager)

    log.info("Server ready at http://%s:%d", HOST, PORT)
    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    log.info("=== AgriScan 360 Server Shutting Down ===")


# =============================================================================
# FastAPI App
# =============================================================================

app = FastAPI(
    title="AgriScan 360 API",
    description=(
        "Multi-spectral 360° produce freshness classification system. "
        "Fuses RGB imaging, 365nm UV-A fluorescence, and BME688 VOC gas sensing."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS — allow all origins on local LAN
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files (images + frontend assets)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# =============================================================================
# Routers
# =============================================================================

from routers.scan    import router as scan_router
from routers.history import router as history_router

app.include_router(scan_router)
app.include_router(history_router)


# =============================================================================
# Core Routes
# =============================================================================

@app.get("/api/health", response_model=HealthCheck, tags=["system"])
def health_check():
    """Health check endpoint — called by Raspberry Pi on startup."""
    classifier = get_classifier()
    return HealthCheck(
        status       = "ok",
        version      = "1.0.0",
        model_loaded = classifier._onnx.available,
        db_ok        = True,
    )


@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    """
    WebSocket endpoint for real-time dashboard updates.
    Connects dashboard browser clients; receives scan_complete events.
    """
    await ws_manager.connect(websocket)
    try:
        # Send initial connection confirmation
        await websocket.send_text(json.dumps({
            "event": "connected",
            "message": "AgriScan 360 live feed connected"
        }))
        # Keep alive — just listen (server pushes, client doesn't need to send)
        while True:
            await websocket.receive_text()   # Will raise on disconnect
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


@app.get("/", response_class=HTMLResponse, tags=["frontend"])
async def serve_dashboard():
    """Serve the main dashboard HTML."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if not os.path.exists(index_path):
        return HTMLResponse("<h1>Frontend not found. Check static/index.html</h1>", status_code=404)
    return FileResponse(index_path)


# =============================================================================
# Dev / CLI Entrypoint
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main_server:app", host=HOST, port=PORT, reload=True, log_level="info")
