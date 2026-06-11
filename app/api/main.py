"""
app/api/main.py — FastAPI application.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.api.routes import groups, tests, tituls, attempts, results, web_api


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ishga tushirishda va to'xtatishda bajariladigan amallar."""
    settings = get_settings()
    setup_logging()
    settings.ensure_dirs()
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="OMR Test Bot API",
        description="O'qituvchilar uchun OMR test bot REST API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Static file mounting
    app.mount("/static/pdfs", StaticFiles(directory=str(settings.pdf_output_dir)), name="pdfs")
    app.mount("/static/debug", StaticFiles(directory=str(settings.debug_output_dir)), name="debug")
    app.mount("/static/uploads", StaticFiles(directory=str(settings.temp_dir)), name="uploads")

    # Routerlarni ulash
    from app.api.routes import auth as auth_router
    app.include_router(auth_router.router)
    app.include_router(groups.router)
    app.include_router(tests.router)
    app.include_router(tituls.router)
    app.include_router(attempts.router)
    app.include_router(results.router)
    app.include_router(web_api.router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

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

    return app


app = create_app()
