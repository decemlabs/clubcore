"""OtpRequestBody schema tests (Phase 42 Plan 09 Task 3 / AUTH-EM-02 / D-42-22).

The body has two fields:
  - ``channel: Literal['telegram','email']`` default ``'telegram'``
  - ``email: EmailStr | None`` default ``None``

Cross-field invariant: ``channel='email'`` REQUIRES ``email`` to be present.
``Literal`` narrows ``channel`` to the two listed values; any other string
(including the historically reserved ``'whatsapp'``) is rejected by Pydantic
BEFORE the model validator runs.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.auth.schemas import OtpRequestBody


def test_default_channel_is_telegram() -> None:
    body = OtpRequestBody()
    assert body.channel == "telegram"
    assert body.email is None


def test_email_channel_with_email_validates() -> None:
    body = OtpRequestBody(channel="email", email="user@example.com")
    assert body.channel == "email"
    assert body.email == "user@example.com"


def test_email_channel_without_email_raises() -> None:
    with pytest.raises(ValidationError) as exc_info:
        OtpRequestBody(channel="email")
    # Pydantic surfaces model_validator ValueError as a ValidationError.
    assert "email is required" in str(exc_info.value).lower()


def test_unknown_channel_rejected_by_literal() -> None:
    with pytest.raises(ValidationError):
        OtpRequestBody(channel="whatsapp")  # type: ignore[arg-type]


def test_telegram_channel_with_email_is_allowed() -> None:
    # The validator only enforces email-required when channel='email'.
    # A telegram call with an incidental email field is harmless.
    body = OtpRequestBody(channel="telegram", email="user@example.com")
    assert body.channel == "telegram"
    assert body.email == "user@example.com"
