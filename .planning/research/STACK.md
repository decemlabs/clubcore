# Stack Research

**Domain:** v2.0 Client PWA + Client-facing backend API additions to existing clubcore gym CRM
**Researched:** 2026-05-29
**Confidence:** HIGH (all recommendations verified against official docs, PyPI, or codebase inspection)

---

## Context: What Is Already Locked

The following are NOT research targets — they are settled and must not change:

- Backend: Python 3.12 + uv + FastAPI 0.115+ + SQLAlchemy 2.0 async + Alembic async + Pydantic v2 + Postgres 16 + Redis 7 + ARQ + structlog
- Admin-web: React 19 + Vite 6 + TanStack Router + TanStack Query + Tailwind v4 + shadcn + pnpm + TS strict (frozen, out of scope)
- Auth primitives: JWT HS256 + Argon2id + cookie matrix (`sz_access` httpOnly + `cc_refresh` + `clubcore_csrf` CSRF double-submit) + refresh-rotation family with Redis-mirrored sessions — all reusable
- Codegen pipeline: `openapi-typescript@^7.13.0` → `schema.d.ts` + drift gate CI

This document covers only what must be ADDED or CHANGED for v2.0.

---

## 1. Client Auth Strategy — Phone + OTP

### 1a. SMS vs Telegram: Use Telegram OTP Only for v1

**Recommendation: Telegram OTP only for client auth. Add SMS as a v2 fallback. Do not install an SMS provider in v2.0.**

Rationale:

The existing codebase has a fully working OTP infrastructure: `OtpCode` table, `OtpChannel = Literal["telegram", "email"]` discriminator (in `app/modules/auth/models.py`), `otp_code_ttl_seconds`, `otp_max_attempts`, and the `request_otp_telegram` / `request_otp_email` service functions. Adding phone-based SMS is a third channel extension to this existing pattern — the table schema and service architecture already accommodate it.

Telegram Gateway API costs $0.01/code vs ~1-2 RUB for domestic SMS, has better delivery guarantees (no SS7 interception risk, no carrier routing delays), and RF/CIS gym users have near-universal Telegram penetration. The friction objection ("user needs Telegram") is bounded: any non-Telegram user is handled by SMS fallback in a later phase.

SMS provider onboarding in Russia requires regulatory friction: A2P SMS sender registration with the operator (MTS/Beeline/MegaFon), message template approval, and sandbox testing. This is non-trivial overhead for a pet-project with 1 gym.

**Explicit recommendation: Telegram Gateway Only for v2.0. SMS Aero as the additive fallback in a subsequent phase (v2.1 or later).**

### 1b. Telegram Gateway API Integration

The Telegram Gateway API (`https://core.telegram.org/gateway`) is distinct from the Telegram Bot API already in use. It takes a phone number in E.164 format and delivers a verification code to the user's Telegram account if they have Telegram registered with that phone number. It also offers `checkSendAbility` (free call) to verify reachability before dispatching.

**Adapter approach: write a thin `app/integrations/telegram_gateway/` async adapter using `httpx.AsyncClient`.**

This follows the established `app/integrations/yookassa/` integration pattern: frozen dataclass boundary types, pure-async httpx adapter, never raises to the service layer (returns success/error result variants), non-fatal degraded mode on boot probe failure. No new pip dependency required — `httpx` is already installed.

The alternative (`telegram-gateway` PyPI package, v0.x, sync-only) would require `asyncio.to_thread` wrapping. The custom adapter is simpler, consistent with project discipline, and avoids an external dependency for a 4-method REST API.

| Thing to build | Where | Notes |
|----------------|-------|-------|
| `app/integrations/telegram_gateway/client.py` | `httpx.AsyncClient` wrapper | 4 methods: sendVerificationMessage, checkSendAbility, checkVerificationStatus, revokeVerificationMessage |
| `app/integrations/telegram_gateway/__init__.py` | Boundary types (frozen dataclasses) | Mirrors yookassa boundary discipline |
| New `OtpChannel` value `"sms"` | `app/modules/auth/models.py` | Deferred — not in v2.0 |
| `TELEGRAM_GATEWAY_TOKEN` config | `app/core/config.py` | New `SecretStr` field, same placeholder-default discipline as `telegram_bot_token` |

### 1c. SMS Aero (Deferred Fallback)

When the SMS fallback is eventually built:

| Library | Version | Notes |
|---------|---------|-------|
| `smsaero-api` | 3.2.0 | Sync-only; wrap in `asyncio.to_thread`. Install: `uv add smsaero-api`. Email + API key auth. |

SMSC.ru is the alternative (no Python SDK; use `httpx` directly with HTTP GET/POST + JSON via `fmt=3` parameter). SMS Aero is preferred due to the official Python SDK.

**Do NOT add SMS provider in v2.0.** This is explicitly out of scope.

### 1d. Phone Number Anchor

`clients.phone` column already exists (`Mapped[str]`, `Text NOT NULL`) with partial unique index `uq_clients_phone_alive WHERE deleted_at IS NULL`. Client OTP lookup is: `SELECT * FROM clients WHERE phone = $1 AND deleted_at IS NULL`. No new column needed.

The new OTP flow for client auth differs from staff auth: instead of looking up a `users` row by email, look up a `clients` row by phone. The `OtpCode` table should store `client_id` (new nullable FK column) alongside the existing nullable `user_id`, with a CHECK constraint ensuring exactly one of `user_id`/`client_id` is non-null per row. Alternatively, add a new `client_otp_codes` table (cleaner isolation, same schema shape). The latter is recommended.

---

## 2. Client Session Strategy — Reuse Staff Auth Machinery With Role Isolation

**Recommendation: Reuse `issue_tokens` / `rotate_refresh` / `revoke_family` as-is. Distinguish client tokens via a new `Role.CLIENT` value. Do NOT fork the token machinery or add `aud` claims.**

### Why Reuse Works

`encode_access_token` is generic: it puts `{"sub": str(uuid), "role": role.value, "typ": "access", ...}` in the JWT. `decode_access_token` validates signature, expiry, and `typ` — it does not validate `role`. Adding `Role.CLIENT = "client"` to the existing `Role` StrEnum is a one-line change that flows through `AccessTokenClaims.role` correctly.

The existing `can()` function short-circuits to `True` for `OWNER` and does a set-membership check for `RECEPTION` against `OWNER_ONLY`. A `CLIENT` value falls through both branches and is denied all `OWNER_ONLY` pairs — but that is insufficient for staff route protection. Staff routes currently use `require_authenticated()` (which accepts any authenticated user including hypothetical clients) — these need an explicit guard or a separate dependency.

### Minimal Stack Delta (Backend)

| What | Where | Notes |
|------|-------|-------|
| `Role.CLIENT = "client"` | `app/core/permissions.py` | One line addition to `Role` StrEnum |
| Update `users` CHECK constraint | Alembic migration | `CHECK ck_users_role IN ('owner', 'reception', 'client')` — OR keep `clients` table separate from `users` and never create `Role.CLIENT` users in the `users` table (preferred) |
| `CurrentClient` Protocol | `app/core/dependencies.py` | Parallel to `CurrentUser`; has `id: UUID`, `phone: str` |
| `require_client_authenticated()` | `app/core/dependencies.py` | Decodes access token, asserts `role == Role.CLIENT`, loads `clients` row |
| `client_refresh_tokens` table | New Alembic migration | Mirror of `refresh_tokens` with FK to `clients.id` instead of `users.id`; same columns |
| Client auth router | `app/modules/client_auth/router.py` | New module under `app/modules/`; phone OTP request + verify + refresh + logout + `/me` |
| Client-scoped API router prefix | `app/api.py` or `app/main.py` | All client endpoints under `/api/v1/client/`; import-linter contract extended |

### Why NOT Add `aud` JWT Claim

Adding audience validation requires changing `decode_access_token`'s PyJWT `options` block (currently `{"require": ["sub", "role", "typ", "iat", "exp"]}`). This changes the staff token decode path — a cross-cutting change with regression risk. The `role="client"` discriminator in the `require_client_authenticated()` dependency achieves the same isolation at the FastAPI dependency layer without touching the JWT decode primitives. Defer audience claim to a future security hardening phase.

### Staff Route Protection Against Client Tokens

Staff routes using `require_authenticated()` will currently accept a client-role token (since `require_authenticated` only checks that the token is valid, not the role value). Two options:

1. Add `if current_user.role == Role.CLIENT: raise ForbiddenError("client_not_allowed")` inside `require_authenticated()` — makes the change at the dependency level, affects all staff routes at once.
2. Use `require_client_authenticated()` exclusively on client routes; never share `require_authenticated()` between staff and client routes.

Option 2 is cleaner: separate dependencies, separate routes, no shared path. Recommended.

### Redis Key Namespace

Client session keys use `client.id` (UUID) as `user_id` in the existing key pattern `cc:idem:{user_id}:...` and refresh-token family pattern. Since `clients.id` is UUIDv4 (different namespace from `users.id`), there is no practical collision — but the design relies on a statistical guarantee, not a structural one. Using `client_refresh_tokens` as a separate table (rather than a nullable `user_id` column on `refresh_tokens`) provides structural isolation. The Redis idempotency key pattern will need a `client:` prefix for client-scoped mutations to prevent cross-principal replay.

---

## 3. PWA Stack Alignment

### 3a. Workspace Entry

`pnpm-workspace.yaml` already declares `apps/*`. `apps/client-pwa` is automatically picked up — no `pnpm-workspace.yaml` change needed. Delete `apps/client-pwa/bun.lock` and run `pnpm install` from the monorepo root.

### 3b. Bun.lock Removal

Delete `apps/client-pwa/bun.lock`. There is no automated bun→pnpm migration tool. `package.json` is the source of truth; the lockfile is regenerated by pnpm from scratch. All declared dependencies (`react@18.3.1`, `react-router-dom@6.26.2`, `@vitejs/plugin-react@4.3.1`, `vite@5.4.8`) resolve correctly under pnpm.

### 3c. React 18 and React 19 Coexistence

`apps/admin-web` uses `react@^19.2.5`; `apps/client-pwa` uses `react@18.3.1`. pnpm resolves each app's dependencies from its own `package.json` — the two apps get separate React instances through pnpm's symlink tree. This is standard pnpm workspace behavior.

Potential `@types/react` conflict: if any shared package's devDeps leak `@types/react` into the workspace root node_modules, TypeScript may resolve the wrong version. The `@clubcore/api-client` package has no React imports or `@types/react` devDependency, so no real conflict exists in this project. If LSP confusion appears, add to `apps/client-pwa/tsconfig.json`:

```json
{
  "compilerOptions": {
    "paths": {
      "react": ["./node_modules/@types/react"]
    }
  }
}
```

React 18→19 upgrade for client-pwa is optional and not required for v2.0. Do not schedule it.

### 3d. Vite 5 → Vite 6 Alignment

| Package | From | To | Action |
|---------|------|----|--------|
| `vite` | `5.4.8` | `^6.x` | Update `apps/client-pwa/package.json` |
| `@vitejs/plugin-react` | `4.3.1` | `^5.0.0` | Required for Vite 6 — the v4 plugin does not support Vite 6 |

Breaking changes that affect this specific app:

- `commonjsOptions.strictRequires` defaults to `true` (was `'auto'`). React + react-router-dom are ESM; this change is unlikely to cause issues. Monitor build output. If CJS bundle errors appear: `build: { commonjsOptions: { strictRequires: false } }` in `vite.config.ts`.
- `resolve.conditions` internal defaults changed — no practical impact for a React SPA using ESM modules.
- The existing `vite.config.js` (`defineConfig` with `@vitejs/plugin-react`, `resolve.alias @/`, `build.target: 'es2020'`, `manualChunks`) requires no other changes for Vite 6.
- `vite.config.js` is renamed `vite.config.ts` as part of TypeScript migration.

### 3e. TypeScript: Incremental JS→TS Adoption

**Strategy: `allowJs: true` + `strict: false` initially; rename files one folder at a time; tighten later.**

The PWA is approximately 20 source files (4 screen JSX files, hooks, utils, context, services, App). Full manual rename is feasible in one phase with `allowJs: true` as a safety net.

Target `apps/client-pwa/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": false,
    "allowJs": true,
    "checkJs": false,
    "noEmit": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"],
      "@clubcore/api-client": ["../../packages/api-client/src/index.ts"]
    }
  },
  "include": ["src", "vite.config.ts"]
}
```

Tighten to `strict: true` + remove `allowJs` in a follow-up phase after all `.jsx` → `.tsx` renames are done. Migration order: `utils/` → `hooks/` → `context/` → `components/` → `screens/` → `App.tsx` → `main.tsx`.

Do not use `ts-migrate` (Airbnb's tool) — the codebase is small enough for manual rename. The tool adds `@ts-ignore` comments liberally, which obscures type errors rather than resolving them.

### 3f. Wiring `@clubcore/api-client` in a react-router-dom App

`fetcher.ts` is framework-agnostic (D-A2 states explicitly: "NO router/window/redirect logic here"). It uses native `fetch` with `credentials: 'include'`. It can be imported from react-router-dom apps directly.

**Required change to shared `fetcher.ts`:** The `AUTH_EXEMPT_PATHS` constant must include client auth endpoints. These are logically equivalent to staff auth endpoints (no refresh attempt on OTP/verify/refresh endpoints):

```typescript
// Add to AUTH_EXEMPT_PATHS in packages/api-client/src/fetcher.ts:
'/api/v1/client/auth/otp/request',
'/api/v1/client/auth/verify',
'/api/v1/client/auth/refresh',
'/api/v1/client/auth/logout',
'/api/v1/client/me',
```

This change affects both admin-web and client-pwa since they share `fetcher.ts`. Admin-web is unaffected (it never calls client paths). The change is additive and safe.

**Usage in react-router-dom v6 component (simplest pattern):**

```typescript
import { request, ApiError } from '@clubcore/api-client'

// In a hook or component:
const data = await request('GET', '/api/v1/client/me')
```

**Usage in react-router-dom v6.4+ loader (data API):**

```typescript
import { request, ApiError } from '@clubcore/api-client'
import { redirect } from 'react-router-dom'

export async function clientMeLoader() {
  try {
    return await request('GET', '/api/v1/client/me')
  } catch (err) {
    if (err instanceof ApiError && err.code === 'session_expired') {
      return redirect('/login')
    }
    throw err
  }
}
```

No TanStack Query is needed for the client-pwa data layer in v2.0. React-router-dom's data API loaders or simple `useEffect`-based fetching are sufficient. TanStack Query can be added later if caching/prefetching becomes a priority.

### 3g. OpenAPI Codegen: Single Spec, Additive Client Paths

**Keep one `openapi.json`, one `schema.d.ts`.** Client-facing paths (`/api/v1/client/...`) are added to the same FastAPI app with a `tags=["Client"]` group. The existing `@clubcore/api-client` codegen script (`openapi-typescript ../../apps/backend/openapi.json --output src/schema.d.ts`) continues to work unchanged. The generated `schema.d.ts` grows to include client path types alongside staff path types.

The existing drift gate (`git diff --exit-code apps/backend/openapi.json packages/api-client/src/schema.d.ts`) and `AssertNonNever` guards continue to work. New `AssertNonNever` entries for client paths are added per-phase per the established milestone discipline.

The existing `redocly.yaml` (which lints the staff-only spec) will lint client paths automatically since they are in the same file — no `redocly.yaml` changes required.

**Do not split into two OpenAPI specs.** The redocly.yaml multi-schema (`x-openapi-ts.output`) approach is available in `openapi-typescript@^7.13.0` but adds codegen complexity with no benefit for a single-backend project.

---

## 4. PWA Testing Tooling Alignment

**Add Vitest + jsdom + React Testing Library to `apps/client-pwa`, matching the admin-web pattern.**

| Tool | Version | Why |
|------|---------|-----|
| `vitest` | `~2.1.8` | Match workspace version (admin-web pinned to `~2.1.8`) |
| `jsdom` | `~25.0.1` | Match admin-web |
| `@testing-library/react` | `^16.x` | React 18 compatible; co-located test pattern |
| `@testing-library/jest-dom` | `^6.x` | Matchers |

`vitest.config.ts` for client-pwa:

```typescript
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
})
```

Tests co-located as `*.test.ts(x)` siblings (matches admin-web convention).

Do not add Playwright or Cypress for v2.0. E2E testing is not in the existing stack.

---

## Recommended Stack Additions — Consolidated

### Backend (new for v2.0)

| Technology | Version | Purpose | Notes |
|------------|---------|---------|-------|
| `app/integrations/telegram_gateway/` | (custom code) | Telegram Gateway OTP delivery | `httpx.AsyncClient` adapter; no new pip dep |
| `TELEGRAM_GATEWAY_TOKEN` env var | config only | Gateway API authentication | Add to `app/core/config.py` as `SecretStr` with placeholder default |
| `Role.CLIENT = "client"` | Python StrEnum | Client principal discriminator | One-line addition to `app/core/permissions.py` |
| `CurrentClient` Protocol | `app/core/dependencies.py` | Typed client identity for dependencies | Parallel to `CurrentUser` |
| `require_client_authenticated()` | `app/core/dependencies.py` | Client-only dependency factory | Asserts `role == CLIENT`; no shared path with staff |
| `client_refresh_tokens` table | Alembic migration | Client session token storage | FK to `clients.id`; mirrors `refresh_tokens` structure |
| `client_otp_codes` table (or add `client_id` FK) | Alembic migration | Client OTP storage, phone-anchored | Prefer separate table for clean isolation |
| `app/modules/client_auth/` | FastAPI router | Phone OTP request + verify + refresh + logout + `/me` | New module under `app/modules/` |
| `app/modules/client_*/` | FastAPI routers | Client-scoped domain endpoints (memberships, bookings, etc.) | New modules; all under `/api/v1/client/` prefix |

### Frontend (new for `apps/client-pwa`)

| Technology | Version | Purpose | Notes |
|------------|---------|---------|-------|
| `typescript` | `~5.7.2` | Type safety | Match workspace version |
| `vite` | `^6.x` | Build tool | Align with admin-web |
| `@vitejs/plugin-react` | `^5.0.0` | Vite 6 compatibility | Required with Vite 6 |
| `@clubcore/api-client` | `workspace:*` | Typed transport | Add to `dependencies` in package.json |
| `vitest` | `~2.1.8` | Testing | Match admin-web |
| `jsdom` | `~25.0.1` | Test DOM | Match admin-web |
| `@testing-library/react` | `^16.x` | Component testing | React 18 compatible |
| `@testing-library/jest-dom` | `^6.x` | Test matchers | Standard with Testing Library |

### What NOT to Add or Change

| Do NOT add/change | Reason |
|-------------------|--------|
| TanStack Router | User decision: react-router-dom v6 stays. Not migrating. |
| TanStack Query | Not required for v2.0; react-router-dom loaders or `useEffect` suffice. Add later if needed. |
| React 18→19 upgrade in client-pwa | Optional; no architectural blocker; defer. |
| SMS provider (`smsaero-api`, SMSC.ru) | Defer to SMS fallback phase; Telegram Gateway covers v1. |
| Twilio | Non-starter in RF/CIS; unreliable Russian SMS termination since 2022. |
| `telegram-gateway` PyPI package | Use custom `httpx` adapter instead; fewer deps; follows project integration discipline. |
| `aud` JWT claim | Not needed; `role="client"` discriminator in `require_client_authenticated()` is sufficient. |
| Two OpenAPI specs or two `schema.d.ts` files | Unnecessary complexity; one backend, one spec, additive client paths. |
| `@hey-api/openapi-ts` | Different package from `openapi-typescript`; incompatible model; do not introduce. |
| `ts-migrate` | Codebase is small; manual file rename is correct approach. |
| Playwright / Cypress | Not in existing stack; adds infra overhead; defer. |
| Pre-commit hooks | Not in existing stack; CI gates are the enforcement layer. |
| Kubernetes / production deploy | Out of scope per PROJECT.md. |

---

## Installation Commands

```bash
# Step 1: Remove bun lockfile and let pnpm take over
rm apps/client-pwa/bun.lock

# Step 2: From monorepo root — installs all workspace members
pnpm install

# Step 3: Update client-pwa for Vite 6 + TypeScript + testing
pnpm --filter gym-app add -D \
  typescript@~5.7.2 \
  vite@^6 \
  @vitejs/plugin-react@^5.0.0 \
  vitest@~2.1.8 \
  jsdom@~25.0.1 \
  "@testing-library/react@^16" \
  "@testing-library/jest-dom@^6"

# Step 4: Add @clubcore/api-client as a workspace dependency
# In apps/client-pwa/package.json, add to "dependencies":
# "@clubcore/api-client": "workspace:*"
# Then:
pnpm install

# Step 5: Backend — no new pip packages for v2.0 client auth
# (httpx already installed; Telegram Gateway adapter is custom code)
# The only config addition is TELEGRAM_GATEWAY_TOKEN in .env

# Deferred — NOT in v2.0:
# uv add smsaero-api
```

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `vite@^6` | `@vitejs/plugin-react@^5.0.0` | v4 plugin does not support Vite 6; upgrade together |
| `react@18.3.1` | `@testing-library/react@^16.x` | RTL 16 supports React 18 |
| `react@18.3.1` | `react-router-dom@6.26.2` | No change; RRD v6 works on React 18 |
| `react@18.3.1` (client-pwa) | `react@^19.2.5` (admin-web) | pnpm resolves per-workspace; no conflict |
| `openapi-typescript@^7.13.0` | Additive client paths in `schema.d.ts` | No version change; codegen script unchanged |
| `typescript@~5.7.2` | `allowJs: true` | Standard TS feature; enables gradual migration |

---

## Sources

- `apps/client-pwa/package.json` — React 18.3.1, Vite 5.4.8, react-router-dom 6.26.2, bun.lock present
- `apps/client-pwa/vite.config.js` — current config: react plugin, alias `@/`, port 5173, es2020 target
- `apps/client-pwa/src/main.jsx` — BrowserRouter, TweaksProvider, UIContext, plain JSX entry point
- `packages/api-client/src/fetcher.ts` — confirmed D-A2 framework-agnostic, `AUTH_EXEMPT_PATHS` hardcoded list, `credentials: 'include'`
- `packages/api-client/src/index.ts` — public surface: `request`, `ApiError`, `paths`, `components`
- `packages/api-client/package.json` — `openapi-typescript@^7.13.0` codegen script
- `apps/backend/app/modules/auth/router.py` — confirmed OTP channel infrastructure and discriminator
- `apps/backend/app/modules/auth/models.py` — confirmed `OtpChannel = Literal["telegram", "email"]`
- `apps/backend/app/core/permissions.py` — confirmed `Role` StrEnum with only `OWNER` / `RECEPTION`
- `apps/backend/app/core/security.py` — confirmed `AccessTokenClaims` shape: `sub, role, typ, iat, exp`
- `apps/backend/app/core/dependencies.py` — confirmed `CurrentUser` Protocol, `require_authenticated()` factory structure
- `apps/backend/app/modules/clients/models.py` — confirmed `clients.phone` column + partial unique index
- `apps/backend/app/core/config.py` — confirmed `otp_code_ttl_seconds`, `otp_max_attempts`, placeholder-default discipline pattern
- `pnpm-workspace.yaml` — confirmed `apps/*` glob; client-pwa auto-included
- [Telegram Gateway API](https://core.telegram.org/gateway) — HIGH confidence: $0.01/code; `checkSendAbility` free for unreachable numbers; REST HTTP API; 4 methods
- [smsaero-api on PyPI](https://pypi.org/project/smsaero-api/) — HIGH confidence: v3.2.0 (2026-04-01), sync-only, email+apikey auth
- [SMSC.ru API](https://smsc.ru/api/) — MEDIUM confidence: HTTP GET/POST + JSON (fmt=3), no official Python SDK
- [Vite 5→6 migration guide](https://v6.vite.dev/guide/migration) — HIGH confidence: `@vitejs/plugin-react@^5` required; React SPAs upgrade smoothly; `strictRequires` change documented
- [openapi-typescript CLI](https://openapi-ts.dev/cli) — HIGH confidence: single-spec approach is standard; multi-schema via `redocly.yaml` available but not needed here
- [TypeScript JS→TS migration handbook](https://www.typescriptlang.org/docs/handbook/migrating-from-javascript.html) — HIGH confidence: `allowJs: true`, incremental file rename
- pnpm workspace React version coexistence — MEDIUM confidence (community + docs): per-workspace isolation; `paths` tsconfig override for `@types/react` if needed
- [Vitest + jsdom + React Testing Library setup](https://dev.to/pacheco/configure-vitest-with-react-testing-library-5cbb) — HIGH confidence: standard pattern, matches admin-web config

---

*Stack research for: clubcore v2.0 Client PWA + Client-facing backend API*
*Researched: 2026-05-29*
