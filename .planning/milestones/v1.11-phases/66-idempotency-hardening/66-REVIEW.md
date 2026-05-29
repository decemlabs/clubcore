---
phase: 66-idempotency-hardening
reviewed: 2026-05-29T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - apps/backend/app/core/idempotency.py
  - apps/backend/app/main.py
  - apps/backend/app/modules/memberships/router.py
  - apps/backend/app/modules/online_payments/router.py
  - apps/backend/app/modules/pt_packages/router.py
  - apps/backend/app/modules/pt_sessions/router.py
  - apps/backend/app/modules/bookings/router.py
  - apps/backend/app/modules/schedule/router.py
  - apps/backend/app/api/v1/_internal/yookassa/router.py
findings:
  critical: 1
  warning: 4
  info: 2
  total: 7
status: issues_found
---

# Phase 66: Code Review Report

**Reviewed:** 2026-05-29
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Phase 66 hardens the per-route Idempotency-Key flow: user-scoped Redis keys
(`cc:idem:{user_id}:{method}:{path}:{header}`), a shared exception-aware
orchestrator (`idempotent_execute`) with AppError-replay and unknown-exception
cleanup branches, and an OpenAPI parameter-injection pass. The orchestrator
itself is correct: the AppError branch stores a replayable error envelope keyed
on the REQUEST body hash (preserving the same-key/different-body 422 invariant),
the unknown-exception branch deletes the placeholder, the success path commits
(inside the runner) before storing the envelope, and verbatim replay
(status + body + `application/json`) is byte-identical to the live AppError
handler output. User-scoping has no bypass path, and the ЮKassa webhook is
correctly left off `verify_idempotency` (it keeps its own `cc:yookassa:webhook:`
dedup). The `CATEGORY_A_OPERATION_IDS` set in `main.py` exactly matches the 22
handlers actually carrying `Depends(verify_idempotency)` — no OpenAPI drift —
and RBAC-04 ordering (auth → permission → csrf → idempotency) is preserved on
every newly-wired endpoint.

The phase's central goal — eliminate the 24h placeholder-wedge on failure — is
defeated on ONE endpoint that was never migrated to the orchestrator:
`create_time_off` still uses the legacy inline block and only catches
`TimeOffBookedConflictError`. Other exceptions it can raise
(`TrainerNotFoundError`, `InternalConsistencyError`) leak the in-flight
placeholder, re-introducing exactly the wedge IDM-06 was built to remove.

## Critical Issues

### CR-01: `create_time_off` leaks the in-flight placeholder on non-conflict errors — 24h key wedge

**File:** `apps/backend/app/modules/schedule/router.py:375-460`
**Issue:**
`create_time_off` is the only category-A endpoint NOT migrated to
`idempotent_execute`. It claims the placeholder via `begin_idempotency` (line
378) and wraps the service call in a `try` that catches ONLY
`service.TimeOffBookedConflictError` (line 393). But `service.create_time_off`
also raises:
- `TrainerNotFoundError` (a `NotFoundError`/`AppError`, 404) — `app/modules/schedule/service.py:866`
- `InternalConsistencyError` (an `AppError`, 500) — `app/modules/schedule/service.py:959`

When either fires, the `except TimeOffBookedConflictError` does not match, the
exception propagates, and the `__in_flight__` placeholder set at line 378 is
NEVER replaced or deleted. It survives for the full `IDEMPOTENCY_TTL_SECONDS`
(86400s / 24h). A retry with the same Idempotency-Key — even after the operator
fixes the request (e.g. supplies a valid trainer) — reads the placeholder and
gets `409 idempotency_in_flight` for 24 hours, despite no mutation having
occurred. This is precisely the failure mode that IDM-06's unknown-exception
cleanup branch and AppError-replay branch were designed to eliminate everywhere
else; this endpoint silently regresses it.

The endpoint is also inconsistent with the locked phase contract — every other
mutating route delegates to `idempotent_execute`; this one duplicates a ~70-line
inline block that the phase set out to retire.

**Fix:** Migrate `create_time_off` to `idempotent_execute` like its siblings.
The only special case is that the `TimeOffBookedConflictError` 409 carries a
`data` field, which the generic AppError handler does not. Build that richer
409 body inside the runner and return it as a normal success-shaped tuple
(status 409, serialized body) so the orchestrator stores a replayable envelope,
OR keep the typed-conflict body but route ALL other exceptions through the
orchestrator's cleanup. Minimal correct form:

```python
incoming_body = await request.body()

async def _runner() -> tuple[int, bytes]:
    try:
        time_off = await service.create_time_off(session, actor, payload, force=force)
    except service.TimeOffBookedConflictError as exc:
        exc_fields: dict[str, object] = exc.fields or {}
        raw_slot_ids = cast(list[str], exc_fields.get("conflicting_slot_ids") or [])
        raw_booking_ids = cast(list[str], exc_fields.get("conflicting_booking_ids") or [])
        conflict_detail = TimeOffConflictDetail(
            conflicting_slot_ids=[UUID(s) for s in raw_slot_ids],
            conflicting_booking_ids=[UUID(s) for s in raw_booking_ids],
        )
        body = json.dumps(
            {"code": exc.code, "message": exc.message, "fields": exc.fields,
             "data": conflict_detail.model_dump(mode="json", by_alias=True)},
            separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")
        return 409, body
    body_bytes = json.dumps(
        envelope(time_off).model_dump(mode="json", by_alias=True),
        separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    return status.HTTP_201_CREATED, body_bytes

return await idempotent_execute(redis, idempotency_key, incoming_body, runner=_runner)
```

Now `TrainerNotFoundError` / `InternalConsistencyError` hit the orchestrator's
`except AppError` (replayable error envelope) / `except Exception`
(placeholder deleted) branches, and the wedge is closed. After the migration,
the now-unused imports (`base64`, `ConflictError`, `begin_idempotency`,
`body_sha256`, `load_idempotency_response`, `IDEMPOTENCY_REDIS_PREFIX`,
`IDEMPOTENCY_TTL_SECONDS`) should be dropped from `schedule/router.py`.

## Warnings

### WR-01: Placeholder leaks if the success-envelope `redis.set` fails after the DB commit

**File:** `apps/backend/app/core/idempotency.py:328-340`
**Issue:**
On the success path the runner has already committed the DB transaction (commit
happens inside `service.*`). The subsequent `await redis.set(...)` that replaces
the placeholder with the success envelope (lines 336-340) is OUTSIDE the
`try/except`. If Redis raises here (connection drop, timeout), the exception
propagates uncaught: the placeholder stays, the response is lost, and a retry
with the same key gets `409 idempotency_in_flight` for the full TTL even though
the mutation already succeeded. Same wedge class as CR-01, narrower trigger.
**Fix:** Wrap the success-store in a defensive guard so a Redis store failure
deletes the placeholder (so the key is reclaimable) before re-raising, or treat
store-failure as best-effort and still return the response (the DB write is the
source of truth). At minimum, document the chosen trade-off — silently wedging
on Redis hiccup is the worst of the options.

### WR-02: Key-segment ambiguity between `path` and `header` could collide for string path params

**File:** `apps/backend/app/core/idempotency.py:107`
**Issue:**
The user-scoped key is `f"{current_user.id}:{request.method}:{request.url.path}:{key}"`,
and the header value pattern `[A-Za-z0-9_:-]{16,128}` permits colons. Because
the separator is also `:`, two different `(path, header)` pairs can serialize to
the same string in principle — e.g. path `/a` + header `b:cccc...` vs path `/a:b`
+ header `cccc...`. Today every path param is a UUID (colon-free), so this is
not reachable, but the invariant is implicit, not enforced. A future route with
a string/slug path param would silently enable cross-request key collision (and
thus an incorrect replay across two distinct requests).
**Fix:** Use an unambiguous join that cannot appear in any segment — e.g. hash
the tuple components, or length-prefix / use a delimiter excluded from both the
path charset and the header charset (the header charset already excludes most
characters; pick one of those, e.g. `|`). Add a unit test asserting two crafted
`(path, header)` pairs that share a colon boundary produce distinct keys.

### WR-03: `verify_idempotency` declares a `redis` dependency it never uses

**File:** `apps/backend/app/core/idempotency.py:73-107`
**Issue:**
The `redis: Annotated[Redis, Depends(get_redis)]` parameter is bound but never
referenced in the function body. The docstring claims it "seeds the dep graph,"
but every wired handler already declares its own `redis: Depends(get_redis)`,
so this adds nothing and is dead within the function. It is a maintenance trap:
a reader may assume the dependency is load-bearing. (ruff would normally flag an
unused arg, but FastAPI Depends params are conventionally exempt, so this can
slip through.)
**Fix:** Drop the unused `redis` parameter from `verify_idempotency`. The
function only needs `request` and `current_user`.

### WR-04: `create_time_off` stored 409 envelope diverges from the generic AppError handler shape

**File:** `apps/backend/app/modules/schedule/router.py:406-434`
**Issue:**
The inline block builds the conflict body as `{code, message, fields, data}` and
stores it. The application-wide `_app_error_handler`
(`app/core/exceptions.py:442-450`) emits `{code, message, fields}` with no
`data` key for any `AppError`. So the FIRST `time_off_booked_conflict` response
(and its replay) carries a `data` field that no other 409 in the system carries,
and that the OpenAPI `409_Conflict` component does not model. This is an
undocumented response-shape divergence on a single endpoint. (It is internally
self-consistent — first response and replay match — so it is a contract/quality
issue, not a correctness break.)
**Fix:** Decide whether `time_off_booked_conflict` is a documented richer 409
(then model the `data` field in the spec and note the exception) or fold the
conflict detail into `fields` to match every other 409. Resolving this alongside
CR-01's migration is natural.

## Info

### IN-01: `idempotent_response` is dead code

**File:** `apps/backend/app/core/idempotency.py:182-216, 356`
**Issue:**
`idempotent_response` is defined and exported in `__all__` but has zero callers
(`grep` confirms only the definition and the `__all__` entry). It is superseded
by `idempotent_execute`. Keeping a second, subtly different
claim/replay helper invites a future caller picking the wrong one (it lacks the
exception-aware store/cleanup branches that make `idempotent_execute` safe).
**Fix:** Remove `idempotent_response` and its `__all__` entry, or document it as
deprecated. Prefer removal — the phase's stated contract is that "all wired
callsites MUST use `idempotent_execute`."

### IN-02: Repeated inline envelope-serialization boilerplate across all runners

**File:** `apps/backend/app/modules/memberships/router.py:322-329` (and ~14 sibling runners across the 6 routers)
**Issue:**
Every `_runner` repeats the identical
`json.dumps(envelope(x).model_dump(mode="json", by_alias=True), separators=(",", ":"), ensure_ascii=False).encode("utf-8")`
incantation. The separators / `ensure_ascii` / encoding must stay byte-aligned
with the verbatim-replay contract and with the AppError handler's Starlette
serialization; a single drifted callsite would produce a replay that differs
from a fresh response. The duplication makes that invariant fragile.
**Fix:** Extract a small helper (e.g. `serialize_envelope(payload) -> bytes`) in
`app/core/idempotency.py` or `app/core/schemas.py` and call it from every runner,
so the serialization contract lives in one place.

---

_Reviewed: 2026-05-29_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
