---
phase: 17-membership-instances-resolver-backend
plan: 03
subsystem: api
tags: [memberships, sqlalchemy, fastapi, audit, fk-restrict, transition-guard, snapshot-pricing]

# Dependency graph
requires:
  - phase: 17-membership-instances-resolver-backend
    provides: "17-01: Membership ORM, schemas (CreateRequest/CancelRequest/ListQuery/Response/Status/Sort), domain exceptions (PlanInactiveError, PlanInUseError, InvalidTransitionError, MembershipNotFoundError)"
  - phase: 17-membership-instances-resolver-backend
    provides: "17-02: ActiveMembership Protocol + register_active_membership_resolver slot in core/dependencies.py"
  - phase: 16-membership-plans-catalog-backend
    provides: "MembershipPlan ORM, repository.get_alive, _is_plan_name_conflict, soft_delete_plan baseline (now extended)"
  - phase: 15
    provides: "audit.emit + LOCKED_AUDIT_EVENTS (membership_created, membership_cancelled pre-locked)"
provides:
  - "repository.insert_membership / get_membership / list_memberships / update_membership_status / find_active_for_client"
  - "service.create_membership / cancel_membership / list_memberships / get_membership / resolve_active_membership_by_client"
  - "service._is_plan_in_use_conflict — IntegrityError → 409 plan_in_use translation pinned on fk_memberships_plan_id_membership_plans"
  - "service._assert_can_cancel / _assert_can_expire — pre-mutation transition guards (D-15 invariant)"
  - "service.soft_delete_plan extended: try/except IntegrityError on flush; co-transactional rollback unwinds soft-delete + audit row (Phase 16 D-15 closure)"
  - "ROADMAP Phase 16 SC#4 wording aligned with D-07 (any Membership row blocks deletion, including cancelled and expired)"
affects: [17-04, 17-05, 18-arq-membership-expiry, 22-frontend-memberships]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Constraint-name-pinned IntegrityError translation (mirror of Phase 16 _is_plan_name_conflict; one helper per constraint)"
    - "Pre-mutation transition guards as free module-level functions (CD-03) — keep service.py composable, no class hierarchy"
    - "Resolver query uses composite index ix_memberships_client_id_status_end_date with silent tiebreak (D-17) — no warnings, no audit"
    - "Audit payload key omission for optional fields (D-14) — `kwargs: dict[str, Any] = {} if data.reason is None else {\"reason\": data.reason}`"
    - "Audit-emit-before-flush co-transactional contract honoured on FK-rejecting paths: rollback unwinds the audit row alongside the data mutation"

key-files:
  created: []
  modified:
    - "apps/backend/app/modules/memberships/repository.py — +5 helpers, imports widened (Membership, MembershipCreateRequest, MembershipListQuery, MembershipListSort, true)"
    - "apps/backend/app/modules/memberships/service.py — +5 public service fns, +3 helpers, soft_delete_plan extended with FK translation"
    - ".planning/ROADMAP.md — Phase 16 SC#4 wording aligned with D-07"

key-decisions:
  - "Did NOT wire register_active_membership_resolver(...) into a startup hook here — that wiring belongs to Plan 17-04 (HTTP routes / app composition) per the plan's responsibility split"
  - "Computed `start_date` as a pure-Python `datetime.now(ZoneInfo('Europe/Moscow')).date()` (D-04 — Moscow TZ, end_date inclusive via duration_days - 1) inside the service, before insert"
  - "Used `cancelled_at = datetime.now(tz=UTC)` (UTC clock) on the timestamptz column — wall-time encoding is preserved regardless of zone; Moscow-only date computation is reserved for `start_date` per D-04"
  - "Re-used `_is_plan_name_conflict` shape verbatim for `_is_plan_in_use_conflict` — same control flow, only constraint name differs; keeps the audit/forensic patterns parallel and ASCII-greppable"
  - "Returned the SA ORM `Membership` from `resolve_active_membership_by_client` (not a DTO) — structurally satisfies the `ActiveMembership` Protocol (D-18) so no boundary conversion"

patterns-established:
  - "Repository helpers stay strictly transactionless (no flush, no commit) — caller (service) owns the unit of work and the audit-emit-before-flush ordering"
  - "Service write paths follow Phase 16 D-14 order: get → mutate → audit.emit → flush (FK risk surfaces here) → commit; on FK reject the rollback masks both data + audit row co-transactionally"
  - "Transition guards run BEFORE any state change (D-15) — so the 409 path leaves zero side effects on a 4xx exit"
  - "Audit payload key OMISSION (not nulling) for optional fields — JSONB stays compact and forensic queries can use key-existence as a sentinel"

requirements-completed: [MEM-02, MEM-03, MEM-04, MEM-AUDIT-01, MEM-PLAN-EP-04]

# Metrics
duration: ~12min
completed: 2026-05-07
---

# Phase 17 Plan 03: Membership Service + Repository + Plan-In-Use FK Translation Summary

**Membership write paths (sale + cancel + active-resolver) + repository helpers (insert/get/list/update_status/find_active) + Phase 16 D-15 closure: soft_delete_plan now translates fk_memberships_plan_id_membership_plans IntegrityError to 409 `plan_in_use`.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-05-07T15:40:23Z (worktree base merge of Wave 1)
- **Completed:** 2026-05-07T15:53:00Z
- **Tasks:** 2
- **Files modified:** 3 (`repository.py`, `service.py`, `ROADMAP.md`)

## Accomplishments

- Membership repository: 5 transactionless helpers (`insert_membership`, `get_membership`, `list_memberships`, `update_membership_status`, `find_active_for_client`) with snapshot-pricing copy from the resolved plan ORM ref (MEM-02) and the canonical resolver query covered by `ix_memberships_client_id_status_end_date`.
- Membership service: 5 public functions (`create_membership`, `cancel_membership`, `list_memberships`, `get_membership`, `resolve_active_membership_by_client`) wired with audit-emit-before-flush, MEM-AUDIT-01 payloads, and a literal-string `audit.emit` pattern that the Phase 15 AST taxonomy walker accepts unmodified.
- Service helpers: `_is_plan_in_use_conflict` (constraint-pinned FK translator), `_assert_can_cancel` / `_assert_can_expire` (pre-mutation transition guards — D-15 invariant).
- Phase 16 D-15 closure: `soft_delete_plan` now wraps `session.flush()` in `try/except IntegrityError`, rolls back to unwind both the soft-delete and the audit row co-transactionally (Phase 16 D-14), and translates the FK violation to 409 `plan_in_use`. Cancelled and expired memberships also block deletion per D-06 — the helper does not inspect status.
- ROADMAP Phase 16 SC#4 wording brought into alignment with D-07: "any `Membership` references it (cancelled and expired included) (FK `ON DELETE RESTRICT`)" replaces the older "non-cancelled" phrasing.

## Task Commits

1. **Task 1: Add Membership repository helpers** — `f4a530f` (feat)
2. **Task 2: Add Membership service write paths + soft_delete_plan FK translation + ROADMAP D-07 fix** — `9168514` (feat)

## Files Created/Modified

- `apps/backend/app/modules/memberships/repository.py` — Added `insert_membership`, `get_membership`, `list_memberships`, `update_membership_status`, `find_active_for_client`. Widened imports to include `Membership` ORM, `MembershipCreateRequest`, `MembershipListQuery`, `MembershipListSort`, and SQLA `true()` for the empty-predicate branch. Phase 16 helpers (`get_alive`, `list_alive`, `insert_plan`, `update_plan`, `soft_delete_plan` repository-side) untouched.
- `apps/backend/app/modules/memberships/service.py` — Added `_is_plan_in_use_conflict`, `_assert_can_cancel`, `_assert_can_expire`, `create_membership`, `cancel_membership`, `list_memberships`, `get_membership`, `resolve_active_membership_by_client`. Modified existing `soft_delete_plan` to wrap `session.flush()` in `try/except IntegrityError` with co-transactional rollback + FK translation per D-05 / D-08.
- `.planning/ROADMAP.md` — Phase 16 SC#4 wording fix per D-07.

## Decisions Made

- **Resolver registration is Plan 17-04 work, not 17-03.** `register_active_membership_resolver(resolve_active_membership_by_client)` is the wiring step that belongs in app composition / module init alongside HTTP route registration. Plan 17-03 ships only the public service symbol per CD-06; Plan 17-04 wires it into `core/dependencies.py`.
- **`cancelled_at` uses UTC clock, not Moscow.** D-04's Moscow-TZ rule applies specifically to `start_date` computation (date-only, end_date inclusive). The `cancelled_at` column is `timestamptz` and stores the absolute moment regardless of zone; using UTC keeps the recorded value parallel to `created_at` / `updated_at` (which the SA mixin defaults via UTC).
- **Reused `_is_plan_name_conflict` shape verbatim.** `_is_plan_in_use_conflict` is a one-line variant — only the constraint name differs. Same control flow (asyncpg `constraint_name` first, substring fallback for other drivers) keeps both translation paths grep-symmetric and easy to audit.
- **Returned SA ORM `Membership` from the resolver, not a DTO.** D-18 declares `ActiveMembership` as a structural Protocol (matches on `id`, `client_id`, `end_date`, `status`); the ORM class satisfies all four. Skipping a DTO conversion keeps the resolver hot path zero-allocation and avoids a redundant `model_validate` per request.

## Deviations from Plan

None - plan executed exactly as written.

The plan-level acceptance grep `grep -F 'audit.emit(session, "membership_created"' service.py` reports MISS because the multi-line call format puts `session` on its own line (`audit.emit(\n    session,\n    "membership_created",`). The authoritative AST taxonomy walker (`tests/unit/test_audit_taxonomy.py`) IS green — it parses the call tree and verifies both `event` and `resource_type` resolve to literal `ast.Constant(str)` nodes. This is a plan-grep formatting expectation mismatch, not a code defect; the literal-string contract is satisfied.

## Issues Encountered

- **Ruff E501 on `_is_plan_in_use_conflict` docstring.** The first-line summary "Return True iff `exc` was caused by `fk_memberships_plan_id_membership_plans` (Phase 17 D-05)." was 101 chars (over 100). Trimmed to "Return True iff `exc` was the FK `fk_memberships_plan_id_membership_plans` (D-05)." — same intent, fits within the 100-char limit.

## Verification Outcome

- `uv run mypy app/modules/memberships/repository.py app/modules/memberships/service.py` — Success (2 files, 0 issues).
- `uv run ruff check app/modules/memberships/{repository,service}.py` — All checks passed.
- `uv run lint-imports` — 3 contracts kept, 0 broken (65 files, 112 dependencies analyzed).
- `uv run pytest tests/unit/test_service_commit_gate.py tests/unit/test_audit_taxonomy.py -q` — 10 passed (every new write path commits; both `membership_created` and `membership_cancelled` audit emits use literal strings; both pairs in `LOCKED_AUDIT_EVENTS`).
- `uv run pytest tests/unit/ -q` — 229 passed (no regressions; baseline maintained).
- Public symbol import — `create_membership`, `cancel_membership`, `resolve_active_membership_by_client`, `_is_plan_in_use_conflict`, `_assert_can_cancel`, `_assert_can_expire` all resolve and are async coroutines where required.

## Next Phase Readiness

Plan 17-04 (HTTP routes) can now:
- Import all 5 service functions and bind them to `POST /api/v1/memberships`, `POST /api/v1/memberships/{id}/cancel`, `GET /api/v1/memberships`, `GET /api/v1/memberships/{id}`.
- Register the resolver via `register_active_membership_resolver(resolve_active_membership_by_client)` in app composition / module bootstrap.
- Rely on `_is_plan_in_use_conflict`-translated 409 `plan_in_use` from `DELETE /api/v1/membership-plans/{id}` (Phase 16 endpoint, Phase 17 closure).

Plan 17-05 (integration tests) can now exercise:
- The full sale flow via direct service calls or HTTP.
- The cancel transition rejection (409 invalid_transition) on `cancelled` and `expired` source states.
- The plan-in-use rejection on `DELETE /membership-plans/{id}` for active, expired, AND cancelled membership rows (D-06 invariant).
- The active-membership resolver tiebreak via the integration fixture `test_resolver_tiebreak.py`.

Phase 18 ARQ (`membership_expired` audit event) can:
- Reuse `_assert_can_expire` and `repository.update_membership_status(..., status='expired')` for the scheduled flip; the gate already exists.

## Self-Check: PASSED

- `apps/backend/app/modules/memberships/repository.py` — FOUND
- `apps/backend/app/modules/memberships/service.py` — FOUND
- `.planning/ROADMAP.md` — FOUND
- Commit `f4a530f` (Task 1) — FOUND in git log
- Commit `9168514` (Task 2) — FOUND in git log

---
*Phase: 17-membership-instances-resolver-backend*
*Completed: 2026-05-07*
