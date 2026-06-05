"""
app/tests/test_key_parse.py — Kalit parse testlari.
"""
from __future__ import annotations

import pytest

from app.services.tests import parse_key


class TestParseKeyFormat1:
    """Format 1: ketma-ket harflar."""

    def test_basic_40(self):
        text = "A" * 40
        key = parse_key(text, 40)
        assert len(key) == 40
        assert all(v == "A" for v in key.values())
        assert key["1"] == "A"
        assert key["40"] == "A"

    def test_with_spaces(self):
        text = "ABCD " * 10
        key = parse_key(text, 40)
        assert len(key) == 40

    def test_with_newlines(self):
        text = "\n".join(["ABCD"] * 10)
        key = parse_key(text, 40)
        assert len(key) == 40

    def test_mixed_case(self):
        text = "abcd" * 10
        key = parse_key(text, 40)
        assert all(v.isupper() for v in key.values())

    def test_wrong_length(self):
        with pytest.raises(ValueError, match="40"):
            parse_key("ABCD", 40)

    def test_invalid_char(self):
        with pytest.raises(ValueError):
            parse_key("ABCZ" * 10, 40)


class TestParseKeyFormat2:
    """Format 2: nomerlangan."""

    def test_numbered_dash(self):
        lines = [f"{i}-{chr(64 + (i % 4) + 1)}" for i in range(1, 41)]
        text = "\n".join(lines)
        key = parse_key(text, 40)
        assert len(key) == 40

    def test_numbered_space(self):
        lines = [f"{i} A" for i in range(1, 41)]
        text = "\n".join(lines)
        key = parse_key(text, 40)
        assert all(v == "A" for v in key.values())

    def test_numbered_colon(self):
        lines = [f"{i}:B" for i in range(1, 41)]
        text = "\n".join(lines)
        key = parse_key(text, 40)
        assert all(v == "B" for v in key.values())

    def test_numbered_dot(self):
        lines = [f"{i}. C" for i in range(1, 41)]
        text = "\n".join(lines)
        key = parse_key(text, 40)
        assert all(v == "C" for v in key.values())

    def test_wrong_count(self):
        lines = [f"{i}-A" for i in range(1, 20)]  # 19 ta
        text = "\n".join(lines)
        with pytest.raises(ValueError):
            parse_key(text, 40)


class TestParseKeyVariants:
    def test_5_options(self):
        text = "ABCDE" * 10
        key = parse_key(text, 50, options=list("ABCDE"))
        assert len(key) == 50

    def test_90(self):
        text = "ABCD" * 22 + "AB"  # 90 ta
        key = parse_key(text, 90)
        assert len(key) == 90
