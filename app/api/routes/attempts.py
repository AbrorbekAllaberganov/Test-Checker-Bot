"""
app/api/routes/attempts.py — Skan qabul qilish va natija endpointlari.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import verify_internal_key
from app.core.config import get_settings
from app.core.db import get_db
from app.models.attempt import Attempt
from app.schemas.attempts import AttemptOut, AttemptPatch, ScanResponse

router = APIRouter(
    prefix="/attempts",
    tags=["attempts"],
    dependencies=[Depends(verify_internal_key)],
)

ALLOWED_TYPES = {
    "image/jpeg", "image/png", "image/webp",
    "image/tiff", "application/pdf",
}


@router.post("/scan", response_model=ScanResponse, status_code=status.HTTP_202_ACCEPTED)
async def scan_file(
    file: UploadFile = File(...),
    chat_id: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """Skan fayl qabul qilish → Celery omr_task."""
    settings = get_settings()

    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Iltimos rasm yoki PDF yuboring.",
        )

    # Fayl hajmi tekshiruvi
    content = await file.read()
    max_bytes = settings.max_image_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Fayl hajmi {settings.max_image_mb} MB dan oshmasligi kerak.",
        )

    # Vaqtinchalik faylga saqlash
    suffix = Path(file.filename or "scan.jpg").suffix or ".jpg"
    tmp_path = settings.temp_dir / f"scan_{id(content)}{suffix}"
    tmp_path.write_bytes(content)

    # Pending attempt yaratish
    pending = Attempt(
        titul_id=1,  # placeholder, omr_task yangilaydi
        detected={},
        status="pending",
        source_file=str(tmp_path),
    )
    db.add(pending)
    await db.flush()
    await db.refresh(pending)

    # Celery task
    from app.worker.tasks import omr_task
    task = omr_task.delay(str(tmp_path), chat_id, pending.id)

    return ScanResponse(task_id=task.id)


@router.get("/{attempt_id}", response_model=AttemptOut)
async def get_attempt(attempt_id: int, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
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
    """Qo'lda tuzatish (needs_review hal qilish)."""
    from sqlalchemy import select
    result = await db.execute(select(Attempt).where(Attempt.id == attempt_id))
    attempt = result.scalar_one_or_none()
    if attempt is None:
        raise HTTPException(status_code=404, detail="Attempt topilmadi")

    if body.needs_review is not None:
        attempt.needs_review = body.needs_review
    if body.score is not None:
        attempt.score = body.score
    if body.detail is not None:
        attempt.detail = body.detail

    await db.flush()
    return attempt
