"""
app/services/access.py — Egalik (tenant) tekshiruvlari.

Bot handlerlari ham, Mini App API'si ham shu funksiyalar orqali obyektni
oladi. Har biri obyektni FAQAT egasi (guruh `owner_id` si) uchun qaytaradi,
aks holda `None` — chaqiruvchi buni "topilmadi" deb ko'rsatadi (403 emas:
obyekt mavjudligini ham oshkor qilmaymiz).

Nima uchun alohida modul: egalik zanjiri hamma joyda bir xil
(Attempt → Titul → Test → Group.owner_id), lekin uni har handlerda qo'lda
yozish unutilib qolishga olib keladi — aynan shu sababli IDOR paydo bo'lgan
edi. Bitta joyda to'g'ri yozilgan zanjir + majburiy `owner_id` parametri.

Egalik zanjiri:
    Group    → Group.owner_id
    Test     → Test.group_id → Group.owner_id
    Student  → Student.group_id → Group.owner_id
    Titul    → Titul.test_id → Test → Group.owner_id
    Attempt  → Attempt.titul_id → Titul → Test → Group.owner_id

`Attempt.titul_id` NULL bo'lishi mumkin (QR hali o'qilmagan pending skan).
Bunday skan hech kimga "tegishli" emas — `owned_attempt` uni qaytarmaydi.
Mini App ro'yxatlari ham ularni ko'rsatmaydi (INNER JOIN Titul), shu
sababli foydalanuvchi ularga havola ham olmaydi.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Optional

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.base import ExecutableOption

from app.models.attempt import Attempt
from app.models.group import Group
from app.models.student import Student
from app.models.test import Test
from app.models.titul import Titul


def _apply_options(stmt: Select, options: Sequence[ExecutableOption]) -> Select:
    return stmt.options(*options) if options else stmt


async def owned_group(
    db: AsyncSession,
    group_id: int,
    owner_id: int,
    *,
    options: Sequence[ExecutableOption] = (),
) -> Optional[Group]:
    """Guruhni faqat egasi uchun qaytaradi."""
    stmt = select(Group).where(Group.id == group_id, Group.owner_id == owner_id)
    return (await db.execute(_apply_options(stmt, options))).scalar_one_or_none()


async def owned_test(
    db: AsyncSession,
    test_id: int,
    owner_id: int,
    *,
    options: Sequence[ExecutableOption] = (),
) -> Optional[Test]:
    """Testni faqat guruh egasi uchun qaytaradi (`Test.group` yuklangan)."""
    stmt = (
        select(Test)
        .join(Group, Group.id == Test.group_id)
        .where(Test.id == test_id, Group.owner_id == owner_id)
        .options(selectinload(Test.group))
    )
    return (await db.execute(_apply_options(stmt, options))).scalar_one_or_none()


async def owned_student(
    db: AsyncSession,
    student_id: int,
    owner_id: int,
    *,
    options: Sequence[ExecutableOption] = (),
) -> Optional[Student]:
    """O'quvchini faqat guruh egasi uchun qaytaradi (`Student.group` yuklangan)."""
    stmt = (
        select(Student)
        .join(Group, Group.id == Student.group_id)
        .where(Student.id == student_id, Group.owner_id == owner_id)
        .options(selectinload(Student.group))
    )
    return (await db.execute(_apply_options(stmt, options))).scalar_one_or_none()


async def owned_titul(
    db: AsyncSession,
    titul_id: int,
    owner_id: int,
) -> Optional[Titul]:
    """Titulni faqat test egasi uchun qaytaradi (`test`, `student` yuklangan)."""
    stmt = (
        select(Titul)
        .join(Test, Test.id == Titul.test_id)
        .join(Group, Group.id == Test.group_id)
        .where(Titul.id == titul_id, Group.owner_id == owner_id)
        .options(selectinload(Titul.test), selectinload(Titul.student))
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def owned_attempt(
    db: AsyncSession,
    attempt_id: int,
    owner_id: int,
) -> Optional[Attempt]:
    """
    Urinishni faqat test egasi uchun qaytaradi.

    `titul`, `titul.student`, `titul.test`, `titul.test.group` yuklangan —
    chaqiruvchi relationship'larga tegishi mumkin (async'da lazy-load yo'q).
    `titul_id` NULL bo'lgan pending skanlar hech kimga qaytarilmaydi.
    """
    stmt = (
        select(Attempt)
        .join(Titul, Titul.id == Attempt.titul_id)
        .join(Test, Test.id == Titul.test_id)
        .join(Group, Group.id == Test.group_id)
        .where(Attempt.id == attempt_id, Group.owner_id == owner_id)
        .options(
            selectinload(Attempt.titul).selectinload(Titul.student),
            selectinload(Attempt.titul)
            .selectinload(Titul.test)
            .selectinload(Test.group),
        )
    )
    return (await db.execute(stmt)).scalar_one_or_none()


# ── So'rov bloklari (ro'yxat/hisob so'rovlari uchun) ────────────────────


def owner_filter_for_tests(stmt: Select, owner_id: int) -> Select:
    """`select(Test...)` so'roviga guruh egasi bo'yicha filtr qo'shadi."""
    return stmt.join(Group, Group.id == Test.group_id).where(Group.owner_id == owner_id)


def owner_filter_for_students(stmt: Select, owner_id: int) -> Select:
    """`select(Student...)` so'roviga guruh egasi bo'yicha filtr qo'shadi."""
    return stmt.join(Group, Group.id == Student.group_id).where(Group.owner_id == owner_id)


def owner_filter_for_attempts(stmt: Select, owner_id: int) -> Select:
    """
    `select(...).select_from(Attempt)` so'roviga to'liq zanjir bo'yicha filtr.

    INNER JOIN — `titul_id` NULL skanlar chiqib ketadi; bu ataylab: ular
    hali hech kimga tegishli emas.
    """
    return (
        stmt.join(Titul, Titul.id == Attempt.titul_id)
        .join(Test, Test.id == Titul.test_id)
        .join(Group, Group.id == Test.group_id)
        .where(Group.owner_id == owner_id)
    )
