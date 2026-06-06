---
phase: 86-gym-info-cms
plan: "03"
subsystem: client-pwa-gym-info
tags: [gym-info, pwa-wiring, react-query, vitest, gym-01]
dependency_graph:
  requires:
    - GET /api/v1/client/gym endpoint (86-02)
    - GymInfoResponse schema with camelCase wire (86-01)
    - clientRequest typed transport (clientFetcher.ts)
    - clientPortalKeys factory (clientQueries.ts)
  provides:
    - useClientGymInfo hook (clientQueries.ts)
    - GymInfoData TypeScript interface
    - gymInfo key in clientPortalKeys factory
    - useClientGymInfo re-export through data/index.js swap seam
    - Full GymInfoSheet.jsx rendering live DB gym data per UI-SPEC
    - GymInfoSheet.test.jsx — 7 vitest tests (loaded/loading/error/badge-open/badge-closed/social-hidden/social-shown)
  affects:
    - packages/api-client/src/schema.d.ts (forward-added /api/v1/client/gym path + operation; Phase 89 will regenerate byte-stable)
tech_stack:
  added: []
  patterns:
    - useQuery hook with clientRequest GET, staleTime 30_000 (mirrors useClientLoyaltyBalance)
    - swap-seam re-export through data/index.js (mirrors Phase-82 loyalty hooks)
    - Europe/Moscow client-side open/closed badge derivation via Intl.DateTimeFormat + formatToParts
    - Static photo strip from STATIC_PHOTOS constant (frontend-only, not from API)
    - Conditional social section (rendered only when data.social.length > 0)
    - T-86-09: rel="noopener noreferrer" on social/external links + fixed URL prefix construction
key_files:
  created:
    - apps/client-pwa/src/screens/sheets/GymInfoSheet.test.jsx
  modified:
    - apps/client-pwa/src/lib/clientQueries.ts
    - apps/client-pwa/src/data/index.js
    - apps/client-pwa/src/screens/sheets/GymInfoSheet.jsx
    - packages/api-client/src/schema.d.ts
decisions:
  - "D-86-03-SCHEMA-FORWARD: /api/v1/client/gym path + client_get_gym_info operation added to schema.d.ts as a forward entry — Phase 89 will regenerate byte-stable openapi.json + schema.d.ts; this avoids a TS2345 type error without weakening type safety"
  - "D-86-03-STATIC-PHOTOS: STATIC_PHOTOS inlined in GymInfoSheet.jsx (not imported from gym.js) — gym.js retained for other non-wired consumers per CONTEXT.md deferral; the photos array shape is identical"
  - "D-86-03-INTL-BADGE: Open/closed badge uses Intl.DateTimeFormat formatToParts (weekday+hour+minute) with timeZone:'Europe/Moscow' rather than a fixed UTC offset — handles DST-safe derivation without date-fns"
metrics:
  duration: ~12 minutes
  completed_date: "2026-06-06"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 4
---

# Phase 86 Plan 03: PWA GymInfoSheet wired to live backend (GYM-01) Summary

useClientGymInfo hook + GymInfoData interface in clientQueries.ts, swap-seam export in data/index.js, full GymInfoSheet.jsx rewrite per 86-UI-SPEC (hero, photo strip, hours + open/closed badge, amenities grid, rules, contacts, conditional social), and 7 passing vitest tests.

## What Was Built

**`useClientGymInfo` hook + `GymInfoData` interface** (`apps/client-pwa/src/lib/clientQueries.ts`):
- `gymInfo: () => [...clientPortalKeys.all, 'gym-info'] as const` added to key factory.
- `GymInfoData` interface with all API wire fields: `name`, `tagline`, `address`, `city`, `metro`, `phone`, `email`, `hours[]`, `amenities[]`, `rules[]`, `social[]`.
- `useClientGymInfo()` using `useQuery` with `queryFn` → `clientRequest('get', '/api/v1/client/gym')` → `(res as { data: GymInfoData }).data`, `staleTime: 30_000`.

**Swap-seam export** (`apps/client-pwa/src/data/index.js`):
- `useClientGymInfo` appended to the `export { ... } from '../lib/clientQueries'` block with a Phase-86 GYM-01 comment.

**Forward schema entry** (`packages/api-client/src/schema.d.ts`):
- Path `/api/v1/client/gym` and operation `client_get_gym_info` added so TypeScript resolves the typed `clientRequest` call. Phase 89 will regenerate this byte-stable from the live FastAPI spec.

**GymInfoSheet full rewrite** (`apps/client-pwa/src/screens/sheets/GymInfoSheet.jsx`):
- Outer shell: `position:absolute; inset:0; zIndex:220; sheet-up animation` + `StatusBar` + `SubSheetHeader title="Информация о зале"` + `PullToRefresh`.
- Loading: `GymInfoSkeleton` component with `aria-label="Загрузка информации о зале…"` — sk/sk-line blocks preserving section structure.
- Error: `GymInfoError` — alertCircle 40px in danger-soft 64px circle + t-h3 + t-small copy per UI-SPEC.
- [1] Hero card: name (t-h2), tagline (t-body), address chip (mapPin icon), metro chip (navigation icon).
- [2] Photo strip: `STATIC_PHOTOS` constant (frontend-only, 5 decorative cells with bg color + icon + tag label).
- [3] Hours section: today row with open/closed badge + secondary line; hairline divider; 6 weekly rows sorted by distance from today.
- [4] Amenities 4-col grid: accent-soft icon containers + t-mini label.
- [5] Rules numbered list: number circle (surface-2 + border) + t-body rule text.
- [6] Contacts: `<a href="tel:">` phone row + `<a href="mailto:">` email row with chevronRight trailing icon.
- [7] Social section: conditional on `data.social.length > 0`; socialUrl() builds `https://t.me/` / `https://instagram.com/` URLs with handle `@` stripped; `rel="noopener noreferrer"` on all external links (T-86-09).

**Open/closed badge derivation** (client-side, Europe/Moscow):
- `getMoscowNow()` uses `Intl.DateTimeFormat('en', {timeZone:'Europe/Moscow', hour, minute, weekday}).formatToParts(new Date())` to extract `{todayIdx, nowMinutes}` safely across timezones.
- `todayIdx = weekdayMap[weekdayStr]` (Mon=0…Sun=6); `isOpen = nowMinutes >= openMinutes && nowMinutes < closeMinutes`.
- Closed-night path: show tomorrow's open time in secondary line.

**GymInfoSheet.test.jsx** (`apps/client-pwa/src/screens/sheets/GymInfoSheet.test.jsx`):
- 7 tests: loaded (gym name + ЧАСЫ РАБОТЫ + Парковка), loading (skeleton aria-label, no error), error (error heading + sub-copy), badge-open (Mon 10:00 MSK → "Сейчас открыто"), badge-closed (Mon 03:00 MSK → "Закрыто"), social-hidden (social:[]), social-shown (Telegram + handle).
- Mock `@/data` via `vi.mock`, stub Icon/StatusBar/PullToRefresh/SubSheetHeader, deterministic Date mock for badge tests.

## Verification Results

- `pnpm tsc -b --noEmit`: exit 0 (hook + interface + schema forward-entry typecheck).
- `pnpm vitest run src/screens/sheets/GymInfoSheet.test.jsx`: 7 passed.
- `GymInfoSheet.jsx` contains `useClientGymInfo`, does not contain `ComingSoon`.
- `grep "Информация о зале" GymInfoSheet.jsx`: matches SubSheetHeader title.
- `grep "Сейчас открыто"` and `grep "Закрыто"`: both match (open/closed badge branches).

## Commits

- `dd956d56`: feat(86-03): useClientGymInfo hook + GymInfoData interface + swap-seam export
- `d870ab25`: feat(86-03): GymInfoSheet full rewrite + vitest coverage

## Deviations from Plan

**1. [Rule 1 - Bug] Forward schema.d.ts entry added (D-86-03-SCHEMA-FORWARD)**
- **Found during:** Task 1 — `pnpm tsc -b --noEmit` raised TS2345 for `/api/v1/client/gym` not in `keyof paths`.
- **Issue:** The typed `clientRequest` signature requires the path to exist in the OpenAPI `paths` type. Phase 85 froze the schema before Phase 86 added the gym endpoint; Phase 89 will regenerate byte-stable.
- **Fix:** Added `/api/v1/client/gym` path entry and `client_get_gym_info` operation to `packages/api-client/src/schema.d.ts`. Matches the additive pattern used by every prior phase that shipped a new endpoint between freeze cycles.
- **Files modified:** `packages/api-client/src/schema.d.ts`
- **Commit:** dd956d56

**2. [Rule 2 - Missing critical] `rel="noopener noreferrer"` on all external links**
- **Found during:** Task 2 — threat model T-86-09 requires external links to use `rel="noopener noreferrer"`.
- **Action:** Applied to both `target="_blank"` social links. No separate deviation — planned mitigation from threat register, implemented inline per plan instructions.

## Known Stubs

None — GymInfoSheet renders live DB content from the seeded baseline. No hardcoded placeholder text. `STATIC_PHOTOS` is intentionally frontend-only per CONTEXT.md (décor photos not stored in DB); this is a documented product decision, not a stub.

## Threat Flags

None — all threat mitigations from T-86-09 / T-86-10 / T-86-11 / T-86-SC implemented:
- T-86-09: social URLs built via fixed `https://t.me/` / `https://instagram.com/` prefixes; `rel="noopener noreferrer"` on all `target="_blank"` links.
- T-86-10: Generic error copy; no raw error object or HTTP status echoed to UI.
- T-86-11: `useClientGymInfo` calls `clientRequest` which carries the established client auth transport — no separate auth path.
- T-86-SC: No new package installs; reuses existing PWA stack.

## Self-Check: PASSED

- [x] `apps/client-pwa/src/lib/clientQueries.ts` contains `useClientGymInfo` and `GymInfoData`
- [x] `apps/client-pwa/src/data/index.js` contains `useClientGymInfo` re-export
- [x] `apps/client-pwa/src/screens/sheets/GymInfoSheet.jsx` contains `useClientGymInfo`, does not contain `ComingSoon`
- [x] `apps/client-pwa/src/screens/sheets/GymInfoSheet.test.jsx` exists (7 tests)
- [x] Commits `dd956d56` and `d870ab25` verified in git log
- [x] `pnpm tsc -b --noEmit` exit 0
- [x] `pnpm vitest run GymInfoSheet.test.jsx`: 7 passed
