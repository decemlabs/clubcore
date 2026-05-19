"""Unit tests for ``request_otp_email`` symbol surface (Plan 42-09 Task 4).

These tests assert the LOCKED CONSTANTS that anchor the anti-oracle and
single-active invariants but do NOT exercise the DB / Redis / dispatcher
path — that is covered by the integration-tier anti-oracle suite in plan
42-11. Behaviour-level pre-commit assertion here keeps the constants
mypy-strict-tied to the implementation (changing them requires touching
this file).

Behaviors asserted:
  - ``request_otp_email`` exists and is async.
  - ``_EMAIL_OTP_FLOOR_MS`` constant exists and equals 200.
  - ``_EMAIL_DEEP_LINK_PLACEHOLDER_PREFIX`` constant equals
    ``"email-channel:"`` (LOCKED — empty-string placeholder rejected
    because OtpCode.deep_link_token_hash is nullable=False + unique=True).
"""

from __future__ import annotations

import inspect

import pytest


def test_request_otp_email_is_async_function() -> None:
    from app.modules.auth.service import request_otp_email

    assert inspect.iscoroutinefunction(request_otp_email)


def test_email_otp_floor_constant_is_200ms() -> None:
    from app.modules.auth.service import _EMAIL_OTP_FLOOR_MS

    assert _EMAIL_OTP_FLOOR_MS == 200


def test_deep_link_placeholder_prefix_is_locked() -> None:
    from app.modules.auth.service import _EMAIL_DEEP_LINK_PLACEHOLDER_PREFIX

    # LOCKED — the empty-string approach is REJECTED because the column
    # is nullable=False + unique=True (apps/backend/app/modules/auth/models.py:109-113).
    assert _EMAIL_DEEP_LINK_PLACEHOLDER_PREFIX == "email-channel:"


def test_otp_requested_audit_event_is_locked() -> None:
    """Audit event ``("otp_requested", "otp")`` must be in LOCKED_AUDIT_EVENTS
    so ``audit.emit(session, "otp_requested", ...)`` does not raise
    ``AuditEventNotLockedError`` (D-42-35 piggyback)."""
    from app.core.audit import LOCKED_AUDIT_EVENTS

    assert ("otp_requested", "otp") in LOCKED_AUDIT_EVENTS


@pytest.mark.parametrize(
    "ident",
    [
        "_constant_time_floor",
    ],
)
def test_internal_helpers_present(ident: str) -> None:
    """Smoke test — internal helper exists so refactors don't accidentally
    remove the anti-oracle floor enforcement."""
    import app.modules.auth.service as svc

    assert hasattr(svc, ident), f"{ident} missing from app.modules.auth.service"
