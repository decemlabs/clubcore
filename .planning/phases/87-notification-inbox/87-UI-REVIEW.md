# Phase 87 — UI Review

**Audited:** 2026-06-06
**Baseline:** 87-UI-SPEC.md (approved design contract)
**Screenshots:** not captured (no dev server running on ports 3000, 5173, 8080)

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 3/4 | All contract strings present verbatim; one deviation: section label top padding omitted per spec |
| 2. Visuals | 3/4 | Icon/color mapping correct; booking cancellation uses accent-soft per spec but intent signals danger; no visual regression |
| 3. Color | 4/4 | All semantic tokens used; single hardcoded hex (#fff on toast) is a documented PWA-internal pattern |
| 4. Typography | 3/4 | .t-* classes used correctly; section label element overrides fontWeight to 700 (spec value is 600 from .t-mini) and t-small default color `var(--text-2)` is not overridden on the timestamp element |
| 5. Spacing | 3/4 | Core spacing follows spec; two non-spec padding values present (14px bottom on skeleton/list wrappers; 10px/14px on toast) |
| 6. Experience Design | 4/4 | Loading/error/empty/optimistic/rollback/debounce all implemented; pull-to-refresh on error; feature flag kill-switch; both Home variants updated |

**Overall: 20/24**

---

## Top 3 Priority Fixes

1. **Section label `fontWeight: 700` overrides `.t-mini`'s declared 600** — The `.t-mini` class already sets `font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase`. The inline style block at line 268–271 of `NotificationsSheet.jsx` redundantly re-declares all three properties AND bumps fontWeight to 700, diverging from the spec and `.t-mini` baseline. Fix: remove the `fontWeight`, `letterSpacing`, and `textTransform` inline overrides; keep only `color` and `padding`. (`NotificationsSheet.jsx:270`)

2. **Skeleton/list wrapper bottom padding 14px is off-scale** — The spec declares the spacing scale with no 14px step; the canonical closest values are 12px (xs+) and 16px (md). `padding: '0 16px 14px'` appears twice (line 277, line 310) for the skeleton container and notification list container. If the intent is "compact bottom breathing room", use `12px`; if it is "standard bottom margin", use `16px`. Pick one and document the exception. (`NotificationsSheet.jsx:277,310`)

3. **Booking cancellation icon container colour semantics — `accent-soft` for `booking_cancelled_by_client` and `booking_cancelled_by_owner`** — The spec (`87-UI-SPEC.md` Color section) explicitly maps all booking kinds including cancellations to `background: var(--accent-soft); color: var(--accent-deep)`. However, this is semantically confusing: a cancellation shares the same green tint as a confirmation. The spec is technically met, but the spec itself is under-specified on this point. Flagging as a WARNING to revisit in UI-SPEC v2 — the icon (`close`) communicates cancellation but the green container fights that signal. Not blocking but worth a future spec amendment to use a neutral `var(--surface-2)` container for cancellation kinds. (`NotificationsSheet.jsx:52–54`)

---

## Detailed Findings

### Pillar 1: Copywriting (3/4)

WARNING — All required copy strings verified present verbatim against the contract:

| Contract string | Present | Location |
|----------------|---------|----------|
| Sheet title "Уведомления" | YES | line 248 |
| Mark-all "Всё прочитано" | YES | line 260 |
| Section label "УВЕДОМЛЕНИЯ" | YES | line 272 |
| Empty heading "Нет уведомлений" | YES | line 301 |
| Empty body "Здесь будут появляться уведомления о записях, платежах и других событиях." | YES | line 303 |
| Error body "Не удалось загрузить уведомления. Потяните вниз, чтобы повторить." | YES | line 286 |
| Load-more "Загрузить ещё" | YES | line 334 |
| Skeleton aria-label "Загрузка уведомлений…" | YES | line 277 |
| Bell aria-label (no unread) "Уведомления" | YES | HomeScreen.jsx line 140, 869 |
| Bell aria-label (with unread) "Уведомления · {N} непрочитанных" | YES | HomeScreen.jsx line 140, 869 |

The section label text is hardcoded as `УВЕДОМЛЕНИЯ` (already uppercase) while the element also applies `textTransform: uppercase` — redundant but not broken. No generic labels (Submit, OK, Cancel) found.

One minor gap: the spec's mark-all error rollback toast copy is "Не удалось отметить прочитанными" (line 226 `NotificationsSheet.jsx`). Verified matches spec. No deviation.

Score reduced to 3 rather than 4 only because of the redundant inline text properties on the section label element that introduce a spec deviation on fontWeight (see Pillar 4).

### Pillar 2: Visuals (3/4)

WARNING — All seven notification kinds mapped correctly to icons and color containers per spec table:

| Kind | Icon | Container bg | Status |
|------|------|-------------|--------|
| booking_confirmed | calendar | accent-soft / accent-deep | PASS |
| booking_cancelled_by_client | close | accent-soft / accent-deep | SPEC-MET (semantic concern noted) |
| booking_cancelled_by_owner | close | accent-soft / accent-deep | SPEC-MET (semantic concern noted) |
| booking_rescheduled | history | accent-soft / accent-deep | PASS |
| payment_succeeded | card | accent-soft / accent-deep | PASS |
| autopay_charge_succeeded | card | accent-soft / accent-deep | PASS |
| autopay_charge_failed | alertCircle | danger-soft / danger | PASS |

Unread dot: correctly rendered at `width: 8, height: 8, borderRadius: 999, background: var(--accent), flexShrink: 0, alignSelf: center` — exactly per spec. Conditional on `item.readAt === null`. (`NotificationsSheet.jsx:97–103`)

Hairline divider: `height: 0.5, marginLeft: 60` — correct. (`NotificationsSheet.jsx:315`)

Sheet shell structure (StatusBar → SubSheetHeader → PullToRefresh scroller) matches spec exactly.

Empty state icon: `bell` at size 28 in a 60×60 circle. Correct per spec.

One visual concern: booking cancellation icon container is green (`accent-soft`), while the `close` icon suggests a negative event. Users may experience colour-intent mismatch. The spec permits this, but it degrades visual communication quality. Score 3 not 4.

### Pillar 3: Color (4/4)

All color usage audited against the spec's token inventory:

- `var(--bg)` — sheet background (`line 239`). Correct.
- `var(--surface)` — notification card container (`.card` via CSS class). Correct.
- `var(--accent)` — unread row dot (`line 100`). Correct; reserved use per spec.
- `var(--accent-soft)` / `var(--accent-deep)` — booking/payment icon containers. Correct.
- `var(--danger-soft)` / `var(--danger)` — autopay failure icon container. Correct.
- `var(--surface-2)` — empty state icon container background (`line 296`). Correct.
- `var(--text)`, `var(--text-2)`, `var(--text-3)` — text hierarchy. Correct on all elements.
- `var(--border)` — hairline dividers. Correct.

Hardcoded values found:
- `#f43f5e` (bell unread dot in HomeScreen) — inherited existing value, documented exception in spec. Not a new violation.
- `#fff` on toast element (`line 347`) — toast is not governed by the spec (it's an implementation detail for the local in-sheet toast, a deviation from the Sonner plan). The `var(--danger)` background with white text is a reasonable pattern but lacks a semantic token equivalent.

No raw palette classes (no Tailwind `bg-*` palette). No new hardcoded hex values beyond the inherited `#f43f5e`. Score: 4/4.

### Pillar 4: Typography (3/4)

Typography classes used in `NotificationsSheet.jsx`:

| Class | Elements | Spec says |
|-------|----------|-----------|
| `.t-h3` | Empty state heading | YES — correct |
| `.t-body` | Notification title (+ `fontWeight: 700`) | YES — correct modifier |
| `.t-small` | Body, timestamp, error, empty body, mark-all label | YES — correct |
| `.t-mini` | Section label | YES — but with overrides (see below) |

Deviations:

1. **Section label redundant overrides** (`NotificationsSheet.jsx:268–271`): `.t-mini` defines `font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase; color: var(--text-3)`. The inline style applies `fontWeight: 700, letterSpacing: 0.5, textTransform: 'uppercase'`. The `fontWeight: 700` override diverges from the class definition (600) and the spec contract (the spec does not list 700 for this element). The `letterSpacing` and `textTransform` are redundant no-ops but harmless.

2. **Toast `fontSize: 13`** (`line 349`): raw `fontSize: 13` bypasses the type system. The correct class would be `.t-small` (also 13px). Minor but diverges from the "no inline font-size overrides" principle from the spec's Typography section.

3. **`.t-small` default color** (`styles.css:253`): `.t-small { color: var(--text-2) }` — on the timestamp element, the spec requires `color: var(--text-3)`. This IS properly overridden at `NotificationsSheet.jsx:91`. Correct.

No new font sizes introduced. No non-spec weights except the section label 700 override.

### Pillar 5: Spacing (3/4)

Spacing scale declared in spec: 4, 8, 12, 16, 24, 32, 48, 64. Exceptions documented: 12px (xs+), 0.5px hairline, bell dot top:8 / right:9.

Verified values:

| Value | Location | Spec compliance |
|-------|----------|----------------|
| `padding: '12px 16px'` | Row (line 73), skeleton row (line 112) | PASS — documented xs+ exception |
| `gap: 12` | Row and skeleton (lines 73, 112) | PASS — documented xs+ exception |
| `padding: '0 16px 8px'` | Section label (line 269) | PASS — 8px (sm) bottom |
| `padding: '16px 16px'` | Error state (line 284) | PASS — 16px (md) |
| `padding: '48px 24px'` | Empty state (line 293) | PASS — 48px (2xl) + 24px (lg) |
| `marginLeft: 60` | Hairline divider (line 315) | PASS — 60 = 16+32+12, spec-specified |
| `padding: '0 16px 24px'` | Load-more wrapper (line 326) | PASS — 24px (lg) |
| `height: 32` | Bottom padding (line 340) | PASS — 32px (xl) |
| `marginBottom: 8` | Skeleton line gap (line 115) | PASS — 8px (sm) |

Off-scale values:

1. **`padding: '0 16px 14px'`** at lines 277 (skeleton wrapper) and 310 (list wrapper) — 14px is not on the declared scale. Adjacent canonical values are 12px (xs+) and 16px (md). The spec does not document 14px as an exception.

2. **`padding: '10px 14px'`** on the in-sheet toast (line 348) — both 10px and 14px are off-scale. However, the toast itself is an implementation-detail element not governed by the spec (it replaced the planned Sonner integration). Flagging but treating as lower severity.

3. **`margin: '0 auto 16px'`** on empty state icon container (line 295) — 16px bottom margin. PASS — 16px is md.

4. **`marginTop: 1`** (body element, line 88) and **`marginTop: 2`** (timestamp, line 91) — sub-pixel optical adjustments. The spec specifies these as `marginTop: 1` and `marginTop: 2` respectively (spec Layout section, Content block sub-items). These match the spec exactly.

### Pillar 6: Experience Design (4/4)

Full state coverage verified:

| State | Implementation | Location |
|-------|---------------|---------|
| Loading / skeleton | `isFetching && allItems.length === 0` → 4 skeleton rows | lines 276–280 |
| Error inline | `isError && allItems.length === 0` → error copy + pull-to-refresh | lines 283–289 |
| Empty state | `!isFetching && !isError && allItems.length === 0` → bell icon + copy | lines 292–306 |
| Load-more pagination | `hasMore` gate + page increment | lines 325–337 |
| Load-more disabled during fetch | `disabled={isFetching}` | line 330 |
| Optimistic mark-all | `setAllItems` immediate + rollback `onError` | lines 218–226 |
| Optimistic mark-single on open | 800ms debounce + `setOptimisticReadIds` | lines 177–188 |
| Pull-to-refresh | `<PullToRefresh onRefresh={handleRefresh}>` resets page + items | lines 195–201 |
| Feature flag kill-switch | `NOTIFICATIONS_FEATURE_FLAGS.notificationsInbox` | lines 233–235 |
| Bell badge — both Home variants | `useClientNotifications(1)` → `unreadCount` → both `HomeHeroCard` and `HomeNewbie` | HomeScreen.jsx lines 268–269, 319, 326 |
| Rules of Hooks compliance | All hooks called before feature-flag early return | lines 128–144 |
| Local in-sheet toast | `[toastMsg, setToastMsg]` state with 2600ms auto-dismiss | lines 133, 139 |
| Rollback snapshot correctness | Pre-optimistic snapshot captured before `setState` (CR-01 fix) | lines 210–211 |

No state transitions missing. Error on mark-all shows a local toast and rolls back — correct. No global Sonner dependency (correctly replaced). Both Home variants (ActiveSub / Newbie) receive the live `unread` prop correctly.

---

## Registry Safety

Registry audit: 0 third-party blocks — PWA does not use shadcn. Registry audit skipped per protocol.

---

## Files Audited

- `apps/client-pwa/src/screens/sheets/NotificationsSheet.jsx` (357 lines — primary audit target)
- `apps/client-pwa/src/screens/HomeScreen.jsx` (lines 100–335, 820–902 — bell badge sections)
- `apps/client-pwa/src/styles.css` (lines 251–254 — `.t-mini`, `.t-body`, `.t-small`, `.t-h3` definitions)
- `.planning/phases/87-notification-inbox/87-UI-SPEC.md` (design contract baseline)
- `.planning/phases/87-notification-inbox/87-04-SUMMARY.md` (implementation summary)
- `.planning/phases/87-notification-inbox/87-04-PLAN.md` (task plan)
- `.planning/phases/87-notification-inbox/87-01-SUMMARY.md` (backend data layer summary)
- `.planning/phases/87-notification-inbox/87-CONTEXT.md` (phase context)
