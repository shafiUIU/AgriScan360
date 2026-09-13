# AgriScan 360 — User Action Checklist
**Project:** AgriScan 360 (Stage 1 — Multi-Spectral Produce Freshness Inspection Chamber)  
**Course:** CSE 4326 (Microprocessors & Microcontrollers Lab), UIU  

---

## 📋 Phase 1: Physical Fabrication & Chamber Assembly
- [ ] **1.1 Box Interior Preparation**
  - [ ] Line or spray the interior of the chamber (11" L × 17" W × 9" H) with matte-black finish/paper to eliminate internal reflections.
- [ ] **1.2 Turntable Fabrication**
  - [ ] 3D print or laser-cut the 7-inch diameter (3.5" radius) turntable plate in PLA+ material.
  - [ ] Drill a central hole through the box floor for the NEMA 17 motor shaft.
- [ ] **1.3 Motor Mounting**
  - [ ] Securely mount the NEMA 17 stepper motor **underneath the box floor** with vibration dampers/brackets so only the shaft protrudes into the box.
  - [ ] Attach the 3D-printed turntable firmly to the motor shaft.
- [ ] **1.4 Sensor & Illumination Placement**
  - [ ] Mount the **Raspberry Pi Camera Module 2** on the upper side wall tilted ~35° downward towards the turntable center.
  - [ ] Mount the **White Diffused LED Array** (with butter-paper diffuser) around or adjacent to the camera.
  - [ ] Mount the **365nm UV-A LED Array** on the side wall pointing at the fruit placement zone.
  - [ ] Mount the **45° angled mirror** on the opposite side wall to give the camera a line-of-sight to the fruit's underside/bottom.
  - [ ] Mount the **Bosch BME688** gas sensor on the ceiling directly above the turntable to sniff rising VOC gases.
  - [ ] Mount the **SSD1306 0.96" OLED display** on the outer front wall of the box for the operator.

---

## ⚡ Phase 2: Electrical Wiring & Driver Tuning
- [ ] **2.1 Stepper Driver (A4988) Wiring**
  - [ ] Connect `STEP` → Pi GPIO 17 (Pin 11).
  - [ ] Connect `DIR` → Pi GPIO 27 (Pin 13).
  - [ ] Connect `ENABLE` → Pi GPIO 22 (Pin 15).
  - [ ] Bridge `RST` and `SLP` pins together on the A4988 board.
  - [ ] Connect `VMOT` and `GND` to the 12V DC power supply.
  - [ ] **CRITICAL:** Connect the 12V PSU Ground to the Raspberry Pi GND (Common Ground).
  - [ ] Connect NEMA 17 motor phases: Pin 1 → 1A, Pin 3 → 1B, Pin 4 → 2A, Pin 6 → 2B.
- [ ] **2.2 A4988 Current Limit (Vref) Calibration**
  - [ ] Using a multimeter, measure Vref between the trimmer potentiometer and GND.
  - [ ] Adjust potentiometer to limit current to ~0.4A for the 4S42Q-P0404S motor (`Vref ≈ 0.4 × 8 × 0.1 = 0.32V` for Rs=0.1Ω) so the motor does not overheat.
- [ ] **2.3 IRLZ44N MOSFET Switching Circuits**
  - [ ] **MOSFET #1 (White LEDs):**
    - Gate → Pi GPIO 18 (Pin 12) with a 10kΩ pull-down resistor to GND.
    - Drain → White LED Array negative (−) terminal.
    - Source → Common GND.
    - LED positive (+) → 12V / 5V power rail.
  - [ ] **MOSFET #2 (365nm UV LEDs):**
    - Gate → Pi GPIO 24 (Pin 18) with a 10kΩ pull-down resistor to GND.
    - Drain → UV LED Array negative (−) terminal.
    - Source → Common GND.
    - LED positive (+) → 12V / 5V power rail.
- [ ] **2.4 I2C Sensor & Display Bus**
  - [ ] Connect Pi 3.3V (Pin 1) to BME688 VCC and SSD1306 VCC.
  - [ ] Connect Pi GND (Pin 6) to BME688 GND and SSD1306 GND.
  - [ ] Connect Pi GPIO 2 (SDA, Pin 3) to both BME688 SDA and SSD1306 SDA.
  - [ ] Connect Pi GPIO 3 (SCL, Pin 5) to both BME688 SCL and SSD1306 SCL.

---

## 🧪 Phase 3: Bench Diagnostic Tests (On Raspberry Pi)
- [ ] **3.1 I2C Address Verification**
  - [ ] Run `i2cdetect -y 1` in Pi terminal. Confirm `0x77` (BME688) and `0x3c` (OLED) appear.
- [ ] **3.2 BME688 Standalone Test**
  - [ ] Run `python test_bme688.py`. Verify live readings of Temperature, Humidity, and Gas Resistance (kΩ).
- [ ] **3.3 Stepper Motor Test**
  - [ ] Run `python run_stepper_continuous.py`. Confirm smooth clockwise rotation without jittering or stalling.
- [ ] **3.4 Dual LED Test & UV Verification**
  - [ ] Run `python test_dual_lights.py`. Confirm White LED and UV LED alternate cleanly every 5 seconds.
  - [ ] **UV Safety/Wavelength Check:** In a darkened room, shine the UV light on a ৳500 note. Confirm glowing security threads appear without excessive purple glare (confirms true 365nm UV-A).

---

## 💻 Phase 4: Network & Laptop Server Deployment
- [ ] **4.1 Network Setup**
  - [ ] Connect both the Laptop and the Raspberry Pi 5 to the **same Wi-Fi router** (or laptop mobile hotspot).
  - [ ] Open terminal on laptop, run `ipconfig`, note your **IPv4 Address** (e.g., `192.168.1.105`).
- [ ] **4.2 Pi Configuration Update**
  - [ ] In `AgriScan360/pi_client/config.py`, change:
    ```python
    LAPTOP_SERVER_URL = "http://192.168.1.105:8000"  # Replace with your laptop IP
    ```
- [ ] **4.3 Start the Laptop FastAPI Server**
  - [ ] Double-click `start_server.bat` (or run `python -m uvicorn main_server:app --host 0.0.0.0 --port 8000 --reload` inside `laptop_server/`).
  - [ ] Open `http://localhost:8000` in your laptop browser.
  - [ ] Check the connection indicator in the top navbar: it should show **Live** (WebSocket connected).

---

## 🚀 Phase 5: End-to-End System Testing
- [ ] **5.1 Pi Simulation Run (Dry-Run)**
  - [ ] On the Pi, run:
    ```bash
    python pi_client/main.py --simulate
    ```
  - [ ] Check that dummy scan data and images are transmitted to the laptop.
  - [ ] Confirm the laptop dashboard updates live with the result and updates the SQLite database.
- [ ] **5.2 Full Physical Scan Run**
  - [ ] Place a test fruit (e.g. Tomato or Banana) on the turntable.
  - [ ] On the Pi, run:
    ```bash
    bash start_pi.sh
    ```
  - [ ] Follow prompts: select fruit, allow gas baseline calibration, press Enter.
  - [ ] Observe:
    - [ ] Motor executes 8 stops (45° increments = 360° total).
    - [ ] White light fires → RGB image taken at each stop.
    - [ ] UV light fires → UV image taken at each stop.
    - [ ] Post-scan gas delta is computed.
    - [ ] OLED displays `"UPLOADING..."` then shows final status (`HEALTHY` / `ROTTEN` / `UNCERTAIN`), Confidence %, and Gas Δ.
    - [ ] Laptop dashboard receives real-time WebSocket push: populates the 16-image matrix, updates statistics, and appends to the history table.
- [ ] **5.3 Offline Server Fallback Check**
  - [ ] Temporarily close the laptop server and trigger a scan.
  - [ ] Verify the OLED shows `"SERVER OFFLINE"` gracefully without crashing the Pi script.

---

## 📦 Phase 6: Repository & Git Push
- [ ] **6.1 Commit and Push to Remote**
  - [ ] In `AgriScan360/`, run:
    ```bash
    git add .
    git commit -m "feat: complete two-tier Stage 1 architecture (Pi client + FastAPI server + bio-tech dashboard)"
    git push origin master
    ```

---

## 🔮 Phase 7: Future ML Model Training (When Ready)
- [ ] **7.1 Download Datasets**
  - [ ] Review `DataSet Link List.docx` for the strict 11 target produce items.
  - [ ] Download RGB datasets (Freshness44, BrinjalFruitX, Fruits-360).
- [ ] **7.2 Collect Real Chamber Samples**
  - [ ] Capture synchronized UV-A fluorescence images and BME688 gas logs using your actual hardware chamber.
- [ ] **7.3 Train Model & Export to ONNX**
  - [ ] Train multi-modal vision model, export as `agriscan360.onnx`.
  - [ ] Place `agriscan360.onnx` into `laptop_server/model/` (the server auto-detects it and switches from rule-based to neural inference).
