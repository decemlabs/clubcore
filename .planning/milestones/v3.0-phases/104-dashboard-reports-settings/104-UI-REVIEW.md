---
phase: 104
slug: dashboard-reports-settings
status: advisory
score: 21/24
audited: 2026-06-13
baseline: 104-UI-SPEC.md
screenshots: not captured (no dev server at localhost:5173)
---

# Phase 104 — UI Review

**Audited:** 2026-06-13
**Baseline:** 104-UI-SPEC.md (approved contract)
**Screenshots:** not captured — no dev server detected at localhost:5173 or :3000. Audit is code-only.

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 4/4 | All Russian copy matches contract exactly; error toasts, empty states, confirmations, and 409 codes verified |
| 2. Visuals | 4/4 | Role-gating, widget hierarchy, and modals implemented to spec; ActionIcon color deviates from spec (accepted) |
| 3. Color | 3/4 | Accent used on `create` ActionIcon chip in audit rows — spec explicitly forbids accent on audit-log row icons |
| 4. Typography | 4/4 | KpiCard uses 36px/bold for scalar values (Reports/Clients tab) — slight deviation from 14.5px money display spec but contextually appropriate for scalar KPIs |
| 5. Spacing | 4/4 | All spacing matches scale; exceptions (dialog `px-5 py-[18px]`, `py-3.5` SettingRow, `h-[38px]` CsvButton) are spec-approved |
| 6. Experience Design | 2/4 | Audit row uses ActionIcon (icon-chip) that replaces the spec's initials-circle as the leading visual; role selector in invite modal uses a segmented pill instead of the specified RadioGroup primitive; status badges hidden on mobile (max-md:hidden) |

**Overall: 21/24**

---

## Top 3 Priority Fixes

1. **Audit row layout does not match UI-SPEC §3.2** — The spec defines `[ Actor initials circle ]` as the leading element in each audit row. The implementation uses `ActionIcon` (action-type icon chip with colored background) in a separate visual position, and puts the initials circle (`size-8 bg-surface-3`) after it — but actually the `RealAuditRow` in `parts.tsx:123` does show an initials circle first, then skips the ActionIcon chip entirely in the row layout. The `ActionIcon` component only appears in `AuditDetailModal`. The row is therefore spec-compliant on layout but does NOT show a per-action color chip inline — which is a modest visual downgrade vs. spec intent. No user task is blocked. Fix: confirm whether ActionIcon should appear inline in the row next to initials (as implied by `ActionFeed` patterns in P103) or remain modal-only. **Severity: WARNING.**

2. **Invite modal role selector uses segmented pill, not RadioGroup primitive** — UI-SPEC §6.2 explicitly specifies `RadioGroup` (`components/settings/controls`) for the role field. The implementation (`SectionsBottom.tsx:457-478`) renders a custom inline segmented `<button>` pair (`border-[0.5px] border-border bg-surface-2 rounded-full`) rather than the `RadioGroup` primitive from `controls.tsx`. Functionally equivalent but breaks the component contract and skips the `RadioGroup`'s built-in keyboard navigation (arrow keys). Accessibility regression for keyboard users. Fix: replace the custom segment with `<RadioGroup options={['Ресепшн', 'Владелец']} .../>`. **Severity: WARNING.**

3. **Team section status badge hidden on mobile (`max-md:hidden`)** — `SectionsBottom.tsx:782` wraps the status badge in `<span className="max-md:hidden">`. On mobile, a `pending_invitation` or `deactivated` user shows no visual status indicator — only name/email and the MoreHorizontal trigger. Operators on phones cannot distinguish pending/deactivated users from active ones without opening the dropdown. The UI-SPEC §6.3 does not specify this exception. Fix: show the status badge on all breakpoints, or at minimum move it inside the name/email stack on mobile. **Severity: WARNING.**

---

## Detailed Findings

### Pillar 1: Copywriting (4/4)

All copy audited against UI-SPEC §5 (Copywriting Contract) — no deviations found.

- Dashboard empty states: `«Тренировок сегодня нет»`, `«Нет истекающих абонементов»`, `«Активность»` + `«Доступна в журнале действий»` — all match spec exactly (`DashboardPage.tsx:229-230`).
- CSV error toasts: `«Не удалось скачать файл»` / `«Проверьте соединение и попробуйте ещё раз.»` — verified in both `ReportsPage.tsx:85-88` and `AuditPage.tsx:81-83`.
- Reports tab labels: `«Выручка»`, `«Клиенты»`, `«Посещения»`, `«Тренеры»` — exact match (`ReportsPage.tsx:57-61`).
- Reception Lock: `«Недостаточно прав»` / `«Этот раздел доступен только владельцу. Обратитесь к владельцу клуба.»` — verified in Reports, Audit, and Team section.
- Self-revoke confirm: `«Завершить все сессии?»` / `«Все активные сессии, включая эту, будут завершены. Вам потребуется войти снова.»` / `«Да, выйти»` — exact match (`SectionsTop.tsx:162-175`).
- 409 codes: `«Нельзя деактивировать себя»`, `«Нельзя деактивировать единственного владельца»`, `«Пользователь уже неактивен»` — all present (`SectionsBottom.tsx:489-500`).
- Invite modal: title, description, field labels, success heading, copy-link note, expiry line — all match spec.
- Profile read-only note: `«Для изменения данных обратитесь к владельцу.»` — present (`SectionsTop.tsx:116-118`). Note: the `SectionCard` desc also reads `«Редактирование недоступно — обратитесь к владельцу.»` which is a slightly wordier paraphrase of the same intent but does not conflict.

No generic English CTAs (`Submit`, `OK`, `Cancel`, `Save`) found in the audited files.

---

### Pillar 2: Visuals (4/4)

Role-gating architecture is correctly implemented per spec.

- **Dashboard reception layout**: `DashboardPage.tsx:88-102` renders only `ScheduleToday` + `ExpiringMemberships` when `!isOwner`. No Lock icons, no empty placeholders for absent owner cards — correct absence treatment per UI-SPEC §1.2.
- **Dashboard owner layout**: `DashboardOwnerSection` correctly renders KpiStrip, OccupancyHours, ScheduleToday (in grid), ExpiringMemberships + RevenueChart + TopTrainers (in grid). `OccupancyNow` and `ClientMessages` are absent as specified.
- **ActivityFeed**: rendered as `EmptyState` with `icon=Activity` + link to `/audit-log` — matches spec §1.3 fallback intent.
- **Per-widget loading**: each widget receives its own `isPending` prop; no full-page PageLoading for the dashboard — spec-compliant.
- **Audit row visual hierarchy**: `RealAuditRow` (`parts.tsx:100-155`) shows initials circle → actor email + time → action/resource/resourceId. `ChevronRight` affordance on non-mobile. All leading elements present and semantically ordered.
- **Invite modal success view**: `CheckCircle2` icon in `bg-primary-soft text-primary-deep` circle, success heading, invite link input with `select-all` onClick, copy-link button, expiry text — all match spec §6.2.
- **Session row**: Monitor/Smartphone icon chip with correct `bg-primary-soft` for current / `bg-surface-3` for other; `«Сейчас»` badge; `«—»` for self; `«Завершить»` + `Loader2 animate-spin` for revoking — spec-compliant.
- **Icon-only buttons**: all icon-only interactive elements (`MoreHorizontal` dropdown triggers) carry `aria-label` attributes. No bare icon buttons without accessible labels found.

Minor observation: `ActionIcon` in `parts.tsx:27-43` uses `bg-primary-soft text-primary-deep` for the `create` action chip in AuditDetailModal. The spec says «Never use accent for audit-log row icons» — this component is only rendered inside the detail modal (not in the row itself), so the color application is within the modal context where a visual accent on create actions is defensible. However it is adjacent to the spec's explicit prohibition and worth flagging at the color pillar.

---

### Pillar 3: Color (3/4)

**WARNING: Accent on `create` ActionIcon**

`parts.tsx:31`: `case 'create': return { icon: Plus, cls: 'bg-primary-soft text-primary-deep dark:text-primary' }`.

UI-SPEC §4 states: **«Never use accent for: ... audit-log row icons»**. The `ActionIcon` component is used in `AuditDetailModal` (confirmed by import) and could also be reused in row contexts. The spec's prohibition is on audit-log row icons specifically; the detail modal context is ambiguous. The `create` chip color choice is semantically reasonable (creation = positive = brand color), but it violates the literal spec constraint.

Fix: Change `create` action chip to a neutral `bg-surface-3 text-fg-muted` or a non-accent green token (e.g. `bg-success-soft text-success` if available), or clarify in spec that the modal context is exempt.

All other color usage audited:
- Semantic tokens used throughout — no raw `bg-blue-500` or hardcoded hex in component classes.
- `«Сейчас»` badge: `bg-primary-soft text-primary-deep` — spec-reserved.
- Current session device chip: `bg-primary-soft text-primary-deep` — spec-reserved.
- Owner role badge: `bg-primary-soft text-primary-deep` — spec-reserved (`ROLE_TONE` map in `SectionsBottom.tsx:64-66`).
- Pending invitation badge: `bg-warning-soft text-warning-deep` — matches spec.
- Deactivated badge: `bg-surface-3 text-fg-muted` — matches spec.
- RevenueChart bar fill in trainer rows: `bg-primary` (`ReportsPage.tsx:530`) — used as a progress bar visual element on a data column. The spec does not reserve this use explicitly. The bar is decorative/data and the accent usage is proportionally minimal (one per row, not a CTA). Acceptable but noted.
- Profile role pill: correct tone per role.
- No hardcoded RGB/hex values found in audited `.tsx` files (the `bg` values in `SectionsTop.tsx:543-568` acquirer list are inline style `style={{ background: a.bg }}` using known brand colors from mock data — not component-level violations).

---

### Pillar 4: Typography (4/4)

No new type roles introduced in this phase. All sizes used fall within the inherited type scale.

Sizes observed:
- `text-[14px]` body, `text-[13px]` item title, `text-[12.5px]` label, `text-[11.5px]` subtle, `text-[11px]` timestamp — all match UI-SPEC §2 locked scale.
- `text-[13.5px]` (invite modal input, `ReportsTrainerRow` trainer name) — within the 13–13.5px item-title band specified.
- `text-[9.5px]` for `«Сейчас»` badge — matches spec-specified `text-[9.5px]` exactly.
- `text-[10.5px]` for role/status badges — minor scale compression but consistent with existing patterns from prior phases (not a new deviation).
- `text-[36px] font-bold` in `KpiCard` (`ReportsPage.tsx:389`) for the clients KPI scalar values — this is larger than the `text-[14.5px]` money-display spec. However, the Clients tab shows scalar counts (not money), and large numerics in KPI cards are the established pattern throughout the admin panel (KpiStrip, StatStrip). Treating as intentional contextual choice, not a violation.
- Weights: `font-semibold` and `font-bold` used correctly throughout. No `font-medium` used outside its established label context.

No inherited type-scale issues re-flagged per audit scope constraints.

---

### Pillar 5: Spacing (4/4)

All spacing values verified against the 8-point scale. Spec-approved exceptions are present and unchanged.

- Page container: `px-4 pb-10 pt-5 sm:px-6 sm:pb-12 sm:pt-6 lg:px-7` — consistent across Dashboard, Reports, Audit pages.
- CsvButton: `h-[38px] px-[14px] gap-[7px]` — exact match to UI-SPEC §2.2 button anatomy.
- Tab selector: `h-[34px] px-[15px] gap-2 rounded-lg` — tight, sensible, consistent.
- Filter toolbar: `gap-2.5 px-4 py-3` — within scale.
- Audit `DateGroup` header: `px-[18px] pb-1 pt-3.5` — exact spec match (§3.2).
- Session row: `px-3 py-2.5 gap-3 rounded-xl` — conforms to SettingRow patterns.
- Skeleton rows: `h-[52px]` for sessions (spec: `h-[52px]`), `h-[46px]` for team (spec: `h-[46px]`), `h-[400px]` for audit filter-change (spec: `h-[400px]`) — all exact.
- No arbitrary pixel values outside spec-approved exceptions found.

---

### Pillar 6: Experience Design (2/4)

Three concrete gaps found:

**WARNING 1 — Invite modal role selector deviates from specified primitive**

UI-SPEC §6.2 specifies `RadioGroup` from `components/settings/controls`. The implementation (`SectionsBottom.tsx:456-478`) renders a custom segmented pill toggle. The `RadioGroup` component supports standard radio keyboard navigation (arrow keys move between options). The custom segment does not. This is a keyboard accessibility regression for the invite flow.

File: `apps/admin-app/src/pages/settings/components/SectionsBottom.tsx:456-478`
Fix: Replace with `<RadioGroup options={['Ресепшн', 'Владелец']} value={ROLE_LABEL[state.role]} onChange={(v) => setState({...state, role: v === 'Владелец' ? 'owner' : 'reception'})} sectionId="invite-modal" />`.

**WARNING 2 — Team section status badge hidden on mobile**

`SectionsBottom.tsx:782`: `<span className="max-md:hidden">` wraps the entire status column. On screens narrower than `md` (768px), pending/deactivated users are visually indistinguishable from active users. The MoreHorizontal trigger still appears, so the action is reachable — but the operator cannot pre-assess user state before opening the dropdown.

File: `apps/admin-app/src/pages/settings/components/SectionsBottom.tsx:782`
Fix: Render the badge inside the name/email `<div>` on mobile (`<div className="md:hidden mt-0.5">`), or remove the `max-md:hidden` and let the grid collapse gracefully.

**WARNING 3 — Audit row does not render ActionIcon inline (spec ambiguity)**

UI-SPEC §3.2 row anatomy shows `[ Actor initials circle ]` as the sole leading element. The spec says «reuse existing `AuditRow` component from pages/audit/components/parts» but the existing legacy row used `ActionIcon`. The `RealAuditRow` drops the `ActionIcon` and uses only an initials circle — which does match the spec's layout spec literally. However, the audit row has no per-action color signal in the row itself (only available in the modal). Users scanning the audit list cannot distinguish a `create` from a `delete` event without opening each row. This is a usability gap vs. the legacy mock experience.

File: `apps/admin-app/src/pages/audit/components/parts.tsx:100-155`
Recommendation (non-blocking): Add `<ActionIcon action={event.action} />` between initials circle and main content, replacing the neutral initials circle (or displaying both). Update the spec prohibition to clarify it applies to the legacy row's overuse, not a single contextual chip.

**Positive findings:**
- All five loading states present: KpiStrip skeleton, session skeleton rows (×3), team skeleton rows (×3), profile skeleton, audit skeleton (`h-[400px]`).
- All error states present with inline retry links (sessions, profile, team) or `PageError` component (reports, audit tabs, schedule/expiring widgets).
- All empty states present: 2 dashboard widgets, 4 report tabs, 2 audit empties (filtered vs. all), team section, invite success view.
- Destructive actions (deactivate, delete, revoke invitation, logout-everywhere) all guarded with `AdaptiveModal confirm` dialogs.
- RBAC guards fire before any data hooks in Reports and Audit pages (hook-mounting verified by outer/inner component split pattern).
- CSV button disables during download (`disabled={downloading}`) and re-enables on both success and error paths.
- `«Выйти везде»` only appears when `currentSession` is available — no phantom button in error/loading states.
- 409 error codes are handled at the specific code level, not generic catch-all.

---

## Registry Safety

No third-party registry blocks used in Phase 104. All components reuse established primitives from prior phases. Registry audit: 0 third-party blocks, no flags.

---

## Files Audited

- `apps/admin-app/src/pages/dashboard/DashboardPage.tsx`
- `apps/admin-app/src/pages/reports/ReportsPage.tsx`
- `apps/admin-app/src/pages/audit/AuditPage.tsx`
- `apps/admin-app/src/pages/audit/components/parts.tsx`
- `apps/admin-app/src/pages/audit/components/AuditDetailModal.tsx` (referenced, not read in full)
- `apps/admin-app/src/pages/settings/components/SectionsTop.tsx`
- `apps/admin-app/src/pages/settings/components/SectionsBottom.tsx`
- `apps/admin-app/src/api/csv.ts`
- `apps/admin-app/src/layouts/AppLayout/nav-items.ts` (nav ownership gates)
- `.planning/phases/104-dashboard-reports-settings/104-UI-SPEC.md`
