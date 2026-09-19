"""
app/tests/test_db_commit.py — `get_db` qachon commit qilishi (T-33).

Optimizatsiya (har GET'da COMMIT yubormaslik) yozuvni YO'QOTMASLIGI kerak:
`flush()` dan keyin `session.dirty` bo'shaydi, shu sababli faqat unga
qarash xavfli edi.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.db import _session_has_writes
from app.models.user import User


@pytest.mark.asyncio
async def test_read_only_session_is_not_committed(db_session):
    """Faqat SELECT — commit kerak emas."""
    await db_session.execute(select(User).limit(1))
    assert _session_has_writes(db_session) is False


@pytest.mark.asyncio
async def test_pending_object_needs_commit(db_session):
    db_session.add(User(telegram_id=770_001, full_name="Pending User"))
    assert _session_has_writes(db_session) is True


@pytest.mark.asyncio
async def test_flushed_change_still_needs_commit(db_session):
    """
    ENG MUHIM HOLAT: `flush()` dan keyin `dirty` bo'sh, lekin tranzaksiyada
    yozuv bor. `get_active_subscription()` aynan shunday ishlaydi (obunani
    `expired` qilib flush qiladi).
    """
    user = User(telegram_id=770_002, full_name="Flushed User")
    db_session.add(user)
    await db_session.flush()

    assert not db_session.new
    assert not db_session.dirty
    assert _session_has_writes(db_session) is True


@pytest.mark.asyncio
async def test_flushed_update_still_needs_commit(db_session):
    user = User(telegram_id=770_003, full_name="Before")
    db_session.add(user)
    await db_session.flush()
    db_session.sync_session.info.pop("omr_has_writes", None)

    user.full_name = "After"
    await db_session.flush()

    assert not db_session.dirty
    assert _session_has_writes(db_session) is True
