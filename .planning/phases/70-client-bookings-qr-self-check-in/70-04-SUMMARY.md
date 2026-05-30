---
phase: 70-client-bookings-qr-self-check-in
plan: "04"
subsystem: client-portal + visits (QR self check-in)
tags:
  - security
  - jwt
  - qr-checkin
  - anti-replay
  - token-confusion
  - protocol-slots
  - rate-limiting
dependency_graph:
  requires:
    - "70-01 (encode_qr_token / decode_qr_token / QrTokenClaims / qr_token_ttl_seconds)"
    - "70-03 (client_portal router/service/schemas base + Protocol slot pattern)"
    - "Phase 68 (ClientPrincipal + require_client)"
    - "Phase 19 (_create_visit_with_anti_fraud / DuplicateCheckinError / uq_visits_client_id_gym_date)"
  provides:
    - "create_visit_client_qr wrapper (visits/service.py; channel='client_qr', checked_in_by=None)"
    - "register_visit_client_qr_creator + create_visit_client_qr Protocol slot (core/dependencies.py)"
    - "GET /client/qr-token (authenticated, ~60s token, no membership pre-check)"
    - "POST /client/check-in (token-as-credential, NO require_client, sub-only client_id)"
    - "Per-IP rate limiting on both endpoints (Redis INCR+EXPIRE)"
    - "ClientQrTokenResponse / ClientCheckInRequest / ClientCheckInResponse schemas"
  affects:
    - "Plan 71 (PWA QR screen uses these endpoints)"
tech_stack:
  added: []
  patterns:
    - "Protocol-slot write delegation: client_portal -> core.dependencies -> visits (D-20-MODULE)"
    - "Token-as-credential endpoint: POST /check-in has NO require_client (D-70-11)"
    - "Per-IP Redis fixed-window rate limit on unauthenticated endpoint (T-70-18)"
    - "SAVEPOINT test harness for duplicate UNIQUE detection (no real-commit needed)"
key_files:
  created:
    - "apps/backend/tests/integration/client_portal/test_qr_token_issue.py"
    - "apps/backend/tests/integration/client_portal/test_qr_checkin.py"
  modified:
    - "apps/backend/app/modules/visits/service.py"
    - "apps/backend/app/core/dependencies.py"
    - "apps/backend/app/main.py"
    - "apps/backend/app/modules/client_portal/schemas.py"
    - "apps/backend/app/modules/client_portal/service.py"
    - "apps/backend/app/modules/client_portal/router.py"
decisions:
  - id: D-70-11-impl
    text: "POST /client/check-in deliberately omits require_client(); client_id derives only from verified QR token sub claim — cross-client check-in structurally impossible (no body/path/query client_id parameter)"
  - id: D-70-RATELIMIT
    text: "Per-IP Redis fixed-window rate limits: 20 req/min for GET /qr-token (authenticated, legitimate use=1 req/50s), 60 req/min for POST /check-in (unauthenticated, accommodates multi-scanner gyms). INCR+EXPIRE pattern mirrors auth/reset_rate_limit.py. RateLimited(429) bubbles to _app_error_handler. Decision: actual controls wired in the router, not deferred."
  - id: D-70-ERRCODE
    text: "HTTP response for InvalidAccessToken always uses class-level code='invalid_token'; specific discriminator is in message field (token_expired/wrong_token_type/wrong_audience). Tests assert message field, not code, for granular validation — consistent with unit tests (exc_info.value.message)."
  - id: D-70-04-SLOT
    text: "VisitClientQrCreator Protocol slot in core/dependencies.py mirrors BookingForClientCreator shape exactly (Callable[..., Awaitable[Any]], defensive-raise, idempotent re-register). client_portal never imports app.modules.visits — zero new ignore_imports."
metrics:
  duration: "~35 min"
  completed: "2026-05-30"
  tasks_completed: 3
  files_modified: 8
---

# Phase 70 Plan 04: QR Self Check-In Security Surface Summary

**One-liner:** Token-as-credential QR check-in with anti-replay (exp + daily-UNIQUE), token-confusion isolation (distinct typ/aud), structurally-impossible cross-client check-in, per-IP rate limits on both endpoints, and Protocol-slot write delegation preserving zero new ignore_imports.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | create_visit_client_qr wrapper + Protocol slot + main wiring | c8e246de | visits/service.py, core/dependencies.py, main.py |
| 2 | QR token issue + check-in endpoints + rate limiting | d39a4d9c | schemas.py, service.py, router.py, test_qr_token_issue.py |
| 3 | Anti-replay / token-confusion / cross-client tests (criterion #5) | 53128de7 | test_qr_checkin.py, test_qr_token_issue.py |
| 4 | CHECKPOINT: Human verification of QR security behavior | — | — |

## What Was Built

### Task 1: `create_visit_client_qr` Wrapper + Protocol Slot

`app/modules/visits/service.py`:
- `create_visit_client_qr(session, client_id: UUID) -> VisitResponse` mirrors `create_visit_self_checkin` exactly — calls `_create_visit_with_anti_fraud` with `channel="client_qr"`, `checked_in_by=None`, `audit_actor_user_id=None`. Returns `VisitResponse` only (discards `end_date` — QR scanner has no DM target unlike the bot path D-22-11).

`app/core/dependencies.py`:
- `VisitClientQrCreator = Callable[..., Awaitable[Any]]` — late-bound return type to respect `core-not-depend-on-modules` contract.
- `register_visit_client_qr_creator(creator)` — idempotent composition-root setter (WR-05).
- `create_visit_client_qr(session, client_id)` — defensive-raise accessor (mirrors `get_payment_recorder` pattern).

`app/main.py`:
- Wired `register_visit_client_qr_creator(visits_service.create_visit_client_qr)` next to the booking slot registrations. HTTP-only single-wire.

### Task 2: QR Endpoints + Schemas + Rate Limiting

**Schemas (`client_portal/schemas.py`)**:
- `ClientQrTokenResponse(token: str, expires_in: int)` — `expires_in` mirrors `settings.qr_token_ttl_seconds` (~60s)
- `ClientCheckInRequest(token: str)` — NO `client_id` field (D-70-10 / T-70-17 structural mitigation)
- `ClientCheckInResponse(id, gym_date, checked_in_at, channel)` — client-safe visit projection; never imports `app.modules.visits`

**Service (`client_portal/service.py`)**:
- `issue_qr_token(client_id) -> ClientQrTokenResponse` — pure function, calls `encode_qr_token(client_id)` + `get_settings().qr_token_ttl_seconds`. NO membership pre-check (D-70-09).
- `check_in_via_qr(session, *, token) -> ClientCheckInResponse` — calls `decode_qr_token(token)` (raises `InvalidAccessToken` on any failure), extracts `client_id = UUID(claims.sub)` (sole source, D-70-10), then calls `create_visit_client_qr` Protocol slot.

**Router (`client_portal/router.py`)**:
- `GET /qr-token` (`operation_id="client_get_qr_token"`) — behind `require_client()`, no CSRF (GET), rate-limited.
- `POST /check-in` (`operation_id="client_check_in"`) — **deliberately omits `require_client()`** (token-as-credential, D-70-11). Rate-limited. No body/path `client_id`.

**Rate Limiting (T-70-18 — actual control, not deferral)**:
- `/qr-token`: 20 req/min per IP (authenticated; legitimate use ~1/50s). Key: `ratelimit:qr_token:ip:{ip}`.
- `/check-in`: 60 req/min per IP (unauthenticated; multi-scanner gym consideration). Key: `ratelimit:check_in:ip:{ip}`.
- INCR+EXPIRE pattern from `app/modules/auth/reset_rate_limit.py`. `RateLimited(429)` bubbles to `_app_error_handler`.
- **This is an actual rate-limiting control wired in the router — not a deferral note.**

### Task 3: Security Tests (Criterion #5 / CCHK-03)

**`test_qr_token_issue.py`** (5 tests):
- `test_qr_token_issuance_returns_token_and_expires_in` — 200, token present, `expires_in == qr_token_ttl_seconds`
- `test_qr_token_no_membership_precheck` — client with no membership still gets a token (D-70-09)
- `test_qr_token_requires_auth` — no session → 401 (require_client guard)
- `test_check_in_valid_token_creates_visit` — valid QR token → 200, channel='client_qr'
- `test_check_in_schema_has_no_client_id_field` — invalid token at unauthenticated endpoint → 401 `invalid_token` (not `missing_access_cookie`)

**`test_qr_checkin.py`** (6 tests):
1. `test_expired_qr_token_rejected` — 120s-past token → 401, message=`token_expired` (T-70-14)
2. `test_same_day_double_checkin_collapses_to_duplicate` — second check-in → 409 `duplicate_checkin` (T-70-15); DB confirms exactly 1 visit row
3. `test_access_token_at_checkin_rejected` — access token (typ=access) → 401, message=`wrong_token_type` (T-70-16)
4. `test_qr_token_at_authenticated_endpoint_rejected` — QR token at `GET /membership` → 401, message=`wrong_token_type` (T-70-16 reverse)
5. `test_cross_client_checkin_structurally_impossible` — client B's token under client A's session → visit created for B, not A; DB confirms `client_id == B.id` (T-70-17)
6. `test_no_request_parameter_can_override_checkin_target` — extra `clientId` field injected → silently ignored; visit still for B (D-70-10)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] HTTP 401 response uses class-level `code="invalid_token"`, not message**
- **Found during:** Task 3 test execution
- **Issue:** Tests initially asserted `r.json()["code"] == "token_expired"` but the error handler returns `exc.code` (class default = `"invalid_token"`) not the constructor message. The specific discriminator is in `exc.message = "token_expired"`.
- **Fix:** Updated test assertions to check `body["code"] == "invalid_token"` and `body["message"] == "token_expired"` (or "wrong_token_type" etc.). Consistent with unit test discipline (`exc_info.value.message`).
- **Files modified:** `test_qr_checkin.py`, `test_qr_token_issue.py`
- **Commit:** 53128de7

**2. [Rule 1 - Bug] SQLAlchemy detached instance on `client.id` after SAVEPOINT rollback**
- **Found during:** Task 3 duplicate-checkin test
- **Issue:** `client.id` accessed after SAVEPOINT operations expired the ORM instance.
- **Fix:** Captured `client_id = client.id` before any HTTP calls that trigger SAVEPOINT rollback.
- **Files modified:** `test_qr_checkin.py`
- **Commit:** 53128de7

**3. [Rule 1 - Bug] httpx deprecated per-request `cookies=` parameter**
- **Found during:** Task 3 QR-at-authenticated-endpoint test
- **Issue:** `http_client.get(url, cookies={...})` raised `DeprecationWarning` treated as error in pytest.
- **Fix:** Used a fresh `AsyncClient` instance with cookies pre-set on the client constructor, sharing the same ASGI transport.
- **Files modified:** `test_qr_checkin.py`
- **Commit:** 53128de7

## Verification Results

```
uv run pytest tests/integration/client_portal/ tests/integration/visits/ -q
78 passed in 33.44s

uv run lint-imports
Contracts: 3 kept, 0 broken. (1 pre-existing warning: online_payments.service -> users.display unmatched — not introduced by this plan)

uv run mypy app/modules/client_portal/ app/core/dependencies.py app/modules/visits/service.py
Success: no issues found in 7 source files

uv run ruff check app/modules/client_portal/ app/modules/visits/service.py app/core/dependencies.py
All checks passed!
```

## Rate-Limiting Decision Record (T-70-18)

**Threat:** POST /client/check-in is unauthenticated — an open scan endpoint invites brute-force QR token scanning flood and DoS.

**Control implemented:** Per-IP Redis fixed-window rate limit using `INCR + EXPIRE` pipeline (same pattern as `app/modules/auth/reset_rate_limit.py`).

| Endpoint | Limit | Window | Key pattern | Rationale |
|----------|-------|--------|-------------|-----------|
| GET /client/qr-token | 20 req/min | 60s | `ratelimit:qr_token:ip:{ip}` | Authenticated; ~1 legitimate refresh per 50s. Burst headroom for retry on network failure. |
| POST /client/check-in | 60 req/min | 60s | `ratelimit:check_in:ip:{ip}` | Unauthenticated; gym may have multiple scanners behind a single NAT IP. 1/sec steady-state per scanner, 60 gives ~60 scanners or burst allowance. |

`RateLimited` (HTTP 429, code="rate_limited") bubbles to `_app_error_handler`. No new packages required — Redis client already in the dependency graph. **This is a wired control, not a deferred note.**

## Known Stubs

None. All endpoints are fully implemented and wired.

## Threat Flags

No new threat surfaces beyond what the plan's threat_model defines. All T-70-14..T-70-19 and T-70-SC mitigations implemented:
- T-70-14 (expired replay): exp claim + decode_qr_token raises token_expired → 401. Tested.
- T-70-15 (duplicate same-day): uq_visits_client_id_gym_date → duplicate_checkin. Tested.
- T-70-16 (token confusion): distinct typ/aud; access token → wrong_token_type at /check-in; QR token → wrong_token_type at require_client endpoint. Tested both directions.
- T-70-17 (cross-client): ClientCheckInRequest has no client_id field; client_id strictly from sub; cross-client structurally impossible. Tested.
- T-70-18 (DoS): per-IP rate limits wired as actual controls on both endpoints.
- T-70-19 (import boundary): core.dependencies Protocol slot; lint-imports confirms 0 new ignore_imports.
- T-70-SC: No new package installs in this plan.

## CHECKPOINT: Awaiting Human Verification

Task 4 is a `blocking-human` checkpoint. See checkpoint message below.

## Self-Check

- [x] `apps/backend/app/modules/visits/service.py` — contains `def create_visit_client_qr(` with `channel="client_qr"`, `checked_in_by=None`
- [x] `apps/backend/app/core/dependencies.py` — contains `register_visit_client_qr_creator` and `create_visit_client_qr`
- [x] `apps/backend/app/main.py` — calls `register_visit_client_qr_creator(visits_service.create_visit_client_qr)`
- [x] `apps/backend/app/modules/client_portal/router.py` — contains `operation_id="client_get_qr_token"` and `operation_id="client_check_in"`; check-in handler has NO `require_client()` in signature
- [x] `apps/backend/app/modules/client_portal/schemas.py` — `ClientCheckInRequest` has NO `client_id` field
- [x] `apps/backend/tests/integration/client_portal/test_qr_token_issue.py` — 5 tests, all pass
- [x] `apps/backend/tests/integration/client_portal/test_qr_checkin.py` — 6 tests, all pass
- [x] lint-imports: 3 contracts kept, 0 broken, 0 new ignore_imports
- [x] 78 total client_portal + visits integration tests passing

## Self-Check: PASSED
