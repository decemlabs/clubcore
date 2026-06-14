---
status: complete
phase: quick-260529-ll9
plan: 01
subsystem: backend-auth, api-contract, frontend-fetcher, tooling, handoff
tags: [cookie-rename, csrf, domain-rename, name-cleanup, contract-regeneration]
dependency_graph:
  requires: []
  provides: [cc_access-cookie, cc_refresh-cookie, clubcore_csrf-cookie, clubcore.ru-email-domain, clubcore_actor_context-contextvar, cc-yookassa-ua, regenerated-openapi-contract]
  affects: [apps/backend/app/core/security.py, apps/backend/app/core/dependencies.py, apps/backend/openapi.json, packages/api-client/src/schema.d.ts, packages/api-client/src/fetcher.ts]
tech_stack:
  added: []
  patterns: [cookie-name-rename-names-only, regen-not-hand-edit]
key_files:
  created: []
  modified:
    - apps/backend/app/core/security.py
    - apps/backend/app/core/config.py
    - apps/backend/app/core/actor_context.py
    - apps/backend/app/core/audit.py
    - apps/backend/app/core/dependencies.py
    - apps/backend/app/core/exceptions.py
    - apps/backend/app/integrations/yookassa/factory.py
    - apps/backend/app/modules/auth/email_templates.py
    - apps/backend/app/modules/auth/router.py
    - apps/backend/app/modules/auth/schemas.py
    - apps/backend/app/modules/auth/service.py
    - apps/backend/app/modules/bookings/email_templates.py
    - apps/backend/app/modules/memberships/email_templates.py
    - apps/backend/app/modules/payments/email_templates.py
    - apps/backend/app/main.py
    - apps/backend/infra/dns/clubcore.ru.zone
    - apps/backend/openapi.json
    - packages/api-client/src/fetcher.ts
    - packages/api-client/src/schema.d.ts
    - packages/api-client/CHANGELOG.md
    - packages/api-client/README.md
    - tools/newman/augment-collection.mjs
    - .planning/handoff/clubcore-auth-runbook.md
    - .planning/handoff/v1.11-clubcore.postman_collection.json
    - apps/backend/tests/ (108 test files)
decisions:
  - "Cookie names changed via plain rename (no dual-read window) — no live client holding old cookies pre-integration"
  - "Only cookie NAMES changed; all attributes (httpOnly, SameSite=lax, Path, Secure, Max-Age) are byte-identical"
  - "CLUB_BRAND='Sportzal' preserved per D-62-02 (gym brand, not product namespace)"
  - "Historical .planning/ docs with old identifiers left untouched per D-62-09 / D-10-HISTORY-IMMUTABLE"
  - "Contract-freeze-v1.11.0 baseline intentionally shifted (pre-integration cheapest moment)"
  - "openapi.json and schema.d.ts regenerated (not hand-edited); double-regen determinism verified"
metrics:
  duration: ~35 minutes
  completed_date: "2026-05-29"
  tasks_completed: 3
  files_changed: 135
---

# Quick Task 260529-ll9: Purge Sportzal-Era Technical Naming — Summary

**One-liner:** Renamed auth cookie keys (cc_access, cc_refresh, clubcore_csrf), email domain (mail.clubcore.ru), ContextVar (clubcore_actor_context), and YooKassa User-Agent from sportzal-era identifiers, closing NAME-01 / D-11-CSRF-DEFER with green tests and regenerated contract.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Rename backend technical identifiers + update 108 test files | 97e1fc1b |
| 2 | Rename frontend contract package, tooling, and active handoff artifacts | 8f697a7b |
| 3 | Regenerate frozen contract artifacts (openapi.json + schema.d.ts) | 063df3b8 |

## What Changed

### Auth Cookie Names (NAMES ONLY — attributes byte-identical)

| Old name | New name | Attributes |
|----------|----------|------------|
| `sz_access` | `cc_access` | httpOnly=True, Path=/, SameSite=lax |
| `sz_refresh` | `cc_refresh` | httpOnly=True, Path=/api/v1/auth, SameSite=lax |
| `sportzal_csrf` | `clubcore_csrf` | httpOnly=False, Path=/, SameSite=lax |

**Cookie attribute tuple verified byte-identical** — all six set/delete calls in `security.py` preserve the original attribute values unchanged. Tests asserting httpOnly/SameSite/Path/Secure/Max-Age still pass byte-identically.

### Email Domain
- `config.py` `from_address` default: `noreply@mail.clubcore.ru`
- All four email template modules: `mail.clubcore.ru` in footers; `{CLUB_BRAND}` token untouched (renders "Sportzal")

### ContextVar
- `actor_context.py`: ContextVar name `clubcore_actor_context`
- Docstring example addresses updated to `@clubcore.local`

### YooKassa User-Agent
- `factory.py`: `"clubcore/1.11 YooKassa-Adapter"` (product client identity, not gym brand)

### DNS Zone
- `git mv apps/backend/infra/dns/sportzal.ru.zone → clubcore.ru.zone`
- `$ORIGIN clubcore.ru.`, all hostnames updated; placeholder DKIM/SPF/DMARC values preserved

### OpenAPI Prose (feeds regeneration)
- `main.py` SECURITY_SCHEMES: `cookieAuth.name=cc_access`, descriptions updated
- Route docstrings: `cc_refresh` in /refresh, /logout, /sessions endpoints

### Contract Artifacts (regenerated, not hand-edited)
- `apps/backend/openapi.json`: `securitySchemes.cookieAuth.name=cc_access`; route descriptions reference `cc_refresh`/`clubcore_csrf`; info.description updated
- `packages/api-client/src/schema.d.ts`: regenerated from new openapi.json via openapi-typescript
- **Double-regen determinism verified**: running `uv run python -m scripts.export_openapi` and `pnpm --filter @clubcore/api-client codegen` a second time produces zero diff

### Frontend Fetcher
- `packages/api-client/src/fetcher.ts`: `readCsrfCookie()` reads `clubcore_csrf=` prefix

### Active Handoff Artifacts
- `clubcore-auth-runbook.md`: 31 references updated
- `v1.11-clubcore.postman_collection.json`: 214 references updated

## Verification Gates — All Passed

| Gate | Status |
|------|--------|
| `uv run pytest -q` | PASSED (2249 passed, 6 skipped) |
| `uv run ruff check` | PASSED |
| `uv run ruff format --check` | PASSED |
| `uv run mypy --strict app` | PASSED (no issues in 210 files) |
| `uv run lint-imports` | PASSED (3 contracts kept) |
| `git diff --exit-code openapi.json` (after 2nd regen) | PASSED |
| `git diff --exit-code packages/api-client/src/schema.d.ts` (after 2nd regen) | PASSED |
| Redocly lint | PASSED |
| Zero-residue grep (app/infra/tests) | PASSED |
| `CLUB_BRAND: Final[str] = "Sportzal"` intact | PASSED |
| `pnpm -F @clubcore/api-client typecheck` | PASSED |
| `pnpm -F @clubcore/api-client test` | PASSED (16 tests) |

## Contract-Freeze Baseline Note

The regeneration in Task 3 **intentionally shifts the contract-freeze-v1.11.0 baseline**. This is acceptable and expected — the rename is happening pre-integration (no live frontend consuming old cookie names), which is exactly the cheapest moment. The baseline tag `contract-freeze-v1.11.0` now refers to the commit before this task; new baseline reflects cc_access/cc_refresh/clubcore_csrf.

## Historical .planning/ Occurrences

Historical `.planning/phases/**`, `.planning/milestones/v1.*-*`, `.planning/MILESTONES.md`, `.planning/RETROSPECTIVE.md`, `.planning/handoff/v1.4-auth-runbook.md`, and `.planning/handoff/v1.9-trainers-runbook.md` **intentionally retain the old identifiers** per D-62-09 / D-10-HISTORY-IMMUTABLE (forward-only audit trail). These reflect what was true at the time of their writing.

## Deviations from Plan

None — plan executed exactly as written. All renames applied as specified; attribute tuples verified byte-identical; zero occurrences in in-scope paths; CLUB_BRAND preserved.

## Self-Check: PASSED

- apps/backend/app/core/security.py: FOUND (contains `cc_access`)
- apps/backend/infra/dns/clubcore.ru.zone: FOUND (contains `$ORIGIN clubcore.ru.`)
- apps/backend/app/core/actor_context.py: FOUND (contains `clubcore_actor_context`)
- packages/api-client/src/fetcher.ts: FOUND (contains `clubcore_csrf`)
- apps/backend/openapi.json: FOUND (contains `cc_access`)
- Commits 97e1fc1b, 8f697a7b, 063df3b8: all present in git log
