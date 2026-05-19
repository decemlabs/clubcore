---
phase: 42-email-transport-layer-email-otp-fallback
plan: 04
subsystem: auth / users-schema
tags:
  - migration
  - orm
  - users
  - email-verified
  - auth-em-02
requires:
  - 0027_otp_codes_channel_discriminator (Wave-1 sibling plan 42-03 — referenced as down_revision)
provides:
  - users.email_verified BOOLEAN NOT NULL DEFAULT FALSE
  - User.email_verified Mapped[bool] ORM column
affects:
  - Wave-3 plan 42-09 service `request_otp_email` (reads user.email_verified as part of the 3-way eligibility guard)
  - Phase 43 USERS module (will ship the verify-flow set side — open conflict #7)
tech-stack:
  added: []
  patterns:
    - "Alembic single-column add via op.add_column + sa.Column(nullable=False, server_default=sa.text('FALSE'))"
    - "ORM column mirror with Mapped[bool] + mapped_column(Boolean, nullable=False, server_default=text('FALSE'))"
key-files:
  created:
    - apps/backend/alembic/versions/0028_users_email_verified.py
  modified:
    - apps/backend/app/core/models.py
decisions:
  - "D-42-21 honored verbatim: bootstrap-runbook comment carried in migration docstring (UPDATE users SET email_verified=TRUE WHERE email='<owner_email>')"
  - "D-42-22 anti-oracle invariant called out in the migration docstring so future schema-archaeologists understand WHY a column lands with FALSE default (read-side returns identical 202 shape whether unverified, unknown, or inactive)"
  - "Phase-41-deferred drift on User.email UNIQUE + missing User.deleted_at ORM mapping deliberately NOT addressed — Phase 43 USERS module owns per deferred-items.md (out of scope of plan 42-04)"
metrics:
  duration: ~3 minutes
  completed: 2026-05-19
---

# Phase 42 Plan 04: users.email_verified column + ORM Summary

Adds the read-side schema half of AUTH-EM-02 — `users.email_verified BOOLEAN NOT NULL DEFAULT FALSE` — via Alembic migration 0028 and a single matching ORM column on `app.core.models.User`. Wave 3 plan 42-09 consumes it as part of the email-OTP eligibility guard; Phase 43 (open conflict #7) will ship the corresponding verify-flow set side.

## Tasks Completed

| Task | Name                                            | Commit  | Files                                                                |
| ---- | ----------------------------------------------- | ------- | -------------------------------------------------------------------- |
| 1    | Alembic 0028 — users.email_verified column      | 8c09c19 | apps/backend/alembic/versions/0028_users_email_verified.py (created) |
| 2    | User.email_verified ORM column add              | 78e5f11 | apps/backend/app/core/models.py (modified)                            |

## Implementation Details

### Migration `0028_users_email_verified.py`

- `revision = "0028_users_email_verified"`
- `down_revision = "0027_otp_codes_channel_discriminator"` (Wave-1 sibling plan 42-03)
- `upgrade()`: `op.add_column("users", sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")))`
- `downgrade()`: `op.drop_column("users", "email_verified")`
- No CHECK constraint (Boolean type is its own constraint); no index; no partial-UNIQUE.
- Module docstring carries the **D-42-21 bootstrap-runbook verbatim** — the operator flips the owner row via direct SQL after migration lands; the OWNER's first email-OTP login becomes Phase 43's first verify-flow consumer.
- Anti-oracle preservation (D-42-22) called out in the docstring: when `channel='email'` and the eligibility guard rejects (user missing / inactive / `email_verified=FALSE`), the response is the **identical 202 shape** with a constant-time floor sleep — no oracle leak.

### ORM column `User.email_verified` in `app/core/models.py`

- **Exact insertion location:** immediately **after** `email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)` and **before** `password_hash: Mapped[str] = mapped_column(Text, nullable=False)` — adjacent to the email/role/full_name block as the plan specified.
- Column declaration:
  ```python
  email_verified: Mapped[bool] = mapped_column(
      Boolean,
      nullable=False,
      server_default=text("FALSE"),
  )
  ```
- Added `Boolean` and `text` to the existing `from sqlalchemy import ...` line — `Mapped` and `mapped_column` were already imported.
- **Pre-existing Phase-41-deferred ORM drift intentionally left UNRESOLVED** (Phase 43 owns per `.planning/phases/41-infra-bedrock-anti-oracle-scaffold/deferred-items.md`):
  - `User.email` still declares `unique=True` (migration 0022 already replaced the global UNIQUE with a partial-UNIQUE index on `lower(email) WHERE deleted_at IS NULL`).
  - `User.deleted_at` ORM mapping is still missing (migration 0022 added the column).
  Neither line was touched in this plan.

## Verification Results

| Check                                                                                    | Status        |
| ---------------------------------------------------------------------------------------- | ------------- |
| `grep -c 'revision: str = "0028_users_email_verified"'`                                  | 1 ✓           |
| `grep -c 'down_revision: str \| None = "0027_otp_codes_channel_discriminator"'`          | 1 ✓           |
| `grep -c "BOOTSTRAP RUNBOOK"`                                                            | 1 ✓           |
| `grep -c "UPDATE users SET email_verified = TRUE"`                                       | 1 ✓           |
| `grep -c "op.add_column"`                                                                | 1 ✓           |
| `grep -c "email_verified: Mapped\[bool\]"` in models.py                                  | 1 ✓           |
| `grep -c 'server_default=text("FALSE")'` in models.py                                    | 1 ✓           |
| `grep "email.*unique"` in models.py (must still be `unique=True`)                        | preserved ✓   |
| `uv run ruff check apps/backend/alembic/versions/0028_users_email_verified.py`           | passes ✓      |
| `uv run mypy --strict apps/backend/alembic/versions/0028_users_email_verified.py`        | passes ✓      |
| `uv run ruff check apps/backend/app/core/models.py`                                      | passes ✓      |
| `uv run mypy --strict apps/backend/app/core/models.py`                                   | passes ✓      |
| In-process ORM metadata check (`Base.metadata.tables['users'].columns['email_verified']`)| Boolean, NOT NULL, default=`FALSE` ✓ |

## Deferred (post-merge) verification

The following plan-level verify steps require a live Postgres instance and the sibling Wave-1 migrations (0026, 0027) to be present. They are intentionally NOT executed in this parallel worktree because:

1. The worktree has no Postgres connection (no `DATABASE_URL` populated).
2. Migrations 0026 and 0027 are produced by sibling plans 42-01 / 42-03 in the same wave and only co-exist after the orchestrator merges the wave.

Deferred steps (orchestrator post-merge):

- `cd apps/backend && uv run alembic upgrade head` (round-trip)
- `cd apps/backend && uv run alembic downgrade -1`
- `cd apps/backend && uv run alembic upgrade head` (re-apply)
- `cd apps/backend && uv run alembic check 2>&1` — MUST NOT mention `email_verified` (pre-existing drift on `users.email` UNIQUE + `users.deleted_at` is permitted and documented).
- `cd apps/backend && uv run pytest tests/test_alembic_clean.py`
- `information_schema.columns` query asserting `data_type='boolean'`, `is_nullable='NO'`, `column_default` contains `'false'`.

The static + in-process subset of the verify suite IS green locally; the DB-bound subset will be re-run by the orchestrator after wave-1 merge per parallel-execution contract.

## Deviations from Plan

None — plan executed exactly as written. Static checks all pass; DB-bound checks deferred to the orchestrator post-merge per parallel-executor contract.

## Decisions Made

- **Preserve Phase-41-deferred drift as instructed.** The plan's `<read_first>` flagged the `User.email unique=True` and missing `User.deleted_at` drift as Phase 43 scope. Plan 42-04 added exactly one column and touched nothing else in the `User` class — no proactive cleanup, no Rule-2 invocation, no scope creep.
- **No CHECK constraint on `email_verified`.** Boolean is its own constraint; mirrors Phase 41 0023 audit-snapshot precedent for plain boolean / nullable columns.
- **Server-side default mirrored in BOTH migration AND ORM** so a `Base.metadata.create_all()` test path (rare but possible in unit tests that spin up SQLite in-memory) does not need application-level patching to round-trip the column.

## Threat Flags

No new security-relevant surface introduced beyond what `<threat_model>` already enumerated (T-42-04-01..03 all addressed by the column's existence + downstream Wave-3 read-side guard).

## Self-Check: PASSED

- File `apps/backend/alembic/versions/0028_users_email_verified.py` exists ✓
- File `apps/backend/app/core/models.py` exists ✓
- Commit `8c09c19` present in `git log --oneline --all` ✓
- Commit `78e5f11` present in `git log --oneline --all` ✓
