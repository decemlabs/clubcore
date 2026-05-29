---
phase: 64-contract-freeze-openapi-curation
verified: 2026-05-29T00:00:00Z
status: passed
score: 8/8 must-haves verified
overrides_applied: 0
re_verification: false
---

# Phase 64: Contract Freeze — OpenAPI Curation Verification Report

**Phase Goal:** Curated OpenAPI spec under the clubcore name — correct info.*, servers, securitySchemes, explicit operation IDs, tags for 10+ domains, shared components.responses; Redocly lint added as the 7th CI gate; baseline tag committed (FRZ-01..08).
**Verified:** 2026-05-29T00:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | openapi.json info.title equals "clubcore API", version "1.11.0", description populated, no contact/license | VERIFIED | `spec['info'] = {title: 'clubcore API', version: '1.11.0', description: non-empty (717 chars), no contact, no license}` |
| 2 | servers[] contains exactly one entry: {url: http://localhost:8000, description: Local dev} | VERIFIED | `spec['servers'] = [{'description': 'Local dev', 'url': 'http://localhost:8000'}]` — one entry |
| 3 | All 103 operationIds are unique and contain no _api_v1_ substring | VERIFIED | `total: 103, bad (contain _api_v1_): [], duplicates: []` |
| 4 | Top-level spec.tags lists exactly 12 entries in the locked order | VERIFIED | `['Auth', 'Users', 'Clients', 'Memberships', 'Visits', 'Schedule', 'Bookings', 'Trainers', 'Payments', 'Reports', 'Audit-log', 'Internal']` — 12 entries, correct order |
| 5 | No operation has duplicate tags; no operation falls into a "default" folder | VERIFIED | `duplicate-tag ops: 0; ops without tags: 0` |
| 6 | spec.components.securitySchemes has cookieAuth (sz_access) + csrfHeader (X-CSRF-Token); sportzal_csrf annotation present; global security set; public endpoint opt-outs active | VERIFIED | cookieAuth.name=sz_access (CR-01 fixed); csrfHeader.name=X-CSRF-Token; sportzal_csrf in description; D-11-CSRF-DEFER cited; global security=[{cookieAuth:[], csrfHeader:[]}]; 10 public endpoints have security=[] |
| 7 | spec.components.responses has exactly 6 keys; all inline 401/403/404/409/422/429 responses migrated to $ref | VERIFIED | keys: ['401_Unauthorized','403_Forbidden','404_NotFound','409_Conflict','422_ValidationError','429_RateLimited']; inline-response offenders: 0 |
| 8 | redocly.yaml exists with extends: [recommended]; npx @redocly/cli lint exits 0; redocly-lint CI job is parallel (no needs:); annotated tag contract-freeze-v1.11.0 exists; CHANGELOG.md has all 8 FRZ-* entries; FRZ-08 paths corrected in REQUIREMENTS.md | VERIFIED | All sub-checks pass (see detailed sections below) |

**Score:** 8/8 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/app/main.py` | FastAPI constructor with curated info{} + servers[] + openapi_tags + generate_unique_id_function + security post-processor | VERIFIED | All kwarg additions confirmed at lines 81, 102, 132, 202, 230, 259, 377–400, 604–644 |
| `apps/backend/openapi.json` | Regenerated curated spec (byte-stable) | VERIFIED | Drift gate green: `git diff --exit-code` exits 0 after fresh regen |
| `packages/api-client/src/schema.d.ts` | Regenerated TypeScript bindings | VERIFIED | Byte-stable; codegen produces no diff vs committed file |
| `apps/backend/app/core/openapi_responses.py` | OPENAPI_ERROR_RESPONSES with 6 keys | VERIFIED | File exists; all 6 keys present; mypy strict + ruff green |
| `redocly.yaml` | Repo-root lint config with extends: [recommended] | VERIFIED | File exists with extends: [recommended]; documented rule overrides with trade-off comments |
| `.github/workflows/ci.yml` | 7th parallel job redocly-lint | VERIFIED | Job exists, no needs: key, runs npx @redocly/cli@latest lint apps/backend/openapi.json |
| `packages/api-client/CHANGELOG.md` | Keep-a-Changelog v1.1 with v1.11.0 Contract Freeze entry | VERIFIED | All 8 FRZ-* IDs present; D-11-CSRF-DEFER and D-11-DOCS-PRIVATE cited; Notes section present |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `app/main.py FastAPI(...)` | `openapi.json info{} + servers[]` | `scripts/export_openapi.py` | WIRED | title="clubcore API", version="1.11.0", servers=[{localhost:8000}] confirmed in spec |
| `app/main.py custom_unique_id` | `FastAPI(generate_unique_id_function=...)` | FastAPI hook | WIRED | `generate_unique_id_function=custom_unique_id` at line 400; 103 clean IDs in spec |
| `app/main.py OPENAPI_TAGS` | `FastAPI(openapi_tags=...)` | FastAPI kwarg | WIRED | `openapi_tags=OPENAPI_TAGS` at line 399; 12 ordered tags in spec |
| `app/modules/*/router.py APIRouter(tags=[...])` | `openapi.json operation.tags` | FastAPI auto-derivation | WIRED | All 16 module routers have explicit tags; aggregator has no tags= on include_router calls (only comment) |
| `SECURITY_SCHEMES + PUBLIC_ENDPOINT_OPERATION_IDS` | `openapi.json securitySchemes + security + per-op` | `_customize_openapi()` assigned to `app.openapi` | WIRED | sz_access, X-CSRF-Token confirmed; 10 public ops have security=[]; global security set |
| `OPENAPI_ERROR_RESPONSES` | `openapi.json components.responses + $ref` | `_customize_openapi()` extended | WIRED | 6 shared responses in spec; 0 inline offenders for 401/403/404/409/422/429 |
| `redocly.yaml` | `apps/backend/openapi.json` | `npx @redocly/cli lint` | WIRED | Lint exits 0 ("Your API description is valid") |
| `.github/workflows/ci.yml redocly-lint` | `redocly.yaml + openapi.json` | GitHub Actions parallel job | WIRED | Job exists with no needs: dependency |
| Annotated tag `contract-freeze-v1.11.0` | HEAD commit | `git tag -a` | WIRED | `git cat-file -t` returns `tag`; tag message references all FRZ-01..08 |

### Data-Flow Trace (Level 4)

Not applicable — this phase produces static JSON spec artifacts and configuration files, not dynamic data-rendering components.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| openapi.json info.title is "clubcore API" | `python3 -c "import json;spec=json.load(open('apps/backend/openapi.json'));assert spec['info']['title']=='clubcore API'"` | Exit 0 | PASS |
| 103 operation IDs, none contain _api_v1_, none duplicated | `python3 -c "import json,collections;spec=json.load(open('apps/backend/openapi.json'));ids=[op['operationId'] for p in spec['paths'].values() for op in p.values() if isinstance(op,dict) and 'operationId' in op];assert not any('_api_v1_' in i for i in ids) and len(ids)==len(set(ids))"` | Exit 0 | PASS |
| Drift gate green after fresh regen | `cd apps/backend && uv run python -m scripts.export_openapi && git diff --exit-code apps/backend/openapi.json packages/api-client/src/schema.d.ts` | Exit 0 | PASS |
| Redocly lint exits 0 | `npx -y @redocly/cli@latest lint apps/backend/openapi.json` | "Your API description is valid" | PASS |
| cookieAuth.name == sz_access (CR-01 fix verified) | `python3 -c "import json;spec=json.load(open('apps/backend/openapi.json'));assert spec['components']['securitySchemes']['cookieAuth']['name']=='sz_access'"` | Exit 0 | PASS |
| 6 shared components.responses; 0 inline error offenders | `python3 -c "import json;spec=json.load(open('apps/backend/openapi.json'));r=spec['components']['responses'];assert set(r)=={'401_Unauthorized','403_Forbidden','404_NotFound','409_Conflict','422_ValidationError','429_RateLimited'}"` | Exit 0 | PASS |
| Annotated tag exists | `git cat-file -t contract-freeze-v1.11.0` | Returns "tag" | PASS |
| Backend test suite green | `uv run pytest tests/ -q --tb=no` | 2185 passed, 6 skipped | PASS |

### Probe Execution

Step 7c: SKIPPED — no conventional probe scripts under `scripts/*/tests/probe-*.sh` discovered. The behavioral spot-checks above cover the equivalent verification surface.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| FRZ-01 | 64-01-PLAN | info.title="clubcore API", version="1.11.0", description populated; byte-stable regen | SATISFIED | spec verified; drift gate green |
| FRZ-02 | 64-02-PLAN | 102+ operation IDs cleaned via generate_unique_id_function suffix-strip | SATISFIED | 103 IDs, none contain _api_v1_, none duplicated |
| FRZ-03 | 64-03-PLAN | Explicit openapi_tags with 12 domains; every router declares tags=[]; no default folder | SATISFIED | 12 tags in order; 0 stray-default ops; aggregator tags= dropped (comment only) |
| FRZ-04 | 64-01-PLAN | info{} complete; servers[] with localhost dev entry; contact/license omitted | SATISFIED | servers=[{localhost:8000}]; no contact/license in spec |
| FRZ-05 | 64-04-PLAN | securitySchemes (cookieAuth sz_access + csrfHeader); sportzal_csrf documented; public opt-outs | SATISFIED | sz_access (CR-01 fixed); sportzal_csrf+D-11-CSRF-DEFER in description; 10 public ops with security=[] |
| FRZ-06 | 64-05-PLAN | 6 shared components.responses; $ref migration at all 401/403/404/409/422/429 callsites | SATISFIED | 6 keys confirmed; 0 inline offenders |
| FRZ-07 | 64-06-PLAN | redocly.yaml at repo root; lint exits 0; 7th parallel CI gate | SATISFIED | File exists; lint clean; ci.yml job verified parallel |
| FRZ-08 | 64-07-PLAN | Annotated tag contract-freeze-v1.11.0; CHANGELOG.md with all FRZ-*; REQUIREMENTS.md paths fixed | SATISFIED | Tag type=tag; all 8 FRZ-* in CHANGELOG; stale admin-web paths removed from REQUIREMENTS.md |

**Orphaned requirements:** FRZ-01 through FRZ-04 show `[ ]` (unchecked) in the REQUIREMENTS.md requirements section and "Pending" in the traceability table. However, the ROADMAP.md marks Phase 64 as `[x]` (completed 2026-05-28) and the implementations are fully present in the codebase. This is a documentation update gap in REQUIREMENTS.md — the checkbox state does not reflect execution reality. It is not a code gap.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `packages/api-client/CHANGELOG.md` | FRZ-05 bullet | Says "cc_access httpOnly cookie" but actual spec has sz_access post-CR-01 | INFO | Documentation inaccuracy — spec and tag message are correct (sz_access); CHANGELOG was drafted before CR-01 fix |
| `.planning/REQUIREMENTS.md` | Lines 29-32, 137-140 | FRZ-01/02/03/04 checkboxes unchecked `[ ]` and traceability table shows "Pending" despite implementation being complete | INFO | Documentation gap — ROADMAP.md correctly marks Phase 64 complete; no code impact |

No `TBD`, `FIXME`, or `XXX` markers found in any files modified by this phase.

### Human Verification Required

None. All must-haves are programmatically verifiable and verified.

### Gaps Summary

No gaps. All 8 FRZ-* requirements are implemented and verified against the codebase.

The two INFO-level documentation items noted above (CHANGELOG FRZ-05 cookie name pre-CR-01 wording, and REQUIREMENTS.md unchecked checkboxes for FRZ-01..04) are non-blocking informational findings. The codebase correctly reflects the post-CR-01 state (sz_access); the REQUIREMENTS.md checkbox gap does not affect code or downstream consumers.

---

_Verified: 2026-05-29T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
