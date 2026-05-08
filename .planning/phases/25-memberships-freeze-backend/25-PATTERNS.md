# Phase 25: Memberships — Freeze (backend) - Pattern Map

**Mapped:** 2026-05-08
**Files analyzed:** 11 new/modified artifacts + 7 new test files
**Analogs found:** 18 / 18 (100% — all artifacts have direct analogs in v1.2/v1.3 backend)
**Mode:** `--auto`

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `apps/backend/alembic/versions/0008_freeze.py` | migration | DDL + backfill | `0004_membership_plans.py` (partial unique index) + `0005_memberships.py` (FK + CHECK + composite index) + `0007_status_taxonomy.py` (alter pattern) | exact (composite — split-by-section) |
| `apps/backend/app/modules/memberships/models.py` (extend) | ORM model | declarative + `__table_args__` | `Membership` class (lines 85-161) + `MembershipPlan` class (lines 53-82) of same file | exact (sibling in same module) |
| `apps/backend/app/modules/memberships/repository.py` (extend) — `insert_freeze_period` | repository fn (mutation, no commit) | INSERT, caller-owns-flush | `insert_membership` (lines 166-193) + `insert_plan` (lines 109-125) | exact |
| `apps/backend/app/modules/memberships/repository.py` (extend) — `get_open_freeze_period` | repository fn (read) | SELECT WHERE LIMIT 1 | `find_active_for_client` (lines 316-352) + `get_membership` (lines 196-205) | exact |
| `apps/backend/app/modules/memberships/repository.py` (extend) — `compute_freeze_days_used` | repository fn (aggregate) | scalar SQL aggregate | (no direct sibling — closest: `total_stmt` count idiom inside `list_alive` lines 82-83) | partial (role-match, novel SQL) |
| `apps/backend/app/modules/memberships/repository.py` (extend) — `_freeze_days_used_subquery` (helper) + LEFT JOIN in `list_memberships` | repository helper | scalar subquery in list query | `list_memberships` predicate-builder pattern (lines 208-290) | partial (role-match, novel JOIN) |
| `apps/backend/app/modules/memberships/service.py` (extend) — `freeze_membership` | service fn (mutation, owns commit) | request-response | `cancel_membership` (lines 394-449) | exact |
| `apps/backend/app/modules/memberships/service.py` (extend) — `unfreeze_membership` | service fn (mutation, owns commit) | request-response | `cancel_membership` (lines 394-449) | exact |
| `apps/backend/app/modules/memberships/service.py` (extend) — `cancel_membership` (frozen-source branch) | service fn extension | request-response | itself (current `cancel_membership` body, lines 394-449); add pre-mutation freeze-close branch BEFORE existing `update_membership_status` step | self-extension |
| `apps/backend/app/modules/memberships/service.py` (extend) — `_is_already_frozen_conflict` | service helper (IntegrityError discriminator) | translation | `_is_plan_name_conflict` (lines 74-84) + `_is_plan_in_use_conflict` (lines 87-102) | exact |
| `apps/backend/app/modules/memberships/service.py` (extend) — `_assert_can_freeze` / `_assert_can_unfreeze` | service helper (transition wrappers) | guard | `_assert_can_cancel` (lines 124-129) + `_assert_can_expire` (lines 132-137) | exact |
| `apps/backend/app/modules/memberships/schemas.py` (extend) — `FreezePeriodResponse` | schema (response) | wire format | `MembershipPlanResponse` (lines 106-117) | exact |
| `apps/backend/app/modules/memberships/schemas.py` (extend) — `MembershipResponse` 4 new fields | schema (response) | wire format | itself (lines 207-229) — extend in place | self-extension |
| `apps/backend/app/modules/memberships/schemas.py` (extend) — `MembershipStatus.FROZEN` | enum value | enum extension | `MembershipStatus` (lines 139-144) | self-extension |
| `apps/backend/app/modules/memberships/router.py` (extend) — `POST /freeze` + `POST /unfreeze` | router endpoint (mutation) | request-response | `cancel_membership` route (lines 284-311) | exact |
| `apps/backend/app/modules/memberships/constants.py` (extend) — populate freeze edges | const map (state machine) | declarative | itself (lines 21-28; placeholder fills) | self-extension |
| `apps/backend/app/core/exceptions.py` (extend) — `FreezeLimitExceededError` + `AlreadyFrozenError` | exception class | error type | `InvalidTransitionError` (lines 158-173) + `PlanInUseError` (lines 145-155) | exact |
| `apps/backend/tests/unit/memberships/test_state_machine.py` (extend) — 9→16 cells | unit test | parametrize matrix | itself (full file) | self-extension |
| `apps/backend/tests/unit/memberships/test_freeze_days_computation.py` (NEW) | unit test | pure helper | `apps/backend/tests/unit/memberships/test_state_machine.py` (DB-free shape) | role-match |
| `apps/backend/tests/integration/memberships/test_freeze_cycle.py` (NEW) | integration test | HTTP roundtrip | `tests/integration/memberships/test_memberships_audit.py` + `test_memberships_crud.py` | role-match |
| `apps/backend/tests/integration/memberships/test_freeze_limit.py` (NEW) | integration test | HTTP error path | `test_memberships_audit.py` (cancel-then-409 patterns) | role-match |
| `apps/backend/tests/integration/memberships/test_freeze_race.py` (NEW) | integration test | concurrency | `tests/integration/visits/test_visits_concurrent.py` (lines 54-160) | exact (mirror) |
| `apps/backend/tests/integration/memberships/test_freeze_resolver.py` (NEW) | integration test | resolver behaviour | `tests/integration/memberships/test_resolver.py` | exact |
| `apps/backend/tests/integration/memberships/test_cancel_during_freeze.py` (NEW) | integration test | multi-event audit | `tests/integration/memberships/test_memberships_audit.py` | role-match |
| `apps/backend/tests/integration/memberships/test_freeze_endpoints.py` (NEW) | integration test | RBAC matrix + shape | `tests/integration/memberships/test_memberships_rbac.py` | role-match |

---

## Pattern Assignments

### `apps/backend/alembic/versions/0008_freeze.py` (migration, DDL + backfill)

**Analogs (composite):** `0004_membership_plans.py` (partial unique index) + `0005_memberships.py` (FK + CHECK + composite) + `0007_status_taxonomy.py` (revision-chain header)

**Revision-chain header pattern** (mirror `0007_status_taxonomy.py:25-28`):
```python
revision: str = "0008_freeze"
down_revision: str | None = "0007_status_taxonomy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```

**Module docstring pattern** (mirror `0004_membership_plans.py:1-15` + `0007_status_taxonomy.py:1-17`):
- 1st para: phase tag + REQ-IDs (e.g. "Phase 25 / MEM-FRZ-01..03").
- "Notes" block calls out: (a) partial unique index installed via `op.execute()` because expression-where indexes are not autogenerate-stable, (b) constraint name literals referenced by `service.py` (`uq_membership_freeze_periods_active_per_membership`), (c) backfill semantics (`COALESCE(plan.freeze_days_limit, 14)` — archived-plan rows lock to 14 by snapshot semantics; downgrade is data-lossy, document in docstring per D-25-03).

**ALTER COLUMN pattern with default-then-drop** (D-25-02 step 1 — mirror Phase 17 snapshot-pricing rationale):
```python
# Step 1 — add freeze_days_limit with DEFAULT 14 so existing rows backfill, then drop default
op.execute(
    "ALTER TABLE membership_plans "
    "ADD COLUMN freeze_days_limit INTEGER NOT NULL DEFAULT 14 "
    "CHECK (freeze_days_limit > 0)"
)
op.execute("ALTER TABLE membership_plans ALTER COLUMN freeze_days_limit DROP DEFAULT")
```
**Invariant:** the CHECK constraint name auto-generated by Postgres in inline `CHECK (...)` differs from `op.f("ck_...")` form. To keep NAMING_CONVENTION literal-references stable, use the explicit `sa.CheckConstraint(name=op.f(...))` form via `op.create_check_constraint(...)` OR install the CHECK on the column via `op.add_column` with `sa.Column(..., sa.CheckConstraint(...))`. Mirror `0005_memberships.py:78-85` constraint-naming rather than the inline-string form above.

**ADD COLUMN nullable → backfill → ALTER NOT NULL pattern** (D-25-02 steps 2-4 — Postgres requires this two-step for safe backfill):
```python
op.add_column("memberships", sa.Column("freeze_days_limit_snapshot", sa.Integer(), nullable=True))
op.execute(
    "UPDATE memberships SET freeze_days_limit_snapshot = "
    "COALESCE((SELECT freeze_days_limit FROM membership_plans WHERE id = memberships.plan_id), 14)"
)
op.alter_column("memberships", "freeze_days_limit_snapshot", nullable=False)
```

**Create-table pattern** (D-25-04 — mirror `0005_memberships.py:34-100` PrimaryKeyConstraint + ForeignKeyConstraint via `op.f(...)`):
```python
op.create_table(
    "membership_freeze_periods",
    sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
    sa.Column("membership_id", sa.UUID(), nullable=False),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("started_by", sa.UUID(), nullable=False),
    sa.Column("ended_by", sa.UUID(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.PrimaryKeyConstraint("id", name=op.f("pk_membership_freeze_periods")),
    sa.ForeignKeyConstraint(
        ["membership_id"], ["memberships.id"],
        name=op.f("fk_membership_freeze_periods_membership_id_memberships"),
        ondelete="RESTRICT",
    ),
    sa.ForeignKeyConstraint(
        ["started_by"], ["users.id"],
        name=op.f("fk_membership_freeze_periods_started_by_users"),
        ondelete="RESTRICT",
    ),
    sa.ForeignKeyConstraint(
        ["ended_by"], ["users.id"],
        name=op.f("fk_membership_freeze_periods_ended_by_users"),
        ondelete="SET NULL",
    ),
)
```

**Partial unique index pattern** (`0004_membership_plans.py:62-65` is the canonical analog — D-25-05):
```python
op.execute(
    "CREATE UNIQUE INDEX uq_membership_freeze_periods_active_per_membership "
    "ON membership_freeze_periods (membership_id) WHERE ended_at IS NULL"
)
```
**Invariants:**
- Constraint-name literal `"uq_membership_freeze_periods_active_per_membership"` MUST be added to `apps/backend/alembic/env.py:_include_object` exclusion tuple (currently lines 60-66, contains `"uq_membership_plans_name_alive"`) so autogenerate skips the partial unique on subsequent revisions.
- The literal is also referenced by `service.py:_is_already_frozen_conflict` (D-25-22).

**Downgrade pattern** (`0004_membership_plans.py:68-70` shape, but reverse all 6 upgrade steps in reverse order — D-25-03):
```python
def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_membership_freeze_periods_active_per_membership")
    op.drop_table("membership_freeze_periods")
    op.drop_column("memberships", "freeze_days_limit_snapshot")
    op.drop_column("membership_plans", "freeze_days_limit")
```
**Invariant:** docstring MUST flag downgrade as data-lossy (snapshots cannot be re-derived after column drop) per D-25-03.

---

### `apps/backend/app/modules/memberships/models.py` extension (ORM model — `MembershipFreezePeriod` + `Membership.freeze_days_limit_snapshot` + `MembershipPlan.freeze_days_limit`)

**Analog:** sibling classes in same file — `Membership` (lines 85-161) + `MembershipPlan` (lines 53-82).

**Composition pattern** (`Membership` line 85 — D-25-04 specifies `Base + UUIDPkMixin + TimestampMixin`, NO `SoftDeleteMixin`):
```python
class MembershipFreezePeriod(Base, UUIDPkMixin, TimestampMixin):
    """Membership freeze period — open while ended_at IS NULL (Phase 25 MEM-FRZ-02)."""

    __tablename__ = "membership_freeze_periods"
```

**FK column pattern** (`Membership` lines 99-117):
```python
membership_id: Mapped[UUIDType] = mapped_column(
    PgUUID(as_uuid=True),
    ForeignKey(
        "memberships.id",
        ondelete="RESTRICT",
        name="fk_membership_freeze_periods_membership_id_memberships",
    ),
    nullable=False,
)
started_by: Mapped[UUIDType] = mapped_column(
    PgUUID(as_uuid=True),
    ForeignKey("users.id", ondelete="RESTRICT", name="fk_membership_freeze_periods_started_by_users"),
    nullable=False,
)
ended_by: Mapped[UUIDType | None] = mapped_column(
    PgUUID(as_uuid=True),
    ForeignKey("users.id", ondelete="SET NULL", name="fk_membership_freeze_periods_ended_by_users"),
    nullable=True,
)
```

**TIMESTAMPTZ column pattern** (`Membership.cancelled_at` lines 128-131):
```python
started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

**`__table_args__` partial unique index pattern** (`MembershipPlan.__table_args__` lines 76-81 — D-25-05):
```python
__table_args__ = (
    Index(
        "uq_membership_freeze_periods_active_per_membership",
        "membership_id",
        unique=True,
        postgresql_where=text("ended_at IS NULL"),
    ),
)
```

**Membership column extension** (`Membership.duration_days_snapshot` line 119 — mirror snapshot pattern):
```python
freeze_days_limit_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
```

**MembershipPlan column extension** (`MembershipPlan.duration_days` line 59 + CheckConstraint pattern lines 66-70):
```python
freeze_days_limit: Mapped[int] = mapped_column(Integer, nullable=False)
# ... in __table_args__ extend with:
CheckConstraint("freeze_days_limit > 0", name="freeze_days_limit_positive"),
# NAMING_CONVENTION expands to ck_membership_plans_freeze_days_limit_positive
```

**Invariants:**
- NAMING_CONVENTION (`apps/backend/app/core/database.py:28-34`) auto-expands `name="status"` → `ck_memberships_status`. Use the SHORT constraint name in `__table_args__`; the long name lives in the migration's `op.f(...)` form.
- ORM file MUST also be added to `apps/backend/alembic/env.py:24-28` import block if a NEW model file is created (NOT needed if `MembershipFreezePeriod` lives inline in `models.py` per D-25-discretion recommendation).
- `created_at` from TimestampMixin and `started_at` are SEMANTICALLY DISTINCT (audit row wallclock vs operational period start) — document in class docstring (Risks/Watchpoints note 1).

---

### `apps/backend/app/modules/memberships/repository.py` extensions

**Analog:** `find_active_for_client` (lines 316-352) + `insert_membership` (lines 166-193) + `update_membership_status` (lines 293-313) + `expire_due_rows` (lines 360-396).

**Insert helper** (`insert_membership` lines 166-193 — D-25-16):
```python
async def insert_freeze_period(
    session: AsyncSession,
    *,
    membership_id: UUID,
    started_by: UUID,
    started_at: datetime,
) -> MembershipFreezePeriod:
    """Insert an open freeze period. Caller (service) owns flush + commit and
    handles IntegrityError on uq_membership_freeze_periods_active_per_membership.
    """
    period = MembershipFreezePeriod(
        membership_id=membership_id,
        started_by=started_by,
        started_at=started_at,
        # ended_at intentionally omitted — NULL while period is open.
    )
    session.add(period)
    return period
```

**Single-row read helper** (`get_membership` lines 196-205 + `find_active_for_client` lines 316-352):
```python
async def get_open_freeze_period(
    session: AsyncSession, membership_id: UUID
) -> MembershipFreezePeriod | None:
    """Return the open freeze period for `membership_id`, or None.

    Defence-in-depth: if status='frozen' but no open period exists, that's a
    DB-level invariant violation (manual SQL surgery, bug). Caller raises.
    """
    stmt = (
        select(MembershipFreezePeriod)
        .where(
            MembershipFreezePeriod.membership_id == membership_id,
            MembershipFreezePeriod.ended_at.is_(None),
        )
        .limit(1)
    )
    result: MembershipFreezePeriod | None = await session.scalar(stmt)
    return result
```

**SQL aggregate scalar pattern** (closest analog: `total = await session.scalar(total_stmt) or 0` in `list_alive` lines 82-83 — D-25-16):
```python
async def compute_freeze_days_used(
    session: AsyncSession, membership_id: UUID, *, today_msk: date
) -> int:
    """Sum of completed-period days + ongoing days if frozen (MEM-FRZ-EP-03).

    Single SQL aggregate — O(1) extra query per row (avoids N+1 in list view).
    `CEIL((COALESCE(ended_at, now()) - started_at) seconds / 86400)` matches the
    "half-day rounds up" semantic byte-stable between Python (math.ceil) and SQL.
    """
    stmt = text(
        "SELECT COALESCE(SUM("
        "  CEIL(EXTRACT(EPOCH FROM (COALESCE(ended_at, now()) - started_at)) / 86400)"
        "), 0)::int "
        "FROM membership_freeze_periods "
        "WHERE membership_id = :membership_id"
    )
    result = await session.scalar(stmt, {"membership_id": membership_id})
    return int(result or 0)
```

**Subquery aggregate for list view** (`list_memberships` predicate-builder shape lines 208-290 + `list_alive` count idiom — D-25-18):
```python
def _freeze_days_used_subquery() -> Subquery:
    """Reusable scalar subquery for list view's freeze_days_used column.

    Emitted as a LEFT JOIN against memberships so list view stays single-query.
    """
    return (
        select(
            MembershipFreezePeriod.membership_id.label("membership_id"),
            func.coalesce(
                func.sum(
                    func.ceil(
                        func.extract(
                            "epoch",
                            func.coalesce(MembershipFreezePeriod.ended_at, func.now())
                            - MembershipFreezePeriod.started_at,
                        )
                        / 86400
                    )
                ),
                0,
            )
            .cast(Integer)
            .label("days_used"),
        )
        .group_by(MembershipFreezePeriod.membership_id)
        .subquery()
    )
```

**Caller-owns-txn invariant** (`insert_membership` line 174-175 docstring — repository.py module docstring lines 12-14):
> Transaction control: NO `session.commit()` and NO `session.flush()` calls live here. The caller (service) owns the transactional moment so it can co-write the audit log row in the same UoW.

**Invariants:**
- `update_membership_status` signature (lines 293-313) does NOT need extension — D-25-13 says call with `status="frozen"` for freeze and `status="active"` for unfreeze; cancelled_at/cancel_reason stay None.
- `find_active_for_client` (lines 316-352) — **NO change** in Phase 25 (D-25-17). Frozen rows excluded by existing `Membership.status == "active"` predicate.
- `list_memberships` (lines 208-290) extended with LEFT JOIN to `_freeze_days_used_subquery()` so each row carries `freeze_days_used`; `current_freeze_period` JOIN is a separate concern (small N=20 default page → simple secondary query is acceptable).

---

### `apps/backend/app/modules/memberships/service.py` extensions

**Analog:** `cancel_membership` (lines 394-449) is the canonical mutation flow + `_is_plan_name_conflict` (lines 74-84) for IntegrityError discriminator + `_assert_can_cancel` (lines 124-129) for thin transition wrapper.

**Module docstring update** — extend the existing docstring's "Audit emit ordering" section (lines 17-30) with freeze/unfreeze cases. Mirror the bulleted format.

**Thin transition wrapper pattern** (`_assert_can_cancel` lines 124-129 — D-25-15):
```python
def _assert_can_freeze(membership: Membership) -> None:
    """Phase 25 D-25-15: only status='active' may transition to 'frozen'.

    Thin wrapper over `_assert_can_transition` — same Phase 24 D-24-05 pattern.
    """
    _assert_can_transition(membership, target="frozen")


def _assert_can_unfreeze(membership: Membership) -> None:
    """Phase 25 D-25-15: only status='frozen' may transition to 'active'."""
    _assert_can_transition(membership, target="active")
```

**IntegrityError discriminator** (`_is_plan_name_conflict` lines 74-84 — exact mirror, constraint name swapped — D-25-22):
```python
def _is_already_frozen_conflict(exc: IntegrityError) -> bool:
    """Return True iff `exc` was caused by uq_membership_freeze_periods_active_per_membership.

    Direct mirror of `_is_plan_name_conflict` with constraint name substituted.
    Concurrent-INSERT race on the partial unique index — second freeze loses.
    """
    constraint = getattr(exc.orig, "constraint_name", None) or ""
    if constraint == "uq_membership_freeze_periods_active_per_membership":
        return True
    return "uq_membership_freeze_periods_active_per_membership" in str(exc.orig)
```

**`freeze_membership` mutation flow** (mirror `cancel_membership` lines 394-449 step-by-step — D-25-07):
```python
async def freeze_membership(
    session: AsyncSession,
    actor: CurrentUser,
    membership_id: UUID,
) -> MembershipResponse:
    """Open a freeze period and transition active → frozen (MEM-FRZ-04).

    Order (mirror cancel_membership: D-15 invariant — guard BEFORE mutation):
      1. Load — 404 membership_not_found if missing.
      2. Transition guard — 409 invalid_transition for non-active source.
      3. Preventive limit check (D-25-07 step 3) — 409 freeze_limit_exceeded.
      4. INSERT freeze period → flush → catch IntegrityError → 409 already_frozen
         (constraint-name discrimination via _is_already_frozen_conflict).
      5. update_membership_status(status="frozen").
      6. Flush.
      7. audit.emit("membership_frozen", ...) — payload per D-25-27.
      8. Refresh updated_at.
      9. Commit (SVC001 gate enforces this).
    """
    membership = await repository.get_membership(session, membership_id)
    if membership is None:
        raise MembershipNotFoundError("membership_not_found")

    _assert_can_freeze(membership)

    today_msk = datetime.now(ZoneInfo("Europe/Moscow")).date()
    days_used = await repository.compute_freeze_days_used(
        session, membership_id, today_msk=today_msk
    )
    if days_used >= membership.freeze_days_limit_snapshot:
        raise FreezeLimitExceededError(
            "freeze_limit_exceeded",
            fields={"limit": membership.freeze_days_limit_snapshot, "used": days_used},
        )

    now_utc = datetime.now(tz=UTC)
    period = await repository.insert_freeze_period(
        session, membership_id=membership.id, started_by=actor.id, started_at=now_utc,
    )
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if _is_already_frozen_conflict(exc):
            raise AlreadyFrozenError("already_frozen") from exc
        raise

    await repository.update_membership_status(session, membership, status="frozen")
    await session.flush()

    await audit.emit(
        session,
        "membership_frozen",  # LITERAL (Phase 15 INFRA-11 AST gate)
        actor_user_id=actor.id,
        resource_type="membership",  # LITERAL
        resource_id=membership.id,
        client_id=str(membership.client_id),
        freeze_period_id=str(period.id),
        started_at=period.started_at.isoformat(),
    )
    await session.refresh(membership, attribute_names=["updated_at"])
    await session.commit()  # SVC001 gate
    return MembershipResponse.model_validate(...)  # see "Response shape" below
```

**`unfreeze_membership` flow** (same template, with day-math — D-25-08):
```python
async def unfreeze_membership(
    session: AsyncSession,
    actor: CurrentUser,
    membership_id: UUID,
) -> MembershipResponse:
    membership = await repository.get_membership(session, membership_id)
    if membership is None:
        raise MembershipNotFoundError("membership_not_found")

    _assert_can_unfreeze(membership)

    period = await repository.get_open_freeze_period(session, membership_id)
    if period is None:
        # Defence-in-depth: status='frozen' implies open period exists.
        raise RuntimeError("frozen_membership_without_open_period")  # 500

    now_utc = datetime.now(tz=UTC)
    period.ended_at = now_utc
    period.ended_by = actor.id

    delta_seconds = (period.ended_at - period.started_at).total_seconds()
    days_added = max(1, math.ceil(delta_seconds / 86400))  # D-25-08 step 5
    membership.end_date = membership.end_date + timedelta(days=days_added)

    await repository.update_membership_status(session, membership, status="active")
    await session.flush()

    await audit.emit(
        session,
        "membership_unfrozen",  # LITERAL
        actor_user_id=actor.id,
        resource_type="membership",  # LITERAL
        resource_id=membership.id,
        client_id=str(membership.client_id),
        freeze_period_id=str(period.id),
        days_added=days_added,
    )
    await session.refresh(membership, attribute_names=["updated_at"])
    await session.commit()
    return MembershipResponse.model_validate(...)
```

**`cancel_membership` extension for frozen source** (D-25-09 — insert BEFORE existing line 423 `update_membership_status` call):
```python
# After existing _assert_can_cancel(membership) line 420.
# D-25-09: if cancelling from frozen, close the open period first.
if membership.status == "frozen":
    period = await repository.get_open_freeze_period(session, membership.id)
    if period is None:
        raise RuntimeError("frozen_membership_without_open_period")
    period.ended_at = datetime.now(tz=UTC)
    period.ended_by = actor.id
    # NO end_date extension — cancellation supersedes freeze (REQUIREMENTS MEM-FRZ-07).
    await session.flush()
    await audit.emit(
        session,
        "membership_unfrozen",  # LITERAL
        actor_user_id=actor.id,
        resource_type="membership",
        resource_id=membership.id,
        client_id=str(membership.client_id),
        freeze_period_id=str(period.id),
        days_added=0,  # sentinel (D-25-09): discriminates cancel-from-frozen in audit log
    )
# Existing flow continues: update_membership_status(status="cancelled", cancelled_at=..., cancel_reason=...)
```

**Audit ordering invariant** (D-25-09 + REQUIREMENTS MEM-FRZ-07): `membership_unfrozen` MUST be emitted BEFORE `membership_cancelled` in the same UoW (single commit at end). `audit_log` `id` auto-increment provides chronological ordering. Test verifies both rows present.

**Docstring update for `_assert_can_cancel`** (lines 124-129 — Risks/Watchpoints note "Plan-agent docstring update"): the current docstring says "only status='active' may transition to 'cancelled'". Phase 25 makes this incorrect — update to "active OR frozen may transition to 'cancelled'".

**SVC001 commit-gate invariant** (`tests/unit/test_service_commit_gate.py:167-211`): `_INSPECTED_SERVICES` already includes `memberships/service.py`. Both NEW public functions (`freeze_membership`, `unfreeze_membership`) MUST end with `await session.commit()` — the AST walker will fail CI otherwise. NO `# noqa: SVC001 caller-owns-txn` opt-out is acceptable for these (only valid on private `_`-prefixed helpers per Phase 15 INFRA-13).

**Invariants:**
- All `audit.emit()` event names + `resource_type` MUST be LITERAL strings (Phase 15 INFRA-11 AST gate at `tests/unit/test_audit_taxonomy.py`). The 6 v1.3 pairs are already in `LOCKED_AUDIT_EVENTS` (Phase 24).
- UUIDs in audit payload MUST be `str()`-cast (`client_id=str(membership.client_id)`, `freeze_period_id=str(period.id)`) for JSONB-serialisability. `resource_id` stays `UUID` (column is UUID, not JSONB).
- `service.resolve_active_membership_by_client` (lines 480-508) — **NO change** in Phase 25 (D-25-17).

---

### `apps/backend/app/modules/memberships/schemas.py` extensions

**Analog:** `MembershipResponse` (lines 207-229) + `MembershipPlanResponse` (lines 106-117) + `MembershipStatus` enum (lines 139-144).

**`FreezePeriodResponse` schema** (mirror `MembershipPlanResponse` shape — D-25-12):
```python
class FreezePeriodResponse(ResponseData):
    """Outbound representation of a MembershipFreezePeriod (Phase 25 D-25-12).

    Used as the value of `MembershipResponse.current_freeze_period`. When surfaced
    that way, `ended_at` and `ended_by` are always None (open period definition).
    """

    id: UUID
    started_at: datetime
    started_by: UUID
    ended_at: datetime | None
    ended_by: UUID | None
```

**`MembershipResponse` extension** (lines 207-229 — extend in place, D-25-12):
```python
class MembershipResponse(ResponseData):
    # ... existing 14 fields stay ...
    # Phase 25 MEM-FRZ-EP-03 — freeze projection fields:
    freeze_days_limit_snapshot: int
    freeze_days_used: int
    freeze_days_remaining: int  # computed = limit - used, clamped to 0
    current_freeze_period: FreezePeriodResponse | None  # None when status != frozen
```

**`MembershipStatus` enum extension** (lines 139-144 — D-25-13):
```python
class MembershipStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    FROZEN = "frozen"  # Phase 25 D-25-13
```

**`MembershipPlanCreateRequest` extension** (D-25-10 — add `freeze_days_limit` field):
```python
class MembershipPlanCreateRequest(BackendSchemaBase):
    name: str = Field(min_length=1, max_length=120)
    duration_days: int = Field(ge=1, le=3650)
    price_kopecks: int = Field(ge=0, le=10**11)
    freeze_days_limit: int = Field(ge=1, le=365)  # Phase 25 D-25-10 — explicit, no default
    active: bool = Field(default=True)
```

**`MembershipPlanResponse` extension** (D-25-10 — add field):
```python
freeze_days_limit: int
```

**`MembershipPlanUpdateRequest`** — **NO CHANGE** per D-25-11. `extra='forbid'` (BackendSchemaBase) auto-rejects PATCH payloads containing `freezeDaysLimit` with a stock 422.

**Invariants:**
- BackendSchemaBase auto-converts `freeze_days_limit_snapshot` Python → `freezeDaysLimitSnapshot` JSON via `alias_generator`. NO manual aliasing.
- `extra='forbid'` (inherited from BackendSchemaBase) is the immutability gate for `freeze_days_limit` on PATCH.
- `current_freeze_period` populated by service-layer projection logic; NOT directly available from `MembershipFreezePeriod` ORM via SA relationship (no relationship declared per D-25-discretion / Phase 17 layering minimalism).

---

### `apps/backend/app/modules/memberships/router.py` extensions

**Analog:** `cancel_membership` route (lines 284-311).

**Endpoint signature pattern** (D-25-19):
```python
@memberships_router.post(
    "/{membership_id}/freeze",
    response_model=ResponseEnvelope[MembershipResponse],
    status_code=status.HTTP_200_OK,
    summary="Freeze membership (reception+owner; 409 freeze_limit_exceeded / already_frozen / invalid_transition)",
)
async def freeze_membership(
    membership_id: UUID,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.CREATE, Resource.MEMBERSHIPS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[MembershipResponse]:
    """Freeze a membership (MEM-FRZ-EP-01). CREATE permission + CSRF required."""
    membership = await service.freeze_membership(session, actor, membership_id)
    return envelope(membership)


@memberships_router.post("/{membership_id}/unfreeze", ...)  # mirror exactly
```

**RBAC-04 dependency ordering invariant** (router.py lines 40-45 docstring + `tests/integration/test_route_introspection.py`):
> `Depends(require_permission(...))` MUST be declared BEFORE `Depends(verify_csrf)` in the function signature so 401 (auth) fires before 403 (rbac/csrf).

**Permission mapping** (D-25-19 + CONTEXT.md `<domain>` line 21):
- `(CREATE, MEMBERSHIPS)` — reception+owner. NOT in OWNER_ONLY (Phase 15 INFRA-08 — only `(CANCEL, MEMBERSHIPS)` is owner-only).

**HTTP method/body/response invariants** (D-25-19 + REQUIREMENTS MEM-FRZ-EP-01/02):
- POST (matches REQUIREMENTS).
- Empty body — NO Pydantic body schema (FastAPI accepts no body on POST).
- 200 OK (NOT 201/204) — body carries new state per REQUIREMENTS.
- `cancel_membership` route (line 284-311) is the closest existing analog with this exact 200 OK + body shape.

**Module docstring update** — extend lines 10-22 phase block (currently lists 4 Phase 17 routes) with 2 new Phase 25 routes:
```
Phase 25 endpoint surface (2 new routes — both on `memberships_router`):
  - POST /api/v1/memberships/{id}/freeze    — freeze, 200 (MEM-FRZ-EP-01)
  - POST /api/v1/memberships/{id}/unfreeze  — unfreeze, 200 (MEM-FRZ-EP-02)
```

**Existing `cancel_membership` route** — **NO signature change** per D-25-20. Service-layer guard (D-25-09) handles `frozen → cancelled` transparently. Update docstring (lines 300-309) to mention frozen source acceptance.

---

### `apps/backend/app/modules/memberships/constants.py` extension

**Analog:** itself (lines 21-28 placeholder fills).

**Pattern** (D-25-14):
```python
MEMBERSHIP_STATUS_TRANSITIONS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "active": frozenset({"expired", "cancelled", "frozen"}),  # +frozen
        "expired": frozenset(),  # terminal
        "cancelled": frozenset(),  # terminal
        "frozen": frozenset({"active", "cancelled"}),  # populated
    }
)
```

**Module docstring update** (lines 1-16): change "Phase 24 ships the constant with `frozen: frozenset()` as a placeholder. Phase 25 will populate the freeze edges..." to "Phase 25 populates the freeze edges (`active → frozen`, `frozen → {active, cancelled}`); Phase 26 may extend renewal-related edges if necessary."

**Invariants:**
- `MappingProxyType` (read-only) is verified by `tests/unit/memberships/test_state_machine.py:109-117` (`test_membership_status_transitions_constant_is_immutable`).
- `str` keys (NOT `MembershipStatus` enum) — keeps module low-level / circular-import-safe (lines 13-15 docstring).
- `test_state_machine.py:120-136` (`test_membership_status_transitions_phase24_contents`) MUST be updated for new contents (or replaced by Phase 25 equivalent).

---

### `apps/backend/app/core/exceptions.py` extensions

**Analog:** `InvalidTransitionError` (lines 158-173) for state-machine-style 409 with `fields={...}` payload + `PlanInUseError` (lines 145-155) for IntegrityError-discriminated 409.

**`FreezeLimitExceededError`** (mirror `InvalidTransitionError` structure — D-25-21):
```python
class FreezeLimitExceededError(ConflictError):
    """Raised on POST /memberships/{id}/freeze when cumulative freeze days
    would exceed freeze_days_limit_snapshot (Phase 25 MEM-FRZ-04).

    Constructor:
        raise FreezeLimitExceededError(
            "freeze_limit_exceeded",
            fields={"limit": snapshot_limit, "used": days_used},
        )
    """

    code = "freeze_limit_exceeded"
    status_code = 409
```

**`AlreadyFrozenError`** (mirror `PlanInUseError` lines 145-155 — IntegrityError-discriminated — D-25-21):
```python
class AlreadyFrozenError(ConflictError):
    """Raised on POST /memberships/{id}/freeze when partial unique index
    uq_membership_freeze_periods_active_per_membership rejects concurrent
    INSERT (Phase 25 MEM-FRZ-TEST-03 race).

    Discriminated against IntegrityError by service.py:_is_already_frozen_conflict
    checking constraint name.
    """

    code = "already_frozen"
    status_code = 409
```

**Existing `InvalidTransitionError`** (lines 158-173) — reused as-is for `invalid_transition` 409s. Existing `MembershipNotFoundError` (lines 176-180) — reused as-is for 404s.

**Invariants:**
- `AppError.__init__` signature (lines 13-16): `__init__(self, message: str = "", *, fields: dict[str, object] | None = None)` — exception construction MUST pass `code` as positional message and `fields=` keyword. Mirror existing usage (e.g. `cancel_membership` service.py:436 — `raise InvalidTransitionError("invalid_transition", fields={...})`).
- `register_exception_handlers` (lines 243-256) handles all `AppError` subclasses uniformly — NO new handler needed.

---

### `apps/backend/tests/unit/memberships/test_state_machine.py` extension (9 → 16 cells)

**Analog:** itself (full file, lines 1-137).

**16-cell matrix** (D-25-15):
```python
@pytest.mark.parametrize(
    ("from_status", "action", "expect"),
    [
        # active source — 4 actions
        ("active", "freeze", "ok"),       # NEW
        ("active", "unfreeze", "invalid_transition"),  # NEW
        ("active", "cancel", "ok"),
        ("active", "expire", "ok"),
        # frozen source — 4 actions (NEW row)
        ("frozen", "freeze", "invalid_transition"),
        ("frozen", "unfreeze", "ok"),
        ("frozen", "cancel", "ok"),
        ("frozen", "expire", "invalid_transition"),
        # expired source — 4 actions
        ("expired", "freeze", "invalid_transition"),
        ("expired", "unfreeze", "invalid_transition"),
        ("expired", "cancel", "invalid_transition"),
        ("expired", "expire", "invalid_transition"),
        # cancelled source — 4 actions
        ("cancelled", "freeze", "invalid_transition"),
        ("cancelled", "unfreeze", "invalid_transition"),
        ("cancelled", "cancel", "invalid_transition"),
        ("cancelled", "expire", "invalid_transition"),
    ],
)
def test_state_machine_matrix(from_status: str, action: str, expect: str) -> None:
    # Extend dispatch:
    if action == "freeze":
        target = "frozen"
        guard = _assert_can_freeze
    elif action == "unfreeze":
        target = "active"
        guard = _assert_can_unfreeze
    elif action == "cancel":
        target = "cancelled"
        guard = _assert_can_cancel
    else:  # expire
        target = "expired"
        guard = _assert_can_expire
    # ... rest mirrors existing assert structure (lines 79-91)
```

**Invariant:** `test_membership_status_transitions_phase24_contents` (lines 120-136) MUST be renamed/updated for Phase 25 contents (now `active: {expired, cancelled, frozen}` + `frozen: {active, cancelled}`).

---

### NEW unit test: `apps/backend/tests/unit/memberships/test_freeze_days_computation.py`

**Analog:** existing `test_state_machine.py` (DB-free shape).

**Pattern** (D-25-23):
- Pure-function tests for `math.ceil(delta_seconds / 86400)` rounding.
- Edge cases: `delta_seconds = 0` → assert `max(1, ceil(0))` = 1 (instant unfreeze rule, D-25-08 step 5).
- Fractional day: `delta_seconds = 86400 * 1.5` → `ceil(1.5)` = 2.
- Multi-period: not testing the SQL aggregate directly here (that's integration); test the Python helper if extracted.

---

### NEW integration test: `apps/backend/tests/integration/memberships/test_freeze_race.py`

**Analog (exact mirror):** `tests/integration/visits/test_visits_concurrent.py` (lines 54-160).

**Mirror pattern** (D-25-23 / MEM-FRZ-TEST-03):
- Use `db_session_real_commit` fixture (NOT `db_session` SAVEPOINT) — concurrent INSERTs need real serialisation (visits test line 56-57 docstring).
- Seed user + client + plan + membership via real-commit session.
- `await app.state.redis.flushdb()` to avoid rate-limit bleed.
- Use `_build_authed_client(app)` style (visits test lines 39-51) to bypass SAVEPOINT-scoped fixtures.
- `asyncio.gather(*[_post() for _ in range(N)])` for N concurrent POST calls.
- Assert: exactly 1× 200 + (N-1)× 409 `already_frozen`.
- Assert: exactly 1 `membership_frozen` audit row + 0 (or N-1) audit rows for losing inserts (the losing branch raises before emit, so 0 expected).

**Invariant:** the test asserts the partial unique index `uq_membership_freeze_periods_active_per_membership` is the source-of-truth race winner, NOT app-layer logic (visits test line 60-66 docstring). This is the canonical Phase 19 visits race test pattern (`UNIQUE` index + IntegrityError translation).

---

### NEW integration test: `apps/backend/tests/integration/memberships/test_freeze_resolver.py`

**Analog:** `tests/integration/memberships/test_resolver.py`.

**Pattern** (D-25-23 / MEM-FRZ-06):
- Seed: client + plan + active membership.
- Call `POST /api/v1/memberships/{id}/freeze` → assert 200 + status=frozen.
- Call `resolve_active_membership_by_client` directly → assert returns None.
- Call `POST /api/v1/visits` (reception path) → assert 409 `no_active_membership`.
- Call Telegram `/checkin` simulator → assert generic Russian DM (no oracle leak — same DM as stranger / no-active path).

**Invariant:** the resolver path is **NOT** modified in Phase 25 (D-25-17). The test verifies that the existing `status='active'` filter naturally excludes frozen rows; if a future Phase 26 tiebreak refactor accidentally surfaces frozen rows, this test fails loudly.

---

### NEW integration tests (cycle / limit / cancel-during-freeze / endpoints)

**Analogs:**
- `test_freeze_cycle.py` — mirror `test_memberships_audit.py` (HTTP roundtrip + audit assertions) + `test_memberships_crud.py`.
- `test_freeze_limit.py` — mirror cancel-then-409 patterns in `test_memberships_audit.py`.
- `test_cancel_during_freeze.py` — mirror multi-event audit assertions in `test_memberships_audit.py`. Specifically assert BOTH `membership_unfrozen` (with `days_added=0`) AND `membership_cancelled` rows present in same UoW; `end_date` UNCHANGED from pre-freeze.
- `test_freeze_endpoints.py` — mirror `test_memberships_rbac.py` (RBAC matrix) + response-shape assertions on the 4 new fields.

**Shared fixtures** — use `make_plan` + `make_membership` from `tests/integration/memberships/conftest.py:187-256`. `make_membership` already supports `status="frozen"` override (line 235 `status: str = "active"` — caller passes any).

---

## Shared Patterns

### Authentication / RBAC

**Source:** `apps/backend/app/core/dependencies.py` — `require_permission(Action, Resource)`, `verify_csrf`, `CurrentUser`.
**Apply to:** Both new POST endpoints (`/freeze`, `/unfreeze`) — D-25-19.
**Pattern reference:** `cancel_membership` route (router.py:284-311); RBAC-04 ordering enforced by `tests/integration/test_route_introspection.py`.

```python
actor: Annotated[CurrentUser, Depends(require_permission(Action.CREATE, Resource.MEMBERSHIPS))],
_csrf: Annotated[None, Depends(verify_csrf)],
```

### Service-layer commit ordering (Phase 16 D-14 pattern, SVC001 gate)

**Source:** `apps/backend/app/modules/memberships/service.py:17-30` module docstring + `cancel_membership` flow (lines 394-449).
**Apply to:** All new public service functions (`freeze_membership`, `unfreeze_membership`).
**Pattern:**
```
load → guard → mutate (repository call) → flush (catch IntegrityError early) →
audit.emit (BEFORE commit, co-transactional D-14) → refresh updated_at →
session.commit() (SVC001 walker enforces presence)
```

**Test gate:** `tests/unit/test_service_commit_gate.py:167-211` — `_INSPECTED_SERVICES` includes `memberships/service.py`. Every new public mutation MUST end in `await session.commit()`.

### Audit emit (LITERAL strings + LOCKED_AUDIT_EVENTS)

**Source:** `apps/backend/app/core/audit.py:150-205` (`emit` signature) + `LOCKED_AUDIT_EVENTS` (lines 92-147 — already includes `("membership_frozen", "membership")` and `("membership_unfrozen", "membership")` per Phase 24 D-24-18).
**Apply to:** Two new callsites in `freeze_membership` + `unfreeze_membership` + extension in `cancel_membership` (frozen-source branch — `membership_unfrozen` with `days_added=0`).
**Pattern:**
```python
await audit.emit(
    session,
    "membership_frozen",         # LITERAL (Phase 15 INFRA-11 AST gate)
    actor_user_id=actor.id,
    resource_type="membership",  # LITERAL
    resource_id=membership.id,
    client_id=str(membership.client_id),  # str-cast for JSONB
    freeze_period_id=str(period.id),       # str-cast for JSONB
    started_at=period.started_at.isoformat(),
)
```

**Test gate:** `tests/unit/test_audit_taxonomy.py` (AST walker at lines 35-145) — both `event` and `resource_type` MUST be `ast.Constant(str)`. Pair MUST be in `LOCKED_AUDIT_EVENTS`.

### IntegrityError discrimination (constraint name)

**Source:** `apps/backend/app/modules/memberships/service.py:74-102` (`_is_plan_name_conflict`, `_is_plan_in_use_conflict`).
**Apply to:** `_is_already_frozen_conflict` for `uq_membership_freeze_periods_active_per_membership`.
**Pattern:** `getattr(exc.orig, "constraint_name", None)` first, substring fallback on `str(exc.orig)`.

### Migration constraint-name literal pinning

**Source:** `apps/backend/app/modules/memberships/models.py:113-114` (FK literal-ref'd) + `apps/backend/alembic/env.py:54-66` (`_include_object` exclusion).
**Apply to:** `uq_membership_freeze_periods_active_per_membership` — add to `_include_object` exclusion tuple.
**Pattern:** any constraint name referenced as a literal string in service code MUST also be excluded from autogenerate diff in `env.py` so `alembic check` stays clean.

### Time injection (Europe/Moscow + UTC)

**Source:** `apps/backend/app/modules/memberships/service.py:480-508` (`resolve_active_membership_by_client`, `today: date | None = None` injection) + `_expire_due_memberships` (lines 516-575) + `cancel_membership` line 428 (`datetime.now(tz=UTC)` for cancelled_at TIMESTAMPTZ).
**Apply to:** `freeze_membership` uses `datetime.now(tz=UTC)` for `started_at` (TIMESTAMPTZ); `today_msk` for limit-precondition uses `datetime.now(ZoneInfo("Europe/Moscow")).date()`.
**Pattern:** TIMESTAMPTZ columns store UTC wallclock; date() math uses Europe/Moscow zone. Default-args of `None` resolve to current zone for production; tests pass explicit values for determinism.

**Clock injection for tests** (D-25-24): existing pattern uses explicit `today` param + monkeypatch on private `_utc_now` helpers. Mirror Phase 19 visits race + Phase 18 ARQ tests. NO `freezegun` (Phase 24 D-24-06 precedent).

### Pagination envelope + camelCase wire format

**Source:** `apps/backend/app/core/schemas.py` — `BackendSchemaBase` (alias_generator) + `ResponseEnvelope` + `envelope()` + `apps/backend/app/core/pagination.py` — `PaginatedData`.
**Apply to:** all list/detail responses.
**Pattern:** `freeze_days_limit_snapshot` Python → `freezeDaysLimitSnapshot` JSON automatic via `BackendSchemaBase` alias_generator. NO manual aliasing.

### Test fixtures — SAVEPOINT vs real-commit

**Source:** `tests/integration/memberships/conftest.py:43-256` (SAVEPOINT-mode `db_session` + `make_plan` + `make_membership`) + `tests/integration/visits/test_visits_concurrent.py:54-66` docstring (real-commit rationale).
**Apply to:**
- Cycle / limit / endpoints / cancel-during-freeze / resolver tests → use SAVEPOINT-mode `db_session` + existing `authed_client_owner`/`_reception` + `make_plan`/`make_membership`.
- Race test → use `db_session_real_commit` + custom `_build_authed_client` (visits pattern).

---

## No Analog Found

None — every Phase 25 artifact has either an exact analog or a partial role-match analog within the existing v1.2 / Phase 24 backend codebase. Novel SQL (`compute_freeze_days_used` aggregate, `_freeze_days_used_subquery` LEFT JOIN) is sufficiently constrained by the surrounding repository patterns and CONTEXT.md D-25-16/D-25-18 specifications.

---

## Cross-Phase Invariants (planner MUST preserve)

1. **SVC001 commit-gate** (`tests/unit/test_service_commit_gate.py:167-211`): every public service mutation in `memberships/service.py` MUST end with `await session.commit()`. NO opt-out via `# noqa: SVC001 caller-owns-txn` for public paths (only valid on `_`-prefixed private helpers per Phase 15 INFRA-13).

2. **AST literal-string audit gate** (`tests/unit/test_audit_taxonomy.py`): every `audit.emit(...)` MUST pass `event` and `resource_type` as `ast.Constant(str)`. Pair MUST be in `LOCKED_AUDIT_EVENTS` (Phase 24 D-24-18 already pre-registered the 6 v1.3 pairs — Phase 25 only adds callsites).

3. **NAMING_CONVENTION** (`apps/backend/app/core/database.py:28-34`): all constraints named via `op.f(...)` in migrations and short-form name in `__table_args__`. Literal-pinned constraint names MUST be excluded in `alembic/env.py:_include_object` (currently excludes `uq_membership_plans_name_alive`; Phase 25 adds `uq_membership_freeze_periods_active_per_membership`).

4. **Partial unique index — `op.execute()` not declarative** (`0004_membership_plans.py:62-65`): `WHERE`-predicate unique indexes are not autogenerate-stable; install via raw SQL in migration AND mirror in `__table_args__` `Index(unique=True, postgresql_where=text(...))` for ORM awareness.

5. **RBAC-04 ordering** (`router.py:40-45` docstring + `tests/integration/test_route_introspection.py`): in mutation endpoint signatures, `Depends(require_permission(...))` MUST be declared BEFORE `Depends(verify_csrf)`. 401 → 403 ordering preserved.

6. **Caller-owns-txn for repository** (`repository.py:12-14` module docstring): NO `session.commit()` or `session.flush()` calls in `repository.py`. The service layer owns the transactional moment so audit row co-writes in the same UoW.

7. **Audit ordering for cancel-during-freeze** (REQUIREMENTS MEM-FRZ-07 + D-25-09): `membership_unfrozen` audit row MUST be emitted BEFORE `membership_cancelled` audit row in the same UoW. `audit_log.id` auto-increment ordering provides forensic chronology.

8. **Resolver — NO touch in Phase 25** (D-25-17): `find_active_for_client` (repository.py:316-352) and `resolve_active_membership_by_client` (service.py:480-508) MUST NOT be modified. Frozen rows excluded by existing `status='active'` predicate. Phase 24/25/26 each touch the resolver in serialised, controlled ways — Phase 25's contribution is "ZERO resolver code".

9. **Telegram oracle-safe DM** (Phase 20 D-5 + REQUIREMENTS MEM-FRZ-06): frozen membership → reception 409 `no_active_membership`; Telegram `/checkin` → generic Russian DM (same DM as stranger / no-active path). NO new copy strings needed in Phase 25.

10. **Migration chain** (D-25-01): `0007_status_taxonomy` → `0008_freeze` (Phase 25). Phase 26 will create `0009_renewal` revising from `0008_freeze`. Plan agent MUST update the milestone roadmap line claiming Phase 25/26 share migration `0007` (now stale post-Phase 24's `0007_status_taxonomy.py`).

---

## Metadata

**Analog search scope:**
- `apps/backend/app/modules/memberships/` (full module)
- `apps/backend/app/core/{audit,exceptions,database,schemas}.py`
- `apps/backend/alembic/versions/0004_..0007_*.py` + `alembic/env.py`
- `apps/backend/tests/{unit,integration}/memberships/`
- `apps/backend/tests/integration/visits/test_visits_concurrent.py` (race test analog)
- `apps/backend/tests/unit/{test_audit_taxonomy,test_service_commit_gate}.py` (CI gate analogs)
- `apps/backend/app/integrations/telegram/handlers.py` (oracle-safe DM context)
- `apps/backend/app/modules/visits/service.py:150-180` (resolver `NoActiveMembershipError` raise site)

**Files scanned:** 16 source files + 7 test files
**Pattern extraction date:** 2026-05-08
**Project skills:** none (no `.claude/skills/` or `.agents/skills/` directories present)
**CLAUDE.md applied:** root `./CLAUDE.md` conventions (modular monolith, SQLAlchemy 2.0 async, Pydantic v2, ruff/mypy strict, import-linter, BackendSchemaBase camelCase wire format, audit ordering)
