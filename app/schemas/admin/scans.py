"""
app/schemas/admin/scans.py — OMR skanlari va inspektor sxemalari.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ScanListItem(BaseModel):
    """Skanlar jadvali qatori."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    needs_review: bool
    manual_override: bool
    score: Optional[int] = None
    total: Optional[int] = None
    percent: Optional[float] = None
    confidence: Optional[float] = Field(
        default=None, description="0..1 — o'rtacha doira ishonchliligi (eski qatorlarda NULL)"
    )
    error_msg: Optional[str] = None
    created_at: datetime

    student_id: Optional[int] = None
    student_name: Optional[str] = None
    test_id: Optional[int] = None
    test_title: Optional[str] = None
    group_id: Optional[int] = None
    group_name: Optional[str] = None
    owner_id: Optional[int] = None
    owner_name: Optional[str] = None
    # Skanni kim yubordi (004). QR o'qilmagan skanda `owner_*` NULL bo'ladi —
    # bu yagona manba.
    submitted_by_id: Optional[int] = None
    submitted_by_name: Optional[str] = None


class BubbleCell(BaseModel):
    """Bitta variant doirasi — heatmap chizish uchun."""

    letter: str
    fill_ratio: float = Field(ge=0.0, description="0..1 to'ldirilganlik")
    is_selected: bool = False
    is_correct_key: bool = False


class ScanQuestionRow(BaseModel):
    """Inspektordagi bitta savol qatori."""

    question: str
    detected: Optional[str] = None
    correct: Optional[str] = None
    is_correct: bool = False
    flag: Optional[str] = Field(
        default=None, description="None | 'blank' | 'ambiguous'"
    )
    confidence: Optional[float] = None
    bubbles: list[BubbleCell] = Field(default_factory=list)


class OmrInspectorOut(BaseModel):
    """`GET /api/admin/scans/{id}` — inspektor uchun to'liq ma'lumot."""

    id: int
    status: str
    needs_review: bool
    manual_override: bool
    score: Optional[int] = None
    total: Optional[int] = None
    percent: Optional[float] = None
    confidence: Optional[float] = None
    error_msg: Optional[str] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None

    student_id: Optional[int] = None
    student_name: Optional[str] = None
    test_id: Optional[int] = None
    test_title: Optional[str] = None
    group_name: Optional[str] = None
    owner_id: Optional[int] = None
    owner_name: Optional[str] = None
    owner_telegram_id: Optional[int] = None

    question_count: int = 0
    variant_letters: list[str] = Field(default_factory=list)

    # Rasmlar — admin auth talab qiladigan nisbiy URL'lar. Frontend ularni
    # `<img src>` bilan emas, Authorization header'li so'rov + blob URL
    # bilan ko'rsatadi.
    source_url: Optional[str] = Field(
        default=None,
        description="Asl yuklangan rasm (/api/admin/scans/{id}/file/source)",
    )
    debug_url: Optional[str] = Field(
        default=None,
        description="OMR annotatsiyalangan rasm (/api/admin/scans/{id}/file/debug)",
    )

    questions: list[ScanQuestionRow] = Field(default_factory=list)


class OverrideAnswersIn(BaseModel):
    """
    Qo'lda tuzatish: {"1": "A", "2": null, ...}

    Faqat o'zgartirilayotgan savollarni yuborish yetarli — qolganlari joriy
    aniqlangan javoblardan olinadi.
    """

    answers: dict[str, Optional[str]] = Field(
        description="Savol raqami → javob harfi yoki null (bo'sh)"
    )
    reason: Optional[str] = Field(default=None, max_length=500)
    notify_teacher: bool = Field(
        default=True, description="Ustozga Telegram orqali yangi natijani yuborish"
    )
