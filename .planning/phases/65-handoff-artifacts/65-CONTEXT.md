# Phase 65: Handoff Artifacts - Context

**Gathered:** 2026-05-29
**Status:** Ready for planning
**Mode:** `--auto` (single-pass; all gray areas auto-resolved with recommended defaults — user may override before plan-phase)

<domain>
## Phase Boundary

Deliver a complete, usable v2.0-frontend-integration **handoff package** generated from the post-Phase-66 frozen `apps/backend/openapi.json`. Six deliverables (HND-01..06):

1. **HND-01** — Postman v2.1 collection generated via `openapi-to-postmanv2@6.0.1` from the frozen spec, at `.planning/handoff/v1.11-clubcore.postman_collection.json`; grouped under the 10 FRZ-03 domain folders (`folderStrategy=Tags`); environment file `.planning/handoff/v1.11-clubcore.postman_environment.json` ships placeholder values only (`{{baseUrl}}` / `{{accessToken}}` / `{{csrfToken}}`).
2. **HND-02** — Pre-request/auth scripts: login extracts `Set-Cookie` (`cc_access`, `cc_refresh`, `sportzal_csrf`) into collection variables; mutating requests auto-send `X-CSRF-Token` from the stored value; CSRF retrieval documented inline in the collection description.
3. **HND-03** — Test assertions: every request ≥ `pm.response.to.have.status(...)`; auth happy-path + 1 representative request per business domain additionally asserts response body shape via `pm.test()`. Not a hollow shell.
4. **HND-04** — Newman smoke harness at `tools/newman/`; `pnpm newman run` runs the collection against `docker compose up` with `--bail` (non-zero on any failure); documented as "local handoff smoke — not a CI gate" (D-11-NEWMAN-LOCAL).
5. **HND-05** — `clubcore-auth-runbook.md` at `.planning/handoff/clubcore-auth-runbook.md`; extends the v1.4 runbook precedent under the clubcore name; covers email/password + Telegram OTP + email OTP + refresh-rotation + CSRF retrieval; curl paired with Postman request IDs; `sportzal_csrf` carry-over + v2.0 cutover; Phase 66 `Idempotency-Key` semantics + 24h replay window.
6. **HND-06** — Private OpenAPI doc-site via `@redocly/cli@2.31.4`; `pnpm docs` (or `make docs`) runs `npx @redocly/cli preview-docs openapi.json` on port 8080; `.docs-site/` gitignored; private artifact, never published (D-11-DOCS-PRIVATE) — no PDF, no published search index.

**Scope anchor:** Packaging + documentation of the EXISTING frozen API surface. NO backend code changes, NO new endpoints, NO spec edits (the spec is frozen at Phase 66 HEAD). `apps/admin-web` is untouched. All artifacts derive from the post-Phase-66 `openapi.json`. Adds repo-root tooling scaffolding (`package.json`, `tools/newman/`, `pnpm docs`/`pnpm newman` scripts) — these are the only new code paths.

</domain>

<decisions>
## Implementation Decisions

### Postman generation + augmentation pipeline (HND-01/02/03)

- **D-65-GEN-NPM:** Generate the base collection with **`openapi-to-postmanv2@6.0.1`** (LOCKED by HND-01), NOT by extending the existing stdlib generator `apps/backend/scripts/export_postman.py` (Phase 46, which produced the historical `v1.6-postman.json`). The npm tool provides `folderStrategy=Tags` natively and consumes the Phase 64 tags/operation-IDs directly.
  - **Why:** HND-01 pins the tool by name and version. The Python generator is superseded for v1.11 handoff; leave `v1.6-postman.json` as a historical artifact, do not delete it.
  - **How to apply:** Base generation is a build step (config: `folderStrategy=Tags`, request name from `summary`, internal `_internal` tag excluded — mirror `export_postman.py`'s `_operation_is_internal` filter so the external team never sees webhooks). Output is then augmented (D-65-AUGMENT).

- **D-65-AUGMENT:** Inject auth scripts (HND-02) and test assertions (HND-03) via a **committed Node post-processing script** (e.g. `tools/newman/augment-collection.mjs`) that reads the base-generated collection and writes the final committed `v1.11-clubcore.postman_collection.json`. Do NOT hand-edit the generated JSON.
  - **Why:** The frozen spec can still drift (e.g. the Phase 66 `IdempotencyKey` parameter just landed); a scriptable augmentation survives regeneration where hand-edits would be silently lost. Matches the project's byte-stable-regen culture (D-64-BYTE-STABLE).
  - **How to apply:** The augment script injects (a) a collection-level pre-request stub + collection variables `{accessToken, csrfToken}`; (b) on the login request: a `pm.cookies`/`pm.response.headers` extraction of `cc_access`/`cc_refresh`/`sportzal_csrf` → collection vars; (c) a collection-level pre-request that adds `X-CSRF-Token: {{csrfToken}}` to every non-GET; (d) `pm.response.to.have.status(...)` on every request; (e) one `pm.test()` body-shape assertion on the auth happy-path + 1 representative request per domain. Planner may fall back to targeted hand-editing for the per-domain `pm.test()` bodies if scripted injection of those proves heavy — the auth/CSRF wiring stays scripted regardless.

### Newman smoke credentials + seed (HND-04)

- **D-65-NEWMAN-CREDS:** The Newman smoke authenticates against the **existing verification fixtures** seeded by `apps/backend/scripts/seed_verification_fixtures.py` (`verify_owner@local.dev`). The Newman env file (`tools/newman/`) commits the **email only**; the password is supplied at runtime via `newman --env-var "password=$SEED_VERIFY_OWNER_PASSWORD"`, never committed.
  - **Why:** `seed_verification_fixtures.py` already reads passwords from env (`SEED_VERIFY_OWNER_PASSWORD`) and commits none — the smoke must honor the same "no real credentials committed" constraint (HND-01/04). The fixture user is deterministic against `docker compose up`.
  - **How to apply:** Document in the runbook that the smoke requires `docker compose up` + the seed script run with `SEED_VERIFY_OWNER_PASSWORD` set, then `SEED_VERIFY_OWNER_PASSWORD=... pnpm newman run`. The Newman env is a SEPARATE file from the placeholder-only Postman environment (HND-01): the Postman env ships pure placeholders for human GUI use; the Newman env wires the local-dev fixture login for automated smoke.

### Newman smoke scope (HND-04)

- **D-65-SMOKE-SCOPE:** The smoke runs a **curated happy-path subset**, not the entire mutating surface: login → CSRF retrieval → one representative *safe* request per domain (GET/list where possible) → the idempotency replay happy-path. Destructive/financial mutations (refunds, sells) requiring complex fixtures are NOT in the smoke.
  - **Why:** "Smoke harness" = prove auth + CSRF + representative reachability against a fresh `docker compose` DB. Running every category-A mutation against a bare DB fails on missing fixtures and is not a smoke. `--bail` then meaningfully gates on real breakage, not fixture gaps.
  - **How to apply:** Implement the subset either as a dedicated Postman folder the smoke targets (`newman run ... --folder smoke`) or as a separate trimmed collection in `tools/newman/`. Planner picks; the folder-within-the-shipped-collection approach keeps a single source of truth. Log/document which requests are in-smoke so coverage is not silently truncated.

### Auth runbook structure + language (HND-05)

- **D-65-RUNBOOK-EXTEND:** Author `clubcore-auth-runbook.md` by **extending the v1.4 structure** (`.planning/handoff/v1.4-auth-runbook.md`), under the clubcore name, with the project's bilingual convention: **Russian section prose + English code/curl** (matches v1.4 precedent and RU-only project i18n).
  - **Sections (in order):** 1) Login (email/password — owner + reception) → 2) Refresh rotation family → 3) CSRF on mutating requests → 4) Telegram OTP (client-app path) → 5) Email OTP → 6) Logout-all → 7) **Idempotency-Key semantics (NEW, Phase 66)** → 8) `sportzal_csrf` carry-over note + v2.0 cutover plan.
  - **How to apply:** Each curl example is paired with its Postman-collection request ID/name (HND-05). The Idempotency-Key section documents: header format (`^[A-Za-z0-9_:-]{16,128}$`), user-scoped key, 24h replay window, verbatim replay (returns first-success response, not live DB state — point readers to the resource GET), and curl examples showing a replay. Pull these from the Phase 66 spec + `.planning/handoff/v1.11-idempotency-audit.md`.

### Tooling entry point (pnpm scripts) (HND-04/06)

- **D-65-ROOT-PKG:** Add a **private repo-root `package.json`** (`"private": true`, no version/publish) holding the `docs` and `newman` scripts and the three handoff devDependencies (`@redocly/cli@2.31.4`, `newman`, `openapi-to-postmanv2@6.0.1`). This makes `pnpm docs` and `pnpm newman run` resolve at repo root exactly as HND-04/HND-06 phrase them.
  - **Why:** There is NO root `package.json` today (only `pnpm-workspace.yaml` with globs `apps/*`, `packages/*`); `tools/` is outside the workspace globs. A private root package.json is the conventional pnpm-workspace root and the lowest-surprise home for cross-cutting handoff tooling. Avoids polluting `apps/admin-web` (frozen) or `packages/api-client`.
  - **How to apply:** `scripts.docs` = `redocly preview-docs apps/backend/openapi.json --port 8080` (or the `npx @redocly/cli` equivalent); `scripts.newman` = `newman run .planning/handoff/v1.11-clubcore.postman_collection.json -e tools/newman/<env>.json --bail` (so `pnpm newman run` works). The base-generation + augment steps may also be root scripts (e.g. `postman:gen`, `postman:augment`). A `make docs` alias is OPTIONAL (HND-06 says "or make docs") — root package.json `pnpm docs` is the primary.

### Doc-site privacy enforcement (HND-06)

- **D-65-DOCS-PRIVATE:** `pnpm docs` runs **`preview-docs` only** (live local server on port 8080) — no static `build-docs`/`bundle` step that emits a publishable artifact, no PDF export, no published search index, no deploy/publish script anywhere in the repo. If a static `.docs-site/` is ever built for offline browsing, it is gitignored and unpublished.
  - **Why:** D-11-DOCS-PRIVATE (CLAUDE.md constraint) — the doc-site is a private artifact that must never reach a public domain. Shipping only `preview-docs` structurally prevents an accidental publish path.
  - **How to apply:** Add `.docs-site/` to `.gitignore` (HND-06). Verify no GitHub Pages / deploy workflow references the doc-site. The runbook notes the doc-site is private/local-only.

### Claude's Discretion

- Whether the smoke subset (D-65-SMOKE-SCOPE) is a folder inside the shipped collection (`--folder smoke`) or a separate trimmed collection file — planner picks; single-collection-with-folder preferred for one source of truth.
- Exact shape of the augment script (D-65-AUGMENT) — single `.mjs`, or a small pipeline (`postman:gen` → `postman:augment`); whether per-domain `pm.test()` bodies are scripted or targeted hand-edits (auth/CSRF wiring stays scripted regardless).
- Whether to add a `make docs` alias in addition to `pnpm docs` (HND-06 allows either) — optional convenience.
- Exact representative request chosen per domain for the HND-03 body-shape assertion and the D-65-SMOKE-SCOPE smoke — researcher/planner picks the safest read per domain against a fresh compose DB.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 65 scope authority
- `.planning/ROADMAP.md` §"Phase 65: Handoff Artifacts" (lines 106-121) — goal, 6 success criteria, the non-monotonic ordering note (65 executes AFTER 66), dependency on Phase 64 tags/op-IDs + Phase 66 idempotency param
- `.planning/REQUIREMENTS.md` §"Handoff Artifacts (Phase 65 — HND-*)" lines 54-59 — the 6 authoritative HND-* requirements (these LOCK tool versions, file paths, env-var names, folder strategy)
- `.planning/PROJECT.md` §"Current Milestone: v1.11 API Handoff + Production Hardening"

### v1.11 milestone decisions (locked 2026-05-26)
- `.planning/STATE.md` §"Key v1.11 Decisions" — **D-11-CSRF-DEFER** (`sportzal_csrf` retained, rename → v2.0), **D-11-NEWMAN-LOCAL** (Newman is local smoke, not a CI gate), **D-11-DOCS-PRIVATE** (Redocly doc-site private/gitignored, no public publish)
- `.planning/STATE.md` §"Deferred to v2.0" — `sportzal_csrf` → `clubcore_csrf` rename; Newman as blocking CI gate

### Frozen spec + generation inputs
- `apps/backend/openapi.json` — the post-Phase-66 frozen spec; the SINGLE source all artifacts derive from (correct clubcore `info`, 10 tags, cleaned operation IDs, `components.parameters.IdempotencyKey`)
- `apps/backend/scripts/export_postman.py` — the existing stdlib Postman generator (Phase 46). REFERENCE ONLY for v1.11 (D-65-GEN-NPM supersedes it with the npm tool); reuse its `_operation_is_internal` `_internal`-tag exclusion logic so webhooks don't leak to the external team
- `apps/backend/scripts/export_openapi.py` — byte-stable spec exporter (the spec is regenerated by this, never hand-edited)

### Phase 66 idempotency inputs (for HND-05 runbook section)
- `.planning/handoff/v1.11-idempotency-audit.md` — the category-A endpoint audit + classification; source for the runbook's Idempotency-Key endpoint list
- `.planning/phases/66-idempotency-hardening/66-CONTEXT.md` §D-66-OPENAPI-PARAM / §"Specific Ideas" — key pattern `{16,128}`, user-scoped key, 24h TTL, verbatim-replay semantics (PITFALLS C-05 note); explicitly defers the runbook idempotency prose + client-side retry-key guidance to THIS phase

### Precedent artifacts (templates to extend, NOT edit)
- `.planning/handoff/v1.4-auth-runbook.md` — the runbook structure D-65-RUNBOOK-EXTEND extends (bilingual RU prose + EN curl; sections: login / refresh rotation / CSRF / Telegram OTP / logout-all)
- `.planning/handoff/v1.6-postman.json` — historical Postman artifact (the prior generator's output); reference for structure, NOT the v1.11 deliverable
- `apps/backend/scripts/seed_verification_fixtures.py` — `verify_owner@local.dev` / `verify_reception@local.dev` fixtures (env-sourced passwords `SEED_VERIFY_OWNER_PASSWORD` / `SEED_VERIFY_RECEPTION_PASSWORD`); the Newman smoke login target (D-65-NEWMAN-CREDS)

### Workspace / tooling context
- `pnpm-workspace.yaml` — globs `apps/*`, `packages/*` (NO `tools/*`; NO root `package.json` today — D-65-ROOT-PKG adds one)
- `packages/api-client/package.json` — `codegen` script pattern (`openapi-typescript ../../apps/backend/openapi.json`); precedent for a tool consuming the frozen spec
- `redocly.yaml` (repo root) — Phase 64 Redocly lint config; HND-06 `preview-docs` reuses the same Redocly CLI
- `.gitignore` — add `.docs-site/` (HND-06)

### Prior-phase precedent
- `.planning/phases/64-contract-freeze-openapi-curation/64-CONTEXT.md` §D-64-BYTE-STABLE / §D-64-TAG-ORDER — byte-stable regen discipline (D-65-AUGMENT mirrors it) + the 10-domain tag order the Postman folders inherit
- `.planning/phases/63-tech-debt-sweep/63-CONTEXT.md` — atomic-commit-per-requirement discipline

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`apps/backend/scripts/export_postman.py`** — `_operation_is_internal` (`_internal`-tag exclusion), `_path_variables` (`{id}` → Postman url.variable), byte-stable JSON write conventions. Reuse the exclusion logic when configuring/augmenting the npm-generated collection so webhooks stay out of the external package.
- **`apps/backend/scripts/seed_verification_fixtures.py`** — deterministic `verify_owner@local.dev` fixture with env-sourced password; the exact login the Newman smoke targets (D-65-NEWMAN-CREDS).
- **`redocly.yaml` + Redocly CLI (Phase 64)** — already installed/configured for lint; HND-06 `preview-docs` reuses the same CLI on the same frozen spec.
- **`v1.4-auth-runbook.md`** — full bilingual runbook skeleton (login / refresh / CSRF / OTP / logout) to extend.
- **`packages/api-client` codegen** — precedent for `openapi.json` → generated-artifact pipelines consuming the frozen spec from `apps/backend/`.

### Established Patterns
- **Byte-stable regen + drift discipline** (D-64-BYTE-STABLE) — argues for D-65-AUGMENT's scriptable (not hand-edited) collection augmentation.
- **`_internal`-tag exclusion** (D-46-08) — external consumers never see webhook endpoints; carry into the npm-generated collection config.
- **Env-sourced secrets, none committed** (`seed_verification_fixtures.py`, placeholder Postman env) — Newman password via `--env-var` at runtime, not in any committed file.
- **`sportzal_csrf` cookie name retained** (D-11-CSRF-DEFER) — the runbook + Postman cookie-extraction script use the literal `sportzal_csrf`, documented as a carry-over.

### Integration Points
- **Repo-root `package.json` (new, D-65-ROOT-PKG)** — `pnpm docs` + `pnpm newman` entry points; the only place handoff devDeps live.
- **`tools/newman/`** — smoke script + Newman env JSON (outside pnpm workspace globs; invoked via root scripts, not as a workspace package).
- **`.planning/handoff/`** — output home for the collection, environment, and runbook (sits alongside existing v1.4/v1.6/v1.9 artifacts).
- **`apps/backend/openapi.json`** — read-only input to every artifact; this phase NEVER edits it.
- **`.gitignore`** — `.docs-site/` added (HND-06).

</code_context>

<specifics>
## Specific Ideas

- **Two distinct env files:** placeholder-only Postman GUI environment (`v1.11-clubcore.postman_environment.json`, committed, no creds) vs the Newman smoke env (`tools/newman/`, ships fixture email only, password via runtime `--env-var`). Do not conflate them.
- **Idempotency runbook section is the Phase-66 → Phase-65 handoff seam:** Phase 66 deliberately deferred the runbook prose + client-side retry-key (UUIDv4) guidance to here. Document key format `{16,128}`, user-scope, 24h replay window, verbatim-replay-not-live-state, with a worked curl replay example.
- **Webhooks excluded from the external collection** (`_internal` tag) — but the runbook may still mention the ЮKassa webhook's separate `cc:yk:webhook:*` dedup for completeness.
- **Smoke coverage must be documented, not silently truncated** — the runbook lists which requests the smoke exercises and notes it deliberately excludes destructive/financial mutations.

</specifics>

<deferred>
## Deferred Ideas

- **Newman as a blocking CI gate** → v2.0 (D-11-NEWMAN-LOCAL: local smoke only in v1.11; STATE.md "Deferred to v2.0").
- **`sportzal_csrf` → `clubcore_csrf` cookie rename** → v2.0 (D-11-CSRF-DEFER); v1.11 runbook documents the carry-over + cutover plan only.
- **Public-hosted / deployed API docs** → never under current constraints (D-11-DOCS-PRIVATE); doc-site stays private/local.
- **Replacing/retiring the stdlib `export_postman.py` generator** → not in scope; leave as historical Phase 46 tooling. A future cleanup phase could remove it once the npm pipeline is proven.
- **Mailpit `--profile dev` in docker-compose + operator runbook walkthroughs** → Phase 67 (RUN-*), not Phase 65.

### Reviewed Todos (not folded)
None — `todo.match-phase 65` returned 0 matches.

</deferred>

---

*Phase: 65-handoff-artifacts*
*Context gathered: 2026-05-29*
*Discussion mode: `--auto` (recommended defaults; user can override before plan-phase)*
