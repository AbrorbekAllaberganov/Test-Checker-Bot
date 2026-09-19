"""
app/tests/test_access.py — Egalik (tenant) izolyatsiyasi testlari.

Ikki ustoz: A o'z guruhi/testi/o'quvchisi/urinishini ko'radi; B esa A ning
obyektlari uchun `None`, bo'sh ro'yxat yoki 404 oladi.

Baza izolyatsiyasi `conftest.py` da (T-35): har test bitta tranzaksiyada,
oxirida rollback — qo'lda tozalash yo'q.
"""
from __future__ import annotations

import pytest

from app.api.main import app
from app.api.routes.auth import get_webapp_user
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
ANSWER_KEY = {"1": "A", "2": "B"}


@pytest.fixture
async def world(db_session):
    """A ustozning to'liq zanjiri + begona ustoz B."""
    db = db_session

    owner = User(telegram_id=OWNER_TG, full_name="Access Owner")
    other = User(telegram_id=OTHER_TG, full_name="Access Other")
    db.add_all([owner, other])
    await db.flush()

    group = Group(owner_id=owner.id, name="Access Test Group")
    db.add(group)
    await db.flush()

    student = Student(group_id=group.id, full_name="Access Student")
    db.add(student)
    await db.flush()

    test = Test(
        group_id=group.id,
        title="Access Test",
        question_count=40,  # CHECK: 40 | 50 | 90
        variant_count=4,
        answer_key=ANSWER_KEY,
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
        detail={
            "1": {"got": "A", "key": "A", "ok": True},
            "2": {"got": "C", "key": "B", "ok": False},
        },
        status="done",
        submitted_by_id=owner.id,
    )
    # QR o'qilmagan skan: `titul_id` NULL, egalik faqat `submitted_by_id` da.
    pending = Attempt(
        titul_id=None, detected={}, status="pending", submitted_by_id=owner.id
    )
    db.add_all([attempt, pending])
    await db.flush()

    return {
        "owner": owner,
        "other": other,
        "owner_id": owner.id,
        "other_id": other.id,
        "group_id": group.id,
        "student_id": student.id,
        "test_id": test.id,
        "titul_id": titul.id,
        "attempt_id": attempt.id,
        "pending_id": pending.id,
    }


# ─── Servis qatlami ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_owner_sees_own_objects(db_session, world):
    db = db_session
    owner_id = world["owner_id"]

    assert await access.owned_group(db, world["group_id"], owner_id) is not None
    assert await access.owned_test(db, world["test_id"], owner_id) is not None
    assert await access.owned_student(db, world["student_id"], owner_id) is not None
    assert await access.owned_titul(db, world["titul_id"], owner_id) is not None

    owned = await access.owned_attempt(db, world["attempt_id"], owner_id)
    assert owned is not None
    # selectinload zanjiri to'liq — relationship'larga tegish xatosiz
    assert owned.titul.test.group.owner_id == owner_id
    assert owned.titul.student.id == world["student_id"]


@pytest.mark.asyncio
async def test_foreign_owner_sees_nothing(db_session, world):
    db = db_session
    other_id = world["other_id"]

    assert await access.owned_group(db, world["group_id"], other_id) is None
    assert await access.owned_test(db, world["test_id"], other_id) is None
    assert await access.owned_student(db, world["student_id"], other_id) is None
    assert await access.owned_titul(db, world["titul_id"], other_id) is None
    assert await access.owned_attempt(db, world["attempt_id"], other_id) is None
    assert await access.owned_attempt(db, world["pending_id"], other_id) is None


@pytest.mark.asyncio
async def test_pending_scan_belongs_to_submitter(db_session, world):
    """
    QR o'qilmagan skan (`titul_id IS NULL`) YUBORUVCHIGA tegishli (T-37).

    Ilgari u hech kimga ko'rinmasdi — aynan eng muammoli skanlar
    ro'yxatdan tushib qolardi.
    """
    pending = await access.owned_attempt(
        db_session, world["pending_id"], world["owner_id"]
    )
    assert pending is not None
    assert pending.titul_id is None


@pytest.mark.asyncio
async def test_services_filter_by_owner(db_session, world):
    db = db_session
    owner_id, other_id = world["owner_id"], world["other_id"]
    group_id, test_id = world["group_id"], world["test_id"]

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
    assert len(await export_group_excel(db, group_id, owner_id=other_id)) > 0


# ─── Web API (Mini App) ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_web_api_foreign_gets_404(api_client, world):
    app.dependency_overrides[get_webapp_user] = lambda: world["other"]
    try:
        for url in (
            f"/api/web/groups/{world['group_id']}",
            f"/api/web/tests/{world['test_id']}",
            f"/api/web/students/{world['student_id']}",
            f"/api/web/attempts/{world['attempt_id']}",
            f"/api/web/attempts/{world['attempt_id']}/file/source",
            f"/api/web/attempts/{world['attempt_id']}/file/debug",
        ):
            resp = await api_client.get(url)
            assert resp.status_code == 404, f"{url} → {resp.status_code}"

        resp = await api_client.post(
            f"/api/web/attempts/{world['attempt_id']}/review",
            json={"corrected_answers": {"1": "B", "2": "B"}},
        )
        assert resp.status_code == 404

        resp = await api_client.get("/api/web/groups")
        assert resp.status_code == 200
        assert all(g["id"] != world["group_id"] for g in resp.json())
    finally:
        app.dependency_overrides.pop(get_webapp_user, None)


@pytest.mark.asyncio
async def test_web_api_foreign_review_does_not_change_score(
    api_client, db_session, world
):
    app.dependency_overrides[get_webapp_user] = lambda: world["other"]
    try:
        await api_client.post(
            f"/api/web/attempts/{world['attempt_id']}/review",
            json={"corrected_answers": {"1": "B", "2": "B"}},
        )
    finally:
        app.dependency_overrides.pop(get_webapp_user, None)

    attempt = await db_session.get(Attempt, world["attempt_id"])
    await db_session.refresh(attempt)
    assert attempt.score == 1


@pytest.mark.asyncio
async def test_web_api_owner_sees_everything(api_client, world):
    app.dependency_overrides[get_webapp_user] = lambda: world["owner"]
    try:
        resp = await api_client.get(f"/api/web/tests/{world['test_id']}")
        assert resp.status_code == 200
        assert resp.json()["answer_key"] == ANSWER_KEY

        resp = await api_client.get(f"/api/web/attempts/{world['attempt_id']}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["student_name"] == "Access Student"
        # Fayl diskda yo'q → URL berilmaydi (404 emas, None)
        assert body["source_url"] is None

        resp = await api_client.get("/api/web/groups")
        assert any(g["id"] == world["group_id"] for g in resp.json())

        resp = await api_client.get("/api/web/dashboard-stats")
        stats = resp.json()
        assert stats["groups_count"] >= 1
        assert stats["attempts_count"] >= 1
    finally:
        app.dependency_overrides.pop(get_webapp_user, None)
