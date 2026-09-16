"""
app/bot/handlers/scan.py — Skan qabul qilish (photo, document, PDF, media group).

Docs/05 Oqim 4:
- photo / document image / PDF → yuklab olish → Celery omr_task
- media group (album) → har biri alohida navbatga qo'yish + jamlama natija

Kirish siyosati (weaknesses.md №10, №4):
- Faqat ro'yxatdagi ustoz skan yubora oladi. `db_user` ni `AccessMiddleware`
  beradi (yo'q bo'lsa o'zi yaratadi — ro'yxat = birinchi xabar); `None` faqat
  `from_user` bo'lmagan g'ayrioddiy update'da qoladi — "/start yuboring".
- Bloklangan ustoz middleware'da to'xtaydi, bu yerga yetib kelmaydi.
- FSM holatida (kalit/guruh nomi kutilayotganda) yuborilgan rasm skan emas —
  `StateFilter(None)` uni o'tkazmaydi, `groups.fsm_non_text` javob beradi.
- Kim yuborgani `user_id` sifatida taskga uzatiladi; worker titul aynan shu
  ustozning testiga tegishli ekanini tekshiradi (QR nusxasi bilan begona
  natijani olish yo'li yopiq).
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from pathlib import Path
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.types import Message

from app.core.config import get_settings
from app.core.db import get_session_factory
from app.models.attempt import Attempt
from app.models.user import User
from app.services.subscriptions import QuotaExceeded
from app.services.telegram import escape

log = logging.getLogger(__name__)
router = Router(name="scan")

# Media group collector: media_group_id → [file_path, ...]
_album_collector: dict[str, list[str]] = defaultdict(list)
_album_tasks: dict[str, asyncio.Task] = {}
ALBUM_TIMEOUT = 3.0  # sekund — album oxirgi rasm kelgandan kutish

NOT_REGISTERED_MESSAGE = (
    "Skan yuborishdan oldin ro'yxatdan o'ting: /start buyrug'ini yuboring."
)


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


async def _check_quota(user_id: int, db_factory) -> Optional[str]:
    """
    Skan boshlashdan oldin tarif kvotasini tekshiradi.

    Returns:
        None — ruxsat bor; aks holda foydalanuvchiga ko'rsatiladigan xabar.
    """
    from app.services import subscriptions as subs_svc

    async with db_factory() as db:
        allowed, reason = await subs_svc.check_scan_allowed(db, user_id)
        await db.commit()  # ensure_period() davrni yangilagan bo'lishi mumkin

        if not allowed and get_settings().enforce_quota:
            return (
                f"🚫 <b>Limit tugadi</b>\n\n{escape(reason)}\n\n"
                "Tarifni yangilash uchun qo'llab-quvvatlash xizmatiga murojaat qiling."
            )
    return None


async def _enqueue_scan(file_path: str, chat_id: int, user_id: int, db_factory) -> str:
    """Pending attempt + Celery task (kvota hisobini oshiradi)."""
    from app.services import subscriptions as subs_svc
    from app.worker.tasks import omr_task

    log.info(
        "Bot: Urinish (Attempt) yaratilmoqda. File: %s, Chat ID: %d, User ID: %d",
        file_path, chat_id, user_id,
    )
    async with db_factory() as db:
        # Kvota hisobi — skan navbatga qo'yilgani uchun olinadi (natijadan
        # qat'i nazar), aks holda xato bergan skanlarni cheksiz qayta
        # yuborish mumkin bo'lib qolardi. QuotaExceeded faqat
        # ENFORCE_QUOTA=true bo'lganda ko'tariladi.
        await subs_svc.consume_scan(db, user_id)

        pending = Attempt(
            titul_id=None,  # hali noma'lum — worker QR ni o'qib to'ldiradi
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


async def _process_album(chat_id: int, user_id: int, media_group_id: str, bot: Bot) -> None:
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
    queued = 0
    for fp in paths:
        try:
            await _enqueue_scan(fp, chat_id, user_id, factory)
            queued += 1
        except QuotaExceeded as exc:
            # Limit albom o'rtasida tugadi — qolganlari navbatga qo'yilmaydi.
            await bot.send_message(
                chat_id,
                f"🚫 <b>Limit tugadi.</b> {queued} ta varaq qabul qilindi, "
                f"qolgan {len(paths) - queued} tasi tekshirilmadi.\n\n{escape(exc)}",
                parse_mode="HTML",
            )
            return


def _start_album_task(message: Message, user_id: int, bot: Bot) -> None:
    """Albomning birinchi rasmida yig'uvchi taskni ishga tushiradi."""
    if message.media_group_id not in _album_tasks:
        task = asyncio.create_task(
            _process_album(message.chat.id, user_id, message.media_group_id, bot)
        )
        _album_tasks[message.media_group_id] = task


async def _accept_scan(
    message: Message,
    bot: Bot,
    db_user: Optional[User],
    *,
    file_id: str,
    suffix: str,
) -> None:
    """
    Yakka yoki albomdagi faylni qabul qilishning umumiy qismi.

    `db_user` — AccessMiddleware bergan ro'yxatdagi ustoz. Yo'q bo'lsa skan
    qabul qilinmaydi: kimligi noma'lum foydalanuvchi uchun kvota ham,
    egalik ham tekshirib bo'lmaydi.
    """
    if db_user is None:
        await message.answer(NOT_REGISTERED_MESSAGE)
        return

    settings = get_settings()

    # Media group (album) — yig'ib, keyin bir yo'la navbatga qo'yamiz.
    if message.media_group_id:
        log.info("Bot: Fayl albom guruhiga tegishli. Media Group ID: %s", message.media_group_id)
        file_path = await _download_file(bot, file_id, settings.temp_dir, suffix)
        _album_collector[message.media_group_id].append(file_path)
        _start_album_task(message, db_user.id, bot)
        return

    # Yakka fayl
    quota_error = await _check_quota(db_user.id, get_session_factory())
    if quota_error:
        await message.answer(quota_error, parse_mode="HTML")
        return

    file_path = await _download_file(bot, file_id, settings.temp_dir, suffix)
    await message.answer("⏳ Tekshirilmoqda...")
    try:
        await _enqueue_scan(file_path, message.chat.id, db_user.id, get_session_factory())
    except QuotaExceeded as exc:
        await message.answer(
            f"🚫 <b>Limit tugadi.</b>\n\n{escape(exc)}", parse_mode="HTML"
        )


# ─── Photo handler ───────────────────────────────────────────────────────────
#
# `StateFilter(None)` — faqat holatsiz (FSM'da bo'lmagan) ustozdan skan
# qabul qilinadi. Kalit/guruh nomi kutilayotganda yuborilgan rasm skan emas —
# uni `groups.fsm_non_text` ushlab "amalni yakunlang" deydi (weaknesses №11).

@router.message(F.photo, StateFilter(None))
async def handle_photo(
    message: Message, bot: Bot, db_user: Optional[User] = None
) -> None:
    photo = message.photo[-1]
    log.info(
        "Bot: Rasm xabari qabul qilindi. Chat ID: %d, File ID: %s, Hajmi: %s px",
        message.chat.id, photo.file_id, f"{photo.width}x{photo.height}",
    )
    await _accept_scan(message, bot, db_user, file_id=photo.file_id, suffix=".jpg")


# ─── Document handler (rasm yoki PDF) ────────────────────────────────────────

@router.message(F.document, StateFilter(None))
async def handle_document(
    message: Message, bot: Bot, db_user: Optional[User] = None
) -> None:
    settings = get_settings()
    doc = message.document
    log.info(
        "Bot: Hujjat/Fayl qabul qilindi. Chat ID: %d, Nomi: %s, MIME: %s, Hajmi: %d bytes",
        message.chat.id, doc.file_name, doc.mime_type, doc.file_size or 0,
    )

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

    await _accept_scan(message, bot, db_user, file_id=doc.file_id, suffix=suffix)
