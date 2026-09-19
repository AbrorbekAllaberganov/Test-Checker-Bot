"""
app/core/security.py — Admin panel uchun JWT (access + refresh) tokenlari.

Parol yo'q: admin faqat Telegram orqali o'zini tasdiqlaydi (Mini App initData
imzosi yoki bot yuborgan bir martalik kod). Shundan keyin brauzer sessiyasi
uchun qisqa muddatli access token va uzoq muddatli refresh token beriladi.

Token payload:
    {
      "sub": "<users.id>",
      "tg":  <telegram_id>,
      "role": "SUPERADMIN",
      "typ": "access" | "refresh",
      "fam": "<sessiya oilasi>",   # refresh rotatsiyasi uchun
      "iat": ..., "exp": ..., "jti": "..."
    }
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import jwt

from app.core.config import get_settings

ALGORITHM = "HS256"

TokenType = Literal["access", "refresh"]

# `.env.example` dagi namunaviy qiymatlar — bular bilan token imzolash
# yoki ichki API'ni himoyalash xavfli, chunki kalit ochiq repoda turadi.
_INSECURE_SECRETS = frozenset(
    {
        "change-me",
        "change-me-use-a-random-32-char-secret",
        "change-me-super-secret-internal-key",
        "CHANGE_ME_INTERNAL_API_KEY_32_BELGIDAN_UZUN",
        "secret",
        "changeme",
    }
)
MIN_SECRET_LENGTH = 32
# Ichki kalit uchun biroz yumshoqroq chegara — u faqat konteynerlar
# orasida yuradi, lekin baribir taxmin qilib bo'lmaydigan bo'lishi kerak.
MIN_INTERNAL_KEY_LENGTH = 24


class TokenError(Exception):
    """Token yaroqsiz, muddati o'tgan yoki turi mos emas."""


class InsecureSecretError(RuntimeError):
    """SECRET_KEY namunaviy yoki juda qisqa — admin panel ishlamaydi."""


def assert_secret_is_safe() -> None:
    """
    JWT kaliti xavfsizligini tekshiradi.

    Nima uchun bu MUHIM: `secret_key` faqat admin panel tokenlarini
    imzolash uchun ishlatiladi. Agar u `.env.example` dagi namunaviy
    qiymatda qolsa, repoNI ko'rgan istalgan kishi o'ziga SUPERADMIN
    tokeni yasab panelga kira oladi.

    Shu sababli bunday holatda token BERILMAYDI va QABUL QILINMAYDI.
    Bot va Telegram Mini App bu kalitga bog'liq emas (ular bot_token
    HMAC'idan foydalanadi), shu sababli ular ishlashda davom etadi.
    """
    secret = get_settings().secret_key
    if secret in _INSECURE_SECRETS or len(secret) < MIN_SECRET_LENGTH:
        raise InsecureSecretError(
            "Admin panel o'chirilgan: SECRET_KEY namunaviy yoki juda qisqa "
            f"(kamida {MIN_SECRET_LENGTH} belgi). Yangi kalit yarating va "
            ".env ga yozing: "
            'python -c "import secrets; print(secrets.token_hex(32))"'
        )


def assert_internal_key_is_safe() -> None:
    """
    Ichki API kaliti xavfsizligini tekshiradi.

    `INTERNAL_API_KEY` bot va worker'ning API'ga kirish parolidir
    (`/attempts/*`). U `.env.example` dagi namunaviy qiymatda qolsa,
    repo'ni ko'rgan har kim skan yuborishi, urinish natijasini o'qishi
    va bahoni o'zgartirishi mumkin bo'ladi.

    Shu sababli bunday holatda himoyalangan endpointlar 503 qaytaradi.
    Bot va Mini App bu kalitga bog'liq emas — ular ishlashda davom etadi.
    """
    key = get_settings().internal_api_key
    if key in _INSECURE_SECRETS or len(key) < MIN_INTERNAL_KEY_LENGTH:
        raise InsecureSecretError(
            "Ichki API o'chirilgan: INTERNAL_API_KEY namunaviy yoki juda "
            f"qisqa (kamida {MIN_INTERNAL_KEY_LENGTH} belgi). Yangi kalit "
            "yarating va .env ga yozing: "
            'python -c "import secrets; print(secrets.token_hex(32))"'
        )


@dataclass(frozen=True)
class TokenPayload:
    user_id: int
    telegram_id: int
    admin_role: str
    token_type: TokenType
    expires_at: datetime
    jti: str
    # Bitta login sessiyasi. Refresh aylanganda jti o'zgaradi, family qoladi —
    # o'g'irlangan token aniqlansa butun oila bekor qilinadi (T-30).
    family: str = ""


def _create_token(
    *,
    user_id: int,
    telegram_id: int,
    admin_role: str,
    token_type: TokenType,
    expires_delta: timedelta,
    family: str,
) -> str:
    assert_secret_is_safe()

    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "tg": telegram_id,
        "role": admin_role,
        "typ": token_type,
        "fam": family,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, get_settings().secret_key, algorithm=ALGORITHM)


def new_family_id() -> str:
    """Yangi login sessiyasi uchun oila identifikatori."""
    return uuid.uuid4().hex


def create_access_token(
    *, user_id: int, telegram_id: int, admin_role: str, family: str = ""
) -> str:
    settings = get_settings()
    return _create_token(
        user_id=user_id,
        telegram_id=telegram_id,
        admin_role=admin_role,
        token_type="access",
        expires_delta=timedelta(minutes=settings.admin_access_token_minutes),
        family=family or new_family_id(),
    )


def create_refresh_token(
    *, user_id: int, telegram_id: int, admin_role: str, family: str = ""
) -> str:
    settings = get_settings()
    return _create_token(
        user_id=user_id,
        telegram_id=telegram_id,
        admin_role=admin_role,
        token_type="refresh",
        expires_delta=timedelta(days=settings.admin_refresh_token_days),
        family=family or new_family_id(),
    )


def decode_token(token: str, *, expected_type: TokenType | None = None) -> TokenPayload:
    """
    Tokenni tekshirib payload qaytaradi.

    Raises:
        TokenError — imzo noto'g'ri, muddati o'tgan yoki turi kutilganidan farqli.
        InsecureSecretError — SECRET_KEY namunaviy qiymatda.
    """
    assert_secret_is_safe()

    try:
        raw = jwt.decode(
            token,
            get_settings().secret_key,
            algorithms=[ALGORITHM],
            options={"require": ["exp", "sub", "typ"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Token muddati tugagan") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError(f"Token yaroqsiz: {exc}") from exc

    token_type = raw.get("typ")
    if expected_type is not None and token_type != expected_type:
        raise TokenError(
            f"Token turi mos emas: kutilgan '{expected_type}', kelgan '{token_type}'"
        )

    try:
        user_id = int(raw["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise TokenError("Token 'sub' maydoni noto'g'ri") from exc

    return TokenPayload(
        user_id=user_id,
        telegram_id=int(raw.get("tg") or 0),
        admin_role=str(raw.get("role") or ""),
        token_type=token_type,  # type: ignore[arg-type]
        expires_at=datetime.fromtimestamp(raw["exp"], tz=timezone.utc),
        jti=str(raw.get("jti") or ""),
        family=str(raw.get("fam") or ""),
    )
