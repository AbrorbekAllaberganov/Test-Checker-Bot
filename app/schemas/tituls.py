"""app/schemas/tituls.py"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class TitulOut(BaseModel):
    id: int
    uuid: uuid.UUID
    test_id: int
    student_id: int
    pdf_path: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class TitulGenerateResponse(BaseModel):
    task_ids: list[str]
    count: int
