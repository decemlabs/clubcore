"""Payroll module constants (Phase 58 D-58-19 / D-58-21).

`PAYMENT_SUBJECT_KIND_PT_PACKAGE` is the subject-kind literal passed to
cross-module raw-SQL `text()` SELECTs in payroll/repository.py. The
importlinter modules-independent contract forbids
`app.modules.payroll -> app.modules.payments`, so we cannot import
`payments.constants.SUBJECT_KIND_PT_PACKAGE` here. The literal must match
the migration 0012_payments CHECK constraint ck_payments_subject_kind value
'pt_package'; payments.constants.SUBJECT_KIND_PT_PACKAGE is the same string.
Cross-module pinning is enforced by the runtime CHECK and by both modules
anchoring on the migration value (mirrors pt_packages D-33 / memberships D-32-09).

Error codes (D-58-07 / D-58-06 / D-58-08):
- `ERROR_COMP_CONFIG_MISSING` — raised by run_payroll_period when no active
  comp config exists for the trainer as of period_end (422).
- `ERROR_PAYROLL_PERIOD_ALREADY_RUN` — raised by run_payroll_period on
  ON CONFLICT idempotency collision (409, D-58-06).
- `ERROR_ALREADY_PAID` — raised by mark_accrual_paid on second attempt (409,
  D-58-08).
"""

# Mirror pt_packages.constants.PAYMENT_SUBJECT_KIND_PT_PACKAGE (D-33 / D-58-19).
# Importlinter forbids importing payments.constants here — literal pinned to
# migration 0012_payments CHECK ck_payments_subject_kind value.
PAYMENT_SUBJECT_KIND_PT_PACKAGE = "pt_package"

# Error codes (snake_case per project convention — D-58-07)
ERROR_COMP_CONFIG_MISSING = "comp_config_missing"
ERROR_PAYROLL_PERIOD_ALREADY_RUN = "payroll_period_already_run"
ERROR_ALREADY_PAID = "already_paid"

__all__ = [
    "ERROR_ALREADY_PAID",
    "ERROR_COMP_CONFIG_MISSING",
    "ERROR_PAYROLL_PERIOD_ALREADY_RUN",
    "PAYMENT_SUBJECT_KIND_PT_PACKAGE",
]
