@echo off
REM ============================================================
REM  AgriScan 360 — Laptop FastAPI Server Launcher
REM  Run this on your LAPTOP (Windows) to start the server.
REM ============================================================

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║       AgriScan 360 — FastAPI Server          ║
echo  ║       UIU CSE 4326  -  Stage 1               ║
echo  ╚══════════════════════════════════════════════╝
echo.

REM --- Find your laptop's local IP and display it ---
echo Your laptop's network IP addresses:
ipconfig | findstr /i "IPv4"
echo.
echo  → Update pi_client\config.py  LAPTOP_SERVER_URL with your IP above
echo.

REM --- Change to the laptop_server directory ---
cd /d "%~dp0laptop_server"

REM --- Install dependencies if not already installed ---
REM Uncomment the line below on first run:
REM pip install -r requirements_laptop.txt

REM --- Start FastAPI with Uvicorn ---
echo Starting FastAPI server on http://0.0.0.0:8000 ...
echo Dashboard: http://localhost:8000
echo API Docs:  http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop the server.
echo.

python -m uvicorn main_server:app --host 0.0.0.0 --port 8000 --reload

pause
