# Phase 75: Backend Field Additions - Pattern Map

**Mapped:** 2026-06-02
**Files analyzed:** 7 (4 modified, 3 new)
**Analogs found:** 7 / 7

> **IMPORTANT:** The latest Alembic revision on disk is `0049_fiscal_receipts_customer_phone`
> (not `0048` as noted in CONTEXT.md). The two new migrations for Phase 75 must use
> revision IDs `0050_clients_notif_prefs` and `0051_seed_fit15_promo`.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `app/modules/client_portal/schemas.py` (modify) | schema | request-response | same file (existing `ClientMeResponse`/`ClientProfileUpdateRequest`) | exact |
| `app/modules/clients/models.py` (modify) | model | CRUD | `clients.models.py` lines 95-98 (`emergency_contact` JSONB) | exact |
| `app/modules/client_portal/repository.py` (modify) | repository | CRUD | same file lines 568-640 (`update_client_profile` / `fetch_client_me`) | exact |
| `app/modules/client_portal/service.py` (modify) | service | request-response | same file lines 82-195 (validation constants + `update_client_profile`) | exact |
| `alembic/versions/0050_clients_notif_prefs.py` (new) | migration | CRUD | `0048_client_onboarding_fields.py` (additive nullable column, no backfill) | exact |
| `alembic/versions/0051_seed_fit15_promo.py` (new) | migration | CRUD | `scripts/seed_demo_data.py::_seed_promo_codes` lines 88-130 (pg_insert + on_conflict_do_nothing) | exact |
| `tests/modules/client_portal/test_notif_prefs_service.py` (new) | test | request-response | `tests/modules/client_portal/test_client_me_service.py` (service-layer unit, make_client fixture) | exact |
| `tests/integration/client_portal/test_notif_prefs_route.py` (new) | test | request-response | `tests/integration/client_portal/test_client_me_route.py` (ASGI + OTP + CSRF pattern) | exact |

---

## Pattern Assignments

### `app/modules/client_portal/schemas.py` (modify — schema, request-response)

**Analog:** same file, existing `ClientMembershipResponse` (lines 20-34), `ClientProfileUpdateRequest` (277-294), `ClientMeResponse` (297-313).

**Three targeted edits:**

**Edit 1 — Update module docstring** (lines 1-10): remove `price_kopecks_snapshot` from the "NEVER include" list, add a note that own-membership price is explicitly client-visible per D-03/D-75. Replace line 8:
```python
# OLD line 8:
#   - owner-only economics (price_kopecks_snapshot, duration_days_snapshot)
# NEW (split):
#   - owner-only economics (duration_days_snapshot, other clients' prices)
#   - own-membership price (price_kopecks_snapshot) IS client-visible per D-75-03
```

**Edit 2 — Add fields to `ClientMembershipResponse`** (after line 33):
```python
class ClientMembershipResponse(ResponseData):
    """Active membership payload with server-derived temporal fields (D-69-02).

    Exposed fields only (D-69-05 / D-75-03): no freeze_days_limit_snapshot
    internals, no audit fields. price_kopecks and auto_renew added Phase 75
    (D-75-02/D-75-01): own-membership price is client-visible; auto_renew is
    always null (no autopay concept in v1 — null = 'not applicable', preserves
    future boolean slot per D-75-01).
    days_until_end and expiring_soon are server-computed (D-69-02).
    """

    id: UUID
    plan_name_snapshot: str
    start_date: date
    end_date: date
    status: str
    days_until_end: int          # server-computed (D-69-02)
    expiring_soon: bool          # server-computed (D-69-02)
    price_kopecks: int           # wire: priceKopecks — D-75-02; source: price_kopecks_snapshot
    auto_renew: bool | None      # wire: autoRenew — D-75-01; always null (no autopay in v1)
```

**Edit 3 — Add `notif_prefs` to `ClientProfileUpdateRequest` and `ClientMeResponse`:**

Introduce a new inner schema above `ClientProfileUpdateRequest` (after line 275):
```python
class NotifPrefs(ResponseData):
    """Notification preference toggles (NOTIF-01 / D-75-04).

    Strict schema — exactly four bool keys. Unknown keys rejected (extra='forbid'
    inherited from ResponseData). Wire names via alias_generator=to_camel:
      promo, schedule, trainer, sound (no renaming needed — all single-word).
    Full-replace semantics on PATCH (D-75-05): client sends all four; server overwrites.
    """

    promo: bool
    schedule: bool
    trainer: bool
    sound: bool
```

Extend `ClientProfileUpdateRequest` (line ~294) to add:
```python
    notif_prefs: NotifPrefs | None = None  # wire: notifPrefs — D-75-04/D-75-05 full replace
```

Extend `ClientMeResponse` (line ~313) to add:
```python
    notif_prefs: NotifPrefs  # wire: notifPrefs — D-75-06 defaults applied server-side when NULL
```

**Wire alias note:** `alias_generator=to_camel` on `ResponseData` base produces:
- `price_kopecks` → `priceKopecks`
- `auto_renew` → `autoRenew`
- `notif_prefs` → `notifPrefs`
- `plan_name_snapshot` → `planNameSnapshot`

---

### `app/modules/clients/models.py` (modify — model, CRUD)

**Analog:** same file, `emergency_contact` JSONB column, lines 95-98.

**Pattern to copy exactly** (lines 95-98):
```python
emergency_contact: Mapped[dict[str, Any] | None] = mapped_column(
    JSONB,
    nullable=True,
)
```

**New column to add** (after `onboarding_completed_at`, ~line 128):
```python
notif_prefs: Mapped[dict[str, Any] | None] = mapped_column(
    JSONB,
    nullable=True,
)
```

**Key points:**
- Type annotation is `dict[str, Any] | None` — same as `emergency_contact`. No `typing.Any` import needed (already on line 29).
- `JSONB` import already present (line 45).
- `nullable=True` — no server_default; NULL = "not yet persisted" (service applies defaults on read per D-06).
- No `__table_args__` change needed (no index, no CHECK constraint — JSONB content is validated by the Pydantic schema layer per D-04).

---

### `alembic/versions/0050_clients_notif_prefs.py` (new — migration, CRUD)

**Analog:** `alembic/versions/0048_client_onboarding_fields.py` (additive nullable column, no backfill).

**Full structure pattern** (copy from 0048):
```python
"""clients: notif_prefs JSONB column for notification preference persistence (Phase 75 NOTIF-01).

Revision ID: 0050_clients_notif_prefs
Revises: 0049_fiscal_receipts_customer_phone
Create Date: 2026-06-02 00:00:00.000000

Additive migration — one nullable JSONB column. No backfill, no table rewrite.
ADD COLUMN is metadata-only on Postgres 16 — negligible lock window.
NULL means prefs not yet persisted; service returns NOTIF_DEFAULTS on read (D-75-06).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0050_clients_notif_prefs"
down_revision: str | None = "0049_fiscal_receipts_customer_phone"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "clients",
        sa.Column("notif_prefs", JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("clients", "notif_prefs")
```

**Key differences from 0048:**
- Import `JSONB` from `sqlalchemy.dialects.postgresql` (not needed in 0048 which only used `sa.Column` basic types).
- No `op.create_check_constraint` — JSONB content is validated by Pydantic, not DB CHECK.
- `down_revision` must be `"0049_fiscal_receipts_customer_phone"` (the actual current head).

---

### `alembic/versions/0051_seed_fit15_promo.py` (new — data migration, CRUD)

**Analog:** `scripts/seed_demo_data.py::_seed_promo_codes` lines 88-130 — the pg_insert + on_conflict_do_nothing shape.

**Seed script pattern** (lines 99-129):
```python
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import func

stmt = (
    pg_insert(PromoCode)
    .values(**c)
    .on_conflict_do_nothing(
        index_elements=[func.upper(PromoCode.code)],
        index_where=PromoCode.deleted_at.is_(None),
    )
)
await session.execute(stmt)
```

**Alembic data-migration adaptation** — Alembic migrations use `op.get_bind()` for raw connection, NOT an async session. Pattern for data migrations with raw SQL (preferred in this codebase per 0046_promo_codes.py precedent):

```python
"""promo_codes: seed FIT15 promo code (Phase 75 PROMO-01 / D-75-07/D-75-09).

Revision ID: 0051_seed_fit15_promo
Revises: 0050_clients_notif_prefs
Create Date: 2026-06-02 00:00:00.000000

Idempotent data migration — inserts FIT15 promo code using ON CONFLICT DO NOTHING
on the partial-UNIQUE index uq_promo_codes_code_alive (upper(code) WHERE deleted_at IS NULL).

FIT15 is a product code (not demo data), so it lands via migration on any DB including
production — unlike FIT10/FIRST500 which live only in scripts/seed_demo_data.py (D-75-07).

Parameters (D-75-09):
  discount_type='percentage', discount_value=1500 (15% encoded as percent*100),
  per_client_limit=1, max_uses=NULL, valid_from=NULL, valid_until=NULL (no expiry),
  is_active=true, applicable_to=NULL (membership + pt_package both eligible, D-75-08).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0051_seed_fit15_promo"
down_revision: str | None = "0050_clients_notif_prefs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ON CONFLICT DO NOTHING on uq_promo_codes_code_alive:
    #   partial UNIQUE on upper(code) WHERE deleted_at IS NULL (0046_promo_codes.py).
    # Re-running (e.g. on a restored DB) is a no-op.
    op.execute(
        sa.text(
            """
            INSERT INTO promo_codes (code, discount_type, discount_value,
                                     per_client_limit, max_uses,
                                     valid_from, valid_until, is_active, applicable_to)
            VALUES ('FIT15', 'percentage', 1500,
                    1, NULL,
                    NULL, NULL, TRUE, NULL)
            ON CONFLICT DO NOTHING
            """
        )
    )


def downgrade() -> None:
    # Soft-delete rather than hard-delete so referential integrity is preserved
    # if any redemption rows reference this code.
    op.execute(
        sa.text(
            "UPDATE promo_codes SET deleted_at = now() "
            "WHERE upper(code) = 'FIT15' AND deleted_at IS NULL"
        )
    )
```

**Key encoding notes (D-75-09):**
- `discount_value = 1500` = 15% encoded as `percent × 100` (matches FIT10=1000 in seed_demo_data.py line 105).
- `applicable_to = NULL` = both membership and pt_package (matches PromoCode model line 65-67).
- `ON CONFLICT DO NOTHING` without specifying `index_elements` works when the table has exactly one relevant partial unique index, but use the explicit form if needed:

```sql
ON CONFLICT (upper(code)) WHERE deleted_at IS NULL DO NOTHING
```

---

### `app/modules/client_portal/repository.py` (modify — repository, CRUD)

**Analog:** same file, `fetch_client_me` (lines 539-565) and `update_client_profile` (lines 568-640).

**Two targeted edits:**

**Edit 1 — Add `notif_prefs` to `fetch_client_me` SELECT** (line 556-558):
```python
# CURRENT SELECT list (line 556):
"SELECT id, first_name, last_name, phone, email, goal, "
"  height_cm, weight_kg, onboarding_completed_at "
"FROM clients WHERE id = :client_id AND deleted_at IS NULL"

# NEW SELECT list:
"SELECT id, first_name, last_name, phone, email, goal, "
"  height_cm, weight_kg, onboarding_completed_at, notif_prefs "
"FROM clients WHERE id = :client_id AND deleted_at IS NULL"
```

**Edit 2 — Add `notif_prefs` branch to `update_client_profile`** (after line 601, before the `if not sets:` guard):
```python
# Follow the existing pattern for each field (lines 586-602):
if payload.notif_prefs is not None:
    sets.append("notif_prefs = :notif_prefs")
    bind["notif_prefs"] = payload.notif_prefs.model_dump()
    # model_dump() produces a plain dict; asyncpg serializes dict→JSONB automatically.
```

**Cross-module write discipline (repository.py lines 1-17):**
- Raw `text()` SQL only — no ORM model imports from other modules.
- SET clause fragments are fixed string literals, never user-supplied SQL (S608 comment pattern on line 614).
- `payload.notif_prefs.model_dump()` converts the strict Pydantic `NotifPrefs` object to a plain `dict` for the bind parameter.

---

### `app/modules/client_portal/service.py` (modify — service, request-response)

**Analog:** same file, `update_client_profile` (lines 148-195) and validation constants (lines 84-115).

**Two targeted edits:**

**Edit 1 — Add `_NOTIF_KEYS` constant and `_InvalidNotifPrefsError`** (after line 115, following the existing validation error class pattern):
```python
_NOTIF_KEYS: frozenset[str] = frozenset({"promo", "schedule", "trainer", "sound"})

# D-75-06: server-side defaults when notif_prefs column is NULL
_NOTIF_DEFAULTS: dict[str, bool] = {
    "promo": True,
    "schedule": True,
    "trainer": True,
    "sound": False,
}
```

**Edit 2 — Apply defaults in `get_client_me`** (lines 133-145). After fetching the row, before constructing `ClientMeResponse`:
```python
# D-75-06: notif_prefs defaults when column is NULL
raw_notif = r.get("notif_prefs")
notif_prefs_data = raw_notif if raw_notif is not None else _NOTIF_DEFAULTS

return ClientMeResponse(
    id=cast(UUID, r["id"]),
    first_name=str(r["first_name"]),
    last_name=str(r["last_name"]),
    phone=str(r["phone"]),
    email=r.get("email"),
    goal=r.get("goal"),
    height_cm=r.get("height_cm"),
    weight_kg=r.get("weight_kg"),
    onboarding_completed_at=r.get("onboarding_completed_at"),
    notif_prefs=NotifPrefs(**notif_prefs_data),
)
```

**Edit 3 — Add `price_kopecks` and `auto_renew` to `_build_membership_response`** — find where `ClientMembershipResponse` is constructed (after the `fetch_client_membership` call in `get_client_membership`). The membership dict from the repository already contains `price_kopecks_snapshot` once the SELECT is extended:

In `repository.fetch_client_membership` (line 191), extend the SELECT to include `price_kopecks_snapshot`:
```python
# Add to SELECT list in fetch_client_membership (line 191-196):
"SELECT id, plan_name_snapshot, start_date, end_date, status, "
"  price_kopecks_snapshot, "
"  (end_date - (now() AT TIME ZONE 'Europe/Moscow')::date) AS days_until_end "
"FROM memberships "
"WHERE client_id = :client_id AND status = 'active' "
"ORDER BY start_date DESC, created_at DESC LIMIT 1"
```

Then in the service `_build_membership_response` helper (or inline where `ClientMembershipResponse` is constructed), add:
```python
# D-75-02: price_kopecks from price_kopecks_snapshot (immutable historic truth)
# D-75-01: auto_renew always None (no autopay concept in v1)
price_kopecks=int(row["price_kopecks_snapshot"]),
auto_renew=None,
```

**No `notif_prefs` validation in service** — the strict `NotifPrefs` Pydantic schema (extra='forbid') rejects unknown keys at the wire layer before the service is called. D-75-04 specifies validation belongs in the schema, not the service layer (contrast with `goal` enum which is service-validated because it arrives as a raw `str`).

---

### `tests/modules/client_portal/test_notif_prefs_service.py` (new — test, request-response)

**Analog:** `tests/modules/client_portal/test_client_me_service.py` — service-layer unit tests using `make_client` fixture and direct `service.*` calls.

**Header pattern** (lines 1-34 of analog):
```python
"""Phase 75 NOTIF-01 — service-layer tests for notif_prefs persistence + defaults.

Behaviors locked (D-75-04/D-75-05/D-75-06):
  - get_client_me returns NOTIF_DEFAULTS when notif_prefs column is NULL.
  - update_client_profile with notif_prefs persists all four keys (full replace).
  - update_client_profile with notif_prefs=None leaves existing prefs untouched.
  - get_client_me returns persisted prefs after PATCH.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.client_portal import service
from app.modules.client_portal.schemas import (
    ClientMeResponse,
    ClientProfileUpdateRequest,
    NotifPrefs,
)
from app.modules.clients.models import Client

pytestmark = pytest.mark.asyncio(loop_scope="function")


def _payload(**kwargs: object) -> ClientProfileUpdateRequest:
    return ClientProfileUpdateRequest(**kwargs)
```

**Test structure pattern** (mirrors `test_client_me_service.py` blocks):
```python
async def test_get_client_me_returns_notif_defaults_when_null(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
) -> None:
    """D-75-06: notif_prefs column NULL → server returns NOTIF_DEFAULTS."""
    client = await make_client()  # notif_prefs column is NULL
    result = await service.get_client_me(db_session, client.id)
    assert isinstance(result, ClientMeResponse)
    assert result.notif_prefs.promo is True
    assert result.notif_prefs.schedule is True
    assert result.notif_prefs.trainer is True
    assert result.notif_prefs.sound is False


async def test_update_client_profile_persists_notif_prefs(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
) -> None:
    """D-75-05: full-replace — all four keys written; GET reflects them."""
    client = await make_client()
    result = await service.update_client_profile(
        db_session,
        client_id=client.id,
        payload=_payload(
            notif_prefs=NotifPrefs(promo=False, schedule=True, trainer=False, sound=True)
        ),
    )
    assert result.notif_prefs.promo is False
    assert result.notif_prefs.schedule is True
    assert result.notif_prefs.trainer is False
    assert result.notif_prefs.sound is True
```

---

### `tests/integration/client_portal/test_notif_prefs_route.py` (new — test, request-response)

**Analog:** `tests/integration/client_portal/test_client_me_route.py` — ASGI-level integration tests with full OTP auth + CSRF flow.

**Auth helper pattern** (lines 46-96 of analog — copy `_auth_as_client_with_csrf` verbatim, same CSRF double-submit requirement for PATCH):
```python
from tests.integration.client_portal.test_client_me_route import _auth_as_client_with_csrf
# OR copy the helper — prefer import to avoid drift.
```

**PATCH test pattern** (lines 119-148 of analog):
```python
resp = await async_client.patch(
    "/api/v1/client/me",
    json={
        "notifPrefs": {
            "promo": False,
            "schedule": True,
            "trainer": False,
            "sound": True,
        }
    },
    headers={
        "Cookie": f"cc_client_access={access}; clubcore_client_csrf={csrf}",
        "x-csrf-token": csrf,
    },
)
assert resp.status_code == 200
data = resp.json()["data"]
assert data["notifPrefs"]["promo"] is False
assert data["notifPrefs"]["sound"] is True
```

**GET test pattern** (lines 150-194 of analog):
```python
# GET /me must include notifPrefs with NOTIF_DEFAULTS when never persisted
resp = await async_client.get(
    "/api/v1/client/me",
    headers={"Cookie": f"cc_client_access={access}"},
)
assert resp.status_code == 200
data = resp.json()["data"]
assert "notifPrefs" in data, "notifPrefs missing from GET /me response"
# Defaults: promo=true, schedule=true, trainer=true, sound=false
assert data["notifPrefs"]["promo"] is True
assert data["notifPrefs"]["sound"] is False
```

**Also add a test for `priceKopecks`/`autoRenew` on `/client/membership`:**
```python
async def test_membership_exposes_price_kopecks_and_auto_renew(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client_a: Client,
    seeded_owned_data: SeededOwnedData,
    redis_clean: object,
) -> None:
    """D-75-02/D-75-01: GET /membership returns priceKopecks (int) and autoRenew (null)."""
    token = await _auth_as_client(async_client, db_session, client_a)
    resp = await async_client.get(
        "/api/v1/client/membership",
        headers={"Cookie": f"cc_client_access={token}"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "priceKopecks" in data, "priceKopecks missing (D-75-02)"
    assert isinstance(data["priceKopecks"], int), "priceKopecks must be integer kopecks"
    assert data["priceKopecks"] > 0
    assert "autoRenew" in data, "autoRenew missing (D-75-01)"
    assert data["autoRenew"] is None, "autoRenew must be null (no autopay in v1)"
```

This test can live in `tests/integration/client_portal/test_read_endpoints.py` (alongside the existing `test_membership_temporal_fields_present`) or in the new `test_notif_prefs_route.py` file — follow the planner's placement decision.

---

## Shared Patterns

### camelCase wire serialization
**Source:** `app/modules/client_portal/schemas.py` line 17 + `app/core/schemas.py` (ResponseData base)
**Apply to:** All new/modified schema classes in schemas.py
```python
from app.core.schemas import ResponseData
# ResponseData base carries alias_generator=to_camel — all snake_case fields
# serialize as camelCase automatically. No per-field alias needed.
# price_kopecks → priceKopecks, auto_renew → autoRenew, notif_prefs → notifPrefs
```

### Validation error pattern
**Source:** `app/modules/client_portal/service.py` lines 93-115
**Apply to:** Any new service-layer validation for `notif_prefs` (not needed — schema handles it)
```python
class _InvalidXxxError(ValidationAppError):
    code = "invalid_xxx"
    status_code = 422
```
No new error class needed for `notif_prefs` — `NotifPrefs` schema with `extra='forbid'` (inherited from ResponseData) raises a Pydantic 422 at the route level before reaching the service.

### Cross-module read discipline (repository)
**Source:** `app/modules/client_portal/repository.py` lines 1-17 (module docstring)
**Apply to:** All repository changes
```python
# CROSS-MODULE READ — raw SQL text() only; NO ORM model import from other modules.
# SET clause = fixed string literals (never user-supplied SQL). S608 noqa if needed.
# .mappings().one_or_none() for scalar reads; .mappings().all() for list reads.
```

### Caller-owns-transaction
**Source:** `app/modules/client_portal/repository.py` lines 568-570 docstring
**Apply to:** `update_client_profile` (already applies; notif_prefs addition follows same pattern)
```python
# No session.commit() — caller-owns-txn (D-32-10/D-49-19).
```

### Alembic migration structure
**Source:** `alembic/versions/0048_client_onboarding_fields.py` lines 1-49
**Apply to:** Both new migrations (0050, 0051)
```python
from __future__ import annotations
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0050_..."
down_revision: str | None = "0049_fiscal_receipts_customer_phone"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None: ...
def downgrade() -> None: ...
```

---

## No Analog Found

All files have close analogs. No entries.

---

## Metadata

**Analog search scope:** `apps/backend/app/modules/client_portal/`, `apps/backend/app/modules/clients/`, `apps/backend/app/modules/memberships/`, `apps/backend/app/modules/promo_codes/`, `apps/backend/alembic/versions/`, `apps/backend/scripts/`, `apps/backend/tests/integration/client_portal/`, `apps/backend/tests/modules/client_portal/`
**Files scanned:** 14 source files + migration listing
**Pattern extraction date:** 2026-06-02

**Critical fact for planner:** Latest Alembic revision is `0049_fiscal_receipts_customer_phone`, not `0048`. New migrations must chain as `0050 → 0051`, both with `down_revision` pointing to the correct predecessor.
