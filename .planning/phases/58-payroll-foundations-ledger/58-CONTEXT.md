# Phase 58: Payroll Foundations + Ledger - Context

**Gathered:** 2026-05-25
**Status:** Ready for planning
**Mode:** `--auto` (decisions auto-selected to recommended defaults from v1.9 research; review before planning)

<domain>
## Phase Boundary

The **payroll-domain bedrock** for v1.9. Six requirements (PAY-01..06) land
together as a single, financially-correct foundation that the rest of v1.9
plus all future payroll work depends on. This phase establishes the INFRA-15
bedrock (RBAC parity + LOCKED_AUDIT_EVENTS pre-registration) AND the first
append-only payroll ledger rows; subsequent phases (59 schedule, 60 report,
61 handoff) consume the comp-config and accrual tables read-only.

**Three concrete deliverables:**

1. **INFRA-15 bedrock (pre-registration, no callsites yet).**
   - Extend `OWNER_ONLY` in both `apps/backend/app/core/permissions.py` and
     `apps/admin-web/src/shared/session/can.ts` with the new payroll/compensation
     write/run/refund pairs. The `Resource.PAYROLL` and `Resource.COMPENSATION`
     members AND the `(VIEW, PAYROLL)` / `(VIEW, COMPENSATION)` pairs ALREADY
     EXIST in permissions.py (kept since the early role grid). Phase 58 adds
     the WRITE-side pairs.
   - Add 6 new `LOCKED_AUDIT_EVENTS` tuples in `app/core/audit.py` covering
     the payroll lifecycle (comp-config set, accrual created, accrual paid,
     clawback recorded, plus any plan-time refinements). All must exist
     before any `audit.emit(...)` callsite per INFRA-15 discipline.
   - Three-way RBAC parity test (existing TEST-06 / Phase 6 parity machinery)
     must remain green: backend `OWNER_ONLY` ↔ admin-web `can.ts` ↔
     `registry.ts`. `apps/admin-web` is otherwise frozen in v1.9 per the
     milestone goal — these three files are the only admin-web edits allowed.
   - Register `app.modules.payroll` in `apps/backend/.importlinter`
     `modules-independent` contract list with **zero new `ignore_imports`
     edges** (preemptive registration per Phase 54 D-54-09 precedent).

2. **Comp-config + accrual schema + endpoints (PAY-01..05).**
   - New `app/modules/payroll/` module: `models.py`, `schemas.py`,
     `repository.py`, `service.py`, `router.py`, `constants.py`.
   - New Alembic migration `0041_payroll_foundations.py` creating
     `trainer_comp_configs` (versioned, INSERT-only) + `trainer_payroll_accruals`
     (append-only, signed-amount).
   - Endpoints (owner-only, mounted under `/api/v1/payroll/`):
     - `PUT /payroll/trainer-configs/{trainer_id}` — set / replace comp config
       (PAY-01). Versioned INSERT (new row with `effective_from`); never UPDATE.
     - `GET /payroll/trainer-configs/{trainer_id}` — return latest config
       resolved by `effective_from <= today` (PAY-01 read).
     - `GET /payroll/preview?trainer_id=...&period_start=...&period_end=...` —
       read-only preview, zero persistence (PAY-02).
     - `POST /payroll/accruals` — record an accrual (PAY-03); body
       `{trainer_id, period_start, period_end}`; idempotent on
       `(trainer_id, period_start, period_end)` UNIQUE → 409 on duplicate;
       422 `comp_config_missing` if no config resolves for the period.
     - `POST /payroll/accruals/{id}/mark-paid` — single allowed lifecycle
       transition (PAY-04); 409 `already_paid` on second attempt; no `unpay`.
     - `GET /payroll/accruals?trainer_id=...&page=...&pageSize=...` — paginated
       list ordered by `accrued_at DESC` (PAY-05); response shape
       `{items, total, page, pageSize}` per project convention.

3. **Clawback hook for PT-package refund (PAY-06).**
   - New Protocol slot `PayrollClawbackRecorder` registered in
     `app/main.py`, owned by `app/modules/payroll/`. Mirrors the existing
     `PaymentRefunder` Protocol slot pattern used by
     `pt_packages.service.refund_pt_package` (apps/backend/app/modules/pt_packages/service.py:1038).
   - Wire the slot call into `refund_pt_package` BETWEEN steps 6 and 8 of the
     existing D-33-11 sequence — after `pt_package_refunded` audit emit, before
     the final `session.commit()`. The slot inspects whether the refunded
     payment is referenced by any accrual row with status='paid' covering
     that payment's bucket date; if yes, INSERT a new accrual row with
     **negative** `accrual_kopecks`, `clawback_of_accrual_id` self-FK, and
     `source_refund_payment_id` FK to the refund payment row. Same UoW; no
     UPDATE to the original accrual.
   - `pt_packages.service` cannot import `app.modules.payroll.*` (modules-
     independent contract). Cross-module call is through the Protocol slot
     ONLY — zero new `ignore_imports` edges added.

**In scope (PAY-01..06):**
- 1 new Alembic migration `0041_payroll_foundations.py` (head 0040 → 0041).
- 2 new tables: `trainer_comp_configs` (INSERT-only versioned),
  `trainer_payroll_accruals` (append-only signed-amount with optional self-FK
  for clawback rows).
- 1 new module `app/modules/payroll/` registered in import-linter contract.
- 7 endpoints (6 functional + 1 GET config read).
- 1 new Protocol slot (`PayrollClawbackRecorder`) wired in main.py.
- 1 new callsite in `pt_packages.service.refund_pt_package` (the clawback
  hook) — narrowly scoped, Protocol-slot mediated.
- ≤6 new `LOCKED_AUDIT_EVENTS` pre-registered (exact count refined at plan
  time; minimum 4 confirmed: `trainer_comp_config_set`,
  `payroll_accrual_created`, `payroll_accrual_paid`, `payroll_clawback_recorded`).
- New `OWNER_ONLY` write/run/refund pairs (PAYROLL + COMPENSATION resources).
- Three-way RBAC parity tests + audit-lock parity tests stay green.
- Integration tests covering all 7 endpoints + 6 success criteria + idempotency
  races + 422 missing-config + 409 already-paid + 409 already-run + clawback
  same-UoW invariant.

**Out of scope (later phases / versions):**
- Recurring slot patterns + ARQ generation cron (REC-01, REC-02 → Phase 59).
- Time-off blocks + conflict guard (REC-03, REC-04 → Phase 59).
- Trainer-usage report incl. `total_accrued`/`total_paid` summary
  (RPT-01..04 → Phase 60); Phase 60 reads `trainer_payroll_accruals`
  via raw-SQL `text()` (D-54-08 pattern, read-only, no protocol slot).
- OpenAPI handoff / `schema.d.ts` regeneration (HND-01 → Phase 61).
- `apps/admin-web` UI for payroll (frozen in v1.9; admin-web edits limited
  to `permissions.py`-mirror in `can.ts` + `registry.ts` for parity).
- Membership / online-refund clawback hooks — PAY-06 is **PT-package refund
  only** per requirement wording ("Возврат PT-пакета"). Other refund paths
  added in a future milestone if/when their commissionable nature is
  established (currently only PT-packages drive trainer commission).
- Per-session commission proration across period boundaries; tiered
  commission; auto period-detection; "void accrual" operation; UPDATE of an
  existing accrual row.
- 1C / external payroll export, payroll PDF reports, partial PT-package
  refunds (B-02 still deferred from v1.4).

</domain>

<decisions>
## Implementation Decisions

> **Most decisions are LOCKED by the v1.9 research convergence**
> (`.planning/research/SUMMARY.md` "Discrepancy Resolutions" §1–3 + PITFALLS
> 1–6). Phase 58 ratifies them. The planner refines counts/names/exact column
> sets within these locked boundaries.

### Module placement (D-58-01)
- **D-58-01:** Payroll lives in a NEW `app/modules/payroll/` module, NOT in
  `trainers` (catalog-only, no financial logic) and NOT in `payments`
  (incoming-money ledger; payroll is outgoing wages — separate domain).
  Locked by ARCHITECTURE.md Q1 + SUMMARY §1. Module registered in
  `.importlinter modules-independent` list before any code lands
  (Phase 54 D-54-09 / INFRA-15 precedent — zero new `ignore_imports` edges).

### Schema discipline (D-58-02..05)
- **D-58-02:** `trainer_comp_configs` is **INSERT-only versioned** with
  `effective_from date NOT NULL`. No `UNIQUE(trainer_id)`. Resolver picks
  `ORDER BY effective_from DESC LIMIT 1 WHERE effective_from <= :as_of_date`.
  `PUT /payroll/trainer-configs/{trainer_id}` INSERTs a new row; the prior
  row is never UPDATEd. Locked by PITFALL 5 + SUMMARY §1.
  - Two nullable economics columns per REQUIREMENTS PAY-01:
    `commission_pct_bps INT NULL CHECK (>= 0 AND <= 10000)` (basis points,
    1% = 100 bps) and `session_fee_kopecks INT NULL CHECK (>= 0)`. Both NULL
    is allowed at write time but blocks accrual creation (422 at run time).
    Hybrid (both set) is allowed per REQUIREMENTS.
  - **No `comp_model` enum column.** The model is derived from which fields
    are non-NULL (matches REQUIREMENTS PAY-01 wording; simpler schema).
- **D-58-03:** `trainer_payroll_accruals` is **append-only with signed
  amount** semantics (mirrors v1.4 `payments` ledger). The only allowed
  mutation post-INSERT is the single `paid_at` / `paid_by_user_id` /
  `status='paid'` transition (mirrors `pt_packages.status` single-transition
  pattern). No UPDATE to `accrual_kopecks`, period bounds, snapshots, or
  any other field. Locked by PITFALL 1 + ARCHITECTURE.md Q1.
  - Snapshot columns (frozen at run time, never recomputed): `sessions_count
    INT`, `revenue_kopecks INT`, `commission_pct_bps_snapshot INT`,
    `session_fee_kopecks_snapshot INT`, `comp_config_id_snapshot UUID` (FK to
    the `trainer_comp_configs` row in effect), `period_start date`,
    `period_end date`, `accrual_kopecks INT` (can be negative for clawback
    rows; positive for regular accruals).
  - `UNIQUE (trainer_id, period_start, period_end)` only applies to
    **regular accrual rows** (`clawback_of_accrual_id IS NULL`). Clawback
    rows (`clawback_of_accrual_id IS NOT NULL`) are exempt — multiple
    clawbacks may legitimately offset one accrual. Implementation: partial
    UNIQUE INDEX `WHERE clawback_of_accrual_id IS NULL`.
  - Lifecycle fields: `status TEXT NOT NULL CHECK IN ('pending','paid')
    DEFAULT 'pending'`, `paid_at TIMESTAMPTZ NULL`,
    `paid_by_user_id UUID NULL FK→users.id`. Clawback rows are inserted
    with `status='pending'` by default (planner may revisit; the operator
    "marks paid" the clawback row separately if/when the negative payout is
    settled).
  - Clawback self-FK: `clawback_of_accrual_id UUID NULL FK→trainer_payroll_accruals.id`
    AND `source_refund_payment_id UUID NULL FK→payments.id`. Both NULL on a
    regular accrual; both NOT NULL on a clawback row (CHECK constraint).
- **D-58-04:** Rate stored as **integer basis points** (`commission_pct_bps`,
  `commission_pct_bps_snapshot`), never `FLOAT` / `NUMERIC`. All commission
  math uses integer arithmetic: `accrual = (revenue_kopecks * bps) // 10000`
  with `math.ceil` rounding in the trainer's favor (mirrors freeze-day ceil
  discipline from Phase 25). Session-fee component: `session_fee_kopecks *
  sessions_count` (pure integer). Total = sum of components. Locked by
  PITFALL 3.
- **D-58-05:** Period boundaries are **inclusive `[period_start, period_end]`
  MSK dates** — `(performed_at AT TIME ZONE 'Europe/Moscow')::date BETWEEN
  :period_start AND :period_end`. Matches `memberships.end_date` and
  `visits.gym_date` canonical project discipline. Locked by PITFALL 2.

### Idempotency & error codes (D-58-06..09)
- **D-58-06:** Run idempotency via DB-wins-the-race —
  `INSERT INTO trainer_payroll_accruals ... ON CONFLICT (trainer_id,
  period_start, period_end) WHERE clawback_of_accrual_id IS NULL DO NOTHING
  RETURNING id`. If RETURNING yields no row → 409 `payroll_period_already_run`.
  Service-layer pre-flight SELECT followed by INSERT is **forbidden** (TOCTOU
  race; PITFALL 2). Locked.
- **D-58-07:** Missing comp config returns **422 `comp_config_missing`** at
  `POST /payroll/accruals` time (REQUIREMENTS PAY-03 success criterion #1).
  Resolver SELECT returns no row → service raises typed
  `CompConfigMissingError` → router maps to 422. The error_code is
  snake_case (project convention; mirrors `cancel_window_expired`,
  `original_payment_not_found`).
- **D-58-08:** Mark-paid idempotency: `SELECT ... FOR UPDATE` the accrual
  row, check `status == 'pending'`, UPDATE to `'paid'`. Second attempt:
  409 `already_paid`. No `unpay` endpoint exists (locked by REQUIREMENTS
  PAY-04 wording).
- **D-58-09:** Accrual creation is non-zero only when at least one of
  `commission_pct_bps` / `session_fee_kopecks` is non-NULL in the resolved
  config. If both are NULL the resolver treats the trainer as "no config" →
  422 `comp_config_missing` (matches REQUIREMENTS PAY-01 wording: "оба NULL
  = payroll для тренера не считается"). The PUT endpoint allows BOTH-NULL
  writes (operator may stage a config before fully defining it), but a
  run against a both-NULL config still 422s.

### Endpoint shape (D-58-10..14)
- **D-58-10:** `PUT /api/v1/payroll/trainer-configs/{trainer_id}` —
  body `{commission_pct_bps?: int, session_fee_kopecks?: int,
  effective_from: date}`. INSERTs a new row in `trainer_comp_configs`.
  Returns `200 {id, trainer_id, commission_pct_bps, session_fee_kopecks,
  effective_from, created_at}`. Owner-only (RBAC).
- **D-58-11:** `GET /api/v1/payroll/trainer-configs/{trainer_id}` — returns
  the resolved active config (latest `effective_from <= today`) or 404
  `comp_config_missing` if no rows exist for the trainer. Owner-only.
- **D-58-12:** `GET /api/v1/payroll/preview?trainer_id=&period_start=&period_end=` —
  read-only preview. Body returns `{session_count, fixed_kopecks,
  commission_kopecks, total_kopecks}`. No row written, no audit emitted.
  Resolver still raises 422 `comp_config_missing` if no config. Owner-only.
- **D-58-13:** `POST /api/v1/payroll/accruals` — body
  `{trainer_id, period_start, period_end}`. Returns `201 {id, ...all
  snapshot columns..., status:'pending', accrued_at}`. Owner-only.
  `POST /api/v1/payroll/accruals/{id}/mark-paid` — empty body. Returns
  `200 {id, status:'paid', paid_at, paid_by_user_id}`. Owner-only.
- **D-58-14:** `GET /api/v1/payroll/accruals?trainer_id=&page=&pageSize=` —
  ordered `accrued_at DESC`. Response `{items: [...], total, page, pageSize}`
  per project pagination convention. Filters: `trainer_id` required; future
  `status`, `period_start`, `period_end` filters are deferred (NOT in PAY-05).
  Owner-only.

### RBAC + audit pre-registration (D-58-15..18)
- **D-58-15:** New `OWNER_ONLY` pairs added in
  `apps/backend/app/core/permissions.py` AND mirrored verbatim in
  `apps/admin-web/src/shared/session/can.ts`. Pairs (working set; planner
  may refine wording, but the cardinality target is "all payroll/compensation
  WRITE+RUN+REFUND pairs are owner-only"):
  - `(Action.CREATE, Resource.COMPENSATION)` — set/replace comp config
  - `(Action.EDIT, Resource.COMPENSATION)` — alias for replace; may collapse
    to `CREATE` if the only write is "INSERT new version" (D-58-02). Planner
    decides whether one or both ship; final pair count documented in the plan.
  - `(Action.CREATE, Resource.PAYROLL)` — record accrual (run)
  - `(Action.EDIT, Resource.PAYROLL)` — mark paid (the only allowed
    post-INSERT mutation; mapping `mark-paid` to `Action.EDIT` keeps the
    Action enum small per project convention)
  - `(Action.REFUND, Resource.PAYROLL)` — clawback hook authorization
    (the clawback is server-internal, but the Protocol-slot path is
    permission-checked against actor=owner to prevent reception-initiated
    refunds from cascading silently into trainer payroll).
  - `(Action.LIST, Resource.PAYROLL)` — paginated listing (owner-only;
    reception has zero payroll visibility).
  Existing `(VIEW, PAYROLL)` and `(VIEW, COMPENSATION)` pairs are unchanged.
  Final OWNER_ONLY size: 29 → planner reports the new size (TEST-06 parity
  count assertion bumped). Three-way RBAC parity test (existing) stays green.
- **D-58-16:** New `LOCKED_AUDIT_EVENTS` entries added to
  `app/core/audit.py` BEFORE any `audit.emit(...)` callsite (INFRA-15
  discipline; AuditEventNotLockedError-friendly). Confirmed minimum set
  (4 events):
  - `("trainer_comp_config_set", "trainer_comp_config")`
  - `("payroll_accrual_created", "payroll_accrual")`
  - `("payroll_accrual_paid", "payroll_accrual")`
  - `("payroll_clawback_recorded", "payroll_accrual")`
  Up to 2 additional events may be added by the planner if the
  six-LOCKED_AUDIT_EVENTS roadmap count (SC#5) requires finer granularity
  (e.g., separate `_created` vs `_updated` for the comp config, or a
  `payroll_accrual_cancelled` audit on a future void path). Pre-registration
  is mandatory; emission callsites land in the same plans that introduce
  the corresponding service methods.
- **D-58-17:** Audit emit follows the v1.4 atomic chain discipline (UoW
  owns commit; emit BEFORE `session.commit()`, hash-chained via
  `audit_hash.py`). Specifically:
  - `payroll_accrual_created` emits AFTER the INSERT-with-RETURNING and
    BEFORE the orchestrator's `session.commit()` (D-33-11 sequence
    mirrored — same pattern as `pt_package_refunded`).
  - `payroll_clawback_recorded` emits inside the `PayrollClawbackRecorder`
    Protocol-slot body, before the caller's `session.commit()`. The audit
    chain for a PT-package refund-with-clawback becomes:
    `payment_recorded` (original sale) → `refund_issued` (payment-side,
    inside `issue_refund`) → `pt_package_refunded` (subject-side) →
    `payroll_clawback_recorded` (payroll-side, inside the slot call).
- **D-58-18:** `app.modules.payroll` is added to the
  `[importlinter:contract:modules-independent]` `modules` list in
  `apps/backend/.importlinter` BEFORE any payroll/* file is imported by
  the runtime composition root. Zero new `ignore_imports` edges. Mirrors
  Phase 54 D-54-09 preemptive-registration pattern.

### Cross-module access pattern (D-58-19..20)
- **D-58-19:** Preview + accrual creation read cross-module data
  (`pt_sessions`, `pt_packages`, `payments`) via **raw-SQL `text()`** inside
  `app/modules/payroll/repository.py`. NO `from app.modules.pt_sessions
  import ...` / `from app.modules.payments import ...`. Zero new
  `ignore_imports` edges. Mirrors v1.8 `reports` module discipline
  (D-54-08, D-49-03). The SQL JOIN shape is in ARCHITECTURE.md Q1 (see
  `fetch_trainer_session_revenue`); column names verified against current
  `apps/backend/app/modules/pt_sessions/models.py` and
  `apps/backend/app/modules/payments/models.py` at plan time.
- **D-58-20:** Clawback write is a **Protocol slot owned by payroll**,
  registered in `app/main.py`, called from
  `pt_packages.service.refund_pt_package` in the same `session` /
  same UoW. Mirrors existing `PaymentRefunder` Protocol slot pattern.
  Slot interface (final names refined at plan time):
  ```python
  class PayrollClawbackRecorder(Protocol):
      async def record_clawback_for_pt_package_refund(
          self,
          session: AsyncSession,
          actor: CurrentUser,
          refund_payment_id: UUID,
          pt_package_id: UUID,
      ) -> UUID | None:
          """Append a negative clawback accrual row if the refund's revenue
          appears in any status='paid' accrual. Returns the new clawback
          accrual id, or None if no payroll impact."""
  ```
  `pt_packages.service.refund_pt_package` calls `get_payroll_clawback_recorder()`
  (mirroring `get_payment_refunder()`) BEFORE its own `session.commit()`.

### Attribution model (D-58-21)
- **D-58-21:** Locked per PITFALL 6:
  - **`commission_pct_bps` → % of PT-package revenue** is attributed to
    `pt_packages.trainer_id` (the trainer assigned at sale time).
  - **`session_fee_kopecks * sessions_count` → fixed per session** is
    attributed to `pt_sessions.trainer_id` (the trainer who conducted).
  - A trainer with a hybrid config gets BOTH components: pct on packages
    they were assigned + fixed-per-session on sessions they conducted.
  - Every payroll SQL query carries an inline comment `-- attribution:
    assigned-at-sale` or `-- attribution: conducting` to prevent silent
    drift (project standard for ambiguous JOINs).
  - The clawback hook (PAY-06 / D-58-20) uses the **assigned-at-sale**
    attribution: a PT-package refund triggers a clawback against the
    trainer to whom the package was originally assigned, not against the
    session-conducting trainer. (A refund cancels the package; the
    session-fee accruals already booked for conducted sessions are
    unaffected — those sessions happened; the trainer earned their
    per-session fee independent of the eventual refund.)

### Claude's Discretion
- Exact wording of the 4–6 audit event names (the set above is the
  minimum; the planner may split or rename within the LOCKED_AUDIT_EVENTS
  cardinality target of "≤6 new" implied by ROADMAP SC#5).
- Whether `(EDIT, COMPENSATION)` collapses into `(CREATE, COMPENSATION)`
  given the INSERT-only versioning model (D-58-02 makes "edit" semantically
  identical to "create new version"). Planner picks the smallest pair set
  that maintains can.ts/registry.ts coherence.
- Exact column order, index list, and constraint names in the Alembic
  migration (`0041_payroll_foundations.py`); the schema CONTRACT is
  D-58-02..05, but Alembic column ordering is the planner's call.
- Whether `app/modules/payroll/constants.py` carries inline literals for
  cross-module subject-kind strings (e.g., `SUBJECT_KIND_PT_PACKAGE`)
  mirroring the `pt_packages.service` locally-pinned-literal pattern
  (D-33-11 step 3 commentary). Planner decides; the principle (no import
  of `payments.constants`) is locked.
- Test file layout (one `test_payroll_*.py` per endpoint vs grouped),
  fixture builder placement (in existing `tests/factories/` vs new
  `tests/factories/payroll.py`), and the exact deterministic kopeck
  amounts used in golden tests.
- Whether the `commission_pct_bps` upper bound is 10000 (100%) or higher
  (some gyms in RU/CIS pay > 100% as a promo "double commission" month).
  Default: cap at 10000 per ARCHITECTURE.md; planner may raise if domain
  research surfaces a real-world > 100% rate.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap (source of truth on scope)
- `.planning/REQUIREMENTS.md` §"PAY-01..06" — exact wording of all six
  requirements; "оба nullable", "append-only", "snapshot ставки", "single
  allowed mutation", and "append-only clawback" are verbatim contract.
- `.planning/ROADMAP.md` §"Phase 58: Payroll Foundations + Ledger" —
  goal + 5 success criteria (authoritative on RBAC parity, INFRA-15
  pre-registration, 6 LOCKED_AUDIT_EVENTS, clawback in same UoW).
- `.planning/PROJECT.md` — Key Decisions log; v1.4 ledger discipline +
  v1.2 snapshot discipline + v1.8 read-only cross-module SQL discipline
  are the precedents this phase mirrors.

### v1.9 research (locked decisions; do NOT re-derive)
- `.planning/research/SUMMARY.md` — Executive summary + Discrepancy
  Resolutions §1 (comp-config placement), §2 (clawback append-only), §3
  (6-phase v1.9 structure). The four pitfall mitigations in §"Critical
  Pitfalls" are LOCKED inputs to D-58-02..06.
- `.planning/research/ARCHITECTURE.md` §"Question 1: Where Does Payroll
  Live?" — module placement, `trainer_payroll_accruals` schema, cross-module
  read SQL (`fetch_trainer_session_revenue`), atomic audit chain. D-58-01,
  D-58-03, D-58-19 derive directly from here.
- `.planning/research/PITFALLS.md` §"Pitfall 1..6" — recompute drift,
  double-run race, % rounding, refund clawback, rate-config drift,
  attribution ambiguity. Every D-58-0X has a pitfall counterpart.
- `.planning/research/STACK.md` — Confirms zero new dependencies; `decimal`
  + `zoneinfo` stdlib only.
- `.planning/research/FEATURES.md` — PAY-01..06 feature definitions
  (anti-features: tiered commission, "void accrual", reuse of `payments`
  table for payroll, auto period-detection).

### Prior CONTEXTs (precedent for discipline this phase mirrors)
- `.planning/milestones/v1.8-phases/54-foundations-module-scaffold-rbac-parity-indexes/54-CONTEXT.md` —
  INFRA-15 precedent: preemptive module registration in `.importlinter`,
  three-way RBAC parity, audit event pre-registration. Phase 58 is the
  v1.9 analog of Phase 54.
- `.planning/milestones/v1.8-phases/57-openapi-handoff-milestone-verification/57-CONTEXT.md` —
  Documents the v1.8 milestone-close pattern; informs what Phase 61 will
  consume (NOT what Phase 58 produces directly, but worth scanning).

### Backend code under direct edit (READ before planning)
- `apps/backend/app/core/permissions.py` §40-41 — existing
  `Resource.PAYROLL` + `Resource.COMPENSATION` members; §66-67 — existing
  `(VIEW, PAYROLL)` + `(VIEW, COMPENSATION)` OWNER_ONLY pairs. New write
  pairs land here (D-58-15).
- `apps/backend/app/core/audit.py` §244 — `LOCKED_AUDIT_EVENTS` frozenset;
  §460-519 — `emit()` validation. New events land in the frozenset
  (D-58-16).
- `apps/backend/app/core/audit_hash.py` — hash-chain machinery used by
  `audit.emit()`; no edits, but understand the invariant.
- `apps/backend/.importlinter` §"modules-independent" — registration
  list (mirror Phase 54 D-54-09 add of `reports`). Add `app.modules.payroll`
  (D-58-18).
- `apps/backend/app/main.py` — Protocol-slot registration site. New
  `register_payroll_clawback_recorder(...)` wires the slot at startup
  (D-58-20). Read the existing `register_*` patterns.
- `apps/backend/app/core/dependencies.py` — Protocol-slot getter helpers
  (`get_payment_refunder()` etc.). New `get_payroll_clawback_recorder()`
  follows the same shape.

### Backend code referenced read-only (do NOT edit, must understand)
- `apps/backend/app/modules/pt_packages/service.py:1038` —
  `refund_pt_package` D-33-11 sequence; clawback hook inserts between
  steps 6 and 8. PRESERVE the existing UoW discipline and audit chain
  ordering.
- `apps/backend/app/modules/pt_packages/router.py:460` — `/api/v1/pt-packages/{id}/refund`
  endpoint; the clawback flows through this surface but the endpoint
  signature is unchanged in Phase 58.
- `apps/backend/app/modules/pt_sessions/models.py` — `trainer_id`,
  `pt_package_id`, `performed_at`, `cancelled_at` columns referenced by
  cross-module payroll SQL (D-58-19).
- `apps/backend/app/modules/payments/models.py` — `subject_kind`,
  `subject_id`, `amount_kopecks`, `received_at`, `refund_of` columns
  referenced by cross-module payroll SQL.
- `apps/backend/app/modules/memberships/service.py` — for the v1.4 ledger
  discipline pattern (append-only INSERT, atomic audit chain, SVC001
  commit gate); plus the cross-module-write-via-Protocol-slot pattern
  (`PaymentRecorder`).
- `apps/backend/alembic/versions/` — current head is `0040`; new migration
  is `0041_payroll_foundations.py`. Read 2-3 recent migrations for the
  project's Alembic style (env hash, function-naming, FK ON DELETE policy).

### Frontend code under direct edit (admin-web frozen otherwise)
- `apps/admin-web/src/shared/session/can.ts` §15-16 — existing
  `{ action: 'view', resource: 'payroll' }` + `compensation` entries; new
  write/run/refund pairs mirror permissions.py byte-for-semantic (D-58-15).
- `apps/admin-web/src/shared/session/registry.ts` §8-9 — existing
  `'payroll' | 'compensation'` resource union. NO new resources added
  in Phase 58 (Resource.PAYROLL + COMPENSATION already exist); only the
  OWNER_ONLY pair tuples grow. Confirm three-way parity test recognizes
  the new pair set.

### Test infrastructure
- `apps/backend/tests/conftest.py` — `authed_client_owner`,
  `authed_client_reception`, SAVEPOINT-per-test isolation, db_session,
  factory builders. New `trainer_comp_config` + `trainer_payroll_accrual`
  factories land in (or next to) this file.
- `apps/backend/tests/integration/` — existing module-test directory
  shape (e.g., `tests/integration/reports/`); new
  `tests/integration/payroll/` mirrors the pattern.
- `apps/backend/tests/contracts/` (or equivalent) — TEST-06 RBAC parity
  test + LOCKED_AUDIT_EVENTS parity test. Both consume the
  permissions.py + audit.py edits transparently; the count assertions
  bump automatically when new tuples land.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`PaymentRefunder` Protocol slot pattern** (`pt_packages.service.refund_pt_package`
  D-33-11) — exact template for `PayrollClawbackRecorder` slot.
  Same registration site (`main.py`), same getter (`dependencies.py`),
  same caller-owns-UoW discipline.
- **`payments` ledger append-only schema** — direct schema template for
  `trainer_payroll_accruals` (signed amounts, no UPDATE, single-transition
  status flip is the only allowed mutation).
- **Memberships price snapshot pattern** (v1.2 `memberships.price_kopecks_snapshot`
  + `plan_name_snapshot`) — exact template for `trainer_payroll_accruals`
  rate/config snapshot columns.
- **`reports` module raw-SQL `text()` cross-module read pattern** (v1.8
  D-54-08) — template for `payroll/repository.py` cross-module reads of
  `pt_sessions` + `pt_packages` + `payments`. Zero `ignore_imports` edges.
- **TEST-06 three-way RBAC parity test machinery** (existing) — bumps
  automatically when new `OWNER_ONLY` tuples land in permissions.py +
  can.ts; no test rewrite needed, only the parity count assertion.
- **`audit_hash.py` hash-chained emit + `LOCKED_AUDIT_EVENTS` frozenset
  validation** — guarantees `audit.emit("payroll_accrual_*", ...)` either
  works or raises `AuditEventNotLockedError` at first call. No new audit
  machinery; only frozenset growth.
- **Phase 54 INFRA-41 preemptive `.importlinter` registration** — exact
  precedent for `app.modules.payroll` listing before code lands.
- **`SVC001` commit-gate convention** — orchestrator owns the explicit
  `await session.commit()`; service helpers never commit. Inherited
  by `payroll.service`.

### Established Patterns
- **DB-wins-the-race idempotency** — `INSERT ... ON CONFLICT (...) DO
  NOTHING RETURNING id`, never SELECT-then-INSERT. Already used on
  visits, memberships, payments refunds. PAY-03 mirrors this verbatim.
- **Inclusive `[start, end]` MSK date ranges** — `memberships.end_date`,
  `visits.gym_date`, `gym_date STORED AS (... AT TIME ZONE 'Europe/Moscow')::date`.
  PAY-02 and PAY-03 use the same convention.
- **Integer kopeck money + integer numerator-denominator rate** — never
  FLOAT; `math.ceil` rounding in the customer/trainer's favor. Inherited
  from v1.4.
- **Single-transition status flip** — `pt_packages.status` precedent;
  `trainer_payroll_accruals.status` 'pending' → 'paid' is the only
  allowed mutation, gated by `SELECT ... FOR UPDATE` + 409 on second
  attempt.
- **Pagination envelope `{items, total, page, pageSize}`** — universal
  list-endpoint shape; PAY-05 mirrors.
- **`snake_case` error_code in 4xx responses** — `cancel_window_expired`,
  `original_payment_not_found`, `already_refunded`. PAY-03/04 use
  `comp_config_missing`, `payroll_period_already_run`, `already_paid`.

### Integration Points
- **`app/main.py`** — new `register_payroll_clawback_recorder(slot)`
  call at startup (mirrors `register_payment_refunder`). The slot
  implementation lives in `app/modules/payroll/clawback.py` (or
  `service.py` — planner decides).
- **`app/core/dependencies.py`** — new
  `get_payroll_clawback_recorder() -> PayrollClawbackRecorder` helper
  (mirrors `get_payment_refunder`).
- **`pt_packages.service.refund_pt_package`** (line 1038) — adds one
  `get_payroll_clawback_recorder()` call between current steps 6 and 8
  of the D-33-11 sequence. The orchestrator's `session.commit()` (step 8)
  still owns the entire UoW (refund payment row + pt_package_refunded
  audit + payroll_clawback row + payroll_clawback_recorded audit). The
  pt_package_refunded audit DOES NOT include the clawback info — those
  are two separate audit rows in the chain.
- **`apps/backend/app/api/v1/__init__.py`** (or equivalent router
  registration) — new `payroll.router` mounted under `/api/v1/payroll/`.
- **`apps/admin-web/src/shared/session/can.ts` + `registry.ts`** — the
  ONLY admin-web files Phase 58 may touch (v1.9 milestone goal:
  "apps/admin-web не трогаем" — the OWNER_ONLY mirror is treated as
  RBAC infrastructure, NOT a UI change; precedent: every prior INFRA-N
  RBAC phase touched both files).

</code_context>

<specifics>
## Specific Ideas

- The clawback row is **inserted in the same SQLAlchemy `session` as the
  refund payment row**. The orchestrator (`refund_pt_package`) calls into
  the Protocol slot inside the existing UoW; the slot uses the passed
  `session` and does NOT open a new transaction. This is the only way to
  guarantee the requirement "не UPDATE существующей строки" + "same-UoW"
  simultaneously.
- The **deterministic kopeck examples** used in golden tests should include
  at least: (a) a pure-pct case proving `math.ceil` rounding gives the
  trainer the extra kopeck; (b) a pure-fixed-fee case; (c) a hybrid case;
  (d) a clawback case where the refunded payment exactly cancels the
  commission portion of a single session; (e) a clawback case where the
  refund is a partial PT-package value (currently NOT supported per B-02
  deferred — but the test fixture should document the assumption so
  Phase 60+ has a clear extension point).
- The "trainer assigned at sale" attribution (D-58-21) hinges on
  `pt_packages.trainer_id`. **Verify at plan time** that this column is
  NOT nullable and is immutable post-INSERT (no UPDATE path). If it IS
  nullable / mutable, the attribution model needs a documented fallback
  (likely: skip clawback if `pt_package.trainer_id IS NULL`).
- `(EDIT, COMPENSATION)` may NOT need to exist as a distinct pair given
  the INSERT-only versioned model. The planner should evaluate whether
  the WRITE surface for comp config is best modeled as one `CREATE` pair
  (semantically: "create a new version of the config") or two
  `CREATE` + `EDIT` pairs (for can.ts coherence — admin-web may render
  "Edit config" UI in a future milestone, even though it always
  generates an INSERT server-side). Default: `(CREATE, COMPENSATION)`
  alone, with `EDIT` only if can.ts requires it.

</specifics>

<deferred>
## Deferred Ideas

- **Membership refund → trainer clawback** — not in scope; PAY-06 is
  PT-package refund only. Memberships are not commissionable today
  (commission applies to PT-package revenue per attribution model).
  If future milestones introduce commission on memberships, the
  `PayrollClawbackRecorder` Protocol slot already exposes a clean
  extension surface (a second method `record_clawback_for_membership_refund`
  can be added without disturbing this phase's wiring).
- **Online-refund → trainer clawback** — same as above; online refunds
  flow through the same subject-side service paths
  (`pt_packages.service.refund_pt_package` is invoked from the operator
  refund endpoint regardless of original payment method). The clawback
  hook fires once per PT-package refund, online or cash.
- **Partial PT-package refund (B-02)** — still deferred from v1.4. When
  introduced, the clawback amount becomes a proportional negative
  (`refund_kopecks / original_kopecks * accrued_commission_kopecks`,
  with ceil); the snapshot columns on the original accrual remain
  immutable.
- **`unpay` / accrual void** — explicit anti-feature per REQUIREMENTS
  PAY-04 ("операции unpay нет"). Corrections are append-only adjustment
  rows.
- **`trainer_payroll_accruals` UPDATE via "edit accrual"** — explicit
  anti-feature; mirror the v1.4 payments ledger's "never UPDATE" rule.
- **Auto period-detection** — explicit anti-feature; the operator
  always supplies `period_start` + `period_end`.
- **`commission_pct_bps > 10000` (promo double-commission)** — held back
  pending domain research; Phase 58 enforces ≤ 10000 (100%).
- **Compensation history endpoint** (`GET /payroll/trainer-configs/{id}/history`)
  — useful but NOT in PAY-01..06. Phase 60 trainer-usage report may
  expose recent rates via raw-SQL read; a dedicated history endpoint
  ships in a future milestone if surfaced as a need.
- **Filter-by-status on PAY-05** (`?status=pending` / `?status=paid`)
  — NOT in REQUIREMENTS PAY-05 wording. Easy add post-v1.9 if Phase 60
  trainer report shows the operator needs it before the full list view.
- **Trainer self-service "view my accruals"** — not in scope; v1.9 is
  owner-only payroll. Trainer portal is a future milestone (admin-web
  frozen in v1.9).
- **1C / external payroll export, payroll PDF** — out of scope.

None of the above are scope creep into Phase 58.

</deferred>

---

*Phase: 58-payroll-foundations-ledger*
*Context gathered: 2026-05-25*
