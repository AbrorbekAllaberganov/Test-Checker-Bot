"""
app/api/routes/tituls.py — Titul generatsiya va PDF serve.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import verify_internal_key
from app.core.db import get_db
from app.schemas.tituls import TitulGenerateResponse, TitulOut
from app.services import titul as titul_svc

router = APIRouter(
    prefix="/tituls",
    tags=["tituls"],
    dependencies=[Depends(verify_internal_key)],
)


@router.post("/tests/{test_id}/generate", response_model=TitulGenerateResponse)
async def generate_tituls(
    test_id: int,
    notify_chat_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Test uchun barcha o'quvchilarga titul yaratib Celery'ga yuboradi.
    """
    from app.worker.tasks import pdf_task

    try:
        titul_ids = await titul_svc.generate_tituls_for_test(db, test_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    task_ids: list[str] = []
    for tid in titul_ids:
        task = pdf_task.delay(tid, notify_chat_id)
        task_ids.append(task.id)

    return TitulGenerateResponse(task_ids=task_ids, count=len(titul_ids))


@router.get("/tests/{test_id}", response_model=list[TitulOut])
async def list_tituls(test_id: int, db: AsyncSession = Depends(get_db)):
    tituls = await titul_svc.get_tituls_by_test(db, test_id)
    return tituls


@router.get("/{titul_uuid}/pdf")
async def serve_titul_pdf(
    titul_uuid: str, db: AsyncSession = Depends(get_db)
):
    titul = await titul_svc.get_titul_by_uuid(db, titul_uuid)
    if titul is None:
        raise HTTPException(status_code=404, detail="Titul topilmadi")
    if titul.pdf_path is None:
        raise HTTPException(status_code=404, detail="PDF hali tayyorlanmagan")

    return FileResponse(
        titul.pdf_path,
        media_type="application/pdf",
        filename=f"titul_{titul_uuid[:8]}.pdf",
    )
