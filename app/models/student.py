"""
app/models/student.py — Guruhdagi o'quvchi.

DDL:
    CREATE TABLE students (
        id          BIGSERIAL PRIMARY KEY,
        group_id    BIGINT NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
        full_name   TEXT NOT NULL,
        telegram_id BIGINT,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX idx_students_group ON students(group_id);
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Student(Base):
    __tablename__ = "students"
    __table_args__ = (Index("idx_students_group", "group_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    group_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False
    )
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )

    # Relationships
    group: Mapped["Group"] = relationship("Group", back_populates="students")  # type: ignore[name-defined]
    tituls: Mapped[list["Titul"]] = relationship(  # type: ignore[name-defined]
        "Titul", back_populates="student", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Student id={self.id} name={self.full_name!r}>"
