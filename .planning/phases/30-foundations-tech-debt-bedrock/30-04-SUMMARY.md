---
phase: 30-foundations-tech-debt-bedrock
plan: 04
subsystem: admin-web/mock-services
tags:
  - frontend
  - mock-parity
  - tech-debt
  - admin-web
  - debt-05
requirements:
  - DEBT-05
dependency_graph:
  requires:
    - "v1.3 Phase 28 FE-11 status filter parity (existing test in memberships.read.test.ts:211-220 — still green)"
  provides:
    - "mock/memberships.list() honours query.status inside the expiring branch — full byte-paritet with the http adapter under VITE_API_MODE=mock"
    - "Two new DEBT-05 vitest specs lock the contract against future regressions"
  affects:
    - "/memberships page (admin-web): «Заморожен» pill + expiring=true combination now behaves identically in mock and http"
tech-stack:
  added: []
  patterns:
    - "Mock-service test setup: seed faker.seed=42 baseline, then mutate via saveDB() to inject deterministic rows for status taxonomy coverage gaps"
    - "In-code rationale comment near tech-debt fixes — bug-vs-verbatim-wording mismatch documented at the site of the fix"
key-files:
  created: []
  modified:
    - apps/admin-web/src/shared/api/services/mock/memberships.ts
    - apps/admin-web/src/shared/api/services/mock/memberships.read.test.ts
decisions:
  - "Inject frozen rows via saveDB rather than using memberships.freeze() API in setup — avoids coupling DEBT-05 fix tests to the freeze write-path, which has its own preconditions (active status, freezeDaysRemaining > 0). Direct DB mutation is the existing pattern for mock-mode tests that need taxonomy coverage beyond what faker.seed=42 produces."
  - "Keep the longer 6-line DEBT-05 rationale comment (rather than the 1-line minimum) — the bug-vs-verbatim-REQ-wording semantic mismatch is non-obvious and re-reading the REQ in isolation would mislead future maintainers into thinking the pill path itself was broken."
metrics:
  duration_minutes: 4
  tasks_completed: 1
  files_modified: 2
  files_created: 0
  tests_added: 2
  completed: 2026-05-14T12:35:15Z
---

# Phase 30 Plan 04: DEBT-05 Mock Memberships Parity — Summary

**One-liner:** Fixed `mock/memberships.list()` `if (query.expiring)` branch to respect `query.status` (was hardcoded `m.status === 'active'`), closing v1.3 deferred mock-parity gap; added 2 vitest specs (status×expiring=true regression-guard + frozen-pill canary) + in-code DEBT-05 rationale comment.

## Outcome

Plan 30-04 executed atomically in a single commit. The one-liner fix replaces the hardcoded `'active'` literal with `query.status ?? 'active'` inside the expiring branch, so the «Заморожен» pill combined with the expiring filter no longer silently returns zero rows under `VITE_API_MODE=mock`. Mock and http modes are now byte-paritet on this surface.

## Exact Change

**File:** `apps/admin-web/src/shared/api/services/mock/memberships.ts` (`list()` method, expiring branch)

**Before:**
```typescript
if (query.expiring) {
  const within = query.within ?? 7
  const todayStr = todayMSK()
  const cutoff = new Date(todayStr)
  cutoff.setUTCDate(cutoff.getUTCDate() + (within - 1))
  const cutoffStr = cutoff.toISOString().slice(0, 10)
  const items = all.filter(
    (m) => m.status === 'active' && m.endDate >= todayStr && m.endDate <= cutoffStr,
  )
  return { items, total: items.length, page: 1, pageSize: Math.max(1, items.length) }
}
```

**After:**
```typescript
if (query.expiring) {
  const within = query.within ?? 7
  const todayStr = todayMSK()
  const cutoff = new Date(todayStr)
  cutoff.setUTCDate(cutoff.getUTCDate() + (within - 1))
  const cutoffStr = cutoff.toISOString().slice(0, 10)
  // DEBT-05: respect query.status across expiring branch (was hardcoded 'active').
  // The verbatim REQ wording mentions the «Заморожен» pill no-op, but that path
  // (status=frozen, expiring=false) already works via the early `if (query.status)`
  // filter above. The actual bug is the status+expiring=true combination where the
  // expiring branch hardcoded `m.status === 'active'` and overrode the user's status
  // filter. The fix respects query.status here too. Phase 30 / v1.3 Phase 28 gap closure.
  const wantedStatus = query.status ?? 'active'
  const items = all.filter(
    (m) => m.status === wantedStatus && m.endDate >= todayStr && m.endDate <= cutoffStr,
  )
  return { items, total: items.length, page: 1, pageSize: Math.max(1, items.length) }
}
```

The in-code rationale comment is present (WARNING #3 fix — see "Semantic-Mismatch Note" below).

## Tests Added

Two new vitest specs appended to `apps/admin-web/src/shared/api/services/mock/memberships.read.test.ts` (inside the existing `describe('mock/memberships RBAC + shape', ...)` block, after the Phase 28 FE-11 spec):

1. **`list applies query.status inside the expiring branch (DEBT-05)`** — load-bearing regression-guard for the actual fix. Setup injects one `status='frozen'` row and one `status='active'` row, both inside the default 7-day expiring window, via `saveDB`. Calls `memberships.list({ expiring: true, status: 'frozen' })` and asserts the result contains the frozen row, excludes the active row, and every item has `status==='frozen'`. Also asserts that the no-status call still defaults to `status='active'` (back-compat).

2. **`list({ status: "frozen", expiring: false }) returns only frozen memberships (DEBT-05)`** — canary for the verbatim DEBT-05 REQ wording (the «Заморожен» pill scenario). Setup injects one frozen row via `saveDB` (faker.seed=42 produces no frozen rows). Asserts `items.length > 0` and `every(m.status === 'frozen')`. This test would fail if a future "simplification" removed the early `if (query.status)` filter at lines 38-40.

## Verification

| Check | Result |
|-------|--------|
| `pnpm vitest run src/shared/api/services/mock/memberships.read.test.ts` | 18/18 pass (16 existing + 2 new DEBT-05) |
| `pnpm vitest run` (full admin-web suite) | 235/235 pass across 41 files |
| `pnpm typecheck` | clean (no errors) |
| `pnpm lint` | clean (0 errors; 2 pre-existing warnings in unrelated files) |
| `grep -c "DEBT-05" memberships.ts` | 1 (≥1 required) |
| `grep -c "respect query.status" memberships.ts` | 1 (≥1 required) |
| `grep -c "query.status ?? 'active'" memberships.ts` | 1 (≥1 required) |
| `grep -c "m.status === 'active' && m.endDate >= todayStr" memberships.ts` | 0 (must be 0 — hardcoded literal gone) |
| `grep -c "wantedStatus" memberships.ts` | 2 (≥2 required — declaration + usage) |
| `grep -c "DEBT-05" memberships.read.test.ts` | 4 (≥2 required — two `it()` blocks plus comments) |
| `MembershipsListPage.frozen.test.tsx` regression | 4/4 still green |

## Semantic-Mismatch Note (WARNING #3 from Iteration-0 checker)

> "DEBT-05 verbatim wording says «Заморожен» pill must be a no-op no longer.
> Analysis: the pill scenario (`status=frozen, expiring=false`) ALREADY works via
> the early `if (query.status)` filter at lines 38-40 — pre-existing correct
> behavior. The actual bug fixed by Plan 04 is the `status + expiring=true`
> combination where the expiring branch hardcoded `m.status === 'active'` and
> overrode the user's status filter. BOTH the verbatim REQ wording AND the
> actual bug are now covered by the test suite: test 1 = actual fix verification
> (status+expiring=true respects query.status); test 2 = regression-guard for
> the pre-existing pill behavior (status=frozen, expiring=false)."

An in-code rationale comment was added to `mock/memberships.ts` next to the changed line so this mismatch is discoverable from code without reading this SUMMARY (the longer 6-line variant rather than the 1-line minimum — the semantic context is non-trivial and worth keeping inline).

## «Заморожен» Pill — Mock vs HTTP Parity

After this fix, the following combinations behave identically under `VITE_API_MODE=mock` and `VITE_API_MODE=http`:

| Query | Mock (after fix) | HTTP |
|-------|------------------|------|
| `{ status: 'frozen' }` | only frozen rows | only frozen rows |
| `{ status: 'frozen', expiring: false }` | only frozen rows | only frozen rows |
| `{ status: 'frozen', expiring: true }` | only frozen rows inside the window | only frozen rows inside the window |
| `{ status: 'active', expiring: true }` | only active rows inside the window (unchanged) | only active rows inside the window |
| `{ expiring: true }` (no status) | only active rows inside the window (back-compat) | only active rows inside the window |

## v1.3 Deferred Items Table — DEBT-05 Resolution

`.planning/STATE.md` "Deferred Items" table currently has:

| Category | Item | Status | Source | Resolution |
|----------|------|--------|--------|-----------|
| verification_gap | Phase 28 — `apps/admin-web/src/shared/api/services/mock/memberships.ts` `list()` does not filter by `query.status` | scheduled-v1.4 | v1.3 close | Phase 30 / DEBT-05 (one-liner + parity tests) |

Will be marked **resolved** in the post-plan STATE.md update. DEBT-05 row in `.planning/REQUIREMENTS.md` will be checked off (`[x]`).

## Deviations from Plan

None — plan executed exactly as written. The two test setups required `saveDB`-based row injection (anticipated and documented in the plan under "Verify seeded DB has both active and frozen memberships"). Selected option (b) — direct DB mutation — over option (a) freeze() API because it avoids coupling DEBT-05 fix tests to the freeze write-path's own preconditions.

## Files Modified

- `apps/admin-web/src/shared/api/services/mock/memberships.ts` — one-liner fix in `list()` expiring branch + 6-line DEBT-05 rationale comment.
- `apps/admin-web/src/shared/api/services/mock/memberships.read.test.ts` — 2 new `it()` blocks (DEBT-05) + `saveDB`/`todayMSK`/`Membership`/`MembershipId` imports added.

## Commits

| Hash | Message |
|------|---------|
| `dd69b21` | `fix(30-04): mock memberships.list respects query.status in expiring branch (DEBT-05)` |

## Self-Check: PASSED

- File `apps/admin-web/src/shared/api/services/mock/memberships.ts` — FOUND (modified)
- File `apps/admin-web/src/shared/api/services/mock/memberships.read.test.ts` — FOUND (modified)
- Commit `dd69b21` — FOUND in `git log`
- All acceptance grep gates pass (verified above)
- All tests pass (18/18 focused, 235/235 full suite)
- `pnpm typecheck` + `pnpm lint` clean
