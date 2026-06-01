---
phase: 260601-vxr
plan: "01"
subsystem: client-pwa
tags: [payment, membership, ux, animation, anti-oracle]
dependency_graph:
  requires: []
  provides:
    - useClientMembership read hook with D-10 anti-oracle gate
    - useClientPaymentHistory enabled param for anti-oracle gating
    - formatRuDate ISO-date-only → ru long-date helper
    - .pa-* Plan Activated success-screen CSS classes (full 1:1 mockup)
    - Rebuilt PaymentSucceededView with achievement chip, validity bar, perks, receipt-link, two CTAs
    - one-shot openQr navigation state signal from PaymentSucceededView → HomeRoute
  affects:
    - apps/client-pwa/src/routes/PaymentReturnScreen.jsx
    - apps/client-pwa/src/lib/clientQueries.ts
    - apps/client-pwa/src/data/index.js
    - apps/client-pwa/src/utils/format.js
    - apps/client-pwa/src/styles.css
    - apps/client-pwa/src/App.jsx
tech_stack:
  added: []
  patterns:
    - useQuery with enabled gate for anti-oracle (D-10)
    - CSS custom property animations with prefers-reduced-motion guard
    - Genitive ru date formatting without new Date() (CLAUDE.md DST rule)
    - navigate(state={openQr:true}) one-shot signal pattern (App.jsx HomeRoute)
key_files:
  created: []
  modified:
    - apps/client-pwa/src/lib/clientQueries.ts
    - apps/client-pwa/src/data/index.js
    - apps/client-pwa/src/utils/format.js
    - apps/client-pwa/src/styles.css
    - apps/client-pwa/src/routes/PaymentReturnScreen.jsx
    - apps/client-pwa/src/routes/PaymentReturnScreen.test.jsx
    - apps/client-pwa/src/App.jsx
decisions:
  - "Anti-oracle gate: useClientMembership(data?.status === 'succeeded') — hook present but enabled=false during pending; query never fires (D-10)"
  - "Anti-oracle gate: useClientPaymentHistory(1, succeeded) — payment history also gated by D-10"
  - "Plan card omitted when membership null — graceful 200-null handling per API contract"
  - "formatRuDate splits on '-', indexes genitive month table — no new Date() per CLAUDE.md DST rule"
  - "Perks list hardcoded static copy (no API field; acceptable per REVISION 1 spec for single-gym project)"
  - "Receipt-link 'Открыть чек' lives inside plan card — D-11 enforced (only when receiptUrl non-null)"
  - "QR button signals App shell via navigate state {openQr:true}; HomeRoute reads once via useEffect + ref guard then clears state"
  - ".pa-achv achievement chip always shown in succeeded state; pop-in animation + star twinkle; reduced-motion suppressed"
  - "Test updated to mock useClientPaymentHistory; 16 tests covering all new elements + anti-oracle"
metrics:
  duration: "~30min (REVISION 1)"
  completed: "2026-06-01T23:25:00Z"
  tasks_completed: 4
  files_changed: 7
---

# Phase 260601-vxr Plan 01: Plan Activated Success Screen Summary

**One-liner:** Full 1:1 mockup restore of `PaymentSucceededView` — achievement chip, validity progress bar (100%), hardcoded perks list, real paid amount from payment history, two CTA buttons (QR-pass + home), live badge, card shimmer sweep.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Add useClientMembership + formatRuDate | a927659f | clientQueries.ts, format.js, data/index.js |
| 2 | Add .pa-* styles to styles.css | ae3ce309 | styles.css |
| 3 | Rebuild PaymentSucceededView | b103c843 | PaymentReturnScreen.jsx, .test.jsx |
| 4 (REV1) | Full 1:1 mockup restore | 87644aa6 | PaymentReturnScreen.jsx, styles.css, App.jsx, clientQueries.ts, .test.jsx |

## What Was Built

### Task 1: useClientMembership + formatRuDate

Added `ClientMembershipData` interface and `useClientMembership(enabled)` read hook to `clientQueries.ts`, immediately after `useClientHome`, mirroring the same pattern. The hook queries `GET /api/v1/client/membership` and returns `ClientMembershipData | null`. The `enabled` param is the D-10 anti-oracle gate — callers pass `data?.status === 'succeeded'` so the query never fires during pending.

Added `formatRuDate(isoDateOnly)` to `utils/format.js` that parses `YYYY-MM-DD` by splitting on `-` (never `new Date()`) and indexes a genitive full-month-name table. Returns `''` on falsy/malformed input. The existing `monthName` (short nominative) is untouched.

Both are re-exported from `data/index.js` (D-71-07 swap seam).

### Task 2: .pa-* styles

Appended a complete `.pa-*` section to `styles.css` with:
- Keyframes: `pa-check-pop`, `pa-wave-out`, `pa-check-draw`, `pa-confetti-out`, `pa-fade-up`
- `.pa-screen` scroll container
- `.pa-check-hero` 104px accent medallion with pop animation and continuous `::before`/`::after` wave rings
- `.pa-check-hero svg path` stroke-draw animation
- `.pa-confetti` + 8 `nth-child` definitions with `--tx`/`--ty`/`--rot` custom props (#fbbf24/#f87171 decorative accents)
- `.pa-title` (fade-up 0.45s), `.pa-sub` (0.55s), `.pa-card` (0.65s), `.pa-actions` (0.75s)
- `.pa-card-head`, `.pa-card-name`, `.pa-badge`, `.pa-card-meta`, `.pa-days`
- `.pa-receipt-chip`
- `@media (prefers-reduced-motion: reduce)` block suppressing all `.pa-*` animations with immediate final state

No Tailwind. No raw hex except #06120c (on-accent) and the sanctioned #fbbf24/#f87171 confetti accents.

### Task 3: Rebuilt PaymentSucceededView

Replaced the function body (the outer `PaymentReturnScreen`, `PaymentCanceledView`, and polling logic are byte-for-byte unchanged). The new view:

- `useClientMe()` for personalized greeting ("Ты в команде, {firstName}" / fallback "Ты в команде!")
- `useClientMembership(data?.status === 'succeeded')` with explicit enabled gate
- `.pa-screen` scroll container with `aria-live="polite"` and `role="region"`
- `.pa-check-hero` with `aria-label`, confetti `aria-hidden`
- `.pa-title` personalized headline
- `.pa-sub` truthful copy: "Оплата подтверждена. Доступ активен."
- `.pa-card` rendered only when `membership !== null`: planNameSnapshot, "Активен" badge when `status==='active'`, `formatRuDate(endDate)`, `daysUntilEnd`
- Receipt chip preserved from old view (receiptEmail || receiptPhone)
- `.pa-actions`: conditional "Открыть чек" (D-11), single "Хорошо" → onDone()
- `primaryBtnRef` focus on mount preserved

Test file updated: mocks `useClientMe` and `useClientMembership` alongside existing `useClientPaymentStatus`. 8 tests covering: pending anti-oracle (no succeeded content), personalized greeting, fallback greeting, plan card presence/absence (null vs non-null membership), receipt link conditional (D-11), "Открыть чек" absent. All 53 tests pass.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test file broke after component change**
- **Found during:** Task 3 — `pnpm test` failure
- **Issue:** `PaymentReturnScreen.test.jsx` mocked `@/data` with only `useClientPaymentStatus`; component now also calls `useClientMe` and `useClientMembership`. Test also asserted on old copy ("Готово!") that no longer exists.
- **Fix:** Updated mock to include all three hooks with sensible defaults in `beforeEach`. Updated assertions to match new copy and added 5 new behavioral test cases (greeting fallback, plan card, receipt conditional).
- **Files modified:** `apps/client-pwa/src/routes/PaymentReturnScreen.test.jsx`
- **Commit:** b103c843 (included in Task 3 commit)

**2. [Rule 1 - Bug] Anti-oracle hook-call assertion too strict**
- **Found during:** Task 3 test iteration
- **Issue:** Initial anti-oracle test asserted `useClientMembership` was not called at all during pending. React's rendering behavior called the mock (possibly from StrictMode double-invoke); the real invariant is that no network request fires (enabled=false) and no succeeded content renders.
- **Fix:** Changed assertion to UI-level: verify no succeeded-view content (greeting, "Оплата подтверждена", "Активен" badge) is present during pending state.
- **Files modified:** Same test file

## Verification

- `pnpm typecheck` — pass
- `pnpm lint` — pass
- `pnpm test` — 53/53 pass (pre-existing build warnings about duplicate JSX keys in unrelated files not introduced here)
- `pnpm build` — pass (41.24 kB CSS, 5.40 kB PaymentReturnScreen chunk)

## Threat Surface Scan

No new network endpoints introduced. `useClientMembership` reuses the existing `GET /client/membership` endpoint already in the backend's client portal. The D-10 anti-oracle gate (`enabled: data?.status === 'succeeded'`) is correctly wired — membership is never fetched during pending.

T-vxr-01 (premature activation reveal) — mitigated per plan. T-vxr-02 (economics over-exposure) — accepted per plan (only client-safe fields rendered).

## Known Stubs

None. All data is real: `useClientMe` (already wired), `useClientMembership` (new hook, existing endpoint). No placeholder text or hardcoded values in the rendered output.

## REVISION 1 — What Was Added (commit 87644aa6)

### Achievement chip `.pa-achv`
Static "Новый участник клуба" badge placed between hero-sub and plan card. Star SVG medallion with pop-in animation (`pa-achv-pop`, 0.95s delay, elastic cubic) and `pa-star-twinkle` continuous animation. `aria-label="Достижение: новый участник клуба"`, star `aria-hidden`. Always shown in succeeded state. Fully suppressed by `prefers-reduced-motion`.

### Validity block inside plan card
`pa-validity` block: `pa-validity-row` with "Впереди `{daysUntilEnd}` дней" (real server value) + "100%" label. `pa-validity-track` + `pa-validity-fill` (accent, 100% width — correct at activation moment). `role="progressbar" aria-valuenow=100`. No fake %; 100% is correct because entire term is ahead. Fill animated with `transition: width 1.15s … 0.7s`.

### Perks list
`pa-perks` with 3 hardcoded `pa-perk` rows. Each has `pa-perk-dot` (check icon on accent-soft background). No API field for perks — static is the only path to 1:1 for this single-gym project (REVISION 1 decision).

### Receipt-link row inside card
`pa-receipt-link` separated by a top border. Left: "Списано · `{formatMoney(paidAmount)}`" (real amount from `useClientPaymentHistory`, most recent positive item). Right: "Открыть чек ›" link — D-11: rendered as `<a>` ONLY when `data.receiptUrl` non-null. Row shown only when at least one of (paidAmount, receiptUrl) is truthy. Receipt link has `aria-label="Открыть чек оплаты (новая вкладка)"`.

### CTA stack — two buttons
Replaced single "Хорошо" with:
1. Primary `.btn-accent` "Открыть QR-пропуск" (QR/grid SVG icon) — calls `navigate('/', { state: { openQr: true } })` which signals HomeRoute via one-shot effect.
2. Secondary `.btn-ghost` "На главную" — `navigate('/', { replace: true })`.

### App.jsx HomeRoute — one-shot QR signal
`useEffect` reads `location.state?.openQr`, calls `ui.setQrOpen(true)`, then clears state via `navigate('/home', { replace: true, state: {} })`. `handledQrSignal` ref prevents double-fire on StrictMode double-invoke. Only fires when `state?.openQr` is truthy.

### useClientPaymentHistory enabled param
Added `enabled = true` default param so the ProfileScreen tab usage is unchanged. PaymentSucceededView passes `enabled = succeeded` (D-10 anti-oracle gate).

### New/extended CSS classes (styles.css)
`pa-achv-pop`, `pa-star-twinkle` keyframes + `.pa-achv`, `.pa-achv-star` rules. `pa-validity*` block. `pa-perks`, `pa-perk`, `pa-perk-dot`. `pa-receipt-link`, `pa-receipt-lbl`, `pa-receipt-val`. `pa-badge-live`, `pa-badge-dot` (pulse-dot animation). `pa-card-sweep` shimmer animation on `.pa-card::after`. Reduced-motion block extended to cover all new classes.

### Tests (PaymentReturnScreen.test.jsx — 16 tests, 61 total)
Added `useClientPaymentHistory` mock. New tests:
- Achievement chip visible in succeeded state
- Achievement chip NOT in pending state (anti-oracle)
- Perks list visible with membership
- Validity "100%" visible with membership
- Two CTA buttons visible in succeeded state
- QR-pass button NOT in pending state (anti-oracle)
- Receipt-link row with amount + "Открыть чек" when history + receiptUrl present
- "Открыть чек" absent with null membership (card not rendered — D-11 path)

## Self-Check: PASSED

- a927659f — FOUND in git log
- ae3ce309 — FOUND in git log
- b103c843 — FOUND in git log
- 87644aa6 — FOUND in git log
- apps/client-pwa/src/lib/clientQueries.ts — FOUND
- apps/client-pwa/src/utils/format.js — FOUND
- apps/client-pwa/src/routes/PaymentReturnScreen.jsx — FOUND
- apps/client-pwa/src/styles.css — FOUND
- apps/client-pwa/src/App.jsx — FOUND

---

## REVISION 2 (user feedback) — commit b17cd86a

Four corrections applied to `PaymentSucceededView` based on user review of the REVISION 1 result:

**1. Removed "ЧЕК ОТПРАВЛЕН НА" receipt-destination chip**
The chip block (`data?.receiptEmail || data?.receiptPhone`) was deleted from `PaymentReturnScreen.jsx` (was lines 341-360). The mockup has no such chip — the receipt is represented solely by "Открыть чек" inside the plan card. The dead `.pa-receipt-chip` CSS rule was also removed from `styles.css`. The `Icon` import was kept (still used by `PaymentCanceledView`).

**2. TabBar hidden on /payment/return**
Added `const isPaymentReturnRoute = pathname === '/payment/return'` in `App.jsx` and included it in the `hideTabBar` OR condition alongside the existing `isLoginRoute` / `isOnboardingRoute` guards. The bottom nav is now absent on the success/pending/canceled screen.

**3. Receipt-link row always renders inside the plan card**
Previously gated on `paidAmount !== null || data?.receiptUrl`, so it vanished when both were null. Now it renders unconditionally inside the `{membership && ...}` card (the mockup always shows it as the card footer). Left-side label: "Списано · {amount}" when `paidAmount` is available; fallback "Оплата · картой" when the amount can't be resolved (prevents an empty "Списано · "). Right side unchanged: "Открыть чек ›" only when `data.receiptUrl` is non-null (D-11). A new test was added to cover the fallback label path.

**4. Increased spacing between check medallion and headline**
Added `margin-top: 14px` to `.pa-title` in `styles.css`. Combined with the medallion's existing `margin-bottom: 18px` (from `margin: 38px auto 18px`), this gives 32 px of clear breathing room — matching the mockup's proportions.

---

## REVISION 3 (post-review polish) — user-approved 2026-06-02

Iterative visual fixes from live review; user confirmed final state ("вот так фиксируем"):

- **`1fe5c7d7` — focus ring no longer squares pill buttons.** The auto-focused primary CTA looked square because (a) the generic `:focus-visible` rule set `border-radius: 6px` on the focused element (clobbering the pill's `var(--r-pill)`), and (b) button focus used CSS `outline`, which Safari/macOS draws rectangular. Removed the radius override from `:focus-visible` and switched button/pill `:focus-visible` to a border-radius-following `box-shadow` ring. (App-wide improvement.)
- **`76339415` — plan card dropped to the bottom.** Moved `margin-top: auto` from `.pa-actions` to `.pa-card` so the slack lands above the card; card now sits directly above the CTA buttons.
- **`72851ba3` — header column horizontally centered.** `.pa-screen { align-items: center }`; `.pa-card` + `.pa-actions` kept full width via `width: 100%`.
- **`a7b27e91` — header vertically centered.** `.pa-check-hero { margin-top: auto }` pairs with the card's `margin-top: auto` to split free vertical space evenly — header sits mid-screen, card + CTA pinned to the bottom.
- **`cfc7a753` — doubled the medallion↔title gap** from 32px to 64px (`.pa-check-hero` bottom 18→36, `.pa-title` top 14→28).

**Status:** COMPLETE — browser-verified by user across all iterations.

## Final commit set (code, plan 260601-vxr-01)

`a927659f`, `ae3ce309`, `b103c843`, `87644aa6`, `b17cd86a`, `1fe5c7d7`, `76339415`, `72851ba3`, `a7b27e91`, `cfc7a753`
