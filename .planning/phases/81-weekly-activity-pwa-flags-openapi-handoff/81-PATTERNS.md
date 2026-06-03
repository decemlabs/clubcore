# Phase 81: Weekly Activity + PWA Flag Flips + OpenAPI Handoff — Pattern Map

**Mapped:** 2026-06-03
**Files analyzed:** 8 new/modified files
**Analogs found:** 8 / 8

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `apps/backend/app/modules/client_portal/router.py` | controller | request-response | same file (existing GET read endpoints) | exact |
| `apps/backend/app/modules/client_portal/service.py` | service | CRUD | same file (`get_client_membership` service call) | exact |
| `apps/backend/app/modules/client_portal/repository.py` | repository | CRUD | same file (`fetch_client_visits_page`, `fetch_client_membership`) | exact |
| `apps/backend/app/modules/client_portal/schemas.py` | model | transform | same file (`ClientVisitItem`, `ClientHomeResponse`) | exact |
| `apps/backend/tests/integration/client_portal/test_weekly_activity.py` | test | request-response | `tests/integration/client_portal/test_payment_method_endpoints.py` + `tests/unit/visits/test_schemas.py` | exact |
| `apps/client-pwa/src/lib/clientQueries.ts` | hook | request-response | same file (`useClientHome`, `useRescheduleBooking`, `useCancelBooking`) | exact |
| `apps/client-pwa/src/screens/ProfileScreen.jsx` | component | request-response | same file (flag block ~line 25, hidden card ~line 268) | exact |
| `apps/client-pwa/src/screens/SettingsScreen.jsx` | component | request-response | same file (flag block ~line 15, hidden row ~line 294) | exact |
| `apps/client-pwa/src/screens/sheets/ProfileExtraSheets.jsx` | component | request-response | same file (`CardSheet` ~line 324, `unbindConfirm` confirm modal ~line 413) | exact |
| `apps/backend/scripts/export_openapi.py` | utility | batch | same file (regen script — read-only, no changes needed) | exact |
| `apps/backend/openapi.json` | config | batch | generated artifact (regen via `uv run python -m scripts.export_openapi`) | N/A |
| `packages/api-client/src/schema.d.ts` | config | batch | generated artifact (regen via `pnpm --filter @clubcore/api-client codegen`) | N/A |

---

## Pattern Assignments

### `apps/backend/app/modules/client_portal/router.py` (controller, request-response)

**Analog:** same file — `client_get_membership` handler (lines 144–162) and `client_list_visit_history` (lines 218–234)

**Imports pattern** (lines 30–77):
```python
from __future__ import annotations
from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import ClientPrincipal, require_client
from app.core.schemas import ResponseEnvelope, envelope
from app.modules.client_portal import service
from app.modules.client_portal.schemas import (
    ClientWeeklyActivityResponse,  # new schema to add
    ...
)
```

**Auth + route registration pattern** (lines 144–162):
```python
router = APIRouter(tags=["Client-Portal"])

@router.get(
    "/activity/weekly",
    response_model=ResponseEnvelope[list[ClientWeeklyActivityItem]],
    operation_id="client_get_weekly_activity",
    summary="Weekly workout activity (Mon–Sun, Europe/Moscow, zero-filled) for the authenticated client (WACT-01)",
)
async def client_get_weekly_activity(
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[list[ClientWeeklyActivityItem]]:
    """WACT-01 — own-week activity read, IDOR-safe via client_id from principal.

    No CSRF dep — GET is a safe method (RBAC-04).
    No try/except — AppError bubbles to _app_error_handler.
    D-69-03: empty week → all 7 days workouts=0 (never []).
    D-20-IDOR: client_id injected from cookie principal, not URL param.
    """
    result = await service.get_client_weekly_activity(session, client.id)
    return envelope(result)
```

**Pattern notes:**
- GET endpoint: no `verify_client_csrf` dependency (safe method, RBAC-04)
- No `try/except` — AppError bubbles to `_app_error_handler`
- `envelope(result)` wraps the list in `ResponseEnvelope`
- `operation_id` uses `client_` prefix per D-20-OPENAPI
- Tag is always `"Client-Portal"`

---

### `apps/backend/app/modules/client_portal/service.py` (service, CRUD)

**Analog:** same file — `get_client_membership` function and `list_client_visits` (lines ~100+)

**Service function pattern:**
```python
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

_MSK = ZoneInfo("Europe/Moscow")

async def get_client_weekly_activity(
    session: AsyncSession,
    client_id: UUID,
) -> list[ClientWeeklyActivityItem]:
    """Return 7 zero-filled daily workout counts for the current Moscow week (WACT-01).

    Week anchor: Monday of the current week in Europe/Moscow (isoweekday 1).
    Zero-fill: DB returns only days with visits; service fills all 7 days.
    minutes: always None (no duration column in schema — deferred to v2.3 WACT-03).
    """
    now_msk = datetime.now(_MSK)
    monday = (now_msk - timedelta(days=now_msk.weekday())).date()
    sunday = monday + timedelta(days=6)
    rows = await repository.fetch_weekly_activity(session, client_id, monday, sunday)
    # rows is a dict {date: count} from the raw-SQL aggregate
    return [
        ClientWeeklyActivityItem(
            date=monday + timedelta(days=i),
            workouts=rows.get(monday + timedelta(days=i), 0),
            minutes=None,
        )
        for i in range(7)
    ]
```

**Pattern notes:**
- Service calls `repository.fetch_weekly_activity` and does app-side zero-fill
- Uses `ZoneInfo("Europe/Moscow")` — same import as `fetch_client_membership` repo SQL
- Returns a list (not paginated) — 7 items always
- `minutes=None` always (WACT-01 decision, no duration column)

---

### `apps/backend/app/modules/client_portal/repository.py` (repository, CRUD)

**Analog:** same file — `fetch_client_visits_page` (lines 243–284) and `fetch_client_membership` (lines 169–202)

**Raw-SQL read pattern with Moscow TZ** — `fetch_client_visits_page` lines 260–278:
```python
async def fetch_weekly_activity(
    session: AsyncSession,
    client_id: UUID,
    monday: date,
    sunday: date,
) -> dict[date, int]:
    """Aggregate visit counts per gym_date for the current Moscow week (WACT-01).

    CROSS-MODULE READ — raw SQL text() only; NO ORM import of Visit (D-54-08/D-20-MODULE).
    Verified column source:
      visits (apps/backend/app/modules/visits/models.py:43-113):
        client_id  UUID FK to clients.id
        gym_date   Date STORED GENERATED (checked_in_at AT TIME ZONE 'Europe/Moscow')::date

    Groups on gym_date STORED column — NEVER DATE(checked_in_at) (D-81 TZ contract).
    BETWEEN is inclusive on both ends (Mon..Sun).
    IDOR: mandatory :client_id bind param.
    Returns dict {date: count} — service layer zero-fills missing days.
    """
    rows = (
        await session.execute(
            text(
                "SELECT gym_date, COUNT(*) AS cnt "
                "FROM visits "
                "WHERE client_id = :client_id "
                "  AND gym_date BETWEEN :monday AND :sunday "
                "GROUP BY gym_date "
                "ORDER BY gym_date ASC"
            ),
            {
                "client_id": str(client_id),
                "monday": str(monday),
                "sunday": str(sunday),
            },
        )
    ).mappings().all()
    return {row["gym_date"]: int(row["cnt"]) for row in rows}
```

**Key patterns:**
- `from sqlalchemy import text` — NEVER import another module's ORM model (D-54-08)
- Bind params via `:name` placeholders + dict; UUID cast to `str()`
- `.mappings().all()` for list reads
- `gym_date` is the STORED GENERATED column `(checked_in_at AT TIME ZONE 'Europe/Moscow')::date` — the whole reason TZ test matters. NEVER use `DATE(checked_in_at)`.
- Moscow TZ week boundary in SQL: `fetch_client_membership` line 194 uses `(now() AT TIME ZONE 'Europe/Moscow')::date` — the same timezone casting pattern
- No `CAST(:param AS UUID)` needed for date params (dates bind as strings directly)

**gym_date STORED column** (`apps/backend/app/modules/visits/models.py` lines 77–84):
```python
gym_date: Mapped[date] = mapped_column(
    Date,
    Computed(
        "(checked_in_at AT TIME ZONE 'Europe/Moscow')::date",
        persisted=True,
    ),
    nullable=False,
)
```

---

### `apps/backend/app/modules/client_portal/schemas.py` (model, transform)

**Analog:** same file — `ClientVisitItem` (lines 64–69) and `ClientMembershipResponse` (lines 24–39)

**New schema pattern:**
```python
class ClientWeeklyActivityItem(ResponseData):
    """Single day's workout count for the weekly activity endpoint (WACT-01).

    Ordered Mon→Sun (service constructs the list in day order).
    minutes is always None — no duration column in schema (deferred to WACT-03).
    date wire: ISO date string (date type serialises as YYYY-MM-DD via ResponseData).
    """

    date: date          # wire: date (ISO YYYY-MM-DD)
    workouts: int       # count of visits on this day (0 for days with no visits)
    minutes: int | None = None  # always None in v2.2 (no duration column — WACT-03)
```

**Pattern notes:**
- `ResponseData` base class (not `BackendSchemaBase`) — client-facing output schema
- `date` field type uses Python `datetime.date` (imported at top of file: `from datetime import date, datetime`)
- `from app.core.schemas import BackendSchemaBase, ResponseData` — same import already at top of file

---

### `apps/backend/tests/integration/client_portal/test_weekly_activity.py` (test, request-response)

**Analog A:** `tests/integration/client_portal/test_payment_method_endpoints.py` (lines 1–100) — integration test structure with `_overridden_app`, `http_client`, `stub_otp_sender`, seed helpers, `_auth_as_client`

**Analog B:** `tests/unit/visits/test_schemas.py` (lines 1–134) — golden TZ unit test pattern using `ZoneInfo("Europe/Moscow")`

**Integration test harness pattern** (from `test_payment_method_endpoints.py` lines 48–84):
```python
from __future__ import annotations
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.redis import get_redis
from tests.integration.client_portal.test_idor_sweep import _auth_as_client

pytestmark = pytest.mark.asyncio
_MSK = ZoneInfo("Europe/Moscow")

@pytest_asyncio.fixture
async def _overridden_app(app: FastAPI, db_session: AsyncSession) -> AsyncIterator[FastAPI]:
    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = lambda: app.state.redis
    try:
        yield app
    finally:
        app.dependency_overrides.clear()

@pytest_asyncio.fixture
async def http_client(_overridden_app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=_overridden_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c

@pytest.fixture(autouse=True)
def stub_otp_sender(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    _ = app
    from app.modules.client_auth import service as client_auth_service
    async def _noop(chat_id: int, code: str) -> None:
        pass
    monkeypatch.setattr(client_auth_service, "_client_otp_sender", _noop)
```

**Golden TZ unit test pattern** (v1.8 VER-02 — from `test_schemas.py` / CONTEXT.md):
```python
_MSK = ZoneInfo("Europe/Moscow")

def test_tz_boundary_21_30_utc_lands_in_next_moscow_day() -> None:
    """Golden TZ test (VER-02 pattern): a visit with checked_in_at=21:30 UTC
    has gym_date = the NEXT Moscow calendar day (Moscow is UTC+3, so 21:30 UTC
    = 00:30 MSK next day). Must land in THAT day's workouts bucket, not the
    previous day.

    This is a unit test of the bucketing logic in fetch_weekly_activity / service
    zero-fill: construct a mock DB row as if gym_date were set by the STORED
    column and verify the service assigns it to the correct day.
    """
    # 2026-06-01 21:30 UTC = 2026-06-02 00:30 MSK
    checked_in_at_utc = datetime(2026, 6, 1, 21, 30, tzinfo=UTC)
    expected_gym_date = (checked_in_at_utc.astimezone(_MSK)).date()
    # = 2026-06-02 (the NEXT calendar day in Moscow)
    assert expected_gym_date == date(2026, 6, 2)
    # The STORED column expression: (checked_in_at AT TIME ZONE 'Europe/Moscow')::date
    # gives the same result. The service zero-fill must map this gym_date to
    # the correct Monday-offset index.
```

**Behavior tests to write** (covering WACT-01 and SUCCESS criteria):
1. Empty week → exactly 7 items, all `workouts=0`, `minutes=null`
2. Visit on Monday → Monday bucket has `workouts=1`, all others `workouts=0`
3. Two visits same day → single day bucket has `workouts=2`
4. `minutes` is always `null`
5. Response ordered Mon→Sun
6. IDOR: client_a's visits do not appear in client_b's response

---

### `apps/client-pwa/src/lib/clientQueries.ts` (hook, request-response)

**Analog:** same file — `useClientHome` (lines 131–140, read query), `useRescheduleBooking` (lines 497–525, mutation), `useCancelBooking` (lines 474–489, mutation)

**New key factory entries** (following line 38 pattern):
```typescript
export const clientPortalKeys = {
  // ... existing entries ...
  weeklyActivity: () => [...clientPortalKeys.all, 'weekly-activity'] as const,
  paymentMethod: () => [...clientPortalKeys.all, 'payment-method'] as const,
} as const
```

**useClientWeeklyActivity hook** (mirrors `useClientHome` pattern lines 131–140):
```typescript
interface WeeklyActivityItem {
  date: string        // ISO date YYYY-MM-DD
  workouts: number    // int, 0 for no-workout days
  minutes: null       // always null in v2.2 (WACT-01)
}

/** GET /api/v1/client/activity/weekly — 7-item Mon→Sun array for current Moscow week (WACT-01) */
export function useClientWeeklyActivity() {
  return useQuery({
    queryKey: clientPortalKeys.weeklyActivity(),
    queryFn: async () => {
      const res = await clientRequest('get', '/api/v1/client/activity/weekly')
      return (res as { data: WeeklyActivityItem[] }).data
    },
    staleTime: 30_000,
  })
}
```

**useClientPaymentMethod read hook** (mirrors `useClientMembership` lines 165–175):
```typescript
interface PaymentMethodData {
  last4: string
  brand: string
  expiryMonth: number
  expiryYear: number
  autopayEnabled: boolean
  consentRecordedAt: string | null
}

/** GET /api/v1/client/payment-method — active payment method or null (PAYM-02) */
export function useClientPaymentMethod() {
  return useQuery({
    queryKey: clientPortalKeys.paymentMethod(),
    queryFn: async () => {
      const res = await clientRequest('get', '/api/v1/client/payment-method')
      return (res as { data: PaymentMethodData | null }).data
    },
    staleTime: 30_000,
  })
}
```

**useUnlinkPaymentMethod mutation** (mirrors `useCancelBooking` lines 474–489):
```typescript
/** DELETE /api/v1/client/payment-method — soft-delete card (PAYM-03) */
export function useUnlinkPaymentMethod() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      await clientRequest('delete', '/api/v1/client/payment-method')
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: clientPortalKeys.paymentMethod() })
    },
  })
}
```

**usePatchAutopay mutation** (mirrors `useRescheduleBooking` lines 497–525 for body pattern):
```typescript
/** PATCH /api/v1/client/payment-method/autopay — enable/disable autopay (PAYM-04) */
export function usePatchAutopay() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      enabled,
      consentAcknowledged,
    }: {
      enabled: boolean
      consentAcknowledged: boolean
    }) => {
      const res = await clientRequest('patch', '/api/v1/client/payment-method/autopay', {
        body: { enabled, consentAcknowledged },
      })
      return (res as { data: PaymentMethodData }).data
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: clientPortalKeys.paymentMethod() })
    },
  })
}
```

**Pattern notes:**
- All new hooks follow `staleTime: 30_000` global convention
- Mutations use `onSettled` (not `onSuccess`) for cache invalidation — mirrors existing hooks
- CSRF is handled automatically by `clientRequest` (cookie-based, transparent to hooks)
- `consentAcknowledged` must be `true` when `enabled: true` (ФЗ-376 — backend enforces 409 `consent_required` if missing)

---

### `apps/client-pwa/src/screens/ProfileScreen.jsx` (component, request-response)

**Analog:** same file — feature flag block (lines 18–30) and hidden card markup (lines 267–285)

**Feature flag block** (lines 25–30 — flip `weeklyActivity` and `linkedCard`):
```jsx
const PROFILE_FEATURE_FLAGS = {
  weeklyActivity: true,   // FLIP: was false — wired to GET /client/activity/weekly (WACT-02)
  tenureBadge:    false,
  weeksStat:      false,
  linkedCard:     true,   // FLIP: was false — wired to CardSheet + payment-method API (PAYM-05)
};
```

**Hidden activity-bars card** (lines 267–285 — wire to `useClientWeeklyActivity`):
```jsx
{/* BUILT, HIDDEN: weekly activity card — now wired to GET /client/activity/weekly */}
{PROFILE_FEATURE_FLAGS.weeklyActivity && (
  <div style={{ padding: '0 16px 18px' }}>
    <div className="card fade-up" style={{ padding: 14 }}>
      <div className="row-between" style={{ alignItems: 'center' }}>
        <span className="t-mini" style={{ color: 'var(--text-3)' }}>Активность за неделю</span>
      </div>
      {/* Activity bars — wired to useClientWeeklyActivity() */}
      <div style={{ height: 60, display: 'flex', alignItems: 'flex-end', gap: 7, marginTop: 12 }}>
        {/* Replace static placeholder with real data from hook */}
        {['Пн','Вт','Ср','Чт','Пт','Сб','Вс'].map(d => (
          <div key={d} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 7 }}>
            <div style={{ width: '100%', height: 40, borderRadius: 6, background: 'var(--border-strong)' }} />
            <span style={{ fontSize: 9.5, fontWeight: 500, color: 'var(--text-3)' }}>{d}</span>
          </div>
        ))}
      </div>
    </div>
  </div>
)}
```

**Wire pattern:** call `useClientWeeklyActivity()` at the top of the component (same location as other hooks on lines 9–16), destructure `{ data: weeklyActivity }`, compute bar heights from `workouts` count relative to the week's max.

**Import addition:** add `useClientWeeklyActivity` to the `from '@/data'` import block at lines 9–16.

---

### `apps/client-pwa/src/screens/SettingsScreen.jsx` (component, request-response)

**Analog:** same file — feature flag block (lines 15–18) and hidden card row (lines 293–298)

**Feature flag block** (lines 15–18 — flip `linkedCard`):
```jsx
const SETTINGS_FEATURE_FLAGS = {
  linkedCard:  true,   // FLIP: was false — wired to CardSheet + payment-method endpoints (PAYM-05)
  tenureBadge: false,
};
```

**Hidden card row** (lines 293–298 — already renders `onOpenCard`; just flip flag):
```jsx
{/* Привязанная карта — now wired via SETTINGS_FEATURE_FLAGS.linkedCard = true */}
{SETTINGS_FEATURE_FLAGS.linkedCard && (
  <>
    <Divider2 />
    <NavRow label="Привязанная карта" value="•••• 4821" onClick={onOpenCard} />
  </>
)}
```

**Live data wire:** `onOpenCard` already calls `CardSheet` (via `ProfileExtraSheets.jsx`). After flag flip, the `value="•••• 4821"` placeholder should be replaced with real `last4` from `useClientPaymentMethod()`. When `data === null` (no card), show `"Добавить"` or hide the row.

**Import addition:** add `useClientPaymentMethod` to the `from '@/data'` import (currently line 6: `import { useClientMe, useUpdateClientProfile } from '@/data'`).

---

### `apps/client-pwa/src/screens/sheets/ProfileExtraSheets.jsx` (component, request-response)

**Analog:** same file — `CardSheet` component (lines 323–450+) and `unbindConfirm` confirm modal (lines 413–449)

**CardSheet existing structure** (lines 323–450) — wire the following changes:

1. **Replace static card visual** with data from `useClientPaymentMethod()`:
   - `•••• 4821` → `•••• {data.last4}`
   - `09 / 28` → `{data.expiryMonth.toString().padStart(2,'0')} / {String(data.expiryYear).slice(-2)}`
   - `ALEXANDRA Z.` → omit or show generic "КАРТА CLUBCORE" (no cardholder name in API)

2. **Autopay toggle** — keep only `«Авто-продление абонемента»`; **remove** `«Авто-оплата тренировок»` toggle (lines 393–394) — it is the anti-feature per CONTEXT.md.

3. **Wire unbind action** to `useUnlinkPaymentMethod()` mutation (replace `setUnbound(true)` mock with real DELETE call). The existing `unbindConfirm` modal (lines 413–449) is the correct UX pattern — reuse it with the mutation.

4. **ФЗ-376 consent modal** for autopay enable — follows the same bottom-sheet confirm pattern as `unbindConfirm` (lines 413–449):

```jsx
{/* ФЗ-376 consent disclosure — shown before enabling autopay */}
{autopayConsentOpen && (
  <div style={{
    position: 'absolute', inset: 0, zIndex: 30,
    background: 'rgba(0,0,0,0.45)',
    display: 'flex', alignItems: 'flex-end', justifyContent: 'center',
    animation: 'ctx-fade 0.2s ease-out',
  }} onClick={() => setAutopayConsentOpen(false)}>
    <div onClick={(e) => e.stopPropagation()} style={{
      width: 'calc(100% - 24px)', margin: '0 12px 12px',
      background: 'var(--surface)', borderRadius: 20, padding: 20,
      boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
      animation: 'sheet-up 0.28s cubic-bezier(0.32, 0.72, 0.2, 1)',
    }}>
      <div className="t-h2" style={{ fontSize: 18 }}>Подключить автопродление?</div>
      <div className="t-small" style={{ marginTop: 6, color: 'var(--text-2)', lineHeight: 1.6 }}>
        {/* ФЗ-376 required: amount + periodicity + cancellation method */}
        Сумма списания — стоимость текущего тарифа. Списывается за 3 дня до окончания
        абонемента. Отключить можно в любой момент в настройках карты.
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
        <button onClick={() => setAutopayConsentOpen(false)} className="press" style={{
          flex: 1, height: 46, borderRadius: 999, border: '0.5px solid var(--border-strong)',
          background: 'transparent', color: 'var(--text)',
          fontFamily: 'inherit', fontSize: 15, fontWeight: 600, cursor: 'pointer',
        }}>
          Отмена
        </button>
        <button onClick={handleEnableAutopayWithConsent} className="press" style={{
          flex: 2, height: 46, borderRadius: 999, border: 'none',
          background: 'var(--accent)', color: '#06120c',
          fontFamily: 'inherit', fontSize: 15, fontWeight: 700, cursor: 'pointer',
        }}>
          Подключить
        </button>
      </div>
    </div>
  </div>
)}
```

**`handleEnableAutopayWithConsent` calls:**
```jsx
await patchAutopay.mutateAsync({ enabled: true, consentAcknowledged: true })
```

**Disable autopay** — no consent modal needed; call directly:
```jsx
await patchAutopay.mutateAsync({ enabled: false, consentAcknowledged: false })
```

**State management pattern** (mirrors `unbindConfirm` line 325):
```jsx
const [autopayConsentOpen, setAutopayConsentOpen] = React.useState(false)
const patchAutopay = usePatchAutopay()
const unlinkCard = useUnlinkPaymentMethod()
```

---

## Shared Patterns

### Authentication / IDOR Guard
**Source:** `apps/backend/app/modules/client_portal/router.py` lines 150–162
**Apply to:** `client_get_weekly_activity` endpoint
```python
client: Annotated[ClientPrincipal, Depends(require_client())],
```
- `client_id` comes ONLY from `client.id` — NEVER from URL params or body
- No `verify_client_csrf` for GET endpoints (safe method, RBAC-04)

### Raw-SQL Repository Pattern (D-54-08)
**Source:** `apps/backend/app/modules/client_portal/repository.py` lines 1–18
**Apply to:** `fetch_weekly_activity` in `repository.py`
```python
from sqlalchemy import text
# NO ORM model imports from other modules
# Bind params via :name + dict; UUID → str()
# .mappings().all() for list reads
```

### ResponseEnvelope Wrapping
**Source:** `apps/backend/app/modules/client_portal/router.py` lines 158–162
**Apply to:** new endpoint handler
```python
from app.core.schemas import ResponseEnvelope, envelope
return envelope(result)
```

### Moscow TZ in SQL
**Source:** `apps/backend/app/modules/client_portal/repository.py` line 194 (`fetch_client_membership`)
```sql
(now() AT TIME ZONE 'Europe/Moscow')::date
```
**Apply to:** `fetch_weekly_activity` week-boundary anchor and `gym_date` grouping column. Use `CAST(:param AS DATE)` or plain string date bind — no `::date` cast on params (conflicts with asyncpg text() param substitution).

### TanStack Query Hook Convention
**Source:** `apps/client-pwa/src/lib/clientQueries.ts` lines 131–140
**Apply to:** all new hooks
```typescript
staleTime: 30_000,
// mutations: onSettled (not onSuccess) for invalidation
void qc.invalidateQueries({ queryKey: clientPortalKeys.xxx() })
```

### Bottom-Sheet Confirm Modal
**Source:** `apps/client-pwa/src/screens/sheets/ProfileExtraSheets.jsx` lines 413–449
**Apply to:** ФЗ-376 consent disclosure + unbind confirmation
```jsx
// animation: 'ctx-fade 0.2s ease-out' on overlay
// animation: 'sheet-up 0.28s cubic-bezier(0.32, 0.72, 0.2, 1)' on content
// onClick backdrop dismisses; stopPropagation on content
```

### Error Handling in PWA Mutations
**Source:** `apps/client-pwa/src/screens/sheets/BookingManageSheet.jsx` lines 177–190
**Apply to:** CardSheet mutation calls
```jsx
try {
  await mutation.mutateAsync(...)
  // success state
} catch (err) {
  const code = err && typeof err === 'object' && 'code' in err ? err.code : null
  if (code === 'consent_required') {
    // show consent modal
  } else {
    // generic error message
  }
}
```

---

## OpenAPI Handoff (HND-01)

### Export script (no changes needed)
**Source:** `apps/backend/scripts/export_openapi.py` lines 1–80

**Run command:**
```bash
cd apps/backend
uv run python -m scripts.export_openapi
```

**Key invariants:**
- `os.environ.setdefault('ENVIRONMENT', 'dev')` MUST precede `from app.main` (line 31)
- `indent=2, sort_keys=True, ensure_ascii=False` + trailing newline = byte-stable (line 69)
- Staff contract must be byte-identical — only new `/client/activity/weekly` path is additive

### CI Drift Gate commands
**Source:** `.github/workflows/ci.yml` lines 90–94 (backend) and 159–162 (frontend)

**Backend gate** (lines 90–94):
```bash
git ls-files --error-unmatch apps/backend/openapi.json
git diff --exit-code apps/backend/openapi.json
```

**Frontend gate** (lines 159–162):
```bash
pnpm --filter @clubcore/api-client codegen   # regen schema.d.ts
git ls-files --error-unmatch packages/api-client/src/schema.d.ts
git diff --exit-code packages/api-client/src/schema.d.ts
```

**Local verification sequence:**
```bash
# 1. Regen openapi.json
cd apps/backend && uv run python -m scripts.export_openapi

# 2. Regen schema.d.ts
pnpm --filter @clubcore/api-client codegen

# 3. Verify drift gates pass (both must exit 0)
git diff --exit-code apps/backend/openapi.json
git diff --exit-code packages/api-client/src/schema.d.ts

# 4. Redocly lint
npx -y @redocly/cli@latest lint apps/backend/openapi.json
```

---

## No Analog Found

All files have close analogs in the existing codebase. No files require referencing RESEARCH.md patterns.

---

## Metadata

**Analog search scope:** `apps/backend/app/modules/client_portal/`, `apps/backend/tests/integration/client_portal/`, `apps/backend/tests/unit/visits/`, `apps/client-pwa/src/lib/`, `apps/client-pwa/src/screens/`, `apps/client-pwa/src/screens/sheets/`, `apps/backend/scripts/`, `.github/workflows/`
**Files scanned:** 14
**Pattern extraction date:** 2026-06-03
