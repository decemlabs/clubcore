---
phase: 33-pt-package-plans-instances
reviewed: 2026-05-15T00:00:00Z
depth: standard
files_reviewed: 18
files_reviewed_list:
  - apps/backend/alembic/env.py
  - apps/backend/alembic/versions/0013_pt_package_plans.py
  - apps/backend/alembic/versions/0014_pt_packages.py
  - apps/backend/app/api/v1/router.py
  - apps/backend/app/core/audit_payloads.py
  - apps/backend/app/core/dependencies.py
  - apps/backend/app/main.py
  - apps/backend/app/modules/payments/repository.py
  - apps/backend/app/modules/payments/service.py
  - apps/backend/app/modules/pt_packages/__init__.py
  - apps/backend/app/modules/pt_packages/constants.py
  - apps/backend/app/modules/pt_packages/models.py
  - apps/backend/app/modules/pt_packages/repository.py
  - apps/backend/app/modules/pt_packages/router.py
  - apps/backend/app/modules/pt_packages/schemas.py
  - apps/backend/app/modules/pt_packages/service.py
  - apps/backend/app/workers/__init__.py
  - apps/backend/app/workers/scheduled/expire_pt_packages.py
findings:
  critical: 3
  warning: 6
  info: 5
  total: 14
status: issues_found
---

# Phase 33: Code Review Report

**Reviewed:** 2026-05-15
**Depth:** standard
**Files Reviewed:** 18
**Status:** issues_found

## Summary

Phase 33 lands PT-package plans + instances with sale/cancel/refund flows
and an ARQ cron expirer. Architectural shape (modules-independent via
Protocol slots, append-only payments ledger, snapshot fields, partial
UNIQUE invariants, FSM guards) is sound.

The biggest concerns sit on the **HTTP idempotency layer** of the new
PT-package router. The router rolls its own two-phase pattern that
diverges from the project's `app.core.idempotency.idempotent_response`
helper in two material ways:

1. **No `Idempotency-Key` route binding.** Different routes (sale, cancel,
   refund) share the same Redis namespace `sz:idem:{key}` — the same key
   reused across endpoints can replay the wrong response. This is a
   correctness defect that contradicts the comment in router.py:346-349.
2. **No in-flight placeholder claim.** `begin_idempotency` is never
   called. Two concurrent requests with the same key can both pass the
   "no stored entry" check and both execute the orchestrator. For
   `/cancel` this causes a double mutation + double audit emit; for the
   sale path the DB partial UNIQUE catches the race, but the loser's 409
   is never cached so subsequent retries re-execute.

Additionally, the helper has `Redis` injected in `verify_idempotency` as
an unused parameter (`# noqa: ARG001`), strongly suggesting the original
design intent was to do the route+key binding inside the dependency —
the bind was never wired.

Other concerns: a silent empty-string fallback in the ARQ expire audit
emit, missing IntegrityError handling around the payment recorder call
in the sale orchestrator, and dead-code branches for `idempotency_in_flight`
across all three mutating endpoints.

## Critical Issues

### CR-01: Idempotency-Key collides across PT-package routes (data integrity)

**File:** `apps/backend/app/modules/pt_packages/router.py:243-294, 390-433, 493-538` and
`apps/backend/app/core/idempotency.py:35-79`

**Issue:** The Redis key derivation in `app.core.idempotency` is
`sz:idem:{Idempotency-Key header value}` — **the request route is NOT
part of the key** (see `_redis_key` at `idempotency.py:51-52` and
`verify_idempotency` at `idempotency.py:60-79`, which only validates the
header pattern and never inspects `request.url.path` / `request.method`).

The router comment at `router.py:346-349` is therefore **incorrect**:

> "Different routes (cancel vs refund) hash to distinct Redis keys
>  because the request method + URL path are part of the key derivation
>  in `verify_idempotency` — same key on different routes does NOT
>  collide (T-33-03-10 mitigation)."

Concrete failure: an operator calls `POST /pt-packages` with
`Idempotency-Key: abc123` and body `{"clientId":..., "planId":..., "amountKopecks":99000}`,
receives a 201 cached envelope. Later the same operator (or a retry
script) calls `POST /pt-packages/{id}/refund` with the **same** header
value `abc123`. If the bodies happen to hash equal (e.g., both empty
JSON during a misfire, or both `{}`), the operator gets the cached **sale
response** as if the refund had succeeded — silently masking a refund
failure with a fabricated sale envelope. Even when bodies differ, the
operator gets a confusing 422 `idempotency_key_reuse` on a fresh route.

The `Redis` argument is wired into `verify_idempotency` but unused
(`idempotency.py:62 # noqa: ARG001 — kept for parity / DI graph`),
which is a strong indicator that the route-binding step was planned but
never implemented.

**Fix:** Bind the route into the idempotency key derivation. Either:

```python
# Option A: bind in verify_idempotency
async def verify_idempotency(
    request: Request,
    redis: Annotated[Redis, Depends(get_redis)],  # noqa: ARG001
) -> str:
    key = request.headers.get("idempotency-key")
    if key is None or key == "":
        raise ValidationAppError("idempotency_key_required")
    if not _IDEMPOTENCY_KEY_RE.match(key):
        raise ValidationAppError("idempotency_key_invalid_format")
    # Bind route+method so the same client-supplied key cannot replay
    # across endpoints (D-32-19 / D-33-16 invariant).
    return f"{request.method}:{request.url.path}:{key}"
```

or rework `_redis_key` to accept a route tuple. Update Phase 32 callsites
(memberships sale/refund) for symmetry. Add a regression test asserting
that `POST /pt-packages` and `POST /pt-packages/{id}/refund` with the
same header value AND identical body hashes return distinct cached
envelopes.

---

### CR-02: Concurrent /cancel requests can double-mutate + double-audit

**File:** `apps/backend/app/modules/pt_packages/router.py:362-433` (cancel) and
`apps/backend/app/modules/pt_packages/service.py:702-789`

**Issue:** The cancel endpoint never claims the Idempotency-Key
placeholder before running the orchestrator. The router only calls
`load_idempotency_response` (read-only) and proceeds when it returns
`None`. With no `SET NX` claim, two concurrent requests carrying the
**same** Idempotency-Key both pass the "stored is None" check and both
enter `service.cancel_pt_package`.

Trace for two concurrent identical cancel requests on an active
PT-package:

1. T1 and T2 both `SELECT` `status='active'`, both pass
   `_assert_can_transition(target='cancelled')`.
2. T1 mutates `status='cancelled'`, `cancellation_reason=reason_T1`,
   flushes, emits `pt_package_cancelled` audit row, commits.
3. T2 (different DB transaction with REPEATABLE READ / READ COMMITTED?
   default is READ COMMITTED in asyncpg) — at flush time, T2 reads the
   row, sees `active` in its snapshot or sees `cancelled` after T1's
   commit. There is **no** `SELECT ... FOR UPDATE`, no `version_id_col`,
   no FSM check after the snapshot read. The mutation `pt_package.status
   = 'cancelled'` overwrites T1's row in T2's transaction; T2 emits a
   **second** `pt_package_cancelled` audit row with `cancellation_reason
   = reason_T2` and `prior_status='active'` (snapshot value, now wrong).
4. T2 commits — the surviving DB state has T2's `cancellation_reason`
   replacing T1's, and the audit log carries TWO `pt_package_cancelled`
   events for the same `pt_package_id`.

Sale (CR-02b): The DB partial UNIQUE `uq_pt_packages_active_per_client`
catches the duplicate-insert case for the sale path. The race-loser
raises `ActivePtPackageAlreadyExistsError` but that 409 is **never
cached**, so a third retry with the same key re-executes — defeating
the operator-UX guarantee of Idempotency-Key.

Refund: similar to cancel — `_assert_can_transition` is snapshot-bound,
so T2 may pass the FSM check on a stale 'active' read, then race with
T1 inside `get_payment_refunder()`. The DB partial UNIQUE
`uq_payments_refund_of_alive` saves the payment ledger from a double
insert (T1 wins with 200, T2 raises `AlreadyRefundedError` 409, which
again is never cached).

**Fix:** Use the existing helper that already implements claim + replay
correctly (`app.core.idempotency.idempotent_response`):

```python
# router.py:362 cancel_pt_package
async def cancel_pt_package(
    ...
    idempotency_key: Annotated[str, Depends(verify_idempotency)],
    redis: Annotated[Redis, Depends(get_redis)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    incoming_body = await request.body()
    cached = await idempotent_response(redis, idempotency_key, incoming_body)
    if cached is not None:
        return Response(
            content=base64.b64decode(cached["body_b64"]),
            status_code=cached["status_code"],
            media_type="application/json",
        )
    # cached is None ⇒ we own the in-flight placeholder.
    pt_package = await service.cancel_pt_package(session, actor, pt_package_id, payload)
    body_bytes = json.dumps(
        envelope(pt_package).model_dump(mode="json", by_alias=True),
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    await store_idempotency_response(
        redis, idempotency_key,
        status_code=status.HTTP_200_OK,
        body_bytes=body_bytes,
    )
    return Response(content=body_bytes, status_code=status.HTTP_200_OK, media_type="application/json")
```

Replicate across `create_pt_package` and `refund_pt_package` (and audit
the Phase 32 memberships sale/refund for the same gap). Add a
regression test: two concurrent identical `/cancel` requests against an
active PT-package must produce exactly ONE successful response and ONE
`pt_package_cancelled` audit row.

---

### CR-03: Comment falsely asserts route-aware Idempotency-Key isolation

**File:** `apps/backend/app/modules/pt_packages/router.py:340-349`

**Issue:** The block comment claims:

> "Different routes (cancel vs refund) hash to distinct Redis keys
>  because the request method + URL path are part of the key derivation
>  in `verify_idempotency` — same key on different routes does NOT
>  collide (T-33-03-10 mitigation)."

This is contradicted by the actual implementation (CR-01). The lie in
the comment masks the data-integrity bug from reviewers and from
operators reading the source. **This is classified Critical because
removing the false claim is required to expose CR-01 and CR-02 for
remediation.**

**Fix:** Either (preferred) implement the route binding described by the
comment, or delete the misleading sentences and acknowledge the limit:

```python
# T-33-03-10 NOTE: The Redis namespace `sz:idem:{key}` is currently
# bound ONLY to the header value — NOT the route. Operators MUST use
# distinct Idempotency-Key values across the 3 mutating PT-package
# endpoints (sale, cancel, refund) until route-aware binding lands.
```

---

## Warnings

### WR-01: Dead-code branch — `idempotency_in_flight` is unreachable

**File:** `apps/backend/app/modules/pt_packages/router.py:252-254, 397-398, 499-500`

**Issue:** All three mutating endpoints check
`if isinstance(stored, str): raise ConflictError("idempotency_in_flight")`.
The placeholder string is only written by `begin_idempotency` (which is
never called in this module). As long as the router uses the manual
two-phase pattern without a NX claim, `load_idempotency_response` can
never return the `_PLACEHOLDER` sentinel and this branch is dead code.

This is more than a stylistic dead-branch warning: the dead branch
suggests the author *intended* to use the placeholder pattern but only
wired half of it (the consumer side, not the producer side). Fixing
CR-02 will make the branch live.

**Fix:** Implementing CR-02 makes the branch reachable. Until then, add
a TODO above each occurrence or remove the dead arm.

---

### WR-02: ARQ expire audit emits empty `end_date` on defensive fallback

**File:** `apps/backend/app/modules/pt_packages/service.py:677-693`

**Issue:** The bulk-expire loop emits `pt_package_expired` audit rows
with:

```python
end_iso = row_end_date.isoformat() if isinstance(row_end_date, date) else ""
```

If the defensive `isinstance` ever evaluates false, the audit emit
proceeds with `end_date=""`. `PtPackageExpiredPayload.end_date: str` has
**no format pattern**, so an empty string passes Pydantic validation and
lands in JSONB silently. The "should never happen" branch then becomes
a silent corruption vector for downstream audit consumers (BI, REF-07
chain, future PT-21 callsite).

The SQL filter `end_date IS NOT NULL` should make this branch
unreachable, but the safer pattern is to raise on the invariant
violation so it surfaces loudly.

**Fix:**

```python
for row in rows:
    pt_package_id, client_id, row_end_date = row
    if row_end_date is None:
        # Invariant: repository SQL filters end_date IS NOT NULL.
        # If this fires, the SQL predicate has regressed.
        raise RuntimeError(
            f"expire cron returned NULL end_date for pt_package {pt_package_id}; "
            "expire_due_pt_packages_bulk_returning SQL filter has regressed"
        )
    await audit.emit(
        session,
        "pt_package_expired",
        actor_user_id=None,
        resource_type="pt_package",
        resource_id=pt_package_id,
        pt_package_id=str(pt_package_id),
        client_id=str(client_id),
        end_date=row_end_date.isoformat(),
    )
```

Also consider tightening `PtPackageExpiredPayload.end_date` to a
`pattern=r"^\d{4}-\d{2}-\d{2}$"` or `date` type, mirroring
`PtPackageSoldPayload.end_date: date | None`.

---

### WR-03: `record_payment` IntegrityError not caught in sale orchestrator

**File:** `apps/backend/app/modules/pt_packages/service.py:553-561` and
`apps/backend/app/modules/payments/service.py:107-117`

**Issue:** `record_payment` calls `await session.flush()` (payments
service line 117) **without** a try/except. If the payment INSERT fails
(e.g., FK violation on `received_by_user_id` for a soft-deleted user,
CHECK violation on `amount_kopecks`, partial UNIQUE on
`uq_payments_refund_of_alive` for a refund — though that one is in
`issue_refund` not `record_payment`), an `IntegrityError` propagates
out of `record_payment` with the SA session in a failed state.

The orchestrator (`create_pt_package`) catches `IntegrityError` only
around the **earlier** `repository.insert_pt_package` flush
(`service.py:538-546`). The later `get_payment_recorder()(...)` call at
line 553 is **not** wrapped, so an IntegrityError from the payment
insert escapes uncaught:

1. SA session is now in failed-transaction state.
2. The audit emit at line 574 will fail (session unusable).
3. The orchestrator's `await session.commit()` at line 597 will fail.
4. The pt_packages row inserted at step 5 is rolled back when the
   session context exits — semantically correct, but no typed error is
   surfaced to the caller and no audit row records the attempted sale.

This is a robustness defect rather than a security/data-loss bug
(rollback DOES happen), but the operator UX is a generic 500 instead of
a typed `payment_recording_failed` 409 / 422.

**Fix:** Either explicitly catch `IntegrityError` around the recorder
call and translate to a typed conflict, or harden `record_payment`
itself to catch + rollback + translate. Mirror the pattern already in
place at `service.py:538-546`:

```python
try:
    payment = await get_payment_recorder()(
        session,
        subject_kind=PAYMENT_SUBJECT_KIND_PT_PACKAGE,
        subject_id=pt_package.id,
        amount_kopecks=pt_package.price_kopecks_snapshot,
        method="cash",
        received_by_user_id=actor.id,
        audit_actor=actor,
    )
except IntegrityError as exc:
    await session.rollback()
    # Typed error or re-raise as a service-layer ConflictError.
    raise
```

Audit the membership sale path (Phase 32) for the same shape.

---

### WR-04: `session.refresh(pt_package)` after commit reloads ALL columns

**File:** `apps/backend/app/modules/pt_packages/service.py:600`

**Issue:** After the sale orchestrator's `await session.commit()` at
line 597, the code issues `await session.refresh(pt_package)` with no
`attribute_names=` filter. With SA 2.0 async defaults
(`expire_on_commit=True`), this triggers a full re-SELECT of all
columns of the freshly-committed row.

The cancel and refund orchestrators at lines 783 and 898 use the
narrower `session.refresh(pt_package, attribute_names=["updated_at"])`
form. The inconsistency is small but real — the unscoped refresh in
`create_pt_package` is the outlier and risks accidentally lazy-loading
any future relationship attribute defined on `PtPackage` (e.g., when
Phase 34 adds a `sessions` collection).

**Fix:** Tighten to the same narrow form:

```python
await session.refresh(pt_package, attribute_names=["updated_at", "created_at"])
```

or whatever response fields the orchestrator needs post-commit.

---

### WR-05: 422 status path on idempotency body mismatch when stored response is 201/200

**File:** `apps/backend/app/modules/pt_packages/router.py:251-262, 395-405, 497-507`

**Issue:** When `stored["body_hash"] != incoming_hash`, the router
raises `ValidationAppError("idempotency_key_reuse")` (422). This is the
correct semantic, but combined with CR-01 (no route binding), it means:

- Operator calls `POST /pt-packages` with `Idempotency-Key=K1` → 201
  cached.
- Operator calls `POST /pt-packages/{id}/cancel` with the **same** key
  `K1` and a non-matching body hash → 422
  `idempotency_key_reuse`.

The 422 is confusing because the operator is on a fresh route. Fixing
CR-01 (route-bound keys) resolves this UX issue. Until that lands, the
error message should at least mention "Idempotency-Key already used on
a different operation in the last hour" rather than the bare reuse
code.

**Fix:** Bundled with CR-01.

---

### WR-06: `find_active_for_client` resolver does not check `end_date`

**File:** `apps/backend/app/modules/pt_packages/repository.py:186-212` and
`apps/backend/app/modules/pt_packages/service.py:439-449`

**Issue:** The `ActivePtPackage` Protocol resolver returns the first
row with `status='active'`, ordered by `created_at DESC`. It does NOT
filter `end_date >= today`. Between the package's `end_date` and the
next cron tick at 06:25 MSK (worst case ~30 hours), a row will be
returned as "active" even though its validity window has elapsed.

Phase 34's PT-session decrement will be the first consumer of this
resolver. If it treats the return value as "definitely live", it will
record a PT-session against an effectively-expired package. The cron
will subsequently flip it to `expired`, leaving the recorded session
on an expired package — semantically wrong.

The class docstring at `dependencies.py:141-155` lists `end_date` in
the Protocol — Phase 34 has the data it needs to refilter, but the
resolver itself should not pretend the row is alive.

**Fix:** Either filter `end_date >= today OR end_date IS NULL` in
`find_active_for_client`, or document loudly that consumers MUST
recheck `end_date` before treating the row as live. Add a unit test:
package with `end_date = yesterday` and status still `active` (cron
not yet run) — resolver should either return None or the consumer
docstring contract must mandate a recheck.

---

## Info

### IN-01: Idempotency envelope produced via manual `redis.set` instead of helper

**File:** `apps/backend/app/modules/pt_packages/router.py:271-289, 408-428, 510-533`

**Issue:** All three endpoints inline the envelope construction +
base64 encoding + `redis.set` call instead of using
`store_idempotency_response` from `app.core.idempotency`. This
duplicates code, drifts the envelope shape, and (combined with CR-02)
contributes to the missing claim/replay discipline.

**Fix:** Refactor to use `idempotent_response` + `store_idempotency_response`
as shown in CR-02's fix block.

---

### IN-02: `await request.body()` called after FastAPI body parsing

**File:** `apps/backend/app/modules/pt_packages/router.py:244, 390, 493`

**Issue:** FastAPI has already parsed the body into the typed `payload`
parameter before the handler runs. Calling `await request.body()` again
returns the cached bytes (Starlette caches), so this works, but the
pattern is non-obvious. The body bytes are then re-hashed for
idempotency. Acceptable, but the project could canonicalise the JSON
encoding of `payload` instead to make the hash independent of
client-side whitespace.

**Fix:** Document the pattern explicitly OR hash the canonical encoding
of `payload.model_dump(mode="json", by_alias=True)` so two clients with
semantically-identical bodies but different whitespace get the same
hash.

---

### IN-03: Defensive constraint-name fallback uses substring match

**File:** `apps/backend/app/modules/pt_packages/service.py:153-176` and
`apps/backend/app/modules/payments/repository.py:52-62`

**Issue:** Both discriminators check
`getattr(exc.orig, "constraint_name", None)` and fall back to
`"<name>" in str(exc.orig)`. The substring fallback could match a
constraint whose name shares a prefix/suffix (e.g., a future
`uq_pt_packages_active_per_client_v2`). asyncpg reliably exposes
`constraint_name`; the fallback is a v0 belt-and-braces left over from
the membership precedent.

**Fix:** Either drop the fallback and rely on `constraint_name`
exclusively, or anchor the substring with word boundaries.

---

### IN-04: `_validate_immutability` does not validate `name` value

**File:** `apps/backend/app/modules/pt_packages/schemas.py:85-118` and
`apps/backend/app/modules/pt_packages/service.py:226-249`

**Issue:** The schema admits `validity_days` on PATCH for the
immutability gate, but if the operator sends `{"validityDays": null}`,
the `_reject_explicit_null` validator (schemas.py:103) rejects with a
generic `ValueError` → 422. For the three immutable fields, this means
`null` produces a 422 (schema layer) while a non-matching int produces
a 409 `field_immutable` (service layer). Asymmetric error codes for
"don't try to change this" is a minor UX inconsistency.

**Fix:** Decide on one error code (probably 409 `field_immutable`) for
all attempts to mutate immutable fields, regardless of whether the
attempt uses `null` or a non-matching value.

---

### IN-05: `PAYMENT_SUBJECT_KIND_PT_PACKAGE` literal duplicated

**File:** `apps/backend/app/modules/pt_packages/constants.py:23-51` and
`apps/backend/app/modules/payments/constants.py` (referenced)

**Issue:** `pt_packages.constants.PAYMENT_SUBJECT_KIND_PT_PACKAGE` and
`payments.constants.SUBJECT_KIND_PT_PACKAGE` are sibling literals that
MUST stay byte-equal. The docstring documents this and points at the
migration as the canonical source. If either drifts, the partial
UNIQUE + CHECK constraint will reject the insert at runtime — caught,
but the path is a runtime error rather than a CI failure.

**Fix:** Add a unit test that asserts the two literals are equal AND
that both match the migration CHECK literal `'pt_package'`. The
modules-independent contract allows a *test* to import both modules.

---

_Reviewed: 2026-05-15_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
