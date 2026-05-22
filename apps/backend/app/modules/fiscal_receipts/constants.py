"""Fiscal receipts module declarative-FSM constants (Phase 50 D-50-32).

Mirrors app/modules/memberships/constants.py:22 shape; Phase 50 inserts
rows directly as 'sent' (D-50-18 step 5); the 'pending' → 'sent' edge
exists for Phase 51 ARQ retry flow where a row may be re-INSERTed as
'pending' after dispatch failure.

The literal values are pinned to the 0035_fiscal_receipts migration CHECK
constraint enum (``status IN ('pending','sent','succeeded','failed')``);
cross-module pinning is enforced by the runtime DB CHECK and by both the
migration + this file anchoring on the same literal strings (mirrors the
app/modules/online_payments/constants.py and memberships/constants.py
lineage).
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

KIND_PAYMENT = "payment"
KIND_REFUND = "refund"
KIND_VALUES: tuple[str, ...] = (KIND_PAYMENT, KIND_REFUND)

STATUS_PENDING = "pending"
STATUS_SENT = "sent"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"
STATUS_VALUES: tuple[str, ...] = (
    STATUS_PENDING,
    STATUS_SENT,
    STATUS_SUCCEEDED,
    STATUS_FAILED,
)

FISCAL_RECEIPT_STATUS_TRANSITIONS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        STATUS_PENDING: frozenset({STATUS_SENT}),
        STATUS_SENT: frozenset({STATUS_SUCCEEDED, STATUS_FAILED}),
        STATUS_SUCCEEDED: frozenset(),  # terminal
        STATUS_FAILED: frozenset(),  # terminal
    }
)

__all__ = (
    "FISCAL_RECEIPT_STATUS_TRANSITIONS",
    "KIND_PAYMENT",
    "KIND_REFUND",
    "KIND_VALUES",
    "STATUS_FAILED",
    "STATUS_PENDING",
    "STATUS_SENT",
    "STATUS_SUCCEEDED",
    "STATUS_VALUES",
)
