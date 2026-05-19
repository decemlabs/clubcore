# Phase 43: Multi-User Admin Module — Context

**Gathered:** 2026-05-19
**Status:** Ready for planning
**Mode:** `--auto` (recommended defaults auto-selected from REQUIREMENTS.md / ROADMAP.md / Phase 41 CONTEXT / PITFALLS.md research)

<domain>
## Phase Boundary

Build a new owner-managed `app/modules/users/` module that lets the owner onboard, deactivate, soft-delete, and re-onboard reception operators end-to-end via API — never via direct DB poking — and ensure any operator action carries denormalised audit traceability that survives that operator being fired. Concretely: 7 endpoints (`GET/POST /api/v1/users`, `PATCH /{id}/deactivate`, `PATCH /{id}/reactivate`, `DELETE /{id}`, `POST /invitations/{id}/revoke`) backed by repository + service + schemas + permissions + email_templates files mirroring `clients/`; the Phase-41 `UserSessionInvalidator` Protocol slot is wired to `auth.service.invalidate_all_families_for_user` in `app/main.py:create_app()`; the `/auth/refresh` hot path is joined against `users.is_active AND users.deleted_at IS NULL` (USERS-06 anti-oracle); a single Alembic migration `0030_users_lifecycle_columns` adds `is_active`, `status`, `deactivated_at`, `deactivated_by_user_id` and drops `password_hash NOT NULL`; the `USER_INVITATION_EMAIL` locked template (identifier pre-registered in Phase 41 D-41-12) gets its content + render path landed here; `?include_invite_link=true` query param gives owner a copy-paste fallback for bouncing inboxes.

Requirements in scope: **USERS-01, USERS-02, USERS-03, USERS-04, USERS-05, USERS-06, USERS-07** (7 reqs per `.planning/REQUIREMENTS.md` traceability table).

**Out of scope (forwarded):**
- `password-reset/request` + `password-reset/confirm` endpoints — Phase 44 (RESET-01/02). `password_reset_tokens` table already exists from Phase 41 0025 with `purpose IN ('password_reset','invitation')`; Phase 43 only writes the `invitation` rows.
- `PASSWORD_RESET_EMAIL` template content — Phase 44 (RESET-03 / `app/modules/auth/email_templates.py`).
- Daily ARQ cleanup cron deleting expired `password_reset_tokens` (D-41-06) — Phase 44.
- Invitation-accept endpoint `POST /api/v1/users/invitations/accept` (RESET-04) — Phase 44 (it sets the password and is co-owned by the auth + users modules; lives in users router but its atomic-consume SQL belongs to Phase 44's `password_reset_service.py` scope per D-41-28 SVC001 extension).
- Aggressive email-verify re-flow (re-send verification, owner-triggered re-verify) — v1.7.
- Audit-log read API (filter by actor) — v1.8.

</domain>

<decisions>
## Implementation Decisions

### Email-verify policy for owner-added accounts (open conflict #7 — RESOLVED)

- **D-43-01 (Trust owner-entered email + lazy verify via invitation-accept):** Owner-entered emails are trusted at insert time (`users.email_verified=false` per the column default from migration 0028); the act of accepting the invitation **proves email control** (user clicked the link delivered to that mailbox), so the invitation-accept flow (Phase 44 RESET-04) sets `email_verified=true` in the same UoW as the password set. Phase 43 does NOT ship a separate `POST /api/v1/users/{id}/resend-verification` or a re-verify ladder — operator account turnover is rare enough (1–3 reception swaps/year for a single-gym CRM) that an explicit re-invite (revoke + re-issue) covers the rare typo case. Rejected: separate click-to-verify endpoint before invitation accept (doubles the email round-trip without measurable security gain — invitation-accept is already a one-time link delivered to the same mailbox).
- **D-43-02 (USERS-02 list response does NOT expose `email_verified`):** The flag is operationally interesting only at invitation-accept time and the `/auth/login` path (where `email_verified=false` blocks email-channel OTP per AUTH-EM-02). Exposing it in the operator list would invite confusion ("why does this active user show email_verified=false?" — answer: legacy v1.0 owner who pre-dates the column). Field is intentionally omitted from `UserListItemResponse`.

### `actor_display_name` formatting (USERS-07 deferred from Phase 41 — RESOLVED)

- **D-43-03 (No new `actor_display_name` payload field — `actor_email_snapshot` is sufficient):** The Phase-41-registered Pydantic payloads for the 6 user-lifecycle events (`UserInvitedPayload`, `UserInvitationAcceptedPayload`, `UserInvitationRevokedPayload`, `UserDeactivatedPayload`, `UserReactivatedPayload`, `UserSoftDeletedPayload` — see `apps/backend/app/core/audit_payloads.py:513-598`) do NOT carry an `actor_display_name` field. The original REQUIREMENTS.md USERS-07 wording ("payloads include `actor_display_name`") was superseded by Phase 41 D-41-09: `actor_email_snapshot` is the **column-level snapshot on `audit_log`**, captured at every `audit.emit()` boundary via the request-scoped ContextVar (D-41-08) — NOT a payload field. The v1.8 audit-read API will join `audit_log.actor_user_id` to a current `users.full_name` when the user still exists, and fall back to `actor_email_snapshot` when the user has been hard-deleted. Phase 43 ships zero new payload-field decisions; the 6 payloads from `audit_payloads.py` are consumed verbatim.
- **D-43-04 (No new payload fields in users module beyond pre-registered):** Every `audit.emit(...)` callsite in `app/modules/users/service.py` MUST pass exactly the kwargs of the matching pre-registered payload (extra='forbid' rejects anything else). Concretely: `user_invited` carries `invited_user_id`, `invited_email` (lowercased), `invited_role` (Role.value), `invitation_expires_at` (UTC datetime), `audit_correlation_id`; `user_deactivated` carries `deactivated_user_id`, `sessions_revoked_count` (int returned by the slot), `audit_correlation_id`; rest analogous.

### Schema migration — user lifecycle columns (`0030_users_lifecycle_columns`)

- **D-43-05 (Single migration `0030_users_lifecycle_columns`):** Phase 41 D-41-15 scoped 0022–0025 explicitly to the bedrock bundle (deleted_at, audit snapshot, channel discriminator, password_reset_tokens). The user-lifecycle columns (`is_active`, `deactivated_at`, `deactivated_by_user_id`, `status`) were NOT in that bundle and they have NO downstream consumers before Phase 43 — so they ship in this phase as a single Alembic migration `0030_users_lifecycle_columns`. NOT split per column (mechanical 4-column ALTER inside a single feature delta is the v1.0–v1.5 convention; mirrors 0011_trainers + 0016_trainer_availability_slots shape).
- **D-43-06 (Column shapes — locked):**
  - `is_active BOOLEAN NOT NULL DEFAULT true` — every existing user becomes `true` on upgrade (matches today's implicit "always active" behaviour). Indexed via the `WHERE is_active = true` partial used by deactivation guards (see D-43-13).
  - `status TEXT NOT NULL DEFAULT 'active' CHECK status IN ('active', 'pending_invitation')` — derived field rejected (`password_hash IS NULL` would conflate "invited" with "legacy owner with corrupted hash"). Explicit column is queryable, debuggable, and admits future statuses (`'invited_expired'` if v1.7 surfaces auto-expiry sweeping). Mirrors `bookings.status` discriminator pattern.
  - `deactivated_at TIMESTAMPTZ NULL` — set atomically with `is_active=false`; cleared on reactivate. CHECK constraint `(is_active = true AND deactivated_at IS NULL) OR (is_active = false AND deactivated_at IS NOT NULL)` enforces consistency at DB layer (mirrors v1.2 freeze period CHECK pattern).
  - `deactivated_by_user_id UUID NULL FK users.id ON DELETE SET NULL` — preserves traceability past deactivator soft-delete; SET NULL chosen over RESTRICT (would block deactivator soft-delete) per Pitfall 5 mitigation precedent (audit_log.actor_user_id D-41-08). No ON DELETE CASCADE — the deactivation history outlives the deactivator's user row.
  - **Drop `password_hash NOT NULL`** — invited-but-not-yet-accepted users live in the `users` table with `password_hash IS NULL`. The `/auth/login` password path already lookups `WHERE email = ... AND password_hash IS NOT NULL` (verify by-types vs verify on-the-wire — Phase 12.1 lesson means we MUST add the explicit IS NOT NULL filter or it blows up at Argon2id.verify-time with a sentinel-string row); auth.service updates are scoped tightly to that single SELECT in `_authenticate_password` (Plan 43-XX to be sized by planner).
  - **No new index on `email_verified`** — the existing partial-UNIQUE on `(lower(email)) WHERE deleted_at IS NULL` (Phase 41 0022) is sufficient; verification status is read in single-row paths only.
- **D-43-07 (Single migration ordering):** 0030 has no cross-table dependencies — `deactivated_by_user_id FK users.id` self-references but the FK declares against the same table being altered (PostgreSQL accepts this in one DDL transaction). Round-trip clean (`alembic upgrade head && alembic downgrade -1 && alembic upgrade head`) is a [BLOCKING] checkpoint per the v1.6 Phase 42 16-plan precedent.
- **D-43-08 (Hoisted User ORM extension):** All four new columns land on `apps/backend/app/core/models.py:User` (the hoisted model per Phase 41 D-41-01), NOT on the auth/models.py re-export shim. Mapped types: `is_active: Mapped[bool]`, `status: Mapped[Literal['active','pending_invitation']]` (Python literal type + SAEnum with `native_enum=False, length=32`), `deactivated_at: Mapped[datetime | None]`, `deactivated_by_user_id: Mapped[UUID | None]`. `password_hash: Mapped[str | None]` — the change from `Mapped[str]` to `Mapped[str | None]` is mechanical but must be paired with explicit `IS NOT NULL` guards at every consumer (D-43-06 fourth bullet); test_workers_eager_import asserts the column is still introspectable from the worker root.

### Module structure (USERS-01 — RESOLVED)

- **D-43-09 (Mirror `clients/` module layout):** `app/modules/users/` grows from `__init__.py + service.py` (Phase 41 SVC001 placeholder) to the full 7-file shape `{router.py, service.py, repository.py, schemas.py, permissions.py, constants.py, email_templates.py}`. NO `models.py` — the `User` ORM lives in `app.core.models` (D-41-01); the users module imports it from there. NO `models.py` re-export shim within `users/` — keeps the rule "one User import path per consumer" clean. Repository owns `list_alive`/`get_alive` partition pattern (mirrors `apps/backend/app/modules/clients/repository.py:46-64`). Service owns transaction control (no `commit()` in repository per D-03 lineage). Router owns RBAC + CSRF dependency injection.
- **D-43-10 (`schemas.py` uses `BackendSchemaBase`):** All response models inherit from `app.core.schemas.BackendSchemaBase` (camelCase wire format per the established v1.4 pattern). `UserListItemResponse` fields: `{id, email, fullName, role, isActive, isDeactivated, status, createdAt, deactivatedAt, deactivatedByUserId, invitationExpiresAt}`. `isDeactivated` is a Pydantic computed field (`@computed_field`) derived as `not is_active and deactivated_at is not None` — kept alongside `isActive` per ROADMAP success criterion #5 which lists both explicitly (UI consumers may want the boolean derived for them; backward-compatible if `isActive` semantics ever evolve). `invitationExpiresAt` is None for `status='active'` users; populated from the latest non-consumed `password_reset_tokens` row with `purpose='invitation'` for pending users (LEFT JOIN in `list_alive`). Excluded fields (NEVER in any response): `password_hash`, `password_changed_at`, `telegram_chat_id`, refresh-family rows, `email_verified` (per D-43-02), raw invitation tokens.
- **D-43-11 (`permissions.py` is a thin marker file):** Just re-exports `Resource.USERS` for grep-locality (`from app.modules.users.permissions import USERS_RESOURCE`); no new Action verbs (D-41-22 — reuses CREATE/UPDATE/DELETE/LIST). Router-layer `Depends(require_permission(Action.X, Resource.USERS))` references `app.core.permissions.Resource.USERS` directly (the marker file is for callsite legibility, not as a new enum surface).
- **D-43-12 (`constants.py` holds `INVITATION_TOKEN_TTL`):** Exactly one constant: `INVITATION_TOKEN_TTL: Final[timedelta] = timedelta(days=7)` (D-41-04 + RESET-03 spec). Used at token generation time in `service.create_user` and at SELECT-time predicate (`expires_at > now()`).

### Endpoint surface + behaviour

- **D-43-13 (`POST /api/v1/users` — atomic, idempotent on re-invite of pending/expired users):** Body: `{email, fullName, role: 'owner' | 'reception'}`. Behaviour by current state of `users WHERE lower(email) = lower(:email) AND deleted_at IS NULL`:
  - **No row found:** INSERT new `users` row with `password_hash=NULL`, `status='pending_invitation'`, `is_active=true`, `email_verified=false`; INSERT new `password_reset_tokens` row with `purpose='invitation'`, `expires_at=now()+INVITATION_TOKEN_TTL`, fresh token hash (raw token retained for email payload); emit `user_invited`; enqueue invitation email via `EmailDispatcher` slot (template_id=`USER_INVITATION_EMAIL`); return 201 with `{id, email, role, invitationExpiresAt}`.
  - **Row found with `status='pending_invitation'`:** atomic-consume the existing active invitation token (UPDATE consumed_at=now() WHERE purpose='invitation' AND consumed_at IS NULL RETURNING — partial-UNIQUE D-41-05 guarantees at most one); INSERT a fresh invitation token row (new audit_correlation_id chain); emit `user_invited` (re-issue); enqueue email; return 200 `{...}`. This is the "owner clicked POST again because the first invite bounced or expired" path — idempotent operator UX without requiring an explicit revoke + delete dance.
  - **Row found with `status='active'`:** return 409 `{error: 'email_already_active'}`. Owner must explicitly soft-delete first (DELETE /users/{id}) if the position is genuinely changing hands.
  - **Soft-deleted row exists for the email (`deleted_at IS NOT NULL`):** the partial-UNIQUE permits the INSERT path automatically (the `deleted_at IS NULL` predicate excludes the old row); new `users.id` minted, historical audit rows from the deleted user retain their `actor_email_snapshot` and `actor_user_id` (per Pitfall 4 invite-accept-INSERT-only invariant — Phase 43 enforces it at CREATE-time, not delegated to Phase 44 RESET-04).
- **D-43-14 (Query param `?include_invite_link=true`):** Owner-only. Default `false`. When `true`, response body is extended with `inviteLinkUrl: 'https://<FRONTEND_BASE_URL>/auth/accept-invite#token=<raw-token>'` (token in URL fragment per RESET-03 — never the path). The frontend base URL comes from `Settings.frontend_base_url` (already used by Telegram bot for similar deep-links; default `http://localhost:5173` in dev). The audit payload for `user_invited` does NOT carry the URL itself — only `link_copied: bool` derived from the query-param value (extends `UserInvitedPayload` — needs a one-line Phase 43 amendment to `audit_payloads.py:UserInvitedPayload` with `link_copied: bool` field). Frontend never sees the URL fragment server-side; standard CSRF + RBAC apply. Use case: email transport breaks (Yandex Postbox circuit-open) and owner needs to onboard reception in the next 30 seconds.
- **D-43-15 (`GET /api/v1/users`):** Query params `?active=true|false&deleted=false&page=1&pageSize=20`. Defaults: `active` unset (returns both), `deleted=false` (returns only `deleted_at IS NULL`), `page=1`, `pageSize=20` (mirrors `core/pagination.py` default). Sort: `created_at DESC` (newest first — matches v1.2 clients list convention). Response: `PaginatedData[UserListItemResponse]` wrapped in `ResponseEnvelope` (standard v1.4 envelope pattern). The `deleted=true` value is owner-only and returns ALL rows (active + deactivated + soft-deleted) — useful for forensic UI; document explicitly in the endpoint docstring.
- **D-43-16 (`PATCH /api/v1/users/{id}/deactivate`):** Body: `{}` (no body — pure state transition). Pre-conditions checked in service-layer SAVEPOINT BEFORE any UPDATE:
  - Target user MUST exist + `deleted_at IS NULL` + `is_active=true` → otherwise 404 `user_not_found` (for missing/deleted) or 409 `user_already_inactive` (for already-deactivated, idempotent-safe).
  - `target.id != current_user.id` → otherwise 409 `cannot_deactivate_self`.
  - If `target.role == 'owner'`: `SELECT count(*) FROM users WHERE role='owner' AND is_active=true AND deleted_at IS NULL AND id != :target_id AND status='active'` MUST return ≥1 → otherwise 409 `cannot_deactivate_last_owner`. The count uses `FOR UPDATE` to serialise concurrent deactivate attempts against the same owner (mirrors v1.2 freeze period serial-arbiter pattern).
  - On success (atomic, single UoW): UPDATE `users SET is_active=false, deactivated_at=now(), deactivated_by_user_id=:current_user_id WHERE id=:target_id`; call `get_user_session_invalidator()(session, user_id=target_id, reason='deactivated')` → returns `sessions_revoked_count`; emit `user_deactivated` with that count.
  - Returns 204 No Content (mutation-without-body convention from v1.4 cancel endpoints).
- **D-43-17 (`PATCH /api/v1/users/{id}/reactivate`):** Body: `{}`. Pre-conditions: target exists + `deleted_at IS NULL` + `is_active=false`. NO self/last-owner guards (re-activation is always safe). On success: UPDATE `users SET is_active=true, deactivated_at=NULL, deactivated_by_user_id=NULL WHERE id=:target_id`; emit `user_reactivated`. Sessions are NOT auto-restored — user re-authenticates normally (refresh families were revoked at deactivate, they stay revoked). Returns 204.
- **D-43-18 (`DELETE /api/v1/users/{id}`):** Soft-delete. Pre-conditions: same self/last-owner guards as deactivate (cannot delete self → 409 `cannot_delete_self`; cannot delete last owner → 409 `cannot_delete_last_owner`). Allowed regardless of `is_active` state (deleting an already-deactivated user is the common case). On success (atomic): UPDATE `users SET deleted_at=now(), is_active=false, deactivated_at=COALESCE(deactivated_at, now())`; revoke all refresh families via `get_user_session_invalidator()(... reason='soft_deleted')` (defensive — most deletes follow a deactivate so families are already revoked, returns 0; but pure-delete-without-deactivate path needs the kill); atomic-consume any pending invitation tokens for this user (UPDATE consumed_at=now() WHERE user_id=:target_id AND purpose='invitation' AND consumed_at IS NULL — no audit on the cascade, the parent `user_soft_deleted` event covers it); emit `user_soft_deleted`. Returns 204.
- **D-43-19 (`POST /api/v1/users/invitations/{token_id}/revoke`):** Body: `{reason?: str}`. Token resolves via `password_reset_tokens.id` (UUID), NOT by raw token (owner UI shows the token row id, never the raw token). Pre-conditions: token exists + `purpose='invitation'` + `consumed_at IS NULL` → otherwise 404 `invitation_not_found` (for missing) or 409 `invitation_already_accepted` (for consumed). On success: atomic UPDATE `password_reset_tokens SET consumed_at=now() WHERE id=:token_id AND purpose='invitation' AND consumed_at IS NULL RETURNING id` → 0-row return is a race-lost outcome that maps to 409 (mirrors v1.1 refresh-token rotation race-loss pattern); emit `user_invitation_revoked` with payload `{audit_correlation_id, revoked_user_id, invitation_token_id, reason}`. Returns 204.

### `/auth/refresh` extension (USERS-06 — RESOLVED)

- **D-43-20 (Join `users.is_active = true AND users.deleted_at IS NULL` at refresh token validation):** Modify `apps/backend/app/modules/auth/service.py:rotate_refresh` to extend the user-row fetch with `is_active=true AND deleted_at IS NULL` in the same SELECT (NOT as a post-fetch Python branch — single SELECT is race-tight; Pitfall 5 case 3 explicit mitigation). On miss, return the SAME error shape as `invalid_session` (401 with body `{error: 'invalid_session'}`) — anti-oracle, no enumeration of which condition failed. Audit: emit `refresh_failed` with reason `account_inactive` (existing event name extended in audit_payloads via a new Literal value `'account_inactive'` for `RefreshFailedPayload.reason` — one-line addition).
- **D-43-21 (No change to `require_user` access-token path):** Access tokens are short-lived (5 min default per Phase 5); the `/auth/refresh` join is the chokepoint that catches deactivated/deleted operators within one refresh cycle. Adding `is_active` to the per-request `require_user` would couple every authenticated request to a `users` SELECT — refused (the 5-minute window before next refresh is acceptable per the threat model: a deactivated reception cannot do meaningful damage in 5 min, AND the deactivate flow already calls `UserSessionInvalidator` which kills all refresh families in the same UoW, so the access token can't be rotated to a fresh one).

### Invitation email content (USER_INVITATION_EMAIL — first locked email template AFTER Phase 42's EMAIL_OTP_LOGIN — RESOLVED)

- **D-43-22 (Template lives in `app/modules/users/email_templates.py`):** Per D-39-02 per-domain ownership + REQUIREMENTS RESET-03 ("`USER_INVITATION_EMAIL_*` in `app/modules/users/email_templates.py`"). Phase 41 D-41-12 pre-registered the identifier `USER_INVITATION_EMAIL` in `LOCKED_EMAIL_TEMPLATES`; Phase 43 ships the **content** (subject + html + text) + the `TEMPLATES: Final[dict[str, EmailTemplate]]` registry entry. Mirrors `app/modules/auth/email_templates.py:EMAIL_OTP_LOGIN` shape (Phase 42 D-42-06).
- **D-43-23 (Russian locked copy — owner sign-off enumerated by constant name):** Single template carries `{full_name}`, `{role_ru}` (translated via `ru.ts`-style `ROLE_RU` dict — `'owner' → 'администратор'`, `'reception' → 'администратор стойки'`), `{invitation_url}` (full URL with `#token=` fragment), `{expires_at_human}` (Russian long-form datetime per `formatMoney`/`formatDate` discipline). Subject: `"Приглашение в Sportzal"` (locked Final[str]). HTML body uses `&nbsp;` entities + RFC-2047-encoded subject per Phase 42 D-42-05 + Pitfall 6 mitigation (Jinja2 SandboxedEnvironment, autoescape=True on HTML, passthrough on text). Owner sign-off enumerated as `D-43-OWNER-COPY-LOCK` at Phase 43 plan SUMMARY (mirrors D-27-OWNER-COPY-LOCK lineage from v1.3). Actual Russian wording drafted by planner + owner-reviewed at plan-time (NOT baked into this CONTEXT.md — owner-copy-lock discipline keeps the strings under owner authority, not Claude's).
- **D-43-24 (Render at enqueue time, transport pre-rendered envelope):** Per D-42-07 — `app/modules/users/service.py:create_user` calls `_render_invitation_email(...)` which imports `users.email_templates`, renders subject/html/text into an `EmailEnvelope` (`app/integrations/email/types.py`), passes the envelope as kwargs to `get_email_dispatcher()(template_id='USER_INVITATION_EMAIL', to=email, audit_correlation_id=..., **envelope_fields)`. The ARQ `dispatch_email` task (Phase 42) never imports `app.modules.users.*` — import-linter contract 3 (`integrations ⊥ modules`) holds.
- **D-43-25 (Sandbox provider in tests):** Integration tests use the `SandboxEmailClient` stub from Phase 42 (D-42-03) — no real Yandex Postbox calls in CI. Unit tests for the template render path use a frozen-string snapshot per the Pitfall 6 golden-file pattern (one fixture: `tests/fixtures/email_user_invitation_snapshot.txt` rendered with deterministic inputs).

### `UserSessionInvalidator` wiring (Phase 41 D-41-25 slot, first real implementation here)

- **D-43-26 (Implementation = `auth.service.invalidate_all_families_for_user`):** New async function in `apps/backend/app/modules/auth/service.py` with signature matching `UserSessionInvalidator` Protocol exactly: `async def invalidate_all_families_for_user(session: AsyncSession, *, user_id: UUID, reason: Literal['deactivated','password_reset','soft_deleted']) -> int`. Body wraps the existing `revoke_all_sessions(session, redis, user_id)` (apps/backend/app/modules/auth/service.py:577) with one-call shape adaptation: pulls the Redis client from the FastAPI app state via `get_redis_from_request_state(...)` helper OR — preferred — accepts `redis` via a closure when registered at composition root. Implementation detail (Plan 43-XX) — Protocol surface unchanged.
- **D-43-27 (Single-wire vs double-wire — RESOLVED):** `UserSessionInvalidator` is consumed only from FastAPI request flows (`POST /users/.../deactivate`, `DELETE /users/...`, future Phase 44 `POST /auth/password-reset/confirm`). It is NOT consumed from ARQ worker contexts (no cron deactivates users). So registration is **single-wire in `app/main.py:create_app()` only** — NOT double-wired in `app/workers/__init__.py`. Distinguishes from `EmailDispatcher` (D-42-XX double-wire) because the worker has zero `get_user_session_invalidator()` callsites. A parity test (`tests/unit/test_app_wiring.py::test_user_session_invalidator_registered`) asserts the registration in the FastAPI app; no worker-side assertion needed.
- **D-43-28 (Returns `sessions_revoked_count` for audit payload):** The int return is plumbed straight into `UserDeactivatedPayload.sessions_revoked_count`. On soft-delete path, the count goes into a structlog log line (no payload field on `UserSoftDeletedPayload` — D-43-04 / pre-registered shape).

### RBAC + CSRF + audit traceability (USERS-07 — RESOLVED)

- **D-43-29 (Router-layer enforcement, mirrors clients pattern):** Every endpoint decorator includes `Depends(require_permission(Action.X, Resource.USERS))` (auth happens first → 401), then `Depends(verify_csrf)` for mutations (403 on missing/invalid token). Dependency declaration order matters per `app/modules/clients/router.py:17-19` — auth before RBAC before CSRF.
- **D-43-30 (3-way RBAC parity test extension):** Already satisfied at Phase 41 D-41-21 (USERS resource + 4 OWNER_ONLY pairs are byte-equal across backend/can.ts/registry.ts). Phase 43 ships zero new admin-web changes — the existing `tests/test_rbac_parity.py` already passes against the v1.6 state.
- **D-43-31 (USERS-07 traceability auto-satisfied):** Every `audit.emit(...)` from `app/modules/users/service.py` runs inside an HTTP request → `ActorContextMiddleware` (Phase 41 D-41-08) has set `actor_context_var` → `audit.emit` reads it → `audit_log.actor_email_snapshot` is populated → past-deactivation lookups work. No per-module wiring needed; the infra commit (Phase 41) handles it. Phase 43 just ensures the users module does NOT use a non-request execution context for audit emits (no ARQ jobs in scope).

### Eager-import discipline (REG-29-04 — preventative)

- **D-43-32 (No new eager-import lines needed):** Phase 43 introduces ZERO new ORM tables (`User` is already eagerly imported via `app/workers/__init__.py` ← Phase 41 0022). The 4 new columns on `users` are visible to the worker the moment the migration applies (column metadata is per-row, not per-import). `tests/unit/test_workers_eager_import.py` requires zero amendments. The migration discipline check (`alembic upgrade head` round-trip clean) is the [BLOCKING] checkpoint.

### Test surface

- **D-43-33 (Test files mirror clients module test layout):**
  - `tests/integration/users/test_users_crud.py` — happy path + idempotent re-invite + soft-delete-then-recreate-email + paginated list with filters.
  - `tests/integration/users/test_users_guards.py` — cannot_deactivate_self / cannot_deactivate_last_owner / cannot_delete_self / cannot_delete_last_owner / RBAC 403 from reception / CSRF 403 on missing token.
  - `tests/integration/users/test_users_session_invalidation.py` — deactivate revokes all families + next `/auth/refresh` returns 401 `invalid_session` (anti-oracle body) + `audit_log` shows `user_deactivated` with `sessions_revoked_count > 0`.
  - `tests/integration/users/test_users_invitation_flow.py` — invitation email envelope is enqueued through `SandboxEmailClient`; `?include_invite_link=true` returns URL; revoke flips `consumed_at`.
  - `tests/integration/users/test_refresh_account_inactive.py` — extends Phase 41 `test_password_reset_no_oracle.py` discipline; refresh-token for a deactivated user returns identical body to invalid-session refresh; bounded timing within 100ms tolerance.
  - `tests/unit/users/test_email_template_render.py` — Jinja2 template renders against snapshot file with deterministic inputs (full_name, role_ru, expires_at fixed).
  - `tests/unit/test_locked_email_templates_ast.py` — extended with one real-callsite assertion that `users.service.create_user` references `template_id='USER_INVITATION_EMAIL'` literal (Phase 42 4-11 lesson — Wave 4 test extension precedent).
- **D-43-34 (No deviations from anti-pattern table):** Specifically: tests use real Postgres via SAVEPOINT per-test (Phase 41 D-41-18 lineage); audit emits exercised via real `audit.emit()` not unit-mocked (Phase 42 CR-01 lesson); no monkeypatching the ContextVar (use the request context properly via `httpx.AsyncClient` with auth cookies).

### Plan packaging (planner sizing hints, not locks)

- **D-43-35 (Wave structure — planner refines):** Expected wave shape, subject to planner adjustment:
  - **Wave 1** (parallel): 43-01 Alembic 0030 + User ORM extension (3 hours); 43-02 `users/schemas.py` + `permissions.py` + `constants.py` + `email_templates.py` registry skeleton (2 hours); 43-03 `auth.service.invalidate_all_families_for_user` impl + main.py registration + parity test (2 hours).
  - **Wave 2** (blocked on Wave 1): 43-04 `users/repository.py` list_alive/get_alive/invitation token CRUD (3 hours); 43-05 `users/service.py` create/deactivate/reactivate/soft-delete/revoke orchestration + audit.emit + render (5 hours); 43-06 `users/router.py` 6 endpoints + RBAC + CSRF (3 hours).
  - **Wave 3** (blocked on Wave 2): 43-07 `/auth/refresh` is_active+deleted_at join + RefreshFailedPayload reason extension (1 hour); 43-08 `audit_payloads.UserInvitedPayload.link_copied` field add (30 min — kept separate so the audit_payloads.py touch doesn't block Wave 2's service.py work).
  - **Wave 4** (blocked on Wave 3): 43-09..14 the 6 test files (parallel-eligible after the implementation lands).
  - Total: ~14 plans across 4 waves. Planner refines based on file-overlap minimisation (Phase 42 precedent: parallel waves require zero `files_modified` overlap pairwise).
- **D-43-36 (Round-trip [BLOCKING] checkpoint on plan 43-01):** Alembic 0030 plan ships with an explicit `[BLOCKING] alembic round-trip checkpoint` step (per Phase 42 4-15 / 4-16 precedent). Migration MUST `upgrade head → downgrade -1 → upgrade head` clean before any code-side plan in Wave 2 unblocks. Mirrors the v1.6 hygiene discipline (Phase 42 16-plan precedent).

### Claude's Discretion

- Exact Russian wording of `USER_INVITATION_EMAIL` subject/body/text (owner-copy-lock — drafted by planner, owner-signed-off at plan SUMMARY).
- Exact wording of error messages in non-anti-oracle paths (e.g. `"Невозможно деактивировать единственного владельца"` vs English `cannot_deactivate_last_owner` — UI surface vs error code; tests assert on error code, not localised message).
- Whether `UserListItemResponse.invitationExpiresAt` is `None` or omitted for `status='active'` rows (Pydantic config decision — recommend `None` for stable wire shape, no exclude_none).
- Internal helper function naming inside `service.py` (`_assert_can_deactivate` vs `_guard_deactivate` etc.).
- Whether the `?include_invite_link=true` URL includes a query-string CSRF nonce or relies on the path-fragment + cookie-pair to keep the URL CSRF-safe (recommend: no extra nonce; the fragment is read by the SPA which submits the consume request with the normal CSRF cookie pair).
- Migration docstring wording.
- Whether `deactivated_by_user_id` is indexed (recommend: no — read-side audit join is rare, not on hot path).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 43 source-of-truth specs (locked)
- `.planning/REQUIREMENTS.md` §§ USERS-01..07 — locked requirements; non-negotiable acceptance criteria
- `.planning/ROADMAP.md` §§ Phase 43 — goal + 5 success criteria + dependency declaration
- `.planning/PROJECT.md` — current state (v1.5 shipped 2026-05-18; v1.6 Phase 41 + Phase 42 landed; 11 v1.6 LOCKED_AUDIT_EVENTS pairs registered; Resource.USERS active in OWNER_ONLY)

### Phase 41 dependency surface (mandatory — Phase 43 cannot ship without these)
- `.planning/phases/41-infra-bedrock-anti-oracle-scaffold/41-CONTEXT.md` — D-41-01 (User hoist), D-41-04 (`password_reset_tokens` unified table with `purpose='invitation'`), D-41-07 (INSERT-only on invite-accept — Phase 43 enforces at CREATE), D-41-08 (ContextVar actor capture), D-41-09 (no actor fields in payloads), D-41-12 (`USER_INVITATION_EMAIL` pre-locked identifier), D-41-15 (migrations 0022–0025 scope — Phase 43 ships 0030 outside that bundle), D-41-21 (USERS resource + OWNER_ONLY entries), D-41-25 (`UserSessionInvalidator` Protocol slot), D-41-28 (SVC001 scope already includes `users/service.py`)
- `apps/backend/app/core/models.py` — hoisted `User` ORM (Phase 41); Phase 43 extends with `is_active`, `status`, `deactivated_at`, `deactivated_by_user_id`, drops `password_hash NOT NULL`
- `apps/backend/app/core/dependencies.py:608-744` — `EmailDispatcher` + `UserSessionInvalidator` Protocol slot declarations + accessors; Phase 43 wires `UserSessionInvalidator` in `app/main.py:create_app()`
- `apps/backend/app/core/audit_payloads.py:510-598` — pre-registered 6 user-lifecycle payloads with `extra='forbid'`; Phase 43 extends `UserInvitedPayload` with `link_copied: bool` (D-43-14)
- `apps/backend/app/core/permissions.py:29-123` — `Resource.USERS` + 4 OWNER_ONLY pairs already active (Phase 41 D-41-21)
- `apps/backend/alembic/versions/0022_users_soft_delete_partial_unique.py` — `users.deleted_at` + partial-UNIQUE `(lower(email)) WHERE deleted_at IS NULL` — Phase 43 INSERT-on-email-reclaim relies on this
- `apps/backend/alembic/versions/0025_password_reset_tokens.py` — unified table with `purpose IN ('password_reset','invitation')` + partial-UNIQUE `(user_id, purpose) WHERE consumed_at IS NULL` — Phase 43 writes only `purpose='invitation'` rows
- `apps/backend/alembic/versions/0028_users_email_verified.py` — `users.email_verified` column + bootstrap docstring; Phase 43 D-43-01 sets it to true on invitation-accept (Phase 44)
- `apps/backend/tests/integration/auth/test_password_reset_no_oracle.py` — xfail-strict 4-case anti-oracle template; Phase 43 mirrors discipline for `test_refresh_account_inactive.py`

### Phase 42 dependency surface (LOCKED — Phase 43 consumes the EmailDispatcher slot)
- `.planning/phases/42-email-transport-layer-email-otp-fallback/42-CONTEXT.md` — D-42-02 (`aioboto3` SES-V2 client), D-42-05 (Jinja2 SandboxedEnvironment), D-42-06 (per-domain templates), D-42-07 (render at enqueue, transport envelope), D-42-13 (ARQ task config), D-42-16 (`EmailEnvelope` shape), D-42-18 (`email_send_log` schema)
- `apps/backend/app/integrations/email/types.py` (Phase 42 plan 01) — `EmailEnvelope` frozen dataclass; Phase 43 constructs envelopes via the rendering layer
- `apps/backend/app/integrations/email/client.py` (Phase 42 plan 07) — `aioboto3` client + `SandboxEmailClient`; Phase 43 tests against the sandbox
- `apps/backend/app/modules/auth/email_templates.py` (Phase 42 plan 05) — reference shape for `app/modules/users/email_templates.py` (Phase 43)
- `apps/backend/app/workers/dispatch_email.py` (Phase 42 plan 08) — ARQ task body; Phase 43 enqueues into it via the EmailDispatcher slot
- `apps/backend/app/main.py:create_app()` — Phase 42 wired `register_email_dispatcher`; Phase 43 adds `register_user_session_invalidator` adjacent

### v1.6 research (HIGH confidence — must read for Phase 43 trade-off rationale)
- `.planning/research/PITFALLS.md` §§ Pitfall 4 (token replay + email re-claim — D-43-13 fourth bullet enforces INSERT-only at CREATE-time), Pitfall 5 (audit traceability under multi-user — D-43-31 satisfaction path), Pitfall 6 (locked Russian copy — D-43-23 enforcement), Pitfall 11 (invitation TTL — D-43-12 7-day choice)
- `.planning/research/FEATURES.md` — 11 anti-features (esp. plaintext password email — D-43-13 NEVER returns password; dual-email-per-user — partial-UNIQUE enforces) — Phase 43 must not enable these; `?include_invite_link=true` is the explicit P2 escape hatch
- `.planning/research/ARCHITECTURE.md` — modular monolith additions, Protocol slot pattern (Phase 43 wires the 12th carve-out)
- `.planning/research/SUMMARY.md` — 7 open conflicts; Phase 43 resolves #7 (email-verify policy → D-43-01)

### v1.0–v1.5 codebase landmarks (Phase 43 extends or mirrors)
- `apps/backend/app/modules/clients/` — full module shape (router/service/repository/schemas/permissions/constants/models); Phase 43 mirrors except `models.py` (User lives in `core/models.py`)
- `apps/backend/app/modules/clients/repository.py:30-100` — `list_alive`/`get_alive` partition pattern; soft-delete invariant; no commit/flush in repository (D-03 lineage)
- `apps/backend/app/modules/clients/service.py:1-100` — service orchestration; co-transactional audit emit; mutation ordering (insert → flush → emit | mutate → emit → flush); `await session.commit()` at boundary (Phase 12.1 lesson)
- `apps/backend/app/modules/clients/router.py:1-130` — RBAC + CSRF dependency injection order (auth → RBAC → CSRF → session)
- `apps/backend/app/modules/auth/service.py:506-645` — `revoke_session` / `revoke_all_sessions` reference impl; D-43-26 wraps `revoke_all_sessions` into the `UserSessionInvalidator` Protocol signature
- `apps/backend/app/modules/auth/service.py:333+` — `rotate_refresh` hot path; D-43-20 adds `is_active=true AND deleted_at IS NULL` to the user-row SELECT
- `apps/backend/app/core/schemas.py` — `BackendSchemaBase` + `ResponseEnvelope`; Phase 43 response models inherit from `BackendSchemaBase` (camelCase wire)
- `apps/backend/app/core/pagination.py` — `PaginatedData[T]` + `PageQuery`; D-43-15 uses defaults `page=1, page_size=20`
- `apps/backend/app/core/middleware.py` — `ActorContextMiddleware` (Phase 41 D-41-08); Phase 43 audit emits inherit ContextVar automatically
- `apps/backend/tests/test_rbac_parity.py` — 3-way parity; already covers USERS at Phase 41 (D-43-30 — zero amendments)
- `apps/backend/tests/unit/test_workers_eager_import.py` — zero amendments needed for Phase 43 (no new tables — D-43-32)
- `apps/backend/tests/unit/test_locked_email_templates_ast.py` (Phase 42 plan 11) — Phase 43 extends with one real-callsite assertion for `USER_INVITATION_EMAIL`

### Verification + governance lineage
- `.planning/milestones/v1.5-VERIFICATION-LOG.md` — REG-29-01/03/04 regressions + DEFER-40-01 runbook scaffolding lesson; Phase 43 preventative discipline derives from these
- `.planning/phases/42-email-transport-layer-email-otp-fallback/42-VERIFICATION.md` — CR-01..04 + WR hygiene findings; D-43-34 inherits the lessons (real audit emit in tests, no kwargs nesting, atomic Redis ops where relevant)
- `.planning/milestones/v1.1-MILESTONE-AUDIT.md` — Phase 12.1 SVC001 + commit-gate lessons (D-43-09 service-owns-transaction pattern)

### Key D-XX-YY decision lineage carried forward
- **D-12** (v1.1): `escape_like_pattern` for ILIKE inputs — Phase 43 `list_alive` filters on email may use ILIKE; reuse the helper.
- **D-20-9** (v1.2): `/checkin` anti-oracle DM equality — Phase 43 D-43-20 mirrors at the `/auth/refresh` body shape.
- **D-27-OWNER-COPY-LOCK** (v1.3): per-template owner sign-off enumerated by constant name — D-43-23 ships as `D-43-OWNER-COPY-LOCK` at plan SUMMARY.
- **D-39-02** (v1.5): per-domain template ownership — D-43-22 places `USER_INVITATION_EMAIL` in `app/modules/users/email_templates.py`.
- **REG-29-03** (v1.3): double-wire Protocol slot; D-43-27 explicitly justifies single-wire for `UserSessionInvalidator`.
- **REG-29-04** (v1.3): eager-import discipline; D-43-32 confirms zero amendments (no new tables).
- **REG-36-03** (v1.4): UUIDs serialise as `str(uuid)` in audit payloads — Phase 43 inherits via pre-registered payloads.
- **Phase 12.1 SVC001 + commit-gate**: services own `session.commit()`; D-43-09 service-layer carries it (already in SVC001 walker scope via D-41-28).
- **Phase 42 CR-01 audit emit shape**: Phase 43 audit.emit calls pass payload kwargs flat (NOT nested under a `payload=` dict) — service.py callsites mirror `auth.service` post-fix.
- **Phase 42 4-15 + 4-16 BLOCKING alembic round-trip**: D-43-36 carries the precedent for migration 0030.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`apps/backend/app/modules/clients/{router,service,repository,schemas}.py`** — full module shape Phase 43 mirrors. Repository pattern (`list_alive`/`get_alive`), service orchestration (audit emit + flush + commit), router (RBAC + CSRF dependency chain) all transfer directly. Differences: no `models.py` in users/ (User lives in core/models.py per D-41-01); add `email_templates.py` (new for v1.6 modules); `permissions.py` as marker file (clients doesn't have one because clients RBAC was the original).
- **`apps/backend/app/core/dependencies.py:608-744`** — `EmailDispatcher` + `UserSessionInvalidator` Protocol slot declarations + register/get accessors are ready; Phase 43 D-43-26/27 wires the real `UserSessionInvalidator` impl + registration.
- **`apps/backend/app/core/audit_payloads.py:510-598`** — 6 user-lifecycle Pydantic payloads pre-registered with `extra='forbid'`. Phase 43 consumes them verbatim (one additive `link_copied: bool` on `UserInvitedPayload` per D-43-14).
- **`apps/backend/app/modules/auth/service.py:506-645`** — `revoke_session` + `revoke_all_sessions` reference impl. Phase 43 D-43-26 wraps `revoke_all_sessions` into the Protocol-conformant `invalidate_all_families_for_user`.
- **`apps/backend/app/modules/auth/service.py:333+`** — `rotate_refresh` hot path. Phase 43 D-43-20 adds `is_active=true AND deleted_at IS NULL` to the user-row SELECT (single-SELECT race-tight).
- **`apps/backend/app/modules/auth/email_templates.py`** (Phase 42 plan 05) — Phase 43 `app/modules/users/email_templates.py` mirrors the shape: `TEMPLATES: Final[dict[str, EmailTemplate]]` registry + Jinja2 SandboxedEnvironment usage.
- **`apps/backend/alembic/versions/0011_trainers.py`** — `is_active BOOLEAN NOT NULL DEFAULT true` + `is_active=false` soft-delete pattern; Phase 43 migration 0030 mirrors the column shape.
- **`apps/backend/alembic/versions/0008_membership_freeze_periods.py`** — CHECK constraint correlating two columns (e.g. `(started_at IS NULL AND ended_at IS NULL) OR (started_at IS NOT NULL)`); Phase 43 D-43-06 mirrors for `(is_active=true AND deactivated_at IS NULL) OR (is_active=false AND deactivated_at IS NOT NULL)`.
- **`apps/backend/app/core/schemas.py:BackendSchemaBase`** — camelCase wire format; Phase 43 schemas inherit.
- **`apps/backend/app/core/pagination.py:PaginatedData,PageQuery`** — pagination envelope; Phase 43 list endpoint uses defaults.
- **`apps/backend/app/integrations/email/types.py:EmailEnvelope`** (Phase 42 plan 01) — frozen dataclass; Phase 43 constructs at enqueue time.

### Established Patterns

- **Service owns transaction (D-03 / Phase 12.1 lineage):** Repository emits NO `commit()`/`flush()`; service emits `audit.emit` co-transactionally, `await session.flush()` to surface IntegrityErrors before route exit, `await session.commit()` at the route boundary. SVC001 AST walker (Phase 41 D-41-28) enforces — `users/service.py` is already in scope.
- **Soft-delete-and-recreate via partial-UNIQUE (clients.phone + Phase 41 0022):** `INSERT` is the only path; never `UPDATE existing.deleted_at TO NULL`. Phase 43 D-43-13 enforces at CREATE-time (D-41-07 deferred this from Phase 41).
- **Anti-oracle response equality (D-20-9 / RESET-06 / Phase 42 AUTH-EM-04):** Identical body + bounded timing across success/failure modes. Phase 43 D-43-20 extends to `/auth/refresh` for `account_inactive`.
- **Protocol slot single-wire vs double-wire (REG-29-03):** Double-wire when both FastAPI + ARQ worker consume; single-wire when only one consumer. Phase 43 D-43-27 single-wires `UserSessionInvalidator` (no ARQ consumer).
- **Per-domain template ownership (D-39-02):** Templates next to owning module; D-43-22 places `USER_INVITATION_EMAIL` in `app/modules/users/email_templates.py`.
- **Owner-copy-lock (D-27):** Russian email/DM content enumerated by constant name in plan SUMMARY; owner explicitly signs off. D-43-23 carries forward as `D-43-OWNER-COPY-LOCK`.
- **xfail-strict for forward-declared tests (D-41-17):** Phase 43 does NOT need this discipline — all assertions land with implementation in the same wave.
- **Migration round-trip [BLOCKING] checkpoint (Phase 42 4-15/4-16):** D-43-36 carries the precedent for plan 43-01.
- **Test discipline (Phase 42 CR-01 lesson):** Audit emit exercised via real `audit.emit()` + `audit_log` query in integration tests; no kwargs nesting; no monkeypatching the ContextVar.

### Integration Points

- **`app/main.py:create_app()`** — Phase 43 adds `register_user_session_invalidator(invalidate_all_families_for_user)` adjacent to the Phase 42 `register_email_dispatcher(...)` call. Single addition.
- **`app/main.py:include_router`** — Phase 43 adds `from app.modules.users import router as users_router` + `app.include_router(users_router, prefix='/api/v1')`.
- **`app/modules/auth/service.py:rotate_refresh`** — Phase 43 D-43-20 modifies the user-row SELECT (single-line change).
- **`app/core/audit_payloads.py:UserInvitedPayload`** — Phase 43 D-43-14 adds `link_copied: bool` field (additive, extra='forbid' compatible).
- **`apps/admin-web/` — NO touch in Phase 43.** RBAC parity already established at Phase 41; Phase 43 ships backend-only. Future v2.0 production frontend (design team) integrates the surface.
- **`packages/api-client/`** — OpenAPI drift gate at Phase 46 (HANDOFF-03) picks up the new routes; Phase 43 does NOT regenerate `openapi.json` mid-milestone (drift gate refreshes only at handoff per v1.4 lesson).

</code_context>

<specifics>
## Specific Ideas

- **Trust + lazy-verify (D-43-01)** — recommended default chosen because operator turnover is rare (1–3/year for a single-gym CRM); the extra security from a separate click-to-verify step does not pay for the doubled email round-trip when invitation-accept already proves email control.
- **Explicit `status` column over derived `password_hash IS NULL` (D-43-06)** — recommended default because explicit columns are debuggable in `psql` and admit future statuses (`'invited_expired'` for v1.7 auto-expiry sweeping) without a second schema migration.
- **Idempotent re-invite for `pending_invitation` users (D-43-13 second bullet)** — recommended default because operator UX of "click POST again because the email bounced" is the dominant onboarding-failure path; requiring an explicit revoke+delete dance is hostile to the 1-user-per-week onboarding rhythm of a single gym.
- **`?include_invite_link=true` as explicit P2 escape hatch (D-43-14)** — recommended default because Phase 42's circuit breaker (D-42-14) acknowledges email transport CAN fail; the copy-paste fallback is the only way to onboard reception during a Yandex Postbox outage. Owner-only + audit-logged keeps the surface contained.
- **No new `actor_display_name` payload field (D-43-03/04)** — recommended default because Phase 41 D-41-08 + D-41-09 already solved the traceability question with column-level `actor_email_snapshot`; adding a payload field would be redundant data with a worse refresh story (snapshot at emit time vs current users.full_name).
- **Single migration 0030 — outside Phase 41 bedrock bundle (D-43-05)** — recommended default because D-41-15 explicitly scoped the bedrock to 0022–0025; lifecycle columns have no downstream consumers before Phase 43, so deferring to feature-phase placement preserves the bedrock-vs-feature boundary cleanly.
- **Single-wire `UserSessionInvalidator` (D-43-27)** — recommended default because the worker has zero consumers of this slot; double-wiring would create an idle registration that REG-29-03 parity tests would flag as inconsistent if anyone ever tries to consume it from a cron without a parallel main.py update.

</specifics>

<deferred>
## Deferred Ideas

- **`POST /api/v1/auth/password-reset/request` + `confirm`** — Phase 44 (RESET-01/02). Token storage (`password_reset_tokens.purpose='password_reset'`) already exists from Phase 41 0025.
- **`POST /api/v1/users/invitations/accept`** — Phase 44 RESET-04. Sets password (`password_hash` becomes non-NULL), flips `status='active'` + `email_verified=true`, atomically consumes the invitation token.
- **`PASSWORD_RESET_EMAIL` template content** — Phase 44 RESET-03 (`app/modules/auth/email_templates.py`).
- **Daily ARQ cleanup cron for `password_reset_tokens`** — Phase 44 (D-41-06). Daily job deletes rows where `expires_at < now() - INTERVAL '30 days'`.
- **Re-send verification email + owner-triggered re-verify ladder** — v1.7. Operator turnover is rare enough that explicit re-invite (revoke + re-issue) covers the typo case.
- **Audit-log read API (filter by actor, time-window, event-kind)** — v1.8. Phase 43 ships write-side traceability; read-side is a separate scope per PROJECT.md backlog.
- **`actor_display_name` formatting policy** (first-name + last-initial vs full name) — superseded by D-43-03 (no payload field; v1.8 read API joins live `users.full_name`).
- **`?status=invited_expired` listing** — v1.7 auto-expiry sweeping. Phase 43 has only `'active'` and `'pending_invitation'` in the CHECK constraint; v1.7 ALTERs the constraint to add `'invited_expired'`.
- **Email-channel preference per operator** (separate notification-channel preferences vs always-fallback) — Pitfall 2 lineage; Phase 45 NOTIFY-* concern, not Phase 43.
- **Bouncing-mailbox aggressive `email_verified=false` flag flip** — Phase 42 D-42-XX explicit defer to v1.7.
- **Owner-managed password reset for another user (administrative override)** — out of scope for v1.6; if the owner cannot reach reception, the revoke + re-invite path provides equivalent functionality via the user's mailbox.
- **Activity log surfacing in operator list** ("last seen", "last login at") — v1.8 audit-read concern.
- **IN-03 (Phase 43 review): `INVITATION_TOKEN_TTL` style inconsistency vs `frontend_base_url`** — Promote `INVITATION_TOKEN_TTL` to a `Settings` field (`invitation_token_ttl_seconds: int = 7 * 86400`) and read it at call time so test overrides of the env var take effect. **Deferred to v1.7** — neither configuration is currently per-environment; no immediate functional impact. Recommended by 43-REVIEW.md IN-03.
- **IN-04 (Phase 43 review): `__table_args__ name="role"` constraint naming inconsistency** — The `CheckConstraint("role IN ('owner', 'reception')", name="role")` on `apps/backend/app/core/models.py:116-118` predates the `ck_<table>_<name>` convention used by migration 0030. **Deferred to a future Alembic naming-cleanup pass** — out-of-Phase-43-scope (already noted as such by the reviewer at 43-REVIEW.md IN-04). No-op for v1.6.

</deferred>

---

*Phase: 43-multi-user-admin-module*
*Context gathered: 2026-05-19*
