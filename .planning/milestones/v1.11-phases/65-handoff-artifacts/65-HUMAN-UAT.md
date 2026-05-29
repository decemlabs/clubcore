---
status: partial
phase: 65-handoff-artifacts
source: [65-VERIFICATION.md]
started: 2026-05-29
updated: 2026-05-29
---

## Current Test

[awaiting human testing — auto-approved under `--auto`; re-verify against a live stack before real handoff]

## Tests

### 1. `pnpm docs` renders the private doc-site on localhost:8080
expected: From repo root, `pnpm install` then `pnpm docs` starts `redocly preview-docs apps/backend/openapi.json --port 8080`; opening http://localhost:8080 shows "clubcore API" v1.11.0 with all domain tag groups in the left sidebar; URL is localhost-only (no public publish path); Ctrl-C stops it.
result: [pending]

### 2. Postman GUI auth flow (cookie extraction + CSRF auto-injection)
expected: With `docker compose up` (apps/backend) + seeded fixtures, importing `.planning/handoff/v1.11-clubcore.postman_collection.json` + `.postman_environment.json` into Postman, running the Login request extracts `sz_access`/`sz_refresh`/`sportzal_csrf` and stores `csrfToken`; subsequent mutating requests auto-send `X-CSRF-Token` from the stored value with no manual header wiring.
result: [pending]

### 3. `pnpm newman run` smoke against docker compose
expected: With `docker compose up` (apps/backend) + `seed_verification_fixtures.py` run with `SEED_VERIFY_OWNER_PASSWORD` set, `SEED_VERIFY_OWNER_PASSWORD=… pnpm newman` runs the `smoke` folder (login → CSRF → one safe GET per domain → idempotency replay) and exits 0 when healthy; `--bail` makes it exit non-zero on any endpoint failure. (Documented as "local handoff smoke — not a CI gate" per D-11-NEWMAN-LOCAL.)
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
