"""
app/tests/test_admin_explorer.py — Admin explorer drill-down endpointlari.

Asosiy tekshiruv: `GET /api/admin/students/{id}` o'quvchi ishlagan
testlarni qaytaradi va skanlanmagan varaq ham ro'yxatdan tushib qolmaydi.

Baza izolyatsiyasi `conftest.py` da (T-35).
"""
from __future__ import annotations

import pytest

from app.api.admin.deps import get_current_admin
from app.api.main import app
from app.models.attempt import Attempt
from app.models.enums import AdminRole
from app.models.group import Group
from app.models.student import Student
from app.models.test import Test
from app.models.titul import Titul
from app.models.user import User


@pytest.fixture
async def explorer_world(db_session):
    db = db_session

    user = User(telegram_id=888_888, full_name="Explorer Teacher")
    db.add(user)
    await db.flush()

    group = Group(owner_id=user.id, name="Explorer Group")
    db.add(group)
    await db.flush()

    student = Student(group_id=group.id, full_name="Ali Valiyev")
    db.add(student)
    await db.flush()

    key = {str(i): "ABCD"[(i - 1) % 4] for i in range(1, 41)}
    graded_test = Test(
        group_id=group.id,
        title="Baholangan test",
        question_count=40,
        variant_count=4,
        answer_key=key,
    )
    # Varaq chiqarilgan, lekin hali skanlanmagan test.
    pending_test = Test(
        group_id=group.id,
        title="Skanlanmagan test",
        question_count=40,
        variant_count=4,
        answer_key=key,
    )
    db.add_all([graded_test, pending_test])
    await db.flush()

    graded_titul = Titul(test_id=graded_test.id, student_id=student.id)
    pending_titul = Titul(test_id=pending_test.id, student_id=student.id)
    db.add_all([graded_titul, pending_titul])
    await db.flush()

    attempt = Attempt(
        titul_id=graded_titul.id,
        detected=dict(key),
        score=32,
        total=40,
        percent=80.0,
        detail={},
        status="done",
        submitted_by_id=user.id,
    )
    db.add(attempt)
    await db.flush()

    # Admin roli BAZADAN o'qiladi — testda token yasamay, dependency'ni
    # to'g'ridan-to'g'ri almashtiramiz.
    admin = User(
        id=user.id,
        telegram_id=user.telegram_id,
        full_name=user.full_name,
        admin_role=AdminRole.ANALYST.value,
    )
    app.dependency_overrides[get_current_admin] = lambda: admin
    try:
        yield {
            "group_id": group.id,
            "student_id": student.id,
            "graded_test_id": graded_test.id,
            "pending_test_id": pending_test.id,
            "attempt_id": attempt.id,
        }
    finally:
        app.dependency_overrides.pop(get_current_admin, None)


@pytest.mark.asyncio
async def test_group_detail(api_client, explorer_world):
    response = await api_client.get(f"/api/admin/groups/{explorer_world['group_id']}")
    assert response.status_code == 200
    group_data = response.json()
    assert any(s["id"] == explorer_world["student_id"] for s in group_data["students"])
    assert {t["id"] for t in group_data["tests"]} == {
        explorer_world["graded_test_id"],
        explorer_world["pending_test_id"],
    }


@pytest.mark.asyncio
async def test_student_detail_drill_down(api_client, explorer_world):
    response = await api_client.get(
        f"/api/admin/students/{explorer_world['student_id']}"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Ali Valiyev"
    assert data["group_name"] == "Explorer Group"
    assert data["tituls_count"] == 2
    assert data["attempts_count"] == 1
    assert data["avg_percent"] == 80.0

    rows = {row["test_id"]: row for row in data["attempts"]}
    assert rows[explorer_world["graded_test_id"]]["attempt_id"] == (
        explorer_world["attempt_id"]
    )
    assert rows[explorer_world["graded_test_id"]]["percent"] == 80.0
    # Skanlanmagan varaq ham ko'rinishi shart.
    assert rows[explorer_world["pending_test_id"]]["attempt_id"] is None
    assert rows[explorer_world["pending_test_id"]]["status"] is None


@pytest.mark.asyncio
async def test_unknown_student_404(api_client, explorer_world):
    response = await api_client.get("/api/admin/students/99999999")
    assert response.status_code == 404
