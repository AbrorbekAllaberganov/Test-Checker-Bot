"""
app/schemas/admin/broadcasts.py — Telegram e'lonlari sxemalari.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import BroadcastAudience
from app.services.broadcast import MAX_BODY_LENGTH


class BroadcastCreateIn(BaseModel):
    """E'lon yaratish (va ixtiyoriy ravishda darrov yuborish)."""

    title: Optional[str] = Field(default=None, max_length=128)
    body: str = Field(min_length=1, max_length=MAX_BODY_LENGTH)
    parse_mode: Literal["HTML", "Markdown", "None"] = "HTML"
    audience: BroadcastAudience = BroadcastAudience.ALL
    target_user_ids: Optional[list[int]] = Field(
        default=None, description="audience='specific' uchun users.id ro'yxati"
    )
    send_now: bool = Field(
        default=False, description="false — 'draft' holatida saqlanadi"
    )

    @model_validator(mode="after")
    def check_targets(self) -> "BroadcastCreateIn":
        if self.audience == BroadcastAudience.SPECIFIC and not self.target_user_ids:
            raise ValueError(
                "audience='specific' bo'lganda target_user_ids bo'sh bo'lmasligi kerak"
            )
        # Sarlavha + matn birgalikda Telegram chegarasidan oshmasin.
        overhead = len(self.title or "") + 4
        if len(self.body) + overhead > MAX_BODY_LENGTH:
            raise ValueError(
                f"Sarlavha va matn birgalikda {MAX_BODY_LENGTH} belgidan oshmasligi kerak"
            )
        return self


class BroadcastListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: Optional[str] = None
    body_preview: str = ""
    audience: str
    status: str
    total_count: int
    sent_count: int
    failed_count: int
    created_by: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class RecipientRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    telegram_id: int
    full_name: Optional[str] = None
    username: Optional[str] = None
    status: str
    error_msg: Optional[str] = None
    sent_at: Optional[datetime] = None


class BroadcastDetail(BroadcastListItem):
    body: str
    parse_mode: str
    target_user_ids: Optional[list[int]] = None
    error_msg: Optional[str] = None
    recipients: list[RecipientRow] = Field(default_factory=list)


class BroadcastPreviewOut(BaseModel):
    """Yuborishdan oldin: kimga ketadi va qanday ko'rinadi."""

    audience: str
    recipients_count: int
    rendered_text: str
    sample_recipients: list[RecipientRow] = Field(default_factory=list)
