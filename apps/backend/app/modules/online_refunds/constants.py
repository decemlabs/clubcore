"""Online refunds module literal constants (Phase 51 D-51-07 / D-51-08).

Status literals are pinned to the 0037 migration CHECK constraint values —
cross-module pinning enforced by runtime CHECK + this file anchoring on the
migration literal (mirrors app/modules/online_payments/constants.py lineage).

No SUBJECT_KIND_* constants (refund dispatches on parent OnlinePayment's XOR
per D-51-11). No CONFIRMATION_TYPE_* (no user redirect for refunds).
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType


class ErrorCode(StrEnum):
    """Phase 51 service-layer error codes (locked literals).

    Note: refund inherits customer email from parent OnlinePayment per D-51-08
    — there is no `CLIENT_EMAIL_REQUIRED` member here.
    """

    ORIGINAL_PAYMENT_NOT_FOUND = "original_payment_not_found"
    ONLINE_PAYMENT_NOT_FOUND = "online_payment_not_found"
    YOOKASSA_VALIDATION_ERROR = "yookassa_validation_error"
    YOOKASSA_UNAVAILABLE = "yookassa_unavailable"
    YOOKASSA_PERMANENT_ERROR = "yookassa_permanent_error"


STATUS_PENDING = "pending"
STATUS_SUCCEEDED = "succeeded"
STATUS_CANCELED = "canceled"
STATUS_VALUES: tuple[str, ...] = (STATUS_PENDING, STATUS_SUCCEEDED, STATUS_CANCELED)

# ─────────────────────────────────────────────────────────────────────────────
# Phase 51 D-51-07 — Declarative FSM transitions for online_refunds.
# Byte-for-byte mirror of ONLINE_PAYMENT_STATUS_TRANSITIONS (Phase 50 D-50-15)
# consumed by the refund webhook + poll-cron transition guards (Plans 51-07,
# 51-09). Terminal states are explicit (empty frozenset) so the guard rejects
# re-transitions of finalised rows.
# ─────────────────────────────────────────────────────────────────────────────
ONLINE_REFUND_STATUS_TRANSITIONS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        STATUS_PENDING: frozenset({STATUS_SUCCEEDED, STATUS_CANCELED}),
        STATUS_SUCCEEDED: frozenset(),  # terminal
        STATUS_CANCELED: frozenset(),  # terminal
    }
)


__all__ = (
    "ONLINE_REFUND_STATUS_TRANSITIONS",
    "STATUS_CANCELED",
    "STATUS_PENDING",
    "STATUS_SUCCEEDED",
    "STATUS_VALUES",
    "ErrorCode",
)
