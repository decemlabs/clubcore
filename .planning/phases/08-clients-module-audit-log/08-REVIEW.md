---
phase: 08-clients-module-audit-log
reviewed: 2026-05-03T00:00:00Z
depth: standard
files_reviewed: 16
files_reviewed_list:
  - apps/backend/alembic/env.py
  - apps/backend/app/api/v1/router.py
  - apps/backend/app/modules/clients/repository.py
  - apps/backend/app/modules/clients/router.py
  - apps/backend/app/modules/clients/service.py
  - apps/backend/tests/integration/auth/test_login.py
  - apps/backend/tests/integration/auth/test_logout.py
  - apps/backend/tests/integration/auth/test_refresh.py
  - apps/backend/tests/integration/auth/test_telegram_start.py
  - apps/backend/tests/integration/auth/test_telegram_verify_happy.py
  - apps/backend/tests/integration/clients/__init__.py
  - apps/backend/tests/integration/clients/conftest.py
  - apps/backend/tests/integration/clients/test_audit_writes.py
  - apps/backend/tests/integration/clients/test_clients_crud.py
  - apps/backend/tests/integration/clients/test_clients_list.py
  - apps/backend/tests/integration/clients/test_clients_rbac.py
findings:
  critical: 2
  warning: 6
  info: 4
  total: 12
status: issues_found
---

# Phase 08: Code Review Report

**Reviewed:** 2026-05-03
**Depth:** standard
**Files Reviewed:** 16
**Status:** issues_found

## Summary

The clients module implements the planned route → service → repository chain
with sensible architectural boundaries (only `repository.py` imports the
`Client` ORM, audit emit is co-transactional with mutations) and the audit /
RBAC / soft-delete invariants are exercised by an integration suite that
covers every BLOCKER acceptance criterion in the plan.

However, two BLOCKER-class defects are present:

1. **SQL `LIKE`-injection / wildcard bypass** in `repository.list_alive` —
   user-supplied `q` is interpolated into an `ILIKE` pattern without escaping
   `%`, `_`, or `\`. This lets any caller with `VIEW,CLIENTS` craft pattern
   matches the schema does not intend (privacy bypass on a PII table) and
   trigger O(N) sequential scans by side-stepping the trigram GIN indexes.
2. **Eager `session.rollback()` inside a SAVEPOINT-shared session** in
   `service.create_client` / `service.update_client`. When `IntegrityError`
   fires (phone collision), the service issues `await session.rollback()` —
   under the `join_transaction_mode='create_savepoint'` test fixture this
   rolls the OUTER transaction back, but more importantly in production it
   discards every prior pending mutation in the unit-of-work and any
   in-flight audit row the request had already staged. For inserts there is
   nothing else pending; for updates this is a real footgun if any caller
   ever stages multiple operations (and it loses the audit context that the
   request handlers might otherwise emit on the failure path).

Six additional warnings cover audit-payload data leakage on phone change,
non-determinism in tests that depend on equal `created_at` ordering, weak
RBAC coverage on the PATCH route, an unused fixture parameter that masks a
fixture-dependency typo, the missing `previous_phone` on payload key
collision risk, and a non-functional `redis_clean` fixture in
`test_telegram_start.py` (no Redis flush at all).

The remaining info items are minor.

## Critical Issues

### CR-01: `q` interpolated into ILIKE pattern without escaping `%`, `_`, `\`

**File:** `apps/backend/app/modules/clients/repository.py:73-88`

**Issue:** `q` is taken from request query params, lowercased, and pasted
directly into an ILIKE pattern:

```python
like_pattern = f"%{query.q.lower()}%"
...
full_name_expr.ilike(like_pattern),
Client.phone.ilike(f"%{query.q}%"),
```

ILIKE treats `%` and `_` as wildcards and `\` as the escape character. A
caller submitting `q=%` matches every row regardless of the intended search.
A caller submitting `q=_` matches every row containing any single character.
This is a privacy/authorisation regression on a PII table: someone with
`VIEW,CLIENTS` can dump the entire client base via `?q=%` even while the
sanctioned UX may block bare list views. It also defeats the trigram GIN
indexes (the PLAN's documented Pitfall 1 trigram indexes only assist
patterns that begin with non-wildcard literals), so the query degrades to a
sequential scan over `clients` for every search.

**Fix:** Escape user-supplied `q` before interpolation, then pass `escape=`
to ILIKE so the dialect knows the escape character:

```python
def _escape_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

if query.q is not None:
    safe = _escape_like(query.q.lower())
    like_pattern = f"%{safe}%"
    phone_pattern = f"%{_escape_like(query.q)}%"
    predicates.append(
        or_(
            full_name_expr.ilike(like_pattern, escape="\\"),
            Client.phone.ilike(phone_pattern, escape="\\"),
        )
    )
```

Also add an integration test (`?q=%` returns 0 results when no row contains
a literal `%`) so the regression is locked.

---

### CR-02: `session.rollback()` inside service breaks the unit-of-work boundary

**File:** `apps/backend/app/modules/clients/service.py:117-122, 167-172`

**Issue:** Both `create_client` and `update_client` catch `IntegrityError`
from `session.flush()` and immediately call `await session.rollback()`
before re-raising. The module's own docstring (lines 1-15) says the service
owns the transactional moment so it can co-write the audit log row in the
same UoW. Issuing `rollback()` here:

1. Aborts any other pending mutation the caller might have staged in the
   same session — defeating the very co-transactional guarantee the
   architecture promises.
2. Under the test suite's
   `join_transaction_mode='create_savepoint'` fixture, the *outermost*
   transaction is the SAVEPOINT envelope's outer transaction. Calling
   `await session.rollback()` on the joined session releases the joined
   savepoint, but downstream code in the same request still expects a
   live session — any subsequent `session.flush()` (e.g. by FastAPI's
   exception handler emitting another audit row, or a future
   wrapper that adds tracing) will run on a closed/auto-begun fresh
   transaction without the savepoint protection.
3. Discards the request's logical transaction even though the request is
   about to raise a domain exception that the global handler maps to 409.
   The 409 response is supposed to leave the database in the same state as
   the start of the request, but it does so by accident here — the
   `IntegrityError` already invalidated the SAVEPOINT, so rollback was
   forced. The correct primitive is `await session.rollback()` against
   *that savepoint*, not the whole session, OR letting the FastAPI request
   scope handle teardown via `get_db` exit.

**Fix:** Drop the explicit rollback — under SQLAlchemy 2.0 async, when
`flush()` raises `IntegrityError` the transaction is already invalid and
`get_db`'s teardown will rollback. The service should just translate the
exception:

```python
try:
    await session.flush()
except IntegrityError as exc:
    if _is_phone_conflict(exc):
        raise PhoneExistsError("phone_exists") from exc
    raise
```

If `get_db` does NOT rollback on exception today, fix `get_db` first (single
choke point) — every service should not be reaching for `session.rollback()`.

## Warnings

### WR-01: Phone leak via audit `previous_phone` is captured but never sanitised against length / type

**File:** `apps/backend/app/modules/clients/service.py:177-179`

**Issue:** `payload["previous_phone"] = changed_previous["phone"]` stores
whatever `getattr(client, "phone")` returned at update time. Because
`repository.update_client` passes the value through `model_dump`, this is
guaranteed to be a `str` for the canonical case — but the type annotation
on `changed_previous` is `dict[str, object]`, so the audit emission relies
on the payload-shaping invariant being held by the repository. If any
future caller adds a non-`str`-typed field whose name happens to be `phone`
(e.g. a normalised number type), the audit row's JSONB column receives
something the AUDIT-02 contract did not promise.

**Fix:** Type the previous values precisely (`dict[str, str | None | int]`)
or convert at the audit-emit boundary:

```python
if "phone" in changed_previous:
    payload["previous_phone"] = str(changed_previous["phone"])
```

Add a unit test that asserts `isinstance(payload["previous_phone"], str)`.

---

### WR-02: PATCH never tested against the reception role

**File:** `apps/backend/tests/integration/clients/test_clients_rbac.py:78-87`

**Issue:** The RBAC suite covers POST + DELETE + GET for reception, but
there is no PATCH-by-reception test. PATCH maps to `(EDIT, CLIENTS)` which
the plan says is NOT in `OWNER_ONLY`, so reception should get 200 — but
that is unverified. A future tightening of `OWNER_ONLY` (or a typo that
adds PATCH to the owner-only set) would silently regress reception's edit
flow without breaking any test.

**Fix:** Add `test_patch_reception_returns_200` mirroring
`test_create_reception_returns_201`, and a CSRF-mismatch counterpart.

---

### WR-03: `test_list_sort_default_is_created_at_desc` relies on identical `created_at` and is non-deterministic outside the savepoint fixture

**File:** `apps/backend/tests/integration/clients/test_clients_list.py:190-214`

**Issue:** The test docstring acknowledges that two POSTs share `created_at`
because the SAVEPOINT-rolled `db_session` keeps both inside one transaction
(`transaction_timestamp()` is constant). The router actually issues
real-world `session.commit()` per request, however — under
`join_transaction_mode='create_savepoint'` the inner commits become nested
savepoint releases, but the outer transaction is the same connection, so
this *happens* to hold. If the fixture is ever rebuilt to issue per-request
connections (e.g. for a future load test), this test silently inverts:
`a.id` may now have a *smaller* `created_at` than `b.id`. The assertion
`expected_first = max(a["id"], b["id"])` would still pass for the random
case where `a["id"] > b["id"]` and fail otherwise — so the test becomes
flaky rather than deterministic.

**Fix:** Either insert the rows with explicit, distinct `created_at` values
through the repository (bypassing the route) or assert only the first row's
`created_at` >= the second row's `created_at`, with `id DESC` only as a
secondary tie-break: drop the strict ordering assertion, or override
`func.now()` per-row.

---

### WR-04: `redis_clean` fixture in `test_telegram_start.py` is missing — tests don't flush Redis

**File:** `apps/backend/tests/integration/auth/test_telegram_start.py:1-63`

**Issue:** This test file has NO `redis_clean` fixture, while every other
auth test file in the suite includes one. `/api/v1/auth/telegram/start`
likely writes to Redis (rate-limit counter; deep-link token mapping in
production). Without a Redis flush between tests, accumulated rate-limit
counters can push the first test in a fresh CI run past a daily quota and
make the assertion `assert response.status_code == 200` fail
intermittently. This is a flaky-test risk, not a correctness bug — but it's
the kind of flake that costs a CI re-run every few weeks and obscures real
regressions.

**Fix:** Copy the `redis_clean` fixture from any sibling auth test file and
list it in each test signature:

```python
@pytest_asyncio.fixture
async def redis_clean(app: FastAPI) -> Redis:
    client: Redis = app.state.redis
    await client.flushdb()
    return client

async def test_telegram_start_returns_deep_link_and_creates_otp_row(
    async_client: AsyncClient,
    db_session: AsyncSession,
    redis_clean: Redis,
) -> None:
    ...
```

---

### WR-05: `_is_phone_conflict` falls back to substring match on `str(exc.orig)` — fragile across psycopg / asyncpg versions

**File:** `apps/backend/app/modules/clients/service.py:95-100`

**Issue:** `getattr(exc.orig, "constraint_name", None)` works for asyncpg's
`UniqueViolationError`, but the fallback `"uq_clients_phone_alive" in
str(exc.orig)` is locale- and driver-version sensitive. Postgres ships a
translated error message in many locales by default; if the server's
`lc_messages` is e.g. `ru_RU.UTF-8`, the message is "повторяющееся значение
ключа нарушает ограничение уникальности «uq_clients_phone_alive»" and
substring match by index still works — but if a future Postgres version or
an aggressive sanitiser strips the constraint quotation, the fallback
silently returns False, the IntegrityError propagates as a 500, and the
caller sees a generic "Internal server error" instead of `409 phone_exists`.

**Fix:** Inspect `exc.orig.__cause__` / `exc.orig.diag.constraint_name`
(asyncpg surfaces `constraint_name` directly; psycopg3 exposes
`exc.diag.constraint_name`). Drop the substring match; if neither
attribute is set, treat it as a non-phone conflict and re-raise.

```python
def _is_phone_conflict(exc: IntegrityError) -> bool:
    constraint = getattr(exc.orig, "constraint_name", None)
    if constraint is None:
        diag = getattr(exc.orig, "diag", None)
        constraint = getattr(diag, "constraint_name", None)
    return constraint == "uq_clients_phone_alive"
```

Add a unit test that constructs an `IntegrityError` with a non-phone
constraint and asserts `_is_phone_conflict` returns False.

---

### WR-06: `repository.update_client` mutates `value` in-place, shadowing the `dict[str, Any]` value

**File:** `apps/backend/app/modules/clients/repository.py:177-189`

**Issue:**

```python
for key, value in updates.items():
    if (
        key == "emergency_contact"
        and value is not None
        and isinstance(value, EmergencyContact)
    ):
        value = value.model_dump()
    previous = getattr(client, key)
    if previous != value:
        changed[key] = previous
        setattr(client, key, value)
```

The `isinstance(value, EmergencyContact)` branch is dead code: `updates =
data.model_dump(exclude_unset=True)` already serialises Pydantic submodels
to plain `dict`, so `value` is `dict | None`, never `EmergencyContact`.
Reading the source, the guard is a leftover from an earlier draft. It has
two bad consequences:

1. mypy sees the branch as live and types `value` accordingly — masking
   real type drift if `model_dump()` config changes (e.g. the Pydantic
   `mode='python'` argument flips a flag).
2. The `previous != value` comparison now compares a stored JSONB dict
   (`Client.emergency_contact` is loaded as `dict | None`) against the
   incoming dict, which is fine — but the comment "otherwise it's
   already a dict" is the only thing that documents this. If a future
   contributor sees the `isinstance` and adds another union branch
   (assuming the Pydantic instance can arrive), they'll introduce a real
   bug.

**Fix:** Remove the dead branch and let `model_dump` do its job:

```python
updates = data.model_dump(exclude_unset=True, mode="python")
for key, value in updates.items():
    previous = getattr(client, key)
    if previous != value:
        changed[key] = previous
        setattr(client, key, value)
```

Leave a one-line comment explaining that submodels arrive as plain dicts.

## Info

### IN-01: `_actor` parameter in router is fine, but `actor` typed `CurrentUser` makes the unused-name lint inconsistent

**File:** `apps/backend/app/modules/clients/router.py:59-61, 76-78, 131-133`

**Issue:** GET endpoints use `_actor` (underscore prefix to silence
`noUnusedParameters`-style checks for FastAPI dep-only parameters). DELETE
uses `actor` even though the variable is read only by the dependency
itself, not the function body. Inconsistency makes a future audit-of-actor
addition error-prone (developer may add a body that reads `actor` in GET
and find it isn't bound). Convention only.

**Fix:** Either rename DELETE's parameter to `_actor` or read `actor.id`
in the body for documentation purposes.

---

### IN-02: `Path = ('/' or '/api/v1/auth')` cookie-attribute assertions are case-sensitive

**File:** `apps/backend/tests/integration/auth/test_login.py:72, 78, 83`

**Issue:** `assert "Path=/" in sz_access` is case-sensitive against the
`Set-Cookie` syntax. RFC 6265 lists attribute names as case-insensitive
("Path" / "path" both legal). httpx + Starlette emit `Path` today, but the
tests will silently break if the framework upgrades to lowercase
attribute names. Same pattern for `HttpOnly` (line 73) and `samesite=lax`
(handled correctly with `.lower()` on line 74).

**Fix:** Lower-case the haystack first or use a regex:

```python
assert "path=/" in sz_access.lower()
```

---

### IN-03: `_full_name(client)` builds the same string for a client with no middle name twice — once at create-time, again at delete-time — but capitalisation is not normalised

**File:** `apps/backend/app/modules/clients/service.py:87-92`

**Issue:** `_full_name` joins last/first[/middle] with single spaces. If a
user enters `last_name="ИВАНОВ "` (trailing whitespace not stripped at the
schema level), the audit payload will contain the trailing space verbatim.
This is not a bug per se, but the audit log is meant to be human-searchable
and `WHERE payload->>'full_name' ILIKE 'ivanov'` will not match
`'ivanov '`.

**Fix:** Strip whitespace in `ClientCreateRequest` validators (Pydantic
`StringConstraints(strip_whitespace=True)`), or in `_full_name`:

```python
return " ".join(p.strip() for p in parts if p and p.strip())
```

---

### IN-04: `test_no_audit_log_endpoint_exists` is not exhaustive

**File:** `apps/backend/tests/integration/clients/test_audit_writes.py:177-189`

**Issue:** The AUDIT-03 invariant states "no public read endpoint for the
audit log." The test checks two plausible URL spellings (`/audit-log`,
`/auditlog`) but does not check `/audit_log`, `/audit`, `/admin/audit`,
or query AuditLog via clients (`/api/v1/clients?audit=1`). A negative test
of this kind is best done by walking `app.routes` and asserting no path
contains "audit":

**Fix:**

```python
async def test_no_audit_log_endpoint_exists(app: FastAPI) -> None:
    paths = [r.path for r in app.routes if hasattr(r, "path")]
    assert not any("audit" in p.lower() for p in paths), \
        f"audit path leaked: {[p for p in paths if 'audit' in p.lower()]}"
```

This catches the entire class instead of two spellings.

---

_Reviewed: 2026-05-03_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
