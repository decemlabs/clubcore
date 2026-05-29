---
phase: 65-handoff-artifacts
plan: "02"
subsystem: handoff-tooling
tags: [postman, collection, augment, newman, csrf, auth]
dependency_graph:
  requires: [65-01]
  provides: [v1.11-postman-collection, postman-environment, augment-script]
  affects: [65-03, 65-04]
tech_stack:
  added: []
  patterns:
    - "openapi-to-postmanv2@6.0.1 folderStrategy=Tags base generation"
    - "ES module post-processor (augment-collection.mjs) for byte-stable collection augmentation"
    - "Postman v2.1 pm.* API: collection vars, events, prerequest/test scripts"
key_files:
  created:
    - tools/newman/augment-collection.mjs
    - .planning/handoff/v1.11-clubcore.postman_collection.json
    - .planning/handoff/v1.11-clubcore.postman_environment.json
  modified: []
decisions:
  - "D-65-AUGMENT: All collection transformations scripted in augment-collection.mjs; no hand-edits to generated JSON"
  - "Cookie names confirmed: sz_access/sz_refresh/sportzal_csrf (not cc_access/cc_refresh per CONTEXT.md)"
  - "Deduplication of Reports/reports folders added as augment step (Rule 1 fix for generator bug)"
metrics:
  duration: "~20min"
  completed: "2026-05-29"
  tasks_completed: 3
  files_modified: 3
---

# Phase 65 Plan 02: Postman Collection Augmentation and Environment Summary

Generated the curated Postman v2.1 collection from the frozen `apps/backend/openapi.json` via `openapi-to-postmanv2@6.0.1`, then augmented it with a committed Node post-processor that injects auth/CSRF wiring (HND-02) and test assertions (HND-03), plus a placeholder-only Postman environment (HND-01).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | augment-collection.mjs (Internal removal, vars, login extraction, CSRF prerequest, status assertions) | 3ab21269 | tools/newman/augment-collection.mjs, .planning/handoff/v1.11-clubcore.postman_collection.json |
| 2 | Per-domain body-shape pm.test() + placeholder Postman environment | 6180d530 + ea3a1f2f | .planning/handoff/v1.11-clubcore.postman_environment.json, collection refreshed |
| 3 | Verify auth flow in Postman GUI (checkpoint:human-verify — auto-approved) | — | see Manual verification required below |

## Artifact Verification

All automated checks passed:

- Collection `info.schema` contains `v2.1.0/collection.json`
- No top-level folder named `Internal` remains in `collection.item`
- `collection.variable` contains keys `baseUrl`, `accessToken`, `csrfToken`
- Serialized collection contains `X-CSRF-Token` and `sportzal_csrf`
- Serialized collection contains neither `cc_access` nor `cc_refresh`
- 101 `pm.response.to.have.status()` assertions (every request)
- 17 `pm.test()` body-shape assertions (11 required; 17 delivered):
  - Auth: Login (login envelope: email + role), Me (data wrapper)
  - Users: list users (pagination envelope)
  - Clients: list clients, single client (pagination + data wrapper)
  - Memberships: list plans, single plan (pagination + data wrapper)
  - Visits: list visits, single visit (pagination + data wrapper)
  - Schedule: list recurring templates (pagination envelope)
  - Bookings: list bookings, single booking (pagination + data wrapper)
  - Trainers: list trainers, single trainer (pagination + data wrapper)
  - Payments: list payments (pagination envelope)
  - Reports: clients summary (items array)
  - Audit-log: list audit log (pagination envelope)
- Postman environment `accessToken` = `""`, `csrfToken` = `""` (no credentials)
- Postman environment passes credential regex check (`@local.dev`, `password`, `verify_owner` absent)
- Augment script byte-stable: running `pnpm postman:augment` twice on the same base-collection.json produces zero git diff

## Cookie Name Correction (load-bearing discrepancy)

**CONTEXT.md HND-02 and REQUIREMENTS.md incorrectly documented `cc_access`/`cc_refresh`** as the login cookie names. These cookies do not exist in the backend. `apps/backend/app/core/security.py` lines 223-254 (function `issue_session_cookies`) sets:

- `sz_access` — httpOnly access token cookie (Path=/)
- `sz_refresh` — httpOnly refresh token cookie (Path=/api/v1/auth)
- `sportzal_csrf` — non-httpOnly CSRF cookie (D-11-CSRF-DEFER; rename to `clubcore_csrf` deferred to v2.0)

All extraction logic in `augment-collection.mjs` uses the correct names. The source documentation (`CONTEXT.md`/`REQUIREMENTS.md`) retains the incorrect `cc_*` names and should be corrected in a future cleanup.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Deduplicated Reports/reports duplicate folder**
- **Found during:** Task 1 execution
- **Issue:** `openapi-to-postmanv2` creates case-sensitive distinct folders for tag values. Two operations in `apps/backend/openapi.json` carry both `"Reports"` (canonical) and `"reports"` (lowercase variant) tags: `GET /api/v1/reports/trainers` and `GET /api/v1/reports/trainers.csv`. This causes the generator to emit two separate folders — `Reports` (8 items) and `reports` (2 items, duplicate of the trainer-usage entries).
- **Fix:** Added deduplication logic in Step 1 of `augment-collection.mjs`: after removing `Internal`, filter folders using a case-insensitive seen-set so the first (canonical `Reports`) folder is kept and the duplicate lowercase `reports` folder is dropped.
- **Files modified:** `tools/newman/augment-collection.mjs`
- **Commit:** 3ab21269 (included in original Task 1 commit)

### UUID Re-generation Note (not a bug; operational note)

`openapi-to-postmanv2` generates random UUIDs for item IDs on every `pnpm postman:gen` run. The committed collection is byte-stable for repeated `pnpm postman:augment` calls against the same `tools/newman/base-collection.json`. After any `pnpm postman:gen`, a new `pnpm postman:augment` + commit is required to re-sync the committed collection. The augment script itself is deterministic and idempotent.

## Manual Verification Required

**Task 3: checkpoint:human-verify — auto-approved (--auto mode)**

The following manual steps verify HND-02 (auth flow in Postman GUI without manual header wiring):

Prerequisites:
1. In `apps/backend`, run `docker compose up` (Postgres + Redis + API).
2. Seed verification fixtures: run `apps/backend/scripts/seed_verification_fixtures.py` with `SEED_VERIFY_OWNER_PASSWORD` exported.

Postman GUI steps:
3. Import `.planning/handoff/v1.11-clubcore.postman_collection.json` and `.planning/handoff/v1.11-clubcore.postman_environment.json`; select the environment.
4. Run the Login request with body `{"email":"verify_owner@local.dev","password":"<seeded password>"}`. Expect 200; confirm the `csrfToken` collection variable is now populated (visible in Postman Variables panel).
5. Run any non-GET mutating request (e.g. a Memberships POST). Confirm in the Postman console that an `X-CSRF-Token` header was auto-sent without manual addition.
6. A business-logic 422/404 for missing body fields is acceptable — you are verifying CSRF header wiring, not business payload.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. All generated artifacts are static JSON files derived from the frozen spec. T-65-05 (credentials in env file), T-65-06 (Internal endpoints leaking), T-65-07 (CSRF wiring), T-65-08 (runtime access tokens), T-65-09 (spec drift) mitigations all confirmed applied.

## Self-Check: PASSED

Created files verified:
- `tools/newman/augment-collection.mjs`: FOUND
- `.planning/handoff/v1.11-clubcore.postman_collection.json`: FOUND
- `.planning/handoff/v1.11-clubcore.postman_environment.json`: FOUND

Commits verified:
- 3ab21269: Task 1 (augment script + initial collection)
- 6180d530: Task 2 (environment file + refreshed collection)
- ea3a1f2f: Task 2 sync (collection re-synced to latest postman:gen output)
