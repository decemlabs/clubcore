# Phase 34: PT-Session Recording — Pattern Map

**Mapped:** 2026-05-16
**Files analyzed:** 14 (8 new module files + 1 migration + 1 importlinter + 1 permissions amendment + 1 core deps amendment + 1 admin-web amendment + tests)
**Analogs found:** 14 / 14 (every new file has a strong analog in v1.4 codebase)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `apps/backend/alembic/versions/0015_pt_sessions.py` | migration | DDL | `apps/backend/alembic/versions/0014_pt_packages.py` | exact |
| `apps/backend/app/modules/pt_sessions/__init__.py` | module marker | — | `apps/backend/app/modules/pt_packages/__init__.py` | exact |
| `apps/backend/app/modules/pt_sessions/constants.py` | constants | — | `apps/backend/app/modules/pt_packages/constants.py` | role-match (no FSM, just numeric windows) |
| `apps/backend/app/modules/pt_sessions/models.py` | ORM model | — | `apps/backend/app/modules/pt_packages/models.py` (`PtPackage` class) | exact |
| `apps/backend/app/modules/pt_sessions/repository.py` | repository | CRUD + raw SQL UPDATE…RETURNING | `apps/backend/app/modules/pt_packages/repository.py` + `apps/backend/app/modules/visits/repository.py` (for race-safe UPDATE) | hybrid (CRUD from pt_packages; race-safe SQL pattern via visits + Phase 33 `expire_due_pt_packages_bulk_returning`) |
| `apps/backend/app/modules/pt_sessions/schemas.py` | DTO/schemas | — | `apps/backend/app/modules/pt_packages/schemas.py` | exact |
| `apps/backend/app/modules/pt_sessions/service.py` | service orchestrator | request-response (record) + cross-table balance mutation (cancel) | `apps/backend/app/modules/pt_packages/service.py` (`create_pt_package`, `cancel_pt_package`, `refund_pt_package`) + `apps/backend/app/modules/memberships/service.py` (`refund_membership`) + `apps/backend/app/modules/visits/service.py` (`_create_visit_with_anti_fraud` race-safe insert+UNIQUE pattern) | hybrid |
| `apps/backend/app/modules/pt_sessions/router.py` | HTTP router | request-response | `apps/backend/app/modules/pt_packages/router.py` (`create_pt_package`, `cancel_pt_package`, `refund_pt_package` handlers) | exact (idempotency two-phase Redis pattern verbatim) |
| `apps/backend/app/modules/pt_sessions/permissions.py` | permissions stub | — | `apps/backend/app/modules/memberships/` (no permissions.py — declared inline) | precedent: empty stub OR absent (Claude's discretion per D-34-03) |
| `apps/backend/app/api/v1/router.py` (modification) | router aggregator | — | self (existing file, add include lines for `pt_sessions_router` + `package_scoped_router`) | exact (existing pt_packages include pattern at lines 39, 35) |
| `apps/backend/app/main.py` (no modification per D-34-13a) | composition root | — | self (verify: no new resolver registration, only `app.include_router(api)` continues to work via aggregator) | n/a |
| `apps/backend/app/core/dependencies.py` (amendment) | Protocol slot extension (D-34-12a) | — | `apps/backend/app/core/dependencies.py:280-285` self (add `full_name: str` field to `TrainerById` Protocol) | self-edit |
| `apps/backend/app/core/permissions.py` (amendment, D-34-09a) | RBAC matrix | — | `apps/backend/app/core/permissions.py:88` (remove `(Action.CANCEL, Resource.PT_SESSIONS)` line) | self-edit |
| `apps/backend/.importlinter` (amendment, D-34-14) | architectural contract | — | `.importlinter:13-27` (add `app.modules.pt_sessions` as 12th module) | self-edit |
| `apps/admin-web/src/shared/session/can.ts` (amendment, D-34-19) | RBAC mirror | — | `apps/admin-web/src/shared/session/can.ts:42` (remove `{ action: 'cancel', resource: 'pt-sessions' }` line for byte-parity) | self-edit |
| `apps/backend/tests/integration/pt_sessions/test_*.py` (NEW) | integration tests | request-response | `apps/backend/tests/integration/pt_packages/test_pt_package_sale.py`, `test_pt_package_cancel.py`, `test_pt_package_refund_race.py` | exact |
| `apps/backend/tests/unit/pt_sessions/test_*.py` (NEW) | unit tests | — | `apps/backend/tests/unit/pt_packages/test_state_machine.py`, `test_plan_immutability.py` | role-match (no FSM table, but boundary-math tests for windows) |

---

## Pattern Assignments

### `apps/backend/alembic/versions/0015_pt_sessions.py` (migration, DDL)

**Analog:** `apps/backend/alembic/versions/0014_pt_packages.py`

**Header pattern** (0014 lines 1–38):
```python
"""pt_sessions

Revision ID: 0015_pt_sessions
Revises: 0014_pt_packages
Create Date: 2026-05-16 ...

Phase 34 PT-14 — PT-session row (one per recorded training).
"""
from collections.abc import Sequence
import sqlalchemy as sa
from sqlalchemy import text
from alembic import op

revision: str = "0015_pt_sessions"
down_revision: str | None = "0014_pt_packages"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```

**`op.create_table` pattern with FK ON DELETE RESTRICT + named CHECK constraints** (0014 lines 41–114):
```python
op.create_table(
    "pt_sessions",
    sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
    sa.Column("pt_package_id", sa.UUID(), nullable=False),
    sa.Column("trainer_id", sa.UUID(), nullable=False),
    sa.Column("client_id", sa.UUID(), nullable=False),
    sa.Column("performed_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("performed_by_user_id", sa.UUID(), nullable=False),
    sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("cancel_reason", sa.Text(), nullable=True),
    sa.Column("trainer_name_snapshot", sa.Text(), nullable=False),
    sa.Column("notes", sa.Text(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.CheckConstraint(
        "cancel_reason IS NULL OR cancelled_at IS NOT NULL",
        name=op.f("ck_pt_sessions_cancel_reason_requires_cancelled_at"),
    ),
    sa.CheckConstraint(
        "cancel_reason IS NULL OR char_length(cancel_reason) <= 200",
        name=op.f("ck_pt_sessions_cancel_reason_length"),
    ),
    sa.CheckConstraint(
        "notes IS NULL OR char_length(notes) <= 500",
        name=op.f("ck_pt_sessions_notes_length"),
    ),
    sa.PrimaryKeyConstraint("id", name=op.f("pk_pt_sessions")),
    sa.ForeignKeyConstraint(
        ["pt_package_id"], ["pt_packages.id"],
        name=op.f("fk_pt_sessions_pt_package_id_pt_packages"),
        ondelete="RESTRICT",
    ),
    sa.ForeignKeyConstraint(
        ["trainer_id"], ["trainers.id"],
        name=op.f("fk_pt_sessions_trainer_id_trainers"),
        ondelete="RESTRICT",
    ),
    sa.ForeignKeyConstraint(
        ["client_id"], ["clients.id"],
        name=op.f("fk_pt_sessions_client_id_clients"),
        ondelete="RESTRICT",
    ),
    sa.ForeignKeyConstraint(
        ["performed_by_user_id"], ["users.id"],
        name=op.f("fk_pt_sessions_performed_by_user_id_users"),
        ondelete="RESTRICT",
    ),
)
```

**Composite-index pattern** (0014 lines 117–126):
```python
op.create_index(
    "ix_pt_sessions_pt_package_id_performed_at_desc",
    "pt_sessions",
    ["pt_package_id", sa.text("performed_at DESC")],
)
op.create_index(
    "ix_pt_sessions_trainer_id_performed_at_desc",
    "pt_sessions",
    ["trainer_id", sa.text("performed_at DESC")],
)
```

**Mirror what:** revision header style, named-CHECK pattern, FK `ON DELETE RESTRICT`, `op.f()` naming, server_default UUID + now().
**Adapt what:** no partial UNIQUE (D-34-02 — no "active per client" invariant for sessions); no status column (cancellation is single-row `cancelled_at IS NOT NULL`); 4 FKs (not 2) for `pt_package_id` / `trainer_id` / `client_id` / `performed_by_user_id`; 2 composite indexes (not 4 single-col).

---

### `apps/backend/app/modules/pt_sessions/__init__.py` (module marker)

**Analog:** `apps/backend/app/modules/pt_packages/__init__.py`

**Pattern** (full file, 14 lines):
```python
"""PT-sessions module (Phase 34 PT-14..22).

Module marker. Phase 34 introduces ZERO new Protocol slots in
`core.dependencies` (D-34-13a — resolver-only consumer of TrainerById +
ActivePtPackage; no `register_pt_session_*` calls in `app.main.create_app`).
"""
```

**Mirror what:** docstring shape.
**Adapt what:** NO `__all__` re-export (pt_sessions exports nothing to composition root per D-34-13a — `pt_packages.__init__` re-exports `resolve_active_pt_package` because Phase 33 wired a resolver; Phase 34 wires none).

---

### `apps/backend/app/modules/pt_sessions/constants.py` (constants)

**Analog:** `apps/backend/app/modules/pt_packages/constants.py` (general shape) — but content is closer to Phase 19 `app/modules/visits/service.py` gym-hours window numerics.

**Pattern:**
```python
"""PT-sessions module constants (Phase 34 D-34-06 / D-34-07).

NO FSM — single-row mutation only (cancelled_at set on cancel). Numeric
window constants live here so service tests can import them without
spinning up DB.
"""
BACKDATING_WINDOW_DAYS_RECEPTION = 7  # B-11
CANCEL_WINDOW_HOURS_RECEPTION = 24    # B-12
MAX_NOTES_CHARS = 500                 # D-34-02 (mirror migration CHECK)
MAX_CANCEL_REASON_CHARS = 200         # D-34-02 (mirror migration CHECK)

__all__ = [
    "BACKDATING_WINDOW_DAYS_RECEPTION",
    "CANCEL_WINDOW_HOURS_RECEPTION",
    "MAX_NOTES_CHARS",
    "MAX_CANCEL_REASON_CHARS",
]
```

**Mirror what:** module docstring referencing decision IDs; `__all__` discipline; no cross-module imports (modules-independent).
**Adapt what:** NO `*_STATUS_TRANSITIONS` MappingProxyType (D-34-03 — no local FSM); NO `CANCELLATION_REASON_REFUNDED` sentinel (no refund flow on sessions); NO `PAYMENT_SUBJECT_KIND_*` literal (sessions don't insert payments).

---

### `apps/backend/app/modules/pt_sessions/models.py` (ORM model)

**Analog:** `apps/backend/app/modules/pt_packages/models.py` (`PtPackage` class, lines 90–172)

**Composition pattern** (lines 39–58):
```python
from __future__ import annotations
from datetime import date, datetime
from uuid import UUID as UUIDType

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base, TimestampMixin, UUIDPkMixin
```

**Class pattern** (lines 90–172; D-34-02 column list):
```python
class PtSession(Base, UUIDPkMixin, TimestampMixin):
    """PT-session row (Phase 34 PT-14).

    NO SoftDeleteMixin — lifecycle is single-cancel via cancelled_at column
    (D-34-02; mirrors PtPackage D-33-03 status-only pattern).

    NB: This ORM is the ONLY direct PtPackage cross-reference allowed; balance
    mutations on `pt_packages.sessions_remaining` are performed via raw
    `text()` SQL in pt_sessions.repository (D-34-04a) so that this module's
    files NEVER `from app.modules.pt_packages import ...` — the
    modules-independent importlinter contract is preserved.
    """
    __tablename__ = "pt_sessions"

    pt_package_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("pt_packages.id", ondelete="RESTRICT",
                   name="fk_pt_sessions_pt_package_id_pt_packages"),
        nullable=False,
    )
    trainer_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("trainers.id", ondelete="RESTRICT",
                   name="fk_pt_sessions_trainer_id_trainers"),
        nullable=False,
    )
    client_id: Mapped[UUIDType] = mapped_column(...)
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    performed_by_user_id: Mapped[UUIDType] = mapped_column(...)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    trainer_name_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "cancel_reason IS NULL OR cancelled_at IS NOT NULL",
            name="cancel_reason_requires_cancelled_at",
        ),
        CheckConstraint(
            "cancel_reason IS NULL OR char_length(cancel_reason) <= 200",
            name="cancel_reason_length",
        ),
        CheckConstraint(
            "notes IS NULL OR char_length(notes) <= 500",
            name="notes_length",
        ),
        Index("ix_pt_sessions_pt_package_id_performed_at_desc",
              "pt_package_id", text("performed_at DESC")),
        Index("ix_pt_sessions_trainer_id_performed_at_desc",
              "trainer_id", text("performed_at DESC")),
    )
```

**Mirror what:** `Base + UUIDPkMixin + TimestampMixin` composition (no SoftDeleteMixin); `__future__ annotations` for PaginatedData generic; ForeignKey with explicit `name=` matching migration; CheckConstraint `name=` un-prefixed (NAMING_CONVENTION prepends `ck_pt_sessions_`); raw `text("performed_at DESC")` index expression.
**Adapt what:** 5 nullable / 5 NOT NULL split per D-34-02; no `status` column; no `start_date`/`end_date`; the `trainer_name_snapshot` IS the B-05 column captured at insert.

---

### `apps/backend/app/modules/pt_sessions/repository.py` (repository, CRUD + raw SQL UPDATE…RETURNING)

**Primary analog (CRUD shape):** `apps/backend/app/modules/pt_packages/repository.py`
**Secondary analog (race-safe UPDATE…RETURNING):** `apps/backend/app/modules/pt_packages/repository.py:338-368` (`expire_due_pt_packages_bulk_returning`) AND `apps/backend/app/modules/visits/service.py:177-197` (insert+IntegrityError pattern; conceptually distinct but same "DB is sole arbiter" discipline).

**Header pattern** (pt_packages/repository.py lines 1–46):
```python
"""PT-sessions repository — single point of access to the PtSession ORM.

This is the ONLY module in the codebase that imports the PtSession ORM
model from `pt_sessions.models`. Cross-module reads (pt_packages metadata)
and cross-module writes (sessions_remaining decrement/increment, status
flip exhausted↔active) go through raw `sa.text()` SQL strings — D-34-04a
keeps the modules-independent importlinter contract clean without an
ORM import.

Transaction control: NO `session.commit()` and NO `session.flush()` here
(mirror memberships D-14, pt_packages D-33 caller-owns-txn). The service
layer owns the UoW so it can co-write audit_log in the same transaction.
"""
from __future__ import annotations
from datetime import datetime
from uuid import UUID
import sqlalchemy as sa
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PaginatedData
from app.modules.pt_sessions.models import PtSession
from app.modules.pt_sessions.schemas import PtSessionListByPackageQuery
```

**Race-safe atomic decrement pattern (D-34-04a) — raw text() SQL with predicate gate:**

Based on `pt_packages/repository.py:expire_due_pt_packages_bulk_returning` (lines 338–368) but adapted to single-row decrement:
```python
async def atomic_decrement_pt_package(
    session: AsyncSession, pt_package_id: UUID
) -> int | None:
    """Race-safe decrement of pt_packages.sessions_remaining (PT-16 / D-34-04a).

    Returns new sessions_remaining on success; None on 0-row update (caller
    raises 409 pt_package_exhausted). The predicate
    ``sessions_remaining > 0 AND status='active'`` makes this UPDATE the SOLE
    arbiter — concurrent callers serialise at the row lock and the loser
    sees 0 rows updated.

    Raw text() SQL avoids importing `pt_packages.models.PtPackage` (would
    break modules-independent importlinter contract). The migration
    0014_pt_packages CHECK `sessions_remaining >= 0` is defence-in-depth.
    """
    stmt = sa.text(
        """
        UPDATE pt_packages
        SET sessions_remaining = sessions_remaining - 1,
            updated_at = now()
        WHERE id = :pt_package_id
          AND sessions_remaining > 0
          AND status = 'active'
        RETURNING sessions_remaining
        """  # noqa: TABLE_REF cross-module SQL per D-34-04a
    )
    result = await session.execute(stmt, {"pt_package_id": pt_package_id})
    row = result.first()
    return None if row is None else int(row[0])


async def atomic_increment_pt_package(
    session: AsyncSession, pt_package_id: UUID
) -> int | None:
    """Race-safe increment on cancel; predicate is defence-in-depth ceiling
    (`sessions_remaining < session_count_snapshot`).

    Returns new sessions_remaining; None is a hard logic error (CHECK
    invariant breach) and caller MUST raise 500.
    """
    stmt = sa.text(
        """
        UPDATE pt_packages
        SET sessions_remaining = sessions_remaining + 1,
            updated_at = now()
        WHERE id = :pt_package_id
          AND sessions_remaining < session_count_snapshot
        RETURNING sessions_remaining, status
        """  # noqa: TABLE_REF cross-module SQL per D-34-04a
    )
    result = await session.execute(stmt, {"pt_package_id": pt_package_id})
    row = result.first()
    return None if row is None else int(row[0])


async def atomic_transition_to_exhausted(
    session: AsyncSession, pt_package_id: UUID
) -> bool:
    """Flip status='active' → 'exhausted' inside the same UoW that just
    consumed the last session (D-34-05). Predicate `WHERE status='active'`
    guards against a concurrent refund flipping to cancelled mid-tx —
    the PT_PACKAGE_STATUS_TRANSITIONS FSM permits active→exhausted only.
    """
    stmt = sa.text(
        """
        UPDATE pt_packages
        SET status = 'exhausted', updated_at = now()
        WHERE id = :pt_package_id AND status = 'active'
        """  # noqa: TABLE_REF cross-module SQL per D-34-04a
    )
    result = await session.execute(stmt, {"pt_package_id": pt_package_id})
    return result.rowcount == 1


async def atomic_transition_exhausted_to_active(
    session: AsyncSession, pt_package_id: UUID
) -> bool:
    """Reverse transition exhausted→active (D-34-11a carve-out).

    NOT in the global PT_PACKAGE_STATUS_TRANSITIONS FSM (Phase 33 D-33-04 is
    forward-only). The predicate `WHERE status='exhausted'` is the controlled
    invariant: pt_sessions.cancel_pt_session has just freed one balance unit
    against an exhausted package, so the reverse flip is safe under that
    locally-scoped precondition. Document the carve-out in service.py
    docstring.
    """
    stmt = sa.text(
        """
        UPDATE pt_packages
        SET status = 'active', updated_at = now()
        WHERE id = :pt_package_id AND status = 'exhausted'
        """  # noqa: TABLE_REF cross-module SQL per D-34-04a
    )
    result = await session.execute(stmt, {"pt_package_id": pt_package_id})
    return result.rowcount == 1


async def fetch_pt_package_metadata(
    session: AsyncSession, pt_package_id: UUID
) -> dict[str, object] | None:
    """SELECT id, client_id, status, sessions_remaining, end_date FROM
    pt_packages WHERE id=:id (D-34-13a — direct read instead of consuming
    the client_id→active-package Protocol slot, which doesn't fit the
    id-as-input signature).

    Returns dict (NOT the PtPackage ORM) to keep the cross-module surface
    flat. None = pt_package_not_found.
    """
    stmt = sa.text(
        """
        SELECT id, client_id, status, sessions_remaining, end_date
        FROM pt_packages WHERE id = :pt_package_id
        """  # noqa: TABLE_REF cross-module SQL per D-34-04a
    )
    result = await session.execute(stmt, {"pt_package_id": pt_package_id})
    row = result.mappings().first()
    return dict(row) if row is not None else None
```

**Local CRUD helpers (pt_sessions table — full ORM use, no `text()`):**

Pattern from `pt_packages/repository.py:get_pt_package` (lines 171–185) and `list_pt_packages_paginated` (lines 280–330):
```python
async def get_pt_session(session: AsyncSession, pt_session_id: UUID) -> PtSession | None:
    stmt: Select[tuple[PtSession]] = select(PtSession).where(PtSession.id == pt_session_id)
    return await session.scalar(stmt)


async def list_by_pt_package_paginated(
    session: AsyncSession, pt_package_id: UUID, query: PtSessionListByPackageQuery,
) -> PaginatedData[PtSession]:
    """Mirror pt_packages.list_pt_packages_paginated; orders by performed_at
    DESC matching ix_pt_sessions_pt_package_id_performed_at_desc index."""
    predicates: list[Any] = [PtSession.pt_package_id == pt_package_id]
    if not query.include_cancelled:
        predicates.append(PtSession.cancelled_at.is_(None))
    ...
    stmt = stmt.order_by(
        PtSession.performed_at.desc(),
        PtSession.created_at.desc(),
        PtSession.id.desc(),
    )
    ...
    return PaginatedData.model_construct(items=list(rows), total=total, page=..., page_size=...)


async def insert_pt_session(session: AsyncSession, *, pt_package_id, trainer_id, client_id,
                             performed_at, performed_by_user_id, trainer_name_snapshot,
                             notes) -> PtSession:
    """Insert pt_sessions row; caller MUST flush + commit."""
    pt_session = PtSession(...)
    session.add(pt_session)
    return pt_session


async def mark_cancelled(
    session: AsyncSession, pt_session: PtSession, *, cancel_reason: str,
) -> PtSession:
    """Narrow setter (mirror pt_packages.update_pt_package_status pattern)."""
    pt_session.cancelled_at = datetime.now(tz=UTC)
    pt_session.cancel_reason = cancel_reason
    return pt_session
```

**Mirror what:** caller-owns-txn (no flush/commit); `Select[tuple[PtSession]]` typing; `PaginatedData.model_construct(...)` over ORM rows; soft-delete-style absence (no `deleted_at` column).
**Adapt what:** raw `text()` SQL string literals for cross-module mutations + the `# noqa: TABLE_REF cross-module SQL` grep marker (D-34-04a); `fetch_pt_package_metadata` returns `dict` not ORM (cross-module surface flat); NO ORM import of `PtPackage`.

---

### `apps/backend/app/modules/pt_sessions/schemas.py` (DTOs)

**Analog:** `apps/backend/app/modules/pt_packages/schemas.py`

**Imports + base** (pt_packages/schemas.py lines 25–35):
```python
from __future__ import annotations
from datetime import datetime
from uuid import UUID
from pydantic import Field, field_validator

from app.core.pagination import PageQuery
from app.core.schemas import BackendSchemaBase, ResponseData
```

**Request schemas pattern** (pt_packages/schemas.py lines 149–181):
```python
class PtSessionCreateRequest(BackendSchemaBase):
    """POST /api/v1/pt-sessions body (PT-15 / D-34-06).

    `extra='forbid'` inherited from BackendSchemaBase. Server-validates
    trainer existence/active (Protocol slot) and performed_at backdating
    window (B-11) AFTER schema parses.
    """
    pt_package_id: UUID
    trainer_id: UUID
    performed_at: datetime  # ISO-8601 with offset; backdating window enforced server-side
    notes: str | None = Field(default=None, max_length=500)


class PtSessionCancelRequest(BackendSchemaBase):
    """POST /api/v1/pt-sessions/{id}/cancel body (PT-18 / D-34-07).

    `extra='forbid'`. `cancel_reason` REQUIRED 1..200 (mirrors
    PtPackageCancelRequest 1..200 length bounds).
    """
    cancel_reason: str = Field(min_length=1, max_length=200)


class PtSessionListByPackageQuery(PageQuery):
    """GET /api/v1/pt-packages/{id}/sessions query (D-34-08)."""
    include_cancelled: bool = True  # D-34-08 default: show all (UI/operator filters)


class PtSessionResponse(ResponseData):
    """Outbound representation of a PtSession (D-34-08)."""
    id: UUID
    pt_package_id: UUID
    trainer_id: UUID
    client_id: UUID
    performed_at: datetime
    performed_by_user_id: UUID
    cancelled_at: datetime | None
    cancel_reason: str | None
    trainer_name_snapshot: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
```

**Mirror what:** `BackendSchemaBase` for inputs (camelCase wire ↔ snake_case Python + `extra='forbid'`); `ResponseData` for outputs; `PageQuery` for list queries; `Field(max_length=...)` mirrors DB CHECK constraints (defence-in-depth).
**Adapt what:** NO enum (no status column); NO computed_field `is_active` (use `cancelled_at` directly); body schemas REJECT `amountKopecks` / `clientId` (server derives client_id from pt_package row per D-34-13a — body has only `pt_package_id`).

---

### `apps/backend/app/modules/pt_sessions/service.py` (orchestrator)

**Primary analog (sale-flow shape):** `apps/backend/app/modules/pt_packages/service.py:create_pt_package` (lines 457–616).
**Secondary analog (cancel-flow shape):** `apps/backend/app/modules/pt_packages/service.py:cancel_pt_package` (lines 726–813) + `apps/backend/app/modules/memberships/service.py:refund_membership` (lines 690–802).
**Tertiary analog (rejection-emit-commit pattern for race-loser audit):** `apps/backend/app/modules/visits/service.py:_create_visit_with_anti_fraud` (lines 106–212) — though Phase 34 chooses NOT to emit on race-loser (D-34-04a: just raise 409, no rejection audit).

**Imports + module docstring pattern** (pt_packages/service.py lines 1–69):
```python
"""PT-sessions service — orchestration between router and repository (Phase 34).

PT-sessions are orthogonal to visits (PT-20 / Q3 default): recording does NOT
INSERT into visits; check-in does NOT INSERT into pt_sessions. Enforced by
ABSENCE — no service code in this file touches visits.

D-34-11a carve-out: `cancel_pt_session` performs a reverse transition
`exhausted → active` on the parent pt_package via raw `text()` SQL
predicate-gated UPDATE. This bypass is NOT in the global
PT_PACKAGE_STATUS_TRANSITIONS FSM (Phase 33 D-33-04 forward-only). The
locally-scoped invariant "we just freed one balance unit from an
exhausted package" makes the reverse flip safe under
`WHERE status='exhausted'`.

D-34-04a: ALL cross-module SQL against pt_packages uses raw `text()` from
pt_sessions.repository (NEVER `from app.modules.pt_packages import ...`)
to keep modules-independent importlinter contract clean.

Discipline invariants (Phase 30 walkers must remain green):
  - SVC001 caller-owns-txn (test_service_commit_gate): every public
    mutating orchestrator MUST end with `await session.commit()`.
  - audit.emit literal-string AST gate (INFRA-11 / test_audit_taxonomy):
    every emit() call uses literal strings for `event` and `resource_type`.
  - audit_payloads.py extra='forbid' validation (D-30-03): emit kwargs
    MUST match PtSessionRecordedPayload / PtSessionCancelledPayload /
    PtPackageExhaustedPayload schemas verbatim.
"""
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.dependencies import CurrentUser, resolve_trainer_by_id
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError, ForbiddenError
from app.core.pagination import PaginatedData
from app.core.permissions import Role
from app.modules.pt_sessions import repository
from app.modules.pt_sessions.constants import (
    BACKDATING_WINDOW_DAYS_RECEPTION,
    CANCEL_WINDOW_HOURS_RECEPTION,
)
from app.modules.pt_sessions.schemas import (
    PtSessionCancelRequest, PtSessionCreateRequest, PtSessionListByPackageQuery,
    PtSessionResponse,
)
```

**Error-class pattern** (pt_packages/service.py lines 76–146):
```python
class PtSessionNotFoundError(NotFoundError):
    code = "pt_session_not_found"
    status_code = 404


class PtPackageNotFoundError(NotFoundError):
    code = "pt_package_not_found"
    status_code = 404


class PtPackageNotActiveError(ConflictError):
    """Raised when fetch_pt_package_metadata returns status != 'active'
    (pre-decrement guard; race-loser uses PtPackageExhaustedError)."""
    code = "pt_package_not_active"
    status_code = 409


class PtPackageExhaustedError(ConflictError):
    """Raised when atomic_decrement_pt_package returns None (PT-16 / D-34-04a
    race-loser)."""
    code = "pt_package_exhausted"
    status_code = 409


class TrainerNotFoundError(NotFoundError):
    code = "trainer_not_found"
    status_code = 404


class TrainerInactiveError(ValidationAppError):
    code = "trainer_inactive"
    status_code = 422


class PerformedAtInFutureError(ValidationAppError):
    code = "performed_at_in_future"
    status_code = 422


class PerformedAtOutOfWindowError(ValidationAppError):
    code = "performed_at_out_of_window"
    status_code = 422


class PtSessionAlreadyCancelledError(ConflictError):
    code = "already_cancelled"
    status_code = 409


class CancelWindowExpiredError(ForbiddenError):
    """403 not 409 — actor authorisation issue, not state conflict
    (D-34-07; mirrors OWNER_ONLY 403 mapping convention)."""
    code = "cancel_window_expired"
    status_code = 403
```

**`record_pt_session` orchestrator shape** (composite from pt_packages/service.py:`create_pt_package` lines 457–616 + decision D-34-05):
```python
async def record_pt_session(
    session: AsyncSession,
    actor: CurrentUser,
    data: PtSessionCreateRequest,
) -> PtSessionResponse:
    """Record a PT-session (PT-15 / PT-16 / PT-17). Reception+owner.

    10-step orchestrator (mirrors pt_packages.create_pt_package recipe):
      1. Validate performed_at — future-dated → 422 (D-34-06 / both roles);
         reception >7d back → 422.
      2. Fetch trainer via TrainerById Protocol slot — 404 / 422 inactive
         (D-34-12a; uses trainer.full_name for B-05 snapshot).
      3. fetch_pt_package_metadata (raw text() SELECT) — 404
         pt_package_not_found / 409 pt_package_not_active.
      4. atomic_decrement_pt_package (raw text() UPDATE...RETURNING) —
         None → 409 pt_package_exhausted (PT-16 race-loser path).
      5. insert_pt_session row with trainer_name_snapshot = trainer.full_name.
      6. session.flush() to surface FK errors.
      7. audit.emit('pt_session_recorded', ...) — payload matches
         PtSessionRecordedPayload extra='forbid' verbatim.
      8. If new_remaining == 0 → atomic_transition_to_exhausted + emit
         'pt_package_exhausted' once (D-34-05 / PT-17).
      9. session.commit() (SVC001 gate).
     10. Return PtSessionResponse.
    """
    # 1. performed_at window — both roles reject future; reception 7d past.
    now = datetime.now(UTC)
    delta = now - data.performed_at
    if delta.total_seconds() < 0:
        raise PerformedAtInFutureError("performed_at_in_future")
    if actor.role == Role.RECEPTION and delta > timedelta(days=BACKDATING_WINDOW_DAYS_RECEPTION):
        raise PerformedAtOutOfWindowError("performed_at_out_of_window")

    # 2. Trainer via Protocol slot (D-34-12a — full_name now on TrainerById).
    trainer = await resolve_trainer_by_id(session, data.trainer_id)
    if trainer is None:
        raise TrainerNotFoundError("trainer_not_found")
    if not trainer.is_active:
        raise TrainerInactiveError("trainer_inactive")

    # 3. pt_package metadata (D-34-13a raw SQL — slot doesn't fit id-input).
    pkg = await repository.fetch_pt_package_metadata(session, data.pt_package_id)
    if pkg is None:
        raise PtPackageNotFoundError("pt_package_not_found")
    if pkg["status"] != "active":
        raise PtPackageNotActiveError("pt_package_not_active")

    # 4. Race-safe decrement (PT-16 / D-34-04a). 0-row = 409 exhausted.
    new_remaining = await repository.atomic_decrement_pt_package(session, data.pt_package_id)
    if new_remaining is None:
        raise PtPackageExhaustedError("pt_package_exhausted")

    # 5. Insert + 6. flush (FK / CHECK surface).
    pt_session = await repository.insert_pt_session(
        session,
        pt_package_id=data.pt_package_id,
        trainer_id=data.trainer_id,
        client_id=pkg["client_id"],
        performed_at=data.performed_at,
        performed_by_user_id=actor.id,
        trainer_name_snapshot=trainer.full_name,  # B-05
        notes=data.notes,
    )
    await session.flush()

    # 7. Emit pt_session_recorded (LITERAL — INFRA-11 AST gate).
    await audit.emit(
        session,
        "pt_session_recorded",
        actor_user_id=actor.id,
        resource_type="pt_session",
        resource_id=pt_session.id,
        pt_session_id=str(pt_session.id),
        pt_package_id=str(data.pt_package_id),
        client_id=str(pkg["client_id"]),
        trainer_id=str(data.trainer_id),
        trainer_name_snapshot=trainer.full_name,
        performed_at=data.performed_at.isoformat(),
        performed_by_user_id=actor.id,
        sessions_remaining_after=new_remaining,
    )

    # 8. Auto-exhausted transition (D-34-05 / PT-17).
    if new_remaining == 0:
        await repository.atomic_transition_to_exhausted(session, data.pt_package_id)
        await audit.emit(
            session,
            "pt_package_exhausted",
            actor_user_id=actor.id,
            resource_type="pt_package",
            resource_id=data.pt_package_id,
            pt_package_id=str(data.pt_package_id),
            client_id=str(pkg["client_id"]),
            exhausted_at=datetime.now(UTC).isoformat(),
        )

    # 9. Commit (SVC001 gate).
    await session.commit()

    # 10. Return — refresh narrowed to created_at/updated_at (WR-04 lesson).
    await session.refresh(pt_session, attribute_names=["updated_at", "created_at"])
    return PtSessionResponse.model_validate(pt_session, from_attributes=True)
```

**`cancel_pt_session` orchestrator shape** (composite from pt_packages/service.py:`cancel_pt_package` lines 726–813 + decision D-34-11):
```python
async def cancel_pt_session(
    session: AsyncSession,
    actor: CurrentUser,
    pt_session_id: UUID,
    data: PtSessionCancelRequest,
) -> PtSessionResponse:
    """Cancel a recorded PT-session (PT-18 / D-34-07 / D-34-11a).

    Orchestrator owns the UoW. Sequence:
      1. Load session row — 404 pt_session_not_found / 409 already_cancelled.
      2. Cancel-window gate (D-34-07): reception >24h from `created_at`
         (NOT performed_at) → 403 cancel_window_expired; owner anytime.
      3. fetch_pt_package_metadata to capture prior_status (forensic).
      4. mark_cancelled (set cancelled_at + cancel_reason).
      5. atomic_increment_pt_package — defence-in-depth ceiling
         (sessions_remaining < session_count_snapshot). 0-row = hard logic
         error (raise 500).
      6. If prior status was 'exhausted' → atomic_transition_exhausted_to_active
         (D-34-11a predicate-gated reverse transition; FSM unchanged).
         If 'cancelled' or 'expired' → balance still incremented (data
         integrity), status STAYS terminal, package_reactivated=False.
      7. Flush.
      8. Emit 'pt_session_cancelled' with package_reactivated bool
         (payload matches PtSessionCancelledPayload extra='forbid').
      9. session.commit() (SVC001 gate).
     10. Return PtSessionResponse.
    """
    pt_session = await repository.get_pt_session(session, pt_session_id)
    if pt_session is None:
        raise PtSessionNotFoundError("pt_session_not_found")
    if pt_session.cancelled_at is not None:
        raise PtSessionAlreadyCancelledError("already_cancelled")

    # B-12 cancel-window from created_at (NOT performed_at — D-34-07).
    if actor.role == Role.RECEPTION:
        age = datetime.now(UTC) - pt_session.created_at
        if age > timedelta(hours=CANCEL_WINDOW_HOURS_RECEPTION):
            raise CancelWindowExpiredError("cancel_window_expired")

    pkg = await repository.fetch_pt_package_metadata(session, pt_session.pt_package_id)
    if pkg is None:
        raise PtPackageNotFoundError("pt_package_not_found")
    prior_status = pkg["status"]

    await repository.mark_cancelled(session, pt_session, cancel_reason=data.cancel_reason)
    new_remaining = await repository.atomic_increment_pt_package(session, pt_session.pt_package_id)
    if new_remaining is None:
        raise RuntimeError(
            f"atomic_increment_pt_package returned 0 rows for {pt_session.pt_package_id}; "
            "CHECK sessions_remaining <= session_count_snapshot invariant breached"
        )

    package_reactivated = False
    if prior_status == "exhausted":
        await repository.atomic_transition_exhausted_to_active(session, pt_session.pt_package_id)
        package_reactivated = True

    await session.flush()

    await audit.emit(
        session,
        "pt_session_cancelled",
        actor_user_id=actor.id,
        resource_type="pt_session",
        resource_id=pt_session.id,
        pt_session_id=str(pt_session.id),
        pt_package_id=str(pt_session.pt_package_id),
        client_id=str(pt_session.client_id),
        cancel_reason=data.cancel_reason,
        sessions_remaining_after=new_remaining,
        package_reactivated=package_reactivated,
    )

    await session.refresh(pt_session, attribute_names=["updated_at"])
    await session.commit()
    return PtSessionResponse.model_validate(pt_session, from_attributes=True)
```

**Read paths** (mirror `pt_packages/service.py:get_pt_package_by_id` + `list_pt_packages`):
```python
async def get_pt_session(session: AsyncSession, pt_session_id: UUID) -> PtSessionResponse:
    pt_session = await repository.get_pt_session(session, pt_session_id)
    if pt_session is None:
        raise PtSessionNotFoundError("pt_session_not_found")
    return PtSessionResponse.model_validate(pt_session, from_attributes=True)


async def list_sessions_by_pt_package(
    session: AsyncSession, pt_package_id: UUID, query: PtSessionListByPackageQuery,
) -> PaginatedData[PtSessionResponse]:
    page = await repository.list_by_pt_package_paginated(session, pt_package_id, query)
    return PaginatedData.model_construct(
        items=[PtSessionResponse.model_validate(s, from_attributes=True) for s in page.items],
        total=page.total, page=page.page, page_size=page.page_size,
    )
```

**Mirror what:** orchestrator recipe (load → guard → mutate → audit → commit); error-class hierarchy with `code` + `status_code`; LITERAL strings in `audit.emit` for INFRA-11 AST gate; `str(UUID)` cast for JSONB serialisability (Phase 32-02 deviation #1 lesson); `from_attributes=True` on response validate.
**Adapt what:** NO `_assert_can_transition` FSM helper (no local FSM per D-34-03); NO payment_recorder consumption (sessions don't insert payments, D-34); raw `text()` repository calls replace `update_pt_package_status` ORM mutations; cancel-window enforcement on `created_at` NOT `performed_at` (D-34-07).

---

### `apps/backend/app/modules/pt_sessions/router.py` (HTTP router)

**Analog:** `apps/backend/app/modules/pt_packages/router.py` (`create_pt_package` lines 207–300; `cancel_pt_package` lines 360–447 — two-phase Redis claim + replay pattern verbatim).

**Imports** (pt_packages/router.py lines 29–64):
```python
import base64, json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission, verify_csrf
from app.core.exceptions import ConflictError, ValidationAppError
from app.core.idempotency import (
    IDEMPOTENCY_REDIS_PREFIX, IDEMPOTENCY_TTL_SECONDS,
    begin_idempotency, body_sha256, load_idempotency_response, verify_idempotency,
)
from app.core.pagination import PaginatedData
from app.core.permissions import Action, Resource
from app.core.redis import get_redis
from app.core.schemas import ResponseEnvelope, envelope
from app.modules.pt_sessions import service
from app.modules.pt_sessions.schemas import (
    PtSessionCancelRequest, PtSessionCreateRequest,
    PtSessionListByPackageQuery, PtSessionResponse,
)

pt_sessions_router = APIRouter()
package_scoped_router = APIRouter()  # mounted at /pt-packages for GET /pt-packages/{id}/sessions
```

**POST handler with Idempotency-Key two-phase Redis claim + replay pattern** (pt_packages/router.py lines 207–300):
```python
@pt_sessions_router.post(
    "",
    response_model=ResponseEnvelope[PtSessionResponse],
    status_code=status.HTTP_201_CREATED,
    summary=(
        "Record a PT-session (reception+owner; 404 pt_package_not_found / "
        "trainer_not_found; 409 pt_package_not_active / pt_package_exhausted; "
        "422 trainer_inactive / performed_at_in_future / performed_at_out_of_window; "
        "requires Idempotency-Key — D-34-10)"
    ),
)
async def record_pt_session(
    payload: PtSessionCreateRequest,
    request: Request,
    actor: Annotated[CurrentUser, Depends(require_permission(Action.CREATE, Resource.PT_SESSIONS))],
    _csrf: Annotated[None, Depends(verify_csrf)],
    idempotency_key: Annotated[str, Depends(verify_idempotency)],
    redis: Annotated[Redis, Depends(get_redis)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Record a PT-session (PT-15).

    RBAC-04 ordering: auth → require_permission → verify_csrf → verify_idempotency → get_db.
    (CREATE, PT_SESSIONS) is NOT in OWNER_ONLY — reception + owner both receive 201.
    """
    incoming_body = await request.body()
    incoming_hash = body_sha256(incoming_body)

    is_first = await begin_idempotency(redis, idempotency_key)
    if not is_first:
        stored = await load_idempotency_response(redis, idempotency_key)
        if stored is None or isinstance(stored, str):
            raise ConflictError("idempotency_in_flight")
        if stored["body_hash"] != incoming_hash:
            raise ValidationAppError("idempotency_key_reuse")
        return Response(
            content=base64.b64decode(stored["body_b64"]),
            status_code=stored["status_code"],
            media_type="application/json",
        )

    pt_session = await service.record_pt_session(session, actor, payload)
    response_envelope = envelope(pt_session)
    body_bytes = json.dumps(
        response_envelope.model_dump(mode="json", by_alias=True),
        separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    envelope_json = json.dumps(
        {
            "status_code": status.HTTP_201_CREATED,
            "body_hash": incoming_hash,
            "body_b64": base64.b64encode(body_bytes).decode("ascii"),
        },
        separators=(",", ":"), ensure_ascii=False,
    )
    await redis.set(
        f"{IDEMPOTENCY_REDIS_PREFIX}{idempotency_key}",
        envelope_json, ex=IDEMPOTENCY_TTL_SECONDS,
    )
    return Response(
        content=body_bytes, status_code=status.HTTP_201_CREATED,
        media_type="application/json",
    )
```

**Cancel POST handler** — copy `pt_packages/router.py:cancel_pt_package` lines 360–447 verbatim, swap entities/permission. KEY: `(Action.CANCEL, Resource.PT_SESSIONS)` is NO LONGER in OWNER_ONLY after D-34-09a amendment, so reception receives 201 from the RBAC gate; service layer enforces the 24h cancel window and raises 403 `cancel_window_expired`.

**GET handlers** (pt_packages/router.py lines 303–344):
```python
@pt_sessions_router.get(
    "/{pt_session_id}",
    response_model=ResponseEnvelope[PtSessionResponse],
    summary="Read a single PT-session (reception+owner; 404 pt_session_not_found)",
)
async def get_pt_session(
    pt_session_id: UUID,
    _actor: Annotated[CurrentUser, Depends(require_permission(Action.VIEW, Resource.PT_SESSIONS))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PtSessionResponse]:
    return envelope(await service.get_pt_session(session, pt_session_id))


@package_scoped_router.get(
    "/{pt_package_id}/sessions",
    response_model=ResponseEnvelope[PaginatedData[PtSessionResponse]],
    summary="List PT-sessions for a package (reception+owner; paginated; ?includeCancelled)",
)
async def list_sessions_by_pt_package(
    pt_package_id: UUID,
    query: Annotated[PtSessionListByPackageQuery, Depends()],
    _actor: Annotated[CurrentUser, Depends(require_permission(Action.LIST, Resource.PT_SESSIONS))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PaginatedData[PtSessionResponse]]:
    """D-34-08: implementation lives in pt_sessions/router.py (subject-side
    ownership), URL path is rooted at /pt-packages/{id}/sessions via the
    package_scoped_router mounted at prefix='/pt-packages' in v1 aggregator."""
    page = await service.list_sessions_by_pt_package(session, pt_package_id, query)
    return envelope(page)
```

**Aggregator mount** (modify `apps/backend/app/api/v1/router.py` lines 28–41):
```python
from app.modules.pt_sessions.router import (
    pt_sessions_router,
    package_scoped_router as pt_sessions_package_scoped_router,
)
...
v1.include_router(pt_sessions_router, prefix="/pt-sessions", tags=["pt-sessions"])
v1.include_router(pt_sessions_package_scoped_router, prefix="/pt-packages", tags=["pt-sessions"])
```

**Mirror what:** two-phase Redis claim + replay verbatim (CR-02 from Phase 33 review); RBAC-04 dependency order; `envelope(...)` wrapping; LITERAL strings in `require_permission`; route-binding `verify_idempotency` (returns `f"{method}:{path}:{header}"` so same header on different routes does NOT collide — CR-01 fix).
**Adapt what:** TWO routers exported (`pt_sessions_router` + `package_scoped_router`) per D-34-08; `(Action.CANCEL, Resource.PT_SESSIONS)` admits reception per D-34-09a (the service layer's `cancel_window_expired` 403 is the new gate); NO `Idempotency-Key` on GET endpoints (read-only).

---

### `apps/backend/app/modules/pt_sessions/permissions.py` (empty stub or absent)

**Analog:** `apps/backend/app/modules/memberships/` (no `permissions.py` — declarations are inline in router via `require_permission`).

**Pattern (option A — empty stub):**
```python
"""PT-sessions module permissions stub.

Phase 34 D-34-03 / D-34-09a: ALL permission gating happens inline in
router.py via `Depends(require_permission(Action.X, Resource.PT_SESSIONS))`.
This file exists only for module-shape parity with `pt_packages/` and
`trainers/` precedent; no exports.
"""
```

**Pattern (option B — omit file entirely):** memberships module has no permissions.py.

**Decision per CONTEXT.md D-34-03:** Claude's discretion. Planner picks based on whether the import-linter `modules-independent` walker complains about a missing file (unlikely).

---

### `apps/backend/app/core/dependencies.py` (amendment — D-34-12a)

**Self-analog:** `apps/backend/app/core/dependencies.py:280-285` (existing `TrainerById` Protocol).

**Current code (lines 280-285):**
```python
class TrainerById(Protocol):
    """Structural type for alive Trainer lookup result (Phase 31 D-31-13).
    Phase 34 pt_sessions service checks id + is_active."""

    id: UUID
    is_active: bool
```

**Amended code (Phase 34 D-34-12a):**
```python
class TrainerById(Protocol):
    """Structural type for alive Trainer lookup result (Phase 31 D-31-13).

    Phase 34 pt_sessions service checks id + is_active AND reads full_name
    for B-05 `trainer_name_snapshot` capture (D-34-12a additive extension).
    The SA `Trainer` ORM structurally satisfies this Protocol — zero
    implementation change to the resolver wiring; the existing
    `register_trainer_by_id_resolver(trainers_service.resolve_trainer_by_id)`
    call in app.main.create_app() returns the ORM row which already exposes
    `full_name: Mapped[str]` (Trainer model line 28).
    """

    id: UUID
    is_active: bool
    full_name: str  # Phase 34 D-34-12a — B-05 trainer_name_snapshot capture
```

**Mirror what:** Protocol class structure; docstring lineage notation.
**Adapt what:** add single line `full_name: str` + update docstring with D-34-12a reference. NO new Protocol slot, NO new register/resolve callables (the slot itself is unchanged).

---

### `apps/backend/app/core/permissions.py` (amendment — D-34-09a)

**Self-analog:** `apps/backend/app/core/permissions.py:88`

**Current code (lines 86-89):**
```python
    (Action.CANCEL, Resource.PT_PACKAGES),
    (Action.DELETE, Resource.PT_PACKAGES),
    (Action.CANCEL, Resource.PT_SESSIONS),   # ← line 88 — REMOVE per D-34-09a
})
```

**Amended code:** delete line 88 entirely (no replacement). Update comment block at lines 73-77 to note: "Phase 34 D-34-09a removed `(CANCEL, PT_SESSIONS)` — B-12 grants reception 24h cancel-window; application-layer `cancel_window_expired` 403 enforces the gate, not RBAC."

**Mirror what:** frozenset literal shape; trailing comma; comment-anchored decision references.
**Adapt what:** single-line removal; OWNER_ONLY size 26 → 25.

---

### `apps/backend/.importlinter` (amendment — D-34-14)

**Self-analog:** `apps/backend/.importlinter:13-27` (modules-independent contract)

**Current code (lines 16-27):**
```ini
[importlinter:contract:modules-independent]
name = modules cannot import each other
type = independence
modules =
    app.modules.auth
    app.modules.clients
    app.modules.memberships
    app.modules.visits
    app.modules.trainers
    app.modules.schedule
    app.modules.bookings
    app.modules.billing
    app.modules.notifications
    app.modules.payments
    app.modules.pt_packages
```

**Amended code:** append one line `    app.modules.pt_sessions` after `app.modules.pt_packages`. Total module count becomes 12 (per D-34-14).

**Mirror what:** indented list shape (4-space indent); alphabetical-by-roadmap-phase ordering retained.
**Adapt what:** single-line append; `lint-imports` MUST run green locally — pt_sessions/repository.py uses raw `text()` SQL referencing `pt_packages` / `trainers` / `clients` / `users` tables by string name (NOT ORM imports), so the contract passes (per D-34-04a).

---

### `apps/admin-web/src/shared/session/can.ts` (amendment — D-34-19)

**Self-analog:** `apps/admin-web/src/shared/session/can.ts:42`

**Current code (lines 40-43):**
```ts
  { action: 'cancel', resource: 'pt-packages' },
  { action: 'delete', resource: 'pt-packages' },
  { action: 'cancel', resource: 'pt-sessions' },   // ← line 42 — REMOVE per D-34-09a
]
```

**Amended code:** delete line 42. Update comment block at lines 29-31 to mirror backend `permissions.py` note: "reception now retains `{cancel, pt-sessions}` — 24h window enforced server-side."

**Mirror what:** array element shape `{ action: '...', resource: '...' }`; comment-block lineage notation.
**Adapt what:** single-line removal; byte-parity with backend `permissions.py` OWNER_ONLY (Phase 6 TEST-06 parity test catches drift; no separate test file edit needed).

---

### `apps/backend/tests/integration/pt_sessions/test_*.py` (NEW tests)

**Analog set:**
- `apps/backend/tests/integration/pt_packages/test_pt_package_sale.py` — happy-path + 422 + 404 + 409 + Idempotency replay + CSRF/auth shape.
- `apps/backend/tests/integration/pt_packages/test_pt_package_cancel.py` — cancel-flow + audit emit + invalid_transition.
- `apps/backend/tests/integration/pt_packages/test_pt_package_refund_race.py` — Postgres-only N-parallel race test using `db_session_real_commit` + `ASGITransport` + `asyncio.gather`; SAVEPOINT-isolated `db_session` cannot serialize concurrent INSERTs — race tests MUST use real-commit fixture.

**Race test pattern (PTS-TEST-01 / D-34-19)** — mirror `test_pt_package_refund_race.py` lines 50–63:
```python
@pytest.mark.asyncio
async def test_concurrent_record_pt_session_decrement_at_db_layer(
    db_session_real_commit: AsyncSession,
    app: FastAPI,
) -> None:
    """PTS-TEST-01: 2 parallel POST /pt-sessions on package with
    sessions_remaining=1 → exactly 1x201 + 1x409 pt_package_exhausted.

    Asserts the predicate `sessions_remaining > 0 AND status='active'` on
    the atomic UPDATE...RETURNING (D-34-04a / PT-16) is the source-of-truth
    race winner. App-layer fetch_pt_package_metadata pre-check performs
    SELECT-then-DECREMENT (TOCTOU) so app-side checks alone cannot serialise;
    only the DB row lock + predicate wins.

    Uses 2 DISTINCT Idempotency-Keys so the idempotency layer does NOT
    collapse them into a replay branch — observe the DB race, not cache.
    """
```

**Mirror what:** `pytest.mark.asyncio`; `db_session_real_commit` fixture for race tests (REF-TEST-02 precedent); `ASGITransport(app=app)` for end-to-end HTTP; `_csrf_headers(client, idempotency_key=...)` helper; CSRF cookie pluck pattern (`client.cookies.get("sportzal_csrf", "")`).
**Adapt what:** entity swap (Membership/PtPackage → PtSession); permission swap; backdating-window + cancel-window boundary tests (unit tests + integration smoke).

---

### `apps/backend/tests/unit/pt_sessions/test_*.py` (NEW unit tests)

**Analog:** `apps/backend/tests/unit/pt_packages/test_state_machine.py` (FSM math) + Phase 32 timing tests.

**Pattern (window-math boundary tests, D-34-19):**
- `test_backdating_window.py` — reception 7d inclusive/exclusive boundary, owner unlimited past, both roles reject future (`PerformedAtInFutureError`).
- `test_cancel_window.py` — reception 24h-from-`created_at` boundary, owner anytime; assert `cancel_window_expired` 403 raised.
- `test_revert_predicate.py` — `atomic_transition_exhausted_to_active` predicate `WHERE status='exhausted'` only flips that source (asserts no flip when status='cancelled').

**Mirror what:** Vitest-style "describe → it" sentence naming; pure-sync helpers tested without DB session (window math is a `datetime` arithmetic concern only).
**Adapt what:** NO FSM transition table (no FSM); replaced with numeric-boundary tests.

---

## Shared Patterns

### Caller-owns-txn (SVC001 / INFRA-13)
**Source:** `apps/backend/tests/unit/test_service_commit_gate.py:31` (`_SERVICE_GLOB = "modules/**/service.py"`)
**Apply to:** ALL public mutating functions in `pt_sessions/service.py` (`record_pt_session`, `cancel_pt_session`). They MUST end with `await session.commit()`. Helpers stay private (`_`-prefixed) or carry `# noqa: SVC001 caller-owns-txn` marker on def line.
**No Phase 30 amendment needed** — glob auto-covers `pt_sessions/service.py`.

### Audit emit with LITERAL strings (INFRA-11 AST gate)
**Source:** `apps/backend/app/core/audit.py:202-210` (`emit(session, event, *, actor_user_id, resource_type, resource_id=None, **payload)`)
**Apply to:** all `audit.emit(...)` calls in `pt_sessions/service.py`. Both `event` and `resource_type` MUST be literal strings (the AST walker `tests/unit/test_audit_taxonomy.py` enforces).
```python
await audit.emit(
    session,
    "pt_session_recorded",      # LITERAL
    actor_user_id=actor.id,
    resource_type="pt_session", # LITERAL
    resource_id=pt_session.id,
    **payload,  # **payload kwargs verbatim from locked PtSessionRecordedPayload
)
```
Three event names available to Phase 34 (pre-registered Phase 30/33): `"pt_session_recorded"`, `"pt_session_cancelled"`, `"pt_package_exhausted"`. ALL three payloads `extra='forbid'` — kwargs MUST match schema field-for-field.

### UUID/date JSONB serialisation
**Source:** `apps/backend/app/modules/pt_packages/service.py:591-604` (Phase 32-02 deviation #1 lesson)
**Apply to:** all audit emit calls in `pt_sessions/service.py`. Use `str(uuid)` and `.isoformat()` for UUID and datetime kwargs; Pydantic UUID validators on payload schemas accept str input.
```python
pt_session_id=str(pt_session.id),
performed_at=data.performed_at.isoformat(),
```

### Idempotency-Key two-phase Redis claim + replay
**Source:** `apps/backend/app/modules/pt_packages/router.py:244-300` (CR-02 from Phase 33 review)
**Apply to:** BOTH POST endpoints in `pt_sessions/router.py` (record + cancel). Pattern: read body → compute `body_sha256` → `begin_idempotency` (SET NX) → if NOT first → `load_idempotency_response` → match body_hash or raise `idempotency_in_flight` / `idempotency_key_reuse` → else run orchestrator → store envelope JSON in Redis with TTL.

### Modules-independent contract via raw `text()` SQL (D-34-04a)
**Source:** `apps/backend/app/modules/visits/repository.py` (no cross-module imports) + the precedent of Phase 32 payments writing FROM memberships orchestrator via Protocol slot (NOT direct import).
**Apply to:** ALL cross-module SQL in `pt_sessions/repository.py` touching `pt_packages` table. Use raw `sa.text("...")` strings with named params, add `# noqa: TABLE_REF cross-module SQL` marker for grep-ability. NO `from app.modules.pt_packages import ...`.

### RBAC-04 dependency ordering invariant
**Source:** `apps/backend/app/modules/pt_packages/router.py:217-227` (sale endpoint signature)
**Apply to:** ALL POST endpoints in `pt_sessions/router.py`. Order: `payload` → `request: Request` → `actor: Depends(require_permission(...))` → `_csrf: Depends(verify_csrf)` → `idempotency_key: Depends(verify_idempotency)` → `redis: Depends(get_redis)` → `session: Depends(get_db)`. `tests/integration/test_route_introspection.py` enforces statically.

### Pagination envelope `{items, total, page, pageSize}`
**Source:** `apps/backend/app/core/pagination.py` `PaginatedData` + `PageQuery` (Phase 8 standard)
**Apply to:** `GET /pt-packages/{id}/sessions` response. Use `PaginatedData.model_construct(...)` over ORM rows (skips Pydantic generic-validation issue with SA ORM types).

### Refresh narrowed to specific attributes (WR-04 lesson)
**Source:** `apps/backend/app/modules/pt_packages/service.py:614-615`, also `:807`, `:922`
**Apply to:** every `session.refresh(...)` in `pt_sessions/service.py`. ALWAYS pass `attribute_names=["updated_at", "created_at"]` (or narrower) — unscoped refresh eagerly loads future relationship attrs (e.g. a hypothetical `pt_session.sessions` collection if added later).

---

## No Analog Found

All Phase 34 files have strong analogs in the v1.4 codebase. No file falls into the "no analog" bucket — the codebase has consolidated patterns through Phases 30–33 that Phase 34 can mirror directly.

---

## Metadata

**Analog search scope:**
- `apps/backend/app/modules/{pt_packages,memberships,visits,trainers,clients,payments}/`
- `apps/backend/app/core/{audit,audit_payloads,dependencies,permissions,idempotency,pagination,schemas}.py`
- `apps/backend/alembic/versions/0014_pt_packages.py`
- `apps/backend/tests/integration/pt_packages/`, `apps/backend/tests/unit/pt_packages/`
- `apps/backend/.importlinter`, `apps/backend/app/main.py`, `apps/backend/app/api/v1/router.py`
- `apps/admin-web/src/shared/session/can.ts`

**Files scanned:** 17 source files read in full or in targeted ranges.
**Pattern extraction date:** 2026-05-16
**Project skills loaded:** none (no `.claude/skills/` or `.agents/skills/` directories present).
