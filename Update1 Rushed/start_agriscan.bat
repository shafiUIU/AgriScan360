@echo off
REM =============================================================================
REM  AgriScan 360 — Single-Device Standalone Launcher (Windows / PC Test)
REM =============================================================================

cd /d "%~dp0"

echo.
echo  ======================================================
echo   AgriScan 360 - Standalone Single-Device Mode
echo  ======================================================
echo.

python run_single_device.py --simulate %*

pause
