---
phase: 82
plan: "02"
subsystem: backend
tags: [loyalty, service, accrual, grant, balance, history, idor, rbac, audit, integration-tests]
dependency_graph:
  requires:
    - 82-01 (LoyaltyLedger model, migration 0054, loyalty_accrued LOCKED audit event)
  provides:
    - loyalty/service.py: accrue_welcome_bonus, owner_grant_loyalty, get_client_loyalty_balance, list_client_loyalty_history
    - loyalty/schemas.py: ClientLoyaltyBalanceResponse, ClientLoyaltyHistoryItem, ClientLoyaltyGrantResponse, LoyaltyGrantRequest
    - loyalty/permissions.py: require_owner_for_loyalty_grant
    - loyalty/router.py: client_get_loyalty_balance, client_list_loyalty_history endpoints
    - clients/router.py: owner_grant_loyalty POST endpoint
    - clients/service.py: welcome accrual co-transactional callsite
    - api/v1/router.py: loyalty_router mounted at /client
    - 20 integration tests (ACCR-01/02/03, LOYL-01/02, IDOR, idempotency, RBAC)
  affects:
    - apps/backend/app/modules/clients/service.py (welcome callsite)
    - apps/backend/app/modules/clients/router.py (grant endpoint)
    - apps/backend/app/api/v1/router.py (loyalty_router mount)
    - apps/backend/.importlinter (4 new ignore_imports edges)
tech_stack:
  added: []
  patterns:
    - RETURNING-gated welcome audit (pg_insert.on_conflict_do_nothing with index_elements+index_where for partial UNIQUE INDEX)
    - caller-owns-txn discipline (service flush only; router commits)
    - IDOR-safe client reads (client_id from require_client() principal, never URL)
    - Direct owner-role guard (require_owner_for_loyalty_grant; does not extend OWNER_ONLY)
    - SUM fold balance (raw SQL text() COALESCE 0; D-54-08 cross-module read)
key_files:
  created:
    - apps/backend/app/modules/loyalty/service.py
    - apps/backend/app/modules/loyalty/schemas.py
    - apps/backend/app/modules/loyalty/permissions.py
    - apps/backend/app/modules/loyalty/router.py
    - apps/backend/tests/integration/test_loyalty_accrual.py
    - apps/backend/tests/integration/test_loyalty_grant.py
    - apps/backend/tests/integration/test_loyalty_read.py
  modified:
    - apps/backend/app/modules/clients/service.py (welcome callsite)
    - apps/backend/app/modules/clients/router.py (grant endpoint)
    - apps/backend/app/api/v1/router.py (loyalty_router mount)
    - apps/backend/.importlinter (4 new edges)
decisions:
  - "on_conflict_do_nothing uses index_elements+index_where (not constraint=) because uq_loyalty_ledger_welcome is a partial UNIQUE INDEX not a named UNIQUE CONSTRAINT; ON CONFLICT ON CONSTRAINT only works for named constraints"
  - "RETURNING id gates the welcome audit emit — conflict path returns None, real insert returns UUID; audit only on real insert"
  - "Loyalty router mounted separately from client_portal_router to avoid client_portal→loyalty cross-module edge (D-20-MODULE)"
  - "owner_grant_loyalty flush occurs inside service after insert+audit emit so balance SUM includes new row; commit in router"
  - "require_owner_for_loyalty_grant does not extend OWNER_ONLY frozenset or add a Resource — CISO-01 and Phase-6 parity tests stay green"
  - "Integration tests inline _auth_as_client helper rather than importing from client_portal/test_idor_sweep to avoid cross-test-module coupling"
metrics:
  duration_minutes: 10
  completed_date: "2026-06-05"
  tasks_completed: 3
  tasks_total: 3
  files_created: 7
  files_modified: 4
---

# Phase 82 Plan 02: Loyalty Backend Service — Accrual, Grant, Balance, History Summary

**One-liner:** Loyalty service with RETURNING-gated idempotent welcome accrual (50000 kopecks), owner-only grant API (ACCR-02), IDOR-safe balance/history reads (SUM fold via raw SQL), co-transactional audit on every accrual, and 20 green integration tests covering idempotency, RBAC, IDOR, and audit completeness.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Loyalty service, schemas, owner-guard | b3f0c7d2 | loyalty/service.py, schemas.py, permissions.py |
| 2 | Wire endpoints + welcome callsite + router mounts + importlinter | 4ed6bd7c | loyalty/router.py, clients/service.py, clients/router.py, api/v1/router.py, .importlinter |
| 3 | Integration tests + partial-UNIQUE bug fix | bd877b0d | test_loyalty_accrual.py, test_loyalty_grant.py, test_loyalty_read.py, service.py (bug fix) |

## Verification Results

- `uv run pytest tests/integration/test_loyalty_accrual.py tests/integration/test_loyalty_grant.py tests/integration/test_loyalty_read.py -q` — 20 passed
- `uv run lint-imports` — Contracts: 3 kept, 0 broken (5 pre-existing warnings, no new ones)
- `uv run mypy --strict app/modules/loyalty app/modules/clients` — Success: no issues
- `uv run ruff check app/modules/loyalty app/modules/clients app/api/v1/router.py` — All checks passed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed on_conflict_do_nothing constraint vs index syntax**
- **Found during:** Task 3 — first test run (test_loyalty_accrual.py test 1)
- **Issue:** `on_conflict_do_nothing(constraint="uq_loyalty_ledger_welcome")` raises `asyncpg.exceptions.UndefinedObjectError: constraint "uq_loyalty_ledger_welcome" for table "loyalty_ledger" does not exist`. PostgreSQL's `ON CONFLICT ON CONSTRAINT` only resolves named UNIQUE CONSTRAINTs, not UNIQUE INDEXes. Migration 0054 creates `uq_loyalty_ledger_welcome` via `op.create_index(unique=True, postgresql_where=...)` (a partial UNIQUE INDEX), not `op.create_unique_constraint`. The PATTERNS.md analog (`promo_codes` using `uq_promo_redemptions_online_payment_id`) works because that IS a named constraint.
- **Fix:** Changed to `on_conflict_do_nothing(index_elements=["client_id"], index_where=literal_column("entry_type") == "welcome")` — this matches the partial index predicate exactly without requiring a named constraint. Added `literal_column` import to service.py.
- **Files modified:** `apps/backend/app/modules/loyalty/service.py`
- **Commit:** bd877b0d

## Known Stubs

None — all four service functions are fully implemented and wired. No placeholder returns.

## Threat Flags

No new threat surface beyond what is documented in the plan threat model (T-82-05..10).
All STRIDE mitigations implemented:
- T-82-05 (IDOR): client_id from require_client() principal only in all read endpoints
- T-82-06 (Elevation): require_owner_for_loyalty_grant + rbac_forbidden audit
- T-82-07 (double-credit): on_conflict_do_nothing + RETURNING gate + idempotency test
- T-82-08 (negative/overflow): amount_kopecks <= 0 → 422 before any DB write
- T-82-09 (repudiation): loyalty_accrued emitted co-transactionally for every real accrual
- T-82-10 (CSRF): verify_csrf in RBAC-04 order on grant endpoint

## Self-Check: PASSED

- `apps/backend/app/modules/loyalty/service.py` — FOUND (WELCOME_BONUS_KOPECKS=50000, accrue_welcome_bonus, owner_grant_loyalty, get_client_loyalty_balance, list_client_loyalty_history)
- `apps/backend/app/modules/loyalty/schemas.py` — FOUND
- `apps/backend/app/modules/loyalty/permissions.py` — FOUND (require_owner_for_loyalty_grant)
- `apps/backend/app/modules/loyalty/router.py` — FOUND (client_get_loyalty_balance, client_list_loyalty_history)
- `apps/backend/tests/integration/test_loyalty_accrual.py` — FOUND (3 tests)
- `apps/backend/tests/integration/test_loyalty_grant.py` — FOUND (7 tests)
- `apps/backend/tests/integration/test_loyalty_read.py` — FOUND (10 tests)
- Commit b3f0c7d2 — FOUND (feat: loyalty service, schemas, and owner-guard)
- Commit 4ed6bd7c — FOUND (feat: wire loyalty endpoints)
- Commit bd877b0d — FOUND (feat: loyalty integration tests + partial-UNIQUE bug fix)
- `grep -c "session.commit" apps/backend/app/modules/loyalty/service.py` — 1 (only in module docstring, not actual code call)
- `uv run lint-imports` — 3 contracts kept, 0 broken
