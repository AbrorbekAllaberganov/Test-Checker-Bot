"""
app/api/routes/tests.py — Test endpointlari.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import verify_internal_key
from app.core.db import get_db
from app.schemas.tests import TestCreate, TestOut, TestUpdate
from app.services import tests as test_svc

router = APIRouter(
    prefix="/tests",
    tags=["tests"],
    dependencies=[Depends(verify_internal_key)],
)


@router.post(
    "/groups/{group_id}",
    response_model=TestOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_test(
    group_id: int,
    body: TestCreate,
    db: AsyncSession = Depends(get_db),
):
    test = await test_svc.create_test(
        db,
        group_id=group_id,
        title=body.title,
        question_count=body.question_count,
        variant_count=body.variant_count,
        answer_key=body.answer_key,
    )
    return test


@router.get("/groups/{group_id}", response_model=list[TestOut])
async def list_tests(group_id: int, db: AsyncSession = Depends(get_db)):
    return await test_svc.get_tests_by_group(db, group_id)


@router.get("/{test_id}", response_model=TestOut)
async def get_test(test_id: int, db: AsyncSession = Depends(get_db)):
    test = await test_svc.get_test(db, test_id)
    if test is None:
        raise HTTPException(status_code=404, detail="Test topilmadi")
    return test


@router.patch("/{test_id}", response_model=TestOut)
async def update_test(
    test_id: int,
    body: TestUpdate,
    db: AsyncSession = Depends(get_db),
):
    test = await test_svc.update_test(
        db, test_id, title=body.title, answer_key=body.answer_key
    )
    if test is None:
        raise HTTPException(status_code=404, detail="Test topilmadi")
    return test
