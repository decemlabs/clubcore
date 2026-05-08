# Phase 21: OpenAPI drift gate refresh + api-client codegen - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-08
**Phase:** 21-openapi-drift-gate-refresh-api-client-codegen
**Mode:** `--auto` (Claude resolved every gray area to the recommended default; no AskUserQuestion calls)
**Areas discussed:** Sessions inclusion (Phase 23 timing), Operation ID convention, Contract smoke test, Plan layout

---

## Sessions inclusion (Phase 23 timing)

| Option | Description | Selected |
|--------|-------------|----------|
| Ship Phase 21 now without sessions paths; Phase 23 ships its own drift-gate refresh on its merge | Honors roadmap dependency note ("Phase 23 *if* it lands before this gate"); Phase 21 stays minimal and unblocks Phase 22's memberships/visits wiring | ✓ |
| Block Phase 21 on Phase 23 (start Phase 23 first, then run the refresh once for both) | Single regeneration commit covers all v1.2 + sessions; cleaner Git history | |
| Pre-emptively stub `/api/v1/auth/sessions` as a placeholder route in `app/api/v1/router.py` so Phase 21 freezes the path even if the implementation lands later | Forces a contract dummy that Phase 23 has to fill; risks shipping a 501-style route to prod | |

**[auto] Selection:** Option 1 (recommended default).
**Rationale captured in CONTEXT.md:** D-21-1 + D-21-2.

---

## Operation ID convention

| Option | Description | Selected |
|--------|-------------|----------|
| Keep FastAPI auto-derived `{func}_{path}_{method}` IDs (current convention across v1.1) | Zero churn; consistent with existing auth/clients routes; path-keyed access pattern in `fetcher.ts` doesn't depend on operationId ergonomics | ✓ |
| Set explicit `operation_id="listMembershipPlans"` etc. on every v1.2 route now | Cleaner generated client method names if a future RPC façade emerges; matches some teams' codegen norms | |
| Configure FastAPI `unique_id_function=` for a global short-ID rule | Centralizes the rename; still introduces churn across the v1.2 surface | |

**[auto] Selection:** Option 1 (recommended default).
**Rationale captured in CONTEXT.md:** D-21-3.

---

## Contract smoke test

| Option | Description | Selected |
|--------|-------------|----------|
| NEW `packages/api-client/src/schema.contract.test.ts` (vitest, type-only assertions on `paths`/`operations`) | Catches openapi-typescript regressions, accidental router prefix typos, operationId collisions; lives next to `fetcher.test.ts` in the same package | ✓ |
| No new test — rely on the CI drift gates + admin-web `tsc` to catch breakage at consumption time | Lowest churn; trades a forward-guard for a downstream debug burden when codegen breaks subtly | |
| Add a Python-side OpenAPI schema test (e.g. `tests/integration/test_openapi_shape.py` asserting path keys) instead | Closer to the source of truth, but doesn't validate the typed-transport surface admin-web actually consumes | |

**[auto] Selection:** Option 1 (recommended default).
**Rationale captured in CONTEXT.md:** D-21-4.

---

## Plan layout

| Option | Description | Selected |
|--------|-------------|----------|
| Single `21-01-PLAN.md` with sequential steps (regenerate spec → regenerate codegen → contract test → docs) | Smallest-surface phase in v1.2 (1 file regenerated, 1 file added); mechanically sequential; mirrors Phase 18 plan-04 single-small-plan precedent | ✓ |
| Two plans (`21-01` regeneration; `21-02` contract test + docs) | Tidy task split; adds wave-orchestration overhead with no parallelism win | |
| Three plans (split each artifact into its own plan) | Maximally atomic but pure ceremony at this surface size | |

**[auto] Selection:** Option 1 (recommended default).
**Rationale captured in CONTEXT.md:** CD-01.

---

## Claude's Discretion

- **CD-01 — Single plan:** finalised at `/gsd-plan-phase`.
- **CD-02 — Atomic commit per artifact:** standard executor behavior; planner doesn't need to prescribe.
- **CD-03 — No `--all-phases` re-run from this phase:** trust Phases 16/17/19 CI-green merges; Phase 21 PR re-runs both drift gates as part of its own CI.

## Deferred Ideas

- Explicit short operation IDs (`operation_id="listMembershipPlans"`) — v1.3+ ergonomics.
- Runtime schema validation on the FE side (zod from openapi) — defense-in-depth, v1.3+.
- Automatic operation tag taxonomy / hierarchical tags — wait until the API grows past 6-7 tag families.
- Cross-package type re-export (admin-web `shared/api/types.ts` deriving from `paths[...]`) — Phase 22.
- `@redocly/cli` lint or `spectral` rule pack on `openapi.json` — v1.3+ unless a breakage motivates.
- OpenAPI version bump to 3.1.x — defer unless a tool demands it.
- Contract test for `components/schemas` shape stability — over-specification for v1.2.
- `export_openapi.py` enhancements (`--check`, `--diff`, pre-commit) — CI gate already covers this.
- Pre-formatted sessions endpoints inclusion — Phase 23 will own when it ships.

---

*Phase: 21-openapi-drift-gate-refresh-api-client-codegen*
*Discussion logged: 2026-05-08 (--auto mode, no interactive questions)*
