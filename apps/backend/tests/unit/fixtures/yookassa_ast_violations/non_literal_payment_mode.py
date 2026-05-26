"""Synthetic AST-gate violation fixture (D-48-18) — payment_mode variant.

Exercises ``test_non_literal_payment_mode_fixture_is_rejected``.

NOTE: this file is allowed to fail ruff/mypy in isolation. CI excludes
tests/unit/fixtures/* from mypy via [[tool.mypy.overrides]] in
apps/backend/pyproject.toml (Phase 30 INFRA-22 pattern).
"""

# mypy: ignore-errors
# ruff: noqa
from typing import Any


def build_receipt_item(**kwargs: Any) -> dict[str, Any]:
    return {}


chosen_mode = "full_payment"  # variable — violates D-48-18

_ = build_receipt_item(
    description="x",
    amount_kopecks=100,
    payment_subject=None,
    payment_mode=chosen_mode,  # AST gate must reject this line
    vat_code=1,
)
