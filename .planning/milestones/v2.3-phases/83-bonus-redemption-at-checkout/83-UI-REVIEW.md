---
phase: 83
slug: bonus-redemption-at-checkout
reviewed: 2026-06-05
baseline: 83-UI-SPEC.md
screenshots: not captured (no dev server)
verdict: ADVISORY — non-blocking
---

# Phase 83 — UI Review

**Audited:** 2026-06-05
**Baseline:** `.planning/phases/83-bonus-redemption-at-checkout/83-UI-SPEC.md`
**Screenshots:** Not captured (no dev server detected on ports 3000 / 5173)
**File audited:** `apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx`

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 4/4 | All spec copy matched; `~` qualifier correct; toast copy matches |
| 2. Visuals | 4/4 | Bonus row is structural analog of promo row; ring preserved as decorative chrome |
| 3. Color | 4/4 | All color via CSS vars; no raw hex; accent usage matches spec reservation |
| 4. Typography | 4/4 | No new sizes/weights; all text uses inherited `.co-bonus-*` / `.co-sum-row` classes |
| 5. Spacing | 4/4 | Zero new CSS classes; all spacing inherited from pre-existing `.co-*` rules |
| 6. Experience Design | 4/4 | Loading/error → section hidden; toggle reversible; D-06 invariant intact |

**Overall: 24/24**

---

## Top 3 Priority Fixes

No blockers or warnings found. Three minor notes below — informational only.

1. **Estimate floor refinement vs spec** — The spec states `Math.min(balanceKopecks, total)` but the implementation computes `Math.min(balanceKopecks, Math.max(0, total - 1))`. This is a deliberate tightening (WR-03 fix note at line 379) that prevents the estimate from reaching 0 kopecks (ЮKassa minimum). The deviation is correct and intentional — no action required, but the spec should be updated to match the implementation if it is ever re-read as ground truth.

2. **Bonus section between promo and summary** — The spec places the bonus section as "2b" between the promo section and the summary card. The implementation follows this ordering exactly (lines 515–551 sit between `PromoSection` and the `co-sec-label` "Итог"). Confirmed correct — noted to make the section-order contract explicit for future auditors.

3. **Space before `~` chip** — The spec example shows `Бонусы<span className="co-mini">~</span>` with no space (same as implementation at line 577). The promo row, by contrast, inserts `{' '}` before the promo-code chip (line 567). The asymmetry is intentional: the promo chip shows a code word that benefits from whitespace separation; the tilde chip is a modifier symbol that reads better attached. Consistent with spec — no action required.

---

## Detailed Findings

### Pillar 1: Copywriting (4/4)

All new and modified copy matches the spec's Copywriting Contract exactly.

- Toggle subtitle (line 532): `На счёте <b>{formatMoney(balanceKopecks)}</b>` — matches spec. `toGold` text correctly absent.
- Bonus discount row label (line 577): `Бонусы` — matches spec.
- Estimate chip (line 577): `<span className="co-mini">~</span>` — tilde present, `.co-mini` class used. Matches spec.
- Toggle ON toast (line 544): `'Бонусы будут списаны при оплате'` — matches spec ("при оплате" clause present).
- Toggle OFF toast (line 544): `'Списание бонусов отменено'` — matches spec.
- Pay button (line 686): `Оплатить · {bonusOn && bonusEstimateKopecks > 0 ? '~' : ''}{totalDisplay}` — `~` prefix gated correctly, matches spec pattern.
- Section label (line 520): `Бонусы клуба` — unchanged, inherited.
- Toggle title (line 530): `Списать бонусы` — unchanged, inherited.

No generic labels, no missing qualifiers.

### Pillar 2: Visuals (4/4)

- Bonus discount row (lines 574–581) is a structural clone of the promo discount row (lines 563–571): same `co-sum-row discount` wrapper, same `co-sl-tag` + `co-mini` chip pattern, same `co-sv` value span. Direct analog confirmed.
- Ring SVG (lines 522–526) preserved with all existing classes (`co-bonus-ring`, `co-bonus-track`, `co-bonus-prog`, `co-bonus-coin`). No `stroke-dashoffset` inline style applied in JSX — the CSS static value at `styles.css:2124` remains the sole source, as required.
- `BONUS_PLACEHOLDER` is gone (grep returns no match). Real `formatMoney(balanceKopecks)` in its place.
- No visual chrome added or removed beyond spec scope.
- Section hidden when `balanceKopecks === 0` OR `loyaltyLoading === true` (line 518 condition): `!loyaltyLoading && balanceKopecks > 0`. Correct — no empty-state or skeleton renders.

### Pillar 3: Color (4/4)

- No raw hex values present in CheckoutSheet.jsx. All 14 inline-style color references use `var(--*)` tokens (`var(--bg)`, `var(--surface)`, `var(--accent)`, `var(--border)`, `var(--text)`, `var(--text-3)`, `var(--surface-2)`).
- The bonus section itself uses zero new inline color — all color is delegated to the existing `.co-bonus-*` CSS classes which carry the spec-reserved tokens (`var(--accent)` for switch ON, `var(--accent-deep)` for `co-bonus-sub b` and `co-bonus-coin`, `var(--border)` for track).
- `co-sum-row.discount` class handles `var(--accent-deep)` coloring for the bonus discount row — no new CSS rule needed, identical to promo row. Confirmed at `styles.css:1859–1860`.

### Pillar 4: Typography (4/4)

No new font sizes or weights introduced. All text in the bonus section delta uses inherited classes:

- `.co-bonus-title` — 14px / 650 (styles.css:2137)
- `.co-bonus-sub` — 12px / 400, `b` child 700 (styles.css:2138–2139)
- `.co-sum-row` — 14px / 400 for label (styles.css:1844+)
- `.co-sv` in `.co-sum-row.discount` — 14px / 650 (styles.css:1854, 1859)

The `<b>` tag for balance amount (line 532) reuses the pre-existing `.co-bonus-sub b` rule — not a new element.

### Pillar 5: Spacing (4/4)

- Zero new CSS classes introduced. Grep on styles.css confirms all `.co-bonus-*`, `.co-sum-row`, `.co-mini`, `.co-sl-tag`, `.co-sv` classes are pre-existing.
- The bonus section JSX applies no new inline spacing. The only inline style overrides in the section are on the save-card row (line 644: `padding: '14px 16px', gap: 14`) — which is a pre-existing override unrelated to Phase 83.
- New JSX elements (lines 519–551) use only class-driven spacing from existing `.co-*` rules.
- No arbitrary `[Xpx]` or `[Xrem]` Tailwind values (this is a plain-CSS PWA, not Tailwind — no class scanner needed).

### Pillar 6: Experience Design (4/4)

- **Loading state:** `loyaltyLoading === true` → section not rendered (line 518). No skeleton, consistent with spec's CardSheet pattern.
- **Error state:** `loyaltyBalance === undefined` after load → `balanceKopecks` falls back to `0` via `?? 0` (line 151) → section not rendered. Silent hide matches spec.
- **Empty state (balance = 0):** Guard `balanceKopecks > 0` hides section. No zero-balance prompt rendered.
- **Toggle reversibility:** `setBonusOn` flips both ways; toast fires on both transitions. No confirmation needed (reversible action, per spec).
- **D-06 invariant:** `total` and `discount` state variables not mutated by bonus logic. `bonusEstimateKopecks` and `estimatedTotal` are derived constants (lines 380–381), not `useState`. Confirmed.
- **Checkout wiring:** Both `checkoutMembership.mutateAsync` (line 241) and `checkoutPtPackage.mutateAsync` (line 252) spread `loyaltyRedeemKopecks: balanceKopecks` identically, gated on `bonusOn && balanceKopecks > 0`. Matches spec's Change 2 wiring exactly.
- **Savings bar:** `totalDiscount = discount + bonusEstimateKopecks` (line 387); `savePct` derived from `estimatedTotal` (line 388). Combined promo + bonus display correct.
- **CountUp deps:** `useCountUp(estimatedTotal, [estimatedTotal, bonusOn, bonusEstimateKopecks])` (line 384) — deps include bonus state, animation re-fires on toggle. Matches spec note 5.

---

## Registry Safety

Not applicable. `apps/client-pwa` is a plain-CSS PWA with no shadcn, no `components.json`, and no third-party component registry. Registry audit skipped per spec gate.

---

## Files Audited

- `/Users/andre/Workspace/Development/clubcore/apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx` — primary implementation file
- `/Users/andre/Workspace/Development/clubcore/apps/client-pwa/src/styles.css` — CSS class definitions (lines 1844–1953, 2103–2165) verified for pre-existence of all used classes
- `/Users/andre/Workspace/Development/clubcore/.planning/phases/83-bonus-redemption-at-checkout/83-UI-SPEC.md` — design contract baseline
