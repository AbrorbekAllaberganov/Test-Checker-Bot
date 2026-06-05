"""app/schemas/students.py"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class StudentCreate(BaseModel):
    full_names: list[str] = Field(..., min_length=1)


class StudentOut(BaseModel):
    id: int
    group_id: int
    full_name: str
    telegram_id: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}
