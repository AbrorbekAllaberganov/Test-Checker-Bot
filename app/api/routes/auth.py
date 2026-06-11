"""
app/api/routes/auth.py — Telegram Mini App (Web App) autentifikatsiyasi.

Oqim (Mini App):
  1. Foydalanuvchi botdagi "📊 Dashboard" web_app tugmasini bosadi
     → Telegram Mini App'ni ochadi va `initData` (imzolangan) beradi
  2. Frontend har bir API so'roviga `Authorization: tma <initData>` header qo'shadi
  3. Backend `initData` imzosini bot_token bilan HMAC-SHA256 orqali tekshiradi
     → ichidan telegram user.id olinadi, DB'dan User topiladi
  4. Token/cookie/Redis kerak emas — imzo har so'rovda tekshiriladi

Bu eski Redis-token + JWT-cookie oqimining o'rnini bosadi.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from urllib.parse import parse_qsl

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.models.user import User

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# initData auth_date dan keyin necha soniyada eskirgan deb hisoblanadi.
# 0 — eskirishni tekshirmaslik (Mini App sessiyasi uzoq ochiq turishi mumkin).
_INIT_DATA_MAX_AGE = 0


# ─── Telegram Mini App initData validatsiyasi ───────────────────────────────

def validate_init_data(init_data: str) -> dict:
    """
    Telegram WebApp `initData` qatorini tekshiradi.

    Algoritm (Telegram rasmiy):
        secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)
        hash       = HMAC_SHA256(key=secret_key,  msg=data_check_string)

    Muvaffaqiyatli bo'lsa — Telegram `user` dict qaytaradi.
    Xato bo'lsa — ValueError ko'taradi.
    """
    settings = get_settings()

    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    except Exception:
        raise ValueError("initData formati noto'g'ri")

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise ValueError("hash topilmadi")

    # data_check_string — qolgan barcha maydonlar alifbo tartibida
    data_check_string = "\n".join(f"{k}={parsed[k]}" for k in sorted(parsed.keys()))

    secret_key = hmac.new(b"WebAppData", settings.bot_token.encode(), hashlib.sha256).digest()
    calc_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calc_hash, received_hash):
        raise ValueError("imzo noto'g'ri")

    # Ixtiyoriy: auth_date eskirganini tekshirish
    if _INIT_DATA_MAX_AGE > 0:
        import time
        try:
            auth_date = int(parsed.get("auth_date", "0"))
        except ValueError:
            auth_date = 0
        if auth_date and (time.time() - auth_date) > _INIT_DATA_MAX_AGE:
            raise ValueError("initData muddati o'tgan")

    user_raw = parsed.get("user")
    if not user_raw:
        raise ValueError("user ma'lumoti topilmadi")
    try:
        return json.loads(user_raw)
    except Exception:
        raise ValueError("user ma'lumoti JSON formatida emas")


def _extract_init_data(request: Request) -> str:
    """So'rov header'laridan initData qatorini ajratib oladi."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("tma "):
        return auth[4:].strip()
    # Muqobil header (frontend qulayligi uchun)
    return request.headers.get("X-Telegram-Init-Data", "").strip()


# ─── Dependency: joriy foydalanuvchi (Mini App) ─────────────────────────────

async def get_webapp_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    FastAPI Dependency: `initData` imzosini tekshirib joriy foydalanuvchini qaytaradi.
    Imzo yo'q yoki noto'g'ri bo'lsa — 401.
    """
    init_data = _extract_init_data(request)
    if not init_data:
        raise HTTPException(
            status_code=401,
            detail="Avtorizatsiya yo'q. Dashboard'ni bot orqali (Mini App) oching.",
        )

    try:
        tg_user = validate_init_data(init_data)
    except ValueError as e:
        log.warning("Mini App auth rad etildi: %s", e)
        raise HTTPException(status_code=401, detail=f"Avtorizatsiya xatosi: {e}")

    telegram_id = tg_user.get("id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Telegram ID topilmadi")

    result = await db.execute(select(User).where(User.telegram_id == int(telegram_id)))
    user = result.scalar_one_or_none()
    if user is None:
        log.warning("Mini App: user DB'da topilmadi: telegram_id=%s", telegram_id)
        raise HTTPException(
            status_code=401,
            detail="Siz ro'yxatdan o'tmagansiz. Avval botda /start buyrug'ini yuboring.",
        )

    return user


# ─── /api/auth/me — joriy foydalanuvchi haqida ma'lumot ─────────────────────

@router.get("/me")
async def me(user: User = Depends(get_webapp_user)):
    """Frontend uchun: joriy foydalanuvchi ma'lumoti (auth tekshiruvi ham)."""
    return {
        "telegram_id": user.telegram_id,
        "full_name": user.full_name,
        "username": user.username,
    }
