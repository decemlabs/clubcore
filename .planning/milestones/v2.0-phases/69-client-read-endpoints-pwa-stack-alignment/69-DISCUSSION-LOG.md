# Phase 69: Client Read Endpoints + PWA Stack Alignment - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-29
**Phase:** 69-Client Read Endpoints + PWA Stack Alignment
**Areas discussed:** Home data shape, Catalog scope & fields, PWA TS ramp depth, PWA SW & test bar

---

## Home data shape

| Option | Description | Selected |
|--------|-------------|----------|
| Composite /client/home | Single GET returning { membership, nextBooking, expiringSoon }; fewer round-trips, couples 3 domains | |
| Granular endpoints | Separate /client/membership + /client/bookings?upcoming; composed client-side; more reusable | |
| Hybrid | Granular endpoints as real contract + thin server-side fan-out /client/home reusing same query functions | ✓ |

**User's choice:** Hybrid

### Expiring / days-left derivation

| Option | Description | Selected |
|--------|-------------|----------|
| Server-derived | Backend returns end_date + daysUntilEnd + expiringSoon, reusing expiring-window logic + Europe/Moscow | ✓ |
| Raw dates only | Return end_date + status; PWA computes (DST/TZ risk) | |

**User's choice:** Server-derived

### Empty states

| Option | Description | Selected |
|--------|-------------|----------|
| 200 + null/empty | No membership → 200 null; no bookings → 200 empty list; own scope, valid state | ✓ |
| 404 for membership | 404 when no membership; conflates with IDOR 404-collapse | |

**User's choice:** 200 + null/empty

**Notes:** Empty state is deliberately distinct from the IDOR 404-collapse — the client owns their scope, so "nothing there" is a 200, never a 404.

---

## Catalog scope & fields

| Option | Description | Selected |
|--------|-------------|----------|
| New client_ routes | New /client/plans, /client/pt-packages, /client/trainers under Client-Portal tag; reuse staff query logic internally | ✓ |
| Reuse staff routes | Point PWA at staff endpoints; leaks staff contract, entangles frozen surface | |

**User's choice:** New client_ routes

### Field exposure

| Option | Description | Selected |
|--------|-------------|----------|
| Client-safe projection | Purchase-relevant fields only; strip economics, freeze_days_limit internals, audit, soft-delete, inactive/archived | ✓ |
| Full minus secrets | Most fields, hiding obvious internals; risks exposing economics | |

**User's choice:** Client-safe projection

---

## PWA TS ramp depth

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal bootstrap | tsconfig+allowJs+strict, pnpm, Vite 6, shared lint; new code in TS, leave .jsx screens | ✓ |
| Bootstrap + entry | Minimal + convert app shell (main/App/router/context) to TS | |
| Aggressive | Convert most of src/ to TS; large diff, regression risk on frozen UI | |

**User's choice:** Minimal bootstrap

### React version

| Option | Description | Selected |
|--------|-------------|----------|
| Stay on React 18 | Keep 18.3.1; stack alignment scoped to pnpm/TS/Vite-6, not React | ✓ |
| Bump to React 19 | Align with admin-web; adds migration risk this phase | |

**User's choice:** Stay on React 18

---

## PWA SW & test bar

| Option | Description | Selected |
|--------|-------------|----------|
| vite-plugin-pwa | Workbox; declarative manifest + shell precache; /api/* excluded via navigateFallbackDenylist + no runtime API caching | ✓ |
| Hand-rolled minimal SW | Tiny custom SW; zero deps but own cache-invalidation correctness | |

**User's choice:** vite-plugin-pwa

### Test bar

| Option | Description | Selected |
|--------|-------------|----------|
| Vitest + smoke test | Add Vitest + clientFetcher unit test + one render-without-crash; real CI gate | ✓ |
| Vitest, no tests yet | Wire Vitest to exit 0 with no tests; hollow gate | |

**User's choice:** Vitest + smoke test

---

## Claude's Discretion

- History endpoint pagination shape ({items,total,page,pageSize} convention; page size / ordering).
- Module placement of read endpoints relative to Phase-68 `client_auth` (client_portal aggregator locked by D-20-MODULE).
- `clientFetcher.ts` internals — refresh-on-401, error mapping, CSRF header handling.
- Per-IP/proxy handling, TS strictness flags, PWA ESLint import-boundary zones.

## Deferred Ideas

- PWA-05 (screens on real backend) → Phase 71.
- React 19 bump for client-pwa → later phase.
- Aggressive JS→TS conversion of existing screens → later phases.
- Full PWA UI test coverage → Phase 71+.
- Trainer ratings/reviews → net-new domain, stays mock (PWA-06).
