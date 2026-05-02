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

### 🚧 v1.1 Auth + Clients (Phases 4-10)

- [ ] **Phase 4: Auth Foundations & Cookie/RBAC Primitives** — Lift JWT/Argon2/cookie/RBAC primitives into `core`, set Alembic naming convention, flip pagination contract, rename `members` → `clients`
- [ ] **Phase 5: User Schema + Email/Password Auth** — First business migration; `/auth/login|refresh|logout|logout-all|me` end-to-end with refresh-rotation family + Redis sessions
- [ ] **Phase 6: RBAC Wiring + Parity Tests** — `require_permission` as Depends on every business route, CSRF dependency, byte-parity test against frontend `can.ts`, route-introspection guard
- [ ] **Phase 7: Telegram OTP Channel** — Standalone bot worker (ptb 22 long-polling), deep-link + 6-digit OTP flow, ARQ send-OTP task, DM-blocked → 409 path
- [ ] **Phase 8: Clients Module + Audit Log** — First business CRUD with soft-delete partial unique index, ILIKE/`pg_trgm` search, owner-only delete, `audit_log` writes from auth + clients
- [ ] **Phase 9: OpenAPI Pipeline + packages/api-client** — Lifespan-safe OpenAPI export, CI drift gate, `openapi-typescript` codegen, hand-rolled `fetcher.ts` with single-flight refresh + typed `ApiError`
- [ ] **Phase 10: admin-web Auth + Clients Wiring** — `VITE_API_MODE=http` for `/login` + `/clients/*` only; Telegram + email/password tabs; ESLint ban on raw `fetch(`; redirect-back + 401-loop guard

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
**Plans**: TBD

### Phase 7: Telegram OTP Channel
**Goal**: Operator without a password can log in by tapping a deep-link to the bot, pressing `/start`, receiving a 6-digit DM, and pasting it into the admin-web — with all DM-blocked / wrong-code / expired-code edges handled deterministically.
**Depends on**: Phase 6
**Requirements**: INFRA-06, AUTH-TG-01, AUTH-TG-02, AUTH-TG-03, AUTH-TG-04, AUTH-TG-05, AUTH-TG-06, TEST-03
**Success Criteria** (what must be TRUE):
  1. `POST /api/v1/auth/telegram/start` returns `{deepLinkUrl: "https://t.me/<bot>?start=<token>", deepLinkToken}` with the deep-link token TTL = 10 minutes; `GET /api/v1/auth/telegram/status?token=...` reports `{bound: true}` only after the bot has linked the chat.
  2. After `/start <token>` in the bot, the operator receives a 6-digit DM (TTL 5 min, max 5 verification attempts); `POST /api/v1/auth/telegram/verify { token, code }` upserts the user by `telegram_chat_id`, issues the same cookie pair as the email/password path, and emits `otp_consumed` audit.
  3. Invoking the verify endpoint when the user has not yet started a chat with the bot returns 409 `bot_not_started` carrying the deep-link URL; expired OTP, wrong code, and exceeded-attempts paths all return distinct error codes.
  4. `docker compose up` brings up a fourth `telegram-bot` service (`restart: unless-stopped`) that runs `python -m app.workers.telegram_bot` long-polling — separate from the API and ARQ worker processes.
**Plans**: TBD
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
**Plans**: TBD

### Phase 9: OpenAPI Pipeline + packages/api-client
**Goal**: A change to a backend Pydantic schema either updates `apps/backend/openapi.json` and the generated TS types in the same PR, or CI fails — making FE/BE drift impossible without an explicit "I really meant it" commit.
**Depends on**: Phase 8 (backend surface stable)
**Requirements**: API-01, API-02, API-05, API-06, API-07
**Success Criteria** (what must be TRUE):
  1. Running `uv run python apps/backend/scripts/export_openapi.py` writes `apps/backend/openapi.json` deterministically (`indent=2, sort_keys=True`, byte-stable across macOS/Linux) without touching Postgres or Redis.
  2. CI runs the export script and `git diff --exit-code apps/backend/openapi.json` — a PR that changed a schema without regenerating fails the build.
  3. CI runs `pnpm --filter @sportzal/api-client codegen` and `git diff --exit-code` against the generated `src/schema.d.ts` (gitignored locally, regenerated in CI from the checked-in openapi.json).
  4. A FE consumer can call `request<P, M>(method, path, init)` from `@sportzal/api-client/fetcher` with `credentials: 'include'`; on 401 (non-`/auth/*`) the wrapper does a single-flight `/auth/refresh` and retries once; failures throw a typed `ApiError { code, message, fields? }`.
**Plans**: TBD

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

## Progress

| Phase | Milestone | Plans Complete | Status   | Completed  |
|-------|-----------|----------------|----------|------------|
| 1. Monorepo Restructure & Frontend Move | v1.0 | 3/3 | Complete | 2026-04-30 |
| 2. Backend Skeleton with Quality Tooling | v1.0 | 8/8 | Complete | 2026-04-30 |
| 3. Tests, Dev Infrastructure & Documentation | v1.0 | 6/6 | Complete | 2026-05-01 |
| 4. Auth Foundations & Cookie/RBAC Primitives | v1.1 | 0/TBD | Not started | — |
| 5. User Schema + Email/Password Auth | v1.1 | 0/8 | Not started | — |
| 6. RBAC Wiring + Parity Tests | v1.1 | 0/TBD | Not started | — |
| 7. Telegram OTP Channel | v1.1 | 0/TBD | Not started | — |
| 8. Clients Module + Audit Log | v1.1 | 0/TBD | Not started | — |
| 9. OpenAPI Pipeline + packages/api-client | v1.1 | 0/TBD | Not started | — |
| 10. admin-web Auth + Clients Wiring | v1.1 | 0/TBD | Not started | — |

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
