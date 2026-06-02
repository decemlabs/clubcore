---
phase: 70-client-bookings-qr-self-check-in
plan: "01"
subsystem: backend-core
tags: [security, jwt, alembic, migration, constants, tdd]
dependency_graph:
  requires: []
  provides:
    - encode_qr_token / decode_qr_token / QrTokenClaims (app.core.security)
    - qr_token_ttl_seconds config setting (app.core.config)
    - CANCEL_WINDOW_HOURS_CLIENT constant (app.modules.bookings.constants)
    - ck_visits_channel CHECK extended with client_qr (Alembic 0045 + ORM)
  affects:
    - app/core/security.py
    - app/core/config.py
    - app/modules/bookings/constants.py
    - app/modules/visits/models.py
    - alembic/versions/0045_visits_channel_client_qr.py
tech_stack:
  added: []
  patterns:
    - TDD RED/GREEN for QR token unit tests
    - op.f() to avoid NAMING_CONVENTION double-prefix on Alembic drop_constraint
    - Frozen dataclass mirroring ClientAccessTokenClaims for QrTokenClaims
key_files:
  created:
    - apps/backend/tests/unit/core/test_qr_token.py
    - apps/backend/tests/unit/core/__init__.py
    - apps/backend/alembic/versions/0045_visits_channel_client_qr.py
    - apps/backend/tests/integration/migrations/test_visits_channel_client_qr.py
    - apps/backend/tests/integration/migrations/__init__.py
  modified:
    - apps/backend/app/core/security.py
    - apps/backend/app/core/config.py
    - apps/backend/app/modules/bookings/constants.py
    - apps/backend/app/modules/visits/models.py
decisions:
  - id: D-70-07-impl
    text: "encode_qr_token mirrors encode_client_token exactly; aud='qr', typ='qr_checkin' provide structural isolation from access/refresh tokens (D-70-08)"
  - id: D-45-op-f
    text: "op.f('ck_visits_channel') used in both drop_constraint and create_check_constraint to prevent NAMING_CONVENTION double-prefix (ck_visits_ck_visits_channel bug)"
metrics:
  duration: "~15 min"
  completed: "2026-05-30"
  tasks_completed: 3
  files_modified: 9
---

# Phase 70 Plan 01: QR Token + Cancel Constant + Channel Migration Summary

**One-liner:** Short-lived (60s) signed QR JWT with distinct aud/typ isolation, CANCEL_WINDOW_HOURS_CLIENT constant, and Alembic migration extending ck_visits_channel CHECK to allow 'client_qr'.

## Tasks Completed

| # | Task | Commit | Status |
|---|------|--------|--------|
| 1a | RED: failing tests for QrTokenClaims/encode_qr_token/decode_qr_token | 414b4529 | done |
| 1b | GREEN: QrTokenClaims + encode_qr_token + decode_qr_token + qr_token_ttl_seconds | f1ed80ce | done |
| 2 | CANCEL_WINDOW_HOURS_CLIENT = 24 in bookings/constants.py | 53d7a4c9 | done |
| 3 | Alembic 0045 migration + ORM sync + integration tests | 07ec7c47 | done |

## What Was Built

### Task 1 (TDD)
- `QrTokenClaims` frozen dataclass in `app/core/security.py` mirroring `ClientAccessTokenClaims`, with `aud="qr"` and `typ="qr_checkin"`.
- `encode_qr_token(client_id: UUID, *, now: datetime | None = None) -> str` — HS256 JWT with 60s TTL.
- `decode_qr_token(token: str) -> QrTokenClaims` — verifies signature, requires sub/aud/typ/iat/exp, maps ExpiredSignatureError → "token_expired", InvalidTokenError → "invalid_token", asserts typ=="qr_checkin" → "wrong_token_type", aud=="qr" → "wrong_audience".
- `qr_token_ttl_seconds: int = 60` added to `Settings` in `config.py`.
- 7 unit tests covering all rejection paths and the round-trip; cross-rejection (QR→decode_client_token, access→decode_qr_token) verified.

### Task 2
- `CANCEL_WINDOW_HOURS_CLIENT = 24` added to `bookings/constants.py`, documented as D-70-05/D-38-16 (measured against slot.start_time, independently tunable, starts at 24h). Added to `__all__`.

### Task 3
- Migration `0045_visits_channel_client_qr.py`: drop then recreate `ck_visits_channel` using `op.f()` (prevents NAMING_CONVENTION double-prefix).
- `visits/models.py` `__table_args__` CheckConstraint synced to `"channel IN ('reception', 'telegram_bot', 'client_qr')"`.
- Integration tests in `tests/integration/migrations/test_visits_channel_client_qr.py`: schema-level constraint inspection (passes without row seeding) + round-trip test.
- Round-trip: `alembic downgrade -1 && alembic upgrade head` verified clean.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Alembic drop_constraint double-prefix**
- **Found during:** Task 3 first migration run
- **Issue:** `op.drop_constraint("ck_visits_channel", ...)` goes through NAMING_CONVENTION template `ck_%(table_name)s_%(constraint_name)s` → produces `ck_visits_ck_visits_channel` which doesn't exist in DB.
- **Fix:** Changed to `op.drop_constraint(op.f("ck_visits_channel"), ...)` and `op.create_check_constraint(op.f(_CONSTRAINT_NAME), ...)` — mirrors the 0032 migration precedent.
- **Files modified:** `alembic/versions/0045_visits_channel_client_qr.py`
- **Commit:** 07ec7c47

**2. [Rule 1 - Bug] Test seed used wrong memberships schema**
- **Found during:** Task 3 integration test first run
- **Issue:** Test seed used `membership_plan_id` (doesn't exist) and assumed a `created_by_user_id` column on memberships (doesn't exist). Actual column is `plan_id`.
- **Fix:** Rewrote test to use schema-level constraint inspection (no row seeding required for the primary assertions) + row-level tests that skip if no membership_plan exists. Fixed INSERT to use correct columns.
- **Files modified:** `tests/integration/migrations/test_visits_channel_client_qr.py`

**3. [Rule 1 - Bug] SQL alias `def` is Python reserved word**
- **Found during:** Task 3 integration test second run
- **Issue:** `AS def` in the SQL for `pg_get_constraintdef` — `row.def_` fails because `def` doesn't match. Partially fixed by rename to `AS constraint_def` but two occurrences retained `AS def` in string concatenation.
- **Fix:** Replaced all occurrences with `AS constraint_def` and `row.constraint_def`.
- **Files modified:** `tests/integration/migrations/test_visits_channel_client_qr.py`

## Verification Results

```
uv run pytest tests/unit/core/test_qr_token.py tests/integration/migrations/test_visits_channel_client_qr.py -q
10 passed, 2 skipped in 4.82s

uv run mypy app/core/security.py app/core/config.py app/modules/visits/models.py
Success: no issues found in 3 source files

uv run lint-imports
Contracts: 3 kept, 0 broken.

alembic upgrade head / downgrade -1 / upgrade head — round-trip clean
```

## Known Stubs

None — this plan introduces primitives with no UI stubs.

## Threat Flags

No new threat surface beyond what is already in the plan's threat_model (T-70-01 through T-70-04 all mitigated in this plan).

## Self-Check

- [x] `apps/backend/app/core/security.py` — contains `encode_qr_token`, `decode_qr_token`, `QrTokenClaims`
- [x] `apps/backend/app/core/config.py` — contains `qr_token_ttl_seconds`
- [x] `apps/backend/app/modules/bookings/constants.py` — contains `CANCEL_WINDOW_HOURS_CLIENT = 24`
- [x] `apps/backend/alembic/versions/0045_visits_channel_client_qr.py` — exists, `down_revision = "0044_client_refresh_token"`, contains `client_qr`
- [x] `apps/backend/tests/unit/core/test_qr_token.py` — 7 tests all pass
- [x] `apps/backend/tests/integration/migrations/test_visits_channel_client_qr.py` — 3 pass, 2 skip
