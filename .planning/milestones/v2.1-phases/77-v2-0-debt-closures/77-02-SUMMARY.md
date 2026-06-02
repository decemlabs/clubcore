---
phase: 77-v2-0-debt-closures
plan: "02"
subsystem: client-pwa / planning-docs
tags: [doc-only, fix-02, receipt-chip, ui-spec, debt-closure]
dependency_graph:
  requires: []
  provides: [FIX-02-resolution]
  affects: []
tech_stack:
  added: []
  patterns: [amend-spec-to-match-shipped-reality]
key_files:
  modified:
    - .planning/milestones/v2.0-phases/999.5-client-pwa-onboarding-and-receipt-email/999.5-UI-SPEC.md
    - apps/client-pwa/src/routes/PaymentReturnScreen.jsx
decisions:
  - "D-77-05/06: amend 999.5-UI-SPEC D-09 rather than restore the receipt-destination chip; no-chip PaymentSucceededView declared accepted behavior (FIX-02)"
  - "D-77-07: only a comment cross-reference added to PaymentReturnScreen.jsx — no behavioral change"
metrics:
  duration: "~10 min"
  completed: "2026-06-02"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
---

# Phase 77 Plan 02: FIX-02 Doc Amendment (D-09 Accepted-Behavior Rationale) Summary

**One-liner:** Amended 999.5-UI-SPEC §Screen 2 D-09 to declare the no-chip `PaymentSucceededView` the accepted behavior (FIX-02), with explicit rationale and a comment cross-reference in PaymentReturnScreen.jsx.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Amend 999.5-UI-SPEC D-09 with accepted-behavior rationale | 55176e67 | `.planning/milestones/.../999.5-UI-SPEC.md` |
| 2 | Add cross-reference comment in PaymentReturnScreen.jsx | 1b376be5 | `apps/client-pwa/src/routes/PaymentReturnScreen.jsx` |

## What Was Done

### Task 1 — UI-SPEC amendment

The `D-09` block (§Screen 2, "Post-payment augmentation") in `999.5-UI-SPEC.md` was amended with an explicit note (Phase 77 / FIX-02, 2026-06-02) that:

- The "ЧЕК ОТПРАВЛЕН НА {email|phone}" chip is intentionally omitted to match the approved payment mockup (REVISION 2, `PaymentReturnScreen.jsx`).
- Receipt access is provided via the existing "Открыть чек" receipt-link row (D-11).
- Backend `receiptEmail`/`receiptPhone` fields remain available for future reinstatement.
- A labelled **Accepted behavior** statement declares the no-chip `PaymentSucceededView` the current accepted state, superseding the original D-09 chip specification.

Summary item #8 was also updated from "shows 'ЧЕК ОТПРАВЛЕН НА {dest}' as read-only" to accurately reflect the no-chip accepted state.

### Task 2 — Comment cross-reference

A single comment line was appended to the existing REVISION 2 block in `PaymentReturnScreen.jsx`:

```
 * Chip omission accepted per amended 999.5-UI-SPEC §Screen 2 D-09 (Phase 77 / FIX-02).
```

No JSX, state, props, or logic was changed. All 17 existing `PaymentReturnScreen.test.jsx` tests pass unchanged. `tsc -b` and `eslint` exit 0.

## Verification Results

| Check | Result |
|-------|--------|
| `grep -n "Accepted behavior" 999.5-UI-SPEC.md` | Line 402: match found in D-09 region |
| `git diff --stat PaymentReturnScreen.jsx` | 1 insertion (comment only) |
| `pnpm exec vitest run PaymentReturnScreen.test.jsx` | 17/17 pass |
| `pnpm exec tsc -b` | exit 0 |
| `pnpm lint` | exit 0 |

## Deviations from Plan

None — plan executed exactly as written. Both tasks followed the prescribed amend-not-restore path (D-77-05/06/07).

## Threat Flags

None. FIX-02 is a documentation amendment plus a comment-only edit. No new data flows, no runtime behavior changes, no new network endpoints or trust boundaries.

## Self-Check

- [x] `.planning/milestones/v2.0-phases/999.5-client-pwa-onboarding-and-receipt-email/999.5-UI-SPEC.md` — modified and committed (55176e67)
- [x] `apps/client-pwa/src/routes/PaymentReturnScreen.jsx` — modified and committed (1b376be5)
- [x] "Accepted behavior" label present and greppable in D-09 region
- [x] Summary item #8 no longer claims chip is required
- [x] No behavioral change to PaymentSucceededView

## Self-Check: PASSED
