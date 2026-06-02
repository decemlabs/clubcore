---
phase: 78-pmem-notif-promo-frontend-surfacing
reviewed: 2026-06-02T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - apps/client-pwa/src/screens/ProfileScreen.jsx
  - apps/client-pwa/src/screens/SettingsScreen.jsx
  - apps/client-pwa/src/lib/clientQueries.ts
  - apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx
findings:
  critical: 0
  warning: 3
  info: 2
  total: 5
status: issues_found
---

# Phase 78: Code Review Report

**Reviewed:** 2026-06-02
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Phase 78 surfaced three backend-complete fields in the client PWA: membership price + auto-renew (PMEM-01), server-backed notification toggles (NOTIF-01), and the recommended-promo chip flag flip (PROMO-01).

I verified the wire contract directly against `apps/backend/app/modules/client_portal/schemas.py`:

- `ClientMembershipResponse.price_kopecks` / `auto_renew` serialize to `priceKopecks` / `autoRenew` via `alias_generator=to_camel` (inherited `ResponseData → ContractModel`). ProfileScreen reads `membership.priceKopecks` / `membership.autoRenew` — **correct camelCase, no snake_case regression.**
- `ClientMeResponse.notif_prefs` → wire `notifPrefs`; nested `NotifPrefs` keys (`promo/schedule/trainer/sound`) are single-word and unchanged by `to_camel`. SettingsScreen reads `me.notifPrefs.{promo,schedule,trainer,sound}` — **correct.**
- `NotifPrefs(BackendSchemaBase)` is `extra="forbid"` with all four fields required → a partial object would 422. `setNotifKey` always sends a full 4-key object — **the full-replace contract is honored.**
- `localStorage` / `NOTIF_STORAGE_KEY` is fully removed from `SettingsScreen.jsx` — no dead references remain.
- PROMO-01: the chip `onClick={() => handlePromoApply(RECOMMENDED_PROMO.code)}` passes a string (not the event), the `typeof codeArg === 'string'` guard in `handlePromoApply` handles it, and the chip is gated behind `!promoResult`. **Correct.**
- PMEM-01 auto-renew: hidden for both `null` and `undefined` (`membership.autoRenew !== null && membership.autoRenew !== undefined`), and the whole price block is gated on `priceKopecks > 0`, so `false`/loading do not produce an empty row. **Correct; no "false shows nothing" bug.**

The contract-class bugs that bit earlier phases are NOT present here. However, the NOTIF-01 optimistic-update logic has a real concurrency defect and two robustness gaps, detailed below.

## Warnings

### WR-01: Concurrent toggle taps lose the first change (stale-closure full-replace)

**File:** `apps/client-pwa/src/screens/SettingsScreen.jsx:61-71`
**Issue:** `setNotifKey` builds the full 4-key payload from `notif` read directly out of the render closure, not via a functional state updater:

```js
const setNotifKey = async (key, val) => {
  const prior = notif;
  const next = { promo: notif.promo, schedule: notif.schedule, trainer: notif.trainer, sound: notif.sound, [key]: val };
  setNotif(next);
  await updateProfile.mutateAsync({ notifPrefs: next });
  ...
};
```

If the user taps two different switches before React commits the first `setNotif` (entirely plausible with rapid touches), both handler invocations close over the *same* pre-first-tap `notif`. The second `next` is rebuilt from stale state and therefore **omits the first tap's change**. Because every PATCH is a full 4-key replace against an `extra="forbid"`/all-required backend, the second request clobbers the first on the server. Example: tap promo→false then schedule→false rapidly; the second PATCH sends `promo:true`, and the server ends with promo re-enabled. The `prior = notif` revert path inherits the same stale snapshot, so an error revert can also restore the wrong value. This is the exact "second toggle does not include the first's change" race called out in the review brief, and it is currently unguarded.

**Fix:** Derive `next` from the functional updater so each toggle composes on the latest committed state, and capture `prior` inside the updater:

```js
const setNotifKey = async (key, val) => {
  let prior;
  let next;
  setNotif((cur) => {
    prior = cur;
    next = { ...cur, [key]: val };
    return next;
  });
  try {
    await updateProfile.mutateAsync({ notifPrefs: next });
  } catch {
    setNotif((cur) => ({ ...cur, [key]: prior[key] }));
    showToast('Не удалось сохранить настройки. Попробуйте ещё раз.');
  }
};
```

(Reverting only the single `key` rather than the whole `prior` object avoids stomping a concurrent toggle on the error path too.)

### WR-02: In-flight optimistic toggle can be clobbered by a server re-sync

**File:** `apps/client-pwa/src/screens/SettingsScreen.jsx:44-48` (in concert with `clientQueries.ts:235-238`)
**Issue:** The re-sync effect unconditionally overwrites local state whenever `me.notifPrefs` changes identity:

```js
React.useEffect(() => {
  if (me?.notifPrefs) setNotif(me.notifPrefs);
}, [me?.notifPrefs]);
```

`useUpdateClientProfile.onSettled` invalidates `clientPortalKeys.me()`. If that refetch (or any other `me` invalidation — e.g. `AuthContext` line 105-106, or a checkout flow that touches `/client/me`) resolves while a *different* toggle's PATCH is still in flight, the effect runs `setNotif(server)` using a server value that does not yet reflect the in-flight optimistic change — visibly reverting the switch mid-flight until the second PATCH settles. The optimistic `setNotif(next)` in `setNotifKey` is not protected against an interleaved authoritative refetch. The single-toggle tests pass because nothing else invalidates `me` during the test, so this gap is untested.

**Fix:** Suppress re-sync while a mutation is pending, e.g. gate the effect on `updateProfile.isPending` being false, or skip the `setNotif` when the incoming server value is shallow-equal to the current optimistic state. Minimal version:

```js
React.useEffect(() => {
  if (me?.notifPrefs && !updateProfile.isPending) setNotif(me.notifPrefs);
}, [me?.notifPrefs, updateProfile.isPending]);
```

### WR-03: Error toast can mask a successful save under interleaved failures

**File:** `apps/client-pwa/src/screens/SettingsScreen.jsx:61-71`
**Issue:** On a failed `mutateAsync`, the handler does `setNotif(prior)` where `prior` is the closure snapshot from this handler's render. Combined with WR-01, if two toggles overlap and the first succeeds but the second fails, the catch restores `prior` (the state from before the *second* tap), which still contains the first tap's optimistic value — but the revert and the success-path `onSuccess` cache seed can land out of order, leaving the UI inconsistent with the server (UI shows the reverted second toggle while the server retained the first toggle's committed value, or vice-versa). There is no mutation serialization, so overlapping PATCHes resolve in arbitrary order while both mutate the same 4-key object. This is a maintainability/robustness hazard distinct from WR-01: even after fixing the closure read, overlapping full-replace mutations have no last-writer-wins guarantee.

**Fix:** Serialize toggle mutations (queue them, or disable the switches while `updateProfile.isPending`), so each full-replace PATCH observes the committed result of the prior one. Disabling during pending is the smallest change and also resolves the WR-02 interleave:

```jsx
<SettingRow label="Акции и скидки" value={notif.promo}
  disabled={updateProfile.isPending}
  onChange={(v) => setNotifKey('promo', v)} />
```

(`SettingRow` would need to forward `disabled` to the `<button>`.)

## Info

### IN-01: Recommended-promo chip wired to a placeholder code that will 422 for users

**File:** `apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx:45-50, 453-465`
**Issue:** PROMO-01 flips `recommendedPromo: true`, but `RECOMMENDED_PROMO = { code: 'FIT15', ... }` is an explicitly-labeled placeholder ("Placeholder until a real 'recommended promo' source exists on the backend"). Unless `FIT15` is a real server-known promo, every tap routes through `handlePromoApply` → `promoValidate.mutateAsync` → 422 and surfaces a "Промокод не найден" error to the user. The chip is now visible in production while pointing at a code with no guaranteed backend existence. Functionally the flow is correct (server-authoritative validation), but flipping the flag on without confirming `FIT15` exists ships a chip that may only ever error.

**Fix:** Confirm `FIT15` is a seeded/active promo code before enabling the chip in production, or keep the chip gated until a real recommended-promo source exists. If `FIT15` is intentionally seeded for this milestone, document that in the flag comment.

### IN-02: `window.__openSubManage` global is an untyped escape hatch

**File:** `apps/client-pwa/src/screens/ProfileScreen.jsx:217`
**Issue:** The Freeze button calls `window.__openSubManage?.('freeze')`. This pre-existing global-on-window pattern bypasses the component prop/router contract and is invisible to type checking. Not introduced by this phase, but it sits adjacent to the PMEM-01 changes in the membership hero and is worth flagging as a coupling smell.

**Fix:** Thread a `onManageSubscription` prop (like the sibling `onOpenPlans`) instead of reaching through `window`.

---

_Reviewed: 2026-06-02_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
