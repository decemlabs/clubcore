# Phase 24: Foundations & Tech-Debt Bedrock — Pattern Map

**Mapped:** 2026-05-08
**Files analyzed:** 16 (15 modified + 1 net-new migration)
**Analogs found:** 16 / 16
**Mode:** GSD pattern mapping (no RESEARCH.md — extracted from CONTEXT.md `<canonical_refs>`)

> All pattern excerpts below are verbatim from the existing codebase, addressed by absolute path + line number. The planner should reference this file from each plan's `## Action` section instead of restating the patterns.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `apps/backend/alembic/versions/0007_status_taxonomy.py` (NEW) | migration | DDL CHECK extension | `apps/backend/alembic/versions/0006_visits.py` (chain head) + `0005_memberships.py` (CHECK origin) | **role-match** — first ALTER-only migration in the project; pattern composed from `op.execute()` raw-SQL precedent in 0005/0006 |
| `apps/backend/app/core/audit.py` (MODIFY) | core constant + emit helper | static frozenset extension | self — append v1.3 block to lines 78-126 frozenset literal | **exact** (file already structured for additive blocks) |
| `apps/backend/app/modules/memberships/constants.py` (NEW) | module constant (read-only mapping) | static lookup | none in `app/` — closest precedent is `LOCKED_AUDIT_EVENTS` (`audit.py:78`) using `frozenset` and `app/core/rbac.py` `OWNER_ONLY` matrix | **role-match** — adopt `MappingProxyType` pattern (CONTEXT D-24-03) |
| `apps/backend/app/modules/memberships/models.py:144-161` (MODIFY) | ORM model `__table_args__` | DDL DSL | self — modify CheckConstraint string in-place; ORM mirror of D-24-02 SQL | **exact** |
| `apps/backend/app/modules/memberships/service.py` (MODIFY — add `_assert_can_transition`, refactor cancel/expire guards, add `today` kwarg to resolver) | service (orchestration) | request-response + system cron | self at lines 104-129 (per-transition guards), 472-489 (resolver public wrapper), 497-543 (`_expire_due_memberships(today=None)` injection pattern) | **exact** |
| `apps/backend/app/modules/memberships/repository.py:283-305` (MODIFY — add `today` kwarg, `end_date >= today` predicate, reverse docstring; extend `list_memberships` for `expiring`/`within`) | repository (SQL query builder) | CRUD select | self at lines 283-305 (`find_active_for_client`) + lines 313-349 (`expire_due_rows` `end_date <` predicate) + lines 205-257 (`list_memberships` predicate composition) | **exact** |
| `apps/backend/app/modules/memberships/schemas.py:235-247` (MODIFY — add `expiring` + `within` query fields) | DTO (Pydantic v2) | request validation | self — `MembershipPlanListQuery` at lines 123-128 (additive query field with `Field(default=...)`) | **exact** |
| `apps/backend/app/modules/memberships/router.py` (VERIFY only — no edit if `Annotated[..., Depends()]` already wraps the query) | router | request-response | self at lines 215-232 (`list_memberships` endpoint with `Annotated[MembershipListQuery, Depends()]`) | **exact** (likely zero-edit verification) |
| `apps/backend/app/modules/auth/service.py` (MODIFY — add explicit `await session.commit()` to public write paths) | service (orchestration) | request-response | `apps/backend/app/modules/clients/service.py:109-144` (Phase 12.1 fix exemplar) and self at lines 290-314 (`revoke_sessions_on_password_change` already commits) and 486-549 (`revoke_session` already commits) and 710-775 (`revoke_family` already commits) | **exact** — pattern already used in this file for newer functions; gap is in older `authenticate`/`issue_tokens`/`rotate_refresh` paths |
| `apps/backend/tests/unit/test_service_commit_gate.py:167-211` (MODIFY — add `_AUTH_SERVICE` to inspected tuple) | test (AST static walker) | scan + assert | self at lines 167-211 (existing `_INSPECTED_SERVICES` tuple + offender loop) | **exact** |
| `apps/backend/tests/unit/test_audit_taxonomy.py` (MODIFY — bump count assert + 6 new pair assertions) | test (AST static walker) | scan + assert | self at lines 164-178 (`test_locked_audit_events_has_expected_count`) | **exact** |
| `apps/backend/tests/unit/memberships/test_state_machine.py` (MODIFY — exercise `_assert_can_transition` in addition to per-helper guards) | test (parametrize unit) | pure function call | self at lines 60-91 (9-cell matrix); D-24-05 keeps shape | **exact** |
| `apps/backend/tests/integration/memberships/test_resolver.py` (MODIFY — add `test_resolver_filters_expired_active_row`) | integration test (httpx) | DB fixture + assert | self at lines 103-117 (`test_resolver_returns_none_for_expired_only_client`) — closest existing case; new test inserts active+stale row | **exact** |
| `apps/admin-web/src/shared/api/services/mock/memberships.ts:28-57` (MODIFY — accept `query.within: number = 7`) | mock service | in-memory filter | self at lines 43-52 (existing `query.expiring` branch) | **exact** |
| `apps/admin-web/src/shared/api/services/http/memberships.ts:38-81` (MODIFY — forward `expiring`+`within`, drop client-side filter + BLK-06 collapse) | http service | network adapter | self at lines 68-79 (existing client-side filter to be removed) + sibling `listPlans` at lines 127-137 (canonical "forward query params" shape) | **exact** |
| `apps/admin-web/src/shared/api/contracts/memberships.ts` (VERIFY — add `within?: number` to `MembershipsListQuery`) | TS interface | static type | self at lines 9-14 | **exact** |

---

## Pattern Assignments

### 1. `apps/backend/alembic/versions/0007_status_taxonomy.py` (NEW)

**Role:** Alembic migration. **Data flow:** DDL — CHECK constraint replacement only (no columns, no tables).

**Analogs:**
- `apps/backend/alembic/versions/0006_visits.py` — chain-head template (revision wiring + `op.execute()` raw-SQL).
- `apps/backend/alembic/versions/0005_memberships.py:78-81` — original `ck_memberships_status` CHECK string this migration must DROP and re-CREATE.

**Revision header pattern** (from `0006_visits.py:31-34`):
```python
revision: str = "0007_status_taxonomy"
down_revision: str | None = "0006_visits"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```

**Raw-SQL `op.execute()` precedent** (from `0006_visits.py:113-116`):
```python
op.execute(
    "CREATE INDEX ix_visits_client_id_checked_in_at "
    "ON visits (client_id, checked_in_at DESC)"
)
```

**Original CHECK that must be replaced** (`0005_memberships.py:78-81`):
```python
sa.CheckConstraint(
    "status IN ('active', 'expired', 'cancelled')",
    name=op.f("ck_memberships_status"),
),
```

**Apply to plan:** `upgrade()` issues two `op.execute()` statements per CONTEXT D-24-02:
```python
op.execute("ALTER TABLE memberships DROP CONSTRAINT ck_memberships_status")
op.execute(
    "ALTER TABLE memberships ADD CONSTRAINT ck_memberships_status "
    "CHECK (status IN ('active','expired','cancelled','frozen'))"
)
```
`downgrade()` reverses to the v1.2 three-status form. **No column adds, no index touches** — that index (`ix_memberships_client_id_status_end_date`) stays exactly as 0005 left it; DEBT-01 still uses it.

---

### 2. `apps/backend/app/core/audit.py` (MODIFY — extend `LOCKED_AUDIT_EVENTS`)

**Role:** core constant + emit helper. **Data flow:** static frozenset literal extension.

**Analog:** self at lines 78-126 — the file is already structured as additive version-blocks (v1.1 then v1.2 then v1.2 Phase 23). The v1.3 block follows the same shape.

**Existing v1.2 block tail** (`audit.py:112-124`):
```python
        # v1.2 (Phase 15 lock — emitted in Phases 16/17/19/20)
        ("membership_plan_created", "membership_plan"),
        ("membership_plan_updated", "membership_plan"),
        ("membership_plan_archived", "membership_plan"),
        ("membership_created", "membership"),
        ("membership_cancelled", "membership"),
        ("membership_expired", "membership"),
        ("visit_created", "visit"),
        ("visit_rejected_no_membership", "visit"),
        ("visit_rejected_duplicate", "visit"),
        ("visit_rejected_outside_hours", "visit"),
        # Phase 20 — bot self check-in: stranger /checkin lands here (D-20-10).
        ("telegram_unknown_checkin", "visit"),
```

**Apply to plan:** append the six pairs from CONTEXT D-24-18 inside the same frozenset literal, in the order specified, under a new comment header `# v1.3 (Phase 24 lock — emitted in Phases 25/26/27)`. Also extend the docstring inventory at lines 18-54 to mirror the new block (matches existing convention).

**Hard-fail invariant to preserve** (`audit.py:69-75`):
```python
class AuditEventNotLockedError(ValueError):
    """Raised by audit.emit() when (event, resource_type) ∉ LOCKED_AUDIT_EVENTS.

    Hard fail in dev AND prod (Phase 15 D-09): unknown audit pair = programmer
    error (stale callsite or unlocked taxonomy). NO graceful degradation, NO
    DEBUG-only assert. Tests catch this exception explicitly.
    """
```
INFRA-15's reason for shipping in Phase 24: callsites land in 25/26/27 and would crash without the frozenset extension already in place.

---

### 3. `apps/backend/app/modules/memberships/constants.py` (NEW)

**Role:** module constant — read-only Mapping[str, frozenset[str]] of allowed transitions.

**Analogs:**
- `audit.py:78` — `LOCKED_AUDIT_EVENTS: frozenset[tuple[str, str]] = frozenset({...})` — module-level constant pattern.
- The constant must be importable from `models.py` (CHECK string lives there) without circular import — keep `str` keys, NOT the `MembershipStatus` StrEnum.

**Apply to plan** (verbatim from CONTEXT D-24-03):
```python
from collections.abc import Mapping
from types import MappingProxyType

MEMBERSHIP_STATUS_TRANSITIONS: Mapping[str, frozenset[str]] = MappingProxyType({
    "active":    frozenset({"expired", "cancelled"}),  # Phase 25 will add "frozen"
    "expired":   frozenset(),                          # Phase 26 may extend for renewal mechanics
    "cancelled": frozenset(),                          # terminal
    "frozen":    frozenset(),                          # Phase 25 will add {"active", "cancelled"}
})
```

**Top-doc rationale** (mirror `service.py:1-37` style — module-level docstring explains shape + Phase 25 extension contract). REQUIREMENTS INFRA-16 names the file path verbatim, so creating it here keeps Phase 25's blast radius small.

---

### 4. `apps/backend/app/modules/memberships/models.py:144-161` (MODIFY — CheckConstraint string)

**Role:** ORM model `__table_args__`. **Data flow:** SQLAlchemy DSL.

**Analog:** self at lines 144-161 — modify the CheckConstraint string only. Index stays untouched (DEBT-01 still uses it).

**Current shape** (`models.py:144-161`):
```python
__table_args__ = (
    CheckConstraint(
        "status IN ('active', 'expired', 'cancelled')",
        # NAMING_CONVENTION expands to ck_memberships_status
        name="status",
    ),
    CheckConstraint(
        "activation_policy = 'purchase_date'",
        name="activation_policy",
    ),
    Index(
        "ix_memberships_client_id_status_end_date",
        "client_id",
        "status",
        text("end_date DESC"),
    ),
)
```

**Apply to plan:** replace the first CheckConstraint string literal with `"status IN ('active', 'expired', 'cancelled', 'frozen')"`. Both `activation_policy` constraint and the composite index are unchanged.

---

### 5. `apps/backend/app/modules/memberships/service.py` (MODIFY)

**Role:** service orchestration. **Data flow:** request-response (cancel/transition guards) + system cron (resolver from visits/checkin).

#### 5a. New central guard `_assert_can_transition(membership, *, target)`

**Analog (per-helper shape to delegate from):** `service.py:104-129`
```python
def _assert_can_cancel(membership: Membership) -> None:
    """Phase 17 D-12 + D-15: only status='active' may transition to 'cancelled'."""
    if membership.status != "active":
        raise InvalidTransitionError(
            "invalid_transition",
            fields={"from_status": membership.status, "to_status": "cancelled"},
        )


def _assert_can_expire(membership: Membership) -> None:
    """Phase 17 D-19: only status='active' may transition to 'expired'."""
    if membership.status != "active":
        raise InvalidTransitionError(
            "invalid_transition",
            fields={"from_status": membership.status, "to_status": "expired"},
        )
```

**Apply to plan:** new module-private helper `_assert_can_transition(membership, *, target: str) -> None` reads `MEMBERSHIP_STATUS_TRANSITIONS` from the new `constants.py`, looks up `MEMBERSHIP_STATUS_TRANSITIONS.get(membership.status, frozenset())`, and raises `InvalidTransitionError("invalid_transition", fields={"from_status": membership.status, "to_status": target})` when `target` is not in that set. The two existing helpers become thin wrappers (CONTEXT D-24-05): `_assert_can_cancel = lambda m: _assert_can_transition(m, target="cancelled")` (or thin `def` wrappers preserving signature for the unit test imports at `tests/unit/memberships/test_state_machine.py:28`).

**Reuse — do NOT add a new exception** (`exceptions.py:158-172`):
```python
class InvalidTransitionError(ConflictError):
    """Raised on POST /memberships/{id}/cancel for non-active source state (Phase 17 D-12).
    ...
    Usage:
        raise InvalidTransitionError(
            "invalid_transition",
            fields={"from_status": membership.status, "to_status": "cancelled"},
        )
    """
    code = "invalid_transition"
    status_code = 409
```

#### 5b. `today` kwarg on `resolve_active_membership_by_client`

**Canonical injection-pattern analog** (`service.py:497-543` — pulled tight to the `today` block):
```python
async def _expire_due_memberships(  # noqa: SVC001 caller-owns-txn
    session: AsyncSession,
    today: date | None = None,
) -> int:
    ...
    if today is None:
        today = datetime.now(ZoneInfo("Europe/Moscow")).date()

    rows = await repository.expire_due_rows(session, today)
    ...
```

**Existing public wrapper to modify** (`service.py:472-489`):
```python
async def resolve_active_membership_by_client(
    session: AsyncSession,
    client_id: UUID,
) -> Membership | None:
    """Return the canonical active membership for `client_id`, or None (MEM-04, CD-06)."""
    return await repository.find_active_for_client(session, client_id)
```

**Apply to plan:** signature becomes `resolve_active_membership_by_client(session, client_id, *, today: date | None = None)` and resolves `today=None` to `datetime.now(ZoneInfo("Europe/Moscow")).date()` BEFORE delegating to repository. Pass `today=today` through. The Protocol `ActiveMembershipResolver` at `dependencies.py:81` is `Callable[[AsyncSession, UUID], Awaitable[ActiveMembership | None]]` — keyword-only `today` with default keeps this assignment shape valid (mypy-strict verified by the planner per CONTEXT risk note).

---

### 6. `apps/backend/app/modules/memberships/repository.py:283-305` (MODIFY)

**Role:** repository SQL query builder. **Data flow:** CRUD select.

#### 6a. `find_active_for_client` — `today` kwarg + `end_date >= today` predicate + reversed docstring

**Current docstring is the explicit anti-pattern to REVERSE** (`repository.py:283-305`):
```python
async def find_active_for_client(
    session: AsyncSession, client_id: UUID
) -> Membership | None:
    """Return the canonical active membership for `client_id`, or None (MEM-04).

    Tiebreak: ORDER BY end_date DESC, created_at DESC LIMIT 1 (D-17 — silent,
    no structlog warning, no audit event). The composite index
    `ix_memberships_client_id_status_end_date` on
    `(client_id, status, end_date DESC)` covers this query.

    Date filter is intentionally NOT applied here: per D-13, status field is
    the gate, not end_date. Phase 18 ARQ flips status -> 'expired' on its own
    cadence; until then a row whose end_date has passed but whose status is
    still 'active' is the canonical row.
    """
    stmt = (
        select(Membership)
        .where(Membership.client_id == client_id, Membership.status == "active")
        .order_by(Membership.end_date.desc(), Membership.created_at.desc())
        .limit(1)
    )
    result: Membership | None = await session.scalar(stmt)
    return result
```

**Predicate analog to copy** — `expire_due_rows` already encodes the `end_date < today` shape (`repository.py:342-348`):
```python
stmt = (
    update(Membership)
    .where(Membership.end_date < today, Membership.status == "active")
    .values(status="expired")
    .returning(Membership.id, Membership.client_id)
)
```

**Apply to plan:**
- Signature becomes `find_active_for_client(session, client_id, *, today: date)` (caller resolves None → MSK today before calling — keeps the repository pure/testable).
- Add `Membership.end_date >= today` to the WHERE chain (third predicate, AND).
- Rewrite docstring per CONTEXT D-24-08: cite DEBT-01 + missed-ARQ-tick scenario as defence-in-depth rationale; replace the "Date filter is intentionally NOT applied here" paragraph entirely.
- Index `ix_memberships_client_id_status_end_date` on `(client_id, status, end_date DESC)` is range-scan friendly on the rightmost column — no index change needed (CONTEXT D-24-07).

#### 6b. `list_memberships` — extend for `expiring`/`within`

**Analog (predicate composition shape)** — `list_memberships` at `repository.py:205-257`:
```python
predicates: list[Any] = []
if query.client_id is not None:
    predicates.append(Membership.client_id == query.client_id)
if query.status is not None:
    predicates.append(Membership.status == query.status.value)

where_clause = and_(*predicates) if predicates else true()
```

**Apply to plan** (CONTEXT D-24-10..D-24-12):
- Resolve `today = datetime.now(ZoneInfo("Europe/Moscow")).date()` once at function head when `query.expiring` is True.
- When `query.expiring`:
  - Force `Membership.status == "active"` (override any user-supplied `status` filter — but if `query.status is not None and query.status != MembershipStatus.ACTIVE`, raise `ValidationAppError("query_invalid", fields={"status": "incompatible_with_expiring"})` per D-24-11).
  - Append `Membership.end_date >= today AND Membership.end_date <= today + (query.within - 1)` (inclusive end-date semantics — same `end_date < today` mirror that `expire_due_rows` uses, but inclusive).
- When `query.expiring is False`: ignore `query.within` silently.
- Pagination envelope (`PaginatedData.model_construct`) and sort logic are untouched. The http adapter's BLK-06 single-page collapse goes away because the backend now paginates the filtered set honestly.

---

### 7. `apps/backend/app/modules/memberships/schemas.py:235-247` (MODIFY)

**Role:** Pydantic v2 query DTO. **Data flow:** request validation.

**Analog (additive query field with `Field(default=...)`)** — `MembershipPlanListQuery` at `schemas.py:123-128`:
```python
class MembershipPlanListQuery(PageQuery):
    """GET /api/v1/membership-plans query parameters (D-08)."""

    active: bool | None = None  # omit = include both active and inactive
    sort: MembershipPlanSort = MembershipPlanSort.CREATED_AT_DESC
```

**Current shape to extend** (`schemas.py:235-247`):
```python
class MembershipListQuery(PageQuery):
    """GET /api/v1/memberships query parameters (Phase 17 D-09).
    ...
    """
    client_id: UUID | None = None
    status: MembershipStatus | None = None
    sort: MembershipListSort = MembershipListSort.CREATED_AT_DESC
```

**Apply to plan** (CONTEXT D-24-10):
```python
expiring: bool = False
within: int = Field(default=7, ge=1, le=30)
```
No `model_validator` coupling between the two — repository decides whether to apply the predicate (D-24-10 explicit). FastAPI's `Annotated[MembershipListQuery, Depends()]` translates camelCase `expiring`/`within` query params to snake_case automatically via `BackendSchemaBase` (already in place).

---

### 8. `apps/backend/app/modules/memberships/router.py` (VERIFY)

**Analog (already in canonical shape)** — `router.py:215-232`:
```python
async def list_memberships(
    query: Annotated[MembershipListQuery, Depends()],
    _actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.VIEW, Resource.MEMBERSHIPS)),
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PaginatedData[MembershipResponse]]:
    """List memberships, paginated (MEM-EP-01)."""
    page = await service.list_memberships(session, query)
    return envelope(page)
```

**Apply to plan:** zero edits expected. The new `expiring`/`within` fields propagate automatically through `Annotated[MembershipListQuery, Depends()]`. Planner only needs to update the docstring's "Query parameters" inventory at lines 224-229 to enumerate the two new params. The OpenAPI surface change is the deferred concern in CONTEXT — Phase 28 owns the drift gate; this phase regenerates `apps/backend/openapi.json` if CI's drift check fires per commit (planner: confirm CI mode and decide).

---

### 9. `apps/backend/app/modules/auth/service.py` (MODIFY — explicit commits on public write paths)

**Role:** auth service orchestration. **Data flow:** request-response, but with Redis side-channel.

**The Phase 12.1 fix exemplar** (`apps/backend/app/modules/clients/service.py:109-144`):
```python
async def create_client(
    session: AsyncSession,
    actor: CurrentUser,
    data: ClientCreateRequest,
) -> ClientResponse:
    """Create a new client (CLIENTS-06).

    Order: insert → flush (surface DB constraints) → emit audit on success (D-03).
    """
    client = await repository.insert_client(session, actor.id, data)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if _is_phone_conflict(exc):
            raise PhoneExistsError("phone_exists") from exc
        raise

    await audit.emit(
        session,
        "client_created",
        actor_user_id=actor.id,
        resource_type="client",
        resource_id=client.id,
        ...
    )
    await session.commit()
    return ClientResponse.model_validate(client)
```

**Same-file functions that are ALREADY CORRECT** (use as in-file pattern reference):

`auth/service.py:290-314` — `revoke_sessions_on_password_change` already commits (template for `change_password` if it lands during planning):
```python
async def revoke_sessions_on_password_change(...) -> int:
    family_count = await revoke_all_sessions(session, redis, user_id)
    await audit.emit(
        session,
        "password_changed_revokes_sessions",
        actor_user_id=user_id,
        resource_type="user",
        resource_id=user_id,
        family_count=family_count,
    )
    await session.commit()
    return family_count
```

`auth/service.py:486-549` — `revoke_session` (single-family): SELECT → UPDATE → `audit.emit(session_revoked)` → `await session.commit()` → Redis cleanup outside tx. Identical "Pitfall 2" comment block at line 534 explains the ordering.

`auth/service.py:710-775` — `revoke_family` (per-family endpoint, Phase 23 HYG-03) — same `audit.emit` → `session.commit()` shape.

**Functions where the gap exists today** (the planner will verify the exact list during inventory):

| Function | Current end-of-write-path | What's missing |
|---|---|---|
| `authenticate` (lines 110-189) | emits `login_failed` or `login_success` then `return user` / `raise` | NO `await session.commit()` — audit row gets dropped on `get_db` rollback when caller exception fires downstream |
| `issue_tokens` (lines 197-245) | already has `await session.commit()` at line 232 — VERIFY only |
| `rotate_refresh` (lines 322-478) | uses `async with session.begin():` block (auto-commits on context exit) for the active-rotation branch — VERIFY this is the SVC001-walker-acceptable shape; the family-reuse branch at lines 446-467 emits inside the `async with` block, so the commit is implicit but present |
| `revoke_session` | already commits (line 543) — VERIFY only |
| `revoke_all_sessions` | already commits (line 603) — VERIFY only |
| `revoke_sessions_on_password_change` | already commits (line 313) — VERIFY only |
| `revoke_family` | already commits (line 767) — VERIFY only |

**Apply to plan:** the only confirmed gap is `authenticate` (both failure and success branches — three audit-emit sites at lines 153-161, 168-176, 179-188). Add `await session.commit()` immediately after each emit, BEFORE the `raise InvalidPassword(...)` / `return user` statements.

The SVC001 marker `# noqa: SVC001 caller-owns-txn` is **NOT** valid here — these are public functions (D-24-16). Use explicit commits.

**Deferred-scan note for `apps/backend/app/modules/auth/telegram_service.py`** — quick grep shows `audit.emit` at lines 102, 198, 274 each followed within ~7 lines by `await session.commit()` at lines 109, 205, 280. **This file is already clean — no DEBT-03 follow-up needed.** Planner can record this as a confirmed-clean note in the Phase 24 deferred list (closes the CONTEXT D-24-15 follow-up scan question).

---

### 10. `apps/backend/tests/unit/test_service_commit_gate.py:167-211` (MODIFY)

**Role:** AST static walker test. **Data flow:** scan + assert.

**Current state to extend** (`test_service_commit_gate.py:167-211`):
```python
_CLIENTS_SERVICE = _BACKEND_APP / "modules" / "clients" / "service.py"
_MEMBERSHIPS_SERVICE = _BACKEND_APP / "modules" / "memberships" / "service.py"
_INSPECTED_SERVICES: tuple[Path, ...] = (_CLIENTS_SERVICE, _MEMBERSHIPS_SERVICE)
...
def test_service_commit_gate_against_app_modules() -> None:
    """Live gate against clients/service.py and memberships/service.py (post-12.1 fix).
    ...
    """
    offenders: list[str] = []
    for service_path in _INSPECTED_SERVICES:
        assert service_path.is_file(), (
            f"Expected service file at {service_path} — phase fixture drift?"
        )
        for func in _iter_functions_in_file(service_path):
            msg = _check_function(service_path, func)
            if msg is not None:
                offenders.append(msg)
    assert not offenders, ...
```

**Apply to plan** (CONTEXT D-24-14):
```python
_AUTH_SERVICE = _BACKEND_APP / "modules" / "auth" / "service.py"
_INSPECTED_SERVICES: tuple[Path, ...] = (_CLIENTS_SERVICE, _MEMBERSHIPS_SERVICE, _AUTH_SERVICE)
```
Update the docstring at lines 182-197 to remove the deferred-items reference for `auth/service.py` (now closed). The `test_walker_scope_is_modules_service_only` test at line 213 needs no change — `auth/service.py` is already under `modules/`.

---

### 11. `apps/backend/tests/unit/test_audit_taxonomy.py` (MODIFY)

**Role:** AST taxonomy walker. **Data flow:** scan + assert.

**Existing count assertion to bump** (`test_audit_taxonomy.py:164-178`):
```python
def test_locked_audit_events_has_expected_count() -> None:
    """Sanity belt — 18 v1.1 + 11 v1.2 + 1 v1.2 Phase 23 = 30 locked pairs.
    ...
    """
    assert len(LOCKED_AUDIT_EVENTS) == 30, (
        f"LOCKED_AUDIT_EVENTS size drifted: expected 30 (18 v1.1 + 12 v1.2), "
        f"got {len(LOCKED_AUDIT_EVENTS)}"
    )
```

**Apply to plan** (CONTEXT D-24-19):
- Bump expected count from 30 to 36.
- Update the docstring inventory: `18 v1.1 + 12 v1.2 + 6 v1.3 = 36`.
- Add a new test `test_locked_audit_events_includes_v13_pairs` that asserts each of the six pairs is present:
  ```python
  for pair in [
      ("membership_frozen", "membership"),
      ("membership_unfrozen", "membership"),
      ("membership_renewed", "membership"),
      ("expiring_notification_sent_7d", "membership"),
      ("expiring_notification_sent_3d", "membership"),
      ("expiring_notification_sent_1d", "membership"),
  ]:
      assert pair in LOCKED_AUDIT_EVENTS, f"Phase 24 INFRA-15: {pair} missing"
  ```
- The `test_every_audit_emit_pair_is_in_locked_set` walker at line 138 stays green because Phase 24 adds NO callsites (D-24-19).

---

### 12. `apps/backend/tests/unit/memberships/test_state_machine.py` (MODIFY)

**Role:** parametrize unit test. **Data flow:** pure-function call.

**Existing 9-cell matrix** (`test_state_machine.py:43-91`):
```python
@pytest.mark.parametrize(
    ("from_status", "action", "expect"),
    [
        ("active", "cancel", "ok"),
        ("active", "expire", "ok"),
        ("active", "create-self", "n/a"),
        ("expired", "cancel", "invalid_transition"),
        ...
    ],
)
def test_state_machine_matrix(from_status: str, action: str, expect: str) -> None:
    ...
    if action == "cancel":
        _assert_can_cancel(membership)
    elif action == "expire":
        _assert_can_expire(membership)
    ...
```

**Apply to plan** (CONTEXT D-24-05): keep the 9-cell shape unchanged (the test is the regression contract). Add a new test exercising `_assert_can_transition` directly with explicit `target` strings:
```python
def test_central_helper_matches_per_helper_guards() -> None:
    """D-24-05: refactor target — central helper agrees with thin wrappers."""
    from app.modules.memberships.service import _assert_can_transition
    # Allowed: active → cancelled / expired
    _assert_can_transition(_stub_membership(status="active"), target="cancelled")
    _assert_can_transition(_stub_membership(status="active"), target="expired")
    # Disallowed: expired/cancelled → anything (Phase 24; Phase 25 adds frozen)
    for src in ("expired", "cancelled"):
        for tgt in ("cancelled", "expired"):
            with pytest.raises(InvalidTransitionError):
                _assert_can_transition(_stub_membership(status=src), target=tgt)
```
Phase 25 will extend the matrix to 16 cells (`frozen` source/target); Phase 24 stays at 9 + the central-helper smoke (CONTEXT specifics #2).

---

### 13. `apps/backend/tests/integration/memberships/test_resolver.py` (MODIFY — new test)

**Role:** integration test. **Data flow:** DB fixture + httpx assertion.

**Closest existing case** (`test_resolver.py:103-117`):
```python
async def test_resolver_returns_none_for_expired_only_client(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """Client with only expired rows -> resolver returns None."""
    plan = await make_plan(name="Expired Only")
    client = await _create_client(authed_client_owner, phone="+79991232004")
    client_uuid = UUID(client["id"])
    await make_membership(client_id=client_uuid, plan=plan, status="expired")

    got = await resolve_active_membership_by_client(db_session, client_uuid)
    assert got is None
```

**`make_membership` fixture date-injection precedent** (`test_resolver.py:135-147`):
```python
m_short = await make_membership(
    client_id=client_uuid,
    plan=plan,
    status="active",
    start_date=today,
    end_date=today + timedelta(days=89),
)
```

**Apply to plan** (CONTEXT D-24-09): new test `test_resolver_filters_expired_active_row` inserts a row with `status='active'` AND `end_date = today - timedelta(days=1)` (simulating the missed-ARQ-tick scenario), then asserts:
```python
got = await resolve_active_membership_by_client(db_session, client_uuid, today=today)
assert got is None  # DEBT-01: end_date < today filters this row even with status='active'
```
Pass `today` explicitly for determinism (per D-24-06 — same pattern as `_expire_due_memberships` tests). All existing tests in this file stay green — they use `today + timedelta(days=N)` for `N > 0`, so `end_date >= today` is satisfied.

---

### 14. `apps/admin-web/src/shared/api/services/mock/memberships.ts:28-57` (MODIFY)

**Role:** mock service. **Data flow:** in-memory filter against versioned localStorage DB.

**Current shape with hard-coded constant** (`mock/memberships.ts:14-57`):
```typescript
// D-22-10 mirror: keep mock filter window in sync with the http adapter.
const EXPIRING_DAYS = 7
...
async list(query: MembershipsListQuery): Promise<Pagination<Membership>> {
    ...
    if (query.expiring) {
      const todayStr = todayMSK()
      const cutoff = new Date(todayStr)
      cutoff.setUTCDate(cutoff.getUTCDate() + EXPIRING_DAYS)
      const cutoffStr = cutoff.toISOString().slice(0, 10)
      const items = all.filter(
        (m) => m.status === 'active' && m.endDate >= todayStr && m.endDate <= cutoffStr,
      )
      return { items, total: items.length, page: 1, pageSize: Math.max(1, items.length) }
    }
    ...
}
```

**Apply to plan** (CONTEXT D-24-13):
- Drop the module-local `EXPIRING_DAYS = 7` constant.
- Read window from `const within = query.within ?? 7` at the top of the `expiring` branch.
- Use `cutoff.setUTCDate(cutoff.getUTCDate() + (within - 1))` to apply inclusive end-date semantics matching the backend (`<= today + (within - 1)` per D-24-12).
- Keep the BLK-06 single-page collapse in the mock branch (mock stays as-is for symmetry — only the http adapter strips it because the backend now paginates honestly).
- Add a Vitest case (per CONTEXT specifics — risk note 4) asserting `within=undefined` defaults to the legacy 7-day window so FE-08 D-2 doesn't regress.

---

### 15. `apps/admin-web/src/shared/api/services/http/memberships.ts:38-81` (MODIFY)

**Role:** http service. **Data flow:** network adapter (axios-style via `@sportzal/api-client`).

**Sibling pattern for "forward optional query params"** (`http/memberships.ts:127-137` — `listPlans`):
```typescript
async listPlans(query: MembershipPlansListQuery) {
    const q: Record<string, string | number | boolean> = {
      page: query.page ?? 1,
      pageSize: query.pageSize ?? 20,
    }
    if (query.active !== undefined) q.active = query.active
    const raw = unwrap<PaginatedMembershipPlanResponse>(
      await request('get', '/api/v1/membership-plans', { query: q }),
    )
    return { ...raw, items: raw.items.map(responseToMembershipPlan) }
},
```

**Block to REMOVE entirely** (`http/memberships.ts:53-79`):
```typescript
// BLK-06 / WR-03 client-side filter + pagination collapse — REMOVE
let items = raw.items.map(responseToMembership)
if (query.expiring) {
  const todayStr = todayMSK()
  const cutoff = new Date(todayStr)
  cutoff.setUTCDate(cutoff.getUTCDate() + EXPIRING_DAYS)
  const cutoffStr = cutoff.toISOString().slice(0, 10)
  items = items.filter(
    (m) => m.status === 'active' && m.endDate >= todayStr && m.endDate <= cutoffStr,
  )
  return { items, total: items.length, page: 1, pageSize: Math.max(1, items.length) }
}
return { ...raw, items }
```

**Apply to plan** (CONTEXT D-24-13):
- Forward `expiring` and `within` to the backend in the `q` record:
  ```typescript
  if (query.expiring) {
    q.expiring = true
    q.within = query.within ?? 7
  }
  ```
- Drop the `EXPIRING_DAYS = 7` module constant and the `todayMSK()` import (no longer needed in http mode).
- Drop the `BLK-06` single-page collapse — backend paginates honestly. The list method becomes:
  ```typescript
  const raw = unwrap<PaginatedMembershipResponse>(
    await request('get', '/api/v1/memberships', { query: q }),
  )
  return { ...raw, items: raw.items.map(responseToMembership) }
  ```
- Update the `MembershipsListPage` if it inspects `pageSize === Math.max(1, items.length)` for hide-pagination logic — Phase 28 owns the UI flip per CONTEXT, so leave a `// TODO Phase 28 (FE-13)` marker if needed.

---

### 16. `apps/admin-web/src/shared/api/contracts/memberships.ts` (VERIFY/MODIFY)

**Current shape** (`contracts/memberships.ts:9-14`):
```typescript
export interface MembershipsListQuery {
  page: number
  pageSize: number
  clientId?: string
  expiring?: boolean // D-22-10 client-side filter flag
}
```

**Apply to plan** (per CONTEXT specifics — `MembershipsListQuery` already has `expiring?: boolean`):
```typescript
export interface MembershipsListQuery {
  page: number
  pageSize: number
  clientId?: string
  expiring?: boolean // DEBT-02: forwarded to backend (Phase 24)
  within?: number    // DEBT-02: 1..30, defaults to 7 server-side; ignored when expiring is false
}
```
Update the inline comment on `expiring` to drop "client-side filter flag" (no longer accurate post-Phase 24).

---

## Shared Patterns

### S-1. Audit emit literal-string contract

**Source:** `apps/backend/app/core/audit.py` + AST gate at `apps/backend/tests/unit/test_audit_taxonomy.py:103-135`.

**Apply to:** every existing or new `audit.emit(...)` callsite in this phase. (Phase 24 adds zero callsites — only frozenset entries — so this gate stays green automatically.)

**Verbatim contract** (`audit.py:151-153` from emit() docstring):
> `event` MUST be a literal str at every callsite (the AST gate `tests/unit/test_audit_taxonomy.py` enforces this).

### S-2. SVC001 commit-gate (Phase 12.1 bug class)

**Source:** `apps/backend/tests/unit/test_service_commit_gate.py:118-159`.

**Apply to:** every public function under `apps/backend/app/modules/<scope>/service.py` that mutates the session or emits audit. After Phase 24's edit, the live gate covers `clients`, `memberships`, AND `auth`.

**Decision tree** (`test_service_commit_gate.py:122-130`):
```
1. Not a write path (no mutating SQL, no audit.emit) → pass.
2. Has explicit `await session.commit(...)` → pass.
3. Has `# noqa: SVC001 caller-owns-txn` marker on private (`_`-prefixed) function → pass.
4. Has SVC001 marker on public function → FAIL (D-04: marker only valid on private helpers).
5. Otherwise → FAIL (Phase 12.1 bug class).
```

**Implication for this phase:** `auth/service.py` write paths must add explicit `await session.commit()` (D-24-15); the marker is NOT a valid escape on public functions (D-24-16).

### S-3. Caller-owns-transaction (audit.emit + repository)

**Source:** `apps/backend/app/core/audit.py:138-148` + `apps/backend/app/modules/memberships/repository.py:12-15`.

**Apply to:** the new repository signature for `find_active_for_client` and the extended `list_memberships` predicate path. `today` resolution (None → MSK) belongs in the SERVICE layer, NOT the repository — keep the repository pure (planner: ensure call sites pass an explicit `date`).

### S-4. Reuse existing `InvalidTransitionError`

**Source:** `apps/backend/app/core/exceptions.py:158-172`.

**Apply to:** the new `_assert_can_transition` central guard. **Do NOT add a parallel exception class.** The existing 409 envelope shape with `fields={"from_status": ..., "to_status": ...}` already matches REQUIREMENTS INFRA-16's "discriminating payload" wording.

### S-5. Europe/Moscow today injection

**Source:** `apps/backend/app/modules/memberships/service.py:541-542` (`_expire_due_memberships`).

**Apply to:** `resolve_active_membership_by_client` (D-24-06) and `list_memberships` when `expiring=True` (D-24-12). Standard idiom:
```python
if today is None:
    today = datetime.now(ZoneInfo("Europe/Moscow")).date()
```
Tests pass explicit `today` for determinism — never use `freezegun` or wall-clock probes.

### S-6. Mock/http parity rule

**Source:** `apps/admin-web/CLAUDE.md` § "Architecture — non-negotiable" point 2 (swap seam) + the mock/http memberships pair.

**Apply to:** `mock/memberships.ts` and `http/memberships.ts` together. Identical observable behaviour for `list({expiring: true, within: N})` after Phase 24, even though the implementation paths diverge (mock filters in-memory; http forwards to backend).

---

## No Analog Found

| File | Role | Data Flow | Reason / Resolution |
|---|---|---|---|
| `apps/backend/app/modules/memberships/constants.py` (NEW) | module constant — read-only Mapping | static lookup | First module-local immutable constant of this shape under `app/modules/`. **Pattern composed** from `audit.py:78` (`frozenset` literal at module scope) + `MappingProxyType` from CONTEXT D-24-03. No prior analog in the codebase. |

All other files have direct same-file or sibling analogs already in the codebase.

---

## Metadata

**Analog search scope:**
- `apps/backend/app/core/` — exception hierarchy, audit, dependencies (resolver Protocol).
- `apps/backend/app/modules/memberships/` — full module (models, repository, service, schemas, router).
- `apps/backend/app/modules/auth/` — service.py + telegram_service.py for DEBT-03 deferred-scan check.
- `apps/backend/app/modules/clients/` — Phase 12.1 fix exemplar.
- `apps/backend/alembic/versions/` — migration chain head (0006) + CHECK origin (0005).
- `apps/backend/tests/unit/` — AST gates (taxonomy, commit-gate) + state machine.
- `apps/backend/tests/integration/memberships/` — resolver integration tests.
- `apps/admin-web/src/shared/api/{services/{mock,http},contracts}/memberships.ts` — full FE memberships surface.

**Files scanned (Read calls):** 13 (no re-reads). Targeted Grep used to locate sections inside `auth/service.py` (700+ lines) and `memberships/router.py` before reading the relevant ranges only.

**Pattern extraction date:** 2026-05-08

**Downstream consumer:** `gsd-planner` (next step: `/gsd-plan-phase 24` planning sub-step). Each pattern excerpt above is keyed by the file the planner will write a plan section for.
