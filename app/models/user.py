"""
app/models/user.py — Telegram orqali kiradigan foydalanuvchi (ustoz/admin).

DDL (docs/02):
    CREATE TABLE users (
        id          BIGSERIAL PRIMARY KEY,
        telegram_id BIGINT UNIQUE NOT NULL,
        full_name   TEXT,
        username    TEXT,
        role        TEXT NOT NULL DEFAULT 'teacher',
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    );
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    username: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    role: Mapped[str] = mapped_column(Text, nullable=False, default="teacher")
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )

    # Relationships
    groups: Mapped[list["Group"]] = relationship(  # type: ignore[name-defined]
        "Group", back_populates="owner", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} tg={self.telegram_id} role={self.role}>"
