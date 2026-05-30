"""Unit tests for QR self-check-in token helpers (Phase 70 D-70-07/D-70-08).

Covers:
- encode_qr_token / decode_qr_token round-trip
- QrTokenClaims fields: sub==client_id, aud=="qr", typ=="qr_checkin", TTL
- decode_qr_token rejects expired token -> "token_expired"
- decode_qr_token rejects an access token (wrong typ) -> "wrong_token_type"
- decode_qr_token rejects a token whose aud != "qr" but typ=="qr_checkin" -> "wrong_audience"
- A QR token is rejected by decode_client_token (isolation check)
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest

from app.core.exceptions import InvalidAccessToken
from app.core.security import (
    QrTokenClaims,
    decode_client_token,
    decode_qr_token,
    encode_client_token,
    encode_qr_token,
)


def test_encode_qr_token_payload_fields() -> None:
    """encode_qr_token returns JWT whose decoded payload has correct sub/aud/typ/TTL."""
    from app.core.config import get_settings

    client_id = uuid4()
    settings = get_settings()
    token = encode_qr_token(client_id)

    # Decode without verification to inspect raw payload.
    raw = jwt.decode(
        token,
        settings.secret_key.get_secret_value(),
        algorithms=["HS256"],
        options={"verify_exp": False, "verify_aud": False},
    )
    assert raw["sub"] == str(client_id)
    assert raw["aud"] == "qr"
    assert raw["typ"] == "qr_checkin"
    # TTL: exp - iat == qr_token_ttl_seconds
    assert raw["exp"] - raw["iat"] == settings.qr_token_ttl_seconds


def test_decode_qr_token_round_trip() -> None:
    """decode_qr_token returns QrTokenClaims with correct sub for a freshly minted token."""
    client_id = uuid4()
    token = encode_qr_token(client_id)
    claims = decode_qr_token(token)
    assert isinstance(claims, QrTokenClaims)
    assert claims.sub == str(client_id)
    assert claims.aud == "qr"
    assert claims.typ == "qr_checkin"


def test_decode_qr_token_rejects_expired() -> None:
    """decode_qr_token raises InvalidAccessToken("token_expired") for a TTL-elapsed token."""
    from app.core.config import get_settings

    settings = get_settings()
    # Mint token issued far in the past — beyond any clock leeway.
    past = datetime.now(tz=UTC) - timedelta(seconds=settings.qr_token_ttl_seconds + 120)
    token = encode_qr_token(uuid4(), now=past)
    with pytest.raises(InvalidAccessToken) as exc_info:
        decode_qr_token(token)
    assert exc_info.value.message == "token_expired"


def test_decode_qr_token_rejects_access_token_wrong_typ() -> None:
    """decode_qr_token raises "wrong_token_type" when given an access token (typ=="access")."""
    client_id = uuid4()
    access_token = encode_client_token(client_id)
    with pytest.raises(InvalidAccessToken) as exc_info:
        decode_qr_token(access_token)
    assert exc_info.value.message == "wrong_token_type"


def test_decode_qr_token_rejects_wrong_audience() -> None:
    """decode_qr_token raises "wrong_audience" for typ=="qr_checkin" but aud != "qr"."""
    from app.core.config import get_settings

    settings = get_settings()
    # Manually mint a token with correct typ but wrong aud.
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": str(uuid4()),
            "aud": "client",  # wrong aud
            "typ": "qr_checkin",
            "iat": now,
            "exp": now + 60,
        },
        settings.secret_key.get_secret_value(),
        algorithm="HS256",
    )
    with pytest.raises(InvalidAccessToken) as exc_info:
        decode_qr_token(token)
    assert exc_info.value.message == "wrong_audience"


def test_qr_token_rejected_by_decode_client_token() -> None:
    """A QR token must NOT validate as a client access token (wrong typ/aud)."""
    client_id = uuid4()
    qr_token = encode_qr_token(client_id)
    with pytest.raises(InvalidAccessToken):
        decode_client_token(qr_token)


def test_access_token_rejected_by_decode_qr_token() -> None:
    """An access token (minted by encode_client_token) must fail decode_qr_token."""
    client_id = uuid4()
    access_token = encode_client_token(client_id)
    with pytest.raises(InvalidAccessToken):
        decode_qr_token(access_token)
