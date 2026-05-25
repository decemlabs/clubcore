---
status: partial
phase: 58-payroll-foundations-ledger
source: [58-VERIFICATION.md]
started: 2026-05-25
updated: 2026-05-25
---

## Current Test

[awaiting developer decision — no functional testing required; both items are reconciliation decisions]

## Tests

### 1. Rounding algorithm reconciliation (financial-correctness decision)
expected: A single, intentional rounding policy for commission_kopecks, consistent between the milestone-level locked decision and the shipped code.
result: [pending]

REQUIREMENTS.md "Locked Decisions" **D-PAYROLL-ROUNDING** specifies
`decimal.Decimal` + `ROUND_HALF_EVEN` (banker's rounding). The shipped
implementation (`compute_accrual_components` in `app/modules/payroll/service.py`)
uses integer `math.ceil` (rounding in the trainer's favor), per CONTEXT.md
**D-58-04**. Both are written as "locked." The code is internally consistent
(preview + accrual + clawback all share the one helper, so no drift), but it
diverges from the REQUIREMENTS.md milestone contract.

Decision needed: either (a) ratify `math.ceil` and correct D-PAYROLL-ROUNDING in
REQUIREMENTS.md, or (b) gap-closure plan to switch the helper to
`Decimal` + `ROUND_HALF_EVEN` and update the golden-number tests.

### 2. ROADMAP SC#5 audit-event count wording
expected: ROADMAP Phase 58 SC#5 count matches the registered LOCKED_AUDIT_EVENTS so Phase 61 milestone verification does not re-raise it as a gap.
result: [pending]

ROADMAP SC#5 says "all **6** new LOCKED_AUDIT_EVENTS." Only **4** were registered
(trainer_comp_config_set, payroll_accrual_created, payroll_accrual_paid,
payroll_clawback_recorded) — the planner/executors determined PAY-01..06 genuinely
need only 4, and documented the "6" as a pre-collapse over-estimate
(`(EDIT,COMPENSATION)` collapsed into `(CREATE,COMPENSATION)`).
`test_audit_taxonomy.py` correctly asserts 89. Recommended: update SC#5 wording
to "4" before Phase 61. Low-risk doc edit, no code impact.

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps

(none functional — both items are decisions, tracked above)
