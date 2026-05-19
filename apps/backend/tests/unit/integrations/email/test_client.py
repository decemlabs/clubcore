"""Unit tests for ``app.integrations.email.client``.

Plan 42-07 Task 2: EmailClient adapter + SandboxEmailClient stub.

Locks the classification chain (ok / blocked / transient_error / permanent_error)
that PATTERNS.md §3 derives from the telegram.sender outbound-boundary pattern.
The "never re-raises transport errors" invariant is asserted explicitly so
the ARQ dispatcher (plan 42-08) can rely on EmailSendResult as a value-typed
outcome rather than an exception surface.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from botocore.exceptions import ClientError

from app.integrations.email.client import EmailClient, SandboxEmailClient
from app.integrations.email.types import EmailEnvelope


def _envelope() -> EmailEnvelope:
    return EmailEnvelope(
        to="user@example.com",
        subject="Тема",
        html="<p>hi</p>",
        text="hi-body-text-with-enough-chars-to-preview",
        template_id="EMAIL_OTP_LOGIN",
        audit_correlation_id=uuid4(),
    )


# ---------- SandboxEmailClient ----------------------------------------------


@pytest.mark.asyncio
async def test_sandbox_returns_ok_without_calling_provider() -> None:
    """Test 1: SandboxEmailClient.send_email returns ok with sandbox-<uuid> id."""
    c = SandboxEmailClient()
    r = await c.send_email(_envelope())
    assert r.ok is True
    assert r.classification == "ok"
    assert r.provider_message_id is not None
    assert r.provider_message_id.startswith("sandbox-")
    assert r.error is None


@pytest.mark.asyncio
async def test_sandbox_logs_envelope_at_info(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test 2: SandboxEmailClient logs subject + text preview + to + template_id.

    structlog is configured to render to stdout in this codebase, so we capture
    stdout (not caplog) and assert the envelope's identifying fields appear.
    """
    c = SandboxEmailClient()
    env = _envelope()
    await c.send_email(env)
    captured = capsys.readouterr()
    blob = captured.out + captured.err
    assert env.to in blob
    assert env.subject in blob
    assert env.template_id in blob
    assert env.text[:40] in blob  # text_preview cap is 80 chars; 40 is a safe slice


# ---------- EmailClient classification chain --------------------------------


def _client_error(code: str, http_status: int) -> ClientError:
    return ClientError(
        error_response={
            "Error": {"Code": code, "Message": f"simulated {code}"},
            "ResponseMetadata": {"HTTPStatusCode": http_status},
        },
        operation_name="SendEmail",
    )


class _FakeSesClient:
    def __init__(self, *, send_side_effect: Any = None, send_return: Any = None) -> None:
        self._send_side_effect = send_side_effect
        self._send_return = send_return

    async def __aenter__(self) -> "_FakeSesClient":
        return self

    async def __aexit__(self, *_a: Any) -> None:
        return None

    async def send_email(self, **_kwargs: Any) -> Any:
        if self._send_side_effect is not None:
            raise self._send_side_effect
        return self._send_return


def _make_email_client_with_fake_send(send_outcome: Any) -> EmailClient:
    """Return an EmailClient whose aioboto3 session is patched to a fake."""
    session = MagicMock()
    session.client = MagicMock(return_value=send_outcome)
    return EmailClient(
        session=session,
        endpoint_url="https://postbox.cloud.yandex.net",
        from_address="noreply@mail.sportzal.ru",
    )


@pytest.mark.asyncio
async def test_emailclient_ok_returns_message_id() -> None:
    """Success path: classification='ok', provider_message_id from response."""
    fake = _FakeSesClient(send_return={"MessageId": "msg-abc-123"})
    c = _make_email_client_with_fake_send(fake)
    r = await c.send_email(_envelope())
    assert r.ok is True
    assert r.classification == "ok"
    assert r.provider_message_id == "msg-abc-123"
    assert r.error is None


@pytest.mark.asyncio
async def test_emailclient_message_rejected_is_blocked() -> None:
    """Test 3: ClientError Code=MessageRejected → classification='blocked'."""
    fake = _FakeSesClient(send_side_effect=_client_error("MessageRejected", 400))
    c = _make_email_client_with_fake_send(fake)
    r = await c.send_email(_envelope())
    assert r.ok is False
    assert r.classification == "blocked"
    assert r.error is not None
    assert r.provider_message_id is None


@pytest.mark.asyncio
async def test_emailclient_account_sending_paused_is_blocked() -> None:
    """ClientError Code=AccountSendingPausedException → blocked."""
    fake = _FakeSesClient(
        send_side_effect=_client_error("AccountSendingPausedException", 400)
    )
    c = _make_email_client_with_fake_send(fake)
    r = await c.send_email(_envelope())
    assert r.classification == "blocked"


@pytest.mark.asyncio
async def test_emailclient_5xx_is_transient_error() -> None:
    """Test 4: ClientError with 5xx → classification='transient_error'."""
    fake = _FakeSesClient(send_side_effect=_client_error("InternalFailure", 503))
    c = _make_email_client_with_fake_send(fake)
    r = await c.send_email(_envelope())
    assert r.ok is False
    assert r.classification == "transient_error"
    assert r.error is not None


@pytest.mark.asyncio
async def test_emailclient_4xx_non_blocked_is_permanent_error() -> None:
    """Test 5: ClientError 4xx (non-blocked code) → classification='permanent_error'."""
    fake = _FakeSesClient(send_side_effect=_client_error("InvalidParameterValue", 400))
    c = _make_email_client_with_fake_send(fake)
    r = await c.send_email(_envelope())
    assert r.ok is False
    assert r.classification == "permanent_error"
    assert r.error is not None


@pytest.mark.asyncio
async def test_emailclient_generic_exception_is_transient_error() -> None:
    """Test 6: bare Exception (network/timeout) → classification='transient_error'."""
    fake = _FakeSesClient(send_side_effect=RuntimeError("connection reset"))
    c = _make_email_client_with_fake_send(fake)
    r = await c.send_email(_envelope())
    assert r.ok is False
    assert r.classification == "transient_error"
    assert r.error is not None
    assert "connection reset" in r.error


@pytest.mark.asyncio
async def test_emailclient_never_re_raises() -> None:
    """Test 7: EmailClient.send_email NEVER re-raises (invariant per PATTERNS.md §3)."""

    class WeirdError(BaseException):
        """Even an unusual base exception class should not leak out."""

    fake = _FakeSesClient(send_side_effect=Exception("anything"))
    c = _make_email_client_with_fake_send(fake)
    # Must not raise:
    r = await c.send_email(_envelope())
    assert r.ok is False
    assert r.classification in {"transient_error", "permanent_error", "blocked"}
