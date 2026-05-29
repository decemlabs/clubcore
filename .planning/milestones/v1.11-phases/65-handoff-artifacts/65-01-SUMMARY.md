---
phase: 65-handoff-artifacts
plan: "01"
subsystem: tooling
tags: [handoff, redocly, newman, postman, doc-site, gitignore]
dependency_graph:
  requires: []
  provides: [root-package-json, pnpm-docs-script, pnpm-newman-script, pnpm-postman-gen-script, docs-site-gitignored]
  affects: [pnpm-workspace, pnpm-lock.yaml, .gitignore]
tech_stack:
  added:
    - "@redocly/cli 2.31.4 — Redocly preview-docs server (pnpm docs / HND-06)"
    - "newman 6.2.2 — Newman CLI smoke runner (pnpm newman)"
    - "openapi-to-postmanv2 6.0.1 — OpenAPI to Postman collection converter (pnpm postman:gen)"
  patterns:
    - "Private root package.json (type:module, no publish target) as workspace root entry point for handoff tooling"
    - "pnpm workspace root devDependencies at exact pinned versions (no caret/tilde) per D-65-ROOT-PKG / T-65-03"
    - ".gitignore append pattern with decision rationale comment (D-11-DOCS-PRIVATE)"
key_files:
  created:
    - path: "package.json"
      role: "Private monorepo root package with four handoff scripts and three pinned devDeps"
  modified:
    - path: ".gitignore"
      role: "Added .docs-site/ ignore entry with D-11-DOCS-PRIVATE rationale"
    - path: "pnpm-lock.yaml"
      role: "Lockfile entries for @redocly/cli, newman, openapi-to-postmanv2"
decisions:
  - "D-65-ROOT-PKG: Root package.json is the workspace root itself (not a workspace member) — pnpm-workspace.yaml globs only apps/* and packages/*; tools/ is outside those globs so scripts run from root without a separate workspace entry"
  - "D-65-DOCS-PRIVATE: Only preview-docs script provided for HND-06 — no build-docs/bundle/deploy script exists per D-11-DOCS-PRIVATE privacy constraint"
  - "D-65-EXACT-PINS: All three handoff devDeps pinned at exact versions (no caret/tilde) to prevent silent supply-chain drift on tools that read the full private API spec (T-65-03)"
metrics:
  duration: "90s"
  completed: "2026-05-29T09:31:45Z"
  tasks_completed: 3
  files_changed: 3
---

# Phase 65 Plan 01: Private root package.json + pnpm docs preview entry point Summary

Private repo-root package.json with four handoff scripts and three exact-pinned devDeps; `redocly preview-docs` entry point for the clubcore API doc-site on localhost:8080 with no publish path; `.docs-site/` gitignored per D-11-DOCS-PRIVATE.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create private repo-root package.json | a1cfcd52 | package.json, pnpm-lock.yaml |
| 2 | Gitignore .docs-site/ and confirm no publish path | a3b53f82 | .gitignore |
| 3 | Verify pnpm docs preview server (human-verify, auto-approved) | — | (manual verification) |

## What Was Built

### Task 1: Root package.json

Created `package.json` at repo root with:

- `"private": true`, `"type": "module"`, `"name": "clubcore-monorepo"`, `"version": "0.0.0"`
- Four handoff scripts:
  - `docs`: `redocly preview-docs apps/backend/openapi.json --port 8080` (HND-06)
  - `postman:gen`: `openapi2postmanv2 -s apps/backend/openapi.json -o tools/newman/base-collection.json -O folderStrategy=Tags,requestNameSource=summary`
  - `postman:augment`: `node tools/newman/augment-collection.mjs`
  - `newman`: `newman run .planning/handoff/v1.11-clubcore.postman_collection.json -e tools/newman/clubcore-smoke.postman_environment.json --bail`
- Three devDependencies at exact pinned versions (no caret/tilde): `@redocly/cli: 2.31.4`, `newman: 6.2.2`, `openapi-to-postmanv2: 6.0.1`
- `engines`: node >=20.0.0, pnpm >=9.0.0 (matches api-client analog)
- `pnpm install` ran successfully; all three binaries materialized at `node_modules/.bin/` (redocly, openapi2postmanv2, newman)

### Task 2: .gitignore update

Appended to `.gitignore` after the existing entries:
```
# Redocly static doc-site build output (D-11-DOCS-PRIVATE — private artifact, never published)
.docs-site/
```
Confirmed `.github/workflows/` contains zero references to `preview-docs`, `build-docs`, `docs-site`, or `gh-pages` — no public publish path exists.

## Manual Verification Required

**Task 3 (checkpoint:human-verify, auto-approved in autonomous mode):**

To verify the `pnpm docs` preview server:

1. From the repo root, run: `pnpm docs`
2. Wait for Redocly to print "Preview server running ... http://localhost:8080"
3. Open `http://localhost:8080` in a browser
4. Confirm: title shows "clubcore API" version 1.11.0, 10 business-domain tag groups visible in left sidebar (Auth, Users, Clients, Memberships, Visits, Schedule, Bookings, Trainers, Payments, Reports/Audit-log; Internal may also appear — expected for local private doc-site)
5. Confirm URL is `localhost` only — no public host, no published link
6. Stop the server with Ctrl-C

Expected: binaries are installed at `node_modules/.bin/redocly`; `redocly.yaml` at repo root is auto-discovered by Redocly CLI; spec at `apps/backend/openapi.json` contains `info.title: "clubcore API"` version 1.11.0.

## Threat Surface Check

No new network endpoints, auth paths, file access patterns, or schema changes were introduced. The threat model from the plan was fully addressed:

- T-65-01 mitigated: `scripts.docs` runs `preview-docs` only; verification confirmed no `build-docs/bundle/publish/deploy/pdf` script anywhere in package.json. `.github/workflows/` grep returned zero matches.
- T-65-02 mitigated: `.docs-site/` added to `.gitignore` — any locally-built static site cannot be committed.
- T-65-03 mitigated: All three devDeps pinned at exact versions (no caret/tilde) in committed `package.json`.
- T-65-04 accepted: package.json holds no secrets (scripts + dep pins only).

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED

- `package.json` exists at repo root: FOUND
- `package.json` contains `"private": true`: VERIFIED
- `.gitignore` contains `.docs-site/`: VERIFIED (grep -qxF)
- `node_modules/.bin/redocly` exists: FOUND
- `node_modules/.bin/openapi2postmanv2` exists: FOUND
- `node_modules/.bin/newman` exists: FOUND
- Task 1 commit `a1cfcd52` exists: VERIFIED
- Task 2 commit `a3b53f82` exists: VERIFIED
- No forbidden scripts (build-docs/bundle/publish/deploy/pdf): VERIFIED
- No publish path in .github/workflows/: VERIFIED
