# Roadmap: Sportzal

## Milestones

- ✅ **v1.0 Phase A: Skeleton** — Phases 1-3 (shipped 2026-05-01) — see [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- ✅ **v1.1 Auth + Clients** — Phases 4-14 (shipped 2026-05-07) — see [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)
- ✅ **v1.2 Memberships + Visits** — Phases 15-23 (shipped 2026-05-08) — see [milestones/v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md)
- ✅ **v1.3 Memberships Extras + Tech-Debt** — Phases 24-29 (shipped 2026-05-14) — see [milestones/v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md)
- ✅ **v1.4 Cash Sales + PT Packages** — Phases 30-36 (shipped 2026-05-16) — see [milestones/v1.4-ROADMAP.md](milestones/v1.4-ROADMAP.md)
- ✅ **v1.5 Schedule + Bookings (PT slots)** — Phases 37-40 (shipped 2026-05-18) — see [milestones/v1.5-ROADMAP.md](milestones/v1.5-ROADMAP.md)
- 🚧 **v1.6 Email channel + Multi-user admin** — Phases 41-46 (active, opened 2026-05-18)

## Phases

<details>
<summary>✅ v1.0 Phase A: Skeleton (Phases 1-3) — SHIPPED 2026-05-01</summary>

- [x] Phase 1: Monorepo Restructure & Frontend Move (3/3 plans) — completed 2026-04-30
- [x] Phase 2: Backend Skeleton with Quality Tooling (8/8 plans) — completed 2026-04-30
- [x] Phase 3: Tests, Dev Infrastructure & Documentation (6/6 plans) — completed 2026-05-01

Full details: [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)

</details>

<details>
<summary>✅ v1.1 Auth + Clients (Phases 4-14) — SHIPPED 2026-05-07</summary>

- [x] Phase 4: Auth Foundations & Cookie/RBAC Primitives (9/9 plans) — completed 2026-05-02
- [x] Phase 5: User Schema + Email/Password Auth (8/8 plans) — completed 2026-05-03
- [x] Phase 6: RBAC Wiring + Parity Tests (5/5 plans) — completed 2026-05-03
- [x] Phase 7: Telegram OTP Channel (8/8 plans) — completed 2026-05-04
- [x] Phase 8: Clients Module + Audit Log (8/8 plans) — completed 2026-05-04
- [x] Phase 9: OpenAPI Pipeline + packages/api-client (3/3 plans) — completed 2026-05-04
- [x] Phase 10: admin-web Auth + Clients Wiring (8/8 plans) — completed 2026-05-04
- [x] Phase 11: Clients HTTP-mode Shape Adapter *(gap closure)* (2/2 plans) — completed 2026-05-04
- [x] Phase 12: v1.1 Verification Backfill *(gap closure)* (5/5 plans) — completed 2026-05-05
- [x] Phase 12.1: Clients Service Commit Fix *(inline quick-fix `260504-fst`, commit ba14aba)* — completed 2026-05-04
- [x] Phase 13: v1.1 Minor Drift & Hygiene Cleanup *(gap closure)* (4/4 plans) — completed 2026-05-05
- [x] Phase 14: Clients Search PII Hardening *(gap closure, security)* (3/3 plans) — completed 2026-05-07

Full details: [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)

</details>

<details>
<summary>✅ v1.2 Memberships + Visits (Phases 15-23) — SHIPPED 2026-05-08</summary>

- [x] Phase 15: Foundations — RBAC + audit taxonomy + helper hoisting (5/5 plans) — completed 2026-05-07
- [x] Phase 16: Membership Plans Catalog (backend) (5/5 plans) — completed 2026-05-07
- [x] Phase 17: Membership Instances + Resolver (backend) (5/5 plans) — completed 2026-05-07
- [x] Phase 18: ARQ scheduled `expire_memberships` (6/6 plans) — completed 2026-05-07
- [x] Phase 19: Visits — DB + reception check-in (backend) (5/5 plans) — completed 2026-05-07
- [x] Phase 20: Telegram bot `/checkin` self check-in (3/3 plans) — completed 2026-05-08
- [x] Phase 21: OpenAPI drift gate refresh + api-client codegen (1/1 plan) — completed 2026-05-08
- [x] Phase 22: admin-web wiring — memberships + visits + active sessions UI (5/5 plans) — completed 2026-05-08
- [x] Phase 23: Hygiene + active sessions backend *(parallel-eligible)* (1/1 plan) — completed 2026-05-08

Full details: [milestones/v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md)

</details>

<details>
<summary>✅ v1.3 Memberships Extras + Tech-Debt (Phases 24-29) — SHIPPED 2026-05-14</summary>

- [x] Phase 24: Foundations & Tech-Debt Bedrock (5/5 plans) — completed 2026-05-08 — INFRA-15/16 + DEBT-01/02/03
- [x] Phase 25: Memberships — Freeze (backend) (5/5 plans) — completed 2026-05-09 — MEM-FRZ-01..07 + EP-01..03 + AUDIT-01 + TEST-01..03
- [x] Phase 26: Memberships — Renewal (backend) (4/4 plans) — completed 2026-05-09 — MEM-REN-01..04 + EP-01 + AUDIT-01 + TEST-01..04
- [x] Phase 27: Expiring-soon Telegram Notifications (5/5 plans) — completed 2026-05-09 — NTF-01..06 + COPY-01 + TEST-01..03
- [x] Phase 28: OpenAPI Drift-Gate Refresh + admin-web Wiring (8/8 plans) — completed 2026-05-10 — FE-10/11/12/13 *(1 mock-parity gap deferred to v1.4)*
- [x] Phase 29: Milestone Verification (6/6 plans) — completed 2026-05-14 — DEBT-04 *(7/7 scenarios passed; 3 inline blocker fixes; see milestones/v1.3-VERIFICATION-LOG.md)*

Full details: [milestones/v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md)

</details>

<details>
<summary>✅ v1.4 Cash Sales + PT Packages (Phases 30-36) — SHIPPED 2026-05-16</summary>

- [x] Phase 30: Foundations & Tech-Debt Bedrock (4/4 plans) — completed 2026-05-14 — INFRA-17/18/19/20/21/22/23 + DEBT-05
- [x] Phase 31: Trainers Module (2/2 plans) — completed 2026-05-14 — TRN-01..08
- [x] Phase 32: Payment Ledger + Sale Flow + Refund (3/3 plans) — completed 2026-05-15 — PAY-01..10 + REF-01..08
- [x] Phase 33: PT-Package Plans + Instances (3/3 plans) — completed 2026-05-15 — PT-01..13
- [x] Phase 34: PT-Session Recording (3/3 plans) — completed 2026-05-16 — PT-14..22
- [x] Phase 35: OpenAPI Drift Gate (backend-only handoff) (2/2 plans) — completed 2026-05-16 — FE-10 *(FE-11..18 descoped to v2.0 — design team owns production frontends)*
- [x] Phase 36: Milestone Verification (backend-only) (5/5 plans) — completed 2026-05-16 — VER-01..04 *(8/8 scenarios + 20/20 race + 4/4 CI gates passed; 5 inline regression fixes; 44 pre-existing pytest failures → DEFER-36-04-A; see milestones/v1.4-VERIFICATION-LOG.md)*

Full details: [milestones/v1.4-ROADMAP.md](milestones/v1.4-ROADMAP.md)

</details>

<details>
<summary>✅ v1.5 Schedule + Bookings (Phases 37-40) — SHIPPED 2026-05-18</summary>

- [x] Phase 37: Foundations Bedrock (5/5 plans) — completed 2026-05-17 — INFRA-24..28 + RBAC/audit/Protocol-slot setup for schedule + bookings
- [x] Phase 38: Schedule Module + Booking Core (6/6 plans) — completed 2026-05-17 — SLOT-01..09 + BOOK-01..10 + PKG-01..06 (partial UNIQUE race, FSM, validity-window guard)
- [x] Phase 39: Notifications + Cron (4/4 plans) — completed 2026-05-18 — NOTIFY-01..05 + CRON-01..05 (Russian DMs, `booking_notifications` idempotency, 23:10 no-show + 06:35 reminder crons)
- [x] Phase 40: Telegram /book + OpenAPI + Verification (5/5 plans) — completed 2026-05-18 — BOT-01..05 + HANDOFF-01..02 + VER-05..08 *(`create_booking_via_bot` self-service entry, Alembic 0021 nullable, +11 AssertNonNever forward-guards, byte-stable openapi.json regen; minimal live-Postgres verification PASS for the 6 Phase 40 surface invariants; full 10-scenario operator runbook deferred to v1.9 as DEFER-40-01 — see milestones/v1.5-VERIFICATION-LOG.md)*

Full details: [milestones/v1.5-ROADMAP.md](milestones/v1.5-ROADMAP.md)

</details>

<details open>
<summary>🚧 v1.6 Email channel + Multi-user admin (Phases 41-46) — ACTIVE (opened 2026-05-18)</summary>

- [ ] **Phase 41: INFRA Bedrock + Anti-Oracle Scaffold** — Pre-register audit taxonomy, RBAC additions, schema migrations, Protocol slots, and the anti-oracle reset-flow test BEFORE any feature callsite lands (v1.3 INFRA-15 + Pitfall 1 discipline). INFRA-34..40 + RESET-06.
- [ ] **Phase 42: Email Transport Layer + Email OTP Fallback** — Channel-agnostic outbound email transport (provider adapter, ARQ dispatch task, DNS runbook, circuit breaker, bounce webhook) plus email-channel OTP fallback for `/auth/otp/request`. EMAIL-01..07 + AUTH-EM-01..04.
- [ ] **Phase 43: Multi-User Admin Module** — New `app/modules/users/` (owner-managed CRUD, soft-delete, deactivate-with-session-revoke, multi-user audit traceability). USERS-01..07.
- [x] **Phase 44: Invitation + Password-Reset Flow** — Anti-oracle `password-reset/request`, atomic-consume `password-reset/confirm`, invitation accept (INSERT-only re-claim), revoke. RESET-01..05.
- [ ] **Phase 45: Email Notification Mirrors** — Channel-discriminator migration, email fallback for expiring + booking reminders, payment-receipt email, locked Russian email templates with owner sign-off. NOTIFY-06..14.
- [ ] **Phase 46: OpenAPI Handoff + Milestone Verification** — Byte-stable spec + `schema.d.ts` regen with new v1.6 paths, forward-guards 61 → ~73, then live-stack operator runbook + race tests + email-deliverability probe + 6/6 CI gates green + owner sign-off (DEFER-40-01 lesson — budget runbook scaffolding hardening). HANDOFF-03..04 + VER-09..14.

### Phase 41: INFRA Bedrock + Anti-Oracle Scaffold
**Goal**: All v1.6 audit events, RBAC additions, schema migrations, Protocol-slot scaffolding, and the anti-oracle reset-flow test exist BEFORE the first feature callsite lands — closing the AST-gate-churn class (v1.3 INFRA-15 lesson) and the Pitfall 1 anti-oracle regression class up-front.
**Depends on**: Nothing (first phase of v1.6; baseline = shipped v1.5 codebase at Phase 40)
**Requirements**: INFRA-34, INFRA-35, INFRA-36, INFRA-37, INFRA-38, INFRA-39, INFRA-40, RESET-06
**Success Criteria** (what must be TRUE):
  1. `LOCKED_AUDIT_EVENTS` frozenset grows 56 → 67 with the 11 v1.6 event names pre-registered, every entry has a matching Pydantic payload schema (`extra='forbid'`) in `audit_payloads.py`, and a synthetic `audit.emit("bogus_v16_event", ...)` AST violation fixture fails CI.
  2. A new `LOCKED_EMAIL_TEMPLATES` AST gate exists in `app/core/audit.py` (or sibling); a synthetic violation that calls `get_email_dispatcher()(...)` with a raw string-literal subject is rejected by CI.
  3. The three-way RBAC parity test (backend ↔ admin-web `can.ts` ↔ `registry.ts`) passes with `Resource.USERS` and `(CREATE|UPDATE|DELETE|LIST, USERS)` added to `OWNER_ONLY` (26 → 30 entries); reception holds zero USERS permissions.
  4. `alembic upgrade head` against a clean dev database applies: `users.deleted_at` + partial-UNIQUE `(lower(email)) WHERE deleted_at IS NULL`; `audit_log.actor_email_snapshot TEXT NULL` + FK `actor_user_id ON DELETE SET NULL`; cross-channel `channel TEXT NOT NULL DEFAULT 'telegram' CHECK (...)` discriminator on `membership_notifications` AND `booking_notifications` with UNIQUE recreated as `(subject_id, kind, channel)`.
  5. `EmailDispatcher` and `UserSessionInvalidator` Protocol types exist in `app/core/dependencies.py` with `register_*` / `get_*` accessors; `app.modules.users` is listed in `.importlinter` `modules-independent`; SVC001 AST commit-gate scope includes `app/modules/users/service.py` AND `app/modules/auth/password_reset_service.py`.
  6. `tests/integration/test_password_reset_no_oracle.py` exists and fails as expected against the not-yet-implemented endpoint (test-first lands before any reset endpoint code per Pitfall 1) — asserting the 4-case identical 202 + identical body + bounded timing contract is in the repo for future phases to satisfy.
**Plans**: 11 plans (waves 1-3)
Plans:
**Wave 1**
- [x] 41-01-PLAN.md — INFRA-34 LOCKED_AUDIT_EVENTS 56→67 + synthetic-violation
- [x] 41-03-PLAN.md — INFRA-36 LOCKED_EMAIL_TEMPLATES frozenset + AST walker + 2 synthetic fixtures
- [x] 41-04-PLAN.md — INFRA-37 Resource.USERS + 4 OWNER_ONLY entries + three-way RBAC parity
- [x] 41-05-PLAN.md — INFRA-38 Alembic 0022 users.deleted_at + partial-UNIQUE on lower(email)
- [x] 41-10-PLAN.md — INFRA-40 User hoist+shim + EmailDispatcher/UserSessionInvalidator Protocol slots + .importlinter + SVC001 scope
- [x] 41-11-PLAN.md — RESET-06 test_password_reset_no_oracle.py (xfail-strict; 4-case identical 202 + body + 100ms timing)

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 41-02-PLAN.md — INFRA-35 11 new Pydantic payload schemas (extra=forbid + audit_correlation_id)
- [x] 41-06-PLAN.md — INFRA-39 Alembic 0023 audit_log.actor_email_snapshot + FK ON DELETE SET NULL
- [x] 41-08-PLAN.md — INFRA-38 Alembic 0024 cross-channel discriminator on membership_/booking_notifications

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 41-07-PLAN.md — INFRA-39 actor_context_var + ActorContextMiddleware + ARQ on_job_start/end + audit.emit wiring
- [x] 41-09-PLAN.md — INFRA-38 Alembic 0025 password_reset_tokens unified table + ORM + eager-import

### Phase 42: Email Transport Layer + Email OTP Fallback
**Goal**: Sportzal can send a transactional email asynchronously through a verified РФ-domiciled provider end-to-end, with circuit-breaker protection, bounce-webhook intake, and an immediate consumer (email-channel OTP fallback for `/auth/otp/request`) proving the slot wiring works.
**Depends on**: Phase 41 (uses `LOCKED_EMAIL_TEMPLATES` AST gate, `EmailDispatcher` slot declaration, `LOCKED_AUDIT_EVENTS` pre-registration, INFRA-39 audit snapshot column, eager-import discipline)
**Requirements**: EMAIL-01, EMAIL-02, EMAIL-03, EMAIL-04, EMAIL-05, EMAIL-06, EMAIL-07, AUTH-EM-01, AUTH-EM-02, AUTH-EM-03, AUTH-EM-04
**Success Criteria** (what must be TRUE):
  1. Operator can run `docker compose up`, trigger an OTP request via `POST /api/v1/auth/otp/request {channel: 'email'}` against a sandbox provider, and observe (a) an `email_sent` audit row with `audit_correlation_id`, (b) the 6-digit code arriving in the sandbox inbox via the locked `EMAIL_OTP_LOGIN` template, (c) successful `/auth/otp/verify` completion.
  2. A user with no Telegram + a verified email AND a user without verified email both receive the same anti-oracle 202 response shape from `POST /auth/otp/request {channel: 'email'}` (no oracle leak); `test_otp_email_anti_oracle.py` (AUTH-EM-04) passes.
  3. The `EmailDispatcher` Protocol slot is double-wired in BOTH `app/main.py:create_app()` AND `app/workers/__init__.py:WorkerSettings.on_startup` (REG-29-03 parity test asserts both call sites register identical implementations); ARQ task `dispatch_email` is registered with `max_tries=2, timeout=20`.
  4. When the provider returns 5xx for 5 consecutive calls, the Redis circuit breaker opens (`sz:email:circuit:{provider}` TTL 5m), subsequent `dispatch_email` jobs short-circuit to `EmailSendResult.transient_error` without touching the provider, and the 06:15 → 06:35 cron window completes within budget.
  5. `infra/dns/sportzal.ru.zone` documents SPF/DKIM/DMARC records for the dedicated email subdomain with `p=none` initial policy and DMARC `rua` reports addressed to the owner; the Pydantic `EmailProviderSettings` validator fails fast at boot if `from_domain` is empty in non-sandbox mode AND the boot-time `/domains` probe asserts domain verification.
  6. `POST /api/v1/_internal/email/webhook` rejects unsigned bodies in O(1) time via `hmac.compare_digest` BEFORE body parsing; valid signed bounce/complaint payloads append to `email_send_log` with classification.
**Plans**: 16 plans (waves 1-6); plans 42-12..42-16 are gap-closure plans created 2026-05-19 to address VERIFICATION.md CR-01..04 + WR hygiene
Plans:
**Wave 1**
- [x] 42-01-PLAN.md — EMAIL-01/07 EmailEnvelope + EmailSendResult types + EmailSendLog ORM + Alembic 0026 + env.py registration
- [x] 42-02-PLAN.md — EMAIL-02 EmailProviderSettings Pydantic block + fail-fast validator
- [x] 42-03-PLAN.md — AUTH-EM-01 Alembic 0027 otp_codes.channel discriminator + ORM column + partial-UNIQUE recreate
- [x] 42-04-PLAN.md — AUTH-EM-02 Alembic 0028 users.email_verified + ORM column + bootstrap-runbook docstring
- [x] 42-05-PLAN.md — AUTH-EM-03 app/modules/auth/email_templates.py with EMAIL_OTP_LOGIN (Jinja2 SandboxedEnvironment) + jinja2 dep pin
- [x] 42-06-PLAN.md — EMAIL-05 infra/dns/sportzal.ru.zone SPF/DKIM/DMARC operator runbook (p=none baseline)

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 42-07-PLAN.md — EMAIL-01/02 EmailClient aioboto3 adapter + SandboxEmailClient stub + build_email_client factory + boot-time /domains probe
- [x] 42-08-PLAN.md — EMAIL-03/06 enqueue_email_dispatch + _resolve_template walker + Redis circuit breaker + ARQ dispatch_email task

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 42-09-PLAN.md — EMAIL-03/04 + AUTH-EM-02/03 REG-29-03 double-wire + OtpRequestBody channel discriminator + /auth/otp/request route + request_otp_email anti-oracle service
- [x] 42-10-PLAN.md — EMAIL-07 POST /api/v1/_internal/email/webhook HMAC-before-parse bounce/complaint handler

**Wave 4** *(blocked on Wave 3 completion)*
- [x] 42-11-PLAN.md — AUTH-EM-04 + REG-29-03/04 tests: test_otp_email_anti_oracle + test_app_wiring extension + test_workers_eager_import extension + test_locked_email_templates_ast real-callsite assertion

**Wave 5** *(gap-closure — blocked on Wave 4; plans run parallel — zero files_modified overlap pairwise)*
- [ ] 42-12-PLAN.md — CR-01 fix: flatten audit.emit kwargs in dispatch_email.py (both branches) + rewrite unit tests + integration test exercising real audit.emit + audit_log query (EMAIL-03)
- [ ] 42-13-PLAN.md — CR-02 fix: _constant_time_floor try/finally on request_otp_telegram + extend test_otp_email_anti_oracle.py to include case B in body+timing parity (AUTH-EM-02, AUTH-EM-04)
- [ ] 42-14-PLAN.md — CR-03 fix: atomic Redis pipeline in circuit_breaker.record_failure + concurrency test under asyncio.gather (EMAIL-06)
- [x] 42-15-PLAN.md — CR-04 fix: defensive UPDATE pass in migration 0027 + docstring + regression test seeding colliding rows; includes [BLOCKING] alembic round-trip checkpoint (AUTH-EM-01)

**Wave 6** *(hygiene bundle — blocked on Wave 5; depends_on [12, 13] for dispatch_email.py + service.py overlap)*
- [x] 42-16-PLAN.md — WR-01/02/03/04/06 hygiene: migration 0029 (bounce_type CHECK + status circuit_open) + dispatch_email status taxonomy + webhook orphan event name + email_lower at dispatcher + HMAC strip/lower; includes [BLOCKING] alembic round-trip checkpoint (EMAIL-03/06/07, AUTH-EM-02)

**Cross-cutting constraints:**
- alembic upgrade head + downgrade -1 + upgrade head round-trips clean

### Phase 43: Multi-User Admin Module
**Goal**: Owner can onboard, deactivate, soft-delete, and re-onboard reception operators end-to-end via API without any direct DB-poking — and any operator action carries denormalised audit traceability that survives that operator being fired.
**Depends on**: Phase 41 (uses `Resource.USERS` + `OWNER_ONLY`, `users.deleted_at` partial-UNIQUE migration, `actor_email_snapshot` migration, `UserSessionInvalidator` slot declaration, SVC001 scope extension, `.importlinter` users-listing); independent of Phase 42 (USERS-03 invitation email enqueues via the Phase-41-declared `EmailDispatcher` slot — actual email delivery is satisfied once Phase 42 lands, but USERS-* surface is testable against an in-memory dispatcher stub)
**Requirements**: USERS-01, USERS-02, USERS-03, USERS-04, USERS-05, USERS-06, USERS-07
**Success Criteria** (what must be TRUE):
  1. Owner can `POST /api/v1/users` with a new operator's `{email, fullName, role}` and observe a 201 response carrying `{id, email, role, invitationExpiresAt}` — never a plaintext password — and a pending-invitation row exists in the database with status `'pending_invitation'`.
  2. Owner can `PATCH /api/v1/users/{id}/deactivate` and observe in a single atomic step that (a) `users.is_active = false` with `deactivated_at` + `deactivated_by_user_id` populated, (b) every refresh-token family for that user is revoked via the `UserSessionInvalidator` slot, (c) a `user_deactivated` audit row exists with `actor_email_snapshot` denormalised — and the deactivated user's next `/auth/refresh` call returns 401 `account_inactive`.
  3. Owner can `DELETE /api/v1/users/{id}` to soft-delete and then `POST /api/v1/users` with the SAME email for a different person — the partial-UNIQUE permits the INSERT, a brand-new `users.id` is generated (never reactivates the soft-deleted row), and historical audit rows from the deleted user still resolve their `actor_email_snapshot`.
  4. Owner attempts to deactivate self → 409 `cannot_deactivate_self`; owner attempts to deactivate the last active owner → 409 `cannot_deactivate_last_owner`; reception attempts any `/api/v1/users/*` mutation → 403 (RBAC three-way parity holds).
  5. `GET /api/v1/users?active=true|false&deleted=false` returns the paginated `{items, total, page, pageSize}` envelope with each item carrying `{id, email, fullName, role, isActive, isDeactivated, createdAt, deactivatedAt, deactivatedByUserId}` — no leak of `passwordHash`, `password_changed_at`, refresh families, or invitation tokens.
**Plans**: 13 plans (waves 1-4)
Plans:
**Wave 1** (parallel — zero files_modified overlap pairwise)
- [x] 43-01-PLAN.md — Alembic 0030 users lifecycle columns + User ORM extension + [BLOCKING] round-trip checkpoint
- [x] 43-02-PLAN.md — users/{schemas, permissions, constants, email_templates} + USER_INVITATION_EMAIL snapshot test
- [x] 43-03-PLAN.md — invalidate_all_families_for_user + main.py registration + UserInvitedPayload.link_copied + RefreshFailedPayload + test_app_wiring extension

**Wave 2** (blocked on Wave 1)
- [x] 43-04-PLAN.md — users/repository.py (list_alive/get_alive/invitation token CRUD)
- [x] 43-05-PLAN.md — users/service.py (4-branch create, deactivate/reactivate/soft-delete/revoke orchestration)
- [x] 43-06-PLAN.md — users/router.py 6 endpoints + RBAC + CSRF + api/v1/router.py include

**Wave 3** (blocked on Wave 2)
- [x] 43-07-PLAN.md — auth.service.rotate_refresh is_active+deleted_at predicate + refresh_failed audit emit

**Wave 4** (blocked on Wave 3 — parallel-eligible test files, zero files_modified overlap pairwise)
- [x] 43-08-PLAN.md — test_users_crud.py (4-branch create + paginated list + denylist)
- [x] 43-09-PLAN.md — test_users_guards.py (self/last-owner/RBAC/CSRF)
- [x] 43-10-PLAN.md — test_users_session_invalidation.py (deactivate→revoke→refresh-fail)
- [x] 43-11-PLAN.md — test_users_invitation_flow.py (sandbox email + invite-link + revoke)
- [x] 43-12-PLAN.md — test_refresh_account_inactive.py (anti-oracle 4-case body+timing parity)
- [x] 43-13-PLAN.md — test_locked_email_templates_ast.py extension (USER_INVITATION_EMAIL real-callsite assertion)

### Phase 44: Invitation + Password-Reset Flow
**Goal**: A pending-invitation user can accept their invitation by setting an initial password via email link; any user can reset their password via email link with full anti-oracle protection; existing operators can revoke outstanding invitations.
**Depends on**: Phase 42 (email transport delivers the link) + Phase 43 (USERS module + `UserSessionInvalidator` slot wired). The Phase 41 `test_password_reset_no_oracle.py` test now goes from RED to GREEN here.
**Requirements**: RESET-01, RESET-02, RESET-03, RESET-04, RESET-05
**Success Criteria** (what must be TRUE):
  1. `POST /api/v1/auth/password-reset/request` returns identical 202 + identical body + bounded-equal timing (within 100ms tolerance) for all 4 cases (existing-active / existing-deactivated / owner-account / non-existent); `password_reset_requested` audit row is emitted in BOTH branches (known and unknown email); the `test_password_reset_no_oracle.py` test from Phase 41 now passes.
  2. `POST /api/v1/auth/password-reset/confirm {token, newPassword}` atomically consumes the token via single-SQL `RETURNING`, updates `users.password_hash`, bumps `users.password_changed_at`, revokes ALL refresh-token families for the user, emits `password_reset_completed` in the same UoW, and returns 200; replay of the same token → 410 Gone with generic copy.
  3. A pending-invitation user can `POST /api/v1/users/invitations/accept {token, password, fullName}` with the token from the invitation email and receive a login cookie pair; if the same email previously belonged to a soft-deleted user, the accept INSERTS a new row (never UPDATEs the soft-deleted row) and emits `user_invitation_accepted` with the new `user_id`.
  4. Invitation tokens TTL = 7 days; password-reset tokens TTL = 1 hour (OWASP 2025 floor); both delivered via URL fragment `#token=...` or POST body — never URL path; `/auth/password-reset/request` rate-limited at 5/15min per IP AND 1/min + 5/hour per email with the same generic 202 on rate-limit hit.
  5. Owner can `POST /api/v1/users/invitations/{id}/revoke` and observe `user_invitation_revoked` audit emission plus the token immediately becomes invalid; revoking an already-accepted invitation returns 409 `invitation_already_accepted`.
**Plans**: 11 plans (waves 1-5)
Plans:
**Wave 1** (parallel — zero files_modified overlap pairwise)
- [ ] 44-01-PLAN.md — PASSWORD_RESET_TOKEN_TTL constant + reset_rate_limit.py 3-key fixed-window (D-44-05/10)
- [ ] 44-02-PLAN.md — PASSWORD_RESET_EMAIL locked Russian template (D-44-OWNER-COPY-LOCK)
- [ ] 44-03-PLAN.md — password_reset_service.py skeleton + 3 new exceptions (D-44-15/17/20)

**Wave 2** (blocked on Wave 1)
- [ ] 44-04-PLAN.md — Fill request_password_reset + confirm_password_reset + accept_invitation bodies (D-44-06..23)

**Wave 3** (blocked on Wave 2)
- [ ] 44-05-PLAN.md — Router endpoints: /auth/password-reset/{request,confirm} + /users/invitations/accept (D-44-18/34)

**Wave 4** (blocked on Wave 3 — parallel-eligible, zero files_modified overlap pairwise)
- [ ] 44-06-PLAN.md — [BLOCKING] Ungate test_password_reset_no_oracle.py + audit-row extension (D-41-17 / D-44-29/30/39)
- [ ] 44-07-PLAN.md — test_password_reset_confirm.py + test_password_reset_rate_limit.py
- [ ] 44-08-PLAN.md — test_invitation_accept.py + test_invitation_accept_insert_only.py (RESET-04 + RESET-05 cross-coverage)
- [ ] 44-09-PLAN.md — test_password_reset_email_render.py + AST gate extension for PASSWORD_RESET_EMAIL real callsite (D-44-36)

**Wave 5** (blocked on Wave 4 — cleanup cron)
- [ ] 44-10-PLAN.md — cleanup_password_reset_tokens.py ARQ cron + WorkerSettings registration (D-44-31/32)
- [ ] 44-11-PLAN.md — test_cleanup_password_reset_tokens.py retention-boundary integration test

### Phase 45: Email Notification Mirrors
**Goal**: Existing Telegram-only flows (expiring-soon at 06:15, booking reminders at 06:35, cash payment-receipts) reach clients via email when Telegram is unavailable or the client prefers email — with cross-channel idempotency preserved per the Phase 41 `channel` discriminator and owner-signed-off locked Russian copy.
**Depends on**: Phase 42 (transport + `EmailDispatcher`) + Phase 41 (cross-channel idempotency migration was a hard precondition before any NOTIFY-* phase per critical invariant)
**Requirements**: NOTIFY-06, NOTIFY-07, NOTIFY-08, NOTIFY-09, NOTIFY-10, NOTIFY-11, NOTIFY-12, NOTIFY-13, NOTIFY-14
**Success Criteria** (what must be TRUE):
  1. A client with `email IS NOT NULL` and Telegram blocked (or unlinked) receives an email at 06:15 Europe/Moscow when their membership has `end_date IN (today+1, today+3, today+7)` — using the appropriate locked `EMAIL_EXPIRING_{7D,3D,1D}_VARIANT_{A,B}` template chosen via `client_id.bytes[0] & 1` (anti-oracle A/B preserved); a `membership_notifications` idempotency row exists with `channel='email'`, and a second 06:15 tick the same day produces zero duplicate sends.
  2. A booked client with email receives a `EMAIL_BOOKING_REMINDER_24H` email at 06:35 Europe/Moscow 24h before slot start when Telegram delivery fails; `booking_notifications (booking_id, kind, channel='email')` idempotency row exists; the 4 booking lifecycle locked templates (`EMAIL_BOOKING_CONFIRMED`, `EMAIL_BOOKING_CANCELLED_BY_CLIENT`, `EMAIL_BOOKING_CANCELLED_BY_OWNER`, `EMAIL_BOOKING_REMINDER_24H`) live in `app/modules/bookings/notifications.py` per the D-39-02 module-ownership precedent.
  3. After reception records a cash sale via `POST /api/v1/memberships` or `POST /api/v1/pt-packages`, the client receives `EMAIL_PAYMENT_RECEIPT_SALE` containing amount via `formatMoney` (NBSP-safe — `&nbsp;` in HTML body, literal U+00A0 in plain-text), receipt timestamp, snapshot description, and `actor_display_name` of the operator who recorded it; `payment_receipt_emailed` audit row exists with `audit_correlation_id` linking to the original `payment_recorded` row; `payment_receipts` UNIQUE `(payment_id, channel)` prevents double-receipt across docker-restart races.
  4. After owner issues a refund via `POST /api/v1/memberships/{id}/refund`, the client receives the locked `EMAIL_PAYMENT_RECEIPT_REFUND` email and `payment_receipt_emailed` audit is emitted; payment commit is NOT rolled back if the email send fails (best-effort informational receipt).
  5. The eager-import discipline (REG-29-04 mirror) is enforced — `app/workers/__init__.py` imports the new ORM models (`email_send_log`, `payment_receipts`, optional `password_reset_tokens`) and `tests/test_workers_eager_import.py` verifies via AST introspection; cron one-shot scripts return non-zero counts on first call against a freshly migrated database.
**Plans**: 12 plans

Plans:
**Wave 1**
- [x] 45-01-PLAN.md — Alembic 0031 payment_receipts + PaymentReceipt ORM + telegram_chat_id NULLABLE widening
- [x] 45-02-PLAN.md — ExpiringNotificationSentPayload (CREATE) + format_actor_display helper + unit test
- [x] 45-04-PLAN.md — memberships/email_templates.py (6 EMAIL_EXPIRING templates)
- [x] 45-05-PLAN.md — bookings/email_templates.py (4 EMAIL_BOOKING templates)
- [x] 45-06-PLAN.md — payments/email_templates.py (2 receipt templates) + dispatcher walker + .importlinter

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 45-03-PLAN.md — Eager-import PaymentReceipt in app/workers/__init__.py + test extension

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 45-07-PLAN.md — memberships notifications helper + repo + service email fallback + integration test
- [x] 45-08-PLAN.md — bookings notifications helper + repo + service (4 callsites) email fallback + integration test
- [x] 45-09-PLAN.md — Payment receipt fanout at memberships orchestrators (sale + refund) + integration test

**Wave 4** *(blocked on Wave 3 completion)*
- [ ] 45-10-PLAN.md — Payment receipt fanout at pt_packages orchestrators + integration test
- [x] 45-11-PLAN.md — Real-Postgres concurrent receipt UNIQUE race test

**Wave 5** *(blocked on Wave 4 completion)*
- [ ] 45-12-PLAN.md — Phase 45 AST gate enumeration + walker scope extension

### Phase 46: OpenAPI Handoff + Milestone Verification
**Goal**: The external design team can consume the v1.6 contract via byte-stable artifacts; the milestone is gated by live-stack proof that anti-oracle, cross-channel idempotency, multi-user audit traceability, and deliverability invariants all hold against a real provider AND a real Postgres.
**Depends on**: Phase 45 (all feature surface complete — this is the serialization point + verification gate); applies DEFER-40-01 lesson by budgeting runbook scaffolding hardening explicitly
**Requirements**: HANDOFF-03, HANDOFF-04, VER-09, VER-10, VER-11, VER-12, VER-13, VER-14
**Success Criteria** (what must be TRUE):
  1. `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts` regenerate byte-stable in one atomic pass exposing every new v1.6 path (`/users` GET/POST, `/users/{id}/deactivate`, `/users/{id}/reactivate`, `/users/{id}` DELETE, `/users/invitations/accept`, `/users/invitations/{id}/revoke`, `/auth/password-reset/request`, `/auth/password-reset/confirm`, `/_internal/email/webhook`, updated `/otp/request` with `channel` parameter); CI `git diff --exit-code` is green on both artifacts.
  2. `packages/api-client/src/schema.contract.test.ts` `AssertNonNever` forward-guards grow from 61 to ~73 covering every new v1.6 path + method + request-body realisation + 2xx-response realisation; `apps/backend/README.md` carries a v1.6 changelog section documenting all new endpoints.
  3. An operator can execute ≥7 curl-based runbook scenarios against `docker compose up` and produce verbatim HTTP transcripts proving: (a) invite → accept → login flow, (b) deactivate → `/refresh` returns 401 `account_inactive`, (c) password-reset → all old sessions invalidated → new password works, (d) anti-oracle 4-case identical-202, (e) Telegram-blocked client gets expiring email with `channel='email'` idempotency row, (f) cash sale triggers receipt email, (g) soft-delete + re-invite different person succeeds, (h) cron chain stays in window under mocked provider 5xx with circuit breaker open.
  4. ≥6 real-Postgres race tests pass: token replay race, soft-delete + re-invite race, deactivate + `/refresh` race, bounce-webhook + active-send race, concurrent expiring-cron double-pings race, RFC 2047 Cyrillic-subject round-trip; `test_password_reset_no_oracle.py` + `test_otp_email_anti_oracle.py` pass at the gate.
  5. Live email-deliverability probe is captured as evidence in `.planning/milestones/v1.6-VERIFICATION-LOG.md` — one email each to a yandex.ru + mail.ru + rambler.ru recipient with `Authentication-Results` showing SPF=pass, DKIM=pass, DMARC=pass alignment; 6/6 CI gates green (ruff + mypy --strict + pytest + import-linter + OpenAPI drift + frontend codegen drift) plus SVC001 + `LOCKED_EMAIL_TEMPLATES` AST gates green.
  6. Owner sign-off is recorded in `.planning/milestones/v1.6-VERIFICATION-LOG.md` enumerating every locked Russian email template constant name (D-27-OWNER-COPY-LOCK + D-39-02 lineage); inline regressions discovered at the gate are fixed in place under the ≤5 hard cap (>5 → roll forward as DEFER-46-N).
**Plans**: TBD

</details>

---

#### Progress

**Execution Order:** 41 → 42 → 43 → 44 → 45 → 46

(Phase 43 can run in parallel with Phase 42 once Phase 41 lands — the dependency graph forks at Phase 41 and reconverges at Phase 44. Plan-phase resolves parallel-eligible plans.)

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 41. INFRA Bedrock + Anti-Oracle Scaffold | 11/11 | Complete   | 2026-05-18 |
| 42. Email Transport Layer + Email OTP Fallback | 13/16 | In Progress|  |
| 43. Multi-User Admin Module | 18/18 | Complete   | 2026-05-19 |
| 44. Invitation + Password-Reset Flow | 11/11 | Complete | 2026-05-20 |
| 45. Email Notification Mirrors | 11/13 | In Progress|  |
| 46. OpenAPI Handoff + Milestone Verification | 0/? | Not started | — |

---

*Roadmap last updated: 2026-05-18 — v1.6 Email channel + Multi-user admin opened. 6 phases (41-46), 48/48 requirements mapped (7 INFRA + 1 RESET-06 → Phase 41; 7 EMAIL + 4 AUTH-EM → Phase 42; 7 USERS → Phase 43; 5 RESET → Phase 44; 9 NOTIFY → Phase 45; 2 HANDOFF + 6 VER → Phase 46). Phase numbering continues from v1.5 (last phase: 40 → next phase: 41). Critical-invariant ordering preserved: INFRA-39 audit-snapshot + INFRA-38 users-soft-delete partial-UNIQUE + NOTIFY-06 channel-discriminator migration land in Phase 41 BEFORE any feature callsite; `test_password_reset_no_oracle.py` (RESET-06) lands in Phase 41 BEFORE any reset endpoint per Pitfall 1; OpenAPI drift gate (HANDOFF-03..04) bundled with milestone verification (VER-09..14) in Phase 46 as the serialization point (mirrors v1.5 Phase 40 shape). v1.5 collapsed above.*
*v1.0 Coverage: 47/47 v1 requirements validated*
*v1.1 Coverage: 70/70 v1 requirements validated*
*v1.2 Coverage: 63/63 v1 requirements satisfied (2 accepted-at-planning deviations carried forward as v1.3 tech-debt — both closed in Phase 24 DEBT-01/02)*
*v1.3 Coverage: 44/44 v1.3 requirements satisfied (1 mock-mode UX deferred to v1.4 — closed in Phase 30 DEBT-05)*
*v1.4 Coverage: 61/61 v1.4 in-scope requirements satisfied (8 INFRA/DEBT + 8 TRN + 18 PAY/REF + 13 PT-package + 9 PT-session + 1 FE-10 + 4 VER). FE-11..18 (8 reqs) descoped to v2.0 Frontend Integration milestone per the 2026-05-15 pivot.*
*v1.5 Coverage: 57/57 v1.5 requirements mapped (11 INFRA/DEBT → Phase 37; 25 SLOT/BOOK/PKG → Phase 38; 10 NOTIFY/CRON → Phase 39; 11 BOT/HANDOFF/VER → Phase 40).*
*v1.6 Coverage: 48/48 v1.6 requirements mapped (8 → Phase 41; 11 → Phase 42; 7 → Phase 43; 5 → Phase 44; 9 → Phase 45; 8 → Phase 46).*
