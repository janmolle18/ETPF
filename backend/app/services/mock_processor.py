import asyncio
import random
import uuid
from typing import Any, Dict
from app.services.base import BaseDocumentProcessor


class MockDocumentProcessor(BaseDocumentProcessor):
    async def process(self, document_id: uuid.UUID, file_path: str) -> Dict[str, Any]:
        """
        Simulates running Computer Vision / OCR models.
        Wait for 3 seconds, then return realistic receipt extraction results.
        """
        # Simulate processing delay (OCR models loading and executing)
        await asyncio.sleep(3.0)

        # Mock database of potential vendors for realistic outputs
        vendors = [
            {"name": "Metro Cash & Carry", "phone": "+49 30 123456", "tax_id": "DE123456789"},
            {"name": "Bio-Company Berlin", "phone": "+49 30 9876543", "tax_id": "DE987654321"},
            {"name": "Shell Tankstelle", "phone": "+49 89 555444", "tax_id": "DE456789123"},
            {"name": "Gravis Computer GmbH", "phone": "+49 30 888999", "tax_id": "DE789123456"}
        ]

        vendor = random.choice(vendors)

        # Build line items
        items_choices = [
            ("Premium USB-C Hub", 59.99, 1),
            ("Wireless Mouse M590", 39.90, 1),
            ("Bio Espresso Bohnen 1kg", 18.50, 2),
            ("Premium Copy Paper A4", 6.50, 5),
            ("Super Fuel Super E10", 72.40, 1)
        ]

        selected_items = random.sample(items_choices, k=random.randint(2, 4))
        line_items = []
        subtotal = 0.0

        for name, price, qty in selected_items:
            total_item_price = round(price * qty, 2)
            line_items.append({
                "description": name,
                "unit_price": price,
                "quantity": qty,
                "total": total_item_price
            })
            subtotal += total_item_price

        subtotal = round(subtotal, 2)
        tax_rate = 0.19  # 19% German VAT
        tax_amount = round(subtotal * (tax_rate / (1.0 + tax_rate)), 2)

        # Bounding box simulation (layout OCR results)
        # x, y, width, height represent percentages of document size (0 to 100)
        layout_blocks = [
            {"text": vendor["name"],
             "x": 10.0, "y": 5.0, "width": 80.0, "height": 5.0, "confidence": 0.99},
            {"text": f"Tel: {vendor['phone']}",
             "x": 10.0, "y": 11.0, "width": 40.0, "height": 3.0, "confidence": 0.95},
            {"text": f"Steuer-Nr: {vendor['tax_id']}",
             "x": 10.0, "y": 14.0, "width": 50.0, "height": 3.0, "confidence": 0.98},
            {"text": "RECHNUNG",
             "x": 10.0, "y": 22.0, "width": 80.0, "height": 6.0, "confidence": 0.99},
            {"text": "Datum: 15.07.2026",
             "x": 10.0, "y": 30.0, "width": 30.0, "height": 3.0, "confidence": 0.97},
            {"text": f"Beleg-ID: {document_id}",
             "x": 10.0, "y": 33.0, "width": 60.0, "height": 3.0, "confidence": 0.96}
        ]

        # Append line items layout representation
        current_y = 42.0
        for item in line_items:
            layout_blocks.append({
                "text": f"{item['description']} x{item['quantity']}",
                "x": 10.0, "y": current_y, "width": 50.0, "height": 3.0, "confidence": 0.94
            })
            layout_blocks.append({
                "text": f"{item['total']} EUR",
                "x": 75.0, "y": current_y, "width": 15.0, "height": 3.0, "confidence": 0.96
            })
            current_y += 5.0

        # Add summary layout blocks
        current_y += 2.0
        layout_blocks.append({
            "text": f"SUBTOTAL: {subtotal} EUR",
            "x": 50.0, "y": current_y, "width": 40.0, "height": 4.0, "confidence": 0.98
        })
        current_y += 4.0
        layout_blocks.append({
            "text": f"MWST 19%: {tax_amount} EUR",
            "x": 50.0, "y": current_y, "width": 40.0, "height": 4.0, "confidence": 0.97
        })
        current_y += 4.0
        layout_blocks.append({
            "text": f"TOTAL: {subtotal} EUR",
            "x": 45.0, "y": current_y, "width": 45.0, "height": 6.0, "confidence": 0.99
        })

        # Raw text concatenation
        raw_lines = [block["text"] for block in layout_blocks]
        raw_text = "\n".join(raw_lines)

        return {
            "raw_text": raw_text,
            "layout_data": {
                "width": 800,
                "height": 1200,
                "blocks": layout_blocks
            },
            "extracted_data": {
                "vendor_name": vendor["name"],
                "tax_id": vendor["tax_id"],
                "phone": vendor["phone"],
                "date": "2026-07-15",
                "total_amount": subtotal,
                "tax_amount": tax_amount,
                "currency": "EUR",
                "line_items": line_items
            }
        }
