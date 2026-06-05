"""app/schemas/groups.py — Guruh uchun Pydantic schemalar."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class GroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class GroupOut(BaseModel):
    id: int
    owner_id: int
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}
