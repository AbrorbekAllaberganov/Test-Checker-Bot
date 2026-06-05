"""
app/api/routes/web_api.py — FastAPI endpoints for the Web UI Dashboard.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy import func, select, distinct
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_db
from app.models.group import Group
from app.models.test import Test
from app.models.student import Student
from app.models.attempt import Attempt
from app.models.titul import Titul
from app.services import history as history_svc
from app.services.grading import grade

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/web",
    tags=["web-ui"],
)


def map_file_to_url(filepath: Optional[str], route_prefix: str) -> Optional[str]:
    """Lokal fayl yo'lini static url yo'liga aylantiradi."""
    if not filepath:
        return None
    try:
        path_obj = Path(filepath)
        return f"{route_prefix}/{path_obj.name}"
    except Exception:
        return None


@router.get("/dashboard-stats")
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Umumiy tizim statistikasi."""
    groups_count = (await db.execute(select(func.count(Group.id)))).scalar() or 0
    tests_count = (await db.execute(select(func.count(Test.id)))).scalar() or 0
    students_count = (await db.execute(select(func.count(Student.id)))).scalar() or 0
    attempts_count = (await db.execute(select(func.count(Attempt.id)))).scalar() or 0

    # Bugungi urinishlar (kun boshi)
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    scans_today = (await db.execute(
        select(func.count(Attempt.id)).where(Attempt.created_at >= today_start)
    )).scalar() or 0

    # Barcha topshirilgan testlar bo'yicha o'rtacha foiz
    avg_percent = (await db.execute(
        select(func.avg(Attempt.percent)).where(Attempt.status == "done")
    )).scalar()
    avg_percent = round(float(avg_percent), 2) if avg_percent is not None else 0.0

    # Tekshirish kerak bo'lganlar soni
    needs_review_count = (await db.execute(
        select(func.count(Attempt.id)).where(Attempt.needs_review == True, Attempt.status == "done")
    )).scalar() or 0

    return {
        "groups_count": groups_count,
        "tests_count": tests_count,
        "students_count": students_count,
        "attempts_count": attempts_count,
        "scans_today": scans_today,
        "avg_percent": avg_percent,
        "needs_review_count": needs_review_count,
    }


@router.get("/groups")
async def get_groups(db: AsyncSession = Depends(get_db)):
    """Guruhlar ro'yxati va ulardagi o'quvchilar/testlar soni."""
    stmt = (
        select(Group)
        .options(
            selectinload(Group.students),
            selectinload(Group.tests)
        )
        .order_by(Group.created_at.desc())
    )
    result = await db.execute(stmt)
    groups = result.scalars().all()

    return [
        {
            "id": g.id,
            "name": g.name,
            "created_at": g.created_at.strftime("%d.%m.%Y %H:%M"),
            "students_count": len(g.students),
            "tests_count": len(g.tests),
        }
        for g in groups
    ]


@router.get("/groups/{group_id}")
async def get_group_details(group_id: int, db: AsyncSession = Depends(get_db)):
    """Guruh tafsilotlari, o'quvchilar va testlar ro'yxati."""
    stmt = (
        select(Group)
        .options(
            selectinload(Group.students),
            selectinload(Group.tests)
        )
        .where(Group.id == group_id)
    )
    result = await db.execute(stmt)
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Guruh topilmadi")

    return {
        "id": group.id,
        "name": group.name,
        "created_at": group.created_at.strftime("%d.%m.%Y %H:%M"),
        "students": [
            {
                "id": s.id,
                "full_name": s.full_name,
                "telegram_id": s.telegram_id,
                "created_at": s.created_at.strftime("%d.%m.%Y %H:%M"),
            }
            for s in group.students
        ],
        "tests": [
            {
                "id": t.id,
                "title": t.title,
                "question_count": t.question_count,
                "variant_count": t.variant_count,
                "created_at": t.created_at.strftime("%d.%m.%Y %H:%M"),
            }
            for t in group.tests
        ]
    }


@router.get("/tests/{test_id}")
async def get_test_details(test_id: int, db: AsyncSession = Depends(get_db)):
    """Test tafsilotlari, natijalar va savollar analitikasi (Item Analysis)."""
    stmt = (
        select(Test)
        .options(selectinload(Test.group))
        .where(Test.id == test_id)
    )
    result = await db.execute(stmt)
    test = result.scalar_one_or_none()
    if not test:
        raise HTTPException(status_code=404, detail="Test topilmadi")

    results = await history_svc.test_results(db, test_id)
    stats = await history_svc.test_stats(db, test_id)

    # Savollar tahlili (Item Analysis) uchun urinishlarni olish
    attempts_stmt = (
        select(Attempt)
        .join(Titul, Titul.id == Attempt.titul_id)
        .where(Titul.test_id == test_id, Attempt.status == "done")
    )
    attempts_res = await db.execute(attempts_stmt)
    attempts = attempts_res.scalars().all()

    # Tahlil lug'atini tayyorlash
    item_analysis = {}
    for i in range(1, test.question_count + 1):
        q_str = str(i)
        item_analysis[q_str] = {
            "question": q_str,
            "correct_count": 0,
            "incorrect_count": 0,
            "unmarked_count": 0,
            "correct_percent": 0.0
        }

    total_attempts = len(attempts)
    for att in attempts:
        detail = att.detail or {}
        for q_str in item_analysis.keys():
            q_info = detail.get(q_str, {})
            got = q_info.get("got")
            ok = q_info.get("ok")

            if got is None:
                item_analysis[q_str]["unmarked_count"] += 1
            elif ok:
                item_analysis[q_str]["correct_count"] += 1
            else:
                item_analysis[q_str]["incorrect_count"] += 1

    # Foizlarni hisoblash
    if total_attempts > 0:
        for q_str in item_analysis.keys():
            corrects = item_analysis[q_str]["correct_count"]
            item_analysis[q_str]["correct_percent"] = round(100 * corrects / total_attempts, 2)

    # Natijalarni formatlash
    formatted_results = []
    for r in results:
        formatted_results.append({
            "student_name": r.student_name,
            "student_id": r.student_id,
            "score": r.score,
            "total": r.total,
            "percent": r.percent,
            "needs_review": r.needs_review,
            "attempt_id": r.attempt_id,
            "created_at": r.created_at.strftime("%d.%m.%Y %H:%M") if r.created_at else None,
        })

    return {
        "id": test.id,
        "title": test.title,
        "question_count": test.question_count,
        "variant_count": test.variant_count,
        "answer_key": test.answer_key,
        "group_name": test.group.name if test.group else "Noma'lum guruh",
        "stats": stats,
        "results": formatted_results,
        "item_analysis": list(item_analysis.values()),
        "total_attempts": total_attempts
    }


@router.get("/students/{student_id}")
async def get_student_details(student_id: int, db: AsyncSession = Depends(get_db)):
    """O'quvchi profili va barcha testlardagi urinishlar tarixi."""
    stmt = (
        select(Student)
        .options(selectinload(Student.group))
        .where(Student.id == student_id)
    )
    result = await db.execute(stmt)
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="O'quvchi topilmadi")

    # Urinishlar ro'yxati
    attempts_stmt = (
        select(
            Attempt.id,
            Test.title,
            Attempt.score,
            Attempt.total,
            Attempt.percent,
            Attempt.needs_review,
            Attempt.created_at
        )
        .join(Titul, Titul.id == Attempt.titul_id)
        .join(Test, Test.id == Titul.test_id)
        .where(Titul.student_id == student_id)
        .order_by(Attempt.created_at.desc())
    )
    attempts_res = await db.execute(attempts_stmt)
    attempts_rows = attempts_res.all()

    return {
        "id": student.id,
        "full_name": student.full_name,
        "telegram_id": student.telegram_id,
        "group_name": student.group.name if student.group else "Noma'lum guruh",
        "history": [
            {
                "attempt_id": r[0],
                "test_title": r[1],
                "score": r[2],
                "total": r[3],
                "percent": float(r[4]) if r[4] is not None else 0.0,
                "needs_review": r[5],
                "date": r[6].strftime("%d.%m.%Y %H:%M"),
            }
            for r in attempts_rows
        ]
    }


@router.get("/attempts/{attempt_id}")
async def get_attempt_details(attempt_id: int, db: AsyncSession = Depends(get_db)):
    """Urinish natijasi va review uchun ma'lumotlar."""
    stmt = (
        select(Attempt)
        .options(
            selectinload(Attempt.titul).selectinload(Titul.student),
            selectinload(Attempt.titul).selectinload(Titul.test)
        )
        .where(Attempt.id == attempt_id)
    )
    result = await db.execute(stmt)
    attempt = result.scalar_one_or_none()
    if not attempt:
        raise HTTPException(status_code=404, detail="Urinish topilmadi")

    # Lokal yo'llarni vebga moslash
    source_url = map_file_to_url(attempt.source_file, "/static/uploads")
    debug_url = map_file_to_url(attempt.debug_file, "/static/debug")

    student_name = "Noma'lum"
    test_title = "Noma'lum"
    answer_key = {}
    variant_count = 4

    if attempt.titul:
        if attempt.titul.student:
            student_name = attempt.titul.student.full_name
        if attempt.titul.test:
            test_title = attempt.titul.test.title
            answer_key = attempt.titul.test.answer_key
            variant_count = attempt.titul.test.variant_count

    question_count = 0
    if attempt.titul and attempt.titul.test:
        question_count = attempt.titul.test.question_count or 0
    # Fallback: detected javoblar sonidan aniqlash
    if not question_count and attempt.detected:
        question_count = len(attempt.detected)

    return {
        "id": attempt.id,
        "status": attempt.status,
        "score": attempt.score,
        "total": attempt.total,
        "question_count": question_count,   # <-- savol soni (total != question_count)
        "percent": float(attempt.percent) if attempt.percent is not None else None,
        "needs_review": attempt.needs_review,
        "created_at": attempt.created_at.strftime("%d.%m.%Y %H:%M"),
        "detected": attempt.detected,
        "detail": attempt.detail,
        "error_msg": attempt.error_msg,
        "source_url": source_url,
        "debug_url": debug_url,
        "student_name": student_name,
        "test_title": test_title,
        "answer_key": answer_key,
        "variant_count": variant_count,
    }


@router.post("/attempts/{attempt_id}/review")
async def review_attempt(
    attempt_id: int,
    corrected_answers: dict[str, Optional[str]] = Body(..., embed=True),
    db: AsyncSession = Depends(get_db)
):
    """Ustoz tomonidan belgilarni qo'lda to'g'rilash va ballarni qayta hisoblash."""
    stmt = (
        select(Attempt)
        .options(selectinload(Attempt.titul).selectinload(Titul.test))
        .where(Attempt.id == attempt_id)
    )
    result = await db.execute(stmt)
    attempt = result.scalar_one_or_none()
    if not attempt:
        raise HTTPException(status_code=404, detail="Urinish topilmadi")

    if not attempt.titul or not attempt.titul.test:
        raise HTTPException(status_code=400, detail="Urinish testga ulanmagan")

    test = attempt.titul.test

    # Yangi kiritilgan javoblar bo'yicha qayta baholash
    gr = grade(corrected_answers, test.answer_key)

    # Attempt ma'lumotlarini yangilash
    attempt.detected = {k: v for k, v in corrected_answers.items()}
    attempt.score = gr.score
    attempt.total = gr.total
    attempt.percent = gr.percent
    attempt.detail = gr.detail
    attempt.needs_review = False  # Ustoz tekshirdi
    attempt.status = "done"

    await db.commit()
    await db.refresh(attempt)

    return {
        "success": True,
        "score": attempt.score,
        "total": attempt.total,
        "percent": attempt.percent,
        "needs_review": attempt.needs_review,
        "detected": attempt.detected,
        "detail": attempt.detail,
    }
