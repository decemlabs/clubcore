# Pitfalls Research — v1.6 Email channel + Multi-user admin

**Domain:** Adding email-channel + multi-user admin to a Russian-market single-gym CRM that already has Telegram channel, anti-oracle invariants, locked-Russian-copy, idempotency tables, refresh-rotation families, and an AST-gated audit-event taxonomy.
**Researched:** 2026-05-18
**Confidence:** HIGH (system-specific pitfalls grounded in PROJECT.md / RETROSPECTIVE.md / MILESTONES.md patterns) + MEDIUM (Russian-locale + provider deliverability surface)

> All pitfalls below are framed against **existing** invariants. The hardest v1.6 mistakes will be the ones that quietly weaken an invariant the codebase already enforces (anti-oracle DM equality, AST `audit.emit` gate, partial-UNIQUE idempotency, locked-copy owner sign-off, refresh-family race tolerance). Generic "use SPF" advice is intentionally minimised.

---

## Critical Pitfalls

### Pitfall 1: Email channel breaks the anti-oracle invariant that Telegram channel pays for

**What goes wrong:**
The Telegram `/checkin` and `/book` handlers spend code complexity to enforce D-20-9: stranger / expired-membership / inactive-client / frozen-membership all receive the **same** DM — no oracle leak (see `apps/backend/app/modules/bookings/notifications.py:35` `_BOT_BOOK_DENIED_DM`, `_DM_NO_MEMBERSHIP` in visits). When email is added as a parallel channel, the natural reflex is "use a different template per failure reason" because email is verbose and "feels safe." That reflex turns email into the oracle that Telegram refused to be: an attacker can probe an email-address by triggering a flow (e.g. password-reset, expiring-soon trigger after admin-poke) and reading either the response code or the bounce signal.

**Why it happens:**
1. Email feels like "private one-to-one" so developers relax the constraint that was obvious in Telegram (where one DM string protected six failure modes).
2. The Telegram anti-oracle rule is encoded as locked Russian DM constants in `app/modules/*/notifications.py`; email templates will live somewhere else (probably `app/integrations/email/templates/`) and the constant-level proximity is lost.
3. Provider features (Resend tags, SES configuration sets) tempt per-reason templating because it improves analytics — at the cost of the oracle.

**How to avoid:**
- Mirror the bookings/notifications.py pattern: put email subject + body as **`Final[str]` constants** in `app/modules/<module>/email_notifications.py` next to the existing Telegram DM constants, not in `integrations/email/`. The proximity makes the equality auditable.
- For password-reset / invitation-accept flows: **always return HTTP 202 + identical generic copy** regardless of whether the email exists, is deactivated, is owner-only, or is the same user re-requesting. Send the email asynchronously via ARQ; the HTTP response carries no oracle.
- Extend the `LOCKED_AUDIT_EVENTS` AST gate concept to email: a `LOCKED_EMAIL_TEMPLATES` frozenset listing every (subject, body) constant identifier, with a sibling AST test that forbids `mailer.send(subject=...)` with a string-literal subject that isn't in the frozenset.
- For account-enumeration paths specifically: a single integration test `test_password_reset_no_oracle.py` that triggers reset for `(existing-active, existing-deactivated, owner-account, non-existent)` and asserts (a) identical 202 response, (b) identical response headers minus `x-request-id`, (c) bounded-equal response timing (±50ms) so timing doesn't leak.

**Warning signs:**
- A pull request adds a "user not found" email template, or a "this account has been deactivated" email template.
- A `/auth/password-reset` endpoint returns 404 on unknown email.
- Provider analytics dashboard segments by `failure_reason` tag — that segmentation IS the oracle.

**Phase to address:** **Phase 41 (spec/foundations)** before any email integration code lands. The locked-template AST gate and the `test_password_reset_no_oracle.py` contract must exist before the first reset-flow endpoint is committed, mirroring how `LOCKED_AUDIT_EVENTS` was pre-registered in v1.3 Phase 24 (RETROSPECTIVE.md key lesson #1 from v1.3).

---

### Pitfall 2: Cross-channel double-pings (idempotency taxonomy was per-channel, not per-event)

**What goes wrong:**
`membership_notifications` has `UNIQUE (membership_id, kind)` and `booking_notifications` has the same shape — but `kind` was implicitly "telegram kind" because there was only one channel. When email lands, the obvious wrong move is to write `kind='expiring_7d'` from both the Telegram cron and the email cron — and now the same row blocks the email send (because Telegram already ran), or worse, the email cron writes its own row with the same `kind` and a UNIQUE violation crashes the cron silently (or the cron retries forever via ARQ). The opposite wrong move — different `kind` per channel — lets a client receive a Telegram DM **and** an email for the same event, which is double-pinging and undermines the 06:15 single-tick discipline.

**Why it happens:**
v1.3 / v1.5 designed idempotency tables assuming Telegram as the only channel. The taxonomy was implicit. Without an explicit `channel` discriminator, the schema can't represent "the same event went out via two channels" coherently.

**How to avoid:**
- Migrate idempotency tables to a `(subject_id, kind, channel)` composite UNIQUE where `channel ∈ {'telegram','email'}`. Make this a single Alembic migration in Phase 41 before any provider integration: `0024_notification_channel_discriminator`.
- Notification dispatch becomes **per-client preference**: each client has a `notification_channel` preference (default: telegram if linked + email-fallback; email-only if Telegram not linked). The cron consults the preference and inserts exactly one idempotency row matching the channel actually used.
- Define a small `NotificationDispatcher` Protocol in `core/dependencies.py` (mirroring `ActiveMembershipResolver` and `HandlerContext`) with method `dispatch(client_id, kind, payload) -> Channel`; concrete implementations registered from `app/main.py` composition root. Cron writes the idempotency row using the returned `Channel`.
- Cross-channel **fallback semantics** must be explicit: if Telegram send fails 403 (user blocked bot), the cron may try email IF the client has a verified email AND the kind is allow-listed for fallback. Insert the idempotency row only for the channel that **succeeded** (preserves the v1.3 Phase 27 lesson: "insert idempotency row only on successful send").

**Warning signs:**
- A unit test or migration touches `*_notifications` table without adding a `channel` column.
- ARQ logs show `IntegrityError: duplicate key value violates unique constraint` for notification tables after email rollout.
- A client reports receiving both Telegram DM and email for the same `expiring_3d` event (double-ping bug report).

**Phase to address:** **Phase 41 (spec) for the schema decision + Phase 42-or-43 (notification dispatcher) for the Protocol slot**. The migration `0024_notification_channel_discriminator` must land before any email cron is written. The dispatcher Protocol is the same pattern as v1.2 `register_active_membership_resolver` (Decisions table entry "Cross-module callbacks via Protocol").

---

### Pitfall 3: Provider 5xx + ARQ retry storm collides with the 06:xx cron window

**What goes wrong:**
ARQ cron `send_expiring_notifications` runs at 06:15 MSK with `unique=True, keep_result=60`. If Resend / SES returns 5xx (provider degraded), the SDK retries internally; the ARQ job retries on exception. Cascading: a single 06:15 tick spawns 50 retry attempts in 60s, each holding a worker slot for the SDK timeout (default ~30s on most providers), and **blocks the 06:25 `expire_pt_packages` cron and 06:35 `send_booking_reminders` cron** because the same `arq-worker` container has finite concurrency (typically 10). The single failing provider takes down the whole 06:xx cron chain.

**Why it happens:**
1. Provider SDKs (`resend-python`, `boto3 sesv2`) ship with their own retry logic that's invisible to ARQ. Result: layered exponential backoff that wedges the worker.
2. ARQ retry defaults assume idempotent transient failures, not "provider is down for 30 minutes."
3. The current cron chain (06:05 expire → 06:15 expiring → 06:25 pt-expire → 06:35 booking-reminder) has 10-minute buffers but no per-job circuit breaker; one slow job eats the next window.

**How to avoid:**
- Set provider SDK retry counts to **0 or 1 max** (e.g. `resend.Client(retries=0)` or boto3 `Config(retries={'max_attempts': 1})`); let ARQ + the per-event idempotency row be the only retry mechanism.
- Add per-job `max_tries=2, retry_delay=30s` to the new email cron; after 2 attempts, fail the job loudly. The next 06:15 tick (24h later) is the retry — no thundering herd on the same morning.
- **Move email sends out of the cron path** into a fire-and-forget queued task: cron writes a row to `email_outbox` (status='pending'), a separate `send_outbox_emails` job drains it on a 1-minute schedule with bounded concurrency `max_jobs=3`. Cron tick stays under 60s even when the provider is degraded.
- Set an explicit per-job timeout `timeout=20` on the email-dispatcher job so a hung SDK call doesn't wedge the worker.
- Add a per-provider circuit breaker in Redis: key `sz:email:circuit:open`, TTL 5m, opened on 5xx, checked at the head of the dispatcher job — when open, the dispatcher returns immediately and the outbox row is untouched.

**Warning signs:**
- ARQ structlog `job_id`/`job_name` contextvars (Pitfall 14 mirror from v1.2 Phase 18) show overlapping `send_expiring_notifications` and `expire_pt_packages` jobs.
- Worker container memory creeps up overnight (queued retries holding HTTP clients open).
- Operator runbook scenarios time out at the 06:xx window (Phase 29 / Phase 36 verification regression class).

**Phase to address:** **Phase 43 (cron + worker integration)**, with the `email_outbox` table introduced in the same Alembic migration. The circuit-breaker + max_tries discipline is a CI-level concern: add an `assert` in the worker startup that `WorkerSettings.functions['send_outbox_emails']` has `max_tries <= 2` and `timeout <= 30`, mirroring the v1.2 `on_startup` cron-resolution invariant.

---

### Pitfall 4: Password-reset / invitation token replay or account hijack via email re-claim

**What goes wrong:**
Three concrete failure modes, all subtle:

1. **Replay:** Reset token is single-use in spec but the "mark consumed" UPDATE runs after `commit()` of the password change, so a concurrent request can use the same token twice (race). This is the v1.1 Phase 12.1 commit-gate bug class — audit emits looked fine but the row wasn't durable.
2. **Account hijack via email re-claim:** Owner deactivates reception user `alice@gym.ru`. Later, owner invites a new user with email `alice@gym.ru` (legitimate — Alice's replacement at front desk). The new invite-accept flow finds the existing soft-deleted user row and **reactivates it** (because the email already exists with UNIQUE) — the new operator now inherits Alice's `actor_user_id` in historical audit. Worse: if refresh-token family rows survive `is_active=False`, the new operator inherits Alice's sessions.
3. **Reset-link leak:** The link includes the token as a path parameter (`/auth/reset/{token}`); the token leaks via HTTP `Referer:` when the user opens the link and clicks any external link in the success page, or via proxy logs at the gym network, or via shoulder-surf if reception clicks the link on the front-desk terminal.

**Why it happens:**
- (1) The auth module already learned this lesson in Phase 12.1 (RETROSPECTIVE.md Key Lessons v1.1 #3, "Verify-on-the-wire, not verify-by-types") but the SVC001 commit-gate AST walker is scoped to `app/modules/auth/service.py` — a new `password_reset_service.py` file may be added at the same module level and the walker won't include it without an explicit scope extension.
- (2) The `users` table has `UNIQUE (email)` (auth/models.py:34) with no soft-delete partial-unique. The codebase pattern for `clients.phone` is `WHERE deleted_at IS NULL` (v1.1 Phase 8 decision); `users.email` is unconstrained on this axis because v1.1 didn't anticipate multi-user.
- (3) Standard webapp mistake; the gym front-desk terminal makes it worse (semi-public screen).

**How to avoid:**
- (1) Reset tokens stored hashed in a new `password_reset_tokens` table with columns `(id, user_id, token_hash, expires_at, consumed_at, created_at)` and a partial UNIQUE `(user_id) WHERE consumed_at IS NULL` so only one outstanding token per user. Token consumption is `UPDATE ... SET consumed_at = now() WHERE token_hash = :h AND consumed_at IS NULL RETURNING id` — the SQL is its own race arbiter; 0-row return → 409 `token_already_used`. Extend SVC001 AST walker to include any file matching `app/modules/auth/*.py` (not just `service.py`).
- (2) Two-fold defence: (a) Add Alembic migration adding partial UNIQUE `(lower(email)) WHERE deleted_at IS NULL` to `users` so soft-deleted emails can be reused **as new rows** (not by reactivating the old row); the invitation-accept flow MUST insert a new `users` row, never update an existing `is_active=False`. (b) Soft-delete a user must REVOKE all refresh-token families and INSERT a sentinel audit row `user_deactivated` — re-activation (if ever supported) requires explicit owner action with a new audit row. Forbid invitation-accept from touching an existing user row period: invitation-accept either inserts new or 409 `email_already_active`.
- (3) Token in `POST` body, not URL path. The reset link points to a tokenless landing page (`/auth/reset?id=<opaque-reset-session-id>`); the page reads the token from a `localStorage`/sessionStorage seeded by a one-time `GET /auth/reset/session/{id}` call that the SPA performs once. Better yet: token in URL fragment (`#token=...`) so it never hits any HTTP referer or proxy log; SPA reads `window.location.hash`.

**Warning signs:**
- A code review on the invite-accept path uses `UPDATE users SET is_active=true` (instead of INSERT).
- The reset URL appears in any HTTP access log.
- A test reuses the same reset token twice and the second attempt succeeds.
- `audit_log` has rows where `actor_user_id` belongs to a user with `is_active=False` (post-invite-accept anomaly).

**Phase to address:** **Phase 42 (user-management + invitation/reset flow)**. The partial-UNIQUE migration on `users.email` and the `password_reset_tokens` table should be in Phase 42's foundations plan; the SVC001 scope extension is a one-line change but must land in Phase 41 spec.

---

### Pitfall 5: `actor_user_id` historical interpretation breaks under multi-user

**What goes wrong:**
The audit-log infrastructure was effectively single-actor: there was one owner and ad-hoc DB-poked reception. Queries reasoned as "actor is either THE owner or a vanishingly small set of reception users." With multi-user, three things break:

1. **Audit traceability survives operator soft-delete only if FK is `ON DELETE RESTRICT` or `SET NULL`** — but the migration writer copies the `clients.created_by_user_id` shape (which is `RESTRICT`, per `apps/backend/app/modules/auth/models.py:4`) without checking that **the operator is a *gym staff* User, not a client**. RESTRICT on a deactivated user blocks the soft-delete; SET NULL loses traceability. The trade-off was never explicitly chosen — the v1.0 default leaked through.
2. **Idempotency-via-actor leaks across operators.** Currently some payment idempotency relies on `Idempotency-Key` header per-request, but cron-emitted audits use `actor_user_id=None`. If a future "owner-scoped idempotency" leaks into multi-user (e.g. "this owner already sold this membership today"), reception inheriting the same scope would replay-deny legitimate work.
3. **Refresh-family reactivation race.** Deactivated user logs in via still-valid refresh cookie before the family is revoked: the auth path checks `is_active` only on `/login`, not on `/refresh`. The deactivated operator gets a fresh access token. v1.1 Phase 5 `refresh-rotation family with ~5s reuse-window race tolerance` doesn't help — it tolerates by design.

**Why it happens:**
- (1) `models.py` comments say `ON DELETE RESTRICT on clients.created_by_user_id is acceptable because soft-delete-after-data-export is the supported flow` — that contract was for clients, but audit_log was implicit. No one documented the audit_log FK choice explicitly.
- (2) Idempotency taxonomy was per-request-key, not per-actor — but the boundary isn't enforced anywhere.
- (3) `/refresh` is the hot path; auth dependencies (`require_user`) check `is_active` on access tokens but the refresh path uses cookie + token_hash lookup without joining `users.is_active`.

**How to avoid:**
- (1) Pick `audit_log.actor_user_id` FK behaviour **explicitly and in writing**: `ON DELETE SET NULL` for audit_log + soft-delete-on-users (so operator can be deactivated and historical audits survive with `actor_user_id=NULL`, plus a `actor_email_snapshot` column denormalised at audit-write time, mirroring the v1.2 mandatory-snapshot pricing pattern). Migration `0023_audit_actor_snapshot` adds `actor_email_snapshot TEXT` and backfills it from current rows; emit-time validation in the canonical Pydantic `audit_payloads.py` registry enforces the snapshot.
- (2) Define explicitly: idempotency keys are **request-scoped, not actor-scoped**. Document this as a Key Decision row. Add an integration test `test_idempotency_key_cross_actor.py` that proves two operators using the same `Idempotency-Key` value get isolated results.
- (3) Add `users.is_active` check to the `/auth/refresh` path AND to the `require_user` access-token dependency. On deactivation, **revoke all refresh-token families immediately** (the existing per-family revoke from v1.2 Phase 23 HYG-03 already exists; deactivation calls it for every family of the deactivated user). Audit event `user_deactivated` fires the family revoke as part of the same UoW (caller-owns-txn pattern from v1.3 freeze).

**Warning signs:**
- An Alembic migration touches `audit_log` foreign keys without an explicit `ON DELETE` clause.
- A user is deactivated and 10 minutes later their access token still works.
- `audit_log.actor_user_id` is NULL on rows that should have an actor (vs cron rows which legitimately have NULL).

**Phase to address:** **Phase 42 (user management)** for the FK + `actor_email_snapshot` decision and the `/refresh` `is_active` join. Migration `0023_audit_actor_snapshot` lands in Phase 41 foundations alongside the locked-template gate (it's a schema decision, not user-mgmt code).

---

### Pitfall 6: Locked Russian copy lock breaks under email's richer surface

**What goes wrong:**
Telegram DMs are short plain-text. Email has subject + plain-text body + (likely) HTML body + footer + sender-name. Each surface is an independent point of locked-copy compromise:

- **Subject lines in Cyrillic** must be RFC 2047 encoded-word (`=?UTF-8?B?...?=` base64 or `=?UTF-8?Q?...?=` quoted-printable). Forgetting this breaks display on older Outlook / mail.ru clients; doing it wrong (e.g. exceeding the 75-char encoded-word limit, splitting in the middle of a multi-byte UTF-8 character) breaks rendering on yandex.ru. mail.ru in particular has known display quirks for non-encoded Cyrillic subjects.
- **NBSP (U+00A0) handling differs across clients.** The `formatMoney` helper produces NBSPs for ru-RU currency (`shared/lib/money.ts` CLAUDE.md note); Outlook for Windows renders them as `?` in some HTML contexts; Gmail web renders them correctly. Locked Russian copy that interpolates money will look broken to one of the two most-used desktop clients in РФ.
- **From: header with Cyrillic name** (e.g. `From: "Спортзал" <no-reply@sportzal.ru>`) requires RFC 2047 encoding of the display name; provider SDKs (Resend, SES, Mailgun) handle this inconsistently — some auto-encode, some pass through as raw UTF-8 and silently break.
- **Footer is jurisdictionally required** for РФ commercial mail (Закон "О рекламе" 38-ФЗ Art. 18 for marketing; transactional is exempt but the line is blurry — booking reminders skirt it). Forgetting the footer is a regulatory miss; adding the wrong footer is a locked-copy compromise.
- **D-27-OWNER-COPY-LOCK precedent:** owner sign-off is the gate, not a nice-to-have (RETROSPECTIVE.md v1.2 key lesson #2). Email surface multiplies the number of strings under that gate by ~3-4× (subject + body + footer + alt-text).

**Why it happens:**
The Telegram-locked-copy pattern (single `Final[str]` constant, owner sign-off in plan SUMMARY) doesn't compose with multi-part email content. The natural reflex is to put templates in Jinja2 files outside the codebase — at which point the AST gate that protects Telegram copy no longer protects email copy.

**How to avoid:**
- Email templates are **Python data classes (or `Final[str]` constants for each part)** in `app/modules/<module>/email_notifications.py`, NOT external Jinja files. Subject + plain-body + html-body are sibling constants; one owner-sign-off row covers the tuple as a unit.
- AST gate `LOCKED_EMAIL_TEMPLATES`: same shape as `LOCKED_AUDIT_EVENTS`, a frozenset of `(subject_constant_name, body_constant_name, html_body_constant_name)` triples. `email_mailer.send(...)` must take a `LockedEmailTemplate` enum, not raw strings.
- Subject encoding: use Python stdlib `email.headerregistry.Address` + `EmailMessage.set_content()` rather than provider SDK string interpolation. Stdlib does RFC 2047 correctly; provider SDKs vary. Unit test `test_email_headers_rfc2047.py` round-trips a known-Cyrillic subject through the rendering path and asserts the wire form starts with `=?UTF-8?`.
- NBSP discipline: HTML body templates render NBSPs as `&nbsp;` entities, not literal U+00A0; plain-text body keeps literal NBSP. Snapshot test renders one money-formatted template and diffs against a checked-in golden file.
- Footer: a single `RU_FOOTER_HTML` + `RU_FOOTER_PLAIN` constant interpolated automatically by the mailer. Owner sign-off on the footer is one row, not one per template.
- Owner sign-off discipline: same `D-XX-OWNER-COPY-LOCK` decision-row mechanism as D-27. Auto-advance under `workflow.auto_advance` is fine — the v1.3 precedent stands. But the sign-off row must enumerate **every locked constant identifier**, not say "all email templates."

**Warning signs:**
- A PR adds a `templates/*.html` file outside `app/modules/`.
- A subject line includes raw Cyrillic and the test suite doesn't probe wire-encoded form.
- Outlook screenshot in a Phase verification log shows `?` characters in money amounts.
- A SUMMARY.md sign-off row says "all v1.6 email templates" without enumeration.

**Phase to address:** **Phase 41 (spec) for the locked-template gate**, **Phase 43 (templates + rendering)** for the actual templates with explicit per-template owner sign-off. The footer + From: header decisions should be in Phase 41 because they affect the integration's API surface (mailer interface), not just template content.

---

### Pitfall 7: ARQ cron eager-import regression class repeats (REG-29-04 mirror)

**What goes wrong:**
v1.3 Phase 29 caught REG-29-04: the one-shot expiring-cron runner missed eager ORM-model import → first invocation returned `count=0` because SQLAlchemy hadn't seen the model. v1.5 Phase 36 caught REG-36-01: arq-worker compose `uv run arq` vs `arq` directly. v1.5 Phase 40 verification needed 4 hotfixes during runbook attempt. **Email integration will repeat this class** because: (a) a new email worker may be added (6th docker-compose service), (b) the email cron creates new ORM tables (`email_outbox`, `password_reset_tokens`, `notification_preferences`) that aren't imported by the worker module unless explicitly added, (c) the Resend / SES / Mailgun SDKs do their own module-level config that interacts with `on_startup` ordering.

**Why it happens:**
The `app/main.py` composition root imports modules transitively for the FastAPI process, but `app/workers/__init__.py` (or wherever `WorkerSettings` lives) has its **own** transitive closure. New tables added in a different module than where the cron lives are invisible unless eagerly imported.

**How to avoid:**
- Add Phase 41 / Phase 43 a verification step that explicitly mirrors the v1.3 REG-29-04 lesson: a 1-line `from app.modules.<new_module> import models  # noqa: F401` in `app/workers/__init__.py` for every new business module that the worker touches.
- Add an `on_startup` invariant: at worker boot, log the set of mapped table names (`Base.metadata.tables.keys()`) and assert that the set contains every table the cron functions query. Failure-to-import is loud, not silent.
- One-shot script discipline: `scripts/run_<cron>_once.py` files MUST import models eagerly. Codify as a test: a `tests/test_oneshot_scripts_eager_import.py` that introspects each `scripts/run_*_once.py` file's AST for the eager-import block.
- Milestone-verification-as-phase (v1.3 Phase 29 model, v1.5 Phase 36 model): one of the v1.6 phases is the verification phase against live docker-compose. Budget ≥1 day for it.

**Warning signs:**
- A Phase verification scenario reports "cron returned 0 first run, then non-0 after restart" (REG-29-04 signature).
- arq-worker logs at boot don't list one of the new email-related tables.
- A `scripts/run_*_once.py` file lacks `import app.modules.<x>.models`.

**Phase to address:** **Phase 41 (spec)** for the eager-import test discipline, **Phase 43 (cron integration)** for the per-cron implementation, **Phase 45-ish (milestone verification)** for live-stack proof.

---

### Pitfall 8: Provider secret + domain + sandbox mode rotting at the env boundary

**What goes wrong:**
Email providers have multi-part credentials: API key + verified sending domain + (sometimes) region + sandbox flag. Storing them as `EMAIL_PROVIDER_API_KEY` alone fails because:

- Sandbox mode (Resend `re_sandbox_...`, SES sandbox-mode account) silently allows sends to **only verified addresses** — works in dev, fails in prod for any unknown client email.
- Domain not in env: production accidentally sends from `acme.sandbox.resend.dev` because the prod env forgot `EMAIL_FROM_DOMAIN`; mail.ru DMARC rejects; Telegram channel keeps working so the bug stays hidden for days.
- Key rotation: the SDK caches the key at module import (Resend Python SDK pattern); rotating the key requires restart, not env reload. Phase 27 expiring-cron tick at 06:15 will still use the stale key for the full 24h until the next deploy.

**Why it happens:**
v1.1+ env discipline has `.env.example` as single source of truth (Decisions table CR-01) but email providers expand the secret surface 4× (API key + domain + region + webhook signing secret for bounces).

**How to avoid:**
- Pydantic Settings adds a `class EmailProviderSettings` block with required fields: `api_key`, `from_domain`, `from_address`, `webhook_signing_secret`, `sandbox_mode: bool = False`. Settings validation **fails at boot** if `from_domain` is empty in non-sandbox mode.
- A boot-time integration check (gated behind `EMAIL_PROVIDER_PROBE_AT_BOOT=true`, default off in test) sends a probe to the provider's `/domains` or equivalent endpoint and asserts the configured `from_domain` is verified. Loud failure on misconfig.
- Webhook signing secret is mandatory for bounce + complaint webhooks (all major providers sign these). Verify signature in `app/api/v1/webhooks/email/bounce.py` before processing — defends against attackers POSTing fake bounces to mark legitimate clients as undeliverable.
- `.env.example` enumerates every email-related variable with placeholder values + a comment indicating sandbox vs prod (e.g. `EMAIL_API_KEY=re_test_...  # sandbox: re_test_..., prod: re_prod_...`).

**Warning signs:**
- A production deploy sends from `sportzal.test.local` or a provider sandbox domain.
- A bounce webhook is processed without signature verification.
- The settings module hard-codes the email region (e.g. `eu-central-1` for SES).

**Phase to address:** **Phase 41 (spec / provider selection + settings)**. Provider choice itself is a STACK.md / SUMMARY.md decision; this pitfall is about the settings surface once the choice is made.

---

## Moderate Pitfalls

### Pitfall 9: Bounce / complaint webhooks silently degrade client deliverability over time

**What goes wrong:**
Provider sends `email.bounced` or `email.complained` webhook. Backend receives it but doesn't act → keeps sending to the bounced address → provider gradually throttles the sender domain → all deliverability suffers (including transactional OTP). This is the standard email-deliverability decay path.

**How to avoid:**
- Add `clients.email_deliverable: BOOL DEFAULT TRUE` column (or `email_status: TEXT` with `{'unknown','verified','bounced','complained'}`).
- Bounce webhook handler transitions `bounced` (hard bounce) → `email_deliverable=False`; subsequent sends skipped at the dispatcher level (returns Channel.SKIPPED, idempotency row not written, audit event `email_send_skipped_bounced`).
- Soft bounces (4xx-class) tracked with retry count; flip to hard after 3.
- Complaint webhook → immediate `email_deliverable=False` + audit `email_complaint_received` (compliance evidence).
- Owner UI surface (deferred to v2.0): "X clients have undeliverable email" filter for outreach via Telegram.

**Phase to address:** Phase 43 (provider integration) — webhook handlers + status column.

---

### Pitfall 10: OTP email fallback path repeats the Telegram OTP flow's TTL/attempt design without recheck

**What goes wrong:**
Telegram OTP design (Phase 7): 6-digit, TTL 5 min, max 5 attempts. Email OTP fallback copy-pastes these numbers. But email delivery has **30-second to 5-minute latency variance** (provider queueing + spam-filter scrubbing) — 5-minute TTL with provider lag of 4 minutes leaves 60 seconds of usable window. User retries → second OTP arrives → user enters first OTP → expired → user enters second → first one's expiry race makes both look invalid.

**How to avoid:**
- Email OTP TTL = 10 minutes (Telegram TTL × 2 to absorb provider lag).
- "Resend OTP" button enforces 60s cooldown server-side; second OTP invalidates the first (only one active per user-channel).
- Email OTP attempts = 5 (same as Telegram) but `otp_codes` table needs `channel` column to prevent cross-channel reuse and to scope rate-limiting per channel.

**Phase to address:** Phase 42 (multi-channel auth + OTP table extension).

---

### Pitfall 11: Multi-user invitation token TTL collides with onboarding reality

**What goes wrong:**
Invitation token TTL set to 24h (security-conscious default) — but the typical gym owner adds reception ahead of their start date by 3-5 days. User receives invite, doesn't open until day 3, token expired, has to ask owner to re-send. Operator friction → owner extends TTL to 30 days → token is now a long-lived secret in inboxes → password-reset-style replay attacks.

**How to avoid:**
- Invitation TTL = 7 days (covers typical onboarding lag).
- Invitation token consumption invalidates the token immediately on first successful POST (regardless of password-set success — separate the steps with a short-lived intermediate session).
- "Token expired" path triggers an owner-action workflow, not a user-action one (the user can't self-rescue; they ping the owner via Telegram).

**Phase to address:** Phase 42 (user management).

---

### Pitfall 12: Provider rate limits (429) interact badly with OTP burst sends

**What goes wrong:**
Provider rate-limit is typically 10 req/s sustained for new accounts. Multi-user invitation flow + bulk OTP send + expiring-soon batch (50 clients × 06:15 tick) can burst above 10 req/s and trigger 429. Provider 429 is opaque to ARQ → cron job sees an exception, retries the whole batch, queues more retries, never drains.

**How to avoid:**
- `email_outbox` table + 1-minute dispatcher job with bounded concurrency = natural rate limiter (3 workers × 1 send each = 3 req/s peak).
- Explicit `asyncio.Semaphore(5)` at the dispatcher entry to cap concurrent provider calls.
- 429 response → exponential backoff (5s, 30s, 5m) inside dispatcher, NOT inside the per-send job (so the burst gets paced, not dropped).

**Phase to address:** Phase 43 (cron + worker integration).

---

## Minor Pitfalls

### Pitfall 13: `audit.emit` event-name overflow without taxonomy planning

`LOCKED_AUDIT_EVENTS` is currently 56-entry frozenset. v1.6 adds ~10-12 events (`email_sent`, `email_bounced`, `email_complained`, `user_invited`, `user_invitation_accepted`, `user_deactivated`, `password_reset_requested`, `password_reset_completed`, `email_verification_sent`, `email_verification_completed`, `notification_preference_changed`). Pre-register in Phase 41 foundations (RETROSPECTIVE.md v1.3 key lesson #1 — pre-registration discipline).

**Phase to address:** Phase 41.

---

### Pitfall 14: New email worker becomes 7th docker-compose service vs ARQ-batch

`docker-compose.yml` is at 6 services. Adding a 7th for email (e.g. a separate Resend webhook receiver if hosted) creates ops surface area. Prefer: email send + bounce-webhook receive both live inside `web` + `arq-worker` containers; webhook receiver is just a FastAPI endpoint at `/api/v1/webhooks/email/*` with signature verification.

**Phase to address:** Phase 43.

---

### Pitfall 15: SPF-aligned domain ≠ DMARC-aligned domain when From: uses different subdomain

If `EMAIL_FROM_DOMAIN=mail.sportzal.ru` but SPF record is on `sportzal.ru`, DMARC alignment can fail on strict policy. Document the explicit DNS layout in Phase 41 spec (probably: SPF + DKIM + DMARC all on `mail.sportzal.ru`, with `_dmarc.sportzal.ru` policy in `p=quarantine` for the parent).

**Phase to address:** Phase 41 (DNS spec is a precondition to provider selection).

---

### Pitfall 16: mail.ru lacks DKIM/SPF outbound but is the dominant recipient

mail.ru does not publish SPF/DKIM for **outbound** sender authentication (per mxtoolbox / dmarc-research). That doesn't affect us — but it means: mail.ru users **receive** from us, and their inbound spam filter is weaker on alignment heuristics. Don't optimise solely for mail.ru deliverability; yandex.ru is the stricter inbox and the right deliverability tuning target.

**Phase to address:** Phase 41 (provider + DNS spec).

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Store reset tokens in plain text in DB | Simpler debugging | Full DB read = full account takeover via token reuse | Never. Hash with SHA-256 minimum (faster than Argon2 and acceptable for short-lived tokens). |
| Reuse Telegram `notifications.py` constants for email | Less duplication | Couples two channels' copy; anti-oracle harder to audit per-channel | Never. Sibling `email_notifications.py` per module. |
| Skip the `channel` column on idempotency tables, use `kind='telegram_expiring_7d'` vs `kind='email_expiring_7d'` | One less migration | Doubles taxonomy; analytics + audit queries fork per channel; cross-channel dedup impossible | Never. Add the column in Phase 41 schema migration. |
| Pass through to provider SDK retry/timeout defaults | Less config | Provider degradation cascades into worker wedge (Pitfall 3) | Never for cron-path code. Acceptable only for one-shot scripts that have human supervision. |
| Send password-reset email with token in URL path | Simpler SPA | Token leaks via Referer, proxy logs, shoulder-surf | Never. Token in `#fragment` or POST body only. |
| Skip `users.email` partial-UNIQUE on `WHERE deleted_at IS NULL` | Less migration churn | Email reuse hijacks deactivated operator's audit trail (Pitfall 4 case 2) | Never. Mirror the `clients.phone` partial-unique pattern. |
| Single From: domain across transactional + marketing | One DNS setup | Marketing complaints poison transactional reputation | Acceptable for v1.6 (transactional only); revisit if marketing emails are added later. |
| Inline email template HTML in `Final[str]` constants | AST gate works | Hard to preview in dev; designers can't iterate | Acceptable in v1.6 — design team is external; locked copy is owner-signed-off; preview is a CI step (snapshot test). |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Resend Python SDK | Module-level `resend.api_key = ...` cached at import → key rotation requires restart | Wrap SDK in a thin `EmailClient` class that reads settings per-call; cache only client builder, not credentials |
| AWS SES (boto3) | Default `retries.max_attempts=3` (or 10 on legacy mode) compounds with ARQ retries | `Config(retries={'max_attempts': 1, 'mode': 'standard'})` |
| Mailgun | Webhooks signed with HMAC-SHA256 of `timestamp + token` — easy to verify wrong field order | Use Mailgun's official webhook-verification function or a tested helper; never roll your own |
| Yandex Postmaster Tools | Domain reputation reports need DMARC `rua=` to point at a yandex-friendly endpoint | Use the provider's DMARC aggregation feature (Resend, SES all offer it) — don't build a parser |
| Provider sandbox mode | Sends succeed to verified addresses, silently drop to unverified — works in CI, fails in prod | Pydantic Settings flag `sandbox_mode: bool` + assertion at boot that prod env is non-sandbox |
| Webhook receiver behind nginx | nginx default body size 1MB → bounce webhooks with full original message attached can exceed | Set explicit `client_max_body_size 4M;` for `/api/v1/webhooks/email/*` location (infra/nginx) |
| Provider DKIM key rotation | New key published in DNS but provider not signaled → in-flight sends signed with old key fail alignment | Coordinate via provider's "key rotation" workflow; gate switch with a CI smoke test (probe a known address, check DKIM-Signature header) |
| Python `email.headerregistry.Address` with Cyrillic display-name | Library auto-encodes display name; provider SDK may **re-encode** the already-encoded string → double-encoded `=?UTF-8?B?PT9VVEYtO...` garbage | Pass display-name as raw Python `str` to provider SDK; let SDK encode; round-trip test on the wire form |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Send loop without dispatcher concurrency cap | First 50 sends queue, last 200 timeout | `asyncio.Semaphore` + outbox table | At ~50 clients (early prod) — i.e. immediately |
| ARQ job per-email vs per-batch | Redis queue depth balloons; ARQ admin dashboard unusable | Outbox row + one drainer job that processes N rows per tick | At ~500 emails/day (v1.7+) |
| Synchronous bounce-webhook processing | Provider retries the webhook on 5xx → cascade | Webhook handler accepts → enqueues → returns 200 immediately | Always (providers retry within seconds) |
| Render HTML body inside the SQL transaction | Long-held connection during Jinja render | Render outside the txn (in service layer); txn holds only the outbox INSERT | At ~10 concurrent sends |
| `SELECT * FROM email_outbox WHERE status='pending'` without LIMIT | Drainer scans full table after a backlog spike | `SELECT ... ORDER BY created_at LIMIT 100 FOR UPDATE SKIP LOCKED` | At ~1000 backlog rows |
| Bounce status checked on send-side (read full table) | Every send does `SELECT clients.email_deliverable WHERE id=...` — N+1 | Join at outbox-row write time, denormalise `email_deliverable_at_send_time` snapshot | At ~100 concurrent sends |

---

## Security Mistakes

| Mistake | How Users Suffer | What to Do Instead |
|---------|-------------------|---------------------|
| Reset token in URL path | Leaks via Referer / proxy / browser history / shoulder-surf | Token in URL fragment (`#token=...`) consumed by SPA without server round-trip |
| Different response for "email exists" vs "email not found" on reset | Account enumeration → targeted phishing | Single 202 response with single generic body for all four cases |
| Webhook receiver without signature verification | Attacker forges bounces, marks legitimate clients undeliverable → silent client lockout | HMAC verify with timing-safe compare (`hmac.compare_digest`) before any processing |
| Plain text reset tokens in DB | DB read = account-takeover-at-scale | SHA-256 hash; verify by hash; cleanup expired rows nightly |
| Invitation token survives password set | Replay invitation → second account-set | Invalidate token atomically on first POST regardless of password set success; intermediate short-lived session for the form |
| `password_reset_tokens` without rate limit per-email | Attacker triggers 1000 emails to `victim@target.ru` to fill inbox | Rate-limit POST /auth/password-reset by email (1/min, 5/hour); insert hashed-email-only row to detect; same generic 202 response |
| Bot DM oracle replicated in email subject | "Your gym membership has expired" subject leaks status to anyone with email access | Generic subject "Сообщение от Спортзал" + body carries detail; consistent across all states |
| OTP attempt-count reset on resend | Attacker forces fresh OTP every 30s, brute-forces in parallel | Attempt counter scoped per `(user_id, channel, current_active_otp_id)` — resend doesn't reset |
| Email verification stores raw token instead of hash | Mirror of reset-token issue | SHA-256 hash for verification tokens too |
| Permitting `From: alice@gym.ru` (same as a real client's email) | Phishing via spoofed sender | `From:` must always be on verified domain; display name can vary but local-part is fixed |

---

## "Looks Done But Isn't" Checklist

- [ ] **Password reset:** Often missing → returns same response regardless of email-existence (anti-enumeration) — verify with `test_password_reset_no_oracle.py` triggering all 4 cases (existing-active, existing-deactivated, owner-account, non-existent) and asserting identical 202 + body + bounded timing.
- [ ] **Password reset:** Often missing → token consumption is single-SQL atomic with `RETURNING` (not check-then-update) — grep the service for `WHERE ... AND consumed_at IS NULL RETURNING`.
- [ ] **Invitation:** Often missing → soft-deleted user with same email cannot be reactivated by re-invitation — verify with an integration test that soft-deletes Alice, invites Alice's-email-again, asserts new `users.id` (not the old one).
- [ ] **Email send:** Often missing → bounce webhook actually updates `email_deliverable=False` — verify with a webhook fixture POST and a follow-up send-attempt that returns SKIPPED.
- [ ] **Email send:** Often missing → RFC 2047 encoding of Cyrillic subject — verify by capturing the raw outgoing SMTP via provider's "sandbox" mode or by snapshotting the assembled `MIMEMessage` and asserting subject starts with `=?UTF-8?`.
- [ ] **OTP via email:** Often missing → TTL extended vs Telegram (10min vs 5min) — verify settings.
- [ ] **OTP via email:** Often missing → `otp_codes` table has `channel` column and UNIQUE includes `channel` — verify Alembic migration.
- [ ] **Audit traceability:** Often missing → `actor_email_snapshot` denormalised at audit-write time — verify in `audit_payloads.py` registry that the snapshot field is required.
- [ ] **Multi-user deactivation:** Often missing → revokes all refresh-token families synchronously — verify with an integration test that logs in user, deactivates, and asserts both `/refresh` and access-token use return 401.
- [ ] **Email cron:** Often missing → outbox + dispatcher pattern, not direct send from cron — verify by grepping `app/workers/tasks/` for `mailer.send(` outside the dispatcher file.
- [ ] **Email cron:** Often missing → eager-import of new ORM models in `app/workers/__init__.py` — verify with `tests/test_workers_eager_import.py`.
- [ ] **Idempotency:** Often missing → `(subject_id, kind, channel)` composite — verify Alembic migration `0024_notification_channel_discriminator`.
- [ ] **Provider config:** Often missing → boot-time assertion that `from_domain` is verified — verify with a settings validator that fails on empty `from_domain` in non-sandbox mode.
- [ ] **DNS / DMARC:** Often missing → DMARC alignment between `From:` domain and SPF/DKIM signing domain — verify by sending one probe email and reading the receiving server's Authentication-Results header.
- [ ] **Locked copy:** Often missing → owner sign-off enumerates every constant identifier, not "all v1.6 templates" — verify in plan SUMMARY.md.
- [ ] **Refresh path:** Often missing → `users.is_active` join — grep `/auth/refresh` handler for the join or for an explicit `is_active=True` check.
- [ ] **Email rate-limit:** Often missing → per-email rate limit on `/auth/password-reset` — verify with an integration test hitting the endpoint 10× rapid-fire and asserting 429 after N.
- [ ] **Webhook:** Often missing → signature verification BEFORE body parsing — read the route handler and check that signature check is the first await.
- [ ] **From: header:** Often missing → display name encoded once, not twice — capture wire form and grep for `=?UTF-8?B?=?UTF-8?` double-encoding.
- [ ] **AST gate:** Often missing → `LOCKED_EMAIL_TEMPLATES` frozenset + `email_mailer.send(...)` literal-string gate — verify by adding a synthetic violation fixture (mirrors the v1.2 `audit.emit` AST gate pattern).

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Email channel leaks oracle on reset (Pitfall 1) | MEDIUM | Lock all reset/invite endpoints behind a feature flag; ship corrected anti-oracle response; audit-log all reset attempts in the leak window; owner DM to affected clients only if probe-pattern detected. |
| Cross-channel double-ping (Pitfall 2) | LOW (early) → HIGH (after many sends) | Add `channel` column via online ALTER (Postgres 16 supports it); backfill existing rows with `channel='telegram'`; lock the migration with a partial UNIQUE recreation. Acceptable downtime: cron window (06:14–06:16 MSK). |
| Worker wedge from provider 5xx (Pitfall 3) | LOW | Manual SIGINT the arq-worker container; restart with circuit-breaker key pre-set; provider 5xx still ongoing → cron skips the window; next 06:15 tick recovers. |
| Account hijack via email re-claim (Pitfall 4 case 2) | HIGH | Audit-log scan for `user_invitation_accepted` rows where the resulting `user_id` had prior audit rows under a different name; revoke all such users' tokens; force re-invite with new email aliases. |
| Audit traceability lost (Pitfall 5) | HIGH (irreversible for past rows) | Cannot retroactively recover `actor_user_id`; going forward, add `actor_email_snapshot` and accept the gap on legacy rows. Document the cutover date in PROJECT.md. |
| Locked-copy compromise (Pitfall 6) | LOW | Revert PR; owner re-signs new copy under a new D-XX-OWNER-COPY-LOCK row; redeploy. |
| Eager-import regression (Pitfall 7) | LOW | Add the missing import; redeploy worker; verify with one-shot script. |
| Provider sandbox in prod (Pitfall 8) | MEDIUM | Restart with corrected settings; messages already sent are lost (sandbox doesn't deliver); inform affected users to expect a re-trigger (e.g. re-request expiring-soon notification — though the next 06:15 tick auto-handles it). |
| Bounce webhook unverified (security mistake) | MEDIUM | Add signature verification, deploy, scan audit_log for `email_send_skipped_bounced` rows in the unverified window, manually verify each via provider's UI to confirm not attacker-forged. |
| Reset-token leak via URL (security mistake) | HIGH | Invalidate all outstanding reset tokens (UPDATE all WHERE consumed_at IS NULL SET consumed_at=now()); deploy fragment-based URL; force-resend invitations for any in-flight onboarding. |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1. Email breaks anti-oracle invariant | Phase 41 (spec) | `test_password_reset_no_oracle.py` + `LOCKED_EMAIL_TEMPLATES` AST gate + synthetic-violation fixture |
| 2. Cross-channel double-ping (idempotency taxonomy) | Phase 41 (schema migration `0024_notification_channel_discriminator`) | Integration test sends same-event Telegram + email, asserts only one channel actually fires per client preference |
| 3. Provider 5xx wedges worker | Phase 43 (cron integration) | `WorkerSettings` boot assertion `max_tries<=2, timeout<=30`; chaos test with provider stub returning 5xx for 5 minutes asserts cron next-tick recovery |
| 4. Token replay / email hijack | Phase 41 (foundations: SVC001 scope + partial-UNIQUE migration) + Phase 42 (impl: reset/invite endpoints) | Three integration tests: token-replay → 409, soft-deleted email re-invitation → new user_id, soft-deleted refresh-token revocation |
| 5. Audit `actor_user_id` semantics break | Phase 41 (schema migration `0023_audit_actor_snapshot`) + Phase 42 (deactivation flow) | Test deactivates user, asserts (a) `actor_email_snapshot` populated on past rows after backfill, (b) `/refresh` returns 401, (c) `/me` returns 401 within session lifetime |
| 6. Locked-copy lock breaks under email surface | Phase 41 (gate) + Phase 43 (templates with per-template sign-off) | RFC 2047 round-trip test, NBSP HTML snapshot test, footer existence assertion in every template render |
| 7. ARQ cron eager-import regression | Phase 41 (test discipline) + Phase 43 (cron impl) + Phase 45-ish (verification) | `tests/test_workers_eager_import.py` + Phase-N verification scenario "run cron one-shot, assert non-zero on first call" |
| 8. Provider secret/domain rotting | Phase 41 (settings + boot probe) | Settings validator + boot-time `/domains` probe in non-sandbox mode |
| 9. Bounce / complaint webhook silent decay | Phase 43 (webhook handlers + status column) | Webhook fixture POST → status flips → next send returns SKIPPED |
| 10. Email-OTP TTL/attempt collision | Phase 42 (OTP table migration) | TTL = 10min asserted in test; cross-channel reuse blocked at UNIQUE constraint |
| 11. Invitation TTL onboarding friction | Phase 42 (invitation impl) | Operator runbook scenario: invite, wait 3 days (mock clock), accept successfully |
| 12. Provider 429 burst | Phase 43 (outbox dispatcher) | Load test fires 50 sends, asserts dispatcher caps at ≤5 concurrent |
| 13. `LOCKED_AUDIT_EVENTS` overflow | Phase 41 (pre-register) | Frozenset extended in foundations plan; AST gate stays green across Phases 42/43 |
| 14. 7th docker-compose service drift | Phase 43 (deployment shape decision) | Architecture decision record: webhook receiver lives in `web`, dispatcher in `arq-worker`; explicit reject of 7th service |
| 15. DMARC alignment for subdomain | Phase 41 (DNS spec) | DNS records committed to `infra/dns/sportzal.ru.zone`; probe-send verifies alignment in operator runbook |
| 16. mail.ru vs yandex.ru deliverability asymmetry | Phase 41 (provider selection) + Phase 45 (verification) | Probe-send to one yandex.ru and one mail.ru recipient during milestone verification; check Authentication-Results headers on both |

---

## Sources

### System-grounded (HIGH confidence)
- `.planning/PROJECT.md` — D-20-9 anti-oracle, D-27-OWNER-COPY-LOCK, `LOCKED_AUDIT_EVENTS` frozenset, idempotency table patterns (`membership_notifications`, `booking_notifications`), refresh-rotation family race tolerance, cross-module Protocol slots, SVC001 AST commit gate
- `.planning/RETROSPECTIVE.md` — v1.1 Phase 12.1 commit-gate bug (key lesson #3), v1.2 locked Russian copy lesson (#2), v1.3 `LOCKED_AUDIT_EVENTS` pre-registration (#1), v1.3 milestone-verification-as-phase (#1)
- `.planning/MILESTONES.md` — REG-29-01 dev-proxy, REG-29-03 worker resolver registration, REG-29-04 cron eager-import; REG-36-01..05 verification-time regression class; v1.5 Phase 40 verification 4-hotfix pattern (DEFER-40-01)
- `apps/backend/app/modules/auth/models.py:32-60` — `users` table shape (no soft-delete partial-UNIQUE on email; `telegram_chat_id BIGINT NULL UNIQUE`)
- `apps/backend/app/modules/bookings/notifications.py:35` — `_BOT_BOOK_DENIED_DM` constant pattern (locked Russian copy + anti-oracle in one `Final[str]`)

### Russian-locale / deliverability (MEDIUM confidence)
- [mail.ru SPF & DKIM Setup — mxtoolbox](https://mxtoolbox.com/c/outboundemailsources?public=Mail.ru) — confirms mail.ru's weak outbound authentication posture relative to yandex
- [Yandex SPF & DKIM Setup — mxtoolbox](https://mxtoolbox.com/c/outboundemailsources?public=Yandex-Mail) — confirms yandex's stricter alignment requirements
- [Understanding Yandex Mail DMARC Reports — Skysnag](https://www.skysnag.com/blog/dmarc-report-received-from-yandex-mail-what-you-need-to-know/) — yandex postmaster tooling
- [RFC 2047 — IETF](https://datatracker.ietf.org/doc/html/rfc2047) — encoded-word format for Cyrillic in `Subject` + `From` display names; 75-char limit per encoded-word; `=?UTF-8?B?...?=` syntax
- [Yandex SPF and DKIM set up — OnDMARC](https://knowledge.ondmarc.redsift.com/en/articles/1962212-yandex-spf-and-dkim-set-up) — alignment requirements

### Pattern references (training-data, MEDIUM confidence — verify with Context7 / provider docs at Phase 41 spec time)
- Resend Python SDK module-level `resend.api_key = ...` pattern (verify against current docs)
- AWS SES boto3 retry defaults (verify against current SDK docs)
- Mailgun HMAC-SHA256 webhook signature format
- Postgres 16 partial UNIQUE + `WHERE` clause syntax (well-established)
- `asyncio.Semaphore` rate-limit pattern (stdlib)

---

*Pitfalls research for: v1.6 Email channel + Multi-user admin*
*Researched: 2026-05-18*
*Grounded in Sportzal-specific patterns from v1.0–v1.5; provider-specific items flagged for Phase 41 spec-time validation against current provider docs (Context7).*
