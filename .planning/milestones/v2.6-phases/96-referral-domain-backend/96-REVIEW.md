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
  info: 2
  total: 3
status: clean
---

# Phase 96: Code Review Report

**Reviewed:** 2026-06-08T00:00:00Z
**Depth:** standard
**Files Reviewed:** 11
**Status:** clean

## Summary

Reviewed the full Phase 96 referral domain backend: three ORM models, five repository helpers, five service functions, three router handlers, audit infrastructure extensions (LOCKED_AUDIT_EVENTS + AUDIT_PAYLOAD_SCHEMAS + two payload schemas), a Settings field, and two Alembic migrations.

The iteration-3 state is substantially sound. Both mutation paths (mint + capture) use the pg_insert on_conflict_do_nothing + RETURNING pattern. Audit is correctly emitted only on real inserts (RETURNING-gated). All payload UUID kwargs are str()-coerced for JSONB compatibility. RBAC-04 ordering is correct. IDOR is correctly anchored to the require_client() principal throughout. The migration DDL is consistent with service on_conflict index_elements targets.

One Warning remains: a narrow TOCTOU code-string collision gap described below. No Critical issues found. Info findings are non-blocking.

## Narrative Findings (AI reviewer)

## Warnings

### WR-01: Unhandled IntegrityError on Code-String Collision in Concurrent Mint

**File:** `apps/backend/app/modules/referrals/service.py:146-153`

**Issue:** `_generate_unique_code` uses a SELECT pre-check to verify the candidate code string is unused, then `get_or_create_referral_code` inserts via `pg_insert(...).on_conflict_do_nothing(index_elements=["client_id"])`. The `index_elements=["client_id"]` clause suppresses conflicts only on the `uq_referral_codes_client_id` unique index. It does NOT suppress conflicts on `uq_referral_codes_code`. If two concurrent mint requests for **different** clients both pass the SELECT check with the same candidate code string (probability ≈ 1 in 32^8 ≈ 1.1T per concurrent pair), the second INSERT hits `uq_referral_codes_code` and raises an unhandled `sqlalchemy.exc.IntegrityError`, producing a 500 for what is otherwise a legitimate request. The same-client concurrent path — which was the explicit target of the WR-01-iter2 fix — is correctly handled; this is a structurally distinct code-string collision path that the current on_conflict target does not cover.

**Fix:** Remove `index_elements` so `ON CONFLICT DO NOTHING` suppresses any unique violation on the table. The `if row is None` re-read branch already handles the same-client race correctly; extend it to also handle a code-collision no-insert:

```python
stmt = (
    pg_insert(ReferralCode)
    .values(client_id=client_id, code=new_code_str)
    .on_conflict_do_nothing()          # no index_elements — suppresses ANY unique violation
    .returning(ReferralCode.id, ReferralCode.code)
)
row = (await session.execute(stmt)).one_or_none()

if row is None:
    # Two possible causes:
    #   (a) Same-client concurrent mint won — re-read winner by client_id returns it.
    #   (b) Code-string collision with a different client — re-read by client_id returns None.
    winner = await repository.get_code_by_client_id(session, client_id)
    if winner is not None:
        # Case (a): idempotent no-op return.
        return ReferralCodeResponse(
            code=winner.code,
            share_url=f"{settings.pwa_base_url}/i/{winner.code}",
        )
    # Case (b): regenerate and retry (astronomically rare).
    raise RuntimeError("referral code string collision — retry required")
    # Caller wraps in a retry loop, or _generate_unique_code retries internally.
```

Alternatively, keep `index_elements=["client_id"]` and wrap only the `session.execute(stmt)` in a try/except for `IntegrityError` with a `uq_referral_codes_code` discriminator and re-generate on that path.

## Info

### IN-01: Unused `settings` Parameter in `resolve_public_code`

**File:** `apps/backend/app/modules/referrals/service.py:199-255`

**Issue:** `resolve_public_code(session, code_str, settings)` accepts a `Settings` argument but never references it anywhere inside the function body. The router resolves `get_settings` as a Depends and passes it as the third argument on every unauthenticated public request, incurring an unnecessary DI resolution. Under `mypy --strict` with `noUnusedParameters` this is flagged. The parameter appears to have been scaffolded for a planned `shareUrl` inclusion in the valid-code response branch but is presently dead.

**Fix:** Remove the parameter from both the service signature and the router call site, or suppress with a leading underscore rename if intentionally reserved for a follow-on plan:

```python
# service.py
async def resolve_public_code(
    session: AsyncSession,
    code_str: str,
) -> ReferralResolveResponse:
    ...

# router.py — remove settings dep injection from public_resolve_referral_code
async def public_resolve_referral_code(
    code: Annotated[str, Path(min_length=1, max_length=16)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[ReferralResolveResponse]:
    result = await service.resolve_public_code(session, code)
    return envelope(result)
```

### IN-02: Redundant `session.flush()` Before `session.commit()` in `update_referral_config`

**File:** `apps/backend/app/modules/referrals/service.py:377-378`

**Issue:** `update_referral_config` calls `await session.flush()` immediately followed by `await session.commit()`. SQLAlchemy async `commit()` always issues an implicit flush of pending unit-of-work changes before committing, making the explicit `flush()` a no-op. The other two mutating functions in this module (`get_or_create_referral_code` at line 189, `capture_referral` at line 341) both use bare `session.commit()` without a preceding flush. The inconsistency may mislead future maintainers into believing a separate flush is required for ORM-backed singleton writes.

**Fix:** Remove the explicit `flush()` to align with the rest of the module:

```python
config = await repository.upsert_config(session, data)
await session.commit()          # commit() flushes pending ORM changes atomically
```

---

_Reviewed: 2026-06-08T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
