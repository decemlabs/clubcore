---
phase: 36-milestone-verification-backend-only
plan: 03
subsystem: verification-race-tests
tags: [verification, race-tests, pytest, audit-chain, backend-only]
wave: 2
dependency_graph:
  requires:
    - "36-01 (live stack up + seed script)"
  provides:
    - "race-test green evidence for VER-02"
    - "VERIFICATION-LOG.md skeleton (frontmatter + overrides + race_tests block)"
  affects:
    - .planning/milestones/v1.4-VERIFICATION-LOG.md
    - .planning/milestones/v1.4-verification-evidence/race_tests.txt
tech_stack:
  added: []
  patterns:
    - "single pytest invocation across 7 race/audit test files"
    - "stdout tail capture into VERIFICATION-LOG.md race_tests YAML block"
    - "5 logical test entries (REF-TEST-01/02, PTS-TEST-01, PAY-TEST-01, AUDIT-TEST-01)"
    - "SAVEPOINT outer-transaction conftest pattern → no live-stack data pollution"
    - "git stash A/B verification for pre-existing-vs-new failure classification"
key_files:
  created:
    - .planning/milestones/v1.4-VERIFICATION-LOG.md (skeleton — frontmatter + overrides + race_tests block)
    - .planning/milestones/v1.4-verification-evidence/race_tests.txt (1187 bytes, 20/20 pass)
  modified:
    - apps/backend/docker-compose.yml (REG-36-02 — redis port exposed for host-side pytest)
    - apps/backend/app/modules/pt_sessions/service.py (REG-36-03 — UUID stringify in audit payload)
    - apps/backend/tests/integration/pt_sessions/test_pt_session_record_race.py (REG-36-04 — identity-map expire_all)
requirements_covered:
  - VER-02
must_haves_met:
  - "REF-TEST-01 (concurrent membership refund) green"
  - "REF-TEST-02 (concurrent PT-package refund) green"
  - "PTS-TEST-01 (concurrent PT-session decrement) green"
  - "PAY-TEST-01 (concurrent sale double-submit with same Idempotency-Key) green"
  - "AUDIT-TEST-01 (every state-mutating service emits expected locked event) green"
inline_regressions:
  - id: REG-36-02
    commit: 99bbf4e
    summary: "docker-compose redis port not exposed → host-side pytest could not connect to localhost:6379. Mirrored the postgres pattern."
  - id: REG-36-03
    commit: bea5c42
    summary: "pt_sessions/service.py:267 raw UUID in audit JSONB → `TypeError: Object of type UUID is not JSON serializable`. Fix: `str(actor.id)`."
  - id: REG-36-04
    commit: 864977a
    summary: "Race test's post-race re-read returned identity-map-cached PtPackage with stale `sessions_remaining=1`. Fix: `db_session_real_commit.expire_all()` before re-read."
deferred:
  - id: DEFER-36-03-A
    summary: "7 pt_sessions cancel + record non-race tests fail with sqlalchemy.exc.MissingGreenlet (pre-existing async/sync mismatch, NOT caused by REG-36-02/03/04; A/B verified via git stash). Rolled forward to 36-04 for visibility in full pytest gate."
  - one_liner: "Race-test sweep 20/20 green; 3 inline regression fixes (REG-36-02/03/04); VERIFICATION-LOG.md bootstrapped with shape mirroring v1.3 canonical."
status: complete
commits:
  - hash: 99bbf4e
    message: "fix(36-03): REG-36-02 expose redis port for host-side pytest"
  - hash: bea5c42
    message: "fix(36-03): REG-36-03 stringify UUID in pt_session_recorded audit payload"
  - hash: 864977a
    message: "fix(36-03): REG-36-04 expire identity-map before post-race re-read"
  - hash: 10eb78d
    message: "docs(36-03): capture race-test sweep evidence + bootstrap VERIFICATION-LOG.md (VER-02)"
---

# Phase 36 Plan 03 — Race-test sweep evidence (VER-02)

## One-liner

20/20 race + audit tests green across 7 files; 3 inline regressions fixed during execution (redis port, UUID-in-audit-JSON, identity-map cache); `.planning/milestones/v1.4-VERIFICATION-LOG.md` bootstrapped with frontmatter + `race_tests:` block; `.planning/milestones/v1.4-verification-evidence/race_tests.txt` (1187 bytes) committed as raw evidence.

## What got built

Plan 36-03 executed the D-36-08 verbatim race-test sweep command and captured evidence into the new milestone-level VERIFICATION-LOG.md. The plan was infrastructure-light — no new test files — and execution-heavy: run pytest against the 7-file race+audit set, classify failures, fix what the v1.4 milestone owned (3 REGs), defer what was pre-existing (DEFER-36-03-A: 7 pre-existing MissingGreenlet failures).

The 5 logical test IDs (REF-TEST-01/02, PTS-TEST-01, PAY-TEST-01, AUDIT-TEST-01) map across 7 physical test files; the YAML block makes the mapping explicit so a future operator can re-run any single ID.

## Coverage map

| Logical ID | File(s) | Pass count |
|------------|---------|------------|
| REF-TEST-01 | tests/integration/payments/test_payments_refund_race.py | 1 |
| REF-TEST-02 | tests/integration/pt_packages/test_pt_package_refund_race.py | 1 |
| PTS-TEST-01 | tests/integration/pt_sessions/test_pt_session_record_race.py | 1 |
| PAY-TEST-01 | tests/integration/payments/test_idempotency.py | 5 |
| AUDIT-TEST-01 | tests/integration/payments/test_payments_audit_chain.py + test_payments_refund_audit_chain.py + tests/integration/memberships/test_audit_writes.py | 12 |
| **Total** | **7 files** | **20** |

## Inline regressions (3)

All 3 surfaced during sweep execution; all fixed inline per D-36-15 protocol; all counted toward the D-36-17 5-blocker hard cap.

1. **REG-36-02 (test infrastructure)** — `apps/backend/docker-compose.yml` did not expose redis on host 6379. Host-side pytest could not reach Redis → multiple skipped/errored tests. Fix mirrored the postgres pattern (`ports: ["6379:6379"]`). Commit `99bbf4e`.
2. **REG-36-03 (backend bug)** — `pt_sessions/service.py:267` placed raw UUID into the audit JSONB payload. `json.dumps` raised TypeError. Fix: `str(actor.id)` (the established v1.3 pattern). This is the same defect class that drove REG-36-03 in v1.3 audit work. Commit `bea5c42`.
3. **REG-36-04 (test bug)** — Post-race re-read returned identity-map-cached `PtPackage` instance with stale `sessions_remaining=1`. SQLAlchemy's per-session identity map masked the race-loser's DB-truth view. Fix: `db_session_real_commit.expire_all()` before re-read. Commit `864977a`.

## Deferred

- **DEFER-36-03-A** — 7 pt_sessions cancel + record non-race tests fail with `sqlalchemy.exc.MissingGreenlet`. A/B verified pre-existing via `git stash` round-trip; failures present at Phase 35 close. Rolled forward to 36-04 for surfacing in the full `test_suites.backend` evidence block.

## VERIFICATION-LOG.md bootstrap

Created `.planning/milestones/v1.4-VERIFICATION-LOG.md` with:
- Full YAML frontmatter mirroring `.planning/milestones/v1.3-VERIFICATION-LOG.md` shape
- `overrides_applied: 4` (REG-36-01 from 36-01 preflight + REG-36-02/03/04 from this plan)
- `overrides:` list with 4 entries (gap, resolved_in, evidence per v1.3 shape)
- `race_tests:` populated with 5 entries (all `result: pass`)
- Other top-level blocks (`human_verification:`, `ci_gates:`, `admin_web_canary:`, `test_suites:`, `deferred_items:`, `handoff_artifacts:`, `sign_off:`) as placeholder comments for 36-02/04/05 to fill incrementally

## Commits

| Hash | Message |
|------|---------|
| `99bbf4e` | fix(36-03): REG-36-02 expose redis port for host-side pytest |
| `bea5c42` | fix(36-03): REG-36-03 stringify UUID in pt_session_recorded audit payload |
| `864977a` | fix(36-03): REG-36-04 expire identity-map before post-race re-read |
| `10eb78d` | docs(36-03): capture race-test sweep evidence + bootstrap VERIFICATION-LOG.md (VER-02) |
