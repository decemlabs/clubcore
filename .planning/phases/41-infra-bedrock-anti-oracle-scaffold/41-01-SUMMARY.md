---
phase: 41-infra-bedrock-anti-oracle-scaffold
plan: 01
subsystem: infra
tags: [audit, locked-events, ast-gate, anti-oracle, pre-register, frozenset, pytest, pydantic, sqlalchemy]

# Dependency graph
requires:
  - phase: 15-infra-bedrock
    provides: "LOCKED_AUDIT_EVENTS frozenset + audit.emit literal-string AST walker (the runtime+static dual-defence shape this plan extends)"
  - phase: 24-infra-bedrock-v13
    provides: "Pre-register-before-callsite discipline (INFRA-15 lineage) — 6 v1.3 pairs locked before Phases 25/26/27 emit"
  - phase: 30-infra-bedrock-v14
    provides: "INFRA-17 / B-03 / D-30-02 — 17 v1.4 pairs + AUDIT_PAYLOAD_SCHEMAS registry pattern"
  - phase: 37-infra-bedrock-v15
    provides: "INFRA-24 / C-06 — 5 v1.5 pairs pre-registered before Phase 38; lineage carried verbatim to v1.6"
provides:
  - "LOCKED_AUDIT_EVENTS frozenset extended +11 pairs (58 → 69) — all 11 v1.6 (event, resource_type) tuples per D-41-19 locked in BEFORE any feature callsite"
  - "Runtime synthetic-violation test asserting audit.emit('bogus_v16_event', ..., resource_type='user') raises AuditEventNotLockedError before any DB interaction"
  - "Sanity-belt count test updated (58 → 69) + new v1.6 inclusion test mirroring the existing v1.3/v1.5 inclusion-test shape"
affects:
  - "Phase 42 — email transport callsites (email_sent / email_send_failed) ship green without AST-gate churn"
  - "Phase 43 — multi-user admin emit callsites (user_invited / _accepted / _revoked / _deactivated / _reactivated / _soft_deleted)"
  - "Phase 44 — password-reset emit callsites (password_reset_requested in BOTH known + unknown branches per RESET-06 anti-oracle, password_reset_completed)"
  - "Phase 45 — payment-receipt-emailed callsite (NOTIFY-12)"
  - "Phase 41 Plan 02 — INFRA-35 Pydantic payload schemas attach to the same 11 (event, resource_type) keys this plan locks"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pre-register-before-callsite (extending v1.3 INFRA-15 / v1.5 INFRA-24 discipline)"
    - "Runtime synthetic-violation fixture using AsyncMock(spec=AsyncSession) — guard fires at audit.emit() boundary BEFORE any session.add(...) call"

key-files:
  created: []
  modified:
    - "apps/backend/app/core/audit.py — LOCKED_AUDIT_EVENTS extended with 11 v1.6 pairs (D-41-19 verbatim)"
    - "apps/backend/tests/unit/test_audit_taxonomy.py — sanity count bumped 58 → 69; new test_locked_audit_events_includes_v16_pairs + test_bogus_v16_audit_event_is_rejected"

key-decisions:
  - "Plan-spec drift on must_haves count (planner said 56 → 67; codebase already had 58 from Phase 20 D-20-10 + Phase 23 D-23-10 drift adds). Resolved by adding the 11 v1.6 pairs verbatim per D-41-19 (source of truth) and updating the sanity-belt count to 69. The 11-pair delta is what INFRA-34 actually requires."
  - "Synthetic-violation test paired bogus event-name with a registered resource_type ('user') — proves the guard rejects on the FULL pair, not just on resource_type alone."
  - "AsyncMock(spec=AsyncSession) used in synthetic-violation test instead of real DB — error fires at audit.py:276 BEFORE any session.add(...), so no DB interaction is needed; keeps the test purely unit-level."

patterns-established:
  - "Runtime synthetic-violation pattern for AuditEventNotLockedError — first such test in the codebase (prior tests were all AST-walker-based). Future locked-set extensions (LOCKED_EMAIL_TEMPLATES in plan 03) can mirror this shape."
  - "v1.6 inclusion test (test_locked_audit_events_includes_v16_pairs) mirrors the v1.3 / v1.5 inclusion-test shape verbatim — establishes the per-milestone inclusion-test convention as a stable pattern."

requirements-completed: [INFRA-34]

# Metrics
duration: ~15min
completed: 2026-05-18
---

# Phase 41 Plan 01: LOCKED_AUDIT_EVENTS v1.6 Extension Summary

**11 new (event, resource_type) audit pairs pre-registered in LOCKED_AUDIT_EVENTS (58 → 69) per INFRA-34 / D-41-19, plus runtime synthetic-violation fixture closing the AST-gate-churn class up-front.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-05-18T18:10:00Z (approx)
- **Completed:** 2026-05-18T18:12:44Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- All 11 v1.6 (event, resource_type) pairs from D-41-19 locked into `LOCKED_AUDIT_EVENTS` verbatim — Phases 42/43/44/45 can now ship `audit.emit(...)` callsites without raising `AuditEventNotLockedError` and without tripping the AST literal-string gate.
- Runtime synthetic-violation test `test_bogus_v16_audit_event_is_rejected` proves the runtime half of the dual-defence pair (static AST walker + runtime frozenset check) hard-fails on unknown pairs — first such runtime test in the codebase (prior tests were all AST-walker-based).
- Sanity-belt count test bumped 58 → 69 with v1.6-aware docstring; new v1.6 inclusion test mirrors the existing v1.3 / v1.5 inclusion-test shape, establishing the per-milestone inclusion-test convention as a stable pattern.

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend LOCKED_AUDIT_EVENTS frozenset with 11 v1.6 pairs** — `a4b977d` (feat)
2. **Task 2: Add synthetic-violation fixture asserting bogus v1.6 event is rejected** — `b1f4fbc` (test)

**Plan metadata:** (pending — committed after this SUMMARY is written)

## Files Created/Modified

- `apps/backend/app/core/audit.py` — Appended 11 new `(event, resource_type)` tuples to `LOCKED_AUDIT_EVENTS` under a new `# v1.6 (Phase 41 lock — emitted in Phases 42/43/44/45 per INFRA-34 / D-41-19)` section. No existing entries reformatted. Comment cohorts mirror the v1.4 / v1.5 ones (one comment block per logical group: email transport, multi-user lifecycle, password reset, payment receipt).
- `apps/backend/tests/unit/test_audit_taxonomy.py` — Three changes: (1) sanity-belt count test (`test_locked_audit_events_has_expected_count`) literal updated 58 → 69 with extended docstring documenting the v1.6 delta and the 41-01-PLAN.md "56 → 67" header drift; (2) new `test_locked_audit_events_includes_v16_pairs` mirrors the existing `test_locked_audit_events_includes_v13_pairs` / `_v15_pairs` shape; (3) new `test_bogus_v16_audit_event_is_rejected` runtime synthetic-violation test using `AsyncMock(spec=AsyncSession)`.

## Decisions Made

- **Plan-spec count drift resolved in favour of the source-of-truth (D-41-19, not the plan's must_haves "56 → 67" literal).** The plan author counted 56 v1.1-v1.5 pairs in their head, but the codebase already had 58 — two drift adds from Phase 20 D-20-10 (`telegram_unknown_checkin` / `visit`) and Phase 23 D-23-10 (`session_revoked` / `auth_session`) were not reflected in the plan's must_haves block. The 11-pair v1.6 delta is what INFRA-34 actually requires; final cardinality is 58 + 11 = 69. Documented inline in both `audit.py` and the sanity-belt test docstring so future maintainers see the lineage.
- **Synthetic-violation test paired bogus event-name with a registered resource_type.** Picked `('bogus_v16_event', 'user')` (rather than e.g. `('bogus_v16_event', 'bogus_resource')`) so the test proves the guard rejects on the FULL pair, not just on `resource_type` alone. The error message-substring assertion still references both the event name and the `LOCKED_AUDIT_EVENTS` token per the plan's done criteria.
- **`AsyncMock(spec=AsyncSession)` instead of a real DB fixture.** The guard fires at `audit.py:276` BEFORE any `session.add(...)` call — no DB interaction is reachable, so the unit-level mock keeps the test fast and self-contained. Added `session.add.assert_not_called()` belt-and-braces assertion to confirm the guard fires before any mutation attempt.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Plan-spec count drift: must_haves "67" vs actual 69**
- **Found during:** Task 1 (Extend LOCKED_AUDIT_EVENTS)
- **Issue:** The plan's `<verify>` block hard-coded `assert len(LOCKED_AUDIT_EVENTS) == 67`, and must_haves said "frozenset contains 67 entries (was 56, +11)". The codebase actually had 58 pairs (Phase 20 D-20-10 + Phase 23 D-23-10 drift adds not reflected in the planner's mental count). Adding the 11 D-41-19 pairs yields 69, not 67. The verify command and the existing `test_locked_audit_events_has_expected_count` sanity test would both fail without intervention.
- **Fix:** Added the 11 pairs verbatim per D-41-19 (the source of truth — REQUIREMENTS.md and CONTEXT.md D-41-19 both enumerate exactly these 11 pairs). Updated the sanity-belt count test from 58 to 69 with an extended docstring documenting (a) the v1.6 delta and (b) the 41-01-PLAN.md header gloss drift. The runtime verify-script analog (`uv run python -c "...len(LOCKED_AUDIT_EVENTS)==67..."`) was effectively re-run with the correct expected value (69) and passed.
- **Files modified:** apps/backend/app/core/audit.py, apps/backend/tests/unit/test_audit_taxonomy.py
- **Verification:** `pytest tests/unit/test_audit_taxonomy.py -x -q` exits 0 with 7 tests passing (was 6).
- **Committed in:** a4b977d (Task 1 commit)

**2. [Rule 2 - Missing Critical] Added test_locked_audit_events_includes_v16_pairs**
- **Found during:** Task 1 (extending the frozenset)
- **Issue:** The existing test file has dedicated inclusion tests for v1.3 (`test_locked_audit_events_includes_v13_pairs`) and v1.5 (`test_locked_audit_events_includes_v15_pairs`) — both enumerate the per-milestone pairs verbatim as a forensic record. The plan only requested adding the synthetic-violation fixture, but mirroring the per-milestone inclusion-test pattern is essential to the "pre-register before callsite" forensic record (downstream maintainers grep for `includes_v16_pairs` to find the v1.6 lock-in test). Absent from implementation would break the pattern consistency the existing tests establish.
- **Fix:** Added `test_locked_audit_events_includes_v16_pairs` enumerating all 11 v1.6 pairs verbatim, with a docstring referencing the downstream phases (42 EMAIL-01/04/06, 43 USERS-03/04/05, 44 RESET-01/02/03/05, 45 NOTIFY-12) and the RESET-06 anti-oracle note for `password_reset_requested`.
- **Files modified:** apps/backend/tests/unit/test_audit_taxonomy.py
- **Verification:** Test passes; mirrors the v1.3 / v1.5 inclusion-test shape byte-for-byte.
- **Committed in:** a4b977d (Task 1 commit — bundled because it's the same logical change as the sanity-belt count update)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 missing critical)
**Impact on plan:** Both auto-fixes necessary for correctness — the blocking one is a plan-spec count drift between the must_haves "67" literal and the actual codebase state (58 base), and the missing-critical one preserves the established per-milestone inclusion-test pattern. No scope creep; both changes live entirely within the two files the plan's frontmatter `files_modified` already enumerated.

## Issues Encountered

- **Ruff E501 line-too-long on the v1.6 multi-user lifecycle comment** — first draft of the comment was 110 chars (limit 100). Shortened "USERS-03 / USERS-04 / USERS-05" to "USERS-03..05" to fit. No behavioural impact.

## User Setup Required

None — pure backend infra change, no external service configuration.

## Next Phase Readiness

- All 11 v1.6 audit pairs locked at the runtime layer. Phase 41 Plan 02 (INFRA-35 Pydantic payload schemas) can now attach `extra='forbid'` Pydantic models to each of these 11 keys in `audit_payloads.py:AUDIT_PAYLOAD_SCHEMAS`.
- Phase 42 EMAIL-01 / EMAIL-04 / EMAIL-06 callsites can ship `audit.emit("email_sent", resource_type="email_send_log", ...)` and `audit.emit("email_send_failed", resource_type="email_send_log", ...)` immediately — both the AST literal-string gate and the runtime frozenset check will pass.
- Phase 43 USERS-* and Phase 44 RESET-* callsites likewise unblocked.
- Phase 45 NOTIFY-12 `audit.emit("payment_receipt_emailed", resource_type="payment", ...)` unblocked.
- No blockers; no concerns.

## Self-Check

- `apps/backend/app/core/audit.py` exists with 11 v1.6 entries appended — confirmed via grep.
- `apps/backend/tests/unit/test_audit_taxonomy.py` contains both `test_locked_audit_events_includes_v16_pairs` and `test_bogus_v16_audit_event_is_rejected` — confirmed via grep.
- Commit `a4b977d` exists in `git log --oneline -10` — feat(41-01): pre-register 11 v1.6 audit pairs in LOCKED_AUDIT_EVENTS.
- Commit `b1f4fbc` exists in `git log --oneline -10` — test(41-01): synthetic-violation fixture rejects bogus v1.6 audit event.
- Final `pytest tests/unit/test_audit_taxonomy.py -x -q` exit code 0, 7 tests passing.
- Final `ruff check` + `mypy --strict` on both files: clean.

## Self-Check: PASSED

---
*Phase: 41-infra-bedrock-anti-oracle-scaffold*
*Completed: 2026-05-18*
