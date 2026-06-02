---
phase: 68-client-auth-foundation
verified: 2026-05-29T14:00:00Z
status: passed
score: 5/5
overrides_applied: 0
gaps: []
gap_closed:
  - truth: "PATCH /api/v1/client/me accepts an email update; subsequent GET returns the updated email"
    status: resolved
    resolved_by: "tests/integration/client_auth/test_profile_update.py (commit df314ffb)"
    tests:
      - "test_patch_me_email_round_trip: authenticate → PATCH /me new email → 200 + body reflects new email → GET /me → email matches patched value"
      - "test_patch_me_duplicate_email_409: PATCH /me with email held by another alive client → 409 code=conflict message=email_unavailable → GET /me → original email unchanged"
    note: "SC4 gap closed in-line during execution. 18 client_auth tests green (was 16). ruff + mypy --strict clean."
---

# Phase 68: Client Auth Foundation — Verification Report

**Phase Goal:** A secure, isolated client principal exists; gym members can authenticate via phone + Telegram OTP, hold a distinct session cookie (`cc_client_access`) that survives browser restart (refresh rotation + logout clears it), view/edit their profile, and the two-principal isolation (staff vs client) is proven by automated test.
**Verified:** 2026-05-29T14:00:00Z
**Status:** passed (SC4 gap closed in-line; see `gap_closed` in frontmatter)
**Re-verification:** Yes — SC4 gap resolved 2026-05-29 (commit `df314ffb`)

## Goal Achievement

### Observable Truths (5 ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | Client can request Telegram OTP with phone, verify the code, receive a `cc_client_access` cookie that survives browser restart (refresh rotation works, logout clears it) | VERIFIED | `test_full_session_lifecycle` (CAUTH-04) in `test_session_lifecycle.py`: OTP request → verify (3 cookies with correct Path/HttpOnly attributes) → GET /me 200 → refresh rotation (new refresh token) → logout (all 3 cookies cleared) → GET /me 401. Cookie math: `cc_client_access` (Path=/, HttpOnly, SameSite=Lax), `cc_client_refresh` (Path=/api/v1/client, HttpOnly), `clubcore_client_csrf` (Path=/, NOT HttpOnly). `max_age = refresh_token_ttl_seconds` ensures browser-restart persistence. |
| 2 | OTP request for unknown/duplicate/soft-deleted phone returns response byte-identical to a known phone (anti-oracle; `_constant_time_floor`) | VERIFIED | `test_otp_request_anti_oracle` (4-case parametrize, each 202) + `test_otp_request_anti_oracle_body_parity` asserts byte-identical response body across all 4 phone states. `_constant_time_floor` applied via `try/finally` in `request_client_otp` (line 248) AND `verify_client_otp` (line 370, WR-02 fix). `test_verify_otp_oracle_parity` (added in review-fix) confirms expired-vs-unknown OTP returns byte-identical 401 — CR-02 oracle closed. |
| 3 | Staff JWT to `GET /api/v1/client/me` → 401; client JWT to any staff endpoint → 401 (two-principal isolation test green) | VERIFIED | `test_staff_token_rejected_by_client_endpoint` (CISO-02): staff `cc_access` token presented as `cc_client_access` → 401. `test_client_token_rejected_by_staff_endpoint` (CISO-02 reverse): client `cc_client_access` token presented as `cc_access` to `GET /clients` → 401. Isolation is structural: `decode_client_token` requires `aud="client"` (staff tokens lack `aud` → `MissingRequiredClaimError → 401`); `decode_access_token` validates `role` against `Role` enum (client tokens carry no `role` → `unknown_role → 401`). |
| 4 | `PATCH /api/v1/client/me` accepts an email update; subsequent GET returns the updated email | VERIFIED | `test_patch_me_email_round_trip` + `test_patch_me_duplicate_email_409` in `test_profile_update.py` (SC4 gap closed). Round-trip proven: authenticate → PATCH /me new email → 200 → GET /me → email matches. 409 duplicate-email case proven: PATCH with another alive client's email → 409 code=conflict message=email_unavailable (D-06 non-enumerating) → GET /me → original email unchanged. 18 client_auth tests green. |
| 5 | OTP requests exceeding the rate limit (per-IP 5/15min, per-phone daily cap) rejected with 429; brute-force code guessing blocked | VERIFIED | `test_otp_rate_limited` (CAUTH-06): directly sets daily counter to `_DAILY_LIMIT` in Redis, next request → 429 `rate_limited`. `test_otp_brute_force_blocked` (CAUTH-06): `otp_max_attempts - 1` wrong codes → 401 `otp_invalid`; final wrong → 429 `otp_max_attempts`; subsequent wrong → still 429. Rate-limit implementation: `check_client_ip_rate` (5/15min), `check_client_otp_cooldown` (60s per phone), `check_client_otp_daily` (5/24h per phone) — all checked BEFORE DB lookup (D-11). WR-01 fix: `nx=True` on `pipe.expire()` anchors window to first request. |

**Score:** 5/5 truths verified (SC4 gap closed — see `gap_closed` in frontmatter)

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/app/modules/auth/models.py` | OtpCode.client_id FK + AT-MOST-ONE CHECK (`principal_excl`) + partial-unique `uq_otp_codes_client_channel_active` | VERIFIED | `client_id: Mapped[UUIDType | None]` with `ForeignKey("clients.id", ondelete="CASCADE")`, `CheckConstraint("NOT (user_id IS NOT NULL AND client_id IS NOT NULL)", name="principal_excl")`, `Index("uq_otp_codes_client_channel_active", "client_id", "channel", unique=True, postgresql_where=text("consumed_at IS NULL"))`. Note: Plan 01 must_haves named the constraint `ck_otp_codes_principal_xor` but D-03 was corrected during execution — XOR (exactly-one) was over-constraining; AT-MOST-ONE (`principal_excl`) is the implemented and documented design (migration docstring explains the correction). |
| `apps/backend/app/modules/client_auth/models.py` | `ClientRefreshToken` ORM model, FK to `clients.id` | VERIFIED | `class ClientRefreshToken(Base, UUIDPkMixin, TimestampMixin)`, `__tablename__ = "client_refresh_tokens"`, `client_id FK → clients.id CASCADE`, `replaced_by_id FK → self SET NULL`, `token_hash unique=True`, `Index("ix_client_refresh_tokens_client_id_family_id")`. |
| `apps/backend/alembic/versions/0043_client_auth_otp.py` | Additive migration with working downgrade | VERIFIED | `revision = "0043_client_auth_otp"`, `down_revision = "0042_recurring_schedule_time_off"`, upgrade adds `client_id` column + FK + CHECK + index; downgrade drops them in reverse order. |
| `apps/backend/alembic/versions/0044_client_refresh_token.py` | `client_refresh_tokens` table migration with working downgrade | VERIFIED | `revision = "0044_client_refresh_token"`, `down_revision = "0043_client_auth_otp"`, creates `client_refresh_tokens` with all columns, FKs, PK, unique, index. Linear chain `0042 → 0043 → 0044`. |
| `apps/backend/app/core/security.py` | `encode_client_token`, `decode_client_token`, `ClientAccessTokenClaims`, `issue_client_session_cookies`, `clear_client_session_cookies` | VERIFIED | All 5 symbols present. `ClientAccessTokenClaims` has no `role` field (D-07). `decode_client_token` requires `aud="client"` (D-08). `issue_client_session_cookies` sets `cc_client_access` (Path=/, HttpOnly), `cc_client_refresh` (Path=/api/v1/client, HttpOnly), `clubcore_client_csrf` (Path=/, NOT HttpOnly). Staff `AccessTokenClaims` + `decode_access_token` are byte-unchanged (CISO-01 frozen contract). |
| `apps/backend/app/core/dependencies.py` | `ClientPrincipal`, `register_client_loader`, `get_current_client`, `require_client`, `verify_client_csrf` | VERIFIED | All 5 symbols present at line 1148+. `ClientPrincipal` protocol: `id: UUID`, `phone: str`, `email: str | None` — no `role` field (CISO-01). `get_current_client` reads `cc_client_access` → `decode_client_token` → `_client_loader` → `ClientPrincipal`. `verify_client_csrf` checks `clubcore_client_csrf` cookie vs `x-csrf-token` header. |
| `apps/backend/app/modules/client_auth/service.py` | `request_client_otp`, `verify_client_otp`, `rotate_client_refresh`, `revoke_client_session`, `update_client_me` | VERIFIED | All 5 functions present with real DB operations. `_constant_time_floor` applied via `try/finally` in both `request_client_otp` and `verify_client_otp`. 3-branch rotation in `rotate_client_refresh` mirrors staff `rotate_refresh`. Redis keys in `auth:client:*` namespace only (CISO-05). |
| `apps/backend/app/modules/client_auth/router.py` | 6 handlers: `/otp/request`, `/otp/verify`, `/session/refresh`, `/session/logout`, `GET /me`, `PATCH /me` | VERIFIED | All 6 handlers present, mounted under `/api/v1/client` via `apps/backend/app/api/v1/router.py:95`. `require_client()` + `verify_client_csrf` dependency ordering (RBAC-04: auth before CSRF). `/otp/request` always returns 202 envelope (SC2 boundary). |
| `apps/backend/app/modules/client_auth/schemas.py` | `ClientOtpRequestBody`, `ClientOtpVerifyBody`, `ClientMeResponse`, `ClientMePatchRequest` | VERIFIED | All 4 schemas present. `ClientMePatchRequest.email: EmailStr | None = None` (CR-01 fix applied). Phone validated with `_PHONE_REGEX = r"^\+[1-9]\d{1,14}$"` (CAUTH-03, E.164). |
| `apps/backend/app/modules/client_auth/rate_limit.py` | per-IP, cooldown, daily rate limiters with `nx=True` window anchoring | VERIFIED | `_IP_LIMIT = 5`, `_IP_WINDOW = 900`; `_COOLDOWN_SECONDS = 60`; `_DAILY_LIMIT = 5`, `_DAILY_WINDOW = 86400`. Both `bump_client_ip_rate` and `bump_client_otp_daily` use `pipe.expire(key, ttl, nx=True)` (WR-01 fix). Separate `ratelimit:client_otp_*` keyspace (CISO-05 quota isolation). |
| `apps/backend/tests/integration/client_auth/` (5 test files) | 18 tests proving phase contract | VERIFIED | 18 tests green. `test_otp_isolation.py` (7), `test_idor.py` (2), `test_session_lifecycle.py` (4), `test_byte_parity.py` (3), `test_profile_update.py` (2 — SC4 gap closed). |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `client_otp_request` handler | `service.request_client_otp` | direct call | VERIFIED | Router imports `service` and calls `await service.request_client_otp(session, redis, payload.phone, ip=ip)` |
| `client_otp_verify` handler | `issue_client_session_cookies` | response mutation | VERIFIED | Calls `issue_client_session_cookies(response, access_token=access, ...)` with 3 cookie names |
| `get_current_client` | `decode_client_token` | `cc_client_access` cookie | VERIFIED | `token = request.cookies.get("cc_client_access")` → `claims = decode_client_token(token)` |
| `app/api/v1/router.py` | `client_auth_router` | `include_router(prefix="/client")` | VERIFIED | Line 95: `v1.include_router(client_auth_router, prefix="/client")` |
| `app/main.py create_app` | `register_client_loader` | composition root | VERIFIED | Line 470: `register_client_loader(load_client_by_id)` |
| `app/main.py create_app` | `register_client_otp_sender` | composition root | VERIFIED | Lines 479-486: `register_client_otp_sender(_send_client_otp_dm)` |
| `OtpCode.client_id` | `clients.id` | `ForeignKey ondelete="CASCADE"` | VERIFIED | `ForeignKey("clients.id", ondelete="CASCADE")` in `auth/models.py:116` |
| `ClientRefreshToken.client_id` | `clients.id` | `ForeignKey ondelete="CASCADE"` | VERIFIED | `ForeignKey("clients.id", ondelete="CASCADE")` in `client_auth/models.py:37` |
| `patch_client_me` handler | `service.update_client_me` | direct call | VERIFIED | `updated = await service.update_client_me(session, client.id, payload.email)` — no stale `try/except ConflictError: raise` (WR-04 fix applied) |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `router.py:get_client_me` | `client: ClientPrincipal` | `get_current_client → _client_loader → load_client_by_id → DB SELECT` | Yes — `select(Client).where(Client.id == uid, Client.deleted_at.is_(None))` | FLOWING |
| `router.py:patch_client_me` | `updated: Client` | `service.update_client_me → DB SELECT + flush/commit` | Yes — loads client, sets `email`, commits to DB | FLOWING |
| `service.py:verify_client_otp` | `(access, raw_refresh, csrf)` | DB OTP row + `encode_client_token` + `generate_refresh_token` + `generate_csrf_token` | Yes — real JWT minting, real token generation, DB commit | FLOWING |
| `service.py:rotate_client_refresh` | `(access, raw_refresh, csrf)` | `ClientRefreshToken` DB row + branch logic | Yes — 3-branch rotation, SELECT FOR UPDATE, real INSERT + UPDATE | FLOWING |

---

### Behavioral Spot-Checks

Step 7b SKIPPED — tests require a running Postgres+Redis stack; spot-checks deferred to the existing integration test suite which reports 2279 passed, 6 skipped, 0 failed (per REVIEW-FIX verification results).

---

### Probe Execution

No `scripts/*/tests/probe-*.sh` files declared or discovered for this phase.

---

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|---------------|-------------|--------|---------|
| CAUTH-01 | 68-01, 68-05 | Phone + Telegram OTP login; reuses existing OTP infrastructure | SATISFIED | `request_client_otp` + `verify_client_otp` in service.py; OtpCode.client_id FK; `test_full_session_lifecycle` green |
| CAUTH-02 | 68-05, 68-06 | Anti-oracle: unknown/duplicate/soft-deleted phone returns byte-identical response | SATISFIED | `_constant_time_floor` in `request_client_otp` + `verify_client_otp`; 4-case body-parity test + `test_verify_otp_oracle_parity` green |
| CAUTH-03 | 68-02 (implicitly), 68-05 | Phone normalized and validated to E.164 | SATISFIED | `_PHONE_REGEX = r"^\+[1-9]\d{1,14}$"` on `phone: str = Field(pattern=_PHONE_REGEX)` in schemas.py; 422 before any DB lookup |
| CAUTH-04 | 68-01, 68-02, 68-03, 68-05, 68-06 | Session cookie persistence, refresh rotation, logout | SATISFIED | `test_full_session_lifecycle` green: verify → GET /me 200 → refresh → new cookies → logout → GET /me 401; `cc_client_access` has `max_age = access_token_ttl_seconds` for browser restart persistence |
| CAUTH-05 | 68-05 | GET /me returns profile; PATCH /me accepts email update | SATISFIED | GET /me → `ClientMeResponse` (8 fields, session-bound) is tested and wired. PATCH /me round-trip proven by `test_patch_me_email_round_trip` + `test_patch_me_duplicate_email_409` in `test_profile_update.py` (SC4 gap closed) |
| CAUTH-06 | 68-05, 68-06 | Rate limiting (per-IP + cooldown + daily cap) + brute-force protection | SATISFIED | `rate_limit.py` with 3 Redis-backed limiters; `test_otp_rate_limited` + `test_otp_brute_force_blocked` green |
| CISO-01 | 68-03, 68-04, 68-06 | No Role.CLIENT; permissions.py + can.ts frozen | SATISFIED | `test_no_role_client_in_permissions`: `"CLIENT" not in Role.__members__`; `test_client_principal_has_no_role`: `"role" not in annotations`; `test_admin_web_can_ts_unchanged`: `can.ts` has no `| 'client'` or `Role.CLIENT` |
| CISO-02 | 68-03, 68-05, 68-06 | Staff token 401 on client endpoint; client token 401 on staff endpoint | SATISFIED | `test_staff_token_rejected_by_client_endpoint` + `test_client_token_rejected_by_staff_endpoint` both green; structural isolation via `aud` claim asymmetry |
| CISO-03 | 68-03, 68-05 | Each client-scoped endpoint filters by session client_id; get-by-id asserts ownership | SATISFIED (Phase 68 scope) | Phase 68 has only `/me` endpoints — inherently owner-filtered (principal from cookie, no URL param). `require_client()` resolves the cookie-bound principal; `update_client_me` uses `client.id` from principal (not a URL parameter). `test_get_me_returns_only_own_id` (IDOR parametrize) proves no cross-client read. No get-by-id resource endpoints exist in Phase 68; `assert_owns()` pattern applies to Phase 69+ resource endpoints. |
| CISO-04 | 68-06 | Parametrized cross-client enumeration (IDOR) test covers all client-owned resources and is green | SATISFIED | `test_get_me_returns_only_own_id[True/False]`: both orderings (A→B, B→A) assert `returned_id == attacker.id AND != victim.id` |
| CISO-05 | 68-01, 68-02, 68-03, 68-05, 68-06 | Client cookies `cc_client_*` isolated from staff `cc_*`; no mutual session overwrite | SATISFIED | Cookie names: `cc_client_access`, `cc_client_refresh` (Path=/api/v1/client), `clubcore_client_csrf`. Staff cookies: `cc_access`, `cc_refresh` (Path=/api/v1/auth), `clubcore_csrf`. No name overlap. Redis namespace: `auth:client:*` vs `auth:session:*` (D-11 separate quota). |

**Orphaned requirements check:** No REQUIREMENTS.md entries for Phase 68 appear outside the plans' declared `requirements` fields. All 11 Phase 68 requirements accounted for.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `apps/backend/app/modules/client_auth/__init__.py` | 4 | `TODO Phase C+: client OTP request/verify, session cookies, /me endpoints.` | Warning | Stale documentation. The TODO was written in Plan 01 before the rest of the phase was built; the implementation it references is fully complete as of Plans 02-06. No functional impact. The module docstring simply was not updated after completion. |

No `TBD`, `FIXME`, or `XXX` markers found in any file modified by this phase.
The `__init__.py` TODO is stale documentation, not a debt marker for unimplemented work — the referenced functionality fully exists. This is a Warning, not a Blocker.

---

### Frozen-Contract Verification (Phase 68 Specific)

| Contract | Status | Evidence |
|----------|--------|---------|
| `Role.CLIENT` never added to `app/core/permissions.py` | VERIFIED | `Role` enum has only `OWNER` and `RECEPTION` values; `test_no_role_client_in_permissions` green |
| `AccessTokenClaims` / `decode_access_token` byte-unchanged | VERIFIED | Staff `AccessTokenClaims` dataclass: `sub, role, typ, iat, exp` — no `aud` field added; `decode_access_token` validates `role` against `Role` enum — unchanged from pre-Phase 68 baseline |
| `apps/admin-web/src/shared/session/can.ts` byte-unchanged | VERIFIED | `test_admin_web_can_ts_unchanged`: file exists, no `Role.CLIENT`, no `| 'client'` or `| "client"` in `types.ts` Role union |
| `apps/admin-web/src/shared/session/types.ts` Role type | VERIFIED | `export type Role = 'owner' | 'reception'` — client role absent |
| `app/core/permissions.py` source has no `Role.CLIENT` literal | VERIFIED | Content-check passes: `"Role.CLIENT" not in source_text` |

---

### Human Verification Required

None — all verifiable claims resolved programmatically except the PATCH /me round-trip, which is classified as a gap (code gap, not a human-verification item: the missing artifact is an automated test, not a UI/UX behavior).

---

### Gaps Summary

**0 gaps** — all 5 success criteria verified.

**SC4 gap closed** (`test_profile_update.py`, commit `df314ffb`):

`test_patch_me_email_round_trip` and `test_patch_me_duplicate_email_409` were added to
`tests/integration/client_auth/test_profile_update.py` in-line during execution.  Both tests
pass; client_auth suite is now 18 tests green (was 16).  The PATCH /me round-trip behavior
described in ROADMAP SC4 is now proven by automated test: authenticate → PATCH /me new email
→ 200 → GET /me → email matches; and duplicate-email → 409 code=conflict
message=email_unavailable (D-06) → original email unchanged.

---

_Verified: 2026-05-29T14:00:00Z_
_Verifier: Claude (gsd-verifier)_
