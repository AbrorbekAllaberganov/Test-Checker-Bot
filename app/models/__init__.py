"""app/models/__init__.py — barcha modellarni eksport qilish (alembic uchun)."""
from app.models.user import User
from app.models.group import Group
from app.models.student import Student
from app.models.test import Test
from app.models.titul import Titul
from app.models.attempt import Attempt

# ── SaaS / Admin panel (003) ────────────────────────────────────────────
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.audit_log import AuditLog
from app.models.broadcast import Broadcast, BroadcastRecipient

__all__ = [
    "User",
    "Group",
    "Student",
    "Test",
    "Titul",
    "Attempt",
    "Plan",
    "Subscription",
    "AuditLog",
    "Broadcast",
    "BroadcastRecipient",
]
