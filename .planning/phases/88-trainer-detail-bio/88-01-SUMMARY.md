---
phase: 88-trainer-detail-bio
plan: 01
subsystem: database
tags: [sqlalchemy, alembic, pydantic, postgres, trainers]

requires:
  - phase: 87-notification-inbox
    provides: migration head 0061_client_push_tokens (down_revision anchor for 0062)

provides:
  - "Trainer ORM columns: bio, specialization, photo_url (nullable Text)"
  - "TrainerUpdateRequest extended with bio/specialization/photo_url (owner-write, max_length=2048 on photo_url)"
  - "TrainerResponse extended with bio/specialization/photo_url (read echo)"
  - "DDL migration 0062_trainer_profile_fields (add_column on trainers table)"
  - "Idempotent seed migration 0063_seed_trainer_profiles (six PWA trainers backfilled)"

affects: [88-02-endpoints, 88-03-pwa, client_portal schemas Plan 02]

tech-stack:
  added: []
  patterns:
    - "Nullable Text column added via add_column (no server_default, no CHECK constraint — free text)"
    - "Idempotent UPDATE seed migration via sa.text().bindparams() — re-running sets identical values"
    - "photo_url max_length=2048 at DTO boundary only; scheme validation deferred to render layer"

key-files:
  created:
    - apps/backend/alembic/versions/0062_trainer_profile_fields.py
    - apps/backend/alembic/versions/0063_seed_trainer_profiles.py
  modified:
    - apps/backend/app/modules/trainers/models.py
    - apps/backend/app/modules/trainers/schemas.py

key-decisions:
  - "D-88-01-PHOTO-URL-LENGTH: max_length=2048 on TrainerUpdateRequest.photo_url only (write boundary); TrainerResponse has no length cap (read-only echo of DB value); scheme validation at render layer (Plan 03)"
  - "D-88-01-SEED-STRATEGY: UPDATE WHERE full_name = :name AND deleted_at IS NULL — idempotent because re-setting identical values is a no-op side-effect; photo_url left NULL (owner sets later via PATCH)"
  - "D-88-01-NO-CREATE-FIELDS: TrainerCreateRequest not modified — owner sets profile via PATCH only (TRNR-02 decision)"

patterns-established:
  - "Three-column nullable Text extension: copy phone-column pattern (Mapped[str | None] = mapped_column(Text, nullable=True))"
  - "RUF001 noqa markers on intentional Cyrillic strings in seed migrations (matches 0059_seed_gym_info.py precedent)"

requirements-completed: [TRNR-01, TRNR-02, TRNR-03]

duration: 15min
completed: 2026-06-06
---

# Phase 88 Plan 01: Trainer Profile Fields Summary

**Three nullable Text columns (bio/specialization/photo_url) added to Trainer ORM + schemas + migration chain 0062→0063 with idempotent six-trainer backfill**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-06-06T11:01:42Z
- **Completed:** 2026-06-06T11:17:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Extended `Trainer` ORM with three nullable Text columns (bio, specialization, photo_url) following the `phone` column pattern
- Extended `TrainerUpdateRequest` (owner-write) and `TrainerResponse` (read echo) with the three fields; `extra='forbid'` mass-assignment guard (T-88-04) intact; `TrainerCreateRequest` untouched
- DDL migration 0062 applies three `op.add_column` calls on `trainers` table; round-trip downgrade/upgrade clean
- Idempotent seed migration 0063 backfills specialization + bio for all six PWA trainers (Аня Соколова, Марк Левин, Лиза Орлова, Денис Кравцов, Соня Бек, Игорь Раш); photo_url left NULL per owner-PATCH-only decision
- `alembic upgrade head` twice = clean no-op; `alembic check` reports no pending diff

## Task Commits

1. **Task 1: Add bio/specialization/photo_url to Trainer model + schemas** — `a1fe392c` (feat)
2. **Task 2: DDL migration 0062 + idempotent seed migration 0063** — `9732b255` (feat)

## Files Created/Modified

- `apps/backend/app/modules/trainers/models.py` — three new nullable Text columns after `is_active`
- `apps/backend/app/modules/trainers/schemas.py` — bio/specialization/photo_url added to both `TrainerUpdateRequest` and `TrainerResponse`
- `apps/backend/alembic/versions/0062_trainer_profile_fields.py` — DDL add_column migration, down_revision=0061_client_push_tokens
- `apps/backend/alembic/versions/0063_seed_trainer_profiles.py` — idempotent UPDATE backfill, down_revision=0062_trainer_profile_fields

## Decisions Made

- **D-88-01-PHOTO-URL-LENGTH:** `max_length=2048` on `TrainerUpdateRequest.photo_url` only (write boundary enforcement, T-88-05 mitigation). `TrainerResponse` carries no length cap — it echoes the DB value read-only. URL scheme validation deferred to PWA render layer (Plan 03).
- **D-88-01-SEED-STRATEGY:** `UPDATE WHERE full_name = :name AND deleted_at IS NULL` — idempotent because re-running sets identical values. No `WHERE bio IS NULL` guard needed. `photo_url` stays NULL — owner sets it via PATCH later.
- **D-88-01-NO-CREATE-FIELDS:** `TrainerCreateRequest` not modified — per TRNR-02 the owner sets profile fields via PATCH only.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed I001 import-sort in new migration files**
- **Found during:** Task 2 verification (ruff check)
- **Issue:** `from alembic import op` placed before `from collections.abc import Sequence` — violated isort ordering
- **Fix:** `uv run ruff check --fix` auto-sorted import blocks in both 0062 and 0063
- **Files modified:** `alembic/versions/0062_trainer_profile_fields.py`, `alembic/versions/0063_seed_trainer_profiles.py`
- **Verification:** `ruff check` exits 0 after fix
- **Committed in:** `9732b255` (Task 2 commit)

**2. [Rule 1 - Bug] Added RUF001 noqa markers for intentional Cyrillic strings**
- **Found during:** Task 2 verification (ruff check)
- **Issue:** Three strings in 0063 seed data contain Cyrillic letters visually similar to ASCII (М/А in "ММА", с in bio text) — ruff RUF001 flagged them
- **Fix:** Added `# noqa: RUF001` to the three affected string lines; matches 0059_seed_gym_info.py precedent (same pre-existing pattern in existing migrations)
- **Files modified:** `alembic/versions/0063_seed_trainer_profiles.py`
- **Verification:** `ruff check` exits 0 after markers added
- **Committed in:** `9732b255` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 × Rule 1 - Bug)
**Impact on plan:** Both fixes are lint correctness; no behavior change, no scope creep.

## Issues Encountered

None — plan executed without blockers.

## Known Stubs

None — all new fields have real data: model columns are DB-backed, seed migration populates six real trainer rows, schemas carry the values end-to-end.

## Threat Flags

No new security-relevant surfaces beyond the plan's threat model. All DB writes use `bindparams` (parameterized SQL, T-88-05 mitigated). `extra='forbid'` on `TrainerUpdateRequest` (T-88-04 mitigated).

## Next Phase Readiness

- Data foundation for Plan 02 (endpoints) is complete: `Trainer` model + schemas carry the three fields; migration chain 0061→0062→0063 is applied and seeded
- Plan 02 can extend `client_portal` repository/service/router with `fetch_trainer_detail` + `get_trainer_detail` + `client_get_trainer` endpoint immediately
- Plan 03 (PWA `TrainerDetailSheet`) can wire `useClientTrainerDetail` hook once Plan 02 ships the endpoint

---
*Phase: 88-trainer-detail-bio*
*Completed: 2026-06-06*
