<div align="center">

# 🌿 AgriScan 360 — [Update1 Rushed Build]

> ⚠️ **NOTICE — RUSHED/SIMPLIFIED BUILD:**
> - **Motor:** 100% Active (NEMA 17 + A4988 driver, 8 stops × 45° = 360°).
> - **Camera:** 100% Active (Picamera2, captures 8 high-resolution RGB frames).
> - **LEDs:** Purely manual external switch (no MOSFETs, no GPIO control).
> - **Gas Sensor:** Disabled (BME688 not used in this build).
> - **Web Server:** Fully active (FastAPI + SQLite + WebSockets), RGB surface analysis only.

[![UIU](https://img.shields.io/badge/University-United_International_University-blue?style=flat-square)](https://www.uiu.ac.bd/)
[![Course](https://img.shields.io/badge/Course-CSE_4326_Microprocessors_Lab-purple?style=flat-square)]()
[![Build](https://img.shields.io/badge/Build-Update1_Rushed-orange?style=flat-square)]()
[![Python](https://img.shields.io/badge/Python-3.11+-yellow?style=flat-square&logo=python)]()
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-teal?style=flat-square&logo=fastapi)]()

</div>

---

## 🏗️ System Architecture (Single-Device Standalone)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       RASPBERRY PI 5 (All-In-One Appliance)                 │
│                                                                             │
│  ┌─────────────────────────┐          Internal Loopback                     │
│  │   Hardware & Scanner    │  ─────────────────────────────────┐            │
│  │                         │       HTTP POST http://127.0.0.1  │            │
│  │  • NEMA 17 + A4988      │         16 images (8 RGB + 8 UV)  │            │
│  │  • Pi Camera Module     │                                   ▼            │
│  │  • Manual LED prompts   │                          ┌──────────────────┐  │
│  │  • SSD1306 OLED (I2C)   │                          │  FastAPI Backend │  │
│  └─────────────────────────┘                          │  • Port 8000     │  │
│                                                       │  • SQLite DB     │  │
│                                                       │  • Local AI      │  │
│  ┌─────────────────────────┐     LAN (Wi-Fi)          │  • WebSocket     │  │
│  │ Remote Browser (Laptop) │ ◀─────────────────────── │  • Web Dashboard │  │
│  │  http://<PI_IP>:8000    │   Live Updates & UI      └──────────────────┘  │
│  └─────────────────────────┘                                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 🔬 Three Detection Pillars

| Pillar | Sensor | What It Detects |
|--------|--------|-----------------|
| **1 — RGB Surface** | Camera + White LEDs | Browning, necrosis, bruising, calyx decay |
| **2 — UV Fluorescence** | Camera + 365nm UV-A | Fungal mould (glows green/yellow), aflatoxin |
| **3 — Gas / VOC** | BME688 | Internal rot, core decay, ethylene, ethanol emission |

> **One scan = 16 frames** (8 RGB × 8 angles + 8 UV × 8 angles) at 45° increments for full 360° coverage.

---

## 📁 Project Structure

```
AgriScan360/
│
├── pi_client/                  ← Runs on Raspberry Pi 5
│   ├── config.py               GPIO pins, server URL, motor/camera settings
│   ├── motor.py                NEMA 17 + A4988 stepper controller
│   ├── lights.py               White + UV-A LED switching via IRLZ44N
│   ├── gas_sensor.py           BME688 I2C driver + baseline/delta analysis
│   ├── camera.py               Picamera2 controller (RGB + UV pair capture)
│   ├── display.py              SSD1306 OLED I2C driver
│   ├── uploader.py             HTTP multipart POST client → laptop server
│   ├── main.py                 Master scan orchestrator
│   └── requirements_pi.txt
│
├── laptop_server/              ← Runs on your Laptop (Windows/Linux/Mac)
│   ├── main_server.py          FastAPI app entry point + WebSocket manager
│   ├── config.py               Server host, DB path, AI thresholds
│   ├── database.py             SQLAlchemy SQLite engine + session
│   ├── models.py               ORM: Scan + ScanImage tables
│   ├── schemas.py              Pydantic request/response schemas
│   ├── ai_engine.py            Multi-modal classifier (rule-based + ONNX slot)
│   ├── routers/
│   │   ├── scan.py             POST /api/scan
│   │   └── history.py          GET /api/history, /api/scan/{id}, /api/stats, DELETE
│   ├── static/
│   │   ├── index.html          Industrial Bio-Tech Dark dashboard
│   │   ├── css/style.css       Full custom dark theme + animations
│   │   ├── js/app.js           WebSocket client + API calls + table rendering
│   │   └── scans/              Scan images saved here: scans/{scan_id}/
│   ├── db/
│   │   └── agriscan360.db      SQLite database (auto-created on first run)
│   └── requirements_laptop.txt
│
├── start_server.bat            One-click laptop server launcher (Windows)
├── start_pi.sh                 One-click Pi client launcher (Linux/RPi OS)
├── .gitignore
└── README.md
```

---

## ⚡ Quick Start — Single-Device Standalone (Recommended)

Everything runs standalone on the **Raspberry Pi alone**. No laptop server required!

### 1. Copy `Update1 Rushed` to your Raspberry Pi
Drag-and-drop the folder `Update1 Rushed` to `/home/pi/` via VS Code Remote SSH or SCP:
```bash
scp -r "C:\Users\MD. SHAFIUL BARI\Downloads\MICRO LAB\Update1 Rushed" pi@<PI_IP>:~/
```

### 2. Set Up Virtual Environment on Pi
In your Raspberry Pi terminal:
```bash
cd ~/Update1\ Rushed
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install -r requirements_pi_all_in_one.txt
```

### 3. Run Standalone AgriScan 360
```bash
bash start_agriscan.sh
# Or directly:
python run_single_device.py
```
> **Testing without hardware?** Pass `--simulate`:
> `python run_single_device.py --simulate`

### 4. What Happens Automatically:
1. The FastAPI Web Server boots on `http://0.0.0.0:8000` (PID logged to `server.log`).
2. The Web Dashboard is immediately accessible:
   - On the Pi itself: `http://localhost:8000`
   - From any laptop, phone, or tablet on your Wi-Fi: `http://<PI_IP>:8000`
3. The interactive scanner prompts you for produce name and manual LED passes.
4. Images are sent internally via `127.0.0.1:8000` — zero Wi-Fi drops, zero firewall blocking!
5. The local AI engine classifies the sample and immediately pushes results to the web dashboard and OLED display.

---

## 🔌 Hardware Pin Reference

### A4988 Stepper Driver → Raspberry Pi 5

| A4988 Signal | Pi GPIO (BCM) | Pi Physical Pin |
|---|---|---|
| STEP | GPIO 17 | Pin 11 |
| DIR | GPIO 27 | Pin 13 |
| ENABLE | GPIO 22 | Pin 15 |
| RST + SLP | Bridge together | — |
| VMOT | 12V PSU (+) | — |
| GND (motor) | 12V PSU (−) + Pi GND | — |

### IRLZ44N MOSFETs → Raspberry Pi 5

| LED Array | Gate (GPIO BCM) | Physical Pin |
|---|---|---|
| White LED Array | GPIO 18 | Pin 12 |
| 365nm UV-A Array | GPIO 24 | Pin 18 |

> **Wiring:** LED (+) → Power rail · LED (−) → Drain · Gate → GPIO + 10kΩ pull-down · Source → GND

### I2C Devices (shared bus)

| Device | SDA | SCL | I2C Address |
|---|---|---|---|
| BME688 Gas Sensor | GPIO 2 (Pin 3) | GPIO 3 (Pin 5) | `0x77` |
| SSD1306 OLED 0.96" | GPIO 2 (Pin 3) | GPIO 3 (Pin 5) | `0x3C` |

### NEMA 17 Motor (6-pin socket → A4988)

| Pin | A4988 Terminal |
|---|---|
| Pin 1 (leftmost) | 1A |
| Pin 2 | Skip/Empty |
| Pin 3 | 1B |
| Pin 4 | 2A |
| Pin 5 | Skip/Empty |
| Pin 6 (rightmost) | 2B |

---

## 🌐 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Web dashboard |
| `GET` | `/api/health` | Server health check (called by Pi on startup) |
| `POST` | `/api/scan` | Ingest scan (multipart: 16 images + gas data) |
| `GET` | `/api/history` | Paginated scan history (`?page=1&limit=20&produce=Tomato&status=ROTTEN`) |
| `GET` | `/api/scan/{id}` | Full scan detail with all 16 image URLs |
| `GET` | `/api/stats` | Aggregated stats (total, healthy%, rotten%, produce breakdown) |
| `DELETE` | `/api/scan/{id}` | Delete scan record + image files |
| `WS` | `/ws/live` | WebSocket — real-time scan result push to dashboard |
| `GET` | `/docs` | Swagger UI (auto-generated) |
| `GET` | `/redoc` | ReDoc API docs |

---

## 🗄️ Database Schema

```
scans
├── id              INTEGER  PRIMARY KEY
├── produce_name    TEXT     (Tomato, Banana, Eggplant …)
├── status          TEXT     HEALTHY | ROTTEN | UNCERTAIN | PENDING
├── confidence      REAL     0.0 – 100.0 %
├── reason          TEXT     Human-readable explanation
├── gas_delta       REAL     kΩ resistance drop (BME688)
├── rot_suspicion   TEXT     LOW | MEDIUM | HIGH
├── temperature_c   REAL
├── humidity_pct    REAL
├── model_used      TEXT     rule_based_v1 | onnx_agriscan360_v1
└── created_at      DATETIME

scan_images  (16 rows per scan)
├── id          INTEGER  PRIMARY KEY
├── scan_id     INTEGER  FK → scans.id
├── angle_deg   INTEGER  0, 45, 90, 135, 180, 225, 270, 315
├── light_type  TEXT     rgb | uv
├── filename    TEXT     e.g. rgb_045.jpg
└── url_path    TEXT     /static/scans/{id}/rgb_045.jpg
```

---

## 🤖 AI Engine — Datasets (To Train Later)

> **Do NOT download datasets yet** — user will do this manually when ready.

| Branch | Dataset | Notes |
|---|---|---|
| RGB (main) | Freshness44 | 10 of 11 produce covered |
| RGB (eggplant) | BrinjalFruitX (Kaggle/Mendeley) | Solves eggplant gap |
| RGB (multi-angle) | Fruits-360 (90,483 images) | Turntable geometry matches exactly |
| RGB (Bangladesh) | Fresh & Rotten Fruits (BD) | Local conditions |
| UV-A | Longitudinal RGB+UV-A Tomato (Zenodo) | Only public UV dataset |
| UV-A (main) | **Own chamber captures** | Must collect with hardware |
| Gas | **Own BME688 dataset** | Must collect with hardware |

**Supported Produce (11):** Tomato, Banana, Eggplant, Apple, Carrot, Grape, Cucumber, Guava, Orange, Potato, Pomegranate

---

## 📦 Inspection Chamber Specs

| Parameter | Value |
|---|---|
| Dimensions | L: 11" × W: 17" × H: 9" (~27.6 L) |
| Interior finish | Matte black (no reflections) |
| Camera | RPi Camera Module 2 (side wall, ~35° downward tilt) |
| Turntable | 7" diameter, PLA+ 3D printed |
| Motor mount | Under-floor (only shaft pokes through) |
| Scan geometry | 8 stops × 45° = 360° |

---

## 🗺️ Stage Roadmap

### ✅ Stage 1 (Active Build — This Repo)
- [x] Inspection chamber (matte-black box)
- [x] 8-angle stepper motor turntable
- [x] White LED + 365nm UV-A LED capture
- [x] BME688 gas sensing (VOC / ethylene)
- [x] FastAPI laptop server + SQLite DB
- [x] Real-time WebSocket dashboard
- [x] Rule-based AI (placeholder until model trained)
- [ ] ONNX model training (after dataset collection)

### 🔮 Stage 2 (Future)
- [ ] Motorized PVC conveyor belt (12V gearmotor + L298N)
- [ ] Break-beam optical sensors (fruit arrival detection)
- [ ] MG996R servo diverter gate (ACCEPTED/REJECTED bins)
- [ ] 40mm 5V exhaust blower fan (automated gas purge)
- [ ] Light-tight silicone entry/exit curtains

---

## 👨‍💻 Course Info

- **University:** United International University (UIU)
- **Course:** CSE 4326 — Microprocessors and Microcontrollers Laboratory
- **Year:** 4th Year CSE