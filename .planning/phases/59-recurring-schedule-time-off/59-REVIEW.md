---
phase: 59-recurring-schedule-time-off
reviewed: 2026-05-25T00:00:00Z
depth: standard
files_reviewed: 18
files_reviewed_list:
  - apps/backend/alembic/versions/0042_recurring_schedule_time_off.py
  - apps/backend/app/api/v1/router.py
  - apps/backend/app/core/audit.py
  - apps/backend/app/core/audit_payloads.py
  - apps/backend/app/core/config.py
  - apps/backend/app/modules/schedule/constants.py
  - apps/backend/app/modules/schedule/models.py
  - apps/backend/app/modules/schedule/repository.py
  - apps/backend/app/modules/schedule/router.py
  - apps/backend/app/modules/schedule/schemas.py
  - apps/backend/app/modules/schedule/service.py
  - apps/backend/app/workers/__init__.py
  - apps/backend/app/workers/scheduled/generate_recurring_slots.py
  - apps/backend/tests/integration/schedule/test_generate_recurring_slots.py
  - apps/backend/tests/integration/schedule/test_recurring_templates.py
  - apps/backend/tests/integration/schedule/test_time_off.py
  - apps/backend/tests/unit/test_audit_taxonomy.py
  - apps/backend/tests/unit/workers/test_worker_settings.py
findings:
  critical: 1
  warning: 6
  info: 3
  total: 10
status: issues_found
---

# Phase 59: Code Review Report

**Reviewed:** 2026-05-25T00:00:00Z
**Depth:** standard
**Files Reviewed:** 18
**Status:** issues_found

## Summary

Phase 59 (REC-01..04) adds recurring-slot templates, a daily materialization cron, and trainer time-off blocks. The core DST handling (`_expand_template_occurrences` via `ZoneInfo("Europe/Moscow")` + `.astimezone(UTC)`) is correct, the cron idempotency gate (`ON CONFLICT (trainer_id, start_time) DO NOTHING` + RETURNING-driven audit) is sound, the `slot_published` cron emit correctly tolerates `created_by_user_id=None`, and RBAC reuses existing `SCHEDULE_SLOTS` pairs with no new `OWNER_ONLY` entries. The cross-module bookings UPDATE in the force-cascade is raw `sa.text()` with the correct `# noqa` markers and the 0-row `InternalConsistencyError` guard, all inside a single UoW.

The dominant defect is a broken idempotency contract on the `POST /time-off` 409 conflict path: the in-flight Redis claim is never replaced with a replayable envelope, so a legitimate retry of the same key is wedged into `idempotency_in_flight` for the full TTL. Several WARNING-level issues concern audit-payload schema gaps, a missing trainer-existence guard producing raw 500s, and documentation drift.

## Critical Issues

### CR-01: `POST /time-off` 409 conflict path leaks the in-flight idempotency claim (key wedged for full TTL)

**File:** `apps/backend/app/modules/schedule/router.py:504-527`
**Issue:** `create_time_off` calls `begin_idempotency(redis, key)` (line 491), which SETs the `__in_flight__` placeholder with `nx=True` and a 3600s TTL. When the service raises `TimeOffBookedConflictError`, the handler returns a `JSONResponse` (line 519) **without ever calling `redis.set(...)`** to replace the placeholder with a replayable envelope (contrast the success path, lines 544-548, which does store one).

The placeholder therefore survives. A legitimate client retry of the **same** Idempotency-Key (the normal way a client re-issues a request after a transient 409, or after a network blip on the original 409 response) re-enters the handler, hits `is_first == False` (line 492), `load_idempotency_response` returns the `__in_flight__` sentinel string, and the handler raises `ConflictError("idempotency_in_flight")` (line 495). The client is now locked out of that key for up to one hour even though no mutation ever occurred. This breaks the D-38-14 / Pitfall-14 idempotency contract for the entire booked-conflict branch and is the *only* documented business outcome of the endpoint besides 201.

Note the same latent shape exists on any *raised* (non-returned) error in the other mutation handlers, but those propagate to the global handler and are arguably acceptable for true error states; here the 409 is a *returned* terminal business response that the contract says must be replayable, so it must persist an envelope.

**Fix:** Store the 409 response in Redis before returning it, mirroring the success path:
```python
except service.TimeOffBookedConflictError as exc:
    from typing import cast as _cast
    exc_fields: dict[str, object] = exc.fields or {}
    raw_slot_ids = _cast(list[str], exc_fields.get("conflicting_slot_ids") or [])
    raw_booking_ids = _cast(list[str], exc_fields.get("conflicting_booking_ids") or [])
    conflict_detail = TimeOffConflictDetail(
        conflicting_slot_ids=[UUID(s) for s in raw_slot_ids],
        conflicting_booking_ids=[UUID(s) for s in raw_booking_ids],
    )
    conflict_body = {
        "code": exc.code,
        "message": exc.message,
        "fields": exc.fields,
        "data": conflict_detail.model_dump(mode="json", by_alias=True),
    }
    body_bytes = json.dumps(conflict_body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    envelope_json = json.dumps(
        {"status_code": 409, "body_hash": incoming_hash,
         "body_b64": base64.b64encode(body_bytes).decode("ascii")},
        separators=(",", ":"), ensure_ascii=False,
    )
    await redis.set(f"{IDEMPOTENCY_REDIS_PREFIX}{idempotency_key}", envelope_json, ex=IDEMPOTENCY_TTL_SECONDS)
    return Response(content=body_bytes, status_code=409, media_type="application/json")
```
(Alternatively, on the conflict branch explicitly `redis.delete(...)` the in-flight key so the retry is allowed to re-run — but persisting a replayable 409 is the contract-faithful choice.)

## Warnings

### WR-01: Phase 59 audit events have no registered payload schema — `extra="forbid"` is silently NOT enforced

**File:** `apps/backend/app/core/audit_payloads.py:1146-1223` (registry) / `apps/backend/app/core/audit.py:558-560`
**Issue:** The four new locked pairs (`recurring_slot_template_created`, `recurring_slot_template_cancelled`, `trainer_time_off_created`, `trainer_time_off_cancelled`) are added to `LOCKED_AUDIT_EVENTS` but have **no entry** in `AUDIT_PAYLOAD_SCHEMAS`. In `audit.emit`, `schema = AUDIT_PAYLOAD_SCHEMAS.get((event, resource_type))` returns `None`, so the `extra="forbid"` validation branch is skipped entirely. The phase-context invariant "payloads match audit_payloads.py schemas with `extra="forbid"`" is therefore unmet for every new Phase 59 event. A typo'd or drifting payload key (e.g. the `force_cascade`/`cancelled_slot_count` keys the audit.py docstring claims vs. the `block_start`/`block_end`/`reason` the service actually emits) will land silently in JSONB rather than hard-failing.
**Fix:** Add four Pydantic payload schemas (`RecurringSlotTemplateCreatedPayload`, `RecurringSlotTemplateCancelledPayload`, `TrainerTimeOffCreatedPayload`, `TrainerTimeOffCancelledPayload`, each `extra="forbid"`) matching the exact emit kwargs in `service.py`, and register them in `AUDIT_PAYLOAD_SCHEMAS`. Add a `test_audit_taxonomy`-style assertion that every Phase 59 locked pair has a registered schema.

### WR-02: `trainer_time_off_created` audit docstring contradicts the actual emitted payload

**File:** `apps/backend/app/core/audit.py:228-233` vs `apps/backend/app/modules/schedule/service.py:1022-1033`
**Issue:** The `audit.py` event catalog documents `trainer_time_off_created` as carrying `{time_off_id, trainer_id, block_start, block_end, reason, force_cascade, cancelled_slot_count, cancelled_booking_count}`. The service emits only `{time_off_id, trainer_id, block_start, block_end, reason}` — `force_cascade`, `cancelled_slot_count`, `cancelled_booking_count` are absent. Because there is no registered payload schema (WR-01), this drift is not caught at runtime. The forensic value the docstring promises (how many slots/bookings the time-off cascade cancelled, whether `?force` was used) is not actually recorded.
**Fix:** Decide the canonical shape and make both sides agree. Recommended: emit `force_cascade=force`, `cancelled_slot_count=len(active_slot_ids) + len(cascaded_booking_ids)` (or the precise count), and `cancelled_booking_count=len(cascaded_booking_ids)` so the cascade scope is auditable; then encode the same fields in the new `extra="forbid"` schema from WR-01.

### WR-03: `create_recurring_template` / `create_time_off` raise opaque 500 on a non-existent `trainer_id`

**File:** `apps/backend/app/modules/schedule/service.py:705-735` and `:828-1019`
**Issue:** Unlike `publish_slot` (which resolves the trainer via `resolve_trainer_by_id` and returns a clean `404 trainer_not_found` / `409 trainer_inactive`), neither `create_recurring_template` nor `create_time_off` validates the `trainer_id` from the request body. A bad `trainer_id` survives Pydantic (it is a well-formed UUID), then fails the FK `fk_recurring_slot_templates_trainer_id_trainers` / `fk_trainer_time_off_trainer_id_trainers` at flush. `insert_recurring_template` only catches the *unique-constraint* `IntegrityError` (it inspects `"uq_recurring_slot_templates_trainer_id" in str(exc.orig)`) and re-raises everything else — so the FK violation propagates as an unhandled `IntegrityError` → HTTP 500. `create_time_off` has no try/except at all around the insert. Owner-only endpoints, so not a security hole, but a poor/ambiguous error surface and an inconsistency with the sibling `publish_slot` contract.
**Fix:** Resolve the trainer up-front in both functions (`trainer = await resolve_trainer_by_id(session, data.trainer_id)`; raise `TrainerNotFoundError` on None) before any INSERT, matching `publish_slot`. Optionally also reject `trainer.is_active is False` for `create_recurring_template`.

### WR-04: `RecurringTemplateDuplicateError` detection relies on substring match against the index name in the driver error text

**File:** `apps/backend/app/modules/schedule/repository.py:330-335`
**Issue:** `insert_recurring_template` distinguishes the expected UNIQUE violation from any other `IntegrityError` via `if "uq_recurring_slot_templates_trainer_id" in str(exc.orig)`. This is fragile: it depends on asyncpg/SQLAlchemy embedding the *index name* in `str(exc.orig)` verbatim. If the driver message format changes, or the violated constraint name is ever renamed, the branch silently flips — either masking a different IntegrityError as a duplicate (returning `None` → wrong 409) or re-raising the real duplicate as a 500. Note the index is created as a plain `unique=True` `Index` (`uq_...`), not a named `UniqueConstraint`, so the diagnostic surface is the index name specifically.
**Fix:** Prefer inspecting `exc.orig.__cause__.constraint_name` (asyncpg exposes `UniqueViolationError.constraint_name`) or match on `sqlstate == '23505'` plus the constraint name, rather than a substring of the rendered message. At minimum, add a regression test that asserts a duplicate insert produces exactly this code path.

### WR-05: `list_active_time_off_for_trainers` is misnamed — it does not filter to "active" blocks

**File:** `apps/backend/app/modules/schedule/repository.py:489-505`
**Issue:** The helper is named `list_active_time_off_for_trainers` and the cron docstring (service.py:1272-1281) refers to "active trainer_time_off window," but the query has no temporal/active predicate at all — it returns **every** time-off row for the given trainers, including blocks entirely in the past. The downstream Python overlap filter (`block_start < row_end and block_end > row_start`) makes the result *correct* (past blocks cannot overlap future cron candidates), so this is not a correctness bug, but the name actively misleads a future maintainer into believing a not-present filter exists, and pulls unbounded historical rows into memory as the table grows.
**Fix:** Either rename to `list_time_off_for_trainers` (truthful) or add the intended predicate `WHERE block_end > :now` and pass `now` through from the cron helper so the fetch is actually bounded to forward-relevant blocks.

### WR-06: Force-cascade cancels the booking but never restores the PT-package session credit

**File:** `apps/backend/app/modules/schedule/service.py:922-949`
**Issue:** The `?force=true` cascade flips the confirmed booking to `cancelled` via a raw `UPDATE bookings ... WHERE status='confirmed'` but does nothing to the `pt_packages` row whose session was decremented when the booking was created. An owner-initiated cancellation that consumed a client's prepaid session should normally credit the session back (the booking never happened — the trainer took time off). As written, the client silently loses a paid PT session. The sibling `cancel_slot` booked-cascade (service.py:471-504) has the identical omission, so this is a pre-existing pattern rather than a Phase-59-introduced regression — but Phase 59 newly reaches it from a *bulk* time-off path, multiplying the blast radius (one time-off block can burn N clients' sessions), which warrants an explicit decision.
**Fix:** Confirm the intended business rule. If sessions must be restored on owner-driven cancellation, add the cross-module `UPDATE pt_packages SET sessions_remaining = sessions_remaining + 1 ...` (raw `sa.text()` per D-38-11) inside the same UoW, and emit/adjust the corresponding audit. If the loss is intentional, document it explicitly at the callsite so it is not read as an oversight.

## Info

### IN-01: Cron time-off skip has a TOCTOU window (accepted for a daily cron)

**File:** `apps/backend/app/modules/schedule/service.py:1272-1311`
**Issue:** The time-off skip pre-fetches all blocks then filters candidates in Python before the bulk INSERT, so a time-off block created between the fetch and the INSERT will not exclude already-materialized slots. The phase context explicitly accepts this for a once-daily cron, and `create_time_off` independently cancels overlapping active slots, so a slot that slips through is cleaned up by the next time-off mutation. No fix required; recorded for traceability.

### IN-02: Schema docstring references a wrong route path

**File:** `apps/backend/app/modules/schedule/schemas.py:171`
**Issue:** `RecurringSlotTemplateCreate` docstring says `POST /api/v1/recurring-slot-templates`, but the router mounts the prefix as `/recurring-templates` (api/v1/router.py:72-76). Pure documentation drift; no behavioral impact.
**Fix:** Update the docstring to `/api/v1/recurring-templates`.

### IN-03: Migration comments claim a SQL `NOT EXISTS` time-off predicate that does not exist in the executor

**File:** `apps/backend/alembic/versions/0042_recurring_schedule_time_off.py:172` and `apps/backend/app/modules/schedule/models.py:284`
**Issue:** Both the migration and the model comment justify the `ix_trainer_time_off_trainer_id` index as backing "the cron NOT EXISTS predicate (PITFALL 9)." The executor moved the time-off filter to a Python-side pre-fetch (`list_active_time_off_for_trainers` + in-memory overlap), so no `NOT EXISTS` SQL exists. The index is still useful for the in-memory fetch's `WHERE trainer_id IN (...)`, but the comment misdescribes how it is used.
**Fix:** Reword the index comments to "backs the cron's per-trainer time-off pre-fetch" to match the shipped Python-side implementation.

---

_Reviewed: 2026-05-25T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
