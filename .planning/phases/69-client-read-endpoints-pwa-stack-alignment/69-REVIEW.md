---
phase: 69-client-read-endpoints-pwa-stack-alignment
reviewed: 2026-05-30T00:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - apps/backend/app/api/v1/router.py
  - apps/backend/app/modules/client_portal/__init__.py
  - apps/backend/app/modules/client_portal/repository.py
  - apps/backend/app/modules/client_portal/router.py
  - apps/backend/app/modules/client_portal/schemas.py
  - apps/backend/app/modules/client_portal/service.py
  - apps/backend/tests/integration/client_portal/conftest.py
  - apps/backend/tests/integration/client_portal/test_idor_sweep.py
  - apps/backend/tests/integration/client_portal/test_read_endpoints.py
  - apps/client-pwa/src/lib/clientFetcher.ts
  - apps/client-pwa/src/lib/clientFetcher.test.tsx
findings:
  critical: 2
  warning: 3
  info: 2
  total: 7
status: issues_found
---

# Phase 69: Code Review Report

**Reviewed:** 2026-05-30
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Phase 69 delivers client-scoped read endpoints (`/api/v1/client/...`) and PWA stack
alignment. The IDOR discipline is structurally sound — every owned read receives
`client_id` solely from the cookie principal (`require_client()`), never from a URL param,
and all SQL uses `:name` bind parameters with no interpolation of user input. Catalog
field projection correctly omits owner-only fields. The `clientFetcher.ts` single-flight
refresh and CSRF isolation are correctly implemented.

Two critical issues were found: a wrong membership query that consistently returns the
**oldest** rather than the most-recent active membership, and CSRF token elevation for
`TRACE` requests in the PWA fetcher. Three warnings cover a semantic gap in the refund
ownership query, a hollow IDOR test assertion path, and a test phone-number collision
risk. Two informational findings cover minor quality gaps.

---

## Critical Issues

### CR-01: `fetch_client_membership` returns the oldest active membership, not the newest

**File:** `apps/backend/app/modules/client_portal/repository.py:67`

**Issue:** The ORDER BY clause is `start_date ASC, created_at DESC LIMIT 1`. With
`ASC`, the row with the **smallest** (earliest) `start_date` is selected first. If a
client has an old expired+reactivated membership row still marked `active` (possible in
grace-period or re-purchase scenarios where the cron hasn't run yet), or simply holds
two overlapping `active` rows temporarily, the query surfaces the stale older one, not
the current subscription the client purchased most recently.

The canonical membership resolver in `apps/backend/app/modules/memberships/repository.py`
(line ~387) is explicitly documented as using `ORDER BY start_date ASC, created_at DESC`
as the **tiebreak for concurrent freeze/unfreeze** under the rule "oldest start wins" —
a domain-specific invariant for the staff-side that does not automatically apply to the
client-portal display. More importantly, the comment in that file says this is the
*tiebreak*, not the primary selection intent. For a client-facing display the caller
expects to see the most recently started active plan. The query should be
`ORDER BY start_date DESC, created_at DESC LIMIT 1` to surface the latest active plan.

**Fix:**
```sql
-- Change in fetch_client_membership (repository.py line 67)
"WHERE client_id = :client_id AND status = 'active' "
"ORDER BY start_date DESC, created_at DESC LIMIT 1"
--                    ^^^^
```

If the intent is intentionally to replicate the staff canonical resolver's `ASC`
tiebreak, that must be explicitly documented with the D-26-17 decision reference —
and the near-expiry test in `test_read_endpoints.py` (which seeds a `frozen` membership
to avoid competing with the active one) should be revisited.

---

### CR-02: `isMutating()` in `clientFetcher.ts` omits `TRACE` — CSRF not sent for TRACE requests, diverges from backend contract

**File:** `apps/client-pwa/src/lib/clientFetcher.ts:38-40`

**Issue:** The comment on line 37 correctly states it should mirror the server
`_SAFE_METHODS = {GET, HEAD, OPTIONS, TRACE}`. However the implementation omits `TRACE`:

```ts
function isMutating(method: string): boolean {
  return method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS'
  // TRACE is missing — treated as mutating
}
```

Because `isMutating` returns `true` for `TRACE`, the code **does** attempt to add a
CSRF header for TRACE requests (which is harmless in practice since TRACE is not used
by the app). However the asymmetry creates a correctness contract mismatch: the server
exempts `TRACE` from CSRF checking; the client sends a CSRF header for it. More
critically, the inverted logic means any future method added to the server's safe set
that the developer forgets to update here will silently send CSRF headers when it
shouldn't — a divergence that can cause mutations on the server's safe list to bypass
double-submit protection if the server-side list were ever tightened.

The higher-risk vector: because the method check is the **only** guard before sending
the CSRF token value in the `X-CSRF-Token` header, the inconsistency exposes the CSRF
token value in requests to methods the server considers safe (and therefore doesn't
validate against the header — the value leaks to the server for no reason).

**Fix:**
```ts
const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS', 'TRACE'])

function isMutating(method: string): boolean {
  return !SAFE_METHODS.has(method)
}
```

---

## Warnings

### WR-01: Refund ownership query has a semantic gap — `subject_id` for refund rows points to the originating Payment, not to a membership/pt_package

**File:** `apps/backend/app/modules/client_portal/repository.py:260-279`

**Issue:** The refund branch of `fetch_client_payments_page` correctly resolves
ownership through `p.refund_of = orig.id` and then checks `orig.subject_kind` /
`orig.subject_id` against `memberships`/`pt_packages`. However, the `subject_id` for
a `subject_kind='refund'` row is set to `payment.id` (the original payment's primary
key) in `conftest.py` line 360-364 — not to a membership or pt_package UUID. This is
confirmed by the Payment model: `subject_id` for a refund row is a self-referential
UUID pointing to the parent payment row.

The ownership check in the CTE:

```sql
(p.subject_kind = 'refund' AND p.refund_of IS NOT NULL
 AND EXISTS (
     SELECT 1 FROM payments orig
     WHERE orig.id = p.refund_of ...
 ))
```

traverses `p.refund_of → orig.id` correctly. This path **is safe** as written because
the `refund_of` FK is used — not `subject_id` — to join to the originating payment.
The concern is that if any future code path consults `p.subject_id` on a refund row
expecting it to point to a membership or pt_package, it will silently get a payment UUID
instead and the EXISTS subquery will return false (IDOR-safe but data-silent). A comment
clarifying that `subject_id` on refund rows is a payment UUID (not a domain-object UUID)
is needed to prevent future maintainers from accidentally writing a broken ownership
check.

Additionally: the `subject_id` for refund rows is stored as `payment.id` in the conftest
test fixture, but the **ownership CTE never queries `p.subject_id` for the refund
branch** — it only uses `p.refund_of`. This means the CTE would still work even if
`subject_id` were NULL on refund rows. The test therefore does not exercise the
`subject_id` field on the refund path at all, leaving a gap should the model semantics
ever change.

**Fix:** Add an explicit comment to `fetch_client_payments_page` clarifying the
`subject_id` semantics on refund rows:

```python
# For 'refund' rows, subject_id contains the originating Payment UUID (self-ref),
# NOT a membership or pt_package UUID. Ownership is resolved via refund_of FK only.
```

---

### WR-02: IDOR sweep test assertion can pass vacuously when both clients share the same booking slot / trainer UUIDs

**File:** `apps/backend/tests/integration/client_portal/test_idor_sweep.py:148-185`

**Issue:** `_extract_ids_from_data` collects all UUID-shaped string values from the
response. The test seeding creates a separate `Trainer` and `TrainerAvailabilitySlot`
per client (each with unique UUIDs) so their IDs will not overlap. However:

1. The `trainer_name` field returned by `fetch_client_next_booking` is a plain string
   (`t.full_name`), not the trainer UUID, so the trainer UUID itself is not returned in
   the response — the sweep cannot detect trainer-record leakage via this path.

2. More critically, the sweep checks that `victim_owned_ids & response_ids` is empty,
   but `victim_owned_ids` does not include the `booking_id` of the victim (that field
   is not tracked in `ClientOwnedData` — there is a `visit_id`, `pt_session_id`,
   `payment_id` but **no `booking_id`**). If the bookings endpoint were to somehow
   return the victim's booking row, the booking UUID would appear in `response_ids` but
   not in `victim_owned_ids`, so the assertion `leaked = victim_owned_ids & response_ids`
   would remain empty — a false green.

**Fix:** Add `booking_id: UUID` to `ClientOwnedData` and include it in both the seeding
return value and the `victim_owned_ids` set:

```python
# In ClientOwnedData dataclass:
booking_id: UUID  # add after pt_package_id

# In _seed_client_owned_data return:
booking_id=booking.id,

# In test_owned_resource_idor:
victim_owned_ids = {
    ...,
    str(victim_data.booking_id),   # add this
}
```

---

### WR-03: Phone number generation in `test_read_endpoints.py` can produce invalid E.164 phone numbers with collisions across test runs in the same DB snapshot

**File:** `apps/backend/tests/integration/client_portal/test_read_endpoints.py:119,192,240`

**Issue:** Three test helpers generate dynamic phone numbers using the pattern:

```python
phone=f"+7999666{int(suffix[:4], 16) % 10000:04d}"
```

`suffix` is a 6-character hex UUID fragment (`uuid4().hex[:6]`). `suffix[:4]` is always
4 hex digits with value 0x0000–0xFFFF = 0–65535. After `% 10000`, the range is 0–9999,
yielding always-valid 11-digit phones. This is fine in isolation.

However, three different test functions in the same file independently call `uuid4()` and
use the same format with **different prefixes** (`666`, `555`, `444`). The issue is that
`telegram_user_id` is also generated from the same `suffix[:4]` hex value but with an
additive offset (`666_000_000 + int(suffix[:4], 16)`, etc.). With `int(suffix[:4], 16)`
spanning 0–65535, two test helpers using the same numeric offset base risk colliding if
UUID generation produces the same 4-hex prefix — extremely unlikely for uuid4 but
statistically possible in large CI runs.

More concretely: the `_CLIENT_A_PHONE = "+79997770001"` and `_CLIENT_B_PHONE =
"+79997770002"` are hardcoded. The dynamically-generated phones in `test_read_endpoints.py`
use `+7999666xxxx`, `+7999555xxxx`, `+7999444xxxx` — no overlap with A/B. But the
`telegram_user_id` ranges (`666_000_000–666_065_535`, `555_000_000–555_065_535`,
`444_000_000–444_065_535`) overlap with each other only if the same hex prefix is
generated twice across different test functions within the same test-session — SAVEPOINT
rollback ensures rows are torn down per-test, so this cannot collide at the DB level.
No actual collision risk in practice.

The real quality issue is that if the `phone` field has a UNIQUE constraint on `clients`
and two tests running in the same transaction snapshot (unlikely but possible in
parallel test execution) generate the same `suffix[:4]` hex value, one INSERT will fail
with a UniqueViolation that produces a confusing error message unrelated to the code
under test.

**Fix:** Use the full `uuid4().hex` (32 chars, not 6) for suffix to make the collision
space negligible, or use a counter/timestamp:

```python
suffix = uuid4().hex  # 32 hex chars — collision probability negligible
phone=f"+7999666{int(suffix[:4], 16) % 10000:04d}"  # existing logic works the same
```

---

## Info

### IN-01: `GET /client/bookings` silently ignores `?upcoming=1` query parameter

**File:** `apps/backend/app/modules/client_portal/router.py:87-112`

**Issue:** The IDOR sweep test sends `GET /api/v1/client/bookings?upcoming=1` (lines
94-95 of `test_idor_sweep.py`), and the context decisions (D-69-01) call this the
"upcoming-bookings query". However `client_list_bookings` accepts only a `PageQuery`
dependency — it has no `upcoming: bool` parameter. FastAPI silently ignores unknown
query params by default. The `?upcoming=1` in the test URL is a no-op; the endpoint
always returns the next upcoming booking regardless.

This is not a security issue (the endpoint is scoped by cookie principal and always
returns the same data). But it creates misleading test URLs and will confuse Phase 70
implementors who wire the full paginated booking list — they may assume `?upcoming=1`
already has server-side meaning and skip adding it.

**Fix:** Either (a) declare `upcoming: bool = Query(default=True)` as a parameter and
document that it's reserved for Phase 70, or (b) update the test URL to remove
`?upcoming=1` since it has no effect:

```python
# test_idor_sweep.py — simplest immediate fix:
("/api/v1/client/bookings", True),
("/api/v1/client/bookings", False),
```

---

### IN-02: `client_list_bookings` calls a private service function (`_get_client_next_booking`) directly from the router

**File:** `apps/backend/app/modules/client_portal/router.py:104`

**Issue:** `router.py` directly calls `service._get_client_next_booking(...)` — a
function whose leading underscore marks it as a module-internal helper. The public API
surface of the service layer should be used from the router; private helpers should
remain internal to the service. If `_get_client_next_booking` is called from the router,
it is effectively public and the underscore convention is broken.

```python
# router.py line 104:
single = await service._get_client_next_booking(session, client.id)
```

**Fix:** Either rename `_get_client_next_booking` to `get_client_next_booking` in
`service.py` (making its public status explicit), or introduce a thin public wrapper:

```python
# service.py — rename the function:
async def get_client_next_booking(  # was _get_client_next_booking
    session: AsyncSession,
    client_id: UUID,
) -> ClientNextBookingResponse | None:
    ...

# get_client_home already calls it internally — update that call too
```

---

_Reviewed: 2026-05-30_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
