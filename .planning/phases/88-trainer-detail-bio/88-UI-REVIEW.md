# Phase 88 — UI Review

**Audited:** 2026-06-06
**Baseline:** 88-UI-SPEC.md (approved design contract)
**Screenshots:** Not captured (no dev server detected on ports 5173, 3000, 8080 — code-only audit)

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 4/4 | All contract strings exact-match; aria-label and img alt present |
| 2. Visuals | 3/4 | Solid hierarchy; SectionLabel inline overrides diverge from .t-mini base silently |
| 3. Color | 4/4 | Zero hardcoded colors; accent used only on CTA; full token compliance |
| 4. Typography | 3/4 | SectionLabel applies fontWeight:700 overriding .t-mini font-weight:600 — undocumented |
| 5. Spacing | 3/4 | Skeleton name margin '8px auto 0' vs spec '8px auto'; spec hero-gap diagram vs container property internally inconsistent |
| 6. Experience Design | 3/4 | Re-fetch skeleton gap: isLoading is false on pull-to-refresh refetch after first load; no ErrorBoundary anywhere in PWA |

**Overall: 20/24**

---

## Top 3 Priority Fixes

1. **SectionLabel fontWeight:700 overrides .t-mini base silently** — User sees slightly bolder section labels than the design system intends; the `.t-mini` class defines `font-weight: 600` but the inline `fontWeight: 700` in `SectionLabel` (TrainerDetailSheet.jsx:61, mirrored from GymInfoSheet.jsx:103) silently wins. Fix: remove the inline `fontWeight: 700` from `SectionLabel` and let `.t-mini` govern weight, OR update `styles.css` `.t-mini` to `font-weight: 700` to codify the intent across all sheets.

2. **Re-fetch after error shows stale error UI instead of skeleton** — When the user pulls-to-refresh from an error state, `query.isLoading` is `false` (data was never loaded) and `query.isError` remains `true` until the refetch resolves, so the error copy stays visible during the network request. Fix: add `{(query.isLoading || query.isFetching) && <TrainerDetailSkeleton />}` and remove the separate `{query.isError && ...}` branch when fetching is in progress — or follow the NotificationsSheet pattern which checks `isFetching` directly.

3. **Skeleton name margin bottom explicitly 0 contradicts spec** — Spec (88-UI-SPEC.md Loading section) states `margin: 8px auto` for the name skeleton line; implementation (TrainerDetailSheet.jsx:80) uses `margin: '8px auto 0'`, explicitly zeroing the bottom margin. In the flex context the uniform gap:8 container means bottom=0 produces the same visual, but the explicit `0` deviates from the spec shorthand and could break if skeleton structure changes. Fix: change to `margin: '8px auto'` at TrainerDetailSheet.jsx:80.

---

## Detailed Findings

### Pillar 1: Copywriting (4/4)

All seven copywriting contract items from the UI-SPEC are implemented verbatim:

| Contract item | Expected | Actual | File:Line |
|---------------|----------|--------|-----------|
| Sheet title | Тренер | Тренер | TrainerDetailSheet.jsx:144 |
| Bio section label | БИОГРАФИЯ | БИОГРАФИЯ | TrainerDetailSheet.jsx:192 |
| Primary CTA | Записаться | Записаться | TrainerDetailSheet.jsx:230 |
| Empty bio hint | Информация скоро появится. | Информация скоро появится. | TrainerDetailSheet.jsx:200 |
| Error body | Не удалось загрузить профиль тренера. Потяните вниз, чтобы повторить. | Exact match | TrainerDetailSheet.jsx:107 |
| Loading aria-label | Загрузка профиля тренера… | Загрузка профиля тренера… | TrainerDetailSheet.jsx:73 |
| Avatar img alt | {trainer.name} (dynamic) | alt={data.fullName} (dynamic) | TrainerDetailSheet.jsx:168 |

No generic labels ("Submit", "OK", "Cancel", "Save") present. No vague error copy. The null-bio placeholder is a complete sentence with a period, meeting the spec tone.

---

### Pillar 2: Visuals (3/4)

**PASS — Clear focal point and hierarchy.** The 80×80 avatar is the dominant focal point, followed by `.t-h2` name and `.t-body` specialization. The `.card` bio section creates a distinct visual surface. Error state uses an icon-in-circle pattern consistent with GymInfoSheet and NotificationsSheet.

**WARNING — SectionLabel inline styles partially redundant and partially override the class.**
- `textTransform: 'uppercase'` (TrainerDetailSheet.jsx:63) duplicates what `.t-mini` already sets in `styles.css:254`. Harmless, but clutters the diff.
- `fontWeight: 700` (TrainerDetailSheet.jsx:61) overrides `.t-mini`'s `font-weight: 600`. The visual result (bold vs semi-bold) may be imperceptible but is an undocumented design decision embedded in inline style. See Pillar 4 for full analysis.

**PASS — Skeleton layout.** The skeleton maintains the same structural padding/margins as the loaded state (hero padding `24px 16px 16px`, card padding `12px 16px`, margin `0 16px`), preventing layout shift on data reveal — spec requirement met.

**PASS — Loading aria-label.** `TrainerDetailSkeleton` is wrapped in `<div aria-label="Загрузка профиля тренера…">` at line 73, satisfying the accessibility contract.

**PASS — No icon-only interactive controls.** The sole interactive element in the sheet body is the labelled "Записаться" button. The close button is inside `SubSheetHeader` (shared component, outside this audit scope).

---

### Pillar 3: Color (4/4)

**PASS — Zero hardcoded colors.** Grep for `#[0-9a-fA-F]{3,8}` and `rgb(` in TrainerDetailSheet.jsx returns no matches.

**PASS — Full CSS custom property compliance.** All color references use design system tokens:
- `var(--bg)` — sheet/CTA bar background (dominant 60%)
- `var(--surface)` / `var(--surface-2)` — card, error icon circle (secondary 30%)
- `var(--text)`, `var(--text-2)`, `var(--text-3)` — text hierarchy
- `var(--accent)` via `.btn-accent` — sole accent usage on CTA button (10%)

**PASS — Accent usage disciplined.** `.btn-accent` appears once (TrainerDetailSheet.jsx:225), strictly on the primary CTA. The spec reserves accent only for the CTA and focus rings (global CSS). Contract met.

**PASS — 60/30/10 distribution respected.** Background (`var(--bg)`) dominates the full-screen sheet. Cards (`.card` using `var(--surface)`) occupy the secondary layer. Accent appears on one button only.

Avatar `bg`/`color` values are per-trainer decorative values from seeded data, not semantic token overrides — correctly treated as data, not hardcoded design tokens.

---

### Pillar 4: Typography (3/4)

**PASS — Only spec-declared .t-* classes used.** All five classes match the spec's "Class Usage by Element" table:

| Element | Spec class | Actual | File:Line |
|---------|------------|--------|-----------|
| Hero name | `.t-h2` | `t-h2` | TrainerDetailSheet.jsx:180 |
| Hero specialization | `.t-body` | `t-body` | TrainerDetailSheet.jsx:185 |
| Bio body | `.t-body` | `t-body` | TrainerDetailSheet.jsx:195 |
| Empty bio hint | `.t-small` | `t-small` | TrainerDetailSheet.jsx:199 |
| Error body | `.t-small` | `t-small` | TrainerDetailSheet.jsx:106 |
| Section eyebrow | `.t-mini` | `t-mini` | TrainerDetailSheet.jsx:58 |

**WARNING — `SectionLabel` applies `fontWeight: 700` inline, overriding `.t-mini`'s `font-weight: 600`.**
- `styles.css:254`: `.t-mini { font-size: 11px; font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase; color: var(--text-3); }`
- TrainerDetailSheet.jsx:61: `fontWeight: 700`
- This overrides the type system's declared weight for `.t-mini` without a spec-documented justification. The spec (88-UI-SPEC.md Typography section) states "This phase introduces 0 new font sizes and 0 new font weights" and lists the section eyebrow as `.t-mini` without noting a weight override.
- Mitigating context: `GymInfoSheet.jsx:103` does the exact same override (`fontWeight: 700`), so this is a codebase-wide inherited inconsistency, not a new deviation introduced by Phase 88. However, the inconsistency is real and exists in both sheets.

`letterSpacing: 0.5` (unitless, TrainerDetailSheet.jsx:62) — React inline style numeric values for `letterSpacing` are treated as pixels by browsers: `0.5` = `0.5px`. This matches `.t-mini`'s `letter-spacing: 0.5px`. Not a deviation.

`textTransform: 'uppercase'` (TrainerDetailSheet.jsx:63) — duplicates `.t-mini`'s `text-transform: uppercase`. Redundant but harmless.

---

### Pillar 5: Spacing (3/4)

**PASS — All spacing values are multiples of 4.** Values found in the implementation: 4, 8, 12, 16, 18, 24, 32, 40, 56, 80, 100, 140. The non-4-multiple values (18, 100, 140) are skeleton line dimensions (height/width), not spacing tokens — acceptable.

**PASS — All spec-declared spacing properties match.**

| Section | Spec value | Implementation | File:Line |
|---------|------------|----------------|-----------|
| Hero padding | `24px 16px 16px` | `'24px 16px 16px'` | TrainerDetailSheet.jsx:159 |
| Hero gap | `8px` | `gap: 8` | TrainerDetailSheet.jsx:160 |
| SectionLabel padding | `16px 16px 8px` | `'16px 16px 8px'` | TrainerDetailSheet.jsx:59 |
| Bio card padding | `12px 16px` | `'12px 16px'` | TrainerDetailSheet.jsx:193 |
| Bio card margin | `0 16px` | `'0 16px'` | TrainerDetailSheet.jsx:193 |
| Bottom safe-area | `32px` | `height: 32` | TrainerDetailSheet.jsx:206 |
| CTA bar padding | `8px 16px 32px` | `'8px 16px 32px'` | TrainerDetailSheet.jsx:221 |
| Gradient fade height | `24px` | `height: 24` | TrainerDetailSheet.jsx:216 |
| Error padding | `40px 24px` | `'40px 24px'` | TrainerDetailSheet.jsx:98 |
| Error icon circle | `56×56` | `width:56, height:56` | TrainerDetailSheet.jsx:100 |

**WARNING — Skeleton name line margin deviates from spec.**
- Spec (88-UI-SPEC.md Loading section): `margin: 8px auto` (two-value shorthand: 8px top/bottom, auto left/right)
- Implementation (TrainerDetailSheet.jsx:80): `margin: '8px auto 0'` (three-value: 8px top, auto left/right, 0 bottom)
- In a flex column with `gap: 8`, the explicit bottom `0` is visually equivalent to the spec's `auto` bottom (flex gap handles spacing), but the explicit `0` diverges from spec shorthand and could produce unexpected results if the flex container's `gap` is removed or changed.

**PASS — Hero visual diagram gap ambiguity resolved.** The spec's visual diagram (88-UI-SPEC.md line 137) shows `[gap 12px]` between avatar and name, but the container property (line 131) explicitly states `gap: 8px`. The CSS container property is the authoritative specification for implementation. The implementation's `gap: 8` matches the container spec. The `12px` in the visual diagram is illustrative.

**PASS — No arbitrary Tailwind values** (grep for `[.*px]` and `[.*rem]` returns zero matches — this is a CSS-first PWA, no Tailwind).

---

### Pillar 6: Experience Design (3/4)

**PASS — Loading state.** `TrainerDetailSkeleton` renders when `query.isLoading` is true (TrainerDetailSheet.jsx:149). Skeleton structure mirrors the loaded layout exactly (hero + bio card padding/margins identical). CTA bar is always visible per spec.

**PASS — Error state.** `TrainerDetailError` renders when `query.isError` is true (TrainerDetailSheet.jsx:152). Error copy matches spec exactly. Error state is inline (sheet stays open), consistent with spec.

**PASS — Empty bio state.** `data.bio` falsy branch renders "Информация скоро появится." at TrainerDetailSheet.jsx:199–201. Spec requires this. Implemented.

**PASS — CTA disabled state.** `disabled={!onBook}` at TrainerDetailSheet.jsx:228. When `onBook` is not provided, the button renders as disabled. Spec says `disabled` attribute + `opacity: 0.4` via global `.btn:disabled` CSS — contract met.

**PASS — Pull-to-refresh.** `<PullToRefresh onRefresh={handleRefresh}>` wraps the scroller content. `handleRefresh` calls `query.refetch()` and resets `photoError` state. `PullToRefresh` component manages its own `refreshing` state and spinner display independently of React Query state.

**PASS — XSS defence (T-88-03).** `isSafePhotoUrl()` validates scheme before use; `photoError` state catches `img onError`. Both layers present. The `setPhotoError(false)` reset in `handleRefresh` correctly clears stale error state on pull-to-refresh.

**WARNING — Re-fetch does not show skeleton when refetching after first successful load.**
After data loads once, `query.isLoading` becomes permanently `false`. On subsequent pull-to-refresh calls, only `query.isFetching` is true. The sheet will show stale data (correct) but not a skeleton indicator. This is consistent with the GymInfoSheet pattern (which also only checks `isLoading`) and the `PullToRefresh` component shows its own spinner. This is an accepted codebase pattern, but it means the stale-data display during a slow re-fetch could confuse users if the data changes.

**WARNING — Re-fetch from error state shows error UI during the refetch.**
When the user is in error state and pulls to refresh: `query.isLoading` is `false` (no prior data), `query.isError` is `true` (previous failure), and `query.isFetching` is `true` (network request in flight). The current logic renders `<TrainerDetailError />` during the refetch because `isError` is still `true`. The `PullToRefresh` spinner is visible at the top, but the error copy and icon remain in the scroller — creating a visual double-signal. Fix: add `{query.isLoading && !query.isFetching && ...}` guard or check `!query.isFetching` before rendering the error state.

**WARNING — No ErrorBoundary anywhere in the PWA.** `grep -r ErrorBoundary apps/client-pwa/src` returns zero results. No `componentDidCatch` exists. If the `TrainerDetailSheet` component throws a render-phase JS error (e.g., unexpected API response shape), the entire PWA will crash to a blank screen. This is a codebase-wide gap, not introduced by Phase 88, but it means this new sheet has no isolation net. Mitigating context: the sheet wraps API data in a `data &&` guard, and the hook returns typed data, limiting crash surface.

---

## Files Audited

- `apps/client-pwa/src/screens/sheets/TrainerDetailSheet.jsx` — primary audit target
- `apps/client-pwa/src/components/Avatar.jsx` — reviewed for API compatibility
- `apps/client-pwa/src/screens/sheets/GymInfoSheet.jsx` — analog comparison (SectionLabel pattern)
- `apps/client-pwa/src/screens/sheets/NotificationsSheet.jsx` — analog comparison (isFetching pattern)
- `apps/client-pwa/src/components/PullToRefresh.jsx` — reviewed for independent loading state
- `apps/client-pwa/src/styles.css` — `.t-mini` definition verified
- `apps/client-pwa/src/App.jsx` — reviewed for ErrorBoundary/Suspense wiring
- `.planning/phases/88-trainer-detail-bio/88-UI-SPEC.md` — design contract baseline
- `.planning/phases/88-trainer-detail-bio/88-03-SUMMARY.md` — implementation record
- `.planning/phases/88-trainer-detail-bio/88-03-PLAN.md` — task definitions

Registry audit: shadcn not initialized (`components.json` absent in both `apps/client-pwa/` and repo root). Registry audit skipped per protocol.
