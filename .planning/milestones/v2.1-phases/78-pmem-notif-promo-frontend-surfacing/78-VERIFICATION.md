---
phase: 78-pmem-notif-promo-frontend-surfacing
verified: 2026-06-02T23:30:00Z
status: human_needed
score: 3/3 must-haves code-verified
overrides_applied: 0
human_verification:
  - test: "PROMO-01 live checkout — subscription context"
    expected: "FIT15 chip is visible in the Промокод section when no promo applied; one tap shows chip disabled, triggers POST /client/promo/validate, resolves to discounted amount, chip disappears"
    why_human: "Requires running backend with FIT15 seeded (migration 0051) + PWA dev server; cannot verify server-round-trip or chip DOM visibility in a browser without running the full stack"
  - test: "PROMO-01 live checkout — PT context"
    expected: "FIT15 chip also surfaces in the personal-training checkout (ctx.kind='pt'); one tap applies FIT15 and shows discounted amount"
    why_human: "Same as above — requires live stack; automated tests do not cover CheckoutSheet (no test file for it)"
  - test: "NOTIF-01 persistence after full page reload"
    expected: "Toggle a notif setting, reload the browser, confirm the setting is still as toggled (i.e. server round-trip persisted it, not localStorage)"
    why_human: "Persistence across a real reload requires GET /client/me to return the updated notifPrefs from the database; can only be confirmed end-to-end against the running backend"
---

# Phase 78: PMEM/NOTIF/PROMO Frontend Surfacing Verification Report

**Phase Goal:** Surface the backend-complete v2.1 fields in the PWA UI: membership price + auto-renew on Profile; Settings notif toggles server-backed; FIT15 promo chip in checkout. Closes the v2.1 audit frontend-surfacing tech debt.
**Verified:** 2026-06-02T23:30:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | PMEM-01: Profile shows membership priceKopecks via formatMoney + auto-renew hidden when null, from useClientMembership() | ✓ VERIFIED | ProfileScreen.jsx lines 76, 189-211: useClientMembership() called; price row gated `membership != null && typeof priceKopecks === 'number' && priceKopecks > 0`; auto-renew gated `!== null && !== undefined`; formatMoney() called at line 194. camelCase fields confirmed. 4 vitest tests covering all branches pass. |
| 2 | NOTIF-01: Toggles hydrate from GET /client/me notifPrefs; PATCH sends full 4-key notifPrefs; localStorage dropped; race fixes present | ✓ VERIFIED | SettingsScreen.jsx: `useClientMe().notifPrefs` drives the `useEffect` re-sync (lines 50-55); `notifRef` pattern resolves WR-01 stale-closure; `!updateProfile.isPending` guard resolves WR-02 mid-flight clobber; per-key revert resolves WR-03. `NOTIF_STORAGE_KEY` count in src/: 0. `useUpdateClientProfile` payload type includes `notifPrefs`. 6 vitest tests pass. |
| 3 | PROMO-01: CHECKOUT_FEATURE_FLAGS.recommendedPromo === true; chip onClick passes string code; !promoResult gate intact | ✓ VERIFIED | CheckoutSheet.jsx line 46: `recommendedPromo: true`. Line 453: `CHECKOUT_FEATURE_FLAGS.recommendedPromo && !promoResult`. Line 458: `onClick={() => handlePromoApply(RECOMMENDED_PROMO.code)}` passes string 'FIT15'. Gate is intact. |

**Score:** 3/3 truths code-verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/client-pwa/src/screens/ProfileScreen.jsx` | useClientMembership import + price/auto-renew rows | ✓ VERIFIED | Lines 12 (import), 76 (call), 188-211 (price + auto-renew rows with correct guards) |
| `apps/client-pwa/src/screens/SettingsScreen.jsx` | Server-backed notif toggles, no localStorage | ✓ VERIFIED | notifRef pattern + !isPending guard + per-key revert; NOTIF_STORAGE_KEY absent (count: 0) |
| `apps/client-pwa/src/lib/clientQueries.ts` | notifPrefs in useUpdateClientProfile payload type | ✓ VERIFIED | Lines 227: `notifPrefs?: { promo: boolean; schedule: boolean; trainer: boolean; sound: boolean }` |
| `apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx` | recommendedPromo: true; !promoResult gate; string code onclick | ✓ VERIFIED | Lines 46-48, 453-464 |
| `apps/client-pwa/src/screens/ProfileScreen.membership.test.jsx` | 4 vitest tests for PMEM-01 render branches | ✓ VERIFIED | File exists; all 4 tests pass in the 92-test suite |
| `apps/client-pwa/src/screens/SettingsScreen.notif.test.jsx` | 6 vitest tests for NOTIF-01 behaviors | ✓ VERIFIED | File exists; all 6 tests pass (hydration, optimistic flip, full-replace PATCH, revert+toast) |
| `apps/client-pwa/src/screens/ProfileScreen.identity.test.jsx` | useClientMembership stub repaired | ✓ VERIFIED | Line 23: `useClientMembership: () => ({ data: null })` present in vi.mock |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| ProfileScreen | useClientMembership() | import from @/data | ✓ WIRED | Line 12 imports hook; line 76 calls it; result destructured as `membership` |
| membership.priceKopecks | formatMoney() | line 194 call | ✓ WIRED | `formatMoney(membership.priceKopecks)` renders in JSX |
| SettingsScreen | useClientMe().notifPrefs | useEffect lines 50-55 | ✓ WIRED | `me?.notifPrefs` drives notifRef + setNotif on arrival |
| setNotifKey | useUpdateClientProfile().mutateAsync | line 77 | ✓ WIRED | `await updateProfile.mutateAsync({ notifPrefs: next })` sends full 4-key object |
| CheckoutSheet chip | handlePromoApply('FIT15') | onClick line 458 | ✓ WIRED | `onClick={() => handlePromoApply(RECOMMENDED_PROMO.code)}` passes string; typeof guard in handlePromoApply handles it |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| ProfileScreen price row | `membership.priceKopecks` | `useClientMembership()` → GET /api/v1/client/membership | `ClientMembershipData.priceKopecks: number` typed in clientQueries.ts (line 154); real backend field (Phase 75) | ✓ FLOWING |
| SettingsScreen notif toggles | `notif` (from `notifRef`) | `useClientMe().notifPrefs` → GET /api/v1/client/me | `ClientMeData.notifPrefs` typed (line 101); useEffect re-syncs from server value | ✓ FLOWING |
| CheckoutSheet promo chip | `promoResult` (after apply) | `usePromoValidate` → POST /client/promo/validate | Returns `{ discountKopecks, newAmountKopecks, discountType }` from server | ✓ FLOWING (server-authoritative) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 92 vitest tests pass | `pnpm exec vitest run` | 16 files / 92 tests passed in 1.58s | ✓ PASS |
| ESLint clean | `pnpm lint` | exit 0, no output | ✓ PASS |
| TypeScript strict | `pnpm exec tsc -b` | exit 0, no output | ✓ PASS |
| Vite build succeeds | `pnpm build` | built in 685ms; dist/sw.js generated | ✓ PASS |

### Race Fix Verification (NOTIF-01)

The three warnings from 78-REVIEW.md (WR-01/02/03) were addressed in HEAD:

- **WR-01 (stale-closure full-replace):** Fixed via `notifRef.current` as synchronous source of truth. `setNotifKey` builds `next = { ...notifRef.current, [key]: val }` (line 73) and writes to `notifRef.current` before awaiting — rapid taps compose correctly.
- **WR-02 (in-flight clobber from re-sync):** Fixed via `!updateProfile.isPending` guard in the useEffect (line 51). Re-sync only fires when no mutation is in flight.
- **WR-03 (per-key revert):** Fixed via `{ ...notifRef.current, [key]: priorVal }` revert (lines 79-81) — only the failed key is reverted, not the entire prior snapshot.

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `CheckoutSheet.jsx:50` | `RECOMMENDED_PROMO = { code: 'FIT15', label: '−15%' }` labeled as "Placeholder" | INFO (IN-01 from REVIEW) | FIT15 must be a seeded/active promo code on the server; chip surfaces in prod and will 422 if FIT15 doesn't exist. Not a code blocker — server-authoritative validation handles it gracefully with "Промокод не найден" — but requires confirming the seed. |
| `ProfileScreen.jsx:217` | `window.__openSubManage?.('freeze')` | INFO (IN-02 from REVIEW, pre-existing) | Not introduced by Phase 78; adjacent to PMEM-01 changes. No action needed for this phase. |

No TBD/FIXME/XXX markers found in Phase 78 modified files.

### Human Verification Required

#### 1. PROMO-01 — FIT15 chip in subscription checkout (live stack)

**Test:** Start backend (FIT15 seeded via migration 0051) + `cd apps/client-pwa && pnpm dev`. Log in as a client, open a membership plan, tap "К оплате", verify the FIT15 chip ("−15% Применить FIT15") is visible in the Промокод section when no promo is applied. Tap it once.
**Expected:** Toast "Промокод FIT15 применён" (or equivalent) appears; discounted amount is shown; chip disappears. Manual text entry of "FIT15" also works.
**Why human:** Requires running backend with FIT15 seeded; chip render-in-browser and server round-trip can't be confirmed by grep or vitest.

#### 2. PROMO-01 — FIT15 chip in PT checkout (live stack)

**Test:** Open a personal-training package checkout.
**Expected:** FIT15 chip also surfaces there (same flag gates both ctx.kind='sub' and ctx.kind='pt'); one tap applies FIT15 with discounted amount.
**Why human:** No automated test file exists for CheckoutSheet; requires live PT package.

#### 3. NOTIF-01 — persistence across full page reload

**Test:** On the running app, open Settings, toggle one notification switch (e.g. "Звук уведомлений"), fully reload the browser tab.
**Expected:** The toggled setting is preserved after reload (server round-trip persisted it; no localStorage fallback).
**Why human:** localStorage removal is verified by grep (count: 0), but actual server persistence requires a live PATCH → GET round-trip through the running backend.

### Gaps Summary

No gaps found. All three success criteria are code-verified in HEAD:
- PMEM-01: price row + auto-renew guard wired; camelCase fields confirmed; all render branches tested.
- NOTIF-01: server hydration wired; localStorage removed; all three race fixes in place; mutation payload typed.
- PROMO-01: flag flipped true; chip renders when `!promoResult`; string code passed to handler.

Three human verification items remain for live-stack behaviors (PROMO chip UX in both checkout contexts; NOTIF persistence after reload). These are inherently UI/server behaviors that cannot be confirmed by static analysis.

---

_Verified: 2026-06-02T23:30:00Z_
_Verifier: Claude (gsd-verifier)_
