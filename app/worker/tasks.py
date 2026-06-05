"""
app/worker/tasks.py — Celery vazifalari.

pdf_task(titul_id):
  1. DB dan titul/test/group/student olish
  2. QR data URI yaratish
  3. PDF generatsiya → fayl saqlash
  4. DB'da pdf_path yangilash
  5. Bot orqali natija yuborish

omr_task(file_path, chat_id, attempt_id):
  1. Rasm/PDF yuklash
  2. OMR pipeline
  3. QR → titul UUID → DB dan test/student topish
  4. grade() → attempt yozish
  5. Bot orqali natija yuborish
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from celery import shared_task

from app.worker.celery_app import celery_app

log = logging.getLogger(__name__)


def _get_sync_session():
    """Celery task uchun sync SQLAlchemy session."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.config import get_settings

    settings = get_settings()
    engine = create_engine(settings.sync_database_url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    return Session()


def _send_message_sync(chat_id: int, text: str, **kwargs) -> None:
    """Bot orqali xabar yuborish (asyncio.run bilan)."""
    import asyncio
    from aiogram import Bot
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode
    from app.core.config import get_settings

    log.info("Worker: Bot orqali xabar yuborilmoqda: chat_id=%d", chat_id)
    async def _send():
        bot = Bot(
            token=get_settings().bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        try:
            await bot.send_message(chat_id=chat_id, text=text, **kwargs)
            log.info("Worker: Xabar yuborildi: chat_id=%d", chat_id)
        except Exception as e:
            log.error("Worker: Xabar yuborishda xatolik: chat_id=%d, xato=%s", chat_id, e)
        finally:
            await bot.session.close()

    asyncio.run(_send())


def _send_document_sync(chat_id: int, file_path: str, caption: str = "") -> None:
    """Bot orqali fayl yuborish."""
    import asyncio
    from aiogram import Bot
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode
    from aiogram.types import FSInputFile
    from app.core.config import get_settings

    log.info("Worker: Bot orqali fayl yuborilmoqda: chat_id=%d, file=%s", chat_id, file_path)
    async def _send():
        bot = Bot(
            token=get_settings().bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        try:
            await bot.send_document(
                chat_id=chat_id,
                document=FSInputFile(file_path),
                caption=caption,
            )
            log.info("Worker: Fayl yuborildi: chat_id=%d", chat_id)
        except Exception as e:
            log.error("Worker: Fayl yuborishda xatolik: chat_id=%d, xato=%s", chat_id, e)
        finally:
            await bot.session.close()

    asyncio.run(_send())


@celery_app.task(bind=True, name="pdf_task", max_retries=3)
def pdf_task(self, titul_id: int, notify_chat_id: int | None = None):
    """
    Titul PDF ni generatsiya qiladi.

    Args:
        titul_id:       Titul DB ID.
        notify_chat_id: Tayyor bo'lgach xabar yuborish (ixtiyoriy).
    """
    from app.core.config import get_settings
    from app.pdf.qrgen import make_qr_data_uri
    from app.pdf.render import render_titul_pdf

    log.info("Worker: pdf_task boshlandi: titul_id=%d, notify_chat_id=%s", titul_id, notify_chat_id)
    settings = get_settings()
    db = _get_sync_session()

    try:
        # DB dan ma'lumot olish (sync ORM)
        from app.models.titul import Titul
        from app.models.test import Test
        from app.models.group import Group
        from app.models.student import Student

        titul = db.get(Titul, titul_id)
        if titul is None:
            log.error("Worker: Titul topilmadi: %d", titul_id)
            return

        test = db.get(Test, titul.test_id)
        group = db.get(Group, test.group_id)
        student = db.get(Student, titul.student_id)

        log.info("Worker: Ma'lumotlar o'qildi: student=%s, test=%s", student.full_name, test.title)

        # QR data URI
        qr_uri = make_qr_data_uri(str(titul.uuid))
        log.info("Worker: QR data URI yaratildi.")

        # PDF fayl yo'li
        out_path = (
            settings.pdf_output_dir
            / f"titul_{titul.id}_{student.id}.pdf"
        )
        log.info("Worker: PDF yo'li belgilandi: %s", out_path)

        # PDF render
        log.info("Worker: WeasyPrint orqali PDF render boshlanmoqda...")
        render_titul_pdf(
            titul_uuid=str(titul.uuid),
            test_title=test.title,
            group_name=group.name,
            student_name=student.full_name,
            question_count=test.question_count,
            variant_count=test.variant_count,
            qr_data_uri=qr_uri,
            out_path=out_path,
            bot_username=settings.bot_username,
        )
        log.info("Worker: PDF render muvaffaqiyatli yakunlandi.")

        # DB yangilash
        titul.pdf_path = str(out_path)
        db.commit()
        log.info("Worker: DB'da pdf_path yangilandi: %s", out_path)

        # Xabar yuborish
        if notify_chat_id:
            log.info("Worker: Bot orqali titul yuborilmoqda, chat_id=%d", notify_chat_id)
            _send_document_sync(
                notify_chat_id,
                str(out_path),
                caption=f"📄 {student.full_name} — {test.title}",
            )

    except Exception as exc:
        db.rollback()
        log.exception("Worker: pdf_task xatosi (titul_id=%d): %s", titul_id, exc)
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()


@celery_app.task(bind=True, name="omr_task", max_retries=2)
def omr_task(self, file_path: str, chat_id: int, attempt_id: int):
    """
    OMR pipeline + baholash + DB yozish + natija yuborish.

    Args:
        file_path:  Yuklab olingan rasm/PDF yo'li.
        chat_id:    Natija yuboriladigan Telegram chat ID.
        attempt_id: Pending attempt DB ID.
    """
    from app.core.config import get_settings
    from app.omr.pipeline import run
    from app.services.grading import grade, format_result_message
    from app.models.attempt import Attempt
    from app.models.titul import Titul
    from app.models.test import Test
    from app.models.student import Student

    log.info("Worker: omr_task boshlandi: file_path=%s, attempt_id=%d, chat_id=%d", file_path, attempt_id, chat_id)
    settings = get_settings()
    db = _get_sync_session()

    try:
        attempt = db.get(Attempt, attempt_id)
        if attempt is None:
            log.error("Worker: Attempt topilmadi: %d", attempt_id)
            return

        attempt.status = "pending"
        db.commit()

        # OMR pipeline
        debug_dir = settings.debug_output_dir if settings.omr_debug else None
        log.info("Worker: OMR pipeline ishga tushirilmoqda. File: %s", file_path)
        results = run(
            file_path,
            fill_min=settings.fill_min,
            fill_margin=settings.fill_margin,
            warp_w=settings.warp_w,
            warp_h=settings.warp_h,
            omr_dpi=settings.omr_dpi,
            omr_debug=settings.omr_debug,
            debug_out_dir=Path(debug_dir) if debug_dir else None,
        )

        log.info("Worker: OMR pipeline yakunlandi. Natija soni: %d", len(results) if results else 0)
        if not results:
            raise ValueError("Pipeline hech natija qaytarmadi")

        # Birinchi (yoki yagona) sahifani olish
        res = results[0]

        if res.error:
            attempt.status = "error"
            attempt.error_msg = res.error
            attempt.detected = {}
            db.commit()
            _send_message_sync(
                chat_id,
                _error_message(res.error),
            )
            return

        if res.titul_uuid is None:
            attempt.status = "error"
            attempt.error_msg = "QR not found"
            attempt.detected = {}
            db.commit()
            _send_message_sync(
                chat_id,
                "Varaqdagi QR kod o'qilmadi. To'liq, aniq suratga oling.",
            )
            return

        # Titul topish
        from sqlalchemy import select as sa_select

        import uuid as _uuid_mod
        try:
            uuid_obj = _uuid_mod.UUID(res.titul_uuid)
        except ValueError:
            raise ValueError(f"Noto'g'ri UUID: {res.titul_uuid}")

        titul = db.execute(
            sa_select(Titul).where(Titul.uuid == uuid_obj)
        ).scalar_one_or_none()

        if titul is None:
            attempt.status = "error"
            attempt.error_msg = "Titul DB'da topilmadi"
            attempt.detected = res.detected
            db.commit()
            _send_message_sync(
                chat_id,
                "Bu varaq tizimda topilmadi (eski yoki boshqa bot).",
            )
            return

        test = db.get(Test, titul.test_id)
        student = db.get(Student, titul.student_id)

        # Baholash
        gr = grade(res.detected, test.answer_key, res.bubble_data)

        # Attempt yangilash
        attempt.titul_id = titul.id
        attempt.detected = {k: v for k, v in res.detected.items()}
        attempt.score = gr.score
        attempt.total = gr.total
        attempt.percent = gr.percent
        attempt.detail = gr.detail
        attempt.needs_review = gr.needs_review or res.needs_review
        attempt.status = "done"
        attempt.source_file = file_path

        # Debug rasm
        if settings.omr_debug:
            debug_files = list(
                Path(debug_dir).glob(f"{Path(file_path).stem}*_debug.jpg")
            ) if debug_dir else []
            if debug_files:
                attempt.debug_file = str(debug_files[0])

        db.commit()

        # Natija xabari
        msg = format_result_message(gr, test.title, student.full_name)
        _send_message_sync(chat_id, msg)

        # Debug rasm ham yuborish (agar mavjud)
        if settings.omr_debug and attempt.debug_file:
            _send_document_sync(
                chat_id,
                attempt.debug_file,
                caption="🔍 Debug annotatsiya",
            )

        log.info(
            "OMR tayyor: student=%s score=%d/%d (%.1f%%)",
            student.full_name, gr.score, gr.total, gr.percent,
        )

    except Exception as exc:
        db.rollback()
        log.exception("omr_task xatosi (attempt_id=%d): %s", attempt_id, exc)

        # Attempt'ni error holatiga o'tkazish
        try:
            attempt = db.get(Attempt, attempt_id)
            if attempt:
                attempt.status = "error"
                attempt.error_msg = str(exc)
                db.commit()
        except Exception:
            pass

        _send_message_sync(
            chat_id,
            "❌ Xatolik yuz berdi. Iltimos qayta urinib ko'ring.",
        )
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()


def _error_message(error_code: str) -> str:
    """Xato kodi → foydalanuvchiga tushunarli xabar."""
    messages = {
        "QR not found": "Varaqdagi QR kod o'qilmadi. To'liq, aniq suratga oling.",
        "Anchor topilmadi": "Varaq burchaklari ko'rinmayapti. Butun varaqni kadrga oling.",
    }
    return messages.get(error_code, f"❌ Xatolik: {error_code}")
