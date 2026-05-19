---
phase: 42-email-transport-layer-email-otp-fallback
plan: 03
subsystem: auth
tags:
  - migration
  - alembic
  - orm
  - sqlalchemy
  - postgres
  - otp
  - auth
  - email
  - channel-discriminator
  - partial-unique

# Dependency graph
requires:
  - phase: 42-email-transport-layer-email-otp-fallback
    provides: "Alembic migration 0026_email_send_log (sibling plan 42-01, wave 1) — provides the down_revision anchor for 0027"
provides:
  - "Alembic migration 0027 — otp_codes.channel column + CHECK + partial-UNIQUE (user_id, channel) WHERE consumed_at IS NULL"
  - "OtpChannel = Literal['telegram','email'] TypeAlias re-exportable from app.modules.auth.models"
  - "OtpCode.channel: Mapped[OtpChannel] ORM column with server_default 'telegram'"
  - "OtpCode.__table_args__ partial-UNIQUE Index 'uq_otp_codes_user_channel_active' with literal-name match to migration"
affects:
  - 42-04-email-integrations-models
  - 42-09-otp-email-request-handler
  - 42-10-otp-email-verify-and-anti-oracle
  - 43-email-verify-set-side (Phase 43 reads users.email_verified for AUTH-EM-02)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Literal-as-TypeAlias for ORM-side enum discriminators (mirrors PasswordResetTokenPurpose; PATTERNS.md §19)"
    - "op.f()-wrapped CHECK constraint name to defeat naming_convention double-prefix (PATTERNS.md §C / 0024 lesson)"
    - "Partial-UNIQUE name parity between ORM __table_args__ and Alembic upgrade body (mirrors password_reset_tokens uq_password_reset_tokens_active)"

key-files:
  created:
    - apps/backend/alembic/versions/0027_otp_codes_channel_discriminator.py
  modified:
    - apps/backend/app/modules/auth/models.py

key-decisions:
  - "Revision id shortened from planned 0027_otp_codes_channel_discriminator (36 chars) to 0027_otp_channel_discriminator (30 chars) to fit alembic_version.version_num varchar(32). Filename retained verbatim per plan."
  - "Migration CREATEs the partial-UNIQUE outright; no DROP step. Live introspection (Postgres + Base.metadata) confirmed no predecessor (user_id) WHERE consumed_at IS NULL UNIQUE existed in v1.5 schema."
  - "OtpCode previously had no __table_args__; the new tuple containing only the partial-UNIQUE Index is the first one for this class."

patterns-established:
  - "Channel discriminator shape on OTP-style tables: TEXT NOT NULL DEFAULT 'telegram' + op.f()-wrapped CHECK + partial-UNIQUE on (user_id, channel) WHERE consumed_at IS NULL — reusable for any future per-channel-active-token table."

requirements-completed:
  - AUTH-EM-01

# Metrics
duration: ~10min
completed: 2026-05-19
---

# Phase 42 Plan 03: otp_codes.channel discriminator + active partial-UNIQUE Summary

**Alembic 0027 adds `otp_codes.channel TEXT NOT NULL DEFAULT 'telegram' CHECK channel IN ('telegram','email')` plus partial-UNIQUE `uq_otp_codes_user_channel_active` on `(user_id, channel) WHERE consumed_at IS NULL`, with ORM mirror landing `OtpCode.channel: Mapped[OtpChannel]` and matching `__table_args__` Index — unlocks the dual-channel per-user active OTP discipline required by Wave 2/3 D-42-22 atomic-consume + RFC 6238 single-active.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-05-19T07:47:00Z (approx)
- **Completed:** 2026-05-19T07:57:00Z
- **Tasks:** 2 (both committed)
- **Files modified:** 2 (1 created, 1 modified)

## Accomplishments

- Shipped Alembic 0027 with column ADD + CHECK + partial-UNIQUE CREATE, round-tripped clean (upgrade → downgrade → upgrade) against live Postgres
- Shipped ORM mirror in `app/modules/auth/models.py`: `OtpChannel` Literal TypeAlias, `OtpCode.channel` column, `OtpCode.__table_args__` partial-UNIQUE Index with literal-name + `postgresql_where` text parity
- `alembic check` reports **NO drift on `otp_codes`** (pre-existing deferred drift on `email_send_log` / `*_notifications.channel` / `users.deleted_at` / `users.email` is unrelated to this plan and permitted per `.planning/phases/41-infra-bedrock-anti-oracle-scaffold/deferred-items.md`)
- ruff + mypy strict both clean on `app/modules/auth/models.py`

## Task Commits

Each task was committed atomically:

1. **Task 1: Alembic 0027 — otp_codes.channel discriminator + partial-UNIQUE** — `df15b06` (feat)
2. **Task 2: OtpCode.channel ORM column + __table_args__ partial-UNIQUE** — `4044c13` (feat)

## Files Created/Modified

- `apps/backend/alembic/versions/0027_otp_codes_channel_discriminator.py` (created) — Alembic migration. Revision id `0027_otp_channel_discriminator` (shortened from planned 36-char name to fit varchar(32) `alembic_version.version_num`). `down_revision = '0026_email_send_log'`. Upgrade: `add_column channel TEXT NOT NULL DEFAULT 'telegram'` + `create_check_constraint(op.f('ck_otp_codes_channel'), ...)` + `create_index('uq_otp_codes_user_channel_active', ['user_id','channel'], unique=True, postgresql_where=text("consumed_at IS NULL"))`. Downgrade: symmetric reverse.
- `apps/backend/app/modules/auth/models.py` (modified) — added `from typing import Literal`, `text` import from sqlalchemy, `OtpChannel = Literal["telegram", "email"]` module-level TypeAlias, `OtpCode.channel: Mapped[OtpChannel]` column with `server_default=text("'telegram'")`, new `OtpCode.__table_args__` tuple containing the partial-UNIQUE Index.

## Decisions Made

- **Revision id shortened** — planned name `0027_otp_codes_channel_discriminator` (36 chars) exceeds DB constraint `alembic_version.version_num VARCHAR(32)`. Same shortening discipline as Phase 41 0024 (`0024_notif_channel_discriminator` = 32 chars, dropped "ication" from "notification"). My id: `0027_otp_channel_discriminator` (30 chars). File name kept as planned.
- **No DROP of predecessor partial-UNIQUE** — plan assumed an existing `(user_id) WHERE consumed_at IS NULL` partial-UNIQUE on `otp_codes`. Verified by introspection of both `Base.metadata.tables['otp_codes'].indexes` (empty) and `pg_indexes` (only `pk_otp_codes` + `uq_otp_codes_deep_link_token_hash`). Migration creates the new partial-UNIQUE outright; downgrade drops it symmetrically without recreating a non-existent predecessor. Schema end-state matches the AUTH-EM-01 contract verbatim.
- **`OtpCode.__table_args__` is new** — the OtpCode class previously had no `__table_args__` (only `RefreshToken` had one for `ix_refresh_tokens_user_id_family_id`). The added tuple contains only the new partial-UNIQUE Index — no removal of any pre-existing entry is required, and no other otp_codes-side options (e.g., `Index`/`CheckConstraint`) coexist with it.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Revision id length exceeds DB column limit**
- **Found during:** Task 1 (live `alembic upgrade head` against compose Postgres)
- **Issue:** `UPDATE alembic_version SET version_num='0027_otp_codes_channel_discriminator'` failed with `StringDataRightTruncationError: value too long for type character varying(32)`. Planned id is 36 chars; column is varchar(32).
- **Fix:** Shortened revision id to `0027_otp_channel_discriminator` (30 chars). All five planned grep acceptance criteria using the long name updated implicitly in the file (the file uses the short id consistently; docstring header, `revision: str`, and downgrade are aligned).
- **Files modified:** `apps/backend/alembic/versions/0027_otp_codes_channel_discriminator.py` (filename unchanged; only the revision-id string inside).
- **Verification:** Round-trip `upgrade → downgrade -1 → upgrade` against live Postgres each completed cleanly with the new id.
- **Committed in:** `df15b06` (Task 1 commit).

**2. [Rule 1 — Bug in plan assumption] No predecessor partial-UNIQUE on otp_codes to DROP**
- **Found during:** Task 1 (introspection step explicitly mandated by the plan)
- **Issue:** Plan body specified "DROP existing UNIQUE" and provided a placeholder `_OTP_OLD_UNIQUE` constant. Introspection of `Base.metadata.tables['otp_codes'].indexes` returned `[]`, and `pg_indexes` query returned only `pk_otp_codes` + `uq_otp_codes_deep_link_token_hash`. No partial-UNIQUE on `(user_id) WHERE consumed_at IS NULL` exists in either ORM or live schema. The original `0001_auth.py` migration (lines 53-80) does NOT create such an index.
- **Fix:** Migration body has a single CREATE for the new partial-UNIQUE in `upgrade()` and a single DROP in `downgrade()`. The `_OTP_OLD_UNIQUE` constant is omitted entirely. A module-level deviation note documents the introspection finding and the resulting shape change.
- **Files modified:** `apps/backend/alembic/versions/0027_otp_codes_channel_discriminator.py`.
- **Verification:** `pg_indexes` after upgrade shows the new partial-UNIQUE plus the original two (pk + deep-link). After `downgrade -1`, `pg_indexes` shows only the original two — clean symmetric round-trip. AUTH-EM-01 end-state contract (`UNIQUE (user_id, channel) WHERE consumed_at IS NULL`) matches verbatim.
- **Committed in:** `df15b06` (Task 1 commit).

---

**Total deviations:** 2 auto-fixed (1 blocking — DB column overflow, 1 bug — plan-vs-reality assumption gap).
**Impact on plan:** Both auto-fixes preserve the AUTH-EM-01 contract end-state verbatim. The shorter revision id is purely an internal alembic identifier (filename + docstring header remain readable). The no-predecessor finding is a documented discovery — the migration's resulting schema is identical to what the plan intended.

## Issues Encountered

- **Worktree alembic chain gap:** This plan's `down_revision` is `0026_email_send_log`, which is created by sibling Wave-1 plan 42-01 in a different worktree. My worktree does not contain that file. Resolution: copied the file from the sibling worktree (`/Users/andre/Workspace/Development/clubcore/.claude/worktrees/agent-aeed78af7f33c0f66/apps/backend/alembic/versions/0026_email_send_log.py`) **as an untracked verification-only file** for the duration of testing, then **deleted before commit**. My commits contain only the two planned files (0027 migration + models.py change); cross-worktree integration becomes the orchestrator's job at merge time.
- **Shared compose Postgres is at head `0027_otp_channel_discriminator` after this run.** Other parallel agents may need to be aware. The orchestrator should run `alembic downgrade base && alembic upgrade head` on a clean DB after merge to validate the full chain end-to-end.

## ORM ↔ Migration Parity Confirmation

Per plan output spec:

- **Old partial-UNIQUE name dropped:** _NONE_ — none existed (see deviation #2). Introspection confirmed.
- **New partial-UNIQUE name as shipped:** `uq_otp_codes_user_channel_active` (matches plan's `_OTP_NEW_UNIQUE` constant verbatim).
- **ORM ↔ migration parity on `otp_codes`:** **GREEN.** `alembic check` output (run with the 0026 sibling copy in place) reports no drift entries mentioning `otp_codes` — only the documented pre-existing deferred drift on `email_send_log`, `*_notifications.channel`, `users.deleted_at`, and `users.email` remains.

## Self-Check

- [x] `apps/backend/alembic/versions/0027_otp_codes_channel_discriminator.py` — FOUND (committed in `df15b06`)
- [x] `apps/backend/app/modules/auth/models.py` modified — FOUND (committed in `4044c13`)
- [x] `df15b06` — FOUND in git log
- [x] `4044c13` — FOUND in git log
- [x] Grep checks for Task 1: `revision: str = "0027_otp_channel_discriminator"` (1), `down_revision: str | None = "0026_email_send_log"` (1), `op.add_column` (1), `op.f(` (4), `uq_otp_codes_user_channel_active` (2)
- [x] Grep checks for Task 2: `OtpChannel = Literal["telegram", "email"]` (1), `channel: Mapped[OtpChannel]` (1), `uq_otp_codes_user_channel_active` (1)
- [x] ruff + mypy strict on `app/modules/auth/models.py`: PASS
- [x] Round-trip live Postgres: `upgrade → downgrade -1 → upgrade` clean
- [x] `alembic check` no drift on `otp_codes`

**Self-Check: PASSED**

## Next Phase Readiness

- Wave 2/3 OTP-email service logic (`42-09` request handler, `42-10` verify + anti-oracle) can now read/write `OtpCode.channel` directly. The atomic UPDATE-to-consumed + INSERT-new in same UoW (D-42-22) is unblocked.
- D-42-21 / Alembic 0028 (`users.email_verified`) — sibling plan, no blocker from this plan.
- After orchestrator merges all Wave-1 plans, the full chain 0025 → 0026 → 0027 will be the new head. The shared compose DB head after this run is `0027_otp_channel_discriminator` (the parallel-execution side-effect noted above) — a fresh DB on merge will replay cleanly because each migration is self-contained.

---
*Phase: 42-email-transport-layer-email-otp-fallback*
*Completed: 2026-05-19*
