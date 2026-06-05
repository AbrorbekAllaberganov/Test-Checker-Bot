"""
app/bot/main.py — aiogram dispatcher va polling ishga tushirish.
"""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from app.bot.handlers import groups, results, scan, start, students, tests
from app.core.config import get_settings
from app.core.logging import setup_logging

log = logging.getLogger(__name__)


async def main() -> None:
    setup_logging()
    settings = get_settings()

    # Bot
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # FSM Storage — Redis
    storage = RedisStorage.from_url(settings.redis_url)

    # Dispatcher
    dp = Dispatcher(storage=storage)

    # Handlerlarni ro'yxatga olish (tartib muhim!)
    dp.include_router(start.router)
    dp.include_router(groups.router)
    dp.include_router(students.router)
    dp.include_router(tests.router)
    dp.include_router(results.router)
    dp.include_router(scan.router)  # oxirida — boshqalar catch qilmagan narsalar

    log.info("Bot ishga tushdi (@%s)", settings.bot_username)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
