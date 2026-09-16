"""
app/api/deps.py — FastAPI dependencies.
"""
from __future__ import annotations

import hmac
import logging

from fastapi import Header, HTTPException, status

from app.core.config import get_settings
from app.core.security import InsecureSecretError, assert_internal_key_is_safe

log = logging.getLogger(__name__)


async def verify_internal_key(x_internal_key: str = Header(...)) -> None:
    """
    Ichki API key tekshiruvi.

    Ikki bosqich:
      1. Kalitning o'zi xavfsizmi (namunaviy qiymat bo'lsa endpoint
         ataylab 503 qaytaradi — bu bug emas, sozlama xatosi).
      2. Kelgan kalit to'g'rimi — `compare_digest` bilan, ya'ni
         solishtirish vaqti kalit mazmuniga bog'liq emas (timing attack
         orqali kalitni harfma-harf taxmin qilib bo'lmaydi).
    """
    try:
        assert_internal_key_is_safe()
    except InsecureSecretError as exc:
        log.error("Ichki API so'rovi rad etildi: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    # `compare_digest` faqat ASCII satrlar bilan ishlaydi — sarlavhada
    # istalgan belgi kelishi mumkin, shu sababli baytlarga o'tkazamiz.
    expected = get_settings().internal_api_key.encode("utf-8")
    received = x_internal_key.encode("utf-8", errors="replace")
    if not hmac.compare_digest(received, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Noto'g'ri API kalit",
        )
