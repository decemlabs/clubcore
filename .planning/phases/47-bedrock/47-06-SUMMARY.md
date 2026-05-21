---
phase: 47-bedrock
plan: 06
subsystem: database
tags: [alembic, postgres, partial-unique, clients, email, infra-41, ddl-migration]

# Dependency graph
requires:
  - phase: 08
    provides: clients table with email Text NULL column (Alembic 0002 — predates 0033)
  - phase: 41
    provides: 0022_users_soft_delete_partial_unique.py — partial UNIQUE on lower(email) precedent
  - phase: 40
    provides: 0021_bookings_created_by_user_id_nullable.py — pre-flight conn.execute().fetchall() guard pattern
  - phase: 45
    provides: 0032_booking_notif_widen_kind (alembic HEAD; 0033 chains from it)
provides:
  - Alembic 0033 partial UNIQUE on clients(lower(email)) WHERE email IS NOT NULL AND deleted_at IS NULL
  - Pre-flight duplicate-check guard with operator-actionable RuntimeError listing offenders
  - Tightened REQUIREMENTS.md INFRA-41 wording (D-47-06)
affects: [phase-49-online-payments-sell-endpoint, phase-53-ver-02-race-test, fis-05-fiscal-receipt-email-gate]

# Tech tracking
tech-stack:
  added: []  # No new tooling; uses existing alembic + sqlalchemy + Postgres stack
  patterns:
    - "Composite migration analog: partial-UNIQUE-on-lower(email) (0022) + pre-flight guard (0021) → 0033"
    - "Fail-fast schema discipline: pre-flight read-only SELECT before any DDL, RuntimeError abort with offender listing"

key-files:
  created:
    - apps/backend/alembic/versions/0033_clients_email_partial_unique.py
    - apps/backend/tests/integration/alembic/test_migration_0033_clients_email.py
  modified:
    - .planning/REQUIREMENTS.md (INFRA-41 wording — single line)

key-decisions:
  - "D-47-03 honored: 0033 does NOT add the clients.email column (pre-existing since Alembic 0002) and does NOT narrow Text to a fixed-width character type"
  - "D-47-04 honored: only the partial UNIQUE index is created (postgresql_where='email IS NOT NULL AND deleted_at IS NULL')"
  - "D-47-05 honored: pre-flight duplicate-check raises RuntimeError listing offending lower(email) values; no silent dedup, no soft-delete, no automatic backfill"
  - "D-47-06 honored: REQUIREMENTS.md INFRA-41 wording tightened to remove the inaccurate 'adds VARCHAR(255) column' claim"
  - "down_revision pinned to actual HEAD revision id ('0032_booking_notif_widen_kind') rather than the plan's must_haves value ('0032_booking_notifications_widen_kind' — that is the *filename*, not the revision id). Deviation documented inline in the migration module docstring"

patterns-established:
  - "Pattern: a schema-altering migration ships exactly two operations — a pre-flight read-only SELECT that aborts with RuntimeError on contract breach, and a single atomic DDL. Failure modes restricted to 'contract breach' (caught before any DDL) or 'Postgres rejects DDL' (well-defined rollback)."

requirements-completed: [INFRA-41]

# Metrics
duration: ~25min
completed: 2026-05-21
---

# Phase 47 Plan 06: Alembic 0033 — clients.email Partial UNIQUE Summary

**Ships Alembic 0033 with a partial UNIQUE on `clients(lower(email)) WHERE email IS NOT NULL AND deleted_at IS NULL` and a pre-flight `RuntimeError` guard that aborts the migration before any DDL if case-insensitive duplicates already exist.**

## What Shipped

### Task 1 — `apps/backend/alembic/versions/0033_clients_email_partial_unique.py`

Single-revision Alembic migration. Two operations only:

1. **Pre-flight duplicate check (D-47-05):**
   ```sql
   SELECT lower(email) AS email_lc, COUNT(*) AS n
   FROM clients
   WHERE email IS NOT NULL AND deleted_at IS NULL
   GROUP BY lower(email) HAVING COUNT(*) > 1
   ```
   If any rows return, the migration raises `RuntimeError` formatted as:
   ```
   cannot apply 0033 — duplicate clients.email (case-insensitive) rows present:
   '<offender_lower>' (Nx), ...
   Operator must dedup manually (soft-delete, merge, or correct typos) and re-run the migration.
   ```

2. **Index creation:**
   ```python
   op.create_index(
       "ix_clients_email_lower_unique",
       "clients",
       [text("lower(email)")],
       unique=True,
       postgresql_where=text("email IS NOT NULL AND deleted_at IS NULL"),
   )
   ```

`downgrade()` drops only the index — the `clients.email` column is untouched (it pre-dates this migration via Alembic 0002).

### Task 1 — co-located integration tests

`apps/backend/tests/integration/alembic/test_migration_0033_clients_email.py` — four tests mirroring `test_migration_0027_cleanup.py` harness:

1. `test_0033_upgrade_clean_no_duplicates` — fresh-DB upgrade creates `ix_clients_email_lower_unique` with the documented predicate.
2. `test_0033_upgrade_aborts_on_duplicate` — seeds `Foo+<nonce>@Example.com` + `foo+<nonce>@example.com` on a 0032 schema, asserts upgrade fails with `RuntimeError` naming the offender, asserts index does NOT exist after the failed upgrade.
3. `test_0033_soft_deleted_duplicate_allowed` — seeds one soft-deleted + one live row with the same case-insensitive email, asserts upgrade succeeds (predicate excludes the soft-deleted row).
4. `test_0033_round_trip_drops_index_but_keeps_column` — downgrade to 0032 drops the index, leaves `clients.email` as `text NOT NULL=NO`.

Tests skip cleanly if Postgres is unreachable (`pytest.skip` from the `direct_engine_session` fixture).

### Task 2 — REQUIREMENTS.md INFRA-41 wording (D-47-06)

One-line edit. Diff:

**Before:**
> - [ ] **INFRA-41**: Alembic 0033 adds `clients.email VARCHAR(255) NULL` (idempotent for clients without email); partial UNIQUE `(lower(email)) WHERE email IS NOT NULL AND deleted_at IS NULL` for case-insensitive uniqueness

**After:**
> - [ ] **INFRA-41**: Alembic 0033 adds partial UNIQUE `(lower(email)) WHERE email IS NOT NULL AND deleted_at IS NULL` on the existing `clients.email` column (column already exists since Alembic 0002 per v1.1; 0033 does NOT add or narrow it). Migration runs a pre-flight duplicate check (D-47-05) and aborts with `RuntimeError` listing offenders if any case-insensitive collision exists.

## Deviations from Plan

### `[Plan-vs-Reality - down_revision pin]` Pinned to actual HEAD revision id, not plan must_haves value

- **Found during:** Task 1 step 1 (confirm current Alembic HEAD).
- **Issue:** The plan's `must_haves.key_links` and `must_haves.truths` document `down_revision = "0032_booking_notifications_widen_kind"` (matching the migration's *filename*). The actual `revision: str` inside that file is `"0032_booking_notif_widen_kind"` (a shorter 30-char internal id) — confirmed by `grep -E "^revision: str"` against the file and by `uv run alembic heads`.
- **Fix:** Pinned `down_revision = "0032_booking_notif_widen_kind"` (actual HEAD) per Task 1 step 1 instruction: "If a different revision is the actual HEAD, pin down_revision to the actual HEAD and document the deviation."
- **Documented:** Inline in the migration's module docstring under "Down-revision pin (deviation note)".
- **Files modified:** `apps/backend/alembic/versions/0033_clients_email_partial_unique.py`
- **Commit:** 7da6159
- **Verification:** `uv run alembic heads` now reports `0033_clients_email_partial_unique (head)`; `ScriptDirectory.walk_revisions()` correctly chains `0033 -> 0032_booking_notif_widen_kind -> 0031_payment_receipts -> ...`.

### `[Rule 3 - Negative-grep collision]` Removed literal `VARCHAR(255)` from migration docstring

- **Found during:** Task 1 verification (`! grep -q 'VARCHAR(255)' ...`).
- **Issue:** Initial docstring read "does NOT narrow `Text → VARCHAR(255)`". The plan's verification command is a *negative* grep — any occurrence (even in a docstring saying we *don't* do it) fails the check.
- **Fix:** Rewrote the docstring phrase to "does NOT narrow Text to a fixed-width character type" — semantically identical, no literal `VARCHAR(255)` token. Mirrors the spirit of the D-47-03 prohibition (no `VARCHAR(255)` anywhere in the file).
- **Files modified:** `apps/backend/alembic/versions/0033_clients_email_partial_unique.py`
- **Commit:** 7da6159 (squashed into the GREEN commit before it landed).
- **Verification:** `! grep -q 'VARCHAR(255)'` now passes.

## Manual Verification Outcome

Per universal_rules — "If the local Postgres isn't available for the upgrade test, mark the run as 'verified by structure + dry-run check' in the SUMMARY; do NOT block on infra unavailability":

- **Local Postgres availability:** Not configured in this worktree (`uv run alembic upgrade head` fails with `pydantic_core._pydantic_core.ValidationError: Field required: database_url / redis_url / secret_key` — no `.env` set, no docker-compose Postgres bound).
- **Structural verification (substitute):**
  - `uv run alembic heads` → reports `0033_clients_email_partial_unique (head)` — module is discoverable.
  - `alembic.script.ScriptDirectory.walk_revisions()` correctly orders `0033 -> 0032_booking_notif_widen_kind -> 0031_payment_receipts -> ...` — chain integrity confirmed.
  - `uv run python -c "import importlib.util; ..."` loads the module cleanly and exposes the expected symbols (`revision`, `down_revision`, `_NEW_EMAIL_PARTIAL_UNIQUE_INDEX`, `upgrade`, `downgrade`).
  - `uv run ruff check` → all checks passed.
  - `uv run mypy --strict` → success, no issues.
- **Verification command chain from the plan's `<verify><automated>`:** all checks pass (positive greps for `0032_booking_notif_widen_kind`, `ix_clients_email_lower_unique`, `email IS NOT NULL AND deleted_at IS NULL`, `RuntimeError`; negative greps for `op.add_column(`, `op.alter_column(`, `VARCHAR(255)`).

## Confirmation of Absent Constructs

Negative-grep verification — all three required prohibitions hold:

```
$ grep -E 'op\.(add_column|alter_column)\(' alembic/versions/0033_clients_email_partial_unique.py
(no output)

$ grep -q 'VARCHAR(255)' alembic/versions/0033_clients_email_partial_unique.py; echo "exit=$?"
exit=1   # i.e., not found
```

- ❌ `op.add_column(` — absent (D-47-03 honored: column pre-exists).
- ❌ `op.alter_column(` — absent (D-47-03 honored: no narrowing).
- ❌ `VARCHAR(255)` — absent anywhere in the file (D-47-03 honored).

## Deferred Integration Tests

The four migration tests under `apps/backend/tests/integration/alembic/test_migration_0033_clients_email.py` are wired and lint-clean but **not executed in this worktree** because:

- The test fixture (`direct_engine_session`) requires `settings.database_url` to be set and a reachable Postgres bound to it (matches the existing `test_migration_0027_cleanup.py` convention).
- This worktree has no `.env` and no docker-compose Postgres binding.
- The fixture's `pytest.skip` path covers exactly this case — tests will pass-by-skip in CI environments without Postgres, and execute fully against the test DB once Postgres is available.

**Where they run:** the standard CI test job that runs `apps/backend/tests/integration/alembic/` against a docker-compose Postgres instance. No additional plumbing needed — the tests follow the project's existing migration-test convention letter-for-letter.

Per the plan: "If no migration-test pattern exists, defer integration testing to manual verification + Phase 53 VER-02 race test; note the deferral in the SUMMARY." A migration-test pattern *does* exist (`test_migration_0027_cleanup.py`) so the tests are co-located there per the plan's preferred branch; execution is deferred to the next CI run only because no Postgres is bound in this exact worktree.

## TDD Gate Compliance

Task 1 had `tdd="true"`. Sequence in git log:

1. **RED:** `e4de01c test(47-06): add failing tests for Alembic 0033 partial UNIQUE on clients.email` — tests authored before the migration; would fail (test assertions reference `ix_clients_email_lower_unique` which only exists after 0033 lands).
2. **GREEN:** `7da6159 feat(47-06): add Alembic 0033 partial UNIQUE on clients.email (INFRA-41)` — migration ships, tests would now pass.
3. **REFACTOR:** not needed (single-pass GREEN).

Both gate commits present in the chain; sequence preserved.

## Commits

| Order | Hash    | Type | Message |
| ----- | ------- | ---- | ------- |
| 1     | e4de01c | test | test(47-06): add failing tests for Alembic 0033 partial UNIQUE on clients.email |
| 2     | 7da6159 | feat | feat(47-06): add Alembic 0033 partial UNIQUE on clients.email (INFRA-41) |
| 3     | 6818b4a | docs | docs(47-06): tighten INFRA-41 wording to reflect actual scope (D-47-06) |

## Threat Flags

None — the migration introduces no new network endpoint, no new auth path, no new file-access pattern, no new trust boundary beyond what the plan's `<threat_model>` already enumerates. T-47-06-01..05 dispositions stand as planned.

## Self-Check: PASSED

- File `apps/backend/alembic/versions/0033_clients_email_partial_unique.py`: **FOUND**
- File `apps/backend/tests/integration/alembic/test_migration_0033_clients_email.py`: **FOUND**
- File `.planning/REQUIREMENTS.md` (modified — INFRA-41 wording): **FOUND** (positive grep on "Alembic 0033 adds partial UNIQUE" returns the new line)
- Commit `e4de01c`: **FOUND** in `git log --all`
- Commit `7da6159`: **FOUND** in `git log --all`
- Commit `6818b4a`: **FOUND** in `git log --all`
- `uv run ruff check` on both new files: **PASS**
- `uv run mypy --strict` on migration: **PASS**
- Plan `<verify><automated>` command chain: **PASS** (all positive + negative greps)
- Plan-level `<done>` `uv run alembic upgrade head against fresh DB`: **deferred** (local Postgres unavailable; verified by structure per universal_rules).
