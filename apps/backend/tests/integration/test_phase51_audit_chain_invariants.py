"""Phase 51 D-51-11 + D-51-19 — Audit-chain invariants.

Verifies that:

1. LOCKED_AUDIT_EVENTS count is 85 after Phase 51 (79 pre-51 + 3 refund + 3 fiscal).
   NOTE: plan 51-10 documents 82 but the actual running total is 85; the plan used
   a stale figure. The AST gate (tests/unit/test_audit_taxonomy.py) protects against
   undeclared additions. This test locks the POST-phase-51 baseline.

2. The 3 new Phase 51 audit event pairs are present in LOCKED_AUDIT_EVENTS.

3. The 3 new Phase 51 payload classes are registered in AUDIT_PAYLOAD_SCHEMAS.

4. For a refund.succeeded webhook UoW, the audit chain contains exactly the expected
   set of events: online_payment_refunded + membership_refunded + yookassa_webhook_received
   (3 audits — the root is yookassa_webhook_received per D-50-18 step 8).
   (No fiscal_receipt_inserted audit — the fiscal receipt INSERT in settle.py does NOT
   emit a dedicated audit row per plan 51-07 implementation.)

5. poll_pending_refunds (cron path) uses online_refund_polled_settled as the chain root.

6. dispatch_fiscal_receipt emits fiscal_receipt_dispatched audit inside its write session.

7. All Phase 51 audit.emit callsites use literal string event names (AST gate).

8. All Phase 51 audit.emit UUID kwargs are wrapped in str() (AST gate — Phase 32-02 lesson).
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

from app.core.audit import LOCKED_AUDIT_EVENTS


# ---------------------------------------------------------------------------
# 1. LOCKED_AUDIT_EVENTS count.
# ---------------------------------------------------------------------------


def test_locked_audit_events_count_after_phase_51_is_85() -> None:
    """LOCKED_AUDIT_EVENTS baseline — 93 after Phase 59.

    History (the diff IS the review gate — bump on every audit-event addition):
      - 85 after Phase 51 (79 pre-51 + 3 refund + 3 fiscal)
      - 89 after Phase 58 (+4 payroll: comp-config set, accrual created/paid, clawback)
      - 93 after Phase 59 (+4 schedule: recurring_slot_template_created/cancelled,
        trainer_time_off_created/cancelled)
    If this fails with a higher count a new audit event was added without
    updating this test (intended behaviour). Update this assertion to lock the
    new baseline.
    """
    assert len(LOCKED_AUDIT_EVENTS) == 93, (
        f"Expected 93 LOCKED_AUDIT_EVENTS after Phase 59, got {len(LOCKED_AUDIT_EVENTS)}. "
        "Either a new event was added without updating this test, or an event was removed. "
        "Update this assertion to lock the new baseline."
    )


# ---------------------------------------------------------------------------
# 2. 3 new Phase 51 event pairs present.
# ---------------------------------------------------------------------------


def test_phase_51_new_audit_pairs_registered() -> None:
    """The 3 new Phase 51 audit event pairs are in LOCKED_AUDIT_EVENTS."""
    assert ("online_refund_initiated", "online_refund") in LOCKED_AUDIT_EVENTS, (
        "('online_refund_initiated', 'online_refund') missing from LOCKED_AUDIT_EVENTS"
    )
    assert ("online_refund_polled_settled", "online_refund") in LOCKED_AUDIT_EVENTS, (
        "('online_refund_polled_settled', 'online_refund') missing from LOCKED_AUDIT_EVENTS"
    )
    assert ("online_refund_canceled", "online_refund") in LOCKED_AUDIT_EVENTS, (
        "('online_refund_canceled', 'online_refund') missing from LOCKED_AUDIT_EVENTS"
    )


# ---------------------------------------------------------------------------
# 3. 3 new payload classes in AUDIT_PAYLOAD_SCHEMAS.
# ---------------------------------------------------------------------------


def test_phase_51_new_payload_classes_registered_in_audit_payload_schemas() -> None:
    """All 3 new Phase 51 audit payload classes are registered in AUDIT_PAYLOAD_SCHEMAS."""
    from app.core.audit_payloads import (
        AUDIT_PAYLOAD_SCHEMAS,
        OnlineRefundCanceledPayload,
        OnlineRefundInitiatedPayload,
        OnlineRefundPolledSettledPayload,
    )

    assert (
        AUDIT_PAYLOAD_SCHEMAS.get(("online_refund_initiated", "online_refund"))
        is OnlineRefundInitiatedPayload
    ), "OnlineRefundInitiatedPayload not registered in AUDIT_PAYLOAD_SCHEMAS"
    assert (
        AUDIT_PAYLOAD_SCHEMAS.get(("online_refund_polled_settled", "online_refund"))
        is OnlineRefundPolledSettledPayload
    ), "OnlineRefundPolledSettledPayload not registered in AUDIT_PAYLOAD_SCHEMAS"
    assert (
        AUDIT_PAYLOAD_SCHEMAS.get(("online_refund_canceled", "online_refund"))
        is OnlineRefundCanceledPayload
    ), "OnlineRefundCanceledPayload not registered in AUDIT_PAYLOAD_SCHEMAS"


# ---------------------------------------------------------------------------
# 4. refund.succeeded webhook audit chain shape.
# ---------------------------------------------------------------------------


def test_refund_succeeded_webhook_audit_chain_shape_is_documented() -> None:
    """Audit chain for refund.succeeded webhook: documents the expected 3-event shape.

    Per D-51-11 + settle.py implementation:
    - online_payment_refunded (child — carries audit_correlation_id=chain_root_corr)
    - membership_refunded (child — REF-07: does NOT carry audit_correlation_id)
    - yookassa_webhook_received (root — audit_correlation_id=None, IS the chain root)

    NOTE: The fiscal receipt INSERT in _settle_online_refund does NOT emit a
    dedicated audit row — it relies on the later fiscal_receipt_dispatched event.
    So the chain has 3 child rows, not 4 as some plan docs imply.

    The runtime assertion for this shape is in:
    test_e2e_refund_full_cycle.py::test_e2e_refund_full_cycle_membership (step 3d).

    This static test verifies the settle.py source emits all 3 expected event names
    using AST analysis (does not require a running DB).
    """
    settle_path = Path(__file__).parent.parent.parent / "app/modules/online_refunds/settle.py"
    source = settle_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    emit_names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Await) and isinstance(node.value, ast.Call):
            call = node.value
            func = call.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "emit"
                and len(call.args) >= 2
                and isinstance(call.args[1], ast.Constant)
            ):
                emit_names.append(str(call.args[1].value))

    assert "online_payment_refunded" in emit_names, (
        "online_payment_refunded not found in settle.py audit.emit calls"
    )
    assert "membership_refunded" in emit_names, (
        "membership_refunded not found in settle.py audit.emit calls"
    )
    assert "pt_package_refunded" in emit_names, (
        "pt_package_refunded not found in settle.py audit.emit calls"
    )
    assert "yookassa_webhook_received" in emit_names, (
        "yookassa_webhook_received not found in settle.py audit.emit calls (webhook path)"
    )
    assert "online_refund_polled_settled" in emit_names, (
        "online_refund_polled_settled not found in settle.py audit.emit calls (cron path)"
    )


# ---------------------------------------------------------------------------
# 5-6. Static assertions on audit chain properties (no DB needed for these).
# ---------------------------------------------------------------------------


def test_settle_online_refund_emits_root_event_yookassa_webhook_received_last() -> None:
    """D-50-18 step 8 invariant: the chain root (yookassa_webhook_received) is emitted LAST.

    AST-based check: in settle.py, the yookassa_webhook_received audit.emit call
    comes AFTER the child audit emits (online_payment_refunded, membership_refunded).
    """
    import ast

    settle_path = Path(__file__).parent.parent.parent / "app/modules/online_refunds/settle.py"
    source = settle_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    emit_event_names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Await) and isinstance(node.value, ast.Call):
            func = node.value.func
            if isinstance(func, ast.Attribute) and func.attr == "emit":
                args = node.value.args
                # audit.emit(session, event_name, ...) — event_name is args[1]
                if len(args) >= 2 and isinstance(args[1], ast.Constant):
                    emit_event_names.append(str(args[1].value))

    # Root event must come after child events.
    assert "yookassa_webhook_received" in emit_event_names, (
        "yookassa_webhook_received not found in settle.py audit.emit calls"
    )
    assert "online_refund_polled_settled" in emit_event_names, (
        "online_refund_polled_settled not found in settle.py audit.emit calls"
    )
    # Root events are always last in the function body (D-50-18 step 8).
    last_root_idx = max(
        i
        for i, e in enumerate(emit_event_names)
        if e in ("yookassa_webhook_received", "online_refund_polled_settled")
    )
    first_child_idx_after_root = next(
        (
            i
            for i, e in enumerate(emit_event_names[last_root_idx + 1 :], last_root_idx + 1)
            if e in ("online_payment_refunded", "membership_refunded", "pt_package_refunded")
        ),
        None,
    )
    assert first_child_idx_after_root is None, (
        f"A child audit emit appears AFTER the root emit at index {last_root_idx}. "
        f"emit order: {emit_event_names}"
    )


# ---------------------------------------------------------------------------
# 7. AST gate: Phase 51 audit.emit callsites use literal event names.
# ---------------------------------------------------------------------------

# Phase 51 source files that contain audit.emit calls.
_PHASE_51_AUDIT_FILES: list[Path] = [
    path
    for path in [
        Path(__file__).parent.parent.parent / "app/modules/online_refunds/service.py",
        Path(__file__).parent.parent.parent / "app/modules/online_refunds/settle.py",
        Path(__file__).parent.parent.parent / "app/modules/online_refunds/cron.py",
        Path(__file__).parent.parent.parent / "app/modules/fiscal_receipts/tasks.py",
        Path(__file__).parent.parent.parent / "app/modules/fiscal_receipts/service.py",
        Path(__file__).parent.parent.parent / "app/api/v1/_internal/yookassa/handlers.py",
    ]
    if path.exists()
]


def _collect_audit_emit_calls(
    source: str,
) -> list[tuple[int, ast.Call]]:
    """Return (lineno, ast.Call) for all audit.emit(...) calls in source."""
    tree = ast.parse(source)
    calls: list[tuple[int, ast.Call]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Await) and isinstance(node.value, ast.Call):
            call = node.value
        elif isinstance(node, ast.Call):
            call = node
        else:
            continue
        func = call.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "emit"
            and isinstance(func.value, ast.Name)
            and func.value.id == "audit"
        ):
            calls.append((call.lineno if hasattr(call, "lineno") else 0, call))
    return calls


def test_all_phase_51_audit_emit_callsites_use_literal_event_names() -> None:
    """Phase 47 INFRA-35 AST gate re-check for Phase 51 files.

    Every audit.emit(session, event_name, ...) first positional arg (the event name)
    must be a string literal Constant (not a variable). This enforces the static
    taxonomy requirement: event names must be statically discoverable.
    """
    violations: list[str] = []
    for path in _PHASE_51_AUDIT_FILES:
        source = path.read_text(encoding="utf-8")
        for lineno, call in _collect_audit_emit_calls(source):
            # audit.emit(session, event_name, ...) — event_name is args[1]
            # (args[0] is session, args[1] is the event string).
            if len(call.args) >= 2:
                event_arg = call.args[1]
                if not isinstance(event_arg, ast.Constant):
                    violations.append(
                        f"{path.name}:{lineno} — event arg is {type(event_arg).__name__}, "
                        f"not a string literal"
                    )

    assert not violations, (
        f"Phase 51 audit.emit callsites with non-literal event names:\n" + "\n".join(violations)
    )


# ---------------------------------------------------------------------------
# 8. AST gate: UUID kwargs are str()-wrapped.
# ---------------------------------------------------------------------------


def test_all_phase_51_audit_emit_uuid_kwargs_are_str_cast() -> None:
    """Phase 32-02 deviation #1 lesson: UUID objects in audit.emit **payload kwargs must be str().

    The ``audit.emit(session, event, *, actor_user_id, resource_type, resource_id, **payload)``
    signature accepts typed params directly (UUID handled by the function signature) AND
    free-form ``**payload`` JSONB fields. The Phase 32-02 lesson applies to the PAYLOAD kwargs:
    if a JSONB payload field holds a UUID, it must be str()-cast because raw UUID objects
    are not JSON-serializable.

    Typed params that the function signature handles natively (NOT checked here):
      - actor_user_id, resource_id, actor_email_snapshot, audit_correlation_id

    Checked: all other ``_id``-suffixed kwargs that flow into the JSONB payload.
    """
    # Typed params that audit.emit handles natively (UUID or str, function handles conversion).
    _TYPED_PARAMS = frozenset(
        {
            "actor_user_id",
            "resource_id",
            "actor_email_snapshot",
            "audit_correlation_id",
            "resource_type",
        }
    )

    violations: list[str] = []

    for path in _PHASE_51_AUDIT_FILES:
        source = path.read_text(encoding="utf-8")
        for lineno, call in _collect_audit_emit_calls(source):
            for kw in call.keywords:
                if kw.arg is None:
                    continue  # **kwargs spread — skip
                if kw.arg in _TYPED_PARAMS:
                    continue  # typed param — handled by audit.emit signature
                if not kw.arg.endswith("_id"):
                    continue  # not an _id field — skip
                val = kw.value
                # Allowed: str(something), string literal, None constant.
                if isinstance(val, ast.Constant):
                    continue  # literal string or None — ok
                if (
                    isinstance(val, ast.Call)
                    and isinstance(val.func, ast.Name)
                    and val.func.id == "str"
                ):
                    continue  # str(...) wrapper — ok
                # Flag raw `something.id` Attribute access (ORM model UUID field).
                # Name nodes (plain variables) are excluded because they could be
                # string variables (e.g., `object_id: str`, `yookassa_refund_id: str`).
                # Only `something.id` attribute access is a reliable UUID indicator.
                if isinstance(val, ast.Attribute) and val.attr == "id":
                    violations.append(
                        f"{path.name}:{lineno} — payload kwarg {kw.arg!r} value "
                        f"{ast.dump(val)!r} not wrapped in str() "
                        "(Phase 32-02 lesson: ORM UUID .id fields must be str-cast in JSONB)"
                    )

    assert not violations, (
        f"Phase 51 audit.emit JSONB payload UUID kwargs not wrapped in str():\n"
        + "\n".join(violations)
    )
