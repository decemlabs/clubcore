---
phase: 94
slug: pwa-chatscreen-wiring
status: draft
shadcn_initialized: false
preset: none
created: 2026-06-08
mode: pixel-perfect-port
source: 94-REFERENCE-ChatScreen.jsx (1398 lines)
---

# Phase 94 — UI Design Contract: PWA ChatScreen Wiring

> PIXEL-PERFECT PORT mode. This is NOT a new design. Every visual value below is extracted
> verbatim from `94-REFERENCE-ChatScreen.jsx`. The executor must reproduce the reference
> exactly — no redesign, no substitution. The only changes from the reference are:
> (1) prototype chrome stripped, (2) hidden-for-future features kept in code but not rendered,
> (3) CSS scoped to the chat container, (4) mock data replaced with the single real backend thread.
>
> Source of truth: `.planning/phases/94-pwa-chatscreen-wiring/94-REFERENCE-ChatScreen.jsx`
> All LOCKED values are verbatim from that file.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none (inline styles + scoped CSS string — `const CSS`) |
| Preset | not applicable |
| Component library | none (hand-rolled: `Ico`, `Avatar`, `ReadTick`, `PhotoBubble`, `MessageRow`, `ConvCard`) |
| Icon library | inline SVG via `ICON` map + `Ico` component (Lucide-style strokes) |
| Font | `--font: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Inter Variable", "Inter", system-ui, sans-serif` |
| Styling approach | scoped `const CSS` string injected via `<style>{CSS}</style>`; NO Tailwind; NO global `:root` leakage |
| Language | Russian-only (`ru`). All copy verbatim from reference. |
| Timezone | Europe/Moscow for all time display (`Intl.DateTimeFormat`) |

**shadcn gate:** Not applicable — this is a JSX/CSS screen in `apps/client-pwa`. No shadcn, no Tailwind. CSS is scoped to the chat container, not global.

---

## CSS Scoping Contract

The reference CSS block contains global selectors (`html, body`, `:root`, `body.dark`) that MUST be
converted to scoped selectors in the port. Strategy (from CONTEXT.md D-2):

- Inject `<style>{CSS}</style>` scoped within the chat component's root container
- Strip or convert `html, body` global rules (font-family, background, color are set at container level)
- Strip `.device`, `.device-inner`, `.island`, `.status-bar`, `.home-indicator`, `.stage`, `.tweaks` blocks entirely
- Strip the `.tabbar` / `.tabbar-item` / `.tab-badge` rules (existing PWA TabBar owns these)
- Strip `body.dark` global — theme class is on `<html>` via existing PWA ThemeProvider; read via `document.documentElement.classList.contains('dark')` to set the chat container's data attribute or class
- All other selectors (`.screen`, `.view`, `.bubble`, `.composer`, etc.) are scoped by wrapping in a `.chat-root` ancestor
- The reference `--accent`, `--bg`, etc. CSS variables are declared on `.chat-root` (light) and `.chat-root.dark` (dark) — NOT on `:root`

---

## Design Tokens (LOCKED — verbatim from reference `const CSS`)

### Light mode (`.chat-root` — was `:root`)

| Token | Value | Usage |
|-------|-------|-------|
| `--accent` | `#2dd4a4` | Send button armed, unread badge bg, official ✓ badge, unread divider lines, scroll-down dot, read ticks (double) |
| `--accent-deep` | `#0f9b76` | Swipe-to-mute action bg, read tick stroke color, unread divider text, spot chip c1/c3, accent-deep elements |
| `--accent-soft` | `#d6f5ea` | Conv-empty icon wrapper bg, spot halo gradient |
| `--bg` | `#f5f5f4` | Screen/stage background, composer bg, thread bar bg mix |
| `--surface` | `#ffffff` | Cards, bubbles-them, composer field, sheets, scroll-down FAB, avatar bg fallback |
| `--surface-2` | `#fafaf9` | Search bar, segmented control track, send btn unarmed state, system bubbles, sheet-cancel |
| `--border` | `#e7e5e4` | Card borders (0.5px), composer field border, thread bar bottom border, search bar border, day sep pill border, seg control border |
| `--border-strong` | `#d6d3d1` | Composer field textarea border, segmented control items, search-clear btn bg, scroll-down FAB border, quick-reply pill border |
| `--text` | `#1c1917` | Primary text, headings, active seg item color, sheet btn color |
| `--text-2` | `#57534e` | Secondary text, icon-btn default color, sub-labels, sheet-cancel color, send btn unarmed icon |
| `--text-3` | `#a8a29e` | Tertiary text, timestamps, typing dots, search icon, ptr icon, muted label |
| `--warn` | `#e9a23b` | Warning accent (not used in current wired features) |
| `--warn-soft` | `#fef3e2` | Warning soft background |
| `--danger` | `#e1483b` | Destructive sheet btn (Удалить), cancel bubble bg border |
| `--danger-soft` | `#fee2e2` | Cancel bubble background |
| `--font` | `-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Inter Variable", "Inter", system-ui, sans-serif` | All text |
| `--r-pill` | `999px` | Badges, avatars, pills, send btn, scroll-down FAB, quick chips, search-clear |
| `--r-lg` | `20px` | Cards (conv-card, .card), sheets |
| `--sh-1` | `0 1px 2px rgba(28,25,23,0.04)` | Conv-cards, day sep cards |
| `--sh-2` | `0 1px 3px rgba(28,25,23,0.05), 0 4px 14px rgba(28,25,23,0.04)` | Sheets, scroll-down FAB |
| `--page` | `#e7e5e4` | Outer page (stage bg) — not needed post-strip; kept for completeness |

### Dark mode (`.chat-root.dark` — was `body.dark`)

| Token | Value |
|-------|-------|
| `--accent` | `#2dd4a4` |
| `--accent-deep` | `#34e0b0` |
| `--accent-soft` | `rgba(45, 212, 164, 0.18)` |
| `--bg` | `#14110e` |
| `--surface` | `#211c18` |
| `--surface-2` | `#1b1714` |
| `--border` | `#2e2823` |
| `--border-strong` | `#3d362f` |
| `--text` | `#f5f1ea` |
| `--text-2` | `#b8b0a6` |
| `--text-3` | `#7c736a` |
| `--warn` | `#e9a23b` |
| `--warn-soft` | `rgba(233, 162, 59, 0.20)` |
| `--danger` | `#f47168` |
| `--danger-soft` | `rgba(244, 113, 104, 0.18)` |
| `--sh-1` | `0 1px 2px rgba(0,0,0,0.4)` |
| `--sh-2` | `0 1px 3px rgba(0,0,0,0.5), 0 4px 14px rgba(0,0,0,0.3)` |
| `--page` | `#0a0a0a` |

---

## Spacing Scale

Chat screen uses a mixed scale derived from the reference. Not 8-point strict — values extracted
verbatim.

| Context | Value | Usage |
|---------|-------|-------|
| Bubble padding | `9px 13px` | All `.bubble` text bubbles |
| Bubble gap in stack | `3px` | `.msg-stack` gap |
| Conv-card inner padding | `14px` | Card content area |
| Conv-card avatar gap | `12px` | Avatar → content gap |
| Conv-list gap | `8px` | `.conv-list` between cards |
| Conv-list side padding | `16px` | `.conv-list` padding: `0 16px` |
| List header padding | `54px 20px 12px 20px` | Title block top padding (under status bar area) |
| Searchbar padding | `0 16px 10px` | Wrapper padding |
| Seg control padding | `0 16px 12px` | Wrapper padding |
| Scroller thread padding | `14px 14px` | Thread message area |
| Composer padding | `8px 8px 14px` | Composer bar |
| Composer field padding | `4px 8px 4px 16px` | Inner composer field |
| Sheet padding | `8px` | Sheet outer |
| Sheet btn padding | `14px` | Sheet button row |
| Sheet title padding | `12px 14px 6px` | Sheet title area |
| Thread bar padding | `4px 12px` | Thread top bar inner row |
| Thread bar top offset | `50px` (padding-top) | Clears PWA status + safe area |
| Day sep margin | `14px 0 8px` | Above separator |
| Unread divider margin | `12px 4px 6px` | Above first unread |

Exceptions (touch targets):
- Icon buttons (`.icon-btn`): `36px × 36px`
- Send button (`.send-btn`): `40px × 40px`
- Avatar (list): `48px × 48px`
- Avatar (thread bar): `36px × 36px`
- Scroll-down FAB: `40px × 40px`
- Official ✓ badge overlay: `18px × 18px` (border `2px solid var(--surface)`)
- Unread badge (`.badge`): `20px` height, min-width `20px`, padding `0 6px`
- Tab badge: `16px` height, min-width `16px`, padding `0 4px`, border `1.5px solid var(--surface)`
- Search-clear button: `20px × 20px`
- Segmented control item height: `32px`
- Pull-to-refresh indicator: `46px` height trigger, max translate `64px`

---

## Typography

All values LOCKED from reference CSS (`.t-mini`, `.t-small`, `.t-h3`, `.t-h1`).

| Class | Size | Weight | Letter-spacing | Line-height | Color | Text-transform |
|-------|------|--------|----------------|-------------|-------|----------------|
| `.t-mini` | 11px | 600 | 0.5px | — | `var(--text-3)` | uppercase |
| `.t-small` | 13px | 400 | — | 1.4 | `var(--text-2)` | — |
| `.t-h3` | 17px | 600 | -0.2px | 1.25 | `var(--text)` | — |
| `.t-h1` | 28px | 700 | -0.6px | 1.1 | `var(--text)` | — |

Additional inline overrides (from reference JSX — LOCKED):

| Context | Size | Weight | Notes |
|---------|------|--------|-------|
| Conv-card name | 15px | (`.t-h3` override) | `fontSize: 15` on the span |
| Conv-card timestamp | 12px | — | `color: var(--text-3)` |
| Conv-card sub label | t-mini | 500 | `textTransform: 'none'`, `letterSpacing: '0.2px'` |
| Conv-card last msg | 13px (`.t-small`) | 500 if unread / 400 | overflow: ellipsis |
| Bubble text | 15px | 400 | `line-height: 1.4` |
| Bubble meta (time) | 11px | 500 | `.bubble-meta`, `color: var(--text-3)` |
| System bubble | 12.5px | 500 | `line-height: 1.45`, `max-width: 290px`, centered |
| Cancel bubble header | 12px | 700 | `letterSpacing: '0.4px'`, uppercase |
| Cancel bubble body | 13.5px | 500 | `lineHeight: 1.45` |
| Thread bar name | 15px | 600 | `.t-h3` override |
| Thread bar status | t-mini | 500 | `textTransform: 'none'`, `letterSpacing: '0.2px'` — accent-deep when typing, text-3 otherwise |
| Composer textarea | 15px | — | `line-height: 20px`, `min-height: 20px`, `max-height: 96px` |
| Quick-reply chip | 13px | 500 | `.quick` |
| Sheet btn | 15px | 600 | `.sheet-btn` |
| Toast | 13.5px | 600 | `.toast` |
| Day sep pill | 11px | 600 | `letter-spacing: 0.3px` |
| Unread divider label | 10.5px | 700 | `letter-spacing: 0.5px`, uppercase, `color: var(--accent-deep)` |
| Tabbar item label | 10.5px | 600 | `letterSpacing: 0.1px` (STRIPPED — existing PWA TabBar owns this) |
| `.t-num` | — | — | `font-variant-numeric: tabular-nums` |
| Conv-empty heading | 16px | 600 | Inline override on `.t-h3` |
| List footer note | `.t-small` | — | `color: var(--text-3)` |

---

## Color Contract (60/30/10)

| Role | Token | Value (light / dark) |
|------|-------|-----------------------|
| Dominant 60% | `--bg` | `#f5f5f4` / `#14110e` — screen background, stage, composer bar |
| Secondary 30% | `--surface` | `#ffffff` / `#211c18` — cards, bubbles-them, sheets, search bar, scroll-down FAB |
| Accent 10% | `--accent` | `#2dd4a4` (both modes) — see reserved list below |
| Danger | `--danger` | `#e1483b` / `#f47168` — destructive sheet btn only |

**Accent (`--accent`) reserved for these specific elements only:**

1. Send button `.send-btn.armed` background
2. Unread badge `.badge` background (conv-list + thread scroll-down dot)
3. Official ✓ badge overlay on avatar
4. Typing dots (future — color comes from `var(--text-3)` for the dots themselves, but the indicator row uses bubble-them which uses `--surface`)
5. Scroll-down FAB `.sd-dot` new-message indicator
6. Unread divider line `color-mix(in oklab, var(--accent) 32%, transparent)`
7. Spot illustration: halo gradient `color-mix(in oklab, var(--accent) 20%, transparent)`, ring `color-mix(in oklab, var(--accent) 42%, transparent)`, chip `.me` bar, chip `.c2`
8. Segmented control active item uses `var(--text)` background (NOT accent)

**`--accent-deep` reserved for:**
- Swipe-to-mute action background
- Read tick (double-check) SVG stroke
- Unread divider text (`Новые сообщения`)
- Thread bar status text when typing
- Spot chip c1 and c3

---

## Component Contracts (LOCKED — verbatim from reference)

### `.bubble` — Message Bubbles

```
max-width: 78%
padding: 9px 13px
border-radius: 18px
font-size: 15px
line-height: 1.4
word-break: break-word
```

Variants:
- `.bubble-me`: `background: var(--accent); color: #06120c; border-bottom-right-radius: 5px`
- `.bubble-them`: `background: var(--surface); color: var(--text); border: 0.5px solid var(--border); border-bottom-left-radius: 5px`
- `.bubble-system`: `background: var(--surface-2); color: var(--text-2); border: 0.5px solid var(--border); font-size: 12.5px; line-height: 1.45; max-width: 290px; text-align: center; border-radius: 14px; font-weight: 500` — HIDDEN in wired phase (no system_message type in backend)
- `.bubble-cancel` (inline style): `background: var(--danger-soft); color: var(--danger); border: 0.5px solid color-mix(in oklab,var(--danger) 30%,transparent); maxWidth: 280; textAlign: center; fontSize: 13.5; lineHeight: 1.45; fontWeight: 500` — HIDDEN in wired phase

Photo bubble (real attachment — replaces gradient preset):
- Container: `width: 220px; height: 140px; border-radius: 14px; overflow: hidden`
- Image: rendered as `<img>` via IDOR-safe attachment URL; object-fit: cover
- Bubble padding override: `padding: 4` (image fills flush)

### `ReadTick` — Read Status Icons

Single check (delivered):
- SVG `11×11`, viewBox `0 0 11 11`
- Path: `M1 6l3 3 6-7`, stroke `var(--text-3)`, strokeWidth `1.6`
- `aria-label="Доставлено"`

Double check (read):
- SVG `16×11`, viewBox `0 0 16 11`
- Path 1: `M1 6l3 3 6-7`, Path 2: `M6 6l3 3 6-7`
- Both strokes: `var(--accent-deep)`, strokeWidth `1.6`
- `aria-label="Прочитано"`

Both have `style={{ marginBottom: -1 }}`.

Data mapping: `read` ⇔ `readAt != null` (backend `readAt` field).

### `Avatar` Component

```
border-radius: 999px
display: flex; align-items: center; justify-content: center
font-weight: 600; flex-shrink: 0; line-height: 1; overflow: hidden
```
- Size 48px in list, 36px in thread bar
- Font size = `Math.round(size * 0.36)` → 17px (list), 13px (thread)
- Wired: for the single «Мой зал» conversation: `initials: 'МЗ'`, `color: '#1c1917'`, `bg: '#e7e5e4'`

### `.conv-card` — Conversation Card

```css
position: relative; z-index: 1; display: block; width: 100%; text-align: left;
border: 0.5px solid var(--border); border-radius: var(--r-lg);
background: var(--surface); color: var(--text);
cursor: pointer; touch-action: pan-y;
transition: transform 0.26s cubic-bezier(0.32,0.72,0.2,1);
-webkit-user-select: none; user-select: none;
```

Official ✓ badge overlay (for «Администрация / Мой зал» only):
```
position: absolute; right: -2px; bottom: -2px;
width: 18px; height: 18px; border-radius: 999px;
background: var(--accent);
display: flex; align-items: center; justify-content: center;
border: 2px solid var(--surface);
```
Contains `<Ico name="check" size={11} color="#06120c" sw={3} />`.

Press state: `.press:active { transform: scale(0.985); }`

### `.swipe` — Swipe-to-Mute Wrapper

```css
position: relative; border-radius: var(--r-lg); overflow: hidden;
```

`.swipe-action`:
```css
position: absolute; inset: 0;
display: flex; align-items: center; justify-content: flex-end;
gap: 7px; padding-right: 24px;
color: #fff; font-size: 13.5px; font-weight: 700;
background: var(--accent-deep); opacity: 0;
transition: opacity 0.15s ease;
```
`.swipe.armed .swipe-action { opacity: 1; }`

Swipe threshold: `dx <= -64` → mute action fires; card snaps back, `.armed` removed after 180ms.
Long-press threshold: 450ms → vibrate 8ms + open action sheet.

### `.thread-bar` — Thread Top Bar

```css
flex-shrink: 0;
padding-top: 50px; padding-bottom: 10px;
background: color-mix(in oklab, var(--bg) 88%, transparent);
backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
border-bottom: 0.5px solid var(--border);
```

Contents (left to right):
1. Back chevron icon-btn (36×36, `stroke="var(--text)"`, strokeWidth 2.2)
2. Avatar 36px with online dot: `width:10; height:10; border-radius:999; background: var(--accent); border: 2px solid var(--bg)`
3. Name `.t-h3` at 15px + status text `.t-mini` (typing → accent-deep color; idle → text-3)

Status text formula: `typing ? 'печатает…' : conv.sub + (conv.isOfficial ? ' · ✓ верифицирован' : ' · в сети')`
For the single wired conversation: `'Мой зал · ✓ верифицирован'` when not typing.

### `.composer` — Message Composer

```css
flex-shrink: 0;
padding: 8px 8px 14px; border-top: 0.5px solid var(--border);
background: var(--bg); display: flex; align-items: flex-end; gap: 6px;
```

Attach button (left of field):
- `width: 40px; height: 40px` icon-btn, `color: var(--text-2)`
- Paperclip SVG: `M21 11l-8.5 8.5a4.5 4.5 0 01-6.4-6.4L14 5a3 3 0 014.2 4.2l-8 8a1.5 1.5 0 01-2.1-2.1l7.3-7.3`, strokeWidth 1.8

`.composer-field`:
```css
flex: 1; background: var(--surface); border-radius: 22px;
border: 0.5px solid var(--border-strong); padding: 4px 8px 4px 16px;
display: flex; align-items: center; min-height: 40px;
```

Textarea inside:
```css
flex: 1; border: 0; outline: 0; background: transparent;
font-size: 15px; color: var(--text); font-family: inherit;
padding: 0; margin: 0; resize: none; line-height: 20px;
min-height: 20px; max-height: 96px; overflow-y: auto; display: block;
```
Auto-grow: `ta.style.height = 'auto'` then `Math.min(ta.scrollHeight, 110) + 'px'` (via `useLayoutEffect` on `input` change).
Enter key: sends if `!e.shiftKey`; Shift+Enter = newline.

`.send-btn`:
```css
width: 40px; height: 40px; border-radius: 999px; border: 0;
display: flex; align-items: center; justify-content: center;
cursor: pointer; flex-shrink: 0; transition: background 0.15s;
background: var(--surface-2); color: var(--text-2);   /* unarmed */
```
`.send-btn.armed`:
```css
background: var(--accent); color: #06120c;
```
Unarmed icon: microphone SVG (`rect x9 y3 w6 h13 rx3; path M5 11a7 7 0...`), strokeWidth 1.8.
Armed icon: send/paper-plane SVG (`M22 2L11 13; M22 2l-7 20-4-9-9-4 20-7z`), strokeWidth 2.

**HIDDEN in wired phase:** Unarmed state shows mic icon but sends voice mock in prototype.
In wired phase: mic icon still shown, but tapping sends nothing (voice feature hidden-for-future).
Armed state (text in field): sends text message normally.

### Typing Dots

```css
.typing-dots { display: inline-flex; gap: 4px; align-items: center; }
.typing-dots span {
  width: 7px; height: 7px; border-radius: 999px; background: var(--text-3);
  animation: typing-bounce 1.2s ease-in-out infinite;
}
.typing-dots span:nth-child(2) { animation-delay: 0.15s; }
.typing-dots span:nth-child(3) { animation-delay: 0.3s; }
@keyframes typing-bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.5; }
  30% { transform: translateY(-3px); opacity: 1; }
}
```
Rendered inside `.bubble.bubble-them` with `padding: 10px 14px` (not 9px 13px).
Triggered by WS `typing` event (Phase 91 ephemeral, 5s TTL, auto-dismiss).

### `.scroll-down` — Scroll-to-Bottom FAB

```css
position: absolute; right: 14px; bottom: 78px; z-index: 6;
width: 40px; height: 40px; border-radius: 999px;
background: var(--surface); border: 0.5px solid var(--border-strong);
box-shadow: var(--sh-2); cursor: pointer;
display: flex; align-items: center; justify-content: center; color: var(--text-2);
opacity: 0; transform: translateY(12px) scale(0.9); pointer-events: none;
transition: opacity 0.22s ease, transform 0.22s cubic-bezier(0.32,0.72,0.2,1);
```
`.scroll-down.show { opacity: 1; transform: none; pointer-events: auto; }`

New-message dot (`.sd-dot`):
```css
position: absolute; top: -2px; right: -2px; width: 12px; height: 12px;
border-radius: 999px; background: var(--accent); border: 2px solid var(--surface);
opacity: 0; transform: scale(0.5); transition: opacity 0.2s, transform 0.2s;
```
`.scroll-down.has-new .sd-dot { opacity: 1; transform: none; }`

Show threshold: `scrollHeight - scrollTop - clientHeight >= 120`.
Has-new: set when inbound message arrives and user is not near bottom.

### Day Separator

```css
.day-sep { display: flex; justify-content: center; margin: 14px 0 8px; }
.day-sep span {
  background: var(--surface-2); border: 0.5px solid var(--border);
  color: var(--text-3); font-size: 11px; font-weight: 600; letter-spacing: 0.3px;
  padding: 4px 12px; border-radius: 999px;
}
```
Rendered when message `day` field changes (grouped by date label).

### Unread Divider

```css
.unread-divider { display: flex; align-items: center; gap: 10px; margin: 12px 4px 6px; }
.unread-divider::before, .unread-divider::after {
  content: ''; flex: 1; height: 1px;
  background: color-mix(in oklab, var(--accent) 32%, transparent);
}
.unread-divider span {
  font-size: 10.5px; font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase;
  color: var(--accent-deep); white-space: nowrap;
}
```
Label: `Новые сообщения`. Placed above the first unread message on thread open.

### `.sheet` — Bottom Action Sheet

```css
position: absolute; left: 8px; right: 8px; bottom: 8px; z-index: 81;
background: var(--surface); border: 0.5px solid var(--border);
border-radius: 24px; box-shadow: var(--sh-2); padding: 8px;
transform: translateY(150%); transition: transform 0.34s cubic-bezier(0.32,0.72,0.2,1);
```
`.sheet.show { transform: translateY(0); }`

`.sheet-backdrop`:
```css
position: absolute; inset: 0; z-index: 80;
background: rgba(0,0,0,0.32); opacity: 0; pointer-events: none;
transition: opacity 0.25s ease;
```
`.sheet-backdrop.show { opacity: 1; pointer-events: auto; }`

`.sheet-btn`:
```css
display: flex; align-items: center; gap: 12px; width: 100%;
border: 0; background: transparent; font-family: inherit;
font-size: 15px; font-weight: 600; color: var(--text);
padding: 14px; border-radius: 14px; cursor: pointer; text-align: left;
```
`.sheet-btn:hover { background: var(--surface-2); }`
`.sheet-btn.danger { color: var(--danger); }`
`.sheet-cancel { margin-top: 4px; justify-content: center; background: var(--surface-2); color: var(--text-2); }`

### `.searchbar`

```css
display: flex; align-items: center; gap: 8px;
background: var(--surface-2); border: 0.5px solid var(--border);
border-radius: 12px; padding: 0 12px; height: 40px;
```
Search icon: 18×18, `stroke="currentColor"`, strokeWidth 2.
Input: font-size 15px, `color: var(--text)`, background transparent.
Clear button: 20×20 pill, `background: var(--border-strong); color: var(--surface)`, shows when query non-empty.
Placeholder: `"Поиск по чатам"`.

### `.seg` — Segmented All/Unread Control

```css
.seg { display: flex; gap: 2px; padding: 3px; background: var(--surface-2); border: 0.5px solid var(--border); border-radius: 999px; }
.seg-item {
  appearance: none; border: 0; background: transparent; cursor: pointer;
  height: 32px; border-radius: 999px; font-family: inherit; font-size: 12.5px; font-weight: 600;
  color: var(--text-2); transition: background 0.15s, color 0.15s, box-shadow 0.15s;
}
.seg-item.active { background: var(--text); color: var(--bg); box-shadow: 0 1px 4px rgba(0,0,0,0.18); }
```
Labels: `Все · {count}` / `Новые{unreadCount > 0 ? ' · ' + unreadCount : ''}`.
Width: `style={{ flex: 1, width: '100%' }}` on each item.

### `.toast`

```css
position: absolute; left: 50%; bottom: 96px; transform: translate(-50%, 16px);
z-index: 90; background: var(--text); color: var(--bg);
font-size: 13.5px; font-weight: 600; padding: 11px 18px; border-radius: 999px;
box-shadow: 0 12px 30px rgba(0,0,0,0.28);
opacity: 0; pointer-events: none;
transition: opacity 0.22s ease, transform 0.28s cubic-bezier(0.32,0.72,0.2,1);
white-space: nowrap;
```
`.toast.show { opacity: 1; transform: translate(-50%, 0); }`
Auto-dismiss after 1700ms.

### Branded Empty State — Thread (`.thread-empty`)

Shown when thread has no messages and `!typing`.

```css
.thread-empty {
  display: flex; flex-direction: column; align-items: center; text-align: center;
  padding: 50px 24px 24px;
}
```

`.spot` illustration (128×96px):
- `.halo`: 90×90 radial gradient circle, `color-mix(in oklab, var(--accent) 20%, transparent)`
- `.ring`: 90×90 dashed ring, `border: 1.5px dashed color-mix(in oklab, var(--accent) 42%, transparent); opacity: 0.5`
- `.ring.r2`: 118×118, `opacity: 0.24`
- `.scene`: 76×62, `border-radius: 15px`, rotated -4deg, animated via `scene-in`
  - Contains `.sc-chat` with three `<i>` bars: `.b1` (72%), `.b2` (48%), `.me` (58%, right-aligned, accent color)
- Three floating chips (`.chip`): animated via `spot-float`

Text below spot:
- Heading (`.t-h3`): `"Здесь пока пусто"` — `margin-top: 14px`
- Body (`.t-small`): `"Напишите первое сообщение — ответим в рабочее время."` — `max-width: 248px; margin-top: 6px`

### Conv-List Empty State (`.conv-empty`)

```css
.conv-empty { display: flex; flex-direction: column; align-items: center; text-align: center; padding: 44px 24px 24px; }
```

Icon wrapper: `56×56, borderRadius: 16, background: var(--accent-soft)`.
Icon inside: `<Ico name={searching ? 'search' : 'check'} size={26} color="var(--accent-deep)" sw={1.9} />`

Two states:
- **Filter=unread, no unread**: Icon `check`. Heading: `"Всё прочитано"` (16px/.t-h3). Body: `"Непрочитанных чатов нет."` (max-width 230px, margin-top 4).
- **Searching, no results**: Icon `search`. Heading: `"Ничего не найдено"`. Body: `"Попробуйте другой запрос."`.

---

## Animation Contract (LOCKED — verbatim from reference keyframes)

| Name | Keyframe | Trigger | Duration + Easing |
|------|----------|---------|-------------------|
| `screen-push` | `from { transform: translateX(40px); opacity: 0; }` | Thread open (`.view-enter`) | `0.34s cubic-bezier(0.32,0.72,0.2,1)` |
| `screen-pop` | `from { transform: translateX(-30px); opacity: 0; }` | Thread close (`.view-back`) | `0.3s cubic-bezier(0.32,0.72,0.2,1)` |
| `msg-in` | `from { opacity: 0; transform: translateY(10px) scale(0.98); }` | New message (`.msg-in`) | `0.32s cubic-bezier(0.32,0.72,0.2,1) both` |
| `typing-bounce` | `0%,60%,100% {translateY(0); opacity:0.5} 30% {translateY(-3px); opacity:1}` | Typing dots (each dot) | `1.2s ease-in-out infinite` (delays: 0, 0.15s, 0.3s) |
| `scene-in` | `0% {scale(0.5) opacity:0} 60% {scale(1.06)} 100% {scale(1) opacity:1}` | Spot illustration (empty state) | `0.46s cubic-bezier(0.32,1.6,0.32,1) both` |
| `spot-float` | `0%,100% {translateY(0) rotate(0)} 50% {translateY(-6px) rotate(10deg)}` | Floating chips in spot | `3.4s ease-in-out infinite` (delays: 0, 0.7s, 1.2s) |
| `ptr-spin` | `to { transform: rotate(360deg); }` | Pull-to-refresh loading | `0.7s linear infinite` |
| Sheet slide in | `transform: translateY(150%) → translateY(0)` | Sheet open (`.sheet.show`) | `0.34s cubic-bezier(0.32,0.72,0.2,1)` |
| Scroll-down FAB show | `opacity 0.22s ease, transform 0.22s cubic-bezier(0.32,0.72,0.2,1)` | Near-bottom state change | built-in transition |
| Toast show | `opacity 0.22s ease, transform 0.28s cubic-bezier(0.32,0.72,0.2,1)` | `toast()` call | built-in transition |
| Conv-card swipe | `transform 0.26s cubic-bezier(0.32,0.72,0.2,1)` | Swipe restore | built-in transition |
| `fade-up` | `from { opacity: 0; transform: translateY(8px); }` | Empty states | `0.32s cubic-bezier(0.32,0.72,0.2,1) both` |

---

## Gesture Contract

### Swipe-to-mute (conv list card)

- Pointer down → capture `x0, y0`; set `card.style.transition = 'none'`
- Pointer move → track `dx`; clamp `transform: translateX(clamp(-100, dx, 0))`; toggle `.armed` when `dx < 0`
- Pointer up:
  - If `dx <= -64` → fire mute, snap back, show swipe-action reveal + toast
  - Else → snap back
- Only horizontal swipe (if `|dx| > |dy|` after 6px threshold)

### Long-press (conv list card)

- Timer: 450ms after pointer down without movement
- On fire: `navigator.vibrate(8)` + open action sheet
- Clears if pointer moves >6px before 450ms

### Pull-to-refresh (list view)

- Only fires when `scrollTop === 0`
- Pull threshold: `dy * 0.5`, max translate `64px`; opacity = `min(1, pull/46)`
- Release at `pull >= 44` → animate to `44px`, spin icon, hold 850ms, snap back + toast `"Обновлено"`
- In wired version: 850ms window triggers real `refetch()` from React Query

### Scroll-to-bottom FAB click

- `sc.scrollTo({ top: sc.scrollHeight, behavior: 'smooth' })`
- Remove `.has-new` class

### Composer auto-scroll

- On send (own message): `stickRef.current = true` → `useLayoutEffect` scrolls to bottom
- On inbound message: stick if user was within 140px of bottom; else show `.has-new` dot on FAB

---

## Interaction States

| State | Visual |
|-------|--------|
| Thread loading | Spinner or skeleton per P87/P88 precedent (loading/error/retry pattern from NotificationsSheet) |
| Thread error | Inline error + retry button (same pattern as TrainerDetailSheet) |
| Thread empty (no messages) | Branded spot illustration + copy (see above) |
| Typing (inbound staff) | `.bubble.bubble-them` with `.typing-dots` (3 dots, `typing-bounce` anim) |
| New inbound (not near bottom) | `.has-new` dot on scroll-down FAB |
| Unread divider | `.unread-divider` above first unread on thread open |
| Message sent (mine) | Single check (delivered) `var(--text-3)` |
| Message read | Double check (read) `var(--accent-deep)` |
| Conv-card unread | `.badge` with count; last-msg font-weight 500; text `var(--text)` |
| Conv-list filter=unread, none | Empty state: check icon + "Всё прочитано" |
| Search no results | Empty state: search icon + "Ничего не найдено" |
| Send button unarmed | `background: var(--surface-2); color: var(--text-2)` + mic SVG |
| Send button armed | `background: var(--accent); color: #06120c` + send SVG |
| Pull-to-refresh loading | PTR icon spins, list shifts down 44px |
| Sheet open | Backdrop `rgba(0,0,0,0.32)` + sheet slides from bottom |
| Toast | Pill from bottom (`bottom: 96px`), auto-dismiss 1700ms |
| Muted conversation | Sub-label appended with `' · приглушён'` |

---

## Reconciliation Contract (LOCKED — from CONTEXT.md 2026-06-08)

### Strip from prototype (do NOT port)

| Element | CSS/JSX |
|---------|---------|
| iPhone device frame | `.device`, `.device-inner`, `.island` |
| Status bar (simulated iOS) | `.status-bar` |
| Home indicator | `.home-indicator` |
| Prototype tabbar | `.tabbar`, `.tabbar-item`, `.tab-badge` CSS (existing PWA TabBar owns this) |
| Tweaks panel | `.tweaks`, `TWEAK_DEFAULTS`, `ACCENTS`, `applyAccent`, `applyTweaks`, `setTweak` |
| edit-mode postMessage protocol | `window.parent.postMessage`, `__activate_edit_mode` message listener |
| Global `data-go`/`data-toast` handler | `document.addEventListener('click', onClick)` |
| `myzal_theme` localStorage sync | `applyTweaks` writes to `localStorage.myzal_theme`; `storage` event listener |

### Hidden for future (code retained, not rendered)

| Feature | How to hide |
|---------|-------------|
| Voice message (mic btn → real send) | Show mic SVG in unarmed send-btn but no-op on tap; no voice recording |
| Document attach | Sheet shows only Camera + Фото из галереи; Документ button commented/flagged off |
| Голосовое in attach sheet | `Голосовое` button commented/flagged off |
| `PHOTO_PRESETS` gradient bubbles (`PhotoBubble` with preset) | Replace with real `<img>` for photo attachments; `PHOTO_PRESETS` constant kept but unused |
| `system` message kind rendering | `MessageRow` system/cancel branches kept in code; no system messages in backend |
| `cancel` message kind rendering | Same — kept, not rendered for wired data |
| Bot autoresponder (`botReplies`) | Remove from `sendMessage` logic; real staff replies arrive via WS |
| Quick-reply chips | Hidden (bot-coupled; `showQuick` always false in wired version) |

### Wired to backend (real)

| Feature | Backend endpoint |
|---------|-----------------|
| Text send | `POST /api/v1/client/messages` + WS `new_message` echo |
| Photo attach | Camera/Gallery → validate image/≤5MB → two-step upload (`POST /api/v1/client/messages/attachments`) → send | 
| Photo display | Real IDOR-safe attachment URL (`GET /api/v1/client/attachments/{id}`) in `<img>` |
| Full-screen photo tap | Overlay (see PWA-03) |
| Read receipts | `readAt != null` → double check (WS `read_receipt` event updates) |
| Typing indicator | WS `typing` event → show dots; auto-dismiss after 5s (ephemeral) |
| Unread count | `unreadCount` from REST `GET /api/v1/client/messages` → feeds TabBar badge |
| Mark-read | `PATCH /api/v1/client/messages/read` on thread open + inbound-while-open |
| Pull-to-refresh | Real `queryClient.invalidateQueries` + REST refetch |
| WS reconnect catch-up | REST `GET /api/v1/client/messages?after={cursor}` on reconnect |

### Single real conversation

List contains exactly **one** conversation card:
- `name: 'Администрация'`, `sub: 'Мой зал'`, `initials: 'МЗ'`
- `color: '#1c1917'`, `bg: '#e7e5e4'` (same as reference `c1`)
- `isOfficial: true` (shows ✓ badge)
- `unread`: from backend `unreadCount`
- `last`: last message body preview (truncated)
- `lastTime`: `sentAt` formatted `HH:MM` or day label

The other 3 mock conversations (`c2` тренер, `c3` уведомления, `c4` ресепшен) are removed.

### Theme sync

The existing PWA uses `next-themes` (admin-web) / its own theme mechanism. In `apps/client-pwa`, theme is read from the existing PWA context (not Tweaks panel). The chat container reads theme state and toggles `.dark` class on its root element:

```js
const isDark = document.documentElement.classList.contains('dark')
// or read from existing PWA theme context
```

Apply `dark` class to the `.chat-root` container (not `document.body`).

---

## Data Mapping (Reference Mock → Backend)

| Reference mock field | Backend field | Notes |
|---------------------|--------------|-------|
| `m.from === 'me'` | `message.role === 'client'` | Current authenticated client |
| `m.from === 'them'` | `message.role === 'staff'` | Staff message |
| `m.time` | `Intl.DateTimeFormat('ru-RU', {hour:'2-digit', minute:'2-digit', timeZone:'Europe/Moscow'}).format(new Date(message.sentAt))` | Display format HH:MM |
| `m.read` | `message.readAt != null` | Boolean derived from readAt |
| `m.body` | `message.body` | Text content |
| `m.kind === 'photo'` | `message.attachment != null` | Photo bubble if attachment present |
| `m.photo` (gradient preset) | `message.attachment.id` → IDOR-safe URL | Real image URL |
| `c.unread` | `thread.unreadCount` | From REST response |
| `c.last` | `thread.lastMessage.body` or `'📷 Фото'` if photo | Preview text |
| `c.lastTime` | Formatted `thread.lastMessage.sentAt` | Same HH:MM format |
| `m.id` for unread divider | First message with `readAt == null` and `role === 'staff'` | Backend-derived |
| Day group label (`m.day`) | Derived from `sentAt` via date-fns `ru` locale | 'Сегодня', 'Вчера', day/month |
| `c.isOfficial = true` | Hardcoded for the single gym conversation | Always true for «Мой зал» |

---

## Copywriting Contract (LOCKED — Russian-only, verbatim from reference)

| Element | Copy |
|---------|------|
| List screen heading (mini label) | `Сообщения` |
| List screen heading (h1) | `Чат` |
| Search placeholder | `Поиск по чатам` |
| Seg control: all | `Все · {n}` |
| Seg control: unread | `Новые` / `Новые · {n}` |
| Empty list (filter=unread) heading | `Всё прочитано` |
| Empty list (filter=unread) body | `Непрочитанных чатов нет.` |
| Empty list (search) heading | `Ничего не найдено` |
| Empty list (search) body | `Попробуйте другой запрос.` |
| List footer note | `Администрация работает с 8:00 до 22:00. Тренеры отвечают в свободное время.` |
| Empty thread heading | `Здесь пока пусто` |
| Empty thread body | `Напишите первое сообщение — ответим в рабочее время.` |
| Thread bar status (idle) | `Мой зал · ✓ верифицирован` |
| Thread bar status (typing) | `печатает…` |
| Composer placeholder | `Сообщение` |
| Send btn aria-label (armed) | `Отправить` |
| Send btn aria-label (unarmed) | `Записать голосовое` |
| Attach btn aria-label | `Прикрепить` |
| Back btn aria-label | `Назад к списку чатов` |
| Scroll-down btn aria-label | `К последним сообщениям` |
| Unread divider label | `Новые сообщения` |
| Read tick aria-label (single) | `Доставлено` |
| Read tick aria-label (double) | `Прочитано` |
| Toast: pull-to-refresh done | `Обновлено` |
| Toast: muted | `Чат заглушён` |
| Toast: unmuted | `Уведомления включены` |
| Toast: archived | `Чат в архиве` |
| Toast: deleted | `Чат удалён` |
| Action sheet title (mini) | `Чат` |
| Action sheet: mark read | `Прочитано` |
| Action sheet: mark unread | `Не прочитано` |
| Action sheet: mute | `Заглушить` |
| Action sheet: unmute | `Включить уведомления` |
| Action sheet: archive | `В архив` |
| Action sheet: delete | `Удалить` |
| Action sheet: cancel | `Отмена` |
| Attach sheet title (mini) | `Прикрепить` |
| Attach sheet: camera | `Камера` |
| Attach sheet: gallery | `Фото из галереи` |
| Muted conv sub-label suffix | `· приглушён` |
| Official badge sub-label suffix | `· ✓ верифицирован` |
| Conv «Мой зал» sub-label | `Мой зал` |
| Conv «Мой зал» name | `Администрация` |
| Unread badge cap | `99+` (display cap; exact count from backend up to 99) |

**Destructive actions:** `Удалить` (delete conv) — no confirmation dialog; single tap in sheet fires immediately (same as reference). In wired phase operates on local UI state only (single conv cannot truly be deleted; if clicked, show toast but keep conv — or per CONTEXT.md: local state delete as prototype does).

---

## PWA-03: Photo Picker + Full-Screen Overlay

Wired (Phase 94, not in reference CSS — implement per pattern):

**Attach flow:**
1. Tap attach btn → attach sheet slides up (Camera / Фото из галереи)
2. Camera: `capture="environment"` input (hidden `<input type="file" accept="image/*" capture="environment">`)
3. Gallery: hidden `<input type="file" accept="image/jpeg,image/png,image/webp">`
4. Client-side validation: magic bytes check + size ≤5MB; show toast on fail
5. Two-step: POST upload → get `attachmentId` → POST message with `attachmentId`
6. Optimistic bubble: show preview `<img>` in bubble immediately; confirm/rollback on response

**Photo bubble (real image):**
- Same outer structure as `PhotoBubble` but `<img src={attachmentUrl} style={{width:220, height:140, borderRadius:14, objectFit:'cover'}}>`
- Tap → full-screen overlay (no CSS in reference; use `position:fixed; inset:0; background:rgba(0,0,0,0.9); z-index:200`)
- Overlay: centered `<img>` with `max-width:100%; max-height:100%`; tap anywhere to close

**File validation error toast:** `"Файл слишком большой (макс. 5 МБ)"` / `"Неподдерживаемый формат"`

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| None | — | not applicable — no shadcn, no third-party registry |

---

## Loading / Error States (PWA Pattern — from P87/P88 precedent)

Per `NotificationsSheet.jsx` (P87) and `TrainerDetailSheet.jsx` (P88) graduation precedents:

**Loading:** Centered spinner or skeleton rows while initial message fetch is in progress.
**Error:** Inline error message + "Повторить" retry button.
**Retry:** `queryClient.invalidateQueries` or manual `refetch()`.

These patterns are NOT in the reference (which has no loading state); implement per project convention.

---

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS
- [ ] Dimension 2 Visuals: PASS
- [ ] Dimension 3 Color: PASS
- [ ] Dimension 4 Typography: PASS
- [ ] Dimension 5 Spacing: PASS
- [ ] Dimension 6 Registry Safety: PASS

**Approval:** pending
