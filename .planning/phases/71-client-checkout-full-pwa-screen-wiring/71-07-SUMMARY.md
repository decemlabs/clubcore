---
phase: 71-client-checkout-full-pwa-screen-wiring
plan: "07"
subsystem: auth
tags: [pwa, client-auth, otp, react-router, auth-guard, telegram, redirect-loop]
gap_closure: true

# Dependency graph
requires:
  - phase: 71-04
    provides: clientPortalKeys factory, clientRequest transport, data/index.js swap seam, queryClient
  - phase: 71-05
    provides: wired Home/Profile/Plans/Checkout screens + App.jsx routing
  - phase: 68-client-auth
    provides: POST /client/otp/request, POST /client/otp/verify, GET /client/me, cc_client_* cookies

provides:
  - authBus.ts — decoupled session-expiry pub/sub (queryClient publishes, AuthContext subscribes)
  - AuthContext (status unknown|authed|anon) bootstrapped via GET /client/me probe + login/logout
  - useClientMe / useOtpRequest / useOtpVerify query+mutation hooks (via data/index.js swap seam)
  - LoginScreen — real two-step OTP login (phone → 6-digit code) on the provided HTML template
  - /login route + RequireAuth guard (protected tabs + catch-all); QueryClientProvider lifted to main.jsx
  - LoadError — shared data-load failure state (full-screen + inline) from the Error.html template
  - dev-only login UAT path: pinned OTP 111111 + seed_dev_client fixture (+79999999999)

affects:
  - Phase 72 (E2E verification — login now unblocks all client PWA flows)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "authBus module-scoped pub/sub decouples non-React queryClient from react-router navigation"
    - "me-probe auth bootstrap (GET /client/me → authed/anon/unknown) instead of a token store"
    - "RequireAuth wraps protected routes AND the catch-all so anon never lands on a protected query"
    - "scoped <style> blocks with lg-/le- prefixes port HTML mockups onto PWA design tokens"

key-files:
  created:
    - apps/client-pwa/src/lib/authBus.ts
    - apps/client-pwa/src/lib/authBus.test.tsx
    - apps/client-pwa/src/context/AuthContext.jsx
    - apps/client-pwa/src/context/AuthContext.test.jsx
    - apps/client-pwa/src/context/RequireAuth.jsx
    - apps/client-pwa/src/context/RequireAuth.test.jsx
    - apps/client-pwa/src/screens/LoginScreen.jsx
    - apps/client-pwa/src/components/LoadError.jsx
    - apps/backend/scripts/seed_dev_client.py
  modified:
    - apps/client-pwa/src/lib/queryClient.ts
    - apps/client-pwa/src/lib/clientQueries.ts
    - apps/client-pwa/src/data/index.js
    - apps/client-pwa/src/App.jsx
    - apps/client-pwa/src/main.jsx
    - apps/client-pwa/src/lib/clientFetcher.test.tsx
    - apps/client-pwa/src/screens/HomeScreen.jsx
    - apps/client-pwa/src/screens/ProfileScreen.jsx
    - apps/client-pwa/src/screens/BookScreen.jsx
    - apps/backend/app/main.py
    - apps/backend/app/modules/client_auth/service.py

key-decisions:
  - "Replace window.location.replace('/login') with authBus publish so session expiry routes via react-router (no full reload, no loop)"
  - "OTP is 6 digits (backend generate_otp_code) — login uses 6 boxes, not the mockup's 4"
  - "Phone sent as E.164 +7XXXXXXXXXX (CAUTH-03 _PHONE_REGEX); copy says Telegram (real OTP channel)"
  - "Dev-only (ENVIRONMENT=dev) OTP pinned to 111111 + log; staging/prod keep random code + bot DM only"

patterns-established:
  - "authBus seam: pure module pub/sub bridges queryClient (no React) to AuthContext (React/router)"
  - "LoadError variants: full-screen for primary-query failure, inline for tab/list failures"
---

## What was built

Closed the UAT blocker (`71-07`, gap closure): every unauthenticated PWA load was
trapped in an infinite redirect loop (`useClientHome` 401 → single-flight refresh 401 →
`window.location.replace('/login')` → no `/login` route → catch-all `Navigate to /home` →
re-fire query → loop), and there was no real client login.

**Task 1 — break the loop.** `authBus.ts` (module-scoped `subscribe/publishSessionExpired`);
`queryClient.ts` now calls `publishSessionExpired()` instead of `window.location.replace`.

**Task 2 — auth bootstrap.** `useClientMe` / `useOtpRequest` / `useOtpVerify` hooks (exported
through the `data/index.js` swap seam); `AuthContext` runs a `GET /client/me` probe on mount
(authed/anon/unknown), subscribes to authBus for mid-use expiry, exposes `login`/`logout`.

**Task 3 — login UI + guard.** `LoginScreen` (real OTP request+verify), `/login` route,
`RequireAuth` guard over protected tabs and the catch-all, `QueryClientProvider` lifted into
`main.jsx` above `AuthProvider`. `clientFetcher.test.tsx` updated for the new provider tree.

**Task 4 — human verify: APPROVED** (see Verification).

**Post-checkpoint enhancements (user-directed):**
- `LoginScreen` redesigned to the provided `Login.html` mockup (brand mark, two-step slide,
  +7 phone-row, accent CTA, OTP boxes, success flash) on PWA tokens; fixed a double focus ring.
- `LoadError` component from the `Error.html` mockup, wired into HomeScreen (full-screen),
  ProfileScreen tabs (inline), and BookScreen schedule failure.
- Dev-only login UAT path: `ENVIRONMENT=dev` pins the client OTP to `111111` (and logs it);
  `seed_dev_client.py` seeds an alive fake-linked test client `+79999999999`.

## Verification

Live browser walkthrough (fresh isolated context, via the Vite proxy → Docker backend):
- `/home` while unauthenticated → redirected to `/login`, LoginScreen renders, **single**
  `GET /client/me 401` (no `/session/refresh`, no repeating 401 storm, no `/login↔/home` loop).
- Phone `999 999-99-99` → "Получить код" → `POST /otp/request 202` → 6-box code step.
- Code `111111` → `POST /otp/verify 200` (cc_client_* cookies issued) → `login()` →
  `GET /client/me 200` → navigate `/home` → `GET /client/home 200`, HomeScreen real data
  ("Доброе утро, Саша", Годовой абонемент, 47 дней). No console errors.

Automated: authBus (4), AuthContext (3), RequireAuth (3), clientFetcher (3) = 13 tests green;
`tsc --noEmit` clean for new .ts; `pnpm build` succeeds. Backend ruff + mypy strict clean;
client_auth integration tests (18) green.

## Deviations / notes

- The mockup used 4 OTP boxes; real backend codes are 6 digits → 6 boxes.
- Earlier UAT failures were operational, not login bugs: missing seed client, Docker-on-macOS
  WatchFiles missing a `service.py` reload (needs `docker restart`), a stale `cc_client_access`
  cookie (`invalid_token` on `/me` — clean in incognito), and OTP rate-limit 429 from repeated
  test requests (clear `ratelimit:client_otp*` in Redis).
- Dev OTP override and seed are strictly `ENVIRONMENT=dev`-gated; production delivery path
  (random code via Telegram bot DM) is unchanged.

## Self-Check: PASSED
