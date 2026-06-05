"""
app/core/config.py — Pydantic Settings (environment variables).

Barcha konstantalar shu yerdan o'qiladi. Hech qayerda hardcode yo'q.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Telegram ──────────────────────────────────────────────────────────
    bot_token: str
    bot_username: str = "omr_test_bot"

    # Web Dashboard URL (bot ichidan ochish uchun)
    web_app_url: str = ""  # Masalan: https://yourdomain.com/dashboard

    # ── Database ──────────────────────────────────────────────────────────
    database_url: str  # asyncpg
    sync_database_url: str  # psycopg2 (alembic / celery)

    # ── Redis ─────────────────────────────────────────────────────────────
    redis_url: str = "redis://redis:6379/0"

    # ── Auth ──────────────────────────────────────────────────────────────
    admin_telegram_ids: Any = []
    internal_api_key: str = "change-me"

    @field_validator("admin_telegram_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, v: object) -> list[int]:
        if isinstance(v, str):
            return [int(i.strip()) for i in v.split(",") if i.strip()]
        return list(v) if v else []

    # ── File paths ────────────────────────────────────────────────────────
    pdf_output_dir: Path = Path("/data/pdfs")
    debug_output_dir: Path = Path("/data/debug")
    temp_dir: Path = Path("/tmp/omr_uploads")

    # ── Limits ────────────────────────────────────────────────────────────
    max_image_mb: int = 20

    # ── OMR parameters (env-tunable for calibration) ──────────────────────
    omr_debug: bool = False
    fill_min: float = 0.35     # bo'sh doira uchun minimal to'ldirilganlik
    fill_margin: float = 0.15  # ikkilanish chegarasi
    omr_dpi: int = 200
    warp_w: int = 1449         # warped rasm kengligi (px)
    warp_h: int = 2134         # warped rasm balandligi (px)

    def ensure_dirs(self) -> None:
        """Ishga tushirishda papkalarni yaratish."""
        for d in (self.pdf_output_dir, self.debug_output_dir, self.temp_dir):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton settings instance."""
    s = Settings()  # type: ignore[call-arg]
    s.ensure_dirs()
    return s
