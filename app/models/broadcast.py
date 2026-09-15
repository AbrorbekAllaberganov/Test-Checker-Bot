"""
app/models/broadcast.py — Telegram e'lonlari (broadcast) va ularning qabul
qiluvchilari.

`broadcasts` — e'lon matni va auditoriyasi.
`broadcast_recipients` — har bir ustozga yuborish natijasi (idempotentlik uchun:
    qayta ishga tushirilsa `sent` bo'lganlarga ikkinchi marta yuborilmaydi).

DDL:
    CREATE TABLE broadcasts (
        id             BIGSERIAL PRIMARY KEY,
        title          TEXT,
        body           TEXT NOT NULL,
        parse_mode     TEXT NOT NULL DEFAULT 'HTML',
        audience       TEXT NOT NULL,
        target_user_ids JSONB,
        status         TEXT NOT NULL DEFAULT 'draft',
        total_count    INT NOT NULL DEFAULT 0,
        sent_count     INT NOT NULL DEFAULT 0,
        failed_count   INT NOT NULL DEFAULT 0,
        error_msg      TEXT,
        created_by_id  BIGINT REFERENCES users(id) ON DELETE SET NULL,
        created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
        started_at     TIMESTAMPTZ,
        finished_at    TIMESTAMPTZ
    );
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import BroadcastAudience, BroadcastStatus, RecipientStatus

_B_STATUSES = ", ".join(f"'{s}'" for s in BroadcastStatus.values())
_AUDIENCES = ", ".join(f"'{a}'" for a in BroadcastAudience.values())
_R_STATUSES = ", ".join(f"'{s}'" for s in RecipientStatus.values())


class Broadcast(Base):
    __tablename__ = "broadcasts"
    __table_args__ = (
        CheckConstraint(f"status IN ({_B_STATUSES})", name="chk_broadcast_status"),
        CheckConstraint(f"audience IN ({_AUDIENCES})", name="chk_broadcast_audience"),
        Index("idx_broadcasts_created", "created_at"),
        Index("idx_broadcasts_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    parse_mode: Mapped[str] = mapped_column(Text, nullable=False, default="HTML")

    audience: Mapped[str] = mapped_column(Text, nullable=False)
    # audience='specific' bo'lganda — tanlangan users.id lar ro'yxati.
    target_user_ids: Mapped[Optional[list[int]]] = mapped_column(JSONB, nullable=True)

    status: Mapped[str] = mapped_column(
        Text, nullable=False, default=BroadcastStatus.DRAFT.value
    )
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_msg: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_by_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    recipients: Mapped[list["BroadcastRecipient"]] = relationship(
        "BroadcastRecipient",
        back_populates="broadcast",
        cascade="all, delete-orphan",
    )
    created_by: Mapped[Optional["User"]] = relationship(  # type: ignore[name-defined]
        "User", foreign_keys=[created_by_id]
    )

    def __repr__(self) -> str:
        return f"<Broadcast id={self.id} {self.status} {self.sent_count}/{self.total_count}>"


class BroadcastRecipient(Base):
    __tablename__ = "broadcast_recipients"
    __table_args__ = (
        UniqueConstraint("broadcast_id", "user_id", name="uq_broadcast_recipient"),
        CheckConstraint(f"status IN ({_R_STATUSES})", name="chk_recipient_status"),
        Index("idx_broadcast_recipients_broadcast", "broadcast_id", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    broadcast_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("broadcasts.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # Yuborish paytidagi chat_id nusxasi (user o'chirilsa ham tarix qoladi).
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    status: Mapped[str] = mapped_column(
        Text, nullable=False, default=RecipientStatus.PENDING.value
    )
    error_msg: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    broadcast: Mapped["Broadcast"] = relationship("Broadcast", back_populates="recipients")

    def __repr__(self) -> str:
        return f"<BroadcastRecipient b={self.broadcast_id} u={self.user_id} {self.status}>"
