---
phase: 43-multi-user-admin-module
reviewed: 2026-05-19T15:47:16Z
depth: standard
files_reviewed: 17
files_reviewed_list:
  - apps/backend/alembic/versions/0030_users_lifecycle_columns.py
  - apps/backend/app/api/v1/router.py
  - apps/backend/app/core/audit_payloads.py
  - apps/backend/app/core/audit.py
  - apps/backend/app/core/config.py
  - apps/backend/app/core/exceptions.py
  - apps/backend/app/core/models.py
  - apps/backend/app/integrations/email/dispatcher.py
  - apps/backend/app/main.py
  - apps/backend/app/modules/auth/service.py
  - apps/backend/app/modules/users/constants.py
  - apps/backend/app/modules/users/email_templates.py
  - apps/backend/app/modules/users/permissions.py
  - apps/backend/app/modules/users/repository.py
  - apps/backend/app/modules/users/router.py
  - apps/backend/app/modules/users/schemas.py
  - apps/backend/app/modules/users/service.py
findings:
  critical: 4
  warning: 7
  info: 4
  total: 15
status: issues_found
---

# Phase 43: Code Review Report

**Reviewed:** 2026-05-19T15:47:16Z
**Depth:** standard
**Files Reviewed:** 17
**Status:** issues_found

## Summary

The Phase 43 multi-user admin module is broadly well-structured: the
4-branch invitation flow is sketched out, the partial-UNIQUE branches
are correctly partitioned, anti-oracle 401-harmonisation in
`rotate_refresh` is wired with paired emit/commit ordering, and the
core/modules import boundary is respected.

However, several defects materially affect correctness and security:

1. The invitation email is sent with EMPTY content because the service
   passes pre-rendered `subject`/`html`/`text` to a dispatcher that
   ignores them and re-renders the template against missing variables
   (BLOCKER).
2. The last-owner guard uses `SELECT count(*) ... FOR UPDATE`, which
   Postgres rejects with `ERROR: FOR UPDATE is not allowed with
   aggregate functions` — so every owner deactivate / soft-delete
   request will fail at runtime against a real database (BLOCKER).
3. Soft-deleted operators can still authenticate at
   `POST /auth/login` because `authenticate()` filters on
   `password_hash IS NOT NULL` but not on `deleted_at IS NULL` or
   `is_active`. The Phase 43 D-43-20 anti-oracle harmonisation only
   covers refresh — the login chokepoint was not closed (BLOCKER).
4. `deactivate_user` and `soft_delete_user` split their UoW into
   multiple committed transactions because
   `revoke_all_sessions(...)` issues its own `session.commit()`
   mid-flow. The "audit + mutation in same UoW" discipline cited
   throughout the codebase is violated (BLOCKER).

The 7 Warning findings concentrate around incorrect actor attribution
on `session_revoked_all`, silent ignoring of changed user data on
re-invite, missing `deactivated_by_user_id` on pure-delete paths,
under-counting on `family_count`, and the misleading docstring claim
that `FOR UPDATE` on an aggregate "serialises concurrent attempts".

---

## Critical Issues

### CR-01: Invitation email is sent with EMPTY Jinja variables — invitation link never reaches the operator

**File:** `apps/backend/app/modules/users/service.py:181-220`
**Issue:**
`service.create_user` does its own render of the
`USER_INVITATION_EMAIL` template (lines 181-193) and then passes the
rendered `subject` / `html` / `text` as `**envelope_fields` kwargs into
the dispatcher:

```python
envelope_fields = {
    "subject": template.subject,
    "html": template.html.render(**render_kwargs),
    "text": template.text.render(**render_kwargs),
}
...
await get_email_dispatcher()(
    template_id="USER_INVITATION_EMAIL",
    to=email_lower,
    audit_correlation_id=audit_correlation_id,
    **envelope_fields,
)
```

However, the dispatcher at
`apps/backend/app/integrations/email/dispatcher.py:167-205` is designed
to render templates ITSELF at enqueue time:

```python
template = _resolve_template(template_id)
rendered_html: str = template.html.render(**template_vars)
rendered_text: str = template.text.render(**template_vars)
```

Where `template_vars` is the catch-all `**template_vars: Any` from the
dispatcher's signature. The result:

1. The pre-rendered `subject` / `html` / `text` from the service are
   passed in as `template_vars` keys named `subject`/`html`/`text` —
   Jinja silently ignores unknown variables.
2. The variables the template actually needs (`full_name`, `role_ru`,
   `invitation_url`, `expires_at_human`) are NEVER passed to the
   dispatcher and therefore default to Jinja `Undefined` (rendered as
   empty string under `SandboxedEnvironment`).
3. The email body that lands in the operator's inbox contains
   `Здравствуйте, !` and an empty `<a href="">` element — no
   invitation URL.

The service's local `envelope_fields` render is dead code from a
mis-merged contract: the dispatcher exposes a "pass template_vars,
I'll render" surface (see the Phase 42 `EMAIL_OTP_LOGIN` callsite at
`auth/service.py:1031-1036` which passes `otp_code=raw_code` directly,
NOT a pre-rendered `html` kwarg).

This is a functional regression for the entire USERS-03 flow — the
invitation cannot be accepted because the URL never reaches the
invitee. There is no integration test that asserts the rendered
template variables hit the dispatched envelope (the existing
`tests/unit/users/test_email_template_render.py` only tests the
template module in isolation), which is why CI did not catch it.

**Fix:**
Match the Phase 42 `EMAIL_OTP_LOGIN` callsite — drop the local render
and pass the raw template variables:

```python
invitation_url = _build_invitation_url(raw_token)
expires_at_human = _format_expires_ru(token.expires_at)

# Audit emit ... (unchanged)

await get_email_dispatcher()(
    template_id="USER_INVITATION_EMAIL",
    to=email_lower,
    audit_correlation_id=audit_correlation_id,
    full_name=user.full_name,
    role_ru=ROLE_RU[user.role],
    invitation_url=invitation_url,
    expires_at_human=expires_at_human,
)
```

Delete the `TEMPLATES` / `ROLE_RU` imports at the service layer
(`service.py:68`) — they belong only at the dispatcher's resolution
boundary. Add an integration test that asserts
`envelope_kwargs["html"]` contains the literal `invitation_url`
substring.

---

### CR-02: Last-owner guard SQL fails at runtime — `SELECT count(*) ... FOR UPDATE` is rejected by Postgres

**File:** `apps/backend/app/modules/users/repository.py:349-372`
**Issue:**
`count_active_owners_excluding` compiles to:

```sql
SELECT count(*) AS count_1
FROM users
WHERE users.role = 'owner'
  AND users.is_active IS true
  AND users.deleted_at IS NULL
  AND users.id <> :excluded
  AND users.status = 'active'
FOR UPDATE
```

PostgreSQL explicitly rejects this combination:
`ERROR: FOR UPDATE is not allowed with aggregate functions`. SQLAlchemy
does NOT silently strip `with_for_update()` for aggregates — the
generated SQL emits `FOR UPDATE` verbatim (verified via
`stmt.compile(dialect=postgresql.dialect())`).

Consequence: EVERY call path through `deactivate_user(target.role ==
Role.OWNER)` and `soft_delete_user(target.role == Role.OWNER)` raises
`sqlalchemy.exc.ProgrammingError` at runtime. Owner deactivation /
soft-delete is broken in production. The only reason CI may pass is
that test fixtures may not exercise the owner-target branch against a
real Postgres connection (this should be confirmed and a regression
test added).

The docstring further claims `FOR UPDATE` "serialises concurrent
deactivates" — even if the query were legal, `FOR UPDATE` on an
aggregate locks zero rows (no rows are in the result set), so it would
serialise nothing. The intended invariant (no two parallel deactivates
both pass the guard) needs an actual row-lock strategy.

**Fix:**
Two viable approaches:

(a) Lock the candidate-owner rows directly, then count Python-side:

```python
stmt = (
    select(User.id)
    .where(
        User.role == Role.OWNER,
        User.is_active.is_(True),
        User.deleted_at.is_(None),
        User.id != excluded_user_id,
        User.status == "active",
    )
    .with_for_update()
)
return len((await session.execute(stmt)).all())
```

This actually takes row locks and gives real serialisation semantics.

(b) Use a PG advisory lock keyed on `('users:last_owner_guard')` at
the service boundary, then do an unlocked count.

Add a regression test that asserts the deactivate-owner path runs
green against an asyncpg Postgres test container (not SQLite/JSON shim).

---

### CR-03: Soft-deleted and deactivated users can still log in via `POST /auth/login`

**File:** `apps/backend/app/modules/auth/service.py:140-152`
**Issue:**
The Phase 43 D-43-20 anti-oracle work closed `rotate_refresh` against
deactivated / soft-deleted users (lines 419-456, correctly), but the
LOGIN chokepoint was not updated to match. `authenticate()` selects:

```python
user = await session.scalar(
    select(User).where(
        User.email == email_lower,
        User.password_hash.is_not(None),
    )
)
```

There is NO predicate on `User.deleted_at IS NULL` and NO predicate on
`User.is_active IS True`. The new Phase 43 `password_hash IS NOT NULL`
filter only covers pending-invitation users; soft-deleted operators and
deactivated operators both keep their `password_hash` and therefore
match this SELECT.

Concrete consequences:

1. A soft-deleted owner (`users.deleted_at IS NOT NULL`) can present
   their original email + password to `/auth/login`, receive a fresh
   `access` + `refresh` + `csrf` triple, and operate the system. The
   "tombstoned" semantics of soft-delete are bypassed.
2. A deactivated operator (`is_active = false`) can mint a fresh
   session via login even though `rotate_refresh` would later reject
   any rotation attempt — they are effectively granted a single
   access-token-TTL of access (default 15 min) per re-login, every
   time, with no upper bound.
3. The owner deactivating an attacker who has access to the
   credential cannot actually lock them out without also changing the
   password — contradicting the USERS-04 owner-revoke story.

This is the inverse of the `password_hash IS NOT NULL` defence-in-depth
filter that D-43-06 carefully added — that change filtered out one
new class of stranger (pending-invitation) but left the existing classes
unprotected. Anti-oracle uniformity is preserved (timing is symmetric
either way), but the access-control invariant fails.

**Fix:**
Mirror the `rotate_refresh` predicate set in `authenticate`:

```python
user = await session.scalar(
    select(User).where(
        User.email == email_lower,
        User.password_hash.is_not(None),
        User.is_active.is_(True),
        User.deleted_at.is_(None),
    )
)
```

Audit:
- emit `login_failed` with `reason="invalid_credentials"` in both
  miss branches (preserves AUTH-EP-02 timing+info equivalence at the
  audit layer — same shape the existing unknown-email path uses).
- Add `tests/integration/auth/test_login_deactivated_user.py` that
  asserts a deactivated user receives 401 `invalid_credentials` and
  no `set-cookie` headers.

The `getattr(user, 'is_active', True)` defensive read at
`auth/service.py:949` (in `request_otp_email`) should also be tightened
to `User.is_active.is_(True)` in the SQL predicate now that Phase 43
landed the column.

---

### CR-04: `deactivate_user` / `soft_delete_user` split their UoW — audit and mutation are NOT atomic

**File:** `apps/backend/app/modules/users/service.py:233-334` (and
chain through `apps/backend/app/modules/auth/service.py:644-692`)
**Issue:**
The service layer top-doc claim is:

> Repository emits zero commit/flush; service emits audit BEFORE flush
> (capture-before-mutate where needed), then flush to surface
> IntegrityErrors, then session.commit() at the route boundary.

This invariant is violated in three places because
`invalidate_all_families_for_user` → `revoke_all_sessions` calls
`await session.commit()` internally (auth/service.py:690).

Concrete trace for `deactivate_user`:

1. `repository.deactivate_user(...)` UPDATE users SET is_active=false
   (tx-1 starts).
2. `get_user_session_invalidator()(...)` →
   `invalidate_all_families_for_user` → `revoke_all_sessions`:
     - UPDATE refresh_tokens SET revoked_at = now (tx-1).
     - audit.emit("session_revoked_all", ...).
     - **session.commit() — tx-1 closes here**, including the
       deactivate UPDATE. The `user_deactivated` audit row has not
       been written yet.
3. audit.emit("user_deactivated", ...) — autobegins tx-2.
4. session.flush(); session.commit() — tx-2 closes.

If step 4 fails (DB error, network blip, unique violation on a future
audit-log constraint), the system has:
- `users.is_active = false` committed,
- `session_revoked_all` audit committed,
- `refresh_tokens` revoked,
- but NO `user_deactivated` audit row.

The compliance contract that "the actor and the deactivation reason
are reconstructable from `audit_log` alone" is broken at exactly the
boundary the contract was meant to defend.

`soft_delete_user` has the same shape AND additionally calls
`repository.consume_active_invitation_for_user` AFTER the mid-flow
commit — so the soft-delete + session-revoke + invitation-consume can
all commit while the `user_soft_deleted` audit row gets dropped on a
later failure.

The `password_changed_revokes_sessions` wrapper at
`auth/service.py:325-349` has the same shape (revoke commits, then
audit emits + commits in a separate tx) — pre-existing issue but
inherited into the Phase 43 surface.

**Fix:**
Introduce a non-self-committing variant of the session-revoke that the
USERS-04/05 service can compose into its own UoW. Sketch:

```python
# auth/service.py
async def _revoke_all_sessions_no_commit(
    session: AsyncSession, redis: Redis, user_id: UUID,
) -> int:
    # ... same Redis + UPDATE + audit.emit, NO session.commit() here.
    return family_count

async def revoke_all_sessions(session, redis, user_id) -> int:
    count = await _revoke_all_sessions_no_commit(session, redis, user_id)
    await session.commit()
    return count

async def invalidate_all_families_for_user(
    session, *, user_id, reason,
) -> int:
    # Wired from create_app(); composable variant — caller commits.
    if _redis_factory is None: ...
    return await _revoke_all_sessions_no_commit(
        session, _redis_factory(), user_id,
    )
```

Then in `users/service.py`:

```python
await repository.deactivate_user(...)
sessions_revoked = await get_user_session_invalidator()(
    session, user_id=target_user_id, reason="deactivated",
)
await audit.emit(session, "user_deactivated", ...)
await session.commit()  # ONE commit covers UPDATE + revoke + both audits.
```

Mirror the same restructuring in `soft_delete_user`. Add an explicit
test that simulates a DB failure between the revoke-call and the
final commit and asserts the deactivate UPDATE is rolled back.

---

## Warnings

### WR-01: `session_revoked_all` audit row carries the TARGET as `actor_user_id`, not the OWNER who initiated the action

**File:** `apps/backend/app/modules/auth/service.py:682-689` (called
from `users/service.py:252-254`)
**Issue:**
`revoke_all_sessions` emits:

```python
await audit.emit(
    session,
    "session_revoked_all",
    actor_user_id=user_id,
    resource_type="user",
    resource_id=user_id,
    family_count=family_count,
)
```

When invoked from `users/service.deactivate_user` /
`soft_delete_user`, `user_id` is the TARGET being deactivated. The
audit row therefore looks like the target deactivated themselves —
which is exactly the "self-deactivate" path the Phase 43 service
explicitly forbids via `CannotDeactivateSelfError`. Compliance review
of the audit log would draw the wrong conclusion about who initiated
the action.

**Fix:**
Plumb the owner `actor.id` through the invalidator Protocol so the
audit row attributes correctly:

```python
# dependencies.py UserSessionInvalidator Protocol
async def __call__(
    self,
    session: AsyncSession,
    *,
    user_id: UUID,
    actor_user_id: UUID | None,  # NEW
    reason: Literal[...],
) -> int: ...

# users/service.py
await get_user_session_invalidator()(
    session,
    user_id=target_user_id,
    actor_user_id=actor.id,  # NEW
    reason="deactivated",
)
```

Pass `actor_user_id` down to `revoke_all_sessions` and use it as the
audit `actor_user_id` (`user_id` stays in `resource_id` /
`family_count` context).

---

### WR-02: Re-invite branch silently ignores changed `full_name` / `role`

**File:** `apps/backend/app/modules/users/service.py:146-159`
**Issue:**
Branch B handles "existing pending_invitation user, owner is
re-inviting":

```python
if existing is not None and existing.status == "pending_invitation":
    await repository.consume_active_invitation_for_user(session, user_id=existing.id)
    user = existing
```

The new `data.full_name` and `data.role` from the inbound request are
DISCARDED. A common operator-error scenario:

1. Owner invites "John Smith / reception" — pending_invitation row
   created.
2. Owner notices typo, re-invites "Jane Smith / owner".
3. System sends invitation under the OLD full_name "John Smith" with
   the OLD role "reception". The accepted user lands with reception
   role even though the owner intended owner.

This may be intended (re-invite is purely a token refresh) but the
plan docstrings and the API contract suggest the POST body is the
authoritative re-statement of the invite. At minimum, raise a 409 if
the request data does not match the existing pending row, OR overwrite.

**Fix:**
Either:
1. Persist the new values:
   ```python
   user.full_name = data.full_name
   user.role = data.role
   ```
   inside branch B (then the existing flush surfaces any conflict).
2. Or raise a domain error:
   ```python
   if (existing.full_name != data.full_name) or (existing.role != data.role):
       raise EmailAlreadyActiveError("invitation_data_mismatch")
   ```

Pick one and document it on the endpoint. The current silent-keep
behaviour is the least-discoverable option.

---

### WR-03: `soft_delete_user` never populates `deactivated_by_user_id` on the pure-delete-without-deactivate path

**File:** `apps/backend/app/modules/users/repository.py:286-304`
**Issue:**
`soft_delete_user` sets `is_active=False` and uses
`COALESCE(deactivated_at, now)` to populate `deactivated_at`. But it
NEVER touches `deactivated_by_user_id`. For the pure-delete path
(target was active before delete), the resulting row has:

- `is_active = false`
- `deactivated_at = <now>`
- `deactivated_by_user_id = NULL`

The forensic chain ("which owner ended this account") is broken for
this path. Migration 0030's lifecycle CHECK constraint passes because
it only correlates `is_active` and `deactivated_at`, not
`deactivated_by_user_id`. The `User.deactivated_by_user_id` column on
the ORM is the natural place to record the deleting actor.

**Fix:**
Pass actor id and use the same COALESCE pattern:

```python
async def soft_delete_user(
    session: AsyncSession,
    *,
    target_user_id: UUID,
    actor_user_id: UUID,
) -> None:
    now = _now_utc()
    await session.execute(
        update(User)
        .where(User.id == target_user_id)
        .values(
            deleted_at=now,
            is_active=False,
            deactivated_at=func.coalesce(User.deactivated_at, now),
            deactivated_by_user_id=func.coalesce(
                User.deactivated_by_user_id, actor_user_id,
            ),
        )
    )
```

And update the service callsite to pass `actor_user_id=actor.id`.

---

### WR-04: `family_count` reported in `session_revoked_all` audit is read from Redis SMEMBERS, not from the DB UPDATE

**File:** `apps/backend/app/modules/auth/service.py:656-688`
**Issue:**
`revoke_all_sessions` first computes `family_count = len(family_ids_raw)`
from `SMEMBERS auth:user_sessions:{user_id}`, then runs the DB
UPDATE on every alive refresh row. Redis can drift below the DB
ground truth (TTL expiry, flush, replica-lag), in which case the
audit row understates the number of families actually killed. The
`user_deactivated` payload's `sessions_revoked_count` then reports
the wrong figure to ops dashboards and to compliance.

**Fix:**
Use the DB UPDATE's `rowcount` (or run an explicit DISTINCT
`family_id` count) for the audit and the return value:

```python
res = await session.execute(
    update(RefreshToken)
    .where(
        RefreshToken.user_id == user_id,
        RefreshToken.revoked_at.is_(None),
    )
    .values(revoked_at=datetime.now(tz=UTC))
    .returning(RefreshToken.family_id.distinct())
)
family_ids_revoked = {row.family_id for row in res}
family_count = len(family_ids_revoked)
```

Or run a `SELECT DISTINCT family_id` first, then UPDATE; either path
gives the DB-authoritative count.

---

### WR-05: `count_active_owners_excluding` docstring claims `FOR UPDATE` "serialises concurrent deactivates" — false for aggregate queries

**File:** `apps/backend/app/modules/users/repository.py:352-372`
**Issue:**
Independent of CR-02 (the SQL will error), the surrounding
documentation in `users/service.py:243` ("FOR UPDATE serialises
parallel deactivate attempts on owners") and the repository docstring
itself communicate an invariant that the chosen mechanism cannot
provide. Even if Postgres allowed it, `FOR UPDATE` on an aggregate
query has no rows to lock. The "v1.2 freeze-period serial-arbiter"
analogy in the docstring locks specific rows; this one does not.

This is a documentation defect that would mislead the next maintainer
into thinking the race window is closed — leading to a real
TOCTOU between two parallel owner-deactivate requests both observing
`count >= 1` and both proceeding.

**Fix:**
Adopt the CR-02 fix (lock the candidate rows themselves) AND update
the docstring to describe the real locking semantics. Add a
unit/integration test that fires two concurrent deactivate requests
against the second-to-last owner and asserts exactly one wins.

---

### WR-06: `revoke_invitation` does not check that the invitation has not expired before raising "already accepted" on race

**File:** `apps/backend/app/modules/users/service.py:337-372`
**Issue:**
`revoke_invitation` pre-checks `token.consumed_at is not None` and
re-uses `InvitationAlreadyAcceptedError` for both the pre-check and
race-loss paths. But `atomic_consume_invitation_token_by_id` only
filters on `consumed_at IS NULL` — it does NOT filter on `expires_at
> now()`. An expired-but-unconsumed token would be successfully
"consumed" by this UPDATE (silently flipping `consumed_at` on a row
that was already useless), the service would emit
`user_invitation_revoked`, and the owner UI would see a clean 204.

That is mostly benign (the token was already unusable), but combined
with the audit emit at line 360-370 it produces a
`user_invitation_revoked` row for an already-expired invitation —
muddying the forensic chain. Worse: if Phase 44 RESET-04 later filters
acceptance on `expires_at > now() AND consumed_at IS NULL`, an
already-`consumed_at`-set expired token cannot be distinguished from
an owner-revoked one when reconstructing the chain.

**Fix:**
Filter the atomic-consume on `expires_at > now()` AND return a
sentinel that disambiguates "expired" from "race-lost", OR add a
distinct domain error `InvitationExpiredError` that maps to 409
(`invitation_expired`):

```python
stmt = (
    update(PasswordResetToken)
    .where(
        PasswordResetToken.id == token_id,
        PasswordResetToken.purpose == "invitation",
        PasswordResetToken.consumed_at.is_(None),
        PasswordResetToken.expires_at > _now_utc(),
    )
    ...
)
```

Add a pre-check on `token.expires_at <= now` that raises
`InvitationExpiredError` so the owner UI can distinguish.

---

### WR-07: `_format_expires_ru` formats datetimes in UTC but rendered string carries no TZ — Russian-language email will display an off-by-3-hours time

**File:** `apps/backend/app/modules/users/service.py:94-103`
**Issue:**
`token.expires_at` is a TIMESTAMPTZ stored in UTC. `_format_expires_ru`
formats it as `"DD <month_ru> YYYY в HH:MM"`. The format string
contains no TZ marker, and the local docstring explicitly notes "Render
in UTC to keep the wire shape deterministic". An invitee in Moscow
(MSK = UTC+3, project i18n is Europe/Moscow per CLAUDE.md) will see an
expiry that reads 3 hours earlier than reality, and 1 hour earlier
again during DST transitions in zones the invitee is reading from.

Given the project's hardline "all human-facing dates in Europe/Moscow"
convention (`shared/i18n/date.ts`, gym hours pinned MSK, etc.), the
asymmetry is a real defect — the Russian text reads naturally as
"Moscow time" but is actually UTC.

**Fix:**
Convert to Europe/Moscow before formatting, matching project i18n:

```python
from zoneinfo import ZoneInfo
_MSK = ZoneInfo("Europe/Moscow")

def _format_expires_ru(dt: datetime) -> str:
    local = dt.astimezone(_MSK)
    return (
        f"{local.day} {_RU_MONTHS_GENITIVE[local.month - 1]} {local.year} "
        f"в {local.hour:02d}:{local.minute:02d} (МСК)"
    )
```

The `(МСК)` suffix removes ambiguity for international invitees
forwarded the email.

---

## Info

### IN-01: `audit_correlation_id` fabricated with fresh `uuid4()` for events with no downstream chain

**File:** `apps/backend/app/modules/users/service.py:262, 290, 330, 366`
**Issue:**
`deactivate_user`, `reactivate_user`, `soft_delete_user`, and
`revoke_invitation` each generate a fresh
`audit_correlation_id=str(uuid4())` purely to satisfy the
`UserDeactivatedPayload` schema. None of these flows produce a
downstream async event that consumes the chain id; per the schema
docstring at `audit_payloads.py:454-456`, `audit_correlation_id` is
declared `UUID | None` precisely so chain-starters can pass `None`.

Fabricating fresh UUIDs makes audit-log greps for "which events were
correlated" noisier and provides no forensic value here.

**Fix:**
Pass `audit_correlation_id=None` for these four call sites; reserve
fresh uuid4 generation for `create_user` (which DOES chain to the
email_sent / email_send_failed downstream rows).

---

### IN-02: `repository.get_alive` uses `User.deleted_at.is_(None)` but `repository.deactivate_user` does NOT filter on `deleted_at IS NULL` in its UPDATE

**File:** `apps/backend/app/modules/users/repository.py:244-263`
**Issue:**
`deactivate_user(target_user_id)` runs `UPDATE users WHERE id =
target_user_id` with no guard against `deleted_at IS NOT NULL`. The
service-layer guard (`get_alive` returning None) is the only defence
— but a race between two requests (one deactivate, one soft-delete)
could allow a soft-delete to land while the deactivate UPDATE is in
flight, producing a `deleted_at IS NOT NULL` row that gets
`is_active` re-flipped (no-op for the soft-delete invariant but a
violation of "soft-deleted rows are tombstones, never mutated again").

Defence-in-depth: add the predicate.

**Fix:**
```python
await session.execute(
    update(User)
    .where(
        User.id == target_user_id,
        User.deleted_at.is_(None),
    )
    .values(...)
)
```

Apply the same change to `repository.reactivate_user` and to
`repository.soft_delete_user` (idempotency only — soft-delete-on-soft-
delete should remain a no-op rather than re-stamping `deleted_at`).

---

### IN-03: `INVITATION_TOKEN_TTL` is module-level but read inside repository.insert_invitation_token via direct import — `frontend_base_url` is read via `get_settings()` only in the service

**File:** `apps/backend/app/modules/users/repository.py:33,211` and
`apps/backend/app/modules/users/service.py:112`
**Issue:**
Style inconsistency: `INVITATION_TOKEN_TTL` is a `Final` module
constant the repository imports directly, while `frontend_base_url`
must be fetched at call time via `get_settings()` (so test overrides
of the env var take effect). Both are configuration; one bypasses the
settings indirection. If a future deployment needs different TTL per
environment, this becomes a config-drift trap.

**Fix:**
Either:
1. Promote `INVITATION_TOKEN_TTL` to a `Settings` field
   (`invitation_token_ttl_seconds: int = 7 * 86400`) and read it at
   call time, OR
2. Promote `frontend_base_url` to a module-level constant if it's
   truly immutable.

Pick one pattern (#1 is more flexible and matches existing
`access_token_ttl_seconds` / `refresh_token_ttl_seconds`).

---

### IN-04: `User.__table_args__` constraint name "role" risks pgname collision; mismatch with naming convention

**File:** `apps/backend/app/core/models.py:116-118`
**Issue:**
```python
__table_args__ = (
    CheckConstraint("role IN ('owner', 'reception')", name="role"),
)
```

A constraint literally named `"role"` (no `ck_users_` prefix) bypasses
the project naming convention defined in `app/core/database.py` and
risks colliding with future column names (Postgres allows but
discourages reserved-word-like constraint names). The companion
migration 0030 uses `op.f("ck_users_status")` so the new checks pick
up `ck_users_<name>`. The pre-existing `role` constraint name is
inconsistent.

Out-of-Phase-43-scope as it predates this phase, but flagged for a
future Alembic naming-cleanup pass.

**Fix:**
On a future migration, rename to `ck_users_role` to align with the
naming convention. No-op for Phase 43 since this is pre-existing.

---

_Reviewed: 2026-05-19T15:47:16Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
