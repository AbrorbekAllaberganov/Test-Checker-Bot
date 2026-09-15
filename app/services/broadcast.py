"""
app/services/broadcast.py — Telegram e'loni auditoriyasini aniqlash va
yuborish navbatini tayyorlash.

Yuborishning o'zi Celery'da bo'ladi (app/worker/broadcast_tasks.py) — API
faqat qabul qiluvchilar ro'yxatini yozib, taskni navbatga qo'yadi. Shu tufayli
10 000 ta ustozga yuborish ham HTTP so'rovni bloklamaydi.
"""
from __future__ import annotations

import logging
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.broadcast import Broadcast, BroadcastRecipient
from app.models.enums import BroadcastAudience, PlanCode, SubscriptionStatus
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.user import User

log = logging.getLogger(__name__)

# Telegram 4096 belgidan uzun xabarni qabul qilmaydi.
MAX_BODY_LENGTH = 4096


async def resolve_audience(
    db: AsyncSession,
    *,
    audience: str,
    target_user_ids: Sequence[int] | None = None,
) -> list[User]:
    """
    Auditoriya → foydalanuvchilar ro'yxati.

    Bloklangan ustozlarga e'lon yuborilmaydi (ular botdan foydalana olmaydi).
    """
    stmt = select(User).where(User.is_blocked.is_(False))

    if audience == BroadcastAudience.SPECIFIC:
        ids = list(target_user_ids or [])
        if not ids:
            return []
        stmt = stmt.where(User.id.in_(ids))

    elif audience == BroadcastAudience.ACTIVE_SUBSCRIBERS:
        # Pullik tarifdagi faol obunachilar.
        sub_q = (
            select(Subscription.user_id)
            .join(Plan, Plan.id == Subscription.plan_id)
            .where(
                Subscription.status.in_(
                    [SubscriptionStatus.ACTIVE.value, SubscriptionStatus.TRIAL.value]
                ),
                Plan.price_uzs > 0,
            )
        )
        stmt = stmt.where(User.id.in_(sub_q))

    elif audience == BroadcastAudience.FREE_TIER:
        # FREE tarifdagilar + umuman obunasi yo'qlar.
        free_q = (
            select(Subscription.user_id)
            .join(Plan, Plan.id == Subscription.plan_id)
            .where(
                Subscription.status.in_(
                    [SubscriptionStatus.ACTIVE.value, SubscriptionStatus.TRIAL.value]
                ),
                Plan.code == PlanCode.FREE.value,
            )
        )
        paid_q = (
            select(Subscription.user_id)
            .join(Plan, Plan.id == Subscription.plan_id)
            .where(
                Subscription.status.in_(
                    [SubscriptionStatus.ACTIVE.value, SubscriptionStatus.TRIAL.value]
                ),
                Plan.price_uzs > 0,
            )
        )
        stmt = stmt.where(User.id.in_(free_q) | User.id.not_in(paid_q))

    elif audience != BroadcastAudience.ALL:
        raise ValueError(f"Noma'lum auditoriya: {audience}")

    stmt = stmt.order_by(User.id)
    return list((await db.execute(stmt)).scalars().all())


async def prepare_recipients(db: AsyncSession, broadcast: Broadcast) -> int:
    """
    Auditoriyani hisoblab `broadcast_recipients` qatorlarini yaratadi.

    Returns:
        Qabul qiluvchilar soni.
    """
    users = await resolve_audience(
        db,
        audience=broadcast.audience,
        target_user_ids=broadcast.target_user_ids,
    )

    existing = set(
        (
            await db.execute(
                select(BroadcastRecipient.user_id).where(
                    BroadcastRecipient.broadcast_id == broadcast.id
                )
            )
        )
        .scalars()
        .all()
    )

    added = 0
    for user in users:
        if user.id in existing:
            continue
        db.add(
            BroadcastRecipient(
                broadcast_id=broadcast.id,
                user_id=user.id,
                telegram_id=user.telegram_id,
            )
        )
        added += 1

    broadcast.total_count = len(existing) + added
    await db.flush()
    log.info(
        "Broadcast %s: %d qabul qiluvchi tayyorlandi (auditoriya=%s)",
        broadcast.id, broadcast.total_count, broadcast.audience,
    )
    return broadcast.total_count


def render_preview(title: str | None, body: str) -> str:
    """Telegram'da qanday ko'rinishini taxminan ko'rsatadi (sarlavha + matn)."""
    if title:
        return f"<b>{title}</b>\n\n{body}"
    return body
