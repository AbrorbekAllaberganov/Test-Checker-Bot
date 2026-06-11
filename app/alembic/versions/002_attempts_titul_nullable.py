"""attempts.titul_id ni nullable qilish.

Skan kelganda titul hali noma'lum (u rasm ichidagi QR orqali worker tomonidan
aniqlanadi). Shu sababli pending attempt titul_id=NULL bilan yaratiladi va
omr_task QR ni o'qib haqiqiy titul_id ni keyin to'ldiradi. Eski "placeholder
titul_id=1" yondashuvi FK cheklovni buzardi (id=1 titul mavjud bo'lmasa).

Revision ID: 002
Revises: 001
Create Date: 2026-06-11 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "attempts",
        "titul_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )


def downgrade() -> None:
    # NOT NULL ni qaytarish — avval NULL qatorlarni tozalash kerak,
    # aks holda ALTER yiqiladi.
    op.execute("DELETE FROM attempts WHERE titul_id IS NULL;")
    op.alter_column(
        "attempts",
        "titul_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
