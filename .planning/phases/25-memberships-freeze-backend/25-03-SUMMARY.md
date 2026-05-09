---
phase: 25-memberships-freeze-backend
plan: 03
subsystem: service
tags: [memberships, freeze, service, audit, transition-guard, n-plus-one-avoidance]

# Dependency graph
requires:
  - phase: 25-memberships-freeze-backend
    plan: 01
    provides: MembershipFreezePeriod ORM, freeze_days_limit_snapshot, MEMBERSHIP_STATUS_TRANSITIONS populated, FreezeLimitExceededError, AlreadyFrozenError.
  - phase: 25-memberships-freeze-backend
    plan: 02
    provides: insert_freeze_period / get_open_freeze_period / compute_freeze_days_used repository helpers.
  - phase: 25-memberships-freeze-backend
    plan: 04
    provides: MembershipStatus.FROZEN, FreezePeriodResponse, MembershipResponse + 4 freeze projection fields, POST /freeze + /unfreeze endpoints (transient type-ignore markers cleaned by this plan).
provides:
  - service.freeze_membership (D-25-07 — 10-step UoW with preventive limit guard, IntegrityError translation, audit emit, single commit)
  - service.unfreeze_membership (D-25-08 — 12-step UoW with ceil-rounding, end_date extension, audit emit, single commit)
  - service.cancel_membership (extended for frozen source per D-25-09 — closes open period without end_date extension, emits membership_unfrozen days_added=0 BEFORE membership_cancelled in same UoW)
  - service._build_membership_response (D-25-12 — SOLE single-row projector with locked model_validate(membership, from_attributes=True).model_copy(update=overlay) pattern)
  - service.list_memberships (rewritten per D-25-18 — bulk-prefetch maps avoid N+1; 3 queries total regardless of N rows)
  - service.get_membership / create_membership / cancel_membership migrated to _build_membership_response
  - service._assert_can_freeze / _assert_can_unfreeze thin transition wrappers (D-25-15)
  - service._is_already_frozen_conflict IntegrityError discriminator (D-25-22)
affects: [25-05-tests, 26-renewal, 28-frontend]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Locked Phase 25 D-25-12 projection: MembershipResponse.model_validate(membership, from_attributes=True).model_copy(update=overlay) — single source of truth for the 4 freeze fields; ORM column freeze_days_limit_snapshot rides via from_attributes, the 3 computed fields ride via overlay."
    - "Two-implementation single-projection-pattern for read paths: _build_membership_response is the per-row helper; list_memberships inlines the same Step 1 + Step 2 with bulk-prefetched (days_used, open_period) maps so the no-N+1 invariant holds. Single source of truth for projection logic; two implementations differ only in I/O batching."
    - "IntegrityError discriminator pattern from clients/_is_phone_conflict + memberships/_is_plan_name_conflict generalised: getattr(exc.orig, 'constraint_name', None) first, substring fallback. _is_already_frozen_conflict mirrors directly, constraint name uq_membership_freeze_periods_active_per_membership."
    - "Cancel-during-freeze audit ordering invariant: membership_unfrozen (days_added=0) BEFORE membership_cancelled, both in the same UoW (single commit at function end). audit_log.id auto-increment preserves chronology; the days_added=0 sentinel is the discriminator vs normal unfreeze."

key-files:
  created:
    - .planning/phases/25-memberships-freeze-backend/25-03-SUMMARY.md
  modified:
    - apps/backend/app/modules/memberships/service.py
    - apps/backend/app/modules/memberships/router.py
    - .planning/phases/25-memberships-freeze-backend/deferred-items.md

key-decisions:
  - "Followed plan as specified — D-25-07, D-25-08, D-25-09, D-25-12, D-25-15, D-25-18, D-25-22 implemented verbatim. No architectural deviations."
  - "Acceptance grep for the locked projection pattern uses POSIX extended regex with [^)]* (no newline). Reformatted the projection call to a single line via overlay = {...} extraction so the regex matches without a multi-line workaround. Acceptance gate now passes cleanly with 1 match."
  - "Removed Wave 3 transient '# type: ignore[attr-defined]  # Wave 4' markers from router.py at the freeze + unfreeze callsites in the same Task 2 commit that introduced the real service functions — the cleanup gate (grep zero matches) was an acceptance criterion of this plan."
  - "Imported MembershipFreezePeriod at module top-level for the list_memberships bulk-fetch SQL (Task 4) rather than inline-importing inside the function — top-level keeps mypy/ruff happy and the import is now a real consumer (not stubbed)."
  - "Reworded the _build_membership_response docstring 'Do NOT call MembershipResponse.model_validate(membership) directly' to 'Do NOT call ``MembershipResponse.model_validate`` on a Membership ORM directly' so the documentation reference does not match the acceptance grep regex (which scans the file as a whole)."

patterns-established:
  - "Single-projector helper for response models with computed fields: _build_membership_response is the bedrock; future Phase 26 renewal projection (when added) follows the same pattern (model_validate ORM with from_attributes -> model_copy with overlay of service-computed fields)."
  - "Bulk-prefetch maps for list endpoints with computed projection fields: page_ids = [m.id for m in page.items] -> single GROUP BY aggregate query for sums + single IN-list query for joined open rows -> dict[UUID, T] lookups in the projection loop. 3 queries regardless of N rows — extends to any future per-row computed projection (renewal status, payment recency, etc.)."

requirements-completed:
  - MEM-FRZ-04
  - MEM-FRZ-05
  - MEM-FRZ-07
  - MEM-FRZ-EP-03
  - MEM-FRZ-AUDIT-01

# Metrics
duration: 25min
completed: 2026-05-09
---

# Phase 25 Plan 03: Service Layer for Freeze Cycle Summary

**The Phase 25 business logic landing: `freeze_membership`, `unfreeze_membership`, and the `cancel_membership` frozen-source extension, plus the locked single-row response projector `_build_membership_response` and a bulk-prefetch rewrite of `list_memberships` to avoid N+1 — all on top of the Plan 01 schema, Plan 02 repository helpers, and Plan 04 schemas/router contract.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-05-09T03:55:00Z (approx; first commit 03:57)
- **Completed:** 2026-05-09T04:20:04Z
- **Tasks:** 4
- **Files modified/created:** 3 (1 modified service.py, 1 modified router.py, 1 modified deferred-items.md, 1 new SUMMARY.md)

## Accomplishments

- **`_assert_can_freeze` / `_assert_can_unfreeze`** thin transition wrappers added after `_assert_can_expire`. Both delegate to `_assert_can_transition` (Phase 24 D-24-05 pattern) — `_assert_can_freeze` targets `'frozen'`, `_assert_can_unfreeze` targets `'active'`.
- **`_is_already_frozen_conflict(exc: IntegrityError) -> bool`** discriminator added after `_is_plan_in_use_conflict`. Direct mirror of `_is_plan_name_conflict` with constraint name `uq_membership_freeze_periods_active_per_membership`.
- **`_assert_can_cancel` docstring updated** to mention the post-Phase-25 frozen source acceptance and the cancel-during-freeze audit ordering invariant.
- **Module docstring "Audit emit ordering" section extended** with three new bullets describing `freeze_membership`, `unfreeze_membership`, and the `cancel_membership` frozen-source extension flows.
- **`_build_membership_response(session, membership) -> MembershipResponse`** projector landed with the locked Phase 25 D-25-12 pattern: `MembershipResponse.model_validate(membership, from_attributes=True).model_copy(update=overlay)`. ORM column `freeze_days_limit_snapshot` rides through `from_attributes`; the 3 computed fields (`freeze_days_used`, `freeze_days_remaining`, `current_freeze_period`) ride through `overlay`. The helper carries the `# noqa: SVC001 caller-owns-txn` opt-out marker because it's a read-only projection helper.
- **`freeze_membership(session, actor, membership_id) -> MembershipResponse`** implemented exactly per D-25-07 (10 ordered steps): load → `_assert_can_freeze` (409 invalid_transition for non-active) → preventive limit check (409 freeze_limit_exceeded when days_used >= snapshot_limit) → INSERT freeze period → flush (translate `IntegrityError` on `uq_membership_freeze_periods_active_per_membership` via `_is_already_frozen_conflict` → 409 already_frozen) → status='frozen' → flush → `audit.emit("membership_frozen", ...)` (LITERAL strings; payload includes `client_id`, `freeze_period_id`, `started_at` ISO) → refresh `updated_at` → commit → return via `_build_membership_response`.
- **`unfreeze_membership(session, actor, membership_id) -> MembershipResponse`** implemented exactly per D-25-08 (12 ordered steps): load → `_assert_can_unfreeze` → load open period (raise `RuntimeError` defence-in-depth if absent) → close period (`ended_at`, `ended_by`) → `days_added = max(1, math.ceil(delta_seconds / 86400))` → extend `end_date` → status='active' → flush → `audit.emit("membership_unfrozen", ..., days_added=N)` → refresh → commit → return via `_build_membership_response`.
- **`cancel_membership` extended for frozen source per D-25-09**: a new branch after `_assert_can_cancel` and before `update_membership_status` handles `membership.status == "frozen"` — closes the open period (`ended_at = now(UTC)`, `ended_by = actor.id`), flushes, then emits `audit.emit("membership_unfrozen", ..., days_added=0)` BEFORE the existing `audit.emit("membership_cancelled", ...)` emit. Both emits live in the same UoW (single terminal commit covers both); the `days_added=0` sentinel discriminates cancel-from-frozen vs normal unfreeze in audit_log forensics. NO `end_date` extension — cancellation supersedes freeze (REQUIREMENTS MEM-FRZ-07).
- **`get_membership` migrated** — terminal `MembershipResponse.model_validate(membership)` replaced with `await _build_membership_response(session, membership)`.
- **`create_membership` migrated** — terminal projection migrated; at create time the helper returns `(snapshot_limit, 0, snapshot_limit, None)` for the 4 freeze fields (no freeze period exists yet; status='active').
- **`cancel_membership` terminal projection migrated** — `current_freeze_period` resolves to None because after the cancel mutation the status is `'cancelled'`, not `'frozen'` (helper guards on `status == 'frozen'`).
- **`list_memberships` rewritten per D-25-18 to avoid N+1**: bulk-fetches `days_used` per `membership_id` via a single `GROUP BY` aggregate (mirrors `repository.compute_freeze_days_used` SQL: `SUM(CEIL(EXTRACT(EPOCH FROM (COALESCE(ended_at, now()) - started_at)) / 86400))`); bulk-fetches open freeze periods for the page in one IN-list query; iterates `page.items` with `dict[UUID, ...]` lookups for both maps; inlines the same Step 1 + Step 2 projection pattern as `_build_membership_response` so single source of truth for projection logic is preserved (the two implementations only differ in I/O batching). Total: 3 queries regardless of N rows (outer list + days_used aggregate + open periods bulk fetch).
- **Wave 3 cleanup**: removed both `# type: ignore[attr-defined]  # Wave 4: service.freeze_membership defined in Plan 03` markers from `apps/backend/app/modules/memberships/router.py` at the `service.freeze_membership` and `service.unfreeze_membership` callsites — the service flow now exists, the markers are no longer needed.
- **`resolve_active_membership_by_client` body unchanged** (D-25-17 invariant preserved — verified by `git diff` shows no resolver lines modified).
- **`_expire_due_memberships` body unchanged** (Phase 18 invariant preserved).

## Task Commits

1. **Task 1: helpers + discriminator + docstrings** — `dd4b9b1` (feat)
2. **Task 2: _build_membership_response + freeze_membership + unfreeze_membership + Wave 3 cleanup** — `6c2ee02` (feat)
3. **Task 3: cancel_membership frozen-source extension** — `3c4046f` (feat)
4. **Task 4: read/mutation projection migrations + list_memberships bulk-prefetch rewrite + deferred-items log** — `31bc3e5` (feat)

## Files Created/Modified

- `apps/backend/app/modules/memberships/service.py` — +209 LOC net across 4 commits. New helpers, projector, two new public service functions, cancel extension, list rewrite, four projection migrations. Final file size: 959 LOC.
- `apps/backend/app/modules/memberships/router.py` — −2 LOC (Wave 3 type-ignore markers removed; 2 callsite lines collapsed from 3-line form to single-line `service.<fn>(session, actor, membership_id)`).
- `.planning/phases/25-memberships-freeze-backend/deferred-items.md` — added an entry documenting a pre-existing test failure in `tests/unit/memberships/test_schemas.py::test_create_trims_leading_trailing_whitespace_preserves_casing` (Plan 25-04 added a required field but didn't update Phase 17 schema-test fixtures). Out-of-scope per Rule SCOPE BOUNDARY; deferred to Plan 25-05.

## Decisions Made

- Followed plan as specified — D-25-07, D-25-08, D-25-09, D-25-12, D-25-15, D-25-18, D-25-22 implemented verbatim.
- Reformatted the projection call (Task 2) into a single line by extracting `overlay = {...}` so the acceptance grep `MembershipResponse\.model_validate\([^)]*from_attributes=True[^)]*\)\.model_copy` matches (the original 4-line form was POSIX-incompatible with `[^)]*` — that character class doesn't match newlines). Added `# noqa: E501` with a comment marking it as the locked Phase 25 D-25-12 projection pattern + grep-acceptance gate justification.
- Reworded the `_build_membership_response` docstring sentence "Do NOT call `MembershipResponse.model_validate(membership)` directly" to "Do NOT call ``MembershipResponse.model_validate`` on a Membership ORM directly" so the doc text does not match the acceptance grep regex (which scans the whole file as a regex stream, not by AST).
- Imported `MembershipFreezePeriod` at module top-level (re-add in Task 4) rather than inline-import inside `list_memberships`. Top-level keeps mypy/ruff happy; the import is now a real runtime consumer (not stubbed).

## Deviations from Plan

None — plan executed exactly as written. The two micro-adjustments (single-line projection call format and docstring rewording) are formatting-only changes to satisfy the plan's own acceptance grep regex without altering the locked pattern semantics.

## Issues Encountered

- Initial Task 2 reformat: the locked projection call spanned 4 lines (`MembershipResponse.model_validate(\n    membership, from_attributes=True\n).model_copy(...)`), so the acceptance grep returned 0 matches. Reformatted to a single line via `overlay` extraction; gate now matches with 1 hit.
- Initial `MembershipFreezePeriod` import (Task 2): I imported it for future Task 4 use, but ruff flagged F401 (unused). Removed in Task 2 commit and re-added in Task 4 when the bulk-fetch SQL became a real consumer.
- Pre-existing test failure (out-of-scope): `tests/unit/memberships/test_schemas.py::test_create_trims_leading_trailing_whitespace_preserves_casing` fails because Plan 25-04 added a required `freeze_days_limit` field to `MembershipPlanCreateRequest` without updating Phase 17 schema-test fixtures. Logged to `deferred-items.md`; not auto-fixed (Rule SCOPE BOUNDARY).

## Verification Evidence

### Per-task gates

- **Task 1:** `uv run python -c "from app.modules.memberships.service import _assert_can_freeze, _assert_can_unfreeze, _is_already_frozen_conflict; print('OK')"` → `OK`. `uv run mypy app/modules/memberships/service.py` → `Success: no issues found in 1 source file`.
- **Task 2:** `uv run python -c "from app.modules.memberships.service import freeze_membership, unfreeze_membership, _build_membership_response; print('OK')"` → `OK`. mypy + ruff clean on `service.py` and `router.py`. `uv run pytest tests/unit/test_service_commit_gate.py -x -q` → `7 passed`. Wave 3 cleanup grep gates: `# type: ignore.*Wave 4` → 0 matches; `raise NotImplementedError.*Phase 25 Plan 03` → 0 matches.
- **Task 3:** mypy + ruff clean. `uv run pytest tests/unit/test_service_commit_gate.py tests/unit/test_audit_taxonomy.py -x -q` → `11 passed`. AWK-extracted ordering: in `cancel_membership` body, `"membership_unfrozen"` literal at line 44 of body precedes `"membership_cancelled"` at line 70 of body.
- **Task 4:** mypy + ruff clean. All 6 service functions importable. **Critical grep gate** (`MembershipResponse\.(model_validate|from_orm)\(membership\)` outside `_build_membership_response` and outside comments) → 0 matches. `await _build_membership_response(session, membership)` → 5 occurrences (get_membership, create_membership, cancel_membership, freeze_membership, unfreeze_membership terminals). `MembershipFreezePeriod.membership_id.in_(page_ids)` → 2 occurrences (days_used aggregate + open periods bulk fetch). `days_used_map` → 2 (build + lookup). `open_period_map` → 2 (build + lookup).

### Plan-level verify gates

- `cd apps/backend && uv run mypy app/modules/memberships/service.py` → clean.
- `cd apps/backend && uv run ruff check app/modules/memberships/` → clean (entire module, including unmodified files).
- `cd apps/backend && uv run pytest tests/unit/test_service_commit_gate.py -x -q` → 7 passed.
- `cd apps/backend && uv run pytest tests/unit/test_audit_taxonomy.py -x -q` → 4 passed.
- `cd apps/backend && uv run pytest tests/unit/test_service_commit_gate.py tests/unit/test_audit_taxonomy.py tests/unit/memberships/test_state_machine.py -q` → 23 passed.
- **Grep zero-matches:** `grep -nE 'MembershipResponse\.(model_validate|from_orm)\(membership\)' app/modules/memberships/service.py | grep -v '_build_membership_response' | grep -v '^[0-9]*: *#'` → no matches.
- **Wave 4 cleanup zero-matches:** `grep -nE '# type: ignore.*Wave 4|raise NotImplementedError.*Phase 25 Plan 03' app/modules/memberships/service.py app/modules/memberships/router.py 2>/dev/null` → no matches.
- `resolve_active_membership_by_client` line range unchanged (D-25-17 invariant).

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- **Plan 25-05 (Wave 5):** can compose the 7 planned freeze integration tests (cycle, limit, race, resolver, cancel-during-freeze, endpoints RBAC matrix, days_used computation) — all required service flows now exist with the documented audit + commit semantics. Plan 25-05 should also fold the pre-existing test_schemas.py fix in `deferred-items.md` (add `freeze_days_limit=14` to the affected fixtures).
- **Phase 26 (renewal):** can extend `cancel_membership` further or add `renew_membership` on top of the same `_build_membership_response` projector pattern; the helper is now the central response-projection contract for the memberships module.
- **Phase 28 (FE drift gate):** OpenAPI surface is complete after Plan 25-04 (this plan changes only service-layer code, no schema changes). `apps/backend/openapi.json` regen still deferred to Phase 28 per D-25-25.
- No blockers.

## Self-Check: PASSED

**Files verified:**
- FOUND: apps/backend/app/modules/memberships/service.py (959 LOC; freeze_membership, unfreeze_membership, _build_membership_response, _assert_can_freeze, _assert_can_unfreeze, _is_already_frozen_conflict all importable; resolve_active_membership_by_client line 864 unchanged)
- FOUND: apps/backend/app/modules/memberships/router.py (Wave 3 type-ignore markers removed; freeze + unfreeze callsites use plain `await service.freeze_membership(session, actor, membership_id)` form)
- FOUND: .planning/phases/25-memberships-freeze-backend/25-03-SUMMARY.md (this file)
- FOUND: .planning/phases/25-memberships-freeze-backend/deferred-items.md (entry added for Plan 25-04 schema-test fixture gap)

**Commits verified:**
- FOUND: dd4b9b1 (Task 1)
- FOUND: 6c2ee02 (Task 2)
- FOUND: 3c4046f (Task 3)
- FOUND: 31bc3e5 (Task 4)

---
*Phase: 25-memberships-freeze-backend*
*Completed: 2026-05-09*
