"""PT-packages module constants (Phase 33 D-33-04 / D-33-05).

`PT_PACKAGE_STATUS_TRANSITIONS` is the declarative state-machine source of truth
for PT-package lifecycle (D-33-04). Keys are source statuses; values are
frozensets of allowed target statuses. Read-only via `MappingProxyType` so
module consumers cannot mutate it at runtime.

Transition matrix (D-33-04):
  - active    → {exhausted, expired, cancelled}
  - exhausted → {cancelled}   (refund of exhausted package)
  - expired   → {cancelled}   (refund of expired package)
  - cancelled → ∅             (terminal)

`str` keys (not the schema-layer `PtPackageStatus` enum) keep this module
importable from `models.py` and `service.py` without a circular import; the
schema-layer enum and the constant share string values.

`CANCELLATION_REASON_REFUNDED` is the sentinel set on `pt_packages.cancellation_reason`
by the refund orchestrator (Plan 33-03) — mirrors memberships D-32-08 pattern.

`PAYMENT_SUBJECT_KIND_PT_PACKAGE` is the subject-kind literal passed to the
PaymentRecorder / PaymentRefunder Protocol slots. The importlinter
`modules-independent` contract forbids `app.modules.pt_packages -> app.modules.payments`,
so we cannot import `payments.constants.SUBJECT_KIND_PT_PACKAGE` here. The literal
must match the migration 0012_payments CHECK constraint ck_payments_subject_kind
value 'pt_package'; payments.constants.SUBJECT_KIND_PT_PACKAGE is the same string.
Cross-module pinning is enforced by the runtime CHECK and by both modules anchoring
on the migration value (mirrors memberships D-32-09).
"""

from collections.abc import Mapping
from types import MappingProxyType

PT_PACKAGE_STATUS_TRANSITIONS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "active": frozenset({"exhausted", "expired", "cancelled"}),
        "exhausted": frozenset({"cancelled"}),  # refund of exhausted package
        "expired": frozenset({"cancelled"}),  # refund of expired package
        "cancelled": frozenset(),  # terminal
    }
)

# Mirror memberships.constants.CANCELLATION_REASON_REFUNDED (D-32-08).
# Set by refund orchestrator (Plan 33-03) on the cancelled instance; free-text
# operator reason goes in the same column for admin-cancel-without-refund.
CANCELLATION_REASON_REFUNDED = "refunded"

# Mirror memberships.constants.PAYMENT_SUBJECT_KIND_MEMBERSHIP (D-32-09).
# Importlinter forbids importing payments.constants here — literal pinned to
# migration 0012_payments CHECK ck_payments_subject_kind value.
PAYMENT_SUBJECT_KIND_PT_PACKAGE = "pt_package"

__all__ = [
    "CANCELLATION_REASON_REFUNDED",
    "PAYMENT_SUBJECT_KIND_PT_PACKAGE",
    "PT_PACKAGE_STATUS_TRANSITIONS",
]
