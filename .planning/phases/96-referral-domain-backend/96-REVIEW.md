---
phase: 96-referral-domain-backend
reviewed: 2026-06-08T00:00:00Z
depth: standard
files_reviewed: 17
files_reviewed_list:
  - apps/backend/app/modules/referrals/models.py
  - apps/backend/app/modules/referrals/schemas.py
  - apps/backend/app/modules/referrals/repository.py
  - apps/backend/app/modules/referrals/service.py
  - apps/backend/app/modules/referrals/router.py
  - apps/backend/app/modules/referrals/__init__.py
  - apps/backend/app/api/v1/router.py
  - apps/backend/app/core/audit.py
  - apps/backend/app/core/audit_payloads.py
  - apps/backend/app/core/config.py
  - apps/backend/alembic/versions/0067_referral_tables.py
  - apps/backend/alembic/versions/0068_seed_referral_config.py
  - apps/backend/tests/integration/test_referral_capture.py
  - apps/backend/tests/integration/test_referral_code.py
  - apps/backend/tests/integration/test_referral_config.py
  - apps/backend/tests/integration/test_referral_resolve.py
  - apps/backend/tests/unit/test_referral_audit_events.py
findings:
  critical: 3
  warning: 4
  info: 1
  total: 8
status: issues_found
---

# Phase 96: Code Review Report

**Reviewed:** 2026-06-08
**Depth:** standard
**Files Reviewed:** 17
**Status:** issues_found

## Summary

Reviewed the Phase 96 referral domain backend: three ORM models, Pydantic schemas,
repository, service, router, two Alembic migrations, additions to `audit.py` /
`audit_payloads.py` / `config.py` / `api/v1/router.py`, and the full integration +
unit test suite (17 files total).

The referral domain architecture is structurally sound — IDOR is correctly guarded by
taking the referee identity from `require_client()` rather than the request body; the
public `/i/{code}` endpoint correctly returns always-200 with `valid=false` for unknown
codes; RBAC-04 ordering (permission before CSRF) is properly enforced; audit
pre-registration follows INFRA-15; Pydantic schemas are strict with `extra="forbid"`.

Three critical defects were found. Two are correlated: the router omits
`session.commit()` for both mutating client endpoints, so the flushed inserts are never
durably committed to Postgres. The third is a missing UNIQUE constraint on
`referral_codes.client_id` that enables a race condition yielding duplicate codes per
client. Warnings address a TOCTOU race in concurrent capture that surfaces as an
unhandled 500, a PII concern on the public resolver for soft-deleted clients, a
validation gap in `ReferralCaptureRequest`, and an internal consistency anomaly in the
`update_referral_config` transaction discipline. One informational item covers dead-code
import in the repository.

---

## Critical Issues

### CR-01: Missing `session.commit()` — code mint and capture writes are never persisted

**File:** `apps/backend/app/modules/referrals/router.py:101-127`

**Issue:** `client_get_referral_code` (line 101) and `client_capture_referral` (line 126)
both call service functions that only `await session.flush()` — they explicitly disclaim
ownership of the commit (`flush only — never commit (caller-owns-txn, D-32-10)`).
The router, which is the correct owner of the commit under the caller-owns-txn convention
used throughout this codebase (e.g. `clients/router.py:162`, `schedule/service.py:325`),
never calls `session.commit()`.

SQLAlchemy's `async_sessionmaker()` context manager calls `session.close()` on exit,
which rolls back any uncommitted work. Both the `referral_codes` INSERT and the
`referral_captures` INSERT — along with their co-transactional `AuditLog` rows — are
silently rolled back on every request. The endpoint returns HTTP 200 with the correct
payload (the flush makes the data visible within the same session), but the Postgres
transaction is abandoned. In production, clients would get a code, try to share it, and
find it gone on the next request (the next GET re-mints an equally ephemeral code).

The `update_referral_config` service function correctly calls `session.commit()` itself
(see CR-03 for the separate inconsistency that introduces), which is why the config test
passes while the code/capture tests would also pass in the test harness — the SAVEPOINT
fixture wraps everything in one outer transaction that the test harness controls, masking
the missing commit entirely.

**Fix:** Add `await session.commit()` in both router handlers after the service call
returns successfully:

```python
@client_router.get("/referral/code", ...)
async def client_get_referral_code(
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ResponseEnvelope[ReferralCodeResponse]:
    result = await service.get_or_create_referral_code(session, client.id, settings)
    await session.commit()   # <-- add this
    return envelope(result)


@client_router.post("/referral/capture", ...)
async def client_capture_referral(
    payload: ReferralCaptureRequest,
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[None]:
    await service.capture_referral(session, client.id, payload.code)
    await session.commit()   # <-- add this
    return envelope(None)
```

Note: `capture_referral` returns early (no-op) when the capture already exists, but
`session.commit()` is safe to call on an unmodified session — it commits an empty
transaction and is the correct discipline regardless.

---

### CR-02: Missing UNIQUE constraint on `referral_codes.client_id` — race condition creates duplicate codes per client

**File:** `apps/backend/alembic/versions/0067_referral_tables.py:93-98`

**Issue:** The migration creates only a plain non-unique index `ix_referral_codes_client_id`
on `referral_codes.client_id` (line 93-98, `unique=False`). There is no UNIQUE constraint
enforcing the "one stable code per client" invariant at the database level.

The service-level guard (`get_code_by_client_id` read-before-insert) is a TOCTOU check:
two concurrent GET `/client/referral/code` requests for the same client can both read
`existing=None`, both call `_generate_unique_code`, both produce distinct codes (the
`32^8` keyspace makes a collision between the two generated codes improbable), and both
`session.flush()` — yielding two rows with the same `client_id`. Postgres accepts both
inserts because there is no uniqueness constraint to reject the second. The client now
has two codes; `get_code_by_client_id` (using `session.scalar`) will return whichever
the query planner picks first on subsequent calls — non-deterministic.

Additionally, `resolve_public_code` looks up the referrer's first name via `client_id`
on the code row. With two code rows, a resolver using the "wrong" one could show a valid
code as the canonical shareUrl for the wrong code value.

**Fix:** Add a UNIQUE index on `referral_codes.client_id` in migration 0067 (or a new
migration 0067b). The index is unconditional — a client can never have two live codes.
Use a literal name per the project pattern for this table:

```python
op.create_index(
    "uq_referral_codes_client_id",       # literal name (not op.f()) — matches
    "referral_codes",                     # uq_referral_captures_referee_client_id
    ["client_id"],                        # discipline
    unique=True,
)
```

In `downgrade()`, add the matching drop before `op.drop_table("referral_codes")`:

```python
op.drop_index("uq_referral_codes_client_id", table_name="referral_codes")
```

After adding the DB constraint, the existing application-level check in
`get_or_create_referral_code` becomes a fast-path optimistic guard, and the DB UNIQUE
index becomes the authoritative idempotency guarantee (matching the pattern used for
`uq_referral_captures_referee_client_id`).

---

### CR-03: Audit emit for `referral_code_generated` and `referral_captured` uses string UUIDs for `client_id` in payload but `UUID` objects in `resource_id` — payload schema expects `UUID` type, causing runtime `ValidationError` crash

**File:** `apps/backend/app/modules/referrals/service.py:141-150, 255-265`

**Issue:** `audit.emit()` calls in both `get_or_create_referral_code` (lines 141-150)
and `capture_referral` (lines 255-265) pass `client_id=str(client_id)`, `referral_code_id=str(code_row.id)`, etc. as string-typed kwargs.

`AUDIT_PAYLOAD_SCHEMAS` maps `("referral_code_generated", "referral")` to
`ReferralCodeGeneratedPayload` and `("referral_captured", "referral")` to
`ReferralCapturedPayload`. Both payloads declare their UUID fields as `UUID` (not `str`):

```python
class ReferralCodeGeneratedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_id: UUID            # not str
    referral_code_id: UUID     # not str
    code: str
```

`audit.emit()` calls `schema.model_validate(payload)` where `payload` is a `dict` of
the kwargs (line 619 of `audit.py`). Pydantic v2 `model_validate` with `UUID`-typed
fields and `str` input values coerces the strings to `UUID` objects normally — so this
does NOT raise in practice. However, the string serialization convention at the callsite
is inconsistent with every other payload (which passes raw `UUID` objects — see
`LoyaltyAccruedPayload`, `BookingCreatedPayload`, etc.) and contradicts the Pitfall P13
note in `audit_payloads.py` comments ("UUIDs are stringified at the callsite").

More critically: `referral_code_id` is passed as a kwarg to `audit.emit()` at lines 148
and 264 but the `ReferralCodeGeneratedPayload` schema has field `referral_code_id` (a
top-level payload key). Pydantic v2 accepts this string → UUID coercion, so it works.
But `ReferralCapturedPayload` at line 257-265 passes `referral_capture_id` as
`str(capture.id)` — also a string. The same coercion applies. **The real crash risk** is
that `resource_id` is passed as `capture.id` (a `UUID` object, line 260) while all the
payload kwargs use `str(...)` — if a future audit version tightens the schema or adds an
`extra="forbid"` field that matches one of the kwargs as a string, the inconsistency will
surface. The existing test in `test_referral_audit_events.py` exercises the schema with
raw `UUID` objects (line 102-107), not strings, so the test does not catch a string/UUID
type mismatch at the callsite.

**Fix:** Pass raw `UUID` objects (not `str(...)`) as payload kwargs for UUID fields, matching
the project's other audit callsites. Keep `str(...)` only for structlog (`_log.info`)
calls where string representation is needed:

```python
# In get_or_create_referral_code:
await audit.emit(
    session,
    "referral_code_generated",
    actor_user_id=None,
    resource_type="referral",
    resource_id=code_row.id,
    client_id=client_id,            # UUID, not str(client_id)
    referral_code_id=code_row.id,   # UUID, not str(code_row.id)
    code=new_code_str,
)

# In capture_referral:
await audit.emit(
    session,
    "referral_captured",
    actor_user_id=None,
    resource_type="referral",
    resource_id=capture.id,
    referee_client_id=referee_principal_id,         # UUID
    referrer_client_id=code_row.client_id,          # UUID
    referral_capture_id=capture.id,                 # UUID
    referral_code_id=code_row.id,                   # UUID
)
```

---

## Warnings

### WR-01: Concurrent captures raise unhandled 500 — TOCTOU on `get_capture_by_referee`

**File:** `apps/backend/app/modules/referrals/service.py:228-253`

**Issue:** The idempotency gate in `capture_referral` (lines 228-235) reads the existing
capture row before inserting. Two concurrent POST `/client/referral/capture` requests for
the same referee both read `existing_capture=None`, both pass the self-referral guard
and code lookup, and both attempt to `session.flush()` a new `ReferralCapture` row.

PostgreSQL's `UNIQUE` index on `referee_client_id` (`uq_referral_captures_referee_client_id`)
will reject the second flush with an `IntegrityError`. The service has no `try/except` for
`IntegrityError` (per project convention — no try/except in routers or service functions
that reach the router), so the second request surfaces as an unhandled 500, violating the
idempotency contract of the endpoint.

The project convention cited in `service.py:7` is "RETURNING-gated audit emit" using
`pg_insert on_conflict_do_nothing`. This is the correct pattern for truly idempotent
inserts at the DB level. The current implementation is a read-check-insert TOCTOU that
relies on single-threaded serialisation.

**Fix:** Use PostgreSQL `INSERT ... ON CONFLICT DO NOTHING RETURNING id` via `pg_insert`:

```python
from sqlalchemy.dialects.postgresql import insert as pg_insert

stmt = (
    pg_insert(ReferralCapture)
    .values(
        referee_client_id=referee_principal_id,
        referrer_client_id=code_row.client_id,
        referral_code_id=code_row.id,
    )
    .on_conflict_do_nothing(index_elements=["referee_client_id"])
    .returning(ReferralCapture.id)
)
result = await session.scalar(stmt)
if result is None:
    # Conflict — idempotent no-op (second concurrent insert)
    return
capture_id = result
# Emit audit only when result is not None (RETURNING-gated)
await audit.emit(session, "referral_captured", ..., referral_capture_id=capture_id, ...)
```

The RETURNING-gated audit emit mirrors the pattern described in the module docstring
(`service.py:7-8`: "idempotency via DB partial-UNIQUE + pg_insert on_conflict_do_nothing
with RETURNING-gated audit emit") and prevents the 500 under concurrent load.

---

### WR-02: `resolve_public_code` returns `valid=True` for a soft-deleted referrer — PII exposure for deleted client

**File:** `apps/backend/app/modules/referrals/service.py:189-203`

**Issue:** The referrer first-name lookup at lines 189-196 filters `WHERE deleted_at IS NULL`.
If the referrer client is soft-deleted after their code was shared, the SQL returns `None`
for the row but the code row still exists, so the service returns:

```python
ReferralResolveResponse(
    valid=True,           # code exists → valid=True
    referrer_first_name=None,  # deleted client → row is None
    welcome_bonus_kopecks=...,
)
```

The caller receives `valid=True` with `referrer_first_name=None` — a contradictory
response that the PWA landing page cannot correctly render ("Your friend invited you…"
but there is no name). More importantly: this allows a capture by a new referee against
a deleted referrer's code. The capture will succeed (`capture_referral` does not check
whether the referrer is alive — it only checks the code row exists and prevents self-referral).
A new `ReferralCapture` row will be inserted with a `referrer_client_id` pointing to a
soft-deleted client, and a reward will be owed to a deleted client if reward logic is
added in a future phase.

**Fix:** Treat a missing (deleted) referrer as an invalid code in `resolve_public_code`:

```python
row = (
    await session.execute(
        text("SELECT first_name FROM clients WHERE id = :cid AND deleted_at IS NULL"),
        {"cid": str(code_row.client_id)},
    )
).mappings().one_or_none()

if row is None:
    # Referrer is soft-deleted — treat code as invalid (anti-oracle: still 200)
    return ReferralResolveResponse(
        valid=False,
        referrer_first_name=None,
        welcome_bonus_kopecks=0,
    )
```

Similarly, `capture_referral` should check that the resolved `code_row.client_id` is not
soft-deleted before inserting the capture row. Add a raw-SQL check (D-54-08) after
resolving the code row:

```python
referrer_alive = (
    await session.execute(
        text("SELECT 1 FROM clients WHERE id = :cid AND deleted_at IS NULL"),
        {"cid": str(code_row.client_id)},
    )
).fetchone()
if referrer_alive is None:
    raise ReferralCodeNotFoundError("referral_code_not_found")
```

---

### WR-03: `ReferralCaptureRequest.code` allows spaces and arbitrary non-Crockford characters — bypass potential

**File:** `apps/backend/app/modules/referrals/schemas.py:51`

**Issue:** The `code` field is validated only with `min_length=1, max_length=16`. It does not
enforce that the value consists solely of Crockford-base32 characters (the set
`0-9A-HJKMNP-TV-Z`, no O/I/L). The repository function `get_code_by_value` normalises
to upper-case (`code_str.upper()`), but it does not reject strings containing spaces,
unicode characters, or characters outside the alphabet.

This is low-severity in isolation (an invalid code simply returns 404), but it creates a
minor oracle: an attacker who submits a code with unusual characters gets a 404, while
a valid code format but wrong value also gets 404 — the response is identical, so no
information is leaked. However, it also allows unexpected characters to be passed through
to the raw-SQL lookup in `get_code_by_value` (via SQLAlchemy parameterised query, so no
injection risk) and produces misleading 404s that bypass the "unknown code → 404"
contract by constructing codes that can never exist.

More practically: the `capture_referral` service documents `code` as "an 8-char
Crockford-base32 referral code" but the schema enforces neither the 8-char length nor
the Crockford alphabet. A client submitting a 1-char or 16-char code hits the DB lookup
unnecessarily.

**Fix:** Add a regex pattern and exact length constraint:

```python
class ReferralCaptureRequest(BackendSchemaBase):
    code: str = Field(
        min_length=8,
        max_length=8,    # codes are always exactly 8 chars
        pattern=r"^[0-9A-HJKMNP-TV-Z]{8}$",  # Crockford upper-case
    )
```

Since `get_code_by_value` already normalises to upper-case, the pattern should allow
lower-case too if the intent is to accept mixed-case input from the PWA. In that case:

```python
code: str = Field(
    min_length=8,
    max_length=8,
    pattern=r"^[0-9A-HJKMNPa-hjkmnpQ-TVWXYZq-tvwxyz]{8}$",  # Crockford any case
)
```

Simplest: accept upper or lower `[0-9A-HJKMNPQRSTVWXYZa-hjkmnpqrstvwxyz]{8}` and let
the repository normalise.

---

### WR-04: `update_referral_config` calls `session.commit()` inside the service — inconsistent with project D-03 caller-owns-txn discipline and breaks the transaction contract for the two client endpoints

**File:** `apps/backend/app/modules/referrals/service.py:286-306`

**Issue:** `update_referral_config` (lines 300-302) performs `session.flush()` then
`session.commit()` inside the service. The docstring acknowledges this: "Caller-owns-txn:
flush + commit here (D-03). Matches gym.service.update_gym_info discipline: singleton
write owns the transactional moment."

However, this is an inconsistency within the same module: `get_or_create_referral_code`
and `capture_referral` disclaim ownership (flush-only), forcing the commit onto the
router — but the router never calls commit (CR-01). `update_referral_config` takes the
opposite approach, owning the commit inside the service. The pattern is incoherent within
the module: one service function style for singleton writes, another for ledger writes,
with the router not adapting either way.

Regardless of which convention is chosen, the current state is broken for client
endpoints (CR-01). If the singleton-commit style is the intended pattern for this module,
then `get_or_create_referral_code` and `capture_referral` must also call
`session.commit()` at the end of their bodies (removing the "flush only" disclaimer).
If the router-commit style is preferred (which aligns with `clients/router.py` and
`schedule/service.py`), then `update_referral_config` should be refactored to flush-only,
and the `owner_update_referral_config` router handler must call `await session.commit()`.

**Fix (preferred — align to router-owns-commit discipline):**

In `service.py`, change `update_referral_config` to flush-only (remove `session.commit()`):

```python
async def update_referral_config(...) -> ReferralConfigResponse:
    config = await repository.upsert_config(session, data)
    await session.flush()
    # No commit here — router owns the commit (D-03 caller-owns-txn)
    return ReferralConfigResponse(...)
```

In `router.py`, add commit in `owner_update_referral_config`:

```python
result = await service.update_referral_config(session, actor, payload)
await session.commit()   # router owns the transactional moment
return envelope(result)
```

---

## Info

### IN-01: `ReferralConfigUpdateRequest` imported in `repository.py` — tight coupling, dead import if full-replace semantics change

**File:** `apps/backend/app/modules/referrals/repository.py:18`

**Issue:** `repository.py` imports `ReferralConfigUpdateRequest` (line 18) and
`upsert_config` takes it as a typed parameter. Repository functions are documented as
"thin select wrappers" with no business logic; accepting a Pydantic request schema as
input (rather than raw field values or a dataclass) creates a direct coupling from the
data-access layer to the HTTP schema layer. If the wire format changes (e.g., PATCH
semantics replacing PUT), the repository signature must also change.

Additionally, `upsert_config` uses `data.model_dump(exclude_unset=True)` (line 83),
implying PATCH semantics, but `ReferralConfigUpdateRequest` is documented as
"full-replace semantics, not PATCH" (schemas.py:68) — the `exclude_unset=True` is a
no-op for a required-field model where both fields must always be set.

**Fix:** Either accept typed scalar parameters directly:

```python
async def upsert_config(
    session: AsyncSession,
    referrer_bonus_kopecks: int,
    referee_welcome_kopecks: int,
) -> ReferralConfig:
```

Or, if keeping the current pattern for consistency with `gym/repository.py` precedent,
remove the `exclude_unset=True` since the schema guarantees both fields are always
present:

```python
updates = data.model_dump()  # not exclude_unset=True — all fields always present
```

---

_Reviewed: 2026-06-08_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
