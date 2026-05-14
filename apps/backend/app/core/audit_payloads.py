"""Audit payload schemas (INFRA-23 / Phase 30 / D-30-03).

Strict Pydantic-v2 BaseModel per audit event for the 17 new v1.4 events.
`audit.emit()` looks up `(event, resource_type)` in `AUDIT_PAYLOAD_SCHEMAS`
and calls `Schema.model_validate(payload_kwargs)` BEFORE structlog/DB writes.
Mirrors the D-09 hard-fail discipline of `AuditEventNotLockedError`:
unknown payload key OR missing required key → pydantic.ValidationError
(programmer error, not graceful degradation).

Scope (D-30-02): ONLY v1.4 events are locked. The 34 existing v1.1-v1.3
logical events remain free-form (back-compat); `audit.emit()` validates
payload only when `(event, resource_type)` is present in this registry.

Pydantic base-class divergence (rationale):
    Audit payloads are internal kwargs (snake_case Python identifiers),
    NOT camelCase wire DTOs. Therefore each schema inherits plain
    `pydantic.BaseModel` with `model_config = ConfigDict(extra="forbid")` —
    NOT `app.core.schemas.BackendSchemaBase` (which auto-aliases via
    `to_camel`). The `extra="forbid"` is the load-bearing invariant
    per D-30-01.

`payment_row_hash` (D-30-04): SHA-256 of canonical-JSON of the original
payment row, prefixed with `sha256:`. Canonicalization algorithm is
pencilled in for Phase 32 / Plan 03 (helper module `app.core.audit_hash`
exposes `payment_row_hash(row: dict) -> str` returning
`"sha256:<64-hex>"`). Field pattern constraint `^sha256:[0-9a-f]{64}$`
is locked here.

Architectural boundary: app.core.audit_payloads MUST NOT import from
app.modules.* (importlinter `core-not-depend-on-modules` contract).
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Trainers lifecycle (Phase 31 TRN-07)
# ---------------------------------------------------------------------------


class TrainerCreatedPayload(BaseModel):
    """Payload schema for ("trainer_created", "trainer") — TRN-07."""

    model_config = ConfigDict(extra="forbid")

    trainer_id: UUID
    full_name: str
    phone: str | None


class TrainerUpdatedPayload(BaseModel):
    """Payload schema for ("trainer_updated", "trainer") — TRN-07."""

    model_config = ConfigDict(extra="forbid")

    trainer_id: UUID
    changed_fields: list[str]


class TrainerDeactivatedPayload(BaseModel):
    """Payload schema for ("trainer_deactivated", "trainer") — TRN-07."""

    model_config = ConfigDict(extra="forbid")

    trainer_id: UUID


class TrainerReactivatedPayload(BaseModel):
    """Payload schema for ("trainer_reactivated", "trainer") — TRN-07."""

    model_config = ConfigDict(extra="forbid")

    trainer_id: UUID


# ---------------------------------------------------------------------------
# Payments + refund + membership refund (Phase 32 PAY-10 / REF-07)
# ---------------------------------------------------------------------------


class PaymentRecordedPayload(BaseModel):
    """Payload schema for ("payment_recorded", "payment") — PAY-10.

    Verbatim per REQUIREMENTS.md §PAY-10:
        {payment_id, subject_kind, subject_id, amount_kopecks, method,
         received_by_user_id, payment_row_hash}.

    `payment_row_hash` (D-30-04): SHA-256 canonical-JSON of the payment row,
    prefixed `sha256:` — pattern `^sha256:[0-9a-f]{64}$`.
    """

    model_config = ConfigDict(extra="forbid")

    payment_id: UUID
    subject_kind: str = Field(pattern=r"^(membership|pt_package|refund)$")
    subject_id: UUID
    amount_kopecks: int
    method: str
    received_by_user_id: UUID
    # D-30-04: SHA-256 of canonical-JSON of the original payment row.
    payment_row_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class RefundIssuedPayload(BaseModel):
    """Payload schema for ("refund_issued", "payment") — REF-07.

    `amount_kopecks` is negative (refund row in append-only payments ledger).
    `payment_row_hash` (D-30-04): SHA-256 of canonical-JSON of the ORIGINAL
    payment row being refunded — forensic chain-of-custody.
    """

    model_config = ConfigDict(extra="forbid")

    payment_id: UUID
    refund_of_payment_id: UUID
    amount_kopecks: int
    subject_kind: str = Field(pattern=r"^(membership|pt_package)$")
    subject_id: UUID
    received_by_user_id: UUID
    reason: str
    # D-30-04: SHA-256 of canonical-JSON of the ORIGINAL refunded payment row.
    payment_row_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class MembershipRefundedPayload(BaseModel):
    """Payload schema for ("membership_refunded", "membership") — REF-07."""

    model_config = ConfigDict(extra="forbid")

    membership_id: UUID
    client_id: UUID
    refund_payment_id: UUID
    reason: str


# ---------------------------------------------------------------------------
# PT-package plans lifecycle (Phase 33 PT-03)
# ---------------------------------------------------------------------------


class PtPackagePlanCreatedPayload(BaseModel):
    """Payload schema for ("pt_package_plan_created", "pt_package_plan") — PT-03."""

    model_config = ConfigDict(extra="forbid")

    plan_id: UUID
    name: str
    session_count: int
    price_kopecks: int
    validity_days: int | None


class PtPackagePlanUpdatedPayload(BaseModel):
    """Payload schema for ("pt_package_plan_updated", "pt_package_plan") — PT-03."""

    model_config = ConfigDict(extra="forbid")

    plan_id: UUID
    changed_fields: list[str]


class PtPackagePlanArchivedPayload(BaseModel):
    """Payload schema for ("pt_package_plan_archived", "pt_package_plan") — PT-03."""

    model_config = ConfigDict(extra="forbid")

    plan_id: UUID


# ---------------------------------------------------------------------------
# PT-package instances lifecycle (Phase 33 PT-13)
# ---------------------------------------------------------------------------


class PtPackageSoldPayload(BaseModel):
    """Payload schema for ("pt_package_sold", "pt_package") — PT-13."""

    model_config = ConfigDict(extra="forbid")

    pt_package_id: UUID
    client_id: UUID
    plan_id: UUID
    session_count_snapshot: int
    price_kopecks_snapshot: int
    validity_days_snapshot: int | None
    payment_id: UUID


class PtPackageCancelledPayload(BaseModel):
    """Payload schema for ("pt_package_cancelled", "pt_package") — PT-13."""

    model_config = ConfigDict(extra="forbid")

    pt_package_id: UUID
    client_id: UUID
    cancellation_reason: str


class PtPackageRefundedPayload(BaseModel):
    """Payload schema for ("pt_package_refunded", "pt_package") — REF-07."""

    model_config = ConfigDict(extra="forbid")

    pt_package_id: UUID
    client_id: UUID
    refund_payment_id: UUID
    reason: str


class PtPackageExhaustedPayload(BaseModel):
    """Payload schema for ("pt_package_exhausted", "pt_package") — PT-13."""

    model_config = ConfigDict(extra="forbid")

    pt_package_id: UUID
    client_id: UUID


class PtPackageExpiredPayload(BaseModel):
    """Payload schema for ("pt_package_expired", "pt_package") — PT-13.

    `end_date` is the ISO date string (YYYY-MM-DD) on which the package
    became expired (snapshot from `pt_packages.end_date` at expiry).
    """

    model_config = ConfigDict(extra="forbid")

    pt_package_id: UUID
    client_id: UUID
    end_date: str


# ---------------------------------------------------------------------------
# PT-sessions lifecycle (Phase 34 PT-21)
# ---------------------------------------------------------------------------


class PtSessionRecordedPayload(BaseModel):
    """Payload schema for ("pt_session_recorded", "pt_session") — PT-21.

    `trainer_name_snapshot` (B-05) captures the trainer display name at
    recording time so historical UI integrity survives trainer rename /
    deactivation.
    `performed_at` is ISO-8601 datetime string with timezone offset.
    """

    model_config = ConfigDict(extra="forbid")

    pt_session_id: UUID
    pt_package_id: UUID
    client_id: UUID
    trainer_id: UUID
    trainer_name_snapshot: str
    performed_at: str
    performed_by_user_id: UUID
    sessions_remaining_after: int


class PtSessionCancelledPayload(BaseModel):
    """Payload schema for ("pt_session_cancelled", "pt_session") — PT-21.

    `package_reactivated` flags whether the parent pt_package transitioned
    `exhausted → active` as part of the same UoW (PT-18 semantics).
    """

    model_config = ConfigDict(extra="forbid")

    pt_session_id: UUID
    pt_package_id: UUID
    client_id: UUID
    cancel_reason: str
    sessions_remaining_after: int
    package_reactivated: bool


# ---------------------------------------------------------------------------
# Registry — single canonical (event, resource_type) → Pydantic schema map.
# Mirrors LOCKED_AUDIT_EVENTS tuple-key shape (`audit.py:102-157`) so the
# lookup in `audit.emit()` is a single `.get((event, resource_type))`.
# ---------------------------------------------------------------------------


AUDIT_PAYLOAD_SCHEMAS: dict[tuple[str, str], type[BaseModel]] = {
    # Trainers (Phase 31 TRN-07)
    ("trainer_created", "trainer"): TrainerCreatedPayload,
    ("trainer_updated", "trainer"): TrainerUpdatedPayload,
    ("trainer_deactivated", "trainer"): TrainerDeactivatedPayload,
    ("trainer_reactivated", "trainer"): TrainerReactivatedPayload,
    # Payments + refunds (Phase 32 PAY-10 / REF-07)
    ("payment_recorded", "payment"): PaymentRecordedPayload,
    ("refund_issued", "payment"): RefundIssuedPayload,
    ("membership_refunded", "membership"): MembershipRefundedPayload,
    # PT-package plans (Phase 33 PT-03)
    ("pt_package_plan_created", "pt_package_plan"): PtPackagePlanCreatedPayload,
    ("pt_package_plan_updated", "pt_package_plan"): PtPackagePlanUpdatedPayload,
    ("pt_package_plan_archived", "pt_package_plan"): PtPackagePlanArchivedPayload,
    # PT-package instances (Phase 33 PT-13)
    ("pt_package_sold", "pt_package"): PtPackageSoldPayload,
    ("pt_package_cancelled", "pt_package"): PtPackageCancelledPayload,
    ("pt_package_refunded", "pt_package"): PtPackageRefundedPayload,
    ("pt_package_exhausted", "pt_package"): PtPackageExhaustedPayload,
    ("pt_package_expired", "pt_package"): PtPackageExpiredPayload,
    # PT-sessions (Phase 34 PT-21)
    ("pt_session_recorded", "pt_session"): PtSessionRecordedPayload,
    ("pt_session_cancelled", "pt_session"): PtSessionCancelledPayload,
}
