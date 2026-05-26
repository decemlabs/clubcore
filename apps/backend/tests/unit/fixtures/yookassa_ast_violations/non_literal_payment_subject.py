"""Synthetic AST-gate violation fixture (D-48-18).

Exercises ``test_non_literal_payment_subject_fixture_is_rejected``.

The file is intentionally NOT imported anywhere in production code — it
exists ONLY to feed the AST walker a known-bad callsite shape so the
gate's negative-test branch has measurable coverage.

NOTE: this file is allowed to fail ruff/mypy in isolation. CI excludes
tests/unit/fixtures/* from mypy via [[tool.mypy.overrides]] in
apps/backend/pyproject.toml (Phase 30 INFRA-22 pattern).
"""

# mypy: ignore-errors
# ruff: noqa
from typing import Any


def build_receipt_item(**kwargs: Any) -> dict[str, Any]:  # stub for syntactic parsing
    return {}


chosen_subject = "service"  # variable — violates D-48-18

_ = build_receipt_item(
    description="x",
    amount_kopecks=100,
    payment_subject=chosen_subject,  # AST gate must reject this line
    payment_mode=None,
    vat_code=1,
)
