# Phase 33: PT-Package Plans + Instances — Context

**Gathered:** 2026-05-15
**Status:** Ready for planning
**Mode:** `/gsd-discuss-phase 33` → user selected **Auto (recommended defaults)** — single pass; recommended defaults selected for every gray area; full audit trail in `33-DISCUSSION-LOG.md`.

<domain>
## Phase Boundary

Phase 33 материализует PT-пакеты как новый тариф рядом с месячными memberships, переиспользуя append-only payment ledger из Phase 32 и Resource/audit/RBAC bedrock из Phase 30. Конкретно:

- **Две миграции**: `0013_pt_package_plans.py` (тариф-каталог) + `0014_pt_packages.py` (instance per client). Раздельные revisions — `pt_packages` FK ссылается на `pt_package_plans` (depend-on dependency), и две таблицы концептуально разделены (catalog vs instance) — мы НЕ повторяем Phase 32 «mixed migration» pattern (там был ALTER+CREATE одной revision из-за refund cross-table требования; здесь semantic decoupling выгоднее).
- **`pt_package_plans`** (тариф каталог, owner-only CRUD `/api/v1/pt-package-plans`): `id`, `name`, `session_count INT CHECK > 0` (immutable), `price_kopecks INT CHECK > 0` (immutable), `validity_days INT NULL CHECK > 0` (immutable; NULL = бессрочный по времени), `deleted_at` (soft-delete). Partial UNIQUE `lower(name) WHERE deleted_at IS NULL` (mirrors v1.2 Phase 16 membership_plans).
- **`pt_packages`** (instance per client, reception+owner sell/refund, owner-only cancel): полный snapshot suite (`plan_name_snapshot`, `session_count_snapshot`, `price_kopecks_snapshot`, `validity_days_snapshot NULL`), `sessions_remaining INT NOT NULL CHECK >= 0 AND <= session_count_snapshot`, `status TEXT CHECK IN ('active','exhausted','expired','cancelled')`, `start_date DATE DEFAULT today(Europe/Moscow)`, `end_date DATE NULL` (computed-and-stored as `start_date + validity_days_snapshot - 1`; NULL когда validity_days_snapshot NULL), `cancellation_reason TEXT NULL`. Partial UNIQUE `(client_id) WHERE status='active'` — один активный пакет на клиента (Q5 default; multi-package в v1.5).
- **Новый модуль** `app/modules/pt_packages/` уже создан placeholder'ом в Phase 30 (`app/modules/pt_packages/service.py` пустой со SVC001 walker scope). Phase 33 разворачивает полный shape (constants/models/repository/schemas/service/router); `app/modules/pt_packages/__init__.py` уже existed для модуля-маркера.
- **PT-package status FSM** (`PT_PACKAGE_STATUS_TRANSITIONS` MappingProxyType в `pt_packages/constants.py`):
  - `active → {exhausted, expired, cancelled}`
  - `exhausted → {cancelled}` (refund of exhausted pkg)
  - `expired → {cancelled}` (refund of expired pkg)
  - `cancelled → ∅` (terminal)
  Центральный `_assert_can_transition(package, *, target)` + thin wrappers per transition (`_assert_can_cancel`, `_assert_can_expire`, `_assert_can_exhaust`) — mirrors v1.3 D-24-05 memberships pattern.
- **Sale flow** (`POST /api/v1/pt-packages`, reception+owner): `Idempotency-Key` required (PAY-09 forward seam — same Redis namespace `sz:idem:{key}` reused from Phase 32 `app.core.idempotency` dependency); body `{client_id, plan_id, amount_kopecks}` (clients schema layer rejects extras с `extra='forbid'`). Server: load `pt_package_plans WHERE id=:plan_id AND deleted_at IS NULL` (404 `pt_package_plan_not_found` if archived/missing); snapshot 4 поля; check `EXISTS (active pkg for client_id)` → 409 `active_pt_package_already_exists`; INSERT instance с `sessions_remaining = session_count_snapshot` + computed `end_date`; вызов `payment_recorder` Protocol slot в той же UoW с `subject_kind='pt_package'`, `amount_kopecks == price_kopecks_snapshot` (snapshot symmetry mirrors v1.2 membership sale); emit `pt_package_sold`. IntegrityError на `uq_pt_packages_active_per_client` → 409 `active_pt_package_already_exists` (DB-layer race-safe гарант).
- **Cancel-without-refund** (`POST /api/v1/pt-packages/{id}/cancel`, owner-only): body `{reason: str ≤200}` (required, `extra='forbid'`). Сервис: load instance, `_assert_can_transition(target='cancelled')`, set `status='cancelled'` + `cancellation_reason = <free-text reason>`; emit `pt_package_cancelled`. **Distinct from refund** (REF-02) — НЕ записывает negative-amount payment row, НЕ переиспользует `payment_refunder`.
- **Refund flow** (`POST /api/v1/pt-packages/{id}/refund`, REF-02, reception+owner per B-07): body schema `PtPackageRefundRequest { reason: str ≤200 }` с `model_config = ConfigDict(extra='forbid')` — symmetric к Phase 32 D-32-13 `MembershipRefundRequest`. Orchestrator `pt_packages.service.refund_pt_package(session, *, pt_package_id, actor, reason)` (own the UoW, explicit `await session.commit()`):
  1. Load instance (404 `pt_package_not_found`).
  2. Status guard через `_assert_can_transition(target='cancelled')` — allowed sources `{active, exhausted, expired}`; `cancelled` источник → 409 `invalid_transition`. **NO** freeze guard (v1.4 НЕ freezes PT-packages), **NO** renewed-source guard (нет PT-package renewal в v1.4).
  3. Load ORIGINAL sale payment: `SELECT * FROM payments WHERE subject_kind='pt_package' AND subject_id=:pt_package_id AND amount_kopecks > 0 ORDER BY received_at ASC LIMIT 1` (404 `original_payment_not_found` если missing — should not happen после Phase 33 land; legacy fall-through impossible так как пакеты вводятся в этом phase).
  4. Call `payments.service.issue_refund(...)` через `core.dependencies.get_payment_refunder()` Protocol slot (НЕ direct import — `modules-independent` контракт).
  5. Transition `status → 'cancelled'` + set `cancellation_reason = 'refunded'` sentinel (новая константа `CANCELLATION_REASON_REFUNDED = 'refunded'` в `pt_packages/constants.py`, mirrors Phase 32 D-32-08).
  6. `audit.emit('pt_package_refunded', ...)` с payload `{pt_package_id, client_id, refund_payment_id, reason}`.
  7. `await session.flush()` (IntegrityError на `uq_payments_refund_of_alive` → 409 `already_refunded`).
  8. `await session.commit()`. Return `PtPackageResponse`.
- **Protocol slot `register_active_pt_package_resolver`** в `app/core/dependencies.py` (mirrors `register_active_membership_resolver`): `ActivePtPackage` Protocol class + `ActivePtPackageResolver = Callable[[AsyncSession, UUID], Awaitable[ActivePtPackage | None]]` type alias + module-level slot `_active_pt_package_resolver` + register/get accessors. Wired EXCLUSIVELY из `app/main.py:create_app()` (НЕ из `telegram_bot.py:main()` — bot не consumer для PT-сессий; mirrors Phase 32 D-32-14 payment recorder discipline). Phase 34 PT-session router consumes этот slot для валидации active package при recording.
- **Read API**:
  - `GET /api/v1/pt-package-plans` (owner-only, фильтр `?include_archived=false` default) + `GET /api/v1/pt-package-plans/{id}` — pagination envelope.
  - `GET /api/v1/pt-packages?client_id=...&status=active` (reception+owner) — для PT-session form prefill в Phase 35.
  - `GET /api/v1/pt-packages/{id}` (reception+owner) — instance со snapshot + `sessions_remaining` + `start_date` + `end_date` + `status` + computed `is_active` boolean.
- **ARQ cron `expire_pt_packages`** в `app/workers/scheduled/expire_pt_packages.py` (mirrors `expire_memberships.py` shape verbatim): `cron(expire_pt_packages, hour=3, minute=25, unique=True, keep_result=60)` в `WorkerSettings.cron_jobs` (контейнер `TZ=UTC` ⇒ 06:25 Europe/Moscow). Worker — transaction owner, вызывает service helper `pt_packages.service._expire_due_pt_packages(session)` (с `# noqa: SVC001 caller-owns-txn`); helper делает bulk UPDATE `pt_packages SET status='expired' WHERE status='active' AND end_date IS NOT NULL AND end_date < CURRENT_DATE AT TIME ZONE 'Europe/Moscow'` + per-row `audit.emit('pt_package_expired', ...)`; commit в worker; structlog summary `expire_pt_packages_complete count=N` AFTER commit (Phase 18 CD-03 convention). Идемпотент: re-run в тот же день — `WHERE status='active'` SQL guard skip'ает уже-expired rows.
- **5 audit events** (все pre-registered в Phase 30 INFRA-17 `LOCKED_AUDIT_EVENTS`):
  - `pt_package_plan_created` / `pt_package_plan_updated` / `pt_package_plan_archived` — plan CRUD lifecycle.
  - `pt_package_sold` / `pt_package_cancelled` / `pt_package_refunded` (subject-side; payment-side `refund_issued` уже existed) / `pt_package_exhausted` / `pt_package_expired` — instance lifecycle.
  - Plan 30-01 audit_payloads.py defines schemas; **VERIFY** на planning phase что `PtPackageRefundedPayload` ожидает {pt_package_id, client_id, refund_payment_id, reason}. Если не точно — planner добавляет supplementary plan для дополнения schema (additive change в frozenset BANNED — но добавление полей в Pydantic model OK).
- **SVC001 walker scope**: уже extended в Phase 30 INFRA-21 на `pt_packages/service.py`. Все state-mutating service functions (`create_pt_package`, `cancel_pt_package`, `refund_pt_package`, `_expire_due_pt_packages`) MUST либо `await session.commit()` либо declare `# noqa: SVC001 caller-owns-txn` в docstring (для helper'ов typа `_expire_due_pt_packages`).
- **append-only AST guard** (Plan 30-03 `tests/unit/test_payments_appendonly.py`): Phase 33 НЕ trigger'ит этот gate — `pt_packages` НЕ append-only (status mutates, sessions_remaining decrements в Phase 34); только `payments` table защищена этим walker'ом. PT-package refund INSERTS payment row, что уже разрешено.
- **`.importlinter` modules-independent**: `app.modules.pt_packages` уже в контракте (Phase 30 INFRA-20). PT-package service НЕ может импортировать `payments.service` напрямую — consumes через `core.dependencies.get_payment_recorder() / get_payment_refunder()` Protocol slots. Cross-module communication ИСКЛЮЧИТЕЛЬНО через `app.core.*`.

**13 requirements в scope**: PT-01..PT-13 (см. `.planning/REQUIREMENTS.md` §76-93).

**Out of scope (deferred / handled elsewhere):**
- PT-sessions table + sale + cancel + decrement + auto-exhausted transition (`pt_sessions` table) — **Phase 34** (PT-14..22).
- Trainer-active validation в PT-session sale — **Phase 34** (consumes `register_trainer_by_id_resolver` slot из Phase 31).
- admin-web `/pt-package-plans` route + `/pt-packages` list/detail + PaymentBadge + PtPackageStatusBadge + mock parity — **Phase 35** (FE-10..18).
- OpenAPI byte-stable regen и `schema.d.ts` — **Phase 35**.
- Multi-package per client (lift `(client_id) WHERE status='active'` partial UNIQUE) — **v1.5**.
- PT-package renewal carry-over — **v1.5+** (Q8 expansion).
- Telegram bot `/pt_packages` self-balance check — **v1.5+** (Q15).
- Pro-rata refunds — **out of v1.4 entirely** (B-02 full-only).
- `pt_package_refunded` payload hash (parity с `refund_issued`) — Phase 30 explicit'но deferred hash на membership/pt_package subject-side; только `refund_issued` payment-side hash в v1.4.

</domain>

<decisions>
## Implementation Decisions

### D-33-01: Migration split — two separate revisions (0013 + 0014)

- `0013_pt_package_plans.py`: revision = `"0013_pt_package_plans"`, down_revision = `"0012_payments"`. Single concern: `CREATE TABLE pt_package_plans`.
- `0014_pt_packages.py`: revision = `"0014_pt_packages"`, down_revision = `"0013_pt_package_plans"`. Single concern: `CREATE TABLE pt_packages` (FK to pt_package_plans + clients).
- **Why:** Catalog vs instance — concepts decoupled; instances FK plans, so plans MUST exist first; separating revisions allows future operators (e.g., zero-downtime data migration on instances) to land without touching plans schema. Differs from Phase 32 D-32-01 mixed migration because there refund flow needed BOTH `payments` and ALTER `memberships.cancellation_reason` simultaneously; here no such cross-table necessity.

### D-33-02: `pt_package_plans` columns (PT-01)

- `id UUID PK DEFAULT gen_random_uuid()` (UUIDPkMixin per INFRA-02).
- `name TEXT NOT NULL` — display name (e.g., «10 тренировок»).
- `session_count INT NOT NULL CHECK > 0` — immutable post-create (PATCH rejects 409).
- `price_kopecks INT NOT NULL CHECK > 0` — immutable post-create.
- `validity_days INT NULL CHECK > 0` — NULL = no time-expiry (no `end_date` derivation downstream). Immutable post-create.
- `deleted_at TIMESTAMPTZ NULL` — soft-delete (SoftDeleteMixin).
- `created_at` / `updated_at` from TimestampMixin.
- Partial UNIQUE `lower(name) WHERE deleted_at IS NULL` (mirrors v1.2 Phase 16 membership_plans `uq_membership_plans_name_alive`).

### D-33-03: `pt_packages` columns (PT-04, PT-05)

- `id UUID PK DEFAULT gen_random_uuid()`.
- `client_id UUID NOT NULL REFERENCES clients(id) ON DELETE RESTRICT`.
- `plan_id UUID NOT NULL REFERENCES pt_package_plans(id) ON DELETE RESTRICT` (snapshot pattern — archive of plan keeps historical instances readable).
- **Snapshot fields (NOT NULL except validity_days):**
  - `plan_name_snapshot TEXT NOT NULL`
  - `session_count_snapshot INT NOT NULL CHECK > 0`
  - `price_kopecks_snapshot INT NOT NULL CHECK > 0`
  - `validity_days_snapshot INT NULL CHECK > 0` (если NULL — package бессрочный, `end_date IS NULL`, ARQ cron skip'ает).
- `sessions_remaining INT NOT NULL CHECK >= 0 AND <= session_count_snapshot` (table-level CHECK — defence-in-depth для Phase 34 decrement).
- `status TEXT NOT NULL CHECK IN ('active','exhausted','expired','cancelled')`.
- `start_date DATE NOT NULL DEFAULT (now() AT TIME ZONE 'Europe/Moscow')::date` — Europe/Moscow business day (mirrors v1.2 memberships start_date discipline).
- `end_date DATE NULL` — computed-and-stored: `start_date + validity_days_snapshot - 1` если validity_days_snapshot NOT NULL; NULL otherwise. **Stored**, не virtual/computed column — Postgres GENERATED ALWAYS вариант избегаем (downstream tools / fixture parity проще на plain INSERT). Application-layer computation в `pt_packages.service.create_pt_package`.
- `cancellation_reason TEXT NULL` — sentinel `'refunded'` для refund flow, или free-text для admin cancel. Same shape как memberships.cancellation_reason (Phase 32 D-32-07).
- `created_at` / `updated_at` (TimestampMixin).
- Partial UNIQUE `(client_id) WHERE status = 'active'` → `uq_pt_packages_active_per_client` (PT-05; one active package per client at a time).
- Indexes: `ix_pt_packages_client_id`, `ix_pt_packages_status`, `ix_pt_packages_plan_id`.

### D-33-04: `PT_PACKAGE_STATUS_TRANSITIONS` constant (PT-06)

В `app/modules/pt_packages/constants.py`:
```python
PT_PACKAGE_STATUS_TRANSITIONS: Mapping[str, frozenset[str]] = MappingProxyType({
    "active": frozenset({"exhausted", "expired", "cancelled"}),
    "exhausted": frozenset({"cancelled"}),  # refund of exhausted
    "expired": frozenset({"cancelled"}),    # refund of expired
    "cancelled": frozenset(),               # terminal
})
```
Plus `_assert_can_transition(package, *, target)` central guard + thin wrappers `_assert_can_cancel(package)` / `_assert_can_expire(package)` / `_assert_can_exhaust(package)` — mirrors v1.3 D-24-05 memberships pattern verbatim.

### D-33-05: Module shape

`app/modules/pt_packages/`:
- `__init__.py` (existing — module marker).
- `constants.py` — `PT_PACKAGE_STATUS_TRANSITIONS` + `CANCELLATION_REASON_REFUNDED = 'refunded'` sentinel + `PAYMENT_SUBJECT_KIND_PT_PACKAGE = 'pt_package'` (Phase 32 D-32-09 precedent — string pinned to migration CHECK value).
- `models.py` — `PtPackagePlan` ORM + `PtPackage` ORM (with snapshot fields + Mapped[] attrs matching migration).
- `repository.py` — `find_plan_by_id`, `find_plan_by_name`, `find_active_for_client`, `find_pt_package_by_id`, `find_pt_packages_by_client`, `expire_due_pt_packages_bulk_returning`, `has_instances_for_plan` (для soft-delete 409 `plan_in_use` guard).
- `schemas.py` — `PtPackagePlanCreate`, `PtPackagePlanUpdate` (omits immutable fields; service-side guard still raises 409 `field_immutable` если хитро прислали через `extra='forbid'` bypass), `PtPackagePlanResponse`, `PtPackageCreate { client_id, plan_id, amount_kopecks }`, `PtPackageCancelRequest { reason: str ≤200 }`, `PtPackageRefundRequest { reason: str ≤200 }`, `PtPackageResponse`. All extend `BackendSchemaBase`; refund/cancel use `extra='forbid'` per REF-05 pattern.
- `service.py` — `create_pt_package_plan`, `update_pt_package_plan`, `archive_pt_package_plan`, `create_pt_package`, `cancel_pt_package`, `refund_pt_package`, `get_pt_package_by_id`, `list_pt_packages`, `_expire_due_pt_packages` (caller-owns-txn helper для cron), `_assert_can_transition` + wrappers.
- `router.py` — endpoints below.
- `permissions.py` — stub or thin wrapper (memberships pattern; `require_permission(Action.X, Resource.PT_PACKAGES)` напрямую в router'е).

### D-33-06: Endpoints + permissions (PT-02, PT-07..10)

| Method | Path | Auth | Action |
|---|---|---|---|
| POST | `/api/v1/pt-package-plans` | owner | `(CREATE, PT_PACKAGE_PLANS)` |
| GET | `/api/v1/pt-package-plans` | owner | `(VIEW, PT_PACKAGE_PLANS)` |
| GET | `/api/v1/pt-package-plans/{id}` | owner | `(VIEW, PT_PACKAGE_PLANS)` |
| PATCH | `/api/v1/pt-package-plans/{id}` | owner | `(UPDATE, PT_PACKAGE_PLANS)` |
| DELETE | `/api/v1/pt-package-plans/{id}` | owner | `(DELETE, PT_PACKAGE_PLANS)` |
| POST | `/api/v1/pt-packages` | reception+owner | `(CREATE, PT_PACKAGES)` |
| GET | `/api/v1/pt-packages?client_id=...&status=...` | reception+owner | `(LIST, PT_PACKAGES)` |
| GET | `/api/v1/pt-packages/{id}` | reception+owner | `(VIEW, PT_PACKAGES)` |
| POST | `/api/v1/pt-packages/{id}/cancel` | owner | `(CANCEL, PT_PACKAGES)` |
| POST | `/api/v1/pt-packages/{id}/refund` | reception+owner | `(REFUND, PT_PACKAGES)` (B-07) |

All POST/PATCH/DELETE: CSRF required (Phase 4 idempotent-CSRF pattern). POST `/pt-packages` + POST `/pt-packages/{id}/refund` + POST `/pt-packages/{id}/cancel`: `Idempotency-Key` header **required** (PAY-09 forward seam; reuses `app.core.idempotency` Redis namespace `sz:idem:{key}`).

### D-33-07: PATCH plan immutability — 409 `field_immutable` at service layer

`PtPackagePlanUpdate` schema **includes** `session_count`/`price_kopecks`/`validity_days` as `Optional[int]` so the service can detect attempts and return the locked 409 code (instead of 422 schema-layer rejection that would happen if we omitted them). Service compares incoming non-None values to current row values; if **any** of the three immutable fields differs, raise `FieldImmutableError("field_immutable")` → 409. Mutable fields (`name`) update normally. Mirrors v1.2 membership_plans immutability discipline.

**Why:** Roadmap SC #2 verbatim locks 409 `field_immutable` code. Schema-layer 422 на `extra='forbid'` not equivalent (different error code/shape).

### D-33-08: Soft-delete plan with instance — 409 `plan_in_use`

DELETE `/pt-package-plans/{id}` runs `repository.has_instances_for_plan(plan_id)` → if true, raise 409 `plan_in_use`; else set `deleted_at = now()`. Existing pt_packages instances continue to work via snapshot fields. Sale endpoint filters `deleted_at IS NULL` when loading plan → 404 `pt_package_plan_not_found` (deliberate — UI should never offer archived plans for new sales).

### D-33-09: Sale flow (PT-07)

`pt_packages.service.create_pt_package(session, *, client_id, plan_id, amount_kopecks, actor)`:
1. Load plan `WHERE id=:plan_id AND deleted_at IS NULL` (404 `pt_package_plan_not_found`).
2. Validate `amount_kopecks == plan.price_kopecks` (server-enforced snapshot symmetry; 422 `amount_mismatch` if client passes wrong amount — mirrors Phase 32 D-32-09 / Plan 32-02 sale-flow pattern).
3. Check active package existence: `SELECT id FROM pt_packages WHERE client_id=:client_id AND status='active' LIMIT 1` (defensive pre-check, 409 `active_pt_package_already_exists` if found; partial UNIQUE на DB layer is final gate).
4. Compute `end_date`: `start_date + plan.validity_days - 1` если validity_days NOT NULL else NULL. `start_date = now() AT TIME ZONE 'Europe/Moscow'`.
5. INSERT pt_packages row с full snapshot + `sessions_remaining = plan.session_count` + `status = 'active'`.
6. Call `payment_recorder(session, subject_kind='pt_package', subject_id=new_pt_package.id, amount_kopecks=plan.price_kopecks, received_by_user_id=actor.user_id, audit_actor=actor)` через `core.dependencies.get_payment_recorder()` (Protocol slot from Phase 32).
7. `audit.emit('pt_package_sold', payload={...})`.
8. `await session.flush()` → IntegrityError on `uq_pt_packages_active_per_client` → 409 `active_pt_package_already_exists`.
9. `await session.commit()`. Return `PtPackageResponse`.

`create_pt_package` is **the transaction owner** (mirrors `memberships.service.create_membership` Phase 32 D-32-11 pattern).

### D-33-10: Cancel flow (PT-08) — distinct from refund

`pt_packages.service.cancel_pt_package(session, *, pt_package_id, actor, reason)`:
1. Load instance (404 `pt_package_not_found`).
2. `_assert_can_transition(package, target='cancelled')` (allowed sources: `active`, `exhausted`, `expired`).
3. Set `status='cancelled'` + `cancellation_reason = <free-text reason>` (NOT sentinel `'refunded'` — that's reserved for refund flow).
4. `audit.emit('pt_package_cancelled', payload={pt_package_id, client_id, reason, prior_status})`.
5. `await session.flush()` + `await session.commit()`. Return `PtPackageResponse`.

**No payment row inserted.** Owner-only operation. Use case: operator commits a sales error без денежного refund (manual handling out-of-band).

### D-33-11: Refund flow (REF-02 / PT-12 cross-ref / B-07)

`pt_packages.service.refund_pt_package(session, *, pt_package_id, actor, reason)` — orchestrator owns UoW:
1. Load instance (404 `pt_package_not_found`).
2. `_assert_can_transition(package, target='cancelled')`. Sources `{active, exhausted, expired}` → ok; `cancelled` → 409 `invalid_transition` (already cancelled).
3. Load ORIGINAL sale payment: `SELECT * FROM payments WHERE subject_kind='pt_package' AND subject_id=:pt_package_id AND amount_kopecks > 0 ORDER BY received_at ASC LIMIT 1`. 404 `original_payment_not_found` if missing.
4. Call `payments.service.issue_refund(...)` via `core.dependencies.get_payment_refunder()` — passes `original_payment_id` + `refund_user_id=actor.user_id` + `reason` + `audit_actor=actor`. `issue_refund` computes `payment_row_hash` SHA-256 over 8 stable columns of original (Phase 32 D-32-02), INSERTS negative-amount refund row, emits `refund_issued` payment-side. Returns new refund Payment instance.
5. Transition `status → 'cancelled'` + set `cancellation_reason = CANCELLATION_REASON_REFUNDED` ('refunded' sentinel).
6. `audit.emit('pt_package_refunded', payload={pt_package_id, client_id, refund_payment_id, reason})` — subject-side. Chain order: `payment_recorded` (от sale-time) → `refund_issued` (payment-side, в issue_refund) → `pt_package_refunded` (subject-side, в orchestrator).
7. `await session.flush()` → IntegrityError on `uq_payments_refund_of_alive` → 409 `already_refunded` (Phase 32 D-32-04 race gate).
8. `await session.commit()`. Return `PtPackageResponse`.

**NO renewal guard** (v1.4 не имеет PT-package renewal). **NO freeze guard** (v1.4 не имеет PT-package freeze). Только `invalid_transition` + `already_refunded` (DB race) + `original_payment_not_found` (data integrity).

### D-33-12: Protocol slot `register_active_pt_package_resolver` (PT-11)

В `app/core/dependencies.py` после existing `ActiveMembership` block:
```python
class ActivePtPackage(Protocol):
    id: UUID
    client_id: UUID
    status: str
    sessions_remaining: int
    end_date: date | None

ActivePtPackageResolver = Callable[[AsyncSession, UUID], Awaitable[ActivePtPackage | None]]

_active_pt_package_resolver: ActivePtPackageResolver | None = None

def register_active_pt_package_resolver(resolver: ActivePtPackageResolver) -> None: ...
async def get_active_pt_package(session: AsyncSession, client_id: UUID) -> ActivePtPackage | None: ...
```
Wired EXCLUSIVELY из `app/main.py:create_app()` (НЕ в telegram_bot.py — bot не consumer для PT-сессий; mirror Phase 32 D-32-14). Resolver implementation в `pt_packages/__init__.py` exports `resolve_active_pt_package(session, client_id)`. Phase 34 PT-session sale consumes этот slot для валидации.

**Slot accessor:** silent-None pattern (mirrors `_active_membership_resolver` Phase 17 D-18 — НЕ defensive raise like `payment_recorder`; consumer treats None как «no active package»).

### D-33-13: ARQ cron `expire_pt_packages` (PT-12)

- File: `app/workers/scheduled/expire_pt_packages.py` — mirrors `expire_memberships.py` shape verbatim. Worker is transaction owner.
- Registered в `app/workers/__init__.py:WorkerSettings`:
  - `functions += [expire_pt_packages]`.
  - `cron_jobs += [cron(expire_pt_packages, hour=3, minute=25, unique=True, keep_result=60)]`.
  - **Cron-resolution invariant test** в `apps/backend/tests/unit/test_worker_cron_resolution.py` — extends existing assertion `c.coroutine in (f for f in functions)` to ensure pt_package cron entry references registered function (Pitfall 4 step 6).
- Service helper `pt_packages.service._expire_due_pt_packages(session)` (with `# noqa: SVC001 caller-owns-txn`):
  - Bulk UPDATE: `UPDATE pt_packages SET status='expired', updated_at=now() WHERE status='active' AND end_date IS NOT NULL AND end_date < (now() AT TIME ZONE 'Europe/Moscow')::date RETURNING id, client_id`.
  - Per-row `audit.emit('pt_package_expired', payload={pt_package_id, client_id, end_date})`.
  - Return count (int).
- Idempotent: `WHERE status='active'` predicate skips already-expired rows on re-run.
- Summary log AFTER commit: `_log.info("expire_pt_packages_complete", count=N)` (Phase 18 CD-03 convention).

### D-33-14: Cron edge case — `validity_days_snapshot IS NULL` instances

Packages с NULL validity_days_snapshot имеют `end_date IS NULL`. ARQ cron SQL filter `end_date IS NOT NULL AND end_date < today` исключает их из bulk UPDATE — они никогда не expire по времени (только по exhaustion в Phase 34 или manual cancel). Это контракт «бессрочный пакет до истощения».

### D-33-15: 5 audit events (PT-03 + PT-13)

Все уже в `LOCKED_AUDIT_EVENTS` (Phase 30 INFRA-17). Payload schemas в `app/modules/audit/audit_payloads.py` (Plan 30-01) — **planner MUST verify** что schemas совпадают с D-33-09/-10/-11/-13/-14 payload shapes:

| Event | Payload (verify в planning) |
|---|---|
| `pt_package_plan_created` | `{plan_id, name, session_count, price_kopecks, validity_days}` |
| `pt_package_plan_updated` | `{plan_id, name?, changes: dict}` (только mutable fields) |
| `pt_package_plan_archived` | `{plan_id, name}` |
| `pt_package_sold` | `{pt_package_id, client_id, plan_id, plan_name_snapshot, session_count_snapshot, price_kopecks_snapshot, validity_days_snapshot, start_date, end_date}` |
| `pt_package_cancelled` | `{pt_package_id, client_id, reason, prior_status}` |
| `pt_package_refunded` | `{pt_package_id, client_id, refund_payment_id, reason}` |
| `pt_package_exhausted` | `{pt_package_id, client_id, exhausted_at}` (emit в Phase 34 на decrement→0 + в Phase 33 manual-exhaust никогда) |
| `pt_package_expired` | `{pt_package_id, client_id, end_date}` |

`pt_package_exhausted` — Phase 33 НЕ emits (no decrement code yet); zhe тa event LANDED audit-wise в Phase 30 для downstream Phase 34. **`LOCKED_AUDIT_EVENTS` контракт** разрешает событие зарегистрированным без callsite — Phase 24/25 precedent (audit events были pre-registered за phase до first emit).

### D-33-16: Idempotency-Key reuse

POST `/pt-packages` + POST `/pt-packages/{id}/refund` + POST `/pt-packages/{id}/cancel` — **all three** require `Idempotency-Key` header (mirrors Phase 32 D-32-10 idempotency-on-money-mutating discipline). Reuses `app.core.idempotency.idempotency_dependency` from Phase 32 verbatim — same Redis namespace `sz:idem:{key}` 1h TTL; replay returns cached envelope; same-key/different-body → 422 `idempotency_key_reuse`.

### D-33-17: Snapshot symmetry server-enforced (PT-07 / mirrors PAY-05)

`create_pt_package` validates `amount_kopecks == plan.price_kopecks` server-side BEFORE calling payment_recorder. If client passes wrong amount → 422 `amount_mismatch` (Pydantic field-level OR service-layer assertion; planner picks layer). Snapshot fields in pt_packages row written с plan values — NEVER trust client-provided snapshot.

### D-33-18: REF-02 router consolidation point

REF-02 (POST `/api/v1/pt-packages/{id}/refund`) lives в `pt_packages/router.py` (not `payments/router.py` или `memberships/router.py`). Resource ownership принцип: subject-side endpoints живут с subject module. Phase 32 wired Protocol slot consumer side; Phase 33 wires endpoint.

### D-33-19: Tests scope

- **Unit:** status FSM transitions exhaustive; immutability schema-vs-service split; cron SQL guard (active-only).
- **Integration (httpx ASGITransport):** plan CRUD owner-only + reception 403; sale golden path + snapshot symmetry mismatch 422; sale with archived plan 404; sale with already-active client 409; cancel owner-only; refund reception+owner; refund of expired/exhausted pkg ok; refund of cancelled 409 invalid_transition; concurrent refund race REF-TEST-02 (mirrors REF-TEST-01) — Postgres-only test marker, не SQLite.
- **Cron:** schedule expire_pt_packages tick, verify `pt_package_expired` audit per row; rerun same day = 0 rows updated; NULL end_date row не expired.
- **Worker resolution invariant:** assertion в `test_worker_cron_resolution.py` covers new cron entry.

### Claude's Discretion

- Exact module file layout follows memberships precedent — planner has discretion on internal helper splits (e.g., `_validate_sale_input` private vs inline).
- `permissions.py` может быть пустым stub'ом (memberships does it inline в router — same here).
- Test file naming follows `test_pt_packages_<concern>.py` convention из `test_memberships_<concern>.py`.
- Repository helpers signature: planner picks parameter shape (positional vs keyword-only) following existing repo conventions per file.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap / Requirements
- `.planning/ROADMAP.md` §«Phase 33: PT-Package Plans + Instances» — phase goal, depends-on, success criteria (5), plans hint.
- `.planning/REQUIREMENTS.md` §76-93 — PT-01..PT-13 detailed (13 requirements in scope).
- `.planning/REQUIREMENTS.md` §«Business Decisions» B-01, B-02, B-04, B-07, B-09, B-10, B-11 — append-only ledger, full-only refund, separate PT-packages module, uniform reception RBAC, renewal/freeze semantics, PT floor-access, backdating windows (Phase 34 only).
- `.planning/PROJECT.md` — Sportzal core value, region constraints (RUB/cash only v1.4).

### Phase 30 Bedrock (foundations consumed here)
- `.planning/phases/30-foundations-tech-debt-bedrock/30-CONTEXT.md` — full bedrock decisions.
- `.planning/phases/30-foundations-tech-debt-bedrock/30-01-PLAN.md` & `30-01-SUMMARY.md` — LOCKED_AUDIT_EVENTS 17 new events + Pydantic payload schemas (`audit_payloads.py`).
- `.planning/phases/30-foundations-tech-debt-bedrock/30-02-PLAN.md` & `30-02-SUMMARY.md` — Resource enum +5 + OWNER_ONLY frozenset +11 + admin-web byte-paritet.
- `.planning/phases/30-foundations-tech-debt-bedrock/30-03-PLAN.md` & `30-03-SUMMARY.md` — `.importlinter` modules-independent +3 (incl. pt_packages) + SVC001 walker scope +3 + append-only AST walker + module placeholders.
- `apps/backend/app/modules/audit/audit_payloads.py` — `PtPackageSoldPayload`, `PtPackageRefundedPayload`, etc. (verify shapes during planning).
- `apps/backend/app/modules/audit/locked_events.py` — `LOCKED_AUDIT_EVENTS` frozenset (51 entries).
- `apps/backend/app/core/permissions.py` — `Resource.PT_PACKAGES`, `Resource.PT_PACKAGE_PLANS`, OWNER_ONLY frozenset.

### Phase 32 Payment Ledger (consumed by sale + refund)
- `.planning/phases/32-payment-ledger-sale-flow-refund/32-CONTEXT.md` — payment ledger decisions.
- `.planning/phases/32-payment-ledger-sale-flow-refund/32-01-PLAN.md` & `32-01-SUMMARY.md` — migration 0012, payments module, Protocol slots, audit_hash, idempotency, GET endpoints.
- `.planning/phases/32-payment-ledger-sale-flow-refund/32-02-PLAN.md` & `32-02-SUMMARY.md` — sale-flow snapshot symmetry pattern (mirror for PT-07).
- `.planning/phases/32-payment-ledger-sale-flow-refund/32-03-PLAN.md` & `32-03-SUMMARY.md` — refund flow orchestrator pattern (mirror for REF-02).
- `apps/backend/app/core/dependencies.py:233-340` — `PaymentRecorder`/`PaymentRefunder` Protocol class + register/get accessors.
- `apps/backend/app/core/idempotency.py` — `idempotency_dependency` FastAPI dep + Redis cache (reuse verbatim for PT endpoints).
- `apps/backend/app/modules/payments/service.py` — `record_payment` + `issue_refund` (caller-owns-txn; consumed via Protocol slots).
- `apps/backend/app/modules/memberships/service.py:690-810` — `refund_membership` orchestrator (mirror shape for `refund_pt_package`).

### Phase 17/18 ARQ / Memberships precedents
- `apps/backend/app/workers/__init__.py` — WorkerSettings + cron_jobs + cron-resolution invariant.
- `apps/backend/app/workers/scheduled/expire_memberships.py` — mirror shape verbatim для expire_pt_packages.
- `apps/backend/app/modules/memberships/constants.py:22-30` — `MEMBERSHIP_STATUS_TRANSITIONS` (mirror for `PT_PACKAGE_STATUS_TRANSITIONS`).
- `apps/backend/app/modules/memberships/service.py:194-260` — `_assert_can_transition` central guard + thin wrappers (mirror pattern).
- `apps/backend/app/core/dependencies.py:65-130` — `ActiveMembership` Protocol + `register_active_membership_resolver` + silent-None accessor (mirror for ActivePtPackage).
- `apps/backend/app/modules/clients/`, `apps/backend/app/modules/memberships/` — module shape reference (constants/models/repository/schemas/service/router layout).

### Cross-cutting infra
- `apps/backend/app/schemas/base.py` — `BackendSchemaBase`, `to_camel`, `BackendResponseModel`.
- `apps/backend/app/core/audit_hash.py` — `payment_row_hash` helper (Phase 32 D-32-02; pt_package refund flow consumes through `issue_refund`).
- `apps/backend/tests/unit/test_payments_appendonly.py` — append-only AST walker (Phase 33 NOT trigger gate but tests must pass с new PT inserts).
- `apps/backend/tests/unit/test_worker_cron_resolution.py` — cron invariant test (extend для expire_pt_packages).
- `apps/backend/tests/unit/test_modules_independent.py` (or .importlinter contract) — verify `pt_packages` НЕ imports `payments`/`memberships`/`trainers` directly.

### Migration ordering
- `apps/backend/alembic/versions/0012_payments.py` — down_revision target for 0013.
- `apps/backend/alembic/versions/0011_trainers.py` — predecessor of 0012 (no direct dep, just sequence).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`memberships/service.refund_membership`** — full orchestrator template; PT-package refund is 70% copy-with-adjustments (no freeze guard, no renewal guard, different subject_kind).
- **`memberships/service.create_membership`** — sale-flow + payment_recorder consumption pattern; PT-package sale follows verbatim minus duration-days specifics.
- **`memberships/constants.MEMBERSHIP_STATUS_TRANSITIONS`** — declarative FSM Mapping pattern.
- **`memberships/service._assert_can_transition`** — central guard + thin wrappers; copy-paste-adjust for PT.
- **`payments/service.issue_refund`** + **`payments/service.record_payment`** — already done in Phase 32; PT-package consumes ABI unchanged.
- **`core.dependencies` Protocol slot machinery** — `ActiveMembership` resolver pattern for `ActivePtPackage`; `PaymentRecorder`/`PaymentRefunder` already wired and consumed.
- **`core.idempotency.idempotency_dependency`** — FastAPI Depends consumed by `POST /memberships` (Phase 32 D-32-10); reused as-is on PT-package endpoints.
- **`workers.scheduled.expire_memberships`** — cron job shape verbatim for `expire_pt_packages`.
- **`workers.__init__` cron-resolution invariant** — extends to новый cron entry.
- **`audit.locked_events.LOCKED_AUDIT_EVENTS`** + **`audit_payloads.py` schemas** — all 5 PT events pre-registered in Phase 30 INFRA-17 (with payload schemas defined в Plan 30-01).
- **`permissions.Resource.PT_PACKAGES` / `PT_PACKAGE_PLANS`** + OWNER_ONLY entries — already extended в Phase 30 INFRA-19 (`(CREATE, PT_PACKAGES)` and `(REFUND, PT_PACKAGES)` are NOT в OWNER_ONLY → reception+owner; `(CANCEL, PT_PACKAGES)`, `(DELETE, PT_PACKAGES)`, all CRUD on PT_PACKAGE_PLANS — in OWNER_ONLY).
- **`schemas/base.BackendSchemaBase`** + camelCase alias generator — used by all module schemas.
- **`.importlinter` `modules-independent` contract** — `pt_packages` already listed; planner must NOT add direct imports across modules.
- **SVC001 AST commit-gate walker** — scope already covers `pt_packages/service.py` from Phase 30 INFRA-21.

### Established Patterns
- **Caller-owns-txn discipline (D-03)**: orchestrators commit; helpers don't. `refund_pt_package` / `create_pt_package` / `cancel_pt_package` commit; `_expire_due_pt_packages` (cron helper) doesn't (worker commits).
- **Snapshot symmetry**: plan archived → existing instances readable via snapshot fields. Sale validates `amount_kopecks == plan.price_kopecks` server-side.
- **Partial UNIQUE для active-only invariants**: `WHERE status='active'` proven pattern (memberships freeze, payments refund_of) — race-safe via DB layer.
- **Status FSM via MappingProxyType + central guard**: enforced runtime через `_assert_can_transition`.
- **Locked audit events frozenset + payload schemas via Pydantic**: all 5 PT events already locked; planning verifies payload shape match.
- **Protocol slots for cross-module communication**: registered in `app/main.py` only (defensive raise for required slots, silent None for optional resolvers).
- **Pagination envelope `{items, total, page, pageSize}`** для GET list endpoints.
- **Audit chain readable through `audit_log.created_at` ASC**: ordering for forensic traceability (sale → refund_issued → subject_refunded).

### Integration Points
- **`app/main.py:create_app()`**: register `active_pt_package_resolver` (Phase 33 wires; Phase 34 consumes).
- **`core/dependencies.py`**: add `ActivePtPackage` Protocol + `_active_pt_package_resolver` slot + register/get accessors.
- **`workers/__init__.py:WorkerSettings`**: add `expire_pt_packages` to `functions` + `cron_jobs`.
- **`router.py` aggregation** (`app/api/__init__.py` or equivalent): mount `pt_packages_router` + `pt_package_plans_router` (planner verifies actual aggregation file).
- **Migration `0014_pt_packages.py`**: FK to `pt_package_plans.id` + `clients.id` (both `ON DELETE RESTRICT`).
- **audit_payloads.py schemas**: planner verifies (and supplements if mismatch) all 5 PT event payload shapes match D-33-09/-10/-11/-13 fields.
- **OpenAPI / `schema.d.ts` regen**: NOT in Phase 33 — Phase 35 owns codegen. Backend endpoints land here; FE wiring deferred.

</code_context>

<specifics>
## Specific Ideas

- **Russian-locale strings** in audit-event payload `reason` fields and `cancellation_reason` — passthrough str, no enum coercion (operator types free-text).
- **`'refunded'` sentinel constant** in pt_packages/constants.py mirrors Phase 32 D-32-08 — symbol not magic string.
- **Atomic refund chain** (load original → issue_refund → transition+sentinel → emit subject_refunded → commit) — single transaction; partial state impossible.
- **Concurrent refund race REF-TEST-02** (Postgres-only) mirrors Phase 32 REF-TEST-01 verbatim shape: spawn 2 concurrent `POST /pt-packages/{id}/refund` against same instance → exactly one 201, other 409 `already_refunded` via partial UNIQUE.
- **Cron MSK→UTC translation**: container `TZ=UTC` per Phase 18 D-09; `hour=3, minute=25` UTC = 06:25 Europe/Moscow (winter standard; Europe/Moscow does NOT observe DST since 2014 — single offset +03:00 year-round).
- **`pt_package_exhausted` event** registered but NOT emitted from Phase 33 code — emit callsite lives in Phase 34 PT-session decrement orchestrator. Phase 30 precedent established: pre-registration без callsite OK.

</specifics>

<deferred>
## Deferred Ideas

- **`pt_package_refunded` payload hash** parity с `refund_issued` SHA-256 hash — out of v1.4 (Phase 30 explicit deferred subject-side hashing; only payment-side `refund_issued` uses hash в v1.4).
- **Pro-rata refunds** для partially-used PT-packages — out of v1.4 (B-02 full-only).
- **Multi-package per client** (drop `(client_id) WHERE status='active'` partial UNIQUE) — v1.5.
- **PT-package renewal** (carry-over unused sessions) — v1.5+ (Q8 expansion). При landing renewal — add renewed-source refund guard symmetric к B-09 memberships.
- **PT-package freeze** (suspend validity period like memberships) — not on roadmap; if landed in v1.5+ — adds freeze guard symmetric к B-08.
- **Telegram bot `/pt_packages`** self-balance check — v1.5+ (Q15).
- **admin-web `/pt-package-plans` + `/pt-packages` routes** + PtPackageStatusBadge + mock parity — **Phase 35** (FE-10..18) NOT THIS PHASE.
- **End-of-day cash-drawer reconciliation** of pt_package sales — v1.5+ (B-06).
- **PT-package floor-access semantics** — explicitly NOT granted in v1.4 (B-10); separate active duration membership required для gym entry. NO code change needed in Phase 33 для этого — это business rule, не technical invariant.
- **OpenAPI byte-stable regen + schema.d.ts** — Phase 35 owns codegen.

</deferred>

---

*Phase: 33-pt-package-plans-instances*
*Context gathered: 2026-05-15*
