"""
app/tests/test_admin_security.py — Admin JWT, rol iyerarxiyasi va ichki
API kaliti testlari.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException

from app.api.admin.deps import _ROLE_WEIGHT
from app.api.deps import verify_internal_key
from app.core.config import get_settings
from app.core.security import (
    ALGORITHM,
    InsecureSecretError,
    TokenError,
    assert_internal_key_is_safe,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.models.enums import AdminRole

# `.env` dagi SECRET_KEY namunaviy bo'lishi mumkin va bu holda
# `assert_secret_is_safe()` token berishni ataylab rad etadi. Testlar
# imzolash mantiqini tekshirishi kerak, sozlamani emas — shu sababli
# har bir test uchun kuchli kalit o'rnatamiz.
_STRONG_SECRET = "a" * 64


@pytest.fixture(autouse=True)
def strong_secret():
    settings = get_settings()
    original = settings.secret_key
    settings.secret_key = _STRONG_SECRET
    yield
    settings.secret_key = original


class TestSecretGuard:
    """Namunaviy SECRET_KEY bilan admin tokeni berilmasligi kerak."""

    @pytest.mark.parametrize(
        "weak",
        ["change-me", "change-me-use-a-random-32-char-secret", "qisqa"],
    )
    def test_weak_secret_blocks_token_creation(self, weak):
        settings = get_settings()
        settings.secret_key = weak
        with pytest.raises(InsecureSecretError):
            create_access_token(user_id=1, telegram_id=1, admin_role="SUPERADMIN")

    def test_weak_secret_blocks_token_decoding(self):
        token = create_access_token(user_id=1, telegram_id=1, admin_role="ANALYST")
        get_settings().secret_key = "change-me"
        with pytest.raises(InsecureSecretError):
            decode_token(token, expected_type="access")


class TestTokens:
    def test_access_token_roundtrip(self):
        token = create_access_token(
            user_id=7, telegram_id=123456, admin_role="SUPERADMIN"
        )
        payload = decode_token(token, expected_type="access")
        assert payload.user_id == 7
        assert payload.telegram_id == 123456
        assert payload.admin_role == "SUPERADMIN"
        assert payload.token_type == "access"

    def test_refresh_token_roundtrip(self):
        token = create_refresh_token(user_id=1, telegram_id=1, admin_role="ANALYST")
        payload = decode_token(token, expected_type="refresh")
        assert payload.token_type == "refresh"

    def test_access_token_rejected_where_refresh_expected(self):
        """Access token bilan refresh qilishga urinish rad etilishi kerak."""
        token = create_access_token(user_id=1, telegram_id=1, admin_role="ANALYST")
        with pytest.raises(TokenError, match="turi mos emas"):
            decode_token(token, expected_type="refresh")

    def test_tampered_signature_rejected(self):
        token = create_access_token(user_id=1, telegram_id=1, admin_role="ANALYST")
        forged = jwt.encode(
            {
                "sub": "1",
                "tg": 1,
                "role": "SUPERADMIN",
                "typ": "access",
                "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
            },
            "b" * 64,
            algorithm=ALGORITHM,
        )
        assert forged != token
        with pytest.raises(TokenError):
            decode_token(forged, expected_type="access")

    def test_expired_token_rejected(self):
        expired = jwt.encode(
            {
                "sub": "1",
                "tg": 1,
                "role": "ANALYST",
                "typ": "access",
                "exp": int((datetime.now(timezone.utc) - timedelta(minutes=1)).timestamp()),
            },
            get_settings().secret_key,
            algorithm=ALGORITHM,
        )
        with pytest.raises(TokenError, match="muddati"):
            decode_token(expired, expected_type="access")

    def test_garbage_token_rejected(self):
        with pytest.raises(TokenError):
            decode_token("bu-token-emas", expected_type="access")


class TestInternalKeyGuard:
    """
    `INTERNAL_API_KEY` namunaviy qolsa `/attempts/*` ishlamasligi kerak.

    Nima uchun 503 va 403 emas: kalit noto'g'ri emas — SERVER noto'g'ri
    sozlangan. 403 bo'lsa chaqiruvchi kalitni almashtirib ko'rardi, aslida
    muammo `.env` da.
    """

    @pytest.fixture
    def internal_key(self):
        """Har test o'z kalitini o'rnatadi va keyin asliga qaytaradi."""
        settings = get_settings()
        original = settings.internal_api_key

        def _set(value: str) -> None:
            settings.internal_api_key = value

        yield _set
        settings.internal_api_key = original

    @pytest.mark.parametrize(
        "weak",
        [
            "change-me",
            "change-me-super-secret-internal-key",
            "qisqa-kalit",
        ],
    )
    def test_weak_key_rejected_by_guard(self, internal_key, weak):
        internal_key(weak)
        with pytest.raises(InsecureSecretError):
            assert_internal_key_is_safe()

    def test_strong_key_accepted_by_guard(self, internal_key):
        internal_key("f" * 64)
        assert_internal_key_is_safe()  # istisno ko'tarilmasligi kerak

    async def test_weak_key_returns_503(self, internal_key):
        internal_key("change-me")
        with pytest.raises(HTTPException) as exc_info:
            await verify_internal_key(x_internal_key="change-me")
        assert exc_info.value.status_code == 503

    async def test_wrong_key_returns_403(self, internal_key):
        internal_key("f" * 64)
        with pytest.raises(HTTPException) as exc_info:
            await verify_internal_key(x_internal_key="g" * 64)
        assert exc_info.value.status_code == 403

    async def test_correct_key_passes(self, internal_key):
        internal_key("f" * 64)
        assert await verify_internal_key(x_internal_key="f" * 64) is None


class TestRoleHierarchy:
    def test_every_role_has_a_weight(self):
        assert set(_ROLE_WEIGHT) == set(AdminRole.values())

    def test_hierarchy_is_strictly_ordered(self):
        assert (
            _ROLE_WEIGHT[AdminRole.ANALYST.value]
            < _ROLE_WEIGHT[AdminRole.SUPPORT_OPERATOR.value]
            < _ROLE_WEIGHT[AdminRole.SUPERADMIN.value]
        )

    @pytest.mark.parametrize(
        "actual,required,allowed",
        [
            ("SUPERADMIN", "ANALYST", True),
            ("SUPERADMIN", "SUPERADMIN", True),
            ("SUPPORT_OPERATOR", "ANALYST", True),
            ("SUPPORT_OPERATOR", "SUPERADMIN", False),
            ("ANALYST", "SUPPORT_OPERATOR", False),
            ("", "ANALYST", False),  # roli yo'q foydalanuvchi
        ],
    )
    def test_access_decision(self, actual, required, allowed):
        assert (_ROLE_WEIGHT.get(actual, 0) >= _ROLE_WEIGHT[required]) is allowed
