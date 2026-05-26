---
phase: 61-openapi-handoff-milestone-verification
plan: 03
subsystem: docs
tags: [runbook, handoff, v1.9, trainers, payroll, schedule, reports, operator, csv-bom, cyrillic, csrf, rbac, milestone-close]

# Dependency graph
requires:
  - phase: 58-payroll-foundations-ledger
    provides: payroll endpoints (trainer-configs PUT/GET, preview GET, accruals POST/GET, mark-paid POST) + OWNER_ONLY pairs (CREATE,COMPENSATION) / (CREATE,PAYROLL) / (EDIT,PAYROLL) / (REFUND,PAYROLL) / (LIST,PAYROLL); golden kopeck fixtures in test_payroll_preview.py
  - phase: 59-recurring-schedule-time-off
    provides: recurring-templates POST/GET/deactivate + time-off POST/GET/DELETE endpoints; D-59-08 reception-accessible LIST exception
  - phase: 60-trainer-usage-report
    provides: /reports/trainers JSON + /reports/trainers.csv endpoints; D-60-11 CSV discipline (UTF-8 BOM + RFC-4180); D-60-03 deterministic ordering
  - phase: 57-openapi-handoff-milestone-verification (v1.8 milestone)
    provides: v1.8-reports-runbook.md sectioned-curl + attestation format template; D-12 OPERATOR-PENDING discipline
provides:
  - "v1.9 operator runbook authored at .planning/handoff/v1.9-trainers-runbook.md (513 lines)"
  - "5 numbered scenarios proving v1.9 trainers surface end-to-end against a live docker compose stack"
  - "Reception-403 enumeration over 12 owner-only v1.9 routes (explicit exclusion of GET /recurring-templates + GET /time-off per D-59-08)"
  - "Live cross-validation harness for Phase 60 CSV discipline (UTF-8 BOM + Cyrillic round-trip in Excel/LibreOffice)"
  - "OPERATOR-PENDING (D-61-12) discipline: live execution recorded as post-merge operator step, NOT a phase-completion blocker"
affects: [61-04, v1.10-admin-web-integration, v2.0-external-integrators]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Milestone-close runbook authoring (v1.4 / v1.7 / v1.8 / v1.9 cadence — authored by Claude, executed by operator post-merge)"
    - "Sectioned-curl idiom: numbered `## N. Title` + Russian prose referencing file:line + fenced bash with `При успехе:` expected response"
    - "Cookies.txt jar + `CSRF=$(awk '/sportzal_csrf/ {print $7}' cookies.txt)` for owner mutating-call bootstrap (lifted from v1.4 / v1.8 runbooks)"
    - "OPERATOR-PENDING disclaimer block at the end + `## Operator` attestation block at the very bottom"

key-files:
  created:
    - ".planning/handoff/v1.9-trainers-runbook.md (513 lines, 5 scenarios + disclaimer + attestation)"
  modified: []

key-decisions:
  - "Followed D-61-07 verbatim: 5 scenarios = bring-up + payroll + recurring/time-off + trainers report + reception-403; mirrored v1.8 runbook format exactly"
  - "§2 payroll fixtures lifted from apps/backend/tests/integration/payroll/test_payroll_preview.py (pure-pct 15%, pure-fixed 50k×3, hybrid 1000bps+30k/session×2) — operator eyeball-matches against seed-dependent demo data"
  - "§3 includes a deliberate §3.5 trainer-slots eyeball-check confirming time-off уважается генератором (REC-04 / TOFF-03 live acceptance)"
  - "§5 explicitly notes GET /recurring-templates + GET /time-off are reception-accessible per D-59-08 booking flow — NOT in the 12-route 403 enumeration"
  - "Added CSRF discipline (X-CSRF-Token header + cookies.txt extract via awk) on all unsafe-method curl examples — v1.8 runbook predominantly GETs and did not need it; v1.9 surface is mutation-heavy"

patterns-established:
  - "v1.9 runbook is a faithful clone of v1.8 sectioned-curl structure with v1.9-specific endpoint substitutions; sets the template precedent for the v2.0 milestone-close runbook"
  - "Reception-403 scenarios should explicitly call out LIST-endpoint exceptions (D-59-08-style carve-outs) to prevent operator confusion when GET succeeds under reception"

requirements-completed: [HND-01]

# Metrics
duration: ~18min
completed: 2026-05-26
---

# Phase 61 Plan 03: v1.9 Trainers Surface Runbook Summary

**Operator runbook for the v1.9 trainers surface — 5 scenarios (docker bring-up, payroll golden-path, recurring + time-off golden-path, trainer-usage report with Excel/Cyrillic check, reception-403 over 12 owner-only routes) authored as a faithful clone of v1.8-reports-runbook.md with OPERATOR-PENDING (D-61-12) discipline.**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-05-26T06:19:00Z (approx — first context read)
- **Completed:** 2026-05-26T06:37:32Z
- **Tasks:** 1
- **Files modified:** 1 (created)

## Accomplishments
- Authored `.planning/handoff/v1.9-trainers-runbook.md` (513 lines) at the ROADMAP-locked path
- All 5 numbered scenarios committed in a single docs(61-03) commit with deterministic operator-runnable curl examples
- Live cross-validation harness for Phase 58 payroll arithmetic, Phase 59 REC-04/TOFF-03 acceptance, and Phase 60 D-60-11 CSV BOM discipline
- OPERATOR-PENDING (D-61-12) disclaimer + `## Operator` attestation block establish post-merge live-walkthrough as the explicit follow-up, not a phase blocker

## Task Commits

Each task was committed atomically:

1. **Task 1: Author v1.9-trainers-runbook.md with 5 scenarios + operator-pending disclaimer + attestation** — `b3b3ed04` (docs)

## Files Created/Modified
- `.planning/handoff/v1.9-trainers-runbook.md` (NEW, 513 lines) — operator runbook for the v1.9 trainers surface. Header + 5 sectioned-curl scenarios + OPERATOR-PENDING (D-61-12) disclaimer + `## Operator` attestation. Mirrors v1.8-reports-runbook.md format verbatim, substitutes v1.9 endpoints (payroll trainer-configs/preview/accruals/mark-paid, recurring-templates POST/GET/deactivate, time-off POST/GET/DELETE, reports/trainers JSON+CSV).

## Decisions Made
- **§2 fixture seed reference (vs hard-coded number):** test_payroll_preview.py exposes multiple goldens (pure-pct, pure-fixed, hybrid); the exact kopecks the operator observes from `GET /payroll/preview` depends on which demo seed is loaded. The runbook lists ALL three constants and asks the operator to eyeball-match against whichever pattern the seed expresses — this is more honest than picking one number and hoping it matches.
- **§3.5 added a trainer-slots eyeball-check** (not explicitly enumerated in the plan's `<the_5_scenarios>` but called out in D-61-07 as the "confirm slot generation respects time-off windows per REC-04 / TOFF-03 acceptance" requirement). Without this verification step, §3 would only exercise CRUD on time-off without proving the integration with slot generation.
- **CSRF discipline added on all unsafe-method calls** (PUT, POST, DELETE). v1.8 runbook's surface was predominantly GETs and only its login flow demonstrated the CSRF cookie; v1.9 surface is mutation-heavy, so the `CSRF=$(awk ...)` extract is hoisted to §2.1 and reused throughout §§2–3 + §5. Consistent with v1.4-auth-runbook.md L77-80 idiom.
- **§5 explicit LIST carve-out callout:** the plan's `<the_5_scenarios> §5` notes that GET LIST endpoints are reception-accessible per D-59-08. I made this a prominent "Важно — НЕ в 403-перечислении" block before the 12-route enumeration to prevent operator confusion (operator who sees `GET /recurring-templates` return 200 under reception might wrongly conclude RBAC is broken).

## Deviations from Plan

None — plan executed exactly as written. The two "additions" above (§3.5 trainer-slots check, CSRF discipline) are not deviations: §3.5 is explicitly called for in D-61-07 ("confirm slot generation respects time-off windows"); CSRF discipline is mandated by the plan's `<runbook_template>` block ("reuses §1 cookies.txt jar + `CSRF=$(awk '/sportzal_csrf/ {print $7}' cookies.txt)` pattern").

## Issues Encountered
None.

## User Setup Required
None for this plan. Live operator execution of the runbook is captured by D-61-12 OPERATOR-PENDING discipline and is tracked at phase close (Plan 61-04 / STATE.md) — it is explicitly not a Phase 61 completion blocker.

## Self-Check: PASSED
- File exists: `/Users/andre/Workspace/Development/clubcore/.claude/worktrees/agent-a9e711e91bafa288e/.planning/handoff/v1.9-trainers-runbook.md` ✓
- Commit exists: `b3b3ed04 docs(61-03): author v1.9-trainers-runbook.md` ✓
- All 16 verification markers present (5 numbered scenarios, OPERATOR-PENDING, D-61-12, ## Operator, 8 endpoint paths, 403) ✓
- 5 numbered scenario headers (`## 1.` through `## 5.`) verified via `grep -c '^## [1-5]\. '` returning 5 ✓
- No stub patterns (TODO/FIXME/placeholder/coming soon) ✓
- No accidental deletions in commit ✓

## Next Phase Readiness
- Runbook is ready for the v1.9 milestone close (Plan 61-04 — verification + STATE.md OPERATOR-PENDING entry).
- v1.10 admin-web integration team has a copy-paste operational walkthrough proving the v1.9 backend surface against a live docker stack.
- Live operator execution remains the only outstanding cross-validation point (D-61-12) — explicitly NOT a Phase 61 blocker per the v1.4 / v1.7 / v1.8 precedent.

---
*Phase: 61-openapi-handoff-milestone-verification*
*Completed: 2026-05-26*
