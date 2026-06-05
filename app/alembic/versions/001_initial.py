"""Initial migration — pgcrypto extension + all tables.

Revision ID: 001
Revises:
Create Date: 2026-06-01 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union
import uuid

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pgcrypto — gen_random_uuid() uchun
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

    # ── users ────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=True),
        sa.Column("username", sa.Text(), nullable=True),
        sa.Column("role", sa.Text(), nullable=False, server_default="teacher"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("telegram_id", name="uq_users_telegram_id"),
    )

    # ── groups ───────────────────────────────────────────────────────────
    op.create_table(
        "groups",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], ondelete="CASCADE", name="fk_groups_owner"
        ),
    )
    op.create_index("idx_groups_owner", "groups", ["owner_id"])

    # ── students ─────────────────────────────────────────────────────────
    op.create_table(
        "students",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("group_id", sa.BigInteger(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["group_id"], ["groups.id"], ondelete="CASCADE", name="fk_students_group"
        ),
    )
    op.create_index("idx_students_group", "students", ["group_id"])

    # ── tests ────────────────────────────────────────────────────────────
    op.create_table(
        "tests",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("group_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column("variant_count", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("answer_key", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["group_id"], ["groups.id"], ondelete="CASCADE", name="fk_tests_group"
        ),
        sa.CheckConstraint(
            "question_count IN (40,50,90)", name="chk_qcount"
        ),
    )
    op.create_index("idx_tests_group", "tests", ["group_id"])

    # ── tituls ───────────────────────────────────────────────────────────
    op.create_table(
        "tituls",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "uuid",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
            unique=True,
        ),
        sa.Column("test_id", sa.BigInteger(), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("pdf_path", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["test_id"], ["tests.id"], ondelete="CASCADE", name="fk_tituls_test"
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["students.id"],
            ondelete="CASCADE",
            name="fk_tituls_student",
        ),
        sa.UniqueConstraint(
            "test_id", "student_id", name="uq_titul_test_student"
        ),
    )
    op.create_index("idx_tituls_test", "tituls", ["test_id"])

    # ── attempts ─────────────────────────────────────────────────────────
    op.create_table(
        "attempts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("titul_id", sa.BigInteger(), nullable=False),
        sa.Column("detected", postgresql.JSONB(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("total", sa.Integer(), nullable=True),
        sa.Column("percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("detail", postgresql.JSONB(), nullable=True),
        sa.Column(
            "needs_review", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column("source_file", sa.Text(), nullable=True),
        sa.Column("debug_file", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="done"),
        sa.Column("error_msg", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["titul_id"],
            ["tituls.id"],
            ondelete="CASCADE",
            name="fk_attempts_titul",
        ),
    )
    op.create_index("idx_attempts_titul", "attempts", ["titul_id"])
    op.create_index("idx_attempts_created", "attempts", ["created_at"])


def downgrade() -> None:
    op.drop_table("attempts")
    op.drop_table("tituls")
    op.drop_table("tests")
    op.drop_table("students")
    op.drop_table("groups")
    op.drop_table("users")
    op.execute("DROP EXTENSION IF EXISTS pgcrypto;")
