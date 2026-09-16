"""
app/tests/test_excel.py — Excel/CSV eksport yordamchilarining sof testlari.

`export_*` funksiyalari bazani talab qiladi; bu yerda faqat formula
injection (weaknesses №17) va fayl nomi sanitizatsiyasi tekshiriladi.
"""
from __future__ import annotations

import csv
import io

import pytest

from app.services.excel import safe_cell, safe_filename
from app.services.history import TestResultItem, results_to_csv


class TestSafeCell:
    @pytest.mark.parametrize("prefix", ["=", "+", "-", "@", "\t", "\r"])
    def test_dangerous_prefix_is_neutralised(self, prefix):
        value = f"{prefix}HYPERLINK(\"http://evil\")"
        out = safe_cell(value)
        assert out.startswith("'")
        assert out[1:] == value

    def test_plain_text_unchanged(self):
        assert safe_cell("Ali Valiyev") == "Ali Valiyev"
        assert safe_cell("O'ktam") == "O'ktam"

    def test_non_str_unchanged(self):
        assert safe_cell(42) == 42
        assert safe_cell(3.5) == 3.5
        assert safe_cell(None) is None

    def test_empty_string(self):
        assert safe_cell("") == ""


class TestSafeFilename:
    def test_spaces_and_apostrophes(self):
        assert safe_filename("Ali Valiyev O'g'li") == "Ali_Valiyev_O_g_li"

    def test_path_separators_and_quotes_removed(self):
        out = safe_filename('../../etc/"passwd"')
        assert "/" not in out
        assert "\\" not in out
        assert '"' not in out
        assert ".." not in out

    def test_fallback_when_empty(self):
        assert safe_filename("") == "fayl"
        assert safe_filename("///") == "fayl"
        assert safe_filename(None, fallback="x") == "x"

    def test_length_capped(self):
        assert len(safe_filename("a" * 500)) <= 60

    def test_unicode_kept(self):
        # Kirill/lotin harflari `\w` ga kiradi — o'chirilmaydi.
        assert safe_filename("Гуруҳ 5") == "Гуруҳ_5"


class TestCsvExport:
    def test_csv_student_name_is_neutralised(self):
        item = TestResultItem(
            student_name="=cmd|' /C calc'!A0",
            student_id=1,
            score=1,
            total=2,
            percent=50.0,
            needs_review=False,
            attempt_id=1,
            created_at=None,
        )
        raw = results_to_csv([item], "T").decode("utf-8-sig")
        rows = list(csv.reader(io.StringIO(raw)))
        assert rows[1][1].startswith("'=")
