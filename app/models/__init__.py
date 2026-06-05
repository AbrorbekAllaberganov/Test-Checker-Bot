"""app/models/__init__.py — barcha modellarni eksport qilish (alembic uchun)."""
from app.models.user import User
from app.models.group import Group
from app.models.student import Student
from app.models.test import Test
from app.models.titul import Titul
from app.models.attempt import Attempt

__all__ = ["User", "Group", "Student", "Test", "Titul", "Attempt"]
