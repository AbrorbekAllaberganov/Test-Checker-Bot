"""
app/api/admin/explorer.py — Guruh / o'quvchi / test tadqiqotchisi.

Iyerarxiya: Ustoz → Guruh → O'quvchi → Natijalar.

  GET /api/admin/groups                  — barcha guruhlar (egasi bilan)
  GET /api/admin/groups/{id}             — guruh + o'quvchilar + testlar
  GET /api/admin/groups/{id}/export      — guruh natijalari (Excel)
  GET /api/admin/students                — o'quvchilar ro'yxati
  GET /api/admin/students/{id}           — o'quvchi + u ishlagan testlar
  GET /api/admin/students/{id}/export    — o'quvchi natijalari (Excel)
  GET /api/admin/tests                   — testlar ro'yxati
  GET /api/admin/tests/{id}              — test + natijalar + savol tahlili
  GET /api/admin/tests/{id}/export       — test natijalari (Excel)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.deps import DbDep, PaginationDep, require_analyst
from app.models.attempt import Attempt
from app.models.group import Group
from app.models.student import Student
from app.models.test import Test
from app.models.titul import Titul
from app.models.user import User
from app.services.search import LIKE_ESCAPE, like_pattern
from app.schemas.admin.common import Page
from app.schemas.admin.explorer import (
    GroupDetail,
    GroupListItem,
    ItemAnalysisRow,
    StudentAttemptItem,
    StudentDetail,
    StudentListItem,
    StudentResultItem,
    TestDetail,
    TestListItem,
)
from app.services import excel as excel_svc

log = logging.getLogger(__name__)

router = APIRouter(tags=["admin:explorer"], dependencies=[Depends(require_analyst)])

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx_response(content: bytes, prefix: str) -> Response:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    return Response(
        content=content,
        media_type=XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{prefix}_{stamp}.xlsx"'},
    )


# ── Guruhlar ────────────────────────────────────────────────────────────


def _group_scans_sq():
    return (
        select(func.count(Attempt.id))
        .select_from(Attempt)
        .join(Titul, Titul.id == Attempt.titul_id)
        .join(Test, Test.id == Titul.test_id)
        .where(Test.group_id == Group.id)
        .correlate(Group)
        .scalar_subquery()
    )


@router.get("/groups", response_model=Page[GroupListItem])
async def list_groups(
    db: DbDep,
    pagination: PaginationDep,
    owner_id: Optional[int] = Query(None, description="Ustoz bo'yicha filtr"),
    search: Optional[str] = Query(None, description="Guruh nomi"),
) -> Page[GroupListItem]:
    """Barcha guruhlar — egasi va sanoqlari bilan."""

    def apply(stmt: Select) -> Select:
        if owner_id is not None:
            stmt = stmt.where(Group.owner_id == owner_id)
        if search:
            stmt = stmt.where(Group.name.ilike(like_pattern(search), escape=LIKE_ESCAPE))
        return stmt

    total = (await db.execute(apply(select(func.count(Group.id))))).scalar() or 0

    stmt = apply(
        select(
            Group.id,
            Group.name,
            Group.created_at,
            Group.owner_id,
            User.full_name.label("owner_name"),
            User.telegram_id.label("owner_telegram_id"),
            select(func.count(Student.id))
            .where(Student.group_id == Group.id)
            .correlate(Group)
            .scalar_subquery()
            .label("students_count"),
            select(func.count(Test.id))
            .where(Test.group_id == Group.id)
            .correlate(Group)
            .scalar_subquery()
            .label("tests_count"),
            _group_scans_sq().label("scans_count"),
        ).outerjoin(User, User.id == Group.owner_id)
    ).order_by(Group.created_at.desc()).offset(pagination.offset).limit(pagination.limit)

    rows = (await db.execute(stmt)).all()
    items = [
        GroupListItem(
            id=r.id,
            name=r.name,
            created_at=r.created_at,
            owner_id=r.owner_id,
            owner_name=r.owner_name,
            owner_telegram_id=r.owner_telegram_id,
            students_count=r.students_count or 0,
            tests_count=r.tests_count or 0,
            scans_count=r.scans_count or 0,
        )
        for r in rows
    ]
    return Page.build(
        items, page=pagination.page, page_size=pagination.page_size, total=total
    )


@router.get("/groups/{group_id}", response_model=GroupDetail)
async def get_group(group_id: int, db: DbDep) -> GroupDetail:
    """Guruh tafsiloti: o'quvchilar va testlar."""
    row = (
        await db.execute(
            select(
                Group.id,
                Group.name,
                Group.created_at,
                Group.owner_id,
                User.full_name.label("owner_name"),
                User.telegram_id.label("owner_telegram_id"),
            )
            .outerjoin(User, User.id == Group.owner_id)
            .where(Group.id == group_id)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Guruh topilmadi")

    student_rows = (
        await db.execute(
            select(
                Student.id,
                Student.full_name,
                Student.telegram_id,
                Student.group_id,
                Student.created_at,
                select(func.count(Attempt.id))
                .select_from(Attempt)
                .join(Titul, Titul.id == Attempt.titul_id)
                .where(Titul.student_id == Student.id)
                .correlate(Student)
                .scalar_subquery()
                .label("attempts_count"),
                select(func.avg(Attempt.percent))
                .select_from(Attempt)
                .join(Titul, Titul.id == Attempt.titul_id)
                .where(Titul.student_id == Student.id, Attempt.status == "done")
                .correlate(Student)
                .scalar_subquery()
                .label("avg_percent"),
            )
            .where(Student.group_id == group_id)
            .order_by(Student.full_name)
        )
    ).all()

    test_rows = (
        await db.execute(
            select(
                Test.id,
                Test.title,
                Test.question_count,
                Test.variant_count,
                Test.created_at,
                Test.group_id,
                select(func.count(Titul.id))
                .where(Titul.test_id == Test.id)
                .correlate(Test)
                .scalar_subquery()
                .label("tituls_count"),
                select(func.count(Attempt.id))
                .select_from(Attempt)
                .join(Titul, Titul.id == Attempt.titul_id)
                .where(Titul.test_id == Test.id)
                .correlate(Test)
                .scalar_subquery()
                .label("attempts_count"),
                select(func.avg(Attempt.percent))
                .select_from(Attempt)
                .join(Titul, Titul.id == Attempt.titul_id)
                .where(Titul.test_id == Test.id, Attempt.status == "done")
                .correlate(Test)
                .scalar_subquery()
                .label("avg_percent"),
            )
            .where(Test.group_id == group_id)
            .order_by(Test.created_at.desc())
        )
    ).all()

    return GroupDetail(
        id=row.id,
        name=row.name,
        created_at=row.created_at,
        owner_id=row.owner_id,
        owner_name=row.owner_name,
        owner_telegram_id=row.owner_telegram_id,
        students=[
            StudentListItem(
                id=s.id,
                full_name=s.full_name,
                telegram_id=s.telegram_id,
                group_id=s.group_id,
                group_name=row.name,
                created_at=s.created_at,
                attempts_count=s.attempts_count or 0,
                avg_percent=(
                    round(float(s.avg_percent), 2) if s.avg_percent is not None else None
                ),
            )
            for s in student_rows
        ],
        tests=[
            TestListItem(
                id=t.id,
                title=t.title,
                question_count=t.question_count,
                variant_count=t.variant_count,
                created_at=t.created_at,
                group_id=t.group_id,
                group_name=row.name,
                owner_id=row.owner_id,
                owner_name=row.owner_name,
                tituls_count=t.tituls_count or 0,
                attempts_count=t.attempts_count or 0,
                avg_percent=(
                    round(float(t.avg_percent), 2) if t.avg_percent is not None else None
                ),
            )
            for t in test_rows
        ],
    )


@router.get("/groups/{group_id}/export")
async def export_group(group_id: int, db: DbDep) -> Response:
    """Guruhning barcha test natijalari — Excel."""
    # Admin barcha ustozlarni ko'radi — tenant filtri yo'q (owner_id=None).
    content = await excel_svc.export_group_excel(db, group_id, owner_id=None)
    return _xlsx_response(content, f"group_{group_id}_results")


# ── O'quvchilar ─────────────────────────────────────────────────────────


@router.get("/students", response_model=Page[StudentListItem])
async def list_students(
    db: DbDep,
    pagination: PaginationDep,
    group_id: Optional[int] = Query(None),
    owner_id: Optional[int] = Query(None, description="Ustoz bo'yicha filtr"),
    search: Optional[str] = Query(None, description="O'quvchi F.I.Sh."),
) -> Page[StudentListItem]:
    def apply(stmt: Select) -> Select:
        stmt = stmt.join(Group, Group.id == Student.group_id)
        if group_id is not None:
            stmt = stmt.where(Student.group_id == group_id)
        if owner_id is not None:
            stmt = stmt.where(Group.owner_id == owner_id)
        if search:
            stmt = stmt.where(Student.full_name.ilike(like_pattern(search), escape=LIKE_ESCAPE))
        return stmt

    total = (
        await db.execute(apply(select(func.count(Student.id)).select_from(Student)))
    ).scalar() or 0

    stmt = apply(
        select(
            Student.id,
            Student.full_name,
            Student.telegram_id,
            Student.group_id,
            Student.created_at,
            Group.name.label("group_name"),
            select(func.count(Attempt.id))
            .select_from(Attempt)
            .join(Titul, Titul.id == Attempt.titul_id)
            .where(Titul.student_id == Student.id)
            .correlate(Student)
            .scalar_subquery()
            .label("attempts_count"),
            select(func.avg(Attempt.percent))
            .select_from(Attempt)
            .join(Titul, Titul.id == Attempt.titul_id)
            .where(Titul.student_id == Student.id, Attempt.status == "done")
            .correlate(Student)
            .scalar_subquery()
            .label("avg_percent"),
        ).select_from(Student)
    ).order_by(Student.full_name).offset(pagination.offset).limit(pagination.limit)

    rows = (await db.execute(stmt)).all()
    items = [
        StudentListItem(
            id=r.id,
            full_name=r.full_name,
            telegram_id=r.telegram_id,
            group_id=r.group_id,
            group_name=r.group_name,
            created_at=r.created_at,
            attempts_count=r.attempts_count or 0,
            avg_percent=round(float(r.avg_percent), 2) if r.avg_percent is not None else None,
        )
        for r in rows
    ]
    return Page.build(
        items, page=pagination.page, page_size=pagination.page_size, total=total
    )


@router.get("/students/{student_id}", response_model=StudentDetail)
async def get_student(student_id: int, db: DbDep) -> StudentDetail:
    """
    O'quvchi tafsiloti: u ishlagan testlar ro'yxati.

    Qatorlar `tituls` dan olinadi va `attempts` ga OUTER join qilinadi —
    varaq chiqarilgan, lekin hali skanlanmagan holat ham ko'rinishi kerak.
    Bitta titulga bir nechta skan tushgan bo'lsa (qayta yuborilgan varaq),
    har biri alohida qator bo'lib chiqadi.
    """
    row = (
        await db.execute(
            select(
                Student.id,
                Student.full_name,
                Student.telegram_id,
                Student.group_id,
                Student.created_at,
                Group.name.label("group_name"),
                Group.owner_id.label("owner_id"),
                User.full_name.label("owner_name"),
            )
            .join(Group, Group.id == Student.group_id)
            .outerjoin(User, User.id == Group.owner_id)
            .where(Student.id == student_id)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="O'quvchi topilmadi")

    attempt_rows = (
        await db.execute(
            select(
                Titul.id.label("titul_id"),
                Titul.created_at.label("titul_created_at"),
                Test.id.label("test_id"),
                Test.title.label("test_title"),
                Test.question_count,
                Test.variant_count,
                Attempt.id.label("attempt_id"),
                Attempt.score,
                Attempt.total,
                Attempt.percent,
                Attempt.needs_review,
                Attempt.manual_override,
                Attempt.confidence,
                Attempt.status,
                Attempt.created_at,
            )
            .select_from(Titul)
            .join(Test, Test.id == Titul.test_id)
            .outerjoin(Attempt, Attempt.titul_id == Titul.id)
            .where(Titul.student_id == student_id)
            .order_by(
                Attempt.created_at.desc().nullslast(),
                Titul.created_at.desc(),
            )
        )
    ).all()

    items = [
        StudentAttemptItem(
            titul_id=r.titul_id,
            titul_created_at=r.titul_created_at,
            test_id=r.test_id,
            test_title=r.test_title,
            question_count=r.question_count,
            variant_count=r.variant_count,
            attempt_id=r.attempt_id,
            score=r.score,
            total=r.total,
            percent=float(r.percent) if r.percent is not None else None,
            needs_review=bool(r.needs_review),
            manual_override=bool(r.manual_override),
            confidence=float(r.confidence) if r.confidence is not None else None,
            status=r.status,
            created_at=r.created_at,
        )
        for r in attempt_rows
    ]

    # Titul bir nechta skan bergan bo'lsa ham bitta varaq deb sanaladi.
    tituls_count = len({r.titul_id for r in attempt_rows})
    graded = [
        i.percent for i in items if i.status == "done" and i.percent is not None
    ]

    return StudentDetail(
        id=row.id,
        full_name=row.full_name,
        telegram_id=row.telegram_id,
        group_id=row.group_id,
        group_name=row.group_name,
        owner_id=row.owner_id,
        owner_name=row.owner_name,
        created_at=row.created_at,
        tituls_count=tituls_count,
        attempts_count=sum(1 for i in items if i.attempt_id is not None),
        graded_count=len(graded),
        avg_percent=round(sum(graded) / len(graded), 2) if graded else None,
        best_percent=round(max(graded), 2) if graded else None,
        attempts=items,
    )


@router.get("/students/{student_id}/export")
async def export_student(student_id: int, db: DbDep) -> Response:
    content = await excel_svc.export_student_excel(db, student_id, owner_id=None)
    return _xlsx_response(content, f"student_{student_id}_results")


# ── Testlar ─────────────────────────────────────────────────────────────


@router.get("/tests", response_model=Page[TestListItem])
async def list_tests(
    db: DbDep,
    pagination: PaginationDep,
    group_id: Optional[int] = Query(None),
    owner_id: Optional[int] = Query(None),
    question_count: Optional[int] = Query(None, description="40 | 50 | 90"),
    search: Optional[str] = Query(None, description="Test nomi"),
) -> Page[TestListItem]:
    def apply(stmt: Select) -> Select:
        stmt = stmt.join(Group, Group.id == Test.group_id)
        if group_id is not None:
            stmt = stmt.where(Test.group_id == group_id)
        if owner_id is not None:
            stmt = stmt.where(Group.owner_id == owner_id)
        if question_count is not None:
            stmt = stmt.where(Test.question_count == question_count)
        if search:
            stmt = stmt.where(Test.title.ilike(like_pattern(search), escape=LIKE_ESCAPE))
        return stmt

    total = (
        await db.execute(apply(select(func.count(Test.id)).select_from(Test)))
    ).scalar() or 0

    stmt = apply(
        select(
            Test.id,
            Test.title,
            Test.question_count,
            Test.variant_count,
            Test.created_at,
            Test.group_id,
            Group.name.label("group_name"),
            Group.owner_id.label("owner_id"),
            User.full_name.label("owner_name"),
            select(func.count(Titul.id))
            .where(Titul.test_id == Test.id)
            .correlate(Test)
            .scalar_subquery()
            .label("tituls_count"),
            select(func.count(Attempt.id))
            .select_from(Attempt)
            .join(Titul, Titul.id == Attempt.titul_id)
            .where(Titul.test_id == Test.id)
            .correlate(Test)
            .scalar_subquery()
            .label("attempts_count"),
            select(func.avg(Attempt.percent))
            .select_from(Attempt)
            .join(Titul, Titul.id == Attempt.titul_id)
            .where(Titul.test_id == Test.id, Attempt.status == "done")
            .correlate(Test)
            .scalar_subquery()
            .label("avg_percent"),
        ).select_from(Test)
    ).outerjoin(User, User.id == Group.owner_id).order_by(
        Test.created_at.desc()
    ).offset(pagination.offset).limit(pagination.limit)

    rows = (await db.execute(stmt)).all()
    items = [
        TestListItem(
            id=r.id,
            title=r.title,
            question_count=r.question_count,
            variant_count=r.variant_count,
            created_at=r.created_at,
            group_id=r.group_id,
            group_name=r.group_name,
            owner_id=r.owner_id,
            owner_name=r.owner_name,
            tituls_count=r.tituls_count or 0,
            attempts_count=r.attempts_count or 0,
            avg_percent=round(float(r.avg_percent), 2) if r.avg_percent is not None else None,
        )
        for r in rows
    ]
    return Page.build(
        items, page=pagination.page, page_size=pagination.page_size, total=total
    )


@router.get("/tests/{test_id}", response_model=TestDetail)
async def get_test(test_id: int, db: DbDep) -> TestDetail:
    """Test tafsiloti: kalit, natijalar va savollar tahlili."""
    row = (
        await db.execute(
            select(
                Test.id,
                Test.title,
                Test.question_count,
                Test.variant_count,
                Test.answer_key,
                Test.created_at,
                Test.group_id,
                Group.name.label("group_name"),
                Group.owner_id.label("owner_id"),
                User.full_name.label("owner_name"),
            )
            .join(Group, Group.id == Test.group_id)
            .outerjoin(User, User.id == Group.owner_id)
            .where(Test.id == test_id)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Test topilmadi")

    # Natijalar (har o'quvchining oxirgi urinishi emas — barcha urinishlari).
    result_rows = (
        await db.execute(
            select(
                Attempt.id.label("attempt_id"),
                Student.id.label("student_id"),
                Student.full_name.label("student_name"),
                Attempt.score,
                Attempt.total,
                Attempt.percent,
                Attempt.needs_review,
                Attempt.status,
                Attempt.created_at,
            )
            .select_from(Attempt)
            .join(Titul, Titul.id == Attempt.titul_id)
            .join(Student, Student.id == Titul.student_id)
            .where(Titul.test_id == test_id)
            .order_by(Attempt.percent.desc().nullslast(), Attempt.created_at.desc())
        )
    ).all()

    # Savol tahlili — `detail` JSONB dan hisoblanadi.
    detail_rows = (
        await db.execute(
            select(Attempt.detail)
            .select_from(Attempt)
            .join(Titul, Titul.id == Attempt.titul_id)
            .where(Titul.test_id == test_id, Attempt.status == "done")
        )
    ).scalars().all()

    analysis: dict[str, dict[str, int]] = {
        str(i): {"correct": 0, "incorrect": 0, "unmarked": 0}
        for i in range(1, row.question_count + 1)
    }
    for detail in detail_rows:
        if not detail:
            continue
        for q_str, bucket in analysis.items():
            info = detail.get(q_str) or {}
            got = info.get("got")
            if got is None:
                bucket["unmarked"] += 1
            elif info.get("ok"):
                bucket["correct"] += 1
            else:
                bucket["incorrect"] += 1

    graded = len(detail_rows)
    item_analysis = [
        ItemAnalysisRow(
            question=q,
            correct_count=b["correct"],
            incorrect_count=b["incorrect"],
            unmarked_count=b["unmarked"],
            correct_percent=round(100.0 * b["correct"] / graded, 2) if graded else 0.0,
        )
        for q, b in sorted(analysis.items(), key=lambda kv: int(kv[0]))
    ]

    percents = [float(r.percent) for r in result_rows if r.percent is not None]

    return TestDetail(
        id=row.id,
        title=row.title,
        question_count=row.question_count,
        variant_count=row.variant_count,
        answer_key=row.answer_key or {},
        created_at=row.created_at,
        group_id=row.group_id,
        group_name=row.group_name,
        owner_id=row.owner_id,
        owner_name=row.owner_name,
        attempts_count=len(result_rows),
        avg_percent=round(sum(percents) / len(percents), 2) if percents else None,
        results=[
            StudentResultItem(
                attempt_id=r.attempt_id,
                student_id=r.student_id,
                student_name=r.student_name,
                score=r.score,
                total=r.total,
                percent=float(r.percent) if r.percent is not None else None,
                needs_review=r.needs_review,
                status=r.status,
                created_at=r.created_at,
            )
            for r in result_rows
        ],
        item_analysis=item_analysis,
    )


@router.get("/tests/{test_id}/export")
async def export_test(test_id: int, db: DbDep) -> Response:
    content = await excel_svc.export_test_excel(db, test_id, owner_id=None)
    return _xlsx_response(content, f"test_{test_id}_results")
