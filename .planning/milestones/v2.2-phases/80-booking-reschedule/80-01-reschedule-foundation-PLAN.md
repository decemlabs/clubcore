---
phase: 80-booking-reschedule
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - apps/backend/alembic/versions/0053_booking_notifications_widen_kind.py
  - apps/backend/app/core/audit.py
  - apps/backend/app/core/audit_payloads.py
  - apps/backend/app/modules/bookings/notifications.py
  - apps/backend/app/modules/client_portal/schemas.py
  - apps/backend/tests/integration/test_alembic_0053_booking_notif_rescheduled.py
  - apps/backend/tests/unit/test_booking_notifications_copy.py
autonomous: true
requirements: [RESCH-02]
must_haves:
  truths:
    - "Migration 0053 widens booking_notifications.kind CHECK to allow 'rescheduled' and chains from 0052"
    - "Audit event ('booking_rescheduled', 'booking') is registered in LOCKED_AUDIT_EVENTS with a typed payload schema"
    - "render_booking_rescheduled_dm produces a locked DM string carrying the new slot time"
    - "ClientRescheduleBookingRequest schema accepts {new_slot_id} and forbids extra fields (no client_id)"
  artifacts:
    - path: "apps/backend/alembic/versions/0053_booking_notifications_widen_kind.py"
      provides: "CHECK-widening migration for 'rescheduled' kind"
      contains: "0052_client_payment_methods"
    - path: "apps/backend/app/core/audit_payloads.py"
      provides: "BookingRescheduledPayload + AUDIT_PAYLOAD_SCHEMAS registration"
      contains: "booking_rescheduled"
    - path: "apps/backend/app/modules/bookings/notifications.py"
      provides: "render_booking_rescheduled_dm + BOOKING_RESCHEDULED_DM"
      contains: "render_booking_rescheduled_dm"
    - path: "apps/backend/app/modules/client_portal/schemas.py"
      provides: "ClientRescheduleBookingRequest"
      contains: "ClientRescheduleBookingRequest"
  key_links:
    - from: "apps/backend/app/core/audit_payloads.py AUDIT_PAYLOAD_SCHEMAS"
      to: "BookingRescheduledPayload"
      via: "dict entry keyed ('booking_rescheduled','booking')"
      pattern: "booking_rescheduled.*BookingRescheduledPayload"
    - from: "apps/backend/app/core/audit.py LOCKED_AUDIT_EVENTS"
      to: "audit.emit('booking_rescheduled', ...)"
      via: "frozenset membership gate"
      pattern: "booking_rescheduled"
---

<objective>
Create the data + contract foundation for booking reschedule: migration 0053 (widen
`booking_notifications.kind` CHECK for the new `'rescheduled'` kind), the `booking_rescheduled`
audit event registration + typed payload, the locked reschedule DM template, and the
`ClientRescheduleBookingRequest` Pydantic schema.

Purpose: Plan 02 (service/endpoint) and Plan 03 (PWA) build against these contracts. The audit
event MUST exist in `LOCKED_AUDIT_EVENTS` before any `audit.emit("booking_rescheduled", ...)` call
can pass the INFRA-11 gate; the migration MUST exist before a `kind='rescheduled'` row can insert.

Output: migration 0053 + audit registration + DM renderer + request schema + their verification tests.
</objective>

<execution_context>
@/Users/andre/Workspace/Development/clubcore/.claude/get-shit-done/workflows/execute-plan.md
@/Users/andre/Workspace/Development/clubcore/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/80-booking-reschedule/80-CONTEXT.md
@.planning/phases/80-booking-reschedule/80-PATTERNS.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Migration 0053 — widen booking_notifications.kind CHECK for 'rescheduled'</name>
  <files>apps/backend/alembic/versions/0053_booking_notifications_widen_kind.py, apps/backend/tests/integration/test_alembic_0053_booking_notif_rescheduled.py</files>
  <read_first>
    - apps/backend/alembic/versions/0032_booking_notifications_widen_kind.py (EXACT analog — copy structure)
    - apps/backend/alembic/versions/0020_booking_notifications.py (origin of `ck_booking_notifications_kind` constraint name)
    - apps/backend/alembic/versions/0024_notification_channel_discriminator.py (origin of `uq_booking_notifications_booking_kind_channel`)
    - apps/backend/alembic/versions/0052_client_payment_methods.py (the down_revision target)
    - apps/backend/tests/integration/test_alembic_0049_customer_phone.py (alembic-test analog under tests/integration/fiscal_receipts/)
  </read_first>
  <action>
    Create migration with `revision = "0053_booking_notif_widen_kind_rescheduled"` and
    `down_revision = "0052_client_payment_methods"`. In `upgrade()`: drop constraint
    `op.f("ck_booking_notifications_kind")` (type_="check") on table `booking_notifications`, then
    recreate it with predicate `kind IN ('reminder_24h', 'confirmed', 'cancelled_by_client',
    'cancelled_by_owner', 'rescheduled')`. No VARCHAR alter is needed ('rescheduled' is 12 chars,
    fits VARCHAR(32)); the unique constraint `uq_booking_notifications_booking_kind_channel` already
    keys on (booking_id, kind, channel) per 0024 and needs no change. In `downgrade()`: drop + recreate
    the CHECK with the old 4-kind predicate (without 'rescheduled'). Add a top docstring noting
    Phase 80 RESCH-02. Create `test_alembic_0053_booking_notif_rescheduled.py` that runs
    `alembic upgrade head` against the test DB and asserts a `booking_notifications` row with
    `kind='rescheduled'` inserts successfully while an unknown kind still violates the CHECK.
  </action>
  <verify>
    <automated>cd apps/backend && uv run alembic upgrade head && uv run pytest tests/integration/test_alembic_0053_booking_notif_rescheduled.py -q</automated>
  </verify>
  <acceptance_criteria>
    - `uv run alembic upgrade head` applies 0053 with no error; `alembic current` shows 0053 head
    - Inserting a `booking_notifications` row with `kind='rescheduled'` succeeds
    - Inserting `kind='bogus'` still raises a CHECK violation
    - `down_revision` is exactly `"0052_client_payment_methods"`
    - test file exits 0
  </acceptance_criteria>
  <done>Migration 0053 applied to local Postgres; 'rescheduled' kind accepted; alembic-test green.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Register booking_rescheduled audit event + typed payload</name>
  <files>apps/backend/app/core/audit.py, apps/backend/app/core/audit_payloads.py</files>
  <read_first>
    - apps/backend/app/core/audit.py (LOCKED_AUDIT_EVENTS frozenset ~lines 361-443; the `booking_no_show` entry)
    - apps/backend/app/core/audit_payloads.py (BookingCancelledPayload ~lines 453-474; BookingNoShowPayload ~line 492; AUDIT_PAYLOAD_SCHEMAS dict ~line 1283)
  </read_first>
  <behavior>
    - AUDIT_PAYLOAD_SCHEMAS[("booking_rescheduled","booking")] resolves to BookingRescheduledPayload
    - BookingRescheduledPayload validates a payload with old_booking_id, new_booking_id, old_slot_id, new_slot_id, old_start, new_start, client_id, actor_role='client'
    - BookingRescheduledPayload rejects an extra/unknown field (extra='forbid')
    - ('booking_rescheduled','booking') is a member of LOCKED_AUDIT_EVENTS
  </behavior>
  <action>
    Add tuple `("booking_rescheduled", "booking")` to `LOCKED_AUDIT_EVENTS` in audit.py (after the
    `booking_no_show` entry) with a comment referencing Phase 80 RESCH-02 / single-event-not-pair.
    In audit_payloads.py add `BookingRescheduledPayload(BaseModel)` with `model_config =
    ConfigDict(extra="forbid")` and fields `old_booking_id: UUID, new_booking_id: UUID, old_slot_id:
    UUID, new_slot_id: UUID, old_start: str, new_start: str, client_id: UUID, actor_role:
    Literal["client"] = "client"`. Register it in `AUDIT_PAYLOAD_SCHEMAS` under key
    `("booking_rescheduled", "booking")`. This is a single event linking old→new (NOT a separate
    cancelled+created pair) per CONTEXT.md.
  </action>
  <verify>
    <automated>cd apps/backend && uv run python -c "from app.core.audit import LOCKED_AUDIT_EVENTS; from app.core.audit_payloads import AUDIT_PAYLOAD_SCHEMAS; assert ('booking_rescheduled','booking') in LOCKED_AUDIT_EVENTS; assert ('booking_rescheduled','booking') in AUDIT_PAYLOAD_SCHEMAS; print('ok')" && uv run mypy --strict app/core/audit_payloads.py</automated>
  </verify>
  <acceptance_criteria>
    - `("booking_rescheduled","booking")` present in both LOCKED_AUDIT_EVENTS and AUDIT_PAYLOAD_SCHEMAS
    - `BookingRescheduledPayload` rejects extra fields (extra='forbid')
    - `uv run mypy --strict app/core/audit_payloads.py` exits 0
    - `uv run ruff check app/core/audit_payloads.py app/core/audit.py` exits 0
  </acceptance_criteria>
  <done>Audit event + payload registered and typed; mypy strict clean.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Reschedule DM template + reschedule request schema</name>
  <files>apps/backend/app/modules/bookings/notifications.py, apps/backend/app/modules/client_portal/schemas.py, apps/backend/tests/unit/test_booking_notifications_copy.py</files>
  <read_first>
    - apps/backend/app/modules/bookings/notifications.py (BOOKING_REMINDER_24H_DM ~line 43; render_booking_reminder_24h_dm ~lines 93-104; OWNER-COPY-LOCK convention ~lines 34-47)
    - apps/backend/app/modules/client_portal/schemas.py (ClientCreateBookingRequest ~lines 128-145; ClientBookingResponse ~lines 148-167; ResponseData base)
    - apps/backend/tests/unit/test_booking_notifications_copy.py (copy-lock test analog)
  </read_first>
  <behavior>
    - render_booking_rescheduled_dm(client_name=, trainer_name=, new_slot_start_msk=) returns a string containing the trainer name and the new MSK time
    - render_booking_rescheduled_dm raises KeyError if a required placeholder key is missing
    - ClientRescheduleBookingRequest parses {"new_slot_id": "<uuid>"} successfully
    - ClientRescheduleBookingRequest rejects a body containing client_id (extra='forbid')
  </behavior>
  <action>
    In notifications.py add `BOOKING_RESCHEDULED_DM: Final[str]` (single-line, with `# noqa: E501,
    RUF001  # OWNER-COPY-LOCK` annotation) reading: greeting with `{client_name}`, mention trainer
    `{trainer_name}`, state new time `{new_slot_start_msk} (МСК)`. Add `render_booking_rescheduled_dm(*,
    client_name: str, trainer_name: str, new_slot_start_msk: str) -> str` delegating to
    `BOOKING_RESCHEDULED_DM.format(...)`. In schemas.py add `class ClientRescheduleBookingRequest(ResponseData)`
    with a single field `new_slot_id: UUID` and a docstring noting NO client_id (IDOR-safe principal
    source) and inherited extra='forbid'. Reuse the existing `ClientBookingResponse` for responses — do
    NOT add a new response schema. Extend `test_booking_notifications_copy.py` with a case asserting
    `render_booking_rescheduled_dm` renders all three placeholders and raises on a missing key.
  </action>
  <verify>
    <automated>cd apps/backend && uv run pytest tests/unit/test_booking_notifications_copy.py -q && uv run mypy --strict app/modules/bookings/notifications.py app/modules/client_portal/schemas.py && uv run ruff check app/modules/bookings/notifications.py app/modules/client_portal/schemas.py</automated>
  </verify>
  <acceptance_criteria>
    - `render_booking_rescheduled_dm` returns a non-empty string with the new MSK time substituted
    - Missing placeholder key raises KeyError
    - `ClientRescheduleBookingRequest(new_slot_id=...)` validates; extra `client_id` rejected
    - mypy --strict + ruff check exit 0 on both files
    - notifications copy test exits 0
  </acceptance_criteria>
  <done>DM renderer + reschedule request schema exist, typed, copy-lock-annotated, tested.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| migration → DB schema | DDL applied to shared Postgres; widened CHECK must not weaken existing kind validation |
| audit registration → forensic log | event name/resource_type must match emit-site literals (INFRA-11 AST gate) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-80-01 | Tampering | migration 0053 CHECK predicate | mitigate | downgrade restores the narrow predicate; only 'rescheduled' added — no kind removed; alembic-test asserts both accept-new and reject-bogus |
| T-80-02 | Repudiation | booking_rescheduled audit event | mitigate | event registered in LOCKED_AUDIT_EVENTS + typed payload with old/new ids for forensic chain |
| T-80-03 | Information Disclosure | ClientRescheduleBookingRequest | mitigate | extra='forbid' rejects injected client_id; only new_slot_id accepted (principal is IDOR source) |
| T-80-04 | Tampering | DM copy string | accept | OWNER-COPY-LOCK annotation flags for owner sign-off; no user input interpolated beyond name/trainer/time |
| T-80-SC | Tampering | npm/pip/cargo installs | mitigate | no new packages introduced in this plan; if any install appears, block on slopcheck human checkpoint |
</threat_model>

<verification>
- `uv run alembic upgrade head` green; 0053 at head
- `uv run pytest tests/integration/test_alembic_0053_booking_notif_rescheduled.py tests/unit/test_booking_notifications_copy.py -q` exits 0
- `uv run mypy --strict app` exits 0
- `uv run ruff check` exits 0 on modified files
- `uv run lint-imports` exits 0 (no new cross-module imports)
</verification>

<success_criteria>
Supports ROADMAP success criterion 3 (audit event + DM exist) by providing the registered
`booking_rescheduled` event, typed payload, and DM renderer; provides the migration enabling
`kind='rescheduled'` notification rows and the request schema consumed by Plan 02's endpoint.
</success_criteria>

<output>
Create `.planning/phases/80-booking-reschedule/80-01-SUMMARY.md` when done.
</output>
