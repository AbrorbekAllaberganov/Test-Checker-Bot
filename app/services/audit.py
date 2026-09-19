"""
app/services/audit.py — Admin amallarini jurnalga yozish.

Foydalanish:
    await audit.record(
        db,
        actor=admin,
        action=AuditAction.USER_BLOCK,
        object_type="user",
        object_id=user.id,
        payload={"reason": reason},
        request=request,
    )

Jurnal yozuvi hech qachon asosiy amalni buzmasligi kerak — shu sababli
`record()` ichidagi xato faqat log'ga tushadi va yuqoriga ko'tarilmaydi.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.enums import AuditAction
from app.models.user import User

log = logging.getLogger(__name__)


def client_ip(request: Optional[Request]) -> Optional[str]:
    """
    So'rov kelgan IP.

    `X-Forwarded-For` ga TO'G'RIDAN-TO'G'RI ISHONMAYMIZ (weaknesses.md №19):
    uni istalgan klient o'zi yozib yuborishi mumkin edi — audit jurnalidagi
    IP soxtalashtirilar va IP bo'yicha rate limit aylanib o'tilardi.

    Uvicorn `--proxy-headers --forwarded-allow-ips=$TRUSTED_PROXY_IPS`
    bilan ishga tushadi (docker-compose.yml): u header'ni FAQAT ishonchli
    proxy'dan qabul qiladi va `request.client.host` ni allaqachon to'g'ri
    qiymatga almashtirgan bo'ladi.
    """
    if request is None:
        return None
    return request.client.host if request.client else None


async def record(
    db: AsyncSession,
    *,
    actor: Optional[User],
    action: AuditAction | str,
    object_type: Optional[str] = None,
    object_id: Optional[int | str] = None,
    payload: Optional[dict[str, Any]] = None,
    request: Optional[Request] = None,
) -> Optional[AuditLog]:
    """Amalni jurnalga qo'shadi (commit chaqiruvchi zimmasida)."""
    try:
        entry = AuditLog(
            actor_id=actor.id if actor else None,
            actor_label=actor.display_name if actor else "system",
            action=str(action),
            object_type=object_type,
            object_id=str(object_id) if object_id is not None else None,
            payload=payload,
            ip_address=client_ip(request),
        )
        db.add(entry)
        await db.flush()
        return entry
    except Exception:  # noqa: BLE001 — jurnal asosiy amalni to'xtatmasin
        log.exception("Audit yozuvini saqlab bo'lmadi: action=%s", action)
        return None


def diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """
    Faqat o'zgargan maydonlarni {"field": {"from": .., "to": ..}} ko'rinishida
    qaytaradi — jurnal ixcham bo'lishi uchun.
    """
    changed: dict[str, Any] = {}
    for key in set(before) | set(after):
        old, new = before.get(key), after.get(key)
        if old != new:
            changed[key] = {"from": old, "to": new}
    return changed
