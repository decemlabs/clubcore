# Feature Research

**Domain:** API Handoff + Production Hardening for single-gym CRM backend (v1.11)
**Researched:** 2026-05-26
**Confidence:** HIGH — domain is well-defined infrastructure work (no new business features); patterns sourced from current codebase inspection + Stripe/Redocly/OpenAPI canonical references

---

## Context: What v1.11 Is and Is Not

v1.11 is a zero-new-business-feature milestone. Every "feature" below is infrastructure plumbing,
documentation quality, or operator verification. The frontend integration team (v2.0) is the
downstream consumer of every artifact produced here.

**Current state entering v1.11 (confirmed by codebase inspection):**
- 81 OpenAPI paths, 104 route operations across 18 tags
- 57 mutating endpoints (POST/PATCH/DELETE); 0 have `Idempotency-Key` documented in the OpenAPI spec
- `app/core/idempotency.py` exists: `verify_idempotency` Depends, `begin_idempotency`, `store_idempotency_response`, `idempotent_response`. TTL currently 3600s (1h), Redis prefix `cc:idem:`.
- 8 route files use `verify_idempotency`: `pt_sessions`, `schedule`, `pt_packages`, `bookings`, `online_payments` — covering financial + scheduling mutations. Auth, clients, memberships sell/cancel, trainers, users, visits, payroll do NOT.
- `app/main.py` FastAPI title = `"Sportzal API"`, version = `"1.1.0"`, no `servers`, no `securitySchemes`, no `info.contact/license/description` — default auto-gen spec.
- Auto-generated `operationId` values follow FastAPI's `{function_name}{path_slug}{method}` pattern (e.g. `login_api_v1_auth_login_post`) — verbose, unstable, consumer-unfriendly.
- Existing handoff artifacts: `v1.4-auth-runbook.md`, `v1.6-postman.json` (Sportzal-branded, pre-rebrand), `v1.8-reports-runbook.md`, `v1.9-trainers-runbook.md` (operator-pending).
- `v1.10-OPERATOR-EVIDENCE.md` is the canonical append-only evidence file; v1.11 RUN-01..06 append there.
- Ruff: 79 check errors + 205 format files pending. mypy: attr-defined warnings pending. (DEFER-46-04).

---

## Feature Landscape: v1.11 Capabilities

Capabilities are organized by phase. Each entry carries complexity (S/M/L) and
Table Stakes / Differentiator / Anti-Feature designation.

---

### Phase 63 — Tech-Debt Sweep

#### Table Stakes (must close before contract-freeze artifacts)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `ruff check` exit 0 (DEFER-46-04) | CI gate was parked for 3 milestones; a spec with linting errors cannot credibly claim production-ready | S | 79 known errors; mostly stylistic. `uv run ruff check` baseline. |
| `ruff format` applied (DEFER-46-04) | Byte-stable `openapi.json` regen requires deterministic code formatting | S | 205 files. Activate as CI gate AFTER applying. |
| `mypy --strict` clean (DEFER-46-04) | Strict-typed codebase with attr-defined warnings is inconsistent branding to handoff consumers reading the README | S | Only attr-defined class; not new `ignore` lines. |
| v1.5 `run.sh` runbook hardened (DEFER-40-01) | DEFER-40-01 has been carried 3 milestones; Phase 67 operator walkthrough requires a working v1.5 verification script | M | 4 documented bugs in the script: RBAC actor, X-CSRF-Token header, table name. Fix + end-to-end clean. |
| DEFER-36-04-B residual closed | Same formatting wave as DEFER-46-04; 123 files from v1.4 era | S | Rolled into the ruff format pass. |

#### Differentiators (do-if-trivial in Phase 63)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Add `ruff format` + `ruff check` as blocking CI gate | Future milestones cannot re-accumulate debt | S | One-liner addition to CI workflow after the sweep. Worth doing. |

#### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Suppress mypy warnings with `# type: ignore` | Fastest path to green | Creates debt at exactly the moment a handoff consumer inherits the codebase | Fix the underlying attr-defined issue properly |
| Run ruff with `--select` subset to avoid fixing everything | Faster | Leaves the CI bar lower than claimed | Apply full `ruff check` as configured in `pyproject.toml` |

---

### Phase 64 — Contract Freeze (OpenAPI Curation)

#### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Explicit `operation_id=` on all 104 business operations | Auto-gen IDs like `login_api_v1_auth_login_post` are verbose and break on refactor; consumers generate SDK clients from operationId | M | Naming convention: `verb_resource` snake_case (e.g. `auth_login`, `clients_list`, `memberships_sell`). FastAPI `@router.post(..., operation_id="auth_login")`. |
| `title` updated to `"clubcore API"` | Spec was authored under `"Sportzal API"` title — all handoff docs generated from it will carry the wrong name | S | `FastAPI(title="clubcore API", version="1.11.0", ...)` |
| `version` bumped to `"1.11.0"` | Downstream consumers (Postman, SDK generators) key on version for changelog tracking | S | Must match package.json `@clubcore/api-client` version bump. |
| `info.description` populated | Tells consumers what the API is, auth model, and base URL; currently absent | S | 3-4 sentences: gym CRM, JWT cookie auth + CSRF, RU/CIS region. |
| `servers` array populated | Without servers the spec defaults to relative URL `/`; Postman env variables cannot auto-populate from spec | S | At minimum: `http://localhost:8000` (dev). Placeholder `https://api.{your-domain}.ru` for staging/prod. |
| `securitySchemes` defined | Currently absent; spec consumers cannot understand the auth model. Cookie-based JWT + CSRF is non-standard enough to require documentation. | M | OAS3 `apiKey` type for the `sz_access` cookie + separate `apiKey` for `X-CSRF-Token` header. Or `http: {scheme: bearer}` for access + `apiKey` for CSRF. Route-level `security:` annotations on all non-anonymous endpoints. |
| Explicit `tags=[...]` with `app.openapi_tags` ordering | Tags exist (`v1/router.py` assigns them) but tag order in the spec is arbitrary; Redocly/Stoplight render tags in declaration order | S | Add `openapi_tags=[{"name": "auth"}, {"name": "clients"}, ...]` to `FastAPI(...)`. 18 existing tags; consider merging `pt-package-plans` + `pt-packages` under `pt-packages` or keeping granular — decide and freeze. |
| `components.responses` shared error envelopes | Currently every 422/401/403/404/409 response is inlined per-operation. Deduplication makes the spec 20-30% smaller and enables consumers to write shared error-handling middleware. | M | Define at minimum: `Error401`, `Error403`, `Error404`, `Error409`, `Error422UnprocessableEntity`. Reference via `$ref: '#/components/responses/Error401'`. |
| Pre-freeze drift gate baseline | CI must fail if `openapi.json` is out of sync with the codebase after the freeze | S | `python -c "from app.main import create_app; ..."` export script already exists; `git diff --exit-code openapi.json` as CI step. Already partially in place — tighten the gate to treat any diff as a breaking error. |
| `@clubcore/api-client` version bump to `1.11.0` | Frontend consumers pin to a version; bumping signals the freeze | S | `package.json` version field + `CHANGELOG.md` baseline entry. |

#### Differentiators (do-if-trivial)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| `info.contact` (email + support URL) | Tells handoff consumers who to contact when the spec seems wrong | S | `contact: {"name": "clubcore backend", "email": "andre.shipunov@icloud.com"}` |
| `components.parameters.PageParam`, `PageSizeParam`, `SortParam` | Recurring pagination params documented once; reduces copy-paste in spec | S | Only worth doing if 5+ endpoints share the same `page`/`page_size` query params — audit first. |
| `x-clubcore-rbac` extension on owner-only operations | Machine-readable RBAC hints; useful for future codegen | S | `x-clubcore-rbac: {roles: ["owner"]}` on all OWNER_ONLY paths. Very low effort. |
| `deprecated: true` markers on any legacy alias paths | Documents intentional deprecation for consumers | S | Check if any `/api/v1/auth/sessions/revoke` vs `/api/v1/auth/sessions/{family_id}/revoke` legacy patterns exist. |

#### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Publishing the spec to a public URL (GitHub Pages, Redocly Cloud, public npm) | Easier sharing | This is a private commercial CRM — the API surface reveals business logic, RBAC structure, and endpoint URLs of a commercial system. Publishing = security and business risk. | Private gitignored doc-site (Phase 65) + share via encrypted channel with the design team |
| Restructuring route prefixes during curation | Makes spec "cleaner" | Any URL change is a **breaking change** after freeze; the frontend team builds against the frozen URLs | Freeze URLs as-is; document known "ugly" URLs in the spec description |
| Merging `_internal` routes into the business spec | Webhooks are documented for completeness | `_internal` routes (email webhook, ЮKassa webhook) are server-to-server; including them in the handoff spec confuses frontend developers and leaks infrastructure details | Tag `_internal` routes with `x-internal: true`; exclude from Postman collection (already precedent from v1.6 Postman) |

---

### Phase 65 — Handoff Artifacts

#### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Curated Postman v2.1 collection (full surface) | Frontend integration team needs a runnable collection to validate their HTTP client setup | L | Cover all 18 tag domains (not just auth). Folder per tag. Auth happy-path at the top as a setup folder (login → capture cookie + CSRF into env variables via `pm.test` + `pm.environment.set`). ENV templates: `clubcore-local.postman_environment.json` (`baseUrl=http://localhost:8000`). |
| Pre-request auth script pattern | Without it, every request in the collection would require manual cookie pasting | M | Collection-level pre-request: if `{{accessToken}}` is absent, execute `POST /api/v1/auth/login`, then extract `Set-Cookie: sz_access` → `pm.environment.set("accessToken", ...)` and extract `sportzal_csrf` cookie → `pm.environment.set("csrfToken", ...)`. Mutating requests send `X-CSRF-Token: {{csrfToken}}`. |
| Test scripts (status code + schema shape per request) | v1.6 Postman had 74 items with no test assertions; fails silently | M | Each request gets at minimum `pm.test("Status 200", () => pm.response.to.have.status(200))` + `pm.test("has data key", () => pm.expect(pm.response.json()).to.have.property("data"))`. |
| Newman CLI smoke integration | CI-runnable (exit non-zero on fail); the single script the design team can run to verify the backend is alive | M | `npx newman run clubcore-collection.json -e clubcore-local.json --reporters cli,junit --reporter-junit-export newman-results.xml`. Cover at minimum: auth login → CSRF capture → clients list → memberships list → visits list → health. ~10 requests. |
| `clubcore-auth-runbook.md` (expanded, clubcore-branded) | `v1.4-auth-runbook.md` was written under the Sportzal name + does not cover Telegram OTP, refresh rotation, multi-user invite, password-reset, or CSRF flow | M | Supersede `v1.4-auth-runbook.md`. Add: (a) CSRF header extraction one-liner `CSRF=$(awk '/sportzal_csrf/ {print $7}' cookies.txt)`; (b) JWT decode via `python3 -c "import base64, json, sys; [print(json.loads(base64.b64decode(p+'==').decode())) for p in sys.argv[1].split('.')[0:2]]"`; (c) Telegram OTP flow (start → status poll → verify); (d) refresh rotation manual test; (e) invite + accept flow; (f) password-reset flow. |
| Private OpenAPI doc-site via Redocly CLI | Design team needs browseable, searchable API docs — not raw JSON | M | `npx @redocly/cli preview-docs apps/backend/openapi.json` (port 8080). Add `make docs` target. Add `docs/` output to `.gitignore`. Do NOT publish to any public URL. |

#### Differentiators (do-if-trivial)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| `Makefile` target `make docs` (wraps Redocly preview) | One command for new team members | S | `docs: npx @redocly/cli preview-docs apps/backend/openapi.json --port 8080` |
| `Makefile` target `make smoke` (wraps Newman) | One command for integration validation | S | `smoke: npx newman run ...` |
| Postman folder for idempotency testing (duplicate-request pairs) | Shows consumers how Idempotency-Key works in practice | S | Two-request folder: original sale + identical replay → same 200 body. |
| Code samples in spec `x-codeSamples` | Redocly renders curl/Python/TypeScript samples in the doc-site | M | Moderate effort but high DX value; worth doing for the 5 most-used endpoints (login, clients list, memberships sell, visits check-in, reports). |

#### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Publishing doc-site to Redocly Cloud / GitHub Pages / any public URL | Easy sharing | Private commercial CRM — leaks business logic, RBAC, URL surface | Private serve via `redocly preview-docs`; share the `openapi.json` file directly over encrypted channel |
| Full collection covering all 104 operations with detailed bodies | Comprehensive coverage | Unsustainable; the collection becomes a maintenance burden larger than the code itself | Smoke 10-15 key operations; document the rest via the OpenAPI spec |
| PDF export of the doc-site | Printable docs | PDFs go stale immediately as the spec evolves; they cannot stay in sync | Direct consumers to the live local preview or the JSON spec |
| Newman as a blocking CI gate at this stage | Seems like a natural extension | Newman requires a running backend + real secrets (DB, Redis, ЮKassa sandbox) — cannot run in CI without a full docker-compose stack; adds complexity without a clear payoff at the v1.11 stage | Run Newman locally via `make smoke`; add to CI only when a staging environment exists |

---

### Phase 66 — Idempotency Hardening

#### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Full audit of 57 mutating endpoints — per-endpoint classification | Before standardizing, you need to know which endpoints are in which category | S | Three categories: (A) already uses `verify_idempotency` + `idempotent_response`, (B) needs idempotency but doesn't have it, (C) idempotency is not applicable (auth flows, reads, webhook receivers). |
| TTL extension from 3600s → 86400s (24h) | Current TTL of 1h is too short; Stripe's documented standard is 24h; ЮKassa also uses 24h per their API docs. Clients retry over longer windows (network timeouts, app restarts). | S | Single constant change in `app/core/idempotency.py:IDEMPOTENCY_TTL_SECONDS`. No Redis key migration needed (keys expire naturally). |
| `components.parameters.IdempotencyKey` in OpenAPI spec | Currently 0 endpoints document the header in the spec despite 8 route files requiring it. Downstream consumers cannot know the header is required from the spec alone. | M | Add to `components.parameters`: `IdempotencyKey: {name: Idempotency-Key, in: header, required: true, schema: {type: string, minLength: 1, maxLength: 128, pattern: "^[A-Za-z0-9_:-]{1,128}$"}}`. Add `$ref` on all endpoints that call `verify_idempotency`. |
| Integration tests for double-submit on financial endpoints | CR-02 carry-over from Phase 33 review; memberships sell, PT-package sell, online-payment sell are the highest-risk double-submit paths | M | Tests: first POST succeeds (201) → same key + same body → 200 replay with identical body. Different body → 422 `idempotency_key_reuse`. In-flight placeholder → 409 `idempotency_in_flight`. At minimum: `POST /memberships` (cash sell), `POST /pt-packages`, `POST /online-payments/memberships/{plan_id}/sell`. |
| Document idempotency semantics in `clubcore-auth-runbook.md` (CR-02b) | Consumers need to understand: which endpoints require the header, what format the key must be, what errors they get on reuse | S | Add dedicated "Idempotency-Key" section to the runbook. Cover: required format, TTL, replay semantics, `idempotency_key_reuse` vs `idempotency_in_flight` error codes. |
| Classify `POST /memberships/sell` (cash) for idempotency coverage | Currently missing — financial endpoint with no idempotency | M | Verify `memberships/router.py` `sell_membership` handler. If missing `verify_idempotency`, add it in this phase. |

#### Differentiators (do-if-trivial)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Idempotency on `POST /payroll/accruals` | Payroll accrual is financial; double-submit creates a double-payment | S | Low risk to add; mirrors existing pattern. |
| Idempotency on `POST /visits` (check-in) | Prevents double check-in on network retry | S | Already has DB-level uniqueness via `UNIQUE(client_id, gym_date)` — returns 409 on true duplicate, but the `verify_idempotency` layer provides a cleaner 200-replay instead of 409. Optional. |
| `Idempotency-Replayed: true` response header on replayed responses | Lets consumers distinguish a real 200 from a cached replay | S | Single header add in `idempotent_response` helper. Low effort, good DX. |

#### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Idempotency on all 57 mutating endpoints (blanket) | "Safer" | Auth flows (login, logout, OTP, refresh), soft-delete, status transitions are not idempotent in the traditional sense — applying the header requirement universally adds friction and breaks anti-oracle flows where the server intentionally does NOT reveal whether a prior attempt succeeded | Classify endpoints into A/B/C; only add to category-B financial + scheduling mutations |
| Changing the idempotency key format requirement to UUID-only | "Cleaner" | The current regex `[A-Za-z0-9_:-]{1,128}` is already documented in `IDEMPOTENCY_KEY_PATTERN`; the ЮKassa integration generates deterministic sha256 keys. Narrowing to UUID-only breaks existing callsites. | Keep the current regex; document the recommended format (UUIDv4) without enforcing it |
| Database persistence for idempotency keys | Redis eviction could theoretically replay a request | Adds a write to every mutating endpoint; defeats the purpose of a lightweight idempotency layer; Redis TTL 24h covers all real-world retry windows | Keep Redis-only with 24h TTL |

---

### Phase 67 — Operator-Pending Runbook Execution

#### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| RUN-01: ЮKassa sandbox walkthrough (v1.7 VER-03) | VER-03 was explicitly deferred at v1.7 close as operator-credential-gated; cannot ship a billing product without a live payment confirmation | M | Requires ЮKassa sandbox credentials in `.env`. Script `apps/backend/scripts/` (sandbox-evidence scaffolding already exists per v1.7 PROJECT.md). Evidence appended to `v1.10-OPERATOR-EVIDENCE.md` (append-only per D-62.1-B2). |
| RUN-02: RU email-deliverability probe (v1.7 CARRY-01 / DEFER-46-01) | SPF/DKIM/DMARC send-to-Gmail/Yandex `Authentication-Results` headers must be captured; fiscal receipts go to real clients | M | Requires live `CLUBCORE_EMAIL_FROM` domain provisioned. If not yet provisioned, mark `N/A-until-production` with trigger condition (same pattern as RUN-08-dns-dkim-DEFERRED). |
| RUN-03: Owner countersign on 19 locked email templates (v1.7 CARRY-02 / DEFER-46-02) | `LOCKED_EMAIL_TEMPLATES` frozenset contains 19 strings; owner must attest these are correct before production send | S | Read the template IDs from the source file + owner signature in `v1.6-template-countersign.md` (already exists, may need updating from 15 → 19 templates). Evidence: appended to operator file. |
| RUN-04: Reports runbook walkthrough (v1.8 VER-01) | `v1.8-reports-runbook.md` was authored but never executed (operator-pending per D-12). Revenue golden-path + audit-log filter + CSV download. | M | `docker compose up` → 5 scenarios. Evidence appended to `v1.10-OPERATOR-EVIDENCE.md`. |
| RUN-05: Trainers runbook walkthrough (v1.9 D-61-12) | `v1.9-trainers-runbook.md` (513 lines, 5 scenarios) was authored but never executed (operator-pending per D-61-12). | M | `docker compose up` → payroll golden-path + recurring schedule + time-off + trainer-usage report + reception-403. Evidence appended. |
| RUN-06: MailHog `--profile dev` integration (DEFER-46-05) | Email integration tests currently require real SMTP; MailHog provides a local SMTP trap for dev/CI | M | Add MailHog service to `docker-compose.yml` under `--profile dev`. `SMTP_HOST=mailhog` when profile is active. Evidence: `docker compose --profile dev up` screenshot or curl to MailHog API. |

#### Differentiators (do-if-trivial)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Consolidated operator evidence index at top of `v1.10-OPERATOR-EVIDENCE.md` | Makes the file navigable as it grows | S | Update the `## Index` section after all RUN-01..06 sections are appended. |
| One-line pass/fail verdict per scenario (not just transcript) | Makes evidence file scannable | S | Each RUN-XX section: `VERDICT: PASS/PARTIAL/FAIL` header line before the command transcript. |

#### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Screenshots as the primary evidence format | "More convincing" | Screenshots cannot be git-diffed, searched, or verified automatically; they also contain secrets (env values, email addresses) if not redacted | Captured curl transcripts as code blocks in the markdown file (existing project convention from RUN-08-local-db-smoke) |
| Faking evidence (fabricating command output) | "Faster" | This is explicitly prohibited by project convention (D-62.1-B1: "No fabricated evidence is present in this file") and undermines the entire purpose of operator verification | Execute the runbook and capture real output; if credential-gated, mark as N/A with trigger condition |
| Scattering evidence across per-phase files | "Organized by phase" | Creates N evidence files vs one append-only file; the project convention (D-62.1-B2) is explicit: append to `v1.10-OPERATOR-EVIDENCE.md` | All v1.11 RUN-01..06 evidence appends to the single `v1.10-OPERATOR-EVIDENCE.md` |

---

## Feature Dependencies

```
Phase 63 (Tech-Debt Sweep)
    └──unblocks──> Phase 64 (Contract Freeze)
                       └──unblocks──> Phase 65 (Handoff Artifacts)
                       └──unblocks──> Phase 66 (Idempotency Hardening)
                                          └──enhances──> Phase 65 (Postman idempotency folder)
                       └──unblocks──> Phase 67 (Operator Runbook — needs stable backend)

Phase 65 OpenAPI doc-site
    └──requires──> Phase 64 curated spec (doc-site sourced from openapi.json)

Phase 65 Postman collection
    └──requires──> Phase 64 explicit operation_ids + tags (folder organization)

Phase 66 `components.parameters.IdempotencyKey`
    └──requires──> Phase 64 `components` hygiene pass

Phase 67 Trainers runbook (RUN-05)
    └──requires──> DEFER-40-01 fix from Phase 63 (run.sh hardening)

Phase 67 RUN-01 (ЮKassa sandbox)
    └──requires──> Phase 65 auth runbook (documents CSRF + cookie flow needed for sandbox test)
```

### Dependency Notes

- **Phase 63 must finish before Phase 64:** The drift gate only makes sense on a clean, formatted tree. Running `ruff format` after freezing would change the spec.
- **Phase 64 must finish before Phase 65:** All handoff artifacts (Postman, doc-site, runbook) are sourced from the curated OpenAPI spec. Doing them before curation locks in the uncurated operationIds.
- **Phase 66 can run parallel with Phase 65** after Phase 64 completes. The idempotency OpenAPI parameter is added to the same spec being documented in Phase 65.
- **Phase 67 can run any time after Phase 63** cleans the runbook tooling, but is logically last since it validates everything.

---

## MVP Definition (What Phase Completion Means)

### Phase 63 closes when:
- [ ] `uv run ruff check` exits 0 (0 errors, no suppressions added)
- [ ] `uv run ruff format --check` exits 0
- [ ] `uv run mypy --strict` exits 0 with 0 warnings
- [ ] `v1.5-verification-evidence/run.sh` executes end-to-end against `docker compose up` with exit 0

### Phase 64 closes when:
- [ ] All 104 operations have explicit `operation_id=` (no auto-generated `*_api_v1_*` names)
- [ ] `info.title = "clubcore API"`, `info.version = "1.11.0"`, `info.description` populated
- [ ] `servers` array includes `http://localhost:8000`
- [ ] `securitySchemes` defines cookie auth + CSRF header scheme
- [ ] `components.responses` defines at minimum 4 shared error envelopes (401/403/404/422)
- [ ] `app.openapi_tags` defines tag order
- [ ] `git diff --exit-code openapi.json` passes in CI

### Phase 65 closes when:
- [ ] Postman v2.1 collection file exists at `.planning/handoff/clubcore-v1.11.postman_collection.json` with auth pre-request script + test assertions
- [ ] `clubcore-local.postman_environment.json` exists
- [ ] Newman smoke (`make smoke`) runs 10+ requests with exit 0 against local stack
- [ ] `clubcore-auth-runbook.md` replaces `v1.4-auth-runbook.md` with all 6 expanded scenarios documented
- [ ] `make docs` (Redocly preview) starts without errors; `docs/` in `.gitignore`

### Phase 66 closes when:
- [ ] Per-endpoint idempotency classification table exists (A/B/C)
- [ ] `IDEMPOTENCY_TTL_SECONDS = 86400` (24h)
- [ ] `components.parameters.IdempotencyKey` defined in spec; `$ref` on all category-A/B endpoints
- [ ] Double-submit integration tests pass for 3 financial endpoints
- [ ] Idempotency section in `clubcore-auth-runbook.md`

### Phase 67 closes when:
- [ ] All 6 RUN items have evidence appended to `v1.10-OPERATOR-EVIDENCE.md`
- [ ] Any credential-gated items (RUN-02 email delivery if domain not provisioned) have explicit `N/A-until-production` rows with documented trigger conditions
- [ ] No `OPERATOR-PENDING` markers remain in the repo without a corresponding evidence section or explicit deferral

---

## Feature Prioritization Matrix

| Feature | Consumer Value | Implementation Cost | Priority |
|---------|----------------|---------------------|----------|
| Explicit operation_ids (FRZ-04) | HIGH — SDK generators break on auto-gen names | MEDIUM | P1 |
| CSRF + cookie securitySchemes (FRZ-05) | HIGH — undocumented auth model blocks integration | MEDIUM | P1 |
| Postman pre-request auth script (HND-01) | HIGH — collection is unusable without it | MEDIUM | P1 |
| Idempotency TTL 24h (IDM-02) | HIGH — 1h TTL causes spurious replay failures | LOW | P1 |
| Tech-debt sweep ruff/mypy (DEBT-01..03) | HIGH — prerequisite for stable spec generation | LOW | P1 |
| `components.parameters.IdempotencyKey` (IDM-04) | MEDIUM — spec consumers need this documented | MEDIUM | P1 |
| Newman smoke (HND-02) | MEDIUM — validation tool for integration team | MEDIUM | P1 |
| Private Redocly doc-site (HND-04) | MEDIUM — browseable alternative to raw JSON | LOW | P2 |
| ЮKassa sandbox RUN-01 | MEDIUM — billing validation | MEDIUM | P2 |
| RU email deliverability RUN-02 | MEDIUM — production readiness | MEDIUM — depends on domain | P2 |
| Double-submit integration tests (IDM-03) | MEDIUM — regression protection | MEDIUM | P2 |
| `info.contact`, `x-clubcore-rbac` extensions | LOW — nice-to-have for consumers | LOW | P3 |
| Code samples `x-codeSamples` | LOW — Redocly DX enhancement | MEDIUM | P3 |
| `Idempotency-Replayed` response header | LOW — consumer DX | LOW | P3 |

**Priority key:**
- P1: Must have for milestone to close
- P2: Should have; implement before milestone verification
- P3: Nice to have; do only if time permits

---

## Sources

- Current codebase inspection: `apps/backend/openapi.json` (81 paths, 104 ops, 0 shared components, auto-gen operationIds confirmed)
- `apps/backend/app/core/idempotency.py` — `IDEMPOTENCY_TTL_SECONDS = 3600`; `verify_idempotency` Depends pattern
- `apps/backend/app/main.py` — `FastAPI(title="Sportzal API", version="1.1.0")` — no servers/securitySchemes
- `.planning/milestones/v1.10-REQUIREMENTS.md` — IDM-01..04, DEBT-01..05, RUN-01..06, HND-01..04, FRZ-01..05 requirement snapshot
- `.planning/milestones/v1.10-OPERATOR-EVIDENCE.md` — append-only convention per D-62.1-B2
- `.planning/handoff/v1.9-trainers-runbook.md` — existing CSRF extraction pattern `awk '/sportzal_csrf/'`
- [Stripe: Designing robust and predictable APIs with idempotency](https://stripe.com/blog/idempotency) — POST-only scope, 24h TTL, placeholder-in-flight pattern
- [Stripe API: Idempotent requests](https://docs.stripe.com/api/idempotent_requests) — scope to POST, key format, TTL
- [FastAPI: Metadata and Docs URLs](https://fastapi.tiangolo.com/tutorial/metadata/) — `openapi_tags`, `info.contact`, `info.license`
- [Redocly CLI commands](https://redocly.com/docs/cli/commands) — `preview-docs`, `bundle` commands
- [Redocly CLI preview-docs](https://redocly.com/docs/cli/v1/commands/preview-docs) — `npx @redocly/cli preview-docs`, default port 8080

---
*Feature research for: v1.11 API Handoff + Production Hardening (clubcore gym CRM)*
*Researched: 2026-05-26*
