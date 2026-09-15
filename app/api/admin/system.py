"""
app/api/admin/system.py — Tizim holati va nosozliklar.

  GET /api/admin/system/status        — Redis / Celery / Postgres
  GET /api/admin/system/failed-tasks  — xato bilan tugagan skanlar
  GET /api/admin/system/stuck-tasks   — uzoq vaqt 'pending' da qotib qolganlar
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.api.admin.deps import DbDep, PaginationDep, require_analyst
from app.models.attempt import Attempt
from app.schemas.admin.common import Page
from app.schemas.admin.dashboard import SystemStatus
from app.schemas.admin.scans import ScanListItem
from app.services import system_status as status_svc

router = APIRouter(
    prefix="/system",
    tags=["admin:system"],
    dependencies=[Depends(require_analyst)],
)


@router.get("/status", response_model=SystemStatus)
async def get_status(db: DbDep) -> SystemStatus:
    """Barcha komponentlar sog'lig'i (navbat uzunligi va worker'lar bilan)."""
    return SystemStatus(**await status_svc.full_status(db))


def _simple_item(a: Attempt) -> ScanListItem:
    return ScanListItem(
        id=a.id,
        status=a.status,
        needs_review=a.needs_review,
        manual_override=a.manual_override,
        score=a.score,
        total=a.total,
        percent=float(a.percent) if a.percent is not None else None,
        confidence=float(a.confidence) if a.confidence is not None else None,
        error_msg=a.error_msg,
        created_at=a.created_at,
    )


@router.get("/failed-tasks", response_model=Page[ScanListItem])
async def failed_tasks(
    db: DbDep,
    pagination: PaginationDep,
    days: int = Query(7, ge=1, le=90),
) -> Page[ScanListItem]:
    """Xato bilan tugagan skanlar — `error_msg` bilan."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    condition = (Attempt.status == "error") & (Attempt.created_at >= since)

    total = (
        await db.execute(select(func.count(Attempt.id)).where(condition))
    ).scalar() or 0

    rows = (
        await db.execute(
            select(Attempt)
            .where(condition)
            .order_by(Attempt.created_at.desc())
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
    ).scalars().all()

    return Page.build(
        [_simple_item(a) for a in rows],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )


@router.get("/stuck-tasks", response_model=Page[ScanListItem])
async def stuck_tasks(
    db: DbDep,
    pagination: PaginationDep,
    minutes: int = Query(15, ge=1, le=1440, description="Shuncha vaqt 'pending' turganlar"),
) -> Page[ScanListItem]:
    """
    Navbatda qotib qolgan skanlar.

    Odatda OMR bir necha sekundda tugaydi — 15 daqiqadan ortiq 'pending'
    holat worker o'lgani yoki navbat tiqilib qolganini bildiradi.
    """
    threshold = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    condition = (Attempt.status == "pending") & (Attempt.created_at < threshold)

    total = (
        await db.execute(select(func.count(Attempt.id)).where(condition))
    ).scalar() or 0

    rows = (
        await db.execute(
            select(Attempt)
            .where(condition)
            .order_by(Attempt.created_at.asc())
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
    ).scalars().all()

    return Page.build(
        [_simple_item(a) for a in rows],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )
