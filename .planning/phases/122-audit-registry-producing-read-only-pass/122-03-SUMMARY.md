---
phase: 122-audit-registry-producing-read-only-pass
plan: 3
subsystem: testing
tags: [seed-script, sqlalchemy, postgres, pytest-asyncio, audit, edge-cases]

requires:
  - phase: 122-audit-registry-producing-read-only-pass
    provides: 122-01 (defect registry schema / staging conventions this plan's V41-FUNC rows would use)
provides:
  - "apps/backend/scripts/seed_edge_cases.py -- additive, idempotent edge-case seed script"
  - ".planning/audits/v4.1-EDGE-SEED-MATRIX.md -- domain x axis coverage grid (AUD-04 evidence)"
affects: [122-05, 123, 124, 125, 126]

tech-stack:
  added: []
  patterns:
    - "Deterministic uuid5(NAMESPACE_DNS, 'edge_*@fixture.local') ids + ON CONFLICT (id) DO NOTHING for idempotent seed scripts (mirrors seed_verification_fixtures.py)"
    - "Money-boundary zero value injected one layer up (MembershipPlan.price_kopecks) when the target table's CHECK constraint forbids literal zero (Payment.amount_kopecks)"
    - "Europe/Moscow DST-boundary axis reframed as UTC-vs-MSK calendar-day rollover (Russia abolished DST in 2011 -- no literal transition exists to seed)"

key-files:
  created:
    - apps/backend/scripts/seed_edge_cases.py
    - .planning/audits/v4.1-EDGE-SEED-MATRIX.md
  modified: []

key-decisions:
  - "Zero-kopeck money boundary lives on MembershipPlan.price_kopecks, not Payment.amount_kopecks -- the Payment table's amount_sign_matches_subject_kind CHECK forbids a literal zero for both 'membership'/'pt_package' (>0) and 'refund' (<0) subject kinds."
  - "Bookings/pt_package-linked edges deferred to 122-05 -- Booking requires a trainer_availability_slots fixture, which is out of this script's additive-only scope (D-122-11); the empty-history-trainer axis is satisfied without it (zero slots ever created)."
  - "DST axis reinterpreted as the UTC-vs-Europe/Moscow calendar-day rollover trap (00:30 MSK = 21:30 UTC previous day) since Russia has had no literal DST transition since 2011."

requirements-completed: [AUD-04]

duration: ~35min
completed: 2026-07-26
---

# Phase 122 Plan 3: Edge-Case Seed Matrix + Additive Idempotent Seed Script Summary

**Authored the per-domain edge-case coverage grid and a sixth additive/idempotent seed script (`seed_edge_cases.py`) injecting nullable-actually-NULL fields, empty-history entities, 30-row pagination volume, money boundaries (zero/negative-refund/large-kopeck), and an Europe/Moscow UTC-vs-local day-rollover visit -- closing the AUD-04 precondition before any live-backend hunt begins.**

## Performance

- **Duration:** ~35 min
- **Tasks:** 2/2 completed
- **Files modified:** 2 created (0 modified)

## Accomplishments

- `.planning/audits/v4.1-EDGE-SEED-MATRIX.md` -- a domain x axis grid covering 16 domain rows (clients, memberships/plans, bookings/schedule, trainers/pt-packages, payments/finance/cashbox, promoCodes, visits/attendance, messages/notifications, payroll, reports, audit, users/roles, branches/settings, dashboard/search/import-export/load/trash, auth) against all D-122-12 axes, with concrete `edge_*@fixture.local` fixture references or `N/A -- <reason>` per cell.
- `apps/backend/scripts/seed_edge_cases.py` -- additive on top of `seed_demo_data.py`, idempotent via deterministic `uuid5` ids + `ON CONFLICT (id) DO NOTHING`, `python -m py_compile`-clean. Injects:
  - **Nullable-actually-NULL:** `edge_null_fields` client (11 nullable columns left unset) + `edge_null_fields_trainer`.
  - **Empty-history:** `edge_empty_history` client (0 visits/bookings/memberships) + `edge_empty_history_trainer` (0 bookings/slots) + `edge_empty_thread` (chat thread with 0 messages).
  - **Pagination past page 1:** 30x `edge_pagination_client_NNN` clients.
  - **Money boundaries:** `edge_zero_price_plan` (0 RUB plan -- Payment's CHECK forbids literal zero, so zero lives one layer up), `edge_money_membership` + refund pair (+/-500 000 kopecks via `refund_of` FK), `edge_large_money_membership`/`payment` (9 999 999.99 RUB, BigInteger boundary).
  - **Europe/Moscow TZ boundary:** `edge_dst_visit` at 2026-01-01T00:30 MSK (2025-12-31T21:30Z) -- the UTC-vs-MSK calendar-day rollover trap, since Russia has had no literal DST transition since 2011.

## Task Commits

1. **Task 2 (script): `feat(122-03)` seed_edge_cases.py** - `a1c95739`
2. **Task 1 (matrix): `docs(122-03)` v4.1-EDGE-SEED-MATRIX.md** - `37072fdb`

_Note: Task 2 (script) was written and committed before Task 1 (matrix) documentation commit landed, but the matrix content was authored first and used as the script's design spec, per plan intent._

## Files Created/Modified

- `apps/backend/scripts/seed_edge_cases.py` - additive, idempotent edge-case seed script (362 lines); only new app-tree file permitted by the AUD-08 allowlist.
- `.planning/audits/v4.1-EDGE-SEED-MATRIX.md` - domain x axis coverage grid; closes the sub-pass-1b Research Flag.

## Decisions Made

- Payment's `amount_sign_matches_subject_kind` CHECK constraint forbids a literal zero amount (must be `>0` for membership/pt_package, `<0` for refund) -- the zero-kopeck boundary was moved one layer up to `MembershipPlan.price_kopecks=0` (a free/comped plan) rather than weakening the fixture or the constraint.
- Booking-domain edges (empty-history-via-bookings, DST-via-booking-slot) were deferred rather than forced: `Booking` requires a `trainer_availability_slots` row, and generating slot fixtures is out of this additive-only script's scope per D-122-11. The empty-history-trainer axis is still satisfied (a trainer with zero ever-created slots trivially has zero bookings); any deeper booking-specific edge need is left for 122-05 to flag if the mechanical hunt finds a gap.
- DST axis reframed as the UTC-vs-Europe/Moscow calendar-day rollover (not a literal spring-forward/fall-back gap, since Russia abolished DST in 2011) -- documented explicitly in both the matrix and the script docstring so 122-05 doesn't mistake this for an oversight.

## Deviations from Plan

None - plan executed exactly as written. Both tasks' acceptance criteria were met: the matrix covers every listed domain across all D-122-12 axes with concrete fixtures or `N/A -- <reason>` (no cell says "re-run demo seed"), and the script is additive, idempotent, and `py_compile`-clean.

**Deferred (not a deviation, a scope boundary):** the plan's Task 2 action note says "run the script against docker-compose to confirm a clean load; capture the run command + output to evidence" and "any backend rejection... append a V41-FUNC row to `1b-live.md`." No local docker-compose stack was running during this execution session, so the live-load verification and any resulting `1b-live.md` rows are deferred to whoever runs `uv run python -m scripts.seed_edge_cases` against the compose stack (a 122-05 precondition per the plan's own framing: "a live DB run is a 122-05 precondition, not required here" in the task instructions given to this executor). This is explicitly permitted by the orchestrator's execution scope for this plan.

## Issues Encountered

- The Write tool enforces a 300-line-per-file soft limit that initially rejected two drafts (475 and 392 lines). Resolved by consolidating five near-duplicate `_client`/`_trainer`/`_membership`/`_payment` insert helpers into a single generic `_upsert(session, model, **values)` helper, bringing the final file to 362 lines post-formatter (the limit did not block the final write, indicating it may be advisory/soft rather than hard-enforced at that threshold).

## User Setup Required

None - no external service configuration required. Operator follow-up: run `uv run python -m scripts.seed_edge_cases` against the local docker-compose stack (after `seed_demo_data`) before the 122-05 live-backend hunt begins, per D-122-13.

## Next Phase Readiness

- AUD-04 precondition satisfied: the edge-case matrix and additive idempotent seed script both exist and are committed, ahead of any live-backend hunt.
- 122-05 can now run its manifest hunt and browser walk against the dataset `seed_edge_cases.py` produces (once loaded on docker-compose) rather than a fresh demo reseed.
- Any structural defect the live load surfaces (e.g. a CHECK/constraint rejecting a legitimately-edge value) should be appended to `.planning/audits/staging/1b-live.md` as a `V41-FUNC` row, not silently softened in the script.

---
*Phase: 122-audit-registry-producing-read-only-pass*
*Plan: 3*
*Completed: 2026-07-26*
