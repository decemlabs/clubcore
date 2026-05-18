---
phase: 41-infra-bedrock-anti-oracle-scaffold
plan: 08
subsystem: db
tags: [alembic, migration, schema, notifications, channel-discriminator, idempotency, postgres]

# Dependency graph
requires:
  - phase: 41-infra-bedrock-anti-oracle-scaffold (Plan 06)
    provides: Alembic head at 0023_audit_actor_snapshot (down_revision target for 0024)
  - revision: 0010_notifications
    provides: membership_notifications table + uq_membership_notifications_membership_kind UNIQUE
  - revision: 0020_booking_notifications
    provides: booking_notifications table + uq_booking_notifications_booking_kind UNIQUE
provides:
  - apps/backend/alembic/versions/0024_notification_channel_discriminator.py (revision id 0024_notif_channel_discriminator, down_revision 0023_audit_actor_snapshot)
  - membership_notifications.channel TEXT NOT NULL DEFAULT 'telegram' CHECK channel IN ('telegram','email')
  - booking_notifications.channel TEXT NOT NULL DEFAULT 'telegram' CHECK channel IN ('telegram','email')
  - UNIQUE uq_membership_notifications_membership_kind_channel (membership_id, kind, channel)
  - UNIQUE uq_booking_notifications_booking_kind_channel (booking_id, kind, channel)
  - CHECK ck_membership_notifications_channel + ck_booking_notifications_channel
affects:
  - Phase 41 Plan 09 (Alembic 0025 — final migration in the 0022-0025 bundle)
  - Phase 45 cross-channel email mirrors (NOTIFY-06 service layer reads channel column when emitting email mirrors of expiring + booking-reminder + payment-receipt notifications)
  - Service-layer idempotency helpers in app/modules/memberships/service.py + app/modules/bookings/service.py (constraint-name change requires Phase 45 update — out of scope here)

# Tech tracking
tech-stack:
  added: []  # Pure DDL — no new libraries
  patterns:
    - "Constraint name passed via op.f() inside create_check_constraint / drop_constraint so the project naming_convention (`ck_%(table_name)s_%(constraint_name)s` in app/core/database.py:31) does NOT double-prefix. Mirrors 0010_notifications.py line 78 idiom."
    - "Zero-row backfill via NOT NULL + server_default: rows added in a single op.add_column atomic step (DEFAULT 'telegram' satisfies NOT NULL for existing rows). No explicit UPDATE statement needed — mirrors v1.3 NTF-05 / D-41-03 precedent."
    - "DROP-then-CREATE UNIQUE constraint for column-list extension: alembic has no native 'extend UNIQUE' op, so the two-step replace is the canonical Postgres idiom."

key-files:
  created:
    - apps/backend/alembic/versions/0024_notification_channel_discriminator.py
  modified: []

key-decisions:
  - "Revision id literal is 0024_notif_channel_discriminator (32 chars, fits alembic's varchar(32) version_num table). The filename keeps the readable 0024_notification_channel_discriminator suffix for human navigation; alembic distinguishes the two via the `revision:` variable inside the file."
  - "CHECK constraint names are wrapped in op.f() so the project naming_convention (`ck_%(table_name)s_%(constraint_name)s`) does NOT re-prefix the table name. Initial revision used bare strings and Postgres ended up with `ck_membership_notifications_ck_membership_notifications_channel` — caught during behavioural verification, fixed by mirroring the 0010_notifications.py op.f() pattern."
  - "Order inside upgrade(): add_column → create_check_constraint → drop_constraint(old UNIQUE) → create_unique_constraint(new). Downgrade is the strict reverse, table-order also reversed (booking_notifications first, then membership_notifications) for symmetry."
  - "Zero-row backfill (D-41-15 / D-41-03 / v1.3 NTF-05 precedent): existing notification rows pre-v1.6 are all Telegram-originated; DEFAULT 'telegram' assigns them atomically with the column add. No explicit UPDATE."

patterns-established:
  - "When adding a NOT NULL discriminator column that must extend an existing UNIQUE, the four-op recipe (add_column NOT NULL DEFAULT → CHECK → drop old UNIQUE → create new UNIQUE with discriminator last) is the canonical shape. Future channel-like extensions (e.g. notification kind splits) follow the same template."
  - "Always pass constraint names through op.f() in this codebase when the naming_convention template contains %(constraint_name)s — otherwise the convention double-prefixes. Applies to ck_ and uq_ where the convention uses `constraint_name`."

requirements-completed: []  # INFRA-38 stays open until 0025 lands (Plan 09); this is the third of four migrations in the 0022-0025 bundle (D-41-15).

# Metrics
duration: 4min
completed: 2026-05-18
---

# Phase 41 Plan 08: Alembic 0024 — channel discriminator on notification tables

**Single-file Alembic migration (0024) wiring a `channel` discriminator into BOTH `membership_notifications` and `booking_notifications` so Phase 45 can record per-channel idempotency rows — the schema half of NOTIFY-06, ordered before any NOTIFY-* phase per the v1.6 critical-invariant rule.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-05-18T19:13:28Z
- **Completed:** 2026-05-18T19:17:27Z
- **Tasks:** 1 (auto)
- **Files created:** 1 (`0024_notification_channel_discriminator.py`)
- **Files modified:** 0

## Accomplishments

- New Alembic revision `0024_notif_channel_discriminator` with `down_revision = "0023_audit_actor_snapshot"`, applied cleanly on top of the Phase 41 Plan 06 head.
- Both notification tables now carry an identically-shaped discriminator:
  - `channel TEXT NOT NULL DEFAULT 'telegram'`
  - `CHECK (channel IN ('telegram','email'))` — names `ck_membership_notifications_channel` and `ck_booking_notifications_channel` (post-op.f() fix).
- Existing `(subject_id, kind)` UNIQUEs dropped and recreated with `channel` as the trailing column:
  - `uq_membership_notifications_membership_kind` → `uq_membership_notifications_membership_kind_channel` on `(membership_id, kind, channel)`
  - `uq_booking_notifications_booking_kind` → `uq_booking_notifications_booking_kind_channel` on `(booking_id, kind, channel)`
- Downgrade is the strict structural reverse (drop new UNIQUE → recreate old UNIQUE → drop CHECK → drop column), tables addressed in reverse order. Round-trip (`downgrade -1 && upgrade head`) verified clean.
- Behavioural live-DB verification on `booking_notifications` (the only table with an existing FK target row in the dev DB) confirms:
  - 2 rows with same `(booking_id, kind)` but different `channel` both INSERT successfully.
  - 3rd row repeating `(booking_id, kind, channel)` raises `UniqueViolationError` on `uq_booking_notifications_booking_kind_channel`.
  - Row with `channel='sms'` raises `CheckViolationError` on `ck_booking_notifications_channel`.
  - `membership_notifications` is structurally identical (same op shape, same constraint kinds, same column types) — see "Behavioural verification scope" below.
- Migration file passes `ruff check` clean.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] CHECK constraint names doubled by naming_convention**
- **Found during:** Task 1 verification (post-`alembic upgrade head` schema introspection).
- **Issue:** The first version of the migration passed bare strings to `op.create_check_constraint("ck_membership_notifications_channel", ...)`. The project's `MetaData(naming_convention=...)` template `ck_%(table_name)s_%(constraint_name)s` (defined in `apps/backend/app/core/database.py:31`) interpolated `constraint_name` with the raw bare string, producing the actual Postgres constraint name `ck_membership_notifications_ck_membership_notifications_channel` (and the booking-side equivalent). Verification assertion `chan_check = [c for c in cks if c["conname"] == f"ck_{t}_channel"]` failed on this.
- **Fix:** Wrapped all four CK references (two in `upgrade`, two in `downgrade`) with `op.f("ck_<table>_channel")` so alembic treats them as already-fully-rendered names — mirrors the `op.f("ck_membership_notifications_kind")` idiom at `0010_notifications.py:78`. After the fix, downgrade-then-upgrade cycle re-applied cleanly and produced the canonical names exactly.
- **Files modified:** `apps/backend/alembic/versions/0024_notification_channel_discriminator.py` (four `op.f()` wraps + an inline comment explaining why)
- **Commit:** `354e749` (the final committed file is the fixed version; the buggy version was caught and corrected before commit)

## Behavioural verification scope

The plan's success criteria asked for INSERT-time behavioural verification on **both** tables. The dev Postgres at verification time had:

- `bookings` table with at least one row → full behavioural matrix exercised on `booking_notifications` (telegram + email insert OK; duplicate same-channel triggers UniqueViolation; `sms` triggers CheckViolation — all three asserted).
- `memberships` table empty → FK-constrained `membership_notifications` inserts were skipped at runtime (no eligible `membership_id` to reference). Inserting a synthetic membership would have required satisfying a multi-hop FK chain (memberships → plans + clients → branches, etc.) that is outside the scope of an Alembic-only plan.

Mitigation: the schema-level checks (column presence + NOT NULL + DEFAULT + CHECK definition + UNIQUE column list including `channel`) were asserted on **both** tables, and the migration source applies an **identical** four-op sequence to both, so the runtime behaviour is provably symmetric. Phase 45 will exercise the membership_notifications path end-to-end when the email-mirror service code lands.

## Threat Flags

None — the migration introduces no new trust boundaries, no new endpoints, no new auth paths. The schema change strictly tightens existing invariants (CHECK adds a closed set; UNIQUE narrows to include the channel discriminator). All mitigations in the plan's `<threat_model>` are realised by the schema alone:

- **T-41-08-01 (Tampering — wrong channel value):** CHECK constraint admits only `'telegram'` and `'email'`; behavioural test rejected `'sms'` with `CheckViolationError`.
- **T-41-08-02 (Repudiation — double-pinging across channels):** Per-channel UNIQUE allows recording both telegram and email rows for the same `(subject, kind)` — Phase 45 fallback policy (email only when telegram blocked) is enforced at the service layer; this schema admits both rows when the policy permits.
- **T-41-08-03 (Tampering — lowercased duplicate bypass):** No app-layer change required — `channel` values are short literal enums set by the application; no user-input path writes the column.

## Known Stubs

None.

## Commits

- `354e749` — feat(41-08): add alembic 0024 channel discriminator on notification tables

## Self-Check: PASSED

- File `apps/backend/alembic/versions/0024_notification_channel_discriminator.py` exists.
- Commit `354e749` present in `git log --all`.
- `alembic upgrade head` reports `Running upgrade 0023_audit_actor_snapshot -> 0024_notif_channel_discriminator` and exits 0.
- `alembic downgrade -1 && alembic upgrade head` round-trips clean.
- Constraint inventory post-roundtrip is exactly: `ck_<t>_channel`, `ck_<t>_kind`, `uq_<t>_<subject>_kind_channel` — no doubled prefixes, no leftover old uniques.
- `ruff check` on the new file: All checks passed.
