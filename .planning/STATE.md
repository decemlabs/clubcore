---
gsd_state_version: 1.0
milestone: v1.6
milestone_name: Email channel + Multi-user admin
status: executing
stopped_at: Phase 45 context gathered
last_updated: "2026-05-20T10:52:42.347Z"
last_activity: 2026-05-20
progress:
  total_phases: 6
  completed_phases: 4
  total_plans: 69
  completed_plans: 66
  percent: 96
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-18)

**Core value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.
**Current focus:** Phase 44 — Invitation + Password-Reset Flow

## Current Position

Phase: 44 — COMPLETE
Plan: 9 of 11
Status: Ready to execute
Last activity: 2026-05-20

## v1.6 Milestone Plan

**Status:** Ready to execute

**Phase structure:**

| Phase | Goal | Requirements (count) |
|-------|------|----------------------|
| 41. INFRA Bedrock + Anti-Oracle Scaffold | Pre-register audit events, RBAC, schema migrations, Protocol slots, anti-oracle test BEFORE feature code | INFRA-34..40 + RESET-06 (8) |
| 42. Email Transport Layer + Email OTP Fallback | Provider adapter + ARQ dispatch + DNS + circuit breaker + bounce webhook + email OTP fallback | EMAIL-01..07 + AUTH-EM-01..04 (11) |
| 43. Multi-User Admin Module | New `app/modules/users/` — owner CRUD + deactivate + soft-delete + multi-user audit | USERS-01..07 (7) |
| 44. Invitation + Password-Reset Flow | Anti-oracle `password-reset/request`, atomic-consume confirm, invite-accept INSERT-only, revoke | RESET-01..05 (5) |
| 45. Email Notification Mirrors | Email fallback for expiring + booking reminders + payment-receipt; locked Russian templates | NOTIFY-06..14 (9) |
| 46. OpenAPI Handoff + Milestone Verification | Byte-stable spec regen + live-stack runbook + race tests + deliverability probe + owner sign-off | HANDOFF-03..04 + VER-09..14 (8) |

**Coverage:** 48/48 v1.6 requirements mapped, no orphans, no duplicates.

**Phase numbering:** continues from v1.5 — Phase 41 is the first phase of v1.6 (v1.5 ended at Phase 40).

**Execution order:** 41 → 42 → 43 → 44 → 45 → 46. The dependency graph forks after Phase 41 (Phases 42 and 43 are independent) and reconverges at Phase 44; plan-phase will resolve parallel-eligible plans within each phase.

**Critical-invariant ordering preserved:**

- INFRA bedrock (Phase 41) lands FIRST — cannot start any feature work without it
- `test_password_reset_no_oracle.py` (RESET-06) lands in Phase 41 BEFORE any reset endpoint per Pitfall 1
- Cross-channel `channel`-column migration (INFRA-* / NOTIFY-06) lands in Phase 41 BEFORE any NOTIFY-* phase
- OpenAPI drift gate (HANDOFF-03..04) bundled with verification (VER-09..14) in Phase 46 as the serialization point AFTER all feature phases

**Open conflicts (resolve at discuss-phase per scope):**

1. Email provider (Yandex Cloud Postbox primary vs Unisender Go fallback) — Phase 42 discuss
2. Reset-token storage (itsdangerous stateless vs DB `password_reset_tokens` table) — Phase 44 discuss
3. `notifications` module status (placeholder vs resurrect) — Phase 45 discuss (synthesizer leans placeholder)
4. Template engine (Jinja2 SandboxedEnvironment vs `Final[str]` f-string) — Phase 42 / 45 discuss
5. `User` ORM ownership (hoist to `core/models.py` vs `UserLookup` Protocol slot) — Phase 41 discuss
6. Phase numbering — RESOLVED here: 6 phases (41-46)
7. Email-verify policy for owner-added accounts (trust vs click-to-verify) — Phase 43 discuss

## Accumulated Context

### Decisions

Full decisions log lives in PROJECT.md Key Decisions table. v1.5 added 18 new decisions (D-37-01..D-40-18) — all archived in `.planning/milestones/v1.5-ROADMAP.md` and per-phase `*-CONTEXT.md` files. v1.6 decisions will land at each phase's discuss-phase as `D-41-NN..D-46-NN`.

**Phase 41 Plan 01 (2026-05-18):** LOCKED_AUDIT_EVENTS extended 58 → 69 (+11 v1.6 pairs per D-41-19). Plan must_haves drift ("56 → 67") resolved in favour of D-41-19 source-of-truth — the codebase already had 58 pairs (Phase 20 D-20-10 + Phase 23 D-23-10 drift adds not in the planner's mental count); the 11-pair v1.6 delta is what INFRA-34 requires; final cardinality is 69. Synthetic-violation runtime test established as first such test in the codebase (prior tests were all AST-walker-based). See `41-01-SUMMARY.md`.

- [Phase ?]: Plan 41-03: LOCKED_EMAIL_TEMPLATES frozenset (15 v1.6 template identifiers) + AST walker enforcing literal-only template_id at every get_email_dispatcher() callsite (D-41-11/12/13)
- [Phase ?]: Plan 41-04: Action.UPDATE added to backend Action StrEnum (D-41-22 verb). OWNER_ONLY 29 -> 33 with 4 USERS pairs. Three-way RBAC parity green at 33.
- [Phase 41]: Plan 41-05: Alembic 0022 ships users.deleted_at TIMESTAMPTZ + partial UNIQUE INDEX uq_users_email_active ON users (lower(email)) WHERE deleted_at IS NULL (drops uq_users_email from 0001_auth.py). Revision id shortened to `0022_users_soft_delete_unique` (29 chars) to fit alembic_version VARCHAR(32). Round-trip clean. uq_users_email_active added to env.py _include_object skiplist (D-25-05 lineage). INFRA-38 partially progressed (schema half of 0022 done; 0024 + 0025 land in plans 41-08 + 41-09).
- [Phase 41]: D-41-01/02 User ORM hoisted to app.core.models with one-milestone shim at app.modules.auth.models (v1.7 DEFER-41-shim removes)
- [Phase 41]: D-41-24/25 EmailDispatcher + UserSessionInvalidator Protocol slots declared with defensive-raise accessors
- [Phase 41]: D-41-27/28 .importlinter modules-independent gains app.modules.users; SVC001 walker scope gains modules/users/service.py + modules/auth/password_reset_service.py (anti-silent-drop pin)
- [Phase ?]: Plan 41-11 (2026-05-18): RESET-06 anti-oracle xfail-strict test landed at apps/backend/tests/integration/auth/test_password_reset_no_oracle.py. 4-case identical-202 + identical-body + 100ms bounded-timing contract documented as code; xfail(strict=True) per D-41-17 ensures Phase 44 RESET-01 cannot ship the endpoint without satisfying the contract or breaking CI.
- [Phase ?]: Plan 41-02: 11 v1.6 Pydantic payload schemas registered in AUDIT_PAYLOAD_SCHEMAS with extra='forbid' + audit_correlation_id: UUID | None per D-41-20; PasswordResetRequestedPayload.target_user_id is Optional to support the anti-oracle unknown-email branch (D-41-10)
- [Phase ?]: Migration 0023 alters fk_audit_log_actor_user_id_users from ON DELETE RESTRICT to SET NULL via drop+recreate (no Postgres ALTER CONSTRAINT for ondelete); pairs with new actor_email_snapshot TEXT NULL column for forensic continuity past user hard-deletes (D-41-08/09/10 schema half).
- [Phase ?]: Phase 41 Plan 07: Wired ContextVar runtime half of INFRA-39 — actor_context_var + ActorContextMiddleware (baseline-None envelope) + get_current_user.set_actor() write site + audit.emit() reads contextvar with T-41-07-02 defensive identity check + ARQ on_job_start/on_job_end job envelope. ARQ 0.28 ctx limitation (no job kwargs surfaced) → jobs needing attribution call set_actor() in body. CurrentUser Protocol gained email: str.
- [Phase ?]: [Phase 41 Plan 08]: Alembic 0024 channel discriminator on membership_notifications + booking_notifications — channel TEXT NOT NULL DEFAULT 'telegram' CHECK channel IN ('telegram','email'); UNIQUE recreated to include channel. Zero-row backfill (D-41-15 precedent). CK names wrapped in op.f() so project naming_convention does not double-prefix (caught + fixed pre-commit). Round-trip clean. INFRA-38 still progressing — 0025 lands in Plan 09.
- [Phase ?]: Plan 41-09: INFRA-38 closed — Alembic 0025 ships password_reset_tokens (purpose discriminator + partial UNIQUE (user_id,purpose) WHERE consumed_at IS NULL + non-unique token_hash idx for atomic-consume); PasswordResetToken ORM + alembic/env.py registration; REG-29-04 eager-import discipline pinned in tests/unit/test_workers_eager_import.py (new file — no prior eager-import test existed). All 4 v1.6 INFRA-bedrock migrations in. Pre-existing 41-05/41-08 ORM drift catalogued in deferred-items.md (owned by Phases 43/45).
- [Phase ?]: Phase 43 Plan 01: Alembic 0030 adds 4 user-lifecycle columns (is_active, status, deactivated_at, deactivated_by_user_id) + 2 CHECKs + self-FK ON DELETE SET NULL; password_hash NOT NULL dropped (D-43-06); User ORM at app.core.models extended with same shape + deleted_at mirror; round-trip clean against live Postgres. D-43-36 BLOCKING checkpoint auto-approved (objective verification PASS).
- [Phase ?]: Plan 43-02 D-43-OWNER-COPY-LOCK landed USER_INVITATION_EMAIL
- [Phase ?]: Phase 43 Plan 03: UserSessionInvalidator single-wire (D-43-27) — closure-injected Redis factory; LOCKED_AUDIT_EVENTS cardinality 70 -> 71 (pre-existing Phase 42 plan 09 drift documented); test_audit_taxonomy assertion updated
- [Phase ?]: Plan 43-04: users/repository.py — 12 async functions, zero commit/flush (D-43-09); list_alive LEFT JOIN subquery MAX(expires_at) populates invitation_expires_at; count_active_owners_excluding uses .with_for_update() last-owner serial-arbiter; atomic-consume via UPDATE...RETURNING for both re-invite + revoke paths
- [Phase ?]: Plan 43-05: users/service.py — 6 public async functions composing repository + audit + email-dispatch + session-invalidation. 4-branch idempotent create_user (D-43-13: active=409, pending=re-invite, no-row=INSERT, soft-deleted=fallthrough). Two-guard layer on deactivate/soft-delete (self + last-owner via FOR UPDATE count). Atomic-consume race-loss → 409 on revoke. SVC001 invariant green (5/5 mutating functions carry `await session.commit()`). FLAT audit kwargs (Phase 42 CR-01) — 0 nested payload= occurrences. Literal `template_id="USER_INVITATION_EMAIL"` at dispatcher callsite. 10 domain exceptions added to app/core/exceptions.py. Settings.frontend_base_url added (D-43-14 invitation URL base). Hand-rolled Russian-date helper (no babel dep).
- [Phase ?]: Plan 43-13: AST positive-assertion for USER_INVITATION_EMAIL literal at users/service.py callsite — mirrors Phase 42 4-11 pattern; walker logic mirrored locally so future _iter_dispatcher_calls refactor cannot weaken the gate (D-43-33)
- [Phase ?]: Users router uses global AppError handler (no per-endpoint try/except) — mirrors clients/router.py
- [Phase ?]: Plan 43-07: rotate_refresh single-SELECT predicate (is_active=true AND deleted_at IS NULL); refresh_failed/account_inactive forensic audit emit; row-is-None harmonised to InvalidSession for anti-oracle parity
- [Phase 43]: Plan 43-07b: shared tests/integration/users/conftest.py (17 fixtures + RecordingEmailDispatcher) lands BEFORE Wave 4 to eliminate parallel conftest race; deactivated state encoded as is_active=False+deactivated_at (status enum only admits 'active'|'pending_invitation' per migration 0030 CHECK)
- [Phase 43]: 43-09: Test assertion shape uses r.json()['code'] flat — AppError handler returns {code, message, fields} at top level, not nested under 'detail'
- [Phase ?]: 43-11: Drift-tolerant invitation-flow tests using AuditLog.action (not .event), r.json()['code'] (not detail.error), JSONB UUID-string roundtrip
- [Phase 43]: Phase 43 Plan 08: Audit payload UUIDs/datetimes stringified at users/service.py audit.emit callsites (REG-36-03 carried forward); integrations/email/dispatcher per-module walker gains users.email_templates branch with matching .importlinter ignore_imports
- [Phase 43]: Plan 43-10: e2e USERS-04+USERS-06 + USERS-05+USERS-06 integration test lands. Documents that in the real prod sequence the post-deactivate refresh hits Branch C (family_reuse_detected → invalid_token), not Branch A (account_inactive → invalid_session), because families are revoked in the same UoW as is_active=false. Branch A coverage is 43-12's responsibility via refresh_client_deactivated synthetic fixture. Test accepts code in {invalid_session, invalid_token} — both are anti-oracle-safe.
- [Phase 43 regression gate fix-pack (2026-05-19)]: 4 atomic commits resolved 3/4 Phase 43 regressions discovered by the post-phase regression gate:
  (1) `UserInvitedPayload.link_copied` defaulted to `False` (restores `test_user_invited_payload_round_trip` + `test_v16_payloads_accept_uuid_as_str`);
  (2) `User.status` ORM type changed `SAEnum(...)` → `Text` so on-disk TEXT no longer produces `modify_type` autogenerate diff (mirrors `User.role` TEXT+CHECK pattern, D-07);
  (3) `User.email` ORM `unique=True` removed (Migration 0022 dropped the global `uq_users_email` in favour of partial-UNIQUE `uq_users_email_active` on `lower(email) WHERE deleted_at IS NULL`);
  (4) `app.modules.users.repository -> app.modules.auth.password_reset_token_model` added to `.importlinter` `modules-independent` `ignore_imports` (Phase 41 0025 password_reset_tokens is shared bedrock between auth RESET-02 and users USERS-02; v1.7 tighten path is `DEFER-43-shim` — hoist model to `app.core.models` alongside `User`).
  Phase 43 users/ integration suite still 19/19 green. `test_alembic_check_clean` still fails on PRE-EXISTING `booking_notifications.channel` + `membership_notifications.channel` ORM-vs-DB drift (unrelated to Phase 43 — out of scope per regression-fix spec). Phase 43-specific `users.*` drift is fully resolved.

- [Phase 43]: Plan 43-14 gap-closure: CR-01 (email empty) fixed by dropping local render and passing raw template vars to dispatcher. WR-02 overwrite policy chosen for Branch B re-invite (full_name/role updated from request). WR-06 expired-token guard added to revoke_invitation (InvitationExpiredError 409) + repository defence-in-depth filter. WR-07 _format_expires_ru now converts to Europe/Moscow + appends (MSK) Cyrillic suffix. IN-01 audit_correlation_id=None at 4 terminal events (deactivate/reactivate/soft_delete/revoke). IN-03+IN-04 recorded as CONTEXT.md deferred ideas. Regression suite 80 passed.

- [Phase 43]: Plan 43-16 gap-closure: CR-04 fixed by introducing `_revoke_all_sessions_no_commit` (no commit helper) + `revoke_all_sessions` (thin commit wrapper for logout-all/pwd-change) + `invalidate_all_families_for_user` calling no-commit variant. WR-01 fixed by extending `UserSessionInvalidator` Protocol with `actor_user_id: UUID | None`; all 4 callsites updated atomically (users/service x2, auth/service Protocol impl, main.py registration). WR-04 fixed by using `UPDATE...RETURNING family_id` distinct set for DB-authoritative count (Redis SMEMBERS drift eliminated). WR-03 fixed by `repository.soft_delete_user` accepting `actor_user_id` + `func.coalesce(User.deactivated_by_user_id, actor_user_id)`. Regression suite 88 passed.

- [Phase 43]: Plan 43-17 gap-closure: CR-03 (login chokepoint) closed — `authenticate()` SELECT now filters `User.is_active.is_(True)` AND `User.deleted_at.is_(None)`, mirroring the D-43-20 `rotate_refresh` predicate set. Deactivated/soft-deleted users fall into the existing sentinel-hash + `login_failed` emit path (no new emit branch needed; anti-oracle body+timing parity preserved). CR-03 secondary closed — `request_otp_email` eligibility replaced defensive `getattr(user, "is_active", True)` with a SQL predicate. All three auth chokepoints (rotate_refresh + authenticate + request_otp_email) now share the same predicate set. Regression suite 86 passed, 1 xfailed.
- [Phase ?]: 45-06: Payments email templates registered (SALE + REFUND); pure-literal subjects per D-45-19
- [Phase ?]: Plan 45-02 anchors landed
- [Phase 45]: Phase 45-05: 4 EMAIL_BOOKING locked Russian templates land in app/modules/bookings/email_templates.py — voice mirrors Telegram BOOKING_*_DM, NBSP discipline per D-45-17, owner sign-off recorded in 45-05-SUMMARY.md
- [Phase ?]: Override D-45-24 'zero .importlinter changes' per PATTERNS.md correction #3 — grimp parses function-scope imports
- [Phase ?]: Phase 45 plan 07: ExpiringNotificationSentPayload extra=forbid prevents audit_correlation_id from flowing through audit.emit — logged via structlog instead
- [Phase ?]: Phase 45-08: Migration 0032 widens booking_notifications.kind from VARCHAR(16) + single-element CHECK to VARCHAR(32) + 4-kind CHECK
- [Phase ?]: Phase 45-08: 5-callsite booking email-fallback wiring (D-45-05) — create_booking/cancel_booking owner+reception/schedule.cancel_slot cascade/_send_booking_reminders cron. New _dispatch_booking_lifecycle_notification helper. 4 literal kind branches at the enqueue_booking_email_fallback helper (D-45-22 + AST gate parity).

### Pending Todos

- `/gsd-discuss-phase 41` — resolve open conflict #5 (`User` ORM ownership), draft Phase 41 plan structure for INFRA bedrock + anti-oracle scaffold
- After Phase 41 lands: `/gsd-discuss-phase 42` (resolves conflict #1 provider + #4 template engine) and `/gsd-discuss-phase 43` (resolves #7 email-verify) — can be drafted in parallel

### Blockers/Concerns

None blocking. Deferred items from prior milestones remain tracked below; none gate v1.6 start. The DEFER-40-01 lesson (v1.5 verification runbook scaffolding needed 4 hotfixes) is explicitly budgeted in Phase 46's verification scope.

## Deferred Items

Items carried forward from v1.5 milestone close on 2026-05-18:

| Category | Item | Status | Source | Resolution |
|----------|------|--------|--------|-----------|
| verification_gap | **DEFER-40-01** — Full v1.5 operator runbook (6 curl + 2 Telegram sandbox + 2 cron + 5 CI gate URLs); `run.sh` needs 2+ remaining hotfixes (wrong RBAC actor on POST /trainer-slots; missing X-CSRF-Token header on mutating endpoints). Phase 40 minimal verification PASSED via `scripts/verify_40_create_booking_via_bot.py`; full ritual deferred. | acknowledged | Phase 40 | v1.9 (API Handoff + Production Hardening) — rerun against the stack after `run.sh` hardening |
| verification_gap | Phase 38 verification gaps (38-VERIFICATION.md status: gaps_found) | acknowledged at v1.5 close | Phase 38 | v1.9 audit sweep, or address during v1.6 if cheap |
| pytest_failures | DEFER-36-04-A — 11 remaining failures from v1.4 (7 pt_sessions MissingGreenlet + 3 pt_packages validation_error envelope drift + 1 test_revert_predicate logic bug) | unchanged from v1.4 | Phase 36.1 | v1.9 doc-debt + test-debt sweep |
| lint_format | DEFER-36-04-B — `ruff format --check` red on 123 files | unchanged from v1.4 | Phase 36-04 | v1.9 doc-debt sweep |
| verification_gap | Phase 31 admin-web browser checks (2 scenarios) | unchanged from v1.3 | Phase 31 | v2.0 Frontend Integration milestone scope |
| quick_task | `260501-ndi` orphan in `.planning/quick/` | unchanged from v1.0 | v1.0 | Defer to `/gsd-cleanup` |
| uat_gap | Phase 06 + Phase 08 HUMAN-UAT.md pending scenarios | unchanged from v1.1 | v1.1 | v2.0 Frontend Integration milestone scope |

## Session Continuity

Last session: 2026-05-20T10:52:13.789Z
Stopped at: Phase 45 context gathered
Resume: None — Phase 43 gap-closure plans complete
