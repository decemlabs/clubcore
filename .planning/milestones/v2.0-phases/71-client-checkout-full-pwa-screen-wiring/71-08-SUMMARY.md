---
phase: 71-client-checkout-full-pwa-screen-wiring
plan: 08
subsystem: client-pwa
tags: [pwa, service-worker, security, cache, PWA-05, PWA-07, gap-closure]
requires:
  - "Hand-written public/sw.js as the registered canonical worker"
provides:
  - "PWA-07-compliant service worker: /api/* network-only, no Cache Storage writes for authed data"
  - "Cache version gym-v3 — old gym-v2 cache (with stale /api/* entries) evicted on activate"
affects:
  - "apps/client-pwa runtime offline + caching behavior"
tech-stack:
  added: []
  patterns:
    - "URL-pathname-based /api guard (not origin) — dev proxy makes /api same-origin"
    - "Cache-version bump as eviction mechanism via existing activate delete-non-VERSION handler"
key-files:
  created: []
  modified:
    - apps/client-pwa/public/sw.js
    - apps/client-pwa/src/services/pwa.js
decisions:
  - "Keep hand-written public/sw.js and harden it (not switch to VitePWA workbox worker) — registerPwa() already registers /sw.js; switching would lose bespoke offline-shell + offline.html and require re-deriving precache list"
metrics:
  duration: ~6m
  completed: 2026-05-30
  tasks: 2
  files: 2
---

# Phase 71 Plan 08: PWA Service Worker /api Cache Hardening Summary

Made the registered hand-written service worker network-only for `/api/*` and bumped the cache version to `gym-v3` so authed per-client API payloads are never written to Cache Storage and old polluting `gym-v2` entries are evicted on activate — closing the BLOCKER from 71-HUMAN-UAT test 2 (stale `/api/v1/client/plans` served from cache).

## What Was Built

- **Task 1 (`apps/client-pwa/public/sw.js`):** Added an early `url.pathname.startsWith('/api/')` guard in the fetch handler that returns `fetch(req)` with zero cache read and zero `cache.put`, placed before the navigation branch so `/api/*` can never reach the navigation or cache-first paths. Bumped `VERSION` from `gym-v2` to `gym-v3`; the existing activate handler (deletes every cache key !== VERSION) now evicts the entire stale `gym-v2` cache on next activate. Navigation branch (network-first → cached shell → `/offline.html`) and the static-asset cache-first branch left unchanged — the cache-first branch now only ever sees non-`/api`, non-navigation GETs.
- **Task 2 (`apps/client-pwa/src/services/pwa.js`):** Added a two-line PWA-07 / T-69-07 regression-guard comment above the `navigator.serviceWorker.register('/sw.js')` call warning against swapping to the VitePWA-generated worker without porting the `/api` guard. No behavioral change: registration target, `beforeinstallprompt` capture, and `triggerInstall`/`canInstall` exports untouched.

## Verification

- Task 1 automated check: PASSED — `gym-v3` present, `/api` guard with `event.respondWith(fetch(req))` present and precedes the navigation branch, no `gym-v2` literal remains.
- Task 2 automated check: PASSED — still registers `/sw.js`, PWA-07 guard comment present.
- **Pending live UAT (runtime, human):** Cache Storage population is runtime behavior. The plan's `<verification>` block requires re-running 71-HUMAN-UAT test 2 in a live browser: confirm active worker is `gym-v3`, Cache Storage has no `gym-v2` and zero `/api/*` keys, Network tab shows every `/api/*` "(from network)", and offline reload still renders `/offline.html` / cached shell. This cannot be automated here.

## Deviations from Plan

None — plan executed exactly as written.

## Threat Mitigations Applied

| Threat ID | Mitigation | Status |
|-----------|------------|--------|
| T-71-08-01 (Info Disclosure: /api caching) | `url.pathname.startsWith('/api/')` network-only guard, zero cache.put | Applied (sw.js) |
| T-71-08-02 (Stale serve from gym-v2) | VERSION bump to gym-v3 → activate evicts non-VERSION caches | Applied (sw.js) |

## Commits

- `27fd4f72` fix(71-08): make /api/* network-only in sw.js + bump cache to gym-v3
- `4f1780f0` docs(71-08): add PWA-07 regression-guard comment in pwa.js

## Self-Check: PASSED

All modified/created files present and all commits verified in git log:
- apps/client-pwa/public/sw.js
- apps/client-pwa/src/services/pwa.js
- .planning/phases/71-client-checkout-full-pwa-screen-wiring/71-08-SUMMARY.md
- Commits: 27fd4f72, 4f1780f0, 4dc32f27
