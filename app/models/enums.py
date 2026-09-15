"""
app/models/enums.py — Admin panel va SaaS qatlamidagi umumiy enum'lar.

Bazada ular TEXT + CHECK constraint sifatida saqlanadi (PostgreSQL ENUM turi
emas) — shunda yangi qiymat qo'shish oddiy migratsiya bilan hal bo'ladi va
`ALTER TYPE ... ADD VALUE` ning tranzaksiya cheklovlariga tushib qolmaymiz.
"""
from __future__ import annotations

from enum import StrEnum


class AdminRole(StrEnum):
    """Admin panelga kirish darajalari."""

    SUPERADMIN = "SUPERADMIN"          # hamma narsa
    SUPPORT_OPERATOR = "SUPPORT_OPERATOR"  # bloklash, review, broadcast
    ANALYST = "ANALYST"                # faqat o'qish

    @classmethod
    def values(cls) -> list[str]:
        return [r.value for r in cls]


class PlanCode(StrEnum):
    """Standart tarif kodlari (seed migratsiyada yaratiladi)."""

    FREE = "FREE"
    STANDARD = "STANDARD"
    PRO = "PRO"
    ENTERPRISE = "ENTERPRISE"

    @classmethod
    def values(cls) -> list[str]:
        return [p.value for p in cls]


class SubscriptionStatus(StrEnum):
    """Obuna holati."""

    TRIAL = "trial"
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"

    @classmethod
    def values(cls) -> list[str]:
        return [s.value for s in cls]


class BroadcastStatus(StrEnum):
    """Telegram e'lon holati."""

    DRAFT = "draft"
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @classmethod
    def values(cls) -> list[str]:
        return [s.value for s in cls]


class BroadcastAudience(StrEnum):
    """E'lon kimga yuboriladi."""

    ALL = "all"                    # barcha ustozlar (bloklanmaganlar)
    ACTIVE_SUBSCRIBERS = "active_subscribers"  # pullik + faol obunachilar
    FREE_TIER = "free_tier"        # FREE tarifdagilar
    SPECIFIC = "specific"          # qo'lda tanlangan user_id'lar

    @classmethod
    def values(cls) -> list[str]:
        return [a.value for a in cls]


class RecipientStatus(StrEnum):
    """Har bir qabul qiluvchi uchun yuborish natijasi."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    BLOCKED_BOT = "blocked_bot"   # foydalanuvchi botni bloklagan (403)

    @classmethod
    def values(cls) -> list[str]:
        return [s.value for s in cls]


class AuditAction(StrEnum):
    """Audit jurnaliga yoziladigan amallar."""

    USER_BLOCK = "user.block"
    USER_UNBLOCK = "user.unblock"
    USER_ROLE_CHANGE = "user.role_change"
    SUBSCRIPTION_ASSIGN = "subscription.assign"
    SUBSCRIPTION_RENEW = "subscription.renew"
    SUBSCRIPTION_CANCEL = "subscription.cancel"
    SUBSCRIPTION_CREDITS = "subscription.grant_credits"
    PLAN_CREATE = "plan.create"
    PLAN_UPDATE = "plan.update"
    ATTEMPT_OVERRIDE = "attempt.override"
    BROADCAST_SEND = "broadcast.send"
    BROADCAST_CANCEL = "broadcast.cancel"
    ADMIN_LOGIN = "admin.login"
