"""
app/schemas/admin/users.py — Ustozlar (teachers) boshqaruvi sxemalari.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AdminRole
from app.schemas.admin.subscriptions import SubscriptionOut


class TeacherStats(BaseModel):
    groups_count: int = 0
    students_count: int = 0
    tests_count: int = 0
    scans_count: int = 0
    scans_30d: int = 0
    needs_review_count: int = 0
    avg_score_percent: float = 0.0
    last_scan_at: Optional[datetime] = None


class TeacherListItem(BaseModel):
    """Jadval qatori — ro'yxat uchun zarur minimum."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    telegram_id: int
    full_name: Optional[str] = None
    username: Optional[str] = None
    role: str
    admin_role: Optional[str] = None
    is_blocked: bool
    blocked_reason: Optional[str] = None
    created_at: datetime
    last_seen_at: Optional[datetime] = None

    # Agregatlar (ro'yxat so'rovida bitta JOIN bilan hisoblanadi)
    groups_count: int = 0
    students_count: int = 0
    tests_count: int = 0
    scans_count: int = 0

    # Obuna qisqacha
    plan_code: Optional[str] = None
    plan_name: Optional[str] = None
    subscription_status: Optional[str] = None
    scans_used: int = 0
    scan_limit: Optional[int] = None


class RecentActivityItem(BaseModel):
    attempt_id: int
    student_name: Optional[str] = None
    test_title: Optional[str] = None
    score: Optional[int] = None
    total: Optional[int] = None
    percent: Optional[float] = None
    status: str
    needs_review: bool
    created_at: datetime


class TeacherGroupBrief(BaseModel):
    id: int
    name: str
    students_count: int
    tests_count: int
    created_at: datetime


class TeacherDetail(BaseModel):
    """Drawer/sahifa uchun to'liq profil."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    telegram_id: int
    full_name: Optional[str] = None
    username: Optional[str] = None
    role: str
    admin_role: Optional[str] = None
    is_blocked: bool
    blocked_reason: Optional[str] = None
    blocked_at: Optional[datetime] = None
    blocked_by: Optional[str] = None
    created_at: datetime
    last_seen_at: Optional[datetime] = None

    stats: TeacherStats
    subscription: Optional[SubscriptionOut] = None
    groups: list[TeacherGroupBrief] = Field(default_factory=list)
    recent_activity: list[RecentActivityItem] = Field(default_factory=list)


class BlockUserIn(BaseModel):
    """Bloklash/blokdan chiqarish."""

    blocked: bool
    reason: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Bloklash sababi — foydalanuvchiga botda ko'rsatiladi",
    )


class ChangeAdminRoleIn(BaseModel):
    """Admin panel rolini o'zgartirish (NULL — panelga kirishni bekor qilish)."""

    admin_role: Optional[AdminRole] = None
