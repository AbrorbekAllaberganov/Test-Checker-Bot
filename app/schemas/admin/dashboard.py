"""
app/schemas/admin/dashboard.py — Executive Dashboard javob sxemalari.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class KpiCards(BaseModel):
    """Yuqoridagi KPI kartochkalari."""

    total_teachers: int
    active_teachers_30d: int
    blocked_teachers: int
    total_groups: int
    total_students: int
    total_tests: int
    total_scans: int
    scans_today: int
    scans_7d: int
    omr_accuracy: float = Field(
        description="Toza o'qilgan skanlar ulushi, % (needs_review va error hisobga olinadi)"
    )
    needs_review_count: int
    error_rate: float = Field(description="Xato bilan tugagan skanlar ulushi, %")
    avg_score_percent: float = Field(description="O'quvchilarning o'rtacha ball foizi")
    paying_subscribers: int
    new_teachers_7d: int


class ScanPoint(BaseModel):
    date: str
    total: int
    clean: int
    review: int
    errors: int


class TeacherActivityPoint(BaseModel):
    date: str
    active_teachers: int
    new_teachers: int


class QuestionDistributionItem(BaseModel):
    question_count: int
    tests: int
    scans: int


class FailureReason(BaseModel):
    reason: str
    count: int


class FailureBreakdown(BaseModel):
    period_days: int
    total_scans: int
    ambiguous_count: int
    error_count: int
    overridden_count: int
    ambiguity_rate: float
    failure_rate: float
    reasons: list[FailureReason]


class PlanUsage(BaseModel):
    plan_code: str
    plan_name: str
    price_uzs: int
    subscribers: int
    scans_used: int
    mrr_uzs: int = Field(description="subscribers × price_uzs (taxminiy oylik daromad)")


class TopTeacher(BaseModel):
    user_id: int
    full_name: Optional[str] = None
    username: Optional[str] = None
    telegram_id: int
    scans: int


class ComponentStatus(BaseModel):
    name: str
    status: str
    detail: str = ""
    metrics: dict[str, Any] = Field(default_factory=dict)


class SystemStatus(BaseModel):
    overall: str
    components: list[ComponentStatus]


class DashboardOverview(BaseModel):
    """`GET /api/admin/dashboard/overview` — bitta so'rovda hamma narsa."""

    kpi: KpiCards
    scan_timeseries: list[ScanPoint]
    teacher_activity: list[TeacherActivityPoint]
    question_distribution: list[QuestionDistributionItem]
    failures: FailureBreakdown
    plans: list[PlanUsage]
    top_teachers: list[TopTeacher]
    system: SystemStatus
