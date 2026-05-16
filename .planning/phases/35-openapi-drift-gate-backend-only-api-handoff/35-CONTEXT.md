# Phase 35: OpenAPI Drift Gate (backend-only API handoff) — Context

**Gathered:** 2026-05-16
**Status:** Ready for planning
**Mode:** `/gsd-discuss-phase 35 --auto` — single pass; recommended defaults selected for every gray area; full audit trail in `35-DISCUSSION-LOG.md`.

<domain>
## Phase Boundary

Phase 35 regenerates the byte-stable API contract artifacts to expose every v1.4 typed path that landed in Phases 31–34, so that the external design team (now owning production admin + client apps per the 2026-05-15 pivot) can consume the contract independently of this repository. This is a **handoff phase**, not a UI phase.

Mechanically Phase 35 delivers:

- **Atomic regeneration of `apps/backend/openapi.json`** via `uv run python -m scripts.export_openapi` (byte-stable: `indent=2, sort_keys=True, ensure_ascii=False, trailing newline` — D-21 contract). Single commit; mirrors v1.2 Phase 21 + v1.3 Phase 28 pattern.
- **Atomic regeneration of `packages/api-client/src/schema.d.ts`** via `pnpm --filter @sportzal/api-client codegen` (`openapi-typescript ^7.13.0` against the regenerated `openapi.json`). Same commit as the json — drift-gate works against a single delta.
- **Forward-guard extension of `packages/api-client/src/schema.contract.test.ts`** — pin every new v1.4 typed path + method as compile-time `AssertNonNever<paths['/api/v1/...']['post'|'get'|'patch'|'delete']>` entries. Method-level granularity (one entry per path-method pair, not just per path) matches the existing Phase 21 D-21-4 pattern.
- **`packages/api-client/README.md` changelog** — concise v1.4 path inventory grouped by module (trainers, payments, pt-package-plans, pt-packages, pt-sessions, membership refund, pt-package refund) + auth setup pointer (Argon2id login → JWT access + refresh-rotation family + CSRF on mutating methods); points to existing fetcher single-flight refresh doc instead of duplicating.
- **CI verification path** — both drift-gate steps (`git diff --exit-code apps/backend/openapi.json` and `git diff --exit-code packages/api-client/src/schema.d.ts`) green; `pnpm --filter @sportzal/api-client typecheck` and `vitest run` green (forward-guard compiles); admin-web 233 vitest specs continue to pass unchanged as canary.

**1 requirement in scope:** FE-10 (sole v1.4 requirement in this phase; FE-11..18 descoped to v2.0 Frontend Integration per 2026-05-15 pivot).

**Out of scope (deferred / handled elsewhere):**
- Any admin-web route, mutation, shared component, or i18n string change — `apps/admin-web` is **frozen-as-of-v1.3** mock-mode reference; production frontends ship in v2.0 from external design team.
- Adding explicit `operation_id=` decorators to FastAPI routers for naming hygiene — auto-generated operationIds are accepted as-is for v1.4 (Phase 21/28 precedent); revisit only if collisions appear.
- Postman collection authored by hand — that's part of v1.5 API Handoff milestone, not v1.4. Phase 35 only ships the OpenAPI spec + TypeScript types + README; v1.5 will build the Postman/curl examples on top.
- Operator API-contract scenarios via curl/Postman + 4-gate evidence + race tests — **Phase 36** milestone verification.
- Cleanup of stale `Phase 35 UI` / `FE-13 in Phase 35` doc-strings in `apps/backend/app/modules/memberships/router.py` and `apps/backend/app/modules/payments/router.py` — comments only, not contracts; doc-debt deferred (noted under Deferred Ideas).
- API versioning bump (`@sportzal/api-client` package.json `0.0.0` → `0.1.0`) — version field intentionally inert in private workspace package; revisit at v1.5 publish step.

</domain>

<decisions>
## Implementation Decisions

### Regen mechanics & atomicity

- **D-35-01:** **Single-commit atomic regen** of `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts`. The export script (`apps/backend/scripts/export_openapi.py`) runs first; then `pnpm --filter @sportzal/api-client codegen` consumes the new json. Both deltas land in ONE git commit so the drift-gate sees a coherent contract. Mirrors v1.2 D-21-1 and v1.3 Phase 28 pattern exactly. No staging-then-rebasing trickery.
- **D-35-02:** **No manual edits** to either artifact. `schema.d.ts` is fully overwritten by codegen; `openapi.json` is fully overwritten by `export_openapi.py`. If the diff looks wrong (e.g., unexpected new path, missing path, schema reshape), the fix is in the **router/schema source**, not the artifact. Re-run the script after the source fix.
- **D-35-03:** **Byte-stable canonical form is non-negotiable.** `export_openapi.py` already enforces `indent=2, sort_keys=True, ensure_ascii=False` + trailing newline (verified in script header). Codegen output stability is implicit to `openapi-typescript ^7.13.0` (pinned via lockfile). If either tool drifts in a non-content-meaningful way (whitespace, key order) the plan must catch it before commit, not after.
- **D-35-04:** **Drift-gate is the CI gate of record.** Plan must include a local pre-commit verification step that runs `git diff --exit-code apps/backend/openapi.json packages/api-client/src/schema.d.ts` AFTER the regen commit lands — a green local run is the entry criterion to push.

### Forward-guard extension scope

- **D-35-05:** **Pin every new v1.4 typed path + method explicitly** in `schema.contract.test.ts` using the existing `AssertNonNever<paths['...']['...']>` pattern. Inventory derived from the seven new path groups exposed by Phases 31–34:
  - `/api/v1/trainers` (GET, POST), `/api/v1/trainers/{trainer_id}` (GET, PATCH, DELETE) — Phase 31
  - `/api/v1/payments` (GET — listing — only; no POST in v1.4 since sale is via `/memberships` + `/pt-packages`), `/api/v1/payments/by-client/{client_id}` (GET), `/api/v1/payments/by-membership/{membership_id}` (GET) — Phase 32
  - `/api/v1/memberships/{membership_id}/refund` (POST) — Phase 32
  - `/api/v1/pt-package-plans` (GET, POST), `/api/v1/pt-package-plans/{plan_id}` (GET, PATCH, DELETE) — Phase 33
  - `/api/v1/pt-packages` (POST, GET), `/api/v1/pt-packages/{pt_package_id}` (GET), `/api/v1/pt-packages/{pt_package_id}/cancel` (POST), `/api/v1/pt-packages/{pt_package_id}/refund` (POST) — Phase 33
  - `/api/v1/pt-sessions` (POST, GET), `/api/v1/pt-sessions/{pt_session_id}/cancel` (POST), `/api/v1/pt-packages/{pt_package_id}/sessions` (GET) — Phase 34
  (Planner MUST re-derive this inventory from the actual regenerated `openapi.json` — any path here that doesn't appear in the regen is a sign of misrouting in `app/api/v1/router.py`, not a contract test bug.)
- **D-35-06:** **Method-level pinning, not just path existence.** Each path/method pair gets its own `AssertNonNever` line — POST and GET on the same path are pinned separately. Matches existing v1.2 surface block in `schema.contract.test.ts:25-45`.
- **D-35-07:** **Do NOT pin operationIds.** FastAPI auto-generates operationIds from function names (`refund_membership_api_v1_memberships__membership_id__refund_post`-style); pinning them would freeze a brittle naming surface the team has not curated. The forward-guard checks **paths + methods + request body realisation + response 2xx realisation** — that's contract enough. Operation-id discipline is a v1.5 hygiene topic if it surfaces at all.
- **D-35-08:** **Request body realisation guard.** Where a POST takes a non-empty body (every v1.4 sale/refund/cancel endpoint), add a `_BodyIsRealised` assertion (mirrors `_MembershipsPostBody` precedent at line 37) so that an openapi-typescript regression turning the body into `never` fails CI. Required at minimum for the refund + PT-session cancel endpoints (most regression-prone shape).
- **D-35-09:** **Response 200/201 reachability guard.** At least one assertion per new module that the success-response is non-`never` (mirrors `_VisitsListOkRealised` precedent at line 41). Reduces volume; do NOT enforce per-endpoint.

### README changelog format

- **D-35-10:** **Concise, source-of-truth-pointing changelog.** `packages/api-client/README.md` gets a new `## v1.4 changelog` section enumerating the seven new path groups (one bullet per group, not per endpoint) plus a one-line note pointing readers to `apps/backend/openapi.json` for the full surface. Do NOT duplicate path/method tables — they rot.
- **D-35-11:** **Auth setup pointer, not auth tutorial.** Add a `## Auth quick-start` section that points to:
  - existing `## CSRF` and `## Single-flight refresh` sections (already in README) — they cover the runtime contract;
  - server-side `POST /api/v1/auth/login` request shape (Argon2id verifies; sets `sportzal_session` + `sportzal_csrf` cookies + returns access JWT in body);
  - `POST /api/v1/auth/refresh` for rotation family;
  - Telegram OTP flow `(start → status → verify)` for the client-app path.
  Do NOT inline curl examples — the design team will get those in v1.5 Postman collection. One paragraph + path pointers max.
- **D-35-12:** **No changelog entry for trainers/payments/pt_packages/pt_sessions module READMEs.** README.md scope stays at `packages/api-client/` only — backend module-level READMEs are not part of the contract handoff and would create rot surface.

### admin-web canary handling

- **D-35-13:** **admin-web 233 vitest specs are a hard canary** — they MUST continue passing unchanged after regen. The pivot froze admin-web as mock-mode reference, but `schema.d.ts` is shared so a breaking schema change would break the existing wired routes (memberships, plans, visits, clients, auth). If any test breaks: STOP and investigate — it indicates a backwards-incompatible schema change in Phases 31–34 that needs a fix in the backend, NOT in admin-web.
- **D-35-14:** **Zero source edits inside `apps/admin-web/`.** Phase 35 plans MUST NOT touch any file under `apps/admin-web/src/`. Plan files that propose such edits should be rejected at gsd-plan-checker time.
- **D-35-15:** **CI continues to run admin-web typecheck+lint+test** as a blocking gate (NOT downgraded to canary-only at this phase — that downgrade is a v2.0 concern when the production frontend ships externally).

### Plan structure

- **D-35-16:** **Two plans, wave-1 (regen) + wave-2 (contract test + README), with wave-2 depending on wave-1.** Rationale: regen is mechanical and atomic (single commit, two files); contract test + README extension are deterministic from the regenerated artifacts and small enough to bundle. Splitting regen from forward-guard keeps the diff stories clean and lets the executor verify drift-gate green after wave-1 before extending the guard. Mirrors the 2-plan shape of v1.2 Phase 21 (regen + drift-gate setup were separated similarly), scaled down from Phase 28's 8 plans (which were UI-heavy).
- **D-35-17:** **No separate plan for admin-web canary verification.** Wave-2 plan owns it as an exit criterion (run `pnpm --filter @sportzal/admin-web test` locally before commit; CI re-runs it). Adding a third plan for "just run tests" creates ceremony without value.

### Verification & rollback posture

- **D-35-18:** **Local verification before commit (every wave):** plan must spell out the exact command sequence:
  1. `cd apps/backend && uv run python -m scripts.export_openapi`
  2. `pnpm --filter @sportzal/api-client codegen`
  3. `pnpm --filter @sportzal/api-client typecheck`
  4. `pnpm --filter @sportzal/api-client test`
  5. `pnpm --filter @sportzal/admin-web typecheck && pnpm --filter @sportzal/admin-web lint && pnpm --filter @sportzal/admin-web test`
  6. `git diff --exit-code apps/backend/openapi.json packages/api-client/src/schema.d.ts` AFTER staging
- **D-35-19:** **Rollback posture:** if regen surfaces a schema regression (e.g., reception-only field appearing in owner-only response), DO NOT mutate the artifact — fix the backend `schemas.py` / response_model wiring, then re-regen. Plan calls this out so the executor doesn't try to handcraft the json.

### Claude's Discretion

- **Order of method assertions inside `schema.contract.test.ts`** — group by module (trainers / payments / refund / pt-package-plans / pt-packages / pt-sessions) in roadmap-phase order (31 → 34) rather than alphabetical. Reading order matters less than module cohesion.
- **Comment style for the new contract-test block** — use a per-module section header comment + a one-line phase reference (e.g., `// --- v1.4 trainers (Phase 31) ---`) so future archaeologists trace which phase added what. Matches the existing `// --- v1.2 surface (must always be present after Phase 21) ---` header style at line 23.
- **README changelog markdown style** — H2 `## v1.4 changelog` + bullet list, no nested tables. Plain text Russian/English mix matches existing README voice.

### Folded Todos
[None — `cross_reference_todos` returned no matches for Phase 35.]

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 35 anchor docs

- `.planning/ROADMAP.md` § "Phase 35: OpenAPI Drift Gate (backend-only API handoff)" — phase goal + 4 success criteria + dependency chain (Phases 31–34).
- `.planning/REQUIREMENTS.md` § "FE — Descoped to v2.0 Frontend Integration milestone (pivot 2026-05-15)" + FE-10 entry — sole in-scope requirement; scope reduction rationale.
- `.planning/PROJECT.md` § "Current Milestone: v1.4 Cash Sales + PT Packages" + § "Long-term MVP roadmap (post-v1.4)" — v1.5 API Handoff milestone is the consumer of this phase's artifact; v1.4 ships backend-complete + contract.
- `.planning/STATE.md` § "v1.4 Milestone Plan" — confirms Phase 35 is `Not started`, FE-11..18 deferred.

### Precedent phases (READ for pattern fidelity — Phase 35 is the third iteration of this drift-gate pattern)

- `.planning/milestones/v1.3-ROADMAP.md` § "Phase 28: OpenAPI Drift-Gate Refresh + admin-web Wiring" — full 8-plan precedent; Phase 35 inherits regen pattern but drops the 6 admin-web wiring plans.
- `apps/backend/scripts/export_openapi.py` (lines 1–30 docstring) — D-04 ENVIRONMENT setdefault discipline; byte-stable JSON contract; lifespan-safe (no Postgres/Redis touch). **Phase 35 plans MUST NOT modify this script** — it is the canonical exporter.
- `.github/workflows/ci.yml` § "Drift gate — apps/backend/openapi.json" (with WR-06 `git ls-files --error-unmatch` guard) + § "Drift gate — packages/api-client/src/schema.d.ts" — both gates are the contract Phase 35 must satisfy.

### Code surface to extend (and surface NOT to touch)

- `packages/api-client/src/schema.contract.test.ts` (lines 1–90) — full file template for the forward-guard. New v1.4 path/method assertions land BELOW the existing v1.2 + Phase 23 blocks; do not reshape the helpers (`AssertNonNever`, `HasPath`) or the trailing vitest `describe(...)` block — they are part of the test-counting contract.
- `packages/api-client/README.md` (current 57 lines) — README.md target; v1.4 changelog section inserts after § "Codegen", before § "Single-flight refresh". Do not edit existing sections; append only.
- `packages/api-client/package.json` § "scripts.codegen" — `openapi-typescript ../../apps/backend/openapi.json --output src/schema.d.ts`. **Pinned tool version `openapi-typescript: "^7.13.0"`** in devDependencies — do NOT bump in Phase 35 (would cause non-trivial schema diff).
- `apps/backend/app/api/v1/router.py` (lines 35–53) — single source of truth for v1.4 route mounting. Every path in the forward-guard derives from a line in this file. Plans MUST cross-reference this file when enumerating paths.

### Frozen surfaces (DO NOT MODIFY in Phase 35)

- `apps/admin-web/src/**` — entire admin-web tree is frozen-as-of-v1.3. Zero edits. Any plan proposing changes here = scope creep / pivot violation.
- `apps/backend/app/modules/**` — backend modules are LANDED (Phases 31–34). Phase 35 plans MUST NOT modify router signatures, schemas, or service code. If regen reveals a problem, that's a Phase 31/32/33/34 follow-up, not a Phase 35 fix.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`apps/backend/scripts/export_openapi.py`** — lifespan-safe, byte-stable canonical exporter. Runs in clean shell without DB/Redis. Already passes CI on v1.3 artifacts; Phase 35 just re-invokes it.
- **`packages/api-client/src/schema.contract.test.ts`** — existing forward-guard scaffold has helpers (`AssertNonNever`, `HasPath`) and a vitest `describe(...)` shell. New v1.4 assertions plug into the existing skeleton with zero structural change.
- **`packages/api-client/src/schema.d.ts`** (committed) — current file already shows the pattern `openapi-typescript` produces; reading the existing file gives the planner accurate type-shape expectations for the v1.4 additions.
- **`.github/workflows/ci.yml`** drift-gate jobs — already wired with the `git ls-files --error-unmatch` defensive guard (WR-06). Phase 35 inherits CI verification without any workflow edit.
- **`packages/api-client/README.md`** existing sections § "Codegen" / § "Single-flight refresh" / § "CSRF" — auth-quickstart pointer can reference these instead of duplicating.

### Established Patterns

- **Atomic regen + drift-gate** (v1.2 Phase 21 → v1.3 Phase 28 → v1.4 Phase 35) — same export script + same codegen command + same single-commit shape. Three iterations confirm the pattern is stable. Phase 35 is a direct replay minus the UI wiring.
- **Path-only contract pinning** (`schema.contract.test.ts` lines 25–45) — `AssertNonNever<paths['/api/v1/...']['method']>` per-endpoint, plus body-realisation + 200-reachability spot-checks. Do not invent a new test style.
- **Conditional probes (`HasPath`)** (lines 21, 62–68) — used in Phase 21 for paths that would land in later phases. Phase 35 has NO forward-looking paths (all v1.4 endpoints are landed), so every assertion is a hard `AssertNonNever`, NOT a conditional probe.
- **No `operation_id=` decorators in backend routers** — established absence; v1.4 keeps it. Don't introduce them in Phase 35.

### Integration Points

- **CI gate consumes regen artifacts via `git diff --exit-code`** — Phase 35's only runtime integration is the GitHub Actions runner re-running both gates on push. Local verification mirrors CI exactly (same commands).
- **External design team consumes `openapi.json` + (optionally) `schema.d.ts`** — `openapi.json` is the canonical contract; `schema.d.ts` is a convenience for TypeScript consumers. README points design-team readers to both.
- **Admin-web is the canary consumer of `schema.d.ts`** — 233 vitest specs catch breakage. Phase 35 relies on this; no new consumer instrumentation needed.

</code_context>

<specifics>
## Specific Ideas

- **"Backend-only handoff" framing is the through-line.** Every plan, every doc-string, every comment in the new contract-test block should reference this — so that a future reader (or onboarding AI agent) understands why Phase 35 looks so much smaller than Phase 28. The pivot date (2026-05-15) and FE-11..18 → v2.0 deferral are the historical anchor.
- **The "v1.4 surface block" comment header in `schema.contract.test.ts`** should explicitly call out the absent operation_id discipline: `// v1.4 surface (Phases 31-34): operationIds intentionally not pinned — see CONTEXT D-35-07.` Future ergonomic changes (e.g., naming convention adoption) trace cleanly back to this CONTEXT.
- **README "v1.4 changelog" should NOT include the membership freeze/renew/unfreeze paths** (already in v1.3 surface block). Only the new v1.4 additions. Avoid double-listing.

</specifics>

<deferred>
## Deferred Ideas

- **Postman / curl integration collection authored by hand** — belongs in v1.5 API Handoff milestone, not Phase 35. The OpenAPI artifact already supports auto-generation via Postman's import; v1.5 will curate auth/sample-flow examples on top.
- **Doc-string cleanup: stale "Phase 35 UI" / "FE-13 in Phase 35" references** in `apps/backend/app/modules/memberships/router.py` (around the `refund_membership` docstring) and `apps/backend/app/modules/payments/router.py` (`# the client detail page (Phase 35 UI)`). These are doc-debt from before the 2026-05-15 pivot; comments only, not contracts. Capture as v1.4 tech-debt for v1.5 cleanup wave (Phase 35 will not touch backend module source).
- **`@sportzal/api-client` package.json version bump** (`0.0.0` → `0.1.0`) — semver discipline. Private workspace package, no public registry; defer to v1.5 publish prep.
- **Auto-publishing `openapi.json` to a versioned URL** (e.g., GitHub Pages or S3 mirror so the design team can pull a canonical URL) — v1.5 concern. Phase 35 only commits the artifact in-repo.
- **`schema.d.ts` regen via `predev` hook in `apps/admin-web/package.json`** — already exists per README line 41. No change needed; just confirming the existing hook keeps working post-regen.
- **OpenAPI tag curation** (e.g., consistent capitalization, descriptions per tag) — surfaced by `tags=["payments"]` etc. in `app/api/v1/router.py`. Not a contract issue; v1.5 hygiene if surfaced.
- **operationId hygiene (explicit `operation_id=` decorators)** — once the design team gives feedback on the generated TS client method names, decide whether to curate (one-line per route in v1.5+) or accept FastAPI defaults.
- **Reviewed Todos (not folded):** None.

</deferred>

---

*Phase: 35-OpenAPI-Drift-Gate-(backend-only-API-handoff)*
*Context gathered: 2026-05-16*
