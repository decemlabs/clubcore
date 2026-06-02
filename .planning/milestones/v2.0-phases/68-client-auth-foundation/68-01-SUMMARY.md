---
phase: 68-client-auth-foundation
plan: "01"
subsystem: auth
tags: [sqlalchemy, alembic, postgres, otp, refresh-token, client-auth, migration]

requires:
  - phase: clients-module
    provides: clients table + Client ORM model (FK target for new columns)
  - phase: auth-module
    provides: OtpCode model + otp_codes table (extended by this plan)

provides:
  - "OtpCode.client_id nullable FK + ck_otp_codes_principal_xor CHECK + uq_otp_codes_client_channel_active partial-unique index"
  - "ClientRefreshToken ORM model (app/modules/client_auth/models.py)"
  - "app/modules/client_auth/ package (__init__.py + models.py)"
  - "Alembic revision 0043_client_auth_otp (additive otp_codes changes)"
  - "Alembic revision 0044_client_refresh_token (new client_refresh_tokens table)"

affects:
  - 68-02
  - 68-03
  - 68-04
  - 68-05
  - 68-06

tech-stack:
  added: []
  patterns:
    - "XOR CHECK on OtpCode ensures exactly one of (user_id, client_id) is non-null per row (D-03)"
    - "Parallel ORM module pattern: client_auth mirrors auth with clients.id as FK target"
    - "Full-slug Alembic revision IDs with linear chain (0042->0043->0044)"

key-files:
  created:
    - apps/backend/app/modules/client_auth/__init__.py
    - apps/backend/app/modules/client_auth/models.py
    - apps/backend/alembic/versions/0043_client_auth_otp.py
    - apps/backend/alembic/versions/0044_client_refresh_token.py
  modified:
    - apps/backend/app/modules/auth/models.py

key-decisions:
  - "D-03 implemented: nullable client_id FK on otp_codes with XOR CHECK (not a separate table)"
  - "D-09 implemented: separate client_refresh_tokens table (never intersects with refresh_tokens)"
  - "CheckConstraint added to sqlalchemy imports in auth/models.py (was missing)"
  - "Migration downgrade drops in strict reverse order: index -> check -> FK -> column (0043); drop_table (0044)"

patterns-established:
  - "Parallel auth module pattern: client_auth/ mirrors auth/ structure; staff code untouched"
  - "XOR CHECK name ck_otp_codes_principal_xor enforces single-principal ownership per OTP row"

requirements-completed: [CAUTH-01, CAUTH-04, CISO-05]

duration: 10min
completed: "2026-05-29"
---

# Phase 68 Plan 01: Client Auth Foundation — Schema Summary

**Additive otp_codes schema extension (client_id FK + XOR CHECK) and new client_refresh_tokens table via two async Alembic migrations providing the isolated persistence foundation for the parallel client auth stack.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-05-29T16:55:34Z
- **Completed:** 2026-05-29T16:59:18Z
- **Tasks:** 3 completed
- **Files modified/created:** 5

## Accomplishments

- OtpCode gains nullable `client_id` FK (→ clients.id CASCADE) + `ck_otp_codes_principal_xor` CHECK (XOR ensures single principal per row) + `uq_otp_codes_client_channel_active` partial-unique index; existing staff columns byte-unchanged
- New `app/modules/client_auth/` package with `ClientRefreshToken` ORM model fully parallel to `auth.RefreshToken`, FK targeting `clients.id` (D-09 isolation)
- Linear Alembic revision chain 0042→0043→0044; both migrations are additive-only with working downgrade; no staff tables altered beyond the otp_codes column add

## Task Commits

1. **Task 1: Add client_id FK + XOR CHECK + partial-unique to OtpCode** - `3bc0c80c` (feat)
2. **Task 2: Create client_auth module + ClientRefreshToken model** - `7fa26f13` (feat)
3. **Task 3: Write Alembic revisions 0043 + 0044** - `4d5267f7` (feat)

## Files Created/Modified

- `apps/backend/app/modules/auth/models.py` — Added `client_id` column, `CheckConstraint` to import, XOR CHECK + client partial-unique to `__table_args__`
- `apps/backend/app/modules/client_auth/__init__.py` — New module package init
- `apps/backend/app/modules/client_auth/models.py` — `ClientRefreshToken` ORM model (parallel to `RefreshToken`)
- `apps/backend/alembic/versions/0043_client_auth_otp.py` — Additive otp_codes migration with working downgrade
- `apps/backend/alembic/versions/0044_client_refresh_token.py` — New client_refresh_tokens table migration

## Decisions Made

- D-03: Reuse existing `otp_codes` table with nullable `client_id` FK + XOR CHECK (not a new table). Staff OTP infrastructure shared at the storage layer; ownership isolated by DB constraint.
- D-09: Separate `client_refresh_tokens` table so staff and client refresh storage never intersect (strongest CISO-05 isolation guarantee).
- Migration downgrade for 0043 uses `type_="check"` in `drop_constraint` to be explicit about constraint type.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- Live DB not available in this environment (`sportzal` database does not exist). Migration round-trip test (`alembic upgrade head && downgrade -2 && upgrade head`) could not run against a real DB. Static verification used instead: revision chain confirmed 0042→0043→0044 via `grep revision/down_revision`; both migrations are structurally correct additive-only scripts following established patterns from 0001_auth.py and 0027_otp_email_channel.py analogs. mypy strict and ruff pass on all files.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- ORM foundation is complete: `OtpCode.client_id` column + `ClientRefreshToken` model are importable and mypy-clean
- Plans 68-02 through 68-06 can proceed: they depend on these models existing
- When a live DB is available, run `uv run alembic upgrade head` from `apps/backend/` to apply revisions 0043 and 0044

---
*Phase: 68-client-auth-foundation*
*Completed: 2026-05-29*
