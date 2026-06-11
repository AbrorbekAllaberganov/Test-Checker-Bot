"""
app/bot/handlers/start.py — /start handler va asosiy menyu (faqat inline).
"""
from __future__ import annotations

import logging

import httpx
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from app.bot.keyboards.inline import main_menu_inline_kb, back_to_main_kb
from app.core.config import get_settings
from app.core.db import get_session_factory
from app.services.groups import get_or_create_user

router = Router(name="start")
log = logging.getLogger(__name__)

HELP_TEXT = (
    "📖 <b>OMR Test Bot bo'yicha yo'riqnoma va imkoniyatlar</b>\n\n"
    "Ushbu bot o'qituvchilarga test sinovlarini tezkor va avtomatlashtirilgan tarzda o'tkazish "
    "hamda natijalarni soniyalar ichida hisoblashda yordam beradi.\n\n"
    "🤖 <b>Botning asosiy imkoniyatlari:</b>\n"
    "1️⃣ <b>Guruh va o'quvchilar:</b> Guruhlar ochish va har bir guruhga o'quvchilarni ism-familiyasi bo'yicha qo'shish. Har bir o'quvchiga maxsus individual ID kodi beriladi.\n"
    "2️⃣ <b>Titul (PDF) generatsiyasi:</b> 40, 50 yoki 90 ta savol uchun mo'ljallangan javoblar varaqalarini "
    "o'quvchining F.I.Sh va ID kodi bilan birga tayyor holda yuklab olish.\n"
    "3️⃣ <b>Kamera orqali tekshirish:</b> O'quvchi to'ldirgan titul varaqasini rasmga olib yoki skanerlab botga yuborsangiz, "
    "bot uni Computer Vision (OpenCV) yordamida tezkor tekshiradi.\n"
    "4️⃣ <b>Excel hisobotlar:</b> Guruhdagi barcha test natijalarini yagona Excel jadvali shaklida yuklab olish.\n\n"
    "💡 <b>Ishlatish ketma-ketligi (Qo'llanma):</b>\n"
    "1️⃣ <b>Guruh oching:</b> Bosh menyudan <i>➕ Guruh yaratish</i> tugmasini bosing va guruh nomini yuboring.\n"
    "2️⃣ <b>O'quvchi qo'shing:</b> <i>📁 Guruhlarim</i> -> Guruhni tanlang -> <i>➕ O'quvchi qo'shish</i> "
    "tugmasini bosing va o'quvchilar ro'yxatini yuboring (har qatorda bittadan).\n"
    "3️⃣ <b>Test yarating:</b> Guruh sahifasida <i>📝 Test berish</i> tugmasini bosing, savollar sonini belgilang va "
    "to'g'ri kalitlarni kiriting (masalan: <code>ABCD...</code>).\n"
    "4️⃣ <b>Titul chop eting:</b> Bot tayyorlab bergan PDF faylni chop etib, o'quvchilarga tarqating.\n"
    "5️⃣ <b>Tekshirishga yuboring:</b> O'quvchilar doiralarni to'ldirgandan so'ng, ularni rasmga olib oddiygina botga yuboring.\n\n"
    "⚙️ <b>Buyruqlar:</b>\n"
    "• /start - Asosiy menyuni ochish\n"
    "• /help - Ushbu yo'riqnomani ko'rish\n\n"
    "❓ Muammolar yuzaga kelsa, /start buyrug'ini yuboring."
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Foydalanuvchini ro'yxatdan o'tkazish va asosiy menyuni ko'rsatish."""
    await state.clear()

    factory = get_session_factory()
    async with factory() as db:
        await get_or_create_user(
            db,
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username,
        )
        await db.commit()

    await message.answer(
        f"👋 Salom, <b>{message.from_user.first_name}</b>!\n\n"
        "OMR Test Bot'ga xush kelibsiz.\n"
        "Quyidagi inline menyu orqali botni boshqaring:",
        reply_markup=main_menu_inline_kb(web_app_url=get_settings().web_app_url or None),
        parse_mode="HTML",
    )


@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext) -> None:
    """Help buyrug'i handler."""
    await state.clear()
    await message.answer(
        HELP_TEXT,
        reply_markup=back_to_main_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "back_to_main")
async def back_to_main_handler(call: CallbackQuery, state: FSMContext) -> None:
    """Bosh menyuga qaytish."""
    await state.clear()
    await call.message.edit_text(
        "Asosiy menyu. Kerakli bo'limni tanlang:",
        reply_markup=main_menu_inline_kb(web_app_url=get_settings().web_app_url or None),
    )
    await call.answer()


@router.callback_query(F.data == "cancel_fsm")
async def cancel_fsm_handler(call: CallbackQuery, state: FSMContext) -> None:
    """Amalni bekor qilish."""
    await state.clear()
    await call.message.edit_text(
        "Amal bekor qilindi. Bosh menyuga qaytdik:",
        reply_markup=main_menu_inline_kb(web_app_url=get_settings().web_app_url or None),
    )
    await call.answer()


@router.callback_query(F.data == "menu_help")
async def help_handler(call: CallbackQuery) -> None:
    """Yordam bo'limi."""
    await call.message.edit_text(
        HELP_TEXT,
        reply_markup=back_to_main_kb(),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data == "dashboard_open")
async def dashboard_open_handler(call: CallbackQuery) -> None:
    """
    Dashboard tugmasi bosilganda:
    1. API orqali vaqtinchalik token generatsiya qilinadi (Redis, TTL=5min)
    2. Foydalanuvchiga /api/auth/login?token=... URL yuboriladi
    """
    settings = get_settings()

    if not settings.web_app_url:
        await call.answer("Dashboard URL sozlanmagan.", show_alert=True)
        return

    await call.answer()

    api_base = _get_api_base(settings.web_app_url)
    token_url = f"{api_base}/api/auth/dashboard-token"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                token_url,
                json={"telegram_id": call.from_user.id},
                headers={"X-Internal-Key": settings.internal_api_key},
            )
            resp.raise_for_status()
            data = resp.json()
            token = data["token"]
    except Exception as e:
        log.error("Dashboard token olishda xatolik: %s", e)
        await call.message.answer(
            "❌ Dashboard havolasini olishda xatolik yuz berdi. Qayta urinib ko'ring.",
            parse_mode="HTML",
        )
        return

    dashboard_url = f"{api_base}/api/auth/login?token={token}"

    await call.message.answer(
        "🔐 <b>Dashboard havolasi</b>\n\n"
        "Quyidagi havola faqat <b>5 daqiqa</b> davomida ishlaydi.\n"
        "Havola bir martalik — faqat siz uchun!\n\n"
        f'👉 <a href="{dashboard_url}">Dashboard\'ni ochish</a>',
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


def _get_api_base(web_app_url: str) -> str:
    """
    web_app_url dan protocol+host ajratib oladi.
    Masalan: "https://domain.com/dashboard" → "https://domain.com"
    """
    from urllib.parse import urlparse
    parsed = urlparse(web_app_url)
    return f"{parsed.scheme}://{parsed.netloc}"
