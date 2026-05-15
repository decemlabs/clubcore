"""Payments module literal constants (Phase 32 D-32-09).

Subject-kind literals mirror the migration 0012_payments CHECK constraint
ck_payments_subject_kind. Service code references these constants instead
of bare strings so the AST-mismatch class of bugs is impossible.
"""

SUBJECT_KIND_MEMBERSHIP = "membership"
SUBJECT_KIND_PT_PACKAGE = "pt_package"
SUBJECT_KIND_REFUND = "refund"
SUBJECT_KIND_VALUES: tuple[str, ...] = (
    SUBJECT_KIND_MEMBERSHIP,
    SUBJECT_KIND_PT_PACKAGE,
    SUBJECT_KIND_REFUND,
)

__all__ = (
    "SUBJECT_KIND_MEMBERSHIP",
    "SUBJECT_KIND_PT_PACKAGE",
    "SUBJECT_KIND_REFUND",
    "SUBJECT_KIND_VALUES",
)
