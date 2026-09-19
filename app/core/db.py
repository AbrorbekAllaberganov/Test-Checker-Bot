"""
app/core/db.py — Async SQLAlchemy engine va session factory.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Session as SyncSession

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Barcha SQLAlchemy modellari uchun asosiy sinf."""
    pass


def _make_engine():
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        echo=False,
    )


# Module-level engine (lazy — birinchi import paytida yaratiladi)
_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = _make_engine()
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            expire_on_commit=False,
            class_=AsyncSession,
        )
    return _session_factory


_WROTE_FLAG = "omr_has_writes"


@event.listens_for(SyncSession, "after_flush")
def _mark_session_wrote(session: SyncSession, flush_context) -> None:
    """
    Sessiya bazaga yozganini belgilaydi.

    MUHIM: `flush()` dan keyin `session.dirty` BO'SHAYDI (o'zgarish endi
    tranzaksiyada, obyektda emas). Shu sababli `get_db` ni faqat
    `new/dirty/deleted` ga qarab commit qildirish yozuvlarni indamay
    yo'qotardi — masalan `get_active_subscription()` obunani `expired`
    qilib `flush()` qiladi va commit chaqirmaydi.
    """
    session.info[_WROTE_FLAG] = True


def _session_has_writes(session: AsyncSession) -> bool:
    """Sessiyada commit qilinishi kerak bo'lgan o'zgarish bormi?"""
    if session.new or session.dirty or session.deleted:
        return True
    return bool(session.sync_session.info.get(_WROTE_FLAG))


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency: yields async DB session.

    Commit faqat o'zgarish bo'lganda: har GET so'rovida ham `COMMIT` yuborish
    ortiqcha round-trip edi (weaknesses.md №29). "O'zgarish" — yuvilmagan
    obyektlar YOKI allaqachon `flush()` qilingan yozuv (yuqoridagi izohga
    qarang).
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            if _session_has_writes(session):
                await session.commit()
        except Exception:
            await session.rollback()
            raise
