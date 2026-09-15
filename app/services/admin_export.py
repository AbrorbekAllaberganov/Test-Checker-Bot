"""
app/services/admin_export.py — Admin panel uchun Excel eksportlari.

Guruh/test/o'quvchi natijalari uchun mavjud `app/services/excel.py` ishlatiladi;
bu modul faqat admin'ga xos kesimlarni (ustozlar ro'yxati, obuna holati)
qo'shadi va o'sha fayldagi stil funksiyasini qayta ishlatadi.
"""
from __future__ import annotations

from openpyxl import Workbook
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attempt import Attempt
from app.models.group import Group
from app.models.plan import Plan
from app.models.student import Student
from app.models.subscription import LIVE_STATUSES, Subscription
from app.models.test import Test
from app.models.titul import Titul
from app.models.user import User
from app.services.excel import _style_sheet, _to_bytes


async def export_teachers_excel(db: AsyncSession) -> bytes:
    """Barcha ustozlar: faollik, obuna va kvota kesimida."""
    groups_sq = (
        select(func.count(Group.id))
        .where(Group.owner_id == User.id)
        .correlate(User)
        .scalar_subquery()
    )
    students_sq = (
        select(func.count(Student.id))
        .select_from(Student)
        .join(Group, Group.id == Student.group_id)
        .where(Group.owner_id == User.id)
        .correlate(User)
        .scalar_subquery()
    )
    tests_sq = (
        select(func.count(Test.id))
        .select_from(Test)
        .join(Group, Group.id == Test.group_id)
        .where(Group.owner_id == User.id)
        .correlate(User)
        .scalar_subquery()
    )
    scans_sq = (
        select(func.count(Attempt.id))
        .select_from(Attempt)
        .join(Titul, Titul.id == Attempt.titul_id)
        .join(Test, Test.id == Titul.test_id)
        .join(Group, Group.id == Test.group_id)
        .where(Group.owner_id == User.id)
        .correlate(User)
        .scalar_subquery()
    )

    rows = (
        await db.execute(
            select(
                User.id,
                User.full_name,
                User.username,
                User.telegram_id,
                User.is_blocked,
                User.blocked_reason,
                User.created_at,
                groups_sq.label("groups_count"),
                students_sq.label("students_count"),
                tests_sq.label("tests_count"),
                scans_sq.label("scans_count"),
                Plan.name.label("plan_name"),
                Subscription.status.label("sub_status"),
                Subscription.scans_used,
                Plan.monthly_scan_limit,
                Subscription.bonus_credits,
            )
            .outerjoin(
                Subscription,
                and_(
                    Subscription.user_id == User.id,
                    Subscription.status.in_(LIVE_STATUSES),
                ),
            )
            .outerjoin(Plan, Plan.id == Subscription.plan_id)
            .order_by(User.created_at.desc())
        )
    ).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Ustozlar"
    ws.append(
        [
            "ID",
            "F.I.Sh.",
            "Username",
            "Telegram ID",
            "Tarif",
            "Obuna holati",
            "Skan (davr)",
            "Limit",
            "Guruhlar",
            "O'quvchilar",
            "Testlar",
            "Jami skanlar",
            "Bloklangan",
            "Blok sababi",
            "Ro'yxatdan o'tgan",
        ]
    )

    for r in rows:
        limit = (
            "Cheksiz"
            if r.monthly_scan_limit is None
            else r.monthly_scan_limit + (r.bonus_credits or 0)
        )
        ws.append(
            [
                r.id,
                r.full_name or "",
                f"@{r.username}" if r.username else "",
                r.telegram_id,
                r.plan_name or "—",
                r.sub_status or "—",
                r.scans_used or 0,
                limit,
                r.groups_count or 0,
                r.students_count or 0,
                r.tests_count or 0,
                r.scans_count or 0,
                "Ha" if r.is_blocked else "Yo'q",
                r.blocked_reason or "",
                # Excel timezone-aware datetime'ni qabul qilmaydi.
                r.created_at.replace(tzinfo=None) if r.created_at else None,
            ]
        )

    _style_sheet(ws)
    return _to_bytes(wb)
