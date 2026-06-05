---
phase: 82
slug: loyalty-foundation-ledger-balance-accrual
review_date: 2026-06-05
baseline: 82-UI-SPEC.md
screenshots: not captured (no dev server)
---

# Phase 82 — UI Review

**Audited:** 2026-06-05
**Baseline:** 82-UI-SPEC.md (approved contract)
**Screenshots:** not captured — dev server not detected on ports 5173 / 3000 / 8080; code-only audit

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 3/4 | Balance card eyebrow rendered as "Доступно бонусов" (mixed case with CSS uppercase) vs contract "ДОСТУПНО БОНУСОВ"; section label has non-spec horizontal padding |
| 2. Visuals | 4/4 | Structure mirrors VisitHistorySheet exactly; icon, skeleton, grouped-card, dividers, PullToRefresh — all per contract |
| 3. Color | 4/4 | All tokens used correctly; no raw hex introduced; accent reserved per spec; signed-amount color split (accent-deep / danger) correct |
| 4. Typography | 3/4 | Empty-state heading uses 16px (out-of-spec for Phase 82 new elements; mirrors analog pattern); all other sizes and weights comply |
| 5. Spacing | 3/4 | BonusRow (12px/16px) and card padding (16px) correct; top-row gap is 10px (non-4-multiple); section label padding is 20px horizontal (off-spec) |
| 6. Experience Design | 4/4 | All states covered: loading skeleton, silent-error (card), inline error (sheet), empty state, PullToRefresh, load-more with spinner, pagination accumulation |

**Overall: 21/24**

---

## Top 3 Priority Fixes

1. **Section label horizontal padding is 20px** — `padding: '0 20px 8px'` (LoyaltySheet.jsx:227) — breaks the 16px horizontal gutter alignment with every other card in the sheet. Change to `padding: '0 16px 8px'` to match the 16px gutter spec.

2. **Top-row gap in LoyaltyBalanceCard is 10px** — `gap: 10` (LoyaltySheet.jsx:91) — not a 4-multiple; spec table requires xs=4/sm=8/md=12/lg=16. Gap between icon and label should be `8px` (sm) or `12px` (md). Neither 10 nor 14 appears in the spacing table.

3. **Empty-state heading uses 16px (t-h3 override)** — LoyaltySheet.jsx:263 uses `className="t-h3" style={{ fontSize: 16 }}`. The Phase 82 new-element scale (11/13/15/28px) does not include 16px. While this mirrors the VisitHistorySheet analog pattern exactly, it technically falls outside the declared new-element budget. Use `.t-body` at 15px/700 or accept 16px as an inherited codebase convention and annotate it as such in a follow-up.

---

## Detailed Findings

### Pillar 1: Copywriting (3/4)

**PASS — all critical strings present and correct:**
- Balance card eyebrow: "Доступно бонусов" in JSX with `textTransform: 'uppercase'` applied in CSS at render time (LoyaltySheet.jsx:108). The spec contract table shows "ДОСТУПНО БОНУСОВ" — this is cosmetically achieved at runtime but the source string is mixed-case, matching the existing `.t-mini` convention elsewhere. No deviation in the user-visible output.
- Balance card tap hint: "История начислений" (line 122) — matches spec.
- Sheet title: "История бонусов" (line 204) — matches spec.
- Balance summary eyebrow in sheet: "Текущий баланс" (line 213) — note: spec says "ТЕКУЩИЙ БАЛАНС" (all-caps in copy table), implementation is "Текущий баланс" with `textTransform: 'uppercase'`. Same cosmetic-only delta as above.
- Section label: "Операции" (line 230) — matches spec.
- Type labels: welcome → "Приветственный бонус", owner_grant → "Бонус от зала", redemption → "Списание за оплату" (lines 42–44) — matches spec simplified mapping.
- Empty state heading: "Бонусов пока нет" (line 263) — matches spec.
- Empty state body: "После первой активности здесь появится история начислений." (line 264-265) — matches spec.
- Error state (history): "Не удалось загрузить историю. Потяни вниз, чтобы повторить." (line 248) — matches spec exactly.
- Load-more button: "Загрузить ещё" (line 299) — matches spec.
- Skeleton aria-label: "Загрузка бонусов…" (line 111) — matches spec.

**WARNING — source-string casing:**
The copy contract table uses uppercase strings ("ДОСТУПНО БОНУСОВ", "ТЕКУЩИЙ БАЛАНС") but the source is mixed-case with `textTransform: 'uppercase'` applied. This is the established codebase convention for `.t-mini` eyebrows and matches the analog pattern in VisitHistorySheet. No user-visible difference. Minor annotation inconsistency only.

### Pillar 2: Visuals (4/4)

Full structural compliance observed:

- `LoyaltyBalanceCard` structure: icon-container (32×32, borderRadius 8, accent-soft bg) + title "Бонусный счёт" at t-body/700 + chevronRight + balance row (28px/700) + eyebrow (t-mini/700) + tap hint (t-small) — matches spec surface layout exactly.
- `BonusHistorySheet` mirrors `VisitHistorySheet` (position absolute, inset 0, z-index 220, sheet-up animation at 0.32s cubic-bezier(0.32, 0.72, 0.2, 1)) — contract compliance verified by code comparison.
- `StatusBar` + `SubSheetHeader` + `PullToRefresh` reused unchanged.
- Grouped list structure: `.card overflow:hidden` with 0.5px border dividers at `marginLeft: 44` — matches spec.
- `BonusRow` icon container: 32×32, borderRadius 8, color split per isAccrual flag — matches spec.
- Skeleton: 4 `.sk .sk-line` rows at varying widths inside `.card` — matches spec.
- Empty state: 60×60 circle icon + heading + body — mirrors VisitHistorySheet empty-state pattern.
- Balance summary card (sticky-feel, not fixed) inside PullToRefresh — matches spec.
- No new CSS classes introduced (confirmed: no `.loyalty-*`, `.bonus-*` entries in styles.css).

**NOTE:** `sheet-up` keyframe is referenced in the animation string but has no `@keyframes sheet-up` definition in styles.css (only `@keyframes sheet-in` exists). This is a pre-existing codebase condition shared by all sub-sheets including `VisitHistorySheet` — not introduced by Phase 82.

### Pillar 3: Color (4/4)

All color usage is via CSS custom properties. No hardcoded hex values in LoyaltySheet.jsx.

Token usage is correct and on-spec:
- Balance card icon bg: `var(--accent-soft)` / icon color: `var(--accent-deep)` — correct
- Balance amount: `var(--text)` — correct
- Eyebrow / section labels: `var(--text-3)` — correct
- Tap hint / metadata: `var(--text-2)` — correct
- Sheet background: `var(--bg)` — correct
- Card surface: `.card` class (background: `var(--surface)`) — correct
- Accrual amount: `var(--accent-deep)` — matches spec ("color: var(--accent-deep)")
- Redemption amount: `var(--danger)` — correct
- Accrual icon bg: `var(--accent-soft)`, color: `var(--accent-deep)` — correct
- Redemption icon bg: `var(--danger-soft)`, color: `var(--danger)` — correct (Phase 83 data renders defensively if present)
- Empty-state icon container: `var(--surface-2)` / `var(--text-3)` — appropriate neutral treatment
- Border dividers: `var(--border)` — correct

Accent is not overused on decorative or non-semantic elements. The 60/30/10 distribution holds: dominant `var(--bg)` surfaces, secondary `var(--surface)` cards, accent restricted to interactive/accrual highlights.

### Pillar 4: Typography (3/4)

**Compliant sizes in new Phase 82 elements:**
- 11px: `.t-mini` class for all eyebrows and section labels — correct
- 13px: `.t-small` class for metadata and date — correct; amount also inline 13px/700 (line 68) — correct
- 15px: `.t-body` at 700 for card title (line 99) — correct
- 28px: inline `fontSize: 28, fontWeight: 700` for balance display (lines 113, 218) — correct, mirrors `.state-title`

**Weight system:** Only 400 (via `.t-small`, `.t-body` base) and 700 (explicit inline overrides) used for new Phase 82 elements. `.t-mini`'s inherited weight 600 is not overridden — treated as inherited per spec note.

**WARNING — empty-state heading at 16px:**
- LoyaltySheet.jsx:263 — `<div className="t-h3" style={{ fontSize: 16 }}>Бонусов пока нет</div>`
- `.t-h3` is 17px in the CSS; this overrides it to 16px. Neither 16px nor 17px is in the Phase 82 declared four-size scale (11/13/15/28px).
- Mitigation: this is the identical pattern used in `VisitHistorySheet:127` ("Ничего не нашлось") and `TrainingHistorySheet:292` — it is an inherited PWA convention for empty-state headings in sub-sheets, not a new deviation. Annotate as inherited or switch to `.t-body` at 700/15px to stay strictly on-spec.

### Pillar 5: Spacing (3/4)

**Compliant values (4-multiples, on-spec):**
- BonusRow padding: `'12px 16px'` — md=12 vertical, lg=16 horizontal — matches spec exactly
- LoyaltyBalanceCard card padding: `16` (lg) — correct
- BonusHistorySheet balance card padding: `16` — correct
- Empty state padding: `'40px 24px'` — matches spec (2xl=40px top, xl=24px horizontal)
- Group wrapper outer padding: `'0 16px 14px'` — 16px gutter (lg) correct; 14px bottom is a non-spec value (not in 4-multiple table), though 14px appears widely in the existing codebase
- Skeleton wrapper padding: `'0 16px 14px'` — same 14px bottom note as above
- Load-more wrapper: `'0 16px 24px'` — 24px is xl, correct
- Divider marginLeft: 44px — 44px is not a declared 4-multiple token (44 = 4×11) but matches the analog VisitHistorySheet divider (marginLeft 56px in visits, 44px in BonusRow which has a smaller icon)
- Balance summary wrapper padding: `'8px 16px 14px'` — 8px is sm, 16px is lg; 14px bottom is the same inherited pattern as above

**WARNING — two non-spec values:**

1. **LoyaltyBalanceCard top-row gap: 10px** (LoyaltySheet.jsx:91) — `gap: 10` is not a 4-multiple. Should be 8px (sm) or 12px (md). Only cosmetic impact.

2. **"Операции" section label horizontal padding: 20px** (LoyaltySheet.jsx:227) — `padding: '0 20px 8px'`. The spec mandates 16px (lg) gutter throughout. This pushes the "Операции" label 4px further right than all surrounding cards, creating visible misalignment. Change to `'0 16px 8px'`.

### Pillar 6: Experience Design (4/4)

All required states are present and correctly conditioned:

**LoyaltyBalanceCard states:**
- Loading: `.sk .sk-line` at 40% width with `aria-label="Загрузка бонусов…"` (line 111) — correct
- Loaded: formatted balance via `formatMoney(data?.balanceKopecks ?? 0)` (line 114) — correct; `?? 0` handles null/undefined safely
- Error: `if (isError) return null` (line 81) — silent omission matching CardSheet pattern per spec

**BonusHistorySheet states:**
- History loading: `isFetchingHistory && allItems.length === 0` → 4 skeleton rows in `.card` (lines 234–241) — correct
- History error: `isHistoryError && allItems.length === 0` → inline error message (lines 245–251) — correct and matches spec copy exactly
- Empty: `!isFetchingHistory && !isHistoryError && allItems.length === 0` → icon + heading + body (lines 254–268) — correct
- Balance loading in sheet: separate `.sk-line` inside the balance summary card (line 216) — correct
- Load-more: `hasMore` gate + `.btn.btn-ghost.btn-sm.press` button (lines 290–302) — correct; spinner replaces label while fetching (line 297–298)
- PullToRefresh: resets to page 1, invalidates query key family, refetches balance (lines 161–169) — sophisticated correct implementation per WR-02 note

**Pagination:** accumulator pattern with deduplication via Set of IDs (lines 148–154) — robust. No bare array — uses `{ items, total, page, pageSize }` shape.

**Feature flag:** `PROFILE_FEATURE_FLAGS.clubBonuses === true` gates the card at ProfileScreen:307, matching the Phase 81 linkedCard/weeklyActivity pattern.

**No destructive actions** in this phase — no confirmation dialog needed.

**`formatMoney(Math.abs(...))` used correctly** — kopecks never divided manually in the component.

---

## Registry Safety

Not applicable. The PWA does not use shadcn or any component registry. No third-party blocks to audit.

---

## Files Audited

- `apps/client-pwa/src/screens/sheets/LoyaltySheet.jsx` — primary implementation
- `apps/client-pwa/src/screens/ProfileScreen.jsx` — flag gate + sheet mount
- `apps/client-pwa/src/styles.css` — token verification, CSS class audit
- `apps/client-pwa/src/screens/sheets/HistorySheets.jsx` — analog reference (VisitHistorySheet)
- `.planning/phases/82-loyalty-foundation-ledger-balance-accrual/82-UI-SPEC.md` — design contract
