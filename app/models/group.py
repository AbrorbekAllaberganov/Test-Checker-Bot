"""
app/models/group.py — Ustoz ochadigan guruh.

DDL:
    CREATE TABLE groups (
        id         BIGSERIAL PRIMARY KEY,
        owner_id   BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        name       TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX idx_groups_owner ON groups(owner_id);
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Group(Base):
    __tablename__ = "groups"
    __table_args__ = (Index("idx_groups_owner", "owner_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )

    # Relationships
    owner: Mapped["User"] = relationship("User", back_populates="groups")  # type: ignore[name-defined]
    students: Mapped[list["Student"]] = relationship(  # type: ignore[name-defined]
        "Student", back_populates="group", cascade="all, delete-orphan"
    )
    tests: Mapped[list["Test"]] = relationship(  # type: ignore[name-defined]
        "Test", back_populates="group", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Group id={self.id} name={self.name!r}>"
