---
phase: 260601-sxf-v2-checkout
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - apps/client-pwa/src/styles.css
  - apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx
autonomous: false
requirements: [CPAY-RESTYLE]
must_haves:
  truths:
    - "Checkout review stage renders the v2 membership-pass hero card with plan name (ctx.title), meta (ctx.subtitle), a duration pill, the price, and a 'Гарантия возврата' badge"
    - "The total/pay amount count-up animates to the real server total on mount and on promo apply/remove"
    - "A 'Ваша выгода' savings bar appears only when the server-returned total is below ctx.amount, driven by real base-vs-total values"
    - "The promo field uses the v2 coupon look (ticket notch, tag icon, applied check + code + remove) and keeps server validation + per-reason D-09 error mapping"
    - "The ЮKassa method plate uses the v2 .method visual language but implies no saved/selectable wallet (no card picker, no '·· 4821')"
    - "Toasts fire on promo apply, promo remove, and method confirm using an in-sheet toast"
    - "Paying stage (D-13), exactly 4 error states (D-12), success-on-server-truth (D-10), focus mgmt + aria-live + aria-labels, and formatMoney() amounts are all preserved unchanged"
    - "Light and dark themes both render correctly via existing styles.css custom properties"
  artifacts:
    - path: "apps/client-pwa/src/styles.css"
      provides: "v2 checkout classes (.pass, .coupon, .sum, .save-*, .method, .co-toast) + count-up/tick keyframes"
      contains: ".pass"
    - path: "apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx"
      provides: "v2 review-stage layout wired to server-authoritative pricing + existing promo/checkout handlers"
      contains: "pass"
  key_links:
    - from: "CheckoutSheet.jsx review stage"
      to: "ctx.amount / promoResult.newAmountKopecks"
      via: "total = promoResult ? promoResult.newAmountKopecks : ctx.amount (D-06, unchanged)"
      pattern: "promoResult.*newAmountKopecks"
    - from: "CheckoutSheet.jsx pay button"
      to: "startPay / launchCheckout"
      via: "onClick startPay (email-gate + launchCheckout unchanged)"
      pattern: "onClick.*startPay"
    - from: "CheckoutSheet.jsx promo apply"
      to: "usePromoValidate + PROMO_ERROR_MESSAGES"
      via: "handlePromoApply / handlePromoRemove (unchanged)"
      pattern: "handlePromoApply"
---

<objective>
Visually integrate the new "К оплате v2" checkout design into the client-PWA
CheckoutSheet review stage. Full visual transfer (user chose "Полный перенос"):
membership-pass hero card, coupon-style promo field, summary card with a
"Ваша выгода" savings bar, restyled ЮKassa method plate, price count-up
animation, and toasts on promo/method actions.

This is a frontend-only visual restyle. ALL behavior, server-authoritative
pricing, and locked phase-999.4 states stay exactly as they are today — only
the review-stage presentation changes.

Purpose: bring the checkout look to the approved v2 mockup without touching the
payment flow, backend, or pricing logic.
Output: updated `styles.css` (net-new checkout classes + keyframes) and a
restyled `CheckoutSheet.jsx` review stage.
</objective>

<execution_context>
@/Users/andre/Workspace/Development/clubcore/.claude/get-shit-done/workflows/execute-plan.md
@/Users/andre/Workspace/Development/clubcore/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/quick/260601-sxf-v2-checkout/260601-sxf-CONTEXT.md
@.planning/phases/999.4-client-pwa-checkout-visual-restyle/999.4-UI-SPEC.md
@apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx
@apps/client-pwa/src/utils/format.js

<reference_mockup>
The reference mockup is at `~/Downloads/К оплате v2.html`. ONLY the `.screen`
contents are in scope. STRIP all of: the device frame (`.device`, `.device-inner`,
`.island`), status bar, `.home-indicator`, the `.tweaks` panel + its script, all
`postMessage` / edit-mode hooks, and the vestigial `.lockbar` / `.pass-live` /
live-occupancy / `.promo-rec` / `.bonus` blocks (those are demo-only — several DOM
nodes referenced by the lockbar/occupancy JS don't even exist in the mockup body).

Do NOT port the mockup's client-side `compute()` / `PROMOS` pricing math — pricing
is server-authoritative (D-06). The mockup's `animateTotal()` count-up technique
(cubic ease-out over ~440ms) is reusable, but it must animate toward the REAL
server total, not a client-computed one.
</reference_mockup>

<interfaces>
<!-- Contracts the executor needs — already present in CheckoutSheet.jsx today. Do NOT change them. -->

CheckoutSheet props (UNCHANGED public contract):
  { ctx: { kind: 'sub'|'pt', planId, title, subtitle, amount /* kopecks */ }, onClose, onDone, forceOutcome }

Server-authoritative pricing (D-06 — keep as-is):
  const total    = promoResult ? promoResult.newAmountKopecks : ctx.amount
  const discount = promoResult ? promoResult.discountKopecks  : 0
  // promoResult shape: { discountKopecks, newAmountKopecks, discountType, _validatedCode }

Existing handlers to REUSE verbatim (do not rewrite logic):
  handlePromoApply()  — calls usePromoValidate().mutateAsync, sets promoResult / promoError
  handlePromoRemove() — clears promoResult / promoError / promoCode
  startPay()          — email-gate gate (D-02/D-03) then launchCheckout()
  launchCheckout()    — demo guards + checkoutMembership/checkoutPtPackage mutateAsync + redirect

Existing promo error map (D-09 — keep):
  PROMO_ERROR_MESSAGES = { not_found, expired, not_yet_active, used_up, not_applicable, inactive }

formatMoney(kopecks) from src/utils/format.js → ru-RU RUB string with NBSPs. Use for ALL amounts.

Icon component: <Icon name="…" size={…} color="…" strokeWidth={…} />. Available names include:
  tag, lock, shield, check, x, chevronLeft, chevronRight, barbell, card, user, alertCircle, clock, wifiOff, mail.
  (No new icon names — restrict to these.)

styles.css tokens already present (reference via var(), no raw hex except sanctioned --on-accent #06120c):
  --bg --surface --surface-2 --border --border-strong --text --text-2 --text-3
  --accent --accent-deep --accent-soft --danger --danger-soft --warn --warn-soft
  --r-sm(10) --r-md(14) --r-lg(20) --r-xl(28) --r-pill --sh-1 --sh-2 --sh-3
  Type classes: .t-display .t-h1 .t-h2 .t-h3 .t-body .t-small .t-mini .t-num
  Spinner: .ptr-spin  | State pattern: .state .state-icon(.ok/.error/.warn/.info) .state-title .state-desc .state-actions
  Buttons: .btn .btn-accent .btn-ghost
NOTE: mockup uses --ink-* premium-card tokens and --r-lg:22/--r-xl:28; our --r-lg is 20.
  Do NOT add --ink-* tokens — the v2 .pass uses var(--surface)/var(--border) in light mode.
  Map mockup radii to our existing scale (--r-xl for the pass, --r-lg for cards).

NO global toast singleton exists. PushToast.jsx is a push-notification overlay, not a
generic toast. Per CONTEXT.md, add a MINIMAL in-sheet toast (local state + a `.co-toast`
class) consistent with PWA patterns. Do not invent a global provider.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add v2 checkout CSS classes + keyframes to styles.css</name>
  <files>apps/client-pwa/src/styles.css</files>
  <action>
Append a "Checkout v2" CSS block to `apps/client-pwa/src/styles.css` (after the
existing `.state*` / `.field` blocks). Port ONLY the in-scope `.screen`-content
classes from `~/Downloads/К оплате v2.html`, adapted to our token scale. Use
`var(--token)` exclusively — the only sanctioned raw hex is `#06120c` (on-accent
text, already used in the project).

Add these classes (names prefixed where they'd collide with existing ones —
NOTE `.field`, `.chip`, `.method`, `.toast` already exist in styles.css, so use
NEW names to avoid clobbering): 

- `.co-pass` (membership-pass hero): `var(--surface)` bg, `0.5px solid var(--border)`,
  `border-radius: var(--r-xl)`, `box-shadow: var(--sh-3)`, padding `20px 20px 18px`,
  `position: relative; overflow: hidden`. Sub-parts: `.co-pass-mark` (barbell watermark
  SVG, `color: var(--accent); opacity: 0.13; transform: rotate(-18deg)`, absolute
  bottom-right), `.co-pass-row`, `.co-brand`, `.co-brand-mark` (30×30, `var(--accent)` bg,
  `#06120c` text, radius 9px), `.co-brand-name`, `.co-pass-pill` (accent-soft pill with
  a dot — the duration pill), `.co-pass-body`, `.co-pass-eyebrow` (`var(--accent-deep)`
  caps), `.co-pass-name` (27px/800/-0.9px), `.co-pass-meta` (with `i` dot separators),
  `.co-pass-foot` (`border-top: 0.5px dashed var(--border-strong)`), `.co-pass-price-lbl`,
  `.co-pass-price` (32px/800/-1.2px, tabular-nums, with `small` /мес-style suffix),
  `.co-pass-secure` (shield icon + "Гарантия возврата", `var(--accent-deep)` icon).
- `.co-coupon` (promo ticket): `var(--surface)` bg, `0.5px solid var(--border)`,
  `border-radius: var(--r-lg)`, `box-shadow: var(--sh-2)`, padding `14px 15px`,
  `position: relative; overflow: hidden`. Ticket notches via `::before`/`::after`
  (18px circles, `background: var(--bg)`, left:-9px / right:-9px, vertically centered,
  `box-shadow: inset 0 0 0 0.5px var(--border)`). `.co-coupon-glow` accent edge strip.
  Error variant `.co-coupon.error` (`border-color: var(--danger)`,
  `box-shadow: 0 0 0 3px rgba(220,38,38,0.12)`). Applied variant `.co-coupon.applied`
  (`border-color: rgba(45,212,164,0.5)`, `box-shadow: 0 0 0 3px var(--accent-soft), var(--sh-2)`).
  `.co-field` row (tag-icon chip `.co-tag-ic` 38×38 accent-soft, input-wrap, apply button),
  `.co-input-lbl` ("Есть промокод?" caps), `.co-promo-apply` (idle: `var(--surface-2)`/
  `var(--text-3)`; `.ready`: `var(--text)` bg / `var(--bg)` text), `.co-promo-hint`
  (`.err` → `var(--danger)`), `.co-applied-view` (av-check accent square, av-code,
  av-desc `var(--accent-deep)`, av-remove round button).
- `.co-sum` (summary card): `var(--surface)`, `var(--r-lg)`, `var(--sh-3)`, with
  `.co-sum-row` (border-bottom 0.5px), `.co-sum-row.discount` (accent-deep),
  `.co-sum-total` (total row: `.co-tl` 16px/700 with `small` subtext, `.co-amount`
  32px/800/-1.1px tabular-nums).
- `.co-save-wrap` (hidden by default; `.show` reveals), `.co-save-bar` (7px track with
  `.co-pay-seg` `var(--text)` + `.co-save-seg` `var(--accent)`, width-transition
  0.5s), `.co-save-legend` ("Ваша выгода" + `b` accent-deep amount).
- `.co-method` (ЮKassa plate): `var(--surface)`, `var(--r-lg)`, `var(--sh-2)`,
  padding `13px 15px`, NON-interactive cursor default. `.co-method-logo` 42×42 with
  ЮKassa "Ю" glyph — use `var(--accent-soft)` bg + `var(--accent-deep)` text (NOT the
  mockup's purple #7a30e8 wallet logo). `.co-method-text` with name "ЮKassa" + sub
  "Карта, СБП, Мир". NO "Выбрано" default-wallet badge, NO "·· 4821", NO change chevron
  implying a picker — a static `lock`-icon shield on the right instead (D-01).
- `.co-toast` (in-sheet toast): absolute, `left/right: 16px; bottom: 124px; z-index: 200`,
  `var(--text)` bg / `var(--bg)` text, radius 14px, padding `11px 13px`, flex row with
  `.co-toast-ic` (30×30 accent square) + text. Default `transform: translateY(180%); opacity:0`,
  `.show` → `translateY(0); opacity:1`, transition matching the mockup (~0.42s cubic-bezier(.32,.72,.2,1)).
- `.co-sec-label` (section label with trailing rule line `.co-ln`): 11px/700 caps,
  `var(--text-3)`, optional `flex: 1; height: 1px; background: var(--border)` line.

Add keyframes if not already present: `tickA` (number tick, translateY -3px bump,
~0.42s cubic-bezier(.32,1.6,.32,1)) and a `.co-tick` class applying it. Reuse the
existing `spin`/`ptr-spin` and `state-in`/`icon-pop` keyframes — do NOT redefine them.

Ensure dark-theme correctness: because every value uses semantic tokens, the existing
`[data-theme="dark"]` block already covers it — verify visually. Respect the existing
global `@media (prefers-reduced-motion: reduce)` rule (do not add motion that bypasses it).
  </action>
  <verify>
    <automated>cd apps/client-pwa && pnpm lint 2>&1 | tail -20 && pnpm build 2>&1 | tail -20</automated>
    Manual: open the PWA (`pnpm dev`), trigger checkout; confirm new classes resolve
    (no unstyled/raw-palette flashes) in both light and dark themes.
  </verify>
  <done>
styles.css contains the `.co-pass`, `.co-coupon`, `.co-sum`, `.co-save-*`,
`.co-method`, `.co-toast`, `.co-sec-label` classes and the `tickA`/`.co-tick`
keyframe; no raw hex except `#06120c`; `pnpm lint` and `pnpm build` pass.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 2: Rewrite CheckoutSheet review stage to the v2 layout (behavior preserved)</name>
  <files>apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx</files>
  <what-built>
Restructured ONLY the review-stage JSX of `CheckoutSheet.jsx` to the v2 mockup
layout, reusing the new `.co-*` classes from Task 1. Everything else stays byte-for-byte:
the `mapApiErrorToKind`, `PROMO_ERROR_MESSAGES`, all hooks/state, `handlePromoApply`,
`handlePromoRemove`, `launchCheckout`, `startPay`, the email-gate branch, the paying
stage (D-13), and the `CheckoutError` component (D-12 — exactly 4 kinds) are untouched.

Implementation notes for the executor:
- Keep `const total = promoResult ? promoResult.newAmountKopecks : ctx.amount` and
  `const discount = promoResult ? promoResult.discountKopecks : 0` (D-06). Never compute
  discounts client-side.
- Replace the centered amount header + order card + plate + promo block with the v2
  body order: (1) `.co-pass` hero, (2) `.co-sec-label` "Промокод" + `.co-coupon`,
  (3) `.co-sec-label` "Итог" + `.co-sum` summary with `.co-save-wrap` savings bar,
  (4) `.co-sec-label` "Способ оплаты" + `.co-method` plate. Keep the existing top bar
  ("Оплата", back button, aria-label="Назад") and the sticky paybar.
- HERO (`.co-pass`): brand mark "МЗ" + brand name "Мой зал / Клубная карта";
  duration pill — derive from `ctx` (if `ctx.subtitle` carries a duration use it,
  else a neutral label; do NOT hardcode "30 дней" when no duration is known —
  fall back to omitting the pill); eyebrow from `ctx.kind` ("Абонемент" for sub,
  "Тренировки" for pt); `.co-pass-name` = `ctx.title`; `.co-pass-meta` = `ctx.subtitle`;
  `.co-pass-price` = `formatMoney(ctx.amount)` (base price, NOT the discounted total);
  `.co-pass-secure` = shield icon + "Гарантия возврата".
- PROMO COUPON: bind the existing `promoCode`/`setPromoCode`, `promoLoading`,
  `promoError`, `promoResult`, `handlePromoApply`, `handlePromoRemove`. Idle shows
  `.co-field` (tag-icon + "Есть промокод?" label + input placeholder "Промокод" +
  "Применить" button that gets `.ready` when input non-empty). Loading swaps the
  apply label for `.ptr-spin`. Applied (`promoResult` truthy) shows `.co-applied-view`
  (check + `promoResult._validatedCode` + "Скидка −{formatMoney(discount)} применена" +
  remove button wired to `handlePromoRemove`). Error renders `.co-promo-hint.err` with
  `role="alert"` and `PROMO_ERROR_MESSAGES[promoError] ?? 'Промокод не найден'` (D-09).
  OMIT the recommended-promo chip (`.promo-rec`/FIT15). OMIT the bonus block entirely.
- SUMMARY (`.co-sum`): a base row (`ctx.title` → `formatMoney(ctx.amount)`), a
  conditional discount row shown only when `discount > 0` (label "Промокод {code}",
  value `−{formatMoney(discount)}`), and the total row `.co-sum-total` with
  `formatMoney(total)`. The `.co-save-wrap` gets `.show` ONLY when `total < ctx.amount`;
  set `.co-save-seg` width to `Math.round(discount / ctx.amount * 100)%` and
  `.co-pay-seg` to the remainder; legend amount = `formatMoney(discount)` (real
  base-vs-total, D-06).
- METHOD (`.co-method`): static ЮKassa plate — "ЮKassa" / "Карта, СБП, Мир",
  no wallet number, no "Выбрано" badge, no picker chevron (D-01). On press fire the
  method-confirm toast (see toasts below). Keep it visually a card but with no nav affordance.
- COUNT-UP: animate the total/pay amount toward the REAL `total` (kopecks) using the
  mockup's cubic ease-out over ~440ms — run on mount and whenever `total` changes
  (promo apply/remove). Use a small effect + `requestAnimationFrame`; format each frame
  with `formatMoney`. The hero base price may also count-up on mount (optional polish);
  it animates to `ctx.amount`, never to a discounted value. Respect reduced-motion:
  when `matchMedia('(prefers-reduced-motion: reduce)')` matches, skip the tween and set
  the final value immediately.
- TOASTS: add minimal local state `const [toast, setToast] = useState(null)` and a
  `.co-toast` element (`.show` when toast set, auto-dismiss ~2.6s). Fire it on:
  promo apply success ("Промокод {code} применён"), promo remove ("Промокод удалён"),
  and method press ("ЮKassa" / "Способ оплаты подтверждён"). aria-live="polite".
- PAYBAR: keep the sticky bar + `.btn.btn-accent` CTA "Оплатить · {formatMoney(total)}",
  `onClick={startPay}`, the `disabled`/opacity guard for `!ctx.planId && !forceOutcome`,
  and the "Защищено · ЮKassa" lock note. May adopt the v2 `.pay`-style arrow/amount
  split visually, but the button MUST remain `.btn.btn-accent` (or equivalent) and call
  `startPay` — do not reintroduce the mockup's redirect-overlay demo timer.
- A11y: preserve all aria-labels, `role="alert"` on promo error, `aria-live` on toast,
  and the error/paying overlays' existing focus management.

Verification performed before checkpoint: `pnpm typecheck`, `pnpm lint`, `pnpm build`,
and `pnpm test` (existing CheckoutSheet/PaymentReturnScreen suites) all pass.
  </what-built>
  <how-to-verify>
1. `cd apps/client-pwa && pnpm dev`, open the PWA, navigate to a plan and open checkout.
2. REVIEW STAGE: confirm the v2 membership-pass hero (plan name = ctx.title, meta =
   ctx.subtitle, price = base amount, "Гарантия возврата" badge), the coupon-style
   promo field, the summary card, and the restyled ЮKassa method plate render correctly.
3. Total/pay amount COUNTS UP on open; toggle theme (light ↔ dark) — both look correct.
4. PROMO: enter a valid code → applied check view + discount row + "Ваша выгода" bar
   appears + total re-animates down + toast fires. Remove → reverts + toast fires.
   Enter an invalid code → inline error text under the coupon (red) per D-09.
5. METHOD: tap the ЮKassa plate → confirm toast; verify NO wallet number / picker.
6. Tap "Оплатить" → paying spinner stage (D-13) then the real redirect/flow; verify
   the 4 error states (D-12) still render via existing CheckoutError; verify email-gate
   still appears when the client has no email.
7. Confirm OMISSIONS: no bonus toggle, no recommended-promo chip, no device frame /
   tweaks panel.
  </how-to-verify>
  <resume-signal>Type "approved" or describe visual/behavior issues to fix.</resume-signal>
</task>

</tasks>

<verification>
- `cd apps/client-pwa && pnpm typecheck` — passes.
- `cd apps/client-pwa && pnpm lint` — passes (no raw-palette / boundary violations).
- `cd apps/client-pwa && pnpm build` — passes.
- `cd apps/client-pwa && pnpm test` — existing CheckoutSheet / PaymentReturnScreen
  suites pass (no behavior regressions).
- Manual visual check in light + dark per Task 2 how-to-verify.
</verification>

<success_criteria>
- The checkout review stage matches the v2 mockup `.screen` layout: hero pass card,
  coupon promo, summary + savings bar, restyled ЮKassa method plate, count-up amount,
  and action toasts.
- Pricing remains server-authoritative (D-06): total = promoResult.newAmountKopecks
  or ctx.amount; no client-side promo math ported.
- Locked states preserved: paying (D-13), 4 error kinds (D-12), success-on-server-truth
  (D-10), per-reason promo errors (D-09), payment-method presentation (D-01),
  accessibility, and formatMoney() for all amounts.
- Loyalty/bonus toggle and recommended-promo chip are absent.
- CheckoutSheet public props contract `{ ctx, onClose, onDone, forceOutcome }` unchanged.
- Light and dark themes both render correctly via existing styles.css tokens.
</success_criteria>

<output>
Create `.planning/quick/260601-sxf-v2-checkout/260601-sxf-01-SUMMARY.md` when done.
</output>
