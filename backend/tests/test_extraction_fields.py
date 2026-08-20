"""
Fixture-based tests for the v2 extraction pipeline.

No OCR inference happens here – blocks are provided as synthetic JSON fixtures.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.services.extraction.fields import (
    extract_fields,
    parse_german_amount_cents,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "invoices"
FIXTURE_FILES = sorted(FIXTURES_DIR.glob("*.json"))


# ---------------------------------------------------------------------------
# Amount-parsing unit tests
# ---------------------------------------------------------------------------

class TestParseGermanAmountCents:
    def test_german_with_thousands(self):
        assert 420000 in parse_german_amount_cents("4.200,00 EUR")

    def test_german_without_thousands(self):
        assert 5042 in parse_german_amount_cents("50,42")

    def test_international_format(self):
        assert 5042 in parse_german_amount_cents("50.42")

    def test_date_not_parsed_as_amount(self):
        amounts = parse_german_amount_cents("Datum: 15.07.2026")
        assert 0 not in amounts
        # The date "15.07.2026" should NOT yield 1507 (cents) as a match
        assert all(a > 10000 or a == 0 for a in amounts) or amounts == []

    def test_large_german_amount(self):
        assert 511700 in parse_german_amount_cents("5.117,00")

    def test_small_cents(self):
        assert 25 in parse_german_amount_cents("0,25")

    def test_multiple_amounts_in_text(self):
        results = parse_german_amount_cents("Netto 83,19 MwSt 15,81 Gesamt 99,00")
        assert 8319 in results
        assert 1581 in results
        assert 9900 in results


# ---------------------------------------------------------------------------
# Fixture-based field extraction tests
# ---------------------------------------------------------------------------

def _load_fixture(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize("fixture_path", FIXTURE_FILES, ids=[f.stem for f in FIXTURE_FILES])
def test_fixture_extraction(fixture_path: Path):
    """Each fixture must meet hard minimum-accuracy requirements per field."""
    data = _load_fixture(fixture_path)
    blocks = data["blocks"]
    expected = data["expected"]

    result = extract_fields(blocks)

    # --- vendor_name: must match (case-insensitive prefix)
    if "vendor_name" in expected:
        exp_vendor = expected["vendor_name"].lower()
        got_vendor = result.get("vendor_name", "").lower()
        assert exp_vendor[:20] in got_vendor or got_vendor[:20] in exp_vendor, (
            f"[{fixture_path.name}] vendor_name mismatch: {result['vendor_name']!r} vs {expected['vendor_name']!r}"
        )

    # --- date: exact ISO match
    if "date" in expected:
        assert result.get("date") == expected["date"], (
            f"[{fixture_path.name}] date mismatch: {result.get('date')!r} vs {expected['date']!r}"
        )

    # --- service_date: exact ISO match when present
    if "service_date" in expected:
        assert result.get("service_date") == expected["service_date"], (
            f"[{fixture_path.name}] service_date mismatch: {result.get('service_date')!r}"
        )

    # --- invoice_number: exact match when present
    if "invoice_number" in expected:
        assert result.get("invoice_number") == expected["invoice_number"], (
            f"[{fixture_path.name}] invoice_number: {result.get('invoice_number')!r} vs {expected['invoice_number']!r}"
        )

    # --- tax_id: exact match when present
    if "tax_id" in expected:
        assert result.get("tax_id") == expected["tax_id"], (
            f"[{fixture_path.name}] tax_id: {result.get('tax_id')!r} vs {expected['tax_id']!r}"
        )

    # --- steuernummer: present when expected
    if "steuernummer" in expected:
        assert result.get("steuernummer") == expected["steuernummer"], (
            f"[{fixture_path.name}] steuernummer: {result.get('steuernummer')!r}"
        )

    # --- total_amount: within ±2 cents
    if "total_amount" in expected:
        got = result.get("total_amount", 0)
        exp = expected["total_amount"]
        assert abs(got - exp) <= 2, (
            f"[{fixture_path.name}] total_amount: got {got} expected {exp}"
        )

    # --- tax_amount: within ±3 cents
    if "tax_amount" in expected:
        got = result.get("tax_amount", 0)
        exp = expected["tax_amount"]
        assert abs(got - exp) <= 3, (
            f"[{fixture_path.name}] tax_amount: got {got} expected {exp}"
        )

    # --- net_amount: within ±5 cents
    if "net_amount" in expected:
        got = result.get("net_amount", 0)
        exp = expected["net_amount"]
        assert abs(got - exp) <= 5, (
            f"[{fixture_path.name}] net_amount: got {got} expected {exp}"
        )

    # --- tax_amount_source: exact match when present
    if "tax_amount_source" in expected:
        assert result.get("tax_amount_source") == expected["tax_amount_source"], (
            f"[{fixture_path.name}] tax_amount_source: {result.get('tax_amount_source')!r}"
        )

    # --- vat_breakdown: correct number of entries and rates
    if "vat_breakdown" in expected:
        got_breakdown = result.get("vat_breakdown", [])
        exp_breakdown = expected["vat_breakdown"]
        assert len(got_breakdown) == len(exp_breakdown), (
            f"[{fixture_path.name}] vat_breakdown length: {len(got_breakdown)} vs {len(exp_breakdown)}"
        )
        got_rates = {entry["rate"] for entry in got_breakdown}
        exp_rates = {entry["rate"] for entry in exp_breakdown}
        assert got_rates == exp_rates, (
            f"[{fixture_path.name}] vat_breakdown rates: {got_rates} vs {exp_rates}"
        )
        # Per-rate tax_cents within ±3 cents
        for exp_entry in exp_breakdown:
            rate = exp_entry["rate"]
            got_entry = next((e for e in got_breakdown if e["rate"] == rate), None)
            assert got_entry is not None, f"[{fixture_path.name}] VAT rate {rate}% missing"
            assert abs(got_entry["tax_cents"] - exp_entry["tax_cents"]) <= 3, (
                f"[{fixture_path.name}] VAT {rate}% tax_cents: {got_entry['tax_cents']} vs {exp_entry['tax_cents']}"
            )


class TestCoffeeShopReceiptExtraction:
    def test_us_coffee_receipt_parsing(self):
        blocks = [
            {"text": "2847 Madison Avenue", "x": 30.0, "y": 18.0},
            {"text": "New York, NY 10017", "x": 30.0, "y": 22.0},
            {"text": "(212) 555-0142", "x": 30.0, "y": 25.0},
            {"text": "10/25/2025 8:47:03 AM", "x": 30.0, "y": 28.0},
            {"text": "Order #: 10847", "x": 30.0, "y": 34.0},
            {"text": "Cashier: Sarah M.", "x": 30.0, "y": 37.0},
            {"text": "Register: 3", "x": 30.0, "y": 40.0},
            {"text": "1 Grande Latte $5.25", "x": 10.0, "y": 46.0},
            {"text": "+ Oat Milk $0.50", "x": 12.0, "y": 49.0},
            {"text": "+ Extra Shot $1.20", "x": 12.0, "y": 52.0},
            {"text": "1 Blueberry Muffin $3.00", "x": 10.0, "y": 55.0},
            {"text": "1 Americano (Tall) $3.90", "x": 10.0, "y": 58.0},
            {"text": "Subtotal $10.94", "x": 30.0, "y": 64.0},
            {"text": "Tax $2.91", "x": 30.0, "y": 67.0},
            {"text": "Total $13.85", "x": 30.0, "y": 70.0},
            {"text": "Bank Card **** **** **** 1234", "x": 10.0, "y": 76.0},
            {"text": "Entry Mode Swiped", "x": 10.0, "y": 79.0},
            {"text": "Card Type Visa", "x": 10.0, "y": 82.0},
            {"text": "Thank you!", "x": 40.0, "y": 88.0},
        ]

        result = extract_fields(blocks)

        assert result["date"] == "2025-10-25"
        assert result["total_amount"] == 1385
        assert result["tax_amount"] == 291
        assert result["net_amount"] == 1094

        items = result["line_items"]
        assert len(items) >= 4

        descriptions = [it["description"] for it in items]
        assert any("Grande Latte" in d for d in descriptions)
        assert any("Oat Milk" in d for d in descriptions)
        assert any("Extra Shot" in d for d in descriptions)
        assert any("Blueberry Muffin" in d for d in descriptions)
        assert any("Americano" in d for d in descriptions)

