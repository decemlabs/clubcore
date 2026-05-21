"""Unit tests for ``app.integrations.yookassa.settings.YooKassaSettings``.

Plan 47-02 Task 1 — INFRA-36 settings type. Locks:
- 6-field env round-trip with ``env_prefix='YOOKASSA_'``
- ``SecretStr`` redaction lineage (``repr()`` does NOT contain the literal)
- Negative-case ``ValidationError`` on missing/malformed fields

Per D-47-08: standalone ``BaseSettings`` (NOT nested under ``app.core.config.Settings``).
Per D-47-09: every value used here is an obvious placeholder — no real credentials.
"""

from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from app.integrations.yookassa.settings import YooKassaSettings


def _setenv_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Apply a complete, valid placeholder env block for YooKassaSettings."""
    monkeypatch.setenv("YOOKASSA_SHOP_ID", "12345")
    monkeypatch.setenv("YOOKASSA_SECRET_KEY", "test-secret-not-real")
    monkeypatch.setenv("YOOKASSA_RETURN_URL", "https://example.com/return")
    monkeypatch.setenv("YOOKASSA_TAX_SYSTEM_CODE", "2")
    monkeypatch.setenv("YOOKASSA_DEFAULT_VAT_CODE", "1")
    monkeypatch.setenv("YOOKASSA_SANDBOX", "true")


def test_round_trip_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """All 6 fields parse from YOOKASSA_*-prefixed env vars with correct coercion."""
    _setenv_valid(monkeypatch)
    s = YooKassaSettings(_env_file=None)  # type: ignore[call-arg]

    assert s.shop_id == 12345
    assert isinstance(s.secret_key, SecretStr)
    assert s.secret_key.get_secret_value() == "test-secret-not-real"
    assert str(s.return_url) == "https://example.com/return"
    assert s.tax_system_code == 2
    assert s.default_vat_code == 1
    assert s.sandbox is True


def test_secret_key_repr_redaction(monkeypatch: pytest.MonkeyPatch) -> None:
    """SecretStr typing keeps the literal out of ``repr()`` — structlog redaction lineage.

    Confirms T-47-02-01 mitigation: even when an operator accidentally logs the
    settings object, the secret_key value is masked by SecretStr's __repr__.
    """
    _setenv_valid(monkeypatch)
    s = YooKassaSettings(_env_file=None)  # type: ignore[call-arg]

    assert "test-secret-not-real" not in repr(s.secret_key)
    assert "test-secret-not-real" not in repr(s)


def test_sandbox_defaults_false(monkeypatch: pytest.MonkeyPatch) -> None:
    """``sandbox`` defaults to False when YOOKASSA_SANDBOX is unset."""
    monkeypatch.setenv("YOOKASSA_SHOP_ID", "12345")
    monkeypatch.setenv("YOOKASSA_SECRET_KEY", "test-secret-not-real")
    monkeypatch.setenv("YOOKASSA_RETURN_URL", "https://example.com/return")
    monkeypatch.setenv("YOOKASSA_TAX_SYSTEM_CODE", "2")
    monkeypatch.setenv("YOOKASSA_DEFAULT_VAT_CODE", "1")
    monkeypatch.delenv("YOOKASSA_SANDBOX", raising=False)
    s = YooKassaSettings(_env_file=None)  # type: ignore[call-arg]

    assert s.sandbox is False


def test_missing_shop_id_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Omitting YOOKASSA_SHOP_ID surfaces a Pydantic ValidationError."""
    monkeypatch.delenv("YOOKASSA_SHOP_ID", raising=False)
    monkeypatch.setenv("YOOKASSA_SECRET_KEY", "test-secret-not-real")
    monkeypatch.setenv("YOOKASSA_RETURN_URL", "https://example.com/return")
    monkeypatch.setenv("YOOKASSA_TAX_SYSTEM_CODE", "2")
    monkeypatch.setenv("YOOKASSA_DEFAULT_VAT_CODE", "1")
    monkeypatch.setenv("YOOKASSA_SANDBOX", "true")

    with pytest.raises(ValidationError):
        YooKassaSettings(_env_file=None)  # type: ignore[call-arg]


def test_malformed_return_url_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """``YOOKASSA_RETURN_URL=not-a-url`` raises ValidationError (HttpUrl coercion)."""
    monkeypatch.setenv("YOOKASSA_SHOP_ID", "12345")
    monkeypatch.setenv("YOOKASSA_SECRET_KEY", "test-secret-not-real")
    monkeypatch.setenv("YOOKASSA_RETURN_URL", "not-a-url")
    monkeypatch.setenv("YOOKASSA_TAX_SYSTEM_CODE", "2")
    monkeypatch.setenv("YOOKASSA_DEFAULT_VAT_CODE", "1")
    monkeypatch.setenv("YOOKASSA_SANDBOX", "true")

    with pytest.raises(ValidationError):
        YooKassaSettings(_env_file=None)  # type: ignore[call-arg]
