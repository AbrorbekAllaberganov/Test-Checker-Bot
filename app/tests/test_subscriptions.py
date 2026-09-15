"""
app/tests/test_subscriptions.py — Kvota davri va limit mantiqi testlari.

Bu yerda DB kerak emas: `ensure_period()` va `Subscription` xossalari
faqat ob'ekt holati ustida ishlaydi, shu sababli oddiy soxta (fake)
ob'ektlar bilan sinaladi.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models.plan import Plan
from app.models.subscription import Subscription
from app.services.subscriptions import _next_period_end, ensure_period


def _make_sub(
    *,
    period_start: datetime,
    period_end: datetime,
    scans_used: int = 0,
    bonus: int = 0,
    monthly_limit: int | None = 100,
    status: str = "active",
    ends_at: datetime | None = None,
) -> Subscription:
    """
    Bazaga tegmasdan Subscription nusxasini yasash.

    Declarative konstruktor ishlatiladi (`__new__` emas) — aks holda
    SQLAlchemy atribut instrumentatsiyasi ishga tushmay qoladi.
    """
    sub = Subscription(
        id=1,
        user_id=1,
        plan_id=1,
        status=status,
        ends_at=ends_at,
        period_start=period_start,
        period_end=period_end,
        scans_used=scans_used,
        bonus_credits=bonus,
    )
    # `plan` — relationship, shu sababli HAQIQIY ORM ob'ekti bo'lishi shart
    # (SimpleNamespace SQLAlchemy instrumentatsiyasiga tushmaydi).
    # Sessiyaga qo'shilmagani uchun bazaga hech narsa yozilmaydi.
    sub.plan = Plan(
        id=1,
        code="TEST",
        name="Test",
        price_uzs=0,
        monthly_scan_limit=monthly_limit,
        max_groups=5,
        max_students_per_group=30,
    )
    return sub


class TestNextPeriodEnd:
    def test_adds_one_calendar_month(self):
        start = datetime(2026, 1, 15, tzinfo=timezone.utc)
        assert _next_period_end(start) == datetime(2026, 2, 15, tzinfo=timezone.utc)

    def test_rolls_over_year_boundary(self):
        start = datetime(2026, 12, 10, tzinfo=timezone.utc)
        assert _next_period_end(start) == datetime(2027, 1, 10, tzinfo=timezone.utc)

    def test_clamps_late_day_to_28th(self):
        """31-kun fevralda mavjud emas — 28 ga qisqartiriladi."""
        start = datetime(2026, 1, 31, tzinfo=timezone.utc)
        assert _next_period_end(start) == datetime(2026, 2, 28, tzinfo=timezone.utc)


class TestEnsurePeriod:
    def test_active_period_is_untouched(self):
        now = datetime.now(timezone.utc)
        sub = _make_sub(
            period_start=now - timedelta(days=1),
            period_end=now + timedelta(days=20),
            scans_used=42,
        )
        assert ensure_period(sub, now=now) is False
        assert sub.scans_used == 42

    def test_expired_period_resets_usage(self):
        now = datetime(2026, 3, 5, tzinfo=timezone.utc)
        sub = _make_sub(
            period_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
            period_end=datetime(2026, 2, 1, tzinfo=timezone.utc),
            scans_used=99,
        )
        assert ensure_period(sub, now=now) is True
        assert sub.scans_used == 0
        # Bir necha oy o'tib ketgan bo'lsa ham joriy oyga yetib boradi.
        assert sub.period_end > now

    def test_bonus_credits_survive_rollover(self):
        """Bonus kredit davr bilan kuymaydi — uni admin qo'lda beradi."""
        now = datetime(2026, 3, 5, tzinfo=timezone.utc)
        sub = _make_sub(
            period_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
            period_end=datetime(2026, 2, 1, tzinfo=timezone.utc),
            scans_used=99,
            bonus=50,
        )
        ensure_period(sub, now=now)
        assert sub.bonus_credits == 50


class TestQuotaProperties:
    def test_limit_includes_bonus(self):
        now = datetime.now(timezone.utc)
        sub = _make_sub(
            period_start=now,
            period_end=now + timedelta(days=30),
            scans_used=80,
            bonus=25,
            monthly_limit=100,
        )
        assert sub.scan_limit == 125
        assert sub.scans_remaining == 45

    def test_unlimited_plan_has_no_limit(self):
        now = datetime.now(timezone.utc)
        sub = _make_sub(
            period_start=now,
            period_end=now + timedelta(days=30),
            scans_used=10_000,
            monthly_limit=None,
        )
        assert sub.scan_limit is None
        assert sub.scans_remaining is None

    def test_remaining_never_goes_negative(self):
        now = datetime.now(timezone.utc)
        sub = _make_sub(
            period_start=now,
            period_end=now + timedelta(days=30),
            scans_used=150,
            monthly_limit=100,
        )
        assert sub.scans_remaining == 0

    @pytest.mark.parametrize(
        "status,expected",
        [("active", True), ("trial", True), ("expired", False), ("cancelled", False)],
    )
    def test_is_live_follows_status(self, status, expected):
        now = datetime.now(timezone.utc)
        sub = _make_sub(
            period_start=now,
            period_end=now + timedelta(days=30),
            status=status,
        )
        assert sub.is_live is expected

    def test_is_live_false_when_expired_by_date(self):
        now = datetime.now(timezone.utc)
        sub = _make_sub(
            period_start=now - timedelta(days=60),
            period_end=now + timedelta(days=30),
            status="active",
            ends_at=now - timedelta(days=1),
        )
        assert sub.is_live is False
