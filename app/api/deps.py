"""
app/api/deps.py — FastAPI dependencies.
"""
from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


async def verify_internal_key(x_internal_key: str = Header(...)) -> None:
    """Ichki API key tekshiruvi."""
    if x_internal_key != get_settings().internal_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Noto'g'ri API kalit",
        )
