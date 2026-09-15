"""
app/api/admin — React admin paneli uchun REST API (`/api/admin/...`).

Barcha endpointlar JWT Bearer token bilan himoyalangan (`deps.admin_required`).
Token Telegram orqali olinadi: Mini App `initData` imzosi yoki bot yuborgan
bir martalik kod (OTP).
"""
from app.api.admin.router import admin_router

__all__ = ["admin_router"]
