---
phase: 71
slug: client-checkout-full-pwa-screen-wiring
status: verified
threats_open: 0
asvs_level: 1
created: 2026-05-31
---

# Phase 71 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| client→API | Client JWT (`ClientPrincipal`) crosses on POST checkout + GET status | untrusted plan_id, payment_id, Idempotency-Key |
| service→ЮKassa | Server-authoritative price + receipt cross to payment provider | amount (kopecks), client email (54-ФЗ receipt) |
| webhook→activation | `payment.succeeded` → activation seam | provider event, payment_id |
| PWA→client API | React Query hooks via clientFetcher; cookies (cc_client_*) carry session | session cookie, idempotency keys |
| PWA→ЮKassa redirect | Client leaves to confirmation_url, returns to /payment/return | idempotency_key in return_url query |
| net-new screens→query layer | Structurally forbidden boundary (D-71-09) | none (ESLint-barred) |
| backend→generated schema | openapi.json is trusted contract; schema.d.ts derived, never hand-edited | API surface contract |
| service worker ↔ HTTP cache | SW could persist authed per-client /api payloads into Cache Storage | per-client authed JSON |
| /client/me cache ↔ rendered identity | PWA renders authenticated client identity | client name/email/phone |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-71-01 | Tampering | `_sell_subject_core` price read | mitigate | Price read server-side via `_read_*_plan_or_raise`; no amount param — `service.py:282-286` | closed |
| T-71-02 | Elevation | `created_by_user_id=NULL` client path | mitigate | `actor_user_id=None` via audit system-emit path (D-41-10); no fake staff UUID — `service.py:326,345,362` | closed |
| T-71-03 | Repudiation | audit chain on client checkout | mitigate | ROOT + CHILD audit emits share correlation_id + client-aware actor — `service.py:342-366` | closed |
| T-71-04 | Tampering | staff contract drift via refactor | mitigate | Staff signatures + SellResponse unchanged; thin wrappers delegate to core — `service.py:396-455` | closed |
| T-71-05 | Information Disclosure | `GET /payments/{id}/status` | mitigate | Mandatory `:client_id` filter + NotFoundError 404-collapse; SELECT id,status only — `repository.py:511-519`, `service.py:593-594` | closed |
| T-71-06 | Tampering | checkout amount | mitigate | Body schema empty; only path plan_id + header key — `router.py:564-625` | closed |
| T-71-07 | DoS/double-charge | PT-package repeat submit | mitigate | Client Idempotency-Key passed to core replay check — `router.py:604`, `service.py:563` | closed |
| T-71-08 | DoS/double-charge | membership repeat submit | mitigate | Server-derived per-day SHA256 key → replay returns same confirmation_url — `service.py:466-478,503` | closed |
| T-71-09 | Spoofing | CSRF on state-changing POST | mitigate | `verify_client_csrf` on both POSTs; GET status safe-method — `router.py:568,603,638` | closed |
| T-71-10 | Tampering | 54-ФЗ fiscal bypass | mitigate | Email gate raises `ClientEmailRequiredForOnlinePaymentError` → 422 — `service.py:279` | closed |
| T-71-11 | Information Disclosure | status endpoint surface | mitigate | Test asserts keys exactly {id,status} — `test_checkout.py:509-513` | closed |
| T-71-12 | Elevation/IDOR | cross-client status read | mitigate | Test: client A → 404 on client B payment — `test_checkout.py:558-562` | closed |
| T-71-13 | Tampering/replay | duplicate webhook | mitigate | Test delivers payment.succeeded twice, asserts single activation — `test_checkout.py:565+` | closed |
| T-71-14 | Tampering | 54-ФЗ bypass | mitigate | Test asserts 422 `client_email_required_for_online_payment` — `test_checkout.py:455-458` | closed |
| T-71-15 | Information Disclosure | net-new screens calling /api/* | mitigate | ESLint `no-restricted-paths` bars 5 screens; ComingSoon-only — `eslint.config.js:65-111` | closed |
| T-71-16 | Information Disclosure | stale authed data in SW cache | accept | SW `/api/*` network-only (D-69-08); no `/api/*` cache.put added | closed |
| T-71-17 | Spoofing | expired session reuse | mitigate | session-expiry → authBus → AuthContext invalidates cache + redirect — `queryClient.ts:27-37`, `AuthContext.jsx:69-76` | closed |
| T-71-18 | Information Disclosure | premature activation display | mitigate | Navigate Home only on `status==='succeeded'`; pending shows wait msg — `PaymentReturnScreen.jsx:43-53` | closed |
| T-71-19 | Information Disclosure | net-new screen backend calls | mitigate | Same control as T-71-15 (ESLint boundary + ComingSoon) | closed |
| T-71-20 | Tampering | checkout amount from client | mitigate | CheckoutSheet sends only planId (+ PT idem key) — `CheckoutSheet.jsx:73,82-88` | closed |
| T-71-21 | DoS/double-charge | PT retry after redirect | mitigate | `crypto.randomUUID()` once per intent, carried via return_url query (D-71-04, no localStorage) — `CheckoutSheet.jsx:31-33` | closed |
| T-71-22 | Tampering | hand-edited schema.d.ts drift | mitigate | Regenerated from live openapi.json via codegen; staff paths byte-identical — `schema.d.ts:2892-2948` | closed |
| T-71-26 | Tampering/replay | QR token replay | mitigate | Short-lived signed JWT (Phase 70); PWA displays only, refreshes before TTL — `clientQueries.ts:330-340` | closed |
| T-71-27 | DoS/double-book | duplicate booking submit | mitigate | Per-intent Idempotency-Key; server UNIQUE arbiter 409 on race — `clientQueries.ts:265-294` | closed |
| T-71-28 | Information Disclosure | cross-client booking access | mitigate | Server IDOR-safe (Phase 70); PWA reads own bookings via session cookie only | closed |
| T-71-29 | Spoofing | booking without PT-package | mitigate | `no_active_pt_package` routes to Plans/Checkout, no raw error leak — `BookScreen.jsx:206-211` | closed |
| T-71-08-01 | Information Disclosure | sw.js caching /api/* | mitigate | `pathname.startsWith('/api/')` → `fetch(req)`; zero cache.put — `sw.js:40-43` | closed |
| T-71-08-02 | Tampering (stale) | gym-v2 cache holding stale /api/* | mitigate | VERSION bumped gym-v3; activate evicts non-VERSION caches — `sw.js:4,22-28` | closed |
| T-71-08-SC | Tampering | npm installs | accept | No package installs; sw.js + pwa.js edits only | closed |
| T-71-09-01 | Information Disclosure | seed_demo_data dev catalog | accept | Dev/local-only seed; non-sensitive fixture prices; owner creds from env var | closed |
| T-71-09-02 | Tampering (data integrity) | adapter field rename | mitigate | camelCase reads only; no snake_case API field reads remain — `PlansSheet.jsx`, `ProfileScreen.jsx` | closed |
| T-71-09-SC | Tampering | npm/pip installs | accept | No package installs; JSX adapter + one Python seed edit | closed |
| T-71-10-01 | Information Disclosure | useClientMe cached read | mitigate | `clientPortalKeys.me()` invalidated on session-expiry + logout; no new persistence — `HomeScreen.jsx:94,103`, `AuthContext.jsx:73` | closed |
| T-71-10-02 | Spoofing | hardcoded mock identity | mitigate | Hardcoded literals removed; bound to /client/me — `ProfileScreen.jsx:60-63` | closed |
| T-71-10-SC | Tampering | npm installs | accept | No package installs; JSX edits only | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-71-01 | T-71-16 | SW `/api/*` network-only guard shipped Phase 69 (D-69-08); Phase 71 adds no `/api/*` cache writes — verified no `cache.put` for `/api/` in sw.js | Andre | 2026-05-31 |
| AR-71-02 | T-71-08-SC | Plan 71-08 scope = sw.js + pwa.js edits only; no new package.json entries | Andre | 2026-05-31 |
| AR-71-03 | T-71-09-01 | `seed_demo_data.py` is local-only dev seed; non-sensitive fixture prices; owner creds from `SEED_OWNER_PASSWORD` env (not hardcoded); idempotent ON CONFLICT | Andre | 2026-05-31 |
| AR-71-04 | T-71-09-SC | Plan 71-09 scope = JSX adapter edits + one Python seed edit; no new dependency entries | Andre | 2026-05-31 |
| AR-71-05 | T-71-10-SC | Plan 71-10 scope = JSX edits only (HomeScreen/ProfileScreen); no package installs | Andre | 2026-05-31 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-31 | 35 | 35 | 0 | gsd-security-auditor (claude-sonnet-4-6) |

**Notes:**
- T-71-17 implemented via `publishSessionExpired()` → authBus → AuthContext `<Navigate>` rather than the originally specced `window.location.replace('/login')`. The implementation is strictly stronger (no full-page reload loop risk) — CLOSED on the stronger control.
- `_sell_subject_core` added optional `online_payment_id_override` / `return_url_override` params (CR-01/CR-02 fix) with `None` defaults; staff path byte-identical — additive hardening, not a regression.
- T-71-28 is partly a Phase 70 server-side invariant; Phase 71 PWA-layer verification confirms the PWA passes only the session cookie and reads own bookings.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-31
