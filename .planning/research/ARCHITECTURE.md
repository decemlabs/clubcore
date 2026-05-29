# Architecture Patterns: v2.0 Client Portal Integration

**Domain:** Client-facing API + PWA layered over an existing FastAPI modular monolith gym CRM
**Researched:** 2026-05-29
**Confidence:** HIGH — based on direct code inspection of all relevant source files

---

## Recommended Architecture

### Decision 1: Where Client Endpoints Live

**Recommendation: A new `app/modules/client_portal/` aggregator module exposing client-scoped views.**

Do NOT add client-scoped routes inside each existing domain module. Do NOT use a standalone FastAPI app.

**Rationale:**

The `modules-independent` importlinter contract already has precedent for a read-only cross-module aggregator: `app/modules/reports/` uses raw-SQL `text()` reads across `payments`, `memberships`, `clients`, and `visits` tables with zero new `ignore_imports` edges (D-54-08). The `client_portal` module follows the same pattern for its read side.

For writes (booking creation, checkout initiation), the client_portal router delegates to existing domain services through the composition-root Protocol slot pattern already established for cross-module callbacks (`PaymentRecorder`, `BookingCompleter`, `ActiveMembershipResolver`, etc.). No new importlinter edges are needed for the slot-mediated path.

The URL space is a separate prefix: `/api/v1/client/*`. This is mounted as a new top-level entry in `app/api/v1/router.py` alongside existing staff routers. The frozen staff paths (`/api/v1/memberships`, `/api/v1/bookings`, etc.) are untouched.

**New `app/modules/client_portal/` structure:**

```
app/modules/client_portal/
  __init__.py
  router.py          # FastAPI APIRouter(tags=["Client-Portal"])
  service.py         # thin orchestration: calls domain services via Protocol slots
  repository.py      # raw-SQL text() reads (D-54-08 discipline for reads)
  schemas.py         # client-facing response/request shapes (no staff schemas reused)
  permissions.py     # require_client() dependency + ownership guard
  auth_router.py     # /client/auth/* (phone+OTP, refresh, logout, /me)
  auth_service.py    # client-specific OTP logic wrapping existing OTP infrastructure
  constants.py
```

**importlinter registration:**

Add `app.modules.client_portal` to the `modules-independent` contract. Its read side uses raw SQL (zero `ignore_imports`). Its write side uses Protocol slots defined in `app.core.dependencies` (zero `ignore_imports`). The only needed `ignore_imports` edges are for narrow service-layer needs analogous to existing exceptions (e.g. `client_portal.auth_service -> app.modules.clients.models` for the phone lookup, `client_portal.auth_service -> app.modules.auth.models` for OtpCode, parallel to existing `online_payments.service -> clients.models`).

---

### Decision 2: Client Principal and RBAC

**Recommendation: A parallel, non-intersecting dependency `require_client` — NOT an extension of `Role`/`permissions.py`.**

**Rationale:**

The existing `Role` StrEnum (`owner`, `reception`) + `OWNER_ONLY` matrix is byte-paritized with the frozen admin-web `can.ts` + `registry.ts`. Adding a `client` role there would require changes to the frozen admin-web or breaking the three-way parity test. Neither is acceptable.

Instead, the client principal is entirely separate:

1. **New `ClientPrincipal` Protocol** in `app/core/dependencies.py` (parallel to `CurrentUser`):
   ```python
   class ClientPrincipal(Protocol):
       id: UUID          # Client.id (not User.id)
       client_id: UUID   # same as id, aliased for clarity at call sites
   ```

2. **New `require_client()` dependency** in `app/core/dependencies.py` (parallel to `require_permission`/`require_authenticated`). It:
   - Reads the `cc_client_access` cookie (distinct cookie name — see Decision 3)
   - Decodes a client-flavored JWT (distinct `aud` claim: `"client"` vs no aud for staff)
   - Looks up the `Client` row (via a new Protocol slot `register_client_loader`)
   - Returns a `ClientPrincipal`
   - Never touches `Role`, `OWNER_ONLY`, or `can()`

3. **Ownership enforcement** is a function `assert_owns(client_principal, resource_client_id)` used at the service layer — raises `ForbiddenError('client_ownership_violation')` if `client_principal.client_id != resource_client_id`. This is the single chokepoint (see Decision 4).

**Three-way parity test:** The client principal has NO parity mirror in admin-web because admin-web is staff-only and frozen. The parity test remains unchanged. Client-portal RBAC is its own orthogonal concern, enforced entirely server-side through `require_client` + ownership guards. A new independent test (`test_client_portal_rbac.py`) covers client access patterns separately, never touching the existing parity test.

**Route introspection test (TEST-07):** TEST-07 currently asserts every non-auth route uses `require_permission` or `require_authenticated`. It must be extended to recognize `require_client` as a third valid guard factory. The check is: `__qualname__.startswith('require_client.')`. Without this extension, TEST-07 fails for all client routes.

---

### Decision 3: Auth Wiring — Client Login

**Recommendation: New endpoints `/api/v1/client/auth/*` with distinct cookie names and a separate JWT audience claim, fully reusing the refresh-rotation + CSRF machinery.**

**Cookie separation:**

| Cookie | Staff | Client |
|--------|-------|--------|
| Access token | `cc_access` | `cc_client_access` |
| Refresh token | `cc_refresh` | `cc_client_refresh` |
| CSRF | `clubcore_csrf` | `cc_client_csrf` |

The cookie names are different to prevent cross-principal session confusion. The existing `verify_csrf` in `app/core/dependencies.py` reads `clubcore_csrf` and `X-CSRF-Token`. Client endpoints use a parallel `verify_client_csrf` that reads `cc_client_csrf` and the same `X-CSRF-Token` header (the header name is shared — it is the transport mechanism, not an identifier).

**JWT audience claim:** Client JWTs carry `aud: "client"` claim; staff JWTs carry no `aud`. The `decode_access_token` function in `app/core/security.py` is extended with an optional `audience` parameter (default `None` for staff backward compatibility). A new `decode_client_access_token` wrapper validates `aud == "client"`. This is additive and does not break existing staff token decode paths.

**OTP infrastructure reuse:**

The existing `OtpCode` ORM model (`app/modules/auth/models.py`) already supports an `OtpChannel` discriminator (`"telegram"` | `"email"`). Client phone+OTP login introduces a new OTP purpose distinguishing client login from staff login. The `client_portal/auth_service.py` calls into the existing `OtpCode` insert/verify machinery via the composition root — it does NOT duplicate the code. The narrow `ignore_import` edge `client_portal.auth_service -> app.modules.auth.models` is the only edge needed (mirrors `online_payments.service -> app.modules.clients.models`).

**`register_client_loader` — new composition-root slot:**

A new composition-root slot `register_client_loader` is added to `app/core/dependencies.py`. It is filled in `create_app()` with `clients_service.load_client_by_id`. This is the same pattern as `register_user_loader` (Phase 5 D-15) — the 18th composition-root carve-out. The `get_current_client` dependency reads `cc_client_access`, decodes the client JWT, then calls through `_client_loader` to fetch the `Client` row.

**Refresh rotation:** The client refresh endpoint (`POST /api/v1/client/auth/refresh`) reads `cc_client_refresh` and calls the same refresh-rotation logic. The existing `RefreshToken` table is reused with a new `purpose: Literal["staff", "client"]` column added in a new Alembic migration (with an index on `(token_hash, purpose)`). This is the simplest path: the `rotate_refresh` function accepts a `purpose` parameter. The `revoke_all_sessions` for a staff user filters by `user_id` (users.id) — client tokens store `client_id` (clients.id) in a separate column and are structurally invisible to the staff revocation sweep. Making this explicit with a `purpose` discriminator is the clean approach.

**PUBLIC_ENDPOINT_OPERATION_IDS** in `app/main.py` is extended with the new client auth endpoints (client-login, client-refresh, client-otp-request, etc.) per the existing frozenset-literal pattern (visible in diff, auditable).

---

### Decision 4: Data Isolation Enforcement Point

**Recommendation: Service-layer ownership guard (`assert_owns`) called at every client-portal service function, backed by repository-layer `WHERE client_id = :client_id` parameter injection. NOT a middleware or ORM event.**

**Single chokepoint design:**

```python
# app/modules/client_portal/permissions.py

def assert_owns(principal: ClientPrincipal, row_client_id: UUID) -> None:
    """Raise NotFoundError (not ForbiddenError) if the row does not belong to this client.

    404 collapse is intentional: returning 403 when the row exists but belongs to
    another client leaks the existence of that row (anti-oracle violation, mirrors
    bot self-checkin discipline). Only the owning client may know the row exists.

    This is the ONLY place where client data-isolation is enforced for
    the client portal for get-by-id endpoints. List endpoints enforce isolation
    via mandatory client_id WHERE clause in the repository function signature.
    """
    if row_client_id != principal.client_id:
        raise NotFoundError("not_found")
```

Two patterns enforce isolation:

1. **List endpoints:** The repository function always accepts `client_id: UUID` and injects it as a mandatory WHERE clause parameter. The caller cannot omit it (it is not optional in the function signature). Example:
   ```python
   async def get_client_memberships(session: AsyncSession, client_id: UUID) -> list[...]: ...
   # SQL: WHERE memberships.client_id = :client_id
   ```

2. **Get-by-ID endpoints:** After fetching by primary key, `assert_owns(principal, row.client_id)` is called before returning. This collapses 404 and 403 into a single anti-oracle response (return 404 when the row exists but belongs to another client).

**Why NOT middleware:** Middleware cannot know the `client_id` inside a fetched row without running the query twice. Service-layer enforcement is the correct DDD pattern.

**Why NOT repository-layer-only:** The get-by-ID pattern inherently requires a fetch then a check. Enforcing only at the repository level would require passing both the pk AND the client_id to every repository function, which is error-prone for the id-lookup case. The two-pattern approach is cleaner.

**Test strategy for anti-oracle (cross-client leakage):**

Every client-portal service function needs a test that:
1. Creates two clients with separate data rows (e.g. two memberships owned by different clients)
2. Authenticates as client A (via `require_client()` stub in test)
3. Attempts to access client B's row by its UUID
4. Asserts HTTP 404 (not 403, and never 200)

A parametrized `test_client_cannot_access_other_client_{resource}` sweep analogous to the existing `reception-403 enumeration` test (121 assertions) covers all client-owned resources. This sweep test fails the build if any new client endpoint is added without a corresponding anti-oracle test.

---

### Decision 5: Contract Handoff — Client Paths in OpenAPI

**Recommendation: Separate OpenAPI tag group `"Client-Portal"` added to `OPENAPI_TAGS` in `app/main.py`. Client operationIds are prefixed `client_`. Staff `openapi.json` paths and operationIds are structurally unchanged. Parallel frozensets for client public endpoints and client category-A operations follow the existing discipline.**

**Approach:**

1. `OPENAPI_TAGS` in `app/main.py` gets a new entry inserted between `"Audit-log"` and `"Internal"`:
   ```python
   {"name": "Client-Portal", "description": "Client-facing self-service API — phone/OTP auth + owned-data reads + checkout."}
   ```

2. Client router uses `APIRouter(tags=["Client-Portal"])`. Because the tag name is distinct, Redocly renders client endpoints in a separate group. The existing 12-domain tag ordering for staff is unaffected.

3. **operationId naming:** Client handler functions are named `client_get_my_memberships`, `client_create_booking`, etc. The `custom_unique_id` function in `app/main.py` strips the `_api_v1_*` suffix — client handler names already have the `client_` prefix so no additional collision guard is needed.

4. **`PUBLIC_ENDPOINT_OPERATION_IDS`** grows to include client auth endpoints (frozenset literal, visible in diff).

5. **`CATEGORY_A_OPERATION_IDS`** grows with client mutating endpoints that need idempotency keys (client booking creation, client booking cancellation, client checkout). New `CLIENT_CATEGORY_A_OPERATION_IDS` frozenset is added separately to keep the diff minimal and auditable, then merged into the per-operation walk in `_customize_openapi`.

6. **`schema.d.ts` and drift gate:** The existing codegen drift gate (`pnpm --filter @clubcore/api-client codegen`) generates a new `schema.d.ts` covering both staff and client paths. The `schema.contract.test.ts` `AssertNonNever` tuple grows with a `_v20Checks` epic banner block for client operationIds. Staff guards (`_v19Checks`, `_v18Checks`, etc.) are untouched.

7. **Staff contract preservation:** The staff operationIds under `/api/v1/auth/*`, `/api/v1/clients/*`, `/api/v1/memberships/*`, etc. are unchanged. The committed `openapi.json` after v2.0 contains the v1.11 staff paths exactly as frozen, plus the new client paths. The drift gate detects any regression in either group.

---

### Decision 6: PWA Data Flow

**Recommendation: Wrap the shared `fetcher.ts` in a PWA-local `clientFetcher.ts` that overrides the CSRF cookie name. Add TanStack Query v5 to the PWA. Use react-router v6 loaders with `queryClient.ensureQueryData` for route-level prefetch.**

**`fetcher.ts` reuse — no change to the shared file:**

The existing `fetcher.ts` reads `clubcore_csrf` for CSRF (hardcoded). Rather than adding a parameter to the shared fetcher (which would require touching a file admin-web depends on), the PWA creates its own thin wrapper:

```typescript
// apps/client-pwa/src/api/clientFetcher.ts
// Wraps the shared fetcher with cc_client_csrf cookie name override.
// The shared fetcher is not modified — admin-web freeze is preserved.
import type { paths } from '@clubcore/api-client/schema'

// Re-implemented CSRF reader for the client cookie name
function readClientCsrfCookie(): string | undefined { ... }

// Thin wrapper: same signature as request(), but reads cc_client_csrf
export async function clientRequest<P extends keyof paths, M extends keyof paths[P] & string>(
  method: M, path: P, init?: RequestInitWithBody
): Promise<unknown> { ... }
```

Client auth-exempt paths use `/api/v1/client/auth/*` prefix instead of `/api/v1/auth/*`. The single-flight refresh targets `/api/v1/client/auth/refresh`.

**TanStack Query v5** is added to the PWA (`@tanstack/react-query@^5`). The same version already in admin-web is used. Per-screen hooks follow the `clientXxxKeys` factory pattern. A single `clientQueryClient` instance is created in the PWA's app root — separate from admin-web's `QueryClient`.

**react-router v6 loaders:** Each route's `loader` function calls `clientQueryClient.ensureQueryData(clientMembershipsKeys.list(), fetchMyMemberships)` to prefetch data before render. This mirrors the TanStack Router `ensureQueryData` pattern used in admin-web but adapted for react-router v6's `loader` API.

**Auth state in PWA:** A lightweight Zustand store (already in PWA or simple `useState` + context) tracks whether the client session is live. On `session_expired` ApiError from `clientFetcher`, the PWA redirects to `/login`. No redirect logic in the fetcher itself (mirrors admin-web D-A2).

---

### Decision 7: Suggested Build Order

**Phase 68 — Client Auth Foundations**
- New `ClientPrincipal` Protocol + `register_client_loader` slot in `app/core/dependencies.py`
- `require_client()` dependency + `verify_client_csrf` dependency in `app/core/dependencies.py`
- `decode_client_access_token()` in `app/core/security.py` (additive, backward-compatible)
- Client cookie name constants in `app/core/config.py`
- Alembic migration: `purpose` column on `refresh_tokens` (or `client_refresh_tokens` table)
- `app/modules/client_portal/auth_service.py` + `auth_router.py` — phone+OTP request/verify, refresh, logout, `/me`
- `PUBLIC_ENDPOINT_OPERATION_IDS` extended; `OPENAPI_TAGS` extended with `"Client-Portal"` tag
- Mount `client_portal_auth_router` at `/api/v1/client/auth` in `app/api/v1/router.py`
- `register_client_loader` wired in `app/main.py:create_app()` (18th carve-out)
- Route introspection test (TEST-07) extended to recognize `require_client` as valid guard
- Tests: client login/refresh/logout + anti-oracle OTP (unknown phone → same 202)
- OpenAPI: `schema.d.ts` regen with client auth operationIds; `_v20ClientAuthChecks` AssertNonNever

**Phase 69 — Client-Scoped Read Endpoints (catalog + own data)**
- `app/modules/client_portal/repository.py` with raw-SQL reads (D-54-08 discipline, zero ignore_imports)
- `app/modules/client_portal/permissions.py` with `assert_owns()`
- `app/modules/client_portal/router.py` — read endpoints:
  - `GET /api/v1/client/me` (profile — own Client row)
  - `GET /api/v1/client/memberships` + `GET /api/v1/client/memberships/{id}` (own memberships)
  - `GET /api/v1/client/visits` (own visit history)
  - `GET /api/v1/client/pt-sessions` (own PT session history)
  - `GET /api/v1/client/payments` (own payment history)
  - `GET /api/v1/client/membership-plans` (catalog — open, no ownership guard)
  - `GET /api/v1/client/trainers` (catalog — open, no ownership guard)
  - `GET /api/v1/client/schedule` (available slots — open read)
- Anti-oracle cross-client sweep tests (one assertion per owned resource type)
- `schema.d.ts` codegen, `_v20ClientReadChecks` AssertNonNever block

**Phase 70 — Client Bookings Write + QR Check-In**
- New `ClientBookingCreator` Protocol slot in `app/core/dependencies.py` (or reuse existing bookings service via raw-SQL validation in `client_portal/service.py`)
- `POST /api/v1/client/bookings` (create booking for self — `client_id` locked to principal)
- `DELETE /api/v1/client/bookings/{id}` or `POST /api/v1/client/bookings/{id}/cancel`
- `POST /api/v1/client/visits/qr-checkin` (self check-in via QR token — reuses existing visit service slot)
- Idempotency-Key on booking create + cancel (extend `CATEGORY_A_OPERATION_IDS`)
- Tests: booking create + cancel + idempotency replay + cross-client guard
- `schema.d.ts` update, `_v20ClientWriteChecks` additions

**Phase 71 — Client Checkout (ЮKassa)**
- `POST /api/v1/client/checkout/membership/{plan_id}` — self-initiated membership purchase
- `POST /api/v1/client/checkout/pt-package/{plan_id}` — self-initiated PT package purchase
- Both delegate to existing `online_payments` service logic via Protocol slots; `received_by_user_id = None` (client self-purchase)
- Email gate enforced: client must have email set for fiscal receipt (FIS-05 discipline reused)
- Idempotency-Key on both checkout endpoints (extend `CATEGORY_A_OPERATION_IDS`)
- The ЮKassa webhook (`/_internal/yookassa/webhook`) already handles `payment.succeeded` — no change needed
- Tests: checkout flow + email gate + idempotency + cross-client guard
- `schema.d.ts` final staff+client regen

**Phase 72 — PWA Wiring + OpenAPI Handoff**
- PWA stack alignment: migrate `apps/client-pwa` to pnpm workspace, add TypeScript strict, `@clubcore/api-client` dependency, shared ESLint/Prettier config
- `apps/client-pwa/src/api/clientFetcher.ts` (wraps shared fetcher with `cc_client_csrf`)
- TanStack Query v5 added to PWA `package.json`
- Screen wiring: Login/OTP, Home (memberships overview), Profile, Book (trainer slots), Schedule browser, Payments history, Checkout, QR check-in
- All screens use `clientRequest` + TanStack Query hooks
- `schema.d.ts` final codegen covering all v2.0 client paths
- `_v20Checks` AssertNonNever tuple completed (all client operationIds in one epic banner)
- Drift gate updated: committed `openapi.json` now includes client paths; staff subset verified identical to v1.11 baseline
- CI: all 7 existing gates remain green; add `client-pwa typecheck`, `client-pwa lint`, `client-pwa test` gates

---

## Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `app/modules/client_portal/auth_router.py` | Phone+OTP login, refresh, logout, /me for clients | `client_portal/auth_service.py` |
| `app/modules/client_portal/auth_service.py` | OTP issue/consume, client JWT mint, refresh rotation | `app/modules/auth/models.py` (OtpCode — via `ignore_import`), `app/modules/clients/models.py` (phone lookup — via `ignore_import`), `app/core/security.py` |
| `app/modules/client_portal/router.py` | All client-scoped business endpoints | `client_portal/service.py`, `client_portal/permissions.py` |
| `app/modules/client_portal/service.py` | Write orchestration via Protocol slots; read delegation to repository | Protocol slots in `app/core/dependencies.py` only |
| `app/modules/client_portal/repository.py` | raw-SQL `text()` reads across existing domain tables | `AsyncSession` only — zero ORM model imports from other modules |
| `app/modules/client_portal/permissions.py` | `require_client()` dep, `verify_client_csrf` dep, `assert_owns()` | `app/core/dependencies.py` (ClientPrincipal Protocol) |
| `app/core/dependencies.py` (extended) | `ClientPrincipal`, `register_client_loader`, `get_current_client`, `require_client`, `verify_client_csrf` | No new module imports (Protocol boundary maintained) |
| `app/core/security.py` (extended) | `decode_client_access_token`, client cookie name constants | No new module imports |
| `app/main.py` (extended) | Wire `register_client_loader`; extend frozensets; extend `OPENAPI_TAGS` | `app/modules/clients.service.load_client_by_id` (18th carve-out) |
| `packages/api-client` | Typed `schema.d.ts` covering both staff and client paths | Generated from `openapi.json` |
| `apps/client-pwa` | React 18 + react-router v6 + TanStack Query + `clientFetcher.ts` | `packages/api-client` (typed schema) |

---

## Data Flow Examples

**Client login (phone+OTP):**
```
POST /api/v1/client/auth/otp/request
  → client_portal/auth_router.py
  → client_portal/auth_service.py → request_client_otp(phone)
    → Client lookup by phone (ignore_import: client_portal.auth_service -> clients.models)
    → OtpCode INSERT purpose='client_login' (ignore_import: -> auth.models)
    → SMS/Telegram dispatch via existing notification infrastructure
  → 202 anti-oracle response (identical shape for known/unknown phone)

POST /api/v1/client/auth/otp/verify
  → auth_service.consume_client_otp(phone, code)
    → OtpCode SELECT + Argon2 verify + mark consumed
    → Client row lookup by phone
    → encode_client_access_token(client_id, aud="client")
    → RefreshToken INSERT purpose="client" + family_id
    → issue_client_session_cookies(cc_client_access, cc_client_refresh, cc_client_csrf)
  → 200 + cookies set
```

**Client reads own memberships:**
```
GET /api/v1/client/memberships
  → require_client() -> get_current_client()
    → decode_client_access_token(cc_client_access cookie) — validates aud="client"
    → _client_loader(session, client_id) -> Client row
    -> returns ClientPrincipal
  → client_portal/router.py → repository.get_client_memberships(session, client_id=principal.client_id)
    → raw SQL: SELECT ... FROM memberships WHERE client_id = :client_id AND status != 'deleted'
  → response
```

**Client gets one membership by ID (anti-oracle pattern):**
```
GET /api/v1/client/memberships/{id}
  → require_client() -> ClientPrincipal
  → repository.get_membership_by_id(session, membership_id=id)
    → raw SQL: SELECT ... FROM memberships WHERE id = :id
  → assert_owns(principal, row.client_id)
    → if mismatch: raise NotFoundError("not_found")  # 404, not 403 (anti-oracle)
  → response
```

**Client checkout (ЮKassa):**
```
POST /api/v1/client/checkout/membership/{plan_id}
  → require_client() + verify_client_csrf
  → Idempotency-Key header validated (verify_idempotency bound to client principal)
  → client_portal/service.py -> initiate_client_checkout(session, principal, plan_id)
    → validate: client has email (fiscal receipt gate, mirrors FIS-05)
    → validate: plan exists + is_active (raw SQL read)
    → get_payment_recorder() [existing Protocol slot] — method='online', client_id locked
    → create ЮKassa payment (via existing get_yookassa_client_provider() slot)
  → 200 with redirect_url / qr_url
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Extending `Role` with a `client` value
**What:** Adding `Role.CLIENT = "client"` to `app/core/permissions.py` and using `require_permission` for client routes.
**Why bad:** Breaks byte-parity with frozen admin-web `can.ts`. The three-way parity test (TEST-06) fails. Admin-web would need updates (frozen). Staff RBAC semantics (owner > reception) do not translate to client semantics (all clients are peers, distinguished only by `client_id` ownership predicate).
**Instead:** Separate `ClientPrincipal` + `require_client` — fully orthogonal to staff RBAC.

### Anti-Pattern 2: Adding client routes inside existing domain modules
**What:** Adding `GET /memberships/my` inside `app/modules/memberships/router.py`.
**Why bad:** Bleeds the modules-independent contract. Memberships router would need to import `ClientPrincipal` from `app/core/dependencies` — currently legal but semantically wrong; more critically it mixes staff and client RBAC in one file, making ownership guards easy to miss. The route introspection test (TEST-07) would need to be weakened.
**Instead:** All client-scoped routes live in `app/modules/client_portal/`.

### Anti-Pattern 3: Sharing staff JWT cookies with the client principal
**What:** Reusing `cc_access` / `cc_refresh` / `clubcore_csrf` cookies for client sessions.
**Why bad:** Without distinct cookie names AND a distinguishing JWT claim (`aud`), a client who obtained a staff token could call client endpoints with it, or vice versa. The `audience` claim is the cryptographic discriminator between principals. Sharing cookie names also means browser sends both staff and client tokens on every request, creating confusion.
**Instead:** `cc_client_access` + `aud: "client"` claim enforced in `decode_client_access_token`.

### Anti-Pattern 4: Client-portal repository importing other modules' ORM models
**What:** `client_portal/repository.py` imports `from app.modules.memberships.models import Membership`.
**Why bad:** Violates `modules-independent` contract. Requires a new `ignore_imports` edge. The reports module precedent (D-54-08) shows raw SQL `text()` with `.mappings().all()` is sufficient and requires zero ignore edges.
**Instead:** Raw SQL with `:name` bind params + `.mappings()` for all cross-module reads in the repository layer.

### Anti-Pattern 5: Skipping the route introspection test update
**What:** Adding client endpoints without extending TEST-07 to recognize `require_client` as a valid guard.
**Why bad:** TEST-07 asserts that every non-auth route uses `require_permission` or `require_authenticated`. Client routes use `require_client` — a third factory. Without the extension, TEST-07 fails for all client routes (build-breaking).
**Instead:** Extend TEST-07 to include `require_client` as an allowlisted dependency factory: check `__qualname__.startswith('require_client.')` alongside the existing two checks.

### Anti-Pattern 6: Reusing staff idempotency key scope for client requests
**What:** Using the existing `verify_idempotency` dependency (which scopes keys to staff `user_id`) on client endpoints.
**Why bad:** `verify_idempotency` is currently bound to `Depends(get_current_user)` and produces keys scoped to `user_id` (a `users.id`). Client principals have `client_id` (a `clients.id`). Using the staff dependency on a client route would either fail (no `cc_access` cookie) or produce incorrectly scoped idempotency keys.
**Instead:** A new `verify_client_idempotency` dependency (or extend `verify_idempotency` with an optional `principal` parameter) that scopes the Redis key to `client_id`. The key pattern becomes `cc:idem:{client_id}:{method}:{path}:{header}` with the same TTL and pattern validation.

---

## Scalability Considerations

| Concern | Current (1 gym, ~100 clients) | Future (multi-gym) |
|---------|------------------------------|-------------------|
| Client data isolation | `client_id` WHERE clause in every query | Same — no architectural change needed |
| Client session Redis keys | `cc:client:sess:{client_id}:{family_id}` (new namespace, no collision with staff `cc:*` keys) | Same pattern |
| OTP rate limiting | Per-phone counter in Redis (mirrors per-email `cc:rate:login:{email}`) | Same |
| Client checkout concurrency | Idempotency-Key + DB UNIQUE constraints (Phase 66 machinery reused) | Same |
| Ownership sweep test | Parametrized per-resource (N assertions) | Must grow as new resources are added — test-gated |

---

## OpenAPI Contract Preservation

### Staff contract frozen at v1.11.0

The tag `contract-freeze-v1.11.0` anchors the staff paths. After v2.0, the committed `openapi.json` includes both staff (frozen) AND client paths. The CI drift gate detects any drift from the committed baseline across both groups.

Staff operationIds (`login`, `get_client`, `create_membership`, etc.) are unchanged. Client operationIds (`client_login`, `client_get_my_memberships`, etc.) are additive. No collision is possible because of the `client_` prefix convention.

### Staff `AssertNonNever` guards are untouched

`schema.contract.test.ts` contains `_v15Checks` through `_v19Checks` tuples. These are not modified. The new `_v20Checks` tuple (or separate `_v20ClientChecks`) asserts the presence of client operationIds. The `toHaveLength(N)` assertion in the v20 block covers only v20 additions.

### Redocly lint

The new `"Client-Portal"` tag appears in `OPENAPI_TAGS` list between `"Audit-log"` and `"Internal"`. Redocly renders client operations under this heading, separated from staff operations. No changes to `redocly.yaml` rules are needed — client endpoints follow the same structural conventions.

---

## Composition Root Summary (new carve-outs for v2.0)

All new slots follow the established pattern in `app/core/dependencies.py`:

| Slot | Pattern | Wired from | Phase |
|------|---------|-----------|-------|
| `register_client_loader` | Defensive-raise (mirrors `_user_loader` at Phase 5 D-15) | `create_app()` only | 68 |
| `register_client_booking_creator` | Silent-None or Defensive (TBD by planner based on booking service shape) | `create_app()` only | 70 |

The `create_app()` function in `app/main.py` grows by 2-3 registration calls in `create_app()`. These follow the established ordering (import inside `create_app()` body for composition-root carve-out) and documentation pattern (numbered carve-out, cross-reference to Phase/D-* decision).

---

## Sources

All findings from direct code inspection (HIGH confidence):

- `/Users/andre/Workspace/Development/clubcore/apps/backend/app/main.py` — composition root, Protocol slots, `OPENAPI_TAGS`, `PUBLIC_ENDPOINT_OPERATION_IDS`, `CATEGORY_A_OPERATION_IDS`, `_customize_openapi`
- `/Users/andre/Workspace/Development/clubcore/apps/backend/app/core/dependencies.py` — all Protocol slot declarations (`CurrentUser`, `UserLoader`, `ActiveMembership`, `PaymentRecorder`, etc.), `require_permission`, `require_authenticated`, `get_current_user`, `verify_csrf`
- `/Users/andre/Workspace/Development/clubcore/apps/backend/app/core/permissions.py` — `Role`, `Action`, `Resource`, `OWNER_ONLY`, `can()`, parity test contract
- `/Users/andre/Workspace/Development/clubcore/apps/backend/app/core/security.py` — JWT encode/decode, `AccessTokenClaims`, cookie issuance pattern
- `/Users/andre/Workspace/Development/clubcore/apps/backend/app/modules/auth/router.py` — auth endpoint patterns, CSRF exemptions, `require_authenticated` usage, OTP flow
- `/Users/andre/Workspace/Development/clubcore/apps/backend/app/modules/auth/service.py` — `load_user_by_id`, `authenticate`, token rotation, anti-oracle sentinel hash pattern
- `/Users/andre/Workspace/Development/clubcore/apps/backend/app/modules/reports/repository.py` — raw-SQL cross-module read pattern (D-54-08), `text()` discipline, zero `ignore_imports`
- `/Users/andre/Workspace/Development/clubcore/apps/backend/app/api/v1/router.py` — current aggregator router, module mount pattern, `_internal` namespace precedent
- `/Users/andre/Workspace/Development/clubcore/apps/backend/.importlinter` — `modules-independent` contract, `ignore_imports` precedents (all 30+ edges), `unmatched_ignore_imports_alerting`
- `/Users/andre/Workspace/Development/clubcore/packages/api-client/src/fetcher.ts` — CSRF cookie reading (`clubcore_csrf`), single-flight refresh, `AUTH_EXEMPT_PATHS`, D-A1..D-A4 contracts
- `/Users/andre/Workspace/Development/clubcore/.planning/PROJECT.md` — v2.0 milestone scope, target features, key constraints, out-of-scope list
