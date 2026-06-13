# Phase 100: Foundation + Authentication - Context

**Gathered:** 2026-06-13
**Status:** Ready for planning

<domain>
## Phase Boundary

`apps/admin-app` is absorbed into the clubcore monorepo as a first-class pnpm
workspace member, talks to the real backend over staff cookies + CSRF, gates the
deferred (future) screens behind a "coming soon" placeholder, and lets a staff
member log in / log out / have their session survive a refresh / see their role
reflected in the UI. The per-domain zod contract seam is established so that
Phase 101+ can flip each domain from mock → real API one at a time.

**In scope:** workspace/PM absorption, CI job, typed transport seam (CSRF + 401),
session/role wiring (login/logout/refresh/me), RBAC re-home target, hide-for-future
placeholders, zod seam bootstrapped on the auth/session domain.

**Out of scope:** wiring any business domain (clients/memberships/schedule/etc.)
to real data — those stay on mocks until their own phase; deleting `apps/admin-web`
(that is Phase 105); new backend endpoints (wire-only milestone, D-V30-SCOPE-WIRE).
</domain>

<decisions>
## Implementation Decisions

### Workspace Absorption & Tooling
- Migrate `apps/admin-app` from Bun → **pnpm@9.15.9**; join the existing pnpm
  workspace (`apps/*`). Single package manager across CI and lockfile discipline
  (client-pwa v2.0 absorption precedent). Drop `bun.lock`; generate/commit the
  workspace `pnpm-lock.yaml`. Set `packageManager: pnpm@9.15.9` in the member
  package.json.
- Rename the workspace package `clubcore-admin-frontend` → **`@clubcore/admin-app`**
  (scoped, matches `@clubcore/client-pwa`).
- Add a `@clubcore/api-client` dependency via **`workspace:*`** — reuse the
  byte-stable generated `schema.d.ts` for typed requests (client-pwa pattern).
- Add a **dedicated parallel `admin-app` CI job** (install → typecheck → lint →
  test → build), excluded from the recursive `pnpm -r` frontend steps the same way
  client-pwa is (D-72-05), so it never double-runs.
- Align TS/engine versions with the workspace (TypeScript ~5.7.x, Node ≥20, pnpm ≥9).

### API Client & Transport Seam
- **CORRECTION — real staff cookie names** (verified in `apps/backend/app/core/security.py`,
  NOT the `sz_*` written in the ROADMAP/STATE prose — that is stale pre-v1.10-rebrand
  text; the v1.10 rebrand flipped `sz:* → cc:*`):
  - `cc_access` — httpOnly, Path=`/`, 15-min TTL (sent on all API paths)
  - `cc_refresh` — httpOnly, Path=`/api/v1/auth`, 7-day TTL
  - `clubcore_csrf` — **non-httpOnly** (JS-readable), Path=`/`, 7-day TTL — the
    CSRF double-submit token
- Adopt a **per-domain `VITE_API_MODE` mock|http chokepoint** (admin-web/client-pwa
  pattern). In Phase 100 only the auth/session domain flips to `http`; every other
  domain stays on its existing mock `queryFn`. Each domain flips independently in
  its own phase (matches lazy zod-seam, D-V30 / spike 010 Option A).
- The central `api()` fetch wrapper **reads the `clubcore_csrf` cookie and injects
  `X-CSRF-Token`** on every non-GET/HEAD/OPTIONS request (double-submit). Backend
  validates via constant-time compare; mismatch → 403 `csrf_mismatch`.
- A **global 401 handler** in the transport layer / QueryClient navigates to
  `/login` (clears session state) without crashing — covers expired access cookie
  on any query or mutation (success criterion 3).
- All requests use **`credentials: 'include'`**; dev uses a **Vite dev proxy
  `/api → backend`** (no CORS in dev). API base from `VITE_API_BASE_URL ?? '/api'`.

### Session, RBAC & Hide-for-Future
- Session is a **`useSession()` TanStack Query hook over `GET /api/v1/auth/me`** as
  the single source of truth (role/full_name/email/has_telegram). Survives browser
  refresh via the httpOnly `cc_*` cookies — no role mirrored into a client store.
  Login mutation invalidates/sets the session query; logout clears it.
- **Auth contract shapes** (verified): login `POST /api/v1/auth/login`
  `{email, password}` → `{data:{user:{id, role, fullName}}}`; `GET /api/v1/auth/me`
  → `{data:{id, role, fullName, email, hasTelegram}}`; success envelope is
  `{data: …}`, error envelope is top-level `{code, message, fields?}` (NOT wrapped).
- **RBAC re-home:** port `can(role, action, resource)` + the **41-entry `OWNER_ONLY`**
  matrix + the `Resource`/`Action`/`registry` definitions into `apps/admin-app` so it
  becomes the parity reference that Phase 105 keeps green after `apps/admin-web` is
  deleted. Roles are binary: `owner` | `reception`. Owner short-circuits to `true`.
  Wire role-gated sidebar nav + in-page action gating off this. **The exact re-home
  mechanic (admin-app `can.ts` as the CISO-01 byte-parity target vs. another
  arrangement) is re-confirmed at plan time after the planner reads the real coupling
  in `permissions.py` / `can.ts` / `registry.ts` / `test_rbac_parity.py`** (D-V30).
- **Deferred ("future") screens:** Branches, Branch-Settings, System-Settings,
  ImportExport, Duplicates, Archive, Trash, Messages (staff), Roles,
  Notifications-mgmt. Replace each route's element with a **shared `<ComingSoon/>`
  placeholder** and **remove its sidebar nav entry** (PWA hide-for-future pattern,
  D-71-09 — not broken, not wired). Keep the original page files in-tree but
  un-imported so a future milestone can graduate them (de-list + wire via the seam).
- **zod seam:** establish a per-domain zod contract layer and apply it to the
  auth/session domain in Phase 100 (login request, login response, `/auth/me`
  response). Document the "mock `queryFn` removal path" so Phase 101+ repeats the
  pattern per domain.

### Login Flow Wiring
- Wire to real backend in Phase 100: **login** (`POST /auth/login`), **logout**
  (`POST /auth/logout`), **session refresh / survives-reload** (cookie + `/auth/me`),
  **401 → expired/login redirect**, and **password-reset request + confirm**
  (`POST /auth/password-reset/request` + `/confirm` — endpoints exist, cheap to wire).
- **Hide the TOTP `twofa` view** — there is no staff TOTP/2FA backend; staff OTP is a
  Telegram/email channel, out of scope for P100. Treat the view as future.
- **"Remember me"** stays as a **documented no-op** in P100 (backend cookie TTLs are
  fixed: access 15 min / refresh 7 days); revisit if a TTL knob is ever added.
- **Form validation:** zod `password.min(12)` + email format on the login form, to
  mirror the backend `LoginRequest` (`password Field(min_length=12)`) and avoid a
  guaranteed 422.
- **Error mapping:** `invalid_credentials` (401) → generic Russian message
  «Неверный email или пароль» (anti-oracle — don't reveal which was wrong); 422 with
  a `fields` map → inline field errors; other codes → a non-blocking alert.

### Claude's Discretion
- File/module layout for the new `features/auth/` (schemas, hooks, session), the
  `<ComingSoon/>` component location, the exact transport-wrapper refactor, and test
  organization are at Claude's discretion, following admin-app's existing
  `features/<domain>/api.ts` + `pages/` conventions and the project's strict-TS rules.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets (admin-app)
- `src/api/client.ts` — thin `api()` fetch wrapper + `ApiError` + `mockResponse()`
  helper; base URL `import.meta.env.VITE_API_BASE_URL ?? '/api'`. **This is the
  chokepoint to extend** with `credentials:'include'`, CSRF injection, 401 handling.
- `src/api/query-client.ts` — QueryClient singleton (`staleTime: 30_000`,
  `refetchOnWindowFocus:false`, `retry:1`) — matches workspace conventions already.
- `src/features/<domain>/api.ts` — per-domain TanStack Query hooks with `xKeys`
  factories resolving mocks via `mockResponse()`. **The swap-seam unit** — flip
  `queryFn` per domain.
- `src/pages/login/LoginPage.tsx` — 7-view FSM (login, forgot, forgot-sent, reset,
  twofa, expired, logout); `LoginForm.tsx` currently regex-validates + simulates a
  700 ms success. Wire `onSuccess` → real login mutation.
- `src/features/roles/types.ts` — existing role/permission model (PermLevel 0|1|2) is
  a *mock UI* model, NOT the backend RBAC contract; the ported `can()`/`OWNER_ONLY`
  is separate (mirrors `apps/admin-web/src/shared/session/can.ts`).
- shadcn/ReUI primitives + `PageLoading`/`PageError` feedback components exist.

### Backend Contract (verified — `apps/backend`)
- Auth router `app/modules/auth/router.py`; cookies issued in
  `app/core/security.py:issue_session_cookies()` (`cc_access`/`cc_refresh`/`clubcore_csrf`).
- CSRF verified in `app/core/dependencies.py:verify_csrf` — reads `clubcore_csrf`
  cookie + `X-CSRF-Token` header, constant-time compare, safe methods exempt,
  ordered AFTER auth (401-before-403, RBAC-04).
- RBAC source of truth `app/core/permissions.py` — `Role{owner,reception}`,
  `Action`/`Resource` StrEnums, `OWNER_ONLY` frozenset (**41 entries**),
  `can()` owner-short-circuit. Mirrored byte-for-byte in
  `apps/admin-web/src/shared/session/{can.ts,registry.ts}`; parity locked by
  `apps/backend/tests/integration/test_rbac_parity.py` (CISO-01).

### Integration Points (workspace / CI)
- Root `package.json` (private, type:module, pnpm≥9) + `pnpm-workspace.yaml`
  (`apps/*`, `packages/*`).
- `.github/workflows/ci.yml` — parallel jobs: backend (ruff/mypy/lint-imports/openapi
  drift/alembic/pytest), frontend (`pnpm -r --filter '!@clubcore/client-pwa'`
  lint/typecheck/test + api-client codegen drift on `schema.d.ts`), client-pwa
  (typecheck/lint/test/build), redocly-lint. **Add an `admin-app` job mirroring
  client-pwa** and exclude admin-app from the recursive frontend filter.
- `packages/api-client` — `openapi-typescript apps/backend/openapi.json → src/schema.d.ts`;
  byte-stability drift gate in CI. No new backend domains → contract unchanged.
- `apps/admin-web/eslint.config.js` — `no-restricted-paths` boundary zones +
  `VITE_API_MODE` chokepoint rule + raw-Tailwind-palette ban — pattern to adopt.

### Reference for RBAC re-home
- `apps/admin-web/src/shared/session/can.ts` + `registry.ts` are the exact files
  whose role admin-app must take over before Phase 105 deletes admin-web.
</code_context>

<specifics>
## Specific Ideas

- The `sz_*` cookie names written in the ROADMAP/STATE/REQUIREMENTS prose for v3.0
  are **factually wrong** against frozen code — use `cc_access`/`cc_refresh`/`clubcore_csrf`.
  This applies to the whole milestone (every wired mutation carries `X-CSRF-Token`
  from `clubcore_csrf`).
- Client-pwa v2.0 absorption is the working precedent for every workspace/CI step.
- Deferred-screen handling is the *inverse* of the v2.x PWA placeholder-graduation
  lesson: here we demote already-built mock screens to placeholders + drop them from
  nav (keep files for future graduation).
</specifics>

<deferred>
## Deferred Ideas

- Staff TOTP/2FA login (`twofa` view) — no backend; future.
- Wiring any business domain to real data — each has its own phase (101–104).
- Deleting `apps/admin-web` + final RBAC parity re-home enforcement — Phase 105.
- Multi-branch (Branches/Branch-Settings/System-Settings) — future milestone; stays
  hidden-for-future this milestone (D-V30-BRANCH).
- Graduating any hidden-for-future staff screen (Roles, Messages, ImportExport, etc.)
  to real data — future milestones.
</deferred>
