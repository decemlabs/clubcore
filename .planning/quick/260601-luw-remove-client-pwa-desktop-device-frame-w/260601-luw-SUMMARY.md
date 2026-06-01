---
quick_id: 260601-luw
slug: remove-client-pwa-desktop-device-frame-w
status: complete
commit: 4f70c69f
completed: 2026-06-01
---

# Quick Task Summary: Remove client-pwa device-frame wrapper (full-bleed render)

Removed the desktop iPhone "Прототип" device-frame wrapper from `apps/client-pwa`
so the app renders full-bleed and responsive instead of as a fixed 390×844 boxed
card with a black bezel and centered gray margins.

## Status

Complete. Lint + typecheck clean. Committed as `4f70c69f`.

## Files Changed

- `apps/client-pwa/src/App.jsx` — replaced the outer wrapper chain.
- `apps/client-pwa/src/styles.css` — added `.app-viewport`, removed `.stage`,
  added `html, body, #root { height: 100% }`.

## What Changed

### Task 1 — App.jsx

- Replaced the `.stage` → fixed `390×844` black-bezel div
  (`borderRadius: 54, background: '#0a0a0a', padding: 12, boxShadow: …`) → inset
  `borderRadius: 44` rounded div → faux dynamic-island pill wrapper chain with a
  **single** full-viewport container `<div className="app-viewport">` directly
  wrapping `<div className="screen">`.
- Dropped the obsolete `data-screen-label="Прототип"` and ``data-screen-label={`01 ${tab}`}``
  dev annotations and the faux dynamic-island `<div>`.
- Kept all existing `.screen` children intact: the `tabLoading`/`Suspense` block,
  `<Routes>` and every `<Route>`, the lazy sheet `<SheetGate>` overlays, `<PushToast>`,
  `<TabBar>`, the `hideTabBar` logic, and `<TweaksRoot>`.
- `<HomeIndicator />` is now a sibling of `.screen` inside `.app-viewport` (it was
  previously a sibling of `.screen` inside the now-removed inset/rounded div), so
  rendering position is preserved.
- Re-indented the `.screen` subtree by −4 spaces to match the two removed nesting
  levels (App.jsx is in the `.jsx` allowJs ramp and is excluded from eslint/tsc, so
  this is cosmetic, not tool-enforced).

### Task 2 — styles.css

- Added `.app-viewport { position: fixed; inset: 0; overflow: hidden; background: var(--bg); }`
  — fills the viewport and provides the positioning context that `.screen`
  (`position: absolute; inset: 0`) needs.
- Removed the now-unused `.stage` rule (the `min-height: 100vh` flex-centering block)
  and its comment.
- Added `html, body, #root { height: 100% }` — `#root` had no rules and no
  `height: 100%` existed previously; `html, body` already had `margin: 0` (lines
  76–86) so margin was not duplicated. (`.app-viewport` is `position: fixed` so it
  self-anchors to the viewport; the height rule is a belt-and-suspenders guard for
  any non-fixed descendant assumptions.)
- `.screen` left unchanged.

## Out of Scope (left in place — flagged for follow-up)

The faux `<StatusBar>` "9:41" bar (rendered per-screen) and the `<HomeIndicator>`
bottom bar are also iOS-prototype chrome. Per the task scope, only the
bezel/frame was removed; these remain. On a real device they can duplicate the OS
status bar / home indicator and may warrant a follow-up task to remove or
conditionally hide them.

## Deviations from Plan

None — plan executed as written. (The −4-space re-indent of the `.screen` subtree
is the mechanical consequence of removing two wrapper nesting levels, not a scope
change; `.screen` children are otherwise unchanged.)

## Verification

- `pnpm --filter @clubcore/client-pwa lint` — clean (exit 0). Note: `App.jsx` is a
  `.jsx` file in the D-69-06 allowJs ramp and is globally ignored by eslint, so the
  lint pass covers the rest of the package, not App.jsx itself.
- `pnpm --filter @clubcore/client-pwa typecheck` (`tsc -b --noEmit`) — clean (exit 0).
  No unrelated pre-existing errors observed.
- Live browser verification deliberately NOT run from the worktree — the
  orchestrator verifies on the main-tree dev server (:5174) after this lands.

## Self-Check: PASSED

- App.jsx modified and committed: FOUND
- styles.css modified and committed: FOUND
- Commit 4f70c69f: FOUND
- No live `.stage` / `data-screen-label` / dynamic-island references remain: CONFIRMED
