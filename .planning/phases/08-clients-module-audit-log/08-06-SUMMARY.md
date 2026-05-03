---
phase: 08-clients-module-audit-log
plan: 06
subsystem: api
tags: [fastapi, sqlalchemy, audit, clients, service-layer, integrity-error]

# Dependency graph
requires:
  - phase: 08-clients-module-audit-log
    provides: |
      Plan 08-01 (exceptions: ClientNotFoundError / PhoneExistsError),
      Plan 08-02 (audit.emit async signature + AuditLog row co-transactional INSERT),
      Plan 08-03 (Pydantic DTOs: ClientCreateRequest / ClientUpdateRequest / ClientListQuery / ClientResponse),
      Plan 08-04 (repository: list_alive / get_alive / insert_client / update_client / soft_delete_client)
provides:
  - "apps/backend/app/modules/clients/service.py — orchestration layer"
  - "list_clients / get_client / create_client / update_client / soft_delete_client (5 module-level async functions)"
  - "D-08 audit payload shapes locked (client_created / client_updated / client_soft_deleted)"
  - "D-09 no-op PATCH skip implemented (idempotent updates do not emit)"
  - "D-11 PhoneExistsError translation from IntegrityError on uq_clients_phone_alive"
affects: [08-07-router, 08-08-tests, 09-openapi-pipeline, 10-admin-web-wiring]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Service layer = module-level async functions (not classes), each takes AsyncSession + actor: User + DTO inputs (D-19)"
    - "TYPE_CHECKING-only Client ORM import to satisfy D-02 / CLIENTS-09 architectural boundary"
    - "Per-event flush ordering: insert→flush→emit (create); mutate→flush→emit (update); mutate→emit→flush (soft-delete)"
    - "IntegrityError → domain error translation via constraint_name detection (_is_phone_conflict helper)"

key-files:
  created:
    - "apps/backend/app/modules/clients/service.py"
  modified: []

key-decisions:
  - "Use TYPE_CHECKING block for Client ORM import (mypy keeps strong typing on _full_name; runtime never imports the ORM, satisfying D-02 / CLIENTS-09 architecturally)"
  - "Centralise constraint-name detection in _is_phone_conflict helper (DRY across create_client and update_client; covers both attribute-form constraint_name and substring-of-str(orig) fallback for SA driver variance)"
  - "create_client uses insert→flush→emit ordering (cannot emit before flush — IntegrityError surfaces only on flush); update/soft_delete keep emit-before-flush where no constraint risk exists (update_client still flushes early because phone change risks uq_clients_phone_alive)"
  - "soft_delete_client captures full_name and phone into local variables BEFORE repository.soft_delete_client(...) so the audit payload survives independently of post-delete ORM state (mitigates threat T-08-33)"

patterns-established:
  - "Service no-op short-circuit: when repository.update_client returns empty changed dict, return current ClientResponse without emit + without flush (D-09)"
  - "Audit payload as dict[str, object] built locally then **payload-spread into audit.emit — keeps event-specific fields explicit and PII-minimised (D-08)"

requirements-completed: [CLIENTS-02, CLIENTS-05, CLIENTS-06, CLIENTS-07, CLIENTS-08, AUDIT-02]

# Metrics
duration: 9min
completed: 2026-05-03
---

# Phase 08 Plan 06: Clients Service Orchestration Summary

**5 module-level async service functions wiring router → repository → audit.emit with co-transactional flush, D-08 payload shapes, D-09 no-op skip, and D-11 PhoneExistsError translation — all without runtime Client ORM import.**

## Performance

- **Duration:** ~9 min
- **Started:** 2026-05-03T12:17:00Z
- **Completed:** 2026-05-03T12:26:05Z
- **Tasks:** 2
- **Files modified:** 1 (created)

## Accomplishments

- Read-side: `list_clients` and `get_client` with 404 on missing/soft-deleted (CLIENTS-05).
- Mutation-side: `create_client`, `update_client`, `soft_delete_client` orchestrating repository + audit.emit + flush.
- D-08 payload shapes implemented exactly per spec (PII-aware — no full state dump).
- D-09 no-op short-circuit for idempotent PATCHes (no emit, no flush).
- D-11 IntegrityError → PhoneExistsError translation centralised in `_is_phone_conflict` helper.
- D-02 / CLIENTS-09 architectural boundary preserved: zero runtime imports of `Client` ORM (only `TYPE_CHECKING`).

## Task Commits

Each task was committed atomically:

1. **Task 1: list_clients + get_client (read-side, CLIENTS-03/04/05)** — `a925d0b` (feat)
2. **Task 2: create_client + update_client + soft_delete_client (mutations, CLIENTS-06/07/08, AUDIT-02)** — `e199b79` (feat)

## Service Function Signatures

Verbatim from `apps/backend/app/modules/clients/service.py`:

```python
async def list_clients(
    session: AsyncSession,
    query: ClientListQuery,
) -> PaginatedData[ClientResponse]: ...

async def get_client(
    session: AsyncSession,
    client_id: UUID,
) -> ClientResponse: ...

async def create_client(
    session: AsyncSession,
    actor: User,
    data: ClientCreateRequest,
) -> ClientResponse: ...

async def update_client(
    session: AsyncSession,
    actor: User,
    client_id: UUID,
    data: ClientUpdateRequest,
) -> ClientResponse: ...

async def soft_delete_client(
    session: AsyncSession,
    actor: User,
    client_id: UUID,
) -> None: ...
```

All five functions are module-level async (D-18). All three mutation functions take `actor: User` second-positional (D-19).

## D-08 Audit Payload Mapping

| Event                | resource_type | resource_id | payload keys                              | Rationale |
|----------------------|---------------|-------------|--------------------------------------------|-----------|
| `client_created`     | `'client'`    | `client.id` | `full_name`, `phone`, `has_email`, `has_telegram` | Minimal PD-safe surface; full state reconstructable via clients table + created_at. Excludes notes / birthday / emergency_contact (T-08-31 mitigation). |
| `client_updated`     | `'client'`    | `client.id` | `changed_fields` (sorted list); `previous_phone` (only when phone in changed) | Diff-only payload (D-08). `previous_phone` enables phone-conflict reconstruction without storing full before-image. |
| `client_soft_deleted`| `'client'`    | `client.id` | `full_name`, `phone`                       | Captured pre-deletion (T-08-33 mitigation) so audit-log read endpoint v1.2 can name the deleted client without joining a soft-deleted row. |

## D-02 Compliance — No Runtime Client Import

```bash
$ ! grep -E "^from app\.modules\.clients\.models import Client$" apps/backend/app/modules/clients/service.py
# (succeeds — pattern not found)
```

The only reference to `Client` is inside a `TYPE_CHECKING` block (lines 54-55), so mypy keeps strong typing on the `_full_name(client: "Client") -> str` helper while the runtime module imports nothing from `app.modules.clients.models`. CLIENTS-09 guarantee preserved.

## Flush / Emit Ordering Rationale

| Function              | Order                                        | Why |
|-----------------------|----------------------------------------------|-----|
| `create_client`       | insert → **flush** → emit                    | IntegrityError on `uq_clients_phone_alive` surfaces only on flush. Cannot emit before knowing the row took. |
| `update_client`       | mutate → **flush** → emit                    | Phone change risks `uq_clients_phone_alive`; flush early to surface conflict, then emit. No-op short-circuits before either. |
| `soft_delete_client`  | mutate → emit → **flush**                    | Soft-delete only flips `deleted_at`; no constraint risk; emit-before-flush pattern from PATTERNS.md applies. |

In all three cases the route exit (`get_db` async context manager) commits the transaction containing both the client mutation row and the `audit_log` INSERT atomically (D-03 co-transactional).

## Files Created/Modified

- `apps/backend/app/modules/clients/service.py` (created, 224 lines) — Orchestration layer; 5 async service functions + `_full_name` + `_is_phone_conflict` helpers.

## Decisions Made

- **`if TYPE_CHECKING`** for `Client` ORM type-only import (D-02 strict compliance — runtime never imports, mypy still type-checks).
- **`_is_phone_conflict(exc)` helper** centralises the constraint-name detection (`getattr(exc.orig, "constraint_name", None)` then substring fallback) so create + update share the exact same branch.
- **`session.rollback()`** is called in the IntegrityError branch before raising `PhoneExistsError`; otherwise the route-level commit attempt would re-raise the same IntegrityError as a 500.
- **`sorted(changed_previous.keys())`** for `changed_fields` payload — gives stable ordering for downstream audit-read UI grouping.

## Deviations from Plan

### Plan-acknowledged Issues (NOT auto-fixed — out of scope)

**1. [Pre-existing — Plan 08-04] `repository.py` runtime import error**
- **Observed during:** Task 1 verification step `uv run python -c "from app.modules.clients.service import ..."`.
- **Issue:** `apps/backend/app/modules/clients/repository.py:47` declares `async def list_alive(...) -> PaginatedData[Client]:` — without `from __future__ import annotations`, the annotation is evaluated at module-load and Pydantic raises `PydanticSchemaGenerationError` because `Client` is a SQLAlchemy ORM class, not a Pydantic-compatible type.
- **Plan 08-04 SUMMARY explicitly accepted this** (see "Self-Check: PASSED" section of `08-04-SUMMARY.md`): `python -c "from app.modules.clients.repository import ..."` listed as "Fails — same root cause".
- **Why not fixed here:** Plan 08-06 `files_modified` is restricted to `apps/backend/app/modules/clients/service.py`. Touching `repository.py` is out of scope per executor scope-boundary rule. The fix is trivial (`from __future__ import annotations` at the top of repository.py, or change return type to `PaginatedData[Any]`) and belongs to Plan 08-04 follow-up or Plan 08-08 test wiring.
- **Impact on this plan:** The runtime import test in `<verify>` cannot succeed today, but the static analysis verifications (ruff + mypy on service.py + grep checks) all pass. Plan 08-08 (tests) will need to address repository import as a prerequisite.
- **Tracked in:** `.planning/phases/08-clients-module-audit-log/08-04-SUMMARY.md` "Self-Check: PASSED" section + repository.py line 47.

**2. [Pre-existing — Plan 08-04] `mypy --strict` reports `no-any-return` on `repository.py:42`**
- **Observed during:** Task 1 + Task 2 mypy verification.
- **Issue:** `app/modules/clients/repository.py:42: error: Returning Any from function declared to return "Client | None" [no-any-return]`.
- **Plan 08-04 SUMMARY explicitly accepted this** ("cascades into one `no-any-return` for `session.scalar`").
- **Why not fixed here:** Same scope-boundary as #1.
- **Impact:** mypy on `service.py` cascades to repository.py and surfaces this single pre-existing error. Service.py itself contributes zero mypy errors.

### Auto-fixed Issues

None — plan executed as written for service.py. All Rule 1/2/3 deviations would have required touching files outside this plan's scope.

---

**Total deviations:** 0 auto-fixed (2 pre-existing issues from Plan 08-04 explicitly noted but out-of-scope to fix here).
**Impact on plan:** Static verification passes. Runtime import will start working once Plan 08-04's documented `repository.py` issues are resolved.

## Issues Encountered

- Initial Task 1 draft included Task 2 imports up-front (per PLAN.md guidance) — ruff F401 flagged them as unused while only Task 1 was committed. Resolved by deferring Task 2 imports to the Task 2 edit; final state has all imports at top of file once Task 2 is applied.

## TDD Gate Compliance

N/A — plan is `type: execute` (not `type: tdd`). Tests for the service live in Plan 08-08.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- **Plan 08-07 (router)** can now `from app.modules.clients import service` and wire endpoints to `service.list_clients / get_client / create_client / update_client / soft_delete_client`.
- **Plan 08-08 (tests)** needs to first resolve Plan 08-04's documented `repository.py` annotation-evaluation issue (add `from __future__ import annotations` or equivalent) before integration tests can import the service module at runtime. Static analysis is unblocked today.
- All five service functions take consistent `(session, [actor], ...)` signatures; router can compose them with FastAPI dependencies (`get_db`, `require_permission(Action.X, Resource.CLIENTS)`) without further service-side changes.

## Self-Check: PASSED

- File exists: `apps/backend/app/modules/clients/service.py` — **FOUND**
- Commit `a925d0b` (Task 1) — **FOUND** in `git log --oneline`
- Commit `e199b79` (Task 2) — **FOUND** in `git log --oneline`
- All 5 exports present: `list_clients`, `get_client`, `create_client`, `update_client`, `soft_delete_client` — **FOUND** via grep
- D-02 architectural rule: no runtime `from app.modules.clients.models import Client` — **VERIFIED** by negative grep
- ruff: clean on `app/modules/clients/service.py`
- mypy --strict: zero errors attributable to `service.py`; only one pre-existing cascade error in repository.py (Plan 08-04 deferred)

---

*Phase: 08-clients-module-audit-log*
*Completed: 2026-05-03*
