"""
app/api/admin/broadcasts.py — Telegram e'lonlari.

  GET  /api/admin/broadcasts             — e'lonlar tarixi
  POST /api/admin/broadcasts             — yaratish (ixtiyoriy: darrov yuborish)
  POST /api/admin/broadcasts/preview     — kimga ketishini oldindan ko'rish
  GET  /api/admin/broadcasts/{id}        — tafsilot + qabul qiluvchilar
  POST /api/admin/broadcasts/{id}/send   — draft'ni navbatga qo'yish
  POST /api/admin/broadcasts/{id}/cancel — hali yuborilmaganini bekor qilish

Yuborishning o'zi Celery'da (`broadcast_task`) — HTTP so'rov faqat navbatga
qo'yadi va darhol javob qaytaradi.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.admin.deps import DbDep, PaginationDep, require_analyst, require_support
from app.models.broadcast import Broadcast, BroadcastRecipient
from app.models.enums import AuditAction, BroadcastStatus
from app.models.user import User
from app.schemas.admin.broadcasts import (
    BroadcastCreateIn,
    BroadcastDetail,
    BroadcastListItem,
    BroadcastPreviewOut,
    RecipientRow,
)
from app.schemas.admin.common import Page
from app.services import audit as audit_svc
from app.services import broadcast as broadcast_svc

log = logging.getLogger(__name__)

router = APIRouter(prefix="/broadcasts", tags=["admin:broadcasts"])

PREVIEW_LENGTH = 120
SAMPLE_SIZE = 10

# Bu holatlardan keyin e'lonni qayta yuborib bo'lmaydi.
_TERMINAL = (BroadcastStatus.SENT.value, BroadcastStatus.CANCELLED.value)


def _to_list_item(b: Broadcast, *, created_by: Optional[str] = None) -> BroadcastListItem:
    body = b.body or ""
    return BroadcastListItem(
        id=b.id,
        title=b.title,
        body_preview=(body[:PREVIEW_LENGTH] + "…") if len(body) > PREVIEW_LENGTH else body,
        audience=b.audience,
        status=b.status,
        total_count=b.total_count,
        sent_count=b.sent_count,
        failed_count=b.failed_count,
        created_by=created_by,
        created_at=b.created_at,
        started_at=b.started_at,
        finished_at=b.finished_at,
    )


@router.get("", response_model=Page[BroadcastListItem], dependencies=[Depends(require_analyst)])
async def list_broadcasts(db: DbDep, pagination: PaginationDep) -> Page[BroadcastListItem]:
    """E'lonlar tarixi (yangi → eski)."""
    total = (await db.execute(select(func.count(Broadcast.id)))).scalar() or 0

    rows = (
        await db.execute(
            select(Broadcast, User.full_name.label("created_by"))
            .outerjoin(User, User.id == Broadcast.created_by_id)
            .order_by(Broadcast.created_at.desc())
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
    ).all()

    items = [_to_list_item(r.Broadcast, created_by=r.created_by) for r in rows]
    return Page.build(
        items, page=pagination.page, page_size=pagination.page_size, total=total
    )


@router.post("/preview", response_model=BroadcastPreviewOut, dependencies=[Depends(require_analyst)])
async def preview(body: BroadcastCreateIn, db: DbDep) -> BroadcastPreviewOut:
    """
    Yuborishdan oldin: nechta ustozga ketadi va matn qanday ko'rinadi.

    Hech narsa saqlanmaydi — faqat hisob-kitob.
    """
    users = await broadcast_svc.resolve_audience(
        db, audience=body.audience.value, target_user_ids=body.target_user_ids
    )
    return BroadcastPreviewOut(
        audience=body.audience.value,
        recipients_count=len(users),
        rendered_text=broadcast_svc.render_preview(body.title, body.body),
        sample_recipients=[
            RecipientRow(
                user_id=u.id,
                telegram_id=u.telegram_id,
                full_name=u.full_name,
                username=u.username,
                status="pending",
            )
            for u in users[:SAMPLE_SIZE]
        ],
    )


async def _load_broadcast(db: AsyncSession, broadcast_id: int) -> Broadcast:
    b = (
        await db.execute(select(Broadcast).where(Broadcast.id == broadcast_id))
    ).scalar_one_or_none()
    if b is None:
        raise HTTPException(status_code=404, detail="E'lon topilmadi")
    return b


def _enqueue(broadcast_id: int) -> None:
    """Celery'ga topshirish — import shu yerda, sirkulyar importdan qochish uchun."""
    from app.worker.broadcast_tasks import broadcast_task

    broadcast_task.delay(broadcast_id)


@router.post("", response_model=BroadcastDetail, status_code=status.HTTP_201_CREATED)
async def create_broadcast(
    body: BroadcastCreateIn,
    request: Request,
    db: DbDep,
    admin: User = Depends(require_support),
) -> BroadcastDetail:
    """E'lon yaratadi; `send_now=true` bo'lsa darhol navbatga qo'yadi."""
    b = Broadcast(
        title=body.title,
        body=body.body,
        parse_mode=body.parse_mode,
        audience=body.audience.value,
        target_user_ids=body.target_user_ids,
        status=BroadcastStatus.DRAFT.value,
        created_by_id=admin.id,
    )
    db.add(b)
    await db.flush()

    count = await broadcast_svc.prepare_recipients(db, b)

    if body.send_now:
        b.status = BroadcastStatus.QUEUED.value
        await audit_svc.record(
            db,
            actor=admin,
            action=AuditAction.BROADCAST_SEND,
            object_type="broadcast",
            object_id=b.id,
            payload={"audience": b.audience, "recipients": count, "title": b.title},
            request=request,
        )

    await db.commit()

    # Commit'dan KEYIN navbatga qo'yamiz — aks holda worker hali ko'rinmagan
    # qatorni o'qishga urinishi mumkin.
    if body.send_now:
        _enqueue(b.id)

    return await get_broadcast(b.id, db)


@router.get("/{broadcast_id}", response_model=BroadcastDetail, dependencies=[Depends(require_analyst)])
async def get_broadcast(
    broadcast_id: int,
    db: DbDep,
    recipients_limit: int = Query(100, ge=0, le=1000),
) -> BroadcastDetail:
    """E'lon tafsiloti va qabul qiluvchilar holati."""
    row = (
        await db.execute(
            select(Broadcast, User.full_name.label("created_by"))
            .outerjoin(User, User.id == Broadcast.created_by_id)
            .where(Broadcast.id == broadcast_id)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="E'lon topilmadi")

    b: Broadcast = row.Broadcast

    recipient_rows = []
    if recipients_limit:
        recipient_rows = (
            await db.execute(
                select(
                    BroadcastRecipient.user_id,
                    BroadcastRecipient.telegram_id,
                    BroadcastRecipient.status,
                    BroadcastRecipient.error_msg,
                    BroadcastRecipient.sent_at,
                    User.full_name,
                    User.username,
                )
                .outerjoin(User, User.id == BroadcastRecipient.user_id)
                .where(BroadcastRecipient.broadcast_id == broadcast_id)
                # Muammoli qatorlar birinchi ko'rinsin.
                .order_by(BroadcastRecipient.status.desc(), BroadcastRecipient.user_id)
                .limit(recipients_limit)
            )
        ).all()

    base = _to_list_item(b, created_by=row.created_by)
    return BroadcastDetail(
        **base.model_dump(),
        body=b.body,
        parse_mode=b.parse_mode,
        target_user_ids=b.target_user_ids,
        error_msg=b.error_msg,
        recipients=[
            RecipientRow(
                user_id=r.user_id,
                telegram_id=r.telegram_id,
                full_name=r.full_name,
                username=r.username,
                status=r.status,
                error_msg=r.error_msg,
                sent_at=r.sent_at,
            )
            for r in recipient_rows
        ],
    )


@router.post("/{broadcast_id}/send", response_model=BroadcastDetail)
async def send_broadcast(
    broadcast_id: int,
    request: Request,
    db: DbDep,
    admin: User = Depends(require_support),
) -> BroadcastDetail:
    """Draft holatidagi e'lonni yuborish navbatiga qo'yadi."""
    b = await _load_broadcast(db, broadcast_id)

    if b.status in _TERMINAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"E'lon allaqachon '{b.status}' holatida — qayta yuborib bo'lmaydi",
        )
    if b.status == BroadcastStatus.SENDING.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="E'lon hozir yuborilmoqda",
        )

    count = await broadcast_svc.prepare_recipients(db, b)
    if count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu auditoriyada birorta ham qabul qiluvchi yo'q",
        )

    b.status = BroadcastStatus.QUEUED.value
    b.error_msg = None

    await audit_svc.record(
        db,
        actor=admin,
        action=AuditAction.BROADCAST_SEND,
        object_type="broadcast",
        object_id=b.id,
        payload={"audience": b.audience, "recipients": count, "title": b.title},
        request=request,
    )
    await db.commit()

    _enqueue(b.id)
    return await get_broadcast(broadcast_id, db)


@router.post("/{broadcast_id}/cancel", response_model=BroadcastDetail)
async def cancel_broadcast(
    broadcast_id: int,
    request: Request,
    db: DbDep,
    admin: User = Depends(require_support),
) -> BroadcastDetail:
    """
    E'lonni bekor qiladi.

    Yuborish boshlangan bo'lsa, worker har xabardan oldin holatni tekshiradi —
    shu sababli bekor qilish o'rtada ham ishlaydi (yuborilganlari qaytmaydi).
    """
    b = await _load_broadcast(db, broadcast_id)
    if b.status in _TERMINAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"E'lon '{b.status}' holatida — bekor qilib bo'lmaydi",
        )

    b.status = BroadcastStatus.CANCELLED.value
    b.finished_at = datetime.now(timezone.utc)

    await audit_svc.record(
        db,
        actor=admin,
        action=AuditAction.BROADCAST_CANCEL,
        object_type="broadcast",
        object_id=b.id,
        payload={"sent_before_cancel": b.sent_count},
        request=request,
    )
    await db.commit()

    return await get_broadcast(broadcast_id, db)
