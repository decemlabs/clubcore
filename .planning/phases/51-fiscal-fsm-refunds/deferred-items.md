# Phase 51 — Deferred Items

Pre-existing tech-debt items discovered during plan execution that are out
of scope for the current task.

## From 51-03 (YooKassaClient.create_receipt) execution

### Pre-existing ruff errors in tests/integrations/yookassa/conftest.py

Found while running the plan 51-03 acceptance criterion
``uv run ruff check tests/integrations/yookassa/``. The two errors below
exist on the wave-base commit (a4392fcd) and are unrelated to the
``create_receipt`` work:

1. **S110** — `try`/`except`/`pass` in ``_reset_structlog_for_capture``
   fixture (line 57). Best-effort isolation that intentionally swallows
   exceptions; the existing inline comment explains the rationale.

2. **RUF100** — unused ``# noqa: BLE001`` directive on the same line; the
   BLE001 rule is no longer enabled in the project ruff config but the
   directive remained.

Both are documentation/style issues only. They do not affect runtime
behavior of any test. Sweep target: DEFER-46-04 (the ruff tree-wide
cleanup queued for v1.9).

## From 51-08 (initiate_online_refund + POST endpoints) execution

### Pre-existing mypy errors in app/modules/online_payments/router.py

Found while running the plan 51-08 acceptance criterion
``uv run mypy --strict app/modules/online_payments/router.py``. Four
errors all in pre-existing Phase 49 sell endpoints (lines 219, 268, 314,
357) — ``Argument "confirmation_type" to "sell_membership"/"sell_pt_package"
has incompatible type "str"; expected "Literal['redirect', 'qr']"``. None
trace to the Phase 51 refund endpoints appended by plan 51-08 (lines 401+).
Sweep target: DEFER-46-04 (v1.9 tech-debt sweep).

### Pre-existing route_introspection gate-test failure

Found while running ``uv run pytest tests/integration/test_route_introspection.py``.
3 routes missing the auth gate per introspection: ``/api/v1/auth/password-reset/request``,
``/api/v1/auth/password-reset/confirm``, ``/api/v1/users/invitations/accept``.
All three exist on the wave-base commit (4b7148d2) and are unrelated to
the Phase 51 refund endpoints (which the test correctly recognises as
gated). They are anonymous-by-design endpoints that should likely be
added to ``EXCLUDED_PATHS`` (mirror of the existing ``/api/v1/auth/otp/request``
exclusion at line 35). Surface for Phase 53 verification follow-up or
DEFER-46-04 tech-debt sweep.

## From 51-10 (E2E + regression sweep) execution

### DEFER-51-01 (open): orphan refund webhook reconciliation

When ЮKassa sends ``refund.succeeded`` for a refund whose ``OnlineRefund`` row does not
exist (e.g., refund created directly via the ЮKassa dashboard), the handler currently
logs a WARNING + emits an audit row with ``idempotency_outcome='orphan'``. Full automated
reconciliation (look up by payment_id or create a synthetic ``OnlineRefund`` row) is
deferred to Phase 53 until the scenario frequency in production is known.

### DEFER-51-02 (open): dedicated audit event for ЮKassa call failures

Phase 51 emits structlog WARNINGs on transient/permanent ЮKassa error classifications
during fiscal-receipt dispatch and refund-poll cron. A dedicated audit-DB row event
(``yookassa_call_failed``) was considered but not emitted — only the structlog line is
written. Defer to Phase 53 cleanup unless verification flags as a gap in the audit trail.

### DEFER-50-04 (CLOSED): _post_commit_enqueue fiscal-dispatch stub

Closed by plan 51-06. The stub implementation has been replaced with the real
ARQ-enqueue path. Verified by ``tests/integration/fiscal_receipts/test_e2e_fiscal_receipt_full_cycle.py``.

### Carry-forward items (unchanged from Phase 50)

| ID | Description | Target |
|----|-------------|--------|
| DEFER-50-01 | payment.waiting_for_capture — not handled | Phase 53 |
| DEFER-50-02 | orphan-recovery cron (payment.succeeded for unknown payment) | Phase 53 |
| DEFER-50-03 | cancellation_reason enum + operator runbook | Phase 53 |
| DEFER-50-05 | test_alembic_clean pre-existing failure | Phase 53 |
| DEFER-46-03 | cron-chain circuit-breaker re-run (now naturally exercised by FISCAL-05) | Phase 53 |
| NOT-02, NOT-04 | notification branches (Telegram DM on payment events) | Phase 52 |
| v1.4 B-02 | partial refund (refund less than full amount) | v1.8+ |

### E2E real-commit engine test isolation issue

The 4 E2E test files added in this plan use a ``real_commit_engine`` pattern (not
SAVEPOINT rollback) because the handlers use ``async with session.begin()``. When the
full test suite runs, leftover DB connections from the E2E engines cause transient
failures in unrelated tests that run AFTER the E2E tests in the same pytest session.
All 21 plan-51-10 tests pass when run in isolation or as a group. The cross-contamination
is a test-ordering issue only; it does not affect production code correctness.
Deferred to Phase 53 to restructure E2E fixtures with proper engine disposal teardown.
