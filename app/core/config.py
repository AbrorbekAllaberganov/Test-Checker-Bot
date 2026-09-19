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

    # Web Dashboard URL (foydalanuvchi brauzeriga ko'rsatiladigan tashqi URL)
    web_app_url: str = ""  # Masalan: http://localhost:8000 yoki https://yourdomain.com

    # Ichki API URL — bot Docker ichidan API ga so'rov yuborish uchun
    # Docker compose'da bu odatda http://api:8000
    internal_api_url: str = ""  # Bo'sh bo'lsa web_app_url ishlatiladi

    # ── Database ──────────────────────────────────────────────────────────
    database_url: str  # asyncpg
    sync_database_url: str  # psycopg2 (alembic / celery)

    # ── Redis ─────────────────────────────────────────────────────────────
    redis_url: str = "redis://redis:6379/0"

    # ── Auth ──────────────────────────────────────────────────────────────
    admin_telegram_ids: Any = []
    internal_api_key: str = "change-me"
    # JWT dashboard session
    secret_key: str = "change-me-use-a-random-32-char-secret"
    jwt_expire_days: int = 7

    @field_validator("admin_telegram_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, v: object) -> list[int]:
        if isinstance(v, str):
            return [int(i.strip()) for i in v.split(",") if i.strip()]
        return list(v) if v else []

    # ── Admin panel (React) ───────────────────────────────────────────────
    # Access token qisqa, refresh uzoq — brauzer sessiyasi uchun.
    admin_access_token_minutes: int = 30
    admin_refresh_token_days: int = 14
    # Bot yuboradigan bir martalik kod (OTP) amal qilish muddati.
    admin_otp_ttl_seconds: int = 300
    # Bitta telegram_id uchun OTP so'rashlar orasidagi minimal interval.
    admin_otp_resend_seconds: int = 60
    # React dev-server origin'lari (vergul bilan). Bo'sh bo'lsa faqat
    # same-origin ishlaydi — prod'da panel API bilan bir domenda turadi.
    admin_cors_origins: Any = []

    @field_validator("admin_cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: object) -> list[str]:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return list(v) if v else []

    # ── SaaS kvota ────────────────────────────────────────────────────────
    # false bo'lsa limitlar hisoblanadi, lekin skan bloklanmaydi (soft-launch).
    enforce_quota: bool = False
    # Yangi ro'yxatdan o'tgan ustozga beriladigan tarif.
    default_plan_code: str = "FREE"
    # Yangi obuna necha kun 'trial' bo'ladi (0 = darrov 'active').
    trial_days: int = 0

    # ── Vaqt zonasi ───────────────────────────────────────────────────────
    # Ilova ichida hamma narsa UTC; bu faqat "bugun" kabi KUN chegaralari va
    # foydalanuvchiga ko'rsatiladigan vaqt uchun (weaknesses.md №28).
    app_timezone: str = "Asia/Tashkent"

    # ── API hujjatlari ────────────────────────────────────────────────────
    # Prod'da yopiq: /docs butun ichki API sxemasini ochib beradi.
    enable_api_docs: bool = False

    # ── Proxy ─────────────────────────────────────────────────────────────
    # Uvicorn `--forwarded-allow-ips` bilan bir xil bo'lishi kerak. Faqat shu
    # IP'lardan kelgan X-Forwarded-For ga ishonamiz (audit/rate limit uchun).
    trusted_proxy_ips: str = "127.0.0.1"

    # ── initData (Telegram Mini App) ──────────────────────────────────────
    # 0 = cheksiz (tutib olingan initData abadiy ishlaydi) — ishlatmang.
    init_data_max_age_seconds: int = 86400        # Mini App sessiyasi
    admin_init_data_max_age_seconds: int = 300    # admin: uzoq refresh beradi

    # ── File paths ────────────────────────────────────────────────────────
    pdf_output_dir: Path = Path("/data/pdfs")
    debug_output_dir: Path = Path("/data/debug")
    temp_dir: Path = Path("/tmp/omr_uploads")
    # Baholangan skanlar ko'chiriladigan doimiy papka (review uchun kerak):
    # `temp_dir` efemer, review esa oylab ochilishi mumkin.
    uploads_dir: Path = Path("/data/uploads")
    # `temp_dir` dagi yetim fayllar shu muddatdan keyin o'chiriladi.
    temp_file_max_age_hours: int = 24

    # ── Limits ────────────────────────────────────────────────────────────
    max_image_mb: int = 20
    # PDF skandan nechta sahifa tekshiriladi (titul bir varaqli).
    omr_max_pages: int = 1
    # "Alohida" rejimida bir yo'la yuboriladigan titullar chegarasi —
    # Telegram flood limitlari (weaknesses.md №22).
    titul_single_send_max: int = 20
    # Telegram hujjat chegarasi 50 MB; zaxira bilan bo'laklaymiz.
    telegram_zip_max_mb: int = 45

    # ── OMR parameters (env-tunable for calibration) ──────────────────────
    omr_debug: bool = False
    fill_min: float = 0.35     # bo'sh doira uchun minimal to'ldirilganlik
    fill_margin: float = 0.15  # ikkilanish chegarasi
    omr_dpi: int = 200
    warp_w: int = 1449         # warped rasm kengligi (px)
    warp_h: int = 2134         # warped rasm balandligi (px)

    def ensure_dirs(self) -> None:
        """Ishga tushirishda papkalarni yaratish."""
        for d in (
            self.pdf_output_dir,
            self.debug_output_dir,
            self.temp_dir,
            self.uploads_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton settings instance."""
    s = Settings()  # type: ignore[call-arg]
    s.ensure_dirs()
    return s
