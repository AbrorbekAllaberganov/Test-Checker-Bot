"""
app/schemas/admin/audit.py — Audit jurnali sxemasi.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class AuditLogItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_id: Optional[int] = None
    actor_label: str
    action: str
    object_type: Optional[str] = None
    object_id: Optional[str] = None
    payload: Optional[dict[str, Any]] = None
    ip_address: Optional[str] = None
    created_at: datetime
