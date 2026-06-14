---
phase: 101
slug: clients-memberships
status: advisory
score: 20/24
audited: 2026-06-13
baseline: 101-UI-SPEC.md
screenshots: not captured (no dev server, code-only audit)
---

# Phase 101 — UI Review

**Audited:** 2026-06-13
**Baseline:** `.planning/phases/101-clients-memberships/101-UI-SPEC.md`
**Screenshots:** not captured (code-only audit — dev server not running)
**Scope:** net-new and changed surfaces only per audit brief (RefundScreen, ClientsToolbar, data-states on tabs, permission states, client modals, HistoryScreen placeholder)

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 3/4 | Four copy deviations from spec; none block task completion |
| 2. Visuals | 4/4 | All visual contracts met; correct icons, hierarchy, skeleton anatomy |
| 3. Color | 3/4 | FreezeScreen Callout uses `tone="accent"` (wrong); UnfreezeScreen uses hardcoded `bg-indigo-500` raw palette |
| 4. Typography | 4/4 | No new type roles introduced; all sizes match locked P100 scale |
| 5. Spacing | 4/4 | No arbitrary spacing values detected in changed surfaces |
| 6. Experience Design | 4/4 | All states covered — loading/error/empty per tab, per-tab isolation, submit pending, 403 gating |

**Overall: 20/24**

---

## Top 3 Priority Fixes

1. **FreezeScreen Callout uses wrong tone** — `tone="accent"` renders emerald background; spec requires `tone="warn"` (amber) for the informational freeze callout. Users expecting warning-amber get green instead, weakening the cautionary signal. Fix: change `<Callout tone="accent"` to `<Callout tone="warn"` at `SubscriptionModal.tsx:343`.

2. **UnfreezeScreen hardcodes raw Tailwind palette classes** — `bg-indigo-500/15`, `bg-indigo-500/20`, `text-indigo-600`, `text-indigo-300` at lines 415–424 bypass the project's semantic token system. ESLint raw-palette rule covers these. Spec requires `bg-info-soft text-info` (indigo) semantic tokens. Fix: replace hardcoded classes with `bg-info-soft`, `text-info`, `bg-info-soft/50` — or define `--info` / `--info-soft` tokens that map to indigo values.

3. **Telegram filter exposes unsupported `"Нет Telegram"` option** — `ClientsToolbar.tsx:33` defines `{ value: 'no', label: 'Нет Telegram' }` and `ClientsPage.tsx:54` maps `telegram === 'no'` → `hasTelegram: false`. The UI-SPEC table (§4.3) lists only two options: `all` and `true`; backend parameter is `hasTelegram=true` only. Sending `hasTelegram=false` is a backend contract violation — if the API ignores the param the filter silently fails; if it errors the list breaks. Fix: remove the `'no'` option from `TELEGRAM_OPTIONS` and drop the `telegram === 'no'` branch in filter construction.

---

## Detailed Findings

### Pillar 1: Copywriting (3/4)

Contract compliance is high. All major state copy, toast titles/descriptions, and validation messages match the spec. Four specific deviations found:

**WARNING — Cancel dialog ghost button copy mismatch**
- Spec (`Copywriting Contract > Primary CTAs per Dialog`): ghost button = `«Отмена»`
- Implementation (`SubscriptionModal.tsx:489`): `«Не отменять»`
- `«Не отменять»` is arguably better UX (mirrors "Отменить абонемент" positive framing), but it deviates from the design contract. Accept or update spec.

**WARNING — PaymentsTab empty state body copy typo**
- Spec: `«История платежей клиента появятся здесь.»` (deliberately uses plural verb — matches other tab patterns)
- Implementation (`PaymentsTab.tsx:98`): `«История платежей клиента появится здесь.»` (singular verb)
- Both are grammatically defensible in Russian but spec says `появятся`. Minor inconsistency with the other tabs.

**WARNING — Telegram filter has undocumented option**
- Spec (§4.3) defines 2 Telegram options only: `all` and `true`.
- Implementation (`ClientsToolbar.tsx:30–34`): 3 options including `'no'` / `«Нет Telegram»`.
- See Priority Fix #3 above for full reasoning.

**ADVISORY — RefundScreen icon is `ReceiptText`, spec requires `ReceiptX`**
- Spec (§3.2): `icon=ReceiptX (Lucide)` for the refund `IconChip`.
- Implementation (`SubscriptionModal.tsx:37, 564`): `ReceiptText` is imported and used.
- Both are similar Lucide icons; `ReceiptX` more directly communicates "cancelled receipt". Cosmetic only.

### Pillar 2: Visuals (4/4)

All visual contracts verified:

- RefundScreen: irreversibility warn Callout present, StatRow rows in correct order (Оплачено → Дата покупки), no amount field, danger `IconChip`, correct footer layout.
- ClientsPage: two distinct empty states with correct Lucide icons (`Users` for zero-state, `Search` for filter-empty). Status filter tabs removed. `ClientFilterTabs` not present.
- ActivityTab, PaymentsTab, TrainingsTab: per-tab skeletons (3 × `h-10 Skeleton` stacks), inline `PageError`, inline `EmptyState` without icon tile — all match spec.
- PlansPage: `Lock` icon `EmptyState` renders for 403 query response; Add/Edit/Delete buttons hidden (not disabled) for reception.
- HistoryScreen: clean text-center placeholder `«История появится позже — эта функция будет доступна в следующей версии.»` — honest, no fake events.

### Pillar 3: Color (3/4)

**BLOCKER-grade deviation but accepted as WARNING given no user-visible crash:**

**FreezeScreen Callout tone (`SubscriptionModal.tsx:343`)**
- Spec (§Color): freeze-state informational callouts should use `tone="warn"` (amber `--warning-soft`).
- Implementation: `<Callout tone="accent"` — renders emerald/primary background.
- `tone="accent"` is a raw accent usage on an informational non-action element, which violates the "never use accent for" list in the color contract (§Color).

**UnfreezeScreen freeze-info panel (`SubscriptionModal.tsx:415–424`)**
- Spec (§Color): `bg-info-soft text-info` (indigo) semantic tokens.
- Implementation: `bg-indigo-500/15`, `bg-indigo-500/20`, `text-indigo-600 dark:text-indigo-300`, `text-indigo-600/80 dark:text-indigo-300/80` — raw Tailwind palette classes banned by project ESLint rules.
- These would likely trigger the `raw-palette` ESLint rule if `indigo` is covered.

All other wired surfaces use correct semantic tokens (`bg-warning-soft`, `text-danger`, `bg-danger-soft`, `text-primary`, `bg-primary-soft`).

### Pillar 4: Typography (4/4)

No new type roles introduced. All observed sizes in changed surfaces (`text-[11.5px]`, `text-[12px]`, `text-[13px]`, `text-[13.5px]`) match the locked P100 scale. Character counter (`text-[11.5px] tabular-nums text-fg-subtle`) and inline validation error (`text-[12px] text-danger`) match spec exactly. No deviations found.

### Pillar 5: Spacing (4/4)

All spacing in changed surfaces uses scale-aligned values (`mt-3.5`, `px-3.5`, `py-3`, `gap-3`, `px-4`, `py-4`, `sm:px-5`). The RefundScreen textarea is `min-h-[80px]` as specified. No arbitrary `[Npx]` or `[Nrem]` spacing outside the established exception pattern (`px-5 py-[18px]` AdaptiveModal body, pre-existing). No regressions detected.

### Pillar 6: Experience Design (4/4)

All state coverage verified:

- **Loading:** `<PageLoading />` on ClientsPage; per-tab `Skeleton` stacks on ActivityTab, PaymentsTab, TrainingsTab — not full-page PageLoading on tab switch.
- **Error:** `<PageError onRetry={refetch} />` on ClientsPage; inline per-tab `PageError` within `<Card>` wrapper — correct isolation, no bubbling.
- **Empty:** Two distinct empty states on ClientsPage; per-tab `EmptyState` without icon tile on all three tabs; Plans 403 → `Lock EmptyState`; Plans zero-tariffs → inline `EmptyState`.
- **Submit pending:** All SubscriptionModal screens: primary + ghost buttons disabled, spinner shown, `onOpenChange` suppressed during mutation.
- **Error inline:** `ErrorCallout` renders `Callout tone="danger"` below fields; dialog stays open; ApiError message forwarded, generic fallback for network errors.
- **403 gating:** Cancel screen hidden for reception via `can()` check; client delete button gated; Plans Add/Edit/Delete hidden (not disabled); mutation 403 → `toast.error('Недостаточно прав', …)`.
- **HistoryScreen:** Honest placeholder, no fake event list — regression from review resolved.

The tag filter derives options from current-page items (`ClientsPage.tsx:64–73`) — this means tags from other pages are invisible. Acceptable for Phase 101 (no tags endpoint in scope), but worth noting for a future phase when a `GET /tags` endpoint lands.

---

## Registry Safety

No third-party shadcn registry blocks introduced in Phase 101. Audit not applicable.

---

## Files Audited

- `apps/admin-app/src/components/modals/SubscriptionModal.tsx`
- `apps/admin-app/src/pages/clients/ClientsPage.tsx`
- `apps/admin-app/src/pages/clients/components/ClientsToolbar.tsx`
- `apps/admin-app/src/pages/client/components/ActivityTab.tsx`
- `apps/admin-app/src/pages/client/components/PaymentsTab.tsx`
- `apps/admin-app/src/pages/client/components/TrainingsTab.tsx`
- `apps/admin-app/src/pages/plans/PlansPage.tsx` (partial — permission gating and 403 state sections)
- `apps/admin-app/src/features/memberships/api.ts` (toast copy verification)
- `apps/admin-app/src/components/modals/NewClientModal.tsx` (partial — submit state and toast wiring)
- `.planning/phases/101-clients-memberships/101-UI-SPEC.md`
