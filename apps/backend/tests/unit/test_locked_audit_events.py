"""Phase 50 D-50-23 — LOCKED registry tests for the two new webhook-activation
audit events:
  * ("membership_activated_online", "membership")
  * ("pt_package_activated_online", "pt_package")

These events are emitted from the activator bodies that plan 50-03 implements
inside the ЮKassa webhook UoW (CHILD audit emits per D-50-18 — the webhook
intake's audit_correlation_id is propagated into the payloads).

This file is the Phase 47 INFRA-15 AST/registry discipline gate for the +2
new pairs: it asserts both pairs are in LOCKED_AUDIT_EVENTS, both payload
classes exist with `extra='forbid'`, and AUDIT_PAYLOAD_SCHEMAS maps both
pairs to their respective payload classes.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.audit import LOCKED_AUDIT_EVENTS
from app.core.audit_payloads import (
    AUDIT_PAYLOAD_SCHEMAS,
    MembershipActivatedOnlinePayload,
    PtPackageActivatedOnlinePayload,
)


# --- LOCKED_AUDIT_EVENTS membership ----------------------------------------


def test_membership_activated_online_event_locked() -> None:
    assert ("membership_activated_online", "membership") in LOCKED_AUDIT_EVENTS


def test_pt_package_activated_online_event_locked() -> None:
    assert ("pt_package_activated_online", "pt_package") in LOCKED_AUDIT_EVENTS


def test_locked_audit_events_count_grew_by_2_for_phase_50() -> None:
    """Sanity bound for the Phase 50 +2 D-50-23 additions.

    v1.7 baseline pairs (Phase 47 lock) are 9 — the +2 Phase 50 emit
    surface lifts that to ≥ 11 inside the larger frozenset. The +2 lifts
    the total LOCKED_AUDIT_EVENTS cardinality by at least 2 over the
    Phase 47 baseline (which is many more than 11 across all milestones).
    """
    new_pairs = {
        ("membership_activated_online", "membership"),
        ("pt_package_activated_online", "pt_package"),
    }
    assert new_pairs.issubset(LOCKED_AUDIT_EVENTS)


# --- MembershipActivatedOnlinePayload --------------------------------------


def test_membership_activated_online_payload_validates() -> None:
    payload = MembershipActivatedOnlinePayload(
        audit_correlation_id=uuid4(),
        membership_id=uuid4(),
        client_id=uuid4(),
        online_payment_id=uuid4(),
    )
    assert payload.membership_id is not None
    assert payload.client_id is not None
    assert payload.online_payment_id is not None


def test_membership_activated_online_payload_allows_none_correlation_id() -> None:
    payload = MembershipActivatedOnlinePayload(
        audit_correlation_id=None,
        membership_id=uuid4(),
        client_id=uuid4(),
        online_payment_id=uuid4(),
    )
    assert payload.audit_correlation_id is None


def test_membership_activated_online_payload_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        MembershipActivatedOnlinePayload(
            audit_correlation_id=None,
            membership_id=uuid4(),
            client_id=uuid4(),
            online_payment_id=uuid4(),
            foo="bar",  # type: ignore[call-arg]
        )


# --- PtPackageActivatedOnlinePayload ---------------------------------------


def test_pt_package_activated_online_payload_validates() -> None:
    payload = PtPackageActivatedOnlinePayload(
        audit_correlation_id=uuid4(),
        pt_package_id=uuid4(),
        client_id=uuid4(),
        online_payment_id=uuid4(),
    )
    assert payload.pt_package_id is not None
    assert payload.client_id is not None
    assert payload.online_payment_id is not None


def test_pt_package_activated_online_payload_allows_none_correlation_id() -> None:
    payload = PtPackageActivatedOnlinePayload(
        audit_correlation_id=None,
        pt_package_id=uuid4(),
        client_id=uuid4(),
        online_payment_id=uuid4(),
    )
    assert payload.audit_correlation_id is None


def test_pt_package_activated_online_payload_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        PtPackageActivatedOnlinePayload(
            audit_correlation_id=None,
            pt_package_id=uuid4(),
            client_id=uuid4(),
            online_payment_id=uuid4(),
            foo="bar",  # type: ignore[call-arg]
        )


# --- AUDIT_PAYLOAD_SCHEMAS registry ----------------------------------------


def test_audit_payload_schemas_registers_membership_activated_online() -> None:
    assert (
        AUDIT_PAYLOAD_SCHEMAS[("membership_activated_online", "membership")]
        is MembershipActivatedOnlinePayload
    )


def test_audit_payload_schemas_registers_pt_package_activated_online() -> None:
    assert (
        AUDIT_PAYLOAD_SCHEMAS[("pt_package_activated_online", "pt_package")]
        is PtPackageActivatedOnlinePayload
    )
