---
quick_id: 260601-luw
slug: remove-client-pwa-desktop-device-frame-w
description: Remove client-pwa desktop device-frame wrapper — render full-bleed
created: 2026-06-01
status: planned
---

# Quick Task: Remove client-pwa device-frame wrapper (full-bleed render)

## Problem

`apps/client-pwa` wraps the entire app in a fixed-size iPhone "Прототип" mock
frame. On a real phone this renders the PWA as a 390×844 boxed card with a black
bezel and gray margins instead of filling the screen. The frame is pre-existing
prototype scaffolding (NOT part of phase 999.5) and must be removed so the app
is full-bleed and responsive.

## Location

`apps/client-pwa/src/App.jsx` — the return block currently (~lines 213-231):

```jsx
return (
  <div className="stage" data-screen-label="Прототип">
    <div
      data-screen-label={`01 ${tab}`}
      style={{
        width: 390, height: 844, position: 'relative',
        borderRadius: 54, background: '#0a0a0a', padding: 12,
        boxShadow: '0 50px 100px rgba(28,25,23,0.25), 0 0 0 1px rgba(28,25,23,0.15)',
      }}
    >
      <div style={{ position: 'absolute', inset: 12, borderRadius: 44, overflow: 'hidden', background: 'var(--bg)' }}>
        {/* Dynamic island */}
        <div style={{ position:'absolute', top:8, left:'50%', transform:'translateX(-50%)',
          width:120, height:32, borderRadius:999, background:'#000', zIndex:300, pointerEvents:'none' }} />
        <div className="screen">
          ... routes / TabBar / sheets / HomeIndicator ...
        </div>
      </div>
    </div>
  </div>
)
```

`.screen` in `apps/client-pwa/src/styles.css` (~line 103) is already
`position: absolute; inset: 0; background: var(--bg); display:flex; flex-direction:column; overflow:hidden`
— it fills whatever positioned parent contains it.

## Tasks

### Task 1 — Replace the frame wrapper with a full-viewport container (App.jsx)

- Remove the `.stage` wrapper, the fixed `width:390,height:844` black-bezel div
  (`borderRadius:54, background:#0a0a0a, padding:12, boxShadow:…`), the rounded
  `inset:12, borderRadius:44` inner div, and the faux "Dynamic island" pill.
- Replace with a SINGLE full-viewport positioned container that provides the
  positioning context `.screen` needs, e.g.:
  ```jsx
  return (
    <div className="app-viewport">
      <div className="screen">
        {/* unchanged children: tab screen <Routes>, TabBar, sheets, HomeIndicator, toasts */}
      </div>
    </div>
  )
  ```
- Keep ALL existing children of `.screen` exactly as-is (the `<Routes>`, the
  `tabLoading`/`Suspense` wrapper, `<TabBar>`, `<SheetGate>`, `<HomeIndicator>`,
  `<PushToast>`, `<Toaster>`, the `hideTabBar` logic, etc.). Only the outer
  wrapper chain changes.
- Drop the now-obsolete `data-screen-label` dev annotations.

### Task 2 — Add `.app-viewport` full-bleed styles + retire `.stage` (styles.css)

- Add an `.app-viewport` rule that fills the viewport and is a positioning
  context for `.screen`:
  ```css
  .app-viewport { position: fixed; inset: 0; overflow: hidden; background: var(--bg); }
  ```
  (Use `100dvh`/safe-area insets only if needed; `position:fixed; inset:0` already
  tracks the dynamic viewport on mobile.)
- Remove the now-unused `.stage` rule (lines ~92-100: min-height:100vh, flex
  centering, padding:24px, gap:32px) and its comment, since nothing renders
  `.stage` anymore. Leave `.screen` unchanged.
- Ensure `html, body, #root` allow a full-height child (add `height:100%` /
  `margin:0` only if not already present — check before adding to avoid dupes).

## Out of scope (flag in SUMMARY, do NOT change)

- The faux `<StatusBar>` "9:41" bar (rendered per-screen) and `<HomeIndicator>`
  bottom bar are also iOS prototype chrome. The user's explicit ask is the
  bezel/frame only. Note in SUMMARY that these remain and may warrant a
  follow-up (on a real device they can duplicate the OS status bar / home
  indicator), but leave them in place this task.

## Verification

- `pnpm --filter @clubcore/client-pwa lint` — clean.
- `pnpm --filter @clubcore/client-pwa typecheck` — clean (tsc -b).
- Do NOT attempt live browser verification from the worktree — the orchestrator
  verifies live on the main-tree dev server (:5174) after this lands.

## Must-haves

- truths:
  - "The app renders full-bleed: no black bezel, no rounded device corners, no faux dynamic island, no centered gray margins."
  - "`.screen` fills the entire viewport (login, home, onboarding, sheets, tabbar all reach the window edges)."
  - "All routes, TabBar, sheets, HomeIndicator, and toasts still render and function."
  - "lint + typecheck pass for @clubcore/client-pwa."
- artifacts:
  - apps/client-pwa/src/App.jsx
  - apps/client-pwa/src/styles.css
