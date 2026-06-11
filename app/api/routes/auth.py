"""
app/api/routes/auth.py — Dashboard autentifikatsiyasi.

Oqim:
  1. Bot (internal key bilan) POST /api/auth/dashboard-token chaqiradi
     → Redis'ga {token: telegram_id} yoziladi, TTL=5 daqiqa
     → token qaytariladi
  2. Bot foydalanuvchiga {web_app_url}?token={token} URL yuboradi
  3. Brauzer GET /api/auth/login?token={token} ga kiradi
     → Redis'dan telegram_id olinadi, token o'chiriladi (one-time)
     → JWT cookie set qilinadi (HttpOnly, 7 kun)
     → /dashboard ga redirect
  4. GET /api/auth/logout — cookie o'chiriladi
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.models.user import User

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

_REDIS_TOKEN_PREFIX = "dashboard_token:"
_REDIS_TOKEN_TTL = 300  # 5 daqiqa


# ─── Redis yordamchi ────────────────────────────────────────────────────────

async def _get_redis():
    """Async Redis klient."""
    import redis.asyncio as aioredis
    settings = get_settings()
    return aioredis.from_url(settings.redis_url, decode_responses=True)


# ─── JWT yordamchi ──────────────────────────────────────────────────────────

def _create_jwt(telegram_id: int) -> str:
    """JWT token yaratish."""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_expire_days)
    payload = {
        "sub": str(telegram_id),
        "telegram_id": telegram_id,
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_jwt(token: str) -> dict:
    """JWT tokenni tekshirish va payload qaytarish. Xato bo'lsa ValueError."""
    settings = get_settings()
    try:
        return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise ValueError("Token muddati o'tgan")
    except jwt.InvalidTokenError:
        raise ValueError("Token noto'g'ri")


# ─── Bot uchun: token generatsiya ───────────────────────────────────────────

class DashboardTokenRequest(BaseModel):
    telegram_id: int


class DashboardTokenResponse(BaseModel):
    token: str
    expires_in: int  # soniya


def _verify_internal_key(request: Request) -> None:
    """Internal API key tekshirish."""
    settings = get_settings()
    key = request.headers.get("X-Internal-Key", "")
    if key != settings.internal_api_key:
        raise HTTPException(status_code=403, detail="Ruxsat yo'q")


@router.post("/dashboard-token", response_model=DashboardTokenResponse)
async def generate_dashboard_token(
    body: DashboardTokenRequest,
    request: Request,
):
    """
    Bot chaqiradi: foydalanuvchi uchun vaqtinchalik token generatsiya qilish.
    Internal API key talab qilinadi.
    """
    _verify_internal_key(request)

    token = str(uuid.uuid4())
    redis = await _get_redis()
    try:
        await redis.set(
            f"{_REDIS_TOKEN_PREFIX}{token}",
            str(body.telegram_id),
            ex=_REDIS_TOKEN_TTL,
        )
    finally:
        await redis.aclose()

    log.info("Dashboard token yaratildi: telegram_id=%d", body.telegram_id)
    return DashboardTokenResponse(token=token, expires_in=_REDIS_TOKEN_TTL)


# ─── Brauzer uchun: token → JWT cookie ──────────────────────────────────────

@router.get("/login")
async def login_with_token(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Brauzer chaqiradi: URL'dagi token ni JWT cookie ga almashtiradi.
    Token bir martalik (Redis'dan o'chiriladi).
    """
    redis = await _get_redis()
    try:
        redis_key = f"{_REDIS_TOKEN_PREFIX}{token}"
        telegram_id_str = await redis.get(redis_key)
        if not telegram_id_str:
            log.warning("Login urinishi: token topilmadi yoki muddati o'tgan: %s", token[:8])
            return RedirectResponse(
                url="/login?error=expired",
                status_code=302,
            )
        # One-time: darhol o'chirish
        await redis.delete(redis_key)
    finally:
        await redis.aclose()

    telegram_id = int(telegram_id_str)

    # Foydalanuvchini DB'dan tekshirish
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        log.warning("Login urinishi: user DB'da topilmadi: telegram_id=%d", telegram_id)
        return RedirectResponse(url="/login?error=not_registered", status_code=302)

    # JWT cookie yaratish
    jwt_token = _create_jwt(telegram_id)
    settings = get_settings()

    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(
        key="dashboard_session",
        value=jwt_token,
        max_age=settings.jwt_expire_days * 24 * 3600,
        httponly=True,       # JS o'qiy olmaydi
        samesite="lax",      # CSRF himoya
        secure=False,        # HTTPS bo'lganda True qiling
    )
    log.info("Dashboard login muvaffaqiyatli: telegram_id=%d, user=%s", telegram_id, user.full_name)
    return response


# ─── Logout ─────────────────────────────────────────────────────────────────

@router.get("/logout")
async def logout():
    """Cookie'ni o'chiradi va login sahifasiga yo'naltiradi."""
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(key="dashboard_session", httponly=True, samesite="lax")
    log.info("Dashboard logout")
    return response


# ─── Dependency: joriy foydalanuvchi ────────────────────────────────────────

async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    FastAPI Dependency: cookie'dan JWT o'qib joriy foydalanuvchini qaytaradi.
    Cookie yo'q yoki noto'g'ri bo'lsa 401 xatosi.
    """
    token = request.cookies.get("dashboard_session")
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Kirish talab qilinadi. Bot orqali tizimga kiring.",
        )
    try:
        payload = decode_jwt(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    telegram_id = payload.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Token noto'g'ri format")

    result = await db.execute(
        select(User).where(User.telegram_id == int(telegram_id))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="Foydalanuvchi topilmadi")

    return user
