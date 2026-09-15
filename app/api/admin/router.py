"""
app/api/admin/router.py — Barcha admin router'larini bitta `/api/admin`
prefiksi ostida yig'adi.

Tartib muhim: `/auth` birinchi turadi, chunki u yagona himoyalanmagan
bo'lim (token aynan shu yerda olinadi).
"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.admin import (
    audit,
    auth,
    broadcasts,
    dashboard,
    explorer,
    scans,
    subscriptions,
    system,
    users,
)

admin_router = APIRouter(prefix="/api/admin")

admin_router.include_router(auth.router)
admin_router.include_router(dashboard.router)
admin_router.include_router(users.router)
admin_router.include_router(explorer.router)
admin_router.include_router(scans.router)
admin_router.include_router(subscriptions.router)
admin_router.include_router(broadcasts.router)
admin_router.include_router(audit.router)
admin_router.include_router(system.router)

__all__ = ["admin_router"]
