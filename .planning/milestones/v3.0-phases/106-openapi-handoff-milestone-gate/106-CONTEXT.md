# Phase 106: OpenAPI Handoff + Milestone Gate - Context

**Gathered:** 2026-06-13
**Status:** Ready for planning
**Mode:** Infrastructure / verification ceremony (grey-area discuss skipped — all-technical
success criteria, no user-facing behavior, no new code). Fact-driven from the gate inventory.

<domain>
## Phase Boundary

Confirm the staff OpenAPI contract is byte-stable, run the FULL milestone gate green, and
verify all 30 v3.0 requirements are satisfied with no open blockers. v3.0 added ZERO new
backend domains/endpoints (D-V30-SCOPE-WIRE) — the staff contract is unchanged vs
`contract-freeze-v1.11.0` / v2.6. The "handoff" is therefore the byte-stable contract +
green gate; NO new Postman/runbook artifact is expected (wire-only milestone).

**In scope:** regenerate openapi.json + schema.d.ts byte-stably (confirm no drift); run the
full 7-gate suite; classify any pytest failure as the 4 documented pre-existing flakes vs a
real v3.0 regression (fix regressions); verify 30/30 v3.0 requirements; produce a concise
gate-evidence summary. **Out of scope:** new backend endpoints; new contract guards
(`_v30Checks` NOT expected — nothing new to guard); deployment/launch (v3.1+); the live
human-UAT items deferred from P100-P105 (batch-validated separately, tracked in STATE).
</domain>

<decisions>
## Implementation Decisions

### OpenAPI byte-stability (HND-01 core)
- Regenerate: `cd apps/backend && uv run python -m scripts.export_openapi` → drift check
  `git ls-files --error-unmatch apps/backend/openapi.json && git diff --exit-code apps/backend/openapi.json`
  → MUST be byte-unchanged (v3.0 touched no backend routes; only a test-path repoint + doc comments).
- Regenerate schema.d.ts: `pnpm --filter @clubcore/api-client codegen` → drift check
  `git ls-files --error-unmatch packages/api-client/src/schema.d.ts && git diff --exit-code packages/api-client/src/schema.d.ts`
  → byte-unchanged. The existing `_v26Checks[8]` AssertNonNever guards stay; **NO `_v30Checks`**
  (zero new endpoints → nothing to add). If a guard expects a new count, that would be wrong — leave it.

### Full milestone gate (run all 7 CI gates locally; postgres+redis+s3 are up)
- **backend:** `uv sync --frozen && uv run ruff check && uv run ruff format --check &&
  uv run mypy --strict app && uv run lint-imports && uv run python -m scripts.export_openapi &&
  git diff --exit-code apps/backend/openapi.json && uv run alembic upgrade head && uv run pytest`
  (with `DATABASE_URL='postgresql+asyncpg://app:app@localhost:5432/clubcore'
  REDIS_URL='redis://localhost:6379/0'`).
- **frontend (recursive):** `pnpm install --frozen-lockfile` + `pnpm -r --filter '!client-pwa'
  --filter '!admin-app' lint/typecheck/test` + `pnpm -F @clubcore/api-client test` + codegen + schema.d.ts drift.
- **admin-app:** `pnpm -F @clubcore/admin-app typecheck && lint && test && build` (~337 tests).
- **client-pwa:** `pnpm -F @clubcore/client-pwa typecheck && lint && test && build` (222 tests;
  the vitest.config.ts typecheck was fixed in P105 — confirm still green).
- **redocly:** `npx -y @redocly/cli@latest lint apps/backend/openapi.json`.

### Pre-existing flakes — ACCEPTED, not v3.0 regressions (documented v2.3→v2.6)
Treat ONLY these as accepted; ANY other failure is a v3.0 regression to FIX:
1. `test_freeze_race` — timing-dependent 409 reason-code; passes in isolation.
2. `test_audit_taxonomy` (full-suite) — leaked Telegram/respx socket GC misattribution
   (`PytestUnraisableExceptionWarning`); passes in isolation; frozenset+AST guard can't be a real gap.
3. `tests/test_client_promo_validate.py` — whole-tree promo F821/ruff debt; pre-dates v2.x.
4. `test_alembic_clean` — `promo_codes.models` unregistered in `alembic/env.py` since v2.0; intermittent.
**If pytest fails ONLY on these (for these documented reasons), the gate PASSES modulo accepted debt.**
Confirm the audit-taxonomy soundness by running the 4 audit-taxonomy test files together in isolation
(they pass) per the documented procedure if the full-suite artifact appears.

### Requirement coverage (HND-01 criterion 3)
- Cross-reference `.planning/REQUIREMENTS.md`: all 30 v3.0 requirements (FND-01..04, AUTH-01..03,
  CLI-01..03, MEM-01..03, SCH-01/02, TRN-01/02, ATT-01/02, FIN-01/02, RPT-01..03, SET-01/02,
  ADMW-01..03, HND-01) marked satisfied across P100-105. Confirm none left open; the deferred
  human-UAT items are acknowledged-deferred (not unsatisfied requirements).

### Handoff artifact
- NO dedicated v3.0 runbook/Postman (wire-only, no new API surface). The handoff = byte-stable
  contract + green gate. Optionally write a concise `106` gate-evidence summary in the phase dir.

### Dev-DB note (STATE blocker)
- STATE flags a dev-DB carry-over (stale `ix_referral_codes_client_id`). The host pytest rebuilds
  schema / uses the migrated docker DB; this was already addressed by the P100 `down -v` + fresh
  migrate. `alembic upgrade head` + `alembic check` should be clean (modulo the test_alembic_clean flake).

### Claude's Discretion
- Whether to run the full gate as one executor pass or split; the gate-evidence summary format;
  whether to commit a v3.0 contract-freeze tag note. Following prior milestone-gate phases.
</decisions>

<code_context>
## Existing Code Insights (gate inventory)

- Full 7-gate CI: backend (ruff/format/mypy --strict/lint-imports/openapi-drift/alembic/pytest),
  frontend recursive, admin-app, client-pwa, redocly, (+ postgres/redis services).
- openapi export: `apps/backend/scripts/export_openapi.py` (lifespan-safe, env-placeholder-safe,
  `json.dumps(indent=2,sort_keys=True,ensure_ascii=False)+"\n"`). Drift: git diff --exit-code.
- schema.d.ts: `packages/api-client` `codegen` → openapi-typescript; `schema.contract.test.ts`
  has `_v26Checks` (8 AssertNonNever) + toHaveLength runtime assert — unchanged for v3.0.
- Contract freeze baseline tag: `contract-freeze-v1.11.0`; v2.6 additive-safe; v3.0 byte-identical.
- Backend ~2654 pytest baseline (v2.4); admin-app ~337; client-pwa 222.
- 4 documented pre-existing flakes (above) — carried forward through v2.6 audit.
- Docker stack up: postgres+redis+s3 (localhost; creds app/app; db clubcore; migrated to 0069 head).

## v3.0 backend touch surface (what could affect pytest)
- P100: test_rbac_parity.py repointed to admin-app (passes 4/4).
- P105: test_byte_parity.py repointed to admin-app (passes 3/3 warm) + doc comments in
  permissions.py/config.py/loyalty/permissions.py (comment-only, mypy/ruff green).
- No business-logic backend changes → no new pytest regressions expected.
</code_context>

<specifics>
## Specific Ideas

- The KEY HND-01 deliverable: openapi.json + schema.d.ts byte-unchanged (prove via git diff --exit-code).
- v3.0 is the FIRST milestone where the OpenAPI handoff is a NO-OP (no new surface) — the discipline
  holds precisely because nothing changed.
- Distinguish the 4 accepted flakes from real regressions; only regressions block.
- No `_v30Checks`, no runbook — wire-only.
</specifics>

<deferred>
## Deferred Ideas

- Live human-UAT batch validation (P101-P104 items + P100 already validated) — acknowledged-deferred,
  tracked in STATE Deferred Items; the milestone audit notes them. NOT requirement gaps.
- v3.1 production deploy/launch + any operator handoff runbook — future milestone.
- The 4 pre-existing test flakes — carried forward (not v3.0 scope).
</deferred>
