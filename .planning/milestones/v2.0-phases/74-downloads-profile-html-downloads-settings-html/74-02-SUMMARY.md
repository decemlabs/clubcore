---
phase: 74-downloads-profile-html-downloads-settings-html
plan: "02"
subsystem: client-pwa
tags: [frontend, profile-screen, membership-hero, feature-flags, restyle]
dependency_graph:
  requires:
    - 74-01 (SettingsScreen.jsx and /settings route must exist for gear navigation)
  provides:
    - apps/client-pwa/src/screens/ProfileScreen.jsx (restyled)
    - .membership-hero CSS in apps/client-pwa/src/styles.css
  affects:
    - apps/client-pwa/src/styles.css
tech_stack:
  added: []
  patterns:
    - PROFILE_FEATURE_FLAGS module-level const (mirrors CHECKOUT_FEATURE_FLAGS from CheckoutSheet.jsx)
    - .membership-hero contrast-flip CSS via [data-theme="dark"] selector (not body.dark)
    - useCountUp hook with requestAnimationFrame ease-out cubic for stat strip animation
    - elapsedDays = total - daysLeft for progress bar labeling (D-74-03)
key_files:
  created: []
  modified:
    - apps/client-pwa/src/screens/ProfileScreen.jsx
    - apps/client-pwa/src/styles.css
decisions:
  - "D-74-01: Gear button in identity card calls navigate('/settings'); Settings tab removed from ProfileScreen tabs"
  - "D-74-03: Hero shows only toSubInfo-derived API fields; price/auto-renew block entirely absent"
  - "D-74-04: Stat strip has 2 live cells (visits, trainings); 3rd cell weeksStat gated false"
  - "D-74-05: PROFILE_FEATURE_FLAGS.weeklyActivity/tenureBadge/weeksStat/linkedCard all false (BUILT, HIDDEN)"
  - "CSS dark selector [data-theme='dark'] .membership-hero per TweaksContext convention (not body.dark)"
metrics:
  duration: "~4m"
  completed: "2026-06-02"
  tasks_completed: 2
  files_modified: 2
---

# Phase 74 Plan 02: ProfileScreen Restyle Summary

Pass-style membership hero, live stat strip with count-up animation, gear→/settings navigation, and 3-tab history panel; all unbacked decor gated behind PROFILE_FEATURE_FLAGS.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Add .membership-hero contrast-flip CSS to styles.css | 2d33b609 |
| 2 | Restyle ProfileScreen — flags, pass-hero, stat strip, gear→/settings, drop Settings tab | f06cb9e7 |

## What Was Built

**styles.css** (membership-hero CSS block added):
- `.membership-hero` light theme: dark graphite (#0e0e0e) pass with full `--mh-*` var set (text/text-2/text-3, track, divider, accent, chip-bg/fg/border, ghost-bg/border, cta-bg/cta-fg)
- `[data-theme="dark"] .membership-hero`: beige (#ece0cd) pass override — selector uses `data-theme` per TweaksContext convention (NOT `body.dark`)
- Ports Profile.html lines 199-242 with enhanced chip vars added from the full mockup

**ProfileScreen.jsx** (full restyle, 450 lines):
- `PROFILE_FEATURE_FLAGS = { weeklyActivity: false, tenureBadge: false, weeksStat: false, linkedCard: false }` with BUILT, HIDDEN comment block
- `useCountUp(target)` hook: requestAnimationFrame cubic ease-out (1-Math.pow(1-p,3)) for stat strip animation
- Identity card: Avatar + name column + gear button (`<Icon name="settings">`) calling `navigate('/settings')`; tenure badge gated behind `PROFILE_FEATURE_FLAGS.tenureBadge`
- Membership hero: className `membership-hero` card with pass-style layout from Profile.html. Binds only API fields via `toSubInfo` result: `sub.daysLeft`, `elapsedDays` (= total − daysLeft), progress bar at elapsed/total pct, `sub.until`, `sub.label`. Freeze button (active only) + Change/Extend button preserved. No price line ("Стоимость … ₽/год"), no auto-renew ("Продление: Автоматически").
- Stat strip: 2 `StatCell` components with count-up bound to `visitData?.total ?? 0` and `ptData?.total ?? 0`; 3rd "недель" cell wrapped in `PROFILE_FEATURE_FLAGS.weeksStat && (...)`
- Weekly activity card: built with 7 placeholder bar divs + day labels, wrapped in `PROFILE_FEATURE_FLAGS.weeklyActivity && (...)`
- Quick tiles: referral (coupon-style with dashed divider matching Profile.html) + gym info
- Tab array: 3 entries only (Визиты / Тренировки / Покупки); `id: 'settings'` entry deleted
- `tab === 'settings'` panel and `<SettingsList>` call removed
- `SettingsList`, `SettingRow`, `NavRow`, `Divider2` components deleted (now live in SettingsScreen.jsx)
- `useAuth` import removed (no longer needed after SettingsList removal)

## Deviations from Plan

None — plan executed exactly as written.

Minor implementation note: `useClientVisitHistory` and `useClientPtHistory` are called at the top of ProfileScreen (not just inside the tab components) so the stat strip always has data regardless of which tab is active. This is consistent with the plan requirement that the stat strip binds live totals.

## Threat Model Coverage

| Threat | Disposition | Result |
|--------|-------------|--------|
| T-74-04: Info Disclosure (fake price/tenure/card data) | mitigate | Price/auto-renew block removed entirely; tenure badge, weeksStat, linkedCard, weeklyActivity all gated false — no fabricated value shown |
| T-74-05: Tampering via null/garbage membership | accept | toSubInfo reused unchanged with existing null/NaN guards |
| T-74-06: DoS from count-up animation | accept | Pure requestAnimationFrame on small integers; bounded |

## Known Stubs

None. All data rendered is either API-backed with graceful `?? 0` fallbacks, or feature-flagged off. No hardcoded numbers presented as real stats.

## Self-Check: PASSED

- `apps/client-pwa/src/screens/ProfileScreen.jsx` — exists, PROFILE_FEATURE_FLAGS present, navigate('/settings') present, membership-hero className present, no id:'settings' tab, no SettingsList component
- `apps/client-pwa/src/styles.css` — .membership-hero block present, [data-theme="dark"] .membership-hero block present, --mh-text var present
- Commit 2d33b609 — styles.css membership-hero CSS
- Commit f06cb9e7 — ProfileScreen.jsx full restyle
- `pnpm exec tsc -b --noEmit` — clean (no output)
