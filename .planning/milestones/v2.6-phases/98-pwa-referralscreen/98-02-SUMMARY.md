---
phase: 98-pwa-referralscreen
plan: "02"
subsystem: client-pwa
tags: [referral, pwa, pixel-perfect-port, d71-09-graduation, react-query]
dependency_graph:
  requires: ["98-01"]
  provides: ["REFER-05", "REFER-06-frontend"]
  affects: ["apps/client-pwa/src/screens/sheets/ReferralSheet.jsx", "apps/client-pwa/src/lib/clientQueries.ts", "apps/client-pwa/src/data/index.js", "apps/client-pwa/eslint.config.js"]
tech_stack:
  added: []
  patterns:
    - "ChatScreen graduation recipe (CSS scoped to .referral-root, chrome stripped)"
    - "Cast escape hatch for schema.d.ts gap (/client/referral/* not in schema.d.ts until Phase 99)"
    - "data-theme MutationObserver for PWA dark mode (not localStorage)"
key_files:
  created:
    - apps/client-pwa/src/screens/ReferralSheet.delist.test.ts
  modified:
    - apps/client-pwa/src/lib/clientQueries.ts
    - apps/client-pwa/src/data/index.js
    - apps/client-pwa/src/screens/sheets/ReferralSheet.jsx
    - apps/client-pwa/eslint.config.js
    - apps/client-pwa/src/screens/ChatScreen.delist.test.ts
decisions:
  - "Cast escape hatch used for /client/referral/summary path (not in schema.d.ts until Phase 99) — mirrors useClientMessages pattern"
  - "Count-up animation deferred in favor of static figure (simpler, non-load-bearing per CONTEXT)"
  - "Avatar color stable hash over name string — deterministic colors without server data"
  - "Tier tracker .milestones rendered with display:none CSS + hidden attr (belt-and-suspenders hide)"
metrics:
  duration: "~25 minutes"
  completed: "2026-06-08T15:09:34Z"
  tasks_completed: 3
  files_modified: 6
---

# Phase 98 Plan 02: PWA ReferralSheet Port + D-71-09 Graduation Summary

**One-liner:** Pixel-perfect port of the Приведи друга screen with React Query hook (useClientReferralSummary), @/data re-export, CSS scoped to .referral-root, and full D-71-09 ESLint graduation (all 3 spots removed, grep returns 0).

## What Was Built

### Task 1: useClientReferralSummary hook + @/data re-export (commit ede0297c)

Added `referralSummary` key-factory entry to `clientPortalKeys`, typed interfaces `ReferralInviteeItem` + `ReferralSummaryData`, and exported `useClientReferralSummary()` in `clientQueries.ts`. The hook uses the cast escape hatch (`clientRequest as unknown as (...)`) because `/client/referral/*` paths are not in `schema.d.ts` until Phase 99 — mirrors the `useClientMessages` pattern exactly.

Re-exported `useClientReferralSummary` from `data/index.js` swap seam and updated the top comment to document that ReferralSheet has graduated (all net-new screens now wired).

### Task 2: Pixel-perfect ReferralSheet.jsx rewrite (commit bc33bd06)

Complete rewrite of the 11-line ComingSoon placeholder (1008 lines). Key implementation:

- **CSS** verbatim from reference, re-scoped to `.referral-root` (`:root` → `.referral-root` with `position:absolute;inset:0`, `body.dark` → `.referral-root.dark`, all component classes prefixed)
- **Device chrome stripped** — `.device`, `.island`, `.status-bar`, `.home-indicator`, `.stage` not transcribed
- **Theme** via `data-theme` MutationObserver on `<html>` (PWA app mechanism)
- **Data wiring** through `useClientReferralSummary` imported from `@/data` only (no mock constants)
- **Loading state**: skeletons for code-box, accrued figure, and friends list; hero/chrome renders immediately
- **Error state**: inline neutral fallback with "Не удалось загрузить" copy
- **Empty state**: "Пока никого" heading + "Поделитесь промокодом — приглашённые друзья появятся здесь."
- **Populated**: `.fr-row` per invitee with initials avatar, ru-RU/Europe/Moscow date, joined (green badge +N ₽) / pending (amber "Ждём") badges
- **Share handlers**: all embed the server `shareUrl` from the summary response (T-98-06 mitigated); `window.open` with `noopener` (T-98-08 mitigated)
- **Tier tracker** (`.milestones`): in DOM behind `hidden` attr + `display:none` CSS — not deleted (SC-5 hide-for-future)
- **Brand**: «Sportzal» (D-62-02) throughout share text and toast copy

### Task 3: D-71-09 ESLint de-list + graduation guard test (commit 3db993dd)

Removed all 3 ReferralSheet spots from `eslint.config.js`:
1. The negated ignore `'!src/screens/sheets/ReferralSheet.jsx'` from the ignores array
2. The entire `{ files: ['src/screens/sheets/ReferralSheet.jsx'], ... }` no-restricted-paths block (~lines 71-109)
3. The leading comments referencing "remaining net-new placeholder screen"

`grep ReferralSheet eslint.config.js` returns 0. Created `ReferralSheet.delist.test.ts` mirroring the ChatScreen pattern (asserts zero occurrences). Updated `ChatScreen.delist.test.ts` to remove the now-stale assertion that the config still contained 'ReferralSheet'.

## Deviations from Plan

None — plan executed exactly as written. The only minor discretionary choice was using a stable hash for avatar background colors (non-load-bearing, not specified in the plan).

## Known Stubs

None. All UI elements read from real query data:
- `code` → `data.code` from `useClientReferralSummary`
- `shareUrl` → `data.shareUrl` from `useClientReferralSummary`
- `accruedKopecks` → `data.accruedKopecks` from `useClientReferralSummary`
- `invitees` → `data.invitees` from `useClientReferralSummary`

The reward amounts ("−1 000 ₽", "14 дней") are static copy from the reference verbatim (no server config for these amounts yet — deferred to future phase per CONTEXT).

## Threat Flags

No new threat surface introduced beyond what was planned and mitigated:
- T-98-06 (shareUrl tampering): mitigated — share handlers use server `shareUrl` only
- T-98-07 (PII disclosure): mitigated — renders only `firstName` + `status` + `bonusKopecks`
- T-98-08 (reverse-tabnabbing): mitigated — `window.open` with `noopener`

## Self-Check: PASSED

Files verified:
- apps/client-pwa/src/lib/clientQueries.ts: FOUND (hook exported)
- apps/client-pwa/src/data/index.js: FOUND (re-export present)
- apps/client-pwa/src/screens/sheets/ReferralSheet.jsx: FOUND (1008 lines, scoped to .referral-root)
- apps/client-pwa/eslint.config.js: FOUND (grep ReferralSheet = 0)
- apps/client-pwa/src/screens/ReferralSheet.delist.test.ts: FOUND
- apps/client-pwa/src/screens/ChatScreen.delist.test.ts: FOUND (stale assertion removed)

Commits verified:
- ede0297c: feat(98-02): add useClientReferralSummary hook and @/data re-export
- bc33bd06: feat(98-02): rewrite ReferralSheet as pixel-perfect data-wired port
- 3db993dd: feat(98-02): D-71-09 ESLint de-list ReferralSheet + graduation guard test
