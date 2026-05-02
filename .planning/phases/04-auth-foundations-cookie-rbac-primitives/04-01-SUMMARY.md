---
phase: 04-auth-foundations-cookie-rbac-primitives
plan: 01
subsystem: infra
tags: [pyjwt, argon2-cffi, python-telegram-bot, pydantic, uv, deps, settings]

# Dependency graph
requires:
  - phase: 03-tests-dev-infrastructure-documentation
    provides: pyproject.toml with PEP 735 dependency-groups, uv toolchain, Settings baseline
provides:
  - pyjwt>=2.12.1,<3 pinned and installed (JWT encode/decode for Plan 04-07)
  - argon2-cffi>=25.1.0,<26 pinned and installed (Argon2id hashing for Plan 04-07)
  - python-telegram-bot>=22.7,<23 pinned and installed (Telegram OTP channel for Phase 7)
  - pydantic>=2.11,<3 floor bump (validate_by_name/validate_by_alias for Plan 04-05)
  - Settings.access_token_ttl_seconds = 900 (env-driven access JWT TTL)
  - Settings.refresh_token_ttl_seconds = 2_592_000 (env-driven refresh token TTL)
  - Settings.jwt_clock_leeway_seconds = 30 (env-driven PyJWT leeway)
  - Settings.cookie_secure = False (env-driven Secure cookie flag; prod assertion in Phase 5)
  - .env.example documents all four new env vars with dev defaults
affects:
  - 04-07: security.py JWT helpers read settings.access_token_ttl_seconds, jwt_clock_leeway_seconds, cookie_secure
  - 04-05: schemas.py ContractModel uses validate_by_name/validate_by_alias (requires pydantic>=2.11)
  - 05: login/refresh endpoints use Settings TTLs via get_settings()
  - 07: python-telegram-bot dep available for Telegram OTP process

# Tech tracking
tech-stack:
  added:
    - pyjwt 2.12.1 (HS256 JWT sign/verify; algorithm confusion pre-empted by explicit algorithms= kwarg)
    - argon2-cffi 25.1.0 (Argon2id password hashing; OWASP 2026 defaults)
    - python-telegram-bot 22.7 (Telegram bot SDK; process-based worker, not ARQ)
    - pydantic 2.13.3 (bumped from 2.0 floor; 2.11+ validate_by_name/validate_by_alias active)
  patterns:
    - env-driven TTL/security config via pydantic-settings (no hardcoded security constants)
    - upper-bound pinning on security-critical deps (pyjwt<3, argon2-cffi<26, ptb<23)
    - alphabetical dep ordering in pyproject.toml for grepping

key-files:
  created: []
  modified:
    - apps/backend/pyproject.toml
    - apps/backend/uv.lock
    - apps/backend/app/core/config.py
    - apps/backend/.env.example

key-decisions:
  - "D-05: TTL constants live in Settings (env-driven), not module constants — staging/prod can tune without code edits"
  - "D-12: pydantic>=2.11,<3 floor required for validate_by_name/validate_by_alias (Plan 04-05 ContractModel)"
  - "D-25: cookie_secure bool field with dev-friendly False default; prod startup assertion deferred to Phase 5 create_app"
  - "Upper-bound pinning on all three new security deps (pyjwt<3, argon2-cffi<26, ptb<23) per T-04-01"

patterns-established:
  - "env-driven security config: access_token_ttl_seconds / refresh_token_ttl_seconds / jwt_clock_leeway_seconds / cookie_secure"
  - "pyproject.toml deps alphabetically ordered for consistency"

requirements-completed: [INFRA-07]

# Metrics
duration: 3min
completed: 2026-05-02
---

# Phase 04 Plan 01: Dep Foundations + Settings Extension Summary

**pydantic bumped to 2.13.3 (>=2.11), pyjwt/argon2-cffi/python-telegram-bot pinned with upper bounds, Settings extended with 4 env-driven JWT TTL + cookie Secure fields**

## Performance

- **Duration:** 3 min
- **Started:** 2026-05-02T06:38:25Z
- **Completed:** 2026-05-02T06:41:30Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Added pyjwt>=2.12.1,<3, argon2-cffi>=25.1.0,<26, python-telegram-bot>=22.7,<23 to pyproject.toml with upper bounds per T-04-01 supply-chain mitigation; uv.lock regenerated (59 packages, 5 new)
- Bumped pydantic floor from >=2.0 to >=2.11,<3 (required by D-12 for validate_by_name/validate_by_alias in Plan 04-05 ContractModel); pydantic 2.13.3 resolved
- Extended Settings with access_token_ttl_seconds=900, refresh_token_ttl_seconds=2_592_000, jwt_clock_leeway_seconds=30, cookie_secure=False (D-05, D-25); documented in .env.example with comments
- All quality gates green: uv lock --check, mypy strict, ruff, import-linter (3 contracts KEPT)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add three new deps + bump pydantic floor + regenerate uv.lock** - `4c8fa27` (chore)
2. **Task 2: Extend Settings with 4 fields + .env.example with 4 entries** - `88b7a15` (feat)

**Plan metadata:** committed below with SUMMARY.md

## Files Created/Modified
- `apps/backend/pyproject.toml` - Added 3 new pinned deps, bumped pydantic to >=2.11,<3, reordered alphabetically
- `apps/backend/uv.lock` - Regenerated; 5 new packages (argon2-cffi, argon2-cffi-bindings, cffi, pycparser, python-telegram-bot); pyjwt was already resolved from prior dep tree
- `apps/backend/app/core/config.py` - 4 new typed fields appended after secret_key with D-05/D-25 comment marker
- `apps/backend/.env.example` - 4 new env vars with one-line comments appended at end of file

## Decisions Made
- Alphabetically reordered entire dependencies array while making edits (not strictly required by plan but improves maintainability — no behavioral change)
- Shortened cookie_secure comment from plan's exact wording to fit 100-char ruff line limit (Rule 1 deviation — CLAUDE.md ruff enforcement takes precedence)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Shortened cookie_secure inline comment to satisfy ruff E501**
- **Found during:** Task 2 (config.py edit + ruff check)
- **Issue:** Plan specified comment text `# prod startup must ASSERT True (Phase 5 will add the assertion)` which produced 114-char line; ruff E501 limit is 100 chars
- **Fix:** Shortened to `# prod startup must ASSERT True (Phase 5 adds assertion)` — same semantic meaning, 2 chars under limit
- **Files modified:** apps/backend/app/core/config.py
- **Verification:** `uv run ruff check app/core/config.py` exits 0
- **Committed in:** 88b7a15 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - formatting/linting)
**Impact on plan:** Trivial comment shortening; semantic intent fully preserved. No scope creep.

## Issues Encountered
- pyjwt 2.12.1 was already in the uv dependency graph from a prior transitive dep, so `uv lock` output listed it as "not added" — the explicit pin now enforces the lower/upper bound correctly regardless.
- Settings verification command requires DATABASE_URL / REDIS_URL / SECRET_KEY env vars to be provided (pydantic-settings has no .env file in the worktree); ran with inline env vars — standard pattern for CI without Postgres.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 04-05 (schemas.py ContractModel): pydantic>=2.11 available; validate_by_name/validate_by_alias will work at class-creation time
- Plan 04-07 (security.py JWT + cookie helpers): settings.access_token_ttl_seconds, settings.jwt_clock_leeway_seconds, settings.cookie_secure all readable via get_settings(); pyjwt and argon2-cffi installed
- Phase 5 login/refresh endpoints: TTLs env-driven; cookie_secure=False dev default; prod assertion scaffolded via comment, to be implemented in Phase 5 create_app()
- Phase 7 (Telegram OTP): python-telegram-bot dep available in the venv

---
*Phase: 04-auth-foundations-cookie-rbac-primitives*
*Completed: 2026-05-02*
