"""Integration tests for ``dispatch_email`` audit.emit → audit_log row (Plan 42-12 Task 3).

These tests exercise the REAL ``audit.emit`` function without any monkey-patch,
so the real ``EmailSentPayload.model_validate`` / ``EmailSendFailedPayload.model_validate``
Pydantic validation runs. Any regression where ``dispatch_email`` passes the wrong
kwarg shape to ``audit.emit`` (CR-01 class: ``payload=<Model>`` instead of flattened
kwargs) will cause a ``pydantic.ValidationError`` to propagate and these tests will
fail — catching the exact defect that escaped CI through the fake_emit bypass in
the unit tests.

Context (Phase 42 SC#1 / CR-01):
The pre-fix ``dispatch_email.py:160-172/175-188`` called
``audit.emit(... payload=EmailSentPayload(...))``. ``audit.emit``'s signature is
``**payload: Any``, so the collected kwarg dict becomes ``{'payload': <Model>}``.
``EmailSentPayload.model_validate({'payload': <Model>})`` raises ``ValidationError``
(``extra='forbid'`` + 4 missing required fields). Every production ``dispatch_email``
job crashed; no ``email_sent`` audit row ever landed. The unit tests missed this
because they monkey-patch ``audit.emit`` with a ``fake_emit`` that never runs the
real validator.

These integration tests are the regression gate: they MUST NOT monkey-patch
``audit.emit``. They query the ``audit_log`` table via the real DB session to confirm
the row lands after ``dispatch_email`` succeeds, making SC#1 of Phase 42 observable.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import fakeredis.aioredis
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.integrations.email.types import EmailSendResult
from app.workers.tasks.dispatch_email import dispatch_email

# ---------------------------------------------------------------------------
# Test doubles — stub email client only; NO monkey-patch of audit.emit
# ---------------------------------------------------------------------------


class _StubEmailClient:
    """Returns the pre-configured EmailSendResult without calling any provider."""

    def __init__(self, result: EmailSendResult) -> None:
        self._result = result

    async def send_email(self, envelope: Any) -> EmailSendResult:
        return self._result


# ---------------------------------------------------------------------------
# Session factory helpers — wrap db_session in an ARQ-compatible sessionmaker
# ---------------------------------------------------------------------------


class _SessionContext:
    """``async with _SessionContext(session)`` — yields session, swallows exit."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, *args: Any) -> None:
        # Teardown belongs to the outer db_session fixture (SAVEPOINT rollback).
        return None


class _SavepointSessionmaker:
    """ARQ-compatible callable that returns the same SAVEPOINT-wrapped session.

    Mirrors the pattern in tests/integration/workers/conftest.py:worker_ctx so
    the worker's ``async with session_factory() as session`` block uses the same
    connection the test queries directly — required under Postgres READ COMMITTED
    isolation to see the INSERTed rows without a separate COMMIT.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def __call__(self) -> _SessionContext:
        return _SessionContext(self._session)


def _make_envelope_kwargs(audit_correlation_id: UUID) -> dict[str, Any]:
    """Build a minimal valid EmailEnvelope kwargs dict with a known correlation_id."""
    return {
        "to": "intg-test@example.com",
        "subject": "Код входа в Sportzal",
        "html": "<p>Ваш код: <strong>123456</strong></p>",
        "text": "Ваш код: 123456",
        "template_id": "EMAIL_OTP_LOGIN",
        "audit_correlation_id": str(audit_correlation_id),
    }


def _make_ctx(
    *,
    email_client: _StubEmailClient,
    redis: Any,
    session_factory: _SavepointSessionmaker,
) -> dict[str, Any]:
    return {
        "email_client": email_client,
        "redis": redis,
        "sessionmaker": session_factory,
    }


# ---------------------------------------------------------------------------
# Tests — NO monkeypatch of audit.emit (grep "monkeypatch.setattr.*audit.emit"
# in this file should return 0)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_email_success_writes_email_sent_audit_row(
    db_session: AsyncSession,
) -> None:
    """Test 1: ok path — audit_log gains exactly 1 'email_sent' row with the correct payload.

    This test exercises the REAL ``audit.emit`` + ``EmailSentPayload.model_validate``.
    Pre-CR-01-fix code raised ``pydantic.ValidationError`` here and this test would FAIL,
    which is exactly the regression-gate property we want.
    """
    correlation_id = uuid4()
    envelope_kw = _make_envelope_kwargs(correlation_id)

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    client = _StubEmailClient(
        EmailSendResult(
            ok=True,
            classification="ok",
            provider_message_id="msg-INTG-001",
            error=None,
        )
    )
    session_factory = _SavepointSessionmaker(db_session)
    ctx = _make_ctx(email_client=client, redis=redis, session_factory=session_factory)

    result = await dispatch_email(ctx, envelope_kw)

    assert result == "sent"

    # Query the real audit_log table for the email_sent row.
    rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "email_sent",
                    AuditLog.payload["audit_correlation_id"].astext == str(correlation_id),
                )
            )
        )
        .scalars()
        .all()
    )

    assert len(rows) == 1, (
        f"expected exactly 1 email_sent audit row with audit_correlation_id={correlation_id}, "
        f"got {len(rows)}. This failure indicates CR-01 regression or DB rollback."
    )

    row = rows[0]
    # Verify all 4 EmailSentPayload fields landed in JSONB correctly.
    assert row.payload["template_id"] == "EMAIL_OTP_LOGIN", row.payload
    assert row.payload["to_email"] == "intg-test@example.com", row.payload
    assert row.payload["provider_message_id"] == "msg-INTG-001", row.payload
    assert row.payload["audit_correlation_id"] == str(correlation_id), row.payload
    # Verify resource linkage.
    assert row.resource_type == "email_send_log"
    assert row.resource_id is not None


@pytest.mark.asyncio
async def test_dispatch_email_failure_writes_email_send_failed_audit_row(
    db_session: AsyncSession,
) -> None:
    """Test 2: fail path — audit_log gains exactly 1 'email_send_failed' row.

    Exercises the REAL ``audit.emit`` + ``EmailSendFailedPayload.model_validate``.
    Pre-CR-01-fix code raised ``pydantic.ValidationError`` here.
    """
    correlation_id = uuid4()
    envelope_kw = _make_envelope_kwargs(correlation_id)

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    client = _StubEmailClient(
        EmailSendResult(
            ok=False,
            classification="transient_error",
            provider_message_id=None,
            error="HTTP 503",
        )
    )
    session_factory = _SavepointSessionmaker(db_session)
    ctx = _make_ctx(email_client=client, redis=redis, session_factory=session_factory)

    result = await dispatch_email(ctx, envelope_kw)

    assert result == "failed"

    rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "email_send_failed",
                    AuditLog.payload["audit_correlation_id"].astext == str(correlation_id),
                )
            )
        )
        .scalars()
        .all()
    )

    assert len(rows) == 1, (
        f"expected exactly 1 email_send_failed audit row with "
        f"audit_correlation_id={correlation_id}, got {len(rows)}"
    )

    row = rows[0]
    # Verify EmailSendFailedPayload fields landed correctly.
    assert row.payload["reason"] == "provider_5xx", row.payload
    assert row.payload["provider_error_code"] == "HTTP 503", row.payload
    assert row.payload["audit_correlation_id"] == str(correlation_id), row.payload
    assert row.payload["template_id"] == "EMAIL_OTP_LOGIN", row.payload
    assert row.payload["to_email"] == "intg-test@example.com", row.payload
    assert row.resource_type == "email_send_log"
    assert row.resource_id is not None
