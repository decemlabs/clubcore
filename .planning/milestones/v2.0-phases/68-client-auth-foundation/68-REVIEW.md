---
phase: 68-client-auth-foundation
reviewed: 2026-05-29T12:00:00Z
depth: standard
files_reviewed: 23
files_reviewed_list:
  - apps/backend/alembic/env.py
  - apps/backend/alembic/versions/0043_client_auth_otp.py
  - apps/backend/alembic/versions/0044_client_refresh_token.py
  - apps/backend/app/api/v1/router.py
  - apps/backend/app/core/audit.py
  - apps/backend/app/core/dependencies.py
  - apps/backend/app/core/security.py
  - apps/backend/app/main.py
  - apps/backend/app/modules/auth/models.py
  - apps/backend/app/modules/client_auth/__init__.py
  - apps/backend/app/modules/client_auth/models.py
  - apps/backend/app/modules/client_auth/rate_limit.py
  - apps/backend/app/modules/client_auth/router.py
  - apps/backend/app/modules/client_auth/schemas.py
  - apps/backend/app/modules/client_auth/service.py
  - apps/backend/app/modules/clients/service.py
  - apps/backend/tests/integration/client_auth/conftest.py
  - apps/backend/tests/integration/client_auth/test_byte_parity.py
  - apps/backend/tests/integration/client_auth/test_idor.py
  - apps/backend/tests/integration/client_auth/test_otp_isolation.py
  - apps/backend/tests/integration/client_auth/test_session_lifecycle.py
  - apps/backend/tests/integration/test_route_introspection.py
  - apps/backend/.importlinter
findings:
  critical: 2
  warning: 4
  info: 2
  total: 8
status: issues_found
---

# Phase 68: Code Review Report

**Reviewed:** 2026-05-29T12:00:00Z
**Depth:** standard
**Files Reviewed:** 23
**Status:** issues_found

## Summary

Phase 68 delivers the client-auth foundation: a phone+OTP session stack that is structurally isolated from the staff auth stack. The principal separation (separate cookies, separate JWT audience claim, separate DB table, separate Redis namespace, no `Role.CLIENT`) is well-executed. The byte-parity test, IDOR sweep, anti-oracle body-parity check, and full session lifecycle test are all well-scoped.

Two critical defects are present. First, `ClientMePatchRequest.email` accepts any string — `EmailStr` validation present on the staff `ClientCreateRequest`/`ClientUpdateRequest` was not carried over, so arbitrary non-email strings are silently stored. Second, `OtpExpired` (HTTP 410) is raised from `verify_client_otp` when an OTP row is found but stale, while `InvalidAccessToken` (HTTP 401) is raised when no OTP row exists — creating a status-code oracle that allows phone enumeration via the verify endpoint.

Four warnings and two info items round out the findings. None of the core CISO isolation contracts (CISO-01 through CISO-05) are violated.

---

## Critical Issues

### CR-01: `ClientMePatchRequest.email` accepts arbitrary strings — no format validation

**File:** `apps/backend/app/modules/client_auth/schemas.py:63`

**Issue:** `email: str | None = None` stores any string in the `clients.email` column without validating it as an email address. The staff-side schemas (`ClientCreateRequest` line 112, `ClientUpdateRequest` line 144 in `clients/schemas.py`) both use `EmailStr | None`, which runs Pydantic's RFC 5321 validation. The client self-edit path skips this validation entirely. A client can PATCH `/client/me` with `{"email": "notanemail"}` or `{"email": "x@"}` and it will be committed to the DB, potentially breaking downstream receipts, notification delivery, or future integrations that trust the stored value.

The partial unique index `ix_clients_email_lower_unique` enforces uniqueness but not format. No DB-level CHECK constraint enforces email syntax.

**Fix:**
```python
# schemas.py
from pydantic import EmailStr

class ClientMePatchRequest(BackendSchemaBase):
    """PATCH /client/me — email-only self-edit (D-04)."""
    email: EmailStr | None = None
```

---

### CR-02: `verify_client_otp` leaks phone enumeration via different status codes for expired vs missing OTP

**File:** `apps/backend/app/modules/client_auth/service.py:293-295`

**Issue:** When an OTP row is found but its `expires_at < now`, the function raises `OtpExpired` which maps to HTTP **410**. When no OTP row exists (or no client exists), it raises `InvalidAccessToken` which maps to HTTP **401**. An attacker probing `/api/v1/client/otp/verify` can distinguish these two states:

- HTTP 401 → the phone has no active (unconsumed) OTP row.
- HTTP 410 → the phone has a recently-expired OTP row, which means a legitimate OTP was requested and not yet consumed for that phone within the last ~5 minutes.

This status-code oracle enables phone enumeration via the verify endpoint. The anti-oracle guarantee on the *request* endpoint (always 202) is not extended to the *verify* endpoint, but different status codes on verify still reveal phone registration state.

**Fix:** Replace `OtpExpired` with `InvalidAccessToken("invalid_session")` in the expired-OTP branch so both "no row" and "expired row" return the same 401 status code and body:

```python
# service.py — verify_client_otp, line 294-295
if otp_row.expires_at < now:
    raise InvalidAccessToken("invalid_session")  # was: OtpExpired("otp_expired")
```

The `OtpExpired` (410) exception is appropriate for the *staff* OTP flow where the client already authenticated and a specific 410 helps the UI prompt a re-request. For the pre-auth client OTP flow, a distinct expiry status code leaks information.

---

## Warnings

### WR-01: Rate-limit EXPIRE resets the sliding window on every bump — `_DAILY_LIMIT` window anchors to last request, not first

**File:** `apps/backend/app/modules/client_auth/rate_limit.py:106-110`

**Issue:** `bump_client_otp_daily` issues `INCR` then `EXPIRE` unconditionally in a pipeline. When the key already exists, `EXPIRE` resets its TTL from the current moment rather than preserving the original anchor. The "24h" window therefore starts from the 5th request, not the 1st. A client sending OTPs at `t=0, t=60, t=120, t=180, t=240` (5 requests, one per cooldown interval) will not be able to request again until `t=240+86400=86640` rather than `t=86400`. More importantly, the window can be *extended* by the attacker: if an attacker triggers requests on a victim phone's behalf (D-02 silent no-op means this doesn't send a DM, but it still consumes quota), they can push out the reset window indefinitely, effectively locking the phone from OTP receipt.

The same pattern exists in the staff login rate limiter so this is consistent, but the staff limiter is per-failed-login (not per-successful-send), which limits exploitability. The daily OTP limiter is per-successful-send, making it more sensitive.

**Fix:** Use `EXPIRE key ttl NX` (set TTL only if the key has no TTL) to anchor the window to the first request:

```python
async def bump_client_otp_daily(redis: Redis, phone: str) -> None:
    """INCR per-phone daily counter; EXPIRE only on first hit (fixed window anchor)."""
    pipe = redis.pipeline()
    pipe.incr(_daily_key(phone))
    pipe.expire(_daily_key(phone), _DAILY_WINDOW, nx=True)  # nx=True: set only if no TTL
    await pipe.execute()
```

Apply the same fix to `bump_client_ip_rate` for consistency.

---

### WR-02: `verify_client_otp` has no constant-time floor — timing oracle reveals phone/OTP existence

**File:** `apps/backend/app/modules/client_auth/service.py:256-347`

**Issue:** `request_client_otp` correctly applies `_constant_time_floor` via `try/finally` to equalise response timing across all phone states. `verify_client_otp` has no equivalent floor. An attacker submitting codes against different phone numbers will observe different wall-clock response times:

- Unknown phone: one DB query (Client lookup) → very fast 401.
- Known phone but no active OTP: two DB queries (Client + OtpCode) → slightly slower 401.
- Known phone with active OTP but wrong code: two DB queries + commit → even slower 401/429.

This allows timing-based phone enumeration via the verify endpoint, partially undermining the anti-oracle on the request endpoint.

**Fix:**
```python
async def verify_client_otp(
    session: AsyncSession,
    redis: Redis,
    phone: str,
    code: str,
) -> tuple[str, str, str]:
    t_start = time.perf_counter()
    try:
        # ... existing logic ...
        return access, raw_refresh, csrf
    finally:
        await _constant_time_floor(t_start)
```

---

### WR-03: `OtpMaxAttempts` does not invalidate the OTP — correct code succeeds after max attempts

**File:** `apps/backend/app/modules/client_auth/service.py:297-307`

**Issue:** In `verify_client_otp`, the brute-force check evaluates `attempts` only inside the `if presented_hash != otp_row.code_hash:` branch. When the presented hash *matches* (correct code), the function skips the attempts check entirely and grants the session. This means that after `otp_max_attempts` wrong guesses (all returning 429/`otp_max_attempts`), a correct code submitted on the next attempt will still succeed.

The same pattern exists in `auth/telegram_service.py:consume()` (staff flow), so this appears to be a consistent design choice rather than an accidental omission. The practical security impact is limited given the 1,000,000 code space and the 5-codes-per-24h daily cap. However, the intent of `OtpMaxAttempts` is to signal that the code is exhausted — the UX messaging ("too many attempts, request a new code") and the actual behavior (correct code still works) are contradictory.

**Fix:** Add a pre-check for max attempts at the top of the hash comparison block so the OTP is fully locked once the limit is reached:

```python
# Add before the hash comparison (line 297)
if otp_row.attempts >= settings.otp_max_attempts:
    raise OtpMaxAttempts("otp_max_attempts")

presented_hash = _sha256_hex(code)
if presented_hash != otp_row.code_hash:
    otp_row.attempts += 1
    await session.commit()
    if otp_row.attempts >= settings.otp_max_attempts:
        raise OtpMaxAttempts("otp_max_attempts")
    remaining = settings.otp_max_attempts - otp_row.attempts
    raise OtpInvalid("otp_invalid", fields={"attemptsRemaining": remaining})
```

Note: this changes semantics such that OtpMaxAttempts now *locks* the OTP. If the intent is to avoid DoS (attacker burning 5 attempts to lock victim's OTP), the current behavior is arguably correct and the fix should instead be to clarify in comments and align the UX messaging.

---

### WR-04: Redundant `try/except ConflictError: raise` in `patch_client_me` router handler

**File:** `apps/backend/app/modules/client_auth/router.py:204-207`

**Issue:** The `patch_client_me` handler wraps the service call in `try: ... except ConflictError: raise`. This catches `ConflictError` only to immediately re-raise it — the `ConflictError` would propagate naturally without the `try/except` block. The pattern implies a future intent to add additional handling (logging, transformation) that was never implemented, leaving dead control-flow overhead.

```python
# Current (redundant):
try:
    updated = await service.update_client_me(session, client.id, payload.email)
except ConflictError:
    raise
return envelope(ClientMeResponse.model_validate(updated, from_attributes=True))

# Fix (clean):
updated = await service.update_client_me(session, client.id, payload.email)
return envelope(ClientMeResponse.model_validate(updated, from_attributes=True))
```

---

## Info

### IN-01: `test_otp_brute_force_blocked` does not test correct-code submission after `OtpMaxAttempts`

**File:** `apps/backend/tests/integration/client_auth/test_session_lifecycle.py:258-321`

**Issue:** The brute force test verifies that the (max_attempts)'th wrong code returns 429/`otp_max_attempts` and that a subsequent wrong code also returns 429. It does not test that submitting the *correct* code after max_attempts returns the expected result. Given the design discussion in WR-03 above, an explicit test for this case would document the intended behaviour (pass or fail), preventing silent regression regardless of which direction the fix goes.

**Fix:** Add a parametrized case or an additional assertion at the end of `test_otp_brute_force_blocked`:

```python
# After the post-max wrong attempt assertion:
# Verify correct code still works (current behavior) OR fails (if locking is added)
correct_resp = await async_client.post(
    "/api/v1/client/otp/verify",
    json={"phone": linked_client.phone, "code": raw_code},
)
# Document which behavior is expected:
# assert correct_resp.status_code == 200  # if correct code should still work
# assert correct_resp.status_code == 429  # if OTP should be fully locked
```

---

### IN-02: `soft_deleted_client` fixture uses `telegram_user_id=None`, not a Telegram-linked deleted client

**File:** `apps/backend/tests/integration/client_auth/conftest.py:135-149`

**Issue:** The `soft_deleted_client` fixture creates a client with `deleted_at` set AND `telegram_user_id=None`. The anti-oracle test (`test_otp_request_anti_oracle`) uses this fixture as one of the four phone states. However, this fixture tests two conditions simultaneously: soft-deleted AND no Telegram link. A soft-deleted client who *was* Telegram-linked is a distinct case: the `deleted_at.is_(None)` filter in the service correctly blocks it, but the test fixture doesn't cover it. If the service filter were ever accidentally removed, the existing test would not catch the regression for a Telegram-linked soft-deleted client.

**Fix:** Change `soft_deleted_client` to have `telegram_user_id` set (a real Telegram id), ensuring the only distinguishing factor is `deleted_at`:

```python
@pytest_asyncio.fixture
async def soft_deleted_client(db_session: AsyncSession, seeded_staff: User) -> Client:
    """Soft-deleted Client with Telegram link — deleted_at IS NOT NULL gate tested."""
    client = Client(
        first_name="Deleted",
        last_name=f"Client{uuid4().hex[:6]}",
        phone=_SOFT_DELETED_PHONE,
        telegram_user_id=987_654_321,  # was None — now tests the deleted_at filter directly
        created_by_user_id=seeded_staff.id,
        deleted_at=datetime.now(tz=UTC),
    )
```

---

_Reviewed: 2026-05-29T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
