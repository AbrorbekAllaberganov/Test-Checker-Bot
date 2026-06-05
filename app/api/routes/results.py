"""
app/api/routes/results.py — Natijalar va tarix endpointlari.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import verify_internal_key
from app.core.db import get_db
from app.services import history as history_svc

router = APIRouter(
    prefix="/results",
    tags=["results"],
    dependencies=[Depends(verify_internal_key)],
)


@router.get("/tests/{test_id}")
async def test_results(test_id: int, db: AsyncSession = Depends(get_db)):
    results = await history_svc.test_results(db, test_id)
    stats = await history_svc.test_stats(db, test_id)
    return {
        "test_id": test_id,
        "stats": stats,
        "results": [
            {
                "student_name": r.student_name,
                "student_id": r.student_id,
                "score": r.score,
                "total": r.total,
                "percent": r.percent,
                "needs_review": r.needs_review,
            }
            for r in results
        ],
    }


@router.get("/tests/{test_id}/export")
async def export_results_csv(test_id: int, db: AsyncSession = Depends(get_db)):
    """CSV eksport."""
    from app.services.tests import get_test
    test = await get_test(db, test_id)
    if test is None:
        raise HTTPException(status_code=404, detail="Test topilmadi")

    results = await history_svc.test_results(db, test_id)
    csv_bytes = history_svc.results_to_csv(results, test.title)

    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8-sig",
        headers={
            "Content-Disposition": f'attachment; filename="results_{test_id}.csv"'
        },
    )


@router.get("/students/{student_id}/history")
async def student_history(student_id: int, db: AsyncSession = Depends(get_db)):
    history = await history_svc.student_history(db, student_id)
    return [
        {
            "test_title": h.test_title,
            "score": h.score,
            "total": h.total,
            "percent": h.percent,
            "needs_review": h.needs_review,
            "date": h.created_at.strftime("%d.%m.%Y %H:%M"),
        }
        for h in history
    ]
