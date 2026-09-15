"""
app/services/telegram.py — API jarayonidan Telegram'ga xabar yuborish.

Bot alohida konteynerda polling qilib turadi, lekin xabar yuborish uchun
Bot API'ga oddiy HTTP so'rov yetarli — shu sababli API konteyneri ham
bot_token bilan to'g'ridan-to'g'ri yubora oladi (OTP kodi, blok haqida
ogohlantirish, qo'lda tuzatilgan natija).

Har chaqiruvda yangi `Bot` sessiyasi ochilib yopiladi — API'da xabar yuborish
kam uchraydigan amal, shu sababli doimiy sessiya saqlashning hojati yo'q.
"""
from __future__ import annotations

import html
import logging
from typing import Optional

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

from app.core.config import get_settings

log = logging.getLogger(__name__)


def escape(text: object) -> str:
    """
    Matnni Telegram HTML rejimida xavfsiz ko'rsatish uchun ekranlaydi.

    Foydalanuvchi kiritgan har qanday matn (F.I.Sh, test nomi, blok sababi)
    shu funksiyadan o'tkazilishi SHART: ichida `<` yoki `&` bo'lsa Telegram
    "can't parse entities" xatosini qaytaradi va xabar umuman yetib
    bormaydi (yomon holatda handler yiqiladi).
    """
    return html.escape(str(text if text is not None else ""), quote=False)


class TelegramSendError(Exception):
    """Xabar yuborilmadi."""

    def __init__(self, message: str, *, blocked: bool = False) -> None:
        super().__init__(message)
        # True — foydalanuvchi botni bloklagan (qayta urinish foydasiz).
        self.blocked = blocked


def _make_bot(parse_mode: str = "HTML") -> Bot:
    mode: Optional[ParseMode]
    if parse_mode == "HTML":
        mode = ParseMode.HTML
    elif parse_mode == "Markdown":
        mode = ParseMode.MARKDOWN_V2
    else:
        mode = None
    return Bot(
        token=get_settings().bot_token,
        default=DefaultBotProperties(parse_mode=mode),
    )


async def send_message(
    chat_id: int, text: str, *, parse_mode: str = "HTML"
) -> None:
    """
    Bitta xabar yuboradi.

    Raises:
        TelegramSendError — yuborilmasa (`blocked=True` bo'lsa qayta urinmang).
    """
    bot = _make_bot(parse_mode)
    try:
        await bot.send_message(chat_id=chat_id, text=text)
        log.info("Telegram xabar yuborildi: chat_id=%s", chat_id)
    except TelegramForbiddenError as exc:
        log.warning("Foydalanuvchi botni bloklagan: chat_id=%s", chat_id)
        raise TelegramSendError(str(exc), blocked=True) from exc
    except TelegramRetryAfter as exc:
        log.warning("Telegram rate limit: %s sekund kutish kerak", exc.retry_after)
        raise TelegramSendError(
            f"Rate limit: {exc.retry_after}s", blocked=False
        ) from exc
    except Exception as exc:  # noqa: BLE001
        log.error("Telegram xabar yuborilmadi: chat_id=%s xato=%s", chat_id, exc)
        raise TelegramSendError(str(exc)) from exc
    finally:
        await bot.session.close()
