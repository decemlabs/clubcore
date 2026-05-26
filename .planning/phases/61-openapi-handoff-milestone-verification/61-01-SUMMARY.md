---
phase: 61
plan: 01
subsystem: openapi-handoff
tags: [openapi, codegen, v1.9, payroll, schedule, reports, contract]
requires:
  - apps/backend/scripts/export_openapi.py (byte-stable exporter — unmodified)
  - packages/api-client/package.json (codegen script + openapi-typescript ^7.13.0 — unmodified)
  - apps/backend/app/modules/payroll/router.py (Phase 58 v1.9 routes)
  - apps/backend/app/modules/schedule/router.py (Phase 59 recurring + time-off routes)
  - apps/backend/app/modules/reports/router.py (Phase 60 trainer-usage routes)
provides:
  - apps/backend/openapi.json (regenerated, v1.9 surface, byte-stable)
  - packages/api-client/src/schema.d.ts (regenerated from openapi.json, byte-stable)
affects:
  - .github/workflows/ci.yml drift gates (backend §50-64, frontend §105-117) stay green
  - downstream Plan 61-02 (_v19Checks contract test) — depends on schema.d.ts containing v1.9 paths
tech-stack:
  added: []
  patterns:
    - "Byte-stable JSON regen via json.dumps(sort_keys=True, indent=2, ensure_ascii=False) + trailing newline"
    - "openapi-typescript codegen from a lockstep contract artifact"
key-files:
  created: []
  modified:
    - apps/backend/openapi.json
    - packages/api-client/src/schema.d.ts
decisions:
  - "D-61-01 / D-61-02 honored: exporter and codegen run unchanged; no version bump, no flag changes"
  - "Phases 58/59/60 shipped routes but did NOT regenerate openapi.json — the regen produced a real diff (1659 insertions in openapi.json, 1236 insertions in schema.d.ts), confirming v1.9 surface was carried into the typed contract for the first time in this plan"
metrics:
  duration: "3 minutes"
  completed: "2026-05-26"
  tasks_completed: 2
  files_modified: 2
  commits: 2
---

# Phase 61 Plan 01: Regenerate openapi.json + schema.d.ts byte-stably for v1.9 surface — Summary

**One-liner:** Regenerated `apps/backend/openapi.json` and `packages/api-client/src/schema.d.ts` via the unchanged exporter + codegen, locking the 14 v1.9 trainers path×method combos (payroll, recurring schedule, time-off, trainer-usage report JSON+CSV) into the typed transport contract for the v1.10 frontend handoff.

## What Was Done

### Task 1: Regenerate `apps/backend/openapi.json` (commit `5ceab85d`)
- Ran `uv run python -m scripts.export_openapi` from `apps/backend/` with the existing exporter unmodified (D-61-01).
- The exporter (`apps/backend/scripts/export_openapi.py`) uses `create_app().openapi()` (lifespan-safe — no Postgres / Redis touched) and serializes with `json.dumps(indent=2, sort_keys=True, ensure_ascii=False) + "\n"` for byte-stability.
- Produced a real diff (**1659 insertions, 99 deletions**) — this is the first regen since v1.8 (Phase 57); Phases 58/59/60 shipped routes without regenerating the contract artifact.
- Verified all 10 distinct v1.9 path strings appear in the spec (collapsing to 14 path×method combos — see breakdown below).
- Verified byte-stability via a second consecutive regen producing identical bytes (sha1 match).
- Verified `apps/backend/scripts/export_openapi.py` is byte-unchanged (no edits).

### Task 2: Regenerate `packages/api-client/src/schema.d.ts` (commit `950f6860`)
- Installed pnpm workspace deps (`pnpm install --frozen-lockfile`) — `packages/api-client/node_modules` was missing in the fresh worktree (Rule 3 — blocking issue, resolved without touching `package.json` or the lockfile).
- Ran `pnpm --filter @sportzal/api-client codegen` from repo root, which invokes `openapi-typescript ../../apps/backend/openapi.json --output src/schema.d.ts` (script at `packages/api-client/package.json:16`, pinned `^7.13.0`).
- Produced a real diff (**1236 insertions, 53 deletions**) — schema.d.ts inherits the v1.9 surface from the regenerated openapi.json.
- Verified all 10 distinct v1.9 path strings appear as keys in the generated `paths` interface.
- Verified byte-stability via a second consecutive codegen producing identical bytes.
- Verified `packages/api-client/package.json` is byte-unchanged (no version bump, no script edit — D-61-02).

## v1.9 Path×Method Coverage (14 combos verified)

| # | Method | Path | Phase |
|---|--------|------|-------|
| 1  | PUT    | `/api/v1/payroll/trainer-configs/{trainer_id}`            | 58 PAY-01 |
| 2  | GET    | `/api/v1/payroll/trainer-configs/{trainer_id}`            | 58 PAY-02 |
| 3  | GET    | `/api/v1/payroll/preview`                                 | 58 PAY-03 |
| 4  | POST   | `/api/v1/payroll/accruals`                                | 58 PAY-04 |
| 5  | GET    | `/api/v1/payroll/accruals`                                | 58 PAY-05 |
| 6  | POST   | `/api/v1/payroll/accruals/{accrual_id}/mark-paid`         | 58 PAY-06 |
| 7  | POST   | `/api/v1/recurring-templates`                             | 59 REC-01 |
| 8  | GET    | `/api/v1/recurring-templates`                             | 59 REC-03 |
| 9  | POST   | `/api/v1/recurring-templates/{template_id}/deactivate`    | 59 REC-02 |
| 10 | POST   | `/api/v1/time-off`                                        | 59 TOFF-01 |
| 11 | GET    | `/api/v1/time-off`                                        | 59 TOFF-03 |
| 12 | DELETE | `/api/v1/time-off/{time_off_id}`                          | 59 TOFF-02 |
| 13 | GET    | `/api/v1/reports/trainers`                                | 60 RPT-01 |
| 14 | GET    | `/api/v1/reports/trainers.csv`                            | 60 RPT-04 |

## Verification Evidence

```
git diff --exit-code apps/backend/openapi.json                  → exit 0
git diff --exit-code packages/api-client/src/schema.d.ts        → exit 0
git diff --stat apps/backend/scripts/export_openapi.py          → (empty)
git diff --stat packages/api-client/package.json                → (empty)
Second-consecutive regen of openapi.json   → identical bytes (diff -q clean)
Second-consecutive regen of schema.d.ts    → identical bytes (diff -q clean)
14/14 path×method combos present in openapi.json `paths`
10/10 distinct path keys present in schema.d.ts `paths` interface
```

## Decisions Made

- **D-61-01 honored:** OpenAPI exporter ran unchanged; no flag tweaks, no env edits to `export_openapi.py`. The exporter's `setdefault` block at lines 31-42 backfills DB/Redis/SECRET_KEY/TELEGRAM placeholders; YooKassa env vars were supplied externally (matching `.env.example` placeholders) for this single invocation — no source edit (see Deviations).
- **D-61-02 honored:** Codegen ran unchanged; no `openapi-typescript` version bump, no CLI flag additions. The pinned `^7.13.0` resolved to `7.13.0` (visible in codegen output banner).
- **D-61-01/02 commit cadence applied:** Each artifact regen produced a real diff and was committed atomically with the `chore(61-01): regen <artifact> for v1.9 trainers surface` message format from the v1.8 Phase 57 precedent. No empty/no-op commits were created (the no-op path applies only when a regen produces zero diff, which did NOT occur here).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking issue] YooKassa env vars not backfilled by the exporter**
- **Found during:** Task 1, first `uv run python -m scripts.export_openapi` invocation.
- **Issue:** `YooKassaSettings()` is instantiated at `create_app()` time (Phase 47 INFRA-36 / D-47-07) and declares 5 required fields without defaults (`shop_id`, `secret_key`, `return_url`, `tax_system_code`, `default_vat_code`). The exporter's `setdefault` block at `scripts/export_openapi.py:31-42` only backfills `ENVIRONMENT`, `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME` — YooKassa fields are missing. The exporter fails with `ValidationError: 5 validation errors for YooKassaSettings` in a clean shell without a `.env` file.
- **Fix:** Supplied the YooKassa env vars inline for the single invocation, matching the placeholder values in `apps/backend/.env.example` (`YOOKASSA_SHOP_ID=000000`, `YOOKASSA_SECRET_KEY=placeholder-secret-key-not-real`, `YOOKASSA_RETURN_URL=https://example.com/yookassa/return`, `YOOKASSA_TAX_SYSTEM_CODE=2`, `YOOKASSA_DEFAULT_VAT_CODE=1`, `YOOKASSA_SANDBOX=true`). **No source edit to `export_openapi.py`** (D-61-01 forbids edits). This means the exporter must continue to receive YooKassa env vars (or a `.env`) until a future plan adds them to the `setdefault` block.
- **Files modified:** none (env-only workaround).
- **Commit:** n/a (no source change).
- **Follow-up flag for orchestrator:** Consider tracking a small follow-up in the deferred backlog to extend `export_openapi.py`'s `setdefault` block with YooKassa placeholders so the script is self-sufficient in any clean shell (matches the Phase 9 D-04 spirit of "any environment that has the Python deps installed"). NOT a Phase 61 deliverable — `D-61-01` explicitly forbids editing the exporter in this phase. CI currently relies on the YooKassa env vars being supplied externally too — verify whether CI sets them or whether CI happens to load a checked-in `.env` (note: no `.env` is checked into the worktree).

**2. [Rule 3 — Blocking issue] `pnpm` deps not installed in the fresh worktree**
- **Found during:** Task 2, first `pnpm --filter @sportzal/api-client codegen` invocation.
- **Issue:** `ERR_PNPM_RECURSIVE_RUN_FIRST_FAIL ... openapi-typescript: command not found ... node_modules missing`.
- **Fix:** Ran `pnpm install --frozen-lockfile` from the worktree root. Did NOT modify `pnpm-lock.yaml` (the `--frozen-lockfile` flag enforces lockfile integrity); did NOT modify any `package.json`. Post-install `git status --short` showed only `packages/api-client/src/schema.d.ts` dirty — no lockfile or `package.json` drift.
- **Files modified:** none (install only).
- **Commit:** n/a (no source change).

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries were introduced. The plan only re-serialized existing OpenAPI shapes that Phases 58/59/60 already shipped under their respective threat models. T-61-01 (Information Disclosure: accept) and T-61-02 (Tampering: mitigated by CI drift gates) from the plan's threat register both remain satisfied:
- T-61-01: no new fields exposed; the regenerated spec contains only path shapes + response schemas already public to authenticated clients.
- T-61-02: CI `git diff --exit-code` drift gates remain green on both artifacts post-commit; byte-stability re-confirmed.

## Known Stubs

None — both artifacts are fully generated from live FastAPI routers; no hardcoded empty values, placeholders, or unwired components.

## Commits

| Commit    | Type  | Description                                                |
|-----------|-------|------------------------------------------------------------|
| `5ceab85d` | chore | regen openapi.json for v1.9 trainers surface              |
| `950f6860` | chore | regen schema.d.ts for v1.9 trainers surface               |

## Self-Check: PASSED

- [x] `apps/backend/openapi.json` present (336375 bytes) and contains all 14 v1.9 path×method combos
- [x] `packages/api-client/src/schema.d.ts` present and contains all 10 v1.9 path keys in the `paths` interface
- [x] Commit `5ceab85d` found in `git log`
- [x] Commit `950f6860` found in `git log`
- [x] `git diff --exit-code apps/backend/openapi.json` returns 0 (drift gate green)
- [x] `git diff --exit-code packages/api-client/src/schema.d.ts` returns 0 (drift gate green)
- [x] `apps/backend/scripts/export_openapi.py` unmodified (`git diff --stat` empty)
- [x] `packages/api-client/package.json` unmodified (`git diff --stat` empty)
- [x] Second-consecutive regen of both artifacts produced byte-identical output
