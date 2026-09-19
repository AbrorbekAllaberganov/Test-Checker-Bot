"""
app/tests/conftest.py — Pytest fixtures.

TEST BAZASI IZOLYATSIYASI (weaknesses.md №34):
  Ilgari DB testlari `get_session_factory()` orqali `.env` dagi bazaga
  YOZARDI va oxirida o'zi o'chirardi. Prod `.env` bilan ishga tushirilsa
  haqiqiy ma'lumot buzilardi, test yarmida yiqilsa esa axlat qolardi.

  Endi:
    • `TEST_DATABASE_URL` majburiy — bo'lmasa DB testlari `skip`.
    • URL ichida "test" so'zi bo'lishi SHART — aks holda sessiya to'xtaydi.
      Bu "noto'g'ri URL qo'ydim" xatosidan himoya.
    • Har test bitta TRANZAKSIYADA ishlaydi va oxirida `rollback` bo'ladi —
      bazada hech narsa qolmaydi, testlar bir-biriga ta'sir qilmaydi.

Ishga tushirish:
    docker compose exec -T postgres psql -U omruser -d postgres \
        -c "CREATE DATABASE omrdb_test"
    TEST_DATABASE_URL=postgresql+asyncpg://omruser:PASS@postgres:5432/omrdb_test \
        docker compose run --rm --no-deps -e TEST_DATABASE_URL api pytest app/tests -q
"""
from __future__ import annotations

import os

import pytest

TEST_DB_ENV = "TEST_DATABASE_URL"
_SKIP_REASON = (
    f"{TEST_DB_ENV} berilmagan — bazaga tegadigan testlar o'tkazib yuborildi. "
    "Namuna: postgresql+asyncpg://omruser:PASS@postgres:5432/omrdb_test"
)


def _test_database_url() -> str | None:
    """Test bazasi URL'i (yo'q bo'lsa None)."""
    url = os.getenv(TEST_DB_ENV, "").strip()
    return url or None


def _sync_url(async_url: str) -> str:
    """asyncpg URL → psycopg2 URL (alembic uchun)."""
    return async_url.replace("+asyncpg", "").replace(
        "postgresql://", "postgresql+psycopg2://", 1
    )


def pytest_configure(config: pytest.Config) -> None:
    """URL xavfsizligini sessiya boshida tekshiradi."""
    url = _test_database_url()
    if url and "test" not in url.lower():
        pytest.exit(
            f"{TEST_DB_ENV} ichida 'test' so'zi bo'lishi SHART — prod bazasiga "
            "yozib yuborishning oldini olish uchun. Joriy qiymat rad etildi.",
            returncode=2,
        )


# ─── Sessiya darajasidagi tayyorgarlik ──────────────────────────────────────


@pytest.fixture(scope="session")
def test_db_url() -> str:
    """Test bazasi URL'i; yo'q bo'lsa testni skip qiladi."""
    url = _test_database_url()
    if url is None:
        pytest.skip(_SKIP_REASON, allow_module_level=True)
    return url


@pytest.fixture(scope="session", autouse=True)
def _configure_test_env() -> None:
    """
    `DATABASE_URL` ni test bazasiga yo'naltiradi (import'lardan keyin ham
    ishlaydi, chunki `app.core.db` engine'ni LAZY yaratadi).
    """
    url = _test_database_url()
    if url is None:
        return

    os.environ["DATABASE_URL"] = url
    os.environ["SYNC_DATABASE_URL"] = _sync_url(url)

    from app.core.config import get_settings

    get_settings.cache_clear()

    from app.core import db as core_db

    core_db._engine = None
    core_db._session_factory = None


@pytest.fixture(scope="session", autouse=True)
def _migrate(_configure_test_env) -> None:
    """Test bazasiga migratsiyalarni bir marta qo'llaydi."""
    if _test_database_url() is None:
        return

    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["SYNC_DATABASE_URL"])
    command.upgrade(cfg, "head")


# ─── Test darajasidagi sessiya (tranzaksiya + rollback) ─────────────────────


@pytest.fixture
async def db_session(test_db_url):
    """
    Bitta test uchun DB sessiyasi — oxirida HAMMASI qaytariladi.

    `join_transaction_mode="create_savepoint"`: test ichidagi `commit()`
    chaqiruvlari tashqi tranzaksiyani yopmaydi, faqat savepoint'ni
    tasdiqlaydi. Shu sababli endpointlardagi `await db.commit()` ishlaydi,
    lekin ma'lumot bazada qolmaydi.
    """
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.db import get_engine

    engine = get_engine()
    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(
            bind=conn,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()


@pytest.fixture
async def api_client(db_session):
    """
    `httpx.AsyncClient` — `get_db` test sessiyasiga ulangan.

    Endpointlar test yaratgan ma'lumotni ko'radi (bitta tranzaksiya) va
    ular yozgani ham test oxirida qaytariladi.
    """
    from httpx import ASGITransport, AsyncClient

    from app.api.main import app
    from app.core.db import get_db

    async def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture(autouse=True)
async def _dispose_engine():
    """Test oxirida engine ulanishlarini yopadi (event loop almashinuvi uchun)."""
    yield
    from app.core import db

    if db._engine is not None:
        await db._engine.dispose()
        db._session_factory = None
        db._engine = None


# ─── DB'siz (toza) fixture'lar ──────────────────────────────────────────────


@pytest.fixture
def sample_key_40() -> dict:
    """40 ta to'g'ri javob (test ma'lumoti)."""
    opts = "ABCD"
    return {str(i): opts[(i - 1) % 4] for i in range(1, 41)}


@pytest.fixture
def sample_detected_40(sample_key_40) -> dict:
    """Simulyatsiyalangan aniqlangan javoblar (5 ta noto'g'ri)."""
    detected = dict(sample_key_40)
    wrong_qs = [3, 7, 15, 22, 38]
    for q in wrong_qs:
        correct = sample_key_40[str(q)]
        # Boshqa harfni tanlash
        for opt in "ABCD":
            if opt != correct:
                detected[str(q)] = opt
                break
    return detected
