# Phase 86 — UI Review

**Audited:** 2026-06-06
**Baseline:** 86-UI-SPEC.md (approved design contract)
**Screenshots:** Not captured (no dev server on ports 3000, 5173, 8080) — code-only audit

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 2/4 | Closed-night sub-line omits day name required by spec; import bypass bypasses mock/live seam |
| 2. Visuals | 3/4 | Missing `.scroller` class on scroll container; photo strip skeleton uses `overflow:hidden` instead of `overflow-x:auto` causing visible skeleton/loaded mismatch |
| 3. Color | 3/4 | Five hardcoded hex colors in STATIC_PHOTOS break the design token contract; all semantic token usage is otherwise correct |
| 4. Typography | 2/4 | `SectionLabel` injects `fontWeight: 700`, `textTransform: 'uppercase'`, and `letterSpacing: 0.5` as inline overrides — spec explicitly prohibits new inline font-weight/size overrides |
| 5. Spacing | 3/4 | Section vertical gap is 16px (SectionLabel top padding) instead of the spec-declared 24px (`lg`); tagline `marginTop: 4` is undocumented |
| 6. Experience Design | 3/4 | All three states handled; `useClientGymInfo` imported directly from `@/lib/clientQueries` bypassing the `@/data` swap seam, which breaks the mock/http switchability contract |

**Overall: 16/24**

---

## Top 3 Priority Fixes

1. **Swap-seam bypass** (`GymInfoSheet.jsx` line 21) — `import { useClientGymInfo } from '@/lib/clientQueries'` imports the hook directly, bypassing the `apps/client-pwa/src/data/index.js` swap seam. Every other PWA sheet imports from `@/data`. This silently breaks the mock/http switchability and violates the documented architectural pattern. **Fix:** change line 21 to `import { useClientGymInfo } from '@/data'`.

2. **Inline typography overrides in `SectionLabel`** (`GymInfoSheet.jsx` lines 103–105) — `fontWeight: 700`, `textTransform: 'uppercase'`, and `letterSpacing: 0.5` are all inline style overrides. The UI-SPEC Typography section states "This phase introduces 0 new font sizes and 0 new font weights" and "No inline font-weight or font-size overrides are introduced by new code in this sheet." The section eyebrow rendering should rely on the `.t-mini` class alone (or a shared utility class if uppercase/tracking is needed). **Fix:** remove `fontWeight`, `textTransform`, and `letterSpacing` from `SectionLabel` styles; move uppercase and tracking into a dedicated CSS class if needed by the design system.

3. **Closed-night sub-line missing day name** (`GymInfoSheet.jsx` lines 313–314) — Both closed branches output `` `откроется в ${time}` `` without a day name. The Copywriting Contract specifies "откроется {завтра/день недели} в HH:MM" when closed for the night. A gym open 24h except overnight needs this to avoid ambiguity (e.g. "откроется завтра в 08:00" vs "откроется во вторник в 08:00"). **Fix:** derive the day label from `tomorrowIdx` (Пн/Вт/Ср/Чт/Пт/Сб/Вс; "завтра" when `tomorrowIdx === (todayIdx + 1) % 7`) and prepend it to the time string.

---

## Detailed Findings

### Pillar 1: Copywriting (2/4)

**WARNING — Contract copy deviation**

The Copywriting Contract table (86-UI-SPEC.md) declares two distinct closed sub-lines:

| Spec row | Expected |
|---|---|
| Closed sub-line (will open today) | `откроется в HH:MM` |
| Closed sub-line (closed for night/day) | `откроется {завтра/день недели} в HH:MM` |

The implementation collapses both into the same template:
- Line 313: `` `откроется в ${status.todayRow.open}` `` (today branch — correct)
- Line 314: `` `откроется в ${status.nextOpenTime}` `` (night branch — MISSING day name)

The seeded gym data has hours Mon–Sun 10:00–23:00. At 02:00 Monday the closed-night branch fires and would display "откроется в 10:00" — no day name, ambiguous. Spec requires "откроется завтра в 10:00" (or the weekday name).

**WARNING — Architectural copy concern**

All remaining Russian copy strings match the Copywriting Contract exactly:
- Line 129: `Загрузка информации о зале…` (aria-label) — PASS
- Line 201: `Не удалось загрузить информацию о зале` — PASS
- Line 202: `Потяните вниз, чтобы попробовать снова.` — PASS
- Line 295: `ЧАСЫ РАБОТЫ`, line 363: `УДОБСТВА`, line 398: `ПРАВИЛА`, line 430: `КОНТАКТЫ`, line 494: `МЫ В СОЦСЕТЯХ` — all PASS
- Line 311: `до ${status.todayRow.close}` — PASS
- Line 323: `Сейчас открыто` / `Закрыто` — PASS
- Line 454: `Позвонить`, line 482: `Написать` — PASS
- Social labels from `item.label` (line 520) — PASS

No generic English labels (`Submit`, `Cancel`, etc.) found. Score penalty is solely for the day-name omission in the night-closed branch.

---

### Pillar 2: Visuals (3/4)

**WARNING — Missing `.scroller` class**

The spec Layout section declares the scroll area as a `.scroller` class wrapper (line: `─── .scroller ───────────────────────────────────`). No element in `GymInfoSheet.jsx` carries `className="scroller"` or any `scroller` class. `PullToRefresh` wraps the content but its internal DOM structure may not apply the `.scroller` styles (momentum scroll, `-webkit-overflow-scrolling: touch`, safe-area padding). Other sheets (BonusHistorySheet, CardSheet) use an explicit `.scroller` div inside `PullToRefresh`. The absence breaks momentum scroll on iOS.

**WARNING — Photo strip skeleton/loaded structural mismatch**

- Skeleton (line 141): `overflow: 'hidden'` — photos are clipped, strip is NOT scrollable in loading state
- Loaded (line 264): `overflowX: 'auto', scrollbarWidth: 'none'` — photos scroll correctly

This means the skeleton strip appears as a static row (no overflow hint) while the loaded strip becomes a horizontal scroller. The skeleton does not preserve the layout of its loaded equivalent, violating the spec's loading-state contract: "All skeleton containers maintain the same structural padding/margins as their loaded equivalents, preventing layout shift."

**PASS items:**
- Visual hierarchy is clear: `t-h2` name > `t-body` tagline > chips follows the spec hierarchy
- Open/closed badge uses system `.chip-accent` / `.chip-danger` classes — no custom colors on badge
- Icon-only buttons are wrapped with `aria-hidden="true"` on the SVG (Icon.jsx default) and the skeleton has `aria-label="Загрузка информации о зале…"`
- Today row puts day abbrev and "сегодня" hint on the left, hours + badge on the right — matches spec
- Conditional social section render guard (`data.social && data.social.length > 0`) — PASS

---

### Pillar 3: Color (3/4)

**WARNING — Five hardcoded hex colors in STATIC_PHOTOS**

Lines 26–30 define `bg` values as hex strings:
```
'#3f4444', '#2c5e3f', '#7c5e3f', '#5a4d3a', '#4a3f5e'
```

These are applied as `background: photo.bg` on the photo strip cells (line 273). The UI-SPEC Color section states only `var(--bg)`, `var(--surface)`, `var(--accent)`, `var(--danger)`, `var(--accent-soft)`, `var(--accent-deep)`, `var(--surface-2)`, `var(--border)`, `var(--text)`, `var(--text-2)`, `var(--text-3)`, and `var(--danger-soft)` are permitted. Hardcoded hex bypasses the dark-mode token system — the same hex values will appear in dark mode, where they may clash with the `#1a1715` background.

The spec notes "Photo strip cells: height: 80px; border-radius: var(--r-lg) — decorative height, not tied to spacing scale; inherited from the existing photo-strip pattern." This acknowledges the static photo strip, but does NOT grant an exemption for hardcoded bg colors outside the token system.

**PASS items (all other color usage):**
- `var(--accent-soft)` on amenity icon containers — correct (spec: "Icon color in amenity cells: `var(--accent-deep)` on `var(--accent-soft)` background")
- `var(--accent)` / `var(--danger)` only on badge classes — 60/30/10 distribution respected
- `var(--danger-soft)` on error circle — correct
- `rgba(255,255,255,0.85)` on photo strip icons/labels — spec-declared exception ("color: rgba(255,255,255,0.85)")
- No raw Tailwind palette classes (`bg-slate-900`, etc.) — consistent with ESLint ban
- `var(--text)`, `var(--text-2)`, `var(--text-3)` used correctly throughout

---

### Pillar 4: Typography (2/4)

**BLOCKER — Inline typography overrides in `SectionLabel`**

`SectionLabel` (lines 100–108) applies three inline style properties that the spec prohibits:

| Property | Value | Spec verdict |
|---|---|---|
| `fontWeight: 700` | Overrides `.t-mini` weight | Prohibited — "No inline font-weight or font-size overrides are introduced by new code" |
| `textTransform: 'uppercase'` | Not in `.t-mini` class | Introduced by this phase, not an inherited exception |
| `letterSpacing: 0.5` | Unitless (= 0.5px) | Introduced by this phase; not in spec's spacing exception list |

The spec Typography section is explicit: "This phase introduces 0 new font sizes and 0 new font weights. It consumes existing `.t-*` utility classes... No inline `font-weight` or `font-size` overrides are introduced by new code in this sheet."

All six `SectionLabel` usages carry these overrides. While the `textTransform: uppercase` and `letterSpacing` serve a legitimate visual purpose (caps section eyebrows), they are uncontrolled inline style values outside the design system. If `.t-mini` in `styles.css` does not include uppercase/tracking, the correct fix is to add a `.t-eyebrow` or `.t-label` class to `styles.css`, not to inline them per-component.

**PASS items:**
- `.t-h2` on gym name (line 243) — correct
- `.t-body` on tagline (line 245) — correct
- `.t-h3` on today day abbrev (line 306) — correct
- `.t-small` on all secondary text (lines 307, 309, 347, 348) — correct
- `.t-body` with `fontVariantNumeric: tabular-nums` on hours (lines 319, 348) — correct per spec
- `.t-mini` on amenity labels (line 381), number circles (line 415), photo tags (line 281) — correct
- `.t-h3` on contacts primary (lines 453, 481, 520) — correct
- `.t-small` on contacts secondary (lines 454, 482, 521) — correct
- Total distinct typography classes: `t-h2`, `t-h3`, `t-body`, `t-small`, `t-mini` — 5 classes, all from existing `.t-*` system

---

### Pillar 5: Spacing (3/4)

**WARNING — Section vertical gap is 16px, spec declares 24px**

The spacing scale (86-UI-SPEC.md) declares `lg = 24px` for "Section vertical gap between groups." Between sections, the gap comes from `SectionLabel`'s `padding: '16px 16px 8px'` — giving 16px above the label text. No `margin-bottom` is applied to `.card` section containers. The resulting visual gap between a card bottom edge and the next section label is 16px, not the specified 24px.

**WARNING — `marginTop: 4` on tagline (line 245)**

`marginTop: 4` is applied to the tagline div. 4px is the `xs` token in the spec scale, so it is a valid scale value. However, the spec [1] Hero section does not mention a gap between name and tagline; only "gap 8px below tagline" for the address chip row is specified. The 4px value is technically in-scale but undocumented in the Hero layout spec.

**PASS items:**
- Hero card `padding: 16, margin: '8px 16px 0'` — matches spec exactly (`padding: 16px; margin: 8px 16px 0`)
- Photo strip `padding: '12px 0 4px'`, inner `padding: '0 16px'`, `gap: 8` — matches spec
- Photo strip cells `width: 88, height: 80, gap: 4` — matches spec
- Hours today row `padding: '12px 16px'`, `gap: 12` — matches spec
- Weekly row `padding: '12px 16px'`, `gap: 12` — matches spec
- Weekly hairline `marginLeft: 56` — matches spec (16 + 28 + 12 = 56)
- Amenities grid `padding: 12`, `gap: 8`, cells `gap: 8, padding: '8px 4px'` — matches spec
- Amenity icon container `width: 32, height: 32, borderRadius: 8` — matches spec
- Rules row `padding: '12px 16px'`, `gap: 12` — matches spec
- Rules hairline `marginLeft: 52` — matches spec (16 + 24 + 12 = 52)
- Number circle `width: 24, height: 24` — matches spec
- Contact rows `padding: '12px 16px'`, `gap: 12` — matches spec
- Contact icon container `width: 32, height: 32, borderRadius: 8` — matches spec
- Error state `padding: '40px 24px'` — matches spec
- Error circle `width: 64, height: 64`, `margin: '0 auto 16px'` — matches spec
- Bottom safe-area `height: 32` — matches spec (`xl = 32px`)
- Hairline `height: 0.5` — matches spec (inherited retina hairline exception)

Only the section vertical gap and the undocumented tagline marginTop are non-conforming. No arbitrary `[Npx]` Tailwind values; all spacing is inline CSS with values from the spec scale.

---

### Pillar 6: Experience Design (3/4)

**WARNING — Swap seam bypassed (architectural violation)**

Line 21: `import { useClientGymInfo } from '@/lib/clientQueries'`

The `apps/client-pwa/src/data/index.js` swap seam is the project's architectural boundary that allows the same component tree to run against either mock services or the live backend. The seam re-exports `useClientGymInfo` at line 57 of `data/index.js`. Every other PWA data hook in sheets (loyalty, home, etc.) imports from `@/data`. This direct import bypasses the seam, meaning:
- In mock mode (`VITE_API_MODE=mock`), this component will attempt a real HTTP call instead of using mock data
- The ESLint `import/no-restricted-paths` rule (`eslint.config.js:8-9, 71-83`) enforcing the swap seam may trigger on this file

**PASS items:**
- Loading state: full `GymInfoSkeleton` component with all sections represented (`aria-label="Загрузка информации о зале…"`) — PASS
- Error state: `GymInfoError` with generic copy (no raw error object echoed) — PASS (T-86-10 honored)
- Pull-to-refresh: `PullToRefresh` wraps the entire content area; `handleRefresh` calls `gymInfoQuery.refetch()` — PASS
- Conditional renders: hours shown only if `data.hours.length > 0`, amenities if `> 0`, rules if `> 0`, social if `> 0` — PASS
- Partial data guard: metro chip only rendered if `data.metro` present (line 252); tagline only if `data.tagline` (line 244); contacts only if `data.phone || data.email` (line 428) — PASS
- Social links: `rel="noopener noreferrer"` on all `target="_blank"` links (line 502) — T-86-09 honored
- Social URL construction uses fixed prefixes (line 115–116), handle `@` stripped — PASS
- Empty state: spec states "not applicable" for this sheet — correctly not implemented

**NOTE — Icons `dumbbell`, `run`, `yoga` not in `Icon.jsx`**

`STATIC_PHOTOS` references icons `dumbbell` (line 26), `run` (line 27), and `yoga` (line 30). `Icon.jsx` does not define any of these keys. When `paths[name]` is `undefined`, the `<svg>` renders an empty element — no visible icon, no error thrown. This is a silent visual defect: three of five photo cells show no icon. The spec's "Component Reuse Checklist" only lists icons already in `Icon.jsx` for amenities; the photo strip icon names are not validated there, but were apparently assumed to exist. This does not break user task completion (the sheet opens and data is visible) but represents a render defect.

---

## Additional Findings (below top 3)

4. **Photo strip skeleton has `overflow: hidden` instead of `overflow-x: auto`** — Skeleton strip is not scrollable; loaded strip is scrollable. This causes a layout-shift-style mismatch where the skeleton content snaps to a different scroll position on data load. Fix: change line 141 skeleton strip to `overflowX: 'auto', scrollbarWidth: 'none'` matching the loaded version.

5. **Missing `.scroller` class on scroll container** — The spec Layout section and Component Reuse Checklist both reference `.scroller` from `styles.css`. The loaded content area has no `className="scroller"` applied. Other sheets (LoyaltySheet) use an explicit `.scroller` div. Fix: wrap the loaded content `<div>` (line 239) in `<div className="scroller">` or add `className="scroller"` to that div.

6. **Section vertical gap 16px vs spec 24px** — `SectionLabel` top padding is 16px; spec spacing scale declares `lg = 24px` for section gaps. Fix: change `SectionLabel` padding to `'24px 16px 8px'`, or add `marginBottom: 8` to section `.card` containers to bring the total gap to 24px.

7. **Three STATIC_PHOTOS icons missing from Icon.jsx** — `dumbbell`, `run`, and `yoga` are not defined in `Icon.jsx` paths object. The SVG renders empty for those three cells. Fix: either add SVG path definitions for these three icons to `Icon.jsx`, or replace with icons that already exist in the set (e.g. `barbell` for 'Зал', `flame` for 'Кардио', `sparkle` for 'Студия').

8. **Five hardcoded hex bg colors on photo cells** — Lines 26–30 use raw hex values that do not participate in the dark-mode token system. Fix: define five themed tokens in `styles.css` (e.g. `--photo-gym-bg`, `--photo-cardio-bg`, etc.) with appropriate light/dark values, or use existing semantic tokens with opacity modifiers.

---

## Files Audited

- `/Users/andre/Workspace/Development/clubcore/apps/client-pwa/src/screens/sheets/GymInfoSheet.jsx` — primary audit target
- `/Users/andre/Workspace/Development/clubcore/apps/client-pwa/src/components/Icon.jsx` — icon availability check
- `/Users/andre/Workspace/Development/clubcore/apps/client-pwa/src/data/index.js` — swap seam verification
- `/Users/andre/Workspace/Development/clubcore/.planning/phases/86-gym-info-cms/86-UI-SPEC.md` — design contract baseline
- `/Users/andre/Workspace/Development/clubcore/.planning/phases/86-gym-info-cms/86-CONTEXT.md` — implementation decisions
- `/Users/andre/Workspace/Development/clubcore/.planning/phases/86-gym-info-cms/86-01-SUMMARY.md` — backend foundation
- `/Users/andre/Workspace/Development/clubcore/.planning/phases/86-gym-info-cms/86-02-SUMMARY.md` — HTTP router
- `/Users/andre/Workspace/Development/clubcore/.planning/phases/86-gym-info-cms/86-03-SUMMARY.md` — PWA wiring
- `/Users/andre/Workspace/Development/clubcore/.planning/phases/86-gym-info-cms/86-03-PLAN.md` — implementation plan
