# Phase 44: Invitation + Password-Reset Flow — Context

**Gathered:** 2026-05-19
**Status:** Ready for planning
**Mode:** `--auto` (recommended defaults auto-selected from REQUIREMENTS.md / ROADMAP.md / Phase 41 + 42 + 43 CONTEXT / PITFALLS.md research)

<domain>
## Phase Boundary

Ship the four auth-side token-consuming endpoints that close the v1.6 user-lifecycle loop:

1. `POST /api/v1/auth/password-reset/request` — anti-oracle reset-link issuance (RESET-01).
2. `POST /api/v1/auth/password-reset/confirm` — atomic single-SQL consume + password rotate + revoke-all (RESET-02).
3. `POST /api/v1/users/invitations/accept` — pending-invitation INSERT-only password-set + issue session cookie pair (RESET-04, router lives in `users/` per D-43-RESET-04 forwarding, service in `auth/password_reset_service.py` per D-41-28 SVC001 extension).
4. `POST /api/v1/users/invitations/{token_id}/revoke` — owner-only invitation revoke (RESET-05; **already implemented at Phase 43** plan 43-05/06, see D-43-19 + verification — this phase only adds the `password_reset_completed`-style integration tests if not already covered).

Plus the supporting cast:
- `PASSWORD_RESET_EMAIL` locked Russian template content (RESET-03) in `app/modules/auth/email_templates.py` (identifier pre-registered in Phase 41 D-41-12, slot in `LOCKED_EMAIL_TEMPLATES` per `audit.py:271`).
- `USER_INVITATION_EMAIL` rendering already shipped Phase 43 (D-43-22); Phase 44 consumes the render path verbatim from `app/modules/users/email_templates.py`.
- Constant-time response floor (≥500ms) on `/password-reset/request` to defeat timing oracle (RESET-01).
- Per-IP (5/15min) + per-email (1/min + 5/hour) rate limit on `/password-reset/request` — 3 separate Redis fixed-window keys, all checked BEFORE the user lookup (anti-oracle, same discipline as `auth/rate_limit.py`).
- Daily ARQ cleanup cron `cleanup_expired_password_reset_tokens` (D-41-06) — deletes `password_reset_tokens WHERE expires_at < now() - INTERVAL '30 days'`. Scheduled 03:30 Europe/Moscow (off-peak, well away from 06:15/06:35 notification crons).
- Ungating `tests/integration/auth/test_password_reset_no_oracle.py` — D-41-17 RED→GREEN: remove `@pytest.mark.xfail(strict=True)` marker in the same commit that ships RESET-01.

Requirements in scope: **RESET-01, RESET-02, RESET-03, RESET-04, RESET-05** (5 reqs per `.planning/REQUIREMENTS.md` traceability table). RESET-06 already shipped at Phase 41 (xfail-strict template).

**Out of scope (forwarded):**
- Owner administrative-override password reset (force-set another user's password without their email control) — v1.7. The revoke + re-invite path already covers the operational case ("operator lost mailbox access").
- Email re-verification ladder, re-send invitation, owner-triggered re-verify — v1.7 (per D-43-01 — operator turnover is rare; revoke + re-issue suffices).
- Multi-channel reset (SMS / Telegram-DM token) — v1.7+; Phase 44 is email-only since v1.6 only delivers tokens via the new email transport (Phase 42).
- Self-service email change (`PATCH /api/v1/auth/me` with email-verify round-trip) — v1.7+.
- Reset-flow surfacing in admin-web UI — frontend integration deferred to v2.0 design-team handoff (per Phase 43 D-43 — Phase 43/44 ship backend-only; admin-web RBAC parity already established).
- Forensic audit-read API ("show all reset attempts for user X") — v1.8.
- HSTS / referrer-policy hardening for the reset-link landing page — v1.7+ frontend concern (RESET-03 places token in URL fragment `#token=…` for browser-side hygiene; server-side mitigation is the body/fragment-only choice and is in scope).
- Phase 45 NOTIFY-* expiring/booking/payment-receipt emails (separate phase, already scoped).
- OpenAPI schema regen — Phase 46 HANDOFF-03 (drift gate refreshes only at handoff per v1.4 lesson; Phase 44 endpoints will appear in the Phase-46 atomic regen).

</domain>

<decisions>
## Implementation Decisions

### Open Conflict #2 — Reset-token storage (RESOLVED at Phase 41, confirmed here)

- **D-44-01 (DB-table `password_reset_tokens` with `purpose` column — itsdangerous-stateless REJECTED):** Phase 41 D-41-04 already locked the choice: single table `password_reset_tokens` (Alembic 0025) discriminated by `purpose IN ('password_reset', 'invitation')` backs BOTH flows. Atomic-consume is single-SQL `UPDATE … RETURNING` on the row, NOT a stateless `password_changed_at` equality check on the signed payload. Rationale carried forward verbatim from D-41-04:
  - DB-table path admits revocation (set `consumed_at=now()` before token TTL expires — see RESET-05).
  - Single-use guarantee lives at SQL layer (`UPDATE … WHERE consumed_at IS NULL RETURNING id` — race-tight under concurrent confirms).
  - Already-pre-built infrastructure: ORM (`app/modules/auth/password_reset_token_model.py`), migration (0025), partial-UNIQUE (`uq_password_reset_tokens_active`), hash-lookup index (`ix_password_reset_tokens_token_hash`) are all live since Phase 41.
  - itsdangerous-stateless would require a NEW `users.password_changed_at` column for the single-use check AND would leak the user_id via the signed payload (forensic but also a thin enumeration surface) — strictly worse for v1.6's anti-oracle posture.
- **D-44-02 (No new `users.password_changed_at` column — D-41-04 obsoletes it):** REQUIREMENTS.md RESET-02 text ("bumps `users.password_changed_at`") was superseded by D-41-04 — the column does NOT exist in the `users` table (verified at `apps/backend/app/core/models.py:35-118`). The atomic-consume marker is `password_reset_tokens.consumed_at`; the forensic timestamp lives on the `password_reset_completed` audit row's `created_at`. Phase 44 ships ZERO new schema migrations. (The REQUIREMENTS.md sentence is treated as legacy phrasing — codebase + D-41-04 are the locked truth.)

### Token entropy + URL format (RESET-03 — RESOLVED)

- **D-44-03 (32-byte `secrets.token_urlsafe(32)` raw token, sha256 hash stored):** Raw token = `secrets.token_urlsafe(32)` (256 bits of entropy, base64url-encoded ⇒ ~43-char string). Storage = `hashlib.sha256(raw_token.encode()).hexdigest()` written to `password_reset_tokens.token_hash` (64-char hex). The raw token is NEVER persisted server-side — it exists transiently in the email body only. The confirm path hashes the inbound token and matches by `token_hash`; this prevents a DB exfiltration from yielding active reset links. Mirrors v1.1 refresh-token discipline (`app/modules/auth/service.py:revoke_session` family-row hash pattern) and the Phase 43 invitation token helper (`repository._hash_token` at `apps/backend/app/modules/users/repository.py:42`).
- **D-44-04 (Token in URL fragment `#token=...`, NEVER URL path — PITFALLS token-leak-via-Referer):** RESET-03 invariant. URL shape: `https://<FRONTEND_BASE_URL>/auth/password-reset#token=<raw>` and `https://<FRONTEND_BASE_URL>/auth/accept-invite#token=<raw>` (invitation shape already locked at Phase 43 D-43-14 / `_build_invitation_url`). The SPA reads `window.location.hash`, posts to `/api/v1/auth/password-reset/confirm` or `/api/v1/users/invitations/accept` with `{token: <raw>, ...}` in the JSON body. Server-side `Referer-Policy: same-origin` header guidance is for the SPA (v2.0 frontend concern); Phase 44 is body/fragment-only on the backend contract.
- **D-44-05 (TTLs — locked from RESET-03):** Password-reset token TTL = **1 hour** (`timedelta(hours=1)` — OWASP 2025 floor). Invitation token TTL = **7 days** (`timedelta(days=7)` — already in `app/modules/users/constants.py:INVITATION_TOKEN_TTL`, Phase 43 D-43-12). Phase 44 adds `PASSWORD_RESET_TOKEN_TTL: Final[timedelta] = timedelta(hours=1)` in `app/modules/auth/constants.py` (NEW file — mirrors `app/modules/users/constants.py` shape; one constant only). Both TTLs are read at INSERT time (`expires_at = now() + TTL`) and at SELECT-time predicate (`expires_at > now()` in the atomic-consume WHERE clause).

### `/password-reset/request` anti-oracle envelope (RESET-01 — RESOLVED)

- **D-44-06 (Identical 202 + identical body for all 4 cases):** Response body = `{"data": null, "meta": {}}` (standard `envelope(None)` shape from `app/core/schemas.py`), HTTP 202. NO email-presence leak: response is byte-identical whether the email resolves to an active user, deactivated user, owner, or non-existent address. Matches the Phase 41 `test_password_reset_no_oracle.py` contract (RESET-06 / D-41-17).
- **D-44-07 (Constant-time response floor = 500ms — `asyncio.sleep(max(0, 0.5 - elapsed))`):** Handler wraps the entire request lifecycle in a `time.perf_counter()` start/end deltacomputation; immediately before returning, `await asyncio.sleep(max(0.0, 0.5 - elapsed))` ensures every request takes ≥500ms wall-clock. This is enough headroom to cover: rate-limit checks (Redis GET, <5ms), user lookup (Postgres SELECT, ~10ms), token row INSERT (~10ms), audit emit + flush (~15ms), and the email-enqueue ARQ push (~20ms) — all well under 500ms even on a cold path. The Phase 41 test (`bounded_equal_timing_within_100ms`) admits a 100ms tolerance window which `time.perf_counter()`-based sleep-to-floor satisfies easily (variance in real-world tests is <30ms).
- **D-44-08 (Audit emit in BOTH branches — known AND unknown email):** Per D-41-10: known-email branch emits `password_reset_requested` with `target_user_id=<resolved UUID>`, `email_hint=<lowercased email>`, `audit_correlation_id=<fresh UUID>`. Unknown-email branch emits with `target_user_id=None`, `email_hint=<lowercased email>`, `audit_correlation_id=<fresh UUID>`, `actor_user_id=None` (system emit per D-41-10). The `actor_email_snapshot` column stays NULL in both branches because the request is anonymous (no `actor_context_var` set — D-41-08). Both branches emit BEFORE the constant-time sleep so the audit-emit cost is amortised inside the budget.
- **D-44-09 (Email enqueue ONLY in known + active + non-deleted branch):** The audit row is forensic; the actual `PASSWORD_RESET_EMAIL` is only enqueued when the email resolves to a row with `is_active=true AND deleted_at IS NULL`. Owner accounts are eligible (owner can reset their own password). Deactivated/soft-deleted users get the audit row but NO email send — this preserves the anti-oracle (response is identical) without spending Yandex Postbox quota on unrecoverable mailboxes. The "unknown email" branch obviously has no `to_address` to enqueue to.

### Rate limit topology (RESET-01 — RESOLVED)

- **D-44-10 (3 separate Redis fixed-window keys — reuse `auth/rate_limit.py` shape):** Per RESET-01 spec: per-IP 5/15min + per-email 1/min + per-email 5/hour. NEW module `app/modules/auth/reset_rate_limit.py` (mirrors `auth/rate_limit.py:check_login_rate` / `bump_login_rate` shape):
  - Key `ratelimit:password_reset:ip:{ip}` — INCR with TTL=900s, threshold=5.
  - Key `ratelimit:password_reset:email_min:{email_lower}` — INCR with TTL=60s, threshold=1.
  - Key `ratelimit:password_reset:email_hour:{email_lower}` — INCR with TTL=3600s, threshold=5.
- **D-44-11 (Rate-limit hits return the SAME 202 + identical body — NOT 429):** Anti-oracle: a 429 leaks "this email exists AND someone is hammering it" (or "your IP is rate-limited" — both observable). Rate-limit hit short-circuits to the standard 202 envelope WITHOUT bumping any counters further (idempotent re-check). The audit emit fires with a sentinel `audit_correlation_id` and reason captured in a structlog WARN line (`password_reset.rate_limited` event in the structlog stream, NOT in the audit_log table — keeps the public-facing surface anti-oracle while preserving ops visibility). Owner can grep structlog for `password_reset.rate_limited` to triage abuse without exposing the signal in HTTP responses.
- **D-44-12 (IP resolution — use `X-Forwarded-For` first hop, fall back to `request.client.host`):** Matches the existing CSRF + cookie discipline (Phase 6). Helper lives in `app/core/request_meta.py:client_ip_from_request(...)` if it already exists; otherwise a thin inline helper inside `reset_rate_limit.py`. NO trust of arbitrary `X-Real-IP` headers — only `X-Forwarded-For` (Yandex Cloud LB sets this).
- **D-44-13 (Order of checks — IP first, then email):** Three Redis GETs in sequence: IP → email-minute → email-hour. ALL three checked BEFORE the user lookup so an unknown-email rate-limited request matches the timing/audit profile of a known-email rate-limited request (anti-oracle parity). On hit, short-circuit to the 202 + sleep-to-floor path (no INCR after the first hit on that key in the same request, no user lookup, no audit emit in the table — only the structlog WARN).

### `/password-reset/confirm` atomic-consume + revoke-all (RESET-02 — RESOLVED)

- **D-44-14 (Single-SQL atomic consume — `UPDATE … RETURNING` race-tight):**
  ```sql
  UPDATE password_reset_tokens
     SET consumed_at = NOW()
   WHERE token_hash = :hash
     AND purpose = 'password_reset'
     AND consumed_at IS NULL
     AND expires_at > NOW()
   RETURNING id, user_id, audit_correlation_id;
  ```
  Single round-trip. Zero-row return → 410 Gone (replay / expired / unknown — anti-oracle: all three map to the same error code and body, no enumeration). One-row return → continue with password rotate + revoke + audit. Mirrors v1.1 refresh-token rotation atomic-consume + the Phase 43 invitation atomic-consume (`apps/backend/app/modules/users/repository.py:atomic_consume_invitation_token_by_id`).
- **D-44-15 (410 Gone for replay/expired/invalid — generic body):** Per RESET-02 spec: HTTP 410 with `{"error": {"code": "invalid_or_expired_token"}, "data": null, "meta": {}}` envelope. NO distinguishing "replay" vs "expired" vs "never-existed" (defence-in-depth — attacker cannot enumerate which condition failed). Audit emit: `password_reset_completed` is NOT emitted in this branch (only on success); the failure is a structlog WARN line, NOT in `audit_log` (matches Phase 42 `email_send_failed` discipline — only successful state changes get audit rows).
- **D-44-16 (Password rotate + revoke-all + audit emit — single UoW):** On the one-row RETURNING:
  1. `users.password_hash = await hash_password(new_password)` (Argon2id via `app.core.security.hash_password`).
  2. `await invalidate_all_families_for_user(session, user_id=<resolved>, reason='password_reset')` (Phase 43 D-43-26 Protocol slot wired in `app/main.py`).
  3. `audit.emit("password_reset_completed", target_user_id=<resolved>, sessions_revoked_count=<int>, token_id=<token row id>, audit_correlation_id=<from token row>)` — `PasswordResetCompletedPayload` already registered at Phase 41 (`apps/backend/app/core/audit_payloads.py:640-645`).
  4. `await session.commit()` — service owns transaction (D-03 / Phase 12.1 / SVC001 walker scope already covers `app/modules/auth/password_reset_service.py` per D-41-28).
  5. Returns HTTP 200 envelope `{"data": null, "meta": {}}` — NO new login cookies issued (user must re-authenticate via `/auth/login` with the new password — matches OWASP recommendation; no automatic session resumption after reset).
- **D-44-17 (Password complexity reuse — `app.core.security.validate_password_strength` if it exists, else inline 8-char minimum):** Search `app.core.security` for existing validator. If absent, inline `len(new_password) >= 8` minimum (matches v1.0 AUTH-* baseline — RESET-02 does not specify stronger requirements). Argon2id absorbs any practical complexity; the minimum is purely a UX-stage anti-foot-gun. Returns 422 with `{"error": {"code": "weak_password"}}` on failure (deliberate exception to the 410 anti-oracle — weak-password rejection happens BEFORE the atomic-consume so no oracle is leaked; the token stays valid for a second attempt within TTL).

### `/users/invitations/accept` — Phase 44's contribution to USERS-03 / RESET-04 (RESOLVED)

- **D-44-18 (Router lives in `users/router.py`, service in `auth/password_reset_service.py` — cross-module split):** REQUIREMENTS.md RESET-04 path: `POST /api/v1/users/invitations/accept`. The router endpoint sits adjacent to Phase 43's invitation-revoke endpoint in `app/modules/users/router.py`. The service implementation lives in `app/modules/auth/password_reset_service.py:accept_invitation(...)` (NOT in `users/service.py`) because: (a) atomic-consume of `password_reset_tokens` is auth-bedrock surface (SVC001 walker already covers `password_reset_service.py` per D-41-28); (b) issuing the session cookie pair requires `auth/service.issue_tokens` + `app/core/security.issue_session_cookies` — same import space as `auth/service.authenticate`; (c) keeps the users module free of the "set initial password" responsibility (D-43-09 architectural boundary).
- **D-44-19 (Atomic-consume SQL — by `token_hash`, NOT by `id` or by `user_id+purpose`):**
  ```sql
  UPDATE password_reset_tokens
     SET consumed_at = NOW()
   WHERE token_hash = :hash
     AND purpose = 'invitation'
     AND consumed_at IS NULL
     AND expires_at > NOW()
   RETURNING id, user_id, audit_correlation_id;
  ```
  Mirror of D-44-14 with `purpose='invitation'` discriminator. The Phase 43 `revoke_invitation` endpoint operates on token `id` because the owner UI shows it; the user-facing accept-flow operates on `token_hash` because the user only has the raw token from the email.
- **D-44-20 (Pending-user state transition — INSERT-only invariant pre-satisfied at Phase 43):** Phase 43 D-43-13 already ENFORCES "soft-deleted email → INSERT new row" at create-user time (the partial-UNIQUE allows the INSERT path automatically). Phase 44 invitation-accept therefore operates on a `users` row that ALREADY EXISTS in `status='pending_invitation'` state — it never CREATES a new user. Mutation:
  ```sql
  UPDATE users
     SET password_hash = :argon2_hash,
         status = 'active',
         email_verified = TRUE
   WHERE id = :user_id
     AND status = 'pending_invitation'
     AND is_active = TRUE
     AND deleted_at IS NULL
  RETURNING id, email, role, full_name;
  ```
  If 0 rows return (race: user got soft-deleted between token consume and password set), the whole UoW rolls back via raising `InvitationAlreadyAcceptedError` → 409 (rare edge — Phase 43's revoke + soft-delete chain calls `consume_active_invitation_for_user` so this race window is millisecond-scale).
- **D-44-21 (Returns `LoginResponse` envelope with cookie pair):** Same shape as `/auth/login` response. Calls `issue_tokens(session, user)` + `issue_session_cookies(response, …)` (existing Phase 5 helpers). User is logged in immediately upon successful invitation-accept — no second `/auth/login` round-trip needed. This matches the RESET-04 spec ("Returns 200 with login cookie pair").
- **D-44-22 (Audit emit — `user_invitation_accepted` with `accepted_user_id` + `invitation_token_id`):** Per `UserInvitationAcceptedPayload` already registered at Phase 41 + 43 (`apps/backend/app/core/audit_payloads.py:545-549`). Emit kwargs: `audit_correlation_id=<from token row>`, `accepted_user_id=<user_id>`, `invitation_token_id=<token_id>`. Single emit; `password_reset_completed` is NOT emitted on the invitation-accept path (different event, different requirement — RESET-04 vs RESET-02).
- **D-44-23 (`fullName` body field — UPDATE if non-empty, else preserve):** RESET-04 spec accepts `{token, password, fullName}`. The user-row from Phase 43's `insert_user_pending_invitation` already has `full_name` populated from the owner's create-user input. Behaviour:
  - If `fullName` in request is non-empty AND differs from the existing row → UPDATE it in the same UoW as the password set (user took the opportunity to correct the typo the owner made).
  - If `fullName` is empty or missing → leave the existing value untouched.
  This makes the accept-flow self-healing for the common "owner typed Анна-Анна-Б instead of Анна Б" case.

### `PASSWORD_RESET_EMAIL` template content (RESET-03 — RESOLVED)

- **D-44-24 (Template lives in `app/modules/auth/email_templates.py` — already partially scaffolded for `EMAIL_OTP_LOGIN`):** Phase 42 D-42-06 + Phase 44 (this decision) confirm per-domain ownership. Add a second entry to the existing `TEMPLATES: Final[dict[str, EmailTemplate]]` registry: `"PASSWORD_RESET_EMAIL": EmailTemplate(subject=…, html=…, text=…)`. Mirrors the Phase 42 `EMAIL_OTP_LOGIN` shape (`apps/backend/app/modules/auth/email_templates.py:73-91`).
- **D-44-25 (Variables — `{reset_url}`, `{expires_at_human}`; NO `{full_name}` in body):** Anti-oracle defence-in-depth (Phase 42 D-42-23 lineage — stolen-mailbox replay cannot enumerate user identity). The reset email contains the reset URL + expiry timestamp + standard helpdesk footer; it does NOT greet by name (matches Phase 42 `EMAIL_OTP_LOGIN` discipline — only `{otp_code}` is interpolated). Phase 44 ships the Russian copy + Jinja2 sandboxed templates per D-42-05.
- **D-44-26 (Subject = locked `Final[str]` — no interpolation):** Subject: `"Восстановление пароля Sportzal"` (locked, no `{full_name}` or `{otp_code}`-style fields). Matches Phase 42 D-42-23 lock. Owner sign-off enumerated as `D-44-OWNER-COPY-LOCK` at plan SUMMARY time (lineage: D-27-OWNER-COPY-LOCK from v1.3).
- **D-44-27 (Render at enqueue time, transport pre-rendered envelope — D-42-07 carried forward):** `app/modules/auth/password_reset_service.py:request_password_reset(...)` calls a local `_render_password_reset_email(reset_url, expires_at)` helper that imports `app.modules.auth.email_templates`, renders subject/html/text into an `EmailEnvelope` (`app/integrations/email/types.py`), passes the envelope as kwargs to `get_email_dispatcher()(template_id='PASSWORD_RESET_EMAIL', to=email, audit_correlation_id=..., **envelope_fields)`. The ARQ `dispatch_email` task NEVER imports `app.modules.auth.*` — import-linter contract 3 (`integrations ⊥ modules`) holds.
- **D-44-28 (URL construction — `Settings.frontend_base_url + '/auth/password-reset#token=' + raw`):** Mirrors Phase 43 D-43-14's `_build_invitation_url`. Frontend path: `/auth/password-reset`. Fragment carries the raw token. Owner-only `?include_reset_link=true` query param is **NOT** added in v1.6 (deferred to v1.7 if email transport reliability becomes an operational pain point — the invitation flow has the escape hatch because operator-onboarding is owner-supervised; password-reset is self-service so a copy-link escape hatch defeats the anti-oracle).

### `tests/integration/auth/test_password_reset_no_oracle.py` ungating (RESET-06 — RESOLVED)

- **D-44-29 (Remove `@pytest.mark.xfail(strict=True)` in the same commit that ships RESET-01):** D-41-17 explicit handoff. The test file already exists with the 4-case identical-202 + identical-body + bounded-timing-within-100ms contract. Phase 44 plan that lands the `/password-reset/request` endpoint MUST include the marker-removal in the same atomic commit (per D-41-17 `strict=True` discipline — never let the suite drift). Failure mode: if RESET-01 ships without satisfying the contract, CI breaks loudly on the xfail-now-fails-as-pass invariant.
- **D-44-30 (Test extends with `password_reset_requested` audit-row assertion):** Phase 41's existing 4-case test asserts identical 202 + identical body + bounded timing. Phase 44 extends the same test (or sibling `test_password_reset_request_emits_audit.py` if file diff is cleaner) with: "in BOTH known-email and unknown-email branches, exactly one `password_reset_requested` row exists in `audit_log` with the correct `target_user_id` shape (UUID vs NULL)" — closes the audit half of RESET-01 that D-41-10 deferred.

### Cleanup cron (D-41-06 — RESOLVED)

- **D-44-31 (Daily ARQ job `cleanup_expired_password_reset_tokens`):** New file `app/workers/scheduled/cleanup_password_reset_tokens.py` (mirrors `app/workers/scheduled/send_expiring_notifications.py` shape per Phase 41 plan 09 referenced precedent — ARQ cron, not pure asyncio.create_task). Body:
  ```sql
  DELETE FROM password_reset_tokens
   WHERE expires_at < NOW() - INTERVAL '30 days';
  ```
  Returns deleted-row count for structlog observability. No audit emit (housekeeping, not a state change observers care about — matches v1.4 `cleanup_expired_otp_attempts` precedent if it exists; otherwise establishes the precedent here).
- **D-44-32 (Schedule = 03:30 Europe/Moscow, daily):** Off-peak (well away from 06:15 expiring-notifications and 06:35 booking-reminders crons). Cron expression in ARQ settings: `CronJob('cleanup_password_reset_tokens', hour=3, minute=30, run_at_startup=False)`. Retention window = **30 days** (per D-41-06). Long enough for forensic queries ("did we send a reset for user X 3 weeks ago?") to walk `audit_log` + `password_reset_tokens` together; bounded enough to keep the table small (5 tokens/op × 2 ops × 365 days × 30-day retention = ~30 rows steady-state for a 1-gym tenant).

### Eager-import discipline (REG-29-04 — preventative)

- **D-44-33 (PasswordResetToken already eager-imported at Phase 41 plan 09):** `app/workers/__init__.py` already imports `app.modules.auth.password_reset_token_model.PasswordResetToken` (per Phase 41 plan 09 `tests/unit/test_workers_eager_import.py` mention). Phase 44 ships ZERO new ORM tables → zero eager-import amendments. The cleanup cron operates on the existing model. `tests/unit/test_workers_eager_import.py` requires no changes.

### RBAC + CSRF + audit traceability

- **D-44-34 (Anonymous endpoints — no RBAC, no CSRF):** `/auth/password-reset/request` and `/auth/password-reset/confirm` and `/users/invitations/accept` are all UNAUTHENTICATED — they're consumed by users who don't have a session yet (either they forgot their password or they're a freshly invited operator). NO `Depends(require_authenticated())`, NO `Depends(verify_csrf)`, NO `Depends(require_permission(...))`. Matches the `/auth/login` discipline (Phase 5 — also unauthenticated, also has rate limit instead of CSRF). The `/users/invitations/{token_id}/revoke` endpoint IS authenticated + RBAC + CSRF — that's owner-only and already landed at Phase 43 (D-43-19).
- **D-44-35 (Audit emits use `actor_user_id=None` — system emits per D-41-10):** All three Phase 44 anonymous endpoints emit audit rows with `actor_user_id=None` (no `ActorContextMiddleware`-set ContextVar). `actor_email_snapshot` stays NULL. The `target_user_id` field on the payload carries the affected user's UUID where applicable (or NULL for the unknown-email branch of `/password-reset/request` per D-41-10).

### Test surface

- **D-44-36 (Test files):**
  - `tests/integration/auth/test_password_reset_no_oracle.py` — Phase 41 file; Phase 44 removes the xfail-strict marker + adds the audit-row assertion extension (D-44-30).
  - `tests/integration/auth/test_password_reset_confirm.py` — NEW. Happy path (atomic consume + password set + sessions revoked + audit emit + new login works), replay rejection (410 + identical body), expired-token rejection (410 + identical body), weak-password rejection (422 + token still valid for retry).
  - `tests/integration/auth/test_password_reset_rate_limit.py` — NEW. Per-IP 5/15min, per-email 1/min, per-email 5/hour. Each hit returns 202 + identical body (not 429); structlog `password_reset.rate_limited` event captured via caplog.
  - `tests/integration/auth/test_invitation_accept.py` — NEW. Happy path (atomic consume + password set + status flip + email_verified flip + cookie pair issued + audit emit), replay rejection (410 + identical body), expired-invitation rejection, full_name update branch, race-with-soft-delete rejection (409).
  - `tests/integration/auth/test_invitation_accept_insert_only.py` — NEW. Soft-deleted email → re-invite → accept lands as NEW user_id (Pitfall 4 invite-accept-INSERT-only invariant verified at the accept point, not just create-user point per Phase 43 D-43-13 + D-41-07).
  - `tests/unit/auth/test_password_reset_email_render.py` — NEW. Jinja2 template renders deterministic snapshot for fixed `reset_url` + `expires_at_human` inputs. Pattern mirrors Phase 43 `test_email_template_render.py` (D-43-33).
  - `tests/unit/test_locked_email_templates_ast.py` — EXTEND with one new real-callsite assertion: `auth.password_reset_service.request_password_reset` references `template_id='PASSWORD_RESET_EMAIL'` literal. Pattern mirrors Phase 43 D-43-33 (D-42-27 lineage).
  - `tests/integration/workers/test_cleanup_password_reset_tokens.py` — NEW. Cron deletes rows where `expires_at < now() - 30 days`; rows within retention window preserved.
- **D-44-37 (Test discipline — Phase 42 CR-01 + Phase 43 D-43-34 carried forward):** Real Postgres via SAVEPOINT per-test; real `audit.emit()` exercised in integration tests; no kwargs nesting; no monkeypatching the ContextVar; sandbox email client only (no real Yandex Postbox in CI); deterministic-input snapshot files for template rendering.

### Plan packaging (planner sizing hints, not locks)

- **D-44-38 (Wave structure — planner refines):** Expected wave shape:
  - **Wave 1** (parallel — independent files):
    - 44-01 `app/modules/auth/constants.py` (NEW file, single constant `PASSWORD_RESET_TOKEN_TTL`) + `app/modules/auth/reset_rate_limit.py` (NEW, 3-key fixed-window) — 1 hour.
    - 44-02 `app/modules/auth/email_templates.py` — add `PASSWORD_RESET_EMAIL` entry + `_render_password_reset_email` helper — 2 hours (Russian copy + sandboxed Jinja2 mirroring `EMAIL_OTP_LOGIN`).
    - 44-03 `app/modules/auth/password_reset_service.py` skeleton with `request_password_reset`, `confirm_password_reset`, `accept_invitation` stubs (no body) + `_atomic_consume_token(session, *, raw_token, purpose)` helper — 2 hours.
  - **Wave 2** (blocked on Wave 1):
    - 44-04 `request_password_reset` body — anti-oracle envelope + 3-rate-limit checks + constant-time floor + dual-branch audit emit + email enqueue — 4 hours.
    - 44-05 `confirm_password_reset` body — atomic-consume + Argon2 rehash + revoke-all + audit emit + 410-on-failure — 3 hours.
    - 44-06 `accept_invitation` body — atomic-consume + user-row UPDATE + email_verified=true + issue_session_cookies + audit emit — 3 hours.
    - 44-07 Router endpoints — `POST /auth/password-reset/request`, `POST /auth/password-reset/confirm` in `auth/router.py`; `POST /users/invitations/accept` in `users/router.py` — 2 hours.
  - **Wave 3** (blocked on Wave 2):
    - 44-08 Ungate `test_password_reset_no_oracle.py` (remove xfail) + extend with audit-row assertion — 1 hour. [BLOCKING — CI gate per D-41-17.]
    - 44-09 `tests/integration/auth/test_password_reset_confirm.py` + `test_password_reset_rate_limit.py` — 3 hours.
    - 44-10 `tests/integration/auth/test_invitation_accept.py` + `test_invitation_accept_insert_only.py` — 3 hours.
    - 44-11 `tests/unit/auth/test_password_reset_email_render.py` + extend `tests/unit/test_locked_email_templates_ast.py` — 1 hour.
  - **Wave 4** (blocked on Wave 3):
    - 44-12 ARQ cron `app/workers/scheduled/cleanup_password_reset_tokens.py` + settings registration + cron entry — 2 hours.
    - 44-13 `tests/integration/workers/test_cleanup_password_reset_tokens.py` — 1 hour.
    - 44-14 Owner sign-off enumeration update (D-44-OWNER-COPY-LOCK) — 30 min.
  - Total: ~14 plans across 4 waves. Planner refines based on file-overlap minimisation (Phase 42 + 43 precedent: parallel waves require zero `files_modified` overlap pairwise).
- **D-44-39 (Anti-oracle test ungating is a [BLOCKING] checkpoint on plan 44-08):** Per D-41-17 strict-xfail discipline. The plan that ungates MUST sequence after RESET-01 implementation lands AND before milestone-close. If ungating happens too early (before request handler exists), CI breaks. If too late (after handler exists but suite still xfails), the marker becomes stale. Plan 44-08 enforces the atomic land.
- **D-44-40 (No new migration — no round-trip checkpoint needed):** Phase 44 ships ZERO Alembic migrations (D-44-02 confirms no `password_changed_at` column). The migration-discipline `[BLOCKING] alembic round-trip` checkpoint (Phase 42 4-15/4-16, Phase 43 43-01 D-43-36) does NOT apply. Plan 44-08 is the equivalent blocking checkpoint for this phase (anti-oracle gate).

### Claude's Discretion

- Exact Russian wording of `PASSWORD_RESET_EMAIL` subject/body/text (owner-copy-lock — drafted by planner, owner-signed-off at plan SUMMARY as `D-44-OWNER-COPY-LOCK`).
- Whether `PASSWORD_RESET_TOKEN_TTL` lives in `app/modules/auth/constants.py` (new file) vs `app/modules/auth/__init__.py` vs as a module-level `Final` in `password_reset_service.py` itself (recommend: new `constants.py` file — mirrors `users/constants.py` shape from Phase 43 D-43-12).
- Internal helper function naming inside `password_reset_service.py` (`_render_password_reset_email` vs `_make_password_reset_envelope` etc.).
- Whether the rate-limit short-circuit emits a sentinel `audit_correlation_id` for forensic linking (recommend: yes — `uuid4()` so structlog WARN line can be grep-correlated to the request span).
- Whether to add an `audit.emit("invitation_accepted_with_full_name_correction", ...)` event for the full_name-update branch (recommend: NO — overspecified; the `user_invitation_accepted` payload covers the lifecycle event, and the diff is recoverable from `audit_log.actor_email_snapshot` join + `users.full_name` history if v1.8 read-API wants it).
- Whether `request_password_reset` short-circuits the constant-time sleep when rate-limited (recommend: NO — keep the 500ms floor on rate-limit-hit paths too, otherwise the floor itself becomes an oracle for "you are rate-limited" via faster response).
- Migration docstring wording (N/A this phase — no migrations).
- Whether `accept_invitation` issues fresh CSRF tokens alongside the session cookie pair (recommend: yes — `issue_session_cookies` already handles this in Phase 5; mirrors `/auth/login`).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 44 source-of-truth specs (locked)
- `.planning/REQUIREMENTS.md` §§ RESET-01..06 — locked requirements; non-negotiable acceptance criteria.
- `.planning/ROADMAP.md` §§ Phase 44 — goal + 5 success criteria + dependency declaration.
- `.planning/PROJECT.md` — current state (v1.6 milestone, Phase 43 complete 2026-05-19; 11 v1.6 LOCKED_AUDIT_EVENTS pairs registered; `PASSWORD_RESET_EMAIL` and `USER_INVITATION_EMAIL` identifiers active in `LOCKED_EMAIL_TEMPLATES`).

### Phase 41 dependency surface (mandatory — Phase 44 cannot ship without these)
- `.planning/phases/41-infra-bedrock-anti-oracle-scaffold/41-CONTEXT.md` — D-41-04 (unified `password_reset_tokens` table with `purpose` column), D-41-05 (partial-UNIQUE on `(user_id, purpose) WHERE consumed_at IS NULL`), D-41-06 (cleanup cron Phase 44), D-41-07 (INSERT-only invariant Phase 43/44), D-41-08 (ContextVar — Phase 44 anonymous paths have NULL actor), D-41-09 (`actor_email_snapshot` semantics), D-41-10 (system emits with `actor_user_id=None`), D-41-12 (`PASSWORD_RESET_EMAIL` + `USER_INVITATION_EMAIL` identifiers pre-locked), D-41-17 (RESET-06 xfail-strict RED-then-keep-RED-until-Phase-44 — ungating discipline D-44-29), D-41-25 (`UserSessionInvalidator` Protocol slot — Phase 44 RESET-02 consumes), D-41-28 (SVC001 walker scope includes `password_reset_service.py`).
- `apps/backend/app/modules/auth/password_reset_token_model.py` — `PasswordResetToken` ORM (Phase 41 plan 09); Phase 44 consumes via `_atomic_consume_token` helper.
- `apps/backend/alembic/versions/0025_password_reset_tokens.py` — unified table migration; Phase 44 ships no new migration.
- `apps/backend/app/core/dependencies.py` (lines 608-744) — `EmailDispatcher` + `UserSessionInvalidator` Protocol slot declarations + accessors; Phase 44 consumes both via `get_email_dispatcher()` and `get_user_session_invalidator()`.
- `apps/backend/app/core/audit_payloads.py:608-694` — pre-registered `PasswordResetRequestedPayload`, `PasswordResetCompletedPayload`, `UserInvitationAcceptedPayload`, `RefreshFailedPayload`; Phase 44 consumes verbatim (zero schema additions).
- `apps/backend/app/core/audit.py:264-300` — `LOCKED_EMAIL_TEMPLATES` frozenset with `PASSWORD_RESET_EMAIL` already at line 271; Phase 44 ships the content.
- `apps/backend/tests/integration/auth/test_password_reset_no_oracle.py` — Phase 41 xfail-strict 4-case anti-oracle template; Phase 44 ungates + extends.

### Phase 42 dependency surface (LOCKED — Phase 44 consumes the EmailDispatcher slot)
- `.planning/phases/42-email-transport-layer-email-otp-fallback/42-CONTEXT.md` — D-42-02 (`aioboto3` SES-V2 client), D-42-05 (Jinja2 SandboxedEnvironment + autoescape rules), D-42-06 (per-domain templates), D-42-07 (render at enqueue, transport envelope), D-42-13 (ARQ task config — Phase 44 inherits via dispatcher slot), D-42-16 (`EmailEnvelope` shape), D-42-23 (anti-oracle subject + only-essential-variables policy — Phase 44 D-44-25/26 carry forward).
- `apps/backend/app/integrations/email/types.py` — `EmailEnvelope` frozen dataclass; Phase 44 constructs at enqueue time.
- `apps/backend/app/integrations/email/client.py` — `aioboto3` client + `SandboxEmailClient`; Phase 44 tests against the sandbox.
- `apps/backend/app/modules/auth/email_templates.py` — Phase 42 plan 05 reference shape (`EMAIL_OTP_LOGIN`); Phase 44 adds `PASSWORD_RESET_EMAIL` adjacent.
- `apps/backend/app/workers/dispatch_email.py` — ARQ task body; Phase 44 enqueues into it via `get_email_dispatcher()`.
- `apps/backend/app/main.py:create_app()` — Phase 42 wired `register_email_dispatcher`; Phase 43 wired `register_user_session_invalidator`; Phase 44 adds NO new registrations.

### Phase 43 dependency surface (LOCKED — Phase 44 inherits invitation-side scaffolding)
- `.planning/phases/43-multi-user-admin-module/43-CONTEXT.md` — D-43-12 (`INVITATION_TOKEN_TTL=7d` in `users/constants.py`), D-43-13 (4-branch idempotent create-user — Phase 44's accept-flow operates on `status='pending_invitation'` rows), D-43-14 (`?include_invite_link=true` + `_build_invitation_url` URL fragment shape — Phase 44 mirrors for password-reset URL but withouth the include-link query param per D-44-28), D-43-19 (invitation-revoke endpoint already shipped — Phase 44 ships its INTEGRATION tests if not already covered), D-43-22..25 (`USER_INVITATION_EMAIL` template shape — Phase 44 mirrors for `PASSWORD_RESET_EMAIL`), D-43-26/27 (`UserSessionInvalidator` Protocol slot wired in `app/main.py` — Phase 44 RESET-02 calls `get_user_session_invalidator()(... reason='password_reset')`).
- `apps/backend/app/modules/users/service.py` — Phase 43 `create_user` puts users in `status='pending_invitation'` with `password_hash=NULL` + `email_verified=false`; Phase 44 `accept_invitation` flips all three.
- `apps/backend/app/modules/users/repository.py:42` — `_hash_token` helper (sha256); Phase 44 reuses (or duplicates the 3-line pattern in `password_reset_service.py`).
- `apps/backend/app/modules/users/router.py` — Phase 43 owns the users router; Phase 44 adds the `POST /api/v1/users/invitations/accept` endpoint here (D-44-18).
- `apps/backend/app/modules/users/constants.py:INVITATION_TOKEN_TTL` — 7-day TTL; Phase 44 adds the password-reset 1-hour parallel.

### v1.6 research (HIGH confidence — must read for Phase 44 trade-off rationale)
- `.planning/research/PITFALLS.md` §§ Pitfall 1 (anti-oracle reset-flow — D-44-06/07/08), Pitfall 4 (invite-accept INSERT-only — D-44-20), Pitfall 6 (locked Russian copy — D-44-24/26), Pitfall 11 (token TTL — D-44-05).
- `.planning/research/FEATURES.md` — Anti-features: plaintext password email is BANNED (Phase 44 never returns the password; the user types their own); single-use-token enforcement at SQL layer is REQUIRED (D-44-14/19); rate-limit-as-anti-oracle (D-44-11).
- `.planning/research/SUMMARY.md` — Open conflict #2 (reset-token storage) RESOLVED via D-41-04 + D-44-01 (this CONTEXT confirms the resolution).
- `.planning/research/ARCHITECTURE.md` — modular monolith; Phase 44 reuses Protocol slot infrastructure, adds NO new slots.
- `.planning/research/STACK.md` — Yandex Cloud Postbox primary email transport; sandbox in CI.

### v1.0–v1.5 codebase landmarks (Phase 44 extends or mirrors)
- `apps/backend/app/modules/auth/service.py:106-200` — `authenticate(...)` reference impl for: rate-limit-before-Argon2, anti-oracle response timing, structlog ops events — Phase 44 D-44-07/10/13 mirrors.
- `apps/backend/app/modules/auth/service.py:506-645` — `revoke_session` / `revoke_all_sessions` + Phase 43 D-43-26 `invalidate_all_families_for_user` Protocol slot impl — Phase 44 RESET-02 calls via slot.
- `apps/backend/app/modules/auth/service.py:333+` — `rotate_refresh` hot path with `is_active+deleted_at` join (Phase 43 D-43-20) — Phase 44 inherits the anti-oracle session-invalidation guarantee.
- `apps/backend/app/modules/auth/rate_limit.py` — `check_login_rate` / `bump_login_rate` reference shape for Phase 44's `reset_rate_limit.py` (D-44-10).
- `apps/backend/app/modules/auth/router.py:72-95` — `/auth/login` endpoint shape (unauthenticated, no CSRF, rate-limit-then-Argon2); Phase 44's `/password-reset/request` and `/password-reset/confirm` mirror the unauthenticated + cookie-issuing pattern.
- `apps/backend/app/modules/users/service.py` — Phase 43 `create_user` + `revoke_invitation` reference shape; Phase 44's `accept_invitation` mirrors the atomic-consume + audit-emit + service-owns-commit pattern.
- `apps/backend/app/core/security.py` — `hash_password`, `verify_password`, `issue_session_cookies`, `clear_session_cookies`; Phase 44 RESET-02 + RESET-04 consume all four.
- `apps/backend/app/core/schemas.py:envelope,ResponseEnvelope` — standard response envelope; Phase 44 returns `envelope(None)` for 202 + `envelope(LoginResponse)` for invitation-accept.
- `apps/backend/app/core/exceptions.py` — `AppError` family; Phase 44 adds `InvalidOrExpiredTokenError` (410), `WeakPasswordError` (422), `InvitationAlreadyAcceptedError` (409 — race-loss) to `app/modules/auth/exceptions.py`.
- `apps/backend/app/workers/scheduled/` — existing 06:15 / 06:35 cron precedent; Phase 44's `cleanup_password_reset_tokens.py` mirrors the cron-shape (D-44-31).
- `apps/backend/tests/integration/auth/test_otp_email_anti_oracle.py` — Phase 42 mirror of the Phase 41 4-case discipline (AUTH-EM-04); Phase 44 RESET-01 anti-oracle test follows the same fixture seeding + bounded-timing assertion pattern.
- `apps/backend/tests/unit/test_locked_email_templates_ast.py` — AST walker; Phase 44 extends with `PASSWORD_RESET_EMAIL` real-callsite assertion (D-44-36).
- `apps/backend/tests/integration/users/test_users_invitation_flow.py` (Phase 43) — invitation-revoke end-to-end; Phase 44 extends with the accept-side closing the loop.

### Verification + governance lineage
- `.planning/milestones/v1.5-VERIFICATION-LOG.md` — REG-29-01/03/04 regressions + DEFER-40-01 runbook lesson; Phase 44 preventative discipline derives.
- `.planning/phases/42-email-transport-layer-email-otp-fallback/42-VERIFICATION.md` — CR-01..04 + WR hygiene findings; Phase 44 inherits (real audit emit, no kwargs nesting, atomic Redis ops where relevant).
- `.planning/phases/43-multi-user-admin-module/43-VERIFICATION.md` — Phase 43 verification trail; Phase 44 inherits the test-shape lessons.

### Key D-XX-YY decision lineage carried forward
- **D-18 / D-19** (v1.0): per-email rate limit BEFORE Argon2; Phase 44 D-44-13 carries to `/password-reset/request` ordering.
- **D-20-9** (v1.2): `/checkin` anti-oracle DM equality; Phase 44 D-44-06/14/15 mirrors at HTTP body equality.
- **D-27-OWNER-COPY-LOCK** (v1.3): per-template owner sign-off enumerated by constant name; Phase 44 ships as `D-44-OWNER-COPY-LOCK` at plan SUMMARY.
- **D-39-02** (v1.5): per-domain template ownership; Phase 44 D-44-24 places `PASSWORD_RESET_EMAIL` in `app/modules/auth/email_templates.py`.
- **D-41-04**: unified `password_reset_tokens` table; Phase 44 confirms via D-44-01 + D-44-02.
- **D-41-17**: RESET-06 xfail-strict; Phase 44 D-44-29 ungates.
- **D-42-23**: anti-oracle template content (only essential variables); Phase 44 D-44-25/26 mirrors.
- **D-43-13**: 4-branch idempotent invitation create; Phase 44 D-44-20 operates on the `status='pending_invitation'` post-state.
- **D-43-22..25**: `USER_INVITATION_EMAIL` shape + render path; Phase 44 D-44-24/27 mirrors.
- **REG-29-04**: eager-import discipline; Phase 44 D-44-33 confirms zero amendments (PasswordResetToken already imported).
- **Phase 12.1 SVC001 + commit-gate**: services own `session.commit()`; Phase 44 D-44-16 service-layer carries it (SVC001 walker scope already covers `password_reset_service.py` via D-41-28).
- **Phase 42 CR-01 audit emit shape**: flat kwargs (NOT nested under `payload=`); Phase 44 audit.emit calls inherit (D-44-08/16/22).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`apps/backend/app/modules/auth/password_reset_token_model.py`** — `PasswordResetToken` ORM with `__table_args__` declaring partial-UNIQUE + hash-lookup index. Phase 44 queries via `token_hash` lookup + `UPDATE … RETURNING` atomic consume.
- **`apps/backend/app/modules/auth/password_reset_service.py`** — 9-line placeholder (Phase 41 SVC001 anchor). Phase 44 fills the body: `request_password_reset`, `confirm_password_reset`, `accept_invitation`, `_atomic_consume_token`, `_render_password_reset_email`.
- **`apps/backend/app/modules/auth/email_templates.py`** — `TEMPLATES: Final[dict[str, EmailTemplate]]` registry already exists with `EMAIL_OTP_LOGIN`. Phase 44 appends `PASSWORD_RESET_EMAIL` adjacent. Sandboxed Jinja2 environments (`_ENV`, `_ENV_TEXT`) reusable as module-level singletons.
- **`apps/backend/app/modules/auth/rate_limit.py`** — `check_login_rate` / `bump_login_rate` shape; Phase 44's `reset_rate_limit.py` mirrors (3 keys instead of 1).
- **`apps/backend/app/modules/auth/service.py:authenticate`** — anti-oracle login reference: rate-limit BEFORE Argon2 verify (D-18), constant-time-equivalent failure paths, structlog ops events. Phase 44 RESET-01 mirrors with a hard ≥500ms floor.
- **`apps/backend/app/modules/users/repository.py:_hash_token`** — sha256(raw) helper (Phase 43). Phase 44 reuses via duplication (3 lines — not worth a shared util at this scale).
- **`apps/backend/app/modules/users/repository.py:atomic_consume_invitation_token_by_id`** — invitation-revoke atomic-consume reference. Phase 44's `_atomic_consume_token` parameterises on `purpose` + lookup-by-hash.
- **`apps/backend/app/modules/users/router.py`** — Phase 43 owns the users router. Phase 44 adds the `POST /invitations/accept` endpoint here (D-44-18); imports `accept_invitation` from `auth.password_reset_service` (cross-module import — analogous to `users/router.py` already calling `users/service.py`).
- **`apps/backend/app/core/security.py:hash_password`** — Argon2id wrapper via `asyncio.to_thread`. Phase 44 RESET-02 + RESET-04 call directly.
- **`apps/backend/app/core/security.py:issue_session_cookies`** — Phase 5 cookie issuance helper. Phase 44 RESET-04 calls on invitation-accept.
- **`apps/backend/app/modules/auth/service.py:issue_tokens`** — Phase 5 access+refresh token pair. Phase 44 RESET-04 calls.
- **`apps/backend/app/core/audit.py:audit.emit`** — standard audit emit. Phase 44 calls with flat kwargs per Phase 42 CR-01.
- **`apps/backend/app/core/dependencies.py:get_email_dispatcher,get_user_session_invalidator`** — Protocol slot accessors; Phase 44 calls both.
- **`apps/backend/app/integrations/email/types.py:EmailEnvelope`** — frozen dataclass; Phase 44 constructs at enqueue time.

### Established Patterns

- **Service owns transaction (D-03 / Phase 12.1 lineage):** Repository / atomic-consume helpers emit NO `commit()`/`flush()`; service emits `audit.emit` co-transactionally, `await session.flush()` to surface IntegrityErrors before route exit, `await session.commit()` at the route boundary. SVC001 AST walker (Phase 41 D-41-28) enforces — `password_reset_service.py` is already in scope.
- **Anti-oracle response equality (D-20-9 / RESET-06 / D-44-06/14/15):** Identical body + bounded timing across success/failure modes. `/password-reset/request` returns the same 202+body for all 4 cases including rate-limit hits (D-44-11). `/password-reset/confirm` returns the same 410+body for replay/expired/invalid.
- **Constant-time floor via `time.perf_counter()` + `asyncio.sleep`:** Phase 44 D-44-07 establishes the precedent at 500ms. Pattern is portable to future anti-oracle endpoints (v1.7+ if a "request password reset by username" surface gets added).
- **Atomic-consume via `UPDATE … RETURNING` (D-41-04 / Phase 43 D-43-19):** Single round-trip, race-tight, zero application-layer state machine. Phase 44 D-44-14/19 carries to both password-reset and invitation-accept.
- **Per-domain template ownership (D-39-02 / D-42-06 / D-43-22):** Templates next to owning module. Phase 44 D-44-24 places `PASSWORD_RESET_EMAIL` in `app/modules/auth/email_templates.py` alongside `EMAIL_OTP_LOGIN`.
- **Owner-copy-lock (D-27 / D-43-OWNER-COPY-LOCK):** Russian email content enumerated by constant name in plan SUMMARY; owner signs off. Phase 44 ships as `D-44-OWNER-COPY-LOCK`.
- **Rate-limit BEFORE expensive verify (D-18):** Phase 44 D-44-13 checks Redis BEFORE user lookup so anti-oracle holds for unknown-email rate-limited paths too.
- **Locked email-template AST gate (Phase 41 D-41-11):** Phase 44 D-44-36 extends `test_locked_email_templates_ast.py` with a real-callsite assertion for `template_id='PASSWORD_RESET_EMAIL'`.
- **ARQ cron one-shot via `app/workers/scheduled/<name>.py`:** Phase 44 D-44-31 follows the existing 06:15/06:35 cron precedent for 03:30 daily cleanup.

### Integration Points

- **`app/main.py:create_app()`** — NO new Protocol-slot registrations in Phase 44 (D-44-33). `EmailDispatcher` (Phase 42) and `UserSessionInvalidator` (Phase 43) are already registered; Phase 44 only CONSUMES via `get_*` accessors.
- **`app/main.py:include_router`** — NO new router include. `auth.router` already included; Phase 44 adds endpoints to it. `users.router` already included; Phase 44 adds the invitation-accept endpoint there.
- **`app/modules/auth/router.py`** — Phase 44 adds `POST /password-reset/request` + `POST /password-reset/confirm` here (unauthenticated, no CSRF dep, rate-limit handled inside the service).
- **`app/modules/users/router.py`** — Phase 44 adds `POST /invitations/accept` here (unauthenticated, no CSRF dep, imports service from `auth/password_reset_service`).
- **`app/modules/auth/email_templates.py`** — Phase 44 appends `PASSWORD_RESET_EMAIL` to `TEMPLATES` dict.
- **`app/core/audit_payloads.py`** — NO additions (Phase 41 + 43 pre-registered all 4 Phase-44-relevant payloads).
- **`tests/unit/test_locked_email_templates_ast.py`** — Phase 44 extends with one new real-callsite assertion (mirrors Phase 43 plan 13 + Phase 42 plan 11 pattern).
- **`tests/integration/auth/test_password_reset_no_oracle.py`** — Phase 44 removes xfail-strict marker + extends with audit-row assertion (D-44-29/30) — **[BLOCKING]** checkpoint per D-41-17.
- **`app/workers/scheduled/`** — Phase 44 adds `cleanup_password_reset_tokens.py`.
- **`apps/admin-web/`** — NO touch in Phase 44. v2.0 design-team handoff (per Phase 43 D-43-XX precedent — backend-only milestone).
- **`packages/api-client/`** — OpenAPI drift gate at Phase 46 HANDOFF-03 picks up the 3 new routes; Phase 44 does NOT regenerate `openapi.json` (drift gate refreshes only at handoff per v1.4 lesson).

</code_context>

<specifics>
## Specific Ideas

- **DB-table token storage (D-44-01)** — recommended default chosen because Phase 41 D-41-04 already shipped the table + ORM + partial-UNIQUE + hash-lookup index; itsdangerous-stateless would require a new `password_changed_at` column AND a separate revocation mechanism (signed-payload TTL only — no operator-triggered revoke surface).
- **No `password_changed_at` column (D-44-02)** — recommended default because the atomic-consume marker (`password_reset_tokens.consumed_at`) + `password_reset_completed` audit row's `created_at` cover the forensic need. REQUIREMENTS.md text is superseded by the D-41-04 lock; codebase + Phase-41 decision win.
- **32-byte `secrets.token_urlsafe(32)` (D-44-03)** — recommended default because 256 bits of entropy is the v1.1 refresh-token precedent + the OWASP 2025 floor; sha256-hashed at rest defeats DB exfiltration of active links.
- **500ms constant-time floor (D-44-07)** — recommended default because the cold-path work (rate-limit + lookup + insert + audit + enqueue) is reliably <100ms in production-like conditions; the Phase 41 test's 100ms tolerance window admits 500ms comfortably; raising the floor to 750ms would noticeably affect the UX (a slow-feeling button click for legitimate users) without adding meaningful timing-oracle protection.
- **Rate-limit hit returns 202 + identical body, not 429 (D-44-11)** — recommended default because a 429 leaks "this email exists AND someone is hammering it"; the structlog WARN line preserves ops visibility without leaking via HTTP.
- **PASSWORD_RESET_EMAIL contains NO `{full_name}` (D-44-25)** — recommended default because the Phase 42 `EMAIL_OTP_LOGIN` precedent (D-42-23) is the anti-oracle template-content discipline; the reset email is functionally identical to the OTP email in threat model (stolen-mailbox replay scenario).
- **NO `?include_reset_link=true` escape hatch (D-44-28)** — recommended default because password-reset is self-service (unlike invitation, which is owner-supervised at Phase 43 D-43-14); a copy-link escape hatch defeats the anti-oracle (owner can enumerate "is this email in our system?" by attempting a reset with the link visible in the response).
- **Invitation-accept service in `auth/password_reset_service.py` (D-44-18)** — recommended default because the atomic-consume SQL is auth-bedrock (already in SVC001 walker scope per D-41-28); the router endpoint is in `users/router.py` because that's where the operator-onboarding surface naturally clusters from an API consumer's POV (URL grouping under `/users/invitations/...`).
- **No `password_changed_at` column AND no Alembic migration (D-44-02 + D-44-40)** — Phase 44 ships ZERO schema changes. The migration round-trip [BLOCKING] checkpoint (Phase 42 4-15/4-16 precedent) is replaced by the anti-oracle xfail-ungate [BLOCKING] checkpoint on plan 44-08 (D-44-39).
- **30-day retention for `password_reset_tokens` (D-44-32)** — recommended default because Phase 41 D-41-06 specified it; the bounded table size is trivial for a 1-gym tenant (steady-state ~30 rows), so the 30-day window is generous enough to admit a "did we send a reset 3 weeks ago?" forensic query without blowing storage.

</specifics>

<deferred>
## Deferred Ideas

- **Owner administrative-override password reset** (force-set another user's password without their email control) — **v1.7**. Operationally the revoke + re-invite path covers the case ("operator lost mailbox access"); explicit admin-override would create a new audit surface (`password_admin_overridden` event) and a new abuse vector (owner compromise → full takeover of all operators).
- **Multi-channel reset** (SMS / Telegram-DM reset tokens) — **v1.7+**. v1.6 is email-only; if Yandex Postbox circuit-open becomes a regular failure mode, Telegram-DM reset is the natural fallback (Telegram bot already exists, can reuse the deep-link pattern).
- **Self-service email change** (`PATCH /api/v1/auth/me` with new-email-verify round-trip) — **v1.7+**. Currently the owner changes operator email via revoke + re-invite (forces email-control proof on the new address).
- **Email re-verification ladder** (re-send verification, owner-triggered re-verify) — **v1.7**. Phase 43 D-43-01 already deferred this.
- **`?include_reset_link=true` escape hatch on `/password-reset/request`** — **v1.7+ IF email transport reliability becomes operational pain**. Currently rejected per D-44-28 (anti-oracle preservation outweighs the operational hedge for self-service flows; the invitation flow keeps its escape hatch because it's owner-supervised).
- **Forensic audit-read API** ("show all reset attempts for user X" / "show all reset attempts by IP X in the last 24h") — **v1.8**. Phase 44 ships write-side traceability via `audit_log`; the read-side query API is a v1.8 backlog item per PROJECT.md.
- **Account-lockout after N failed password-reset attempts in 24h** — **v1.7+**. Currently rate-limited (per-IP + per-email) but lockout is not in scope; the v1.6 anti-oracle posture covers the threat model.
- **Push notification on password change** ("Your Sportzal password was just changed — if this wasn't you, contact support") — **v1.7+** (cross-channel; depends on Telegram-DM availability).
- **2FA / MFA on password reset** ("send a confirmation code to your Telegram before allowing the reset") — **v1.7+**. v1.6 single-factor (email-only) — adequate for the threat model (1-gym tenant, 1-2 operators).
- **OpenAPI schema regen of 3 new endpoints** — **Phase 46 HANDOFF-03** (drift gate at milestone serialization point).
- **Frontend integration of the reset/invite-accept flows in admin-web** — **v2.0 design-team handoff** (per Phase 43 D-43-XX backend-only discipline).
- **Translation of the locked Russian copy to additional languages** — **v2.0+** (Russian-only single-locale v1; `ru.ts` discipline holds for backend templates).
- **Reset-token replay-attack monitoring dashboard** (Grafana panel for `password_reset_completed` rate per minute) — **Phase 46 VER-* monitoring hardening** or v1.8 ops tooling.

### Reviewed Todos (not folded)
None — no todos matched Phase 44 scope at scan-time (gsd-sdk query todo.match-phase returned `todo_count=0`).

</deferred>

---

*Phase: 44-invitation-password-reset-flow*
*Context gathered: 2026-05-19*
