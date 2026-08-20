"""
Extraction eval harness – per-field accuracy table and CI threshold enforcement.

Runs all fixtures through extract_fields(), computes per-field accuracy across
the corpus, asserts hard thresholds, and prints a markdown table at end of run.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.services.extraction.fields import extract_fields

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "invoices"
FIXTURE_FILES = sorted(FIXTURES_DIR.glob("*.json"))

# Fixtures where OCR noise / foreign vendor makes certain fields unreliable.
# These are excluded from the "clean" sub-corpus for strict CI thresholds.
NOISY_FIXTURES = {
    "invoice_12_bad_ocr_noise",
    "invoice_18_handwritten_low_confidence",
    "invoice_22_ocr_noise_low_confidence_ust",
}

# CI accuracy thresholds (fraction, not percent) applied to the clean sub-corpus.
THRESHOLD_TOTAL_AMOUNT = 0.95
THRESHOLD_TAX_AMOUNT = 0.90
THRESHOLD_OVERALL = 0.80

# Fields included in the overall accuracy calculation.
_TRACKED_FIELDS = [
    "vendor_name",
    "date",
    "total_amount",
    "tax_amount",
    "invoice_number",
    "ust_idnr",
    "vat_rates",
]


def _load_fixture(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _vendor_match(got: str, exp: str) -> bool:
    got_l = (got or "").lower().strip()
    exp_l = (exp or "").lower().strip()
    return exp_l[:20] in got_l or got_l[:20] in exp_l


def _field_correct(field: str, result: dict, expected: dict) -> bool | None:
    """Return True/False if the field can be evaluated, None if not applicable."""
    if field == "vendor_name":
        if "vendor_name" not in expected:
            return None
        return _vendor_match(result.get("vendor_name", ""), expected["vendor_name"])

    if field == "date":
        if "date" not in expected:
            return None
        return result.get("date") == expected["date"]

    if field == "total_amount":
        if "total_amount" not in expected:
            return None
        got = result.get("total_amount", 0)
        return abs(got - expected["total_amount"]) <= 2

    if field == "tax_amount":
        if "tax_amount" not in expected:
            return None
        got = result.get("tax_amount", 0)
        return abs(got - expected["tax_amount"]) <= 3

    if field == "invoice_number":
        if "invoice_number" not in expected:
            return None
        return result.get("invoice_number") == expected["invoice_number"]

    if field == "ust_idnr":
        if "tax_id" not in expected:
            return None
        return result.get("tax_id") == expected["tax_id"]

    if field == "vat_rates":
        if "vat_breakdown" not in expected:
            if "vat_rates" not in expected:
                return None
            exp_rates = set(expected["vat_rates"])
            got_rates = {e["rate"] for e in result.get("vat_breakdown", [])}
            return got_rates == exp_rates
        exp_rates = {e["rate"] for e in expected["vat_breakdown"]}
        got_rates = {e["rate"] for e in result.get("vat_breakdown", [])}
        return got_rates == exp_rates

    return None


# ---------------------------------------------------------------------------
# Accumulator shared across test_fixture_accuracy parametrised instances
# ---------------------------------------------------------------------------

_accuracy_rows: list[dict] = []


@pytest.fixture(scope="session", autouse=True)
def _print_accuracy_table(request):
    """Session-scoped fixture that prints the accuracy table after all tests."""
    yield
    if not _accuracy_rows:
        return

    field_correct: dict[str, list[bool]] = {f: [] for f in _TRACKED_FIELDS}
    clean_total_correct: list[bool] = []
    clean_tax_correct: list[bool] = []
    clean_overall_correct: list[bool] = []

    for row in _accuracy_rows:
        for field in _TRACKED_FIELDS:
            val = row["fields"].get(field)
            if val is not None:
                field_correct[field].append(val)

        is_clean = not row["noisy"]
        if is_clean:
            ta = row["fields"].get("total_amount")
            if ta is not None:
                clean_total_correct.append(ta)
            tx = row["fields"].get("tax_amount")
            if tx is not None:
                clean_tax_correct.append(tx)
            all_evals = [v for v in row["fields"].values() if v is not None]
            if all_evals:
                clean_overall_correct.append(all(all_evals))

    print("\n")
    print("## Extraction Accuracy Report\n")
    header = "| Field            | Correct | Total | Accuracy |"
    sep    = "|------------------|---------|-------|----------|"
    print(header)
    print(sep)
    for field in _TRACKED_FIELDS:
        results = field_correct[field]
        if not results:
            print(f"| {field:<16} |    -    |   -   |    -     |")
            continue
        correct = sum(results)
        total = len(results)
        pct = correct / total * 100
        print(f"| {field:<16} | {correct:>7} | {total:>5} | {pct:>7.1f}% |")

    print()
    print("### CI Thresholds (clean corpus)\n")

    def _threshold_row(label: str, results: list[bool], threshold: float) -> str:
        if not results:
            return f"| {label} | - | - | - | - |"
        correct = sum(results)
        total = len(results)
        acc = correct / total
        status = "PASS" if acc >= threshold else "FAIL"
        return (
            f"| {label} | {correct}/{total} | {acc * 100:.1f}% "
            f"| >= {threshold * 100:.0f}% | {status} |"
        )

    print("| Metric | Score | Accuracy | Threshold | Status |")
    print("|--------|-------|----------|-----------|--------|")
    print(_threshold_row("total_amount_cents", clean_total_correct, THRESHOLD_TOTAL_AMOUNT))
    print(_threshold_row("tax_amount_cents", clean_tax_correct, THRESHOLD_TAX_AMOUNT))
    print(_threshold_row("overall (all fields)", clean_overall_correct, THRESHOLD_OVERALL))
    print()


@pytest.mark.parametrize("fixture_path", FIXTURE_FILES, ids=[f.stem for f in FIXTURE_FILES])
def test_fixture_accuracy(fixture_path: Path):
    """Run extraction and record per-field correctness for the accuracy report."""
    data = _load_fixture(fixture_path)
    blocks = data["blocks"]
    expected = data["expected"]

    result = extract_fields(blocks)

    stem = fixture_path.stem
    is_noisy = stem in NOISY_FIXTURES

    field_results: dict[str, bool | None] = {}
    for field in _TRACKED_FIELDS:
        field_results[field] = _field_correct(field, result, expected)

    _accuracy_rows.append({"stem": stem, "noisy": is_noisy, "fields": field_results})


# ---------------------------------------------------------------------------
# CI threshold assertions (session scope, runs once after all collection)
# ---------------------------------------------------------------------------

def test_ci_thresholds():
    """Assert hard accuracy thresholds on the clean sub-corpus."""
    if not _accuracy_rows:
        pytest.skip("No fixture data collected yet – run test_fixture_accuracy first")

    clean_total: list[bool] = []
    clean_tax: list[bool] = []
    all_fields: list[bool] = []

    for row in _accuracy_rows:
        if row["noisy"]:
            continue
        ta = row["fields"].get("total_amount")
        if ta is not None:
            clean_total.append(ta)
        tx = row["fields"].get("tax_amount")
        if tx is not None:
            clean_tax.append(tx)
        evals = [v for v in row["fields"].values() if v is not None]
        if evals:
            all_fields.extend(evals)

    if clean_total:
        acc = sum(clean_total) / len(clean_total)
        assert acc >= THRESHOLD_TOTAL_AMOUNT, (
            f"total_amount accuracy {acc:.1%} below threshold {THRESHOLD_TOTAL_AMOUNT:.0%}"
        )

    if clean_tax:
        acc = sum(clean_tax) / len(clean_tax)
        assert acc >= THRESHOLD_TAX_AMOUNT, (
            f"tax_amount accuracy {acc:.1%} below threshold {THRESHOLD_TAX_AMOUNT:.0%}"
        )

    if all_fields:
        acc = sum(all_fields) / len(all_fields)
        assert acc >= THRESHOLD_OVERALL, (
            f"overall accuracy {acc:.1%} below threshold {THRESHOLD_OVERALL:.0%}"
        )
