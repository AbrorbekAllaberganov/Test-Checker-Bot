"""
app/models/subscription.py — Ustozning tarifga obunasi va joriy davr kvotasi.

Bitta ustozda bir vaqtda faqat BITTA faol obuna bo'ladi (qisman unique index
`uq_subscriptions_active_user` buni ta'minlaydi). Eski obunalar tarix uchun
`cancelled`/`expired` holatida saqlanib qoladi.

Kvota hisobi:
    limit       = plan.monthly_scan_limit + bonus_credits   (NULL = cheksiz)
    ishlatilgan = scans_used   (har skan qabul qilinganda +1)
    davr        = [period_start, period_end)  — oylik, avtomatik rollover

DDL:
    CREATE TABLE subscriptions (
        id             BIGSERIAL PRIMARY KEY,
        user_id        BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        plan_id        BIGINT NOT NULL REFERENCES plans(id) ON DELETE RESTRICT,
        status         TEXT NOT NULL DEFAULT 'trial',
        starts_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        ends_at        TIMESTAMPTZ,
        period_start   TIMESTAMPTZ NOT NULL DEFAULT now(),
        period_end     TIMESTAMPTZ NOT NULL,
        scans_used     INT NOT NULL DEFAULT 0,
        bonus_credits  INT NOT NULL DEFAULT 0,
        note           TEXT,
        created_by_id  BIGINT REFERENCES users(id) ON DELETE SET NULL,
        created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE UNIQUE INDEX uq_subscriptions_active_user ON subscriptions(user_id)
        WHERE status IN ('active', 'trial');
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import SubscriptionStatus

_STATUSES = ", ".join(f"'{s}'" for s in SubscriptionStatus.values())

# Faol obuna deb hisoblanadigan statuslar — kvota va unique index shu ro'yxatga tayanadi.
LIVE_STATUSES: tuple[str, ...] = (
    SubscriptionStatus.ACTIVE.value,
    SubscriptionStatus.TRIAL.value,
)
_LIVE_SQL = ", ".join(f"'{s}'" for s in LIVE_STATUSES)


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        CheckConstraint(f"status IN ({_STATUSES})", name="chk_subscription_status"),
        CheckConstraint("scans_used >= 0", name="chk_subscription_scans_used"),
        CheckConstraint("bonus_credits >= 0", name="chk_subscription_bonus"),
        Index("idx_subscriptions_user", "user_id"),
        Index("idx_subscriptions_status", "status"),
        # Bitta userda bitta faol obuna (trial ham "faol" hisoblanadi).
        Index(
            "uq_subscriptions_active_user",
            "user_id",
            unique=True,
            postgresql_where=text(f"status IN ({_LIVE_SQL})"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    plan_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default=SubscriptionStatus.TRIAL.value
    )

    starts_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    # NULL — muddatsiz (masalan Enterprise shartnoma yoki doimiy FREE).
    ends_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    # Kvota davri — oylik oyna, services/subscriptions.ensure_period() aylantiradi.
    period_start: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    period_end: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    # Davr "langari" (004): obuna boshlangan kalendar kun (1..31). Har oy
    # `min(anchor_day, oydagi_kunlar)` olinadi — 31-yanvar → 28-fevral →
    # 31-mart. Busiz sana har qisqa oyda oldinga siljib ketardi
    # (weaknesses.md №18).
    anchor_day: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)

    scans_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bonus_credits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships — `user_id` va `created_by_id` ikkalasi ham users'ga ketgani
    # uchun foreign_keys ni aniq ko'rsatish shart.
    user: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User", back_populates="subscriptions", foreign_keys=[user_id]
    )
    plan: Mapped["Plan"] = relationship("Plan", back_populates="subscriptions")  # type: ignore[name-defined]

    # ── Hisob-kitob yordamchilari ────────────────────────────────────────

    @property
    def is_live(self) -> bool:
        """Obuna hozir kuchdami (status + muddat)."""
        if self.status not in LIVE_STATUSES:
            return False
        if self.ends_at is None:
            return True
        return self.ends_at > datetime.now(timezone.utc)

    @property
    def scan_limit(self) -> Optional[int]:
        """Joriy davrdagi to'liq limit (None = cheksiz)."""
        base = self.plan.monthly_scan_limit if self.plan else None
        if base is None:
            return None
        return base + self.bonus_credits

    @property
    def scans_remaining(self) -> Optional[int]:
        limit = self.scan_limit
        if limit is None:
            return None
        return max(limit - self.scans_used, 0)

    def __repr__(self) -> str:
        return f"<Subscription user={self.user_id} plan={self.plan_id} {self.status}>"
