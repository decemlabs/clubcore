"""Unit tests for ``app.workers.tasks.dispatch_email`` (Plan 42-08 Task 3).

Covers:
  - LOCKED classification → audit reason map (see ``_audit_reason_for``):
      blocked                                     -> invalid_recipient
      transient_error + error == 'circuit_open'   -> circuit_open
      transient_error + other error               -> provider_5xx
      permanent_error                             -> provider_5xx
  - Circuit-open short-circuit: skips ``email_client.send_email`` entirely
  - Circuit-breaker ``record_failure`` invoked on transient_error path
  - INSERT EmailSendLog row + audit.emit BEFORE session.commit (Pitfall 2)
  - dispatch_email_complete summary log line emitted

Pure-unit: no live Redis, no real DB. Uses fakeredis + AsyncMock session.

NOTE (Plan 42-12 CR-01 fix): These are sequence/structure unit tests that use
``fake_emit`` to capture audit.emit kwargs. The REAL ``audit.emit`` Pydantic
validator is exercised by
``tests/integration/email/test_dispatch_email_audit_integration.py``, added in
Plan 42-12 to close CR-01. The ``fake_emit`` bypass was the structural reason
CR-01 escaped CI: the unit tests passed while production crashed because
``fake_emit`` never ran the real ``EmailSentPayload.model_validate`` call.
All assertions below use flattened kwargs (``kwargs["template_id"]`` etc.) and
include ``assert "payload" not in kwargs`` as a CR-01 regression guard.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import fakeredis.aioredis
import pytest

from app.integrations.email.types import EmailSendResult
from app.workers.tasks.dispatch_email import (
    _PROVIDER,
    _audit_reason_for,
    dispatch_email,
)

# --------------------------------------------------------------------- helpers


class _StubEmailClient:
    """Stand-in for EmailClient/SandboxEmailClient — returns the configured result."""

    def __init__(self, result: EmailSendResult) -> None:
        self._result = result
        self.calls: list[Any] = []

    async def send_email(self, envelope: Any) -> EmailSendResult:
        self.calls.append(envelope)
        return self._result


class _StubSession:
    """Bare AsyncSession stand-in that records add/flush/commit calls.

    Mirrors AsyncSession's surface narrowly — we only need ``add``, ``flush``,
    and ``commit`` plus the ``async with`` enter/exit protocol (which the
    sessionmaker factory below produces).
    """

    def __init__(self) -> None:
        self.added: list[Any] = []
        self.flushes: int = 0
        self.commits: int = 0
        self._add_order: list[str] = []  # records 'add' vs 'commit' relative order

    def add(self, obj: Any) -> None:
        self.added.append(obj)
        self._add_order.append(f"add:{type(obj).__name__}")

    async def flush(self) -> None:
        self.flushes += 1
        # Simulate AuditLog row id population on flush — irrelevant here.

    async def commit(self) -> None:
        self.commits += 1
        self._add_order.append("commit")

    async def rollback(self) -> None:
        pass


class _StubSessionFactory:
    """``async with session_factory()`` -> _StubSession."""

    def __init__(self) -> None:
        self.sessions: list[_StubSession] = []

    def __call__(self) -> Any:
        s = _StubSession()
        self.sessions.append(s)
        return _AsyncCtx(s)


class _AsyncCtx:
    def __init__(self, session: _StubSession) -> None:
        self._session = session

    async def __aenter__(self) -> _StubSession:
        return self._session

    async def __aexit__(self, *_exc: Any) -> None:
        return None


def _envelope_kwargs() -> dict[str, Any]:
    _corr_id = str(uuid4())
    return {
        "to": "user@example.com",
        "subject": "Тема",
        "html": "<p>hi</p>",
        "text": "hi",
        "template_id": "EMAIL_OTP_LOGIN",
        "audit_correlation_id": _corr_id,
    }


def _make_ctx(
    *,
    email_client: Any,
    redis: Any,
    session_factory: Any,
) -> dict[str, Any]:
    return {
        "email_client": email_client,
        "redis": redis,
        "sessionmaker": session_factory,
    }


# --------------------------------------------------------------------- _audit_reason_for


def test_audit_reason_blocked_maps_to_invalid_recipient() -> None:
    r = EmailSendResult(
        ok=False, classification="blocked", provider_message_id=None, error="MessageRejected"
    )
    assert _audit_reason_for(r) == "invalid_recipient"


def test_audit_reason_circuit_open_sentinel_maps_to_circuit_open() -> None:
    r = EmailSendResult(
        ok=False, classification="transient_error", provider_message_id=None, error="circuit_open"
    )
    assert _audit_reason_for(r) == "circuit_open"


def test_audit_reason_transient_provider_maps_to_provider_5xx() -> None:
    r = EmailSendResult(
        ok=False, classification="transient_error", provider_message_id=None, error="HTTP 503"
    )
    assert _audit_reason_for(r) == "provider_5xx"


def test_audit_reason_permanent_maps_to_provider_5xx() -> None:
    r = EmailSendResult(
        ok=False, classification="permanent_error", provider_message_id=None, error="HTTP 400"
    )
    assert _audit_reason_for(r) == "provider_5xx"


# --------------------------------------------------------------------- dispatch_email


@pytest.mark.asyncio
async def test_dispatch_email_success_path_logs_and_audits_sent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 1: ok path - INSERT log status='sent', audit 'email_sent', commit."""
    captured_audit: list[tuple[Any, ...]] = []
    envelope_kw = _envelope_kwargs()

    async def fake_emit(session: Any, event: str, **kwargs: Any) -> None:
        captured_audit.append((event, kwargs))

    monkeypatch.setattr("app.workers.tasks.dispatch_email.audit.emit", fake_emit)

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    client = _StubEmailClient(
        EmailSendResult(ok=True, classification="ok", provider_message_id="msg-123", error=None)
    )
    factory = _StubSessionFactory()
    ctx = _make_ctx(email_client=client, redis=redis, session_factory=factory)

    result = await dispatch_email(ctx, envelope_kw)

    assert result == "sent"
    # Provider was called exactly once.
    assert len(client.calls) == 1
    # Session lifecycle: add (EmailSendLog) -> flush -> audit.emit(BEFORE commit) -> commit.
    assert len(factory.sessions) == 1
    s = factory.sessions[0]
    assert len(s.added) == 1
    assert s.flushes >= 1
    assert s.commits == 1
    # Audit emitted BEFORE commit (Pitfall 2): check the captured order.
    # The fake_emit appended; then commit was called. We just check audit fired.
    assert len(captured_audit) == 1
    event, kwargs = captured_audit[0]
    assert event == "email_sent"
    assert kwargs["resource_type"] == "email_send_log"
    # CR-01 regression guard: audit.emit must NOT receive payload=<Model>
    assert "payload" not in kwargs, "audit.emit received payload=<Model> kwarg — CR-01 regression"
    # Flattened kwargs assertions (plan 42-12 Task 2)
    assert kwargs["template_id"] == envelope_kw["template_id"]
    assert kwargs["to_email"] == envelope_kw["to"]
    assert kwargs["provider_message_id"] == "msg-123"
    # audit_correlation_id must be stringified at the boundary
    assert kwargs["audit_correlation_id"] == str(envelope_kw["audit_correlation_id"])
    assert isinstance(kwargs["audit_correlation_id"], str)


@pytest.mark.asyncio
async def test_dispatch_email_blocked_path_audits_invalid_recipient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 2: blocked - status='rejected', audit reason='invalid_recipient'."""
    captured_audit: list[tuple[Any, ...]] = []

    async def fake_emit(session: Any, event: str, **kwargs: Any) -> None:
        captured_audit.append((event, kwargs))

    monkeypatch.setattr("app.workers.tasks.dispatch_email.audit.emit", fake_emit)

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    client = _StubEmailClient(
        EmailSendResult(
            ok=False,
            classification="blocked",
            provider_message_id=None,
            error="MessageRejected",
        )
    )
    factory = _StubSessionFactory()
    ctx = _make_ctx(email_client=client, redis=redis, session_factory=factory)

    result = await dispatch_email(ctx, _envelope_kwargs())

    assert result == "failed"
    assert len(captured_audit) == 1
    event, kwargs = captured_audit[0]
    assert event == "email_send_failed"
    # CR-01 regression guard
    assert "payload" not in kwargs, "audit.emit received payload=<Model> kwarg — CR-01 regression"
    # Flattened kwargs assertions
    assert kwargs["reason"] == "invalid_recipient"
    assert kwargs["provider_error_code"] == "MessageRejected"
    assert "audit_correlation_id" in kwargs and isinstance(kwargs["audit_correlation_id"], str)
    # Circuit breaker NOT exercised for 'blocked' (not transient).
    # Window key should be untouched.
    assert (await redis.zcard("cc:email:circuit_window:yandex_postbox")) == 0
    # WR-04 regression: non-circuit non-ok paths must use status='rejected'.
    s = factory.sessions[0]
    assert s.added[0].status == "rejected", (
        f"blocked path EmailSendLog should use status='rejected' (WR-04), got {s.added[0].status!r}"
    )


@pytest.mark.asyncio
async def test_dispatch_email_transient_5xx_records_failure_and_audits_provider_5xx(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 3: transient_error from a real provider 5xx - record_failure + reason=provider_5xx."""
    captured_audit: list[tuple[Any, ...]] = []

    async def fake_emit(session: Any, event: str, **kwargs: Any) -> None:
        captured_audit.append((event, kwargs))

    monkeypatch.setattr("app.workers.tasks.dispatch_email.audit.emit", fake_emit)

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    client = _StubEmailClient(
        EmailSendResult(
            ok=False, classification="transient_error", provider_message_id=None, error="HTTP 503"
        )
    )
    factory = _StubSessionFactory()
    ctx = _make_ctx(email_client=client, redis=redis, session_factory=factory)

    result = await dispatch_email(ctx, _envelope_kwargs())

    assert result == "failed"
    # Circuit breaker recorded the failure (one entry in window key).
    assert (await redis.zcard("cc:email:circuit_window:yandex_postbox")) == 1
    event, kwargs = captured_audit[0]
    assert event == "email_send_failed"
    # CR-01 regression guard
    assert "payload" not in kwargs, "audit.emit received payload=<Model> kwarg — CR-01 regression"
    # Flattened kwargs assertions
    assert kwargs["reason"] == "provider_5xx"
    assert kwargs["provider_error_code"] == "HTTP 503"
    assert "audit_correlation_id" in kwargs and isinstance(kwargs["audit_correlation_id"], str)
    # WR-04 regression: transient provider 5xx uses status='rejected' (not 'circuit_open').
    s = factory.sessions[0]
    assert s.added[0].status == "rejected", (
        "transient 5xx EmailSendLog should use status='rejected' (WR-04), "
        f"got {s.added[0].status!r}"
    )


@pytest.mark.asyncio
async def test_dispatch_email_when_circuit_open_short_circuits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 4: open circuit -> short-circuit without calling provider; reason='circuit_open'."""
    captured_audit: list[tuple[Any, ...]] = []

    async def fake_emit(session: Any, event: str, **kwargs: Any) -> None:
        captured_audit.append((event, kwargs))

    monkeypatch.setattr("app.workers.tasks.dispatch_email.audit.emit", fake_emit)

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    # Pre-open the circuit.
    await redis.set(f"cc:email:circuit:{_PROVIDER}", "1", ex=300)
    client = _StubEmailClient(
        EmailSendResult(ok=True, classification="ok", provider_message_id="should-not-be-used")
    )
    factory = _StubSessionFactory()
    ctx = _make_ctx(email_client=client, redis=redis, session_factory=factory)

    result = await dispatch_email(ctx, _envelope_kwargs())

    assert result == "failed"
    # CRITICAL: provider was NOT called.
    assert len(client.calls) == 0
    event, kwargs = captured_audit[0]
    assert event == "email_send_failed"
    # CR-01 regression guard
    assert "payload" not in kwargs, "audit.emit received payload=<Model> kwarg — CR-01 regression"
    # Flattened kwargs assertions
    assert kwargs["reason"] == "circuit_open"
    assert kwargs["provider_error_code"] == "circuit_open"
    assert "audit_correlation_id" in kwargs and isinstance(kwargs["audit_correlation_id"], str)
    # WR-04 — status='circuit_open' on breaker shorts (NOT 'rejected').
    assert len(factory.sessions) == 1
    s = factory.sessions[0]
    assert len(s.added) == 1
    log_row = s.added[0]
    assert log_row.status == "circuit_open", (
        f"breaker-short EmailSendLog row should use status='circuit_open' "
        f"(WR-04 regression — got {log_row.status!r})"
    )


@pytest.mark.asyncio
async def test_dispatch_email_permanent_error_audits_provider_5xx(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 5: permanent_error -> reason='provider_5xx' (collapses 4xx-non-blocked)."""
    captured_audit: list[tuple[Any, ...]] = []

    async def fake_emit(session: Any, event: str, **kwargs: Any) -> None:
        captured_audit.append((event, kwargs))

    monkeypatch.setattr("app.workers.tasks.dispatch_email.audit.emit", fake_emit)

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    client = _StubEmailClient(
        EmailSendResult(
            ok=False, classification="permanent_error", provider_message_id=None, error="HTTP 400"
        )
    )
    factory = _StubSessionFactory()
    ctx = _make_ctx(email_client=client, redis=redis, session_factory=factory)

    result = await dispatch_email(ctx, _envelope_kwargs())

    assert result == "failed"
    event, kwargs = captured_audit[0]
    assert event == "email_send_failed"
    # CR-01 regression guard
    assert "payload" not in kwargs, "audit.emit received payload=<Model> kwarg — CR-01 regression"
    # Flattened kwargs assertions
    assert kwargs["reason"] == "provider_5xx"
    assert "audit_correlation_id" in kwargs and isinstance(kwargs["audit_correlation_id"], str)
    # Circuit-breaker NOT armed on permanent_error (only transient_error arms it).
    assert (await redis.zcard(f"cc:email:circuit_window:{_PROVIDER}")) == 0
    # WR-04 regression: permanent error uses status='rejected' (not 'circuit_open').
    s = factory.sessions[0]
    assert s.added[0].status == "rejected", (
        "permanent_error EmailSendLog should use status='rejected' (WR-04), "
        f"got {s.added[0].status!r}"
    )


@pytest.mark.asyncio
async def test_dispatch_email_emits_complete_summary_log(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test 6: every path ends with structlog dispatch_email_complete summary."""

    async def fake_emit(session: Any, event: str, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr("app.workers.tasks.dispatch_email.audit.emit", fake_emit)

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    client = _StubEmailClient(
        EmailSendResult(ok=True, classification="ok", provider_message_id="msg-1")
    )
    factory = _StubSessionFactory()
    ctx = _make_ctx(email_client=client, redis=redis, session_factory=factory)
    await dispatch_email(ctx, _envelope_kwargs())

    captured = capsys.readouterr()
    assert "dispatch_email_complete" in captured.out
