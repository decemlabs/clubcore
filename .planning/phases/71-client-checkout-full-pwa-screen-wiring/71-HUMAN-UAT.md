---
status: diagnosed
phase: 71-client-checkout-full-pwa-screen-wiring
source: [71-VERIFICATION.md]
started: 2026-05-30T00:00:00Z
updated: 2026-05-30T19:00:00Z
---

## Current Test

number: 1
name: ЮKassa redirect round-trip (anti-oracle poll, criterion #1)
expected: |
  Initiate a membership purchase from the PWA → land on the ЮKassa hosted page → complete/cancel → ЮKassa redirects back to `/payment/return?payment_id=<id>`; the screen shows ONLY "Ожидаем подтверждение..." while pending, never showing the membership as active until the `payment.succeeded` webhook fires and the status endpoint reports `succeeded`. Repeat for a PT-package purchase (return_url also carries `idempotency_key`).
awaiting: blocked by redirect loop — cannot reach checkout (see issue)

## Tests

### 1. ЮKassa redirect round-trip (anti-oracle poll, criterion #1)
expected: Initiate a membership purchase from the PWA → land on the ЮKassa hosted page → complete/cancel → ЮKassa redirects back to `/payment/return?payment_id=<id>`; the screen shows ONLY "Ожидаем подтверждение..." while pending, never showing the membership as active until the `payment.succeeded` webhook fires and the status endpoint reports `succeeded`. Repeat for a PT-package purchase (return_url also carries `idempotency_key`).
result: issue
reported: "stuck on infinite loading spinner on app load; cannot reach Plans/Checkout to start a purchase"
severity: blocker
root_cause: "PWA has no /login route. On any unauthenticated load, useClientHome() → GET /api/v1/client/home 401 → single-flight POST /api/v1/client/session/refresh 401 → clientFetcher throws ApiError('session_expired'). queryClient.ts handleSessionExpired() then calls window.location.replace('/login'). No /login route exists in App.jsx — the catch-all `*` route renders <Navigate to=\"/home\" replace />, which remounts HomeScreen → 401 again → replace('/login') → infinite redirect loop. User sees a perpetual spinner. Additionally there is NO real login flow at all: the OTP screen in screens/sheets/flows.jsx is a pure mock (setTimeout simulate, accepts any code != '0000') and never calls /api/v1/client/otp/* nor establishes a backend session, so a client cannot authenticate to reach the wired screens."

### 2. Service worker never caches /api/* at runtime
expected: With the PWA installed/loaded, open DevTools → Application → Cache Storage. No `/api/*` requests appear in any Workbox cache; the SW `navigateFallbackDenylist` excludes `/^\/api\//` and `runtimeCaching` is empty. Network tab confirms `/api/*` calls always hit the network, never the SW cache.
result: [pending]

### 3. Net-new screens make zero backend calls
expected: Open Chat, Referral, TrainerDetail, Notifications, and GymInfo screens. Each renders the shared "В разработке" ComingSoon placeholder. DevTools Network tab shows NO `/api/*` requests originating from any of these five screens.
result: [pending]

## Summary

total: 3
passed: 0
issues: 1
pending: 2
skipped: 0
blocked: 0

## Gaps

- truth: "A client can initiate a ЮKassa membership/PT-package purchase entirely from the PWA"
  status: failed
  reason: "User reported: stuck on infinite loading spinner on app load; cannot reach Plans/Checkout"
  severity: blocker
  test: 1
  root_cause: "Redirect loop: queryClient.ts handleSessionExpired() does window.location.replace('/login'), but App.jsx has no /login route — catch-all `*` redirects back to /home, which re-fires useClientHome() → 401 → session_expired → /login → loop. Compounded by absence of any real client login flow (OTP in flows.jsx is mock-only, sets no session)."
  artifacts:
    - path: "apps/client-pwa/src/lib/queryClient.ts"
      issue: "Line 31 redirects to non-existent /login route on session_expired"
    - path: "apps/client-pwa/src/App.jsx"
      issue: "No /login route; catch-all `*` → Navigate to /home creates the loop (lines 222-228)"
    - path: "apps/client-pwa/src/screens/sheets/flows.jsx"
      issue: "OTP verify (~line 545) is a mock simulation; never calls /api/v1/client/otp/* nor establishes a backend session"
  missing:
    - "A real client login route/screen that performs OTP request+verify against /api/v1/client/otp/* and establishes the session cookie"
    - "An auth guard that routes unauthenticated users to login WITHOUT a window.location loop"
    - "Decision: was real PWA auth in scope for Phase 71, or should screens fall back to mock when no session?"
