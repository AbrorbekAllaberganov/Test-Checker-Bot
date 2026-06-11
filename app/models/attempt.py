"""
app/models/attempt.py — O'quvchi yuborgan skan natijasi.

DDL:
    CREATE TABLE attempts (
        id           BIGSERIAL PRIMARY KEY,
        titul_id     BIGINT NOT NULL REFERENCES tituls(id) ON DELETE CASCADE,
        detected     JSONB NOT NULL,
        score        INT,
        total        INT,
        percent      NUMERIC(5,2),
        detail       JSONB,
        needs_review BOOLEAN NOT NULL DEFAULT false,
        source_file  TEXT,
        debug_file   TEXT,
        status       TEXT NOT NULL DEFAULT 'done',
        error_msg    TEXT,
        created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX idx_attempts_titul   ON attempts(titul_id);
    CREATE INDEX idx_attempts_created ON attempts(created_at);
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Attempt(Base):
    __tablename__ = "attempts"
    __table_args__ = (
        Index("idx_attempts_titul", "titul_id"),
        Index("idx_attempts_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # Skan kelganda titul hali noma'lum (QR worker tomonidan o'qiladi),
    # shu sababli pending attempt NULL titul_id bilan yaratiladi.
    titul_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("tituls.id", ondelete="CASCADE"), nullable=True
    )
    detected: Mapped[dict] = mapped_column(JSONB, nullable=False)
    score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    percent: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    detail: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_file: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    debug_file: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="done")
    error_msg: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )

    # Relationships
    titul: Mapped["Titul"] = relationship("Titul", back_populates="attempts")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<Attempt id={self.id} titul={self.titul_id} score={self.score}/{self.total}>"
