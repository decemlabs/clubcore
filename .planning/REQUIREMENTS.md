# Milestone v1.4 — Cash Sales + PT Packages — Requirements

**Milestone goal:** Закрыть критический MVP-gap "симуляция продажи без денег" + добавить персональные тренировки как новый тип услуги, чтобы зал реально мог принимать клиентов на двух тарифах (месячный абонемент и ПТ-пакет) с настоящим учётом наличных и возвратов.

**Scope locked:** 2026-05-14. Phase numbering continues from v1.3 (Phase 30+).

**Locked bedrock decisions** (recorded in PROJECT.md Key Decisions during Phase 30):
- B-01 — `payments` table append-only (no soft-delete, no UPDATE; AST-enforced)
- B-02 — full-refund only in v1.4 (no pro-rata; defer to v1.5+)
- B-03 — `LOCKED_AUDIT_EVENTS` pre-registered in Phase 30 before any callsite
- **B-04 — PT-packages live in separate `pt_packages` module with dedicated tables** (variant B)
- B-05 — `trainer_name_snapshot` on PT-session (historical UI integrity)
- B-06 — no end-of-day cash-drawer close in v1.4 (deferred to v1.5)
- **B-07 — uniform reception can refund (no 24h owner-approval split); H-13 mitigated by AlertDialog + confirm checkbox**
- B-08 — refund of `frozen` membership → 409 `must_unfreeze_first`
- B-09 — refund of renewed-source → 409 `cannot_refund_renewed_source`
- B-10 — PT-package alone does NOT grant gym floor access
- B-11 — PT-session backdating: reception 7d / owner unlimited
- B-12 — PT-session cancellation: reception 24h / owner anytime; balance restored atomically

---

## v1.4 Requirements

### INFRA — Foundations & Bedrock (Phase 30)

- [x] **INFRA-17**: Extend `LOCKED_AUDIT_EVENTS` frozenset from 34 → 51 entries (17 new): `trainer_created`, `trainer_updated`, `trainer_deactivated`, `trainer_reactivated`, `payment_recorded`, `refund_issued`, `membership_refunded`, `pt_package_plan_created`, `pt_package_plan_updated`, `pt_package_plan_archived`, `pt_package_sold`, `pt_package_cancelled`, `pt_package_refunded`, `pt_package_exhausted`, `pt_package_expired`, `pt_session_recorded`, `pt_session_cancelled`. Pre-registered in this phase before any downstream callsite (mirrors v1.3 Phase 24 INFRA-15).
- [ ] **INFRA-18**: Extend `Resource` enum with 5 new values: `TRAINERS`, `PAYMENTS`, `PT_PACKAGE_PLANS`, `PT_PACKAGES`, `PT_SESSIONS`. No new `Action` values (reuse existing `VIEW/CREATE/EDIT/DELETE/REFUND/CANCEL/LIST`). Three-way byte-paritet with `apps/admin-web/src/shared/session/can.ts` + `registry.ts`.
- [ ] **INFRA-19**: Extend `OWNER_ONLY` frozenset 15 → ~26 entries to cover trainers CRUD, PT-package plans CRUD, `(VIEW, PAYMENTS)` global list, `(CANCEL, PT_PACKAGES)`, `(DELETE, PT_PACKAGES)`, `(CANCEL, PT_SESSIONS)`. Reception retains: `(CREATE, PAYMENTS)`, `(REFUND, MEMBERSHIPS)`, `(REFUND, PT_PACKAGES)`, `(CREATE, PT_PACKAGES)`, `(CREATE, PT_SESSIONS)`, `(LIST, TRAINERS)`.
- [ ] **INFRA-20**: Extend `.importlinter` `modules-independent` contract with `app.modules.trainers`, `app.modules.payments`, `app.modules.pt_packages`. Three top-level contracts (`core ⊥ modules`, `modules independent`, `integrations ⊥ modules`) remain unchanged in shape.
- [ ] **INFRA-21**: Extend SVC001 AST commit-gate walker scope to forthcoming service files: `payments/service.py`, `trainers/service.py`, `pt_packages/service.py`. Every state-mutating service method must explicitly `await session.commit()` (mirrors v1.3 SVC001).
- [ ] **INFRA-22**: New AST walker forbids `UPDATE`/`DELETE` SQL against the `payments` table in any service file (defence for B-01 append-only). Negative-test fixture commits a violation; CI must catch it.
- [x] **INFRA-23**: Lock canonical payload schemas for the 17 new audit events in `audit_payloads.py` (or equivalent). `payment_refunded` payload MUST include `payment_row_hash` (SHA-256 canonical-JSON of original payment row) for forensic chain-of-custody.

### DEBT — Tech-debt carryover from v1.3 (Phase 30)

- [ ] **DEBT-05**: Close v1.3 deferred mock-mode parity gap — `apps/admin-web/src/shared/api/services/mock/memberships.ts` `list()` must filter by `query.status`. The «Заморожен» filter pill on `/memberships` must be a no-op no longer under `VITE_API_MODE=mock`. One-liner fix + 1-2 mock-parity tests.

### TRN — Trainers Module (Phase 31)

- [ ] **TRN-01**: New `trainers` table (Alembic 0011): `id UUIDv4 PK`, `full_name TEXT NOT NULL`, `phone TEXT NULL` (free-text — E.164 validated when present at schema layer), `is_active BOOLEAN NOT NULL DEFAULT TRUE`, `deleted_at TIMESTAMPTZ NULL`. Partial UNIQUE index on `phone WHERE deleted_at IS NULL AND phone IS NOT NULL` (mirrors v1.1 clients).
- [ ] **TRN-02**: Owner-only CRUD via `POST /api/v1/trainers`, `GET /api/v1/trainers/{id}`, `PATCH /api/v1/trainers/{id}`, `DELETE /api/v1/trainers/{id}`. CSRF required on mutations.
- [ ] **TRN-03**: Owner can deactivate (`is_active=false`) and reactivate (`is_active=true`) via PATCH. Inactive trainers are excluded from reception's PT-session picker but remain visible on historical PT-sessions.
- [ ] **TRN-04**: `GET /api/v1/trainers?active=true` returns active trainers for the PT-session picker. Reception has `(LIST, TRAINERS)` permission.
- [ ] **TRN-05**: Hard-delete (`DELETE`) returns 409 `trainer_in_use` when `pt_sessions.trainer_id` FK references exist. Owner deactivates instead.
- [ ] **TRN-06**: Protocol slot `register_trainer_by_id_resolver` in `core/dependencies.py` registered from both `app/main.py:create_app()` and `app/workers/telegram_bot.py:main()` (defensive double-wiring per REG-29-03 lesson, even though bot doesn't consume in v1.4).
- [ ] **TRN-07**: 4 audit events emitted on lifecycle transitions: `trainer_created`, `trainer_updated`, `trainer_deactivated`, `trainer_reactivated`.
- [ ] **TRN-08**: Admin-web `/trainers` route (owner-only `beforeLoad` guard) with: list page (table of trainers + active filter pill), create/edit modal (RHF + Zod schema), deactivate/reactivate buttons, hard-delete with 409 surface as inline error.

### PAY — Payment Ledger & Sale Flow (Phase 32)

- [ ] **PAY-01**: New `payments` table (Alembic 0012): `id UUIDv4 PK`, `subject_kind TEXT CHECK IN ('membership','pt_package','refund')`, `subject_id UUIDv4 NOT NULL`, `amount_kopecks INTEGER NOT NULL` (positive for sales, negative for refunds), `method TEXT NOT NULL DEFAULT 'cash'` (forward seam for v1.6 ЮKassa), `received_at TIMESTAMPTZ NOT NULL DEFAULT now()`, `received_by_user_id UUIDv4 NOT NULL FK users`, `refund_of UUIDv4 NULL FK payments(id) ON DELETE RESTRICT`, `audit_log_id UUIDv4 NULL FK audit_log(id)`. CHECK: amount sign matches `subject_kind` (refund ⇒ negative; sale ⇒ positive). **No `deleted_at`, no `updated_at`** (append-only — B-01).
- [ ] **PAY-02**: Partial UNIQUE index `(refund_of) WHERE refund_of IS NOT NULL` — second concurrent refund click loses at DB layer (mirrors v1.3 freeze partial-unique).
- [ ] **PAY-03**: New module `app/modules/payments/` (router + service + repository + schemas + permissions). Service exposes `record_payment(subject_kind, subject_id, amount_kopecks, user_id, *, audit_payload)` and `issue_refund(payment_id, refund_user_id, reason)` — both caller-owns-txn discipline (D-03).
- [ ] **PAY-04**: Protocol slots `register_payment_recorder` and `register_payment_refunder` in `core/dependencies.py` registered exclusively from `app/main.py:create_app()`. `memberships.service.create_membership` and (later) `pt_packages.service.create_pt_package` consume the recorder; refund methods consume the refunder.
- [ ] **PAY-05**: Modified `memberships.service.create_membership` calls the payment recorder inside the same UoW as the membership insert. Sale must record `payment.amount == membership.price_kopecks_snapshot` (mandatory snapshot symmetry); CHECK enforced server-side.
- [ ] **PAY-06**: New `GET /api/v1/payments` (owner-only) with filters `?subject_kind=`, `?subject_id=`, `?received_by_user_id=`, `?received_from=&received_to=`, pagination envelope `{items, total, page, pageSize}`. Reception cannot list globally — they only see payments tied to a client/membership they're viewing.
- [ ] **PAY-07**: `GET /api/v1/clients/{id}/payments` returns payment history (sales + refunds) for one client — reception+owner. Renders on client detail page.
- [ ] **PAY-08**: `GET /api/v1/memberships/{id}/payments` returns the membership's sale + any refund. Reception+owner.
- [ ] **PAY-09**: `Idempotency-Key` HTTP header required on `POST /api/v1/memberships` (sale endpoint) and forthcoming PT-package sale endpoint. Redis-cached for 1h (`sz:idem:{key}` → response hash) — replay returns cached response.
- [ ] **PAY-10**: Audit event `payment_recorded` emitted with payload `{payment_id, subject_kind, subject_id, amount_kopecks, method, received_by_user_id, payment_row_hash}`.

### REF — Refund Flow (Phase 32)

- [ ] **REF-01**: New endpoint `POST /api/v1/memberships/{id}/refund` (reception+owner per B-07). Body: `{reason: string}`. Atomically: insert negative-amount `payments` row with `refund_of FK` → original payment; transition membership to `cancelled` (using existing `_assert_can_transition` + new `cancellation_reason: 'refunded'` column on `memberships`); emit `payment_refunded` + `membership_refunded` audit events.
- [ ] **REF-02**: New endpoint `POST /api/v1/pt-packages/{id}/refund` (reception+owner) — symmetric to REF-01 but for pt_package. Transitions package to `cancelled`; emits `payment_refunded` + `pt_package_refunded`. Defined in Phase 33 alongside pt_packages module but RBAC + Protocol slot wired in Phase 32.
- [ ] **REF-03**: Refund of `frozen` membership returns 409 `must_unfreeze_first`. UI forces unfreeze→refund flow (B-08).
- [ ] **REF-04**: Refund of a renewed-source membership returns 409 `cannot_refund_renewed_source` — must refund descendant first (B-09). Detection via `EXISTS (SELECT 1 FROM memberships WHERE previous_membership_id = $1)`.
- [ ] **REF-05**: Refund is full-amount only (B-02). Backend rejects any request body containing an explicit `amount_kopecks` (forbidden field at schema layer).
- [ ] **REF-06**: Admin-web AlertDialog confirms refund: client full name + plan name + `formatMoney(amount)` + sale date + reason input (free-text required; max 200 chars). Confirm-button disabled until user checks "Понимаю, что возврат необратим" — H-13 mitigation.
- [ ] **REF-07**: Audit emits `refund_issued` (on payment ledger insert) + `payment_refunded` (linking to subject) + `membership_refunded` or `pt_package_refunded` (subject-side). All three are pre-registered locked events.
- [ ] **REF-08**: Postgres integration test REF-TEST-01: two concurrent `POST /refund` calls against the same membership → exactly one succeeds (DB partial UNIQUE wins), the other returns 409.

### PT — PT-Package Plans + Instances + Sessions (Phases 33-34)

#### PT-package Plans (Phase 33)

- [ ] **PT-01**: New `pt_package_plans` table (Alembic 0013): `id`, `name TEXT NOT NULL`, `session_count INTEGER NOT NULL CHECK > 0` (immutable post-creation, mirrors v1.2 `duration_days` discipline), `price_kopecks INTEGER NOT NULL CHECK > 0`, `validity_days INTEGER NULL CHECK > 0` (NULL = no time-expiry), `deleted_at TIMESTAMPTZ NULL`. Partial UNIQUE on `lower(name) WHERE deleted_at IS NULL` (mirrors v1.2 Phase 16).
- [ ] **PT-02**: Owner-only CRUD `POST/GET/PATCH/DELETE /api/v1/pt-package-plans`. `session_count` and `price_kopecks` and `validity_days` immutable post-creation (PATCH rejects with 409 `field_immutable`). Soft-delete returns 409 `plan_in_use` when `pt_packages` instance references exist.
- [ ] **PT-03**: 3 audit events: `pt_package_plan_created`, `pt_package_plan_updated`, `pt_package_plan_archived`.

#### PT-package Instances (Phase 33)

- [ ] **PT-04**: New `pt_packages` table (Alembic 0014): `id`, `client_id FK clients`, `plan_id FK pt_package_plans ON DELETE RESTRICT`, full snapshot suite (`plan_name_snapshot`, `session_count_snapshot`, `price_kopecks_snapshot`, `validity_days_snapshot NULL`), `sessions_remaining INTEGER NOT NULL CHECK >= 0 AND <= session_count_snapshot`, `status TEXT CHECK IN ('active','exhausted','expired','cancelled')`, `start_date DATE NOT NULL DEFAULT today(Europe/Moscow)`, `end_date DATE NULL` (derived as `start_date + validity_days_snapshot - 1` when `validity_days_snapshot IS NOT NULL`), `cancellation_reason TEXT NULL`.
- [ ] **PT-05**: Partial UNIQUE `(client_id) WHERE status = 'active'` — one active PT-package per client at a time (Q5 default; defer multi-package to v1.5).
- [ ] **PT-06**: New `PT_PACKAGE_STATUS_TRANSITIONS` declarative constant + `_assert_can_transition` central guard (mirrors v1.3 `MEMBERSHIP_STATUS_TRANSITIONS`). Legal: `active → exhausted`, `active → expired`, `active → cancelled`, `exhausted → cancelled` (for refund of exhausted), `expired → cancelled` (same). Invalid: returns 409 `invalid_transition`.
- [ ] **PT-07**: `POST /api/v1/pt-packages` (reception+owner) sells a PT-package: snapshot from current plan, insert instance, call payment recorder. Symmetric to v1.2 membership sale.
- [ ] **PT-08**: `POST /api/v1/pt-packages/{id}/cancel` (owner-only) cancels without refund — sets status to `cancelled` with `cancellation_reason`. Emits `pt_package_cancelled`. Distinct from refund (REF-02).
- [ ] **PT-09**: `GET /api/v1/pt-packages/{id}` returns instance with snapshot fields and sessions_remaining.
- [ ] **PT-10**: `GET /api/v1/pt-packages?client_id=...&status=active` for reception PT-session form prefill.
- [ ] **PT-11**: Protocol slot `register_active_pt_package_resolver` (same shape as v1.2 `ActiveMembership`) — registered in `app/main.py`.
- [ ] **PT-12**: New ARQ cron job `expire_pt_packages` at 06:25 MSK (cron `hour=3, minute=25, unique=True, keep_result=60` with container `TZ=UTC`). Transitions packages where `status='active' AND end_date IS NOT NULL AND end_date < today(Europe/Moscow)` to `expired`. Idempotent (re-running same day is no-op). Emits one `pt_package_expired` per row.
- [ ] **PT-13**: 5 audit events: `pt_package_sold`, `pt_package_cancelled`, `pt_package_refunded` (subject-side, defined REF-07), `pt_package_exhausted`, `pt_package_expired`.

#### PT-sessions (Phase 34)

- [ ] **PT-14**: New `pt_sessions` table (Alembic 0015): `id`, `pt_package_id FK pt_packages ON DELETE RESTRICT`, `trainer_id FK trainers ON DELETE RESTRICT`, `client_id FK clients` (denormalised — avoids JOIN on client history), `performed_at TIMESTAMPTZ NOT NULL`, `performed_by_user_id UUIDv4 NOT NULL FK users`, `cancelled_at TIMESTAMPTZ NULL`, `cancel_reason TEXT NULL`, `trainer_name_snapshot TEXT NOT NULL` (B-05), `notes TEXT NULL` (≤ 500 chars). Composite indexes `(pt_package_id, performed_at DESC)` and `(trainer_id, performed_at DESC)`.
- [ ] **PT-15**: `POST /api/v1/pt-sessions` (reception+owner) records a session. Body: `{pt_package_id, trainer_id, performed_at, notes?}`. Server validates: trainer exists+active (via Protocol slot), package active, performed_at within backdating window (B-11: reception 7d / owner unlimited).
- [ ] **PT-16**: Race-safe decrement via single SQL: `UPDATE pt_packages SET sessions_remaining = sessions_remaining - 1 WHERE id=:id AND sessions_remaining > 0 AND status='active' RETURNING sessions_remaining`. 0-row RETURNING → 409 `pt_package_exhausted`. Defence-in-depth CHECK `sessions_remaining >= 0`.
- [ ] **PT-17**: Auto-transition to `'exhausted'` synchronously when decrement returns `sessions_remaining = 0` (same UoW; emits `pt_package_exhausted` once).
- [ ] **PT-18**: `POST /api/v1/pt-sessions/{id}/cancel` cancels a recorded session (reception within 24h of recording / owner anytime per B-12). Atomically: set `cancelled_at` + `cancel_reason`; increment `sessions_remaining` on parent package; if package was `exhausted`, transition back to `active`; emit `pt_session_cancelled`.
- [ ] **PT-19**: `GET /api/v1/pt-packages/{id}/sessions` returns session history (incl. cancelled).
- [ ] **PT-20**: PT-sessions are independent of `visits` table — recording a PT-session does NOT create a `visits` row, and a visit does not create a PT-session. Orthogonal events (Q3 default).
- [ ] **PT-21**: 2 audit events: `pt_session_recorded`, `pt_session_cancelled`.
- [ ] **PT-22**: Postgres integration test PTS-TEST-01: two concurrent `POST /pt-sessions` against a package with `sessions_remaining=1` → exactly one succeeds, other 409.

### FE — Admin-web Wiring (Phase 35)

- [ ] **FE-10**: OpenAPI drift gate: single byte-stable regen of `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts` exposing all new v1.4 typed paths (payments, trainers, pt-package-plans, pt-packages, pt-sessions, refund endpoints). CI `git diff --exit-code` enforces.
- [ ] **FE-11**: New routes: `/trainers` (owner-only `beforeLoad`), `/pt-package-plans` (owner-only), `/pt-packages` (list + `$pt_packageId` detail), `/clients/$clientId` extended with payments-history block + active-pt-package block.
- [ ] **FE-12**: Sale flow modification: `/memberships` sale form gets a "Получено наличными" section (mandatory cash-received amount input, defaulted to `plan.price_kopecks`; validated equal to plan price server-side). Same for `/pt-packages` sale.
- [ ] **FE-13**: Refund button on `/memberships/$membershipId` and `/pt-packages/$pt_packageId` detail pages. Opens AlertDialog per REF-06.
- [ ] **FE-14**: PT-session recording UI: panel on `/pt-packages/$pt_packageId` detail with trainer-dropdown (loads `?active=true`), datetime picker (defaulted to now, backdating ≤7d for reception), notes textarea. "Записать тренировку" button. Session history below with `(уволен)` suffix on inactive-trainer names.
- [ ] **FE-15**: New shared `PaymentBadge` (sale/refund tint via `bg-success`/`bg-warning` tokens) and `PtPackageStatusBadge` (4-variant discriminated union: active/exhausted/expired/cancelled). Used on list pages, detail pages, and history blocks.
- [ ] **FE-16**: TanStack Query mutation hooks: `usePtPackageSell`, `usePtPackageCancel`, `usePtPackageRefund`, `useMembershipRefund`, `usePtSessionRecord`, `usePtSessionCancel`, `useTrainerCreate/Update/Deactivate/Reactivate`. Optimistic where safe; refund non-optimistic + navigate-on-success.
- [ ] **FE-17**: Locked Russian i18n strings for new flows (sale-with-payment labels, refund AlertDialog copy, PT-session form copy, trainers CRUD copy, status badge labels). Hard-coded in `src/shared/i18n/ru.ts`.
- [ ] **FE-18**: Three-way RBAC parity test extended to assert byte-paritet between backend `OWNER_ONLY` + admin-web `can.ts` + `registry.ts` for the new resources.

### VER — Milestone Verification (Phase 36)

- [ ] **VER-01**: 7+ operator human-verification scenarios executed against live backend + admin-web stack (mirrors v1.3 Phase 29 sweep). Scenarios cover: sale-with-payment golden path; refund of fresh sale; refund attempt on frozen membership (must be rejected); PT-package sale; PT-session recording with active trainer; PT-package exhaustion mid-session-flow; trainer deactivation; cross-phase smoke (sell membership → freeze → refund-attempt-rejected → unfreeze → refund-succeeds).
- [ ] **VER-02**: Race-condition Postgres integration tests REF-TEST-01 (concurrent refund) + PTS-TEST-01 (concurrent PT-session decrement) + PAY-TEST-01 (concurrent sale double-submit with same Idempotency-Key) + AUDIT-TEST-01 (every state-mutating service emits expected event).
- [ ] **VER-03**: 6 CI gates green: backend `ruff` + `mypy --strict` + `pytest` + OpenAPI drift; frontend `pnpm typecheck` + `pnpm lint` + `pnpm test` + api-client codegen drift. Evidence captured as gate logs in `milestones/v1.4-VERIFICATION-LOG.md`.
- [ ] **VER-04**: Operator sign-off documented in `.planning/milestones/v1.4-VERIFICATION-LOG.md` with verbatim DM / UI evidence per scenario. Any production-blocker regressions discovered are fixed inline (v1.3 caught 3 such regressions at this gate).

---

## Future Requirements (deferred to v1.5+)

- Pro-rata refunds for partially-used memberships and PT-packages (Q1).
- End-of-day cash-drawer reconciliation (daily totals endpoint + admin UI).
- Owner reports dashboard: revenue by day/month/category (memberships vs PT), active clients, expiring clients, conversion rates.
- `GET /api/v1/audit-log` (owner-only) read API + UI for the existing audit_log table.
- Online payments via ЮKassa (v1.6): intake + webhooks + 54-ФЗ fiscal receipts.
- Paid freeze model (kopecks/day pricing; depends on online payments).
- Multiple active PT-packages per client (Q5 expansion).
- PT-package renewal carry-over of unused sessions (Q8 expansion).
- Visit-count plans alternative tariff (different from PT-packages).
- Telegram bot extensions for PT-packages (`/pt_packages` self-balance check) (Q15).
- Trainer profile features: schedule, payroll, commission, login, ratings.
- Admin-web UI polish milestone (v1.7).

## Out of Scope (permanent)

Carried forward from PROJECT.md:
- Multi-tenancy (ContextVar / `tenant_id` / RLS) — single-gym pet project.
- Stripe — region-banned in RU/CIS.
- `apps/client-web` — client frontend reserved for future Phase J.
- Kubernetes / Terraform / production deploy.

New for v1.4:
- Fiscal 54-ФЗ receipts and online cash register (АТОЛ / OFD.ru integration) — gym operates in grey zone; no fiscal compliance in v1.4.
- Trainer payroll / pay rates / commission / shift schedules — trainers catalog is identity-only.
- Card payments / bank transfers / mixed-payment-method sales — cash-only in v1.4.
- Partial refunds and pro-rata refunds — full-amount only.
- PT-package floor-access semantics — a PT-package alone does NOT grant gym entry (must have an active duration membership for floor access).
- Trainer self-service logging (trainer logs own sessions) — reception-driven only.
- Group personal training (multi-client per session).
- PT-session scheduling / pre-booking.

---

## Traceability

Filled by `gsd-roadmapper` on 2026-05-14. Each REQ-ID maps to exactly one phase; 100% coverage validated (69/69).

| Phase | REQ-IDs | Count |
|-------|---------|-------|
| **Phase 30 — Foundations & Tech-Debt Bedrock** | INFRA-17, INFRA-18, INFRA-19, INFRA-20, INFRA-21, INFRA-22, INFRA-23, DEBT-05 | 8 |
| **Phase 31 — Trainers Module** | TRN-01, TRN-02, TRN-03, TRN-04, TRN-05, TRN-06, TRN-07, TRN-08 | 8 |
| **Phase 32 — Payment Ledger + Sale Flow + Refund** | PAY-01, PAY-02, PAY-03, PAY-04, PAY-05, PAY-06, PAY-07, PAY-08, PAY-09, PAY-10, REF-01, REF-02, REF-03, REF-04, REF-05, REF-06, REF-07, REF-08 | 18 |
| **Phase 33 — PT-Package Plans + Instances** | PT-01, PT-02, PT-03, PT-04, PT-05, PT-06, PT-07, PT-08, PT-09, PT-10, PT-11, PT-12, PT-13 | 13 |
| **Phase 34 — PT-Session Recording** | PT-14, PT-15, PT-16, PT-17, PT-18, PT-19, PT-20, PT-21, PT-22 | 9 |
| **Phase 35 — OpenAPI Drift Gate + admin-web Full Wiring** | FE-10, FE-11, FE-12, FE-13, FE-14, FE-15, FE-16, FE-17, FE-18 | 9 |
| **Phase 36 — Milestone Verification** | VER-01, VER-02, VER-03, VER-04 | 4 |
| **TOTAL** | | **69 / 69** |

Coverage: 100% (every v1.4 REQ-ID mapped to exactly one phase). Dependency ordering validated:
- Phase 31 (Trainers) lands before Phase 34 (PT-sessions FK target).
- Phase 32 (Payments + payment_recorder Protocol slot) lands before Phase 33 (PT-package sale consumes recorder).
- Phase 33 (PT-package instances + sessions_remaining counter) lands before Phase 34 (PT-session decrement target).
- Phase 35 (OpenAPI + admin-web wiring) lands after all backend Phases 31..34.
- Phase 36 (verification) gates on Phase 35 (full stack required for smoke).

REF-02 endpoint shape is defined in Phase 32 (RBAC + Protocol slot wiring) but the actual `POST /api/v1/pt-packages/{id}/refund` router lands in Phase 33 alongside the `pt_packages` module — this cross-phase coordination mirrors v1.3 Phase 24/25 audit-event pre-registration.

---

*Requirements locked: 2026-05-14. Phase numbering continues from v1.3 (start at Phase 30). Roadmap created 2026-05-14 by `gsd-roadmapper`.*
