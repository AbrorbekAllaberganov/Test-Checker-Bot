"""
app/services/groups.py — Guruh CRUD servisi.
Bot ham, API ham shu funksiyalardan foydalanadi.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.group import Group
from app.models.user import User


async def get_or_create_user(
    db: AsyncSession,
    telegram_id: int,
    full_name: Optional[str] = None,
    username: Optional[str] = None,
) -> User:
    """Telegram ID bo'yicha foydalanuvchi olish yoki yaratish."""
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(telegram_id=telegram_id, full_name=full_name, username=username)
        db.add(user)
        await db.flush()

    return user


async def create_group(db: AsyncSession, owner_id: int, name: str) -> Group:
    """Yangi guruh yaratish."""
    group = Group(owner_id=owner_id, name=name)
    db.add(group)
    await db.flush()
    await db.refresh(group)
    return group


async def get_groups_by_owner(db: AsyncSession, owner_id: int) -> list[Group]:
    """Ustoz guruhlarini olish."""
    result = await db.execute(
        select(Group).where(Group.owner_id == owner_id).order_by(Group.created_at.desc())
    )
    return list(result.scalars().all())


async def get_group(db: AsyncSession, group_id: int) -> Optional[Group]:
    """Guruhni ID bo'yicha olish."""
    result = await db.execute(select(Group).where(Group.id == group_id))
    return result.scalar_one_or_none()


async def get_group_for_owner(
    db: AsyncSession, group_id: int, owner_id: int
) -> Optional[Group]:
    """Faqat o'z guruhini olish (xavfsizlik)."""
    result = await db.execute(
        select(Group).where(Group.id == group_id, Group.owner_id == owner_id)
    )
    return result.scalar_one_or_none()


async def delete_group(db: AsyncSession, group_id: int, owner_id: int) -> bool:
    """Guruhni o'chirish (faqat egasi)."""
    group = await get_group_for_owner(db, group_id, owner_id)
    if group is None:
        return False
    await db.delete(group)
    await db.flush()
    return True
