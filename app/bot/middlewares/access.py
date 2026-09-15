"""
app/bot/middlewares/access.py — Bloklangan foydalanuvchilarni to'xtatuvchi
va faollikni qayd etuvchi middleware.

Admin panelda "blok" tugmasi bosilishi bilan foydalanuvchi botdan ham
uziladi: har bir xabar/callback shu yerdan o'tadi va `users.is_blocked`
bazadan o'qiladi.

Nima uchun keshsiz? Har xabarda bitta indeksli `SELECT ... WHERE telegram_id=?`
— bu Telegram polling yukiga nisbatan arzimas narsa, lekin blok bir zumda
kuchga kirishini kafolatlaydi. Kesh qo'shilsa, blokdan keyin ham foydalanuvchi
kesh muddati tugaguncha ishlay olardi.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, User as TgUser
from sqlalchemy import select

from app.core.db import get_session_factory
from app.models.user import User

log = logging.getLogger(__name__)

# `last_seen_at` ni har xabarda emas, shu oraliqda bir marta yangilaymiz.
LAST_SEEN_THROTTLE_SECONDS = 300

BLOCKED_MESSAGE = (
    "⛔️ <b>Hisobingiz vaqtincha cheklangan.</b>\n\n"
    "{reason}"
    "Savollar bo'lsa qo'llab-quvvatlash xizmatiga murojaat qiling."
)


class AccessMiddleware(BaseMiddleware):
    """Bloklangan foydalanuvchilarni to'xtatadi va `last_seen_at` ni yangilaydi."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user: TgUser | None = data.get("event_from_user")
        if tg_user is None:
            return await handler(event, data)

        factory = get_session_factory()
        async with factory() as db:
            user = (
                await db.execute(
                    select(User).where(User.telegram_id == tg_user.id)
                )
            ).scalar_one_or_none()

            # Hali /start bosmagan — ro'yxatdan o'tishiga to'sqinlik qilmaymiz.
            if user is None:
                return await handler(event, data)

            if user.is_blocked:
                log.info("Bloklangan foydalanuvchi to'xtatildi: tg=%s", tg_user.id)
                await self._reject(event, user.blocked_reason)
                return None

            now = datetime.now(timezone.utc)
            if (
                user.last_seen_at is None
                or (now - user.last_seen_at).total_seconds() > LAST_SEEN_THROTTLE_SECONDS
            ):
                user.last_seen_at = now
                await db.commit()

            # Handler'lar foydalanuvchini qayta so'ramasligi uchun uzatamiz.
            data["db_user"] = user

        return await handler(event, data)

    @staticmethod
    async def _reject(event: TelegramObject, reason: str | None) -> None:
        text = BLOCKED_MESSAGE.format(reason=f"Sabab: {reason}\n\n" if reason else "")
        try:
            if isinstance(event, Message):
                await event.answer(text, parse_mode="HTML")
            elif isinstance(event, CallbackQuery):
                await event.answer("Hisobingiz bloklangan", show_alert=True)
        except Exception as exc:  # noqa: BLE001 — xabar yuborilmasa ham blok kuchda
            log.warning("Blok xabarini yuborib bo'lmadi: %s", exc)
