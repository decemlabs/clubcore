# Phase 89: OpenAPI Handoff + Milestone Verification - Context

**Gathered:** 2026-06-06
**Status:** Ready for planning
**Mode:** Infrastructure phase — smart-discuss skipped (pure regen + forward-guards + gate verification; no user-facing behavior, no grey areas). Follows the established HND pattern from Phase 72 (v2.0) / Phase 81 (v2.2) / Phase 85 (v2.3).

<domain>
## Phase Boundary

Freeze the v2.4 contract: byte-stable regenerate `apps/backend/openapi.json` +
`packages/api-client/src/schema.d.ts` so they contain every new v2.4 path (gym-info,
notification-inbox, trainer-detail) — REPLACING the hand-added forward-stub entries that
phases 86/87/88 inserted into `schema.d.ts` with the authoritative generated output; add
`_v24Checks` `AssertNonNever` forward-guards (+ a runtime path-count assertion) for each new
path×method combo in `packages/api-client/src/schema.contract.test.ts`; confirm the CI drift
gates are green (committed artifacts == regenerated); confirm existing staff paths remain
byte-identical to `contract-freeze-v1.11.0` (only additive v2.4 paths); and run the full
milestone gate (backend pytest, mypy --strict, lint-imports, PWA vitest/tsc, Redocly lint,
no-edit guard on permissions.py/can.ts/registry.ts beyond the additive gym RBAC entry).

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — pure infrastructure/verification phase following the Phase 72 / 81 / 85 HND precedent. Use the established conventions:

- **Regen**: `cd apps/backend && uv run python -m scripts.export_openapi` (regenerates
  `apps/backend/openapi.json` from the live FastAPI app) then `pnpm -F @clubcore/api-client codegen`
  (`openapi-typescript ../../apps/backend/openapi.json --output src/schema.d.ts`). This is the
  AUTHORITATIVE regen — it overwrites the hand-added forward-stubs that 86/87/88 executors put
  in `schema.d.ts` (those were stopgaps explicitly deferred to this phase). A fresh regen after
  commit must produce zero `git diff` (byte-stable, deterministic export).
- **New v2.4 paths to guard** in `_v24Checks` (verify the EXACT set + operationIds against the
  regenerated openapi.json — paths below are from CONTEXT/SUMMARY of 86/87/88):
  - Phase 86: `GET /api/v1/client/gym`; `PUT /api/v1/gym` (owner write, additive staff path)
  - Phase 87: `GET /api/v1/client/notifications`; `PATCH /api/v1/client/notifications/{notification_id}/read`;
    `PATCH /api/v1/client/notifications/read-all`; `POST /api/v1/client/push-tokens`
    (confirm exact path-param name `{notification_id}` vs `{id}` from the regenerated spec)
  - Phase 88: `GET /api/v1/client/trainers/{trainer_id}` (new client detail). The owner
    `PATCH /api/v1/trainers/{trainer_id}` is an EXISTING path with additive fields
    (bio/specialization/photo_url) — guard the new request-body fields via the body type if not
    already covered by an existing trainers-PATCH guard (mirrors the v2.3 `loyaltyRedeemKopecks`
    request-body guard precedent).
- **Forward-guard shape**: `type _XxxGet = AssertNonNever<paths['/api/v1/...']['get']>` per the
  existing `_v2xChecks` style, grouped under a `_v24Checks` comment block; bump the runtime
  `toHaveLength`/path-count assertion. Do NOT touch the existing `_v1x`/`_v20`/`_v21`/`_v22`/`_v23` guards.
- **Staff parity**: existing staff paths must remain byte-identical to `contract-freeze-v1.11.0` —
  v2.4 only ADDS paths (client gym/notifications/trainer-detail + owner gym PUT) and additively
  EXTENDS the existing trainers PATCH body. The gym RBAC entry (`Resource.GYM`, Phase 86) is the
  one intentional additive change to permissions.py/can.ts/registry.ts — the no-edit guard must
  treat it as the expected v2.4 RBAC addition, not a violation.
- **Drift gates**: after regen + commit, `git diff --exit-code apps/backend/openapi.json` and
  `git diff --exit-code packages/api-client/src/schema.d.ts` must be clean; Redocly lint clean.
- **Milestone gate**: run + confirm green — backend `uv run pytest` (incl. all new gym/notifications/
  trainer tests), `uv run mypy --strict app`, `uv run lint-imports`, PWA
  `pnpm -F @clubcore/client-pwa typecheck && vitest run`, Redocly lint, and a no-edit guard on
  permissions.py/can.ts/registry.ts (expecting ONLY the additive gym RBAC entry). Document any
  pre-existing-known failures (documented flaky `test_freeze_race`; whole-tree ruff/DTZ/promo debt;
  pre-existing `test_alembic_clean`) as NOT v2.4 regressions.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `packages/api-client/src/schema.contract.test.ts` — home of the `_v2xChecks`
  `AssertNonNever<paths[...]>` forward-guards + runtime path-count assertion. Add `_v24Checks` here.
- `apps/backend/scripts/export_openapi.py` — `uv run python -m scripts.export_openapi` regenerates
  `apps/backend/openapi.json` from the live FastAPI app.
- `packages/api-client/package.json` `codegen` — `openapi-typescript ../../apps/backend/openapi.json --output src/schema.d.ts`.
- `.github/workflows/ci.yml` — drift gates (backend export_openapi + git diff --exit-code; frontend
  codegen + git diff --exit-code) + Redocly lint job.
- Precedent: Phase 72 (`_v20Checks`), Phase 81 (`_v22Checks`), Phase 85 (`_v23Checks`) — same shape.

### Established Patterns
- Additive contract evolution: new milestone paths added; existing staff paths byte-identical to baseline.
- Byte-stable regen: fresh regen after commit yields zero git diff (deterministic export).
- Forward-guards are compile-time `AssertNonNever` (via tsc/vitest) — a dropped path flips to a type error.
- The hand-added schema.d.ts entries from 86/87/88 (gym GET/PUT, notifications x4, trainer detail GET +
  owner PATCH body) are stopgaps — this phase's real regen is the source of truth and may reshape them.

### Integration Points
- `apps/backend/openapi.json` (regen) + `packages/api-client/src/schema.d.ts` (codegen).
- `packages/api-client/src/schema.contract.test.ts` (`_v24Checks`).
- CI drift gates + Redocly lint (already wired).

</code_context>

<specifics>
## Specific Ideas

- This is the FINAL v2.4 phase — after it, the milestone audit → complete → cleanup lifecycle runs.
- The hand-added schema.d.ts stubs may not be byte-identical to openapi-typescript output; the
  authoritative regen WILL overwrite them and the drift gate proves byte-stability thereafter.
- Confirm the exact notifications path-param spelling (`{notification_id}` vs `{id}`) and the
  trainer-detail path-param (`{trainer_id}`) against the regenerated openapi.json before writing guards.

</specifics>

<deferred>
## Deferred Ideas

None — final milestone phase; verification only.

</deferred>
