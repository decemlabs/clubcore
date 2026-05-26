# Project Research Summary

**Project:** clubcore — v1.11 API Handoff + Production Hardening
**Domain:** FastAPI modular monolith — OpenAPI curation, handoff tooling, idempotency hardening, tech-debt sweep, operator runbook execution
**Researched:** 2026-05-26
**Confidence:** HIGH — all four researchers worked from direct codebase inspection; versions confirmed live

---

## Executive Summary

v1.11 is a zero-new-business-feature milestone. The entire backend business logic (clients, memberships, visits, schedule, bookings, trainers, payroll, billing, notifications) was shipped in v1.1–v1.9. This milestone is about making that surface credible for handoff: clean linting, a curated OpenAPI spec with correct metadata, Postman and Newman artifacts a frontend integration team can actually use, hardened idempotency semantics, and execution of four runbooks that have been sitting OPERATOR-PENDING for up to three milestones. No new ORM entities, no Alembic migrations, no new business modules, no npm/PyPI publishing.

The recommended approach is strictly sequential for the first two phases, with a compact parallel window before artifacts are generated. Phase 63 (tech-debt sweep) must come first — ruff/mypy errors will break the CI drift gate that guards `openapi.json`, so any spec-touching work must wait for a clean tree. Phase 64 (contract freeze) must complete before any handoff artifact is generated, because the Postman collection, auth runbook, and doc-site are all sourced from the curated `openapi.json`. Phase 66 (idempotency hardening) must complete before Phase 65 artifacts are finalized, because Phase 66 adds `components/parameters/IdempotencyKey` to the spec and backfills `Depends(verify_idempotency)` to several financial endpoints — regenerating the Postman collection before Phase 66 merges would produce an incomplete collection. The correct order is **63 → 64 → 66 → 65 → 67**.

The two highest-risk areas are the operation ID strategy and the cross-user idempotency gap. The operation ID decision in Phase 64 directly affects whether `schema.d.ts` function names change — breaking all callsites in `apps/admin-web`. The safest path is `generate_unique_id_function` to strip the `_api_v1_{method}` suffix (one atomic diff that changes string values but not TypeScript function names) rather than 103 hand-written `operation_id=` annotations that each change the semantic name. On idempotency: the current `verify_idempotency` key is `{method}:{path}:{header_value}` — it does not bind to the authenticated user. In a multi-user admin (owner + reception) with deterministic or short retry keys, two users can collide on the same Redis entry and user B receives user A's transaction result. Phase 66 must add `current_user.id` to the key namespace.

---

## Key Findings

### Recommended Stack

The locked backend stack (Python 3.12 + FastAPI 0.115+ + SQLAlchemy 2.0 async + Redis 7 + ARQ + structlog) is unchanged. v1.11 adds exactly four new devDependencies to the pnpm workspace root, all for tooling — none affect the Python runtime or the production Docker image.

**New tooling additions (all devDeps, pnpm workspace root):**
- `openapi-to-postmanv2@6.0.1` — official Postman Labs OpenAPI 3.x → Collection v2.1 converter; binary `openapi2postmanv2`; matches the `v2.1.0/collection.json` schema already used in `v1.6-postman.json`
- `newman@6.2.2` — official Postman CLI smoke runner; operator-local only, not a CI gate in v1.11
- `@redocly/cli@2.31.4` — dual use: Phase 64 CI lint gate (`redocly lint`) + Phase 65 local doc preview (`redocly preview-docs`); released 2026-05-22
- `axllent/mailpit:latest` — Docker-only SMTP trap; drop-in for archived MailHog (last Docker update 2019); added behind `profiles: [dev]`; requires an SMTP adapter path in the backend which is NOT yet implemented

**Critical constraint:** The existing email integration uses `aioboto3` SES-V2 against Yandex Cloud Postbox — not SMTP. Mailpit cannot intercept SES-V2 calls. For Phase 67 email evidence, use `EMAIL_PROVIDER=sandbox` (the existing `SandboxEmailClient` logs full email envelopes to structlog) — zero new code. A real Mailpit SMTP adapter requires `aiosmtplib` + new config fields + new tests and is out of v1.11 scope.

**No new Python packages.** `app/core/idempotency.py` (210 lines) is fully implemented. ruff `0.15.12` and mypy `1.20.2` are already installed. No `pre-commit` hooks — existing CI gates provide the same coverage without workflow-contract changes.

### Expected Features

v1.11 produces infrastructure artifacts, not business features.

**Must have (table stakes — milestone cannot close without these):**

Phase 63:
- `ruff check` exit 0 (158 current errors, ~80 auto-fixable safely with `--fix`)
- `ruff format` applied to 297 files — byte-stable `openapi.json` regen requires deterministic formatting
- `mypy --strict` clean (11 errors in 7 files in `app/`; all fixable without new `# type: ignore` lines)
- DEFER-40-01: v1.5 `run.sh` runbook hardened (4 documented bugs: RBAC actor, X-CSRF-Token header, table name, +1 TBD from archives)

Phase 64:
- `info.title = "clubcore API"`, `info.version = "1.11.0"`, `info.description` populated (currently `"Sportzal API"` + `"1.1.0"`)
- `servers` array with `http://localhost:8000` dev server entry
- `securitySchemes` defining `cookieAuth` (`sz_access` cookie) + `csrfHeader` (`X-CSRF-Token`)
- Explicit operation IDs on all 103 operations (strategy decision: see Open Questions)
- `openapi_tags` list for tag ordering and descriptions (18 existing tags)
- `components.responses` shared error envelopes for 401/403/404/422 (currently all inlined per-operation)
- Pre-freeze drift gate tightened so any `openapi.json` diff fails CI

Phase 65:
- Postman v2.1 collection at `.planning/handoff/v1.11-clubcore.postman_collection.json` with pre-request auth script (cookie capture + CSRF extraction) and `pm.test()` assertions on every request
- Newman smoke (`make smoke` / `tools/newman/smoke.sh`) covering 10+ critical endpoints, exits non-zero on failure
- `clubcore-auth-runbook.md` — expanded replacement for `v1.4-auth-runbook.md` covering CSRF flow, Telegram OTP, refresh rotation, invite+accept, password-reset, Idempotency-Key semantics
- Private Redocly doc-site via `make docs` (gitignored output, never published)

Phase 66:
- Per-endpoint idempotency audit table (A: already covered, B: needs coverage, C: not applicable)
- `IDEMPOTENCY_TTL_SECONDS = 86400` (24h — up from 3600s/1h)
- `Depends(verify_idempotency)` backfilled to 5 membership endpoints + 2 online-refund endpoints currently missing it
- `verify_idempotency` key binds to `actor_user_id` (currently missing — cross-user replay security gap)
- `components/parameters/IdempotencyKey` reusable OpenAPI parameter + `$ref` injection on all covered endpoints
- Integration tests: double-submit on 3 financial endpoints (memberships sell, PT-package sell, online-payment sell)

Phase 67:
- RUN-01..06 evidence appended to `.planning/milestones/v1.10-OPERATOR-EVIDENCE.md` (append-only per D-62.1-B2)
- Credential-gated items (RUN-02 email delivery if domain not provisioned) have `N/A-until-production` rows with trigger conditions

**Should have (differentiators — do if trivial):**
- `info.contact` populated in Phase 64
- `x-clubcore-rbac` extension on OWNER_ONLY operations in Phase 64
- `Idempotency-Replayed: true` response header on replayed responses in Phase 66
- `Makefile` targets `make docs` and `make smoke` in Phase 65
- Postman folder demonstrating idempotency duplicate-request pairs in Phase 65

**Defer to v2.0+:**
- Newman as a blocking CI gate (requires full docker-compose service stack in CI)
- Mailpit + SMTP adapter (`aiosmtplib` + new config + new tests)
- Per-club configurable gym brand (`CLUB_BRAND` placeholder `"Sportzal"` retained per D-62-02)
- `sportzal_csrf` cookie name rename (locked runtime client contract; requires coordinated admin-web update)
- `x-codeSamples` in spec (Medium effort; v2.0 DX enhancement)
- PDF export of doc-site
- Public publish of spec or collection

**Explicit anti-features (never do in this project):**
- Publishing spec/collection to any public URL — private commercial CRM; leaks business logic and RBAC surface
- npm/PyPI publishing — prohibited per D-10-NO-PUBLISH
- `# type: ignore` to suppress mypy warnings — fix the underlying issue
- Newman with no test assertions — silently exits 0 even when every endpoint returns 500
- Fabricated operator evidence — explicitly prohibited by D-62.1-B1
- Unifying ЮKassa webhook Redis dedup (`cc:yk:webhook:*`) with client-facing idempotency (`cc:idem:*`)
- Blanket idempotency on all 57 mutating endpoints — auth flows, soft-deletes, and status transitions are deliberately exempt

### Architecture Approach

v1.11 makes no structural changes to the modular monolith. The Protocol-slot cross-module wiring, the 15-module `app/modules/*/router.py` layout, and `app/core/` utilities are untouched architecturally. Changes are confined to `app/main.py` (spec metadata + `custom_openapi()` override), 15 module routers (`operation_id=` decorators + some `Depends(verify_idempotency)` additions), `app/core/idempotency.py` (one constant + signature addition), `apps/backend/scripts/export_postman.py` (constants update), and new files in `tools/newman/` and `.planning/handoff/`.

**Major components touched per phase:**

1. `app/main.py` — Phases 63 + 64 + 66: `title=`, `version=`, `openapi_tags=`, `custom_openapi()` override injecting `servers`, `securitySchemes`, `components/parameters/IdempotencyKey`, and `IDEMPOTENCY_OPERATION_IDS` post-processing hook
2. `app/modules/*/router.py` (15 files) — Phase 64: `operation_id=` on all 103 decorators; Phase 66: `Depends(verify_idempotency)` on 7 additional endpoints
3. `app/core/idempotency.py` — Phase 66: `IDEMPOTENCY_TTL_SECONDS = 86400`; add `current_user` param to `verify_idempotency`
4. `.planning/handoff/` — Phase 65: new Postman collection, auth runbook, Newman env
5. `apps/backend/docker-compose.yml` — Phase 67: MailHog service under `profiles: [dev]`
6. `.planning/milestones/v1.10-OPERATOR-EVIDENCE.md` — Phase 67: append RUN-01..06 sections

**Key pattern — one atomic `openapi.json` regen per phase.** The drift gate fails if `openapi.json` or `schema.d.ts` are out of sync. Each phase that changes the spec must regenerate both files and commit them in the same PR.

**`custom_openapi()` override** in `app/main.py` is the correct FastAPI idiom for injecting `securitySchemes` and `components/parameters` that FastAPI does not generate natively from `Depends()`. No new module is needed — 40 lines in the existing file.

**Idempotency stays as `Depends()`, not ASGI middleware.** 16 existing callsites already use `Depends(verify_idempotency)`. Middleware would require response buffering and removing all 16 explicit deps — wrong direction for opt-in endpoint-level idempotency.

### Critical Pitfalls

1. **Operation ID rename breaks `schema.d.ts` and `apps/admin-web` callsites (C-01)** — Use `generate_unique_id_function` to strip the `_api_v1_{method}` suffix in one atomic commit rather than 103 hand-written explicit IDs with new semantic names. The suffix strip changes string values in `schema.d.ts` but not the TypeScript function names that admin-web callsites reference. Verify with `_v19Checks` + `_v18Checks` TypeScript guards compiling clean. Recovery if wrong: `git revert` the operation ID changes and re-approach with suffix stripping.

2. **Cross-user idempotency replay — missing `actor_user_id` in Redis key (C-03)** — Current key is `{method}:{path}:{header_value}`. User B with the same key string gets User A's cached transaction result. Fix in Phase 66: add `current_user: Annotated[User, Depends(get_current_user)]` to `verify_idempotency` and use `f"{method}:{path}:{user.id}:{header_value}"`. All 16+ existing callsites get the fix automatically via FastAPI dependency graph resolution.

3. **In-flight idempotency placeholder stuck after DB rollback (C-02)** — If the service layer raises and `store_idempotency_response` is never called, the Redis key stays as `__in_flight__` for up to TTL. Fix: wrap `store_idempotency_response` in `try/except` — store error response envelope on known `AppError`; delete placeholder on unknown exceptions so client can retry fresh.

4. **Newman exits 0 with no test assertions (C-08)** — `openapi-to-postmanv2` generates request definitions but no `pm.test()` scripts. Always add `pm.response.to.be.success` to each request minimum and always pass `--bail` to Newman.

5. **Monolithic sweep PR is undebuggable if any test fails (C-07)** — Split Phase 63 into three separate commits: (1) `ruff format` only, (2) `ruff check --fix` safe-only, (3) manual mypy + remaining ruff fixes. Never use `--unsafe-fixes` — the 17 Protocol slots have arguments that appear unused to ruff but are required by Protocol signatures.

---

## Implications for Roadmap

Based on combined research, the confirmed phase order is **63 → 64 → 66 → 65 → 67**.

### Phase 63: Tech-Debt Sweep
**Rationale:** CI must be green before any spec-touching PR lands. ruff/mypy are the CI gates that block Phase 64's `openapi.json` drift event. Also resolves DEFER-46-04 and DEFER-36-04-B which have been carried for 3 milestones.
**Delivers:** `ruff check` exit 0, `ruff format` applied, `mypy --strict` clean, v1.5 `run.sh` hardened (DEFER-40-01)
**Avoids:** C-06 (unsafe ruff fixes change semantics), C-07 (monolithic sweep PR)
**Planning hint:** Encode the three-commit split (format → safe-fix → manual) as separate plans, not one. DEFER-36-04-B content needs confirmation from v1.4 archives before requirements authoring (see Gaps).
**Research flag:** Standard patterns — no further research needed.

### Phase 64: Contract Freeze (OpenAPI Curation)
**Rationale:** All handoff artifacts are sourced from `openapi.json`. Must merge before Phase 65 artifact generation begins.
**Delivers:** Frozen curated spec with correct `info.*`, `servers`, `securitySchemes`, `openapi_tags`, `components.responses`, operation IDs, Redocly lint gate in CI, regenerated `openapi.json` + `schema.d.ts`
**Avoids:** C-01 (operation ID rename breaks schema.d.ts), C-04 (stale Sportzal API title), C-13 (OpenAPI 3.1 nullable holdovers)
**Planning hint (scope realism):** 103 endpoints across 15 router files is M-to-L complexity. Suggest structuring as 4 plans: (1) `generate_unique_id_function` + spec metadata (`title`, `version`, `description`, `servers`) + regen, (2) `securitySchemes` + `openapi_tags` via `custom_openapi()` + regen, (3) `components.responses` shared error envelopes + Redocly lint gate addition to CI, (4) drift gate tightening + `@clubcore/api-client` version bump to `1.11.0`.
**Research flag:** No further research needed — architecture file has exact code patterns.

### Phase 66: Idempotency Hardening
**Rationale:** Placed before Phase 65 because Phase 66 adds `components/parameters/IdempotencyKey` to the spec and backfills 7 endpoints. The Postman collection generated in Phase 65 must reflect the final idempotency surface.
**Delivers:** `IDEMPOTENCY_TTL_SECONDS = 86400`, `verify_idempotency` user-scoped, 7 endpoints backfilled, `components/parameters/IdempotencyKey` in spec, double-submit integration tests for 3 financial endpoints, idempotency section in auth runbook
**Avoids:** C-02 (in-flight placeholder stuck on rollback), C-03 (cross-user replay), C-05 (stale cache semantics undocumented)
**Planning hint:** The `current_user` parameter addition to `verify_idempotency` affects all 16+ existing callsites — verify FastAPI resolves the nested `Depends` correctly. Add a test that submits the same key from two different user sessions and confirms distinct Redis entries.
**Research flag:** No further research needed — architecture file has the `IDEMPOTENCY_OPERATION_IDS` post-processing hook pattern.

### Phase 65: Handoff Artifacts
**Rationale:** Artifact generation is last of the backend-engineering phases because every artifact derives from the finalized spec (after both Phase 64 curation and Phase 66 idempotency additions).
**Delivers:** `.planning/handoff/v1.11-clubcore.postman_collection.json`, `tools/newman/smoke.sh` + env JSON, `.planning/handoff/clubcore-auth-runbook.md`, `make docs` Redocly preview target
**Avoids:** C-08 (Newman exits 0 with no assertions), C-09 (Newman in CI without DB), C-10 (credentials in newman-env.json)
**Planning hint (scope realism):** The Postman collection is L complexity — full rewrite of `v1.6-postman.json` (which had no test assertions and the Sportzal name). Plan for 5 plans: (1) update `export_postman.py` + regenerate base collection, (2) add pre-request auth script + CSRF extraction, (3) add `pm.test()` assertions on all 10+ smoke requests, (4) auth runbook authoring, (5) Redocly preview setup + `make docs`/`make smoke` targets. Newman env file must use only `@fixture.local` credentials; add `*newman-env.local.json` to `.gitignore` before creating the committed file.
**Research flag:** No further research needed — STACK.md has exact `openapi2postmanv2` flags and Newman invocation.

### Phase 67: Operator-Pending Runbook Execution
**Rationale:** Must be last — depends on the auth runbook (Phase 65), the `run.sh` fix (Phase 63), and ideally the Postman collection for ЮKassa sandbox flow.
**Delivers:** Evidence for RUN-01..06 appended to `.planning/milestones/v1.10-OPERATOR-EVIDENCE.md`; MailHog `--profile dev` service in docker-compose
**Avoids:** C-11 (stale runbook env var names), C-12 (VER-03 accidentally hits ЮKassa production)
**Planning hint:** Plan 1 is always a staleness audit — grep each runbook for `sz:`, `SPORTZAL_EMAIL_FROM`, `sportzal`, and validate endpoint paths against curated `openapi.json`. VER-03 must print `YooKassaSettings().sandbox == True` as first evidence line.
**Research flag:** No further research needed for standard walkthroughs. VER-03 may surface ЮKassa sandbox credential availability — if not provisioned, mark `N/A-until-production` per RUN-08-dns-dkim-DEFERRED precedent.

### Phase Ordering Rationale

- **63 before 64:** ruff/mypy CI gates block `openapi.json` drift PRs; clean tree required
- **64 before 66:** Phase 66's `IDEMPOTENCY_OPERATION_IDS` frozenset uses the Phase 64 explicit operation ID strings; spec must be consistent
- **66 before 65:** `components/parameters/IdempotencyKey` + backfilled endpoints must be in spec before Postman collection is generated; auth runbook idempotency section written last
- **65 before 67:** auth runbook documents CSRF + cookie flow needed for RUN-01; Newman smoke is the primary tool for Phase 67 evidence capture
- **66 CAN start in parallel with 64 code changes** (adding `Depends(verify_idempotency)` to routers does not conflict with adding `operation_id=`), but `openapi.json` regen at end of Phase 66 must include both Phase 64 and Phase 66 changes. Simplest: merge Phase 64 first, then open Phase 66.

### Open Questions for Planning

1. **operation_id strategy (Phase 64, plan 1):** `generate_unique_id_function` suffix stripping (RECOMMENDED — one atomic diff, TypeScript function names unchanged, defers semantic rename to v2.0 when admin-web integration happens anyway) vs explicit `operation_id=` on every decorator (more diff, full semantic control, higher risk of schema.d.ts breakage). Architecture research strongly supports `generate_unique_id_function` for v1.11.

2. **`verify_idempotency` + `get_current_user` dependency depth (Phase 66):** Adding `Depends(get_current_user)` to `verify_idempotency` deepens the chain. Verify no circular dependency before writing Phase 66 requirements. All existing callsites already independently declare `current_user` — FastAPI will deduplicate. LOW risk.

3. **DEFER-36-04-B content (Phase 63):** Not described in research. Must check v1.4 milestone archives before Phase 63 requirements. Research summary says "123 files from v1.4 era, rolled into the ruff format pass" — confirm this is correct.

4. **`sportzal_csrf` cookie name:** Architecture research flags this as a locked runtime client contract. Phase 63 sweep should explicitly NOT rename this cookie. Document as v2.0 item. Do not confuse with the `title="Sportzal API"` string (which IS a Phase 64 target).

### Research Flags

Phases needing deeper research during planning:
- None — all five phases have well-documented patterns from direct codebase inspection. The research files contain exact code snippets for every integration point.

Phases with standard patterns (skip `/gsd-research-phase`):
- **Phase 63:** ruff/mypy sweeps are mechanical; patterns and exact fix list documented in STACK.md
- **Phase 64:** `custom_openapi()` pattern + exact file list documented in ARCHITECTURE.md
- **Phase 65:** `openapi2postmanv2` flags + Newman invocation documented in STACK.md and FEATURES.md
- **Phase 66:** `verify_idempotency` extension + `IDEMPOTENCY_OPERATION_IDS` hook documented in ARCHITECTURE.md
- **Phase 67:** Runbook execution — staleness audit pattern documented in PITFALLS.md

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions confirmed via live npm registry queries + direct pyproject.toml inspection |
| Features | HIGH | Entire feature set sourced from current codebase state (`openapi.json`, router files, `idempotency.py`) + PROJECT.md carry-over items |
| Architecture | HIGH | All integration points verified by AST scan of 15 router files + direct inspection of `idempotency.py`, `main.py`, `ci.yml`, `docker-compose.yml` |
| Pitfalls | HIGH | 8 of 13 pitfalls backed by direct codebase evidence; 5 are pattern-based but consistent with established conventions |

**Overall confidence: HIGH**

Minor discrepancy: STACK.md reports 11 mypy errors in 7 files (`mypy app`); ARCHITECTURE.md reports 394 errors across 117 files (`mypy app tests`). Phase 63 planning should confirm scope: `mypy app` (11 errors — likely the correct gate given DEFER-46-04 was about the app tree) vs `mypy app tests` (394 errors — includes test annotation gaps). Recommend `mypy app` as the Phase 63 gate with `tests/` as a separate sweep.

### Gaps to Address

- **DEFER-36-04-B scope:** Not documented in research. Check v1.4 milestone archives before Phase 63 planning.
- **mypy scope (app vs app+tests):** Confirm before writing Phase 63 requirements — 11 errors vs 394 errors is a significant planning difference.
- **DEFER-40-01 run.sh fourth bug:** Research describes 3 of 4 bugs (RBAC actor, X-CSRF-Token header, table name). Confirm full bug list from v1.5 deferred item.
- **RUN-02 domain status:** Phase 67 RUN-02 requires a live `CLUBCORE_EMAIL_FROM` domain with SPF/DKIM. Confirm domain provisioning status before Phase 67 planning.

---

## Sources

### Primary (HIGH confidence — direct codebase inspection)

- `apps/backend/app/core/idempotency.py` — full idempotency subsystem; TTL, key shape, in-flight pattern confirmed
- `apps/backend/app/main.py` — `title="Sportzal API"`, `version="1.1.0"` stale strings confirmed
- `apps/backend/app/api/v1/router.py` — all 103 endpoint mounts with tags confirmed
- `apps/backend/app/modules/*/router.py` — AST scan of all 15 module routers; idempotency coverage table
- `apps/backend/openapi.json` — 81 paths, 103 operations, 0 securitySchemes, 0 parameters, 0 servers, 1 `nullable` holdover
- `apps/backend/docker-compose.yml` — 5 services; no MailHog; no `profiles:` defined yet
- `.github/workflows/ci.yml` — no Newman job; drift gate guards `openapi.json` + `schema.d.ts`
- `apps/backend/pyproject.toml` — ruff `0.15.12`, mypy `1.20.2` already installed
- `.planning/handoff/` — existing artifact precedent (`v1.6-postman.json`, `v1.4-auth-runbook.md`, `v1.9-trainers-runbook.md`)
- `.planning/milestones/v1.10-OPERATOR-EVIDENCE.md` — append-only convention per D-62.1-B2
- `.planning/PROJECT.md` — v1.11 milestone scope, DEFER items, carry-over operator-pending list
- `.planning/RETROSPECTIVE.md` — v1.5 Phase 40 runbook staleness precedent (4 hotfixes on first execution)

### Primary (HIGH confidence — live npm registry + Docker Hub verification)

- `npm view openapi-to-postmanv2 dist-tags.latest` → `6.0.1` (2026-05-26)
- `npm view newman dist-tags.latest` → `6.2.2` (2026-05-26)
- `npm view @redocly/cli dist-tags.latest` → `2.31.4` (2026-05-26; released 2026-05-22)
- `hub.docker.com/r/axllent/mailpit` — actively maintained; MailHog archived since 2019

### Secondary (HIGH confidence — authoritative specs)

- `datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-header/` — draft-07, October 2025, Standards Track
- FastAPI docs: metadata + docs URLs, `openapi_tags`, `custom_openapi()` pattern
- Stripe idempotency design docs — 24h TTL standard, placeholder-in-flight pattern
- ЮKassa API docs — `ex=86400` webhook dedup window (basis for 24h TTL alignment)

---

*Research completed: 2026-05-26*
*Ready for roadmap: yes*
