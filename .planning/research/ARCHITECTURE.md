# Architecture — v1.4 Cash Sales + PT Packages

**Project:** Sportzal v1.4 (Cash Sales + PT Packages)
**Researched:** 2026-05-14
**Confidence:** HIGH (grounded in concrete v1.0–v1.3 patterns; all references verified against current codebase)

This file answers: *how do v1.4's five business themes (payments, refund, trainers catalog, PT-package plan kind, PT session recording) plug into the existing modular-monolith without breaking the three import-linter contracts or the Locked-Audit-Events frozenset gate?*

## Module structure decisions

### 1. `payments/` — NEW module, owns ledger + refund

**Decision: create `app/modules/payments/`.**

Rationale:
- A payment is **not** a property of a membership — it is an independent ledger fact owned by the operator (who took the cash, when). v1.5 reports will need to read it without traversing memberships. v1.6 (ЮKassa) will swap the *source* of a payment row without touching memberships.
- Putting it inside `memberships/` would make refund logic asymmetric the day PT-packages arrive (refund touches both `memberships` and PT-package state), and would force `memberships/` to grow finance-shaped concepts (`actor_received_by_user_id`, refund accounting) that it does not own.
- The `modules-independent` contract forbids `memberships → payments` and `payments → memberships`. Both directions are needed at sale + refund time. The fix is the same Protocol pattern v1.1 / v1.2 / v1.3 used three times already: **`payments` exposes a Protocol slot that the composition root wires into `memberships.service`'s sale + cancel paths**, and **`memberships` exposes its existing slots to `payments` for refund coordination**.

Module shape (mirrors `clients/` and `memberships/`):
```
app/modules/payments/
├── __init__.py
├── router.py           — /api/v1/payments (list, get) + /refunds (POST refund)
├── service.py          — record_payment(), issue_refund(), list_payments_for_client(), list_payments_for_membership()
├── repository.py       — insert_payment, insert_refund, select_by_subject, etc.
├── models.py           — Payment, Refund (or one Payment row with refund_of FK — see below)
├── schemas.py          — Pydantic request/response (camelCase, ResponseEnvelope)
├── permissions.py      — (optional, only if reception-specific checks beyond RBAC dependency)
└── constants.py        — payment kinds, refund reasons enum, error codes
```

### 2. `trainers/` — promote placeholder to a real module

**Decision: create `app/modules/trainers/`.**

Currently `app/modules/trainers/` is an empty placeholder (no files inside). Promote it to a real module with the standard shape. It is the smallest scope in v1.4 and the cleanest first phase.

Trainers cannot logically live anywhere else — it is a top-level catalog, owner-only, no overlap with clients (no auth, no Telegram, no payments). Single table, 4 CRUD endpoints, ~150 LOC service.

### 3. PT-packages — NEW module `pt_packages/` (NOT extension of `memberships`)

**Decision: create `app/modules/pt_packages/` as a separate module.**

This is the most consequential decision. Argument both ways:

**For "extend `memberships`":**
- 80% lifecycle overlap (sell → hold balance → cancel/refund).
- Audit events and RBAC actions could be reused (`membership_*`).
- Saves one module.

**For "new module" (chosen):**
- The *balance* model is fundamentally different: memberships hold a date (`end_date`), PT-packages hold a counter (`sessions_remaining` decremented per use). Putting both into one ORM table forces a nullable-pair schema (`end_date NULL XOR sessions_remaining NULL`) — exactly the kind of soft union that v1.3 audit-and-CHECK culture rejects.
- The active-instance *resolver* is different: visits resolver currently returns `ActiveMembership` with `end_date` and `status`. PT-session recording needs `sessions_remaining > 0` instead. Trying to merge these into one Protocol creates an oracle (which kind?) at every caller. Two separate Protocol slots is cleaner.
- The audit taxonomy is already separable. `pt_package_sold`, `pt_session_recorded`, `pt_package_refunded` are distinct verbs from `membership_*`.
- v1.5 reports will likely treat revenue-from-memberships vs revenue-from-PT as separate metrics anyway — the schema separation makes that 1-line SQL instead of a discriminator scan.
- The two share zero query patterns: memberships query by `(client_id, status, end_date DESC)`, PT-packages query by `(client_id, status, sessions_remaining > 0)`. No composite index serves both.

PT-package module shape:
```
app/modules/pt_packages/
├── __init__.py
├── router.py           — /api/v1/pt-package-plans/* (owner CRUD) +
│                          /api/v1/pt-packages/* (sell, cancel, list, get) +
│                          /api/v1/pt-sessions/* (record, list, get, ?cancel)
├── service.py
├── repository.py
├── models.py           — PtPackagePlan, PtPackage, PtSession
├── schemas.py
├── constants.py        — PT-package status transitions matrix + error codes
```

Why fold PT-sessions into the same module rather than a 4th `pt_sessions/`:
- Sessions cannot exist without a parent PT-package; balance decrement is one transaction; the only cross-module reference is `trainer_id` (Protocol slot).
- v1.2 lesson from `memberships/` containing both `membership_plans` and `memberships` (two ORM types, two routers, one service file): one module per *bounded context*, not per table.

### Summary — new modules: 3
| Module | Tables | Routers |
|---|---|---|
| `trainers` | `trainers` | 1 |
| `payments` | `payments` (+ refund as a row or separate table — see below) | 1–2 |
| `pt_packages` | `pt_package_plans`, `pt_packages`, `pt_sessions` | 3 |

Module count goes from 4 (auth, clients, memberships, visits) → 7. Still well within "modular monolith" scope.

## Database migration plan

Existing migration chain ends at `0010_notifications.py`. v1.4 adds **migrations 0011 through 0015** in this order (each one self-contained; later ones reference earlier FKs):

### 0011_trainers.py — Trainers catalog
```sql
CREATE TABLE trainers (
  id UUID PRIMARY KEY,
  full_name        VARCHAR(120) NOT NULL,
  phone            VARCHAR(32)  NULL,       -- E.164 if present; nullable per scope
  active           BOOLEAN NOT NULL DEFAULT true,
  notes            TEXT NULL,
  created_at, updated_at, deleted_at         -- standard mixins
);
CREATE UNIQUE INDEX uq_trainers_phone_alive
  ON trainers (phone) WHERE deleted_at IS NULL AND phone IS NOT NULL;
-- Mirrors clients soft-delete partial-unique pattern (Phase 8).
```

### 0012_payments.py — Payment ledger + refund
**One table, refunds are rows that point at parents** (chosen over two tables):

```sql
CREATE TABLE payments (
  id UUID PRIMARY KEY,
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,
  subject_kind VARCHAR(16) NOT NULL,        -- 'membership' | 'pt_package' | 'refund'
  subject_id   UUID NOT NULL,               -- membership.id OR pt_package.id OR original payment.id
  amount_kopecks BIGINT NOT NULL,            -- positive on sale; negative on refund row
  method VARCHAR(16) NOT NULL DEFAULT 'cash', -- forward-compat enum: 'cash' | 'yookassa' (v1.6) | 'card_offline'
  received_by_user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  refund_of UUID NULL REFERENCES payments(id) ON DELETE RESTRICT,
                                             -- set on refund rows; one-to-one logical link
  refund_reason TEXT NULL,
  created_at, updated_at                     -- (no soft-delete; ledger is append-only)
  CONSTRAINT ck_payments_subject_kind CHECK (subject_kind IN ('membership','pt_package','refund')),
  CONSTRAINT ck_payments_amount_sign  CHECK (
    (subject_kind = 'refund' AND amount_kopecks < 0) OR
    (subject_kind != 'refund' AND amount_kopecks > 0)
  ),
  CONSTRAINT ck_payments_refund_link CHECK (
    (subject_kind = 'refund') = (refund_of IS NOT NULL)
  )
);
CREATE INDEX ix_payments_client_id_received_at ON payments (client_id, received_at DESC);
CREATE INDEX ix_payments_subject_kind_subject_id ON payments (subject_kind, subject_id);
CREATE UNIQUE INDEX uq_payments_refund_of ON payments (refund_of) WHERE refund_of IS NOT NULL;
-- one refund per original payment; reattempts must replace, not stack
```

Rationale for one-table:
- Refund is a payment in the bookkeeping sense (negative cash event). Two tables would split a query like "show me all the cash flow on this client" into a `UNION`.
- The `subject_kind = 'refund'` + `refund_of` CHECK is the schema-level integrity, not app-layer.
- Matches v1.3 lesson: discriminated unions guarded by CHECKs are clearer than parallel tables.

### 0013_pt_package_plans.py
```sql
CREATE TABLE pt_package_plans (
  id UUID PRIMARY KEY,
  name VARCHAR(120) NOT NULL,
  session_count INTEGER NOT NULL,            -- e.g. 10 sessions
  price_kopecks BIGINT NOT NULL,
  validity_days INTEGER NULL,                -- optional expiry; NULL = never
  active BOOLEAN NOT NULL DEFAULT true,
  created_at, updated_at, deleted_at
  CONSTRAINT ck_pt_package_plans_session_count_positive CHECK (session_count > 0),
  CONSTRAINT ck_pt_package_plans_price_kopecks_nonneg   CHECK (price_kopecks >= 0),
  CONSTRAINT ck_pt_package_plans_validity_days_positive CHECK (validity_days IS NULL OR validity_days > 0)
);
CREATE UNIQUE INDEX uq_pt_package_plans_name_alive
  ON pt_package_plans (lower(name)) WHERE deleted_at IS NULL;
-- Mirrors uq_membership_plans_name_alive (Phase 16).
```

### 0014_pt_packages.py
```sql
CREATE TABLE pt_packages (
  id UUID PRIMARY KEY,
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,
  plan_id   UUID NOT NULL REFERENCES pt_package_plans(id) ON DELETE RESTRICT,
  plan_name_snapshot     VARCHAR(120) NOT NULL,    -- mandatory snapshot pattern (v1.2 lesson)
  session_count_snapshot INTEGER     NOT NULL,
  price_kopecks_snapshot BIGINT      NOT NULL,
  validity_days_snapshot INTEGER     NULL,
  sessions_remaining     INTEGER     NOT NULL,     -- decremented per pt_session
  start_date             DATE        NOT NULL,
  end_date               DATE        NULL,         -- start + validity_days - 1; NULL if no expiry
  status VARCHAR(16) NOT NULL DEFAULT 'active',
  cancelled_at TIMESTAMPTZ NULL,
  cancel_reason TEXT NULL,
  paid_at TIMESTAMPTZ NULL,
  notes TEXT NULL,
  created_at, updated_at
  CONSTRAINT ck_pt_packages_status CHECK (status IN ('active','exhausted','expired','cancelled')),
  CONSTRAINT ck_pt_packages_sessions_remaining_nonneg CHECK (sessions_remaining >= 0),
  CONSTRAINT ck_pt_packages_sessions_remaining_le_snapshot
    CHECK (sessions_remaining <= session_count_snapshot)
);
CREATE INDEX ix_pt_packages_client_id_status_remaining
  ON pt_packages (client_id, status, sessions_remaining DESC);
-- supports the active-PT-package resolver lookup
```

Status taxonomy (declarative constant, like `MEMBERSHIP_STATUS_TRANSITIONS`):
```
active → exhausted   (sessions_remaining hits 0)
active → expired     (cron: end_date < today)
active → cancelled   (operator refund)
```
No `frozen` for PT-packages in v1.4 (out of scope; PT-package freeze is a v1.5+ ask if at all).

### 0015_pt_sessions.py
```sql
CREATE TABLE pt_sessions (
  id UUID PRIMARY KEY,
  pt_package_id UUID NOT NULL REFERENCES pt_packages(id) ON DELETE RESTRICT,
  client_id     UUID NOT NULL REFERENCES clients(id)     ON DELETE RESTRICT,
                                            -- denormalised for fast client-history query (one JOIN avoided)
  trainer_id    UUID NOT NULL REFERENCES trainers(id)    ON DELETE RESTRICT,
  performed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  performed_by_user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
                                            -- reception operator who logged the session
  cancelled_at TIMESTAMPTZ NULL,             -- if reception mis-recorded; cancel restores balance
  cancel_reason TEXT NULL,
  notes TEXT NULL,
  created_at, updated_at
);
CREATE INDEX ix_pt_sessions_client_id_performed_at ON pt_sessions (client_id, performed_at DESC);
CREATE INDEX ix_pt_sessions_trainer_id_performed_at ON pt_sessions (trainer_id, performed_at DESC);
CREATE INDEX ix_pt_sessions_pt_package_id ON pt_sessions (pt_package_id);
```

PT-session decrement is **two SQL statements in one UoW**: INSERT into `pt_sessions` + UPDATE `pt_packages SET sessions_remaining = sessions_remaining - 1 WHERE id = $1 AND sessions_remaining > 0` (returning-clause guarded — Postgres wins the race, not app-layer; this mirrors visits's DB-level `UNIQUE (client_id, gym_date)` discipline). Zero-decrement → 409 `pt_package_exhausted`.

### Out-of-band: status enum on `memberships` does **NOT** change

PT-packages live in a separate table → no need to extend `ck_memberships_status`. The `'pt_package'` discriminator never reaches the memberships taxonomy. This preserves Phase 17 / 24 status guard machinery intact.

## Cross-module callbacks (Protocol slots)

Each callback lives in `app/core/dependencies.py` next to existing `register_user_loader` / `register_active_membership_resolver` / `register_client_by_telegram_resolver`. Each is registered exactly once in `app/main.py:create_app()` and re-registered in `app/workers/telegram_bot.py:main()` (the REG-29-03 lesson from v1.3 verification — both processes must register or one will silently fail).

### Slot 4: `register_trainer_by_id_resolver` — consumed by PT-sessions

```python
class TrainerRef(Protocol):
    id: UUID
    full_name: str
    active: bool

TrainerByIdResolver = Callable[[AsyncSession, UUID], Awaitable[TrainerRef | None]]
```

Used by `pt_packages.service.record_pt_session()` to validate `trainer_id` exists + is active. Production wiring: `trainers.service.resolve_trainer_by_id`. Without this, `pt_packages` would need to `from app.modules.trainers import ...` which violates `modules-independent`.

### Slot 5: `register_payment_recorder` — consumed by memberships + pt_packages at sale time

```python
@dataclass
class PaymentRecordRequest:
    client_id: UUID
    subject_kind: Literal['membership','pt_package']
    subject_id: UUID
    amount_kopecks: int
    received_by_user_id: UUID

PaymentRecorder = Callable[[AsyncSession, PaymentRecordRequest], Awaitable[UUID]]
                  # returns the new payment.id
```

Used by `memberships.service.create_membership()` and `pt_packages.service.create_pt_package()` to atomically record the cash event in the same UoW as the sale. Production wiring: `payments.service.record_payment`. **Co-transactional discipline** (D-03 from Phase 8 audit): the caller owns the transaction; `record_payment` adds the row to the session and does not commit.

### Slot 6: `register_payment_refunder` — consumed by memberships + pt_packages at cancel time

```python
PaymentRefunder = Callable[[AsyncSession, UUID, UUID, str | None], Awaitable[UUID]]
                  # (session, subject_id, refunded_by_user_id, reason) -> refund_payment.id
```

Used by `memberships.service.cancel_membership()` (when initiated as a refund — see RBAC below) and `pt_packages.service.cancel_pt_package()` to insert the negative payment row. Looks up the original payment via `subject_kind + subject_id`, inserts the refund row, and (transactionally) cancels the parent.

**Inverse direction (payments → memberships/pt_packages) is NOT needed:** the refund flow is initiated from the *subject*'s module (`memberships` or `pt_packages`), which calls `payments` to record. The refund endpoint surfaces *on the subject* (`POST /memberships/{id}/refund`, `POST /pt-packages/{id}/refund`) — not on payments. This matches reception's mental model ("refund this membership") and avoids `payments → memberships` dependency.

### Slot 7: `register_active_pt_package_resolver` — consumed by pt_sessions logic + future reports

```python
class ActivePtPackage(Protocol):
    id: UUID
    client_id: UUID
    sessions_remaining: int
    status: str
    end_date: date | None

ActivePtPackageResolver = Callable[[AsyncSession, UUID], Awaitable[ActivePtPackage | None]]
                          # (session, client_id) -> first active package with sessions_remaining > 0
```

Used by reception UI's "record PT-session" flow (find which package to decrement). Same pattern as `ActiveMembership` from Phase 17.

### Composition-root wiring (`app/main.py`)

```python
# After existing register_* calls in create_app():

from app.modules.trainers import service as trainers_service
from app.modules.payments import service as payments_service
from app.modules.pt_packages import service as pt_packages_service

register_trainer_by_id_resolver(trainers_service.resolve_trainer_by_id)
register_payment_recorder(payments_service.record_payment)
register_payment_refunder(payments_service.issue_refund)
register_active_pt_package_resolver(pt_packages_service.resolve_active_pt_package_by_client)
```

**Mirror in `app/workers/telegram_bot.py:main()` is NOT needed** in v1.4 — the bot does not record payments or PT-sessions. (Future v1.5+ Telegram self-PT-record would require the mirror.)

### Import-linter contracts: no changes needed

The three existing contracts (`core ⊥ modules`, `modules-independent`, `integrations ⊥ modules`) hold without modification:
- All new cross-module talk goes through `core/dependencies.py` Protocol slots, identical to v1.1/v1.2/v1.3.
- `app/main.py` retains its single carve-out (it is outside `source_modules = app.core`).
- The new modules `payments`, `trainers`, `pt_packages` are added to the `modules-independent` contract's modules list.

Update needed in `apps/backend/.importlinter`:
```ini
[importlinter:contract:modules-independent]
modules =
    app.modules.auth
    app.modules.clients
    app.modules.memberships
    app.modules.visits
    app.modules.trainers     ; (was placeholder; now real)
    app.modules.payments     ; NEW
    app.modules.pt_packages  ; NEW
    app.modules.schedule
    app.modules.bookings
    app.modules.billing
    app.modules.notifications
```

## RBAC additions

### New `Action` enum values (`app/core/permissions.py`)

Existing: `VIEW, CREATE, EDIT, DELETE, REFUND, CANCEL, CHECK_IN`.

**No new `Action` values needed.**
- `REFUND` already exists (was previously paired with `FINANCE` for owner-only owner-view). Reuse it for `(REFUND, MEMBERSHIPS)` and `(REFUND, PT_PACKAGES)`.
- Decrement of a PT-session is `(CREATE, PT_SESSIONS)`. Mis-record cancel is `(CANCEL, PT_SESSIONS)`.
- Trainers CRUD uses standard `CREATE/EDIT/DELETE/VIEW`.

### New `Resource` enum values

```python
class Resource(StrEnum):
    ...
    TRAINERS         = "trainers"
    PAYMENTS         = "payments"
    PT_PACKAGE_PLANS = "pt-package-plans"   # kebab on wire
    PT_PACKAGES      = "pt-packages"
    PT_SESSIONS      = "pt-sessions"
```

### `OWNER_ONLY` additions (must mirror byte-for-byte in `apps/admin-web/src/shared/session/can.ts`)

```python
# Trainers — owner-only catalog (mirrors membership-plans pattern from v1.2)
(Action.VIEW,   Resource.TRAINERS),
(Action.CREATE, Resource.TRAINERS),
(Action.EDIT,   Resource.TRAINERS),
(Action.DELETE, Resource.TRAINERS),

# PT-package plans — owner-only catalog (mirrors membership-plans)
(Action.VIEW,   Resource.PT_PACKAGE_PLANS),
(Action.CREATE, Resource.PT_PACKAGE_PLANS),
(Action.EDIT,   Resource.PT_PACKAGE_PLANS),
(Action.DELETE, Resource.PT_PACKAGE_PLANS),

# Payments — reception writes (sale + refund), owner reads
# Reception RETAINS (CREATE, PAYMENTS) — not listed here.
# Reception RETAINS (REFUND, MEMBERSHIPS) and (REFUND, PT_PACKAGES) — per scope: reception can refund without owner approval
(Action.VIEW, Resource.PAYMENTS),    # history is owner-only (finance-adjacent)

# PT-packages instances — same shape as MEMBERSHIPS:
# Reception RETAINS (CREATE, PT_PACKAGES) and (CREATE, PT_SESSIONS).
(Action.CANCEL, Resource.PT_PACKAGES),
(Action.DELETE, Resource.PT_PACKAGES),
(Action.CANCEL, Resource.PT_SESSIONS),   # mis-record cancel = owner-only
```

**Open question deferred to discuss-phase:** the milestone goal text says "ресепшен сам без owner approval" for refund — so `(REFUND, MEMBERSHIPS)` is **NOT** in OWNER_ONLY. But `(VIEW, PAYMENTS)` is owner-only because viewing the full ledger is a finance surface. Confirm with operator.

`OWNER_ONLY` grows from 15 entries → ~26 entries.

### Three-way RBAC parity gate

Phase 6 TEST-06 asserts `apps/backend OWNER_ONLY` set-equals `apps/admin-web can.ts OWNER_ONLY` set-equals `packages/api-client` if it surfaces any. All new entries must land in **both** files in the same commit.

## LOCKED_AUDIT_EVENTS additions

Pre-register the full v1.4 frozenset extension in the foundations phase (mirrors v1.3 Phase 24 INFRA-15 / D-24-18 — register events BEFORE callsites land, so all subsequent phases pass CI from their first commit).

Add to `apps/backend/app/core/audit.py` `LOCKED_AUDIT_EVENTS`:

```python
# v1.4 — Trainers (Phase X1)
("trainer_created",       "trainer"),
("trainer_updated",       "trainer"),
("trainer_deactivated",   "trainer"),   # soft-delete (active=false) — chose "deactivated" over "deleted" to match domain language
("trainer_reactivated",   "trainer"),   # owner toggle active=false → true

# v1.4 — Payments (Phase X2)
("payment_recorded",      "payment"),   # cash sale
("refund_issued",         "payment"),   # negative-amount payment row inserted
# NOTE: payment_recorded fires from BOTH memberships sale AND pt_packages sale —
# `subject_kind` payload discriminates. Single audit verb, payload differentiates.

# v1.4 — Memberships refund (Phase X2 — touches memberships state via refund)
("membership_refunded",   "membership"),  # distinct from membership_cancelled:
                                          # refund cancels + reverses payment.
                                          # cancelled (existing) does NOT reverse payment.

# v1.4 — PT-package plans (Phase X3)
("pt_package_plan_created",   "pt_package_plan"),
("pt_package_plan_updated",   "pt_package_plan"),
("pt_package_plan_archived",  "pt_package_plan"),

# v1.4 — PT-packages (Phase X3)
("pt_package_sold",        "pt_package"),
("pt_package_cancelled",   "pt_package"),
("pt_package_refunded",    "pt_package"),
("pt_package_exhausted",   "pt_package"),   # sessions_remaining hit 0 (state transition)
("pt_package_expired",     "pt_package"),   # ARQ cron (if validity_days set)

# v1.4 — PT-sessions (Phase X4)
("pt_session_recorded",    "pt_session"),
("pt_session_cancelled",   "pt_session"),   # mis-record reversal; restores balance

# Total: 16 new entries → LOCKED_AUDIT_EVENTS goes from 34 → 50
```

Decision notes:
- **`membership_refunded` ≠ `membership_cancelled`**: cancel (existing v1.2) is operator-initiated state change with no money implication. Refund (new v1.4) is cancel + reverse-payment. Two distinct verbs so audit grep yields clean revenue numbers.
- **No `pt_package_freezing` events** — freeze is out of scope for v1.4.
- **No `payment_voided`** — refund is the only reverse path; we never delete or "void" a row. The append-only ledger discipline is the audit guarantee.
- Same AST literal-only gate (Phase 15 INFRA-11) applies — every `audit.emit("...", resource_type="...")` callsite must use string literals.

## Frontend admin-web structure

Mirror module/route boundaries on the frontend to keep ESLint `import/no-restricted-paths` consistent.

### New top-level routes (TanStack file-based)
```
src/routes/
├── trainers.tsx                       — list (owner-only beforeLoad)
├── trainers.$trainerId.tsx            — detail + edit (owner-only)
├── pt-package-plans.tsx               — owner-only catalog (mirrors membership-plans)
├── pt-package-plans.$planId.tsx
├── pt-packages.tsx                    — list (reception + owner)
├── pt-packages.$ptPackageId.tsx       — detail with balance + session history
├── payments.tsx                       — owner-only history page
```

### Modified routes / flows
- `/memberships` sale form (existing) — add "payment received" section: amount (pre-filled from snapshot price, editable for cash-discount cases) + "received by" (auto-set to current user). One TanStack mutation, two co-transactional inserts on backend.
- `/memberships/$membershipId` detail — add **Refund button** (reception or owner per scope). Confirm dialog with reason field. Add **payments section** showing the original + any refund rows.
- `/clients/$clientId` — extend Pattern α loader to fan into 5 ensureQueryData calls (clients, memberships, visits, pt-packages, payments). ESLint `no-restricted-paths` updated to allow `routes/clients` to import from `features/pt-packages` + `features/payments` per same Pattern α carve-out.

### New shared primitives
- `PaymentBadge` (semantic colors via `bg-success` token for sale, `bg-warning` for refunded) — extends `StatusBadge` family.
- `PtPackageStatusBadge` (4 variants: active / exhausted / expired / cancelled) — mirrors v1.3 `StatusBadge`.

### Mock services
- `mock/trainers.ts`, `mock/payments.ts`, `mock/pt-packages.ts` — full parity with backend service contracts.
- `mock/memberships.ts` — extend `createMembership` to optionally accept `payment` parameter, returning `{membership, payment}`. Wire to existing sale flow.
- v1.3 deferred tech-debt: `mock/memberships.ts ?status=` filter parity — land in foundations phase.

### OpenAPI drift gate refresh
Single atomic regen at end of v1.4 (mirrors Phase 28 + Phase 21): `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts` byte-stable, CI `git diff --exit-code` on both. Adds typed paths for:
- `/trainers/*`, `/payments/*`, `/pt-package-plans/*`, `/pt-packages/*`, `/pt-sessions/*`
- Extended `MembershipResponse` if it carries `latestPaymentId` (decision deferred — recommend NO, fetch separately, keep `MembershipResponse` stable).

## Suggested phase build order

**Recommended order (8 phases for milestone v1.4):**

### Phase 30 — Foundations (audit, RBAC, importlinter, deferred mock parity)
- LOCKED_AUDIT_EVENTS extension (all 16 new pairs locked up-front per v1.3 lesson).
- `Resource` enum values added.
- `OWNER_ONLY` entries added (~11 new) — three-way parity assertion runs.
- `.importlinter` modules-independent list extended.
- v1.3 deferred mock-mode `?status=` filter parity closed.
- No new tables yet; no new endpoints. Just the contract bedrock.

### Phase 31 — Trainers module
- Migration 0011_trainers.
- `app/modules/trainers/` full module: 4 CRUD endpoints owner-only + 1 `GET /trainers?active=true` for reception filter.
- Protocol slot 4 (`register_trainer_by_id_resolver`) added.
- Wired in `app/main.py` AND `app/workers/telegram_bot.py:main()` (defensive — REG-29-03 lesson, even though bot doesn't use it yet).
- Frontend `/trainers` page + mock service.
- Smallest scope → validates the "new module" template before bigger phases.

### Phase 32 — Payment ledger + Membership sale-with-payment + Membership refund
- Migration 0012_payments.
- `app/modules/payments/` module: list/get + internal `record_payment` / `issue_refund` functions.
- Protocol slots 5 + 6 (`register_payment_recorder`, `register_payment_refunder`).
- Modify `memberships.service.create_membership` to call payment recorder in same UoW.
- New endpoint `POST /memberships/{id}/refund` (separate from cancel — refund cascades to payments).
- Audit: `payment_recorded`, `refund_issued`, `membership_refunded` callsites land.
- Frontend: sale form extension, refund button + dialog.
- **Why before PT-packages:** PT-package sale-with-payment reuses the recorder slot. Wrong order = rework.

### Phase 33 — PT-package plans + PT-package instances (no sessions yet)
- Migrations 0013_pt_package_plans + 0014_pt_packages.
- `app/modules/pt_packages/` — plans router + packages router (sell, list, get, cancel, refund). Reuses payment recorder + refunder slots from Phase 32.
- Protocol slot 7 (`register_active_pt_package_resolver`) — registered but not yet consumed.
- Audit: `pt_package_plan_*`, `pt_package_sold`, `pt_package_cancelled`, `pt_package_refunded`, `pt_package_expired` callsites.
- Frontend: `/pt-package-plans` (owner) + `/pt-packages` list + detail (no session history yet).
- ARQ cron `expire_pt_packages` at 06:25 MSK (10-min stagger after expiring-notifications; pattern from v1.2 D-cron-ordering).

### Phase 34 — PT-session recording
- Migration 0015_pt_sessions.
- `pt_packages.service.record_pt_session` + cancel — DB-level race-proof decrement (UPDATE ... WHERE sessions_remaining > 0 RETURNING ...).
- Consumes Slot 4 (trainer resolver) + Slot 7 (active PT-package resolver).
- New endpoints: `POST /pt-sessions` + `POST /pt-sessions/{id}/cancel` (owner-only) + `GET /pt-sessions?clientId=` + `GET /pt-sessions/{id}`.
- Audit: `pt_session_recorded`, `pt_session_cancelled` callsites.
- Frontend: "record PT-session" panel on PT-package detail; session history list.

### Phase 35 — OpenAPI drift gate refresh + admin-web full wiring sweep
- Regenerate `openapi.json` + `schema.d.ts` (single atomic commit).
- admin-web: full http-mode pass on all new routes; `VITE_API_MODE=http` validation; mock-parity tests.
- New TanStack Query mutation hooks (sell-with-payment optimistic, refund non-optimistic + navigate, record-PT-session optimistic with rollback on decrement failure).
- Three-way RBAC parity assertion re-run.

### Phase 36 — Milestone verification (replicates Phase 29 v1.3 pattern)
- Operator runs cross-phase human scenarios:
  1. Sell membership with cash → see payment row on client card.
  2. Refund the membership → ledger shows two rows, membership status flips to refunded/cancelled.
  3. Sell PT-package → record 3 sessions with different trainers → balance ticks down.
  4. Refund half-used PT-package → confirm partial-refund policy (deferred discuss-phase: full vs prorated).
  5. Owner-only gate checks (reception → 403 on trainers CRUD, on PT-package plan CRUD).
  6. Cron ordering: `expire_memberships 06:05` → `send_expiring_notifications 06:15` → `expire_pt_packages 06:25` all idempotent.
- Live backend + Telegram sandbox.
- Capture 6 CI gate evidence (no new gates added).
- Operator sign-off in `milestones/v1.4-VERIFICATION-LOG.md`.

### Dependency-order rationale
- **Trainers first** because PT-sessions reference trainers. (Cannot record a session without a trainer catalog.)
- **Payments before PT-packages** because PT-package sale reuses the recorder slot; landing PT-packages first would force a second migration on the sale path.
- **PT-package instances before PT-sessions** because sessions reference a package and decrement its counter; the instance schema and resolver must exist first.
- **OpenAPI/admin-web sweep at the end**, not per-phase: one byte-stable regen avoids the per-phase drift-gate churn that bloated v1.2 / v1.3 phases.
- **Foundations Phase 30 first** so all subsequent phases pass `LOCKED_AUDIT_EVENTS` + RBAC parity from their first commit (v1.3 INFRA-15 lesson).

## Open architectural questions for discuss-phase

1. **Refund — full or prorated?** For a 30-day membership cancelled on day 10, does the refund row equal full price or 2/3 of price? Scope text says "ресепшен возвращает деньги напрямую" — silent on amount. **Recommendation: full refund in v1.4** (matches "симуляция продажи без денег" → "симуляция возврата без денег"; pro-rata adds complexity that is not in scope; the operator can adjust the amount manually before confirming if the form allows an editable field). Confirm.

2. **Multiple payments per membership?** If a client pays half cash now + half later, is that two `payment_recorded` rows pointing at the same `subject_id` membership, or is the second one a separate type? **Recommendation: yes, allow multiple payment rows per `subject_id`** (the schema already supports it; no UNIQUE on `subject_id`). Sale flow inserts one row; future "add additional payment" UI is post-v1.4. Confirm operator wants this open or wants a UNIQUE constraint.

3. **PT-session "cancel" or "delete"?** Phase 34 surface — when reception mis-records a session, is the row soft-cancelled (`cancelled_at` populated, balance restored) or hard-deleted? **Recommendation: soft-cancel** (audit trail, mirrors visits-style discipline). Owner-only per RBAC table above.

4. **`(REFUND, MEMBERSHIPS)` / `(REFUND, PT_PACKAGES)` — reception or owner?** Milestone text is explicit: reception, without owner approval. But this is a notable departure from v1.2 where `(CANCEL, MEMBERSHIPS)` is owner-only. **Recommendation: confirm** — if reception can refund, can they also cancel-without-refund (i.e. avoid the payment reversal)? Or are cancel and refund now operationally the same action, with cancel-only being an owner-only escape hatch?

5. **Active-PT-package resolver tiebreak** — if a client has two active PT-packages (rare but possible if they buy two before exhausting the first), which one does the recorder decrement? **Recommendation: `start_date ASC, created_at DESC`** (same tiebreak as v1.3 memberships resolver — oldest live package consumed first, predictable FIFO). Confirm.

6. **Cron stagger for `expire_pt_packages`** — pick 06:25 MSK (10 min after expiring-notifications) for the same "no ordering races, all idempotent" rationale as v1.2 cron-ordering. Confirm no operator scheduling conflicts.

7. **Telegram bot extension** — does v1.4 add any `/pt_packages` or `/payments` commands? **Recommendation: no.** Out of scope. Bot stays at `/start` + `/checkin`. Confirm.

8. **Trainer phone E.164 validation** — reuse the `clients/` E.164 validator? **Recommendation: yes**, lift the helper to `app/core/` if not already there (clean opportunity surfaced by trainers module).

## Sources

- `/Users/andre/Workspace/Development/clubcore/.planning/PROJECT.md` — invariants, completed-milestone summaries, key-decisions table
- `/Users/andre/Workspace/Development/clubcore/apps/backend/.importlinter` — three contracts
- `/Users/andre/Workspace/Development/clubcore/apps/backend/app/main.py` — composition root, three Protocol registrations
- `/Users/andre/Workspace/Development/clubcore/apps/backend/app/core/dependencies.py` — Protocol slot patterns (lines 33–192)
- `/Users/andre/Workspace/Development/clubcore/apps/backend/app/core/permissions.py` — `Role`/`Action`/`Resource` enums, `OWNER_ONLY` frozenset
- `/Users/andre/Workspace/Development/clubcore/apps/backend/app/core/audit.py` — `LOCKED_AUDIT_EVENTS` frozenset + emit gate
- `/Users/andre/Workspace/Development/clubcore/apps/backend/app/modules/memberships/router.py` + `models.py` + `service.py` — closest analog for plan + instance + lifecycle module
- `/Users/andre/Workspace/Development/clubcore/apps/backend/alembic/versions/` — 0001–0010 migration history
- `/Users/andre/Workspace/Development/clubcore/apps/admin-web/src/shared/session/can.ts` — frontend RBAC mirror (parity contract)
- `/Users/andre/Workspace/Development/clubcore/apps/backend/app/workers/telegram_bot.py` — bot-process Protocol-registration mirror (REG-29-03 lesson)
