"""
app/bot/handlers/students.py — O'quvchi qo'shish va ko'rish oqimi (faqat inline).

Egalik: `students:<id>` va `add_students:<id>` callback'lari va FSM'dagi
`group_id` har safar `owned_group()` bilan tekshiriladi — boshqa ustozning
guruhiga o'quvchi qo'shish yoki ro'yxatini ko'rish mumkin emas.

`db_user` — `AccessMiddleware` bergan bazadagi foydalanuvchi.
"""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.bot.keyboards.inline import cancel_inline_kb, group_menu_kb, main_menu_inline_kb
from app.bot.states import StudentAdd
from app.core.config import get_settings
from app.core.db import get_session_factory
from app.models.user import User
from app.services.access import owned_group
from app.services.students import add_students, get_students_by_group
from app.services.subscriptions import check_student_limit
from app.services.telegram import escape

log = logging.getLogger(__name__)
router = Router(name="students")


@router.callback_query(F.data.startswith("students:"))
async def list_students_handler(call: CallbackQuery, db_user: User) -> None:
    group_id = int(call.data.split(":")[1])
    factory = get_session_factory()
    async with factory() as db:
        group = await owned_group(db, group_id, db_user.id)
        if group is None:
            await call.answer("Guruh topilmadi.", show_alert=True)
            return
        students = await get_students_by_group(db, group_id, owner_id=db_user.id)

    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"group:{group_id}")]
    ])

    if not students:
        await call.message.edit_text(
            "Bu guruhda hozircha o'quvchi yo'q.",
            reply_markup=back_kb
        )
        await call.answer()
        return

    # Bot default parse_mode=HTML — F.I.Sh escape qilinmasa `<` xabarni buzadi.
    text = f"👥 O'quvchilar ({len(students)} ta):\n\n"
    for i, s in enumerate(students, 1):
        text += f"{i}. {escape(s.full_name)}\n"

    await call.message.edit_text(text, reply_markup=back_kb)
    await call.answer()


@router.callback_query(F.data.startswith("add_students:"))
async def start_add_students(call: CallbackQuery, state: FSMContext, db_user: User) -> None:
    group_id = int(call.data.split(":")[1])
    factory = get_session_factory()
    async with factory() as db:
        group = await owned_group(db, group_id, db_user.id)
    if group is None:
        await call.answer("Guruh topilmadi.", show_alert=True)
        return

    await state.set_state(StudentAdd.waiting_names)
    await state.update_data(group_id=group_id)

    # Edit the text of the current message to show the prompt and cancellation inline button
    await call.message.edit_text(
        "📝 Har qatorga bitta o'quvchi F.I.Sh ni yuboring:\n\n"
        "<i>Masalan:\n"
        "Ali Valiyev\n"
        "Vali Aliyev\n"
        "Sara Karimova</i>",
        reply_markup=cancel_inline_kb(),
        parse_mode="HTML",
    )
    await call.answer()


@router.message(StudentAdd.waiting_names, F.text)
async def receive_student_names(message: Message, state: FSMContext, db_user: User) -> None:
    data = await state.get_data()
    group_id: int = data["group_id"]

    names = [n.strip() for n in message.text.splitlines() if n.strip()]
    if not names:
        await message.answer(
            "Hech qanday ism topilmadi. Qayta yuboring:",
            reply_markup=cancel_inline_kb()
        )
        return

    factory = get_session_factory()
    async with factory() as db:
        # FSM'dagi group_id ham qayta tekshiriladi — state Redis'da turadi va
        # uni o'rnatgan callback tekshiruvdan o'tgan bo'lsa ham, guruh shu
        # orada o'chirilgan yoki egasi o'zgargan bo'lishi mumkin.
        group = await owned_group(db, group_id, db_user.id)
        if group is None:
            await state.clear()
            await message.answer(
                "Guruh topilmadi. Bosh menyudan qaytadan boshlang.",
                reply_markup=main_menu_inline_kb(),
            )
            return

        # Tarif limiti (`max_students_per_group`). ENFORCE_QUOTA=false — faqat log.
        allowed, reason = await check_student_limit(
            db, db_user.id, group_id, adding=len(names)
        )
        await db.commit()  # ensure_period()/yangi obuna yozilgan bo'lishi mumkin
        if not allowed:
            if get_settings().enforce_quota:
                await message.answer(
                    f"🚫 <b>Limit</b>\n\n{escape(reason)}\n\n"
                    "Kamroq o'quvchi yuboring yoki tarifni yangilang.",
                    reply_markup=cancel_inline_kb(),
                    parse_mode="HTML",
                )
                return  # state saqlanadi — qisqaroq ro'yxat yuborishi mumkin
            log.warning(
                "O'quvchi limiti oshdi (ENFORCE_QUOTA=false): user=%s guruh=%s — %s",
                db_user.id, group_id, reason,
            )

        students = await add_students(db, group_id, names)
        await db.commit()

    await state.clear()
    names_list = "\n".join(f"• {escape(s.full_name)}" for s in students)

    await message.answer(
        f"✅ {len(students)} ta o'quvchi guruhga qo'shildi:\n{names_list}",
    )
    await message.answer(
        "Guruh boshqaruviga o'tish yoki Bosh menyuga qaytish:",
        reply_markup=group_menu_kb(group_id),
    )
