# Phase 64: Contract Freeze — OpenAPI Curation - Context

**Gathered:** 2026-05-26
**Status:** Ready for planning
**Mode:** `--auto` (single-pass; all gray areas auto-resolved with recommended defaults)

<domain>
## Phase Boundary

Make `apps/backend/openapi.json` the authoritative, curated single source of truth under the **clubcore** name. Eight deliverables (FRZ-01..08):

1. Stale-rebrand fix in `app/main.py`: `title="clubcore API"`, `version="1.11.0"`, populated `description`, `servers[]` with localhost:8000 dev entry. Byte-stable regen of `openapi.json` + `packages/api-client/src/schema.d.ts`; drift gate green.
2. All 102+ operation IDs cleaned via `generate_unique_id_function` hook in `app/main.py` per **D-11-OPID** (suffix-strip `_api_v1_{method}`); single atomic regen; admin-web `schema.d.ts` callsites adjusted in same PR.
3. Explicit `openapi_tags=[...]` ordering all 10 business domains; every router declares `tags=[...]` explicitly (no auto-derived tags); Redocly preview groups operations under expected headings — no stray "default" folder.
4. Complete `info{}` metadata under clubcore name; `servers[]` populated with ≥1 placeholder entry.
5. `securitySchemes` wired — cookie auth (`cc_access` / `cc_refresh` httpOnly) + CSRF header (`X-CSRF-Token`); `sportzal_csrf` cookie name retained per **D-11-CSRF-DEFER**; routes apply `Security()` where appropriate.
6. Shared `components.responses` for 401/403/404/409/422/429 error envelopes; usage sites reference via `$ref` (no inline duplicates).
7. Redocly CLI lint config (`redocly.yaml` at repo root); `npx @redocly/cli lint openapi.json` exits 0; wired as 7th parallel CI gate in `.github/workflows/ci.yml`.
8. Pre-freeze baseline captured — drift gate clean post-curation; `contract-freeze-v1.11.0` baseline marker committed; `CHANGELOG.md` entry in `packages/api-client/`.

**Scope anchor:** Curation only. NO new business endpoints, NO new ORM entities, NO behaviour changes. Backend-only milestone; `apps/admin-web` is frozen mock-reference except for `schema.d.ts` regen (mechanical drift).

</domain>

<decisions>
## Implementation Decisions

### Plan decomposition (atomic commits)

- **D-64-PLANS:** 7 atomic plans, one per FRZ requirement, executed in this order:
  1. **64-01 — FRZ-01 + FRZ-04** (info{} + servers[] + description; byte-stable regen). Bundled because both touch the same `FastAPI(...)` constructor block in `app/main.py:183-189` and one regen settles both. Single commit.
  2. **64-02 — FRZ-02** (operation_id rename via `generate_unique_id_function` hook). Standalone — large mechanical diff in `schema.d.ts` (102+ keys); easier to review and revert in isolation.
  3. **64-03 — FRZ-03** (explicit `tags=[...]` per router + `openapi_tags` ordering in `app/main.py`). Standalone — multi-router edit.
  4. **64-04 — FRZ-05** (`securitySchemes` + `Security()` per route). Standalone — security-surface change deserves its own diff.
  5. **64-05 — FRZ-06** (shared `components.responses` + `$ref` migration at usage sites). Standalone — largest semantic refactor.
  6. **64-06 — FRZ-07** (`redocly.yaml` + Redocly lint as 7th CI gate). Standalone — CI workflow change.
  7. **64-07 — FRZ-08** (baseline tag + `packages/api-client/CHANGELOG.md` entry). Closure plan.

  **Rationale:** Mirrors Phase 63 atomicity discipline (one requirement per plan). Each plan must keep `openapi.json` + `schema.d.ts` drift-gate-green at HEAD.

### Operation ID rename (FRZ-02)

- **D-64-OPID-HOOK:** Use FastAPI `generate_unique_id_function` per **D-11-OPID** (already locked at milestone open). Strip `_api_v1_{method}` suffix from the default operation IDs.
  - **Why:** suffix-strip preserves the human-readable function name (e.g., `login_api_v1_auth_login_post` → `login`) without requiring 102+ per-route `operation_id=` literals. Less diff, less drift surface.
  - **How to apply:** `def custom_unique_id(route: APIRoute) -> str: return re.sub(r'_api_v1_.*', '', route.name)` (or equivalent — researcher confirms exact regex against current ID corpus). Wire in `FastAPI(generate_unique_id_function=custom_unique_id, ...)`.

- **D-64-OPID-COLLISION:** Researcher MUST verify no collisions after suffix-strip across all 102+ routes (e.g., two `list_*` handlers in different routers). If collisions exist, fall back to a stripped-name + tag prefix (`auth_login`, `clients_list`) for the collision-set only. Document any collision-set in the plan.

- **D-64-OPID-ADMIN-WEB-IMPACT:** Confirmed scout (2026-05-26): `apps/admin-web/src/` has zero direct references to `_api_v1_` suffixed operation IDs — only `packages/api-client/src/schema.d.ts` consumes them. Rename impact = regenerated `schema.d.ts` only. The `_v18Checks`/`_v19Checks` `AssertNonNever` guards in `packages/api-client/src/schema.contract.test.ts` are keyed on `paths['/api/v1/...']` strings, NOT on operation IDs — so they survive the rename unchanged.

### Tag ordering (FRZ-03)

- **D-64-TAG-ORDER:** `openapi_tags` order in `app/main.py` = the 10 domains in the exact order locked by REQUIREMENTS.md (FRZ-03 line 31):
  1. Auth
  2. Clients
  3. Memberships
  4. Visits
  5. Schedule
  6. Bookings
  7. Trainers
  8. Payments
  9. Reports
  10. Audit-log

  **Why:** Matches business-flow narrative (identity → CRM → product → operations → money → analytics). Mirrors how the auth-runbook (Phase 65) will walk operators through the API.
  **How to apply:** Every router file (`app/modules/*/router.py`) declares `APIRouter(..., tags=["{Domain}"])`. Cross-cutting `_internal` endpoints (email-webhook, yookassa-webhook) get tag `Internal` and are listed LAST in `openapi_tags` after the 10 business domains.

- **D-64-TAG-INTERNAL:** `_internal/*` endpoints get tag `"Internal"` (sorted last). Reason: keeps Redocly preview's business-domain navigation clean; internal endpoints are visible but visually segregated.

### Error response envelope (FRZ-06)

- **D-64-RESPONSES-LOCATION:** Define the 6 shared response objects (`401_Unauthorized`, `403_Forbidden`, `404_NotFound`, `409_Conflict`, `422_ValidationError`, `429_RateLimited`) in a new module `app/core/openapi_responses.py`. Each is a `dict` matching the existing exception-handler envelope shape from `app/core/exceptions.py`.

- **D-64-RESPONSES-APPLY:** Apply via per-router `responses=...` kwarg OR via a `customize_openapi_schema()` post-processor that injects `$ref` at usage sites. **Recommended:** post-processor approach (touches the spec JSON in one place, leaves router code untouched). Researcher confirms feasibility vs. FastAPI's `app.openapi_schema` cache hook.
  - **Why:** Per-router `responses=...` requires editing every router (high-touch). A post-processor in `app/main.py` keeps the diff localized.
  - **How to apply:** After `FastAPI.openapi()` builds the schema, walk every operation; for each documented response status in {401, 403, 404, 409, 422, 429}, replace inline schema with `{"$ref": "#/components/responses/{Code}_{Name}"}`. Then set `app.openapi_schema = curated` so subsequent calls return the cached curated version.
  - **Drift risk:** Researcher MUST verify the post-processor produces byte-stable output across `uv run python -m scripts.export_openapi` invocations (no key-order nondeterminism from Python dict iteration).

### Security schemes (FRZ-05)

- **D-64-SEC-SCHEMES:** Define two `securitySchemes` in `components.securitySchemes`:
  - `cookieAuth` — `type: apiKey`, `in: cookie`, `name: cc_access` (refresh cookie `cc_refresh` documented in `description`, not as a separate scheme since refresh-token is server-internal flow).
  - `csrfHeader` — `type: apiKey`, `in: header`, `name: X-CSRF-Token`. Description annotates the `sportzal_csrf` cookie carry-over per **D-11-CSRF-DEFER** with v2.0 cutover plan.

- **D-64-SEC-APPLY:** Apply security globally via `FastAPI(..., openapi_extra={"security": [{"cookieAuth": [], "csrfHeader": []}]})` post-processed, then override per-route to `security: []` for public endpoints (`/healthz`, `/api/v1/auth/login`, `/api/v1/auth/password-reset/request`, `/api/v1/auth/password-reset/confirm`, `/api/v1/auth/otp/request`, `/api/v1/auth/otp/verify`, `/api/v1/auth/telegram/*`, `_internal/*`).
  - **Why:** Most routes are authenticated; global default + per-route opt-out has the smallest diff.
  - **How to apply:** Researcher enumerates the public-endpoint allowlist by grepping for routes without `Depends(get_current_user)` / `Depends(require_permission)`. Allowlist is committed as a frozenset literal in `app/main.py` (mirroring `LOCKED_AUDIT_EVENTS` discipline) so additions are visible in diff.

### Redocly lint (FRZ-07)

- **D-64-REDOCLY-RULESET:** Use Redocly's `recommended` ruleset (NOT `recommended-strict`). Disable case-sensitivity rules on operation IDs only if collisions force underscore-style IDs; otherwise leave defaults.
  - **Why:** `recommended-strict` flags stylistic issues (e.g., missing `examples`) that would balloon scope. `recommended` catches structural problems (broken `$ref`, missing required fields, duplicate operation IDs) — exactly what we need to lock down.
  - **How to apply:** `redocly.yaml` at repo root with `extends: [recommended]` and a `rules:` block ONLY for documented exceptions. Each disabled rule MUST have an inline comment explaining the trade-off.

- **D-64-REDOCLY-CI-PLACEMENT:** Add as a new top-level job `redocly-lint` in `.github/workflows/ci.yml`, parallel to `backend` and `frontend`. Runs `npx -y @redocly/cli@latest lint apps/backend/openapi.json`. Permission-minimal (`contents: read`).
  - **Why:** A new top-level job preserves the existing 2-job structure clean separation; mirroring the drift-gate pattern. Pinning to `@latest` is acceptable for a lint-only CI step (no runtime risk), but researcher MUST confirm whether to pin to an exact version for byte-stable CI reproducibility.

### Baseline tag + CHANGELOG (FRZ-08)

- **D-64-BASELINE-TAG:** Annotated git tag `contract-freeze-v1.11.0` on the merge commit of the final plan (64-07). NOT a lightweight tag — annotated so it has a commit message describing the freeze contract.
  - **Why:** Annotated tags ship release notes inline; downstream agents (Phase 65 Postman generator, Phase 66 idempotency wiring) can `git show contract-freeze-v1.11.0` to read the freeze charter.
  - **How to apply:** Tag is created in a final closure commit by the executor after all 7 plans land and drift gate is green. Tag message references this CONTEXT.md and the 8 FRZ-* requirements.

- **D-64-CHANGELOG-NEW:** Create `packages/api-client/CHANGELOG.md` (does not exist yet). Format: Keep-a-Changelog v1.1. First entry: `## [Unreleased] - 2026-05-26 — v1.11.0 Contract Freeze` with bullet list of the 8 FRZ-* deliverables.
  - **Why:** Phase 65 Postman/Newman handoff package and v2.0 frontend integration both need a human-readable freeze charter. CHANGELOG.md is the conventional location.

### Path discrepancy resolution

- **D-64-PATH-FIX:** REQUIREMENTS.md line 35 / FRZ-08 references `apps/admin-web/packages/api-client/openapi.json apps/admin-web/packages/api-client/src/generated/schema.d.ts` — these paths are **stale**. Actual locations confirmed 2026-05-26:
  - `apps/backend/openapi.json` (exported by `scripts/export_openapi.py`)
  - `packages/api-client/src/schema.d.ts` (regenerated by `pnpm --filter @clubcore/api-client codegen` from the backend-exported spec)
  - There is NO `apps/admin-web/packages/api-client/` directory; api-client is a workspace package at repo-root `packages/api-client/`.

  **How to apply:** Plan 64-07 closure commit also amends `.planning/REQUIREMENTS.md` FRZ-08 to use the correct paths. Drift gate command becomes `git diff --exit-code apps/backend/openapi.json packages/api-client/src/schema.d.ts`. The existing CI workflow already drift-gates `apps/backend/openapi.json` only — adding a second drift check on `packages/api-client/src/schema.d.ts` is in-scope for plan 64-07 (one-line addition to the existing drift step).

### Byte-stability discipline

- **D-64-BYTE-STABLE:** Every plan MUST leave `openapi.json` + `schema.d.ts` byte-stable at HEAD. Drift-gate green is a per-plan acceptance criterion, NOT a phase-close criterion only. This is the same discipline as Phase 63 (each plan = green CI tree).
  - **Why:** If plan N introduces drift, plan N+1 inherits a poisoned tree and can't isolate its own changes.
  - **How to apply:** Each plan's last task is `uv run python -m scripts.export_openapi && pnpm --filter @clubcore/api-client codegen && git diff --exit-code apps/backend/openapi.json packages/api-client/src/schema.d.ts`. If diff is non-zero, the regen output is committed AS PART OF the same plan (single atomic commit).

### Out-of-scope guardrails

- **D-64-NO-OPENAPI-EXTRA-INFO:** `info.contact` and `info.license` — explicitly omit with reason. Personal commercial project; no public publish path (D-11-DOCS-PRIVATE). Document the omission in the plan, not as TODO comments.
- **D-64-NO-EXAMPLES:** Do NOT add `examples` blocks to every operation in this phase. Phase 65 (Postman handoff) is where example payloads land — keeping Phase 64 to spec-structure curation only.
- **D-64-NO-SERVER-LIST-EXPANSION:** `servers[]` ships exactly one entry: `{url: "http://localhost:8000", description: "Local dev"}`. Production / staging URLs deferred to v2.0 launch milestone (no production deploy story yet).

### Claude's Discretion

- Exact regex for the `generate_unique_id_function` hook — researcher finalizes against the live operation-ID corpus.
- Exact post-processor implementation for `components.responses` / `securitySchemes` — researcher picks between (a) override `app.openapi_schema` directly or (b) override `app.openapi` method. Either works; researcher picks whichever produces byte-stable output across cold/warm calls.
- Order of public-endpoint allowlist entries in `app/main.py` (cosmetic).
- Whether `redocly.yaml` lives at repo root or under `apps/backend/` (root recommended — repo-wide tool config convention; researcher may push back if Redocly CLI has strong opinions about cwd).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 64 scope authority
- `.planning/ROADMAP.md` §"Phase 64: Contract Freeze — OpenAPI Curation" — phase goal + 5 success criteria + dependency on Phase 63
- `.planning/REQUIREMENTS.md` §"Contract Freeze — OpenAPI Curation (Phase 64 — FRZ-*)" lines 25-36 — 8 FRZ-* requirements (authoritative; FRZ-08 paths stale — see D-64-PATH-FIX)
- `.planning/PROJECT.md` §"Current Milestone: v1.11 API Handoff + Production Hardening" — milestone goal and constraints

### v1.11 milestone decisions (locked at milestone open 2026-05-26)
- `.planning/STATE.md` §"Key v1.11 Decisions" — D-11-OPID (suffix-strip via hook, not explicit per-route), D-11-CSRF-DEFER (`sportzal_csrf` cookie retained in v1.11), D-11-DOCS-PRIVATE (no public publish path)

### Code anchors (read before planning)
- `apps/backend/app/main.py:183-189` — `FastAPI(...)` constructor with stale `title="Sportzal API"` + `version="1.1.0"` (FRZ-01 target)
- `apps/backend/app/main.py:155-280` — `create_app()` composition root (where `generate_unique_id_function` + `openapi_tags` + post-processor wire in)
- `apps/backend/scripts/export_openapi.py` — byte-stable spec exporter (drift-gate input)
- `apps/backend/app/core/exceptions.py` — error envelope shape (source of truth for `components.responses` payloads)
- `apps/backend/openapi.json` — current uncurated spec (5479+ lines; baseline before curation)
- `packages/api-client/package.json` §"codegen" script — `openapi-typescript ../../apps/backend/openapi.json --output src/schema.d.ts` (path confirms D-64-PATH-FIX)
- `packages/api-client/src/schema.d.ts` — generated TypeScript bindings (regen target)
- `packages/api-client/src/schema.contract.test.ts` — `AssertNonNever` guards keyed on `paths[...]` (NOT operation IDs — survives FRZ-02 rename)
- `.github/workflows/ci.yml` — existing 6 CI gates (FRZ-07 adds 7th)

### Drift-gate discipline (v1.7/v1.8/v1.9 precedent)
- Search the v1.9 milestone summary for the `byte-stable regen` pattern — same `openapi.json` + `schema.d.ts` byte-stability discipline applies here, with one new dimension: `redocly lint` must exit 0 after every plan that touches the spec.

### Tooling
- Redocly CLI docs (researcher fetches at plan time): https://redocly.com/docs/cli/configuration
- FastAPI `generate_unique_id_function` docs: https://fastapi.tiangolo.com/advanced/path-operation-advanced-configuration/#using-the-path-operation-function-name-as-the-operationid (researcher confirms against installed FastAPI 0.115+ version)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`scripts/export_openapi.py`** — already produces byte-stable JSON (Phase 4+ discipline). Plan 64-01 reuses unchanged.
- **`app/core/exceptions.py`** error-envelope shape — directly reusable as the schema of the 6 `components.responses` objects. No new Pydantic model needed.
- **`LOCKED_AUDIT_EVENTS` frozenset pattern** (`app/core/audit.py`) — the lock+AST-gate idiom is the model for the public-endpoint allowlist frozenset in D-64-SEC-APPLY.
- **Existing CI drift-gate step** (`.github/workflows/ci.yml:50-62`) — extend its `git diff --exit-code` to cover `packages/api-client/src/schema.d.ts` (one-line addition in plan 64-07).

### Established Patterns
- **Atomic commits per requirement** (Phase 63 precedent — D-63-01): 7 plans = 7 commits. No bundling unless requirements share the same constructor block (only FRZ-01+04 qualify).
- **Composition root in `app/main.py`** — the only place that wires cross-module concerns. Hook registration (`generate_unique_id_function`, `openapi_tags`, post-processor) belongs here. importlinter contract scopes `app.core`, so `app/main.py` is exempt.
- **Frozenset-as-lock with AST gate** — applies to the public-endpoint allowlist (D-64-SEC-APPLY). Researcher confirms whether an AST gate is needed in this phase or deferred (likely deferred — security-allowlist drift is caught by the Redocly lint + drift gate combo).
- **`# v1.X carry-over` annotations** — `sportzal_csrf` description (D-64-SEC-SCHEMES) follows D-11-CSRF-DEFER carry-over pattern from v1.10 close.

### Integration Points
- **`FastAPI(...)` constructor** at `app/main.py:183-189` — single edit point for `title`/`version`/`description`/`servers`/`openapi_tags`/`generate_unique_id_function`.
- **`app.openapi_schema = curated_spec`** — post-processor hook for `components.responses` `$ref` migration + `securitySchemes` injection. Must be set inside `create_app()` AFTER all routers are included.
- **Every `APIRouter(...)` constructor** in `app/modules/*/router.py` — touched by FRZ-03 (explicit `tags=[...]`). Researcher enumerates the exact router files.
- **`.github/workflows/ci.yml`** — touched by FRZ-07 (new top-level `redocly-lint` job) and FRZ-08 (one-line drift-gate extension).

</code_context>

<specifics>
## Specific Ideas

- **Operation IDs after rename should be human-readable in Postman.** Phase 65 will `folderStrategy=Tags` group requests under the 10 domains, but the request *name* inside each folder will be the operation ID. So `login` reads better than `auth_login` — keep stripped name unless collisions force prefixing.
- **`info.description`** content: short statement that this is the v1.11.0 contract-freeze baseline, references the auth runbook (Phase 65 will write `.planning/handoff/clubcore-auth-runbook.md`), notes the spec is curated for handoff (not auto-generated boilerplate). No marketing text — engineering-targeted.
- **`servers[].description`** value: `"Local dev"` — short, unambiguous. Future entries will add `"Staging"` / `"Production"` in v2.0.

</specifics>

<deferred>
## Deferred Ideas

- **Per-operation `examples` payloads** → Phase 65 (Postman handoff) — example bodies live in the Postman collection, not in the spec.
- **Production / staging `servers[]` entries** → v2.0 launch milestone — no production deploy story yet (PROJECT.md "Out of scope" line 111).
- **`sportzal_csrf` → `clubcore_csrf` cookie rename** → v2.0 (D-11-CSRF-DEFER; documented in spec description as known carry-over).
- **`info.contact` / `info.license`** → permanently omitted (personal commercial project; D-11-DOCS-PRIVATE — no public publish).
- **AST-gating the public-endpoint allowlist frozenset** → consider in Phase 66 (idempotency) if a similar allowlist emerges; not in Phase 64 scope unless researcher flags it as cheap.
- **`components.parameters.IdempotencyKey`** → Phase 66 (IDM-04). Phase 64 does NOT add this — Phase 66 is responsible.
- **Public Redocly doc-site publish path** → never (D-11-DOCS-PRIVATE locked; Phase 65 ships a private gitignored doc-site only).

</deferred>

---

*Phase: 64-contract-freeze-openapi-curation*
*Context gathered: 2026-05-26*
*Discussion mode: `--auto` (recommended defaults; user can override before plan-phase)*
