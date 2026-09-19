"""
app/api/admin/scans.py — OMR skanlari markazi va inspektor.

  GET  /api/admin/scans                  — sahifalangan ro'yxat + filtrlar
  GET  /api/admin/scans/review-queue     — faqat qayta ko'rik kutayotganlar
  GET  /api/admin/scans/{id}             — inspektor uchun to'liq ma'lumot
  POST /api/admin/scans/{id}/override    — javoblarni qo'lda tuzatish
  POST /api/admin/scans/{id}/resolve     — tuzatishsiz "ko'rildi" deb belgilash

Inspektor rasmlar: `source_url` — o'quvchi yuborgan asl surat, `debug_url` —
OMR annotatsiyalangan varaq (faqat `OMR_DEBUG=true` bo'lganda saqlanadi).
Doira to'ldirilganligi (`bubble_data`) 003 migratsiyasidan keyingi skanlarda
mavjud; undan oldingilarida `bubbles` bo'sh qaytadi va frontend faqat
aniqlangan javobni ko'rsatadi.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.api.admin.deps import DbDep, PaginationDep, require_analyst, require_support
from app.models.attempt import Attempt
from app.models.enums import AuditAction
from app.models.group import Group
from app.models.student import Student
from app.models.test import Test
from app.models.titul import Titul
from app.models.user import User
from app.schemas.admin.common import Page
from app.schemas.admin.scans import (
    BubbleCell,
    OmrInspectorOut,
    OverrideAnswersIn,
    ScanListItem,
    ScanQuestionRow,
)
from app.services import audit as audit_svc
from app.services.attempt_files import (
    FileKind,
    attempt_file_path,
    file_response_for,
    resolve_attempt_file,
)
from app.services.grading import grade
from app.services.telegram import TelegramSendError, escape, send_message

log = logging.getLogger(__name__)

router = APIRouter(prefix="/scans", tags=["admin:scans"])

LETTERS = "ABCDE"


# `User` ikki marta JOIN qilinadi: guruh egasi va skanni yuborgan.
# Ikkinchisi uchun alias shart, aks holda SQLAlchemy ularni ajrata olmaydi.
Submitter = aliased(User, name="submitter")


def _file_url(attempt_id: int, kind: FileKind, filepath: Optional[str]) -> Optional[str]:
    """
    Fayl mavjud bo'lsa — admin auth'li endpoint URL'i, aks holda None.

    Ilgari `/static/uploads/<nom>` qaytarilardi — autentifikatsiyasiz.
    """
    if resolve_attempt_file(filepath) is None:
        return None
    return f"/api/admin/scans/{attempt_id}/file/{kind}"


def _base_scan_query() -> Select:
    """Skan + titul → test → guruh → ustoz zanjiri (hammasi LEFT JOIN).

    `titul_id` NULL bo'lishi mumkin (QR o'qilmagan skanlar), shu sababli
    barcha JOIN'lar outer — aks holda aynan eng muammoli skanlar ro'yxatdan
    tushib qolardi.
    """
    return (
        select(
            Attempt.id,
            Attempt.status,
            Attempt.needs_review,
            Attempt.manual_override,
            Attempt.score,
            Attempt.total,
            Attempt.percent,
            Attempt.confidence,
            Attempt.error_msg,
            Attempt.created_at,
            Student.id.label("student_id"),
            Student.full_name.label("student_name"),
            Test.id.label("test_id"),
            Test.title.label("test_title"),
            Group.id.label("group_id"),
            Group.name.label("group_name"),
            User.id.label("owner_id"),
            User.full_name.label("owner_name"),
            # Kim yubordi (004): QR o'qilmagan skanda `owner_*` NULL bo'ladi
            # va faqat shu ustun kimdan kelganini ko'rsatadi.
            Submitter.id.label("submitted_by_id"),
            Submitter.full_name.label("submitted_by_name"),
        )
        .select_from(Attempt)
        .outerjoin(Titul, Titul.id == Attempt.titul_id)
        .outerjoin(Test, Test.id == Titul.test_id)
        .outerjoin(Student, Student.id == Titul.student_id)
        .outerjoin(Group, Group.id == Test.group_id)
        .outerjoin(User, User.id == Group.owner_id)
        .outerjoin(Submitter, Submitter.id == Attempt.submitted_by_id)
    )


def _apply_scan_filters(
    stmt: Select,
    *,
    status_filter: Optional[str],
    needs_review: Optional[bool],
    owner_id: Optional[int],
    test_id: Optional[int],
    group_id: Optional[int],
    date_from: Optional[datetime],
    date_to: Optional[datetime],
    max_confidence: Optional[float],
) -> Select:
    if status_filter:
        stmt = stmt.where(Attempt.status == status_filter)
    if needs_review is not None:
        stmt = stmt.where(Attempt.needs_review.is_(needs_review))
    if owner_id is not None:
        stmt = stmt.where(Group.owner_id == owner_id)
    if test_id is not None:
        stmt = stmt.where(Titul.test_id == test_id)
    if group_id is not None:
        stmt = stmt.where(Test.group_id == group_id)
    if date_from is not None:
        stmt = stmt.where(Attempt.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(Attempt.created_at <= date_to)
    if max_confidence is not None:
        stmt = stmt.where(Attempt.confidence <= max_confidence)
    return stmt


def _count_query() -> Select:
    """Filtrlar bilan bir xil JOIN zanjiriga ega COUNT so'rovi."""
    return (
        select(func.count(Attempt.id))
        .select_from(Attempt)
        .outerjoin(Titul, Titul.id == Attempt.titul_id)
        .outerjoin(Test, Test.id == Titul.test_id)
        .outerjoin(Group, Group.id == Test.group_id)
    )


def _to_list_item(row) -> ScanListItem:
    return ScanListItem(
        id=row.id,
        status=row.status,
        needs_review=row.needs_review,
        manual_override=row.manual_override,
        score=row.score,
        total=row.total,
        percent=float(row.percent) if row.percent is not None else None,
        confidence=float(row.confidence) if row.confidence is not None else None,
        error_msg=row.error_msg,
        created_at=row.created_at,
        student_id=row.student_id,
        student_name=row.student_name,
        test_id=row.test_id,
        test_title=row.test_title,
        group_id=row.group_id,
        group_name=row.group_name,
        owner_id=row.owner_id,
        owner_name=row.owner_name,
        submitted_by_id=row.submitted_by_id,
        submitted_by_name=row.submitted_by_name,
    )


@router.get("", response_model=Page[ScanListItem], dependencies=[Depends(require_analyst)])
async def list_scans(
    db: DbDep,
    pagination: PaginationDep,
    status_filter: Optional[str] = Query(
        None, alias="status", description="pending | done | error"
    ),
    needs_review: Optional[bool] = Query(None),
    owner_id: Optional[int] = Query(None),
    test_id: Optional[int] = Query(None),
    group_id: Optional[int] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    max_confidence: Optional[float] = Query(
        None, ge=0.0, le=1.0, description="Shu qiymatdan past ishonchli skanlar"
    ),
) -> Page[ScanListItem]:
    """Barcha skanlar — filtrlangan va sahifalangan."""
    filters = dict(
        status_filter=status_filter,
        needs_review=needs_review,
        owner_id=owner_id,
        test_id=test_id,
        group_id=group_id,
        date_from=date_from,
        date_to=date_to,
        max_confidence=max_confidence,
    )

    total = (
        await db.execute(_apply_scan_filters(_count_query(), **filters))
    ).scalar() or 0

    stmt = (
        _apply_scan_filters(_base_scan_query(), **filters)
        .order_by(Attempt.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    rows = (await db.execute(stmt)).all()

    return Page.build(
        [_to_list_item(r) for r in rows],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )


@router.get(
    "/review-queue",
    response_model=Page[ScanListItem],
    dependencies=[Depends(require_analyst)],
)
async def review_queue(
    db: DbDep,
    pagination: PaginationDep,
) -> Page[ScanListItem]:
    """
    Qayta ko'rik navbati: ikkilangan (`needs_review`) yoki xato bergan skanlar.

    Eng eskisi birinchi — navbat FIFO tartibida ishlanadi.
    """
    condition = (Attempt.needs_review.is_(True)) | (Attempt.status == "error")

    total = (
        await db.execute(_count_query().where(condition))
    ).scalar() or 0

    rows = (
        await db.execute(
            _base_scan_query()
            .where(condition)
            .where(Attempt.manual_override.is_(False))
            .order_by(Attempt.created_at.asc())
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
    ).all()

    return Page.build(
        [_to_list_item(r) for r in rows],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )


async def _load_attempt(db: AsyncSession, attempt_id: int) -> Attempt:
    attempt = (
        await db.execute(
            select(Attempt)
            .options(
                # `owner` gacha to'liq zanjir — aks holda async kontekstda
                # lazy-load MissingGreenlet xatosini beradi.
                selectinload(Attempt.titul)
                .selectinload(Titul.test)
                .selectinload(Test.group)
                .selectinload(Group.owner),
                selectinload(Attempt.titul).selectinload(Titul.student),
                selectinload(Attempt.reviewed_by),
            )
            .where(Attempt.id == attempt_id)
        )
    ).scalar_one_or_none()
    if attempt is None:
        raise HTTPException(status_code=404, detail="Skan topilmadi")
    return attempt


def _build_questions(attempt: Attempt, test: Optional[Test]) -> list[ScanQuestionRow]:
    """detected + detail + bubble_data → inspektor qatorlari."""
    answer_key: dict[str, str] = (test.answer_key if test else {}) or {}
    detected: dict[str, Optional[str]] = attempt.detected or {}
    detail: dict[str, dict] = attempt.detail or {}
    bubbles: dict[str, dict] = attempt.bubble_data or {}

    variant_count = test.variant_count if test else 4
    letters = list(LETTERS[:variant_count])

    # Savollar ro'yxati: kalit bo'lsa undan, bo'lmasa aniqlanganlardan.
    question_ids = sorted(
        {*answer_key.keys(), *detected.keys(), *bubbles.keys()},
        key=lambda q: int(q) if q.isdigit() else 0,
    )

    rows: list[ScanQuestionRow] = []
    for q in question_ids:
        got = detected.get(q)
        correct = answer_key.get(q)
        info = detail.get(q) or {}
        bubble_info = bubbles.get(q) or {}
        ratios: dict[str, float] = bubble_info.get("ratios") or {}

        rows.append(
            ScanQuestionRow(
                question=q,
                detected=got,
                correct=correct,
                is_correct=bool(info.get("ok")) if info else (got is not None and got == correct),
                flag=bubble_info.get("flag"),
                confidence=bubble_info.get("conf"),
                bubbles=[
                    BubbleCell(
                        letter=letter,
                        fill_ratio=float(ratios.get(letter, 0.0)),
                        is_selected=(got == letter),
                        is_correct_key=(correct == letter),
                    )
                    for letter in letters
                ]
                if ratios
                else [],
            )
        )
    return rows


@router.get("/{attempt_id}", response_model=OmrInspectorOut, dependencies=[Depends(require_analyst)])
async def inspect_scan(attempt_id: int, db: DbDep) -> OmrInspectorOut:
    """OMR inspektori uchun to'liq ma'lumot (rasm + doiralar + javoblar)."""
    attempt = await _load_attempt(db, attempt_id)

    titul = attempt.titul
    test = titul.test if titul else None
    student = titul.student if titul else None
    group = test.group if test and test.group else None
    owner = group.owner if group and group.owner else None

    question_count = test.question_count if test else len(attempt.detected or {})
    variant_count = test.variant_count if test else 4

    return OmrInspectorOut(
        id=attempt.id,
        status=attempt.status,
        needs_review=attempt.needs_review,
        manual_override=attempt.manual_override,
        score=attempt.score,
        total=attempt.total,
        percent=float(attempt.percent) if attempt.percent is not None else None,
        confidence=float(attempt.confidence) if attempt.confidence is not None else None,
        error_msg=attempt.error_msg,
        created_at=attempt.created_at,
        reviewed_at=attempt.reviewed_at,
        reviewed_by=attempt.reviewed_by.display_name if attempt.reviewed_by else None,
        student_id=student.id if student else None,
        student_name=student.full_name if student else None,
        test_id=test.id if test else None,
        test_title=test.title if test else None,
        group_name=group.name if group else None,
        owner_id=owner.id if owner else None,
        owner_name=owner.display_name if owner else None,
        owner_telegram_id=owner.telegram_id if owner else None,
        question_count=question_count,
        variant_letters=list(LETTERS[:variant_count]),
        source_url=_file_url(attempt.id, "source", attempt.source_file),
        debug_url=_file_url(attempt.id, "debug", attempt.debug_file),
        questions=_build_questions(attempt, test),
    )


@router.get(
    "/{attempt_id}/file/{kind}",
    dependencies=[Depends(require_analyst)],
    response_class=Response,
)
async def scan_file(attempt_id: int, kind: FileKind, db: DbDep) -> Response:
    """
    Skan surati (`source`) yoki OMR annotatsiyasi (`debug`).

    Frontend `<img src>` bilan emas, `Authorization` header'li so'rov +
    blob URL bilan ko'rsatadi (OmrInspectorModal). Fayl faqat ruxsat
    etilgan papkalardan beriladi (`services/attempt_files.py`).
    """
    attempt = (
        await db.execute(select(Attempt).where(Attempt.id == attempt_id))
    ).scalar_one_or_none()
    if attempt is None:
        raise HTTPException(status_code=404, detail="Skan topilmadi")

    path = attempt_file_path(attempt, kind)
    if path is None:
        raise HTTPException(status_code=404, detail="Fayl topilmadi")
    return file_response_for(path)


@router.post("/{attempt_id}/override", response_model=OmrInspectorOut)
async def override_answers(
    attempt_id: int,
    body: OverrideAnswersIn,
    request: Request,
    db: DbDep,
    admin: User = Depends(require_support),
) -> OmrInspectorOut:
    """
    Javoblarni qo'lda tuzatadi, ballni qayta hisoblaydi va (ixtiyoriy)
    ustozga Telegram orqali yangilangan natijani yuboradi.

    Faqat yuborilgan savollar o'zgaradi — qolganlari joriy qiymatida qoladi.
    """
    attempt = await _load_attempt(db, attempt_id)

    titul = attempt.titul
    test = titul.test if titul else None
    if test is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu skan testga ulanmagan (QR o'qilmagan) — qo'lda tuzatib bo'lmaydi",
        )

    valid_letters = set(LETTERS[: test.variant_count])
    for q, value in body.answers.items():
        if value is not None and value not in valid_letters:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"{q}-savol uchun '{value}' javobi noto'g'ri. "
                    f"Ruxsat etilgan: {', '.join(sorted(valid_letters))} yoki null"
                ),
            )
        if q not in (test.answer_key or {}):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{q}-savol bu testda mavjud emas",
            )

    before = {
        "score": attempt.score,
        "total": attempt.total,
        "percent": float(attempt.percent) if attempt.percent is not None else None,
        "detected": dict(attempt.detected or {}),
    }

    merged: dict[str, Optional[str]] = dict(attempt.detected or {})
    merged.update(body.answers)

    result = grade(merged, test.answer_key or {})

    attempt.detected = merged
    attempt.score = result.score
    attempt.total = result.total
    attempt.percent = result.percent
    attempt.detail = result.detail
    attempt.needs_review = False
    attempt.manual_override = True
    attempt.status = "done"
    attempt.error_msg = None
    attempt.reviewed_by_id = admin.id
    attempt.reviewed_at = datetime.now(timezone.utc)
    await db.flush()

    await audit_svc.record(
        db,
        actor=admin,
        action=AuditAction.ATTEMPT_OVERRIDE,
        object_type="attempt",
        object_id=attempt.id,
        payload={
            "reason": body.reason,
            "changed_questions": sorted(body.answers.keys(), key=lambda x: int(x) if x.isdigit() else 0),
            "changes": audit_svc.diff(
                before,
                {
                    "score": attempt.score,
                    "total": attempt.total,
                    "percent": float(attempt.percent) if attempt.percent is not None else None,
                    "detected": merged,
                },
            ),
        },
        request=request,
    )
    await db.commit()

    if body.notify_teacher:
        await _notify_override(attempt, test)

    return await inspect_scan(attempt_id, db)


async def _notify_override(attempt: Attempt, test: Test) -> None:
    """Ustozga qo'lda tuzatilgan natija haqida xabar (xato bo'lsa faqat log)."""
    group = test.group
    owner = group.owner if group else None
    student = attempt.titul.student if attempt.titul else None
    if owner is None:
        return

    student_name = student.full_name if student else "O'quvchi"
    text = (
        "✏️ <b>Natija qo'lda tuzatildi</b>\n\n"
        f"👤 {student_name}\n"
        f"📝 {test.title}\n"
        f"✅ Yangi natija: <b>{attempt.score}/{attempt.total}</b> "
        f"({float(attempt.percent or 0):.1f}%)\n\n"
        "<i>Varaq operator tomonidan qayta ko'rib chiqildi.</i>"
    )
    try:
        await send_message(owner.telegram_id, text)
    except TelegramSendError as exc:
        log.warning(
            "Tuzatish haqida xabar yuborilmadi: tg=%s xato=%s", owner.telegram_id, exc
        )


@router.post("/{attempt_id}/resolve", response_model=OmrInspectorOut)
async def resolve_scan(
    attempt_id: int,
    request: Request,
    db: DbDep,
    admin: User = Depends(require_support),
    reason: Optional[str] = Query(None, max_length=500),
) -> OmrInspectorOut:
    """Tuzatishsiz "ko'rildi, hammasi joyida" deb belgilash (navbatdan chiqarish)."""
    attempt = await _load_attempt(db, attempt_id)

    attempt.needs_review = False
    attempt.reviewed_by_id = admin.id
    attempt.reviewed_at = datetime.now(timezone.utc)
    await db.flush()

    await audit_svc.record(
        db,
        actor=admin,
        action=AuditAction.ATTEMPT_OVERRIDE,
        object_type="attempt",
        object_id=attempt.id,
        payload={"resolved_without_changes": True, "reason": reason},
        request=request,
    )
    await db.commit()

    return await inspect_scan(attempt_id, db)
