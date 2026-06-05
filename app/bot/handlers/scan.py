"""
app/bot/handlers/scan.py — Skan qabul qilish (photo, document, PDF, media group).

Docs/05 Oqim 4:
- photo / document image / PDF → yuklab olish → Celery omr_task
- media group (album) → har biri alohida navbatga qo'yish + jamlama natija
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.types import Message

from app.core.config import get_settings
from app.core.db import get_session_factory
from app.models.attempt import Attempt

log = logging.getLogger(__name__)
router = Router(name="scan")

# Media group collector: media_group_id → [file_path, ...]
_album_collector: dict[str, list[str]] = defaultdict(list)
_album_tasks: dict[str, asyncio.Task] = {}
ALBUM_TIMEOUT = 3.0  # sekund — album oxirgi rasm kelgandan kutish


ALLOWED_MIME = {
    "image/jpeg", "image/png", "image/webp",
    "image/heic", "image/heif", "image/tiff",
    "application/pdf",
}


async def _download_file(bot: Bot, file_id: str, dest_dir: Path, suffix: str) -> str:
    """Faylni yuklab olib vaqtincha saqlaymiz."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / f"{file_id}{suffix}"
    log.info("Bot: Telegramdan fayl yuklab olinmoqda. File ID: %s, Destination: %s", file_id, out)
    await bot.download(file_id, destination=str(out))
    log.info("Bot: Fayl muvaffaqiyatli yuklab olindi: %s", out)
    return str(out)


async def _enqueue_scan(file_path: str, chat_id: int, db_factory) -> str:
    """Pending attempt + Celery task."""
    from app.worker.tasks import omr_task

    log.info("Bot: Urinish (Attempt) yaratilmoqda. File: %s, Chat ID: %d", file_path, chat_id)
    async with db_factory() as db:
        pending = Attempt(
            titul_id=1,  # placeholder
            detected={},
            status="pending",
            source_file=file_path,
        )
        db.add(pending)
        await db.flush()
        await db.refresh(pending)
        attempt_id = pending.id
        await db.commit()

    log.info("Bot: Urinish DB'da saqlandi (ID: %d). Celery omr_task ga yuborilmoqda...", attempt_id)
    task = omr_task.delay(file_path, chat_id, attempt_id)
    log.info("Bot: Celery omr_task muvaffaqiyatli yuborildi (Task ID: %s)", task.id)
    return task.id


async def _process_album(chat_id: int, media_group_id: str, bot: Bot) -> None:
    """Album yig'ilgandan keyin har biriga task yuborish + jamlama."""
    log.info("Bot: Albom media guruhi (ID: %s) uchun yig'ish boshlandi.", media_group_id)
    await asyncio.sleep(ALBUM_TIMEOUT)
    paths = _album_collector.pop(media_group_id, [])
    _album_tasks.pop(media_group_id, None)

    if not paths:
        log.warning("Bot: Albom (ID: %s) bo'sh bo'lib chiqdi.", media_group_id)
        return

    log.info("Bot: Albom (ID: %s) yig'ildi. Jami rasmlar: %d. Navbatga qo'yilmoqda...", media_group_id, len(paths))
    await bot.send_message(
        chat_id,
        f"⏳ {len(paths)} ta varaq tekshirilmoqda..."
    )
    factory = get_session_factory()
    for fp in paths:
        await _enqueue_scan(fp, chat_id, factory)


# ─── Photo handler ───────────────────────────────────────────────────────────

@router.message(F.photo)
async def handle_photo(message: Message, bot: Bot) -> None:
    settings = get_settings()
    photo = message.photo[-1]
    log.info("Bot: Rasm xabari qabul qilindi. Chat ID: %d, File ID: %s, Hajmi: %s px", message.chat.id, photo.file_id, f"{photo.width}x{photo.height}")

    # Media group (album) bo'lsa
    if message.media_group_id:
        log.info("Bot: Rasm albom guruhiga tegishli. Media Group ID: %s", message.media_group_id)
        file_path = await _download_file(
            bot, photo.file_id,
            settings.temp_dir,
            ".jpg",
        )
        _album_collector[message.media_group_id].append(file_path)

        # Agar birinchi rasm bo'lsa, timeout taskini boshlash
        if message.media_group_id not in _album_tasks:
            task = asyncio.create_task(
                _process_album(message.chat.id, message.media_group_id, bot)
            )
            _album_tasks[message.media_group_id] = task
        return

    # Yakka rasm
    file_path = await _download_file(
        bot, photo.file_id, settings.temp_dir, ".jpg"
    )
    await message.answer("⏳ Tekshirilmoqda...")
    factory = get_session_factory()
    await _enqueue_scan(file_path, message.chat.id, factory)


# ─── Document handler (rasm yoki PDF) ────────────────────────────────────────

@router.message(F.document)
async def handle_document(message: Message, bot: Bot) -> None:
    settings = get_settings()
    doc = message.document
    log.info("Bot: Hujjat/Fayl qabul qilindi. Chat ID: %d, Nomi: %s, MIME: %s, Hajmi: %d bytes", message.chat.id, doc.file_name, doc.mime_type, doc.file_size or 0)

    if doc.mime_type not in ALLOWED_MIME:
        log.warning("Bot: Noto'g'ri MIME formatdagi hujjat keldi: %s", doc.mime_type)
        await message.answer("Iltimos rasm yoki PDF yuboring.")
        return

    # Hajm tekshiruvi
    max_bytes = settings.max_image_mb * 1024 * 1024
    if doc.file_size and doc.file_size > max_bytes:
        log.warning("Bot: Hujjat hajmi limitdan katta: %d > %d bytes", doc.file_size, max_bytes)
        await message.answer(
            f"❌ Fayl hajmi {settings.max_image_mb} MB dan oshmasligi kerak."
        )
        return

    # Kengaytma
    suffix = Path(doc.file_name or "scan.jpg").suffix or ".jpg"
    if doc.mime_type == "application/pdf":
        suffix = ".pdf"

    # Media group
    if message.media_group_id:
        log.info("Bot: Hujjat albom guruhiga tegishli. Media Group ID: %s", message.media_group_id)
        file_path = await _download_file(
            bot, doc.file_id, settings.temp_dir, suffix
        )
        _album_collector[message.media_group_id].append(file_path)
        if message.media_group_id not in _album_tasks:
            task = asyncio.create_task(
                _process_album(message.chat.id, message.media_group_id, bot)
            )
            _album_tasks[message.media_group_id] = task
        return

    file_path = await _download_file(
        bot, doc.file_id, settings.temp_dir, suffix
    )
    await message.answer("⏳ Tekshirilmoqda...")
    factory = get_session_factory()
    await _enqueue_scan(file_path, message.chat.id, factory)
