"""Online payments module literal constants (Phase 49 D-49-01 / Claude's discretion).

Status / confirmation_type / subject_kind literals are pinned to the 0034
migration CHECK constraint values — cross-module pinning enforced by runtime
CHECK + this file anchoring on the migration literal (mirrors
app/modules/payments/constants.py lineage).
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType


class ErrorCode(StrEnum):
    """Phase 49 service-layer error codes (locked literals)."""

    CLIENT_EMAIL_REQUIRED = "client_email_required_for_online_payment"
    YOOKASSA_VALIDATION_ERROR = "yookassa_validation_error"
    YOOKASSA_UNAVAILABLE = "yookassa_unavailable"
    YOOKASSA_PERMANENT_ERROR = "yookassa_permanent_error"


STATUS_PENDING = "pending"
STATUS_SUCCEEDED = "succeeded"
STATUS_CANCELED = "canceled"
STATUS_VALUES: tuple[str, ...] = (STATUS_PENDING, STATUS_SUCCEEDED, STATUS_CANCELED)

CONFIRMATION_TYPE_REDIRECT = "redirect"
CONFIRMATION_TYPE_QR = "qr"
CONFIRMATION_TYPE_VALUES: tuple[str, ...] = (
    CONFIRMATION_TYPE_REDIRECT,
    CONFIRMATION_TYPE_QR,
)

SUBJECT_KIND_MEMBERSHIP = "membership"
SUBJECT_KIND_PT_PACKAGE = "pt_package"
SUBJECT_KIND_VALUES: tuple[str, ...] = (
    SUBJECT_KIND_MEMBERSHIP,
    SUBJECT_KIND_PT_PACKAGE,
)

# ─────────────────────────────────────────────────────────────────────────────
# Phase 50 D-50-15 / WH-04 — Declarative FSM transitions for online_payments.
# Byte-for-byte mirror of MEMBERSHIP_STATUS_TRANSITIONS (Phase 16 / Phase 24)
# consumed by app/api/v1/_internal/yookassa/handlers.py:_assert_can_transition
# (D-50-16). Terminal states are explicit (empty frozenset) so the guard
# rejects re-transitions of finalised rows.
# ─────────────────────────────────────────────────────────────────────────────
ONLINE_PAYMENT_STATUS_TRANSITIONS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        STATUS_PENDING: frozenset({STATUS_SUCCEEDED, STATUS_CANCELED}),
        STATUS_SUCCEEDED: frozenset(),  # terminal
        STATUS_CANCELED: frozenset(),  # terminal
    }
)


__all__ = (
    "CONFIRMATION_TYPE_QR",
    "CONFIRMATION_TYPE_REDIRECT",
    "CONFIRMATION_TYPE_VALUES",
    "ONLINE_PAYMENT_STATUS_TRANSITIONS",
    "STATUS_CANCELED",
    "STATUS_PENDING",
    "STATUS_SUCCEEDED",
    "STATUS_VALUES",
    "SUBJECT_KIND_MEMBERSHIP",
    "SUBJECT_KIND_PT_PACKAGE",
    "SUBJECT_KIND_VALUES",
    "ErrorCode",
)
