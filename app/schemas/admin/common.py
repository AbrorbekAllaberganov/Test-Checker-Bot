"""
app/schemas/admin/common.py — Umumiy sxemalar: sahifalash va xato javobi.
"""
from __future__ import annotations

import math
from typing import Generic, Sequence, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class PageMeta(BaseModel):
    """TanStack Table serverside pagination uchun meta."""

    page: int = Field(ge=1, description="Joriy sahifa (1 dan boshlanadi)")
    page_size: int = Field(ge=1, le=200)
    total: int = Field(ge=0, description="Filtrdan keyingi umumiy qatorlar soni")
    total_pages: int = Field(ge=0)

    @classmethod
    def build(cls, *, page: int, page_size: int, total: int) -> "PageMeta":
        return cls(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if page_size else 0,
        )


class Page(BaseModel, Generic[T]):
    """Sahifalangan ro'yxat javobi."""

    model_config = ConfigDict(from_attributes=True)

    items: list[T]
    meta: PageMeta

    @classmethod
    def build(
        cls, items: Sequence[T], *, page: int, page_size: int, total: int
    ) -> "Page[T]":
        return cls(
            items=list(items),
            meta=PageMeta.build(page=page, page_size=page_size, total=total),
        )


class ErrorResponse(BaseModel):
    """FastAPI HTTPException javobining hujjatlangan shakli."""

    detail: str


class OkResponse(BaseModel):
    """Oddiy muvaffaqiyat javobi."""

    ok: bool = True
    message: str = ""
