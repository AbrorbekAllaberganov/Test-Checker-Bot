"""
app/models/titul.py — Har (test, student) juftligi uchun bitta varaq.

DDL:
    CREATE TABLE tituls (
        id         BIGSERIAL PRIMARY KEY,
        uuid       UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
        test_id    BIGINT NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
        student_id BIGINT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
        pdf_path   TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (test_id, student_id)
    );
    CREATE INDEX idx_tituls_test ON tituls(test_id);
"""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, ForeignKey, Index, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Titul(Base):
    __tablename__ = "tituls"
    __table_args__ = (
        UniqueConstraint("test_id", "student_id", name="uq_titul_test_student"),
        Index("idx_tituls_test", "test_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    uuid: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        unique=True,
        nullable=False,
        server_default=func.gen_random_uuid(),
    )
    test_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tests.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    pdf_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )

    # Relationships
    test: Mapped["Test"] = relationship("Test", back_populates="tituls")  # type: ignore[name-defined]
    student: Mapped["Student"] = relationship("Student", back_populates="tituls")  # type: ignore[name-defined]
    attempts: Mapped[list["Attempt"]] = relationship(  # type: ignore[name-defined]
        "Attempt", back_populates="titul", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Titul id={self.id} uuid={self.uuid}>"
