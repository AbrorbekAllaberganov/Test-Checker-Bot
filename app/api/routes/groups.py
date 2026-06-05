"""
app/api/routes/groups.py — Guruh va o'quvchi endpointlari.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import verify_internal_key
from app.core.db import get_db
from app.schemas.groups import GroupCreate, GroupOut
from app.schemas.students import StudentCreate, StudentOut
from app.services import groups as group_svc
from app.services import students as student_svc

router = APIRouter(
    prefix="/groups",
    tags=["groups"],
    dependencies=[Depends(verify_internal_key)],
)


@router.post("", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
async def create_group(
    body: GroupCreate,
    owner_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Yangi guruh yaratish."""
    group = await group_svc.create_group(db, owner_id=owner_id, name=body.name)
    return group


@router.get("", response_model=list[GroupOut])
async def list_groups(owner_id: int, db: AsyncSession = Depends(get_db)):
    return await group_svc.get_groups_by_owner(db, owner_id)


@router.get("/{group_id}", response_model=GroupOut)
async def get_group(group_id: int, db: AsyncSession = Depends(get_db)):
    group = await group_svc.get_group(db, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Guruh topilmadi")
    return group


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: int, owner_id: int, db: AsyncSession = Depends(get_db)
):
    deleted = await group_svc.delete_group(db, group_id, owner_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Guruh topilmadi")


# ─── Students sub-routes ──────────────────────────────────────────────────────

@router.post(
    "/{group_id}/students",
    response_model=list[StudentOut],
    status_code=status.HTTP_201_CREATED,
)
async def add_students(
    group_id: int,
    body: StudentCreate,
    db: AsyncSession = Depends(get_db),
):
    group = await group_svc.get_group(db, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Guruh topilmadi")
    students = await student_svc.add_students(db, group_id, body.full_names)
    return students


@router.get("/{group_id}/students", response_model=list[StudentOut])
async def list_students(group_id: int, db: AsyncSession = Depends(get_db)):
    return await student_svc.get_students_by_group(db, group_id)
