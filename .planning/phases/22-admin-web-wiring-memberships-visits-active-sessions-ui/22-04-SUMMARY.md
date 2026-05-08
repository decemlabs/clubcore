---
phase: 22-admin-web-wiring-memberships-visits-active-sessions-ui
plan: 04
subsystem: ui
tags: [react, tanstack-router, tanstack-query, eslint, pattern-alpha, telegram-bot, fastapi]

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
  - D-5 Telegram bot days-remaining DM with owner-approved locked Russian strings (D-22-11)
  - create_visit_self_checkin returns tuple[VisitResponse, date] for handler computation

affects:
  - phase-23-and-beyond: Pattern α is the precedent for composing features at the route layer
  - apps/admin-web/eslint.config.js: new import/no-restricted-paths zone
  - apps/backend: visits service bot path now returns membership end_date alongside VisitResponse

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pattern α: feature composition at the route layer (features never import other features)"
    - "Colocated page component inside route file when it bridges multiple feature domains"
    - "ESLint import/no-restricted-paths zone enforcing Pattern α statically"
    - "verify-pattern-alpha.sh copies fixture to target path and inverts ESLint exit code"
    - "Service tuple return pattern: internal bot path returns (VisitResponse, date) without changing public HTTP schema"

key-files:
  created:
    - apps/admin-web/src/routes/_protected/clients.$clientId.tsx
    - apps/admin-web/src/features/clients/components/ClientProfileCard.tsx
    - apps/admin-web/src/features/memberships/components/MembershipsBlock.test.tsx
    - apps/admin-web/src/__fixtures/features/illegal-cross-feature-import.ts
    - apps/admin-web/scripts/verify-pattern-alpha.sh
    - apps/backend/tests/integration/telegram_bot/test_checkin_dm_days_remaining.py
  modified:
    - apps/admin-web/src/features/memberships/components/MembershipsBlock.tsx
    - apps/admin-web/src/features/clients/components/ClientsTable.tsx
    - apps/admin-web/src/features/clients/components/ClientsTable.rbac.test.tsx
    - apps/admin-web/eslint.config.js
    - apps/backend/app/integrations/telegram/handlers.py
    - apps/backend/app/modules/visits/service.py
    - apps/backend/tests/integration/telegram_bot/test_checkin_handler.py

key-decisions:
  - "ClientDetailPage is colocated INSIDE the route file clients.$clientId.tsx — NOT under features/clients/components/ — because it imports from features/memberships and features/visits (Architecture Rule 5 / Pattern α)"
  - "DataGrid onRowClick prop used for row navigation (already supported by reui DataGrid, applies cursor-pointer automatically)"
  - "verify-pattern-alpha.sh copies fixture to src/features/clients/__test__/ so ESLint evaluates it as a features/clients file (target glob match)"
  - "D-22-11 owner sign-off RECEIVED: Option B (special-case zero). Two locked Russian strings: _DM_CHECKIN_OK_WITH_DAYS for days_remaining>0, _DM_CHECKIN_OK_LAST_DAY for days_remaining==0 (INCLUSIVE end_date per Phase 15)"
  - "_create_visit_with_anti_fraud returns tuple[VisitResponse, date] (membership.end_date); create_visit_reception discards the date; VisitResponse public schema is unchanged — no openapi regen needed"

patterns-established:
  - "Pattern α: composition of multiple feature blocks happens at the route layer only"
  - "ESLint zone + negative fixture + shell verification script as the enforcement triad"
  - "Service tuple return for internal channels: bot path gets extra data without polluting the public HTTP schema"

requirements-completed: [FE-07, FE-10, FE-11]

# Metrics
duration: ~90min
completed: 2026-05-08
---

# Phase 22 Plan 04: Pattern α route + ESLint enforcement + D-3 badge + D-5 Telegram DM Summary

**Pattern α client-detail route with Promise.all loader, ESLint cross-feature import zone, D-3 expiry badge wiring, ClientsTable row navigation, and D-5 Telegram bot days-remaining DM with owner-approved locked Russian strings**

## Performance

- **Duration:** ~90 min (Tasks 1 + 2 + 3)
- **Started:** 2026-05-08T12:07:51Z
- **Completed:** 2026-05-08
- **Tasks:** 3/3 completed
- **Files created/modified:** 15

## Accomplishments

- **Task 1 (D-3 badge + row navigation):** MembershipsBlock wires `todayMSK` IMPORTED from `@/shared/i18n/date`; destructive badge renders when `status==='active' && endDate===todayMSK()`; ClientsTable passes `onRowClick` to DataGrid navigating to `/clients/$clientId`; Pencil + Trash2 buttons call `e.stopPropagation()` — 7 tests pass (4 badge + 3 navigation/stopPropagation)
- **Task 2 (Pattern α route + ESLint zone):** New route `clients.$clientId.tsx` with `Promise.all([ensureQueryData x3])` loader, colocated `ClientDetailPage` composing `ClientProfileCard + MembershipsBlock + RecentVisitsBlock` in `space-y-8` stack; `ClientProfileCard` lives under `features/clients` (client data only, no forbidden imports); ESLint Pattern α zone added; `illegal-cross-feature-import.ts` fixture created; `verify-pattern-alpha.sh` proves zone fires (exit 0, PASS printed)
- **Task 3 (D-5 DM days-remaining):** Owner sign-off received (Option B — special-case zero). `create_visit_self_checkin` now returns `tuple[VisitResponse, date]`; `checkin_handler` destructures and branches on `days_remaining==0` to select locked last-day string vs. days-remaining string with `{days_remaining}` interpolation. 3 integration tests pass (5 days, 1 day, 0 days). All existing 10 telegram bot tests continue to pass. No openapi/schema.d.ts drift.

## Task Commits

1. **Task 1: D-3 badge wiring + ClientsTable row navigation** - `bb0b344` (feat)
2. **Task 2: Pattern α route + ClientProfileCard + ESLint zone** - `c641e62` (feat)
3. **Task 3: D-5 Telegram bot DM days-remaining** - `26a7a18` (feat)

**Plan metadata:** See final docs commit (docs(22-04): complete plan)

## D-22-11 Owner Sign-Off (Task 3 — RECEIVED)

**Status: RECEIVED — Option B (special-case zero)**

### Locked Russian strings

```python
# days_remaining > 0:
_DM_CHECKIN_OK_WITH_DAYS = "✅ Отмечено. Абонемент действует ещё {days_remaining} дн."

# days_remaining == 0 (last valid day, INCLUSIVE end_date per Phase 15):
_DM_CHECKIN_OK_LAST_DAY = "✅ Отмечено. Сегодня — последний день абонемента."
```

These strings are LOCKED — exact wording, punctuation, em-dash (—), and `{days_remaining}` interpolation token are owner-approved and must not be altered.

### days_remaining boundary behavior

| end_date | days_remaining | DM sent |
|----------|---------------|---------|
| today + 5 | 5 | "✅ Отмечено. Абонемент действует ещё 5 дн." |
| today + 1 | 1 | "✅ Отмечено. Абонемент действует ещё 1 дн." |
| today (INCLUSIVE) | 0 | "✅ Отмечено. Сегодня — последний день абонемента." |

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
- `apps/backend/app/integrations/telegram/handlers.py` - Replaced _DM_CHECKIN_OK with two locked strings + days_remaining branch
- `apps/backend/app/modules/visits/service.py` - _create_visit_with_anti_fraud + create_visit_self_checkin return tuple[VisitResponse, date]
- `apps/backend/tests/integration/telegram_bot/test_checkin_handler.py` - Updated 3 happy-path DM assertions for new format
- `apps/backend/tests/integration/telegram_bot/test_checkin_dm_days_remaining.py` - NEW: 3 boundary-case integration tests

## Architecture confirmation

- **ClientDetailPage lives in route file**: `grep -q "function ClientDetailPage" apps/admin-web/src/routes/_protected/clients.$clientId.tsx` — confirmed. No `ClientDetailPage.tsx` under `features/clients/components/`.
- **Pattern α isolation**: `! grep -rE "from '@/features/(memberships|visits)'" apps/admin-web/src/features/clients/` — confirmed, no matches.
- **todayMSK IMPORTED**: `grep -q "import.*todayMSK.*from.*@/shared/i18n/date" apps/admin-web/src/features/memberships/components/MembershipsBlock.tsx` — confirmed.
- **No openapi regen**: `git diff --exit-code apps/backend/openapi.json packages/api-client/src/schema.d.ts` — exit 0, no drift. VisitResponse public schema unchanged; only the internal bot service path extended.
- **DataGrid row-click mechanism**: `onRowClick` prop (Option A preferred per plan) — DataGrid applies `cursor-pointer` and `hover:bg-muted/40` automatically.
- **ESLint Pattern α verification**: `bash apps/admin-web/scripts/verify-pattern-alpha.sh` → "PASS: Pattern α ESLint zone fires correctly" (exit 0).
- **Telegram DM test path**: `apps/backend/tests/integration/telegram_bot/test_checkin_dm_days_remaining.py` — co-located with existing harness, 3 tests pass.
- **days_remaining strings present**: `grep -q "Сегодня — последний день абонемента" handlers.py` → 0; `grep -q "Абонемент действует ещё" handlers.py` → 0; `grep -q "{days_remaining}" handlers.py` → 0.

## Decisions Made

- ClientDetailPage colocated in route file, not features/clients (Pattern α / Architecture Rule 5)
- DataGrid onRowClick prop chosen over Link-in-cell (cleaner API, already supported)
- D-22-11 Option B: two separate locked strings for zero vs. non-zero days_remaining
- Service tuple return `tuple[VisitResponse, date]` chosen over extra DB query in handler (no round-trip, avoids handler touching DB directly)
- `create_visit_reception` discards the `_end_date` component — reception path is unaffected

## Deviations from Plan

### Auto-fixed Issues

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

None — all three shipped blocks (MembershipsBlock, RecentVisitsBlock, ClientProfileCard) are wired to real mock data via TanStack Query hooks. Telegram DM now sends a real computed days_remaining value.

## Threat Flags

None beyond what is documented in the plan's threat_model. Single integer `days_remaining` in the DM does not reveal membership_id, end_date, or pricing (T-22-14 mitigated).

## Self-Check: PASSED

- `apps/admin-web/src/routes/_protected/clients.$clientId.tsx` — FOUND
- `apps/admin-web/src/features/clients/components/ClientProfileCard.tsx` — FOUND
- `apps/admin-web/src/features/memberships/components/MembershipsBlock.test.tsx` — FOUND
- `apps/admin-web/src/__fixtures/features/illegal-cross-feature-import.ts` — FOUND
- `apps/admin-web/scripts/verify-pattern-alpha.sh` — FOUND
- `apps/backend/tests/integration/telegram_bot/test_checkin_dm_days_remaining.py` — FOUND
- Commits `bb0b344`, `c641e62`, `26a7a18` — FOUND (git log confirms)
- `git diff --exit-code apps/backend/openapi.json packages/api-client/src/schema.d.ts` — exit 0

## Issues Encountered

None beyond the expected sign-off gate for Task 3 (D-22-11), which was resolved via the checkpoint handshake.

## Next Phase Readiness

- Pattern α is established and ESLint-enforced — future features composing multiple domains must use the route-layer pattern
- `/clients/$clientId` route is live in routeTree.gen.ts with full prefetch
- D-5 Telegram DM days-remaining is deployed; locked strings are owner-approved
- FE-07, FE-10 (D-3 + D-5), and FE-11 are all closed

---
*Phase: 22-admin-web-wiring-memberships-visits-active-sessions-ui*
*Completed: 2026-05-08*
