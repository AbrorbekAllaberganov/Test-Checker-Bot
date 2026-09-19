"""
app/api/routes/attempts.py — Skan qabul qilish va natija endpointlari.

Bu router ICHKI (`verify_internal_key`): bot va boshqa servislar uchun.
Foydalanuvchi oqimi `app/bot/handlers/scan.py` orqali boradi.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import verify_internal_key
from app.core.config import get_settings
from app.core.db import get_db
from app.models.attempt import Attempt
from app.models.titul import Titul
from app.models.user import User
from app.schemas.attempts import AttemptOut, AttemptPatch, ScanResponse
from app.services.grading import AnswerValidationError, grade, validate_answers

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/attempts",
    tags=["attempts"],
    dependencies=[Depends(verify_internal_key)],
)

ALLOWED_TYPES = {
    "image/jpeg", "image/png", "image/webp",
    "image/tiff", "application/pdf",
}
ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".pdf"}

# Diskka yozish bo'lagi.
CHUNK_SIZE = 1 << 20  # 1 MB


@router.post("/scan", response_model=ScanResponse, status_code=status.HTTP_202_ACCEPTED)
async def scan_file(
    file: UploadFile = File(...),
    chat_id: int = Query(..., gt=0, description="Natija yuboriladigan Telegram chat ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    Skan fayl qabul qilish → Celery `omr_task`.

    `chat_id` MAJBURIY: worker natijani shu chatga yuboradi va aynan shu
    chatdagi ustoz titul egasi ekanini tekshiradi (weaknesses.md №9, №10).
    Egasi bo'lmasa attempt `error` bo'ladi.
    """
    settings = get_settings()

    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Iltimos rasm yoki PDF yuboring.",
        )

    suffix = Path(file.filename or "scan.jpg").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        suffix = ".pdf" if file.content_type == "application/pdf" else ".jpg"

    # Nom UUID bo'yicha: ilgari `scan_{id(content)}` edi — `id()` qayta
    # ishlatiladigan qiymat, ikki so'rov bir xil faylga yozishi mumkin edi.
    tmp_path = settings.temp_dir / f"{uuid4().hex}{suffix}"
    settings.temp_dir.mkdir(parents=True, exist_ok=True)

    # Oqimli yozish: ilgari butun fayl RAM'ga o'qilib KEYIN hajm tekshirilardi
    # (weaknesses.md №9) — 2 GB yuborib API'ni yiqitish mumkin edi.
    max_bytes = settings.max_image_mb * 1024 * 1024
    size = 0
    try:
        with tmp_path.open("wb") as fh:
            while chunk := await file.read(CHUNK_SIZE):
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            f"Fayl hajmi {settings.max_image_mb} MB dan "
                            "oshmasligi kerak."
                        ),
                    )
                fh.write(chunk)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    if size == 0:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Fayl bo'sh.")

    # Kim yubordi (004): `chat_id` dagi ustoz. Topilmasa NULL — worker
    # egalikni baribir tekshiradi va begona titulni rad etadi.
    submitter_id = (
        await db.execute(select(User.id).where(User.telegram_id == chat_id))
    ).scalar_one_or_none()

    # Pending attempt: `titul_id` NULL (002 dan beri nullable) — QR ni worker
    # o'qiydi. Ilgari `titul_id=1` placeholder edi: begona titulga bog'lanish
    # yoki FK xatosi (weaknesses.md №9).
    pending = Attempt(
        titul_id=None,
        detected={},
        status="pending",
        source_file=str(tmp_path),
        submitted_by_id=submitter_id,
    )
    db.add(pending)
    await db.flush()
    await db.refresh(pending)
    await db.commit()

    from app.worker.tasks import omr_task
    task = omr_task.delay(str(tmp_path), chat_id, pending.id)
    log.info("API: skan navbatga qo'yildi: attempt_id=%d task_id=%s", pending.id, task.id)

    return ScanResponse(task_id=task.id)


@router.get("/{attempt_id}", response_model=AttemptOut)
async def get_attempt(attempt_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Attempt).where(Attempt.id == attempt_id))
    attempt = result.scalar_one_or_none()
    if attempt is None:
        raise HTTPException(status_code=404, detail="Attempt topilmadi")
    return attempt


@router.patch("/{attempt_id}", response_model=AttemptOut)
async def patch_attempt(
    attempt_id: int,
    body: AttemptPatch,
    db: AsyncSession = Depends(get_db),
):
    """
    Qo'lda tuzatish (needs_review hal qilish).

    `score`/`detail` ni to'g'ridan-to'g'ri yozib bo'lmaydi: ilgari `score`
    yangilanib `percent`/`detail` eskisicha qolardi va hisobot o'ziga zid
    bo'lardi (weaknesses.md №24). Endi `detected` yuboriladi va ball
    `grade()` bilan qayta hisoblanadi.
    """
    result = await db.execute(
        select(Attempt)
        .where(Attempt.id == attempt_id)
        .options(selectinload(Attempt.titul).selectinload(Titul.test))
    )
    attempt = result.scalar_one_or_none()
    if attempt is None:
        raise HTTPException(status_code=404, detail="Attempt topilmadi")

    if body.detected is not None:
        test = attempt.titul.test if attempt.titul else None
        if test is None:
            raise HTTPException(
                status_code=400,
                detail="Bu skan testga ulanmagan (QR o'qilmagan) — javobni tuzatib bo'lmaydi",
            )

        try:
            validate_answers(
                body.detected,
                question_count=test.question_count,
                variant_count=test.variant_count,
                answer_key=test.answer_key or {},
            )
        except AnswerValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        merged: dict[str, Optional[str]] = dict(attempt.detected or {})
        merged.update(body.detected)

        gr = grade(merged, test.answer_key or {})
        attempt.detected = merged
        attempt.score = gr.score
        attempt.total = gr.total
        attempt.percent = gr.percent
        attempt.detail = gr.detail
        attempt.manual_override = True
        attempt.status = "done"
        attempt.needs_review = False

    if body.needs_review is not None:
        attempt.needs_review = body.needs_review

    await db.commit()
    await db.refresh(attempt)
    return attempt
