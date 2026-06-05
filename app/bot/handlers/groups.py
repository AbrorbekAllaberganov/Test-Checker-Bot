"""
app/bot/handlers/groups.py — Guruh yaratish va boshqarish oqimi (FSM, faqat inline).
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.inline import (
    group_menu_kb,
    groups_kb,
    cancel_inline_kb,
    main_menu_inline_kb,
)
from app.bot.states import GroupCreate
from app.core.db import get_session_factory
from app.services.groups import (
    create_group,
    delete_group,
    get_group,
    get_groups_by_owner,
    get_or_create_user,
)

router = Router(name="groups")


async def _get_user_id(telegram_id: int) -> int | None:
    """Telegram ID dan DB user id olish."""
    factory = get_session_factory()
    async with factory() as db:
        user = await get_or_create_user(db, telegram_id)
        await db.commit()
        return user.id


# ─── Guruhlar ro'yxati (Inline callback) ──────────────────────────────────────

@router.callback_query(F.data == "menu_groups")
async def list_my_groups(call: CallbackQuery) -> None:
    user_id = await _get_user_id(call.from_user.id)
    factory = get_session_factory()
    async with factory() as db:
        groups = await get_groups_by_owner(db, user_id)

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
async def group_selected(call: CallbackQuery) -> None:
    group_id = int(call.data.split(":")[1])
    factory = get_session_factory()
    async with factory() as db:
        group = await get_group(db, group_id)

    if group is None:
        await call.answer("Guruh topilmadi", show_alert=True)
        return

    await call.message.edit_text(
        f"📁 Guruh: <b>{group.name}</b>\n\nNima qilmoqchisiz?",
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


@router.message(GroupCreate.waiting_name)
async def receive_group_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not name:
        await message.answer(
            "Guruh nomi bo'sh bo'lmaydi. Qayta kiriting:",
            reply_markup=cancel_inline_kb()
        )
        return

    user_id = await _get_user_id(message.from_user.id)
    factory = get_session_factory()
    async with factory() as db:
        group = await create_group(db, owner_id=user_id, name=name)
        await db.commit()
        group_id = group.id

    await state.clear()
    
    # Yangi xabarda muvaffaqiyat bildirish
    await message.answer(
        f"✅ <b>{name}</b> guruhi yaratildi!\n\nEndi o'quvchi qo'shishingiz yoki test yaratishingiz mumkin.",
        parse_mode="HTML",
    )
    await message.answer(
        "Guruh boshqaruviga o'tish yoki Bosh menyu:",
        reply_markup=group_menu_kb(group_id),
    )


# ─── Guruhni o'chirish ────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("del_group:"))
async def delete_group_handler(call: CallbackQuery) -> None:
    group_id = int(call.data.split(":")[1])
    user_id = await _get_user_id(call.from_user.id)

    factory = get_session_factory()
    async with factory() as db:
        deleted = await delete_group(db, group_id, user_id)
        await db.commit()

    if deleted:
        await call.message.edit_text(
            "🗑 Guruh muvaffaqiyatli o'chirildi.",
            reply_markup=main_menu_inline_kb()
        )
    else:
        await call.answer("Guruh topilmadi yoki siz egasi emassiz.", show_alert=True)
