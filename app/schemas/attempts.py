"""app/schemas/attempts.py"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AttemptOut(BaseModel):
    id: int
    # QR hali o'qilmagan (pending/error) skan uchun NULL — `int` bo'lganda
    # `GET /attempts/{id}` bunday qatorda 500 qaytarardi (weaknesses.md №9).
    titul_id: Optional[int]
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
    # 003 ustunlari — eski qatorlarda NULL.
    confidence: Optional[float] = None
    manual_override: bool = False

    model_config = {"from_attributes": True}


class AttemptPatch(BaseModel):
    """
    Qo'lda tuzatish.

    `score`/`detail` ATAYLAB yo'q: ball faqat `detected` dan `grade()` bilan
    qayta hisoblanadi, aks holda `score` va `percent` bir-biriga mos kelmay
    qolardi (weaknesses.md №24).
    """
    needs_review: Optional[bool] = None
    # Faqat o'zgargan savollar: {"7": "B", "12": None}
    detected: Optional[dict[str, Optional[str]]] = None


class ScanResponse(BaseModel):
    task_id: str
    message: str = "⏳ Tekshirilmoqda..."
