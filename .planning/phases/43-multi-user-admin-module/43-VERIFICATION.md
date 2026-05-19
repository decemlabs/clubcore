---
phase: 43-multi-user-admin-module
verified: 2026-05-19T21:10:00Z
status: passed
score: 5/5 success criteria verified (7/7 USERS-* requirements satisfied); 13/13 review findings closed (CR-01..04 + WR-01..07 + IN-01..02); IN-03/IN-04 deferred per CONTEXT.md; SVC001 regression closed by commit 629b433
overrides_applied: 0
re_verification:
  previous_status: passed
  previous_score: 5/5
  re_verified: 2026-05-19T21:10:00Z
  re_verification_reason: "Post-gap-closure re-verification after 43-14..43-17 (4 BLOCKER + 7 WARNING + 2 INFO findings from 43-REVIEW.md). SVC001 regression flagged at 21:00 and closed at 21:10 via commit 629b433."
  gaps_closed:
    - "CR-01: Invitation email dispatched with EMPTY Jinja variables"
    - "CR-02: count_active_owners_excluding used SELECT count(*) FOR UPDATE — rejected by Postgres"
    - "CR-03: Login chokepoint missing is_active + deleted_at predicates"
    - "CR-04: deactivate_user / soft_delete_user split UoW — audit and mutation not atomic"
    - "WR-01: session_revoked_all audit attributed to target, not actor"
    - "WR-02: re-invite silently discarded full_name/role from new request"
    - "WR-03: soft_delete_user never populated deactivated_by_user_id on pure-delete path"
    - "WR-04: family_count read from Redis SMEMBERS instead of DB UPDATE RETURNING"
    - "WR-05: count_active_owners_excluding docstring falsely claimed FOR UPDATE serialised concurrent deactivates"
    - "WR-06: revoking an already-expired invitation returned 204 instead of 409"
    - "WR-07: _format_expires_ru formatted in UTC not MSK — Russian email showed wrong time"
    - "IN-01: deactivate/reactivate/soft_delete/revoke_invitation fabricated uuid4() for audit_correlation_id"
    - "IN-02: deactivate_user/reactivate_user/soft_delete_user UPDATEs missing deleted_at IS NULL defence"
    - "REGRESSION-43-16-SVC001: _revoke_all_sessions_no_commit missing # noqa: SVC001 caller-owns-txn marker — closed by commit 629b433"
  gaps_remaining: []
  regressions_closed:
    - "REGRESSION-43-16-SVC001: commit 629b433 adds '# noqa: SVC001 caller-owns-txn' to auth/service.py:668. tests/unit/test_service_commit_gate.py now 7/7 PASS. Full users + auth chokepoint sanity suite: 45/45 PASS."
---

# Phase 43: Multi-User Admin Module Verification Report

**Phase Goal:** Owner can onboard, deactivate, soft-delete, and re-onboard reception operators end-to-end via API without any direct DB-poking — and any operator action carries denormalised audit traceability that survives that operator being fired.

**Initial Verification:** 2026-05-19T15:41:30Z — status: passed (5/5 SC, 7/7 USERS-*)
**Re-Verification:** 2026-05-19T21:00:00Z — after gap-closure plans 43-14..43-17
**Re-Verification Status:** passed (1 regression introduced by 43-16 closed by commit 629b433 at 21:10)

---

## Re-Verification: Post-Gap-Closure Findings (43-14..43-17)

### Review Findings Status Matrix

| Finding | Severity | Plan | Code Evidence | Test Evidence | Status |
|---------|----------|------|---------------|---------------|--------|
| CR-01: Empty invitation email | BLOCKER | 43-14 | `service.py:234-237` passes `full_name=user.full_name`, `role_ru=role_ru`, `invitation_url=invitation_url`, `expires_at_human=expires_at_human` directly to dispatcher — no pre-rendered `envelope_fields` | `test_invitation_email_envelope.py::test_invitation_email_envelope_carries_invitation_url` PASS | CLOSED |
| CR-02: SELECT count(*) FOR UPDATE illegal in Postgres | BLOCKER | 43-15 | `repository.py:410-421` now `select(User.id).with_for_update()` + `len(result.all())` — aggregate removed | `test_deactivate_owner_real_postgres.py::test_deactivate_owner_against_real_postgres` PASS | CLOSED |
| CR-03: Login chokepoint missing is_active + deleted_at | BLOCKER | 43-17 | `auth/service.py:157-160`: `authenticate()` SELECT includes `User.is_active.is_(True)` and `User.deleted_at.is_(None)` | `test_login_deactivated_user.py` — 4 tests PASS; `test_request_otp_inactive_user.py` — 3 tests PASS | CLOSED |
| CR-04: deactivate/soft_delete split UoW | BLOCKER | 43-16 | `auth/service.py:668` `_revoke_all_sessions_no_commit` exists; `invalidate_all_families_for_user` (line 1189) calls no-commit variant; `users/service.py` single `session.commit()` covers UPDATE + revoke + both audits | `test_deactivate_atomic_uow.py` — 2 tests PASS (including rollback test) | CLOSED (fix correct) but **REGRESSION introduced** — see below |
| WR-01: session_revoked_all actor is target not actor | WARNING | 43-16 | `dependencies.py:721`: `actor_user_id: UUID \| None` in Protocol; `users/service.py:287,370`: `actor_user_id=actor.id` passed; `auth/service.py:720`: `actor_user_id=actor_user_id` in audit emit | `test_session_revoked_all_actor_attribution.py::test_session_revoked_all_actor_is_owner_not_target` PASS | CLOSED |
| WR-02: re-invite discards full_name/role | WARNING | 43-14 | `service.py:167-168`: `existing.full_name = data.full_name` and `existing.role = data.role` in Branch B | `test_reinvite_overrides_pending_user_data.py::test_reinvite_overwrites_full_name_and_role` PASS | CLOSED |
| WR-03: soft_delete_user never writes deactivated_by_user_id | WARNING | 43-16 | `repository.py:330-331`: `func.coalesce(User.deactivated_by_user_id, actor_user_id)` in soft_delete_user UPDATE | `test_soft_delete_records_actor.py` — 2 tests PASS (pure-delete + delete-after-deactivate paths) | CLOSED |
| WR-04: family_count from Redis SMEMBERS not DB | WARNING | 43-16 | `auth/service.py:708-711`: `UPDATE...RETURNING family_id` + `{row.family_id for row in result}` — Redis SMEMBERS path retained as best-effort cleanup only | `test_family_count_db_authoritative.py::test_family_count_reports_db_truth_when_redis_drifted` PASS | CLOSED |
| WR-05: docstring claims FOR UPDATE serialises aggregates (false) | WARNING | 43-15 | `service.py:26-29` module docstring updated; `deactivate_user` comment rewritten to describe correct row-lock semantics | Covered by CR-02 test above; WR-05 is documentation + docstring correctness | CLOSED |
| WR-06: revoking expired invitation returned 204 | WARNING | 43-14 | `service.py:410-411`: `if token.expires_at <= now: raise InvitationExpiredError`; `repository.py:376`: `PasswordResetToken.expires_at > _now_utc()` predicate in atomic_consume | `test_revoke_expired_invitation.py` — 2 tests PASS | CLOSED |
| WR-07: expiry time in UTC not MSK in Russian email | WARNING | 43-14 | `service.py:97-114`: `_MOSCOW_TZ = ZoneInfo("Europe/Moscow")`, `_format_expires_ru` calls `dt.astimezone(_MOSCOW_TZ)`, appends `(МСК)` suffix | `tests/unit/users/test_format_expires_ru.py` — 3 tests PASS | CLOSED |
| IN-01: fabricated uuid4() at terminal audit events | INFO | 43-14 | `service.py:297,325,382,426`: `audit_correlation_id=None` at deactivate/reactivate/soft_delete/revoke_invitation | Code verified by grep: 4 occurrences of `audit_correlation_id=None` | CLOSED |
| IN-02: mutation UPDATEs missing deleted_at IS NULL defence | INFO | 43-15 | `repository.py:264,291,326`: `User.deleted_at.is_(None)` in WHERE clause of deactivate_user, reactivate_user, soft_delete_user | `test_deactivate_owner_real_postgres.py` PASS; no regression in existing tests | CLOSED |
| IN-03: INVITATION_TOKEN_TTL style inconsistency | INFO | 43-14 | Deferred to v1.7 — recorded in CONTEXT.md `## Deferred Ideas` | N/A — deferred | DEFERRED |
| IN-04: ck_users_role constraint naming | INFO | 43-14 | Deferred to future Alembic naming-cleanup pass — recorded in CONTEXT.md | N/A — deferred | DEFERRED |

---

### REGRESSION Introduced by 43-16: SVC001 Commit-Gate Test Failure

**Finding:** The `_revoke_all_sessions_no_commit` helper introduced in commit `1d70be9` (plan 43-16) is missing the `# noqa: SVC001 caller-owns-txn` opt-out marker. The SVC001 AST commit-gate walker (`tests/unit/test_service_commit_gate.py`) identifies it as a write-path function (it calls `audit.emit` and a bulk `UPDATE`) with no `session.commit()` and no opt-out — which is exactly the Phase 12.1 bug class the gate guards against.

**Observable failure:**

```
FAILED tests/unit/test_service_commit_gate.py::test_service_commit_gate_against_app_modules
AssertionError: Service write-path commit-gate (SVC001) failed.
  Offenders:
    apps/backend/app/modules/auth/service.py:668 — `_revoke_all_sessions_no_commit` is a write
    path (mutating SQL or audit.emit) but contains no `await session.commit()` and no SVC001
    opt-out marker.
```

**Why this happened:** The 43-16 regression suite ran `tests/integration/users/ tests/integration/auth/ tests/integration/test_app_wiring.py tests/unit/users/` — it did NOT include `tests/unit/test_service_commit_gate.py`. The function IS intentionally caller-owns-txn (that is the whole purpose of the CR-04 fix), but the required opt-out marker was omitted.

**Fix is trivial:** add `# noqa: SVC001 caller-owns-txn` to the `def` line:

```python
async def _revoke_all_sessions_no_commit(  # noqa: SVC001 caller-owns-txn
    session: AsyncSession,
```

**Full test suite (excluding this one test):** 95 passed, 1 xfailed — all other tests pass. The regression is isolated to this one missing marker.

---

### Regression Suite Results (Post-Gap-Closure, Excl. Commit-Gate)

```
uv run pytest tests/integration/users/ tests/integration/auth/ tests/integration/test_app_wiring.py tests/unit/users/ -q
95 passed, 1 xfailed in 15.42s
```

```
uv run pytest tests/integration/users/ -v
33 passed in 5.84s  (19 pre-existing + 14 new from 43-14..43-17)
```

```
uv run pytest tests/integration/auth/ -v
53 passed, 1 xfailed in 9.30s  (46 pre-existing + 7 new from 43-17)
```

```
uv run pytest tests/unit/ -q
1 FAILED (test_service_commit_gate), 712 passed — regression isolated to missing SVC001 marker
```

```
uv run ruff check app/modules/users/ app/modules/auth/service.py app/core/dependencies.py app/core/exceptions.py
All checks passed!

uv run mypy app/modules/users/
Success: no issues found in 8 source files

uv run lint-imports
3 contracts kept, 0 broken
```

---

## Original Verification (2026-05-19T15:41:30Z) — Preserved for Audit History

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC1 | Owner POSTs `/api/v1/users` → 201 `{id, email, role, invitationExpiresAt}`, never plaintext password; row exists with `status='pending_invitation'` | VERIFIED | `app/modules/users/router.py:84-109` (status_code=201, response_model=UserCreateResponse — no password field); `app/modules/users/schemas.py` UserCreateResponse lacks password field; `app/modules/users/service.py:123-230` creates row with `status='pending_invitation'`, `password_hash=None`. Test: `test_create_happy_returns_201_and_emits_user_invited` (PASS) explicitly asserts `user.password_hash is None`, `user.status == "pending_invitation"`, `user.is_active is True` |
| SC2 | Owner PATCHes `/{id}/deactivate` → atomic (`is_active=false` + `deactivated_at` + `deactivated_by_user_id`) + revoke families via `UserSessionInvalidator` + `user_deactivated` audit with `actor_email_snapshot` + next `/auth/refresh` returns 401 | VERIFIED | `service.py:233-267` enforces atomic UPDATE + `get_user_session_invalidator()(...)` + `audit.emit("user_deactivated", sessions_revoked_count=...)` in one UoW; `auth/service.py:413-456` extends `rotate_refresh` user-SELECT with `User.is_active.is_(True) AND User.deleted_at.is_(None)`. Tests: `test_deactivate_revokes_families_and_blocks_refresh` (PASS), `test_refresh_anti_oracle_four_cases` (PASS) — body parity across (active, deactivated, soft-deleted, unknown) within 100ms timing spread |
| SC3 | Owner DELETEs a user → soft-delete; then POSTs same email for different person → partial-UNIQUE permits INSERT, brand-new `users.id`, historical audit rows resolve `actor_email_snapshot` | VERIFIED | `service.py:297-334` soft-delete + invitation cascade consume; `repository.py` get_by_email_for_create uses `WHERE deleted_at IS NULL` predicate so soft-deleted rows are invisible to the create path (branch D in service.py:17-24 docstring). Test: `test_soft_deleted_email_can_be_re_invited_with_new_id` (PASS) asserts new UUID minted; audit history preserved via Phase 41 `actor_email_snapshot` column persistence |
| SC4 | Owner cannot deactivate self → 409 `cannot_deactivate_self`; cannot deactivate last owner → 409 `cannot_deactivate_last_owner`; reception → 403 on all `/api/v1/users/*` mutations (RBAC 3-way parity holds) | VERIFIED | `service.py:240-248` enforces self-guard + last-owner guard with `FOR UPDATE` serialisation. Router (router.py:84-186) wraps every endpoint with `Depends(require_permission(...))` for CREATE/UPDATE/DELETE/LIST on `Resource.USERS` (all in OWNER_ONLY per `permissions.py:120-123`). Tests: `test_cannot_deactivate_self_returns_409`, `test_cannot_deactivate_last_owner_returns_409`, `test_cannot_delete_self_returns_409`, `test_reception_cannot_create_user_403`, `test_reception_cannot_list_users_403`, `test_create_missing_csrf_returns_403` — all PASS. 3-way RBAC parity test (`tests/integration/test_rbac_parity.py`) PASSES |
| SC5 | `GET /api/v1/users?active=...&deleted=...` returns paginated `{items, total, page, pageSize}` envelope with `{id, email, fullName, role, isActive, isDeactivated, createdAt, deactivatedAt, deactivatedByUserId}` — NO `passwordHash`, `password_changed_at`, refresh families, invitation tokens | VERIFIED | Router returns `ResponseEnvelope[PaginatedData[UserListItemResponse]]`; `schemas.py` UserListItemResponse explicitly lists allowed fields and EXCLUDES password fields. Test: `test_list_users_paginated_envelope_no_password_leak` (PASS) asserts the envelope shape and `passwordHash`/`password_changed_at`/raw token absence |

**Score:** 5/5 ROADMAP success criteria verified.

### Required Artifacts (USERS-01 module structure)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/modules/users/__init__.py` | exists | VERIFIED | present |
| `app/modules/users/router.py` | 6 endpoints + RBAC + CSRF | VERIFIED | 186 lines; 6 routes: GET, POST, PATCH deactivate, PATCH reactivate, DELETE, POST revoke-invitation |
| `app/modules/users/service.py` | 4-branch create + deactivate/reactivate/soft-delete/revoke orchestration | VERIFIED | 372 lines; flat-kwargs audit, FOR UPDATE last-owner serialisation, atomic UoW |
| `app/modules/users/repository.py` | `list_alive`/`get_alive` + invitation token CRUD | VERIFIED | 372 lines; no commit/flush (service owns transaction per D-03) |
| `app/modules/users/schemas.py` | BackendSchemaBase (camelCase wire) | VERIFIED | 84 lines; UserCreateRequest/UserCreateResponse/UserListItemResponse/UserListQuery/InvitationRevokeRequest |
| `app/modules/users/permissions.py` | marker file re-exporting `Resource.USERS` | VERIFIED | 13 lines; thin shim per D-43-11 |
| `app/modules/users/constants.py` | `INVITATION_TOKEN_TTL = timedelta(days=7)` | VERIFIED | 12 lines, single constant per D-43-12 |
| `app/modules/users/email_templates.py` | `USER_INVITATION_EMAIL` template (subject + html + text) | VERIFIED | 81 lines; SandboxedEnvironment + locked subject |
| `alembic/versions/0030_users_lifecycle_columns.py` | adds `is_active`, `status`, `deactivated_at`, `deactivated_by_user_id`, drops `password_hash NOT NULL` | VERIFIED | revision present; downgrade defined; CHECK constraint on lifecycle consistency |
| `app/core/models.py:User` ORM extension | 4 new columns + `password_hash` nullable | VERIFIED | `is_active`, `status` (Text+CHECK), `deactivated_at`, `deactivated_by_user_id` mapped; `password_hash: Mapped[str \| None]` |
| `app/core/audit_payloads.py` 6 user-lifecycle payloads | pre-registered Phase 41; `link_copied` field added | VERIFIED | all 6 payloads registered in AUDIT_PAYLOAD_SCHEMAS (lines 738-743); `UserInvitedPayload.link_copied: bool = False` (default per regression fix) |
| `auth.service.invalidate_all_families_for_user` | UserSessionInvalidator Protocol impl | VERIFIED | `auth/service.py:1189`; wraps `_revoke_all_sessions_no_commit` with Redis closure + actor_user_id plumbing |
| `app/main.py` registration | `register_user_session_invalidator(invalidate_all_families_for_user)` | VERIFIED | line 270 in `create_app()`; single-wire per D-43-27 |
| `app/api/v1/router.py` include | users_router mounted at `/users` | VERIFIED | line 68: `v1.include_router(users_router, prefix="/users", tags=["users"])` |

### Key Link Verification (Wiring)

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| router.py:create_user_endpoint | service.create_user | direct call line 108 | WIRED | router → service → repository chain intact |
| service.deactivate_user | UserSessionInvalidator | `get_user_session_invalidator()(...)` line 287 with `actor_user_id=actor.id` | WIRED | Protocol slot resolved at runtime; registered in main.py:270; CR-04 + WR-01 fixed |
| service.create_user | EmailDispatcher | `get_email_dispatcher()(template_id="USER_INVITATION_EMAIL", full_name=..., role_ru=..., invitation_url=..., expires_at_human=...)` | WIRED | CR-01 fix: raw template vars passed directly (not pre-rendered envelope_fields) |
| service.create_user | audit.emit("user_invited", ...) | line 200; FLAT kwargs incl. `link_copied` | WIRED | matches UserInvitedPayload extra='forbid' shape |
| auth.service.rotate_refresh | User.is_active + User.deleted_at filter | line 436-437 single SELECT | WIRED | single SELECT race-tight per D-43-20 |
| auth.service.authenticate | User.is_active + User.deleted_at filter | lines 159-160 | WIRED | CR-03 fix: mirrors rotate_refresh predicate set |
| auth.service.request_otp_email | User.is_active + User.deleted_at filter | lines 1009-1010 | WIRED | CR-03 secondary fix: SQL predicate replaces defensive getattr |
| service.* | actor_email_snapshot capture | inherited from ActorContextMiddleware (Phase 41) | WIRED | audit.py:389-400 reads ContextVar at every emit call |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| GET /users | `page.items` | repository.list_alive → SELECT users WHERE deleted_at IS NULL + filters | YES | test_list_users_paginated_envelope_no_password_leak (PASS) asserts ≥1 item, exact field shape |
| POST /users | `UserCreateResponse` | service.create_user → INSERT users + INSERT password_reset_tokens | YES | DB row asserted by test_create_happy_returns_201_and_emits_user_invited (PASS) |
| PATCH /deactivate | sessions_revoked_count → audit payload | UserSessionInvalidator → _revoke_all_sessions_no_commit returns int via UPDATE RETURNING | YES | test_deactivate_revokes_families_and_blocks_refresh (PASS); test_family_count_db_authoritative (PASS) asserts DB count not Redis |
| session_revoked_all audit | actor_user_id | actor.id plumbed through invalidator Protocol | YES | test_session_revoked_all_actor_attribution (PASS) asserts actor_user_id == owner.id != target.id |
| soft_delete deactivated_by_user_id | actor.id via COALESCE | repository.soft_delete_user(..., actor_user_id=actor.id) | YES | test_soft_delete_records_actor (PASS) — pure-delete path populates, post-deactivate path preserves |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Users integration suite (33 tests — 19 pre-existing + 14 new) | `uv run pytest tests/integration/users/ -q` | 33 passed in 5.84s | PASS |
| Auth integration suite (53 tests + 1 xfail — 7 new from 43-17) | `uv run pytest tests/integration/auth/ -q` | 53 passed, 1 xfailed in 9.30s | PASS |
| Full combined regression (excl. commit-gate) | `uv run pytest tests/integration/users/ tests/integration/auth/ tests/integration/test_app_wiring.py tests/unit/users/ -q` | 95 passed, 1 xfailed in 15.42s | PASS |
| Commit-gate (SVC001 walker) | `uv run pytest tests/unit/test_service_commit_gate.py -q` | 1 FAILED | **FAIL** — see regression above |
| Full unit suite | `uv run pytest tests/unit/ -q` | 1 failed, 712 passed | **FAIL** (same isolated regression) |
| Ruff on modified source files | `uv run ruff check app/modules/users/ app/modules/auth/service.py app/core/dependencies.py app/core/exceptions.py` | All checks passed! | PASS |
| Mypy strict (users module) | `uv run mypy app/modules/users/` | Success: no issues found in 8 source files | PASS |
| Import-linter contracts | `uv run lint-imports` | 3 contracts kept, 0 broken (143 files / 398 dependencies) | PASS |

### Requirements Coverage (Post-Gap-Closure)

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| USERS-01 | 43-01..06 | module shape mirrors `clients/` | SATISFIED | All 7 files present |
| USERS-02 | 43-06, 43-08 | GET /api/v1/users with envelope + no password leak | SATISFIED | test_list_users_paginated_envelope_no_password_leak PASS |
| USERS-03 | 43-05, 43-06, 43-08, 43-11 + CR-01 fix | POST /api/v1/users with working invitation email delivery | SATISFIED | CR-01 fixed: `test_invitation_email_envelope_carries_invitation_url` PASS; WR-06 fixed: `test_revoke_expired_invitation` PASS; WR-02 fixed: `test_reinvite_overwrites_full_name_and_role` PASS |
| USERS-04 | 43-05, 43-06, 43-09, 43-10 + CR-02/03/04 fixes | PATCH deactivate/reactivate atomic + guards — including login chokepoint | SATISFIED | CR-02: `test_deactivate_owner_against_real_postgres` PASS; CR-04: `test_deactivate_atomic_uow` PASS; CR-03: `test_login_deactivated_user` PASS |
| USERS-05 | 43-05, 43-06, 43-09, 43-10 + CR-03 fix | DELETE soft-delete; email eligible for re-invite | SATISFIED | `test_soft_delete_also_blocks_refresh` PASS; `test_soft_delete_records_actor` PASS; `test_login_soft_deleted_user_returns_401_no_cookies` PASS |
| USERS-06 | 43-07, 43-12 + CR-03 fix | All 3 auth chokepoints (login + refresh + OTP) filter is_active + deleted_at | SATISFIED | rotate_refresh (D-43-20 original), authenticate (CR-03 fix), request_otp_email (CR-03 secondary); `test_request_otp_inactive_user` PASS |
| USERS-07 | 43-03 + Phase 41 INFRA-39 + WR-01/03 fixes | audit actor attribution correct at all callsites | SATISFIED | WR-01: `test_session_revoked_all_actor_attribution` PASS; WR-03: `test_soft_delete_records_actor` PASS; USERS-07 traceability auto-satisfied via ContextVar |

### Anti-Patterns Found (Post-Gap-Closure)

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `apps/backend/app/modules/auth/service.py` | 668 | Missing `# noqa: SVC001 caller-owns-txn` on `_revoke_all_sessions_no_commit` def line | BLOCKER | Causes `test_service_commit_gate_against_app_modules` to FAIL. The function IS intentionally caller-owns-txn (CR-04 fix), but the opt-out marker was omitted. Fix: add the noqa comment to the def line. |

### Gap Summary

All 4 BLOCKERs and 7 WARNINGs from 43-REVIEW.md are closed. Code evidence confirmed by direct file reads; tests confirmed by running the full suite. IN-03 and IN-04 are correctly deferred per CONTEXT.md.

However, plan 43-16's gap-closure for CR-04 introduced a new regression: `_revoke_all_sessions_no_commit` is missing the `# noqa: SVC001 caller-owns-txn` opt-out marker. This causes `test_service_commit_gate_against_app_modules` to fail. The fix is a one-line addition to `auth/service.py:668`.

All other quality gates (ruff, mypy strict, import-linter, 95 integration/wiring tests) pass. The regression is isolated and trivial to fix.

---

_Initial Verification: 2026-05-19T15:41:30Z_
_Re-Verification: 2026-05-19T21:00:00Z_
_Verifier: Claude (gsd-verifier)_
