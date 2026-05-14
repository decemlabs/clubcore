# Phase 30: Foundations & Tech-Debt Bedrock — Pattern Map

**Mapped:** 2026-05-14
**Files analyzed:** 10 (7 modified + 3 created)
**Analogs found:** 10 / 10

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `apps/backend/app/core/audit.py` *(modify)* | core/audit | request-response (validation gate) | self (in-place extension of `LOCKED_AUDIT_EVENTS` + `emit()`) | exact (extension) |
| `apps/backend/app/core/audit_payloads.py` *(create)* | core/schema-registry | event-driven (data shape contract) | `apps/backend/app/core/audit.py` (sibling locked registry) + Pydantic v2 `BaseModel` (NOT `BackendSchemaBase`) | role-match |
| `apps/backend/app/core/permissions.py` *(modify)* | core/RBAC | request-response (permission check) | self (in-place extension of `Resource` + `OWNER_ONLY`) | exact (extension) |
| `apps/backend/.importlinter` *(modify)* | lint/contract | static-analysis (config) | self (modules list extension) | exact (extension) |
| `apps/backend/tests/unit/test_service_commit_gate.py` *(modify)* | test/AST-walker | static-analysis | self (extend `_INSPECTED_SERVICES` tuple) | exact (extension) |
| `apps/backend/tests/unit/test_payments_appendonly.py` *(create)* | test/AST-walker | static-analysis | `apps/backend/tests/unit/test_service_commit_gate.py` (SVC001 walker shape) | exact |
| `apps/backend/tests/unit/fixtures/payments_violation_*.py` *(create)* | test/fixture | synthetic-source | inline `_check_snippet` blocks in `test_service_commit_gate.py:266-336` | role-match (move from inline strings → on-disk fixtures) |
| `apps/admin-web/src/shared/session/can.ts` *(modify)* | RBAC mirror | request-response | self (extend `OWNER_ONLY` array) | exact (extension) |
| `apps/admin-web/src/shared/session/registry.ts` *(modify)* | RBAC mirror | type-only | self (extend `Resource` string literal union) | exact (extension) |
| `apps/admin-web/src/shared/api/services/mock/memberships.ts` *(modify)* | mock-service | CRUD/read | self (fix `list()` to respect `status` inside `expiring` branch) | exact (one-liner) |

---

## Pattern Assignments

### `apps/backend/app/core/audit.py` (core/audit — extend in place)

**Analog:** self — current 34-entry `LOCKED_AUDIT_EVENTS` frozenset + `emit()` body.

**Locked-frozenset literal shape** (`apps/backend/app/core/audit.py:102-157`):
```python
LOCKED_AUDIT_EVENTS: frozenset[tuple[str, str]] = frozenset(
    {
        # v1.1 (Phase 5/6/7/8) — pairs verified against actual callsites …
        ("login_success", "session"),
        # …
        # v1.3 (Phase 24 lock — emitted in Phases 25/26/27)
        ("membership_frozen", "membership"),
        ("membership_unfrozen", "membership"),
        ("membership_renewed", "membership"),
        ("expiring_notification_sent_7d", "membership"),
        ("expiring_notification_sent_3d", "membership"),
        ("expiring_notification_sent_1d", "membership"),
    }
)
```
**Extension pattern (Phase 30 — copy verbatim shape):**
- Add a new `# v1.4 (Phase 30 lock — emitted in Phases 31/32/33/34)` section block immediately after the v1.3 block.
- Add 16 `(event, resource_type)` tuples (per INFRA-17): 4 trainer-lifecycle (`trainer_created/updated/deactivated/reactivated` → `"trainer"`), 2 payment (`payment_recorded`, `refund_issued` → `"payment"`), 1 `membership_refunded` → `"membership"`, 3 pt-package-plan (`*_created/updated/archived` → `"pt_package_plan"`), 5 pt-package-instance (`*_sold/cancelled/refunded/exhausted/expired` → `"pt_package"`), 2 pt-session (`*_recorded/cancelled` → `"pt_session"`). Final length: 50.
- Exact `resource_type` value strings come from existing v1.3 naming convention (snake_case singular noun on the wire) — `_extract_event_and_resource_type` in `test_audit_taxonomy.py:60-78` enforces literal-str args.

**`emit()` validation extension point** (`apps/backend/app/core/audit.py:160-214`):
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
    # …
    if (event, resource_type) not in LOCKED_AUDIT_EVENTS:
        raise AuditEventNotLockedError(
            f"audit.emit({event!r}, resource_type={resource_type!r}) "
            f"is not in LOCKED_AUDIT_EVENTS — extend the frozenset in "
            f"app.core.audit or fix the typo at the callsite."
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
**Phase 30 insertion (per D-30-03):** between line 204 (`LOCKED_AUDIT_EVENTS` check raise) and line 205 (`structlog.get_logger(...)`), insert:
```python
schema = AUDIT_PAYLOAD_SCHEMAS.get((event, resource_type))
if schema is not None:
    schema.model_validate(payload)  # raises pydantic.ValidationError (D-09 hard-fail)
```
- Import at top: `from app.core.audit_payloads import AUDIT_PAYLOAD_SCHEMAS`.
- Hard-fail discipline mirrors `AuditEventNotLockedError` raise at `audit.py:200-204` — ValidationError propagates unchanged (no wrapping, no catch).
- Pre-Phase-30 docstring at `audit.py:5-7` already documents the LOCKED-frozenset-is-runtime-source-of-truth invariant; extend that docstring header with one line "v1.4 (Phase 30): adds AUDIT_PAYLOAD_SCHEMAS registry validating payload kwargs for 16 new events (D-30-03/04)."

---

### `apps/backend/app/core/audit_payloads.py` (core/schema-registry — CREATE)

**Analog:** `apps/backend/app/core/audit.py` (sibling locked-registry module) for the file shape; **divergent** from `app/core/schemas.py` `BackendSchemaBase` (`schemas.py:36-53`) — see note below.

**Module-docstring pattern (copy from `audit.py:1-82`):**
```python
"""Audit payload schemas (INFRA-23 / Phase 30 / D-30-03).

Strict Pydantic-v2 BaseModel per audit event for the 16 new v1.4 events.
`audit.emit()` looks up `(event, resource_type)` in `AUDIT_PAYLOAD_SCHEMAS`
and calls `Schema.model_validate(payload_kwargs)` BEFORE structlog/DB writes.
Mirrors the D-09 hard-fail discipline of `AuditEventNotLockedError`:
unknown payload key OR missing required key → pydantic.ValidationError
(programmer error, not graceful degradation).

Scope (D-30-02): ONLY v1.4 events are locked. The 34 existing v1.1–v1.3
events remain free-form (back-compat); `audit.emit()` validates payload
only when `(event, resource_type)` is present in this registry.

Architectural boundary: app.core.audit_payloads MUST NOT import from
app.modules.* (importlinter `core-not-depend-on-modules` contract).
"""
```

**Pydantic base-class divergence (CRITICAL):**
- Audit payloads are **internal kwargs** (snake_case) — NOT camelCase wire DTOs.
- Therefore: inherit `pydantic.BaseModel` directly with `model_config = ConfigDict(extra="forbid")`.
- Do NOT inherit `BackendSchemaBase` (`schemas.py:36-53`) — that base auto-aliases via `to_camel`, which would break snake_case `payload_id`, `subject_kind`, etc.
- Justification in CONTEXT.md `<code_context>` "Reusable Assets" bullet 3.

**Per-event schema shape (copy `BackendSchemaBase` strictness, drop alias_generator):**
```python
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class PaymentRecordedPayload(BaseModel):
    """Payload schema for ("payment_recorded", "payment") — PAY-10.

    Fields per REQUIREMENTS.md §PAY-10:
        payment_id, subject_kind, subject_id, amount_kopecks, method,
        received_by_user_id, payment_row_hash.
    """

    model_config = ConfigDict(extra="forbid")

    payment_id: UUID
    subject_kind: str = Field(pattern=r"^(membership|pt_package|refund)$")
    subject_id: UUID
    amount_kopecks: int
    method: str
    received_by_user_id: UUID
    payment_row_hash: str  # D-30-04: SHA-256 canonical-JSON of original payment row
```

**Registry dict pattern (mirror `LOCKED_AUDIT_EVENTS` shape — tuple keys):**
```python
AUDIT_PAYLOAD_SCHEMAS: dict[tuple[str, str], type[BaseModel]] = {
    ("trainer_created", "trainer"): TrainerCreatedPayload,
    ("trainer_updated", "trainer"): TrainerUpdatedPayload,
    # … 16 entries total (one per new event from INFRA-17)
    ("payment_recorded", "payment"): PaymentRecordedPayload,
    ("payment_refunded", "payment"): PaymentRefundedPayload,  # MUST include payment_row_hash (D-30-04)
    # …
}
```
- Tuple-key shape mirrors `LOCKED_AUDIT_EVENTS` at `audit.py:102-157` — same `(event, resource_type)` index — so the lookup at the emit-callsite is a single `.get(...)` against the same canonical key.
- 16 entries; 1:1 with the 16 new `LOCKED_AUDIT_EVENTS` additions.

**Architectural boundary:** module sits at `app/core/audit_payloads.py`. Per `.importlinter` `core-not-depend-on-modules` contract (`.importlinter:5-11`), only stdlib + Pydantic + UUID imports allowed — never `app.modules.*`.

---

### `apps/backend/app/core/permissions.py` (core/RBAC — extend in place)

**Analog:** self — current 11-value `Resource` StrEnum + 15-entry `OWNER_ONLY` frozenset.

**`Resource` StrEnum extension pattern** (`apps/backend/app/core/permissions.py:30-45`):
```python
class Resource(StrEnum):
    DASHBOARD = "dashboard"
    CLIENTS = "clients"
    # …
    MEMBERSHIPS = "memberships"            # Phase 15 INFRA-08
    MEMBERSHIP_PLANS = "membership-plans"  # Phase 15 INFRA-08 — kebab on wire (mirrors OWNER_AREA)
    VISITS = "visits"                      # Phase 15 INFRA-08
    PROFILE = "profile"                    # Phase 22 FE-09 — both roles, not OWNER_ONLY
```
**Phase 30 additions (INFRA-18 — 5 new values, value strings MUST match admin-web `registry.ts` literals byte-for-byte):**
- `TRAINERS = "trainers"`
- `PAYMENTS = "payments"`
- `PT_PACKAGE_PLANS = "pt-package-plans"` (kebab — mirrors `MEMBERSHIP_PLANS` convention at line 43)
- `PT_PACKAGES = "pt-packages"` (kebab — multi-word resource)
- `PT_SESSIONS = "pt-sessions"` (kebab — multi-word resource)

**Comment pattern:** each new line ends with `# Phase 30 INFRA-18` (mirrors the `# Phase 15 INFRA-08` / `# Phase 22 FE-09` annotation style at lines 42-45).

**`OWNER_ONLY` extension pattern** (`permissions.py:48-68`):
```python
# Verbatim mirror of apps/admin-web/src/shared/session/can.ts:12-22 (15 entries).
OWNER_ONLY: frozenset[tuple[Action, Resource]] = frozenset({
    (Action.VIEW, Resource.FINANCE),
    # …
    (Action.VIEW, Resource.MEMBERSHIP_PLANS),
    (Action.EDIT, Resource.MEMBERSHIP_PLANS),
    (Action.CREATE, Resource.MEMBERSHIP_PLANS),
    (Action.DELETE, Resource.MEMBERSHIP_PLANS),
    (Action.CANCEL, Resource.MEMBERSHIPS),
    (Action.DELETE, Resource.MEMBERSHIPS),
})
```
**Phase 30 additions (INFRA-19 — ~11 net entries; mirror v1.2 `MEMBERSHIP_PLANS` block shape):**
- Trainers CRUD owner-only: `(VIEW, TRAINERS)`, `(CREATE, TRAINERS)`, `(EDIT, TRAINERS)`, `(DELETE, TRAINERS)` — but NOT `(LIST, TRAINERS)` (reception keeps list per REQ INFRA-19).
  - **Note:** there is no `Action.LIST` in current enum (lines 20-28). REQ INFRA-18 says "no new Action values"; reception's "LIST trainers" right is therefore expressed via `Action.VIEW` semantically being "list permission". Planner clarification flagged: either (a) `(VIEW, TRAINERS)` is NOT in OWNER_ONLY (reception sees the list, owner-only is CRUD via CREATE/EDIT/DELETE), or (b) add `Action.LIST` and revise INFRA-18 "no new Action" claim. **D-30-09 prescribes (a)** — reception keeps `(VIEW, TRAINERS)` for `?active=true` picker, owner-only is CRUD writes only.
- PT-package plans CRUD owner-only: `(VIEW, PT_PACKAGE_PLANS)`, `(CREATE, PT_PACKAGE_PLANS)`, `(EDIT, PT_PACKAGE_PLANS)`, `(DELETE, PT_PACKAGE_PLANS)`.
- Payments: `(VIEW, PAYMENTS)` owner-only (global list per PAY-06); reception keeps `(CREATE, PAYMENTS)` (the sale flow records payment) → NOT in OWNER_ONLY.
- PT-packages: `(CANCEL, PT_PACKAGES)`, `(DELETE, PT_PACKAGES)` owner-only; reception keeps `(CREATE, PT_PACKAGES)` and `(REFUND, PT_PACKAGES)` per B-07 → NOT in OWNER_ONLY.
- PT-sessions: `(CANCEL, PT_SESSIONS)` owner-only; reception keeps `(CREATE, PT_SESSIONS)` → NOT in OWNER_ONLY.

Final `OWNER_ONLY` length: 15 + 11 = **~26 entries** (matches REQ INFRA-19 expectation).

**Comment pattern:** prepend group separator comment block `# v1.4 (Phase 30 INFRA-19) — trainers/payments/pt_package_plans/pt_packages/pt_sessions owner-only pairs.` mirroring the `# Phase 15 INFRA-08 — v1.2 owner-only pairs …` style at `permissions.py:60-61`.

**Parity-test update** (`apps/backend/tests/unit/test_permissions.py:16-19, 39-59, 97-117`):
- `test_owner_only_has_exactly_fifteen_entries` → rename to `..._twenty_six_entries`, update literal `15` → `26`.
- `test_resource_value_set` → add 5 new `"trainers"`, `"payments"`, `"pt-package-plans"`, `"pt-packages"`, `"pt-sessions"` to expected set.
- `test_specific_owner_only_membership` → extend `expected = frozenset({...})` with the ~11 new pairs.

---

### `apps/backend/.importlinter` (lint/contract — extend in place)

**Analog:** self — current 3-contract config with 9-module `modules-independent` list (`trainers` already present as v1.0 placeholder per CONTEXT.md `<canonical_refs>`).

**Current shape** (`apps/backend/.importlinter:13-25`):
```ini
[importlinter:contract:modules-independent]
name = modules cannot import each other
type = independence
modules =
    app.modules.auth
    app.modules.clients
    app.modules.memberships
    app.modules.visits
    app.modules.trainers
    app.modules.schedule
    app.modules.bookings
    app.modules.billing
    app.modules.notifications
```
**Phase 30 extension (INFRA-20):** add 2 new lines (8-space indent, alphabetized within v1.4 group is fine — drop in next to `trainers`):
```
    app.modules.payments
    app.modules.pt_packages
```
- `trainers` is already present (v1.0 placeholder).
- Other two contracts (`core-not-depend-on-modules` lines 5-11, `integrations-not-depend-on-modules` lines 27-33) are **untouched** — top-level shape invariant per ROADMAP.md Phase 30 SC #3.
- Pre-create empty `app/modules/payments/__init__.py` + `app/modules/pt_packages/__init__.py` (mirror existing `app/modules/trainers/__init__.py` one-liner placeholder: `"""Trainers module placeholder. TODO Phase B+: …"""`). Otherwise `lint-imports` reports "module not importable" against the contract.

---

### `apps/backend/tests/unit/test_service_commit_gate.py` (test/AST-walker — extend in place)

**Analog:** self — current `_INSPECTED_SERVICES` tuple at `test_service_commit_gate.py:170-174`.

**Current shape** (`test_service_commit_gate.py:167-174`):
```python
_CLIENTS_SERVICE = _BACKEND_APP / "modules" / "clients" / "service.py"
_MEMBERSHIPS_SERVICE = _BACKEND_APP / "modules" / "memberships" / "service.py"
_AUTH_SERVICE = _BACKEND_APP / "modules" / "auth" / "service.py"
_INSPECTED_SERVICES: tuple[Path, ...] = (
    _CLIENTS_SERVICE,
    _MEMBERSHIPS_SERVICE,
    _AUTH_SERVICE,
)
```
**Phase 30 extension (INFRA-21):**
```python
_TRAINERS_SERVICE = _BACKEND_APP / "modules" / "trainers" / "service.py"
_PAYMENTS_SERVICE = _BACKEND_APP / "modules" / "payments" / "service.py"
_PT_PACKAGES_SERVICE = _BACKEND_APP / "modules" / "pt_packages" / "service.py"
_INSPECTED_SERVICES: tuple[Path, ...] = (
    _CLIENTS_SERVICE,
    _MEMBERSHIPS_SERVICE,
    _AUTH_SERVICE,
    _TRAINERS_SERVICE,    # Phase 30 INFRA-21 — placeholder service file
    _PAYMENTS_SERVICE,    # Phase 30 INFRA-21
    _PT_PACKAGES_SERVICE, # Phase 30 INFRA-21
)
```
**Bootstrapping consideration:** the live test at `test_service_commit_gate.py:212-219` asserts `service_path.is_file()`. Phase 30 MUST therefore create minimal `service.py` placeholder files in `trainers/`, `payments/`, `pt_packages/` (empty or a single docstring) so the live walker has something to walk. A zero-function service passes the gate trivially (the `for func in …` loop yields nothing → no offenders).

**Docstring update:** extend the docstring at `test_service_commit_gate.py:187-209` with a new paragraph: "Phase 30 INFRA-21 extends the live scope to `trainers/service.py`, `payments/service.py`, `pt_packages/service.py` (empty placeholders at Phase 30 — substantive write paths land in Phases 31/32/33)."

---

### `apps/backend/tests/unit/test_payments_appendonly.py` (test/AST-walker — CREATE)

**Analog:** `apps/backend/tests/unit/test_service_commit_gate.py` (full file structure — module-docstring → constants → AST predicates → live test → synthetic tests).

**Module-docstring pattern (copy shape of `test_service_commit_gate.py:1-19`):**
```python
"""AST append-only gate (INFRA-22 / B-01 / Phase 30).

Walks every public/private function in `apps/backend/app/modules/<scope>/service.py`
and asserts: NO function body contains `update(Payment)`, `delete(Payment)`,
`session.execute(update(Payment)...)`, `session.execute(delete(Payment)...)`,
or `session.delete(<Payment-typed instance>)`.

Detects `Payment` by import-tracking: walker resolves any
`from app.modules.payments.models import Payment` (or `… import Payment as X`)
and flags AST nodes that reference the bound name. Avoids the SVC001-era
string-match false-positive class (no docstring/comment false positives).

INSERT-only policy (D-30-08): only `session.add(Payment(...))`,
`session.execute(insert(Payment).values(...))`, and
`session.execute(insert(Payment)...on_conflict_do_nothing())` are allowed.
`on_conflict_do_update()` is forbidden — formally an UPDATE, blocked at the
AST layer (PAY-02 partial UNIQUE handles concurrent-refund via IntegrityError,
not on_conflict).
"""
```

**Constants pattern (mirror `test_service_commit_gate.py:28-35`):**
```python
_REPO_ROOT = Path(__file__).resolve().parents[4]
_BACKEND_APP = _REPO_ROOT / "apps" / "backend" / "app"
_SERVICE_GLOB = "modules/**/service.py"  # mirrors SVC001 _SERVICE_GLOB exactly (D-30-05)
_FORBIDDEN_SQL_FUNCS = {"update", "delete"}      # against Payment class
_FORBIDDEN_SESSION_ATTRS = {"delete"}            # session.delete(<Payment instance>)
_FORBIDDEN_ON_CONFLICT = {"on_conflict_do_update"}  # D-30-08
```

**Reusable AST predicates (copy + adapt from `test_service_commit_gate.py:38-94`):**
- Adapt `_is_session_execute_with_mutating_sql` (lines 48-70): instead of detecting `{"insert", "update", "delete"}` in `_MUTATING_SQL_FUNCS`, narrow to `{"update", "delete"}` AND additionally check that the inner `ast.Call` first arg is a `Name(id=<bound Payment name>)`. This is the import-tracking refinement (D-30-06).
- Adapt `_is_session_call` (lines 38-45): unchanged shape — used for `session.delete(...)` detection.
- New helper `_resolve_payment_binding(tree: ast.Module) -> set[str]`: walks the module's top-level `ImportFrom` nodes and returns the set of local names bound to `app.modules.payments.models.Payment`. Empty set when the module doesn't import Payment → no-op (no false negatives per CONTEXT.md `<code_context>` "Integration Points" bullet 3).
- Adapt `_function_is_write_path` (lines 83-94): rename to `_function_violates_appendonly` — returns offender message or None per function.

**Live-test pattern (copy `test_service_commit_gate.py:187-223`):**
```python
def test_payments_appendonly_against_app_modules() -> None:
    """Live gate against every modules/**/service.py — forbids UPDATE/DELETE
    against the `payments.Payment` model class. Phase 30 INFRA-22 / B-01."""
    offenders: list[str] = []
    for service_path in sorted(_BACKEND_APP.glob(_SERVICE_GLOB)):
        tree = ast.parse(service_path.read_text(encoding="utf-8"),
                         filename=str(service_path))
        payment_names = _resolve_payment_binding(tree)
        if not payment_names:
            continue  # module doesn't reference Payment — no-op
        for func in _iter_functions_in_file(service_path):
            msg = _function_violates_appendonly(service_path, func, payment_names)
            if msg is not None:
                offenders.append(msg)
    assert not offenders, (
        "Payments append-only gate (B-01) failed.\n"
        "Offenders:\n  " + "\n  ".join(offenders)
    )
```

**Synthetic-test pattern (mirror `test_service_commit_gate.py:244-336`):**
- Use the `_check_snippet` helper pattern (lines 244-263) with `linecache.cache` injection so on-disk fixtures aren't strictly required for synthetic cases.
- BUT per D-30-07, parameterize against the on-disk fixtures at `apps/backend/tests/unit/fixtures/payments_violation_*.py` (see next section).

**Walker-scope sanity test (copy `test_service_commit_gate.py:226-236`):**
```python
def test_appendonly_walker_scope_is_modules_service_only() -> None:
    matches = list(_BACKEND_APP.glob(_SERVICE_GLOB))
    assert matches, "Walker glob found no service.py files — scope drift?"
    assert all(p.name == "service.py" for p in matches)
    assert all("modules" in p.parts for p in matches)
```

---

### `apps/backend/tests/unit/fixtures/payments_violation_*.py` (test/fixture — CREATE)

**Analog:** inline synthetic-source string-snippets at `test_service_commit_gate.py:273-322` (e.g. `test_synthetic_missing_commit_is_detected` lines 266-280).

**Current inline-snippet pattern (`test_service_commit_gate.py:266-280`):**
```python
def test_synthetic_missing_commit_is_detected() -> None:
    src = (
        "async def create_thing(session, actor):\n"
        "    session.add(thing)\n"
        "    await audit.emit(session, 'x', actor_user_id=None, resource_type='y')\n"
    )
    msg = _check_snippet(src, fake_filename="<missing_commit>")
    assert msg is not None
    assert "Phase 12.1 bug class" in msg
```

**Phase 30 fixture-file shape (D-30-07 — promote synthetic snippets to on-disk fixtures):**

`tests/unit/fixtures/__init__.py` — empty marker.

`tests/unit/fixtures/payments_violation_update.py` (must fail walker):
```python
"""Synthetic negative fixture — UPDATE against Payment (B-01 violation).

Imported by test_payments_appendonly.py to assert the walker catches the
update(Payment) shape. NOT executed at runtime; parsed by the AST walker only.
"""
from sqlalchemy import update
from app.modules.payments.models import Payment


async def violate_update(session) -> None:
    await session.execute(update(Payment).where(Payment.id == "x").values(amount_kopecks=0))
```

`tests/unit/fixtures/payments_violation_delete.py` (must fail walker):
```python
"""Synthetic negative fixture — DELETE against Payment (B-01 violation)."""
from sqlalchemy import delete
from app.modules.payments.models import Payment


async def violate_delete(session) -> None:
    await session.execute(delete(Payment).where(Payment.id == "x"))
```

`tests/unit/fixtures/payments_violation_on_conflict_update.py` (must fail walker — D-30-08):
```python
"""Synthetic negative fixture — on_conflict_do_update against Payment (B-01)."""
from sqlalchemy.dialects.postgresql import insert
from app.modules.payments.models import Payment


async def violate_on_conflict(session) -> None:
    stmt = insert(Payment).values(...).on_conflict_do_update(...)
    await session.execute(stmt)
```

`tests/unit/fixtures/payments_violation_session_delete.py` (must fail walker):
```python
"""Synthetic negative fixture — session.delete(<Payment instance>) (B-01)."""
from app.modules.payments.models import Payment


async def violate_session_delete(session, payment: Payment) -> None:
    await session.delete(payment)
```

`tests/unit/fixtures/payments_violation_clean_insert.py` (MUST PASS — control):
```python
"""Positive control — INSERT-only is allowed (D-30-08)."""
from sqlalchemy import insert
from app.modules.payments.models import Payment


async def clean_insert(session) -> None:
    session.add(Payment(amount_kopecks=100))
    await session.execute(insert(Payment).values(amount_kopecks=200))
```

**Parametrized test pattern in `test_payments_appendonly.py`:**
```python
import pytest


_FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize("fixture_filename", [
    "payments_violation_update.py",
    "payments_violation_delete.py",
    "payments_violation_on_conflict_update.py",
    "payments_violation_session_delete.py",
])
def test_walker_catches_violation_fixture(fixture_filename: str) -> None:
    path = _FIXTURES_DIR / fixture_filename
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    payment_names = _resolve_payment_binding(tree)
    assert payment_names, f"Fixture {fixture_filename} must import Payment"
    offenders = [
        msg for func in _iter_functions_in_file(path)
        if (msg := _function_violates_appendonly(path, func, payment_names))
    ]
    assert offenders, f"Walker failed to catch violation in {fixture_filename}"


def test_walker_passes_clean_insert_fixture() -> None:
    path = _FIXTURES_DIR / "payments_violation_clean_insert.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    payment_names = _resolve_payment_binding(tree)
    assert payment_names
    offenders = [
        msg for func in _iter_functions_in_file(path)
        if (msg := _function_violates_appendonly(path, func, payment_names))
    ]
    assert not offenders, f"Walker false-positive on clean insert: {offenders}"
```
**Why on-disk fixtures (not inline strings):** the walker uses import-tracking (D-30-06), which requires real `ast.ImportFrom` nodes referencing `app.modules.payments.models.Payment`. Inline strings work but obscure the real-shape assertion; on-disk `.py` fixtures double as living documentation of what is forbidden/allowed.

**Pyright/ruff exclusion:** these fixtures import `from app.modules.payments.models import Payment` which won't exist until Phase 32. Add `# type: ignore[import-not-found]` on the import lines AND exclude `tests/unit/fixtures/` from `ruff`/`mypy` via `[tool.ruff.lint.per-file-ignores]` and `[tool.mypy].overrides` (planner decides exact pyproject.toml stanza based on existing patterns).

---

### `apps/admin-web/src/shared/session/can.ts` (RBAC mirror — extend in place)

**Analog:** self — current 15-entry `OWNER_ONLY` array at `can.ts:12-29`.

**Current shape** (`apps/admin-web/src/shared/session/can.ts:12-29`):
```typescript
export const OWNER_ONLY: ReadonlyArray<{ action: Action; resource: Resource }> = [
  { action: 'view', resource: 'finance' },
  { action: 'view', resource: 'reports' },
  // …
  // Phase 15 INFRA-09 — v1.2 owner-only pairs (mirror permissions.py)
  { action: 'view', resource: 'membership-plans' },
  { action: 'edit', resource: 'membership-plans' },
  { action: 'create', resource: 'membership-plans' },
  { action: 'delete', resource: 'membership-plans' },
  { action: 'cancel', resource: 'memberships' },
  { action: 'delete', resource: 'memberships' },
]
```
**Phase 30 extension pattern (INFRA-19 mirror; comment block style copies `Phase 15 INFRA-09` annotation at line 22):**
```typescript
  // Phase 30 INFRA-19 — v1.4 owner-only pairs (mirror permissions.py)
  { action: 'create', resource: 'trainers' },
  { action: 'edit', resource: 'trainers' },
  { action: 'delete', resource: 'trainers' },
  // NOTE: (view, trainers) is NOT in OWNER_ONLY — reception needs ?active=true picker (TRN-04)
  { action: 'view', resource: 'pt-package-plans' },
  { action: 'create', resource: 'pt-package-plans' },
  { action: 'edit', resource: 'pt-package-plans' },
  { action: 'delete', resource: 'pt-package-plans' },
  { action: 'view', resource: 'payments' },
  // NOTE: (create, payments) is NOT in OWNER_ONLY — reception records sale (PAY-04)
  { action: 'cancel', resource: 'pt-packages' },
  { action: 'delete', resource: 'pt-packages' },
  // NOTE: (create/refund, pt-packages) NOT in OWNER_ONLY — reception sells + refunds (B-07)
  { action: 'cancel', resource: 'pt-sessions' },
  // NOTE: (create, pt-sessions) NOT in OWNER_ONLY — reception records session (PT-15)
```
- ~11 new entries; final array length = **26**.
- Byte-paritet contract with backend `permissions.py` `OWNER_ONLY`: same set of pairs after StrEnum value mapping.
- Parity test at `apps/backend/tests/unit/test_permissions.py:97-117` (test_specific_owner_only_membership) is the canonical asserter — extend its `expected = frozenset({...})` literal in lock-step.

**Parity-test extension in `apps/admin-web/src/shared/session/can.test.ts`** (`can.test.ts:28-35`):
```typescript
it('OWNER_ONLY covers ROLE-02/03/04 pairs', () => {
  const pairs = OWNER_ONLY.map((e) => `${e.action}:${e.resource}`)
  expect(pairs).toContain('view:finance')
  // …
})
```
Extend to spot-check the new v1.4 pairs: `'create:trainers'`, `'view:pt-package-plans'`, `'view:payments'`, `'cancel:pt-packages'`, `'cancel:pt-sessions'`. Add a parallel negative spot-check: `expect(pairs).not.toContain('view:trainers')`, `expect(pairs).not.toContain('create:payments')`, `expect(pairs).not.toContain('refund:pt-packages')`, `expect(pairs).not.toContain('create:pt-sessions')` (reception-retained rights).

---

### `apps/admin-web/src/shared/session/registry.ts` (RBAC mirror — extend in place)

**Analog:** self — current `Resource` string-literal union at `registry.ts:1-16`.

**Current shape** (`registry.ts:1-16`):
```typescript
export type Resource =
  | 'dashboard'
  | 'clients'
  | …
  | 'memberships' // NEW Phase 15 INFRA-09
  | 'membership-plans' // NEW Phase 15 INFRA-09 — kebab-case mirror of Resource.MEMBERSHIP_PLANS.value
  | 'visits' // NEW Phase 15 INFRA-09
  | 'profile' // NEW Phase 22 FE-09 — own-account surface; both roles allowed (NOT in OWNER_ONLY)
```
**Phase 30 extension pattern (INFRA-18 — 5 new union members):**
```typescript
  | 'trainers' // NEW Phase 30 INFRA-18 — mirror Resource.TRAINERS.value
  | 'payments' // NEW Phase 30 INFRA-18 — mirror Resource.PAYMENTS.value
  | 'pt-package-plans' // NEW Phase 30 INFRA-18 — kebab, mirror Resource.PT_PACKAGE_PLANS.value
  | 'pt-packages' // NEW Phase 30 INFRA-18 — kebab, mirror Resource.PT_PACKAGES.value
  | 'pt-sessions' // NEW Phase 30 INFRA-18 — kebab, mirror Resource.PT_SESSIONS.value
```
- Each string-literal MUST equal the backend StrEnum `.value` byte-for-byte (parity-test contract).

**`Action` union (`registry.ts:18-25`):** **UNCHANGED** per REQ INFRA-18 ("No new Action values").

**`routeRegistry` array (`registry.ts:47-81`):** **UNCHANGED** in Phase 30 (D-30-09). Routes for `/trainers`, `/pt-packages`, `/pt-package-plans` land in Phase 31/35 — Phase 30 ships only Resource enum entries.

**`navKey` union (`registry.ts:35-45`):** **UNCHANGED** — no new sidebar entries in Phase 30.

---

### `apps/admin-web/src/shared/api/services/mock/memberships.ts` (mock-service — one-liner fix)

**Analog:** self — current `list()` method at `memberships.ts:30-61`.

**Current shape** (`mock/memberships.ts:30-56`):
```typescript
async list(query: MembershipsListQuery): Promise<Pagination<Membership>> {
  await delay()
  ensure('view', 'memberships')
  const db = loadDB()
  let all = db.memberships
  if (query.clientId) {
    all = all.filter((m) => m.clientId === query.clientId)
  }
  if (query.status) {
    all = all.filter((m) => m.status === query.status)
  }
  // DEBT-02 (Phase 24): window comes from `query.within ?? 7` …
  if (query.expiring) {
    const within = query.within ?? 7
    const todayStr = todayMSK()
    const cutoff = new Date(todayStr)
    cutoff.setUTCDate(cutoff.getUTCDate() + (within - 1))
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    const items = all.filter(
      (m) => m.status === 'active' && m.endDate >= todayStr && m.endDate <= cutoffStr,
    )
    return { items, total: items.length, page: 1, pageSize: Math.max(1, items.length) }
  }
  // …
}
```
**DEBT-05 gap:** the early `if (query.status)` filter at lines 38-40 DOES apply, but the `if (query.expiring)` branch at lines 46-56 **hardcodes** `m.status === 'active'` (line 53), discarding `query.status` semantics when `expiring=true` is combined with `status=frozen`. ALSO, when neither `query.expiring` nor `query.status` is set, the "Заморожен" pill click at `MembershipsListPage.frozen.test.tsx:114-131` navigates to `{ status: 'frozen', expiring: false }` — that path is already covered by lines 38-40. So the DEBT-05 surface is the `expiring + status` interaction OR the renaming of the inline `m.status === 'active'` literal.

**One-liner fix (D-30-11):** inside the `if (query.expiring)` branch (line 53), replace the hardcoded `'active'` with `query.status ?? 'active'`:
```typescript
if (query.expiring) {
  const within = query.within ?? 7
  // …
  const wantedStatus = query.status ?? 'active'  // DEBT-05: respect query.status when combined with expiring
  const items = all.filter(
    (m) => m.status === wantedStatus && m.endDate >= todayStr && m.endDate <= cutoffStr,
  )
  return { items, total: items.length, page: 1, pageSize: Math.max(1, items.length) }
}
```
**Test extension pattern (mirror existing `memberships.read.test.ts:211-220` "Phase 28 FE-11 status filter parity" block — same import set, same `useSessionStore.setState({ role: 'owner' })` + DB-load + multiple-list-call shape):**
```typescript
// Phase 30 DEBT-05: status filter interaction with expiring
it('list applies query.status inside the expiring branch (DEBT-05)', async () => {
  useSessionStore.setState({ role: 'owner' })
  const frozenExpiring = await memberships.list({
    page: 1, pageSize: 1000, expiring: true, status: 'frozen'
  })
  expect(frozenExpiring.items.every((m) => m.status === 'frozen')).toBe(true)
  const activeExpiring = await memberships.list({
    page: 1, pageSize: 1000, expiring: true,  // status defaults to 'active'
  })
  expect(activeExpiring.items.every((m) => m.status === 'active')).toBe(true)
})
```
Add ONE more test (1-2 per D-30-11):
```typescript
// Phase 30 DEBT-05: «Заморожен» pill works under VITE_API_MODE=mock
it('list({ status: "frozen", expiring: false }) returns only frozen memberships', async () => {
  useSessionStore.setState({ role: 'owner' })
  const frozen = await memberships.list({ page: 1, pageSize: 1000, status: 'frozen', expiring: false })
  expect(frozen.items.every((m) => m.status === 'frozen')).toBe(true)
})
```

---

## Shared Patterns

### Locked-registry frozenset / dict shape
**Source:** `apps/backend/app/core/audit.py:102-157` (`LOCKED_AUDIT_EVENTS` frozenset)
**Apply to:** `audit_payloads.py` `AUDIT_PAYLOAD_SCHEMAS` dict + extension of `audit.py` `LOCKED_AUDIT_EVENTS` itself + extension of `permissions.py` `OWNER_ONLY` frozenset.

Same tuple-key shape `(event, resource_type)` indexes both the locked-event set AND the payload-schema registry. Identical lookup pattern: `if (event, resource_type) not in LOCKED_AUDIT_EVENTS:` (line 199) ↔ `schema = AUDIT_PAYLOAD_SCHEMAS.get((event, resource_type))`. Grouping comments by phase (`# v1.1 …`, `# v1.2 …`, `# v1.3 …`, `# v1.4 (Phase 30 lock — emitted in Phases 31/32/33/34)`).

### Hard-fail discipline (D-09)
**Source:** `apps/backend/app/core/audit.py:93-99` (`AuditEventNotLockedError(ValueError)`)
**Apply to:** payload validation in `audit.emit()` extension.

```python
class AuditEventNotLockedError(ValueError):
    """Hard fail in dev AND prod (Phase 15 D-09): unknown audit pair = programmer
    error (stale callsite or unlocked taxonomy). NO graceful degradation, NO
    DEBUG-only assert. Tests catch this exception explicitly.
    """
```
Phase 30 mirrors verbatim: `pydantic.ValidationError` from `schema.model_validate(payload)` propagates unchanged. NO `try/except`, NO debug-only assert. The error surfaces at the callsite with the standard Pydantic v2 error message; CI catches it via the existing `_iter_audit_emit_calls` walker pattern in `test_audit_taxonomy.py`.

### AST walker scaffolding
**Source:** `apps/backend/tests/unit/test_service_commit_gate.py:28-94` (constants + predicates) and `:177-184` (`_iter_functions_in_file` helper).
**Apply to:** `test_payments_appendonly.py` — same `_REPO_ROOT/_BACKEND_APP/_SERVICE_GLOB` constants, same `ast.walk` + `isinstance(ast.Call)` body shape, same `_iter_functions_in_file` reuse (or local clone).

Reusable helpers per CONTEXT.md `<code_context>` "Reusable Assets" bullet 2:
- `_is_session_call(node, attr)` — `test_service_commit_gate.py:38-45` — reuse for `session.delete(...)` detection.
- `_is_session_execute_with_mutating_sql(node)` shape — `test_service_commit_gate.py:48-70` — adapt to narrow `_MUTATING_SQL_FUNCS` to `{"update", "delete"}` and add import-tracking refinement.
- `_iter_functions_in_file(path)` — `test_service_commit_gate.py:177-184` — reuse unchanged.

### Synthetic-fixture testing
**Source:** `apps/backend/tests/unit/test_service_commit_gate.py:244-336` (six `test_synthetic_*` cases + `_check_snippet` helper with `linecache.cache` injection).
**Apply to:** `test_payments_appendonly.py` parametrized fixture tests.

Phase 30 differs: on-disk `.py` fixtures (per D-30-07) instead of inline strings, because import-tracking needs real `ImportFrom` AST nodes. Parametrize with `@pytest.mark.parametrize` over fixture filenames (4 violations + 1 control).

### Three-way RBAC parity (TEST-06 / FE-18 lineage)
**Source:** `apps/backend/tests/unit/test_permissions.py:97-117` (`test_specific_owner_only_membership` literal-frozenset assertion) + `apps/admin-web/src/shared/session/can.test.ts:13-17, 28-35`.
**Apply to:** byte-paritet between `permissions.py:OWNER_ONLY` ↔ `can.ts:OWNER_ONLY` ↔ `registry.ts:Resource` union.

Three nodes update in lock-step in Phase 30 plan 2 (RBAC bedrock) — same commit (D-30-09). Each StrEnum `.value` string equals the corresponding `can.ts`/`registry.ts` literal byte-for-byte; mismatch → parity test fails.

### Comment annotation convention
**Source:** `apps/backend/app/core/permissions.py:42-45` (`# Phase 15 INFRA-08`), `audit.py:39, 56, 149` (`## v1.2 (Phase 15 lock — emitted in Phases 16/17/19/20)`), `registry.ts:13-16` (`// NEW Phase 22 FE-09 — own-account surface; …`).
**Apply to:** every Phase 30 addition.

Each new line/entry across all touched files annotated with `# Phase 30 INFRA-NN` (Python) or `// NEW Phase 30 INFRA-NN — <intent>` (TypeScript). Group blocks prefixed with `# v1.4 (Phase 30 lock — emitted in Phases X/Y/Z)` mirroring v1.2/v1.3 grouping at `audit.py:39, 56, 149`.

### Pydantic v2 strict base
**Source:** `apps/backend/app/core/schemas.py:36-53` (`BackendSchemaBase` with `extra="forbid"` + `validate_by_name=True` + `validate_by_alias=True`).
**Apply to:** `audit_payloads.py` — DIVERGENT (does not inherit `BackendSchemaBase`).

Audit payloads use plain `pydantic.BaseModel` with `model_config = ConfigDict(extra="forbid")` only. NO `alias_generator=to_camel` (kwargs are snake_case Python internals, not camelCase wire format). NO `from_attributes=True` (not ORM-bound). NO `validate_by_alias` (no aliases in play). The `extra="forbid"` is the load-bearing invariant per D-30-01 (mirrors D-09 hard-fail).

---

## No Analog Found

None — every file has an existing analog or is a same-file extension. The single divergence-flagged case is `audit_payloads.py` (intentionally divergent from `BackendSchemaBase` for snake-case internal-kwargs reason).

---

## Planner Cross-Cuts

These constraints apply across all Phase 30 plans and are NOT file-specific patterns:

1. **Pre-create empty module placeholders** (for INFRA-20 / INFRA-21 to be satisfiable):
   - `apps/backend/app/modules/payments/__init__.py` — placeholder docstring.
   - `apps/backend/app/modules/payments/service.py` — empty (allows SVC001 walker scope extension to pass trivially).
   - `apps/backend/app/modules/pt_packages/__init__.py` — placeholder docstring.
   - `apps/backend/app/modules/pt_packages/service.py` — empty.
   - `apps/backend/app/modules/trainers/service.py` — empty (trainers `__init__.py` already exists per `app/modules/trainers/__init__.py`).
   - Optional per CONTEXT.md `<code_context>` "Integration Points" bullet 3: minimal `payments/models.py` stub with `class Payment(Base): __tablename__ = "payments"; ...` so the append-only walker has a class to resolve. **Planner decision:** include in Plan 3 to make Phase 30 self-contained (otherwise Phase 31/32 inherits a half-wired walker).

2. **Parity-test atomicity** (D-30-09): backend `permissions.py` changes + `can.ts` changes + `registry.ts` changes + `test_permissions.py` literal-set extension + `can.test.ts` spot-check extension all land in the same plan + same commit. No interleaved partial states.

3. **AST literal-string gate compatibility**: every new `LOCKED_AUDIT_EVENTS` tuple's `event` and `resource_type` strings must be literal at every future emit-callsite (Phase 31/32/33/34) — `test_audit_taxonomy.py:60-78` `_extract_event_and_resource_type` enforces this. Phase 30 only adds to the frozenset; no emit-callsites land in Phase 30.

4. **Pyproject/ruff/mypy exclusions for fixtures**: `tests/unit/fixtures/payments_violation_*.py` files import `from app.modules.payments.models import Payment` which doesn't exist until Phase 32. Per-file ignores must be added in `pyproject.toml` (planner identifies the exact stanza; mirrors any existing test-fixture exclusion pattern — there's no analog yet, so this is a small new addition).

---

## Metadata

**Analog search scope:**
- `apps/backend/app/core/` (audit.py, permissions.py, schemas.py)
- `apps/backend/tests/unit/` (test_service_commit_gate.py, test_audit_taxonomy.py, test_permissions.py)
- `apps/backend/.importlinter`
- `apps/backend/app/modules/{trainers,payments,pt_packages}/` (placeholder discovery)
- `apps/admin-web/src/shared/session/` (can.ts, registry.ts, can.test.ts)
- `apps/admin-web/src/shared/api/services/mock/memberships.ts` + `memberships.read.test.ts` + `MembershipsListPage.frozen.test.tsx`

**Files scanned:** ~14 source/test files + 1 lint-config.

**Pattern extraction date:** 2026-05-14.

*Pattern map ready for `gsd-planner` consumption.*
