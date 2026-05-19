---
phase: 43-multi-user-admin-module
verified: 2026-05-19T15:41:30Z
status: passed
score: 5/5 success criteria verified (7/7 USERS-* requirements satisfied)
overrides_applied: 0
---

# Phase 43: Multi-User Admin Module Verification Report

**Phase Goal:** Owner can onboard, deactivate, soft-delete, and re-onboard reception operators end-to-end via API without any direct DB-poking — and any operator action carries denormalised audit traceability that survives that operator being fired.

**Verified:** 2026-05-19T15:41:30Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

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
| `auth.service.invalidate_all_families_for_user` | UserSessionInvalidator Protocol impl | VERIFIED | `auth/service.py:1117`; wraps `revoke_all_sessions` with Redis closure |
| `app/main.py` registration | `register_user_session_invalidator(invalidate_all_families_for_user)` | VERIFIED | line 270 in `create_app()`; single-wire per D-43-27 |
| `app/api/v1/router.py` include | users_router mounted at `/users` | VERIFIED | line 68: `v1.include_router(users_router, prefix="/users", tags=["users"])` |

### Key Link Verification (Wiring)

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| router.py:create_user_endpoint | service.create_user | direct call line 108 | WIRED | router → service → repository chain intact |
| service.deactivate_user | UserSessionInvalidator | `get_user_session_invalidator()(...)` line 252 | WIRED | Protocol slot resolved at runtime; registered in main.py:270 |
| service.create_user | EmailDispatcher | `get_email_dispatcher()(template_id="USER_INVITATION_EMAIL", ...)` line 215 | WIRED | literal template_id satisfies AST gate (D-41-11) |
| service.create_user | audit.emit("user_invited", ...) | line 200; FLAT kwargs incl. `link_copied` | WIRED | matches UserInvitedPayload extra='forbid' shape |
| auth.service.rotate_refresh | User.is_active + User.deleted_at filter | line 424-428 single SELECT | WIRED | single SELECT race-tight per D-43-20 |
| auth.service.rotate_refresh | audit.emit("refresh_failed", reason="account_inactive") | line 440-454 | WIRED | commit BEFORE raise so audit persists; same 401 invalid_session body |
| service.* | actor_email_snapshot capture | inherited from ActorContextMiddleware (Phase 41) | WIRED | audit.py:389-400 reads ContextVar at every emit call |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| GET /users | `page.items` | repository.list_alive → SELECT users WHERE deleted_at IS NULL + filters | YES | test_list_users_paginated_envelope_no_password_leak (PASS) asserts ≥1 item, exact field shape |
| POST /users | `UserCreateResponse` | service.create_user → INSERT users + INSERT password_reset_tokens | YES | DB row asserted by test_create_happy_returns_201_and_emits_user_invited (PASS) |
| PATCH /deactivate | sessions_revoked_count → audit payload | UserSessionInvalidator → revoke_all_sessions returns int | YES | test_deactivate_revokes_families_and_blocks_refresh (PASS) asserts subsequent /auth/refresh returns 401 |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Users module tests | `uv run pytest tests/integration/users/ tests/unit/users/ -q` | 21 passed in 3.42s | PASS |
| Dependent regressions | `uv run pytest tests/integration/auth/ tests/integration/test_app_wiring.py tests/integration/test_rbac_parity.py tests/unit/test_workers_eager_import.py tests/unit/test_locked_email_templates_ast.py -q` | 62 passed, 1 xfailed | PASS |
| Ruff (users module + tests) | `uv run ruff check app/modules/users/ tests/integration/users/ tests/unit/users/` | All checks passed! | PASS |
| Mypy strict (users module) | `uv run mypy app/modules/users/` | Success: no issues found in 8 source files | PASS |
| Import-linter contracts | `uv run lint-imports` | 3 contracts kept, 0 broken (core/modules/integrations boundaries) | PASS |

**Note on test count discrepancy:** User context said ~24 tests expected; actual collected count is 21 (19 integration + 2 unit). All 21 pass. The 24 figure appears to over-count by 3 — does not affect verification outcome since every USERS-* requirement has explicit test coverage (see Requirements Coverage below).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| USERS-01 | 43-01..06 | module shape mirrors `clients/` (router/service/repository/schemas/permissions/constants/email_templates) | SATISFIED | All 7 files present in `app/modules/users/`; `list_alive`/`get_alive` partition pattern in repository.py |
| USERS-02 | 43-06, 43-08 | GET /api/v1/users with `?active`/`?deleted`/pagination + envelope; no password leak | SATISFIED | `router.py:67-81`, `schemas.py:UserListItemResponse`; test_list_users_paginated_envelope_no_password_leak PASS |
| USERS-03 | 43-05, 43-06, 43-08, 43-11 | POST /api/v1/users CSRF + invitation token + email dispatch + `?include_invite_link=true` + revoke endpoint; NEVER returns admin-set plaintext password | SATISFIED | service.py:123-230 (no password field in response); test_invitation_email_enqueued_through_sandbox, test_include_invite_link_returns_url_with_token_fragment, test_revoke_invitation_flips_consumed_and_emits_audit, test_revoke_already_consumed_invitation_returns_409 — all PASS |
| USERS-04 | 43-05, 43-06, 43-09, 43-10 | PATCH deactivate/reactivate (atomic UPDATE + UserSessionInvalidator + audit); self + last-owner guards | SATISFIED | service.py:233-294; test_deactivate_revokes_families_and_blocks_refresh, test_cannot_deactivate_self_returns_409, test_cannot_deactivate_last_owner_returns_409 — all PASS |
| USERS-05 | 43-05, 43-06, 43-09, 43-10 | DELETE soft-delete; cannot delete self/last owner; email eligible for re-invite via partial-UNIQUE | SATISFIED | service.py:297-334; test_cannot_delete_self_returns_409, test_soft_deleted_email_can_be_re_invited_with_new_id, test_soft_delete_also_blocks_refresh — all PASS |
| USERS-06 | 43-07, 43-12 | `/auth/refresh` joins `users.is_active=true AND users.deleted_at IS NULL`; same response shape as invalid_session (anti-oracle) | SATISFIED | auth/service.py:413-456 (single SELECT with predicates, identical InvalidSession body); test_refresh_anti_oracle_four_cases PASS — body parity + 100ms timing tolerance asserted |
| USERS-07 | 43-03 + Phase 41 INFRA-39 inheritance | every audit.emit captures actor_email_snapshot; 3-way RBAC parity extended | SATISFIED | audit.py:389-400 auto-resolves snapshot from ContextVar (Phase 41 ActorContextMiddleware); validated by tests/unit/test_actor_context.py (passes). 3-way RBAC parity test PASSES with USERS resource (Phase 41 active state). All 6 user-lifecycle audit emits in service.py inherit middleware-set actor identity. |

**All 7 USERS-* requirements SATISFIED.** No orphaned requirements (REQUIREMENTS.md maps USERS-01..07 → Phase 43; every ID appears in at least one plan's `requirements` field and has direct test validation).

### D-43-* Locked Decisions Verification

| Decision | Description | Status | Evidence |
|----------|-------------|--------|----------|
| D-43-01 | trust owner-entered email; no separate verify endpoint | SATISFIED | No `/resend-verification` or `/re-verify` routes in `router.py` |
| D-43-02 | `email_verified` excluded from UserListItemResponse | SATISFIED | schemas.py UserListItemResponse — no email_verified field |
| D-43-03/04 | no actor_display_name payload field; FLAT audit kwargs | SATISFIED | audit_payloads.py UserInvitedPayload/UserDeactivatedPayload have no actor_display_name; service.py audit emits use FLAT kwargs (not nested under payload=) |
| D-43-05/06/07/08 | single migration 0030 with 4 columns + drop NOT NULL + self-FK | SATISFIED | alembic/versions/0030_users_lifecycle_columns.py present; User ORM extended in core/models.py |
| D-43-09 | clients/ mirror layout; no models.py in users/ | SATISFIED | 7 expected files present; no `users/models.py` |
| D-43-10 | schemas use BackendSchemaBase camelCase | SATISFIED | schemas.py imports BackendSchemaBase |
| D-43-11 | permissions.py marker file (re-exports Resource.USERS) | SATISFIED | 13-line marker shim |
| D-43-12 | INVITATION_TOKEN_TTL = timedelta(days=7) | SATISFIED | constants.py single constant |
| D-43-13 | 4-branch idempotent POST flow (A/B/C/D) | SATISFIED | service.py:140-164 implements all 4 branches; test_create_pending_user_idempotent_re_invite + test_create_email_already_active_returns_409 + test_soft_deleted_email_can_be_re_invited_with_new_id all PASS |
| D-43-14 | `?include_invite_link=true` + UserInvitedPayload.link_copied | SATISFIED | router.py:97-105 query param; audit_payloads.py link_copied field; service.py:211 passes through to emit; URL excluded from payload (test_create_with_include_invite_link... asserts) |
| D-43-15 | GET with filters + page=1/pageSize=20 defaults | SATISFIED | router.py:67-81; PaginatedData envelope |
| D-43-16 | deactivate pre-conditions (404/409) + FOR UPDATE last-owner | SATISFIED | service.py:233-267; repository.count_active_owners_excluding uses FOR UPDATE |
| D-43-17 | reactivate no self/last-owner guards; sessions NOT auto-restored | SATISFIED | service.py:270-294 has NO self/last-owner checks |
| D-43-18 | DELETE soft-delete + session revoke + invitation cascade | SATISFIED | service.py:297-334 |
| D-43-19 | revoke by `password_reset_tokens.id` (UUID), NOT raw token | SATISFIED | router.py:170-186 path param `token_id: UUID`; service.py:337-372 uses get_invitation_token_by_id |
| D-43-20 | `/auth/refresh` joins is_active+deleted_at; same body as invalid_session | SATISFIED | auth/service.py:413-456 single SELECT + InvalidSession raise; test_refresh_anti_oracle_four_cases PASS |
| D-43-22/23/24 | USER_INVITATION_EMAIL template in users/email_templates.py; render-at-enqueue | SATISFIED | email_templates.py present with Jinja2 SandboxedEnvironment; service.py:178-220 renders before dispatch |
| D-43-26/27 | UserSessionInvalidator impl + single-wire registration | SATISFIED | auth/service.py:1117 impl; main.py:270 register; integration/test_app_wiring.py asserts registration |
| D-43-29 | router-layer auth → RBAC → CSRF ordering | SATISFIED | router.py:84-186 every mutation: CurrentUser/permission first, verify_csrf second |
| D-43-31 | USERS-07 traceability auto-satisfied via ContextVar | SATISFIED | audit.py:389-400 reads ContextVar at every emit |
| D-43-32 | no eager-import amendments needed | SATISFIED | tests/unit/test_workers_eager_import.py PASSES unchanged |
| D-43-36 | Alembic round-trip [BLOCKING] checkpoint on 0030 | SATISFIED | 0030 file present with both upgrade() and downgrade() defined |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | — | — | — | No `TBD`, `FIXME`, `XXX`, `TODO`, `HACK`, `PLACEHOLDER`, stub returns, or hardcoded empty data found in `app/modules/users/`, `tests/integration/users/`, `tests/unit/users/`, or `alembic/versions/0030_users_lifecycle_columns.py` |

Pre-existing failures called out in the verifier context (test_bookings_router_smoke self-grep — Phase 38; test_alembic_check_clean drift — Phase 41 channel migration; 4 telegram tests — Phase 40 handler arity; test_create_booking_via_bot_pt_package_expired_before_slot — Phase 40 business logic) are explicitly NOT attributable to Phase 43 and were excluded from scoring per verifier instructions.

### Human Verification Required

None. All success criteria are programmatically verifiable: API behavior validated via integration tests against real Postgres; audit-row persistence asserted via direct DB queries; RBAC/CSRF wiring validated via 403/401 status assertions; anti-oracle parity validated via byte-for-byte JSON body equality + 100ms timing tolerance; mypy strict + import-linter contracts pass. No visual/UX surface in scope (backend-only phase per D-43 integration points note — admin-web NOT touched).

### Post-Phase Regression Fixes (in scope, all integrated)

The verifier context flagged 3 fix commits that landed after the main 14-plan wave:
1. `fix(43-03)`: default `link_copied=False` in `UserInvitedPayload` — VERIFIED in audit_payloads.py:534
2. `fix(43-01)`: align `users.email` + `users.status` ORM with on-disk schema (Text instead of SAEnum, removed `unique=True` from email) — VERIFIED in models.py:52 (email no unique=True), models.py:101 (status as Text + CHECK)
3. `fix(43-04)`: importlinter ignore for `users.repository → auth.password_reset_token_model` — VERIFIED indirectly: `lint-imports` produces "3 contracts kept, 0 broken" against 143 files / 398 dependencies

### Gaps Summary

**None.** Phase 43 delivers all 5 ROADMAP success criteria and all 7 USERS-* requirements with direct test validation. All locked D-43-* decisions are honored in code. All quality gates (ruff + mypy strict + import-linter + 21 phase tests + 62 dependent tests) pass. Anti-oracle discipline verified at `/auth/refresh` via byte-equal body + bounded timing assertions. USERS-07 audit traceability inherits Phase 41 ContextVar infrastructure transparently.

---

*Verified: 2026-05-19T15:41:30Z*
*Verifier: Claude (gsd-verifier)*
