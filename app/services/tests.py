"""
app/services/tests.py — Test CRUD + kalit parse servisi.

Docs/05 §2 — Kalit parse (ikkala format):
  Format 1: "ABCDABCD..." — ketma-ket harflar (probel/qator/vergul ajratar)
  Format 2: "1 A", "2-C", "3:B" — nomerlangan
"""
from __future__ import annotations

import re
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.test import Test

# Ruxsat etilgan javob harflari
VALID_OPTIONS = set("ABCDE")


def parse_key(
    text: str,
    qcount: int,
    options: Optional[list[str]] = None,
) -> dict[str, str]:
    """
    Kalit matnini parse qilib {"1":"A", "2":"B", ...} formatga aylantiradi.

    Docs/05 ikkala formatni qo'llab-quvvatlaydi.

    Args:
        text:    Foydalanuvchi kiritgan matn.
        qcount:  Savol soni (tekshirish uchun).
        options: Ruxsat etilgan harflar (None = A-E).

    Returns:
        {str: str} — 1-based string kalitlar.

    Raises:
        ValueError: Format noto'g'ri yoki uzunlik mos kelmasa.
    """
    allowed = set(options or list("ABCDE"))
    result: dict[str, str] = {}

    text = text.strip()

    # Format 2 sinash: "1 A", "2-C", "3:B", "10. D" kabi
    numbered_pattern = re.compile(
        r"(\d+)\s*[-.:)\s]\s*([A-Ea-e])\b",
        re.IGNORECASE,
    )
    numbered_matches = numbered_pattern.findall(text)

    if numbered_matches:
        # Format 2 — nomerlangan
        for num_str, letter in numbered_matches:
            num = int(num_str)
            letter = letter.upper()
            if letter not in allowed:
                raise ValueError(
                    f"Noto'g'ri javob harfi: {letter!r}. "
                    f"Ruxsat etilganlar: {sorted(allowed)}"
                )
            result[str(num)] = letter
    else:
        # Format 1 — ketma-ket harflar (probel/qator/vergul ajratadi yoki yo'q)
        cleaned = re.sub(r"[\s,]+", "", text).upper()
        letters = list(cleaned)

        if not all(c in allowed for c in letters):
            bad = [c for c in letters if c not in allowed]
            raise ValueError(
                f"Noto'g'ri belgilar: {bad}. Ruxsat: {sorted(allowed)}"
            )

        result = {str(i + 1): letters[i] for i in range(len(letters))}

    # Uzunlik tekshiruvi
    if len(result) != qcount:
        raise ValueError(
            f"Javoblar soni {len(result)} ta, {qcount} ta bo'lishi kerak."
        )

    # Raqamlar 1..qcount bo'lishini tekshirish
    expected_keys = {str(i) for i in range(1, qcount + 1)}
    if set(result.keys()) != expected_keys:
        missing = expected_keys - set(result.keys())
        raise ValueError(f"Quyidagi savol raqamlari yetishmaydi: {sorted(missing)}")

    return result


async def create_test(
    db: AsyncSession,
    group_id: int,
    title: str,
    question_count: int,
    variant_count: int,
    answer_key: dict[str, str],
) -> Test:
    test = Test(
        group_id=group_id,
        title=title,
        question_count=question_count,
        variant_count=variant_count,
        answer_key=answer_key,
    )
    db.add(test)
    await db.flush()
    await db.refresh(test)
    return test


async def get_tests_by_group(db: AsyncSession, group_id: int) -> list[Test]:
    result = await db.execute(
        select(Test)
        .where(Test.group_id == group_id)
        .order_by(Test.created_at.desc())
    )
    return list(result.scalars().all())


async def get_test(db: AsyncSession, test_id: int) -> Optional[Test]:
    result = await db.execute(select(Test).where(Test.id == test_id))
    return result.scalar_one_or_none()


async def update_test(
    db: AsyncSession,
    test_id: int,
    title: Optional[str] = None,
    answer_key: Optional[dict[str, str]] = None,
) -> Optional[Test]:
    test = await get_test(db, test_id)
    if test is None:
        return None
    if title is not None:
        test.title = title
    if answer_key is not None:
        test.answer_key = answer_key
    await db.flush()
    return test
