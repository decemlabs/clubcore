---
phase: 41-infra-bedrock-anti-oracle-scaffold
plan: 06
subsystem: infra
tags: [alembic, migration, audit_log, foreign-key, on-delete-set-null, actor-snapshot, postgres, infra-39]

# Dependency graph
requires:
  - phase: 5
    provides: audit_log table + fk_audit_log_actor_user_id_users with ON DELETE RESTRICT (0002_clients.py lines 129-161)
  - phase: 41-plan-05
    provides: alembic head 0022_users_soft_delete_unique
provides:
  - audit_log.actor_email_snapshot TEXT NULL column (denormalised email for forensic continuity)
  - fk_audit_log_actor_user_id_users altered to ON DELETE SET NULL (was RESTRICT)
  - alembic head bumped 0022_users_soft_delete_unique -> 0023_audit_actor_snapshot
affects:
  - phase-41-plan-07 (INFRA-39 runtime — ActorContextMiddleware + audit.emit reads from ContextVar to populate actor_email_snapshot)
  - phase-43 (USERS-05 soft-delete + USERS-06 list filter — audit rows survive future hard-deletes)
  - phase-44 (RESET-01 password_reset_requested anti-oracle emit — system path with actor_user_id=NULL keeps snapshot NULL too)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Drop+recreate cycle on existing FK to alter ON DELETE behaviour (Postgres-canonical Alembic pattern — no ALTER CONSTRAINT for ondelete)"
    - "FK name resolved verbatim from op.f() output in source migration (fk_audit_log_actor_user_id_users) — no re-derivation via naming convention helpers"
    - "Snapshot column is on the audit row, NOT on the payload schema — keeps the 11 v1.6 Pydantic payload schemas free of cross-cutting actor noise (D-41-09)"

key-files:
  created:
    - apps/backend/alembic/versions/0023_audit_actor_snapshot.py
  modified: []

key-decisions:
  - "Single migration adds the column AND alters the FK in one transactional DDL block — both changes target the same table and same logical concern (actor identity preservation). Splitting into two migrations would add round-trip cost without isolation benefit (Postgres DDL is transactional)."
  - "No index on actor_email_snapshot — analytics queries scanning by email-snapshot are out of v1.6 scope (deferred). Avoids carrying an unused index through every audit_log write for the rest of the milestone."
  - "down_revision literal is '0022_users_soft_delete_unique' (the actual revision id inside 0022's file), NOT '0022_users_soft_delete_partial_unique' (which is only the filename). Plan-spec optimistically used the long form; resolved by reading 0022 source."
  - "Downgrade restores ondelete='RESTRICT' verbatim from 0002_clients.py line 159 — the original behaviour before this migration. Drop of actor_email_snapshot column happens last so the FK recreate sees the table in its pre-snapshot shape."

patterns-established:
  - "Alembic FK ondelete change = drop_constraint + create_foreign_key with new ondelete (Postgres has no ALTER CONSTRAINT for this attribute)"
  - "Forensic-continuity migrations pair a denormalised snapshot column with a SET NULL FK so business-data hard-deletes don't cascade into audit destruction"

requirements-completed: []
requirements-progressed: [INFRA-39]

# Metrics
duration: 2min
completed: 2026-05-18
---

# Phase 41 Plan 06: INFRA-39 — Alembic 0023 (audit_log.actor_email_snapshot + FK ON DELETE SET NULL) Summary

**Alembic migration 0023 ships the schema half of D-41-08/09/10: adds `audit_log.actor_email_snapshot TEXT NULL` for denormalised actor email and flips `fk_audit_log_actor_user_id_users` from `ON DELETE RESTRICT` to `ON DELETE SET NULL` — so audit rows survive any future hard-delete of a referenced user with the email snapshot preserved as forensic continuity. The runtime half (ContextVar middleware + `audit.emit` snapshot capture) lands in Plan 07.**

## Performance

- Plan duration: ~2 minutes (single-file migration; verification dominated by alembic upgrade/downgrade round-trip + live FK behaviour test).
- Migration is two op calls in upgrade (add_column + drop+recreate FK) and three in downgrade (drop+recreate FK back to RESTRICT + drop_column). Runs in well under a second against the dev DB.

## Decisions Made

1. **Snapshot is a column on `audit_log`, not a payload field (D-41-09 carried forward).** `actor_email_snapshot` writes via the `audit.emit()` boundary at Plan 07, not via any of the 11 INFRA-35 Pydantic payload schemas. Keeps `extra='forbid'` schemas focused on per-event business data, not cross-cutting actor identity. The column lives next to `actor_user_id` for forensic locality.

2. **FK ondelete behaviour change requires drop+recreate in Postgres.** There is no `ALTER CONSTRAINT ... ON DELETE` syntax for foreign keys; the only Alembic-supported path is `op.drop_constraint(..., type_='foreignkey')` followed by `op.create_foreign_key(..., ondelete='SET NULL')`. Both operations run in the same Alembic transaction, so concurrent writers see the migration atomically.

3. **Resolved FK name verbatim from source.** `fk_audit_log_actor_user_id_users` is the string emitted by `op.f("fk_audit_log_actor_user_id_users")` in `0002_clients.py:158` — captured as a module-level constant `_ACTOR_FK_NAME` in 0023 so both upgrade and downgrade use the identical literal. Avoids re-derivation through SQLAlchemy's naming-convention helpers, which would re-introduce the same fragility class as the v1.2 Phase 17 FK-rename incident.

4. **No index on `actor_email_snapshot`.** Analytics use-cases (e.g. "all actions by user@former-employee.com") are not on the v1.6 roadmap. Adding an index now would pay maintenance cost on every audit_log write for the rest of the milestone with no caller. Deferred until a Phase 47+ use case justifies it.

5. **Downgrade restores original ondelete = RESTRICT.** Read from `0002_clients.py:159`. The drop_column for `actor_email_snapshot` happens last so the FK recreate sees the table in its pre-snapshot column shape — pure reverse-order of upgrade.

## Verification Results

**Automated verification (from the plan's `<verify>` block):**

1. `cd apps/backend && uv run alembic upgrade head` — applied `0022_users_soft_delete_unique -> 0023_audit_actor_snapshot` cleanly; new head is `0023_audit_actor_snapshot`.
2. Schema introspection via `sqlalchemy.inspect`:
   - `audit_log.actor_email_snapshot` exists as `TEXT`, `nullable=True`.
   - `fk_audit_log_actor_user_id_users` has `ondelete = 'SET NULL'`.
3. Round-trip `alembic downgrade -1 && alembic upgrade head` — both directions succeeded, head ends at `0023_audit_actor_snapshot`.
4. **Live FK behaviour test** (beyond the plan's automated check — exercises the actual SET NULL semantics):
   - Inserted a User row + an audit_log row with `actor_user_id` pointing at that User and `actor_email_snapshot` populated.
   - Hard-deleted the User row (`DELETE FROM users WHERE id = :uid`) — succeeded without FK violation (would have raised under the prior RESTRICT behaviour).
   - SELECT on the audit_log row showed `actor_user_id = NULL` and `actor_email_snapshot` intact with the original email string.
5. `ruff check` and `ruff format --check` on the new file: clean.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `down_revision` literal corrected to match Plan 05's actual revision id**

- **Found during:** Authoring 0023, reading 0022's source file.
- **Issue:** The 41-06-PLAN's specimen code used `down_revision = "0022_users_soft_delete_partial_unique"`, but `0022_users_soft_delete_partial_unique.py:36` actually declares `revision: str = "0022_users_soft_delete_unique"` — the revision id was shortened to fit `alembic_version.version_num VARCHAR(32)` (see Plan 05's SUMMARY key-decisions). Using the plan's long form verbatim would have produced `KeyError` / "down_revision not found" at `alembic upgrade head`.
- **Fix:** Used the actual revision id `0022_users_soft_delete_unique` as `down_revision` in 0023. Verified by `alembic upgrade head` succeeding.
- **Files modified:** `apps/backend/alembic/versions/0023_audit_actor_snapshot.py` (one-line correction from spec).
- **Commit:** 3731a45.

No other deviations. The migration body matched the plan's specimen code (column add + FK drop+recreate with `ondelete='SET NULL'`, mirror downgrade restoring `ondelete='RESTRICT'`).

## Authentication Gates

None — pure schema migration against the local dev Postgres.

## Threat Model Coverage

Plan threats (T-41-06-01..03) reviewed against implementation:

- **T-41-06-01 (Repudiation, mitigate):** `ON DELETE SET NULL` plus the `actor_email_snapshot TEXT` column together preserve the audit row past any future hard-delete of the referenced user — confirmed by the live behaviour test (audit row survived, `actor_email_snapshot` intact).
- **T-41-06-02 (Information disclosure, mitigate):** No router or schema introduced in this plan exposes `audit_log` rows. Snapshot column is internal-only. Will be re-checked by the Phase 46 OpenAPI gate against `/users`-related schemas authored in Phase 43.
- **T-41-06-03 (Tampering / drift, accept):** Snapshot is point-in-time at audit-emit. If a user's email later changes, prior audit rows keep the historical email value — this is the desired forensic semantic, not a bug.

No new threat flags discovered during implementation.

## Known Stubs

None. The migration is the schema half of INFRA-39; the runtime half (ContextVar + middleware + `audit.emit` writes to the new column) is intentionally scoped to Plan 07. The column being NULL on every audit row written between this plan and Plan 07 is expected and documented — the field is `NULL`-able precisely so the gap is safe.

## Tasks Completed

| Task | Name                                                | Commit  | Files                                                          |
| ---- | --------------------------------------------------- | ------- | -------------------------------------------------------------- |
| 1    | Author Alembic migration 0023_audit_actor_snapshot.py | 3731a45 | apps/backend/alembic/versions/0023_audit_actor_snapshot.py     |

## Self-Check: PASSED

- File `apps/backend/alembic/versions/0023_audit_actor_snapshot.py`: FOUND.
- Commit `3731a45`: FOUND in `git log`.
- `alembic current` reports `0023_audit_actor_snapshot (head)`: FOUND.
- Live FK SET NULL behaviour exercised against a real audit_log row: VERIFIED.
