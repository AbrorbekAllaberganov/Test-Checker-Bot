"""
app/api/admin/subscriptions.py — Tariflar va obunalar boshqaruvi.

  GET    /api/admin/plans                        — tariflar ro'yxati
  POST   /api/admin/plans                        — yangi tarif (SUPERADMIN)
  PUT    /api/admin/plans/{id}                   — tarifni tahrirlash (SUPERADMIN)
  GET    /api/admin/subscriptions                — ustozlar + obunalari
  POST   /api/admin/subscriptions/{user_id}/assign  — tarif biriktirish
  POST   /api/admin/subscriptions/{user_id}/credits — qo'shimcha kredit
  POST   /api/admin/subscriptions/{user_id}/cancel  — obunani bekor qilish
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.deps import DbDep, PaginationDep, require_analyst, require_superadmin
from app.models.enums import AuditAction
from app.models.plan import Plan
from app.models.subscription import LIVE_STATUSES, Subscription
from app.models.user import User
from app.services.search import LIKE_ESCAPE, like_pattern
from app.schemas.admin.common import Page
from app.schemas.admin.subscriptions import (
    AssignPlanIn,
    GrantCreditsIn,
    PlanIn,
    PlanOut,
    SubscriptionOut,
    SubscriptionRow,
)
from app.services import audit as audit_svc
from app.services import subscriptions as subs_svc

log = logging.getLogger(__name__)

router = APIRouter(tags=["admin:subscriptions"])


def _to_subscription_out(sub: Subscription) -> SubscriptionOut:
    snap = subs_svc.snapshot_from(sub)
    return SubscriptionOut(
        id=sub.id,
        plan_id=sub.plan_id,
        plan_code=snap.plan_code,
        plan_name=snap.plan_name,
        status=sub.status,
        starts_at=sub.starts_at,
        ends_at=sub.ends_at,
        period_start=sub.period_start,
        period_end=sub.period_end,
        scans_used=sub.scans_used,
        bonus_credits=sub.bonus_credits,
        scan_limit=snap.scan_limit,
        scans_remaining=snap.scans_remaining,
        usage_percent=snap.usage_percent,
        max_groups=snap.max_groups,
        max_students_per_group=snap.max_students_per_group,
        note=sub.note,
    )


# ── Tariflar ────────────────────────────────────────────────────────────


@router.get("/plans", response_model=list[PlanOut], dependencies=[Depends(require_analyst)])
async def list_plans(
    db: DbDep,
    include_inactive: bool = Query(False),
) -> list[PlanOut]:
    """Tariflar va har biridagi faol obunachilar soni."""
    subscribers_sq = (
        select(func.count(Subscription.id))
        .where(
            Subscription.plan_id == Plan.id,
            Subscription.status.in_(LIVE_STATUSES),
        )
        .correlate(Plan)
        .scalar_subquery()
    )

    stmt = select(Plan, subscribers_sq.label("subscribers_count"))
    if not include_inactive:
        stmt = stmt.where(Plan.is_active.is_(True))
    stmt = stmt.order_by(Plan.sort_order, Plan.id)

    rows = (await db.execute(stmt)).all()
    out: list[PlanOut] = []
    for row in rows:
        item = PlanOut.model_validate(row.Plan)
        item.subscribers_count = row.subscribers_count or 0
        out.append(item)
    return out


@router.post("/plans", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
async def create_plan(
    body: PlanIn,
    request: Request,
    db: DbDep,
    admin: User = Depends(require_superadmin),
) -> PlanOut:
    """Yangi tarif yaratish."""
    existing = (
        await db.execute(select(Plan).where(Plan.code == body.code))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"'{body.code}' kodli tarif allaqachon mavjud",
        )

    plan = Plan(**body.model_dump())
    db.add(plan)
    await db.flush()

    await audit_svc.record(
        db,
        actor=admin,
        action=AuditAction.PLAN_CREATE,
        object_type="plan",
        object_id=plan.id,
        payload=body.model_dump(),
        request=request,
    )
    await db.commit()

    return PlanOut.model_validate(plan)


@router.put("/plans/{plan_id}", response_model=PlanOut)
async def update_plan(
    plan_id: int,
    body: PlanIn,
    request: Request,
    db: DbDep,
    admin: User = Depends(require_superadmin),
) -> PlanOut:
    """
    Tarifni tahrirlash.

    DIQQAT: limitni o'zgartirish shu tarifdagi BARCHA faol obunalarga darhol
    ta'sir qiladi (limit obunada emas, tarifda saqlanadi).
    """
    plan = (await db.execute(select(Plan).where(Plan.id == plan_id))).scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=404, detail="Tarif topilmadi")

    if body.code != plan.code:
        clash = (
            await db.execute(
                select(Plan).where(Plan.code == body.code, Plan.id != plan_id)
            )
        ).scalar_one_or_none()
        if clash is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"'{body.code}' kodli boshqa tarif mavjud",
            )

    before = {
        "code": plan.code,
        "name": plan.name,
        "price_uzs": plan.price_uzs,
        "max_groups": plan.max_groups,
        "max_students_per_group": plan.max_students_per_group,
        "monthly_scan_limit": plan.monthly_scan_limit,
        "is_active": plan.is_active,
    }

    for field, value in body.model_dump().items():
        setattr(plan, field, value)
    await db.flush()

    await audit_svc.record(
        db,
        actor=admin,
        action=AuditAction.PLAN_UPDATE,
        object_type="plan",
        object_id=plan.id,
        payload={"changes": audit_svc.diff(before, body.model_dump())},
        request=request,
    )
    await db.commit()

    return PlanOut.model_validate(plan)


# ── Obunalar ────────────────────────────────────────────────────────────


@router.get(
    "/subscriptions",
    response_model=Page[SubscriptionRow],
    dependencies=[Depends(require_analyst)],
)
async def list_subscriptions(
    db: DbDep,
    pagination: PaginationDep,
    plan_code: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None, description="Ism, username yoki telegram_id"),
    over_quota: bool = Query(False, description="Faqat limitdan oshganlar"),
) -> Page[SubscriptionRow]:
    """Ustozlar va ularning joriy obunasi (obunasi yo'qlar ham ko'rinadi)."""

    def apply(stmt: Select) -> Select:
        stmt = stmt.outerjoin(
            Subscription,
            and_(
                Subscription.user_id == User.id,
                Subscription.status.in_(LIVE_STATUSES),
            ),
        ).outerjoin(Plan, Plan.id == Subscription.plan_id)

        if plan_code:
            stmt = stmt.where(Plan.code == plan_code)
        if status_filter:
            stmt = stmt.where(Subscription.status == status_filter)
        if search:
            pattern = like_pattern(search)
            conditions = [
                User.full_name.ilike(pattern, escape=LIKE_ESCAPE),
                User.username.ilike(pattern, escape=LIKE_ESCAPE),
            ]
            digits = search.strip().lstrip("@")
            if digits.isdigit():
                conditions.append(User.telegram_id == int(digits))
            stmt = stmt.where(or_(*conditions))
        if over_quota:
            stmt = stmt.where(
                Plan.monthly_scan_limit.is_not(None),
                Subscription.scans_used
                >= Plan.monthly_scan_limit + Subscription.bonus_credits,
            )
        return stmt

    total = (
        await db.execute(apply(select(func.count(User.id)).select_from(User)))
    ).scalar() or 0

    rows = (
        await db.execute(
            apply(select(User, Subscription, Plan).select_from(User))
            .order_by(User.created_at.desc())
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
    ).all()

    items: list[SubscriptionRow] = []
    for row in rows:
        user: User = row.User
        sub: Optional[Subscription] = row.Subscription
        out = None
        if sub is not None:
            # `plan` relationship'ini qo'lda bog'laymiz — qo'shimcha so'rov shart emas.
            sub.plan = row.Plan
            out = _to_subscription_out(sub)
        items.append(
            SubscriptionRow(
                user_id=user.id,
                telegram_id=user.telegram_id,
                full_name=user.full_name,
                username=user.username,
                is_blocked=user.is_blocked,
                subscription=out,
            )
        )

    return Page.build(
        items, page=pagination.page, page_size=pagination.page_size, total=total
    )


async def _load_user(db: AsyncSession, user_id: int) -> User:
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    return user


@router.post("/subscriptions/{user_id}/assign", response_model=SubscriptionOut)
async def assign_plan(
    user_id: int,
    body: AssignPlanIn,
    request: Request,
    db: DbDep,
    admin: User = Depends(require_superadmin),
) -> SubscriptionOut:
    """Ustozga tarif biriktirish / yangilash / uzaytirish."""
    user = await _load_user(db, user_id)
    plan = (
        await db.execute(select(Plan).where(Plan.id == body.plan_id))
    ).scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=404, detail="Tarif topilmadi")

    current = await subs_svc.get_active_subscription(db, user_id)
    before = (
        {
            "plan_code": current.plan.code,
            "status": current.status,
            "ends_at": current.ends_at.isoformat() if current.ends_at else None,
        }
        if current
        else {}
    )

    sub = await subs_svc.assign_plan(
        db,
        user=user,
        plan=plan,
        actor_id=admin.id,
        duration_days=body.duration_days,
        status=body.status.value,
        reset_usage=body.reset_usage,
        note=body.note,
    )

    await audit_svc.record(
        db,
        actor=admin,
        action=AuditAction.SUBSCRIPTION_ASSIGN,
        object_type="user",
        object_id=user.id,
        payload={
            "before": before,
            "after": {
                "plan_code": plan.code,
                "status": sub.status,
                "ends_at": sub.ends_at.isoformat() if sub.ends_at else None,
                "reset_usage": body.reset_usage,
            },
            "note": body.note,
        },
        request=request,
    )
    await db.commit()

    return _to_subscription_out(sub)


@router.post("/subscriptions/{user_id}/credits", response_model=SubscriptionOut)
async def grant_credits(
    user_id: int,
    body: GrantCreditsIn,
    request: Request,
    db: DbDep,
    admin: User = Depends(require_superadmin),
) -> SubscriptionOut:
    """Joriy davrga qo'shimcha skan krediti berish (manfiy — qaytarib olish)."""
    await _load_user(db, user_id)
    sub = await subs_svc.ensure_subscription(db, user_id)

    before = sub.bonus_credits
    await subs_svc.grant_credits(db, subscription=sub, credits=body.credits)

    await audit_svc.record(
        db,
        actor=admin,
        action=AuditAction.SUBSCRIPTION_CREDITS,
        object_type="user",
        object_id=user_id,
        payload={
            "credits": body.credits,
            "bonus_before": before,
            "bonus_after": sub.bonus_credits,
            "note": body.note,
        },
        request=request,
    )
    await db.commit()

    return _to_subscription_out(sub)


@router.post("/subscriptions/{user_id}/cancel", response_model=SubscriptionOut)
async def cancel_subscription(
    user_id: int,
    request: Request,
    db: DbDep,
    admin: User = Depends(require_superadmin),
    note: Optional[str] = Query(None, max_length=500),
) -> SubscriptionOut:
    """Faol obunani bekor qilish."""
    sub = await subs_svc.get_active_subscription(db, user_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="Faol obuna topilmadi")

    await subs_svc.cancel_subscription(db, subscription=sub, note=note)

    await audit_svc.record(
        db,
        actor=admin,
        action=AuditAction.SUBSCRIPTION_CANCEL,
        object_type="user",
        object_id=user_id,
        payload={"plan_code": sub.plan.code, "note": note},
        request=request,
    )
    await db.commit()

    return _to_subscription_out(sub)
