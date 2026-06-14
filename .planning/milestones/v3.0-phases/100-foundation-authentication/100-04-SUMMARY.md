---
phase: 100-foundation-authentication
plan: "04"
subsystem: auth/rbac
tags: [rbac, can, registry, coming-soon, sidebar, session, role-badge, hide-for-future]

# Dependency graph
requires:
  - "100-03 (useSession hook, RequireAuth guard, MeData type)"
provides:
  - "apps/admin-app/src/shared/session/types.ts — Role union"
  - "apps/admin-app/src/shared/session/registry.ts — Resource + Action unions + RouteEntry + routeRegistry (admin-app adapted)"
  - "apps/admin-app/src/shared/session/can.ts — OWNER_ONLY (41 entries) + can() byte-parity with admin-web/permissions.py"
  - "apps/admin-app/src/shared/session/can.test.ts — 7 unit tests; owner-allows-all + reception-denied-matrix + 41-count"
  - "apps/backend/tests/integration/test_rbac_parity.py — _CAN_TS/_REGISTRY_TS repointed to admin-app; 4 parity assertions green"
  - "apps/admin-app/src/components/feedback/ComingSoon.tsx — shared hide-for-future placeholder (FND-04)"
  - "apps/admin-app/src/app/router.tsx — 8 deferred routes use <ComingSoon/> element"
  - "apps/admin-app/src/layouts/AppLayout/nav-items.ts — deferred nav items removed; ownerOnly flag added"
  - "apps/admin-app/src/layouts/AppLayout/AppSidebar.tsx — session-driven role pill + footer card + can()-gated nav"
  - "apps/admin-app/src/lib/format.ts — getInitials(fullName) helper"
affects:
  - "105 (admin-web deletion — RBAC re-home done here; parity test already at admin-app before Phase 105)"
  - "101-104 (all domain wiring assumes sidebar/nav is already role-aware)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "RBAC re-home mechanic (D-V30/ADMW-02 groundwork): admin-app becomes CISO-01 byte-parity target before Phase 105 deletes admin-web"
    - "ownerOnly flag on NavItem — gates Финансы/Отчёты via can() without overloading resource semantics"
    - "hide-for-future (FND-04): deferred routes render <ComingSoon/> static element; page files kept un-imported for future graduation"
    - "Least-privilege default: role='reception' while session.isPending (T-100-14 — no owner-item flash)"
    - "getInitials: first char of first 2 space-separated words, uppercase"

key-files:
  created:
    - "apps/admin-app/src/shared/session/types.ts — Role = 'owner' | 'reception'"
    - "apps/admin-app/src/shared/session/registry.ts — Resource + Action unions verbatim; routeRegistry admin-app adapted"
    - "apps/admin-app/src/shared/session/can.ts — 41 OWNER_ONLY entries + can(); byte-parity with admin-web"
    - "apps/admin-app/src/shared/session/can.test.ts — 7 vitest assertions"
    - "apps/admin-app/src/components/feedback/ComingSoon.tsx — hide-for-future placeholder"
  modified:
    - "apps/backend/tests/integration/test_rbac_parity.py — _CAN_TS/_REGISTRY_TS repointed admin-web → admin-app"
    - "apps/admin-app/src/app/router.tsx — 8 deferred routes get element: <ComingSoon/>; active routes keep lazy:"
    - "apps/admin-app/src/layouts/AppLayout/nav-items.ts — deferred items removed; ownerOnly field added; Финансы/Отчёты flagged"
    - "apps/admin-app/src/layouts/AppLayout/AppSidebar.tsx — useSession + can() + role pill + footer skeleton + real fullName"
    - "apps/admin-app/src/lib/format.ts — getInitials added"

key-decisions:
  - "D-100-04-OWNERFLAG: Gate ONLY Финансы+Отчёты via ownerOnly=true flag on NavItem rather than mapping all items to Resource values. UI-SPEC is authoritative on which items are visible to all roles — mapping Касса/Настройки/Посещаемость/Загруженность to their backend resources would incorrectly hide them from reception (e.g. 'settings' is OWNER_ONLY for view). ownerOnly flag stays aligned with the OWNER_ONLY matrix via can()."
  - "D-100-04-RBAC-REHOME: admin-app is now the CISO-01 parity source (ADMW-02 groundwork). The backend parity test (_CAN_TS/_REGISTRY_TS) repointed from admin-web to admin-app. admin-web untouched — deleted in Phase 105, by which time the test already points at admin-app."
  - "D-100-04-LEASTPRIV-DEFAULT: While session.isPending, role defaults to 'reception' (not 'owner'). Owner-only items are absent by default, revealed only after session.data confirms 'owner'. T-100-14 mitigation."

requirements-completed: [FND-04, AUTH-03]

# Metrics
duration: ~6min
completed: 2026-06-13
---

# Phase 100 Plan 04: RBAC Re-home + Hide-for-future + Role Visibility Summary

**RBAC byte-parity ported to admin-app (41 OWNER_ONLY entries), CISO-01 parity test repointed, ComingSoon placeholder wired to deferred routes, sidebar shows real fullName/role with skeleton and can()-gates Финансы/Отчёты for reception**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-06-13T09:14:47Z
- **Completed:** 2026-06-13T09:20:48Z
- **Tasks:** 3
- **Files created/modified:** 10

## Accomplishments

- `shared/session/types.ts` — `Role = 'owner' | 'reception'` type
- `shared/session/registry.ts` — `Resource` union (26 values), `Action` union (9 values), `RouteEntry` interface, and `routeRegistry` — all verbatim from admin-web except `routeRegistry` adapted to admin-app's `ROUTES` constants. Both type unions byte-match the backend `permissions.py` StrEnum values (verified by parity test)
- `shared/session/can.ts` — `OWNER_ONLY` (41 entries) + `can()` copied verbatim from admin-web; 41 unique pairs confirmed by node inline check and vitest
- `shared/session/can.test.ts` — 7 assertions: owner-allows-all OWNER_ONLY pairs, reception-denied-all-41, reception-retained non-owner pairs (create/memberships, check_in/visits, view/clients), 41-count sanity, Action/Resource type coverage
- `apps/backend/tests/integration/test_rbac_parity.py` — `_CAN_TS` and `_REGISTRY_TS` path constants repointed from `admin-web` to `admin-app`; docstring updated to document the RBAC re-home. All 4 parity assertions pass: owner_only_pairs_match, resource_values_match, action_values_match, owner_only_count_is_forty
- `components/feedback/ComingSoon.tsx` — FND-04 placeholder: full-height centered flex, Clock ScreenIcon with accent tone, «Раздел в разработке» heading, sub-text with correct Russian copy, animate-in, no action button, no props
- `router.tsx` — 8 deferred routes swapped to `element: <ComingSoon/>`: branches, branch(), messages, notifications, systemSettings, roles, trash, importExport. Active routes (dashboard, clients, client, schedule, plans, trainers, trainer, cashbox, reports, attendance, load, finance, settings, audit) keep `lazy:`. RequireAuth wrapper + 404 catch-all intact
- `nav-items.ts` — removed Сообщения, Уведомления, Филиалы (deferred — gone for all roles); added `ownerOnly?: boolean` field; Финансы + Отчёты flagged `ownerOnly: true`
- `AppSidebar.tsx` — `useSession()` wired; role pill shows «Владелец» (emerald) / «Ресепшн» (neutral) / hidden while pending (T-100-14); nav filtered via `can()` — ownerOnly items absent for reception; footer card renders real `fullName` + localized role label with gradient avatar; loading state uses `Skeleton h-3 w-24` + `Skeleton h-2.5 w-16`; hardcoded "Маша Костина" and `APP_ROLE_LABEL` removed
- `lib/format.ts` — `getInitials(fullName)`: split on whitespace, take first char of first 2 words, uppercase; handles empty/single-word edge cases

## Task Commits

1. **Task 1: Port RBAC (types/can/registry) into admin-app and repoint the CISO-01 parity test** — `48a44895` (feat)
2. **Task 2: ComingSoon placeholder + swap deferred routes + remove deferred nav items** — `1873094b` (feat)
3. **Task 3: Session-driven sidebar — role badge, footer card, can()-gated nav** — `f193a5aa` (feat)

## Files Created/Modified

- `apps/admin-app/src/shared/session/types.ts` — Role type (new)
- `apps/admin-app/src/shared/session/registry.ts` — Resource/Action unions + routeRegistry (new)
- `apps/admin-app/src/shared/session/can.ts` — 41 OWNER_ONLY + can() (new)
- `apps/admin-app/src/shared/session/can.test.ts` — 7 vitest assertions (new)
- `apps/backend/tests/integration/test_rbac_parity.py` — path constants repointed (modified)
- `apps/admin-app/src/components/feedback/ComingSoon.tsx` — hide-for-future placeholder (new)
- `apps/admin-app/src/app/router.tsx` — 8 deferred routes → ComingSoon element (modified)
- `apps/admin-app/src/layouts/AppLayout/nav-items.ts` — deferred removed, ownerOnly added (modified)
- `apps/admin-app/src/layouts/AppLayout/AppSidebar.tsx` — session-driven (modified)
- `apps/admin-app/src/lib/format.ts` — getInitials added (modified)

## Decisions Made

- **D-100-04-OWNERFLAG**: Gate ONLY Финансы+Отчёты via `ownerOnly=true` flag on NavItem rather than mapping all items to Resource values. UI-SPEC is authoritative on which items are visible to all roles — mapping Касса/Настройки to their backend resources would incorrectly hide them from reception ('view'/'settings' and 'view'/'payments' are both in OWNER_ONLY). The ownerOnly flag uses `can()` under the hood so the parity matrix remains the single authority.
- **D-100-04-RBAC-REHOME**: admin-app is now the CISO-01 parity source (ADMW-02 groundwork). Backend parity test repointed admin-web → admin-app. admin-web left untouched (deleted in Phase 105, by which time this test already reads admin-app).
- **D-100-04-LEASTPRIV-DEFAULT**: While `session.isPending`, role defaults to `'reception'` (least privilege). Owner-only items absent by default, revealed only after session resolves to `'owner'`. T-100-14 mitigation against role flash.

## Deviations from Plan

None — plan executed exactly as written. The ownerOnly flag approach for nav gating (vs overloading `resource`) was explicitly described in the plan's Task 2 action section as the correct reconciliation.

## Known Stubs

None — `ComingSoon.tsx` is intentional (FND-04 hide-for-future, not a data stub). The sidebar renders real session data from `/auth/me`. No hardcoded values remain in wired paths.

## Threat Surface Scan

All mitigations from the plan's threat model implemented:

| Threat ID | Mitigation | Status |
|-----------|------------|--------|
| T-100-11 | OWNER_ONLY (41) + Resource/Action unions byte-parity; parity test repointed and green | implemented |
| T-100-12 | can() gates sidebar nav as defense-in-depth; backend enforces server-side (403 → ErrorPage) | implemented |
| T-100-13 | Deferred routes render static ComingSoon — no data fetch, no crash possible | implemented |
| T-100-14 | role defaults to 'reception' while session.isPending; pill hidden (no owner-item flash) | implemented |

No new security-relevant surface beyond what the plan's threat model covers.

## Self-Check: PASSED

Files verified present:
- `apps/admin-app/src/shared/session/types.ts` — FOUND
- `apps/admin-app/src/shared/session/registry.ts` — FOUND
- `apps/admin-app/src/shared/session/can.ts` — FOUND
- `apps/admin-app/src/shared/session/can.test.ts` — FOUND
- `apps/admin-app/src/components/feedback/ComingSoon.tsx` — FOUND
- `apps/admin-app/src/app/router.tsx` — FOUND (ComingSoon wired)
- `apps/admin-app/src/layouts/AppLayout/nav-items.ts` — FOUND (deferred removed, ownerOnly added)
- `apps/admin-app/src/layouts/AppLayout/AppSidebar.tsx` — FOUND (session-driven)
- `apps/admin-app/src/lib/format.ts` — FOUND (getInitials added)
- `apps/backend/tests/integration/test_rbac_parity.py` — FOUND (repointed)

Commits verified:
- `48a44895` — Task 1 (RBAC port + parity repoint)
- `1873094b` — Task 2 (ComingSoon + router + nav-items)
- `f193a5aa` — Task 3 (AppSidebar session-driven)

Tests: 99/99 passing. Typecheck: clean. Lint: clean. Parity test: 4/4 passing.
