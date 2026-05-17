---
phase: 38-schedule-module-booking-core
addendum_to: 38-VERIFICATION.md
resolved: 2026-05-17
status: gaps_closed
resolution: implementation_aligned_to_locked_contracts
post_fix_test_count: 1247 passed
gaps_closed:
  - id: gap_1_slot_cancel_verb
    truth: "Slot cancel uses PATCH /api/v1/trainer-slots/{id}/cancel per REQUIREMENTS SLOT-02 / SLOT-07 + ROADMAP Phase 38 SC #2"
    resolution_commit: f1f1021
    one_line_diff: "@schedule_router.post → @schedule_router.patch on /{slot_id}/cancel; docstrings + cascade-test http call swapped POST → PATCH"
    files_touched:
      - apps/backend/app/modules/schedule/router.py
      - apps/backend/app/modules/schedule/schemas.py
      - apps/backend/tests/integration/schedule/test_slot_cancel_cascade.py
  - id: gap_2_per_client_bookings_url
    truth: "Per-client bookings endpoint is mounted at GET /api/v1/clients/{id}/bookings per REQUIREMENTS BOOK-08 + ROADMAP Phase 38 SC #5"
    resolution_commit: b6f235a
    new_router_pattern: client_scoped_bookings_router
    precedent_followed: pt_sessions_package_scoped_router (apps/backend/app/api/v1/router.py:50)
    files_touched:
      - apps/backend/app/api/v1/router.py
      - apps/backend/app/modules/bookings/router.py
      - apps/backend/app/modules/bookings/service.py
      - apps/backend/tests/integration/bookings/test_bookings_list.py
gates_post_fix:
  - "tests/integration/{schedule,bookings}/: 69 passed"
  - "full suite tests/: 1247 passed (zero regressions vs the pre-fix baseline)"
  - "ruff check app/modules/{schedule,bookings} app/api: clean"
  - "mypy --strict app/modules/{schedule,bookings} app/api: success, 20 source files"
  - "lint-imports: 3 contracts kept, 0 broken"
modules_independent_invariant: "Preserved — grep -c 'from app.modules.bookings' apps/backend/app/modules/clients/router.py → 0"
---

# Phase 38 Verification Addendum — Gap Closures

This addendum records the resolution of the two URL/verb contract gaps
surfaced by `38-VERIFICATION.md` (status: `gaps_found`). Both gaps were
closed by aligning the implementation to the REQUIREMENTS-locked
contracts (Option (a) from the verifier's recommendation block) rather
than amending the spec. No D-38-NN entries are needed because the
implementation now matches the spec verbatim.

## Gap #1 — Slot cancel verb POST → PATCH

**Resolution commit:** `f1f1021`

**One-line diff summary:** `@schedule_router.post("/{slot_id}/cancel", ...)`
→ `@schedule_router.patch("/{slot_id}/cancel", ...)`. Module-level docstring
and `SlotCancelRequest` schema docstring updated from "POST" to "PATCH"; the
end-to-end `test_http_cancel_inconsistent_slot_returns_500_json` test now
issues `authed_client_owner.patch(...)` instead of `.post(...)`. All other
attributes of the endpoint (status_code=200, dependency stack, body schema,
response model, idempotency replay) are unchanged.

**Files touched:**
- `apps/backend/app/modules/schedule/router.py`
- `apps/backend/app/modules/schedule/schemas.py`
- `apps/backend/tests/integration/schedule/test_slot_cancel_cascade.py`

**Post-fix gate:** `tests/integration/schedule/` 30 passed.

## Gap #2 — Per-client bookings URL re-rooted to /api/v1/clients/{id}/bookings

**Resolution commit:** `b6f235a`

**New router pattern:** `client_scoped_bookings_router` (a second
`APIRouter()` declared inside `apps/backend/app/modules/bookings/router.py`
next to `bookings_router`). The per-client list handler is moved off
`bookings_router` (where it was declared at `/clients/{client_id}/bookings`,
yielding the wrong public URL because `bookings_router` is mounted at
`/bookings`) and onto `client_scoped_bookings_router` at the internal path
`/{client_id}/bookings`. The v1 composition root then mounts the new router
with `prefix="/clients"`, producing the BOOK-08 contract URL
`GET /api/v1/clients/{client_id}/bookings`.

**Precedent followed:** Identical composition pattern to the v1.4
`pt_sessions_package_scoped_router` already in
`apps/backend/app/api/v1/router.py:50` — a second APIRouter declared in the
implementing module and composed by the v1 router at a different prefix.

**Architectural invariant preserved:** `clients/router.py` retains zero
`from app.modules.bookings` imports — the bookings → clients composition
edge lives exclusively in `app.api.v1.router`. `lint-imports` confirms 3
contracts kept, 0 broken; the `modules cannot import each other` rule
remains intact.

**Files touched:**
- `apps/backend/app/api/v1/router.py`
- `apps/backend/app/modules/bookings/router.py`
- `apps/backend/app/modules/bookings/service.py`
- `apps/backend/tests/integration/bookings/test_bookings_list.py`

**Post-fix gate:** `tests/integration/bookings/` (plus schedule) 69 passed.

## Combined Gate Outcomes (Post-Fix)

| Gate                                                                 | Result |
|----------------------------------------------------------------------|--------|
| `tests/integration/{schedule,bookings}/`                             | 69 passed |
| Full backend suite (`tests/`)                                        | 1247 passed (matches pre-fix baseline — zero regressions) |
| `ruff check app/modules/{schedule,bookings} app/api`                 | clean |
| `mypy --strict app/modules/{schedule,bookings} app/api`              | Success: no issues found in 20 source files |
| `lint-imports`                                                       | 3 contracts kept, 0 broken |
| `grep -c "from app.modules.bookings" clients/router.py`              | 0 (dep-leaf invariant) |
| `grep -c '@schedule_router.patch' schedule/router.py`                | 1 (verb fixed) |
| `grep -c 'client_scoped_bookings_router' bookings/router.py`         | 3 (declaration + 2 references) |
| `grep -c 'client_scoped_bookings_router' app/api/v1/router.py`       | 3 (import + 1 mount block + 1 reference) |

## Updated Verifier Score

The original `38-VERIFICATION.md` scored 4/6 must-haves verified with two
PARTIAL FAIL rows (SC #2, SC #5). With this addendum:

| # | Success Criterion | Status |
|---|------|--------|
| 2 | PATCH `/api/v1/trainer-slots/{id}/cancel` cascade | VERIFIED (was PARTIAL FAIL) |
| 5 | `GET /api/v1/clients/{id}/bookings` paginated envelope | VERIFIED (was PARTIAL FAIL) |

All 5 ROADMAP Success Criteria and all 25 REQ-IDs (SLOT-02, SLOT-07,
BOOK-08 included) are now SATISFIED. Phase 40 HANDOFF-01 byte-stable
OpenAPI regen can proceed against the locked contracts without further
amendment.

---

_Addendum recorded: 2026-05-17_
_Resolution by: Claude (gsd-executor, sequential gap-closure run)_
