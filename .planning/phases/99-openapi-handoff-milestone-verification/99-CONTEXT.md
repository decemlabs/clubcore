# Phase 99: OpenAPI Handoff + Milestone Verification - Context

**Gathered:** 2026-06-08
**Status:** Ready for planning
**Mode:** Auto-generated (smart discuss — infrastructure/handoff phase, no grey areas)

<domain>
## Phase Boundary

Freeze the v2.6 referral surface into a byte-stable API contract and run the full
v2.6 milestone gate green. No new business behavior — contract regeneration,
forward-guard checks, and gate verification only.

Requirement: HND-01.

Endpoints to surface in the contract (all built in Phases 96–98):
- `GET /api/v1/client/referral/code`
- `POST /api/v1/client/referral/capture`
- `GET /api/v1/i/{code}` (public deep-link resolver)
- `GET /api/v1/referral/config` (owner)
- `PUT /api/v1/referral/config` (owner)
- `GET /api/v1/client/referral/summary` (Phase 98)

Success criteria (all technical):
1. `apps/backend/openapi.json` and `packages/api-client/src/schema.d.ts` regenerate byte-stably; `git diff --exit-code` clean on both.
2. `_v26Checks` `AssertNonNever` tuple in `schema.contract.test.ts` covers all new v2.6 path×method combos with a `toHaveLength(N)` assertion.
3. Staff contract paths byte-identical to the Phase 95 baseline (drift gate green); CISO-01 no-edit guard passes.
4. Full milestone gate green: backend `pytest` + `mypy --strict` + `lint-imports` + client-pwa `vitest` + Redocly lint.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — infrastructure/handoff phase, discuss skipped. **Follow the established Phase 95 (v2.5) → Phase 89 (v2.4) handoff pattern EXACTLY.** Use the existing tooling; do not invent new mechanisms.

Key precedent (from `.planning/milestones/v2.5-phases/95-openapi-handoff/`):
- **Plan 01 — OpenAPI freeze:** register a `"Referral"` OpenAPI tag (after `"Client-Portal"`/`"Messaging"`, preserving D-64-TAG-ORDER) and tag the referral routes; regenerate `apps/backend/openapi.json` (sorted keys, byte-stable); verify byte-stability via consecutive-run diff; Redocly lint clean; staff drift gate vs the Phase 95 baseline (the prior frozen commit) — staff/admin contract paths byte-identical (CISO-01 no-edit guard).
- **Plan 02 — Schema codegen + milestone gate:** regenerate `packages/api-client/src/schema.d.ts` from the frozen `openapi.json` via the existing openapi-typescript codegen (this ADDS the `/client/referral/*` + `/i/{code}` paths, retiring the Phase-98 cast escape hatch in `clientQueries.ts`); add a `_v26Checks` `AssertNonNever[N]` tuple in `packages/api-client/src/schema.contract.test.ts` mirroring `_v25Checks`, with `toHaveLength(N)` where N = the new v2.6 path×method count (+ any POST-body realization entry, as in `_v25Checks[7]`); mark HND-01 complete in REQUIREMENTS.md; run the full milestone gate.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets / Precedent
- `.planning/milestones/v2.5-phases/95-openapi-handoff/95-01-PLAN.md` + `95-02-PLAN.md` + their SUMMARYs — the exact two-plan handoff recipe to mirror.
- `apps/backend/app/main.py` — `OPENAPI_TAGS` list + `_customize_openapi()` post-processor (sorted-keys serialization, manual path injection if needed).
- `apps/backend/openapi.json` — the frozen contract artifact (regenerate, byte-stable).
- `packages/api-client/src/schema.d.ts` — generated TS types (regenerate from openapi.json).
- `packages/api-client/src/schema.contract.test.ts` — `_v25Checks` AssertNonNever tuple is the template for `_v26Checks`.
- `apps/backend/app/modules/referrals/router.py` — the routers whose routes need the `"Referral"` tag.
- Redocly config + the drift-gate mechanism used in Phase 95 (staff-contract byte-parity vs prior baseline).

### Established Patterns
- Byte-stable openapi.json via FastAPI `_customize_openapi` with `sort_keys=True`.
- `openapi-typescript` deterministic codegen; verify byte-stability with a consecutive-run diff.
- `_vNNChecks` `AssertNonNever` forward-guard tuple + `toHaveLength(N)` arity assertion.
- Drift gate: staff/admin contract paths compared byte-for-byte to the prior milestone baseline (CISO-01 no-edit guard — admin-web frozen).
- Milestone gate ordering: mypy --strict → lint-imports → pytest (incl. CISO-01) → vitest → Redocly.

### Integration Points
- Phase 98 left `clientQueries.ts` referral hooks using a cast escape hatch because `/client/referral/*` were not yet in `schema.d.ts`. After regen, those paths exist — optionally tighten the casts (low priority; not a gate requirement, but note it).
- The dev Postgres needs a clean re-migrate (`docker compose down -v` + migrate + seed) before any LIVE manual verification — see STATE.md blocker. Test-suite gates rebuild schema and are unaffected.

</code_context>

<specifics>
## Specific Ideas

- Mirror Phase 95 exactly: a `"Referral"` OpenAPI tag, two plans (freeze, then codegen + gate).
- `_v26Checks` arity = count of new v2.6 path×method combos surfaced in the contract.
- schema.d.ts regen retires the Phase-98 cast escape hatch in clientQueries.ts.

</specifics>

<deferred>
## Deferred Ideas

- Live manual verification (the 98-HUMAN-UAT browser items + dev-DB clean re-migrate) — operator/browser task, deferred during the autonomous run; surfaces in the milestone audit.
- `ReferralLandingScreen.formatBonusPreview` Phase-99 follow-up (welcomeBonusKopecks vs days) — cosmetic, decide during/after handoff; not an HND-01 gate item.

</deferred>
