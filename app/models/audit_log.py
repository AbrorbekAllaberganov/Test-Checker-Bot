"""
app/models/audit_log.py — Admin amallari jurnali.

Har bir o'zgartiruvchi admin amali (bloklash, tarif almashtirish, natijani
qo'lda tuzatish, e'lon yuborish) shu yerga yoziladi. Jurnal faqat qo'shiladi —
API orqali o'chirish yoki tahrirlash yo'q.

DDL:
    CREATE TABLE audit_logs (
        id          BIGSERIAL PRIMARY KEY,
        actor_id    BIGINT REFERENCES users(id) ON DELETE SET NULL,
        actor_label TEXT NOT NULL,
        action      TEXT NOT NULL,
        object_type TEXT,
        object_id   TEXT,
        payload     JSONB,
        ip_address  TEXT,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    );
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import TIMESTAMP, BigInteger, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_logs_created", "created_at"),
        Index("idx_audit_logs_actor", "actor_id"),
        Index("idx_audit_logs_action", "action"),
        Index("idx_audit_logs_object", "object_type", "object_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # Admin o'chirilsa ham jurnal o'qilarli qolishi uchun `actor_label` da
    # ism/username nusxasi saqlanadi.
    actor_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_label: Mapped[str] = mapped_column(Text, nullable=False)

    action: Mapped[str] = mapped_column(Text, nullable=False)
    object_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    object_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Amal tafsiloti: {"before": {...}, "after": {...}, "reason": "..."}
    payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    actor: Mapped[Optional["User"]] = relationship(  # type: ignore[name-defined]
        "User", foreign_keys=[actor_id]
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} by={self.actor_label} obj={self.object_type}:{self.object_id}>"
