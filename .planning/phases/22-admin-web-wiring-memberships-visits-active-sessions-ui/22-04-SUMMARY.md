---
phase: 22-admin-web-wiring-memberships-visits-active-sessions-ui
plan: 04
subsystem: ui
tags: [react, tanstack-router, tanstack-query, eslint, pattern-alpha, telegram-bot]

# Dependency graph
requires:
  - phase: 22-02
    provides: MembershipsBlock component, membershipsKeys, useMembershipsByClient hook
  - phase: 22-03
    provides: RecentVisitsBlock component, visitsKeys, todayMSK() helper in @/shared/i18n/date

provides:
  - Pattern α route at /clients/$clientId with Promise.all(ensureQueryData) loader
  - Colocated ClientDetailPage composing three feature blocks at the route layer
  - ClientProfileCard under features/clients (client data only, no cross-feature imports)
  - ESLint Pattern α zone blocking features/clients from importing features/memberships or features/visits
  - Negative-test fixture + verify-pattern-alpha.sh script proving the zone fires
  - D-3 destructive badge in MembershipsBlock (imports todayMSK from 22-03, not redefined)
  - ClientsTable row navigation to /clients/$clientId with stopPropagation on action buttons

affects:
  - phase-23-and-beyond: Pattern α is the precedent for composing features at the route layer
  - apps/admin-web/eslint.config.js: new import/no-restricted-paths zone

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pattern α: feature composition at the route layer (features never import other features)"
    - "Colocated page component inside route file when it bridges multiple feature domains"
    - "ESLint import/no-restricted-paths zone enforcing Pattern α statically"
    - "verify-pattern-alpha.sh copies fixture to target path and inverts ESLint exit code"

key-files:
  created:
    - apps/admin-web/src/routes/_protected/clients.$clientId.tsx
    - apps/admin-web/src/features/clients/components/ClientProfileCard.tsx
    - apps/admin-web/src/features/memberships/components/MembershipsBlock.test.tsx
    - apps/admin-web/src/__fixtures/features/illegal-cross-feature-import.ts
    - apps/admin-web/scripts/verify-pattern-alpha.sh
  modified:
    - apps/admin-web/src/features/memberships/components/MembershipsBlock.tsx
    - apps/admin-web/src/features/clients/components/ClientsTable.tsx
    - apps/admin-web/src/features/clients/components/ClientsTable.rbac.test.tsx
    - apps/admin-web/eslint.config.js

key-decisions:
  - "ClientDetailPage is colocated INSIDE the route file clients.$clientId.tsx — NOT under features/clients/components/ — because it imports from features/memberships and features/visits (Architecture Rule 5 / Pattern α)"
  - "DataGrid onRowClick prop used for row navigation (already supported by reui DataGrid, applies cursor-pointer automatically)"
  - "verify-pattern-alpha.sh copies fixture to src/features/clients/__test__/ so ESLint evaluates it as a features/clients file (target glob match)"
  - "D-22-11 owner sign-off PENDING — Task 3 halted at checkpoint; awaiting owner approval on Russian DM string"

patterns-established:
  - "Pattern α: composition of multiple feature blocks happens at the route layer only"
  - "ESLint zone + negative fixture + shell verification script as the enforcement triad"

requirements-completed: [FE-07, FE-11]
# NOTE: FE-10 (D-3 + D-5) partially completed: D-3 badge shipped; D-5 backend DM awaiting owner sign-off

# Metrics
duration: 45min
completed: 2026-05-08
---

# Phase 22 Plan 04: Pattern α route composition + ESLint enforcement + D-3 badge Summary

**Pattern α client-detail route with Promise.all loader, ESLint cross-feature import zone enforcement, D-3 expiry badge, and ClientsTable row navigation — Task 3 (D-5 Telegram DM) paused at owner sign-off checkpoint**

## Performance

- **Duration:** ~45 min (Tasks 1 + 2)
- **Started:** 2026-05-08T12:07:51Z
- **Completed:** 2026-05-08T12:53:00Z (Tasks 1 + 2 only)
- **Tasks:** 2/3 completed (Task 3 paused at owner sign-off gate)
- **Files created/modified:** 8

## Accomplishments

- **Task 1 (D-3 badge + row navigation):** MembershipsBlock wires `todayMSK` IMPORTED from `@/shared/i18n/date`; destructive badge renders when `status==='active' && endDate===todayMSK()`; ClientsTable passes `onRowClick` to DataGrid navigating to `/clients/$clientId`; Pencil + Trash2 buttons call `e.stopPropagation()` — 7 tests pass (4 badge + 3 navigation/stopPropagation)
- **Task 2 (Pattern α route + ESLint zone):** New route `clients.$clientId.tsx` with `Promise.all([ensureQueryData x3])` loader, colocated `ClientDetailPage` composing `ClientProfileCard + MembershipsBlock + RecentVisitsBlock` in `space-y-8` stack; `ClientProfileCard` lives under `features/clients` (client data only, no forbidden imports); ESLint Pattern α zone added; `illegal-cross-feature-import.ts` fixture created; `verify-pattern-alpha.sh` proves zone fires (exit 0, PASS printed)
- **Task 3 (D-5 DM days-remaining):** PAUSED — owner sign-off required on Russian DM string; see checkpoint section below

## Task Commits

1. **Task 1: D-3 badge wiring + ClientsTable row navigation** - `bb0b344` (feat)
2. **Task 2: Pattern α route + ClientProfileCard + ESLint zone** - `c641e62` (feat)
3. **Task 3:** NOT YET COMMITTED — awaiting owner sign-off

## D-22-11 Owner Sign-Off Gate (Task 3 — PENDING)

**Status: PENDING — owner approval required before implementation**

The Telegram bot success DM `_DM_CHECKIN_OK` must be extended to include days remaining on the active membership. Per Phase 20 AUTH-TG-11 precedent, the executor cannot finalize copy without owner approval.

### Proposed locked constant

```
_DM_CHECKIN_OK = "✅ Отмечено. Абонемент действует ещё {days_remaining} дн."
```

### Boundary cases requiring owner decision

| Case | days_remaining | Rendered message | Issue? |
|------|---------------|------------------|--------|
| Normal | 5 | "✅ Отмечено. Абонемент действует ещё 5 дн." | None |
| Normal | 1 | "✅ Отмечено. Абонемент действует ещё 1 дн." | "1 дн." vs "1 день"? |
| Last valid day | 0 | "✅ Отмечено. Абонемент действует ещё 0 дн." | Odd Russian — "ещё 0 дн." |

**For days_remaining=0 (inclusive end_date, last valid day):**

Option A (current proposal): "✅ Отмечено. Абонемент действует ещё 0 дн." — grammatically odd in Russian.

Option B (boundary string): "✅ Отмечено. Сегодня — последний день абонемента." — clearer for the last day.

Option C (plural-aware): Use a Russian plural form helper:
- 0 дней, 1 день, 2-4 дня, 5-20 дней, 21 день, 22-24 дня, 25+ дней
- E.g.: "✅ Отмечено. Абонемент действует ещё {days_remaining} {plural(days_remaining, 'день','дня','дней')}."

**Executor awaits owner confirmation of Option A, B, or C (or a custom string).**

### Implementation plan (ready to execute after sign-off)

1. Change `create_visit_self_checkin` signature in `service.py` to return `tuple[VisitResponse, date]`
2. Update `checkin_handler` to destructure `(visit, membership_end_date)`, compute `days_remaining = max(0, (membership_end_date - today).days)`, and format the approved DM string
3. Create `tests/integration/telegram_bot/test_checkin_dm_days_remaining.py` with ≥3 tests (happy path N>0, boundary days_remaining=0, regression on rejection DMs)
4. Run: `uv run ruff check && uv run mypy app/integrations/telegram/ app/modules/visits/ && uv run pytest tests/integration/telegram_bot/test_checkin_dm_days_remaining.py -v`
5. No openapi.json / schema.d.ts regen needed (VisitResponse public shape unchanged — only the bot path changes)

## Files Created/Modified

- `apps/admin-web/src/features/memberships/components/MembershipsBlock.tsx` - Added todayMSK import + D-3 destructive badge
- `apps/admin-web/src/features/memberships/components/MembershipsBlock.test.tsx` - NEW: 4 tests for D-3 badge conditions
- `apps/admin-web/src/features/clients/components/ClientsTable.tsx` - Added onRowClick navigation + stopPropagation
- `apps/admin-web/src/features/clients/components/ClientsTable.rbac.test.tsx` - +4 navigation/stopPropagation tests
- `apps/admin-web/src/routes/_protected/clients.$clientId.tsx` - NEW: Pattern α route + colocated ClientDetailPage
- `apps/admin-web/src/features/clients/components/ClientProfileCard.tsx` - NEW: client profile header card
- `apps/admin-web/src/__fixtures/features/illegal-cross-feature-import.ts` - NEW: Pattern α negative-test fixture
- `apps/admin-web/eslint.config.js` - Added Pattern α import/no-restricted-paths zone
- `apps/admin-web/scripts/verify-pattern-alpha.sh` - NEW: ESLint zone verification script

## Architecture confirmation

- **ClientDetailPage lives in route file**: `grep -q "function ClientDetailPage" apps/admin-web/src/routes/_protected/clients.\$clientId.tsx` — confirmed. No `ClientDetailPage.tsx` under `features/clients/components/`.
- **Pattern α isolation**: `! grep -rE "from '@/features/(memberships|visits)'" apps/admin-web/src/features/clients/` — confirmed, no matches.
- **todayMSK IMPORTED**: `grep -q "import.*todayMSK.*from.*@/shared/i18n/date" apps/admin-web/src/features/memberships/components/MembershipsBlock.tsx` — confirmed.
- **No second openapi regen needed**: Task 3 not started yet; even after completion, VisitResponse public shape stays unchanged (only `create_visit_self_checkin` internal tuple return type changes).
- **DataGrid row-click mechanism**: `onRowClick` prop (Option A preferred per plan) — DataGrid applies `cursor-pointer` and `hover:bg-muted/40` automatically.
- **ESLint Pattern α verification**: `bash apps/admin-web/scripts/verify-pattern-alpha.sh` → "PASS: Pattern α ESLint zone fires correctly" (exit 0).
- **New telegram DM test path**: `apps/backend/tests/integration/telegram_bot/test_checkin_dm_days_remaining.py` — co-located with existing harness (to be created after sign-off).

## Deviations from Plan

**1. [Rule 2 - Missing Critical] Added beforeLoad guard to clients.$clientId route**
- **Found during:** Task 2
- **Issue:** The plan showed a loader but did not include `beforeLoad` for RBAC. The sibling `clients.tsx` route has a `beforeLoad` check. Without it, the detail page could be accessed by roles without `can(role, 'view', 'clients')`.
- **Fix:** Added `beforeLoad` with `can(role, 'view', 'clients')` redirect, matching the existing clients.tsx pattern.
- **Files modified:** `apps/admin-web/src/routes/_protected/clients.$clientId.tsx`
- **Committed in:** `c641e62` (part of Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 2 — missing RBAC guard)
**Impact on plan:** Security correctness. No scope creep.

## Known Stubs

None — both shipped blocks (MembershipsBlock, RecentVisitsBlock) are wired to real mock data via TanStack Query hooks. ClientProfileCard reads the loader-prefetched `useClient` result.

## Threat Flags

None beyond what is documented in the plan's threat_model. The route layer composition (legal boundary) does not introduce new trust boundaries.

## Self-Check: PARTIAL

Task 1 + 2:
- `apps/admin-web/src/routes/_protected/clients.$clientId.tsx` — FOUND
- `apps/admin-web/src/features/clients/components/ClientProfileCard.tsx` — FOUND
- `apps/admin-web/src/features/memberships/components/MembershipsBlock.test.tsx` — FOUND
- `apps/admin-web/src/__fixtures/features/illegal-cross-feature-import.ts` — FOUND
- `apps/admin-web/scripts/verify-pattern-alpha.sh` — FOUND
- Commits `bb0b344`, `c641e62` — FOUND (git log confirms)

Task 3: NOT STARTED — awaiting owner sign-off at CHECKPOINT REACHED.

## Issues Encountered

- None for Tasks 1 + 2.
- Task 3: Paused at mandatory owner sign-off gate (D-22-11). This is expected behavior per the plan.

## Next Phase Readiness

- Pattern α is established and ESLint-enforced — future features composing multiple domains must use the route-layer pattern
- `/clients/$clientId` route is live in routeTree.gen.ts
- Task 3 (D-5 Telegram DM) pending: needs owner approval on Russian string → implementation ready to run as continuation task

---
*Phase: 22-admin-web-wiring-memberships-visits-active-sessions-ui*
*Completed: 2026-05-08 (Tasks 1+2); Task 3 pending owner sign-off*
