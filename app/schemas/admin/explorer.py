"""
app/schemas/admin/explorer.py — Guruh / o'quvchi / test tadqiqotchisi sxemalari.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class GroupListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime
    owner_id: int
    owner_name: Optional[str] = None
    owner_telegram_id: Optional[int] = None
    students_count: int = 0
    tests_count: int = 0
    scans_count: int = 0


class StudentListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    telegram_id: Optional[int] = None
    group_id: int
    group_name: Optional[str] = None
    created_at: datetime
    attempts_count: int = 0
    avg_percent: Optional[float] = None


class TestListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    question_count: int
    variant_count: int
    created_at: datetime
    group_id: int
    group_name: Optional[str] = None
    owner_id: Optional[int] = None
    owner_name: Optional[str] = None
    tituls_count: int = 0
    attempts_count: int = 0
    avg_percent: Optional[float] = None


class StudentResultItem(BaseModel):
    attempt_id: Optional[int] = None
    student_id: int
    student_name: str
    score: Optional[int] = None
    total: Optional[int] = None
    percent: Optional[float] = None
    needs_review: bool = False
    status: Optional[str] = None
    created_at: Optional[datetime] = None


class StudentAttemptItem(BaseModel):
    """
    O'quvchiga berilgan bitta varaq (titul) va uning natijasi.

    Manba — `tituls`, `attempts` emas: varaq berilgan-u hali skanlanmagan
    bo'lsa ham qator ko'rinadi (`attempt_id is None`). Shu sababli bu yerda
    "urinish" emas, "ishlagan testi" ma'nosi.
    """

    titul_id: int
    titul_created_at: datetime
    test_id: int
    test_title: str
    question_count: int
    variant_count: int

    attempt_id: Optional[int] = None
    score: Optional[int] = None
    total: Optional[int] = None
    percent: Optional[float] = None
    needs_review: bool = False
    manual_override: bool = False
    confidence: Optional[float] = None
    status: Optional[str] = None  # None = skan yo'q
    created_at: Optional[datetime] = None


class StudentDetail(BaseModel):
    id: int
    full_name: str
    telegram_id: Optional[int] = None
    group_id: int
    group_name: Optional[str] = None
    owner_id: Optional[int] = None
    owner_name: Optional[str] = None
    created_at: datetime
    tituls_count: int = 0
    attempts_count: int = 0
    graded_count: int = 0
    avg_percent: Optional[float] = None
    best_percent: Optional[float] = None
    attempts: list[StudentAttemptItem] = Field(default_factory=list)


class GroupDetail(BaseModel):
    id: int
    name: str
    created_at: datetime
    owner_id: int
    owner_name: Optional[str] = None
    owner_telegram_id: Optional[int] = None
    students: list[StudentListItem] = Field(default_factory=list)
    tests: list[TestListItem] = Field(default_factory=list)


class ItemAnalysisRow(BaseModel):
    """Savol tahlili — qaysi savol ko'p xato qilingan."""

    question: str
    correct_count: int
    incorrect_count: int
    unmarked_count: int
    correct_percent: float


class TestDetail(BaseModel):
    id: int
    title: str
    question_count: int
    variant_count: int
    answer_key: dict[str, str]
    created_at: datetime
    group_id: int
    group_name: Optional[str] = None
    owner_id: Optional[int] = None
    owner_name: Optional[str] = None
    attempts_count: int = 0
    avg_percent: Optional[float] = None
    results: list[StudentResultItem] = Field(default_factory=list)
    item_analysis: list[ItemAnalysisRow] = Field(default_factory=list)
