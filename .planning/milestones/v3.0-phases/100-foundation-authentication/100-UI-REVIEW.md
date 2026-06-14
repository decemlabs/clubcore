---
phase: 100
slug: foundation-authentication
status: advisory
score: 22/24
audited: 2026-06-13
baseline: 100-UI-SPEC.md
screenshots: not captured (no dev server at localhost:5173)
---

# Phase 100 — UI Review

**Audited:** 2026-06-13
**Baseline:** 100-UI-SPEC.md (wiring-only phase over pre-existing design system)
**Screenshots:** not captured (no dev server detected)
**Scope:** three net-new surfaces only — ComingSoon, AppSidebar (role pill + footer card + nav gating), LoginForm error/loading states + RecoveryScreens.

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 4/4 | All Russian copy matches spec exactly; anti-oracle banner, role labels, no-op callout all correct |
| 2. Visuals | 4/4 | Icon choice, hierarchy, skeleton, pill — all per spec; no action button correctly absent from ComingSoon |
| 3. Color | 3/4 | Semantic tokens used throughout; one off-spec hardcoded hex (`#06120c`) in badge active state |
| 4. Typography | 4/4 | All declared sizes and weights match spec; no extra sizes introduced |
| 5. Spacing | 3/4 | Two pre-flagged off-grid values present (`px-[14px] py-[11px]` on error banner); no new violations |
| 6. Experience Design | 4/4 | All interaction states covered; loading/error/empty handled; disabled states during submit correct |

**Overall: 22/24**

---

## Top 3 Priority Fixes

1. **Off-grid error banner padding** — `px-[14px] py-[11px]` in `LoginForm.tsx:100` is not on the 4px grid (spec §Spacing Exceptions notes this but flags it as off-grid). Impact: minor visual inconsistency vs. the rest of the auth UI where all padding is on-grid. Fix: change to `px-3 py-2.5` (12px/10px) or `px-4 py-3` (16px/12px) — advisory, non-blocking.

2. **Hardcoded hex in nav badge active state** — `text-[#06120c]` at `AppSidebar.tsx:105` is a raw color literal. ESLint bans raw palette values; this is a semantic-token violation even though the hex is close to `--ink`. Impact: fails the ESLint raw-palette rule and breaks dark-theme composability. Fix: replace with `text-primary-foreground` or define a named token if the exact value is brand-intentional — advisory, non-blocking.

3. **ChevronRight footer button missing navigation wiring** — `AppSidebar.tsx:147-154` renders a `<button>` with `aria-label="Профиль"` but has no `onClick` handler and no `Link` wrapper. The spec says "keep as-is" for the arrow but the pre-implementation FLAG noted the missing aria-label — that FLAG is resolved. However the button now has a label but still does nothing on click. Impact: screen-reader users will focus an inert button that announces itself as "Профиль" but activates nothing. Fix: either wire it to the Settings/profile route (`ROUTES.settings`) or render it as a `Link` — advisory, non-blocking for Phase 100 but should be resolved before Phase 101 adds profile navigation.

---

## Detailed Findings

### Pillar 1: Copywriting (4/4)

All copy matches the Copywriting Contract exactly.

- `ComingSoon.tsx:16` — heading `«Раздел в разработке»` — PASS
- `ComingSoon.tsx:19` — body copy split across two sentences, matches spec — PASS
- `LoginForm.tsx:100` — `«Неверный email или пароль.»` anti-oracle banner — PASS
- `LoginForm.tsx:64` / `LoginForm.tsx:87` — toast copy `«Не удалось выполнить вход»` / `«Проверьте соединение и попробуйте ещё раз.»` — PASS
- `LoginForm.tsx:139` — remember-me callout `«Сессия действует 7 дней независимо от этого параметра.»` — PASS
- `LoginForm.tsx:151` — Google no-op toast `«Google Workspace вход будет доступен позже.»` — PASS
- `AppSidebar.tsx:71` — owner pill `«Владелец»`, reception `«Ресепшн»` — PASS
- `AppSidebar.tsx:144` — footer card role labels — PASS
- `RecoveryScreens.tsx:38` — email format error copy `«Введите корректный адрес почты»` — PASS
- `RecoveryScreens.tsx:212` — password min-length error `«Пароль должен содержать не менее 12 символов»` — PASS
- No English strings found in any of the three audited surfaces.

### Pillar 2: Visuals (4/4)

- `ComingSoon.tsx:15` — `Clock` icon from `@/components/icons`, `ScreenIcon` with `tone="accent"` — matches spec (52×52 tile, emerald-soft background). PASS
- `ComingSoon.tsx:13` — `flex flex-1 flex-col items-center justify-center` — full-height centering per spec. The `max-w-[400px]` constraint is correctly on the inner wrapper, not the flex container. PASS
- `ComingSoon.tsx` — no action button present — correctly absent per spec. PASS
- Sidebar loading state (`AppSidebar.tsx:126-133`) — avatar circle placeholder + two Skeleton lines — matches spec dimensions (`h-3 w-24`, `h-2.5 w-16`). PASS
- Role pill hidden while session pending (`AppSidebar.tsx:62-73`) — renders `null` — PASS
- Owner pill `bg-primary-soft text-primary-deep`, reception pill `bg-surface-3 text-fg-subtle` — PASS
- Error banner (`LoginForm.tsx:99-104`) — `AlertCircle size-4 shrink-0` left of copy, no `aria-invalid` on fields for credential error — PASS
- Pre-implementation FLAG: "Sidebar ChevronRight/footer button missing aria-label" — RESOLVED at `AppSidebar.tsx:149` (`aria-label="Профиль"`). However see Priority Fix 3 above regarding the inert button.

### Pillar 3: Color (3/4)

- All surface and background tokens are semantic (`bg-surface`, `bg-danger-soft`, `bg-primary-soft`, `bg-surface-3`, `text-danger`, `text-fg`, `text-fg-muted`, `text-fg-subtle`, `text-primary-deep`) — no raw hex outside of the one finding below.
- **WARNING** — `AppSidebar.tsx:105`: `text-[#06120c]` — hardcoded hex in nav badge active state. This is a raw color literal. The ESLint rule in `eslint.config.js` bans raw palette usage. The value appears to be a near-black intended to contrast against `bg-primary` (emerald). This should be `text-primary-foreground` or a named token. This is the only raw hex found across all three surfaces.
- Accent (`--primary`) usage is correctly constrained: ComingSoon icon tile, role pill (owner), badge active, primary buttons — all per the "reserved exclusively for" list in the spec.
- No accent on decorative borders, hover backgrounds, or inactive nav items.

### Pillar 4: Typography (4/4)

All font sizes and weights match the spec's declared roles.

| Spec Role | Spec Size / Weight | Actual (file:line) | Match |
|-----------|--------------------|--------------------|-------|
| ComingSoon heading | `text-[20px] font-bold tracking-[-0.4px]` | `ComingSoon.tsx:16` | PASS |
| ComingSoon body | `text-[14px] leading-[1.55] text-fg-muted` | `ComingSoon.tsx:19` | PASS |
| Badge/pill | `text-[10px] font-bold tracking-[0.4px]` | `AppSidebar.tsx:65` | PASS |
| Footer name | `text-[13px] font-semibold` | `AppSidebar.tsx:140` | PASS |
| Footer role | `text-[11.5px]` | `AppSidebar.tsx:143` | PASS |
| Error banner | `text-[13px]` | `LoginForm.tsx:100` | PASS |

No undeclared font sizes introduced. Weights used: 400/regular (body), 700/bold (headings, pills), 600/semibold (footer name) — all within the declared set.

Pre-implementation FLAG regarding 5-size typography table was documentation-only; no code action was required and none was taken — correctly handled.

### Pillar 5: Spacing (3/4)

On-grid spacing is consistent throughout except for the pre-flagged error banner values.

- **WARNING** (pre-flagged) — `LoginForm.tsx:100`: `px-[14px] py-[11px]` on the credential error banner. 14px and 11px are not on the 4px grid. The spec documented these exact values as the design intent but acknowledged they are off-grid. On-grid alternatives: `px-3 py-2.5` (12px / 10px) or `px-4 py-3` (16px / 12px). The spec retained them for visual continuity with the existing auth-ui; this finding is advisory only.
- `ComingSoon.tsx:13` — `px-6` container padding — on-grid (24px). PASS
- `AppSidebar.tsx:55,123` — header `px-3.5 pb-3.5 pt-[18px]`, footer `px-3.5 pb-[18px]` — `pt-[18px]` and `pb-[18px]` are 18px (off-grid); these are pre-existing values from the established sidebar design, not introduced by Phase 100, and are excluded from this audit scope.
- Skeleton lines (`h-3`, `h-2.5`, `gap-1.5`) — match spec. PASS
- Footer card `p-2 gap-2.5` — matches spec. PASS
- `LoginForm.tsx:137` — remember-me callout wrapper `mb-[22px] mt-2.5` — `mb-[22px]` matches existing auth-ui pattern documented in spec exceptions. PASS

### Pillar 6: Experience Design (4/4)

All interaction states from the spec's Interaction States Summary are implemented.

| State | Surface | Implementation | Result |
|-------|---------|----------------|--------|
| Login — submitting | `LoginForm.tsx:143` | `PrimaryButton loading={isPending}` | PASS |
| Login — fields disabled during submit | `LoginForm.tsx:116,128` | `disabled={isPending}` on both fields | PASS |
| Login — 401 invalid_credentials | `LoginForm.tsx:70-74` | Sets `credentialError`; banner renders above email | PASS |
| Login — 422 field errors | `LoginForm.tsx:76-84` | Maps `err.fields` to `fieldErrors` state | PASS |
| Login — 5xx/network | `LoginForm.tsx:63-68` | `toast.error(...)`, form stays interactive | PASS |
| Login — error cleared on next submit | `LoginForm.tsx:46-47` | Both error states reset at top of `handleSubmit` | PASS |
| Sidebar — session pending | `AppSidebar.tsx:124-133` | Skeleton card rendered | PASS |
| Sidebar — session loaded | `AppSidebar.tsx:133-155` | Real fullName + role label | PASS |
| Sidebar — role pill pending | `AppSidebar.tsx:62` | `session.data` guard; renders `null` while pending | PASS |
| Sidebar — nav gating reception | `AppSidebar.tsx:46-51` | `can()` filter on `ownerOnly` items | PASS |
| Sidebar — deferred items absent | `nav-items.ts` | Сообщения, Уведомления, Филиалы absent from `NAV_SECTIONS` | PASS |
| ComingSoon — static, no loading/error | `ComingSoon.tsx` | Pure static render, no async state | PASS |
| Recovery — loading states | `RecoveryScreens.tsx:31,199` | `usePasswordResetRequest`/`usePasswordResetConfirm` `isPending` wired to `PrimaryButton loading` | PASS |
| Recovery — field errors | `RecoveryScreens.tsx:38,212` | Inline field errors via `Field error` prop | PASS |
| Recovery — 5xx toast | `RecoveryScreens.tsx:51-54,227-230` | `toast.error(...)` with description | PASS |
| TOTP / twofa hidden | Not audited (LoginPage.tsx scope) | Out of scope for this surface audit | N/A |
| Google no-op toast | `LoginForm.tsx:151` | `toast('Google Workspace вход будет доступен позже.')` | PASS |

One note: `ResetScreen` (RecoveryScreens.tsx:207) contains `window.location.search` for token extraction — this is browser-global access rather than router param, which works but bypasses TanStack Router's typed search. This is a minor architectural deviation, not a UI/UX defect; no score impact.

---

## Registry Safety

No third-party registry blocks used in Phase 100. All components are from existing `components/ui/` (shadcn official, hand-maintained). Registry audit: 0 third-party blocks, no flags.

---

## Files Audited

- `/apps/admin-app/src/components/feedback/ComingSoon.tsx`
- `/apps/admin-app/src/layouts/AppLayout/AppSidebar.tsx`
- `/apps/admin-app/src/layouts/AppLayout/nav-items.ts`
- `/apps/admin-app/src/pages/login/components/LoginForm.tsx`
- `/apps/admin-app/src/pages/login/components/RecoveryScreens.tsx`
- `/apps/admin-app/src/pages/login/components/auth-ui.tsx` (referenced, not re-audited — pre-existing)
- `.planning/phases/100-foundation-authentication/100-UI-SPEC.md` (design contract)
