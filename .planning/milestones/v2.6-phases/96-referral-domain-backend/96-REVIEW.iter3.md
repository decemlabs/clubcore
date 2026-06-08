---
phase: 96-referral-domain-backend
reviewed: 2026-06-08T00:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - apps/backend/app/modules/referrals/models.py
  - apps/backend/app/modules/referrals/schemas.py
  - apps/backend/app/modules/referrals/repository.py
  - apps/backend/app/modules/referrals/service.py
  - apps/backend/app/modules/referrals/router.py
  - apps/backend/app/api/v1/router.py
  - apps/backend/app/core/audit.py
  - apps/backend/app/core/audit_payloads.py
  - apps/backend/app/core/config.py
  - apps/backend/alembic/versions/0067_referral_tables.py
  - apps/backend/alembic/versions/0068_seed_referral_config.py
findings:
  critical: 0
  warning: 1
  info: 1
  total: 2
status: issues_found
---

# Phase 96: Code Review Report (Iteration 2)

**Reviewed:** 2026-06-08
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Re-review after auto-fix pass. All seven findings from iteration 1 (CR-01 through WR-04) are correctly resolved in the submitted files. No Critical issues remain. One new Warning and one Info item were introduced or exposed by the fixes.

**Confirmed closed:**

- **CR-01** — `flush + commit` present inside both `get_or_create_referral_code` (service.py:143/157) and `capture_referral` (service.py:305), and in `update_referral_config` (service.py:341-342). `audit.emit` is called before `session.commit()` in both mutating paths, so the AuditLog row is co-transactional. Transaction discipline is unified across the module.
- **CR-02** — `uq_referral_codes_client_id` UNIQUE index added to migration 0067 (lines 99-104) with literal name per project naming discipline; downgrade correctly drops it (line 166). One stable code per client is now enforced at DB level.
- **CR-03** — UUID objects passed directly to `audit.emit` kwargs (`client_id=client_id`, `referral_code_id=code_row.id`, etc.) — no more `str()` wrappers on UUID payload fields. `ReferralCodeGeneratedPayload` and `ReferralCapturedPayload` receive native UUID instances, matching the `extra="forbid"` schema definitions.
- **WR-01** — `pg_insert(ReferralCapture).on_conflict_do_nothing(index_elements=["referee_client_id"]).returning(ReferralCapture.id)` applied in `capture_referral` (service.py:273-282). Audit emit is RETURNING-gated (line 284-304): emitted only when `capture_id is not None`, preventing duplicate audit events on concurrent no-ops.
- **WR-02** — `deleted_at IS NULL` filter applied in both `resolve_public_code` (service.py:199-217) and `capture_referral` (service.py:260-267). Soft-deleted referrer correctly returns `valid=False` (resolver) or raises `ReferralCodeNotFoundError` (capture).
- **WR-03** — Crockford pattern `^[0-9A-HJKMNPQRSTVWXYZa-hjkmnpqrstvwxyz]{8}$` with `min_length=8, max_length=8` applied to `ReferralCaptureRequest.code` (schemas.py:54-60). Pattern correctly excludes I/L/O/U; alphabet matches the `CROCKFORD_ALPHABET` constant in service.py exactly (verified).
- **WR-04** — Transaction discipline unified: all three mutating service functions call `flush + commit`, matching `gym.service.update_gym_info`. No split router/service commit responsibility.

Two new findings remain.

## Warnings

### WR-01: `get_or_create_referral_code` concurrent-mint race yields unhandled `IntegrityError` (500)

**File:** `apps/backend/app/modules/referrals/service.py:128-164`

**Issue:** The CR-02 fix correctly added `uq_referral_codes_client_id` UNIQUE to the DB schema. However, `get_or_create_referral_code` still uses a read-then-insert pattern without catching the resulting `IntegrityError`. Two concurrent `GET /client/referral/code` requests for the same `client_id` that both observe `existing = None` (line 128) will both call `session.flush()` at line 143. The second flush hits the UNIQUE constraint and raises `sqlalchemy.exc.IntegrityError`. This is not caught — it propagates as an unhandled 500.

The project convention — established in `clients/service.py` (function `_is_phone_conflict`) — is to catch `IntegrityError` after `flush()` on insert paths and map it to a typed domain error or an idempotent re-read. The `capture_referral` function in the same file handles this correctly via `pg_insert on_conflict_do_nothing` (the WR-01 fix). The code-creation path does not receive the same treatment.

The race is rare in practice (concurrent first-time mints for the same client within a single request window), but when it occurs the user receives a 500 instead of the idempotent code they would get on a retry.

**Fix (option A — `pg_insert on_conflict_do_nothing`, mirrors `capture_referral`):**

Replace the `session.add` + `flush` with a pg_insert that handles the conflict atomically. Because code generation requires a unique string (not just a PK), the conflict path must re-read the winner row:

```python
stmt = (
    pg_insert(ReferralCode)
    .values(client_id=client_id, code=new_code_str)
    .on_conflict_do_nothing(index_elements=["client_id"])
    .returning(ReferralCode.id, ReferralCode.code)
)
row = (await session.execute(stmt)).one_or_none()
if row is None:
    # Concurrent mint won — re-read winner's row (no audit emit)
    winner = await repository.get_code_by_client_id(session, client_id)
    if winner is None:
        raise RuntimeError("referral code conflict but no winner row found")
    return ReferralCodeResponse(
        code=winner.code,
        share_url=f"{settings.pwa_base_url}/i/{winner.code}",
    )
code_row_id, code_row_code = row
```

**Fix (option B — catch IntegrityError, matches project convention for phone conflicts):**

```python
from sqlalchemy.exc import IntegrityError

try:
    await session.flush()
except IntegrityError:
    await session.rollback()
    winner = await repository.get_code_by_client_id(session, client_id)
    if winner is None:
        raise
    return ReferralCodeResponse(
        code=winner.code,
        share_url=f"{settings.pwa_base_url}/i/{winner.code}",
    )
```

## Info

### IN-01: Public resolver path parameter `/i/{code}` has no length or format bound

**File:** `apps/backend/app/modules/referrals/router.py:60`

**Issue:** The `public_resolve_referral_code` endpoint declares `code: str` as a plain path parameter with no length constraint. An arbitrarily long string passes through to `repository.get_code_by_value`, which calls `code_str.upper()` (allocating a new string) and issues a parameterised `SELECT WHERE code = :code`. The query is SQL-injection-safe (parameterised ORM) and the `String(16)` column will never match a long input, but there is no upper bound preventing a request with a multi-kilobyte path segment from reaching the service layer.

The WR-03 fix correctly constrains `ReferralCaptureRequest.code` (the authenticated POST body) to exactly 8 Crockford chars. The public GET endpoint deserves the same defensive bound, especially since it is unauthenticated.

**Fix:** Annotate with a `Path` constraint matching the code dimensions:

```python
from fastapi import Path

async def public_resolve_referral_code(
    code: Annotated[str, Path(min_length=1, max_length=16)],
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ResponseEnvelope[ReferralResolveResponse]:
```

Using `max_length=16` (the column width) rather than `8` is intentional: the resolver should gracefully return `valid=False` for any string that cannot match, including 9-16 char strings, without a 422 validation error that would create a detectable difference in response shape.

---

_Reviewed: 2026-06-08_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
