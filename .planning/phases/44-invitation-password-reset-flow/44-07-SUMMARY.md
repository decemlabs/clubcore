---
phase: 44-invitation-password-reset-flow
plan: 07
subsystem: auth/password-reset
tags:
  - integration-test
  - atomic-consume
  - rate-limit
  - anti-oracle
  - structlog-caplog
dependency-graph:
  requires: [44-01, 44-02, 44-03, 44-04, 44-05]
  provides:
    - RESET-02 integration coverage (atomic-consume + revoke-all + audit)
    - RESET-01 rate-limit topology integration coverage (3 Redis keys)
    - AppError envelope shape pinned for Wave 4 sibling tests (44-08, 44-09)
  affects: []
tech-stack:
  added: []
  patterns:
    - structlog logger-cache reset (`del _log.__dict__["bind"]`) duplicated per test file
    - SAVEPOINT-per-test isolation via shared `db_session` (D-41-18)
    - byte-identical body parity assertion (`r.content == reference.content`)
    - `structlog.testing.capture_logs()` for ops-visibility WARN capture
key-files:
  created:
    - apps/backend/tests/integration/auth/test_password_reset_confirm.py
    - apps/backend/tests/integration/auth/test_password_reset_rate_limit.py
  modified: []
decisions:
  - "Used `redis.delete(email_min_key)` between iterations in the per-email-hour test to isolate that single key instead of waiting 60s — the plan suggested this as the simpler alternative."
  - "Kept docstring + test-name references to `429` (4 occurrences in `test_password_reset_rate_limit.py`) so the D-44-11 anti-oracle invariant is grep-discoverable; no actual `429` assertions exist."
  - "Logger-cache reset fixture duplicated locally per test file rather than promoted to the auth conftest — keeps the conftest minimal and the rationale visible at the callsite."
metrics:
  duration: 28m
  completed: 2026-05-20
requirements:
  - RESET-01
  - RESET-02
---

# Phase 44 Plan 07: Password-Reset Confirm + Rate-Limit Integration Tests Summary

7 integration tests covering RESET-02 (atomic-consume + revoke-all + audit) and RESET-01 (3-key rate-limit topology with anti-oracle 202-not-429 invariant) — all green against real Postgres + real Redis via the project's SAVEPOINT-per-test isolation.

## Tests Shipped

### `tests/integration/auth/test_password_reset_confirm.py` (4 tests, 380 lines)

1. **`test_confirm_happy_path_atomic_consume_password_rotate_sessions_revoke`** — Full D-44-16 sequence: pre-reset login → /password-reset/confirm → 200 envelope(None) → `consumed_at IS NOT NULL` → `password_hash` rotated → old refresh cookie 401s on /auth/refresh → new login with new password succeeds → exactly 1 `password_reset_completed` audit row with `sessions_revoked_count >= 1` and `token_id == seeded_row_id`.
2. **`test_confirm_replay_returns_410_with_identical_body`** — 2nd POST with the same token returns 410 + `code='invalid_or_expired_token'` + `fields=null`. Asserts no second `password_reset_completed` audit row (D-44-15 anti-oracle: replay collapses to 410 without rotation).
3. **`test_confirm_expired_token_returns_410_with_identical_body`** — Token with `expires_at = now() - 1 minute` returns 410 with the SAME envelope shape as the replay 410 (anti-oracle parity). `consumed_at IS NULL` proves the `expires_at > NOW()` predicate filtered the row out — no atomic-consume, no rotation.
4. **`test_confirm_weak_password_returns_422_token_stays_valid_for_retry`** — 7-char password → 422 `weak_password`. `consumed_at IS NULL` after the 422 (D-44-17 — strength check runs BEFORE atomic-consume). Re-POST with the SAME token + valid password → 200 (retry succeeds within TTL).

### `tests/integration/auth/test_password_reset_rate_limit.py` (3 tests, 197 lines)

1. **`test_rate_limit_per_ip_5_per_15min_returns_202_not_429`** — 5 successful POSTs with `X-Forwarded-For: 127.0.0.1` (different emails per iteration so per-email-min doesn't trip). 6th POST hits per-IP limit; returns 202 with byte-identical body to success. Exactly one `password_reset.rate_limited` structlog event captured with `ip='127.0.0.1'`.
2. **`test_rate_limit_per_email_minute_1_per_60s_returns_202`** — 2 POSTs with same email + different IPs (10.0.0.1, 10.0.0.2). Per-IP counters stay at 1 each; per-email-minute (1/60s) trips on the 2nd request → 202 + byte-identical body. One `password_reset.rate_limited` event.
3. **`test_rate_limit_per_email_hour_5_per_3600s_returns_202`** — 5 POSTs with same email rotating across IPs 10.0.0.{1..5}, deleting `ratelimit:password_reset:email_min:{email}` between iterations so the per-email-minute limit doesn't trip. 6th POST trips per-email-hour (5/3600s) → 202 + byte-identical body. One `password_reset.rate_limited` event.

All 3 rate-limit keys (`ratelimit:password_reset:{ip,email_min,email_hour}:*`) exercise their threshold-hit path in at least one test.

## AppError Envelope Shape Captured (pinned for Wave 4 siblings)

The global AppError handler (`apps/backend/app/core/exceptions.py:415-423`) emits the error envelope **at the top level** (NOT nested under `detail`):

```json
{
  "code": "<error_code>",
  "message": "<message-string>",
  "fields": null
}
```

For Wave 4 sibling tests (44-08 invitation-accept, 44-09 ops drift) match assertions on:

- `body["code"] == "invalid_or_expired_token"` (410)
- `body["code"] == "weak_password"` (422)
- `body["code"] == "invitation_already_accepted"` (409)
- `body["fields"]` is either `null` or a dict — the schemas in `auth/exceptions.py` set `fields=None` by default; `BotNotStarted` sets `fields={"deepLinkUrl": ...}`.

Successful 200 responses serialize as `{"data": null}` (the camelCase `to_camel` generator does not affect this shape since `null` has no keys).

## Redis Isolation

The `redis_clean` fixture (per-test `await client.flushdb()`) was sufficient — no flake encountered across 7 tests over multiple full runs. The `_refresh_password_reset_logger` autouse fixture in the rate-limit file forces the structlog lazy-proxy on `password_reset_service._log` to re-resolve processors so `capture_logs()` sees emissions; mirrors the existing `_reset_auth_service_logger_cache` in `tests/integration/auth/conftest.py`.

In the confirm-tests file the same reset fixture is declared but NOT autouse — none of the 4 tests use `capture_logs()` (audit-row assertions on the DB are the verification surface).

## Deviations from Plan

### Acceptance criterion: `grep -c "429" ... returns 0`

Plan acceptance criterion #7 for the rate-limit file said `grep -c "429" returns 0`. The shipped file contains **4 occurrences** of `429`:

- Line 9: module docstring — "rate-limit hits MUST NEVER surface as 429."
- Line 11: module docstring — "a 429 would leak …"
- Line 68: test function name — `test_rate_limit_per_ip_5_per_15min_returns_202_not_429`
- Line 72: test docstring — "returns 202 (NOT 429)."

**No actual `429` assertions exist** (the underlying invariant). All occurrences are documentation that encodes the D-44-11 invariant for future readers / grep-based discovery. Treating these as Rule 1 (preserves anti-oracle contract surface in test names) — the literal grep heuristic is a weaker form of the invariant.

### Acceptance criterion: `grep -c "status_code == 202 ..." returns at least 6`

Shipped value: 6 — passes.

## Authentication Gates

None — both endpoints are anonymous (D-44-34 — no CSRF, no RBAC, no auth dep).

## Verification

```
$ cd apps/backend && uv run pytest tests/integration/auth/test_password_reset_confirm.py tests/integration/auth/test_password_reset_rate_limit.py -q
.......                                                                  [100%]
7 passed in 8.05s

$ cd apps/backend && uv run ruff check tests/integration/auth/test_password_reset_confirm.py tests/integration/auth/test_password_reset_rate_limit.py
All checks passed!

$ cd apps/backend && uv run pytest tests/integration/auth/ -q
61 passed in 19.39s   # no regressions in the broader auth suite
```

`mypy --strict` reports the pre-existing `from app.modules.auth.models import User` re-export warning that ALSO appears on 4 unrelated production files (`telegram_service.py`, `service.py`, `router.py`, `users/router.py`) and the existing Phase 41 reference test (`test_password_reset_no_oracle.py:47`). This is project-wide baseline noise unrelated to this plan; out-of-scope per the executor scope-boundary rule.

## Commits

- `b52b536` — `test(44-07): add /password-reset/confirm integration tests (RESET-02)`
- `562e0c3` — `test(44-07): add /password-reset/request rate-limit integration tests (RESET-01)`

## Self-Check: PASSED

- `apps/backend/tests/integration/auth/test_password_reset_confirm.py` — FOUND (380 lines)
- `apps/backend/tests/integration/auth/test_password_reset_rate_limit.py` — FOUND (197 lines)
- commit `b52b536` — FOUND
- commit `562e0c3` — FOUND
- 7/7 tests green, 0 ruff warnings, 0 new mypy warnings (1 pre-existing baseline noise carried over from Phase 41 reference test)
