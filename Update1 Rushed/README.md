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

## 🏗️ System Architecture

```
┌─────────────────────────────────┐       Wi-Fi LAN       ┌──────────────────────────────────────┐
│      RASPBERRY PI 5  (Edge)     │  ───────────────────▶  │       LAPTOP  (AI Server)            │
│                                 │   HTTP POST /api/scan   │                                      │
│  • NEMA 17 Stepper + A4988      │   16 images + gas data  │  • FastAPI + Uvicorn (port 8000)     │
│  • White LED Array (IRLZ44N)    │                         │  • SQLite via SQLAlchemy ORM         │
│  • 365nm UV-A Array (IRLZ44N)   │  ◀───────────────────   │  • AI Classifier (rule-based→ONNX)   │
│  • RPi Camera Module 2 (8MP)    │   JSON result           │  • WebSocket live dashboard push     │
│  • BME688 Gas Sensor (I2C)      │                         │  • Web dashboard at localhost:8000   │
│  • SSD1306 OLED 0.96" (I2C)    │                         │                                      │
└─────────────────────────────────┘                         └──────────────────────────────────────┘
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

## ⚡ Quick Start

### Step 1 — Start the Laptop Server

```bash
# On your Windows laptop:
cd "path\to\AgriScan360"
start_server.bat

# Or manually:
cd laptop_server
pip install -r requirements_laptop.txt
python -m uvicorn main_server:app --host 0.0.0.0 --port 8000 --reload
```

Open **http://localhost:8000** in your browser → Dashboard appears.

### Step 2 — Configure the Pi

Edit `pi_client/config.py` and set your laptop's LAN IP:
```python
LAPTOP_SERVER_URL = "http://192.168.1.XXX:8000"   # ← Your laptop's IP from ipconfig
```

> Run `ipconfig` on your laptop and find the **IPv4 Address** under your Wi-Fi adapter.

### Step 3 — Start the Pi Client

```bash
# On the Raspberry Pi:
cd /path/to/AgriScan360
bash start_pi.sh

# Or manually:
cd pi_client
pip install -r requirements_pi.txt
python main.py
```

### Step 4 — Run a Scan

1. Select produce type (Tomato, Banana, etc.)
2. The Pi calibrates BME688 gas baseline (empty chamber)
3. Place fruit on the turntable → press **Enter**
4. Motor rotates 8× 45° → camera captures 16 images
5. Images + gas data POST to laptop → AI classifies → result appears on OLED + dashboard

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