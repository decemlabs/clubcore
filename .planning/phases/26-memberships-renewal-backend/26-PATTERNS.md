# Phase 26: Memberships — Renewal (backend) - Pattern Map

**Mapped:** 2026-05-09
**Files analyzed:** 8 modified files + 8 new test files + 1 new migration
**Analogs found:** 17 / 17 (100% — every Phase 26 artifact has a direct in-tree analog, mostly Phase 25/Phase 17 siblings)
**Mode:** `--auto` (no RESEARCH.md per project config; file list extracted from CONTEXT.md `<canonical_refs>` + `<decisions>`)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `apps/backend/alembic/versions/0009_renewal.py` (NEW) | migration | DDL only (column + self-FK + index) | `0008_freeze.py` (revision header + ALTER + create_table); `0005_memberships.py:34-100` (FK declaration shape) | exact (composite — single-column subset of `0008`) |
| `apps/backend/app/modules/memberships/models.py` (extend) | ORM model | declarative + `__table_args__` extension | `Membership.plan_id` mapped column lines 111-120 (FK literal-ref'd, ON DELETE RESTRICT pattern) | exact (sibling FK column on same class) |
| `apps/backend/app/modules/memberships/repository.py` (extend) — `get_plan_for_renewal` | repository fn (read) | SELECT, ignores soft-delete | `get_alive` lines 51-58 (with `deleted_at IS NULL` predicate REMOVED + tuple return) | role-match (novel return shape) |
| `apps/backend/app/modules/memberships/repository.py` (extend) — `insert_renewal_membership` | repository fn (mutation, no commit) | INSERT, caller-owns-flush | `insert_membership` lines 167-195 + `insert_freeze_period` lines 406-426 | exact |
| `apps/backend/app/modules/memberships/repository.py` (modify) — `find_active_for_client` ORDER BY | repository fn (read) | SELECT WHERE LIMIT 1 | itself (lines 318-354) — change ORDER BY clause from `end_date DESC` → `start_date ASC` | self-modification |
| `apps/backend/app/modules/memberships/service.py` (extend) — `renew_membership` | service fn (mutation, owns commit) | request-response | `freeze_membership` lines 608-688 (load → guard → mutate → flush → emit → refresh → commit) | exact |
| `apps/backend/app/modules/memberships/router.py` (extend) — `POST /{id}/renew` | router endpoint (mutation) | request-response | `freeze_membership` route lines 324-355 + `create_membership` lines 263-285 (201 status) | exact (composite) |
| `apps/backend/app/modules/memberships/schemas.py` (extend) — `MembershipResponse.previous_membership_id` | schema (response) | wire format | itself lines 227-254 — append one optional UUID field | self-extension |
| `apps/backend/app/modules/memberships/constants.py` (extend) — `RENEWAL_STRATEGY_*` literals | const module | declarative | itself lines 1-30 (extends with `__all__` update) | self-extension |
| `apps/backend/app/core/exceptions.py` (extend) — `CannotRenewCancelledError` + `PlanArchivedError` | exception class | error type | `PlanInactiveError` lines 133-142 + `AlreadyFrozenError` lines 191-201 | exact |
| `apps/backend/app/core/audit.py` (modify) — docstring lines 61-62 | docs | inline | self-doc, mirror Phase 25 D-25-27 closing pattern | self-modification |
| `apps/backend/tests/integration/memberships/test_renewal_active.py` (NEW) | integration test | HTTP roundtrip + audit | `tests/integration/memberships/test_freeze_cycle.py` + `test_memberships_audit.py` | role-match |
| `apps/backend/tests/integration/memberships/test_renewal_price_change.py` (NEW) | integration test | snapshot semantics | `test_memberships_audit.py` (audit payload assertions) + `test_plans_crud.py` (PATCH plan price flow) | role-match |
| `apps/backend/tests/integration/memberships/test_renewal_archived_plan.py` (NEW) | integration test | HTTP error path | `test_freeze_endpoints.py` (409 invalid_transition shape) + `test_plan_in_use.py` | role-match |
| `apps/backend/tests/integration/memberships/test_renewal_expired_source.py` (NEW) | integration test | clock injection + start_date strategy | `test_freeze_cycle.py` + `tests/integration/memberships/test_expire_due_memberships_service.py` (clock injection precedent) | role-match |
| `apps/backend/tests/integration/memberships/test_renewal_endpoint.py` (NEW) | integration test | RBAC + CSRF + response shape | `test_freeze_endpoints.py` (RBAC matrix + CSRF + response) | exact (mirror) |
| `apps/backend/tests/integration/memberships/test_renewal_resolver_tiebreak.py` (NEW) | integration test | resolver behaviour | `test_resolver.py` + `test_freeze_resolver.py` (resolver returns expectations + clock injection) | exact (mirror) |
| `apps/backend/tests/integration/memberships/test_renewal_from_frozen.py` (NEW) | integration test | cross-flow happy path | `test_cancel_during_freeze.py` (frozen-source flow) | role-match |
| `apps/backend/tests/unit/memberships/test_renewal_constants.py` (NEW) | unit test | const inspection | `tests/unit/memberships/test_state_machine.py:109-136` (`MEMBERSHIP_STATUS_TRANSITIONS` constant assertions) | exact |

---

## Pattern Assignments

### `apps/backend/alembic/versions/0009_renewal.py` (migration, DDL only)

**Analog:** `apps/backend/alembic/versions/0008_freeze.py` (Phase 25 — full structure) + `apps/backend/alembic/versions/0005_memberships.py` (FK declaration shape).

**Revision-chain header pattern** (mirror `0008_freeze.py:32-35`):
```python
revision: str = "0009_renewal"
down_revision: str | None = "0008_freeze"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```

**Module docstring pattern** (mirror `0008_freeze.py:1-22`):
- Phase tag + REQ-IDs (e.g. "Phase 26 / MEM-REN-01").
- "Notes" block calls out:
  - (a) self-FK is Postgres-native (no cycle issues); ON DELETE SET NULL preserves chain integrity if source row is hard-deleted (D-26-05).
  - (b) Non-partial index on `previous_membership_id` (D-26-02 step 3); partial `WHERE previous_membership_id IS NOT NULL` is a deferred optimization (CONTEXT.md Risks/Watchpoints #2).
  - (c) Downgrade is **lossless for data** (renewal rows survive) but loses chain attribution (D-26-03).
  - (d) Default chain context: `0007_status_taxonomy` → `0008_freeze` → `0009_renewal` → `0010_notifications` (Phase 27).

**Upgrade pattern** (D-26-02 — 3 ops in order):
```python
def upgrade() -> None:
    # 1) Add nullable self-FK column. Existing rows have no source — NULL is correct.
    op.add_column(
        "memberships",
        sa.Column(
            "previous_membership_id",
            sa.UUID(),
            nullable=True,
        ),
    )

    # 2) Self-FK to memberships.id. ON DELETE SET NULL — orphans the renewal but
    #    keeps it queryable (audit trail integrity vs cascade-delete chain).
    op.create_foreign_key(
        op.f("fk_memberships_previous_membership_id_memberships"),
        "memberships",
        "memberships",
        ["previous_membership_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 3) Index for forensic lookup `WHERE previous_membership_id = ?`. Non-partial
    #    per D-26-02 step 3 / CONTEXT.md Risks/Watchpoints #2; partial deferred.
    op.create_index(
        op.f("ix_memberships_previous_membership_id"),
        "memberships",
        ["previous_membership_id"],
    )
```

**Downgrade pattern** (D-26-03 — reverse order):
```python
def downgrade() -> None:
    """Reverse upgrade in reverse order — preserves row data, drops chain attribution."""
    op.drop_index(
        op.f("ix_memberships_previous_membership_id"),
        table_name="memberships",
    )
    op.drop_constraint(
        op.f("fk_memberships_previous_membership_id_memberships"),
        "memberships",
        type_="foreignkey",
    )
    op.drop_column("memberships", "previous_membership_id")
```

**Invariants:**
- Use `op.f(...)` so NAMING_CONVENTION (`apps/backend/app/core/database.py:28-34`) auto-prefixes; matches Phase 25 `0008_freeze.py:99-117` FK shape.
- `sa.UUID()` (NOT `postgresql.UUID(as_uuid=True)`) — matches `0008_freeze.py:78,82,85,86` declarative use.
- The column is **NOT** referenced by literal name in service code, so NO addition to `apps/backend/alembic/env.py:_include_object` is needed (only literal-ref'd constraint names go there — see Phase 25 D-25-22 / `env.py:60-69`).
- Migration is **schema-only** — no backfill needed (existing rows correctly have `previous_membership_id = NULL`).

---

### `apps/backend/app/modules/memberships/models.py` extension (`Membership.previous_membership_id`)

**Analog:** `Membership.plan_id` mapped column at `models.py:111-120` (FK with ON DELETE RESTRICT, named via literal); `Membership.cancelled_at` lines 132-135 (nullable column with timezone-aware mapping).

**Self-FK column pattern** (mirror `Membership.plan_id` lines 111-120 — D-26-04 / D-26-05):
```python
previous_membership_id: Mapped[UUIDType | None] = mapped_column(
    PgUUID(as_uuid=True),
    ForeignKey(
        "memberships.id",
        ondelete="SET NULL",
        name="fk_memberships_previous_membership_id_memberships",
    ),
    nullable=True,
)
```

**Placement:** insert after `Membership.activation_policy` (line 142-146) but **before** `__table_args__` (line 148). Matches alphabetical-adjacency-to-existing-FK convention.

**`__table_args__` extension** (mirror `Membership.__table_args__` lines 148-165 — append one Index entry):
```python
__table_args__ = (
    CheckConstraint(
        "status IN ('active', 'expired', 'cancelled', 'frozen')",
        name="status",
    ),
    CheckConstraint(
        "activation_policy = 'purchase_date'",
        name="activation_policy",
    ),
    Index(
        "ix_memberships_client_id_status_end_date",
        "client_id",
        "status",
        text("end_date DESC"),
    ),
    # Phase 26 D-26-02 — forensic lookup index.
    Index(
        "ix_memberships_previous_membership_id",
        "previous_membership_id",
    ),
)
```

**Class docstring update** — extend the existing docstring (lines 89-98) with a Phase 26 note:
- "Phase 26 MEM-REN-01: `previous_membership_id` self-FK — set ONCE at INSERT by `service.renew_membership`; immutable post-creation (D-26-04). ON DELETE SET NULL preserves renewal-row data when source is hard-deleted (D-26-05). Chain depth is implicitly unbounded (D-26-06)."

**Invariants:**
- `Mapped[UUIDType | None]` (NOT `Mapped[UUIDType]`) — column is nullable.
- Self-FK target is `"memberships.id"` (same table); SQLAlchemy + Postgres support this without special handling (compare `Membership.plan_id` lines 111-120 — same shape, different table).
- Constraint name `fk_memberships_previous_membership_id_memberships` is NOT literal-ref'd by service code (no IntegrityError discriminator needed — there's no UNIQUE conflict to translate; FK violation on bad source.id surfaces only via DBA-direct surgery), so it does NOT go into `alembic/env.py:_include_object`.

---

### `apps/backend/app/modules/memberships/repository.py` extensions

**Analogs:**
- `get_plan_for_renewal` — `get_alive` lines 51-58 (similar SELECT-by-id shape; differs in DROPPING `deleted_at IS NULL` predicate AND returning a tuple).
- `insert_renewal_membership` — `insert_membership` lines 167-195 + `insert_freeze_period` lines 406-426 (both demonstrate keyword-only + caller-owns-flush + `session.add` pattern).
- `find_active_for_client` ORDER BY change — itself lines 318-354.

**`get_plan_for_renewal` helper** (D-26-08 — append after existing `get_alive` block, before the `# Phase 17` divider line 162-164):
```python
async def get_plan_for_renewal(
    session: AsyncSession,
    plan_id: UUID,
) -> tuple[MembershipPlan | None, bool]:
    """Read plan ignoring soft-delete; return (plan, is_archived) for renewal classification (Phase 26 D-26-08).

    Phase 26 needs to discriminate "plan never existed" (404 plan_not_found)
    from "plan exists but archived" (409 plan_archived). `get_alive` collapses
    both to None, so renewal uses this helper instead. NO other caller should
    use this — bypassing soft-delete in any other write path is a bug.
    """
    stmt: Select[tuple[MembershipPlan]] = select(MembershipPlan).where(
        MembershipPlan.id == plan_id,
    )
    plan: MembershipPlan | None = await session.scalar(stmt)
    if plan is None:
        return (None, False)
    return (plan, plan.deleted_at is not None)
```

**`insert_renewal_membership` helper** (D-26-16 — append at end of file, after the Phase 25 freeze block ending at line 518):
```python
# ===========================================================================
# Phase 26 — Renewal helper (D-26-16)
# ===========================================================================


async def insert_renewal_membership(
    session: AsyncSession,
    *,
    source: Membership,
    plan: MembershipPlan,
    start_date: date,
    end_date: date,
) -> Membership:
    """Insert a follow-up membership chained to ``source`` (Phase 26 D-26-16).

    Snapshots from CURRENT plan (price/duration/freeze_limit/name); copies
    client_id from source; previous_membership_id = source.id (immutable; D-26-04).
    Status always starts 'active'; resolver tiebreak (D-26-17) handles overlap
    between still-running source and newly-created renewal.

    Caller (service) owns flush + commit (Phase 16 D-14 / SVC001 gate).
    NO snapshot from source's snapshots — uses the plan's CURRENT values per
    PROJECT.md "Snapshot pricing на renewal — берём текущую цену плана".
    """
    new_membership = Membership(
        client_id=source.client_id,
        plan_id=plan.id,
        plan_name_snapshot=plan.name,
        duration_days_snapshot=plan.duration_days,
        price_kopecks_snapshot=plan.price_kopecks,
        freeze_days_limit_snapshot=plan.freeze_days_limit,
        start_date=start_date,
        end_date=end_date,
        status="active",
        previous_membership_id=source.id,
        # activation_policy intentionally omitted — server_default 'purchase_date'.
    )
    session.add(new_membership)
    return new_membership
```

**`find_active_for_client` ORDER BY change** (D-26-17 — modify existing function lines 318-354):

```python
# Lines 343-352 — replace:
stmt = (
    select(Membership)
    .where(
        Membership.client_id == client_id,
        Membership.status == "active",
        Membership.end_date >= today,
    )
    .order_by(Membership.start_date.asc(), Membership.created_at.desc())  # ← was end_date.desc()
    .limit(1)
)
```

**Docstring update** (D-26-19 — replace `find_active_for_client` docstring lines 324-342):
```python
"""Return the canonical active membership for `client_id`, or None (MEM-04, DEBT-01, Phase 26 D-26-17).

Tiebreak (Phase 26 D-26-17): ORDER BY start_date ASC, created_at DESC LIMIT 1.
Inverts Phase 17 D-17 `end_date DESC` ordering. Rationale: when client has
both a still-running source membership AND a renewal sold ahead, the running
one starts earlier and wins — check-in keeps using it until source.end_date
passes. After that, ARQ `expire_memberships` (06:05 cron) flips source
status='expired' so it no longer matches the `status='active'` filter and
the renewal naturally takes over.

The composite index `ix_memberships_client_id_status_end_date` covers the
WHERE clause; the new ORDER BY `start_date ASC` is NOT in the index, so the
executor sorts the post-filter set in memory. Expected per-client cardinality
≤ 2 active rows → O(1). No new index added (cost > benefit at pet-project
scale).

Date filter (DEBT-01, Phase 24): `end_date >= today` defence-in-depth backstop
for missed ARQ ticks. `today` is required keyword-only — callers MUST resolve
their Europe/Moscow `date` (the service-layer wrapper
`service.resolve_active_membership_by_client` does this).

Manual-stacking compatibility (Phase 17 D-01): two memberships sold raw
without renewal linkage — older `start_date` runs first; if equal,
`created_at DESC` tiebreaks to the LATER-created row (silent, no warning,
no audit event — matches Phase 17 D-17 silence contract).

If you change the resolver tiebreak again: update integration test
test_renewal_resolver_tiebreak.py + cross-check Phase 27 expiring-cron query
selects (NTF-02 reads memberships but doesn't depend on tiebreak — filters
all matching rows, not LIMIT 1).
"""
```

**Invariants:**
- The Phase 17 callsite `service.create_membership` still works unchanged — the new ORDER BY only matters when ≥2 active rows exist for the same client; single-row scenarios are tiebreak-irrelevant.
- `update_membership_status` (lines 295-315) is **NOT** called by `renew_membership` — renewal does not transition source row (D-26-24).
- `get_alive` (lines 51-58) is **NOT** modified — bypassing soft-delete is renewal-specific concern (D-26-08 specifics line 411).
- Imports may need extending if `tuple` typing requires it; check with `from __future__ import annotations` already present at line 25.

---

### `apps/backend/app/modules/memberships/service.py` extensions

**Analog:** `freeze_membership` lines 608-688 is the canonical Phase 25 mutation flow + `create_membership` lines 449-514 demonstrates the snapshot/date-compute pattern + `cancel_membership` lines 517-600 shows the load-then-guard ordering.

**Module docstring update** — extend "Audit emit ordering" section (lines 17-39) with Phase 26:
```
  - renew_membership (Phase 26 D-26-14): load source → status guard
    (cancelled → 409 cannot_renew_cancelled; expired/active/frozen ok) →
    load plan via get_plan_for_renewal (None → 404 plan_not_found;
    archived → 409 plan_archived) → compute dates by source status
    (active/frozen → source.end_date + 1; expired → today MSK) →
    insert via insert_renewal_membership (snapshots from CURRENT plan;
    previous_membership_id = source.id) → flush → emit `membership_renewed`
    (LITERAL; payload includes start_date_strategy literal; current_price_kopecks
    captures plan price at renewal time) → refresh(created_at, updated_at) →
    commit. Source row is NOT mutated — renewal is INSERT, not transition
    (D-26-24).
```

**Imports update** (lines 65-78) — add `CannotRenewCancelledError` + `PlanArchivedError`:
```python
from app.core.exceptions import (
    AlreadyFrozenError,
    CannotRenewCancelledError,    # NEW (Phase 26 D-26-09)
    FreezeLimitExceededError,
    InvalidTransitionError,
    MembershipNotFoundError,
    PlanArchivedError,            # NEW (Phase 26 D-26-09)
    PlanInactiveError,
    PlanInUseError,
    PlanNameExistsError,
    PlanNotFoundError,
)
```

Add constants imports (lines 77-78 area):
```python
from app.modules.memberships.constants import (
    MEMBERSHIP_STATUS_TRANSITIONS,
    RENEWAL_STRATEGY_FROM_SOURCE_END_DATE,        # NEW (Phase 26 D-26-13)
    RENEWAL_STRATEGY_FROM_TODAY_EXPIRED_SOURCE,   # NEW (Phase 26 D-26-13)
)
```

**`renew_membership` mutation flow** (mirror `freeze_membership` lines 608-688 step-by-step — D-26-14):

Append after `unfreeze_membership` (line 758) — before the `list_memberships` block:

```python
# ===========================================================================
# Phase 26 — Renewal service path (MEM-REN-02, D-26-14)
# ===========================================================================


async def renew_membership(
    session: AsyncSession,
    actor: CurrentUser,
    source_membership_id: UUID,
) -> MembershipResponse:
    """Create a follow-up membership chained to source (MEM-REN-02 / Phase 26 D-26-14).

    Order (mirrors freeze_membership: D-15 invariant — guard BEFORE mutation):
      1. Load source — 404 `membership_not_found` if missing.
      2. Source-status guard:
         - 'cancelled' → 409 `cannot_renew_cancelled` (terminal/intentional revocation;
           renewal would mask cancellation intent — D-26-07).
         - {'active','frozen','expired'} → ok.
         - other (defence-in-depth, currently impossible per CHECK constraint) →
           409 `invalid_transition`.
         NO call to `_assert_can_transition` — renewal is NOT a status transition
         on source row; source remains untouched (D-26-24).
      3. Load plan via repository.get_plan_for_renewal:
         - (None, _) → 404 `plan_not_found` (defence-in-depth; FK ON DELETE
           RESTRICT makes this practically impossible).
         - (_, True) → 409 `plan_archived` (owner soft-deleted the plan;
           operator must sell a new membership instead — D-26-08).
         - (plan, False) → proceed. NOTE: plan.active=False is ALLOWED for
           renewal per D-26-08 — `active=False` only pauses NEW catalogue sales;
           existing memberships continue lifecycle including renewal. Owner
           archives the plan to block renewals.
      4. Compute dates (D-26-10..D-26-12):
         - source.status in ('active','frozen') → start_date = source.end_date + 1d;
           strategy = RENEWAL_STRATEGY_FROM_SOURCE_END_DATE.
         - source.status == 'expired' → start_date = today (Europe/Moscow);
           strategy = RENEWAL_STRATEGY_FROM_TODAY_EXPIRED_SOURCE.
         - end_date = start_date + (plan.duration_days - 1) — INCLUSIVE
           (mirrors create_membership line 482 + PROJECT.md Key Decisions).
      5. INSERT via repository.insert_renewal_membership (snapshots from CURRENT
         plan; previous_membership_id = source.id).
      6. Flush — surfaces self-FK errors (e.g. concurrent source delete;
         practically impossible).
      7. audit.emit('membership_renewed', ...) — payload per D-26-15;
         resource_id = NEW membership.id (forensic queries answer "what was
         the renewal record"); source_membership_id back-pointer in payload;
         current_price_kopecks captures plan price at renewal time (NOT
         source.price_kopecks_snapshot) per PROJECT.md "snapshot pricing
         берём ТЕКУЩУЮ цену плана".
      8. Refresh created_at + updated_at on the new row.
      9. Commit (SVC001 gate enforces).
     10. Return response via _build_membership_response — populates the 4
         freeze projection fields (freezeDaysUsed=0, currentFreezePeriod=None,
         freezeDaysRemaining=snapshot_limit) + previousMembershipId field.
    """
    # 1: load source
    source = await repository.get_membership(session, source_membership_id)
    if source is None:
        raise MembershipNotFoundError("membership_not_found")

    # 2: status guard
    if source.status == "cancelled":
        raise CannotRenewCancelledError("cannot_renew_cancelled")
    if source.status not in {"active", "frozen", "expired"}:
        # Defence-in-depth — keeps the source-acceptance set explicit.
        # Currently unreachable: CHECK ck_memberships_status admits exactly the
        # 4 known statuses; this branch fires only on DBA-direct surgery or a
        # future state addition (covered by test_renewal_constants).
        raise InvalidTransitionError(
            "invalid_renewal_source",
            fields={"from_status": source.status, "to_status": "renew"},
        )

    # 3: load plan (renewal-specific — bypasses soft-delete to discriminate)
    plan, is_archived = await repository.get_plan_for_renewal(session, source.plan_id)
    if plan is None:
        raise PlanNotFoundError("plan_not_found")
    if is_archived:
        raise PlanArchivedError("plan_archived")

    # 4: compute dates (D-26-10..D-26-12)
    if source.status == "expired":
        start_date = datetime.now(ZoneInfo("Europe/Moscow")).date()
        strategy = RENEWAL_STRATEGY_FROM_TODAY_EXPIRED_SOURCE
    else:
        # active or frozen — start the day after source.end_date.
        start_date = source.end_date + timedelta(days=1)
        strategy = RENEWAL_STRATEGY_FROM_SOURCE_END_DATE
    end_date = start_date + timedelta(days=plan.duration_days - 1)

    # 5 + 6: insert + flush
    new_membership = await repository.insert_renewal_membership(
        session,
        source=source,
        plan=plan,
        start_date=start_date,
        end_date=end_date,
    )
    await session.flush()

    # 7: audit emit BEFORE commit (Phase 16 D-14 co-transactional)
    await audit.emit(
        session,
        "membership_renewed",  # LITERAL — Phase 15 INFRA-11 AST gate
        actor_user_id=actor.id,
        resource_type="membership",  # LITERAL
        resource_id=new_membership.id,           # NEW row's id (forensic anchor)
        client_id=str(new_membership.client_id),  # str-cast for JSONB
        source_membership_id=str(source.id),
        source_plan_id=str(source.plan_id),
        current_price_kopecks=plan.price_kopecks,  # int from CURRENT plan
        start_date_strategy=strategy,             # one of D-26-13 constants
    )

    # 8: refresh server-side timestamps for response
    await session.refresh(
        new_membership, attribute_names=["created_at", "updated_at"]
    )

    # 9: commit (SVC001 gate enforces)
    await session.commit()

    # 10: project response (freeze fields default-zero on new row;
    # previous_membership_id surfaces via D-26-21 schema field).
    return await _build_membership_response(session, new_membership)
```

**Invariants:**
- Public function — MUST end in `await session.commit()` (SVC001 gate at `tests/unit/test_service_commit_gate.py:167-211`; `memberships/service.py` is in `_INSPECTED_SERVICES`). NO `# noqa: SVC001` opt-out is acceptable.
- All `audit.emit()` calls — `event` and `resource_type` MUST be `ast.Constant(str)`. `("membership_renewed", "membership")` already in `LOCKED_AUDIT_EVENTS` (`audit.py:142`, Phase 24 D-24-18 pre-registration).
- UUIDs in payload — `str()`-cast (`client_id`, `source_membership_id`, `source_plan_id`); `resource_id` stays UUID-typed (`AuditLog.resource_id` column is UUID, not JSONB).
- `_build_membership_response` is reused unchanged (D-26-27, D-26-28); helper handles the 4 freeze fields and (after D-26-21) the new `previous_membership_id` field.
- `_assert_can_transition` is NOT called — renewal does NOT transition source (D-26-24); only INSERT happens.

---

### `apps/backend/app/modules/memberships/router.py` extension (`POST /{membership_id}/renew`)

**Analog:** `freeze_membership` route lines 324-355 (empty body + CSRF + CREATE permission) + `create_membership` lines 263-285 (201 Created + envelope).

**Module docstring update** (lines 16-18 area) — extend Phase 25 endpoint surface block:
```
Phase 26 endpoint surface (1 new route on `memberships_router`):
  - POST   /api/v1/memberships/{id}/renew          — renew, 201 (MEM-REN-EP-01)
```

**Endpoint signature pattern** (D-26-20 + D-26-31 — append AFTER existing `unfreeze_membership` at line 358-383):
```python
@memberships_router.post(
    "/{membership_id}/renew",
    response_model=ResponseEnvelope[MembershipResponse],
    status_code=status.HTTP_201_CREATED,
    summary=(
        "Renew membership (reception+owner; "
        "404 plan_not_found / membership_not_found; "
        "409 cannot_renew_cancelled / plan_archived)"
    ),
)
async def renew_membership(
    membership_id: UUID,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.CREATE, Resource.MEMBERSHIPS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[MembershipResponse]:
    """Renew a membership (MEM-REN-EP-01). CREATE permission + CSRF required.

    Creates a follow-up membership chained via `previous_membership_id` to the
    source. Snapshots from the CURRENT plan (so price increases between sale
    and renewal apply — PROJECT.md). Returns 201 + new MembershipResponse
    including `previousMembershipId` field.

    Date strategy:
      - source 'active' / 'frozen' → start_date = source.end_date + 1 day
      - source 'expired'           → start_date = today (Europe/Moscow)

    Errors:
      - 404 membership_not_found  (source missing)
      - 404 plan_not_found        (source's plan hard-deleted; defence-in-depth)
      - 409 cannot_renew_cancelled (source is cancelled — operator must sell new)
      - 409 plan_archived          (source's plan soft-deleted by owner)
    """
    new_membership = await service.renew_membership(session, actor, membership_id)
    return envelope(new_membership)
```

**Invariants:**
- **RBAC-04 ordering** (`router.py:44-49` docstring + `tests/integration/test_route_introspection.py`): `Depends(require_permission(...))` MUST appear BEFORE `Depends(verify_csrf)` in the signature so 401 → 403 ordering is preserved. Mirror exact ordering of `freeze_membership` at `router.py:333-340`.
- **Status code: 201 Created** (NOT 200) — semantically a NEW resource is created (matches `create_membership` line 266 `status_code=status.HTTP_201_CREATED`). REQUIREMENTS MEM-REN-EP-01 explicit.
- **Permission:** `(CREATE, MEMBERSHIPS)` — reception+owner per `OWNER_ONLY` (15 entries from Phase 22; CREATE on memberships NOT in OWNER_ONLY). Mirrors freeze/unfreeze (`router.py:337`).
- **Empty body:** no Pydantic body schema; FastAPI accepts no body on POST. Matches freeze/unfreeze signature.
- **Path:** `/{membership_id}/renew` — distinct suffix from `/freeze`, `/unfreeze`, `/cancel`; FastAPI exact-match resolution → no shadowing risk (D-26-31).

---

### `apps/backend/app/modules/memberships/schemas.py` extension (`MembershipResponse.previous_membership_id`)

**Analog:** `MembershipResponse` lines 227-254 — extend in place (D-26-21).

**Pattern:**
```python
class MembershipResponse(ResponseData):
    # ... existing 18 fields stay (id...current_freeze_period) ...

    # Phase 26 MEM-REN-01 — chain attribution (auto-camelCased to previousMembershipId).
    previous_membership_id: UUID | None = None
```

**Placement:** insert as the LAST field after `current_freeze_period` (line 254). Default `None` is backwards-compatible for existing rows that have no source.

**Invariants:**
- BackendSchemaBase auto-converts Python `previous_membership_id` → JSON `previousMembershipId` via `alias_generator` (Phase 4 contract; no manual aliasing needed).
- `extra='forbid'` (inherited) is irrelevant for response schema — it's enforced on inputs.
- NO new request schemas — `POST /renew` empty body (D-26-22).
- NO new query-param schemas — `MembershipListQuery` not extended (D-26-22 / D-26-23).
- `_build_membership_response` (`service.py:192-256`) projection dict (lines 235-255) needs ONE field added: `"previous_membership_id": membership.previous_membership_id`. Same change in `list_memberships` projection (`service.py:851-871`).

---

### `apps/backend/app/modules/memberships/constants.py` extension (renewal strategy literals)

**Analog:** itself lines 1-30. Append after the existing `MEMBERSHIP_STATUS_TRANSITIONS` block + update `__all__`.

**Pattern** (D-26-13):
```python
# ... existing imports + MEMBERSHIP_STATUS_TRANSITIONS unchanged ...

# Phase 26 D-26-13 — start_date strategy literals (audit payload values).
# Captured as module-level constants so tests can assert exact literals; service
# emits these via the audit payload key `start_date_strategy` (D-26-15).
RENEWAL_STRATEGY_FROM_SOURCE_END_DATE = "from_source_end_date"
RENEWAL_STRATEGY_FROM_TODAY_EXPIRED_SOURCE = "from_today_expired_source"

__all__ = [
    "MEMBERSHIP_STATUS_TRANSITIONS",
    "RENEWAL_STRATEGY_FROM_SOURCE_END_DATE",
    "RENEWAL_STRATEGY_FROM_TODAY_EXPIRED_SOURCE",
]
```

**Module docstring update** (lines 1-15 area) — replace the "Phase 25 populates… Phase 26 may extend renewal-related edges if necessary." line with:
```
Phase 25 populated the freeze edges (active → frozen, frozen → {active, cancelled}).
Phase 26 leaves MEMBERSHIP_STATUS_TRANSITIONS UNCHANGED — renewal creates a new
row (INSERT), it does NOT transition the source. Phase 26 ALSO appends the
`RENEWAL_STRATEGY_*` literal constants used by service.renew_membership in the
audit payload `start_date_strategy` field (D-26-13).
```

**Invariants:**
- `MEMBERSHIP_STATUS_TRANSITIONS` is **NOT** modified in Phase 26 (D-26-24) — renewal is INSERT, not transition.
- New constants are plain `str` (no enum) — match Phase 24 `str` keys convention (lines 12-14 docstring); audit payload accepts strings; AST gate validates `event` + `resource_type` literals only (NOT payload values), so values may be variables — but the variables themselves are stable string literals.
- `__all__` extension matches existing style.
- `tests/unit/memberships/test_renewal_constants.py` (NEW; D-26-29) asserts both string values are exactly `"from_source_end_date"` and `"from_today_expired_source"`.

---

### `apps/backend/app/core/exceptions.py` extensions (`CannotRenewCancelledError` + `PlanArchivedError`)

**Analog:** `PlanInactiveError` lines 133-142 (ConflictError 409 with `plan_*` code) + `AlreadyFrozenError` lines 191-201 (Phase 25 — same shape).

**`CannotRenewCancelledError`** (D-26-09 — append AFTER `PlanInUseError` at line 155, BEFORE `InvalidTransitionError` line 158):
```python
class CannotRenewCancelledError(ConflictError):
    """Raised on POST /memberships/{id}/renew when source membership status is 'cancelled' (Phase 26 MEM-REN-02 / D-26-09).

    Rationale: cancellation is terminal/intentional revocation; renewal would
    mask cancellation intent. Operator must sell a NEW membership via
    POST /api/v1/memberships instead. If owner needs an "uncancel" path, that
    is a separate endpoint (currently backlog — CONTEXT.md Deferred).
    """

    code = "cannot_renew_cancelled"
    status_code = 409
```

**`PlanArchivedError`** (D-26-09 — append immediately after `CannotRenewCancelledError`):
```python
class PlanArchivedError(ConflictError):
    """Raised on POST /memberships/{id}/renew when source.plan is soft-deleted (deleted_at IS NOT NULL) (Phase 26 MEM-REN-02 / D-26-08).

    Distinct from PlanInactiveError (active=False = paused but alive — renewal
    ALLOWED for inactive plans per D-26-08). Renewal cannot use a plan that
    owner archived. Operator must sell a new membership using a current alive
    plan instead. Discriminated by repository.get_plan_for_renewal returning
    (plan, is_archived=True).
    """

    code = "plan_archived"
    status_code = 409
```

**Reused exceptions (NOT re-defined):**
- `PlanNotFoundError` (lines 115-119) — for null-plan case (D-26-08).
- `MembershipNotFoundError` (lines 204-208) — for null-source case.
- `InvalidTransitionError` (lines 158-173) — for defence-in-depth "unknown source status" branch (D-26-14 step 2).

**Invariants:**
- `AppError.__init__` signature (lines 13-16): `__init__(self, message: str = "", *, fields: dict[str, object] | None = None)`. Construction MUST pass code-as-message: `raise CannotRenewCancelledError("cannot_renew_cancelled")`. Mirror `cancel_membership` raise at `service.py` line 543 + `freeze_membership` raise at line 668.
- `register_exception_handlers` (lines 271-283) handles all `AppError` subclasses uniformly via the `JSONResponse` shape — NO new handler needed.

---

### `apps/backend/app/core/audit.py` docstring update (D-26-26)

**Analog:** itself, lines 61-62.

**Current** (lines 61-62):
```
  - membership_renewed                  {membership_id, client_id, plan_id, new_end_date}
                                        # 'membership' (Phase 26 — before/after expiry)
```

**Replace with** (Phase 26 actual payload per D-26-15):
```
  - membership_renewed                  {client_id, source_membership_id, source_plan_id,
                                         current_price_kopecks, start_date_strategy}
                                        # 'membership' (Phase 26 — operator-initiated renewal;
                                        # resource_id = new_membership.id; current_price_kopecks
                                        # captures plan price at renewal time, not source snapshot;
                                        # start_date_strategy literal is one of D-26-13 constants)
```

**Invariants:**
- `LOCKED_AUDIT_EVENTS` line 142 (`("membership_renewed", "membership")`) is **NOT** changed — pair already pre-registered Phase 24 D-24-18.
- Docstring drift fix mirrors Phase 25 D-25-27 closing pattern (consistent house style: update docstring at callsite addition).

---

### NEW unit test: `apps/backend/tests/unit/memberships/test_renewal_constants.py`

**Analog:** `tests/unit/memberships/test_state_machine.py:109-136` (constant-inspection tests).

**Pattern** (D-26-29):
```python
"""Phase 26 D-26-13 — renewal strategy constants.

Asserts the two literal string values frozen by RENEWAL_STRATEGY_*. Service's
audit payload uses these via `start_date_strategy` key; integration tests
assert exact match against these constants. Drift would silently break
forensic SQL like:
    SELECT COUNT(*) FROM audit_log
    WHERE event='membership_renewed'
      AND payload->>'start_date_strategy' = 'from_today_expired_source';
"""

from __future__ import annotations

from app.modules.memberships.constants import (
    RENEWAL_STRATEGY_FROM_SOURCE_END_DATE,
    RENEWAL_STRATEGY_FROM_TODAY_EXPIRED_SOURCE,
)


def test_renewal_strategy_from_source_end_date_literal() -> None:
    """D-26-13: literal value frozen as 'from_source_end_date'."""
    assert RENEWAL_STRATEGY_FROM_SOURCE_END_DATE == "from_source_end_date"


def test_renewal_strategy_from_today_expired_source_literal() -> None:
    """D-26-13: literal value frozen as 'from_today_expired_source'."""
    assert RENEWAL_STRATEGY_FROM_TODAY_EXPIRED_SOURCE == "from_today_expired_source"


def test_renewal_strategies_are_distinct() -> None:
    """Defence-in-depth: copy-paste accident would collapse the two literals."""
    assert (
        RENEWAL_STRATEGY_FROM_SOURCE_END_DATE
        != RENEWAL_STRATEGY_FROM_TODAY_EXPIRED_SOURCE
    )
```

---

### NEW integration test: `apps/backend/tests/integration/memberships/test_renewal_active.py`

**Analog:** `tests/integration/memberships/test_freeze_cycle.py` (full happy-path roundtrip + audit assertions) + `test_memberships_audit.py`.

**Pattern (MEM-REN-TEST-01)** — D-26-29:
- Use SAVEPOINT-mode `db_session` + `authed_client_owner`/`_reception` + `make_plan` + `make_membership` from `tests/integration/memberships/conftest.py:187-256`.
- Seed: client + plan(duration=30, price=200000) + active membership (start=today, end=today+29).
- Inject clock or seed source with explicit dates so `source.end_date + 1` is deterministic.
- POST `/api/v1/memberships/{source.id}/renew` → assert 201 + envelope.
- Assert response body (camelCase):
  - `previousMembershipId == source.id`
  - `startDate == source.end_date + 1`
  - `endDate == new.start_date + 29`
  - `priceKopecksSnapshot == 200_000`
  - `durationDaysSnapshot == 30`
  - `freezeDaysLimitSnapshot == plan.freeze_days_limit`
  - `status == 'active'`
- Assert audit_log row: `event='membership_renewed'`, `resource_id=new.id`, `payload->'source_membership_id' == str(source.id)`, `payload->'start_date_strategy' == 'from_source_end_date'`.
- Optional: call resolver via `service.resolve_active_membership_by_client(today=source.end_date)` → returns source (still running by D-26-17 tiebreak); call again with `today=source.end_date+1` → ARQ-flip simulation: manually update source.status='expired' → resolver returns renewal.

---

### NEW integration test: `apps/backend/tests/integration/memberships/test_renewal_price_change.py`

**Analog:** `test_memberships_audit.py` (audit payload assertions) + `tests/integration/memberships/test_plans_crud.py` (PATCH plan price flow).

**Pattern (MEM-REN-TEST-02)** — D-26-29:
- Seed: plan(price=200000), active membership (snapshot=200000).
- PATCH plan price=300000 (or use repository.update_plan directly via real-commit session).
- POST `/renew` → 201.
- Assert:
  - response `priceKopecksSnapshot == 300_000` (CURRENT plan price, NOT source snapshot)
  - `audit_log.payload->>'current_price_kopecks' == '300000'`
- Confirm source.price_kopecks_snapshot still 200_000 (unchanged — snapshot semantics).

---

### NEW integration test: `apps/backend/tests/integration/memberships/test_renewal_archived_plan.py`

**Analog:** `test_freeze_endpoints.py` (409 response shape) + `tests/integration/memberships/test_plan_in_use.py` (plan archive flow).

**Pattern (MEM-REN-TEST-03 — A + B parts)** — D-26-29:
- **Part A — archived plan:** seed plan + membership; soft-delete plan via `repository.soft_delete_plan` (sets `deleted_at`); POST `/renew` → assert 409 + body `{code: "plan_archived", message: "plan_archived", fields: null}`.
- **Part B — cancelled source:** seed membership; cancel via `service.cancel_membership` (sets status='cancelled'); POST `/renew` → assert 409 + body `{code: "cannot_renew_cancelled", ...}`.
- Both parts share the helper imports + `_csrf_headers` pattern from `test_freeze_endpoints.py:23-44`.

---

### NEW integration test: `apps/backend/tests/integration/memberships/test_renewal_expired_source.py`

**Analog:** `test_freeze_cycle.py` + `tests/integration/memberships/test_expire_due_memberships_service.py` (clock injection precedent for ARQ expiry simulation).

**Pattern (MEM-REN-TEST-04)** — D-26-29:
- Seed: plan(duration=30) + membership with `start_date = today - 60d`, `end_date = today - 31d` (already past).
- Trigger expiry: either inject `today` and call `_expire_due_memberships(session, today=today)` OR manually update source.status='expired' via repository.
- POST `/renew` → 201.
- Assert:
  - response `startDate == today (Europe/Moscow)` (NOT source.end_date + 1).
  - response `endDate == today + 29`.
  - `audit_log.payload->>'start_date_strategy' == 'from_today_expired_source'`.
- Compare with `test_renewal_active.py` strategy field: should be `'from_source_end_date'` there.

**Clock injection:** mirror Phase 24 D-24-06 pattern — pass explicit `today` arg into `_expire_due_memberships(today=)` for ARQ simulation; for `service.renew_membership` itself, the date is computed via `datetime.now(ZoneInfo(...))` inside the function. If exact-day determinism needed, monkeypatch `service.datetime.now` (mirrors `test_expire_due_memberships_service.py` if it does so) OR accept "today" as the test's wall-clock and assert `>=` rather than exact equality. Avoid `freezegun` (Phase 24 D-24-06 / Phase 25 D-25-24).

---

### NEW integration test: `apps/backend/tests/integration/memberships/test_renewal_endpoint.py`

**Analog (exact mirror):** `tests/integration/memberships/test_freeze_endpoints.py` lines 1-80 (full RBAC matrix structure).

**Pattern** — RBAC + CSRF + response shape (D-26-29):
- `test_renew_anonymous_returns_401` — POST without auth → 401.
- `test_renew_reception_returns_201` — reception POST → 201 (D-26-20: CREATE not in OWNER_ONLY).
- `test_renew_owner_returns_201` — owner POST → 201.
- `test_renew_csrf_missing_returns_403` — POST without `X-CSRF-Token` → 403 csrf_mismatch.
- `test_renew_unknown_source_returns_404` — POST `/{uuid4()}/renew` → 404 membership_not_found.
- `test_renew_response_includes_previous_membership_id_camelcase` — assert `body["data"]["previousMembershipId"] == str(source.id)`.
- `test_renew_response_includes_freeze_projection_zero_baseline` — assert `freezeDaysUsed == 0`, `currentFreezePeriod is None`, `freezeDaysRemaining == plan.freeze_days_limit`.
- Reuse `_csrf_headers(client)` helper + `VALID_CLIENT` payload + `_create_client` helper from `test_freeze_endpoints.py:23-44` (copy-paste; no shared util module exists).

---

### NEW integration test: `apps/backend/tests/integration/memberships/test_renewal_resolver_tiebreak.py`

**Analog (exact mirror):** `tests/integration/memberships/test_resolver.py` + `test_freeze_resolver.py`.

**Pattern (MEM-REN-03 carry-forward)** — D-26-29:
- Seed:
  - source: active, start=today-25, end=today+5.
  - renewal: active, start=today+6, end=today+35, previous_membership_id=source.id.
- Call `service.resolve_active_membership_by_client(session, client_id, today=today)` → assert returns SOURCE (lower start_date wins per D-26-17).
- Inject `today=source.end_date + 1` (= today+6); manually update source.status='expired' (simulate ARQ flip) → assert resolver returns RENEWAL.
- Edge case: same start_date (manual stacking, Phase 17 D-01) → assert tiebreak by `created_at DESC` returns LATER-created row (silent, no warning).

---

### NEW integration test: `apps/backend/tests/integration/memberships/test_renewal_from_frozen.py`

**Analog:** `test_cancel_during_freeze.py` (cross-flow with freeze state) + `test_freeze_cycle.py`.

**Pattern (basic happy-path; full sweep stays in Phase 29)** — D-26-29:
- Seed active membership; POST `/freeze` → status='frozen'.
- POST `/renew` → 201.
- Assert:
  - response `startDate == source.end_date + 1` (NOT today; frozen ≠ expired per D-26-10).
  - source row remains status='frozen' (unchanged).
  - `audit_log.payload->>'start_date_strategy' == 'from_source_end_date'`.
- Resolver behaviour: call `resolve_active_membership_by_client` → returns NONE (frozen excluded by `status='active'` filter; renewal start_date is in future so `end_date >= today` true but `start_date > today` — but the resolver's `find_active_for_client` filters by `status='active' AND end_date >= today`, NOT by start_date, so renewal IS returned. Test asserts this: resolver returns RENEWAL even while source is frozen).
- POST `/checkin` (reception path) WHILE source frozen → 409 `no_active_membership` IF renewal.start_date > today (renewal is active but not yet started — the resolver returns it but visit logic should reject? OR — review with planner: per current code resolver returns renewal as active, so `/checkin` would succeed against renewal. This is a Phase 26 edge case — document expected behaviour in plan; cross-flow sweep formalized in Phase 29).
- NOTE: this is the cross-flow Phase 25 D-25-deferred mentioned for Phase 29 verification; Phase 26 covers basic renewal-from-frozen happy path here, full integration sweep stays in Phase 29.

---

## Shared Patterns

### Authentication / RBAC

**Source:** `apps/backend/app/core/dependencies.py` — `require_permission(Action, Resource)`, `verify_csrf`, `CurrentUser`.
**Apply to:** `POST /memberships/{id}/renew` (D-26-20).
**Pattern reference:** `freeze_membership` route at `router.py:333-340`; RBAC-04 ordering enforced by `tests/integration/test_route_introspection.py`.

```python
actor: Annotated[CurrentUser, Depends(require_permission(Action.CREATE, Resource.MEMBERSHIPS))],
_csrf: Annotated[None, Depends(verify_csrf)],
```

### Service-layer commit ordering (Phase 16 D-14, SVC001 gate)

**Source:** `apps/backend/app/modules/memberships/service.py:17-39` module docstring + `freeze_membership` lines 608-688.
**Apply to:** `renew_membership` public function.
**Pattern:**
```
load → guard → load plan → compute dates → repository.insert_renewal_membership →
flush (surface FK errors) → audit.emit (BEFORE commit, co-transactional D-14) →
refresh(created_at, updated_at) → session.commit() (SVC001 enforces presence)
```

**Test gate:** `tests/unit/test_service_commit_gate.py:167-211` — `_INSPECTED_SERVICES` includes `memberships/service.py`. `renew_membership` MUST end in `await session.commit()`.

### Audit emit (LITERAL strings + LOCKED_AUDIT_EVENTS)

**Source:** `apps/backend/app/core/audit.py:150-205` (`emit` signature) + `LOCKED_AUDIT_EVENTS` lines 92-147 — pair `("membership_renewed", "membership")` already locked at line 142 (Phase 24 D-24-18).
**Apply to:** Single new callsite in `renew_membership`.
**Pattern:**
```python
await audit.emit(
    session,
    "membership_renewed",         # LITERAL — Phase 15 INFRA-11 AST gate
    actor_user_id=actor.id,
    resource_type="membership",   # LITERAL
    resource_id=new_membership.id,
    client_id=str(new_membership.client_id),    # str-cast for JSONB
    source_membership_id=str(source.id),         # str-cast for JSONB
    source_plan_id=str(source.plan_id),          # str-cast for JSONB
    current_price_kopecks=plan.price_kopecks,    # int — current plan price
    start_date_strategy=strategy,                # str — RENEWAL_STRATEGY_* constant value
)
```

**Test gate:** `tests/unit/test_audit_taxonomy.py` (AST walker) — both `event` and `resource_type` MUST be `ast.Constant(str)`. Pair MUST be in `LOCKED_AUDIT_EVENTS` (already done — Phase 26 only adds a callsite, not an entry).

### Self-FK on same table (Postgres-native)

**Source:** `apps/backend/app/modules/memberships/models.py:111-120` (`Membership.plan_id` FK shape — same module).
**Apply to:** `Membership.previous_membership_id` (D-26-04 / D-26-05).
**Pattern:** identical to existing FKs except target table = same; Postgres handles without cycle issues; ON DELETE SET NULL chosen over CASCADE to preserve audit-attributable history.

### Constraint-name literal-pinning convention

**Source:** `apps/backend/alembic/env.py:60-69` `_include_object` exclusion list.
**Apply to:** Phase 26 — **NO new entry needed.** `fk_memberships_previous_membership_id_memberships` is NOT literal-ref'd by service code (no IntegrityError discriminator translates this FK; concurrent-source-delete is a DBA-direct surgery edge case, not an operator-flow conflict). Mirror Phase 25 `0008_freeze.py:13-15` pattern only when constraint name is referenced from runtime code; renewal does not trip that condition.

### Time injection (Europe/Moscow + UTC)

**Source:** `apps/backend/app/modules/memberships/service.py:481-482` (`create_membership` — date arithmetic with Europe/Moscow + INCLUSIVE end_date).
**Apply to:** `renew_membership` date computation (D-26-10..D-26-12):
- For source.status in (active, frozen): `start_date = source.end_date + timedelta(days=1)` (no TZ — `end_date` is `date` not `datetime`).
- For source.status == 'expired': `start_date = datetime.now(ZoneInfo("Europe/Moscow")).date()`.
- `end_date = start_date + timedelta(days=plan.duration_days - 1)` (INCLUSIVE — mirrors `create_membership:482`).

**Clock injection for tests:** mirror Phase 25 D-25-24 — recommend monkeypatch on `service.datetime.now` for the `expired`-source test where exact-today equality matters; otherwise rely on real wall clock and assert `>=` bounds. Avoid `freezegun` (Phase 24 D-24-06 precedent).

### Pagination envelope + camelCase wire format

**Source:** `apps/backend/app/core/schemas.py` — `BackendSchemaBase` (alias_generator) + `ResponseEnvelope` + `envelope()`.
**Apply to:** `MembershipResponse.previous_membership_id` Python → `previousMembershipId` JSON automatic via `BackendSchemaBase` alias_generator. NO manual aliasing.

### Test fixtures — SAVEPOINT vs real-commit

**Source:** `tests/integration/memberships/conftest.py:43-256` (SAVEPOINT-mode `db_session` + `make_plan` + `make_membership`).
**Apply to:** All Phase 26 integration tests — use SAVEPOINT-mode `db_session` + existing `authed_client_owner`/`_reception` + `make_plan`/`make_membership`. NO real-commit needed (renewal does not race; single INSERT, no concurrency invariants tested in Phase 26).

`make_membership(status="active"|"expired"|"frozen"|"cancelled")` already supports any status override (lines 235 default `status: str = "active"`); Phase 26 tests pass explicit overrides for archived/expired/frozen seeds.

---

## No Analog Found

None — every Phase 26 artifact has either an exact analog (Phase 25 freeze flow / Phase 17 create+cancel flow) or a partial role-match analog within the existing v1.2 + Phase 24 + Phase 25 backend codebase. The novel concerns are:
- Self-FK declaration (covered by Postgres-native + sibling FK pattern at `models.py:111-120`).
- Renewal-specific plan helper `get_plan_for_renewal` (covered by `get_alive` shape + tuple return is straightforward extension).
- ORDER BY tiebreak inversion (covered by D-26-17 + index-adequacy docstring guidance).

All have explicit decision rationale in CONTEXT.md so the planner has zero ambiguity.

---

## Cross-Phase Invariants (planner MUST preserve)

1. **SVC001 commit-gate** (`tests/unit/test_service_commit_gate.py:167-211`): `renew_membership` is a public function in `memberships/service.py` — MUST end with `await session.commit()`. NO `# noqa: SVC001 caller-owns-txn` opt-out (only valid on `_`-prefixed private helpers per Phase 15 INFRA-13).

2. **AST literal-string audit gate** (`tests/unit/test_audit_taxonomy.py`): the single new `audit.emit("membership_renewed", ..., resource_type="membership", ...)` callsite MUST use string literals for `event` and `resource_type`. Pair already in `LOCKED_AUDIT_EVENTS` (Phase 24 D-24-18 pre-registration at `audit.py:142`).

3. **NAMING_CONVENTION** (`apps/backend/app/core/database.py:28-34`): all constraints named via `op.f(...)` in migrations and short-form name in `__table_args__`. Phase 26 self-FK constraint `fk_memberships_previous_membership_id_memberships` follows this — NO addition to `alembic/env.py:_include_object` because not literal-ref'd from runtime.

4. **RBAC-04 ordering** (`router.py:44-49` docstring + `tests/integration/test_route_introspection.py`): in `renew_membership` route signature, `Depends(require_permission(...))` MUST be declared BEFORE `Depends(verify_csrf)`. 401 → 403 ordering preserved.

5. **Caller-owns-txn for repository** (`repository.py:12-14` module docstring): NO `session.commit()` or `session.flush()` calls in `repository.py`. Phase 26 `get_plan_for_renewal` and `insert_renewal_membership` MUST conform.

6. **State-machine UNCHANGED** (D-26-24): `MEMBERSHIP_STATUS_TRANSITIONS` (`constants.py:20-27`) is NOT modified. Renewal creates a NEW row `status='active'` (INSERT); source row keeps its original status (active/frozen/expired). NO `from → to` arc on source. State machine remains 4×4 (Phase 25 D-25-14).

7. **Resolver touch-point Phase 26 lock** (D-26-17): `find_active_for_client` ORDER BY changes from `end_date DESC` → `start_date ASC`. Plan agent MUST run `pytest apps/backend/tests/integration/visits/ apps/backend/tests/integration/auth/ -x` after the resolver swap and BEFORE adding renewal-specific tests so a regression in check-in path surfaces immediately. Phase 19/20 single-active scenarios should not regress.

8. **Migration chain** (D-26-01): `0008_freeze` → `0009_renewal` (Phase 26). Phase 27 will create `0010_notifications` revising from `0009_renewal`. Plan agent verifies (and if necessary updates) `.planning/milestones/v1.3-ROADMAP.md` § "Build Order" wording.

9. **Snapshot pricing for renewal uses CURRENT plan** (PROJECT.md "Snapshot pricing на renewal — берём текущую цену плана"): `repository.insert_renewal_membership` snapshots from `plan.{name,duration_days,price_kopecks,freeze_days_limit}`, NOT from `source.*_snapshot` fields. Audit payload `current_price_kopecks` captures this for forensics.

10. **`previous_membership_id` is immutable post-creation** (D-26-04): set ONCE on INSERT via `service.renew_membership`; NO update path; NO PATCH endpoint touches it. Mirrors snapshot-field immutability convention from Phase 17.

---

## Metadata

**Analog search scope:**
- `apps/backend/app/modules/memberships/` (full module — `models.py`, `repository.py`, `service.py`, `router.py`, `schemas.py`, `constants.py`)
- `apps/backend/app/core/{audit,exceptions,database,schemas,dependencies}.py`
- `apps/backend/alembic/versions/0005_memberships.py` + `0007_status_taxonomy.py` + `0008_freeze.py` + `alembic/env.py`
- `apps/backend/tests/{unit,integration}/memberships/` (test scaffolding shape)
- Phase 25 `25-PATTERNS.md` (already-mapped freeze patterns inherited verbatim)

**Files scanned:** 11 source files + 1 prior PATTERNS.md + 2 planning docs

**Pattern extraction date:** 2026-05-09

**Project skills:** none (no `.claude/skills/` or similar directory present)

**CLAUDE.md applied:** root `./CLAUDE.md` conventions (modular monolith, SQLAlchemy 2.0 async, Pydantic v2, ruff/mypy strict, import-linter, BackendSchemaBase camelCase wire format, audit ordering, GSD workflow enforcement)

**RESEARCH.md status:** none (project config has `research_enabled=false`; Phase 26 file list extracted directly from CONTEXT.md `<canonical_refs>` and `<decisions>` blocks per orchestrator instructions)
