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
