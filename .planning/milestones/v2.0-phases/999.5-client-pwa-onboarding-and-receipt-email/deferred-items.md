# Deferred Items — Phase 999.5

## Pre-existing test pollution in online_payments service-sell suites (out of scope, Plan 999.5-06)

**Discovered during:** Plan 999.5-06 execution (verification step).

**Symptom:** 11 tests in `tests/modules/online_payments/test_service_sell_membership.py`
and `test_service_sell_pt_package.py` fail when run as a suite against the host
`clubcore` Postgres:

- `test_sell_*_phone_only_client_proceeds_d10`
- `test_sell_*_validation_error_no_db_row`
- `test_sell_*_transient_error_503`
- `test_sell_*_permanent_error_502`
- `test_sell_*_replay_redirect_returns_existing_row`
- `test_sell_*_replay_qr_refetches_and_returns_qr_payload`

**Root cause:** These tests use unscoped `select(OnlinePayment)` and assert absolute
row counts (`assert len(rows) == 1` / `assert rows == []`). The host `clubcore` DB
carries leftover `online_payments` rows committed OUTSIDE the per-test SAVEPOINT
during prior manual PWA UAT sessions, so the absolute counts are off. Each test
passes in isolation against a clean DB.

**Proof it is pre-existing (NOT caused by 999.5-06):** the identical 11 failures
reproduce on the `master` main checkout with none of the 999.5-06 changes applied
(`apps/backend` at HEAD, same env).

**Why not fixed here (SCOPE BOUNDARY):** the affected tests are not in this plan's
`files_modified`, and the failures are unrelated to the Idempotence-Key collision
retry. The new test file added by this plan
(`test_idempotency_key_collision_retry.py`) deliberately scopes its row queries to
the per-test `client_id` so it is robust against this pollution.

**Suggested fix (future):** scope these legacy assertions to the test's `client_id`
(same pattern as the new collision-retry tests), or truncate `online_payments`
in a session-scoped fixture. Track as a test-hardening chore.
