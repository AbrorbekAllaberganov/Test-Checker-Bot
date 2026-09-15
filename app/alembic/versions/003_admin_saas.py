"""Admin panel + SaaS qatlami: plans, subscriptions, audit_logs, broadcasts.

Qo'shiladi:
  • plans / subscriptions       — tarif va kvota
  • audit_logs                  — admin amallari jurnali
  • broadcasts / broadcast_recipients — Telegram e'lonlari
  • users.*                     — admin_role, is_blocked, blocked_*, last_seen_at
  • attempts.*                  — confidence, bubble_data, manual_override, reviewed_*

Seed: 4 ta standart tarif (FREE / STANDARD / PRO / ENTERPRISE) va mavjud
barcha ustozlarga FREE obunasi (downgrade'da ular ham o'chadi).

Revision ID: 003
Revises: 002
Create Date: 2026-09-15 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Standart tariflar — monthly_scan_limit NULL = cheksiz.
_SEED_PLANS = [
    {
        "code": "FREE",
        "name": "Bepul",
        "description": "Tanishib chiqish uchun. Cheklangan guruh va skan.",
        "price_uzs": 0,
        "max_groups": 2,
        "max_students_per_group": 30,
        "monthly_scan_limit": 100,
        "sort_order": 10,
    },
    {
        "code": "STANDARD",
        "name": "Standart",
        "description": "Bir nechta guruh bilan ishlaydigan ustozlar uchun.",
        "price_uzs": 99_000,
        "max_groups": 10,
        "max_students_per_group": 60,
        "monthly_scan_limit": 1_500,
        "sort_order": 20,
    },
    {
        "code": "PRO",
        "name": "Pro",
        "description": "Repetitor markazlari uchun kengaytirilgan limitlar.",
        "price_uzs": 249_000,
        "max_groups": 50,
        "max_students_per_group": 150,
        "monthly_scan_limit": 10_000,
        "sort_order": 30,
    },
    {
        "code": "ENTERPRISE",
        "name": "Maktab / Enterprise",
        "description": "Cheksiz limitlar, shartnoma asosida.",
        "price_uzs": 0,
        "max_groups": None,
        "max_students_per_group": None,
        "monthly_scan_limit": None,
        "sort_order": 40,
    },
]


def upgrade() -> None:
    # ── plans ────────────────────────────────────────────────────────────
    op.create_table(
        "plans",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price_uzs", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("max_groups", sa.Integer(), nullable=True),
        sa.Column("max_students_per_group", sa.Integer(), nullable=True),
        sa.Column("monthly_scan_limit", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("code", name="uq_plans_code"),
    )

    # ── users kengaytmalari ──────────────────────────────────────────────
    op.add_column("users", sa.Column("admin_role", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("users", sa.Column("blocked_reason", sa.Text(), nullable=True))
    op.add_column(
        "users", sa.Column("blocked_at", sa.TIMESTAMP(timezone=True), nullable=True)
    )
    op.add_column("users", sa.Column("blocked_by_id", sa.BigInteger(), nullable=True))
    op.add_column(
        "users", sa.Column("last_seen_at", sa.TIMESTAMP(timezone=True), nullable=True)
    )
    op.create_foreign_key(
        "fk_users_blocked_by",
        "users",
        "users",
        ["blocked_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("idx_users_admin_role", "users", ["admin_role"])
    op.create_index("idx_users_is_blocked", "users", ["is_blocked"])
    op.create_check_constraint(
        "chk_users_admin_role",
        "users",
        "admin_role IS NULL OR admin_role IN ('SUPERADMIN', 'SUPPORT_OPERATOR', 'ANALYST')",
    )

    # Eski 'admin' rolidagilar avtomatik SUPERADMIN bo'ladi.
    op.execute("UPDATE users SET admin_role = 'SUPERADMIN' WHERE role = 'admin'")

    # ── subscriptions ────────────────────────────────────────────────────
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("plan_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="trial"),
        sa.Column(
            "starts_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("ends_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "period_start",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("period_end", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("scans_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bonus_credits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "status IN ('trial', 'active', 'expired', 'cancelled')",
            name="chk_subscription_status",
        ),
        sa.CheckConstraint("scans_used >= 0", name="chk_subscription_scans_used"),
        sa.CheckConstraint("bonus_credits >= 0", name="chk_subscription_bonus"),
    )
    op.create_index("idx_subscriptions_user", "subscriptions", ["user_id"])
    op.create_index("idx_subscriptions_status", "subscriptions", ["status"])
    # Bir userda bir vaqtda faqat bitta faol obuna.
    op.create_index(
        "uq_subscriptions_active_user",
        "subscriptions",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('active', 'trial')"),
    )

    # ── audit_logs ───────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("actor_id", sa.BigInteger(), nullable=True),
        sa.Column("actor_label", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("object_type", sa.Text(), nullable=True),
        sa.Column("object_id", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ip_address", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_audit_logs_created", "audit_logs", ["created_at"])
    op.create_index("idx_audit_logs_actor", "audit_logs", ["actor_id"])
    op.create_index("idx_audit_logs_action", "audit_logs", ["action"])
    op.create_index("idx_audit_logs_object", "audit_logs", ["object_type", "object_id"])

    # ── broadcasts ───────────────────────────────────────────────────────
    op.create_table(
        "broadcasts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("parse_mode", sa.Text(), nullable=False, server_default="HTML"),
        sa.Column("audience", sa.Text(), nullable=False),
        sa.Column(
            "target_user_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sent_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_msg", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "status IN ('draft', 'queued', 'sending', 'sent', 'failed', 'cancelled')",
            name="chk_broadcast_status",
        ),
        sa.CheckConstraint(
            "audience IN ('all', 'active_subscribers', 'free_tier', 'specific')",
            name="chk_broadcast_audience",
        ),
    )
    op.create_index("idx_broadcasts_created", "broadcasts", ["created_at"])
    op.create_index("idx_broadcasts_status", "broadcasts", ["status"])

    op.create_table(
        "broadcast_recipients",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("broadcast_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("error_msg", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["broadcast_id"], ["broadcasts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("broadcast_id", "user_id", name="uq_broadcast_recipient"),
        sa.CheckConstraint(
            "status IN ('pending', 'sent', 'failed', 'blocked_bot')",
            name="chk_recipient_status",
        ),
    )
    op.create_index(
        "idx_broadcast_recipients_broadcast",
        "broadcast_recipients",
        ["broadcast_id", "status"],
    )

    # ── attempts kengaytmalari ───────────────────────────────────────────
    op.add_column("attempts", sa.Column("confidence", sa.Numeric(5, 4), nullable=True))
    op.add_column(
        "attempts",
        sa.Column("bubble_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "attempts",
        sa.Column(
            "manual_override", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column("attempts", sa.Column("reviewed_by_id", sa.BigInteger(), nullable=True))
    op.add_column(
        "attempts", sa.Column("reviewed_at", sa.TIMESTAMP(timezone=True), nullable=True)
    )
    op.create_foreign_key(
        "fk_attempts_reviewed_by",
        "attempts",
        "users",
        ["reviewed_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_attempts_status_created", "attempts", ["status", "created_at"]
    )
    op.create_index(
        "idx_attempts_needs_review", "attempts", ["needs_review", "created_at"]
    )

    # ── Seed: standart tariflar ──────────────────────────────────────────
    plans_table = sa.table(
        "plans",
        sa.column("code", sa.Text),
        sa.column("name", sa.Text),
        sa.column("description", sa.Text),
        sa.column("price_uzs", sa.BigInteger),
        sa.column("max_groups", sa.Integer),
        sa.column("max_students_per_group", sa.Integer),
        sa.column("monthly_scan_limit", sa.Integer),
        sa.column("sort_order", sa.Integer),
    )
    op.bulk_insert(plans_table, _SEED_PLANS)

    # ── Seed: mavjud ustozlarga FREE obunasi ─────────────────────────────
    # period_end — bugundan +1 oy. Obunasi yo'q userlar bot kvotasidan
    # o'tolmay qolmasligi uchun migratsiyada darrov yaratib qo'yamiz.
    op.execute(
        """
        INSERT INTO subscriptions
            (user_id, plan_id, status, starts_at, ends_at,
             period_start, period_end, scans_used, bonus_credits, note)
        SELECT
            u.id,
            p.id,
            'active',
            now(),
            NULL,
            date_trunc('month', now()),
            date_trunc('month', now()) + interval '1 month',
            0,
            0,
            'Migratsiya 003 tomonidan avtomatik yaratildi'
        FROM users u
        CROSS JOIN (SELECT id FROM plans WHERE code = 'FREE') p
        """
    )


def downgrade() -> None:
    op.drop_index("idx_attempts_needs_review", table_name="attempts")
    op.drop_index("idx_attempts_status_created", table_name="attempts")
    op.drop_constraint("fk_attempts_reviewed_by", "attempts", type_="foreignkey")
    op.drop_column("attempts", "reviewed_at")
    op.drop_column("attempts", "reviewed_by_id")
    op.drop_column("attempts", "manual_override")
    op.drop_column("attempts", "bubble_data")
    op.drop_column("attempts", "confidence")

    op.drop_table("broadcast_recipients")
    op.drop_table("broadcasts")
    op.drop_table("audit_logs")
    op.drop_table("subscriptions")
    op.drop_table("plans")

    op.drop_constraint("chk_users_admin_role", "users", type_="check")
    op.drop_index("idx_users_is_blocked", table_name="users")
    op.drop_index("idx_users_admin_role", table_name="users")
    op.drop_constraint("fk_users_blocked_by", "users", type_="foreignkey")
    op.drop_column("users", "last_seen_at")
    op.drop_column("users", "blocked_by_id")
    op.drop_column("users", "blocked_at")
    op.drop_column("users", "blocked_reason")
    op.drop_column("users", "is_blocked")
    op.drop_column("users", "admin_role")
