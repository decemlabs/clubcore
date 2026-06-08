---
phase: 96-referral-domain-backend
plan: "02"
subsystem: backend
tags: [referrals, migration, alembic, orm, pydantic, config]
dependency_graph:
  requires: []
  provides:
    - app/modules/referrals/models.py (ReferralCode, ReferralCapture, ReferralConfig ORM models)
    - app/modules/referrals/schemas.py (five wire schemas: ReferralCodeResponse, ReferralResolveResponse, ReferralCaptureRequest, ReferralConfigResponse, ReferralConfigUpdateRequest)
    - alembic/versions/0067_referral_tables.py (DDL for three referral tables + UNIQUE indexes)
    - alembic/versions/0068_seed_referral_config.py (singleton config seed 50000/30000 kopecks)
    - app/core/config.py pwa_base_url field (server-authoritative deep-link base)
  affects:
    - alembic migration chain (0067 + 0068 appended after 0066)
    - Settings class (pwa_base_url added)
tech_stack:
  added: []
  patterns:
    - append-only ORM model (Base + UUIDPkMixin only, single-temporal-column)
    - literal FK names in migration + op.f() for PK/plain indexes
    - op.f() UNIQUE for unconditional index; literal name for plain UNIQUE per pattern
    - ON CONFLICT (id) DO NOTHING seed with CAST(:id AS uuid) asyncpg pattern
    - SAVEPOINT-based integration test asserting table existence + seed values + index names
key_files:
  created:
    - apps/backend/app/modules/referrals/__init__.py
    - apps/backend/app/modules/referrals/models.py
    - apps/backend/app/modules/referrals/schemas.py
    - apps/backend/alembic/versions/0067_referral_tables.py
    - apps/backend/alembic/versions/0068_seed_referral_config.py
    - apps/backend/tests/integration/test_alembic_0067_referral.py
  modified:
    - apps/backend/app/core/config.py (pwa_base_url field added)
decisions:
  - "D-96-02-01: referral_captures UNIQUE on referee_client_id is unconditional (not partial) — one capture per referee regardless of any status; uses literal index name per 96-PATTERNS"
  - "D-96-02-02: pwa_base_url added adjacent to frontend_base_url in Settings; default http://localhost:5174 (client-pwa dev port per ws_allowed_origins)"
  - "D-96-02-03: referral_config singleton PK 00000000-0000-0000-0000-000000000002; gym_info used ...001"
metrics:
  duration: ~25 min
  completed: "2026-06-08"
  tasks: 3
  files_created: 6
  files_modified: 1
---

# Phase 96 Plan 02: Referral Data Layer Summary

**One-liner:** Three-table referral schema (referral_codes/captures/config) with UNIQUE constraints enforcing REFER-01/03/07 at DB level, seeded singleton config (500₽/300₽), and pwa_base_url Settings field for server-authoritative shareUrl.

## What Was Built

The full referral data layer — no service logic, no routers, no endpoints. This plan delivers the persistent shape that Plans 96-03/04 will build on.

### Task 1: Referral ORM Models + Module Package + Schemas (commit `07a52ea6`)

Created `app/modules/referrals/` package with three models and five schemas:

**Models** (`models.py`):
- `ReferralCode` — one stable code per client; `client_id` FK→clients RESTRICT (named `fk_referral_codes_client_id_clients`); `code String(16)`; `created_at` server_default
- `ReferralCapture` — referee↔referrer binding; three RESTRICT FKs (referee/referrer→clients, referral_code_id→referral_codes with literal FK names); `created_at` server_default
- `ReferralConfig` — singleton config; `referrer_bonus_kopecks` + `referee_welcome_kopecks` BigInteger; no temporal column (config, not event)

All three composed `Base + UUIDPkMixin` only (single-temporal-column discipline per loyalty_ledger analog).

**Schemas** (`schemas.py`):
- `ReferralCodeResponse(ResponseData)` — `{code, shareUrl}` wire
- `ReferralResolveResponse(ResponseData)` — `{valid, referrerFirstName, welcomeBonusKopecks}` wire
- `ReferralCaptureRequest(BackendSchemaBase)` — `{code}` with `min_length=1, max_length=16`
- `ReferralConfigResponse(ResponseData)` — `{referrerBonusKopecks, refereeWelcomeKopecks}` wire
- `ReferralConfigUpdateRequest(BackendSchemaBase)` — `{referrerBonusKopecks: Field(ge=0), refereeWelcomeKopecks: Field(ge=0)}`

Verification: `mypy --strict` clean; import smoke-test prints `referral_codes referral_captures referral_config`.

### Task 2: Migrations 0067 (tables) + 0068 (seed) + pwa_base_url setting (commit `643c08c3`)

**Migration 0067** (`alembic/versions/0067_referral_tables.py`):
- `down_revision = "0066_message_attachments"` (correct chain head)
- Creates `referral_config` first (no FK deps), then `referral_codes` (FK→clients), then `referral_captures` (FKs→clients + referral_codes)
- UNIQUE indexes: `uq_referral_codes_code` via `op.f()` (plain/unconditional); `uq_referral_captures_referee_client_id` as LITERAL name (no `op.f()`, no `postgresql_where`) per 96-PATTERNS
- Plain index `ix_referral_codes_client_id` via `op.f()`
- Downgrade drops in reverse FK order (captures → codes → config)

**Migration 0068** (`alembic/versions/0068_seed_referral_config.py`):
- `down_revision = "0067_referral_tables"`
- Seeds singleton row with PK `00000000-0000-0000-0000-000000000002`, `referrer_bonus_kopecks=50000`, `referee_welcome_kopecks=30000`
- Uses `CAST(:id AS uuid)` asyncpg pattern (mirrors 0059_seed_gym_info)
- `ON CONFLICT (id) DO NOTHING` idempotency

**Settings field** (`app/core/config.py` line 139):
- `pwa_base_url: str = "http://localhost:5174"` added adjacent to `frontend_base_url`
- Used by Plan 96-03 service to construct `shareUrl = f"{settings.pwa_base_url}/i/{code}"`

Round-trip: `upgrade head` → `downgrade 0066_message_attachments` → `upgrade head` all clean.

### Task 3: Alembic Round-Trip + Constraint Integration Test (commit `fe74ebde`)

Created `tests/integration/test_alembic_0067_referral.py` with 4 tests against live Postgres:
- `test_three_referral_tables_exist` — checks `information_schema.tables`
- `test_referral_config_singleton_seed_values` — asserts kopecks 50000/30000 by PK
- `test_uq_referral_codes_code_index_exists` — asserts index in `pg_indexes` by exact name
- `test_uq_referral_captures_referee_client_id_index_exists` — same for literal-named UNIQUE

All 4 tests pass: `4 passed in 0.92s`.

## Verification

```
uv run alembic upgrade head           ✅ 0067 + 0068 applied
uv run alembic downgrade 0066...      ✅ round-trip clean
uv run alembic upgrade head           ✅ re-applied clean
uv run pytest test_alembic_0067_referral.py  ✅ 4 passed
uv run mypy --strict app/modules/referrals/ app/core/config.py  ✅ 0 issues
uv run ruff check app/modules/referrals/ alembic/versions/0067* alembic/versions/0068*  ✅
uv run lint-imports                   ✅ (pre-existing stale "No matches" warnings only)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Missing .env file in worktree blocked pytest**
- **Found during:** Task 3 test run
- **Issue:** The worktree had `.env.example` but not `.env`; `YooKassaSettings()` is instantiated at module-import time in `webhook_verifier.py` (before conftest's `setdefault` loop runs), causing `ValidationError` for required env vars and `ImportError while loading conftest`
- **Fix:** Copied `.env` from main repo into worktree (`apps/backend/.env`)
- **Note:** `.env` is git-ignored; not committed. Worktree workers need this file to run tests.

**2. [Rule 1 - Bug] ruff I001 import sort in 0068 migration**
- **Found during:** ruff check after Task 2 implementation
- **Issue:** `from alembic import op` was not separated from stdlib imports with a blank line
- **Fix:** `uv run ruff check --fix` applied automatically; import block now correctly sorted

## Known Stubs

None — this plan delivers only schema/data-layer artifacts (no UI, no hardcoded placeholder data flowing to any rendering path).

## Threat Flags

None — no new network endpoints, auth paths, or file access patterns introduced. UNIQUE constraints enforce T-96-03 (one-referrer-per-referee) and T-96-04 (code collision detection) at the DB level as required by the threat model.

## Self-Check: PASSED

Files created:
- `apps/backend/app/modules/referrals/__init__.py` ✅
- `apps/backend/app/modules/referrals/models.py` ✅
- `apps/backend/app/modules/referrals/schemas.py` ✅
- `apps/backend/alembic/versions/0067_referral_tables.py` ✅
- `apps/backend/alembic/versions/0068_seed_referral_config.py` ✅
- `apps/backend/tests/integration/test_alembic_0067_referral.py` ✅

Commits:
- `07a52ea6` feat(96-02): referral ORM models + schemas ✅
- `643c08c3` feat(96-02): migrations 0067 + 0068 + pwa_base_url ✅
- `fe74ebde` test(96-02): alembic 0067 round-trip + constraint integration test ✅
