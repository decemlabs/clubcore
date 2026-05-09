---
phase: 27-expiring-soon-telegram-notifications
plan: 01
subsystem: backend/memberships + planning-docs
tags: [phase-27, alembic, ddl, idempotency-table, audit-docstring, ntf-01, ntf-06]
requires:
  - "0009_renewal alembic head (Phase 26)"
  - "memberships.id PK (FK target)"
  - "Base + UUIDPkMixin + TimestampMixin (app.core.database)"
  - "LOCKED_AUDIT_EVENTS frozenset already pre-registered Phase 24 (3 expiring_notification_sent_* pairs)"
provides:
  - "membership_notifications table (DDL via 0010_notifications.py)"
  - "MembershipNotification ORM class (mirrors migration columns + constraints + index)"
  - "EXPIRING_KIND_7D / _3D / _1D string literals + EXPIRING_KINDS tuple in memberships.constants"
  - "Updated audit.py docstring sketch for expiring_notification_sent_{7d,3d,1d} matching real Phase 27 payload"
  - "Three planning-doc wording fixes (REQUIREMENTS / ROADMAP / milestone v1.3-ROADMAP) referencing 0010_notifications.py"
affects:
  - "Wave 2 of Phase 27 (plan 27-02 repository / service can now reference MembershipNotification + EXPIRING_KIND_*)"
  - "Wave 2 of Phase 27 (plan 27-03 telegram copy module — independent; not blocked but co-arrives)"
  - "Wave 3 of Phase 27 (plan 27-04 worker file uses cron registration patterns — unchanged here)"
tech-stack:
  added: []
  patterns:
    - "Alembic migration follows 0008_freeze.py multi-table create_table + UNIQUE + index shape"
    - "ORM CheckConstraint name='kind' relies on NAMING_CONVENTION expansion (mirrors Membership status/activation_policy pattern)"
    - "ORM mirrors migration index for `alembic check` cleanliness"
    - "Audit docstring drift closed at lock-time (mirrors Phase 26 D-26-26 closure pattern)"
key-files:
  created:
    - "apps/backend/alembic/versions/0010_notifications.py"
  modified:
    - "apps/backend/app/modules/memberships/models.py"
    - "apps/backend/app/modules/memberships/constants.py"
    - "apps/backend/app/core/audit.py"
    - ".planning/REQUIREMENTS.md"
    - ".planning/ROADMAP.md"
    - ".planning/milestones/v1.3-ROADMAP.md"
decisions:
  - "ORM CheckConstraint `name='kind'` (short form, NAMING_CONVENTION expands to ck_membership_notifications_kind) instead of plan's `name='ck_membership_notifications_kind'` — short form matches the existing Membership/MembershipPlan pattern and keeps DB constraint names byte-stable"
  - "Added Index() entry to MembershipNotification.__table_args__ mirroring ix_membership_notifications_membership_id from migration to keep `alembic check` clean (caught by tests/integration/test_alembic_clean.py)"
metrics:
  duration: "7m34s"
  tasks_completed: 5
  files_changed: 6
  commits: 6
  completed_date: "2026-05-09"
---

# Phase 27 Plan 01: Notifications schema + literals foundation Summary

**One-liner:** Alembic migration `0010_notifications.py` creates `membership_notifications` idempotency table (UNIQUE on `(membership_id, kind)`); ORM, kind-literal constants, audit docstring, and three doc-wording fixes all land atomically.

## Changes Delivered

### 1. Migration `0010_notifications.py` (new file, 110 lines)

- Revision identifiers: `revision: str = "0010_notifications"`, `down_revision: str | None = "0009_renewal"`.
- `upgrade()` executes:
  1. `op.create_table("membership_notifications", ...)` with columns `id` (UUID PK, `gen_random_uuid()`), `membership_id` (UUID FK CASCADE), `kind` (String(16)), `sent_at` (TIMESTAMPTZ default `now()`), `telegram_chat_id` (BigInteger), `created_at` + `updated_at` (TimestampMixin parity).
  2. Inline `CheckConstraint("kind IN ('expiring_7d', 'expiring_3d', 'expiring_1d')", name=op.f("ck_membership_notifications_kind"))`.
  3. `op.create_unique_constraint("uq_membership_notifications_membership_kind", ...)` — explicit literal name (not op.f()) per D-27-02. Single source of truth for cron idempotency.
  4. `op.create_index(op.f("ix_membership_notifications_membership_id"), ...)` — forensic per-membership lookup.
- `downgrade()` reverses: drop_index → drop_constraint → drop_table.
- Round-trip verified: `alembic upgrade head` → `downgrade -1` → `upgrade head` all exit 0.

### 2. ORM class `MembershipNotification` (appended to `apps/backend/app/modules/memberships/models.py`)

- Composition: `Base, UUIDPkMixin, TimestampMixin` (no SoftDeleteMixin — append-only rows; UNIQUE is the idempotency truth).
- Columns: `membership_id` (FK CASCADE), `kind` (String(16)), `sent_at` (TIMESTAMPTZ server_default now()), `telegram_chat_id` (BigInteger).
- `__table_args__`:
  - `CheckConstraint("kind IN ('expiring_7d', 'expiring_3d', 'expiring_1d')", name="kind")` → NAMING_CONVENTION expands to `ck_membership_notifications_kind` (matches DB).
  - `UniqueConstraint("membership_id", "kind", name="uq_membership_notifications_membership_kind")` (explicit literal).
  - `Index("ix_membership_notifications_membership_id", "membership_id")` (mirrors migration; required for `alembic check` cleanliness).
- Added `UniqueConstraint` to existing sqlalchemy import block.
- Confirmed via runtime `inspect(...)` that the four DB constraint names are byte-equal to ORM-side names.

### 3. `EXPIRING_KIND_*` constants in `apps/backend/app/modules/memberships/constants.py`

- Long-form per REQUIREMENTS NTF-01:
  - `EXPIRING_KIND_7D = "expiring_7d"`
  - `EXPIRING_KIND_3D = "expiring_3d"`
  - `EXPIRING_KIND_1D = "expiring_1d"`
  - `EXPIRING_KINDS: tuple[str, ...] = (EXPIRING_KIND_7D, EXPIRING_KIND_3D, EXPIRING_KIND_1D)`
- `__all__` extended (isort-sorted order applied automatically by ruff RUF022 fix).

### 4. Audit docstring drift closure (`apps/backend/app/core/audit.py:67-74`)

Before:
```
- expiring_notification_sent_7d       {membership_id, client_id, channel}
                                      # 'membership' (Phase 27 — 7-day reminder, ARQ)
... (×3)
```

After:
```
- expiring_notification_sent_7d       {client_id, telegram_chat_id, kind, channel}
                                      # 'membership' (Phase 27 — 7-day reminder, ARQ;
                                      # resource_id = membership.id; kind="expiring_7d";
                                      # channel="telegram")
... (×3)
```

Real Phase 27 service callsite payload (per D-27-12) is now reflected in the docstring sketch. `LOCKED_AUDIT_EVENTS` frozenset is untouched (Phase 24 lock preserved).

### 5. Planning-doc wording fixes (D-27-01)

| File | Line | Before | After |
|------|------|--------|-------|
| `.planning/REQUIREMENTS.md` | NTF-01 (line 54) | `0008_notifications.py` | `0010_notifications.py` |
| `.planning/ROADMAP.md` | Phase 27 SC #1 (line 124) | `0009_notifications.py` | `0010_notifications.py` |
| `.planning/milestones/v1.3-ROADMAP.md` | Phase 27 'Depends on' (line 61) | `миграция 0009 идёт после 0008` | `миграция 0010 идёт после 0009` |
| `.planning/milestones/v1.3-ROADMAP.md` | Phase 27 SC #1 (line 64) | `0009_notifications.py` | `0010_notifications.py` |
| `.planning/milestones/v1.3-ROADMAP.md` | Notes on dependencies (line 126) | `migration 0009 must come after 0008` | `migration 0010 must come after 0009` |

Phase 25/26 references to `0008` / `0008_freeze` (line 125) intentionally preserved.

## Verification

- `cd apps/backend && uv run alembic upgrade head` → exit 0 (applies 0010 cleanly).
- `cd apps/backend && uv run alembic downgrade -1 && uv run alembic upgrade head` → exit 0 (round-trip).
- `cd apps/backend && uv run alembic check` → "No new upgrade operations detected." (drift-clean).
- `cd apps/backend && uv run ruff check app/modules/memberships/ app/core/audit.py` → All checks passed.
- `cd apps/backend && uv run mypy app/modules/memberships/models.py app/modules/memberships/constants.py` → No issues.
- `cd apps/backend && uv run pytest tests/unit/test_audit_taxonomy.py -x` → 4 passed.
- `cd apps/backend && uv run pytest` → **709 passed** (full backend suite green).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] CheckConstraint name expansion mismatch**
- **Found during:** Task 2 verification (post-write `inspect` call)
- **Issue:** Plan `<action>` block specified `CheckConstraint(..., name="ck_membership_notifications_kind")` but the project's `NAMING_CONVENTION` ck-template `ck_%(table_name)s_%(constraint_name)s` would have produced `ck_membership_notifications_ck_membership_notifications_kind` (double-prefixed) — drift vs DB which has `ck_membership_notifications_kind` from `op.f()`.
- **Fix:** Used short form `name="kind"`; NAMING_CONVENTION expands to the correct `ck_membership_notifications_kind`. This mirrors the existing `Membership` and `MembershipPlan` `CheckConstraint` pattern (`name="status"`, `name="duration_days_positive"`, etc.) and is what PATTERNS.md actually shows (line 352-353).
- **Files modified:** `apps/backend/app/modules/memberships/models.py`
- **Commit:** `0ad042e`

**2. [Rule 1 - Bug] `alembic check` drift on forensic index**
- **Found during:** Full-suite run (`tests/integration/test_alembic_clean.py::test_alembic_check_clean`)
- **Issue:** Migration `0010_notifications.py` creates `ix_membership_notifications_membership_id`, but the initial ORM `__table_args__` only declared the CHECK + UNIQUE constraints. `alembic check` flagged `remove_index` as a drift operation, failing the integration drift-gate test.
- **Fix:** Added `Index("ix_membership_notifications_membership_id", "membership_id")` to `MembershipNotification.__table_args__`. Mirrors what migration creates; `alembic check` now reports "No new upgrade operations detected."
- **Files modified:** `apps/backend/app/modules/memberships/models.py`
- **Commit:** `cf27c4b`

**3. [Rule 1 - Bug] `__all__` not isort-sorted (RUF022)**
- **Found during:** Task 3 verification (`ruff check`)
- **Issue:** Adding new `EXPIRING_KIND_*` entries to `__all__` triggered `RUF022 __all__ is not sorted` (existing entries were alphabetic; appending broke order).
- **Fix:** Applied `ruff check --fix` which produced isort-style ordering (`EXPIRING_KINDS` before `EXPIRING_KIND_1D` per dictionary order on the underscore character).
- **Files modified:** `apps/backend/app/modules/memberships/constants.py`
- **Commit:** `f73aee0`

No architectural deviations (no Rule 4 events). No authentication gates encountered. No deferred items.

## Commits (in order)

| Task | Commit | Message head |
|------|--------|--------------|
| 1 | `d4163c7` | `feat(27-01): add migration 0010_notifications membership idempotency table` |
| 2 | `0ad042e` | `feat(27-01): add MembershipNotification ORM class mirroring 0010 migration` |
| 3 | `f73aee0` | `feat(27-01): add EXPIRING_KIND_* literal constants for Phase 27` |
| 4 | `f2e9134` | `docs(27-01): close Phase 27 audit docstring drift to match real payload` |
| 5 | `80b0fb1` | `docs(27-01): correct Phase 27 migration references 0008/0009 -> 0010 (D-27-01)` |
| Rule 1 fix | `cf27c4b` | `fix(27-01): mirror ix_membership_notifications_membership_id in ORM __table_args__` |

## Threat Flags

None — no new HTTP endpoints, no new auth boundaries, no new file-system access. The new column `membership_notifications.telegram_chat_id` (BIGINT) is already covered by T-27-01-02 in the plan threat register (severity LOW, accept disposition).

## Self-Check: PASSED

- File `apps/backend/alembic/versions/0010_notifications.py` exists.
- File `apps/backend/app/modules/memberships/models.py` modified (MembershipNotification class added).
- File `apps/backend/app/modules/memberships/constants.py` modified (EXPIRING_KIND_* added).
- File `apps/backend/app/core/audit.py` modified (docstring drift closed).
- File `.planning/REQUIREMENTS.md` modified (NTF-01 wording fixed).
- File `.planning/ROADMAP.md` modified (Phase 27 SC #1 wording fixed).
- File `.planning/milestones/v1.3-ROADMAP.md` modified (3 wording fixes).
- All 6 commits exist in `git log` (`d4163c7`, `0ad042e`, `f73aee0`, `f2e9134`, `80b0fb1`, `cf27c4b`).
- Backend full test suite: 709 passed.
- `alembic check`: clean.
