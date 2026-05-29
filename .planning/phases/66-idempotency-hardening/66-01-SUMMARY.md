---
phase: 66-idempotency-hardening
plan: "01"
subsystem: backend/idempotency
tags: [audit, idempotency, classification, doc-only]
dependency_graph:
  requires: []
  provides:
    - .planning/handoff/v1.11-idempotency-audit.md
  affects:
    - 66-03 (IDM-07 wiring — consumes category-C list)
    - 66-04 (IDM-04 $ref injection — consumes CATEGORY_A_OPERATION_IDS)
    - 66-05 (IDM-03 tests — consumes full A-set for test coverage)
tech_stack:
  added: []
  patterns:
    - "D-66-CLASSIFY-RUBRIC: A/B/C rubric applied row-by-row to all 58 mutating ops"
    - "Explicit A-vs-B decision recorded for online refund endpoints (T-66-02)"
key_files:
  created:
    - .planning/handoff/v1.11-idempotency-audit.md
  modified: []
decisions:
  - "Online refund endpoints (refund_membership_online, refund_pt_package_online) classified B — DB partial UNIQUE uq_online_refunds_alive_per_online_payment + body-level idempotency_key forwarded to YooKassa are sufficient; header-level Idempotency-Key would be a redundant third layer"
  - "Cash refund refund_membership classified B — explicit D-32-20 DB-uniqueness-gate-only design"
  - "Cash refund refund_pt_package classified A (already wired) — verify_idempotency IS present at pt_packages/router.py:469"
  - "6 schedule endpoints already wired (not anticipated in CONTEXT.md): publish_slot, cancel_slot, create_recurring_template, deactivate_recurring_template, create_time_off, delete_time_off"
  - "4 membership transitions (cancel/freeze/unfreeze/renew) are C — unwired but should be A; IDM-07 targets for 66-03"
  - "CATEGORY_A_OPERATION_IDS contains 22 entries (18 already-wired + 4 IDM-07 additions)"
metrics:
  duration: "~20min"
  completed_date: "2026-05-29"
  tasks_completed: 2
  files_modified: 1
---

# Phase 66 Plan 01: Idempotency Endpoint Classification Audit Summary

**One-liner:** Authoritative A/B/C classification of all 58 mutating endpoints yielding a 22-operationId CATEGORY_A_OPERATION_IDS list for downstream 66-03/66-04/66-05.

## What Was Done

### Task 1: Enumerate every mutating endpoint under app/api/v1

Ran `python3` against `apps/backend/openapi.json` to extract all POST/PATCH/PUT/DELETE operations — confirmed **58 mutating ops** in the spec. Additionally scraped all modules for:

1. **already-wired?** — grep for `Depends(verify_idempotency)` across all `app/modules/*/router.py` files
2. **emits-audit-event?** — reviewed service layer audit.emit callsites
3. **DB-unique-guarded?** — reviewed UNIQUE constraints, partial UNIQUE indexes, FSM guards

**Key discovery:** The schedule module (`apps/backend/app/modules/schedule/router.py`) has **6 already-wired** idempotency endpoints not anticipated in the CONTEXT.md already-wired list: `publish_slot`, `cancel_slot`, `create_recurring_template`, `deactivate_recurring_template`, `create_time_off`, `delete_time_off`.

The ЮKassa webhook (`/_internal/yookassa/webhook`, `include_in_schema=False`) was manually added as a separate B-row using the `cc:yookassa:webhook:` dedup path (D-11-IDM-WEBHOOK).

### Task 2: Write classification audit table and category-A operationId list

Created `.planning/handoff/v1.11-idempotency-audit.md` with:
1. Phase 66 IDM-01 provenance header
2. D-66-CLASSIFY-RUBRIC verbatim
3. Full 59-row classification table (58 spec ops + 1 webhook)
4. Explicit A-vs-B decision section for refund endpoints (T-66-02 mitigation)
5. Category-A operationId set (22 entries, sorted, machine-copyable)

## Deviations from Plan

### Auto-discovered: more already-wired endpoints than CONTEXT anticipated

**Found during:** Task 1 — live code scan
**Issue:** CONTEXT.md listed `pt_packages`, `pt_sessions`, `bookings`, `memberships` (create only), and `online_payments` (4 sell endpoints) as the already-wired set. The scan also found `apps/backend/app/modules/schedule/router.py` with 6 additional `verify_idempotency` callsites.
**Fix:** All 6 schedule endpoints classified A (already-wired). CATEGORY_A_OPERATION_IDS expanded from 11 to 18 already-wired entries.
**Impact:** 66-03 IDM-07 wiring scope is smaller than anticipated (only 4 new C-class endpoints, not 7). 66-04 frozenset is larger (22 vs expected ~15).

## Key Decisions Made

| Decision | Rationale |
|----------|-----------|
| `refund_membership_online`, `refund_pt_package_online` → **B** | Body-level `idempotency_key` forwarded to ЮKassa + DB `partial UNIQUE` is sufficient double-submit defence; header-level would be redundant third layer; 202 async return makes verbatim-replay semantics awkward |
| `refund_membership` → **B** | Explicit D-32-20 DB-uniqueness-gate-only design; router docstring says "NO Idempotency-Key dependency" |
| `refund_pt_package` → **A (already wired)** | Live code has `verify_idempotency` at pt_packages/router.py:469 |
| `create_visit` → **B** | UNIQUE `(client_id, gym_date)` makes double-checkin a 409 `duplicate_checkin`; DB guard fully defends |
| `create_accrual` → **B** | `INSERT ON CONFLICT DO NOTHING RETURNING` + `payroll_period_already_run` 409 guard |

## Category-A operationId List (verbatim for 66-04 frozenset)

Copy this list verbatim into `CATEGORY_A_OPERATION_IDS` in `apps/backend/app/main.py`:

```
cancel_booking
cancel_membership
cancel_pt_package
cancel_pt_session
cancel_slot
create_booking
create_membership
create_pt_package
create_recurring_template
create_time_off
deactivate_recurring_template
delete_time_off
freeze_membership
publish_slot
record_pt_session
refund_pt_package
renew_membership
sell_membership_qr
sell_membership_redirect
sell_pt_package_qr
sell_pt_package_redirect
unfreeze_membership
```

**Total: 22 operationIds** (18 already-wired + 4 IDM-07 C-class additions).

**IDM-07 wiring targets (C-class, for 66-03):**
- `cancel_membership`
- `freeze_membership`
- `renew_membership`
- `unfreeze_membership`

## Verification

- `git status --porcelain apps/backend` is empty (doc-only plan — confirmed)
- Table column header matches locked spec exactly
- Category-A operationId list present, sorted, one-per-line
- Spec count assertion: `python3 -c "..."` prints 58 (>= 30 per task acceptance criteria)

## Self-Check: PASSED

- `.planning/handoff/v1.11-idempotency-audit.md` exists: FOUND
- Commit `8fe05615` exists: FOUND
- `git status --porcelain apps/backend` empty: CONFIRMED
