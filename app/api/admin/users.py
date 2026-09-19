"""
app/api/admin/users.py — Ustozlar (teachers) boshqaruvi.

  GET    /api/admin/users              — sahifalangan, qidiruvli, filtrlangan
  GET    /api/admin/users/{id}         — to'liq profil (drawer uchun)
  POST   /api/admin/users/{id}/block   — bloklash / blokdan chiqarish
  PATCH  /api/admin/users/{id}/role    — admin rolini o'zgartirish (SUPERADMIN)
  GET    /api/admin/users/export       — Excel eksport

Agregatlar (guruh/o'quvchi/test/skan soni) korrelyatsion subquery bilan
hisoblanadi — bir nechta JOIN'ni birlashtirganda yuzaga keladigan Kartezian
ko'paytma muammosidan xoli va sahifalash to'g'ri ishlaydi.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.admin.deps import (
    DbDep,
    PaginationDep,
    require_analyst,
    require_superadmin,
    require_support,
)
from app.models.attempt import Attempt
from app.models.enums import AuditAction
from app.models.group import Group
from app.models.plan import Plan
from app.models.student import Student
from app.models.subscription import LIVE_STATUSES, Subscription
from app.models.test import Test
from app.models.titul import Titul
from app.models.user import User
from app.services.search import LIKE_ESCAPE, like_pattern
from app.schemas.admin.common import Page
from app.schemas.admin.subscriptions import SubscriptionOut
from app.schemas.admin.users import (
    BlockUserIn,
    ChangeAdminRoleIn,
    RecentActivityItem,
    TeacherDetail,
    TeacherGroupBrief,
    TeacherListItem,
    TeacherStats,
)
from app.services import audit as audit_svc
from app.services import subscriptions as subs_svc
from app.services.telegram import TelegramSendError, escape, send_message

log = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["admin:users"])


# ── Yordamchi subquery'lar ──────────────────────────────────────────────


def _groups_count_sq():
    return (
        select(func.count(Group.id))
        .where(Group.owner_id == User.id)
        .correlate(User)
        .scalar_subquery()
    )


def _students_count_sq():
    return (
        select(func.count(Student.id))
        .select_from(Student)
        .join(Group, Group.id == Student.group_id)
        .where(Group.owner_id == User.id)
        .correlate(User)
        .scalar_subquery()
    )


def _tests_count_sq():
    return (
        select(func.count(Test.id))
        .select_from(Test)
        .join(Group, Group.id == Test.group_id)
        .where(Group.owner_id == User.id)
        .correlate(User)
        .scalar_subquery()
    )


def _scans_count_sq(*, since: Optional[datetime] = None):
    stmt = (
        select(func.count(Attempt.id))
        .select_from(Attempt)
        .join(Titul, Titul.id == Attempt.titul_id)
        .join(Test, Test.id == Titul.test_id)
        .join(Group, Group.id == Test.group_id)
        .where(Group.owner_id == User.id)
    )
    if since is not None:
        stmt = stmt.where(Attempt.created_at >= since)
    return stmt.correlate(User).scalar_subquery()


def _apply_user_filters(
    stmt: Select,
    *,
    search: Optional[str],
    blocked: Optional[bool],
    admin_only: bool,
    plan_code: Optional[str],
) -> Select:
    if search:
        pattern = like_pattern(search)
        conditions = [
            User.full_name.ilike(pattern, escape=LIKE_ESCAPE),
            User.username.ilike(pattern, escape=LIKE_ESCAPE),
        ]
        # Raqam kiritilgan bo'lsa telegram_id bo'yicha ham qidiramiz.
        digits = search.strip().lstrip("@")
        if digits.isdigit():
            conditions.append(User.telegram_id == int(digits))
        stmt = stmt.where(or_(*conditions))

    if blocked is not None:
        stmt = stmt.where(User.is_blocked.is_(blocked))

    if admin_only:
        stmt = stmt.where(User.admin_role.is_not(None))

    if plan_code:
        plan_sq = (
            select(Subscription.user_id)
            .join(Plan, Plan.id == Subscription.plan_id)
            .where(
                Plan.code == plan_code,
                Subscription.status.in_(LIVE_STATUSES),
            )
        )
        stmt = stmt.where(User.id.in_(plan_sq))

    return stmt


_SORTABLE = {
    "created_at": User.created_at,
    "full_name": User.full_name,
    "telegram_id": User.telegram_id,
}


@router.get("", response_model=Page[TeacherListItem], dependencies=[Depends(require_analyst)])
async def list_teachers(
    db: DbDep,
    pagination: PaginationDep,
    search: Optional[str] = Query(None, description="Ism, username yoki telegram_id"),
    blocked: Optional[bool] = Query(None, description="Faqat bloklangan/bloklanmagan"),
    admin_only: bool = Query(False, description="Faqat admin roli borlar"),
    plan_code: Optional[str] = Query(None, description="Tarif kodi bo'yicha filtr"),
    sort_by: str = Query("created_at", description="created_at | full_name | telegram_id"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
) -> Page[TeacherListItem]:
    """Ustozlar ro'yxati — qidiruv, filtr, saralash va sahifalash bilan."""
    if sort_by not in _SORTABLE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"sort_by noto'g'ri. Ruxsat etilgan: {', '.join(_SORTABLE)}",
        )

    count_stmt = _apply_user_filters(
        select(func.count(User.id)),
        search=search,
        blocked=blocked,
        admin_only=admin_only,
        plan_code=plan_code,
    )
    total = (await db.execute(count_stmt)).scalar() or 0

    order_col = _SORTABLE[sort_by]
    order = order_col.desc() if sort_dir == "desc" else order_col.asc()

    stmt = (
        select(
            User,
            _groups_count_sq().label("groups_count"),
            _students_count_sq().label("students_count"),
            _tests_count_sq().label("tests_count"),
            _scans_count_sq().label("scans_count"),
            Plan.code.label("plan_code"),
            Plan.name.label("plan_name"),
            Subscription.status.label("subscription_status"),
            Subscription.scans_used.label("scans_used"),
            Plan.monthly_scan_limit.label("monthly_scan_limit"),
            Subscription.bonus_credits.label("bonus_credits"),
        )
        .outerjoin(
            Subscription,
            and_(
                Subscription.user_id == User.id,
                Subscription.status.in_(LIVE_STATUSES),
            ),
        )
        .outerjoin(Plan, Plan.id == Subscription.plan_id)
    )
    stmt = _apply_user_filters(
        stmt, search=search, blocked=blocked, admin_only=admin_only, plan_code=plan_code
    )
    stmt = stmt.order_by(order, User.id.desc()).offset(pagination.offset).limit(pagination.limit)

    rows = (await db.execute(stmt)).all()

    items: list[TeacherListItem] = []
    for row in rows:
        user: User = row.User
        limit = (
            None
            if row.monthly_scan_limit is None
            else row.monthly_scan_limit + (row.bonus_credits or 0)
        )
        items.append(
            TeacherListItem(
                id=user.id,
                telegram_id=user.telegram_id,
                full_name=user.full_name,
                username=user.username,
                role=user.role,
                admin_role=user.admin_role,
                is_blocked=user.is_blocked,
                blocked_reason=user.blocked_reason,
                created_at=user.created_at,
                last_seen_at=user.last_seen_at,
                groups_count=row.groups_count or 0,
                students_count=row.students_count or 0,
                tests_count=row.tests_count or 0,
                scans_count=row.scans_count or 0,
                plan_code=row.plan_code,
                plan_name=row.plan_name,
                subscription_status=row.subscription_status,
                scans_used=row.scans_used or 0,
                scan_limit=limit,
            )
        )

    return Page.build(
        items, page=pagination.page, page_size=pagination.page_size, total=total
    )


@router.get("/export", dependencies=[Depends(require_analyst)])
async def export_teachers(db: DbDep) -> Response:
    """Ustozlar ro'yxatini Excel (.xlsx) sifatida yuklab olish."""
    from app.services.admin_export import export_teachers_excel

    content = await export_teachers_excel(db)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    return Response(
        content=content,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": f'attachment; filename="teachers_{stamp}.xlsx"'
        },
    )


async def _load_user_or_404(db: AsyncSession, user_id: int) -> User:
    user = (
        await db.execute(
            select(User).options(selectinload(User.blocked_by)).where(User.id == user_id)
        )
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    return user


@router.get("/{user_id}", response_model=TeacherDetail, dependencies=[Depends(require_analyst)])
async def get_teacher(user_id: int, db: DbDep) -> TeacherDetail:
    """Ustozning to'liq profili: statistika, obuna, guruhlar, oxirgi faollik."""
    user = await _load_user_or_404(db, user_id)
    month_ago = datetime.now(timezone.utc) - timedelta(days=30)

    stats_row = (
        await db.execute(
            select(
                _groups_count_sq().label("groups_count"),
                _students_count_sq().label("students_count"),
                _tests_count_sq().label("tests_count"),
                _scans_count_sq().label("scans_count"),
                _scans_count_sq(since=month_ago).label("scans_30d"),
            ).where(User.id == user_id)
        )
    ).one()

    # Skan sifati va oxirgi skan vaqti.
    quality = (
        await db.execute(
            select(
                func.count(Attempt.id).filter(
                    and_(Attempt.needs_review.is_(True), Attempt.status == "done")
                ).label("needs_review"),
                func.avg(Attempt.percent).label("avg_percent"),
                func.max(Attempt.created_at).label("last_scan_at"),
            )
            .select_from(Attempt)
            .join(Titul, Titul.id == Attempt.titul_id)
            .join(Test, Test.id == Titul.test_id)
            .join(Group, Group.id == Test.group_id)
            .where(Group.owner_id == user_id)
        )
    ).one()

    stats = TeacherStats(
        groups_count=stats_row.groups_count or 0,
        students_count=stats_row.students_count or 0,
        tests_count=stats_row.tests_count or 0,
        scans_count=stats_row.scans_count or 0,
        scans_30d=stats_row.scans_30d or 0,
        needs_review_count=quality.needs_review or 0,
        avg_score_percent=(
            round(float(quality.avg_percent), 2) if quality.avg_percent is not None else 0.0
        ),
        last_scan_at=quality.last_scan_at,
    )

    # Guruhlar (har birida o'quvchi/test soni).
    group_rows = (
        await db.execute(
            select(
                Group.id,
                Group.name,
                Group.created_at,
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
            )
            .where(Group.owner_id == user_id)
            .order_by(Group.created_at.desc())
        )
    ).all()

    # Oxirgi 10 ta skan.
    activity_rows = (
        await db.execute(
            select(
                Attempt.id,
                Student.full_name.label("student_name"),
                Test.title.label("test_title"),
                Attempt.score,
                Attempt.total,
                Attempt.percent,
                Attempt.status,
                Attempt.needs_review,
                Attempt.created_at,
            )
            .select_from(Attempt)
            .join(Titul, Titul.id == Attempt.titul_id)
            .join(Test, Test.id == Titul.test_id)
            .join(Group, Group.id == Test.group_id)
            .join(Student, Student.id == Titul.student_id)
            .where(Group.owner_id == user_id)
            .order_by(Attempt.created_at.desc())
            .limit(10)
        )
    ).all()

    # Obuna (yo'q bo'lsa yaratmaymiz — faqat ko'rsatamiz).
    sub = await subs_svc.get_active_subscription(db, user_id)
    subscription = None
    if sub is not None:
        snap = subs_svc.snapshot_from(sub)
        subscription = SubscriptionOut(
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

    return TeacherDetail(
        id=user.id,
        telegram_id=user.telegram_id,
        full_name=user.full_name,
        username=user.username,
        role=user.role,
        admin_role=user.admin_role,
        is_blocked=user.is_blocked,
        blocked_reason=user.blocked_reason,
        blocked_at=user.blocked_at,
        blocked_by=user.blocked_by.display_name if user.blocked_by else None,
        created_at=user.created_at,
        last_seen_at=user.last_seen_at,
        stats=stats,
        subscription=subscription,
        groups=[
            TeacherGroupBrief(
                id=g.id,
                name=g.name,
                students_count=g.students_count or 0,
                tests_count=g.tests_count or 0,
                created_at=g.created_at,
            )
            for g in group_rows
        ],
        recent_activity=[
            RecentActivityItem(
                attempt_id=a.id,
                student_name=a.student_name,
                test_title=a.test_title,
                score=a.score,
                total=a.total,
                percent=float(a.percent) if a.percent is not None else None,
                status=a.status,
                needs_review=a.needs_review,
                created_at=a.created_at,
            )
            for a in activity_rows
        ],
    )


@router.post("/{user_id}/block", response_model=TeacherDetail)
async def set_block_state(
    user_id: int,
    body: BlockUserIn,
    request: Request,
    db: DbDep,
    admin: User = Depends(require_support),
) -> TeacherDetail:
    """
    Ustozni bloklaydi yoki blokdan chiqaradi.

    Blok darhol kuchga kiradi: bot middleware'i har xabarda `is_blocked` ni
    tekshiradi, admin API esa `get_current_admin` ichida.
    """
    user = await _load_user_or_404(db, user_id)

    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O'zingizni bloklay olmaysiz",
        )
    if user.is_superadmin and not admin.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SUPERADMIN'ni faqat boshqa SUPERADMIN bloklay oladi",
        )

    before = {"is_blocked": user.is_blocked, "blocked_reason": user.blocked_reason}

    user.is_blocked = body.blocked
    user.blocked_reason = body.reason if body.blocked else None
    user.blocked_at = datetime.now(timezone.utc) if body.blocked else None
    user.blocked_by_id = admin.id if body.blocked else None
    await db.flush()

    await audit_svc.record(
        db,
        actor=admin,
        action=AuditAction.USER_BLOCK if body.blocked else AuditAction.USER_UNBLOCK,
        object_type="user",
        object_id=user.id,
        payload={
            "changes": audit_svc.diff(
                before, {"is_blocked": user.is_blocked, "blocked_reason": user.blocked_reason}
            ),
            "reason": body.reason,
        },
        request=request,
    )
    await db.commit()

    # Foydalanuvchini xabardor qilamiz (yuborilmasa ham amal bekor bo'lmaydi).
    try:
        if body.blocked:
            text = "⛔️ <b>Hisobingiz vaqtincha cheklandi.</b>"
            if body.reason:
                text += f"\n\nSabab: {escape(body.reason)}"
            text += "\n\nSavollar bo'lsa qo'llab-quvvatlash xizmatiga murojaat qiling."
        else:
            text = "✅ <b>Hisobingiz qayta faollashtirildi.</b>\n\nBotdan foydalanishingiz mumkin."
        await send_message(user.telegram_id, text)
    except TelegramSendError as exc:
        log.warning(
            "Blok holati haqida xabar yuborilmadi: tg=%s xato=%s", user.telegram_id, exc
        )

    return await get_teacher(user_id, db)


@router.patch("/{user_id}/role", response_model=TeacherDetail)
async def change_admin_role(
    user_id: int,
    body: ChangeAdminRoleIn,
    request: Request,
    db: DbDep,
    admin: User = Depends(require_superadmin),
) -> TeacherDetail:
    """Admin panel rolini berish yoki olib qo'yish (faqat SUPERADMIN)."""
    user = await _load_user_or_404(db, user_id)

    if user.id == admin.id and body.admin_role != user.admin_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O'z rolingizni o'zgartira olmaysiz — boshqa SUPERADMIN qilsin",
        )

    before = user.admin_role
    user.admin_role = body.admin_role.value if body.admin_role else None
    # Eski `role` ustuni bilan mosligini saqlaymiz (bot mantiqi unga tayanadi).
    user.role = "admin" if user.admin_role else "teacher"
    await db.flush()

    await audit_svc.record(
        db,
        actor=admin,
        action=AuditAction.USER_ROLE_CHANGE,
        object_type="user",
        object_id=user.id,
        payload={"from": before, "to": user.admin_role},
        request=request,
    )
    await db.commit()

    return await get_teacher(user_id, db)
