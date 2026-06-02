# Phase 70: Client Bookings + QR Self Check-In - Pattern Map

**Mapped:** 2026-05-30
**Files analyzed:** 11 new/modified surfaces
**Analogs found:** 11 / 11 (every surface has an in-repo analog; this phase is exposure/binding, not greenfield)

Backend-only phase (FastAPI modular monolith). No frontend work. Every new surface mirrors an existing one — the dominant risk is *drift* from the analog (staff contract must stay byte-identical) and *import-boundary leakage* (D-20-MODULE: `client_portal` must reach `bookings`/`visits` writes only through composition-root Protocol slots, zero new `ignore_imports`).

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/modules/bookings/service.py` — extract actor-agnostic booking core (D-70-01) | service | request-response / CRUD-write | `create_booking_via_bot` (same file, `service.py:1131`) — already an actor-agnostic variant of `create_booking` | exact (precedent in same file) |
| `app/modules/bookings/service.py` — client cancel reuse (D-70-05/06) | service | CRUD-write | `cancel_booking` (`service.py:1264`) | exact |
| `app/modules/client_portal/router.py` — booking POST / cancel / slots-read / qr-token / check-in endpoints | route | request-response | `client_portal/router.py` (Phase-69 reads) + `bookings/router.py` (staff POST/cancel w/ Idempotency-Key) | exact (read), role-match (write) |
| `app/modules/client_portal/service.py` — booking write-slot delegate + slots read + qr issuance | service | CRUD-write + read | `client_portal/service.py` (read-only Phase 69) | role-match (write is new in this module) |
| `app/modules/client_portal/repository.py` — available-slots raw-SQL read (D-70-04) | repository | read | `client_portal/repository.py:fetch_client_membership` (raw-SQL cross-module read) | exact |
| `app/core/security.py` — `encode_qr_token` / `decode_qr_token` (D-70-07/08) | utility | transform (sign/verify) | `encode_client_token` / `decode_client_token` (`security.py:316-388`) | exact |
| `app/core/dependencies.py` — new booking-write Protocol slot + (maybe) visit-checkin slot (D-20-MODULE) | provider | event-driven (composition-root callback) | `register_booking_slot_restorer` / `BookingSlotRestorerCallable` (`dependencies.py:514-564`), `register_booking_completer` (`:586-616`) | exact |
| `app/modules/bookings/constants.py` — add `CANCEL_WINDOW_HOURS_CLIENT` (D-70-05) | config | n/a | `CANCEL_WINDOW_HOURS_RECEPTION` (`constants.py:41`) | exact |
| `app/modules/visits/service.py` — public client-QR wrapper around `_create_visit_with_anti_fraud` (D-70-11) | service | CRUD-write | `create_visit_self_checkin` (`visits/service.py:233`, channel=`telegram_bot`, `checked_in_by=None`) | exact |
| `alembic/versions/0045_*.py` — extend `ck_visits_channel` CHECK with `'client_qr'` | migration | DDL | `0006_visits.py:77-80` (original CHECK) | exact (constraint-recreate, not table-create) |
| `tests/integration/client_portal/test_*` — concurrency race, IDOR 404-collapse, QR replay/cross-client | test | n/a | `bookings/test_booking_race.py` (real-commit race) + `client_portal/test_idor_sweep.py` + root `conftest.py` SAVEPOINT harness | exact |

---

## Pattern Assignments

### `bookings/service.py` — extract actor-agnostic booking core (D-70-01)

**Analog:** `create_booking` (`apps/backend/app/modules/bookings/service.py:908-1123`) and its already-extracted sibling `create_booking_via_bot` (`:1131-1256`).

**Key insight:** `create_booking_via_bot` is the *exact precedent* for what D-70-01 asks. It already replays `create_booking`'s 10-step recipe with `actor` removed — `created_by_user_id=None`, `audit actor_user_id=None`, `actor_role="telegram_bot"` literal. The planner should extract the shared body into a helper (e.g. `_create_booking_core(session, *, client_id, slot_id, pt_package_id, created_by_user_id, audit_actor_user_id, actor_role)`) that BOTH `create_booking`, `create_booking_via_bot`, AND the new client write-slot call — OR add a third sibling (`create_booking_for_client`) mirroring `create_booking_via_bot`. Either keeps the staff path byte-identical.

**The 10-step recipe to preserve verbatim** (`service.py:957-1123`):
1. Slot resolve via `resolve_slot_by_id` (Protocol slot) → `SlotNotFoundError`/`SlotNotAvailableError`; defensive `slot.start_time <= now_utc` → `SlotNotAvailableError`.
2. `get_active_pt_package(session, client_id)` → `PtPackageNotActiveError` (None OR id-mismatch); `sessions_remaining <= 0` → `PtPackageExhaustedError`.
3. Trainer-match guard: `pkg_trainer_id is not None and pkg_trainer_id != slot.trainer_id` → `TrainerMismatchError`.
4. Moscow-TZ validity window: `pt_package.end_date < slot.start_time.astimezone(MOSCOW_TZ).date()` → `PtPackageExpiredBeforeSlotError`.
5. `repository.update_slot_status_predicate_gated(... from_status="active", to_status="booked")`; 0-row → refresh + `SlotAlreadyBookedError`/`SlotNotAvailableError`.
6. `repository.insert_booking(... created_by_user_id=<actor.id | None>)`.
7. `session.flush()` in try/except — `_is_slot_confirmed_conflict(exc)` → `SlotAlreadyBookedError`. **This is the criterion-#1 race guard.**
8. `audit.emit("booking_created", ...)` — literal event/resource strings (INFRA-11 AST gate).
9. `session.commit()` (SVC001 gate).
10. Reload + return `BookingResponse`.

**Actor parameterization (copy from `create_booking_via_bot`):** for client path pass `created_by_user_id=None` (column nullable since Alembic 0021 / D-40-05). For the audit emit, mirror the `actor_role="telegram_bot"` literal branch — the planner must decide on a `actor_role="client"` literal (Claude's Discretion item: investigate `audit.emit` actor support in `app/core/audit.py`; do NOT invent a fake staff user). The audit `actor_user_id` arg is `UUID | None` — pass `None` for client and stringify `client_id` into the payload's `created_by_user_id` field per Pitfall 13.

**Idempotency (D-70-02):** staff endpoint wraps the service call in `idempotent_execute` at the *router* layer (`bookings/router.py:117-128`), NOT in the service. The client endpoint mirrors this — `Depends(verify_idempotency)` + `idempotent_execute(redis, key, body, runner=_runner)`.

---

### `bookings/service.py` — client cancel (D-70-05 / D-70-06)

**Analog:** `cancel_booking` (`apps/backend/app/modules/bookings/service.py:1264-1404`).

**Window-check pattern to mirror** (`service.py:1315-1320`):
```python
now_utc = datetime.now(UTC)
if actor.role is Role.RECEPTION and (
    booking.slot.start_time - now_utc < timedelta(hours=CANCEL_WINDOW_HOURS_RECEPTION)
):
    raise CancelWindowExpiredError("cancel_window_expired")
```
For the client path: gate on the **new** `CANCEL_WINDOW_HOURS_CLIENT` constant, measured against `booking.slot.start_time` (D-38-16 — NOT `created_at`). Since the client has no `Role`, the actor-agnostic cancel core drops the `actor.role is Role.RECEPTION` branch and always applies the client window.

**Slot-restore-only (D-70-06):** `cancel_booking` already does the full sequence — FSM guard `_assert_can_transition(booking, target="cancelled")`, in-place mutate (`status="cancelled"`, `cancelled_at`, `cancel_reason`), `await restore_booking_slot(session, booking.slot_id)` (Protocol slot, `booked→active`), flush, `audit.emit("booking_cancelled", ...)` (4-key payload — NO `client_id`), commit. **NO `sessions_remaining` touch** — verified: cancel never decrements credit (that lives only in `pt_sessions/repository.py:62`). Reuse verbatim.

**IDOR 404-collapse (D-20-IDOR):** the load is `repository.get_booking_by_id_for_update_with_slot`; client cancel must add a `booking.client_id == principal.id` ownership check that 404-collapses to `BookingNotFoundError("booking_not_found")` (anti-oracle — never reveal the booking exists for another client). The staff path does NOT have this check (staff can cancel any booking), so this is the one place the client cancel diverges from the analog.

---

### `client_portal/router.py` — new client write + read endpoints

**Read-endpoint analog (membership/home/bookings GETs):** `client_portal/router.py:46-233`. Copy the decorator shape exactly:
```python
@router.get(
    "/membership",
    response_model=ResponseEnvelope[ClientMembershipResponse | None],
    operation_id="client_get_membership",      # client_ prefix — D-20-OPENAPI
    summary="...",
)
async def client_get_membership(
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[ClientMembershipResponse | None]:
    result = await service.get_client_membership(session, client.id)
    return envelope(result)
```
Conventions to carry: `tags=["Client-Portal"]` (already on the router, `:38`), `operation_id="client_*"` prefix, `ResponseEnvelope[...]` + `envelope(...)`, **no try/except** (AppError bubbles to `_app_error_handler`).

**Write-endpoint shape (booking POST + cancel):** copy `bookings/router.py:63-196`. The client write endpoints add `Depends(verify_client_csrf)` (the client variant, `dependencies.py:1254`) AND `Depends(verify_idempotency)` + `idempotent_execute` runner. RBAC-04 ordering: `require_client()` (the auth/principal dep) BEFORE `verify_client_csrf` BEFORE `verify_idempotency` BEFORE `get_db`. `client.id` is the IDOR-safe source — never a body/path `client_id`.

**`GET /client/qr-token`** — behind `require_client()` (D-70-09), no membership pre-check, mints a fresh token via `encode_qr_token(client.id)`. Read-style handler (GET, no CSRF). Returns the token + `expires_in` to the PWA.

**`POST /client/check-in`** — the ONE endpoint NOT behind `require_client()` (D-70-11). The signed QR token is the credential (gym scanner/turnstile is the caller). Reads token from request body/header → `decode_qr_token(token)` → `client_id = claims.sub` (the ONLY source — no body/path client_id, making cross-client structurally impossible, criterion #5) → calls the visits client-QR wrapper. Rate-limiting on this unauthenticated endpoint is Claude's Discretion.

**Mount:** all new routes attach to the existing `client_portal_router` mounted at `/api/v1/client` (`app/api/v1/router.py:103`). FastAPI merges disjoint sub-paths (D-20-MODULE). `/client/check-in` lives on the same router but simply omits the `require_client()` dependency.

---

### `client_portal/service.py` — booking write-slot delegate + slots read + qr issuance

**Analog:** `client_portal/service.py` (Phase-69 read-only orchestrator). The module is currently read-only (`No session.commit()` per its docstring `:5`); this phase adds the first *write* paths.

**CRITICAL — D-20-MODULE Protocol-slot writes:** `client_portal/service.py` must NOT `from app.modules.bookings import ...` or `from app.modules.visits import ...`. The write delegates through a composition-root Protocol slot in `app.core.dependencies` (see next section). The read path already proves the discipline — it imports only `app.core.pagination` and `app.modules.client_portal.repository` (`service.py:19-31`). The booking write-slot call looks like:
```python
booking = await create_booking_for_client(session, client_id=client.id, slot_id=..., pt_package_id=...)
```
where `create_booking_for_client` is the new accessor in `core.dependencies` (NOT a direct bookings import).

**Available-slots read (D-70-04):** add a read function mirroring `list_client_visits` (`service.py:96-117`) — call a new repository raw-SQL reader, map rows to a client-safe projection schema (trainer name/specialization + start/end), paginate via `PaginatedData`. Reuse the trainer-match predicate: if the active PT-package pins a trainer, filter to that trainer's `'active'` future slots; else all active trainers'.

---

### `client_portal/repository.py` — available-slots raw-SQL read (D-70-04)

**Analog:** `fetch_client_membership` (`client_portal/repository.py:40-72`).

**Cross-module raw-SQL read discipline (header `:6-16`):**
```python
from sqlalchemy import text   # NEVER import another module's ORM model
row = (await session.execute(
    text("SELECT ... FROM trainer_availability_slots s JOIN trainers t ON ... "
         "WHERE s.status = 'active' AND s.start_time > now() ... "),
    {"client_id": str(client_id), "trainer_id": ...},  # :name binds, UUIDs → str
)).mappings().all()
return [dict(r) for r in row]
```
Use `.mappings().all()` for the list, `:name` bind params with `str(uuid)` casts. Document verified source columns + `file:line` of the foreign table (`trainer_availability_slots` — `app/modules/schedule/models.py`). Read-only; no write SQL here.

---

### `app/core/security.py` — `encode_qr_token` / `decode_qr_token` (D-70-07 / D-70-08)

**Analog:** `encode_client_token` (`security.py:316-340`) + `decode_client_token` (`:343-388`) + `ClientAccessTokenClaims` dataclass (`:300-313`).

**Encode pattern to mirror** (`security.py:316-340`):
```python
def encode_qr_token(client_id: UUID, *, now: datetime | None = None) -> str:
    settings = get_settings()
    issued = now or datetime.now(tz=UTC)
    expires = issued + timedelta(seconds=settings.qr_token_ttl_seconds)   # NEW setting ~60
    payload = {
        "sub": str(client_id),
        "aud": "qr",            # distinct from client "aud": "client" — D-70-08
        "typ": "qr_checkin",    # distinct from "access" — D-70-08
        "iat": int(issued.timestamp()),
        "exp": int(expires.timestamp()),
    }
    return jwt.encode(payload, settings.secret_key.get_secret_value(), algorithm="HS256")
```

**Decode pattern to mirror** (`security.py:343-388`) — assert BOTH `typ=="qr_checkin"` and `aud=="qr"`:
```python
options={"require": ["sub", "aud", "typ", "iat", "exp"], "verify_aud": False}
# ... ExpiredSignatureError -> "token_expired"; InvalidTokenError -> "invalid_token"
if payload.get("typ") != "qr_checkin": raise InvalidAccessToken("wrong_token_type")
if payload.get("aud") != "qr":         raise InvalidAccessToken("wrong_audience")
```
`leeway=settings.jwt_clock_leeway_seconds`. A leaked QR token fails `require_client()` (wrong aud/typ); an access token fails at `/client/check-in` (wrong typ). Add a frozen `QrTokenClaims` dataclass mirroring `ClientAccessTokenClaims` (`:300-313`). New setting `qr_token_ttl_seconds: int = 60` in `app/core/config.py` (sibling of `access_token_ttl_seconds`, `config.py:64`).

---

### `app/core/dependencies.py` — booking-write Protocol slot (D-20-MODULE)

**Analog:** the side-effect-only `BookingCompleterCallable` slot (`dependencies.py:586-616`) and `BookingSlotRestorerCallable` (`:514-564`). For a value-returning write, use the value-returning resolver shape of `ActivePtPackageResolver` (`:163-198`).

**Slot declaration pattern to mirror** (combine `:586-616` shape with a return type):
```python
BookingForClientCreator = Callable[..., Awaitable[BookingResponse]]   # or a Protocol-return
_booking_for_client_creator: BookingForClientCreator | None = None

def register_booking_for_client_creator(creator: BookingForClientCreator) -> None:
    global _booking_for_client_creator
    _booking_for_client_creator = creator   # idempotent re-register (WR-05)

async def create_booking_for_client(session, *, client_id, slot_id, pt_package_id) -> BookingResponse:
    if _booking_for_client_creator is None:
        ...  # defensive-raise (booking write MUST be wired) OR silent — planner decides
    return await _booking_for_client_creator(session, ...)
```
Wire it in `app/main.create_app()` next to the existing booking slot registrations (`main.py:562-569` registers `register_slot_by_id_resolver` / `register_booking_slot_restorer` / `register_booking_completer`). **Zero new `ignore_imports`** — `client_portal` imports only `app.core.dependencies`, never `app.modules.bookings`. Same pattern for the visit-QR check-in write if `client_portal` calls the visits wrapper (or the check-in handler can live where the visits import is already legal — planner decides, but D-20-MODULE forbids `client_portal → visits` direct imports).

---

### `bookings/constants.py` — `CANCEL_WINDOW_HOURS_CLIENT` (D-70-05)

**Analog:** `CANCEL_WINDOW_HOURS_RECEPTION = 24` (`constants.py:41`).
```python
# Phase 70 D-70-05 — client cancel window, measured against slot.start_time
# (D-38-16, NOT created_at). Independently tunable from the reception window;
# starts identical (24h) for predictable behavior.
CANCEL_WINDOW_HOURS_CLIENT = 24
```
Add to `__all__` (`constants.py:43-46`).

---

### `visits/service.py` — client-QR check-in wrapper (D-70-11)

**Analog:** `create_visit_self_checkin` (`visits/service.py:233-262`).

**Wrapper shape to mirror** (`:256-262`):
```python
async def create_visit_client_qr(session, client_id: UUID) -> VisitResponse:
    visit_response, _end_date = await _create_visit_with_anti_fraud(
        session,
        client_id=client_id,        # strictly from verified QR sub claim (D-70-10)
        channel="client_qr",        # NEW channel — migration extends ck_visits_channel
        checked_in_by=None,         # self-service nullable (D-40-05; mirrors telegram_bot)
        audit_actor_user_id=None,
    )
    return visit_response
```
`_create_visit_with_anti_fraud` (`:106-212`) is unchanged — it already enforces gym-hours → active-membership → daily-UNIQUE (`uq_visits_client_id_gym_date`). A same-day replay collapses to `DuplicateCheckinError("duplicate_checkin")` via `_is_duplicate_visit_conflict` (`:66-77`) — this is the criterion-#5 replay guard. No new gating logic — single source of truth (D-70-09).

---

### `alembic/versions/0045_*.py` — extend `ck_visits_channel` CHECK (D-70-11)

**Analog:** the original CHECK creation `0006_visits.py:77-80`:
```python
sa.CheckConstraint("channel IN ('reception', 'telegram_bot')", name=op.f("ck_visits_channel"))
```
This is a CHECK *modification*, not a table create — Postgres requires drop + recreate (no ALTER CONSTRAINT for CHECK expressions):
```python
def upgrade() -> None:
    op.drop_constraint("ck_visits_channel", "visits", type_="check")
    op.create_check_constraint(
        "ck_visits_channel", "visits",
        "channel IN ('reception', 'telegram_bot', 'client_qr')",
    )
def downgrade() -> None:  # reverse — drop + recreate the 2-value CHECK
    ...
```
`down_revision = "0044_client_refresh_token"` (current head, `alembic/versions/` tail). **Also update the ORM** `__table_args__` CheckConstraint in `visits/models.py:96-101` (the `name="channel"` → expands to `ck_visits_channel` via NAMING_CONVENTION) to keep the model and migration in sync. Constraint name stays `ck_visits_channel` (discoverable by `_is_duplicate_visit_conflict`'s sibling discipline — though the duplicate guard is on the UNIQUE, not the CHECK).

---

### Tests — concurrency race, IDOR 404-collapse, QR replay/cross-client

**Concurrency race (criterion #1)** — analog `bookings/test_booking_race.py`:
- Use the `db_session_real_commit` fixture (`test_booking_race.py:54-101`), NOT the SAVEPOINT `db_session` — SAVEPOINT masks the partial-UNIQUE serialization. Copy the fixture verbatim (it TRUNCATEs the seeded tables on teardown since real commits aren't rolled back).
- 2 parallel `POST` with **DISTINCT** Idempotency-Keys (`:221-238`) so the race surfaces at the DB partial UNIQUE, not the Redis cache.
- Assert `statuses == [201, 409]` and the 409 `code == "slot_already_booked"` (`:241-251`); DB invariant: exactly 1 confirmed booking + slot `status='booked'` + exactly 1 `booking_created` audit row (`:253-281`).

**IDOR 404-collapse (criterion #3)** — analog `client_portal/test_idor_sweep.py`:
- SAVEPOINT `db_session` + ASGITransport `async_client` from root `conftest.py:57-140`.
- Auth-as-client helper `_auth_as_client` (`test_idor_sweep.py:36-60`) — OTP request → read+replace OtpCode hash → verify → return `cc_client_access`. Reuse verbatim.
- Client A cancels client B's booking → assert 404 `booking_not_found` (anti-oracle), never 403/leaked existence.

**QR replay / cross-client (criterion #5)** — same SAVEPOINT/ASGITransport harness:
- Expired-token replay: mint a QR token with `now=` in the past (the `now` injectability mirrors `encode_client_token`'s `now` param, `security.py:319`) → `/client/check-in` → assert 401 `token_expired`.
- Same-day double check-in: two scans → second collapses to `duplicate_checkin` via `uq_visits_client_id_gym_date`.
- Cross-client: token's `sub` is the only client source — assert there is structurally no body/path param to target another client (negative test: presenting client B's token under client A's session still checks in client B).

---

## Shared Patterns

### Composition-root Protocol-slot writes (D-20-MODULE) — applies to client_portal write paths
**Source:** `app/core/dependencies.py:514-616` (`register_booking_slot_restorer`, `register_booking_completer`); wiring at `app/main.py:562-569`.
`client_portal` reaches `bookings`/`visits` writes ONLY through a `register_*` slot + accessor in `app.core.dependencies`, wired once in `create_app()`. Zero direct `from app.modules.bookings`/`from app.modules.visits` imports → zero new `ignore_imports`. The read side already proves the discipline (raw-SQL `text()` cross-module reads, `client_portal/repository.py:6-16`).

### Token `aud`/`typ` isolation (Phase 68) — applies to QR token
**Source:** `decode_client_token` (`security.py:377-380`) asserts `typ=="access"` + `aud=="client"`.
QR token uses `typ="qr_checkin"`, `aud="qr"` — non-interchangeable with access/refresh. Decode asserts both; isolation is structural (a leaked QR token fails `require_client()`; an access token fails at `/client/check-in`).

### Audit emit with literal strings + nullable actor (INFRA-11 / D-40-05) — applies to booking + visit writes
**Source:** `create_booking_via_bot` audit branch (`service.py` mirrors `:1063-1090` with `actor_role="telegram_bot"`, `actor_user_id=None`); `_create_visit_with_anti_fraud` (`visits/service.py:201-210`, `audit_actor_user_id=None`).
Event name + `resource_type` are string LITERALS (AST gate). `actor_user_id` is `UUID | None` (pass `None` for client/self-service); UUIDs stringified into the JSONB payload at the callsite (Pitfall 13). Open question (Claude's Discretion): whether `audit.emit` needs a client-aware actor field — investigate `app/core/audit.py`; do NOT invent a fake staff user.

### Idempotency at router layer (D-70-02) — applies to booking POST + cancel
**Source:** `bookings/router.py:117-128, 185-196` — `Depends(verify_idempotency)` + `incoming_body = await request.body()` + `idempotent_execute(redis, key, body, runner=_runner)`. The `_runner` calls the service then JSON-encodes `envelope(result)` with `by_alias=True`, `separators=(",",":")`, `ensure_ascii=False`.

### Self-service nullable attribution (D-40-05) — applies to booking + visit client writes
**Source:** `create_booking_via_bot` (`created_by_user_id=None`); `create_visit_self_checkin` (`checked_in_by=None`, `visits/service.py:260`). Both columns are already nullable. Client booking → `created_by_user_id=None`; client QR visit → `checked_in_by=None`. Audit records the client as the conceptual actor.

### RBAC-04 dependency ordering — applies to all client write endpoints
**Source:** `bookings/router.py:79-86` (auth/principal → CSRF → idempotency → get_db); client variant in `client_portal/router.py` uses `require_client()` + `verify_client_csrf` (`dependencies.py:1254`). The `/client/check-in` endpoint is the deliberate exception: NO `require_client()` (token-as-credential).

---

## No Analog Found

None. Every surface in this phase has a direct in-repo analog — the phase is exposure/binding of existing machinery, not greenfield. The only genuinely new artifacts are the `qr_token_ttl_seconds` setting (sibling of existing TTL settings) and the `'client_qr'` channel literal (additive to an existing CHECK).

## Metadata

**Analog search scope:** `apps/backend/app/modules/{bookings,visits,client_portal}/`, `apps/backend/app/core/{security,dependencies,config}.py`, `apps/backend/app/main.py`, `apps/backend/app/api/v1/router.py`, `apps/backend/alembic/versions/`, `apps/backend/tests/{conftest.py,integration/bookings,integration/client_portal}/`.
**Files scanned:** ~16 (read targeted ranges; bookings/service.py is ~1400 lines — read via non-overlapping offset windows).
**Pattern extraction date:** 2026-05-30
