"""
app/bot/handlers/groups.py — Guruh yaratish va boshqarish oqimi (FSM, faqat inline).

Egalik: callback data (`group:<id>`) mijozdan keladi va soxtalanishi
mumkin — har `group_id` `owned_group()` orqali joriy ustozga tegishli
ekani tekshiriladi. Begona guruh → "topilmadi" (mavjudligi oshkor qilinmaydi).

`db_user` — `AccessMiddleware` bergan bazadagi foydalanuvchi (har xabar/
callback uchun kafolatlangan). Egalik tekshiruvi `db_user.id` bilan.
"""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.inline import (
    cancel_inline_kb,
    group_menu_kb,
    groups_kb,
    main_menu_inline_kb,
)
from app.bot.states import GroupCreate, StudentAdd, TestCreate
from app.core.config import get_settings
from app.core.db import get_session_factory
from app.models.user import User
from app.services.access import owned_group
from app.services.groups import create_group, delete_group, get_groups_by_owner
from app.services.subscriptions import check_group_limit
from app.services.telegram import escape

log = logging.getLogger(__name__)
router = Router(name="groups")


# ─── FSM: matn bo'lmagan xabarlar uchun umumiy fallback ──────────────────────
#
# Holatda turgan ustoz rasm/stiker/voice yuborsa, ilgari `message.text` `None`
# bo'lib handler yiqilardi va state tiqilib qolardi (weaknesses №11). Bu
# handler `groups.router` da turadi — u FSM routerlarining birinchisi, shu
# sababli `scan.router` (oxirida) ushlab olmaydi. `scan.py` ham o'z
# navbatida `StateFilter(None)` bilan faqat holatsiz skanlarni qabul qiladi.

@router.message(StateFilter(GroupCreate, StudentAdd, TestCreate), ~F.text)
async def fsm_non_text(message: Message) -> None:
    await message.answer(
        "Hozir amal bajarilmoqda. Iltimos matn yuboring yoki tugmalardan "
        "birini tanlang.\nBekor qilish uchun ❌ Bekor qilish tugmasini bosing.",
        reply_markup=cancel_inline_kb(),
    )


# ─── Guruhlar ro'yxati (Inline callback) ──────────────────────────────────────

@router.callback_query(F.data == "menu_groups")
async def list_my_groups(call: CallbackQuery, db_user: User) -> None:
    factory = get_session_factory()
    async with factory() as db:
        groups = await get_groups_by_owner(db, db_user.id)

    if not groups:
        await call.message.edit_text(
            "Hozircha guruhlaringiz yo'q.\n➕ Guruh yaratish tugmasini bosing.",
            reply_markup=main_menu_inline_kb(),
        )
        await call.answer()
        return

    await call.message.edit_text(
        f"📁 Sizning guruhlaringiz ({len(groups)} ta):",
        reply_markup=groups_kb(groups, prefix="group:"),
    )
    await call.answer()


@router.callback_query(F.data.startswith("group:"))
async def group_selected(call: CallbackQuery, db_user: User) -> None:
    group_id = int(call.data.split(":")[1])
    factory = get_session_factory()
    async with factory() as db:
        group = await owned_group(db, group_id, db_user.id)

    if group is None:
        await call.answer("Guruh topilmadi", show_alert=True)
        return

    await call.message.edit_text(
        f"📁 Guruh: <b>{escape(group.name)}</b>\n\nNima qilmoqchisiz?",
        reply_markup=group_menu_kb(group_id),
        parse_mode="HTML",
    )
    await call.answer()


# ─── Guruh yaratish (FSM) ─────────────────────────────────────────────────────

@router.callback_query(F.data == "menu_create_group")
async def start_create_group(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(GroupCreate.waiting_name)
    await call.message.edit_text(
        "📝 Yangi guruh nomini yuboring:",
        reply_markup=cancel_inline_kb(),
    )
    await call.answer()


@router.message(GroupCreate.waiting_name, F.text)
async def receive_group_name(message: Message, state: FSMContext, db_user: User) -> None:
    name = message.text.strip()
    if not name:
        await message.answer(
            "Guruh nomi bo'sh bo'lmaydi. Qayta kiriting:",
            reply_markup=cancel_inline_kb()
        )
        return

    factory = get_session_factory()
    async with factory() as db:
        # Tarif limiti (`max_groups`). ENFORCE_QUOTA=false — faqat log,
        # skan kvotasi bilan bir xil siyosat.
        allowed, reason = await check_group_limit(db, db_user.id)
        await db.commit()  # ensure_period()/yangi obuna yozilgan bo'lishi mumkin
        if not allowed:
            if get_settings().enforce_quota:
                await state.clear()
                await message.answer(
                    f"🚫 <b>Limit</b>\n\n{escape(reason)}",
                    reply_markup=main_menu_inline_kb(),
                    parse_mode="HTML",
                )
                return
            log.warning(
                "Guruh limiti oshdi (ENFORCE_QUOTA=false): user=%s — %s", db_user.id, reason
            )

        group = await create_group(db, owner_id=db_user.id, name=name)
        await db.commit()
        group_id = group.id

    await state.clear()

    # Yangi xabarda muvaffaqiyat bildirish
    await message.answer(
        f"✅ <b>{escape(name)}</b> guruhi yaratildi!\n\n"
        "Endi o'quvchi qo'shishingiz yoki test yaratishingiz mumkin.",
        parse_mode="HTML",
    )
    await message.answer(
        "Guruh boshqaruviga o'tish yoki Bosh menyu:",
        reply_markup=group_menu_kb(group_id),
    )


# ─── Guruhni o'chirish ────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("del_group:"))
async def delete_group_handler(call: CallbackQuery, db_user: User) -> None:
    group_id = int(call.data.split(":")[1])

    factory = get_session_factory()
    async with factory() as db:
        deleted = await delete_group(db, group_id, db_user.id)
        await db.commit()

    if deleted:
        await call.message.edit_text(
            "🗑 Guruh muvaffaqiyatli o'chirildi.",
            reply_markup=main_menu_inline_kb()
        )
    else:
        await call.answer("Guruh topilmadi yoki siz egasi emassiz.", show_alert=True)
