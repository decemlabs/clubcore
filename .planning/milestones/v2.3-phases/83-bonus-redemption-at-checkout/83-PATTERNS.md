# Phase 83: Bonus Redemption at Checkout — Pattern Map

**Mapped:** 2026-06-05
**Files analyzed:** 11 new/modified files
**Analogs found:** 11 / 11

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `apps/backend/alembic/versions/0055_loyalty_redemption_columns.py` | migration | batch | `0054_loyalty_ledger.py` (partial UNIQUE) + `0047_online_payments_promo_code_id.py` (column-add) | exact |
| `apps/backend/app/modules/loyalty/models.py` | model | CRUD | `app/modules/promo_codes/models.py` PromoRedemption (nullable FK + __table_args__) | exact |
| `apps/backend/app/modules/loyalty/service.py` | service | CRUD | self (accrue_welcome_bonus idempotent insert pattern) | exact |
| `apps/backend/app/modules/online_payments/models.py` | model | CRUD | self (promo_code_id column pattern lines 91-99) | exact |
| `apps/backend/app/modules/online_payments/repository.py` | repository | CRUD | self (promo_code_id kwarg pattern lines 44-80) | exact |
| `apps/backend/app/modules/online_payments/service.py` | service | CRUD | self (applied_promo_code_id / price_override_kopecks plumbing lines 209-433) | exact |
| `apps/backend/app/modules/client_portal/schemas.py` | schema | request-response | self (ClientCheckoutRequest lines 256-266) | exact |
| `apps/backend/app/modules/client_portal/service.py` | service | request-response | self (client_checkout_membership promo flow lines 682-762) | exact |
| `apps/backend/app/api/v1/_internal/yookassa/handlers.py` | handler | event-driven | self (record_promo_redemption block lines 494-530) | exact |
| `apps/backend/app/core/audit.py` + `audit_payloads.py` | config | event-driven | self (loyalty_accrued registration + LoyaltyAccruedPayload lines 458-463 / 1273-1389) | exact |
| `apps/backend/tests/unit/test_audit_taxonomy.py` + `tests/integration/test_phase51_audit_chain_invariants.py` | test | CRUD | self (count-lock assertions at 102 → 103) | exact |
| `apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx` | component | request-response | self (BONUS_PLACEHOLDER lines 51-52, clubBonuses flag line 47, promo discount row lines 550-558, launchCheckout savePaymentMethod spread lines 236/246) | exact |

---

## Pattern Assignments

### `apps/backend/alembic/versions/0055_loyalty_redemption_columns.py` (migration, batch)

**Analogs:** `0054_loyalty_ledger.py` (partial UNIQUE index) + `0047_online_payments_promo_code_id.py` (nullable column-add to existing table)

**File header + revision chain pattern** (`0054_loyalty_ledger.py` lines 1-35):
```python
"""loyalty_ledger.online_payment_id FK + partial UNIQUE + online_payments.loyalty_redeem_kopecks (Phase 83 REDM-01/REDM-02).

Revision ID: 0055_loyalty_redemption_columns
Revises: 0054_loyalty_ledger
Create Date: 2026-06-05 00:00:00.000000

Adds:
- loyalty_ledger.online_payment_id: nullable UUID FK → online_payments.id (RESTRICT)
  Partial UNIQUE index uq_loyalty_ledger_online_payment_id: (online_payment_id) WHERE entry_type='redemption'
  Literal index name (NOT via op.f()) — per 0034/0037/0046/0054 create_index precedent.
- online_payments.loyalty_redeem_kopecks: nullable BigInteger (kopecks; NULL = no bonus applied)
  FK-free — a scalar column, not a FK (mirrors promo_code_id FK vs no FK on discount_kopecks).
"""
revision: str = "0055_loyalty_redemption_columns"
down_revision: str | None = "0054_loyalty_ledger"
```

**Column-add to existing table pattern** (`0047_online_payments_promo_code_id.py` lines 36-61):
```python
def upgrade() -> None:
    # Column-add to existing table — nullable, no server_default needed.
    op.add_column(
        "online_payments",
        sa.Column(
            "promo_code_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        op.f("fk_online_payments_promo_code_id_promo_codes"),
        "online_payments",
        "promo_codes",
        ["promo_code_id"],
        ["id"],
        ondelete="RESTRICT",
    )

def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_online_payments_promo_code_id_promo_codes"),
        "online_payments",
        type_="foreignkey",
    )
    op.drop_column("online_payments", "promo_code_id")
```

**Partial UNIQUE index pattern** (`0054_loyalty_ledger.py` lines 73-88):
```python
# Partial UNIQUE: literal index name (NOT via op.f()) per 0034/0037/0046 precedent.
# index_elements here is a single column; WHERE clause is a text() predicate.
op.create_index(
    "uq_loyalty_ledger_welcome",        # literal name, no op.f()
    "loyalty_ledger",
    ["client_id"],
    unique=True,
    postgresql_where=text("entry_type = 'welcome'"),
)
# Plain index via op.f() — standard, non-partial.
op.create_index(
    op.f("ix_loyalty_ledger_client_id"),
    "loyalty_ledger",
    ["client_id"],
    unique=False,
)
```

For Phase 83, the new partial UNIQUE is `(online_payment_id) WHERE entry_type='redemption'` and must use a literal name `uq_loyalty_ledger_online_payment_id` (not `op.f()`). The new `online_payments.loyalty_redeem_kopecks` column uses `op.add_column` with `sa.BigInteger, nullable=True` — no FK, no CHECK (it is always non-negative by service logic). Downgrade drops both.

---

### `apps/backend/app/modules/loyalty/models.py` (model, CRUD)

**Analog:** `app/modules/promo_codes/models.py` PromoRedemption lines 122-148 (nullable FK + `__table_args__` constraint pattern)

**New column to add to LoyaltyLedger** — follows PromoRedemption.online_payment_id exactly:
```python
# PromoRedemption pattern (promo_codes/models.py lines 122-130) — copy for LoyaltyLedger:
online_payment_id: Mapped[UUIDType | None] = mapped_column(
    PgUUID(as_uuid=True),
    ForeignKey(
        "online_payments.id",
        ondelete="RESTRICT",
        name="fk_loyalty_ledger_online_payment_id_online_payments",
    ),
    nullable=True,  # NULL for welcome/owner_grant rows; only redemption rows carry a payment id
)
```

**Existing `__table_args__` must gain a note** (existing model `loyalty/models.py` lines 91-101):
```python
__table_args__ = (
    CheckConstraint(
        "entry_type IN ('welcome', 'owner_grant', 'redemption')",
        name="entry_type",
    ),
)
# Partial UNIQUE index uq_loyalty_ledger_online_payment_id and plain index
# ix_loyalty_ledger_client_id are declared in migration 0055 (not here)
# — mirrors PromoCode uq_promo_codes_code_alive partial-index pattern.
```

**NAMING_CONVENTION discipline** (`loyalty/models.py` lines 15-20 docstring):
- ForeignKey `name=` takes the full literal name (e.g. `fk_loyalty_ledger_online_payment_id_online_payments`).
- CheckConstraint `name=` takes the BARE suffix only (convention expands it to `ck_loyalty_ledger_<suffix>`).
- Partial UNIQUE index declared in migration — not as `Index(...)` in ORM.

---

### `apps/backend/app/modules/loyalty/service.py` — new `record_loyalty_redemption` function (service, CRUD)

**Analogs:** `accrue_welcome_bonus` (same file, lines 68-136) for `on_conflict_do_nothing` + `index_elements + index_where` partial-index pattern; `promo_codes/service.py record_promo_redemption` (lines 282-411) for the overall webhook-idempotent write structure.

**Imports to add** (mirrors existing imports in same file lines 1-36):
```python
from uuid import UUID
import structlog
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from app.core import audit
from app.modules.loyalty.models import LoyaltyLedger
```

**Idempotent partial-index ON CONFLICT pattern** (`accrue_welcome_bonus` lines 85-116):
```python
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
        # Must match the partial index predicate EXACTLY — text() literal, not bound param.
        index_where=text("entry_type = 'welcome'"),
    )
    .returning(LoyaltyLedger.id)
)
result = await session.execute(stmt)
inserted_id = result.scalar_one_or_none()

if inserted_id is None:
    # Conflict — idempotent replay, emit nothing.
    _log.info("loyalty_welcome_conflict", ...)
    return
```

For `record_loyalty_redemption`, the ON CONFLICT uses `index_elements=["online_payment_id"]` and `index_where=text("entry_type = 'redemption'")` (matching the new partial UNIQUE migration index). Amount is negative (debit).

**Overdraft guard pattern** (balance SUM fold from `_sum_balance` same file lines 295-310):
```python
async def _sum_balance(session: AsyncSession, client_id: UUID) -> int:
    row = (
        (
            await session.execute(
                text(
                    "SELECT COALESCE(SUM(amount_kopecks), 0) AS balance "
                    "FROM loyalty_ledger WHERE client_id = :cid"
                ),
                {"cid": str(client_id)},
            )
        )
        .mappings()
        .one()
    )
    return int(row["balance"])
```

The overdraft guard calls `_sum_balance` BEFORE inserting the debit to clamp: `actual_debit = min(stored_redeem_kopecks, current_balance)`. If `actual_debit <= 0`, skip and log; otherwise insert `amount_kopecks = -actual_debit`.

**Audit emit pattern** (`accrue_welcome_bonus` lines 119-130, `owner_grant_loyalty` lines 182-194):
```python
await audit.emit(
    session,
    "loyalty_accrued",               # → for Phase 83: "loyalty_redeemed"
    actor_user_id=None,              # system-initiated webhook path
    resource_type="loyalty",
    resource_id=inserted_id,
    client_id=str(client_id),
    entry_id=str(inserted_id),
    amount_kopecks=WELCOME_BONUS_KOPECKS,    # → for redemption: negative amount
    entry_type="welcome",            # → "redemption"
    actor="welcome",                 # → "webhook"
)
```

---

### `apps/backend/app/modules/online_payments/models.py` (model, CRUD)

**Analog:** self — existing `promo_code_id` nullable FK column (lines 91-99); existing `save_payment_method` scalar bool column (lines 125-127)

**New column to add** — follows `save_payment_method` scalar pattern (lines 124-127):
```python
# Phase 79 PAYM-01: intent flag
save_payment_method: Mapped[bool] = mapped_column(
    Boolean, nullable=False, server_default=text("false")
)
```

For Phase 83, `loyalty_redeem_kopecks` is a nullable BigInteger scalar (no FK — just the stored amount). Pattern:
```python
# Phase 83 REDM-01: server-computed loyalty redeem amount stored at checkout.
# NULL = no bonus redemption applied. Positive integer in kopecks (the debit amount).
# Set by _sell_subject_core when loyalty_redeem_kopecks > 0; never client-writable.
loyalty_redeem_kopecks: Mapped[int | None] = mapped_column(
    BigInteger,
    nullable=True,
)
```

No `__table_args__` change needed — no CHECK, no UNIQUE on this scalar column.

---

### `apps/backend/app/modules/online_payments/repository.py` (repository, CRUD)

**Analog:** self — `promo_code_id` optional kwarg pattern (lines 44-83):
```python
async def insert_online_payment(
    session: AsyncSession,
    *,
    ...
    promo_code_id: UUID | None = None,
    save_payment_method: bool = False,
) -> OnlinePayment:
    kwargs: dict[str, Any] = dict(
        ...
        save_payment_method=save_payment_method,
    )
    if id_override is not None:
        kwargs["id"] = id_override
    if promo_code_id is not None:
        kwargs["promo_code_id"] = promo_code_id
    row = OnlinePayment(**kwargs)
    session.add(row)
    return row
```

For Phase 83, add `loyalty_redeem_kopecks: int | None = None` kwarg with the same conditional-include pattern:
```python
if loyalty_redeem_kopecks is not None:
    kwargs["loyalty_redeem_kopecks"] = loyalty_redeem_kopecks
```

---

### `apps/backend/app/modules/online_payments/service.py` — `_sell_subject_core` (service, CRUD)

**Analog:** self — `price_override_kopecks` + `applied_promo_code_id` threading pattern (lines 197-434):

**Signature extension** (lines 197-212):
```python
async def _sell_subject_core(
    session: AsyncSession,
    *,
    ...
    price_override_kopecks: int | None = None,
    applied_promo_code_id: UUID | None = None,
    save_payment_method: bool = False,
) -> SellResponse:
```

For Phase 83 add `loyalty_redeem_kopecks: int | None = None` parameter in the same position.

**Price override application** (lines 339-345):
```python
if price_override_kopecks is not None:
    price_kopecks = price_override_kopecks
```

For Phase 83, the bonus deduction follows AFTER the promo override:
```python
if loyalty_redeem_kopecks is not None and loyalty_redeem_kopecks > 0:
    price_kopecks = max(1, price_kopecks - loyalty_redeem_kopecks)
    # max(1) guard: ЮKassa requires amount > 0 (mirrors PromoNotApplicableError guard)
```

**Repository call extension** (lines 419-434):
```python
row = await repository.insert_online_payment(
    session,
    ...
    promo_code_id=applied_promo_code_id,          # Phase 999.4
    save_payment_method=save_payment_method,       # Phase 79
    loyalty_redeem_kopecks=loyalty_redeem_kopecks, # Phase 83 — add here
)
```

---

### `apps/backend/app/modules/client_portal/schemas.py` — `ClientCheckoutRequest` (schema, request-response)

**Analog:** self — existing `ClientCheckoutRequest` lines 256-266:
```python
class ClientCheckoutRequest(ResponseData):
    """Request body for client-initiated checkout (CPAY-01/02).

    No fields required for membership (plan_id in path); for PT the
    idempotency_key is supplied via Idempotency-Key header (D-71-04), not body.
    Phase 999.4 D-06: optional promo_code field (wire: promoCode).
    Phase 79 PAYM-01: optional save_payment_method flag (wire: savePaymentMethod).
    """

    promo_code: str | None = None  # wire: promoCode (D-06); None = no promo applied
    save_payment_method: bool = False  # wire: savePaymentMethod (PAYM-01)
```

For Phase 83, add one field following the same pattern:
```python
loyalty_redeem_kopecks: int | None = None  # wire: loyaltyRedeemKopecks (REDM-01)
                                            # desired redeem amount; server caps authoritatively
                                            # None = no bonus redemption requested
```

Field naming: Python snake_case `loyalty_redeem_kopecks` maps to Pydantic alias `loyaltyRedeemKopecks` via model_config (or explicit alias — check `ResponseData` base to confirm alias generation pattern).

---

### `apps/backend/app/modules/client_portal/service.py` — `client_checkout_membership` + `client_checkout_pt_package` (service, request-response)

**Analog:** self — promo_code validation + `price_override` + `applied_promo_code_id` block (lines 682-762):

**Promo-validation block to mirror for bonus** (lines 714-732):
```python
# Phase 999.4 D-06: validate promo BEFORE invoking the core.
price_override: int | None = None
applied_promo_code_id: UUID | None = None
if promo_code:
    (
        _discount_kopecks,
        price_override,
        _discount_type,
        applied_promo_code_id,
    ) = await _promo_service.validate_promo_code(
        session,
        code=promo_code,
        kind="sub",
        plan_id=plan_id,
        client_id=client.id,
    )
```

For Phase 83, after the promo block, add bonus clamping (no external service call — pure server math):
```python
# Phase 83 REDM-01: clamp requested bonus redeem against current balance.
# Server-authoritative cap: min(requested, currentBalance, post-promo price).
actual_loyalty_redeem: int | None = None
if loyalty_redeem_kopecks and loyalty_redeem_kopecks > 0:
    current_balance = await _loyalty_service.get_client_loyalty_balance(session, client.id)
    post_promo_price = price_override if price_override is not None else <plan_price>
    actual_loyalty_redeem = min(loyalty_redeem_kopecks, current_balance.balance_kopecks, post_promo_price - 1)
    if actual_loyalty_redeem <= 0:
        actual_loyalty_redeem = None
    else:
        price_override = (price_override if price_override is not None else <plan_price>) - actual_loyalty_redeem
```

**Core invocation extension** (lines 740-754):
```python
result = await invoke_client_checkout_core(
    session,
    ...
    price_override_kopecks=price_override,
    applied_promo_code_id=applied_promo_code_id,
    save_payment_method=save_payment_method,
    loyalty_redeem_kopecks=actual_loyalty_redeem,  # Phase 83 — add here
)
```

---

### `apps/backend/app/api/v1/_internal/yookassa/handlers.py` — succeeded webhook UoW (handler, event-driven)

**Analog:** self — `record_promo_redemption` block (lines 494-530):

**Exact block to replicate beside promo block** (lines 494-530):
```python
# Phase 999.4 D-07: record promo redemption if payment used a promo code.
# row.promo_code_id was set at checkout (migration 0047 + ORM column).
# record_promo_redemption is idempotent (on_conflict_do_nothing on
# uq_promo_redemptions_online_payment_id) so webhook replay is safe.
# discount_kopecks is derived from the plan price minus the stored amount.
if row.promo_code_id is not None:
    ...
    plan_price_kopecks: int = (
        int(_plan_price_row["price_kopecks"]) if _plan_price_row else row.amount_kopecks
    )
    discount_kopecks_for_redemption = max(0, plan_price_kopecks - row.amount_kopecks)
    if discount_kopecks_for_redemption > 0:
        await record_promo_redemption(
            session,
            promo_code_id=row.promo_code_id,
            client_id=row.client_id,
            online_payment_id=row.id,
            discount_kopecks=discount_kopecks_for_redemption,
        )
```

**CRITICAL fix to promo attribution** (CONTEXT.md REDM-02): the existing `discount_kopecks_for_redemption` computation is `plan_price - amount_kopecks`. With bonuses stacking, this over-attributes to promo. The corrected computation must be:
```python
# FIXED: plan_price − amount_kopecks − loyalty_redeem_kopecks
# so promo and bonus discounts are correctly separated.
promo_discount_kopecks = max(0, plan_price_kopecks - row.amount_kopecks - (row.loyalty_redeem_kopecks or 0))
```

**New loyalty redemption block** (add immediately after promo block):
```python
# Phase 83 REDM-02: record loyalty redemption if payment used bonus points.
# row.loyalty_redeem_kopecks was set at checkout (migration 0055 + ORM column).
# record_loyalty_redemption is idempotent (on_conflict_do_nothing on
# uq_loyalty_ledger_online_payment_id partial index) so webhook replay is safe.
# Overdraft guard: service clamps to current balance so ledger never goes negative.
if row.loyalty_redeem_kopecks and row.loyalty_redeem_kopecks > 0:
    await record_loyalty_redemption(
        session,
        client_id=row.client_id,
        online_payment_id=row.id,
        requested_redeem_kopecks=row.loyalty_redeem_kopecks,
    )
```

**Import to add** (follows existing import style at top of handlers.py):
```python
from app.modules.loyalty.service import record_loyalty_redemption
```

---

### `apps/backend/app/core/audit.py` + `audit_payloads.py` (config, event-driven)

**Analog:** `loyalty_accrued` registration (audit.py lines 458-463) + `LoyaltyAccruedPayload` + registry entry (audit_payloads.py lines 1273-1389):

**LOCKED_AUDIT_EVENTS extension** (`audit.py` lines 458-463):
```python
# v2.3 (Phase 82 lock — INFRA-15; emitted in Phase 82 loyalty service)
# Loyalty accrual lifecycle (ACCR-01 welcome + ACCR-02 owner_grant):
("loyalty_accrued", "loyalty"),
# v2.3 (Phase 83 lock — INFRA-15; emitted in Phase 83 webhook handler)
# Loyalty redemption debit (REDM-02): one event per successful payment with bonuses.
("loyalty_redeemed", "loyalty"),   # ADD THIS LINE
```

**New payload class** (`audit_payloads.py` — add after `LoyaltyAccruedPayload` at line 1292):
```python
class LoyaltyRedeemedPayload(BaseModel):
    """Payload schema for ("loyalty_redeemed", "loyalty") — Phase 83 REDM-02.

    Symmetry with LoyaltyAccruedPayload: same fields except entry_type is
    always 'redemption' and amount_kopecks is always negative.
    online_payment_id links the debit to the triggering payment (REDM-02 audit chain).
    """

    model_config = ConfigDict(extra="forbid")

    client_id: UUID
    entry_id: UUID
    amount_kopecks: int              # NEGATIVE integer (the debit)
    online_payment_id: UUID          # FK to online_payments.id
```

**AUDIT_PAYLOAD_SCHEMAS registry entry** (`audit_payloads.py` after line 1389):
```python
# v2.3 (Phase 83 loyalty redemption — REDM-02):
("loyalty_redeemed", "loyalty"): LoyaltyRedeemedPayload,
```

---

### `tests/unit/test_audit_taxonomy.py` + `tests/integration/test_phase51_audit_chain_invariants.py` (tests, CRUD)

**Analog:** self — existing count-lock assertions at 102 (`test_audit_taxonomy.py` line 237; `test_phase51_audit_chain_invariants.py` line 57):

**Current assertion to update** (`test_audit_taxonomy.py` lines 237-243):
```python
assert len(LOCKED_AUDIT_EVENTS) == 102, (
    "LOCKED_AUDIT_EVENTS size drifted: expected 102 "
    "(18 v1.1 + 12 v1.2 + 6 v1.3 + 17 v1.4 + 5 v1.5 + 13 v1.6 + 14 v1.7 "
    "+ 4 v1.9/P58 + 4 v1.9/P59 + 1 pre-P68 + 6 v2.0/P68 + 1 v2.2/P80 booking_rescheduled "
    "+ 1 v2.3/P82 loyalty_accrued), "
    f"got {len(LOCKED_AUDIT_EVENTS)}"
)
```

Change `102` → `103` in both files; update the descriptive string to append `+ 1 v2.3/P83 loyalty_redeemed`.

**Current assertion to update** (`test_phase51_audit_chain_invariants.py` line 57):
```python
assert len(LOCKED_AUDIT_EVENTS) == 102, (
    f"Expected 102 LOCKED_AUDIT_EVENTS after Phase 82 (v2.3), got {len(LOCKED_AUDIT_EVENTS)}. "
    ...
)
```

Change `102` → `103`; update message to reference Phase 83 loyalty_redeemed.

---

### `apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx` (component, request-response)

**Analog:** self — the file is its own analog; all change patterns are extracted from within it.

**Import extension** (line 4):
```javascript
// EXISTING:
import { useClientCheckoutMembership, useClientCheckoutPtPackage, usePromoValidate, useClientMe } from '@/data';
// CHANGE TO:
import { useClientCheckoutMembership, useClientCheckoutPtPackage, usePromoValidate, useClientMe, useClientLoyaltyBalance } from '@/data';
```

**BONUS_PLACEHOLDER removal** (lines 51-52) — delete these two lines entirely:
```javascript
// DELETE:
const BONUS_PLACEHOLDER = { balance: 1080, toGold: 220 };
```

**Feature flag flip** (line 47):
```javascript
// BEFORE:
clubBonuses:      false,
// AFTER:
clubBonuses:      true,
```

**Real balance fetch** — add to `ReviewStage` component body alongside `useClientMe` call (line 147 pattern):
```javascript
// Existing pattern (line 147):
const { data: clientMe } = useClientMe();
// Add after:
const { data: loyaltyBalance, isLoading: loyaltyLoading } = useClientLoyaltyBalance();
const balanceKopecks = loyaltyBalance?.balanceKopecks ?? 0;
```

**`bonusOn` toggle handler** (lines 526-531 — the existing handler):
```javascript
// EXISTING (lines 525-532):
onClick={() => {
  const next = !bonusOn;
  setBonusOn(next);
  showToast(next ? 'Бонусы будут списаны' : 'Списание бонусов отменено');
}}
// CHANGE TO (update toast copy + add estimate):
onClick={() => {
  const next = !bonusOn;
  setBonusOn(next);
  showToast(next ? 'Бонусы будут списаны при оплате' : 'Списание бонусов отменено');
}}
```

**Estimate derivation** — add as derived constants (not state) after existing `total`/`discount` at lines 152-153:
```javascript
// Existing (lines 152-153):
const total = promoResult ? promoResult.newAmountKopecks : ctx.amount;
const discount = promoResult ? promoResult.discountKopecks : 0;
// Add after (derived, not useState):
const bonusEstimateKopecks = bonusOn ? Math.min(balanceKopecks, total) : 0;
const estimatedTotal = total - bonusEstimateKopecks;
```

**`useCountUp` call in ReviewStage** (line 364):
```javascript
// EXISTING:
const totalDisplay = useCountUp(total, [total]);
// CHANGE TO (pass estimatedTotal when bonuses on):
const totalDisplay = useCountUp(estimatedTotal, [estimatedTotal, bonusOn, bonusEstimateKopecks]);
```

**Savings bar** (lines 367-370):
```javascript
// EXISTING:
const savePct = total < ctx.amount
  ? Math.round(discount / ctx.amount * 100)
  : 0;
const payPct = 100 - savePct;
// CHANGE TO (combined discount for savings bar):
const totalDiscount = discount + bonusEstimateKopecks;
const savePct = estimatedTotal < ctx.amount
  ? Math.round(totalDiscount / ctx.amount * 100)
  : 0;
const payPct = 100 - savePct;
```

**Section visibility guard** — wrap `{CHECKOUT_FEATURE_FLAGS.clubBonuses && ...}` to add balance check:
```javascript
{CHECKOUT_FEATURE_FLAGS.clubBonuses && !loyaltyLoading && balanceKopecks > 0 && (
  <>
    <div className="co-sec-label">Бонусы клуба<span className="co-ln" /></div>
    <div className="co-bonus">
      ...
    </div>
  </>
)}
```

**Toggle subtitle** (line 515-516 — replaces BONUS_PLACEHOLDER references):
```javascript
// EXISTING (lines 514-516):
<div className="co-bonus-sub">
  На счёте <b>{BONUS_PLACEHOLDER.balance.toLocaleString('ru-RU')}</b>
  {' · '}до Gold осталось <b>{BONUS_PLACEHOLDER.toGold}</b>
</div>
// CHANGE TO:
<div className="co-bonus-sub">
  На счёте <b>{formatMoney(balanceKopecks)}</b>
</div>
```

**Bonus discount row** — insert immediately after existing promo discount row (lines 550-558):
```javascript
{/* Promo discount row — existing, unchanged */}
{discount > 0 && (
  <div className="co-sum-row discount">
    <span className="co-sl-tag">
      Промокод{' '}
      <span className="co-mini">{promoResult?._validatedCode ?? promoCode}</span>
    </span>
    <span className="co-sv">−{formatMoney(discount)}</span>
  </div>
)}

{/* Bonus discount row — NEW, added immediately after promo row */}
{bonusOn && bonusEstimateKopecks > 0 && (
  <div className="co-sum-row discount">
    <span className="co-sl-tag">
      Бонусы<span className="co-mini">~</span>
    </span>
    <span className="co-sv">−{formatMoney(bonusEstimateKopecks)}</span>
  </div>
)}
```

**Savings bar legend** (line 588 — update `discount` reference):
```javascript
// EXISTING:
<b>{formatMoney(discount)}</b>
// CHANGE TO (show combined discount):
<b>{formatMoney(totalDiscount)}</b>
```

**`launchCheckout` extension** — thread `loyaltyRedeemKopecks` beside existing `savePaymentMethod` spread (lines 233-248):
```javascript
// EXISTING spread pattern (line 236):
...(savePaymentMethod ? { savePaymentMethod: true } : {}),
// ADD after it:
...(bonusOn && balanceKopecks > 0 ? { loyaltyRedeemKopecks: balanceKopecks } : {}),
```

Apply identically to both `checkoutMembership.mutateAsync` (line 233) and `checkoutPtPackage.mutateAsync` (line 242) call sites.

**Pay button estimate label** (locate `startPay` button label in ReviewStage — contains `totalDisplay`):
```javascript
// Prepend '~' when bonuses are on:
Оплатить · {bonusOn && bonusEstimateKopecks > 0 ? '~' : ''}{totalDisplay}
```

---

## Shared Patterns

### Caller-owns-txn
**Source:** `app/modules/loyalty/service.py` lines 1-12 module docstring + `app/modules/promo_codes/service.py` lines 20-21
**Apply to:** `record_loyalty_redemption` (service), `_sell_subject_core` loyalty param threading
```python
# No session.commit() — caller-owns-txn (D-32-10/D-49-19).
# flush only after INSERT to make IDs visible within the UoW.
await session.flush()
```

### D-54-08 Raw SQL
**Source:** `app/modules/loyalty/service.py` lines 4-11 module docstring; `_sum_balance` lines 295-310
**Apply to:** `record_loyalty_redemption` (balance SUM fold for overdraft guard)
```python
# Raw SQL text() — no cross-module ORM import (D-54-08).
row = (await session.execute(
    text("SELECT COALESCE(SUM(amount_kopecks), 0) AS balance FROM loyalty_ledger WHERE client_id = :cid"),
    {"cid": str(client_id)},
)).mappings().one()
```

### Idempotent pg_insert with partial index ON CONFLICT
**Source:** `app/modules/loyalty/service.py` lines 85-106 (`accrue_welcome_bonus`)
**Apply to:** `record_loyalty_redemption`
```python
# index_elements + index_where for partial UNIQUE INDEX (not a named CONSTRAINT).
# PostgreSQL ON CONFLICT ON CONSTRAINT only works for named UNIQUE CONSTRAINTs.
.on_conflict_do_nothing(
    index_elements=["online_payment_id"],
    index_where=text("entry_type = 'redemption'"),
)
.returning(LoyaltyLedger.id)
```

### INFRA-15 pre-registration discipline
**Source:** `app/core/audit.py` lines 458-463 (loyalty_accrued comment block)
**Apply to:** `("loyalty_redeemed", "loyalty")` must be added to `LOCKED_AUDIT_EVENTS` AND `AUDIT_PAYLOAD_SCHEMAS` BEFORE the callsite in `handlers.py` is written
```python
# v2.3 (Phase 83 lock — INFRA-15; emitted in Phase 83 webhook handler)
# Pre-registered BEFORE any callsite per INFRA-15 discipline.
("loyalty_redeemed", "loyalty"),
```

### Structlog emit pattern
**Source:** `app/modules/loyalty/service.py` lines 131-136; `app/modules/promo_codes/service.py` lines 405-410
**Apply to:** `record_loyalty_redemption` log calls
```python
_log.info(
    "loyalty_redemption_recorded",
    client_id=str(client_id),
    online_payment_id=str(online_payment_id),
    amount_kopecks=-actual_debit,
)
```

---

## No Analog Found

All files in this phase have close analogs in the codebase. No files are without pattern.

---

## Metadata

**Analog search scope:** `apps/backend/app/`, `apps/backend/alembic/versions/`, `apps/backend/tests/`, `apps/client-pwa/src/`
**Files scanned:** 18 source files read directly; ~12 grep searches
**Pattern extraction date:** 2026-06-05
