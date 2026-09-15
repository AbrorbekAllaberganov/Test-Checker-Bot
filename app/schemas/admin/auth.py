"""
app/schemas/admin/auth.py — Admin autentifikatsiyasi sxemalari.

Ikki xil kirish yo'li:
  1. Telegram Mini App — `initData` imzosi (telefon/panel ichida).
  2. Bir martalik kod (OTP) — bot admin'ga 6 xonali kod yuboradi
     (kompyuter brauzerida panelga kirish uchun).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class OtpRequestIn(BaseModel):
    """Bot orqali bir martalik kod so'rash."""

    telegram_id: int = Field(gt=0, description="Admin'ning Telegram ID raqami")


class OtpRequestOut(BaseModel):
    ok: bool = True
    message: str
    # Kodni qayta so'rashgacha qolgan sekundlar (frontend'da taymer uchun).
    retry_after_seconds: int = 0
    expires_in_seconds: int = 0


class OtpVerifyIn(BaseModel):
    telegram_id: int = Field(gt=0)
    code: str = Field(min_length=4, max_length=8, pattern=r"^\d+$")


class TelegramLoginIn(BaseModel):
    """Telegram Mini App `initData` qatori (imzo bilan)."""

    init_data: str = Field(min_length=10)


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=10)


class AdminProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    telegram_id: int
    full_name: Optional[str] = None
    username: Optional[str] = None
    admin_role: str
    created_at: datetime


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token amal qilish muddati (sekund)")
    profile: AdminProfile
