"""
app/worker/broadcast_tasks.py — Telegram e'lonini fon rejimida yuborish.

Telegram cheklovlari:
  • bir xil botdan sekundiga ~30 xabar;
  • 429 (RetryAfter) kelsa aynan aytilgan vaqt kutilishi shart.

Shu sababli yuborish ketma-ket, `SEND_DELAY` pauzasi bilan boradi. Har
xabardan oldin e'lon holati qayta o'qiladi — admin "bekor qilish" bosgan
bo'lsa, yuborish shu yerda to'xtaydi.

Idempotentlik: har bir qabul qiluvchi `broadcast_recipients` da alohida
qator; `sent` bo'lganlari qayta ishga tushirishda o'tkazib yuboriladi. Shu
sababli task xato bilan tugab qayta urinsa ham hech kim ikki marta xabar
olmaydi.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

from app.worker.celery_app import celery_app

log = logging.getLogger(__name__)

# Xabarlar orasidagi pauza (sekund) — ~25 msg/sek.
SEND_DELAY = 0.04
# Bu sondagi xabardan keyin progress DB'ga yoziladi.
PROGRESS_BATCH = 25


def _get_sync_session():
    """Celery task uchun sync SQLAlchemy session (umumiy engine — T-18)."""
    from app.worker.session import get_sync_session

    return get_sync_session()


def _send_batch_sync(items: list[tuple[int, int]], text: str, parse_mode: str) -> dict[int, tuple[str, str]]:
    """
    Bir guruh xabarni bitta Bot sessiyasida yuboradi.

    Args:
        items: [(recipient_id, telegram_id), ...]

    Returns:
        {recipient_id: (status, error_msg)}
    """
    from aiogram import Bot
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode
    from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

    from app.core.config import get_settings

    mode = None
    if parse_mode == "HTML":
        mode = ParseMode.HTML
    elif parse_mode == "Markdown":
        mode = ParseMode.MARKDOWN_V2

    results: dict[int, tuple[str, str]] = {}

    async def _run() -> None:
        bot = Bot(
            token=get_settings().bot_token,
            default=DefaultBotProperties(parse_mode=mode),
        )
        try:
            for recipient_id, chat_id in items:
                try:
                    await bot.send_message(chat_id=chat_id, text=text)
                    results[recipient_id] = ("sent", "")
                except TelegramRetryAfter as exc:
                    # Telegram aytgan vaqtni kutib bir marta qayta urinamiz.
                    log.warning("Broadcast rate limit: %s sekund kutilmoqda", exc.retry_after)
                    await asyncio.sleep(exc.retry_after + 1)
                    try:
                        await bot.send_message(chat_id=chat_id, text=text)
                        results[recipient_id] = ("sent", "")
                    except Exception as retry_exc:  # noqa: BLE001
                        results[recipient_id] = ("failed", str(retry_exc)[:500])
                except TelegramForbiddenError as exc:
                    # Foydalanuvchi botni bloklagan — qayta urinish foydasiz.
                    results[recipient_id] = ("blocked_bot", str(exc)[:500])
                except Exception as exc:  # noqa: BLE001
                    results[recipient_id] = ("failed", str(exc)[:500])

                await asyncio.sleep(SEND_DELAY)
        finally:
            await bot.session.close()

    asyncio.run(_run())
    return results


@celery_app.task(bind=True, name="broadcast_task", max_retries=1)
def broadcast_task(self, broadcast_id: int) -> dict:
    """E'lonni barcha qabul qiluvchilarga yuboradi."""
    from app.models.broadcast import Broadcast, BroadcastRecipient
    from app.models.enums import BroadcastStatus, RecipientStatus
    from app.services.broadcast import render_preview

    db = _get_sync_session()
    started = time.monotonic()

    try:
        broadcast = db.get(Broadcast, broadcast_id)
        if broadcast is None:
            log.error("broadcast_task: e'lon topilmadi: %s", broadcast_id)
            return {"ok": False, "reason": "not_found"}

        if broadcast.status in (
            BroadcastStatus.SENT.value,
            BroadcastStatus.CANCELLED.value,
        ):
            log.info(
                "broadcast_task: e'lon %s allaqachon '%s' — o'tkazib yuborildi",
                broadcast_id, broadcast.status,
            )
            return {"ok": True, "skipped": True, "status": broadcast.status}

        broadcast.status = BroadcastStatus.SENDING.value
        broadcast.started_at = broadcast.started_at or datetime.now(timezone.utc)
        db.commit()

        text = render_preview(broadcast.title, broadcast.body)

        pending = (
            db.query(BroadcastRecipient)
            .filter(
                BroadcastRecipient.broadcast_id == broadcast_id,
                BroadcastRecipient.status == RecipientStatus.PENDING.value,
            )
            .order_by(BroadcastRecipient.id)
            .all()
        )
        log.info(
            "broadcast_task: e'lon %s — %d ta qabul qiluvchiga yuborish boshlandi",
            broadcast_id, len(pending),
        )

        sent = failed = 0
        for start in range(0, len(pending), PROGRESS_BATCH):
            # Bekor qilinganini har partiyadan oldin tekshiramiz.
            db.refresh(broadcast)
            if broadcast.status == BroadcastStatus.CANCELLED.value:
                log.info("broadcast_task: e'lon %s bekor qilindi — to'xtatildi", broadcast_id)
                db.commit()
                return {
                    "ok": True,
                    "cancelled": True,
                    "sent": broadcast.sent_count,
                    "failed": broadcast.failed_count,
                }

            chunk = pending[start : start + PROGRESS_BATCH]
            results = _send_batch_sync(
                [(r.id, r.telegram_id) for r in chunk], text, broadcast.parse_mode
            )

            now = datetime.now(timezone.utc)
            for recipient in chunk:
                status_value, error = results.get(
                    recipient.id, (RecipientStatus.FAILED.value, "Natija qaytmadi")
                )
                recipient.status = status_value
                recipient.error_msg = error or None
                if status_value == RecipientStatus.SENT.value:
                    recipient.sent_at = now
                    sent += 1
                else:
                    failed += 1

            broadcast.sent_count = sent
            broadcast.failed_count = failed
            db.commit()

        broadcast.status = BroadcastStatus.SENT.value
        broadcast.finished_at = datetime.now(timezone.utc)
        db.commit()

        log.info(
            "broadcast_task: e'lon %s yakunlandi — %d yuborildi, %d xato, %.1fs",
            broadcast_id, sent, failed, time.monotonic() - started,
        )
        return {"ok": True, "sent": sent, "failed": failed}

    except Exception as exc:
        db.rollback()
        log.exception("broadcast_task xatosi (broadcast_id=%s): %s", broadcast_id, exc)
        try:
            from app.models.broadcast import Broadcast as B
            from app.models.enums import BroadcastStatus as BS

            broadcast = db.get(B, broadcast_id)
            if broadcast is not None:
                broadcast.status = BS.FAILED.value
                broadcast.error_msg = str(exc)[:1000]
                broadcast.finished_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:  # noqa: BLE001
            log.exception("broadcast_task: xato holatini yozib bo'lmadi")
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()
