---
phase: 42-email-transport-layer-email-otp-fallback
plan: 11
subsystem: testing
tags:
  - tests
  - anti-oracle
  - reg-29-03
  - reg-29-04
  - ast-gate
  - auth
  - email
  - otp

dependency-graph:
  requires:
    - 42-01 (EmailSendLog ORM + email_send_log table — eager-import target)
    - 42-08 (enqueue_email_dispatch + dispatch_email task — symbol references)
    - 42-09 (REG-29-03 double-wire of register_email_dispatcher + EMAIL_OTP_LOGIN
       real callsite in auth.service.request_otp_email + /auth/otp/request
       unified route with anti-oracle floor — every gate in this plan exercises
       artifacts plan 42-09 shipped)
    - 42-10 (email webhook — out of scope but co-resident in /api/v1/_internal)
    - 41 INFRA-36 (LOCKED_EMAIL_TEMPLATES + Phase 41 walker — extended here with
       the first positive-fixture real-callsite assertion)
  provides:
    - "AUTH-EM-04 anti-oracle gate (test_otp_email_anti_oracle.py) — GREEN at
       land-time, no xfail-strict marker, asserts byte-identical 202 bodies +
       100ms bounded-equal timing across the 3 email-channel cases plus the
       Telegram-default backwards-compat case (D-42-24)"
    - "REG-29-03 double-wire CI gate
       (test_worker_on_startup_double_wires_email_dispatcher) — AST-walk parity
       between app/main.py and app/workers/__init__.py for
       register_email_dispatcher (D-42-26)"
    - "REG-29-03 slot-fills extension (test_create_app_registers_all_protocol_slots)
       — deps._email_dispatcher is not None after create_app()"
    - "REG-29-04 email_send_log eager-import CI gate
       (test_email_send_log_eager_imported) — Base.metadata.tables visibility
       after import app.workers (D-42-33)"
    - "INFRA-36 positive-fixture real-callsite assertion
       (test_email_otp_login_real_callsite_present) — pins the literal
       \"EMAIL_OTP_LOGIN\" template_id ast.Constant(str) in
       app/modules/auth/service.py (D-42-27)"
  affects:
    - "Phase 46 VER-11 milestone-gate re-runs the same 4 test files"
    - "Phase 44 RESET-01 will lift the xfail-strict marker on
       test_password_reset_no_oracle.py — the AUTH-EM-04 test in this plan is
       the GREEN-at-land-time precedent the RESET test inherits"

tech-stack:
  added: []
  patterns:
    - "Anti-oracle CI gate — bytes-equality + bounded-equal timing within 100ms
       across N branches that should be observationally indistinguishable. Test
       seeds the N branches per-test via SAVEPOINT isolation, posts to the
       endpoint inside a tight loop, captures (status, body bytes,
       time.perf_counter delta) per branch, asserts set-cardinality on
       status/bodies and a hard max-min ceiling on timings."
    - "AST-walk structural parity for compose roots — when two sibling-process
       composition roots (FastAPI + ARQ worker) must register the same slot,
       a runtime test is infeasible inside one process. The structural check
       ast.parse()s both files and asserts the register_* call name appears in
       both call-name sets. Byte-equality of the registered callable is
       implicit via shared imports."
    - "Positive-fixture pin against const-extraction refactors — the AST gate
       walks for ast.Constant(str) only; a future refactor that hoists the
       template_id literal into a module-level constant would silently bypass
       the gate. A dedicated test that asserts the literal exists as an
       ast.Constant(str) inside a specific production module catches the
       refactor at CI time. Walker logic mirrored locally (not delegated to
       the production walker) so the gate cannot be weakened by changes to
       the production walker."
    - "Eager-import contract per ORM table — for every new ORM table that a
       worker process queries, app/workers/__init__.py needs a top-level
       import of the model module, and tests/unit/test_workers_eager_import.py
       needs a dedicated assertion that the table appears in
       Base.metadata.tables after import app.workers."

key-files:
  created:
    - apps/backend/tests/integration/auth/test_otp_email_anti_oracle.py
  modified:
    - apps/backend/tests/integration/test_app_wiring.py
    - apps/backend/tests/unit/test_workers_eager_import.py
    - apps/backend/tests/unit/test_locked_email_templates_ast.py
    - apps/backend/app/modules/auth/service.py  (Rule 1 fix — UUID→str at audit boundary)

key-decisions:
  - "D-42-11-01 — Anti-oracle test treats case B (Telegram-default path) as a
     separate status-only assertion. The Telegram path emits different log
     events and uses a different OTP-code mint flow; expecting byte-equal
     response bodies across channels is intentionally NOT a contract per
     D-42-22. The 3-way body-parity + timing-parity assertion is scoped to
     cases A/C/D (all under channel='email')."
  - "D-42-11-02 — REG-29-03 worker-side double-wire is asserted structurally
     (AST-walk), NOT by calling WorkerSettings.on_startup at test time. The
     on_startup callable lives in a sibling process; invoking it here would
     instantiate the worker side-effect tree (Redis pool, EmailClient,
     domains probe). Structural parity is the right tool for cross-process
     wiring invariants."
  - "D-42-11-03 — Positive-fixture walker logic is mirrored locally rather
     than delegated to _iter_dispatcher_calls from the production walker. A
     refactor of the production walker (e.g., narrowing the scope to
     get_email_dispatcher only) cannot silently weaken the positive fixture."
  - "D-42-11-04 — Rule 1 inline fix: app/modules/auth/service.py was passing
     a raw UUID into audit.emit() payload, which writes JSONB with no
     UUID-aware serializer. The audit_log INSERT failed with `Object of type
     UUID is not JSON serializable`. Fixed at the callsite (UUID → str)
     rather than the audit module: the dispatcher already follows this
     convention at the ARQ enqueue boundary (UUID → str at every JSON
     boundary). Fixing the callsite is consistent + minimally invasive."

patterns-established:
  - "Pattern: GREEN-at-land-time anti-oracle test — the same fixture-seeding
     + perf_counter pattern as Phase 41's RED xfail-strict
     test_password_reset_no_oracle.py, but without the xfail marker because
     the endpoint already ships in the preceding wave."
  - "Pattern: positive-fixture pin alongside negative-fixture walker — a
     production AST walker is paired with both a real-callsite positive
     fixture (to assert the literal still exists in the named module) and
     synthetic negative fixtures (to assert the walker rejects bogus
     callsites)."

requirements-completed:
  - AUTH-EM-04
  - EMAIL-03
  - EMAIL-04

# Metrics
duration: 26min
completed: 2026-05-19
---

# Phase 42 Plan 11: Phase 42 Invariant pytest Gates Summary

**Four CI gates lock the Phase 42 invariants — anti-oracle parity, REG-29-03 double-wire, REG-29-04 eager-import, and INFRA-36 real-callsite — every test goes GREEN at land-time with zero xfail markers.**

## Performance

- **Duration:** ~26 min
- **Started:** 2026-05-19T08:32:00Z (approx)
- **Completed:** 2026-05-19T08:58:00Z
- **Tasks:** 4
- **Files modified:** 5 (4 tests + 1 production Rule-1 fix)

## Anti-Oracle Timing Measurements

Empirical worst-case across 5 trials of cases A/C/D from a clean dev box (run
against the same composition-root path the CI gate uses):

| trial | A (verified+no-tg) ms | C (unverified) ms | D (nonexistent) ms | max−min ms |
|-------|----------------------|--------------------|---------------------|------------|
| 0     | 217.8                | 203.3              | 202.3               | **15.4**   |
| 1     | 203.3                | 202.1              | 202.2               |  1.1       |
| 2     | 202.2                | 202.6              | 202.4               |  0.4       |
| 3     | 203.2                | 202.5              | 202.3               |  0.9       |
| 4     | 202.3                | 202.7              | 202.8               |  0.5       |

Worst-case observed: **15.4ms** (cold-cache trial 0) — well under the 100ms
ceiling. Floor of ~202ms confirms the D-42-22 `_constant_time_floor` with
`_EMAIL_OTP_FLOOR_MS=200ms` is engaging across all 3 branches.

## xfail Marker Audit (D-42-24 Invariant)

Confirmed via `grep -rn "xfail" tests/integration/auth/test_otp_email_anti_oracle.py
tests/integration/test_app_wiring.py tests/unit/test_workers_eager_import.py
tests/unit/test_locked_email_templates_ast.py`: zero `xfail` markers on the four
files in this plan. AUTH-EM-04 and the REG-29-03 / REG-29-04 / INFRA-36 gates
go GREEN at land-time per D-42-24 — the test is the contract, not a placeholder.

## Accomplishments

- Anti-oracle CI gate (AUTH-EM-04) green at land-time across all 4 D-42-24
  cases — byte-identical 202 bodies + 100ms-bounded timing for the 3
  email-channel branches; case B verified to return 202 via the Telegram
  default-channel path.
- REG-29-03 double-wire enforced as a structural AST gate, immune to runtime
  re-arrangement of WorkerSettings.on_startup.
- REG-29-04 eager-import extended to email_send_log — silent regressions on
  the ORM table → worker import dependency are now noisy at CI time.
- INFRA-36 positive-fixture pin against const-extraction refactors of the
  EMAIL_OTP_LOGIN literal.
- Caught + fixed a JSONB-serialization bug in plan 42-09's
  `request_otp_email` (Rule 1) — without the inline fix, every email-channel
  OTP request would have crashed at the audit INSERT.

## Task Commits

1. **Task 1: AUTH-EM-04 anti-oracle integration test (4 cases)** — `db380a9` (feat) — includes Rule 1 inline bug fix in `app/modules/auth/service.py`
2. **Task 2: Extend test_app_wiring.py with EmailDispatcher double-wire** — `cbd66c1` (test)
3. **Task 3: Extend test_workers_eager_import.py with email_send_log assertion** — `4a661f9` (test)
4. **Task 4: Positive-fixture AST gate for EMAIL_OTP_LOGIN real callsite** — `907b22b` (test)

## Files Created / Modified

- `apps/backend/tests/integration/auth/test_otp_email_anti_oracle.py` **(NEW)** — 4-case anti-oracle gate
- `apps/backend/tests/integration/test_app_wiring.py` — `_WORKERS_PY` constant, EmailDispatcher slot-fills assertion, AST parity test
- `apps/backend/tests/unit/test_workers_eager_import.py` — `email_send_log` eager-import assertion
- `apps/backend/tests/unit/test_locked_email_templates_ast.py` — positive-fixture real-callsite assertion
- `apps/backend/app/modules/auth/service.py` — Rule 1 fix: `str(audit_correlation_id)` at the `audit.emit` boundary

## Decisions Made

See `key-decisions` in frontmatter. Two are worth re-stating in body text:

- **Case B is NOT in the body-parity bucket.** Including the Telegram path
  in the body-equality assertion would have forced the two channels to
  produce byte-equal envelopes — which contradicts D-42-22's design (the
  Telegram path needs a different audit emission and different logging
  shape). Status-202 parity is the right contract for the unified
  endpoint shape; body-equality is the right contract for the
  cross-branch leak within a channel.
- **Structural AST parity instead of runtime double-invocation.** The
  worker side's on_startup cannot be invoked from a FastAPI-process
  integration test without instantiating side effects that the test
  deliberately avoids. AST parity is byte-equal-symbol-equivalent because
  both files import the same `enqueue_email_dispatch` symbol from
  `app.integrations.email.dispatcher`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed UUID→JSONB serialization at audit boundary in request_otp_email**
- **Found during:** Task 1 (AUTH-EM-04 anti-oracle test execution)
- **Issue:** Plan 42-09's `service.request_otp_email` passed a raw `UUID`
  object as the `audit_correlation_id` payload kwarg to `audit.emit`.
  `AuditLog.payload` is a `JSONB` column with no UUID-aware serializer, so
  the INSERT failed with `TypeError: Object of type UUID is not JSON
  serializable`. Every email-channel OTP request would have crashed at the
  audit INSERT — this bug was not surfaced by plan 42-09 because no
  integration test exercised the real audit path against Postgres before
  this plan.
- **Fix:** Stringified the UUID at the callsite (`audit_correlation_id=str(audit_correlation_id)`).
  Same convention is already in `app.integrations.email.dispatcher.enqueue_email_dispatch`
  at the ARQ-enqueue boundary (line 197 in that file). Fixing at the callsite
  rather than inside `audit.emit` is consistent with the project convention
  ("UUID → str at every JSON boundary") and minimally invasive.
- **Files modified:** `apps/backend/app/modules/auth/service.py`
- **Verification:** AUTH-EM-04 test now passes; full auth + unit suite (751 tests)
  passes with no regressions (1 pre-existing xfailed test from Phase 41 stays xfailed).
- **Committed in:** `db380a9` (Task 1 commit body documents the Rule 1 fix explicitly).

---

**Total deviations:** 1 auto-fixed (1 Rule 1 bug).
**Impact on plan:** No scope creep. The bug was directly blocking Task 1's GREEN
acceptance criterion — fix is correctness-critical and tightly scoped to the
plan-42-09 callsite that the anti-oracle test exercises. The fix is the
minimal change to make the gate green; it does not introduce any new
behaviour and does not change any audit payload shape (the on-wire JSONB
value is what it should always have been — a JSON string).

## Issues Encountered

- mypy --strict reports `app.modules.auth.models` not explicitly exporting
  `User` for the new test, matching a pre-existing pattern in
  `test_password_reset_no_oracle.py` and ~10 other auth integration tests.
  This is out of scope (Rule 4 architectural; would require either
  re-exporting via `__all__` in the auth shim or migrating every existing
  test to `app.core.models import User`). The new test follows the existing
  convention exactly.

## ROADMAP Success-Criteria Cross-Reference

Phase 42 ROADMAP success criteria → gating test:

| #   | Criterion (paraphrased)                                              | Gating test(s) in this plan                                                                                                                                |
|-----|----------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1   | `/auth/otp/request {channel:'email'}` end-to-end + audit + sandbox inbox | Out of scope here (lives in plan 42-09 + manual sandbox smoke); the anti-oracle gate exercises the audit half indirectly                                       |
| 2   | Anti-oracle response shape across verified-email / unverified-email   | **`tests/integration/auth/test_otp_email_anti_oracle.py::test_otp_email_anti_oracle`** — direct gate                                                       |
| 3   | EmailDispatcher double-wire + ARQ dispatch_email max_tries=2 timeout=20s | **`tests/integration/test_app_wiring.py::test_worker_on_startup_double_wires_email_dispatcher`** + slot-fills extension; ARQ kwargs verified in plan 42-09 |
| 4   | Circuit breaker opens after 5 5xx + short-circuits                    | Out of scope here (plan 42-08 unit + plan 42-09 integration); see `tests/unit/integrations/email/test_circuit_breaker.py`                                  |
| 5   | DNS runbook + EmailProviderSettings fail-fast + boot-time /domains probe | Out of scope (plans 42-02, 42-06, 42-07)                                                                                                                  |
| 6   | `/api/v1/_internal/email/webhook` HMAC-before-parse                   | Out of scope (plan 42-10); REG-29-04 eager-import here is a pre-condition for the webhook handler's join on `email_send_log`                              |

The 4 tests landed in this plan jointly gate ROADMAP criteria 2 + 3 (directly)
and act as pre-conditions for 6 (transitively via REG-29-04 eager-import).
**Phase 46 VER-11 will re-run all 4 tests at the milestone gate.**

## User Setup Required

None — pure CI-gate plan with one inline correctness fix.

## Next Phase Readiness

- All four CI gates GREEN — Phase 42 is fully testable end-to-end.
- The Rule 1 fix to `service.py` closes a real defect that would have crashed
  the first production email-OTP request. Downstream consumers of
  `audit_correlation_id` (e.g., Phase 45 NOTIFY-* event correlation) need to
  read it as a string from the JSONB payload — that contract is now pinned by
  the anti-oracle integration test's audit-INSERT step.
- Phase 43 (USERS) and Phase 44 (RESET) are unblocked. Phase 44's
  `test_password_reset_no_oracle.py` xfail removal follows the GREEN-at-land
  template established here.

## Self-Check: PASSED

- Files created/modified verified to exist via `[ -f ... ]`:
  - `apps/backend/tests/integration/auth/test_otp_email_anti_oracle.py` FOUND
  - `apps/backend/tests/integration/test_app_wiring.py` FOUND (modified)
  - `apps/backend/tests/unit/test_workers_eager_import.py` FOUND (modified)
  - `apps/backend/tests/unit/test_locked_email_templates_ast.py` FOUND (modified)
  - `apps/backend/app/modules/auth/service.py` FOUND (modified — Rule 1 fix)
- Commits verified via `git log --oneline`:
  - `db380a9` FOUND
  - `cbd66c1` FOUND
  - `4a661f9` FOUND
  - `907b22b` FOUND

---
*Phase: 42-email-transport-layer-email-otp-fallback*
*Completed: 2026-05-19*
