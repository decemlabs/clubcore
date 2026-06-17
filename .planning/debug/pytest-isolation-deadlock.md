---
status: resolved
trigger: "backend full-suite pytest test-isolation deadlock in apps/backend — does a single sequential run deadlock or complete? root-cause + minimal fix"
created: 2026-06-17
updated: 2026-06-17
commit: f438ced2
---

## Current Focus

status: fixing

reasoning_checkpoint:
  hypothesis: "The autouse permissive_booking_config fixture's uncommitted UPDATE working_hours_config holds a row lock that the alembic-downgrade subprocess's DELETE FROM working_hours_config (0071 downgrade) blocks on => circular self-deadlock in test_0045_round_trip."
  confirming_evidence:
    - "pg_blocking_pids(68379)={68368} captured live."
    - "68368 = idle in transaction running UPDATE working_hours_config (the autouse fixture)."
    - "68379 = active, Lock/transactionid, running DELETE FROM working_hours_config (0071 downgrade subprocess)."
  falsification_test: "Skip the autouse fixture for the round-trip test; if it STILL deadlocks the hypothesis is wrong; if it passes, confirmed."
  fix_rationale: "Removing the held row lock lets the downgrade subprocess acquire the lock immediately. Migration tests use direct_engine_session and never read booking/working-hours config, so skipping the fixture is semantically safe. pytest-timeout added as a systemic safety net so any FUTURE lock-vs-subprocess hang auto-fails instead of blocking forever."
  blind_spots: "Other tests in the full suite could also downgrade below 0070 — pytest-timeout covers that. Must verify the FULL suite completes, not just this one test."

hypothesis: A SINGLE sequential run self-deadlocks. The autouse `permissive_booking_config` fixture (tests/integration/conftest.py + bookings/conftest.py) issues an UNCOMMITTED `UPDATE working_hours_config WHERE id=<singleton>` on the SAVEPOINT db_session connection, holding a row lock. Migration-reversibility tests (e.g. test_0045_round_trip in tests/integration/migrations/test_visits_channel_client_qr.py) then run `alembic downgrade 0044` in a SUBPROCESS (separate connection). The downgrade chain reaches 0071 (`DELETE FROM working_hours_config`) and 0070 (`DROP TABLE working_hours_config`), which block forever on the row/table lock held by the same test's uncommitted db_session UPDATE. No lock_timeout, no pytest-timeout => hang forever at 0% CPU.
test: Run tests/integration/migrations/ in isolation on the host with a wall-clock guard; observe whether it hangs at the round-trip test. Inspect pg_stat_activity for a blocked DROP/DELETE if it hangs.
expecting: If hypothesis true => the migrations test hangs and pg_stat_activity shows a subprocess backend (client_addr=host gateway) blocked on Lock wait_event waiting for the db_session backend holding the working_hours_config row lock.
next_action: Create debug file (done), then run the migrations subdir in isolation with timeout wrapper, logging to /tmp.

## Symptoms

expected: A full sequential `uv run pytest` completes (green or green-except-documented-known-failures) without hanging.
actual: Full suite reportedly hangs forever at 0% CPU; STATE.md calls it a systemic test-isolation deadlock (permissive_booking_config × working_hours_config). Conflicting note: single sequential runs complete and deadlock only from concurrent runs. Must determine which is true NOW.
errors: No error — a HANG (process blocked indefinitely, no output, no CPU). pg_stat_activity would show a backend blocked on Lock.
reproduction: cd apps/backend && DATABASE_URL=... REDIS_URL=... uv run pytest (full suite, sequential).
started: Pre-existing, deferred at v3.2 close.

## Eliminated

## Evidence

- timestamp: 2026-06-17
  checked: tests/integration/conftest.py + tests/integration/bookings/conftest.py
  found: autouse `permissive_booking_config(db_session)` runs `UPDATE working_hours_config SET schedule=..., closures=... WHERE id=<00000000-...-0004>` on the SAVEPOINT db_session. Never committed (SAVEPOINT mode rolls back at teardown). Holds a FOR NO KEY UPDATE row lock on the singleton row for the entire test.
  implication: Any concurrent DELETE/DROP of working_hours_config on a different connection blocks on this lock.

- timestamp: 2026-06-17
  checked: tests/integration/migrations/test_visits_channel_client_qr.py::test_0045_round_trip
  found: Uses `direct_engine_session` but autouse `permissive_booking_config(db_session)` STILL runs (it's autouse across all integration tests), so db_session opens its outer txn + UPDATE working_hours_config. The test body then calls `_run_alembic("downgrade", "0044_client_refresh_token")` in a subprocess — a SEPARATE connection.
  implication: Subprocess downgrade and the same test's uncommitted db_session UPDATE are concurrent within ONE sequential test => self-deadlock candidate.

- timestamp: 2026-06-17
  checked: alembic/versions/0071_seed_settings.py + 0070_settings_tables.py downgrade()
  found: 0071 downgrade does `DELETE FROM working_hours_config WHERE id=<singleton>`; 0070 downgrade does `op.drop_table("working_hours_config")` (ACCESS EXCLUSIVE). Downgrading to 0044 executes BOTH.
  implication: The subprocess downgrade WILL try to lock/drop working_hours_config — directly contended by the autouse UPDATE row lock. Confirms the deadlock mechanism for a single sequential run.

- timestamp: 2026-06-17
  checked: pyproject.toml [tool.pytest.ini_options]; uv pip list
  found: No pytest-timeout installed (only pytest 9.0.3 + pytest-asyncio 1.3.0). No addopts timeout. No lock_timeout configured.
  implication: A hang never auto-kills — blocks forever. Adding pytest-timeout is a viable safety net.

- timestamp: 2026-06-17
  checked: Ran tests/integration/migrations/ in isolation with -x -v (log /tmp/cc_pytest_migrations.log). Completed in 3.37s — NO HANG.
  found: 2 passed, then test_0045_channel_allows_client_qr FAILED with InFailedSQLTransactionError ("current transaction is aborted") on the direct_engine_session INSERT into visits / cleanup DELETE. Stopped at -x before reaching test_0045_round_trip (the downgrade-to-0044 test). Autouse permissive_booking_config DID run on db_session (SAVEPOINT sa_savepoint_1 + UPDATE working_hours_config visible in log) but on a DIFFERENT connection than the failing direct_engine_session.
  implication: (1) The deadlock did NOT manifest in this isolated subdir run with -x — the suite errored out fast instead. (2) The round-trip downgrade test was never reached here. Need to run WITHOUT -x and watch pg_stat_activity to see if round-trip deadlocks. (3) The InFailedSQLTransactionError suggests an EARLIER statement in that test's transaction failed (likely the client_qr CHECK constraint missing => DB not at head, or order-dependence between migration tests leaving DB downgraded).

- timestamp: 2026-06-17
  checked: Ran test_0045_round_trip in isolation under a 120s/150s watchdog while sampling pg_stat_activity + pg_blocking_pids.
  found: DEADLOCK REPRODUCED ON A SINGLE TEST. Live proof:
    PID 68368 (client_addr 192.168.65.1 = pytest db_session) = "idle in transaction", last stmt UPDATE working_hours_config (the autouse permissive_booking_config fixture, uncommitted, holds row lock).
    PID 68379 (192.168.65.1 = alembic downgrade SUBPROCESS) = "active", wait_event Lock/transactionid, running DELETE FROM working_hours_config (0071 downgrade).
    pg_blocking_pids(68379) = {68368}. xact age climbed 13s->38s and never resolved. Watchdog SIGKILL'd at deadline.
    Note: at the very first 12s sample of the FIRST run, nothing was blocked yet — the `_run_alembic("upgrade","head")` no-op + fixture setup happen first; the block starts once the downgrade subprocess reaches the 0071 DELETE. So the deadlock onset is ~12-13s in.
  implication: ROOT CAUSE CONFIRMED. A single sequential run DOES deadlock (not only concurrent runs). The contention is self-inflicted within ONE test: the test's own uncommitted db_session UPDATE (held for the whole test by the autouse fixture) vs the alembic-downgrade subprocess the test body spawns. Circular wait => infinite hang (no lock_timeout, no pytest-timeout). After SIGKILL of the process group, all orphaned connections drop cleanly; no manual pg_terminate_backend needed.

## Resolution

root_cause: |
  VERDICT: A single sequential `uv run pytest` DOES deadlock (the STATE.md "systemic test-isolation deadlock" description is correct; the "only concurrent runs" note is wrong for the CURRENT code).
  MECHANISM (self-deadlock within ONE test): The autouse fixture `permissive_booking_config` (defined in BOTH tests/integration/conftest.py and tests/integration/bookings/conftest.py) runs for EVERY integration test and issues an UNCOMMITTED `UPDATE working_hours_config ... WHERE id=<singleton>` on the SAVEPOINT-mode `db_session` connection. Under SAVEPOINT isolation this UPDATE is never committed — it holds a FOR NO KEY UPDATE row lock on the singleton row for the entire test.
  Migration-reversibility tests that spawn `alembic downgrade` in a SUBPROCESS (separate connection) — concretely tests/integration/migrations/test_visits_channel_client_qr.py::test_0045_round_trip downgrades to 0044, and test_migration_0027/0033 downgrade to 0026/0032 — execute the 0071 downgrade `DELETE FROM working_hours_config` and the 0070 downgrade `DROP TABLE working_hours_config`. The DELETE blocks on the autouse UPDATE's row lock; the DROP would need ACCESS EXCLUSIVE. The test body is synchronously blocked waiting for `subprocess.run(... alembic downgrade ...)` to return, which never will because it is waiting on the test's own connection. Circular wait. No lock_timeout, no pytest-timeout => blocks forever at 0% CPU.
  Why test_0027/0033 didn't hang historically: they only downgrade to 0026/0032 (ABOVE 0070), so their downgrade never touches working_hours_config. ONLY test_0045_round_trip downgrades below 0070, so it is the (current) trigger.
fix: |
  Make the autouse `permissive_booking_config` fixture NOT hold a working_hours_config / booking_config lock across migration-subprocess tests. Two surgical options considered:
  (A) Guard the fixture so it skips when the requesting test does NOT need it (the migration round-trip tests use direct_engine_session and never touch booking config). Implement by checking the test's fixturenames for db_session usage intent — fragile.
  (B) [CHOSEN] Set a short `lock_timeout` on the alembic subprocess connection AND make the autouse fixture skip for migration-reversibility tests via an opt-out marker. The cleanest minimal fix: add a `no_permissive_config` marker and have the autouse fixture early-return when present; mark test_0045_round_trip (the only sub-0070 downgrade) with it. ALSO add pytest-timeout as a safety net so any future hang auto-kills.
verification: |
  STEP 1 (fix verified on the trigger test): Re-ran test_0045_round_trip in isolation with the marker + pytest-timeout. RESULT: completed in 2.0s (was infinite hang). Setup log shows ONLY `BEGIN`/`SAVEPOINT`/`select 1` — NO `UPDATE working_hours_config` (marker took effect, no lock held). The downgrade now PROCEEDS past 0071/0070 (previously deadlocked there) all the way to 0045, where it fails with CheckViolationError: `ALTER TABLE visits ADD CONSTRAINT ck_visits_channel CHECK (channel IN ('reception','telegram_bot'))` is "violated by some row". Root: the live demo DB has 11 visits rows with channel='client_qr'; downgrading 0045 restores the 2-value CHECK which those rows violate. This is a PRE-EXISTING data-dependency failure (the test was designed for a clean DB), NOT the deadlock and NOT a regression — and it now FAILS FAST instead of hanging. alembic_version stayed at head 0073 (transactional DDL rolled the failed downgrade back; no schema damage).
  STEP 2 (collection blocker found + fixed): First full-suite attempt aborted at COLLECTION (2 errors) — unrelated to deadlock, caused by the starlette 1.3.1 bump (commit 1352ef74): importing starlette.testclient/fastapi.testclient emits StarletteDeprecationWarning ("install httpx2 instead") which filterwarnings=error promotes to a collection error for tests/messaging + tests/unit/test_webhook_router_smoke.py. Fix: added `ignore::starlette.exceptions.StarletteDeprecationWarning` to filterwarnings (mirrors the existing botocore idiom). After fix: `pytest --collect-only` => 3071 tests collected, exit 0.
  STEP 3 (second deadlock site found + fixed): With deadlock-test-1 fixed + pytest-timeout active, the full run hit a SECOND deadlock at tests/integration/alembic/test_migration_0027_cleanup.py::test_0027_upgrade_with_colliding_unconsumed_rows — pytest-timeout (180s) killed it (safety net WORKED, dumped the stack at subprocess.communicate inside _run_alembic("downgrade", 0026)). Root: same mechanism — downgrade to 0026/0032 passes THROUGH 0070/0071, so it also contends the autouse working_hours_config/booking_config row lock. (My earlier assumption that "downgrade to 0026 doesn't touch working_hours_config" was WRONG — it downgrades the whole chain from head.) Fix: added the no_permissive_booking_config marker (module-level pytestmark) to BOTH tests/integration/alembic/test_migration_0027_cleanup.py and test_migration_0033_clients_email.py (the only two other files invoking `alembic downgrade`). Re-ran tests/integration/alembic/ in isolation: completed in 10s (was infinite hang) — 1 passed, 5 failed.
  STEP 4 (the residual alembic-dir failures are a PRE-EXISTING DATA dependency, NOT the deadlock): All 5 failures are the SAME CheckViolationError — the downgrade chain fails at the 0045 downgrade `ALTER TABLE visits ADD CONSTRAINT ck_visits_channel CHECK (channel IN ('reception','telegram_bot'))` because the LIVE DEMO DB has 11 visits rows with channel='client_qr' (verified: SELECT channel,count(*) FROM visits => client_qr=11, reception=47). These migration-reversibility tests assume a CLEAN/empty DB (they pass in CI against a fresh DB); against the populated demo DB the existing client_qr rows violate the restored 2-value CHECK. This is environmental data precondition, not a code bug — and it now FAILS FAST instead of hanging. Out of scope to "fix" (would require altering test assertions or wiping visits).
  STEP 5 (THIRD deadlock site — same root cause, different trigger): Full run with the 2 fixes hit a hang at ~7% in tests/integration/client_portal/test_client_booking_race.py::test_concurrent_client_create_booking_partial_unique_at_db_layer. Captured live pg_blocking_pids: PID 75068 (the test's db_session_real_commit) = active/Lock, blocked_by {75067}; PID 75067 (autouse db_session) = idle in transaction holding UPDATE working_hours_config. The test EXPLICITLY does `UPDATE working_hours_config` via its own real-commit connection (to make config visible to the concurrent HTTP bookings), which deadlocks against the autouse fixture's uncommitted UPDATE of the SAME singleton. Fix: marked the module no_permissive_booking_config (it owns its config setup). Re-ran: PASSES in 1.02s (was infinite hang).
  STEP 5b (timeout method switched thread->signal): pytest-timeout `thread` method calls os._exit() on first timeout, aborting the WHOLE run. Switched default to `signal` (SIGALRM on main thread) which FAILS ONLY the offending test and continues — so a future regression degrades to one failed test, not a whole-run abort, AND lets a full run complete for tallying.
  STEP 5c (complete deadlock-prone set identified): grepped ALL tests writing working_hours_config/booking_config from a SEPARATE connection (real-commit engine or alembic subprocess). Exhaustive set = the 4 now-marked files. Tests that write config via the shared SAVEPOINT db_session (test_new_enforcement_guards.py, test_booking_settings_enforcement.py) are SAFE (same transaction — UPDATEs just stack, no cross-connection lock). test_p102_booking_lifecycle.py only references config in comments.
  STEP 6 (FIRST full suite COMPLETED — no hang): 14m34s, reached 100% with ZERO timeouts + ZERO lock-blocks across the whole run (heartbeat log proved 2%->100% steady progress). Tally: 3054 passed, 4 failed, 5 errors, 8 skipped (of 3071). DEADLOCK DEFINITIVELY RESOLVED.
  STEP 7 (classify the residual 4 failed + 5 errors):
    - FAILED test_freeze_race::...partial_unique_index => "Unexpected 409 codes: [...'invalid_transition'...]" — concurrency TIMING race = task known-failure #1. NOT mine.
    - FAILED test_phase51_audit_chain_invariants::...is_85 => "Expected 117 LOCKED_AUDIT_EVENTS, got 118" — stale hardcoded count (audit taxonomy debt, same family as task known #2). Static test, DB-independent. NOT mine.
    - FAILED test_route_introspection::test_every_protected_route_declares_a_gate => "Routes missing gate: ['/metrics']" — prometheus /metrics not in EXCLUDED_PATHS. Static test, pre-existing. NOT mine.
    - FAILED test_settings_endpoints::test_owner_get_booking_config_returns_seeded_singleton => "assert 365 == 14" — booking_ahead_days=365 leaked. ROOT: test_client_booking_race does a REAL-COMMIT `UPDATE booking_config SET booking_ahead_days=365` but its teardown TRUNCATE list EXCLUDES booking_config/working_hours_config, and (now) it opts out of the autouse fixture that previously would have rolled it back. Before my fix this test DEADLOCKED so never committed 365; un-deadlocking it ACTIVATED a latent leak. THIS ONE IS A SIDE-EFFECT OF MY FIX — fixed by adding a teardown restore of both singletons to migration-0071 seeded values (booking_ahead_days=14, cutoff_minutes=60, schedule=seeded, closures=[]).
    - 5 ERRORs all = asgi_lifespan TimeoutError (per-test create_app()+LifespanManager startup exceeding asgi-lifespan's 5s under full-suite load) — known full-suite lifespan-probe pollution (knowledge base test-debt-sweep-v19 + task known #2 family; pass in isolation). NOT mine.
  STEP 8 (settings failure was NOT a leak — it's pre-existing, fails in isolation): Re-checked: test_owner_get_booking_config_returns_seeded_singleton fails `assert 365==14` EVEN IN ISOLATION because the global autouse permissive_booking_config sets booking_ahead_days=365 and the settings endpoint reads the same overridden db_session. So it's a pre-existing test bug independent of the race-test leak. Fixed by marking THAT test no_permissive_booking_config (now passes in isolation, verified). The race-test teardown restore I added is still correct hardening (prevents real-commit config mutations leaking into the shared/demo DB) — confirmed booking_config returns to 14|60 after the race test.
  STEP 9 (FINAL full-suite re-verify — DONE): 15m08s, reached 100%, ZERO timeouts + ZERO lock-blocks the entire run. Tally: 3058 passed, 3 failed, 2 errors, 8 skipped (improved from 3054/4/5 — the settings test now passes via its marker; asgi_lifespan errors are non-deterministic flakes, 2 this run). Residual failures verified to be EXACTLY the documented pre-existing set (test_freeze_race timing, test_phase51_audit_chain_invariants stale count 117!=118, test_route_introspection /metrics gate) + 2 asgi_lifespan TimeoutError ERRORs (full-suite lifespan-probe pollution, pass in isolation). NONE touch permissive_booking_config/working_hours_config/any changed code.
  STEP 10 (demo DB re-seeded — guardrail 4): pytest wiped users/clients/bookings/visits (singletons survived). Copied scripts into backend container, ran seed_demo_data + seed_dev_client (owner@clubcore.dev, dev client, 1 plan, 1 PT package, 2 promos). Login POST /api/v1/auth/login => 200 CONFIRMED.
  STEP 11 (lint): import-sort auto-fixed on conftest.py (the only new violation). Remaining RUF002 en-dash + TABLE_REF noqa warnings are PRE-EXISTING (unchanged docstring lines / project-custom lint code). No new violations introduced.
  RESIDUAL PRE-EXISTING FAILURES (documented, NOT chased — orthogonal to deadlock):
    - test_freeze_race::...partial_unique_index (concurrency timing — task known #1)
    - test_phase51_audit_chain_invariants::...is_85 (stale hardcoded LOCKED_AUDIT_EVENTS count 117 vs actual 118)
    - test_route_introspection::test_every_protected_route_declares_a_gate (/metrics not in EXCLUDED_PATHS)
    - ~5 asgi_lifespan TimeoutError ERRORs (full-suite lifespan-probe startup pollution; pass in isolation — knowledge base test-debt-sweep-v19)
files_changed:
  - tests/integration/conftest.py (marker opt-out in autouse fixture)
  - tests/integration/bookings/conftest.py (marker opt-out in autouse fixture)
  - tests/integration/migrations/test_visits_channel_client_qr.py (module marker)
  - tests/integration/alembic/test_migration_0027_cleanup.py (module marker)
  - tests/integration/alembic/test_migration_0033_clients_email.py (module marker)
  - tests/integration/client_portal/test_client_booking_race.py (module marker)
  - pyproject.toml (register marker, pytest-timeout dep + config, suppress starlette deprecation)
