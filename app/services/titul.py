"""
app/services/titul.py — Titul (varaq) yaratish va PDF generatsiya.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.titul import Titul
from app.models.student import Student
from app.models.test import Test

log = logging.getLogger(__name__)


async def get_or_create_titul(
    db: AsyncSession,
    test_id: int,
    student_id: int,
) -> Titul:
    """Test + student uchun titul olish yoki yaratish."""
    result = await db.execute(
        select(Titul).where(
            Titul.test_id == test_id,
            Titul.student_id == student_id,
        )
    )
    titul = result.scalar_one_or_none()
    if titul is None:
        titul = Titul(test_id=test_id, student_id=student_id)
        db.add(titul)
        await db.flush()
        await db.refresh(titul)
    return titul


async def get_titul_by_uuid(
    db: AsyncSession, titul_uuid: str
) -> Optional[Titul]:
    """UUID bo'yicha titulni topish (QR dan keyin)."""
    try:
        parsed_uuid = uuid.UUID(titul_uuid)
    except (ValueError, AttributeError):
        return None

    result = await db.execute(
        select(Titul)
        .where(Titul.uuid == parsed_uuid)
        .options(
            selectinload(Titul.test),
            selectinload(Titul.student),
        )
    )
    return result.scalar_one_or_none()


async def get_tituls_by_test(db: AsyncSession, test_id: int) -> list[Titul]:
    result = await db.execute(
        select(Titul)
        .where(Titul.test_id == test_id)
        .options(selectinload(Titul.student))
        .order_by(Titul.id)
    )
    return list(result.scalars().all())


async def update_pdf_path(
    db: AsyncSession, titul_id: int, pdf_path: str
) -> None:
    """PDF yaratilgandan keyin yo'lini yangilash."""
    result = await db.execute(select(Titul).where(Titul.id == titul_id))
    titul = result.scalar_one_or_none()
    if titul:
        titul.pdf_path = pdf_path
        await db.flush()


async def generate_tituls_for_test(
    db: AsyncSession,
    test_id: int,
) -> list[int]:
    """
    Test uchun barcha studentlar uchun titul (DB yozuvi) yaratadi.
    Celery task ID'lari qaytaradi.

    Returns:
        Yaratilgan yoki mavjud titul ID'lari ro'yxati.
    """
    from app.services.students import get_students_by_group
    from app.models.test import Test as TestModel

    test_result = await db.execute(select(TestModel).where(TestModel.id == test_id))
    test = test_result.scalar_one_or_none()
    if test is None:
        raise ValueError(f"Test topilmadi: {test_id}")

    students = await get_students_by_group(db, test.group_id)
    if not students:
        raise ValueError("Guruhda o'quvchi yo'q")

    titul_ids: list[int] = []
    for student in students:
        titul = await get_or_create_titul(db, test_id, student.id)
        titul_ids.append(titul.id)

    return titul_ids
