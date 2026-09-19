"""
app/tests/test_web_api.py — Mini App (Web UI) API integratsiya testlari.

Baza izolyatsiyasi `conftest.py` da: har test bitta tranzaksiyada ishlaydi
va oxirida rollback bo'ladi — qo'lda tozalash kerak emas (T-35).
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


async def _seed(db) -> dict:
    """Bitta ustoz uchun to'liq zanjir: guruh → o'quvchi → test → titul → urinish."""
    user = User(telegram_id=999_999, full_name="Test Teacher")
    db.add(user)
    await db.flush()

    group = Group(owner_id=user.id, name="Test Group 101")
    db.add(group)
    await db.flush()

    student = Student(group_id=group.id, full_name="John Doe", telegram_id=111_111)
    db.add(student)
    await db.flush()

    test = Test(
        group_id=group.id,
        title="Math Test 1",
        question_count=40,  # Constraint: 40, 50 yoki 90
        variant_count=4,
        answer_key={"1": "A", "2": "B", "3": "C", "4": "D"},
    )
    db.add(test)
    await db.flush()

    titul = Titul(test_id=test.id, student_id=student.id)
    db.add(titul)
    await db.flush()

    attempt = Attempt(
        titul_id=titul.id,
        detected={"1": "A", "2": "A", "3": "C", "4": "D"},  # 2-savol xato
        score=3,
        total=4,
        percent=75.0,
        detail={
            "1": {"got": "A", "key": "A", "ok": True},
            "2": {"got": "A", "key": "B", "ok": False},
        },
        needs_review=False,
        status="done",
        submitted_by_id=user.id,
    )
    db.add(attempt)
    await db.flush()

    return {
        "user": user,
        "group_id": group.id,
        "student_id": student.id,
        "test_id": test.id,
        "attempt_id": attempt.id,
    }


@pytest.fixture
async def seeded(db_session):
    """Ma'lumot + Mini App auth override."""
    data = await _seed(db_session)
    app.dependency_overrides[get_webapp_user] = lambda: data["user"]
    try:
        yield data
    finally:
        app.dependency_overrides.pop(get_webapp_user, None)


@pytest.mark.asyncio
async def test_dashboard_stats(api_client, seeded):
    response = await api_client.get("/api/web/dashboard-stats")
    assert response.status_code == 200
    stats = response.json()
    assert stats["groups_count"] == 1
    assert stats["students_count"] == 1
    assert stats["tests_count"] == 1


@pytest.mark.asyncio
async def test_groups_list_and_detail(api_client, seeded):
    response = await api_client.get("/api/web/groups")
    assert response.status_code == 200
    groups_list = response.json()
    assert any(g["id"] == seeded["group_id"] for g in groups_list)

    response = await api_client.get(f"/api/web/groups/{seeded['group_id']}")
    assert response.status_code == 200
    group_data = response.json()
    assert group_data["name"] == "Test Group 101"
    assert len(group_data["students"]) == 1
    assert len(group_data["tests"]) == 1


@pytest.mark.asyncio
async def test_test_and_student_detail(api_client, seeded):
    response = await api_client.get(f"/api/web/tests/{seeded['test_id']}")
    assert response.status_code == 200
    test_data = response.json()
    assert test_data["title"] == "Math Test 1"
    assert len(test_data["results"]) >= 1
    assert len(test_data["item_analysis"]) == 40

    response = await api_client.get(f"/api/web/students/{seeded['student_id']}")
    assert response.status_code == 200
    student_data = response.json()
    assert student_data["full_name"] == "John Doe"
    assert len(student_data["history"]) >= 1


@pytest.mark.asyncio
async def test_attempt_detail(api_client, seeded):
    response = await api_client.get(f"/api/web/attempts/{seeded['attempt_id']}")
    assert response.status_code == 200
    attempt_data = response.json()
    assert attempt_data["student_name"] == "John Doe"
    assert attempt_data["test_title"] == "Math Test 1"


@pytest.mark.asyncio
async def test_review_recalculates_and_marks_override(api_client, db_session, seeded):
    """
    Qo'lda tuzatish: faqat O'ZGARGAN savol yuboriladi, ball qayta hisoblanadi
    va `manual_override` belgilanadi (T-27).
    """
    response = await api_client.post(
        f"/api/web/attempts/{seeded['attempt_id']}/review",
        json={"corrected_answers": {"2": "B"}},
    )
    assert response.status_code == 200
    review_data = response.json()
    assert review_data["success"] is True
    assert review_data["score"] == 4
    assert float(review_data["percent"]) == 100.0
    assert review_data["needs_review"] is False

    attempt = await db_session.get(Attempt, seeded["attempt_id"])
    await db_session.refresh(attempt)
    assert attempt.manual_override is True
    assert attempt.reviewed_by_id == seeded["user"].id
    assert attempt.reviewed_at is not None
    # Yuborilmagan savollar eski qiymatida qoldi.
    assert attempt.detected["1"] == "A"


@pytest.mark.asyncio
async def test_review_rejects_invalid_letter(api_client, seeded):
    """Noto'g'ri harf 422 beradi — ilgari indamay `detail` ga yozilardi."""
    response = await api_client.post(
        f"/api/web/attempts/{seeded['attempt_id']}/review",
        json={"corrected_answers": {"2": "Z"}},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_review_rejects_unknown_question(api_client, seeded):
    response = await api_client.post(
        f"/api/web/attempts/{seeded['attempt_id']}/review",
        json={"corrected_answers": {"999": "A"}},
    )
    assert response.status_code == 422
