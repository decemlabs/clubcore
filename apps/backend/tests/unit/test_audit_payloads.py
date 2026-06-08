"""Tests for v1.5 audit payload schemas (Phase 37 INFRA-25 / C-06).

Covers:
  - The 5 new Pydantic v2 payload schemas (extra='forbid' round-trip + reject).
  - The additive `booking_id: UUID | None = None` extension on the existing
    `PtSessionRecordedPayload` (back-compat preserved for v1.4 callsites in
    apps/backend/app/modules/pt_sessions/service.py).
  - The 5 new entries in `AUDIT_PAYLOAD_SCHEMAS` registry (lookup-by-tuple).

Mirrors PATTERNS.md §8 shape (apps/backend/tests/unit/test_schemas.py:56,90 for
the Pydantic extra-forbid round-trip precedent).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.core.audit_payloads import (
    AUDIT_PAYLOAD_SCHEMAS,
    BookingCancelledPayload,
    BookingCreatedPayload,
    BookingNoShowPayload,
    EmailSendFailedPayload,
    EmailSentPayload,
    PasswordResetCompletedPayload,
    PasswordResetRequestedPayload,
    PaymentReceiptEmailedPayload,
    PtSessionRecordedPayload,
    ReferralBonusAccruedPayload,
    SlotCancelledPayload,
    SlotPublishedPayload,
    UserDeactivatedPayload,
    UserInvitationAcceptedPayload,
    UserInvitationRevokedPayload,
    UserInvitedPayload,
    UserReactivatedPayload,
    UserSoftDeletedPayload,
)

# ---------------------------------------------------------------------------
# SlotPublishedPayload — Phase 38 SLOT-01
# ---------------------------------------------------------------------------


def test_slot_published_payload_round_trip() -> None:
    """SlotPublishedPayload accepts the full v1.5 SLOT-01 kwarg set."""
    p = SlotPublishedPayload(
        slot_id=uuid4(),
        trainer_id=uuid4(),
        start_time="2026-05-20T10:00:00+03:00",
        end_time="2026-05-20T11:00:00+03:00",
        created_by_user_id=uuid4(),
    )
    assert isinstance(p.slot_id, UUID)
    assert p.start_time == "2026-05-20T10:00:00+03:00"


def test_slot_published_payload_rejects_extra_keys() -> None:
    """extra='forbid' surfaces unknown payload keys at emit time."""
    with pytest.raises(ValidationError):
        SlotPublishedPayload(  # type: ignore[call-arg]
            slot_id=uuid4(),
            trainer_id=uuid4(),
            start_time="2026-05-20T10:00:00+03:00",
            end_time="2026-05-20T11:00:00+03:00",
            created_by_user_id=uuid4(),
            spurious_key="should-be-rejected",
        )


# ---------------------------------------------------------------------------
# SlotCancelledPayload — Phase 38 SLOT-07 / SLOT-09
# ---------------------------------------------------------------------------


def test_slot_cancelled_payload_round_trip() -> None:
    """SlotCancelledPayload accepts the SLOT-09 had_booking discriminator."""
    p = SlotCancelledPayload(
        slot_id=uuid4(),
        trainer_id=uuid4(),
        cancelled_by_user_id=uuid4(),
        cancel_reason="trainer unavailable",
        had_booking=True,
    )
    assert p.had_booking is True
    assert p.cancel_reason == "trainer unavailable"


def test_slot_cancelled_payload_rejects_extra_keys() -> None:
    """extra='forbid' surfaces unknown payload keys at emit time."""
    with pytest.raises(ValidationError):
        SlotCancelledPayload(  # type: ignore[call-arg]
            slot_id=uuid4(),
            trainer_id=uuid4(),
            cancelled_by_user_id=uuid4(),
            cancel_reason="trainer unavailable",
            had_booking=False,
            spurious_key="should-be-rejected",
        )


# ---------------------------------------------------------------------------
# BookingCreatedPayload — Phase 38 BOOK-02
# ---------------------------------------------------------------------------


def test_booking_created_payload_round_trip() -> None:
    """BookingCreatedPayload accepts the full BOOK-02 kwarg set."""
    p = BookingCreatedPayload(
        booking_id=uuid4(),
        slot_id=uuid4(),
        client_id=uuid4(),
        pt_package_id=uuid4(),
        created_by_user_id=uuid4(),
    )
    assert isinstance(p.booking_id, UUID)
    assert isinstance(p.pt_package_id, UUID)


def test_booking_created_payload_rejects_extra_keys() -> None:
    """extra='forbid' surfaces unknown payload keys at emit time."""
    with pytest.raises(ValidationError):
        BookingCreatedPayload(  # type: ignore[call-arg]
            booking_id=uuid4(),
            slot_id=uuid4(),
            client_id=uuid4(),
            pt_package_id=uuid4(),
            created_by_user_id=uuid4(),
            spurious_key="should-be-rejected",
        )


# ---------------------------------------------------------------------------
# BookingCancelledPayload — Phase 38 BOOK-06
# ---------------------------------------------------------------------------


def test_booking_cancelled_payload_round_trip() -> None:
    """BookingCancelledPayload accepts the full BOOK-06 kwarg set."""
    p = BookingCancelledPayload(
        booking_id=uuid4(),
        slot_id=uuid4(),
        cancelled_by_user_id=uuid4(),
        cancel_reason="client request",
    )
    assert p.cancel_reason == "client request"


def test_booking_cancelled_payload_rejects_extra_keys() -> None:
    """extra='forbid' surfaces unknown payload keys at emit time."""
    with pytest.raises(ValidationError):
        BookingCancelledPayload(  # type: ignore[call-arg]
            booking_id=uuid4(),
            slot_id=uuid4(),
            cancelled_by_user_id=uuid4(),
            cancel_reason="client request",
            spurious_key="should-be-rejected",
        )


# ---------------------------------------------------------------------------
# BookingNoShowPayload — Phase 39 CRON-01
# ---------------------------------------------------------------------------


def test_booking_no_show_payload_round_trip() -> None:
    """BookingNoShowPayload accepts the full CRON-01 kwarg set."""
    p = BookingNoShowPayload(
        booking_id=uuid4(),
        slot_id=uuid4(),
        client_id=uuid4(),
        no_show_at="2026-05-20T11:15:00+03:00",
    )
    assert p.no_show_at == "2026-05-20T11:15:00+03:00"


def test_booking_no_show_payload_rejects_extra_keys() -> None:
    """extra='forbid' surfaces unknown payload keys at emit time."""
    with pytest.raises(ValidationError):
        BookingNoShowPayload(  # type: ignore[call-arg]
            booking_id=uuid4(),
            slot_id=uuid4(),
            client_id=uuid4(),
            no_show_at="2026-05-20T11:15:00+03:00",
            spurious_key="should-be-rejected",
        )


# ---------------------------------------------------------------------------
# PtSessionRecordedPayload.booking_id — C-06 / D-37-05 additive extension
# ---------------------------------------------------------------------------


def _pt_session_base_kwargs() -> dict[str, object]:
    """v1.4 baseline kwargs for PtSessionRecordedPayload — back-compat anchor."""
    return {
        "pt_session_id": uuid4(),
        "pt_package_id": uuid4(),
        "client_id": uuid4(),
        "trainer_id": uuid4(),
        "trainer_name_snapshot": "Иван Иванов",
        "performed_at": "2026-05-20T10:00:00+03:00",
        "performed_by_user_id": uuid4(),
        "sessions_remaining_after": 4,
    }


def test_pt_session_recorded_payload_accepts_missing_booking_id() -> None:
    """C-06 / D-37-05 back-compat: every v1.4 emit callsite (no booking_id) keeps validating.

    `apps/backend/app/modules/pt_sessions/service.py:record_pt_session` is the
    pre-existing v1.4 caller; this test pins its kwarg shape.
    """
    p = PtSessionRecordedPayload(**_pt_session_base_kwargs())  # type: ignore[arg-type]
    assert p.booking_id is None


def test_pt_session_recorded_payload_accepts_booking_id_uuid() -> None:
    """C-06: completion of a booking flows via the EXISTING pt_session_recorded event."""
    booking_id = uuid4()
    p = PtSessionRecordedPayload(**_pt_session_base_kwargs(), booking_id=booking_id)  # type: ignore[arg-type]
    assert p.booking_id == booking_id


def test_pt_session_recorded_payload_still_rejects_extra_keys() -> None:
    """extra='forbid' must remain enforced after the booking_id additive extension."""
    with pytest.raises(ValidationError):
        PtSessionRecordedPayload(  # type: ignore[arg-type, call-arg]
            **_pt_session_base_kwargs(),
            booking_id=uuid4(),
            spurious_key="should-be-rejected",
        )


# ---------------------------------------------------------------------------
# AUDIT_PAYLOAD_SCHEMAS registry — INFRA-25
# ---------------------------------------------------------------------------


def test_v15_payload_schemas_registered() -> None:
    """5 new v1.5 (event, resource_type) pairs map to their Pydantic schemas."""
    assert AUDIT_PAYLOAD_SCHEMAS[("slot_published", "schedule_slot")] is SlotPublishedPayload
    assert AUDIT_PAYLOAD_SCHEMAS[("slot_cancelled", "schedule_slot")] is SlotCancelledPayload
    assert AUDIT_PAYLOAD_SCHEMAS[("booking_created", "booking")] is BookingCreatedPayload
    assert AUDIT_PAYLOAD_SCHEMAS[("booking_cancelled", "booking")] is BookingCancelledPayload
    assert AUDIT_PAYLOAD_SCHEMAS[("booking_no_show", "booking")] is BookingNoShowPayload


# ---------------------------------------------------------------------------
# Phase 40 D-40-05 — BookingCreatedPayload additive relaxation
# ---------------------------------------------------------------------------


def test_booking_created_payload_accepts_telegram_bot_role() -> None:
    """Phase 40 D-40-05 — actor_role='telegram_bot' + created_by_user_id=None
    is the canonical shape for the Telegram /book self-service path."""
    p = BookingCreatedPayload(
        booking_id=uuid4(),
        slot_id=uuid4(),
        client_id=uuid4(),
        pt_package_id=uuid4(),
        created_by_user_id=None,
        actor_role="telegram_bot",
    )
    assert p.actor_role == "telegram_bot"
    assert p.created_by_user_id is None


def test_booking_created_payload_accepts_default_reception_role() -> None:
    """Back-compat: omitting actor_role yields 'reception' (Phase 38 shape)."""
    p = BookingCreatedPayload(
        booking_id=uuid4(),
        slot_id=uuid4(),
        client_id=uuid4(),
        pt_package_id=uuid4(),
        created_by_user_id=uuid4(),
    )
    assert p.actor_role == "reception"


def test_booking_created_payload_accepts_owner_role() -> None:
    """The 3-value Literal accepts 'owner' for owner-initiated bookings."""
    p = BookingCreatedPayload(
        booking_id=uuid4(),
        slot_id=uuid4(),
        client_id=uuid4(),
        pt_package_id=uuid4(),
        created_by_user_id=uuid4(),
        actor_role="owner",
    )
    assert p.actor_role == "owner"


def test_booking_created_payload_accepts_client_role() -> None:
    """Phase 70 D-70-01/07 — the Literal accepts 'client' for client self-bookings."""
    p = BookingCreatedPayload(
        booking_id=uuid4(),
        slot_id=uuid4(),
        client_id=uuid4(),
        pt_package_id=uuid4(),
        created_by_user_id=None,  # self-service: created_by_user_id is NULL (D-40-05)
        actor_role="client",
    )
    assert p.actor_role == "client"


def test_booking_created_payload_rejects_unknown_role() -> None:
    """Literal["reception", "owner", "telegram_bot", "client"] rejects all other values."""
    with pytest.raises(ValidationError):
        BookingCreatedPayload(  # type: ignore[arg-type]
            booking_id=uuid4(),
            slot_id=uuid4(),
            client_id=uuid4(),
            pt_package_id=uuid4(),
            created_by_user_id=uuid4(),
            actor_role="trainer",  # type: ignore[arg-type]
        )


def test_booking_created_payload_extra_forbid_still_enforced() -> None:
    """extra='forbid' invariant survives the Phase 40 additive relaxation."""
    with pytest.raises(ValidationError):
        BookingCreatedPayload(  # type: ignore[call-arg]
            booking_id=uuid4(),
            slot_id=uuid4(),
            client_id=uuid4(),
            pt_package_id=uuid4(),
            created_by_user_id=uuid4(),
            actor_role="reception",
            foo="bar",
        )


def test_booking_created_payload_registry_unchanged() -> None:
    """LOCKED_AUDIT_EVENTS / AUDIT_PAYLOAD_SCHEMAS shapes are additive-only —
    the ('booking_created', 'booking') key still maps to BookingCreatedPayload."""
    assert AUDIT_PAYLOAD_SCHEMAS[("booking_created", "booking")] is BookingCreatedPayload


# ---------------------------------------------------------------------------
# Phase 41 INFRA-35 — v1.6 payload schemas (11 new models)
# Behaviour contract (per D-41-20):
#   - extra='forbid' on every new payload (unknown key → ValidationError).
#   - audit_correlation_id: UUID | None on every new payload (async chain anchor).
#   - UUID fields accept both UUID(...) instances and str(uuid) (REG-36-03).
#   - No actor_email_snapshot field (D-41-09 — column-only, not payload).
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# EmailSentPayload — Phase 42 EMAIL-01
# ---------------------------------------------------------------------------


def test_email_sent_payload_round_trip() -> None:
    """EmailSentPayload accepts the EMAIL-01 kwarg set."""
    p = EmailSentPayload(
        audit_correlation_id=uuid4(),
        template_id="EMAIL_OTP_LOGIN",
        to_email="user@example.com",
        provider_message_id="msg-abc-123",
    )
    assert p.template_id == "EMAIL_OTP_LOGIN"
    assert p.to_email == "user@example.com"


def test_email_sent_payload_accepts_none_correlation_and_message_id() -> None:
    """audit_correlation_id is Optional (chain-starter); provider_message_id too."""
    p = EmailSentPayload(
        audit_correlation_id=None,
        template_id="EMAIL_OTP_LOGIN",
        to_email="user@example.com",
        provider_message_id=None,
    )
    assert p.audit_correlation_id is None
    assert p.provider_message_id is None


def test_email_sent_payload_rejects_extra_keys() -> None:
    """extra='forbid' enforced on EmailSentPayload."""
    with pytest.raises(ValidationError):
        EmailSentPayload(  # type: ignore[call-arg]
            audit_correlation_id=None,
            template_id="EMAIL_OTP_LOGIN",
            to_email="user@example.com",
            provider_message_id=None,
            spurious="nope",
        )


# ---------------------------------------------------------------------------
# EmailSendFailedPayload — Phase 42 EMAIL-04 / EMAIL-06
# ---------------------------------------------------------------------------


def test_email_send_failed_payload_round_trip() -> None:
    """EmailSendFailedPayload accepts every Literal reason."""
    for reason in (
        "provider_5xx",
        "circuit_open",
        "invalid_recipient",
        "bounce",
        "complaint",
    ):
        p = EmailSendFailedPayload(
            audit_correlation_id=uuid4(),
            template_id="EMAIL_OTP_LOGIN",
            to_email="user@example.com",
            reason=reason,  # type: ignore[arg-type]
            provider_error_code="E500",
        )
        assert p.reason == reason


def test_email_send_failed_payload_rejects_unknown_reason() -> None:
    """Literal reason rejects unknown values."""
    with pytest.raises(ValidationError):
        EmailSendFailedPayload(
            audit_correlation_id=None,
            template_id="EMAIL_OTP_LOGIN",
            to_email="user@example.com",
            reason="rate_limited",  # type: ignore[arg-type]
            provider_error_code=None,
        )


def test_email_send_failed_payload_rejects_extra_keys() -> None:
    with pytest.raises(ValidationError):
        EmailSendFailedPayload(  # type: ignore[call-arg]
            audit_correlation_id=None,
            template_id="EMAIL_OTP_LOGIN",
            to_email="user@example.com",
            reason="bounce",
            provider_error_code=None,
            spurious="nope",
        )


# ---------------------------------------------------------------------------
# UserInvitedPayload — Phase 43 USERS-03
# ---------------------------------------------------------------------------


def test_user_invited_payload_round_trip() -> None:
    p = UserInvitedPayload(
        audit_correlation_id=uuid4(),
        invited_user_id=uuid4(),
        invited_email="new@example.com",
        invited_role="reception",
        invitation_expires_at=datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC),
    )
    assert p.invited_role == "reception"
    assert isinstance(p.invited_user_id, UUID)


def test_user_invited_payload_rejects_extra_keys() -> None:
    with pytest.raises(ValidationError):
        UserInvitedPayload(  # type: ignore[call-arg]
            audit_correlation_id=None,
            invited_user_id=uuid4(),
            invited_email="new@example.com",
            invited_role="reception",
            invitation_expires_at=datetime(2026, 6, 1, tzinfo=UTC),
            spurious="nope",
        )


# ---------------------------------------------------------------------------
# UserInvitationAcceptedPayload — Phase 43 USERS-04
# ---------------------------------------------------------------------------


def test_user_invitation_accepted_payload_round_trip() -> None:
    p = UserInvitationAcceptedPayload(
        audit_correlation_id=uuid4(),
        accepted_user_id=uuid4(),
        invitation_token_id=uuid4(),
    )
    assert isinstance(p.accepted_user_id, UUID)
    assert isinstance(p.invitation_token_id, UUID)


def test_user_invitation_accepted_payload_rejects_extra_keys() -> None:
    with pytest.raises(ValidationError):
        UserInvitationAcceptedPayload(  # type: ignore[call-arg]
            audit_correlation_id=None,
            accepted_user_id=uuid4(),
            invitation_token_id=uuid4(),
            spurious="nope",
        )


# ---------------------------------------------------------------------------
# UserInvitationRevokedPayload — Phase 43 USERS-05
# ---------------------------------------------------------------------------


def test_user_invitation_revoked_payload_round_trip() -> None:
    p = UserInvitationRevokedPayload(
        audit_correlation_id=uuid4(),
        revoked_user_id=uuid4(),
        invitation_token_id=uuid4(),
        reason="email typo",
    )
    assert p.reason == "email typo"


def test_user_invitation_revoked_payload_accepts_none_reason() -> None:
    p = UserInvitationRevokedPayload(
        audit_correlation_id=None,
        revoked_user_id=uuid4(),
        invitation_token_id=uuid4(),
        reason=None,
    )
    assert p.reason is None


def test_user_invitation_revoked_payload_rejects_extra_keys() -> None:
    with pytest.raises(ValidationError):
        UserInvitationRevokedPayload(  # type: ignore[call-arg]
            audit_correlation_id=None,
            revoked_user_id=uuid4(),
            invitation_token_id=uuid4(),
            reason=None,
            spurious="nope",
        )


# ---------------------------------------------------------------------------
# UserDeactivatedPayload — Phase 43 USERS-06
# ---------------------------------------------------------------------------


def test_user_deactivated_payload_round_trip() -> None:
    p = UserDeactivatedPayload(
        audit_correlation_id=None,
        deactivated_user_id=uuid4(),
        sessions_revoked_count=3,
    )
    assert p.sessions_revoked_count == 3


def test_user_deactivated_payload_rejects_extra_keys() -> None:
    with pytest.raises(ValidationError):
        UserDeactivatedPayload(  # type: ignore[call-arg]
            audit_correlation_id=None,
            deactivated_user_id=uuid4(),
            sessions_revoked_count=0,
            spurious="nope",
        )


# ---------------------------------------------------------------------------
# UserReactivatedPayload / UserSoftDeletedPayload — Phase 43
# ---------------------------------------------------------------------------


def test_user_reactivated_payload_round_trip() -> None:
    p = UserReactivatedPayload(
        audit_correlation_id=None,
        reactivated_user_id=uuid4(),
    )
    assert isinstance(p.reactivated_user_id, UUID)


def test_user_reactivated_payload_rejects_extra_keys() -> None:
    with pytest.raises(ValidationError):
        UserReactivatedPayload(  # type: ignore[call-arg]
            audit_correlation_id=None,
            reactivated_user_id=uuid4(),
            spurious="nope",
        )


def test_user_soft_deleted_payload_round_trip() -> None:
    p = UserSoftDeletedPayload(
        audit_correlation_id=None,
        deleted_user_id=uuid4(),
    )
    assert isinstance(p.deleted_user_id, UUID)


def test_user_soft_deleted_payload_rejects_extra_keys() -> None:
    with pytest.raises(ValidationError):
        UserSoftDeletedPayload(  # type: ignore[call-arg]
            audit_correlation_id=None,
            deleted_user_id=uuid4(),
            spurious="nope",
        )


# ---------------------------------------------------------------------------
# PasswordResetRequestedPayload — Phase 44 RESET-01 (anti-oracle: both branches)
# ---------------------------------------------------------------------------


def test_password_reset_requested_payload_known_email_branch() -> None:
    """Known-email branch — target_user_id is set, email_hint optional."""
    p = PasswordResetRequestedPayload(
        audit_correlation_id=uuid4(),
        target_user_id=uuid4(),
        email_hint="user@example.com",
    )
    assert p.target_user_id is not None
    assert p.email_hint == "user@example.com"


def test_password_reset_requested_payload_unknown_email_branch() -> None:
    """RESET-01 anti-oracle: unknown-email branch — target_user_id=None.

    D-41-10 system-emit pattern: forensic chain still captured via email_hint.
    """
    p = PasswordResetRequestedPayload(
        audit_correlation_id=None,
        target_user_id=None,
        email_hint="stranger@example.com",
    )
    assert p.target_user_id is None
    assert p.email_hint == "stranger@example.com"


def test_password_reset_requested_payload_rejects_extra_keys() -> None:
    with pytest.raises(ValidationError):
        PasswordResetRequestedPayload(  # type: ignore[call-arg]
            audit_correlation_id=None,
            target_user_id=None,
            email_hint=None,
            spurious="nope",
        )


# ---------------------------------------------------------------------------
# PasswordResetCompletedPayload — Phase 44 RESET-02
# ---------------------------------------------------------------------------


def test_password_reset_completed_payload_round_trip() -> None:
    p = PasswordResetCompletedPayload(
        audit_correlation_id=uuid4(),
        user_id=uuid4(),
        sessions_revoked_count=2,
        token_id=uuid4(),
    )
    assert p.sessions_revoked_count == 2


def test_password_reset_completed_payload_rejects_extra_keys() -> None:
    with pytest.raises(ValidationError):
        PasswordResetCompletedPayload(  # type: ignore[call-arg]
            audit_correlation_id=None,
            user_id=uuid4(),
            sessions_revoked_count=0,
            token_id=uuid4(),
            spurious="nope",
        )


# ---------------------------------------------------------------------------
# PaymentReceiptEmailedPayload — Phase 45 NOTIFY-12
# ---------------------------------------------------------------------------


def test_payment_receipt_emailed_payload_round_trip() -> None:
    for kind in ("sale", "refund"):
        p = PaymentReceiptEmailedPayload(
            audit_correlation_id=uuid4(),
            payment_id=uuid4(),
            to_email="user@example.com",
            receipt_kind=kind,  # type: ignore[arg-type]
        )
        assert p.receipt_kind == kind


def test_payment_receipt_emailed_payload_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        PaymentReceiptEmailedPayload(
            audit_correlation_id=None,
            payment_id=uuid4(),
            to_email="user@example.com",
            receipt_kind="invoice",  # type: ignore[arg-type]
        )


def test_payment_receipt_emailed_payload_rejects_extra_keys() -> None:
    with pytest.raises(ValidationError):
        PaymentReceiptEmailedPayload(  # type: ignore[call-arg]
            audit_correlation_id=None,
            payment_id=uuid4(),
            to_email="user@example.com",
            receipt_kind="sale",
            spurious="nope",
        )


# ---------------------------------------------------------------------------
# UUID round-trip — REG-36-03 (UUIDs accept str(uuid) at emit time)
# ---------------------------------------------------------------------------


def test_v16_payloads_accept_uuid_as_str() -> None:
    """REG-36-03: every new UUID field must accept str(uuid) coercion."""
    uid = uuid4()
    p = UserInvitedPayload(
        audit_correlation_id=str(uid),  # type: ignore[arg-type]
        invited_user_id=str(uid),  # type: ignore[arg-type]
        invited_email="x@y.z",
        invited_role="owner",
        invitation_expires_at=datetime(2026, 6, 1, tzinfo=UTC),
    )
    assert p.invited_user_id == uid
    assert p.audit_correlation_id == uid


# ---------------------------------------------------------------------------
# Coverage gate — every v1.6 pair has a schema (Task 2)
# ---------------------------------------------------------------------------


def test_v16_pairs_all_have_payload_schemas() -> None:
    """Every Phase 41 v1.6 (event, resource_type) pair MUST resolve to a Pydantic schema.

    Mirrors the discipline of `test_v15_payload_schemas_registered` (Phase 37
    INFRA-25) with an additional anti-drift gate: every pair MUST also live in
    `LOCKED_AUDIT_EVENTS` so the runtime emitter cannot diverge from the
    payload-schema registry (D-15 / Phase 30 D-30-03 lineage).
    """
    from app.core.audit import LOCKED_AUDIT_EVENTS

    v16_pairs: list[tuple[str, str]] = [
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
    missing_from_locked = [p for p in v16_pairs if p not in LOCKED_AUDIT_EVENTS]
    missing_from_schemas = [p for p in v16_pairs if p not in AUDIT_PAYLOAD_SCHEMAS]
    assert not missing_from_locked, (
        f"v1.6 pairs missing from LOCKED_AUDIT_EVENTS: {missing_from_locked}"
    )
    assert not missing_from_schemas, (
        f"v1.6 pairs missing from AUDIT_PAYLOAD_SCHEMAS: {missing_from_schemas}"
    )
    # Spot-check the registry resolves to the expected class.
    assert AUDIT_PAYLOAD_SCHEMAS[("email_sent", "email_send_log")] is EmailSentPayload
    assert AUDIT_PAYLOAD_SCHEMAS[("user_invited", "user")] is UserInvitedPayload
    assert (
        AUDIT_PAYLOAD_SCHEMAS[("password_reset_requested", "user")] is PasswordResetRequestedPayload
    )
    assert (
        AUDIT_PAYLOAD_SCHEMAS[("payment_receipt_emailed", "payment")]
        is PaymentReceiptEmailedPayload
    )


# ---------------------------------------------------------------------------
# Phase 97 — ReferralBonusAccruedPayload (REFER-04 / INFRA-15)
# ---------------------------------------------------------------------------


def test_referral_bonus_accrued_event_is_locked() -> None:
    """("referral_bonus_accrued", "referral") must be in LOCKED_AUDIT_EVENTS (INFRA-15)."""
    from app.core.audit import LOCKED_AUDIT_EVENTS

    assert ("referral_bonus_accrued", "referral") in LOCKED_AUDIT_EVENTS


def test_referral_bonus_accrued_registry_maps_to_payload_class() -> None:
    """AUDIT_PAYLOAD_SCHEMAS maps ("referral_bonus_accrued", "referral") to the payload class."""
    assert (
        AUDIT_PAYLOAD_SCHEMAS[("referral_bonus_accrued", "referral")] is ReferralBonusAccruedPayload
    )


def test_referral_bonus_accrued_payload_valid_referrer_role() -> None:
    """A well-formed payload with role='referrer' validates without error."""
    p = ReferralBonusAccruedPayload(
        client_id=uuid4(),
        entry_id=uuid4(),
        amount_kopecks=50000,
        referral_capture_id=uuid4(),
        online_payment_id=uuid4(),
        role="referrer",
    )
    assert p.amount_kopecks == 50000
    assert p.role == "referrer"
    assert isinstance(p.client_id, UUID)


def test_referral_bonus_accrued_payload_valid_referee_role() -> None:
    """A well-formed payload with role='referee' validates without error."""
    p = ReferralBonusAccruedPayload(
        client_id=uuid4(),
        entry_id=uuid4(),
        amount_kopecks=30000,
        referral_capture_id=uuid4(),
        online_payment_id=uuid4(),
        role="referee",
    )
    assert p.role == "referee"
    assert isinstance(p.online_payment_id, UUID)


def test_referral_bonus_accrued_payload_rejects_extra_field() -> None:
    """extra='forbid' — unknown field raises ValidationError."""
    with pytest.raises(ValidationError):
        ReferralBonusAccruedPayload(  # type: ignore[call-arg]
            client_id=uuid4(),
            entry_id=uuid4(),
            amount_kopecks=50000,
            referral_capture_id=uuid4(),
            online_payment_id=uuid4(),
            role="referrer",
            spurious="nope",
        )


def test_referral_bonus_accrued_payload_rejects_invalid_role() -> None:
    """role must be Literal['referrer', 'referee'] — 'admin' raises ValidationError."""
    with pytest.raises(ValidationError):
        ReferralBonusAccruedPayload(
            client_id=uuid4(),
            entry_id=uuid4(),
            amount_kopecks=50000,
            referral_capture_id=uuid4(),
            online_payment_id=uuid4(),
            role="admin",  # type: ignore[arg-type]
        )


def test_referral_bonus_accrued_payload_rejects_missing_required_field() -> None:
    """Omitting a required field (referral_capture_id) raises ValidationError."""
    with pytest.raises(ValidationError):
        ReferralBonusAccruedPayload(  # type: ignore[call-arg]
            client_id=uuid4(),
            entry_id=uuid4(),
            amount_kopecks=50000,
            online_payment_id=uuid4(),
            role="referrer",
            # referral_capture_id intentionally omitted
        )
