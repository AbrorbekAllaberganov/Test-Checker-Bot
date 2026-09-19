"""attempts.submitted_by_id va subscriptions.anchor_day.

1. `attempts.submitted_by_id` (weaknesses.md №37): `attempts` da yuboruvchi
   haqida hech narsa yo'q edi. QR o'qilmagan (`titul_id IS NULL`)
   pending/error skanlar esa hech qanday ustozga bog'lanmagan bo'lib
   qolardi — ular Mini App'dagi ro'yxatga ham, admin panelidagi "kim
   yubordi" ustuniga ham tushmasdi.

2. `subscriptions.anchor_day` (weaknesses.md №18 qoldig'i): davr sanasi
   31-kunda boshlangan obunada bir marta 28/30 ga surilib, keyin o'sha
   kundan davom etardi — ya'ni har yili bir necha kunga oldinga siljirdi.
   Endi asl kun saqlanadi va har oy `min(anchor_day, oydagi_kunlar)`
   olinadi.

Revision ID: 004
Revises: 003
Create Date: 2026-09-19 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "attempts",
        sa.Column("submitted_by_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_attempts_submitted_by",
        "attempts",
        "users",
        ["submitted_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_attempts_submitted_by",
        "attempts",
        ["submitted_by_id"],
    )

    # Mavjud qatorlar uchun to'ldirish: titul → test → group → owner.
    # Yangi ustun NULL bo'lib qolsa eski skanlar egasiz ko'rinardi.
    op.execute(
        """
        UPDATE attempts a
        SET submitted_by_id = g.owner_id
        FROM tituls t
        JOIN tests te ON te.id = t.test_id
        JOIN groups g ON g.id = te.group_id
        WHERE a.titul_id = t.id
          AND a.submitted_by_id IS NULL
        """
    )

    # ── subscriptions.anchor_day ─────────────────────────────────────────
    op.add_column(
        "subscriptions",
        sa.Column("anchor_day", sa.SmallInteger(), nullable=True),
    )
    # Mavjud obunalar uchun joriy davr boshlanish kunidan olamiz.
    op.execute(
        "UPDATE subscriptions SET anchor_day = EXTRACT(DAY FROM period_start)::smallint "
        "WHERE anchor_day IS NULL"
    )
    op.create_check_constraint(
        "ck_subscriptions_anchor_day",
        "subscriptions",
        "anchor_day IS NULL OR (anchor_day BETWEEN 1 AND 31)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_subscriptions_anchor_day", "subscriptions", type_="check")
    op.drop_column("subscriptions", "anchor_day")

    op.drop_index("idx_attempts_submitted_by", table_name="attempts")
    op.drop_constraint("fk_attempts_submitted_by", "attempts", type_="foreignkey")
    op.drop_column("attempts", "submitted_by_id")
