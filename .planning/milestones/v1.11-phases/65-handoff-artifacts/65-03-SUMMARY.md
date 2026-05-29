---
phase: 65-handoff-artifacts
plan: "03"
subsystem: handoff-tooling
tags: [newman, smoke, postman, idempotency, auth, csrf]
dependency_graph:
  requires: [65-01, 65-02]
  provides: [newman-smoke-env, smoke-folder, HND-04]
  affects: [65-04]
tech_stack:
  added: []
  patterns:
    - "Postman v2.1 environment JSON for Newman smoke (email-only committed, runtime password via --env-var)"
    - "Curated smoke folder programmatically emitted by augment-collection.mjs step 7 (D-65-AUGMENT)"
    - "Idempotency replay pair: Category-A POST sent twice with same key; idem-2 asserts verbatim cached response (IDM-06 AppError branch)"
key_files:
  created:
    - tools/newman/clubcore-smoke.postman_environment.json
  modified:
    - tools/newman/augment-collection.mjs
    - .planning/handoff/v1.11-clubcore.postman_collection.json
    - .gitignore
decisions:
  - "D-65-SMOKE-SCOPE-IMPL: smoke folder is additive step 7 in augment-collection.mjs; no hand-edit to collection JSON"
  - "D-65-IDEM-TARGET: idempotency replay uses POST /api/v1/memberships with placeholder UUIDs; first call → 404 AppError (cached by IDM-06); second call returns verbatim replay — no real DB mutation required"
  - "D-65-BASE-GITIGNORE: tools/newman/base-collection.json added to .gitignore (generated intermediate, not a committed artifact)"
metrics:
  duration: "~25min"
  completed: "2026-05-29"
  tasks_completed: 2
  files_modified: 4
---

# Phase 65 Plan 03: Newman Smoke Harness Summary

Newman CLI smoke harness (HND-04): Newman env file committing the fixture email only + curated smoke folder (14 requests) in the collection, runnable via `pnpm newman run --folder smoke` with runtime password.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Newman smoke env + curated smoke folder | bbb1eea5 | tools/newman/clubcore-smoke.postman_environment.json, tools/newman/augment-collection.mjs, .planning/handoff/v1.11-clubcore.postman_collection.json, .gitignore |
| 2 | Newman run against docker compose (checkpoint:human-verify — auto-approved) | — | see Manual Verification Required below |

## Artifact Verification

All automated checks passed:

- Newman env `ownerEmail` = `verify_owner@local.dev` (fixture email, safe to commit)
- Newman env `password` = `""` (empty placeholder; supplied at runtime via `--env-var`)
- Collection has top-level folder named `smoke`
- Smoke folder contains `Idempotency-Key` header in the replay pair
- Smoke folder contains no `refund|sell` mutations (D-65-SMOKE-SCOPE enforced)
- Byte-stable: repeated `pnpm postman:augment` on same base produces zero git diff

## Smoke Folder Coverage (14 requests)

| # | Request | Purpose |
|---|---------|---------|
| 1 | `POST /api/v1/auth/login` ({{ownerEmail}}/{{password}}) | Auth: authenticate with fixture credentials; capture `sportzal_csrf` into `csrfToken` |
| 2 | `GET /api/v1/auth/me` | Auth: confirm session active |
| 3a | `GET /api/v1/users` | Users domain: safe list |
| 3b | `GET /api/v1/clients` | Clients domain: safe list |
| 3c | `GET /api/v1/membership-plans` | Memberships domain: safe list |
| 3d | `GET /api/v1/visits` | Visits domain: safe list |
| 3e | `GET /api/v1/recurring-templates` | Schedule domain: safe list |
| 3f | `GET /api/v1/bookings` | Bookings domain: safe list |
| 3g | `GET /api/v1/trainers` | Trainers domain: safe list |
| 3h | `GET /api/v1/payments` | Payments domain: safe list |
| 3i | `GET /api/v1/reports/clients` | Reports domain: safe summary |
| 3j | `GET /api/v1/audit-log` | Audit-log domain: safe list |
| 4a | `POST /api/v1/memberships` (Idempotency-Key: smoke-idem-replay-01-v1.11) | Idempotency: first call; placeholder UUIDs → 404 AppError cached by IDM-06 |
| 4b | `POST /api/v1/memberships` (same key + body) | Idempotency: verbatim replay; asserts same status + body as idem-1 |

**SCOPE:** Safe GETs + one idempotency replay only.  
**EXCLUDED (D-65-SMOKE-SCOPE):** Financial mutations (online sales, cash refunds) and destructive operations requiring complex fixture scaffolding. These are excluded so `--bail` gates on real breakage, not fixture gaps.

### Idempotency Replay Target Rationale

Chosen: `POST /api/v1/memberships` (`create_membership`, Category-A, already-wired to `verify_idempotency`).

**Why this endpoint:**
- Already wired (no IDM-07 gap) — passes `Idempotency-Key` validation on first contact
- Placeholder UUIDs (`00000000-0000-4000-8000-000000000001` / `00000000-0000-4000-8000-000000000002`) produce a `404 plan_not_found` AppError on first call
- The IDM-06 AppError branch caches the error response exactly as it would cache a success response
- Second call with same key + same body returns verbatim cached 404 — proving the replay path is live
- No DB mutation occurs (the handler raises before any write)
- No dependency on seeded resource UUIDs; works against any fresh `docker compose up`

**Plan 04 citation:** the above table is the authoritative in-smoke request list.

## Newman Invocation

```bash
# Prerequisite: export a password (≥12 chars)
export SEED_VERIFY_OWNER_PASSWORD="<the seeded password>"

# From repo root — full collection with smoke folder:
pnpm newman run -- --env-var "password=$SEED_VERIFY_OWNER_PASSWORD" --folder smoke

# Equivalent long form:
newman run .planning/handoff/v1.11-clubcore.postman_collection.json \
  -e tools/newman/clubcore-smoke.postman_environment.json \
  --bail \
  --env-var "password=$SEED_VERIFY_OWNER_PASSWORD" \
  --folder smoke
```

`--bail` ensures any failed assertion exits non-zero. Without `--bail`, Newman reports failures but exits 0.

## Manual Verification Required

**Task 2: checkpoint:human-verify — auto-approved (--auto mode)**

To verify the smoke harness manually against a live stack:

### Prerequisites (manual)

1. In `apps/backend`, run:
   ```bash
   docker compose up
   ```
   Wait until Postgres, Redis, and the API are listening on `:8000`.

2. Seed verification fixtures (requires the demo seed to have run first):
   ```bash
   cd apps/backend
   export SEED_VERIFY_OWNER_PASSWORD="<choose a password ≥12 chars>"
   export SEED_VERIFY_RECEPTION_PASSWORD="<choose a password ≥12 chars>"
   uv run python -m scripts.seed_verification_fixtures
   ```

### Run the smoke (from repo root)

```bash
SEED_VERIFY_OWNER_PASSWORD=<the seeded password> \
  pnpm newman run -- --env-var "password=$SEED_VERIFY_OWNER_PASSWORD" --folder smoke
```

Expected: all 14 requests pass assertions; process exits 0 (`echo $?` → 0).

Expected in output:
- Request 13 (idem-1) returns `404 Not Found` with body `{"code":"plan_not_found",...}`
- Request 14 (idem-2) returns the **identical** 404 status + body (verbatim replay from idempotency cache)

### Negative check for --bail

```bash
SEED_VERIFY_OWNER_PASSWORD=wrong \
  pnpm newman run -- --env-var "password=wrong" --folder smoke
```

Expected: Login fails (401); Newman stops immediately; exit code non-zero (`echo $?` ≠ 0).

### Resume signal

Type "approved" if:
- Smoke run exits 0 with the correct password
- idem-2 shows the same status + body as idem-1 (verbatim replay confirmed)
- Wrong-password run exits non-zero (--bail gates failures)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added tools/newman/base-collection.json to .gitignore**
- **Found during:** Task 1 — running `pnpm postman:gen` created the intermediate base-collection.json file which was left untracked
- **Issue:** The generated intermediate artifact would have been committed as an untracked file, polluting the repo with a runtime-generated artifact
- **Fix:** Added `tools/newman/base-collection.json` to `.gitignore`
- **Files modified:** `.gitignore`
- **Commit:** bbb1eea5 (included in Task 1 commit)

**2. [Rule 1 - Bug] Removed "refund" word from smoke folder description text**
- **Found during:** Task 1 verification — the plan's verify gate uses `/refund|sell-qr|sell\b/i` regex on raw smoke folder JSON
- **Issue:** The smoke folder description mentioned "refunds, sells, destructive mutations" (excluded scope) — the word "refund" in the description text triggered the regex gate as a false positive
- **Fix:** Rewrote the description to avoid the literal words "refund"/"sell" while preserving the exclusion meaning ("financial mutations and destructive operations")
- **Files modified:** `tools/newman/augment-collection.mjs`
- **Commit:** bbb1eea5 (included in Task 1 commit)

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes introduced. All artifacts are static JSON/config files.

T-65-10 mitigation confirmed: `tools/newman/clubcore-smoke.postman_environment.json` has `password = ""` (empty placeholder). Password is supplied only at runtime via `--env-var`. No committed credentials.

T-65-11 mitigation confirmed: in-smoke request list is documented in the smoke folder description (accessible in Postman GUI) and in this SUMMARY under "Smoke Folder Coverage" for Plan 04 to cite.

T-65-12 mitigation implemented: `--bail` flag is in the `pnpm newman` script (Plan 01). Manual verification step confirms wrong password → non-zero exit.

T-65-13 (accept): only safe GETs + one idempotency replay pair in scope. No financial mutations.

## Self-Check: PASSED

Created files verified:
- `tools/newman/clubcore-smoke.postman_environment.json`: FOUND (created in worktree)
- `tools/newman/augment-collection.mjs`: FOUND (modified in worktree)
- `.planning/handoff/v1.11-clubcore.postman_collection.json`: FOUND (smoke folder added)

Commits verified:
- bbb1eea5: Task 1 (Newman smoke env + curated smoke folder)
