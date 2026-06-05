"""
app/services/history.py — Natijalar va tarix servislar.

Docs/02 §natijalar tarixi — SQL query'lar SQLAlchemy ORM bilan.
"""
from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.attempt import Attempt
from app.models.student import Student
from app.models.test import Test
from app.models.titul import Titul

log = logging.getLogger(__name__)


@dataclass
class StudentHistoryItem:
    test_title: str
    score: Optional[int]
    total: Optional[int]
    percent: Optional[float]
    needs_review: bool
    created_at: datetime


@dataclass
class TestResultItem:
    student_name: str
    student_id: int
    score: Optional[int]
    total: Optional[int]
    percent: Optional[float]
    needs_review: bool
    attempt_id: Optional[int]
    created_at: Optional[datetime]


async def student_history(
    db: AsyncSession,
    student_id: int,
    limit: int = 50,
) -> list[StudentHistoryItem]:
    """
    O'quvchi barcha urinishlar tarixi (yangi → eski).

    Docs/02 SQL so'roviga mos.
    """
    stmt = (
        select(
            Test.title,
            Attempt.score,
            Attempt.total,
            Attempt.percent,
            Attempt.needs_review,
            Attempt.created_at,
        )
        .join(Titul, Titul.id == Attempt.titul_id)
        .join(Test, Test.id == Titul.test_id)
        .where(Titul.student_id == student_id)
        .order_by(Attempt.created_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [
        StudentHistoryItem(
            test_title=r[0],
            score=r[1],
            total=r[2],
            percent=float(r[3]) if r[3] is not None else None,
            needs_review=r[4],
            created_at=r[5],
        )
        for r in rows
    ]


async def test_results(
    db: AsyncSession,
    test_id: int,
) -> list[TestResultItem]:
    """
    Testdagi barcha o'quvchilar natijasi (eng oxirgi urinish).
    """
    # Har student uchun eng so'nggi attempt ID
    latest_subq = (
        select(
            Attempt.id,
            func.row_number()
            .over(
                partition_by=Titul.student_id,
                order_by=Attempt.created_at.desc(),
            )
            .label("rn"),
        )
        .join(Titul, Titul.id == Attempt.titul_id)
        .where(Titul.test_id == test_id, Attempt.status == "done")
        .subquery()
    )

    stmt = (
        select(
            Student.full_name,
            Student.id,
            Attempt.score,
            Attempt.total,
            Attempt.percent,
            Attempt.needs_review,
            Attempt.id,
            Attempt.created_at,
        )
        .join(Titul, Titul.student_id == Student.id)
        .join(Attempt, Attempt.titul_id == Titul.id)
        .join(latest_subq, latest_subq.c.id == Attempt.id)
        .where(
            Titul.test_id == test_id,
            latest_subq.c.rn == 1,
        )
        .order_by(Attempt.percent.desc().nullslast())
    )

    rows = (await db.execute(stmt)).all()
    return [
        TestResultItem(
            student_name=r[0],
            student_id=r[1],
            score=r[2],
            total=r[3],
            percent=float(r[4]) if r[4] is not None else None,
            needs_review=r[5],
            attempt_id=r[6],
            created_at=r[7],
        )
        for r in rows
    ]


async def test_stats(db: AsyncSession, test_id: int) -> dict:
    """Test uchun umumiy statistika."""
    results = await test_results(db, test_id)
    if not results:
        return {"count": 0, "avg_percent": None, "max_percent": None}

    percents = [r.percent for r in results if r.percent is not None]
    return {
        "count": len(results),
        "avg_percent": round(sum(percents) / len(percents), 2) if percents else None,
        "max_percent": max(percents) if percents else None,
    }


def results_to_csv(results: list[TestResultItem], test_title: str) -> bytes:
    """Natijalarni CSV ga eksport qilish."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["#", "F.I.Sh", "To'g'ri", "Jami", "%", "Ko'rish kerak", "Sana"])

    for i, r in enumerate(results, 1):
        writer.writerow([
            i,
            r.student_name,
            r.score,
            r.total,
            r.percent,
            "Ha" if r.needs_review else "",
            r.created_at.strftime("%d.%m.%Y %H:%M") if r.created_at else "",
        ])

    return buf.getvalue().encode("utf-8-sig")  # Excel uchun BOM
