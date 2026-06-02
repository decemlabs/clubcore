# Phase 68: Client Auth Foundation - Context

**Gathered:** 2026-05-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver a secure, **isolated client principal**. Gym members authenticate via phone + Telegram OTP, receive a distinct `cc_client_*` session cookie (with refresh rotation), can view/edit their own profile, and the two-principal isolation (staff vs client) is proven by automated test. This is an **unconditional security blocker** for all later client-PWA work (Phases 69+).

**In scope:** client OTP request/verify, client session (cookie + refresh rotation + logout), `ClientPrincipal` + `require_client()`, `GET/PATCH /api/v1/client/me`, anti-oracle + rate limiting, two-principal isolation test + parametrized IDOR test.

**Out of scope:** any membership/visits/history/catalog reads (Phase 69), Telegram account *linking* (setting `Client.telegram_user_id` — owned by staff/onboarding), broader client profile self-edit beyond email, bookings/check-in (Phase 70).

</domain>

<decisions>
## Implementation Decisions

### OTP Delivery Flow
- **D-01:** Phone-first delivery — member enters phone; backend looks up `Client` by phone; if `Client.telegram_user_id` is set, the bot **DMs the 6-digit code directly** to that chat. No deep-link hop in the happy path.
- **D-02:** **Silent no-op** when a real (or unknown / duplicate / soft-deleted) phone has no linked `telegram_user_id` — response is **byte-identical** to the success case (CAUTH-02 anti-oracle via `_constant_time_floor`). No code is sent, no error revealed. Telegram linking is a staff/onboarding prerequisite, **out of this phase**.
- **D-03:** **Add a nullable `client_id` FK to the existing `OtpCode` table** (FK → `clients`), with a CHECK enforcing mutual exclusivity: `(user_id IS NULL) <> (client_id IS NULL)`. Reuse `generate_otp_code()`, `consume()`, attempts/`OtpMaxAttempts`, and anti-oracle logic. This is the "reuse existing OTP infrastructure" interpretation (CAUTH-01) — shared logic, isolated ownership.

### Profile Self-Service (`/api/v1/client/me`)
- **D-04:** `PATCH /client/me` accepts **email only** this phase (matches CAUTH-05 exactly). All other fields are read-only via this endpoint; name/birthday/phone/tags/notes stay staff-owned.
- **D-05:** `GET /client/me` returns **core identity fields only**: `id, phone, email, first_name, last_name, middle_name, birthday, gender`. Excludes staff-internal fields (`notes`, `tags`, `created_by_user_id`, `emergency_contact`) and **all membership data** — membership status is strictly Phase 69 (`GET /client/membership`). `/me` stays a pure auth/profile contract.
- **D-06:** Duplicate email on PATCH → **HTTP 409** with a generic non-enumerating body (e.g. `{ error: "email_unavailable" }`). Map the DB IntegrityError (partial-unique on `lower(email) WHERE deleted_at IS NULL`) to 409; do not reveal which account holds it. Email is not a login identifier here (phone is), so the minor existence signal is acceptable.

### aud Claim & Principal Isolation
- **D-07:** **Staff tokens stay aud-less** — the frozen staff `AccessTokenClaims` shape (`{sub, role, typ, iat, exp}`) is **not touched**. Client tokens carry `aud:"client"` (+ `sub = client_id`, no `role`). `require_client()` asserts `aud == "client"`; staff paths reject any aud-bearing token. Isolation derives from separate cookies + separate decode rules, not from a symmetric staff aud. This protects the byte-parity constraint (CISO-01) and avoids modifying the frozen contract.
- **D-08:** **Fully parallel client auth stack.** New `decode_client_token()` (validates `typ` + `aud=="client"`, `sub=client_id`, no role) and `register_client_loader(load_client_by_id)` mirroring the staff composition-root pattern. `require_client()` reads the `cc_client_access` cookie → decode → load `Client` → `ClientPrincipal`. Do **not** route client tokens through `decode_access_token` (it validates `role` against the staff `Role` enum).

### Client Session Storage
- **D-09:** **Separate client refresh stack.** New `client_refresh_token` table (FK → `clients`) + separate Redis namespace (`auth:client:session:{client_id}:{family_id}`, `auth:client:user_sessions:{client_id}`). Port the `rotate_refresh` 3-branch rotation logic (active / replaced-within-window / reuse-revoked) into a `rotate_client_refresh`. Staff and client storage **never intersect** — strongest CISO-05 isolation guarantee.
- **D-10:** Client cookies are `cc_client_*` (`cc_client_access`, `cc_client_refresh`, + a client CSRF cookie) with `Path` scoped to `/api/v1/client` so they never collide with staff `cc_*` cookies on the same origin (CISO-05). Mirror `issue_session_cookies` / `clear_session_cookies` attribute discipline (Path/HttpOnly/SameSite must match between issue and clear).

### Rate Limiting (CAUTH-06)
- **D-11:** Per-phone OTP limits: **≥60s cooldown** between requests for the same phone, **≤5 requests per rolling 24h** per phone. Per-IP limit is locked by the success criteria at **5/15min**. Brute-force code guessing is blocked via the existing `OtpCode.attempts` / `OtpMaxAttempts` path. New rate-limit keys are required (the existing `rate_limit.py` is per-email login only — do not overload it).

### Claude's Discretion
- Per-IP derivation behind proxy (X-Forwarded-For / trusted-proxy handling) — planner to choose, consistent with existing infra.
- Exact client access-token TTL, CSRF token naming, and logout-all-sessions behavior — planner to choose, mirroring staff defaults unless a reason to diverge.
- Concrete error envelope shape / status conventions where not specified above — follow existing API conventions.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap
- `.planning/ROADMAP.md` § Phase 68 — goal + 5 success criteria (the verification anchor).
- `.planning/REQUIREMENTS.md` — CAUTH-01..06 (client auth) and CISO-01..05 (client RBAC + data isolation). These are the locked requirement IDs for this phase.

### Existing backend code to reuse / mirror (full paths)
- `apps/backend/app/modules/auth/service.py` — `_constant_time_floor` (L942-953), `request_otp_telegram` (L1106-1147), `rotate_refresh` 3-branch logic (L367-569), `_write_session_keys` (L293-323). **Mirror, do not break.**
- `apps/backend/app/modules/auth/telegram_service.py` — `bind_and_issue`, `commit_otp`, `consume` — the Telegram OTP send/verify primitives to reuse.
- `apps/backend/app/modules/auth/models.py` — `OtpCode` (L97-160) + partial-unique `uq_otp_codes_user_channel_active`. **`client_id` column is added here (D-03).**
- `apps/backend/app/core/security.py` — `generate_otp_code` (L176-182), `AccessTokenClaims`/`encode_access_token`/`decode_access_token` (L31-110, staff — keep frozen), `issue_session_cookies`/`clear_session_cookies` (L204-292). Client equivalents mirror these.
- `apps/backend/app/core/dependencies.py` — `CurrentUser` Protocol (L33-48), `register_user_loader` (L61-68), `get_current_user` (L767-809), `require_permission` (L812-865). `ClientPrincipal` + `require_client` + `register_client_loader` mirror this composition-root pattern.
- `apps/backend/app/core/permissions.py` — `Role` enum + `OWNER_ONLY` + `can()`. **DO NOT add `Role.CLIENT`; DO NOT touch** (CISO-01 byte-parity with `apps/admin-web/src/shared/session/can.ts`, TEST-06).
- `apps/backend/app/modules/auth/rate_limit.py` — existing per-email login limiter (L1-47). New client OTP limiters are **separate keys** (D-11), not extensions of this.
- `apps/backend/app/modules/clients/models.py` — `Client` model (`phone`, `email`, `telegram_user_id`, soft-delete partial-unique indexes). Source of truth for `/me`.
- `apps/backend/app/api/v1/router.py` — mount new `/api/v1/client` router here.
- `apps/backend/app/main.py` — `create_app()` composition root; register the client loader alongside existing `register_*` calls.
- `apps/backend/tests/conftest.py` (SAVEPOINT harness, `async_client` over ASGITransport) and `apps/backend/tests/integration/auth/` — pattern for the two-principal isolation test (CISO-02) and parametrized IDOR test (CISO-04).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Anti-oracle floor** `_constant_time_floor` (200ms) — wrap every client OTP-request branch so unknown/unlinked/eligible converge to identical timing (CAUTH-02).
- **OTP primitives** `generate_otp_code`, `OtpCode.consume`, attempts/`OtpMaxAttempts` — reuse for client codes; brute-force protection comes free (CAUTH-06).
- **Refresh rotation** `rotate_refresh` 3-branch (active / replaced-within-window / reuse→revoke-family) — port to `rotate_client_refresh` for CAUTH-04 + family-reuse detection.
- **Cookie helpers** `issue_session_cookies`/`clear_session_cookies` — mirror for `cc_client_*` with `Path=/api/v1/client`; clear-must-match-issue attribute discipline.
- **Composition-root loaders** `register_user_loader` / `CurrentUser` Protocol — mirror with `register_client_loader` / `ClientPrincipal`.
- **Client model** already has `phone` (E.164, partial-unique alive), `email` (partial-unique lower alive), `telegram_user_id`, soft-delete — no new client columns needed beyond OTP `client_id`.
- **Test harness** SAVEPOINT rollback + `async_client` ASGITransport + Redis flush fixtures — directly supports isolation/IDOR tests.

### Established Patterns
- All branches converge through `_constant_time_floor` for anti-oracle parity (D-18/D-28 precedent).
- Rate-limit check happens **before** subject lookup to preserve timing equivalence — replicate for client OTP.
- Cookie clear must replicate issue attributes (Path/HttpOnly/SameSite) exactly or deletion silently fails.

### Integration Points
- New `/api/v1/client` router mounted in `app/api/v1/router.py`.
- New client loader registered in `app/main.py` `create_app()`.
- `OtpCode` schema change → Alembic migration (async) adding `client_id` + CHECK constraint.
- New `client_refresh_token` table → Alembic migration.

</code_context>

<specifics>
## Specific Ideas

- Member-facing OTP DM wording in Russian (e.g. «Ваш код: 482913») — Russian-only per project i18n convention.
- Generic duplicate-email error key `email_unavailable` (non-enumerating).
- Client Redis namespace prefix `auth:client:*` to make isolation visually auditable.

</specifics>

<deferred>
## Deferred Ideas

- **Telegram account linking** (setting `Client.telegram_user_id`) — prerequisite for OTP delivery but owned by staff/onboarding; its own phase. Until then, only members with a pre-linked Telegram can authenticate (acceptable for this phase's scope).
- **Broader client profile self-edit** (name, middle_name, birthday, emergency_contact) — possible later phase; this phase is email-only.
- **Membership/status hints on `/me`** — deliberately excluded; belongs to Phase 69 (`GET /client/membership`, CHOME-*).

</deferred>

---

*Phase: 68-Client Auth Foundation*
*Context gathered: 2026-05-29*
