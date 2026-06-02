---
phase: 76
slug: pwa-wiring-cleanup
reviewed: 2026-06-02
baseline: 76-UI-SPEC.md (approved design contract)
screenshots: not captured (no dev server running — code-only audit)
---

# Phase 76 — UI Review

**Audited:** 2026-06-02
**Baseline:** 76-UI-SPEC.md (approved design contract)
**Screenshots:** Not captured — no dev server at localhost:5173 or localhost:3000. Code-only audit.

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 3/4 | All spec-mandated strings present; UI-SPEC field table still says "free text" for Goal but implementation ships pill selector (justified by T-76-05, spec not updated) |
| 2. Visuals | 4/4 | Avatar strip: 34px / 2.5px / -11px dimensions exact; skeleton circles correct; overflow chip correct; plan chip uses `.chip` class; all hierarchy maintained |
| 3. Color | 4/4 | Avatar palette (accent / color-mix / accent-deep / on-accent) matches spec exactly; overflow chip uses surface-2 / text-2; error toast uses danger / danger-soft; no accent overuse |
| 4. Typography | 3/4 | Avatar initials 12px/700 correct; save button 13px/600 correct; chip uses .chip (13px/500); toast body uses 13.5px/650 — off-scale from declared 13px touch point |
| 5. Spacing | 3/4 | All avatar dimensions exact; plan chip marginTop: 10px is off declared scale (scale: 4/8/16/24); toast padding 11px 13px deviates from scale but mirrors co-toast CSS pattern |
| 6. Experience Design | 3/4 | Loading/error/empty states all handled; cache invalidation correct; toast placed inside .scroller instead of after it (structural deviation from CheckoutSheet reference pattern) |

**Overall: 20/24**

---

## Top 3 Priority Fixes

1. **Goal field spec mismatch — UI-SPEC.md not updated to reflect pill selector** — Developers reading the spec will implement a free-text input instead of the enum pill control. Fix: update UI-SPEC.md §Field contract table row for Goal to say "4-pill segmented control over `{lose_weight, gain_mass, tone, maintain}`" and remove "free text `<input>`".

2. **Error toast DOM placement inside `.scroller`** — The toast `<div>` at ProfileExtraSheets.jsx line 260 is a child of `.scroller` (overflow-y: auto). CheckoutSheet places its toast after the scroller closing tag. While the `position: absolute` escapes overflow clipping in this case (the containing block is the outer `position: absolute` sheet div), any future addition of `position: relative` to `.scroller` would trap the toast and cause it to be clipped during its slide-in animation. Fix: move the toast div to after the `.scroller` closing tag, matching the CheckoutSheet reference pattern (CheckoutSheet.jsx line 632).

3. **Plan chip marginTop: 10 is off the declared spacing scale** — HomeScreen.jsx line 556 uses `marginTop: 10`. The UI-SPEC spacing scale declares: 4, 8, 16, 24, 32, 48, 64px as the only standard steps. 10px is between `sm` and `md` and has no documented exception (unlike 11px avatar overlap which is listed). Fix: change to `marginTop: 8` (sm) for a tighter grouping against the tariff selector, or `marginTop: 12` if visual breathing room is needed (though 12 is also off-scale; prefer 8 or 16).

---

## Detailed Findings

### Pillar 1: Copywriting (3/4)

**Passes:**
- Plan chip plural: `pluralPlan()` helper correctly implements the Russian plural rule (тариф / тарифа / тарифов) matching UI-SPEC §Copywriting exactly. HomeScreen.jsx lines 23-30.
- Chip label format: `"{N} {pluralPlan(N)} · от {formatMoney(...)}/мес"` matches spec. Line 558.
- Save button cycle: "Сохранить" / "Сохранение…" / "Сохранено" all present. ProfileExtraSheets.jsx line 145.
- Error toast copy: `"Не удалось сохранить данные. Попробуйте ещё раз."` matches spec exactly. Line 127.
- Local-only label: `"Только на устройстве"` matches §Copywriting (spec table says this, not `[местные данные]` which was the table description column). Line 194.
- CONVERSATIONS import: fully absent from App.jsx (grep confirms 0 occurrences). unreadChat={0} present at line 453.
- Trainer tile subtitle: `"кто работает в зале"` unchanged. Line 1044.

**Finding (WARNING):**
- UI-SPEC.md §Field contract table (line 269) still reads `"Yes — free text \<input\>"` for Goal. The implementation correctly ships a 4-pill segmented control per T-76-05 threat mitigation. The spec was not updated after the corrective deviation. Anyone referencing the spec for future work will get the wrong field type. This is a documentation gap, not a runtime defect.
- The UI-SPEC §Copywriting (line 345) says `"Sonner toast"` for the error toast. The PWA has no Sonner dependency — the implementation uses an inline custom toast that is functionally correct and visually superior to the generic co-toast (which uses accent color, wrong for errors). The spec inaccurately named the mechanism; the intent (error toast with danger styling) is fully met.

---

### Pillar 2: Visuals (4/4)

**Avatar strip (NHOME-01):**
- All three dimensions exact: 34×34px, 2.5px solid var(--surface) border, -11px marginLeft overlap. HomeScreen.jsx lines 998-1001, 1011-1013.
- Skeleton: 3 grey circles with identical dimensions, var(--surface-2) background, no pulse. Lines 996-1003. Matches spec D-76-04.
- Live vs fallback logic: `(liveTrainers && liveTrainers.length > 0) ? liveTrainers : STATIC_TRAINERS_FALLBACK` — never crashes. Lines 1005-1006.
- Overflow chip: 34×34px, -11px marginLeft, var(--surface-2) background, var(--text-2) color, `+{count - 3}`. Lines 1027-1034. Exact spec match.
- Avatar stack `aria-hidden="true"` correctly hides decorative initials from screen readers. Line 994.

**Plan chip (NHOME-02):**
- Uses `.chip` CSS class — spec mandates this class. Line 557. The class delivers: height 28px, padding 0 12px, border-radius pill, var(--surface-2) bg, var(--text-2) color, 13px/500, border 0.5px var(--border). All correct from styles.css lines 202-216.
- Chip only renders when `plans && plans.length > 0 && monthly.length > 0`. Guards against NaN/Infinity. Lines 553-561. D-76-09 compliant.
- Chip centered via `justifyContent: 'center'` wrapper. Line 556.

**PersonalDataSheet:**
- Save button color cycle: var(--text) idle → var(--text-3) saving → var(--accent-deep) confirmed. Line 141. Matches spec D-76-13 table exactly.
- Goal pill selector: 4 pills with accent-soft background / accent-deep color / accent border on selected. Lines 224-243. Visually coherent with design system.
- Error toast slide animation: translateY(180%) → translateY(0) with cubic-bezier(0.32, 0.72, 0.2, 1). Line 278-280. Matches co-toast transition pattern.

**Chat tab (CLEAN-01):**
- unreadChat={0} passed; TabBar renders no badge dot (badge: 0 is falsy per UI-SPEC §4). App.jsx line 453. Correct.

---

### Pillar 3: Color (4/4)

The 60/30/10 split is maintained. Phase 76 touches are additive wiring, not color changes.

**Avatar palette (spec-mandated):**
- Index 0: `var(--accent)` background, `var(--on-accent)` text. Line 1015, 1017.
- Index 1: `color-mix(in oklab, var(--accent) 60%, #6ee7c4)` background, `var(--on-accent)` text. Line 1016, 1017.
- Index 2: `var(--accent-deep)` background, `#ffffff` text. Line 1016, 1017. All exact spec matches.
- Overflow chip: `var(--surface-2)` / `var(--text-2)`. Lines 1030-1031. Correct (NOT accent — spec explicitly lists this under "Accent NOT used for").

**Error toast:**
- `var(--danger-soft)` background, `var(--danger)` border, `var(--danger)` icon background. Lines 269-272, 285. Matches spec §Color destructive role.

**Save button confirmed state:**
- `var(--accent-deep)` color. Line 141. Listed in spec as accent-reserved item #4.

No hardcoded hex colors introduced in phase-touched surfaces (the `#6ee7c4` in color-mix is a spec-mandated value for the avatar palette, documented in UI-SPEC §Component Inventory table).

---

### Pillar 4: Typography (3/4)

**Passes:**
- Avatar initials: `fontSize: 12, fontWeight: 700` (inline). Lines 1019, 1032. Matches spec exactly.
- Save button: `fontSize: 13, fontWeight: 600`. Line 142. Matches spec D-76-13.
- Plan chip: `.chip` class provides 13px/500. styles.css line 213. Matches spec.
- Section headers use `.t-mini` (11px/600). Lines 179, 193, 214. Correct.
- Form labels use `.t-small` (13px/400). FormRow component line 305. Correct.
- "Только на устройстве" uses `.t-mini` with explicit `fontSize: 11` override. Line 193. Redundant but harmless (class already sets 11px).

**Finding (WARNING):**
- Toast body text: `fontSize: 13.5, fontWeight: 650`. ProfileExtraSheets.jsx line 293. The UI-SPEC §Typography declares 13px as the touch point for the phase. 13.5px is between declared scale values (13px `.t-small` and next size up). Weight 650 is also not in the declared weights (declared: 700, 600 for phase touch points). This mirrors the `co-toast-tx` CSS class values exactly (`font-size: 13.5px; font-weight: 650` — confirmed in styles.css line 2040), so it is consistent with the existing design system's toast pattern. The spec's declared weights are specifically for avatar initials and save button — not for toast body text. Minor deviation.

---

### Pillar 5: Spacing (3/4)

**Passes:**
- Avatar: 34×34px, 2.5px border, -11px marginLeft — all spec exceptions met exactly.
- Sheet horizontal padding: 16px (md scale). Line 178, 190, 213. Correct.
- Avatar section padding-bottom: 20px. Line 153. Close to lg=24px; minor.
- FormRow label column: 110px. Line 305. Spec mandates 110px — exact match.
- Tile minHeight: 132px. Line 985. Spec exception met.

**Finding (WARNING):**
- Plan chip wrapper: `marginTop: 10`. HomeScreen.jsx line 556. The declared spacing scale is 4/8/16/24/32/48/64px. No spec exception covers 10px for the chip gap. Nearest scale values are 8 (sm) or 16 (md). This is a cosmetic off-scale value without documentation.
- Toast padding: `padding: '11px 13px'`. Line 272. Both values are off-scale (scale: 8, 16). However, this is directly copied from the `.co-toast` CSS class (`padding: 11px 13px` — styles.css line 2006), so it follows established PWA convention even if off the abstract scale. Documented exception in the co-toast pattern.
- Avatar block bottom padding 20px (line 153) and section gap 12px (line 247) are both off-scale. These predate Phase 76 and are not new deviations.

No arbitrary `[Npx]` Tailwind values (project uses inline styles throughout the PWA — not Tailwind).

---

### Pillar 6: Experience Design (3/4)

**Passes:**
- Trainer strip loading state: 3 skeleton circles rendered while `trainersLoading`. HomeScreen.jsx lines 995-1003. No crash, no flash.
- Trainer strip error/empty: falls back to `STATIC_TRAINERS_FALLBACK`. Lines 1005-1006. Spec D-76-04 met.
- Plan chip loading/error: renders nothing (null), existing hardcoded layout stays. Lines 555-561. Spec D-76-09 met.
- PersonalDataSheet field hydration: `useEffect` keyed on `meData.id` populates fields once; subsequent refetches do not clobber unsaved edits (`hydratedForId` ref guard). Lines 73-84. Correct PDATA-01 implementation.
- Save button: disabled during mutation (`disabled={isSaving}`), cursor not-allowed, label "Сохранение…". Lines 139-145. Spec D-76-13 met.
- Success flash: `setSaved(true)` + `setTimeout(() => setSaved(false), 1400)`. Lines 124-125. 1400ms matches spec.
- Cache invalidation: `useUpdateClientProfile` calls `onSettled` with `invalidateQueries(clientPortalKeys.me())` + `invalidateQueries(clientPortalKeys.home())`. clientQueries.ts lines 225-228. PDATA-02 persist-across-reload criterion met.
- Accessibility: error toast has `aria-live="polite"` and `aria-atomic="true"`. ProfileExtraSheets.jsx lines 261-262. Avatar strip is `aria-hidden="true"` (decorative). Line 994.
- CONVERSATIONS mock removed; `unreadChat={0}` passed. CLEAN-01 complete.

**Finding (WARNING):**
- Error toast is a child of `.scroller` (overflow-y: auto, position: static). CheckoutSheet.jsx places its co-toast after the scroller's closing `</div>`, before the sheet container's closing `</div>`. The `position: absolute` on the toast uses the outer sheet's `position: absolute` as its containing block — so currently the toast renders correctly. However, the scroller's `overflow: auto` means any overflow of the toast within the scroller's painting context could be clipped in edge cases. The structural risk is low but real: if `.scroller` ever gains `position: relative` or `transform`, the toast's containing block changes and the bottom: 32 anchor breaks. Recommend moving the toast outside the scroller to match the reference pattern.

---

## Registry Safety

No shadcn `components.json` present in `apps/client-pwa`. No third-party registry blocks used. Registry audit: not applicable.

---

## Files Audited

- `apps/client-pwa/src/screens/HomeScreen.jsx` — lines 347-562 (HeroNewbie / plan chip), lines 853-1047 (HomeNewbie / trainer strip)
- `apps/client-pwa/src/screens/sheets/ProfileExtraSheets.jsx` — lines 1-300 (PersonalDataSheet, FormRow, Divider3)
- `apps/client-pwa/src/App.jsx` — lines 449-455 (TabBar unreadChat prop)
- `apps/client-pwa/src/styles.css` — lines 1-250 (tokens, chip class, co-toast class, type scale)
- `apps/client-pwa/src/lib/clientQueries.ts` — lines 208-230 (useUpdateClientProfile)
- `apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx` — lines 630-645 (co-toast reference pattern comparison)
- `.planning/phases/76-pwa-wiring-cleanup/76-UI-SPEC.md` — full document (audit baseline)
- `.planning/phases/76-pwa-wiring-cleanup/76-01-SUMMARY.md`, `76-02-SUMMARY.md`, `76-03-SUMMARY.md`
- `.planning/phases/76-pwa-wiring-cleanup/76-CONTEXT.md`
