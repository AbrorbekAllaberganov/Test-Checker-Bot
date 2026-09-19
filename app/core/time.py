"""
app/core/time.py — Vaqt zonasi yordamchilari.

Bazadagi hamma `TIMESTAMPTZ` UTC'da saqlanadi va solishtiriladi. Lekin
"bugungi skanlar" kabi KUN chegaralari foydalanuvchi vaqtida bo'lishi kerak:
UTC kun boshi Toshkentda soat 05:00 — undan oldingi skanlar "kecha"ga
tushib qolardi (weaknesses.md №28).
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.core.config import get_settings


def app_tz() -> ZoneInfo:
    """Ilova ko'rsatadigan vaqt zonasi (`APP_TIMEZONE`)."""
    return ZoneInfo(get_settings().app_timezone)


def to_local(dt: datetime) -> datetime:
    """UTC (yoki naive-UTC) datetime → lokal tz-aware datetime."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(app_tz())


def to_local_naive(dt: datetime) -> datetime:
    """
    Lokal vaqtga o'tkazib tzinfo'ni olib tashlaydi.

    openpyxl tz-aware datetime'ni qabul qilmaydi (CLAUDE.md tuzoq 2), shuning
    uchun Excel eksportida aynan shu ko'rinish kerak.
    """
    return to_local(dt).replace(tzinfo=None)


def local_day_start(now: datetime | None = None) -> datetime:
    """
    Lokal kun boshini UTC tz-aware datetime sifatida qaytaradi.

    Args:
        now: Hisob nuqtasi (None = hozir).
    """
    local = to_local(now or datetime.now(timezone.utc))
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(timezone.utc)
