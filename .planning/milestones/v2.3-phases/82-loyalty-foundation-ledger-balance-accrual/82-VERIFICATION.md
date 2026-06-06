---
phase: 82-loyalty-foundation-ledger-balance-accrual
verified: 2026-06-05T00:00:00Z
status: passed
score: 6/6 must-haves verified
overrides_applied: 0
---

# Phase 82: Loyalty Foundation — Ledger, Balance, Accrual Verification Report

**Phase Goal:** Клиент имеет бонусный баланс, выведенный из append-only ledger, видит его и историю; бонусы начисляются автоматически новому клиенту и вручную owner'ом через backend API; каждое начисление аудируется.
**Verified:** 2026-06-05T00:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | LOYL-01: GET /api/v1/client/loyalty/balance returns {balanceKopecks} = SUM fold, IDOR-safe | ✓ VERIFIED | `apps/backend/app/modules/loyalty/router.py` operation_id=`client_get_loyalty_balance`, `require_client()` principal only; service uses raw SQL `COALESCE(SUM(amount_kopecks), 0)`; no URL client_id param |
| 2 | LOYL-02: GET /api/v1/client/loyalty/history returns paginated signed ledger rows, IDOR-safe | ✓ VERIFIED | `router.py` operation_id=`client_list_loyalty_history`, `require_client()` principal gated; service returns `PaginatedData[ClientLoyaltyHistoryItem]` with signed `amount_kopecks`, DESC order, LIMIT/OFFSET |
| 3 | LOYL-03: balance derived from append-only loyalty_ledger — SUM fold, no destructive UPDATE | ✓ VERIFIED | `models.py`: `Base + UUIDPkMixin` only (no TimestampMixin/SoftDeleteMixin), single `created_at`; `service.py` `_sum_balance()` uses raw SQL SUM fold; migration 0054 creates table without UPDATE triggers; no UPDATE path exists in service |
| 4 | ACCR-01: new client receives exactly one welcome bonus of 50000 kopecks, idempotent on replay | ✓ VERIFIED | `clients/service.py` line 148: `await loyalty_service.accrue_welcome_bonus(session, client_id=client.id)` placed after `client_created` audit emit, before `session.commit()`; `service.py` uses `pg_insert(LoyaltyLedger).on_conflict_do_nothing(index_elements=["client_id"], index_where=text("entry_type = 'welcome'")).returning(LoyaltyLedger.id)`; `WELCOME_BONUS_KOPECKS: int = 50_000`; partial UNIQUE index `uq_loyalty_ledger_welcome` in migration 0054; `test_loyalty_accrual.py` proves idempotency |
| 5 | ACCR-02: owner-only POST /api/v1/clients/{client_id}/loyalty/grant; reception gets 403 | ✓ VERIFIED | `clients/router.py` line 140-163: `/{client_id}/loyalty/grant` POST, status 201, RBAC-04 order (require_owner_for_loyalty_grant → verify_csrf → get_db); `permissions.py` checks `user.role is Role.OWNER`, emits `rbac_forbidden` + raises `ForbiddenError` for non-owner; `test_loyalty_grant.py` covers 201/owner, 403/reception, 422/non-positive, 404/unknown |
| 6 | ACCR-03: every accrual writes loyalty_accrued LOCKED audit event, registered before callsite | ✓ VERIFIED | `audit.py` line 462: `("loyalty_accrued", "loyalty")` in `LOCKED_AUDIT_EVENTS` frozenset (count-lock guards at 102 in both test files); `audit_payloads.py` line 1273-1291: `LoyaltyAccruedPayload(extra="forbid")` with `entry_type: Literal["welcome", "owner_grant"]`; `service.py`: welcome emits audit only on real insert (RETURNING gate); owner_grant always emits; co-transactional (before commit in router) |

**Score:** 6/6 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/app/modules/loyalty/__init__.py` | Package marker | ✓ VERIFIED | Exists |
| `apps/backend/app/modules/loyalty/models.py` | LoyaltyLedger ORM model | ✓ VERIFIED | `class LoyaltyLedger(Base, UUIDPkMixin)`, append-only, signed `amount_kopecks` BigInteger, `entry_type` CHECK, single `created_at`, RESTRICT FK |
| `apps/backend/alembic/versions/0054_loyalty_ledger.py` | loyalty_ledger DDL migration | ✓ VERIFIED | `down_revision="0053_booking_notif_widen_kind_rescheduled"`, creates table, partial UNIQUE `uq_loyalty_ledger_welcome`, plain `ix_loyalty_ledger_client_id` |
| `apps/backend/app/core/audit_payloads.py` | LoyaltyAccruedPayload + registry entry | ✓ VERIFIED | Line 1273: `class LoyaltyAccruedPayload(BaseModel)`, `extra="forbid"`, `entry_type: Literal["welcome", "owner_grant"]`; line 1389: registry entry |
| `apps/backend/app/modules/loyalty/service.py` | accrue_welcome_bonus, owner_grant_loyalty, get_client_loyalty_balance, list_client_loyalty_history | ✓ VERIFIED | All four functions present; `WELCOME_BONUS_KOPECKS: int = 50_000`; 0 actual `session.commit()` calls (only in module docstring); raw SQL for reads (D-54-08) |
| `apps/backend/app/modules/loyalty/permissions.py` | require_owner_for_loyalty_grant | ✓ VERIFIED | Owner short-circuits; non-owner emits `rbac_forbidden` + raises `ForbiddenError`; does NOT extend OWNER_ONLY or add Resource |
| `apps/backend/app/modules/loyalty/router.py` | client balance/history read endpoints | ✓ VERIFIED | `client_get_loyalty_balance` + `client_list_loyalty_history`, both gated by `require_client()`, no URL client_id |
| `apps/backend/app/modules/loyalty/schemas.py` | Response/request schemas | ✓ VERIFIED | `ClientLoyaltyBalanceResponse`, `ClientLoyaltyHistoryItem`, `ClientLoyaltyGrantResponse`, `LoyaltyGrantRequest` (extra=forbid) |
| `apps/backend/tests/unit/test_loyalty_audit_events.py` | Audit registry tests (3 groups) | ✓ VERIFIED | 5 tests: locked event, welcome/owner_grant payload validates, extra fields rejected, redemption rejected, schema registry entry |
| `apps/backend/tests/integration/test_loyalty_accrual.py` | Welcome idempotency tests (ACCR-01/03) | ✓ VERIFIED | 3 tests: 1 welcome row, 1 audit row, idempotent replay |
| `apps/backend/tests/integration/test_loyalty_grant.py` | Owner-grant RBAC tests (ACCR-02/03) | ✓ VERIFIED | 7 tests: 201/owner, 403/reception+rbac_audit, 422/zero, 422/negative, 404/unknown |
| `apps/backend/tests/integration/test_loyalty_read.py` | IDOR + pagination tests (LOYL-01/02) | ✓ VERIFIED | 10 tests including IDOR isolation, empty=200/0, pagination |
| `apps/client-pwa/src/lib/clientQueries.ts` | useClientLoyaltyBalance + useClientLoyaltyHistory hooks | ✓ VERIFIED | Lines 765-788: both hooks, `clientPortalKeys.loyaltyBalance()` + `.loyaltyHistory(page)`, staleTime 30_000 |
| `apps/client-pwa/src/data/index.js` | Hook re-exports | ✓ VERIFIED | Lines 54-55: both hooks re-exported |
| `apps/client-pwa/src/screens/sheets/LoyaltySheet.jsx` | LoyaltyBalanceCard + BonusHistorySheet | ✓ VERIFIED | Both exported; `formatMoney(Math.abs(...))` for amounts; no manual kopeck division; U+2212 minus for redemptions; empty state "Бонусов пока нет"; load-more pagination; error → null (silent hide) |
| `apps/client-pwa/src/screens/ProfileScreen.jsx` | clubBonuses flag + card mount | ✓ VERIFIED | `clubBonuses: true` in `PROFILE_FEATURE_FLAGS`; `LoyaltyBalanceCard` + `BonusHistorySheet` conditionally rendered; state `bonusHistoryOpen` |
| `apps/client-pwa/src/screens/sheets/LoyaltySheet.test.jsx` | 10 Vitest behavior tests | ✓ VERIFIED | Balance render, loading skeleton, error hide, welcome row (+prefix), redemption row (U+2212), empty state, load-more presence, page advance |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `alembic/env.py` | `app.modules.loyalty.models` | import for Base.metadata | ✓ WIRED | Line 44: `import app.modules.loyalty.models  # Phase 82 LOYL-03 / 0054` |
| `.importlinter` | `app.modules.loyalty` | modules-independent contract | ✓ WIRED | Line 53: `app.modules.loyalty` listed; 4 ignore_imports edges for clients→loyalty |
| `clients/service.py` | `loyalty.service.accrue_welcome_bonus` | co-transactional call in create_client | ✓ WIRED | Line 148: after `client_created` audit emit, before `session.commit()` |
| `app/api/v1/router.py` | `loyalty.router` | include_router at /client | ✓ WIRED | Line 111: `v1.include_router(loyalty_router, prefix="/client")` |
| `clients/router.py` | `loyalty.permissions.require_owner_for_loyalty_grant` | grant endpoint dependency | ✓ WIRED | Line 50: imported; line 150: used as `Depends(require_owner_for_loyalty_grant())` |
| `LoyaltySheet.jsx` | `useClientLoyaltyBalance` / `useClientLoyaltyHistory` | import from @/data | ✓ WIRED | Line 18: `import { useClientLoyaltyBalance, useClientLoyaltyHistory } from '@/data'`; both used in components |
| `ProfileScreen.jsx` | `LoyaltyBalanceCard` | clubBonuses-flagged render | ✓ WIRED | Line 307-309: `{PROFILE_FEATURE_FLAGS.clubBonuses && <LoyaltyBalanceCard onOpen={...} />}` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `router.py` `client_get_loyalty_balance` | `result` from service | `service._sum_balance()` → raw SQL `COALESCE(SUM(amount_kopecks), 0) FROM loyalty_ledger` | Yes — DB query | ✓ FLOWING |
| `router.py` `client_list_loyalty_history` | `page` from service | `service.list_client_loyalty_history()` → raw SQL COUNT + SELECT with LIMIT/OFFSET | Yes — DB query | ✓ FLOWING |
| `LoyaltyBalanceCard` | `data.balanceKopecks` | `useClientLoyaltyBalance()` → `clientRequest('get', '/api/v1/client/loyalty/balance')` → real API endpoint | Yes — API call to real backend endpoint | ✓ FLOWING |
| `BonusHistorySheet` | `historyData.items` | `useClientLoyaltyHistory(page)` → `clientRequest('get', '/api/v1/client/loyalty/history')` → real API endpoint | Yes — API call with real pagination | ✓ FLOWING |

### Behavioral Spot-Checks

Step 7b: SKIPPED — backend requires live DB (ASGITransport tests require running postgres); PWA requires dev server. Both are covered by green test suites documented in the orchestrator gate sweep (pytest 2539 passed, vitest 141/141).

### Probe Execution

Step 7c: No `probe-*.sh` files declared in PLAN files or found under `scripts/*/tests/`. SKIPPED.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| LOYL-01 | 82-02-PLAN | Клиент видит бонусный баланс через GET /client/loyalty/balance | ✓ SATISFIED | `router.py` `client_get_loyalty_balance` endpoint; SUM fold in service; IDOR-safe |
| LOYL-02 | 82-02-PLAN | Клиент видит историю бонусов с датой, типом и суммой | ✓ SATISFIED | `router.py` `client_list_loyalty_history`; paginated `{items,total,page,pageSize}`; signed `amountKopecks` + `createdAt` + `type` |
| LOYL-03 | 82-01-PLAN | Баланс выводится из append-only ledger; без деструктивных UPDATE | ✓ SATISFIED | `models.py` append-only ORM; migration 0054; `_sum_balance()` raw SQL SUM fold; no UPDATE path exists |
| ACCR-01 | 82-02-PLAN | Новый клиент получает приветственный бонус one-time идемпотентно | ✓ SATISFIED | `clients/service.py` welcome callsite; partial UNIQUE + RETURNING gate; idempotency test proves no double-credit |
| ACCR-02 | 82-02-PLAN | Owner начисляет бонус вручную через owner-only backend API | ✓ SATISFIED | `POST /api/v1/clients/{client_id}/loyalty/grant`; `require_owner_for_loyalty_grant`; reception 403; admin-web untouched |
| ACCR-03 | 82-01-PLAN | Каждое начисление пишется как LOCKED audit event, зарегистрирован до callsite | ✓ SATISFIED | `("loyalty_accrued","loyalty")` in `LOCKED_AUDIT_EVENTS` (line 462 of audit.py); count-lock 102 in both guard files; co-transactional emit in service |

### Anti-Patterns Found

No blockers or warnings found.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `service.py` | 3 | `session.commit` in module docstring comment only | ℹ️ Info | NOT an actual call; docstring states caller-owns-txn discipline; grep returns 1 (docstring only) |

Scanned files for TBD/FIXME/XXX/TODO/HACK/PLACEHOLDER/empty returns:
- No `TBD`, `FIXME`, `XXX` markers in any loyalty module file
- No `return null` / `return {}` / `return []` stub patterns in backend service
- `LoyaltySheet.jsx` `return null` on error is intentional silent-hide pattern (CardSheet pattern, not a stub)
- No manual kopeck division (`amountKopecks / 100` or `balanceKopecks / 100`) confirmed absent
- `CheckoutSheet.jsx` `BONUS_PLACEHOLDER` confirmed untouched (Phase 83 scope)
- `admin-web` confirmed untouched (zero loyalty-related commits)
- `OWNER_ONLY` frozenset, `can.ts`, `registry.ts` confirmed unmodified

### Human Verification Required

None identified. All behaviors are fully covered by:
- 20 backend integration tests (ASGITransport, no real network)
- 5 unit tests for audit registry
- 10 PWA Vitest component tests
- Static analysis (mypy strict, ruff, tsc --noEmit, lint-imports)

The PWA UI visual appearance (card layout, colors, animation) is intentionally not verified here as it requires a live device/browser, but no test failures or stub patterns indicate risk.

### Gaps Summary

No gaps found. All 6 requirements (LOYL-01/02/03, ACCR-01/02/03) are fully implemented, wired, and covered by passing tests.

---

_Verified: 2026-06-05T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
