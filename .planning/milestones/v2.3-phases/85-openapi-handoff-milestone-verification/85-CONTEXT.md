# Phase 85: OpenAPI Handoff + Milestone Verification - Context

**Gathered:** 2026-06-05
**Status:** Ready for planning
**Mode:** Infrastructure phase — smart-discuss skipped (pure regen + forward-guards + gate verification; no user-facing behavior, no grey areas). Follows the established HND pattern from Phase 72 (v2.0) / Phase 81 (v2.2).

<domain>
## Phase Boundary

Freeze the v2.3 contract: byte-stable regenerate `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts` so they contain every new v2.3 loyalty/autopay client path; add `_v23Checks` `AssertNonNever` forward-guards (+ a runtime path-count assertion) for each new path×method combo in `packages/api-client/src/schema.contract.test.ts`; confirm the CI drift gates are green (committed artifacts == regenerated); confirm existing staff paths remain byte-identical to `contract-freeze-v1.11.0` (only additive v2.3 paths); and run the full milestone gate (backend pytest, mypy --strict, lint-imports, PWA vitest/tsc, Redocly lint, no-edit guard on permissions.py/can.ts/registry.ts).

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — pure infrastructure/verification phase following the Phase 72 / Phase 81 HND precedent. Use the established conventions:

- **Regen**: `cd apps/backend && DATABASE_URL=... uv run python -m scripts.export_openapi` then `pnpm -F @clubcore/api-client codegen`. Both have already been regenerated additively during Phases 82/83; this phase ensures they are CURRENT after Phase 84 (e.g. the `confirmation_type` enum now includes `'autopay'` if it surfaces in any response schema) and byte-stable (a fresh regen produces zero `git diff`).
- **New v2.3 client/staff paths to guard** in `_v23Checks` (verify exact set against the regenerated openapi.json):
  - `GET /api/v1/client/loyalty/balance` (Phase 82, LOYL-01)
  - `GET /api/v1/client/loyalty/history` (Phase 82, LOYL-02)
  - `POST /api/v1/clients/{client_id}/loyalty/grant` (Phase 82, ACCR-02 — owner-only staff path, additive)
  - The checkout request body's new `loyaltyRedeemKopecks` field (Phase 83, REDM-01) — guard via the request-body type if not already covered by the existing checkout guard.
  - Autopay (Phase 84) added NO new client HTTP paths (cron + webhook are internal); the only contract surface is the additive `confirmation_type='autopay'` enum value — no new path guard needed, but confirm it does not break existing checkout guards.
- **Forward-guard shape**: `type _XxxGet = AssertNonNever<paths['/api/v1/...']['get']>` per the existing `_v2xChecks` style, grouped under a `_v23Checks` comment block; bump the runtime `toHaveLength`/path-count assertion in the same file. Do NOT touch the existing `_v1x`/`_v20`/`_v21`/`_v22` guards.
- **Staff parity**: existing staff paths must remain byte-identical to `contract-freeze-v1.11.0` — v2.3 only ADDS paths (loyalty balance/history client paths + the owner-grant staff path); it must not MODIFY any existing staff path. The owner-grant is additive (new path), consistent with the v2.0/2.1/2.2 additive precedent.
- **Drift gates**: after regen + commit, `git diff --exit-code apps/backend/openapi.json` and `git diff --exit-code packages/api-client/src/schema.d.ts` must be clean; Redocly lint clean.
- **Milestone gate**: run + confirm green — backend `uv run pytest` (incl. all new ledger/redemption/autopay race + idempotency tests), `uv run mypy --strict app`, `uv run lint-imports`, PWA `pnpm -F @clubcore/client-pwa typecheck && vitest run`, Redocly lint, and a no-edit guard confirming `permissions.py` / `can.ts` / `registry.ts` were not modified by v2.3 (CISO-01 byte-parity intact). Document any pre-existing-known failures (the documented flaky `test_freeze_race`; whole-tree ruff/DTZ/promo debt) as NOT v2.3 regressions.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `packages/api-client/src/schema.contract.test.ts` — the home of the `_v2xChecks` `AssertNonNever<paths[...]>` forward-guards + runtime path-count assertion. Add `_v23Checks` here.
- `apps/backend/scripts/export_openapi.py` — `uv run python -m scripts.export_openapi` regenerates `apps/backend/openapi.json` from the live FastAPI app.
- `packages/api-client/package.json` `codegen` — `openapi-typescript ../../apps/backend/openapi.json --output src/schema.d.ts`.
- `.github/workflows/ci.yml` — drift gates: backend `export_openapi` + `git diff --exit-code apps/backend/openapi.json`; frontend `codegen` + `git diff --exit-code packages/api-client/src/schema.d.ts`; Redocly lint job.
- Precedent: Phase 72 (`_v20Checks` + Client-Portal additive regen + staff drift gate) and Phase 81 (`_v22Checks` byte-stable regen + staff-contract-byte-identical assertion).

### Established Patterns
- Additive contract evolution: new milestone paths are added; existing staff paths stay byte-identical to the frozen baseline.
- Byte-stable regen: a fresh regen after commit yields zero `git diff` (deterministic export).
- Forward-guards are type-level `AssertNonNever` (compile-time, via `tsc`/vitest) — a path silently dropping out of the schema flips the guard to a type error.

### Integration Points
- `apps/backend/openapi.json` (regen) + `packages/api-client/src/schema.d.ts` (codegen).
- `packages/api-client/src/schema.contract.test.ts` (`_v23Checks`).
- CI drift gates + Redocly lint (already wired).

</code_context>

<specifics>
## Specific Ideas

- This is the final v2.3 phase — after it, the milestone audit/complete/cleanup lifecycle runs.
- openapi.json + schema.d.ts may already be current (regenerated additively in 82/83). Phase 85 must still run a fresh regen to (a) pick up any Phase-84 contract surface (confirmation_type enum) and (b) prove byte-stability.

</specifics>

<deferred>
## Deferred Ideas

None — final milestone phase; verification only.

</deferred>
