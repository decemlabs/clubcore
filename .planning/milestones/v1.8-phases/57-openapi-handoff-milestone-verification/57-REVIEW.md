---
phase: 57-openapi-handoff-milestone-verification
reviewed: 2026-05-24T00:00:00Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - apps/backend/tests/integration/reports/test_reports_dst.py
  - packages/api-client/src/schema.contract.test.ts
findings:
  critical: 0
  warning: 0
  info: 3
  total: 3
status: issues_found
---

# Phase 57: Code Review Report

**Reviewed:** 2026-05-24T00:00:00Z
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found

## Summary

Reviewed the two hand-authored source files from the Phase 57 (v1.8) milestone-close handoff: the backend DST/MSK-boundary golden integration test and the vitest compile-time schema contract test.

Both files were traced against their underlying implementations to validate correctness rather than merely confirm presence:

- `test_reports_dst.py` was cross-checked against `app/modules/reports/repository.py` (the `(received_at AT TIME ZONE 'Europe/Moscow')::date` bucketing SQL and the `gym_date BETWEEN` daily filter), `service.py` (`_pivot_revenue_buckets` net-of-refund accumulation), `schemas.py` (the `netKopecks`/`period`/`daily[].date`/`daily[].count` camelCase contract and `ResponseData` `data` envelope), the Visit model's `uq_visits_client_id_gym_date` unique constraint and STORED GENERATED `gym_date`, and the `reports/conftest.py` + `memberships/conftest.py` fixture signatures. Every assertion path, fixture kwarg, and golden constant is consistent with the implementation. The two-distinct-clients choice in the visits test is required by the unique constraint, the net-of-refund arithmetic (`GROSS − REFUND + anchor`) matches the signed-sum pivot, and the boundary/anchor timestamps are correct (21:30Z = 00:30 MSK next day; 07:00Z = 10:00 MSK same day). `asyncio_mode = "auto"` makes the marker-free async tests valid, and `db_session` is provided by the top-level conftest.

- `schema.contract.test.ts` was cross-checked against the regenerated `schema.d.ts`: all 8 v1.8 paths (`/reports/{revenue,clients,visits}`, `/audit-log`, plus the 4 `.csv` variants) are present, so the `AssertNonNever<...>` guards resolve to `true` (not `never`) at compile time. The `_v18Checks` tuple has exactly 8 entries matching the `toHaveLength(8)` runtime assertion, and all prior milestone count blocks (10/36/11/5/4/2) remain byte-frozen.

No correctness, security, or data-loss defects were found. Three Info-level observations follow; none block the milestone.

## Info

### IN-01: Misleading docstring claim — test never produces two distinct MSK-day buckets

**File:** `apps/backend/tests/integration/reports/test_reports_dst.py:95-100`
**Issue:** The docstring of `test_dst_revenue_boundary_payment_buckets_to_next_msk_day` states the counter-anchor "proves the window produces TWO distinct MSK-day buckets". This is inaccurate: the boundary event (21:30Z on 01-01 = 00:30 MSK on 01-02) and the anchor (07:00Z on 01-02 = 10:00 MSK on 01-02) both bucket into the *same* MSK date (2026-01-02). The test even asserts the `2026-01-01` bucket is *absent* (lines 160-166). The anchor proves the report does not trivially collapse to the UTC date and that same-MSK-day events sum into one bucket — but it does not produce two distinct date buckets. The narrative contradicts the test's own assertions and could mislead a future maintainer (or the 57-03 runbook reader) into expecting a second bucket.
**Fix:** Reword to match the assertions, e.g. "Counter-anchor at 07:00 UTC (10:00 MSK) on the same MSK day proves the bucketing keys on the MSK calendar date (both events sum into the single 2026-01-02 bucket) rather than the UTC date." The module-level docstring at lines 8-9 ("two distinct MSK dates appear") is similarly inaccurate for this test and should be reconciled — distinct dates only appear if events are seeded on different MSK days, which this file does not do.

### IN-02: Magic number for the anchor payment amount

**File:** `apps/backend/tests/integration/reports/test_reports_dst.py:131,153`
**Issue:** The counter-anchor payment amount `10_000` is an inline literal used at insertion (line 131) and again in the assertion `NET_KOPECKS + 10_000` (line 153). The module elevates every other golden value to a named constant referenced by the 57-03 runbook (GROSS/REFUND/NET_KOPECKS), and the inline comment at line 131 even concedes it is "not a named constant". Duplicating the literal across insert and assertion invites drift if one site is edited without the other.
**Fix:** Promote to a module-level constant for symmetry and single-source-of-truth, e.g. `ANCHOR_KOPECKS: int = 10_000`, then use it at both sites (`amount_kopecks=ANCHOR_KOPECKS` and `== NET_KOPECKS + ANCHOR_KOPECKS`). Minor; the value is genuinely incidental, but consistency with the file's own constant discipline argues for it.

### IN-03: Stale/ambiguous phase references in test titles and comments

**File:** `packages/api-client/src/schema.contract.test.ts:354,420`
**Issue:** The v1.8 section header comment says "Phases 54-57" (line 354) while the corresponding `it(...)` title says "Phases 55-57" (line 420). The module-level docstring header at line 1 still reads "Phase 21 D-21-4" and "Sessions paths (Phase 23)". These divergent phase tags are cosmetic but make the file's provenance harder to audit at a milestone-close handoff whose explicit purpose is traceability.
**Fix:** Reconcile the two v1.8 phase ranges to a single accurate value (e.g. both "Phases 55-57", matching the runtime `it` title), so the section comment and test name agree. No behavioral impact.

---

_Reviewed: 2026-05-24T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
