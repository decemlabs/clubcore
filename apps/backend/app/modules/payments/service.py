"""Payments service placeholder (Phase 30 INFRA-21 / B-01).

Empty body — SVC001 commit-gate walker scope target. Substantive write paths
(`record_payment`, `issue_refund`) land in Phase 32.

Append-only invariant (B-01 / INFRA-22): any future function in this file
MUST NOT call `update(Payment)`, `delete(Payment)`,
`session.execute(update|delete(Payment)...)`, `session.delete(<Payment instance>)`,
or `on_conflict_do_update(Payment)`. Enforced at CI by
`tests/unit/test_payments_appendonly.py`.
"""
