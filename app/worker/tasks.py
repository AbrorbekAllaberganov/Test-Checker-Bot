"""
app/worker/tasks.py — Celery vazifalari.

pdf_task(titul_id):
  1. DB dan titul/test/group/student olish
  2. QR data URI yaratish
  3. PDF generatsiya → fayl saqlash
  4. DB'da pdf_path yangilash
  5. (ixtiyoriy) Bot orqali yuborish

tituls_batch_task(test_id, chat_id):
  Barcha titullarni render qilib BITTA ZIP qilib yuboradi — 150 o'quvchi
  uchun 150 ta alohida xabar Telegram flood limitiga urilardi (№22).

omr_task(file_path, chat_id, attempt_id):
  1. Faylni BIR MARTA yuklash (PDF: faqat 1-sahifa)
  2. QR → titul UUID → DB dan test/student topish (egalik tekshiruvi)
  3. OMR pipeline (to'g'ri qcount/vcount bilan)
  4. grade() → attempt yozish
  5. Bot orqali natija yuborish

cleanup_temp_files():
  `temp_dir` dagi yetim (task tugamay qolgan) fayllarni o'chiradi.

Xato siyosati (weaknesses.md №15):
  • DOIMIY xato (buzuq fayl, topilmagan yozuv, vaqt limiti) → attempt `error`,
    foydalanuvchiga bitta xabar, RETRY YO'Q.
  • VAQTINCHALIK xato (DB/Redis/tarmoq) → xabarsiz retry; oxirgi urinishdan
    keyingina foydalanuvchiga aytiladi.
  Istisno matni foydalanuvchiga hech qachon yuborilmaydi (ichki ma'lumot).
"""
from __future__ import annotations

import logging
import shutil
import time
import uuid as uuid_mod
import zipfile
from pathlib import Path
from typing import Optional

from celery.exceptions import SoftTimeLimitExceeded

from app.worker.celery_app import celery_app
from app.worker.session import get_sync_session

log = logging.getLogger(__name__)

# Qayta urinish ma'nosiz bo'lgan xatolar: fayl buzuq, yozuv yo'q, vaqt tugadi.
PERMANENT_ERRORS = (
    ValueError,
    FileNotFoundError,
    IsADirectoryError,
    PermissionError,
    SoftTimeLimitExceeded,
)


def _is_permanent(exc: BaseException) -> bool:
    """
    Xato doimiymi (qayta urinishdan foyda yo'q)?

    `cv2.error` ni tur bo'yicha tekshirmaymiz — cv2 ni modul darajasida import
    qilish bot jarayonini ham sekinlashtiradi (bot `omr_task` ni import qiladi).
    """
    if isinstance(exc, PERMANENT_ERRORS):
        return True
    return type(exc).__module__.split(".")[0] == "cv2"

GENERIC_PERMANENT_MESSAGE = (
    "❌ Varaqni o'qib bo'lmadi. Varaqni to'liq, aniq va yaxshi yoritilgan "
    "holda suratga olib qayta yuboring."
)
GENERIC_TRANSIENT_MESSAGE = (
    "❌ Vaqtinchalik texnik nosozlik. Birozdan keyin qayta yuboring."
)


def _get_sync_session():
    """Celery task uchun sync SQLAlchemy session (umumiy engine)."""
    return get_sync_session()


# ─── Telegram yuborish (sync o'ram) ──────────────────────────────────────────

def _run_bot(coro_factory):
    """Bitta Bot sessiyasi ochib coroutine'ni ishga tushiradi."""
    import asyncio

    from aiogram import Bot
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode

    from app.core.config import get_settings

    async def _wrapper():
        bot = Bot(
            token=get_settings().bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        try:
            return await coro_factory(bot)
        finally:
            await bot.session.close()

    return asyncio.run(_wrapper())


async def _send_with_retry(send_coro_factory, *, what: str, chat_id: int) -> bool:
    """
    Telegram'ga yuborish + `RetryAfter` ni HURMAT qilish.

    Ilgari 429 faqat log qilinardi va xabar indamay yo'qolardi
    (weaknesses.md №22).

    Returns:
        True — yuborildi.
    """
    import asyncio

    from aiogram.exceptions import (
        TelegramForbiddenError,
        TelegramRetryAfter,
    )

    for attempt in range(2):
        try:
            await send_coro_factory()
            return True
        except TelegramRetryAfter as exc:
            if attempt == 0:
                wait = int(exc.retry_after) + 1
                log.warning(
                    "Worker: Telegram flood limiti (%s, chat_id=%d) — %d s kutamiz",
                    what, chat_id, wait,
                )
                await asyncio.sleep(wait)
                continue
            log.error("Worker: %s yuborilmadi (flood limiti): chat_id=%d", what, chat_id)
            return False
        except TelegramForbiddenError:
            # Foydalanuvchi botni bloklagan — qayta urinish ma'nosiz.
            log.warning("Worker: bot bloklangan, %s yuborilmadi: chat_id=%d", what, chat_id)
            return False
        except Exception as exc:
            log.error("Worker: %s yuborishda xatolik: chat_id=%d, xato=%s", what, chat_id, exc)
            return False
    return False


def _send_message_sync(chat_id: int, text: str, **kwargs) -> bool:
    """Bot orqali xabar yuborish."""
    log.info("Worker: Bot orqali xabar yuborilmoqda: chat_id=%d", chat_id)

    async def _send(bot):
        return await _send_with_retry(
            lambda: bot.send_message(chat_id=chat_id, text=text, **kwargs),
            what="xabar",
            chat_id=chat_id,
        )

    return bool(_run_bot(_send))


def _send_document_sync(chat_id: int, file_path: str, caption: str = "") -> bool:
    """Bot orqali fayl yuborish."""
    from aiogram.types import FSInputFile

    log.info("Worker: Bot orqali fayl yuborilmoqda: chat_id=%d, file=%s", chat_id, file_path)

    async def _send(bot):
        return await _send_with_retry(
            lambda: bot.send_document(
                chat_id=chat_id,
                document=FSInputFile(file_path),
                caption=caption,
            ),
            what="fayl",
            chat_id=chat_id,
        )

    return bool(_run_bot(_send))


# ─── Egalik ──────────────────────────────────────────────────────────────────

def _chat_owns_test(db, test_id: int, chat_id: int) -> bool:
    """
    Skan yuborgan chat (ustoz) aynan shu testning egasimi?

    Zanjir: Test → Group.owner_id → User.telegram_id == chat_id.
    Bu tekshiruvsiz QR nusxasiga ega istalgan kishi (o'quvchi ham) begona
    ustozning varag'ini skan qilib natijani olishi va `attempts` ga yozishi
    mumkin edi (weaknesses.md №4, №10).
    """
    from sqlalchemy import select as sa_select

    from app.models.group import Group
    from app.models.test import Test
    from app.models.user import User

    owner_tg = db.execute(
        sa_select(User.telegram_id)
        .join(Group, Group.owner_id == User.id)
        .join(Test, Test.group_id == Group.id)
        .where(Test.id == test_id)
    ).scalar_one_or_none()
    return owner_tg is not None and int(owner_tg) == int(chat_id)


def _reject_foreign_titul(db, attempt, chat_id: int) -> None:
    """Begona titul: attempt → error, foydalanuvchiga qisqa xabar."""
    log.warning(
        "Worker: begona titul rad etildi: attempt_id=%d chat_id=%d", attempt.id, chat_id
    )
    attempt.status = "error"
    attempt.error_msg = "Titul boshqa ustozga tegishli"
    attempt.detected = {}
    db.commit()
    _send_message_sync(
        chat_id,
        "❌ Bu varaq sizning testingizga tegishli emas. "
        "Faqat o'zingiz yaratgan test titullarini yuboring.",
    )


def _mark_error(db, attempt_id: int, message: str) -> None:
    """Attempt'ni `error` holatiga o'tkazadi (ichki xato matni bilan)."""
    from app.models.attempt import Attempt

    try:
        db.rollback()
        attempt = db.get(Attempt, attempt_id)
        if attempt is not None:
            attempt.status = "error"
            attempt.error_msg = message[:500]
            db.commit()
    except Exception:
        log.exception("Worker: attempt'ni error holatiga o'tkazib bo'lmadi: %d", attempt_id)


# ─── PDF ─────────────────────────────────────────────────────────────────────

def _render_titul(db, settings, titul) -> Path:
    """Bitta titul uchun PDF render qiladi (mavjud bo'lsa qayta ishlatadi)."""
    from app.models.group import Group
    from app.models.student import Student
    from app.models.test import Test
    from app.pdf.qrgen import make_qr_data_uri
    from app.pdf.render import render_titul_pdf

    if titul.pdf_path:
        existing = Path(titul.pdf_path)
        if existing.exists():
            return existing

    test = db.get(Test, titul.test_id)
    if test is None:
        raise ValueError(f"Test topilmadi: titul_id={titul.id}")
    group = db.get(Group, test.group_id)
    student = db.get(Student, titul.student_id)
    if group is None or student is None:
        raise ValueError(f"Guruh yoki o'quvchi topilmadi: titul_id={titul.id}")

    # PDF fayl yo'li. Nomda UUID — ketma-ket ID emas: ilgari
    # `titul_{id}_{student_id}.pdf` bo'lib, /static orqali barcha titullarni
    # enumeratsiya qilish mumkin edi (weaknesses.md №4).
    out_path = settings.pdf_output_dir / f"titul_{titul.uuid}.pdf"
    render_titul_pdf(
        titul_uuid=str(titul.uuid),
        test_title=test.title,
        group_name=group.name,
        student_name=student.full_name,
        question_count=test.question_count,
        variant_count=test.variant_count,
        qr_data_uri=make_qr_data_uri(str(titul.uuid)),
        out_path=out_path,
        bot_username=settings.bot_username,
    )
    titul.pdf_path = str(out_path)
    db.commit()
    return out_path


@celery_app.task(bind=True, name="pdf_task", max_retries=3)
def pdf_task(self, titul_id: int, notify_chat_id: int | None = None):
    """
    Titul PDF ni generatsiya qiladi.

    Args:
        titul_id:       Titul DB ID.
        notify_chat_id: Tayyor bo'lgach yuborish (yakka regeneratsiya uchun).
    """
    from app.core.config import get_settings
    from app.models.student import Student
    from app.models.test import Test
    from app.models.titul import Titul
    from app.services.telegram import escape

    log.info("Worker: pdf_task boshlandi: titul_id=%d, notify_chat_id=%s", titul_id, notify_chat_id)
    settings = get_settings()
    db = _get_sync_session()

    try:
        titul = db.get(Titul, titul_id)
        if titul is None:
            # Titul o'chirilgan — qayta urinish ma'nosiz (weaknesses.md №15).
            log.error("Worker: Titul topilmadi: %d", titul_id)
            return

        out_path = _render_titul(db, settings, titul)
        log.info("Worker: PDF tayyor: %s", out_path)

        if notify_chat_id:
            test = db.get(Test, titul.test_id)
            student = db.get(Student, titul.student_id)
            caption = "📄 Titul"
            if student is not None and test is not None:
                caption = f"📄 {escape(student.full_name)} — {escape(test.title)}"
            _send_document_sync(notify_chat_id, str(out_path), caption=caption)

    except Exception as exc:
        db.rollback()
        if _is_permanent(exc):
            log.error("Worker: pdf_task doimiy xatosi (titul_id=%d): %s", titul_id, exc)
            if notify_chat_id:
                _send_message_sync(notify_chat_id, "❌ Titul PDF yaratilmadi.")
            return
        log.exception("Worker: pdf_task xatosi (titul_id=%d): %s", titul_id, exc)
        if self.request.retries >= self.max_retries:
            if notify_chat_id:
                _send_message_sync(notify_chat_id, GENERIC_TRANSIENT_MESSAGE)
            return
        raise self.retry(exc=exc, countdown=30 * (self.request.retries + 1))
    finally:
        db.close()


@celery_app.task(bind=True, name="tituls_batch_task", max_retries=1)
def tituls_batch_task(self, test_id: int, chat_id: int, owner_id: int | None = None):
    """
    Test uchun BARCHA titullarni render qilib ZIP qilib yuboradi.

    Ilgari har titul alohida `pdf_task` + `send_document` edi — 150 o'quvchi
    150 ta xabar, 429 esa faqat log qilinardi va PDF'lar indamay yo'qolardi
    (weaknesses.md №22).

    Args:
        test_id:  Test DB ID.
        chat_id:  Natija yuboriladigan chat.
        owner_id: Egalik tekshiruvi uchun (None = tekshirilmaydi, ichki chaqiruv).
    """
    from sqlalchemy import select as sa_select

    from app.core.config import get_settings
    from app.models.test import Test
    from app.models.titul import Titul
    from app.services.telegram import escape

    log.info("Worker: tituls_batch_task boshlandi: test_id=%d chat_id=%d", test_id, chat_id)
    settings = get_settings()
    db = _get_sync_session()
    zip_paths: list[Path] = []

    try:
        test = db.get(Test, test_id)
        if test is None:
            _send_message_sync(chat_id, "❌ Test topilmadi.")
            return
        if not _chat_owns_test(db, test_id, chat_id):
            log.warning("Worker: tituls_batch_task begona test: test_id=%d chat_id=%d", test_id, chat_id)
            _send_message_sync(chat_id, "❌ Bu test sizga tegishli emas.")
            return

        tituls = list(
            db.execute(sa_select(Titul).where(Titul.test_id == test_id).order_by(Titul.id))
            .scalars()
            .all()
        )
        if not tituls:
            _send_message_sync(chat_id, "Bu test uchun titul yo'q.")
            return

        # 1. Render (mavjudlari qayta ishlatiladi)
        pdf_paths: list[Path] = []
        failed = 0
        for titul in tituls:
            try:
                pdf_paths.append(_render_titul(db, settings, titul))
            except Exception as exc:
                failed += 1
                log.error("Worker: titul render xatosi (id=%d): %s", titul.id, exc)

        if not pdf_paths:
            _send_message_sync(chat_id, "❌ Titullarni tayyorlab bo'lmadi.")
            return

        # 2. ZIP — diskda, oqimli (xotirada 50 MB ushlab turmaymiz)
        max_bytes = settings.telegram_zip_max_mb * 1024 * 1024
        zip_paths = _write_zip_parts(
            pdf_paths,
            out_dir=settings.pdf_output_dir,
            stem=f"titullar_test{test_id}_{uuid_mod.uuid4().hex[:8]}",
            max_bytes=max_bytes,
        )

        # 3. Yuborish
        total = len(zip_paths)
        for idx, zp in enumerate(zip_paths, start=1):
            suffix = f" ({idx}/{total})" if total > 1 else ""
            _send_document_sync(
                chat_id,
                str(zp),
                caption=f"📦 {escape(test.title)} — {len(pdf_paths)} ta titul{suffix}",
            )

        if failed:
            _send_message_sync(
                chat_id, f"⚠️ {failed} ta titul tayyorlanmadi (xatolik)."
            )

    except Exception as exc:
        db.rollback()
        if _is_permanent(exc):
            log.error("Worker: tituls_batch_task doimiy xatosi (test_id=%d): %s", test_id, exc)
            _send_message_sync(chat_id, "❌ Titullarni tayyorlab bo'lmadi.")
            return
        log.exception("Worker: tituls_batch_task xatosi (test_id=%d): %s", test_id, exc)
        if self.request.retries >= self.max_retries:
            _send_message_sync(chat_id, GENERIC_TRANSIENT_MESSAGE)
            return
        raise self.retry(exc=exc, countdown=60)
    finally:
        # ZIP faqat yuborish uchun kerak edi — diskda qoldirmaymiz.
        for zp in zip_paths:
            try:
                zp.unlink(missing_ok=True)
            except OSError:
                pass
        db.close()


def _write_zip_parts(
    files: list[Path],
    *,
    out_dir: Path,
    stem: str,
    max_bytes: int,
) -> list[Path]:
    """
    Fayllarni ZIP(lar)ga yozadi; har bo'lak `max_bytes` dan oshmaydi.

    Returns:
        Yaratilgan ZIP fayllar ro'yxati.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    parts: list[Path] = []
    part_idx = 0
    zf: Optional[zipfile.ZipFile] = None
    path: Optional[Path] = None

    def _open_part() -> tuple[Path, zipfile.ZipFile]:
        nonlocal part_idx
        part_idx += 1
        p = out_dir / f"{stem}_{part_idx}.zip"
        return p, zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED)

    try:
        for fp in files:
            if zf is None:
                path, zf = _open_part()
                parts.append(path)

            zf.write(fp, fp.name)

            # Hajmni faqat FAYL chegarasida tekshiramiz — ZIP o'rtasidan
            # bo'linmasin. `zf.fp.tell()` yozilgan bayt soni (flush shart emas).
            written = zf.fp.tell() if zf.fp is not None else 0
            if written >= max_bytes:
                zf.close()
                zf = None
    finally:
        if zf is not None:
            zf.close()

    return parts


# ─── OMR ─────────────────────────────────────────────────────────────────────

def _archive_source(file_path: str, settings) -> str:
    """
    Skan faylini `temp_dir` dan doimiy `uploads_dir` ga ko'chiradi.

    Review (`/api/web/attempts/{id}/file/source`) shu faylga bog'liq, `temp_dir`
    esa kunlik tozalanadi (weaknesses.md №30).

    Returns:
        Yangi yo'l (ko'chirib bo'lmasa — eskisi).
    """
    src = Path(file_path)
    if not src.exists():
        return file_path
    try:
        if src.parent.resolve() == settings.uploads_dir.resolve():
            return file_path
    except OSError:
        pass

    try:
        settings.uploads_dir.mkdir(parents=True, exist_ok=True)
        dst = settings.uploads_dir / src.name
        if dst.exists():
            dst = settings.uploads_dir / f"{uuid_mod.uuid4().hex}{src.suffix}"
        shutil.move(str(src), str(dst))
        return str(dst)
    except OSError as exc:
        log.warning("Worker: skan faylini ko'chirib bo'lmadi (%s): %s", src, exc)
        return file_path


@celery_app.task(bind=True, name="omr_task", max_retries=2)
def omr_task(self, file_path: str, chat_id: int, attempt_id: int):
    """
    OMR pipeline + baholash + DB yozish + natija yuborish.

    Fayl BIR MARTA yuklanadi (PDF: faqat birinchi sahifa) va ikkala bosqichga
    (QR pre-scan, to'liq pipeline) bir xil kadr beriladi (weaknesses.md №14).

    Args:
        file_path:  Yuklab olingan rasm/PDF yo'li.
        chat_id:    Natija yuboriladigan Telegram chat ID.
        attempt_id: Pending attempt DB ID.
    """
    from sqlalchemy import select as sa_select

    from app.core.config import get_settings
    from app.models.attempt import Attempt
    from app.models.student import Student
    from app.models.test import Test
    from app.models.titul import Titul
    from app.omr.pipeline import load_pages, run
    from app.omr.qr import read_qr
    from app.services.grading import format_result_message, grade

    log.info(
        "Worker: omr_task boshlandi: file_path=%s, attempt_id=%d, chat_id=%d",
        file_path, attempt_id, chat_id,
    )
    settings = get_settings()
    db = _get_sync_session()

    try:
        attempt = db.get(Attempt, attempt_id)
        if attempt is None:
            log.error("Worker: Attempt topilmadi: %d", attempt_id)
            return

        attempt.status = "pending"
        db.commit()

        # ── 0-bosqich: faylni bir marta yuklash ────────────────────────────
        images, total_pages = load_pages(
            file_path, dpi=settings.omr_dpi, max_pages=settings.omr_max_pages
        )
        if not images:
            raise ValueError("Fayldan hech qanday sahifa o'qilmadi")

        page_note = ""
        if total_pages > len(images):
            page_note = (
                f"\n\n⚠️ Faylda {total_pages} sahifa bor — faqat 1-sahifa tekshirildi."
            )
            log.warning(
                "Worker: ko'p sahifali fayl (%d sahifa), faqat %d tekshirildi",
                total_pages, len(images),
            )

        # ── 1-bosqich: QR pre-scan (DB'dan qcount/vcount olish) ────────────
        pre_uuid = read_qr(images[0])
        qcount: Optional[int] = None
        vcount: int = 4

        if pre_uuid is not None:
            try:
                uuid_obj = uuid_mod.UUID(pre_uuid)
            except ValueError:
                log.warning("Worker: QR ichidagi UUID noto'g'ri: %s", pre_uuid)
            else:
                pre_titul = db.execute(
                    sa_select(Titul).where(Titul.uuid == uuid_obj)
                ).scalar_one_or_none()
                if pre_titul is not None:
                    pre_test = db.get(Test, pre_titul.test_id)
                    if pre_test is not None:
                        # EGALIK: varaq shu chatdagi ustozning testigami?
                        # OMR'dan OLDIN tekshiramiz — begona varaq uchun CPU
                        # sarflanmaydi. (Pastda, to'liq pipeline'dan keyin
                        # ham qayta tekshiriladi — ikki qatlam.)
                        if not _chat_owns_test(db, pre_test.id, chat_id):
                            _reject_foreign_titul(db, attempt, chat_id)
                            return
                        qcount = pre_test.question_count
                        vcount = pre_test.variant_count
                        log.info(
                            "Worker: QR pre-scan: uuid=%s, qcount=%d, vcount=%d",
                            pre_uuid, qcount, vcount,
                        )
                    else:
                        log.warning("Worker: Pre-scan: test topilmadi (titul_id=%d)", pre_titul.id)
                else:
                    log.warning("Worker: Pre-scan: titul DB'da topilmadi (uuid=%s)", pre_uuid)
        else:
            log.warning("Worker: Pre-scan: QR topilmadi")

        if qcount is None:
            log.warning("Worker: qcount aniqlanmadi, default=40 qabul qilindi")
            qcount = 40

        # ── 2-bosqich: To'liq OMR pipeline (bir xil kadrlar ustida) ────────
        debug_dir = settings.debug_output_dir if settings.omr_debug else None
        results = run(
            file_path,
            images=images,
            fill_min=settings.fill_min,
            fill_margin=settings.fill_margin,
            warp_w=settings.warp_w,
            warp_h=settings.warp_h,
            omr_dpi=settings.omr_dpi,
            qcount=qcount,
            vcount=vcount,
            omr_debug=settings.omr_debug,
            debug_out_dir=Path(debug_dir) if debug_dir else None,
        )

        if not results:
            raise ValueError("Pipeline hech natija qaytarmadi")

        res = results[0]

        if res.error:
            attempt.status = "error"
            attempt.error_msg = res.error
            attempt.detected = {}
            attempt.source_file = _archive_source(file_path, settings)
            db.commit()
            _send_message_sync(chat_id, _error_message(res.error))
            return

        if res.titul_uuid is None:
            attempt.status = "error"
            attempt.error_msg = "QR not found"
            attempt.detected = {}
            attempt.source_file = _archive_source(file_path, settings)
            db.commit()
            _send_message_sync(
                chat_id,
                "Varaqdagi QR kod o'qilmadi. To'liq, aniq suratga oling.",
            )
            return

        try:
            uuid_obj = uuid_mod.UUID(res.titul_uuid)
        except ValueError:
            raise ValueError(f"Noto'g'ri UUID: {res.titul_uuid}")

        titul = db.execute(
            sa_select(Titul).where(Titul.uuid == uuid_obj)
        ).scalar_one_or_none()

        if titul is None:
            attempt.status = "error"
            attempt.error_msg = "Titul DB'da topilmadi"
            attempt.detected = res.detected
            attempt.source_file = _archive_source(file_path, settings)
            db.commit()
            _send_message_sync(
                chat_id,
                "Bu varaq tizimda topilmadi (eski yoki boshqa bot).",
            )
            return

        test = db.get(Test, titul.test_id)
        student = db.get(Student, titul.student_id)

        # EGALIK (ikkinchi qatlam): pre-scan QR o'qilmagan yoki DB xatosi
        # bilan o'tib ketgan bo'lsa ham, natija faqat test egasiga boradi.
        if test is None or not _chat_owns_test(db, test.id, chat_id):
            _reject_foreign_titul(db, attempt, chat_id)
            return

        # Baholash
        gr = grade(res.detected, test.answer_key, res.bubble_data)

        attempt.titul_id = titul.id
        attempt.detected = {k: v for k, v in res.detected.items()}
        attempt.score = gr.score
        attempt.total = gr.total
        attempt.percent = gr.percent
        attempt.detail = gr.detail
        attempt.needs_review = gr.needs_review or res.needs_review
        attempt.status = "done"
        attempt.source_file = _archive_source(file_path, settings)

        # Admin inspektori uchun: doira o'lchovlarini va o'rtacha ishonchlilikni
        # saqlaymiz (003 migratsiyasi). Busiz panelda faqat yakuniy javob
        # ko'rinardi — nima uchun aynan shu javob tanlangani noma'lum qolardi.
        attempt.bubble_data = res.bubble_data or None
        if res.bubble_data:
            confidences = [
                bd.get("conf")
                for bd in res.bubble_data.values()
                if isinstance(bd.get("conf"), (int, float))
            ]
            if confidences:
                attempt.confidence = round(sum(confidences) / len(confidences), 4)

        # Debug rasm
        if settings.omr_debug and debug_dir:
            debug_files = list(
                Path(debug_dir).glob(f"{Path(file_path).stem}*_debug.jpg")
            )
            if debug_files:
                attempt.debug_file = str(debug_files[0])

        db.commit()

        # Natija xabari
        msg = format_result_message(gr, test.title, student.full_name) + page_note
        _send_message_sync(chat_id, msg)

        if settings.omr_debug and attempt.debug_file:
            _send_document_sync(chat_id, attempt.debug_file, caption="🔍 Debug annotatsiya")

        log.info(
            "OMR tayyor: student=%s score=%d/%d (%.1f%%)",
            student.full_name, gr.score, gr.total, gr.percent,
        )

    except Exception as exc:
        db.rollback()
        if _is_permanent(exc):
            # Buzuq/juda katta fayl, o'chirilgan yozuv, vaqt limiti — retry'dan
            # foyda yo'q, uchala urinishda bir xil xabar ketardi (№15).
            log.error("Worker: omr_task doimiy xatosi (attempt_id=%d): %s", attempt_id, exc)
            _mark_error(db, attempt_id, str(exc))
            _send_message_sync(chat_id, GENERIC_PERMANENT_MESSAGE)
            return

        # DB/Redis/tarmoq — vaqtinchalik. Foydalanuvchini har urinishda
        # bezovta qilmaymiz, faqat oxirgisida.
        log.exception("omr_task xatosi (attempt_id=%d): %s", attempt_id, exc)
        if self.request.retries >= self.max_retries:
            _mark_error(db, attempt_id, str(exc))
            _send_message_sync(chat_id, GENERIC_TRANSIENT_MESSAGE)
            return
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))
    finally:
        db.close()


def _error_message(error_code: str) -> str:
    """Xato kodi → foydalanuvchiga tushunarli xabar (HTML uchun escape qilingan)."""
    from app.services.telegram import escape

    messages = {
        "QR not found": "Varaqdagi QR kod o'qilmadi. To'liq, aniq suratga oling.",
        "Anchor topilmadi": "Varaq burchaklari ko'rinmayapti. Butun varaqni kadrga oling.",
        "Varaq yon tomonga burilgan": (
            "Varaq yon tomonga burilgan. Uni to'g'ri (portret) holatda suratga oling."
        ),
    }
    # Noma'lum kod — pipeline'dan kelgan erkin matn, ichida `<` bo'lishi mumkin.
    return messages.get(error_code, f"❌ Xatolik: {escape(error_code)}")


# ─── Tozalash ────────────────────────────────────────────────────────────────

@celery_app.task(name="cleanup_temp_files")
def cleanup_temp_files(max_age_hours: int | None = None) -> int:
    """
    `temp_dir` dagi eski (yetim) fayllarni o'chiradi.

    Baholangan skanlar `uploads_dir` ga ko'chiriladi, `temp_dir` da esa faqat
    task boshlanmagan yoki yiqilgan fayllar qoladi — ular cheksiz to'planardi
    (weaknesses.md №30).

    Returns:
        O'chirilgan fayllar soni.
    """
    from app.core.config import get_settings

    settings = get_settings()
    hours = max_age_hours if max_age_hours is not None else settings.temp_file_max_age_hours
    cutoff = time.time() - hours * 3600
    removed = 0

    temp_dir = Path(settings.temp_dir)
    if not temp_dir.exists():
        return 0

    for fp in temp_dir.iterdir():
        if not fp.is_file():
            continue
        try:
            if fp.stat().st_mtime < cutoff:
                fp.unlink()
                removed += 1
        except OSError as exc:
            log.warning("Worker: %s o'chirilmadi: %s", fp, exc)

    log.info("Worker: cleanup_temp_files — %d fayl o'chirildi (>%d soat)", removed, hours)
    return removed
