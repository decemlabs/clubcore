---
slug: client-checkout-no-commit
status: resolved
trigger: "Client checkout endpoints never commit the online_payments row — flush-only, rolled back on session close"
created: 2026-05-31
updated: 2026-05-31
---

# Debug Session: client-checkout-no-commit

## Symptoms

**Expected behavior:**
POST /api/v1/client/checkout/memberships/{plan_id} and /checkout/pt-packages/{plan_id} should persist an `online_payments` row (committed) when they return 201 with a ЮKassa confirmationUrl, so that (a) same-day replay returns the same confirmation_url (CPAY-05) and (b) the `payment.succeeded` webhook can find the row by `yookassa_payment_id` and activate the membership/PT-package.

**Actual behavior:**
Both endpoints return 201 + a real ЮKassa confirmationUrl, but `SELECT count(*) FROM online_payments` = 0. The row is flushed then rolled back on session close.

**Error messages / live SQL trace (PT checkout, docker compose logs backend):**
```
SELECT … FROM online_payments WHERE idempotency_key = $1   (replay check — empty)
yookassa_create_payment_ok  status=pending
INSERT INTO online_payments … RETURNING initiated_at
online_payment_initiated / yookassa_payment_created / online_payment_sell outcome=ok
ROLLBACK            ← never COMMIT
```
Downstream symptom: a 2nd membership checkout same-day → 502 `yookassa_permanent_error` (`error_code=invalid_request`, http 400 from ЮKassa) because the backend replay-check finds no row, re-sends the same server-derived per-day idempotency key with a fresh payment_id in return_url, and ЮKassa rejects the key reuse.

**Timeline:** Introduced in Phase 71 (plan 71-02, client checkout endpoints). Never worked end-to-end; masked until now because no live ЮKassa creds were wired.

**Reproduction:**
1. `cd apps/backend && docker compose up -d --force-recreate` (NOTE: `restart` does NOT reload .env; image lacks alembic/ + scripts/ — `docker compose cp scripts backend:/app/scripts`; DB already at head 0045 so start backend with `up -d --no-deps backend` to skip the failing migrate one-shot).
2. Login dev client: `POST /api/v1/client/otp/request` then `/client/otp/verify` {phone:"+79999999999", code:"111111"}; capture cookies + `clubcore_client_csrf`.
3. `POST /api/v1/client/checkout/pt-packages/{plan_id}` with `x-csrf-token` + `Idempotency-Key` headers.
4. Observe 201 + confirmationUrl, then `SELECT count(*) FROM online_payments` = 0.

## Root Cause (established pre-session — verify, then fix)

Commit-ownership gap on the client checkout endpoints:
- `_sell_subject_core` only `session.flush()`es — `apps/backend/app/modules/online_payments/service.py:331`; docstring (L26-27) assumes "FastAPI dependency commits on response".
- `get_db` NEVER commits — `apps/backend/app/core/database.py` (`async with session_factory() as session: yield session`; close rolls back).
- `client_portal` service checkout fns explicitly don't commit — `app/modules/client_portal/service.py:493,545` ("No session.commit() — caller-owns-txn D-32-10/D-49-19").
- Router endpoints `client_checkout_membership` (`app/modules/client_portal/router.py:564`) and `client_checkout_pt_package` (`router.py:599`) call the service and `return envelope(result)` — NO commit owner.
- Asymmetry: staff sell path commits via `idempotent_execute(...)` (`online_payments/router.py:154`); client booking POST commits via its `verify_client_idempotency` `_runner`. The two checkout endpoints have neither.

## Impact

- `online_payments` rows never persist.
- CPAY-05 replay/idempotency broken (membership same-day 2nd call → 502).
- `payment.succeeded` webhook (`handle_payment_succeeded`, `app/api/v1/_internal/yookassa/handlers.py`) looks up the row by `yookassa_payment_id` → finds nothing → no activation. Full CPAY round-trip non-functional.

## Test Gap Closed

Phase-71 integration tests passed because the SAVEPOINT harness + mocked ЮKassa made the flushed-but-uncommitted row visible within the same transaction, and the duplicate-key 400 never surfaced.

Two new regression tests added to `tests/integration/client_portal/test_checkout.py`:
- `test_membership_checkout_row_committed_to_db` — membership path; real-commit harness; fresh connection; asserts row visible after response.
- `test_pt_checkout_row_committed_to_db` — PT path; same harness.

Both tests use `checkout_commit_engine` / `checkout_commit_db_session` / `checkout_commit_client` fixtures (real BEGIN/COMMIT, fresh per-request sessions) added to `tests/integration/client_portal/conftest.py`.

## Resolution

- **Root cause:** Missing `await session.commit()` in `client_checkout_membership` and `client_checkout_pt_package` router endpoints. `get_db` yields a session that rolls back on close; the service only flushes; no caller owned the commit.
- **Fix:** Added `await session.commit()` after the service call in both endpoints (`apps/backend/app/modules/client_portal/router.py` lines 586, 628). Docstrings updated to note "Commit owner: caller-owns-txn (D-32-10/D-49-19); service only flushes."
- **Regression tests:** 2 new real-commit harness tests added. All 13 checkout tests pass (57/57 client_portal; 104/104 online_payments + webhook).

## Current Focus

- hypothesis: RESOLVED
- test: CLOSED
- expecting: online_payments rows committed; CPAY round-trip functional.
- next_action: Deploy and verify live with docker compose up -d --force-recreate.
