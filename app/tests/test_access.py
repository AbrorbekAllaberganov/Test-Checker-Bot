"""
app/tests/test_access.py — Egalik (tenant) izolyatsiyasi testlari.

Ikki ustoz: A o'z guruhi/testi/o'quvchisi/urinishini ko'radi; B esa A ning
obyektlari uchun `None`, bo'sh ro'yxat yoki 404 oladi. Haqiqiy bazaga
yozadi va oxirida tozalaydi (T-35 test izolyatsiyasi kelguncha shu uslub —
`test_web_api.py` bilan bir xil).
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.main import app
from app.api.routes.auth import get_webapp_user
from app.core.db import get_session_factory
from app.models.attempt import Attempt
from app.models.group import Group
from app.models.student import Student
from app.models.test import Test
from app.models.titul import Titul
from app.models.user import User
from app.services import access
from app.services.excel import export_group_excel, export_test_excel
from app.services.students import get_students_by_group
from app.services.tests import get_tests_by_group
from app.services.titul import generate_tituls_for_test, get_tituls_by_test

OWNER_TG = 990_001
OTHER_TG = 990_002


async def _user(db, telegram_id: int, name: str) -> User:
    user = (
        await db.execute(select(User).where(User.telegram_id == telegram_id))
    ).scalar_one_or_none()
    if user is None:
        user = User(telegram_id=telegram_id, full_name=name)
        db.add(user)
        await db.flush()
    return user


@pytest.mark.asyncio
async def test_tenant_isolation():
    factory = get_session_factory()

    # ── Ma'lumot: A ustozning to'liq zanjiri ──────────────────────────────
    async with factory() as db:
        owner = await _user(db, OWNER_TG, "Access Owner")
        other = await _user(db, OTHER_TG, "Access Other")

        group = Group(owner_id=owner.id, name="Access Test Group")
        db.add(group)
        await db.flush()

        student = Student(group_id=group.id, full_name="Access Student")
        db.add(student)
        await db.flush()

        answer_key = {"1": "A", "2": "B"}
        test = Test(
            group_id=group.id,
            title="Access Test",
            question_count=40,  # CHECK: 40 | 50 | 90
            variant_count=4,
            answer_key=answer_key,
        )
        db.add(test)
        await db.flush()

        titul = Titul(test_id=test.id, student_id=student.id)
        db.add(titul)
        await db.flush()

        attempt = Attempt(
            titul_id=titul.id,
            detected={"1": "A", "2": "C"},
            score=1,
            total=2,
            percent=50.0,
            detail={"1": {"got": "A", "key": "A", "ok": True}, "2": {"got": "C", "key": "B", "ok": False}},
            status="done",
        )
        pending = Attempt(titul_id=None, detected={}, status="pending")
        db.add_all([attempt, pending])
        await db.flush()
        await db.commit()

        owner_id, other_id = owner.id, other.id
        group_id, student_id, test_id = group.id, student.id, test.id
        titul_id, attempt_id, pending_id = titul.id, attempt.id, pending.id

    try:
        # ── Servis qatlami ────────────────────────────────────────────────
        async with factory() as db:
            # Egasi hamma narsani ko'radi
            assert await access.owned_group(db, group_id, owner_id) is not None
            assert await access.owned_test(db, test_id, owner_id) is not None
            assert await access.owned_student(db, student_id, owner_id) is not None
            assert await access.owned_titul(db, titul_id, owner_id) is not None
            owned = await access.owned_attempt(db, attempt_id, owner_id)
            assert owned is not None
            # selectinload zanjiri to'liq — relationship'larga tegish xatosiz
            assert owned.titul.test.group.owner_id == owner_id
            assert owned.titul.student.id == student_id

            # Begona ustoz hech narsa ko'rmaydi
            assert await access.owned_group(db, group_id, other_id) is None
            assert await access.owned_test(db, test_id, other_id) is None
            assert await access.owned_student(db, student_id, other_id) is None
            assert await access.owned_titul(db, titul_id, other_id) is None
            assert await access.owned_attempt(db, attempt_id, other_id) is None

            # Pending (titul_id NULL) skan hech kimga tegishli emas
            assert await access.owned_attempt(db, pending_id, owner_id) is None

            # Servislar owner_id bilan filtrlaydi
            assert len(await get_tests_by_group(db, group_id, owner_id=owner_id)) == 1
            assert await get_tests_by_group(db, group_id, owner_id=other_id) == []
            assert len(await get_students_by_group(db, group_id, owner_id=owner_id)) == 1
            assert await get_students_by_group(db, group_id, owner_id=other_id) == []
            assert len(await get_tituls_by_test(db, test_id, owner_id=owner_id)) == 1
            assert await get_tituls_by_test(db, test_id, owner_id=other_id) == []
            # owner_id=None — tenant'siz (ichki API / admin)
            assert len(await get_tituls_by_test(db, test_id, owner_id=None)) == 1

            # Begona test uchun titul generatsiya qilib bo'lmaydi
            with pytest.raises(ValueError, match="Test topilmadi"):
                await generate_tituls_for_test(db, test_id, owner_id=other_id)

            # Excel: begona uchun faqat sarlavha qatori (ma'lumot yo'q)
            own_xlsx = await export_test_excel(db, test_id, owner_id=owner_id)
            foreign_xlsx = await export_test_excel(db, test_id, owner_id=other_id)
            assert len(own_xlsx) > 0 and len(foreign_xlsx) > 0
            foreign_group_xlsx = await export_group_excel(db, group_id, owner_id=other_id)
            assert len(foreign_group_xlsx) > 0

        # ── Web API (Mini App) ────────────────────────────────────────────
        async with factory() as db:
            owner_user = (
                await db.execute(select(User).where(User.id == owner_id))
            ).scalar_one()
            other_user = (
                await db.execute(select(User).where(User.id == other_id))
            ).scalar_one()

        async def as_other():
            return other_user

        async def as_owner():
            return owner_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Begona → 404 (403 emas: mavjudligini oshkor qilmaymiz)
            app.dependency_overrides[get_webapp_user] = as_other
            for url in (
                f"/api/web/groups/{group_id}",
                f"/api/web/tests/{test_id}",
                f"/api/web/students/{student_id}",
                f"/api/web/attempts/{attempt_id}",
                f"/api/web/attempts/{attempt_id}/file/source",
                f"/api/web/attempts/{attempt_id}/file/debug",
            ):
                resp = await client.get(url)
                assert resp.status_code == 404, f"{url} → {resp.status_code}"

            resp = await client.post(
                f"/api/web/attempts/{attempt_id}/review",
                json={"corrected_answers": {"1": "B", "2": "B"}},
            )
            assert resp.status_code == 404

            resp = await client.get("/api/web/groups")
            assert resp.status_code == 200
            assert all(g["id"] != group_id for g in resp.json())

            resp = await client.get("/api/web/dashboard-stats")
            assert resp.status_code == 200

            # Egasi → ko'radi
            app.dependency_overrides[get_webapp_user] = as_owner
            resp = await client.get(f"/api/web/tests/{test_id}")
            assert resp.status_code == 200
            assert resp.json()["answer_key"] == answer_key

            resp = await client.get(f"/api/web/attempts/{attempt_id}")
            assert resp.status_code == 200
            body = resp.json()
            assert body["student_name"] == "Access Student"
            # Fayl diskda yo'q → URL berilmaydi (404 emas, None)
            assert body["source_url"] is None

            resp = await client.get("/api/web/groups")
            assert any(g["id"] == group_id for g in resp.json())

            resp = await client.get("/api/web/dashboard-stats")
            stats = resp.json()
            assert stats["groups_count"] >= 1
            assert stats["attempts_count"] >= 1

        # Review egasi uchun ishlaydi va begona natijaga tegmagan
        async with factory() as db:
            att = await db.get(Attempt, attempt_id)
            assert att.score == 1  # begonaning review so'rovi o'zgartirmagan

    finally:
        app.dependency_overrides.pop(get_webapp_user, None)

        async with factory() as db:
            for model, obj_id in (
                (Attempt, attempt_id),
                (Attempt, pending_id),
                (Titul, titul_id),
                (Test, test_id),
                (Student, student_id),
                (Group, group_id),
                (User, owner_id),
                (User, other_id),
            ):
                obj = await db.get(model, obj_id)
                if obj is not None:
                    await db.delete(obj)
                    await db.flush()
            await db.commit()
