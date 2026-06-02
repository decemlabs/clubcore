---
phase: 74-downloads-profile-html-downloads-settings-html
plan: "01"
subsystem: client-pwa
tags: [frontend, settings-screen, routing, local-storage, feature-flags]
dependency_graph:
  requires: []
  provides:
    - apps/client-pwa/src/screens/SettingsScreen.jsx
    - SettingsSkeleton in apps/client-pwa/src/components/skeletons.jsx
    - /settings route in apps/client-pwa/src/App.jsx
  affects:
    - apps/client-pwa/src/App.jsx
    - apps/client-pwa/src/components/skeletons.jsx
tech_stack:
  added: []
  patterns:
    - SETTINGS_FEATURE_FLAGS module-level const (mirrors CHECKOUT_FEATURE_FLAGS pattern from CheckoutSheet.jsx)
    - clubcore:notif:v1 localStorage persist with NOTIF_DEFAULTS fallback (D-74-04)
    - Lazy import with named export unwrap: .then(m => ({ default: m.SettingsScreen }))
    - Own Suspense boundary on non-tab route with dedicated skeleton fallback
key_files:
  created:
    - apps/client-pwa/src/screens/SettingsScreen.jsx
  modified:
    - apps/client-pwa/src/components/skeletons.jsx
    - apps/client-pwa/src/App.jsx
decisions:
  - "D-74-01: /settings is a standalone protected route (RequireAuth) with TabBar hidden via isSettingsRoute"
  - "D-74-04: Notification toggles persist to clubcore:notif:v1 localStorage key; no server call"
  - "D-74-05: SETTINGS_FEATURE_FLAGS.linkedCard and tenureBadge both false (BUILT, HIDDEN)"
  - "Back handler uses window.history.length > 1 check with navigate('/profile') fallback"
metrics:
  duration: "~8m"
  completed: "2026-06-02"
  tasks_completed: 2
  files_modified: 3
---

# Phase 74 Plan 01: SettingsScreen + /settings Route Summary

Standalone Settings screen extracted from ProfileScreen's SettingsList into its own `/settings` route with full local notif persistence, feature-flag scaffolding, and skeleton loading state.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Create SettingsScreen.jsx with sections, local notif persistence, and feature flags | 806394c6 |
| 2 | Add SettingsSkeleton and wire /settings route + hideTabBar in App.jsx | 7a7a2def |

## What Was Built

**SettingsScreen.jsx** (`apps/client-pwa/src/screens/SettingsScreen.jsx`, 375 lines):
- Named export `SettingsScreen` with props: `tweaks`, `setTweak`, `onOpenPlans`, `onOpenPersonalData`, `onOpenCard`, `onOpenFAQ`
- `SETTINGS_FEATURE_FLAGS = { linkedCard: false, tenureBadge: false }` with BUILT, HIDDEN comment block mirroring CheckoutSheet pattern
- Identity strip: Avatar + fullName from `useClientMe()` (graceful blanks); `tenureBadge` gated
- Appearance section: seg-control calling `setTweak('theme', 'light'|'dark')` exactly as ProfileScreen SettingsList
- Notifications: 4 `SettingRow` toggles (promo/schedule/trainer/sound) reading/writing `clubcore:notif:v1` with `NOTIF_DEFAULTS` fallback and try/catch guard (T-74-03)
- Account card: `NavRow` rows for Тариф/Привязанная карта (gated)/Личные данные/FAQ with `Divider2` separators
- Logout button via `useAuth().logout`
- Version line "Версия 2.4.1 · Мой зал"
- Back handler: `window.history.length > 1 ? window.history.back() : navigate('/profile')`
- Helper components `SettingRow`, `NavRow`, `Divider2` copied unchanged from ProfileScreen

**skeletons.jsx** (SettingsSkeleton added):
- Back-button circle + centered title line + spacer header (height 52)
- Identity strip with SkCircle(62) + two SkLine placeholders
- Three section skeleton blocks matching the screen layout

**App.jsx** wiring:
- Lazy import: `const SettingsScreen = lazy(() => import('@/screens/SettingsScreen.jsx').then(m => ({ default: m.SettingsScreen })))`
- `SettingsRoute` function component mirroring ProfileRoute with same `onOpen*` callbacks
- `const isSettingsRoute = pathname === '/settings'` added to hideTabBar disjunction
- `<Route path="/settings" element={<RequireAuth><Suspense fallback={<SettingsSkeleton />}><SettingsRoute /></Suspense></RequireAuth>} />`
- `SettingsSkeleton` added to skeletons import line

## Deviations from Plan

None — plan executed exactly as written.

The `/settings` route was given its own nested `Suspense` boundary with `<SettingsSkeleton />` fallback (rather than relying on the shared tab `Suspense`) to guarantee the skeleton shows during chunk load without flash.

## Threat Model Coverage

| Threat | Disposition | Result |
|--------|-------------|--------|
| T-74-01: Elevation of Privilege via /settings | mitigate | Route wrapped in `<RequireAuth>` — verified in acceptance criteria |
| T-74-02: Info Disclosure clubcore:notif:v1 | accept | Only boolean UI prefs stored; no PII |
| T-74-03: Tampering via malformed localStorage JSON | mitigate | `JSON.parse` wrapped in try/catch with `NOTIF_DEFAULTS` fallback |

## Known Stubs

None. All data rendered is either from live `useClientMe()` data with graceful fallbacks, or feature-flagged off. No hardcoded human names, no placeholder UI pretending to show server data.

## Self-Check: PASSED

- `apps/client-pwa/src/screens/SettingsScreen.jsx` — exists, 375 lines
- `apps/client-pwa/src/components/skeletons.jsx` — SettingsSkeleton export present
- `apps/client-pwa/src/App.jsx` — isSettingsRoute, SettingsRoute, /settings route all present
- Commit 806394c6 — SettingsScreen.jsx
- Commit 7a7a2def — skeletons.jsx + App.jsx
