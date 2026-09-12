# AgriScan 360 🍎🔍

**An AI-Assisted 360° Multi-Spectral Fruit & Vegetable Quality Inspection Station**  
*Microprocessors and Microcontrollers Laboratory (CSE 4326) — United International University (UIU)*

---

## 📌 Project Overview

**AgriScan 360** is a standalone, multi-modal quality inspection station engineered to detect external and internal produce defects without cutting or destroying the fruit. 

Housed inside a light-tight, matte-black inspection chamber, the system combines:
1. **360° Multi-Angle Computer Vision:** An 8-stop motorized turntable rotates produce in front of a Raspberry Pi Camera Module 2.
2. **Dual-Spectrum Illumination:** Synchronized White LED (visible surface rot) and 365 nm UV-A LED (fungal/aflatoxin fluorescence).
3. **Electrochemical Gas Sensing:** A Bosch BME688 MOX gas sensor measures Volatile Organic Compounds (VOCs), ethanol, and ethylene to detect deep internal rot, core decay, and fruit borer damage that cameras cannot see.
4. **On-Device Multi-Modal AI Fusion:** Fuses visual and chemical data on a Raspberry Pi 5 to classify produce as `HEALTHY`, `ROTTEN`, or `UNCERTAIN`.
5. **Dual Output (Physical + IoT):** Displays instant results on an on-device SSD1306 OLED screen and broadcasts live telemetry over local Wi-Fi via a Flask web dashboard.

---

## 🔬 The 3 Pillars of Detection

| Inspection Pillar | Hardware Component | Physical Mechanism | Targeted Defects |
|---|---|---|---|
| **1. Surface Vision** | RPi Camera Module 2 + White LED (Diffused) | True-color surface reflectance across 8 angles (360°) | Visible skin rot, browning, bruising, necrosis, surface wrinkling, calyx/stem freshness |
| **2. Fungal Fluorescence** | RPi Camera Module 2 + 365 nm UV-A LED | Optical fluorescence of fungal metabolites & aflatoxins | Early-stage mould colonies, fungal mycelium, rot hidden in crevices or under calyx |
| **3. Chemical / Internal** | Bosch BME688 AI Gas Sensor | Metal-Oxide Semiconductor (MOX) VOC resistance drop | Internal core rot, fruit borer larvae (*Leucinodes orbonalis*), anaerobic fermentation gases |

---

## 🛠️ Hardware Bill of Materials (BOM)

| Component | Specification | Quantity | Role in System |
|---|---|:---:|---|
| **Raspberry Pi 5** | 4GB / 8GB RAM, 64-bit OS | 1 | Master compute, GPIO orchestration, AI inference, Flask server |
| **RPi Camera Module 2** | Sony IMX219, 8 MP RGB, CSI-2 | 1 | High-resolution multi-spectral optical capture |
| **Bosch BME688** | I2C (0x77 / 0x76), MOX Gas/T/H/P | 1 | Chamber headspace gas sensing for internal rot detection |
| **NEMA 17 Stepper Motor** | `4S42Q-P0404S` (1.8°/step, 200 steps/rev) | 1 | Drives rotating turntable in precise 45° increments |
| **A4988 Stepper Driver** | Microstepping bipolar motor driver | 1 | Translates STEP/DIR pulses to motor coil phases |
| **IRLZ44N MOSFETs** | Logic-level N-Channel MOSFETs | 2 | GPIO-controlled electronic switches for White & UV lights |
| **White LED Array** | 5V / 12V High-CRI LED chunk + Diffuser | 1 | Shadow-free visible surface lighting |
| **365 nm UV-A LED Array** | 365 nm Ultraviolet LED chunk | 1 | Excitation source for fungal fluorescence |
| **SSD1306 OLED Display** | 0.96", 128×64, I2C (0x3C) | 1 | Standalone physical result display |
| **Turntable Plate & Hub** | 3.5" radius (7" diameter), PLA+ / Acrylic | 1 | Rotating platform supporting the fruit |
| **Inspection Chamber** | L: 17", W: 11", H: 9" (Matte-Black) | 1 | Light-isolated and gas-controlled scanning environment |
| **12V DC Power Supply** | 12V, 2A–3A Regulated | 1 | Dedicated motor power (VMOT) and LED rail |
| **Official 27W USB-C PSU** | 5V, 5A DC | 1 | Clean, isolated power for Raspberry Pi 5 |

---

## ⚡ Wiring & Pinout Tables

### 1. Stepper Motor (A4988 to Raspberry Pi 5 & 12V Supply)
| A4988 Driver Pin | Connects To | Pin Number / Location | Function |
|---|---|:---:|---|
| **STEP** | Raspberry Pi GPIO 17 | Physical Pin 11 | Step pulse input |
| **DIR** | Raspberry Pi GPIO 27 | Physical Pin 13 | Direction control |
| **ENABLE** | Raspberry Pi GPIO 22 | Physical Pin 15 | Active LOW coil enable |
| **VDD** | Raspberry Pi 3.3V | Physical Pin 1 | Logic power |
| **GND (Logic)** | Raspberry Pi GND | Physical Pin 6 | Logic ground |
| **RST & SLP** | **Bridge Together** | Jumper wire across pins | Disables chip sleep mode |
| **VMOT** | External 12V Power (+) | 12V Adapter Positive | Motor power rail |
| **GND (Power)** | External 12V Power (-) | 12V Adapter Negative | **Must connect to Pi GND!** |
| **1A, 1B, 2A, 2B** | Motor Pins 1, 3, 4, 6 | 4S42Q-P0404S Socket | Motor coil phase connections |

### 2. Dual Lights (IRLZ44N MOSFET Low-Side Switches)
| MOSFET Unit | Gate (Pin 1) | Drain (Pin 2) | Source (Pin 3) |
|---|---|---|---|
| **MOSFET #1 (White)** | RPi GPIO 18 *(Physical Pin 12)* | White LED Chunk **Negative (-)** | Common Ground (GND) |
| **MOSFET #2 (UV 365nm)** | RPi GPIO 24 *(Physical Pin 18)* | UV LED Chunk **Negative (-)** | Common Ground (GND) |
* *Note: Positive (+) wire of both LED chunks connects directly to the Power Supply (+) rail.*

### 3. I2C Bus Devices (BME688 & SSD1306 OLED)
| Device Pin | Connects To (Raspberry Pi 5) | Physical Pin # | Function |
|---|---|:---:|---|
| **VCC / VIN** | Raspberry Pi 3.3V | Physical Pin 1 | Power supply |
| **GND** | Raspberry Pi GND | Physical Pin 9 / 14 | Ground |
| **SDA** | Raspberry Pi GPIO 2 (SDA) | Physical Pin 3 | I2C Data line (shared) |
| **SCL** | Raspberry Pi GPIO 3 (SCL) | Physical Pin 5 | I2C Clock line (shared) |

---

## 📁 Repository Structure

```
AgriScan360/
├── config.py                 # Central configurations, pinouts, and thresholds
├── motor.py                  # NEMA 17 stepper controller (45° steps, soft stop)
├── lights.py                 # Dual light switching via IRLZ44N MOSFETs
├── gas_sensor.py             # BME688 baseline calibration & VOC delta measurement
├── camera.py                 # Picamera2 / OpenCV synchronized frame capture
├── display.py                # SSD1306 OLED rendering module
├── ai_classifier.py          # Multi-modal decision fusion engine (Vision + Gas)
├── web_server.py             # Flask IoT web dashboard (Port 5000)
├── main.py                   # Master system orchestrator
├── test_bme688.py            # Standalone unit test for BME688 gas sensor
├── test_dual_lights.py       # Standalone alternating test for White & UV LEDs
├── run_stepper_continuous.py # Standalone test for continuous motor rotation
├── requirements.txt          # Python dependencies list
├── .gitignore                # Git ignore rules for bytecode & scan images
└── README.md                 # Project documentation
```

---

## 🚀 Getting Started & Installation

### 1. Enable Hardware Interfaces on Raspberry Pi 5
Open the terminal on your Raspberry Pi:
```bash
sudo raspi-config
```
* Navigate to **Interface Options** $\rightarrow$ Enable **I2C**.
* Navigate to **Interface Options** $\rightarrow$ Enable **Camera**.
* Reboot if prompted.

### 2. Clone the Repository
```bash
git clone https://github.com/your-username/AgriScan360.git
cd AgriScan360
```

### 3. Install System & Python Dependencies
```bash
# Update system package repository
sudo apt update

# Install hardware backend drivers and packages
sudo apt install -y python3-gpiozero python3-lgpio python3-smbus i2c-tools python3-pip

# Install Python packages
pip install -r requirements.txt --break-system-packages
```

---

## 🧪 Hardware Unit Testing

Before running the complete system, test each hardware subsystem independently:

1. **Test Stepper Motor:**
   ```bash
   python3 run_stepper_continuous.py
   ```
2. **Test Dual Illumination (White & UV):**
   ```bash
   python3 test_dual_lights.py
   ```
3. **Test BME688 Gas Sensor:**
   ```bash
   python3 test_bme688.py
   ```

---

## 🏁 Running the Master Inspection System

Execute the master orchestration script:
```bash
python3 main.py
```

### Automated Inspection Workflow:
1. **IoT Dashboard Launches:** The Flask web server spins up automatically in a background daemon thread at `http://<your-pi-ip>:5000`.
2. **Chamber Calibration:** The BME688 records a clean air baseline of the sealed chamber.
3. **8-Angle 360° Scan:**
   * Stepper rotates turntable in 45° increments across 8 stops.
   * Snaps an **RGB frame** under White light.
   * Snaps a **Fluorescence frame** under 365 nm UV light.
4. **Chemical Analysis:** Measures accumulated chamber VOCs and calculates the resistance drop ($\Delta Gas$).
5. **AI Fusion Inference:** Combines 16 multi-spectral frames with the gas delta to classify produce as:
   * `HEALTHY` (High confidence fresh)
   * `ROTTEN` (Surface necrosis or internal rot gas spike)
   * `UNCERTAIN` (Borderline / manual inspection recommended)
6. **Telemetry Broadcast:** Results update simultaneously on the **SSD1306 OLED** and the **Flask Web Dashboard**.
7. **Safe De-energize:** Stepper motor coils automatically shut off to remain completely cool between inspections.

---

## 🌐 IoT Web Dashboard

The Flask web interface is accessible from any phone, tablet, or laptop connected to the same local network:

```
http://<RASPBERRY_PI_IP>:5000
```
* Real-time classification status badge (`HEALTHY`, `ROTTEN`, `UNCERTAIN`)
* AI confidence percentage metric
* Live chamber gas delta ($\Delta Gas$) reading
* Automated timestamped inspection log

---

## 🎓 Academic Context

* **Institution:** United International University (UIU)
* **Department:** Department of Computer Science and Engineering
* **Course:** Microprocessors and Microcontrollers Laboratory (CSE 4326)
* **Project Title:** AgriScan 360: Multi-Spectral Produce Quality Inspection Station