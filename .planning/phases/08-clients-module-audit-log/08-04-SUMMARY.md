---
phase: 08-clients-module-audit-log
plan: 04
subsystem: clients
tags: [repository, sqlalchemy, soft-delete, pagination, search]
requires:
  - 08-01 (Client ORM + Gender)
  - 08-03 (schemas: ClientCreateRequest/UpdateRequest/ListQuery/Sort + EmergencyContact) — wave 2 sibling
provides:
  - "list_alive(session, query) -> PaginatedData[Client]"
  - "get_alive(session, client_id) -> Client | None"
  - "insert_client(session, actor_user_id, data) -> Client"
  - "update_client(session, client, data) -> dict[str, object]"
  - "soft_delete_client(session, client) -> Client"
affects:
  - app/modules/clients/service.py (Plan 06 — sole consumer)
tech_stack:
  added: []
  patterns:
    - "Repository pattern (D-02): repository owns all select(Client); service never imports Client"
    - "Soft-delete invariant: WHERE deleted_at IS NULL applied in every read helper"
    - "Pagination via separate count() query reusing same predicate list"
    - "Parameterised ARRAY containment: text(':tag = ANY(clients.tags)').bindparams(tag=...)"
    - "Caller owns transaction (D-03) — no session.commit/flush in repository"
key_files:
  created:
    - apps/backend/app/modules/clients/repository.py
  modified: []
decisions: []
metrics:
  duration_seconds: 0
  duration_human: "~12 min"
  completed_at: "2026-05-03T08:56:41Z"
  tasks_completed: 2
  files_changed: 1
commits:
  - { hash: "069a8ed", task: "Task 1 — read helpers (get_alive, list_alive)" }
  - { hash: "6abc1a2", task: "Task 2 — write helpers (insert/update/soft_delete)" }
---

# Phase 8 Plan 04: Clients Repository Summary

**One-liner:** `app/modules/clients/repository.py` — single async repository module owning every `select(Client)` and Client mutation, enforcing soft-delete + pagination + filter/sort contract for the upcoming service layer.

## Outcome

Created `apps/backend/app/modules/clients/repository.py` with five module-level async functions. This is now the ONLY file in the codebase that imports `Client` from `app.modules.clients.models` — the constructive guarantee for CLIENTS-09 ("all queries through `list_alive`/`get_alive`"). The service layer (Plan 06) cannot accidentally bypass the soft-delete predicate because it has no reference to the ORM table.

## Exports

| Function | Signature | Responsibility |
|---|---|---|
| `get_alive` | `(session, client_id: UUID) -> Client \| None` | Fetch one alive client; returns `None` for missing OR soft-deleted. CLIENTS-05. |
| `list_alive` | `(session, query: ClientListQuery) -> PaginatedData[Client]` | Paginated, filtered, sorted list of alive clients. CLIENTS-03/04. |
| `insert_client` | `(session, actor_user_id: UUID, data: ClientCreateRequest) -> Client` | `session.add(Client(...))`; serialises `emergency_contact` via `.model_dump()`. CLIENTS-02 supporting. |
| `update_client` | `(session, client: Client, data: ClientUpdateRequest) -> dict[str, object]` | Apply PATCH via `model_dump(exclude_unset=True)`; returns `{field: previous_value}` for changed fields. Service uses for D-08 (`previous_phone` audit payload) and D-09 (no-op skip). |
| `soft_delete_client` | `(session, client: Client) -> Client` | Sets `client.deleted_at = datetime.now(tz=UTC)`. Never DELETE the row. CLIENTS-08. |

## Filter Coverage Matrix (`list_alive`)

| `ClientListQuery` field | SQL predicate | Decision |
|---|---|---|
| (always) | `Client.deleted_at IS NULL` | CLIENTS-05/09 invariant |
| `q` (≥2 chars; DTO normalises shorter to `None`) | `lower(last_name \|\| ' ' \|\| first_name \|\| ' ' \|\| coalesce(middle_name, '')) ILIKE :pattern OR phone ILIKE :pattern` | D-12 |
| `tag` | `text(':tag = ANY(clients.tags)').bindparams(tag=query.tag)` | D-13 (parameterised, no SQL injection) |
| `gender` | `Client.gender = :gender` | D-14 |
| `created_from` | `Client.created_at >= :created_from` | D-14 (DTO already gives UTC `00:00:00.000`) |
| `created_to` | `Client.created_at <= :created_to` | D-14 (DTO already gives UTC `23:59:59.999999`) |
| `has_telegram == True` | `Client.telegram_user_id IS NOT NULL` | D-14 |
| `has_telegram == False` | `Client.telegram_user_id IS NULL` | D-14 |
| `sort = LAST_NAME_ASC` | `ORDER BY last_name ASC, created_at DESC` | CLIENTS-04 (`created_at DESC` tie-breaker for stability) |
| `sort = CREATED_AT_DESC` (default) | `ORDER BY created_at DESC, id DESC` | CLIENTS-04 (`id DESC` tie-breaker for stability) |
| `page` / `page_size` | `LIMIT :page_size OFFSET (:page - 1) * :page_size` | D-10 pagination contract |

Total count uses a separate `select(func.count()).select_from(Client).where(and_(*predicates))` over the same predicate list (no ORDER/LIMIT) — cheaper than wrapping the items query in `func.count(*)`.

## Architecture Highlights

- **CLIENTS-09 enforced constructively:** the service layer (Plan 06) imports only repository functions, not `Client`. Even an inattentive developer cannot write `select(Client)` outside this file because the symbol is not in scope.
- **Transaction control (D-03):** zero `session.commit()` and zero `session.flush()` in source code. The caller (service) owns the transactional moment so the audit row INSERT and Client mutation share one UoW.
- **Update return contract (D-08/D-09):** `update_client` returns a dict of `{field_name: previous_value}` for each field whose value actually changed. The service uses an empty dict to short-circuit and skip the audit emit (D-09 no-op skip), and reads `previous_phone` out of the dict for the audit payload (D-08).
- **`emergency_contact` JSONB serialisation (D-17):** both `insert_client` and `update_client` call `.model_dump()` on the `EmergencyContact` Pydantic instance before assigning to the JSONB column.

## Verification

- `cd apps/backend && uv run ruff check app/modules/clients/repository.py` → **clean** (zero warnings).
- `grep` checks for required patterns (`Client.deleted_at.is_(None)`, `:tag = ANY(clients.tags)`, `ClientSort.LAST_NAME_ASC`, `Client.created_at.desc()`, `client.deleted_at = datetime.now`, `session.add(client)`) → **all present**.
- `grep -nE "^\s*(await\s+)?(session\.commit\(|session\.flush\()"` on the file → **zero matches** (no transactional control inside repository code).
- All five exports named in plan are defined as `async def` at module level.

### Deferred (parallel-worktree artefact)

This plan runs in **wave 2** parallel with **Plan 08-03 (schemas)**. In this worktree, `apps/backend/app/modules/clients/schemas.py` does not yet exist — it is committed by the sibling worktree and merged at orchestrator wave-join time. Verify steps that import from `app.modules.clients.schemas` (the `python -c "from ..."` checks and `mypy --strict`) cannot pass in isolation here:

| Verify | Status in worktree | Resolution |
|---|---|---|
| `python -c "from app.modules.clients import repository; assert callable(repository.get_alive); ..."` | Fails — `ModuleNotFoundError` on `schemas` | Re-run after Plan 03 merges; orchestrator wave-join verifier |
| `python -c "from app.modules.clients.repository import list_alive, get_alive, insert_client, update_client, soft_delete_client"` | Fails — same root cause | Same |
| `mypy --strict app/modules/clients/repository.py` | Fails — `import-not-found` for `app.modules.clients.schemas`; cascades into one `no-any-return` for `session.scalar` | Same |
| `ruff check app/modules/clients/repository.py` | **PASS** | — |

These import-time checks are expected to pass after merge with Plan 03's `schemas.py`. The repository code itself is final and matches the plan spec verbatim.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Tooling] ruff UP017 — `datetime.timezone.utc` → `datetime.UTC`**
- **Found during:** Task 2 (ruff check after appending write helpers).
- **Issue:** `datetime.timezone.utc` is the legacy import; project's ruff config flags it (`UP017`).
- **Fix:** Switched import to `from datetime import UTC, datetime` and call site to `datetime.now(tz=UTC)`.
- **Files modified:** `apps/backend/app/modules/clients/repository.py`
- **Commit:** `6abc1a2`

**2. [Rule 3 — Tooling] ruff SIM102 — collapsed nested `if` in `update_client`**
- **Found during:** Task 2 (ruff check).
- **Issue:** Nested `if key == "emergency_contact" and value is not None: if isinstance(value, EmergencyContact): ...` triggers `SIM102`.
- **Fix:** Combined into a single `if (... and isinstance(value, EmergencyContact)):` clause; semantics preserved (the `dict` fall-through case is now expressed by the absence of the assignment, which was always the intent).
- **Files modified:** `apps/backend/app/modules/clients/repository.py`
- **Commit:** `6abc1a2`

**3. [Rule 3 — Tooling] explicit `Select[tuple[Client]]` annotation in `get_alive`**
- **Found during:** Task 1 (mypy `no-any-return` on `session.scalar`).
- **Issue:** Without an explicit `Select` type variable, mypy treats `session.scalar(select(Client).where(...))` as returning `Any`, which violates `--strict --no-any-return`.
- **Fix:** Bind the select to `stmt: Select[tuple[Client]]` first, then `await session.scalar(stmt)`. Matches the pattern already used in `list_alive`.
- **Files modified:** `apps/backend/app/modules/clients/repository.py`
- **Commit:** `069a8ed` (applied before initial commit).

### Authentication Gates

None. Repository is a pure-Python file; no external services.

## Threat Flags

None. The file introduces no new trust boundaries beyond those already itemised in the plan's `<threat_model>`. T-08-19 / T-08-20 (SQL injection via `q` and `tag`) are mitigated as planned: `Client.phone.ilike(f"%{query.q}%")` and `func.lower(...).ilike(like_pattern)` rely on SA Core parameter binding, and `text(":tag = ANY(clients.tags)").bindparams(tag=query.tag)` is a parameterised bind, not string interpolation.

## Known Stubs

None. All five exports are fully implemented per spec.

## TDD Gate Compliance

This plan is `type: execute`, not `type: tdd`. No RED/GREEN/REFACTOR sequence required. Tests for these helpers are produced by Plan **08-08** (Tests — Repository + Service + API), which depends on this plan.

## Self-Check: PASSED

- File exists: `apps/backend/app/modules/clients/repository.py` — **FOUND**
- Commit `069a8ed` (Task 1) — **FOUND** in `git log --oneline`
- Commit `6abc1a2` (Task 2) — **FOUND** in `git log --oneline`
- All five `async def` exports present in file (`get_alive`, `list_alive`, `insert_client`, `update_client`, `soft_delete_client`) — **VERIFIED**
- ruff clean — **VERIFIED**
- No `session.commit(`/`session.flush(` calls in code — **VERIFIED** (only doc-string mention)
