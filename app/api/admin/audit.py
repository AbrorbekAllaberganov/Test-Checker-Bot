"""
app/api/admin/audit.py — Audit jurnali (faqat o'qish).

  GET /api/admin/audit-logs         — filtrlangan, sahifalangan jurnal
  GET /api/admin/audit-logs/actions — mavjud amal turlari (filtr uchun)
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Select, func, select

from app.api.admin.deps import DbDep, PaginationDep, require_analyst
from app.models.audit_log import AuditLog
from app.models.enums import AuditAction
from app.schemas.admin.audit import AuditLogItem
from app.schemas.admin.common import Page

router = APIRouter(
    prefix="/audit-logs",
    tags=["admin:audit"],
    dependencies=[Depends(require_analyst)],
)


@router.get("", response_model=Page[AuditLogItem])
async def list_audit_logs(
    db: DbDep,
    pagination: PaginationDep,
    action: Optional[str] = Query(None, description="Masalan: user.block"),
    actor_id: Optional[int] = Query(None),
    object_type: Optional[str] = Query(None, description="user | plan | attempt | broadcast"),
    object_id: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
) -> Page[AuditLogItem]:
    """Admin amallari tarixi (yangi → eski)."""

    def apply(stmt: Select) -> Select:
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if actor_id is not None:
            stmt = stmt.where(AuditLog.actor_id == actor_id)
        if object_type:
            stmt = stmt.where(AuditLog.object_type == object_type)
        if object_id:
            stmt = stmt.where(AuditLog.object_id == object_id)
        if date_from is not None:
            stmt = stmt.where(AuditLog.created_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(AuditLog.created_at <= date_to)
        return stmt

    total = (await db.execute(apply(select(func.count(AuditLog.id))))).scalar() or 0

    rows = (
        await db.execute(
            apply(select(AuditLog))
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
    ).scalars().all()

    return Page.build(
        [AuditLogItem.model_validate(r) for r in rows],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )


@router.get("/actions", response_model=list[str])
async def list_actions() -> list[str]:
    """Filtr uchun mavjud amal turlari ro'yxati."""
    return [a.value for a in AuditAction]
