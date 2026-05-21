# Requirements — Milestone v1.6 Email Channel + Multi-User Admin

**Project:** Sportzal
**Milestone:** v1.6 — Email channel + Multi-user admin
**Goal:** Закрыть последний infra-pillar перед online-платежами (v1.7) — добавить email как параллельный канал уведомлений и закрыть operator-onboarding gap через owner-managed multi-user admin. Все 7 OPEN CONFLICTS из `research/SUMMARY.md` (provider, reset-token store, notifications module, template engine, User ORM, phase numbering, email-verify policy) разрешаются на discuss-phase для конкретной фазы, не на этом этапе.

**Phase numbering:** continues from v1.5 — first phase is **Phase 41** (v1.5 ended at Phase 40).

**Research:** `.planning/research/{STACK,FEATURES,ARCHITECTURE,PITFALLS,SUMMARY}.md` — synthesizer surfaced 7 open conflicts marked for spec phase. All invariants below preserve anti-oracle DM equality, AST `audit.emit` gate, partial-UNIQUE idempotency, locked-copy owner sign-off, refresh-family race tolerance.

---

## v1.6 Requirements (locked scope)

### Foundations bedrock — INFRA-34..40 (Phase 41)

Up-front pre-registration of all v1.6 audit events, RBAC additions, contract/import-linter changes, and SVC001 scope extensions BEFORE any feature callsite lands (v1.3 INFRA-15 lesson).

- [x] **INFRA-34**: Extend `LOCKED_AUDIT_EVENTS` frozenset from 56 → 67 with 11 new event names: `email_sent`, `email_send_failed`, `user_invited`, `user_invitation_accepted`, `user_invitation_revoked`, `user_deactivated`, `user_reactivated`, `user_soft_deleted`, `password_reset_requested`, `password_reset_completed`, `payment_receipt_emailed`. Pre-registered in Phase 41 before any downstream callsite (mirrors v1.5 INFRA-24 + v1.3 INFRA-15 discipline). Final-set boundary check against research/SUMMARY.md table; deviation requires Decision row.
- [x] **INFRA-35**: Lock canonical Pydantic v2 payload schemas for the 11 new audit events in `app/core/audit_payloads.py`. All schemas use `extra='forbid'`. UUIDs serialised as `str(uuid)` (REG-36-03 lesson). Each registry entry includes `audit_correlation_id: UUID | None` for the asynchronous email-event-correlation pattern (links `email_sent` row back to the triggering business audit row).
- [x] **INFRA-36**: Introduce `LOCKED_EMAIL_TEMPLATES` frozenset + AST gate in `app/core/audit.py` (or sibling) mirroring `LOCKED_AUDIT_EVENTS` shape. Frozen set of locked-template constant identifiers (e.g. `USER_INVITATION_EMAIL_SUBJECT`, `PASSWORD_RESET_EMAIL_HTML`). The email-dispatcher entry-point (`get_email_dispatcher()(...)`) accepts a template-id enum, NOT raw subject/html/text strings — AST walker rejects ad-hoc string literals at dispatcher callsites. Synthetic-violation fixture committed first.
- [x] **INFRA-37**: Extend `Resource` enum with `USERS`; extend `OWNER_ONLY` frozenset from 26 → 30 with `(CREATE, USERS)`, `(UPDATE, USERS)`, `(DELETE, USERS)`, `(LIST, USERS)`. Three-way byte-parity test (backend `RBAC` ↔ admin-web `can.ts` ↔ `registry.ts`) updated. Reception keeps zero USERS permissions in v1.6.
- [x] **INFRA-38**: Soft-delete + partial-UNIQUE migration on `users` table — adds `users.deleted_at TIMESTAMPTZ NULL`, drops the existing global UNIQUE `(lower(email))`, recreates as partial UNIQUE `(lower(email)) WHERE deleted_at IS NULL` (mirrors `clients.phone` v1.1 Phase 8 pattern). Closes PITFALLS account-hijack-via-email-reclaim — invite-accept MUST INSERT new row, never UPDATE existing.
- [x] **INFRA-39**: Audit denormalised actor snapshot migration — adds `audit_log.actor_email_snapshot TEXT NULL` and explicitly chooses `actor_user_id ON DELETE SET NULL` (was previously implicit). Population: on every `audit.emit` with non-NULL `actor_user_id`, the snapshot is captured at write time. Closes PITFALLS multi-user audit traceability — soft-deleting a fired operator preserves historical readability via the snapshot column.
- [x] **INFRA-40**: Architectural contract + Protocol-slot scaffolding — adds `app.modules.users` to `.importlinter` `modules-independent` contract (mechanical list addition); declares `EmailDispatcher` + `UserSessionInvalidator` Protocol types in `app/core/dependencies.py` with matching `register_*` / `get_*` accessors; extends SVC001 AST commit-gate walker scope to include `app/modules/users/service.py` AND `app/modules/auth/password_reset_service.py` (v1.1 Phase 12.1 lesson — NOT just `service.py`).

### Email transport layer — EMAIL-01..07 (Phase 42)

Channel-agnostic outbound transport in `app/integrations/email/` (mirrors `integrations/telegram/`). Provider choice deferred to discuss-phase (open conflict #1: Yandex Cloud Postbox primary vs Unisender Go fallback vs other).

- [ ] **EMAIL-01**: Replace `app/integrations/email/client.py` placeholder with a real async provider adapter. Single thin entry-point `async def send_email(*, to, subject, html, text, tags) -> EmailSendResult`. Returns typed `EmailSendResult` dataclass with `ok | blocked | transient_error | permanent_error` classification (mirrors `app/integrations/telegram/sender.py:SendResult` shape). Forbidden from importing `app.modules.*` per existing contract 3. Provider SDK and SDK retry config locked at discuss-phase.
- [ ] **EMAIL-02**: `app/integrations/email/factory.py:build_email_client(*, settings)` factory (mirror `telegram/bot.py:build_bot`). DI-injectable, testable. Pydantic `EmailProviderSettings` block in `app/core/config.py` with fields: `provider`, `api_key`, `from_address`, `from_domain`, `sandbox_mode: bool`. Boot-time validator fails fast if `from_domain` empty in non-sandbox mode; boot-time probe to provider `/domains` endpoint asserts domain is verified.
- [x] **EMAIL-03**: New ARQ task `app/workers/tasks/dispatch_email.py` (`dispatch_email` function in `WorkerSettings.functions`). Consumes pre-rendered `EmailEnvelope` (subject/html/text/to/audit_correlation_id/template_id). Forbidden from importing `app.modules.*` — modules render templates, workers transport bytes (D-41-03 narrative exception documented). On `EmailSendResult.ok` → `audit.emit("email_sent", ...)` with `audit_correlation_id`; on `EmailSendResult.blocked|*_error` → `audit.emit("email_send_failed", ...)` with classification. ARQ `max_tries=2, timeout=20` (PITFALLS provider-5xx-storm mitigation).
- [ ] **EMAIL-04**: Compose-root + worker-startup wiring — `register_email_dispatcher(enqueue_email_dispatch)` called in BOTH `app/main.py:create_app()` AND `app/workers/__init__.py:WorkerSettings.on_startup` (REG-29-03 lesson, non-negotiable double-wiring). On-startup builds the email client via `build_email_client` and stashes in `ctx['email_client']` (mirrors `ctx['engine']` / `ctx['sessionmaker']` pattern from v1.2 Phase 18). Parity test asserts both call sites register identical slot.
- [ ] **EMAIL-05**: DNS owner-runbook artifact — `infra/dns/sportzal.ru.zone` documents required SPF/DKIM/DMARC records for a dedicated email subdomain (`mail.sportzal.ru` or equivalent — final subdomain layout resolved at discuss-phase). DMARC policy ladder: `p=none` initial (monitoring) → `p=quarantine` after one week of clean reports → `p=reject` deferred to v1.7. DMARC `rua` reports go to owner address. Runbook is operator-action, not code — but committed alongside the code so the gate cannot land without DNS spec.
- [x] **EMAIL-06**: Outbound rate-limit + circuit breaker — `asyncio.Semaphore` cap on concurrent provider calls inside the ARQ task; per-provider Redis circuit breaker (`sz:email:circuit:{provider}`, TTL 5m, opened on consecutive 5xx). Open circuit short-circuits to `EmailSendResult.transient_error` without touching the provider (preserves cron-window budget — PITFALLS provider-5xx-storm mitigation).
- [x] **EMAIL-07**: Bounce/complaint webhook endpoint — `POST /api/v1/_internal/email/webhook` (path locked at discuss-phase). HMAC signature verification BEFORE body parse using `hmac.compare_digest` (timing-safe). Recorded into `email_send_log` table (schema locked at discuss-phase). Aggressive bounce-driven `email_verified=false` flag flipping deferred to v1.7 — v1.6 records send-attempt outcomes only.

### Multi-user admin module — USERS-01..07 (Phase 43)

New `app/modules/users/` module. Owner-only operator onboarding + lifecycle.

- [x] **USERS-01**: New `app/modules/users/` directory with `router.py` / `service.py` / `repository.py` / `schemas.py` / `permissions.py` / `constants.py` / `email_templates.py`. Schemas use `BackendSchemaBase` (camelCase wire format). Repository uses `list_alive` / `get_alive` partition pattern (mirrors `clients/repository.py`).
- [x] **USERS-02**: `GET /api/v1/users` (owner-only) — paginated list with filters `?active=true|false&deleted=false` (default: active+not-deleted). Response envelope `{items, total, page, pageSize}`. Each item: `{id, email, fullName, role, isActive, isDeactivated, createdAt, deactivatedAt, deactivatedByUserId}`.
- [x] **USERS-03**: `POST /api/v1/users` (owner-only, CSRF) — creates user with `status='pending_invitation'`, issues invitation token (token mechanism — DB row vs itsdangerous-stateless — locked at discuss-phase per open conflict #2), enqueues invitation email via `EmailDispatcher` slot. Response 201 with `{id, email, role, invitationExpiresAt}`. **NEVER returns an admin-set plaintext password** (FEATURES anti-feature). Optional `?include_invite_link=true` returns the URL for copy-paste fallback when email bounces (FEATURES P2).
- [x] **USERS-04**: `PATCH /api/v1/users/{id}/deactivate` (owner-only, CSRF) — atomically flips `users.is_active=false`, sets `deactivated_at` + `deactivated_by_user_id`, AND revokes all refresh-token families for this user via `UserSessionInvalidator` Protocol slot in the same UoW. Emits `user_deactivated` audit event. Reverse endpoint `PATCH /api/v1/users/{id}/reactivate` flips back (emits `user_reactivated`). Cannot deactivate self (409 `cannot_deactivate_self`); cannot deactivate the last active owner (409 `cannot_deactivate_last_owner`).
- [x] **USERS-05**: `DELETE /api/v1/users/{id}` (owner-only, CSRF) — soft-delete sets `users.deleted_at = now()`. The user's email is now eligible for re-invite of a DIFFERENT person via partial-UNIQUE `(lower(email)) WHERE deleted_at IS NULL`. Cannot delete self; cannot delete the last owner. Emits `user_soft_deleted` audit event.
- [x] **USERS-06**: `/auth/refresh` hot path extended to join `users.is_active = true` AND `users.deleted_at IS NULL` — a deactivated/deleted operator immediately loses session on next refresh attempt (PITFALLS `/refresh` traceability fix). Returns 401 `account_inactive` with no oracle leakage (same response shape as `invalid_session`).
- [x] **USERS-07**: Multi-user audit traceability — every `audit.emit(...)` invoked from the users module captures `actor_email_snapshot` at write time (per INFRA-39 schema). `audit_payloads.py` user-module payloads include `actor_display_name` (computed once at audit-write time; defaults to first-name + last-initial for privacy — final formatting resolved at discuss-phase). 3-way RBAC parity test extended.

### Email OTP fallback — AUTH-EM-01..04 (Phase 42)

Email as second-channel OTP delivery for `/auth/otp/request` when user lacks Telegram or Telegram is blocked. Bundled with the email-transport phase (Phase 42) because both are email-channel mechanics with a shared `LOCKED_EMAIL_TEMPLATES` AST surface — first locked email template (`EMAIL_OTP_LOGIN`) exercises the dispatcher slot end-to-end and gates the rest of the email feature work.

- [x] **AUTH-EM-01**: Extend `otp_codes` table with `channel TEXT NOT NULL DEFAULT 'telegram' CHECK channel IN ('telegram','email')`. Drop existing UNIQUE on `(user_id) WHERE consumed_at IS NULL`; recreate as partial UNIQUE `(user_id, channel) WHERE consumed_at IS NULL` (so user can have one active Telegram OTP AND one active email OTP simultaneously, e.g. when retrying via the other channel). Migration is zero-row (existing rows inherit `channel='telegram'`).
- [x] **AUTH-EM-02**: Extend `POST /api/v1/auth/otp/request` body schema with `channel: 'telegram' | 'email'` (default: `'telegram'` for backwards compat). When `channel='email'`: requires user with verified email, returns same anti-oracle shape, enqueues email via `EmailDispatcher` slot, TTL **10 minutes** (Telegram × 2 to absorb provider lag per FEATURES SLO), 60-second resend cooldown, max 5 attempts per code. Second OTP request invalidates first (RFC 6238 single-active discipline).
- [ ] **AUTH-EM-03**: Locked Russian email template `EMAIL_OTP_LOGIN` (subject + html + text triplet) in `app/modules/auth/email_templates.py`. Owner sign-off enumerated by constant name (D-27-OWNER-COPY-LOCK pattern; template-id in `LOCKED_EMAIL_TEMPLATES`). Body contains 6-digit code; subject `"Код входа в Sportzal"` (locked); no other PII.
- [ ] **AUTH-EM-04**: Integration test `test_otp_email_anti_oracle.py` asserts: (a) user with NO Telegram + verified email gets `channel='email'` OTP; (b) user with Telegram + email, default `channel='telegram'` works unchanged; (c) `channel='email'` request for user without verified email returns the **same** 202 response shape as a successful request (no oracle); (d) constant-time floor enforced.

### Invitation + Password-reset flow — RESET-01..06 (Phase 44; RESET-06 lands in Phase 41)

Token mechanism (DB table vs itsdangerous-stateless signed token — open conflict #2) and exact endpoint paths resolved at discuss-phase. All requirements below hold regardless of which mechanism wins.

- [ ] **RESET-01**: Anti-oracle invariant on `POST /api/v1/auth/password-reset/request` — accepts `{email}` body; **always** returns 202 Accepted with identical response body for all 4 cases: `(existing-active, existing-deactivated, owner-account, non-existent)`. Constant-time response floor (≥500ms) defeats timing-side-channel. `audit.emit("password_reset_requested", actor_user_id=None, email_hash=...)` emitted in BOTH branches (known + unknown email). Rate-limit: 5/15min per IP + 1/min and 5/hour per email. Mirrors v1.2 D-20-9 `/checkin` anti-oracle + v1.3 expiring-soon variant lock.
- [ ] **RESET-02**: `POST /api/v1/auth/password-reset/confirm` — accepts `{token, newPassword}` body. Atomic-consume via `RETURNING` SQL (DB path) or `password_changed_at` equality check (itsdangerous path) — single-use enforced at SQL/signing layer, NOT at app layer. On success: updates `users.password_hash` + bumps `users.password_changed_at`, revokes ALL refresh-token families for this user via `UserSessionInvalidator` slot (forced re-login on every device), emits `password_reset_completed` audit event in same UoW, returns 200. On replay/expired/invalid: 410 Gone with generic message (no oracle).
- [ ] **RESET-03**: Token in URL fragment (`#token=...`) OR POST body — NEVER URL path (PITFALLS token-leak-via-Referer mitigation). Token TTL: invitation 7 days; password-reset 1 hour (OWASP 2025 floor). Locked Russian email templates `USER_INVITATION_EMAIL_*` (in `app/modules/users/email_templates.py`) + `PASSWORD_RESET_EMAIL_*` (in `app/modules/auth/email_templates.py`) — each owner-signed-off by constant name.
- [ ] **RESET-04**: `POST /api/v1/users/invitations/accept` — accepts `{token, password, fullName}` body. Resolves token to pending user. If user already exists with non-NULL `deleted_at` matching the email — MUST INSERT new user row, NEVER UPDATE the existing soft-deleted row (PITFALLS account-hijack-via-email-reclaim — invite-accept INSERT-only invariant). Atomically: marks invitation consumed, INSERT new user row (or update pending → active depending on token mechanism), sets initial password (hashed via Argon2id from `app/core/security.py`), emits `user_invitation_accepted` audit event. Returns 200 with login cookie pair.
- [ ] **RESET-05**: `POST /api/v1/users/invitations/{id}/revoke` (owner-only, CSRF) — explicitly revokes an outstanding invitation (sets `revoked_at` or invalidates signed token via `password_changed_at` bump). Emits `user_invitation_revoked` audit event. Already-consumed tokens cannot be revoked (409 `invitation_already_accepted`).
- [x] **RESET-06**: Integration test `test_password_reset_no_oracle.py` lands in Phase 41 (BEFORE first reset-flow endpoint per PITFALLS preventative discipline). Test asserts 4 cases (existing-active / existing-deactivated / owner-account / non-existent) produce identical 202 + identical response body + bounded-equal timing (within 100ms tolerance). Audit log asserts `password_reset_requested` emitted in all 4 cases. Updated each time RESET-* lands.

### Email mirror of expiring + booking + payment-receipt — NOTIFY-06..14 (Phase 45)

Email-channel fan-out for existing v1.3/v1.4/v1.5 Telegram flows. Uses `EmailDispatcher` slot from EMAIL-* group. All 9 requirements clustered into a single phase per coarse granularity — they share the channel-discriminator migration (NOTIFY-06), the locked Russian copy AST gate, the eager-import discipline, and the common `EmailDispatcher` slot consumer pattern.

- [x] **NOTIFY-06**: Cross-channel idempotency taxonomy migration — Alembic `0024_notification_channel_discriminator` adds `channel TEXT NOT NULL DEFAULT 'telegram' CHECK channel IN ('telegram','email')` to `membership_notifications` AND `booking_notifications`. Drops existing UNIQUE; recreates as `(subject_id, kind, channel)`. Backfill `channel='telegram'` for existing rows (zero-row migration in dev; idempotent in production since data is reproducible by next cron tick).
- [x] **NOTIFY-07**: Extend `app/workers/scheduled/send_expiring_notifications.py` (06:15 Europe/Moscow cron) — for each affected membership: Telegram-first attempt as today; on `SendResult.blocked` AND `client.email IS NOT NULL` AND opt-in flag set (or simple "fallback" policy resolved at discuss-phase), enqueue email via `EmailDispatcher` slot. `membership_notifications` idempotency row inserted on successful send only (preserves v1.3 NTF-05 invariant per channel).
- [x] **NOTIFY-08**: 6 locked Russian email expiring templates `EMAIL_EXPIRING_{7D,3D,1D}_VARIANT_{A,B}` (anti-oracle A/B via `client_id.bytes[0] & 1` per v1.3 D-27 lineage; same `{end_date}` Russian long-form format `16 мая 2026 г.`). Owner sign-off enumerated per constant. NBSP (`U+00A0`) as `&nbsp;` in HTML body, literal NBSP in plain-text (PITFALLS Outlook-NBSP fix).
- [x] **NOTIFY-09**: Extend `app/workers/scheduled/send_booking_reminders.py` (06:35 Europe/Moscow cron) — same dual-channel pattern as NOTIFY-07. Booking reminders 24h before slot; fallback or parallel email if Telegram fails. `booking_notifications` idempotency unchanged at row level (now keyed by `channel`).
- [x] **NOTIFY-10**: 4 locked Russian email booking templates: `EMAIL_BOOKING_CONFIRMED`, `EMAIL_BOOKING_CANCELLED_BY_CLIENT`, `EMAIL_BOOKING_CANCELLED_BY_OWNER`, `EMAIL_BOOKING_REMINDER_24H`. Mirror Telegram constants in `app/modules/bookings/notifications.py` (D-39-02 module ownership preserved — copy lives in modules, not in `integrations/email/`). Owner sign-off per constant.
- [x] **NOTIFY-11**: Payment-receipt email — service hook in `app/modules/payments/service.py` `record_payment` AND `issue_refund` commit paths. After successful commit, enqueues receipt email via `EmailDispatcher` slot. New `payment_receipts` idempotency table with UNIQUE `(payment_id, channel)` ensures no double-receipt across docker-restart races. Email is best-effort (failure does NOT roll back the payment commit — receipt is informational, not the audit row).
- [x] **NOTIFY-12**: 2 locked Russian email payment-receipt templates: `EMAIL_PAYMENT_RECEIPT_SALE`, `EMAIL_PAYMENT_RECEIPT_REFUND`. Body includes payment amount via `formatMoney` (NBSP-safe), receipt timestamp, plan/package snapshot description, `actor_display_name` of operator who recorded it ("Принял: Анна П."). Locked code constants; owner sign-off per constant.
- [x] **NOTIFY-13**: New LOCKED audit event `payment_receipt_emailed` (already pre-registered in INFRA-34). Pydantic payload includes `payment_id`, `channel='email'`, `audit_correlation_id` linking to the original `payment_recorded` / `refund_issued` audit row. Read-side query for owner ops dashboard: "did we send a receipt for payment X?" trivially answerable.
- [x] **NOTIFY-14**: Eager-import discipline (REG-29-04 mirror) — new ORM models (`email_send_log`, `payment_receipts`, any new `password_reset_tokens`) MUST be imported in `app/workers/__init__.py` so cron one-shot scripts can see them at boot time. Boot-time invariant logs `Base.metadata.tables.keys()` count. `tests/test_workers_eager_import.py` AST introspection verifies.

### OpenAPI drift gate refresh — HANDOFF-03..04 (Phase 46)

Bundled with milestone verification (VER-09..14) in Phase 46 as the serialization point — mirrors v1.5 Phase 40 shape where handoff and verification ship together as the final gate.

- [x] **HANDOFF-03**: Atomic byte-stable regen of `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts` exposing every new v1.6 path: `/api/v1/users` (GET/POST), `/api/v1/users/{id}/deactivate`, `/api/v1/users/{id}/reactivate`, `/api/v1/users/{id}` (DELETE), `/api/v1/users/invitations/accept`, `/api/v1/users/invitations/{id}/revoke`, `/api/v1/auth/password-reset/request`, `/api/v1/auth/password-reset/confirm`, `/api/v1/_internal/email/webhook`. `otp/request` updated to surface the `channel` parameter. CI `git diff --exit-code` gate green on both artifacts.
- [x] **HANDOFF-04**: Extend `packages/api-client/src/schema.contract.test.ts` with `AssertNonNever` compile-time forward-guards for every new v1.6 path (path + method + request-body realisation + 2xx-response realisation). Count grows from 61 → ~73. README v1.6 changelog section added under `apps/backend/README.md` documenting all new endpoints. Postman handoff updated for any external design-team consumer.

### Milestone verification — VER-09..14 (Phase 46)

Backend-only operator-runbook discipline (mirrors v1.3 Phase 29 + v1.4 Phase 36 + v1.5 Phase 40 — but explicitly budget time for runbook scaffolding hardening per DEFER-40-01 lesson).

- [x] **VER-09**: 7+ operator API-contract scenarios via curl against `docker compose up` live stack: (a) owner creates user → invitation email arrives in sandbox → user accepts → password set → user logs in; (b) owner deactivates user → user's refresh families revoked → next API call returns 401 `account_inactive`; (c) user requests password reset → email arrives → user resets → all old sessions invalidated → user logs in with new password; (d) password-reset request for non-existent email returns same 202 + identical body + bounded timing (anti-oracle); (e) expiring-7d for client with verified email but Telegram blocked → email fallback fires with idempotency row in `membership_notifications` channel='email'; (f) cash sale recorded → receipt email arrives; (g) owner soft-deletes user → re-invites different person with same email → succeeds (INSERT new row); (h) ARQ cron 06:15 → 06:35 chain stays in window even with mocked provider 5xx (circuit breaker opens, cron completes on time). Verbatim HTTP transcripts captured.
- [x] **VER-10**: Race tests (≥6, against real Postgres): (1) token replay race — two concurrent `POST /password-reset/confirm` with same token, one wins atomically; (2) soft-delete + re-invite race — concurrent `DELETE /users/{old}` + `POST /users` with same email, exactly one new row visible; (3) deactivate + `/refresh` race — refresh race-loses to deactivation in same UoW; (4) bounce-webhook + active-send race — webhook arrival mid-send classified correctly; (5) double-pings race — two concurrent expiring-cron invocations on same membership produce exactly one `email` row in `membership_notifications`; (6) RFC 2047 round-trip — Cyrillic subject encoded-word round-trips byte-stable.
- [x] **VER-11**: Integration tests gating anti-oracle: `test_password_reset_no_oracle.py` (4 cases × identical body × bounded timing within 100ms tolerance × audit emitted in both branches) + `test_otp_email_anti_oracle.py` (AUTH-EM-04 cases). Both must pass at the gate; failure blocks milestone close.
- [x] **VER-12**: Email-deliverability probe (live, not mocked) — probe-send one email to one yandex.ru recipient + one mail.ru recipient + one rambler.ru recipient. Inspect `Authentication-Results` header in delivered mail (SPF=pass, DKIM=pass, DMARC=pass alignment). Captured as evidence in `.planning/milestones/v1.6-VERIFICATION-LOG.md`. (Recipients can be owner's personal accounts.)
- [x] **VER-13**: 6/6 CI gates green captured as evidence: backend ruff + mypy --strict + pytest + import-linter + OpenAPI drift gate + frontend codegen drift gate. Plus SVC001 AST commit-gate green for `users/service.py` + `auth/password_reset_service.py`. Plus `LOCKED_EMAIL_TEMPLATES` AST gate green (no raw-string dispatcher calls).
- [x] **VER-14**: Owner sign-off — enumerated by every locked Russian email template constant name (mirroring D-27-OWNER-COPY-LOCK + D-39-02 module-scope copy pattern). Sign-off row recorded in `.planning/milestones/v1.6-VERIFICATION-LOG.md`. Inline regressions discovered at the gate fixed-in-place at the v1.4/v1.5 hard-cap discipline (≤5 inline fixes; >5 → roll forward as DEFER-N).

---

## Future Requirements (deferred from v1.6 scope)

Items raised during research that are NOT in v1.6 P1 but should land in a future milestone.

- **Owner weekly digest** (bounces + deactivations + failed sends) — needs ≥1 month of `email_send_log` data accumulation. Target: v1.8 Reports + Audit Log read API.
- **Dual-channel resolution** (`clients.preferred_channel ∈ {auto, telegram, email, both}`) — admin-web edit only, no client-facing UI. Optional P2 in v1.6 if cheap; otherwise v2.0 with frontend integration.
- **DMARC `p=quarantine` → `p=reject` policy escalation** — v1.6 ships `p=none` then `p=quarantine`; full reject deferred to v1.7 after ≥1 month of clean DMARC reports.
- **Aggressive bounce-driven `email_verified=false` flag flipping** — v1.6 passive-logs only; v1.7 introduces automated suppression list.
- **Client-facing email preference page** — single-zal scope (~100 clients/gym); admin-web edit suffices; client self-service deferred to v2.0.
- **Owner read-side `GET /api/v1/audit-log`** with multi-actor filtering — v1.6 ships denormalised `actor_email_snapshot` write side; read API is v1.8 Reports.

## Out of Scope (explicit exclusions, locked at this milestone)

Documented anti-features (per FEATURES.md 11-item list) — explicit non-goals for v1.6 regardless of bandwidth.

- **Preference centre with marketing categories** — Sportzal sends transactional email only; preference centre is a marketing-product concept and out of model.
- **Marketing campaigns / mailing lists / segmentation** — different product surface; not in CRM Core.
- **TOTP / WebAuthn MFA** — Telegram OTP + email OTP already provide step-up authentication via channel-fan-out; explicit MFA is over-scope.
- **Custom RBAC roles beyond owner/reception** — single-zal scope; owner/reception split is sufficient. Enterprise multi-role is out-of-scope until multi-tenancy considered (NEVER per project Constraint).
- **In-app inbox / notifications panel** — admin-web is frozen-as-of-v1.3 mock-reference; production admin app is design-team scope.
- **Plaintext password sent in email** — cardinal-sin anti-pattern (Specops/OWASP/Auth0 unanimous). Invitation token to set initial password is the only path.
- **Dual-email-per-user** — single email per user, single recovery channel. Simpler operational model.
- **App-layer bounce retry** — provider SDK or ARQ retries only; the application never retries bounced sends.
- **Multi-channel OTP race (any-of-N delivery)** — user picks ONE channel per OTP request; no fan-out race.
- **Self-service signup** — Sportzal is operator-onboarded only. Owner invites via `POST /api/v1/users`.
- **Production Stripe / non-РФ-accessible providers** (Resend, SendPulse RU-restricted, Mailgun depending on sanctions snapshot) — РФ project constraint pinned in CLAUDE.md.

---

## Traceability

Populated by `gsd-roadmapper` 2026-05-18. 6 phases (41-46), 48/48 v1.6 requirements mapped — 100% coverage, no orphans, no duplicates.

| REQ-ID | Phase | Status |
|--------|-------|--------|
| INFRA-34 | Phase 41 | Active |
| INFRA-35 | Phase 41 | Active |
| INFRA-36 | Phase 41 | Active |
| INFRA-37 | Phase 41 | Active |
| INFRA-38 | Phase 41 | Active |
| INFRA-39 | Phase 41 | Active |
| INFRA-40 | Phase 41 | Active |
| EMAIL-01 | Phase 42 | Active |
| EMAIL-02 | Phase 42 | Active |
| EMAIL-03 | Phase 42 | Active |
| EMAIL-04 | Phase 42 | Active |
| EMAIL-05 | Phase 42 | Active |
| EMAIL-06 | Phase 42 | Active |
| EMAIL-07 | Phase 42 | Active |
| AUTH-EM-01 | Phase 42 | Active |
| AUTH-EM-02 | Phase 42 | Active |
| AUTH-EM-03 | Phase 42 | Active |
| AUTH-EM-04 | Phase 42 | Active |
| USERS-01 | Phase 43 | Active |
| USERS-02 | Phase 43 | Active |
| USERS-03 | Phase 43 | Active |
| USERS-04 | Phase 43 | Active |
| USERS-05 | Phase 43 | Active |
| USERS-06 | Phase 43 | Active |
| USERS-07 | Phase 43 | Active |
| RESET-01 | Phase 44 | Active |
| RESET-02 | Phase 44 | Active |
| RESET-03 | Phase 44 | Active |
| RESET-04 | Phase 44 | Active |
| RESET-05 | Phase 44 | Active |
| RESET-06 | Phase 41 | Active |
| NOTIFY-06 | Phase 45 | Active |
| NOTIFY-07 | Phase 45 | Active |
| NOTIFY-08 | Phase 45 | Active |
| NOTIFY-09 | Phase 45 | Active |
| NOTIFY-10 | Phase 45 | Active |
| NOTIFY-11 | Phase 45 | Active |
| NOTIFY-12 | Phase 45 | Active |
| NOTIFY-13 | Phase 45 | Active |
| NOTIFY-14 | Phase 45 | Active |
| HANDOFF-03 | Phase 46 | Active |
| HANDOFF-04 | Phase 46 | Active |
| VER-09 | Phase 46 | Active |
| VER-10 | Phase 46 | Active |
| VER-11 | Phase 46 | Active |
| VER-12 | Phase 46 | Active |
| VER-13 | Phase 46 | Active |
| VER-14 | Phase 46 | Active |

**Coverage summary:** Phase 41 = 8 reqs (INFRA-34..40 + RESET-06); Phase 42 = 11 reqs (EMAIL-01..07 + AUTH-EM-01..04); Phase 43 = 7 reqs (USERS-01..07); Phase 44 = 5 reqs (RESET-01..05); Phase 45 = 9 reqs (NOTIFY-06..14); Phase 46 = 8 reqs (HANDOFF-03..04 + VER-09..14). Total = 48 ✓

---

## Open Conflicts to Resolve at Discuss-Phase

Carried verbatim from `research/SUMMARY.md` — each phase's discuss-phase resolves the conflicts in its scope before plan-phase runs.

1. **Email provider choice** (EMAIL-01 + EMAIL-02 scope) — Yandex Cloud Postbox primary vs Unisender Go fallback vs other. Resolved at Phase 42 discuss-phase.
2. **Reset-token storage** (RESET-* scope) — itsdangerous stateless signed tokens vs DB `password_reset_tokens` table. Both preserve anti-oracle. Resolved at Phase 44 discuss-phase (initial scaffolding decision may need flagging at Phase 41 if a token-table migration is required).
3. **`notifications` module status** — keep as placeholder (per D-39-02) vs resurrect as channel-multiplexer. Synthesizer leans toward placeholder. Resolved at Phase 45 discuss-phase.
4. **Template engine** (EMAIL-* + NOTIFY-* scope) — Jinja2 SandboxedEnvironment vs `Final[str]` f-string templates per D-39-04. Resolved at Phase 42 discuss-phase (binds first; Phase 45 inherits).
5. **`User` ORM ownership** (INFRA-* + USERS-* scope) — hoist to `app/core/models.py` vs `UserLookup` Protocol slot. Resolved at Phase 41 discuss-phase.
6. **Phase numbering** — PITFALLS 5 phases vs ARCHITECTURE 8 phases. RESOLVED by roadmapper 2026-05-18: 6 phases (41-46), coarse granularity compression with dependency-graph fidelity.
7. **Email verification flow for owner-added accounts** — trust owner-entered addresses vs click-to-verify (industry best practice). Resolved at Phase 43 discuss-phase.

---

*Total: 48 requirements across 8 categories. Continues phase numbering from v1.5 (last phase: 40 → next phase: 41).*
*Created: 2026-05-18. Locked at milestone-open time. Traceability table populated by roadmapper 2026-05-18 — 6 phases (41-46), 48/48 mapped. Modifications require explicit Decision row + commit per `/gsd-evolution` discipline.*
