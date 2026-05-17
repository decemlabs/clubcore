# Phase 37: Foundations Bedrock - Pattern Map

**Mapped:** 2026-05-17
**Files analyzed:** 14 source files + 8 tests
**Analogs found:** 22 / 22 (all locked targets have direct v1.3 / v1.4 precedents)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|---|---|---|---|---|
| `apps/backend/app/core/audit.py` | core taxonomy | append-only frozenset extension | self (same file, prior phase extensions) | exact |
| `apps/backend/app/core/audit_payloads.py` | core schema registry | Pydantic v2 + registry append | self (PT-session block, lines 278-313) | exact |
| `apps/backend/app/core/permissions.py` | core RBAC | enum + frozenset extension | self (Phase 30 INFRA-19 deltas, lines 74-93) | exact |
| `apps/backend/app/core/dependencies.py` | core Protocol slot | composition-root carve-out | self (ActivePtPackage block, lines 122-192) | exact |
| `apps/backend/app/main.py` | composition root | register-then-include-router | self (lines 117-173) | exact |
| `apps/backend/app/workers/telegram_bot.py` | bot composition root | defensive double-wiring | self (lines 57-69, REG-29-03 block) | exact |
| `apps/backend/app/modules/schedule/constants.py` (NEW) | module constants | declarative FSM map | `app/modules/pt_packages/constants.py` | exact |
| `apps/backend/app/modules/bookings/constants.py` (NEW) | module constants | declarative FSM map | `app/modules/pt_packages/constants.py` | exact |
| `.importlinter` (repo root) | architectural contract | independence-list extension | self (`modules-independent` contract, lines 13-28) | exact |
| `apps/backend/tests/unit/test_service_commit_gate.py` (extend `_INSPECTED_SERVICES`) | SVC001 AST walker scope | path-tuple append | self (lines 158-173) | exact |
| `apps/admin-web/src/shared/session/registry.ts` | frontend RBAC mirror | TS union extension | self (lines 1-30) | exact |
| `apps/admin-web/src/shared/session/can.ts` | frontend RBAC mirror | TS array extension | self (lines 12-44) | exact |
| `apps/backend/tests/test_audit_taxonomy.py` (count assert refresh) | static taxonomy test | size + membership asserts | self (lines 164-202) | exact |
| `apps/backend/tests/test_audit_payloads.py` (NEW or existing) | Pydantic schema tests | `model_validate` round-trip | `tests/unit/test_schemas.py:56-90` | partial |
| `apps/backend/tests/test_dependencies.py` (extend) | register/get round-trip | slot-set/get assertions | (no precedent — propose pattern) | NEW |
| `apps/backend/tests/test_app_wiring.py` (NEW) | startup integration | `create_app()` + accessor non-None | (no precedent — propose pattern) | NEW |
| `apps/backend/tests/test_importlinter.py` (existing or new) | importlinter contract | subprocess `lint-imports` invocation | (no precedent yet — see Plan 37-05) | NEW |
| `apps/backend/tests/test_booking_fsm.py` (NEW) | FSM unit test | parametrized matrix | `tests/unit/pt_packages/test_state_machine.py` | exact |
| `apps/backend/tests/test_slot_fsm.py` (NEW) | FSM unit test | parametrized matrix | `tests/unit/pt_packages/test_state_machine.py` | exact |
| `apps/backend/tests/integration/test_rbac_parity.py` (refresh) | byte-parity test | regex + set equality | self (lines 102-146) | exact |
| `apps/backend/tests/integration/telegram_bot/test_worker_handlers_registered.py` (extend or sibling) | bot-main parity | register call assertion | self + propose superset assertion | partial |

---

## Pattern Assignments

### 1. Audit Taxonomy (INFRA-24)

#### `apps/backend/app/core/audit.py` — extend `LOCKED_AUDIT_EVENTS`

**Analog:** self, prior phase extensions (lines 121-199).

**Append-only pattern** with grouped section comments. The 17 Phase 30 v1.4 entries are the closest neighbour for shape:

```python
# apps/backend/app/core/audit.py:175-198 (verbatim)
# v1.4 (Phase 30 lock — emitted in Phases 31/32/33/34 per INFRA-17 / B-03 / D-30-02)
# Trainers lifecycle (Phase 31 TRN-07):
("trainer_created", "trainer"),
("trainer_updated", "trainer"),
("trainer_deactivated", "trainer"),
("trainer_reactivated", "trainer"),
# Payments + refund (Phase 32 PAY-10 / REF-07):
("payment_recorded", "payment"),
("refund_issued", "payment"),
("membership_refunded", "membership"),
# PT-package plans (Phase 33 PT-03):
("pt_package_plan_created", "pt_package_plan"),
...
# PT-sessions (Phase 34 PT-21):
("pt_session_recorded", "pt_session"),
("pt_session_cancelled", "pt_session"),
```

**What Phase 37 must replicate:**
- Append a new section block at the bottom of the frozenset, BEFORE the closing `}`.
- Section header comment: `# v1.5 (Phase 37 lock — emitted in Phase 38 per INFRA-24 / C-06)`.
- One sub-comment per resource_type group (slot lifecycle, booking lifecycle).
- All 5 tuples are `(event_str, resource_type_str)` literals.
- **resource_type values must use snake_case (not kebab):** existing precedent is `"pt_package_plan"`, `"pt_session"`, `"membership_plan"`. Therefore use `"schedule_slot"` (NOT `"schedule-slots"`) and `"booking"` — these are audit `resource_type` values, NOT RBAC `Resource` enum kebab-on-wire values.
- 5 new tuples:
  - `("slot_published", "schedule_slot")`
  - `("slot_cancelled", "schedule_slot")`
  - `("booking_created", "booking")`
  - `("booking_cancelled", "booking")`
  - `("booking_no_show", "booking")`

**Baseline count correction:** the docstring + CONTEXT.md refer to "51 → 56" but the actual `len(LOCKED_AUDIT_EVENTS)` is **53** today (per `test_audit_taxonomy.py:182`). After Phase 37 the count becomes **58**. The "51 logical" number in CONTEXT.md / INFRA-24 reflects logical event names (not the `(event, resource_type)` tuple count). Use **58** in the count assert.

---

#### `apps/backend/app/core/audit_payloads.py` — 5 new schemas + `PtSessionRecordedPayload.booking_id` extension

**Analog:** self, `PtSessionRecordedPayload` (lines 278-296) and `MembershipRefundedPayload` (lines 127-135).

**Canonical Pydantic v2 schema shape** (copy verbatim):

```python
# apps/backend/app/core/audit_payloads.py:278-296 (verbatim)
class PtSessionRecordedPayload(BaseModel):
    """Payload schema for ("pt_session_recorded", "pt_session") — PT-21.

    `trainer_name_snapshot` (B-05) captures the trainer display name at
    recording time so historical UI integrity survives trainer rename /
    deactivation.
    `performed_at` is ISO-8601 datetime string with timezone offset.
    """

    model_config = ConfigDict(extra="forbid")

    pt_session_id: UUID
    pt_package_id: UUID
    client_id: UUID
    trainer_id: UUID
    trainer_name_snapshot: str
    performed_at: str
    performed_by_user_id: UUID
    sessions_remaining_after: int
```

**CRITICAL — UUID type discrepancy with CONTEXT.md D-37-09:**
CONTEXT.md says "every UUID field is typed `str`, not `uuid.UUID`" per REG-36-03 / P13. **The existing v1.4 schemas in `audit_payloads.py` actually type UUIDs as `uuid.UUID`** (see PtSessionRecordedPayload above — `pt_session_id: UUID`, `pt_package_id: UUID`, etc., with `from uuid import UUID` at line 34). The Pydantic v2 model accepts both str and UUID inputs on `model_validate` and stringifies on serialisation; the P13 lesson is about the **emit-callsite** sending `str(uuid)` to avoid raw `UUID` objects landing in JSONB.

**Recommendation for planner:** mirror the existing v1.4 precedent — type fields as `UUID`. This avoids divergence and lets Pydantic handle str↔UUID coercion. The P13 enforcement happens at the emit callsite (Phase 38 service code uses `str(booking.id)` when passing kwargs).  
**If CONTEXT.md D-37-09 is non-negotiable** (must be `str`), document the divergence in PLAN.md and pin the contract via `Field(pattern=r"^[0-9a-f-]{36}$")` for UUID validity.

**Registry-entry append pattern** (lines 323-345):

```python
# apps/backend/app/core/audit_payloads.py:343-345 (verbatim — last block before closing brace)
    # PT-sessions (Phase 34 PT-21)
    ("pt_session_recorded", "pt_session"): PtSessionRecordedPayload,
    ("pt_session_cancelled", "pt_session"): PtSessionCancelledPayload,
}
```

**What Phase 37 must replicate (5 new schemas, all `extra="forbid"`):**
- `SlotPublishedPayload` — fields: `slot_id`, `trainer_id`, `start_time: str` (ISO-8601), `end_time: str`, `created_by_user_id`.
- `SlotCancelledPayload` — fields: `slot_id`, `trainer_id`, `cancelled_by_user_id`, `cancel_reason: str`, `had_booking: bool` (per SLOT-09).
- `BookingCreatedPayload` — fields: `booking_id`, `slot_id`, `client_id`, `pt_package_id`, `created_by_user_id`.
- `BookingCancelledPayload` — fields: `booking_id`, `slot_id`, `cancelled_by_user_id`, `cancel_reason: str`.
- `BookingNoShowPayload` — fields: `booking_id`, `slot_id`, `client_id`, `no_show_at: str` (ISO-8601).
- Add 5 registry entries to `AUDIT_PAYLOAD_SCHEMAS` dict in a `# v1.5 (Phase 37 lock — emitted in Phase 38)` section block.

**`PtSessionRecordedPayload` extension** (additive, per Phase 33 D-33-15 precedent in `PtPackageSoldPayload` docstring lines 178-188):

```python
# Append a single field with default None — backward compatible.
booking_id: UUID | None = None  # Phase 37 INFRA-25 / C-06 — completion via existing event
```

Update the schema's docstring with the `booking_id` extension rationale (see `PtPackageSoldPayload:178-188` for the docstring shape to copy).

---

### 2. RBAC (INFRA-26 / INFRA-27 / D-37-01..03a)

#### `apps/backend/app/core/permissions.py` — extend `Resource`, `Action`, `OWNER_ONLY`

**Analog:** self (lines 30-94).

**`Resource` extension pattern — kebab on wire** (lines 41-50, verbatim):

```python
OWNER_AREA = "owner-area"  # member-name uses underscore; value contains hyphen
MEMBERSHIPS = "memberships"  # Phase 15 INFRA-08
MEMBERSHIP_PLANS = "membership-plans"  # Phase 15 INFRA-08 — kebab on wire (mirrors OWNER_AREA)
VISITS = "visits"  # Phase 15 INFRA-08
PROFILE = "profile"  # Phase 22 FE-09 — both roles, not OWNER_ONLY
TRAINERS = "trainers"  # Phase 30 INFRA-18 — v1.4 trainers module
PAYMENTS = "payments"  # Phase 30 INFRA-18 — v1.4 payments ledger
PT_PACKAGE_PLANS = "pt-package-plans"  # Phase 30 INFRA-18 — kebab (mirrors MEMBERSHIP_PLANS)
PT_PACKAGES = "pt-packages"  # Phase 30 INFRA-18 — kebab (multi-word)
PT_SESSIONS = "pt-sessions"  # Phase 30 INFRA-18 — kebab (multi-word)
```

**What Phase 37 must replicate (append at bottom of `Resource`):**
```python
SCHEDULE_SLOTS = "schedule-slots"  # Phase 37 INFRA-26 — v1.5 slot resource (kebab, multi-word)
BOOKINGS = "bookings"  # Phase 37 INFRA-26 — v1.5 booking resource (single word)
```

**`Action.LIST` append** (per D-37-03a; the existing 7-value enum at lines 20-27):
```python
LIST = "list"  # Phase 37 INFRA-26 / D-37-03a — semantic separation from VIEW for endpoint listings
```

**`OWNER_ONLY` extension pattern with inline phase comment** (lines 74-93, verbatim):

```python
# Phase 30 INFRA-19 — v1.4 owner-only pairs (trainers / payments / pt-package-plans /
# pt-packages / pt-sessions). Reception RETAINS: (VIEW, TRAINERS) for ?active=true
# picker (TRN-04), (CREATE, PAYMENTS) for sale flow (PAY-04), (REFUND, MEMBERSHIPS)
# uniform-reception (B-07), (CREATE, PT_PACKAGES) + (REFUND, PT_PACKAGES) (B-07/PT-07),
# (CREATE, PT_SESSIONS) (PT-15).
# Phase 34 D-34-09a removed `(CANCEL, PT_SESSIONS)` — B-12 grants reception a
# 24h cancel-window; the application layer raises `cancel_window_expired` 403
# from `pt_sessions.service.cancel_pt_session`, not RBAC. Final OWNER_ONLY size
# = 25 (was 26 after Phase 30 INFRA-19).
(Action.CREATE, Resource.TRAINERS),
(Action.EDIT, Resource.TRAINERS),
(Action.DELETE, Resource.TRAINERS),
(Action.VIEW, Resource.PT_PACKAGE_PLANS),
(Action.CREATE, Resource.PT_PACKAGE_PLANS),
(Action.EDIT, Resource.PT_PACKAGE_PLANS),
(Action.DELETE, Resource.PT_PACKAGE_PLANS),
(Action.VIEW, Resource.PAYMENTS),
(Action.CANCEL, Resource.PT_PACKAGES),
(Action.DELETE, Resource.PT_PACKAGES),
```

**What Phase 37 must replicate (append a Phase 37 INFRA-27 block):**
Per D-37-03 (4 owner-only adds for slots; reception keeps booking CRUD):
```python
# Phase 37 INFRA-27 — v1.5 owner-only pairs (schedule-slots).
# Reception RETAINS (NOT listed here): (VIEW, SCHEDULE_SLOTS), (LIST, SCHEDULE_SLOTS)
# for slot picker (SLOT-08), (CREATE, BOOKINGS) for booking flow (BOOK-02),
# (CANCEL, BOOKINGS) with 24h window enforced server-side (BOOK-06 / C-05),
# (VIEW, BOOKINGS), (LIST, BOOKINGS) for booking lists.
# Slot publication is owner-only in v1.5 (no trainer self-service per anti-feature list).
(Action.CREATE, Resource.SCHEDULE_SLOTS),
(Action.EDIT, Resource.SCHEDULE_SLOTS),
(Action.DELETE, Resource.SCHEDULE_SLOTS),
(Action.CANCEL, Resource.SCHEDULE_SLOTS),
```

**Note:** D-37-03 enumerates 4 new owner-only entries (delta confirmed CREATE/EDIT/DELETE/CANCEL on SCHEDULE_SLOTS). Final OWNER_ONLY size: **25 → 29** (not "25 → 35" as CONTEXT.md D-37-03 header states; that header miscounts because reception-retained pairs are not in OWNER_ONLY). Verify against the existing count test (`test_rbac_parity.py:140-146`) which must bump from 25 to 29.

---

#### `apps/admin-web/src/shared/session/registry.ts` — Resource union + Action union mirror

**Analog:** self (lines 1-31).

**TS union literal pattern** (verbatim shape):

```typescript
// apps/admin-web/src/shared/session/registry.ts:17-21 (verbatim)
  | 'trainers' // NEW Phase 30 INFRA-18 — mirror Resource.TRAINERS.value
  | 'payments' // NEW Phase 30 INFRA-18 — mirror Resource.PAYMENTS.value
  | 'pt-package-plans' // NEW Phase 30 INFRA-18 — kebab, mirror Resource.PT_PACKAGE_PLANS.value
  | 'pt-packages' // NEW Phase 30 INFRA-18 — kebab, mirror Resource.PT_PACKAGES.value
  | 'pt-sessions' // NEW Phase 30 INFRA-18 — kebab, mirror Resource.PT_SESSIONS.value
```

**Action union** (verbatim shape, lines 23-30):

```typescript
export type Action =
  | 'view'
  | 'create'
  | 'edit'
  | 'delete'
  | 'refund'
  | 'cancel' // NEW Phase 15 INFRA-09 — mirrors backend Action.CANCEL.value
  | 'check_in' // NEW Phase 15 INFRA-09 — underscore mirrors Action.CHECK_IN.value
```

**What Phase 37 must replicate:**

Append to `Resource` union:
```typescript
  | 'schedule-slots' // NEW Phase 37 INFRA-26 — kebab, mirror Resource.SCHEDULE_SLOTS.value
  | 'bookings' // NEW Phase 37 INFRA-26 — mirror Resource.BOOKINGS.value
```

Append to `Action` union:
```typescript
  | 'list' // NEW Phase 37 INFRA-26 / D-37-03a — mirrors backend Action.LIST.value
```

**Do NOT add** entries to `routeRegistry` (lines 52-86) — per D-37-08, no route/component work in Phase 37.

---

#### `apps/admin-web/src/shared/session/can.ts` — OWNER_ONLY array mirror

**Analog:** self (lines 12-44).

**Phase-30 INFRA-19 mirror block** (lines 29-44, verbatim):

```typescript
  // Phase 30 INFRA-19 — v1.4 owner-only pairs (mirror permissions.py).
  // Reception RETAINS (NOT in this array): {view, trainers}, {create, payments},
  // {refund, memberships}, {create, pt-packages}, {refund, pt-packages},
  // {create, pt-sessions}, {cancel, pt-sessions} (Phase 34 D-34-09a — B-12 24h
  // window enforced server-side via `cancel_window_expired` 403, not RBAC).
  { action: 'create', resource: 'trainers' },
  { action: 'edit', resource: 'trainers' },
  { action: 'delete', resource: 'trainers' },
  ...
  { action: 'cancel', resource: 'pt-packages' },
  { action: 'delete', resource: 'pt-packages' },
]
```

**What Phase 37 must append** (4 entries — kebab-on-wire on the resource side):

```typescript
  // Phase 37 INFRA-27 — v1.5 owner-only pairs (mirror permissions.py).
  // Reception RETAINS (NOT in this array): {view, schedule-slots}, {list, schedule-slots},
  // {create, bookings}, {cancel, bookings} (24h window enforced server-side via
  // `cancel_window_expired` 403, not RBAC — mirror Phase 34 D-34-09a), {view, bookings},
  // {list, bookings}. Slot publication is owner-only (no trainer self-service in v1.5).
  { action: 'create', resource: 'schedule-slots' },
  { action: 'edit', resource: 'schedule-slots' },
  { action: 'delete', resource: 'schedule-slots' },
  { action: 'cancel', resource: 'schedule-slots' },
```

---

### 3. FSM Constants (INFRA-30 / INFRA-31 / D-37-04)

#### `apps/backend/app/modules/schedule/constants.py` (NEW)
#### `apps/backend/app/modules/bookings/constants.py` (NEW)

**Analog:** `apps/backend/app/modules/pt_packages/constants.py` (verbatim shape).

**Canonical declarative-FSM map pattern** (pt_packages/constants.py:31-41):

```python
# apps/backend/app/modules/pt_packages/constants.py:31-41 (verbatim)
from collections.abc import Mapping
from types import MappingProxyType

PT_PACKAGE_STATUS_TRANSITIONS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "active": frozenset({"exhausted", "expired", "cancelled"}),
        "exhausted": frozenset({"cancelled"}),  # refund of exhausted package
        "expired": frozenset({"cancelled"}),  # refund of expired package
        "cancelled": frozenset(),  # terminal
    }
)
```

**Module-doc + `__all__` pattern** (pt_packages/constants.py:1-29, 53-57):

```python
"""PT-packages module constants (Phase 33 D-33-04 / D-33-05).

`PT_PACKAGE_STATUS_TRANSITIONS` is the declarative state-machine source of truth
for PT-package lifecycle (D-33-04). Keys are source statuses; values are
frozensets of allowed target statuses. Read-only via `MappingProxyType` so
module consumers cannot mutate it at runtime.

Transition matrix (D-33-04):
  - active    → {exhausted, expired, cancelled}
  - exhausted → {cancelled}   (refund of exhausted package)
  - expired   → {cancelled}   (refund of expired package)
  - cancelled → ∅             (terminal)

`str` keys (not the schema-layer `PtPackageStatus` enum) keep this module
importable from `models.py` and `service.py` without a circular import; the
schema-layer enum and the constant share string values.
"""

...

__all__ = [
    ...
    "PT_PACKAGE_STATUS_TRANSITIONS",
]
```

**CRITICAL DIVERGENCE from CONTEXT.md D-37-04:**

CONTEXT.md D-37-04 states `_assert_can_transition` should live "alongside `*_STATUS_TRANSITIONS` in `constants.py`". **The actual v1.3/v1.4 precedent places `_assert_can_transition` in `service.py`, not `constants.py`** — see:

```python
# apps/backend/app/modules/pt_packages/service.py:184-197 (verbatim)
def _assert_can_transition(pt_package: PtPackage, *, target: str) -> None:
    """Central state-machine guard (D-33-04).

    Consults `PT_PACKAGE_STATUS_TRANSITIONS` to decide whether
    `pt_package.status → target` is allowed; raises ``InvalidTransitionError``
    (409 invalid_transition) with discriminating `from_status` / `to_status`
    payload otherwise.
    """
    allowed = PT_PACKAGE_STATUS_TRANSITIONS.get(pt_package.status, frozenset())
    if target not in allowed:
        raise InvalidTransitionError(
            "invalid_transition",
            fields={"from_status": pt_package.status, "to_status": target},
        )
```

The guard signature is `(<ModelInstance>, *, target: str)` and it reads `<instance>.status`. The `InvalidTransitionError` is a `ConflictError` subclass (lines 136-145):

```python
class InvalidTransitionError(ConflictError):
    """Raised by ``_assert_can_transition`` on disallowed PT-package status moves.

    Constructor populates ``fields={'from_status': ..., 'to_status': ...}``.
    Mirrors memberships InvalidTransitionError shape but lives in this module
    so importlinter modules-independent contract stays clean.
    """
    code = "invalid_transition"
    status_code = 409
```

**Recommendation for planner:**
- **Phase 37 ships only the `*_STATUS_TRANSITIONS` constant in `constants.py`** (mirrors v1.4 INFRA-22 PT_PACKAGE_STATUS_TRANSITIONS pre-registered in Phase 30 — the guard lands later when service.py exists).
- `_assert_can_transition` + `InvalidTransitionError` land in `service.py` in Phase 38 alongside the actual bookings/schedule service code (they reference `ModelInstance.status` which requires the model to exist).
- Document this in PLAN.md so the planner doesn't try to put a guard in `constants.py` without a model to typecheck against.

**What Phase 37 must replicate (constants only):**

`apps/backend/app/modules/schedule/constants.py`:
```python
SLOT_STATUS_TRANSITIONS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "active": frozenset({"booked", "cancelled"}),
        "booked": frozenset({"active", "cancelled"}),  # active = booking-cancel restore
        "cancelled": frozenset(),  # terminal
    }
)
```
(3 legal transitions per CONTEXT.md / INFRA-31.)

`apps/backend/app/modules/bookings/constants.py`:
```python
BOOKING_STATUS_TRANSITIONS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "confirmed": frozenset({"cancelled", "no_show", "completed"}),
        "cancelled": frozenset(),  # terminal
        "no_show": frozenset(),    # terminal (no reverse per Q3 SUMMARY recommendation)
        "completed": frozenset(),  # terminal
    }
)
```
(3 legal transitions from `confirmed` per CONTEXT.md / INFRA-30.)

---

### 4. Protocol Slot Pattern (INFRA-32)

#### `apps/backend/app/core/dependencies.py` — 3 new Protocol slot blocks

**Analog:** self, `ActivePtPackage` block (lines 122-192) — silent-None semantics (matches all 3 new slots per CONTEXT.md `<code_context>` line 254).

**Canonical single-slot pattern** (`ActivePtPackage`, lines 122-192, verbatim):

```python
# apps/backend/app/core/dependencies.py:122-192 (verbatim — single complete slot)
# ─────────────────────────────────────────────────────────────────────────────
# Phase 33 D-33-12 — ActivePtPackage resolver slot.
#
# Second active-subject slot pair (after Phase 17 ActiveMembership). Phase 34
# pt_sessions service will call ``get_active_pt_package`` through this slot
# to validate that the client owns a live PT-package before recording a
# session. Like ActiveMembership, the consumer's failure mode for
# "no resolver registered" cannot be distinguished from "no active package"
# at the call site — silent-None semantics are the documented contract
# (D-33-12; mirrors line 117). The defensive-raise pattern is reserved for
# payment recorder/refunder (D-32-14) where a missing slot is hard
# misconfiguration.
#
# Wired EXCLUSIVELY from ``app.main.create_app`` (NOT from
# ``app.workers.telegram_bot.main`` — bot is not a PT-session participant
# in v1.4; mirrors D-32-14 discipline).
# ─────────────────────────────────────────────────────────────────────────────


class ActivePtPackage(Protocol):
    """Structural type for the active-PT-package row (Phase 33 D-33-12).

    Per D-33-12: only the attributes Phase 34 pt_sessions service consumes
    are declared (id, client_id, status, sessions_remaining, end_date).
    The SA ``PtPackage`` ORM structurally satisfies this Protocol — no DTO
    conversion at the resolver boundary (mirrors ``ActiveMembership``).
    """

    id: UUID
    client_id: UUID
    status: str
    sessions_remaining: int
    end_date: date | None


ActivePtPackageResolver = Callable[[AsyncSession, UUID], Awaitable[ActivePtPackage | None]]
"""Async callable: (session, client_id) -> ActivePtPackage | None.

Returns None when the client has no active PT-package (the canonical case
Phase 34 pt_sessions service treats as 'no package').
"""

_active_pt_package_resolver: ActivePtPackageResolver | None = None


def register_active_pt_package_resolver(resolver: ActivePtPackageResolver) -> None:
    """Composition-root setter — called once by ``app.main.create_app`` in Phase 33.
    ...
    Idempotent: re-registering replaces the slot (mirrors WR-05 reasoning).
    """
    global _active_pt_package_resolver
    _active_pt_package_resolver = resolver


async def get_active_pt_package(session: AsyncSession, client_id: UUID) -> ActivePtPackage | None:
    """Consumer entry point — used by ``app.modules.pt_sessions.service`` in Phase 34.

    Silent-None when the slot is unset (production code always registers in
    ``create_app()``; tests can register a stub or rely on the default-None
    behaviour). Mirrors ``resolve_active_membership`` (line 117) — D-33-12
    explicit choice: "no active package" is an expected state, not a
    misconfiguration.
    """
    if _active_pt_package_resolver is None:
        return None
    return await _active_pt_package_resolver(session, client_id)
```

**What Phase 37 must replicate — 3 new slot blocks, each block has:**

1. `# ─────...` 14-line block-comment header naming the phase, decision-id, consumer, and silent-None vs defensive-raise rationale.
2. `class Slot(Protocol):` — narrow attribute set (only what the consumer reads).
3. `SlotResolverType = Callable[..., Awaitable[Slot | None]]` — type alias with docstring.
4. `_module_private_slot: SlotResolverType | None = None` — module-private variable.
5. `def register_*(resolver: SlotResolverType) -> None:` — composition-root setter with `global` declaration, idempotent.
6. `async def get_*(...) -> Slot | None:` — silent-None consumer accessor.

**3 slots to ship (Phase 37 INFRA-32):**

**(a) `SlotByIdResolver`** — silent-None; consumer = `bookings.service.create_booking`.
- Protocol: `id: UUID`, `status: str`, `trainer_id: UUID`, `start_time: datetime`, `end_time: datetime` (consumed by booking-creation guards).
- Signature: `Callable[[AsyncSession, UUID], Awaitable[SlotById | None]]`.
- Comment header references "Phase 37 INFRA-32 / D-37-06; wired from `create_app()` AND `telegram_bot.main()` for `/book` callback validation (REG-29-03 defensive double-wiring)".

**(b) `BookingSlotRestorer`** — silent-None per CONTEXT.md (deviates from ARCHITECTURE.md `restore_slot_on_cancel` defensive-raise; CONTEXT.md `<code_context>` line 254 explicitly chooses silent-None for all 3). Consumer = `bookings.service.cancel_booking`.
- Signature: `Callable[[AsyncSession, UUID], Awaitable[None]]`.
- Comment header references "Phase 37 INFRA-32 / D-37-06; wired ONLY from `create_app()` — bot does not cancel bookings".

**(c) `BookingCompleter`** — silent-None per CONTEXT.md. Consumer = `pt_sessions.service.record_pt_session` when `booking_id` non-None.
- Signature: `Callable[[AsyncSession, UUID], Awaitable[None]]`.
- Comment header references "Phase 37 INFRA-32 / D-37-06 / C-03; wired ONLY from `create_app()` — bot does not record PT-sessions".

---

### 5. Composition-Root Wiring (INFRA-33)

#### `apps/backend/app/main.py` — append 3 `register_*` calls

**Analog:** self (lines 117-173) — the existing 7-call chain.

**Established register-block pattern** (lines 162-173, verbatim):

```python
# apps/backend/app/main.py:162-173 (verbatim — last register block)
# Phase 33 D-33-12: seventh composition-root carve-out — pt_sessions
# service (Phase 34) will validate active-PT-package existence via this
# Protocol slot. Wired EXCLUSIVELY here (NOT in telegram_bot.py — the
# bot is not a PT-session participant in v1.4; mirrors D-32-14
# payment-recorder discipline). Silent-None accessor (D-33-12) — a
# missing slot is NOT a hard error like payment_recorder; absence is
# indistinguishable from "no active package" at the consumer site.
from app.modules.pt_packages import (
    service as pt_packages_service,
)

register_active_pt_package_resolver(pt_packages_service.resolve_active_pt_package)

app.include_router(api)
return app
```

**What Phase 37 must replicate:**

Append BEFORE `app.include_router(api)` (line 175), AFTER `register_active_pt_package_resolver` (line 173), in deterministic order:

```python
# Phase 37 INFRA-33 / D-37-06: eighth-tenth composition-root carve-outs —
# v1.5 schedule + bookings cross-module Protocol slots. Schedule slot
# resolver wired BOTH here AND in app/workers/telegram_bot.py (defensive
# double-wiring per REG-29-03 — the bot's Phase 40 /book handler consumes
# the resolver via bookings.service). BookingSlotRestorer and
# BookingCompleter wired EXCLUSIVELY here (bot is not a participant —
# mirrors D-32-14 / D-33-12 discipline). All three are silent-None
# accessors (D-37-06).
from app.modules.schedule import service as schedule_service
from app.modules.bookings import service as bookings_service

register_slot_by_id_resolver(schedule_service.resolve_slot_by_id)
register_booking_slot_restorer(schedule_service.restore_slot_to_active)
register_booking_completer(bookings_service.complete_booking)
```

**Update the import block** (lines 41-49) to add 3 new register names from `app.core.dependencies`.

**Deterministic order matters** for the INFRA-33 startup snapshot test — append at the END of the register chain, NEVER insert in the middle.

**Phase 37 caveat:** Phase 38 will provide the real concrete functions; for Phase 37 the planner must decide:
- **Option A** (cleaner): leave the `register_*` calls commented out with `# Phase 38: ...` and ship only the Protocol-slot definitions in `dependencies.py`. The startup test then asserts only that the register/get functions exist and round-trip.
- **Option B** (more aligned with INFRA-33): ship stub implementations (e.g., `async def resolve_slot_by_id(session, slot_id): return None`) in the empty `schedule/__init__.py` / `bookings/__init__.py` so the `register_*` calls in main.py compile and the slot accessors return the stub. The Phase 38 service.py replaces the stub.

**Recommendation:** Option B — keeps the parity test green and the snapshot stable through Phase 38. Per `<specifics>` "Append at the end; don't insert in the middle." Per ARCHITECTURE.md `service.py` (Phase 38 deliverable). Stubs labelled `# noqa: SVC001 caller-owns-txn` if they touch session.

---

#### `apps/backend/app/workers/telegram_bot.py` — defensive register block

**Analog:** self (lines 57-69) — the existing REG-29-03 block.

**Defensive double-wiring pattern** (verbatim):

```python
# apps/backend/app/workers/telegram_bot.py:56-69 (verbatim)
# REG-29-03 (Phase 29 verification): the bot worker is a separate process
# from the FastAPI app, so it never goes through `app.main.create_app()`
# which is where the Protocol slot resolvers are registered. Without
# these calls, /checkin always hits the no-active-membership oracle-safe
# shared DM (D-20-9) and the bot is effectively dead. Register both the
# telegram-to-client resolver AND the client-to-active-membership
# resolver so the worker process matches the API process exactly.
register_client_by_telegram_resolver(clients_service.resolve_client_by_telegram_user_id)
register_active_membership_resolver(memberships_service.resolve_active_membership_by_client)
# Phase 31 D-31-14: defensive double-wiring for trainer resolver.
# Bot is not a consumer in v1.4 but must register to match API process exactly
# (per REG-29-03 lesson from Phase 29 verification).
register_trainer_by_id_resolver(trainers_service.resolve_trainer_by_id)
```

**What Phase 37 must replicate** (append after line 69):

```python
# Phase 37 DEBT-06 / D-37-06: missing v1.4 pt-package resolver — REG-29-03 omission
# fix. /book handler (Phase 40 BOT-02) consumes register_active_pt_package_resolver
# to gate on active-PT-package existence; without this the bot silently fails.
register_active_pt_package_resolver(pt_packages_service.resolve_active_pt_package)
# Phase 37 INFRA-33 / D-37-06: defensive double-wiring for v1.5 slot resolver.
# /book handler (Phase 40 BOT-02) consumes bookings.service which internally
# calls get_slot_by_id — must be registered in the bot process too.
register_slot_by_id_resolver(schedule_service.resolve_slot_by_id)
```

**Update the import block** (lines 26-30) to add `register_active_pt_package_resolver` and `register_slot_by_id_resolver`; and the module imports (lines 40-44) to add `pt_packages_service` and `schedule_service`.

---

### 6. importlinter Contract (INFRA-28)

#### `.importlinter` (repo root)

**NOTE:** The actual file is at `apps/backend/.importlinter`, NOT repo root. CONTEXT.md "repo root" is a typo — verify with planner.

**Analog:** self (`apps/backend/.importlinter`, lines 13-28).

**Verified state:** `app.modules.schedule` and `app.modules.bookings` are **ALREADY in the contract** (lines 22-23):

```ini
# apps/backend/.importlinter:13-28 (verbatim — current state)
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
    app.modules.payments
    app.modules.pt_packages
    app.modules.pt_sessions
```

**Mechanically nothing to edit** in the `.importlinter` file itself. However, INFRA-28 also requires a **negative-test fixture** — CONTEXT.md D-37-07 explicitly says "Add a negative-test fixture import (a one-line bad import in a `_negative_fixture.py`) exercising the contract under CI — pattern mirrors the v1.4 INFRA-21 negative fixture for SVC001."

**What Phase 37 must produce:**
1. A `_negative_fixture.py` somewhere under `apps/backend/app/modules/bookings/` (e.g., `_negative_importlinter_fixture.py`) containing a forbidden cross-module import:
   ```python
   """Phase 37 INFRA-28 negative fixture — gated by `if False:` so production code
   never imports it. CI test `test_importlinter.py` temporarily moves the gate
   open and asserts the contract FAILS (the import is forbidden by
   `modules-independent`). Mirrors v1.4 INFRA-21 SVC001 negative fixture +
   admin-web `apps/admin-web/scripts/assert-eslint-fixtures.mjs` pattern.
   """
   if False:
       from app.modules.schedule import service as _schedule  # noqa: F401 — fixture
   ```
2. A `test_importlinter.py` (or extend existing `tests/unit/test_importlinter.py` if it exists; verify) that:
   - Invokes `subprocess.run(["uv", "run", "lint-imports"], cwd=..., check=False)` on the real `.importlinter` config and asserts return code 0 (positive case).
   - Temporarily mutates the fixture to remove `if False:` (or copies a copy of `.importlinter` with a tighter contract), re-runs, and asserts return code != 0 with the bookings→schedule offender mentioned in stdout.

**No existing precedent for this exact test** — propose-pattern. Closest analog is `apps/admin-web/scripts/assert-eslint-fixtures.mjs` referenced by CONTEXT.md D-37-07.

---

### 7. SVC001 AST Walker Scope (INFRA-29)

#### `apps/backend/tests/unit/test_service_commit_gate.py` — extend `_INSPECTED_SERVICES`

**Analog:** self (lines 158-173) — the existing Phase 30 INFRA-21 pre-register precedent.

**Established pattern** (verbatim):

```python
# apps/backend/tests/unit/test_service_commit_gate.py:158-173 (verbatim)
_CLIENTS_SERVICE = _BACKEND_APP / "modules" / "clients" / "service.py"
_MEMBERSHIPS_SERVICE = _BACKEND_APP / "modules" / "memberships" / "service.py"
_AUTH_SERVICE = _BACKEND_APP / "modules" / "auth" / "service.py"
# Phase 30 INFRA-21 — pre-register placeholder service files so the live walker
# enters the new modules' write paths from the first commit in Phases 31/32/33.
_TRAINERS_SERVICE = _BACKEND_APP / "modules" / "trainers" / "service.py"
_PAYMENTS_SERVICE = _BACKEND_APP / "modules" / "payments" / "service.py"
_PT_PACKAGES_SERVICE = _BACKEND_APP / "modules" / "pt_packages" / "service.py"
_INSPECTED_SERVICES: tuple[Path, ...] = (
    _CLIENTS_SERVICE,
    _MEMBERSHIPS_SERVICE,
    _AUTH_SERVICE,
    _TRAINERS_SERVICE,
    _PAYMENTS_SERVICE,
    _PT_PACKAGES_SERVICE,
)
```

**Important:** the live test asserts `service_path.is_file()` (line 217), so the placeholder service files MUST exist (even if empty / zero-function). The walker handles zero-function files trivially per the test's own docstring (line 209: "A zero-function service passes the gate trivially").

**What Phase 37 must do:**

1. Append `_SCHEDULE_SERVICE` and `_BOOKINGS_SERVICE` to the tuple:
   ```python
   # Phase 37 INFRA-29 — pre-register v1.5 service files so the live walker
   # enters bookings/schedule write paths from the first commit in Phase 38.
   _SCHEDULE_SERVICE = _BACKEND_APP / "modules" / "schedule" / "service.py"
   _BOOKINGS_SERVICE = _BACKEND_APP / "modules" / "bookings" / "service.py"
   _INSPECTED_SERVICES: tuple[Path, ...] = (
       _CLIENTS_SERVICE,
       _MEMBERSHIPS_SERVICE,
       _AUTH_SERVICE,
       _TRAINERS_SERVICE,
       _PAYMENTS_SERVICE,
       _PT_PACKAGES_SERVICE,
       _PT_SESSIONS_SERVICE,  # Phase 34 — verify this is already in the tuple
       _SCHEDULE_SERVICE,
       _BOOKINGS_SERVICE,
   )
   ```
2. Create empty placeholder files: `apps/backend/app/modules/schedule/service.py` and `apps/backend/app/modules/bookings/service.py`, each with a single module docstring (Phase 37 placeholder per INFRA-29). The walker will trivially pass — no write paths to gate.

**Verify** before extending: re-read `_INSPECTED_SERVICES` first to confirm whether `pt_sessions/service.py` is already a member (it should be from Phase 34) — the tuple grew between Phase 30 and Phase 37 and the lines I read may be stale.

---

### 8. Tests

#### `apps/backend/tests/test_audit_taxonomy.py` — count assert refresh

**Analog:** self (lines 164-202).

**Existing count assert pattern** (verbatim):

```python
# apps/backend/tests/unit/test_audit_taxonomy.py:182-185 (verbatim)
assert len(LOCKED_AUDIT_EVENTS) == 53, (
    f"LOCKED_AUDIT_EVENTS size drifted: expected 53 "
    f"(18 v1.1 + 12 v1.2 + 6 v1.3 + 17 v1.4), got {len(LOCKED_AUDIT_EVENTS)}"
)
```

**What Phase 37 must replicate:**
- Bump count from `53` to `58` (5 new v1.5 pairs).
- Update the breakdown comment: `(18 v1.1 + 12 v1.2 + 6 v1.3 + 17 v1.4 + 5 v1.5)`.
- Update the docstring (lines 164-181) with a `## v1.5 (Phase 37 lock)` paragraph mirroring the v1.4 paragraph (lines 175-181) — naming the 5 events and the INFRA-24 / C-06 anchor.
- Add a new `test_locked_audit_events_includes_v15_pairs()` membership test mirroring `test_locked_audit_events_includes_v13_pairs()` (lines 188-201, verbatim):

```python
# Mirror pattern (existing v1.3 — lines 188-201):
def test_locked_audit_events_includes_v13_pairs() -> None:
    """INFRA-15 (Phase 24): the 6 v1.3 pairs are pre-registered for downstream phases."""
    expected = [
        ("membership_frozen", "membership"),
        ...
    ]
    for pair in expected:
        assert pair in LOCKED_AUDIT_EVENTS, (
            f"Phase 24 INFRA-15: required pair {pair} missing from LOCKED_AUDIT_EVENTS"
        )
```

Phase 37 version asserts the 5 new pairs are present.

---

#### `apps/backend/tests/test_audit_payloads.py` — schema validation tests

**Analog:** no dedicated file exists yet. Closest precedent: `apps/backend/tests/unit/test_schemas.py:56-90` (Pydantic `extra='forbid'` round-trip).

**Existing pattern** (Pydantic extra-forbid assertion shape):

```python
# apps/backend/tests/unit/test_schemas.py:56,90 (line refs from grep)
def test_backend_schema_base_config_uses_extra_forbid() -> None: ...
def test_request_extra_forbid_raises_on_unknown_field() -> None: ...
```

**What Phase 37 must produce** (proposed pattern — no existing dedicated audit-payload test file):

```python
"""Tests for v1.5 audit payload schemas (INFRA-25)."""
import pytest
from pydantic import ValidationError
from uuid import uuid4

from app.core.audit_payloads import (
    SlotPublishedPayload,
    SlotCancelledPayload,
    BookingCreatedPayload,
    BookingCancelledPayload,
    BookingNoShowPayload,
    PtSessionRecordedPayload,
    AUDIT_PAYLOAD_SCHEMAS,
)


def test_slot_published_payload_round_trip() -> None:
    """SlotPublishedPayload accepts the full kwarg set."""
    p = SlotPublishedPayload(
        slot_id=uuid4(),
        trainer_id=uuid4(),
        start_time="2026-05-20T10:00:00+03:00",
        end_time="2026-05-20T11:00:00+03:00",
        created_by_user_id=uuid4(),
    )
    assert p.slot_id is not None


def test_slot_published_payload_rejects_extra_keys() -> None:
    """extra='forbid' surfaces unknown payload keys at emit time."""
    with pytest.raises(ValidationError):
        SlotPublishedPayload(
            slot_id=uuid4(),
            trainer_id=uuid4(),
            start_time="2026-05-20T10:00:00+03:00",
            end_time="2026-05-20T11:00:00+03:00",
            created_by_user_id=uuid4(),
            spurious_key="should-be-rejected",  # extra='forbid'
        )


def test_pt_session_recorded_payload_accepts_optional_booking_id() -> None:
    """C-06 / D-37-05: booking_id is optional + None-default for back-compat."""
    base_kwargs = dict(
        pt_session_id=uuid4(),
        pt_package_id=uuid4(),
        client_id=uuid4(),
        trainer_id=uuid4(),
        trainer_name_snapshot="Иван Иванов",
        performed_at="2026-05-20T10:00:00+03:00",
        performed_by_user_id=uuid4(),
        sessions_remaining_after=4,
    )
    # No booking_id → still valid (back-compat).
    assert PtSessionRecordedPayload(**base_kwargs).booking_id is None
    # With booking_id → also valid.
    assert PtSessionRecordedPayload(**base_kwargs, booking_id=uuid4()).booking_id is not None


def test_v15_payload_schemas_registered() -> None:
    """5 new v1.5 (event, resource_type) pairs map to their Pydantic schemas."""
    assert AUDIT_PAYLOAD_SCHEMAS[("slot_published", "schedule_slot")] is SlotPublishedPayload
    assert AUDIT_PAYLOAD_SCHEMAS[("slot_cancelled", "schedule_slot")] is SlotCancelledPayload
    assert AUDIT_PAYLOAD_SCHEMAS[("booking_created", "booking")] is BookingCreatedPayload
    assert AUDIT_PAYLOAD_SCHEMAS[("booking_cancelled", "booking")] is BookingCancelledPayload
    assert AUDIT_PAYLOAD_SCHEMAS[("booking_no_show", "booking")] is BookingNoShowPayload
```

File location: `apps/backend/tests/unit/test_audit_payloads.py` (sibling of `test_audit_taxonomy.py`).

---

#### `apps/backend/tests/test_dependencies.py` — register/get round-trip for 3 new slots

**Analog:** no existing direct test for slot register/get round-trip. Closest: `apps/backend/tests/unit/test_dependencies_require_authenticated.py` (different pattern — exercises FastAPI dependency).

**Proposed pattern** (NEW — no precedent for slot round-trip tests):

```python
"""Unit test — register_*/get_* round-trip for Phase 37 Protocol slots (INFRA-32)."""
import pytest
from uuid import uuid4

from app.core.dependencies import (
    register_slot_by_id_resolver,
    resolve_slot_by_id,
    register_booking_slot_restorer,
    restore_booking_slot,
    register_booking_completer,
    complete_booking_by_pt_session,
)


@pytest.mark.asyncio
async def test_slot_by_id_resolver_round_trip() -> None:
    """register_slot_by_id_resolver(stub) -> resolve_slot_by_id calls stub."""
    called_with: list[tuple] = []
    async def stub_resolver(session, slot_id):
        called_with.append((session, slot_id))
        return None
    register_slot_by_id_resolver(stub_resolver)
    result = await resolve_slot_by_id(session=None, slot_id=uuid4())  # type: ignore[arg-type]
    assert result is None
    assert len(called_with) == 1


@pytest.mark.asyncio
async def test_slot_by_id_resolver_silent_none_when_unregistered() -> None:
    """D-37-06: unregistered slot returns None (silent-None semantics)."""
    # NOTE: requires test ordering / module-state reset. Use monkeypatch on
    # the module-private `_slot_by_id_resolver` variable, OR a per-test fixture
    # that captures + restores the slot's state.
    ...
```

**Caveat:** the module-private slot variables (`_slot_by_id_resolver: ... | None = None`) are global state. Tests must capture-and-restore via `monkeypatch.setattr(app.core.dependencies, "_slot_by_id_resolver", None)` or via a fixture, OR follow the pattern that `create_app()` is idempotent and tests register stubs through it. Mirror the existing precedent in test files that exercise `register_*` (see `test_dependencies_require_authenticated.py:1-50` for a related fixture-based approach).

---

#### `apps/backend/tests/test_app_wiring.py` (NEW) — startup integration test

**Analog:** no existing precedent (per CONTEXT.md the test is "existing or new"; search confirms it does not exist). Closest cousin: `tests/integration/telegram_bot/test_worker_handlers_registered.py` (registers handlers, asserts they ARE in `app.handlers`).

**Proposed pattern** (NEW):

```python
"""Startup integration test — create_app() registers all expected Protocol slots (INFRA-33)."""
import pytest

import app.core.dependencies as deps
from app.main import create_app


def test_create_app_registers_all_protocol_slots() -> None:
    """After create_app(), all module-private slot variables are non-None.

    Phase 37 INFRA-33 / D-37-06: deterministic registration order, all slots
    wired BEFORE app.include_router(api). This test pins the contract — any
    future register_* added to dependencies.py without a corresponding wire-up
    in create_app() will fail here loudly.
    """
    create_app()
    # Phase 4-34 slots (pre-existing):
    assert deps._user_loader is not None
    assert deps._active_membership_resolver is not None
    assert deps._client_by_telegram_resolver is not None
    assert deps._trainer_by_id_resolver is not None
    assert deps._payment_recorder is not None
    assert deps._payment_refunder is not None
    assert deps._active_pt_package_resolver is not None
    # Phase 37 INFRA-33 slots (new):
    assert deps._slot_by_id_resolver is not None
    assert deps._booking_slot_restorer is not None
    assert deps._booking_completer is not None


def test_bot_main_register_set_is_subset_of_api_main_register_set() -> None:
    """Parity test (INFRA-33 / D-37-06): the bot wires a subset of slots create_app() wires.

    Asserts via AST-walk that every register_* call inside
    app/workers/telegram_bot.py:main() ALSO appears inside
    app/main.py:create_app(). Currently bot wires:
      - register_client_by_telegram_resolver
      - register_active_membership_resolver
      - register_trainer_by_id_resolver
      - register_active_pt_package_resolver (Phase 37 DEBT-06 — newly added)
      - register_slot_by_id_resolver (Phase 37 INFRA-33 — newly added)
    """
    import ast
    from pathlib import Path

    REPO = Path(__file__).resolve().parents[2]
    MAIN_PY = REPO / "apps" / "backend" / "app" / "main.py"
    BOT_PY = REPO / "apps" / "backend" / "app" / "workers" / "telegram_bot.py"

    def _register_calls(path: Path) -> set[str]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id.startswith("register_"):
                    names.add(node.func.id)
        return names

    main_calls = _register_calls(MAIN_PY)
    bot_calls = _register_calls(BOT_PY)

    assert bot_calls <= main_calls, (
        f"bot_main_parity violation: bot wires register_* not in create_app(): "
        f"{sorted(bot_calls - main_calls)}"
    )
    # DEBT-06: bot must wire active_pt_package_resolver (REG-29-03 omission fix)
    assert "register_active_pt_package_resolver" in bot_calls
    # INFRA-33: bot must wire slot_by_id_resolver (defensive double-wire for /book)
    assert "register_slot_by_id_resolver" in bot_calls
```

---

#### `apps/backend/tests/test_booking_fsm.py` (NEW) + `apps/backend/tests/test_slot_fsm.py` (NEW)

**Analog:** `apps/backend/tests/unit/pt_packages/test_state_machine.py` (verbatim — entire file is the template).

**Canonical FSM unit-test shape** (lines 49-119, verbatim):

```python
# apps/backend/tests/unit/pt_packages/test_state_machine.py:49-119 (verbatim — abbreviated)
@pytest.mark.parametrize(
    ("from_status", "action", "expect"),
    [
        ("active", "cancel", "ok"),
        ("active", "expire", "ok"),
        ("active", "exhaust", "ok"),
        ("active", "noop", "invalid_transition"),
        ("exhausted", "cancel", "ok"),
        ("exhausted", "expire", "invalid_transition"),
        ...
    ],
)
def test_state_machine_matrix(from_status: str, action: str, expect: str) -> None:
    pt_package = _stub_pt_package(status=from_status)
    if action == "cancel":
        target = "cancelled"
        guard = _assert_can_cancel
    ...
    if expect == "ok":
        assert guard is not None
        guard(pt_package)
        return
    with pytest.raises(InvalidTransitionError) as exc_info:
        if guard is None:
            _assert_can_transition(pt_package, target=target)
        else:
            guard(pt_package)
    assert exc_info.value.code == "invalid_transition"
    assert exc_info.value.status_code == 409
    assert exc_info.value.fields == {"from_status": from_status, "to_status": target}


def test_pt_package_status_transitions_constant_is_immutable() -> None:
    """D-33-04: PT_PACKAGE_STATUS_TRANSITIONS is a MappingProxyType (read-only)."""
    from types import MappingProxyType
    from app.modules.pt_packages.constants import PT_PACKAGE_STATUS_TRANSITIONS
    assert isinstance(PT_PACKAGE_STATUS_TRANSITIONS, MappingProxyType)
    with pytest.raises(TypeError):
        PT_PACKAGE_STATUS_TRANSITIONS["active"] = frozenset()  # type: ignore[index]


def test_pt_package_status_transitions_phase33_contents() -> None:
    """D-33-04: locked transition matrix exactly matches the spec."""
    assert PT_PACKAGE_STATUS_TRANSITIONS["active"] == frozenset(...)
    ...
    assert set(PT_PACKAGE_STATUS_TRANSITIONS.keys()) == {...}
```

**What Phase 37 must replicate (per the constants-only deferral noted in §3):**

Since `_assert_can_transition` lands in service.py in Phase 38 (per the precedent), the Phase 37 fsm tests are **constants-shape tests only** — they assert the matrix contents and immutability. The transition-guard parametrize matrix lands in Phase 38 alongside service.py.

`apps/backend/tests/unit/bookings/test_booking_fsm.py`:

```python
"""Phase 37 INFRA-30 — BOOKING_STATUS_TRANSITIONS constants tests.

The _assert_can_transition guard lands in Phase 38 alongside bookings/service.py
(mirrors v1.3/v1.4 precedent at app/modules/pt_packages/service.py:184-197).
This file pins ONLY the declarative matrix contents + immutability.
"""
import pytest
from types import MappingProxyType
from app.modules.bookings.constants import BOOKING_STATUS_TRANSITIONS


def test_booking_status_transitions_is_mappingproxy() -> None:
    assert isinstance(BOOKING_STATUS_TRANSITIONS, MappingProxyType)
    with pytest.raises(TypeError):
        BOOKING_STATUS_TRANSITIONS["confirmed"] = frozenset()  # type: ignore[index]


def test_booking_status_transitions_contents() -> None:
    """C-04: confirmed → {cancelled, no_show, completed}; all other states terminal."""
    assert BOOKING_STATUS_TRANSITIONS["confirmed"] == frozenset({"cancelled", "no_show", "completed"})
    assert BOOKING_STATUS_TRANSITIONS["cancelled"] == frozenset()
    assert BOOKING_STATUS_TRANSITIONS["no_show"] == frozenset()
    assert BOOKING_STATUS_TRANSITIONS["completed"] == frozenset()
    assert set(BOOKING_STATUS_TRANSITIONS.keys()) == {"confirmed", "cancelled", "no_show", "completed"}


def test_booking_status_transitions_count_3_legal_from_confirmed() -> None:
    """INFRA-30: enumerates exactly 3 legal transitions from confirmed."""
    assert len(BOOKING_STATUS_TRANSITIONS["confirmed"]) == 3
```

`apps/backend/tests/unit/schedule/test_slot_fsm.py` — same shape, asserting:
```python
assert SLOT_STATUS_TRANSITIONS["active"] == frozenset({"booked", "cancelled"})
assert SLOT_STATUS_TRANSITIONS["booked"] == frozenset({"active", "cancelled"})
assert SLOT_STATUS_TRANSITIONS["cancelled"] == frozenset()
```

(Or, if the planner chooses to also ship the guard in service.py as a Phase 37 stub for symmetry, copy the entire `test_state_machine.py` 16-cell matrix shape.)

---

#### `apps/backend/tests/integration/test_rbac_parity.py` — refresh

**Analog:** self (already-existing test, lines 102-146).

**What Phase 37 must change:**
- Line 144 `len(OWNER_ONLY) == 25` → `== 29` (4 new entries from D-37-03).
- Line 144 docstring breakdown: append `+ 4 v1.5 INFRA-27`.
- Update breakdown comments at lines 5 (counts in docstring) to mention v1.5 totals.
- The set-equality tests (lines 102-137) auto-pick-up the new entries IF and only IF the frontend `can.ts` / `registry.ts` mirror lands in the same commit.

---

#### `apps/backend/tests/integration/telegram_bot/test_worker_handlers_registered.py` (extend or sibling)

**Analog:** self (lines 1-54). This test asserts `/start` + `/checkin` are registered as `CommandHandler`s on the bot Application.

**What Phase 37 may extend or duplicate** (the bot↔main parity assertion is covered in §`test_app_wiring.py` above via AST walk; this file is the per-handler registration shape).

If the planner prefers integration-shape over AST-shape, mirror this test for a future `book_handler` (Phase 40 BOT-01) — but that is OUT OF SCOPE for Phase 37. Phase 37's bot test is the AST parity in `test_app_wiring.py`.

---

## Shared Patterns

### Architectural boundary discipline

**Source:** `app/core/audit.py:98-99` + `app/core/audit_payloads.py:29-30` + `app/core/dependencies.py:1-7` (docstring blocks).

**Apply to:** All `app/core/*.py` edits in Phase 37.

```python
# Verbatim, app/core/audit.py:98-99:
Architectural boundary: app.core.audit MUST NOT import from app.modules.*
(importlinter `core-not-depend-on-modules` contract).
```

Phase 37 changes to `app/core/permissions.py`, `app/core/audit.py`, `app/core/audit_payloads.py`, `app/core/dependencies.py` MUST NOT add any `from app.modules.*` imports. The Protocol-slot pattern is the only legal cross-boundary.

---

### Composition-root carve-out

**Source:** `app/main.py:1-31` (docstring) + `app/main.py:106-117` (line-level rationale).

**Apply to:** Every new `register_*` call wired in Phase 37.

```python
# Verbatim, app/main.py:106-117:
# D-15: composition root fills the Phase 4 loader slot. This is the ONLY
# place where app.main reaches into app.modules.*. The importlinter
# contract scopes source_modules=app.core, so app.main is intentionally
# outside the scope.
#
# WR-05 (Phase 9 review): register_user_loader is idempotent by design ...
# Re-registering replaces the slot, which is intentional so tests can
# inject a stub loader through create_app().
```

Pattern: import the module's service inside `create_app()`'s body (NOT at module scope) to keep the carve-out local. Idempotent registration. Append at end of register chain (never insert).

---

### Phase-comment convention

**Source:** `app/core/permissions.py` lines 26, 27, 41-50, 66-93; `app/core/audit.py` lines 155-198.

**Apply to:** Every appended entry in Phase 37.

Format: `<value>,  # Phase NN INFRA-NN — <one-line rationale>`. For multi-line section breaks, use a paragraph comment block above the entries (see `permissions.py:74-83` for the canonical example).

---

### Pydantic v2 `extra='forbid'` audit payload discipline

**Source:** `app/core/audit_payloads.py:14-20` (docstring) + every existing schema (lines 43-313).

**Apply to:** All 5 new payload schemas + the `PtSessionRecordedPayload` extension.

Every schema:
1. Inherits `pydantic.BaseModel` (NOT `BackendSchemaBase` — these are internal snake_case kwargs, not wire DTOs).
2. Declares `model_config = ConfigDict(extra="forbid")` as the first body line.
3. Has a single-paragraph docstring naming `("event", "resource_type")` and the REQ-ID (e.g. `INFRA-25 / C-06`).
4. Field types follow v1.4 precedent (UUID, str, int, bool, list[str], date, datetime). See UUID-vs-str discrepancy note in §1 above.

---

### Test docstring shape

**Source:** Every `test_*.py` file in `tests/unit/`.

**Apply to:** All new Phase 37 tests.

```python
def test_foo() -> None:
    """<one-sentence claim asserting the locked behaviour>.

    <Optional 2-3 sentence rationale referencing REQ-ID / D-NN-NN.>
    """
    ...
```

The docstring is the test's contract anchor — planner-reviewed and verifiable against REQUIREMENTS.md.

---

## No Analog Found

| File | Role | Reason | Recommendation |
|---|---|---|---|
| `apps/backend/tests/unit/test_importlinter.py` (negative-fixture orchestrator) | importlinter subprocess + fixture toggle | No prior phase test invokes `lint-imports` as a subprocess; the negative-fixture pattern exists for ESLint (`apps/admin-web/scripts/assert-eslint-fixtures.mjs`) but not for importlinter | Propose pattern: subprocess.run + fixture-file mutation + assert-on-stdout, mirroring SVC001 INFRA-21 negative-fixture spirit. Document in PLAN.md as "NEW pattern; v1.5 baseline". |
| `apps/backend/tests/test_app_wiring.py` (Protocol-slot non-None startup assertions + bot-parity AST walk) | Startup integration + cross-process parity | No existing test asserts `create_app()`-registered slot state; `test_worker_handlers_registered.py` is the closest cousin but it tests bot handlers, not Protocol-slot state | Propose pattern above. Critical for INFRA-33 acceptance gate. |

---

## Metadata

**Analog search scope:**
- `apps/backend/app/core/` (all files read)
- `apps/backend/app/main.py`
- `apps/backend/app/workers/telegram_bot.py`
- `apps/backend/app/modules/{memberships,pt_packages,pt_sessions,bookings,schedule}/`
- `apps/backend/tests/unit/` + `apps/backend/tests/integration/`
- `apps/admin-web/src/shared/session/`
- `.importlinter` (located at `apps/backend/.importlinter`)

**Files scanned:** ~30 source files + ~15 test files

**Open verification items for the planner:**
1. Confirm `_INSPECTED_SERVICES` already includes `pt_sessions/service.py` (Phase 34 should have added it; verify line range — the cached read may be stale).
2. Confirm whether `_assert_can_transition` lives in `service.py` (verified precedent) vs `constants.py` (CONTEXT.md D-37-04 claim) — recommendation is `service.py` per the existing v1.3/v1.4 pattern; defer guards to Phase 38.
3. Confirm UUID-vs-str typing decision per §1 — the existing v1.4 schemas type as `UUID`, not `str`. Either align with precedent (UUID) or document the divergence to `str` explicitly.
4. Confirm `.importlinter` is at `apps/backend/.importlinter`, not repo root (CONTEXT.md says repo root — this is a typo).
5. Confirm baseline LOCKED_AUDIT_EVENTS count is 53 (not 51) — Phase 37 target is therefore 58 (not 56).
6. Confirm OWNER_ONLY current count is 25 → target is 29 (4 new entries), not "25 → 35" as CONTEXT.md D-37-03 header states.

---

*Pattern mapping date: 2026-05-17*
*Phase: 37-foundations-bedrock*
