# Project Research Summary — v1.6 Email Channel + Multi-User Admin

**Project:** Sportzal
**Domain:** Single-gym operator CRM (РФ/СНГ); subsequent milestone bolted on top of a shipped Telegram-first system (v1.0–v1.5)
**Researched:** 2026-05-18
**Confidence:** HIGH on architecture + features (entirely grounded in v1.0–v1.5 patterns); MEDIUM on provider/sanctions snapshot (re-verify in Phase 41)

> Scope reminder. v1.6 is a **subsequent** milestone, not greenfield. Existing Telegram flows, auth, payments, audit log (56 LOCKED events, 26-entry `OWNER_ONLY`), idempotency tables, and refresh-rotation families are out of research scope. This SUMMARY focuses strictly on the two new pillars: **(1) email as a parallel notification channel** and **(2) owner-managed multi-user admin**.

---

## Executive Summary

v1.6 closes the last infra-pillar before v1.7 online payments by adding an email channel parallel to the existing Telegram channel (OTP fallback, expiring-soon mirror, payment receipt, booking confirm/remind, password-reset link, user invitation) and by replacing ad-hoc DB-poked operator accounts with an owner-managed multi-user admin surface (invite-token onboarding, soft-delete deactivation, password reset, multi-user audit traceability). The hardest mistakes will be the ones that quietly weaken an invariant the codebase already enforces — anti-oracle DM equality, AST `audit.emit` gate, partial-UNIQUE idempotency, locked-copy owner sign-off, refresh-family race tolerance — not anything provider-specific.

The recommended approach mirrors v1.3 (expiring-soon DM) and v1.5 (booking notifications) shape: a thin `app/integrations/email/` transport layer (parallel to `integrations/telegram/`), per-domain locked Russian templates (`app/modules/<domain>/email_templates.py`, per the D-39-02 precedent), fire-and-forget ARQ dispatch (no 6th docker-compose service), `channel`-discriminator extension of the existing idempotency tables (`membership_notifications`, `booking_notifications`), and a new `app/modules/users/` module (not an extension of `auth`). Phase 41 must be an INFRA-bedrock phase (per the v1.3 INFRA-15 lesson): `LOCKED_AUDIT_EVENTS` extended up-front 56 → ~67; `Resource.USERS` + `OWNER_ONLY` extended; `LOCKED_EMAIL_TEMPLATES` AST gate introduced mirroring `LOCKED_AUDIT_EVENTS`; soft-delete partial-UNIQUE on `users.email`; audit `actor_email_snapshot` denormalisation.

Key risks cluster around three axes: (a) **anti-oracle preservation** — `POST /auth/password-reset/request` must return identical 202 + identical body + bounded-equal timing for known/unknown/deactivated/owner email (mirrors v1.2 D-20-9 `/checkin` and v1.3 expiring-soon anti-oracles); (b) **cross-channel idempotency taxonomy** — extending existing `*_notifications` tables with `channel` column (Alembic `0024_notification_channel_discriminator`) rather than inventing a new `email_notifications` table; (c) **multi-user audit traceability** — explicit FK choice (`audit_log.actor_user_id ON DELETE SET NULL` + denormalised `actor_email_snapshot`) so soft-deleting a fired receptionist preserves history while allowing email re-claim via partial-UNIQUE `(lower(email)) WHERE deleted_at IS NULL`. Mitigations are codified up-front in Phase 41 INFRA before any feature code lands.

---

## Key Findings

### Recommended Stack

A primary-and-fallback РФ-accessibility play: **Yandex Cloud Postbox** (SES-V2-API-compatible, ₽-billed, in-РФ datacentres → native deliverability to mail.ru/yandex.ru/rambler.ru, 2,000 free emails/month covers >3× expected v1.6 volume) accessed via the standard **aioboto3** async SDK. **Unisender Go** (РФ-domestic SDK `unisender-go-api`) is the documented fallback for the case Yandex Cloud credentials are unavailable. Stripe-billed providers (Resend, Mailgun) and SendPulse (RU-restricted) are disqualified by the existing project Out-of-Scope constraint and by Russian-recipient deliverability evidence. Template render via **Jinja2 SandboxedEnvironment** (industry standard, already transitive via FastAPI); reset/invite tokens via **itsdangerous URLSafeTimedSerializer** (stateless HMAC-SHA256, `salt=` per kind). See STACK.md for the full provider scorecard + version pins.

**Core technologies:**
- **Yandex Cloud Postbox** (primary) / **Unisender Go** (fallback): outbound transactional email — РФ-domiciled, ₽-billed, no sanctions exposure, in-region deliverability
- **aioboto3 `>=13.0,<14`**: async SES-V2 client against Postbox endpoint — SDK portability if project ever migrates outside РФ
- **Jinja2 `>=3.1.4,<4` (SandboxedEnvironment)**: render locked Russian templates (HTML + plain-text alt-parts) — industry-standard, sandboxed even for first-party templates per locked-copy discipline
- **itsdangerous `>=2.2.0,<3` (URLSafeTimedSerializer)**: sign reset + invitation tokens — stateless, no DB cleanup cron, `salt=` per kind isolates blast radius
- **moto[ses] (dev)**: SES mock for offline tests; **mailpit** (dev) as local SMTP catcher under `docker-compose.dev.yml` overlay only

### Expected Features

Single-gym CRM expectations are well-anchored — v1.6 is mirror work, not greenfield discovery. Eight P1 features form the launch set, all rated **M (2–4 day)** complexity since each adds a table + endpoint pair + locked Russian template + audit events but reuses existing machinery (ARQ cron loops, refresh-token-family revoke, audit emit, idempotency table pattern).

**Must have (table stakes) — P1 for v1.6 launch:**
- Email integration scaffold + DKIM/SPF/DMARC owner runbook — gate for everything else
- Email OTP fallback for login (TTL 10min vs Telegram 5min to absorb provider lag)
- Email expiring-soon (7+3+1) mirror — revenue retention from non-Telegram clients
- Email payment-receipt (cash sale + refund) — operator habit; hooks into v1.4 commit paths
- Email booking confirm + 24h reminder — parity with v1.5 Telegram flow
- Multi-user admin invite-token flow (NEVER admin-set plaintext password — cardinal sin)
- Password reset with **anti-oracle invariant** (same 202 for known/unknown/deactivated/owner; constant-time floor; `password_reset_requested` audit in BOTH branches)
- Deactivate user + **atomic logout-all** (revoke all refresh-token families in same UoW; `/refresh` joins `users.is_active`)
- Multi-user audit traceability (`actor_user_id ON DELETE SET NULL` + denormalised `actor_email_snapshot`)
- OpenAPI drift gate refresh (forward-guards 61 → ~73)

**Should have (P2, time-permitting):**
- Dual-channel resolution (`clients.preferred_channel ∈ {auto, telegram, email, both}`) — admin-web edit only, no client-facing UI
- Invite-link copy-paste fallback (URL returned in creation response so owner can paste into Telegram/WhatsApp if email bounces)
- DMARC `rua` weekly reports to owner

**Defer (v1.7+ / v2.0+):**
- Owner weekly digest (bounces, deactivations, failed sends) — needs ≥1 month of `email_send_log` data
- Marketing campaigns / mailing lists / preference centre — different product surface
- Custom RBAC roles beyond owner/reception — enterprise scope creep
- TOTP / WebAuthn — Telegram OTP + email OTP already provide step-up
- Per-client email preference (client-facing) — ~100 clients/gym, admin-web edit suffices

**Explicit anti-features (11 documented):** preference centre, marketing campaigns, MFA, custom RBAC, in-app inbox, plaintext password email, dual-email-per-user, app-layer bounce retry, multi-channel OTP race, self-service signup, client-facing preference page. See FEATURES.md for rationale per item.

### Architecture Approach

Modular monolith extension grounded in existing v1.0–v1.5 patterns. Email transport mirrors Telegram exactly: `app/integrations/email/` is channel-agnostic transport that knows nothing about Russian copy or business events; locked templates live next to their owning module (per the D-39-02 v1.5 precedent — booking DMs in `app/modules/bookings/notifications.py`, NOT in `integrations/telegram/copy.py`). Email send is **always async via ARQ**, never inline in the request handler — same discipline as v1.1 D-06 Telegram bot sends. **No 6th docker-compose service**: a new `dispatch_email` ARQ task lives inside the existing `arq-worker` container (5th service, unchanged).

**Major components (additions in v1.6):**
1. **`app/integrations/email/`** (transport) — `client.py` (provider adapter, replaces v1.0 placeholder), `factory.py` (`build_email_client`), `EmailProvider` Protocol. Forbidden from importing `app.modules.*` per existing contract 3.
2. **`app/modules/users/`** (NEW module, NOT an `auth` extension) — owner-managed CRUD + invitation + soft-delete + deactivation; joins `modules-independent` contract list (mechanical addition); cross-module wiring via Protocol slots only. Auth's responsibility stays "credential verification + session lifecycle"; users gets "operator roster + invitation + role assignment."
3. **`app/modules/auth/`** (EXTEND, not split) — new `password_reset_service.py` + `password_reset_email_templates.py`; adds `invalidate_all_families_for_user` exposed via `UserSessionInvalidator` Protocol slot (so `users.service` never imports `auth`).
4. **Per-domain `email_templates.py`** in `memberships/`, `bookings/`, `payments/`, `users/`, `auth/` — locked Russian copy with owner sign-off per template (mirrors D-27-OWNER-COPY-LOCK).
5. **`app/workers/tasks/dispatch_email.py`** (NEW ARQ task) — receives pre-rendered `EmailEnvelope` (substitution happens at calling service); workers transport bytes, modules render templates.
6. **`app/modules/notifications/`** stays a placeholder — per-domain template ownership wins; resurrecting a "real" notifications module would create cross-module fan-in and tempt ad-hoc magic-string event names breaking the AST gate.

**New Protocol slots (composition-root registrations, double-wired per REG-29-03):**
- `EmailDispatcher` — enqueue email-send via ARQ; register in BOTH `app/main.py:create_app()` AND `app/workers/__init__.py:WorkerSettings.on_startup`
- `UserSessionInvalidator` — `users.service.deactivate_user` reaches into `auth.service` via this slot to revoke all refresh-token families

### Critical Pitfalls

System-specific (not generic "use SPF" advice); all framed against invariants the codebase already enforces:

1. **Email breaks anti-oracle invariant Telegram pays for** — natural reflex to use different templates per failure reason on email (because email "feels private") restores the oracle Telegram's locked DM equality refused. Prevention: `POST /auth/password-reset/request` always returns 202 + identical body + bounded-equal timing for all 4 cases (existing-active / existing-deactivated / owner-account / non-existent); `password_reset_requested` audit emitted in BOTH branches; integration test `test_password_reset_no_oracle.py` lands in Phase 41 BEFORE first reset-flow endpoint.

2. **Cross-channel double-pings** — `membership_notifications` UNIQUE `(membership_id, kind)` was implicitly Telegram-only. Without explicit `channel` discriminator: same `kind='expiring_7d'` from Telegram + email cron causes UNIQUE violation OR a client receives both DM + email. Prevention: Alembic `0024_notification_channel_discriminator` adds `channel TEXT NOT NULL DEFAULT 'telegram' CHECK channel IN ('telegram','email')`; UNIQUE becomes `(subject_id, kind, channel)`; backfill is zero-row (reproducible by next cron tick).

3. **Token replay / account hijack via email re-claim** — three failure modes: (a) reset-token replay race via post-commit consume marking (v1.1 Phase 12.1 SVC001 lesson — extend AST walker scope to `app/modules/auth/*.py`); (b) soft-deleted user `alice@gym.ru` re-invited reactivates the OLD row inheriting Alice's audit `actor_user_id` (cardinal sin — invite-accept MUST INSERT new row, never UPDATE existing); (c) token in URL path leaks via Referer/proxy/shoulder-surf. Prevention: soft-delete partial-UNIQUE `(lower(email)) WHERE deleted_at IS NULL` on `users` (mirrors `clients.phone` pattern); token in URL fragment `#token=...` or POST body; single-SQL atomic consume `UPDATE ... WHERE consumed_at IS NULL RETURNING`.

4. **`actor_user_id` historical interpretation breaks under multi-user** — three sub-issues: (a) audit `actor_user_id` FK behaviour was never explicitly chosen (`RESTRICT` blocks soft-delete, `SET NULL` loses traceability); (b) `/refresh` hot path does NOT check `users.is_active` (deactivated operator gets fresh access token until cookie expires); (c) idempotency-via-actor would leak across operators. Prevention: explicit `ON DELETE SET NULL` + denormalised `actor_email_snapshot TEXT` on audit rows (migration `0023_audit_actor_snapshot` in Phase 41); `users.is_active` join on `/refresh`; deactivation revokes all families in same UoW.

5. **Locked Russian copy lock breaks under email's richer surface** — email has subject + plain-body + HTML-body + footer + From: display-name; each is a locked-copy compromise point. Cyrillic subjects need RFC 2047 encoded-word; NBSP in money renders as `?` on Outlook for Windows; provider SDKs inconsistently double-encode UTF-8 display names. Prevention: `LOCKED_EMAIL_TEMPLATES` AST gate mirroring `LOCKED_AUDIT_EVENTS` (frozenset of `(subject_const, body_const, html_const)` triples; `email_mailer.send(...)` takes enum, not raw strings); RFC 2047 round-trip test on assembled wire form; per-template owner sign-off enumerated by constant identifier (not "all v1.6 templates").

6. **Provider 5xx + ARQ retry storm collides with 06:xx cron window** — single failing provider's compounded SDK + ARQ retries wedge the worker container, blocking the 06:15 → 06:25 → 06:35 cron chain. Prevention: provider SDK retries set to 0/1; ARQ `max_tries=2, timeout=20`; outbox+drainer pattern moves email out of cron path; per-provider Redis circuit breaker (TTL 5m, opened on 5xx).

7. **ARQ cron eager-import regression class repeats (REG-29-04 mirror)** — new ORM tables (`email_outbox`, `password_reset_tokens`, `email_send_log`) added in modules the worker doesn't transitively import → cron returns `count=0` on first call. Prevention: explicit `from app.modules.<x> import models  # noqa: F401` in `app/workers/__init__.py` per new module; boot-time invariant logs `Base.metadata.tables.keys()` and asserts all cron-queried tables present; `tests/test_oneshot_scripts_eager_import.py` AST introspection.

8. **Provider secret + domain + sandbox mode rotting at env boundary** — Resend `re_sandbox_*` silently allows sends only to verified addresses (works in dev, fails in prod); `EMAIL_FROM_DOMAIN` empty → production sends from `sandbox.resend.dev` → mail.ru DMARC reject. Prevention: Pydantic `EmailProviderSettings` validator fails at boot if `from_domain` empty in non-sandbox mode; boot-time probe to `/domains` endpoint asserts verified; webhook signing secret mandatory; HMAC verify before body parse.

See PITFALLS.md for the full 16-pitfall taxonomy + per-pitfall recovery-cost table + "looks done but isn't" 20-item checklist.

---

## Open Conflicts (for Spec Phase to Resolve)

The synthesizer surfaces these explicitly rather than pre-emptively choosing — the spec phase will decide. **All preserve the anti-oracle and audit-AST-gate invariants regardless of which path is chosen.**

1. **Email provider choice** — STACK.md recommends **Yandex Cloud Postbox (primary) + Unisender Go (fallback)** based on РФ-accessibility + ₽-billing + in-region deliverability + SES-V2-API portability. Other research files are provider-agnostic. *Conflict severity: low — STACK.md is the owning surface for this decision.*

2. **Reset-token storage** — STACK.md recommends `itsdangerous` stateless signed tokens (HMAC over `(user_id, password_changed_at, kind)` — single-use via `password_changed_at` equality check; no DB row, no cleanup cron). ARCHITECTURE.md recommends DB table `password_reset_tokens` (hash-at-rest, server-side single-use via partial-UNIQUE `(user_id, purpose) WHERE consumed_at IS NULL`; mirrors `refresh_tokens` discipline byte-for-byte; auditable forever via `audit_correlation_id`). PITFALLS.md is path-agnostic but leans toward the DB-table approach for the SVC001 commit-gate + atomic-consume `RETURNING` SQL invariant. *Both preserve anti-oracle. Spec phase decides on the trade-off: itsdangerous is simpler infra; DB-table matches existing v1.1 `refresh_tokens` discipline and gives immutable audit-trail.*

3. **`notifications` module status** — FEATURES.md hints at extending a "real" `app/modules/notifications/`. ARCHITECTURE.md explicitly rejects this (D-39-02 precedent — v1.5 chose per-domain template ownership over a shared `integrations/telegram/copy.py`; same logic applies to email). *Synthesizer leans toward ARCHITECTURE.md's read here because D-39-02 is a load-bearing precedent that the AST-gate-on-locked-events depends on — but spec phase confirms.*

4. **Template engine** — STACK.md recommends **Jinja2 SandboxedEnvironment** (industry standard, transitive via FastAPI, sandbox for defence-in-depth even on first-party templates). ARCHITECTURE.md leans toward **f-string-locked `Final[str]` templates** per D-39-04 anti-magic (matches existing v1.5 Telegram DM constants). PITFALLS.md is engine-agnostic but enumerates the locked-template-AST-gate requirement regardless of engine. *Trade-off: Jinja2 cleaner for HTML/text dual-part interpolation; f-strings cleaner for AST-grep-ability of locked copy.*

5. **`User` ORM ownership** — ARCHITECTURE.md offers two paths: **Path A** hoist `User` from `auth/models.py` to `app/core/models.py` (cleaner; touches all 729 tests' imports; no direct ORM-hoist precedent — closest is v1.2 Phase 15 hoist of the `escape_like_pattern` function); **Path B** leave `User` in `auth/models.py`; new `users` module accesses via `UserLookup` Protocol slot (lower-risk; mirrors existing `register_user_loader` pattern; one extra slot for trivial reads). *Spec phase decides on the risk/cleanliness trade.*

6. **Phase numbering of pitfalls roadmap** — PITFALLS.md uses Phase 41–45 (5 phases); ARCHITECTURE.md uses Phase 41–48 (8 phases). Both start at 41 (continued from v1.5 Phase 40). *Synthesizer deliberately does NOT prescribe phase count — that is the roadmapper's job downstream. The set of v1.6 work items is stable; how they cluster into phases is a roadmap decision.*

7. **Email verification flow for owner-added operator accounts** — trust owner-entered addresses (single zal, owner knows their staff) vs click-to-verify (industry best practice). ARCHITECTURE.md leans toward **trust**; PITFALLS.md is neutral. *Spec phase decides; if "trust" wins, document explicitly as a Decision row.*

---

## Implications for Roadmap

The synthesizer does NOT prescribe phase count — that is the roadmapper's job downstream. Below is the **stable set of v1.6 work items** discovered across all four research files, ordered by dependency.

### Critical invariants to preserve in EVERY phase

- **Anti-oracle**: `POST /auth/password-reset/request` always returns 202 + identical body + bounded-equal timing for `(existing-active, existing-deactivated, owner-account, non-existent)`; `password_reset_requested` audit emitted in BOTH branches; `test_password_reset_no_oracle.py` enforces.
- **`LOCKED_AUDIT_EVENTS` extension up-front in the first phase** (v1.3 INFRA-15 lesson) — adding ~11 new event pairs after callsites land triggers AST-gate churn.
- **`LOCKED_EMAIL_TEMPLATES` frozenset + AST gate** mirroring `LOCKED_AUDIT_EVENTS` shape; `email_mailer.send(...)` takes enum, not raw strings; synthetic-violation fixture lands first.
- **Owner sign-off on every locked Russian email template** (D-27-OWNER-COPY-LOCK precedent) — sign-off row enumerates every constant identifier by name.
- **Double-wire Protocol slots** in BOTH `app/main.py:create_app()` AND `WorkerSettings.on_startup` (REG-29-03 lesson).
- **Cross-channel idempotency taxonomy**: `channel TEXT NOT NULL` column on `membership_notifications` + `booking_notifications` via Alembic `0024_notification_channel_discriminator`.
- **Soft-delete partial-UNIQUE on `users.email`** (`WHERE deleted_at IS NULL`) — mirrors `clients.phone`; invite-accept MUST INSERT new row, never UPDATE existing.
- **Audit `actor_user_id ON DELETE SET NULL` + denormalised `actor_email_snapshot`** (migration `0023_audit_actor_snapshot`).
- **`/refresh` joins `users.is_active`** — deactivated operator immediately loses session.
- **SVC001 AST commit-gate scope extension** — extends to `app/modules/users/service.py` + `app/modules/auth/password_reset_service.py` (Phase 12.1 lesson — NOT just `service.py`).

### Work items by dependency order

**A. INFRA bedrock (MUST be first):**
- Resolve open conflicts (provider, token storage, template engine, `User` ORM ownership, email-verification policy)
- Extend `LOCKED_AUDIT_EVENTS` 56 → ~67; register Pydantic models in `audit_payloads.py`
- Introduce `LOCKED_EMAIL_TEMPLATES` AST gate + synthetic-violation fixture
- Extend `Resource` enum with `USERS`; `OWNER_ONLY` 26 → 29 (CREATE/UPDATE/DELETE/LIST USERS); three-way parity test update
- Declare `EmailDispatcher` + `UserSessionInvalidator` Protocol slots in `app/core/dependencies.py`
- Add `app.modules.users` to `.importlinter` `modules-independent` list
- Extend SVC001 AST commit-gate scope
- Alembic `0023_audit_actor_snapshot` (`actor_email_snapshot TEXT` + FK `ON DELETE SET NULL`)
- Alembic `0024_notification_channel_discriminator` (`channel` column + UNIQUE recreation)
- Alembic migration: `users.deleted_at` + partial-UNIQUE `(lower(email)) WHERE deleted_at IS NULL`
- Alembic `0025_password_reset_tokens` (conditional on conflict #2) OR itsdangerous secret hook
- DNS/SPF/DKIM/DMARC owner runbook draft (dedicated subdomain `mail.sportzal.ru`)
- Pydantic `EmailProviderSettings` with `sandbox_mode: bool`, boot-time `/domains` probe
- Eager-import test discipline (`tests/test_workers_eager_import.py`)

**B. Email transport layer (depends on A):**
- Replace `app/integrations/email/client.py` placeholder with chosen-provider adapter
- `app/integrations/email/factory.py:build_email_client(...)` (mirror `telegram/bot.py:build_bot`)
- `app/workers/tasks/dispatch_email.py` ARQ task (consumes pre-rendered `EmailEnvelope`; forbidden from `app.modules.*` import)
- `EmailDispatcher` slot double-wired
- First `email_sent` / `email_send_failed_*` audit callsites
- Outbox+drainer pattern + per-provider Redis circuit breaker + `asyncio.Semaphore(5)` rate-limit
- Bounce/complaint webhook handler with HMAC signature verification (timing-safe `hmac.compare_digest`)

**C. Multi-user admin (depends on A; independent of B):**
- New `app/modules/users/` (router, service, repository, schemas, permissions, constants, `email_templates.py`)
- `users.service`: `create_user`, `deactivate_user`, `soft_delete_user`, `list_users`, `send_invitation_email`
- `auth.service.invalidate_all_families_for_user` exposed via `UserSessionInvalidator` slot
- `/auth/refresh` `users.is_active` join
- Multi-user audit verification + `actor_display_name` in receipt-render path

**D. Invitation + password-reset flow (depends on B + C):**
- `app/modules/auth/password_reset_service.py` (anti-oracle `request` + atomic-consume `confirm` with `RETURNING` SQL)
- `app/modules/users/invitation_service.py` (MUST INSERT new user row, never UPDATE existing)
- Locked Russian email copy with owner sign-off: `USER_INVITATION_EMAIL_*` + `PASSWORD_RESET_EMAIL_*`
- Token TTL: invitation 7 days; reset 1h (OWASP 2025 floor)
- Token in URL fragment `#token=...` or POST body — NEVER URL path
- Rate-limit `/auth/password-reset/request` 5/15min per IP + 1/min, 5/hour per email; same generic 202

**E. Email fallback for expiring/booking notifications (depends on B):**
- Extend `send_expiring_notifications` (06:15 MSK) — email fallback if `client.email IS NOT NULL`
- Extend `send_booking_reminders` (06:35 MSK) — same dual-channel pattern
- 6 expiring templates `EMAIL_EXPIRING_{7D,3D,1D}_VARIANT_{A,B}` (anti-oracle A/B via `client_id.bytes[0] & 1`) + 4 booking templates
- Owner sign-off per template constant

**F. Email OTP fallback for login (depends on B; can parallel E):**
- Extend `otp_codes` with `channel TEXT NOT NULL DEFAULT 'telegram'` + UNIQUE `(user_id, channel) WHERE consumed_at IS NULL`
- Email OTP TTL **10 minutes** (Telegram × 2 for provider lag); resend 60s cooldown; second OTP invalidates first
- Locked Russian template `EMAIL_OTP_LOGIN`

**G. Email payment-receipt (depends on B; can parallel E + F):**
- Hook into v1.4 `record_payment` + `issue_refund` commit paths
- `payment_receipts` idempotency table UNIQUE `(payment_id, channel)`
- Locked templates `EMAIL_PAYMENT_RECEIPT_SALE` + `EMAIL_PAYMENT_RECEIPT_REFUND` (NBSP as `&nbsp;` in HTML, literal U+00A0 in plain-text)
- `actor_display_name` derived from `users.full_name` in receipt body ("Принял: Анна П.")
- LOCKED audit event `payment_receipt_emailed`

**H. OpenAPI drift gate refresh (serialization point — depends on B–G):**
- Atomic byte-stable regen of `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts`
- `AssertNonNever` forward-guards 61 → ~73
- README v1.6 changelog

**I. Milestone verification phase (gate — depends on all above):**
- Operator scenarios via curl + sandbox email
- Race tests (token replay, soft-delete + re-invite, deactivate + `/refresh` 401)
- Anti-oracle integration test `test_password_reset_no_oracle.py` (4 cases × identical body × bounded timing)
- RFC 2047 round-trip test + NBSP HTML snapshot + footer assertion
- Probe-send to one yandex.ru + one mail.ru recipient; Authentication-Results header inspection
- Eager-import live-Postgres verification (REG-29-04 mirror)
- 6 CI gates green
- Owner sign-off enumerated by constant name

### Research flags

**Phases likely needing deeper `/gsd-research-phase`:**
- **INFRA bedrock (A):** provider runbook re-verification (sanctions/payment landscape moves fast); resolution of open conflicts #2/#4/#5 with explicit Decision rows; DNS/DMARC subdomain layout
- **Invitation + password-reset (D):** locked Russian email copy with owner sign-off mechanism (D-27 lineage); rate-limit calibration; URL-fragment SPA flow design (admin-web frozen — backend-only)
- **Bounce/complaint webhook (within B):** per-provider signature scheme; `email_send_log` schema; reputation decay handling

**Standard patterns (skip research):**
- Multi-user admin module (C) — direct mirror of v1.1 `clients`
- Email fallback for expiring/booking (E) — direct mirror of v1.3 Phase 27 + v1.5 Phase 39
- OpenAPI drift gate refresh (H) — mechanical regen per v1.3 Phase 28 + v1.5 Phase 36
- Verification phase (I) — mirror of v1.3 Phase 29 + v1.5 Phase 40 (apply DEFER-40-01 lessons to runbook scaffolding)

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH on primary recommendation; MEDIUM on fallback rationale | Provider/sanctions snapshot is 2026-05-18 — re-verify in INFRA bedrock. SDK pins + sandbox-mode hazards verified against official docs. |
| Features | HIGH | All 8 P1 features mirror existing v1.0–v1.5 shapes. 11 anti-features explicitly excluded with rationale. |
| Architecture | HIGH | Entirely grounded in v1.0–v1.5 patterns; no speculative external research. D-39-02 + D-06 + D-10 + REG-29-03 are load-bearing precedents. Two open paths flagged MEDIUM. |
| Pitfalls | HIGH on system-specific; MEDIUM on Russian-locale + provider-deliverability | 16-pitfall taxonomy grounded in PROJECT.md + RETROSPECTIVE.md + MILESTONES.md regressions. |

**Overall confidence:** HIGH — every recommendation is anchored either in shipped v1.0–v1.5 invariants or in documented STACK rationale; medium-confidence axes are provider snapshot freshness (re-verify at spec time) and locale-specific deliverability quirks (probe in verification).

### Gaps to Address

- **Open conflicts #1–#7** — spec phase resolves each with explicit Decision row in PROJECT.md
- **DMARC alignment for subdomain** — DNS spec must be finalized at INFRA bedrock; `mail.sportzal.ru` SPF/DKIM/DMARC committed to `infra/dns/sportzal.ru.zone`; `p=none` → `p=quarantine` after monitoring
- **`actor_display_name` formatting** — full name vs first-name-last-initial — default to first-name-last-initial for privacy
- **Bounce/complaint webhook receiver shape** — defer aggressive handling to v1.7 (passive logging in v1.6)
- **Provider sandbox-mode prod-detection** — boot-time probe MUST be in place before first production deploy
- **REG-29-04 mirror** — eager-import test discipline lands in INFRA bedrock; verification phase runs cron one-shot scripts against live Postgres (DEFER-40-01 lesson: budget ≥1 day for runbook scaffolding hardening)

---

## Sources

### Primary (HIGH confidence — system-grounded)
- `.planning/PROJECT.md` — `LOCKED_AUDIT_EVENTS` frozenset, `OWNER_ONLY` RBAC, anti-oracle DM patterns (D-20-9), `D-27-OWNER-COPY-LOCK`, `D-39-02` per-domain template ownership, idempotency table shapes, refresh-rotation family race tolerance, Protocol-slot pattern, SVC001 AST commit gate, mandatory snapshot pricing, REG-29-01/03/04 + REG-36-01..05 + DEFER-40-01 regression classes
- `apps/backend/app/modules/auth/models.py` — `users` table shape (no soft-delete partial-UNIQUE on email; `telegram_chat_id BIGINT NULL UNIQUE`)
- `apps/backend/app/modules/bookings/notifications.py` — `_BOT_BOOK_DENIED_DM` (D-39-02 precedent)

### Primary (HIGH confidence — external)
- Yandex Cloud Postbox service + pricing + quotas + SDK guide (official) — SES-V2 API compatibility, 2000 free emails/month, 152-ФЗ compliance
- Amazon SES Regions (official) — confirms no РФ region
- aioboto3 / Jinja2 SandboxedEnvironment / itsdangerous (PyPI + official docs) — version pins + API surface
- OWASP Forgot Password Cheat Sheet + WSTG — anti-enumeration 202, constant-time, single-use, 1h TTL
- RFC 2047 — encoded-word for Cyrillic Subject + From
- Specops "Scripting new user onboarding" — anchors anti-feature "admin-set initial password mailed in plaintext"
- Postmark "What is transactional email" — transactional/marketing boundary
- moto[ses] docs — SES-V2 mocking

### Secondary (MEDIUM confidence)
- Unisender Go API ref + `unisender-go-api` PyPI — fallback SDK
- Vaadata password-reset vulnerabilities — token-in-URL avoidance
- Mailgun + Brevo SPF/DKIM/DMARC guides — owner runbook shape, dedicated subdomain
- WSO2 invite-user flow + Auth0 B2B onboarding — invite-token industry standard
- mxtoolbox mail.ru/yandex.ru SPF + Skysnag yandex DMARC — РФ-locale deliverability evidence

### Tertiary (LOW confidence — re-verify at spec time)
- Resend Python SDK module-level cache (verify via Context7)
- AWS SES boto3 retry defaults (verify against current SDK)
- Mailgun HMAC-SHA256 field-order (verify via Mailgun official helper)
- Mailgun post-2022 РФ-recipient reputation claim — anecdotal
- SendPulse РФ-restriction claim — single vendor source (Unisender comparison page)

---

*Research completed: 2026-05-18*
*Ready for roadmap: yes (open conflicts surfaced; phase clustering deferred to roadmapper)*
*Detailed dimensional research: `.planning/research/{STACK,FEATURES,ARCHITECTURE,PITFALLS}.md`*
