import asyncio
import os
import sys
import uuid
from PIL import Image, ImageDraw, ImageFont
import fitz  # PyMuPDF

# Reconfigure stdout/stderr to support UTF-8 characters on Windows
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from app.services.easyocr_processor import EasyOCRDocumentProcessor

def draw_visual_debug_boxes(src_image_path: str, result: dict, output_path: str):
    """Loads source image, translates percentage-based blocks to pixels, draws red boxes, and saves."""
    with Image.open(src_image_path) as img:
        img_w, img_h = img.size
        # Make a copy to draw on
        draw_img = img.copy()
        draw = ImageDraw.Draw(draw_img)
        
        # Load default font
        font = ImageFont.load_default()
        
        for idx, block in enumerate(result["layout_data"]["blocks"]):
            x_px = (block["x"] / 100.0) * img_w
            y_px = (block["y"] / 100.0) * img_h
            w_px = (block["width"] / 100.0) * img_w
            h_px = (block["height"] / 100.0) * img_h
            
            # Draw red border
            draw.rectangle([x_px, y_px, x_px + w_px, y_px + h_px], outline="red", width=2)
            # Draw small index text
            draw.text((x_px + 2, y_px - 10 if y_px > 12 else y_px + 2), f"#{idx+1}", fill="red", font=font)
            
        draw_img.save(output_path)
        print(f"Saved visual debug results to: {output_path}")


async def test_searchable_pdf():
    print("\n=== Running Searchable PDF Test ===")
    pdf_path = "test_receipt_digital.pdf"
    
    # 1. Create a synthetic digital PDF
    doc = fitz.open()
    page = doc.new_page(width=800, height=1000)
    
    # Draw digital text onto PDF page
    page.insert_text((100, 80), "METRO CASH AND CARRY", fontsize=32)
    page.insert_text((100, 150), "Tel: +49 30 123456", fontsize=22)
    page.insert_text((100, 200), "DE123456789", fontsize=22)
    page.insert_text((100, 300), "Datum: 15.07.2026", fontsize=22)
    page.insert_text((100, 450), "Premium USB-C Hub   x1", fontsize=22)
    page.insert_text((600, 450), "59.99 EUR", fontsize=22)
    page.insert_text((400, 650), "SUMME: 59.99 EUR", fontsize=32)
    
    doc.save(pdf_path)
    doc.close()
    print(f"Created synthetic digital PDF: {pdf_path}")
    
    # 2. Process searchable PDF
    processor = EasyOCRDocumentProcessor()
    doc_id = uuid.uuid4()
    
    try:
        # Measure processing speed (digital should be extremely fast)
        import time
        start_t = time.time()
        result = await processor.process(doc_id, pdf_path)
        end_t = time.time()
        duration_ms = (end_t - start_t) * 1000.0
        
        print(f"PDF processed in: {duration_ms:.2f} ms")
        print(f"Blocks Found: {len(result['layout_data']['blocks'])}")
        
        # Verify 100% confidence for digital blocks
        for block in result['layout_data']['blocks']:
            assert block['confidence'] == 1.0, f"Expected 1.0 confidence for digital block, got {block['confidence']}"
            
        assert "METRO" in result['raw_text'], "Digital text missing from raw_text output"
        assert result['extracted_data']['total_amount'] == 59.99, "Failed to parse total amount from PDF"
        print("[PASS] PDF digital text extraction and assertions succeeded!")
        
        # 3. Create visual output (render PDF page 1 first to draw on it)
        pdf_doc = fitz.open(pdf_path)
        pdf_page = pdf_doc.load_page(0)
        pix = pdf_page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
        temp_img_path = "temp_pdf_render.png"
        pix.save(temp_img_path)
        pdf_doc.close()
        
        # Draw red boxes on top of rendered PDF page
        draw_visual_debug_boxes(temp_img_path, result, "test_result_pdf.png")
        
        if os.path.exists(temp_img_path):
            os.remove(temp_img_path)
            
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
            print("Cleaned up synthetic PDF file.")


async def test_scanned_png():
    print("\n=== Running Scanned PNG Image Test ===")
    img_width = 800
    img_height = 1000
    img_path = "test_receipt_image.png"
    
    # 1. Create a synthetic receipt image
    img = Image.new("RGB", (img_width, img_height), color="white")
    draw = ImageDraw.Draw(img)
    
    try:
        font_large = ImageFont.truetype("arial.ttf", 36)
        font_medium = ImageFont.truetype("arial.ttf", 26)
    except IOError:
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        
    # Draw receipt texts
    draw.text((100, 80), "METRO CASH AND CARRY", fill="black", font=font_large)
    draw.text((100, 150), "Tel: +49 30 123456", fill="black", font=font_medium)
    draw.text((100, 200), "DE123456789", fill="black", font=font_medium)
    draw.text((100, 300), "Datum: 15.07.2026", fill="black", font=font_medium)
    draw.text((100, 450), "Premium USB-C Hub   x1", fill="black", font=font_medium)
    draw.text((600, 450), "59.99 EUR", fill="black", font=font_medium)
    draw.text((400, 650), "SUMME: 59.99 EUR", fill="black", font=font_large)
    
    img.save(img_path)
    print(f"Created synthetic receipt image: {img_path}")
    
    # 2. Process image
    processor = EasyOCRDocumentProcessor()
    doc_id = uuid.uuid4()
    
    try:
        result = await processor.process(doc_id, img_path)
        print(f"Blocks Found via EasyOCR: {len(result['layout_data']['blocks'])}")
        
        # Verify bounding box coordinate conversion (all should be between 0 and 100)
        blocks = result['layout_data']['blocks']
        assert len(blocks) > 0, "No layout text blocks were detected by EasyOCR"
        for i, block in enumerate(blocks):
            assert 0.0 <= block['x'] <= 100.0, f"Block {i} x coordinate out of bounds: {block['x']}"
            assert 0.0 <= block['y'] <= 100.0, f"Block {i} y coordinate out of bounds: {block['y']}"
            
        assert "METRO" in result['raw_text'].upper(), "EasyOCR failed to detect vendor text"
        assert result['extracted_data']['total_amount'] == 59.99, "Failed to parse total amount from image"
        print("[PASS] PNG Image OCR and assertions succeeded!")
        
        # 3. Create visual output
        draw_visual_debug_boxes(img_path, result, "test_result_png.png")
        
    finally:
        if os.path.exists(img_path):
            os.remove(img_path)
            print("Cleaned up synthetic PNG file.")


async def main():
    print("--- Starting Automated OCR and PDF Verification Suite ---")
    await test_searchable_pdf()
    await test_scanned_png()
    print("\nAll verification tests completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())
