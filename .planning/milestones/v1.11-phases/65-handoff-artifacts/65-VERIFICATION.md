---
phase: 65-handoff-artifacts
verified: 2026-05-29T10:07:27Z
status: human_needed
score: 14/14
overrides_applied: 0
human_verification:
  - test: "pnpm docs renders the clubcore API doc-site on localhost:8080"
    expected: "Redocly prints 'Preview server running ... http://localhost:8080'; browser shows 'clubcore API v1.11.0' with 10 business-domain tag groups in the sidebar; URL is localhost only (no public host)"
    why_human: "Requires starting a live server — cannot verify a rendered HTML doc-site programmatically; HND-06 Task 3 was auto-approved in autonomous mode"
  - test: "Postman GUI auth flow runs without manual header wiring"
    expected: "After importing the collection + environment, running the Login request populates csrfToken collection variable from sportzal_csrf cookie; any subsequent non-GET mutating request auto-sends X-CSRF-Token header without manual addition (visible in Postman console)"
    why_human: "Requires running docker compose up + seed fixtures + Postman GUI session; HND-02 GUI checkpoint was auto-approved in autonomous mode"
  - test: "pnpm newman run exits 0 against docker compose up with seeded fixtures"
    expected: "All 14 smoke requests pass assertions; process exits 0; idem-2 returns identical status + body to idem-1 (verbatim replay confirmed). Negative check: wrong password causes non-zero exit (--bail gates failures)"
    why_human: "Requires docker compose up + seed_verification_fixtures.py with SEED_VERIFY_OWNER_PASSWORD; HND-04 Task 2 was auto-approved in autonomous mode"
---

# Phase 65: Handoff Artifacts Verification Report

**Phase Goal:** The v2.0 frontend integration team receives a complete, usable handoff package — a Postman v2.1 collection with auth scripts and test assertions, a Newman smoke harness, a `clubcore-auth-runbook.md` covering all auth flows and `Idempotency-Key` semantics, and a private local doc-site — all generated from the post-Phase-66 frozen spec.
**Verified:** 2026-05-29T10:07:27Z
**Status:** human_needed — all automated truths VERIFIED; 3 live-stack behaviors require human confirmation
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Postman v2.1 collection exists at the locked path and validates as schema v2.1.0 | VERIFIED | `info.schema = "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"` confirmed in committed JSON |
| 2 | Requests grouped under 11 domain folders; `Internal` folder absent | VERIFIED | `collection.item` = Auth, Users, Clients, Memberships, Visits, Schedule, Bookings, Trainers, Payments, Reports, Audit-log (11 folders + smoke); no `Internal` folder |
| 3 | Login request extracts `sportzal_csrf` into `csrfToken` collection variable; no `cc_access`/`cc_refresh` anywhere | VERIFIED | Auth folder Login test script: `pm.cookies.get("sportzal_csrf")` → `pm.collectionVariables.set("csrfToken", ...)` confirmed; `cc_access` absent, `cc_refresh` absent |
| 4 | Collection-level pre-request injects `X-CSRF-Token` on every non-GET request | VERIFIED | Collection-level `event[listen=prerequest]` script confirmed: `if (pm.request.method !== 'GET') { pm.request.headers.add({ key: 'X-CSRF-Token', value: csrf }) }` |
| 5 | Every request has a status assertion; ≥11 body-shape `pm.test()` assertions | VERIFIED | 113 `pm.response.to.have.status()` assertions; 21 `pm.test()` body-shape assertions (17 required) |
| 6 | Postman environment file ships placeholder values only — no credentials | VERIFIED | `accessToken = ""`, `csrfToken = ""`, `baseUrl = "http://localhost:8000"`; regex check for `@local.dev`, `password`, `verify_owner` passes clean |
| 7 | Newman smoke env commits fixture email only, empty password placeholder | VERIFIED | `ownerEmail = "verify_owner@local.dev"`, `password = ""` (type: secret) |
| 8 | Collection has a `smoke` folder with 14 curated requests including idempotency replay; no refund/sell | VERIFIED | `smoke` folder confirmed with 14 items: Login, Me, 10 domain GETs, idem-1, idem-2; `Idempotency-Key` header present in replay pair; `/refund\|sell\b/i` regex finds no match in smoke folder |
| 9 | `pnpm newman run` script has `--folder smoke`, `--bail`, and `--env-var "password=..."` | VERIFIED | `package.json scripts.newman` = `newman run ... --folder smoke --env-var "password=$SEED_VERIFY_OWNER_PASSWORD" --bail` (WR-01 + WR-02 from code review were fixed) |
| 10 | Root `package.json` is private, has 4 scripts, 3 exact-pinned devDeps, no forbidden scripts | VERIFIED | `"private": true`; scripts: docs, postman:gen, postman:augment, newman; devDeps: `@redocly/cli: 2.31.4`, `newman: 6.2.2`, `openapi-to-postmanv2: 6.0.1` (no caret/tilde); no build-docs/bundle/publish/deploy/pdf |
| 11 | `.docs-site/` is gitignored; no CI workflow publishes the doc-site | VERIFIED | `.gitignore` has exact line `.docs-site/` (grep -qxF confirmed); `.github/workflows/ci.yml` only — grep for preview-docs/build-docs/docs-site/gh-pages returns no matches |
| 12 | `clubcore-auth-runbook.md` exists with all 8 sections and ≥200 lines | VERIFIED | 493 lines; all 8 section headings confirmed (## 1. Login through ## 8. sportzal_csrf carry-over) |
| 13 | Runbook covers Idempotency-Key semantics: `{16,128}` format, user-scope, 24h/86400s, verbatim replay, 422 codes, Category-A list, worked replay curl | VERIFIED | `{16,128}` regex, `cc:idem:{user_id}:{method}:{path}:{key}` user-scope, `86400 секунд`, `idempotency_key_required`, `idempotency_key_reuse`, 22-endpoint Category-A table, worked replay curl all confirmed |
| 14 | Runbook documents `sportzal_csrf` carry-over with v2.0 cutover plan; `cc_access`/`cc_refresh` absent | VERIFIED | Section 8 documents D-11-CSRF-DEFER, `main.py` line references (199/428), v2.0 cutover algorithm with fallback snippet; `cc_access` and `cc_refresh` absent from runbook |

**Score:** 14/14 truths verified (automated)

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `package.json` | Private root package with 4 scripts + 3 pinned devDeps | VERIFIED | Exists, 22 lines, private: true, type: module |
| `.gitignore` | `.docs-site/` ignore entry | VERIFIED | Exact line present with D-11-DOCS-PRIVATE comment |
| `tools/newman/augment-collection.mjs` | ES module post-processor ≥80 lines | VERIFIED | 617 lines, ES module (`import` statements + `import.meta.url`), resolves paths from `import.meta` |
| `.planning/handoff/v1.11-clubcore.postman_collection.json` | Postman v2.1 collection, augmented | VERIFIED | 21,973 lines; v2.1.0 schema; 12 top-level folders (11 domain + smoke) |
| `.planning/handoff/v1.11-clubcore.postman_environment.json` | Placeholder-only GUI environment | VERIFIED | Exists; accessToken="", csrfToken="", baseUrl="http://localhost:8000"; no credentials |
| `tools/newman/clubcore-smoke.postman_environment.json` | Newman smoke env: email + empty password | VERIFIED | ownerEmail="verify_owner@local.dev", password="" (secret type) |
| `.planning/handoff/clubcore-auth-runbook.md` | Auth runbook ≥200 lines with `Idempotency-Key` | VERIFIED | 493 lines; all required content present |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `package.json scripts.docs` | `apps/backend/openapi.json` | `redocly preview-docs --port 8080` | WIRED | Script value: `redocly preview-docs apps/backend/openapi.json --port 8080` |
| `package.json scripts.newman` | `.planning/handoff/v1.11-clubcore.postman_collection.json` | `newman run -e ... --bail` | WIRED | Script value references correct collection path; has `--folder smoke`, `--bail`, `--env-var` |
| `augment-collection.mjs login test event` | `collection variable csrfToken` | `pm.cookies.get('sportzal_csrf')` | WIRED | Confirmed in Auth folder Login item test script |
| `collection-level prerequest event` | Every non-GET request | `X-CSRF-Token` header injection | WIRED | Collection-level event script confirmed; `if (pm.request.method !== 'GET')` guard |
| `augment-collection.mjs` | `tools/newman/base-collection.json` | `fs.readFileSync(INPUT)` | WIRED | INPUT path = `path.join(REPO_ROOT, 'tools', 'newman', 'base-collection.json')` |
| `runbook curl examples` | Postman collection request names | Inline pairing note per section | WIRED | 11 "Postman:" pairing notes confirmed in runbook; "Login", "Refresh", "Logout All", etc. |
| `runbook Idempotency-Key section` | Category-A endpoint list | `v1.11-idempotency-audit.md` reference | WIRED | Section 7.7 cites the audit file; 22-row table present |

---

### Data-Flow Trace (Level 4)

Not applicable — this phase produces static committed artifacts (JSON collection, documentation, tooling scripts), not runtime application components that render dynamic data.

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Collection validates as v2.1.0 | `node -e "require('.planning/handoff/...');..."` | schema = `v2.1.0/collection.json` | PASS |
| 11 domain folders, no Internal | `node` script checking `collection.item` | 11 domain folders + smoke; no Internal | PASS |
| No cc_access / cc_refresh in collection | `node` string search | Both absent | PASS |
| ≥11 pm.test() assertions | `node` regex count | 21 pm.test() found | PASS |
| 113 status assertions | `node` regex count | 113 pm.response.to.have.status() | PASS |
| Smoke folder: 14 items, Idempotency-Key, no refund/sell | `node` script | 14 items, Idempotency-Key present, refund/sell absent | PASS |
| Newman smoke env: ownerEmail correct, password empty | `node` script | ownerEmail=verify_owner@local.dev, password="" | PASS |
| Postman env: no credentials | `node` script + regex | accessToken="", csrfToken=""; credential regex clean | PASS |
| package.json: private, 4 scripts, 3 exact devDeps, no forbidden | `node` script | All checks pass | PASS |
| .gitignore has .docs-site/ | `grep -qxF` | Found | PASS |
| No CI doc-site publish path | `grep -rEi` in .github/workflows/ | No matches | PASS |
| Runbook: 493 lines, 8 sections, all required keywords | `wc -l`, `grep -q` | All pass | PASS |
| pnpm docs — live rendering | Requires server | Cannot verify statically | SKIP (human_verification item 1) |
| Postman GUI auth flow | Requires Postman + live stack | Cannot verify statically | SKIP (human_verification item 2) |
| pnpm newman run exit 0 | Requires docker compose + seed | Cannot verify statically | SKIP (human_verification item 3) |

---

### Probe Execution

Step 7c: SKIPPED — no probe scripts declared in phase plan or SUMMARY; no `scripts/*/tests/probe-*.sh` convention applies to this handoff/tooling phase.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| HND-01 | 65-02-PLAN | Postman v2.1 collection at locked path; environment file with placeholder values only | SATISFIED | Collection at `.planning/handoff/v1.11-clubcore.postman_collection.json`, schema v2.1.0, folderStrategy=Tags (11 domain folders); environment file with baseUrl/accessToken/csrfToken as empty strings |
| HND-02 | 65-02-PLAN | Pre-request scripts: login extracts sz_access/sz_refresh/sportzal_csrf; all non-GETs auto-send X-CSRF-Token | SATISFIED (automated) / NEEDS HUMAN (GUI) | Login test script extracts sportzal_csrf → csrfToken; collection prerequest injects X-CSRF-Token; GUI confirmation is human_verification item 2 |
| HND-03 | 65-02-PLAN | Every request has status assertion; auth + 1 per domain has body-shape pm.test() | SATISFIED | 113 status assertions; 21 pm.test() body-shape assertions (≥11 required) |
| HND-04 | 65-03-PLAN | Newman smoke harness at tools/newman/; `pnpm newman run` uses --bail; documented as local-only | SATISFIED (static) / NEEDS HUMAN (live run) | Smoke env file exists with email-only; smoke folder has 14 curated requests; `--bail` + `--folder smoke` + `--env-var` in newman script; documented as "local handoff smoke — not a CI gate" in runbook §7.10; live run is human_verification item 3 |
| HND-05 | 65-04-PLAN | clubcore-auth-runbook.md covering all auth flows + Idempotency-Key semantics + v2.0 cutover | SATISFIED | 493 lines; 8 sections; all required content verified (format, user-scope, 24h window, verbatim replay, 422 codes, Category-A list, sportzal_csrf carry-over, v2.0 cutover plan) |
| HND-06 | 65-01-PLAN | Private OpenAPI doc-site via pnpm docs on port 8080; .docs-site/ gitignored; no public publish path | SATISFIED (static) / NEEDS HUMAN (live render) | Script value correct; .docs-site/ gitignored; no CI publish path; live render is human_verification item 1 |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `tools/newman/augment-collection.mjs` | 133, 436 | `pm.collectionVariables.set("accessToken", csrfCookie)` — accessToken set to CSRF cookie value (WR-03 from code review) | Warning | Misleading variable name; harmless today because no request uses `{{accessToken}}` as a Bearer header; risk if future requests wire `{{accessToken}}` to Authorization header |
| `tools/newman/augment-collection.mjs` | 175 | `extractPath` fallback doesn't filter `{{param}}` segments (IN-02 from code review) | Info | Low impact; url.raw is always populated by current generator version; fallback silently wrong only if generator changes |
| `tools/newman/augment-collection.mjs` | 138 | `report` shape asserts only `items`, not `total` like list shape (IN-03 from code review) | Info | Minor under-specification; could use `list` shape if endpoint follows standard pagination envelope |

No `TBD`, `FIXME`, or `XXX` markers found in any phase-65 modified file.

**Code review WR-01 and WR-02 were fixed post-review:** `package.json scripts.newman` now includes `--folder smoke` and `--env-var "password=$SEED_VERIFY_OWNER_PASSWORD"` as confirmed in the current committed state.

---

### Human Verification Required

#### 1. pnpm docs — Redocly Preview Server on Port 8080

**Test:** From the repo root, run `pnpm docs`. Wait for Redocly to print "Preview server running ... http://localhost:8080". Open `http://localhost:8080` in a browser.
**Expected:** Page renders the clubcore API reference: title "clubcore API" version 1.11.0; 10 business-domain tag groups visible in left sidebar (Auth, Users, Clients, Memberships, Visits, Schedule, Bookings, Trainers, Payments, Reports/Audit-log; Internal may also appear for local private doc-site); URL is localhost only — no public host. Stop with Ctrl-C.
**Why human:** Starting a live server and visually confirming a rendered HTML doc-site is not verifiable by static code inspection. The binaries are confirmed installed (`@redocly/cli 2.31.4` in devDependencies; pnpm install confirmed in SUMMARY-01); the script value is `redocly preview-docs apps/backend/openapi.json --port 8080` (correct). HND-06 Task 3 was auto-approved in autonomous mode.

#### 2. Postman GUI Auth Flow — CSRF Auto-Wiring

**Test:** Prerequisites: `docker compose up` in `apps/backend`; run `apps/backend/scripts/seed_verification_fixtures.py` with `SEED_VERIFY_OWNER_PASSWORD` exported.
1. Import `.planning/handoff/v1.11-clubcore.postman_collection.json` and `.planning/handoff/v1.11-clubcore.postman_environment.json` into Postman; select the environment.
2. Run the Login request with body `{"email":"verify_owner@local.dev","password":"<seeded password>"}`. Expect 200.
3. Confirm `csrfToken` collection variable is now populated (Postman Variables panel).
4. Run any non-GET mutating request (e.g., a Memberships POST). Confirm in the Postman console that `X-CSRF-Token` was sent automatically without manual addition. A 422/404 business-logic error is acceptable — you are verifying CSRF wiring, not payload.
**Expected:** Login populates csrfToken; non-GET requests auto-send X-CSRF-Token header.
**Why human:** Requires Postman GUI + running backend + seeded fixtures. The collection scripts are statically verified correct (sportzal_csrf extraction wired, X-CSRF-Token prerequest wired), but end-to-end GUI behavior is unverifiable programmatically. HND-02 Task 3 was auto-approved in autonomous mode.

#### 3. Newman Smoke Run — Live Stack Exit 0 + --bail Negative Check

**Test:** Prerequisites: `docker compose up` in `apps/backend`; seed `seed_verification_fixtures.py` with `SEED_VERIFY_OWNER_PASSWORD` exported.
1. From repo root: `SEED_VERIFY_OWNER_PASSWORD=<password> pnpm newman`
2. Confirm all 14 requests pass assertions; process exits 0 (`echo $?` → 0).
3. Confirm idem-2 output shows identical status + body to idem-1 (verbatim replay).
4. Negative check: `SEED_VERIFY_OWNER_PASSWORD=wrong pnpm newman` → confirm non-zero exit (Login 401, Newman stops via --bail).
**Expected:** Exit 0 with correct password; non-zero with wrong password.
**Why human:** Requires live docker compose stack + seeded fixtures. The smoke harness is statically verified (14 requests, Idempotency-Key in replay pair, --bail flag, --env-var password passthrough). HND-04 Task 2 was auto-approved in autonomous mode.

---

### Gaps Summary

No gaps — all 14 automated truths are VERIFIED. The 3 human verification items are live-stack behaviors that are statically correct (scripts, collection JSON, env files all verified) but require a running `docker compose` + seeded fixtures to confirm end-to-end execution. The code review WR-03 warning (accessToken = csrfCookie) is a pre-existing code smell carried forward from review, not a blocker.

---

_Verified: 2026-05-29T10:07:27Z_
_Verifier: Claude (gsd-verifier)_
