"""
app/tests/test_omr_regression.py — OMR regression testi skeleti.

Agar fixtures/sample_scan_40.jpg va fixtures/expected_40.json mavjud bo'lsa,
pipeline ni ishlatib natijani solishtiради.
Fixture yo'q bo'lsa — skip qilinadi.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_40 = FIXTURES_DIR / "sample_scan_40.jpg"
EXPECTED_40 = FIXTURES_DIR / "expected_40.json"


@pytest.mark.skipif(
    not SAMPLE_40.exists() or not EXPECTED_40.exists(),
    reason="OMR regression fixture mavjud emas",
)
def test_omr_pipeline_40():
    """
    40 ta savollik namuna skan bilan regression testi.

    Tekshirish:
    1. Pipeline xatoliksiz ishlasin
    2. QR o'qilsin
    3. Aniqlangan javoblar kutilganga mos kelsin (>= 95%)
    """
    from app.omr.pipeline import run

    results = run(
        str(SAMPLE_40),
        fill_min=0.35,
        fill_margin=0.15,
        omr_debug=False,
        qcount=40,
    )

    assert results, "Pipeline natija qaytarmadi"
    res = results[0]
    assert res.error is None, f"Pipeline xatosi: {res.error}"
    assert res.titul_uuid is not None, "QR topilmadi"

    with open(EXPECTED_40) as f:
        expected = json.load(f)

    # Kamida 95% mos kelish
    total = len(expected)
    correct = sum(
        1 for q, ans in expected.items()
        if res.detected.get(q) == ans
    )
    accuracy = correct / total if total > 0 else 0

    assert accuracy >= 0.95, (
        f"OMR aniqlik past: {correct}/{total} ({accuracy:.1%}). "
        "LAYOUTS_MM ni kalibrlash kerak."
    )
