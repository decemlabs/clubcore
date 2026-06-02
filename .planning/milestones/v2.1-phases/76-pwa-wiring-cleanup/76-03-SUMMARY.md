---
phase: 76-pwa-wiring-cleanup
plan: "03"
subsystem: client-pwa
tags: [cleanup, mock-removal, chat-badge, conversations]
dependency_graph:
  requires: ["76-01"]
  provides: ["CLEAN-01"]
  affects: ["apps/client-pwa/src/App.jsx", "apps/client-pwa/src/data/index.js"]
tech_stack:
  added: []
  patterns: ["static-zero-prop", "mock-removal"]
key_files:
  modified:
    - apps/client-pwa/src/App.jsx
    - apps/client-pwa/src/data/index.js
  deleted:
    - apps/client-pwa/src/data/conversations.js
decisions:
  - "Pass literal unreadChat={0} rather than removing the prop — TabBar hides the badge at 0 per UI-SPEC §4, no TabBar change needed"
  - "Delete entire import line 17 (CONVERSATIONS + TRAINERS together) since both were unused in App.jsx body"
metrics:
  duration: "~5 minutes"
  completed: "2026-06-02"
  tasks_completed: 3
  tasks_total: 3
  files_changed: 3
---

# Phase 76 Plan 03: Remove CONVERSATIONS mock badge dependency Summary

Static zero replaces the fabricated CONVERSATIONS.reduce unread badge in App.jsx; orphaned conversations.js mock deleted with its re-export removed from data/index.js.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Remove CONVERSATIONS from App.jsx and pass static zero unreadChat | 3c4b995e | apps/client-pwa/src/App.jsx |
| 2 | Delete orphaned conversations mock + its re-export | 41db34ea | apps/client-pwa/src/data/index.js, apps/client-pwa/src/data/conversations.js |
| 3 | Lint + full suite green after cleanup | (no code change) | quality gates verified |

## What Was Built

- **Task 1:** Removed `import { CONVERSATIONS, TRAINERS } from '@/data'` (line 17 — both unused in App.jsx body), deleted the `unreadChat = CONVERSATIONS.reduce(...)` line, and changed `<TabBar unreadChat={unreadChat}>` to `<TabBar unreadChat={0}>`. The chat tab badge is now hidden (TabBar renders no dot when value is 0 or falsy per UI-SPEC §4).

- **Task 2:** Verified no other importer of `conversations.js` exists under `apps/client-pwa/src` (grep returned no results excluding App.jsx, data/index.js, and conversations.js itself). Removed the `export { CONVERSATIONS } from './conversations.js'` re-export (line 51) and the stale comment referencing it (line 7) from `data/index.js`. Deleted `apps/client-pwa/src/data/conversations.js`.

- **Task 3:** All quality gates passed with no code changes: `pnpm lint` (ESLint clean), `pnpm exec vitest run` (77/77 tests pass, 13 test files), `pnpm build` (clean Vite + PWA build).

## Decisions Made

1. **Static zero rather than prop removal:** The plan specified passing `unreadChat={0}` (not removing the prop entirely). This keeps the prop interface stable and makes TabBar's badge-hiding behavior explicit. TabBar already hides at 0.

2. **Entire import line deleted:** Both `CONVERSATIONS` and `TRAINERS` were on line 17. Since `TRAINERS` was also unused in App.jsx's body (verified by plan context — TRAINERS is consumed by TweaksRoot, HomeScreen fallback, UIContext, not App.jsx), the entire line was safe to remove.

3. **TRAINERS and useClientTrainers re-exports preserved:** Only the CONVERSATIONS line was removed from `data/index.js`. The TRAINERS export (line 54/55) and the useClientTrainers export added by Plan 76-01 (line 28) were verified to survive.

## Verification Results

- `CONVERSATIONS` token: absent from App.jsx (grep returns nothing)
- `unreadChat={0}`: present in App.jsx (line 453)
- `apps/client-pwa/src/data/conversations.js`: deleted
- `conversations` references in `data/index.js`: none remaining
- `useClientTrainers` in `data/index.js`: preserved
- `TRAINERS` in `data/index.js`: preserved
- `pnpm exec tsc -b`: exits 0
- `pnpm lint`: exits 0 (no unused-import or undefined errors)
- `pnpm exec vitest run`: 77 tests pass (13 files)
- `pnpm build`: exits 0 (PWA build clean)

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None introduced. This plan removes mock data without introducing new stubs.

## Threat Flags

None. This plan removes fabricated mock data (reducing surface), adds no new network endpoints, auth paths, file access patterns, or schema changes.

## Self-Check: PASSED

- [x] apps/client-pwa/src/App.jsx modified — `CONVERSATIONS` absent, `unreadChat={0}` present
- [x] apps/client-pwa/src/data/index.js modified — `conversations` reference removed, `useClientTrainers` and `TRAINERS` preserved
- [x] apps/client-pwa/src/data/conversations.js deleted
- [x] Commit 3c4b995e exists (Task 1)
- [x] Commit 41db34ea exists (Task 2)
- [x] All quality gates green (77 tests, lint clean, build clean)
