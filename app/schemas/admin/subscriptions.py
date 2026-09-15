"""
app/schemas/admin/subscriptions.py — Tarif va obuna sxemalari.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import SubscriptionStatus


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    description: Optional[str] = None
    price_uzs: int
    max_groups: Optional[int] = Field(default=None, description="NULL = cheksiz")
    max_students_per_group: Optional[int] = None
    monthly_scan_limit: Optional[int] = None
    is_active: bool
    sort_order: int
    subscribers_count: int = 0


class PlanIn(BaseModel):
    """Tarif yaratish/tahrirlash (SUPERADMIN)."""

    code: str = Field(min_length=2, max_length=32, pattern=r"^[A-Z0-9_]+$")
    name: str = Field(min_length=1, max_length=64)
    description: Optional[str] = Field(default=None, max_length=500)
    price_uzs: int = Field(ge=0)
    max_groups: Optional[int] = Field(default=None, ge=0)
    max_students_per_group: Optional[int] = Field(default=None, ge=0)
    monthly_scan_limit: Optional[int] = Field(default=None, ge=0)
    is_active: bool = True
    sort_order: int = 0


class SubscriptionOut(BaseModel):
    """Bitta ustozning joriy obunasi."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_id: int
    plan_code: str
    plan_name: str
    status: str
    starts_at: datetime
    ends_at: Optional[datetime] = None
    period_start: datetime
    period_end: datetime
    scans_used: int
    bonus_credits: int
    scan_limit: Optional[int] = Field(default=None, description="NULL = cheksiz")
    scans_remaining: Optional[int] = None
    usage_percent: float = 0.0
    max_groups: Optional[int] = None
    max_students_per_group: Optional[int] = None
    note: Optional[str] = None


class SubscriptionRow(BaseModel):
    """Obunalar jadvali qatori (ustoz ma'lumoti bilan)."""

    user_id: int
    telegram_id: int
    full_name: Optional[str] = None
    username: Optional[str] = None
    is_blocked: bool
    subscription: Optional[SubscriptionOut] = None


class AssignPlanIn(BaseModel):
    """Ustozga tarif biriktirish / yangilash / uzaytirish."""

    plan_id: int = Field(gt=0)
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE
    duration_days: Optional[int] = Field(
        default=None, ge=1, le=3650, description="NULL = muddatsiz"
    )
    reset_usage: bool = Field(
        default=False, description="true — joriy davr sarfini nolga tushiradi"
    )
    note: Optional[str] = Field(default=None, max_length=500)


class GrantCreditsIn(BaseModel):
    """Qo'shimcha skan krediti (manfiy qiymat — qaytarib olish)."""

    credits: int = Field(ge=-100_000, le=100_000)
    note: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def non_zero(self) -> "GrantCreditsIn":
        if self.credits == 0:
            raise ValueError("credits 0 bo'lishi mumkin emas")
        return self
