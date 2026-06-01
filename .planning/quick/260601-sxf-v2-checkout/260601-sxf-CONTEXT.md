# Quick Task 260601-sxf: Integrate "К оплате v2" checkout screen - Context

**Gathered:** 2026-06-01
**Status:** Ready for planning

<domain>
## Task Boundary

Visually integrate the new "К оплате v2" checkout design (reference mockup at
`~/Downloads/К оплате v2.html`) into the **client PWA** checkout, replacing the
current look of `apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx`.

This is a **frontend-only visual restyle** of the existing checkout sheet. It must
stay fully compliant with the locked phase-999.4 decisions. No backend changes.
</domain>

<decisions>
## Implementation Decisions (LOCKED — do not revisit)

### Loyalty / bonus toggle ("Списать бонусы")
- **OMIT** the bonus block from this restyle. There is no loyalty model anywhere
  (no backend ORM, no client model). The user confirmed real loyalty redemption
  will be built as a **separate planned phase** (backend + product decisions:
  conversion rate, earning, Gold tiers, stacking/cap rules). Do NOT ship a
  non-functional stub.
- The mockup's "Бонусы клуба" section, the `.bonus` block, the bonus-balance
  count-up, and the bonus-related summary row are all dropped for this task.

### Pricing source
- **Server-authoritative only (D-06).** Never compute discounts client-side.
  The mockup's `compute()`/`PROMOS` client-side math is demo-only and must NOT be
  ported. Totals come from `usePromoValidate()` → `promoResult.newAmountKopecks`,
  with `ctx.amount` as the base.
- The "savings bar" / "Ваша выгода" is allowed: it is a *display* of
  `ctx.amount` (base) vs server-returned discounted total — derived from real
  server values, not client-computed promo logic.

### Payment method presentation
- **D-01 compliant.** Keep the ЮKassa info plate ("Оплата на защищённой странице
  ЮKassa · Карта, СБП, Мир"). Restyle it to match the mockup's `.method` row
  visual language, but do NOT imply a saved/selectable wallet (the mockup's
  "YooMoney · Кошелёк ·· 4821" is demo-only). No card picker, no Apple Pay, no
  save-card switch.

### Promo code
- Keep the existing server-authoritative promo flow (`usePromoValidate`,
  `PROMO_ERROR_MESSAGES` per-reason D-09 mapping, apply/remove handlers).
- Restyle the promo field to the mockup's coupon look (ticket notch, tag icon,
  applied-view with check + code + remove).
- **OMIT** the mockup's "recommended promo chip" (hardcoded FIT15) — there is no
  recommended-promo source; hardcoding a specific code would be misleading.

### Polish / liveness (full transfer — user chose "Полный перенос")
- Port the membership-pass hero card (brand, plan name from `ctx.title`, duration
  pill, plan meta from `ctx.subtitle`, price, "Гарантия возврата" badge).
- Port the price count-up animation on the total/pay amount (animate to the real
  server total).
- Port the savings bar ("Ваша выгода") driven by real base-vs-total values.
- Port toasts on promo apply/remove and method confirm — but reuse the PWA's
  existing toast/notification mechanism if one exists; otherwise a minimal
  in-sheet toast consistent with PWA patterns.
- **Strip mockup-only scaffolding**: device frame, status bar, home indicator,
  `.tweaks` panel + its script, `postMessage` edit-mode hooks, and the vestigial
  lockbar/live-occupancy JS (those DOM nodes don't even exist in the mockup body).

### Compliance with locked phase-999.4 states (must be preserved)
- Paying stage (D-13), 4 error states only (D-12), success on confirmed server
  truth (D-10), per-reason promo errors (D-09), accessibility (focus mgmt,
  aria-live, aria-labels), `formatMoney()` for all amounts.
- Theming: use existing `apps/client-pwa/src/styles.css` CSS custom properties
  (`--accent`, `--surface`, `--text`, `--r-*`, etc.). Light + dark must both work.
  The mockup's tokens already match these. Do NOT introduce raw hex except the
  existing sanctioned exceptions (e.g. `#06120c` on-accent text).
</decisions>

<specifics>
## Specific Ideas

- Reference mockup: `~/Downloads/К оплате v2.html` (device-framed; only the
  `.screen` contents are in scope).
- Target file: `apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx`.
- Shared styles: `apps/client-pwa/src/styles.css` (add classes there, not Tailwind).
- Pricing/queries: `apps/client-pwa/src/lib/clientQueries.ts`
  (`usePromoValidate`, `useClientCheckoutMembership`, `useClientCheckoutPtPackage`).
- Money formatting: `apps/client-pwa/src/utils/format.js` (`formatMoney`).
- CheckoutSheet props contract unchanged: `{ ctx: { kind, planId, title, subtitle, amount }, onClose, onDone, forceOutcome }`.
</specifics>

<canonical_refs>
## Canonical References

- `.planning/phases/999.4-client-pwa-checkout-visual-restyle/999.4-UI-SPEC.md`
  (design system, token table, typography/spacing scales, component inventory,
  interaction states, a11y, copywriting contract).
- `.planning/phases/999.4-client-pwa-checkout-visual-restyle/999.4-05-SUMMARY.md`
  (CheckoutSheet restyle + promo flow as it stands today).
- Locked decisions D-01, D-06, D-09, D-10, D-11, D-12, D-13 from phase 999.4.
</canonical_refs>

<deferred>
## Deferred to a separate phase

- **Real loyalty-bonus redemption** (the mockup's "Списать бонусы"): client
  loyalty-balance source, server-authoritative redemption reducing the amount via
  `price_override_kopecks`, webhook redemption recording, migration + seeds, and
  product decisions (conversion rate, earning rules, Gold-tier system, stacking
  with promo, max-redemption cap). To be planned via `/gsd:plan-phase`.
</deferred>
</content>
</invoke>
