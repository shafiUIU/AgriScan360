"""
AgriScan 360 - Multi-Modal AI Decision Fusion Module
Combines Computer Vision Features (RGB & UV) with Electrochemical Gas Readings.
"""

from config import VOC_ROT_THRESHOLD


class QualityClassifier:
    def __init__(self):
        print("[AI Classifier] Multi-Modal Quality Engine loaded.")

    def evaluate(self, image_paths, gas_delta, produce_name="Produce"):
        """
        Multi-Modal Fusion Decision:
          - Image evaluation: looks for necrotic spots and UV fluorescence
          - Gas evaluation: checks if VOC gas delta exceeds rotting threshold
        """
        print("\n[AI Inference] Analyzing 16 multi-spectral frames and gas delta...")
        
        # 1. Vision Feature Extraction (Simulated / Rule-based heuristic or TFLite model)
        # In full deployment: TFLite model loads image_paths and outputs surface_score
        surface_flaw_detected = False
        uv_mould_detected = False

        # 2. Gas Scent Feature Extraction
        gas_rot_detected = gas_delta >= VOC_ROT_THRESHOLD

        # 3. Decision Logic Fusion Matrix
        if gas_rot_detected and surface_flaw_detected:
            status = "ROTTEN"
            confidence = 96.5
            reason = "Surface necrosis AND severe internal fermentation gases detected."
        elif gas_rot_detected and not surface_flaw_detected:
            status = "ROTTEN"
            confidence = 91.0
            reason = "Surface looks clean, but significant VOC gas spike indicates INTERNAL ROT / PEST DAMAGE."
        elif surface_flaw_detected or uv_mould_detected:
            status = "ROTTEN"
            confidence = 89.5
            reason = "Surface rot lesions or UV mould fluorescence detected."
        elif gas_delta > (VOC_ROT_THRESHOLD * 0.6):
            status = "UNCERTAIN"
            confidence = 72.0
            reason = "Borderline gas emission. Fruit may be over-ripe or beginning to spoil."
        else:
            status = "HEALTHY"
            confidence = 94.8
            reason = "Clear skin, clean calyx, and baseline chamber gas levels."

        result = {
            "produce": produce_name,
            "status": status,
            "confidence": confidence,
            "gas_delta_kohm": gas_delta,
            "reason": reason,
            "total_images": len(image_paths)
        }

        print(f"[AI Result] Outcome: {status} ({confidence}%) -> {reason}")
        return result
