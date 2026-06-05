"""
app/tests/test_grade.py — grade() funksiyasi testlari.
"""
from __future__ import annotations

import pytest

from app.services.grading import grade


def _make_key(n: int, opt: str = "A") -> dict:
    return {str(i): opt for i in range(1, n + 1)}


def _make_detected(key: dict, wrong: set[int]) -> dict:
    detected = {}
    for q_str, correct in key.items():
        q = int(q_str)
        if q in wrong:
            # Boshqa harf
            for opt in "ABCD":
                if opt != correct:
                    detected[q_str] = opt
                    break
        else:
            detected[q_str] = correct
    return detected


class TestGrade:
    def test_perfect_score(self):
        key = _make_key(40)
        detected = dict(key)
        result = grade(detected, key)
        assert result.score == 40
        assert result.total == 40
        assert result.percent == 100.0
        assert result.needs_review is False

    def test_zero_score(self):
        key = _make_key(40, "A")
        detected = {str(i): "B" for i in range(1, 41)}
        result = grade(detected, key)
        assert result.score == 0
        assert result.percent == 0.0

    def test_partial_score(self):
        key = _make_key(40)
        wrong = {3, 7, 15, 22, 38}
        detected = _make_detected(key, wrong)
        result = grade(detected, key)
        assert result.score == 35
        assert result.total == 40
        assert abs(result.percent - 87.5) < 0.01

    def test_blank_triggers_review(self):
        key = _make_key(40)
        detected = dict(key)
        detected["5"] = None  # bo'sh
        result = grade(detected, key)
        assert result.needs_review is True
        assert result.score == 39

    def test_detail_format(self):
        key = {"1": "A", "2": "B"}
        detected = {"1": "A", "2": "C"}
        result = grade(detected, key)
        assert result.detail["1"]["ok"] is True
        assert result.detail["2"]["ok"] is False
        assert result.detail["2"]["got"] == "C"
        assert result.detail["2"]["key"] == "B"

    def test_50_questions(self):
        key = _make_key(50)
        detected = _make_detected(key, {10, 20})
        result = grade(detected, key)
        assert result.score == 48
        assert result.total == 50

    def test_90_questions(self):
        key = _make_key(90)
        detected = dict(key)
        result = grade(detected, key)
        assert result.score == 90
