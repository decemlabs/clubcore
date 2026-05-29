---
phase: 68
name: client-auth-foundation
asvs_level: L1
audited_at: 2026-05-29
verdict: SECURED
status: verified
threats_total: 32
threats_closed: 32
threats_open: 0
---

# SECURITY.md — Phase 68: client-auth-foundation

## Summary

All 32 declared threats verified. 30 mitigate dispositions have code evidence. 2 accept
dispositions are confirmed in implementation and documented below. No open threats. Phase
may ship.

---

## Accepted Risks Log

### T-68-04 — Denial: migration lock on otp_codes

**Disposition:** ACCEPT

**Rationale:** Migration 0043_client_auth_otp adds a nullable column with no default,
a CHECK constraint, and a partial-unique index to otp_codes. On a single-gym dataset
the table row count is low (hundreds to low-thousands). PostgreSQL ADD COLUMN with
nullable and no default is a metadata-only operation (no table rewrite). The CHECK
constraint and partial-unique index are lightweight additions. The migration takes
<1s under expected dataset sizes. Lock risk is accepted for this deployment tier.

**Code evidence:** `apps/backend/alembic/versions/0043_client_auth_otp.py:40-70` —
additive `add_column` (nullable, no default) + `create_check_constraint` +
`create_index`.

---

### T-68-09 — Repudiation: client CSRF cookie readable by JS

**Disposition:** ACCEPT

**Rationale:** `clubcore_client_csrf` is intentionally `httponly=False` because the
double-submit CSRF pattern requires the frontend PWA to read the cookie value and echo
it in the `X-CSRF-Token` request header. The cookie value is a 64-char hex CSRF nonce
(not a session secret). Session secrets are carried by `cc_client_access` and
`cc_client_refresh` which are both `httponly=True`. This is identical to the staff
`clubcore_csrf` cookie treatment, which is an established accepted risk in the project.

**Code evidence:** `apps/backend/app/core/security.py:444-448` — `clubcore_client_csrf`
set with `httponly=False`.

---

## Threat Verification Table

| Threat ID | Category | Disposition | Status | Evidence |
|-----------|----------|-------------|--------|----------|
| T-68-01 | Elevation | mitigate | CLOSED | auth/models.py:172-175 — CheckConstraint("NOT (user_id IS NOT NULL AND client_id IS NOT NULL)", name="principal_excl"); 0043_client_auth_otp.py:57-61 — ck_otp_codes_principal_excl. Name deviated from plan (xor→excl) but security function is equivalent or stronger (AT-MOST-ONE instead of strict XOR; allows pre-bind null/null rows). |
| T-68-02 | Tampering | mitigate | CLOSED | 0043_client_auth_otp.py:40-43 — `add_column("client_id", nullable=True)` no default; migration comment line 9: "no backfill writes". |
| T-68-03 | Spoofing | mitigate | CLOSED | client_auth/models.py:44 — `token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)`; 0044_client_refresh_token.py:70 — `UniqueConstraint("token_hash")`. |
| T-68-04 | Denial | accept | CLOSED | See accepted risks log above. |
| T-68-05 | Spoofing | mitigate | CLOSED | core/security.py:343-388 — `decode_client_token` requires `aud` claim (MissingRequiredClaimError→invalid_token for staff tokens); guard at line 379: `if payload.get("aud") != "client": raise InvalidAccessToken("wrong_audience")`. Staff decode at line 100 validates Role enum (client tokens have no role→invalid_token). |
| T-68-06 | Tampering | mitigate | CLOSED | core/security.py:360-375 — `jwt.decode` with `algorithms=["HS256"]` and `settings.secret_key`; `except jwt.InvalidTokenError: raise InvalidAccessToken("invalid_token")`. |
| T-68-07 | Elevation | mitigate | CLOSED | core/security.py:429-435 — `cc_client_refresh` set with `path="/api/v1/client"`. Distinct names: `cc_client_access`, `cc_client_refresh`, `clubcore_client_csrf` vs staff `cc_access`, `cc_refresh`, `clubcore_csrf`. |
| T-68-08 | Info disclosure | mitigate | CLOSED | core/security.py:459-481 — `clear_client_session_cookies` deletes all three cookies with matching path/httponly/samesite/secure: `cc_client_access` path="/", httponly=True; `cc_client_refresh` path="/api/v1/client", httponly=True; `clubcore_client_csrf` path="/", httponly=False. |
| T-68-09 | Repudiation | accept | CLOSED | See accepted risks log above. core/security.py:444: `httponly=False`. |
| T-68-10 | Spoofing | mitigate | CLOSED | core/dependencies.py:1210-1216 — reads `cc_client_access` cookie; calls `decode_client_token(token)` which requires `aud=="client"`. Staff tokens (no aud) → MissingRequiredClaimError → InvalidAccessToken("invalid_token") → 401. |
| T-68-11 | Elevation | mitigate | CLOSED | core/dependencies.py:1158-1168 — `class ClientPrincipal(Protocol)`: fields id/phone/email only; no `role`. core/permissions.py lines 15-17: `Role(StrEnum)` has only OWNER and RECEPTION. test_byte_parity.py:55 asserts `"CLIENT" not in Role.__members__`. |
| T-68-12 | Spoofing | mitigate | CLOSED | core/dependencies.py:1254-1276 — `verify_client_csrf` reads `clubcore_client_csrf` cookie; `secrets.compare_digest(cookie_val, header_val)` at line 1275. |
| T-68-13 | Info disclosure | mitigate | CLOSED | modules/clients/service.py:258-263 — `load_client_by_id` filters `Client.deleted_at.is_(None)`; returns None for soft-deleted clients → `get_current_client` raises `InvalidAccessToken("user_not_found")` → 401. |
| T-68-14 | Tampering | mitigate | CLOSED | core/dependencies.py:1218-1221 — `if _client_loader is None: raise InvalidAccessToken("client_loader_not_registered")`. Fail-closed: missing loader slot surfaces as 401, not 500. |
| T-68-15 | Info disclosure | mitigate | CLOSED | client_auth/service.py:190-191 — `if client is None or client.telegram_user_id is None: return` (silent no-op). router.py:74 — always returns `envelope(None)` with status 202. |
| T-68-16 | Info disclosure | mitigate | CLOSED | client_auth/service.py:175 — `t_start = time.perf_counter()` before try; service.py:246-248 — `finally: await _constant_time_floor(t_start)`; rate-limit checks at lines 178-180 run BEFORE `select(Client)` at line 182. |
| T-68-17 | Spoofing | mitigate | CLOSED | client_auth/service.py:495-528 — branch (C) issues `update(ClientRefreshToken)...values(revoked_at=now)` for whole family; audit.emit "client_family_reuse_detected" at line 506; raises `InvalidSession`. |
| T-68-18 | Denial | mitigate | CLOSED | client_auth/rate_limit.py:59-82 — `check_client_ip_rate` (5/900s), `check_client_otp_cooldown` (60s TTL key), `check_client_otp_daily` (5/86400s); all raise `RateLimited("rate_limited")`. |
| T-68-19 | Spoofing | mitigate | CLOSED | client_auth/service.py:318-327 — `if presented_hash != otp_row.code_hash: otp_row.attempts += 1; await session.commit(); if otp_row.attempts >= settings.otp_max_attempts: raise OtpMaxAttempts`. Code dies after attempt cap. |
| T-68-20 | Info disclosure | mitigate | CLOSED | client_auth/service.py:629-632 — `except IntegrityError: await session.rollback(); raise ConflictError("email_unavailable")`. Generic 409, no indication of which account holds the email. |
| T-68-21 | Elevation | mitigate | CLOSED | client_auth/service.py:138-140 — `auth:client:session:{client_id}:{family_id}` and `auth:client:user_sessions:{client_id}`. No `auth:session:` or `auth:user_sessions:` keys anywhere in the file (confirmed by grep). |
| T-68-22 | Info disclosure | mitigate | CLOSED | client_auth/router.py:54-74 — handler always calls `service.request_client_otp(...)` and returns `envelope(None)` with `status_code=202`. Fixed ResponseEnvelope[None] body for every phone state. |
| T-68-23 | Tampering | mitigate | CLOSED | client_auth/schemas.py:28 — `phone: str = Field(pattern=_PHONE_REGEX)` where `_PHONE_REGEX = r"^\+[1-9]\d{1,14}$"`. Pydantic raises 422 before any lookup. |
| T-68-24 | Spoofing | mitigate | CLOSED | client_auth/router.py:177 (`get_client_me`), 195 (`patch_client_me`), 153 (`client_session_logout`) all depend on `require_client()` → `get_current_client` → `decode_client_token` (aud assertion). Staff tokens → 401. |
| T-68-25 | Spoofing | mitigate | CLOSED | client_auth/router.py:153-154 — `_client: Depends(require_client())` declared before `_csrf: Depends(verify_client_csrf)` (RBAC-04 ordering). Same pattern at lines 195-196 for PATCH /me. |
| T-68-26 | Info disclosure | mitigate | CLOSED | main.py:248-249 — `"client_otp_request"` and `"client_otp_verify"` present in `PUBLIC_ENDPOINT_OPERATION_IDS` frozenset. router.py:58,81 — explicit `operation_id=` set on both OTP handlers. |
| T-68-27 | Info disclosure | mitigate | CLOSED | client_auth/schemas.py:38-53 — `ClientMeResponse` has exactly 8 fields: id/phone/email/first_name/last_name/middle_name/birthday/gender. No notes/tags/membership/created_by/emergency_contact fields. |
| T-68-28 | Spoofing | mitigate | CLOSED | test_otp_isolation.py:117-178 — `test_staff_token_rejected_by_client_endpoint` asserts 401; `test_client_token_rejected_by_staff_endpoint` asserts 401. Both directions covered. |
| T-68-29 | Info disclosure | mitigate | CLOSED | test_otp_isolation.py:181-265 — `test_otp_request_anti_oracle` parametrized over [linked_phone, unlinked_phone, unknown_phone, soft_deleted_phone]; each asserts 202. `test_otp_request_anti_oracle_body_parity` asserts `len(bodies) == 1` (byte-identical). |
| T-68-30 | Info disclosure | mitigate | CLOSED | test_idor.py:110-155 — `@pytest.mark.parametrize("attacker_is_a", [True, False])` covers both orderings; asserts `returned_id == str(attacker.id)` AND `!= str(victim.id)`. |
| T-68-31 | Elevation | mitigate | CLOSED | test_byte_parity.py:40-76 — `"CLIENT" not in Role.__members__`; source text has no "Role.CLIENT"; `[m.name for m in Role]` has no CLIENT. test_byte_parity.py:79-101 — ClientPrincipal annotations have no "role". test_byte_parity.py:104-147 — can.ts exists and has no "Role.CLIENT" or "| 'client'" patterns. |
| T-68-32 | Spoofing | mitigate | CLOSED | test_session_lifecycle.py:79-221 — `test_full_session_lifecycle`: verify issues 3 cookies; refresh rotates token (`new_refresh_token != refresh_token`); logout clears all 3; post-logout /me → 401. |

---

## Unregistered Flags

None. All SUMMARY.md `## Threat Flags` sections across plans 68-01 through 68-06
report no new threat surface beyond the registered threat model.

---

## Notable Deviation: T-68-01 Constraint Name and Expression

The threat register specifies `ck_otp_codes_principal_xor` with an XOR expression
`(user_id IS NULL) <> (client_id IS NULL)`. The implementation uses
`ck_otp_codes_principal_excl` (DB name resolves via SQLAlchemy naming convention to
`ck_otp_codes_principal_excl`) with expression
`NOT (user_id IS NOT NULL AND client_id IS NOT NULL)`.

The deviation was intentional and documented in 0043_client_auth_otp.py and
68-01-SUMMARY.md: the strict XOR would have rejected existing staff pre-bind OtpCode
rows where both user_id and client_id are NULL (the bot binds user_id at /telegram/verify,
not at /telegram/start). The corrected AT-MOST-ONE expression forbids dual-ownership
while permitting null/null pre-bind rows. The security function — preventing a single
row from being claimed by both a staff user and a client simultaneously — is fully
preserved.

This deviation does NOT constitute a gap. The mitigation is present and correct.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-29 | 32 | 32 | 0 | gsd-security-auditor (verify-mitigations mode, register authored at plan time) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer) — 30 mitigate, 2 accept
- [x] Accepted risks documented in Accepted Risks Log — T-68-04, T-68-09
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-29
