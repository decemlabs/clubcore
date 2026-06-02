---
phase: 70-client-bookings-qr-self-check-in
reviewed: 2026-05-30T12:00:00Z
depth: standard
files_reviewed: 16
files_reviewed_list:
  - apps/backend/app/core/security.py
  - apps/backend/app/core/config.py
  - apps/backend/app/core/dependencies.py
  - apps/backend/app/core/audit_payloads.py
  - apps/backend/app/core/exceptions.py
  - apps/backend/app/core/idempotency.py
  - apps/backend/app/main.py
  - apps/backend/app/modules/bookings/service.py
  - apps/backend/app/modules/bookings/constants.py
  - apps/backend/app/modules/client_portal/repository.py
  - apps/backend/app/modules/client_portal/router.py
  - apps/backend/app/modules/client_portal/schemas.py
  - apps/backend/app/modules/client_portal/service.py
  - apps/backend/app/modules/visits/models.py
  - apps/backend/app/modules/visits/service.py
  - apps/backend/alembic/versions/0045_visits_channel_client_qr.py
findings:
  critical: 3
  warning: 5
  info: 2
  total: 10
status: issues_found
---

# Phase 70: Code Review Report

**Reviewed:** 2026-05-30T12:00:00Z
**Depth:** standard
**Files Reviewed:** 16
**Status:** issues_found

## Summary

Phase 70 adds client self-booking (CBOOK-01..05) and QR self check-in (CCHK-01..03) on top of the Phase 68/69 client auth foundation. The architecture is structurally sound: Protocol-slot discipline is intact, IDOR 404-collapse is correctly implemented, and the QR token isolation (`aud='qr'`/`typ='qr_checkin'`) is solid. However, three blockers were found:

1. The rate-limit implementation has a TOCTOU race that allows every IP to exceed the configured limit by up to the concurrency factor before being blocked.
2. A single shared Redis bucket (`ratelimit:check_in:ip:unknown`) rate-limits ALL requests arriving through proxies without the `X-Forwarded-For` header, enabling a trivially easy bypass.
3. `verify_client_idempotency` is missing from `idempotency.__all__`, breaking any future wildcard import and violating the module's own export contract.

Additionally, five warnings were found ranging from a misleading HTTP status documented in the router summary, to an open-ended cast that silently skips UUID parse errors in `check_in_via_qr`.

---

## Critical Issues

### CR-01: Rate-limit TOCTOU race allows limit bypass

**File:** `apps/backend/app/modules/client_portal/router.py:91-97` and `:107-113`

**Issue:** Both `_enforce_qr_token_rate_limit` and `_enforce_check_in_rate_limit` use a read-then-write (GET → pipeline INCR+EXPIRE) pattern that is not atomic. The GET and the INCR are separate Redis operations with no lock between them. Under concurrent load, N simultaneous requests all read the same counter value below the limit, all pass the guard, and then all INCR. The limit can be exceeded by a factor equal to the number of concurrent requests. This is a meaningful bypass on the unauthenticated `/client/check-in` endpoint, which is the exact endpoint the rate limit is designed to protect against brute-force QR scanning.

**Fix:** Replace the GET+INCR pattern with an atomic INCR-first approach:

```python
async def _enforce_qr_token_rate_limit(redis: Redis, ip: str) -> None:
    key = _qr_token_rate_key(ip)
    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.expire(key, _QR_TOKEN_IP_WINDOW, xx=False)  # only set if not exists
    results = await pipe.execute()
    count = results[0]
    if count > _QR_TOKEN_IP_LIMIT:
        raise RateLimited("rate_limited")
```

The INCR is atomic — it both increments and returns the new value. EXPIRE with `xx=False` (only set TTL if the key does not already have one) keeps the window correct. This is the same pattern used in `app/modules/auth/reset_rate_limit.py` that this code is supposed to mirror.

---

### CR-02: Shared rate-limit key `"unknown"` for proxy-less requests — effective bypass

**File:** `apps/backend/app/modules/client_portal/router.py:487` and `:532`

**Issue:**

```python
ip = request.client.host if request.client is not None else "unknown"
```

When `request.client` is `None` (which occurs behind some reverse proxies that strip the peer address, or in certain ASGI middleware configurations), every request — from any actual source IP — falls into a single shared bucket keyed `ratelimit:check_in:ip:unknown`. This means:

- **Denial of service:** A single attacker triggering the 60/min limit blocks all other clients also hitting this fallback.
- **Bypass:** If the proxy does not strip the address, the attacker uses a realistic address. If it does strip it, all legitimate clients share one bucket and will hit the limit before attackers who use direct connections.

For the unauthenticated `/client/check-in` endpoint this is a security control gap: a scanner farm behind a proxy that strips addresses faces no effective limit per scanner.

**Fix:** Either trust the `X-Forwarded-For` / `X-Real-IP` header when `request.client` is None (with appropriate proxy trust configuration), or fail-closed and reject the request outright when the peer address cannot be determined:

```python
ip = request.client.host if request.client is not None else None
if ip is None:
    # Cannot rate-limit without an IP. For the unauthenticated check-in
    # endpoint, fail-closed. For the authenticated qr-token endpoint,
    # client auth already provides a different abuse surface.
    raise RateLimited("rate_limited")
```

---

### CR-03: `verify_client_idempotency` missing from `idempotency.__all__`

**File:** `apps/backend/app/core/idempotency.py:377-389`

**Issue:** `verify_client_idempotency` (added at line 112 in the same file for Phase 70) is not listed in `__all__`. The module is already imported via explicit named import in `router.py` (`from app.core.idempotency import ... verify_client_idempotency`), so the immediate runtime is not broken. However:

1. The module's own `__all__` is now internally inconsistent — it documents the public API but silently omits a Phase 70 public entry point.
2. Any downstream consumer using `from app.core.idempotency import *` (e.g., test helpers, future codegen) will not get `verify_client_idempotency`, creating a silent import-time `NameError` only discoverable at call time.
3. The project's AST gate and import-linter checks operate on the declared surface; an undeclared export is invisible to those gates.

**Fix:**

```python
__all__ = (
    "IDEMPOTENCY_KEY_PATTERN",
    "IDEMPOTENCY_REDIS_PREFIX",
    "IDEMPOTENCY_TTL_SECONDS",
    "IdempotencyEnvelope",
    "begin_idempotency",
    "body_sha256",
    "idempotent_execute",
    "idempotent_response",
    "load_idempotency_response",
    "store_idempotency_response",
    "verify_client_idempotency",   # Phase 70 addition
    "verify_idempotency",
)
```

---

## Warnings

### WR-01: Router summary documents wrong HTTP status for `cancel_window_expired`

**File:** `apps/backend/app/modules/client_portal/router.py:389`

**Issue:** The `client_cancel_booking` endpoint's `summary` string reads:

```python
"422 cancel_window_expired if outside client cancel window"
```

But `CancelWindowExpiredError` (defined at `bookings/service.py:190-203`) is a `ConflictError` with `status_code = 409`. The actual HTTP response code for this error is **409**, not 422. The docstring at line 307 in `service.py` also writes `→ 422 cancel_window_expired`. The OpenAPI spec, any generated client, and integration tests derived from these strings will assert the wrong status code.

**Fix:** Change both occurrences to `409`:

```python
# router.py:389
"409 cancel_window_expired if inside client cancel window"

# service.py:307
# BookingNotFoundError → 404; CancelWindowExpiredError → 409 cancel_window_expired
```

---

### WR-02: `check_in_via_qr` silently treats UUID parse failure as a valid client_id

**File:** `apps/backend/app/modules/client_portal/service.py:371`

**Issue:**

```python
claims = decode_qr_token(token)
client_id = UUID(claims.sub)  # sole authoritative source (D-70-10)
```

`UUID(claims.sub)` raises `ValueError` if `claims.sub` is not a valid UUID string (e.g., a malformed token that passes signature verification but has a bad `sub`). This exception is not caught here and will bubble up as an unhandled `ValueError` rather than the expected `InvalidSession` (401) or `InvalidAccessToken` error. The global `_app_error_handler` only handles `AppError` subclasses; an unhandled `ValueError` from FastAPI's ASGI layer becomes a 500 Internal Server Error, leaking stack traces in non-production environments.

**Fix:** Mirror the same `try/except` pattern used in `get_current_client` (`dependencies.py:1223-1226`):

```python
claims = decode_qr_token(token)
try:
    client_id = UUID(claims.sub)
except ValueError as exc:
    from app.core.exceptions import InvalidSession
    raise InvalidSession("invalid_session") from exc
```

---

### WR-03: `slot.status` refresh after failed predicate-gated UPDATE may use stale ORM cache

**File:** `apps/backend/app/modules/bookings/service.py:1341-1344`

**Issue:** When `update_slot_status_predicate_gated` returns `False` (meaning the UPDATE matched 0 rows), the code does:

```python
await session.refresh(slot, attribute_names=["status"])
if slot.status == "booked":
    raise SlotAlreadyBookedError("slot_already_booked")
raise SlotNotAvailableError("slot_not_available")
```

`slot` here is the `SlotById` Protocol object returned by `resolve_slot_by_id`, which is a `TrainerAvailabilitySlot` ORM instance held in the session identity map. The `session.refresh(slot, ...)` call refreshes the slot from DB. However, this path is executed AFTER the predicate-gated raw SQL UPDATE was already issued but returned 0 rows — meaning the DB state has already changed away from 'active'. If the slot was concurrently booked by another request, the refreshed status will be 'booked'. The discriminator logic is correct.

The subtler issue is that `resolve_slot_by_id` is a Protocol slot that returns `SlotById | None`, typed as the Protocol not the ORM concrete class. `session.refresh()` requires a mapped ORM instance, not an arbitrary protocol-satisfying object. If the Protocol slot were ever implemented to return a non-ORM DTO (currently it returns the SA ORM row), `session.refresh(slot, ...)` would raise `InvalidRequestError: Object 'SlotById' is not mapped`. The code relies on an undocumented implementation-specific property of the resolver.

**Fix:** Add an `isinstance` guard or cast-and-comment making the ORM dependency explicit, or use a direct repository re-fetch:

```python
if not slot_flipped:
    # Re-read from DB bypassing identity map to get current slot status.
    refreshed = await resolve_slot_by_id(session, slot_id)
    if refreshed is not None and refreshed.status == "booked":
        raise SlotAlreadyBookedError("slot_already_booked")
    raise SlotNotAvailableError("slot_not_available")
```

This is a latent breakage risk rather than an immediate bug (the current resolver returns ORM rows), hence Warning not Critical.

---

### WR-04: `BookingCancelledPayload` audit emit documents wrong behaviour for `CancelWindowExpiredError` — `actor_role` missing from `booking_cancelled` payload

**File:** `apps/backend/app/modules/bookings/service.py:1629-1638` and `apps/backend/app/core/audit_payloads.py:453-475`

**Issue:** `create_booking_for_client` emits `booking_created` with `actor_role="client"` (correct, since `BookingCreatedPayload` includes the `actor_role` field). However, `cancel_booking_for_client` emits `booking_cancelled` with only `(booking_id, slot_id, cancelled_by_user_id=None, cancel_reason)`. The `BookingCancelledPayload` schema does NOT have an `actor_role` field — this is intentional per the existing 4-key schema (`extra='forbid'`). 

But this creates an audit asymmetry: the forensic record for a client-initiated cancel cannot be distinguished from a staff cancel (which also sets `cancelled_by_user_id=None` when... actually staff always provides a UUID). In practice the `NULL` `cancelled_by_user_id` is the implicit discriminator, but this is undocumented and fragile: if future staff flows also produce `cancelled_by_user_id=None` (e.g., a system-initiated cancel), the two paths become indistinguishable in the audit log.

**Fix:** Extend `BookingCancelledPayload` (additive, back-compat) with an optional `actor_role` field like `BookingCreatedPayload`, and emit it at the `cancel_booking_for_client` callsite:

```python
# audit_payloads.py — additive widening:
actor_role: Literal["reception", "owner", "telegram_bot", "client"] = "reception"

# cancel_booking_for_client emit:
actor_role="client",  # discriminator matching create path
```

This is a Warning because it does not cause incorrect behavior today, only forensic ambiguity.

---

### WR-05: `fetch_available_slots` count query includes unbound `:trainer_id` param when `trainer_id` is `None`

**File:** `apps/backend/app/modules/client_portal/repository.py:93-111`

**Issue:** When `trainer_id is None`, `trainer_filter` is `""` (empty string) and `count_bind` is `{"trainer_id": None}`. The `count_sql` string then does NOT contain `:trainer_id` — but `count_bind` still passes `trainer_id: None` to `session.execute(text(count_sql), count_bind)`. SQLAlchemy's `text()` with asyncpg silently ignores unused bind parameters. This is benign today, but:

1. It adds noise to the bind parameter dict, making the code harder to reason about.
2. If SQLAlchemy or asyncpg ever changes to strict mode (rejecting unused params), this becomes an error without any other code change.

The `list_sql` bind dict correctly includes `trainer_id` as it IS used in `_base_filter` when not None — but `count_sql` uses a separate `count_bind` that still includes `trainer_id: None` unnecessarily.

**Fix:** Only include `trainer_id` in `count_bind` when `trainer_filter` is non-empty:

```python
count_bind: dict[str, object] = {}
if trainer_id is not None:
    count_bind["trainer_id"] = str(trainer_id)
```

---

## Info

### IN-01: `check_in_via_qr` decodes the token but does not validate that the client still exists in the DB

**File:** `apps/backend/app/modules/client_portal/service.py:370-373`

**Issue:** `check_in_via_qr` calls `decode_qr_token(token)` (signature + exp + claims verified) and passes `client_id` from `sub` directly to `create_visit_client_qr`. There is no live-client existence check between token decode and visit creation. If a client is soft-deleted after minting a QR token, the `_create_visit_with_anti_fraud` path will attempt to INSERT a visit with a `client_id` FK that now points to a soft-deleted (but still physically present) row.

This does NOT cause an integrity violation because the FK is `ON DELETE RESTRICT` and soft-delete keeps the row. The visit will be created for a soft-deleted client — which may be intentional given the 60s TTL and the difficulty of a race this tight. However, it is an undocumented edge case: the gym scanner will get a successful check-in response for a client who has just been deactivated.

This is acceptable given the 60s TTL and architectural decision D-70-09 (gate at scan only via `_create_visit_with_anti_fraud`). Noting for awareness — the anti-fraud chain does not have a "client alive" check.

**Fix (optional):** Add a client-alive check in `create_visit_client_qr` by verifying the client via the `_client_loader` slot before the anti-fraud chain, if this edge case is deemed important.

---

### IN-02: `client_cancel_booking` has no Idempotency-Key on the cancel endpoint

**File:** `apps/backend/app/modules/client_portal/router.py:381-416`

**Issue:** The `client_cancel_booking` endpoint (POST `/client/booking/{booking_id}/cancel`) does not have an `Idempotency-Key` requirement, while the staff equivalent (`cancel_booking`) appears in `CATEGORY_A_OPERATION_IDS` (`main.py:266`). A cancel request submitted twice (network retry on timeout) could theoretically try to cancel an already-cancelled booking, which the FSM guard (`_assert_can_transition`) will reject with `InvalidBookingTransitionError` (409 `invalid_transition`) rather than a meaningful response.

This is by design per D-70-02 (idempotency only for booking creation) and the FSM guard provides functional safety. The duplicate cancel produces a 409 which the PWA must handle. The risk is UX-level, not correctness-level, since the cancelled state is terminal and idempotent at the DB level. Flagging as Info since D-70-02 explicitly scoped idempotency to booking creation only.

**Fix (optional):** Add `Depends(verify_client_idempotency)` to the cancel endpoint if the PWA requires idempotent retry semantics for cancel operations. If omitted, the PWA retry logic must handle 409 `invalid_transition` on duplicate cancel as an implicit success (booking is already cancelled).

---

_Reviewed: 2026-05-30T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
