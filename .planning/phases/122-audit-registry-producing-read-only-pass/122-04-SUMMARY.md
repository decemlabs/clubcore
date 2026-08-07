---
phase: 122-audit-registry-producing-read-only-pass
plan: 4
subsystem: infra
tags: [audit, operator-pending, k3d, runbook, defect-registry]

requires:
  - phase: 122-01
    provides: registry skeleton, staging protocol, V41-INFRA-001/002 HARD GATE tracer rows
provides:
  - 27 new V41-INFRA rows (003-029) triaging every non-HARD-GATE v4.0 operator-pending
    item into (k3d-scope) open vs deferred:operator-pending hardware/credential-gated
  - 1 reconciliation row (V41-INFRA-030) recording the honest re-derived count (29)
    against the quoted "23" and STATE.md's "27" tally
affects: [126-infra-ops-fixes, 127-registry-consolidation-milestone-close]

tech-stack:
  added: []
  patterns:
    - "Operator-pending triage: split each runbook item into k3d-provable vs genuinely hardware/credential-gated, one registry row per item, never editing the two HARD GATE rows"

key-files:
  created: []
  modified:
    - .planning/audits/staging/1c-infra.md

key-decisions:
  - "Re-derived count is 29 distinct items (2 HARD GATEs + 27 non-gate items), not the quoted 23 (raw Phase 118/119/120 row sum, still containing 2 HARD GATE duplicate rows, omitting the 6 Cross-Cutting P-items) nor STATE.md's 27 tally (swaps in Phase 121's 4 make-up/make-smoke items, which do not appear anywhere in production.md's Operator-Pending Boundary section at all)"
  - "119-1 and 120-1 are literal restatements of HARD GATE 1/2 inside the Phase 119/120 tables, not new items — de-duplicated rather than re-counted"
  - "119-4 (Certificate NET-03) is split conceptually: selfSigned Ready is k3d-scope (V41-INFRA-009), the letsencrypt-prod half is blocked_by cross-cutting P-1 (V41-INFRA-024)"
  - "120-7 (BAK-04 CronJob restore-verify) is tagged k3d-scope, referencing V41-INFRA-002 (BAK-03) — the CronJob-triggered scratch-namespace mechanics are exercisable in local k3d even though BAK-03 itself stays a HARD GATE"
  - "V41-INFRA-001 (SEC-02) and V41-INFRA-002 (BAK-03) left byte-identical — not edited toward closed, per D-122-23"

requirements-completed: [AUD-07]

coverage:
  - id: D1
    description: "Every non-HARD-GATE v4.0 operator-pending item from infra/runbooks/production.md § Operator-Pending Boundary is a V41-INFRA row (003-029) tagged k3d-scope (open) or hardware/credential-gated (deferred:operator-pending)"
    requirement: "AUD-07"
    verification:
      - kind: other
        ref: "grep -cE '^\\| V41-INFRA-[0-9]' .planning/audits/staging/1c-infra.md -> 30; grep -qi k3d-scope; grep -qi operator-pending; grep -qE V41-INFRA-001; grep -qE V41-INFRA-002 (all pass, see plan verify block)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Honest count reconciliation row (V41-INFRA-030) records the runbook-derived total (29) against the quoted 23 and STATE.md's 27, without force-fitting either"
    requirement: "AUD-07"
    verification:
      - kind: manual_procedural
        ref: "Manual enumeration: 2 HARD GATEs + Phase118(4) + Phase119(9, excl 119-1 dup) + Phase120(8, excl 120-1 dup) + Cross-Cutting(6) = 29; cross-checked against 118/119/120-UAT.md total/pending fields (4/4, 10/10, 9/9)"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-07-26
status: complete
---

# Phase 122 Plan 4: Infra Operator-Pending Desk-Review Triage Summary

**Re-derived the v4.0 operator-pending ledger from infra/runbooks/production.md (not the assumed "23"), producing 27 new V41-INFRA registry rows split k3d-scope vs hardware/credential-gated plus a reconciliation row recording the honest count of 29.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-07-26T13:47:00Z
- **Completed:** 2026-07-26T13:53:37Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Enumerated every item under `infra/runbooks/production.md` § Operator-Pending Boundary (line 421+): 2 HARD GATEs (already seeded as V41-INFRA-001/002), Phase 118 (4 items), Phase 119 (10 rows, 1 a HARD GATE duplicate), Phase 120 (9 rows, 1 a HARD GATE duplicate), Cross-Cutting Production Probes (6 items P-1..P-6)
- Triaged all 27 non-duplicate items into V41-INFRA-003..029, each tagged either `open` + `(k3d-scope)` (provable against a real local k3d cluster: 118-1..4, 119-2/3(part)/5/6/7/8/9/10, 120-2/3/4/5/6/7/9 — 18 rows) or `deferred:operator-pending` + hardware/credential-gated (119-3's live-domain leg, 120-8, all 6 cross-cutting P-items — 9 rows)
- Cross-referenced every row to its source `1NN-UAT.md` file (total/pending counts verified: 118 = 4/4, 119 = 10/10, 120 = 9/9) and the exact runbook line
- Appended V41-INFRA-030, a reconciliation row that records the honest re-derived count (29 distinct items) against the quoted "23" (which double-counts nothing new but omits the 6 Cross-Cutting probes and still contains the 2 HARD GATE dup rows within the 4+10+9) and STATE.md's "27" tally (which substitutes in Phase 121's 4 items — not present anywhere in the runbook's boundary section, since production.md was itself authored by Phase 121)
- Left V41-INFRA-001 (SEC-02) and V41-INFRA-002 (BAK-03) byte-identical to how 122-01 seeded them

## Task Commits

Each task was committed atomically:

1. **Task 1: Re-derive and triage the v4.0 operator-pending ledger into (k3d-scope) vs hardware/credential-gated rows** - `79a25f2c` (docs)

**Plan metadata:** (this commit, below)

## Files Created/Modified
- `.planning/audits/staging/1c-infra.md` - Appended V41-INFRA-003..029 (triage rows) + V41-INFRA-030 (count reconciliation), 28 new rows total (30 rows in file including the 2 pre-existing HARD GATEs)

## Decisions Made
- **Count reconciliation is its own registry row, not a footnote.** The honest runbook-derived total is 29 (2 HARD GATEs + 27 triaged items), which matches neither prior number quoted elsewhere in the project — recorded as V41-INFRA-030 per D-122-22 rather than silently picking one.
- **119-1 and 120-1 (the in-table HARD GATE references) are not counted as new items** — they are literal restatements of V41-INFRA-001/002 within the Phase 119/120 tables, so triaging them again would double-count the same defect under two IDs.
- **119-4 (Certificate NET-03) is split across two rows conceptually but recorded once** — the k3d-provable selfSigned-Ready half is V41-INFRA-009 (open, k3d-scope); the letsencrypt-prod half is explicitly deferred via `blocked_by: V41-INFRA-024` (cross-cutting P-1) rather than force-fitting the whole row into one bucket.
- **120-7 (BAK-04 CronJob restore-verify) is tagged k3d-scope** even though it shares mechanics with the BAK-03 HARD GATE — the CronJob-triggered scratch-namespace restore + injected-mismatch-alert path is exercisable entirely within a local k3d cluster (per the runbook's own wording), distinct from BAK-03's broader "verified restore round-trip on production-equivalent hardware" framing which the tracer already correctly pinned as a HARD GATE.
- **P-3 (ЮKassa sandbox sale+refund) references the STATE.md resolution already on record** (`✅ TEST-SHOP SUFFICIENT`, 2026-06-17) rather than treating the row as fully open — the sandbox leg is done; only real production credentials remain deferred.

## Deviations from Plan

None - plan executed exactly as written. The plan explicitly anticipated the count might not be 23 and instructed recording the real number with a discrepancy row (D-122-22); that is exactly what V41-INFRA-030 does, not a deviation.

## Issues Encountered

**Runbook doesn't self-list Phase 121's items.** `infra/runbooks/production.md` was itself authored by Phase 121, so its own `121-UAT.md` items (`make up`/`make smoke` end-to-end, 4 items) never appear inside the Operator-Pending Boundary section — that section only aggregates gaps from *prior* phases (118, 119, 120) plus cross-cutting probes. This explains why STATE.md's "4+10+9+4=27" tally (which includes Phase 121's own 4 items) cannot be reproduced by reading the runbook alone; documented as part of the V41-INFRA-030 reconciliation rather than treated as an error to fix.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 126 (INFRA-01..05) has a clean, itemized worklist: 18 k3d-scope rows are directly actionable against a real k3d cluster; 9 hardware/credential-gated rows (plus the 2 HARD GATEs) are correctly parked as `deferred:operator-pending` and will not be mistaken for closable work.
- No blockers for the next sub-pass (1d or wave completion) — this plan only appended rows to `.planning/audits/staging/1c-infra.md`; no app or infra code was touched (AUD-08 read-only invariant held).

---
*Phase: 122-audit-registry-producing-read-only-pass*
*Completed: 2026-07-26*

## Self-Check: PASSED
- FOUND: .planning/audits/staging/1c-infra.md
- FOUND: .planning/phases/122-audit-registry-producing-read-only-pass/122-04-SUMMARY.md
- FOUND: commit 79a25f2c
