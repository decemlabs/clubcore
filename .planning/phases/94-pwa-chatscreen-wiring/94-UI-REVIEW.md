# Phase 94 — UI Review (Retroactive, Advisory)

**Audited:** 2026-06-08
**Baseline:** `94-UI-SPEC.md` (pixel-perfect-port contract) + `94-REFERENCE-ChatScreen.jsx` (1398 lines, source of truth)
**Implemented:** `apps/client-pwa/src/screens/ChatScreen.jsx` (1510 lines)
**Screenshots:** not captured — no dev server on :5173 / :3000 / :8080. Code-level audit only. Items needing a running browser are flagged `needs browser check`.
**Mode:** Fidelity assessment of a port. Goal = faithfulness to the reference/SPEC, not redesign.

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 4/4 | Every reference Russian string transferred verbatim; added strings (loading/error) match SPEC's P87/P88 directive. |
| 2. Visuals | 4/4 | All hand-rolled components (Ico/Avatar/ReadTick/ConvCard/MessageRow/spot/composer/sheets/FAB) ported markup-identical; photo bubble correctly swapped to real `<img>`. |
| 3. Color | 4/4 | Token tables verbatim; `:root`→`.chat-root`, `body.dark`→`.chat-root.dark`. No hardcoded color drift vs reference. |
| 4. Typography | 4/4 | `.t-mini/.t-small/.t-h3/.t-h1` and every inline size/weight override carried over byte-for-byte. |
| 5. Spacing | 4/4 | All paddings/gaps/touch-target sizes match reference verbatim (composer 8/8/14, bubble 9/13, thread-bar 50px top, etc.). |
| 6. Experience Design | 3/4 | Reconciliation applied cleanly + loading/error states added per SPEC. Minor: one keyframe-name collision risk and a couple of WS-driven states unverifiable without a browser. |

**Overall: 23/24** — advisory PASS. Phase proceeds regardless.

---

## Top 3 Priority Fixes (all WARNING — none blocking)

1. **Unscoped `@keyframes` live in a per-instance injected `<style>`** — `chat-screen-push`, `chat-msg-in`, `chat-spot-float`, etc. are renamed (prefixed `chat-`) to avoid colliding with the reference's generic names, which is good. But they are still global once injected, and the whole `CSS` string is re-inserted on every mount of the lazy-routed component. Duplicate `<style>` blocks accumulate no visual bug but are wasteful. *Fix:* hoist the `<style>{CSS}</style>` to a module-level singleton or inject once via a `useInsertionEffect`/ref-counted head insert. `needs browser check` to confirm duplicate `<style>` nodes appear on tab re-entry.

2. **Always-on green "online" dot in thread bar contradicts v2.5 staff-anonymous reality** (`ChatScreen.jsx:1414`). The reference hardcodes a `var(--accent)` presence dot; the port faithfully copies it. This is fidelity-correct but semantically misleading: there is no presence signal from the backend, so the gym always appears "online". *Fix (product call, not a port defect):* either keep for visual fidelity (current) or gate the dot behind a real presence flag in a later phase. Documented here so it is a conscious choice, not an oversight.

3. **Day-separator React key uses array index** (`ChatScreen.jsx:1302`, `key={'day-' + i}`) — copied verbatim from the reference. With live data where messages prepend on pagination/`?after=` catch-up, index-based keys can cause separator remount/flicker. *Fix:* key by the day label or first-message id of the group. `needs browser check` to observe flicker on scroll-up pagination.

---

## Detailed Findings

### Pillar 1: Copywriting (4/4)
- All Copywriting-Contract strings present verbatim: `Сообщения`, `Чат`, `Поиск по чатам`, seg labels `Все · {n}` / `Новые{· n}`, `Всё прочитано` / `Непрочитанных чатов нет.`, `Ничего не найдено` / `Попробуйте другой запрос.`, list footer note, `Здесь пока пусто` / `Напишите первое сообщение — ответим в рабочее время.`, composer `Сообщение`, `Новые сообщения`, all aria-labels (`Отправить` / `Записать голосовое` / `Прикрепить` / `Назад к списку чатов` / `К последним сообщениям` / `Доставлено` / `Прочитано`), all toasts and sheet labels. Verified `ChatScreen.jsx:1350-1351, 1356, 1364-1365, 1389-1390, 1396, 1292-1293, 1443, 1305, 1445`.
- Status text formula preserved (`ChatScreen.jsx:1322`): for the single official conv resolves to `Мой зал · ✓ верифицирован` — matches SPEC line 740.
- Added-per-SPEC strings (not in reference, mandated by P87/P88 precedent): error heading `Не удалось загрузить` + body `Потяните вниз, чтобы повторить.` (`:1379-1380`), upload validation toasts `Неподдерживаемый формат` / `Файл слишком большой (макс. 5 МБ)` (`:1012-1013`) — matches SPEC PWA-03 line 794, send-fail toasts `Не удалось отправить` / `Не удалось отправить фото`. All Russian, all on-tone.

### Pillar 2: Visuals (4/4)
- `Ico` / `ICON` map / `Avatar` / `ReadTick` copied byte-identical (`:428-483`). ReadTick single-check 11×11 / double-check 16×11, strokes `var(--text-3)` / `var(--accent-deep)`, `marginBottom:-1`, aria-labels — all match SPEC §ReadTick.
- ConvCard markup identical to reference (`:1241-1276`): 48px avatar, official ✓ badge overlay (18×18, `border:2px solid var(--surface)`, inner check `size=11 color=#06120c sw=3`), name `t-h3 fontSize:15`, timestamp 12px `text-3`, sub `t-mini` with `textTransform:none letterSpacing:0.2px`, last-msg ellipsis with `fontWeight: c.unread?500:400`, unread `.badge`. Verbatim.
- **Correct reconciliation of `PhotoBubble`**: reference gradient-preset `PhotoBubble` retained in source but `eslint-disable no-unused-vars`'d and NOT rendered (`:492-504`); MessageRow photo branch instead renders a real `<img src={m.attachment?.url}>` with `objectFit:cover`, tap → `onPhotoTap` (`:539-549`). Matches SPEC §Photo bubble + PWA-03. Note: SPEC §Photo bubble says container `borderRadius:14` and image fills flush; port sets outer wrapper `borderRadius:14` and the `<img>` `borderRadius:10` — a 4px inner-radius difference from the reference's flush fill. Cosmetic, sub-pixel at this size; `needs browser check`.
- Spot illustration markup identical (`:1284-1294`): ring/ring.r2/halo/3 chips/scene/sc-chat b1/b2/me. Empty-thread heading `<div className="t-h3">` (no inline size) → inherits `.thread-empty .t-h3 {font-size:17px}` per SPEC line 539. Match.
- Conv-empty heading uses inline `fontSize:16` (`:1389`) — matches SPEC line 552 ("16px/.t-h3"). Match.
- Thread bar, composer (attach paperclip path, field, mic/send SVGs), scroll-down FAB + sd-dot, day-sep, unread-divider, sheets (long-press + attach), toast — all markup verbatim.
- New full-screen photo overlay (`:1501-1506`) implemented per SPEC PWA-03 (`position:fixed; inset:0; rgba(0,0,0,0.9); z-index:200`, centered img, tap-to-close). The overlay CSS uses `object-fit:contain` (SPEC says `max-width/max-height:100%`); contain is the correct interpretation and a faithful add.

### Pillar 3: Color (4/4)
- Light tokens on `.chat-root` and dark tokens on `.chat-root.dark` are character-for-character identical to the reference `:root` / `body.dark` blocks (`:33-95` vs reference `:12-66`). Accent `#2dd4a4`, accent-deep light `#0f9b76` / dark `#34e0b0`, all bg/surface/border/text/danger values match.
- CSS-scoping contract honored: every selector prefixed `.chat-root `; `html, body` global rule dropped and its font/background/color folded into `.chat-root` itself (`:63-70`); `* { box-sizing }` scoped to `.chat-root *`. No `:root`, no bare `body`, no `body.dark` leak. This satisfies SPEC §CSS Scoping Contract and CONTEXT D-2 — the primary risk of re-theming the rest of the PWA is closed at the code level. `needs browser check` to confirm no token bleed in practice.
- Accent usage stays on the SPEC reserved list (send armed, badge, official ✓, sd-dot, divider line, spot halo/ring/chips, thread-bar presence dot). No new accent surfaces introduced.
- No hardcoded hex drift: the only literal colors are `#06120c` (on-accent text), `#fff` (swipe-action text), `#e7e5e4`/`#1c1917` (avatar bg/fg for МЗ) — all verbatim from reference. Skeleton loader uses token gradients only.

### Pillar 4: Typography (4/4)
- `.t-mini` (11/600/0.5px/uppercase), `.t-small` (13/400/1.4), `.t-h3` (17/600/-0.2px/1.25), `.t-h1` (28/700/-0.6px/1.1) verbatim (`:101-104`).
- Inline overrides all preserved: conv name 15, timestamp 12, sub `t-mini` non-uppercase 0.2px, last-msg 13 weight 500/400, bubble 15/1.4, bubble-meta 11/500, thread name 15/600, status `t-mini` non-uppercase, textarea 15 / line-height 20 / max-height 96, sheet-btn 15/600, toast 13.5/600, day-sep 11/600/0.3px, unread divider 10.5/700/0.5px. No deviations found.

### Pillar 5: Spacing (4/4)
- Verbatim: bubble `9px 13px`, msg-stack gap 3, conv-card pad 14, avatar gap 12, conv-list gap 8 / pad `0 16px`, list header `54px 20px 12px 20px`, searchbar wrapper `0 16px 10px`, seg wrapper `0 16px 12px`, scroller thread `14px 14px`, composer `8px 8px 14px`, composer-field `4px 8px 4px 16px`, sheet pad 8, sheet-btn 14, sheet-title `12px 14px 6px`, thread-bar inner `4px 12px` + top 50px, day-sep `14px 0 8px`, unread-divider `12px 4px 6px`.
- Touch targets verbatim: icon-btn 36, send 40, avatar 48/36, scroll-down FAB 40, official badge 18, badge h20/min20/pad`0 6px`, search-clear 20, seg-item h32, ptr 46 / max translate 64.
- New skeleton `.sk-card` height 76 / margin `0 16px 8px` — approximates the conv-card footprint, sensible non-reference add.

### Pillar 6: Experience Design (3/4)
**Reconciliation — correctly applied:**
- Prototype chrome fully stripped: no `.device` / `.device-inner` / `.island` / `.status-bar` / `.home-indicator` / `.stage` / `.tabbar*` / `.tweaks*` CSS, no Tweaks panel JSX, no `window.parent.postMessage` edit-mode protocol, no global `data-go`/`data-toast` document click handler, no `myzal_theme` localStorage/storage sync. Verified absent across `:1-1510`. Root is now `.chat-root` mounted in the real PWA shell; the prototype's own `.tabbar` (Главная/Запись/Чат/Профиль with `data-go`) is gone — the existing PWA TabBar owns nav, fed via `ui.setUnreadChat` (`:792-801`).
- Hidden-for-future kept in source, not rendered: `PHOTO_PRESETS`/`PhotoBubble` retained but unused (`:485-504`); `MessageRow` `system`/`cancel` branches retained but unreachable with wired data (`:510-535`); attach sheet shows only Камера + Фото из галереи with Документ/Голосовое removed and commented (`:1490-1492`); `showQuick = false` hardcoded so quick-reply chips never render (`:1321`); mic-icon send-btn is a no-op without text (`:1228-1231`); bot autoresponder fully removed from send path (replaced by REST+WS).
- One real conversation: `ADMIN_CONV` only (`:570-578`), other 3 mock convs removed. `isOfficial:true` shows ✓ badge.
- Theme sync reads PWA `data-theme` on `<html>` via prop + `MutationObserver`, toggles `.dark` on `.chat-root` (`:646-659`) — matches SPEC §Theme sync (note: SPEC example reads `classList.contains('dark')`; port reads `getAttribute('data-theme')==='dark'` which is the actual PWA mechanism per CONTEXT — correct adaptation, `needs browser check` to confirm the PWA sets `data-theme` not a `.dark` class).

**Wired states — implemented:**
- Loading: skeleton cards (`:1369-1373`), Error: inline alert + pull-to-retry copy (`:1374-1381`) per P87/P88 directive. Empty thread: branded spot. Optimistic send + rollback (`:976-1007`), optimistic photo with object-URL lifecycle management (`:1010-1050`, WR-02 revoke-when-unreferenced). Read-receipt watermark via epoch-ms comparison (`:751-758`, CR-02). Typing 5s auto-dismiss (`:907-911`). Mark-read latch to avoid PATCH loops (`:721, 966-973`). Pull-to-refresh wired to real `refetch()` (`:1197-1200`). These are robust beyond the reference.

**Deductions (WARNING-level):**
- Per-mount `<style>` injection of the full CSS string for a lazy-routed component → duplicate `<style>` nodes on tab re-entry (see Priority Fix 1). `needs browser check`.
- Day-separator index keys with live prepend-on-pagination data (Priority Fix 3). `needs browser check`.
- Several core states are WS-driven (typing dots, `read_receipt` → ✓✓, `has-new` FAB dot on inbound-while-scrolled-up, scroll-down show threshold 120px) and cannot be verified without a running browser + live WS. Recommend a live smoke pass before sign-off.

**Accessibility:**
- aria-labels present on all icon-only buttons (back, attach, send, scroll-down, search-clear) and ReadTick `role="img"` + label. Loading region has `aria-label="Загрузка сообщений…"`. No regressions vs reference; the port slightly improves on it (overlay img has alt `Просмотр фото`).
- `needs browser check`: focus management when thread view opens/closes (no `:focus` trap or programmatic focus move observed — same as reference, not a regression).

---

## Reconciliation Compliance Summary

| Reconciliation item | Status |
|---------------------|--------|
| Strip device frame / status-bar / home-indicator / stage | DONE |
| Strip prototype `.tabbar` (PWA TabBar owns nav) | DONE |
| Strip Tweaks panel + ACCENTS + applyTweaks | DONE |
| Strip edit-mode postMessage + global data-go/data-toast | DONE |
| Strip `myzal_theme` localStorage/storage sync | DONE |
| CSS scoped under `.chat-root` / `.chat-root.dark`, no global leak | DONE (code-level; `needs browser check`) |
| Hide voice / docs / photo-presets / system / cancel / bot / quick-replies | DONE |
| One real conversation «Администрация / Мой зал» | DONE |
| Wire text/photo/read/typing/unread/mark-read/pull-refresh | DONE (logic; `needs browser check` for WS paths) |

---

## Files Audited
- `/Users/andre/Workspace/Development/clubcore/.planning/phases/94-pwa-chatscreen-wiring/94-UI-SPEC.md`
- `/Users/andre/Workspace/Development/clubcore/.planning/phases/94-pwa-chatscreen-wiring/94-REFERENCE-ChatScreen.jsx`
- `/Users/andre/Workspace/Development/clubcore/.planning/phases/94-pwa-chatscreen-wiring/94-CONTEXT.md`
- `/Users/andre/Workspace/Development/clubcore/apps/client-pwa/src/screens/ChatScreen.jsx`

## Registry Safety
Not applicable — no `components.json` / shadcn / third-party registry in `apps/client-pwa`. No registry audit performed.
