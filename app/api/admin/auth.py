"""
app/api/admin/auth.py — Admin panelga kirish (JWT).

Parol yo'q — admin o'zini Telegram orqali tasdiqlaydi:

  A) Kompyuter brauzeri (asosiy yo'l):
       POST /api/admin/auth/otp/request  {telegram_id}
         → bot admin'ga 6 xonali kod yuboradi (Redis'da 5 daqiqa yashaydi)
       POST /api/admin/auth/otp/verify   {telegram_id, code}
         → {access_token, refresh_token, profile}

  B) Telegram Mini App ichida:
       POST /api/admin/auth/telegram     {init_data}
         → initData imzosi HMAC bilan tekshiriladi → shu tokenlar

Bootstrap: `.env` dagi `ADMIN_TELEGRAM_IDS` ro'yxatidagi telegram_id birinchi
marta kirganda avtomatik SUPERADMIN qilib belgilanadi — panelga birinchi
kirish uchun bazaga qo'lda SQL yozish shart emas.

Xavfsizlik choralari:
  • Kod faqat DB'da mavjud VA admin huquqi bor foydalanuvchiga yuboriladi.
  • Javob har doim bir xil ("kod yuborildi") — telegram_id ni tanlab olishga
    (user enumeration) yo'l qo'ymaslik uchun.
  • Kodni tekshirish urinishlari 5 tadan oshsa kod bekor qilinadi.
  • Qayta so'rash `ADMIN_OTP_RESEND_SECONDS` bilan cheklanadi.
  • IP bo'yicha limit (T-30): telegram_id limitidan mustaqil — aks holda
    bitta IP'dan barcha adminlarga navbatma-navbat kod spam qilish mumkin edi.
  • Refresh ROTATSIYA: eski token darhol bekor qilinadi; allaqachon
    ishlatilgan refresh qayta kelsa butun sessiya oilasi bekor qilinadi
    (token o'g'irlanganining belgisi).
  • `POST /logout` — access va refresh tokenlarni bekor qiladi.
"""
from __future__ import annotations

import hmac
import logging
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.deps import AdminDep, bearer_scheme
from app.api.routes.auth import validate_init_data
from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    new_family_id,
)
from app.models.enums import AdminRole, AuditAction
from app.models.user import User
from app.schemas.admin.auth import (
    AdminProfile,
    LogoutIn,
    LogoutOut,
    OtpRequestIn,
    OtpRequestOut,
    OtpVerifyIn,
    RefreshIn,
    TelegramLoginIn,
    TokenPair,
)
from app.services import audit as audit_svc
from app.services import token_store
from app.services.audit import client_ip
from app.services.telegram import TelegramSendError, send_message

log = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["admin:auth"])

_OTP_KEY = "admin:otp:{telegram_id}"
_OTP_ATTEMPTS_KEY = "admin:otp:attempts:{telegram_id}"
_OTP_RESEND_KEY = "admin:otp:resend:{telegram_id}"
MAX_OTP_ATTEMPTS = 5

# IP bo'yicha limitlar: (nom, urinishlar, oyna sekundda).
# `otp/request` bot orqali xabar yuboradi — eng qattiq chegara.
RATE_OTP_REQUEST = ("otp_request", 10, 3600)
RATE_OTP_VERIFY = ("otp_verify", 20, 600)
RATE_TELEGRAM_LOGIN = ("tg_login", 30, 600)


def _redis():
    """Har chaqiruvda yangi async Redis klienti (pool Redis kutubxonasida)."""
    return token_store.redis_client()


async def _enforce_ip_limit(redis, rule: tuple[str, int, int], request: Request) -> None:
    """IP bo'yicha limitni qo'llaydi; oshsa 429."""
    name, limit, window = rule
    allowed = await token_store.rate_limit(
        redis, name=name, ident=client_ip(request), limit=limit, window_seconds=window
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Juda ko'p urinish. Birozdan keyin qayta urinib ko'ring.",
        )


async def _bootstrap_admin_role(db: AsyncSession, user: User) -> None:
    """`.env` dagi ADMIN_TELEGRAM_IDS ro'yxatidagilarga SUPERADMIN berish."""
    settings = get_settings()
    if user.admin_role:
        return
    if user.telegram_id in (settings.admin_telegram_ids or []):
        user.admin_role = AdminRole.SUPERADMIN.value
        await db.flush()
        log.info(
            "Bootstrap: telegram_id=%s SUPERADMIN qilib belgilandi (.env ro'yxati)",
            user.telegram_id,
        )


def _token_pair(user: User, family: str) -> TokenPair:
    """Bitta sessiya oilasi uchun access+refresh juftligi."""
    settings = get_settings()
    return TokenPair(
        access_token=create_access_token(
            user_id=user.id,
            telegram_id=user.telegram_id,
            admin_role=user.admin_role or "",
            family=family,
        ),
        refresh_token=create_refresh_token(
            user_id=user.id,
            telegram_id=user.telegram_id,
            admin_role=user.admin_role or "",
            family=family,
        ),
        expires_in=settings.admin_access_token_minutes * 60,
        profile=AdminProfile.model_validate(user),
    )


async def _issue_tokens(
    db: AsyncSession, user: User, request: Request
) -> TokenPair:
    """Yangi login: yangi sessiya oilasi + audit yozuvi."""
    await audit_svc.record(
        db,
        actor=user,
        action=AuditAction.ADMIN_LOGIN,
        object_type="user",
        object_id=user.id,
        payload={"admin_role": user.admin_role},
        request=request,
    )
    return _token_pair(user, new_family_id())


async def _load_admin(db: AsyncSession, telegram_id: int) -> Optional[User]:
    """Telegram ID bo'yicha adminni topadi (bootstrap rolini ham qo'llaydi)."""
    user = (
        await db.execute(select(User).where(User.telegram_id == telegram_id))
    ).scalar_one_or_none()
    if user is None:
        return None
    await _bootstrap_admin_role(db, user)
    if not user.is_admin or user.is_blocked:
        return None
    return user


# ─── A) Bir martalik kod (OTP) ──────────────────────────────────────────


@router.post("/otp/request", response_model=OtpRequestOut)
async def request_otp(
    body: OtpRequestIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> OtpRequestOut:
    """
    Telegram orqali bir martalik kod yuborishni so'raydi.

    Javob har doim bir xil — telegram_id admin ekanini yoki emasligini
    oshkor qilmaydi.
    """
    settings = get_settings()
    generic = OtpRequestOut(
        ok=True,
        message=(
            "Agar bu Telegram ID admin sifatida ro'yxatdan o'tgan bo'lsa, "
            "botga kod yuborildi."
        ),
        expires_in_seconds=settings.admin_otp_ttl_seconds,
    )

    redis = _redis()
    try:
        # IP limiti telegram_id limitidan OLDIN: aks holda bitta IP'dan
        # boshqa-boshqa telegram_id lar bilan cheksiz kod yuborish mumkin edi.
        await _enforce_ip_limit(redis, RATE_OTP_REQUEST, request)

        # DIQQAT: "qayta so'rash" javobi ham, "kod yuborildi" javobi ham bir
        # xil ko'rinishi kerak. Aks holda `retry_after_seconds` faqat haqiqiy
        # adminlar uchun qaytib, admin telegram_id'larini birma-bir topish
        # (enumeratsiya) mumkin bo'lib qolardi. Shu sababli avval
        # foydalanuvchini tekshiramiz va admin bo'lmasa — hech qanday
        # farqlovchi ma'lumot bermaymiz.
        user = await _load_admin(db, body.telegram_id)
        if user is None:
            log.warning(
                "OTP so'rovi rad etildi (admin emas yoki topilmadi): tg=%s",
                body.telegram_id,
            )
            return generic

        resend_key = _OTP_RESEND_KEY.format(telegram_id=body.telegram_id)
        ttl = await redis.ttl(resend_key)
        if ttl and ttl > 0:
            return OtpRequestOut(
                ok=False,
                message=f"Yangi kodni {ttl} sekunddan keyin so'rashingiz mumkin.",
                retry_after_seconds=ttl,
                expires_in_seconds=settings.admin_otp_ttl_seconds,
            )

        code = f"{secrets.randbelow(1_000_000):06d}"
        await redis.setex(
            _OTP_KEY.format(telegram_id=body.telegram_id),
            settings.admin_otp_ttl_seconds,
            code,
        )
        await redis.delete(_OTP_ATTEMPTS_KEY.format(telegram_id=body.telegram_id))
        await redis.setex(resend_key, settings.admin_otp_resend_seconds, "1")

        try:
            await send_message(
                body.telegram_id,
                "🔐 <b>Admin panelga kirish kodi</b>\n\n"
                f"<code>{code}</code>\n\n"
                f"Kod {settings.admin_otp_ttl_seconds // 60} daqiqa amal qiladi.\n"
                "<i>Agar bu siz bo'lmasangiz — bu xabarni e'tiborsiz qoldiring.</i>",
            )
        except TelegramSendError as exc:
            log.error("OTP kodini yuborib bo'lmadi: tg=%s xato=%s", body.telegram_id, exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    "Telegram orqali kod yuborilmadi. Botga /start yuborganingizni "
                    "tekshiring."
                ),
            ) from exc

        await db.commit()
        return generic
    finally:
        await redis.aclose()


@router.post("/otp/verify", response_model=TokenPair)
async def verify_otp(
    body: OtpVerifyIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenPair:
    """Kodni tekshirib JWT juftligini qaytaradi."""
    redis = _redis()
    try:
        await _enforce_ip_limit(redis, RATE_OTP_VERIFY, request)

        key = _OTP_KEY.format(telegram_id=body.telegram_id)
        attempts_key = _OTP_ATTEMPTS_KEY.format(telegram_id=body.telegram_id)

        stored = await redis.get(key)
        if stored is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Kod topilmadi yoki muddati tugagan. Yangi kod so'rang.",
            )

        attempts = await redis.incr(attempts_key)
        await redis.expire(attempts_key, get_settings().admin_otp_ttl_seconds)
        if attempts > MAX_OTP_ATTEMPTS:
            await redis.delete(key, attempts_key)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Juda ko'p urinish. Yangi kod so'rang.",
            )

        # Doimiy vaqtli solishtirish — kodni taxmin qilishni qiyinlashtiradi.
        if not hmac.compare_digest(stored, body.code):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Kod noto'g'ri. Qolgan urinishlar: {MAX_OTP_ATTEMPTS - attempts}",
            )

        user = await _load_admin(db, body.telegram_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin panelga kirish huquqi yo'q",
            )

        # Kod bir martalik — darrov o'chiriladi.
        await redis.delete(key, attempts_key)

        tokens = await _issue_tokens(db, user, request)
        await db.commit()
        return tokens
    finally:
        await redis.aclose()


# ─── B) Telegram Mini App ───────────────────────────────────────────────


@router.post("/telegram", response_model=TokenPair)
async def login_with_init_data(
    body: TelegramLoginIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenPair:
    """
    Mini App `initData` imzosini tekshirib JWT beradi.

    Bu yerda `initData` muddati qattiqroq (`ADMIN_INIT_DATA_MAX_AGE_SECONDS`,
    standart 5 daqiqa): u 14 kunlik refresh token beradi, ya'ni tutib olingan
    eski initData uzoq muddatli sessiyaga aylanib ketmasligi kerak (№20).
    """
    redis = _redis()
    try:
        await _enforce_ip_limit(redis, RATE_TELEGRAM_LOGIN, request)
    finally:
        await redis.aclose()

    try:
        tg_user = validate_init_data(
            body.init_data,
            max_age=get_settings().admin_init_data_max_age_seconds,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Telegram imzosi tekshiruvdan o'tmadi: {exc}",
        ) from exc

    telegram_id = tg_user.get("id")
    if not telegram_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Telegram ID topilmadi"
        )

    user = await _load_admin(db, int(telegram_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin panelga kirish huquqi yo'q",
        )

    tokens = await _issue_tokens(db, user, request)
    await db.commit()
    return tokens


# ─── Refresh / Profil ───────────────────────────────────────────────────


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    body: RefreshIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenPair:
    """
    Refresh token → yangi token juftligi (HAQIQIY rotatsiya).

    Eski refresh darhol bekor qilinadi. Agar allaqachon bekor qilingan
    refresh qayta kelsa — token o'g'irlangan deb hisoblanadi va butun
    sessiya oilasi bekor qilinadi (weaknesses.md №19).
    """
    try:
        payload = decode_token(body.refresh_token, expected_type="refresh")
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc

    redis = _redis()
    try:
        if await token_store.is_revoked(redis, family=payload.family):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sessiya bekor qilingan — qaytadan kiring",
            )

        if await token_store.is_revoked(redis, jti=payload.jti):
            # Qayta ishlatish: o'g'irlangan token belgisi → butun oila yopiladi.
            log.warning(
                "Refresh token qayta ishlatildi (user_id=%s, fam=%s) — sessiya oilasi bekor qilindi",
                payload.user_id, payload.family,
            )
            await token_store.revoke_family(redis, payload.family)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sessiya bekor qilingan — qaytadan kiring",
            )

        user = (
            await db.execute(select(User).where(User.id == payload.user_id))
        ).scalar_one_or_none()
        if user is None or user.is_blocked or not user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sessiya yaroqsiz — qaytadan kiring",
            )

        await token_store.revoke_jti(
            redis, payload.jti, int(payload.expires_at.timestamp())
        )
        # Oila saqlanadi — bitta login sessiyasi davom etyapti.
        return _token_pair(user, payload.family or new_family_id())
    finally:
        await redis.aclose()


@router.post("/logout", response_model=LogoutOut)
async def logout(
    body: LogoutIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> LogoutOut:
    """
    Sessiyani yakunlaydi: access va refresh tokenlar bekor qilinadi.

    Ilgari logout umuman yo'q edi — "chiqish" faqat brauzer xotirasini
    tozalardi, token esa amal qilishda davom etardi (weaknesses.md №19).

    Har doim 200 qaytaradi: chiqish urinishi hech qachon xatoga uchramasin.
    """
    redis = _redis()
    actor: Optional[User] = None
    family = ""
    try:
        if credentials and credentials.credentials:
            try:
                access = decode_token(credentials.credentials, expected_type="access")
                family = access.family
                await token_store.revoke_jti(
                    redis, access.jti, int(access.expires_at.timestamp())
                )
                actor = (
                    await db.execute(select(User).where(User.id == access.user_id))
                ).scalar_one_or_none()
            except TokenError:
                pass

        if body.refresh_token:
            try:
                refresh_payload = decode_token(
                    body.refresh_token, expected_type="refresh"
                )
                family = family or refresh_payload.family
                await token_store.revoke_jti(
                    redis,
                    refresh_payload.jti,
                    int(refresh_payload.expires_at.timestamp()),
                )
            except TokenError:
                pass

        # Butun oilani yopamiz — shu sessiyadan chiqarilgan barcha tokenlar.
        if family:
            await token_store.revoke_family(redis, family)

        if actor is not None:
            await audit_svc.record(
                db,
                actor=actor,
                action=AuditAction.ADMIN_LOGOUT,
                object_type="user",
                object_id=actor.id,
                request=request,
            )
            await db.commit()

        return LogoutOut()
    finally:
        await redis.aclose()


@router.get("/me", response_model=AdminProfile)
async def me(admin: AdminDep) -> AdminProfile:
    """Joriy admin profili (frontend'da sessiyani tiklash uchun)."""
    return AdminProfile.model_validate(admin)
