"""app/schemas/tests.py"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class TestCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    question_count: int = Field(..., description="40 | 50 | 90")
    variant_count: int = Field(4, ge=2, le=5)
    answer_key: dict[str, str] = Field(
        ..., description='{"1":"A","2":"B",...} 1-based string keys'
    )

    @field_validator("question_count")
    @classmethod
    def validate_qcount(cls, v: int) -> int:
        if v not in (40, 50, 90):
            raise ValueError("question_count 40, 50 yoki 90 bo'lishi kerak")
        return v

    @field_validator("answer_key")
    @classmethod
    def validate_key_length(cls, v: dict, info) -> dict:
        # question_count mavjud bo'lsa tekshir
        data = info.data
        qcount = data.get("question_count")
        if qcount and len(v) != qcount:
            raise ValueError(
                f"answer_key uzunligi {qcount} ga teng bo'lishi kerak, {len(v)} berildi"
            )
        return v


class TestUpdate(BaseModel):
    title: Optional[str] = None
    answer_key: Optional[dict[str, str]] = None


class TestOut(BaseModel):
    id: int
    group_id: int
    title: str
    question_count: int
    variant_count: int
    answer_key: dict[str, str]
    created_at: datetime

    model_config = {"from_attributes": True}
