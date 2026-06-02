---
phase: 76-pwa-wiring-cleanup
plan: "02"
subsystem: client-pwa
tags: [pwa, profile, personal-data, react-query, mutation, form, enum]
dependency_graph:
  requires: []
  provides: [PDATA-01, PDATA-02]
  affects:
    - apps/client-pwa/src/screens/sheets/ProfileExtraSheets.jsx
tech_stack:
  added: []
  patterns:
    - useClientMe() read hydration via useEffect keyed on meData
    - useUpdateClientProfile().mutateAsync in try/catch for save
    - Local in-sheet error toast (inline styles, no global Sonner)
    - 4-value server-enforced enum rendered as pill selector
key_files:
  created:
    - apps/client-pwa/src/screens/sheets/PersonalDataSheet.identity.test.jsx
  modified:
    - apps/client-pwa/src/screens/sheets/ProfileExtraSheets.jsx
decisions:
  - "D-76-11 honoured: DOB/Gender local-only fields labelled 'Только на устройстве', not sent in PATCH"
  - "T-76-05 mitigated: goal constrained to 4-value enum via pill selector — free-text input removed"
  - "D-76-12: height/weight changed from read-only display to editable numeric FormRows"
  - "Email verified writable via PATCH per D-76-12 — initialEmail ref removed"
  - "In-sheet toast uses inline styles with var(--danger)/var(--danger-soft) per UI-SPEC (no .co-toast class)"
metrics:
  duration: "~15 min"
  completed: "2026-06-02T18:27:00Z"
  tasks_completed: 2
  files_changed: 2
  requirements_satisfied: [PDATA-01, PDATA-02]
---

# Phase 76 Plan 02: PersonalDataSheet API Wiring Summary

**One-liner:** PersonalDataSheet wired to GET/PATCH /client/me — real name/email/goal/height/weight with segmented enum goal control, save-button state cycle, and inline error toast.

## What Was Built

`PersonalDataSheet` in `apps/client-pwa/src/screens/sheets/ProfileExtraSheets.jsx` now:

1. **Reads** real profile data from `useClientMe()` — `firstName`, `phone`, `email`, `goal`, `heightCm`, `weightKg` — hydrated via `React.useEffect([meData])` so the sheet shows blank/empty fields while loading and populated values once data arrives (PDATA-01).

2. **Writes** editable fields via `useUpdateClientProfile().mutateAsync` — sends `firstName`, `email`, `goal`, `heightCm`, `weightKg` to `PATCH /client/me`. Cache is invalidated via `onSettled` in the mutation hook, so the change persists across full-page reload (PDATA-02).

3. **Goal field** replaced from free-text `FormRow` (which would HTTP 400) to a 4-pill segmented control over `{lose_weight, gain_mass, tone, maintain}` mapped to Russian labels — T-76-05 threat mitigated.

4. **Save button** cycles through four states: Сохранить → Сохранение… (disabled, `cursor: not-allowed`) → Сохранено (accent-deep, reverts after 1400ms) → back to Сохранить on error.

5. **Inline error toast** with `var(--danger)` border + icon + `var(--danger-soft)` background, CSS transition from off-screen (translateY 180%) to visible on error. Copy: `"Не удалось сохранить данные. Попробуйте ещё раз."`.

6. **DOB/Gender** remain local-only interactive state; section header carries `"Только на устройстве"` muted `.t-mini` label (D-76-11).

7. **Phone** is read-only (`onChange={() => {}}`) sourced from `meData?.phone`.

## Tasks

| # | Name | Commit | Type |
|---|------|--------|------|
| T1-RED | Tests: PersonalDataSheet hydration + save | `2047406b` | test |
| T1+T2-GREEN | Wire PersonalDataSheet to GET/PATCH /client/me | `a496839d` | feat |
| T3 | Verify save persists across reload | human-verify | checkpoint |

## TDD Gate Compliance

- **RED commit:** `2047406b` — 11 failing tests covering hydration (Task 1) + save/enum/toast/button-state (Task 2)
- **GREEN commit:** `a496839d` — all 11 tests pass + full suite 77/77

## Automated Verification Results

| Gate | Result |
|------|--------|
| `pnpm exec tsc -b` | Pass (exit 0) |
| `pnpm exec vitest run` (77 tests) | Pass — 13 files, 77 tests |
| `pnpm lint` | Pass (exit 0, JSX screens intentionally ESLint-ignored per D-69-06) |
| `pnpm build` | Pass — `ProfileExtraSheets-DxwSEeCw.js` 20.68 kB gzip 6.11 kB |
| `grep -q "useClientMe"` | Pass |
| `grep -q "Только на устройстве"` | Pass |
| `! grep -q "'Саша'"` | Pass |
| `! grep -q "sasha@example.com"` | Pass |
| `grep -q "mutateAsync"` | Pass |
| `grep -q "Сохранение…"` | Pass |
| `grep -Eq "lose_weight\|gain_mass\|tone\|maintain"` | Pass |
| `grep -q "isPending"` | Pass |

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written, with one spec correction applied as documented:

**1. [Spec Correction — T-76-05] Goal implemented as pill selector, not free-text FormRow**
- **Source:** Plan `<interfaces>` CONSTRAINT and threat model T-76-05
- **Issue:** UI-SPEC §Field contract listed "free text `<input>`" for goal, but backend returns HTTP 400 `invalid_goal` for any value outside the 4-value enum
- **Fix:** Replaced `FormRow` for goal with a 4-pill segmented control mapping enum keys to Russian labels
- **Files modified:** `ProfileExtraSheets.jsx`
- **Commit:** `a496839d`

**2. [Rule 1 - Bug] Removed duplicate `border` key in ContactTile style object**
- **Found during:** Build warning inspection
- **Issue:** Pre-existing `ContactTile` had `border: 0` and `border: '0.5px solid var(--border)'` as two separate keys in same style object
- **Fix:** Merged to single `border: '0.5px solid var(--border)'`
- **Files modified:** `ProfileExtraSheets.jsx`
- **Commit:** `a496839d` (included in same implementation commit)

## Human Verification Required

**Task 3 checkpoint — pending human verification.**

The following manual steps are required against a running PWA + backend:

1. Start the backend (`docker compose up` or `uv run uvicorn`) and the PWA dev server (`pnpm --filter client-pwa dev`)
2. Log in as the seeded client (dev login flow)
3. Navigate to **Профиль → Личные данные**
4. Confirm fields show real values from the database — NOT `"Саша"`, `"sasha@example.com"`, `"168 см"`, `"58 кг"`, `"Поддержание формы"`
5. Edit «Имя» (e.g. append " 2"), select a different goal pill, change height or weight
6. Tap «Сохранить» — confirm button shows «Сохранение…» then «Сохранено»
7. Do a **full page reload** (browser refresh, not just closing the sheet)
8. Reopen «Личные данные» — confirm the edited values persisted (PDATA-02 criterion)
9. (Optional negative) Stop the backend, edit + save — confirm toast `"Не удалось сохранить данные. Попробуйте ещё раз."` appears and field keeps its value

**Resume signal:** Type "approved" or describe what did not persist / render correctly.

## Known Stubs

None — all fields are wired to real API data. DOB/Gender are intentionally local-only (D-76-11, no backend column) — not stubs.

## Threat Flags

No new security surface beyond what the plan's threat model covers. PATCH /client/me is scoped to the authenticated client session (no client-controlled ID in the payload).

## Self-Check: PASSED

- FOUND: `apps/client-pwa/src/screens/sheets/ProfileExtraSheets.jsx`
- FOUND: `apps/client-pwa/src/screens/sheets/PersonalDataSheet.identity.test.jsx`
- FOUND commit `2047406b` (RED: test)
- FOUND commit `a496839d` (GREEN: implementation)
