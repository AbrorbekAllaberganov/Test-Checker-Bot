"""
app/models/plan.py — SaaS tarif rejasi (Free / Standard / Pro / Enterprise).

Kvotalar shu jadvalda saqlanadi; obuna (`subscriptions`) esa ustozni tarifga
bog'laydi va joriy davrdagi sarfni hisoblaydi.

DDL:
    CREATE TABLE plans (
        id                  BIGSERIAL PRIMARY KEY,
        code                TEXT UNIQUE NOT NULL,
        name                TEXT NOT NULL,
        description         TEXT,
        price_uzs           BIGINT NOT NULL DEFAULT 0,
        max_groups          INT,     -- NULL = cheksiz
        max_students_per_group INT,  -- NULL = cheksiz
        monthly_scan_limit  INT,     -- NULL = cheksiz
        is_active           BOOLEAN NOT NULL DEFAULT true,
        sort_order          INT NOT NULL DEFAULT 0,
        created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
    );
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import TIMESTAMP, BigInteger, Boolean, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price_uzs: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    # NULL — cheksiz. 0 — umuman ruxsat yo'q.
    max_groups: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_students_per_group: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    monthly_scan_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    subscriptions: Mapped[list["Subscription"]] = relationship(  # type: ignore[name-defined]
        "Subscription", back_populates="plan"
    )

    @property
    def is_unlimited_scans(self) -> bool:
        return self.monthly_scan_limit is None

    def __repr__(self) -> str:
        return f"<Plan {self.code} limit={self.monthly_scan_limit}>"
