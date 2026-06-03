# Phase 80: Booking Reschedule - Pattern Map

**Mapped:** 2026-06-03
**Files analyzed:** 9
**Analogs found:** 9 / 9

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `apps/backend/alembic/versions/0053_*.py` | migration | transform | `alembic/versions/0032_booking_notifications_widen_kind.py` | exact |
| `apps/backend/app/modules/client_portal/router.py` | controller | request-response | same file — `client_create_booking` (lines 337-396) | exact |
| `apps/backend/app/modules/client_portal/service.py` | service | request-response | same file — `create_booking_for_client_request` + `cancel_client_booking` (lines 429-521) | exact |
| `apps/backend/app/core/dependencies.py` | config/DI | request-response | same file — `BookingForClientCanceller` block (lines 1521-1574) | exact |
| `apps/backend/app/modules/bookings/service.py` | service | CRUD | same file — `create_booking_for_client` + `cancel_booking_for_client` (lines 1265-1654) | exact |
| `apps/backend/app/modules/bookings/notifications.py` | utility | transform | same file — `render_booking_reminder_24h_dm` (lines 93-104) | exact |
| `apps/backend/app/modules/client_portal/schemas.py` | model | transform | same file — `ClientCreateBookingRequest` + `ClientBookingResponse` (lines 128-167) | exact |
| `apps/backend/app/core/audit.py` + `audit_payloads.py` | model/config | event-driven | `LOCKED_AUDIT_EVENTS` + `BookingCancelledPayload` (audit.py lines 361-443, audit_payloads.py lines 453-474) | exact |
| `apps/client-pwa/src/screens/sheets/BookingManageSheet.jsx` + `src/data/booking.js` | component + service | request-response | cancel-flow wiring in `BookingManageSheet.jsx` (lines 150-173) + `useCancelBooking` in `clientQueries.ts` (lines 474-489) | exact |

---

## Pattern Assignments

### 1. `apps/backend/alembic/versions/0053_booking_notifications_widen_kind.py` (migration, transform)

**Analog:** `apps/backend/alembic/versions/0032_booking_notifications_widen_kind.py`

**File header + revision variables** (lines 1-74):
```python
"""widen booking_notifications.kind CHECK + unique constraint for 'rescheduled' kind (Phase 80 RESCH-02).

Revision ID: 0053_booking_notif_widen_kind_rescheduled
Revises: 0052_client_payment_methods
Create Date: 2026-06-03 ...
"""

from __future__ import annotations
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0053_booking_notif_widen_kind_rescheduled"
down_revision: str | None = "0052_client_payment_methods"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```

**Constraint name constant** (line 70 — must match the letter-for-letter name from 0020):
```python
# Name MUST match Migration 0020's op.f()-derived constraint identifier letter-for-letter.
# naming convention expands ck_%(table_name)s_%(constraint_name)s → ck_booking_notifications_kind
_KIND_CHECK_NAME = "ck_booking_notifications_kind"
```

**Unique constraint name** — from `0024_notification_channel_discriminator.py` (line 41 — NOT wrapped in op.f(), literal string):
```python
_BOOKING_NOTIFS_UNIQUE = "uq_booking_notifications_booking_kind_channel"
```

**Predicate constants** (lines 81-84 from 0032 — extend the existing 4-kind set with 'rescheduled'):
```python
_NEW_KIND_PREDICATE = (
    "kind IN ('reminder_24h', 'confirmed', 'cancelled_by_client', 'cancelled_by_owner', 'rescheduled')"
)
_OLD_KIND_PREDICATE = (
    "kind IN ('reminder_24h', 'confirmed', 'cancelled_by_client', 'cancelled_by_owner')"
)
```

**upgrade() body** (lines 87-113 from 0032 — exact sequence: widen VARCHAR first, then drop+recreate CHECK):
```python
def upgrade() -> None:
    # 1) Widen column VARCHAR(32) → VARCHAR(32) — no-op on size but needed for
    #    'rescheduled' (12 chars) which fits existing VARCHAR(32); keep the alter
    #    to be explicit and symmetric with 0032's pattern.
    op.alter_column(
        "booking_notifications", "kind",
        type_=sa.String(length=32),
        existing_type=sa.String(length=32),
        existing_nullable=False,
    )
    # 2) Drop + recreate CHECK with widened predicate.
    op.drop_constraint(op.f(_KIND_CHECK_NAME), "booking_notifications", type_="check")
    op.create_check_constraint(op.f(_KIND_CHECK_NAME), "booking_notifications", _NEW_KIND_PREDICATE)
    # 3) Drop + recreate UNIQUE to include 'rescheduled' in the allowed set
    #    (the unique constraint itself has no predicate — only the CHECK does;
    #    this step is a NO-OP on the unique constraint shape, but document it
    #    so the planner can verify the unique is already (booking_id, kind, channel)
    #    from 0024 and 'rescheduled' needs no unique-constraint change).
```

**NOTE for planner:** The unique constraint `uq_booking_notifications_booking_kind_channel` from 0024 already keys on `(booking_id, kind, channel)` — adding `'rescheduled'` to the CHECK is sufficient; no structural change to the UNIQUE is needed. The migration body is only a CHECK drop+recreate (same as 0032), with no VARCHAR ALTER needed since 'rescheduled' (12 chars) fits VARCHAR(32).

**downgrade() body** (lines 116-141 from 0032 — restore narrower CHECK, reverse order):
```python
def downgrade() -> None:
    op.drop_constraint(op.f(_KIND_CHECK_NAME), "booking_notifications", type_="check")
    op.create_check_constraint(op.f(_KIND_CHECK_NAME), "booking_notifications", _OLD_KIND_PREDICATE)
```

---

### 2. `apps/backend/app/modules/client_portal/router.py` — add `POST /client/booking/{id}/reschedule` (controller, request-response)

**Analog:** Same file, `client_create_booking` (lines 337-396) + `client_cancel_booking` (lines 399-434)

**Import block** (lines 41-43 — already present, no new imports needed beyond the new schema class):
```python
from app.core.dependencies import ClientPrincipal, require_client, verify_client_csrf
from app.core.idempotency import idempotent_execute, verify_client_idempotency
from app.core.schemas import ResponseEnvelope, envelope
```

**RBAC-04 decorator + function signature** — mirror `client_create_booking` exactly (lines 337-356):
```python
@router.post(
    "/booking/{booking_id}/reschedule",
    response_model=ResponseEnvelope[ClientBookingResponse],
    status_code=status.HTTP_200_OK,
    operation_id="client_reschedule_booking",
    summary=(
        "Reschedule the authenticated client's own confirmed booking to a new slot "
        "of the same trainer (RESCH-01; requires Idempotency-Key — D-70-02; "
        "409 slot_already_booked on race; 409 reschedule_window_expired if <24h; "
        "409 slot_trainer_mismatch on cross-trainer; 404 on non-owned booking)"
    ),
)
async def client_reschedule_booking(
    booking_id: UUID,
    payload: ClientRescheduleBookingRequest,
    request: Request,
    client: Annotated[ClientPrincipal, Depends(require_client())],
    _csrf: Annotated[None, Depends(verify_client_csrf)],
    idempotency_key: Annotated[str, Depends(verify_client_idempotency)],
    redis: Annotated[Redis, Depends(get_redis)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
```

**idempotent_execute body** — copy from `client_create_booking` (lines 379-396):
```python
    incoming_body = await request.body()
    client_id = client.id

    async def _runner() -> tuple[int, bytes]:
        booking = await service.reschedule_booking_for_client(
            session,
            client_id=client_id,
            booking_id=booking_id,
            new_slot_id=payload.new_slot_id,
        )
        body_bytes = json.dumps(
            envelope(booking).model_dump(mode="json", by_alias=True),
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return status.HTTP_200_OK, body_bytes

    return await idempotent_execute(redis, idempotency_key, incoming_body, runner=_runner)
```

**Docstring pattern** (lines 357-378 from `client_create_booking`):
```
RBAC-04 ordering: require_client() → verify_client_csrf → verify_client_idempotency → get_db / get_redis.
client.id is the IDOR-safe source: NO client_id in the body.
No try/except — AppError bubbles to _app_error_handler.
```

---

### 3. `apps/backend/app/modules/client_portal/service.py` — add `reschedule_booking_for_client` delegate (service, request-response)

**Analog:** Same file, `create_booking_for_client_request` (lines 429-488) and `cancel_client_booking` (lines 491-521)

**Import additions** — mirror lines 39-46, add `reschedule_booking_for_client` to the imports from `app.core.dependencies`:
```python
from app.core.dependencies import (
    ClientPrincipal,
    cancel_booking_for_client,
    create_booking_for_client,
    create_visit_client_qr,
    get_active_pt_package,
    invoke_client_checkout_core,
    reschedule_booking_for_client,  # NEW — Phase 80
)
```

**Delegate function signature** (mirror `cancel_client_booking` lines 491-521):
```python
async def reschedule_booking_for_client(
    session: AsyncSession,
    *,
    client_id: UUID,
    booking_id: UUID,
    new_slot_id: UUID,
) -> ClientBookingResponse:
    """Delegate reschedule to the Protocol-slot accessor (D-20-MODULE / RESCH-01).

    Calls ``app.core.dependencies.reschedule_booking_for_client`` — the composition-root
    slot wired to ``bookings.service.reschedule_booking_for_client`` in ``main.py``.
    NO direct ``app.modules.bookings`` import (D-20-MODULE / zero new ignore_imports).

    Propagates domain errors without catching:
      - BookingNotFoundError → 404 booking_not_found (IDOR anti-oracle)
      - RescheduleWindowExpiredError → 409 reschedule_window_expired
      - SlotTrainerMismatchError → 409 slot_trainer_mismatch
      - SlotAlreadyBookedError → 409 slot_already_booked (race)
    """
    result = await reschedule_booking_for_client(
        session,
        client_id=client_id,
        booking_id=booking_id,
        new_slot_id=new_slot_id,
    )
    r = cast(Any, result)
    return ClientBookingResponse(
        id=r.id,
        slot_id=r.slot_id,
        status=str(r.status),
        start_time=r.slot_start_time,
        trainer_name=str(r.trainer_full_name),
    )
```

---

### 4. `apps/backend/app/core/dependencies.py` — register `reschedule_booking_for_client` Protocol slot (config/DI, request-response)

**Analog:** Same file, `BookingForClientCanceller` block (lines 1521-1574) — copy the entire 3-part pattern verbatim.

**Three-part pattern** (lines 1521-1574):
```python
# ─────────────────────────────────────────────────────────────────────────────
# Phase 80 RESCH-01 / D-20-MODULE — BookingForClientRescheduler slot.
#
# Allows client_portal to invoke bookings.service.reschedule_booking_for_client
# WITHOUT importing bookings directly (D-20-MODULE: zero new ignore_imports).
# ─────────────────────────────────────────────────────────────────────────────

BookingForClientRescheduler = Callable[..., Awaitable[Any]]
"""Async callable: (session, *, client_id, booking_id, new_slot_id) -> BookingResponse.

Return type is ``Any`` at this scope (same rationale as BookingForClientCreator).
"""

_booking_for_client_rescheduler: BookingForClientRescheduler | None = None


def register_booking_for_client_rescheduler(rescheduler: BookingForClientRescheduler) -> None:
    """Composition-root setter — called by ``app.main.create_app()`` (Phase 80 RESCH-01).

    HTTP-only single-wire. Idempotent: re-registering replaces the slot
    (mirrors WR-05 reasoning).
    """
    global _booking_for_client_rescheduler
    _booking_for_client_rescheduler = rescheduler


async def reschedule_booking_for_client(
    session: AsyncSession,
    *,
    client_id: UUID,
    booking_id: UUID,
    new_slot_id: UUID,
) -> Any:
    """Consumer entry point — used by ``app.modules.client_portal`` (Phase 80 RESCH-01).

    Defensive-raise when the slot is not registered (mirrors cancel/create pattern).
    Return type is ``Any``; callers cast/type-narrow the result.
    Zero new ``ignore_imports``.
    """
    if _booking_for_client_rescheduler is None:
        raise RuntimeError(
            "BookingForClientRescheduler slot not registered — register via "
            "app.core.dependencies.register_booking_for_client_rescheduler() in "
            "app/main.py:create_app() (HTTP-only single-wire; see Phase 80 D-20-MODULE)."
        )
    return await _booking_for_client_rescheduler(
        session, client_id=client_id, booking_id=booking_id, new_slot_id=new_slot_id
    )
```

**main.py wiring** (after line 602 where create/cancel are registered):
```python
# Phase 80 RESCH-01 — reschedule Protocol slot.
register_booking_for_client_rescheduler(bookings_service.reschedule_booking_for_client)
```

---

### 5. `apps/backend/app/modules/bookings/service.py` — implement `reschedule_booking_for_client` (service, CRUD)

**Analog:** Same file, `create_booking_for_client` (lines 1265-1384) + `cancel_booking_for_client` (lines 1552-1653)

**Function signature** (mirror the shape of both analogs):
```python
async def reschedule_booking_for_client(
    session: AsyncSession,
    *,
    client_id: UUID,
    booking_id: UUID,
    new_slot_id: UUID,
) -> BookingResponse:
    """Atomic reschedule: cancel old slot + create new booking in one UoW (RESCH-01).

    PT-session credit PRESERVED (RESCH-01 / D-80-XX): reschedule is a slot MOVE.
    No sessions_remaining decrement, no restore. Any linked pt_session/credit
    carries to the new booking row (contrast with WR-06 owner-force-cancel restore path).

    SVC001: this function commits its own UoW.
    """
```

**Step sequence** (synthesised from cancel + create patterns):
```python
    now_utc = datetime.now(UTC)

    # Step 1 — Load old booking with row lock + eager slot (mirror cancel_booking_for_client:1593).
    booking = await repository.get_booking_by_id_for_update_with_slot(session, booking_id)

    # IDOR 404-collapse (D-20-IDOR): non-owned → BookingNotFoundError (anti-oracle, never 403).
    if booking is None or booking.client_id != client_id:
        raise BookingNotFoundError("booking_not_found")

    # Step 2 — FSM guard (same as cancel; booking must be 'confirmed').
    _assert_can_transition(booking, target="cancelled")

    # Step 3 — Reschedule window: 24h against ORIGINAL slot start (RESCH-01 / D-80-XX).
    if booking.slot.start_time - now_utc < timedelta(hours=CANCEL_WINDOW_HOURS_CLIENT):
        raise RescheduleWindowExpiredError("reschedule_window_expired")

    # Step 4 — Resolve new slot (mirror create_booking_for_client:1300-1306).
    new_slot = await resolve_slot_by_id(session, new_slot_id)
    if new_slot is None:
        raise SlotNotFoundError("slot_not_found")
    if new_slot.status != "active":
        raise SlotNotAvailableError("slot_not_available")
    if new_slot.start_time <= now_utc:
        raise SlotNotAvailableError("slot_not_available")

    # Step 5 — Same-trainer constraint (RESCH-01).
    if new_slot.trainer_id != booking.slot.trainer_id:
        raise SlotTrainerMismatchError("slot_trainer_mismatch")

    # Step 6 — Cancel old booking in-place (mirror cancel_booking_for_client:1613-1619).
    old_slot_id = booking.slot_id
    booking.status = "cancelled"
    booking.cancelled_at = now_utc
    booking.cancel_reason = "rescheduled"
    await restore_booking_slot(session, old_slot_id)

    # Step 7 — Flip new slot active→booked (mirror create_booking_for_client:1332-1344).
    slot_flipped = await repository.update_slot_status_predicate_gated(
        session, new_slot_id, from_status="active", to_status="booked"
    )
    if not slot_flipped:
        await session.refresh(new_slot, attribute_names=["status"])
        if new_slot.status == "booked":
            raise SlotAlreadyBookedError("slot_already_booked")
        raise SlotNotAvailableError("slot_not_available")

    # Step 8 — INSERT new booking row (mirror create_booking_for_client:1348-1354).
    # PT-session credit preserved: new booking reuses same pt_package_id.
    new_booking = await repository.insert_booking(
        session,
        slot_id=new_slot_id,
        client_id=client_id,
        pt_package_id=booking.pt_package_id,
        created_by_user_id=None,
    )

    # Step 9 — Flush + IntegrityError → SlotAlreadyBookedError (mirror create:1360-1366).
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if _is_slot_confirmed_conflict(exc):
            raise SlotAlreadyBookedError("slot_already_booked") from exc
        raise

    # Step 10 — Emit booking_rescheduled audit (LITERAL strings for INFRA-11 AST gate).
    await audit.emit(
        session,
        "booking_rescheduled",          # LITERAL — INFRA-11 AST gate
        actor_user_id=None,
        resource_type="booking",         # LITERAL — INFRA-11 AST gate
        resource_id=new_booking.id,
        old_booking_id=str(booking_id),
        new_booking_id=str(new_booking.id),
        old_slot_id=str(old_slot_id),
        new_slot_id=str(new_slot_id),
        old_start=booking.slot.start_time.isoformat(),
        new_start=new_slot.start_time.isoformat(),
        client_id=str(client_id),
        actor_role="client",             # LITERAL — INFRA-11 AST gate
    )

    # Step 11 — Commit (SVC001 gate).
    await session.commit()

    # Step 12 — Reload with slot+trainer joinedload (Phase 40 BLOCKER-2).
    reloaded = await repository.get_booking_by_id(session, new_booking.id)
    if reloaded is None:
        raise RuntimeError("reschedule_booking_for_client: new booking disappeared on reload")
    return _booking_response_from_orm(reloaded)
```

**New error classes** (mirror lines 133-202, add after `CancelWindowExpiredError`):
```python
class RescheduleWindowExpiredError(ConflictError):
    code = "reschedule_window_expired"

class SlotTrainerMismatchError(ConflictError):
    code = "slot_trainer_mismatch"
```

---

### 6. `apps/backend/app/modules/bookings/notifications.py` — add `render_booking_rescheduled_dm` (utility, transform)

**Analog:** Same file, `render_booking_reminder_24h_dm` (lines 93-104) + `BOOKING_REMINDER_24H_DM` constant (line 43)

**DM constant** (follow exact locked-copy pattern at lines 34-47 — single-line, noqa comments, OWNER-COPY-LOCK annotation):
```python
BOOKING_RESCHEDULED_DM: Final[str] = (
    "Здравствуйте, {client_name}! Ваша запись к тренеру {trainer_name} перенесена. Новое время: {new_slot_start_msk} (МСК). Ждём вас в зале!"  # noqa: E501, RUF001  # OWNER-COPY-LOCK — requires owner sign-off before merge
)
```

**Render function** (lines 93-104 verbatim shape — keyword-only args, str.format, docstring):
```python
def render_booking_rescheduled_dm(
    *,
    client_name: str,
    trainer_name: str,
    new_slot_start_msk: str,
) -> str:
    """Render the locked reschedule DM via ``str.format`` (unknown keys raise KeyError)."""
    return BOOKING_RESCHEDULED_DM.format(
        client_name=client_name,
        trainer_name=trainer_name,
        new_slot_start_msk=new_slot_start_msk,
    )
```

**NOTE:** The `new_slot_start_msk` value is pre-formatted by the caller as `new_slot.start_time.astimezone(MOSCOW_TZ).strftime("%d.%m.%Y %H:%M")` (per D-39-11 placeholder convention at line 21 of the file).

**`booking_notifications` INSERT for kind='rescheduled'** — follow the fan-out INSERT pattern in `service.py` (lines 775-838) for the `confirmed` / `cancelled_by_client` kinds, inserting a row with `kind='rescheduled'` and `channel='telegram'` for the new booking. The existing `uq_booking_notifications_booking_kind_channel` unique constraint guards against duplicate sends.

---

### 7. `apps/backend/app/modules/client_portal/schemas.py` — reschedule request/response schemas (model, transform)

**Analog:** Same file, `ClientCreateBookingRequest` (lines 128-145) + `ClientBookingResponse` (lines 148-167)

**Request body** (mirror `ClientCreateBookingRequest` shape — no client_id, extra='forbid' via ResponseData base):
```python
class ClientRescheduleBookingRequest(ResponseData):
    """POST /client/booking/{id}/reschedule body (Phase 80 RESCH-01).

    NO client_id field — the principal from require_client() is the IDOR-safe source.
    extra='forbid' (inherited from ResponseData) rejects any injected client_id.
    """

    new_slot_id: UUID
```

**Response** — reuse the existing `ClientBookingResponse` (lines 148-167). No new response schema needed; the endpoint returns the new booking via `ClientBookingResponse` (same fields: id, slot_id, status, start_time, trainer_name).

---

### 8. Audit event `booking_rescheduled` — `app/core/audit.py` + `app/core/audit_payloads.py` (model/config, event-driven)

**Analog:** `LOCKED_AUDIT_EVENTS` frozenset entry at audit.py lines 361-362 + `BookingCancelledPayload` at audit_payloads.py lines 453-474

**Step A — Add to `LOCKED_AUDIT_EVENTS` frozenset** (audit.py, after line 363 `booking_no_show`):
```python
        # Phase 80 RESCH-02 — single event for the reschedule operation (D-80-XX).
        # Links old→new booking; NOT a separate cancelled+created pair per CONTEXT.md.
        ("booking_rescheduled", "booking"),
```

**Step B — Add `BookingRescheduledPayload` in `audit_payloads.py`** (after `BookingNoShowPayload` ~line 492, before the next section):
```python
class BookingRescheduledPayload(BaseModel):
    """Payload schema for ("booking_rescheduled", "booking") — Phase 80 RESCH-02.

    Single event (not separate cancelled+created) per CONTEXT.md D-80.
    Links old→new booking ids and slot ids for forensic chain.
    """

    model_config = ConfigDict(extra="forbid")

    old_booking_id: UUID
    new_booking_id: UUID
    old_slot_id: UUID
    new_slot_id: UUID
    old_start: str   # ISO-8601 with TZ
    new_start: str   # ISO-8601 with TZ
    client_id: UUID
    actor_role: Literal["client"] = "client"
```

**Step C — Register in `AUDIT_PAYLOAD_SCHEMAS`** (audit_payloads.py, after line 1283):
```python
    ("booking_rescheduled", "booking"): BookingRescheduledPayload,
```

**INFRA-11 AST gate** — the `audit.emit()` call in `bookings/service.py` must use LITERAL strings for event name and resource_type: `"booking_rescheduled"` and `"booking"` (no f-strings, no variables in those positions — see pattern in `cancel_booking_for_client` lines 1629-1638).

---

### 9. `apps/client-pwa/src/screens/sheets/BookingManageSheet.jsx` + `src/data/booking.js` (component + service, request-response)

**Analog A — cancel-flow wiring** in same file (lines 13-14, 150-173):

**Hook import pattern** (line 6 — add `useRescheduleBooking` + `useClientAvailableSlots` to @/data imports):
```jsx
import { UPCOMING_BOOKING, useCancelBooking, useRescheduleBooking, useClientAvailableSlots } from '@/data';
```

**Cancel-flow wiring pattern** (lines 13-14, 150-173 — the exact template to mirror for reschedule):
```jsx
const cancelMutation = useCancelBooking();
// ...
const rescheduleMutation = useRescheduleBooking();
// ...
// In the reschedule confirm button handler (mirror the cancel button at lines 150-173):
disabled={rescheduleMutation.isPending}
onClick={async () => {
  setRescheduleError(null);
  try {
    await rescheduleMutation.mutateAsync({ bookingId: b.id, newSlotId: selectedSlot.slot_id });
    setView('done-reschedule');
  } catch (err) {
    const code = err && typeof err === 'object' && 'code' in err ? err.code : null;
    if (code === 'reschedule_window_expired') {
      setRescheduleError('Окно переноса истекло — обратитесь на ресепшн');
    } else if (code === 'slot_already_booked') {
      setRescheduleError('Этот слот уже занят. Выберите другое время.');
    } else if (code === 'slot_trainer_mismatch') {
      setRescheduleError('Слот другого тренера — перенос только к тому же тренеру.');
    } else {
      setRescheduleError('Не удалось перенести запись. Попробуйте ещё раз.');
    }
  }
}}
```

**Analog B — `useCancelBooking` in `clientQueries.ts`** (lines 474-489 — exact shape to copy for `useRescheduleBooking`):
```typescript
/**
 * POST /api/v1/client/booking/{booking_id}/reschedule — reschedule own booking (RESCH-01).
 * Requires Idempotency-Key header (D-70-02).
 * IDOR 404-collapse on non-owned booking.
 * onSettled invalidates bookings + availableSlots cache.
 */
export function useRescheduleBooking() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      bookingId,
      newSlotId,
      idempotencyKey,
    }: {
      bookingId: string
      newSlotId: string
      idempotencyKey: string
    }) => {
      const res = await clientRequest(
        'post',
        '/api/v1/client/booking/{booking_id}/reschedule',
        {
          params: { booking_id: bookingId },
          body: { new_slot_id: newSlotId },
          headers: { 'Idempotency-Key': idempotencyKey },
        },
      )
      return (res as { data: BookingResponse }).data
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: clientPortalKeys.bookings() })
      void qc.invalidateQueries({ queryKey: clientPortalKeys.availableSlots() })
    },
  })
}
```

**Mock calendar removal** — `CALENDAR`, `TIME_SLOTS`, `BUSY_SLOTS` are currently imported from `@/data` (line 6). The reschedule view uses `CALENDAR.find()` (line 37), `CALENDAR.slice(1).map()` (line 207), `TIME_SLOTS.filter()` (line 237), and `BUSY_SLOTS[trainerKey]` (line 183-184). These are replaced with real data from `useClientAvailableSlots` filtered to the booking's `trainer_id`. Remove imports of `BUSY_SLOTS`, `CALENDAR`, `TIME_SLOTS` from line 6.

**`src/data/index.js` export additions** (after line 41 where `useCancelBooking` is exported):
```javascript
  useRescheduleBooking,
```

The `CALENDAR`, `TIME_SLOTS`, `BUSY_SLOTS` exports on line 56 of `index.js` are removed from the reschedule view import but the line stays if other consumers remain — check first with grep.

**`BookingManageSheet.cancel.test.jsx` — test template** (full file lines 1-163): the reschedule wiring test follows the exact same structure:
- `vi.fn()` + `vi.mock('@/data', ...)` to stub `useRescheduleBooking`
- `const idleMutation = { mutateAsync: vi.fn().mockResolvedValue({}), isPending: false }`
- `beforeEach(() => { useRescheduleBooking.mockReset(); useRescheduleBooking.mockReturnValue(idleMutation) })`
- `describe` blocks for: calls `mutateAsync` with `{ bookingId, newSlotId }`, shows pending state, transitions to `done-reschedule`, stays on reschedule view on rejection with code-specific error copy

---

## Shared Patterns

### RBAC-04 Dependency Ordering
**Source:** `apps/backend/app/modules/client_portal/router.py` lines 351-353
**Apply to:** `client_reschedule_booking` handler
```python
client: Annotated[ClientPrincipal, Depends(require_client())],
_csrf: Annotated[None, Depends(verify_client_csrf)],
idempotency_key: Annotated[str, Depends(verify_client_idempotency)],
```

### IDOR 404-Collapse
**Source:** `apps/backend/app/modules/bookings/service.py` lines 1593-1600
**Apply to:** `reschedule_booking_for_client` in `bookings/service.py`
```python
booking = await repository.get_booking_by_id_for_update_with_slot(session, booking_id)
if booking is None or booking.client_id != client_id:
    raise BookingNotFoundError("booking_not_found")
```

### IntegrityError → SlotAlreadyBookedError Race Translation
**Source:** `apps/backend/app/modules/bookings/service.py` lines 1360-1366
**Apply to:** `reschedule_booking_for_client` flush step
```python
try:
    await session.flush()
except IntegrityError as exc:
    await session.rollback()
    if _is_slot_confirmed_conflict(exc):
        raise SlotAlreadyBookedError("slot_already_booked") from exc
    raise
```

### D-20-MODULE Protocol Slot (no direct cross-module import)
**Source:** `apps/backend/app/modules/client_portal/service.py` lines 436-441
**Apply to:** all `client_portal/service.py` delegates, `client_portal/router.py`
```python
# NO direct app.modules.bookings import — use Protocol slot accessor from app.core.dependencies.
# Zero new ignore_imports.
```

### INFRA-11 AST Gate (LITERAL strings in audit.emit)
**Source:** `apps/backend/app/modules/bookings/service.py` lines 1372-1383
**Apply to:** `audit.emit()` call in `reschedule_booking_for_client`
```python
await audit.emit(
    session,
    "booking_rescheduled",   # LITERAL — no variable, no f-string
    actor_user_id=None,
    resource_type="booking", # LITERAL — no variable, no f-string
    ...
)
```

### PWA Error Banner Pattern
**Source:** `apps/client-pwa/src/screens/sheets/BookingManageSheet.jsx` lines 102-132
**Apply to:** reschedule view error state
```jsx
{rescheduleError && (
  <div aria-live="polite" aria-atomic="true" style={{ position: 'absolute', ... }}>
    ...{rescheduleError}
  </div>
)}
```

### SVC001 Commit Gate
**Source:** `apps/backend/app/modules/bookings/service.py` lines 1644-1645
**Apply to:** `reschedule_booking_for_client` end of function
```python
# Slot implementation owns commit.
await session.commit()
```

---

## No Analog Found

All files have close analogs in the existing codebase. No fallback to RESEARCH.md needed.

---

## Metadata

**Analog search scope:** `apps/backend/alembic/versions/`, `apps/backend/app/core/`, `apps/backend/app/modules/client_portal/`, `apps/backend/app/modules/bookings/`, `apps/client-pwa/src/`
**Files read:** 22
**Pattern extraction date:** 2026-06-03
