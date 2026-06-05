"""
app/bot/handlers/tests.py — Test yaratish va boshqarish oqimi (faqat inline).
"""
from __future__ import annotations

import io
import logging
import zipfile
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, FSInputFile, Message

from app.bot.keyboards.inline import (
    cancel_inline_kb,
    confirm_test_kb,
    generate_tituls_kb,
    group_menu_kb,
    groups_kb,
    qcount_kb,
    test_menu_kb,
    tests_kb,
    titul_format_kb,
    vcount_kb,
    main_menu_inline_kb,
)
from app.bot.states import TestCreate
from app.core.db import get_session_factory
from app.services.groups import get_group, get_groups_by_owner, get_or_create_user
from app.services.tests import create_test, get_test, get_tests_by_group, parse_key
from app.services.titul import generate_tituls_for_test, get_tituls_by_test

log = logging.getLogger(__name__)
router = Router(name="tests")


async def _owner_id(telegram_id: int) -> int:
    factory = get_session_factory()
    async with factory() as db:
        user = await get_or_create_user(db, telegram_id)
        await db.commit()
        return user.id


# ─── Testlar menyu (Inline callback) ──────────────────────────────────────────

@router.callback_query(F.data == "menu_tests")
async def list_tests_menu(call: CallbackQuery) -> None:
    owner_id = await _owner_id(call.from_user.id)
    factory = get_session_factory()
    async with factory() as db:
        groups = await get_groups_by_owner(db, owner_id)

    if not groups:
        await call.message.edit_text(
            "Avval guruh yarating.",
            reply_markup=main_menu_inline_kb(),
        )
        await call.answer()
        return

    # Guruhni tanlash
    await call.message.edit_text(
        "Qaysi guruh testlarini ko'rmoqchisiz?",
        reply_markup=groups_kb(groups, prefix="list_tests:"),
    )
    await call.answer()


@router.callback_query(F.data.startswith("list_tests:"))
async def list_tests_for_group(call: CallbackQuery) -> None:
    group_id = int(call.data.split(":")[1])
    factory = get_session_factory()
    async with factory() as db:
        tests = await get_tests_by_group(db, group_id)

    if not tests:
        # Orqaga qaytish tugmasi
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        back_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"group:{group_id}")]
        ])
        await call.message.edit_text(
            "Bu guruhda hozircha test yo'q.",
            reply_markup=back_kb,
        )
        await call.answer()
        return

    await call.message.edit_text(
        f"📋 Testlar ({len(tests)} ta):",
        reply_markup=tests_kb(tests, group_id, prefix="test:"),
    )
    await call.answer()


# ─── Test yaratish FSM (Faqat inline tugmalar va bekor qilish) ─────────────────

@router.callback_query(F.data.startswith("create_test:"))
async def start_create_test(call: CallbackQuery, state: FSMContext) -> None:
    group_id = int(call.data.split(":")[1])
    await state.set_state(TestCreate.waiting_title)
    await state.update_data(group_id=group_id)
    await call.message.edit_text(
        "📝 Yangi test nomini yuboring:",
        reply_markup=cancel_inline_kb(),
    )
    await call.answer()


@router.message(TestCreate.waiting_title)
async def receive_test_title(message: Message, state: FSMContext) -> None:
    title = message.text.strip()
    if not title:
        await message.answer(
            "Test nomi bo'sh bo'lmaydi. Qayta yuboring:",
            reply_markup=cancel_inline_kb()
        )
        return
    await state.update_data(title=title)
    await state.set_state(TestCreate.choosing_qcount)
    await message.answer(
        f"✅ Test nomi: <b>{title}</b>\n\nSavollar sonini tanlang:",
        reply_markup=qcount_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("qcount:"), TestCreate.choosing_qcount)
async def receive_qcount(call: CallbackQuery, state: FSMContext) -> None:
    qcount = int(call.data.split(":")[1])
    await state.update_data(qcount=qcount)
    await state.set_state(TestCreate.choosing_vcount)
    await call.message.edit_text(
        f"Savol soni: <b>{qcount}</b>\n\nVariant sonini tanlang:",
        reply_markup=vcount_kb(),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data.startswith("vcount:"), TestCreate.choosing_vcount)
async def receive_vcount(call: CallbackQuery, state: FSMContext) -> None:
    vcount = int(call.data.split(":")[1])
    data = await state.get_data()
    qcount = data["qcount"]
    options = "ABCDE"[:vcount]
    await state.update_data(vcount=vcount)
    await state.set_state(TestCreate.entering_key)

    await call.message.edit_text(
        f"Variant soni: <b>{vcount} ({options})</b>\n\n"
        f"To'g'ri javoblarni yuboring. <b>{qcount}</b> ta javob kerak.\n\n"
        "Format 1: <code>ABCDABCD...</code>\n"
        "Format 2: <code>1 A\n2-C\n3:B</code>",
        reply_markup=cancel_inline_kb(),
        parse_mode="HTML",
    )
    await call.answer()


@router.message(TestCreate.entering_key)
async def receive_answer_key(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    qcount: int = data["qcount"]
    vcount: int = data["vcount"]
    options = list("ABCDE"[:vcount])

    try:
        key = parse_key(message.text, qcount, options)
    except ValueError as e:
        await message.answer(
            f"❌ Xatolik: {e}\n\nQayta yuboring:",
            reply_markup=cancel_inline_kb()
        )
        return

    await state.update_data(answer_key=key)
    await state.set_state(TestCreate.confirm)

    # Namunaviy ko'rsatish (birinchi 10 ta)
    preview = " ".join(f"{k}:{v}" for k, v in list(key.items())[:10])
    await message.answer(
        f"✅ <b>{len(key)} ta javob qabul qilindi.</b>\n\n"
        f"<code>{preview}...</code>\n\n"
        "Tasdiqlaysizmi?",
        reply_markup=confirm_test_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "confirm_test:no", TestCreate.confirm)
async def confirm_test_no(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_text(
        "❌ Test yaratish bekor qilindi.",
        reply_markup=main_menu_inline_kb()
    )
    await call.answer()


@router.callback_query(F.data == "confirm_test:yes", TestCreate.confirm)
async def confirm_test_yes(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    group_id = data["group_id"]

    factory = get_session_factory()
    async with factory() as db:
        test = await create_test(
            db,
            group_id=group_id,
            title=data["title"],
            question_count=data["qcount"],
            variant_count=data["vcount"],
            answer_key=data["answer_key"],
        )
        await db.commit()
        test_id = test.id
        test_title = test.title
        qcount = test.question_count

    await state.clear()
    
    # State ichiga keyinchalik gen_tituls ishlatishi uchun test_id saqlaymiz
    await state.update_data(test_id=test_id)
    
    await call.message.edit_text(
        f"✅ <b>{test_title}</b> testi saqlandi!\n({qcount} ta savol)\n\n"
        "Javoblar varaqalarini (titullarni) hozir generatsiya qilaymi?",
        reply_markup=generate_tituls_kb(),
        parse_mode="HTML",
    )
    await call.answer()


# ─── Titul generatsiya ────────────────────────────────────────────────────────

@router.callback_query(F.data == "gen_tituls:later")
async def gen_tituls_later(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_text(
        "Keyinroq Testlar bo'limidan generatsiya qilishingiz mumkin.",
        reply_markup=main_menu_inline_kb()
    )
    await call.answer()


@router.callback_query(F.data == "gen_tituls:all")
async def gen_tituls_all(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    test_id: int = data.get("test_id", 0)

    if not test_id:
        log.warning("gen_tituls:all bosildi ammo FSM state da test_id topilmadi.")
        await call.answer("Test ID topilmadi.", show_alert=True)
        return

    log.info("Test (ID: %d) uchun titul generatsiya boshlandi.", test_id)
    await call.message.edit_text("⏳ Titullar tayyorlanmoqda... Tayyor bo'lgach har biri yuboriladi.")

    factory = get_session_factory()
    try:
        async with factory() as db:
            titul_ids = await generate_tituls_for_test(db, test_id)
            await db.commit()
    except ValueError as e:
        log.error("Titul generatsiya qilishda xatolik (test_id=%d): %s", test_id, e)
        await call.message.answer(f"❌ {e}")
        await call.answer()
        return

    chat_id = call.message.chat.id
    log.info("Titul yozuvlari yaratildi (soni: %d). Celery tasklar yuborilmoqda... (chat_id: %d)", len(titul_ids), chat_id)

    # Har titul uchun Celery task
    from app.worker.tasks import pdf_task
    for tid in titul_ids:
        pdf_task.delay(tid, chat_id)

    # ZIP yuklash yoki boshqa menyu
    await call.message.answer(
        f"⏳ {len(titul_ids)} ta titul generatsiya qilinmoqda.\n"
        "Yuklab olish formatini tanlang:",
        reply_markup=titul_format_kb(test_id),
    )
    await call.answer()


# ─── Test boshqaruvi ─────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("test:"))
async def test_selected(call: CallbackQuery) -> None:
    test_id = int(call.data.split(":")[1])
    factory = get_session_factory()
    async with factory() as db:
        test = await get_test(db, test_id)

    if test is None:
        await call.answer("Test topilmadi", show_alert=True)
        return

    await call.message.edit_text(
        f"📝 <b>{test.title}</b>\n"
        f"Savollar soni: {test.question_count} ta\n"
        f"Variantlar soni: {test.variant_count} ta\n\n"
        f"Nima qilmoqchisiz?",
        reply_markup=test_menu_kb(test_id),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data.startswith("tituls:"))
async def show_tituls_menu(call: CallbackQuery, state: FSMContext) -> None:
    test_id = int(call.data.split(":")[1])
    factory = get_session_factory()
    async with factory() as db:
        tituls = await get_tituls_by_test(db, test_id)

    if not tituls:
        await state.update_data(test_id=test_id)
        await call.message.edit_text(
            "Bu test uchun hali titullar (javoblar varaqalari) generatsiya qilinmagan.\n"
            "Hozir generatsiya qilamizmi?",
            reply_markup=generate_tituls_kb(),
        )
    else:
        await call.message.edit_text(
            f"Jami {len(tituls)} ta o'quvchi uchun titul mavjud.\n"
            "Qanday formatda yuklab olmoqchisiz?",
            reply_markup=titul_format_kb(test_id),
        )
    await call.answer()


@router.callback_query(F.data.startswith("tituls_send:single:"))
async def send_tituls_single(call: CallbackQuery, bot: Bot) -> None:
    test_id = int(call.data.split(":")[-1])
    factory = get_session_factory()
    async with factory() as db:
        tituls = await get_tituls_by_test(db, test_id)

    ready = [t for t in tituls if t.pdf_path and Path(t.pdf_path).exists()]
    if not ready:
        await call.answer("Hali tayyor titul yo'q.", show_alert=True)
        return

    await call.message.answer(f"⏳ {len(ready)} ta titul yuborilmoqda...")
    for t in ready:
        try:
            fname = Path(t.pdf_path).name
            await bot.send_document(
                call.message.chat.id,
                FSInputFile(t.pdf_path, filename=fname),
                caption=f"📄 {fname}"
            )
        except Exception as e:
            log.error("Titul yuborishda xato (%s): %s", t.pdf_path, e)
    await call.answer()


@router.callback_query(F.data.startswith("tituls_send:zip:"))
async def send_tituls_zip(call: CallbackQuery, bot: Bot) -> None:
    test_id = int(call.data.split(":")[-1])
    factory = get_session_factory()
    async with factory() as db:
        tituls = await get_tituls_by_test(db, test_id)

    ready = [t for t in tituls if t.pdf_path and Path(t.pdf_path).exists()]
    if not ready:
        await call.answer("Hali tayyor titul yo'q.", show_alert=True)
        return

    await call.message.answer("⏳ ZIP tayyorlanmoqda...")

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for t in ready:
            fname = Path(t.pdf_path).name
            zf.write(t.pdf_path, fname)

    zip_buf.seek(0)
    await bot.send_document(
        call.message.chat.id,
        BufferedInputFile(zip_buf.read(), filename=f"titullar_test{test_id}.zip"),
        caption=f"📦 {len(ready)} ta titul",
    )
    await call.answer()
