"""
generate_docx_proposal.py -- Generates a Publication-Grade Word Document (.docx)
for the AgriScan 360 Final Year Design Project (FYDP) / Capstone Proposal.
"""

import os
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

def set_cell_background(cell, hex_color):
    """Sets background color of a table cell."""
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    tc_pr.append(shd)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """Sets cell padding."""
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'<w:top w:w="{top}" w:type="dxa"/>'
        f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'<w:left w:w="{left}" w:type="dxa"/>'
        f'<w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    tc_pr.append(tc_mar)

def create_proposal_docx(output_path):
    doc = Document()

    # Set Margins
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    # Palette
    NAVY = RGBColor(27, 54, 93)      # #1B365D
    SLATE = RGBColor(43, 76, 126)    # #2B4C7E
    TEAL = RGBColor(0, 102, 102)     # #006666
    DARK = RGBColor(34, 34, 34)      # #222222
    MUTED = RGBColor(100, 100, 100)  # #666666

    # Header / Footer
    header = doc.sections[0].header
    hp = header.paragraphs[0]
    hp.text = "AgriScan 360 -- Capstone Project Proposal | Department of CSE, UIU"
    hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    hp.style.font.size = Pt(8.5)
    hp.style.font.color.rgb = MUTED

    footer = doc.sections[0].footer
    fp = footer.paragraphs[0]
    fp.text = "Final Year Design Project (FYDP) -- Confidential & Academic Use Only"
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fp.style.font.size = Pt(8.5)
    fp.style.font.color.rgb = MUTED

    # -------------------------------------------------------------------------
    # Cover / Header Title Block
    # -------------------------------------------------------------------------
    p_inst = doc.add_paragraph()
    p_inst.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_inst = p_inst.add_run("UNITED INTERNATIONAL UNIVERSITY\nDEPARTMENT OF COMPUTER SCIENCE AND ENGINEERING")
    run_inst.font.name = "Arial"
    run_inst.font.size = Pt(13)
    run_inst.font.bold = True
    run_inst.font.color.rgb = SLATE

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_sub = p_sub.add_run("FINAL YEAR DESIGN PROJECT (FYDP) / CAPSTONE PROPOSAL")
    r_sub.font.name = "Arial"
    r_sub.font.size = Pt(11)
    r_sub.font.bold = True
    r_sub.font.color.rgb = TEAL

    # Horizontal Divider
    p_div = doc.add_paragraph()
    p_div.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_div = p_div.add_run("―" * 55)
    r_div.font.color.rgb = SLATE

    # Main Project Title
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_title = p_title.add_run("AgriScan 360:\nAn Automated Multi-Modal Non-Destructive Quality, Internal Defect, and Freshness Inspection System for Agricultural Produce Integrating 360° Cross-Polarized Vision, UV-A Autofluorescence, Vis-NIR Spectroscopy, Acoustic Resonance, Thermal Respiration, and E-Nose Headspace Kinetics")
    r_title.font.name = "Arial"
    r_title.font.size = Pt(16)
    r_title.font.bold = True
    r_title.font.color.rgb = NAVY

    doc.add_paragraph()

    # Meta Table
    tbl_meta = doc.add_table(rows=5, cols=2)
    tbl_meta.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl_meta.autofit = False
    col_widths = [Inches(2.5), Inches(4.0)]

    meta_data = [
        ("Lead Researcher / Student:", "Md. Shafiul Bari"),
        ("Academic Program:", "B.Sc. in Computer Science and Engineering (CSE)"),
        ("Target Agricultural Commodities:", "Apple (Malus domestica), Tomato (Solanum lycopersicum), Eggplant (Solanum melongena)"),
        ("Project Classification:", "Embedded Systems, Edge AI, Multi-Modal Sensor Fusion, Agricultural Robotics"),
        ("Dataset Repository:", "https://huggingface.co/datasets/SHAFI6196UIU/agriscan360-dataset"),
    ]

    for idx, (label, val) in enumerate(meta_data):
        row = tbl_meta.rows[idx]
        c0, c1 = row.cells[0], row.cells[1]
        c0.width, c1.width = col_widths[0], col_widths[1]

        p0 = c0.paragraphs[0]
        r0 = p0.add_run(label)
        r0.font.bold = True
        r0.font.size = Pt(9.5)
        r0.font.color.rgb = NAVY

        p1 = c1.paragraphs[0]
        r1 = p1.add_run(val)
        r1.font.size = Pt(9.5)
        r1.font.color.rgb = DARK

        set_cell_background(c0, "F0F4F8")
        set_cell_background(c1, "FFFFFF")
        set_cell_margins(c0, top=60, bottom=60, left=100, right=100)
        set_cell_margins(c1, top=60, bottom=60, left=100, right=100)

    doc.add_paragraph()

    # -------------------------------------------------------------------------
    # Helper: Add Section Headings
    # -------------------------------------------------------------------------
    def add_h1(text):
        h = doc.add_paragraph()
        h.paragraph_format.space_before = Pt(16)
        h.paragraph_format.space_after = Pt(6)
        h.paragraph_format.keep_with_next = True
        r = h.add_run(text)
        r.font.name = "Arial"
        r.font.size = Pt(13)
        r.font.bold = True
        r.font.color.rgb = NAVY
        return h

    def add_h2(text):
        h = doc.add_paragraph()
        h.paragraph_format.space_before = Pt(12)
        h.paragraph_format.space_after = Pt(4)
        h.paragraph_format.keep_with_next = True
        r = h.add_run(text)
        r.font.name = "Arial"
        r.font.size = Pt(11)
        r.font.bold = True
        r.font.color.rgb = SLATE
        return h

    def add_body(text, bold_prefix=None, space_after=6):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(space_after)
        p.paragraph_format.line_spacing = 1.15
        if bold_prefix:
            rb = p.add_run(bold_prefix)
            rb.font.bold = True
            rb.font.size = Pt(10)
            rb.font.color.rgb = DARK
        r = p.add_run(text)
        r.font.size = Pt(10)
        r.font.color.rgb = DARK
        return p

    def add_callout(text, title=None):
        tbl = doc.add_table(rows=1, cols=1)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = tbl.cell(0, 0)
        cell.width = Inches(6.5)
        set_cell_background(cell, "F4F6F9")
        set_cell_margins(cell, top=100, bottom=100, left=150, right=150)
        p = cell.paragraphs[0]
        p.paragraph_format.line_spacing = 1.15
        if title:
            rt = p.add_run(f"★ {title}\n")
            rt.font.bold = True
            rt.font.size = Pt(10)
            rt.font.color.rgb = TEAL
        r = p.add_run(text)
        r.font.size = Pt(9.5)
        r.font.italic = True
        r.font.color.rgb = DARK
        doc.add_paragraph()

    # -------------------------------------------------------------------------
    # Section 1: Executive Summary & Abstract
    # -------------------------------------------------------------------------
    add_h1("1. Executive Summary & Abstract")
    add_body(
        "Post-harvest food loss represents a catastrophic economic and food-security crisis across South Asia. "
        "In Bangladesh, between 25% and 40% of fresh fruits and vegetables perish prior to reaching consumers due to invisible "
        "internal rot, sub-surface bruising, and latent fungal microbial infections. Existing commercial sorting relies either "
        "on subjective manual sorting—which is completely blind to internal defects—or on destructive penetrometer puncture tests "
        "that destroy good produce while inspecting less than 1% of a harvest batch."
    )
    add_body(
        "AgriScan 360 is an intelligent, multi-modal, non-destructive agricultural inspection platform that automates 360° holistic "
        "produce grading inside an enclosed 27-liter controlled testing chamber. A NEMA 17 stepper motor turntable indexes produce "
        "across 8 discrete 45° angular positions while simultaneously capturing synchronized optical, chemical, acoustic, and thermal data. "
        "By fusing six complementary non-destructive physical phenomena—Cross-Polarized RGB Vision, 365nm UV-A Autofluorescence, "
        "Visible-Near Infrared (Vis-NIR) Spectroscopy, Acoustic Resonance Elasticity, Long-Wave Infrared (LWIR) Thermography, and "
        "BME688 MOX Electronic-Nose gas kinetics—the system eliminates destructive testing and provides accurate 4-tier freshness "
        "classification, sugar estimation (°Brix), firmness indexing, and Remaining Shelf-Life (RSL in days) prediction."
    )

    # -------------------------------------------------------------------------
    # Section 2: Problem Statement & Industrial Motivation
    # -------------------------------------------------------------------------
    add_h1("2. Problem Statement & Industrial Motivation")
    add_body(
        "Agricultural supply chains in developing nations suffer massive post-harvest loss due to two fundamental technological shortcomings:\n"
        "1. Surface Blindness of Standard Computer Vision: Standard RGB cameras capture only visible surface color and 2D geometry. "
        "They cannot detect internal core breakdown, mealiness, internal hollow heart, watercore, or microbial fungal spore colonies that have "
        "not yet breached the outer epidermis.\n"
        "2. Economic Waste of Destructive Penetrometry: Quality assurance currently requires manually puncturing or slicing open fruit. "
        "This destroys marketable produce, causes cross-contamination, and provides zero guarantee for the remaining uninspected 99% of the batch.\n"
        "There is an acute industrial demand for a cost-effective (<$300), automated, multi-physics inspection terminal that can non-destructively "
        "evaluate both internal biochemical health and external cosmetic standards."
    )

    # -------------------------------------------------------------------------
    # Section 3: The 6 Non-Destructive Sensing Modalities
    # -------------------------------------------------------------------------
    add_h1("3. Comprehensive Multi-Modal Sensing Modalities & Physical Mechanisms")
    add_body(
        "To achieve clinical diagnostic precision, AgriScan 360 deploys six non-destructive sensing modalities designed around specific biological phenomena:"
    )

    add_h2("Modality 1: Cross-Polarized Visible Surface Vision")
    add_body(
        "Standard reflective imaging suffers from intense specular glare caused by natural fruit surface cuticular waxes, obscuring shallow bruises. "
        "AgriScan 360 utilizes linear polarization sheets over the high-CRI White LEDs and a cross-polarized optical filter oriented at 90° on the "
        "Pi Camera lens. This extinguishes specular reflections and isolates diffuse subsurface backscatter, revealing deep dermal impact bruises, "
        "sub-epidermal necrosis, and micro-cracking.",
        bold_prefix="Physical Principle: "
    )

    add_h2("Modality 2: 365 nm UV-A Fungal & Metabolic Autofluorescence")
    add_body(
        "Decay fungi such as Penicillium expansum and Botrytis cinerea produce characteristic metabolic fluorophores (pteridines and flavins) "
        "that absorb 365nm UV radiation and autofluoresce brightly in the 450nm-550nm green/yellow spectrum. Furthermore, senescent and "
        "bruised cell walls rupture and leak chlorophyll catabolites that exhibit distinctive red autofluorescence (670nm-720nm). "
        "Analyzing fluorescence pixel ratios across 8 rotation angles enables early fungal identification up to 4 days before visible mycelium emerges.",
        bold_prefix="Physical Principle: "
    )

    add_h2("Modality 3: Visible-to-Near-Infrared (Vis-NIR) Spectroscopy (410 nm - 940 nm)")
    add_body(
        "Photons in the near-infrared spectrum penetrate 10mm-15mm into fruit flesh before diffuse back-scattering. AgriScan 360 integrates an "
        "18-channel Vis-NIR multi-spectral sensor cluster (AS7265x). Optical absorption at 970nm corresponds to the second O-H vibrational overtone "
        "of water, directly quantifying dehydration and turgor pressure. Absorption peaks at 880nm-910nm correlate with C-H vibrational overtones "
        "of sucrose, fructose, and glucose, enabling non-destructive estimation of Total Soluble Solids (°Brix) without juice extraction.",
        bold_prefix="Physical Principle: "
    )

    add_h2("Modality 4: Acoustic Resonance & Non-Destructive Elasticity (Firmness)")
    add_body(
        "A low-mass micro-solenoid softly taps the fruit with a 10ms impulse, exciting natural acoustic standing waves. A high-bandwidth digital "
        "MEMS acoustic pickup records the vibration ringing. Fast Fourier Transform (FFT) analysis extracts the fundamental spherical resonant "
        "frequency (fn). The Elasticity Index (EI = fn^2 * m^(2/3)) is computed in real time. This directly detects internal softening, mealiness, "
        "and internal hollow heart without destructive penetrometer punctures.",
        bold_prefix="Physical Principle: "
    )

    add_h2("Modality 5: Long-Wave Infrared (LWIR) Radiometric Thermography")
    add_body(
        "Active bacterial decomposition and fungal proliferation generate measurable localized metabolic heat spikes (Delta-T approx +0.4°C to +1.5°C). "
        "Conversely, damaged dermal tissue with ruptured stomata exhibits rapid evaporative cooling. A 32x24 pixel radiometric thermal sensor "
        "(MLX90640) maps localized surface thermal gradients, revealing subsurface microbial colonies and physiological disorders.",
        bold_prefix="Physical Principle: "
    )

    add_h2("Modality 6: Chemical Headspace Electronic Nose (E-Nose) & Ethylene Kinetics")
    add_body(
        "During ripening and decay, fruit synthesizes volatile organic compounds (VOCs—ethanol, ethyl acetate, acetaldehyde) and the climacteric "
        "ripening hormone ethylene (C2H4). Inside the sealed 27L chamber during the 300-second pre-scan incubation, VOCs accumulate in the headspace. "
        "A Bosch BME688 MOX gas sensor combined with a dedicated electrochemical ethylene sensor extracts dynamic decay kinetics: baseline resistance "
        "(R_base), relative drop ratio (eta = Delta-R / R_base * 100%), and decay velocity (dR/dt in kOhm/s). This immediately flags internal core rot "
        "even when the fruit exterior appears cosmetically flawless.",
        bold_prefix="Physical Principle: "
    )

    # Comparison Table
    add_h2("Sensing Modalities Comparison Table")
    tbl_sens = doc.add_table(rows=7, cols=4)
    tbl_sens.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl_sens.autofit = False
    s_widths = [Inches(1.8), Inches(1.5), Inches(1.8), Inches(1.4)]

    s_headers = ["Sensing Modality", "Primary Sensor / Component", "Biological Phenomenon Targeted", "Status in Project"]
    for i, h in enumerate(s_headers):
        cell = tbl_sens.rows[0].cells[i]
        cell.width = s_widths[i]
        set_cell_background(cell, "1B365D")
        p = cell.paragraphs[0]
        r = p.add_run(h)
        r.font.bold = True
        r.font.size = Pt(9)
        r.font.color.rgb = RGBColor(255, 255, 255)
        set_cell_margins(cell, top=80, bottom=80, left=80, right=80)

    s_data = [
        ("Cross-Polarized RGB", "Pi Camera v2 + Polarizer Film", "Sub-surface bruising, skin lesions, calyx rot", "Working / Functional"),
        ("365nm UV Autofluorescence", "High-Power 365nm UV LED Array", "Penicillium & Botrytis mould, aflatoxins", "Working / Functional"),
        ("Vis-NIR Spectroscopy", "AS7265x 18-Band Sensor Cluster", "Sugar content (°Brix), internal water content", "Planned / Hardware Ready"),
        ("Acoustic Resonance", "Solenoid Tapper + INMP441 MEMS", "Flesh firmness (EI), mealiness, hollow heart", "Planned / Hardware Ready"),
        ("LWIR Thermography", "MLX90640 32x24 IR Thermal Array", "Microbial respiration heat, transpiration defects", "Planned / Hardware Ready"),
        ("Headspace E-Nose", "Bosch BME688 MOX + C2H4 Sensor", "Headspace VOCs, ethanol, ethylene gas kinetics", "Working / Functional"),
    ]

    for row_idx, data_tuple in enumerate(s_data, start=1):
        row = tbl_sens.rows[row_idx]
        bg = "FFFFFF" if row_idx % 2 == 1 else "F8FAFC"
        for col_idx, text in enumerate(data_tuple):
            cell = row.cells[col_idx]
            cell.width = s_widths[col_idx]
            set_cell_background(cell, bg)
            set_cell_margins(cell, top=60, bottom=60, left=80, right=80)
            p = cell.paragraphs[0]
            r = p.add_run(text)
            r.font.size = Pt(8.5)
            r.font.color.rgb = DARK
            if col_idx == 3:
                r.font.bold = True
                r.font.color.rgb = TEAL if "Working" in text else SLATE

    doc.add_paragraph()

    # -------------------------------------------------------------------------
    # Section 4: Multi-Modal AI Decision Fusion
    # -------------------------------------------------------------------------
    add_h1("4. Multi-Modal AI Decision Fusion Engine")
    add_body(
        "AgriScan 360 eliminates the vulnerability of single-sensor false alarms through a Hierarchical Fusion Decision Engine. "
        "The overall produce health score (F_unified in [0, 100]) is calculated through a gated multi-pillar formulation:"
    )
    add_callout(
        "F_unified = w1 * S_RGB + w2 * S_UV + w3 * S_NIR + w4 * S_Acoustic + w5 * S_Thermal + w6 * S_Gas\n\n"
        "Default Empirical Weighting:\n"
        "w1 = 0.25 (Visible Surface Vision)      w2 = 0.20 (UV Autofluorescence)\n"
        "w3 = 0.15 (Vis-NIR Sugar/Moisture)      w4 = 0.15 (Acoustic Resonance Firmness)\n"
        "w5 = 0.10 (LWIR Thermal Respiration)   w6 = 0.15 (E-Nose VOC & Ethylene)",
        title="Multi-Modal Bayesian Decision Function"
    )
    add_body(
        "Automated Safety Gating Rule: If the chemical VOC emission rate (dR/dt) or acoustic elasticity index (EI) exhibits catastrophic failure "
        "beyond safety thresholds, the system executes an automated override, immediately downgrading visually 'clean' fruit to MID_ROTTEN or ROTTEN. "
        "This guarantees that internal core rot—invisible to normal cameras—is never falsely graded as healthy."
    )

    # -------------------------------------------------------------------------
    # Section 5: Current Implementation Status
    # -------------------------------------------------------------------------
    add_h1("5. Current Working Implementation Status")
    add_body(
        "The AgriScan 360 project is not a theoretical concept; a fully operational embedded prototype has already been built and tested:\n"
        "• Operational 27L Testbed: Fully light-sealed chamber with a NEMA 17 stepper turntable (A4988 driver, 200 steps/rev, 25 steps per 45° stop).\n"
        "• Solid-State Dual Lighting: High-CRI White and 365nm UV-A LED arrays driven by dual IRLZ44N logic-level MOSFETs on GPIO 18 & 24.\n"
        "• Live Gas Headspace Telemetry: Bosch BME688 I2C sensor sniffing continuous VOC resistance with 300s incubation and raw time-series CSV exports.\n"
        "• Complete Deep Learning Pipeline: PyTorch image classification engine supporting EfficientNet-B0/B2, ConvNeXt-Tiny, and ResNet50, "
        "integrated with our curated Hugging Face dataset (SHAFI6196UIU/agriscan360-dataset) and ONNX export tools.\n"
        "• Edge-to-Server Orchestration: Dual-node distributed architecture running master orchestration on the Pi 5 and real-time inference on the laptop RTX 4060 GPU."
    )

    # -------------------------------------------------------------------------
    # Section 6: Future Possibilities & Scope of Expansion
    # -------------------------------------------------------------------------
    add_h1("6. Comprehensive Future Scope & Research Expansion")
    add_body(
        "The modular architecture of AgriScan 360 allows seamless expansion into advanced academic research tracks:\n"
        "1. Remaining Shelf-Life (RSL) Forecasting: Training a Temporal Convolutional Network (TCN) or LSTM on longitudinal 14-day VOC decay curves "
        "and NIR moisture absorption to predict the exact number of days remaining before spoilage.\n"
        "2. On-Device Edge NPU Acceleration: Quantizing models to INT8 and executing directly on the Raspberry Pi 5 via a Hailo-8L M.2 AI acceleration "
        "module (13 TOPS) or Google Coral Edge TPU, creating a 100% self-contained appliance that requires no laptop or cloud.\n"
        "3. Automated Sorting Gantry: Designing a 3-axis Cartesian pick-and-place gantry with a soft pneumatic vacuum suction cup that automatically routes "
        "inspected fruit into Grade A (Premium Export), Grade B (Local Retail), Grade C (Immediate Processing/Juice), and Reject (Compost) bins.\n"
        "4. Farm-to-Fork Blockchain Certification: Generating cryptographic QR code quality certificates for agricultural crates, certifying "
        "non-destructive sugar (°Brix), firmness, and zero internal decay for export compliance."
    )

    # -------------------------------------------------------------------------
    # Section 7: Hardware Budget & Financial Feasibility
    # -------------------------------------------------------------------------
    add_h1("7. Bill of Materials (BOM) & Financial Feasibility")
    add_body(
        "Commercial optical-electronic sorting machines (e.g., Tomra, Aweta, Compac) cost between $35,000 and $120,000 USD, making them unreachable "
        "for regional agro-markets. AgriScan 360 delivers unprecedented multi-modal precision at less than 1% of the cost:"
    )

    tbl_bom = doc.add_table(rows=12, cols=4)
    tbl_bom.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl_bom.autofit = False
    b_widths = [Inches(3.0), Inches(1.2), Inches(1.2), Inches(1.1)]

    b_headers = ["Component / Module Description", "Cost (BDT)", "Cost (USD)", "Project Stage"]
    for i, h in enumerate(b_headers):
        cell = tbl_bom.rows[0].cells[i]
        cell.width = b_widths[i]
        set_cell_background(cell, "1B365D")
        p = cell.paragraphs[0]
        r = p.add_run(h)
        r.font.bold = True
        r.font.size = Pt(9)
        r.font.color.rgb = RGBColor(255, 255, 255)
        set_cell_margins(cell, top=80, bottom=80, left=80, right=80)

    b_data = [
        ("Raspberry Pi 5 (8GB RAM Model)", "9,800 BDT", "$82.00", "Implemented"),
        ("Raspberry Pi Camera Module 2 (8MP IMX219)", "2,200 BDT", "$18.50", "Implemented"),
        ("Linear Polarization Optical Filters (Cross-Polarization)", "450 BDT", "$3.80", "Phase 2"),
        ("Bosch BME688 MOX Digital Gas & VOC Sensor", "1,800 BDT", "$15.00", "Implemented"),
        ("AS7265x 18-Channel Vis-NIR Spectroscopy Sensor", "4,200 BDT", "$35.00", "Phase 2"),
        ("MLX90640 32x24 Radiometric Thermal Array", "4,800 BDT", "$40.00", "Phase 2"),
        ("INMP441 MEMS Microphone + Micro-Solenoid Tapper", "650 BDT", "$5.50", "Phase 2"),
        ("NEMA 17 Stepper Motor + A4988 Driver Module", "1,380 BDT", "$11.50", "Implemented"),
        ("Dual IRLZ44N MOSFET Driver Board & LED Arrays", "1,090 BDT", "$9.10", "Implemented"),
        ("27L Airtight Enclosure, Turntable, 12V PSU, OLED Display", "4,460 BDT", "$37.60", "Implemented"),
        ("COMPLETE 6-PILLAR SYSTEM TOTAL", "~30,830 BDT", "~$258.00", "Full Platform"),
    ]

    for row_idx, data_tuple in enumerate(b_data, start=1):
        row = tbl_bom.rows[row_idx]
        is_total = (row_idx == len(b_data))
        bg = "E2E8F0" if is_total else ("FFFFFF" if row_idx % 2 == 1 else "F8FAFC")
        for col_idx, text in enumerate(data_tuple):
            cell = row.cells[col_idx]
            cell.width = b_widths[col_idx]
            set_cell_background(cell, bg)
            set_cell_margins(cell, top=60, bottom=60, left=80, right=80)
            p = cell.paragraphs[0]
            r = p.add_run(text)
            r.font.size = Pt(8.5)
            r.font.color.rgb = NAVY if is_total else DARK
            if is_total or col_idx == 0:
                r.font.bold = True

    doc.add_paragraph()

    # -------------------------------------------------------------------------
    # Section 8: Timeline & Milestones
    # -------------------------------------------------------------------------
    add_h1("8. Project Milestones & Timeline")
    add_body(
        "• Milestone 1 (Weeks 1-3): Testbed stabilization, mechanical turntable alignment, BME688 clean-air baseline calibration.\n"
        "• Milestone 2 (Weeks 4-6): Longitudinal multi-modal dataset collection across decay stages, uploading to Hugging Face.\n"
        "• Milestone 3 (Weeks 7-9): Multi-architecture deep learning model benchmarking (EfficientNet-B2, ConvNeXt-Tiny, ResNet50).\n"
        "• Milestone 4 (Weeks 10-12): Vis-NIR, Acoustic, and Thermal sensor expansion & multi-modal Bayesian decision fusion formulation.\n"
        "• Milestone 5 (Weeks 13-14): System end-to-end integration, 3D web inspection dashboard, and automated RSL regression.\n"
        "• Milestone 6 (Weeks 15-16): Validation trials against destructive penetrometers/refractometers, final thesis documentation, and defense."
    )

    # -------------------------------------------------------------------------
    # Section 9: Academic Merits & Supervisory Sign-Off
    # -------------------------------------------------------------------------
    add_h1("9. Academic Contributions & Supervisory Sign-Off")
    add_body(
        "AgriScan 360 directly addresses UN Sustainable Development Goals (SDG 2: Zero Hunger and SDG 12: Responsible Consumption). "
        "The project will yield: (1) An open-source, synchronized multi-modal agricultural dataset; (2) A working demonstration prototype; "
        "and (3) A manuscript for submission to an IEEE or Springer peer-reviewed journal in smart agriculture (e.g., Computers and Electronics in Agriculture)."
    )

    doc.add_paragraph()
    doc.add_paragraph()

    # Sign-Off Table
    tbl_sign = doc.add_table(rows=2, cols=2)
    tbl_sign.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl_sign.autofit = False
    s_col_widths = [Inches(3.25), Inches(3.25)]

    c00 = tbl_sign.rows[0].cells[0]
    c01 = tbl_sign.rows[0].cells[1]
    c10 = tbl_sign.rows[1].cells[0]
    c11 = tbl_sign.rows[1].cells[1]

    c00.width, c01.width, c10.width, c11.width = s_col_widths[0], s_col_widths[1], s_col_widths[0], s_col_widths[1]

    p_s1 = c00.paragraphs[0]
    r_s1 = p_s1.add_run("Submitted by:\n\n\n__________________________________\nMd. Shafiul Bari\nStudent, Dept. of CSE\nUnited International University (UIU)")
    r_s1.font.size = Pt(9.5)

    p_s2 = c01.paragraphs[0]
    r_s2 = p_s2.add_run("Approved by Supervisor:\n\n\n__________________________________\n[Supervisor's Name & Title]\nDepartment of CSE\nUnited International University (UIU)")
    r_s2.font.size = Pt(9.5)

    doc.save(output_path)
    print(f"Generated publication-grade proposal DOCX: {output_path}")

if __name__ == "__main__":
    out_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "AgriScan360_FYDP_Proposal.docx")
    create_proposal_docx(out_file)
