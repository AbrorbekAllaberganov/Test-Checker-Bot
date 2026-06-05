"""
app/tests/conftest.py — Pytest fixtures.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def sample_key_40() -> dict:
    """40 ta to'g'ri javob (test ma'lumoti)."""
    opts = "ABCD"
    return {str(i): opts[(i - 1) % 4] for i in range(1, 41)}


@pytest.fixture
def sample_detected_40(sample_key_40) -> dict:
    """Simulyatsiyalangan aniqlangan javoblar (5 ta noto'g'ri)."""
    detected = dict(sample_key_40)
    wrong_qs = [3, 7, 15, 22, 38]
    for q in wrong_qs:
        correct = sample_key_40[str(q)]
        # Boshqa harfni tanlash
        for opt in "ABCD":
            if opt != correct:
                detected[str(q)] = opt
                break
    return detected
