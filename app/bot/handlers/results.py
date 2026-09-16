"""
app/bot/handlers/results.py — Natijalar va tarix ko'rish oqimi (faqat inline).
"""
from __future__ import annotations

import logging
from aiogram import F, Router
from aiogram.types import BufferedInputFile, CallbackQuery

from app.bot.keyboards.inline import (
    main_menu_inline_kb,
    groups_kb,
    res_group_menu_kb,
    res_tests_kb,
    res_test_menu_kb,
    res_student_kb,
    res_student_attempts_kb,
    back_to_student_kb,
)
from app.core.db import get_session_factory
from app.models.user import User
from app.services.access import owned_attempt, owned_group, owned_student, owned_test
from app.services.groups import get_groups_by_owner
from app.services.telegram import escape
from app.services.tests import get_tests_by_group
from app.services.history import test_stats
from app.services.grading import format_attempt_breakdown
from app.models.attempt import Attempt
from app.models.student import Student
from app.models.test import Test
from app.models.titul import Titul
from app.services.excel import (
    export_all_excel,
    export_group_excel,
    export_test_excel,
    export_student_excel,
    safe_filename,
)
from sqlalchemy import select, func

router = Router(name="results")
log = logging.getLogger(__name__)

# Egalik: `res_*:<id>` callback'lari mijozdan keladi va soxtalanishi mumkin.
# Har guruh/test/o'quvchi/urinish `owned_*` bilan joriy ustozga tegishli
# ekani tekshiriladi; Excel eksportlar servisga `owner_id` beradi.
# `db_user` — `AccessMiddleware` bergan bazadagi foydalanuvchi.
# Bot default parse_mode=HTML — guruh/test/o'quvchi nomlari `escape()` dan o'tadi.
# Reply-keyboard yo'q (bot faqat inline) — `"📊 Natijalar"` matn handleri
# hech qachon ishlamasdi va olib tashlandi (weaknesses №25).


@router.callback_query(F.data == "menu_results")
@router.callback_query(F.data == "res_main")
async def results_menu(call: CallbackQuery, db_user: User) -> None:
    log.info("Callback query 'menu_results'/'res_main' called by user_id=%d", call.from_user.id)
    try:
        owner_id = db_user.id
        factory = get_session_factory()
        async with factory() as db:
            groups = await get_groups_by_owner(db, owner_id)
            log.info("Loaded %d groups for callback results menu", len(groups))

        if not groups:
            await call.message.edit_text(
                "Hozircha guruh yo'q.",
                reply_markup=main_menu_inline_kb(),
            )
            await call.answer()
            return

        # Guruhlar ro'yxati va umumiy Excel tugmasi
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton
        
        builder = InlineKeyboardBuilder()
        for g in groups:
            builder.button(text=g.name, callback_data=f"res_group:{g.id}")
        builder.button(text="📥 Barcha natijalar (Excel)", callback_data="res_all_excel")
        builder.button(text="⬅️ Bosh menyu", callback_data="back_to_main")
        builder.adjust(1)

        await call.message.edit_text(
            "📊 Natijalarini ko'rish uchun guruh tanlang yoki barcha natijalarni yuklab oling:",
            reply_markup=builder.as_markup(),
        )
        await call.answer()
    except Exception as e:
        log.exception("Error in callback results_menu: %s", e)
        await call.answer("❌ Natijalarni yuklashda xatolik yuz berdi.", show_alert=True)


@router.callback_query(F.data.startswith("res_group:"))
async def show_res_group(call: CallbackQuery, db_user: User) -> None:
    group_id = int(call.data.split(":")[1])
    owner_id = db_user.id
    factory = get_session_factory()
    async with factory() as db:
        group = await owned_group(db, group_id, owner_id)

    if group is None:
        await call.answer("Guruh topilmadi.", show_alert=True)
        return

    await call.message.edit_text(
        f"📁 Guruh: <b>{escape(group.name)}</b>\n\nNatijalarni ko'rish yoki Excel formatida yuklab olishni tanlang:",
        reply_markup=res_group_menu_kb(group_id),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data.startswith("res_group_tests:"))
async def show_res_group_tests(call: CallbackQuery, db_user: User) -> None:
    group_id = int(call.data.split(":")[1])
    owner_id = db_user.id
    factory = get_session_factory()
    async with factory() as db:
        if await owned_group(db, group_id, owner_id) is None:
            await call.answer("Guruh topilmadi.", show_alert=True)
            return
        tests = await get_tests_by_group(db, group_id, owner_id=owner_id)

    if not tests:
        await call.message.edit_text(
            "Ushbu guruhda hali testlar yaratilmagan.",
            reply_markup=res_group_menu_kb(group_id),
        )
        await call.answer()
        return

    await call.message.edit_text(
        "📝 Kerakli olimpiadani (testni) tanlang:",
        reply_markup=res_tests_kb(tests, group_id),
    )
    await call.answer()


# `results:<id>` — test menyusidagi "📊 Natijalar" tugmasi (inline.py:test_menu_kb);
# ilgari handleri yo'q edi va tugma "aylanib" turardi (weaknesses №25).
@router.callback_query(F.data.startswith("results:"))
@router.callback_query(F.data.startswith("res_test:"))
async def show_res_test(call: CallbackQuery, db_user: User) -> None:
    test_id = int(call.data.split(":")[1])
    owner_id = db_user.id
    factory = get_session_factory()
    async with factory() as db:
        test = await owned_test(db, test_id, owner_id)
        if test is None:
            await call.answer("Test topilmadi.", show_alert=True)
            return
        stats = await test_stats(db, test_id)

    avg_pct = f"{stats['avg_percent']}%" if stats['avg_percent'] is not None else "0.0%"
    max_pct = f"{stats['max_percent']}%" if stats['max_percent'] is not None else "0.0%"
    
    await call.message.edit_text(
        f"🏆 Olimpiada: <b>{escape(test.title)}</b>\n"
        f"Savollar soni: {test.question_count} ta\n\n"
        f"📊 Statistika:\n"
        f"└ Ishtirokchilar: {stats['count']} ta\n"
        f"└ O'rtacha foiz: {avg_pct}\n"
        f"└ Eng yuqori foiz: {max_pct}",
        reply_markup=res_test_menu_kb(test_id, test.group_id),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data.startswith("res_test_students:"))
async def show_res_test_students(call: CallbackQuery, db_user: User) -> None:
    test_id = int(call.data.split(":")[1])
    owner_id = db_user.id
    factory = get_session_factory()
    async with factory() as db:
        test = await owned_test(db, test_id, owner_id)
        if test is None:
            await call.answer("Test topilmadi.", show_alert=True)
            return

        # Guruhdagi barcha o'quvchilarni va ularning ushbu test bo'yicha eng oxirgi urinishlarini olish
        latest_subq = (
            select(
                Attempt.id.label("attempt_id"),
                Titul.student_id,
                func.row_number()
                .over(
                    partition_by=Titul.student_id,
                    order_by=Attempt.created_at.desc(),
                )
                .label("rn"),
            )
            .join(Titul, Titul.id == Attempt.titul_id)
            .where(Titul.test_id == test_id, Attempt.status == "done")
            .subquery()
        )

        stmt = (
            select(
                Student.full_name,
                Student.id,
                Attempt.score,
                Attempt.total,
                Attempt.id.label("attempt_id")
            )
            .outerjoin(latest_subq, (latest_subq.c.student_id == Student.id) & (latest_subq.c.rn == 1))
            .outerjoin(Attempt, Attempt.id == latest_subq.c.attempt_id)
            .where(Student.group_id == test.group_id)
            .order_by(Student.full_name)
        )
        rows = (await db.execute(stmt)).all()

    attempts = [
        (r[0], r[1], r[2] or 0, r[3] or 0, r[4])
        for r in rows
    ]

    await call.message.edit_text(
        "👥 Guruh o'quvchilari ro'yxati (Urinish tahlili uchun o'quvchini tanlang):",
        reply_markup=res_student_kb(attempts, test_id),
    )
    await call.answer()


@router.callback_query(F.data.startswith("res_student_tests:"))
async def show_res_student_tests(call: CallbackQuery, db_user: User) -> None:
    student_id = int(call.data.split(":")[1])
    from_test_id = int(call.data.split(":")[2])
    owner_id = db_user.id
    factory = get_session_factory()
    async with factory() as db:
        student = await owned_student(db, student_id, owner_id)
        if student is None:
            await call.answer("O'quvchi topilmadi.", show_alert=True)
            return

        stmt = (
            select(
                Test.title,
                Attempt.score,
                Attempt.total,
                Attempt.id
            )
            .join(Titul, Titul.id == Attempt.titul_id)
            .join(Test, Test.id == Titul.test_id)
            .where(Titul.student_id == student_id, Attempt.status == "done")
            .order_by(Attempt.created_at.desc())
        )
        rows = (await db.execute(stmt)).all()

    attempts = [
        (r[0], r[1] or 0, r[2] or 0, r[3])
        for r in rows
    ]

    if not attempts:
        await call.answer("Ushbu o'quvchi hali hech qaysi testda qatnashmagan.", show_alert=True)
        return

    await call.message.edit_text(
        f"👤 O'quvchi: <b>{escape(student.full_name)}</b>\n\nIshtirok etgan olimpiadalari ro'yxati:",
        reply_markup=res_student_attempts_kb(attempts, student_id, from_test_id),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data.startswith("res_attempt_detail:"))
async def show_res_attempt_detail(call: CallbackQuery, db_user: User) -> None:
    parts = call.data.split(":")
    attempt_id = int(parts[1])
    student_id = int(parts[2])
    from_test_id = int(parts[3])

    owner_id = db_user.id
    factory = get_session_factory()
    async with factory() as db:
        # `owned_attempt` titul → student/test zanjirini ham yuklaydi.
        attempt = await owned_attempt(db, attempt_id, owner_id)

    if attempt is None:
        await call.answer("Urinish ma'lumotlari topilmadi.", show_alert=True)
        return

    student_name = attempt.titul.student.full_name
    test_title = attempt.titul.test.title

    msg = format_attempt_breakdown(
        detail=attempt.detail or {},
        student_name=student_name,
        test_title=test_title,
        score=attempt.score or 0,
        total=attempt.total or 0,
    )

    await call.message.edit_text(
        msg,
        reply_markup=back_to_student_kb(student_id, from_test_id),
        parse_mode="HTML",
    )
    await call.answer()


# ─── EXCEL EKSPORT QATROVLARI ────────────────────────────────────────────────

@router.callback_query(F.data == "res_all_excel")
async def export_all(call: CallbackQuery, db_user: User) -> None:
    owner_id = db_user.id
    factory = get_session_factory()
    async with factory() as db:
        excel_bytes = await export_all_excel(db, owner_id)

    await call.message.answer_document(
        BufferedInputFile(excel_bytes, filename="barcha_natijalar.xlsx"),
        caption="📊 Barcha guruhlar va olimpiadalar bo'yicha umumiy natijalar",
    )
    await call.answer()


@router.callback_query(F.data.startswith("res_group_excel:"))
async def export_group(call: CallbackQuery, db_user: User) -> None:
    group_id = int(call.data.split(":")[1])
    owner_id = db_user.id
    factory = get_session_factory()
    async with factory() as db:
        group = await owned_group(db, group_id, owner_id)
        if group is None:
            await call.answer("Guruh topilmadi.", show_alert=True)
            return
        excel_bytes = await export_group_excel(db, group_id, owner_id=owner_id)

    safe_name = safe_filename(group.name, fallback="guruh").lower()
    await call.message.answer_document(
        BufferedInputFile(excel_bytes, filename=f"natijalar_guruh_{safe_name}.xlsx"),
        caption=f"📊 Guruh: {escape(group.name)} — barcha olimpiadalar natijalari",
    )
    await call.answer()


@router.callback_query(F.data.startswith("res_test_excel:"))
async def export_test(call: CallbackQuery, db_user: User) -> None:
    test_id = int(call.data.split(":")[1])
    owner_id = db_user.id
    factory = get_session_factory()
    async with factory() as db:
        test = await owned_test(db, test_id, owner_id)
        if test is None:
            await call.answer("Test topilmadi.", show_alert=True)
            return
        excel_bytes = await export_test_excel(db, test_id, owner_id=owner_id)

    safe_title = safe_filename(test.title, fallback="test").lower()
    await call.message.answer_document(
        BufferedInputFile(excel_bytes, filename=f"natijalar_olimpiada_{safe_title}.xlsx"),
        caption=f"🏆 Olimpiada: {escape(test.title)} — o'quvchilar natijalari",
    )
    await call.answer()


@router.callback_query(F.data.startswith("res_student_excel:"))
async def export_student(call: CallbackQuery, db_user: User) -> None:
    student_id = int(call.data.split(":")[1])
    owner_id = db_user.id
    factory = get_session_factory()
    async with factory() as db:
        student = await owned_student(db, student_id, owner_id)
        if student is None:
            await call.answer("O'quvchi topilmadi.", show_alert=True)
            return
        excel_bytes = await export_student_excel(db, student_id, owner_id=owner_id)

    safe_name = safe_filename(student.full_name, fallback="oquvchi").lower()
    await call.message.answer_document(
        BufferedInputFile(excel_bytes, filename=f"natijalar_oquvchi_{safe_name}.xlsx"),
        caption=f"👤 O'quvchi: {escape(student.full_name)} — barcha testlardagi ishtiroki",
    )
    await call.answer()
