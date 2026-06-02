---
phase: 71-client-checkout-full-pwa-screen-wiring
plan: 10
subsystem: client-pwa
tags: [pwa, identity, client-me, wiring, gap-closure]
requires:
  - "71-09: corrected camelCase toSubInfo / toSubInfo(null) empty state in both screens"
  - "@/data useClientMe (GET /client/me) re-export"
provides:
  - "HomeScreen greeting bound to real /client/me firstName"
  - "HomeScreen membership-null → real toSubInfo(null) 'Нет абонемента' empty state"
  - "ProfileScreen identity header bound to /client/me (name/phone/email)"
  - "ProfileScreen membership block free of fabricated renewal amounts"
affects:
  - apps/client-pwa/src/screens/HomeScreen.jsx
  - apps/client-pwa/src/screens/ProfileScreen.jsx
tech-stack:
  added: []
  patterns:
    - "useClientMe() cached read (AuthContext already populates clientPortalKeys.me())"
    - "vi.mock('@/data') render tests asserting real-identity binding"
key-files:
  created:
    - apps/client-pwa/src/screens/HomeScreen.identity.test.jsx
    - apps/client-pwa/src/screens/ProfileScreen.identity.test.jsx
  modified:
    - apps/client-pwa/src/screens/HomeScreen.jsx
    - apps/client-pwa/src/screens/ProfileScreen.jsx
decisions:
  - "Greeting/name falls back to '' (renders nothing) rather than a fake hardcoded human name; tweaks.userName kept only as a dev-panel override."
  - "Profile renewal line shows the real until-date only — fabricated '42 000 ₽'/'4 900 ₽' amounts removed since /client/me + /client/membership expose no renewal price."
metrics:
  duration: ~7m
  tasks: 2
  files: 4
  completed: 2026-05-30
---

# Phase 71 Plan 10: Bind Home/Profile to real /client/me identity Summary

Replaced mock identity + the demo active-membership fallback on the wired PWA Home and
Profile screens with the logged-in client's real `/client/me` identity and the genuine
empty-membership state — closing the MAJOR from 71-HUMAN-UAT test 1 and satisfying ROADMAP
Phase 71 Success Criterion 4 (Home/Profile fetch real backend data, mocks replaced).

## What changed

### Task 1 — HomeScreen identity + empty-membership (commit e09fc0c7)
- Imported `useClientMe` from `@/data`; greeting `userName = me?.firstName || tweaks.userName || ''`
  (no hardcoded `'Саша'` default).
- `sub = toSubInfo(homeData?.membership ?? null)` — removed the `getSubInfo(tweaks.subState)`
  demo active-card fallback on the real-data path; `membership=null` now renders the real
  "Нет абонемента" danger state (ExpiredAlert + "Выбрать тариф" CTA).
- Removed the now-unused `getSubInfo` import.
- Added `HomeScreen.identity.test.jsx` (mocks `@/data`): real first name in greeting; null
  membership → "Нет абонемента"/"Выбрать тариф", no fake "Годовой" active card.

### Task 2 — ProfileScreen identity header + membership block (commit 203bca4a)
- Imported `useClientMe`; identity header now renders the real `fullName`, `phone`, and
  `email` (graceful em-dash `—` when absent). Avatar initials derive from `me?.firstName`.
  Removed the literals `"Саша Морозов"`, `"+7 (916) 482-09-14"`, `"sasha@example.com"`.
- `sub = toSubInfo(homeData?.membership ?? null)` — removed the `getSubInfo(tweaks.subState)`
  demo fallback.
- Removed the fabricated `"· 42 000 ₽"` / `"· 4 900 ₽"` renewal figures; renewal/status line
  now shows the real `sub.until` date only. The 'danger' branch ("Карта •••• 4821") is demo
  card chrome left in place (not presented as live identity data).
- Removed the now-unused `getSubInfo` import.
- Added `ProfileScreen.identity.test.jsx` (mocks `@/data` + `@/context/AuthContext.jsx`):
  real name/phone/em-dash email; null membership → "Нет абонемента", no "42 000 ₽"/"4 900 ₽".

## Verification

- Plan automated grep gates (Task 1 + Task 2): both pass — `useClientMe`/`me?.firstName`
  present; `getSubInfo(tweaks.subState)` count 0; `toSubInfo(homeData?.membership ?? null)`
  present; mock identity literals + fabricated amounts count 0.
- Full client-pwa suite: 9 test files, 23 tests — all pass (includes the 4 new render tests
  and the existing 71-09 adapter tests, no regression).
- TDD gates observed per task (RED render test failing on mock identity → GREEN binding).

## Deviations from Plan

None — plan executed as written. (Deps were installed in the worktree from the frozen
lockfile to run vitest; no package added, lockfile unchanged.)

## Known Stubs

None introduced. Pre-existing demo chrome intentionally left per plan scope:
`tweaks.gymEvent === 'trainer-cancelled'` DEMO_TRAINER_CANCEL card (HomeScreen) and the
"Карта •••• 4821" danger-branch card chrome (ProfileScreen) — both explicitly out of scope
and not presented as live identity/financial data.

## Self-Check: PASSED

- FOUND: apps/client-pwa/src/screens/HomeScreen.jsx (modified)
- FOUND: apps/client-pwa/src/screens/ProfileScreen.jsx (modified)
- FOUND: apps/client-pwa/src/screens/HomeScreen.identity.test.jsx (created)
- FOUND: apps/client-pwa/src/screens/ProfileScreen.identity.test.jsx (created)
- FOUND commit e09fc0c7 (Task 1)
- FOUND commit 203bca4a (Task 2)
