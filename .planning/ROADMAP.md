# Roadmap: Sportzal

## Milestones

- ✅ **v1.0 Phase A: Skeleton** — Phases 1-3 (shipped 2026-05-01) — see [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- 🚧 **v1.1 Auth + Clients** — Phases 4-10 (planning 2026-05-01)

## Phases

<details>
<summary>✅ v1.0 Phase A: Skeleton (Phases 1-3) — SHIPPED 2026-05-01</summary>

- [x] Phase 1: Monorepo Restructure & Frontend Move (3/3 plans) — completed 2026-04-30
- [x] Phase 2: Backend Skeleton with Quality Tooling (8/8 plans) — completed 2026-04-30
- [x] Phase 3: Tests, Dev Infrastructure & Documentation (6/6 plans) — completed 2026-05-01

Full details: [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)

</details>

### 🚧 v1.1 Auth + Clients (Phases 4-14)

- [ ] **Phase 4: Auth Foundations & Cookie/RBAC Primitives** — Lift JWT/Argon2/cookie/RBAC primitives into `core`, set Alembic naming convention, flip pagination contract, rename `members` → `clients`
- [ ] **Phase 5: User Schema + Email/Password Auth** — First business migration; `/auth/login|refresh|logout|logout-all|me` end-to-end with refresh-rotation family + Redis sessions
- [ ] **Phase 6: RBAC Wiring + Parity Tests** — `require_permission` as Depends on every business route, CSRF dependency, byte-parity test against frontend `can.ts`, route-introspection guard
- [ ] **Phase 7: Telegram OTP Channel** — Standalone bot worker (ptb 22 long-polling), deep-link + 6-digit OTP flow, ARQ send-OTP task, DM-blocked → 409 path
- [ ] **Phase 8: Clients Module + Audit Log** — First business CRUD with soft-delete partial unique index, ILIKE/`pg_trgm` search, owner-only delete, `audit_log` writes from auth + clients
- [ ] **Phase 9: OpenAPI Pipeline + packages/api-client** — Lifespan-safe OpenAPI export, CI drift gate, `openapi-typescript` codegen, hand-rolled `fetcher.ts` with single-flight refresh + typed `ApiError`
- [x] **Phase 10: admin-web Auth + Clients Wiring** — `VITE_API_MODE=http` for `/login` + `/clients/*` only; Telegram + email/password tabs; ESLint ban on raw `fetch(`; redirect-back + 401-loop guard (completed 2026-05-04)
- [x] **Phase 11: Clients HTTP-mode Shape Adapter** *(gap closure — must)* — DTO mappers `ClientResponse ↔ Client` and `ClientCreate/UpdateInput ↔ ClientCreate/UpdateRequest` so `VITE_API_MODE=http` clients flow actually works against the live backend (closes INTEGRATION-CHECK F-01, F-02) (completed 2026-05-04)
- [x] **Phase 12: v1.1 Verification Backfill** *(gap closure — should)* — Produce `09-VERIFICATION.md`, refresh `10-VERIFICATION.md`, run Phase 6 live RBAC integration tests on Postgres+Redis, take Phase 8 CR-01 acceptance decision (completed 2026-05-05)
- [ ] **Phase 13: v1.1 Minor Drift & Hygiene Cleanup** *(gap closure — should)* — Drop dead `expiresAt` from Telegram contracts, replace `as never` query-string casts with typed `query` param in api-client, delete empty `app/modules/members/`, add `TELEGRAM_BOT_*` safe defaults, add vitest to `@sportzal/api-client`, refresh REQUIREMENTS.md `Pending → Complete`, backfill SUMMARY frontmatter (closes F-03, F-04, F-06 + procedural debt)
- [ ] **Phase 14: Clients Search PII Hardening** *(gap closure — should, security)* — LIKE-escape `%`/`_`/`\` in `clients.list_alive` ILIKE pattern, with regression test that `?q=%25` matches the literal `%` and not the wildcard (closes Phase 8 CR-01 PII security warning)

## Phase Details

### Phase 4: Auth Foundations & Cookie/RBAC Primitives
**Goal**: Land all cross-cutting primitives (JWT, Argon2, cookies, RBAC matrix, Alembic naming, pagination contract, camelCase wire format) before the first business migration so they cannot be retrofitted later.
**Depends on**: Phase 3 (v1.0 skeleton complete)
**Requirements**: INFRA-01, INFRA-02, INFRA-05, INFRA-07, AUTH-01, AUTH-02, AUTH-03, AUTH-04, CSRF-01, RBAC-01, API-03, API-04
**Success Criteria** (what must be TRUE):
  1. A developer can import `Role`, `Action`, `Resource`, `OWNER_ONLY`, `can()` from `app.core.permissions` and the `OWNER_ONLY` set is byte-equal as a `frozenset` of `(action, resource)` pairs to `apps/admin-web/src/shared/session/can.ts`.
  2. A developer can encode a JWT, hash and verify an Argon2id password, and generate an OTP/deep-link token via `app.core.security`; passwords and OTP codes are never persisted in plaintext (only hashes).
  3. Running `alembic revision --autogenerate -m noop` against a clean Postgres immediately after `alembic upgrade head` produces an empty migration body — proving `MetaData(naming_convention=...)` is set before any business model lands.
  4. `app/modules/members/` no longer exists; `app/modules/clients/` is its successor and `.importlinter` `modules-independent` contract lists `clients` (not `members`); `lint-imports` stays GREEN.
  5. `app.core.pagination.Page[T]` exposes `{items, total, page, pageSize}`; a Pydantic base response/request model with `alias_generator=to_camel` + `populate_by_name=True` is in place; FastAPI's emitted JSON (sample response) contains no `snake_case` property names.
**Plans:** 9 plans
- [x] 04-01-PLAN.md — Dependencies + Settings extension (pyjwt/argon2-cffi/python-telegram-bot deps + 4 new env-driven Settings fields)
- [x] 04-02-PLAN.md — Module rename `members → clients` + `.importlinter` update; `lint-imports` GREEN
- [x] 04-03-PLAN.md — DB foundations (Base.metadata naming_convention + UUIDPkMixin/TimestampMixin/SoftDeleteMixin)
- [x] 04-04-PLAN.md — RBAC primitives (`Role`/`Action`/`Resource` StrEnums + `OWNER_ONLY` frozenset + `can()`) + 3 new exception subclasses
- [x] 04-05-PLAN.md — Wire-format contract `app/core/schemas.py` (ContractModel hierarchy + ResponseEnvelope[T] + ProblemDetails)
- [x] 04-06-PLAN.md — Pagination rewrite (PageQuery + PaginatedData[T]); old LimitOffsetParams/Page[T] deleted
- [x] 04-07-PLAN.md — Security helpers (JWT HS256, Argon2id, OTP/deep-link/refresh/CSRF generators, `issue_session_cookies`)
- [x] 04-08-PLAN.md — Dependencies scaffold (CurrentUser Protocol + register_user_loader + get_current_user + require_permission)
- [x] 04-09-PLAN.md — Verification suite (4 unit tests + alembic-clean integration test — Phase 4 SC #1/#3/#5 gates)

### Phase 5: User Schema + Email/Password Auth
**Goal**: Operator can log in with email/password, receive httpOnly access + refresh cookies, refresh those cookies safely under parallel-request races, log out (current session and all sessions), and read `/auth/me`.
**Depends on**: Phase 4
**Requirements**: INFRA-03, AUTH-05, AUTH-06, AUTH-07, AUTH-EP-01, AUTH-EP-02, AUTH-EP-03, AUTH-EP-04, AUTH-EP-05, AUTH-LO-01, AUTH-LO-02, AUTH-LO-03, AUTH-LO-04, TEST-01, TEST-02, TEST-04, TEST-08
**Success Criteria** (what must be TRUE):
  1. The seeded owner can `POST /api/v1/auth/login` with email + 12-char password and receive a 200 + `sz_access` + `sz_refresh` httpOnly cookies + `{user: {id, role, fullName}}`; wrong credentials return 401 `invalid_credentials` in timing-equivalent fashion; 6th failed attempt within 15 minutes returns 429.
  2. After `/auth/refresh`, the previous refresh token is rotated within a `family_id`; replaying an already-rotated token revokes the entire family with a `family_reuse_detected` audit event; two parallel refresh calls within the ~5-second reuse window return the same new pair.
  3. `POST /auth/logout` clears both cookies + deletes the Redis session entry + stamps `revoked_at` in DB; `POST /auth/logout-all` invalidates every active session for the current user; `GET /auth/me` returns 200 with `{id, role, fullName, email, hasTelegram}` for an authenticated request and 401 otherwise.
  4. The pytest `db_session` fixture rolls back via SAVEPOINT between tests against a real Postgres; running `alembic upgrade head` on a clean DB followed by `alembic check` produces an empty diff.
**Plans:** 8 plans
- [x] 05-01-PLAN.md — Pinned redis>=5,<6 + refresh_reuse_window_seconds Settings + .env.example (D-08, D-13, D-25)
- [x] 05-02-PLAN.md — app/core/redis.py lifespan + app/core/audit.py emit + clear_session_cookies (D-08, D-17, D-21)
- [x] 05-03-PLAN.md — User/RefreshToken/OtpCode ORM models + alembic 0001_auth migration (INFRA-03, TEST-08, D-01..D-07)
- [x] 05-04-PLAN.md — Auth service (authenticate/issue_tokens/rotate_refresh/revoke_session/revoke_all_sessions) + rate_limit (AUTH-05/06/07, D-09..D-14, D-18..D-20)
- [x] 05-05-PLAN.md — Auth schemas + router /login /refresh /logout /logout-all /me (AUTH-EP-01/02/05, AUTH-LO-01/02/04)
- [x] 05-06-PLAN.md — app/main composition (combined_lifespan + register_user_loader) + /api/v1 prefix flip + seed_demo_data.py (AUTH-EP-04, D-15, D-16)
- [x] 05-07-PLAN.md — SAVEPOINT-based db_session fixture + smoke test (TEST-01, D-22)
- [x] 05-08-PLAN.md — Integration tests test_login.py / test_refresh.py / test_logout.py (TEST-02, TEST-04, AUTH-LO-01/02/04)

### Phase 6: RBAC Wiring + Parity Tests
**Goal**: Every protected route refuses unauthenticated callers with 401 and unauthorized callers with 403 before any side-effect runs, and the `OWNER_ONLY` matrix can never silently drift from the frontend.
**Depends on**: Phase 5
**Requirements**: RBAC-02, RBAC-03, RBAC-04, RBAC-05, CSRF-02, TEST-05, TEST-06, TEST-07
**Success Criteria** (what must be TRUE):
  1. A reception-role user receives 403 with `DomainError { code: "forbidden" }` when calling any endpoint listed in `OWNER_ONLY` (delete-clients, view-finance/reports/payroll/compensation/settings/owner-area, edit-templates, refund-finance); the same call as owner returns 200.
  2. Every business route declares `Depends(require_permission(...))` on its signature and never inside the service body — verified by an introspection test that enumerates `app.routes` (excluding `/healthz`, `/auth/login`, `/auth/telegram/*`, `/auth/refresh`).
  3. A parity test imports both `app.core.permissions.OWNER_ONLY` and `apps/admin-web/src/shared/session/can.ts` and fails the build if the two sets of `(action, resource)` pairs differ.
  4. Mutating requests (POST/PATCH/DELETE) without a valid `X-CSRF-Token` matching the `sportzal_csrf` cookie return 403; `/auth/login` and the Telegram server-side endpoints are correctly exempted.
**Plans:** 5 plans
- [x] 06-01-PLAN.md — Add CsrfMismatch(AppError) subclass to app/core/exceptions.py (D-08)
- [x] 06-02-PLAN.md — Add require_authenticated() factory + verify_csrf dependency + audit emit on require_permission (D-01, D-05..D-07, D-23)
- [x] 06-03-PLAN.md — Migrate auth router /me /logout /logout-all to require_authenticated; add CSRF signature dep on /logout /logout-all preserving RBAC-04 ordering; update test_logout.py (D-02, D-09, D-22, D-24)
- [x] 06-04-PLAN.md — TEST-05 fixture-router built dynamically from OWNER_ONLY + RBAC integration tests (owner=200 / reception=403 / unauth=401) (D-10, D-11, D-12)
- [x] 06-05-PLAN.md — TEST-06 three-way parity test against can.ts/registry.ts + TEST-07 route-introspection guard (D-13..D-19)

### Phase 7: Telegram OTP Channel
**Goal**: Operator without a password can log in by tapping a deep-link to the bot, pressing `/start`, receiving a 6-digit DM, and pasting it into the admin-web — with all DM-blocked / wrong-code / expired-code edges handled deterministically.
**Depends on**: Phase 6
**Requirements**: INFRA-06, AUTH-TG-01, AUTH-TG-02, AUTH-TG-03, AUTH-TG-04, AUTH-TG-05, AUTH-TG-06, TEST-03
**Success Criteria** (what must be TRUE):
  1. `POST /api/v1/auth/telegram/start` returns `{deepLinkUrl: "https://t.me/<bot>?start=<token>", deepLinkToken}` with the deep-link token TTL = 10 minutes; `GET /api/v1/auth/telegram/status?token=...` reports `{bound: true}` only after the bot has linked the chat.
  2. After `/start <token>` in the bot, the operator receives a 6-digit DM (TTL 5 min, max 5 verification attempts); `POST /api/v1/auth/telegram/verify { token, code }` upserts the user by `telegram_chat_id`, issues the same cookie pair as the email/password path, and emits `otp_consumed` audit.
  3. Invoking the verify endpoint when the user has not yet started a chat with the bot returns 409 `bot_not_started` carrying the deep-link URL; expired OTP, wrong code, and exceeded-attempts paths all return distinct error codes.
  4. `docker compose up` brings up a fourth `telegram-bot` service (`restart: unless-stopped`) that runs `python -m app.workers.telegram_bot` long-polling — separate from the API and ARQ worker processes.
**Plans:** 8 plans
- [ ] 07-01-PLAN.md — Settings + .env.example + reusable db/redis lifespan managers (D-08, D-10)
- [ ] 07-02-PLAN.md — Migration 0003_telegram_username + User.telegram_username column (D-02, D-18)
- [ ] 07-03-PLAN.md — Auth domain exceptions for D-13 verify failure modes
- [ ] 07-04-PLAN.md — telegram_service (start/bind/commit/consume/get_status) + DTOs + audit names (D-11, D-13, D-19)
- [ ] 07-05-PLAN.md — integrations/telegram (sender + handlers + bot factory) with HandlerContext closure (D-04, D-05, D-09)
- [ ] 07-06-PLAN.md — Auth router 3 telegram endpoints + login_success channel kwarg (D-13, D-14)
- [ ] 07-07-PLAN.md — workers/telegram_bot.py + docker-compose telegram-bot service + seed script (INFRA-06, D-03, D-06)
- [ ] 07-08-PLAN.md — TEST-03 stub_telegram_sender fixture + 4 test files
**UI hint**: yes

### Phase 8: Clients Module + Audit Log
**Goal**: Operator can list, search, filter, sort, view, create, edit, and (owner-only) soft-delete clients via `/api/v1/clients/*`; every mutation lands in `audit_log`; a soft-deleted phone can be reused by a new client.
**Depends on**: Phase 6 (RBAC wiring required by every clients route)
**Requirements**: INFRA-04, CLIENTS-01, CLIENTS-02, CLIENTS-03, CLIENTS-04, CLIENTS-05, CLIENTS-06, CLIENTS-07, CLIENTS-08, CLIENTS-09, AUDIT-01, AUDIT-02, AUDIT-03
**Success Criteria** (what must be TRUE):
  1. `GET /api/v1/clients` returns `{items, total, page, pageSize}` and supports `q=` ILIKE on ФИО + phone (backed by `pg_trgm` GIN), filters by `tag`/`gender`/`createdFrom`/`createdTo`/`hasTelegram`, and sort by `created_at DESC` (default) or `last_name ASC`.
  2. `POST /api/v1/clients` creates a client with E.164 phone validation; `PATCH /api/v1/clients/{id}` partial-updates; `DELETE /api/v1/clients/{id}` is owner-only and is a soft-delete (sets `deleted_at`, never hard-deletes); `GET /api/v1/clients/{id}` returns 404 for soft-deleted rows.
  3. After soft-deleting a client with phone `+79991234567`, creating a new client with the same phone succeeds — the partial unique index `WHERE deleted_at IS NULL` is in place; all queries flow through `list_alive` / `get_alive` repository helpers (no raw `select(Client)` in service layer).
  4. Successful login, logout, OTP issue/consume, session revoke, family-reuse-detected, client created/updated/soft-deleted events all produce one row each in `audit_log` with `{actor_user_id, action, resource_type, resource_id, payload, created_at}`; no `GET /audit-log` endpoint is exposed (deferred to v1.2).
**Plans:** 8 plans
- [x] 08-01-PLAN.md — Migration 0002_clients + AuditLog/Client ORM + 3 DomainError subclasses (INFRA-04, CLIENTS-01, CLIENTS-02, AUDIT-01)
- [x] 08-02-PLAN.md — audit.emit async refactor + DB INSERT body (AUDIT-01, AUDIT-02 partial)
- [x] 08-03-PLAN.md — Pydantic schemas (Create/Update/Response/ListQuery/EmergencyContact) (CLIENTS-01, CLIENTS-04, CLIENTS-06, CLIENTS-07)
- [x] 08-04-PLAN.md — repository.py — sole owner of select(Client); list_alive/get_alive/insert/update/soft_delete (CLIENTS-02..05, CLIENTS-09)
- [x] 08-05-PLAN.md — Migrate 15 audit.emit call-sites across auth/service, auth/router, telegram_service, integrations/telegram/handlers (AUDIT-02)
- [x] 08-06-PLAN.md — service.py orchestration + IntegrityError 409 + D-08 payloads + D-09 no-op skip (CLIENTS-02, CLIENTS-05..08, AUDIT-02)
- [x] 08-07-PLAN.md — router.py 5 endpoints + RBAC + CSRF + mount in /api/v1/clients (CLIENTS-03, CLIENTS-05..08)
- [x] 08-08-PLAN.md — Integration tests (5 new clients files + audit-row assertions in 5 auth files) + alembic env.py include_object filter (CLIENTS-02..09, AUDIT-02, AUDIT-03, INFRA-04 verification)

### Phase 9: OpenAPI Pipeline + packages/api-client
**Goal**: A change to a backend Pydantic schema either updates `apps/backend/openapi.json` and the generated TS types in the same PR, or CI fails — making FE/BE drift impossible without an explicit "I really meant it" commit.
**Depends on**: Phase 8 (backend surface stable)
**Requirements**: API-01, API-02, API-05, API-06, API-07
**Success Criteria** (what must be TRUE):
  1. Running `uv run python apps/backend/scripts/export_openapi.py` writes `apps/backend/openapi.json` deterministically (`indent=2, sort_keys=True`, byte-stable across macOS/Linux) without touching Postgres or Redis.
  2. CI runs the export script and `git diff --exit-code apps/backend/openapi.json` — a PR that changed a schema without regenerating fails the build.
  3. CI runs `pnpm --filter @sportzal/api-client codegen` and `git diff --exit-code` against the generated `src/schema.d.ts` (gitignored locally, regenerated in CI from the checked-in openapi.json).
  4. A FE consumer can call `request<P, M>(method, path, init)` from `@sportzal/api-client/fetcher` with `credentials: 'include'`; on 401 (non-`/auth/*`) the wrapper does a single-flight `/auth/refresh` and retries once; failures throw a typed `ApiError { code, message, fields? }`.
**Plans:** 3 plans
- [x] 09-01-PLAN.md — Lifespan-safe export script (apps/backend/scripts/export_openapi.py) + first openapi.json artifact + FastAPI version pin (API-01, D-04..D-06)
- [x] 09-02-PLAN.md — packages/api-client real package (tsconfig + errors.ts + fetcher.ts with single-flight refresh + generated/committed schema.d.ts + index.ts barrel + README) (API-05, API-06, D-A1..D-A4, D-07, D-09..D-12)
- [x] 09-03-PLAN.md — .github/workflows/ci.yml drift gates (backend + frontend parallel jobs) + admin-web predev hook + workspace dep + REQUIREMENTS API-05 deviation closure (API-02, API-07, D-01..D-03, D-08)

### Phase 10: admin-web Auth + Clients Wiring
**Goal**: An operator running the admin-web with `VITE_API_MODE=http` can log in (email/password OR Telegram OTP), see the real Clients list/detail/create/edit/delete backed by Postgres, and never falls into a 401-redirect loop — while every other domain (memberships, billing, etc.) keeps using the existing mock services unchanged.
**Depends on**: Phase 9
**Requirements**: FE-01, FE-02, FE-03, FE-04, FE-05, FE-06, FE-07
**Success Criteria** (what must be TRUE):
  1. Visiting `/login` with `VITE_API_MODE=http` shows two tabs (email/password, Telegram OTP); the Telegram tab polls `/auth/telegram/status` and only prompts for the 6-digit code after `bound: true`; on success the user is redirected back to the original `next=` location.
  2. Visiting `/clients/*` with `VITE_API_MODE=http` lists/searches/creates/edits/(owner-)deletes clients via `@sportzal/api-client`; mutations use `onMutate`/`onError`/`onSettled` for optimistic updates with rollback; route loaders call `queryClient.ensureQueryData` with the same `clientsKeys` factory as the hooks.
  3. With `VITE_API_MODE=mock`, `/login` and `/clients/*` continue to work against the existing mock services with no regression; all other domains stay on mocks regardless of mode.
  4. A 401 on a non-`/auth/*` request triggers a single-flight `/auth/refresh`; on refresh failure the app navigates to `/login?next=<encoded>` exactly once (module flag prevents loops); logout clears the TanStack Query cache and redirects to `/login`.
  5. ESLint forbids `fetch(` outside `packages/api-client/src/` and `apps/admin-web/src/shared/api/services/http/`; the negative-test fixture proves the rule fires.
**Plans**: TBD
**UI hint**: yes

### Phase 11: Clients HTTP-mode Shape Adapter
**Goal**: Make Phase 10's success criterion #2 ("`VITE_API_MODE=http` lists/searches/creates/edits/deletes clients via `@sportzal/api-client`") actually true on a running backend. Today the FE `Client` domain type and create/update inputs were never reconciled with the backend `ClientResponse` / `ClientCreateRequest` shapes — every list row reads `client.fullName === undefined`, every create returns 422 (`birthDate` is unknown under `extra="forbid"`), and the optimistic-update path crashes on `undefined.split(' ')`.
**Depends on**: Phase 10
**Gap closure**: Closes INTEGRATION-CHECK findings F-01 (BLOCKER) and F-02 (BLOCKER)
**Requirements**: CLIENTS-01, CLIENTS-05, CLIENTS-06, CLIENTS-07, FE-01, FE-04 (in `VITE_API_MODE=http`)
**Success Criteria** (what must be TRUE):
  1. `apps/admin-web/src/shared/api/services/http/clients.ts` adapts every `ClientResponse` from the backend into the FE `Client` shape: `fullName` is composed from `lastName + firstName + middleName` (single space separators, trimmed), `birthDate` is renamed from backend `birthday`, and the FE-only fields not present in `ClientResponse` are populated as `undefined` rather than missing.
  2. The same http impl converts FE `ClientCreateInput` / `ClientUpdateInput` to backend `ClientCreateRequest` / `ClientUpdateRequest` before sending: `fullName` is split into `lastName/firstName/middleName` (≥2 tokens required, third+ tokens collapse into `middleName`), `birthDate` is renamed to `birthday`, and empty-string fields (`email`, `notes`, `birthDate`, etc.) are omitted from the request body so the backend's `extra="forbid"` + `EmailStr` validators do not fail.
  3. `useUpdateClient`'s optimistic-update path no longer relies on splitting `current.fullName` by space — it either re-derives `fullName` only when create-input fields change, or falls back to a stable name source that is always defined for live backend rows.
  4. A live E2E walkthrough against `docker-compose up` + `pnpm -F admin-web dev` with `VITE_API_MODE=http` lists clients (real names visible, not `undefined`), creates a client (returns 201, shows in list), edits the client (returns 200, table reflects), and deletes as owner (returns 204) — all without surfacing `TypeError: Cannot read properties of undefined` or `422 Unprocessable Entity` in the network tab.
  5. Existing `VITE_API_MODE=mock` flow regresses zero tests in `pnpm -F admin-web test`.
**Plans:** 2/2 plans complete
- [x] 11-01-PLAN.md — Adapter mappers (responseToClient / createInputToRequest / updateInputToRequest) wired into http/clients.ts; closes F-01 + F-02 shape mismatch
- [x] 11-02-PLAN.md — Harden useUpdateClient optimistic-update against undefined fullName + regression test + live E2E runbook (human-verify gate)
**UI hint**: no (data adapter, not UI)

### Phase 12: v1.1 Verification Backfill
**Goal**: Close the procedural verification gaps that prevented `/gsd-audit-milestone v1.1` from passing without inventing new code work. This phase produces missing verification artifacts and runs the live CI sweeps that human-needed phases were waiting on, so the v1.1 audit can flip to `passed`.
**Depends on**: Phase 11 (so `10-VERIFICATION.md` reflects the http-mode fix as well)
**Gap closure**: Closes MILESTONE-AUDIT findings (Phase 9 missing VERIFICATION.md, Phase 10 stale `gaps_found`, Phase 6 + 8 `human_needed`)
**Requirements**: API-01, API-02, API-05, API-06, API-07 (Phase 9 partials → satisfied with artifact), no new REQ-IDs
**Success Criteria**:
  1. `.planning/phases/09-openapi-pipeline-api-client/09-VERIFICATION.md` exists, status `passed`, with each Phase 9 success criterion mapped to file/line evidence aggregated from UAT.md + REVIEW-FIX.md.
  2. `.planning/phases/10-admin-web-auth-clients-wiring/10-VERIFICATION.md` re-rendered with status `passed`, citing the post-fix state of `components-json.test.ts` (asserts `'base-nova'`) plus the Phase 11 http-mode evidence.
  3. Phase 6 RBAC integration tests run on a live Postgres+Redis CI host (or a documented local equivalent): `cd apps/backend && uv run pytest tests/integration/auth/test_logout.py tests/integration/rbac/test_owner_only.py -v` exits green; results appended to `06-VERIFICATION.md` body and frontmatter status flipped from `human_needed` to `passed`.
  4. Phase 8 `human_needed` resolved: either CR-01 (ILIKE wildcard escape) is accepted with a documented warning in `08-VERIFICATION.md` and tracked as Phase 14, OR the audit is updated to reflect that Phase 14 owns the closure. CR-02 (rollback inside service) accept-or-fix decision recorded similarly.
  5. Re-running `/gsd-audit-milestone v1.1` after this phase produces an audit with `status: passed` (no `unverified_phases`, no `human_needed_phases`, no stale `gaps_found_phases`).
**Plans**: TBD
**UI hint**: no

### Phase 12.1: Clients Service Commit Fix
**Goal**: Make every clients write actually persist. Today `apps/backend/app/modules/clients/service.py` returns 201/200/204 from POST/PATCH/DELETE without calling `await session.commit()`, so `get_db` (`apps/backend/app/core/database.py:145`) auto-rolls-back at request exit and the row never lands in Postgres. Discovered while auto-verifying Phase 11 SC #4 — Phase 11 FE work is correct, but the live-stack runbook cannot tick through until backend writes commit. `auth/service.py` already commits at every write site; `clients/service.py` mirrors that pattern.
**Depends on**: Phase 11 (uses the http-mode FE adapter as the verification harness)
**Gap closure**: Unblocks Phase 11 SC #4 (deferred via `11-HUMAN-UAT.md`); root-cause for the rolled-back-201 symptom logged in that file
**Requirements**: CLIENTS-06, CLIENTS-07, CLIENTS-08 (write paths, made durable — no new REQ-IDs)
**Success Criteria**:
  1. `apps/backend/app/modules/clients/service.py` calls `await session.commit()` exactly once at the end of each successful write path (`create_client`, `update_client`, `soft_delete_client`, `import_clients_csv` if present), mirroring the pattern in `apps/backend/app/modules/auth/service.py`. Rollback paths (e.g. `IntegrityError → PhoneExistsError`) remain explicit and do NOT swallow the original transaction.
  2. New integration test in `apps/backend/tests/integration/clients/test_persistence.py`: spin up the test stack, `POST /api/v1/clients` with valid body → assert `GET /api/v1/clients` immediately after returns the row (today this would fail because of the rollback). Same for PATCH (mutated value visible after) and DELETE (`deleted_at` set after).
  3. Re-running Phase 11 `11-E2E-RUNBOOK.md` end-to-end against `docker compose up` + `pnpm -F admin-web dev` (`VITE_API_MODE=http`) ticks every checkbox: list shows real Russian names after creates, PATCH `firstName` updates the row visibly, DELETE removes it. `11-HUMAN-UAT.md` `status:` flips from `deferred` to `resolved`, and Phase 11 `10-VERIFICATION.md` evidence (referenced from Phase 12 SC #2) is regenerated.
  4. SQLAlchemy logs no longer show `ROLLBACK` after `client_created` / `client_updated` / `client_deleted` audit events — they show `COMMIT`. (Quick local verification: tail `uvicorn` output during the runbook walkthrough.)
**Plans**: TBD
**UI hint**: no

### Phase 13: v1.1 Minor Drift & Hygiene Cleanup
**Goal**: Tidy the small contract-drift and metadata-rot items the audit surfaced — none individually block the milestone, but together they accumulate developer friction (dead types, casted `as never` query strings, stale traceability table, fresh-clone boot failures, REQUIREMENTS.md `Pending` rows that lie). Single phase keeps related cleanups in one commit chain.
**Depends on**: Phase 11
**Gap closure**: Closes INTEGRATION-CHECK F-03 (MINOR), F-04 (MINOR), F-06 (MINOR); closes Phase 9 UAT Gap 1 + Gap 2; refreshes REQUIREMENTS.md traceability and SUMMARY frontmatter omissions
**Requirements**: No new REQ-IDs (housekeeping)
**Success Criteria**:
  1. `apps/admin-web/src/shared/api/contracts/auth.ts` no longer declares `expiresAt` on `TelegramStartResponse` or `TelegramStatusResponse` — both types match the backend's actual `{deepLinkUrl, deepLinkToken}` and `{bound}` shapes byte-for-byte.
  2. `packages/api-client/src/fetcher.ts` `RequestInitWithBody` accepts a typed `query?: Record<string, string | number | boolean>` field; `apps/admin-web/src/shared/api/services/http/{auth,clients}.ts` use that field instead of building URLs by string concatenation and casting with `as never`. The TODO comment on the cast is removed.
  3. `apps/backend/app/modules/members/` is deleted from the working tree (including stale `__pycache__`); `import-linter` stays GREEN; `Phase 4 INFRA-05` no longer has the "stale dir contradicts SUMMARY" footnote.
  4. `apps/backend/app/core/config.py` (or `.env.example`) provides safe-default values for `TELEGRAM_BOT_TOKEN` and `TELEGRAM_BOT_USERNAME` so a fresh-clone developer can run `docker-compose up` + `pnpm -F admin-web dev` with `VITE_API_MODE=http` without setting bot env vars first; the bot worker still warns/exits cleanly when the token is the placeholder.
  5. `packages/api-client/` has a working test runner (vitest), the throwaway test that was used to verify CR-01/CR-02 fetcher fixes is committed as a permanent regression test, and the package has at least 1 `pnpm test` invocation in CI.
  6. `.planning/REQUIREMENTS.md` traceability table reflects reality: 63 stale `Pending` rows for v1.1 REQs flip to `Complete` (or to `Phase 11/13/14` for the few that gap-closure phases touch); coverage count at the top of the file matches.
  7. SUMMARY.md frontmatter `requirements-completed:` arrays in Phase 04, 05, 06, 08 are backfilled to list every REQ-ID those phases closed (currently 4 + 12 + 4 + 1 = 21 missing entries per the audit) so the next audit's 3-source check sees consistent records.
**Plans**: TBD
**UI hint**: no

### Phase 14: Clients Search PII Hardening
**Goal**: Close the Phase 8 CR-01 security warning. Today `clients.list_alive(q=...)` interpolates the user-supplied search term directly into an ILIKE pattern with no escaping of the SQL `LIKE` metacharacters `%`, `_`, or `\`. A reception user searching `"%"` returns the entire client roster (PII over-exposure). This phase escapes those metacharacters and locks the behaviour with a regression test.
**Depends on**: Phase 12 (so the human_needed flag on Phase 8 is resolved before adding new tests against that surface)
**Gap closure**: Closes Phase 8 CR-01 (PII security warning)
**Requirements**: CLIENTS-04 (search semantics, hardened)
**Success Criteria**:
  1. `apps/backend/app/modules/clients/repository.py` `list_alive` (or whatever helper builds the ILIKE pattern) escapes `%`, `_`, and `\` in the user-supplied `q` value before wrapping it as `%{q}%`. The escape is opt-out only via an explicit caller flag (no caller currently sets it).
  2. A regression test in `apps/backend/tests/integration/clients/test_search.py` (or sibling) confirms: searching `?q=%25` (URL-encoded `%`) returns ZERO rows when no client name literally contains `%`; previously it returned all rows.
  3. The same test confirms `?q=_test_` matches a client with `_test_` literally in the name and does NOT match a client with `atest`-pattern names (i.e. `_` no longer functions as a single-character wildcard).
  4. No regression on existing search behaviour: substring matches on plain alphanumeric queries still hit (`q=Иванов` returns the Ivanov family).
  5. `08-VERIFICATION.md` CR-01 entry is updated to status `resolved` with a back-reference to this phase's commits.
**Plans**: TBD
**UI hint**: no

## Progress

| Phase | Milestone | Plans Complete | Status   | Completed  |
|-------|-----------|----------------|----------|------------|
| 1. Monorepo Restructure & Frontend Move | v1.0 | 3/3 | Complete | 2026-04-30 |
| 2. Backend Skeleton with Quality Tooling | v1.0 | 8/8 | Complete | 2026-04-30 |
| 3. Tests, Dev Infrastructure & Documentation | v1.0 | 6/6 | Complete | 2026-05-01 |
| 4. Auth Foundations & Cookie/RBAC Primitives | v1.1 | 0/TBD | Not started | — |
| 5. User Schema + Email/Password Auth | v1.1 | 0/8 | Not started | — |
| 6. RBAC Wiring + Parity Tests | v1.1 | 0/TBD | Not started | — |
| 7. Telegram OTP Channel | v1.1 | 0/8 | Not started | — |
| 8. Clients Module + Audit Log | v1.1 | 0/8 | Not started | — |
| 9. OpenAPI Pipeline + packages/api-client | v1.1 | 0/TBD | Not started | — |
| 10. admin-web Auth + Clients Wiring | v1.1 | 8/8 | Complete   | 2026-05-04 |
| 11. Clients HTTP-mode Shape Adapter | v1.1 | 2/2 | Complete   | 2026-05-04 |
| 12. v1.1 Verification Backfill | v1.1 | 5/5 | Complete   | 2026-05-05 |
| 13. v1.1 Minor Drift & Hygiene Cleanup | v1.1 | 0/TBD | Not started | — |
| 14. Clients Search PII Hardening | v1.1 | 0/TBD | Not started | — |

## Coverage Report

**v1.1 requirements:** 70 total
**Mapped to phases:** 70 ✓
**Unmapped:** 0

| Category | Count | Phase Distribution |
|----------|-------|--------------------|
| INFRA (7) | 7 | 4 (×4), 5 (×1), 7 (×1), 8 (×1) |
| AUTH (7) | 7 | 4 (×4), 5 (×3) |
| AUTH-EP (5) | 5 | 5 (×5) |
| AUTH-TG (6) | 6 | 7 (×6) |
| AUTH-LO (4) | 4 | 5 (×4) |
| CSRF (2) | 2 | 4 (×1), 6 (×1) |
| RBAC (5) | 5 | 4 (×1), 6 (×4) |
| CLIENTS (9) | 9 | 8 (×9) |
| AUDIT (3) | 3 | 8 (×3) |
| API (7) | 7 | 4 (×2), 9 (×5) |
| FE (7) | 7 | 10 (×7) |
| TEST (8) | 8 | 5 (×4), 6 (×3), 7 (×1) |
| **Total** | **70** | **Phase 4: 12 / Phase 5: 17 / Phase 6: 8 / Phase 7: 8 / Phase 8: 13 / Phase 9: 5 / Phase 10: 7** |

**Validation:**
- ✓ Every v1.1 REQ-ID is mapped to exactly one phase
- ✓ No orphans (12 + 17 + 8 + 8 + 13 + 5 + 7 = 70)
- ✓ No duplicates (each REQ-ID appears in exactly one phase's Requirements list)
- ✓ Phase ordering matches SUMMARY.md merged build order (Foundations → Email/Password → RBAC → Telegram → Clients+Audit → OpenAPI → FE wiring)
- ✓ Continuing phase numbering from v1.0 (last=03 → first v1.1=04), 7 new phases (04-10)

---
*Roadmap last updated: 2026-05-01 — v1.1 Auth + Clients planned (phases 4-10)*
*v1.0 Coverage: 47/47 v1 requirements validated*
*v1.1 Coverage: 70/70 requirements mapped*
