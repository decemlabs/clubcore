---
phase: 02-backend-skeleton-with-quality-tooling
plan: 04
subsystem: backend
tags: [backend, modules, placeholders, import-linter, python]

requires:
  - phase: 02-backend-skeleton-with-quality-tooling
    plan: 02
    provides: "apps/backend/.venv with fastapi importable (APIRouter for auth/router.py)"
provides:
  - "app.modules namespace package (MOD-01, MOD-02)"
  - "app.modules.auth subtree: __init__.py + router.py (empty APIRouter) + service.py + models.py + schemas.py"
  - "app.modules.{members, memberships, visits, trainers, schedule, bookings, billing, notifications} as docstring-only __init__.py packages"
  - "Stable import target `app.modules.auth.router.router` for Plan 06's commented-out include in app/api/v1/router.py (D-02)"
affects:
  - "Plan 02-06 (app/api/v1/router.py may reference app.modules.auth.router — kept commented per D-02)"
  - "Plan 02-08 (import-linter independence contract has 9 real packages to enforce against)"

tech-stack:
  added: []
  patterns:
    - "Docstring-only __init__.py for placeholder modules — sufficient for grimp graph builder (RESEARCH.md Pitfall 5) and avoids `# noqa F401` re-import dance"
    - "Empty APIRouter with no endpoints as the load-bearing export from auth/router.py (MOD-01, D-02)"
    - "Single-line module docstring for the 8 non-auth modules; multi-line for auth subfiles where TODO context is richer"

key-files:
  created:
    - "apps/backend/app/modules/__init__.py (modules namespace docstring)"
    - "apps/backend/app/modules/auth/__init__.py (auth package docstring)"
    - "apps/backend/app/modules/auth/router.py (APIRouter() instance, no endpoints)"
    - "apps/backend/app/modules/auth/service.py (docstring-only Phase C+ placeholder)"
    - "apps/backend/app/modules/auth/models.py (docstring-only Phase C+ placeholder; NO User/RefreshToken)"
    - "apps/backend/app/modules/auth/schemas.py (docstring-only Phase C+ placeholder)"
    - "apps/backend/app/modules/members/__init__.py (docstring-only)"
    - "apps/backend/app/modules/memberships/__init__.py (docstring-only)"
    - "apps/backend/app/modules/visits/__init__.py (docstring-only)"
    - "apps/backend/app/modules/trainers/__init__.py (docstring-only)"
    - "apps/backend/app/modules/schedule/__init__.py (docstring-only)"
    - "apps/backend/app/modules/bookings/__init__.py (docstring-only)"
    - "apps/backend/app/modules/billing/__init__.py (docstring-only; mentions ЮKassa + Stripe-forbidden RU)"
    - "apps/backend/app/modules/notifications/__init__.py (docstring-only)"
  modified: []
  deleted: []

key-decisions:
  - "Used docstring-only __init__.py over `# noqa F401` re-imports — RESEARCH.md Pitfall 5 documents both options; docstring is simpler, satisfies MOD-02 'empty of business logic', and grimp registers the package from the docstring AST node."
  - "Reformatted billing/__init__.py docstring to multi-line — original single-line spec from PLAN was 104 chars and tripped ruff E501 (line-length=100). Split to multi-line preserves both `TODO Phase B+` token and the `ЮKassa integration (Stripe forbidden in RU)` content required by acceptance criteria."

requirements-completed: [MOD-01, MOD-02]

duration: ~1m 24s
completed: 2026-04-30
---

# Phase 2 Plan 04: Module Placeholder Packages Summary

**Created the full `app.modules.*` namespace (14 files): the auth subtree with an empty APIRouter export and three docstring-only stubs (service/models/schemas), plus 8 single-line docstring placeholders for members/memberships/visits/trainers/schedule/bookings/billing/notifications — locking in the modular monolith's vertical-slice boundaries before any business code lands, so import-linter's independence contract has real packages to enforce against from day one.**

## Performance

- **Duration:** ~1m 24s
- **Started:** 2026-04-30T19:43:50Z
- **Completed:** 2026-04-30T19:45:14Z
- **Tasks:** 2
- **Files created:** 14
- **Quality-gate iterations:** 1 (ruff E501 fix on billing/__init__.py — multi-line reformat)

## Accomplishments

- Created `apps/backend/app/modules/__init__.py` with a multi-line docstring identifying it as the business-modules namespace and pointing to import-linter's `modules-independent` contract (MOD-03 enforcement target).
- Created the auth subtree per MOD-01: `auth/__init__.py` (package docstring), `auth/router.py` exposing the load-bearing `router = APIRouter()` symbol, and three docstring-only siblings `auth/service.py`, `auth/models.py`, `auth/schemas.py`. The `auth/router.py` file deliberately has no `@router.get/post` decorators (Phase A scope) — Phase C+ will add `/login`, `/refresh`, `/logout`.
- `auth/models.py` carries the explicit guard text `NO models in Phase A` per CONTEXT.md and REQUIREMENTS MOD-01 — future planners reading the file get the constraint inline.
- Created the 8 remaining module placeholders (members, memberships, visits, trainers, schedule, bookings, billing, notifications), each as a single-line docstring `__init__.py`. `billing/__init__.py` carries the regional-constraint reminder `ЮKassa integration (Stripe forbidden in RU)` per CLAUDE.md.
- Verified zero cross-module imports under `apps/backend/app/modules/` (the only `from app.modules.` token in the tree is inside `auth/router.py`'s docstring, which is text, not an import).
- All 14 files pass `uv run ruff check`, `uv run ruff format --check`, and `uv run mypy app` (now reports `Success: no issues found in 24 source files` — was 16 after Plan 03).

## Task Commits

1. **Task 1: Create modules namespace + auth subtree (6 files)** — `5e363a6` (feat)
2. **Task 2: Create 8 remaining module __init__.py placeholders** — `79b9355` (feat)

**Plan metadata commit:** _to follow this SUMMARY (docs)_

## Quality Gate Results

| Gate | Command | Result |
|------|---------|--------|
| Smoke import (auth + router) | `uv run python -c "from app.modules.auth.router import router; ..."` | OK (`type(router).__name__ == 'APIRouter'`) |
| Smoke import (8 modules) | `uv run python -c "from app.modules import members, ..."` | OK |
| Plan-level smoke | `uv run python -c "import app.modules.auth, ..."` | PLAN-VERIFY OK |
| Ruff lint | `uv run ruff check app/modules/` | All checks passed (after E501 fix) |
| Ruff format | `uv run ruff format --check app/modules/` | 14 files already formatted |
| mypy strict + pydantic plugin | `uv run mypy app` | Success: no issues found in 24 source files |
| Spec-grep: no `@router.` decorators in auth/router.py | `grep -E '^@router\.' auth/router.py` | (none) — empty router confirmed |
| Spec-grep: no def/class in service/models/schemas.py | `grep -lE '^(def \|class )' auth/{service,models,schemas}.py` | (none) — docstring-only confirmed |
| Spec-grep: no imports in 8 module __init__.py | `grep -lE '^import \|^from ' members/... notifications/__init__.py` | (none) |
| Spec-grep: no def/class in 8 module __init__.py | `grep -lE '^(def \|class )' members/... notifications/__init__.py` | (none) |
| Spec-grep: cross-module independence preflight | `grep -rE '^from app\.modules\.[a-z]+' app/modules/ \| grep -v auth/` | (none) — no cross-module imports |
| Spec-grep: TODO tokens present | `TODO Phase C+` x3 (auth siblings) + `TODO Phase B+` x8 (other modules) | All 11 markers verified |
| Spec-grep: regional reminder | `grep -E 'ЮKassa\|Stripe' billing/__init__.py` | Match (multi-line docstring) |

All plan-level `<verification>` block commands pass:
- 14 files exist — VERIFIED
- `import app.modules.auth, app.modules.members, ...; from app.modules.auth.router import router` exits 0 — VERIFIED
- `grep -rE 'from app\.modules\.' apps/backend/app/modules/` returns only the docstring-text reference inside `auth/router.py` (not an import statement) — VERIFIED

All acceptance criteria from both tasks satisfied (16 total checks across the two `<acceptance_criteria>` blocks).

## Decisions Made

- **Docstring-only __init__.py over `# noqa F401` re-imports** — RESEARCH.md Pitfall 5 left this open ("the safer pattern is an empty file [for graph compat], …for Phase A where only auth has any code at all, the pragmatic approach below uses docstrings"). Plan 04's `<interfaces>` block locked the docstring approach. Honored verbatim: simpler, no noqa pragmas, satisfies MOD-02's "empty of business logic" literally — Python's AST still parses the module docstring as a top-level expression, which grimp uses to register the package node.
- **Multi-line docstring for billing/__init__.py** — Plan-spec wrote it as a single line: `"""Billing module placeholder. TODO Phase B+: invoices + ЮKassa integration (Stripe forbidden in RU)."""`. That's 104 chars; ruff E501 (line-length=100, locked in 02-01's `ruff.toml`) rejected it. Reformatted to a 4-line docstring preserving both required tokens (`TODO Phase B+` + `ЮKassa`/`Stripe forbidden in RU`). The literal `TODO Phase B+` token check from acceptance criteria still passes.
- **`router = APIRouter()` sits at module top level (not lazy-built)** — Plan 06's wiring will import the symbol with `from app.modules.auth.router import router`, which only works if `router` is a module-level attribute. No type annotation needed: APIRouter is fully typed by FastAPI's stubs.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Linter] Multi-line reformat of `billing/__init__.py` docstring**
- **Found during:** Task 2, ruff check
- **Issue:** `uv run ruff check app/modules/` exited 1 with `E501 Line too long (104 > 100)` on `app/modules/billing/__init__.py:1`. Plan-spec text was a single-line 104-char docstring.
- **Fix:** Split to a 4-line docstring; both `TODO Phase B+` and `ЮKassa integration (Stripe forbidden in RU)` content preserved, satisfying the acceptance criteria token checks (`grep -c 'TODO Phase B+' billing/__init__.py` = 1; `grep -E 'ЮKassa|Stripe' billing/__init__.py` matches).
- **Files modified:** `apps/backend/app/modules/billing/__init__.py`
- **Commit:** `79b9355` (folded into Task 2's single commit since the fix happened before commit)

This is a linter-driven formatting fix, not a behavior change — the placeholder still carries the same Phase B+ deferral marker and the Stripe-forbidden regional reminder.

## Issues Encountered

None beyond the single E501 fix above. No FastAPI/Pydantic/SQLAlchemy surprises (only auth/router.py imports `APIRouter`; everything else is docstring-only).

## User Setup Required

None. All work is code-only inside `apps/backend/app/modules/`. No env vars, no migrations, no service config.

## Threat Surface Scan

Plan-04 introduces no runtime trust boundaries — all 14 files are placeholders with zero executable logic (the auth `APIRouter()` instance has no endpoints registered). T-02-10 (Tampering: future module imports could violate independence contract silently) is **mitigated** as planned: import-linter's `modules-independent` contract from Plan 01 covers this, and Plan 08 will run `lint-imports` against this real namespace. No new security-relevant surface.

## Next Phase Readiness

- **Plan 02-05** can land `app/integrations/*` without colliding with module imports.
- **Plan 02-06** can wire `from app.modules.auth.router import router` into `app/api/v1/router.py` (commented out per D-02).
- **Plan 02-08** has a real 9-package `app.modules.*` namespace for `lint-imports` to validate the independence contract against — preflight already confirms zero cross-module imports.

## Self-Check

Verifying claims before final commit:

**Created files (all 14):**
- `apps/backend/app/modules/__init__.py` — FOUND
- `apps/backend/app/modules/auth/__init__.py` — FOUND
- `apps/backend/app/modules/auth/router.py` — FOUND
- `apps/backend/app/modules/auth/service.py` — FOUND
- `apps/backend/app/modules/auth/models.py` — FOUND
- `apps/backend/app/modules/auth/schemas.py` — FOUND
- `apps/backend/app/modules/members/__init__.py` — FOUND
- `apps/backend/app/modules/memberships/__init__.py` — FOUND
- `apps/backend/app/modules/visits/__init__.py` — FOUND
- `apps/backend/app/modules/trainers/__init__.py` — FOUND
- `apps/backend/app/modules/schedule/__init__.py` — FOUND
- `apps/backend/app/modules/bookings/__init__.py` — FOUND
- `apps/backend/app/modules/billing/__init__.py` — FOUND
- `apps/backend/app/modules/notifications/__init__.py` — FOUND

**Commits:**
- `5e363a6` (Task 1 — modules namespace + auth subtree)
- `79b9355` (Task 2 — 8 module placeholders, billing E501 fix folded in)

**Quality gates:**
- `uv run ruff check app/modules/` — exit 0, "All checks passed!"
- `uv run ruff format --check app/modules/` — exit 0, "14 files already formatted"
- `uv run mypy app` — exit 0, "Success: no issues found in 24 source files"
- Spec-grep: no `@router.` decorators in auth/router.py — VERIFIED (none)
- Spec-grep: no def/class in auth/{service,models,schemas}.py — VERIFIED (none)
- Spec-grep: no imports in 8 module __init__.py — VERIFIED (none)
- Spec-grep: cross-module independence preflight — VERIFIED (only the auth/router.py docstring text matches `from app.modules.auth.router`)

## Self-Check: PASSED

---

*Phase: 02-backend-skeleton-with-quality-tooling*
*Completed: 2026-04-30*
