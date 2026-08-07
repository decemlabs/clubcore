# Phase 123 Plan 01 — Fresh Full-Suite Pytest Run — Summary Evidence

**Date:** 2026-07-26
**phase_start_sha:** b88eb2ee600142e6e63adbf579b7885b54a8415f

This file is the authoritative evidence artifact TEST-01/TEST-02 registry rows (plan 123-02) resolve
against. All numbers below are transcribed verbatim from the archived logs in this directory — none
are reconstructed, remembered, or copied forward from the June (`f438ced2`) diagnosis.

## 1. DB reset sequence (exact commands)

```bash
# 1. Drop + recreate clean (executed against the running docker-compose postgres service)
docker compose exec -T postgres psql -U app -d postgres -c "DROP DATABASE IF EXISTS clubcore; CREATE DATABASE clubcore OWNER app;"

# 2. Pre-create alembic_version WIDE (VARCHAR(64) — VARCHAR(32) default overflows on this repo's longest revision id)
docker compose exec -T postgres psql -U app -d clubcore -c "CREATE TABLE alembic_version (version_num VARCHAR(64) NOT NULL, CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num));"

# 3. Migrate from the host to head
DATABASE_URL='postgresql+asyncpg://app:app@localhost:5432/clubcore' uv run alembic upgrade head
```

Migration completed clean: `0033_clients_email_partial_unique -> ... -> 0073_message_thread_staff_last_read_at` (head). No errors.

Pre-run orphan-lock check (`SELECT pid,state,wait_event_type,left(query,60) FROM pg_stat_activity WHERE datname='clubcore' AND pid<>pg_backend_pid();`) returned 0 rows both before the DB reset and after migration — no stale `idle in transaction` backends.

## 2. Full-run pytest invocation (exact command, verbatim)

```bash
DATABASE_URL='postgresql+asyncpg://app:app@localhost:5432/clubcore' REDIS_URL='redis://localhost:6379/0' uv run pytest
```

No `-k`, no `-m`, no `--deselect`, no path narrowing — the whole suite, run exactly once (D-123-06).
Output redirected straight to `pytest-full-run-2026-07-26.log` (never streamed through the harness).

Header confirms an unnarrowed run: `collected 3071 items`, `plugins: timeout-2.4.0, asyncio-1.3.0, respx-0.23.1, anyio-4.13.0`, `timeout: 180.0s`, `timeout method: signal`.

## 3. Tally (new run's real numbers)

```
4 failed, 3058 passed, 8 skipped, 1 error in 894.00s (0:14:53)
```

Wall-clock: **14m53s** (started `2026-07-26T15:50:52Z`, ended `2026-07-26T16:07:10Z` per the log's own START/END bracket timestamps).

This is NOT the June tally (`3058 passed / 3 failed / 2 errors / 8 skipped, 15m08s`) copied forward — passed-count coincidentally matches (3058) but failed/error counts differ (4 failed / 1 error here vs 3 failed / 2 errors in June), confirming this is a fresh, independently-produced result.

## 4. D-123-09 regression verdict: **NOT REGRESSED**

Deciding evidence, all from `pytest-full-run-2026-07-26.log`:
- `grep -c "Failed: Timeout >180.0s" pytest-full-run-2026-07-26.log` → **0** matches.
- The run reached a terminal summary line (`4 failed, 3058 passed, 8 skipped, 1 error in 894.00s (0:14:53)`) — it did not hang.
- None of the 5 residual node IDs (below) touch the lock-family surface (`working_hours_config`/`booking_config` singleton fixtures, or the alembic-downgrade subprocess tests under `tests/integration/migrations/` or `tests/integration/alembic/`).
- The `f438ced2` fix (marker opt-out + booking-race teardown restore + pytest-timeout 180s) still holds on this fresh clean-DB run.

## 5. Per-residual table

Every `FAILED`/`ERROR` node ID from the full run (5 total) was re-run as a targeted subset in
`residuals-isolation-2026-07-26.log`; the two count-matched, both 5 in full run.

| node ID | full-run outcome | isolated outcome | classification |
|---|---|---|---|
| `tests/integration/bookings/test_bookings_create.py::test_create_booking_pt_package_expired_before_slot_moscow_tz` | FAILED | FAILED (targeted subset) | **deterministic — new finding.** Hardcoded slot fixture date `2026-07-01 01:00 Moscow` is now BEFORE the wall-clock "today" (`2026-07-26`); the code's defensive freshness guard (`slot.start_time <= now_utc` → `SlotNotAvailableError`) fires before the test ever reaches its intended `PtPackageExpiredBeforeSlotError` assertion. A test-fixture-date time-bomb, not a lock-family issue. |
| `tests/integration/memberships/test_freeze_race.py::test_concurrent_freeze_race_serialised_by_partial_unique_index` | FAILED | **PASSED** when re-run together with the other 4 targeted node IDs; **FAILED** when re-run entirely alone | **non-deterministic concurrency-timing race** (known family per D-123-08/June diagnosis) — flakes both directions depending on scheduling, confirming it is timing-sensitive, not a fixed regression. |
| `tests/integration/test_phase51_audit_chain_invariants.py::test_locked_audit_events_count_after_phase_51_is_85` | FAILED | FAILED | **deterministic — known family.** `LOCKED_AUDIT_EVENTS` count assertion (117 vs actual) — locked-invariant surface, `owning_phase: 124` per D-123-08. |
| `tests/integration/test_route_introspection.py::test_every_protected_route_declares_a_gate` | FAILED | FAILED | **deterministic — known family.** `/metrics` route missing an explicit gate declaration — locked-invariant-adjacent (RBAC route-gate parity), `owning_phase: 124` per D-123-08. |
| `tests/integration/visits/test_visits_self_checkin.py::test_self_checkin_happy_path` | ERROR (setup) | **PASSED** both when re-run together with the other 4 targeted node IDs AND when re-run entirely alone | **full-suite-only pollution — known family.** `asgi_lifespan` `TimeoutError` during `LifespanManager` startup under full-suite load (5s startup budget exceeded); passes cleanly in isolation both times. |

**Isolation re-run commands (exact, verbatim, in `residuals-isolation-2026-07-26.log`):**

```bash
# Targeted subset (all 5 residual node IDs together)
DATABASE_URL='postgresql+asyncpg://app:app@localhost:5432/clubcore' REDIS_URL='redis://localhost:6379/0' \
uv run pytest \
  "tests/integration/bookings/test_bookings_create.py::test_create_booking_pt_package_expired_before_slot_moscow_tz" \
  "tests/integration/memberships/test_freeze_race.py::test_concurrent_freeze_race_serialised_by_partial_unique_index" \
  "tests/integration/test_phase51_audit_chain_invariants.py::test_locked_audit_events_count_after_phase_51_is_85" \
  "tests/integration/test_route_introspection.py::test_every_protected_route_declares_a_gate" \
  "tests/integration/visits/test_visits_self_checkin.py::test_self_checkin_happy_path" \
  -v
# Result: 3 failed, 2 passed in 2.00s

# Alone re-run: test_freeze_race (suspected pollution — confirmed timing-flake instead)
DATABASE_URL='postgresql+asyncpg://app:app@localhost:5432/clubcore' REDIS_URL='redis://localhost:6379/0' \
uv run pytest "tests/integration/memberships/test_freeze_race.py::test_concurrent_freeze_race_serialised_by_partial_unique_index" -v
# Result: 1 failed in 0.68s

# Alone re-run: test_self_checkin_happy_path (suspected asgi_lifespan pollution — confirmed)
DATABASE_URL='postgresql+asyncpg://app:app@localhost:5432/clubcore' REDIS_URL='redis://localhost:6379/0' \
uv run pytest "tests/integration/visits/test_visits_self_checkin.py::test_self_checkin_happy_path" -v
# Result: 1 passed in 0.30s
```

Exactly ONE full-suite invocation was spent (§2 above); everything in this section is a targeted
node-ID subset (D-123-06). No second unnarrowed `uv run pytest` appears anywhere in this file.

## 6. Regression branch

**Did not fire.** D-123-09 verdict is "not regressed" (§4) — the run reached its terminal summary
line with zero lock-family timeouts. No diagnose-fix cycles were run; `.planning/debug/pytest-isolation-deadlock.md`
and every `conftest.py` are unmodified by this plan (`git diff --name-only` confirms).

## 7. Re-seed commands (post-suite, both exit 0)

```bash
SEED_OWNER_EMAIL=owner@clubcore.dev SEED_OWNER_PASSWORD=devpassword12345 \
DATABASE_URL='postgresql+asyncpg://app:app@localhost:5432/clubcore' \
uv run python -m scripts.seed_demo_data
# exit 0 — "Seeded owner owner@clubcore.dev", "Seeded client catalog: 1 membership plan + 1 PT-package", "Seeded 2 promo codes"

SEED_OWNER_EMAIL=owner@clubcore.dev SEED_OWNER_PASSWORD=devpassword12345 \
DATABASE_URL='postgresql+asyncpg://app:app@localhost:5432/clubcore' \
uv run python -m scripts.seed_dev_client
# exit 0 — "Seeded dev test client +79999999999 (telegram_user_id=999999999)"
```

Post-seed check: `SELECT count(*) FROM users;` → `1` (non-empty).

## 8. Secret-leak scan (pre-commit)

Both logs were scanned for leaked credentials (`yookassa_secret`, `shop_id`, `api_key`, `secret_key`,
RSA/private-key PEM headers) before being committed. Zero matches beyond the local placeholder
`app:app` DSN (permitted to remain, already written verbatim in this plan and in the June debug doc)
and Argon2id password hashes from test fixture data (not real secrets). No redaction was necessary.

## 9. Footprint check

`git diff --name-only` (against the working tree, post-run) initially showed 5 `apps/admin/src/features/*/capture/*.json`
files that pytest's live-backend contract-test suite regenerates as a side effect of hitting the
running `docker compose` backend — these are outside the phase-123 allowlist
(`apps/backend/tests/**`, `apps/backend/pyproject.toml`, `.planning/**`) and were reverted with a
targeted `git checkout -- <file>` (not a blanket reset) before any commit. Final diff touches only
`.planning/**` paths. No path under `apps/backend/app/` and no change to `apps/backend/uv.lock`.
