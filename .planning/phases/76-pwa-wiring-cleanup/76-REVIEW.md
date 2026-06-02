---
phase: 76-pwa-wiring-cleanup
reviewed: 2026-06-02T00:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - apps/client-pwa/src/App.jsx
  - apps/client-pwa/src/data/index.js
  - apps/client-pwa/src/lib/clientQueries.ts
  - apps/client-pwa/src/lib/clientQueries.trainers.test.ts
  - apps/client-pwa/src/screens/HomeScreen.jsx
  - apps/client-pwa/src/screens/HomeScreen.identity.test.jsx
  - apps/client-pwa/src/screens/sheets/ProfileExtraSheets.jsx
  - apps/client-pwa/src/screens/sheets/PersonalDataSheet.identity.test.jsx
findings:
  critical: 2
  warning: 5
  info: 3
  total: 10
status: issues_found
---

# Phase 76: Code Review Report

**Reviewed:** 2026-06-02T00:00:00Z
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

Phase 76 wired the newbie Home trainer strip + plan-info chip and the Personal Data
sheet to existing client-portal endpoints, and removed the `conversations.js` mock.

The Personal Data sheet wiring (PATCH payload shaping, enum-constrained goal control,
hydration effect, mutateAsync error handling, in-sheet toast) is correct and well-tested.
The `conversations.js` mock removal is clean — no dangling imports.

However, **both newly wired Home features read the wrong wire field names** and will
fail silently against the real backend. The unit tests pass only because their mock
fixtures fabricate snake_case field names (`price_kopecks`, `full_name`) that do not
match the authoritative camelCase wire contract defined in `apps/backend/openapi.json`
(`ClientCatalogPlanResponse` → `priceKopecks`/`durationDays`; `ClientCatalogTrainerResponse`
→ `fullName`). The tests validate the implementation against itself, not against the API.
This is the exact "tests pass ≠ correct" failure mode. Both are BLOCKERs because the
shipped features render broken output (`"…/мес"` shows `"не число ₽"`; trainer avatars
show empty initials) in production.

## Critical Issues

### CR-01: Plan-info chip reads snake_case fields that don't exist on the wire → renders "не число ₽"

**File:** `apps/client-pwa/src/screens/HomeScreen.jsx:545-546`
**Issue:**
The min-monthly-price chip computes:
```js
Math.min(...plans.map(p => Math.round(p.price_kopecks / (p.duration_days / 30))))
```
The `/api/v1/client/plans` endpoint returns `ClientCatalogPlanResponse` with **camelCase**
fields `priceKopecks` and `durationDays` (verified in `apps/backend/openapi.json`, and
already consumed correctly as camelCase in `PlansSheet.jsx:9-10` which is fed by the same
endpoint). Reading `p.price_kopecks` / `p.duration_days` yields `undefined`:

`Math.round(undefined / (undefined/30))` → `NaN` → `Math.min(...[NaN, ...])` → `NaN` →
`formatMoney(NaN)` → `Intl.NumberFormat('ru-RU').format(NaN)` → the literal string
`"не число ₽"`. The chip renders `"N тарифов · от не число ₽/мес"` for every real user.

The render guard `plans && plans.length > 0` does NOT protect against this — `plans` is a
non-empty array; only the per-item field reads are wrong.

The test (`HomeScreen.identity.test.jsx:220-225`) passes only because it fabricates
`price_kopecks: 150000, duration_days: 30` mock objects that contradict the real wire shape.

**Fix:**
```js
Math.min(...plans.map(p => Math.round(p.priceKopecks / (p.durationDays / 30))))
```
Additionally guard against divide-by-zero / non-finite (a plan with `durationDays === 0`
yields `Infinity`, and a malformed plan yields `NaN`, both poisoning `Math.min`):
```js
const monthly = plans
  .map(p => (p.durationDays > 0 ? Math.round(p.priceKopecks / (p.durationDays / 30)) : null))
  .filter((v) => Number.isFinite(v))
// render the chip price only when monthly.length > 0
```
And update the test fixture to camelCase so it actually exercises the wire contract.

### CR-02: Trainer avatar strip reads `full_name`/`name` that don't exist → empty initials

**File:** `apps/client-pwa/src/screens/HomeScreen.jsx:1009` (and count/key logic 993-1012)
**Issue:**
The avatar initial is derived via:
```js
{[...(tr.full_name ?? tr.name ?? '').trim()][0]}
```
`/api/v1/client/trainers` returns `ClientCatalogTrainerResponse` with only `id` and
**`fullName`** (camelCase — verified in `apps/backend/openapi.json`). Neither `full_name`
nor `name` exists on the real payload, so every live trainer falls through to `''` and the
initial is `undefined` — the strip renders blank colored circles for real data.

Because `liveTrainers` is a non-empty array of valid objects, the fail-open branch
(`STATIC_TRAINERS_FALLBACK`) is NOT taken (`liveTrainers.length > 0` is true), so the
broken live path is what ships. The count `+N` overflow badge still works (it uses
`.length`), making the bug subtle: correct count, blank initials.

The test (`HomeScreen.identity.test.jsx:200-213`) passes only because it fabricates
`full_name: 'Олег Борисов'` fixtures — contradicting the wire contract. The static fallback
mock (`trainers.js`) uses `name`, which is why `?? tr.name` was added, but live data uses
neither.

**Fix:**
Read the camelCase wire field, keeping `name` only for the static fallback shape:
```js
{[...(tr.fullName ?? tr.name ?? '').trim()][0]}
```
Update the live-trainer test fixture to use `fullName` so it validates the real contract.

## Warnings

### WR-01: Newbie auto-redirect effect depends on `homeData`/`me` objects → re-fires on every refetch identity change

**File:** `apps/client-pwa/src/screens/HomeScreen.jsx:245-253`
**Issue:**
The `/onboarding` redirect effect lists `[homeData, me, navigate]` as deps. TanStack Query
returns a new object reference on every refetch/invalidation (and Phase 76's profile
mutations invalidate `clientPortalKeys.home()` + `.me()`). Each new reference re-runs the
effect. The guard `!me.onboardingCompletedAt && !me.goal && !me.heightCm && !me.weightKg`
plus `replace: true` mostly contains this, but if the gate condition is still true (e.g.
the user lands on Home, the data refetches, and onboarding is genuinely incomplete) the
effect will issue `navigate('/onboarding', { replace: true })` repeatedly. This is fragile;
the intended "fires once" semantics (per the comment) are not actually enforced by a ref
guard the way the QR-signal effect at `App.jsx:102-111` is.
**Fix:** Add a `hasRedirected` ref guard mirroring the `handledQrSignal` pattern, or key the
effect on primitive values only (`[homeData?.membershipState, me?.onboardingCompletedAt, ...]`)
and short-circuit once redirected.

### WR-02: `heightCm`/`weightKg` parsed with `Number()` can send NaN for non-numeric input

**File:** `apps/client-pwa/src/screens/sheets/ProfileExtraSheets.jsx:106-107`
**Issue:**
```js
heightCm: heightCm ? Number(heightCm) : undefined,
weightKg: weightKg ? Number(weightKg) : undefined,
```
The inputs are `type="number"` (`FormRow ... type="number"`), but `type=number` still
permits intermediate values like `"1e"`, `"--"`, or `"1.2.3"` via paste/keyboard in several
browsers, and `Number("1e")` → `NaN`. The phase requirement explicitly states
"height/weight parsed to integers (no NaN sent)". `Number('12.5')` also yields `12.5`
(non-integer) which would be sent to an integer column. A truthy-but-invalid string thus
PATCHes `NaN`/float to the server.
**Fix:** Parse with integer coercion and drop non-finite values:
```js
const h = parseInt(heightCm, 10)
const w = parseInt(weightKg, 10)
// ...
heightCm: Number.isFinite(h) ? h : undefined,
weightKg: Number.isFinite(w) ? w : undefined,
```

### WR-03: `useClientMe()` called without coordinating `enabled` — fires on every screen that mounts the sheet/home

**File:** `apps/client-pwa/src/screens/sheets/ProfileExtraSheets.jsx:50`, `HomeScreen.jsx:233`
**Issue:** `useClientMe()` is invoked with no args, defaulting `enabled = true`. This is
fine functionally (shared query key dedupes), but the hydration `useEffect` at
`ProfileExtraSheets.jsx:71-78` depends on `[meData]`. Because `meData` is a fresh object
reference after any invalidation (the profile mutation invalidates `.me()`), the effect
re-runs and **overwrites the user's in-progress edits** with server data while the sheet is
open. If a save succeeds (`onSuccess` seeds + `onSettled` invalidates `.me()`), the hydration
effect fires and resets `name`/`email`/`goal`/`height`/`weight` from the refetched payload —
acceptable post-save, but any concurrent background refetch (window refocus is disabled
globally, but invalidation from another mutation is not) would clobber unsaved edits.
**Fix:** Hydrate only once (guard with a `hydrated` ref) or gate the effect so it does not
overwrite locally-dirty fields:
```js
const hydrated = React.useRef(false)
React.useEffect(() => {
  if (!meData || hydrated.current) return
  hydrated.current = true
  // ...setName etc.
}, [meData])
```

### WR-04: `onSave` toggles `setSaved(true)` even when nothing was actually persisted on phone-change branch

**File:** `apps/client-pwa/src/screens/sheets/ProfileExtraSheets.jsx:96-115`
**Issue:** When `phone !== initialPhone.current`, `onSave` calls
`window.__openSmsVerify?.(...)` and `return`s early — but `phone` is sourced read-only from
the API (`FormRow ... onChange={() => {}}`), so `phone` can never diverge from
`initialPhone.current` in this sheet. The entire SMS-verify branch is dead code for this
component (phone is never editable here). It is harmless but misleading, and the
`initialPhone` ref + effect at lines 82-85 exist only to support an unreachable path.
**Fix:** Remove the dead phone-change branch and the `initialPhone` ref/effect, or make phone
genuinely editable. If retained for future editability, add a comment that the branch is
currently unreachable.

### WR-05: `formatMoney`/min-price has no empty-after-filter guard once CR-01 is fixed

**File:** `apps/client-pwa/src/screens/HomeScreen.jsx:542-550`
**Issue:** The render condition is `plans && plans.length > 0`. After fixing CR-01 to filter
out zero-duration/non-finite plans, it is possible for `plans.length > 0` to be true while
the filtered monthly array is empty (e.g. all plans have `durationDays === 0`), reproducing
`Math.min(...[])` → `Infinity` → `formatMoney(Infinity)` → `"∞ ₽"`. The guard must be on the
computed price array, not the raw `plans` array.
**Fix:** Compute `monthly` first; render the chip with the price only when
`monthly.length > 0`, otherwise render the count-only chip or fall through to the hardcoded
layout (D-76-09 fail-open).

## Info

### IN-01: `badge` destructured from `deriveOnboardingSteps` but unused in `HomeNewbie`

**File:** `apps/client-pwa/src/screens/HomeScreen.jsx:842`
**Issue:** `const { steps, doneCount, title, badge } = deriveOnboardingSteps(...)` — `badge`
is computed and destructured but only forwarded to `OnboardingStrip` (which also ignores it;
the ring renders `{doneCount}/4` inline at line 644, not `badge`). With
`noUnusedLocals`/`noUnusedParameters` this is JS (not TS) so it won't error, but it is dead
data flow. `OnboardingStrip`'s `badge` prop (line 586) is never read either.
**Fix:** Drop `badge` from the destructure and the `OnboardingStrip` prop list, or render it.

### IN-02: Stale hardcoded conversation id `'c2'` after CONVERSATIONS mock removal

**File:** `apps/client-pwa/src/App.jsx:226, 310`
**Issue:** `setTimeout(() => ui.setPendingChat('c2'), 360)` references conversation id `'c2'`
from the deleted `conversations.js` mock. `ChatScreen` is now a `ComingSoon` placeholder that
ignores `initialConv` entirely, so these writes are harmless dead state. Not introduced by
this phase's core scope, but it is leftover coupling to the removed mock domain.
**Fix:** Drop the `setPendingChat('c2')` calls (and the `pendingChat` plumbing) when chat is a
placeholder, or leave a `// TODO Phase N:` marker noting the id is a stale placeholder.

### IN-03: Hardcoded hex colors where semantic tokens exist (CLAUDE.md convention)

**File:** `apps/client-pwa/src/screens/HomeScreen.jsx:1004-1005` (`#6ee7c4`, `#ffffff`),
`HomeScreen.jsx:108, 165, 173` (`#10b981`), `HomeScreen.jsx:153` (`#f43f5e`)
**Issue:** CLAUDE.md mandates semantic design tokens (no hardcoded hex where a token exists).
The trainer-strip avatar mixes a raw `#6ee7c4` into the accent and forces `color: '#ffffff'`
for the third avatar; presence/badge dots use raw `#10b981`/`#f43f5e`. Some of these predate
Phase 76, but the trainer-strip hex (1004-1005) is new in this phase's wiring block.
**Fix:** Replace with `var(--on-accent)` / an accent-mix token / a semantic success/danger
token consistent with the rest of the file (which already uses `var(--accent-deep)`,
`color-mix(in oklab, var(--accent) …)`).

---

_Reviewed: 2026-06-02T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
