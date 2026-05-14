---
phase: 30-foundations-tech-debt-bedrock
plan: 02
subsystem: rbac-bedrock
tags:
  - rbac
  - backend
  - frontend
  - parity
  - bedrock
  - v1.4
requires:
  - 30-01
provides:
  - backend Resource enum v1.4 members (TRAINERS / PAYMENTS / PT_PACKAGE_PLANS / PT_PACKAGES / PT_SESSIONS)
  - backend OWNER_ONLY frozenset 26-entry locked matrix
  - admin-web Resource union v1.4 string-literals (byte-paritet with backend)
  - admin-web OWNER_ONLY array 26-entry mirror
  - three-way RBAC parity test extended (backend + admin-web)
affects:
  - apps/backend/app/core/permissions.py
  - apps/backend/tests/unit/test_permissions.py
  - apps/admin-web/src/shared/session/can.ts
  - apps/admin-web/src/shared/session/registry.ts
  - apps/admin-web/src/shared/session/can.test.ts
tech-stack:
  added: []
  patterns:
    - "three-way RBAC parity (backend OWNER_ONLY ↔ can.ts OWNER_ONLY ↔ registry.ts Resource union)"
    - "StrEnum kebab-case wire values for multi-word resources"
    - "OWNER_ONLY frozenset spot-check + literal-count + negative spot-check (drift tripwire)"
key-files:
  created: []
  modified:
    - apps/backend/app/core/permissions.py
    - apps/backend/tests/unit/test_permissions.py
    - apps/admin-web/src/shared/session/can.ts
    - apps/admin-web/src/shared/session/registry.ts
    - apps/admin-web/src/shared/session/can.test.ts
decisions:
  - "INFRA-18 (no new Action values) honoured verbatim: '(LIST, TRAINERS)' from REQUIREMENTS.md is expressed semantically via (VIEW, TRAINERS) NOT in OWNER_ONLY — reception's ?active=true picker (TRN-04) passes via existing Action.VIEW. OWNER_ONLY for trainers covers CRUD writes only (CREATE/EDIT/DELETE)."
  - "D-30-09 atomicity: all 5 files committed in one commit (e8beda0). No interleaved partial states — parity test green from first commit."
  - "D-30-10 mock-services scope respected: NO mock-service stubs / routes / sidebar items added for new resources in Phase 30. registry.ts touched ONLY at Resource union (no routeRegistry / navKey changes)."
metrics:
  duration_seconds: 228
  completed_at: "2026-05-14T12:42:49Z"
  tasks_completed: 2
  files_modified: 5
  files_created: 0
  tests_added:
    - "test_reception_retains_v1_4_rights (backend pytest)"
    - "OWNER_ONLY has exactly 26 entries (Phase 30 INFRA-19) (admin-web vitest)"
    - "OWNER_ONLY covers Phase 30 INFRA-19 v1.4 owner-only pairs (admin-web vitest)"
    - "OWNER_ONLY does NOT include reception-retained Phase 30 rights (admin-web vitest)"
---

# Phase 30 Plan 02: RBAC Bedrock (INFRA-18 + INFRA-19) Summary

**One-liner:** RBAC matrix v1.4 расширение — backend Resource StrEnum +5 / OWNER_ONLY frozenset 15→26, admin-web `can.ts`/`registry.ts` зеркальный mirror, three-way parity test зелёный с первого commit (atomic per D-30-09).

## What Was Built

### Backend (`apps/backend/app/core/permissions.py`)

**5 new `Resource` StrEnum members** (Python name → wire `.value`):

| Python name | Wire value | Comment |
|---|---|---|
| `TRAINERS` | `"trainers"` | v1.4 trainers module (Phase 31) |
| `PAYMENTS` | `"payments"` | v1.4 payments ledger (Phase 32) |
| `PT_PACKAGE_PLANS` | `"pt-package-plans"` | kebab — mirrors `MEMBERSHIP_PLANS` convention |
| `PT_PACKAGES` | `"pt-packages"` | kebab — multi-word |
| `PT_SESSIONS` | `"pt-sessions"` | kebab — multi-word |

**`Action` enum: UNCHANGED** — per INFRA-18 verbatim ("No new Action values; reuse existing"). Final Action set: `{view, create, edit, delete, refund, cancel, check_in}`.

**11 new `OWNER_ONLY` entries** (final size 15 → 26):

| # | `(Action, Resource)` | Rationale |
|---|---|---|
| 1 | `(CREATE, TRAINERS)` | Trainer create — owner-only per TRN-02 |
| 2 | `(EDIT, TRAINERS)` | Trainer update — owner-only per TRN-02 |
| 3 | `(DELETE, TRAINERS)` | Trainer hard-delete — owner-only per TRN-02/TRN-05 |
| 4 | `(VIEW, PT_PACKAGE_PLANS)` | PT-plan list — owner-only per PT-02 |
| 5 | `(CREATE, PT_PACKAGE_PLANS)` | PT-plan create — owner-only per PT-02 |
| 6 | `(EDIT, PT_PACKAGE_PLANS)` | PT-plan update — owner-only per PT-02 |
| 7 | `(DELETE, PT_PACKAGE_PLANS)` | PT-plan archive — owner-only per PT-02 |
| 8 | `(VIEW, PAYMENTS)` | Global payments ledger — owner-only per PAY-06 |
| 9 | `(CANCEL, PT_PACKAGES)` | PT-package cancel without refund — owner-only per PT-08 |
| 10 | `(DELETE, PT_PACKAGES)` | PT-package destructive ops — owner-only |
| 11 | `(CANCEL, PT_SESSIONS)` | PT-session cancel — owner-anytime branch per PT-18/B-12 |

**6 reception-retained rights** (NEGATIVE list — NOT in OWNER_ONLY):

| `(Action, Resource)` | Why reception retains |
|---|---|
| `(VIEW, TRAINERS)` | TRN-04 — reception needs `?active=true` picker for PT-session form |
| `(CREATE, PAYMENTS)` | PAY-04 — reception records cash at sale-flow |
| `(REFUND, MEMBERSHIPS)` | B-07 — uniform reception refunds (no 24h owner-approval split) |
| `(CREATE, PT_PACKAGES)` | PT-07 — reception sells PT-packages |
| `(REFUND, PT_PACKAGES)` | B-07 / REF-02 — uniform reception refunds |
| `(CREATE, PT_SESSIONS)` | PT-15 — reception records executed PT-sessions |

### Admin-web

**`registry.ts`** — `Resource` string-literal union extended with 5 new members; `Action` union UNCHANGED; `navKey` and `routeRegistry` UNCHANGED (D-30-09 — routes/sidebar live in Phase 31/35).

**`can.ts`** — `OWNER_ONLY` array extended with 11 new entries (final length 26); set-equality with backend after StrEnum-value normalization.

**`can.test.ts`** — 3 new vitest specs:
1. Length-26 assertion (Phase 30 INFRA-19 drift tripwire).
2. Positive spot-check — 11 new owner-only pairs present.
3. Negative spot-check — 6 reception-retained pairs NOT present.

## Three-Way Parity Test Status

| Asserter | Location | Status |
|---|---|---|
| Backend literal-frozenset (canonical) | `apps/backend/tests/unit/test_permissions.py::test_specific_owner_only_membership` | green |
| Backend length tripwire | `..::test_owner_only_has_exactly_twenty_six_entries` | green |
| Backend Resource value-set | `..::test_resource_value_set` | green |
| Backend reception-retained negative | `..::test_reception_retains_v1_4_rights` (new) | green |
| Admin-web length tripwire | `can.test.ts > OWNER_ONLY has exactly 26 entries (Phase 30 INFRA-19)` (new) | green |
| Admin-web positive spot-check | `..> OWNER_ONLY covers Phase 30 INFRA-19 v1.4 owner-only pairs` (new) | green |
| Admin-web negative spot-check | `..> OWNER_ONLY does NOT include reception-retained Phase 30 rights` (new) | green |

Atomic single-commit landing (D-30-09): commit **`e8beda0`** ships all 5 files together. No interleaved partial states ever existed in git history.

## Why `(VIEW, TRAINERS)` is NOT in OWNER_ONLY

INFRA-19 verbatim says reception retains `(LIST, TRAINERS)` — but INFRA-18 verbatim says "No new Action values". There is no `Action.LIST` in the existing 7-member enum. Per D-30-09 + PATTERNS.md lines 207-209 + Claude's Discretion bullet 3 in CONTEXT.md: the canonical resolution is

- Reception list-picker right is expressed via `Action.VIEW` (semantic "list permission")
- `(VIEW, TRAINERS)` is therefore explicitly NOT in OWNER_ONLY (reception sees `/api/v1/trainers?active=true`)
- Owner-only is CRUD writes only: `CREATE/EDIT/DELETE` against `TRAINERS`

The `test_reception_retains_v1_4_rights` test pins this invariant as a hard assertion against `OWNER_ONLY`.

## Why No `Action.LIST`

INFRA-18 verbatim: *"No new `Action` values (reuse existing `VIEW/CREATE/EDIT/DELETE/REFUND/CANCEL/LIST`)"*. The trailing `LIST` in the REQ text is descriptive prose (catalog of conceptual actions), not an enum-member claim — the existing enum has 7 values without `LIST`, and INFRA-18 also says "no new Action values". The semantic of LIST is expressed via `Action.VIEW`. This interpretation is locked by `test_action_value_set` in `test_permissions.py` (asserts exactly 7 values).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Ruff E501 line-too-long in 2 files**

- **Found during:** Task 1 verify (ruff check)
- **Issue:** Inline comment on `PT_PACKAGE_PLANS = "pt-package-plans"` exceeded 100-char width by 12 chars; test_permissions.py docstring line exceeded by 5 chars.
- **Fix:** Trimmed inline comment ("mirrors MEMBERSHIP_PLANS" instead of "kebab on wire (mirrors MEMBERSHIP_PLANS)"); shortened docstring from "Spot-check the 26 known-locked entries (9 v1.1 + 6 v1.2 INFRA-08 + 11 v1.4 INFRA-19)" → "Spot-check 26 locked entries (v1.1 + v1.2 INFRA-08 + v1.4 INFRA-19)".
- **Files modified:** `permissions.py`, `test_permissions.py`
- **Commit:** included in `e8beda0`

No other deviations — plan executed as written, atomic single-commit landing per D-30-09.

## Acceptance Criteria Verification

### Task 1 (backend)
- `Resource.TRAINERS.value == 'trainers'` (and 4 siblings): verified via smoke `uv run python -c "..."`
- `len(OWNER_ONLY) == 26`: verified
- 6 reception-retained pairs NOT in OWNER_ONLY: verified
- `Action` enum value-set unchanged (7 members): verified
- `pytest tests/unit/test_permissions.py -q`: **175 passed**
- `ruff check`: clean
- `mypy --strict`: clean

### Task 2 (admin-web)
- registry.ts grep for `'trainers'` / `'pt-package-plans'` / `'pt-sessions'`: each ≥1
- can.ts grep for `action: 'create', resource: 'trainers'` / `action: 'cancel', resource: 'pt-sessions'`: each ≥1
- can.test.ts grep for `view:trainers` (negative spot-check): ≥1
- can.ts OWNER_ONLY entry count: 27 grep matches (1 type signature + 26 entries) — criterion ≥26 met
- `vitest run src/shared/session/can.test.ts`: 9/9 passed (3 new + 6 existing)
- `pnpm typecheck`: clean
- `pnpm lint`: clean (only 2 pre-existing warnings in unrelated files: `.codex/get-shit-done/bin/lib/state.cjs` and `data-grid-table-virtual.tsx`)
- `pnpm vitest run` (full suite): **41 files / 238 tests passed**

## Files Modified

| Path | Change |
|---|---|
| `apps/backend/app/core/permissions.py` | Resource StrEnum +5; OWNER_ONLY frozenset 15 → 26; docstring comment refresh |
| `apps/backend/tests/unit/test_permissions.py` | Test renamed (`fifteen` → `twenty_six`); 3 tests extended; 1 new test (`test_reception_retains_v1_4_rights`) |
| `apps/admin-web/src/shared/session/registry.ts` | Resource union +5 literals (Action union, navKey, routeRegistry UNCHANGED) |
| `apps/admin-web/src/shared/session/can.ts` | OWNER_ONLY array +11 entries (final length 26) |
| `apps/admin-web/src/shared/session/can.test.ts` | 3 new vitest specs (length + positive + negative spot-check) |

## Authentication Gates

None — pure code-and-test changes; no external services touched.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries introduced. RBAC matrix extension stays within the existing trust boundary (HTTP request → backend `permissions.can()` and UI action → admin-web `can()`). All 5 threats from the plan's `<threat_model>` (T-30-02-01..05) have explicit test mitigations — see acceptance verification above.

## Self-Check: PASSED

- File `apps/backend/app/core/permissions.py`: FOUND (modified, contains `TRAINERS = "trainers"`)
- File `apps/backend/tests/unit/test_permissions.py`: FOUND (modified, contains `twenty_six`)
- File `apps/admin-web/src/shared/session/can.ts`: FOUND (modified, contains 26 owner-only entries)
- File `apps/admin-web/src/shared/session/registry.ts`: FOUND (modified, contains `'pt-sessions'`)
- File `apps/admin-web/src/shared/session/can.test.ts`: FOUND (modified, contains negative spot-check)
- Commit `e8beda0`: FOUND in git log (atomic 5-file commit per D-30-09)
- Backend tests: 175 passed (verified)
- Admin-web tests: 238 passed across 41 files (verified)
