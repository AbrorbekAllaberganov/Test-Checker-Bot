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
        created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
        -- 003: OMR inspektor va qo'lda tuzatish uchun
        confidence      NUMERIC(5,4),   -- 0..1, o'rtacha doira ishonchliligi
        bubble_data     JSONB,          -- {"1": {"ratios": {...}, "conf": .., "flag": ..}}
        manual_override BOOLEAN NOT NULL DEFAULT false,
        reviewed_by_id  BIGINT REFERENCES users(id) ON DELETE SET NULL,
        reviewed_at     TIMESTAMPTZ,
        -- 004: skanni kim yubordi (QR o'qilmagan skanlar ham egali bo'lsin)
        submitted_by_id BIGINT REFERENCES users(id) ON DELETE SET NULL
    );
    CREATE INDEX idx_attempts_titul   ON attempts(titul_id);
    CREATE INDEX idx_attempts_created ON attempts(created_at);
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Attempt(Base):
    __tablename__ = "attempts"
    __table_args__ = (
        Index("idx_attempts_titul", "titul_id"),
        Index("idx_attempts_created", "created_at"),
        # Admin panel: status/review bo'yicha filtr + sana bo'yicha tartib.
        Index("idx_attempts_status_created", "status", "created_at"),
        Index("idx_attempts_needs_review", "needs_review", "created_at"),
        Index("idx_attempts_submitted_by", "submitted_by_id"),
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
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    # ── OMR inspektori uchun (003) ───────────────────────────────────────
    # O'rtacha tanlov ishonchliligi (0..1). Pipeline'dagi decide_answer()
    # qaytargan `conf` qiymatlarining o'rtachasi; eski qatorlarda NULL.
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)
    # Har savol uchun to'liq fill_ratio/flag ma'lumoti — heatmap chizish uchun.
    bubble_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # ── Qo'lda tuzatish (review queue) ───────────────────────────────────
    manual_override: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    reviewed_by_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    # ── Kim yubordi (004) ────────────────────────────────────────────────
    # `titul_id` NULL bo'lgan (QR o'qilmagan) skanlar uchun YAGONA egalik
    # belgisi. Busiz eng muammoli skanlar hech kimga ko'rinmasdi.
    submitted_by_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    titul: Mapped["Titul"] = relationship("Titul", back_populates="attempts")  # type: ignore[name-defined]
    reviewed_by: Mapped[Optional["User"]] = relationship(  # type: ignore[name-defined]
        "User", foreign_keys=[reviewed_by_id]
    )
    submitted_by: Mapped[Optional["User"]] = relationship(  # type: ignore[name-defined]
        "User", foreign_keys=[submitted_by_id]
    )

    def __repr__(self) -> str:
        return f"<Attempt id={self.id} titul={self.titul_id} score={self.score}/{self.total}>"
