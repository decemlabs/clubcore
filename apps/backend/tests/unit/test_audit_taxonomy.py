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
from app.core.audit_payloads import AUDIT_PAYLOAD_SCHEMAS

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
            offenders.append(f"{path.relative_to(_REPO_ROOT)}:{lineno} — missing `event` arg")
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
    """Sanity belt — 18+12+6+17+5+13+9 = 80 locked pairs (v1.1+v1.2+v1.3+v1.4+v1.5+v1.6+v1.7).

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
    drift adds); the actual frozenset was 58 + 11 = 69 at Phase 41 lock.

    Phase 42 Plan 09 (D-42-35) ADDS one v1.6 pair: ``('otp_requested', 'otp')``
    — piggybacked on the existing ``otp_*`` resource-type lineage so the
    unified ``/auth/otp/request`` endpoint (telegram facade + email branch)
    emits a single locked event regardless of channel. The 11-v1.6 count
    becomes 12 and the frozenset total becomes 58 + 12 = 70.

    Phase 43 Plan 03 (D-43-20) ADDS one more v1.6 pair:
    ``('refresh_failed', 'session')`` — anti-oracle forensic emit from
    ``/auth/refresh`` when the refresh-token resolves to a deactivated /
    soft-deleted user (USERS-06). HTTP response is identical to the
    invalid_session branch; only the audit row discriminates. The 12-v1.6
    count becomes 13 and the frozenset total becomes 58 + 13 = 71.

    Phase 47 (INFRA-34 / D-47) added 9 v1.7 pairs pre-registered for Phases
    49/50/51 — the online-payments + 54-ФЗ + ЮKassa webhook lock. 5 online
    payment lifecycle pairs under ``online_payment`` (``online_payment_initiated``,
    ``yookassa_payment_created``, ``online_payment_succeeded``,
    ``online_payment_canceled``, ``online_payment_refunded``) + 3 fiscal-receipt
    lifecycle pairs under ``fiscal_receipt`` (``fiscal_receipt_dispatched``,
    ``fiscal_receipt_succeeded``, ``fiscal_receipt_failed``) + 1 webhook intake
    audit-trail pair (``yookassa_webhook_received`` under ``yookassa_webhook``).
    The frozenset total becomes 71 + 9 = 80. See 47-01-SUMMARY.md.

    Phase 50 Plan 50-02 (D-50-23) ADDS 2 webhook-driven activation pairs:
    ``('membership_activated_online', 'membership')`` and
    ``('pt_package_activated_online', 'pt_package')`` — CHILD audit emits
    inside the ЮKassa webhook UoW (D-50-18). The v1.7 count grows 9 → 11
    and the frozenset total becomes 80 + 2 = 82. See 50-02-SUMMARY.md.

    Phase 51 Plan 51-02 (D-51-19) ADDS 3 online-refund lifecycle pairs:
    ``('online_refund_initiated', 'online_refund')`` — fresh chain root,
    emitted from POST /online-payments/.../refund (Plan 51-08);
    ``('online_refund_polled_settled', 'online_refund')`` and
    ``('online_refund_canceled', 'online_refund')`` — CHILD emits from the
    poll_pending_refunds cron synthesising a settle UoW after a missed
    webhook (Plan 51-09 / D-51-17). The v1.7 count grows 11 → 14 and the
    frozenset total becomes 82 + 3 = 85. See 51-02-SUMMARY.md.

    Phase 90 (INFRA-15 / D-90 messaging lock) ADDS 4 v2.5 messaging pairs
    pre-registered BEFORE any callsite (Phases 90-93 implement the emitters):
    ``('message_sent', 'message')``, ``('message_read', 'message')``,
    ``('attachment_uploaded', 'message')``,
    ``('chat_staff_reply_sent', 'message')``.
    The frozenset total becomes 105 + 4 = 109. See 90-*-SUMMARY.md.

    Phase 96 (INFRA-15 / D-96 referral lock) ADDS 3 v2.6 referral pairs
    pre-registered BEFORE any callsite (Phase 96 implements the emitters):
    ``('referral_code_generated', 'referral')``,
    ``('referral_captured', 'referral')``,
    ``('referral_bonus_accrued', 'referral')``.
    The frozenset total becomes 109 + 3 = 112. See 96-*-SUMMARY.md.
    """
    assert len(LOCKED_AUDIT_EVENTS) == 112, (
        "LOCKED_AUDIT_EVENTS size drifted: expected 112 "
        "(18 v1.1 + 12 v1.2 + 6 v1.3 + 17 v1.4 + 5 v1.5 + 13 v1.6 + 14 v1.7 "
        "+ 4 v1.9/P58 + 4 v1.9/P59 + 1 pre-P68 + 6 v2.0/P68 + 1 v2.2/P80 booking_rescheduled "
        "+ 1 v2.3/P82 loyalty_accrued + 1 v2.3/P83 loyalty_redeemed "
        "+ 2 v2.3/P84: autopay_charge_initiated + autopay_charge_failed (APAY-01/APAY-03, INFRA-15) "
        "+ 4 v2.5/P90: message_sent + message_read + attachment_uploaded + chat_staff_reply_sent "
        "+ 3 v2.6/P96: referral_code_generated + referral_captured + referral_bonus_accrued), "
        f"got {len(LOCKED_AUDIT_EVENTS)}"
    )
    # v2.3 Phase 82 INFRA-15 / ACCR-01/ACCR-02: +1 loyalty accrual lifecycle pair
    # pre-registered before any emit callsite — loyalty_accrued.
    # Single event covers welcome + owner_grant (distinguished by entry_type/actor).
    # Count grows 101 → 102.
    # v1.9 Phase 58 INFRA-15 / D-58-16: +4 payroll lifecycle pairs pre-registered
    # before any emit callsite — trainer_comp_config_set, payroll_accrual_created,
    # payroll_accrual_paid, payroll_clawback_recorded. Count grows 85 → 89.
    # v1.9 Phase 59 INFRA-15 / D-59-09: +4 recurring-schedule + time-off pairs
    # pre-registered before any emit callsite — recurring_slot_template_created,
    # recurring_slot_template_cancelled, trainer_time_off_created,
    # trainer_time_off_cancelled. Count grows 89 → 93.
    # Pre-Phase 68: +1 event added before this count was updated. Count: 93 → 94.
    # v2.0 Phase 68 CAUTH-01..06 / D-01/D-09: +6 client auth lifecycle pairs
    # pre-registered before any emit callsite — client_otp_requested/consumed,
    # client_refresh_failed, client_family_reuse_detected, client_session_revoked,
    # client_me_updated. Count grows 94 → 100.


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


def test_phase59_locked_pairs_have_registered_payload_schemas() -> None:
    """WR-01 (Phase 59): every Phase-59 locked pair MUST have a registered Pydantic
    payload schema in AUDIT_PAYLOAD_SCHEMAS with extra='forbid'.

    Without a registered schema, audit.emit() skips the payload validation branch
    entirely (schema = AUDIT_PAYLOAD_SCHEMAS.get(pair) → None), so typo'd or
    drifting payload keys land silently in JSONB. This test closes that gap for
    the four Phase-59 recurring-schedule + time-off events.
    """
    phase59_pairs = [
        ("recurring_slot_template_created", "schedule_slot"),
        ("recurring_slot_template_cancelled", "schedule_slot"),
        ("trainer_time_off_created", "trainer"),
        ("trainer_time_off_cancelled", "trainer"),
    ]
    missing_from_locked: list[str] = []
    missing_schema: list[str] = []
    for pair in phase59_pairs:
        if pair not in LOCKED_AUDIT_EVENTS:
            missing_from_locked.append(str(pair))
        if pair not in AUDIT_PAYLOAD_SCHEMAS:
            missing_schema.append(str(pair))
    assert not missing_from_locked, (
        f"Phase 59 pairs missing from LOCKED_AUDIT_EVENTS: {missing_from_locked}"
    )
    assert not missing_schema, (
        f"Phase 59 pairs missing from AUDIT_PAYLOAD_SCHEMAS (WR-01): {missing_schema}"
    )
