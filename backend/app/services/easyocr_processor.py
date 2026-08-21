import asyncio
import logging
import os
import re
import threading
import uuid
from typing import Any, Dict
from PIL import Image, ImageEnhance
import easyocr
import fitz  # PyMuPDF

from app.services.base import BaseDocumentProcessor
from app.services.extraction.fields import extract_fields

logger = logging.getLogger(__name__)

# Global singleton for the easyocr Reader to avoid reloading weights
_reader = None
_reader_lock = threading.Lock()

def get_easyocr_reader() -> easyocr.Reader:
    global _reader
    if _reader is not None:
        return _reader
    with _reader_lock:
        if _reader is None:
            logger.info("Initialising EasyOCR reader (first use)…")
            _reader = easyocr.Reader(["de", "en"])
            logger.info("EasyOCR reader ready.")
    return _reader


def detect_and_deskew_image(pil_img: Image.Image) -> tuple[Image.Image, dict]:
    """
    Detects document text line skew angle using horizontal morphological dilation
    and line contour minAreaRect angles. Rotates the image so text baselines
    align to 0.0° horizontal.
    """
    import cv2
    import numpy as np

    try:
        img_np = np.array(pil_img)
        if len(img_np.shape) == 3 and img_np.shape[2] == 3:
            gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        elif len(img_np.shape) == 3 and img_np.shape[2] == 4:
            gray = cv2.cvtColor(img_np, cv2.COLOR_RGBA2GRAY)
        else:
            gray = img_np.copy()

        # Threshold & invert (text pixels become white 255)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # Merge horizontal characters within text lines using horizontal dilation
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (35, 3))
        dilated = cv2.dilate(thresh, kernel, iterations=2)

        # Find line contours
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        angles = []
        for cnt in contours:
            if cv2.contourArea(cnt) < 200:
                continue

            (cx, cy), (w, h), angle = cv2.minAreaRect(cnt)

            # Ensure we are measuring along the long (horizontal) axis of the line strip
            if w < h:
                angle += 90.0

            # Normalize to range [-45, 45]
            while angle <= -45.0:
                angle += 90.0
            while angle > 45.0:
                angle -= 90.0

            # Only collect valid text line angles (filters vertical noise)
            if abs(angle) < 40.0:
                angles.append(angle)

        if not angles:
            return pil_img, {
                "detected_angle_deg": 0.0,
                "correction_applied_deg": 0.0,
                "deskew_applied": False
            }

        # Calculate median text line angle
        median_angle = float(np.median(angles))

        # Ignore negligible skew (< 0.5°)
        if abs(median_angle) < 0.5:
            return pil_img, {
                "detected_angle_deg": round(median_angle, 2),
                "correction_applied_deg": 0.0,
                "deskew_applied": False
            }

        # In Pillow, rotate(deg) rotates counter-clockwise.
        # When text lines are tilted counter-clockwise (median_angle < 0),
        # rotate(median_angle) rotates clockwise to deskew to 0°.
        correction_angle = median_angle
        deskewed_img = pil_img.rotate(
            correction_angle, resample=Image.BICUBIC, expand=False, fillcolor=(255, 255, 255)
        )

        return deskewed_img, {
            "detected_angle_deg": round(median_angle, 2),
            "correction_applied_deg": round(correction_angle, 2),
            "deskew_applied": True
        }
    except Exception as e:
        logger.warning("Deskewing failed: %s", e)
        return pil_img, {
            "detected_angle_deg": 0.0,
            "correction_applied_deg": 0.0,
            "deskew_applied": False,
        }


def _preprocess_image_file(input_path: str, output_path: str) -> dict:
    """Converts image to RGB, detects & corrects skew angle, enhances contrast, and saves as RGB."""
    with Image.open(input_path) as img:
        # Convert to RGB mode (properly handles RGBA, P palette, CMYK, LA, L, etc.)
        rgb_img = img.convert('RGB')

        # Detect and de-skew image rotation
        deskewed_img, deskew_stats = detect_and_deskew_image(rgb_img)

        # Enhance contrast (2.0x)
        enhancer = ImageEnhance.Contrast(deskewed_img)
        enhanced_img = enhancer.enhance(2.0)

        # Save to output path as RGB
        enhanced_img.save(output_path, format="PNG")

        # Overwrite input_path on disk with deskewed version if deskew was applied
        # so frontend canvas preview serves the deskewed image matching bounding boxes!
        if deskew_stats.get("deskew_applied"):
            try:
                enhanced_img.save(input_path, format="PNG")
            except Exception as e:
                logger.warning("Could not update original file with deskewed version: %s", e)

        return deskew_stats


def _run_ocr_sync(file_path: str) -> list:
    """Synchronous OCR run offloaded to thread pool with tuned parameters."""
    reader = get_easyocr_reader()
    return reader.readtext(
        file_path,
        mag_ratio=1.5,      # Upscale character regions by 1.5x for fine letter details
        contrast_ths=0.1,   # Contrast detection threshold
        adjust_contrast=0.7 # High contrast adjustment bias
    )


def _clean_alphanumeric_text(text: str) -> str:
    """
    Cleans up common OCR character confusions in alphanumeric lot/batch numbers
    (e.g., correcting 'o'/'O' to '0' and 'l'/'I' to '1' when adjacent to digits).
    """
    words = text.split()
    cleaned_words = []

    for word in words:
        # Run replacement loops until string stabilizes
        # (covers multi-char confusions like 'oo' -> '00')
        prev = ""
        while prev != word:
            prev = word
            # Replace o/O with 0 if preceded or followed by any digit
            word = re.sub(r'(?<=\d)[oO]|[oO](?=\d)', '0', word)
            # Replace l/I with 1 if preceded or followed by any digit
            word = re.sub(r'(?<=\d)[lI]|[lI](?=\d)', '1', word)

        cleaned_words.append(word)

    return " ".join(cleaned_words)


class EasyOCRDocumentProcessor(BaseDocumentProcessor):
    async def process(self, document_id: uuid.UUID, file_path: str) -> Dict[str, Any]:
        """
        Processes an image or PDF using PyMuPDF and/or EasyOCR,
        computes bounding box percentages, and applies heuristics to extract receipt fields.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        is_pdf = file_path.lower().endswith('.pdf')
        temp_image_path = None
        preprocessed_path = None
        deskew_stats = None
        ocr_results = []
        img_w, img_h = 800, 1000  # Default fallback dimensions

        try:
            if is_pdf:
                # Open PDF document via PyMuPDF
                doc = fitz.open(file_path)
                try:
                    if len(doc) == 0:
                        raise ValueError("The PDF document is empty.")

                    # Load first page
                    page = doc.load_page(0)
                    page_rect = page.rect
                    img_w, img_h = page_rect.width, page_rect.height

                    # Check if it has a digital text layer
                    page_text = page.get_text("text").strip()
                    has_digital_text = len(page_text) > 15

                    if has_digital_text:
                        # Mode A: Digital PDF text extraction
                        blocks = page.get_text("blocks")
                        for x0, y0, x1, y1, text, block_no, block_type in blocks:
                            if block_type == 0:  # Text block
                                # Map to standard EasyOCR box coordinate format:
                                # [[x_min, y_min], [x_max, y_min], [x_max, y_max], [x_min, y_max]]
                                box = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
                                ocr_results.append((box, text.strip(), 1.0))
                    else:
                        # Mode B: Scanned PDF layout extraction
                        # Render page 1 to a high-res PNG (2.0x zoom)
                        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
                        temp_image_path = os.path.join(
                            os.path.dirname(file_path), f"temp_{document_id}.png"
                        )
                        pix.save(temp_image_path)

                        # Preprocess rendered PNG
                        preprocessed_path = os.path.join(
                            os.path.dirname(file_path), f"prep_{document_id}.png"
                        )
                        deskew_stats = _preprocess_image_file(temp_image_path, preprocessed_path)

                        # Update dimensions to preprocessed PNG size for calculations
                        with Image.open(preprocessed_path) as temp_img:
                            img_w, img_h = temp_img.size

                        # Run EasyOCR on the preprocessed image
                        ocr_results = await asyncio.to_thread(_run_ocr_sync, preprocessed_path)
                finally:
                    doc.close()
            else:
                # Standard Image Processing (PNG/JPG)
                # Preprocess image file
                preprocessed_path = os.path.join(
                    os.path.dirname(file_path), f"prep_{document_id}.png"
                )
                deskew_stats = _preprocess_image_file(file_path, preprocessed_path)

                with Image.open(preprocessed_path) as img:
                    img_w, img_h = img.size

                # Run EasyOCR on the preprocessed image
                ocr_results = await asyncio.to_thread(_run_ocr_sync, preprocessed_path)

            # Format raw layout blocks in pixel coordinates first
            raw_blocks = []
            for box, text, confidence in ocr_results:
                xs = [pt[0] for pt in box]
                ys = [pt[1] for pt in box]
                xmin, xmax = min(xs), max(xs)
                ymin, ymax = min(ys), max(ys)
                clean_text = text.replace('\n', ' ').strip()
                clean_text = _clean_alphanumeric_text(clean_text)
                if clean_text:
                    raw_blocks.append({
                        "xmin": xmin, "xmax": xmax,
                        "ymin": ymin, "ymax": ymax,
                        "text": clean_text, "confidence": float(confidence)
                    })

            # Sort raw blocks by vertical center first, then horizontal start
            raw_blocks.sort(key=lambda b: (b["ymin"], b["xmin"]))

            # Merge adjacent horizontal blocks on the same line (dontsplit)
            merged_blocks = []
            for block in raw_blocks:
                if not merged_blocks:
                    merged_blocks.append(block)
                    continue

                last = merged_blocks[-1]

                # Check vertical overlap
                y_overlap = min(last["ymax"], block["ymax"]) - max(last["ymin"], block["ymin"])
                last_h = last["ymax"] - last["ymin"]
                block_h = block["ymax"] - block["ymin"]
                min_h = min(last_h, block_h)

                is_same_line = False
                if min_h > 0:
                    overlap_ratio = y_overlap / min_h
                    if overlap_ratio > 0.40 or abs(last["ymin"] - block["ymin"]) < (img_h * 0.02):
                        is_same_line = True

                # Check horizontal gap closeness (group if gap is within 18% of image width)
                x_gap = block["xmin"] - last["xmax"]
                is_horizontally_close = x_gap < (img_w * 0.18)

                if is_same_line and is_horizontally_close:
                    last["xmax"] = max(last["xmax"], block["xmax"])
                    last["ymin"] = min(last["ymin"], block["ymin"])
                    last["ymax"] = max(last["ymax"], block["ymax"])
                    last["text"] = last["text"] + " " + block["text"]
                    last["confidence"] = (last["confidence"] + block["confidence"]) / 2.0
                else:
                    merged_blocks.append(block)

            # Convert merged blocks to percentages
            layout_blocks = []
            for b in merged_blocks:
                box_w = b["xmax"] - b["xmin"]
                box_h = b["ymax"] - b["ymin"]

                x_pct = (b["xmin"] / img_w) * 100.0 if img_w > 0 else 0.0
                y_pct = (b["ymin"] / img_h) * 100.0 if img_h > 0 else 0.0
                w_pct = (box_w / img_w) * 100.0 if img_w > 0 else 0.0
                h_pct = (box_h / img_h) * 100.0 if img_h > 0 else 0.0

                layout_blocks.append({
                    "text": b["text"],
                    "x": round(max(0.0, min(100.0, x_pct)), 2),
                    "y": round(max(0.0, min(100.0, y_pct)), 2),
                    "width": round(max(0.0, min(100.0, w_pct)), 2),
                    "height": round(max(0.0, min(100.0, h_pct)), 2),
                    "confidence": b["confidence"]
                })

            # Run Self-Healing OCR Optimizer off the event loop (blocking inference)
            from app.services.self_healing_ocr import optimize_low_confidence_blocks
            healing_src = temp_image_path if (is_pdf and temp_image_path) else file_path
            reader = get_easyocr_reader()
            layout_blocks, optimization_stats = await asyncio.to_thread(
                optimize_low_confidence_blocks, healing_src, layout_blocks, reader
            )

            # Run Extensible Text Postprocessor Rules Engine (Ix -> 1x, Ikg -> 1kg, etc.)
            from app.services.text_postprocessor import TextPostprocessor
            postprocessor = TextPostprocessor()
            layout_blocks, postprocessing_stats = postprocessor.process_blocks(layout_blocks)

            # Extract raw text stream
            raw_lines = [block["text"] for block in layout_blocks]
            raw_text = "\n".join(raw_lines)

            # Extract metadata fields via heuristics engine
            extracted = extract_fields(layout_blocks)

            total_amount = (
                round(extracted["total_amount"] / 100.0, 2) if extracted["total_amount"] else 0.0
            )
            tax_amount = (
                round(extracted["tax_amount"] / 100.0, 2) if extracted["tax_amount"] else 0.0
            )

            line_items = [
                {
                    "description": item["description"],
                    "unit_price": round(item["unit_price_cents"] / 100.0, 2),
                    "quantity": item["quantity"],
                    "total": round(item["total_cents"] / 100.0, 2),
                }
                for item in extracted.get("line_items", [])
            ]

            return {
                "raw_text": raw_text,
                "layout_data": {
                    "width": img_w,
                    "height": img_h,
                    "blocks": layout_blocks,
                    "optimization_stats": optimization_stats,
                    "deskew_stats": deskew_stats,
                    "postprocessing_stats": postprocessing_stats
                },
                "extracted_data": {
                    "vendor_name": extracted["vendor_name"],
                    "tax_id": extracted["tax_id"] or "Unknown",
                    "phone": extracted["phone"] or "Unknown",
                    "date": extracted["date"],
                    "total_amount": total_amount,
                    "tax_amount": tax_amount,
                    "currency": extracted.get("currency", "EUR"),
                    "line_items": line_items
                }
            }

        finally:
            # Clean up temporary PNG files if created
            for path in [temp_image_path, preprocessed_path]:
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except Exception as e:
                        logger.warning("Error deleting temporary file %s: %s", path, e)
