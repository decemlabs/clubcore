---
phase: 73-downloads-home-html
plan: "01"
subsystem: client-pwa
tags: [frontend, ui, restyle, home-screen]
dependency_graph:
  requires: []
  provides:
    - HomeHeroCard (classic variant, fixed occupancy, GYM_INFO status)
    - SubCardSpot (canonical dark club-card for active/warn/danger subscriptions)
    - BookSpot (compact illustration for empty-booking CTA)
    - BookTile / ChatTile (replacing QuickTile in HomeClassic)
    - GymStatusPill (upgraded: real GYM_INFO open/closed status)
  affects:
    - apps/client-pwa/src/screens/HomeScreen.jsx
    - apps/client-pwa/src/styles.css
tech_stack:
  added: []
  patterns:
    - Static-data occupancy widget (no interval, no randomness — D-04)
    - Dark club-card with tone-driven accent (SubCardSpot)
    - BookSpot illustration with CSS keyframe references (no inline style block)
key_files:
  created: []
  modified:
    - apps/client-pwa/src/styles.css
    - apps/client-pwa/src/screens/HomeScreen.jsx
decisions:
  - GYM_INFO imported directly from @/data/gym.js (not @/data — was removed from index.js in Plan 71-05)
  - Fixed occupancy at first level only [42,60,30,38]/«Свободно» — no rotation, no Math.random
  - ChatTile badge defaults to 0; chat is not wired to a real API (D-10)
  - HomeHeroCard replaces the inline greeting+GymStatusPill header for all non-newbie variants
  - Default subCardStyle flipped 'eyebrow' → 'spot'; legacy eyebrow block retained for dev tweaks
  - BookSpot inline <style> deleted; keyframes moved to styles.css (Task 1)
  - ChatTile inline <style> deleted; chat-dot already in styles.css
metrics:
  duration: 5m
  completed_date: "2026-06-01T21:45:33Z"
  tasks_completed: 2
  files_modified: 2
---

# Phase 73 Plan 01: Home Screen Restyle — new mockup visual summary

Ported the approved `Home.html` mockup visual into the production `apps/client-pwa` `HomeScreen.jsx` active/lapsed branch — `HomeHeroCard` (static «Свободно» occupancy + live `GYM_INFO` open/closed `GymStatusPill`), canonical `SubCardSpot` dark club-card with real API membership data across active/warn/danger tones, `BookSpot` «Запишись» CTA for the empty-booking case, `BookTile`/`ChatTile` quick-action tiles (chat with no badge), while the newbie branch, App.jsx mount contract, `toSubInfo`/`deriveOnboardingSteps`/redirect effect/`ExpiredAlert`, and all co-located tests remained unchanged and green.

## Tasks

| # | Name | Status | Commit |
|---|------|--------|--------|
| 1 | Port book-scene-in and book-float keyframes into styles.css | done | c6fb5da7 |
| 2 | Port HomeHeroCard, SubCardSpot, BookSpot, BookTile, ChatTile; rewire HomeClassic; flip default subCardStyle | done | a56b3fbe |

## Verification Results

- `pnpm --filter client-pwa test`: 21/21 tests passed (adapters 16 + identity 5)
- `pnpm --filter client-pwa lint`: exit 0
- `pnpm --filter client-pwa build`: exit 0
- `grep "@keyframes book-scene-in"`: count = 1 ✓
- `grep "@keyframes book-float"`: count = 1 ✓
- `grep "function HomeHeroCard("`: present ✓
- `grep "function SubCardSpot("`: present ✓
- `grep "function BookSpot("`: present ✓
- `grep "function BookTile("`: present ✓
- `grep "function ChatTile("`: present ✓
- `grep "tweaks.subCardStyle || 'spot'"`: present ✓
- No `setInterval` in HomeScreen.jsx ✓
- No `Math.random` in HomeScreen.jsx ✓
- Fixed occupancy `[42, 60, 30, 38]` / «Свободно» ✓
- No NOTIFICATIONS/TRAINER_CANCEL/UPCOMING_BOOKING/getSubInfo imports ✓
- `<HomeHeroCard` rendered in non-newbie branch ✓
- Identity test: active renders SubCardSpot with 'Годовой'; no 'Оформить абонемент' ✓
- Identity test: null membership shows 'Нет абонемента' + 'Выбрать тариф' ✓
- Identity test: greeting shows 'Иван' ✓
- Identity test: newbie still renders 'Выбери свой абонемент' ✓

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all components consume real API data (`sub` from `toSubInfo(homeData?.membership)`; `GYM_INFO` static inlined demo data per D-71-07).

## Threat Flags

None — visual restyle only; no new network endpoints, auth paths, or trust boundaries (T-73-01 accepted).

## Self-Check: PASSED

- `apps/client-pwa/src/styles.css` — modified and committed (c6fb5da7) ✓
- `apps/client-pwa/src/screens/HomeScreen.jsx` — modified and committed (a56b3fbe) ✓
- Both commits exist on worktree-agent-a0d66b55e449213fa branch ✓
