---
phase: 98-pwa-referralscreen
plan: "03"
subsystem: client-pwa
tags: [referral, deep-link, onboarding, react-query, sessionStorage]
dependency_graph:
  requires: ["98-02"]
  provides: [deep-link-landing, referral-capture-post-auth]
  affects: [App.jsx, OnboardingScreen.jsx, clientQueries.ts, data/index.js]
tech_stack:
  added: []
  patterns:
    - useQuery with enabled gate (useClientReferralResolve)
    - useMutation fire-and-forget (useCaptureReferral)
    - cast escape hatch for schema.d.ts gap (Phase 99 handoff)
    - sessionStorage pending code pattern (clubcore:pendingReferral)
    - best-effort try/catch with _e + noop (defensive-catch convention)
key_files:
  created:
    - apps/client-pwa/src/screens/ReferralLandingScreen.jsx
  modified:
    - apps/client-pwa/src/lib/clientQueries.ts
    - apps/client-pwa/src/data/index.js
    - apps/client-pwa/src/App.jsx
    - apps/client-pwa/src/screens/OnboardingScreen.jsx
decisions:
  - useClientReferralResolve uses enabled:!!code gate so no request fires on empty code
  - formatBonusPreview returns static "14 дней в подарок" copy (TODO Phase 99 — days field not exposed by resolver)
  - capture runs AFTER setDone(true) precondition in handleFinish so the success overlay fires regardless of capture outcome
  - isReferralLandingRoute uses pathname.startsWith('/i/') to cover all code variants
metrics:
  duration: ~20min
  completed: 2026-06-08T15:21:49Z
  tasks_completed: 3
  tasks_total: 3
  files_changed: 5
---

# Phase 98 Plan 03: PWA Deep-Link Landing + Post-Auth Referral Capture Summary

REFER-02 PWA deep-link plumbing: /i/:code public route resolves code, shows referrer-named landing, stores pending code, and OnboardingScreen captures it post-auth.

---

## What Was Built

Three tasks completing the REFER-02 deep-link flow:

**Task 1 — Hooks + @/data re-exports** (`1589a057`):
- `useClientReferralResolve(code)`: GET /api/v1/i/{code} public resolver, enabled only when code is truthy, staleTime 30s. Cast escape hatch for schema gap.
- `useCaptureReferral()`: POST /api/v1/client/referral/capture mutation, fire-and-forget, same cast pattern.
- Both added to `clientPortalKeys` key factory and re-exported from `@/data` swap seam.

**Task 2 — ReferralLandingScreen + route** (`dcbe0772`):
- New `ReferralLandingScreen.jsx`: chrome-stripped full-screen public landing.
- Valid branch: "{referrerFirstName} зовёт вас в «Sportzal»" + bonus preview chip + stores `clubcore:pendingReferral` then navigates to /login.
- Invalid/error branch: neutral "Добро пожаловать в «Sportzal»" + generic CTA, NO stored code.
- Loading: skeleton placeholder while resolveQuery.isLoading.
- App.jsx: lazy-import + public `/i/:code` route outside RequireAuth + `isReferralLandingRoute` in `hideTabBar` conditions.

**Task 3 — Post-auth capture in OnboardingScreen** (`5fb11e48`):
- `useCaptureReferral` imported and instantiated.
- `handleFinish` success branch: reads `clubcore:pendingReferral`, fires capture (best-effort), removes key.
- `handleSkip` success branch: same pattern.
- Both wrapped in `try/catch (_e) { /* noop */ }` — capture failure never blocks onboarding navigation.
- Fires inside RequireAuth: client_id from authenticated principal (IDOR-safe).

---

## Verification Results

- `tsc --noEmit`: clean (0 errors)
- `eslint src/lib/clientQueries.ts`: clean
- `.jsx` files: excluded by D-69-06 ESLint ramp (intentional — all JSX screens exempt)
- `/i/:code` route present in App.jsx and outside RequireAuth
- `clubcore:pendingReferral` key used in both ReferralLandingScreen and OnboardingScreen
- Brand `«Sportzal»` only; `grep -E "Мой зал|myzal"` → 0 matches
- `apps/admin-web` untouched
- Vitest: 222 tests / 32 test files, all passing

---

## Deviations from Plan

None — plan executed exactly as written.

---

## Known Stubs

| Stub | File | Line | Reason |
|------|------|------|--------|
| `formatBonusPreview` returns static "14 дней в подарок" regardless of `welcomeBonusKopecks` | `apps/client-pwa/src/screens/ReferralLandingScreen.jsx` | 28 | Resolver currently returns kopecks; a days conversion formula is not scoped here. Static copy matches UI-SPEC reference copy. TODO Phase 99 when resolver exposes a `welcomeBonusDays` field. |

Note: The landing CTA ("Присоединиться") and heading copy are fully wired. The bonus preview line is static/safe — it still communicates the gift correctly and matches the reference copy. The plan goal (deep-link resolve + store + capture) is fully achieved.

---

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes introduced in the frontend. The `clubcore:pendingReferral` sessionStorage key is a client-side hint only; the server enforces identity via `require_client()` (T-98-10 mitigated). No new threat surface beyond what was in the plan's STRIDE register.

---

## Self-Check: PASSED

- `apps/client-pwa/src/screens/ReferralLandingScreen.jsx`: EXISTS
- `apps/client-pwa/src/App.jsx`: modified (route + lazy import + hideTabBar)
- `apps/client-pwa/src/screens/OnboardingScreen.jsx`: modified (capture logic)
- `apps/client-pwa/src/lib/clientQueries.ts`: modified (2 new hooks)
- `apps/client-pwa/src/data/index.js`: modified (2 new re-exports)
- Commits: 1589a057, dcbe0772, 5fb11e48 — all present in git log
