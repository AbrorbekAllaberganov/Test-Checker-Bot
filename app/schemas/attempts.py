"""app/schemas/attempts.py"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AttemptOut(BaseModel):
    id: int
    titul_id: int
    detected: dict
    score: Optional[int]
    total: Optional[int]
    percent: Optional[float]
    detail: Optional[dict]
    needs_review: bool
    source_file: Optional[str]
    debug_file: Optional[str]
    status: str
    error_msg: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class AttemptPatch(BaseModel):
    needs_review: Optional[bool] = None
    score: Optional[int] = None
    detail: Optional[dict] = None


class ScanResponse(BaseModel):
    task_id: str
    message: str = "⏳ Tekshirilmoqda..."
