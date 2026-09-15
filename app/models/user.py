"""
app/models/user.py — Telegram orqali kiradigan foydalanuvchi (ustoz/admin).

DDL (docs/02 + 003 migratsiya):
    CREATE TABLE users (
        id             BIGSERIAL PRIMARY KEY,
        telegram_id    BIGINT UNIQUE NOT NULL,
        full_name      TEXT,
        username       TEXT,
        role           TEXT NOT NULL DEFAULT 'teacher',
        -- 003: admin panel va moderatsiya
        admin_role     TEXT,            -- SUPERADMIN | SUPPORT_OPERATOR | ANALYST
        is_blocked     BOOLEAN NOT NULL DEFAULT false,
        blocked_reason TEXT,
        blocked_at     TIMESTAMPTZ,
        blocked_by_id  BIGINT REFERENCES users(id) ON DELETE SET NULL,
        last_seen_at   TIMESTAMPTZ,
        created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
    );
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import TIMESTAMP, BigInteger, Boolean, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import AdminRole


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("idx_users_admin_role", "admin_role"),
        Index("idx_users_is_blocked", "is_blocked"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    username: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    role: Mapped[str] = mapped_column(Text, nullable=False, default="teacher")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    # ── Admin panel roli (NULL = oddiy ustoz, panelga kira olmaydi) ──────
    admin_role: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Moderatsiya ──────────────────────────────────────────────────────
    is_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    blocked_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    blocked_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    blocked_by_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Faollik analitikasi uchun — bot yoki dashboard'ga oxirgi kirish.
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    # Relationships
    groups: Mapped[list["Group"]] = relationship(  # type: ignore[name-defined]
        "Group", back_populates="owner", cascade="all, delete-orphan"
    )
    subscriptions: Mapped[list["Subscription"]] = relationship(  # type: ignore[name-defined]
        "Subscription",
        back_populates="user",
        foreign_keys="Subscription.user_id",
        cascade="all, delete-orphan",
    )
    blocked_by: Mapped[Optional["User"]] = relationship(
        "User", remote_side=[id], foreign_keys=[blocked_by_id]
    )

    # ── Yordamchilar ─────────────────────────────────────────────────────

    @property
    def is_admin(self) -> bool:
        """Admin panelga kirish huquqi bormi."""
        return self.admin_role in AdminRole.values()

    @property
    def is_superadmin(self) -> bool:
        return self.admin_role == AdminRole.SUPERADMIN

    @property
    def display_name(self) -> str:
        """UI va audit jurnali uchun o'qilarli nom."""
        if self.full_name:
            return self.full_name
        if self.username:
            return f"@{self.username}"
        return f"tg:{self.telegram_id}"

    def __repr__(self) -> str:
        return f"<User id={self.id} tg={self.telegram_id} role={self.role} admin={self.admin_role}>"
