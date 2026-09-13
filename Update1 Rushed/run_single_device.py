"""
run_single_device.py — AgriScan 360 All-In-One Single-Device Launcher
=====================================================================
Runs the entire AgriScan 360 system standalone on a SINGLE Raspberry Pi:
  1. Starts the FastAPI Web Server + WebSocket + SQLite DB (binding to 0.0.0.0:8000).
  2. Runs the AI Multi-Spectral Vision Classification Engine locally on the Pi.
  3. Launches the interactive dual-pass scanner (Motor + Camera) in the terminal.
  4. Uploads captures internally to http://127.0.0.1:8000 with zero network friction.

Usage:
  python run_single_device.py              # Full live hardware mode on Raspberry Pi
  python run_single_device.py --simulate   # Simulation mode (runs on laptop/PC without Pi hardware)
  python run_single_device.py --server-only # Start only the FastAPI server
  python run_single_device.py --scan-only   # Start only the scanner (assumes server is running)
"""

import argparse
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.error
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.join(BASE_DIR, "laptop_server")
CLIENT_DIR = os.path.join(BASE_DIR, "pi_client")
HEALTH_URL = "http://127.0.0.1:8000/api/health"

def get_lan_ip() -> str:
    """Best-effort discovery of local LAN IP for display."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        # Connect to a public DNS IP (doesn't send actual packet)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def wait_for_server(timeout_sec: int = 20) -> bool:
    """Poll health endpoint until server is ready."""
    print("[Single-Device] Waiting for FastAPI server to initialize...", end="", flush=True)
    start = time.time()
    while time.time() - start < timeout_sec:
        try:
            req = urllib.request.Request(HEALTH_URL, headers={"User-Agent": "AgriScan-Launcher"})
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode())
                    if data.get("status") == "ok":
                        print(" READY!")
                        return True
        except Exception:
            pass
        time.sleep(0.5)
        print(".", end="", flush=True)
    print(" TIMEOUT!")
    return False


def main():
    parser = argparse.ArgumentParser(description="AgriScan 360 All-In-One Single-Device Launcher")
    parser.add_argument("--simulate", action="store_true", help="Run without physical motor/camera")
    parser.add_argument("--server-only", action="store_true", help="Launch FastAPI server only")
    parser.add_argument("--scan-only", action="store_true", help="Run scanner CLI only")
    parser.add_argument("--port", type=int, default=8000, help="Web server port (default: 8000)")
    args = parser.parse_args()

    lan_ip = get_lan_ip()

    print("\n" + "=" * 62)
    print("      AgriScan 360 — Standalone Single-Device System")
    print("      Hardware, Server, AI & Web UI on One Raspberry Pi")
    print("=" * 62)
    print(f" * Local Dashboard:     http://localhost:{args.port}")
    if lan_ip != "127.0.0.1":
        print(f" * Remote Network URL:   http://{lan_ip}:{args.port}")
    print(f" * API Documentation:   http://localhost:{args.port}/docs")
    print(f" * Hardware Mode:       {'SIMULATED' if args.simulate else 'LIVE RASPBERRY PI'}")
    print("=" * 62 + "\n")

    server_proc = None

    # 1. Start Server Process (unless --scan-only)
    if not args.scan_only:
        log_file_path = os.path.join(BASE_DIR, "server.log")
        log_file = open(log_file_path, "w", encoding="utf-8")

        print(f"[Single-Device] Launching FastAPI backend on port {args.port}...")
        server_cmd = [
            sys.executable, "-m", "uvicorn",
            "main_server:app",
            "--host", "0.0.0.0",
            "--port", str(args.port),
        ]

        server_proc = subprocess.Popen(
            server_cmd,
            cwd=SERVER_DIR,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )

        if not wait_for_server():
            print("[ERROR] FastAPI server failed to start within timeout. Check server.log.")
            if server_proc:
                server_proc.terminate()
            sys.exit(1)

        print(f"[Single-Device] Server is running (PID: {server_proc.pid}). Logs: {log_file_path}")

    # If user only wanted the server running, wait on it
    if args.server_only:
        print("[Single-Device] Server-only mode active. Press Ctrl+C to terminate.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[Single-Device] Stopping server...")
        finally:
            if server_proc:
                server_proc.terminate()
                server_proc.wait()
            print("[Single-Device] Stopped.")
            return

    # 2. Start Scanner Orchestrator
    try:
        scanner_cmd = [sys.executable, "main.py"]
        if args.simulate:
            scanner_cmd.append("--simulate")

        print("[Single-Device] Launching Scanner Orchestrator...\n")
        # Run scanner in foreground so user can interact with prompts
        scanner_proc = subprocess.Popen(
            scanner_cmd,
            cwd=CLIENT_DIR,
        )
        scanner_proc.wait()

    except KeyboardInterrupt:
        print("\n[Single-Device] Keyboard interrupt received.")
    finally:
        if server_proc:
            print("[Single-Device] Shutting down FastAPI server...")
            server_proc.terminate()
            try:
                server_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_proc.kill()
            print("[Single-Device] Server shut down cleanly.")

    print("[Single-Device] AgriScan 360 session complete.")


if __name__ == "__main__":
    main()
