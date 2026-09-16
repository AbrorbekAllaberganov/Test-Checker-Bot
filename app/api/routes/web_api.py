"""
app/api/routes/web_api.py — Telegram Mini App (dashboard) uchun API.

TENANT IZOLYATSIYASI: har endpoint `user` (initData imzosidan olingan
ustoz) ni oladi va faqat SHU ustozning guruhlari, testlari, o'quvchilari
va skanlarini qaytaradi. Begona obyekt so'ralsa — 404 (403 emas: obyekt
mavjudligini ham oshkor qilmaymiz). Egalik zanjiri
`app/services/access.py` da bitta joyda yozilgan.

Fayllar (skan surati, OMR annotatsiyasi) `/static/*` orqali EMAS, balki
`/attempts/{id}/file/{kind}` orqali beriladi — u ham egalikni tekshiradi.
Statik mount'lar olib tashlangan (weaknesses.md №4).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.routes.auth import get_webapp_user
from app.core.db import get_db
from app.models.attempt import Attempt
from app.models.group import Group
from app.models.student import Student
from app.models.test import Test
from app.models.titul import Titul
from app.models.user import User
from app.services import history as history_svc
from app.services.access import (
    owned_attempt,
    owned_group,
    owned_student,
    owned_test,
    owner_filter_for_attempts,
    owner_filter_for_students,
    owner_filter_for_tests,
)
from app.services.attempt_files import (
    FileKind,
    attempt_file_path,
    file_response_for,
    resolve_attempt_file,
)
from app.services.grading import grade

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/web", tags=["web-ui"])


def _file_url(attempt_id: int, kind: FileKind, filepath: Optional[str]) -> Optional[str]:
    """Fayl mavjud bo'lsa — egalik tekshiruvli endpoint URL'i, aks holda None."""
    if resolve_attempt_file(filepath) is None:
        return None
    return f"/api/web/attempts/{attempt_id}/file/{kind}"


# ─── Dashboard statistikasi ──────────────────────────────────────────────


@router.get("/dashboard-stats")
async def get_dashboard_stats(
    user: User = Depends(get_webapp_user),
    db: AsyncSession = Depends(get_db),
):
    """Faqat joriy ustozning statistikasi (butun tizim emas)."""
    groups_count = (
        await db.execute(
            select(func.count(Group.id)).where(Group.owner_id == user.id)
        )
    ).scalar() or 0

    tests_count = (
        await db.execute(
            owner_filter_for_tests(
                select(func.count(Test.id)).select_from(Test), user.id
            )
        )
    ).scalar() or 0

    students_count = (
        await db.execute(
            owner_filter_for_students(
                select(func.count(Student.id)).select_from(Student), user.id
            )
        )
    ).scalar() or 0

    def _attempts(*columns):
        return owner_filter_for_attempts(
            select(*columns).select_from(Attempt), user.id
        )

    attempts_count = (
        await db.execute(_attempts(func.count(Attempt.id)))
    ).scalar() or 0

    # Bugungi urinishlar (kun boshi). created_at TIMESTAMPTZ — tz-aware
    # qiymat kerak, aks holda asyncpg naive/aware xatosi beradi.
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    scans_today = (
        await db.execute(
            _attempts(func.count(Attempt.id)).where(Attempt.created_at >= today_start)
        )
    ).scalar() or 0

    avg_percent = (
        await db.execute(
            _attempts(func.avg(Attempt.percent)).where(Attempt.status == "done")
        )
    ).scalar()
    avg_percent = round(float(avg_percent), 2) if avg_percent is not None else 0.0

    needs_review_count = (
        await db.execute(
            _attempts(func.count(Attempt.id)).where(
                Attempt.needs_review.is_(True), Attempt.status == "done"
            )
        )
    ).scalar() or 0

    return {
        "groups_count": groups_count,
        "tests_count": tests_count,
        "students_count": students_count,
        "attempts_count": attempts_count,
        "scans_today": scans_today,
        "avg_percent": avg_percent,
        "needs_review_count": needs_review_count,
    }


# ─── Guruhlar ────────────────────────────────────────────────────────────


@router.get("/groups")
async def get_groups(
    user: User = Depends(get_webapp_user),
    db: AsyncSession = Depends(get_db),
):
    """Joriy ustozning guruhlari va ulardagi o'quvchilar/testlar soni."""
    stmt = (
        select(Group)
        .where(Group.owner_id == user.id)
        .options(selectinload(Group.students), selectinload(Group.tests))
        .order_by(Group.created_at.desc())
    )
    groups = (await db.execute(stmt)).scalars().all()

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
async def get_group_details(
    group_id: int,
    user: User = Depends(get_webapp_user),
    db: AsyncSession = Depends(get_db),
):
    """Guruh tafsilotlari — faqat egasi uchun."""
    group = await owned_group(
        db,
        group_id,
        user.id,
        options=(selectinload(Group.students), selectinload(Group.tests)),
    )
    if group is None:
        raise HTTPException(status_code=404, detail="Guruh topilmadi")

    return {
        "id": group.id,
        "name": group.name,
        "created_at": group.created_at.strftime("%d.%m.%Y %H:%M"),
        "students": [
            {
                "id": s.id,
                "full_name": s.full_name,
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
        ],
    }


# ─── Testlar ─────────────────────────────────────────────────────────────


@router.get("/tests/{test_id}")
async def get_test_details(
    test_id: int,
    user: User = Depends(get_webapp_user),
    db: AsyncSession = Depends(get_db),
):
    """Test tafsilotlari, natijalar va savollar tahlili — faqat egasi uchun."""
    test = await owned_test(db, test_id, user.id)
    if test is None:
        raise HTTPException(status_code=404, detail="Test topilmadi")

    # Test egaligi tasdiqlandi — quyidagi so'rovlar test_id bo'yicha
    # cheklangan, qo'shimcha filtr kerak emas.
    results = await history_svc.test_results(db, test_id)
    stats = await history_svc.test_stats(db, test_id)

    attempts = (
        await db.execute(
            select(Attempt)
            .join(Titul, Titul.id == Attempt.titul_id)
            .where(Titul.test_id == test_id, Attempt.status == "done")
        )
    ).scalars().all()

    item_analysis: dict[str, dict] = {}
    for i in range(1, test.question_count + 1):
        q_str = str(i)
        item_analysis[q_str] = {
            "question": q_str,
            "correct_count": 0,
            "incorrect_count": 0,
            "unmarked_count": 0,
            "correct_percent": 0.0,
        }

    total_attempts = len(attempts)
    for att in attempts:
        detail = att.detail or {}
        for q_str in item_analysis:
            q_info = detail.get(q_str, {})
            got = q_info.get("got")
            ok = q_info.get("ok")
            if got is None:
                item_analysis[q_str]["unmarked_count"] += 1
            elif ok:
                item_analysis[q_str]["correct_count"] += 1
            else:
                item_analysis[q_str]["incorrect_count"] += 1

    if total_attempts > 0:
        for q_str, row in item_analysis.items():
            row["correct_percent"] = round(
                100 * row["correct_count"] / total_attempts, 2
            )

    formatted_results = [
        {
            "student_name": r.student_name,
            "student_id": r.student_id,
            "score": r.score,
            "total": r.total,
            "percent": r.percent,
            "needs_review": r.needs_review,
            "attempt_id": r.attempt_id,
            "created_at": r.created_at.strftime("%d.%m.%Y %H:%M") if r.created_at else None,
        }
        for r in results
    ]

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
        "total_attempts": total_attempts,
    }


# ─── O'quvchilar ─────────────────────────────────────────────────────────


@router.get("/students/{student_id}")
async def get_student_details(
    student_id: int,
    user: User = Depends(get_webapp_user),
    db: AsyncSession = Depends(get_db),
):
    """O'quvchi profili va urinishlar tarixi — faqat guruh egasi uchun."""
    student = await owned_student(db, student_id, user.id)
    if student is None:
        raise HTTPException(status_code=404, detail="O'quvchi topilmadi")

    attempts_rows = (
        await db.execute(
            select(
                Attempt.id,
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
        )
    ).all()

    return {
        "id": student.id,
        "full_name": student.full_name,
        # `telegram_id` ataylab yo'q: o'quvchini botga ulash oqimi hali yo'q
        # (`link_telegram` chaqirilmaydi), shuning uchun UI'da doim
        # "Ulanmagan" chiqardi. Ulash oqimi — alohida feature (docs/05 reja).
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
        ],
    }


# ─── Urinishlar (skanlar) ────────────────────────────────────────────────


@router.get("/attempts/{attempt_id}")
async def get_attempt_details(
    attempt_id: int,
    user: User = Depends(get_webapp_user),
    db: AsyncSession = Depends(get_db),
):
    """Urinish natijasi va review uchun ma'lumotlar — faqat test egasi uchun."""
    attempt = await owned_attempt(db, attempt_id, user.id)
    if attempt is None:
        raise HTTPException(status_code=404, detail="Urinish topilmadi")

    titul = attempt.titul
    student = titul.student if titul else None
    test = titul.test if titul else None

    question_count = (test.question_count if test else 0) or 0
    if not question_count and attempt.detected:
        question_count = len(attempt.detected)

    return {
        "id": attempt.id,
        "status": attempt.status,
        "score": attempt.score,
        "total": attempt.total,
        "question_count": question_count,
        "percent": float(attempt.percent) if attempt.percent is not None else None,
        "needs_review": attempt.needs_review,
        "created_at": attempt.created_at.strftime("%d.%m.%Y %H:%M"),
        "detected": attempt.detected,
        "detail": attempt.detail,
        "error_msg": attempt.error_msg,
        "source_url": _file_url(attempt.id, "source", attempt.source_file),
        "debug_url": _file_url(attempt.id, "debug", attempt.debug_file),
        "student_name": student.full_name if student else "Noma'lum",
        "test_title": test.title if test else "Noma'lum",
        "answer_key": test.answer_key if test else {},
        "variant_count": test.variant_count if test else 4,
    }


@router.get("/attempts/{attempt_id}/file/{kind}")
async def get_attempt_file(
    attempt_id: int,
    kind: FileKind,
    user: User = Depends(get_webapp_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Skan surati (`source`) yoki OMR annotatsiyasi (`debug`) — faqat egasiga.

    Ilgari bu fayllar `/static/uploads` va `/static/debug` orqali
    autentifikatsiyasiz berilardi va nomlari taxmin qilinardi.
    """
    attempt = await owned_attempt(db, attempt_id, user.id)
    if attempt is None:
        raise HTTPException(status_code=404, detail="Urinish topilmadi")

    path = attempt_file_path(attempt, kind)
    if path is None:
        raise HTTPException(status_code=404, detail="Fayl topilmadi")
    return file_response_for(path)


@router.post("/attempts/{attempt_id}/review")
async def review_attempt(
    attempt_id: int,
    corrected_answers: dict[str, Optional[str]] = Body(..., embed=True),
    user: User = Depends(get_webapp_user),
    db: AsyncSession = Depends(get_db),
):
    """Ustoz tomonidan belgilarni qo'lda to'g'rilash — faqat o'z skani."""
    attempt = await owned_attempt(db, attempt_id, user.id)
    if attempt is None:
        raise HTTPException(status_code=404, detail="Urinish topilmadi")

    test = attempt.titul.test if attempt.titul else None
    if test is None:
        raise HTTPException(status_code=400, detail="Urinish testga ulanmagan")

    gr = grade(corrected_answers, test.answer_key)

    attempt.detected = dict(corrected_answers)
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
