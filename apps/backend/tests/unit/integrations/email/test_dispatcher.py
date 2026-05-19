"""Unit tests for ``app.integrations.email.dispatcher`` (Plan 42-08 Task 2).

Covers:
  - ``_resolve_template`` walks the auth.email_templates registry; KeyError on miss
  - ``enqueue_email_dispatch`` renders subject/html/text at enqueue time
  - the rendered envelope kwargs hand off to ``pool.enqueue_job('dispatch_email',
    envelope_kwargs=..., _max_tries=2, _expires=20)`` (LOCKED — D-42-13 per-enqueue
    convention; matches existing project ARQ usage in ``app/workers/__init__.py``)
  - ``_get_arq_pool`` defensive raise until ``register_arq_pool`` runs
  - ``audit_correlation_id=None`` at the Protocol surface still produces a UUID
    on the envelope (uuid4() fallback per the dispatcher's docstring)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from app.integrations.email.dispatcher import (
    _get_arq_pool,
    _resolve_template,
    enqueue_email_dispatch,
    register_arq_pool,
)


# --------------------------------------------------------------------- helpers


class _FakeArqPool:
    """Captures the last ``enqueue_job`` call for assertion."""

    def __init__(self) -> None:
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    async def enqueue_job(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((args, kwargs))
        return None


@pytest.fixture(autouse=True)
def _reset_pool_slot() -> Any:
    """Reset the module-level pool slot between tests to keep them order-independent."""
    import app.integrations.email.dispatcher as disp

    disp._arq_pool = None
    yield
    disp._arq_pool = None


# --------------------------------------------------------------------- _resolve_template


def test_resolve_template_returns_email_otp_login_record() -> None:
    """Test 1: _resolve_template('EMAIL_OTP_LOGIN') returns the auth.email_templates record."""
    tpl = _resolve_template("EMAIL_OTP_LOGIN")
    assert tpl.subject == "Код входа в Sportzal"  # noqa: RUF001 — locked Russian copy
    # Sanity: html + text are Jinja Templates (have .render method).
    assert hasattr(tpl.html, "render")
    assert hasattr(tpl.text, "render")


def test_resolve_template_raises_keyerror_on_unknown_id() -> None:
    """Test 2: unknown template_id surfaces as KeyError at enqueue time."""
    with pytest.raises(KeyError) as exc_info:
        _resolve_template("NONEXISTENT_TEMPLATE")
    assert "NONEXISTENT_TEMPLATE" in str(exc_info.value)


# --------------------------------------------------------------------- pool accessors


def test_get_arq_pool_raises_when_unregistered() -> None:
    """The defensive accessor is a hard failure surface until compose root wires the pool."""
    with pytest.raises(RuntimeError) as exc_info:
        _get_arq_pool()
    assert "ArqRedis pool not registered" in str(exc_info.value)


def test_register_arq_pool_sets_module_slot() -> None:
    """register_arq_pool replaces the module-level slot; idempotent re-register."""
    pool = _FakeArqPool()
    register_arq_pool(pool)  # type: ignore[arg-type]  # FakeArqPool duck-types ArqRedis
    assert _get_arq_pool() is pool


# --------------------------------------------------------------------- enqueue_email_dispatch


@pytest.mark.asyncio
async def test_enqueue_email_dispatch_renders_and_enqueues() -> None:
    """Test 3: rendered envelope is enqueued with _max_tries=2 and _expires=20."""
    pool = _FakeArqPool()
    register_arq_pool(pool)  # type: ignore[arg-type]
    correlation = uuid4()

    await enqueue_email_dispatch(
        template_id="EMAIL_OTP_LOGIN",
        to="user@example.com",
        audit_correlation_id=correlation,
        otp_code="123456",
    )

    assert len(pool.calls) == 1
    args, kwargs = pool.calls[0]
    assert args == ("dispatch_email",)
    assert kwargs["_max_tries"] == 2
    assert kwargs["_expires"] == 20
    env = kwargs["envelope_kwargs"]
    assert env["to"] == "user@example.com"
    assert env["template_id"] == "EMAIL_OTP_LOGIN"
    assert env["subject"] == "Код входа в Sportzal"  # noqa: RUF001 — locked Russian copy
    assert "<strong>123456</strong>" in env["html"]
    assert "Ваш код для входа: 123456" in env["text"]  # noqa: RUF001 — locked Russian copy
    # audit_correlation_id is serialised as str(UUID) for cloudpickle safety.
    assert env["audit_correlation_id"] == str(correlation)


@pytest.mark.asyncio
async def test_enqueue_email_dispatch_synthesises_correlation_id_when_none() -> None:
    """audit_correlation_id=None at the Protocol surface -> uuid4() fallback on the envelope."""
    pool = _FakeArqPool()
    register_arq_pool(pool)  # type: ignore[arg-type]

    await enqueue_email_dispatch(
        template_id="EMAIL_OTP_LOGIN",
        to="user@example.com",
        audit_correlation_id=None,
        otp_code="654321",
    )

    args, kwargs = pool.calls[0]
    env_corr = kwargs["envelope_kwargs"]["audit_correlation_id"]
    # Should be a valid UUID string (uuid4() fallback).
    parsed = UUID(env_corr)
    assert parsed.version == 4


@pytest.mark.asyncio
async def test_enqueue_email_dispatch_raises_when_pool_unregistered() -> None:
    """If compose-root forgot to wire register_arq_pool, the enqueue call must fail loud."""
    # Pool slot is reset by the autouse fixture.
    with pytest.raises(RuntimeError):
        await enqueue_email_dispatch(
            template_id="EMAIL_OTP_LOGIN",
            to="user@example.com",
            audit_correlation_id=None,
            otp_code="123456",
        )
