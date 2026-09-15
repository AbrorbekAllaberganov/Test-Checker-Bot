"""
app/services/admin_metrics.py — Executive Dashboard uchun agregat so'rovlar.

Barcha hisob-kitob bitta joyda: router'lar faqat chaqiradi va serializatsiya
qiladi. Og'ir `GROUP BY` so'rovlari kun kesimida ishlaydi va `attempts`
jadvalidagi `idx_attempts_status_created` indeksiga tayanadi.

Tushuncha: "OMR aniqlik darajasi" (recognition accuracy) — bu o'quvchilarning
test ballari EMAS. Bu tizim varaqni qanchalik ishonchli o'qiganini bildiradi:

    accuracy = (status='done' VA needs_review=false bo'lgan skanlar) / (jami skanlar)

Ya'ni xato bergan (`error`) yoki ikkilanib qo'lda tekshirishga tushgan
(`needs_review`) skanlar "muvaffaqiyatsiz o'qish" deb hisoblanadi.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attempt import Attempt
from app.models.enums import SubscriptionStatus
from app.models.group import Group
from app.models.plan import Plan
from app.models.student import Student
from app.models.subscription import Subscription
from app.models.test import Test
from app.models.titul import Titul
from app.models.user import User

log = logging.getLogger(__name__)


@dataclass
class KpiSummary:
    total_teachers: int
    active_teachers_30d: int
    blocked_teachers: int
    total_groups: int
    total_students: int
    total_tests: int
    total_scans: int
    scans_today: int
    scans_7d: int
    omr_accuracy: float          # %
    needs_review_count: int
    error_rate: float            # %
    avg_score_percent: float     # %
    paying_subscribers: int
    new_teachers_7d: int


def _utc_today_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


async def kpi_summary(db: AsyncSession) -> KpiSummary:
    """Dashboard yuqorisidagi KPI kartochkalari."""
    today = _utc_today_start()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    total_teachers = (await db.execute(select(func.count(User.id)))).scalar() or 0
    blocked_teachers = (
        await db.execute(select(func.count(User.id)).where(User.is_blocked.is_(True)))
    ).scalar() or 0
    new_teachers_7d = (
        await db.execute(select(func.count(User.id)).where(User.created_at >= week_ago))
    ).scalar() or 0

    # "Faol ustoz" — oxirgi 30 kunda kamida bitta skan yuborgan (titul → test →
    # group → owner zanjiri orqali).
    active_teachers_30d = (
        await db.execute(
            select(func.count(func.distinct(Group.owner_id)))
            .select_from(Attempt)
            .join(Titul, Titul.id == Attempt.titul_id)
            .join(Test, Test.id == Titul.test_id)
            .join(Group, Group.id == Test.group_id)
            .where(Attempt.created_at >= month_ago)
        )
    ).scalar() or 0

    total_groups = (await db.execute(select(func.count(Group.id)))).scalar() or 0
    total_students = (await db.execute(select(func.count(Student.id)))).scalar() or 0
    total_tests = (await db.execute(select(func.count(Test.id)))).scalar() or 0

    # Skan statistikasi — bitta so'rovda barcha kesimlar.
    scan_row = (
        await db.execute(
            select(
                func.count(Attempt.id).label("total"),
                func.count(case((Attempt.created_at >= today, 1))).label("today"),
                func.count(case((Attempt.created_at >= week_ago, 1))).label("week"),
                func.count(
                    case(
                        ((Attempt.status == "done") & (Attempt.needs_review.is_(False)), 1)
                    )
                ).label("clean"),
                func.count(case((Attempt.status == "error", 1))).label("errors"),
                func.count(
                    case(((Attempt.needs_review.is_(True)) & (Attempt.status == "done"), 1))
                ).label("review"),
            )
        )
    ).one()

    total_scans = scan_row.total or 0
    omr_accuracy = round(100.0 * scan_row.clean / total_scans, 2) if total_scans else 0.0
    error_rate = round(100.0 * scan_row.errors / total_scans, 2) if total_scans else 0.0

    avg_percent = (
        await db.execute(
            select(func.avg(Attempt.percent)).where(Attempt.status == "done")
        )
    ).scalar()

    # Pullik obunachilar — narxi > 0 bo'lgan tarifdagi faol obunalar.
    paying = (
        await db.execute(
            select(func.count(Subscription.id))
            .join(Plan, Plan.id == Subscription.plan_id)
            .where(
                Subscription.status.in_(
                    [SubscriptionStatus.ACTIVE.value, SubscriptionStatus.TRIAL.value]
                ),
                Plan.price_uzs > 0,
            )
        )
    ).scalar() or 0

    return KpiSummary(
        total_teachers=total_teachers,
        active_teachers_30d=active_teachers_30d,
        blocked_teachers=blocked_teachers,
        total_groups=total_groups,
        total_students=total_students,
        total_tests=total_tests,
        total_scans=total_scans,
        scans_today=scan_row.today or 0,
        scans_7d=scan_row.week or 0,
        omr_accuracy=omr_accuracy,
        needs_review_count=scan_row.review or 0,
        error_rate=error_rate,
        avg_score_percent=round(float(avg_percent), 2) if avg_percent is not None else 0.0,
        paying_subscribers=paying,
        new_teachers_7d=new_teachers_7d,
    )


async def scan_timeseries(db: AsyncSession, *, days: int = 30) -> list[dict[str, Any]]:
    """
    Kunlik skan hajmi: jami / toza / qayta ko'rik / xato.

    Ma'lumot yo'q kunlar ham 0 bilan to'ldiriladi — grafikda uzilish bo'lmasligi
    uchun (frontend'da bo'sh kunlarni o'zi to'ldirishi kerak emas).
    """
    start = _utc_today_start() - timedelta(days=days - 1)
    day = func.date_trunc("day", Attempt.created_at).label("day")

    rows = (
        await db.execute(
            select(
                day,
                func.count(Attempt.id).label("total"),
                func.count(
                    case(
                        ((Attempt.status == "done") & (Attempt.needs_review.is_(False)), 1)
                    )
                ).label("clean"),
                func.count(
                    case(((Attempt.status == "done") & (Attempt.needs_review.is_(True)), 1))
                ).label("review"),
                func.count(case((Attempt.status == "error", 1))).label("errors"),
            )
            .where(Attempt.created_at >= start)
            .group_by(day)
            .order_by(day)
        )
    ).all()

    by_day = {r.day.date(): r for r in rows}
    out: list[dict[str, Any]] = []
    for i in range(days):
        d = (start + timedelta(days=i)).date()
        r = by_day.get(d)
        out.append(
            {
                "date": d.isoformat(),
                "total": r.total if r else 0,
                "clean": r.clean if r else 0,
                "review": r.review if r else 0,
                "errors": r.errors if r else 0,
            }
        )
    return out


async def active_teachers_timeseries(
    db: AsyncSession, *, days: int = 30
) -> list[dict[str, Any]]:
    """Kuniga nechta noyob ustoz skan yuborgan + nechta yangi ustoz qo'shilgan."""
    start = _utc_today_start() - timedelta(days=days - 1)

    day = func.date_trunc("day", Attempt.created_at).label("day")
    active_rows = (
        await db.execute(
            select(day, func.count(func.distinct(Group.owner_id)).label("active"))
            .select_from(Attempt)
            .join(Titul, Titul.id == Attempt.titul_id)
            .join(Test, Test.id == Titul.test_id)
            .join(Group, Group.id == Test.group_id)
            .where(Attempt.created_at >= start)
            .group_by(day)
            .order_by(day)
        )
    ).all()

    reg_day = func.date_trunc("day", User.created_at).label("day")
    new_rows = (
        await db.execute(
            select(reg_day, func.count(User.id).label("new"))
            .where(User.created_at >= start)
            .group_by(reg_day)
            .order_by(reg_day)
        )
    ).all()

    active_by_day = {r.day.date(): r.active for r in active_rows}
    new_by_day = {r.day.date(): r.new for r in new_rows}

    return [
        {
            "date": (d := (start + timedelta(days=i)).date()).isoformat(),
            "active_teachers": active_by_day.get(d, 0),
            "new_teachers": new_by_day.get(d, 0),
        }
        for i in range(days)
    ]


async def question_count_distribution(db: AsyncSession) -> list[dict[str, Any]]:
    """40 / 50 / 90 savolli testlar va ular bo'yicha skanlar taqsimoti."""
    rows = (
        await db.execute(
            select(
                Test.question_count,
                func.count(func.distinct(Test.id)).label("tests"),
                func.count(Attempt.id).label("scans"),
            )
            .select_from(Test)
            .outerjoin(Titul, Titul.test_id == Test.id)
            .outerjoin(Attempt, Attempt.titul_id == Titul.id)
            .group_by(Test.question_count)
            .order_by(Test.question_count)
        )
    ).all()
    return [
        {
            "question_count": r.question_count,
            "tests": r.tests or 0,
            "scans": r.scans or 0,
        }
        for r in rows
    ]


async def failure_breakdown(db: AsyncSession, *, days: int = 30) -> dict[str, Any]:
    """
    Muvaffaqiyatsiz o'qishlar sabablari — OMR sifatini kuzatish uchun.

    `error_msg` matni bo'yicha guruhlaymiz (QR topilmadi / anchor / boshqa).
    """
    start = _utc_today_start() - timedelta(days=days - 1)

    rows = (
        await db.execute(
            select(
                func.coalesce(Attempt.error_msg, "Noma'lum").label("reason"),
                func.count(Attempt.id).label("count"),
            )
            .where(Attempt.status == "error", Attempt.created_at >= start)
            .group_by("reason")
            .order_by(func.count(Attempt.id).desc())
            .limit(10)
        )
    ).all()

    totals = (
        await db.execute(
            select(
                func.count(Attempt.id).label("total"),
                func.count(
                    case(((Attempt.needs_review.is_(True)) & (Attempt.status == "done"), 1))
                ).label("ambiguous"),
                func.count(case((Attempt.status == "error", 1))).label("errors"),
                func.count(case((Attempt.manual_override.is_(True), 1))).label("overridden"),
            ).where(Attempt.created_at >= start)
        )
    ).one()

    total = totals.total or 0
    return {
        "period_days": days,
        "total_scans": total,
        "ambiguous_count": totals.ambiguous or 0,
        "error_count": totals.errors or 0,
        "overridden_count": totals.overridden or 0,
        "ambiguity_rate": round(100.0 * (totals.ambiguous or 0) / total, 2) if total else 0.0,
        "failure_rate": round(100.0 * (totals.errors or 0) / total, 2) if total else 0.0,
        "reasons": [{"reason": r.reason, "count": r.count} for r in rows],
    }


async def plan_distribution(db: AsyncSession) -> list[dict[str, Any]]:
    """Tariflar kesimida obunachilar va ularning sarfi."""
    rows = (
        await db.execute(
            select(
                Plan.code,
                Plan.name,
                Plan.price_uzs,
                func.count(Subscription.id).label("subscribers"),
                func.coalesce(func.sum(Subscription.scans_used), 0).label("scans_used"),
            )
            .select_from(Plan)
            .outerjoin(
                Subscription,
                (Subscription.plan_id == Plan.id)
                & Subscription.status.in_(
                    [SubscriptionStatus.ACTIVE.value, SubscriptionStatus.TRIAL.value]
                ),
            )
            .group_by(Plan.id, Plan.code, Plan.name, Plan.price_uzs, Plan.sort_order)
            .order_by(Plan.sort_order)
        )
    ).all()
    return [
        {
            "plan_code": r.code,
            "plan_name": r.name,
            "price_uzs": r.price_uzs,
            "subscribers": r.subscribers or 0,
            "scans_used": int(r.scans_used or 0),
            "mrr_uzs": (r.subscribers or 0) * r.price_uzs,
        }
        for r in rows
    ]


async def top_teachers(db: AsyncSession, *, limit: int = 10, days: int = 30) -> list[dict[str, Any]]:
    """Eng ko'p skan yuborgan ustozlar."""
    start = _utc_today_start() - timedelta(days=days - 1)
    rows = (
        await db.execute(
            select(
                User.id,
                User.full_name,
                User.username,
                User.telegram_id,
                func.count(Attempt.id).label("scans"),
            )
            .select_from(Attempt)
            .join(Titul, Titul.id == Attempt.titul_id)
            .join(Test, Test.id == Titul.test_id)
            .join(Group, Group.id == Test.group_id)
            .join(User, User.id == Group.owner_id)
            .where(Attempt.created_at >= start)
            .group_by(User.id, User.full_name, User.username, User.telegram_id)
            .order_by(func.count(Attempt.id).desc())
            .limit(limit)
        )
    ).all()
    return [
        {
            "user_id": r.id,
            "full_name": r.full_name,
            "username": r.username,
            "telegram_id": r.telegram_id,
            "scans": r.scans,
        }
        for r in rows
    ]
