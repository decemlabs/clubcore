---
phase: 26-memberships-renewal-backend
plan: 03
subsystem: api
tags: [fastapi, sqlalchemy, postgres, audit, renewal, memberships]

# Dependency graph
requires:
  - phase: 26-memberships-renewal-backend
    provides: "Plan 26-01 (CannotRenewCancelledError, PlanArchivedError, RENEWAL_STRATEGY_* constants, MembershipResponse.previous_membership_id field, Membership.previous_membership_id ORM column + index)"
  - phase: 26-memberships-renewal-backend
    provides: "Plan 26-02 (resolver tiebreak inversion to ORDER BY start_date ASC, created_at DESC)"
provides:
  - "repository.get_plan_for_renewal(session, plan_id) -> tuple[plan|None, is_archived] discriminator"
  - "repository.insert_renewal_membership(session, *, source, plan, start_date, end_date) -> Membership with snapshots from CURRENT plan, previous_membership_id=source.id, status='active'"
  - "service.renew_membership(session, actor, source_membership_id) -> MembershipResponse with full load->guard->date->insert->flush->audit->refresh->commit ordering"
  - "POST /api/v1/memberships/{id}/renew (reception+owner, CSRF, 201 Created)"
  - "audit.py docstring drift fix (lines 61-62) — payload now matches actual D-26-15 keys"
  - "_build_membership_response + list_memberships projections surface previousMembershipId"
affects: [27-notifications-cron, 28-frontend-renewal-ui, 29-cross-flow-integration-sweeps]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Tuple-return discriminator helpers (get_plan_for_renewal returns (plan, is_archived) so the service can map to 404 vs 409 declaratively)"
    - "Renewal-as-INSERT (NOT transition) — source row stays in its current status; MEMBERSHIP_STATUS_TRANSITIONS untouched; new row carries previous_membership_id for chain attribution"
    - "Snapshot-from-CURRENT-plan lock — repository.insert_renewal_membership reads plan.{name,duration_days,price_kopecks,freeze_days_limit} directly so the 'plan got more expensive between sale and renewal' lock from PROJECT.md applies"
    - "Date-strategy literals captured in audit payload (start_date_strategy = 'from_source_end_date' | 'from_today_expired_source') for forensic SQL"

key-files:
  created:
    - "apps/backend/tests/integration/memberships/test_renewal_repository.py - RED+GREEN coverage for repo helpers"
    - "apps/backend/tests/integration/memberships/test_renewal_endpoint.py - RBAC matrix + CSRF + status guards + date strategies + snapshot semantics + audit payload + chain attribution"
    - ".planning/phases/26-memberships-renewal-backend/26-03-SUMMARY.md - this file"
  modified:
    - "apps/backend/app/modules/memberships/repository.py - get_plan_for_renewal + insert_renewal_membership"
    - "apps/backend/app/modules/memberships/service.py - imports, module docstring, renew_membership public function, _build_membership_response + list_memberships projection adds previous_membership_id"
    - "apps/backend/app/modules/memberships/router.py - module docstring + POST /{membership_id}/renew endpoint declaration"
    - "apps/backend/app/core/audit.py - docstring lines 61-62 drift fix (payload keys match actual emit)"

key-decisions:
  - "Auto-fix: AuditLog column is `action` (not `event`) — RED test used wrong attribute; corrected to AuditLog.action across all 4 audit lookups"
  - "Auto-fix: DTZ011 ruff lock — replaced bare date.today() with datetime.now(tz=UTC).date() in the new test files; mirrors conftest precedent"
  - "Mypy pre-existing errors in tests/unit/memberships/test_renewal_constants.py and tests/integration/auth/test_sessions_endpoints.py are out of scope (Plan 26-01 / pre-Phase-26 baseline); my touched files are mypy --strict clean"

patterns-established:
  - "Tuple-return discriminator: helper returns (entity, classification_flag) so the service maps each branch to a distinct HTTP status without leaking ORM into the service or duplicating queries"
  - "Renewal write-path 10-step ordering documented in service.renew_membership docstring: load -> status guard -> plan classification -> date strategy -> insert -> flush -> audit emit (LITERAL strings) -> refresh -> commit -> projection helper"
  - "AuditLog query attribute is `action` (not `event`) — the kwarg `event=` to `audit.emit` maps to the `action` column on the row; tests querying audit_log MUST use AuditLog.action"

requirements-completed:
  - MEM-REN-02
  - MEM-REN-04
  - MEM-REN-EP-01
  - MEM-REN-AUDIT-01

# Metrics
duration: 18min
completed: 2026-05-09
---

# Phase 26 Plan 03: Renewal write path (service + endpoint + audit) Summary

**POST /memberships/{id}/renew creates a chained follow-up membership with CURRENT-plan snapshots, emits `membership_renewed` with `start_date_strategy` literal, and returns 201 with `previousMembershipId` populated.**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-05-09T19:46:00Z
- **Completed:** 2026-05-09T20:04:00Z
- **Tasks:** 2 (TDD: RED + GREEN per task)
- **Files modified:** 4 source + 2 new test files

## Accomplishments

- `repository.get_plan_for_renewal` discriminates `(None, False)` | `(plan, False)` | `(plan, True)` so the service emits 404 plan_not_found vs 409 plan_archived without duplicating the SELECT.
- `repository.insert_renewal_membership` snapshots from the CURRENT plan (NOT source's stale snapshots) and pins `previous_membership_id = source.id` — the "client pays new price" lock from PROJECT.md is enforced at the data layer.
- `service.renew_membership` ships with the canonical 10-step ordering: load → status guard → plan classification → date strategy (active/frozen → source.end_date+1; expired → today MSK) → insert → flush → `audit.emit("membership_renewed", ...)` (LITERAL strings) → refresh → commit → `_build_membership_response`. SVC001 commit gate green; AST audit gate green.
- `POST /api/v1/memberships/{id}/renew` mounted with `(CREATE, MEMBERSHIPS)` reception+owner RBAC + `verify_csrf` (RBAC-04 ordering), 201 Created, empty body, `ResponseEnvelope[MembershipResponse]` return.
- `audit.py` docstring (lines 61-62) drift closed — payload sketch now lists the actual D-26-15 keys: `client_id, source_membership_id, source_plan_id, current_price_kopecks, start_date_strategy`.
- `_build_membership_response` + `list_memberships` projection both surface `previous_membership_id` (auto-camelCased to `previousMembershipId` on the wire).

## Task Commits

Each task was committed atomically (TDD: RED test → GREEN feat):

1. **Task 1 RED — failing tests for renewal repository helpers** — `8703403` (test)
2. **Task 1 GREEN — repository helpers + projection field** — `327e4c1` (feat)
3. **Task 2 RED — failing tests for POST /renew endpoint + service flow** — `88015f6` (test)
4. **Task 2 GREEN — service.renew_membership + router endpoint + audit docstring** — `4dca4bf` (feat)
5. **Test cleanup — DTZ011 ruff lock, AuditLog.action column** — `80e1f60` (style)

## Files Created/Modified

**Created:**
- `apps/backend/tests/integration/memberships/test_renewal_repository.py` — 5 tests covering get_plan_for_renewal tuple semantics + insert_renewal_membership snapshot/no-flush invariants.
- `apps/backend/tests/integration/memberships/test_renewal_endpoint.py` — 12 tests covering RBAC matrix, CSRF, source-status guards (cancelled / archived plan / unknown source), date-strategy branches (active/expired/frozen), snapshot-from-CURRENT-plan after price PATCH, audit payload shape, and chain attribution row in DB.

**Modified:**
- `apps/backend/app/modules/memberships/repository.py` — `get_plan_for_renewal` after `get_alive`; `insert_renewal_membership` at end of file (Phase 26 block).
- `apps/backend/app/modules/memberships/service.py` — added `CannotRenewCancelledError` + `PlanArchivedError` to imports; added `RENEWAL_STRATEGY_*` constants imports; module docstring extended with renew_membership flow paragraph; `renew_membership` public function appended after `unfreeze_membership`; `_build_membership_response` + `list_memberships` projection dicts now include `previous_membership_id`.
- `apps/backend/app/modules/memberships/router.py` — module docstring extended with Phase 26 endpoint surface block; `POST /{membership_id}/renew` endpoint appended after `/unfreeze` with RBAC-04 ordering, 201 status code, and reception+owner permission.
- `apps/backend/app/core/audit.py` — docstring lines 61-62 replaced with actual Phase 26 payload keys (drift fix); LOCKED_AUDIT_EVENTS line 142 untouched.

## Decisions Made

- **Tuple-return discriminator over flag-on-existing-helper:** `get_plan_for_renewal` is a separate function rather than a `?include_archived=True` flag on `get_alive`, so other write paths (`create_membership`) cannot accidentally bypass soft-delete (D-26-08 Specifics line 411).
- **Renewal is INSERT, not transition:** `MEMBERSHIP_STATUS_TRANSITIONS` was NOT modified; source row keeps its original status; new row simply carries `previous_membership_id` for chain attribution (D-26-24).
- **AuditLog column is `action`, not `event`:** discovered during the GREEN run for Task 2 — corrected the test queries to `AuditLog.action == "membership_renewed"`.
- **Pre-existing mypy errors are out of scope:** the SCOPE BOUNDARY rule says only fix issues caused by current task changes. The 137 pre-existing mypy errors in 15 files (mostly `test_renewal_constants.py` from Plan 26-01 and `test_sessions_endpoints.py` from earlier phases) are tracked separately. My touched files pass `mypy --strict`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] AuditLog column is `action`, not `event`**
- **Found during:** Task 2 (GREEN run)
- **Issue:** RED test used `AuditLog.event` in 4 audit lookup queries; the model declares `action: Mapped[str]` (`audit_models.py:42`).
- **Fix:** `replace_all` updated all 4 occurrences to `AuditLog.action`.
- **Files modified:** `apps/backend/tests/integration/memberships/test_renewal_endpoint.py`
- **Verification:** All 12 endpoint tests pass after fix.
- **Committed in:** `4dca4bf` (Task 2 GREEN commit)

**2. [Rule 1 — Bug] DTZ011 ruff lock — bare `date.today()` use**
- **Found during:** post-Task-2 ruff sweep
- **Issue:** I used `date.today()` in the integration tests; project ruff ruleset (DTZ011) requires `datetime.now(tz=...).date()` for timezone safety.
- **Fix:** Replaced with `datetime.now(tz=UTC).date()` mirroring the conftest precedent (`conftest.py:244`); removed unused `date` from imports.
- **Files modified:** `apps/backend/tests/integration/memberships/test_renewal_endpoint.py`, `apps/backend/tests/integration/memberships/test_renewal_repository.py`
- **Verification:** `uv run ruff check .` exits 0; tests still pass (17 / 17 across both new files).
- **Committed in:** `80e1f60` (style commit)

---

**Total deviations:** 2 auto-fixed (1 bug discovered during GREEN, 1 lint lock discovered during ruff sweep)
**Impact on plan:** Both auto-fixes were trivial corrections to my own RED-phase test code. No scope creep, no design changes, no impact on production code paths.

## Issues Encountered

- App-boot smoke (`uv run python -c "from app.main import app"`) requires env vars (`database_url`, `redis_url`, `secret_key`) which aren't set in the executor's shell. Substituted the targeted route-introspection assertion (`from app.modules.memberships.router import memberships_router`) which proves the same thing without needing settings — output: `renew route mounted: ['/{membership_id}/renew']`.

## Verification Gates Run

| Gate | Result |
|------|--------|
| `ruff check .` | exits 0 (all checks passed) |
| `mypy --strict app/modules/memberships/ app/core/ tests/.../test_renewal_*.py` | exits 0 (no issues in 25 source files) |
| `lint-imports` | 3 contracts kept, 0 broken |
| `pytest tests/unit/test_audit_taxonomy.py tests/unit/test_service_commit_gate.py tests/integration/test_route_introspection.py` | 14 passed |
| `pytest tests/integration/memberships/test_renewal_endpoint.py tests/integration/memberships/test_renewal_repository.py` | 17 passed |
| `pytest tests/integration/memberships/ tests/integration/visits/ tests/integration/auth/` (regression sweep) | 252 passed (no regressions) |
| Inline route-mount assertion | `/{membership_id}/renew` mounted |

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- **Plan 26-04** can land the full integration test matrix (renewal-active, renewal-price-change, renewal-archived-plan, renewal-cancelled-source, renewal-from-frozen, RBAC matrix, expired-source) — the production code is in place and the existing 12 endpoint tests give a strong baseline.
- **Phase 28 (FE-12)** can wire the admin-web "Продлить" button against `POST /memberships/{id}/renew`; mock service in `apps/admin-web/src/shared/api/services/mock/memberships.ts` will need parity with the new endpoint + `previousMembershipId` field.
- **OpenAPI drift:** the new path operation + schema field will surface in the next openapi.json regen; deferred to Phase 28 per D-26-32.

## Self-Check: PASSED

- [x] `apps/backend/app/modules/memberships/repository.py` — `get_plan_for_renewal` and `insert_renewal_membership` defined (verified by `python -c` import script).
- [x] `apps/backend/app/modules/memberships/service.py` — `renew_membership` public function defined; ends with `await session.commit()` (SVC001 gate green).
- [x] `apps/backend/app/modules/memberships/router.py` — `POST /{membership_id}/renew` mounted (verified by route-introspection inline assertion).
- [x] `apps/backend/app/core/audit.py` — docstring lines 61-62 contain `start_date_strategy` (verified by `grep`).
- [x] All commits (`8703403`, `327e4c1`, `88015f6`, `4dca4bf`, `80e1f60`) present in `git log --oneline`.
- [x] No modifications to `STATE.md` or `ROADMAP.md` (worktree mode — orchestrator owns those writes).

---
*Phase: 26-memberships-renewal-backend*
*Completed: 2026-05-09*
