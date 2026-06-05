"""
app/services/grading.py — Baholash logikasi.

Docs/03 §9 — grade() funksiyasi.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class GradeResult:
    score: int
    total: int
    percent: float
    detail: dict[str, dict]
    needs_review: bool
    correct_count: int = 0
    incorrect_count: int = 0
    unmarked_count: int = 0
    ambiguous_count: int = 0


def grade(
    detected: dict[str, Optional[str]],
    answer_key: dict[str, str],
    bubble_data: Optional[dict[str, dict]] = None,
) -> GradeResult:
    """
    Aniqlangan javoblarni to'g'ri kalit bilan solishtiradi.

    Docs/03 §9 ga aniq mos:
      detail[q] = {"got": got, "key": correct, "ok": bool}

    Args:
        detected:   {"1": "A", "2": None, ...} — pipeline natijasi.
        answer_key: {"1": "A", "2": "C", ...} — ustoz kiritgan kalit.
        bubble_data: OMR dan olingan to'liq ma'lumot (flaglar uchun).

    Returns:
        GradeResult.
    """
    total = len(answer_key)
    detail: dict[str, dict] = {}
    needs_review = False

    correct_count = 0
    incorrect_count = 0
    unmarked_count = 0
    ambiguous_count = 0

    for q_str, correct in answer_key.items():
        got = detected.get(q_str)
        ok = got is not None and got == correct

        flag = None
        if bubble_data and q_str in bubble_data:
            flag = bubble_data[q_str].get("flag")

        if flag == "ambiguous":
            ambiguous_count += 1
            needs_review = True
        elif got is None or flag == "blank":
            unmarked_count += 1
            needs_review = True
        elif ok:
            correct_count += 1
        else:
            incorrect_count += 1

        detail[q_str] = {"got": got, "key": correct, "ok": ok}

    percent = round(100 * correct_count / total, 2) if total > 0 else 0.0

    return GradeResult(
        score=correct_count,
        total=total,
        percent=percent,
        detail=detail,
        needs_review=needs_review,
        correct_count=correct_count,
        incorrect_count=incorrect_count,
        unmarked_count=unmarked_count,
        ambiguous_count=ambiguous_count,
    )


def format_result_message(
    grade_result: GradeResult,
    test_title: str,
    student_name: str,
) -> str:
    """Foydalanuvchiga yuboriladigan natija xabari."""
    lines = [
        f"📄 <b>Test:</b> {test_title}",
        f"👤 <b>O'quvchi:</b> {student_name}\n",
        f"✅ <b>To'g'ri:</b> {grade_result.correct_count}/{grade_result.total} ({grade_result.percent}%)",
        f"❌ <b>Xato:</b> {grade_result.incorrect_count} ta",
        f"⚪️ <b>Belgilanmagan:</b> {grade_result.unmarked_count} ta",
        f"⚠️ <b>Noaniq (ambiguous):</b> {grade_result.ambiguous_count} ta",
    ]
    if grade_result.needs_review:
        lines.append("\n⚠️ <b>Ba'zi belgilar noaniq yoki belgilanmagan, ustoz tekshirsin.</b>")
    return "\n".join(lines)


def get_attempt_breakdown(detail: dict) -> dict[str, list[str]]:
    """
    Tafsilotlar lug'atini statuslar bo'yicha guruhlaydi.
    """
    correct = []
    incorrect = []
    unmarked = []

    for q_str in sorted(detail.keys(), key=lambda x: int(x) if x.isdigit() else 999):
        info = detail[q_str]
        got = info.get("got")
        key = info.get("key")
        
        if got is None:
            unmarked.append(f"{q_str} (kalit: {key})")
        elif info.get("ok"):
            correct.append(f"{q_str}:{got}")
        else:
            incorrect.append(f"{q_str}:{got}(to'g'ri:{key})")

    return {
        "correct": correct,
        "incorrect": incorrect,
        "unmarked": unmarked,
    }


def format_attempt_breakdown(
    detail: dict,
    student_name: str,
    test_title: str,
    score: int,
    total: int,
) -> str:
    """O'quvchi javoblarini to'g'ri/xato/belgilanmagan statuslari bilan chiroyli formatda chiqarish."""
    breakdown = get_attempt_breakdown(detail)
    
    corr_len = len(breakdown["correct"])
    inc_len = len(breakdown["incorrect"])
    unm_len = len(breakdown["unmarked"])

    lines = [
        f"👤 <b>O'quvchi:</b> {student_name}",
        f"📋 <b>Test:</b> {test_title}",
        f"📊 <b>Natija:</b> {score}/{total} ({round(100 * score / total, 1) if total > 0 else 0}%)\n",
    ]

    if corr_len > 0:
        lines.append(f"✅ <b>To'g'ri ({corr_len} ta):</b>")
        lines.append(", ".join(breakdown["correct"]))
    else:
        lines.append("✅ <b>To'g'ri:</b> yo'q")

    lines.append("")

    if inc_len > 0:
        lines.append(f"❌ <b>Xato ({inc_len} ta):</b>")
        lines.append(", ".join(breakdown["incorrect"]))
    else:
        lines.append("❌ <b>Xato:</b> yo'q")

    lines.append("")

    if unm_len > 0:
        lines.append(f"⚪️ <b>Belgilanmagan ({unm_len} ta):</b>")
        lines.append(", ".join(breakdown["unmarked"]))
    else:
        lines.append("⚪️ <b>Belgilanmagan:</b> yo'q")

    return "\n".join(lines)
