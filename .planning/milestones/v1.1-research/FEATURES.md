# Feature Research — v1.1 Auth + Clients

**Domain:** Single-gym CRM backend (FastAPI modular monolith) — auth + first business module (clients)
**Region:** РФ/СНГ — Telegram primary channel, ЮKassa, Stripe forbidden
**Researched:** 2026-05-01
**Confidence:** HIGH (Telegram + JWT + RBAC patterns are well-documented; gym client-schema fields verified across multiple CRM vendors)

---

## Scope Reminder

What is **already shipped** in v1.0 and must NOT be re-listed as new:

- Frontend admin-web (React 19 SPA) with full mock services and FSD-lite layering
- Frontend RBAC: `Role = 'owner' | 'reception'`, `OWNER_ONLY` matrix, `can(role, action, resource)` in `apps/admin-web/src/shared/session/can.ts`
- Resource taxonomy in `apps/admin-web/src/shared/session/registry.ts` — `dashboard | clients | schedule | staff | finance | reports | payroll | compensation | templates | settings | owner-area`
- Backend FastAPI skeleton with `core / modules / integrations / workers / api`, `import-linter` enforced, `GET /healthz` only
- Mock-side `clients` UX is fully scaffolded and behaves correctly with role-aware 403-analogs

This research therefore covers **only the server-side gap**: real auth, real RBAC enforcement, real Postgres `clients` table with CRUD. Frontend wiring of `/login` + `/clients/*` to `VITE_API_MODE=http` is included only because it is part of the same milestone.

---

## 1. Auth — Telegram Bot Deep-Link OTP (Primary)

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---|---|---|---|
| Bot deep-link `https://t.me/<bot>?start=<login_token>` | Standard Telegram-login pattern; user clicks link from `/login` page, lands in bot already authenticated by Telegram | **S** | One endpoint to mint `login_token` (random 32-byte URL-safe), one bot `/start <token>` handler |
| One-time code displayed by bot | User sees 6-digit code in Telegram, pastes into web `/login` form. Code is bound to the `login_token` | **S** | Code stored in Redis with short TTL (3-5 min). Hash before storing (HMAC-SHA256, not bcrypt — speed matters; codes are ephemeral and high-entropy enough at 6 digits + rate limiting) |
| Code expiration (3-5 min) | Industry standard for OTP — long enough to paste, short enough to limit brute force | **S** | Redis `SETEX` |
| Rate limiting on code submission | 5 attempts per code, then code is invalidated and user must restart from bot | **S** | Redis `INCR` counter keyed by `login_token` |
| Bot must verify chat type is `private` | Group/channel posts must not initiate auth flow | **S** | Single `if` in bot handler |
| Account binding: `telegram_user_id ↔ user_id` | Required to know **which** Sportzal user is logging in | **S** | Postgres `user.telegram_user_id` UNIQUE column. First-time login → bind + audit log entry |
| `/login` page polls or uses short-lived "login pending" status | UX: user pastes code → server validates → cookies issued → redirect | **S** | Single POST endpoint accepts `{login_token, code}`, returns 204 + Set-Cookie or 401 |
| Bot blocked / user never opens link | Login token must expire (10-15 min) and be reusable-only-once | **S** | TTL on Redis key; `DEL` on success |
| Wrong account (Telegram user not provisioned) | Reject with explicit message: "Этот Telegram-аккаунт не привязан к Sportzal. Обратитесь к администратору." | **S** | Lookup by `telegram_user_id`; if no row, 403 with code `TELEGRAM_NOT_LINKED` |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---|---|---|---|
| Webhook-based bot (vs polling) | Lower latency, scales beyond hobby project | **M** | ARQ worker is already in stack; webhook endpoint sits in `app/api/webhooks/telegram.py`. Required for production but **NOT for v1.1 dev** — long-polling via `python-telegram-bot` getUpdates is acceptable for single-gym pet project |
| Magic-link variant (no code at all) | Even simpler UX: bot replies with a clickable link that hits `/api/v1/auth/telegram/callback?token=...` and sets cookies | **M** | Adds a second flow; for v1.1 keep ONE flow (code-based) |
| "Remember this device" pre-shared with bot | After first login, repeated logins skip the OTP step | **L** | Cookie-bound device fingerprint + Redis whitelist. Postpone — doesn't pay back for one-zal CRM |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---|---|---|---|
| **Telegram Login Widget** (`oauth.telegram.org`) | "Telegram already provides auth!" | Widget requires public HTTPS domain bound to `@bot` for setDomain; awkward for `localhost` dev. Also: widget gives only Telegram identity, you still need to bind to a Sportzal user — you don't save logic. | Keep deep-link OTP. We control the flow end-to-end and dev-friendly |
| **Telegram Passport** | "Verified phone/passport!" | Massive overkill for gym staff login; designed for KYC/financial flows | Not in scope, not in next 5 milestones |
| Public self-registration via bot | "User just types /start and gets account" | Single-gym CRM = **admin-provisioned only**. Self-reg leaks the door wide open | Owner provisions reception users via admin UI (later milestone). v1.1 has seed-script + manual `INSERT` |
| SMS fallback | "What if Telegram is down?" | SMS in РФ requires legal-entity contracts (СМС-агрегатор), кириллица caps at 70 chars, costs ~3 ₽/msg. Not worth it for single-zal pet | Email/password fallback is enough |

---

## 2. Auth — Email/Password Fallback

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---|---|---|---|
| Login by email + password | Owner needs a way in if Telegram bot dies / token expires / phone is broken | **S** | Standard `passlib[argon2]` hash, single POST endpoint `/api/v1/auth/login` |
| Argon2id password hashing (not bcrypt) | Argon2id is OWASP-recommended since 2021 and is the sane default in 2026 | **S** | `passlib.hash.argon2`; bcrypt is acceptable but Argon2id is the modern pick |
| Admin-provisioned only (no public registration) | Single-gym CRM. There is no "sign up" page | **S** | No `/register` endpoint at all. Seed script creates the owner; owner provisions reception via admin UI in a later milestone |
| Rate limit on login (5 attempts / 15 min per email) | Prevents trivial brute force | **S** | Redis `INCR` keyed by lowercased email, expire 15 min. **Don't** lock account permanently — that's a denial-of-service vector |
| Generic error messages | "Неверный email или пароль" — never leak which one was wrong | **S** | One-line decision in handler |
| Password complexity: minimum 12 chars | NIST 800-63B (2024 rev): length > complexity rules. No forced symbols/uppercase | **S** | One Pydantic validator. Don't add a "password strength meter" — overkill |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---|---|---|---|
| Password reset via Telegram bot | More secure and simpler than email reset for our user base | **M** | Reuse the OTP flow with a different intent (`reset` vs `login`). Allowed because owner already has a bound `telegram_user_id` |
| Pwned-password check (HIBP k-anonymity API) | Blocks reuse of leaked passwords on set/change | **M** | Single outbound call to `api.pwnedpasswords.com/range/<sha1prefix>`. Worth it; keeps owner out of trouble |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---|---|---|---|
| Password reset via email link | "Standard everywhere" | Requires real SMTP integration with deliverability, DKIM/SPF, bounce handling. Email is **not** primary channel here. Adds a whole subsystem for a feature used 1×/year per user | Telegram bot reset (above) |
| Forced password rotation every 90 days | "Compliance!" | NIST explicitly **deprecated** this in 2017. Causes weaker passwords (Password1!, Password2!). | Don't do it |
| Password complexity rules (1 upper, 1 digit, 1 symbol) | "Strong passwords" | Same NIST guidance: complexity rules degrade entropy. Length is what matters | Min 12 chars + HIBP check |
| Account lockout after N failures | "Security!" | DoS vector — anyone who knows owner's email can lock him out | Rate limiting (slow down) yes; lockout (deny) no |
| 2FA / TOTP | "Banks have it" | Owner already has Telegram bot OTP as primary; email/password is a **fallback**. Stacking 2FA on the fallback is theatre for a 1-gym pet | Out of scope. If added later, do it on email/password only |
| CAPTCHA on login | "Bots!" | Login is gated behind admin provisioning; nobody can guess emails. No bot problem to solve | Rate limiting is sufficient |

---

## 3. JWT Access + Refresh — Rotation, Sessions, Revocation

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---|---|---|---|
| Short-lived access token (15 min) in httpOnly cookie | OWASP/Auth0 standard; survives a refresh roundtrip | **S** | `python-jose` or `pyjwt`, HS256 with single secret in env. Keep it simple — RS256 has no payback for monolith |
| Long-lived refresh token (30d) in **separate** httpOnly cookie | Rotation needs a token that survives access expiry | **S** | Cookie scoped to `/api/v1/auth/refresh` only, `Secure`, `SameSite=Lax` (Lax over Strict because admin-web is same-site anyway and Strict breaks bot deep-link flow if browsers ever cross origins) |
| Refresh token **rotation** on every use | Detection of refresh-token theft (reuse → revoke entire family) | **M** | Family-id + per-token `jti` stored in Redis. On refresh: verify, mint new pair, mark old as `consumed`. If a `consumed` token is presented again → revoke entire family + log security event. **This is table stakes in 2026, not a differentiator.** |
| Server-side session record in Redis | Required to revoke / "logout everywhere" | **S** | `session:{user_id}:{family_id} → {created_at, last_used, ua, ip}` with TTL = refresh lifetime |
| `/api/v1/auth/logout` invalidates current session | Standard | **S** | `DEL session:{...}` + `Set-Cookie` with `Max-Age=0` for both cookies |
| Idle timeout (no refresh use for 7 days) | Defense in depth; refresh that's been idle a week is suspicious for a daily-use CRM | **S** | TTL on `last_used` key; fail refresh if past idle window |
| Absolute timeout = refresh lifetime (30d) | A session can never live forever | **S** | Refresh token has hard `exp` claim; rotation does **not** extend the absolute expiry beyond 30d from initial login |
| CSRF protection | Cookie-based auth requires it | **S** | Double-submit cookie pattern: server sets non-HttpOnly `csrf_token` cookie + client sends matching `X-CSRF-Token` header on mutating verbs. FastAPI dependency checks header == cookie. Simpler than synchronizer-token-pattern; sufficient for SameSite=Lax |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---|---|---|---|
| "Active sessions" UI — list devices, revoke individually | User-visible session control | **M** | `GET /api/v1/auth/sessions` + `DELETE /api/v1/auth/sessions/{id}`. Read from Redis. Worth the small effort because reception staff = multiple devices reality |
| "Logout everywhere" button | One-click revoke of all sessions | **S** | `DEL session:{user_id}:*` (SCAN pattern). Cheap if active-sessions UI already exists |
| User-Agent + IP captured on session create | Visible in active-sessions UI; helps spot suspicious | **S** | Pull from request, store on session record |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---|---|---|---|
| LocalStorage / Authorization-header bearer tokens | "REST API standard" | XSS-stealable, no CSRF protection comes free, no `Set-Cookie` attribute hardening. Adds token-storage code on frontend that admin-web doesn't have | httpOnly cookies — already aligned with frontend's `services/{mock,http}` swap-seam expectations |
| Stateless JWT with no server-side session | "JWT is supposed to be stateless!" | Cannot revoke. A stolen refresh = 30-day breach window. Reuse-detection requires state | Stateful refresh family in Redis (above). Access tokens stay stateless |
| Passwordless via "magic link emailed on every login" | "Modern!" | Already covered by Telegram bot — that **is** the magic link. Adding email magic links duplicates the surface | Stick with Telegram + email/password |
| Per-request DB lookup of access-token validity | "More secure" | Defeats the point of JWT. 200ms login latency before you do anything | Trust signed access tokens until expiry; revoke at refresh time |

### Token-rotation-flow detail (load-bearing for plan)

```
On login:
  family_id = uuid4()
  refresh_jti = uuid4()
  Redis SET session:{user_id}:{family_id} = {refresh_jti, created_at, last_used, ua, ip} EX 30d
  Issue access (15m, claims: sub=user_id, role) + refresh (30d, claims: sub, family_id, jti)

On /auth/refresh:
  verify refresh sig + exp
  fetch session:{sub}:{family_id}
    if missing → 401 SESSION_REVOKED
    if stored.refresh_jti != incoming.jti → REUSE: DEL session, log security event, 401 TOKEN_REUSE
  rotate: new_jti = uuid4()
  Redis SET session:{sub}:{family_id} = {new_jti, ...same..., last_used=now} EX 30d
  Issue new access + refresh pair (refresh keeps original family_id, new jti)
```

---

## 4. Clients CRUD — Field Set for Single Gym

### Table Stakes (must ship in v1.1)

| Field | Why Expected | Notes |
|---|---|---|
| `id: ClientId` (UUIDv4) | Stable cross-system reference | Branded UUID, matches frontend `ClientId` brand |
| `last_name`, `first_name`, `middle_name` (отчество, optional) | РФ standard ФИО triple. Reception searches and addresses clients by ФИО | Three separate columns. Don't store concatenated `full_name` — derived |
| `phone` (E.164) | Primary contact in РФ. Search target | Stored as `+7XXXXXXXXXX`; UI handles `+7 (XXX) XXX-XX-XX` mask. UNIQUE with `WHERE deleted_at IS NULL` |
| `birthday: date` (nullable) | Age-based pricing, birthday greetings | Nullable — reception sometimes doesn't ask up front |
| `gender: 'male' \| 'female' \| null` | РФ market norm; some pricing/locker logic later depends on it | Enum, nullable |
| `email` (nullable, optional) | Receipts / fallback comms | Nullable — many clients don't volunteer email in РФ |
| `notes: text` (nullable) | Reception's freeform memory ("платит наличкой", "ходит с мамой") | Single textarea; do NOT split into structured sub-fields |
| `created_at`, `updated_at` (timestamptz, UTC) | Audit basics | SQLAlchemy `server_default=func.now()` |
| `deleted_at` (timestamptz, nullable) | Soft delete only — never hard delete clients (financial audit, returning clients) | All queries filter `WHERE deleted_at IS NULL`. Owner-only operation |
| `created_by_user_id` (FK → users.id) | Auditability of who entered the client | NOT NULL |

**Estimated migration size:** ~1 Alembic revision, ~12 columns + 2 indexes (phone unique-where-not-deleted, last_name lower-trgm for ILIKE). **Complexity: S.**

### Differentiators

| Field | Value Proposition | Complexity | Notes |
|---|---|---|---|
| `tags: text[]` (Postgres array) | Fast segmentation: "VIP", "должник", "новичок" | **S** | Postgres `text[]` + GIN index. No separate `tags` table needed for single-gym scale. Enforce normalized lowercase server-side |
| `telegram_user_id` (BIGINT, nullable, UNIQUE) | Future client-bot for self-service | **S** | Add column now, populate later. Reuses the same constraint pattern as `users.telegram_user_id` |
| `emergency_contact: jsonb` (`{name, phone, relation}`) | Liability concern (gym injury) | **S** | Single JSONB column avoids a side table for one optional struct. Validate via Pydantic |
| Client photo (URL) | Reception verifies identity at door | **M** | Requires file storage decision (S3-compatible? local volume?). **Defer to a later milestone** — just reserve `photo_url: text` nullable column now |
| Medical waiver flag (`medical_clearance: bool`) | РФ clubs ask for справка от врача in some cases | **S** | Bool nullable + free-text `medical_notes`. **Differentiator, not table stakes** for v1.1 — owner can put it in `notes` for now |
| Membership-freeze status | Industry-standard pause for vacations / illness | **L** | **Belongs to memberships module, NOT clients.** Out of scope for v1.1 |
| Parent-link for minors | Family-account use case | **L** | `parent_client_id` self-FK. Defer — gym is adults-first |
| Check-in history join | Quick "last visit" column in list view | **M** | Belongs to visits module — out of scope for v1.1 (visits table doesn't exist yet) |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---|---|---|---|
| Hard delete | "GDPR right to erasure!" | РФ has 152-ФЗ (similar but different). Hard-deleting kills financial audit trail, breaks FK from future visits/payments. ЦБ/ФНС audits expect data retention | Soft delete + a separate "anonymize PII" operation in a later milestone if a real request comes in |
| Custom field schema (admin-defined fields) | "Every gym is different" | Forces JSONB-everywhere or EAV. Massive complexity. Single-gym pet doesn't need it | `notes` + `tags[]` cover 95% of requests. Hard-code the schema |
| Bulk import (CSV/Excel) | "I have 200 clients in a spreadsheet" | Validation hell, encoding hell (Windows-1251 vs UTF-8 in РФ Excel exports). Owner has time to add 200 manually for a pet project | Defer. If shipped later, do it as a one-off owner-only endpoint, not a UI |
| Per-client custom pricing | "Friend discount" | Belongs to memberships/billing, not clients | Out of scope |
| Activity feed / timeline on client detail | "See everything they've done" | Requires every other module to exist | Defer to a milestone where >2 modules talk to each other |
| Free-text full-text search (tsvector / Elasticsearch) | "Search all the things!" | Premature for single zal with <2000 clients. ILIKE on `lower(last_name)` and `phone` covers all real reception queries | ILIKE + `pg_trgm` GIN index — covered below |

---

## 5. Search & Filters on `/api/v1/clients`

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---|---|---|---|
| Pagination `{items, total, page, pageSize}` | Already a project-wide contract from frontend; reception list view paginates | **S** | LIMIT/OFFSET with `count(*) OVER ()` window for `total`. For <100k rows OFFSET is fine; if it ever isn't, switch to keyset later |
| ILIKE search across `last_name + first_name + phone` | Reception types "иван" or "+7916" and finds the row | **S** | One query parameter `q`. Build `WHERE (lower(last_name) LIKE %q% OR lower(first_name) LIKE %q% OR phone LIKE %q%) AND deleted_at IS NULL`. **`pg_trgm` GIN index** on `lower(last_name)` and `lower(first_name)` keeps it sub-50ms even at 50k rows |
| Sort: `created_at DESC` default | Newest clients first matches reception's mental model | **S** | Single `ORDER BY` |
| Soft-delete filter applied automatically | Deleted clients never leak into list | **S** | One `WHERE deleted_at IS NULL` shared by all reads |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---|---|---|---|
| Filter by `tags` (any-of) | Segmentation: "show me all VIPs" | **S** | `WHERE tags && ARRAY[...]::text[]` — Postgres array overlap, GIN-indexed |
| Filter by signup date range | Cohort analysis ("clients added this month") | **S** | Two query params, BETWEEN clause |
| Filter by `gender` | Locker assignment edge cases | **S** | One enum filter. Cheap if the column is in the table |
| Filter by `has_telegram` | "Who can I message?" | **S** | `telegram_user_id IS NOT NULL` |
| Sort by `last_name ASC` (alphabetical) | Russian gym staff often want alphabetical printouts | **S** | Add as one of two allowed sort modes |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---|---|---|---|
| Saved filters / smart segments | "CRM should remember!" | Owner-side configuration UI, persistence model, share-between-users — three new subsystems | Defer until proven need (v2+) |
| Boolean query language ("Иван AND VIP NOT debtor") | "Power user!" | Parsing, validation, injection-safe building. ILIKE + tag filter covers the same use cases for 95% less code | Multiple filter params (above) |
| Last-visit-date filter | "Find lapsed clients" | Requires visits module that doesn't exist yet in v1.1 | Defer to milestone where visits exist |
| Server-side CSV export | Standard CRM expectation | Ties up an HTTP worker on large exports, encoding gotchas (БОМ for Excel) | Defer. If shipped, do it as a worker (ARQ already in stack) |
| Geo / radius search | "Find clients near branch X" | Single-zal CRM has one location | Hard-no for v1.x |

---

## 6. Server-Side RBAC — Parity with Frontend

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---|---|---|---|
| `Role` enum in DB matches frontend (`'owner' \| 'reception'`) | Mirrors `apps/admin-web/src/shared/session/types.ts` | **S** | Postgres ENUM or constrained text. ENUM is fine since values are stable |
| `OWNER_ONLY` matrix lives in **one** place server-side | Single source of truth, mirrors `apps/admin-web/src/shared/session/can.ts` | **S** | `app/modules/auth/permissions.py` with the same `(action, resource)` tuple list. Add a unit test that asserts byte-equal parity with the frontend list (read frontend's TS file? No — duplicate the list and add a `test_rbac_parity_with_frontend.py` that just hard-codes the expected pairs) |
| `require_permission(action, resource)` FastAPI dependency | Plug into every business endpoint with `Depends(require_permission('view', 'clients'))` | **S** | Reads role from access-token claim, calls `can()`, raises `HTTPException(403, code='FORBIDDEN')`. Idiomatic FastAPI, exactly the pattern in the search results |
| 403 response shape matches frontend's `DomainError` contract | Frontend already throws/expects `{ code, message, fields? }` from mock services | **S** | One global exception handler maps `PermissionError` → 403 + JSON body |
| `delete clients` is owner-only at server | Mirrors frontend `OWNER_ONLY` | **S** | Falls out of `require_permission('delete', 'clients')` automatically |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---|---|---|---|
| **Audit log table** (`audit_log`: actor_user_id, action, resource_type, resource_id, before/after JSONB, ip, ua, ts) | Owner-visible "who did what" — high value for trust in reception, low cost to ship now | **M** | One table, one SQLAlchemy event listener / explicit `audit.log(...)` call in service-layer mutations. **Worth shipping in v1.1** — adding it later requires retrofitting every endpoint. Read endpoints later (defer to a viewer milestone) |
| Audit-log SELECT endpoint with pagination | Owner-only viewer | **S** | Falls out naturally if the table exists. Could also be deferred — write in v1.1, read UI later |
| Per-resource permission strings (e.g. `clients.delete`) | More flexible than `(action, resource)` tuples | **S** | Cosmetic; not needed since frontend already uses tuples. **Keep tuples** for parity |
| Object-level permissions ("user X can edit only their own resource Y") | Multi-user-data scenarios | **L** | No use case in single-zal CRM where reception sees all clients | **Out of scope** |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---|---|---|---|
| Casbin / Oso / external policy engine | "Industry standard for RBAC" | Two-role static matrix doesn't justify a policy engine. Adds a dependency, a DSL, a learning curve | Hard-coded `OWNER_ONLY` tuple list. Replace if and only if dynamic roles ever ship |
| Permission decorator macro (vs `Depends`) | "Decorators look cleaner" | FastAPI `Depends` integrates with OpenAPI schema generation, request lifecycle, and testing fixtures. Decorators don't | `Depends(require_permission(...))` |
| Multi-tenancy / row-level security / `SET LOCAL tenant_id` | "Future-proof for multi-zal" | Explicitly Out of Scope per `PROJECT.md`. Adding it now leaks into every model and migration | Defer until 2nd customer exists |
| Dynamic role creation in admin UI | "Customers want custom roles!" | Two-role matrix is a deliberate product decision. Custom roles imply policy engine, UI, conflict resolution | Hard-no for v1.x |
| Audit log full-text search / filter UI | "Compliance!" | The viewer is itself deferred; search on top of a viewer that doesn't exist yet is double-deferred | Out of scope. v1.1 ships the **table + writes only** |

---

## Feature Dependencies

```
Postgres `users` table
    └──required by──> Postgres `clients.created_by_user_id` FK
    └──required by──> JWT subject claim (sub = user_id)
    └──required by──> Audit log actor_user_id

Telegram bot deep-link OTP
    └──requires──> users.telegram_user_id (UNIQUE)
    └──requires──> Redis (for login_token + OTP code storage)
    └──requires──> python-telegram-bot dependency added to backend

Email/password fallback
    └──requires──> users.email (UNIQUE) + users.password_hash
    └──requires──> argon2-cffi via passlib

JWT access + refresh rotation
    └──requires──> Redis (session:{user_id}:{family_id} records)
    └──requires──> CSRF double-submit (cookie + header validator)

require_permission() dependency
    └──requires──> JWT access-token claim with `role`
    └──requires──> OWNER_ONLY matrix in app/modules/auth/permissions.py
    └──enhances──> Every business endpoint (clients CRUD is the first consumer)

Clients CRUD
    └──requires──> users (for created_by FK)
    └──requires──> require_permission()
    └──requires──> first business Alembic migration
    └──enhances──> packages/api-client (codegen target)

packages/api-client
    └──requires──> FastAPI exporting openapi.json
    └──requires──> openapi-typescript at build time
    └──enhances──> apps/admin-web /login + /clients/* routes

Audit log
    └──requires──> users (FK)
    └──enhances──> Clients CRUD (mutations write audit entries)
    └──enhances──> Auth flows (login/logout/refresh-reuse events)
```

### Dependency Notes

- **Auth must ship before clients CRUD** — clients endpoints have `Depends(require_permission(...))`, which needs role-claim-bearing JWT, which needs user table + login flow.
- **`packages/api-client` codegen requires the API to exist first** — order inside the milestone: backend auth → backend clients → openapi.json → codegen → admin-web wiring.
- **Audit log table must exist before mutation endpoints write** — otherwise retrofitting writes into 6+ endpoints later is rework.
- **Conflict: Telegram Login Widget vs deep-link OTP** — picking one. Deep-link OTP wins (dev-friendly, full control).
- **Conflict: stateless JWT vs revocable sessions** — picking stateful refresh families with stateless access. Standard 2026 pattern.

---

## v1.1 Scope Definition

### Launch With (v1.1)

Minimum viable for "first business slice with auth":

- [ ] `users` table + Alembic migration (id, email UNIQUE, password_hash, telegram_user_id UNIQUE nullable, role enum, created_at, updated_at)
- [ ] Argon2id password hashing via passlib
- [ ] `POST /api/v1/auth/login` (email + password) → access + refresh cookies
- [ ] Telegram bot deep-link OTP flow: `POST /api/v1/auth/telegram/start` → returns `login_token` → bot `/start <token>` posts 6-digit code → `POST /api/v1/auth/telegram/verify` with `{login_token, code}` → cookies
- [ ] Telegram bot uses long-polling in dev (webhook deferred)
- [ ] `POST /api/v1/auth/refresh` with rotation + reuse-detection
- [ ] `POST /api/v1/auth/logout` — single session
- [ ] `POST /api/v1/auth/logout-all` — all sessions for current user
- [ ] CSRF double-submit cookie pattern for mutating endpoints
- [ ] `OWNER_ONLY` matrix in `app/modules/auth/permissions.py` + parity unit test
- [ ] `require_permission(action, resource)` FastAPI dependency
- [ ] `clients` table + first business Alembic migration (table-stakes fields only — see §4)
- [ ] `pg_trgm` extension migration + GIN indexes on `lower(last_name)`, `lower(first_name)`
- [ ] `GET /api/v1/clients?q=&page=&pageSize=&tag=&gender=&signup_from=&signup_to=&sort=` returns `{items, total, page, pageSize}`
- [ ] `POST /api/v1/clients` (reception+owner)
- [ ] `GET /api/v1/clients/{id}` (reception+owner)
- [ ] `PATCH /api/v1/clients/{id}` (reception+owner)
- [ ] `DELETE /api/v1/clients/{id}` (owner-only, soft delete)
- [ ] `audit_log` table + writes from auth flows + clients mutations (read endpoint deferred)
- [ ] `packages/api-client` typed client generated from `openapi.json` (auth + clients endpoints)
- [ ] CI drift check: `git diff --exit-code` on regenerated openapi.json + ts types
- [ ] `apps/admin-web` `/login` and `/clients/*` routes wired through `VITE_API_MODE=http`

### Add After Validation (v1.2+)

- Active-sessions UI (list + revoke individual)
- Audit log read endpoint + owner-only viewer
- Password reset via Telegram bot
- HIBP pwned-password check on password set
- Tags-table normalization if `text[]` proves limiting
- Webhook-based Telegram bot (replace long-polling)

### Future Consideration (v2+)

- Reception-user provisioning UI (currently seed-script only)
- Photo upload for clients (requires storage decision)
- Medical clearance structured fields
- Bulk CSV import
- Visits/check-in module → unlocks last-visit filter

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---|---|---|---|
| Email/password login | HIGH (only path until Telegram bot is set up) | LOW | **P1** |
| Telegram bot OTP login | HIGH (primary daily-use path) | MEDIUM | **P1** |
| JWT access + refresh rotation | HIGH (security core) | MEDIUM | **P1** |
| Server-side RBAC parity | HIGH (frontend already enforces it; backend MUST match or it's a bypass) | LOW | **P1** |
| Clients CRUD (table-stakes fields) | HIGH (the whole point of v1.1) | LOW | **P1** |
| ILIKE search + paginated list | HIGH (reception's #1 daily action) | LOW | **P1** |
| Soft delete | HIGH (financial audit) | LOW (one column + filter) | **P1** |
| Audit log writes (table + writes only) | MEDIUM (retrofitting later costs more) | LOW–MEDIUM | **P1** |
| `tags[]` + filter | MEDIUM | LOW | **P1** |
| `emergency_contact` JSONB | MEDIUM | LOW | **P2** |
| `telegram_user_id` on clients | LOW–MEDIUM (future-proofing) | LOW | **P1** (cheap, prevents migration later) |
| Active-sessions UI | MEDIUM | MEDIUM | **P2** |
| Password reset via Telegram | LOW (rare event) | MEDIUM | **P2** |
| Audit log viewer | MEDIUM | MEDIUM | **P2** |
| Photo upload | MEDIUM | HIGH (storage decision) | **P3** |
| Bulk import | LOW (200 clients = manual) | HIGH | **P3** |
| Multi-tenancy | ZERO (one zal) | HIGH | **never in v1.x** |

---

## Out-of-Scope Carry-Overs (for REQUIREMENTS.md)

These should appear as explicit "Out of Scope" entries in v1.1 REQUIREMENTS.md so they don't sneak in:

- Public self-registration (admin-provisioned users only)
- SMS OTP (Telegram + email cover the channel matrix)
- Telegram Login Widget (deep-link OTP wins)
- Email-based password reset (Telegram-bot reset deferred to v1.2)
- 2FA / TOTP on email-password
- Forced password rotation, complexity rules beyond min-length, account lockout
- CAPTCHA
- Authorization-header bearer tokens / localStorage tokens
- Stateless-only JWT without revocation
- Per-request DB lookup of access tokens
- Hard delete of clients
- Custom client field schema / admin-defined fields
- Bulk import of clients
- Per-client custom pricing
- Activity timeline on client detail
- Full-text search (tsvector / Elasticsearch)
- Saved filters / smart segments
- Boolean query language
- CSV export
- Last-visit filter (depends on visits module — not in v1.1)
- Casbin / Oso / external policy engine
- Permission-decorator macros (use `Depends`)
- Multi-tenancy / RLS / `SET LOCAL`
- Dynamic role creation
- Audit-log search/filter UI (table writes ship in v1.1; viewer deferred)
- Object-level permissions
- Photo upload for clients
- Medical clearance structured fields (use `notes` for now)
- Membership freeze (belongs to memberships module, not clients)
- Parent-link for minors
- Webhook-based Telegram bot (long-polling acceptable in dev)

---

## Sources

- [Telegram Bot API — auth flows](https://core.telegram.org/bots/telegram-login) — official; HIGH confidence
- [OWASP Authentication Cheat Sheet — refresh-token rotation, httpOnly cookies, CSRF double-submit](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html) — authoritative; HIGH confidence
- [NIST SP 800-63B (rev. 2024) — password length over complexity, no forced rotation, no lockout](https://pages.nist.gov/800-63-3/sp800-63b.html) — authoritative; HIGH confidence
- [FastAPI security tutorial — OAuth2 + JWT + Depends pattern](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/) — official; HIGH confidence
- [FastAPI RBAC implementation tutorial (Permit.io)](https://www.permit.io/blog/fastapi-rbac-full-implementation-tutorial) — MEDIUM confidence (vendor blog, but pattern is standard)
- [JWTs — Expiration, Rotation, and Revocation](https://www.caduh.com/blog/jwts-expiration-rotation-revocation) — MEDIUM confidence (corroborates OWASP)
- [Refresh Token Rotation Best Practices (Serverion)](https://www.serverion.com/uncategorized/refresh-token-rotation-best-practices-for-developers/) — MEDIUM confidence
- [Postgres `pg_trgm` extension — official docs](https://www.postgresql.org/docs/16/pgtrgm.html) — authoritative; HIGH confidence
- [Have I Been Pwned — k-anonymity password range API](https://haveibeenpwned.com/API/v3#PwnedPasswords) — authoritative; HIGH confidence
- Gym CRM field surveys: PushPress, Gymdesk, Zenoti, ClubOS, GymMaster product pages (table-stakes field set verified across vendors) — MEDIUM confidence
- Existing project artifacts (HIGH confidence — ground truth):
  - `/Users/andre/Workspace/Development/clubcore/.planning/PROJECT.md`
  - `/Users/andre/Workspace/Development/clubcore/apps/admin-web/src/shared/session/can.ts`
  - `/Users/andre/Workspace/Development/clubcore/apps/admin-web/src/shared/session/registry.ts`
  - `/Users/andre/Workspace/Development/clubcore/apps/admin-web/CLAUDE.md`

---
*Feature research for: v1.1 Auth + Clients milestone*
*Researched: 2026-05-01*
