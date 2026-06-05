"""
app/tests/test_web_api.py — Unit tests for the Web UI API endpoints.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.main import app
from app.core.db import get_session_factory
from app.models.user import User
from app.models.group import Group
from app.models.student import Student
from app.models.test import Test
from app.models.titul import Titul
from app.models.attempt import Attempt


@pytest.mark.asyncio
async def test_web_ui_endpoints():
    """Tizimning barcha Web UI endpointlarini integratsiya testi."""
    factory = get_session_factory()
    
    # 1. Test ma'lumotlarini yaratish
    async with factory() as db:
        # User (Guruh egasi uchun)
        user_res = await db.execute(select(User).limit(1))
        user = user_res.scalar_one_or_none()
        if not user:
            user = User(telegram_id=999999, full_name="Test Teacher")
            db.add(user)
            await db.flush()

        # Guruh
        group = Group(owner_id=user.id, name="Test Group 101")
        db.add(group)
        await db.flush()

        # O'quvchi
        student = Student(group_id=group.id, full_name="John Doe", telegram_id=111111)
        db.add(student)
        await db.flush()

        # Test
        test_key = {"1": "A", "2": "B", "3": "C", "4": "D"}
        test = Test(
            group_id=group.id,
            title="Math Test 1",
            question_count=40,  # Constraint: must be 40, 50, or 90
            variant_count=4,
            answer_key=test_key
        )
        db.add(test)
        await db.flush()

        # Titul
        titul = Titul(test_id=test.id, student_id=student.id)
        db.add(titul)
        await db.flush()

        # Urinish (Attempt)
        attempt = Attempt(
            titul_id=titul.id,
            detected={"1": "A", "2": "A", "3": "C", "4": "D"}, # 1 wrong
            score=3,
            total=4,
            percent=75.0,
            detail={"1": {"got": "A", "key": "A", "ok": True}, "2": {"got": "A", "key": "B", "ok": False}},
            needs_review=False,
            status="done"
        )
        db.add(attempt)
        await db.commit()

        # IDlarni saqlash
        group_id = group.id
        student_id = student.id
        test_id = test.id
        attempt_id = attempt.id

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 2. GET /api/web/dashboard-stats
            response = await ac.get("/api/web/dashboard-stats")
            assert response.status_code == 200
            stats = response.json()
            assert stats["groups_count"] >= 1
            assert stats["students_count"] >= 1

            # 3. GET /api/web/groups
            response = await ac.get("/api/web/groups")
            assert response.status_code == 200
            groups_list = response.json()
            assert len(groups_list) >= 1
            assert any(g["id"] == group_id for g in groups_list)

            # 4. GET /api/web/groups/{id}
            response = await ac.get(f"/api/web/groups/{group_id}")
            assert response.status_code == 200
            group_data = response.json()
            assert group_data["name"] == "Test Group 101"
            assert len(group_data["students"]) >= 1
            assert len(group_data["tests"]) >= 1

            # 5. GET /api/web/tests/{id}
            response = await ac.get(f"/api/web/tests/{test_id}")
            assert response.status_code == 200
            test_data = response.json()
            assert test_data["title"] == "Math Test 1"
            assert len(test_data["results"]) >= 1
            assert len(test_data["item_analysis"]) == 40  # 40 ta savol uchun

            # 6. GET /api/web/students/{id}
            response = await ac.get(f"/api/web/students/{student_id}")
            assert response.status_code == 200
            student_data = response.json()
            assert student_data["full_name"] == "John Doe"
            assert len(student_data["history"]) >= 1

            # 7. GET /api/web/attempts/{id}
            response = await ac.get(f"/api/web/attempts/{attempt_id}")
            assert response.status_code == 200
            attempt_data = response.json()
            assert attempt_data["student_name"] == "John Doe"
            assert attempt_data["test_title"] == "Math Test 1"

            # 8. POST /api/web/attempts/{id}/review (Qayta baholash testi)
            response = await ac.post(
                f"/api/web/attempts/{attempt_id}/review",
                json={"corrected_answers": {"1": "A", "2": "B", "3": "C", "4": "D"}} # 100% to'g'ri
            )
            assert response.status_code == 200
            review_data = response.json()
            assert review_data["success"] is True
            assert review_data["score"] == 4
            assert review_data["percent"] == 100.0
            assert review_data["needs_review"] is False

    finally:
        # 9. Test ma'lumotlarini bazadan o'chirish (Tozalash)
        async with factory() as db:
            att_obj = await db.get(Attempt, attempt_id)
            if att_obj:
                await db.delete(att_obj)
            tit_obj = await db.get(Titul, titul.id)
            if tit_obj:
                await db.delete(tit_obj)
            test_obj = await db.get(Test, test_id)
            if test_obj:
                await db.delete(test_obj)
            stu_obj = await db.get(Student, student_id)
            if stu_obj:
                await db.delete(stu_obj)
            grp_obj = await db.get(Group, group_id)
            if grp_obj:
                await db.delete(grp_obj)
            await db.commit()
