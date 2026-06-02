---
phase: 76-pwa-wiring-cleanup
verified: 2026-06-02T21:50:00Z
status: human_needed
score: 4/5 must-haves code-verified (PDATA-02 persistence requires browser)
overrides_applied: 0
human_verification:
  - test: "Personal Data save persists across a full page reload"
    expected: >
      After editing a field (name, email, goal, height, or weight) and tapping
      Сохранить, a full browser refresh and re-opening Профиль → Личные данные
      shows the edited values (not the original seeded values). Confirms
      PATCH /client/me reaches the backend and the cache invalidation on onSettled
      causes a refetch from the persisted row.
    why_human: >
      Persistence across a hard reload requires a running backend + browser.
      The mutation payload shape and cache invalidation wiring are verified in code
      (onSettled invalidates clientPortalKeys.me() + .home()), but the backend
      persisting and returning updated data from Postgres cannot be confirmed by
      static analysis alone.
  - test: "Negative: save failure shows inline toast"
    expected: >
      With the backend stopped, editing a field and tapping Сохранить shows the
      inline error toast 'Не удалось сохранить данные. Попробуйте ещё раз.' and the
      field retains its edited value.
    why_human: Requires simulating a network failure against a running dev environment.
---

# Phase 76: PWA Wiring + Cleanup — Verification Report

**Phase Goal:** The newbie-Home screen displays real trainer avatars and live plan-catalog chips; the Personal Data sheet reads from and saves to the backend; the mock chat-badge is gone.
**Verified:** 2026-06-02T21:50:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #  | Truth (Success Criterion)                                                                 | Status      | Evidence                                                                                   |
|----|------------------------------------------------------------------------------------------|-------------|--------------------------------------------------------------------------------------------|
| 1  | NHOME-01: Trainer avatars from GET /client/trainers; overflow counter uses live count    | VERIFIED    | `useClientTrainers()` wired in `HomeNewbie` (HomeScreen.jsx:855); `tr.fullName` read (camelCase, CR-02 fix confirmed at line 1023); fallback to `STATIC_TRAINERS_FALLBACK` when empty (line 1005); overflow chip `+{count - 3}` uses live `.length` (line 1034) |
| 2  | NHOME-02: Plan chip shows live count + min monthly price from GET /client/plans           | VERIFIED    | `useClientPlans()` in `HeroNewbie` (HomeScreen.jsx:349); `p.priceKopecks / (p.durationDays / 30)` with camelCase (CR-01 fix at lines 553-554); zero-duration/non-finite filter + empty-after-filter guard (WR-05 fix at line 555); renders nothing on loading/error (D-76-09) |
| 3  | PDATA-01: Personal Data sheet hydrates name/phone/email/goal/height/weight from useClientMe | VERIFIED | `useClientMe()` called at ProfileExtraSheets.jsx:50; hydration effect at lines 74-84 sets all 6 fields from `meData`; per-client `hydratedForId` ref guards against clobber (WR-03 fix); no hardcoded "Саша"/"sasha@example.com" on API-backed fields (grep confirmed absent) |
| 4  | PDATA-02: Save calls PATCH /client/me and persists after full reload                     | PARTIAL     | `updateProfile.mutateAsync` called at lines 116-122 with correct payload shape; `onSettled` invalidates `clientPortalKeys.me()` + `.home()` in `useUpdateClientProfile` (clientQueries.ts:225-228); height/weight coerced via `toPosInt` (positive integer, no NaN/float — WR-02 fix); goal constrained to 4-value enum pill selector. **Live persistence across reload requires human verification (browser + running backend).** |
| 5  | CLEAN-01: CONVERSATIONS import absent from App.jsx; unreadChat=0                        | VERIFIED    | `grep CONVERSATIONS App.jsx` returns no output; `unreadChat={0}` at App.jsx:453; `conversations.js` deleted (file does not exist); `data/index.js` contains no conversations export |

**Score:** 4/5 code-verifiable truths verified; 1 requires browser testing

---

### Required Artifacts

| Artifact                                                                 | Expected                                  | Status    | Details                                                      |
|--------------------------------------------------------------------------|-------------------------------------------|-----------|--------------------------------------------------------------|
| `apps/client-pwa/src/lib/clientQueries.ts`                              | useClientTrainers() hook + trainers key   | VERIFIED  | clientPortalKeys.trainers() at line 29; useClientTrainers export at line 321-329 calling GET /api/v1/client/trainers |
| `apps/client-pwa/src/data/index.js`                                     | useClientTrainers re-exported; no CONVERSATIONS | VERIFIED | Line 28: `useClientTrainers` in export block; CONVERSATIONS absent |
| `apps/client-pwa/src/screens/HomeScreen.jsx`                            | Live trainer strip + plan chip            | VERIFIED  | camelCase field reads confirmed; fallback logic present; overflow counter wired |
| `apps/client-pwa/src/screens/sheets/ProfileExtraSheets.jsx`             | API-hydrated personal data + PATCH save   | VERIFIED  | useClientMe + useUpdateClientProfile wired; goal enum pill selector; positive-integer coercion |
| `apps/client-pwa/src/App.jsx`                                           | CONVERSATIONS removed; unreadChat=0       | VERIFIED  | Token absent; static zero prop confirmed |
| `apps/client-pwa/src/data/conversations.js`                             | Deleted (orphaned mock)                   | VERIFIED  | File does not exist |
| `apps/client-pwa/src/lib/clientQueries.trainers.test.ts`               | Unit tests for useClientTrainers          | VERIFIED  | File exists; tests included in 77/77 pass |
| `apps/client-pwa/src/screens/HomeScreen.identity.test.jsx`              | NHOME-01/02 assertions with camelCase fixtures | VERIFIED | Fixtures use `fullName` (line 203-204) and `priceKopecks`/`durationDays` (lines 224-225); no snake_case in test |
| `apps/client-pwa/src/screens/sheets/PersonalDataSheet.identity.test.jsx` | PDATA-01/02 identity tests              | VERIFIED  | 11 tests covering hydration, save payload, enum constraint, button states, error toast |

---

### Key Link Verification

| From                          | To                              | Via                                           | Status   | Details                                                                              |
|-------------------------------|---------------------------------|-----------------------------------------------|----------|--------------------------------------------------------------------------------------|
| HomeNewbie (HomeScreen.jsx)   | GET /api/v1/client/trainers     | useClientTrainers() → clientRequest           | WIRED    | Hook imported at line 11, called at line 855, data consumed in avatar strip          |
| HeroNewbie (HomeScreen.jsx)   | GET /api/v1/client/plans        | useClientPlans() → clientRequest              | WIRED    | Hook imported at line 11, called at line 349, data consumed in chip at lines 551-562 |
| PersonalDataSheet             | GET /client/me                  | useClientMe() → hydration effect              | WIRED    | Hook at line 50, useEffect at lines 74-84 sets all 6 state vars                      |
| PersonalDataSheet             | PATCH /client/me                | useUpdateClientProfile().mutateAsync          | WIRED    | Mutation at line 51, called in onSave at lines 116-122; onSettled invalidates cache  |
| App.jsx TabBar                | unreadChat prop                 | static literal 0                              | WIRED    | `unreadChat={0}` at App.jsx:453; CONVERSATIONS removed                               |

---

### Data-Flow Trace (Level 4)

| Artifact                     | Data Variable      | Source                          | Produces Real Data | Status   |
|------------------------------|--------------------|---------------------------------|--------------------|----------|
| HomeScreen.jsx (HomeNewbie)  | liveTrainers       | useClientTrainers → /api/v1/client/trainers | Yes (DB query in backend router per canonical refs) | FLOWING |
| HomeScreen.jsx (HeroNewbie)  | plans              | useClientPlans → /api/v1/client/plans | Yes (DB query) | FLOWING |
| ProfileExtraSheets.jsx       | meData             | useClientMe → /api/v1/client/me | Yes (DB query)  | FLOWING |
| ProfileExtraSheets.jsx       | updateProfile      | useUpdateClientProfile → PATCH /api/v1/client/me | Yes (DB write + onSettled invalidation) | FLOWING (persistence requires browser confirm) |

---

### Behavioral Spot-Checks

| Behavior                                       | Command                                                                                                                  | Result            | Status |
|------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------|-------------------|--------|
| TypeScript type-check passes                   | `pnpm exec tsc -b` in apps/client-pwa                                                                                   | exit 0            | PASS   |
| ESLint clean                                   | `pnpm lint` in apps/client-pwa                                                                                           | exit 0            | PASS   |
| Full test suite                                | `pnpm exec vitest run` in apps/client-pwa                                                                               | 77/77 pass, 13 files | PASS |
| Vite production build                          | `pnpm build` in apps/client-pwa                                                                                          | exit 0, 55.97 kB HomeScreen | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description                                                        | Status     | Evidence                                                  |
|-------------|------------|---------------------------------------------------------------------|------------|-----------------------------------------------------------|
| NHOME-01    | 76-01      | Live trainer avatars/initials + overflow counter from /client/trainers | SATISFIED | useClientTrainers wired in HomeNewbie; camelCase fullName; fallback to static |
| NHOME-02    | 76-01      | Plan chip: count + min monthly price from /client/plans             | SATISFIED  | useClientPlans wired in HeroNewbie; camelCase priceKopecks/durationDays; filter guards |
| PDATA-01    | 76-02      | Personal Data sheet reads real name/phone/email/goal/height/weight  | SATISFIED  | useClientMe hydration; no hardcoded placeholders on API-backed fields |
| PDATA-02    | 76-02      | Save calls PATCH /client/me; persists across reload                 | PARTIAL    | Mutation wiring code-verified; persistence across browser reload is human-verify |
| CLEAN-01    | 76-03      | CONVERSATIONS import absent; unreadChat=0; conversations.js deleted | SATISFIED  | All three conditions confirmed by grep + file-existence check |

---

### Anti-Patterns Found

| File                                              | Line  | Pattern                                 | Severity | Impact                                                                         |
|---------------------------------------------------|-------|-----------------------------------------|----------|--------------------------------------------------------------------------------|
| `apps/client-pwa/src/screens/HomeScreen.jsx`      | 1016-1017 | Hardcoded hex `#6ee7c4` / `#ffffff` in trainer avatar strip | INFO (pre-existing + new in 76-01) | Violates CLAUDE.md semantic-token convention (IN-03 from review); does not block function |
| `apps/client-pwa/src/screens/HomeScreen.jsx`      | 108, 153, 165, 173 | Hardcoded hex `#10b981`, `#f43f5e`      | INFO (pre-existing) | Same semantic-token convention violation; pre-dates Phase 76                   |
| `apps/client-pwa/src/screens/HomeScreen.jsx`      | ~842  | `badge` destructured but unused in HomeNewbie | INFO (pre-existing) | Dead data flow (IN-01 from review); no functional impact                       |
| `apps/client-pwa/src/App.jsx`                     | ~226, 310 | `setPendingChat('c2')` stale stub from deleted conversations mock | INFO (pre-existing) | Dead state writes; IN-02 from review; harmless since ChatScreen ignores it     |

No TBD/FIXME/XXX debt markers found in any phase-modified file.

---

### Human Verification Required

#### 1. PDATA-02: Save persists across full page reload

**Test:** Start backend + PWA dev server. Log in as seeded client. Navigate to Профиль → Личные данные. Confirm fields show real database values (not "Саша", "sasha@example.com", "168 см", "58 кг", "Поддержание формы" hardcoded strings). Edit «Имя» (e.g. append " 2"), select a different goal pill, change height or weight. Tap «Сохранить». Confirm button shows «Сохранение…» then «Сохранено». Do a full browser refresh. Reopen «Личные данные» — confirm edited values are present.

**Expected:** Edited values persist because PATCH /client/me wrote to Postgres and the onSettled cache invalidation caused a refetch of fresh data.

**Why human:** Requires a running backend + browser. Static analysis confirms the mutation payload shape and cache invalidation wiring are correct, but cannot prove the backend actually persists and returns updated data through a reload cycle.

#### 2. Negative: save failure shows inline error toast

**Test:** Stop the backend. Open «Личные данные», edit a field, tap «Сохранить».

**Expected:** Inline toast "Не удалось сохранить данные. Попробуйте ещё раз." appears; field retains its edited value.

**Why human:** Requires simulating a network failure in a running dev environment.

---

### Gaps Summary

No blocking gaps. All code-verifiable success criteria are confirmed in HEAD:

- CR-01 (BLOCKER in review): Fixed in commit `fa1f4418` — plan chip now reads camelCase `priceKopecks`/`durationDays`; guards against zero-duration, non-finite values, and empty-after-filter.
- CR-02 (BLOCKER in review): Fixed in commit `fa1f4418` — trainer initials now read `tr.fullName` (camelCase wire contract); test fixtures updated from `full_name` to `fullName`.
- Both critical bugs from the code review are resolved and confirmed absent in HEAD.

The remaining human verification items (PDATA-02 live persistence, negative toast test) are inherent to browser-side behavior — they cannot be falsified by grep and are not blocking code defects.

---

_Verified: 2026-06-02T21:50:00Z_
_Verifier: Claude (gsd-verifier)_
