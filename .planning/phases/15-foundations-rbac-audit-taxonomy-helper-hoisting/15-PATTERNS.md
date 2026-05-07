# Phase 15: Foundations — RBAC + audit taxonomy + helper hoisting — Pattern Map

**Mapped:** 2026-05-07
**Files analyzed:** 17 (5 NEW + 12 MODIFIED)
**Analogs found:** 17 / 17

## File Classification

| New / Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---------------------|------|-----------|----------------|---------------|
| **NEW** `apps/backend/app/core/sql.py` | core utility (leaf helper) | pure-function transform | `apps/backend/app/modules/clients/repository.py:46-73` (`_escape_like_pattern`) | exact (verbatim hoist) |
| **NEW** `apps/backend/app/core/services.py` | core docstring template | n/a (no runtime code) | `apps/backend/app/modules/clients/service.py` (free-function write-path) + `apps/backend/app/core/audit.py:1-32` (locked-list docstring) | exact (documents the canonical pattern) |
| **NEW** `apps/backend/tests/unit/test_core_sql.py` | unit test (pure func) | request-response | `apps/backend/tests/unit/clients/test_repository_escape.py` | exact (move + add) |
| **NEW** `apps/backend/tests/unit/test_audit_taxonomy.py` | unit test (AST walk) | static-analysis | `apps/backend/tests/integration/test_rbac_parity.py` (file-walking style) + `apps/backend/tests/unit/test_schemas.py:60-71` (`inspect.getsource` precedent) | role-match |
| **NEW** `apps/backend/tests/unit/test_service_commit_gate.py` | unit test (AST walk) | static-analysis | `test_audit_taxonomy.py` (peer — both AST walkers, see CD-03 about shared `iter_module_calls`) + `test_rbac_parity.py` | role-match |
| **MOD** `apps/backend/app/core/permissions.py` | core RBAC enums | static lookup | self (in-place extension; the 9-entry frozenset block is the verbatim mirror of `can.ts:12-22`) | self (extend in place) |
| **MOD** `apps/backend/app/core/audit.py` | core audit emitter | request-response (DB) | self (in-place: docstring → frozenset + raise) | self (extend in place) |
| **MOD** `apps/backend/app/core/schemas.py` | core DTO bases | n/a (declarative) | self (rename `RequestContract` → `BackendSchemaBase`) | self |
| **MOD** `apps/backend/app/core/pagination.py` | core DTO base | declarative | self (import-site update) | self |
| **MOD** `apps/backend/app/modules/clients/schemas.py` | module DTOs | declarative | self (import-site update) | self |
| **MOD** `apps/backend/app/modules/auth/schemas.py` | module DTOs | declarative | self (import-site update) | self |
| **MOD** `apps/backend/app/modules/clients/repository.py` | module repository | CRUD | self (drop `_escape_like_pattern`, import from `core.sql`) | self |
| **MOD** `apps/admin-web/src/shared/session/registry.ts` | FE RBAC registry | declarative | self (extend `Resource` union — TS-side mirror of `permissions.py:Resource`) | self |
| **MOD** `apps/admin-web/src/shared/session/can.ts` | FE RBAC matrix | static lookup | self (extend `OWNER_ONLY` array — TS-side mirror of `permissions.py:OWNER_ONLY`) | self |
| **MOD** `apps/backend/tests/integration/test_rbac_parity.py` | integration test (file walk) | static-analysis | self (extend input fixtures only) | self |
| **MOD** `apps/backend/tests/unit/clients/test_repository_escape.py` | unit test | request-response | self (import-path swap only) | self |
| **MOD** `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md` | doc | n/a | `.planning/PROJECT.md:139-164` (Key Decisions table) | exact format |

---

## Pattern Assignments

### NEW `apps/backend/app/core/sql.py` (core utility, pure-function transform)

**Analog:** `apps/backend/app/modules/clients/repository.py:46-73`

**Hoist target — verbatim function body, drop the leading underscore (becomes module-public per INFRA-10):**

```python
# Source (apps/backend/app/modules/clients/repository.py:46-73)
def _escape_like_pattern(value: str, *, escape_like: bool = True) -> str:
    """Escape SQL LIKE/ILIKE metacharacters in user-supplied search input.

    Postgres ILIKE treats ``%`` (any sequence) and ``_`` (any single char) as
    wildcards, and uses ``\\`` as the default escape character. To make a
    user query match LITERAL text, we double-escape backslashes first
    (so we don't re-escape escapes added in the next step), then escape
    ``%`` and ``_``.

    Order matters: backslash MUST be escaped before ``%`` and ``_``, otherwise
    the backslashes we add to escape ``%``/``_`` would themselves be doubled.

    CR-01 (Phase 8 -> Phase 14): without this helper, a reception user
    could ``?q=%`` and dump the full client roster. ...
    """
    if not escape_like:
        return value
    # Order: backslash first, then % and _.
    return (
        value.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
```

**Imports pattern — leaf module, no project imports (per INFRA-10 + import-linter `core ⊥ modules` contract):**

```python
"""SQL helpers shared across modules (INFRA-10).

`escape_like_pattern` was hoisted from `app.modules.clients.repository` in
Phase 15 so future modules (memberships, visits) can reuse it without
introducing a `modules → modules` import (banned by import-linter contract
`modules-independent`). Pure-function, no DB / Pydantic / SQLAlchemy types.
"""
```

**No `from __future__ import annotations`** — D-148 (Established Patterns / `code_context`): leaf helper with no Pydantic generic types, so PEP 563 deferral is unnecessary.

**Naming change:** `_escape_like_pattern` → `escape_like_pattern` (drop underscore — module-public per INFRA-10).

---

### NEW `apps/backend/app/core/services.py` (core docstring-only module, no runtime code)

**Analog 1 — locked-list docstring style:** `apps/backend/app/core/audit.py:1-32`

```python
# audit.py:1-32 — module docstring carries the contract; no runtime list
"""Audit event emission (D-21 / Phase 8 D-03, D-04).

The function is `async` and takes the caller's `AsyncSession`. It NEVER calls
`session.commit()` or `session.flush()` — the caller owns the transaction
(D-03). The AuditLog row enrolls in whatever transaction `session` is part of
and commits or rolls back atomically with the caller's mutation.

Locked event names (do NOT invent new ones — Phase 8 contract):
  - login_success                       {user_id, email?, ip?, channel}
  - login_failed                        {email, reason, ip}
  ...
```

**Analog 2 — write-path recipe to document:** `apps/backend/app/modules/clients/service.py:107-142` (`create_client`)

```python
# clients/service.py:107-142 — the canonical free-function write path
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
    await session.commit()                 # <-- THE invariant the gate enforces
    return ClientResponse.model_validate(client)
```

**Per D-01:** `core/services.py` is **docstring-only**. No `class BusinessService`, no `Mixin`, no abstract base, no context-manager. Module body is a single triple-quoted string.

**Per D-04:** `# noqa: SVC001 caller-owns-txn` is valid only on private (`_`-prefixed) helpers; public functions must commit themselves.

**CD-01:** Exact docstring wording is planner discretion. Goal: a developer opens the file and grasps the contract in <60s — recipe + ASCII flowchart + 1-2 examples (use `clients/service.py:create_client` as the example).

**Imports:** none. Module body is a single docstring; passes `core ⊥ modules` import-linter contract trivially.

---

### NEW `apps/backend/tests/unit/test_core_sql.py` (unit test, pure-function)

**Analog:** `apps/backend/tests/unit/clients/test_repository_escape.py` (full file, lines 1-43)

**Imports + module docstring pattern (lines 1-11):**

```python
"""Unit tests for `escape_like_pattern` (INFRA-10 — Phase 15 hoist).

The helper escapes SQL `LIKE` metacharacters in user-supplied search input
before it is wrapped in `%...%` for ILIKE. Order matters: backslash MUST
be escaped first so we don't double-escape escapes we add for `%` / `_`.
"""

from __future__ import annotations

from app.core.sql import escape_like_pattern
```

**Test pattern — sentence-case `def test_xxx`, single `assert ==`, no fixtures (lines 13-42):**

```python
def test_plain_alphanumeric_is_unchanged() -> None:
    assert escape_like_pattern("Иванов") == "Иванов"
    assert escape_like_pattern("foo123") == "foo123"


def test_percent_is_escaped() -> None:
    assert escape_like_pattern("50%") == "50\\%"


def test_backslash_is_doubled() -> None:
    assert escape_like_pattern("a\\b") == "a\\\\b"


def test_mixed_metacharacters_apply_in_correct_order() -> None:
    # Order check: backslash must be escaped FIRST so the escapes we
    # then add for %/_ are not themselves re-escaped.
    assert escape_like_pattern("100%_x\\y") == "100\\%\\_x\\\\y"


def test_escape_like_false_returns_input_unchanged() -> None:
    assert escape_like_pattern("100%", escape_like=False) == "100%"
```

**Per D-12:** `test_core_sql.py` is the **direct/owned** test home for `core/sql.py`. The existing `tests/unit/clients/test_repository_escape.py` is also retained and gets only an import-path swap (`from app.modules.clients.repository import _escape_like_pattern` → `from app.core.sql import escape_like_pattern`); test bodies do not change.

---

### NEW `apps/backend/tests/unit/test_audit_taxonomy.py` (unit test, AST walk)

**Analog 1 — file-walking + repo-root pathing:** `apps/backend/tests/integration/test_rbac_parity.py:19-25`

```python
# test_rbac_parity.py:19-25 — repo-root resolution from a tests/ file
_REPO_ROOT = Path(__file__).resolve().parents[4]
# parents[0]=integration, [1]=tests, [2]=backend, [3]=apps, [4]=repo root
# For tests/unit/ a peer would be parents[4] as well.
```

**Repo-root pathing for unit-level (parents[4] still valid since `tests/unit/test_audit_taxonomy.py` has the same depth as `tests/integration/test_rbac_parity.py`):**

```python
_REPO_ROOT = Path(__file__).resolve().parents[4]
_BACKEND_APP = _REPO_ROOT / "apps" / "backend" / "app"
```

**Analog 2 — failure-mode messaging (set-difference diff):** `test_rbac_parity.py:106-110`

```python
# Pattern: report BE-only and FE-only sides separately so devs see drift direction
assert fe_pairs == be_pairs, (
    f"OWNER_ONLY drift detected.\n"
    f"  BE-only (in app.core.permissions, not in can.ts): {sorted(be_pairs - fe_pairs)}\n"
    f"  FE-only (in can.ts, not in app.core.permissions): {sorted(fe_pairs - be_pairs)}"
)
```

**Per D-11 — AST walker contract:**

```python
# Pseudocode for the walker (planner: implement against ast.walk)
import ast

def _iter_audit_emit_calls(module_root: Path):
    """Yield (file, lineno, event_literal | None, resource_type_literal | None) for every
    audit.emit(...) callsite in app/**/*.py. Non-literal args yield None for that slot."""
    for py in module_root.rglob("*.py"):
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            # Match `audit.emit(...)` or `<anything>.audit.emit(...)`
            if not (isinstance(node.func, ast.Attribute) and node.func.attr == "emit"):
                continue
            value = node.func.value
            is_audit = (
                (isinstance(value, ast.Name) and value.id == "audit")
                or (isinstance(value, ast.Attribute) and value.attr == "audit")
            )
            if not is_audit:
                continue
            # Resolve event (positional[0] or kw 'event') and resource_type (kw)
            ...

def test_every_audit_emit_uses_literal_strings() -> None:
    """D-11 step 3: f-strings / variables are forbidden — the gate cannot prove staticness."""
    ...

def test_every_audit_emit_pair_is_in_locked_set() -> None:
    """D-11 step 4: (event, resource_type) ∈ LOCKED_AUDIT_EVENTS for every collected pair."""
    from app.core.audit import LOCKED_AUDIT_EVENTS
    ...
```

**Per D-12:** New file path is `apps/backend/tests/unit/test_audit_taxonomy.py` (unit, NOT integration — pure AST, no DB).

**Per CD-03:** Planner may factor a shared `iter_module_calls()` helper into `tests/_meta_helpers/ast_walk.py` to deduplicate with `test_service_commit_gate.py`, or duplicate on day one. Either is acceptable.

---

### NEW `apps/backend/tests/unit/test_service_commit_gate.py` (unit test, AST walk)

**Analog (peer):** `test_audit_taxonomy.py` above — same walker shape, different predicate.

**Per D-03 — write-path detection (a function fires the gate if its AST contains any of):**
- `session.add(...)`, `session.add_all(...)`, `session.delete(...)`
- `session.execute(insert(...))` / `update(...)` / `delete(...)`
- Any `audit.emit(...)` call (per D-05 — audit row enrolls in same txn)

**Per D-03 — pass condition:** function body (or any `try/except/async with` branch within it) contains a literal `await session.commit()`.

**Per D-04 — opt-out marker:** `# noqa: SVC001 caller-owns-txn` on the `def` line is valid **only** for private helpers (name starts with `_`). A public function with the marker is itself a failure.

**Pass/fail criterion — Phase 12.1 regression test:**
- ✅ Current `apps/backend/app/modules/clients/service.py` (post-12.1 fix, all three write paths now `await session.commit()`) MUST pass.
- ✅ A synthetic test fixture: a fake `service.py` containing `audit.emit(...)` with no `session.commit()` MUST fail (the bug Phase 12.1 shipped).

**Walker scope (Phase 15 only):**

```python
_TARGET_GLOB = "apps/backend/app/modules/**/service.py"
# NOT scanning app/workers/scheduled/**/*.py — that lands in Phase 18 (out of scope here)
```

---

### MOD `apps/backend/app/core/permissions.py` (extend in place — INFRA-08)

**Analog:** the file itself, lines 20-54 (the existing 5+11+9 layout is the template).

**Existing pattern (Action StrEnum, lines 20-26):**

```python
class Action(StrEnum):
    VIEW = "view"
    CREATE = "create"
    EDIT = "edit"
    DELETE = "delete"
    REFUND = "refund"
```

**Phase 15 additions — append in place:**

```python
class Action(StrEnum):
    VIEW = "view"
    CREATE = "create"      # already present
    EDIT = "edit"
    DELETE = "delete"
    REFUND = "refund"
    CANCEL = "cancel"      # NEW — INFRA-08 (memberships)
    CHECK_IN = "check_in"  # NEW — INFRA-08 (visits) — value uses underscore
```

**Existing pattern (Resource StrEnum, lines 28-39):**

```python
class Resource(StrEnum):
    DASHBOARD = "dashboard"
    CLIENTS = "clients"
    ...
    OWNER_AREA = "owner-area"  # member-name uses underscore; value contains hyphen
```

**Phase 15 additions:**

```python
    MEMBERSHIPS = "memberships"            # NEW — INFRA-08
    MEMBERSHIP_PLANS = "membership-plans"  # NEW — kebab on wire (mirrors OWNER_AREA precedent)
    VISITS = "visits"                      # NEW — INFRA-08
```

**Existing pattern (OWNER_ONLY frozenset, lines 42-54):**

```python
# Verbatim mirror of apps/admin-web/src/shared/session/can.ts:12-22 (9 entries).
OWNER_ONLY: frozenset[tuple[Action, Resource]] = frozenset({
    (Action.VIEW, Resource.FINANCE),
    ...
    (Action.REFUND, Resource.FINANCE),
})
```

**Phase 15 additions (per `STATE.md ## Decisions` "extends v1.1 OWNER_ONLY by 6 entries"):**

```python
    # NEW — Phase 15 INFRA-08 (memberships / membership-plans)
    (Action.VIEW, Resource.MEMBERSHIP_PLANS),
    (Action.EDIT, Resource.MEMBERSHIP_PLANS),
    (Action.CREATE, Resource.MEMBERSHIP_PLANS),
    (Action.DELETE, Resource.MEMBERSHIP_PLANS),
    (Action.CANCEL, Resource.MEMBERSHIPS),
    (Action.DELETE, Resource.MEMBERSHIPS),
    # Reception KEEPS (CREATE, MEMBERSHIPS) and (CHECK_IN, VISITS) — NOT in OWNER_ONLY
```

**Mirror docstring update (line 42):** "9 entries" → "15 entries".

**No change to `can()` body** — short-circuit semantics unchanged.

---

### MOD `apps/backend/app/core/audit.py` (in-place — INFRA-11)

**Analog:** the file itself, lines 1-88. Phase 15 turns the docstring list into a runtime frozenset and adds a pre-emit guard.

**New module-level frozenset (D-10) — add before `async def emit`:**

```python
# After the imports (line 41), before async def emit (line 43):

LOCKED_AUDIT_EVENTS: frozenset[tuple[str, str]] = frozenset({
    # v1.1 (lifted from docstring lines 11-28)
    ("login_success", "session"),
    ("login_failed", "login_attempt"),
    ("session_revoked", "session"),
    ("session_revoked_all", "session"),
    ("family_reuse_detected", "session"),
    ("password_changed_revokes_sessions", "user"),
    ("telegram_deep_link_issued", "otp"),
    ("otp_issued", "otp"),
    ("otp_consumed", "otp"),
    ("telegram_unknown_start", "telegram"),  # planner: confirm resource_type from Phase 7 D-04 mapping
    ("telegram_dm_blocked", "telegram"),
    ("telegram_dm_failed", "telegram"),
    ("telegram_replay_attempt", "otp"),
    ("client_created", "client"),
    ("client_updated", "client"),
    ("client_soft_deleted", "client"),
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
})
```

**Planner action item:** verify each v1.1 `(event, resource_type)` pair against the actual call-site arguments (the docstring may have slightly drifted from real calls; the AST walker `test_audit_taxonomy.py` will fail loudly until the frozenset matches reality).

**New exception class (D-09) — add at module level:**

```python
class AuditEventNotLockedError(ValueError):
    """Raised by audit.emit() when (event, resource_type) ∉ LOCKED_AUDIT_EVENTS.

    Hard fail in dev AND prod (D-09): unknown audit pair = programmer error
    (stale callsite or unlocked taxonomy). NO graceful degradation, NO
    DEBUG-only assert. Tests catch this exception explicitly.
    """
```

**Pre-emit guard — modify `emit()` body (insert before line 78 `structlog.get_logger(...)`):**

```python
async def emit(
    session: AsyncSession,
    event: str,
    *,
    actor_user_id: UUID | None,
    resource_type: str,
    resource_id: UUID | None = None,
    **payload: Any,
) -> None:
    if (event, resource_type) not in LOCKED_AUDIT_EVENTS:
        raise AuditEventNotLockedError(
            f"audit.emit({event!r}, resource_type={resource_type!r}) "
            f"is not in LOCKED_AUDIT_EVENTS — extend the frozenset in app.core.audit "
            f"or fix the typo at the callsite."
        )
    structlog.get_logger("audit").info(event, **payload)
    session.add(
        AuditLog(
            action=event,
            actor_user_id=actor_user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            payload=payload,
        )
    )
```

**Signature unchanged** — all v1.1 callers continue to work without modification (per `code_context` Reusable Assets / `audit.emit()`).

---

### MOD `apps/backend/app/core/schemas.py` (rename — INFRA-12 / D-06)

**Analog:** the file itself, lines 36-44.

**Rename pattern — single-symbol find/replace:**

```python
# Before (line 36):
class RequestContract(ContractModel):
    """Inbound request body / query params. Strict on extras (extra='forbid')."""

# After (Phase 15):
class BackendSchemaBase(ContractModel):
    """Inbound request body / query params. Strict on extras (extra='forbid').

    Renamed from `RequestContract` in Phase 15 (INFRA-12 / D-06) — single source of
    truth for v1.2 inbound DTOs. v1.1 modules already reference this class via the
    new name (sed-grade refactor; no behavioural change).
    """
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,    # KEEP (D-07 — Pydantic 2.11+ canonical)
        validate_by_alias=True,   # KEEP (D-07 — paired with validate_by_name)
        extra="forbid",
    )
```

**Per D-07:** Do NOT add `populate_by_name=True`. The existing `validate_by_name=True + validate_by_alias=True` pair is the canonical Pydantic 2.11+ form; `populate_by_name` is the deprecated 2.10 spelling. `tests/unit/test_schemas.py:60-71` already asserts `populate_by_name` does not appear in module source — keep that test green.

**Per D-08:** No retroactive migration of v1.1 schemas onto a different base. v1.1 inputs already inherit from this class (under its old name); they continue to inherit under the new name with zero behavioural drift. `openapi.json` byte-stable per `code_context` Integration Points.

---

### MOD import-site updates (3 files — D-06 / INFRA-12)

**Analog:** verified by grep — exactly 3 modules import `RequestContract`.

| File | Line | Change |
|------|------|--------|
| `apps/backend/app/core/pagination.py` | 17 | `from app.core.schemas import RequestContract, ResponseData` → `from app.core.schemas import BackendSchemaBase, ResponseData` |
| `apps/backend/app/core/pagination.py` | 20 | `class PageQuery(RequestContract):` → `class PageQuery(BackendSchemaBase):` |
| `apps/backend/app/core/pagination.py` | 24 | docstring `RequestContract inherits` → `BackendSchemaBase inherits` |
| `apps/backend/app/modules/clients/schemas.py` | 35 | `from app.core.schemas import RequestContract, ResponseData` → `from app.core.schemas import BackendSchemaBase, ResponseData` |
| `apps/backend/app/modules/clients/schemas.py` | 105, 132 | `class ClientCreateRequest(RequestContract):` / `class ClientUpdateRequest(RequestContract):` → `BackendSchemaBase` |
| `apps/backend/app/modules/clients/schemas.py` | 3, 214 | docstring text `RequestContract` → `BackendSchemaBase` |
| `apps/backend/app/modules/auth/schemas.py` | 19 | `from app.core.schemas import RequestContract, ResponseData` → `from app.core.schemas import BackendSchemaBase, ResponseData` |
| `apps/backend/app/modules/auth/schemas.py` | 22, 75 | `class LoginRequest(RequestContract):` / `class TelegramVerifyRequest(RequestContract):` → `BackendSchemaBase` |
| `apps/backend/app/modules/clients/router.py` | 22 | docstring "Request bodies are RequestContract subclasses" → "BackendSchemaBase subclasses" |

**Verification grep after rename — must return zero hits in `apps/backend/app/`:**

```bash
grep -rn "RequestContract" apps/backend/app/   # expect: empty
```

---

### MOD `apps/backend/app/modules/clients/repository.py` (drop helper, import — INFRA-10)

**Analog:** the file itself, lines 36-43 (current import block) and 46-73 (current helper definition).

**Diff:**

```python
# REMOVE lines 46-73 (the def _escape_like_pattern body)
# UPDATE the import block (lines 32-43) to add:
from app.core.sql import escape_like_pattern

# UPDATE callsite at line 108:
escaped_q = _escape_like_pattern(query.q.lower())
# becomes
escaped_q = escape_like_pattern(query.q.lower())

# UPDATE callsite at line 121:
Client.phone.ilike(f"%{_escape_like_pattern(query.q)}%"),
# becomes
Client.phone.ilike(f"%{escape_like_pattern(query.q)}%"),
```

**No behaviour change.** The escape rules and the callsite ordering (backslash-first) are preserved verbatim — only the import path moves.

---

### MOD `apps/admin-web/src/shared/session/registry.ts` (FE mirror — INFRA-09)

**Analog:** the file itself, lines 1-14. Phase 15 extends both the `Resource` union AND adds optional sidebar entries (TBD by FE planner — FE-06 in Phase 22 owns the sidebar wiring; Phase 15 only needs the type union).

**Existing pattern (lines 1-14):**

```ts
export type Resource =
  | 'dashboard'
  | 'clients'
  | 'schedule'
  | 'staff'
  | 'finance'
  | 'reports'
  | 'payroll'
  | 'compensation'
  | 'templates'
  | 'settings'
  | 'owner-area'

export type Action = 'view' | 'create' | 'edit' | 'delete' | 'refund'
```

**Phase 15 additions:**

```ts
export type Resource =
  | 'dashboard'
  | 'clients'
  | 'schedule'
  | 'staff'
  | 'finance'
  | 'reports'
  | 'payroll'
  | 'compensation'
  | 'templates'
  | 'settings'
  | 'owner-area'
  | 'memberships'         // NEW — INFRA-09
  | 'membership-plans'    // NEW — kebab on wire (mirrors 'owner-area')
  | 'visits'              // NEW — INFRA-09

export type Action =
  | 'view'
  | 'create'
  | 'edit'
  | 'delete'
  | 'refund'
  | 'cancel'              // NEW — INFRA-09
  | 'check_in'            // NEW — value uses underscore (mirrors backend Action.CHECK_IN.value)
```

**Phase 15 does NOT add `routeRegistry` entries.** Per `<deferred>` and `<domain>` "no business endpoints", sidebar entries for memberships/visits land in Phase 22 (FE-06). The type union must exist now so `test_rbac_parity.py` Set-equality #2 stays green; the registry array's set of `resource` values is a strict subset of the union, which is fine.

---

### MOD `apps/admin-web/src/shared/session/can.ts` (FE mirror — INFRA-09)

**Analog:** the file itself, lines 12-22.

**Existing pattern:**

```ts
export const OWNER_ONLY: ReadonlyArray<{ action: Action; resource: Resource }> = [
  { action: 'view', resource: 'finance' },
  { action: 'view', resource: 'reports' },
  { action: 'view', resource: 'payroll' },
  { action: 'view', resource: 'compensation' },
  { action: 'view', resource: 'settings' },
  { action: 'view', resource: 'owner-area' },
  { action: 'edit', resource: 'templates' },
  { action: 'delete', resource: 'clients' },
  { action: 'refund', resource: 'finance' },
]
```

**Phase 15 additions — append (order matches `permissions.py` Phase 15 additions for byte parity):**

```ts
  { action: 'view', resource: 'membership-plans' },     // NEW — INFRA-09
  { action: 'edit', resource: 'membership-plans' },
  { action: 'create', resource: 'membership-plans' },
  { action: 'delete', resource: 'membership-plans' },
  { action: 'cancel', resource: 'memberships' },
  { action: 'delete', resource: 'memberships' },
```

**Total entries: 9 → 15.** `can()` body unchanged.

---

### MOD `apps/backend/tests/integration/test_rbac_parity.py` (extend fixtures — TESTS-08)

**Analog:** the file itself. Per D-12 — extend in place.

**Existing assertion logic stays:**

- `test_owner_only_pairs_match()` (line 102-110) — set equality, nothing to change here.
- `test_resource_values_match()` (line 113-126) — set equality, nothing to change here.
- `test_action_values_match()` (line 129-137) — set equality, nothing to change here.

**Single change — line 140-143 sanity belt:**

```python
def test_owner_only_count_is_nine() -> None:
    """Sanity belt — `OWNER_ONLY` should always be exactly 9 entries (Phase 4 D-21)."""
    assert len(OWNER_ONLY) == 9
    assert len(_parse_owner_only_pairs()) == 9
```

**Phase 15 update:**

```python
def test_owner_only_count_is_fifteen() -> None:
    """Sanity belt — `OWNER_ONLY` is exactly 15 entries (9 v1.1 + 6 v1.2 INFRA-08)."""
    assert len(OWNER_ONLY) == 15
    assert len(_parse_owner_only_pairs()) == 15
```

**No regex / parser changes** — `_PAIR_RE` and `_parse_ts_union` accept the new pairs/values without modification.

---

### MOD `apps/backend/tests/unit/clients/test_repository_escape.py` (import-path swap only — TESTS-11)

**Analog:** the file itself, line 10.

**Single line change (line 10):**

```python
# Before:
from app.modules.clients.repository import _escape_like_pattern

# After (per D-12 / TESTS-11 — test logic unchanged):
from app.core.sql import escape_like_pattern as _escape_like_pattern
```

**Why aliased import:** keeps the existing `_escape_like_pattern(...)` references in the test bodies (lines 14-42) unchanged — minimal-diff. Alternative: rename all callsites to `escape_like_pattern(...)`. Planner picks the lower-noise option; both are valid.

---

### MOD `.planning/PROJECT.md` (append 3 Key Decisions — INFRA-14)

**Analog:** `.planning/PROJECT.md:139-164` (Key Decisions table).

**Existing format (PROJECT.md:141-142):**

```markdown
| Decision | Rationale | Outcome |
|----------|-----------|---------|
```

**Phase 15 appends 3 rows after line 164 (substance from STATE.md `## Decisions`):**

```markdown
| Membership `end_date` is INCLUSIVE — last valid check-in day | Single rule across check-in / ARQ filter / display; ARQ uses `end_date < CURRENT_DATE` (strict) so the last day stays valid | ✓ Good — v1.2 (Phase 15) |
| `gym_date = (checked_in_at AT TIME ZONE 'Europe/Moscow')::date` materialised as STORED column with `UNIQUE (client_id, gym_date)` | DB-level enforcement of "1 visit per client per gym day"; race-safe (Postgres wins, not app); `gym_date` is the audit/report grouping key | ✓ Good — v1.2 (Phase 15 / VIS-01) |
| Accepted residual friend-fraud risk for v1.2 single-zal scope | Self check-in via Telegram bot can be impersonated (member shares Telegram account); mitigation = photo turnstile is hardware-tier, deferred to v1.3+ | ✓ Accepted — v1.2 (Phase 15) |
```

**Per CD-02:** Exact phrasing is planner discretion; substance is locked above.

---

### MOD `.planning/REQUIREMENTS.md` (rewording INFRA-12 — D-07)

**Analog:** `.planning/REQUIREMENTS.md:18` (current INFRA-12 line).

**Current:**

```markdown
- [ ] **INFRA-12**: `app/core/schemas.py` exposes `BackendSchemaBase(BaseModel)` with `alias_generator=to_camel`, `populate_by_name=True`, `extra='forbid'`; ...
```

**Phase 15 update (D-07):**

```markdown
- [ ] **INFRA-12**: `app/core/schemas.py` exposes `BackendSchemaBase(BaseModel)` with `alias_generator=to_camel`, `validate_by_name=True`, `validate_by_alias=True`, `extra='forbid'` (Pydantic 2.11+ canonical pair, replacing the deprecated `populate_by_name=True`); ...
```

---

## Shared Patterns

### Cross-cutting: Three-way RBAC Parity (apply to every Action/Resource/OWNER_ONLY change)

**Source:** `apps/backend/tests/integration/test_rbac_parity.py:102-137` (3 set-equality assertions).

**Constraint (per `code_context` Integration Points):** extending `OWNER_ONLY` on the backend WITHOUT simultaneously extending it on admin-web breaks the parity test. Phase 15 plans MUST change `permissions.py` + `registry.ts` + `can.ts` in the **same commit** (or a single tightly-coupled commit set), not split across commits.

**Apply to:** `permissions.py`, `registry.ts`, `can.ts` — always together.

---

### Cross-cutting: Module Docstring as Contract (apply to `core/sql.py` + `core/services.py` + `core/audit.py` updates)

**Source:** `apps/backend/app/core/audit.py:1-32` — the locked-event docstring is the runtime contract.

**Pattern:** when a module owns a closed taxonomy (allowed event names, forbidden imports, write-path recipe), the module docstring carries the prose + ASCII enumeration; the runtime construct (frozenset / function body) is one scroll below. Test asserts the source-text invariant (e.g. `test_schemas.py:60-71` `inspect.getsource` check).

**Apply to:**
- `core/sql.py` — module docstring documents "shared LIKE-escape helper, used across modules to avoid `modules → modules` violation".
- `core/services.py` — module docstring IS the contract (D-01 — no runtime code at all).
- `core/audit.py` — existing locked-events docstring extended with v1.2 events (mirrors the new frozenset).

---

### Cross-cutting: Free-Function Service Modules (no runtime base class)

**Source:** `apps/backend/app/modules/clients/service.py` (D-18 — module-level async functions, no class).

**Per D-01:** Phase 15 does NOT introduce `BusinessService` as a runtime construct. The pattern is documented in `core/services.py` (docstring) and enforced by the AST gate (`test_service_commit_gate.py`).

**Apply to:** all current and future `apps/backend/app/modules/*/service.py` files. Phase 16 (memberships) and Phase 19 (visits) inherit this pattern verbatim.

---

### Cross-cutting: `from __future__ import annotations` Decision

**Source:** `apps/backend/app/modules/clients/repository.py:18-23` (rationale — Pydantic generic resolution edge case).

**Decision rule:**
- ✅ Need `from __future__ import annotations` if the module declares Pydantic-generic-parameterised types involving SQLAlchemy ORM classes (e.g. `PaginatedData[Client]`).
- ❌ Don't need it if the module is a leaf helper with primitive type annotations only.

**Apply to:**
- `core/sql.py` — leaf helper, `str → str`, no `from __future__ import annotations` needed.
- `core/services.py` — docstring-only, irrelevant.
- `tests/unit/test_core_sql.py` — copy from `test_repository_escape.py:8` which uses `from __future__ import annotations` (consistency with peer tests).
- `tests/unit/test_audit_taxonomy.py`, `tests/unit/test_service_commit_gate.py` — use `from __future__ import annotations` for consistency with `test_rbac_parity.py:12`.

---

### Cross-cutting: import-linter compliance (apply to all NEW backend files)

**Source:** `apps/backend/.importlinter` — three contracts (`core ⊥ modules`, `modules independent`, `integrations ⊥ modules`).

**Per `code_context` Integration Points + `<specifics>`:**
- `core/sql.py` — takes `str`, returns `str`. No `app.modules.*` imports. Trivially passes.
- `core/services.py` — docstring-only, no imports at all. Trivially passes.
- `tests/unit/*` — tests live outside import-linter scope (only `app.*` is contracted).

---

## No Analog Found

None. Every Phase 15 file has either an in-place self-analog (extend in place) or a strong cross-file analog. The two AST-walking unit tests are novel to the codebase BUT structurally mirror `test_rbac_parity.py`'s file-walking + set-equality + diff-message style — no green-field invention required.

---

## Metadata

**Analog search scope:**
- `apps/backend/app/core/` (audit, schemas, permissions, pagination, exceptions, dependencies)
- `apps/backend/app/modules/clients/` (repository, service, schemas, router)
- `apps/backend/app/modules/auth/` (schemas)
- `apps/backend/tests/unit/` (test_permissions, test_schemas, test_pagination, clients/test_repository_escape)
- `apps/backend/tests/integration/test_rbac_parity.py`
- `apps/admin-web/src/shared/session/` (registry.ts, can.ts)
- `.planning/PROJECT.md`, `.planning/STATE.md`, `.planning/REQUIREMENTS.md`

**Files scanned:** ~25
**Pattern extraction date:** 2026-05-07

---

## PATTERN MAPPING COMPLETE

**Phase:** 15 — Foundations — RBAC + audit taxonomy + helper hoisting
**Files classified:** 17
**Analogs found:** 17 / 17

### Coverage
- Files with exact analog: 5 (NEW files — all map to existing precedent code)
- Files with self-analog (extend in place): 12 (MODIFIED files)
- Files with no analog: 0

### Key Patterns Identified
1. **Three-way RBAC parity is non-splittable** — `permissions.py` + `registry.ts` + `can.ts` change in the same commit; `test_rbac_parity.py:102-137` enforces it.
2. **Module docstring is the contract** — `core/audit.py:1-32` documents locked event names; Phase 15 extends the docstring AND adds a runtime frozenset (`LOCKED_AUDIT_EVENTS`) and a guard (`AuditEventNotLockedError`).
3. **Free-function services + AST commit gate** (D-01..D-05) — no runtime `BusinessService` class; `core/services.py` is docstring-only; `test_service_commit_gate.py` AST-walks `app/modules/**/service.py` and fails on missing `await session.commit()` in write paths (the Phase 12.1 bug).
4. **`RequestContract` → `BackendSchemaBase` rename is a 3-file sed-grade refactor** — `core/pagination.py`, `clients/schemas.py`, `auth/schemas.py` (verified via grep). `validate_by_name + validate_by_alias` pair stays (D-07); `populate_by_name` is NOT introduced (deprecated 2.10 spelling).
5. **`_escape_like_pattern` hoist is verbatim** — function body unchanged; rename drops the leading underscore (becomes `escape_like_pattern`); leaf helper, no `from __future__ import annotations`.

### File Created
`/Users/andre/Workspace/Development/clubcore/.planning/phases/15-foundations-rbac-audit-taxonomy-helper-hoisting/15-PATTERNS.md`

### Ready for Planning
Pattern mapping complete. Planner can reference per-file analog patterns and code excerpts directly in PLAN.md action sections.
