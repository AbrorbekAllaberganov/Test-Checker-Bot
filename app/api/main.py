"""
app/api/main.py — FastAPI application.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.security import (
    InsecureSecretError,
    assert_internal_key_is_safe,
    assert_secret_is_safe,
)
from app.api.routes import groups, tests, tituls, attempts, results, web_api

log = logging.getLogger(__name__)


def _warn_about_insecure_secrets() -> None:
    """
    Namunaviy kalitlar haqida ishga tushishda ogohlantiradi.

    Ataylab YIQITMAYDI: `SECRET_KEY` faqat admin panelga, `INTERNAL_API_KEY`
    faqat `/attempts/*` ga ta'sir qiladi — ularsiz ham bot va Mini App
    ishlashi kerak. Himoya baribir kuchda: tegishli endpointlar 503
    qaytaradi (core/security.py).
    """
    for check in (assert_secret_is_safe, assert_internal_key_is_safe):
        try:
            check()
        except InsecureSecretError as exc:
            log.error("XAVFSIZLIK OGOHLANTIRISHI: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ishga tushirishda va to'xtatishda bajariladigan amallar."""
    settings = get_settings()
    setup_logging()
    settings.ensure_dirs()
    _warn_about_insecure_secrets()
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    # `/docs`, `/redoc` va `/openapi.json` prod'da YOPIQ (weaknesses.md №21):
    # ular butun ichki API sxemasini — admin endpointlari, maydon nomlari,
    # validatsiya qoidalarini — anonim ko'rsatib turardi. Dev'da
    # `.env` da `ENABLE_API_DOCS=true` qiling.
    docs_enabled = settings.enable_api_docs
    app = FastAPI(
        title="OMR Test Bot API",
        description="O'qituvchilar uchun OMR test bot REST API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    # CORS: Mini App uchun ochiq, lekin admin paneli JWT ishlatgani sababli
    # `allow_credentials` bilan "*" birga ishlamaydi (brauzer rad etadi).
    # Shu sababli aniq origin'lar berilgan bo'lsa — faqat ularga ruxsat.
    admin_origins = settings.admin_cors_origins or []
    if admin_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=admin_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # `/static/pdfs|debug|uploads` mount'lari ATAYLAB YO'Q (weaknesses.md №4):
    # ular autentifikatsiyasiz edi va fayl nomlari ketma-ket ID'li bo'lgani
    # uchun barcha o'quvchilar titullarini (F.I.Sh + QR) enumeratsiya qilib
    # olish mumkin edi. Skan suratlari endi egalik tekshiruvli endpointlar
    # orqali beriladi: /api/web/attempts/{id}/file/{kind} (Mini App) va
    # /api/admin/scans/{id}/file/{kind} (admin). PDF'lar faqat bot orqali.

    # Routerlarni ulash
    from app.api.admin import admin_router
    from app.api.routes import auth as auth_router

    app.include_router(auth_router.router)
    app.include_router(admin_router)
    app.include_router(groups.router)
    app.include_router(tests.router)
    app.include_router(tituls.router)
    app.include_router(attempts.router)
    app.include_router(results.router)
    app.include_router(web_api.router)

    @app.get("/health")
    async def health(deep: bool = True):
        """
        Servis holati.

        `deep=true` (standart) — DB va Redis ham tekshiriladi va nosoz
        bo'lsa 503 qaytariladi (weaknesses.md №37): ilgari `/health` har
        doim "ok" derdi, ya'ni baza yotgan konteyner ham "healthy"
        ko'rinardi va orchestrator uni qayta ishga tushirmasdi.
        `deep=false` — faqat jarayon tirikligi (liveness).
        """
        if not deep:
            return {"status": "ok"}

        checks: dict[str, str] = {}

        try:
            from sqlalchemy import text

            from app.core.db import get_session_factory

            async with get_session_factory()() as db:
                await db.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception as exc:
            log.error("Health: baza javob bermadi: %s", exc)
            checks["database"] = "error"

        try:
            import redis.asyncio as aioredis

            client = aioredis.from_url(get_settings().redis_url)
            try:
                await client.ping()
            finally:
                await client.aclose()
            checks["redis"] = "ok"
        except Exception as exc:
            log.error("Health: Redis javob bermadi: %s", exc)
            checks["redis"] = "error"

        healthy = all(v == "ok" for v in checks.values())
        return JSONResponse(
            status_code=200 if healthy else 503,
            content={"status": "ok" if healthy else "degraded", "checks": checks},
        )

    @app.get("/login", response_class=HTMLResponse)
    async def login_page(error: str | None = None):
        """Dashboard login sahifasi — foydalanuvchi bot orqali kirishi kerakligini tushuntiradi."""
        template_path = Path(__file__).parent.parent / "templates" / "login.html"
        if not template_path.exists():
            bot_url = f"https://t.me/{settings.bot_username}"
            return HTMLResponse(
                f'<h1>Bot orqali kiring</h1><a href="{bot_url}">@{settings.bot_username}</a>',
                status_code=200,
            )
        html = template_path.read_text(encoding="utf-8")
        # Error xabarini o'rnatish
        error_msg = ""
        if error == "expired":
            error_msg = "Havola muddati o'tgan. Botdan yangi havola oling."
        elif error == "not_registered":
            error_msg = "Siz tizimda ro'yxatdan o'tmagansiz. Avval /start buyrug'ini yuboring."
        html = html.replace("{{BOT_USERNAME}}", settings.bot_username)
        html = html.replace("{{ERROR_MSG}}", error_msg)
        return HTMLResponse(html)

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard():
        """
        Dashboard Mini App sahifasi.

        Autentifikatsiya endi sahifa darajasida emas, balki API darajasida
        (Telegram initData imzosi orqali) amalga oshiriladi. Shu sababli
        HTML to'g'ridan-to'g'ri beriladi — har bir /api/web/* so'rovi
        Authorization header'idagi initData bilan tekshiriladi.
        """
        template_path = Path(__file__).parent.parent / "templates" / "dashboard.html"
        if not template_path.exists():
            return HTMLResponse("<h1>Dashboard HTML shabloni topilmadi</h1>", status_code=404)
        return HTMLResponse(template_path.read_text(encoding="utf-8"))

    _mount_admin_spa(app)

    return app


def _mount_admin_spa(app: FastAPI) -> None:
    """
    React admin panelini `/admin` manzilida xizmat qiladi.

    `admin-ui/dist` mavjud bo'lsa (ya'ni `npm run build` bajarilgan yoki
    Docker image ichida yig'ilgan) — statik fayllar shu yerdan beriladi.
    Build yo'q bo'lsa hech narsa ulanmaydi va API o'z ishini davom ettiradi
    (dev rejimida panel Vite server'ida `http://localhost:5173` da ishlaydi).

    SPA fallback: `/admin/teachers` kabi yo'llar diskda fayl sifatida
    mavjud emas — ular React Router tomonidan brauzerda hal qilinadi.
    Shu sababli mavjud bo'lmagan yo'llarga `index.html` qaytariladi
    (`StaticFiles(html=True)` buni faqat papka yo'llari uchun qiladi,
    shuning uchun catch-all route qo'shamiz).
    """
    dist = Path(__file__).resolve().parents[2] / "admin-ui" / "dist"
    index_file = dist / "index.html"
    if not index_file.exists():
        return

    # Hashlangan asset'lar (index-abc123.js) — uzoq muddatli kesh bilan.
    app.mount(
        "/admin/assets",
        StaticFiles(directory=str(dist / "assets")),
        name="admin-assets",
    )

    @app.get("/admin", include_in_schema=False)
    @app.get("/admin/{spa_path:path}", include_in_schema=False)
    async def admin_spa(spa_path: str = ""):
        """SPA kirish nuqtasi — barcha client-side yo'llar uchun."""
        # Ildizdagi haqiqiy fayllar (favicon.ico, robots.txt, ...) bo'lsa —
        # o'shani beramiz. Yo'l `dist` dan chiqib ketmasligi tekshiriladi.
        if spa_path:
            candidate = (dist / spa_path).resolve()
            if candidate.is_file() and candidate.is_relative_to(dist.resolve()):
                return FileResponse(candidate)

        return FileResponse(index_file)


app = create_app()
