# Phase 116: Chat Inbox & Exports — Pattern Map

**Mapped:** 2026-06-15
**Files analyzed:** 13 new/modified files
**Analogs found:** 13 / 13

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `apps/backend/app/modules/messaging/staff_router.py` (new) | router | request-response | `apps/backend/app/modules/messaging/router.py` | role-match (same module, staff vs client side) |
| `apps/backend/app/modules/messaging/staff_repository.py` (new fns or extend repository.py) | repository | CRUD | `apps/backend/app/modules/messaging/repository.py` | exact |
| `apps/backend/app/modules/messaging/staff_service.py` (new fns or extend service.py) | service | request-response | `apps/backend/app/modules/messaging/service.py` | exact |
| `apps/backend/app/core/permissions.py` (modify) | config | — | self (add Resource.MESSAGES + OWNER_ONLY pair) | exact — Phase 113 PROMO_CODES block is the template |
| `apps/backend/app/modules/reports/constants.py` (modify) | config | — | self (add CSV_PAYMENTS_HEADERS) | exact |
| `apps/backend/app/modules/reports/router.py` (modify) | router | streaming | `apps/backend/app/modules/reports/router.py` lines 190–209 (get_visits_csv) | exact |
| `apps/backend/app/modules/reports/service.py` (modify) | service | CRUD | `apps/backend/app/modules/reports/service.py` lines 402–413 (visits_csv_rows) | exact |
| `apps/backend/tests/integration/messaging/` (new) | test | request-response | `apps/backend/tests/integration/reports/test_csv_export.py` | role-match |
| `apps/backend/tests/integration/test_rbac_parity.py` (modify count) | test | — | self | exact |
| `apps/backend/tests/unit/test_permissions.py` (modify count) | test | — | self | exact |
| `apps/admin-app/src/features/messages/api.ts` (replace) | hook | request-response | `apps/admin-app/src/features/reports/api.ts` | exact |
| `apps/admin-app/src/features/messages/types.ts` (extend) | model | — | self (add StaffThread, StaffMessage wire types) | exact |
| `apps/admin-app/src/shared/session/can.ts` + `registry.ts` (modify) | config | — | self (Phase 113 promo-codes block as template) | exact |
| `apps/admin-app/src/pages/messages/MessagesPage.tsx` (modify) | component | request-response | self + `apps/admin-app/src/features/reports/api.ts` (staffRequest pattern) | exact |
| `apps/admin-app/src/pages/cashbox/`, `finance/`, `attendance/` (add export button) | component | file-I/O | `apps/admin-app/src/pages/messages/MessagesPage.tsx` (can() gate) | role-match |

---

## Pattern Assignments

### `apps/backend/app/modules/messaging/staff_router.py` (router, request-response)

**Analog:** `apps/backend/app/modules/messaging/router.py` + `apps/backend/app/modules/reports/router.py`

**Module docstring pattern** (messaging/router.py lines 1–29):
```python
"""Staff messaging endpoints (Phase 116 MSG-01..02).

Mounted under /api/v1 via staff_messaging_router — separate from the client
router at /api/v1/client (D-20-MODULE pattern; same split as notifications_router).

Endpoints:
  GET  /api/v1/messages/threads                    → StaffInboxResponse (paginated)
  GET  /api/v1/messages/threads/{thread_id}        → StaffThreadHistoryResponse
  POST /api/v1/messages/threads/{thread_id}/reply  → MessageResponse (owner-only)
  POST /api/v1/messages/threads/{thread_id}/read   → 204 No Content

RBAC-04 ordering: require_permission BEFORE verify_csrf on all mutation endpoints.
(CREATE, MESSAGES) ∈ OWNER_ONLY → reception POST /reply → 403.
(LIST, MESSAGES) and (VIEW, MESSAGES) NOT in OWNER_ONLY → reception can read.

No try/except — AppError bubbles to _app_error_handler.
"""
```

**Imports pattern** (mirror reports/router.py lines 27–44):
```python
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission, verify_csrf
from app.core.permissions import Action, Resource
from app.core.schemas import ResponseEnvelope, envelope
from app.modules.messaging import staff_repository, staff_service
from app.modules.messaging.schemas import (
    StaffInboxResponse,
    StaffThreadHistoryResponse,
    StaffReplyRequest,
)
```

**READ endpoint pattern** (mirror reports/router.py lines 70–89, require_permission on GET — no verify_csrf):
```python
router = APIRouter(tags=["Messaging"])

@router.get(
    "/threads",
    response_model=ResponseEnvelope[StaffInboxResponse],
    operation_id="staff_list_threads",
    summary="Staff inbox: all client threads with unread counts (LIST, MESSAGES; both roles)",
)
async def staff_list_threads(
    _actor: Annotated[CurrentUser, Depends(require_permission(Action.LIST, Resource.MESSAGES))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[StaffInboxResponse]:
    result = await staff_service.list_threads(session)
    return envelope(result)
```

**MUTATION endpoint RBAC-04 ordering** — require_permission BEFORE verify_csrf (pt_sessions/router.py lines 75–77):
```python
@router.post(
    "/threads/{thread_id}/reply",
    response_model=ResponseEnvelope[MessageResponse],
    operation_id="staff_send_reply",
    summary="Staff send reply (CREATE, MESSAGES; owner-only)",
)
async def staff_send_reply(
    thread_id: UUID,
    payload: StaffReplyRequest,
    _actor: Annotated[CurrentUser, Depends(require_permission(Action.CREATE, Resource.MESSAGES))],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[MessageResponse]:
    result = await staff_service.send_staff_reply(session, thread_id=thread_id, payload=payload)
    await session.commit()
    return envelope(result)
```

**204 mark-read endpoint** (mirror client router lines 105–127):
```python
@router.post(
    "/threads/{thread_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="staff_mark_thread_read",
    summary="Reset staff-side unread for thread (both roles)",
)
async def staff_mark_thread_read(
    thread_id: UUID,
    _actor: Annotated[CurrentUser, Depends(require_permission(Action.VIEW, Resource.MESSAGES))],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    await staff_service.mark_staff_thread_read(session, thread_id=thread_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

---

### `apps/backend/app/modules/messaging/repository.py` — new staff functions (repository, CRUD)

**Analog:** `apps/backend/app/modules/messaging/repository.py` (existing file — append new functions)

**Cross-module read discipline** (repository.py lines 1–18 — apply to new fns):
```python
# D-54-08: raw SQL text() + :name bind params + str(UUID) casts for all reads.
# No session.commit() — caller-owns-txn (D-32-10/D-49-19).
```

**list_all_threads_with_unread** — copy SELECT shape from `list_thread_history` (lines 172–238), but query all threads (no client_id filter), join on `messages` to derive `staff_unread_count` via `staff_last_read_at`:
```python
async def list_all_threads_with_unread(
    session: AsyncSession,
) -> list[dict[str, Any]]:
    """Return all threads with staff_unread_count, last_message_at, last_message preview.

    staff_unread_count = COUNT(*) of messages WHERE role='client'
    AND sent_at > staff_last_read_at (NULL staff_last_read_at → count all client msgs).
    Cross-module client name via raw SQL text() (D-54-08).
    No session.commit() — caller-owns-txn.
    """
    rows = (
        await session.execute(
            text(
                "SELECT "
                "  mt.id, mt.client_id, mt.last_message_at, "
                "  mt.staff_last_read_at, "
                "  ( SELECT COUNT(*) FROM messages m "
                "    WHERE m.thread_id = mt.id AND m.role = 'client' "
                "    AND (mt.staff_last_read_at IS NULL OR m.sent_at > mt.staff_last_read_at) "
                "  ) AS staff_unread_count, "
                "  ( SELECT m2.body FROM messages m2 "
                "    WHERE m2.thread_id = mt.id "
                "    ORDER BY m2.sent_at DESC LIMIT 1 "
                "  ) AS last_message_body, "
                "  ( SELECT m3.role FROM messages m3 "
                "    WHERE m3.thread_id = mt.id "
                "    ORDER BY m3.sent_at DESC LIMIT 1 "
                "  ) AS last_message_role, "
                "  c.first_name, c.last_name "
                "FROM message_threads mt "
                "JOIN clients c ON c.id = mt.client_id AND c.deleted_at IS NULL "
                "ORDER BY mt.last_message_at DESC NULLS LAST"
            )
        )
    ).mappings().all()
    return [dict(r) for r in rows]
```

**mark_staff_thread_read** — copy `mark_thread_read` pattern (lines 387–439), but update `staff_last_read_at` instead of `client_unread_count`:
```python
async def mark_staff_thread_read(
    session: AsyncSession,
    thread_id: UUID,
) -> None:
    """Set staff_last_read_at = now() for thread; staff unread is derived from this watermark.

    No RETURNING needed (no counter recomputation — unread is derived on read).
    No session.commit() — caller-owns-txn.
    """
    await session.execute(
        text(
            "UPDATE message_threads "
            "SET staff_last_read_at = now(), updated_at = now() "
            "WHERE id = :tid"
        ),
        {"tid": str(thread_id)},
    )
```

**Reuse `insert_message(role='staff')`** (lines 67–139) verbatim — no changes needed. The existing function already bumps `last_message_at` and `client_unread_count` when `role='staff'`.

**Reuse `list_thread_history`** (lines 142–238) for `GET /threads/{id}` — call with `client_id` resolved from `thread_id` via a new `get_thread_client_id` helper (raw SQL text()).

---

### `apps/backend/app/modules/messaging/service.py` — new staff service functions

**Analog:** `apps/backend/app/modules/messaging/service.py` + `apps/backend/app/modules/reports/service.py`

**Existing dispatch reuse** (service.py lines 63–80): staff reply calls `repository.insert_message(role='staff')` then triggers the EXISTING `publish_new_message(redis, client_id=..., message_id=...)` AFTER commit (CR-02 / DB-first). Also enqueues `forward_to_staff` ARQ job per router.py lines 294–321 pattern — BUT for staff send there is NO forward_to_staff (that's client→staff bridge; staff sends go directly to WS + client Telegram).

**Staff send service pattern:**
```python
async def send_staff_reply(
    session: AsyncSession,
    redis: Redis,
    *,
    thread_id: UUID,
    payload: StaffReplyRequest,
) -> MessageResponse:
    """Persist staff reply via insert_message(role='staff'); caller publishes after commit.

    Reuses existing insert_message which bumps last_message_at + client_unread_count.
    No try/except — AppError bubbles to _app_error_handler.
    No session.commit() — caller-owns-txn (D-32-10/D-49-19).
    """
    message_id, sent_at = await repository.insert_message(
        session,
        thread_id=thread_id,
        role="staff",
        body=payload.body,
    )
    return MessageResponse(id=message_id, thread_id=thread_id, ...)
```

---

### `apps/backend/app/core/permissions.py` — add Resource.MESSAGES + OWNER_ONLY pair

**Analog:** `apps/backend/app/core/permissions.py` — Phase 113 PROMO_CODES block (lines 61–63 + 153–157)

**Resource enum addition** (copy style from PROMO_CODES at line 62):
```python
MESSAGES = "messages"  # Phase 116 — staff chat inbox; (CREATE, MESSAGES) owner-only send
```

**OWNER_ONLY addition** (copy Phase 113 comment style, lines 153–157):
```python
# Phase 116 — staff chat inbox: reception can LIST/VIEW threads; only owner can CREATE (send).
# (LIST, MESSAGES) and (VIEW, MESSAGES) NOT in OWNER_ONLY — intentionally omitted.
(Action.CREATE, Resource.MESSAGES),
```

**Count bump:** 45 → 46 (one new pair). Update both `test_owner_only_has_exactly_forty_five_entries` (unit) and `test_owner_only_count_is_forty_five` (integration) to 46.

---

### `apps/backend/app/modules/reports/constants.py` — add CSV_PAYMENTS_HEADERS

**Analog:** `apps/backend/app/modules/reports/constants.py` lines 30–37 (CSV_REVENUE_HEADERS)

**Pattern to copy** (camelCase wire labels matching payments ledger fields):
```python
CSV_PAYMENTS_HEADERS: tuple[str, ...] = (
    "date",           # received_at MSK date
    "clientName",     # client first_name + last_name
    "amountRubles",   # amount_kopecks / 100 (format_kopecks_as_rubles)
    "method",         # 'cash' | 'online'
    "subjectKind",    # 'membership' | 'pt_package' | 'refund' | ...
    "refundOf",       # UUID of original payment or empty string
    "operatorEmail",  # received_by user email snapshot
)
```

Add to `__all__` tuple (lines 97–115 pattern).

---

### `apps/backend/app/modules/reports/router.py` — add GET /reports/payments.csv

**Analog:** `apps/backend/app/modules/reports/router.py` lines 190–209 (`get_visits_csv`)

**Pattern to copy exactly** (StreamingResponse, no ResponseEnvelope, require_permission BEFORE session):
```python
@router.get(
    "/payments.csv",
    response_class=StreamingResponse,
    summary="Payments ledger CSV download — one row per payment (owner-only; EXP-XX)",
)
async def get_payments_csv(
    from_date: Annotated[date, Query(alias="fromDate")],
    to_date: Annotated[date, Query(alias="toDate")],
    _actor: Annotated[CurrentUser, Depends(require_permission(Action.VIEW, Resource.REPORTS))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    """Stream payments ledger as UTF-8 BOM + RFC-4180 CSV.

    Owner-only: (VIEW, REPORTS) ∈ OWNER_ONLY; reception → 403.
    Range cap: 366 days; toDate < fromDate → 422.
    No try/except — errors bubble to _app_error_handler.
    """
    filename = f"payments-{from_date.isoformat()}-{to_date.isoformat()}.csv"
    rows = await service.payments_csv_rows(session, from_date=from_date, to_date=to_date)
    return csv_export.make_csv_streaming_response(iter(rows), CSV_PAYMENTS_HEADERS, filename)
```

Add `CSV_PAYMENTS_HEADERS` to the imports block (lines 38–44 pattern).

---

### `apps/backend/app/modules/reports/service.py` — add payments_csv_rows

**Analog:** `apps/backend/app/modules/reports/service.py` lines 402–413 (`visits_csv_rows`)

**Pattern to copy** (thin orchestrator calling repository, no commit, return list of rows):
```python
async def payments_csv_rows(
    session: AsyncSession,
    *,
    from_date: date,
    to_date: date,
) -> list[list[object]]:
    """Build payments CSV data rows from ledger query (EXP-XX).

    Reuses repository.fetch_payments_for_csv (cross-module read via raw SQL text(), D-54-08).
    Formats amounts via csv_export.format_kopecks_as_rubles (D-13).
    Dates formatted as ISO 'YYYY-MM-DD' MSK.
    No session.commit() — caller-owns-txn.
    """
    _validate_date_range(from_date, to_date)
    raw_rows = await repository.fetch_payments_for_csv(session, from_date, to_date)
    return [
        [
            row["received_at_msk"],         # date string
            row["client_name"],             # sanitize_csv_text() — free text
            csv_export.format_kopecks_as_rubles(int(row["amount_kopecks"])),
            row["method"],
            row["subject_kind"],
            str(row["refund_of"]) if row["refund_of"] else "",
            csv_export.sanitize_csv_text(str(row["operator_email"] or "")),
        ]
        for row in raw_rows
    ]
```

Note: `csv_export.sanitize_csv_text()` (lines 38–59 of csv_export.py) must be applied to free-text cells `client_name` and `operator_email` (formula injection guard, CR-01).

---

### `apps/backend/tests/integration/messaging/` — new test file

**Analog:** `apps/backend/tests/integration/reports/test_csv_export.py`

**Test structure pattern** (same conftest pattern — `authed_client_owner`, `authed_client_reception`, `async_client`):

```python
"""Integration tests for staff messaging endpoints (Phase 116 MSG-01..02).

Coverage:
  - GET /api/v1/messages/threads as owner → 200 + StaffInboxResponse shape
  - GET /api/v1/messages/threads as reception → 200 (both roles allowed)
  - GET /api/v1/messages/threads/{id} as owner → 200 + thread history shape
  - POST /api/v1/messages/threads/{id}/reply as owner → 200
  - POST /api/v1/messages/threads/{id}/reply as reception → 403 "forbidden"
    ((CREATE, MESSAGES) ∈ OWNER_ONLY)
  - POST /api/v1/messages/threads/{id}/read as owner → 204
  - POST /api/v1/messages/threads/{id}/read as reception → 204 (both roles)
  - Empty inbox: GET /api/v1/messages/threads with no threads → 200 + empty items
"""

async def test_staff_reply_reception_forbidden(
    authed_client_reception: AsyncClient,
    seeded_thread: Any,
) -> None:
    """(CREATE, MESSAGES) ∈ OWNER_ONLY → reception 403 on POST /reply."""
    r = await authed_client_reception.post(
        f"/api/v1/messages/threads/{seeded_thread.id}/reply",
        json={"body": "test"},
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"
```

**CSV test for payments** (copy `test_visits_csv_bom_and_content_type`, `test_visits_csv_reception_forbidden` pattern from test_csv_export.py lines 85–100, 191–200):
```python
async def test_payments_csv_bom_and_content_type(
    authed_client_owner: AsyncClient,
) -> None:
    r = await authed_client_owner.get(
        "/api/v1/reports/payments.csv",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/csv")
    assert r.text[0] == BOM

async def test_payments_csv_reception_forbidden(
    authed_client_reception: AsyncClient,
) -> None:
    r = await authed_client_reception.get(
        "/api/v1/reports/payments.csv",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"
```

---

### `apps/admin-app/src/features/messages/api.ts` — replace mock with real hooks

**Analog:** `apps/admin-app/src/features/reports/api.ts` (full file — staffRequest + Zod + keys pattern)

**Current file** (lines 1–21) uses `mockResponse` — replace entirely.

**Keys factory** (copy `reportsQueryKeys` factory pattern from reports/api.ts line 19):
```typescript
export const messagesKeys = {
  all: ['messages'] as const,
  threads: () => ['messages', 'threads'] as const,
  thread: (id: string) => ['messages', 'threads', id] as const,
} as const
```

**useThreads hook** (copy useVisitsReport structure, add refetchInterval override):
```typescript
export function useThreads() {
  return useQuery({
    queryKey: messagesKeys.threads(),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/messages/threads')
      return StaffInboxSchema.parse(raw).data
    },
    staleTime: 0,
    refetchInterval: 15_000,
    refetchOnWindowFocus: true,  // overrides global false for inbox only
  })
}
```

**useThread hook** (read-only, no role gate):
```typescript
export function useThread(threadId: string | null) {
  return useQuery({
    queryKey: messagesKeys.thread(threadId ?? ''),
    queryFn: async () => {
      const raw = await staffRequest('get', `/api/v1/messages/threads/${threadId}`)
      return StaffThreadSchema.parse(raw).data
    },
    enabled: !!threadId,
    staleTime: 30_000,
  })
}
```

**useSendReply mutation** (copy useMutation pattern from payroll/api.ts lines 17–57, with queryClient invalidation on both keys):
```typescript
export function useSendReply(threadId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: string) => {
      return staffRequest('post', `/api/v1/messages/threads/${threadId}/reply`, {
        body: { body },
      })
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: messagesKeys.thread(threadId) })
      void queryClient.invalidateQueries({ queryKey: messagesKeys.threads() })
    },
    onError: () => {
      toast.error('Не удалось отправить сообщение. Попробуйте ещё раз.')
    },
  })
}
```

**useMarkThreadRead mutation** (fire-and-forget, no toast on error):
```typescript
export function useMarkThreadRead() {
  return useMutation({
    mutationFn: async (threadId: string) =>
      staffRequest('post', `/api/v1/messages/threads/${threadId}/read`, { body: {} }),
  })
}
```

---

### `apps/admin-app/src/features/messages/types.ts` — add wire types

**Analog:** self (existing types.ts lines 1–108) + `apps/admin-app/src/features/reports/api.ts` (Zod schema pattern)

Add to existing file — do NOT remove `Conversation`, `ThreadItem`, etc. (still used by components):

```typescript
// Wire types for real staff endpoints (Phase 116)
export interface StaffThread {
  id: string
  clientId: string
  clientName: string
  clientInitials: string
  lastMessageAt: string        // ISO
  lastMessageBody: string | null
  lastMessageRole: 'client' | 'staff' | null
  staffUnreadCount: number
}

export interface StaffMessage {
  id: string
  role: 'client' | 'staff'
  body: string
  sentAt: string               // ISO
}

export interface StaffInboxData {
  items: StaffThread[]
  total: number
}

export interface StaffThreadData {
  threadId: string
  messages: StaffMessage[]
}
```

---

### `apps/admin-app/src/pages/messages/MessagesPage.tsx` — wire mock→real

**Analog:** self (lines 1–54) — structure is preserved; only data source changes

**Key wiring changes:**

Replace `useMessages()` with `useThreads()` + `useThread(activeId)` + `useMarkThreadRead()` + `useSendReply(activeId)`.

```typescript
// Replace lines 1-4 import block:
import { useThreads, useThread, useMarkThreadRead } from '@/features/messages/api'

// Replace onSelect handler (lines 21-27) to call mark-read:
const markRead = useMarkThreadRead()
const onSelect = (id: string) => {
  setActiveId(id)
  markRead.mutate(id)   // fire-and-forget
}
```

**Empty inbox state** (replace `if (data.conversations.length === 0) return null` at line 17):
```typescript
if (threads.length === 0) return (
  <div className="...">
    <MessagesPageHead unread={0} mine={0} />
    <EmptyState
      icon={MessageSquare}
      title="Нет активных диалогов"
      body="Как только клиент напишет, диалог появится здесь."
    />
  </div>
)
```

**Component props mapping** — map `StaffThread[]` to existing `Conversation[]` shape (same structure as current mock data). The existing `ConversationList`, `ThreadPane`, `ClientPanel` props interfaces remain unchanged.

---

### `apps/admin-app/src/shared/session/can.ts` — add MESSAGES resource + owner-only pair

**Analog:** self — Phase 113 promo-codes block (lines 82–87)

**Resource addition** in `registry.ts` (add to union, copy style from line 29):
```typescript
| 'messages' // NEW Phase 116 — staff chat inbox; (create, messages) owner-only send
```

**OWNER_ONLY addition** in `can.ts` (copy Phase 113 comment style):
```typescript
// Phase 116 — staff chat inbox: only owner can send (create); both roles can read.
// (list, messages) and (view, messages) intentionally NOT in OWNER_ONLY.
{ action: 'create', resource: 'messages' },
```

Count: 45 → 46 pairs. Update count comment in can.ts header.

**No new Action value** — reuses existing `'create'`, `'list'`, `'view'`.

---

### CSV export buttons — `CashboxPageHead`, `FinancePage`, `AttendancePageHead`

**Analog:** `apps/admin-app/src/pages/messages/MessagesPage.tsx` (can() gate pattern) + `apps/admin-app/src/features/reports/api.ts` (staffRequest direct blob call)

**Button component** (from UI-SPEC lines 308–322 — exact spec):
```typescript
<Button
  variant="outline"
  size="sm"
  disabled={isDownloading}
  onClick={handleExport}
  aria-busy={isDownloading}
  aria-label="Экспорт CSV"
  className="h-[34px] shrink-0 gap-1.5 rounded-full px-3.5 text-[13px] font-semibold"
>
  {isDownloading ? (
    <Loader2 className="size-3.5 animate-spin" />
  ) : (
    <Download className="size-3.5" strokeWidth={2.2} />
  )}
  <span className="max-sm:hidden">Экспорт CSV</span>
</Button>
```

**Blob download handler** (from UI-SPEC lines 338–355):
```typescript
async function handleExportPayments() {
  setIsDownloading(true)
  try {
    const res = await fetch(
      `/api/v1/reports/payments.csv?fromDate=${fromDate}&toDate=${toDate}`,
      { credentials: 'include', headers: { 'X-CSRF-Token': getCsrfToken() } },
    )
    if (!res.ok) throw new Error(String(res.status))
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `payments-${fromDate}-${toDate}.csv`
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    toast.error('Не удалось экспортировать файл. Попробуйте ещё раз.')
  } finally {
    setIsDownloading(false)
  }
}
```

**Role gate** — copy can() inline conditional pattern from MessagesPage:
```typescript
// In CashboxPageHead / FinancePage:
{can(role, 'view', 'finance') && <ExportButton ... />}

// In AttendancePageHead:
{can(role, 'view', 'reports') && <ExportButton ... />}
```

Note: check if `staffRequest` supports `responseType: 'blob'` — if not, use native `fetch` with `credentials: 'include'` and the CSRF token header (matching how `staffRequest` injects X-CSRF-Token on POST). The `fromDate`/`toDate` are already in page state on each screen (existing date-range pickers).

---

## Shared Patterns

### require_permission BEFORE verify_csrf (RBAC-04 ordering)
**Source:** `apps/backend/app/modules/pt_sessions/router.py` lines 75–77
**Apply to:** All mutation endpoints in staff_router.py (POST /reply, POST /read)
```python
_actor: Annotated[CurrentUser, Depends(require_permission(Action.CREATE, Resource.MESSAGES))],
_csrf: Annotated[None, Depends(verify_csrf)],
```

### StreamingResponse CSV (no ResponseEnvelope, no response_model)
**Source:** `apps/backend/app/modules/reports/router.py` lines 139–143
**Apply to:** GET /reports/payments.csv
```python
# CSV routes return StreamingResponse directly — NO ResponseEnvelope, NO envelope() call,
# NO response_model (EXP-01..04, D-11, D-12).
```

### csv_export.make_csv_streaming_response
**Source:** `apps/backend/app/modules/reports/csv_export.py` lines 80–111
**Apply to:** payments_csv route
```python
return csv_export.make_csv_streaming_response(iter(rows), CSV_PAYMENTS_HEADERS, filename)
```

### csv_export.sanitize_csv_text (formula injection guard)
**Source:** `apps/backend/app/modules/reports/csv_export.py` lines 38–59
**Apply to:** Free-text cells in payments CSV rows (client_name, operator_email)
```python
csv_export.sanitize_csv_text(str(row["client_name"]))
```

### raw SQL text() + :name bind params (D-54-08)
**Source:** `apps/backend/app/modules/messaging/repository.py` lines 24–27
**Apply to:** All new repository functions in messaging module
```python
from sqlalchemy import text
# All cross-module reads via text() with :name bind params; UUID → str cast.
```

### staffRequest + Zod schema parse
**Source:** `apps/admin-app/src/features/reports/api.ts` lines 52–64
**Apply to:** All new hooks in features/messages/api.ts
```typescript
const raw = await staffRequest('get', '/api/v1/messages/threads')
return StaffInboxSchema.parse(raw).data
```

### useMutation with onSettled invalidation + onError toast
**Source:** `apps/admin-app/src/features/payroll/api.ts` (useMutation pattern)
**Apply to:** useSendReply in features/messages/api.ts
```typescript
onSettled: () => {
  void queryClient.invalidateQueries({ queryKey: messagesKeys.thread(threadId) })
  void queryClient.invalidateQueries({ queryKey: messagesKeys.threads() })
},
onError: () => { toast.error('...') },
```

### can() inline conditional render gate
**Source:** `apps/admin-app/src/pages/messages/MessagesPage.tsx` pattern (role-based conditional)
**Apply to:** Composer visibility in ThreadPane, export button visibility in page heads
```typescript
{can(role, 'create', 'messages') && <ComposerSection ... />}
{can(role, 'view', 'finance') && <ExportButton ... />}
```

### RBAC parity count bump
**Source:** `apps/backend/tests/integration/test_rbac_parity.py` line 163 + `tests/unit/test_permissions.py`
**Apply to:** Both test files atomically with permissions.py + can.ts + registry.ts changes
- `test_owner_only_count_is_forty_five` → `test_owner_only_count_is_forty_six`
- `test_owner_only_has_exactly_forty_five_entries` → 46
- Both count comments updated with Phase 116 breakdown line

---

## Additive Migration Decision

**Recommendation:** Add `staff_last_read_at TIMESTAMPTZ` column to `message_threads` via additive Alembic migration.

**Rationale:** Deriving unread from `COUNT(*) WHERE role='client' AND sent_at > staff_last_read_at` is correct only with a stored watermark. NULL means "never read by staff" → all client messages are unread. This is simpler and more performant than scanning all messages to compute the unread count per thread on every inbox load.

**Migration pattern:** Copy any existing additive column migration. The column is nullable (no default needed — NULL = never read):
```python
op.add_column(
    'message_threads',
    sa.Column('staff_last_read_at', sa.TIMESTAMP(timezone=True), nullable=True),
)
```

No backfill needed (NULL is the correct initial state — all threads are "unread" by staff until opened).

---

## No Analog Found

None. All files have analogs in the existing codebase.

---

## Metadata

**Analog search scope:** `apps/backend/app/modules/messaging/`, `apps/backend/app/modules/reports/`, `apps/backend/app/core/permissions.py`, `apps/backend/tests/integration/`, `apps/admin-app/src/features/messages/`, `apps/admin-app/src/features/reports/`, `apps/admin-app/src/shared/session/`, `apps/admin-app/src/pages/messages/`
**Files scanned:** 22
**Pattern extraction date:** 2026-06-15
