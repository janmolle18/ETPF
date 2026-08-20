import logging
import time
import os
import numpy as np
from PIL import Image, ImageOps, ImageEnhance, ImageFilter
import easyocr

logger = logging.getLogger(__name__)

def _is_valid_healing_candidate(orig_text: str, candidate_text: str, orig_conf: float, candidate_conf: float) -> bool:
    """
    Validates sub-crop OCR results to ensure self-healing never corrupts valid words or introduces hallucinations.
    """
    import re
    if not candidate_text:
        return False

    # Require a minimum confidence gain of +10%
    if candidate_conf < orig_conf + 0.10:
        return False

    # Calculate character similarity between candidate and original text
    from difflib import SequenceMatcher
    sim = SequenceMatcher(None, orig_text.lower(), candidate_text.lower()).ratio()

    # Rule 1: Preserve numeric & decimal structure
    # If orig_text has a decimal point (e.g. s0.00, 5.40), candidate MUST contain a decimal point
    if ("." in orig_text or "," in orig_text) and re.search(r'\d+[\.,]\d{2}', orig_text):
        if "." not in candidate_text and "," not in candidate_text:
            return False

    # Rule 2: Minimum similarity check even for low confidence
    # Candidates should not replace numbers/words with completely unrelated text (e.g. s0.00 -> 8000 or PRIMECORP -> PRIHECORP)
    if sim < 0.40 and orig_conf >= 0.25:
        return False

    # Rule 3: If original text had medium confidence (>= 0.50), candidate must retain structural similarity (>= 0.75)
    if orig_conf >= 0.50 and sim < 0.75:
        return False

    # Rule 4: Candidate text length should not explode or shrink drastically
    if len(candidate_text) > len(orig_text) * 1.5 or len(candidate_text) < len(orig_text) * 0.5:
        if orig_conf >= 0.45:
            return False

    return True


def optimize_low_confidence_blocks(
    image_path: str,
    layout_blocks: list[dict],
    reader: easyocr.Reader
) -> tuple[list[dict], dict]:
    """
    Identifies low confidence layout blocks (< 70% confidence), crops their sub-image region,
    applies three reverse-degradation filters sequentially, and runs sub-crop OCR to heal text.
    """
    start_time = time.time()
    
    # Return early if PDF or file doesn't exist
    if not image_path or image_path.lower().endswith('.pdf') or not os.path.exists(image_path):
        return layout_blocks, {
            "low_conf_original": 0,
            "healed_count": 0,
            "avg_confidence_gain": 0.0,
            "healing_time_ms": 0.0
        }
        
    try:
        with Image.open(image_path) as opened_img:
            img = opened_img.convert("RGB")
        img_w, img_h = img.size
    except Exception as e:
        logger.warning("Failed to open image for healing: %s", e)
        return layout_blocks, {
            "low_conf_original": 0,
            "healed_count": 0,
            "avg_confidence_gain": 0.0,
            "healing_time_ms": 0.0
        }

    # Find blocks with confidence < 70%
    low_conf_blocks = [b for b in layout_blocks if b["confidence"] < 0.70]
    low_conf_original = len(low_conf_blocks)
    healed_count = 0
    total_gain = 0.0
    
    # Restrict to maximum of 5 blocks to guarantee fast processing
    target_blocks = low_conf_blocks[:5]
    
    for block in target_blocks:
        orig_text = block["text"]
        orig_conf = block["confidence"]
        
        # Calculate pixel coordinates from relative percentages with an 8px safety margin
        margin = 8
        xmin = max(0, int((block["x"] / 100.0) * img_w) - margin)
        ymin = max(0, int((block["y"] / 100.0) * img_h) - margin)
        xmax = min(img_w, int(((block["x"] + block["width"]) / 100.0) * img_w) + margin)
        ymax = min(img_h, int(((block["y"] + block["height"]) / 100.0) * img_h) + margin)
        
        # Skip invalid crops
        if xmax <= xmin or ymax <= ymin:
            continue
            
        crop_img = img.crop((xmin, ymin, xmax, ymax))
        
        # Try 3 reverse degradation tactics
        best_tactic_text = orig_text
        best_tactic_conf = orig_conf
        
        # Tactic 1: Contrast stretching + High sharpening (combats blur/shadows)
        tactic_1 = ImageEnhance.Contrast(crop_img).enhance(2.5)
        tactic_1 = ImageEnhance.Sharpness(tactic_1).enhance(2.0)
        tactic_1 = tactic_1.filter(ImageFilter.SHARPEN)
        tactic_1 = tactic_1.convert("RGB")
        
        # Tactic 2: 2x Interpolated zoom + Grayscale contrast enhancement (combats small characters/noise without hard binarization)
        w, h = crop_img.size
        tactic_2 = crop_img.resize((w * 2, h * 2), Image.Resampling.LANCZOS)
        tactic_2 = ImageOps.grayscale(tactic_2)
        tactic_2 = ImageEnhance.Contrast(tactic_2).enhance(1.8)
        tactic_2 = ImageEnhance.Sharpness(tactic_2).enhance(1.5)
        tactic_2 = tactic_2.convert("RGB")
        
        # Tactic 3: Histogram Equalization + Edge Enhancement (combats uneven lighting/folds)
        tactic_3 = ImageOps.grayscale(crop_img)
        tactic_3 = ImageOps.equalize(tactic_3)
        tactic_3 = tactic_3.filter(ImageFilter.EDGE_ENHANCE_MORE)
        tactic_3 = tactic_3.convert("RGB")
        
        tactics = [tactic_1, tactic_2, tactic_3]
        
        for idx, crop in enumerate(tactics):
            # Convert PIL crop to NumPy array as required by EasyOCR
            crop_np = np.array(crop)
            
            # Run sub-crop OCR
            ocr_results = reader.readtext(crop_np)
            if not ocr_results:
                continue
                
            # Combine text and find highest confidence returned
            texts = [r[1] for r in ocr_results]
            confs = [r[2] for r in ocr_results]
            
            combined_text = " ".join(texts).strip()
            max_conf = max(confs) if confs else 0.0
            
            # Validate candidate text before accepting
            if _is_valid_healing_candidate(orig_text, combined_text, orig_conf, max_conf):
                if max_conf > best_tactic_conf:
                    best_tactic_text = combined_text
                    best_tactic_conf = max_conf
                
            # If we achieved high confidence (> 85%), stop running remaining tactics
            if best_tactic_conf >= 0.85:
                break
                
        # If confidence improved and candidate passed validation, update block data
        if best_tactic_conf > orig_conf and best_tactic_text != orig_text:
            gain = best_tactic_conf - orig_conf
            total_gain += gain
            
            block["text"] = best_tactic_text
            block["confidence"] = best_tactic_conf
            block["healed"] = True  # Flag that the optimizer helped!
            block["confidence_gain"] = round(gain * 100, 1) # Track block-specific optimization boost
            block["original_text"] = orig_text # Keep record of original text for visual before/after comparison
            
            # If boosted above 70%, mark as healed
            if best_tactic_conf >= 0.70:
                healed_count += 1
                
    duration_ms = (time.time() - start_time) * 1000.0
    
    optimization_stats = {
        "low_conf_original": low_conf_original,
        "healed_count": healed_count,
        "avg_confidence_gain": round((total_gain / healed_count) * 100, 1) if healed_count > 0 else 0.0,
        "healing_time_ms": round(duration_ms, 1)
    }
    
    return layout_blocks, optimization_stats
