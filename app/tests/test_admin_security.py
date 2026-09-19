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


class FakeRedis:
    """
    Minimal in-memory Redis — `token_store` uchun yetarli.

    Haqiqiy Redis'siz bekor qilish mantiqini sinash uchun (TTL e'tiborga
    olinmaydi: testlar bir zumda tugaydi).
    """

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.store[key] = value

    async def mget(self, keys):
        return [self.store.get(k) for k in keys]

    async def incr(self, key: str) -> int:
        value = int(self.store.get(key, "0")) + 1
        self.store[key] = str(value)
        return value

    async def expire(self, key: str, ttl: int) -> None:
        return None

    async def aclose(self) -> None:
        return None


class TestTokenRevocation:
    """
    T-30: refresh rotatsiyasi va logout.

    Ilgari eski refresh token bekor qilinmasdi va logout umuman yo'q edi —
    sizib chiqqan token 14 kun ishlardi (weaknesses.md №19).
    """

    async def test_family_claim_survives_rotation(self):
        from app.core.security import new_family_id

        family = new_family_id()
        access = create_access_token(
            user_id=1, telegram_id=1, admin_role="ANALYST", family=family
        )
        refresh = create_refresh_token(
            user_id=1, telegram_id=1, admin_role="ANALYST", family=family
        )
        assert decode_token(access, expected_type="access").family == family
        assert decode_token(refresh, expected_type="refresh").family == family

    async def test_revoked_jti_is_detected(self):
        from app.services import token_store

        redis = FakeRedis()
        token = create_refresh_token(user_id=1, telegram_id=1, admin_role="ANALYST")
        payload = decode_token(token, expected_type="refresh")

        assert await token_store.is_revoked(redis, jti=payload.jti) is False
        await token_store.revoke_jti(
            redis, payload.jti, int(payload.expires_at.timestamp())
        )
        assert await token_store.is_revoked(redis, jti=payload.jti) is True

    async def test_revoked_family_blocks_all_tokens(self):
        from app.core.security import new_family_id
        from app.services import token_store

        redis = FakeRedis()
        family = new_family_id()
        token = create_access_token(
            user_id=1, telegram_id=1, admin_role="ANALYST", family=family
        )
        payload = decode_token(token, expected_type="access")

        await token_store.revoke_family(redis, family)
        # jti bekor qilinmagan bo'lsa ham oila bo'yicha rad etiladi
        assert await token_store.is_revoked(redis, jti=payload.jti, family=family) is True

    async def test_rate_limit_blocks_after_limit(self):
        from app.services import token_store

        redis = FakeRedis()
        for _ in range(3):
            assert await token_store.rate_limit(
                redis, name="t", ident="1.2.3.4", limit=3, window_seconds=60
            ) is True
        assert await token_store.rate_limit(
            redis, name="t", ident="1.2.3.4", limit=3, window_seconds=60
        ) is False
        # Boshqa IP mustaqil
        assert await token_store.rate_limit(
            redis, name="t", ident="5.6.7.8", limit=3, window_seconds=60
        ) is True


class TestInitDataExpiry:
    """T-28: tutib olingan `initData` abadiy ishlamasligi kerak."""

    @staticmethod
    def _signed_init_data(auth_date: int) -> str:
        import hashlib
        import hmac as hmac_mod
        import json
        from urllib.parse import urlencode

        fields = {
            "auth_date": str(auth_date),
            "user": json.dumps({"id": 42, "first_name": "Test"}),
        }
        data_check = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
        secret = hmac_mod.new(
            b"WebAppData", get_settings().bot_token.encode(), hashlib.sha256
        ).digest()
        fields["hash"] = hmac_mod.new(
            secret, data_check.encode(), hashlib.sha256
        ).hexdigest()
        return urlencode(fields)

    def test_fresh_init_data_accepted(self):
        import time

        from app.api.routes.auth import validate_init_data

        user = validate_init_data(self._signed_init_data(int(time.time())), max_age=300)
        assert user["id"] == 42

    def test_stale_init_data_rejected(self):
        import time

        from app.api.routes.auth import validate_init_data

        stale = self._signed_init_data(int(time.time()) - 3600)
        with pytest.raises(ValueError, match="muddati"):
            validate_init_data(stale, max_age=300)

    def test_missing_auth_date_rejected(self):
        import hashlib
        import hmac as hmac_mod
        import json
        from urllib.parse import urlencode

        from app.api.routes.auth import validate_init_data

        fields = {"user": json.dumps({"id": 42})}
        data_check = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
        secret = hmac_mod.new(
            b"WebAppData", get_settings().bot_token.encode(), hashlib.sha256
        ).digest()
        fields["hash"] = hmac_mod.new(
            secret, data_check.encode(), hashlib.sha256
        ).hexdigest()

        with pytest.raises(ValueError, match="auth_date"):
            validate_init_data(urlencode(fields), max_age=300)
