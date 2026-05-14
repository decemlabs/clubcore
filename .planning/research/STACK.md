# Stack — v1.4 Cash Sales + PT Packages

**Project:** Sportzal
**Milestone:** v1.4 — Cash Sales + PT Packages (subsequent milestone)
**Researched:** 2026-05-14
**Overall confidence:** HIGH (existing stack covers v1.4 fully; recommendation is "no new libraries")

---

## Recommendation Summary

- **No new backend runtime libraries.** Existing FastAPI 0.115 / SQLAlchemy 2.0 async / Alembic / Pydantic v2 / asyncpg / structlog stack covers payments, refunds, trainers, PT packages, PT sessions end-to-end. Add domain models + endpoints, not dependencies.
- **No new frontend runtime libraries.** shadcn/ui + Radix + TanStack Query/Router + react-hook-form + Zod cover sale-with-payment, refund confirmation, trainers CRUD, PT session recording UI without exception. Reuse the existing `formatMoney(minor)` / `StatusBadge` / mutation hook patterns from v1.3.
- **Money: stay with `INTEGER` kopecks** column type + Pydantic v2 `int` field + `formatMoney(minor)` on the frontend. **Do NOT introduce `py-moneyed`, `python-money`, `Decimal`, or `Numeric(18,4)`.** This is consistent with v1.2 mandatory snapshot pricing (`price_kopecks_snapshot INTEGER NOT NULL`) and is the locked Sportzal convention. RUB is single-currency; minor units are exact; integer math is race-safe and trivial for refunds.
- **PT packages: separate table `pt_packages` + new plan kind `pt_package` on the existing `membership_plans` catalog.** Do NOT bolt a `session_count_remaining` column onto `memberships`. PT packages have different lifecycle (no `end_date` semantics, no freeze, no expiring-soon DM, balance-decrement instead of date-based resolver). A separate table keeps the freeze / renewal / resolver / cron code paths from acquiring `if kind == pt_package` branches.
- **Trainers: single `trainers` table.** No FSM, no role, no `Trainer` user account. Owner-only CRUD endpoints mirror the `membership_plans` pattern (v1.2 Phase 16).
- **Refunds: domain logic, not a library.** A refund is an audit-emitting service method that (a) inserts a negative-amount payment row linked to the original payment, (b) transitions the related membership / pt_package to `status='refunded'` via the existing `_assert_can_transition` central guard, (c) writes a `LOCKED_AUDIT_EVENTS` entry. **Do NOT introduce `transitions`, `python-statemachine`, or any FSM library** — the v1.3 `MEMBERSHIP_STATUS_TRANSITIONS` declarative-constant pattern is the precedent and works.
- **Architectural placement:** new logic lives in **two new modules** — `app/modules/payments/` (cash ledger + refund) and `app/modules/trainers/` (catalog + PT session recording, OR a third dedicated module). PT-package model lives next to `memberships` (likely `app/modules/memberships/pt_packages_*`) OR a third module `app/modules/pt_packages/`. Roadmapper picks the split — both respect `modules-independent` import-linter contract via Protocol/composition-root callbacks (precedent: `ActiveMembershipResolver`, `register_user_loader`).

---

## Backend additions

### Runtime dependencies — ZERO new packages

Every v1.4 capability composes from libraries already pinned in `apps/backend/pyproject.toml`:

| Capability | Existing tool | Why no new dep |
|---|---|---|
| Cash payment ledger schema | SQLAlchemy 2.0 async + Alembic | `payments` table is a plain ORM model (`Integer` kopecks; FK to `clients` + nullable FKs to `memberships` and `pt_packages`; CHECK `amount_kopecks != 0`; `method TEXT NOT NULL DEFAULT 'cash'`). |
| Refund row | Same `payments` table | A refund is a row with `kind='refund'` and `amount_kopecks < 0` linked to the original `payment_id` via self-FK. No FSM library — service method + central transition guard on the related membership / pt_package. |
| Trainer catalog | SQLAlchemy + Alembic | `trainers` table with `UUIDPkMixin` + `TimestampMixin` + `SoftDeleteMixin` (mirrors `clients` and `membership_plans`). `lower(name)` partial unique on `WHERE deleted_at IS NULL`. |
| PT package plan kind | SQLAlchemy CHECK constraint | Extend `membership_plans.kind` Postgres CHECK to `('duration', 'pt_package')`; add nullable `session_count INTEGER CHECK (session_count > 0)`; service-layer assertion that `pt_package` plans have `session_count NOT NULL` and `duration_days IS NULL` (and vice versa). |
| PT package instance | SQLAlchemy + Alembic | New `pt_packages` table (separate from `memberships`): `id`, `client_id` FK, `plan_id` FK ON DELETE RESTRICT, `plan_name_snapshot`, `price_kopecks_snapshot`, `session_count_snapshot`, `sessions_remaining`, `status` ('active', 'depleted', 'cancelled', 'refunded'), `purchased_at`, audit columns. **No `end_date`, no freeze, no expiring-soon DM.** |
| PT session recording | SQLAlchemy + Alembic | `pt_sessions` table: `id`, `pt_package_id` FK ON DELETE RESTRICT, `trainer_id` FK ON DELETE RESTRICT, `client_id` FK (denormalised for query speed), `occurred_at TIMESTAMPTZ NOT NULL`, `created_by_user_id` FK to `users`. Decrement happens in service via `UPDATE pt_packages SET sessions_remaining = sessions_remaining - 1 WHERE id=:id AND sessions_remaining > 0 RETURNING sessions_remaining` (DB-level race-safe, same pattern as `visits` uniqueness — Postgres wins races, not the app). |
| Money handling | Python `int` + Pydantic v2 `int` field + Postgres `INTEGER` | Mirrors v1.2/v1.3 `price_kopecks_snapshot`. Integer math; no float; no Decimal; refunds are negative integers; sums use `SUM(amount_kopecks)` (Postgres `bigint` accumulator handles it). |
| Audit trail | Existing `audit_log` table + `LOCKED_AUDIT_EVENTS` frozenset | Pre-register new events in Phase A of v1.4: `payment_recorded`, `payment_refunded`, `trainer_created`, `trainer_updated`, `trainer_deleted`, `pt_package_sold`, `pt_package_cancelled`, `pt_package_refunded`, `pt_session_recorded`. AST commit-gate already covers `audit.emit` literal strings. |
| RBAC for new endpoints | Existing `Resource` + `Action` StrEnums + `OWNER_ONLY` frozenset | Add `Resource.PAYMENTS`, `Resource.TRAINERS`, `Resource.PT_PACKAGES`, `Resource.PT_SESSIONS` and `Action.REFUND`. Reception gets `(CREATE, PAYMENTS)` + `(REFUND, PAYMENTS)` + `(CREATE, PT_PACKAGES)` + `(CREATE, PT_SESSIONS)`. Owner-only: trainer mutations + payment list across all clients. Three-way parity test (backend ↔ admin-web `can.ts` ↔ test snapshot) already exists. |
| CSRF / cookie auth | Existing `CSRFCookie` dependency | Every new POST/PATCH/DELETE inherits `Depends(csrf_required)` via router-level dependency. |
| Pagination | Existing `Page[T]` envelope | `/api/v1/payments?clientId=...` and `/api/v1/trainers` return `{items, total, page, pageSize}` — same shape as v1.3. |
| OpenAPI drift gate | Existing `export_openapi.py` + CI gate | Regenerate `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts` once, both byte-stable; CI fails the milestone if drift slips in unsigned. |
| Testing | pytest-asyncio + httpx ASGITransport + SAVEPOINT isolation + VIS-TEST-01-style real-Postgres concurrent race test | Reuse for PT-session-decrement race ("two receptionists log the same PT click at the same moment — Postgres rejects the second `UPDATE … WHERE sessions_remaining > 0`"). |

### Library decisions — verified rejected

| Candidate | Status | Reason |
|---|---|---|
| `py-moneyed` / `python-money` | REJECT | Adds a `Money` class wrapping `(amount: Decimal, currency: str)`. Sportzal is single-currency RUB; the kopecks integer convention is already locked and works through the v1.0–v1.3 stack including Pydantic serialisation, JSON wire format (`priceKopecks`), and frontend `formatMoney(minor)`. Introducing `Money` here would force a full migration of `price_kopecks_snapshot` (4+ callsites in memberships alone) for zero functional gain. |
| `Decimal` / SQLAlchemy `Numeric(18,4)` | REJECT | Solves a problem we don't have (multi-currency, fractional minor units). Kopecks are exact integers. Sums of integers in Postgres are race-safe and overflow-impossible at our scale (1 zal × years of history fits in `int8`). |
| Native Postgres `MONEY` type | REJECT | Locale-sensitive; SQLAlchemy issue #5965 confirms it returns formatted strings depending on driver; community consensus across SQLAlchemy mailing list and PostgreSQL official docs is "don't use it for portable money handling". |
| `transitions` / `python-statemachine` | REJECT | v1.3 already proved declarative `MEMBERSHIP_STATUS_TRANSITIONS: dict[Status, frozenset[Status]]` + `_assert_can_transition()` is enough — grep-able, unit-testable, no runtime dependency. PT package status transitions (`active → depleted | cancelled | refunded`) get the same pattern in a `PT_PACKAGE_STATUS_TRANSITIONS` constant. |
| `python-fsm` / `automat` | REJECT | Same as above. |
| `sqlalchemy-utils` `MoneyType` | REJECT | Pulls a 30-utility-class dependency for one type. Plain `Integer` column wins. |
| ARQ scheduled job for "deplete PT package on `sessions_remaining = 0`" | REJECT | Status transition happens **synchronously** inside the PT-session-recording service when the `UPDATE … RETURNING sessions_remaining` returns 0. No cron needed — refusing to over-charge is enforced by the `WHERE sessions_remaining > 0` predicate, not by a scheduled sweeper. |
| Event-sourcing framework (`eventsourcing`, etc.) | REJECT | Audit log + payment ledger are append-only by convention; we don't need event-sourcing machinery. The `LOCKED_AUDIT_EVENTS` + service-write commit-gate already gives audit traceability. |
| `pydantic-extra-types` Money / Currency | REJECT | Same single-currency reason; no benefit over plain `int`. |

### New `Resource` and `Action` enum values

```python
# app/core/rbac.py — additions (no new dep)
class Resource(StrEnum):
    # ... existing ...
    PAYMENTS = "payments"
    TRAINERS = "trainers"
    PT_PACKAGES = "pt_packages"
    PT_SESSIONS = "pt_sessions"

class Action(StrEnum):
    # ... existing ...
    REFUND = "refund"

# OWNER_ONLY frozenset additions (best-guess — roadmapper to lock):
#   (CREATE, TRAINERS), (UPDATE, TRAINERS), (DELETE, TRAINERS), (LIST, TRAINERS)
# Reception keeps: (CREATE, PAYMENTS), (REFUND, PAYMENTS),
#                   (CREATE, PT_PACKAGES), (CREATE, PT_SESSIONS),
#                   (LIST, PT_PACKAGES), (LIST, PT_SESSIONS)
```

### New `LOCKED_AUDIT_EVENTS` (must be pre-registered in Phase A of v1.4)

```
payment_recorded, payment_refunded,
trainer_created, trainer_updated, trainer_deleted,
pt_package_sold, pt_package_cancelled, pt_package_refunded,
pt_session_recorded
```

That brings the frozenset to ~43 entries (34 v1.3 + 9 v1.4). Pre-registration pattern locked in v1.3 Phase 24 / INFRA-15.

### Alembic migrations (estimate)

- `0010_payments` — `payments` table (FKs, indexes including `(client_id, purchased_at DESC)` + `(method, purchased_at)` for v1.5 reports forward-seam).
- `0011_trainers` — `trainers` table with `lower(name)` partial unique on `WHERE deleted_at IS NULL`.
- `0012_pt_packages` — extend `membership_plans.kind` CHECK + add `session_count` nullable; add `pt_packages` table.
- `0013_pt_sessions` — `pt_sessions` table with indexes on `(pt_package_id, occurred_at DESC)` and `(trainer_id, occurred_at DESC)`.

(Roadmapper may merge or split. The migration discipline from v1.0–v1.3 — naming convention, async env.py — is already locked.)

### Import-linter contracts — unchanged

The three locked contracts (`core ⊥ modules`, `modules independent`, `integrations ⊥ modules`) hold without modification. Cross-module references (e.g. "selling a PT package emits a payment" — `pt_packages` module → `payments` module) go through **Protocol-based registration in `app/main.py` composition root**, identical to the v1.2 `ActiveMembershipResolver` and v1.1 `register_user_loader` precedents. No new contract needed.

---

## Frontend additions

### Runtime dependencies — ZERO new packages

| UI capability | Existing tool | Why no new dep |
|---|---|---|
| Sale-with-payment form (amount input + cash confirmation) | react-hook-form + Zod + shadcn `<Input>` + `<Button>` | Same pattern as v1.2 `MembershipSellForm`. Money input uses kopecks-as-integer with display-layer `formatMoney(minor)`. BLK-04 (kopecks-at-form-boundary) precedent from v1.2 Phase 22. |
| Refund button + confirm dialog | shadcn `<AlertDialog>` + TanStack Query mutation | Mirrors v1.3 `RenewConfirmDialog`. Mutation is non-optimistic (financial action — wait for server). |
| Payments history list on client/membership card | TanStack Query + existing `<DataTable>` (TanStack Table 8) | Same pattern as v1.3 memberships list with pagination + status pills. |
| `/trainers` owner-only CRUD page | TanStack Router + existing CRUD pattern from `/membership-plans` | Owner-only `beforeLoad` guard already established (v1.2 Phase 22). Active/inactive toggle = shadcn `<Switch>` (already available via shadcn primitives copy). |
| PT package detail page (balance + history) | TanStack Router flat-detail route (precedent: `/memberships/$membershipId` from v1.3) | Same Pattern α: route loader composes `Promise.all([pkg, sessions, payments])` via `ensureQueryData` with feature-isolated imports. |
| PT session recording UI (pick trainer, confirm "1 session used") | shadcn `<Select>` (Radix Select) + `<Button>` + Sonner toast | Trainer picker = active trainers from `/trainers?active=true`. shadcn registry pulls the underlying Radix primitive transparently. |
| Status badges (PT pkg `active / depleted / cancelled / refunded`) | Existing `StatusBadge` (v1.3 4-variant pattern) | Extend discriminated-union to cover 4 new variants; reuse semantic Tailwind tokens (`bg-warning`, `bg-destructive`, `bg-muted`). |
| Phone validation for trainer form | Existing E.164 Zod schema from `clients` entity | Reuse `phoneSchema` (optional variant). Don't duplicate. |
| API client types | Existing `@sportzal/api-client` workspace package + `openapi-typescript` codegen | One `pnpm --filter @sportzal/api-client codegen` run after backend OpenAPI regen — drift-gate already enforces byte stability. |

### Libraries explicitly ruled out for the frontend

| Candidate | Status | Reason |
|---|---|---|
| `dinero.js` / `money.js` | REJECT | Same reason as backend `py-moneyed` — we don't need a Money class. `formatMoney(minor)` + `Intl.NumberFormat('ru-RU', {currency: 'RUB'})` already do the job; raw integer kopecks travel through forms via BLK-04 pattern. |
| Currency input components (`react-currency-input-field`, etc.) | REJECT | shadcn `<Input>` with on-blur normalisation and `inputMode="numeric"` is enough. Russian locale formatting on display is handled by `formatMoney`. |
| State machine library (`xstate`) | REJECT | Refund / PT-package status is server-authoritative; the frontend renders status and shows/hides buttons based on it. No client-side FSM needed. |
| New chart library | REJECT | v1.4 has NO reports. Reports/dashboard is explicitly deferred to v1.5 per `.planning/PROJECT.md` line 49. |
| Receipt PDF / printing libraries | REJECT | No fiscal receipts in v1.4 (54-ФЗ out of scope per owner). |

---

## Explicitly NOT adding (with reasons)

### Backend

1. **`py-moneyed` / `python-money` / `Decimal` / `Numeric` columns.** Single-currency RUB; kopecks are exact integers; convention locked since v1.0. Adding now = migration churn for zero benefit.
2. **Native Postgres `MONEY` type.** Locale-sensitive, driver-dependent string output, community-rejected.
3. **State-machine library (`transitions`, `python-statemachine`, `automat`).** v1.3 proved declarative constant + central guard is enough and grep-able.
4. **Event-sourcing framework.** Append-only ledger + audit log already give traceability; ES would dwarf the feature scope.
5. **Background cron for PT package depletion.** Synchronous status update inside the recording service is race-safe via `WHERE sessions_remaining > 0`. No 6th ARQ job needed.
6. **Fiscal-receipt libraries (`ofd-py`, ATOL SDKs, ЮKassa SDK).** 54-ФЗ explicitly out of scope ("серая зона" per owner). ЮKassa deferred to v1.6.
7. **Stripe SDK.** Region-banned. Never.
8. **`pydantic-extra-types` Money / Currency types.** Same single-currency reason; no benefit over plain `int`.
9. **PT-trainer payroll / commission engine.** v1.4 scope is "тренеры — только справочник"; payroll deferred indefinitely.
10. **`sqlalchemy-utils`.** One-type wrappers don't justify pulling 30 classes; plain Integer columns suffice.
11. **`alembic-utils` for materialised view of "balance per client".** Premature; v1.4 reads remaining balance directly from `pt_packages.sessions_remaining`. No view needed.

### Frontend

1. **Money input library.** Use shadcn `<Input>` + Zod + `formatMoney`. Mirrors v1.2 BLK-04 precedent.
2. **Date-range pickers for "payments between X and Y".** Out of scope — v1.4 surfaces payments per-client / per-membership, not as a global date-ranged report. That's v1.5.
3. **Chart libraries.** Reports are v1.5.
4. **Receipt PDF generation libraries.** No fiscal receipts in v1.4.
5. **A new modal/dialog framework.** Radix `<Dialog>` + `<AlertDialog>` already cover refund-confirm and PT-session-confirm flows.
6. **Optimistic updates for refunds.** Financial actions stay non-optimistic (server-authoritative), same precedent as v1.3 renewal.
7. **A new chart/badge library.** Extend the v1.3 `StatusBadge` discriminated union with new variants.
8. **Trainer avatar uploads / image library.** Out of scope; v1.4 trainers have name + phone + active flag only.

---

## Integration notes

### Existing import-linter contracts hold

- **`core ⊥ modules`** — new `Resource.PAYMENTS / TRAINERS / PT_PACKAGES / PT_SESSIONS` enum values live in `app/core/rbac.py`, which already hosts `Resource`. No change to direction.
- **`modules independent`** — cross-module references go through Protocol callbacks registered in `app/main.py`. Precedents:
  - v1.1 `register_user_loader` (auth → clients)
  - v1.2 `ActiveMembershipResolver` (visits → memberships)
  - v1.3 `HandlerContext` (telegram-bot → visits_service)

  v1.4 will likely need:
  - `PaymentRecorder` Protocol (sellers of memberships and pt_packages call this to insert a payment row without importing `payments` module).
  - `PtPackageResolver` Protocol (if any other module needs "active pt_package for client" — likely only the admin-web wiring needs this through the dedicated endpoint, so the Protocol may not be required).
  - `TrainerResolver` Protocol (pt_sessions service validates trainer exists + is active without importing `trainers` module directly).
- **`integrations ⊥ modules`** — no v1.4 work in `app/integrations/` (cash payments are entered through admin-web; no external SDK).

### Existing patterns to reuse verbatim

| v1.4 surface | Precedent | What to copy |
|---|---|---|
| `/api/v1/payments` list + POST | v1.2 `/api/v1/membership-plans` (Phase 16) | RBAC dependency, CSRF, `Page[T]` envelope, audit emit, SVC001 explicit `await session.commit()` |
| `/api/v1/payments/{id}/refund` POST | v1.3 `/api/v1/memberships/{id}/freeze` (Phase 25) | Mutation endpoint with central-guard transition + 409 `invalid_transition` |
| `pt_packages` table snapshot semantics | v1.2 `memberships` `price_kopecks_snapshot` (Phase 17) | Mandatory NOT NULL snapshot columns; FK to plan with `ON DELETE RESTRICT` |
| `pt_sessions` race-safety | v1.2 `visits` UNIQUE `(client_id, gym_date)` (Phase 19) | Let the DB win the race via `UPDATE … WHERE sessions_remaining > 0 RETURNING …`; second concurrent click returns no rows → service raises 409 `pt_package_depleted_or_missing` |
| PT package status guard | v1.3 `MEMBERSHIP_STATUS_TRANSITIONS` (Phase 24) | Same declarative constant + `_assert_can_transition()` helper |
| Trainer soft-delete + name partial unique | v1.1 clients (Phase 8) + v1.2 membership_plans (Phase 16) | `lower(name)` partial unique on `WHERE deleted_at IS NULL`; 409 `trainer_in_use` if FK from `pt_sessions` exists |
| Admin-web sale form refactor | v1.2 `MembershipSellForm` (Phase 22) | Add a "payment received" subsection; same RHF + Zod single-schema-for-form-and-service |
| Admin-web PT package detail | v1.3 `/memberships/$membershipId` (Phase 28) | Flat route, Pattern α loader, sibling sections (here: `BalanceSection` + `SessionsHistorySection` + `PaymentsSection`) |

### Russian-market constraints respected

- No Stripe (banned).
- No ЮKassa (deferred to v1.6; the payment ledger is shaped so a future ЮKassa intake just inserts rows with `method='card_yookassa'` instead of `method='cash'` — schema needs the `method TEXT` column even though v1.4 only writes `'cash'`).
- No 54-ФЗ fiscal receipts (explicit grey-zone decision per `.planning/PROJECT.md` line 40).
- Russian-only locked DM strings — N/A for v1.4 (no Telegram-side cash flows in scope).
- All amounts in kopecks (RUB minor units); display via `Intl.NumberFormat('ru-RU', {currency: 'RUB'})` with NBSPs.

### CI gates — unchanged

Existing 6-gate matrix (backend ruff / mypy / pytest / openapi-drift + frontend typecheck / lint / test / codegen-drift) holds without modification. v1.4 will add tests inside `apps/backend/tests/` and `apps/admin-web/src/**/__tests__/` trees and let the existing gates catch them.

### Forward seam for v1.5 reports

The `payments` table schema should include `purchased_at TIMESTAMPTZ NOT NULL DEFAULT now()` indexed on `(purchased_at)` AND `(method, purchased_at)` so v1.5 daily-revenue queries are fast without re-indexing. Same forward-thinking discipline as v1.2 visits `gym_date` STORED column being designed for future reports.

### Forward seam for v1.6 ЮKassa

Include `method TEXT NOT NULL DEFAULT 'cash' CHECK (method IN ('cash', ...))` from day one. v1.6 extends the CHECK constraint (one-line Alembic migration) and adds a webhook intake; the ledger schema doesn't need a v1.6 rewrite.

---

## Sources

- [SQLAlchemy 2.1 PostgreSQL dialect docs](https://docs.sqlalchemy.org/en/21/dialects/postgresql.html) (HIGH — official docs)
- [SQLAlchemy issue #5965 — PostgreSQL MONEY returns string](https://github.com/sqlalchemy/sqlalchemy/issues/5965) (HIGH — upstream confirmation that native MONEY is not viable)
- [SQLAlchemy discussion #7124 — Money precision strategies](https://github.com/sqlalchemy/sqlalchemy/discussions/7124) (MEDIUM — community consensus on Numeric vs minor-units)
- [PostgreSQL official docs — Monetary Types](https://www.postgresql.org/docs/current/datatype-money.html) (HIGH — confirms locale sensitivity)
- Existing project decisions: `.planning/PROJECT.md` Key Decisions (kopecks integer convention since v1.0; BLK-04 form-boundary precedent v1.2; `MEMBERSHIP_STATUS_TRANSITIONS` declarative pattern v1.3) — HIGH confidence (in-repo, validated through 729 backend tests + 233 admin-web tests).
- `apps/backend/pyproject.toml` — current backend dependency lockset (HIGH).
- `apps/admin-web/package.json` + `apps/admin-web/CLAUDE.md` — current frontend dependency lockset and locked conventions (HIGH).
