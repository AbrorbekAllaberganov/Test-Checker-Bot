"""
app/services/token_store.py — Admin JWT bekor qilish ro'yxati va rate limit (Redis).

NIMA UCHUN KERAK (weaknesses.md №19):
  • `refresh` "rotatsiya" deb atalgan edi, lekin eski refresh token bekor
    qilinmasdi — sizib chiqqan token 14 kun davomida to'liq ishlardi.
  • `logout` umuman yo'q edi: chiqqandan keyin ham access token amal qilardi.
  • OTP so'rovlari IP bo'yicha cheklanmasdi — har adminga 60 soniyada bitta
    xabar yuborib spam qilish mumkin edi.

OILA (family): bitta login sessiyasi. Refresh har aylanganda yangi `jti`
beriladi, lekin `fam` o'zgarmaydi. Allaqachon ishlatilgan refresh QAYTA
kelsa — bu token o'g'irlangani belgisi: butun oila bekor qilinadi.

Redis yo'q bo'lsa tekshiruvlar O'TKAZIB YUBORILADI (fail-open) va xato log
qilinadi: aks holda Redis uzilishi butun panelni yiqitardi. Bu ongli murosa —
bekor qilish oynasi access token muddati (30 daqiqa) bilan cheklangan.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from app.core.config import get_settings

log = logging.getLogger(__name__)

_REVOKED_JTI_KEY = "admin:revoked:jti:{jti}"
_REVOKED_FAMILY_KEY = "admin:revoked:fam:{family}"
_RATE_KEY = "admin:rate:{name}:{ident}"


def redis_client():
    """Yangi async Redis klienti (pool Redis kutubxonasi ichida)."""
    import redis.asyncio as aioredis

    return aioredis.from_url(get_settings().redis_url, decode_responses=True)


async def revoke_jti(redis, jti: str, expires_at_ts: int) -> None:
    """Bitta tokenni bekor qiladi (TTL — tokenning o'z muddatigacha)."""
    if not jti:
        return
    ttl = max(1, int(expires_at_ts - time.time()))
    try:
        await redis.setex(_REVOKED_JTI_KEY.format(jti=jti), ttl, "1")
    except Exception as exc:
        log.error("Token bekor qilinmadi (Redis): %s", exc)


async def revoke_family(redis, family: str) -> None:
    """Butun sessiya oilasini bekor qiladi (token qayta ishlatilganda)."""
    if not family:
        return
    ttl = get_settings().admin_refresh_token_days * 24 * 3600
    try:
        await redis.setex(_REVOKED_FAMILY_KEY.format(family=family), ttl, "1")
    except Exception as exc:
        log.error("Sessiya oilasi bekor qilinmadi (Redis): %s", exc)


async def is_revoked(redis, *, jti: str = "", family: str = "") -> bool:
    """Token yoki uning oilasi bekor qilinganmi?"""
    keys = []
    if jti:
        keys.append(_REVOKED_JTI_KEY.format(jti=jti))
    if family:
        keys.append(_REVOKED_FAMILY_KEY.format(family=family))
    if not keys:
        return False
    try:
        values = await redis.mget(keys)
    except Exception as exc:
        # Fail-open: Redis yo'q bo'lsa panel ishlashda davom etadi.
        log.error("Bekor qilish ro'yxati o'qilmadi (Redis): %s", exc)
        return False
    return any(v is not None for v in values)


async def rate_limit(
    redis,
    *,
    name: str,
    ident: Optional[str],
    limit: int,
    window_seconds: int,
) -> bool:
    """
    Oddiy sanoqli limit: `window_seconds` ichida `limit` tadan ko'p bo'lmasin.

    Args:
        name:  Limit nomi ("otp_request", ...).
        ident: Identifikator (odatda IP). None bo'lsa limit qo'llanmaydi.

    Returns:
        True — ruxsat; False — limit oshgan.
    """
    if not ident:
        return True
    key = _RATE_KEY.format(name=name, ident=ident)
    try:
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, window_seconds)
        return count <= limit
    except Exception as exc:
        # Fail-open — Redis uzilsa kirishni butunlay yopib qo'ymaymiz.
        log.error("Rate limit tekshirilmadi (Redis): %s", exc)
        return True
