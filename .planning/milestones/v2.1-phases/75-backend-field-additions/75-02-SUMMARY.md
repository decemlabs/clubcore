---
phase: 75-backend-field-additions
plan: "02"
subsystem: backend/promo
tags: [migration, seed, promo-codes, integration-test]
dependency_graph:
  requires: ["75-01"]
  provides: ["PROMO-01 — FIT15 seeded in promo_codes, validate endpoint returns valid discount"]
  affects: ["promo_codes table", "POST /client/promo/validate"]
tech_stack:
  added: []
  patterns: ["data-migration via Alembic op.execute(sa.text())", "ON CONFLICT partial-unique idempotency", "soft-delete downgrade"]
key_files:
  created:
    - apps/backend/alembic/versions/0051_seed_fit15_promo.py
    - apps/backend/tests/integration/client_portal/test_fit15_seed.py
  modified: []
decisions:
  - "D-07 discipline: FIT15 is a product code, not demo data — seeded in a migration, not seed_demo_data.py"
  - "D-09: discount_value=1500 (15% x 100), per_client_limit=1, max_uses=NULL (globally uncapped), no expiry window"
  - "ON CONFLICT explicit partial-index form: ON CONFLICT (upper(code)) WHERE deleted_at IS NULL DO NOTHING"
  - "Downgrade soft-deletes (deleted_at=now()) rather than hard-deletes to preserve promo_redemptions RESTRICT FK"
metrics:
  duration: "3m"
  completed: "2026-06-02"
  tasks_completed: 2
  files_created: 2
  files_modified: 0
---

# Phase 75 Plan 02: FIT15 Seed Migration Summary

**One-liner:** Idempotent Alembic data migration 0051 seeds FIT15 percentage promo code (discount_value=1500, per_client_limit=1) with integration tests proving DB presence, re-run idempotency, and validate-endpoint 200 response.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | FIT15 idempotent data-migration 0051 | a44fd56e |
| 2 | Migration-applied idempotency + validate-endpoint integration test | 53f1c6ba |

## What Was Built

**Migration 0051 (`apps/backend/alembic/versions/0051_seed_fit15_promo.py`):**
- Chains after `0050_clients_notif_prefs` (plan 75-01 output)
- `upgrade()`: `INSERT INTO promo_codes ... ON CONFLICT (upper(code)) WHERE deleted_at IS NULL DO NOTHING` — seeds FIT15 with `discount_type='percentage'`, `discount_value=1500`, `per_client_limit=1`, `max_uses=NULL`, `is_active=TRUE`, `applicable_to=NULL`
- `downgrade()`: `UPDATE promo_codes SET deleted_at = now() WHERE upper(code) = 'FIT15' AND deleted_at IS NULL` — soft-delete preserves referential integrity
- Header docstring cites D-07/D-08/D-09 and the idempotency rationale
- `uv run alembic heads` shows `0051_seed_fit15_promo (head)`

**Integration test (`apps/backend/tests/integration/client_portal/test_fit15_seed.py`):**
- Test A (`test_fit15_row_exists_with_correct_attributes`): asserts FIT15 row in `promo_codes` with all expected field values (discount_type, discount_value, per_client_limit, is_active, deleted_at, applicable_to, max_uses, valid_from, valid_until)
- Test B (`test_fit15_seed_insert_is_idempotent`): re-runs the 0051 upgrade SQL via `db_session.execute(text(...))`, asserts `SELECT count(*)` = 1 (T-75-05 idempotency)
- Test C (`test_fit15_validate_returns_percentage_discount`): authenticates client, POSTs `{"code":"FIT15","kind":"sub","planId":...}` to `/api/v1/client/promo/validate`, asserts HTTP 200 + `discountType=percentage` + `discountKopecks=15000` + `newAmountKopecks=85000` on a 100_000-kopeck plan

## Verification Results

- `uv run pytest tests/integration/client_portal/test_fit15_seed.py -q` — **3 passed** (1.00s)
- `uv run alembic downgrade -1` + `uv run alembic upgrade head` — clean round-trip
- `uv run alembic heads` — `0051_seed_fit15_promo (head)`
- `uv run ruff check tests/integration/client_portal/test_fit15_seed.py` — passed
- `uv run mypy app` — `Success: no issues found in 224 source files`
- `uv run lint-imports` — passed (zero new `ignore_imports`)

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — FIT15 is a real DB row fully validated by the existing endpoint.

## Threat Flags

None — no new network endpoints or auth paths introduced. The only surface is a data row in `promo_codes`, which the existing `/client/promo/validate` endpoint already handles. T-75-05 (re-run creates duplicate) mitigated by `ON CONFLICT ... DO NOTHING`. T-75-06/T-75-07 accepted per plan threat model.

## Self-Check: PASSED

- `apps/backend/alembic/versions/0051_seed_fit15_promo.py` — FOUND
- `apps/backend/tests/integration/client_portal/test_fit15_seed.py` — FOUND
- Commit a44fd56e — FOUND (feat(75-02): FIT15 idempotent data-migration 0051)
- Commit 53f1c6ba — FOUND (test(75-02): migration-applied idempotency + validate-endpoint integration test)
