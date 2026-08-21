"""Pure, testable field extraction from OCR layout blocks."""
from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Result type (plain dict for now; callers may convert to Pydantic models)
# ---------------------------------------------------------------------------

# All monetary values are integer EUR-Cents to avoid float rounding.


# ---------------------------------------------------------------------------
# Helpers: amount parsing
# ---------------------------------------------------------------------------

def _overlaps(start: int, end: int, used: list[tuple[int, int]]) -> bool:
    return any(s < end and start < e for s, e in used)


def parse_german_amount_cents(text: str) -> list[int]:
    """
    Parse monetary amounts in German and US number format and return integer cents.

    Handles:
    - `1.234,56` or `$1.234,56` → 123456
    - `1,234.56` or `$1,234.56` → 123456
    - `234,56` or `$234,56` or `85,25` → 23456
    - `234.56` or `$234.56` or `$5.25` → 23456 / 525
    """
    used: list[tuple[int, int]] = []
    results: list[int] = []

    # 1. German with thousands separator: 1.234,56
    for m in re.finditer(r'[\$\€]?\s*(\d{1,3}(?:\.\d{3})+),(\d{2})\b', text):
        int_part = m.group(1).replace(".", "")
        results.append(int(int_part) * 100 + int(m.group(2)))
        used.append((m.start(), m.end()))

    # 2. US with thousands separator: 1,234.56
    for m in re.finditer(r'[\$\€]?\s*(\d{1,3}(?:,\d{3})+)\.(\d{2})\b', text):
        if not _overlaps(m.start(), m.end(), used):
            int_part = m.group(1).replace(",", "")
            results.append(int(int_part) * 100 + int(m.group(2)))
            used.append((m.start(), m.end()))

    # 3. German without thousands: 234,56
    for m in re.finditer(r'(?<!\d)[\$\€]?\s*(\d+),(\d{2})(?!\d)', text):
        if not _overlaps(m.start(), m.end(), used):
            results.append(int(m.group(1)) * 100 + int(m.group(2)))
            used.append((m.start(), m.end()))

    # 4. International / US: 234.56 (not followed by dot to avoid date false-positives)
    for m in re.finditer(r'(?<!\d)[\$\€]?\s*(\d+)\.(\d{2})(?!\d|\.)', text):
        if not _overlaps(m.start(), m.end(), used):
            results.append(int(m.group(1)) * 100 + int(m.group(2)))
            used.append((m.start(), m.end()))

    return results


# ---------------------------------------------------------------------------
# Helpers: regex patterns for structured fields
# ---------------------------------------------------------------------------

_RE_DATE_DE = re.compile(r'\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b')
_RE_DATE_ISO = re.compile(r'\b(\d{4})-(\d{2})-(\d{2})\b')
_RE_DATE_US = re.compile(r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b')

# USt-IdNr: DE + 9 digits, OCR-tolerant spaces
_RE_UST_IDNR = re.compile(
    r'\bDE\s?(\d[\s]?\d[\s]?\d[\s]?\d[\s]?\d[\s]?\d[\s]?\d[\s]?\d[\s]?\d)\b', re.IGNORECASE
)

# Steuernummer: 2-3 / 3-4 / 4-5 digits (German Finanzamt format, state-dependent)
_RE_STEUERNR = re.compile(r'\b(\d{2,3})[/\-](\d{3,4})[/\-](\d{4,5})\b')

# Invoice number keywords
_RE_INVOICE_NR = re.compile(
    r'(?:rechnungs(?:nummer|nr\.?)|re\.?-?nr\.?|invoice\s+no\.?|belegnr\.?)[:\s#]+([A-Z0-9\-/_.]{3,30})',
    re.IGNORECASE,
)

# VAT line patterns (MwSt/USt + rate + amount on same block)
_RE_VAT_KW_RATE_AMT = re.compile(
    r'(?:enthaltene\s+)?(?:davon\s+)?(?:mwst|ust|vat)[\s.]*\(?\s*(\d{1,2})\s*%\s*\)?[:\s]*(\d[\d.,]*)',
    re.IGNORECASE,
)
_RE_VAT_RATE_KW_AMT = re.compile(
    r'(\d{1,2})\s*%\s*(?:mwst|ust|vat)[:\s]*(\d[\d.,]*)',
    re.IGNORECASE,
)

# Net total keywords
_TOTAL_WORD_REGEX = re.compile(
    r'\b(?:total|summe|gesamt|endbetrag|brutto|gesamtbetrag|rechnungsbetrag)\b', re.IGNORECASE
)
_EXCLUDE_TOTAL_REGEX = re.compile(
    r'\b(?:subtotal|zwischensumme|netto|tax|mwst|ust|vat)\b', re.IGNORECASE
)

_EXPLICIT_TAX_REGEX = re.compile(r'\b(?:tax|mwst|ust|vat)\b', re.IGNORECASE)
_EXCLUDE_TAX_REGEX = re.compile(r'\b(?:subtotal|zwischensumme|total|summe|gesamt)\b', re.IGNORECASE)

_ADDRESS_KEYWORDS = re.compile(
    # NOTE: no 'dr\.' token here — it would false-positive on the German title
    # 'Dr.' in vendor names (e.g. 'Kanzlei Dr. Hoffmann'); 'drive' still matches.
    r'(?:avenue|ave|street|st\.|blvd|road|rd\.|drive|way|lane|suite|ste\.'
    r'|new york|ny \d{5}|\b\d{5}\b)',
    re.IGNORECASE,
)

# Phone
_RE_PHONE = re.compile(r'\b((?:\+?\d{1,3}[- ]?)?\(?\d{2,4}\)?[- ]?\d{3,4}[- ]?\d{3,5})\b')

# Service date keywords
_RE_LEISTUNGSDATUM = re.compile(
    r'(?:leistungsdatum|lieferdatum|lieferung)[:\s]*(\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2})',
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------

def extract_fields(blocks: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Extract structured invoice fields from OCR layout blocks.

    Blocks format (output of EasyOCRDocumentProcessor layout pipeline):
        [{"text": str, "x": float, "y": float, "width": float,
          "height": float, "confidence": float}]
    Where x, y, width, height are percentages (0–100).

    Returns a dict compatible with ExtractedData (amounts in EUR-Cents).
    """
    sorted_blocks = sorted(blocks, key=lambda b: (b.get("y", 0), b.get("x", 0)))
    full_text = "\n".join(b["text"] for b in sorted_blocks)

    vendor_name = _extract_vendor(sorted_blocks)
    date_str, service_date = _extract_dates(sorted_blocks, full_text)
    phone_str = _extract_phone(sorted_blocks)
    ust_idnr = _extract_ust_idnr(full_text)
    steuernummer = _extract_steuernummer(full_text)
    invoice_number = _extract_invoice_number(sorted_blocks)

    vat_breakdown = _extract_vat_breakdown(sorted_blocks)
    total_cents, total_source = _extract_total(sorted_blocks)
    tax_cents, tax_source, net_cents = _derive_tax_and_net(
        total_cents, vat_breakdown, sorted_blocks
    )

    consistency_ok: bool | None = None
    if total_cents > 0 and tax_cents > 0:
        # Allow ±2 cent rounding tolerance
        consistency_ok = abs((net_cents + tax_cents) - total_cents) <= 2

    line_items = _extract_line_items(sorted_blocks)

    return {
        "vendor_name": vendor_name,
        "date": date_str,
        "service_date": service_date,
        "invoice_number": invoice_number,
        "tax_id": ust_idnr,
        "steuernummer": steuernummer,
        "phone": phone_str,
        "total_amount": total_cents,
        "tax_amount": tax_cents,
        "net_amount": net_cents,
        "currency": "EUR",
        "currency_unit": "cent",
        "vat_breakdown": vat_breakdown,
        "line_items": line_items,
        # A8-style source tracking
        "total_amount_source": total_source,
        "tax_amount_source": tax_source,
        "consistency_ok": consistency_ok,
    }


# ---------------------------------------------------------------------------
# Field extractors
# ---------------------------------------------------------------------------

def _extract_vendor(blocks: list[dict]) -> str:
    for block in blocks:
        text = block["text"].strip()
        y = block.get("y", 0)
        if y > 25.0:
            break
        if not text or len(text) < 3:
            continue
        if re.search(r'\b\d+[\.,]\d{2}\b', text):
            continue
        if _RE_DATE_DE.search(text) or _RE_DATE_US.search(text) or _RE_DATE_ISO.search(text):
            continue
        if re.search(
            r'(?:tel|phone|fax|email|www|http|\.com|\.de|str\.|ust|mwst|steuer)',
            text, re.IGNORECASE
        ):
            continue
        if _ADDRESS_KEYWORDS.search(text):
            continue
        return text
    return "Unknown"


def _extract_dates(blocks: list[dict], full_text: str) -> tuple[str, str | None]:
    date_str = "Unknown"
    service_date: str | None = None

    # Try to find Leistungsdatum / Lieferdatum first
    m = _RE_LEISTUNGSDATUM.search(full_text)
    if m:
        raw = m.group(1)
        dm = _RE_DATE_DE.match(raw)
        if dm:
            service_date = f"{dm.group(3)}-{dm.group(2).zfill(2)}-{dm.group(1).zfill(2)}"
        else:
            service_date = raw

    # Invoice date: first date-looking string in blocks
    for block in blocks:
        text = block["text"].strip()
        dm = _RE_DATE_DE.search(text)
        if dm:
            candidate = f"{dm.group(3)}-{dm.group(2).zfill(2)}-{dm.group(1).zfill(2)}"
            if service_date and candidate == service_date:
                continue
            date_str = candidate
            break
        um = _RE_DATE_US.search(text)
        if um:
            candidate = f"{um.group(3)}-{um.group(1).zfill(2)}-{um.group(2).zfill(2)}"
            if service_date and candidate == service_date:
                continue
            date_str = candidate
            break
        im = _RE_DATE_ISO.search(text)
        if im:
            date_str = im.group(0)
            break

    return date_str, service_date


def _extract_phone(blocks: list[dict]) -> str | None:
    for block in blocks:
        m = _RE_PHONE.search(block["text"])
        if m:
            return m.group(1)
    return None


def _extract_ust_idnr(text: str) -> str | None:
    m = _RE_UST_IDNR.search(text)
    if m:
        digits = re.sub(r'\s', '', m.group(1))
        return f"DE{digits}"
    return None


def _extract_steuernummer(text: str) -> str | None:
    # Must be preceded by a keyword to distinguish from phone/dates
    kw_match = re.search(
        r'(?:steuernummer|steuer-nr\.?|st\.?-nr\.?)[:\s]*'
        r'(\d{2,3}[/\-]\d{3,4}[/\-]\d{4,5})',
        text,
        re.IGNORECASE,
    )
    if kw_match:
        return kw_match.group(1)
    return None


def _extract_invoice_number(blocks: list[dict]) -> str | None:
    for block in blocks:
        m = _RE_INVOICE_NR.search(block["text"])
        if m:
            return m.group(1).strip()
    return None


def _extract_vat_breakdown(blocks: list[dict]) -> list[dict]:
    """
    Parse VAT lines and return a list of vat_breakdown entries.
    Each entry: {rate: int, net_cents: int, tax_cents: int, gross_cents: int, source: str}
    """
    found: dict[int, int] = {}  # rate -> tax_cents

    for block in blocks:
        text = block["text"].strip()

        for pattern in (_RE_VAT_KW_RATE_AMT, _RE_VAT_RATE_KW_AMT):
            for m in pattern.finditer(text):
                rate = int(m.group(1))
                if rate not in (7, 19):
                    continue
                amounts = parse_german_amount_cents(m.group(2))
                if amounts:
                    found[rate] = found.get(rate, 0) + amounts[0]

    result = []
    for rate, tax_cents in sorted(found.items()):
        # tax = gross * rate / (100 + rate)  →  gross = tax * (100 + rate) / rate
        gross_cents = round(tax_cents * (100 + rate) / rate)
        net_cents = gross_cents - tax_cents
        result.append({
            "rate": rate,
            "net_cents": net_cents,
            "tax_cents": tax_cents,
            "gross_cents": gross_cents,
            "source": "extracted",
        })

    return result


_VAT_LINE_MARKERS = re.compile(r'\b(?:mwst|ust|vat)\b', re.IGNORECASE)


def _extract_total(blocks: list[dict]) -> tuple[int, str]:
    """Return (total_cents, source_string)."""
    # 1. Block that contains a keyword AND is not subtotal/tax, with amount
    for block in blocks:
        text = block["text"].strip()
        if _TOTAL_WORD_REGEX.search(text) and not _EXCLUDE_TOTAL_REGEX.search(text):
            amounts = parse_german_amount_cents(text)
            if amounts:
                return max(amounts), "extracted_keyword"

    # 2a. Keyword block + amount on SAME line (y-distance < 3%) – highest priority
    kw_blocks = [
        b for b in blocks
        if _TOTAL_WORD_REGEX.search(b["text"]) and not _EXCLUDE_TOTAL_REGEX.search(b["text"])
    ]
    for kw_b in kw_blocks:
        kw_y = kw_b.get("y", 0)
        same_line_amounts: list[int] = []
        for block in blocks:
            if abs(block.get("y", 0) - kw_y) < 3.0 and block is not kw_b:
                if not _EXCLUDE_TOTAL_REGEX.search(block["text"]):
                    amounts = parse_german_amount_cents(block["text"])
                    same_line_amounts.extend(amounts)
        if same_line_amounts:
            return max(same_line_amounts), "extracted_keyword_same_line"

    # 2b. Nearby keyword blocks (y < 8%), skip VAT / subtotal lines
    for kw_b in kw_blocks:
        kw_y = kw_b.get("y", 0)
        nearby_amounts: list[int] = []
        for block in blocks:
            if abs(block.get("y", 0) - kw_y) < 8.0 and block is not kw_b:
                if (_VAT_LINE_MARKERS.search(block["text"])
                        or _EXCLUDE_TOTAL_REGEX.search(block["text"])):
                    continue
                amounts = parse_german_amount_cents(block["text"])
                nearby_amounts.extend(amounts)
        if nearby_amounts:
            return max(nearby_amounts), "extracted_near_keyword"

    # 3. Largest amount in bottom half, excluding VAT / subtotal lines
    candidates: list[int] = []
    for block in blocks:
        if (block.get("y", 0) > 40.0
                and not _VAT_LINE_MARKERS.search(block["text"])
                and not _EXCLUDE_TOTAL_REGEX.search(block["text"])):
            candidates.extend(parse_german_amount_cents(block["text"]))
    if candidates:
        return max(candidates), "fallback_largest_bottom"

    # 4. Largest amount on page
    all_amounts: list[int] = []
    for block in blocks:
        all_amounts.extend(parse_german_amount_cents(block["text"]))
    if all_amounts:
        return max(all_amounts), "fallback_largest_page"

    return 0, "not_extracted"


def _extract_explicit_tax(blocks: list[dict]) -> tuple[int, str]:
    for block in blocks:
        text = block["text"].strip()
        if _EXPLICIT_TAX_REGEX.search(text) and not _EXCLUDE_TAX_REGEX.search(text):
            amounts = parse_german_amount_cents(text)
            if amounts:
                return amounts[0], "extracted_tax_line"
    return 0, "not_extracted"


def _derive_tax_and_net(
    total_cents: int,
    vat_breakdown: list[dict],
    blocks: list[dict] | None = None,
) -> tuple[int, str, int]:
    """
    Returns (tax_cents, tax_source, net_cents).
    """
    if vat_breakdown:
        tax_cents = sum(v["tax_cents"] for v in vat_breakdown)
        net_cents = total_cents - tax_cents
        return tax_cents, "extracted_breakdown", net_cents

    if blocks:
        exp_tax, exp_src = _extract_explicit_tax(blocks)
        if exp_tax > 0:
            net_cents = total_cents - exp_tax if total_cents >= exp_tax else 0
            return exp_tax, exp_src, net_cents

    if total_cents > 0:
        tax_cents = round(total_cents * 19 / 119)
        net_cents = total_cents - tax_cents
        return tax_cents, "calculated_19pct", net_cents

    return 0, "not_extracted", 0


_SKIP_LINE_ITEM_KEYWORDS = frozenset({
    "total", "summe", "gesamt", "endbetrag", "subtotal", "zwischensumme", "netto",
    "mwst", "ust", "vat", "tax", "steuer", "rechnungsnummer", "datum",
    "leistungsdatum", "tel", "phone", "fax", "email", "order", "cashier",
    "register", "bank card", "swiped", "visa", "card", "thank you", "rewards",
    "visit", "entry mode", "type"
})


def _extract_line_items(blocks: list[dict]) -> list[dict]:
    """
    Group blocks into lines by y-proximity, then detect description / qty / price / total.

    Returns list of {description, quantity, unit_price_cents, total_cents}.
    """
    if not blocks:
        return []

    # 1. Group blocks into text lines (y-proximity within 2.5%)
    lines: list[list[dict]] = []
    current_line: list[dict] = []

    sorted_input_blocks = sorted(blocks, key=lambda b: (b.get("y", 0), b.get("x", 0)))
    for block in sorted_input_blocks:
        if not current_line:
            current_line.append(block)
            continue
        last_y = current_line[-1].get("y", 0)
        if abs(block.get("y", 0) - last_y) <= 2.5:
            current_line.append(block)
        else:
            lines.append(current_line)
            current_line = [block]
    if current_line:
        lines.append(current_line)

    items: list[dict] = []

    for line_blocks in lines:
        line_text = " ".join(b["text"] for b in line_blocks).strip()
        if not line_text:
            continue

        lower = line_text.lower()
        if any(kw in lower for kw in _SKIP_LINE_ITEM_KEYWORDS):
            continue

        amounts = parse_german_amount_cents(line_text)
        if not amounts:
            continue

        # Extract quantity if present
        qty = 1
        qty_match = re.match(r'^(\d{1,3})\s+(?=[A-Za-z\+])', line_text)
        if qty_match:
            qty = int(qty_match.group(1))

        # Extract description by removing price patterns & leading qty
        clean_desc = line_text
        if qty_match:
            clean_desc = clean_desc[qty_match.end():].strip()

        # Strip amount patterns from description
        clean_desc = re.sub(r'[\$\€]?\s*\d+[.,]\d{2}\b', '', clean_desc).strip()
        clean_desc = re.sub(r'\s+', ' ', clean_desc).strip()

        if not clean_desc or len(clean_desc) < 2:
            continue

        total_cents = amounts[-1]
        unit_price_cents = amounts[0] if len(amounts) > 1 else total_cents

        items.append({
            "description": clean_desc,
            "quantity": qty,
            "unit_price_cents": unit_price_cents,
            "total_cents": total_cents,
        })

    return items

