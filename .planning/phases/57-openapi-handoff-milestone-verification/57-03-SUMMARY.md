---
phase: 57-openapi-handoff-milestone-verification
plan: "03"
subsystem: handoff-documentation
tags: [runbook, reports, audit-log, operator-verification, v1.8]
dependency_graph:
  requires: [57-02]
  provides: [v1.8-reports-runbook, operator-pending-VER-04]
  affects: [STATE.md, ROADMAP.md]
tech_stack:
  added: []
  patterns: [sectioned-curl-runbook, operator-attestation, golden-number-cross-validation]
key_files:
  created:
    - .planning/handoff/v1.8-reports-runbook.md
  modified:
    - .planning/STATE.md
decisions:
  - "Live docker execution is operator-pending per v1.4/v1.7 precedent — not a phase-57 completion blocker (D-12)"
  - "Revenue golden-path scenario uses exact constants from test_reports_dst.py (GROSS=250000, REFUND=50000, NET=200000 kop, GOLDEN_DATE_MSK_NEXT=2026-01-02)"
  - "Runbook clones v1.4-auth-runbook.md sectioned-curl + attestation format per D-10"
metrics:
  duration: "8 minutes"
  completed_date: "2026-05-24"
---

# Phase 57 Plan 03: v1.8 Reports + Audit Read API Operator Runbook Summary

**One-liner:** Operator runbook with 5 curl scenarios cross-validating reports/audit RBAC and revenue golden amounts against DST test constants (NET_KOPECKS=200 000 kop on MSK 2026-01-02).

## What Was Built

Created `.planning/handoff/v1.8-reports-runbook.md` — a copy-paste curl walkthrough in the
v1.4-auth-runbook.md sectioned format, with 5 numbered scenarios for manual verification of the
v1.8 reports + audit read API (VER-01 / ROADMAP SC#5).

### Five Scenarios

1. **Docker Compose bring-up** — `docker compose up --build` from `apps/backend/`, health-check
   smoke test against `/api/v1/health`.

2. **Revenue golden-path** — Owner-token curl to `GET /api/v1/reports/revenue?fromDate=2026-01-01&toDate=2026-01-02&groupBy=day`. Operator eyeball-matches `netKopecks` in the `2026-01-02` MSK bucket against the DST test constants (GROSS=250 000 kop, REFUND=50 000 kop, NET=200 000 kop). The `2026-01-01` bucket must be absent — proving boundary payment at 21:30 UTC lands on next MSK calendar day.

3. **Audit-log filter narrowing** — Four progressive filter curls: unfiltered list, `?action=login_success`, AND-narrows with `?action=login_success&resourceType=session`, date-window `?from=`/`?to=`, plus actorUserId filter. Negative case: unknown action → 422.

4. **Reception 403** — Login as reception, then curl `/reports/revenue`, `/reports/clients`, and `/audit-log` — all three must return `HTTP 403` + `{"code":"forbidden"}`. Manual cross-validation of T-57-05 RBAC boundary.

5. **CSV download + Excel Cyrillic check** — `curl -OJ` all four CSV endpoints (`revenue.csv`, `clients.csv`, `visits.csv`, `audit-log.csv`), open in Excel, confirm UTF-8 BOM delivers Cyrillic without mojibake — live validation of Phase 56 D-13.

### Operator-Pending Entry

Added `VER-04 / D-12` row to STATE.md Deferred Items table: live runbook execution is
operator-pending per v1.4/v1.7 precedent; **not a phase-57 completion blocker**.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | `4c602fb` | `docs(57-03): author v1.8 reports + audit read API operator runbook` |
| Task 2 | `ff839af` | `chore(57-03): record v1.8 runbook live execution as operator-pending in STATE.md` |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. This is a documentation artifact; no data wiring required.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| T-57-05 (mitigated) | `.planning/handoff/v1.8-reports-runbook.md` | Scenario 4 documents and manually verifies reception → 403 on /reports/* and /audit-log |
| T-57-06 (accepted) | `.planning/handoff/v1.8-reports-runbook.md` | Scenario 5 has operator confirm CSV Cyrillic renders correctly; audit payload export is owner-gated |

## Self-Check: PASSED

- `.planning/handoff/v1.8-reports-runbook.md` — FOUND
- `.planning/STATE.md` — FOUND with VER-04 operator-pending entry
- Commit `4c602fb` — FOUND
- Commit `ff839af` — FOUND
- 5 numbered `## N.` headings — VERIFIED (grep returns 5)
- `reports/revenue`, `/audit-log`, `.csv`, `forbidden`, `## Operator` — all present
- Golden constants (250 000, 50 000, 200 000, 2026-01-01, 2026-01-02) — VERIFIED
- `openapi.json` source-of-truth reference — VERIFIED
