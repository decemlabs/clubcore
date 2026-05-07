# Phase 17: Membership Instances + Resolver (backend) - Context

**Gathered:** 2026-05-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 17 ships the **membership-instance domain** — the row that records "client X bought plan Y on date Z" with snapshot pricing — plus the **active-membership resolver** that Phase 19 visits will validate against. Second business-surface phase of v1.2 after Phase 16's plan catalog.

In scope:
- Alembic migration `0005_memberships.py` (down_revision = `0004_membership_plans`) — `memberships` table per MEM-01: `id` UUID PK, `client_id` UUID NOT NULL FK clients.id ON DELETE RESTRICT, `plan_id` UUID NOT NULL FK membership_plans.id ON DELETE RESTRICT, `duration_days_snapshot` INT, `price_kopecks_snapshot` BIGINT, `plan_name_snapshot` VARCHAR(120), `start_date` DATE, `end_date` DATE (inclusive), `status` VARCHAR CHECK IN ('active','expired','cancelled') DEFAULT 'active', `cancelled_at` TIMESTAMPTZ NULL, `cancel_reason` TEXT NULL, `paid_at` TIMESTAMPTZ NULL, `notes` TEXT NULL, `activation_policy` VARCHAR DEFAULT 'purchase_date' CHECK = 'purchase_date'. Index on `(client_id, status, end_date DESC)` per MEM-01. **No soft-delete column** — lifecycle is purely status-based.
- Extend `app/modules/memberships/` (currently plans-only post-Phase-16): add `Membership` ORM model to `models.py`, sale/cancel/list to `service.py`, repository CRUD to `repository.py`, schemas, mount 4 endpoints in `router.py`. Service uses Phase 15 `BusinessService` template (every write path commits explicitly; AST gate already covers `app.modules.memberships.service` from Phase 16).
- 4 endpoints under `/api/v1/memberships`:
  - `GET    /api/v1/memberships?clientId&status` — list, paginated (MEM-EP-01)
  - `GET    /api/v1/memberships/{id}` — read single (MEM-EP-02)
  - `POST   /api/v1/memberships` — sell, 201 (MEM-EP-03)
  - `POST   /api/v1/memberships/{id}/cancel` — cancel, 200 (MEM-EP-04)
- RBAC mapping: GET (list/get) → `Depends(require_permission(VIEW, MEMBERSHIPS))` (reception+owner); POST sell → `(CREATE, MEMBERSHIPS)` + CSRF (reception+owner — NOT in OWNER_ONLY); POST cancel → `(CANCEL, MEMBERSHIPS)` + CSRF (owner-only — IS in OWNER_ONLY). RBAC-04 ordering: `require_permission` declared before `verify_csrf` in signatures (clients pattern).
- 2 audit events emitted via `app.core.audit.emit()`, both already in `LOCKED_AUDIT_EVENTS` (Phase 15):
  - `membership_created` `{membership_id, client_id, plan_id, end_date}` on POST sale.
  - `membership_cancelled` `{membership_id, client_id, reason?}` on POST cancel (reason key absent when null per D-09).
  - `membership_expired` is **Phase 18** (ARQ daily) — not emitted here.
- `core/dependencies.py` extension (MEM-05): add `ActiveMembership` Protocol (`id, client_id, end_date, status`), `ActiveMembershipResolver` callable type, `register_active_membership_resolver(resolver)` setter, `resolve_active_membership(session, client_id)` consumer — verbatim mirror of `register_user_loader` slot pattern (Phase 4 D-24).
- `app/main.py:create_app()` extension: registers `app.modules.memberships.service.resolve_active_membership_by_client` as the resolver before lifespan starts. Same composition-root carve-out as `register_user_loader` (importlinter `core-not-depend-on-modules` scopes `source_modules = app.core`, not `app`).
- **Phase 16 D-15 closure**: extend `_is_plan_in_use_conflict(exc)` and translate FK-constraint IntegrityError on `fk_memberships_plan_id_membership_plans` to 409 `plan_in_use` in `app/modules/memberships/service.py:soft_delete_plan`. ROADMAP Phase 16 SC#4 wording is updated to match D-04 below ("any membership blocks", not "non-cancelled").
- OpenAPI byte-stable regeneration: `apps/backend/openapi.json` rewritten as part of the phase. Phase 21 handles `schema.d.ts` regen.
- Tests:
  - `tests/integration/memberships/test_memberships_crud.py` — sale + cancel happy paths + 422 boundaries.
  - `tests/integration/memberships/test_memberships_list.py` — pagination, sort, filter (clientId, status).
  - `tests/integration/memberships/test_memberships_rbac.py` — reception 403 on cancel; reception 200 on sale; owner 200 on cancel.
  - `tests/integration/memberships/test_memberships_audit.py` — `membership_created` / `membership_cancelled` payloads visible after success; co-transactional rollback masks them on failure.
  - `tests/integration/memberships/test_plan_in_use.py` — sell membership against plan → DELETE plan → 409 `plan_in_use`.
  - `tests/integration/memberships/test_resolver.py` — multi-active tiebreak (latest end_date, then created_at DESC); resolver returns None for cancelled-only / expired-only / never-bought clients.
  - `tests/unit/memberships/test_state_machine.py` — TESTS-10 9-cell transition matrix.
  - `tests/unit/memberships/test_schemas.py` — Pydantic boundaries (extra='forbid', explicit-null guard, max_length on notes/reason, paidAt accepts ISO timestamp).
  - `tests/unit/test_audit_taxonomy.py` — TESTS-09 already enforces; no extension needed (the 3 `membership_*` events are pre-locked).
- `.importlinter` contracts unchanged — `app.modules.memberships` still consumes only `app.core.*` symbols. The composition-root resolver-registration is in `app/main.py` (out-of-scope for `core-not-depend-on-modules`).

Out of scope (locked to later phases):
- ARQ `expire_memberships` daily job + `membership_expired` audit emit — **Phase 18**.
- `visits` table + reception check-in + Telegram bot `/checkin` — **Phases 19, 20**.
- admin-web `/memberships/*` route + `features/memberships` — **Phase 22**.
- `schema.d.ts` regeneration via api-client codegen — **Phase 21**.
- ЮKassa payment integration; `paid_at` is set manually today (operator timestamp) — **v1.3+**.
- Membership freeze, visit-count plans, expiring-soon notifications — **v1.3+** (Out of Scope per PROJECT.md).
- Active-sessions backend endpoints + Argon2/UUID 401 mapping (HYG-01..03) — **Phase 23**.

</domain>

<decisions>
## Implementation Decisions

### Sale validation policy

- **D-01:** **Stacking allowed — no pre-flight active-membership check.** POST `/memberships` for a client who already has an active membership inserts a 2nd `status='active'` row. The resolver tiebreaks on latest `end_date`, then `created_at DESC` (locked MEM-04). Rationale: MEM-04 already documents "multiple active memberships" as accepted reality; pre-flight SELECT adds latency + race window without preventing legitimate stacking (renewals, owner overrides, edge-case manual entries). No `409 'already_active'` error code.
- **D-02:** **`plan.active=false` → 409 `plan_inactive`**. Service-layer defence against UI bypass (the reception sell screen filters via `?active=true` per Phase 16 D-08, but a malformed/replayed POST can still reference a deactivated plan). Service: `repo.get_plan_alive(plan_id)` → 404 if soft-deleted; then `if not plan.active: raise PlanInactiveError(409, code='plan_inactive')`. `PlanInactiveError(ConflictError)` lives in `app/core/exceptions.py` alongside `PlanNameExistsError` / `PlanNotFoundError` (Phase 16 D-03 precedent — domain errors aggregate in core/exceptions, not per-module).
- **D-03:** **POST body shape: `{clientId, planId, paidAt?, notes?}`.**
  - `paidAt: datetime | None = None` — omit → DB column NULL. Manual sales today record NULL (operator paid in cash, system records the `created_at` as the sale moment); ЮKassa flow in v1.3 will populate it. If owner explicitly passes an ISO timestamp (back-dating cash receipts), accept it. No `default_factory=now` — keeps `created_at` (sale time) and `paid_at` (payment confirmation time) cleanly separable.
  - `notes: str | None = Field(default=None, max_length=1000)` — free-text, no sanitization beyond Pydantic str. NULL when omitted.
  - `clientId` and `planId` are required UUIDs; FastAPI's `UUID` type rejects malformed input as 422.
  - Wire format: camelCase via `BackendSchemaBase.alias_generator=to_camel` (locked).
  - `start_date` is server-computed (`(now() AT TIME ZONE 'Europe/Moscow')::date`); the client never passes it. `activation_policy` is server-set to `'purchase_date'` (DB CHECK = 'purchase_date'); not in the request body.
- **D-04:** **`start_date` and `end_date` computed server-side at insert.**
  - `start_date = (now() AT TIME ZONE 'Europe/Moscow')::date` — same TZ rule as `gym_date` (PROJECT.md Phase 15 Key Decision); Postgres `date` math.
  - `end_date = start_date + (duration_days_snapshot - 1) DAYS` — inclusive, last valid check-in day (PROJECT.md Phase 15 Key Decision: ARQ uses `end_date < CURRENT_DATE` strict, so the last day stays valid).
  - Snapshot fields populated from the `MembershipPlan` row read inside the same transaction: `plan_name_snapshot = plan.name`, `duration_days_snapshot = plan.duration_days`, `price_kopecks_snapshot = plan.price_kopecks`. Subsequent plan edits never propagate (locked MEM-02).
  - Implementation: compute in Python via `datetime.now(ZoneInfo("Europe/Moscow")).date()` — explicit and testable; avoids a server-side `now()` round trip and aligns with the Pydantic validator chain. The `gym_date` STORED column for visits (Phase 19) uses Postgres `AT TIME ZONE` because it's a generated column; sale-time `start_date` does not have that constraint.

### DELETE plan + plan_in_use scope (Phase 16 D-15 closure)

- **D-05:** **FK is the gate; ANY membership row blocks plan deletion.** The FK is `fk_memberships_plan_id_membership_plans ON DELETE RESTRICT` (locked MEM-01). The service's `soft_delete_plan` (currently in `service.py` from Phase 16) extends to catch `IntegrityError` and call a new helper `_is_plan_in_use_conflict(exc)` that checks `exc.orig.constraint_name == "fk_memberships_plan_id_membership_plans"` (asyncpg attribute) with substring fallback. On match → `await session.rollback()` then raise `PlanInUseError(409, code='plan_in_use')`. `PlanInUseError(ConflictError)` lives in `app/core/exceptions.py`.
- **D-06:** **Cancelled/expired memberships ALSO block deletion.** Direct corollary of D-05 — they keep a foreign-key reference. Rationale: cancelled rows are part of the audit trail; allowing the plan to vanish would orphan the snapshot's plan-id reference and complicate any future ad-hoc query like "all sales of plan X this year". Snapshots already preserve forensic plan_name/duration/price, but the plan_id link is still meaningful for joins.
- **D-07:** **ROADMAP Phase 16 SC#4 wording is updated to match D-05/D-06.** The current ROADMAP text says "non-cancelled Membership references it"; the planner must include a small ROADMAP edit in this phase (or add an explicit deviation note in `17-VERIFICATION.md`) to read "any Membership references it (FK ON DELETE RESTRICT)". This is a clarification, not a scope change — the ROADMAP wording predated the explicit decision.
- **D-08:** **`soft_delete_plan` ordering becomes: get → mutate (set `deleted_at = now()`) → `audit.emit("membership_plan_archived")` → `flush()` (FK check fires here on existing-membership case → IntegrityError) → `commit()`.** The audit emit happens BEFORE flush — mirrors Phase 16 D-14 for archive. If the FK rejects the row, the IntegrityError translation rolls back the audit emit too (co-transactional — Phase 16 D-14 contract).

### Memberships list defaults

- **D-09:** **`GET /memberships` query: `clientId` optional, default returns all 3 statuses, sort=`created_at_desc`.**
  - `clientId: UUID | None = None` — optional. Owner can call without it for a global feed; reception+owner pass it for the client-detail block. RBAC is `VIEW, MEMBERSHIPS` regardless (reception is allowed).
  - `status: MembershipStatus | None = None` — single-value enum filter. Omit → no WHERE on status (returns active, expired, cancelled). UI can call `?status=active` for the live block, `?status=expired&status=cancelled`-style multi-value is NOT supported — UI does separate calls or omits the filter.
  - `sort: MembershipListSort = CREATED_AT_DESC` — enum with members `created_at_desc` (default), `end_date_desc`, `start_date_desc`. Single sort axis only.
  - `PageQuery` (page=1, page_size=20, max 100) — locked v1.1 contract.
  - **No `q` text search**, **no date-range filter** (`from`/`to`) in Phase 17. Phase 22 may revisit if owner UI surfaces filters; visits has a `from`/`to` filter per Phase 19 SC, memberships does not.
  - Soft-deleted plans are not a concern for this list (memberships have no `deleted_at`); the response includes the `plan_id` (for joining to plan name/details) AND the snapshot fields.
- **D-10:** **Response shape includes ALL snapshot fields.** `MembershipResponse` exposes: `id`, `clientId`, `planId`, `planNameSnapshot`, `durationDaysSnapshot`, `priceKopecksSnapshot`, `startDate`, `endDate`, `status`, `cancelledAt`, `cancelReason`, `paidAt`, `notes`, `createdAt`, `updatedAt`. The frontend (Phase 22) needs the snapshots to render historical sales correctly even if the plan was later edited or deleted. No PII in snapshots (just plan name).

### Cancel contract + idempotency

- **D-11:** **POST `/memberships/{id}/cancel` body: `{reason?: str | None = Field(default=None, max_length=500)}`.** Reason is optional (matches MEM-AUDIT-01 which makes `reason?` optional in the audit payload). Max length 500 — half the notes ceiling (D-03); a cancellation reason is a short operator note ("client requested", "double sale", "data error"), not a free-form essay. `BackendSchemaBase` + explicit-null guard (mirror of Phase 16 D-05) — POST `{"reason": null}` is rejected with the same explicit-null message; omitting the key is the way to indicate "no reason".
- **D-12:** **Transition rules + 409 `invalid_transition` payload.** Verbatim MEM-03:
  - `active → cancelled`: allowed; sets `status='cancelled'`, `cancelled_at=now()` (server-side timestamp, UTC), `cancel_reason=<body>` (or NULL).
  - `expired → cancelled`: 409 `invalid_transition` with payload `{from_status: 'expired', to_status: 'cancelled'}`.
  - `cancelled → cancelled`: 409 `invalid_transition` with `{from_status: 'cancelled', to_status: 'cancelled'}`.
  - 404 `membership_not_found` if the id doesn't exist.
  - `InvalidTransitionError(ConflictError)` in `core/exceptions.py`; constructor takes `from_status` + `to_status` and packs them into the response envelope's `details` field.
- **D-13:** **"Expired by date but still status='active'" rows can be cancelled.** Edge case: client's `end_date` was yesterday but Phase 18's ARQ hasn't run yet (status still 'active'). Owner cancels → service follows `active → cancelled` happy path. The status field is the gate (locked MEM-03), not the date. ARQ Phase 18 will skip the row on its next run because `status != 'active'` (the daily UPDATE filter is `WHERE end_date < CURRENT_DATE AND status='active'`). No conflict.
- **D-14:** **`membership_cancelled` audit payload shape.** Per Phase 15 LOCKED `{membership_id, client_id, reason?}`. When `reason` is None: omit the `reason` key from the kwargs to `audit.emit` entirely (don't pass `reason=None`). The `?` in the locked spec means "key may be absent", not "value may be null" — keeps the audit JSONB compact and consistent with how Phase 16's `changed_fields`-only payload skipped before/after. Implementation: `kwargs = {} if reason is None else {"reason": reason}` then `await audit.emit(session, "membership_cancelled", actor_user_id=actor.id, resource_type="membership", resource_id=mem.id, client_id=mem.client_id, **kwargs)`.
- **D-15:** **Cancel emit ordering.** Mirror Phase 16 D-14 update path: get → check transition (raise InvalidTransitionError if invalid; raises BEFORE any state change) → mutate (status='cancelled', cancelled_at=now(), cancel_reason=...) → flush → emit `membership_cancelled` → refresh(updated_at) → commit. Status transition is checked before mutation, so an invalid transition never produces a partial write or a stray audit row.

### Resolver mechanics (defaults — area not interactively discussed)

- **D-16:** **Resolver is a plain awaitable, NOT a FastAPI Depends.** `resolve_active_membership(session, client_id)` is called directly from `app.modules.visits.service` in Phase 19 — no Depends wrapper. Mirrors `register_user_loader` precedent: the user-loader is a plain awaitable consumed by `get_current_user` (which IS a Depends). Wrapping the membership resolver as a Depends forces every visit-creating endpoint to declare it in the signature, which couples the visits router to a cross-module concern that belongs in the service layer.
- **D-17:** **Multi-active scenario — silent tiebreak, no warning log.** When the resolver query returns >1 row, ORDER BY `end_date DESC, created_at DESC LIMIT 1` picks the canonical one. No structlog warning, no audit event. Rationale: D-01 makes stacking a deliberate operator workflow (renewals, overrides); flagging it as anomalous would create alert fatigue. If owner UX in Phase 22 wants a "this client has multiple active memberships" badge, the list endpoint with `?status=active&clientId=...` returns all of them — the UI computes the badge.
- **D-18:** **`ActiveMembership` Protocol exposes only the consumer-needed columns.** Per MEM-05: `id, client_id, end_date, status`. The Protocol does NOT include snapshot fields, plan_id, dates other than end_date, or audit timestamps — visits doesn't need them. The repository fetches the full ORM row but the Protocol-typed return narrows the surface that core code can rely on. Implementation note: the resolver returns a SQLAlchemy `Membership` ORM instance (which structurally satisfies the Protocol because all 4 attributes are mapped); no DTO conversion needed at the boundary.

### State machine (TESTS-10) — explicit matrix

- **D-19:** **9-cell transition matrix asserted in `test_state_machine.py`** (TESTS-10). Cells (from_status × action):
  - `active × cancel` → ✅ allowed (D-12).
  - `active × expire` → ✅ allowed (Phase 18 ARQ; tests can simulate via direct service call).
  - `active × create-self` → N/A (creation is `void → active`, not a transition from active).
  - `expired × cancel` → ❌ 409 `invalid_transition`.
  - `expired × expire` → ❌ 409 `invalid_transition` (already expired).
  - `expired × create-self` → N/A.
  - `cancelled × cancel` → ❌ 409 `invalid_transition`.
  - `cancelled × expire` → ❌ 409 `invalid_transition`.
  - `cancelled × create-self` → N/A.
  - The `expire` action's failure cases are tested even though the ARQ job is Phase 18 — the service-layer transition guard `_assert_can_expire(membership)` is shipped in Phase 17 (called by `cancel_membership`'s sibling `_expire_membership` private helper, exposed for Phase 18 to import) so the matrix is fully testable now. Phase 18 just adds the cron scheduling on top.

### Migration + index strategy

- **D-20:** **Migration filename: `0005_memberships.py`. down_revision = `"0004_membership_plans"`.** Confirm via `alembic heads` against dev DB before authoring. NAMING_CONVENTION expands constraint names deterministically: `ck_memberships_status`, `ck_memberships_activation_policy`, `fk_memberships_client_id_clients`, `fk_memberships_plan_id_membership_plans`, `ix_memberships_client_id_status_end_date`. The composite resolver index `(client_id, status, end_date DESC)` uses `Index(...)` in `__table_args__` — DESC order is encoded via `text("end_date DESC")`. NO partial-unique on memberships — duplicate active memberships are explicitly allowed by D-01.
- **D-21:** **No additional index on `plan_id` alone.** Postgres does NOT auto-create btree on FK columns, but the resolver's composite index does NOT cover `plan_id` lookups. Phase 17's plan_in_use FK check is a sequential scan on a small table (≤20 plans × few hundred memberships in one zal) — acceptable. Add `Index('ix_memberships_plan_id', 'plan_id')` ONLY if Phase 22 surfaces a "memberships sold per plan" report with paginated reads; not pre-emptively. The FK metadata still produces a constraint but no btree.

### Claude's Discretion

- **CD-01:** Exact wording of `PlanInactiveError`, `PlanInUseError`, `InvalidTransitionError`, `MembershipNotFoundError` message strings + FastAPI route summaries/descriptions + OpenAPI examples. Goal: consistency with `PlanNameExistsError` / `PhoneExistsError` precedent.
- **CD-02:** Test file granularity within `tests/integration/memberships/` — `test_memberships_crud.py` may be split into `test_create.py` / `test_cancel.py` if the file exceeds ~300 lines. Mirror clients pattern (single file) by default.
- **CD-03:** Whether `_assert_can_cancel` and `_assert_can_expire` live as module-level free functions in `service.py` or as a small private state-machine helper module (`_state.py`). Default: free functions in `service.py` (clients pattern).
- **CD-04:** Migration ordering inside `0005_memberships.py.upgrade()`: by current convention (`0002_clients` / `0004_membership_plans` references) — `op.create_table` → CHECK constraints (in `__table_args__` if SA-friendly; the activation_policy CHECK is `= 'purchase_date'` which is SA-friendly) → composite index via `op.create_index` (DESC ordering may need raw `op.execute` if SA's `text()` doesn't autogen — planner picks the cleanest layout).
- **CD-05:** Whether `MembershipResponse` exposes the FK plan as just `planId` or also embeds a `planNameCurrent` joined field (showing the plan's current display name vs the snapshot). Default: `planId` only — joining adds query cost; the snapshot covers the historical view; Phase 22 can add a separate `?expand=plan` if owner needs both.
- **CD-06:** Resolver helper exposure — whether `resolve_active_membership_by_client` is a public symbol of `app.modules.memberships.service` (importable everywhere) or only the registered callback. Default: public symbol — tests in `test_resolver.py` import it directly without going through `core/dependencies.py`'s registered slot.

### Locked-not-discussed (carried verbatim from REQUIREMENTS / Phase 15)

- **Schema** is REQUIREMENTS-locked: column types, NOT NULL/NULL flags, FK directions, CHECK constraints, single composite index — no discussion needed.
- **Snapshot semantics** (MEM-02) are REQUIREMENTS-locked: snapshot at insert, never propagate plan edits.
- **Inclusive `end_date`** is PROJECT.md-locked (Phase 15 Key Decision).
- **`activation_policy='purchase_date'` only** is REQUIREMENTS-locked (CHECK = 'purchase_date'); future activation policies (start-on-first-checkin, future-dated) are out of scope for v1.2.
- **Resolver tiebreak** (latest `end_date`, then `created_at DESC`) is REQUIREMENTS-locked (MEM-04).
- **Audit event triplet** (`membership_created`, `membership_cancelled`, `membership_expired`) is Phase 15 LOCKED_AUDIT_EVENTS — typos fail the AST gate.
- **RBAC pairs**: `(CANCEL, MEMBERSHIPS)` and `(DELETE, MEMBERSHIPS)` ∈ OWNER_ONLY (Phase 15); reception+owner can CREATE+VIEW.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project context (read first)
- `.planning/PROJECT.md` — project description, Constraints (РФ/СНГ — Stripe banned), Key Decisions table (incl. inclusive `end_date`, `gym_date` Europe/Moscow STORED, residual fraud risk, all v1.2 entries from Phase 15).
- `.planning/REQUIREMENTS.md` — Phase 17 owns MEM-01..05, MEM-EP-01..04, MEM-AUDIT-01, TESTS-09, TESTS-10. Read MEM-01 verbatim for the column list (no paraphrasing — it's the migration spec).
- `.planning/ROADMAP.md` §"Phase 17: Membership Instances + Resolver (backend)" — phase goal + Success Criteria 1-5 + dependency note (depends on Phase 16). **Phase 16 SC#4 wording must be reconciled per D-07** (planner edits ROADMAP or annotates VERIFICATION).
- `.planning/STATE.md` §"Decisions" — accumulated v1.2 decisions including Phase 15 + 16 contract surface.

### Phase 15 outputs (foundation contract — strict prerequisite)
- `.planning/phases/15-foundations-rbac-audit-taxonomy-helper-hoisting/15-CONTEXT.md` — full Phase 15 decision set; D-01..D-12 lock the audit taxonomy, BusinessService template, BackendSchemaBase, AST commit gate.
- `.planning/phases/15-foundations-rbac-audit-taxonomy-helper-hoisting/15-VERIFICATION.md` — confirms Phase 15 success criteria pass.

### Phase 16 outputs (direct precursor — Phase 17 extends the same module)
- `.planning/phases/16-membership-plans-catalog-backend/16-CONTEXT.md` — D-15 documents that Phase 17 owns the FK `fk_memberships_plan_id_membership_plans` introduction AND the 409 `plan_in_use` translation. Phase 16 D-01..D-17 are the implementation patterns Phase 17 mirrors.
- `.planning/phases/16-membership-plans-catalog-backend/16-VERIFICATION.md` — confirms Phase 16 ships `MembershipPlan` model, repository, service, router, audit events. Resolver wiring + `memberships` table are the gaps.
- `.planning/phases/16-membership-plans-catalog-backend/16-PATTERNS.md` (if present) — file-to-analog mapping reused here.

### Research outputs (v1.2 — global)
- `.planning/research/SUMMARY.md` §"Pitfalls (BLOCKER ranks)" #1 — service-write commit discipline (Phase 17 service.py inherits via the Phase 15 AST gate; module already in scope from Phase 16).
- `.planning/research/PITFALLS.md` — full pitfall catalogue.
- `.planning/research/ARCHITECTURE.md` — `register_user_loader` precedent (Phase 17 mirrors as `register_active_membership_resolver`).
- `.planning/research/STACK.md` — confirms zero new runtime deps for v1.2.

### Backend codebase — direct templates
- `apps/backend/app/modules/clients/models.py` — ORM template; `apps/backend/app/modules/memberships/models.py` (Phase 16 plans) — same module, Phase 17 adds a sibling `Membership` class; both classes coexist in `models.py`.
- `apps/backend/app/modules/memberships/repository.py` (Phase 16) — repository pattern reused; Phase 17 adds `insert_membership`, `get_membership_alive`, `update_membership_status`, `list_memberships`, `find_active_for_client`.
- `apps/backend/app/modules/memberships/service.py` (Phase 16) — service template; Phase 17 adds `create_membership`, `cancel_membership`, `list_memberships`, `get_membership`, `resolve_active_membership_by_client`, `_is_plan_in_use_conflict` helper; AST commit gate already covers this module file.
- `apps/backend/app/modules/memberships/schemas.py` (Phase 16) — DTO template; Phase 17 adds `MembershipCreateRequest`, `MembershipCancelRequest`, `MembershipResponse`, `MembershipListQuery`, `MembershipStatus` StrEnum, `MembershipListSort` StrEnum.
- `apps/backend/app/modules/memberships/router.py` (Phase 16) — router template; Phase 17 adds 4 endpoints under the same `router = APIRouter()` instance, mounted at `/memberships` (existing plans router moves to its own file or stays mounted at `/membership-plans` — planner decides; both currently route off the same APIRouter and may need split).
- `apps/backend/app/modules/clients/service.py` — `_is_phone_conflict` + IntegrityError translation pattern → mirror as `_is_plan_in_use_conflict`.
- `apps/backend/alembic/versions/0004_membership_plans.py` — migration template (composite expression index via `op.execute`); `0002_clients.py` — FK creation pattern.

### Backend codebase — Phase 15 contract surface (consumed, not extended)
- `apps/backend/app/core/permissions.py` — `OWNER_ONLY` includes `(CANCEL, MEMBERSHIPS)` and `(DELETE, MEMBERSHIPS)` (Phase 15). `(CREATE, MEMBERSHIPS)` and `(VIEW, MEMBERSHIPS)` are NOT in OWNER_ONLY → reception+owner. **Read but do NOT modify.**
- `apps/backend/app/core/audit.py` — `LOCKED_AUDIT_EVENTS` includes `("membership_created", "membership")`, `("membership_cancelled", "membership")`, `("membership_expired", "membership")`. Phase 17 emits the first two only; Phase 18 emits the third.
- `apps/backend/app/core/schemas.py` — `BackendSchemaBase` + `ResponseEnvelope[T]` parents.
- `apps/backend/app/core/services.py` — `BusinessService` template (Phase 15).
- `apps/backend/app/core/pagination.py` — `PageQuery` + `PaginatedData[T]`.
- `apps/backend/app/core/exceptions.py` — `ConflictError(AppError, status=409)`. Phase 17 adds `PlanInactiveError`, `PlanInUseError`, `InvalidTransitionError`, `MembershipNotFoundError`.
- `apps/backend/app/core/database.py` — `Base + UUIDPkMixin + TimestampMixin` (no SoftDeleteMixin for `Membership`); `NAMING_CONVENTION` produces deterministic constraint names.
- `apps/backend/app/core/dependencies.py` — `register_user_loader` pattern (Phase 4 D-24); Phase 17 adds the parallel `register_active_membership_resolver` slot below it.

### Backend codebase — wiring touch-points
- `apps/backend/app/api/v1/router.py` — Phase 17 adds `from app.modules.memberships.router import memberships_router; v1.include_router(memberships_router, prefix='/memberships', tags=['memberships'])` (separate from the existing `plans_router` mount).
- `apps/backend/app/main.py:create_app()` — Phase 17 adds `register_active_membership_resolver(resolve_active_membership_by_client)` BEFORE `app.include_router(api)`. Same composition-root carve-out as `register_user_loader`. **Document the second-loader pattern in the docstring.**
- `apps/backend/openapi.json` — regenerated by `scripts/export_openapi.py`. Phase 21 refreshes `schema.d.ts`.
- `apps/backend/.importlinter` — three contracts unchanged. `app.main` remains the only crosser; `app.modules.memberships` consumes only `app.core.*`.

### Frontend codebase (NOT touched in Phase 17; mirrored in Phase 22)
- `apps/admin-web/src/shared/session/registry.ts` — already declares `Resource.MEMBERSHIPS` (Phase 15).
- `apps/admin-web/src/shared/session/can.ts` — already declares the 2 owner-only `MEMBERSHIPS` pairs (CANCEL, DELETE).
- `packages/api-client/` — Phase 21 regenerates `schema.d.ts`; Phase 17 does not touch.

### Tests (Phase 17 adds; Phase 15 enforces)
- `apps/backend/tests/integration/test_rbac_parity.py` — TEST-06 already covers MEMBERSHIPS pairs (Phase 15). Phase 17 verifies it stays green.
- `apps/backend/tests/unit/test_audit_taxonomy.py` — Phase 15's static AST walker validates the 2 `membership_*` event names against `LOCKED_AUDIT_EVENTS` (TESTS-09 closure). Phase 17 callsites use literal strings.
- `apps/backend/tests/unit/test_service_commit_gate.py` — Phase 15 INFRA-13's AST commit-gate. `app.modules.memberships.service` is already in scope from Phase 16; the new sale/cancel paths inherit the enforcement.
- `apps/backend/tests/integration/test_route_introspection.py` — every route declares `Depends(require_permission(...))`. Phase 17's 4 new routes pass.
- `apps/backend/tests/integration/clients/conftest.py` — fixture pattern (auth headers, owner/reception bearer fixtures, db_session SAVEPOINT mode). Phase 17's `tests/integration/memberships/conftest.py` extends Phase 16's existing one with a `make_plan(...)` factory that returns an alive plan id (already exists post-16) and a new `make_membership(...)` factory.

### Conventions (read for style consistency)
- `.planning/codebase/CONVENTIONS.md`, `STRUCTURE.md`, `TESTING.md`.
- `apps/backend/docs/conventions.md` — backend-specific (camelCase wire / snake_case Python; ResponseEnvelope; pagination contract).
- `apps/backend/docs/architecture.md` — modular monolith doc.
- `apps/backend/docs/adr/0001-modular-monolith.md` — ADR for the import-linter contracts.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **Module already exists** (`apps/backend/app/modules/memberships/`) — Phase 16 shipped `MembershipPlan` (model + repo + service + schemas + router). Phase 17 EXTENDS this module rather than creating a new one. The split is in-file: `models.py` adds class `Membership`; `service.py` adds `create_membership` / `cancel_membership` / `list_memberships` / `get_membership` / `resolve_active_membership_by_client` alongside the plan functions; `repository.py` adds membership CRUD alongside plan CRUD; `schemas.py` adds membership DTOs alongside plan DTOs; `router.py` may stay as a single file with both endpoint groups OR split into `plans_router.py` + `memberships_router.py` (CD-02 — planner picks).
- **`register_user_loader` precedent** (`apps/backend/app/core/dependencies.py:54-61` + `app/main.py:88`) — the EXACT shape for `register_active_membership_resolver`: module-level `_active_membership_resolver: ActiveMembershipResolver | None = None`; `register_active_membership_resolver(resolver)` setter (idempotent — re-register replaces, useful for tests); `resolve_active_membership(session, client_id)` consumer that raises a defensive error if the slot is unset (or returns None? — defensive raise matches user-loader pattern, but for membership the sane fallback is "no active membership" → return None. Decision: return None on unset slot; the visits service can't distinguish "no resolver registered" from "no active membership" and that's fine — production code always registers in `create_app()`, tests can register a stub).
- **`PlanNameExistsError` IntegrityError translation pattern** (`apps/backend/app/modules/memberships/service.py:58-68` Phase 16) — direct template for `_is_plan_in_use_conflict` (constraint name swap to `fk_memberships_plan_id_membership_plans`). Same control flow: catch IntegrityError → check constraint name → rollback → raise translated error.
- **PATCH explicit-null guard** (`apps/backend/app/modules/memberships/schemas.py:74-85` Phase 16) — `MembershipCancelRequest` (which is a "small PATCH-like" body) ports the same `model_validator(mode='before')` rejecting `{reason: null}`. Mirror verbatim.
- **Test fixture chain** (`apps/backend/tests/integration/memberships/conftest.py` from Phase 16) — `make_plan` factory exists. Phase 17's conftest extends with `make_membership(client_id=, plan_id=, status='active')` factory.
- **`PageQuery` + `PaginatedData[T]`** — already used by clients + plans. Phase 17 list endpoint inherits.
- **`Action.CANCEL` × `Resource.MEMBERSHIPS`** — already in Phase 15 OWNER_ONLY; `require_permission(Action.CANCEL, Resource.MEMBERSHIPS)` dispatches verbatim.
- **`audit.emit` co-transactional contract** (`apps/backend/app/core/audit.py`) — same session, no commit/flush inside emit; caller commits after. Phase 17's 2 emit callsites + commits follow this.

### Established Patterns

- **Module layout: `router/service/repository/schemas/models` (free functions, no classes)** — locked Phase 15 `core/services.py` docstring; Phase 17 extends.
- **Service write paths commit explicitly** — AST gate enforces; `app.modules.memberships.service` already in scope from Phase 16.
- **`audit.emit` uses literal strings only** — Phase 15 D-11 step 3; AST walker validates.
- **PATCH explicit-null reject + `model_dump(exclude_unset=True)`** — clients D-01 / Phase 16 D-05. The cancel body uses the same pattern (even though it's POST, not PATCH — defensive consistency).
- **Domain errors aggregate in `core/exceptions.py`** — Phase 17 adds `PlanInactiveError`, `PlanInUseError`, `InvalidTransitionError`, `MembershipNotFoundError`.
- **OWNER_ONLY pair lookup is the gate; the service never re-checks RBAC** — clients + plans precedent.
- **Pagination envelope `{items, total, page, pageSize}` ALWAYS via `ResponseEnvelope[PaginatedData[T]]`** — locked v1.1.
- **`from __future__ import annotations` in repository modules** — required by Pydantic generic-resolution edge case.
- **Sort enum lives in module schemas** — Phase 17 ships `MembershipListSort` in `memberships/schemas.py`.
- **IntegrityError → domain error translation in service.py** — clients D-11 / Phase 16 D-02. Phase 17 adds `_is_plan_in_use_conflict` for the FK case (NOT a UNIQUE conflict — different SA error path but same translation shape).

### Integration Points

- **`app/api/v1/router.py`** — Phase 17 adds `include_router(memberships_router, prefix='/memberships', tags=['memberships'])`. Mount under the same `/api/v1` umbrella as `/membership-plans`.
- **`app/main.py:create_app()`** — second composition-root call after `register_user_loader(load_user_by_id)`: add `register_active_membership_resolver(resolve_active_membership_by_client)`. Idempotent re-registration is intentional (tests inject stubs via `create_app()`).
- **`apps/backend/openapi.json`** — regenerated by `scripts/export_openapi.py`. CI gate `git diff --exit-code` requires committing the regenerated spec.
- **Alembic chain** — current head after Phase 16: `0004_membership_plans`. New revision `0005_memberships` has `down_revision = "0004_membership_plans"`.
- **`tests/unit/test_service_commit_gate.py`** — Phase 17 sale/cancel paths inherit the gate (module already in scope from Phase 16).
- **`tests/integration/test_rbac_parity.py`** — Phase 15 TESTS-08 covers the 2 `(*, MEMBERSHIPS)` OWNER_ONLY pairs. Phase 17 verifies green after `/api/v1/memberships` mounts.
- **`tests/integration/test_route_introspection.py`** — Phase 6 introspection guard. Phase 17's 4 new routes must declare `Depends(require_permission(...))`.

</code_context>

<specifics>
## Specific Ideas

- **Migration revision chain anchor**: `down_revision = "0004_membership_plans"`. Filename = `0005_memberships.py`. Confirm via `alembic heads` against the dev DB before authoring.
- **Constraint name pinning**: `fk_memberships_plan_id_membership_plans` is the canonical FK name (referenced by `_is_plan_in_use_conflict`). NAMING_CONVENTION makes it deterministic but document in migration comment as a defence against rename.
- **Composite index DESC ordering** — `(client_id, status, end_date DESC)` may need raw `op.execute("CREATE INDEX ix_memberships_client_id_status_end_date ON memberships (client_id, status, end_date DESC)")` if SQLAlchemy autogenerate can't represent the DESC. Document in `alembic/env.py:_include_object` if the index becomes autogenerate-noisy (Phase 8 pattern).
- **Sale → resolver wired test**: integration test creates plan → POST /memberships → GET active via direct call to `resolve_active_membership(session, client_id)` → asserts the new row is returned. Validates the composition-root registration end-to-end.
- **Stacking test**: sell membership #1 (90 days) → wait/clock-shift → sell membership #2 (180 days, longer end_date) → resolver returns #2 (latest end_date). Then cancel #2 → resolver returns #1 (next-latest active end_date). Then cancel #1 → resolver returns None.
- **plan_in_use test**: create plan → sell membership → DELETE plan → 409 `plan_in_use` (FK rejects). Cancel the membership → DELETE plan → still 409 (cancelled rows ALSO block per D-06). Hard-delete the membership row in raw SQL fixture → DELETE plan → 204 success.
- **state-machine matrix test (TESTS-10)**: parametrize over the 9 (from, action) cells; assert allowed cells succeed and disallowed cells raise `InvalidTransitionError(409, code='invalid_transition')` with the right `from_status/to_status` payload.
- **`paid_at` ISO timestamp test**: POST `/memberships` with explicit `"paidAt": "2026-05-01T10:00:00Z"` → row has matching `paid_at`. POST without `paidAt` → row has `paid_at IS NULL`.
- **Audit no-reason test**: POST `/cancel` with no body → `audit_log` row has no `reason` key in payload (NOT `reason: null`). POST with `{"reason": "data error"}` → payload has `reason: "data error"`.
- **Composition-root second-loader docstring**: when adding `register_active_membership_resolver` to `app/main.py`, the docstring should say "second composition-root carve-out (after register_user_loader, Phase 5 D-15)" — keeps the architectural exception traceable.

</specifics>

<deferred>
## Deferred Ideas

- **Membership freeze (заморозка)** — out of scope for v1.2 (PROJECT.md). Would need a `frozen_until` column + ARQ job to thaw + audit events. Revisit v1.3+ based on operator feedback.
- **Visit-count plans (10/20/50 visits, no time limit)** — out of scope for v1.2. Would need plan_kind enum + visits_remaining column on `memberships`. Revisit v1.3+.
- **Hybrid plans (N visits within M months)** — out of scope for v1.2. v1.3+.
- **Expiring-soon Telegram notifications (D-3 in PROJECT.md, e.g. 3 days before end_date)** — Phase 22 differentiator D-3 ships a "истёк сегодня" badge in the client list (read-side); proactive Telegram DM is v1.3+.
- **`POST /memberships/{id}/expire` manual-expiry endpoint** — Phase 18's ARQ does this automatically. No manual override needed in v1.2 (owner can `cancel` instead with a "data error" reason).
- **Future-dated `start_date` (sell today, starts next month)** — `activation_policy` is locked to `'purchase_date'` (CHECK = 'purchase_date') in MEM-01. v1.3+ may add `'first_checkin'` or `'future_date'` policies.
- **`?expand=plan` on GET /memberships** — to embed the plan's CURRENT name/price next to the snapshot. Phase 22 may surface this if owner UX needs it; not pre-emptively (CD-05).
- **Multi-value `?status=active,expired` filter** — single-value enum is enough for v1.2 (D-09). Revisit if Phase 22 surfaces a UI that needs it.
- **`?from`/`?to` date-range filter on memberships list** — visits has it (Phase 19), memberships does not. v1.3+ if ops reports need it.
- **Dedicated `idx_memberships_plan_id` btree** — only added if a "memberships sold per plan" report needs it (D-21).
- **Refund flow** — out of scope for v1.2 (no billing integration). v1.3+ alongside ЮKassa.
- **Membership renewal endpoint (`POST /memberships/{id}/renew` with carry-over discount)** — v1.3+. v1.2 stacking (D-01) covers the operational case via two separate sales.
- **Owner UX warning on multiple active memberships per client** — D-17 leaves this for Phase 22 to compute client-side from the list endpoint.

</deferred>

---

*Phase: 17-Membership Instances + Resolver (backend)*
*Context gathered: 2026-05-07*
