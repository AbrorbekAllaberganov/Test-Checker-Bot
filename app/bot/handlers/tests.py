"""
app/bot/handlers/tests.py — Test yaratish va boshqarish oqimi (faqat inline).
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message

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
from app.core.config import get_settings
from app.core.db import get_session_factory
from app.models.user import User
from app.services.access import owned_group, owned_test
from app.services.groups import get_groups_by_owner
from app.services.telegram import escape
from app.services.tests import (
    DEFAULT_OPTIONS,
    SUPPORTED_VCOUNTS,
    create_test,
    get_tests_by_group,
    parse_key,
)
from app.services.titul import generate_tituls_for_test, get_tituls_by_test

log = logging.getLogger(__name__)
router = Router(name="tests")

# Egalik: har `group:`/`test:` callback'i va FSM'dagi id'lar joriy ustozga
# tegishli ekani `owned_group`/`owned_test` bilan tekshiriladi. Begona
# obyekt → "topilmadi". Servislar ham `owner_id` bilan chaqiriladi
# (ikki qatlam — handler unutsa ham servis himoya qiladi).
# `db_user` — `AccessMiddleware` bergan bazadagi foydalanuvchi.
# Bot default parse_mode=HTML — test nomi/xato matni `escape()` dan o'tadi.


# ─── Testlar menyu (Inline callback) ──────────────────────────────────────────

@router.callback_query(F.data == "menu_tests")
async def list_tests_menu(call: CallbackQuery, db_user: User) -> None:
    owner_id = db_user.id
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
async def list_tests_for_group(call: CallbackQuery, db_user: User) -> None:
    group_id = int(call.data.split(":")[1])
    owner_id = db_user.id
    factory = get_session_factory()
    async with factory() as db:
        if await owned_group(db, group_id, owner_id) is None:
            await call.answer("Guruh topilmadi.", show_alert=True)
            return
        tests = await get_tests_by_group(db, group_id, owner_id=owner_id)

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
async def start_create_test(call: CallbackQuery, state: FSMContext, db_user: User) -> None:
    group_id = int(call.data.split(":")[1])
    owner_id = db_user.id
    factory = get_session_factory()
    async with factory() as db:
        group = await owned_group(db, group_id, owner_id)
    if group is None:
        await call.answer("Guruh topilmadi.", show_alert=True)
        return

    await state.set_state(TestCreate.waiting_title)
    await state.update_data(group_id=group_id)
    await call.message.edit_text(
        "📝 Yangi test nomini yuboring:",
        reply_markup=cancel_inline_kb(),
    )
    await call.answer()


@router.message(TestCreate.waiting_title, F.text)
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
        f"✅ Test nomi: <b>{escape(title)}</b>\n\nSavollar sonini tanlang:",
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
    # Eski klaviaturadagi "5 (A-E)" tugmasi (yoki soxta callback) rad etiladi:
    # layout A-D uchun kalibrlangan (weaknesses.md №12).
    if vcount not in SUPPORTED_VCOUNTS:
        await call.answer(
            "Hozircha faqat 4 variantli (A-D) testlar qo'llanadi.",
            show_alert=True,
        )
        return

    data = await state.get_data()
    qcount = data["qcount"]
    options = DEFAULT_OPTIONS[:vcount]
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


@router.message(TestCreate.entering_key, F.text)
async def receive_answer_key(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    qcount: int = data["qcount"]
    vcount: int = data["vcount"]
    options = list(DEFAULT_OPTIONS[:vcount])

    try:
        key = parse_key(message.text, qcount, options)
    except ValueError as e:
        # Xato matnida foydalanuvchi kiritgan belgilar bo'lishi mumkin (`<`).
        await message.answer(
            f"❌ Xatolik: {escape(e)}\n\nQayta yuboring:",
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
async def confirm_test_yes(call: CallbackQuery, state: FSMContext, db_user: User) -> None:
    data = await state.get_data()
    group_id = data["group_id"]
    owner_id = db_user.id

    factory = get_session_factory()
    async with factory() as db:
        # FSM'dagi group_id qayta tekshiriladi — state Redis'da, uni
        # o'rnatgan callback tekshiruvdan o'tgan bo'lsa ham guruh shu orada
        # o'chirilgan bo'lishi mumkin.
        if await owned_group(db, group_id, owner_id) is None:
            await state.clear()
            await call.message.edit_text(
                "Guruh topilmadi. Bosh menyudan qaytadan boshlang.",
                reply_markup=main_menu_inline_kb(),
            )
            await call.answer()
            return
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
        f"✅ <b>{escape(test_title)}</b> testi saqlandi!\n({qcount} ta savol)\n\n"
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
async def gen_tituls_all(call: CallbackQuery, state: FSMContext, bot: Bot, db_user: User) -> None:
    data = await state.get_data()
    test_id: int = data.get("test_id", 0)

    if not test_id:
        log.warning("gen_tituls:all bosildi ammo FSM state da test_id topilmadi.")
        await call.answer("Test ID topilmadi.", show_alert=True)
        return

    log.info("Test (ID: %d) uchun titul generatsiya boshlandi.", test_id)
    await call.message.edit_text(
        "⏳ Titullar tayyorlanmoqda... Tayyor bo'lgach ZIP arxiv sifatida yuboriladi."
    )

    owner_id = db_user.id
    factory = get_session_factory()
    try:
        async with factory() as db:
            # owner_id — test shu ustozniki ekani servisda tekshiriladi;
            # begona test_id (soxta FSM) → ValueError("Test topilmadi").
            titul_ids = await generate_tituls_for_test(db, test_id, owner_id=owner_id)
            await db.commit()
    except ValueError as e:
        log.error("Titul generatsiya qilishda xatolik (test_id=%d): %s", test_id, e)
        await call.message.answer(f"❌ {escape(e)}")
        await call.answer()
        return

    chat_id = call.message.chat.id
    log.info("Titul yozuvlari yaratildi (soni: %d). Celery tasklar yuborilmoqda... (chat_id: %d)", len(titul_ids), chat_id)

    # BITTA task: hammasini render qilib bitta ZIP qilib yuboradi.
    # Ilgari har titul uchun alohida `pdf_task(tid, chat_id)` edi — 150
    # o'quvchi = 150 ta xabar, Telegram flood limiti, ba'zilari indamay
    # yo'qolardi (weaknesses.md №22).
    from app.worker.tasks import tituls_batch_task
    tituls_batch_task.delay(test_id, chat_id)

    await call.message.answer(
        f"⏳ {len(titul_ids)} ta titul tayyorlanmoqda — tayyor bo'lgach ZIP yuboriladi.\n"
        "Keyinroq boshqa formatda ham yuklab olishingiz mumkin:",
        reply_markup=titul_format_kb(test_id),
    )
    await call.answer()


# ─── Test boshqaruvi ─────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("test:"))
async def test_selected(call: CallbackQuery, db_user: User) -> None:
    test_id = int(call.data.split(":")[1])
    owner_id = db_user.id
    factory = get_session_factory()
    async with factory() as db:
        test = await owned_test(db, test_id, owner_id)

    if test is None:
        await call.answer("Test topilmadi", show_alert=True)
        return

    # Eski (T-21 dan oldin yaratilgan) 5 variantli testlar bazada qolgan —
    # OMR ular uchun "E" doirasini o'qiy olmaydi, ustoz buni bilishi kerak.
    warning = ""
    if test.variant_count not in SUPPORTED_VCOUNTS:
        warning = (
            "\n⚠️ <b>Diqqat:</b> bu test 5 variantli (A-E). Tekshiruv faqat "
            "A-D doiralarini o'qiydi — “E” javoblar xato hisoblanadi.\n"
        )

    await call.message.edit_text(
        f"📝 <b>{escape(test.title)}</b>\n"
        f"Savollar soni: {test.question_count} ta\n"
        f"Variantlar soni: {test.variant_count} ta\n"
        f"{warning}\n"
        f"Nima qilmoqchisiz?",
        reply_markup=test_menu_kb(test_id),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data.startswith("tituls:"))
async def show_tituls_menu(call: CallbackQuery, state: FSMContext, db_user: User) -> None:
    test_id = int(call.data.split(":")[1])
    owner_id = db_user.id
    factory = get_session_factory()
    async with factory() as db:
        if await owned_test(db, test_id, owner_id) is None:
            await call.answer("Test topilmadi.", show_alert=True)
            return
        tituls = await get_tituls_by_test(db, test_id, owner_id=owner_id)

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
async def send_tituls_single(call: CallbackQuery, bot: Bot, db_user: User) -> None:
    test_id = int(call.data.split(":")[-1])
    owner_id = db_user.id
    factory = get_session_factory()
    async with factory() as db:
        # owner_id — begona test uchun bo'sh ro'yxat qaytadi (PDF'da F.I.Sh + QR bor).
        tituls = await get_tituls_by_test(db, test_id, owner_id=owner_id)

    ready = [t for t in tituls if t.pdf_path and Path(t.pdf_path).exists()]
    if not ready:
        await call.answer("Hali tayyor titul yo'q.", show_alert=True)
        return

    # Telegram flood limiti (weaknesses.md №22): "alohida" rejimi faqat kichik
    # guruhlar uchun. Kattasida ZIP — u bitta xabar.
    limit = get_settings().titul_single_send_max
    if len(ready) > limit:
        await call.answer(
            f"{len(ready)} ta titulni alohida yuborib bo'lmaydi "
            f"(chegara {limit} ta). ZIP ni tanlang.",
            show_alert=True,
        )
        return

    await call.message.answer(f"⏳ {len(ready)} ta titul yuborilmoqda...")
    sent = 0
    for t in ready:
        fname = Path(t.pdf_path).name
        ok = await _send_document_safe(
            bot,
            call.message.chat.id,
            FSInputFile(t.pdf_path, filename=fname),
            caption=f"📄 {escape(fname)}",
        )
        if ok:
            sent += 1
        # Ketma-ket yuborishda Telegram ~30 msg/s ga ruxsat beradi.
        await asyncio.sleep(0.05)

    if sent < len(ready):
        await call.message.answer(
            f"⚠️ {len(ready) - sent} ta titul yuborilmadi. ZIP orqali urinib ko'ring."
        )
    await call.answer()


@router.callback_query(F.data.startswith("tituls_send:zip:"))
async def send_tituls_zip(call: CallbackQuery, bot: Bot, db_user: User) -> None:
    test_id = int(call.data.split(":")[-1])
    owner_id = db_user.id
    factory = get_session_factory()
    async with factory() as db:
        if await owned_test(db, test_id, owner_id) is None:
            await call.answer("Test topilmadi.", show_alert=True)
            return

    # ZIP endi worker'da, DISKDA yig'iladi va kerak bo'lsa bo'laklarga
    # bo'linadi — ilgari butun arxiv bot jarayonining xotirasida edi va
    # 50 MB dan oshsa Telegram indamay rad etardi (weaknesses.md №22).
    from app.worker.tasks import tituls_batch_task
    tituls_batch_task.delay(test_id, call.message.chat.id)

    await call.message.answer("⏳ ZIP tayyorlanmoqda, tayyor bo'lgach yuboriladi...")
    await call.answer()


async def _send_document_safe(bot: Bot, chat_id: int, document, caption: str) -> bool:
    """
    Hujjat yuboradi; `RetryAfter` kelsa aytilgan vaqt kutib bir marta qaytaradi.

    Ilgari 429 faqat log qilinardi va titul indamay yetib bormasdi.
    """
    for attempt in range(2):
        try:
            await bot.send_document(chat_id, document, caption=caption)
            return True
        except TelegramRetryAfter as exc:
            if attempt == 0:
                await asyncio.sleep(exc.retry_after + 1)
                continue
            log.error("Titul yuborilmadi (flood limiti): chat_id=%d", chat_id)
            return False
        except TelegramForbiddenError:
            log.warning("Bot bloklangan: chat_id=%d", chat_id)
            return False
        except Exception as e:
            log.error("Titul yuborishda xato: %s", e)
            return False
    return False
