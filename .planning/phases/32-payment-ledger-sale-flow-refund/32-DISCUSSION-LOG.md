# Phase 32: Payment Ledger + Sale Flow + Refund — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `32-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-05-15
**Phase:** 32-payment-ledger-sale-flow-refund
**Mode:** `/gsd-discuss-phase 32 --auto` — Claude selected recommended defaults for every gray area without AskUserQuestion. Single-pass per `auto.md` Cap. Areas were auto-selected (no manual filtering).
**Areas discussed:** Migration shape (PAY-01), memberships.cancellation_reason ALTER (REF-01), Payments module structure (PAY-03), Refund orchestration (REF-01..07), Protocol slot wiring + sale-flow integration (PAY-04, PAY-05), Idempotency-Key dependency (PAY-09), payment_row_hash helper (D-30-04 final selection), List endpoints (PAY-06..08), Plan splitting

---

## Migration shape (`0012_payments.py`)

| Option | Description | Selected |
|--------|-------------|----------|
| One mixed migration (CREATE TABLE payments + ALTER memberships cancellation_reason) | Both schema changes in 0012; refund flow tests work end-to-end after one upgrade step. | ✓ |
| Split into 0012 (payments) + 0013 (memberships ALTER) | "One concern per migration" discipline; downside is fixture ordering trap for refund tests. | |

**Claude's choice (auto):** Single 0012 — mirrors v1.3 0007 (status taxonomy + freeze table bundled) and avoids fixture-ordering trap.
**Rationale:** Refund flow integration tests need both payments table and `cancellation_reason` column simultaneously; semantic cohesion outweighs strict "one concern per file" rule.

---

## Payment table columns + constraints

| Option | Description | Selected |
|--------|-------------|----------|
| `UUIDPkMixin` only (no TimestampMixin, no SoftDeleteMixin); `received_at` single temporal | Append-only invariant explicit at ORM level; mirrors B-01 / INFRA-22 walker enforcement. | ✓ |
| Include `created_at` + omit `updated_at` (partial TimestampMixin) | Conventional "created_at" tracking; redundant with `received_at` for payments. | |

**Claude's choice (auto):** UUIDPkMixin only. `received_at TIMESTAMPTZ DEFAULT now()` is the only temporal column.
**Rationale:** B-01 append-only invariant; `received_at` is what business cares about (when cashier accepted); `created_at` would just duplicate.

| Option | Description | Selected |
|--------|-------------|----------|
| Single CHECK on `amount_kopecks` sign | One `(subject_kind='refund' AND amount<0) OR (subject_kind IN ('membership','pt_package') AND amount>0)` constraint. | ✓ |
| Two separate CHECKs | One for "refund must be negative", one for "sale must be positive". | |

**Claude's choice (auto):** Single CHECK — atomic invariant, cleaner pg_dump output.

---

## memberships.cancellation_reason ALTER

| Option | Description | Selected |
|--------|-------------|----------|
| `ALTER ADD COLUMN cancellation_reason TEXT NULL` (no default, no backfill) | Existing cancelled rows get NULL (legacy-unknown); future cancels populate `'refunded'` or NULL. | ✓ |
| Same + NOT NULL with backfill `'legacy'` | Forces semantic on historical rows; backfill burden without business value. | |
| Same + CHECK `cancellation_reason IS NOT NULL WHERE status='cancelled'` | Forces every future cancel to populate; admin cancels currently store reason in audit, not column. | |

**Claude's choice (auto):** NULL allowed, no backfill, no CHECK. Refund flow uses sentinel `CANCELLATION_REASON_REFUNDED = 'refunded'`; admin cancels remain NULL in v1.4.

---

## payments service entry point shape

| Option | Description | Selected |
|--------|-------------|----------|
| `record_payment(...)` + `issue_refund(...)` — both caller-owns-txn | Module-level async functions; no internal `await session.commit()`; outer orchestrator owns UoW. | ✓ |
| Same functions with internal commit | Self-contained UoW; couples recorder to its caller's transaction lifecycle. | |
| Class-based `PaymentsService` with DI | Object-oriented; not project convention (memberships/clients use module-level functions). | |

**Claude's choice (auto):** Module-level caller-owns-txn functions. SVC001 walker accepts via docstring marker `# caller-owns-txn` per Phase 19 D-10 precedent.
**Rationale:** REQ PAY-03 verbatim "caller-owns-txn discipline (D-03)"; refund orchestrator (memberships.service.refund_membership) must hold UoW; payments.service.issue_refund cannot independently commit without breaking single-UoW integrity for the refund chain.

---

## Refund orchestrator location

| Option | Description | Selected |
|--------|-------------|----------|
| `memberships.service.refund_membership(...)` consumes `payment_refunder` Protocol slot | Symmetric with `create_membership` consuming `payment_recorder`; membership transition is dominant concern. | ✓ |
| `payments.service.issue_membership_refund(...)` orchestrator imports memberships transition | Inverts dependency; would force payments→memberships cross-module import. | |

**Claude's choice (auto):** memberships.service. Symmetric with sale flow; preserves modules-independent contract (payments.service does NOT import memberships).
**Rationale:** Plan 32-03 modifies memberships.service to add refund_membership orchestrator that consumes the `payment_refunder` Protocol slot via `get_payment_refunder()` accessor.

---

## Status guard ordering in refund_membership

| Option | Description | Selected |
|--------|-------------|----------|
| frozen-specific 409 → renewed-source 409 → generic _assert_can_transition | Specific codes win first; preserves operator-friendly error messages. | ✓ |
| Generic guard first | Catches already-cancelled early but loses specific 'must_unfreeze_first' / 'cannot_refund_renewed_source' messages. | |

**Claude's choice (auto):** Specific-first ordering per Phase 25 D-25-07 precedent.

---

## Protocol slot accessor — defensive raise vs silent None

| Option | Description | Selected |
|--------|-------------|----------|
| Defensive raise (mirror `_user_loader` line 60) | `get_payment_recorder()` raises `RuntimeError("payment_recorder not registered")` if slot empty. | ✓ |
| Silent None (mirror `_active_membership_resolver` line 122) | Returns None; caller must handle. | |

**Claude's choice (auto):** Defensive raise. Missing slot at runtime = silently selling without money = invariant violation.
**Rationale:** Payments are load-bearing — they MUST be recorded; missing slot is a programmer error, not a domain "no value" condition.

---

## Protocol slot wiring location

| Option | Description | Selected |
|--------|-------------|----------|
| Exclusively `app/main.py:create_app()` | Single composition root; bot does not sell/refund. | ✓ |
| Double-wired (main.py + telegram_bot.py:main()) | Defensive (TRN-06 / REG-29-03 precedent); unnecessary since bot is not participant. | |

**Claude's choice (auto):** Main.py only. PAY-04 verbatim "registered exclusively from `app/main.py:create_app()`"; bot scope does not include payments in v1.4.

---

## Idempotency-Key implementation

| Option | Description | Selected |
|--------|-------------|----------|
| Per-route FastAPI Dependency (`verify_idempotency` + `idempotent_response`) | Mirrors `verify_csrf` per-route shape; narrowly scoped to sale endpoints. | ✓ |
| ASGI middleware | Global blast radius; harder to test in isolation; over-applies to endpoints that don't need it. | |
| Decorator | Less idiomatic FastAPI; clashes with `dependencies=[...]` route metadata. | |

**Claude's choice (auto):** Per-route Dependency in `app/core/idempotency.py`.

| Option | Description | Selected |
|--------|-------------|----------|
| Scope: sale endpoints only (`POST /memberships`, future `POST /pt-packages`) | Minimal — natural guards (DB partial UNIQUE, status transition guards) handle refund/freeze/renew idempotency. | ✓ |
| Apply to all mutation endpoints | Over-applies; conflicts with status-transition natural guards. | |

**Claude's choice (auto):** Sale-only scope per D-32-20.

| Option | Description | Selected |
|--------|-------------|----------|
| SHA-256 body hash to detect key reuse with different intent | Second-call body hash differs from stored → 422 `idempotency_key_reuse` (RFC 8594 draft semantic). | ✓ |
| First-write-wins ignoring body | Silently returns first cached response regardless of body — risky. | |

**Claude's choice (auto):** Body hash detection (RFC 8594 draft semantic).

---

## payment_row_hash helper

| Option | Description | Selected |
|--------|-------------|----------|
| Helper in `app/core/audit_hash.py` (pencilled in audit_payloads.py docstring) | core ⊥ modules contract preserved; `payment_row_hash(row: Mapping[str, Any]) -> str` primitive. | ✓ |
| Helper in `app/modules/payments/service.py` | Couples to module; restricts reuse if other modules ever need similar hashing. | |

**Claude's choice (auto):** `app/core/audit_hash.py` per D-30-04 docstring final selection.

| Option | Description | Selected |
|--------|-------------|----------|
| `json.dumps(sort_keys=True, separators=(',', ':'), default=str)` + SHA-256 | Pragmatic, deterministic for primitives; UTC-normalize datetime. | ✓ |
| RFC 8785 JCS canonicalization | Over-engineering for internal forensic hash; deterministic across languages, not needed for single-process Python. | |

**Claude's choice (auto):** Python json.dumps with explicit sort_keys + separators.

| Option | Description | Selected |
|--------|-------------|----------|
| Hash 8 stable columns (`id, subject_kind, subject_id, amount_kopecks, method, received_at, received_by_user_id, refund_of`) — exclude `audit_log_id` | `audit_log_id` set after hash → chicken-and-egg; 8 stable cols cover forensic chain. | ✓ |
| Hash all columns including `audit_log_id` | Circular dependency at sale-time emit. | |

**Claude's choice (auto):** 8 stable columns, audit_log_id excluded.

---

## List endpoints (PAY-06/07/08) RBAC modeling

| Option | Description | Selected |
|--------|-------------|----------|
| Router-level scoped Depends `require_payments_view_for_subject(...)` | Local enforcement; no enum/registry churn; admits reception when scope-bound. | ✓ |
| Add `Resource.CLIENT_PAYMENTS`/`Resource.MEMBERSHIP_PAYMENTS` enum entries | Would require admin-web parity update in Phase 35; expands matrix complexity. | |
| Overload existing `(VIEW, PAYMENTS)` | Conflicts with Plan 30-02 locked owner-only semantic. | |

**Claude's choice (auto):** Router-level Depends (option a). Planner final-refines exact API surface during Plan 32-01.

| Option | Description | Selected |
|--------|-------------|----------|
| Define all 3 list endpoints in `payments/router.py` with `by-client`/`by-membership` URL shapes | Preserves modules-independent contract; admin-web fetches `/api/v1/payments/by-client/{id}`. | ✓ |
| Define `/clients/{id}/payments` in clients/router.py importing payments | Violates modules-independent contract. | |
| Nest under `/clients/{id}/payments` via FastAPI sub-prefix | Feasible but complicates path discovery; planner may choose. | |

**Claude's choice (auto):** All 3 in payments/router.py with explicit URL shapes. Planner may refine to nested mount if cleaner.

---

## Date range filter semantics

| Option | Description | Selected |
|--------|-------------|----------|
| Half-open range over `received_at` in Europe/Moscow TZ | `>= receivedFrom 00:00 MSK AND < (receivedTo + 1) 00:00 MSK`; TZ-safe; no last-second boundary loss. | ✓ |
| Inclusive `::date` cast | `received_at::date BETWEEN receivedFrom AND receivedTo`; TZ-ambiguous in container `TZ=UTC`. | |

**Claude's choice (auto):** Half-open MSK range. Mirrors v1.2 gym_date STORED column discipline.

---

## Plan splitting

| Option | Description | Selected |
|--------|-------------|----------|
| 3 plans (foundations → sale-flow → refund-flow) | Mirrors v1.3 Phase 25 cadence; tests live alongside owner; atomic rollback per concern. | ✓ |
| 4 plans (foundations / sale / refund / tests) | Standalone "tests" plan is anti-pattern; tests are owned by feature. | |
| 5+ plans (split idempotency, audit_hash, list endpoints into own plans) | Over-granular; idempotency and audit_hash are infrastructure pieces that belong in foundations. | |

**Claude's choice (auto):** 3 plans per D-32-27. Plan 32-01 (foundations) gates Plans 32-02 and 32-03, which are parallel-eligible thereafter.

---

## Claude's Discretion

These items are explicitly handed off to the planner:

- PAY-07/PAY-08 RBAC modeling detail (router-level Depends vs new enum entries vs overload).
- Migration consolidation 0012 vs 0012+0013 (recommended bundled; planner may split if Alembic autogenerate emits warnings).
- Admin-cancel `cancellation_reason` column populate behaviour (recommended leave NULL in v1.4; planner may populate from request body).
- `payment_row_hash_from_orm(payment: Payment)` typed wrapper (recommended; both primitive + ORM helper).
- Idempotency-Key character set and max length (recommended `^[A-Za-z0-9_:-]{1,128}$`).
- In-flight idempotency placeholder TTL (recommended 3600s — same as final envelope; planner may shorten placeholder to 60s for timeout safety).
- `RefundIssuedPayload.reason` field — already locked in Plan 30-01; planner reuses.

---

## Deferred Ideas

Captured in CONTEXT.md `<deferred>` section. Highlights:

- PT-package sale recorder consumption (PT-07) → Phase 33.
- `POST /api/v1/pt-packages/{id}/refund` router → Phase 33.
- All admin-web UI (FE-11..13, FE-15) → Phase 35.
- Mock-mode service `mock/payments.ts` → Phase 35.
- `payment_row_hash` for `membership_refunded` / `pt_package_refunded` events → rejected; only `refund_issued` carries hash in v1.4.
- Pro-rata refunds → out of v1.4 (B-02).
- End-of-day cash-drawer reconciliation → B-06 / v1.5+.
- `GET /api/v1/audit-log` → v1.5.
- ЮKassa + 54-ФЗ → v1.6.
- Soft-delete on payments → explicitly forbidden by B-01.
- `Resource.CLIENT_PAYMENTS` / `Resource.MEMBERSHIP_PAYMENTS` enum entries → rejected in favor of router-level scoped Depends.

---

*Audit log generated 2026-05-15 by `/gsd-discuss-phase 32 --auto`.*
