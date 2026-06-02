---
status: passed
phase: 73-downloads-home-html
source: [73-VERIFICATION.md]
started: 2026-06-02T09:00:00Z
updated: 2026-06-02T10:00:00Z
---

## Current Test

[complete — all items passed]

## Tests

### 1. HomeHeroCard visual (gym card + status + occupancy)
expected: A dark surface card at top of screen shows gym name «Мой зал» + open-indicator (GymStatusPill «Открыто до 23:00») + static bar chart colored var(--accent). No animated rotation of levels — occupancy stays at [42,60,30,38] «Свободно» on every load.
result: passed

### 2. SubCardSpot tone rendering (active / warn / danger)
expected: Active → accent-green accent + «активен» badge. Warn → var(--warn) accent + «истекает» badge + «Продлить со скидкой 15%» button. Danger → var(--danger) accent + «истёк» badge + «Продлить» button.
result: passed

### 3. BookSpot animation (book-scene-in + book-float)
expected: The dumbbell card enters with a scale+opacity spring animation on mount. Two floating accent chips bounce with the book-float keyframe. Animation is smooth and does not jank.
result: passed

### 4. ChatTile typing-dot animation
expected: Three dots in the chat bubble animate vertically (translateY bounce) with staggered delay. Animation runs continuously — not static dots. (Verifies the CR-02 code-review fix in a real browser.)
result: passed

### 5. HeroCard tap targets (gym pill / gym title / bell)
expected: Tapping GymStatusPill opens GymInfoSheet; tapping the gym title also opens GymInfoSheet; tapping the bell opens the notifications sheet. All three fire the correct handlers passed from App.jsx.
result: passed

### 6. BookSpot CTA navigation
expected: Tapping the «Запишись на тренировку» card fires onTab('book') and switches to the bookings screen.
result: passed

## Summary

total: 6
passed: 6
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

### G1. ChatTile illustration blended into background on dark theme — RESOLVED
found: human UAT (2026-06-02)
detail: The inverted ChatTile (bg=var(--text), fg=var(--bg)) used a hardcoded
  `rgba(255,255,255,0.13)` chat-bubble background. On dark theme the card bg flips
  to light (var(--text)=#f5f2ef), so the white bubble blended in.
fix: Bubble background now uses `color-mix(in oklab, var(--bg) 13%, transparent)`
  — theme-symmetric (semantic token, no hardcoded color), visible in both themes.
status: resolved
