"""
app/bot/keyboards/reply.py — Asosiy menyu klaviaturalari.
"""
from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_menu_kb() -> ReplyKeyboardMarkup:
    """Asosiy menyu (ustoz uchun)."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📁 Mening guruhlarim"),
                KeyboardButton(text="➕ Guruh yaratish"),
            ],
            [
                KeyboardButton(text="📝 Testlar"),
                KeyboardButton(text="📊 Natijalar"),
            ],
            [KeyboardButton(text="ℹ️ Yordam")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Menyu...",
    )


def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
        resize_keyboard=True,
    )


def back_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⬅️ Orqaga")]],
        resize_keyboard=True,
    )
