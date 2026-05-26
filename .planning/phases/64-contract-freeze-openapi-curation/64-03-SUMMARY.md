---
phase: 64-contract-freeze-openapi-curation
plan: 03
subsystem: backend
tags: [openapi, contract-freeze, frz-03, tags, redocly]
requires:
  - apps/backend/app/main.py (FastAPI constructor from 64-01 + custom_unique_id from 64-02)
  - apps/backend/scripts/export_openapi.py (byte-stable exporter)
  - packages/api-client codegen script
provides:
  - OPENAPI_TAGS 12-entry ordered list in app/main.py (D-64-TAG-ORDER + D-64-TAG-USERS + D-64-TAG-INTERNAL)
  - tags=[PascalCase] on every APIRouter constructor (23 router objects across 18 files)
  - aggregator (app/api/v1/router.py) no longer passes tags= on include_router calls
  - /healthz tagged Internal (no default folder in Redocly preview)
  - regenerated openapi.json with per-operation PascalCase tags + top-level tags[] array
  - regenerated schema.d.ts keyed on same operation IDs
affects:
  - apps/backend/app/main.py (OPENAPI_TAGS constant + openapi_tags= kwarg)
  - apps/backend/app/api/v1/router.py (all tags= kwargs dropped)
  - apps/backend/app/api/v1/health.py (healthz tagged Internal)
  - apps/backend/app/api/v1/_internal/email/router.py (tags=["Internal"])
  - apps/backend/app/api/v1/_internal/yookassa/router.py (tags=["Internal"])
  - apps/backend/app/modules/auth/router.py
  - apps/backend/app/modules/bookings/router.py (x2)
  - apps/backend/app/modules/clients/router.py
  - apps/backend/app/modules/memberships/router.py (x2)
  - apps/backend/app/modules/online_payments/router.py
  - apps/backend/app/modules/payments/router.py
  - apps/backend/app/modules/payroll/router.py
  - apps/backend/app/modules/pt_packages/router.py (x2)
  - apps/backend/app/modules/pt_sessions/router.py (x2)
  - apps/backend/app/modules/reports/router.py (x2: Reports + Audit-log)
  - apps/backend/app/modules/schedule/router.py (x3)
  - apps/backend/app/modules/trainers/router.py
  - apps/backend/app/modules/users/router.py
  - apps/backend/app/modules/visits/router.py
  - apps/backend/openapi.json (per-operation tags renamed to PascalCase + top-level tags[] added)
  - packages/api-client/src/schema.d.ts (regenerated; AssertNonNever path-keyed guards unchanged)
  - apps/backend/scripts/export_openapi.py (YooKassa env stubs added — Rule 3 auto-fix)
tech-stack:
  added: []
  patterns:
    - OPENAPI_TAGS module-level frozenset-style constant (mirrors OWNER_ONLY discipline)
    - APIRouter(tags=[...]) per-router declaration (single-source-of-truth for tag grouping)
    - D-64-TAG-USERS: Users carved as 11th tag between Auth and Clients
    - D-64-TAG-INTERNAL: Internal last in ordering, covering healthz + _internal/* webhooks
key-files:
  created: []
  modified:
    - apps/backend/app/main.py
    - apps/backend/app/api/v1/router.py
    - apps/backend/app/api/v1/health.py
    - apps/backend/app/api/v1/_internal/email/router.py
    - apps/backend/app/api/v1/_internal/yookassa/router.py
    - apps/backend/app/modules/auth/router.py
    - apps/backend/app/modules/bookings/router.py
    - apps/backend/app/modules/clients/router.py
    - apps/backend/app/modules/memberships/router.py
    - apps/backend/app/modules/online_payments/router.py
    - apps/backend/app/modules/payments/router.py
    - apps/backend/app/modules/payroll/router.py
    - apps/backend/app/modules/pt_packages/router.py
    - apps/backend/app/modules/pt_sessions/router.py
    - apps/backend/app/modules/reports/router.py
    - apps/backend/app/modules/schedule/router.py
    - apps/backend/app/modules/trainers/router.py
    - apps/backend/app/modules/users/router.py
    - apps/backend/app/modules/visits/router.py
    - apps/backend/openapi.json
    - packages/api-client/src/schema.d.ts
    - apps/backend/scripts/export_openapi.py
decisions:
  - "D-64-TAG-ORDER applied: 12 entries in openapi_tags — Auth, Users (D-64-TAG-USERS), Clients, Memberships, Visits, Schedule, Bookings, Trainers, Payments, Reports, Audit-log, Internal"
  - "D-64-TAG-USERS resolved (PATTERNS.md open-question #3): Users added as 11th tag between Auth and Clients; not folded into Auth"
  - "D-64-TAG-INTERNAL: healthz endpoint tagged Internal (Rule 2 auto-fix) to prevent default folder in Redocly"
  - "Aggregator tags= dropped: all 22 include_router() calls in app/api/v1/router.py no longer pass tags="
  - "D-64-BYTE-STABLE honored: second regen after commit produces byte-identical output (drift gate exits 0)"
metrics:
  completed: 2026-05-26
  duration: ~35min
  tasks: 3
  files_modified: 22
  files_created: 0
---

# Phase 64 Plan 03: Explicit Tags on All Routers + openapi_tags Ordering Summary

Declared `OPENAPI_TAGS` (12-entry ordered constant) in `app/main.py`, wired `openapi_tags=OPENAPI_TAGS` in the `FastAPI(...)` constructor, added `tags=[PascalCase]` to all 23 `APIRouter` constructors across 18 files, stripped all `tags=` kwargs from the aggregator, and regenerated `openapi.json` + `schema.d.ts` byte-stably. No operation falls into the Redocly "default" folder; no operation has duplicate tags.

## One-liner

`OPENAPI_TAGS` 12-entry ordered list wired in `app/main.py`; all 23 APIRouter constructors carry explicit `tags=[PascalCase]`; aggregator drops tags= (single-source-of-truth); openapi.json + schema.d.ts regenerated byte-stably; no duplicate tags, no default folder; drift gate green.

## Tasks Executed

| # | Name | Commit | Files |
| - | ---- | ------ | ----- |
| 1 | Add OPENAPI_TAGS ordered 12-entry list to app/main.py | 0ba1cede | apps/backend/app/main.py |
| 2 | Migrate tags=[PascalCase] onto every APIRouter; drop aggregator tags= | 42d5fc1e | 17 router files + export_openapi.py |
| 3 | Tag healthz Internal; regen openapi.json + schema.d.ts; drift gate | 3b275527 | apps/backend/app/api/v1/health.py, openapi.json, schema.d.ts |

## OPENAPI_TAGS Ordering

| # | Tag | Router(s) | Description |
|---|-----|-----------|-------------|
| 1 | Auth | auth/router.py | Credential lifecycle |
| 2 | Users | users/router.py | Operator admin (D-64-TAG-USERS) |
| 3 | Clients | clients/router.py | Gym client CRM |
| 4 | Memberships | memberships/router.py (x2) | Plans + active memberships |
| 5 | Visits | visits/router.py | Gym visit recording |
| 6 | Schedule | schedule/router.py (x3) | Slots, templates, time-off |
| 7 | Bookings | bookings/router.py (x2) | Slot bookings lifecycle |
| 8 | Trainers | trainers/router.py | Trainer roster |
| 9 | Payments | payments/ + online_payments/ + pt_packages/ (x2) + pt_sessions/ (x2) + payroll/ | All billing |
| 10 | Reports | reports/router.py (`router`) | Aggregate reports |
| 11 | Audit-log | reports/router.py (`audit_log_router`) | Audit log read API |
| 12 | Internal | _internal/email/, _internal/yookassa/, health.py | Transport + liveness |

## Verification Performed

- `grep -E '^OPENAPI_TAGS: list\[dict\[str, str\]\] = \['` app/main.py -- one match
- `grep -E 'openapi_tags=OPENAPI_TAGS'` app/main.py -- one match
- OPENAPI_TAGS names assertion: `['Auth','Users','Clients','Memberships','Visits','Schedule','Bookings','Trainers','Payments','Reports','Audit-log','Internal']` -- OK
- `grep -RE 'APIRouter\(\)'` modules + _internal -- 0 bare constructors
- `grep -RE 'tags=\["...(PascalCase)..."\]'` -- 23 tagged constructors
- `grep -E 'tags=\['` app/api/v1/router.py -- 0 (aggregator clean)
- Duplicate-tag check: 0 operations with duplicate tags
- Default-folder check: 0 operations without tags or with "default" tag
- Top-level tags[] ordering: matches 12-entry expected list exactly
- `uv run ruff check` (full backend) -- exit 0
- `uv run mypy --strict app` (209 files) -- exit 0
- `pnpm --filter @clubcore/api-client typecheck` -- exit 0
- Post-commit drift gate: `uv run python -m scripts.export_openapi && pnpm codegen && git diff --exit-code` -- exit 0 (D-64-BYTE-STABLE proven)

## Diff Profile

- `apps/backend/app/main.py`: +89 lines (OPENAPI_TAGS constant + openapi_tags= kwarg + comment update)
- Router files (x18): 1 line change each (APIRouter() -- APIRouter(tags=[...]))
- `apps/backend/app/api/v1/router.py`: -22 tags= kwargs, +4 lines (comment)
- `apps/backend/scripts/export_openapi.py`: +7 lines (YooKassa env stubs -- Rule 3)
- `apps/backend/openapi.json`: 183 insertions / 128 deletions (per-op tags renamed PascalCase + top-level tags[] added)
- `packages/api-client/src/schema.d.ts`: regenerated (tag renames are spec-only metadata)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Tag healthz endpoint to prevent default folder**
- **Found during:** Task 3 duplicate-tag + default-folder verification
- **Issue:** `/healthz` endpoint in `app/api/v1/health.py` had no `APIRouter` tags, causing it to appear in a "default" folder in Redocly preview -- directly violating plan success criterion "No operation belongs to a stray 'default' tag"
- **Fix:** Added `tags=["Internal"]` to the health router with inline FRZ-03/D-64-TAG-INTERNAL citation. The liveness probe is infrastructure (not a business domain) so "Internal" is the correct grouping.
- **Files modified:** `apps/backend/app/api/v1/health.py`
- **Commit:** 3b275527

**2. [Rule 3 - Blocking Issue] Add YooKassa env stubs to export_openapi.py**
- **Found during:** Task 2 verification (`uv run python -m scripts.export_openapi` failed)
- **Issue:** `scripts/export_openapi.py` had env stubs for standard settings but not for `YooKassaSettings`, which is instantiated at module import time in `webhook_verifier.py`. In a clean shell without a `.env` file (worktree context), the export script failed with a Pydantic validation error.
- **Fix:** Added five `os.environ.setdefault("YOOKASSA_*", ...)` stubs to `export_openapi.py`, mirroring the existing pattern for DATABASE_URL/REDIS_URL/SECRET_KEY stubs. `setdefault` never overrides operator-provided values.
- **Files modified:** `apps/backend/scripts/export_openapi.py`
- **Commit:** 42d5fc1e

## Auth Gates

None. All work was static-file curation + offline regen.

## Decisions Made

- D-64-TAG-ORDER applied -- 12-entry ordered list in `OPENAPI_TAGS`
- D-64-TAG-USERS resolved -- Users as 11th tag between Auth and Clients (not folded into Auth)
- D-64-TAG-INTERNAL applied -- Internal last; covers _internal/* webhooks + /healthz liveness
- D-64-BYTE-STABLE proven -- second regen after commit produces byte-identical output

## Success Criteria Verification

| # | Criterion | Status |
| - | --------- | ------ |
| 1 | Every router declares explicit tags=[...]; no auto-derived tags remain | PASS (23 constructors tagged; 0 bare APIRouter()) |
| 2 | openapi_tags in app/main.py ships the 12-entry ordered list | PASS |
| 3 | No operation in default folder; no duplicate tags | PASS |
| 4 | Drift gate green (D-64-BYTE-STABLE) | PASS |
| 5 | ROADMAP success criterion #3 satisfied | PASS |

## Self-Check: PASSED

- File exists: `apps/backend/app/main.py` (OPENAPI_TAGS + openapi_tags=) -- FOUND
- File exists: `apps/backend/openapi.json` (regenerated) -- FOUND
- File exists: `packages/api-client/src/schema.d.ts` (regenerated) -- FOUND
- Commit `0ba1cede` -- FOUND in git log
- Commit `42d5fc1e` -- FOUND in git log
- Commit `3b275527` -- FOUND in git log
- Post-commit drift gate exits 0 -- CONFIRMED
