---
quick_id: 260606-sqb
slug: pixel-perfect-verbatim-port-of-notificat
date: 2026-06-06
type: quick
---

# Quick Task 260606-sqb: Pixel-perfect verbatim port of NotificationsScreen.jsx

## Description

Port the user-provided `NotificationsScreen.jsx` (from the scratch repo
`/Users/andre/Workspace/Development/clubcore-client-pwa/src/screens/NotificationsScreen.jsx`)
into the project at `apps/client-pwa/src/screens/NotificationsScreen.jsx`, **pixel-perfect /
verbatim** — preserving visual design, structure, sizes, paddings, typography, colors, element
states, animations, and UX behavior with NO changes. The final interface must look pixel-for-pixel
like the original.

## Task

### Task 1: Verbatim copy
- action: byte-for-byte copy the source file to `apps/client-pwa/src/screens/NotificationsScreen.jsx`
- files: apps/client-pwa/src/screens/NotificationsScreen.jsx (new)
- verify: `diff -q` source vs destination → identical (md5 match); `pnpm tsc -b --noEmit` exits 0
- done: file present, byte-identical to source, project type-check green

## Notes / boundary

- This is a **verbatim port** — no rewiring, no visual edits, no integration. The component is
  self-contained: own `<style>` CSS, device frame (`.device`/`.island`/`.status-bar`), mock data
  (`INITIAL_ITEMS`), and all interaction logic (swipe-to-delete, long-press action sheet,
  pull-to-refresh, segmented Все/Новые filter, toast, `myzal_theme` dark-mode key).
- The file is **added, not routed** — it does not replace the existing wired `NotificationsSheet.jsx`
  and is not yet imported anywhere, so the running app is unchanged until a follow-up wires it in.
- Follow-up (separate task, not in scope here): decide whether to (a) route this as the notifications
  screen, (b) strip the standalone device frame to live inside the app shell, and (c) wire it to the
  real `useClientNotifications` API instead of mock `INITIAL_ITEMS`.
