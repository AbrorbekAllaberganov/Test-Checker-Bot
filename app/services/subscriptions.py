"""
app/services/subscriptions.py — Obuna, kvota va limit mantiqi.

Bu modul obunaning YAGONA manbai (single source of truth):
  • `users` jadvalida `plan_id`/`quota_used` dublikat ustunlari YO'Q —
    joriy tarif va sarf har doim faol `subscriptions` qatoridan o'qiladi.
    Shu tufayli "user.quota_used" va "subscription.scans_used" bir-biriga
    mos kelmay qolish muammosi umuman yuzaga kelmaydi.
  • Kvota davri oylik: `period_end` o'tgan bo'lsa `ensure_period()` uni
    keyingi oyga suradi va `scans_used` ni nolga tushiradi (lazy rollover —
    alohida cron kerak emas).

Asosiy funksiyalar:
    get_active_subscription()  — faol obunani olish (yo'q bo'lsa None)
    ensure_subscription()      — yo'q bo'lsa default tarifda yaratish
    quota_snapshot()           — UI/bot uchun limit holati
    check_scan_allowed()       — skanga ruxsat bormi (bloklamaydi)
    consume_scan()             — skan hisobini +1 (atomar)
    assign_plan()              — admin tarifni almashtiradi
    grant_credits()            — admin qo'shimcha kredit beradi
    cancel_subscription()      — obunani bekor qilish
"""
from __future__ import annotations

import calendar
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models.enums import SubscriptionStatus
from app.models.group import Group
from app.models.plan import Plan
from app.models.student import Student
from app.models.subscription import LIVE_STATUSES, Subscription
from app.models.user import User

log = logging.getLogger(__name__)


class QuotaExceeded(Exception):
    """Kvota tugagan — skan qabul qilinmaydi."""

    def __init__(self, message: str, *, limit: int, used: int) -> None:
        super().__init__(message)
        self.limit = limit
        self.used = used


@dataclass(frozen=True)
class QuotaSnapshot:
    """Bot va admin panel uchun kvota holati."""

    plan_code: str
    plan_name: str
    status: str
    scans_used: int
    scan_limit: Optional[int]      # None = cheksiz
    scans_remaining: Optional[int]  # None = cheksiz
    bonus_credits: int
    period_start: datetime
    period_end: datetime
    ends_at: Optional[datetime]
    max_groups: Optional[int]
    max_students_per_group: Optional[int]

    @property
    def is_unlimited(self) -> bool:
        return self.scan_limit is None

    @property
    def usage_percent(self) -> float:
        if self.scan_limit is None or self.scan_limit == 0:
            return 0.0
        return round(min(100.0, 100.0 * self.scans_used / self.scan_limit), 1)


# ── Davr (period) boshqaruvi ────────────────────────────────────────────


def _next_period_end(start: datetime) -> datetime:
    """
    Boshlanish sanasiga +1 kalendar oy (oddiy 30 kun emas).

    Kun raqami saqlanadi, lekin oy qisqa bo'lsa oyning oxirgi kuniga
    qisqartiriladi (31-yanvar → 28-fevral, kabisa yilida 29-fevral).

    Cheklov: 31-kunda boshlangan obunada sana bir marta 28/30 ga surilib,
    keyingi davrlar o'sha kundan davom etadi. Bu bilim bilan qabul
    qilingan murosa — muqobili obunada alohida "anchor day" ustunini
    saqlash bo'lardi. Hisob-kitobga ta'siri yo'q (davr uzunligi baribir
    bir oy), faqat oylik sana bir-ikki kunga siljiydi.
    """
    year = start.year + (1 if start.month == 12 else 0)
    month = 1 if start.month == 12 else start.month + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return start.replace(year=year, month=month, day=day)


def ensure_period(sub: Subscription, *, now: Optional[datetime] = None) -> bool:
    """
    Kvota davri eskirgan bo'lsa yangisiga o'tkazadi (lazy rollover).

    Returns:
        True — davr yangilandi (chaqiruvchi commit qilishi kerak).
    """
    now = now or datetime.now(timezone.utc)
    if sub.period_end > now:
        return False

    # Bir necha oy o'tib ketgan bo'lsa ham joriy oyga yetib olamiz.
    new_start = sub.period_end
    new_end = _next_period_end(new_start)
    guard = 0
    while new_end <= now and guard < 120:
        new_start = new_end
        new_end = _next_period_end(new_start)
        guard += 1

    sub.period_start = new_start
    sub.period_end = new_end
    sub.scans_used = 0
    # Bonus kreditlar davr bilan birga kuymaydi — ular qo'lda beriladi va
    # admin ularni o'zi nolga tushiradi.
    log.info(
        "Obuna davri yangilandi: sub=%s yangi davr=%s..%s",
        sub.id, new_start.isoformat(), new_end.isoformat(),
    )
    return True


# ── O'qish ──────────────────────────────────────────────────────────────


async def get_active_subscription(
    db: AsyncSession, user_id: int
) -> Optional[Subscription]:
    """
    Foydalanuvchining haqiqatda kuchda bo'lgan obunasi + tarifi.

    `status` ning o'zi yetarli emas: to'lov muddati (`ends_at`) o'tgan
    obuna bazada hamon 'active' bo'lib turishi mumkin (uni o'zgartiradigan
    cron yo'q). Shu sababli muddat shu yerda tekshiriladi va o'tgan bo'lsa
    obuna 'expired' ga o'tkaziladi — aks holda pulini to'lamagan ustoz
    cheksiz ishlayverardi.
    """
    stmt = (
        select(Subscription)
        .options(selectinload(Subscription.plan))
        .where(
            Subscription.user_id == user_id,
            Subscription.status.in_(LIVE_STATUSES),
        )
        .order_by(Subscription.created_at.desc())
        .limit(1)
    )
    sub = (await db.execute(stmt)).scalar_one_or_none()
    if sub is None:
        return None

    if sub.ends_at is not None and sub.ends_at <= datetime.now(timezone.utc):
        sub.status = SubscriptionStatus.EXPIRED.value
        await db.flush()
        log.info(
            "Obuna muddati tugadi: user=%s sub=%s ends_at=%s",
            user_id, sub.id, sub.ends_at.isoformat(),
        )
        return None

    return sub


async def get_default_plan(db: AsyncSession) -> Plan:
    """Sozlamalardagi default tarif (topilmasa — eng arzon faol tarif)."""
    settings = get_settings()
    plan = (
        await db.execute(select(Plan).where(Plan.code == settings.default_plan_code))
    ).scalar_one_or_none()
    if plan is not None:
        return plan

    plan = (
        await db.execute(
            select(Plan)
            .where(Plan.is_active.is_(True))
            .order_by(Plan.sort_order.asc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if plan is None:
        raise RuntimeError(
            "Bazada birorta tarif yo'q — '003' migratsiyasi ishga tushirilganini "
            "tekshiring (alembic upgrade head)."
        )
    return plan


async def ensure_subscription(db: AsyncSession, user_id: int) -> Subscription:
    """
    Faol obunani qaytaradi; bo'lmasa default tarifda yaratadi.

    Davr eskirgan bo'lsa shu yerda yangilanadi. Commit chaqiruvchi zimmasida.
    """
    sub = await get_active_subscription(db, user_id)
    if sub is not None:
        ensure_period(sub)
        return sub

    settings = get_settings()
    plan = await get_default_plan(db)
    now = datetime.now(timezone.utc)

    trial = settings.trial_days > 0
    sub = Subscription(
        user_id=user_id,
        plan_id=plan.id,
        status=(
            SubscriptionStatus.TRIAL.value if trial else SubscriptionStatus.ACTIVE.value
        ),
        starts_at=now,
        ends_at=(now + timedelta(days=settings.trial_days)) if trial else None,
        period_start=now,
        period_end=_next_period_end(now),
        scans_used=0,
        bonus_credits=0,
    )
    db.add(sub)
    await db.flush()
    # `plan` relationship'ini darrov ishlatishimiz uchun yuklab qo'yamiz.
    sub.plan = plan
    log.info("Yangi obuna yaratildi: user=%s plan=%s", user_id, plan.code)
    return sub


def snapshot_from(sub: Subscription) -> QuotaSnapshot:
    """Subscription → QuotaSnapshot (plan yuklangan bo'lishi shart)."""
    return QuotaSnapshot(
        plan_code=sub.plan.code,
        plan_name=sub.plan.name,
        status=sub.status,
        scans_used=sub.scans_used,
        scan_limit=sub.scan_limit,
        scans_remaining=sub.scans_remaining,
        bonus_credits=sub.bonus_credits,
        period_start=sub.period_start,
        period_end=sub.period_end,
        ends_at=sub.ends_at,
        max_groups=sub.plan.max_groups,
        max_students_per_group=sub.plan.max_students_per_group,
    )


async def quota_snapshot(db: AsyncSession, user_id: int) -> QuotaSnapshot:
    """Foydalanuvchi kvotasining joriy holati."""
    sub = await ensure_subscription(db, user_id)
    return snapshot_from(sub)


# ── Yozish ──────────────────────────────────────────────────────────────


async def check_scan_allowed(db: AsyncSession, user_id: int) -> tuple[bool, str]:
    """
    Skanga ruxsat bormi? Hech narsani o'zgartirmaydi.

    Returns:
        (allowed, reason) — reason faqat allowed=False bo'lganda to'ladi.
    """
    snap = await quota_snapshot(db, user_id)
    if snap.scan_limit is None:
        return True, ""
    if snap.scans_used >= snap.scan_limit:
        return False, (
            f"«{snap.plan_name}» tarifidagi oylik limit tugadi "
            f"({snap.scans_used}/{snap.scan_limit}). "
            f"Limit {snap.period_end:%d.%m.%Y} kuni yangilanadi."
        )
    return True, ""


async def consume_scan(db: AsyncSession, user_id: int, *, count: int = 1) -> QuotaSnapshot:
    """
    Skan hisobini oshiradi.

    Poyga (race) holatidan himoya: obuna qatori `FOR UPDATE` bilan qulflanadi,
    shu sababli bir vaqtda kelgan bir nechta skan limitdan oshib ketolmaydi.

    Raises:
        QuotaExceeded — limit tugagan va `ENFORCE_QUOTA=true` bo'lsa.
    """
    settings = get_settings()

    sub = await ensure_subscription(db, user_id)
    # Qatorni qulflab qayta o'qiymiz (ensure_subscription yangi yaratgan bo'lsa ham).
    locked = (
        await db.execute(
            select(Subscription)
            .options(selectinload(Subscription.plan))
            .where(Subscription.id == sub.id)
            .with_for_update()
        )
    ).scalar_one()

    ensure_period(locked)

    limit = locked.scan_limit
    if limit is not None and locked.scans_used + count > limit:
        if settings.enforce_quota:
            raise QuotaExceeded(
                f"Oylik skan limiti tugadi ({locked.scans_used}/{limit}).",
                limit=limit,
                used=locked.scans_used,
            )
        # Soft rejim: limitdan oshsa ham qabul qilamiz, faqat ogohlantiramiz.
        log.warning(
            "Kvota oshib ketdi (ENFORCE_QUOTA=false): user=%s %s/%s",
            user_id, locked.scans_used + count, limit,
        )

    locked.scans_used += count
    await db.flush()
    return snapshot_from(locked)


async def check_group_limit(db: AsyncSession, user_id: int) -> tuple[bool, str]:
    """Yangi guruh ochishga ruxsat bormi (tarif `max_groups` bo'yicha)."""
    snap = await quota_snapshot(db, user_id)
    if snap.max_groups is None:
        return True, ""
    current = (
        await db.execute(
            select(func.count(Group.id)).where(Group.owner_id == user_id)
        )
    ).scalar() or 0
    if current >= snap.max_groups:
        return False, (
            f"«{snap.plan_name}» tarifida ko'pi bilan {snap.max_groups} ta guruh "
            "ochish mumkin. Tarifni yangilang."
        )
    return True, ""


async def check_student_limit(
    db: AsyncSession, user_id: int, group_id: int, *, adding: int = 1
) -> tuple[bool, str]:
    """Guruhga yana `adding` ta o'quvchi qo'shishga ruxsat bormi."""
    snap = await quota_snapshot(db, user_id)
    if snap.max_students_per_group is None:
        return True, ""
    current = (
        await db.execute(
            select(func.count(Student.id)).where(Student.group_id == group_id)
        )
    ).scalar() or 0
    if current + adding > snap.max_students_per_group:
        return False, (
            f"«{snap.plan_name}» tarifida bitta guruhda ko'pi bilan "
            f"{snap.max_students_per_group} ta o'quvchi bo'lishi mumkin "
            f"(hozir {current} ta)."
        )
    return True, ""


# ── Admin amallari ──────────────────────────────────────────────────────


async def assign_plan(
    db: AsyncSession,
    *,
    user: User,
    plan: Plan,
    actor_id: Optional[int] = None,
    duration_days: Optional[int] = None,
    status: str = SubscriptionStatus.ACTIVE.value,
    reset_usage: bool = False,
    note: Optional[str] = None,
) -> Subscription:
    """
    Ustozga tarif biriktiradi (yangilash / pasaytirish / uzaytirish).

    Eski faol obuna `cancelled` ga o'tkaziladi va yangisi yaratiladi — shunda
    tarif tarixi audit uchun saqlanib qoladi.
    """
    now = datetime.now(timezone.utc)

    existing = await get_active_subscription(db, user.id)
    if existing is not None:
        # Xuddi shu tarif — yangi qator yaratmay, uzaytiramiz.
        if existing.plan_id == plan.id and not reset_usage:
            existing.status = status
            if duration_days is not None:
                base = existing.ends_at if (existing.ends_at and existing.ends_at > now) else now
                existing.ends_at = base + timedelta(days=duration_days)
            if note:
                existing.note = note
            ensure_period(existing)
            await db.flush()
            return existing

        existing.status = SubscriptionStatus.CANCELLED.value
        await db.flush()

    sub = Subscription(
        user_id=user.id,
        plan_id=plan.id,
        status=status,
        starts_at=now,
        ends_at=(now + timedelta(days=duration_days)) if duration_days else None,
        period_start=now,
        period_end=_next_period_end(now),
        # Yangi tarif = yangi davr: sarf nolga tushadi. Eskisini ko'chirish
        # ustozni yangi tarifda ham darrov limitga urib qo'yardi.
        scans_used=0,
        bonus_credits=0,
        note=note,
        created_by_id=actor_id,
    )
    db.add(sub)
    await db.flush()
    sub.plan = plan
    return sub


async def grant_credits(
    db: AsyncSession, *, subscription: Subscription, credits: int
) -> Subscription:
    """Joriy davrga qo'shimcha skan krediti beradi (manfiy — qaytarib olish)."""
    subscription.bonus_credits = max(0, subscription.bonus_credits + credits)
    await db.flush()
    return subscription


async def cancel_subscription(
    db: AsyncSession, *, subscription: Subscription, note: Optional[str] = None
) -> Subscription:
    """Obunani bekor qiladi — foydalanuvchi keyingi skanda FREE ga tushadi."""
    subscription.status = SubscriptionStatus.CANCELLED.value
    subscription.ends_at = datetime.now(timezone.utc)
    if note:
        subscription.note = note
    await db.flush()
    return subscription
