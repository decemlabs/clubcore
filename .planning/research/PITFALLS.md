# Pitfalls Research — v1.1 Auth + Clients

**Domain:** FastAPI modular-monolith adding two-channel auth (Telegram bot deep-link + email/password) + first business CRUD (Clients) + frontend wiring through typed `packages/api-client`
**Researched:** 2026-05-01
**Confidence:** HIGH for stack-specific items (verified against current FastAPI/SQLAlchemy 2.0/Alembic/Telegram Bot API/openapi-typescript docs); MEDIUM for codebase-specific risks (inferred from `.importlinter`, `core/middleware.py`, `can.ts`, `services/index.ts`).

This document is scoped to the v1.1 milestone. It is intentionally NOT a generic "web auth pitfalls" list — every entry is anchored to a concrete file/contract/test that already exists or will exist in this codebase.

---

## Pitfall-to-Phase Mapping (overview)

The roadmap should be sequenced so that each pitfall is prevented before the code that would expose it lands. Suggested phase taxonomy (used throughout the document):

- **Phase B1 — Auth foundations**: secret config, JWT helpers, password hashing, cookie semantics, Redis session store
- **Phase B2 — Telegram channel**: bot handlers, OTP issue/verify, deep-link state, polling vs webhook in dev
- **Phase B3 — RBAC dependency**: `require_permission(action, resource)` server-side parity with `can.ts`
- **Phase C1 — Clients model + first migration**: SQLAlchemy declarative naming convention, soft-delete, partial unique index, Alembic autogenerate sanity
- **Phase C2 — Clients service + endpoints**: query helpers (`deleted_at IS NULL`), pagination contract, ILIKE search, service-level permission checks
- **Phase D — `packages/api-client`**: openapi-typescript codegen, drift CI check, generic `Page<T>`, optional vs nullable
- **Phase E — Admin-web wiring**: HTTP services aligned to mock contracts, `VITE_API_MODE` chokepoint, login flow, refresh handling in TanStack Query

---

## Critical Pitfalls

### Pitfall 1 — Cookie SameSite=Strict breaks the Telegram-deep-link return flow

**What goes wrong:**
Refresh cookie issued with `SameSite=Strict` is **not** sent on top-level navigations that originate from a third-party origin (e.g. user taps a `t.me/sportzalbot?start=login_<token>` link, the bot DMs them an "Open admin" link, the click lands on `admin.sportzal.ru/auth/callback?...`). Browser strips the cookie. SPA boots, sees no session, redirects to `/login`. User is in an infinite "I just authenticated, why am I logged out" loop.

**Why it happens:**
SameSite=Strict feels safer ("max CSRF protection"), and the Phase A `core/security.py` is just a placeholder, so whoever writes the cookie code in Phase B1 will copy a snippet without thinking about whether the cross-site navigation case applies. It does, because Telegram DMs are cross-origin.

**How to avoid:**
- Refresh cookie: `SameSite=Lax`, `HttpOnly`, `Secure` (in dev: see Pitfall 2), `Path=/api/v1/auth/refresh` (narrow path scope so the refresh token is not sent on every API request — only on refresh).
- Access cookie: same `SameSite=Lax`, broader `Path=/api/v1/`.
- For the Telegram callback, ensure the redirect lands via a **GET** request — `Lax` allows cross-site cookies on top-level GET navigations. Never trigger session creation on a POST from a third party.
- Document the cookie matrix in an ADR before writing the code.

**Warning signs:**
- Test with two browsers: from `t.me/...` → admin → cookie missing in network tab.
- Cypress/Playwright e2e showing "logged out after Telegram auth" on first attempt, "works on refresh".
- Server logs: `/api/v1/auth/refresh` returns 401 immediately after a successful `/api/v1/auth/telegram/callback`.

**Phase to address:** Phase B1 (cookie semantics ADR + integration test that simulates a cross-site GET).

---

### Pitfall 2 — `Secure` cookie flag silently dropped in dev (HTTP localhost)

**What goes wrong:**
You set `Secure=True` on the refresh cookie because docs say "always set Secure". In docker-compose dev, the SPA talks to `http://localhost:5173` and the API at `http://localhost:8000`. Browser **silently drops** the Set-Cookie header because connection is not HTTPS. Auth appears broken in dev. Developer (or AI agent) flips it to `Secure=False` everywhere, then forgets to flip it back for prod.

**Why it happens:**
Docker-compose has no TLS termination layer in v1.0; `localhost` is not treated as a "secure context exception" for the Secure attribute (only some browser features get that exception, not the cookie attribute itself).

**How to avoid:**
- Drive the flag from settings: `cookie_secure: bool = Field(default=True)` in `app/core/config.py`, override in `.env.development` to `false`.
- Keep prod `.env.example` showing `COOKIE_SECURE=true`.
- Add a settings-level assertion: `if settings.environment == "production" and not settings.cookie_secure: raise RuntimeError(...)` at startup.
- Add a unit test that asserts `cookie_secure=True` when `ENVIRONMENT=production`.

**Warning signs:**
- "It works in production but not in dev" or vice-versa.
- `Set-Cookie` header in response but no cookie in browser jar (look in DevTools → Application → Cookies).

**Phase to address:** Phase B1.

---

### Pitfall 3 — CSRF wide open because cookies + non-GET endpoints + no CSRF check

**What goes wrong:**
Cookies are auto-sent on cross-origin POST (with credentials and a permissive CORS). A malicious page issues `fetch('/api/v1/clients/<id>', {method:'DELETE', credentials:'include'})`, browser sends the access cookie, soft-delete happens. SameSite=Lax mitigates but is not airtight (especially with `method=GET`-tunneled or some old browser quirks).

**Why it happens:**
The team historically thinks "JWT in localStorage = no CSRF"; switching to cookie storage re-introduces the CSRF surface, but the auth refactor docs rarely re-flag it.

**How to avoid:**
- Strict CORS allowlist: `allow_origins=[settings.frontend_origin]`, `allow_credentials=True`, no wildcard.
- Double-submit CSRF token for state-changing methods: server sets a non-HttpOnly `csrf_token` cookie, frontend reads it and echoes in `X-CSRF-Token` header on POST/PATCH/DELETE; FastAPI dependency `require_csrf` validates header == cookie.
- Or rely on SameSite=Lax + Origin-header check as a lighter alternative for a 1-2-user pet project (acceptable shortcut, see Technical Debt table).
- Add a test: `POST /api/v1/clients` from `Origin: https://evil.com` returns 403.

**Warning signs:**
- Penetration test ticket; or a test that crafts a cross-origin POST and watches it succeed.

**Phase to address:** Phase B1 (decide CSRF strategy in ADR), enforce in Phase C2 on every mutating endpoint.

---

### Pitfall 4 — Refresh-token rotation race: SPA fires two requests simultaneously, both trigger refresh, second one rotates the rotation, both clients get logged out

**What goes wrong:**
The SPA dispatches two parallel queries (TanStack Query already batches but loaders/onLoad refetches can fire in parallel). Both encounter expired access token, both call `/auth/refresh`, both receive new tokens BUT the second one invalidates the first's cookie because rotation marks the previous refresh as used → reuse-detection trips → ALL sessions for this user are revoked → user logged out mid-action.

**Why it happens:**
Naive implementation rotates on every `/refresh` call without a "single-flight" guard. TanStack Query has no built-in awareness of an in-flight refresh.

**How to avoke:**
- **Server side:** allow a small reuse window (e.g. accept the same refresh token from the same `family_id` for ~5 seconds and return the **same** new pair). Track refresh-token families (`family_id` + `version`) in Redis; only flag reuse if a token is replayed AFTER its rotation has been observed by a different connection.
- **Client side:** single-flight refresh in the api-client. The fetch wrapper (`packages/api-client`) maintains a module-scoped `Promise<void> | null` for an active refresh; concurrent 401s await the same promise and retry once. Test with two parallel `fetch` calls.
- Reuse-detection alarm: if a token is replayed AFTER the family has been advanced, revoke entire family and require re-login.

**Warning signs:**
- Sentry/structlog showing a burst of 401s within 50ms followed by "session revoked" log lines.
- Frontend: sporadic logouts when navigating to a route whose loader prefetches several queries.

**Phase to address:** Phase B1 (server-side family + reuse window) and Phase D (client-side single-flight).

---

### Pitfall 5 — Refresh tokens stored in plaintext in Redis or DB

**What goes wrong:**
Redis dump leaks → all active refresh tokens are usable verbatim against the API. Same risk if stored in Postgres for revoke tracking.

**Why it happens:**
"It's just a Redis cache, who cares" + the ergonomics of comparing strings directly.

**How to avoid:**
- Refresh token = high-entropy random opaque string (32 bytes urlsafe). Store **SHA-256 hash** in Redis; index by `family_id`. Compare hashes.
- Set Redis TTL = refresh expiry + small grace (e.g. `30d + 1h`). Use `EXPIRE` not `PERSIST`.
- For the access token (JWT), no storage needed — it's short-lived and self-contained. But maintain a `revoked_jti` set in Redis for emergency revoke; check on every request.

**Warning signs:**
- `redis-cli KEYS 'session:*'` reveals raw token values.
- Tests that compare `redis.get(...)` against the literal token from the response.

**Phase to address:** Phase B1.

---

### Pitfall 6 — Forgetting to invalidate sessions on password change / email change / role change

**What goes wrong:**
Owner changes their password (because they suspect compromise). Old refresh tokens still work for 30 days. Attacker keeps using them.

**Why it happens:**
The "rotate on every refresh" mental model gives a false sense that everything is invalidated; in reality, the family is still alive.

**How to avoid:**
- On password change / email change / role demotion: bump a `session_version` integer on the user row. Every JWT carries `sv` claim; deny if `sv != user.session_version`. Or: enumerate Redis keys for `family_id` of this user and delete them.
- Add a service method `auth.revoke_all_sessions(user_id, reason)` and unit-test it.
- Same hook on "user disabled" / role demotion.

**Warning signs:**
- After password change, a stale curl with old cookie still returns 200.

**Phase to address:** Phase B1 (mechanism); Phase B3 (call site for role change); future phase for email change.

---

### Pitfall 7 — Telegram Login Widget cannot run in dev (no public HTTPS domain)

**What goes wrong:**
Team picks Telegram Login Widget (`<script src="telegram-widget.js">`) for the auth flow. It REQUIRES the bot to have a `domain` configured via @BotFather, and that domain must be reachable HTTPS. Localhost is rejected. Dev experience is impossible without ngrok/cloudflared. Then in CI, e2e tests cannot exercise it.

**Why it happens:**
Two separate Telegram auth UX exist — Login Widget (browser, requires domain) and Bot deep-link + OTP (Telegram app, requires no public domain). The docs blur the difference; the code samples show widget; the CRM team picks widget without realising the dev cost.

**How to avoid:**
- **Decision: bot deep-link primary, widget never.** This is already locked in PROJECT.md. Verify the chosen library aligns (e.g. `aiogram 3.x` for the bot, NOT `pyTelegramBotAPI` widget helpers).
- Dev: use **long-polling** (`bot.start_polling`) inside an ARQ worker or a dedicated `python -m app.integrations.telegram.poller` process started by docker-compose.
- Prod: switch to webhook by env flag (`TELEGRAM_MODE=webhook|polling`).
- E2E tests: stub the bot transport entirely — Telegram integration tests use a fake adapter that records sent messages and lets the test simulate "user pressed button" by directly calling the OTP submit API.

**Warning signs:**
- Plan mentions `data-telegram-login` script tag.
- Dev runbook starts with "first, run ngrok".

**Phase to address:** Phase B2 — encode the polling-vs-webhook decision in an ADR before writing the integration.

---

### Pitfall 8 — Telegram `auth_data` hash verification using the wrong secret

**What goes wrong:**
You verify a Telegram payload (Login Widget `hash` field, or `WebApp.initData`) using `bot_token` directly as the HMAC key. Telegram requires `secret_key = SHA256(bot_token)` for Login Widget, and `HMAC_SHA256("WebAppData", bot_token)` for WebApp initData. Wrong key → all valid payloads rejected → developer disables verification "to debug" → spoofable forever.

**Why it happens:**
Two different formulas for two different products with similar names. Stack Overflow answers conflate them.

**How to avoid:**
- For the bot deep-link + OTP flow, you do NOT verify a Telegram-signed payload at all — the user's Telegram identity is established by them DMing the bot and the bot's `from.id` field arriving in the update. Trust the bot session, not a hash. This sidesteps the entire pitfall.
- If a future phase adds WebApp/Widget, write the verification helper with explicit unit-test vectors from Telegram's official docs.

**Warning signs:**
- A `verify_telegram_hash()` function with `hmac.new(BOT_TOKEN.encode(), ...)`.
- Tests pass only because the function returns `True` unconditionally during dev.

**Phase to address:** Phase B2.

---

### Pitfall 9 — OTP brute-force: 6-digit code + no rate limit + no max-attempts

**What goes wrong:**
Owner requests a login OTP — bot DMs `Code: 482917`. SPA prompts user to type it. There is no rate limit. Attacker who knows owner's phone/email tries `000000..999999`. 1M attempts at 50 RPS = 5.5 hours to crack any 6-digit code.

**Why it happens:**
"It's just an OTP" — but unlike SMS OTPs (where attempts are gated by carrier), this OTP submission goes through your API directly.

**How to avoid:**
- 6-digit code is fine **only if** combined with: max 5 attempts per code, per-IP rate limit (e.g. 10/minute) via Redis, code TTL = 10 minutes.
- Generate with `secrets.randbelow(10**6)` (NOT `random.randint`).
- After 5 fails, invalidate the code; next request requires a fresh OTP issuance.
- Lockout the user account for 15 minutes after 3 invalidated codes (slow learner detection).

**Warning signs:**
- Test that brute-forces a known OTP from inside the test in <1 second succeeds.
- No `auth.otp.attempts:<user_id>` key in Redis design.

**Phase to address:** Phase B2 (acceptance criterion: brute-force test must fail).

---

### Pitfall 10 — DM blocked by user → silent OTP delivery failure

**What goes wrong:**
User has never started a chat with the bot, or has blocked it. `bot.send_message(chat_id=...)` raises `Forbidden: bot was blocked by the user` or `Forbidden: bot can't initiate conversation with a user`. If the auth service swallows the exception, the SPA shows "Code sent" but no DM arrives. User stuck.

**Why it happens:**
The exception is asynchronous (the user can revoke the chat any time); naive code only handles the happy path.

**How to avoid:**
- The login flow MUST start with a deep-link button "Открыть бота → нажать /start" rendered on `/login`. Until the user has DMed the bot at least once, no OTP flow is attempted. Persist `telegram_chat_active=true` only after a successful update from that user.
- Catch `aiogram.exceptions.TelegramForbiddenError` (or PTB equivalent), and respond with `409 Conflict {code: 'bot_not_started'}` — UI shows "Откройте бот и нажмите /start" with the deep link.

**Warning signs:**
- Manual test: block the bot in Telegram → request OTP → no error returned to UI.

**Phase to address:** Phase B2.

---

### Pitfall 11 — Alembic autogenerate creates random constraint names → next autogenerate "drops and recreates" them

**What goes wrong:**
First migration `clients` table is autogenerated. SQLAlchemy assigns `pk_clients`, `uq_clients_phone_<random>` style names. Second migration adds an index, autogenerate sees existing constraint names differ from defaults → emits `op.drop_constraint(name='uq_clients_phone_abc123')` + recreate. CI fails. PRs accumulate noise.

**Why it happens:**
SQLAlchemy 2.0's `MetaData` does not enforce a naming convention by default. Postgres assigns random suffixes. Alembic's autogenerate compares names, not semantics.

**How to avoid:**
- In `app/core/database.py`, set the `Base.metadata` naming convention BEFORE the first model is defined:
  ```python
  NAMING_CONVENTION = {
      "ix": "ix_%(table_name)s_%(column_0_N_name)s",
      "uq": "uq_%(table_name)s_%(column_0_N_name)s",
      "ck": "ck_%(table_name)s_%(constraint_name)s",
      "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
      "pk": "pk_%(table_name)s",
  }
  metadata = MetaData(naming_convention=NAMING_CONVENTION)
  class Base(DeclarativeBase): metadata = metadata
  ```
- Set BEFORE the first migration is generated. After that, retrofitting requires a no-op rename migration.
- Test: `alembic revision --autogenerate -m "noop"` immediately after a fresh `alembic upgrade head` should produce an EMPTY migration body (no diff).

**Warning signs:**
- A migration whose `upgrade()` is mostly `drop_constraint` / `create_constraint` for tables you didn't touch.
- A fresh DB + autogenerate produces a non-empty diff.

**Phase to address:** Phase C1, BEFORE the first model is committed. Add a CI step `make alembic-check` that runs autogenerate on a clean DB and fails if the diff is non-empty.

---

### Pitfall 12 — Alembic autogenerate detects server-default drift on every run

**What goes wrong:**
You declare `created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)` (Python-side). DB has no `DEFAULT` clause. Then someone adds `server_default=text("now()")` to one model but not others. Autogenerate flips back and forth depending on which version of the file is loaded. Migrations pile up with `alter_column ... server_default`.

**Why it happens:**
Mixing Python-side `default=` with DB-side `server_default=` produces inconsistent autogenerate output. Alembic only sees DB-side defaults.

**How to avoid:**
- **Pick one rule and document it** in `docs/conventions.md`:
  - For `created_at`/`updated_at`: use `server_default=text("now()")` + `onupdate=text("now()")` so SQL handles it.
  - For business defaults that need Python logic: Python-side, no `server_default`.
- Add an ADR or section in conventions.md.
- Test: empty autogenerate diff on a fresh upgrade (same as Pitfall 11).

**Warning signs:**
- Migrations with `op.alter_column(..., server_default=...)` shortly after creation.

**Phase to address:** Phase C1.

---

### Pitfall 13 — UNIQUE constraint on `email` / `phone` blocks soft-deleted reuse

**What goes wrong:**
You soft-delete a client (`deleted_at = now()`). The phone `+7 999 ...` is preserved on the row. Another client signs up with the same phone — `IntegrityError: duplicate key value violates unique constraint`. Either the user is mysteriously locked out, OR you "fix" it by hard-deleting (defeating soft-delete) OR by overwriting (data loss).

**Why it happens:**
A plain `UNIQUE(phone)` constraint does not know about your `deleted_at IS NULL` semantic.

**How to avoid:**
- Use a **partial unique index** (Postgres feature):
  ```python
  __table_args__ = (
      Index("uq_clients_phone_alive", "phone", unique=True,
            postgresql_where=text("deleted_at IS NULL")),
  )
  ```
- Same for `email` if it ever becomes unique.
- Add an integration test: create client → soft-delete → create another with same phone → succeeds; same phone twice while alive → fails.

**Warning signs:**
- `IntegrityError` on routine signups in QA.
- "Why can't I add this client back?" support tickets.

**Phase to address:** Phase C1 (model definition) + Phase C2 (the test).

---

### Pitfall 14 — `deleted_at IS NULL` filter forgotten in one query → soft-deleted clients leak

**What goes wrong:**
You write `select(Client).where(Client.id == id)` somewhere and forget the `Client.deleted_at.is_(None)` predicate. Reception API returns the deleted client; sidebar count is wrong; DELETE-undo races appear; reports double-count.

**Why it happens:**
Ad-hoc queries scattered across `service.py`. Easy to forget.

**How to avoid:**
- **Repository helper**: `clients.list_alive(...)`, `clients.get_alive(id)`. Forbid raw `select(Client)` at module boundary by convention; accept it inside `repository.py` only.
- **Or** SQLAlchemy event hook: a `with_loader_criteria` pattern that auto-applies `deleted_at IS NULL` at the session level for all `Client` queries; opt out explicitly via `.execution_options(include_deleted=True)`.
- Add a test: `GET /clients` after `DELETE /clients/{id}` → deleted not in list; `GET /clients/{id}` → 404.

**Warning signs:**
- Reception sees an alive count of N, owner sees N+1.
- Search returns clients that don't open.

**Phase to address:** Phase C2.

---

### Pitfall 15 — `ON DELETE CASCADE` on related tables defeats soft-delete

**What goes wrong:**
You add `memberships` table with `client_id` FK and `ON DELETE CASCADE`. A future hard-delete ripples through. But you also try a hard-delete via Alembic in a future cleanup → memberships vanish silently.

**Why it happens:**
Mixing semantics: app does soft-delete, schema is wired for hard-delete cascade.

**How to avoid:**
- Default to `ON DELETE RESTRICT` for FKs. Hard-delete is a deliberate admin operation, not a side effect.
- Document soft-delete semantics in `docs/conventions.md`.

**Warning signs:**
- Migration with `ondelete='CASCADE'` while service code does `client.deleted_at = now()`.

**Phase to address:** Phase C1 (and revisit when `memberships` ships in v1.2).

---

### Pitfall 16 — Async session leak in DI: `yield session` without `async with` or commit/rollback discipline

**What goes wrong:**
Existing `get_db` already wraps the session in `async with session_factory()` — good. The trap is when someone refactors a service to take a session from a different source, or commits inside the route then yields again, leaving connections checked out under load.

**Why it happens:**
SQLAlchemy 2.0 async session lifecycle is unforgiving — every checkout MUST be released; pool starvation is silent.

**How to avoid:**
- Keep `get_db` as the ONLY session source for HTTP routes. `expire_on_commit=False` is already set.
- Service-layer functions accept `AsyncSession` as parameter — never construct their own.
- For ARQ workers, build a separate `worker_get_db()` that uses the same `app.state.sessionmaker` semantics.
- Test: load test 100 concurrent requests against a future endpoint with `pool_size=5`; should NOT timeout.

**Warning signs:**
- `sqlalchemy.exc.TimeoutError: QueuePool limit of size 5 overflow 10 reached` under load.
- Log lines about connection checkouts piling up.

**Phase to address:** Phase B1 / C2 (anywhere a new dependency is introduced).

---

### Pitfall 17 — `selectinload` vs `joinedload` mismatch on Clients list

**What goes wrong:**
You eager-load related rows on the list endpoint with `joinedload(Client.memberships)` (LEFT OUTER JOIN). Each client with N memberships explodes the row count by N. Pagination LIMIT counts the joined rows, not the distinct clients → page returns 8 clients when you asked for 20.

**Why it happens:**
`joinedload` is the SQLAlchemy default mental model from the docs but it's wrong for to-many on lists.

**How to avoid:**
- For collection lists with `to-many` relationships, use `selectinload` (issues a separate IN-query, no row explosion).
- For `to-one` relationships, `joinedload` is fine.
- v1.1 Clients has no related tables yet, so the rule is preventive — document it in `docs/conventions.md` so v1.2 (memberships) doesn't trip.

**Warning signs:**
- "Why does my page show 5 results when pageSize=20?" — your COUNT differs from your row count.

**Phase to address:** Phase C2 (document; no actual relationship to load yet).

---

### Pitfall 18 — Pytest fixture transaction not rolled back → cross-test bleed

**What goes wrong:**
A test creates a client; another test asserts the table is empty. Second test fails because the first's row leaked. Or worse: tests pass locally (one DB) and fail in CI (different DB starting state).

**Why it happens:**
Naive fixture: `db_session = sessionmaker()`; `await session.commit()` inside the test; nothing rolls back.

**How to avoid:**
- Use the SAVEPOINT pattern: open a connection, BEGIN, bind a session to that connection, after the test ROLLBACK the outer transaction. SQLAlchemy 2.0 supports this with `connection.begin_nested()` for nested savepoints so `session.commit()` inside the test maps to a savepoint release, not a real commit.
- Reference: SQLAlchemy docs "Joining a Session into an External Transaction".
- Alternative simpler approach: TRUNCATE all tables in a `function`-scoped fixture using `truncate ... restart identity cascade`. Slower but bulletproof.
- Add a meta-test: two tests in sequence, first inserts, second asserts empty — must pass.

**Warning signs:**
- Tests pass alone, fail when run together. Order-dependent failures.

**Phase to address:** Phase C1 (set up the fixture before the first model lands so the very first business test uses the right pattern).

---

### Pitfall 19 — `import-linter` breakage from auth wiring across modules

**What goes wrong:**
`modules/clients/router.py` calls `from app.modules.auth.permissions import require_permission` → violates the `modules-independent` contract. Or `core/middleware.py` imports `from app.modules.auth.session import get_current_user` for a security middleware → violates `core-not-depend-on-modules`. CI fails. Developer "temporarily" comments out the contract.

**Why it happens:**
RBAC naturally cuts across modules, and the obvious place to put `require_permission` is `modules/auth`, but every other module needs it.

**How to avoid:**
- **Decision: RBAC primitives live in `core`, not `modules/auth`.** Specifically:
  - `app/core/security.py` (or new `app/core/permissions.py`) contains: `Action`, `Resource`, `Role` types; `OWNER_ONLY` matrix; `can(role, action, resource)` function; `require_permission(action, resource)` FastAPI dependency.
  - `app/modules/auth` contains: login flow, OTP issuance, session creation, password hashing — i.e. AUTHENTICATION, not AUTHORIZATION.
  - `core` does not import `modules/auth` (still respects contract).
  - `modules/auth` may import `core/security.py` (allowed: `modules → core` is unrestricted).
  - `modules/clients` imports `core/security.py` for `require_permission` (allowed).
- Document this split in an ADR. Update `.importlinter` if needed (it currently does not forbid `core` from modules' callers, so this works as-is).

**Alternative (worse):** Put RBAC in a `app/shared/` layer. Adds a fourth box; not in line with current architecture.

**Warning signs:**
- An attempt to `from app.modules.auth import ...` from a non-auth module.
- `import-linter` CI failure with a "modules independence" violation.

**Phase to address:** Phase B3 — write the ADR before any cross-module import is needed.

---

### Pitfall 20 — `integrations/telegram` needs to call into `modules/auth` for OTP submission → contract violation

**What goes wrong:**
The Telegram bot handler receives `/start login_<token>` → needs to call into the auth module to mark the deep-link as confirmed and issue the OTP. Direct import `from app.modules.auth.service import confirm_telegram_login` violates `integrations-not-depend-on-modules`.

**Why it happens:**
Integrations naturally need to drive business logic. The contract was set in v1.0 without a real integration to test it.

**How to avoid:**
- **Inversion**: define a Protocol/ABC in `app/core/` (e.g. `core/auth_protocol.py`) like `class TelegramAuthCallback(Protocol): async def confirm_deep_link(self, token: str, telegram_user_id: int) -> None: ...`.
- `modules/auth` provides the concrete implementation and registers it in the FastAPI app/lifespan via DI.
- `integrations/telegram/bot.py` receives the protocol via constructor injection (NOT direct import).
- Or simpler: integrations expose endpoints, modules drive everything by hitting those endpoints. The bot handler calls `app.modules.auth.service.confirm(...)` is forbidden, so make the bot publish an event to ARQ; `modules/auth` has an ARQ task subscribed to that queue.
- Decide between **dependency injection via Protocol** (synchronous, simpler) and **event bus via ARQ** (decoupled, more moving parts). For 1 user / pet project, the Protocol approach wins on simplicity.

**Warning signs:**
- Integration code that needs to do business logic and looks at the import-linter contract as "in the way".

**Phase to address:** Phase B2, but the protocol should be defined in Phase B1 alongside the auth foundation work so B2 only writes the implementation.

---

### Pitfall 21 — `VITE_API_MODE` chokepoint bypassed by direct fetch in a one-off place

**What goes wrong:**
Login page is special — it doesn't fit the existing `services.X` pattern because there's no auth domain in the mock services. Developer writes a one-off `fetch('/api/v1/auth/login', ...)` in `routes/login.tsx`. ESLint `no-restricted-paths` doesn't trigger because `fetch` is not an import. Now there are two HTTP transports.

**Why it happens:**
The chokepoint is enforced on imports, not on fetch usage. New domain (auth) means a new service contract to define, but it's tempting to skip while bootstrapping.

**How to avoid:**
- Add `services/auth.ts` (mock + http variants) to `apps/admin-web/src/shared/api/services/` BEFORE writing the login route. Mock variant simulates the OTP flow against the existing role-toggle behaviour for backward compat with non-auth domains.
- Add an ESLint rule banning `fetch(` outside `packages/api-client/` and `shared/api/services/http/`. Use `no-restricted-syntax` with a CallExpression matcher.
- Add a negative-test fixture (already a pattern in this repo): `direct-fetch-leak.ts` that uses `fetch()` directly and is expected to fail lint.

**Warning signs:**
- Grep for `fetch(` outside the api-client package returns hits.

**Phase to address:** Phase E (and add the lint rule the same day).

---

### Pitfall 22 — TanStack Query cache poisoning when mock and HTTP shapes drift

**What goes wrong:**
Mock service returns `{ items, total, page, pageSize }`. HTTP service is hand-written and returns `{ data, total }` because the OpenAPI spec used `data`. Components destructure `data.items` from the query result; in mock mode it works; in http mode `items === undefined`. Or the reverse — types pass because they're `any` somewhere.

**Why it happens:**
Two source of truth (Zod contract on frontend + Pydantic schema on backend) drift apart. Codegen helps but only if it's actually wired.

**How to avoid:**
- `packages/api-client` is typed via `openapi-typescript` codegen against `openapi.json`.
- The HTTP service implementations live in `apps/admin-web/src/shared/api/services/http/` and import types from `@sportzal/api-client`. They are thin pass-throughs that reshape ONLY when necessary.
- The Zod contract in `shared/api/contracts/` is the SINGLE source for both mock validation AND form schemas; if backend Pydantic shape differs, fix backend or fix contract — never tolerate silent reshape.
- Add a **contract test**: for each HTTP service function, both mock and http variants must satisfy the same Zod contract; run a Vitest that calls each variant against a recorded fixture and validates with the contract Zod.

**Warning signs:**
- TS `any` creeping into service signatures.
- Bug "list shows 0 results in http mode but works in mock mode".

**Phase to address:** Phase D (codegen + types) + Phase E (contract test).

---

### Pitfall 23 — Pydantic `Optional[str]` ≠ JSON Schema `nullable` in TS codegen

**What goes wrong:**
Pydantic v2 model: `email: Optional[str] = None`. FastAPI's OpenAPI emits this as `{"type": "string", "nullable": true}` (or similar). `openapi-typescript` codegen produces `email?: string | null`. Frontend expects `email?: string`. Code compiles in some places but blows up at runtime when the field is `null` and a UI does `email.toLowerCase()`.

**Why it happens:**
Three concepts collide: optional (key may be absent), nullable (value may be null), and Pydantic's tendency to map `Optional[T]` to BOTH.

**How to avoid:**
- Pick a convention: optional fields use `field: str | None = None`. In schemas, `model_config = ConfigDict(...)` set explicitly so JSON Schema emits `nullable: true` consistently.
- TS side: prefer `email: string | null` (nullable) over `email?: string` (optional) for backend-driven fields. Fields that are truly absent (UPSERT inputs) stay optional.
- Add a test that snapshots a representative `openapi.json` and checks the TS gen output for sanity on at least one nullable field.

**Warning signs:**
- TS errors like `Object is possibly 'null'` in places you didn't expect.

**Phase to address:** Phase D.

---

### Pitfall 24 — Generic `Page[T]` does not survive openapi-typescript codegen cleanly

**What goes wrong:**
You define `Page[T] = { items: list[T]; total: int; page: int; pageSize: int }` in Pydantic and use it as `Page[ClientRead]` in `GET /clients`. FastAPI's OpenAPI emits `PageClientRead` as a concrete schema. `openapi-typescript` produces `PageClientRead` — but if `Page` is reused in 6 places, you get 6 differently-named schemas, all structurally identical. Frontend can't share a single `Page<T>` helper without manual aliasing.

**Why it happens:**
JSON Schema has no generics; FastAPI's response_model emits monomorphized schemas.

**How to avoid:**
- Embrace it: backend defines `Page[T]` once, frontend does `type ClientsPage = components['schemas']['PageClientRead']` then `type Page<T> = { items: T[]; total: number; page: number; pageSize: number }` as a hand-written generic helper, asserted equal at compile time.
- Or: rename Pydantic generic to use a deterministic suffix and document it.
- Add `pageSize` (camelCase) consistently. Decide on snake_case vs camelCase early — see Pitfall 25.

**Warning signs:**
- TS file with `PageClientRead`, `PageMembershipRead`, `PageVisitRead` repeated, no shared helper.

**Phase to address:** Phase D.

---

### Pitfall 25 — Snake_case vs camelCase boundary not decided → silent field rename storm

**What goes wrong:**
Backend uses `page_size`. Frontend reads `pageSize` (matches existing mock contract). Field is missing in the http-mode payload. Or the codegen produces a snake_case TS field, breaking 200 callsites in the existing frontend.

**Why it happens:**
Python convention vs JS convention.

**How to avoid:**
- Pydantic v2: `model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)` on a base model class; all response schemas inherit. JSON output is camelCase; Python attribute names stay snake_case.
- Document this in `docs/conventions.md`.
- Test: generate `openapi.json`, grep for `page_size` — should not appear in any schema property.

**Warning signs:**
- Frontend sees `page_size` in network responses.
- TS types contain snake_case identifiers.

**Phase to address:** Phase C2 (response model) + Phase D (codegen sanity test).

---

### Pitfall 26 — `openapi.json` regenerated at runtime → CI flake on drift check

**What goes wrong:**
The plan: `make openapi-export` writes `openapi.json` to disk; CI runs `git diff --exit-code openapi.json` to fail on drift. But the export script `from app.main import app; print(app.openapi())` triggers FastAPI lifespan (DB connect) → fails in CI without a DB → developer adds a fallback that initializes the app differently → output differs from local → drift check fails for unrelated reasons.

**Why it happens:**
FastAPI lifespan is required for some app behaviours but not for OpenAPI generation; the schema generation happens lazily on first call.

**How to avoid:**
- Build the FastAPI app in a way that allows `app.openapi()` to be called without entering the lifespan context (it normally can — `app.openapi()` is sync and pure if no `Depends` requires startup data).
- Ensure no top-level code in routers runs DB queries on import.
- Run the export script in CI with `DATABASE_URL=postgresql+asyncpg://localhost/none` and `SKIP_LIFESPAN=true` (a flag that short-circuits db connect at app startup, mirroring what tests do).
- Stable JSON serialization: write with `indent=2, sort_keys=True` so byte-for-byte diffs are stable across Python versions.
- Add the export to CI BEFORE codegen so `openapi.json` always matches the running backend.

**Warning signs:**
- `openapi.json` diff on a PR that touched no API code.
- Different output on Mac vs Linux (sorting issue).

**Phase to address:** Phase D.

---

### Pitfall 27 — Frontend `can()` and backend `require_permission` drift silently

**What goes wrong:**
Frontend `can.ts` says owner-only `delete clients`. Backend forgets the check on `DELETE /clients/{id}` because the dev "knows reception will never click it" (UI hides the button). Reception calls the endpoint via DevTools → succeeds → unauthorized delete.

**Why it happens:**
Two source-of-truth lists in two languages. Easy to add a new owner-only resource on one side and forget the other.

**How to avoid:**
- Single source of truth for the matrix:
  - **Option A (harder, best)**: backend exports `OWNER_ONLY` from `core/security.py` to a JSON file; frontend `can.ts` imports/syncs from that JSON via build step. Diff in CI fails if drifted.
  - **Option B (lighter, acceptable for pet project)**: keep both lists, add a single test on each side that snapshots the matrix, and a daily CI parity test (a script reads both, compares, fails if different).
- Add a backend test for EACH `OWNER_ONLY` pair: as `reception`, hitting the endpoint returns 403.
- Add a backend dependency `require_permission(action, resource)` and a centralized test that enumerates ALL routes and asserts each protected route has the dependency wired (introspection via `app.routes`).

**Warning signs:**
- `can.ts` adds an entry; backend service has no corresponding check (grep).

**Phase to address:** Phase B3 + Phase C2.

---

### Pitfall 28 — 404 vs 403 information leakage in list endpoints

**What goes wrong:**
Reception can list clients (OK by RBAC) but cannot view/delete a particular client's PII (owner-only field). API returns the row in the list but 403s on `GET /clients/{id}`. Reception now knows the client exists. Worse: if reception is ever scoped (future multi-tenant), this leaks IDs across tenants.

**Why it happens:**
Two layers of access (collection-level vs row-level) implemented inconsistently.

**How to avoid:**
- For v1.1 (single tenant, 1-2 users), reception can see clients fully. The OWNER_ONLY list does NOT include `view clients` — only `delete clients`. Confirm against `can.ts` (which has `{action:'delete', resource:'clients'}` only — good).
- Document the rule: "if you can see the list, you can see the detail" in `docs/conventions.md`.
- For future multi-tenant, plan to introduce row-level filters; not in scope for v1.1.
- Test: as reception, `GET /clients` returns the list; `GET /clients/{id}` returns 200; `DELETE /clients/{id}` returns 403.

**Warning signs:**
- Test matrix has a row with "list: yes, detail: no" — that row is the leak risk.

**Phase to address:** Phase B3.

---

### Pitfall 29 — Permission check happens AFTER side effect

**What goes wrong:**
```python
async def delete_client(id, current_user, db):
    client = await db.get(Client, id)
    client.deleted_at = datetime.utcnow()
    require_permission('delete', 'clients')(current_user)  # too late
    await db.commit()
```
Side effect (mutation) precedes the permission check. If anyone reorders the lines, deletion happens for unauthorized users until the commit raises.

**Why it happens:**
Permission check feels like a post-condition; copy-paste from another service that did it post-hoc.

**How to avoid:**
- Use a FastAPI dependency `Depends(require_permission('delete', 'clients'))` on the route signature — runs BEFORE the handler body, so 403s never enter the service.
- Service-layer functions take `current_user` only as audit data, not as gatekeeper.
- Test: with reception role, `DELETE /clients/{id}` → assert client row in DB is unchanged AND status is 403.

**Warning signs:**
- A `require_permission(...)` call inside a service function body.

**Phase to address:** Phase B3 (write `require_permission` as a dependency, not a callable).

---

### Pitfall 30 — Login redirect loop when refresh fails

**What goes wrong:**
TanStack Query's automatic retry (default 1 retry) sees 401 → calls `/auth/refresh` → also 401 (refresh expired) → redirects to `/login` → `/login` happens to fire a query that requires auth (e.g. /me) → 401 → refresh → 401 → loop. Browser pegs at 100% CPU.

**Why it happens:**
Retry policy is global; auth endpoints don't opt out; `/login` page is not strictly anonymous.

**How to avoid:**
- In the api-client fetch wrapper: 401 on `/auth/*` endpoints does NOT trigger refresh.
- TanStack Query: `retry: (failureCount, error) => error.status !== 401`.
- Refresh endpoint failure → call `auth.logout()` + `router.navigate('/login')` ONCE (use a module-scoped flag to ensure it's idempotent).
- `/login` route does not call `/me` (it's the unauthenticated landing).
- Test: stub `/auth/refresh` to 401; load `/clients`; assert exactly ONE redirect to `/login`, no further requests.

**Warning signs:**
- DevTools network tab shows hundreds of `/auth/refresh` calls in a second.

**Phase to address:** Phase E.

---

### Pitfall 31 — Form Zod schema and Pydantic schema diverge → "looks valid" / "rejected by server"

**What goes wrong:**
`react-hook-form` + Zod accepts a phone formatted `+7 999 1234567`. Pydantic schema regex demands `+7\d{10}`. UI shows green; submit returns 422; UI generic error toast. User stuck.

**Why it happens:**
Two languages, two schema files, no enforcement.

**How to avoid:**
- Codegen TS types from openapi handles the SHAPE. Validation rules (regex, min/max) are NOT round-tripped fully.
- Strategy: Pydantic schema is canonical; `openapi.json` exposes regex via `pattern`. Use a small adapter that converts JSON-schema fragments into Zod (e.g. `json-schema-to-zod`) for the validation rules — generated next to types in `packages/api-client`.
- Or: keep validation duplicated but add a backend test that for every response 422 caused by a known validation rule, the frontend Zod also rejects it (run frontend Zod against the same payload in a Node test).
- Pragmatic for pet project: write Zod for FE forms; rely on server 422 mapping for the long tail; design 422 responses with `fields` map so UI can highlight the offending field.

**Warning signs:**
- Recurring 422s on what UI claimed was valid.

**Phase to address:** Phase E (server returns structured 422; UI maps to RHF setError per-field).

---

### Pitfall 32 — Clock skew between API container and DB → JWT iat/exp invalid

**What goes wrong:**
Backend container clock is 30 seconds behind. Token issued at `iat=10:00:00` is "valid in the future" from a strict client's perspective; or token is rejected because `exp` slipped past while the request was in flight.

**Why it happens:**
Container clocks drift if NTP is not configured. Docker on macOS occasionally has clock drift after sleep.

**How to avoid:**
- Allow a small `leeway` (e.g. 30s) in the JWT validation library: `jwt.decode(..., leeway=30)`.
- For the Telegram OTP, similar: TTL counted in seconds, but expiry check uses `now() - leeway`.
- In dev runbook, restart docker after sleep if seeing weird auth failures.

**Warning signs:**
- Auth fails immediately after mac sleep/wake; works after `docker restart backend`.

**Phase to address:** Phase B1.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Skip CSRF token, rely on SameSite=Lax + Origin check | Less code, no token plumbing | XS-Leaks / future cross-site scripting → full CSRF surface | OK for v1.1 (1-2 users); revisit when client-web ships in Phase J |
| Hash/compare refresh tokens with SHA-256 only (no HMAC) | Simpler than per-tenant secret | Rainbow-table-ish risk if Redis dump leaks | Acceptable; the tokens are random 32-byte, not derived from anything |
| 6-digit OTP instead of 8-digit | Easier to type | 100x weaker brute-force; relies on rate-limit | Only acceptable WITH rate-limit + max-attempts |
| Skip openapi-typescript codegen, hand-write TS types | Faster start | Drift between FE/BE; "shape mismatch" bugs | Never — codegen is in scope for v1.1 |
| Single-process backend (no separate worker for Telegram) | Less infra | Telegram polling holds an event loop slot, can starve API in dev | Acceptable in dev; production must split (in scope when prod ships) |
| Hardcode `OWNER_ONLY` in two places (BE + FE) without sync | No build step | Drift between client and server permissions | OK only if covered by a daily CI parity test |
| Frontend stores Telegram-deep-link state in localStorage | Simple | Open second tab → state confusion | Acceptable; document and accept; alternative is server-state (more code) |
| Use `expire_on_commit=False` (already set) | Less reload boilerplate | Stale ORM objects across commit boundaries | Already locked in; just be aware |
| `package_size` (camelCase) only on the wire, snake_case in Python | Idiomatic both sides | One more piece of config | Standard practice; not really debt |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Telegram (aiogram/PTB) | Mixing async aiogram with FastAPI sync handlers; calling bot inside a request handler with no await | Bot lives in a separate ARQ worker / dedicated polling process; HTTP handlers enqueue jobs |
| Telegram bot startup | Bot polling started in FastAPI lifespan → blocks startup if Telegram is slow | Polling lives in its own process; backend lifespan only initializes the bot client (no `start_polling`) |
| Telegram identity | Using `@username` to identify a user | `from.id` (numeric Telegram user ID) is the only stable identifier; @username is mutable and may be absent |
| ЮKassa (future, not v1.1) | Using sandbox URL in prod, or vice versa; testing webhook signature with wrong secret | Pin the API URL via env; fixture-test webhook signature verification |
| Redis (auth sessions) | Sharing Redis 0-DB with ARQ queues → key collisions | Reserve DB indices: `0` for ARQ, `1` for sessions; or prefix all session keys with `auth:session:` |
| Postgres asyncpg | Setting `pool_size` too high → starves Postgres `max_connections` | Default `pool_size=5, max_overflow=10`; document Postgres `max_connections=100` in dev |
| Alembic | Running `alembic upgrade head` against a DB that has live connections from the API → rare lock conflict | Run migrations as a one-off compose step (already done in v1.0); never from a running API process |
| Docker compose dev | Backend can't reach `localhost:5432` because Postgres is on a docker network | Use service name `postgres` in connection string; documented in `.env.example` |
| openapi-typescript | Running codegen against a stale `openapi.json` | CI step: regenerate `openapi.json` from running backend before codegen; fail on git diff |

---

## Performance Traps

(Mostly preventive — pet project on 1 gym likely tops out at ~5 concurrent users in v1.1.)

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| `joinedload` on to-many in list endpoints | Page returns N < pageSize results | Use `selectinload` for to-many | First time a list adds eager-loaded relations (Phase v1.2 memberships) |
| ILIKE on `name` without index | Search slows linearly with table size | `CREATE INDEX clients_name_trgm ON clients USING gin (name gin_trgm_ops)` (after pg_trgm extension); or simpler: lower(name) btree for prefix search | When clients > ~10k rows |
| N+1 on permission resolution | Slow list endpoints | RBAC is matrix-only (no DB lookup); permission check is O(1) | Won't break in v1.1; flagged for future ACL system |
| Redis SCAN to enumerate user sessions | Slow when sessions per user > 100 | Maintain a `auth:user:<id>:families` set so revoke-all is `SMEMBERS` + `DEL` | Pet project: never |
| OpenAPI generation on every request | Slow `/docs` page | FastAPI caches `app.openapi_schema`; export to JSON file for codegen | Already handled by FastAPI |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Storing `bot_token` in repo / unencrypted env | Total bot takeover | `.env.example` has placeholder only; real `.env` git-ignored; doc requires loading via secrets manager in prod |
| Logging full JWT or refresh token in structlog | Leak via log shipping | Add a structlog processor that redacts `Authorization`, `Cookie`, `set-cookie`, `refresh_token` keys |
| Logging OTP code at `INFO` level for "debug" | OTPs in logs forever | Never log OTP; only log `otp_issued` event with user_id and code_id (random uuid), not the digits |
| Returning password-hash via `/me` endpoint due to bare ORM dump | Hash leak (offline crack) | Always go through Pydantic response model that excludes `password_hash`; add a test that asserts no password fields in any 200 response body |
| Using `hashlib.md5` or `sha1` for password storage | Reversible / cheap to crack | Use `argon2-cffi` (or `passlib[argon2]`); document in `core/security.py` |
| Same JWT signing key in dev and prod | Dev key stolen → prod compromised | Per-environment `JWT_SECRET`; rotate on prod; document key-rotation plan in ADR |
| Telegram bot reused across staging/prod | Test message sent to real users | Separate bot per environment; `TELEGRAM_BOT_USERNAME` env-driven; doc lists 3 bots: dev, staging, prod |
| Including PII (phone) in URL paths | Logged by reverse proxies | Use IDs in paths; phone goes in body or query (also log-redacted) |
| Soft-deleted client's phone re-used by a returning client | Privacy: returning user inherits old user's notes | Soft-delete preserves the row but clears any unique-by-design fields (or use partial unique index, see Pitfall 13) |
| `Optional[str]` allows `""` to bypass length validation | Empty strings stored | Pydantic v2: `field: Annotated[str, StringConstraints(min_length=1)]` for required-non-empty fields |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| OTP flow with no "resend" button or no countdown | User taps "send" twice, gets confused | Show countdown ("Запросить новый код через 0:42"); button disabled until 0; backend rate-limits anyway |
| Generic "Something went wrong" on 422 form errors | User can't fix the form | 422 response carries `fields: { phone: 'invalid_format' }`; FE maps to RHF `setError` per-field |
| Login page doesn't preserve "where I was going" | User logs in → lands on home, not the page they tried to open | TanStack Router: `beforeLoad` of protected route stores `redirect` in search; login page reads it |
| Telegram-only auth with no "what if I don't have Telegram" affordance | Locked out users | Email/password fallback is exposed prominently on login (already in scope) |
| Reception sees "Удалить" button greyed out with no tooltip | Confusion | RoleGate already handles this; ensure tooltip "Только для владельца" is present |
| Loading state for OTP submit indistinguishable from idle | User taps submit twice | Disable button on submit; show inline spinner |
| Cookie-expired UI behaviour: silent logout mid-action | User loses unsaved form state | Detect 401; if form is dirty, show modal "Сессия истекла. Войдите снова, чтобы сохранить" with re-login modal that doesn't unmount the form |

---

## "Looks Done But Isn't" Checklist

- [ ] **Cookie auth:** SameSite, Secure (env-driven), Path scoping (refresh on `/auth/refresh` only), HttpOnly — all four flags set?
- [ ] **Refresh rotation:** family tracking + reuse-detection + single-flight on client + small reuse window — all four pieces?
- [ ] **OTP:** 6-digit + rate limit per IP + max attempts per code + code TTL + invalidation on success/fail — all five?
- [ ] **Telegram bot:** /start handler + DM-blocked handling + deep-link state expiry + bot-not-started UX — all four?
- [ ] **First Alembic migration:** naming convention set + autogenerate-on-clean produces empty diff + server_default convention documented — all three?
- [ ] **Soft-delete:** `deleted_at` column + partial unique index on phone + service-layer filter helper + tests for all three — all four?
- [ ] **import-linter:** RBAC primitives in `core` + auth integration uses Protocol injection + CI run green — all three?
- [ ] **`require_permission`:** is a FastAPI dependency on route signature, NOT a service-body call — verified by AST grep?
- [ ] **OpenAPI:** `openapi.json` checked into repo + CI drift check + lifespan-safe export script + camelCase aliases — all four?
- [ ] **api-client:** typed via codegen + cookie credentials + single-flight refresh + retry-policy excludes /auth — all four?
- [ ] **Login UX:** redirect-back works + 401 doesn't loop + form errors map to fields + Telegram-blocked has UX — all four?
- [ ] **Logging:** secrets redacted (Authorization, Cookie, refresh_token, OTP digits) — verified by a snapshot test?
- [ ] **CSRF:** strategy decided in ADR + tested with cross-origin POST returning 403 — both?

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Refresh-token rotation race causing mass logout | LOW | Restore single-flight on client; add reuse window on server; users re-login once |
| Naming convention forgotten on first migration | MEDIUM | Write a no-op rename migration that aliases existing constraints to convention names; squash if early enough |
| Soft-delete unique conflict in production | MEDIUM | Add partial unique index in a new migration; data fix script for existing collisions (ALTER row to NULL out phone of duplicates oldest-first) |
| OTP brute-forced (theoretical) | HIGH | Force password reset for all users; rotate JWT_SECRET; review Redis attempt-count keys |
| `import-linter` violation merged because someone added `# noqa` | LOW | CI catches it on every PR; revert and refactor through Protocol injection |
| Frontend `can()` drifted from backend `OWNER_ONLY` | LOW | Parity test fails; sync the lists; add the missing 403 server-side check; ship a hotfix |
| `openapi.json` drift breaks codegen CI | LOW | Re-run export + commit JSON + commit regenerated TS types |
| CSRF found in pen test | MEDIUM | Add double-submit token; deploy; require fresh login (so old sessions hit the new flow) |
| Stored refresh tokens in plaintext (Redis dump leaked) | HIGH | Rotate JWT_SECRET; invalidate all session families; force re-login; add hash storage in same release |
| Cookie `Secure=True` shipped to dev (broken auth) | LOW | Hotfix env-driven flag; document |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1 — SameSite=Strict breaks Telegram return | B1 | Test: cross-site GET preserves cookie |
| 2 — Secure dropped in dev | B1 | Settings test asserts prod requires Secure=True |
| 3 — CSRF wide open | B1 + C2 | Cross-origin POST test returns 403 |
| 4 — Refresh rotation race | B1 + D | Two parallel queries + expired access → exactly one /refresh call |
| 5 — Plaintext refresh tokens | B1 | Redis snapshot test: no key contains the literal token |
| 6 — Sessions not revoked on password change | B1 | Test: change password → old refresh returns 401 |
| 7 — Telegram widget instead of bot | B2 | ADR locks bot deep-link |
| 8 — Telegram hash with wrong secret | B2 | N/A (bot deep-link sidesteps); guarded by ADR |
| 9 — OTP brute-force | B2 | Test: 100 wrong codes in a row → account locked |
| 10 — DM blocked silent fail | B2 | Manual test + 409 path coverage |
| 11 — Random Alembic constraint names | C1 | autogenerate-on-clean produces empty diff |
| 12 — Server-default drift | C1 | Same as 11 + convention doc |
| 13 — Soft-delete uniqueness conflict | C1 | Test: soft-delete then recreate same phone succeeds |
| 14 — Forgotten deleted_at filter | C2 | Test enumerates list/get endpoints; deleted client is invisible |
| 15 — CASCADE defeats soft-delete | C1 | Migration review: no CASCADE on FKs to clients |
| 16 — Async session leak | B1/C2 | Load test does not exhaust pool |
| 17 — joinedload row explosion | C2 | Document; no relations in v1.1 |
| 18 — Test transaction bleed | C1 | Meta-test: insert + assert empty in next test |
| 19 — RBAC import-linter break | B3 | CI green; no `from app.modules.auth import` outside auth |
| 20 — Telegram → modules/auth violation | B1+B2 | Protocol defined in core; integration uses DI |
| 21 — VITE_API_MODE bypass | E | ESLint rule + negative-test fixture |
| 22 — Cache shape drift | D + E | Contract test: mock+http both validate same Zod |
| 23 — Optional vs nullable | D | Snapshot test of TS gen for a representative nullable field |
| 24 — Generic Page<T> | D | Hand-written `Page<T>` helper + alias usage doc |
| 25 — Snake vs camelCase | C2 + D | Grep `openapi.json`: no snake_case property names |
| 26 — openapi.json regen flake | D | CI step uses lifespan-safe export script |
| 27 — RBAC parity drift | B3 + E | Daily CI parity test on OWNER_ONLY |
| 28 — 404 vs 403 leakage | B3 | Documented rule; test matrix |
| 29 — Permission check after side effect | B3 | `require_permission` is a Depends; AST grep forbids in service body |
| 30 — Login redirect loop | E | Stub /auth/refresh to 401 → exactly one navigate |
| 31 — Zod ↔ Pydantic drift | E | Structured 422 with `fields`; FE maps to RHF setError |
| 32 — Clock skew | B1 | Leeway=30s in JWT validation |

---

## Anti-Pitfalls (don't over-engineer for 1 gym)

These are NOT pitfalls — they're things the team should NOT do despite "best practices" articles.

- **Do NOT add Keycloak / Auth0 / OIDC**. v1.1 needs Telegram bot OTP + email/password. JWT + Redis is enough.
- **Do NOT add Casbin / Oso / OPA policy engines**. The `OWNER_ONLY` matrix is 9 entries. A function in `core/security.py` is the right size.
- **Do NOT add an audit-trail framework** (e.g. SQLAlchemy-Continuum). Add a single `events` table when needed; v1.1 doesn't need it.
- **Do NOT design for multi-tenant** (no `tenant_id` columns, no `SET LOCAL`, no RLS). Locked in PROJECT.md "Out of Scope".
- **Do NOT build a session-management UI** ("active sessions" / "log out elsewhere"). Pet project, 1-2 users; revoke-all on password change is sufficient.
- **Do NOT add OAuth scopes**. Two roles, both authenticated. Scopes are pointless.
- **Do NOT add SAML / SSO**. No.
- **Do NOT add a separate `iam-service`**. Modular monolith; auth is a module, not a service.
- **Do NOT auto-rotate JWT signing key on each deploy**. Manual rotation with a 24h overlap window when needed (probably never in v1.1).
- **Do NOT add MFA** beyond the OTP. The Telegram OTP IS the second factor for the email/password fallback (effectively).

---

## Sources

- FastAPI Security docs (cookies, OAuth2 password flow): https://fastapi.tiangolo.com/tutorial/security/ — HIGH confidence
- SQLAlchemy 2.0 async session lifecycle + naming convention: https://docs.sqlalchemy.org/en/20/core/constraints.html#configuring-constraint-naming-conventions — HIGH
- Alembic autogenerate cookbook: https://alembic.sqlalchemy.org/en/latest/autogenerate.html — HIGH
- Telegram Bot API & deep-linking: https://core.telegram.org/bots/features#deep-linking and https://core.telegram.org/widgets/login — HIGH (deep-linking via `t.me/<bot>?start=<param>`)
- aiogram 3.x async patterns: https://docs.aiogram.dev/ — MEDIUM (specific to library choice)
- OWASP cookie attributes / SameSite RFC 6265bis — HIGH
- openapi-typescript caveats (nullable vs optional, generic monomorphization): https://github.com/openapi-ts/openapi-typescript/blob/main/docs/cli.md — HIGH
- Pydantic v2 alias_generator + populate_by_name: https://docs.pydantic.dev/2.0/migration/#changes-to-config — HIGH
- TanStack Query retry policy: https://tanstack.com/query/latest/docs/framework/react/reference/useQuery — HIGH
- Postgres partial unique index: https://www.postgresql.org/docs/current/indexes-partial.html — HIGH
- Codebase artefacts referenced:
  - `apps/backend/.importlinter` (3 contracts already in place)
  - `apps/backend/app/core/middleware.py` (request-id ordering ADR pattern)
  - `apps/backend/app/core/database.py` (existing async session setup, no naming convention yet)
  - `apps/backend/alembic/env.py` (async env, empty target metadata)
  - `apps/admin-web/src/shared/session/can.ts` (OWNER_ONLY matrix, 9 entries)
  - `apps/admin-web/CLAUDE.md` (`VITE_API_MODE` chokepoint, pagination contract)

---
*Pitfalls research for: v1.1 Auth + Clients on the existing FastAPI modular-monolith skeleton + admin-web frontend with mock services*
*Researched: 2026-05-01*
