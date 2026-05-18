"""AST walker for audit.emit callsites — TESTS-09 / D-11 / D-12 (Phase 15).

Static analysis: walks every `audit.emit(...)` call in apps/backend/app/**/*.py
and asserts (1) both `event` and `resource_type` args are literal strings,
(2) the (event, resource_type) pair is in `LOCKED_AUDIT_EVENTS`.

Catches typos (`memberhsip_created`) and dynamic event names BEFORE they reach
a runtime path. Pure unit-level — no DB.

The walker recognises three callsite shapes:
  - `audit.emit(session, "event", ..., resource_type="x")`            (Name(audit))
  - `<x>.audit.emit(session, "event", ..., resource_type="x")`        (Attribute.audit)
  - `audit_emit(session, "event", ..., resource_type="x")`            (rebound name)

The third form is used by `app/integrations/telegram/handlers.py` which imports
`from app.core.audit import emit as audit_emit` (the only rebinding in the
codebase as of Phase 15).
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import LOCKED_AUDIT_EVENTS, AuditEventNotLockedError, emit

# parents[0]=unit, [1]=tests, [2]=backend, [3]=apps, [4]=repo root.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_BACKEND_APP = _REPO_ROOT / "apps" / "backend" / "app"


def _is_audit_emit_call(node: ast.Call) -> bool:
    """True if `node` is `audit.emit(...)`, `<x>.audit.emit(...)`, or `audit_emit(...)`."""
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr == "emit":
        value = func.value
        if isinstance(value, ast.Name) and value.id == "audit":
            return True
        return isinstance(value, ast.Attribute) and value.attr == "audit"
    # Rebound import: `from app.core.audit import emit as audit_emit`
    return isinstance(func, ast.Name) and func.id == "audit_emit"


def _resolve_str_literal(node: ast.expr | None) -> str | None:
    """Return the literal str value if `node` is `ast.Constant(str)`, else None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _extract_event_and_resource_type(
    call: ast.Call,
) -> tuple[ast.expr | None, ast.expr | None]:
    """Return (event_arg, resource_type_arg) AST nodes — None if not present.

    Signature: `emit(session, event, *, actor_user_id, resource_type, ...)`.
    `event` is positional[1] (positional[0] is `session`) or kw `event`.
    `resource_type` is keyword-only.
    """
    event_node: ast.expr | None = None
    if len(call.args) >= 2:
        event_node = call.args[1]
    for kw in call.keywords:
        if kw.arg == "event":
            event_node = kw.value
    resource_type_node: ast.expr | None = None
    for kw in call.keywords:
        if kw.arg == "resource_type":
            resource_type_node = kw.value
    return event_node, resource_type_node


def _iter_audit_emit_calls(
    module_root: Path,
) -> Iterator[tuple[Path, int, ast.expr | None, ast.expr | None]]:
    """Yield (file, lineno, event_arg, resource_type_arg) for every audit.emit
    callsite under module_root.

    The audit module itself (`app/core/audit.py`) is excluded — that is where
    `LOCKED_AUDIT_EVENTS` lives, and any forward references to event names in
    its docstring or guard error message would be false positives.
    """
    audit_module = module_root / "core" / "audit.py"
    for py in sorted(module_root.rglob("*.py")):
        if py.resolve() == audit_module.resolve():
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        except SyntaxError as exc:  # pragma: no cover — defensive
            pytest.fail(f"Could not parse {py}: {exc}")
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not _is_audit_emit_call(node):
                continue
            event_node, resource_type_node = _extract_event_and_resource_type(node)
            yield py, node.lineno, event_node, resource_type_node


def test_every_audit_emit_uses_literal_strings() -> None:
    """D-11 step 3: f-strings / variables are forbidden for `event` and `resource_type`.

    The static gate cannot prove staticness if the args are dynamic, so the
    contract requires literals at every callsite. Helpers that wrap `audit.emit`
    with computed names are not permitted.
    """
    offenders: list[str] = []
    for path, lineno, event_node, resource_type_node in _iter_audit_emit_calls(_BACKEND_APP):
        if event_node is None:
            offenders.append(
                f"{path.relative_to(_REPO_ROOT)}:{lineno} — missing `event` arg"
            )
            continue
        if resource_type_node is None:
            offenders.append(
                f"{path.relative_to(_REPO_ROOT)}:{lineno} — missing `resource_type` kwarg"
            )
            continue
        if _resolve_str_literal(event_node) is None:
            offenders.append(
                f"{path.relative_to(_REPO_ROOT)}:{lineno} — `event` is not a literal str "
                f"(got {ast.dump(event_node)})"
            )
        if _resolve_str_literal(resource_type_node) is None:
            offenders.append(
                f"{path.relative_to(_REPO_ROOT)}:{lineno} — `resource_type` is not a literal str "
                f"(got {ast.dump(resource_type_node)})"
            )
    assert not offenders, (
        "audit.emit() must be called with literal `event` and `resource_type` strings.\n"
        "Offenders:\n  " + "\n  ".join(offenders)
    )


def test_every_audit_emit_pair_is_in_locked_set() -> None:
    """D-11 step 4: every (event, resource_type) pair MUST be in LOCKED_AUDIT_EVENTS.

    Catches the Phase 17 typo case `audit.emit("memberhsip_created", ...)` BEFORE
    the bug reaches a runtime path.
    """
    unlocked: list[str] = []
    for path, lineno, event_node, resource_type_node in _iter_audit_emit_calls(_BACKEND_APP):
        event = _resolve_str_literal(event_node)
        resource_type = _resolve_str_literal(resource_type_node)
        if event is None or resource_type is None:
            # Covered by the literal-only test above; skip here to avoid double-reporting.
            continue
        if (event, resource_type) not in LOCKED_AUDIT_EVENTS:
            unlocked.append(
                f"{path.relative_to(_REPO_ROOT)}:{lineno} — "
                f"({event!r}, {resource_type!r}) not in LOCKED_AUDIT_EVENTS"
            )
    assert not unlocked, (
        "audit.emit() called with (event, resource_type) pair NOT in LOCKED_AUDIT_EVENTS.\n"
        "Either fix the typo at the callsite or extend `LOCKED_AUDIT_EVENTS` "
        "in apps/backend/app/core/audit.py.\n"
        "Offenders:\n  " + "\n  ".join(unlocked)
    )


def test_locked_audit_events_has_expected_count() -> None:
    """Sanity belt — 18 v1.1 + 12 v1.2 + 6 v1.3 + 17 v1.4 + 5 v1.5 + 11 v1.6 = 69 locked pairs.

    Original Plan 15-03 expected 16 v1.1 + 10 v1.2 = 26. Plan executor verified
    against actual callsites and added 2 v1.1 events the docstring had omitted:
    `(rbac_forbidden, 'rbac')` and `(csrf_mismatch, 'csrf')` (both Phase 6).
    Phase 20 added `(telegram_unknown_checkin, 'visit')` (D-20-10).
    Phase 23 added `('session_revoked', 'auth_session')` (D-23-10 per-family revoke endpoint).
    Phase 24 (INFRA-15, D-24-18) added 6 v1.3 pairs pre-registered for Phases 25/26/27:
    `membership_frozen`, `membership_unfrozen`, `membership_renewed`,
    `expiring_notification_sent_{7d,3d,1d}`. See 15-03-SUMMARY.md / 24-01-SUMMARY.md.
    Phase 30 (INFRA-17, B-03 / D-30-02) added 17 v1.4 pairs pre-registered for Phases
    31/32/33/34: 4 trainer lifecycle + 3 payment/refund + 3 pt_package_plan lifecycle
    + 5 pt_package instance lifecycle + 2 pt_session lifecycle. See 30-01-SUMMARY.md.
    Phase 37 (INFRA-24 / C-06) added 5 v1.5 pairs pre-registered for Phase 38:
    2 schedule_slot lifecycle (`slot_published`, `slot_cancelled`) +
    3 booking lifecycle (`booking_created`, `booking_cancelled`, `booking_no_show`).
    NOTE per C-06: `booking_completed` is NOT a separate event — completion is
    carried by the existing `("pt_session_recorded", "pt_session")` event with
    an optional `booking_id` field on `PtSessionRecordedPayload`.
    See 37-01-SUMMARY.md.
    Phase 41 (INFRA-34 / D-41-19) added 11 v1.6 pairs pre-registered for Phases
    42/43/44/45: 2 email transport (`email_sent`, `email_send_failed` under
    `email_send_log`) + 6 multi-user lifecycle (`user_invited`,
    `user_invitation_accepted`, `user_invitation_revoked`, `user_deactivated`,
    `user_reactivated`, `user_soft_deleted` under `user`) + 2 password reset
    (`password_reset_requested`, `password_reset_completed` under `user`) + 1
    payment receipt email (`payment_receipt_emailed` under `payment`). See
    41-01-SUMMARY.md.
    NOTE: the 41-01 plan header glosses "56 → 67" by counting only the v1.1-v1.5
    pairs the planner had in mind (it omitted the Phase 20 D-20-10
    `telegram_unknown_checkin` and Phase 23 D-23-10 `session_revoked`/`auth_session`
    drift adds); the actual frozenset is 58 + 11 = 69. The 11-pair v1.6 delta is
    what matters per INFRA-34, and `test_locked_audit_events_includes_v16_pairs`
    asserts every required pair is present byte-for-byte.
    """
    assert len(LOCKED_AUDIT_EVENTS) == 69, (
        f"LOCKED_AUDIT_EVENTS size drifted: expected 69 "
        f"(18 v1.1 + 12 v1.2 + 6 v1.3 + 17 v1.4 + 5 v1.5 + 11 v1.6), "
        f"got {len(LOCKED_AUDIT_EVENTS)}"
    )


def test_locked_audit_events_includes_v16_pairs() -> None:
    """INFRA-34 (Phase 41 / D-41-19): the 11 v1.6 pairs are pre-registered for Phases 42/43/44/45.

    Email transport (Phase 42 EMAIL-01 / EMAIL-04 / EMAIL-06):
        `email_sent`, `email_send_failed` under resource_type `email_send_log`.
    Multi-user admin lifecycle (Phase 43 USERS-03 / USERS-04 / USERS-05 +
    Phase 44 RESET-03 / RESET-05):
        `user_invited`, `user_invitation_accepted`, `user_invitation_revoked`,
        `user_deactivated`, `user_reactivated`, `user_soft_deleted` under
        resource_type `user`.
    Password reset (Phase 44 RESET-01 / RESET-02):
        `password_reset_requested` (emitted in BOTH known-email and unknown-email
        branches per the RESET-06 anti-oracle contract; unknown branch passes
        resource_id=None), `password_reset_completed` under resource_type `user`.
    Payment receipt email (Phase 45 NOTIFY-12):
        `payment_receipt_emailed` under resource_type `payment`.
    """
    expected = [
        ("email_sent", "email_send_log"),
        ("email_send_failed", "email_send_log"),
        ("user_invited", "user"),
        ("user_invitation_accepted", "user"),
        ("user_invitation_revoked", "user"),
        ("user_deactivated", "user"),
        ("user_reactivated", "user"),
        ("user_soft_deleted", "user"),
        ("password_reset_requested", "user"),
        ("password_reset_completed", "user"),
        ("payment_receipt_emailed", "payment"),
    ]
    for pair in expected:
        assert pair in LOCKED_AUDIT_EVENTS, (
            f"Phase 41 INFRA-34: required pair {pair} missing from LOCKED_AUDIT_EVENTS"
        )


def test_locked_audit_events_includes_v13_pairs() -> None:
    """INFRA-15 (Phase 24): the 6 v1.3 pairs are pre-registered for downstream phases."""
    expected = [
        ("membership_frozen", "membership"),
        ("membership_unfrozen", "membership"),
        ("membership_renewed", "membership"),
        ("expiring_notification_sent_7d", "membership"),
        ("expiring_notification_sent_3d", "membership"),
        ("expiring_notification_sent_1d", "membership"),
    ]
    for pair in expected:
        assert pair in LOCKED_AUDIT_EVENTS, (
            f"Phase 24 INFRA-15: required pair {pair} missing from LOCKED_AUDIT_EVENTS"
        )


def test_locked_audit_events_includes_v15_pairs() -> None:
    """INFRA-24 (Phase 37): the 5 v1.5 pairs are pre-registered for Phase 38 emit callsites.

    Schedule slot lifecycle (Phase 38 SLOT-01 / SLOT-07 / SLOT-09):
        `slot_published`, `slot_cancelled` under resource_type `schedule_slot`.
    Booking lifecycle (Phase 38 BOOK-02 / BOOK-06; Phase 39 CRON-01 for no_show):
        `booking_created`, `booking_cancelled`, `booking_no_show` under resource_type `booking`.

    Per C-06: `booking_completed` is NOT a separate event — completion is signalled
    by the existing `("pt_session_recorded", "pt_session")` event carrying the
    optional `booking_id` field on `PtSessionRecordedPayload`.
    """
    expected = [
        ("slot_published", "schedule_slot"),
        ("slot_cancelled", "schedule_slot"),
        ("booking_created", "booking"),
        ("booking_cancelled", "booking"),
        ("booking_no_show", "booking"),
    ]
    for pair in expected:
        assert pair in LOCKED_AUDIT_EVENTS, (
            f"Phase 37 INFRA-24: required pair {pair} missing from LOCKED_AUDIT_EVENTS"
        )


@pytest.mark.asyncio
async def test_bogus_v16_audit_event_is_rejected() -> None:
    """Phase 41 / INFRA-34 synthetic-violation fixture: a bogus v1.6 event name
    that is NOT in LOCKED_AUDIT_EVENTS MUST be rejected at the emit() boundary
    BEFORE any DB interaction.

    Mirrors the existing Phase 15 AST literal-string gate, but at the runtime
    layer — the dual-defence pair (AST gate + runtime frozenset check) is what
    closes the AST-gate-churn class (v1.3 INFRA-15 lesson). This test guards the
    runtime half: if a callsite somehow slips past the AST walker (e.g. via a
    rebinding the walker doesn't recognise, or new dynamic code paths in future
    phases), the runtime check still hard-fails per D-09.

    The pair `('bogus_v16_event', 'user')` is intentionally chosen so the event
    name is plausibly v1.6-shaped (`bogus_v16_*`) but the pair is not registered.
    `resource_type='user'` is registered (it IS one of the new v1.6
    resource_types), proving the rejection is on the FULL pair, not just on
    `resource_type`.

    Uses `AsyncMock(spec=AsyncSession)` because the error fires at audit.py:276
    BEFORE any `session.add(...)` call — no real DB interaction needed.
    """
    session = AsyncMock(spec=AsyncSession)
    with pytest.raises(AuditEventNotLockedError) as exc_info:
        await emit(
            session,
            "bogus_v16_event",
            actor_user_id=None,
            resource_type="user",
        )

    msg = str(exc_info.value)
    assert "bogus_v16_event" in msg, msg
    assert "LOCKED_AUDIT_EVENTS" in msg, msg
    # Belt-and-braces: confirm the pair is actually NOT in the frozenset so the
    # test is exercising the real guard (not a falsely-passing assertion).
    assert ("bogus_v16_event", "user") not in LOCKED_AUDIT_EVENTS
    # Confirm the session was never touched — the guard must fire BEFORE any
    # session.add / commit / flush call.
    session.add.assert_not_called()
