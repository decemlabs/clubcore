# Pitfalls Research: v2.0 Frontend Integration — Client PWA

**Domain:** Adding a client-facing portal + PWA to a mature, staff-only FastAPI gym CRM (RF/CIS)
**Researched:** 2026-05-29
**Confidence:** HIGH — based on direct codebase inspection (auth/service.py, visits/service.py, online_payments/service.py, core/permissions.py, core/security.py, core/dependencies.py, core/idempotency.py, apps/client-pwa/package.json)

---

## Critical Pitfalls

### Pitfall P-01: Cross-Client Data Leakage (IDOR) — Missing `client_id` Ownership Filter

**What goes wrong:**
A client-scoped endpoint (e.g., `GET /api/client/v1/memberships`) fetches data by ID without verifying that the authenticated client owns that record. A client who knows or guesses another client's membership UUID can retrieve it. This is the single most dangerous class of bug in this milestone because the existing staff endpoints have NO ownership filter — they are designed for staff who see all data. When a new client endpoint reuses a staff repository method, the ownership filter is trivially omitted.

Concrete example: `GET /api/client/v1/bookings/{booking_id}` calls `repository.get(session, booking_id)` — the staff version of this function — without adding `WHERE client_id = :authenticated_client_id`. An attacker iterates UUIDs and reads other clients' bookings, PT session logs, payment history.

**Why it happens:**
The existing repository layer (`visits/repository.py`, `memberships/repository.py`, etc.) is built for staff who see all records. The developer adds a thin wrapper for the client endpoint and calls the same repository function. The `client_id` filter is the only thing that makes the query client-scoped, and it is not enforced at the repository or model level — it must be threaded explicitly through every query. One missed filter = one IDOR.

**How to avoid:**
1. **Dedicated client-scoped repository layer**: Create `app/modules/{domain}/client_repository.py` that wraps every SELECT with an explicit `WHERE client_id = :client_id` clause. Never call staff repository functions from client endpoints.
2. **`ClientPrincipal` dependency that carries `client_id`**: Analogous to `CurrentUser` for staff, a `ClientPrincipal` Protocol carries the resolved `client_id` and is injected into every client endpoint via `Depends(require_client_auth())`. Every route handler receives `client: ClientPrincipal` — making it impossible to forget the ownership context.
3. **Parametrized IDOR enumeration test suite**: In the same phase that ships each client endpoint domain, add a test: authenticate as client_A, try to fetch client_B's resource ID, assert 404 (not 403 — anti-oracle collapse, same as existing staff patterns). Run for every `GET /{resource}/{id}` and every `POST /{resource}/{id}/action` in the client API.

**Warning signs:**
- A client repository function that does not take `client_id: UUID` as a parameter
- A client endpoint that calls a staff repository function (e.g., `repository.get(session, booking_id)`) without an ownership predicate
- Any test file that covers the client endpoint but does not have a "cross-client access → 404" test case

**Phase to address:** Phase 68 (Client Auth Foundation) — establish the `ClientPrincipal` dependency and ownership-test pattern before any domain endpoint is wired. Every subsequent domain phase (visits, bookings, memberships, payments) must include the IDOR enumeration test as a mandatory success criterion.

---

### Pitfall P-02: Phone/OTP Enumeration Oracle — Anti-Oracle Parity Not Mirrored for Client Principal

**What goes wrong:**
`POST /api/client/v1/auth/otp/request` (phone OTP for client login) leaks whether a phone number is a registered member. The naive implementation checks `SELECT * FROM clients WHERE phone = :phone`, finds no row, and returns a 404 or a different response body or response timing than the "phone found" path. An attacker sends a list of phone numbers and classifies each as "member" or "non-member" by comparing response time or body.

This is the same class of oracle the existing staff auth defends against — `authenticate()` runs `_get_sentinel_hash()` to make the "email not found" path take exactly as long as the "found, wrong password" path, and `request_otp_email()` uses `_constant_time_floor()` to make unknown-email and known-unverified-email branches indistinguishable. The client phone OTP flow must mirror this discipline exactly.

Additional sub-cases:
- A soft-deleted client (`deleted_at IS NOT NULL`) must be treated identically to "phone not found" — same response shape, same timing.
- A client with `phone IS NULL` (some clients were added without phone, only email or manually) must also fold into the silent-drop bucket.
- A client with duplicate phone (partial UNIQUE `(phone) WHERE deleted_at IS NULL` exists in the clients table from v1.1) — the live duplicate should not surface as a 500 error that reveals DB state.

**Why it happens:**
Phone OTP is a new flow with no existing pattern to copy for clients. The developer implements the OTP request, successfully sends the SMS, and writes a test for the happy path. The "phone not found" path raises an HTTP 404 with `{"code": "phone_not_found"}` because it seems user-friendly. No one adds the anti-oracle test until security review, if ever.

**How to avoid:**
1. Copy the `_constant_time_floor()` try/finally wrapper from `auth/service.py:request_otp_email()` verbatim for `request_client_otp_phone()`. Measure the populated-branch median and set the floor at that value.
2. The "phone not found" branch, "soft-deleted client" branch, and "no-phone client" branch ALL return `200 OK` with `{"data": null}` — identical body and headers to the "OTP sent" branch.
3. Write an anti-oracle integration test (analogous to plan 42-11): submit an OTP request for a known phone and an unknown phone; assert response bodies are byte-identical; assert wall-clock difference is within 100ms tolerance.

**Warning signs:**
- `POST /api/client/v1/auth/otp/request` returns 4xx for any phone input (it must always return 200)
- No `await asyncio.sleep(remaining_ms / 1000)` or equivalent timing floor in the client OTP handler
- Response body for "phone not found" contains `code` or `message` that differs from "OTP sent"

**Phase to address:** Phase 68 (Client Auth Foundation) — anti-oracle must be built in from the start, not retrofitted. Gate the phase with the timing-equivalence integration test.

---

### Pitfall P-03: Privilege Boundary Collapse — Client Token Accepted by Staff Endpoints or Vice Versa

**What goes wrong:**
The client principal (phone-OTP login) and the staff principal (email/password or Telegram-OTP login) share the same `cc_access` JWT cookie namespace and potentially the same `decode_access_token()` path. If the client JWT encodes `role: "client"` (a new Role enum value) but `get_current_user()` in `app/core/dependencies.py` is extended naively, two failure modes emerge:

1. **Client token accepted by staff endpoints**: `require_permission(Action.LIST, Resource.CLIENTS)` calls `can(user.role, action, resource)`. If `role = "client"` falls through the `OWNER_ONLY` check (which only checks owner vs. non-owner) and is not explicitly rejected, a client JWT can reach staff endpoints and return data for all clients, not just their own.

2. **Staff token accepted by client endpoints**: A staff `require_client_auth()` dependency that only checks "is authenticated" (not "is a client principal") accepts a staff JWT. A staff member (or a compromised staff account) can use the client endpoints to reach data via the client-scoped repository layer — which may have fewer rate-limit or RBAC guardrails.

**Why it happens:**
The existing `Role` enum has exactly two values: `OWNER` and `RECEPTION`. The `can()` function short-circuits to `True` for owners. Adding `Role.CLIENT = "client"` to the StrEnum without also modifying `can()`, `require_permission()`, and `get_current_user()` to reject client tokens on staff paths leaves a hole. The route-introspection test (`tests/integration/test_route_introspection.py`) only covers staff routes — it will not catch the new client routes if they are not added to the introspection fixture.

**How to avoid:**
1. **Do NOT add `Role.CLIENT` to the shared `app/core/permissions.py` StrEnum** — this would require the frontend `can.ts` parity test to add a client role, breaking the byte-parity invariant. Instead, use a separate `ClientPrincipal` Protocol that carries `client_id: UUID` without a `Role` field.
2. Implement two entirely separate dependency trees: `get_current_user()` (staff, reads `cc_access` JWT with `role in {owner, reception}`) and `get_current_client()` (client, reads a different cookie e.g. `cc_client_access` with a `principal: "client"` claim in the JWT body). The token shape difference at the JWT level means the two dependency trees reject each other's tokens at the `decode_access_token()` call.
3. Add an invariant to the route-introspection test: every route under `/api/client/v1/*` must declare `Depends(require_client_auth())` (analogous to `require_permission`). Every route under `/api/v1/*` must reject client tokens (assert 401 when presented with a client JWT).
4. Add an integration test: mint a client token, present it to `GET /api/v1/clients`, assert 401.

**Warning signs:**
- `role: "client"` added to `app/core/permissions.py`
- `require_permission()` extended to handle client tokens rather than a separate `require_client_auth()` dependency
- Route-introspection test coverage does not include `/api/client/v1/*` routes
- No integration test asserting staff endpoints reject client tokens

**Phase to address:** Phase 68 (Client Auth Foundation) — the two-principal architecture must be settled in the auth phase before any domain endpoint is added.

---

### Pitfall P-04: OTP Bombing and SMS Cost — No Rate Limit on Phone OTP Request

**What goes wrong:**
`POST /api/client/v1/auth/otp/request` triggers an SMS (via the RF/CIS SMS gateway, which is a paid service — roughly 2–5 RUB per SMS). Without a rate limit, an attacker sends 10,000 requests for a single phone number, costing 20,000–50,000 RUB. Even without malice, a client who taps "Resend OTP" rapidly 20 times triggers 20 SMS charges.

The existing email OTP has a **60-second row-level cooldown** (`cooldown_row.created_at > now - timedelta(seconds=60)`) and a pending Redis rate limit for IP/email (documented as "wired in a downstream Wave-3 follow-up" in `service.py:request_otp_email()`). Phone SMS OTP has no analogous protection in the existing codebase.

Additional risk: **OTP brute-force**. A 6-digit OTP has 10^6 combinations. The existing `consume()` function in `telegram_service.py` increments `otp_row.attempts` and raises `OtpMaxAttempts` after `settings.otp_max_attempts` misses, committing the counter before raising. This pattern must be mirrored exactly for phone OTP — including the "commit before raise" discipline so the counter cannot be rewound by a client dropping the connection.

**Why it happens:**
Phone SMS OTP is a new channel not in the existing codebase. The developer copies the Telegram OTP structure (which has no SMS cost pressure) and does not add the per-phone cooldown. The anti-oracle requirement makes the "phone not found" path identical to "OTP sent," so a naive rate-limit that returns 429 only for known phones would itself be an oracle leak.

**How to avoid:**
1. **Per-phone 60-second row-level cooldown**: Mirror `request_otp_email()`'s cooldown check — if an alive `otp_codes` row for this phone exists with `created_at > now - 60s`, silently drop (return 200 `data: null` without sending SMS).
2. **Per-IP rate limit on `/api/client/v1/auth/otp/request`**: 5 requests per 15 minutes per IP, checked BEFORE the phone lookup (same pattern as `check_login_rate()` in `auth/rate_limit.py`). The 429 response for IP-rate-limiting is NOT an oracle for phone existence (the limit applies equally regardless of whether the phone is registered).
3. **Per-phone daily cap**: Additional Redis counter `ratelimit:sms:{phone_e164}` max 10 per day. Reset at Europe/Moscow midnight.
4. **OTP max attempts with commit-before-raise**: Copy `telegram_service.py:consume()` pattern — `otp_row.attempts += 1; await session.commit(); if otp_row.attempts >= max: raise OtpMaxAttempts`. The commit-before-raise ensures the counter persists even if the client drops the TCP connection mid-response.
5. **OTP code TTL**: 5–10 minutes (not 24 hours). Short TTL limits the window for brute-force even if max_attempts is generous.

**Warning signs:**
- No Redis rate-limit key for phone OTP requests
- No 60-second row-level cooldown for phone OTP
- OTP attempts counter incremented and saved AFTER raise (rewindable by connection drop)
- OTP TTL > 15 minutes in settings

**Phase to address:** Phase 68 (Client Auth Foundation) — rate limits and attempt caps are security primitives that must ship with the OTP endpoint, not be added later.

---

### Pitfall P-05: Self-Checkout Integrity — Activating Membership on Redirect Instead of Webhook

**What goes wrong:**
A client initiates a ЮKassa payment for a membership from the PWA. ЮKassa redirects back to the `return_url` after the user completes payment. The naive implementation checks the payment status on the redirect-back and activates the membership if the status is `"succeeded"`. This is wrong for two reasons:

1. **Race condition**: The redirect-back fires before the ЮKassa webhook in some configurations. The payment status on redirect may still be `"waiting_for_capture"` — the membership is not activated, the client sees an error, they retry, the second redirect hits `"succeeded"`, now the membership IS activated — but the first attempt may have already created a duplicate payment row.
2. **Client-side manipulation**: The `return_url` receives `paymentId` as a query parameter. If the client endpoint reads `?paymentId=...` and fetches status from ЮKassa, an attacker can forge a `paymentId` for someone else's payment, activating THEIR membership under the attacker's account.

The existing staff checkout flow (online_payments service) explicitly locks activation to the webhook: the return screen shows "Ожидаем подтверждение от платёжной системы" (anti-oracle constant `_RETURN_HTML`), and the webhook handler does the DB activation in an 8-step atomic UoW. The client checkout MUST use the exact same pattern.

**Why it happens:**
The PWA screens have a Checkout flow that currently redirects to a success screen. The developer adds a "confirm checkout" step that polls the API after redirect. Polling is fine for showing current status; activation on polling is the mistake.

**How to avoid:**
1. **Reuse the existing online_payments webhook handler** — do not create a second webhook endpoint for client-initiated payments. The existing `/_internal/yookassa/webhook` handles `payment.succeeded` for any `online_payment` row regardless of whether it was initiated by staff or client.
2. **Client-scoped `POST /api/client/v1/checkout` endpoint** creates an `online_payments` row and returns the ЮKassa `confirmation_url`. The client PWA redirects the user to ЮKassa. On return, the PWA shows the "awaiting confirmation" screen (same copy as `_RETURN_HTML`). The membership activates ONLY when the webhook fires.
3. **Price must be server-side**: The client sends `{plan_id, confirmation_type}`. The server reads the plan price from the DB (same `_read_membership_plan_or_raise()` pattern in `online_payments/service.py`). The client NEVER sends `amount` — it has no authority over price.
4. **Mandatory email gate**: `_read_client_email_or_raise()` (existing pattern in `online_payments/service.py`) — 422 `client_email_required_for_online_payment` if the client has no email. For client-initiated checkout, the PWA must collect email at checkout time and PATCH the client record before calling checkout. The fiscal receipt requirement (54-ФЗ) is mandatory.

**Warning signs:**
- Any client endpoint that reads `?paymentId` from the redirect URL and activates a membership
- A `POST /api/client/v1/checkout/confirm` endpoint that calls `activate_membership()` directly
- Client checkout endpoint that accepts `amount` in the request body
- A second `yookassa/webhook` endpoint for client payments

**Phase to address:** Phase N (Client Checkout, likely Phase 70+) — the phase plan must explicitly prohibit redirect-based activation and require the existing webhook handler to cover client-initiated payments.

---

### Pitfall P-06: Self Check-In Abuse — QR Replay, Cross-Client Check-In, No Membership Guard

**What goes wrong:**
The QR check-in screen (`apps/client-pwa/src/screens/sheets/QRSheet.jsx`) generates a QR code that the client presents at the gym entrance. The backend `POST /api/client/v1/visits/qr-checkin` processes it. Three attack vectors:

1. **QR replay**: The QR payload is static (client_id encoded in a QR image). An attacker photographs the QR, uses it hours later to check in again (bypassing the 1/day limit if the gym_date changes at midnight Moscow time).
2. **Cross-client check-in**: If the QR payload is simply `{client_id: "..."}` with no time-bound signature, someone can forge a QR for another client's ID.
3. **Checking in without active membership**: The client-initiated check-in endpoint must run the same anti-fraud chain as `_create_visit_with_anti_fraud()` — gym_hours check → active_membership resolver → DB UNIQUE constraint. If the developer creates a simplified "self-checkin" endpoint that skips the active membership check ("clients can see the QR only if they have a membership, so no need to check again"), a client with an expired membership can check in until the QR is revoked.

The existing bot self-checkin (`create_visit_self_checkin()`) calls `_create_visit_with_anti_fraud()` which enforces all three guards. The client QR endpoint must do the same.

**How to avoid:**
1. **Time-bound signed QR tokens**: The QR payload is a short-lived signed JWT (`{sub: client_id, exp: now + 60s, iat: now}`) signed with a server-side secret. The backend verifies the signature AND the expiry. Static QR images are useless after 60 seconds. Refresh the QR token in the PWA every 45 seconds via a `GET /api/client/v1/visits/qr-token` endpoint (which requires the `cc_client_access` cookie — only the authenticated client can generate their own token).
2. **Anti-fraud chain mandatory**: The QR check-in endpoint calls the existing `_create_visit_with_anti_fraud()` helper (or an equivalent that extracts `client_id` from the QR JWT), which enforces gym_hours + active_membership + DB UNIQUE constraint. Never skip any step.
3. **No `client_id` in plain QR**: The QR payload is the signed JWT, not a raw UUID. An attacker who photographs the QR gets an expired token after 60 seconds.
4. **DB UNIQUE constraint is the final arbiter**: `UNIQUE (client_id, gym_date)` on the `visits` table (already exists, Alembic 0006) prevents duplicate check-ins regardless of race conditions or client bugs.

**Warning signs:**
- QR payload contains a raw `client_id` UUID without a signature
- QR tokens with TTL > 5 minutes
- Client check-in endpoint that does not call `_create_visit_with_anti_fraud()` or an equivalent
- No active membership check before inserting a visit row
- No test for "expired QR token → 401"

**Phase to address:** Phase N (Client Visits + QR, likely Phase 69+) — the signed-QR architecture must be decided in the phase design, not added later as a patch.

---

### Pitfall P-07: Staff OpenAPI Contract Broken by Client Path Addition

**What goes wrong:**
The v1.11 milestone froze the staff OpenAPI contract at `apps/backend/openapi.json` with the baseline tag `contract-freeze-v1.11.0`. The v2.0 milestone adds client paths under `/api/client/v1/*`. If these paths are mounted on the same FastAPI app without care, the export script regenerates `openapi.json` with BOTH staff and client paths — changing the document the drift gate guards. Downstream effects:

1. **`schema.d.ts` drift**: `pnpm --filter @clubcore/api-client codegen` regenerates TypeScript types from the new spec, adding client types and potentially renaming existing staff types if client paths reuse the same operation ID prefixes.
2. **`AssertNonNever` forward-guard count**: The existing `_v19Checks.toHaveLength(N)` assertions in `schema.contract.test.ts` will fail if the spec adds new paths that the test does not account for — or if client paths accidentally shadow existing staff paths and the count changes.
3. **Redocly lint**: Client paths that lack `summary`, `tags`, or `operationId` will fail the 7th CI gate.
4. **`operationId` collisions**: If a client endpoint for `GET /api/client/v1/visits` is auto-named `list_visits_api_client_v1_visits_get` and a staff endpoint `GET /api/v1/visits` is auto-named `list_visits_api_v1_visits_get`, the `generate_unique_id_function` suffix-stripping may produce two operations both named `list_visits`, causing a spec validation error.

**How to avoid:**
1. **Separate OpenAPI export for client paths**: Consider mounting client routes on a sub-app (`FastAPI()` instance) that exports its own `client-openapi.json`. The staff contract remains frozen and is not regenerated when client paths change. Only the client-specific artifact tracks client path evolution.
2. **Alternative**: Keep one app but add client paths to the `AssertNonNever` guards and update the `_v20Checks` count as a new check tuple (analogous to `_v19Checks`, `_v18Checks`). This preserves the single-spec discipline but requires the counter to be updated each time client paths are added.
3. **Distinct operation ID prefix**: Name all client operations with a `client_` prefix (enforced via `generate_unique_id_function` for the client sub-router). This avoids shadowing staff operation IDs.
4. **Redocly lint must remain green**: Add all client tags, summaries, and operationIds in the same phase plan that adds the routes. Never add routes without passing Redocly lint.

**Warning signs:**
- `git diff apps/backend/openapi.json` shows staff path changes after adding client routes
- `_v19Checks.toHaveLength(N)` assertion fails after client routes are added
- Two operation IDs with the same base name (after suffix stripping) in the same OpenAPI document
- `pnpm --filter @clubcore/api-client codegen` produces a `schema.d.ts` diff that includes changes to existing staff type signatures

**Phase to address:** Phase 68 (Client Auth Foundation) — decide the single-spec vs. split-spec architecture before the first client route is added. The choice affects every subsequent phase's CI gate. Implement the contract-preservation test (`_v20Checks` or split-spec) in Phase 68 so later phases can add routes safely.

---

### Pitfall P-08: CSRF/Cookie Collision Between Staff and Client Sessions

**What goes wrong:**
The existing staff session uses three cookies: `cc_access` (Path=/), `cc_refresh` (Path=/api/v1/auth), `clubcore_csrf` (Path=/, readable). If the client session uses the SAME cookie names, a browser that has both a staff tab and a client tab open on the same origin will have cookie collisions:

1. The client logs in, overwrites `cc_access` with a client JWT. The staff tab's subsequent requests carry the client JWT, get 401 (`invalid_token` or `invalid_role`) from staff endpoints.
2. The staff logs in, overwrites `cc_access` with a staff JWT. The client tab's subsequent requests carry the staff JWT, get 401 from client endpoints.
3. `clubcore_csrf` collision: the client session's CSRF token overwrites the staff session's CSRF token, causing CSRF verification failures on staff mutations.

This is not hypothetical — a gym owner who uses both the admin panel and the client PWA on the same browser on the same origin (e.g., both served from `api.gym.ru`) will hit this collision.

**Why it happens:**
The `issue_session_cookies()` function in `app/core/security.py` hardcodes the cookie names. Copying the function for the client auth flow without changing the names causes the collision.

**How to avoid:**
1. **Different cookie names for client session**: `cc_client_access` (Path=/api/client), `cc_client_refresh` (Path=/api/client/v1/auth), `clubcore_client_csrf` (Path=/api/client, readable). The different `Path` attribute means the cookies are sent only to their respective API paths, preventing cross-contamination.
2. **Separate cookie-set/clear functions**: `issue_client_session_cookies()` and `clear_client_session_cookies()` — mirror of `issue_session_cookies()` / `clear_session_cookies()` but with the client names and paths.
3. **Separate Redis session namespace**: Staff sessions use `auth:session:{user_id}:{family_id}`. Client sessions use `auth:client:{client_id}:{family_id}`. No key collision in Redis.
4. **Separate refresh endpoint**: `POST /api/client/v1/auth/refresh` reads `cc_client_refresh`, not `cc_refresh`. The staff refresh endpoint (`POST /api/v1/auth/refresh`) reads `cc_refresh`. The narrow `Path` attribute on each cookie ensures they are sent only to their respective endpoints.

**Warning signs:**
- Client auth issues `cc_access` cookie (same name as staff)
- `issue_session_cookies()` is called from a client auth route handler
- No `Path=/api/client` restriction on client session cookies
- Redis session key pattern shared between staff and client sessions

**Phase to address:** Phase 68 (Client Auth Foundation) — the cookie architecture is the foundation. Wrong cookie names here cascade into every phase that adds client endpoints.

---

### Pitfall P-09: PWA Service-Worker Caching Authenticated Responses

**What goes wrong:**
The client PWA is built with Vite. If a Vite PWA plugin (e.g., `vite-plugin-pwa` / Workbox) is added for offline support and is misconfigured, the service worker caches API responses including those carrying membership data, payment history, and visit logs. Two failure modes:

1. **Stale authenticated data**: A client logs out. Another client (or the same client on a different account) logs in on the same device. The service worker serves the previous client's membership response from the cache. The new client sees the old client's data.
2. **Credential-bearing responses cached**: The service worker caches a `200 OK` response to `GET /api/client/v1/me`. The response body contains the client's full name and membership status. A subsequent visit without a valid session token serves the cached response as if authenticated — bypassing the auth dependency entirely at the fetch layer.

The existing admin-web has NO service worker (it is a React SPA without PWA features). This pitfall is entirely new to the client-pwa.

**How to avoid:**
1. **Never cache authenticated API responses in the service worker**: Configure Workbox `NetworkOnly` strategy for all `/api/*` routes. Only static assets (JS/CSS/images) and app-shell HTML are cached.
2. **Cache-Control headers on all client API responses**: Add `Cache-Control: no-store, no-cache, must-revalidate` to all `/api/client/v1/*` responses. This prevents the browser's HTTP cache AND the service worker cache from storing authenticated responses.
3. **Service worker must not intercept `/api/client/*`**: In the Workbox config, explicitly exclude the API origin/path from service worker routing. If the API is on the same origin, use `registerRoute` with a negative matcher.
4. **On logout, clear service worker cache**: In the logout flow, call `caches.delete()` for any named cache that might contain API responses. At minimum, post a message to the service worker to clear all non-static caches.

If the milestone defers full PWA (offline support), skip the service worker entirely in v2.0 — serve the client app without a service worker and add it in v2.1 when the caching strategy has been reviewed.

**Warning signs:**
- `vite-plugin-pwa` added without an explicit `urlPattern` exclusion for `/api/*`
- No `Cache-Control: no-store` headers on client API endpoints
- Service worker registered before a caching-strategy document is written
- No logout test that verifies cached data is cleared on session end

**Phase to address:** Phase N (PWA Integration) — if PWA service worker is in scope, the caching strategy must be the first thing designed in that phase. If it is out of scope (offline not required in v2.0), explicitly note "no service worker" in the phase plan and defer it.

---

### Pitfall P-10: bun → pnpm Migration Breakage in client-pwa

**What goes wrong:**
`apps/client-pwa` currently has a `bun.lock` file and `"name": "gym-app"` in `package.json`. It is NOT yet a pnpm workspace member (no `@clubcore/client-pwa` package name, no entry in root `pnpm-workspace.yaml`). The milestone plan says "выравнивание стека (pnpm + TS + api-client + общий lint/CI)" without migrating the router. Three failure modes during migration:

1. **`bun.lock` + `pnpm-lock.yaml` coexistence**: If `pnpm install` is run in the workspace root without removing `bun.lock` first, pnpm reads its own lockfile. But if any CI step or developer runs `bun install` in `apps/client-pwa`, it regenerates `bun.lock` with different dependency versions, diverging from the pnpm workspace.
2. **Vite 5.4.8 in client-pwa vs. Vite 6.0.7 in admin-web**: Two Vite versions in the same pnpm workspace. pnpm hoists one version (determined by `pnpm-lock.yaml`). The older `@vitejs/plugin-react@4.3.1` (client-pwa) may be incompatible with the hoisted Vite 6. This breaks the client-pwa dev server without obvious error messages.
3. **JS → TS adoption**: The PWA is entirely `.jsx` (no TypeScript). The milestone says TS adoption is part of alignment. Adding `tsconfig.json` and renaming files to `.tsx` in the same phase that wires the real backend API creates a noisy, hard-to-bisect diff. If a type error is introduced alongside a runtime bug, the combined diff makes diagnosis difficult.

**How to avoid:**
1. **Delete `bun.lock` on day one of the migration phase** and add `bun.lock` to `.gitignore`. Run `pnpm install` from the workspace root to generate the canonical `pnpm-lock.yaml` entry. Verify `apps/client-pwa` builds correctly with pnpm before touching any other file.
2. **Align Vite versions**: Pin `apps/client-pwa` to Vite 6 (update `package.json` devDependency) in the same commit that adds the pnpm workspace entry. Document the reason in the commit message.
3. **Two-phase JS → TS migration**: Phase 1 (same migration phase) — add `tsconfig.json` + rename files to `.tsx` + fix type errors, commit. Phase 2 (next feature phase) — add the actual API integration. Never mix renaming with logic changes.
4. **Workspace name**: Rename `"name": "gym-app"` → `"name": "@clubcore/client-pwa"` in `package.json` as part of the migration.

**Warning signs:**
- `bun.lock` still present in `apps/client-pwa` after pnpm workspace migration
- `pnpm ls` in workspace root shows `apps/client-pwa` with a different Vite version than `apps/admin-web`
- A phase plan that combines "migrate to pnpm + TS + wire real API" into a single step

**Phase to address:** Phase 68 (or whichever phase is "PWA Stack Alignment") — migration must be its own isolated phase with a green build verification before domain wiring begins.

---

### Pitfall P-11: react-router v6 CSRF Header Not Sent on Mutations from PWA Fetcher

**What goes wrong:**
The existing staff admin-web (TanStack Router + TanStack Query) manages CSRF via a pattern where the `X-CSRF-Token` header is read from the `clubcore_csrf` cookie and sent on every non-GET request. The client PWA uses react-router v6's `useFetcher` and `fetch()` directly. The `clubcore_client_csrf` cookie (readable, not httpOnly) must be extracted and included in every `POST`/`PATCH`/`DELETE` request. Failure to include it causes `CsrfMismatch` (422) on every mutation.

Edge cases:
1. **After page refresh**: The `clubcore_client_csrf` cookie may not yet be available in `document.cookie` before the first `fetch()` if the cookie is set on login and the page was refreshed. The CSRF token must be re-read on every request, not cached in a React state variable (which is wiped on refresh).
2. **After token refresh**: When `cc_client_access` expires and a silent refresh is performed, the new `cc_client_access` comes with the same `clubcore_client_csrf` cookie. If the CSRF token value changes on refresh (the server generates a new CSRF token on each login, not on each access token refresh — check the existing `generate_csrf_token()` call in `issue_tokens()`), the PWA must update its CSRF token reading logic.
3. **No CSRF on the webhook endpoint**: `/_internal/yookassa/webhook` has no `Depends(verify_csrf)` — this is correct and must NOT be changed. But the client checkout endpoint (`POST /api/client/v1/checkout`) IS a browser-initiated mutation and MUST include CSRF.

**How to avoid:**
1. Create a `getClientCsrfToken()` utility in the PWA that reads `document.cookie` for `clubcore_client_csrf` on every call (not cached).
2. Create a `clientFetch(url, options)` wrapper that always includes `X-CSRF-Token: getClientCsrfToken()` for non-GET methods and `credentials: "include"` for all methods.
3. Add an integration test: make a `POST` without the `X-CSRF-Token` header, assert 422 `csrf_mismatch`. Make the same `POST` with the correct token, assert 2xx.

**Warning signs:**
- PWA fetch calls using bare `fetch()` without the CSRF header on mutations
- CSRF token stored in React state (wiped on refresh) instead of read from cookie on each request
- No test for CSRF rejection

**Phase to address:** Phase 68 (Client Auth Foundation) — the `clientFetch` utility must be available before any domain mutation is wired in subsequent phases.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|---|---|---|---|
| Call staff repository functions from client endpoints (no `WHERE client_id = :id`) | Faster implementation | IDOR — cross-client data leakage; requires a full endpoint audit and new test suite to remediate | Never |
| Add `Role.CLIENT` to shared `app/core/permissions.py` | Reuse existing RBAC machinery | Breaks staff byte-parity test with admin-web `can.ts`; requires frontend Role type to be updated; staff RBAC now needs to explicitly reject `CLIENT` role | Never |
| Static QR code (permanent `client_id` in QR payload) | Simpler QR generation, works offline | QR replay after gym_date changes; cross-client check-in by photographing QR; cannot be invalidated on logout | Never |
| Activate membership on ЮKassa redirect-back (not webhook) | Faster UX (no polling delay) | Race condition; redirect may fire before `payment.succeeded` webhook; double-activation risk | Never |
| Serve both staff and client OpenAPI spec in one document without operation ID namespacing | One drift gate, simpler CI | Operation ID collisions; `schema.d.ts` mixes staff and client types; frozen staff contract breaks when client paths are added | Never |
| Skip JS → TS migration, keep client-pwa in plain JS | Zero migration effort | No TypeScript coverage; `@clubcore/api-client` schema.d.ts types cannot be consumed without TS; import-linter cannot enforce boundaries in JS files | Never — TS adoption is non-negotiable for workspace coherence |
| Use same cookie names for client and staff sessions | Reuse `issue_session_cookies()` without changes | Cookie collision when both staff and client tabs open on same origin | Never |
| Cache API responses in service worker without explicit exclusion | Works offline for some screens | Stale authenticated data served after logout; previous client's data shown to new client on shared device | Never for authenticated resources |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|---|---|---|
| ЮKassa client checkout | Creating a second webhook endpoint for client-initiated payments | Reuse the existing `/_internal/yookassa/webhook` handler — it processes `payment.succeeded` for any `online_payment` row; client-initiated payments write the same `online_payments` table row |
| ЮKassa 54-ФЗ client email gate | Letting the client provide their email at checkout time without persisting it | The `client_email_required_for_online_payment` gate checks `clients.email` in the DB; the PWA must collect email and PATCH the client record BEFORE calling checkout, not pass it as a checkout parameter |
| Phone OTP + Telegram OTP coexistence | Assuming `otp_codes` table rows for phone and Telegram channels can share the same partial UNIQUE constraint | The existing partial UNIQUE `uq_otp_codes_user_channel_active` is `(user_id, channel) WHERE consumed_at IS NULL`; for clients there is no `user_id` — the OTP row must be keyed by `client_id`, requiring either a schema change or a separate `client_otp_codes` table |
| pnpm workspace + client-pwa | Running `npm install` or `bun install` inside `apps/client-pwa` after workspace migration | Always use `pnpm install` from the workspace root; add `.npmrc` `prefer-workspace-packages=true`; CI must run `pnpm install --frozen-lockfile` |
| `@clubcore/api-client` in client-pwa | Importing staff endpoint types for client screens | Client endpoints have different response shapes (client-scoped, no staff audit fields); generate separate client-facing types or add client paths to `schema.d.ts` explicitly rather than reusing staff types |
| React 18 (client-pwa) vs. React 19 (admin-web) in pnpm workspace | pnpm hoist resolves to one React version | Use `pnpm.overrides` in root `package.json` to pin React 18 for client-pwa and React 19 for admin-web, or isolate via `public-hoist-pattern` per workspace; do not let pnpm silently pick a version |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|---|---|---|---|
| QR token endpoint called on every screen render | `GET /api/client/v1/visits/qr-token` hit 60x per minute per active client; Redis/DB load on idle clients | Generate QR token only when QR sheet is open; auto-refresh every 45s only while sheet is visible | At 100+ concurrent clients with QR sheets open |
| Client membership resolver without index | `SELECT * FROM memberships WHERE client_id = :id AND status = 'active'` does a full table scan if no index | The existing `(client_id, status, end_date DESC)` index on `memberships` already covers this; verify the client query uses it (`EXPLAIN ANALYZE`) | At 1000+ membership rows |
| Polling ЮKassa payment status from client PWA after checkout | `GET /api/client/v1/payments/{id}/status` polled every 2 seconds × many clients; ЮKassa API rate-limited; each poll is a `GET /v3/payments/{id}` to ЮKassa | Show "awaiting confirmation" screen with one `GET` on page load; no continuous polling; redirect to "confirmed" screen only when the membership endpoint shows an active membership | At 10+ concurrent checkout flows |
| Loading all client visit history in one request | `GET /api/client/v1/visits?page_size=1000` on a client with 3 years of history | Enforce max `page_size=50` on client visit history; server-side pagination required (per-project convention: `{items, total, page, pageSize}`) | At 500+ visits per client |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---|---|---|
| Missing `client_id` filter on any client endpoint | IDOR — cross-client data leakage | Dedicated client repository layer with `client_id` as mandatory parameter; IDOR enumeration test for every endpoint |
| Static QR payload (plain `client_id`) | QR replay; cross-client check-in by photo | Time-bound signed JWT in QR payload (60s TTL, server-side secret) |
| Client token accepted by staff endpoints | Client accesses all-clients data; privilege escalation | Separate JWT `principal: "client"` claim rejected by `get_current_user()`; integration test: client token → staff endpoint → 401 |
| Membership activated on redirect-back | Double-activation race; manipulation via forged `paymentId` | Activation LOCKED to webhook handler; redirect shows "awaiting confirmation" only |
| No CSRF on client checkout endpoint | CSRF attack can submit payment on behalf of authenticated client | `Depends(verify_csrf)` on all client mutations; `clubcore_client_csrf` cookie + `X-CSRF-Token` header |
| SMS OTP with no rate limit | SMS bombing — 20,000+ RUB cost from one IP; OTP brute-force | Per-IP 5/15min limit + per-phone daily cap + 60s row-level cooldown + max attempts with commit-before-raise |
| Service worker caching authenticated responses | Stale data shown after logout; previous client's data on shared device | `NetworkOnly` strategy for all `/api/*` in Workbox; `Cache-Control: no-store` on all client API responses |
| Client refresh token in same cookie as staff refresh | Session collision on shared-origin browser | Separate `cc_client_refresh` cookie with `Path=/api/client/v1/auth` |

---

## "Looks Done But Isn't" Checklist

- [ ] **IDOR guard**: Every client endpoint has a test asserting that client_A cannot access client_B's resource — not just "authenticated → 200"
- [ ] **Anti-oracle phone OTP**: `POST /api/client/v1/auth/otp/request` with unknown phone returns 200 with `{"data": null}` — not 404 or different body — AND wall-clock is within 100ms of the known-phone path
- [ ] **Privilege boundary**: A client JWT presented to `GET /api/v1/clients` returns 401 — not 200 or 403; a staff JWT presented to `GET /api/client/v1/me` returns 401
- [ ] **Staff contract preserved**: `git diff apps/backend/openapi.json` shows ONLY additions of `/api/client/v1/*` paths — no changes to existing staff paths, schemas, or operationIds
- [ ] **Cookie isolation**: `cc_access` cookie is NOT set on client login — only `cc_client_access`, `cc_client_refresh`, `clubcore_client_csrf` are set; verified with `document.cookie` inspection in browser
- [ ] **Webhook-only activation**: No `activate_membership()` or equivalent call in any code path triggered by the ЮKassa redirect URL; only the webhook handler activates
- [ ] **QR TTL**: QR token endpoint returns a JWT with `exp = now + 60s`; presenting an expired QR to the check-in endpoint returns 401
- [ ] **Active membership check on QR check-in**: A client with expired membership gets 409 `no_active_membership` from the QR check-in endpoint — not 200 or 201
- [ ] **SMS rate limit active**: `redis-cli KEYS "ratelimit:sms:*"` shows a key after the 5th OTP request from the same IP; the 6th request returns 429 at the IP level
- [ ] **Service worker excludes API**: If a service worker is registered, `fetch /api/client/v1/me` with no auth cookie returns 401 from the network, NOT a cached 200 from the service worker
- [ ] **bun.lock removed**: `find apps/client-pwa -name "bun.lock" | wc -l` returns 0 after pnpm migration

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---|---|---|
| IDOR discovered post-launch (missing client_id filter) | HIGH — data breach disclosure, audit | Immediately take the affected endpoint offline; add ownership filter; run full IDOR enumeration test suite; determine blast radius from audit_log; notify affected clients per RF legal requirements |
| Phone enumeration oracle discovered | MEDIUM | Add `_constant_time_floor()` and uniform 200 response; re-run anti-oracle test suite; no DB change required |
| Client token accepted by staff endpoint | HIGH — privilege escalation | Deploy fix immediately (reject `principal: "client"` in `get_current_user()`); rotate all client JWTs by flushing `cc_client_access` TTL in Redis; audit access logs |
| Membership activated on redirect (not webhook) | MEDIUM — potential double-activation | Remove redirect-based activation; add DB UNIQUE constraint guard on activation (`UNIQUE (client_id, plan_id, activated_at::date)`); retroactively check for duplicate activations |
| bun.lock / pnpm conflict causing wrong dependency versions | LOW | `rm apps/client-pwa/bun.lock`; `pnpm install --frozen-lockfile` from workspace root; rebuild |
| Staff OpenAPI contract broken by client path addition | MEDIUM | `git revert` the offending commit; redesign using split-spec or operation ID namespacing before re-adding client paths |
| Service worker cached authenticated data post-logout | MEDIUM | Push a service worker update that clears all non-static caches on install; add `Cache-Control: no-store` to all API responses |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---|---|---|
| P-01: IDOR cross-client data leakage | Phase 68 (establish `ClientPrincipal` + client repository pattern) + every domain phase | IDOR enumeration test (client_A → client_B resource → 404) in each domain phase |
| P-02: Phone OTP enumeration oracle | Phase 68 (Client Auth Foundation) | Anti-oracle timing integration test — unknown phone vs. known phone within 100ms |
| P-03: Client token on staff endpoints | Phase 68 (Client Auth Foundation) | Integration test: client JWT → `/api/v1/clients` → 401; staff JWT → `/api/client/v1/me` → 401 |
| P-04: OTP bombing / SMS cost | Phase 68 (Client Auth Foundation) | Per-IP rate limit test; per-phone daily cap test; OTP max-attempts commit-before-raise test |
| P-05: Membership activated on redirect | Phase N (Client Checkout) | Test: present valid ЮKassa redirect URL to checkout return endpoint — assert membership NOT activated; only webhook triggers activation |
| P-06: QR replay / cross-client check-in | Phase N (Client Visits + QR) | Expired QR → 401; client_A QR → check-in as client_B → 401; no-membership QR check-in → 409 |
| P-07: Staff OpenAPI contract broken | Phase 68 (design decision) + every domain phase | `git diff apps/backend/openapi.json` shows only additions; `_v20Checks` counter or split-spec gate green |
| P-08: Cookie name collision | Phase 68 (Client Auth Foundation) | `document.cookie` in browser shows `cc_client_access`, NOT `cc_access` overwritten after client login |
| P-09: Service worker caches auth responses | Phase N (PWA Integration) | Logout test: subsequent fetch with no cookie returns 401 from network, not 200 from cache |
| P-10: bun → pnpm migration breakage | Phase N (PWA Stack Alignment, first sub-task) | `bun.lock` absent; `pnpm install --frozen-lockfile` passes; client-pwa builds with pnpm |
| P-11: CSRF header missing in PWA | Phase 68 (Client Auth Foundation) — `clientFetch` utility | CSRF rejection test: POST without `X-CSRF-Token` → 422; with token → 2xx |

---

## Sources

- Direct codebase inspection:
  - `apps/backend/app/modules/auth/service.py` — `_constant_time_floor()`, `_get_sentinel_hash()`, OTP cooldown, commit-before-raise patterns
  - `apps/backend/app/modules/auth/telegram_service.py` — `consume()` OTP max_attempts with commit-before-raise; `get_status()` never-raises anti-oracle
  - `apps/backend/app/modules/auth/rate_limit.py` — per-email 5/15min fixed-window rate limit; rate-before-lookup discipline
  - `apps/backend/app/modules/visits/service.py` — `_create_visit_with_anti_fraud()` order-locked chain (gym_hours → active_membership → DB UNIQUE); `create_visit_self_checkin()` precedent for client-initiated check-in
  - `apps/backend/app/modules/online_payments/service.py` — `_read_client_email_or_raise()` FIS-05 gate; `_derive_idempotency_key()` deterministic key; server-side price read
  - `apps/backend/app/modules/online_payments/router.py` — `_RETURN_HTML` anti-oracle redirect-return constant; `_RETURN_FLOOR_SECONDS` timing floor
  - `apps/backend/app/core/permissions.py` — `Role` StrEnum (OWNER/RECEPTION only); `can()` function; byte-parity constraint with admin-web `can.ts`
  - `apps/backend/app/core/security.py` — cookie names (`cc_access`, `cc_refresh`, `clubcore_csrf`); `issue_session_cookies()` / `clear_session_cookies()`
  - `apps/backend/app/core/dependencies.py` — `CurrentUser` Protocol; `require_permission()` dependency chain; `get_current_user()` reads `cc_access` cookie
  - `apps/client-pwa/package.json` — `bun.lock` present; React 18.3.1; react-router-dom 6.26.2; plain JS (no TS); Vite 5.4.8; no pnpm workspace membership
  - `apps/admin-web` — React 19; Vite 6; TanStack Router; pnpm workspace; TypeScript strict
  - `.planning/PROJECT.md` — v2.0 scope; client-PWA isolation constraints; anti-oracle; frozen staff contract
  - `.github/workflows/ci.yml` — drift gate on `openapi.json` + `schema.d.ts`; Redocly lint as 7th gate; no Newman in CI

---

*Pitfalls research for: v2.0 Frontend Integration — Client PWA*
*Researched: 2026-05-29*
