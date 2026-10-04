"""
tools/generate_report.py
Generates both the LaTeX (.tex) and compiled PDF (.pdf) versions of the
AgriScan 360 Final Engineering Project Report for CSE 4326 Micro Lab.
Pure ASCII encoding.
"""

import os
import sys
import shutil
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image, HRFlowable, KeepTogether
)
from reportlab.pdfgen import canvas

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PARENT = os.path.dirname(ROOT)
REPORTS_DIR = os.path.join(ROOT, "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

TEX_OUT = os.path.join(REPORTS_DIR, "AgriScan360_Final_Report.tex")
PDF_OUT = os.path.join(REPORTS_DIR, "AgriScan360_Final_Report.pdf")

LOGO_PATH = os.path.join(PARENT, "image1.jpeg")
if not os.path.exists(LOGO_PATH):
    LOGO_PATH = os.path.join(ROOT, "image1.jpeg")
if not os.path.exists(LOGO_PATH):
    LOGO_PATH = os.path.join(REPORTS_DIR, "image1.jpeg")

CIRCUIT_DIAG_PATH = os.path.join(REPORTS_DIR, "circuit_diagram.png")
if not os.path.exists(CIRCUIT_DIAG_PATH):
    CIRCUIT_DIAG_PATH = os.path.join(ROOT, "circuit_diagram.png")
if not os.path.exists(CIRCUIT_DIAG_PATH):
    CIRCUIT_DIAG_PATH = os.path.join(PARENT, "circuit_diagram.png")

# -----------------------------------------------------------------------------
# 1. GENERATE LATEX DOCUMENT (.tex)
# -----------------------------------------------------------------------------

LATEX_CONTENT = r"""\documentclass[11pt,a4paper]{article}

\usepackage[utf8]{inputenc}
\usepackage[margin=1in]{geometry}
\usepackage{amsmath,amssymb}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{tabularx}
\usepackage{xcolor}
\usepackage{hyperref}
\usepackage{fancyhdr}
\usepackage{titlesec}
\usepackage{enumitem}
\usepackage{caption}
\usepackage{float}

% Colors
\definecolor{primaryblue}{RGB}{27, 54, 93}
\definecolor{accentgreen}{RGB}{13, 104, 50}
\definecolor{darkgray}{RGB}{60, 60, 60}
\definecolor{lightgray}{RGB}{245, 247, 250}
\definecolor{bordergray}{RGB}{210, 215, 225}

% Hyperref setup
\hypersetup{
    colorlinks=true,
    linkcolor=primaryblue,
    citecolor=primaryblue,
    urlcolor=primaryblue
}

% Header / Footer
\pagestyle{fancy}
\fancyhf{}
\lhead{\textcolor{primaryblue}{\textbf{AgriScan 360 --- Final Laboratory Report}}}
\rhead{\textcolor{darkgray}{CSE 4326: Micro Lab}}
\cfoot{\thepage}
\renewcommand{\headrulewidth}{0.6pt}

% Section Titles
\titleformat{\section}
  {\color{primaryblue}\normalfont\Large\bfseries}{\thesection}{1em}{}[\titlerule]
\titleformat{\subsection}
  {\color{primaryblue}\normalfont\large\bfseries}{\thesubsection}{1em}{}
\titleformat{\subsubsection}
  {\color{darkgray}\normalfont\normalsize\bfseries}{\thesubsubsection}{1em}{}

\begin{document}

% --- Title Page (UIU Micro Lab Official Cover Page) ---
\begin{titlepage}
    \centering
    \vspace*{0.2cm}
    \includegraphics[width=3.6cm]{image1.jpeg}\\[0.5cm]
    {\LARGE \textbf{United International University}}\\[0.25cm]
    {\Large \textbf{Department of CSE}}\\[2.0cm]
    
    {\fontsize{32pt}{38pt}\selectfont \textbf{\color{primaryblue} AgriScan - 360}}\\[0.4cm]
    {\large \textbf{Automated Multi-Modal Non-Destructive Produce Quality, Internal Defect, and Freshness Inspection System}}\\[2.2cm]
    
    \begin{flushleft}
    \hspace{0.5cm}{\Large \textbf{Course Code: CSE 4326}}\\[0.3cm]
    \hspace{0.5cm}{\Large \textbf{Course Name: Microprocessors and Microcontrollers Laboratory}}\\[2.0cm]
    \end{flushleft}
    
    \begin{flushleft}
    \hspace{0.5cm}
    \setlength{\fboxsep}{12pt}
    \colorbox{lightgray}{%
    \begin{minipage}{0.88\textwidth}
        \textbf{\large Submitted by (Group no.): 02}\\[0.3cm]
        \textbf{\large Name: Md. Shafiul Bari}\\[0.3cm]
        \textbf{\large Student ID: 0112330837}
    \end{minipage}%
    }
    \end{flushleft}
    
    \vfill
    {\normalsize \textbf{Academic Session:} 2026 \quad $\vert$ \quad \textbf{Course:} CSE 4326 Microprocessors \& Microcontrollers Lab}
\end{titlepage}

\newpage
\tableofcontents
\newpage

% --- Section 1: Abstract & Introduction ---
\section{Abstract \& Introduction}

\subsection{Abstract}
Post-harvest food spoilage constitutes a critical economic and food-security crisis across developing agricultural economies such as Bangladesh, where an estimated 25\% to 40\% of harvested produce perishes prior to consumer distribution. Existing evaluation techniques in regional wholesale mandis remain either purely subjective (superficial human visual sorting that misses internal rot, hollow heart, and latent fungal pathogens) or destructively invasive (penetrometer punctures that ruin saleable produce). 

\textbf{AgriScan 360} resolves this trade-off by engineering an automated, multi-physics, non-destructive freshness inspection ecosystem for the CSE 4326 Microcontrollers Laboratory. The device integrates a gravity pipe feed chute gated by an SG90 micro-servo motor that drops produce into a 27-liter sealed dark chamber onto an 8-stop NEMA 17 stepper motor turntable ($45^\circ$ indexing). A Raspberry Pi 5 orchestrates simultaneous multi-modal sensing: continuous Volatile Organic Compound (VOC) headspace sniffing via a Bosch BME688 MOX gas sensor is executed in parallel with 16 synchronized optical captures (8 White-light RGB and 8 365 nm UV-A autofluorescence frames). Telemetry and multi-spectral imagery are streamed over HTTP multipart to a local host server running FastAPI and SQLite. A multi-modal decision engine fuses visual necrotic browning, fungal excitation, and dynamic gas resistance kinetics ($\Delta R$, drop ratio $\eta$, decay slope $dR/dt$) into a binary classification (\texttt{HEALTHY} vs. \texttt{ROTTEN}). Results are displayed locally on an SSD1306 OLED screen and on a live web dashboard. After scanning, the machine halts safely without automated sorting, allowing the human operator to manually pick up and sort the inspected item.

\subsection{Introduction}
Fresh fruits and vegetables are living biological tissues undergoing active metabolic respiration, transpiration, and volatile organic acid synthesis post-harvest. Traditional single-angle computer vision fails to detect early rot when decay occurs on the opposite side or internally near the seed cavity. Furthermore, latent fungal pathogens such as \textit{Botrytis cinerea} and \textit{Penicillium expansum} remain visually undetectable to the human eye for days before surface mycelium appears.

AgriScan 360 addresses these physical failure modes through three synchronized sensing pillars:
\begin{enumerate}[leftmargin=*]
    \item \textbf{Pillar 1: Complete $360^\circ$ Visible RGB Reflectance:} Captures 8 circumferential angles to eliminate visual blind spots, analyzing surface browning, skin integrity, and stem calyx condition.
    \item \textbf{Pillar 2: 365 nm UV-A Autofluorescence Excitation:} Stimulates fluorophores in fungal mycelium and leaked plant catabolites, revealing latent infections prior to visual spore emergence.
    \item \textbf{Pillar 3: Chemical Headspace E-Nose Kinetics:} Operates a Bosch BME688 MOX gas sensor in the sealed 27L enclosure, tracking VOC evaporation, fermentation ethanol, and respiration velocity.
\end{enumerate}

% --- Section 2: Objectives ---
\section{Project Objectives}
\begin{itemize}[leftmargin=*]
    \item \textbf{Comprehensive $360^\circ$ Spatial Assessment:} Eliminate visual occlusions by rotating produce across 8 discrete $45^\circ$ stops using a precision stepper-driven turntable.
    \item \textbf{Simultaneous Optical \& Chemical Acquisition:} Overlap dual-spectrum optical imaging (White RGB + 365 nm UV-A) with continuous chemical gas sniffing, reducing total testing time from ~5 minutes to ~3 minutes.
    \item \textbf{Automated Gravity Feed Mechanism:} Implement a pipe-loading flap door driven by an SG90 micro-servo ($180^\circ$ open, $90^\circ$ closed) that gently deposits produce onto the turntable center.
    \item \textbf{Calibrated Vision ROI Crop:} Isolate the fruit inside the concentric turntable ring ($X: 25\% - 76\%$, $Y: 41\% - 100\%$), cropping out background chamber walls and wiring for clean AI inference.
    \item \textbf{Robust Binary Freshness Classification:} Classify produce strictly into \texttt{HEALTHY} or \texttt{ROTTEN} categories, incorporating an automatic gas override rule for latent internal decay.
    \item \textbf{Affordable Hardware Budget:} Deliver the complete system under 25,000 BDT using commercial-off-the-shelf components sourced from Bangladesh suppliers (e.g., RoboticsBD.com).
\end{itemize}

% --- Section 3: Features ---
\section{Key System Features}
\begin{itemize}[leftmargin=*]
    \item \textbf{Inspect-and-Halt Workflow:} Follows an inspect-and-halt protocol without mechanical sorters or diverters. Produce is loaded via pipe, inspected across all modalities, and manually retrieved by the operator.
    \item \textbf{Dual Solid-State MOSFET Switching:} Two independent IRLZ44N logic-level MOSFETs switch the 12V White LED array and 365 nm UV-A LED array via 3.3V GPIO commands.
    \item \textbf{Dynamic Gas Kinetics Engine:} Continuously extracts baseline resistance $R_{\text{base}}$, minimum resistance $R_{\text{min}}$, net drop $\Delta R$, drop ratio $\eta$, and decay velocity slope $dR/dt$ using linear regression.
    \item \textbf{Internal Decay Gas Override:} If produce appears visually clean but headspace VOC drop exceeds thresholds ($\Delta R \ge 5.5\text{ k}\Omega$ or $\eta \ge 15\%$ for Tomato), the system automatically overrides vision and marks the produce \texttt{ROTTEN}.
    \item \textbf{Dual HMI Display:} Features an onboard SSD1306 OLED display for standalone operation and a real-time web dashboard broadcasting 16-frame image carousels and gas curves over WebSocket.
    \item \textbf{Live Telemetry Sync:} Automatically exports all completed scans and ground-truth labels from SQLite (\texttt{agriscan360.db}) to CSV (\texttt{bme688\_telemetry\_dataset.csv}) for ongoing machine learning model retraining.
\end{itemize}

% --- Section 4: Components ---
\section{Hardware Components Specification}
\begin{table}[H]
\centering
\small
\begin{tabularx}{\textwidth}{l p{4.5cm} X}
\toprule
\textbf{Component} & \textbf{Model / Specifications} & \textbf{Role in AgriScan 360} \\
\midrule
Raspberry Pi 5 (4GB) & Broadcom BCM2712 Quad Cortex-A76 @ 2.4GHz & Edge orchestrator, I2C master, GPIO controller, HTTP client \\
Pi Camera Module 2 & Sony IMX219 8.08MP, 1080p capture & Dual-spectrum RGB and UV-A optical imaging \\
BME688 MOX Sensor & Bosch Sensortec, I2C address 0x77 & Headspace VOC resistance, temperature, humidity, pressure \\
NEMA 17 Stepper & 17HS4401, 1.8$^\circ$ step, 40 N$\cdot$cm torque & 8-stop 360$^\circ$ turntable rotation \\
A4988 Motor Driver & Allegro Bipolar Microstepping Driver & Current-controlled drive for NEMA 17 stepper \\
SG90 Micro Servo & TowerPro 9g, 50 Hz PWM, 1.8 kg$\cdot$cm & Pipe feed chute entry door flap \\
SSD1306 OLED (0.96") & 128$\times$64 dot-matrix, I2C address 0x3C & Real-time local status and classification display \\
IRLZ44N MOSFETs (x2) & Logic-level N-Channel, $V_{GS(\text{th})} \le 2.0$V & 3.3V logic switching for 12V White and UV-A LEDs \\
365 nm UV-A LED Array & High-radiance 365 nm UV emitters & Latent fungal mycelium autofluorescence excitation \\
White LED Array & High-CRI diffused 12V LED array & Glare-free visible surface reflectance lighting \\
12V 2A DC SMPS & Regulated 12V 2A Power Adapter & Motor and LED illumination power rail \\
3.7V 18650 Battery & Li-ion cell with 5V boost circuit & Portable / backup logic supply \\
Test Chamber & 27-liter sealed dark box & Sealed atmosphere for headspace gas accumulation \\
\bottomrule
\end{tabularx}
\caption{Comprehensive Hardware Component Specifications}
\end{table}

% --- Section 5: Cost Analysis in BDT ---
\section{Cost Analysis in BDT (RoboticsBD Benchmark)}
Pricing verified against leading Bangladesh electronics suppliers, including \textbf{RoboticsBD.com} and local hardware vendors in Dhaka:

\begin{table}[H]
\centering
\begin{tabularx}{\textwidth}{l l X r r}
\toprule
\textbf{\#} & \textbf{Item Name} & \textbf{Source Reference} & \textbf{Unit Price (BDT)} & \textbf{Total (BDT)} \\
\midrule
1 & Raspberry Pi 5 (4GB RAM) & RoboticsBD / TechshopBD & 15,500 & 15,500 \\
2 & Raspberry Pi Camera Module 2 (IMX219) & RoboticsBD.com & 2,450 & 2,450 \\
3 & NEMA 17 Stepper Motor (17HS4401) & RoboticsBD.com & 1,250 & 1,250 \\
4 & A4988 Stepper Motor Driver Module & RoboticsBD.com & 140 & 140 \\
5 & TowerPro SG90 9g Micro Servo & RoboticsBD.com & 140 & 140 \\
6 & Bosch BME688 Gas Sensor Module & RoboticsBD.com & 1,850 & 1,850 \\
7 & SSD1306 0.96" I2C OLED Display & RoboticsBD.com & 320 & 320 \\
8 & 365 nm High-Power UV-A LED Array & RoboticsBD / Local Market & 450 & 450 \\
9 & High-CRI White Diffused LED Strip & Local Market & 220 & 220 \\
10 & Dual IRLZ44N MOSFET Board & Local Market & 180 & 180 \\
11 & 12V 2A DC Power Adapter (SMPS) & RoboticsBD.com & 420 & 420 \\
12 & 3.7V 18650 Battery + Holder & RoboticsBD.com & 320 & 320 \\
13 & 27L Chamber Box, Pipe, Acrylic Turntable & Local Fabrication & 1,400 & 1,400 \\
14 & Jumpers, Perfboard, Fasteners & Local Market & 350 & 350 \\
\midrule
\textbf{Total} & \multicolumn{3}{l}{\textbf{Complete Multi-Modal AgriScan 360 System}} & \textbf{24,990 BDT} \\
\bottomrule
\end{tabularx}
\caption{Itemized Bill of Materials (BOM) in Bangladeshi Taka (BDT)}
\end{table}

\noindent\textbf{Economic Viability:} Commercial single-modal fruit inspection and sorting machines (e.g., Tomra, Compac, Aweta) range from \$35,000 to \$120,000 USD (>40,00,000 BDT). AgriScan 360 delivers an automated multi-spectral optical and chemical inspection platform for \textbf{under 25,000 BDT} ($\approx \$210$ USD), representing a 99\% cost reduction.

% --- Section 6: Circuit Diagram & Pin Mapping ---
\section{Circuit Diagram \& Hardware Interconnections}

\begin{figure}[H]
\centering
\includegraphics[width=\textwidth]{circuit_diagram.png}
\caption{Complete AgriScan 360 System Circuit Schematic and Interconnect Architecture}
\label{fig:circuit_diagram}
\end{figure}

\noindent\textbf{Circuit Architecture \& Power Distribution:}
The complete electrical interconnect architecture is orchestrated by the Raspberry Pi 5 acting as edge master. To prevent electrical noise and ground bounce from inductive loads, a dual-rail power scheme is enforced:
\begin{enumerate}[leftmargin=*]
    \item \textbf{External 12V 2A SMPS Rail:} Powers the NEMA 17 stepper motor through the A4988 driver VMOT pin, decoupled with a $100\ \mu\text{F}$ 25V electrolytic capacitor. This same rail supplies the White and 365 nm UV-A LED arrays.
    \item \textbf{Logic Power \& Isolation:} The Raspberry Pi provides 3.3V logic reference to A4988 VDD and sensor pullups, and 5.0V DC to the SG90 micro-servo motor. All power returns meet at a star common ground plane.
    \item \textbf{Solid-State Switching:} High-power illumination switching is executed by dual IRLZ44N logic-level N-channel MOSFETs with $10\text{ k}\Omega$ pulldown resistors at their gates, ensuring reliable 3.3V GPIO switching without gate float.
    \item \textbf{Shared I2C Bus:} The Bosch BME688 MOX sensor (address \texttt{0x77}) and SSD1306 OLED display (address \texttt{0x3C}) communicate simultaneously over I2C1 (GPIO 2 SDA, GPIO 3 SCL) at 400 kHz.
\end{enumerate}

\newpage
\subsection{Raspberry Pi 5 Pin Mapping}
\begin{table}[H]
\centering
\small
\begin{tabularx}{\textwidth}{l l l l}
\toprule
\textbf{Component Pin} & \textbf{Raspberry Pi 5 Pin} & \textbf{Signal Type} & \textbf{Electrical Specification} \\
\midrule
A4988 STEP & GPIO 17 (Physical Pin 11) & Digital Output & 3.3V pulse ($5\text{ ms}$ width) \\
A4988 DIR & GPIO 27 (Physical Pin 13) & Digital Output & HIGH = CW, LOW = CCW \\
A4988 ENABLE & GPIO 22 (Physical Pin 15) & Digital Output & Active-LOW: LOW = Motor ON, HIGH = Motor OFF \\
A4988 VMOT / GND & 12V 2A SMPS Rail & Motor Power & 12V DC with $100\ \mu\text{F}$ capacitor \\
A4988 VDD / GND & 3.3V (Pin 1) / GND (Pin 6) & Logic Power & 3.3V logic reference \\
SG90 Servo PWM & GPIO 23 (Physical Pin 16) & Hardware PWM & 50 Hz PWM ($90^\circ$ closed, $180^\circ$ open) \\
SG90 VCC / GND & 5V Rail (Pin 2) / GND (Pin 14) & Servo Power & 5V DC supply \\
White MOSFET Gate & GPIO 18 (Physical Pin 12) & Digital Output & 3.3V logic with $10\text{ k}\Omega$ pulldown \\
UV-A MOSFET Gate & GPIO 24 (Physical Pin 18) & Digital Output & 3.3V logic with $10\text{ k}\Omega$ pulldown \\
BME688 SDA & GPIO 2 (Physical Pin 3) & I2C Data & Shared I2C bus, address 0x77 \\
BME688 SCL & GPIO 3 (Physical Pin 5) & I2C Clock & Shared I2C bus \\
SSD1306 SDA & GPIO 2 (Physical Pin 3) & I2C Data & Shared I2C bus, address 0x3C \\
SSD1306 SCL & GPIO 3 (Physical Pin 5) & I2C Clock & Shared I2C bus \\
Pi Camera v2 & CAM0 / CAM1 Port & MIPI CSI-2 & 15-pin serial camera ribbon \\
\bottomrule
\end{tabularx}
\caption{Complete Raspberry Pi 5 Hardware Interconnect Pin Mapping}
\end{table}

% --- Section 7: Working Principle & Implementation ---
\section{Working Principle \& Implementation}

\subsection{Operational Protocol (Inspect-and-Halt Workflow)}
\begin{enumerate}[leftmargin=*]
    \item \textbf{Step A --- Clean-Air Baseline Sniffing:} The empty 27L chamber is closed. The BME688 pre-heats and sniffs for 180 seconds. The first 120 seconds are discarded for thermal stabilization; the final 5 seconds establish the reference baseline resistance $R_{\text{base}}$.
    \item \textbf{Step B --- Pipe Drop \& Auto-Detection:} The operator drops produce into the top pipe. The SG90 servo opens to $180^\circ$ for 2 seconds, releasing the fruit onto the turntable, and closes to $90^\circ$. The lid is secured. The camera captures a test image with ROI cropping ($X: 25\% - 76\%$, $Y: 41\% - 100\%$) and classifies the fruit type (Tomato, Apple, or Eggplant) via HSV color space analysis.
    \item \textbf{Step C --- Simultaneous Sniffing \& 8-Stop Scan:} Continuous BME688 sniffing launches on a background thread. Simultaneously, the NEMA 17 motor steps through 8 angular positions ($45^\circ$ each). At each stop:
    \begin{itemize}
        \item White LED activates $\to$ captures RGB frame $\to$ LED turns off.
        \item UV-A LED activates $\to$ captures UV fluorescence frame $\to$ LED turns off.
        \item Turntable advances 25 steps ($45^\circ$).
    \end{itemize}
    All 16 photos finish in ~100 seconds. If incubation time remains, the system counts down the remaining seconds (skippable via Ctrl+C).
    \item \textbf{Step D --- Decision Fusion \& Result Display:} The Pi stops gas sniffing, compiles $\Delta R$, $\eta$, and decay slope $dR/dt$, and uploads all 16 frames + gas telemetry to the FastAPI server. The AI classifies the sample:
    \begin{equation}
        \text{Fused Score} = 0.40 \cdot P_1 + 0.35 \cdot P_2 + 0.25 \cdot P_3
    \end{equation}
    If $\text{Fused Score} \ge 0.40$ or $P_3 \ge 0.70$ (gas override), status is \texttt{ROTTEN}; otherwise \texttt{HEALTHY}.
    \item \textbf{Step E --- Manual Pickup (No Sorting Mechanism):} The status is shown on the OLED display and web UI. Motor coils de-energize. \textbf{The machine halts completely.} The operator manually opens the lid, removes the fruit, and sorts it based on the displayed result.
\end{enumerate}

% --- Section 8: Results & Applications ---
\section{Results \& Applications}

\subsection{Experimental Scan Records}
\begin{table}[H]
\centering
\small
\begin{tabularx}{\textwidth}{c l c r r r r l c}
\toprule
\textbf{ID} & \textbf{Produce} & \textbf{Ground Truth} & \textbf{$R_{\text{base}}$} & \textbf{$R_{\text{post}}$} & \textbf{$\Delta R$} & \textbf{Ratio $\eta$} & \textbf{AI Result} & \textbf{Confidence} \\
\midrule
08 & Tomato & \textbf{HEALTHY} & 270.66 k$\Omega$ & 267.02 k$\Omega$ & 3.64 k$\Omega$ & 2.26\% & \textbf{HEALTHY} & 88.2\% \\
11 & Tomato & \textbf{ROTTEN} & 263.15 k$\Omega$ & 212.98 k$\Omega$ & 50.17 k$\Omega$ & 19.65\% & \textbf{ROTTEN} & 94.0\% \\
13 & Tomato & \textbf{ROTTEN} & 259.66 k$\Omega$ & 251.72 k$\Omega$ & 7.94 k$\Omega$ & 4.21\% & \textbf{ROTTEN} & 78.5\% \\
14 & Tomato & \textbf{HEALTHY} & 268.38 k$\Omega$ & 262.99 k$\Omega$ & 5.39 k$\Omega$ & 4.47\% & \textbf{HEALTHY} & 87.5\% \\
\bottomrule
\end{tabularx}
\caption{Empirical Experimental Telemetry from Real Chamber Scans}
\end{table}

\subsection{Practical Applications}
\begin{itemize}[leftmargin=*]
    \item \textbf{Wholesale Market Intake:} Rapid testing of incoming crates to isolate batches with early fungal decay before distribution.
    \item \textbf{Cold Storage Screening:} Pre-entry screening to avoid storing fruits with latent fungal rot that emit ethylene and spoil adjacent produce.
    \item \textbf{Quality Control in Packhouses:} Non-destructive validation of premium export produce.
\end{itemize}

% --- Section 9: Social Impact & Future Scope ---
\section{Social Impact \& Future Scope}

\subsection{Social Impact in Bangladesh}
\begin{itemize}[leftmargin=*]
    \item \textbf{Reducing Post-Harvest Waste:} Preserves marketable volumes of high-value perishables (tomatoes, eggplants) without additional fertilizer or water use.
    \item \textbf{Empowering Smallholder Farmers:} Provides an objective, low-cost freshness evaluation to prevent unfair price discounts from middlemen.
    \item \textbf{Public Health Protection:} Identifies fungal mycotoxins (e.g., patulin from \textit{Penicillium}) before produce enters local markets.
\end{itemize}

\subsection{Future Scope}
\begin{itemize}[leftmargin=*]
    \item \textbf{Automated Diverter Arm:} Add a dual-bin servo diverter to sort items into \texttt{HEALTHY} and \texttt{REJECT} bins automatically, eliminating manual pickup.
    \item \textbf{Conveyor Integration:} Replace the turntable with an indexed roller conveyor to increase throughput from ~20 to >600 items/hour.
    \item \textbf{Vis-NIR Spectroscopy:} Integrate an AS7265x multi-spectral sensor ($410 - 940$ nm) for non-destructive sugar content ($^\circ\text{Brix}$) and internal moisture measurement.
    \item \textbf{Standalone Edge NPU:} Quantize models to INT8 to run entirely on the Raspberry Pi 5 using a Hailo-8L NPU accelerator, removing the need for an external laptop server.
\end{itemize}

% --- Section 10: Conclusion & References ---
\section{Conclusion \& References}

\subsection{Conclusion}
AgriScan 360 demonstrates that multi-modal sensing combining 360$^\circ$ optical imaging, UV-A autofluorescence, and dynamic metal-oxide headspace kinetics provides reliable, non-destructive produce freshness evaluation. Running 16-photo image capture simultaneously with continuous BME688 sniffing delivers complete inspections within ~3 minutes. With an inspect-and-halt protocol and manual retrieval, the system achieves commercial-grade evaluation at a bill-of-materials cost under 25,000 BDT, providing a practical, accessible solution for post-harvest quality assessment in developing agricultural economies.

\subsection{References}
\begin{enumerate}[leftmargin=*]
    \item Sanz, V. et al. (2018). \textit{Quality evaluation of fresh produce using electronic nose technology}. Postharvest Biology and Technology, 142, pp. 88--96.
    \item Lorente, D. et al. (2012). \textit{Recent advances and applications of hyperspectral imaging for fruit and vegetable quality assessment}. Food and Bioprocess Technology, 5(4), pp. 1121--1142.
    \item Moshou, D. et al. (2005). \textit{Plant disease detection using spectral reflectance and UV-induced fluorescence}. Biosystems Engineering, 90(4), pp. 431--440.
    \item Bosch Sensortec (2021). \textit{BME688 Low Power Gas, Pressure, Temperature \& Humidity Sensor with AI}. Data Sheet BST-BME688-DS000-01.
    \item Kader, A. A. (2002). \textit{Postharvest Technology of Horticultural Crops}. University of California Agriculture and Natural Resources, Publication 3311.
    \item Bari, M. S. (2026). \textit{AgriScan 360 Dataset: Multi-Modal Optical and E-Nose Headspace Kinetics for Produce Freshness Evaluation}. Hugging Face Dataset Repository.
\end{enumerate}

\end{document}
"""

def write_latex_file():
    with open(TEX_OUT, "w", encoding="utf-8") as f:
        f.write(LATEX_CONTENT)
    print(f"[+] Successfully wrote LaTeX report to: {TEX_OUT}")
    shutil.copyfile(TEX_OUT, os.path.join(ROOT, "AgriScan360_Final_Report.tex"))
    shutil.copyfile(TEX_OUT, os.path.join(PARENT, "AgriScan360_Final_Report.tex"))


# -----------------------------------------------------------------------------
# 2. GENERATE COMPILED REPORTLAB PDF (.pdf)
# -----------------------------------------------------------------------------

class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and print total page count."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        if self._pageNumber == 1:
            return  # Skip page number and header on cover page
        self.saveState()
        self.setFont("Helvetica-Bold", 8.5)
        self.setFillColor(colors.HexColor("#1B365D"))
        
        # Running Header
        self.drawString(54, 750, "AgriScan 360: Multi-Spectral 360\u00b0 Produce Freshness Inspection System")
        self.setFont("Helvetica", 8.5)
        self.setFillColor(colors.HexColor("#4A5568"))
        self.drawRightString(558, 750, "CSE 4326 Micro Lab")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.6)
        self.line(54, 744, 558, 744)

        # Running Footer
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 38, page_text)
        self.drawString(54, 38, "CSE 4326: Microprocessors & Microcontrollers Laboratory | UIU")
        self.line(54, 48, 558, 48)
        self.restoreState()


def build_pdf(filename=PDF_OUT):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()

    PRIMARY = colors.HexColor("#1B365D")   # Deep Navy
    DARK    = colors.HexColor("#1A202C")   # Near Black
    MUTED   = colors.HexColor("#4A5568")   # Slate
    ACCENT  = colors.HexColor("#0D6832")   # Emerald

    # Cover page styles matching Bodoni MT serif academic cover
    cover_univ = ParagraphStyle(
        "CoverUniv",
        parent=styles["Normal"],
        fontName="Times-Bold",
        fontSize=20,
        leading=24,
        textColor=DARK,
        alignment=1,
        spaceAfter=6
    )
    cover_dept = ParagraphStyle(
        "CoverDept",
        parent=styles["Normal"],
        fontName="Times-Bold",
        fontSize=18,
        leading=22,
        textColor=DARK,
        alignment=1,
        spaceAfter=15
    )
    cover_title = ParagraphStyle(
        "CoverTitle",
        parent=styles["Normal"],
        fontName="Times-Bold",
        fontSize=34,
        leading=40,
        textColor=PRIMARY,
        alignment=1,
        spaceAfter=8
    )
    cover_subtitle = ParagraphStyle(
        "CoverSubtitle",
        parent=styles["Normal"],
        fontName="Times-Roman",
        fontSize=11.5,
        leading=16,
        textColor=MUTED,
        alignment=1,
        spaceAfter=25
    )
    cover_course_code = ParagraphStyle(
        "CoverCourseCode",
        parent=styles["Normal"],
        fontName="Times-Bold",
        fontSize=16,
        leading=22,
        textColor=DARK,
        alignment=0,
        leftIndent=15,
        spaceAfter=4
    )
    cover_course_name = ParagraphStyle(
        "CoverCourseName",
        parent=styles["Normal"],
        fontName="Times-Bold",
        fontSize=16,
        leading=22,
        textColor=DARK,
        alignment=0,
        leftIndent=15,
        spaceAfter=20
    )
    sub_title_style = ParagraphStyle(
        "SubTitleStyle",
        parent=styles["Normal"],
        fontName="Times-Bold",
        fontSize=15,
        leading=20,
        textColor=DARK,
    )
    sub_text_style = ParagraphStyle(
        "SubTextStyle",
        parent=styles["Normal"],
        fontName="Times-Bold",
        fontSize=13.5,
        leading=18,
        textColor=DARK,
    )

    # Content body styles
    h1_style = ParagraphStyle(
        "Heading1_Custom",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12.5,
        leading=16,
        textColor=PRIMARY,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )
    h2_style = ParagraphStyle(
        "Heading2_Custom",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13.5,
        textColor=PRIMARY,
        spaceBefore=7,
        spaceAfter=3,
        keepWithNext=True
    )
    body_style = ParagraphStyle(
        "Body_Custom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.3,
        leading=11.8,
        textColor=DARK,
        alignment=4,
        spaceAfter=4
    )
    bullet_style = ParagraphStyle(
        "Bullet_Custom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.3,
        leading=11.6,
        textColor=DARK,
        leftIndent=12,
        spaceAfter=2.5
    )
    caption_style = ParagraphStyle(
        "Caption_Custom",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=7.8,
        leading=10.5,
        textColor=MUTED,
        alignment=1,
        spaceAfter=6
    )
    table_cell = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.6,
        leading=9.8,
        textColor=DARK
    )
    table_cell_bold = ParagraphStyle(
        "TableCellBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.6,
        leading=9.8,
        textColor=DARK
    )
    table_header = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.0,
        leading=10.5,
        textColor=colors.white
    )

    story = []

    # =========================================================================
    # PAGE 1: COVER PAGE (UIU Micro Lab Official Cover Page)
    # =========================================================================
    story.append(Spacer(1, 15))
    if os.path.exists(LOGO_PATH):
        img = Image(LOGO_PATH, width=1.55*inch, height=1.55*inch)
        img.hAlign = 'CENTER'
        story.append(img)
    story.append(Spacer(1, 16))

    story.append(Paragraph("United International University", cover_univ))
    story.append(Paragraph("Department of CSE", cover_dept))
    story.append(Spacer(1, 40))

    story.append(Paragraph("AgriScan - 360", cover_title))
    story.append(Paragraph("Automated Multi-Modal Non-Destructive Produce Quality, Internal Defect, and Freshness Inspection System", cover_subtitle))
    story.append(Spacer(1, 45))

    story.append(Paragraph("<b>Course Code:</b> CSE 4326", cover_course_code))
    story.append(Paragraph("<b>Course Name:</b> Microprocessors and Microcontrollers Laboratory", cover_course_name))
    story.append(Spacer(1, 45))

    sub_table_data = [
        [Paragraph("<b>Submitted by (Group no.):</b> 02", sub_title_style)],
        [Paragraph("<b>Name:</b> Md. Shafiul Bari", sub_text_style)],
        [Paragraph("<b>Student ID:</b> 0112330837", sub_text_style)],
    ]
    sub_table = Table(sub_table_data, colWidths=[470])
    sub_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 16),
        ('RIGHTPADDING', (0, 0), (-1, -1), 16),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 1.0, colors.HexColor("#CBD5E1")),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
    ]))
    story.append(sub_table)

    story.append(PageBreak())

    # =========================================================================
    # PAGE 2: SECTIONS 1, 2, 3
    # =========================================================================

    # 1. ABSTRACT & INTRODUCTION
    story.append(Paragraph("1. Abstract & Introduction", h1_style))
    story.append(Paragraph(
        "<b>Abstract:</b> Post-harvest agricultural loss represents a critical challenge in developing economies like Bangladesh, where 25% to 40% of fresh fruits and vegetables spoil prior to retail distribution. Existing sorting methods in regional wholesale supply chains remain either purely subjective (surface visual sorting that fails to detect internal decay, hollow heart, and latent pathogens) or destructively invasive (penetrometer punctures that damage market produce). "
        "<b>AgriScan 360</b> resolves this trade-off by engineering an automated, multi-physics, non-destructive freshness inspection ecosystem for the CSE 4326 Microcontrollers Laboratory. The device incorporates a gravity pipe feed chute actuated by an SG90 micro-servo motor (180\u00b0 open / 90\u00b0 closed) that deposits produce into a 27-liter sealed dark chamber onto an 8-stop NEMA 17 stepper motor turntable (45\u00b0 indexing). "
        "A Raspberry Pi 5 coordinates simultaneous multi-modal sensing: continuous Volatile Organic Compound (VOC) headspace sniffing via a Bosch BME688 MOX gas sensor runs concurrently with 16 synchronized optical captures (8 White-light RGB and 8 365 nm UV-A autofluorescence frames). "
        "Telemetry and dual-spectral imagery are streamed to a local host server running FastAPI and SQLite. A multi-modal decision engine fuses visual necrotic browning, fungal excitation, and dynamic gas resistance kinetics into a binary classification (<b>HEALTHY</b> vs. <b>ROTTEN</b>). Results are displayed locally on an SSD1306 OLED screen and on an interactive web dashboard. Following the diagnostic cycle, the scan terminates safely without automated sorting, allowing the operator to manually pick up the inspected item.",
        body_style
    ))
    story.append(Paragraph(
        "<b>Introduction:</b> Fruits and vegetables continue active metabolic respiration, transpiration, and volatile organic acid synthesis post-harvest. Traditional single-angle computer vision fails to detect early rot when decay occurs on the opposite side or internally near the seed cavity. Furthermore, latent fungal pathogens like <i>Botrytis cinerea</i> and <i>Penicillium expansum</i> remain visually undetectable to the human eye for days before surface mycelium appears. AgriScan 360 addresses these physical failure modes through three synchronized sensing pillars: (1) 360\u00b0 Visible RGB Reflectance across 8 circumferential angles; (2) 365 nm UV-A Autofluorescence Excitation for latent fungal colonies; and (3) Chemical Headspace E-Nose Kinetics tracking dynamic VOC emissions inside a sealed 27L enclosure.",
        body_style
    ))

    # 2. OBJECTIVES
    story.append(Paragraph("2. Project Objectives", h1_style))
    objectives = [
        "<b>Comprehensive 360\u00b0 Spatial Assessment:</b> Eliminate optical blind spots by rotating produce across 8 discrete 45\u00b0 stops using a precision stepper-driven turntable.",
        "<b>Simultaneous Optical & Chemical Acquisition:</b> Overlap dual-spectrum optical imaging (White RGB + 365 nm UV-A) with continuous chemical gas sniffing, reducing total testing time from ~5 minutes to ~3 minutes.",
        "<b>Automated Gravity Feed Mechanism:</b> Implement a pipe-loading flap door driven by an SG90 micro-servo (180\u00b0 open, 90\u00b0 closed) that deposits produce directly onto the turntable center.",
        "<b>Calibrated Vision ROI Crop:</b> Isolate the fruit inside the concentric turntable ring (X: 25%\u201376%, Y: 41%\u2013100%), cropping out background chamber walls and wiring for clean AI inference.",
        "<b>Robust Binary Freshness Classification:</b> Classify produce strictly into HEALTHY or ROTTEN categories, incorporating an automatic gas override rule for latent internal decay.",
        "<b>Affordable Hardware Budget:</b> Deliver the complete system under 25,000 BDT using commercial-off-the-shelf components sourced from Bangladesh suppliers (e.g., RoboticsBD.com)."
    ]
    for obj in objectives:
        story.append(Paragraph(f"\u2022 {obj}", bullet_style))

    # 3. FEATURES
    story.append(Paragraph("3. Key System Features", h1_style))
    features = [
        "<b>Inspect-and-Halt Workflow:</b> Operates on an inspect-and-halt protocol without mechanical sorters or diverters. Produce is loaded via pipe, inspected across all modalities, and manually retrieved by the operator.",
        "<b>Dual Solid-State MOSFET Switching:</b> Two independent IRLZ44N logic-level MOSFETs switch the 12V White LED array and 365 nm UV-A LED array via 3.3V GPIO commands.",
        "<b>Dynamic Gas Kinetics Engine:</b> Continuously extracts baseline resistance, minimum resistance, net drop, drop ratio, and decay velocity slope using linear regression.",
        "<b>Internal Decay Gas Override:</b> If produce appears visually clean but headspace VOC drop exceeds thresholds (ratio \u2265 15% or drop \u2265 5.5 k\u03a9 for Tomato), the system automatically overrides vision and marks the produce ROTTEN.",
        "<b>Dual HMI Display:</b> Features an onboard SSD1306 OLED display for standalone operation and a real-time web dashboard broadcasting 16-frame image carousels and gas curves over WebSocket.",
        "<b>Live Telemetry Sync:</b> Automatically exports all completed scans and ground-truth labels from SQLite (agriscan360.db) to CSV (bme688_telemetry_dataset.csv) for ongoing machine learning model retraining."
    ]
    for feat in features:
        story.append(Paragraph(f"\u2022 {feat}", bullet_style))

    story.append(PageBreak())

    # =========================================================================
    # PAGE 3: SECTIONS 4, 5
    # =========================================================================

    # 4. COMPONENTS
    story.append(Paragraph("4. Hardware Components Specification", h1_style))
    comp_data = [
        [Paragraph("<b>Component</b>", table_header), Paragraph("<b>Model / Specs</b>", table_header), Paragraph("<b>Role in AgriScan 360</b>", table_header)],
        [Paragraph("Raspberry Pi 5 (4GB)", table_cell_bold), Paragraph("Broadcom BCM2712 Quad Cortex-A76 @ 2.4GHz", table_cell), Paragraph("Edge orchestrator, I2C master, GPIO controller, HTTP client", table_cell)],
        [Paragraph("Pi Camera Module 2", table_cell_bold), Paragraph("Sony IMX219 8.08MP, 1080p capture", table_cell), Paragraph("Dual-spectrum RGB and UV-A optical imaging", table_cell)],
        [Paragraph("BME688 MOX Sensor", table_cell_bold), Paragraph("Bosch Sensortec, I2C address 0x77", table_cell), Paragraph("Headspace VOC resistance, temperature, humidity, pressure", table_cell)],
        [Paragraph("NEMA 17 Stepper", table_cell_bold), Paragraph("17HS4401, 1.8\u00b0 step, 40 N\u00b7cm torque", table_cell), Paragraph("8-stop 360\u00b0 turntable rotation", table_cell)],
        [Paragraph("A4988 Motor Driver", table_cell_bold), Paragraph("Allegro Bipolar Microstepping Driver", table_cell), Paragraph("Current-controlled drive for NEMA 17 stepper", table_cell)],
        [Paragraph("SG90 Micro Servo", table_cell_bold), Paragraph("TowerPro 9g, 50 Hz PWM, 1.8 kg\u00b7cm", table_cell), Paragraph("Pipe feed chute entry door flap (180\u00b0 open / 90\u00b0 closed)", table_cell)],
        [Paragraph("SSD1306 OLED (0.96\")", table_cell_bold), Paragraph("128\u00d764 dot-matrix, I2C address 0x3C", table_cell), Paragraph("Real-time local status and classification display", table_cell)],
        [Paragraph("IRLZ44N MOSFETs (x2)", table_cell_bold), Paragraph("Logic-level N-Channel, Vgs(th) \u2264 2.0V", table_cell), Paragraph("3.3V logic switching for 12V White and UV-A LEDs", table_cell)],
        [Paragraph("365 nm UV-A LED Array", table_cell_bold), Paragraph("High-radiance 365 nm UV emitters", table_cell), Paragraph("Latent fungal mycelium autofluorescence excitation", table_cell)],
        [Paragraph("White LED Array", table_cell_bold), Paragraph("High-CRI diffused 12V LED array", table_cell), Paragraph("Glare-free visible surface reflectance lighting", table_cell)],
        [Paragraph("12V 2A DC SMPS", table_cell_bold), Paragraph("Regulated 12V 2A Power Adapter", table_cell), Paragraph("Motor and LED illumination power rail", table_cell)],
        [Paragraph("3.7V 18650 Battery", table_cell_bold), Paragraph("Li-ion cell with 5V boost circuit", table_cell), Paragraph("Portable / backup logic supply", table_cell)],
        [Paragraph("Test Chamber", table_cell_bold), Paragraph("27-liter sealed dark box", table_cell), Paragraph("Sealed atmosphere for headspace gas accumulation", table_cell)]
    ]
    t_comp = Table(comp_data, colWidths=[115, 155, 234])
    t_comp.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 2.2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.2),
    ]))
    story.append(t_comp)
    story.append(Spacer(1, 6))

    # 5. COST ANALYSIS IN BDT
    story.append(Paragraph("5. Cost Analysis in BDT (RoboticsBD Benchmark)", h1_style))
    cost_data = [
        [Paragraph("<b>#</b>", table_header), Paragraph("<b>Component Name</b>", table_header), Paragraph("<b>Source Reference</b>", table_header), Paragraph("<b>Unit Price (BDT)</b>", table_header), Paragraph("<b>Total (BDT)</b>", table_header)],
        [Paragraph("1", table_cell), Paragraph("Raspberry Pi 5 (4GB RAM)", table_cell_bold), Paragraph("RoboticsBD / TechshopBD", table_cell), Paragraph("15,500", table_cell), Paragraph("15,500", table_cell_bold)],
        [Paragraph("2", table_cell), Paragraph("Pi Camera Module 2 (IMX219)", table_cell_bold), Paragraph("RoboticsBD.com", table_cell), Paragraph("2,450", table_cell), Paragraph("2,450", table_cell_bold)],
        [Paragraph("3", table_cell), Paragraph("NEMA 17 Stepper Motor (17HS4401)", table_cell_bold), Paragraph("RoboticsBD.com", table_cell), Paragraph("1,250", table_cell), Paragraph("1,250", table_cell_bold)],
        [Paragraph("4", table_cell), Paragraph("A4988 Stepper Driver Module", table_cell_bold), Paragraph("RoboticsBD.com", table_cell), Paragraph("140", table_cell), Paragraph("140", table_cell_bold)],
        [Paragraph("5", table_cell), Paragraph("TowerPro SG90 9g Micro Servo", table_cell_bold), Paragraph("RoboticsBD.com", table_cell), Paragraph("140", table_cell), Paragraph("140", table_cell_bold)],
        [Paragraph("6", table_cell), Paragraph("Bosch BME688 Gas Sensor Module", table_cell_bold), Paragraph("RoboticsBD.com", table_cell), Paragraph("1,850", table_cell), Paragraph("1,850", table_cell_bold)],
        [Paragraph("7", table_cell), Paragraph("SSD1306 0.96\" I2C OLED Display", table_cell_bold), Paragraph("RoboticsBD.com", table_cell), Paragraph("320", table_cell), Paragraph("320", table_cell_bold)],
        [Paragraph("8", table_cell), Paragraph("365 nm High-Power UV-A LED Array", table_cell_bold), Paragraph("RoboticsBD / Local Market", table_cell), Paragraph("450", table_cell), Paragraph("450", table_cell_bold)],
        [Paragraph("9", table_cell), Paragraph("High-CRI White Diffused LED Strip", table_cell_bold), Paragraph("Local Market", table_cell), Paragraph("220", table_cell), Paragraph("220", table_cell_bold)],
        [Paragraph("10", table_cell), Paragraph("Dual IRLZ44N MOSFET Board", table_cell_bold), Paragraph("Local Electronics Market", table_cell), Paragraph("180", table_cell), Paragraph("180", table_cell_bold)],
        [Paragraph("11", table_cell), Paragraph("12V 2A DC Power Adapter (SMPS)", table_cell_bold), Paragraph("RoboticsBD.com", table_cell), Paragraph("420", table_cell), Paragraph("420", table_cell_bold)],
        [Paragraph("12", table_cell), Paragraph("3.7V 18650 Battery + Holder", table_cell_bold), Paragraph("RoboticsBD.com", table_cell), Paragraph("320", table_cell), Paragraph("320", table_cell_bold)],
        [Paragraph("13", table_cell), Paragraph("27L Chamber Box, Pipe, Acrylic Turntable", table_cell_bold), Paragraph("Local Fabrication", table_cell), Paragraph("1,400", table_cell), Paragraph("1,400", table_cell_bold)],
        [Paragraph("14", table_cell), Paragraph("Jumpers, Perfboard, Fasteners", table_cell_bold), Paragraph("Local Electronics Market", table_cell), Paragraph("350", table_cell), Paragraph("350", table_cell_bold)],
        [Paragraph("<b>TOTAL</b>", table_cell_bold), Paragraph("<b>Complete AgriScan 360 System</b>", table_cell_bold), Paragraph("<b>Full Multi-Modal Platform</b>", table_cell_bold), Paragraph("\u2014", table_cell), Paragraph("<b>24,990 BDT</b>", table_cell_bold)]
    ]
    t_cost = Table(cost_data, colWidths=[42, 162, 126, 85, 89])
    t_cost.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor("#F8FAFC")]),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#E2E8F0")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0, 0), (-1, -1), 2.2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.2),
    ]))
    story.append(t_cost)
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "<b>Economic Viability:</b> Industrial single-modal fruit sorters (Tomra, Compac, Aweta) range from $35,000 to $120,000 USD (>40,00,000 BDT). AgriScan 360 delivers multi-spectral optical and chemical E-Nose diagnostics for <b>under 25,000 BDT</b> (~$210 USD)\u2014a 99% cost reduction.",
        body_style
    ))

    story.append(PageBreak())

    # =========================================================================
    # PAGE 4: SECTION 6 (CIRCUIT DIAGRAM SCHEMATIC & ARCHITECTURAL ANALYSIS)
    # =========================================================================

    story.append(Paragraph("6. Circuit Diagram & Hardware Interconnections", h1_style))

    if os.path.exists(CIRCUIT_DIAG_PATH):
        # 504 pt is max usable width (7.0 inch)
        img_circuit = Image(CIRCUIT_DIAG_PATH, width=6.9*inch, height=4.38*inch)
        img_circuit.hAlign = 'CENTER'
        story.append(img_circuit)
        story.append(Spacer(1, 3))
        story.append(Paragraph(
            "<b>Figure 1:</b> <i>AgriScan 360 Complete System Circuit Schematic & Hardware Interconnect Architecture.</i>",
            caption_style
        ))
        story.append(Spacer(1, 4))

    story.append(Paragraph(
        "<b>Circuit Architecture & Power Distribution Analysis:</b> The electrical design is orchestrated by the Raspberry Pi 5 acting as central edge master. "
        "To prevent electrical noise, voltage transients, and inductive back-EMF from motor coils interfering with digital logic, a strict dual-rail isolated power distribution topology is implemented:",
        body_style
    ))

    circuit_notes = [
        "<b>High-Power Rail (+12V SMPS):</b> A regulated 12V 2A DC SMPS provides power directly to the A4988 driver VMOT pin, decoupled by a 100 \u03bcF 25V electrolytic capacitor placed immediately across VMOT and GND to absorb motor switching transients. This 12V rail also powers the White and 365 nm UV-A LED arrays.",
        "<b>Digital Logic Rails (+3.3V / +5.0V):</b> The Raspberry Pi 5 provides a clean 3.3V reference rail for A4988 logic VDD and I2C sensor pull-ups, while Pin 2 supplies 5.0V DC to the SG90 micro-servo motor. A star common ground bus ties the 12V power ground, Pi digital ground, driver ground, and sensor returns to eliminate ground loops.",
        "<b>Solid-State Illumination Driver:</b> Dual logic-level IRLZ44N N-channel MOSFETs switch the 12V White and UV-A LED arrays via 3.3V GPIO commands (GPIO 18 and GPIO 24). Each gate includes a 10 k\u03a9 pulldown resistor to ground, ensuring LEDs remain off during Pi boot before GPIO configuration.",
        "<b>Shared I2C Bus:</b> The Bosch BME688 MOX sensor (0x77) and SSD1306 OLED (0x3C) communicate simultaneously over I2C1 (GPIO 2 SDA, GPIO 3 SCL) at 400 kHz fast-mode clock rate.",
        "<b>Stepper & Servo Actuation:</b> A4988 microstepping driver receives STEP (GPIO 17), DIR (GPIO 27), and ENABLE (GPIO 22) pulses, with RESET hardwired to SLEEP. The SG90 servo receives 50 Hz PWM on GPIO 23 to actuate the gravity feed flap door (180\u00b0 open, 90\u00b0 closed)."
    ]
    for note in circuit_notes:
        story.append(Paragraph(f"\u2022 {note}", bullet_style))

    story.append(PageBreak())

    # =========================================================================
    # PAGE 5: PIN MAPPING TABLE & SECTION 7 (WORKING PRINCIPLE)
    # =========================================================================

    story.append(Paragraph("6.1 Complete Raspberry Pi 5 Pin Mapping", h2_style))
    pin_data = [
        [Paragraph("<b>Component Pin</b>", table_header), Paragraph("<b>Target Pin on Raspberry Pi 5</b>", table_header), Paragraph("<b>Signal Type</b>", table_header), Paragraph("<b>Electrical Characteristic</b>", table_header)],
        [Paragraph("A4988 STEP", table_cell_bold), Paragraph("GPIO 17 (Physical Pin 11)", table_cell), Paragraph("Digital Output", table_cell), Paragraph("3.3V pulse (5 ms delay)", table_cell)],
        [Paragraph("A4988 DIR", table_cell_bold), Paragraph("GPIO 27 (Physical Pin 13)", table_cell), Paragraph("Digital Output", table_cell), Paragraph("HIGH = Clockwise, LOW = CCW", table_cell)],
        [Paragraph("A4988 ENABLE", table_cell_bold), Paragraph("GPIO 22 (Physical Pin 15)", table_cell), Paragraph("Digital Output", table_cell), Paragraph("Active-LOW: LOW = Motor ON, HIGH = Motor OFF", table_cell)],
        [Paragraph("A4988 VMOT / GND", table_cell_bold), Paragraph("External 12V 2A DC Supply", table_cell), Paragraph("Power Rail", table_cell), Paragraph("12V DC with 100 \u03bcF decoupling capacitor", table_cell)],
        [Paragraph("A4988 VDD / GND", table_cell_bold), Paragraph("3.3V (Pin 1) & GND (Pin 6)", table_cell), Paragraph("Logic Supply", table_cell), Paragraph("3.3V logic reference", table_cell)],
        [Paragraph("SG90 Servo PWM", table_cell_bold), Paragraph("GPIO 23 (Physical Pin 16)", table_cell), Paragraph("Hardware PWM", table_cell), Paragraph("50 Hz PWM (90\u00b0 closed, 180\u00b0 open)", table_cell)],
        [Paragraph("SG90 VCC / GND", table_cell_bold), Paragraph("5V Rail (Pin 2) & GND (Pin 14)", table_cell), Paragraph("Servo Power", table_cell), Paragraph("5.0V DC operating supply", table_cell)],
        [Paragraph("White MOSFET Gate", table_cell_bold), Paragraph("GPIO 18 (Physical Pin 12)", table_cell), Paragraph("Digital Output", table_cell), Paragraph("3.3V logic with 10 k\u03a9 pulldown", table_cell)],
        [Paragraph("UV-A MOSFET Gate", table_cell_bold), Paragraph("GPIO 24 (Physical Pin 18)", table_cell), Paragraph("Digital Output", table_cell), Paragraph("3.3V logic with 10 k\u03a9 pulldown", table_cell)],
        [Paragraph("BME688 SDA", table_cell_bold), Paragraph("GPIO 2 (Physical Pin 3)", table_cell), Paragraph("I2C Data", table_cell), Paragraph("Shared I2C bus, address 0x77", table_cell)],
        [Paragraph("BME688 SCL", table_cell_bold), Paragraph("GPIO 3 (Physical Pin 5)", table_cell), Paragraph("I2C Clock", table_cell), Paragraph("Shared I2C bus clock", table_cell)],
        [Paragraph("SSD1306 SDA", table_cell_bold), Paragraph("GPIO 2 (Physical Pin 3)", table_cell), Paragraph("I2C Data", table_cell), Paragraph("Shared I2C bus, address 0x3C", table_cell)],
        [Paragraph("SSD1306 SCL", table_cell_bold), Paragraph("GPIO 3 (Physical Pin 5)", table_cell), Paragraph("I2C Clock", table_cell), Paragraph("Shared I2C bus clock", table_cell)],
        [Paragraph("Pi Camera Module 2", table_cell_bold), Paragraph("CAM0 / CAM1 Port", table_cell), Paragraph("MIPI CSI-2", table_cell), Paragraph("15-pin high-speed serial ribbon", table_cell)]
    ]
    t_pin = Table(pin_data, colWidths=[105, 125, 84, 190])
    t_pin.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0, 0), (-1, -1), 2.2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.2),
    ]))
    story.append(t_pin)
    story.append(Spacer(1, 8))

    # 7. WORKING PRINCIPLE & IMPLEMENTATION
    story.append(Paragraph("7. Working Principle & Implementation Details", h1_style))
    story.append(Paragraph(
        "<b>Step A \u2014 Clean-Air Baseline Sniffing:</b> The empty 27L chamber is closed. The BME688 pre-heats and sniffs for 180 seconds. The first 120 seconds are discarded for thermal stabilization; the final 5 seconds establish the reference baseline resistance R_base.<br/>"
        "<b>Step B \u2014 Pipe Drop & Auto-Detection:</b> The operator drops produce into the top pipe. The SG90 servo opens to 180\u00b0 for 2 seconds, releasing the fruit onto the turntable, and closes to 90\u00b0. The lid is secured. The camera captures a test image with ROI cropping (X: 25%\u201376%, Y: 41%\u2013100%) and classifies the fruit type (Tomato, Apple, or Eggplant) via HSV color space analysis.<br/>"
        "<b>Step C \u2014 Simultaneous Sniffing & 8-Stop Scan:</b> Continuous BME688 sniffing launches on a background thread. Simultaneously, the NEMA 17 motor steps through 8 angular positions (45\u00b0 each). At each stop: (1) White LED activates \u2192 captures RGB frame \u2192 turns off; (2) UV-A LED activates \u2192 captures UV fluorescence frame \u2192 turns off; (3) Turntable advances 25 steps (45\u00b0). All 16 photos finish in ~100 seconds. If incubation time remains, the system counts down the remaining seconds (skippable via Ctrl+C).<br/>"
        "<b>Step D \u2014 Decision Fusion & Result Display:</b> The Pi stops gas sniffing, compiles net drop, drop ratio, and decay slope, and uploads all 16 frames + gas telemetry to the FastAPI server. The AI classifies the sample: Fused Score = 0.40\u00b7P1 + 0.35\u00b7P2 + 0.25\u00b7P3. If Fused Score \u2265 0.40 or P3 \u2265 0.70 (gas override), status is ROTTEN; otherwise HEALTHY.<br/>"
        "<b>Step E \u2014 Manual Pickup (No Sorting Mechanism):</b> The status is shown on the OLED display and web UI. Motor coils de-energize. <b>The machine halts completely.</b> The operator manually opens the lid, removes the fruit, and sorts it based on the displayed result.",
        body_style
    ))

    story.append(PageBreak())

    # =========================================================================
    # PAGE 6: SECTIONS 8, 9, 10
    # =========================================================================

    # 8. RESULTS & APPLICATIONS
    story.append(Paragraph("8. Experimental Results & Practical Applications", h1_style))
    res_data = [
        [Paragraph("<b>Scan ID</b>", table_header), Paragraph("<b>Produce</b>", table_header), Paragraph("<b>Ground Truth</b>", table_header), Paragraph("<b>R_base</b>", table_header), Paragraph("<b>R_post</b>", table_header), Paragraph("<b>Delta R</b>", table_header), Paragraph("<b>Ratio %</b>", table_header), Paragraph("<b>AI Result</b>", table_header), Paragraph("<b>Confidence</b>", table_header)],
        [Paragraph("08", table_cell_bold), Paragraph("Tomato", table_cell), Paragraph("HEALTHY", table_cell_bold), Paragraph("270.66 k\u03a9", table_cell), Paragraph("267.02 k\u03a9", table_cell), Paragraph("3.64 k\u03a9", table_cell), Paragraph("2.26%", table_cell), Paragraph("HEALTHY", table_cell_bold), Paragraph("88.2%", table_cell)],
        [Paragraph("11", table_cell_bold), Paragraph("Tomato", table_cell), Paragraph("ROTTEN", table_cell_bold), Paragraph("263.15 k\u03a9", table_cell), Paragraph("212.98 k\u03a9", table_cell), Paragraph("50.17 k\u03a9", table_cell), Paragraph("19.65%", table_cell), Paragraph("ROTTEN", table_cell_bold), Paragraph("94.0%", table_cell)],
        [Paragraph("13", table_cell_bold), Paragraph("Tomato", table_cell), Paragraph("ROTTEN", table_cell_bold), Paragraph("259.66 k\u03a9", table_cell), Paragraph("251.72 k\u03a9", table_cell), Paragraph("7.94 k\u03a9", table_cell), Paragraph("4.21%", table_cell), Paragraph("ROTTEN", table_cell_bold), Paragraph("78.5%", table_cell)],
        [Paragraph("14", table_cell_bold), Paragraph("Tomato", table_cell), Paragraph("HEALTHY", table_cell_bold), Paragraph("268.38 k\u03a9", table_cell), Paragraph("262.99 k\u03a9", table_cell), Paragraph("5.39 k\u03a9", table_cell), Paragraph("4.47%", table_cell), Paragraph("HEALTHY", table_cell_bold), Paragraph("87.5%", table_cell)]
    ]
    t_res = Table(res_data, colWidths=[40, 55, 65, 55, 55, 50, 45, 65, 74])
    t_res.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
    ]))
    story.append(t_res)
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "<b>Applications:</b> (1) Wholesale intake checking to isolate batches with latent fungal rot before transit; (2) Cold storage pre-entry screening to avoid storing fruits that emit ethylene and spoil adjacent produce; (3) Non-destructive quality verification of premium retail produce.",
        body_style
    ))

    # 9. SOCIAL IMPACT & FUTURE SCOPE
    story.append(Paragraph("9. Social Impact & Future Scope", h1_style))
    story.append(Paragraph(
        "<b>Social Impact in Bangladesh:</b> Reducing post-harvest waste directly preserves marketable volumes of high-value crops (tomatoes, eggplants) without requiring additional arable land or fertilizer. It also provides smallholder farmers with an objective, low-cost freshness evaluation to prevent unfair price discounts from middlemen, while protecting public health by identifying fungal mycotoxins before produce reaches consumer markets.<br/>"
        "<b>Future Scope:</b> (1) <i>Automated Diverter Arm:</i> Add a dual-bin servo diverter to sort items into HEALTHY and REJECT bins automatically, eliminating manual pickup; (2) <i>Conveyor Integration:</i> Replace the turntable with an indexed roller conveyor to increase throughput from ~20 to >600 items/hour; (3) <i>Vis-NIR Spectroscopy:</i> Integrate an AS7265x multi-spectral sensor (410\u2013940 nm) for non-destructive sugar content (\u00b0Brix) and internal moisture measurement; (4) <i>Standalone Edge NPU:</i> Quantize models to INT8 to run entirely on the Raspberry Pi 5 using a Hailo-8L NPU accelerator, removing the need for an external laptop server.",
        body_style
    ))

    # 10. CONCLUSION & REFERENCES
    story.append(Paragraph("10. Conclusion & References", h1_style))
    story.append(Paragraph(
        "<b>Conclusion:</b> AgriScan 360 demonstrates that multi-modal sensing combining 360\u00b0 optical imaging, UV-A autofluorescence, and dynamic metal-oxide headspace kinetics provides reliable, non-destructive produce freshness evaluation. Running 16-photo image capture simultaneously with continuous BME688 sniffing delivers complete inspections within ~3 minutes. With an inspect-and-halt protocol and manual retrieval, the system achieves commercial-grade evaluation at a bill-of-materials cost under 25,000 BDT, providing a practical, accessible solution for post-harvest quality assessment in developing agricultural economies.",
        body_style
    ))
    story.append(Paragraph("<b>References:</b>", h2_style))
    refs = [
        "Sanz, V. et al. (2018). <i>Quality evaluation of fresh produce using electronic nose technology</i>. Postharvest Biology and Technology, 142, pp. 88\u201396.",
        "Lorente, D. et al. (2012). <i>Recent advances and applications of hyperspectral imaging for fruit and vegetable quality assessment</i>. Food and Bioprocess Technology, 5(4), pp. 1121\u20131142.",
        "Moshou, D. et al. (2005). <i>Plant disease detection using spectral reflectance and UV-induced fluorescence</i>. Biosystems Engineering, 90(4), pp. 431\u2013440.",
        "Bosch Sensortec (2021). <i>BME688 Low Power Gas, Pressure, Temperature & Humidity Sensor with AI</i>. Data Sheet BST-BME688-DS000-01.",
        "Kader, A. A. (2002). <i>Postharvest Technology of Horticultural Crops</i>. University of California Agriculture and Natural Resources, Publication 3311.",
        "Bari, M. S. (2026). <i>AgriScan 360 Dataset: Multi-Modal Optical and E-Nose Headspace Kinetics for Produce Freshness Evaluation</i>. Hugging Face Dataset Repository."
    ]
    for r in refs:
        story.append(Paragraph(f"\u2022 {r}", bullet_style))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"[+] Successfully compiled publication-grade PDF to: {filename}")
    shutil.copyfile(filename, os.path.join(ROOT, "AgriScan360_Final_Report.pdf"))
    shutil.copyfile(filename, os.path.join(PARENT, "AgriScan360_Final_Report.pdf"))


if __name__ == "__main__":
    write_latex_file()
    build_pdf()
