---
phase: 107-admin-fe-completion-on-existing-backend
reviewed: 2026-06-14T14:12:30Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - apps/admin-app/src/components/modals/PlanFormModal.tsx
  - apps/admin-app/src/components/modals/PtPackageActionDialogs.tsx
  - apps/admin-app/src/components/modals/PtPackageSellModal.tsx
  - apps/admin-app/src/pages/client/components/ProfileHeroReal.tsx
  - apps/admin-app/src/pages/client/components/TrainingsTab.tsx
  - apps/admin-app/src/pages/plans/PlansPage.tsx
findings:
  critical: 0
  warning: 5
  info: 6
  total: 11
status: issues_found
---

# Phase 107: Code Review Report

**Reviewed:** 2026-06-14T14:12:30Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Phase 107 wires five previously-stubbed actions (plan create/edit, PT-package
sell/cancel/refund, client export/delete entry points) onto already-shipped
TanStack Query hooks. The wiring is largely correct: mutation signatures match
the hook contracts (`{id, body}` for plan PATCH, `{packageId, body}` for
PT-package lifecycle, `{clientId, planId, amountKopecks}` for sell), the
hooks own their own toasts so modal `onSuccess` callbacks correctly only close,
`crypto.randomUUID()` Idempotency-Keys are generated per attempt, and `can()`
gating uses valid `(Action, Resource)` pairs that mirror the OWNER_ONLY matrix.
Semantic Tailwind tokens are used throughout (no raw palette leakage).

No BLOCKER-severity correctness or security defects were found. However, several
robustness defects warrant fixing before ship: a numeric-coercion gap that lets
`NaN`/non-integer values reach the validator path, a contradiction between the
"immutable" intent and the values actually re-sent on membership edit, an
RBAC-gate that checks the wrong action verb, an unguarded `usePtPackagePlans()`
default that can surface archived plans in the sell dropdown, and the
mutation-spinner not disabling the "Активен" toggle. The TrainingsTab role
plumbing also discards type safety unnecessarily.

## Narrative Findings (AI reviewer)

## Warnings

### WR-01: Number coercion lets `NaN` and floats reach the create path silently

**File:** `apps/admin-app/src/components/modals/PlanFormModal.tsx:153-159, 215-219`
**Issue:** Numeric fields are coerced with `Number(memDurationDays)` /
`Math.round(Number(memPriceRub) * 100)` etc. `<input type="number">` does NOT
guarantee a numeric string — browsers allow `e`, `+`, `-`, `.`, and multiple
separators in many cases, and the value can be an empty-after-trim or partial
token. `Number('1e')` → `NaN`, `Number('1.5e3')` → `1500`. The non-empty guard
(`=== '' ? undefined : Number(...)`) only filters the literal empty string, so a
malformed entry produces `NaN`, which `z.number().int()` will reject — but the
resulting Zod message ("Expected number, received nan") is not user-friendly and
the `isRequiredValid` button-enable check (`memDurationDays !== ''`) still
enables Submit for `"abc"`-style values that some locales/inputs permit. For
`priceKopecks`, a fractional ruble entry like `19.99` becomes `1999` kopecks via
`Math.round(19.99 * 100)` = `1999` (correct here), but `0.005` → `Math.round(0.5)`
= `1` kopeck silently, masking operator intent.
**Fix:** Guard with `Number.isFinite` and reject non-integer ruble input before
building the payload, or surface a dedicated field error:
```ts
const parsedDuration = Number(memDurationDays)
const durationDays =
  memDurationDays === '' || !Number.isInteger(parsedDuration) ? undefined : parsedDuration
// for price: validate Number.isFinite(Number(memPriceRub)) before *100
```

### WR-02: Membership edit re-sends `priceKopecks`/`freezeDaysLimit` despite "immutable" intent

**File:** `apps/admin-app/src/components/modals/PlanFormModal.tsx:183-188`
**Issue:** The module doc (lines 13-16) and the disabled+hint UI declare that on
membership edit `durationDays`, `priceKopecks`, and `freezeDaysLimit` are
immutable. `durationDays` is correctly omitted (the update schema drops it), but
the edit payload still builds and sends `priceKopecks` and `freezeDaysLimit`
from the prefilled (disabled) state. `MembershipPlanUpdateSchema` is
`CreateSchema.omit({durationDays}).partial()`, so both fields are valid update
keys and WILL be transmitted. Today this is a harmless no-op because the values
equal the stored values, but it (a) contradicts the stated immutability
contract, (b) creates a latent data-change vector if the prefill ever drifts
from the server value (e.g. a stale cache populates the disabled field with an
old price), and (c) the disabled `freezeDaysLimit` input means a plan that
*had* a freeze limit set will keep re-sending it, while a plan that had `null`
re-sends `undefined` — asymmetric round-tripping that depends on prefill state
rather than user intent.
**Fix:** On membership edit, send only the genuinely-mutable fields. Mirror the
PT-package edit path which sends `{ name }` only:
```ts
const raw = { name: memName.trim() || undefined, active: memActive }
const result = MembershipPlanUpdateSchema.safeParse(raw)
```
If `active` is the only other mutable field, exclude `priceKopecks` and
`freezeDaysLimit` from the edit payload entirely.

### WR-03: "Add tariff" / "Add service" buttons gated on `edit` action, but the action performed is `create`

**File:** `apps/admin-app/src/pages/plans/PlansPage.tsx:206-209, 307, 336, 409, 438`
**Issue:** The create-plan buttons are gated by
`canEditMembershipPlans = can(role, 'edit', 'membership-plans')` and
`canEditPtPackagePlans = can(role, 'edit', 'pt-package-plans')`, but clicking
them opens the form in `mode: 'create'`, which calls `useCreatePlan` /
`useCreatePtPackagePlan` (a `create` action). The OWNER_ONLY matrix lists both
`edit` and `create` for these resources, so for the two current roles the
boolean result is identical — but this is a coincidence, not correctness. If a
future role gains `edit` but not `create` (or vice versa), the gate will
authorize the wrong capability. The defense-in-depth check should match the
verb of the action it guards.
**Fix:** Gate create entry points with the `create` action:
```ts
const canCreateMembershipPlans = can(role, 'create', 'membership-plans')
const canCreatePtPackagePlans = can(role, 'create', 'pt-package-plans')
// use these for the "Добавить тариф"/"Добавить услугу" buttons;
// keep can(role, 'edit', …) only for the per-card Изменить button.
```

### WR-04: Sell modal can surface archived PT-package plans (shared cache with PlansPage)

**File:** `apps/admin-app/src/components/modals/PtPackageSellModal.tsx:55, 66`
**Issue:** The module doc claims "no args — backend default = active only", but
`usePtPackagePlans()` (no args) issues `query: {}` and shares its cache key
(`planList(undefined)`) with `PlansPage`, which intentionally renders archived
plans (`!plan.active && ' · Архив'` at PlansPage.tsx:158). If the backend default
for `includeArchived` is `false`, this happens to be safe; but the frontend does
not enforce it — whatever the shared query returns is what populates the sell
`<select>`. If the backend ever defaults to including archived plans (or if
PlansPage later switches to `usePtPackagePlans({ includeArchived: true })`,
poisoning the shared cache), an operator could sell an archived package. The
sell dropdown should not depend on an unstated backend default.
**Fix:** Either request active-only explicitly and/or filter client-side as
defense-in-depth:
```ts
const plans = (plansQuery.data?.items ?? []).filter((p) => p.active)
```
Note this also means the two callers should use distinct query options so the
sell view never inherits PlansPage's archived-inclusive cache.

### WR-05: "Активен" toggle stays interactive while the mutation is pending

**File:** `apps/admin-app/src/components/modals/PlanFormModal.tsx:415-420` (and `fields.tsx:387-407`)
**Issue:** Every other input in the form is disabled via `disabled={isPending}`,
and the modal blocks `onOpenChange` while pending — but `ToggleRow` accepts no
`disabled` prop, so the "Активен" switch remains clickable during the in-flight
create/update. A user can flip `active` after pressing Submit; the toggled value
is captured into local state but the already-dispatched mutation used the prior
value, producing a confusing UI/server mismatch until the success invalidation
refetches.
**Fix:** Thread a `disabled` prop through `ToggleRow`/`ToggleSwitch` and pass
`disabled={isPending}`, mirroring the other fields:
```tsx
<ToggleRow title="Активен" ... checked={memActive} onChange={setMemActive} disabled={isPending} />
```

## Info

### IN-01: `role` widened to `string` then cast back, discarding type safety

**File:** `apps/admin-app/src/pages/client/components/TrainingsTab.tsx:65, 106, 126`
**Issue:** `useSession().data?.role` is `'owner' | 'reception'` (a `Role`), but
`PtPackageRow` types its prop as `role: string` and then re-narrows with
`can(role as Parameters<typeof can>[0], 'cancel', 'pt-packages')`. The widening
+ cast is unnecessary and defeats the compiler's ability to catch an invalid
role at the call site.
**Fix:** Import `Role` (or `type Parameters<typeof can>[0]`) and type the prop
as `role: Role`; drop the cast.

### IN-02: Duplicated `ErrorCallout` helper across three modal files

**File:** `apps/admin-app/src/components/modals/PlanFormModal.tsx:58-71`,
`apps/admin-app/src/components/modals/PtPackageActionDialogs.tsx:31-44`,
`apps/admin-app/src/components/modals/PtPackageSellModal.tsx:21-36`
**Issue:** The same `ErrorCallout({ error })` helper is copy-pasted into three
files (PlanFormModal's header even notes it is "verbatim from SubscriptionModal
lines 81-94"). The Sell variant adds one extra branch (`amount_mismatch` skip).
Drift between copies is likely as messages evolve.
**Fix:** Promote a single `ErrorCallout` into `components/modals/fields.tsx` (or
a shared modal-helpers module) with an optional `skipCode?: string` prop, and
import it in all three.

### IN-03: 422 field-error → state mapping block duplicated four times

**File:** `apps/admin-app/src/components/modals/PlanFormModal.tsx:171-179, 201-209, 232-240, 257-265`
**Issue:** The identical `onError` body that walks `err.fields` and builds
`serverFieldErrors` is repeated verbatim in all four submit branches.
**Fix:** Extract a `mapApiFieldErrors(err): Record<string,string[]> | null`
helper and a shared `onError` closure; call it from each `.mutate(...)`.

### IN-04: `useEffect([open])` resets disable exhaustive-deps; prop changes while open are not re-applied

**File:** `apps/admin-app/src/components/modals/PlanFormModal.tsx:119-144`
**Issue:** The reset effect intentionally depends only on `[open]` (with an
eslint-disable). In the current PlansPage usage the modal is always fully closed
between opens, so `kind`/`mode`/`plan` are re-read on each false→true flip and
the behavior is correct. This is fragile: if any future caller changes
`kind`/`mode`/`plan` while leaving `open === true`, the form will silently keep
stale prefill. Document the invariant or key the modal on its identity.
**Fix:** Either add a `key={`${kind}-${mode}-${plan?.id ?? 'new'}`}` to the
`<PlanFormModal>` instance so React remounts on identity change, or include the
relevant props in the dependency array with a guarded reset.

### IN-05: "Экспорт карточки" is still a fake success toast

**File:** `apps/admin-app/src/pages/client/components/ProfileHeroReal.tsx:149-155`
**Issue:** The dropdown item fires `toast.success('Экспорт готов', { description:
'PDF · карточка клиента' })` without performing any export. This is a remaining
stub presenting success for an action that does nothing — misleading to the
operator. (Phase 107 scope is the five wired actions; flagging so it is tracked
rather than mistaken for shipped functionality.)
**Fix:** Either disable/hide the item until export is implemented, or change the
copy to indicate it is not yet available.

### IN-06: Inconsistent file conventions across the phase (semicolons / quotes)

**File:** `apps/admin-app/src/pages/client/components/ProfileHeroReal.tsx` and
`apps/admin-app/src/features/pt-packages/schemas.ts` use semicolons;
`PlanFormModal.tsx`, `PtPackageActionDialogs.tsx`, `PtPackageSellModal.tsx`,
`PlansPage.tsx`, and `features/plans/*` are semicolon-free.
**Issue:** Mixed semicolon style within the same phase's new/edited files.
Prettier should normalize this, but the divergence suggests files were authored
under different formatter assumptions. Confirm `pnpm -F @clubcore/admin-app lint`
and the Prettier config agree, so the style is enforced rather than incidental.
**Fix:** Run the repo formatter and let it settle one convention; no behavior
change.

---

_Reviewed: 2026-06-14T14:12:30Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
