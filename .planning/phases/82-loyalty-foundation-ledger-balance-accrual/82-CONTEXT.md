# Phase 82: Loyalty Foundation — Ledger + Balance + Accrual - Context

**Gathered:** 2026-06-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver the loyalty/bonus foundation: an append-only `loyalty_ledger` from which a
client's bonus balance is derived (no destructive UPDATEs), a client-facing read API
for balance + history (IDOR-safe via `require_client()`), automatic one-time welcome
accrual for new clients, an owner-only backend grant API (no admin-web UI), and an
auditable LOCKED audit event on every accrual. Redemption (debit) rows are written in
Phase 83 — this phase only establishes the ledger + accrual side and reserves the
`redemption` entry_type.

</domain>

<decisions>
## Implementation Decisions

### Module & Ledger Schema
- New backend module `app/modules/loyalty/` (`models.py` + `service.py`), registered in `.importlinter` `modules-independent` contract — mirrors `app/modules/promo_codes/` precedent. Zero new `ignore_imports` where possible (D-20-MODULE).
- Ledger table `loyalty_ledger`, **append-only**: composition `Base + UUIDPkMixin` ONLY (no TimestampMixin, no SoftDeleteMixin) — single temporal column `created_at` (`server_default=func.now()`), mirroring `PromoRedemption` / `online_refunds` / `online_payments` single-temporal-column discipline.
- Amount stored as a **single signed** `amount_kopecks` BigInteger column: positive = accrual, negative = redemption. Balance = `SUM(amount_kopecks)` reduction over the ledger (LOYL-03 — balance is a fold of rows, never a stored mutable column).
- `entry_type` String column + CHECK constraint `IN ('welcome', 'owner_grant', 'redemption')`. The `redemption` value is reserved here; its row-writer lands in Phase 83.
- `client_id` RESTRICT FK → `clients.id` (promo_redemptions FK pattern). Index on `client_id` for balance/history fold.

### Welcome Accrual (ACCR-01)
- Trigger: emitted on `client_created` — the single deterministic creation point (`app/modules/clients/service.py` create_client, around line 134).
- Idempotency: DB-enforced via a **partial UNIQUE** index `(client_id) WHERE entry_type='welcome'` — one welcome row per client maximum (mirrors `uq_promo_codes_code_alive` partial-index pattern). Re-firing the creation event cannot double-credit.
- Amount source: module-level constant `WELCOME_BONUS_KOPECKS` in the loyalty module (no admin UI — seeded-promo-code precedent / D-999.4 lineage).
- Welcome amount value: **50000 kopecks (500 ₽)**.

### Owner-Grant API (ACCR-02)
- Endpoint: `POST /api/v1/clients/{client_id}/loyalty/grant` on the staff API surface.
- Authorization: **direct owner-role guard** — a thin dependency asserting the authenticated staff user's `role is Role.OWNER`. This intentionally does NOT extend the `OWNER_ONLY` frozenset or add a new `Resource`, so the Phase-6 backend↔frontend parity test and CISO-01 byte-parity guard stay green WITHOUT editing the frozen `apps/admin-web` `can.ts`. Reception → 403.
- Request shape: `{ amount_kopecks: int (>0), reason: str, category: 'promo' | 'referral' | 'manual' }`. Covers promotional + referral grants (referral program proper is deferred to v2.6 per REQUIREMENTS out-of-scope).
- Grants are **accrual-only** (`amount_kopecks > 0`, DB CHECK). Owner cannot create negative/deduction rows; the only debits are redemptions (Phase 83).

### Audit & Read API
- New LOCKED audit event `loyalty_accrued` with payload `{client_id, entry_id, amount_kopecks, entry_type, actor}`, `resource_type='loyalty'`. Registered in `LOCKED_AUDIT_EVENTS` (and `audit_payloads`) BEFORE any callsite per INFRA-15; the count-lock guard tests (`test_audit_taxonomy`, `test_locked_audit_events`, `test_phase51_audit_chain_invariants`) are bumped in the same change. A single event covers both welcome + owner_grant (distinguished by `entry_type`/`actor` in payload).
- Balance endpoint: `GET /api/v1/client/loyalty/balance` → `{ balanceKopecks: int }` (camelCase client schema). `client_id` sourced from `require_client()` principal only (D-20-IDOR).
- History endpoint: `GET /api/v1/client/loyalty/history` → project pagination contract `{ items, total, page, pageSize }`; each item `{ id, type, amountKopecks, createdAt }`. IDOR-safe via principal.
- Direction display: server returns the **signed** `amountKopecks` + `type`; the PWA derives +/− presentation (no separate server `direction` field).

### Claude's Discretion
- Exact pagination defaults (page size), index naming, schema/Pydantic model field ordering, and test file layout left to plan-phase, following established module conventions.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/modules/promo_codes/models.py` — `PromoRedemption` is the exact append-only ledger template (Base + UUIDPkMixin only, single `redeemed_at` temporal col, BigInteger kopecks, RESTRICT FKs, partial-UNIQUE + CHECK constraint naming-convention notes).
- `app/modules/promo_codes/service.py` — caller-owns-txn (no `session.commit()`), raw SQL `text()` reads, `pg_insert` for idempotent writes, distinct typed error classes.
- `app/core/audit.py` — `LOCKED_AUDIT_EVENTS` frozenset (source of truth) + `emit()` (async, caller-owns-txn, raises `AuditEventNotLockedError` for unregistered pairs). `app/core/audit_payloads.py` for payload schemas.
- `app/modules/client_portal/router.py` — `APIRouter(tags=["Client-Portal"])`, `client_` operationId prefix, `require_client()` dependency, raw-SQL reads via repository (D-54-08).
- `app/core/dependencies.py:1234` `require_client()`; `:812` `require_permission()`; `app/core/permissions.py` `Role` enum + `OWNER_ONLY`.

### Established Patterns
- Money = integer kopecks (BigInteger), no float/Decimal; percentage uses integer floor-div.
- Append-only ledgers: never UPDATE; balance/usage = SUM/COUNT fold via raw SQL.
- Audit discipline: register `(event, resource_type)` in `LOCKED_AUDIT_EVENTS` BEFORE callsite (INFRA-15); static AST walker `test_audit_taxonomy.py` + count-lock tests enforce at CI.
- Client endpoints: IDOR-safe, `client_id` from principal only, 404-collapse on non-owned (D-20-IDOR).
- New module → add to `.importlinter` `modules-independent`; zero new `ignore_imports` target (D-20-MODULE).

### Integration Points
- Welcome accrual callsite: `app/modules/clients/service.py` `create_client` (co-transactional with client insert + `client_created` audit emit).
- Client read endpoints mount under existing `client_portal` router (`/api/v1/client/...`).
- Owner-grant endpoint mounts on staff API (`clients` router or new loyalty staff router) under direct owner-role guard.
- Audit event registration in `app/core/audit.py` + `app/core/audit_payloads.py`; count-lock guard tests in `tests/unit/` + `tests/integration/`.

</code_context>

<specifics>
## Specific Ideas

- Welcome bonus = 500 ₽ (50000 kopecks), held in a module-level `WELCOME_BONUS_KOPECKS` constant (no admin UI this milestone).
- Owner-grant `category` enum: `'promo' | 'referral' | 'manual'` — referral here means a manual owner grant, NOT an automated referral program (deferred to v2.6).
- Reserve `entry_type='redemption'` now so Phase 83's webhook-locked debit writer needs no schema migration.

</specifics>

<deferred>
## Deferred Ideas

- Redemption (debit) row-writer + checkout balance control → Phase 83 (REDM-01..03).
- Full referral program (codes / history / auto-rewards) → milestone v2.6.
- admin-web loyalty UI → out of scope (admin-web frozen; owner grants via backend API only).
- Lifetime accrued/redeemed totals on the balance endpoint → not requested; can revisit if PWA design needs them.

</deferred>
