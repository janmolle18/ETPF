import asyncio
import os
import re
import sys
import uuid
import random
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

# Reconfigure stdout for Windows console UTF-8 support
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Add backend directory to Python path if imported elsewhere
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from app.services.easyocr_processor import EasyOCRDocumentProcessor

# Diverse Ground Truth definitions for each stage
GROUND_TRUTHS = {
    "rotation": [
        "ITALIANO PIZZERIA",
        "Steuer-Nr: 12/345/67890",
        "Datum: 10.07.2026",
        "1x Pizza Margherita  9.50 EUR",
        "1x Aqua Frizzante    3.20 EUR",
        "Total: 12.70 EUR"
    ],
    "shear": [
        "SHELL STATION 0412",
        "USt-IdNr: DE811122334",
        "Datum: 12.07.2026",
        "Super Fuel 45L      76.50 EUR",
        "Snack Box            4.99 EUR",
        "Summe: 81.49 EUR"
    ],
    "motion_blur": [
        "OFFICE DEPOT GERMANY",
        "USt-IdNr: DE998877665",
        "Datum: 14.07.2026",
        "Laser Toner Black   89.99 EUR",
        "A4 Paper Copier x5   24.95 EUR",
        "Gesamt: 114.94 EUR"
    ],
    "creases": [
        "BAUHAUS BAUMARKT",
        "USt-Id: DE445566778",
        "Datum: 15.07.2026",
        "Work Gloves L-Size   12.50 EUR",
        "Safety Goggles       18.90 EUR",
        "Gesamt: 31.40 EUR"
    ],
    "shadow": [
        "TAXI SERVICE MUNCHEN",
        "USt-IdNr: DE776655443",
        "Datum: 16.07.2026",
        "Fahrtkosten Munich   45.00 EUR",
        "Trinkgeld             5.00 EUR",
        "Summe: 50.00 EUR"
    ],
    "dark_blur": [
        "REWE MARKET GMBH",
        "USt-IdNr: DE223344556",
        "Datum: 16.07.2026",
        "Bio Apple 1kg        3.49 EUR",
        "Orange Juice 2L      2.99 EUR",
        "Summe: 6.48 EUR"
    ],
    "crumpled_skew": [
        "MEDIA MARKT COLOGNE",
        "USt-IdNr: DE554433221",
        "Datum: 16.07.2026",
        "USB-C Cable 2m      14.99 EUR",
        "Powerbank 20k mAh    49.99 EUR",
        "Summe: 64.98 EUR"
    ],
    "faded_thermal": [
        "APOTHEKE AM DOM",
        "USt-IdNr: DE887766554",
        "Datum: 16.07.2026",
        "Painkiller Ibu 400   6.85 EUR",
        "Vitamin C Tab x2    12.40 EUR",
        "Gesamt: 19.25 EUR"
    ]
}


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculates Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def substring_similarity(block_text: str, gt: str) -> float:
    """Slide a matching window across gt to find the best substring alignment
    accuracy, with normalized whitespace.
    """
    norm_block = re.sub(r'\s+', ' ', block_text).strip().lower()
    norm_gt = re.sub(r'\s+', ' ', gt).strip().lower()

    b_len = len(norm_block)
    g_len = len(norm_gt)
    if b_len == 0 or g_len == 0:
        return 0.0

    if b_len >= g_len:
        dist = levenshtein_distance(norm_block, norm_gt)
        return max(0.0, 1.0 - (dist / b_len))

    best_sim = 0.0
    # Slide window representing the length of the block (+/- 3 characters buffer)
    for length in range(max(1, b_len - 3), min(g_len, b_len + 4)):
        for start in range(0, g_len - length + 1):
            sub = norm_gt[start:start+length]
            dist = levenshtein_distance(norm_block, sub)
            sim = max(0.0, 1.0 - (dist / max(b_len, length)))
            if sim > best_sim:
                best_sim = sim
    return best_sim


def compute_ocr_accuracy(ground_truth_lines: list[str], ocr_blocks: list[dict]) -> float:
    """Combines segments matching a ground truth line and calculates text coverage accuracy."""
    if not ground_truth_lines:
        return 0.0
    if not ocr_blocks:
        return 0.0

    total_accuracy = 0.0
    for gt in ground_truth_lines:
        norm_gt = re.sub(r'\s+', ' ', gt).strip().lower()
        best_line_acc = 0.0

        # 1. Single block similarity against ground truth line
        for block in ocr_blocks:
            parsed_text = block["text"]
            sim = substring_similarity(parsed_text, gt)
            if sim > best_line_acc:
                best_line_acc = sim

        # 2. Combined subset blocks similarity against ground truth line
        matching_texts = [
            re.sub(r'\s+', ' ', b["text"]).strip() for b in ocr_blocks
            if substring_similarity(b["text"], gt) >= 0.15
        ]
        if matching_texts:
            combined_ocr = " ".join(matching_texts).lower()
            dist = levenshtein_distance(norm_gt, combined_ocr)
            max_len = max(len(norm_gt), len(combined_ocr))
            combined_sim = max(0.0, 1.0 - (dist / max_len)) if max_len > 0 else 1.0
            if combined_sim > best_line_acc:
                best_line_acc = combined_sim

        total_accuracy += best_line_acc

    return (total_accuracy / len(ground_truth_lines)) * 100.0


def generate_base_receipt(degradation_type: str) -> Image.Image:
    """Generate a high-quality base synthetic receipt with crisp text,
    specific to a degradation stage.
    """
    width, height = 800, 1000
    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)

    # Load fonts
    try:
        f_large = ImageFont.truetype("arial.ttf", 36)
        f_medium = ImageFont.truetype("arial.ttf", 26)
    except IOError:
        f_large = ImageFont.load_default()
        f_medium = ImageFont.load_default()

    lines = GROUND_TRUTHS.get(degradation_type, GROUND_TRUTHS["rotation"])

    # Draw texts dynamically
    draw.text((100, 100), lines[0], fill="black", font=f_large)
    draw.text((100, 200), lines[1], fill="black", font=f_medium)
    draw.text((100, 300), lines[2], fill="black", font=f_medium)

    draw.text((100, 480), lines[3], fill="black", font=f_medium)
    draw.text((100, 530), lines[4], fill="black", font=f_medium)

    draw.text((380, 680), lines[5], fill="black", font=f_large)

    return img


# Advanced degradation transforms
def apply_rotation(img: Image.Image, angle: float) -> Image.Image:
    """Rotates the receipt image around its center."""
    if angle == 0:
        return img
    return img.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor="white")


def apply_shear_stretch(img: Image.Image, shear_x: float) -> Image.Image:
    """Applies horizontal shearing/stretching to distort text coordinates."""
    if shear_x == 0:
        return img
    width, height = img.size
    # Shift top right coordinate to introduce horizontal skewing
    x_shift = width * shear_x
    coeffs = (1, shear_x, -x_shift / 2, 0, 1, 0)
    return img.transform(
        (width, height), Image.AFFINE, coeffs,
        resample=Image.BICUBIC, fillcolor="white",
    )


def apply_motion_blur(img: Image.Image, radius: int) -> Image.Image:
    """Simulates linear camera motion blur by blending shifted offset sheets."""
    if radius <= 0:
        return img
    width, height = img.size
    blur_img = img.copy()
    # Directional shift in X axis
    for offset in range(1, radius + 1):
        shifted = img.copy()
        coeffs = (1, 0, -offset, 0, 1, 0)
        shifted = shifted.transform((width, height), Image.AFFINE, coeffs, fillcolor="white")
        blur_img = Image.blend(blur_img, shifted, 0.5)
    return blur_img


def apply_crumpled_creases(img: Image.Image, num_creases: int) -> Image.Image:
    """Draws thin shadow lines and highlight creases to simulate folded paper."""
    if num_creases <= 0:
        return img
    width, height = img.size
    draw = ImageDraw.Draw(img)
    random.seed(42) # Deterministic creases

    for _ in range(num_creases):
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(0, width)
        y2 = random.randint(0, height)
        # Shadow fold line
        draw.line([x1, y1, x2, y2], fill=(215, 215, 215), width=1)
        # Accompanying highlight fold line
        draw.line([x1 + 1, y1 + 1, x2 + 1, y2 + 1], fill=(255, 255, 255), width=1)
    return img


def apply_shadow_lighting(img: Image.Image, shadow_level: int) -> Image.Image:
    """Applies a linear shadow gradient from top to bottom."""
    if shadow_level <= 0:
        return img
    width, height = img.size
    mask = Image.new("L", (width, height), color=255)
    m_draw = ImageDraw.Draw(mask)

    for y in range(height):
        # Linearly dim brightness down to shadow level at the bottom
        brightness = int(255 - (y / height) * shadow_level)
        m_draw.line([(0, y), (width, y)], fill=max(0, brightness))

    return Image.composite(img, Image.new("RGB", (width, height), color="black"), mask)


async def execute_degradation_run(
    doc_id: uuid.UUID,
    degradation_type: str,
    level: float,
    processor: EasyOCRDocumentProcessor,
    repo = None
) -> dict:
    """Generates, degrades, processes, and scores a single test case."""
    base_img = generate_base_receipt(degradation_type)

    # Apply selected filter
    if degradation_type == "rotation":
        degraded = apply_rotation(base_img, angle=level)
    elif degradation_type == "shear":
        degraded = apply_shear_stretch(base_img, shear_x=level)
    elif degradation_type == "motion_blur":
        degraded = apply_motion_blur(base_img, radius=int(level))
    elif degradation_type == "creases":
        degraded = apply_crumpled_creases(base_img, num_creases=int(level))
    elif degradation_type == "shadow":
        degraded = apply_shadow_lighting(base_img, shadow_level=int(level))
    elif degradation_type == "dark_blur":
        temp = apply_motion_blur(base_img, radius=3)
        degraded = apply_shadow_lighting(temp, shadow_level=int(level))
    elif degradation_type == "crumpled_skew":
        temp = apply_rotation(base_img, angle=6.0)
        temp = apply_shear_stretch(temp, shear_x=0.22)
        degraded = apply_crumpled_creases(temp, num_creases=int(level))
    elif degradation_type == "faded_thermal":
        enhancer = ImageEnhance.Contrast(base_img)
        temp = enhancer.enhance(level)
        temp = apply_motion_blur(temp, radius=1)
        degraded = apply_crumpled_creases(temp, num_creases=15)

        # Add pixel noise to simulate cheap photocopy scanner sensor
        width, height = degraded.size
        pixels = degraded.load()
        random.seed(42)
        for _ in range(4000):
            x = random.randint(0, width - 1)
            y = random.randint(0, height - 1)
            pixels[x, y] = (165, 165, 165)
    else:
        degraded = base_img

    # Save degraded image to disk
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(settings.UPLOAD_DIR, f"{doc_id}.png")
    degraded.save(file_path)

    # Save formatted name
    label = f"{level}"
    if degradation_type == "shear":
        label = f"{int(level * 100)}% skew"
    elif degradation_type == "motion_blur":
        label = f"{int(level)}px radius"
    elif degradation_type == "rotation":
        label = f"{level}°"
    elif degradation_type == "creases":
        label = f"{int(level)} lines"
    elif degradation_type == "shadow":
        label = f"{int((level / 255) * 100)}% dimming"
    elif degradation_type == "dark_blur":
        label = f"3px blur + {int((level / 255) * 100)}% dim"
    elif degradation_type == "crumpled_skew":
        label = f"22% skew + {int(level)} folds + 6° rot"
    elif degradation_type == "faded_thermal":
        label = f"{int(level * 100)}% contrast + noise"

    # Register in database if repo is available
    db_doc_id = doc_id
    if repo is not None:
        db_doc = await repo.create(
            filename=f"stress_{degradation_type}_{label.replace(' ', '_')}.png",
            content_type="image/png",
            file_path=file_path
        )
        db_doc_id = db_doc.id
        await repo.update(db_doc_id, status="PROCESSING")

    # Process file through OCR
    import time
    start_t = time.time()
    result = await processor.process(db_doc_id, file_path)
    duration_ms = (time.time() - start_t) * 1000.0

    # Attach block-by-block text matching similarity accuracy using substring window matching
    lines = GROUND_TRUTHS.get(degradation_type, GROUND_TRUTHS["rotation"])
    for block in result["layout_data"]["blocks"]:
        best_acc = 0.0
        best_gt = ""
        parsed_text = block["text"]
        for gt in lines:
            sim = substring_similarity(parsed_text, gt)
            if sim > best_acc:
                best_acc = sim
                best_gt = gt
        block["accuracy"] = round(best_acc * 100, 1)
        block["ground_truth"] = re.sub(r'\s+', ' ', best_gt).strip()

    # Clean up test file from disk ONLY if running locally in CLI (otherwise keep for UI previews)
    if repo is None:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
    else:
        # Save results in DB
        await repo.update(
            db_doc_id,
            status="COMPLETED",
            raw_text=result["raw_text"],
            layout_data=result["layout_data"],
            extracted_data=result["extracted_data"]
        )

    # Calculate overall document accuracy (Match value)
    accuracy = compute_ocr_accuracy(lines, result["layout_data"]["blocks"])

    # Calculate average model confidence score
    blocks = result["layout_data"]["blocks"]
    avg_conf = (sum(b["confidence"] for b in blocks) / len(blocks)) * 100.0 if blocks else 0.0

    return {
        "document_id": str(db_doc_id) if repo is not None else None,
        "degradation": degradation_type,
        "level": level,
        "label": label,
        "confidence": round(avg_conf, 1),
        "accuracy": round(accuracy, 1),
        "time_ms": round(duration_ms, 1),
        "blocks_found": len(result["layout_data"]["blocks"]),
        "optimization_stats": result["layout_data"].get("optimization_stats"),
        "deskew_stats": result["layout_data"].get("deskew_stats"),
        "postprocessing_stats": result["layout_data"].get("postprocessing_stats"),
        "ground_truth_lines": lines,
        "blocks": [
            {
                "predicted_value": b["text"],
                "actual_value": b.get("ground_truth", ""),
                "confidence_pct": round(b["confidence"] * 100, 1),
                "match_accuracy_pct": b.get("accuracy", 0.0),
                "healed": b.get("healed", False),
                "original_text": b.get("original_text", None),
                "bounding_box": {
                    "x_pct": b["x"],
                    "y_pct": b["y"],
                    "width_pct": b["width"],
                    "height_pct": b["height"]
                }
            }
            for b in result["layout_data"]["blocks"]
        ]
    }


async def run_stress_test_suite(subset: bool = False, repo = None) -> list[dict]:
    """Runs the full or subset stress test matrix."""
    processor = EasyOCRDocumentProcessor()
    results = []

    # Define test parameters matrix
    if subset:
        # A quick subset of 8 tests for UI snappy loading including compound types
        matrix = [
            ("rotation", 5.0),
            ("shear", 0.15),
            ("motion_blur", 2.0),
            ("creases", 15.0),
            ("shadow", 120.0),
            ("dark_blur", 160.0),
            ("crumpled_skew", 25.0),
            ("faded_thermal", 0.25)
        ]
    else:
        # Full matrix of 18 tests for comprehensive report
        matrix = [
            ("rotation", 0.0),
            ("rotation", 5.0),
            ("rotation", 12.0),

            ("shear", 0.0),
            ("shear", 0.15),
            ("shear", 0.30),

            ("motion_blur", 0.0),
            ("motion_blur", 2.0),
            ("motion_blur", 4.0),

            ("creases", 0.0),
            ("creases", 20.0),
            ("creases", 45.0),

            ("shadow", 0.0),
            ("shadow", 100.0),
            ("shadow", 200.0),

            ("dark_blur", 160.0),
            ("crumpled_skew", 25.0),
            ("faded_thermal", 0.25)
        ]

    for idx, (degr, lvl) in enumerate(matrix):
        print(f"Running Stress Case #{idx+1}: {degr.upper()} level {lvl}...")
        test_id = uuid.uuid4()
        run_res = await execute_degradation_run(test_id, degr, lvl, processor, repo=repo)
        results.append(run_res)

    return results


async def main():
    print("--- Initiating OCR Degradation and Stress Testing Suite ---")
    start_time = asyncio.get_event_loop().time()
    runs = await run_stress_test_suite(subset=False)
    duration = asyncio.get_event_loop().time() - start_time

    # Generate scorecard markdown report
    report_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "storage")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, "degradation_report.md")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# OCR Degradation Scorecard Report\n\n")
        f.write(
            f"Executed stress testing suite over **{len(runs)}** variations "
            f"in **{duration:.2f} seconds**.\n\n"
        )

        # Write tables
        f.write(
            "| Degradation Type | Intensity Level | OCR Character Accuracy "
            "| OCR Blocks | Time (ms) |\n"
        )
        f.write("| --- | --- | --- | --- | --- |\n")
        for run in runs:
            f.write(
                f"| {run['degradation'].capitalize()} | {run['label']} "
                f"| **{run['accuracy']}%** | {run['blocks_found']} "
                f"| {run['time_ms']} |\n"
            )

        f.write("\n\n## Limits Mapping Analysis\n")
        f.write("- **Perfect Baseline**: Accuracy is expected at 100% when degradation is 0.\n")
        f.write("- **Motion Blur Limit**: Evaluates standard camera smudge limits.\n")
        f.write("- **Shearing Limit**: Tests parsing resilience when stretched or skewed.\n")
        f.write("- **Illumination Limit**: Evaluates print readability in shadows.\n")

    print(f"\nDone! Saved scorecard report to: {report_path}")

if __name__ == "__main__":
    asyncio.run(main())
