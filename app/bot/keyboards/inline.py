"""
app/bot/keyboards/inline.py — Inline klaviatura builder'lar.
"""
from __future__ import annotations

from typing import Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.models.group import Group
from app.models.test import Test


def main_menu_inline_kb(web_app_url: Optional[str] = None) -> InlineKeyboardMarkup:
    """Asosiy inline menyu."""
    rows = [
        [
            InlineKeyboardButton(text="📁 Guruhlarim", callback_data="menu_groups"),
            InlineKeyboardButton(text="➕ Guruh yaratish", callback_data="menu_create_group"),
        ],
        [
            InlineKeyboardButton(text="📝 Testlar", callback_data="menu_tests"),
            InlineKeyboardButton(text="📊 Natijalar", callback_data="menu_results"),
        ],
        [InlineKeyboardButton(text="ℹ️ Yordam", callback_data="menu_help")],
    ]
    # Dashboard tugmasi — Telegram Mini App (web_app) sifatida ochiladi.
    # URL majburiy HTTPS bo'lishi kerak (lokal uchun ngrok tunnel).
    if web_app_url:
        dashboard_url = f"{web_app_url.rstrip('/')}/dashboard"
        rows.insert(2, [
            InlineKeyboardButton(
                text="📊 Dashboard (Web Panel)",
                web_app=WebAppInfo(url=dashboard_url),
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cancel_inline_kb() -> InlineKeyboardMarkup:
    """FSM bekor qilish uchun inline tugma."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_fsm")]
    ])


def back_to_main_kb() -> InlineKeyboardMarkup:
    """Asosiy menyuga qaytish tugmasi."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Bosh menyu", callback_data="back_to_main")]
    ])


def groups_kb(groups: list[Group], prefix: str = "group:") -> InlineKeyboardMarkup:
    """Guruhlar ro'yxati (prefix orqali guruh boshqaruvi yoki natijalar uchun ishlatiladi)."""
    builder = InlineKeyboardBuilder()
    for g in groups:
        builder.button(text=g.name, callback_data=f"{prefix}{g.id}")
    builder.button(text="⬅️ Bosh menyu", callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()


def group_menu_kb(group_id: int) -> InlineKeyboardMarkup:
    """Guruh tanlangandan keyin menyu."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 O'quvchilar", callback_data=f"students:{group_id}"),
            InlineKeyboardButton(text="➕ O'quvchi qo'shish", callback_data=f"add_students:{group_id}"),
        ],
        [
            InlineKeyboardButton(text="📝 Test berish", callback_data=f"create_test:{group_id}"),
            InlineKeyboardButton(text="📋 Testlar", callback_data=f"list_tests:{group_id}"),
        ],
        [
            InlineKeyboardButton(text="🗑 Guruhni o'chirish", callback_data=f"del_group:{group_id}"),
            InlineKeyboardButton(text="⬅️ Orqaga", callback_data="menu_groups"),
        ],
    ])


def qcount_kb() -> InlineKeyboardMarkup:
    """Savol soni tanlash."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="40 ta", callback_data="qcount:40"),
            InlineKeyboardButton(text="50 ta", callback_data="qcount:50"),
            InlineKeyboardButton(text="90 ta", callback_data="qcount:90"),
        ],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_fsm")]
    ])


def vcount_kb() -> InlineKeyboardMarkup:
    """Variant soni tanlash."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="4 (A-D)", callback_data="vcount:4"),
            InlineKeyboardButton(text="5 (A-E)", callback_data="vcount:5"),
        ],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_fsm")]
    ])


def confirm_test_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ha", callback_data="confirm_test:yes"),
            InlineKeyboardButton(text="❌ Yo'q", callback_data="confirm_test:no"),
        ],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_fsm")]
    ])


def generate_tituls_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📄 Ha, hammasi", callback_data="gen_tituls:all"),
        InlineKeyboardButton(text="⏰ Keyinroq", callback_data="gen_tituls:later"),
    ]])


def titul_format_kb(test_id: int) -> InlineKeyboardMarkup:
    """Titul yuborish formati."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📑 Alohida", callback_data=f"tituls_send:single:{test_id}"),
            InlineKeyboardButton(text="🗜 ZIP", callback_data=f"tituls_send:zip:{test_id}"),
        ],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"test:{test_id}")],
    ])


def tests_kb(tests: list[Test], group_id: int, prefix: str = "test:") -> InlineKeyboardMarkup:
    """Testlar ro'yxati."""
    builder = InlineKeyboardBuilder()
    for t in tests:
        builder.button(
            text=f"{t.title} ({t.question_count}ta)",
            callback_data=f"{prefix}{t.id}",
        )
    builder.button(text="⬅️ Orqaga", callback_data=f"group:{group_id}")
    builder.adjust(1)
    return builder.as_markup()


def test_menu_kb(test_id: int) -> InlineKeyboardMarkup:
    """Test boshqarish menyusi."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📄 Titullar", callback_data=f"tituls:{test_id}"),
            InlineKeyboardButton(text="📊 Natijalar", callback_data=f"results:{test_id}"),
        ],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="menu_tests")],
    ])


# ─── Natijalar (Results) bo'limi uchun klaviaturalar ─────────────────────────

def res_group_menu_kb(group_id: int) -> InlineKeyboardMarkup:
    """Guruh natijalari menyusi."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📝 Olimpiadalar (Testlar)", callback_data=f"res_group_tests:{group_id}"),
        ],
        [
            InlineKeyboardButton(text="📥 Excel Eksport", callback_data=f"res_group_excel:{group_id}"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Orqaga", callback_data="menu_results"),
        ]
    ])


def res_tests_kb(tests: list[Test], group_id: int) -> InlineKeyboardMarkup:
    """Natijalar uchun guruhdagi testlar ro'yxati."""
    builder = InlineKeyboardBuilder()
    for t in tests:
        builder.button(
            text=f"{t.title} ({t.question_count}ta)",
            callback_data=f"res_test:{t.id}",
        )
    builder.button(text="⬅️ Orqaga", callback_data=f"res_group:{group_id}")
    builder.adjust(1)
    return builder.as_markup()


def res_test_menu_kb(test_id: int, group_id: int) -> InlineKeyboardMarkup:
    """Test natijalari menyusi."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 O'quvchilar ro'yxati", callback_data=f"res_test_students:{test_id}"),
        ],
        [
            InlineKeyboardButton(text="📥 Excel Eksport", callback_data=f"res_test_excel:{test_id}"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"res_group_tests:{group_id}"),
        ]
    ])


def res_student_kb(attempts: list[tuple[str, int, int, int, int]], test_id: int) -> InlineKeyboardMarkup:
    """Olimpiada natijalaridagi o'quvchilar ro'yxati.
    attempts: [(full_name, student_id, score, total, attempt_id_or_none)]
    """
    builder = InlineKeyboardBuilder()
    for name, student_id, score, total, att_id in attempts:
        status_text = f" ({score}/{total})" if att_id else " (Topshirmagan)"
        builder.button(
            text=f"{name}{status_text}",
            callback_data=f"res_student_tests:{student_id}:{test_id}",
        )
    builder.button(text="⬅️ Orqaga", callback_data=f"res_test:{test_id}")
    builder.adjust(1)
    return builder.as_markup()


def res_student_attempts_kb(attempts: list[tuple[str, int, int, int]], student_id: int, from_test_id: int) -> InlineKeyboardMarkup:
    """O'quvchi ishtirok etgan testlar/attempts ro'yxati.
    attempts: [(test_title, score, total, attempt_id)]
    """
    builder = InlineKeyboardBuilder()
    for test_title, score, total, att_id in attempts:
        builder.button(
            text=f"{test_title} ({score}/{total})",
            callback_data=f"res_attempt_detail:{att_id}:{student_id}:{from_test_id}",
        )
    builder.button(text="📥 Excel Eksport", callback_data=f"res_student_excel:{student_id}")
    builder.button(text="⬅️ Orqaga", callback_data=f"res_test_students:{from_test_id}")
    builder.adjust(1)
    return builder.as_markup()


def back_to_student_kb(student_id: int, from_test_id: int) -> InlineKeyboardMarkup:
    """O'quvchi testlari ro'yxatiga qaytish."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"res_student_tests:{student_id}:{from_test_id}")]
    ])

