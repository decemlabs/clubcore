# Phase 21: OpenAPI drift gate refresh + api-client codegen - Context

**Gathered:** 2026-05-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 21 ships the **byte-frozen FE↔BE contract** for the v1.2 surface that landed in Phases 16/17/19. The Phase 9 drift-gate machinery (`apps/backend/scripts/export_openapi.py` + `pnpm --filter @sportzal/api-client codegen` + the two `git diff --exit-code` CI gates) already exists and works; Phase 21 is the act of **regenerating the artifacts post-merge**, **committing the regenerated files**, and **proving the gates stay green** so Phase 22 can consume typed `paths['/api/v1/membership-plans']`, `paths['/api/v1/memberships']`, and `paths['/api/v1/visits']` from `apps/admin-web`.

**Concrete factual baseline (verified at discuss-phase time):**
- `apps/backend/openapi.json` is **already current and byte-stable** — re-running `uv run python -m scripts.export_openapi` from `apps/backend/` produces a 0-byte diff against `HEAD`. The `paths` map already includes all v1.2 endpoints: `/api/v1/membership-plans`, `/api/v1/membership-plans/{plan_id}`, `/api/v1/memberships`, `/api/v1/memberships/{membership_id}`, `/api/v1/memberships/{membership_id}/cancel`, `/api/v1/visits`, `/api/v1/visits/{visit_id}` (verified via `grep '"/api/v1/'`). The committed openapi.json was kept in sync as Phases 16/17/19 landed because each phase's CI gate forced `git diff --exit-code apps/backend/openapi.json` to pass — i.e. the gate already works as designed.
- `packages/api-client/src/schema.d.ts` is **stale** — running `pnpm --filter @sportzal/api-client codegen` produces a **+896 / −13 diff** (909 lines changed). The committed schema.d.ts still reflects only the v1.1 surface (auth + clients). This is the actual delivery work of Phase 21: regenerate, commit, prove the gate green.
- **No new operation IDs need to be set explicitly.** FastAPI auto-derives operationIds from the function name + path + method (e.g. `list_plans_api_v1_membership_plans_get`, `create_visit_api_v1_visits_post`). Existing v1.1 routes (auth/clients) use the same auto-derived convention — Phase 21 stays consistent.
- **Sessions endpoints (`GET /api/v1/auth/sessions`, `POST /api/v1/auth/sessions/{family_id}/revoke`) are NOT yet in the spec.** Phase 23 owns them and is parallel-eligible. The roadmap explicitly says "Depends on: Phases 16, 17, 19 (and Phase 23 if active-sessions endpoints land there before this gate)" — i.e. if Phase 23 has not merged when Phase 21 runs, Phase 21 ships **without** the sessions paths and Phase 23 will commit a follow-up `openapi.json` + `schema.d.ts` diff (the drift gate forces this anyway).

**In scope:**
- **MODIFY** `packages/api-client/src/schema.d.ts` — regenerate via `pnpm --filter @sportzal/api-client codegen`. The +896-line diff is the v1.2 paths and component schemas. Commit verbatim.
- **VERIFY** `apps/backend/openapi.json` — re-run `uv run python -m scripts.export_openapi` from `apps/backend/`; assert `git diff --exit-code apps/backend/openapi.json` passes (it currently does — 0-byte drift). If a future-merged change made it dirty, commit the byte-stable rewrite.
- **NEW** `packages/api-client/src/schema.contract.test.ts` (or extend existing `fetcher.test.ts`) — TypeScript-level smoke test that imports `paths['/api/v1/membership-plans']`, `paths['/api/v1/memberships']`, `paths['/api/v1/visits']` and references `operations[...]` request/response shapes. Vitest passes if and only if the regenerated schema.d.ts exposes the expected typed paths. This is a forward-guard: if a future codegen breakage drops a path or renames an operationId, the test fails before Phase 22 finds out at integration time. Also serves as ROADMAP SC#3 ("typed `paths['/membership-plans']` etc. consumable from `apps/admin-web/src/shared/api`") evidence.
- **MODIFY** PROJECT.md `## Key Decisions` table — add D-21 row: "OpenAPI drift gate refresh shipped without sessions endpoints (Phase 23 not yet merged); schema.d.ts contract test added at packages/api-client level as forward-guard against silent codegen regressions."
- **OPTIONAL: MODIFY** `apps/backend/scripts/export_openapi.py` — `**only**` if a behavioral issue surfaces during re-run (e.g. a new pydantic schema causes non-stable JSON ordering). Default expectation: no edits — Phase 9 D-06 byte-stability (`indent=2, sort_keys=True, ensure_ascii=False, trailing newline`) already holds across the v1.2 surface as verified.

**Out of scope (locked to later phases):**
- **Sessions endpoints in spec/codegen** — Phase 23 owns `GET /api/v1/auth/sessions` and `POST /api/v1/auth/sessions/{family_id}/revoke`. Phase 23 will ship its own openapi.json + schema.d.ts diff as part of its merge (the drift gate forces this; Phase 21 leaves no infrastructure work for Phase 23 to do — only the regeneration commit). If Phase 23 has merged by the time Phase 21 runs, Phase 21 silently picks up the sessions paths in the same regeneration step (no extra logic needed; codegen reads whatever is in openapi.json).
- **Explicit `operation_id="..."` per route** — current FastAPI auto-derived IDs are consistent across the v1.1 + v1.2 surface (`{func}_{path}_{method}`). Switching to explicit, hand-curated short IDs (e.g. `listMembershipPlans`) is a v1.3+ ergonomics improvement; YAGNI for v1.2 (the typed path-based access pattern in fetcher.ts doesn't need short operationIds).
- **`apps/admin-web` consumption** — Phase 22 owns `features/memberships/api/*` and `features/visits/api/*` hooks plus the `/_protected/membership-plans`, `/_protected/memberships`, `/_protected/visits` routes. Phase 21 only ships the **typed transport layer** (schema.d.ts + the contract test); calling-site wiring is Phase 22.
- **`fetcher.ts` extensions** — the existing `fetcher.ts` (`packages/api-client/src/fetcher.ts`, Phase 9 D-09) is a generic `request<P, M>(...)` wrapper that consumes whatever paths/operations the schema exposes. No new methods, no new error types, no new auth helpers. Phase 23 may need a per-family CSRF wiring tweak when sessions ship — Phase 21 doesn't pre-empt it.
- **`packages/ui` placeholder** — still a placeholder per PROJECT.md; Phase 21 doesn't promote it.
- **OpenAPI client-side runtime validation** — schema.d.ts is **types-only**. Adding runtime validation (e.g. zod schemas auto-generated from openapi components) is a v1.3+ defense-in-depth concern. Phase 21 trusts the backend to honor the contract (which it does — Phase 4 D-25 `extra='forbid'` on requests + ResponseEnvelope on responses).
- **Cross-package types deduplication** — existing v1.1 admin-web ad-hoc types (e.g. `apps/admin-web/src/shared/api/types.ts` if any) are not migrated to derive from `paths[...]['responses']['200']['content']['application/json']['data']` in this phase. Phase 22 owns FE consumption refactors.
- **Operation tag taxonomy refactor** — current spec uses tags `["auth", "clients", "membership-plans", "memberships", "visits"]` (per `apps/backend/app/api/v1/router.py:include_router` calls). No grouping/reordering work in Phase 21.
- **CI workflow changes** — `.github/workflows/ci.yml` already has both drift gates (`Drift gate — apps/backend/openapi.json` + `Drift gate — packages/api-client/src/schema.d.ts`). No CI edits.

</domain>

<decisions>
## Implementation Decisions

### Sessions inclusion (Phase 23 timing)

- **D-21-1: Ship Phase 21 with the current spec — no sessions endpoints.** Phase 23 has not merged at discuss-phase time (STATE.md: "Phase 20 execution started" → Phase 20 just completed; Phase 23 is parallel-eligible but not started). The roadmap dependency text ("and Phase 23 if active-sessions endpoints land there before this gate") explicitly authorizes the "ship without sessions" path. Phase 23, when it ships, runs the same `export_openapi` + codegen + commit dance as part of its own deliverable — the drift gate enforces this automatically because Phase 23 will fail CI if it adds routes without committing the regenerated artifacts. Phase 21 does NOT block on Phase 23.
  - **Trade-off accepted:** Phase 22 (which depends on Phase 21) will find the sessions paths missing from `schema.d.ts` if Phase 22 starts before Phase 23 ships. Acceptable: Phase 22 is a wiring phase that imports `paths[...]` lazily; it can ship the memberships/visits routes first and add the active-sessions UI as a parallel sub-plan after Phase 23 lands. Roadmap already frames Phase 22 sessions UI as one of its 5 success criteria, not a gate.

- **D-21-2: If Phase 23 happens to land before Phase 21 (parallel-eligible reordering), Phase 21 silently picks up the sessions paths.** No code change to `export_openapi.py` or codegen; the regeneration step reads whatever endpoints `create_app()` registered. Concretely: a `git diff` after re-running both commands shows the sessions paths in addition to memberships/visits; the same single commit captures both. The Phase 21 contract test (see D-21-4) MUST conditionally include sessions-path assertions only if the spec advertises them — i.e. the test reads `Object.keys(paths)` rather than hardcoding the path list, so it stays green whether or not sessions are present.

### Operation IDs

- **D-21-3: Keep FastAPI auto-derived operation IDs (`{func_name}_{path}_{method}`).** Current v1.1 spec uses `login_api_v1_auth_login_post`, `list_clients_api_v1_clients_get`, etc.; v1.2 routes follow the same pattern (`list_plans_api_v1_membership_plans_get`, `create_visit_api_v1_visits_post`). No new lint, no `unique_id_function=` override, no per-route `operation_id="..."` parameter. Reasoning: the typed transport pattern in `fetcher.ts` accesses operations via `paths['/api/v1/foo']['get']` — operationId is a leaf identifier, not a path. Short hand-curated IDs would be ergonomic for a code-gen client (e.g. `client.memberships.list()`) but Sportzal uses path-keyed access; renaming would only add review surface and a one-time codegen churn with no reader benefit.

### Contract smoke test

- **D-21-4: NEW vitest file `packages/api-client/src/schema.contract.test.ts`** — type-only smoke test (no runtime fetch). Asserts:
  1. `paths['/api/v1/membership-plans']['get']` resolves (compile-time) to a non-`never` type and exposes a `responses['200']` shape.
  2. `paths['/api/v1/memberships']['post']['requestBody']` is non-empty (catches accidental `requestBody?: never` regressions when openapi-typescript versions change).
  3. `paths['/api/v1/visits']['get']['responses']['200']` is reachable.
  4. `paths['/api/v1/membership-plans/{plan_id}']` and `paths['/api/v1/memberships/{membership_id}/cancel']` exist (param-path coverage).
  5. **Conditional sessions check:** if `paths` keys include `'/api/v1/auth/sessions'`, assert its shape; otherwise skip with a clear comment ("Phase 23 not yet merged"). Implemented as a TypeScript conditional type or `if ('/api/v1/auth/sessions' in pathsValue) { ... }` runtime check on the `paths` object — but since paths is type-only, the cleaner pattern is a top-of-file `// @ts-expect-error` guarded probe that compiles when sessions are absent and resolves when present (Plan-phase chooses the exact assertion pattern; both work).
  - Why a contract test in `packages/api-client/` (not in admin-web): keeps the typed-transport package self-validating. If `apps/admin-web` imports breaking schema.d.ts, the failure would surface as a confusing admin-web tsc error far from the root cause; a `vitest run` in the api-client workspace pinpoints the regression at the typed transport layer.
  - Why vitest (not standalone tsc): the package already has `vitest.config.ts` and `fetcher.test.ts`; adding one more test file slots into the existing `pnpm --filter @sportzal/api-client test` command which CI already runs. Zero new tooling.

### Plan layout (Claude's discretion — finalise at `/gsd-plan-phase`)

- **CD-01 (default to apply): Single plan `21-01-PLAN.md`** — Phase 21 is the smallest-surface phase in v1.2 (1 file regenerated, 1 file added, 1 PROJECT.md row). The work is mechanically sequential (regenerate → contract test → PROJECT.md note); splitting into 2 or 3 plans adds wave-orchestration overhead without parallelism gain. Mirror Phase 18 plan-04 size precedent (single small plan for ~5-LOC compose service).
  - Plan steps inside `21-01-PLAN.md`:
    1. Run `uv run python -m scripts.export_openapi` from `apps/backend/`; commit `apps/backend/openapi.json` if any byte changed (defensive — current verification shows 0-byte diff, but the planner runs the command fresh against whatever HEAD is at execution time).
    2. Run `pnpm --filter @sportzal/api-client codegen` from repo root; commit `packages/api-client/src/schema.d.ts`.
    3. Add `packages/api-client/src/schema.contract.test.ts` per D-21-4.
    4. Run `pnpm --filter @sportzal/api-client test` and `pnpm --filter @sportzal/api-client typecheck`; both green.
    5. PROJECT.md `## Key Decisions` row D-21 (per spec above).
    6. REQUIREMENTS.md flip API-04 + API-05 from `[ ]` to `[x]` and update the requirements-status table.
- **CD-02 (default to apply): Single commit per artifact for blame clarity.** `git commit apps/backend/openapi.json` (if dirty) and `git commit packages/api-client/src/schema.d.ts` separately, plus a third commit for the contract test, plus a fourth for the docs. Mirrors v1.2 atomic-commit convention. The executor agent already does atomic commits per task; this is the default behavior, not a special instruction.
- **CD-03 (default to apply): No `--all-phases` re-run of prior CI gates from this phase.** Phase 21 trusts that Phases 16/17/19 each shipped a green CI on their merge commit (verifiable from `git log --oneline` showing `docs(20-03): owner sign-off recorded for AUTH-TG-11 locked Russian DM strings` etc.). The Phase 21 PR re-runs both drift gates as part of its own CI; if a hidden upstream regression shows up, the gate catches it and the executor handles it as a checkpoint deviation.

### Defaults if user says nothing at plan-phase review

All `D-21-*` decisions above are LOCKED by --auto resolution in this discussion. `CD-*` are Claude's discretion at plan-phase. User overrides at plan-phase review by saying e.g. "actually, set explicit `operation_id` on every v1.2 route now (revert D-21-3)" — the planner reflects the change in `21-01-PLAN.md` before execution.

### Locked-not-discussed (carried verbatim from REQUIREMENTS / Phase 9 / ROADMAP / state-of-codebase)

- **Byte-stability invariant** (Phase 9 D-06): `json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + "\n"`. Phase 21 doesn't change this.
- **Lifespan-safe export** (Phase 9 D-04 + D-05): `os.environ.setdefault('ENVIRONMENT', 'dev')` precedes the `app.main` import; `.openapi()` doesn't enter the `combined_lifespan` (no DB / Redis / Telegram needed). Already in place; no edits.
- **Cwd-independent target path** (Phase 9 D-04 docstring): `target = pathlib.Path(__file__).resolve().parents[1] / "openapi.json"`. Already in place.
- **Codegen tool**: `openapi-typescript@^7.13.0` (pinned in `packages/api-client/package.json`). No version bump in this phase.
- **CI gate location**: `.github/workflows/ci.yml` runs both `git diff --exit-code` checks under the "Backend (drift gates + statics)" and "Frontend (drift gates + statics)" job names. No CI edits.
- **Tracked-file assertion**: CI uses `git ls-files --error-unmatch ...` before the diff so deleting the artifact file (and thus making the diff vacuously empty) trips the gate. Phase 21 inherits this.
- **camelCase wire format** (Phase 4 D-21, `to_camel` alias_generator + `populate_by_name=True`): already encoded in the spec (request/response field names like `pageSize`, `clientId`, `endDate`, `gymHoursStart`). Codegen reflects whatever the spec emits — no special handling. Phase 21 doesn't audit field-name correctness; that's a Phase 22 review concern when consuming the types.
- **Pagination envelope** (`{items, total, page, pageSize}`): already in component schemas (`PaginatedData_<T>_`). No edits.
- **Tags**: `auth | clients | membership-plans | memberships | visits` — set on `include_router(prefix=..., tags=[...])` in `apps/backend/app/api/v1/router.py`. No edits.
- **No `apps/admin-web` consumption** in Phase 21 (Phase 22 territory); the only consumer of the regenerated schema.d.ts inside Phase 21 is the new contract test in the same package.
- **No backend code changes** — Phase 21 is a regeneration + verification phase; `apps/backend/app/**` stays untouched. `import-linter` contracts unaffected. ruff / mypy strict / pytest all stay green because no backend source moved.
- **No frontend (`apps/admin-web/`) code changes** — same reasoning. ESLint / typecheck / vitest stay green.
- **No new ARQ jobs, no new audit events, no new RBAC pairs** — pure typed-transport refresh.
- **No `.env.example` changes** — Phase 21 has zero runtime config surface.
- **No Docker compose changes** — same.
- **No Alembic migration** — same.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project context (read first)
- `.planning/PROJECT.md` — pinned РФ/СНГ stack + camelCase wire format Key Decision (Phase 4) + Pagination envelope Key Decision (Phase 4); the `OpenAPI drift gate end-to-end` mention under v1.1 validated requirements is the precedent Phase 21 re-asserts for v1.2.
- `.planning/REQUIREMENTS.md` §"API Surface — OpenAPI Drift Gate Refresh (Phase 21)" — API-04 + API-05 verbatim; the requirements-status table at file end (rows `API-04 | Phase 21 | Pending` and `API-05 | Phase 21 | Pending`) flips to Complete in this phase.
- `.planning/ROADMAP.md` §"Phase 21: OpenAPI drift gate refresh + api-client codegen" — Goal + Success Criteria 1-3 + dependency note ("Depends on: Phases 16, 17, 19 (and Phase 23 if active-sessions endpoints land there before this gate)").
- `.planning/STATE.md` §"Decisions" — accumulated v1.2 decisions; Phase 21's D-21-* will be appended on phase verification.

### Phase 9 outputs (direct precursor — drift-gate machinery)
- `apps/backend/scripts/export_openapi.py` — Phase 9 D-04..D-06 lifespan-safe + byte-stable export. Phase 21 RUNS this script; does not modify it (default expectation).
- `.github/workflows/ci.yml` "Backend (drift gates + statics)" job, `Drift gate — apps/backend/openapi.json` step — `git ls-files --error-unmatch` then `git diff --exit-code apps/backend/openapi.json`. Phase 21 must keep this green.
- `.github/workflows/ci.yml` "Frontend (drift gates + statics)" job, `Drift gate — packages/api-client/src/schema.d.ts` step — `pnpm --filter @sportzal/api-client codegen` then `git ls-files --error-unmatch` then `git diff --exit-code packages/api-client/src/schema.d.ts`. Phase 21 must keep this green after committing the regeneration.
- `packages/api-client/package.json` — `scripts.codegen = "openapi-typescript ../../apps/backend/openapi.json --output src/schema.d.ts"`; Phase 21 invokes this verbatim. No script edits.
- `packages/api-client/src/fetcher.ts` (Phase 9 D-09) — generic `request<P, M>(...)` wrapper consuming `paths[P][M]`. Reference for understanding why the contract test verifies path keys + per-method shapes, not operationIds. Phase 21 does NOT modify fetcher.ts.
- `packages/api-client/src/fetcher.test.ts` — existing vitest file in the same package; Phase 21's new `schema.contract.test.ts` lives next to it (sibling test file convention).

### Phase 16 / 17 / 19 outputs (the new spec surface Phase 21 freezes)
- `apps/backend/app/api/v1/router.py:include_router(plans_router, prefix="/membership-plans", tags=["membership-plans"])` (Phase 16). Source of `/api/v1/membership-plans` + `/api/v1/membership-plans/{plan_id}` paths.
- `apps/backend/app/api/v1/router.py:include_router(memberships_router, prefix="/memberships", tags=["memberships"])` (Phase 17). Source of `/api/v1/memberships`, `/api/v1/memberships/{membership_id}`, `/api/v1/memberships/{membership_id}/cancel`.
- `apps/backend/app/api/v1/router.py:include_router(visits_router, prefix="/visits", tags=["visits"])` (Phase 19). Source of `/api/v1/visits`, `/api/v1/visits/{visit_id}`.
- `apps/backend/app/modules/memberships/router.py` (entire file) — operation summaries + response_models + status codes that materialise as `summary` / `responses` in the openapi.json. Phase 21 doesn't read these to reproduce them — codegen does — but the planner reads to understand which routes are owner-only (RBAC stays server-side; spec only carries the HTTP-layer truth).
- `apps/backend/app/modules/visits/router.py` (entire file) — same as above for visits routes.
- `apps/backend/openapi.json` — current committed spec. Phase 21 verifies regeneration reproduces this byte-for-byte. (At discuss-phase verification: 0-byte diff against `HEAD` after re-running export_openapi — confirmed.)
- `packages/api-client/src/schema.d.ts` — current committed schema.d.ts. Phase 21 OVERWRITES this with the regenerated version (909-line diff: +896 / −13). The pre-Phase-21 file represents v1.1 surface; the post-Phase-21 file represents v1.2 surface.

### Phase 23 awareness (parallel-eligible — D-21-1 / D-21-2)
- `.planning/ROADMAP.md` §"Phase 23: Hygiene + active sessions backend (parallel-eligible)" — Success Criterion 3 lists the sessions endpoints (`GET /api/v1/auth/sessions`, `POST /api/v1/auth/sessions/{family_id}/revoke`). When Phase 23 ships, it will produce its own openapi.json + schema.d.ts diff via the same drift gate. Phase 21 does NOT pre-empt these endpoints.
- `.planning/REQUIREMENTS.md` §"Hygiene — v1.1 Carryover (Phase 23, parallel-eligible)" — HYG-03 verbatim ("Active sessions backend endpoints (if not already shipped in v1.1) ... `GET /api/v1/auth/sessions`, `POST /api/v1/auth/sessions/{family_id}/revoke`"). Phase 21 D-21-1 explicitly cites this requirement as Phase 23's responsibility.

### Backend codebase — composition (read at plan time only if regeneration drifts)
- `apps/backend/app/main.py` — `create_app()` factory; `export_openapi.py` calls `create_app().openapi()`. No edits in Phase 21.
- `apps/backend/app/api/router.py` + `apps/backend/app/api/v1/router.py` — top-level routing chain. No edits.
- `apps/backend/app/core/schemas.py` (or wherever `BackendSchemaBase` + `ResponseEnvelope` + `PaginatedData` live — Phase 15 INFRA-12) — defines `alias_generator=to_camel` + `populate_by_name=True` + `extra='forbid'`. The codegen reflects whatever Pydantic emits as JSON Schema; Phase 21 trusts the upstream schema base.
- `apps/backend/.importlinter` — three contracts (`core ⊥ modules`, `modules independent`, `integrations ⊥ modules`) plus the D-06 + D-10 worker→modules narrative addenda. Phase 21 does not change this; the regeneration step doesn't import any new module.

### Conventions
- `.planning/codebase/CONVENTIONS.md` — backend conventions including OpenAPI export; Phase 21 follows verbatim.
- `.planning/codebase/STRUCTURE.md` — `packages/api-client` placement and consumer convention (admin-web imports via the @sportzal/api-client workspace alias).
- `.planning/codebase/TESTING.md` — vitest test placement convention (sibling `*.test.ts(x)` next to source); Phase 21's `schema.contract.test.ts` follows this.
- `apps/backend/docs/conventions.md` — backend OpenAPI export procedure; Phase 21 invokes this verbatim.
- `apps/backend/docs/architecture.md` — modular monolith doc; Phase 21 doesn't touch.
- `apps/backend/docs/adr/0001-modular-monolith.md` — ADR for import-linter contracts; Phase 21 doesn't touch.

### Third-party docs (read on demand)
- [openapi-typescript v7](https://openapi-ts.dev/cli) — codegen CLI flags, `paths`/`operations` exported types shape. Phase 21 uses defaults; no flag changes from Phase 9.
- [FastAPI OpenAPI utilities](https://fastapi.tiangolo.com/advanced/extending-openapi/) — operationId derivation rules. Phase 21 references for D-21-3 reasoning (auto-derived IDs).
- [Pydantic v2 — JSON Schema generation](https://docs.pydantic.dev/latest/concepts/json_schema/) — how `alias_generator` + `populate_by_name` + `extra='forbid'` materialise into the spec. Phase 21 reads only if a regeneration produces unexpected schema shape.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`apps/backend/scripts/export_openapi.py`** (Phase 9 D-04..D-06) — lifespan-safe, byte-stable, cwd-independent. Phase 21 invokes verbatim via `uv run python -m scripts.export_openapi` from `apps/backend/`. Verified at discuss-phase time: produces 0-byte diff against committed `apps/backend/openapi.json`.
- **`packages/api-client/package.json:scripts.codegen`** — `openapi-typescript ../../apps/backend/openapi.json --output src/schema.d.ts`. Phase 21 invokes via `pnpm --filter @sportzal/api-client codegen` from repo root. Verified at discuss-phase time: produces +896 / −13 diff in `packages/api-client/src/schema.d.ts` (the actual delivery work).
- **`packages/api-client/vitest.config.ts` + `fetcher.test.ts`** — existing vitest setup; the new `schema.contract.test.ts` slots in next to `fetcher.test.ts` and runs under the existing `pnpm --filter @sportzal/api-client test` command. Zero new tooling.
- **`packages/api-client/src/index.ts`** — barrel export including `paths` / `operations` / `components` types from `schema.d.ts`. The contract test imports from `schema.d.ts` directly (or via `index.ts`) to verify the surface; existing exports stay untouched.
- **`.github/workflows/ci.yml` drift gate jobs** — both gates already wired (Phase 9 D-08). Phase 21 just keeps them green; no workflow edits.
- **`fetcher.ts`'s `request<P, M>(paths[P][M])` typing** — proves the `paths` type-keyed access pattern works end-to-end and is a reference for D-21-4 (the contract test uses the same indexed access).

### Established Patterns

- **Atomic-commit-per-artifact** (v1.2 convention): regenerated `openapi.json` (if dirty) → its own commit; regenerated `schema.d.ts` → its own commit; `schema.contract.test.ts` → its own commit; PROJECT.md/REQUIREMENTS.md doc updates → its own commit. The executor agent already does this; CD-02 codifies it.
- **CI drift gate is the source of truth** — if `git diff --exit-code` after regeneration is empty, the artifact is current. Phase 21's verification in step 4 of plan 21-01 is exactly this assertion.
- **Spec is byte-stable, not just semantically equal** — a key Phase 9 invariant. Phase 21 honors it: the regeneration command is the SAME `python -m scripts.export_openapi`, the SAME `openapi-typescript`, the SAME pin (`openapi-typescript@^7.13.0`). No version bumps in this phase.
- **Tests sibling source** (vitest convention): `schema.contract.test.ts` next to `schema.d.ts`. Already convention in `packages/api-client/` (`fetcher.ts` / `fetcher.test.ts`) and `apps/admin-web/src/`.
- **Phase 9 single-script export, no modular spec composition** — Phase 21 trusts FastAPI's `app.openapi()` to reflect the live `create_app()` route surface. No manual JSON merging, no per-module spec fragments.

### Integration Points

- **`apps/backend/openapi.json`** — RE-RUN `export_openapi.py`; commit if any byte changed. Verified currently 0-byte drift.
- **`packages/api-client/src/schema.d.ts`** — RE-RUN `pnpm codegen`; commit the +896-line diff.
- **`packages/api-client/src/schema.contract.test.ts`** — NEW file (~30-50 LOC). Imports `paths` from `./schema.d.ts` (or `./index.ts`); asserts type-level shape per D-21-4.
- **PROJECT.md `## Key Decisions` table** — APPEND row D-21 (per spec above). Trailing-line update.
- **REQUIREMENTS.md API-04 + API-05 checkbox flips + status-table rows** — `[ ]` → `[x]`; `Pending` → `Complete`. Two `Edit` operations.
- **STATE.md** — `update_state` step at workflow end records "Phase 21 context gathered" and stores resume-file pointer.
- **NO changes to `apps/backend/scripts/export_openapi.py`** (default expectation — Phase 9 D-06 invariants hold).
- **NO changes to `apps/backend/app/**`** — pure regeneration phase.
- **NO changes to `apps/admin-web/**`** — Phase 22 owns FE consumption.
- **NO changes to `.github/workflows/ci.yml`** — gates already in place.
- **NO `.importlinter` changes** — no new module imports.
- **NO Alembic migration** — no DB schema work.
- **NO Docker compose changes** — no new services or env vars.

</code_context>

<specifics>
## Specific Ideas

- **The 909-line diff in `schema.d.ts` is the headline deliverable.** Phase 21 is "do the codegen we deferred until all v1.2 endpoints landed". The mechanical work is small; the discipline is that this is the single moment when downstream typed admin-web consumption becomes possible. Phase 22 starts from here.
- **`apps/backend/openapi.json` being already byte-stable is NOT a sign Phase 21 is empty.** It is a sign that the per-phase CI gate worked: each of Phases 16/17/19 was forced to commit the spec changes alongside its route additions because their CI would have failed otherwise. Phase 21 still owns the ROADMAP success criteria + REQUIREMENTS check-off + the schema.d.ts regeneration + the new contract test.
- **The contract test (`schema.contract.test.ts`) is forward-looking.** It catches regressions in:
  1. A future `openapi-typescript` major-version bump that changes the `paths` type shape.
  2. A future operationId-collision quirk where FastAPI silently merges two routes' operations.
  3. A future accidental `prefix=""` typo in `app/api/v1/router.py:include_router(...)` that drops a path family from the spec without breaking ruff/mypy.
  Each of these scenarios is "happens once every few months in a growing API"; the cost of the test is one file (~30-50 LOC), the value is high.
- **Sessions-conditional logic in the contract test (D-21-2)** matters because Phase 23 is parallel-eligible. If we hardcoded the path list, then Phase 23 (which adds sessions paths) would force a Phase 21 sub-plan. Treating `paths` as a discoverable map keeps both phases independent.
- **Owner sign-off NOT required** for Phase 21 (unlike Phase 20's locked Russian DM strings). No user-visible copy in this phase. Merge gate is purely CI-driven (drift gates green + contract test green + tsc green).

</specifics>

<deferred>
## Deferred Ideas

- **Explicit short operation IDs (`operation_id="listMembershipPlans"`)** — D-21-3 rejected for v1.2; revisit at v1.3+ if a code-gen client (e.g. `client.memberships.list()`-style RPC façade) becomes desirable.
- **Runtime schema validation on the FE side (zod from openapi)** — defense-in-depth; v1.3+ if a contract violation surfaces in production. Phase 21 trusts the Phase 4 D-25 `extra='forbid'` upstream guard.
- **Automatic operation tag taxonomy (e.g. `tags=["v1", "members.plans"]` hierarchical)** — current flat tags work for the small surface; revisit at v1.3+ when the API grows past 6-7 tag families.
- **Cross-package type re-export (e.g. `apps/admin-web/src/shared/api/types.ts` deriving from `paths[...]`)** — Phase 22 territory; not Phase 21's concern.
- **`@redocly/cli` lint or `spectral` rule pack on `openapi.json`** — drift-gate-adjacent quality gate; defer to v1.3+ unless a real breakage motivates it.
- **OpenAPI version bump to 3.1.x** (FastAPI 0.115+ supports 3.1) — current spec is whatever FastAPI's default emits. Bumping may regenerate the entire schema.d.ts; deferred unless a tool demands it.
- **`exa.json` / `OpenAPI examples`** for richer admin-web autocomplete — out of scope; Phase 22 may want this for fixture generation but it's a separate concern.
- **Sessions endpoints inclusion** — Phase 23 owns; surfaced here only because of the parallel-eligibility note. Not deferred per se — Phase 23 will trigger its own drift-gate refresh as part of its own deliverable.
- **`export_openapi.py` enhancements** (e.g. `--check` flag, `--diff` flag, integration with `pre-commit`) — not needed for v1.2; the CI gate is the source of truth.
- **Contract test for `components/schemas` shape stability** (e.g. asserting `components['schemas']['MembershipResponse']['properties']['endDate']['format'] === 'date'`) — over-specification for v1.2; the contract test stays at the path-level surface.

</deferred>

---

*Phase: 21-openapi-drift-gate-refresh-api-client-codegen*
*Context gathered: 2026-05-08*
