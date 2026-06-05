"""
app/bot/handlers/students.py — O'quvchi qo'shish va ko'rish oqimi (faqat inline).
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.keyboards.inline import cancel_inline_kb, group_menu_kb
from app.bot.states import StudentAdd
from app.core.db import get_session_factory
from app.services.students import add_students, get_students_by_group

router = Router(name="students")


@router.callback_query(F.data.startswith("students:"))
async def list_students_handler(call: CallbackQuery) -> None:
    group_id = int(call.data.split(":")[1])
    factory = get_session_factory()
    async with factory() as db:
        students = await get_students_by_group(db, group_id)

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

    text = f"👥 O'quvchilar ({len(students)} ta):\n\n"
    for i, s in enumerate(students, 1):
        text += f"{i}. {s.full_name}\n"

    await call.message.edit_text(text, reply_markup=back_kb)
    await call.answer()


@router.callback_query(F.data.startswith("add_students:"))
async def start_add_students(call: CallbackQuery, state: FSMContext) -> None:
    group_id = int(call.data.split(":")[1])
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


@router.message(StudentAdd.waiting_names)
async def receive_student_names(message: Message, state: FSMContext) -> None:
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
        students = await add_students(db, group_id, names)
        await db.commit()

    await state.clear()
    names_list = "\n".join(f"• {s.full_name}" for s in students)
    
    await message.answer(
        f"✅ {len(students)} ta o'quvchi guruhga qo'shildi:\n{names_list}",
    )
    await message.answer(
        "Guruh boshqaruviga o'tish yoki Bosh menyuga qaytish:",
        reply_markup=group_menu_kb(group_id),
    )
