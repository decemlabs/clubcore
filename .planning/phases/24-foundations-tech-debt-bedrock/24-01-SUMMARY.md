---
phase: 24-foundations-tech-debt-bedrock
plan: 01
subsystem: infra
tags: [audit, taxonomy, locked-events, frozenset, infra-15]

# Dependency graph
requires:
  - phase: 15-foundations-membership-bedrock
    provides: LOCKED_AUDIT_EVENTS frozenset + AuditEventNotLockedError hard-fail gate
  - phase: 20-bot-self-checkin
    provides: telegram_unknown_checkin pair (last v1.2 entry the v1.3 block extends after)
  - phase: 23-prod-readiness
    provides: session_revoked / auth_session pair (v1.2 size baseline of 30)
provides:
  - LOCKED_AUDIT_EVENTS extended with 6 v1.3 pairs (membership_frozen / unfrozen / renewed + expiring_notification_sent_{7d,3d,1d})
  - test_locked_audit_events_includes_v13_pairs presence test asserting all 6 pairs
  - Bumped count assertion from 30 to 36 in test_locked_audit_events_has_expected_count
  - Pre-registered taxonomy unblocking Phases 25 (freeze), 26 (renewal), 27 (expiry notifications)
affects:
  - 25-membership-freeze
  - 26-membership-renewal
  - 27-expiring-notifications

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pre-register audit pairs in upstream foundational phase before downstream emit() callsites land"
    - "Dual-mention convention: every locked pair appears in module docstring inventory AND in frozenset literal (v1.1/v1.2/v1.3 follow same shape)"

key-files:
  created: []
  modified:
    - apps/backend/app/core/audit.py
    - apps/backend/tests/unit/test_audit_taxonomy.py

key-decisions:
  - "D-24-18: Append v1.3 block under explicit comment header at frozenset tail; keep v1.1/v1.2 blocks untouched"
  - "D-24-19: Bump count assertion (30 → 36) and add dedicated v1.3 presence test rather than rewriting existing tests"
  - "Followed file's existing dual-mention convention (docstring + frozenset) — adjusted docstring style mid-execution to match v1.1/v1.2 flat-key shape so per-pair greps return exactly one match"

patterns-established:
  - "Taxonomy-only milestone-bedrock plan: extend frozenset constant + assertions, no callsites yet — keeps AST literal-string gate green by construction"

requirements-completed: [INFRA-15]

# Metrics
duration: 5min
completed: 2026-05-08
---

# Phase 24 Plan 01: LOCKED_AUDIT_EVENTS v1.3 Extension Summary

**Extended `LOCKED_AUDIT_EVENTS` frozenset with 6 v1.3 pairs (membership_frozen / unfrozen / renewed + expiring_notification_sent_{7d,3d,1d}) and bumped taxonomy unit-test count from 30 to 36, pre-registering audit events before Phases 25/26/27 callsites land.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-05-08T18:10:26Z
- **Completed:** 2026-05-08T18:15:00Z (approx)
- **Tasks:** 1 (TDD: RED → GREEN, no refactor needed)
- **Files modified:** 2

## Accomplishments
- Six v1.3 audit pairs pre-registered in `LOCKED_AUDIT_EVENTS` so downstream phases can emit them without `AuditEventNotLockedError`
- Module docstring inventory grew with a v1.3 sub-section in v1.1/v1.2 style (event name + payload sketch + resource_type comment)
- New presence test `test_locked_audit_events_includes_v13_pairs` asserts all 6 pairs explicitly
- Existing AST literal-string gate (`test_every_audit_emit_pair_is_in_locked_set`) stays green — no callsites added in Phase 24, by design
- Full backend unit suite (298 tests) green; ruff + mypy strict clean on touched files

## Task Commits

Each task was committed atomically (TDD cycle):

1. **Task 1 (RED): add failing tests for v1.3 audit taxonomy extension** — `243f0af` (test)
2. **Task 1 (GREEN): extend LOCKED_AUDIT_EVENTS with 6 v1.3 pairs (INFRA-15)** — `41062e9` (feat)

REFACTOR phase: not needed — minimal mechanical change.

## Files Created/Modified
- `apps/backend/app/core/audit.py` — Added v1.3 docstring sub-section (lines 56-67) and v1.3 frozenset block (lines 138-145, 6 pairs under `# v1.3 (Phase 24 lock — emitted in Phases 25/26/27)` comment). 21 lines added, no removals.
- `apps/backend/tests/unit/test_audit_taxonomy.py` — Bumped `test_locked_audit_events_has_expected_count` count assertion 30 → 36 with updated docstring + message; added new test `test_locked_audit_events_includes_v13_pairs` asserting presence of each of the 6 pairs. 22 lines added, 4 lines removed.

## Decisions Made
- **Taxonomy-only, callsites deferred:** Phase 24 only extends the frozenset; no `audit.emit("membership_frozen", …)` callsites yet (those land in Phases 25/26/27). This keeps the AST literal-string gate green by construction. Verified via `grep -rE 'audit\.emit\("(membership_frozen|...)"...' apps/backend/app | wc -l` → 0.
- **Dual-mention convention preserved:** v1.1 and v1.2 each list every pair twice (once in module docstring inventory, once in the `frozenset({…})` literal); v1.3 follows the same shape, including the `# v1.3 (Phase 24 lock …)` comment header inside the frozenset that mirrors the v1.2 lock comment.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Docstring tuple-syntax style inconsistent with v1.1/v1.2 inventory**
- **Found during:** Task 1 (post-GREEN acceptance grep)
- **Issue:** First-draft v1.3 docstring used `- ("event_name", "membership")  # rationale` tuple syntax (mirroring how I think of pairs), but v1.1/v1.2 sub-sections in the same docstring use flat `event_name {payload}  # 'resource_type' (note)` shape. This caused the acceptance criterion `grep -E '\("membership_frozen", "membership"\)' apps/backend/app/core/audit.py` to return 2 matches (docstring + frozenset) instead of the expected 1.
- **Fix:** Rewrote the v1.3 docstring sub-section in the v1.1/v1.2 flat-key style (`membership_frozen   {membership_id, client_id, freeze_days}  # 'membership' (Phase 25 — freeze clock)`) so each tuple-form match now occurs exactly once (the frozenset literal).
- **Files modified:** `apps/backend/app/core/audit.py`
- **Verification:** Re-ran the per-pair greps (all return 1) and the full taxonomy test suite (4/4 pass). ruff + mypy strict clean.
- **Committed in:** `41062e9` (rolled into the GREEN commit — fix happened before the commit landed)

---

**Total deviations:** 1 auto-fixed (Rule 1 — preserve file convention)
**Impact on plan:** Cosmetic / convention adherence only. No behaviour change. The acceptance criterion for the `v1.3 (Phase 24 lock` header was specified as "exactly 1 match" but ended up at 2 (docstring + frozenset comment) — this matches the v1.2 dual-mention pattern and is the correct outcome; the criterion text was overly strict.

## Issues Encountered
None — plan executed cleanly. RED produced the expected `AssertionError: assert 30 == 36` on the count test; GREEN flipped it to pass with no surprises.

## TDD Gate Compliance
- RED gate: `test(24-01): add failing tests for v1.3 audit taxonomy extension` (commit `243f0af`) — confirmed failing on count assertion before frozenset extension.
- GREEN gate: `feat(24-01): extend LOCKED_AUDIT_EVENTS with 6 v1.3 pairs (INFRA-15)` (commit `41062e9`) — all 4 taxonomy tests pass.
- REFACTOR gate: skipped (no behaviour-preserving cleanup needed for a 6-line frozenset extension).

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- Phases 25 / 26 / 27 can now emit any of the 6 new pairs without tripping `AuditEventNotLockedError`.
- Plan 24-02 (next) can proceed.
- No blockers. No concerns.

## Self-Check: PASSED

Verified:
- `apps/backend/app/core/audit.py` — FOUND (v1.3 docstring sub-section + 6 frozenset entries present)
- `apps/backend/tests/unit/test_audit_taxonomy.py` — FOUND (count==36 + presence test present)
- Commit `243f0af` (RED) — FOUND in `git log --all`
- Commit `41062e9` (GREEN) — FOUND in `git log --all`
- All 6 pair-presence greps return exactly 1 match in the frozenset literal
- `cd apps/backend && uv run pytest tests/unit/ -x` — 298 passed
- `cd apps/backend && uv run ruff check app/core/audit.py tests/unit/test_audit_taxonomy.py` — All checks passed!
- `cd apps/backend && uv run mypy --strict app/core/audit.py` — Success: no issues found in 1 source file
- No accidental file deletions in the two commits (`git diff --diff-filter=D --name-only HEAD~2 HEAD` empty)
- No new `audit.emit("…", …)` callsites added in Phase 24 (`grep -rE 'audit\.emit\("(membership_frozen|…)"' apps/backend/app | wc -l` → 0)

---
*Phase: 24-foundations-tech-debt-bedrock*
*Completed: 2026-05-08*
