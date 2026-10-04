"""
tools/generate_circuit_diagram.py
Generates a publication-grade, professional circuit schematic diagram
for the AgriScan 360 system (CSE 4326 Microcontrollers Laboratory).
Pure ASCII encoding.
"""

import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches

def draw_circuit():
    fig, ax = plt.subplots(figsize=(16, 10.2), dpi=300)
    ax.set_facecolor("#F8FAFC")
    fig.patch.set_facecolor("#FFFFFF")

    # Set coordinate space: 0 to 100 on both axes
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    # Header / Title Block
    ax.text(50, 97.6, "AgriScan 360 -- System Circuit & Hardware Interconnect Schematic",
            ha="center", va="center", fontsize=15, fontweight="bold", color="#0F172A", family="sans-serif")
    ax.text(50, 95.3, "CSE 4326: Microprocessors & Microcontrollers Laboratory | Department of CSE, United International University (UIU)",
            ha="center", va="center", fontsize=9.2, color="#475569", family="sans-serif")

    # Helper function to draw rounded boxes
    def draw_box(x, y, w, h, title, subtitle="", bg_color="#FFFFFF", border_color="#1E293B", lw=1.5):
        box = patches.FancyBboxPatch((x, y), w, h,
                                     boxstyle="round,pad=0.5,rounding_size=0.8",
                                     facecolor=bg_color, edgecolor=border_color, linewidth=lw, zorder=2)
        ax.add_patch(box)
        if title:
            ax.text(x + w/2, y + h - 2.0, title, ha="center", va="center",
                    fontsize=9.0, fontweight="bold", color="#0F172A", zorder=3, family="sans-serif")
        if subtitle:
            ax.text(x + w/2, y + h - 3.8, subtitle, ha="center", va="center",
                    fontsize=7.0, color="#475569", style="italic", zorder=3, family="sans-serif")
        return box

    # Helper function for pin badge
    def draw_pin(x, y, label, color="#1E293B", align="left"):
        ax.plot(x, y, marker="o", markersize=4.2, color=color, zorder=5)
        offset = 0.8 if align == "left" else -0.8
        ax.text(x + offset, y, label, fontsize=6.8, fontweight="bold", color=color,
                ha=align, va="center", zorder=4, family="monospace")

    # =========================================================================
    # 1. CENTRAL MASTER: Raspberry Pi 5 (x=33 to 67, w=34, y=36 to 90, h=54)
    # =========================================================================
    rpi_x, rpi_y, rpi_w, rpi_h = 33, 36, 34, 54
    draw_box(rpi_x, rpi_y, rpi_w, rpi_h, "Raspberry Pi 5 (4GB Model)",
             "Broadcom BCM2712 Quad Cortex-A76 @ 2.4GHz",
             bg_color="#EFF6FF", border_color="#1D4ED8", lw=2.2)

    # Core specs inside RPi box
    ax.text(rpi_x + rpi_w/2, 63, "Main System Edge Controller\n64-bit OS | Wi-Fi / LAN Sync\nFastAPI Local Host Interconnect",
            ha="center", va="center", fontsize=7.2, color="#1E40AF", style="italic")

    # Left-side pins (Stepper, Servo, Power)
    left_pins = [
        ("+3.3V Logic [Pin 1]", 85, "#D97706"),
        ("+5.0V DC [Pin 2]", 81, "#DC2626"),
        ("GND [Pin 6]", 77, "#1E293B"),
        ("STEP [GPIO 17 / Pin 11]", 57, "#7C3AED"),
        ("DIR [GPIO 27 / Pin 13]", 53, "#2563EB"),
        ("ENABLE [GPIO 22 / Pin 15]", 49, "#0D9488"),
        ("SERVO PWM [GPIO 23 / Pin 16]", 43, "#16A34A"),
        ("GND [Pin 14]", 39, "#1E293B"),
    ]
    for lbl, yp, col in left_pins:
        draw_pin(rpi_x, yp, lbl, color=col, align="left")

    # Right-side pins (Camera, I2C, MOSFETs)
    right_pins = [
        ("MIPI CSI-2 [CAM0]", 85, "#4338CA"),
        ("I2C SDA [GPIO 2 / Pin 3]", 77, "#059669"),
        ("I2C SCL [GPIO 3 / Pin 5]", 73, "#0D9488"),
        ("Sensor GND [Pin 9]", 69, "#1E293B"),
        ("White Gate [GPIO 18 / Pin 12]", 53, "#D97706"),
        ("UV-A Gate [GPIO 24 / Pin 18]", 49, "#9333EA"),
        ("MOSFET GND [Pin 20]", 45, "#1E293B"),
    ]
    for lbl, yp, col in right_pins:
        draw_pin(rpi_x + rpi_w, yp, lbl, color=col, align="right")

    # =========================================================================
    # 2. LEFT COLUMN: POWER & ACTUATION (x=3 to 27, w=24)
    # =========================================================================

    # 2.1 12V 2A DC SMPS (x=3, y=78, w=24, h=12)
    draw_box(3, 78, 24, 12, "12V 2A DC SMPS", "External High-Power Supply",
             bg_color="#FEF2F2", border_color="#B91C1C", lw=1.5)
    ax.text(5, 84.5, "+12V VCC Rail", fontsize=7.2, fontweight="bold", color="#B91C1C")
    ax.text(5, 81.5, "Common GND Rail", fontsize=7.2, fontweight="bold", color="#1E293B")
    ax.plot([20, 20], [84.5, 81.5], color="#B91C1C", lw=1.2, linestyle="--")
    ax.text(21, 83.0, "100uF", fontsize=6.2, color="#B91C1C", va="center")

    # 2.2 A4988 Stepper Driver (x=3, y=47, w=24, h=27)
    draw_box(3, 47, 24, 27, "A4988 Stepper Driver", "Microstepping Driver Module",
             bg_color="#F5F3FF", border_color="#6D28D9", lw=1.5)
    a4988_labels = [
        ("VMOT <- +12V SMPS", 68.5, "#B91C1C"),
        ("VDD  <- +3.3V (Pi Pin 1)", 65.5, "#D97706"),
        ("GND  <- Power & Logic GND", 62.5, "#1E293B"),
        ("STEP <- GPIO 17 (Pin 11)", 59.0, "#7C3AED"),
        ("DIR  <- GPIO 27 (Pin 13)", 56.0, "#2563EB"),
        ("EN   <- GPIO 22 (Pin 15)", 53.0, "#0D9488"),
        ("RESET <-> SLEEP (Bridged)", 49.5, "#4C1D95"),
    ]
    for lbl, yp, col in a4988_labels:
        ax.text(5, yp, lbl, fontsize=6.8, color=col, va="center", family="monospace")

    # 2.3 NEMA 17 Stepper Motor (x=3, y=28, w=24, h=15)
    draw_box(3, 28, 24, 15, "NEMA 17 Stepper (17HS4401)", "Turntable 360 deg Indexer",
             bg_color="#F8FAFC", border_color="#334155", lw=1.4)
    ax.text(15, 35.5, "4 Leads: 1A, 1B, 2A, 2B", fontsize=6.8, ha="center", color="#4338CA", fontweight="bold")
    ax.text(15, 33.0, "1.8 deg / Step (200 steps/rev)", fontsize=6.6, ha="center", color="#334155")
    ax.text(15, 30.5, "8 Stops x 45 deg (25 steps/stop)", fontsize=6.6, ha="center", fontweight="bold", color="#0F172A")

    # Arrow A4988 -> NEMA 17
    ax.annotate("", xy=(15, 43), xytext=(15, 47),
                arrowprops=dict(arrowstyle="->", color="#6D28D9", lw=1.5))

    # 2.4 SG90 Micro Servo (x=3, y=8, w=24, h=16)
    draw_box(3, 8, 24, 16, "TowerPro SG90 Micro Servo", "7-inch Pipe Feeder Door Gate",
             bg_color="#F0FDF4", border_color="#15803D", lw=1.5)
    ax.text(5, 17.5, "VCC <- +5.0V (Pi Pin 2)", fontsize=6.8, color="#15803D")
    ax.text(5, 15.0, "GND <- Common GND (Pin 14)", fontsize=6.8, color="#1E293B")
    ax.text(5, 12.5, "PWM <- GPIO 23 (Pin 16)", fontsize=6.8, fontweight="bold", color="#15803D")
    ax.text(5, 10.0, "90 deg: CLOSED | 180 deg: OPEN", fontsize=6.5, color="#166534", style="italic")

    # =========================================================================
    # 3. RIGHT COLUMN: SENSORS, CAMERA & DISPLAY (x=73 to 97, w=24)
    # =========================================================================

    # 3.1 Pi Camera Module 2 (x=73, y=77, w=24, h=13)
    draw_box(73, 77, 24, 13, "Pi Camera Module 2", "Sony IMX219 8.08MP (MIPI CSI-2)",
             bg_color="#EEF2FF", border_color="#4338CA", lw=1.5)
    ax.text(85, 83.5, "15-Pin MIPI CSI-2 Flex Ribbon", fontsize=6.8, ha="center", color="#4338CA", fontweight="bold")
    ax.text(85, 81.0, "Dual Capture: 8 RGB + 8 UV Frames", fontsize=6.5, ha="center", color="#3730A3")
    ax.text(85, 78.8, "ROI Crop: X 25-76%, Y 41-100%", fontsize=6.5, ha="center", color="#1E1B4B")

    # 3.2 Bosch BME688 MOX Gas Sensor (x=73, y=42, w=24, h=31)
    draw_box(73, 42, 24, 31, "Bosch BME688 MOX Sensor", "Headspace Chemical E-Nose",
             bg_color="#ECFDF5", border_color="#059669", lw=1.5)
    bme_lines = [
        ("I2C Address: 0x77 (Shared)", 66.5, "#065F46", True),
        ("VCC <- +3.3V | GND <- GND", 63.8, "#047857", False),
        ("SDA <- GPIO 2 | SCL <- GPIO 3", 61.2, "#047857", False),
        ("Headspace VOC Sniffing", 57.5, "#0F172A", True),
        ("Measures: R_base, Delta R, Ratio, Slope", 54.8, "#334155", False),
        ("Gas Override: Delta R >= 5.5k Ohm", 52.0, "#B91C1C", True),
        ("Runs parallel with 8-Stop Scan", 49.2, "#475569", False),
        ("Heated MOX Plate (300 C)", 46.5, "#475569", False),
        ("Temp, Humidity, Pressure Telemetry", 43.8, "#475569", False),
    ]
    for txt, yp, col, is_b in bme_lines:
        w_flag = "bold" if is_b else "normal"
        ax.text(75, yp, txt, fontsize=6.6, color=col, fontweight=w_flag, va="center")

    # 3.3 SSD1306 0.96" OLED Display (x=73, y=8, w=24, h=30)
    draw_box(73, 8, 24, 30, "SSD1306 0.96\" OLED", "128x64 Local Diagnostic HMI",
             bg_color="#F8FAFC", border_color="#0284C7", lw=1.5)
    oled_lines = [
        ("I2C Address: 0x3C (Shared)", 31.5, "#0369A1", True),
        ("VCC <- +3.3V | GND <- GND", 29.0, "#0284C7", False),
        ("SDA <- GPIO 2 | SCL <- GPIO 3", 26.5, "#0284C7", False),
        ("Live Status Visualization:", 23.0, "#0F172A", True),
        ("* Preheating / Sniffing / Scanning", 20.5, "#334155", False),
        ("* Produce: Tomato / Apple / Eggplant", 18.0, "#334155", False),
        ("* Classification: HEALTHY / ROTTEN", 15.2, "#B91C1C", True),
        ("* Confidence % & Delta R Value", 12.5, "#475569", False),
        ("* Inspect & Halt: Manual Pickup Prompt", 9.8, "#166534", True),
    ]
    for txt, yp, col, is_b in oled_lines:
        w_flag = "bold" if is_b else "normal"
        ax.text(75, yp, txt, fontsize=6.6, color=col, fontweight=w_flag, va="center")

    # =========================================================================
    # 4. BOTTOM CENTER: DUAL MOSFET ILLUMINATION DRIVER (x=33 to 67, w=34)
    # =========================================================================
    draw_box(33, 8, 34, 24, "Dual IRLZ44N MOSFET Illumination Board",
             "Solid-State Logic-Level LED Switching",
             bg_color="#FFFBEB", border_color="#D97706", lw=1.5)

    ax.text(35, 25.5, "Channel 1 -- White LED Array (12V):", fontsize=7.0, fontweight="bold", color="#B45309")
    ax.text(36, 23.2, "* Gate: GPIO 18 [Pin 12] + 10k pulldown to GND", fontsize=6.5, color="#78350F")
    ax.text(36, 21.0, "* Drain: White LED Cathode (-) | Source: GND", fontsize=6.5, color="#78350F")
    ax.text(36, 18.8, "* Anode (+): Tied to +12V SMPS Power Rail", fontsize=6.5, color="#B91C1C", fontweight="bold")

    ax.text(35, 16.0, "Channel 2 -- 365 nm UV-A LED Array (12V):", fontsize=7.0, fontweight="bold", color="#7E22CE")
    ax.text(36, 13.7, "* Gate: GPIO 24 [Pin 18] + 10k pulldown to GND", fontsize=6.5, color="#581C87")
    ax.text(36, 11.5, "* Drain: UV-A LED Cathode (-) | Source: GND", fontsize=6.5, color="#581C87")
    ax.text(36, 9.3, "* Anode (+): Tied to +12V SMPS Power Rail", fontsize=6.5, color="#B91C1C", fontweight="bold")

    # =========================================================================
    # 5. INTERCONNECT WIRES & BUSES
    # =========================================================================

    # 5.1 Power: SMPS 12V -> A4988 VMOT
    ax.annotate("", xy=(15, 74), xytext=(15, 78),
                arrowprops=dict(arrowstyle="->", color="#B91C1C", lw=2.0))
    ax.text(16.5, 75.8, "+12V", fontsize=7.2, fontweight="bold", color="#B91C1C")

    # 5.2 Power: SMPS 12V -> MOSFET Board
    ax.plot([27, 30, 30, 33], [84.5, 84.5, 18.8, 18.8], color="#B91C1C", lw=1.4, linestyle=":")
    ax.text(30.6, 55, "+12V Rail to LED Anodes", fontsize=6.5, fontweight="bold", color="#B91C1C", rotation=90, va="center")

    # 5.3 Common Ground: SMPS GND <-> Pi GND
    ax.plot([27, 30, 30, 33], [81.5, 81.5, 77, 77], color="#1E293B", lw=1.4, linestyle="--")
    ax.text(28.5, 80.0, "GND", fontsize=6.5, fontweight="bold", color="#1E293B", ha="center")

    # 5.4 Logic Power: Pi Pin 1 (+3.3V) -> A4988 VDD
    ax.plot([33, 31, 31, 27], [85, 85, 65.5, 65.5], color="#D97706", lw=1.4)
    ax.text(31.8, 75, "+3.3V", fontsize=6.5, color="#D97706", rotation=90, va="center")

    # 5.5 Stepper Signals: Pi -> A4988
    # STEP (GPIO 17)
    ax.annotate("", xy=(27, 59.0), xytext=(33, 57.0),
                arrowprops=dict(arrowstyle="<-", color="#7C3AED", lw=1.4))
    # DIR (GPIO 27)
    ax.annotate("", xy=(27, 56.0), xytext=(33, 53.0),
                arrowprops=dict(arrowstyle="<-", color="#2563EB", lw=1.4))
    # ENABLE (GPIO 22)
    ax.annotate("", xy=(27, 53.0), xytext=(33, 49.0),
                arrowprops=dict(arrowstyle="<-", color="#0D9488", lw=1.4))

    # 5.6 Servo Signals: Pi -> SG90
    ax.plot([33, 29, 29, 27], [43, 43, 12.5, 12.5], color="#16A34A", lw=1.4)
    ax.text(28.2, 26, "GPIO 23 PWM", fontsize=6.5, color="#16A34A", rotation=90, va="center")
    # 5V Servo Power
    ax.plot([33, 30, 30, 27], [81, 81, 17.5, 17.5], color="#DC2626", lw=1.2, linestyle="--")

    # 5.7 MOSFET Gates: Pi -> MOSFET Board
    ax.annotate("", xy=(50, 32), xytext=(50, 36),
                arrowprops=dict(arrowstyle="->", color="#D97706", lw=1.6))
    ax.text(51.2, 34.0, "GPIO 18 / 24 Gates", fontsize=6.8, color="#B45309", fontweight="bold")

    # 5.8 Camera: Pi CAM0 -> Camera Module (MIPI CSI Ribbon)
    ax.plot([67, 70, 70, 73], [85, 85, 83.5, 83.5], color="#4338CA", lw=2.2)
    ax.text(70, 85.5, "MIPI CSI-2", fontsize=6.8, fontweight="bold", color="#4338CA", ha="center")

    # 5.9 Shared I2C Bus: Pi -> BME688 & OLED
    # Trunk line
    ax.plot([67, 70, 70], [75, 75, 26.5], color="#059669", lw=2.0)
    ax.text(71.2, 52, "Shared I2C Bus (SDA / SCL @ 400kHz)", fontsize=6.8, fontweight="bold", color="#059669", rotation=90, va="center")
    # Tap to BME688 (0x77)
    ax.annotate("", xy=(73, 61.2), xytext=(70, 61.2),
                arrowprops=dict(arrowstyle="->", color="#059669", lw=1.4))
    # Tap to OLED (0x3C)
    ax.annotate("", xy=(73, 26.5), xytext=(70, 26.5),
                arrowprops=dict(arrowstyle="->", color="#059669", lw=1.4))

    # 6. Bottom Legend / Engineering Notes
    notes = (
        "Design Notes: [1] Common ground plane interconnects 12V SMPS, Raspberry Pi logic ground, and A4988 GND. "
        "[2] A4988 RESET & SLEEP bridged to activate internal translator. "
        "[3] Logic-level IRLZ44N MOSFET gates have 10k pulldowns. "
        "[4] BME688 (0x77) and SSD1306 (0x3C) operate simultaneously on shared I2C bus."
    )
    ax.text(50, 3.2, notes, ha="center", va="center", fontsize=7.2, color="#334155", style="italic")

    plt.tight_layout()
    return fig

if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    parent = os.path.dirname(root)
    reports = os.path.join(root, "reports")
    os.makedirs(reports, exist_ok=True)

    fig = draw_circuit()

    out1 = os.path.join(reports, "circuit_diagram.png")
    out2 = os.path.join(root, "circuit_diagram.png")
    out3 = os.path.join(parent, "circuit_diagram.png")

    fig.savefig(out1, dpi=300, bbox_inches="tight")
    fig.savefig(out2, dpi=300, bbox_inches="tight")
    fig.savefig(out3, dpi=300, bbox_inches="tight")
    plt.close(fig)

    print("[+] Circuit diagram successfully generated:")
    print("    ->", out1)
    print("    ->", out2)
    print("    ->", out3)
