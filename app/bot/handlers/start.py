"""
app/bot/handlers/start.py — /start handler va asosiy menyu (faqat inline).
"""
from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from app.bot.keyboards.inline import main_menu_inline_kb, back_to_main_kb
from app.core.config import get_settings
from app.core.db import get_session_factory
from app.services.groups import get_or_create_user

router = Router(name="start")

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

