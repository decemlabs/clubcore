"""Payments module literal constants (Phase 32 D-32-09).

Subject-kind literals mirror the migration 0012_payments CHECK constraint
ck_payments_subject_kind. Service code references these constants instead
of bare strings so the AST-mismatch class of bugs is impossible.

Phase 63 DEBT-03: ``Literal[...]`` annotations are explicit so callers
that pass these constants into ``Literal["membership", "pt_package"]``
parameters (e.g. ``SettledRefundLocals.subject_kind``) type-check under
mypy --strict without ``# type: ignore`` (D-63-06).
"""

from typing import Final, Literal

SUBJECT_KIND_MEMBERSHIP: Final[Literal["membership"]] = "membership"
SUBJECT_KIND_PT_PACKAGE: Final[Literal["pt_package"]] = "pt_package"
SUBJECT_KIND_REFUND: Final[Literal["refund"]] = "refund"
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
