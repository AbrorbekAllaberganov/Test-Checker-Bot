"""
app/services/students.py — O'quvchi CRUD servisi.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.student import Student


async def add_students(
    db: AsyncSession,
    group_id: int,
    full_names: list[str],
) -> list[Student]:
    """Bir nechta o'quvchini guruhga qo'shish."""
    students: list[Student] = []
    for name in full_names:
        name = name.strip()
        if not name:
            continue
        student = Student(group_id=group_id, full_name=name)
        db.add(student)
        students.append(student)

    await db.flush()
    for s in students:
        await db.refresh(s)
    return students


async def get_students_by_group(
    db: AsyncSession, group_id: int
) -> list[Student]:
    """Guruhdagi barcha o'quvchilarni olish."""
    result = await db.execute(
        select(Student)
        .where(Student.group_id == group_id)
        .order_by(Student.full_name)
    )
    return list(result.scalars().all())


async def get_student(db: AsyncSession, student_id: int) -> Optional[Student]:
    result = await db.execute(select(Student).where(Student.id == student_id))
    return result.scalar_one_or_none()


async def delete_student(db: AsyncSession, student_id: int) -> bool:
    student = await get_student(db, student_id)
    if student is None:
        return False
    await db.delete(student)
    await db.flush()
    return True


async def link_telegram(
    db: AsyncSession, student_id: int, telegram_id: int
) -> Optional[Student]:
    """O'quvchiga Telegram ID biriktirish."""
    student = await get_student(db, student_id)
    if student is None:
        return None
    student.telegram_id = telegram_id
    await db.flush()
    return student
