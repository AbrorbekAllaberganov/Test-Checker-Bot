"""
app/api/admin/deps.py — Admin API dependency'lari: JWT auth, RBAC, sahifalash.

Rollar iyerarxiyasi (yuqoridagi pastdagining hamma huquqiga ega):

    SUPERADMIN        — hamma narsa (tarif, rol, tarif yaratish)
    SUPPORT_OPERATOR  — bloklash, qo'lda tuzatish, e'lon yuborish
    ANALYST           — faqat o'qish

Foydalanish:

    @router.get("/users", dependencies=[Depends(require_analyst)])
    async def list_users(...): ...

    @router.post("/users/{id}/block")
    async def block(admin: User = Depends(require_support)): ...
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import InsecureSecretError, TokenError, decode_token
from app.models.enums import AdminRole
from app.models.user import User
from app.services import token_store

log = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(auto_error=False, description="Admin JWT access token")

# Rol og'irligi — kattasi ko'proq huquqqa ega.
_ROLE_WEIGHT: dict[str, int] = {
    AdminRole.ANALYST.value: 10,
    AdminRole.SUPPORT_OPERATOR.value: 20,
    AdminRole.SUPERADMIN.value: 30,
}


async def get_current_admin(
    request: Request,
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)
    ] = None,
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    `Authorization: Bearer <access_token>` → User.

    Token yaroqsiz, foydalanuvchi o'chirilgan, bloklangan yoki admin roli
    olib qo'yilgan bo'lsa — 401/403. Rol tokendan emas, BAZADAN o'qiladi:
    shunda rol bekor qilinishi darhol kuchga kiradi va eski token bilan
    ish ko'rib bo'lmaydi.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Avtorizatsiya talab qilinadi",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(credentials.credentials, expected_type="access")
    except InsecureSecretError as exc:
        # Sozlama xatosi — foydalanuvchi aybi emas, shu sababli 503.
        log.error("Admin panel ishga tushmadi: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    # Bekor qilingan token (logout yoki o'g'irlangan sessiya) — T-30.
    redis = token_store.redis_client()
    try:
        revoked = await token_store.is_revoked(
            redis, jti=payload.jti, family=payload.family
        )
    finally:
        await redis.aclose()
    if revoked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessiya yakunlangan — qaytadan kiring",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = (
        await db.execute(select(User).where(User.id == payload.user_id))
    ).scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Foydalanuvchi topilmadi",
        )
    if user.is_blocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hisobingiz bloklangan",
        )
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin panelga kirish huquqi yo'q",
        )

    # Keyingi dependency'lar (audit) uchun saqlab qo'yamiz.
    request.state.admin = user
    return user


def admin_required(minimum: AdminRole):
    """
    Minimal rol darajasini talab qiluvchi dependency fabrikasi.

        admin: User = Depends(admin_required(AdminRole.SUPERADMIN))
    """
    required_weight = _ROLE_WEIGHT[minimum.value]

    async def _dep(admin: User = Depends(get_current_admin)) -> User:
        if _ROLE_WEIGHT.get(admin.admin_role or "", 0) < required_weight:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Bu amal uchun kamida '{minimum.value}' roli kerak "
                    f"(sizda: '{admin.admin_role}')"
                ),
            )
        return admin

    return _dep


# Tayyor dependency'lar — router'larda qayta-qayta yozmaslik uchun.
require_analyst = admin_required(AdminRole.ANALYST)
require_support = admin_required(AdminRole.SUPPORT_OPERATOR)
require_superadmin = admin_required(AdminRole.SUPERADMIN)


@dataclass(frozen=True)
class Pagination:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


async def pagination_params(
    page: int = Query(1, ge=1, description="Sahifa raqami (1 dan)"),
    page_size: int = Query(25, ge=1, le=200, description="Sahifadagi qatorlar soni"),
) -> Pagination:
    return Pagination(page=page, page_size=page_size)


PaginationDep = Annotated[Pagination, Depends(pagination_params)]
AdminDep = Annotated[User, Depends(get_current_admin)]
DbDep = Annotated[AsyncSession, Depends(get_db)]
