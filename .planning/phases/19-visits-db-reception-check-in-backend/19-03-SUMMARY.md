---
phase: 19-visits-db-reception-check-in-backend
plan: "03"
subsystem: backend-visits-service
tags:
  - anti-fraud-chain
  - audit-emit
  - d05-deviation
  - caller-owns-txn
  - integrity-error-translation
  - protocol-resolver
dependency_graph:
  requires:
    - 19-01 (Visit ORM, schemas, exceptions, gym_hours config)
    - 19-02 (ClientByTelegram resolver slot in core/dependencies.py)
  provides:
    - visits/repository.py — get, list_by_query, create (single point of access to Visit ORM)
    - visits/service.py — anti-fraud chain + two public wrappers + read helpers
  affects:
    - 19-04 (router imports create_visit_reception, list_visits, get_visit)
    - Phase 20 (bot handler imports create_visit_self_checkin)
tech_stack:
  added: []
  patterns:
    - D-05 DEVIATION: reject paths emit audit + commit + raise (inverts Phase 16/17 pattern)
    - Rollback-then-emit for duplicate-checkin (poisoned session D-08)
    - _is_duplicate_visit_conflict: asyncpg constraint_name + str fallback
    - PaginatedData.model_construct to skip Pydantic validation against SA ORM generic
key_files:
  created:
    - apps/backend/app/modules/visits/repository.py
    - apps/backend/app/modules/visits/service.py
  modified: []
decisions:
  - "D-03: Anti-fraud order LOCKED gym_hours → active_membership → insert+UNIQUE"
  - "D-04: _create_visit_with_anti_fraud shared by reception + bot; two thin public wrappers"
  - "D-05 DEVIATION: reject paths emit + commit + raise (not Phase 16/17 no-commit-on-raise)"
  - "D-08: rollback before emit on duplicate-checkin (failed INSERT poisons session)"
  - "D-12: ClientNotLinkedError raised without audit emit (Phase 20 owns telegram_unknown_checkin)"
  - "D-16: Audit payloads verbatim — visit_created={client_id, membership_id, channel}; rejected_no_membership={client_id, channel}; rejected_duplicate={client_id, gym_date, channel}; rejected_outside_hours={client_id, channel, current_local_time, gym_open, gym_close}"
metrics:
  duration: "~15 minutes"
  completed: "2026-05-07"
  tasks_completed: 2
  files_changed: 2
---

# Phase 19 Plan 03: Visits Repository + Service Summary

**One-liner:** visits/repository.py (single-point-of-access, caller-owns-txn) + visits/service.py (locked anti-fraud chain with D-05 reject-path-commits deviation, 4 literal audit events, Phase 15 AST gates clean).

## What Was Built

### Task 1: visits/repository.py

Module-level async helpers — single point of access to the `Visit` ORM. Mirrors the memberships/repository.py pattern exactly.

**`get(session, visit_id) -> Visit | None`**
- `Select[tuple[Visit]]` with typed intermediate `result: Visit | None` for mypy strict `no-any-return`
- No soft-delete filter (visits have no `deleted_at` column, CD-04)

**`list_by_query(session, query) -> PaginatedData[Visit]`**
- Predicates: `client_id ==`, `gym_date >=` (from_), `gym_date <=` (to)
- Sort: `Visit.checked_in_at.desc()` (D-09 fixed sort, no enum)
- `PaginatedData.model_construct(...)` skips Pydantic validation against SA ORM generic

**`create(session, *, client_id, membership_id, channel, checked_in_by) -> Visit`**
- `session.add(visit)` only — no flush, no commit (caller owns transaction)
- `gym_date` NOT passed (STORED GENERATED column, D-06)

**Transaction invariant:** No `session.commit()` or `session.flush()` anywhere in the file — both verified by grep checks and the file docstring.

### Task 2: visits/service.py

**Module docstring** explicitly documents the D-05 deviation: "DEVIATION FROM PHASE 16/17 (D-05 — DO NOT NORMALIZE BACK)" with full rationale (Pitfall 9 anti-fraud signal, VIS-AUDIT-01 requirement, rollback-before-emit for duplicate path).

**Private helpers:**

- `_is_duplicate_visit_conflict(exc: IntegrityError) -> bool` — checks `getattr(exc.orig, "constraint_name", None)` first (asyncpg), then substring fallback on `str(exc.orig)`. Literal constraint name `uq_visits_client_id_gym_date` appears twice (exact match + substring).
- `_now_msk() -> datetime` — `datetime.now(_MSK)` with `ZoneInfo("Europe/Moscow")` module-level constant.
- `_today_msk() -> date` — delegates to `_now_msk().date()`.
- `_assert_within_gym_hours(now_msk: time) -> None` — pure sync helper (no DB, testable standalone), raises `OutsideGymHoursError` with `open`/`close` fields if `not (start <= now < end)` (end exclusive, CD-07).

**`_create_visit_with_anti_fraud(session, *, client_id, channel, checked_in_by, audit_actor_user_id) -> VisitResponse`** — LOCKED anti-fraud chain (D-03):

| Step | Check | Audit event | D-05 action |
|------|-------|-------------|-------------|
| 1 | `gym_hours_start <= now_msk_t < gym_hours_end` | `visit_rejected_outside_hours` | emit + commit + raise |
| 2 | `resolve_active_membership(session, client_id)` → not None | `visit_rejected_no_membership` | emit + commit + raise |
| 3 | `session.flush()` → IntegrityError → `_is_duplicate_visit_conflict` | `visit_rejected_duplicate` | rollback + emit + commit + raise |
| 4 | Success | `visit_created` | emit + commit + return |

**Public entry points:**

- `create_visit_reception(session, actor, payload) -> VisitResponse` — calls chain with `channel="reception"`, `checked_in_by=actor.id`, `audit_actor_user_id=actor.id`.
- `create_visit_self_checkin(session, telegram_user_id, chat_id) -> VisitResponse` — calls `resolve_client_by_telegram_user_id`; raises `ClientNotLinkedError` WITHOUT audit if None (D-12); calls chain with `channel="telegram_bot"`, `checked_in_by=None`, `audit_actor_user_id=None`. `del chat_id` silences unused-parameter without breaking the forward-compat signature.

**Read-side:**
- `list_visits(session, query) -> PaginatedData[VisitResponse]` — delegates to `repository.list_by_query`, re-wraps via `model_construct`.
- `get_visit(session, visit_id) -> VisitResponse` — delegates to `repository.get`, raises `VisitNotFoundError` if None.

## Audit Event Literal Callsites (D-16)

| Event literal | resource_type | resource_id | actor_user_id | Payload keys |
|---------------|---------------|-------------|---------------|--------------|
| `"visit_created"` | `"visit"` | `visit.id` | reception: actor.id / bot: None | `client_id`, `membership_id`, `channel` |
| `"visit_rejected_no_membership"` | `"visit"` | `None` | same | `client_id`, `channel` |
| `"visit_rejected_duplicate"` | `"visit"` | `None` | same | `client_id`, `channel`, `gym_date` |
| `"visit_rejected_outside_hours"` | `"visit"` | `None` | same | `client_id`, `channel`, `current_local_time`, `gym_open`, `gym_close` |

## D-05 Deviation Documentation Location

Module docstring of `apps/backend/app/modules/visits/service.py`, lines 17-28:
```
DEVIATION FROM PHASE 16/17 (D-05 — DO NOT NORMALIZE BACK):
  Rejection paths emit `visit_rejected_*` audit + commit + raise — even though
  the canonical Phase 16/17 service rule is "no commit on raise". Rationale: ...
```

## Phase 15 AST Gate Results

| Gate | Test | Result |
|------|------|--------|
| Audit taxonomy (INFRA-11) | `test_audit_taxonomy.py` (3 tests) | PASSED |
| Service commit gate (INFRA-13) | `test_service_commit_gate.py` (7 tests) | PASSED |
| Import-linter contracts | `lint-imports` | 3 kept, 0 broken |

No `# noqa: SVC001` marker in `visits/service.py` — every write path commits on every exit branch.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | ad4acfd | feat(19-03): visits/repository.py — get + list_by_query + create (caller-owns-txn) |
| Task 2 | 72b90f8 | feat(19-03): visits/service.py — anti-fraud chain + reception + self-checkin + reads |

## Deviations from Plan

None — plan executed exactly as written. The `_assert_within_gym_hours` helper is defined (per acceptance criteria) AND `_create_visit_with_anti_fraud` inlines the hours check directly (per plan skeleton) so the private chain remains self-contained without requiring a sync raise from within an async function's try block.

## Known Stubs

None. Both files are fully functional implementations with no placeholder values, no hardcoded empty collections, no TODO markers.

## Threat Flags

None. All threat mitigations from the plan's threat register are implemented:
- T-19-03-01 (client_id swap): gym_hours runs unconditionally before client_id is used in DB
- T-19-03-03 (Repudiation): all 4 paths emit literal-string events; Phase 15 AST walker verified
- T-19-03-04 (oracle leak): `ClientNotLinkedError` raised without audit emit; Phase 20 maps to generic Russian DM
- T-19-03-07 (race condition): UNIQUE INDEX `uq_visits_client_id_gym_date` is the structural mitigation; `_is_duplicate_visit_conflict` translates the IntegrityError

## Self-Check: PASSED
