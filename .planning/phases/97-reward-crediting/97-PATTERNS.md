# Phase 97: Reward Crediting - Pattern Map

**Mapped:** 2026-06-08
**Files analyzed:** 7 (5 edits + 1 new migration + 1 new test file)
**Analogs found:** 7 / 7

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `apps/backend/app/modules/loyalty/service.py` (EDIT) | service | CRUD / event-driven | `accrue_welcome_bonus` (line 68) + `record_loyalty_redemption` (line 290) same file | exact |
| `apps/backend/app/modules/loyalty/models.py` (EDIT) | model | CRUD | `online_payment_id` nullable FK column + `entry_type` CheckConstraint, same file | exact |
| `apps/backend/alembic/versions/0069_*.py` (NEW) | migration | batch | `0055_loyalty_redemption_columns.py` (add nullable FK + partial UNIQUE to existing table) + `0054_loyalty_ledger.py` (partial UNIQUE index literal name) | exact |
| `apps/backend/app/core/audit.py` (EDIT) | config | request-response | Phase 96 `referral_code_generated`/`referral_captured` entries, lines 479-483 | exact |
| `apps/backend/app/core/audit_payloads.py` (EDIT) | config | request-response | `LoyaltyAccruedPayload` (line 1273) + `ReferralCapturedPayload` (line 1373) + registry entry pattern (line 1491-1494) | exact |
| `apps/backend/app/api/v1/_internal/yookassa/handlers.py` (EDIT) | controller | request-response / event-driven | `record_loyalty_redemption` call block (lines 554-564) + first-purchase count raw SQL pattern (lines 510-535) | exact |
| `apps/backend/tests/integration/test_referral_crediting*.py` (NEW) | test | CRUD | `test_loyalty_redemption.py` (real-commit engine + ASGITransport + respx YooKassa mock) + `test_referral_capture.py` (SAVEPOINT harness pattern) | exact |

---

## Pattern Assignments

### `apps/backend/app/modules/loyalty/service.py` — add `accrue_referral_bonus`

**Analog:** `accrue_welcome_bonus` (lines 68-136) — line-for-line template.

**Imports pattern** (lines 14-35) — already present; no new imports needed except `Literal` from typing:
```python
from __future__ import annotations
from uuid import UUID
import structlog
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from app.core import audit
from app.modules.loyalty.models import LoyaltyLedger
```

**Core flush-only primitive pattern** (lines 68-136):
```python
async def accrue_welcome_bonus(
    session: AsyncSession,
    client_id: UUID,
) -> None:
    """...flush only — never commit (caller-owns-txn)."""
    stmt = (
        pg_insert(LoyaltyLedger)
        .values(
            client_id=client_id,
            entry_type="welcome",
            amount_kopecks=WELCOME_BONUS_KOPECKS,
            category=None,
            reason=None,
        )
        .on_conflict_do_nothing(
            index_elements=["client_id"],
            # Inline SQL literal (NOT a bound param) so PostgreSQL can match this
            # predicate against the partial UNIQUE INDEX during ON CONFLICT arbiter
            # inference. `literal_column(...) == "welcome"` renders `entry_type = $param`,
            # which Postgres refuses to match (raises InvalidColumnReferenceError).
            index_where=text("entry_type = 'welcome'"),
        )
        .returning(LoyaltyLedger.id)
    )
    result = await session.execute(stmt)
    inserted_id = result.scalar_one_or_none()

    if inserted_id is None:
        _log.info("loyalty_welcome_conflict", client_id=str(client_id), msg="already accrued — no-op")
        return

    # RETURNING-gated audit emit — only on real insert (INFRA-15).
    await audit.emit(
        session,
        "loyalty_accrued",
        actor_user_id=None,
        resource_type="loyalty",
        resource_id=inserted_id,
        client_id=str(client_id),
        entry_id=str(inserted_id),
        amount_kopecks=WELCOME_BONUS_KOPECKS,
        entry_type="welcome",
        actor="welcome",
    )
```

**Adaptation for `accrue_referral_bonus`:**
- `index_elements=["referral_capture_id", "client_id"]` (compound, mirrors the partial UNIQUE in migration 0069)
- `index_where=text("entry_type = 'referral_accrual'")` — literal, same gotcha
- `entry_type="referral_accrual"`
- New `.values(...)` fields: `referral_capture_id=referral_capture_id`, `online_payment_id=online_payment_id`, `category="referral"`
- Audit event: `"referral_bonus_accrued"` / `resource_type="referral"` (per CONTEXT decision)
- Signature: `(session, *, client_id, amount_kopecks, referral_capture_id, online_payment_id, role)` where `role: Literal["referrer", "referee"]`
- Returns `UUID | None` (the inserted id, or None on conflict)
- Must NOT call `session.flush()` or `session.commit()` — the webhook `async with session.begin()` owns the commit

**Second analog — `record_loyalty_redemption`** (lines 290-386) for the `online_payment_id` field pattern:
```python
stmt = (
    pg_insert(LoyaltyLedger)
    .values(
        client_id=client_id,
        entry_type="redemption",
        amount_kopecks=-actual_debit,
        online_payment_id=online_payment_id,   # ← set on referral rows too
        category=None,
        reason=None,
    )
    .on_conflict_do_nothing(
        index_elements=["online_payment_id"],
        index_where=text("entry_type = 'redemption'"),
    )
    .returning(LoyaltyLedger.id)
)
```

---

### `apps/backend/app/modules/loyalty/models.py` — add `referral_capture_id` FK column

**Analog:** `online_payment_id` nullable FK column (lines 85-99) — exact structural twin.

**Existing nullable FK column pattern** (lines 85-99):
```python
# Phase 83 REDM-02: nullable FK → online_payments.id (RESTRICT).
# Idempotency anchor for the webhook-locked redemption write.
# NULL for welcome/owner_grant rows; set for redemption rows only.
online_payment_id: Mapped[UUIDType | None] = mapped_column(
    PgUUID(as_uuid=True),
    ForeignKey(
        "online_payments.id",
        ondelete="RESTRICT",
        name="fk_loyalty_ledger_online_payment_id_online_payments",
    ),
    nullable=True,
)
```

**CheckConstraint bare-suffix naming** (lines 106-113):
```python
__table_args__ = (
    CheckConstraint(
        "entry_type IN ('welcome', 'owner_grant', 'redemption')",
        # NAMING_CONVENTION expands to ck_loyalty_ledger_entry_type
        # bare suffix only — NOT full name — template applies prefix.
        name="entry_type",
    ),
)
```

**Adaptation:** Add after `online_payment_id`:
```python
# Phase 97 REFER-04: nullable FK → referral_captures.id (RESTRICT).
# Idempotency anchor for referral accrual rows (referral_accrual entry_type only).
# NULL for all other entry types. Partial UNIQUE uq_loyalty_ledger_referral_accrual
# declared in migration 0069 (not as ORM Index) — mirrors online_payment_id pattern.
referral_capture_id: Mapped[UUIDType | None] = mapped_column(
    PgUUID(as_uuid=True),
    ForeignKey(
        "referral_captures.id",
        ondelete="RESTRICT",
        name="fk_loyalty_ledger_referral_capture_id_referral_captures",
    ),
    nullable=True,
)
```

**CheckConstraint widen:** Change the `__table_args__` constraint string to:
```python
"entry_type IN ('welcome', 'owner_grant', 'redemption', 'referral_accrual')"
```
The `name="entry_type"` bare suffix stays unchanged (NAMING_CONVENTION expands it at DDL time).

**NOTE:** The ORM model `__table_args__` CHECK update must match the migration 0069 `drop_constraint` + `create_check_constraint` so Alembic autogenerate stays clean. Do NOT add an ORM `Index` for the partial UNIQUE — that is migration-only discipline (mirrors `uq_loyalty_ledger_welcome` / `uq_loyalty_ledger_online_payment_id`).

---

### `apps/backend/alembic/versions/0069_referral_crediting_columns.py` (NEW migration)

**Primary analog:** `0055_loyalty_redemption_columns.py` (add nullable FK + partial UNIQUE to existing table) — closest structural match.

**Migration header pattern** (from 0055):
```python
revision: str = "0055_loyalty_redemption_columns"
down_revision: str | None = "0054_loyalty_ledger"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```

**Add nullable FK column + create_foreign_key pattern** (0055 lines 45-62):
```python
def upgrade() -> None:
    op.add_column(
        "loyalty_ledger",
        sa.Column(
            "online_payment_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_loyalty_ledger_online_payment_id_online_payments",
        "loyalty_ledger",
        "online_payments",
        ["online_payment_id"],
        ["id"],
        ondelete="RESTRICT",
    )
```

**Partial UNIQUE index literal name pattern** (0055 lines 64-72 + 0054 lines 73-81):
```python
    # LITERAL index name (NOT op.f()) — mirrors uq_loyalty_ledger_welcome.
    op.create_index(
        "uq_loyalty_ledger_referral_accrual",   # literal name
        "loyalty_ledger",
        ["referral_capture_id", "client_id"],    # compound — both sides idempotency
        unique=True,
        postgresql_where=text("entry_type = 'referral_accrual'"),
    )
```

**CHECK constraint drop + recreate pattern** — needed because widening a CHECK requires DROP + CREATE (ALTER TABLE ... DROP CONSTRAINT, then ALTER TABLE ... ADD CONSTRAINT). The constraint was created in migration 0054 via `op.f("ck_loyalty_ledger_entry_type")` which expands to the full name:
```python
    # Widen entry_type CHECK to include 'referral_accrual'.
    # Must drop+recreate named constraint (no ALTER CONSTRAINT in Postgres).
    op.drop_constraint("ck_loyalty_ledger_entry_type", "loyalty_ledger", type_="check")
    op.create_check_constraint(
        "ck_loyalty_ledger_entry_type",
        "loyalty_ledger",
        "entry_type IN ('welcome', 'owner_grant', 'redemption', 'referral_accrual')",
    )
```

**Downgrade pattern** (0055 lines 86-95) — reverse order:
```python
def downgrade() -> None:
    op.drop_index("uq_loyalty_ledger_online_payment_id", table_name="loyalty_ledger")
    op.drop_constraint(
        "fk_loyalty_ledger_online_payment_id_online_payments",
        "loyalty_ledger",
        type_="foreignkey",
    )
    op.drop_column("loyalty_ledger", "online_payment_id")
```

**Migration 0069 downgrade must:** (1) drop partial UNIQUE, (2) drop FK constraint, (3) drop column, (4) restore the original CHECK (drop new + recreate with original IN list excluding `'referral_accrual'`).

---

### `apps/backend/app/core/audit.py` — register `referral_bonus_accrued`

**Analog:** Phase 96 block (lines 478-483) — exact insertion style.

**v2.6 block** (lines 478-483):
```python
        # v2.6 (Phase 96 lock — INFRA-15; referral domain. Pre-registered BEFORE
        # any callsite per INFRA-15 discipline.)
        ("referral_code_generated", "referral"),
        ("referral_captured", "referral"),
```

**Adaptation:** Append inside the same v2.6 block (after `referral_captured`, before the closing `}`):
```python
        # v2.6 (Phase 97 lock — INFRA-15; referral bonus accrual. Pre-registered BEFORE
        # the payment.succeeded webhook callsite per INFRA-15 discipline.)
        ("referral_bonus_accrued", "referral"),
```

Resource type `"referral"` follows the Phase 96 referral-domain precedent. The `resource_id` at callsite will be the `loyalty_ledger.id` of the inserted row.

---

### `apps/backend/app/core/audit_payloads.py` — add `ReferralBonusAccruedPayload` + registry entry

**Analog 1 — payload class:** `LoyaltyAccruedPayload` (lines 1273-1291) for the accrual shape, `ReferralCapturedPayload` (lines 1373-1385) for referral linkage IDs.

**LoyaltyAccruedPayload template** (lines 1273-1291):
```python
class LoyaltyAccruedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_id: UUID
    entry_id: UUID
    amount_kopecks: int
    entry_type: Literal["welcome", "owner_grant"]
    actor: str
```

**ReferralCapturedPayload template** (lines 1373-1385):
```python
class ReferralCapturedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    referee_client_id: UUID
    referrer_client_id: UUID
    referral_capture_id: UUID
    referral_code_id: UUID
```

**New payload class** (add in the v2.6 block after `ReferralCapturedPayload`):
```python
class ReferralBonusAccruedPayload(BaseModel):
    """Payload schema for ("referral_bonus_accrued", "referral") — Phase 97 REFER-04.

    Emitted per loyalty_ledger row (one for referrer, one for referee) inside
    the payment.succeeded webhook UoW. RETURNING-gated — emitted only on real insert.
    Pre-registered BEFORE any callsite per INFRA-15 discipline.

    role: 'referrer' — the client who shared the code (positive accrual).
          'referee' — the new client who was invited (welcome-style accrual).
    """
    model_config = ConfigDict(extra="forbid")

    client_id: UUID
    entry_id: UUID
    amount_kopecks: int          # always positive (accrual)
    referral_capture_id: UUID    # idempotency anchor
    online_payment_id: UUID      # forensic link to the triggering payment
    role: Literal["referrer", "referee"]
```

**Analog 2 — registry entry** (lines 1491-1494):
```python
    # v2.6 (Phase 96 referral domain — REFER-01/REFER-03 / INFRA-15):
    ("referral_code_generated", "referral"): ReferralCodeGeneratedPayload,
    ("referral_captured", "referral"): ReferralCapturedPayload,
```

**New registry entry** (append immediately after):
```python
    # v2.6 (Phase 97 referral bonus accrual — REFER-04 / INFRA-15):
    # Pre-registered BEFORE the payment.succeeded webhook callsite.
    ("referral_bonus_accrued", "referral"): ReferralBonusAccruedPayload,
```

---

### `apps/backend/app/api/v1/_internal/yookassa/handlers.py` — orchestrate crediting in `handle_payment_succeeded`

**Analog 1 — existing loyalty redemption call block** (lines 554-564), showing the exact insertion point and guard pattern:
```python
        # Phase 83 REDM-02: write loyalty redemption ledger row on payment.succeeded.
        # record_loyalty_redemption is idempotent (partial UNIQUE on online_payment_id
        # WHERE entry_type='redemption') + overdraft-clamped — webhook replay is safe.
        if row.loyalty_redeem_kopecks is not None and row.loyalty_redeem_kopecks > 0:
            await record_loyalty_redemption(
                session,
                client_id=row.client_id,
                online_payment_id=row.id,
                requested_redeem_kopecks=row.loyalty_redeem_kopecks,
            )
```

**New block inserts after the redemption call, before the notification block (line ~626).** The referral crediting block is `membership`-only (subject_kind guard mirrors the subject-kind dispatch already present).

**Analog 2 — raw SQL cross-module read pattern** (lines 510-535) for the first-purchase count query:
```python
        if _need_plan_price:
            if subject_kind == SUBJECT_KIND_MEMBERSHIP:
                _plan_table = "membership_plans"
            # ...
            _plan_price_row = (
                (
                    await session.execute(
                        text(
                            f"SELECT price_kopecks FROM {_plan_table} WHERE id = :id"  # noqa: S608
                        ),
                        {"id": str(subject_id)},
                    )
                )
                .mappings()
                .one_or_none()
            )
```

**First-purchase count query pattern** (D-54-08 cross-module raw SQL — no ORM import):
```python
        # REFER-04: credit referral bonus only on referee's FIRST membership payment.
        # Raw SQL — D-54-08: no ORM import of OnlinePayment from handlers.py.
        if subject_kind == SUBJECT_KIND_MEMBERSHIP:
            _prior_membership_payments = (
                (
                    await session.execute(
                        text(
                            "SELECT COUNT(*) AS cnt FROM online_payments "
                            "WHERE client_id = :cid "
                            "  AND status = 'succeeded' "
                            "  AND membership_plan_id IS NOT NULL "
                            "  AND id != :current_id"  # exclude the current row
                        ),
                        {"cid": str(row.client_id), "current_id": str(row.id)},
                    )
                )
                .mappings()
                .one()
            )
            _is_first_membership = int(_prior_membership_payments["cnt"]) == 0
```

**Analog 3 — `_read_client_receipt_contact` raw SQL client alive check** (line 273-283):
```python
    row = (
        await session.execute(
            select(Client.email, Client.phone).where(
                Client.id == client_id, Client.deleted_at.is_(None)
            )
        )
    ).one_or_none()
    if row is None:
        raise RuntimeError(f"Client {client_id} not found at webhook time")
```

**Referrer alive check** — raw SQL (D-54-08), adapted:
```python
        _referrer_alive = (
            await session.execute(
                text(
                    "SELECT 1 FROM clients "
                    "WHERE id = :cid AND deleted_at IS NULL LIMIT 1"
                ),
                {"cid": str(_capture.referrer_client_id)},
            )
        ).fetchone()
        if _referrer_alive is None:
            # Void entire accrual per CONTEXT decision — no orphan bonus.
            _log.info("referral_bonus_voided_referrer_deleted", ...)
            # no-op (skip both credit calls)
```

**Analog 4 — referral capture lookup** (`referrals.repository.get_capture_by_referee`, lines 45-58 of repository.py):
```python
async def get_capture_by_referee(
    session: AsyncSession,
    referee_client_id: UUID,
) -> ReferralCapture | None:
    stmt = select(ReferralCapture).where(
        ReferralCapture.referee_client_id == referee_client_id
    )
    result: ReferralCapture | None = await session.scalar(stmt)
    return result
```

**Analog 5 — referral config read** (`referrals.repository.get_config`, lines 61-65 of repository.py):
```python
async def get_config(session: AsyncSession) -> ReferralConfig | None:
    stmt = select(ReferralConfig).limit(1)
    result: ReferralConfig | None = await session.scalar(stmt)
    return result
```

**Import additions needed in handlers.py:**
```python
from app.modules.loyalty.service import accrue_referral_bonus  # new import (line beside record_loyalty_redemption)
from app.modules.referrals import repository as referrals_repo   # D-54-08 cross-module via repository, not service
```

**Complete orchestration sequence** (inside `async with session.begin():`, after `record_loyalty_redemption`, before notification block):
1. Guard: `if subject_kind == SUBJECT_KIND_MEMBERSHIP:`
2. Lookup capture: `_capture = await referrals_repo.get_capture_by_referee(session, row.client_id)` → if None, skip
3. First-purchase count raw SQL → if not first, skip (UNIQUE guard makes this a natural no-op but explicit skip avoids DB round-trip)
4. Referrer alive check raw SQL → if dead, void entire accrual (log + skip)
5. Config read: `_ref_config = await referrals_repo.get_config(session)` → if None, skip (config not seeded)
6. Two `await accrue_referral_bonus(...)` calls — referrer first, then referee

---

### `apps/backend/tests/integration/test_referral_crediting.py` (NEW)

**Primary analog:** `test_loyalty_redemption.py` — real-commit engine + ASGITransport + respx YooKassa mock + TRUNCATE cleanup fixture.

**Engine + session + webhook client fixture pattern** (lines 71-122):
```python
@pytest_asyncio.fixture
async def _redemption_engine() -> AsyncIterator[Any]:
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)
    try:
        yield engine
    finally:
        async with engine.begin() as conn:
            await conn.execute(
                text(f"TRUNCATE {', '.join(_TRUNCATE_TABLES)} RESTART IDENTITY CASCADE")
            )
        await engine.dispose()

@pytest_asyncio.fixture
async def _webhook_client(app: FastAPI, _redemption_engine: Any) -> AsyncIterator[AsyncClient]:
    factory = async_sessionmaker(_redemption_engine, expire_on_commit=False)
    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session
    def _override_get_redis() -> Any:
        return app.state.redis
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = _override_get_redis
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client
    finally:
        app.dependency_overrides.clear()
```

**respx YooKassa mock pattern** (lines 130-155):
```python
def _mock_yookassa_succeeded(yk_id: str) -> respx.MockRouter:
    router = respx.MockRouter(base_url=_YOOKASSA_BASE_URL, assert_all_called=False)
    router.get(url__regex=r"^https://api\.yookassa\.ru/v3/payments/[\w-]+$").mock(
        return_value=httpx.Response(200, json={
            "id": yk_id, "status": "succeeded",
            "amount": {"value": "1000.00", "currency": "RUB"}, "paid": True,
        })
    )
    return router
```

**TRUNCATE table list** — for referral crediting tests, add to the existing list:
```python
_TRUNCATE_TABLES = (
    "audit_log",
    "loyalty_ledger",
    "referral_captures",    # new for Phase 97
    "referral_codes",       # new for Phase 97
    # referral_config must NOT be truncated — seed row must survive
    "fiscal_receipts",
    "payments",
    "memberships",
    "online_payments",
    "membership_plans",
    "clients",
    "users",
)
```

**Secondary analog:** `test_referral_capture.py` for the `_auth_as_client` + `_seed_client` helpers if PWA-authenticated paths are needed. However, the webhook path is staff/system-initiated, so the real-commit engine pattern from `test_loyalty_redemption.py` is the primary harness.

**Test cases to implement** (modeled on `test_redm_01_idempotency_replay_writes_one_row`):
1. First membership payment + capture exists → two `referral_accrual` rows inserted (referrer + referee), two `referral_bonus_accrued` audit rows.
2. Webhook replay (same `yookassa_payment_id`) → exactly two rows total (idempotency via partial UNIQUE, RETURNING=None on conflict).
3. Second membership payment (not first) → no new accrual rows (first-purchase gate).
4. No capture row for referee → no accrual rows.
5. Referrer soft-deleted at webhook time → no accrual rows (void entire accrual).
6. PT-package payment (not membership) → no accrual rows.
7. Config missing → no accrual rows (graceful no-op).

---

## Shared Patterns

### Caller-owns-txn / flush-only (D-03 / D-32-10)
**Source:** `apps/backend/app/modules/loyalty/service.py` module docstring (lines 1-12) + `accrue_welcome_bonus` docstring (lines 72-84)
**Apply to:** `accrue_referral_bonus` in `loyalty/service.py`
```python
"""No session.commit() — caller-owns-txn (D-32-10/D-49-19).
All reads use raw SQL text() — no cross-module ORM import of Client (D-54-08).
"""
# flush only — never commit (caller-owns-txn).
```

### RETURNING-gated audit emit (INFRA-15)
**Source:** `apps/backend/app/modules/loyalty/service.py` lines 106-130
**Apply to:** `accrue_referral_bonus`
```python
    result = await session.execute(stmt)
    inserted_id = result.scalar_one_or_none()
    if inserted_id is None:
        # Conflict path — idempotent replay; emit nothing.
        return
    # Real insert — emit audit co-transactionally.
    await audit.emit(session, "referral_bonus_accrued", ...)
```

### ON CONFLICT partial-index inference — literal text() predicate
**Source:** `apps/backend/app/modules/loyalty/service.py` lines 94-102 + module docstring lines 1-12
**Apply to:** `accrue_referral_bonus` ON CONFLICT clause
```python
        .on_conflict_do_nothing(
            index_elements=["referral_capture_id", "client_id"],
            # Inline SQL literal (NOT a bound param) — PostgreSQL cannot match
            # `entry_type = $param` against `WHERE entry_type = 'referral_accrual'`
            # (raises InvalidColumnReferenceError). Mirror accrue_welcome_bonus.
            index_where=text("entry_type = 'referral_accrual'"),
        )
```

### Cross-module raw SQL reads (D-54-08)
**Source:** `apps/backend/app/api/v1/_internal/yookassa/handlers.py` lines 510-535 + module docstring
**Apply to:** first-purchase count query and referrer-alive check in `handle_payment_succeeded`
```python
# D-54-08: no ORM import of other modules' models; raw text() SQL only
await session.execute(
    text("SELECT COUNT(*) ... FROM online_payments WHERE ..."),
    {"cid": str(row.client_id), ...},
)
```

### INFRA-15 pre-registration discipline
**Source:** `apps/backend/app/core/audit.py` lines 478-483 + `audit_payloads.py` lines 1491-1494
**Apply to:** `audit.py` + `audit_payloads.py` edits — MUST be done in the same commit as (or before) the first `audit.emit(session, "referral_bonus_accrued", ...)` callsite
```python
# WRONG order: callsite before registration → AuditEventNotLockedError at runtime
# CORRECT: registration in audit.py + audit_payloads.py THEN callsite in handlers.py
```

### Partial UNIQUE index literal name (not via op.f())
**Source:** `apps/backend/alembic/versions/0054_loyalty_ledger.py` lines 73-81 and `0055_loyalty_redemption_columns.py` lines 64-72
**Apply to:** migration 0069 `create_index` call
```python
op.create_index(
    "uq_loyalty_ledger_referral_accrual",   # LITERAL — NOT op.f()
    "loyalty_ledger",
    ["referral_capture_id", "client_id"],
    unique=True,
    postgresql_where=text("entry_type = 'referral_accrual'"),
)
```

### FK literal name (full expanded form)
**Source:** `apps/backend/alembic/versions/0055_loyalty_redemption_columns.py` lines 55-62
**Apply to:** migration 0069 `create_foreign_key` call
```python
op.create_foreign_key(
    "fk_loyalty_ledger_referral_capture_id_referral_captures",  # LITERAL full name
    "loyalty_ledger",
    "referral_captures",
    ["referral_capture_id"],
    ["id"],
    ondelete="RESTRICT",
)
```

---

## No Analog Found

All files have close analogs in the codebase. No gaps.

---

## Metadata

**Analog search scope:** `apps/backend/app/modules/loyalty/`, `apps/backend/app/core/`, `apps/backend/app/api/v1/_internal/yookassa/`, `apps/backend/alembic/versions/`, `apps/backend/app/modules/referrals/`, `apps/backend/tests/integration/`
**Files scanned:** 12 source files + 3 migration files
**Pattern extraction date:** 2026-06-08
