# Phase 108 — UI Review

**Audited:** 2026-06-14
**Baseline:** 108-UI-SPEC.md (approved design contract)
**Screenshots:** Not captured (code-only audit — no dev server detected)

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 2/4 | Navigate-away dialog title, always-on hint, sender-signature helper all deviate from spec; global toast fires instead of per-section flow |
| 2. Visuals | 2/4 | Gym card fields `capacity` and `description` never populate from server data; skeleton row count for NotificationsSection is 4 not 7 |
| 3. Color | 4/4 | All semantic tokens used correctly; no raw palette values; accent distribution matches contract |
| 4. Typography | 4/4 | All sizes and weights match locked spec; no deviation from controls.tsx constants |
| 5. Spacing | 3/4 | Consistent with locked design system; one minor arbitrary `pl-12` in BookingSection no-show field |
| 6. Experience Design | 2/4 | `gymDataToFormState` maps `name` to both `nameShort` and `name`; `capacity` and `description` never hydrated from server; success guard dialog has a third button not in spec |

**Overall: 17/24**

---

## Top 3 Priority Fixes

1. **`gymDataToFormState` does not hydrate `capacity` or `description` from server data** — Users see stale default values (capacity=60, description="") regardless of what the backend returns; Cancel reverts to the wrong values. Fix: map `data.capacity` (if present on the response) and `data.description`/`data.tagline` into the form state, and add these fields to `GymInfoSchema` if the backend exposes them.

2. **`nameShort` mapped to `data.name` instead of a distinct short-name field** — `gymDataToFormState` sets both `nameShort: data.name ?? ''` and `name: data.name ?? ''` (lines 438–439). The "Короткое название" input will always be pre-filled with the long name. If the backend provides a separate short-name field, it must be added to `GymInfoSchema` and mapped correctly. If there is no such field, the UI should be collapsed to a single name field.

3. **Navigate-away guard copy and button structure deviate from UI-SPEC** — The rendered dialog title is "Есть несохранённые изменения" (spec: "Выйти без сохранения?"); the dialog has three buttons (Сохранить и уйти / Уйти без сохранения / Остаться) but the spec defines two (Выйти / Остаться, neutral tone); the spec explicitly says the guard should offer to abandon changes, not to save-and-continue. The extra "Сохранить и уйти" flow is an undocumented addition. Fix: align title and button labels to spec, or get explicit sign-off on the three-button variant.

---

## Detailed Findings

### Pillar 1: Copywriting (2/4)

**BLOCKER-level deviations from the Copywriting Contract table (UI-SPEC.md line 356-381):**

| Element | Spec copy | Actual copy | Location |
|---------|-----------|-------------|----------|
| Navigate-away guard title | "Выйти без сохранения?" | "Есть несохранённые изменения" | `SettingsPage.tsx:163` |
| Navigate-away guard body | "Есть несохранённые изменения. Если выйти — они будут потеряны." | "Если уйти без сохранения, все изменения будут потеряны." | `SettingsPage.tsx:166` |
| Navigate-away confirm | "Выйти" | "Уйти без сохранения" (button 2) | `SettingsPage.tsx:188` |
| Navigate-away cancel | "Остаться" | "Остаться" (correct), but a third "Сохранить и уйти" button exists with no spec coverage | `SettingsPage.tsx:179` |
| Always-on trigger hint | "Нельзя отключить — требуется по правилам платёжных систем." | "Нельзя отключить (всегда включено)" | `SectionsBottom.tsx:328` |
| Sender signature helper | "до 11 латинских символов · зарегистрирован в МТС, МегаФон, Билайн, Т2" | "до 11 латинских заглавных символов · зарегистрирован у операторов" | `SectionsBottom.tsx:388` |
| Quiet hours helper | "По московскому времени. В тихие часы срочные уведомления не подавляются." | "по часовому поясу Europe/Moscow" (partial, inline label only) | `SectionsBottom.tsx:417` |

**Additional observations:**
- `BranchSection` title is hard-coded as "Филиал «Тверская»" (`SectionsTop.tsx:553`) rather than derived from server data. The spec says the card shows the gym name from the backend. This will show the wrong name for any gym whose short name differs.
- Global success toast "Настройки сохранены" fires at `SettingsPage.tsx:88` when all sections succeed. The spec defines per-section success toasts and does NOT specify a global aggregate toast. The per-section toasts in `useUpdateGymInfo.onSuccess`, `useUpdateWorkingHours.onSuccess`, etc. already fire "Карточка зала обновлена", "График работы обновлён", etc. — so two toasts fire per section save: the per-section one (from the mutation hook) AND the aggregate one (from `handleSave`). This is noisy and inconsistent with the spec.

---

### Pillar 2: Visuals (2/4)

**WARNING — BranchSection data hydration gap:**
`gymDataToFormState` (`SectionsTop.tsx:436-449`) maps:
- `capacity` → hardcoded `60` (never read from server)
- `description` → hardcoded `''` (never read from server, despite `GymInfoSchema` lacking these fields entirely)

The `GymInfoSchema` (`schemas.ts:47-60`) does not include `capacity` or `description` fields. The backend `GymInfo` model (`gym/models.py`) likely has a `tagline` field that could serve as description. Neither capacity nor description can round-trip through the wiring as implemented. The form renders confidently with stale/default values and Cancel restores wrong values.

**WARNING — NotificationsSection skeleton rows:**
The loading skeleton renders 4 rows (`SectionsBottom.tsx:271-276`). The UI-SPEC requires 7 skeleton rows (one per trigger, line 188). With 8 triggers in `DEFAULT_TRIGGERS`, this is especially undercounted.

**WARNING — Navigate-away guard button structure:**
The spec defines a 2-button dialog (abandon / stay). The implementation has 3 buttons: "Сохранить и уйти", "Уйти без сохранения", "Остаться". While the three-button version is arguably better UX, it contradicts the spec. The primary button ("Сохранить и уйти") uses `bg-primary` background which the spec says should be neutral tone for this dialog.

**INFO — InlineToggle vs Toggle from controls.tsx:**
`InlineToggle` and the inline matrix toggle buttons are hand-rolled duplicates of the `Toggle` component from `controls.tsx`. They produce visually identical output (same `bg-primary` track, same thumb animation) but bypass the shared component's `sectionId`-based `markDirty` integration. The sections call `markDirty` manually, so this works correctly, but the duplication adds maintenance surface.

---

### Pillar 3: Color (4/4)

No deviations found. All color usage:
- Semantic tokens throughout: `bg-primary`, `bg-surface`, `bg-surface-2`, `bg-surface-3`, `text-fg`, `text-fg-muted`, `text-fg-subtle`, `bg-danger-soft`, `text-danger`, `bg-warning-soft`, `text-warning-deep`, `bg-primary-soft`, `text-primary-deep`
- No raw hex values in component classes (the `#06120c` text on primary buttons and the `#2DD4A4` accent color display in `AppSection` are display/read-only values, not styling tokens)
- Lock card uses `Lock` icon with `EmptyState` (no `text-danger` icon, which is acceptable per spec — "if using danger variant")
- 60/30/10 distribution intact: page backgrounds use `bg-bg`; cards use `bg-surface`/`bg-surface-2`; accent (`bg-primary`) reserved for SaveBar save button and toggle on-state

---

### Pillar 4: Typography (4/4)

All text classes match the locked spec:
- Section headings: existing `SectionCard` h2 styles (not changed)
- Setting row labels: `text-[13px] font-semibold`
- Hints / sub-copy: `text-[11.5px]` / `text-[11px]`
- Input text: `text-[13.5px]`
- Matrix column headers: `text-[10.5px] font-semibold`
- Character counter: `text-[11px] text-fg-subtle`

Weights in use: 400 (`text-fg-subtle` contexts), 600 (`font-semibold`), 700 (`font-bold`). No weight outside the locked set.

---

### Pillar 5: Spacing (3/4)

**WARNING — one non-standard arbitrary value:**
`SectionsTop.tsx:1405`: `className="mt-2 pl-12"` for the no-show penalty `MoneyField` indent. `pl-12` = 48px. This is an arbitrary indent to align the money input below the toggle; the spec does not define this offset. It works visually but is outside the declared spacing scale multiples-of-4 pattern. Minor, but worth noting since `pl-12` is not a standard control alignment.

All other spacing tokens (`gap-2`, `gap-3`, `py-4`, `py-2.5`, `px-3`, `px-6`, `pt-2`, etc.) are consistent with the locked spacing scale and existing `controls.tsx` patterns.

---

### Pillar 6: Experience Design (2/4)

**BLOCKER — `gymDataToFormState` field mapping bug:**
```
// SectionsTop.tsx:438-439
nameShort: data.name ?? '',   // WRONG — should be a distinct nameShort field
name: data.name ?? '',        // WRONG — same source field for both inputs
```
Both "Короткое название" and "Полное название" inputs are pre-populated with the same value (`data.name`). On save, `GymInfoUpdateSchema` accepts `nameShort` and `name` as separate fields, so the backend receives duplicate values. No data-loss occurs, but the short-name field is unusable as a distinct editable entity.

**BLOCKER — `capacity` and `description` not hydrated:**
`gymDataToFormState` hard-codes `capacity: 60` and `description: ''`. These fields are displayed and edited in the UI but never loaded from server. Cancel does not restore correct server values. If the gym's capacity is 120 and description is "Открыт с 2018", after loading the UI shows 60 and empty. The `GymInfoSchema` must be extended with these fields and the backend must expose them.

**WARNING — Double toast on successful save:**
When the owner clicks "Сохранить" with, say, BranchSection dirty: `useUpdateGymInfo.onSuccess` fires `toast.success('Карточка зала обновлена')` AND `SettingsPage.handleSave` fires `toast.success('Настройки сохранены')`. Two toasts appear simultaneously.

**WARNING — `HoursSection` Lock gate uses `'settings'` resource, `BranchSection` uses `'gym'` resource:**
This is correct per spec (CFG-01 is `Resource.GYM`, CFG-02/03/04 are `Resource.SETTINGS`). Both gate queries with `enabled: can(role, ...)` satisfying the zero-calls-for-reception requirement. Confirmed correct.

**INFO — `handleSave` handlers registered via `useEffect` with dependency array `[form]` / `[schedule, breaks, closures]`:**
The `// eslint-disable-line react-hooks/exhaustive-deps` suppressions on `SectionsTop.tsx:547` and `863` are intentional (handlers always read latest state via closure refresh). The pattern is correct for this registration approach but fragile — if `registerSave` prop reference changes, old handlers stay registered. No bug today since props are stable, but noted.

**INFO — `NotificationsSection` always-on rows do not visually lock all 4 channels:**
The matrix toggles for `payment_succeeded` and `autopay_charge_failed` are correctly rendered `disabled` with `opacity-65` and `cursor-not-allowed`. The hint text below the trigger label says "Нельзя отключить (всегда включено)" — present and functional, though the copy deviates (see Pillar 1). The `title` tooltip on the toggle says "Нельзя отключить — системное уведомление" (closer to spec intent, just not the exact spec string).

**INFO — `BranchSection` `Стeppер` uses a hand-rolled `InlineStepper` instead of `controls.tsx:Stepper`:**
The shared `Stepper` component accepts a `sectionId` prop for dirty-marking. `InlineStepper` calls `patch()` which calls `markDirty` explicitly, so the dirty behavior is equivalent. Not a defect, but increases component count.

---

## Registry Safety

Registry audit: shadcn official only — no third-party registries declared. Gate not applicable.

---

## Files Audited

- `/apps/admin-app/src/pages/settings/SettingsPage.tsx`
- `/apps/admin-app/src/pages/settings/components/SectionsTop.tsx`
- `/apps/admin-app/src/pages/settings/components/SectionsBottom.tsx`
- `/apps/admin-app/src/features/settings/api.ts`
- `/apps/admin-app/src/features/settings/schemas.ts`
- `.planning/phases/108-editable-settings-backend-wiring/108-UI-SPEC.md`
- `.planning/phases/108-editable-settings-backend-wiring/108-CONTEXT.md`
