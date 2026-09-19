"""
app/worker/session.py — Celery uchun sync SQLAlchemy sessiyasi.

Ilgari har task `create_engine(...)` chaqirardi (weaknesses.md №14): har
vazifa uchun yangi ulanish pul'i, yangi TCP ulanish va sekin start. Engine
jarayon darajasida BITTA bo'ladi — Celery bola-jarayonlari fork'dan keyin
o'zining pul'ini tozalab oladi (`worker_process_init`).
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

log = logging.getLogger(__name__)

_engine: Optional[Engine] = None
_session_factory: Optional[sessionmaker] = None


def get_engine() -> Engine:
    """Jarayon darajasidagi yagona engine."""
    global _engine, _session_factory
    if _engine is None:
        from sqlalchemy import create_engine

        from app.core.config import get_settings

        _engine = create_engine(
            get_settings().sync_database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=5,
            pool_recycle=1800,
        )
        _session_factory = sessionmaker(bind=_engine)
        log.info("Worker: SQLAlchemy engine yaratildi")
    return _engine


def get_sync_session() -> Session:
    """Yangi sync sessiya (umumiy engine ustida)."""
    get_engine()
    assert _session_factory is not None
    return _session_factory()


def dispose_engine() -> None:
    """
    Fork'dan keyin ota-jarayondan meros qolgan ulanishlarni tashlab yuboradi.

    Bir xil TCP soketni ikki jarayon ishlatsa psycopg2 buziladi.
    """
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
        _engine = None
        _session_factory = None
