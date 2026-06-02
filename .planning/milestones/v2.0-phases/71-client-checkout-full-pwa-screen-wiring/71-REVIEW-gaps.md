---
phase: 71-client-checkout-full-pwa-screen-wiring
reviewed: 2026-05-30T00:00:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - apps/backend/scripts/seed_demo_data.py
  - apps/client-pwa/public/sw.js
  - apps/client-pwa/src/screens/HomeScreen.jsx
  - apps/client-pwa/src/screens/ProfileScreen.jsx
  - apps/client-pwa/src/screens/sheets/PlansSheet.jsx
  - apps/client-pwa/src/services/pwa.js
findings:
  critical: 0
  warning: 3
  info: 4
  total: 7
status: issues_found
---

# Phase 71: Code Review Report (Gap-Closure: plans 71-08/09/10)

**Reviewed:** 2026-05-30
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Reviewed the gap-closure diff since base `35cdcc11`, covering the three live-UAT blockers:
SW `/api/*` caching (71-08), snake_case→camelCase render mismatch (71-09), and the
mock client identity / catalog seed (71-10).

The core fixes are sound and were verified against the actual backend contract:

- **camelCase migration is correct.** The backend `ContractModel` base
  (`apps/backend/app/core/schemas.py:24-33`) uses `alias_generator=to_camel`, and FastAPI
  serializes `response_model` with `response_model_by_alias=True` (default), so the wire
  format is genuinely camelCase. Every field the screens now read
  (`daysUntilEnd`, `expiringSoon`, `planNameSnapshot`, `startDate`, `endDate`, `nextBooking`,
  `trainerName`, `startTime`, `gymDate`, `checkedInAt`, `trainerNameSnapshot`, `performedAt`,
  `cancelledAt`, `amountKopecks`, `subjectKind`, `receivedAt`, `priceKopecks`, `durationDays`,
  `sessionCount`, and the `/client/me` `firstName`/`lastName`/`phone`/`email`) matches the
  serialized contract. No residual snake_case reads remain in the reviewed screens.
- **SW `/api/*` network-only guard is correctly placed** before both the navigation and
  cache-first branches, and is keyed off `url.pathname` (correct for the same-origin dev proxy).
- **Seed catalog columns are valid.** `MembershipPlan` (`name`, `duration_days`, `price_kopecks`,
  `freeze_days_limit`, `active`) and `PtPackagePlan` (`name`, `session_count`, `price_kopecks`,
  `validity_days`) match the ORM models; `PtPackagePlan` correctly omits a non-existent `active`
  column; values satisfy all CHECK constraints; the catalog repository filters
  (`active = true` for plans, `deleted_at IS NULL` for PT) will surface both seeded rows.

Remaining issues are wiring/quality defects introduced by the migration — chiefly a now-broken
`currentPlanId` contract and orphaned demo code.

## Warnings

### WR-01: `currentPlanId` passed to PlansSheet is a dead mock slug — "current plan" detection silently broken

**File:** `apps/client-pwa/src/screens/sheets/PlansSheet.jsx:43,63-66,127,148,179`
(root cause manifests via caller `apps/client-pwa/src/App.jsx:260`)

**Issue:** After the 71-09 migration, `PlansSheet` builds card ids from the real backend UUID
via `id: String(p.id)` (lines 14, 31) and compares selection/current-plan state with
`p.id === currentPlanId` (lines 64, 127, 148, 179). But the only caller still passes the legacy
hardcoded mock slug:

```jsx
// App.jsx:260
currentPlanId={t.subState === 'active' ? 'annual' : 'monthly'}
```

`'annual'`/`'monthly'` can never equal a UUID string, so:
- the default-selection branch `allPlans.find(p => p.id === currentPlanId)` (line 64) never matches
  and silently falls through to `find(p => p.popular) ?? allPlans[0]`;
- the `isCurrent` badge (` · сейчас активен`, line 257) never renders;
- the CTA "Текущий тариф" disabled-state guard (line 179) is dead — a user can always re-purchase
  the plan they already own with no "current" indication.

This is a correctness regression: the screen claims to know the user's current plan but the
contract is broken end-to-end. Note the real "current plan" is also not derivable from
`tweaks.subState` anymore — the membership response exposes `planNameSnapshot`, not a catalog
plan id, so matching the active membership back to a catalog card needs a real source (e.g. a
plan-id on the membership, or name match) rather than a dev tweak.

**Fix:** Drive `currentPlanId` from real data, or remove the contract until a real source exists.
Minimum: stop passing a slug that can never match. If "current plan" cannot be resolved from the
membership payload, pass `undefined` and drop the `isCurrent`/"Текущий тариф" affordances rather
than leaving permanently-dead branches:

```jsx
// App.jsx — until membership exposes a catalog plan id, do not fake it
<PlansSheet onClose={...} onPick={...} />   // currentPlanId omitted
```

### WR-02: `subTotalDays` underflows by one day → progress bar can momentarily show 100%+ clamp / off-by-one duration

**File:** `apps/client-pwa/src/screens/HomeScreen.jsx:19-25` (and the mirror in
`apps/client-pwa/src/screens/ProfileScreen.jsx:40-46`)

**Issue:** `subTotalDays` returns the exclusive day-span `(end - start) / 86_400_000` (e.g. a
membership of `start_date=2026-01-01`, `end_date=2026-01-31` yields `30`). But `daysUntilEnd` is
computed server-side as `end_date - today` *inclusive of the current day's remaining time*
(`apps/backend/app/modules/client_portal/repository.py:151`,
`(end_date - now()::date)`), which on the **start date** equals the full inclusive duration
(`31 - 1 = 30` for the example, but for a 30-day plan created same-day `end_date - start_date`
can equal `daysLeft`). The two values use different day-counting conventions (inclusive remaining
vs exclusive span), so `daysLeft / total` can exceed 1 on day zero, and the progress fill is then
clamped to 100% (`Math.min(100, ...)`, line 132 / ProfileScreen:112) — masking a real
off-by-one. On the visual it is minor, but the derived "total membership length" shown to the user
(and any future use of `sub.total`) is one day short of the real plan duration.

**Fix:** Make the span inclusive to match the server's day count:

```js
return Math.max(0, Math.round((end - start) / 86_400_000) + 1)
```

and verify against `daysUntilEnd` on the first day so `pct` starts at ~100 without clamping.
Also factor the duplicated `subTotalDays`/`toSubInfo` pair into one shared module rather than two
hand-synced copies (see IN-02).

### WR-03: Seed catalog commits twice in one logical unit — partial-failure leaves owner seeded but catalog missing

**File:** `apps/backend/scripts/seed_demo_data.py:84,127,143`

**Issue:** `_run` commits the owner insert at line 127, then `_seed_catalog` issues its own
`session.commit()` at line 84 after both catalog inserts. The two catalog inserts share one commit
(good), but if `_seed_catalog` raises (e.g. a constraint violation from a future column change, or
a connection blip) *after* the owner commit, the script exits non-zero with the owner persisted but
the catalog absent — a non-atomic, partially-applied seed. Re-running is idempotent for the owner
but the operator gets a confusing "already exists" no-op while the catalog silently stays empty if
the failure is deterministic. For a one-shot operator command this is a robustness gap, not a data-
loss bug, but the "seed succeeded" mental model is violated.

**Fix:** Either wrap the whole seed (owner + catalog) in a single transaction/commit, or make the
final summary explicitly report catalog state. Minimal:

```python
await session.execute(stmt)          # owner
await _seed_catalog_statements(session)   # no inner commit
await session.commit()               # single atomic commit
```

(move the `await session.commit()` out of `_seed_catalog` into the caller after all inserts).

## Info

### IN-01: `subInfo.js` is now orphaned dead code

**File:** `apps/client-pwa/src/utils/subInfo.js` (importers removed in this diff)

**Issue:** The 71-09 migration removed the last two `import { getSubInfo } from '@/utils/subInfo.js'`
statements (HomeScreen + ProfileScreen). `getSubInfo` now has zero importers; the module is dead.
The only remaining mention is a comment at `HomeScreen.jsx:97`.

**Fix:** Delete `apps/client-pwa/src/utils/subInfo.js` and drop the stale comment reference.

### IN-02: `toSubInfo` + `subTotalDays` duplicated verbatim across two screens

**File:** `apps/client-pwa/src/screens/HomeScreen.jsx:19-44` and
`apps/client-pwa/src/screens/ProfileScreen.jsx:18-46`

**Issue:** Both screens now `export function toSubInfo` and define an identical `subTotalDays`.
The ProfileScreen comment even says "Mirrors the adapter in HomeScreen.jsx". Hand-synced copies
mean a fix to one (e.g. WR-02) will silently diverge. Both are exported, suggesting tests import
them — two export sites for one logical adapter invites drift.

**Fix:** Extract a single `toSubInfo`/`subTotalDays` into a shared module (e.g.
`@/lib/membershipAdapter.js`) and import from both screens and tests.

### IN-03: `tweaks.subState` dev control is now inert for the sub display

**File:** `apps/client-pwa/src/components/Tweaks/TweaksRoot.jsx:71-77`,
`apps/client-pwa/src/context/TweaksContext.jsx:9`

**Issue:** Before 71-09, `tweaks.subState` drove `getSubInfo(tweaks.subState)` for the home/profile
sub card. The migration replaced that with real API data, so the `subState` segmented control in
the dev Tweaks panel no longer affects the subscription card at all — it only feeds the broken
`currentPlanId` slug (WR-01). The control is now misleading to anyone using the dev panel for UAT.

**Fix:** Remove the `subState` control (and its `TweaksContext` default) or repoint it at something
it still drives. Coordinate with WR-01.

### IN-04: Hardcoded demo card/economics strings still present on production-wired ProfileScreen

**File:** `apps/client-pwa/src/screens/ProfileScreen.jsx:127,483,505`

**Issue:** The screen is now wired to real `/client/me` + `/client/home` data, but several
hardcoded demo placeholders survive on the same surface: `Карта •••• 4821` (line 127 and the
`NavRow` at 483), and the app version `Версия 2.4.1` (line 505 — likely fine if intentional).
The card-mask is shown unconditionally for expired memberships and as a settings row even though no
card data comes from the API. On a real client account this displays a fabricated card number.

**Fix:** Gate the card affordances behind real payment-method data, or replace `•••• 4821` with a
neutral placeholder / hide it until a card endpoint exists. (Out of strict gap scope, but it sits
directly in the migrated render path and undermines the "real identity" goal of 71-10.)

---

_Reviewed: 2026-05-30_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
