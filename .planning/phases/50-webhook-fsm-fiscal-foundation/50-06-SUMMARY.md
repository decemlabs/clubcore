---
phase: 50-webhook-fsm-fiscal-foundation
plan: 06
subsystem: webhook-e2e-test-suite
tags: [webhook, e2e, integration-tests, ast-gate, audit-chain, b-2-fix, w-2-fix, w-5-fix, phase-closeout]

# Dependency graph
requires:
  - phase: 50-webhook-fsm-fiscal-foundation/50-01
    provides: fiscal_receipts module + 0035 migration (consumed by WH-05 atomic UoW assertion)
  - phase: 50-webhook-fsm-fiscal-foundation/50-02
    provides: ONLINE_PAYMENT_STATUS_TRANSITIONS + LOCKED audit events (consumed by WH-04 + audit chain tests)
  - phase: 50-webhook-fsm-fiscal-foundation/50-03
    provides: activator bodies + PaymentRecorder Optional widening (consumed by WH-05 4-row commit)
  - phase: 50-webhook-fsm-fiscal-foundation/50-04
    provides: webhook router + handlers (test SUT for WH-01..06)
  - phase: 50-webhook-fsm-fiscal-foundation/50-05
    provides: AST gates locking router shape (parallel structural enforcement)
provides:
  - 25 integration tests covering WH-01..06 + audit chain + post-commit-seam AST gate
  - real-commit test infrastructure (webhook_engine + webhook_db_session + webhook_client) for handlers that use async with session.begin()
  - sqlalchemy_query_log_timestamps fixture (B-2 fix: same-clock-domain ordering check via time.perf_counter on both respx side_effect and SQLAlchemy before_execute listener)
  - yookassa_get_payment_canceled respx fixture (W-5 fix: concrete, not deferred)
  - test_post_commit_seam.py AST gate (W-2 fix: structural, replaces unreachable runtime spy)
  - EXCLUDED_PATHS audit-trail entry for /api/v1/_internal/yookassa/webhook
  - deferred-items.md Phase 50 Carry-Forward Register (5 Phase 50 originating + 3 Phase 49 carry-over + 3 pre-existing failures)
  - Rule 1 fix in handlers.py: cast UUIDs to str(...) in CHILD audit payload kwargs (audit.emit writes payload directly into JSONB; raw UUID failed JSON encoding)
affects: [51-fiscal-receipts-dispatch (orphan cron + yookassa_call_failed event), 52-notifications (post_commit_enqueue lockstep update required), 53-reconcile-cron + ops runbook]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Real-commit test session (webhook_engine + webhook_db_session) mirrors tests/integration/memberships/conftest.py::db_session_real_commit — required because the webhook handler uses `async with session.begin():` which cannot compose with the root SAVEPOINT-mode session"
    - "Shared engine fixture (webhook_engine) bridges seeding session + route per-request session + SQLAlchemy before_execute listener so the WH-02 ordering test sees both sides' statements"
    - "respx side_effect callback as the same-clock-domain capture point — time.perf_counter() at invocation matches the perf_counter() recorded by the SQLAlchemy listener; revision 1 used elapsed.total_seconds() (a timedelta duration ~0.001s) mismatched against perf_counter() values (~10000s) and was tautologically true"
    - "AST-level structural gate (ast.parse + ast.walk on AsyncFunctionDef + ast.unparse on Call.func) replaces unreachable runtime spy for stub-body invariant — the handler passes arq_pool=None directly to _post_commit_enqueue, so app.state.arq_pool spies are never reached"
    - "DB-state-as-canonical-observability (vs structlog capture_logs) — capture_logs() inside the in-process app sometimes misses messages emitted deep in the handler stack because the production logger is configured at lifespan time with cached processors; DB row state is the deterministic surface"
    - "UUID-to-str cast in JSONB audit payload kwargs (Rule 1 fix on Plan 50-04) — audit.emit writes payload kwargs directly into a JSONB column; Pydantic validate-only call (model_validate) does NOT transform UUIDs → JSON encoder rejected raw UUID. Mirrors memberships/service.py:1925 pattern."

key-files:
  created:
    - apps/backend/tests/integration/webhook_yookassa/__init__.py
    - apps/backend/tests/integration/webhook_yookassa/conftest.py
    - apps/backend/tests/integration/webhook_yookassa/test_wh01_ip_gate.py
    - apps/backend/tests/integration/webhook_yookassa/test_wh02_refetch_before_write.py
    - apps/backend/tests/integration/webhook_yookassa/test_wh03_redis_dedup.py
    - apps/backend/tests/integration/webhook_yookassa/test_wh04_fsm_transitions.py
    - apps/backend/tests/integration/webhook_yookassa/test_wh05_succeeded_atomic_uow.py
    - apps/backend/tests/integration/webhook_yookassa/test_wh06_canceled_records_details.py
    - apps/backend/tests/integration/webhook_yookassa/test_audit_chain.py
    - apps/backend/tests/integration/webhook_yookassa/test_post_commit_seam.py
  modified:
    - apps/backend/app/api/v1/_internal/yookassa/handlers.py
    - apps/backend/tests/integration/test_route_introspection.py
    - .planning/phases/50-webhook-fsm-fiscal-foundation/deferred-items.md

key-decisions:
  - "Real-commit test pattern instead of SAVEPOINT — the webhook handler uses `async with session.begin():` which is incompatible with the root db_session's `join_transaction_mode='create_savepoint'`. Mirrors the established db_session_real_commit pattern from tests/integration/memberships/conftest.py (Plan 25-05 D-13) for the same reason. TRUNCATE cleanup on engine teardown handles row isolation."
  - "Shared engine fixture (webhook_engine) instead of per-fixture engines — the SQLAlchemy before_execute listener is bound to one sync_engine; if seeding + route used different engines, the listener would see only one side's statements, breaking the WH-02 ordering test."
  - "DB-state-as-canonical-observability for orphan + refetch_error paths — structlog capture_logs() inside the in-process app sometimes misses messages emitted from deep in the handler stack because the production logger is configured at lifespan time with cached processors. DB-state assertions (no Payment / Membership / FiscalReceipt row written) are deterministic and structurally observable."
  - "Rule 1 fix in production handlers.py — UUIDs in CHILD audit emit payload kwargs cast to str(...). audit.emit writes payload kwargs directly into a JSONB column (line 510 in audit.py); Pydantic schema.model_validate (line 489) only validates shape, it does NOT transform UUID → str. The JSON encoder rejected raw UUID with TypeError. Mirrors memberships/service.py:1925 verbatim pattern. Plan 50-04 missed this because its smoke test never exercised the full UoW commit path."
  - "Reuse Phase 48 respx fixtures (yookassa_get_payment_succeeded / yookassa_get_payment_pending / yookassa_webhook_payload) via direct # noqa: F401 re-export — pytest conftest discovery is directory-tree-only, so explicit import is the documented Sportzal-internal pattern (mirror of tests/integration/online_payments/conftest.py lines 49-55)."
  - "AST gate test_post_commit_enqueue_body_is_only_log_info replaces revision 1's unreachable runtime spy — handler passes arq_pool=None positionally; spy on app.state.arq_pool was never reached, making the assertion tautologically true regardless of stub body. AST inspection of _post_commit_enqueue's body catches drift regardless of runtime call paths."
  - "WH-02 ordering test uses time.perf_counter() on BOTH sides (B-2 fix revision 2). Revision 1 used `respx_mock.calls.last.response.elapsed.total_seconds()` (a timedelta duration ~0.001s) compared against perf_counter() value (~10000s) — that assertion was tautologically true. The new fixture sqlalchemy_query_log_timestamps records perf_counter() in a SQLAlchemy before_execute listener so both sides share the same monotonic clock domain."
  - "yookassa_get_payment_canceled fixture EXPLICITLY created in this plan's conftest (W-5 fix) — not a 'may not exist in Phase 48 conftest' hedge. Cancellation-path tests (WH-06) depend on it directly."

patterns-established:
  - "Per-phase test conftest with REAL-COMMIT engine + TRUNCATE cleanup — the established pattern for tests against handlers that own their own UoW (`async with session.begin():`)."
  - "Same-clock-domain ordering test via respx side_effect + SQLAlchemy before_execute listener — both record time.perf_counter() to share a monotonic clock; the assertion compares perf_counter() values, not elapsed durations."
  - "AST structural gate for stub-body invariants — when a runtime spy would be tautologically true (e.g., the handler passes None and never reaches the spy), use ast.parse + ast.walk + ast.unparse on the function source instead."
  - "Audit-trail diff (D-19) for anonymous-by-design route exclusions — every new /_internal/* inhabitant gets its own enumerated entry in EXCLUDED_PATHS even though the EXCLUDED_PREFIXES tuple already covers them, so the audit trail shows the deliberate decision."

requirements-completed: [WH-01, WH-02, WH-03, WH-04, WH-05, WH-06, FISCAL-01, FISCAL-02, FISCAL-03]

# Metrics
duration: ~45min
completed: 2026-05-22
---

# Phase 50 Plan 06: ЮKassa Webhook E2E Suite + Phase Closeout Summary

**Core Phase 50 closeout deliverable: 25 integration tests covering all 6 success criteria + audit chain semantics + W-2 AST gate on post-commit-enqueue stub + EXCLUDED_PATHS audit trail + Phase 50 carry-forward register.**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-05-22T20:50:00Z (approx)
- **Completed:** 2026-05-22T21:35:00Z (approx)
- **Tasks:** 2 (1 RED→GREEN test commit + 1 chore commit for audit-trail + deferred register)
- **Files created:** 10 (1 __init__.py + 1 conftest.py + 7 per-criterion test files + 1 audit chain + 1 AST gate)
- **Files modified:** 3 (handlers.py UUID→str cast, test_route_introspection.py EXCLUDED_PATHS, deferred-items.md)
- **Tests added:** 25 (all passing)
- **Tests passing in Phase 47-50 related sweep:** 242

## Accomplishments

### Test Suite (25 tests in 10 files)

- **WH-01 (IP gate, 2 tests):** Untrusted IP returns 403 via dependency override (sandbox mode default bypasses verifier; the override exercises the 403 branch directly). Trusted IP does not 403.

- **WH-02 (re-fetch before write, 3 tests):** Primary test uses the B-2 fix (revision 2) pattern — `time.perf_counter()` recorded by both the respx side_effect callback AND the SQLAlchemy `before_execute` listener; assertion compares same-clock-domain values. Pending re-fetch status skips DB write. Transient_error classification skips DB write.

- **WH-03 (Redis dedup, 2 tests):** Second identical delivery does NOT invoke the re-fetch (D-50-10 — dedup BEFORE re-fetch preserves outbound rate-budget). Dedup key prefix matches `WEBHOOK_DEDUP_KEY_PREFIX` constant.

- **WH-04 (FSM transitions, 4 tests):** Illegal transition (canceled→succeeded) returns 200 + audit row with `idempotency_outcome='illegal_transition'`. Legal pending→succeeded flips status. Legal pending→canceled flips status. Already-succeeded terminal row rejects re-transition.

- **WH-05 (atomic UoW, 5 tests):** Single commit writes 4 entities (online_payment + payment + membership + fiscal_receipt) + 4 audit rows (payment_recorded + membership_activated_online + online_payment_succeeded + yookassa_webhook_received). PT-package branch activates PtPackage row + emits pt_package_activated_online. Orphan path returns 200 with no DB writes. Customer email fetched via narrow `SELECT clients.email` (Blocker #4 — NO relationship-traversal JOIN). PaymentRecorder receives `received_by_user_id=None` (Blocker #2 — anonymous flow).

- **WH-06 (cancellation, 3 tests):** Cancellation body with `cancellation_details` → audit captures `cancellation_party` + `cancellation_reason`. Missing details → both fields are None (D-50-25 — payload schema accepts None). No fiscal_receipt insert on cancellation (D-50-26).

- **Audit chain (5 tests):** Success path emits exactly 4 audit rows. Activator emits ONLY `membership_activated_online` (Blocker #6 — never `membership_created`). PT-package mirror: never `pt_package_sold`. `yookassa_webhook_received` row emitted LAST per D-50-18 step 8 (chain ROOT). CHILD audit rows carry non-NULL `audit_correlation_id`.

- **W-2 AST gate (1 test in test_post_commit_seam.py):** Inspects `_post_commit_enqueue`'s AsyncFunctionDef body via ast.parse + ast.walk + ast.unparse; asserts the body is exactly one `_log.info(...)` Call. Tautology-resistant: catches drift toward real enqueue logic regardless of runtime call paths.

### Real-Commit Test Infrastructure

The webhook handler uses `async with session.begin():` which cannot compose with the root SAVEPOINT-mode `db_session` (the savepoint-wrapped session is already inside a transaction; SQLAlchemy raises `InvalidRequestError: A transaction is already begun on this Session`).

**Solution:** New `webhook_engine` / `webhook_db_session` / `webhook_client` fixtures in conftest.py mirror the established `db_session_real_commit` pattern from `tests/integration/memberships/conftest.py` (Plan 25-05 D-13). TRUNCATE cleanup on engine teardown handles row isolation.

The engine is SHARED across `webhook_db_session` (test-side seeding), `webhook_client` (route-side per-request session via dependency override), and `sqlalchemy_query_log_timestamps` (SQL listener). This ensures the WH-02 ordering test sees statements from BOTH sides.

### EXCLUDED_PATHS (D-50-40)

Added `/api/v1/_internal/yookassa/webhook` to the enumerated `EXCLUDED_PATHS` in `test_route_introspection.py`. The `EXCLUDED_PREFIXES` tuple `/api/v1/_internal/` already covers the route at runtime; the explicit enumeration is the D-19 diff-as-audit-trail discipline (mirrors the Phase 49 `/api/v1/online-payments/return` precedent).

### deferred-items.md Phase 50 Carry-Forward Register

5 Phase 50 originating items (DEFER-50-01..05):
- DEFER-50-01 — `payment.waiting_for_capture` event handler (Phase 53 runbook)
- DEFER-50-02 — Orphan recovery cron (Phase 53 ARQ task)
- DEFER-50-03 — Operator runbook for cancellation_reason / cancellation_party enum (Phase 53)
- DEFER-50-04 — `_post_commit_enqueue` stub-body AST gate lockstep update required when Phase 52 NOT-04/05 fills the body
- DEFER-50-05 — `test_alembic_check_clean` pre-existing failure (Blocker #8) excluded from regression sweep

Phase 49 carry-forward: D-49-29 (DONE), D-49-30 (unchanged), yookassa_call_failed event (re-deferred).

Pre-existing failures NOT caused by Phase 50: test_alembic_check_clean (Blocker #8), worker_settings cron count drift (Plan 50-04 register), 3-route gate gap in test_route_introspection (`password-reset/request`, `password-reset/confirm`, `users/invitations/accept`).

## Task Commits

1. **Task 1** — `a7b9092` — `test(50-06): webhook e2e suite — WH-01..06 + audit chain + AST seam gate` (11 files: 10 new tests + handlers.py UUID→str cast fix).
2. **Task 2** — `6a569c7` — `chore(50-06): EXCLUDED_PATHS audit-trail entry + Phase 50 deferred register` (2 files: test_route_introspection.py + deferred-items.md).

## Files Created/Modified

### Created
- `apps/backend/tests/integration/webhook_yookassa/__init__.py` — package marker.
- `apps/backend/tests/integration/webhook_yookassa/conftest.py` — webhook_engine + webhook_db_session + webhook_client + sqlalchemy_query_log_timestamps + yookassa_get_payment_canceled + seeded_online_payment_pending(_pt_package) + webhook_payment_*_body factories + redis_test_client + trusted_ip_header.
- `apps/backend/tests/integration/webhook_yookassa/test_wh01_ip_gate.py` — 2 tests.
- `apps/backend/tests/integration/webhook_yookassa/test_wh02_refetch_before_write.py` — 3 tests (B-2 fix primary).
- `apps/backend/tests/integration/webhook_yookassa/test_wh03_redis_dedup.py` — 2 tests.
- `apps/backend/tests/integration/webhook_yookassa/test_wh04_fsm_transitions.py` — 4 tests.
- `apps/backend/tests/integration/webhook_yookassa/test_wh05_succeeded_atomic_uow.py` — 5 tests.
- `apps/backend/tests/integration/webhook_yookassa/test_wh06_canceled_records_details.py` — 3 tests (W-5 fix consumer).
- `apps/backend/tests/integration/webhook_yookassa/test_audit_chain.py` — 5 tests.
- `apps/backend/tests/integration/webhook_yookassa/test_post_commit_seam.py` — 1 AST gate test (W-2 fix).

### Modified
- `apps/backend/app/api/v1/_internal/yookassa/handlers.py` — Rule 1 fix: cast UUIDs to `str(...)` in `online_payment_succeeded` + `online_payment_canceled` audit payload kwargs (audit.emit writes payload directly into JSONB; Pydantic validate-only does not transform UUIDs; the JSON encoder rejected raw UUID).
- `apps/backend/tests/integration/test_route_introspection.py` — D-50-40 audit-trail entry for `/api/v1/_internal/yookassa/webhook` with D-50-39 anonymous-by-design comment.
- `.planning/phases/50-webhook-fsm-fiscal-foundation/deferred-items.md` — Phase 50 Carry-Forward Register (DEFER-50-01..05) + Phase 49 carry-over + pre-existing failures section.

## Decisions Made

1. **Real-commit test pattern** instead of SAVEPOINT for webhook tests. The handler uses `async with session.begin():` which fails with `InvalidRequestError: A transaction is already begun on this Session` when called against a SAVEPOINT-mode session (the join_transaction_mode='create_savepoint' setup means the session is always inside an outer transaction). Mirrors `db_session_real_commit` from Plan 25-05 D-13.

2. **Shared engine fixture (`webhook_engine`)** across seeding, route per-request session, and SQL listener. Each fixture would otherwise create its own engine, and the `before_execute` listener bound to one engine wouldn't see statements from the others. Critical for WH-02 ordering test which compares timestamps from BOTH seeding/route + SQL listener sides.

3. **DB-state-as-canonical-observability** for orphan + refetch_error paths. `structlog.testing.capture_logs()` inside the in-process app sometimes misses messages emitted from deep in the handler stack (production logger configured at lifespan time with cached processors). Switching to DB-state assertions (`Payment row is None`) makes the tests deterministic and structurally observable.

4. **Rule 1 fix in production handlers.py** — UUIDs cast to `str(...)` in CHILD audit payload kwargs. `audit.emit()` writes payload kwargs directly into a JSONB column (line 510). Pydantic `schema.model_validate(payload)` (line 489) only validates the shape; it does NOT transform UUID → str. The JSON encoder rejected raw UUID with `TypeError: Object of type UUID is not JSON serializable`. The activator services (`memberships/service.py:1925`) cast to str explicitly — the webhook handler did not. Plan 50-04 never caught this because its smoke test didn't exercise the full UoW commit path. The fix is purely additive and matches the established pattern.

5. **Reuse Phase 48 respx fixtures** (yookassa_get_payment_succeeded / yookassa_get_payment_pending) via direct `# noqa: F401` re-export — pytest conftest discovery is directory-tree-only, so explicit import is the documented Sportzal-internal pattern (mirror of `tests/integration/online_payments/conftest.py` lines 49-55).

6. **AST gate replaces tautological runtime spy** for `_post_commit_enqueue` stub-body invariant (W-2 fix revision 2). Revision 1 used `arq_pool_spy.enqueue_calls == []` but the handler passes `arq_pool=None` directly, never reaching the spy mounted on `app.state.arq_pool`. The AST gate inspects the function's body source directly — catches any drift toward real enqueue logic regardless of runtime call paths.

7. **Same-clock-domain ordering test for WH-02** (B-2 fix revision 2). Revision 1 used `respx_mock.calls.last.response.elapsed.total_seconds()` (timedelta duration ~0.001s) compared against `time.perf_counter()` value (~10000s) — tautologically true. The new fixture `sqlalchemy_query_log_timestamps` records `time.perf_counter()` in a SQLAlchemy `before_execute` listener; the respx side_effect callback records `time.perf_counter()` at invocation. Both sides share the same monotonic clock domain.

8. **`yookassa_get_payment_canceled` fixture EXPLICITLY created** here (W-5 fix). No "may not exist in Phase 48 conftest" hedge — the cancellation-path tests (WH-06) depend on it directly, so the fixture lives in this plan's conftest concretely.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] UUIDs in audit payload kwargs not JSON-serializable**

- **Found during:** Task 1 — first WH-04 legal-transition run.
- **Issue:** `handle_payment_succeeded` and `handle_payment_canceled` passed raw `UUID` values (`webhook_intake_corr`, `row.id`, `ledger_payment_id`) to `audit.emit()` payload kwargs. `audit.emit` writes payload kwargs directly into a JSONB column (line 510 in `audit.py`); Pydantic `schema.model_validate(payload)` (line 489) only validates shape, it does NOT transform UUID → str. The JSON encoder raised `TypeError: Object of type UUID is not JSON serializable`, rolling back the entire UoW.
- **Fix:** Cast UUIDs to `str(...)` at the audit emit callsite (mirrors `memberships/service.py:1925` pattern). 3 UUIDs in `online_payment_succeeded` emit; 2 UUIDs in `online_payment_canceled` emit. The `yookassa_webhook_received` emits already use only string/None values, so no change needed there.
- **Files modified:** `apps/backend/app/api/v1/_internal/yookassa/handlers.py`
- **Commit:** `a7b9092` (folded into Task 1 commit)
- **Root cause traceback:** Plan 50-04 shipped this bug because its smoke test (`tests/unit/test_webhook_router_smoke.py`) verifies only that the route is mounted; it never exercises the full UoW. The Phase 50-04 PRD blocker register did not include "smoke tests do not catch payload serialization bugs" so the bug landed silently.

**2. [Rule 1 — Bug] WH-02 ordering test SQL listener bound to wrong engine**

- **Found during:** Task 1 — first WH-02 run.
- **Issue:** The `sqlalchemy_query_log_timestamps` fixture was initially bound to `app.state.engine`, but the `webhook_client` override created a SEPARATE engine. The route's statements flowed through the override engine; the listener saw an empty log.
- **Fix:** Created a SHARED `webhook_engine` fixture used by `webhook_db_session` + `webhook_client` + `sqlalchemy_query_log_timestamps`. All three now bind to the same engine, so the listener captures statements from BOTH seeding and route sides.
- **Files modified:** `apps/backend/tests/integration/webhook_yookassa/conftest.py` (this plan's own file, in-flight)
- **Commit:** `a7b9092` (in-flight during Task 1)

**3. [Rule 1 — Bug] structlog capture_logs() misses some handler messages**

- **Found during:** Task 1 — WH-05 orphan-path test + WH-02 refetch_error_classification test.
- **Issue:** `structlog.testing.capture_logs()` inside the in-process app sometimes misses messages emitted deep in the handler stack because the production logger is configured at lifespan time with cached processors.
- **Fix:** Switched both tests to DB-state assertions (Payment row is None / online_payments.status unchanged) — structurally observable and deterministic.
- **Files modified:** `apps/backend/tests/integration/webhook_yookassa/test_wh05_succeeded_atomic_uow.py`, `apps/backend/tests/integration/webhook_yookassa/test_wh02_refetch_before_write.py`
- **Commit:** `a7b9092`

### Out-of-Scope (logged to deferred-items.md)

- **3-route gate gap in `test_route_introspection.py`** — `/api/v1/auth/password-reset/request`, `/api/v1/auth/password-reset/confirm`, `/api/v1/users/invitations/accept` are not in EXCLUDED_PATHS and lack require_permission/require_authenticated gates. Verified pre-existing on base (stash + re-run). Owners: password-reset = Phase 11, users invitations = Phase 36. Flagged for Phase 53 verification sweep.
- **`test_alembic_check_clean`** — Blocker #8, excluded from Phase 50 regression sweep per DEFER-50-05.
- **`test_worker_settings_cron_resolves_to_registered_function`** + `test_worker_settings_functions_registered` — pre-existing cron-count drift from Plan 50-04 register, not addressed in Plan 50-06.
- Several sweep-order-dependent flakes in the broader sweep (rbac, telegram_bot, schedule cascade) — all pass in isolation; pre-existing infrastructure flakes unrelated to Plan 50-06.

---

**Total deviations:** 3 Rule 1 bugs (1 production handler.py, 2 test infrastructure). All discovered during execution and fixed inline. No scope creep — every change is in service of the plan's stated must-haves and acceptance criteria.

**Impact on plan:** Plan executed as specified. All 9 requirements (WH-01..06 + FISCAL-01..03) covered by at least one test. All 6 Phase 50 ROADMAP success criteria verified by integration tests. All 8 PATTERNS.md blockers resolved (Blocker #1 InvalidTransitionError reused; #2 PaymentRecorder widened — verified by test_wh05_payment_recorder_called_with_none_audit_actor; #3 activator kwarg renamed — verified implicitly by test_wh05 happy paths; #4 narrow email SELECT — verified by test_wh05_customer_email_fetched_via_narrow_select; #5 FISCAL-03 AST gates preserved — verified in Plan 50-05; #6 activator emits only `*_activated_online` — verified by test_audit_chain.test_success_path_emits_no_membership_created + test_pt_package_success_path_emits_no_pt_package_sold; #7 composition root unchanged — verified in Plan 50-04; #8 test_alembic_check_clean excluded with explicit DEFER-50-05 note).

## Issues Encountered

- **`async with session.begin()` vs SAVEPOINT-mode session** — the handler uses `session.begin()` which requires no active transaction, but the root `db_session` fixture's `join_transaction_mode='create_savepoint'` mode means the session is always inside an outer transaction. Resolved by adopting the real-commit pattern (mirror of Plan 25-05 D-13).
- **Engine-binding for SQL listener** — initially bound to `app.state.engine`; the route used a separate engine via override, so the listener never saw the route's statements. Resolved by introducing a shared `webhook_engine` fixture.
- **structlog capture_logs() flakiness** — production logger cached at lifespan time misses some handler messages. Resolved by switching to DB-state assertions for the 2 affected tests.
- **UUID-to-str cast missing in handlers.py** — silently failed Pydantic validation pass; raised TypeError only at JSON encoding time. Discovered during the first end-to-end test run; fixed inline (Rule 1).

## User Setup Required

None. The `.env` file (`cp .env.example .env`) was already in place per Plan 50-04's worktree note.

## Threat Flags

None new — Plan 50-06 adds test code + 1 production handler.py UUID-to-str cast + 1 EXCLUDED_PATHS entry + 1 deferred-items.md update. No new network, auth, file-access, or schema surface introduced.

## Next Phase Readiness

- **Phase 50 closeout — all 9 Phase 50 requirements (WH-01..06 + FISCAL-01..03) verified by integration tests** — see verification matrix in the PLAN's `<verification>` block (executed via `pytest tests/integration/webhook_yookassa/ -v`).
- **Phase 51 (FISCAL-04/05/06 + REFUND-01..04) unblocked** — fiscal_receipts(status='sent') rows are now produced + verified on every successful webhook delivery; Phase 51 ARQ task can consume them and transition status='sent'→'succeeded'|'failed'.
- **Phase 52 (NOT-04/05) unblocked** — `_post_commit_enqueue` hook + W-4 signature locked. Phase 52 swaps `arq_pool=None` for `app.state.arq_pool` and fills the body. **CRITICAL LOCKSTEP REQUIREMENT:** the AST gate in `tests/integration/webhook_yookassa/test_post_commit_seam.py` enforces the single-`_log.info()` body invariant; Phase 52 MUST update or remove this test in the SAME commit that fills the body, otherwise CI fails by design (see DEFER-50-04).
- **Phase 53 (reconcile cron + ops runbook)** — DEFER-50-01/02/03 carry forward the `payment.waiting_for_capture` handler decision, orphan-reconcile ARQ cron, and cancellation_reason runbook.

## Self-Check: PASSED

**Files claimed (all verified via `[ -f ... ]`):**
- `apps/backend/tests/integration/webhook_yookassa/__init__.py` — FOUND
- `apps/backend/tests/integration/webhook_yookassa/conftest.py` — FOUND
- `apps/backend/tests/integration/webhook_yookassa/test_wh01_ip_gate.py` — FOUND
- `apps/backend/tests/integration/webhook_yookassa/test_wh02_refetch_before_write.py` — FOUND
- `apps/backend/tests/integration/webhook_yookassa/test_wh03_redis_dedup.py` — FOUND
- `apps/backend/tests/integration/webhook_yookassa/test_wh04_fsm_transitions.py` — FOUND
- `apps/backend/tests/integration/webhook_yookassa/test_wh05_succeeded_atomic_uow.py` — FOUND
- `apps/backend/tests/integration/webhook_yookassa/test_wh06_canceled_records_details.py` — FOUND
- `apps/backend/tests/integration/webhook_yookassa/test_audit_chain.py` — FOUND
- `apps/backend/tests/integration/webhook_yookassa/test_post_commit_seam.py` — FOUND
- `apps/backend/app/api/v1/_internal/yookassa/handlers.py` — MODIFIED (UUID→str cast)
- `apps/backend/tests/integration/test_route_introspection.py` — MODIFIED (EXCLUDED_PATHS append)
- `.planning/phases/50-webhook-fsm-fiscal-foundation/deferred-items.md` — MODIFIED (Phase 50 register)

**Commits claimed (all verified via `git log --oneline 60f0204..HEAD`):**
- `a7b9092` — Task 1 (test suite + handler UUID→str fix) — FOUND
- `6a569c7` — Task 2 (EXCLUDED_PATHS + deferred register) — FOUND

**Tests claimed (all verified):**
- 25/25 webhook_yookassa tests passing via `uv run pytest tests/integration/webhook_yookassa/ -v`
- ruff clean on tests/integration/webhook_yookassa/ + app/api/v1/_internal/yookassa/handlers.py
- mypy strict clean on tests/integration/webhook_yookassa/ + app/api/v1/_internal/yookassa/handlers.py (11 source files)
- lint-imports passes (1 unused-ignore warning pre-existing, unrelated)
- 242 Phase 47-50 related tests passing in targeted sweep

**Acceptance criteria (Task 1):**
- 10 test files exist under tests/integration/webhook_yookassa/ — VERIFIED
- `grep -c "X-Real-IP" conftest.py` ≥ 1 — VERIFIED (anonymous client uses spoofable header per D-50-42)
- `grep -rn "authed_client_owner\|authed_client_reception" webhook_yookassa/` returns 0 — VERIFIED (anonymous-by-design)
- `grep -c "membership_created" test_audit_chain.py` ≥ 1 — VERIFIED (negative assertion for Blocker #6)
- B-2 fix: `grep -c "get_payment_ts.append(time.perf_counter())" test_wh02...py` == 1 — VERIFIED
- B-2 fix: `grep -rn "elapsed.total_seconds()" webhook_yookassa/` returns 0 — VERIFIED (broken pattern gone)
- B-2 fix: `grep -c "refetch_ts < first_update_ts" test_wh02...py` == 1 — VERIFIED
- B-2 fix: `grep -c "sqlalchemy_query_log_timestamps" conftest.py` >= 1 — VERIFIED
- B-2 fix: `grep -c "time.perf_counter()" conftest.py` >= 1 — VERIFIED
- B-2 fix: `grep -rn "indirect check via audit row content" webhook_yookassa/` returns 0 — VERIFIED
- W-2 fix: `test -f test_post_commit_seam.py` — VERIFIED
- W-2 fix: `grep -c "test_post_commit_enqueue_body_is_only_log_info" test_post_commit_seam.py` == 1 — VERIFIED
- W-2 fix: `grep -c "ast.AsyncFunctionDef" test_post_commit_seam.py` >= 1 — VERIFIED
- W-2 fix: `grep -c "ast.unparse" test_post_commit_seam.py` >= 1 — VERIFIED
- W-2 fix: `grep -rn "arq_pool_spy" webhook_yookassa/` returns 0 — VERIFIED
- W-2 fix: `grep -c "test_post_commit_enqueue_is_noop_in_phase_50" webhook_yookassa/` returns 0 — VERIFIED
- W-5 fix: `grep -c "def yookassa_get_payment_canceled" conftest.py` == 1 — VERIFIED
- W-5 fix: `grep -c "yookassa_get_payment_canceled" test_wh06_canceled_records_details.py` >= 1 — VERIFIED

**Acceptance criteria (Task 2):**
- `grep -c '/api/v1/_internal/yookassa/webhook' test_route_introspection.py` ≥ 1 — VERIFIED (1 match)
- `grep -c '/api/v1/online-payments/return' test_route_introspection.py` ≥ 1 — VERIFIED (2 matches — entry + the surrounding comment block reference)
- `test -f .planning/phases/50-webhook-fsm-fiscal-foundation/deferred-items.md` — VERIFIED
- `grep -c "DEFER-50-01\|DEFER-50-02\|DEFER-50-03\|DEFER-50-04\|DEFER-50-05" deferred-items.md` == 5 — VERIFIED
- `grep -c "yookassa_call_failed" deferred-items.md` ≥ 1 — VERIFIED
- `grep -c "test_post_commit_enqueue_body_is_only_log_info" deferred-items.md` == 1 — VERIFIED (DEFER-50-04 references it explicitly)
- `pytest tests/integration/test_route_introspection.py::test_excluded_paths_set_is_locked test_gate_prefixes_match_factory_names` PASSES — VERIFIED (2/2)

---

*Phase: 50-webhook-fsm-fiscal-foundation*
*Completed: 2026-05-22*
