"""
app/models/test.py — Test (guruhga tegishli, kalit bilan).

DDL:
    CREATE TABLE tests (
        id             BIGSERIAL PRIMARY KEY,
        group_id       BIGINT NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
        title          TEXT NOT NULL,
        question_count INT NOT NULL,
        variant_count  INT NOT NULL DEFAULT 4,
        answer_key     JSONB NOT NULL,
        created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT chk_qcount CHECK (question_count IN (40,50,90))
    );
    CREATE INDEX idx_tests_group ON tests(group_id);
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Test(Base):
    __tablename__ = "tests"
    __table_args__ = (
        CheckConstraint("question_count IN (40,50,90)", name="chk_qcount"),
        Index("idx_tests_group", "group_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    group_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    question_count: Mapped[int] = mapped_column(Integer, nullable=False)
    variant_count: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    answer_key: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )

    # Relationships
    group: Mapped["Group"] = relationship("Group", back_populates="tests")  # type: ignore[name-defined]
    tituls: Mapped[list["Titul"]] = relationship(  # type: ignore[name-defined]
        "Titul", back_populates="test", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Test id={self.id} title={self.title!r} q={self.question_count}>"
