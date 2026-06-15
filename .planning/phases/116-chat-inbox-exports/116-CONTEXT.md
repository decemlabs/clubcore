# Phase 116: Chat Inbox & Exports - Context

**Gathered:** 2026-06-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Two staff-facing capabilities (MSG-01, MSG-02, EXP-01, EXP-02):

1. **Staff chat inbox** — NEW staff-side REST endpoints over the EXISTING `messaging` module
   (which today only exposes client-side `/api/v1/client/messages` + WS). Staff list client↔gym
   threads with unread counts, open a thread, and (owner) send/reply. Wire the EXISTING admin
   MessagesPage (ConversationList / ThreadPane / ClientPanel — currently mock) to the new endpoints.
2. **CSV exports** — owner downloads payments (NEW `/reports/payments.csv`) and visits/attendance
   (REUSE existing `/reports/visits.csv`) as UTF-8 BOM CSV over a date range, from Cashbox/Finance
   and the Attendance screen respectively.

Out of scope: live WebSocket updates for the STAFF inbox (v1 uses refetch; WS deferred); new
message attachments on the staff side (client attachment flow already exists); a multi-thread-
per-client model (the messaging module is 1:1 thread-per-client).
</domain>

<decisions>
## Implementation Decisions

### Staff messaging endpoints (MSG-01, MSG-02)
- **New staff messaging router** (separate from the client router): `GET /api/v1/messages/threads`
  (inbox list + per-thread unread count + last-message preview), `GET /api/v1/messages/threads/{id}`
  (thread history), `POST /api/v1/messages/threads/{id}/reply` (staff send), `POST
  /api/v1/messages/threads/{id}/read` (reset staff-side unread on open).
- **RBAC (per success criteria #1):** READ (list threads + history) allowed for BOTH roles
  (reception sees the inbox); SEND/reply is **owner-only**. Add a NEW `Resource.MESSAGES` to
  permissions.py with `(CREATE, MESSAGES)` (send) in OWNER_ONLY, `(LIST/VIEW, MESSAGES)` for both.
  MUST update backend permissions.py ↔ FE can.ts ↔ registry.ts ↔ RBAC parity tests
  (test_rbac_parity.py + test_permissions.py) ATOMICALLY in this phase. CSRF on the write routes;
  require_permission BEFORE verify_csrf.
- **Delivery to client PWA:** staff send uses the existing `insert_message(role='staff')` (bumps
  `last_message_at` + increments `client_unread_count`) and triggers the EXISTING client delivery
  channel — the WS `new_message` frame the client PWA already consumes AND the Telegram push
  (ccgram). Reuse the existing dispatch path; do NOT build a new one.
- **Mark-read:** opening a thread in the staff inbox resets that thread's STAFF-side unread (a
  staff-side unread counter — distinct from the existing `client_unread_count`). If a staff-side
  unread column does not exist, derive unread from messages with `role='client'` newer than the
  thread's `staff_last_read_at` (add that column via additive migration if needed).

### CSV exports (EXP-01, EXP-02)
- **Payments CSV:** NEW `GET /api/v1/reports/payments.csv` in the reports module, mirroring the
  existing visits/revenue CSV pattern (StreamingResponse, UTF-8 BOM, RFC-4180, `CSV_PAYMENTS_HEADERS`,
  `fromDate`/`toDate` range). Owner-only (`require_permission(VIEW, REPORTS/FINANCE)`).
- **Attendance CSV:** REUSE the EXISTING `GET /api/v1/reports/visits.csv` (already UTF-8 BOM).
- **FE download UX:** immediate blob download via an anchor (no new tab); owner-gated buttons on
  Cashbox/Finance (payments) and the Attendance screen (visits). Cyrillic round-trips via the
  backend UTF-8 BOM (already handled by the existing CSV discipline).

### FE chat inbox + realtime
- Wire the existing MessagesPage from mock to the new staff endpoints; show unread badges; remove
  mock message data. Per-thread + inbox empty states.
- **Realtime (v1):** TanStack Query refetch — `refetchOnWindowFocus` + invalidate after send +
  a modest `refetchInterval` on the inbox; live staff WS is DEFERRED.
- **Send gating:** the reply input/send button is HIDDEN for reception (read-only inbox) via
  `can(role, 'create', 'messages')`.

### Claude's Discretion
- Exact thread/inbox/message Pydantic + Zod field names (camelCase wire); pagination of the
  thread list vs simple list (prefer the paginated envelope for the inbox if many threads).
- Whether a `staff_last_read_at` column + additive migration is needed (vs deriving unread) —
  pick the simplest correct approach and document it.
- CSV column set for payments (mirror the payments ledger fields: date, client, amount, method,
  subject_kind, refund_of, operator).
- inbox refetchInterval value.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Messaging module** (`apps/backend/app/modules/messaging/`): `repository.py` —
  `get_or_create_thread`, `insert_message(thread_id, role: Literal['client','staff'], body, ...)`,
  `list_thread_history`, `mark_thread_read` (RETURNING-based). `router.py` is CLIENT-only today —
  add a separate staff router. Models: `message_threads` (uq on client_id), `messages`
  (role CHECK 'client'|'staff'), `client_unread_count`, `last_message_at`.
- **Client delivery channel:** the existing WS `new_message` broadcast + Telegram push (ccgram
  hooks) that the client PWA consumes when a staff message is inserted — reuse it.
- **CSV exports** (`apps/backend/app/modules/reports/`): `csv_export.py` + `constants.py`
  (`CSV_VISITS_HEADERS`, `CSV_REVENUE_HEADERS`, ...), router CSV routes return `StreamingResponse`
  (NO ResponseEnvelope) with UTF-8 BOM + RFC-4180. `get_visits_csv` is the attendance export.
  Mirror it for payments. `service.visits_csv_rows` is the row-generator pattern.
- **Payments data:** `app/modules/payments/` (repository/service) for the payments-row source the
  new payments CSV reads (append-only ledger incl. refund rows from phase 112).
- **RBAC:** `app/core/permissions.py` (Action/Resource/OWNER_ONLY) + FE
  `apps/admin-app/src/shared/session/can.ts` + `registry.ts` + `tests/integration/test_rbac_parity.py`
  + `tests/unit/test_permissions.py` (count assertion — phases 112/113 each bumped it; this phase
  adds MESSAGES pairs → bump again).
- **Frontend:** `apps/admin-app/src/pages/messages/` (MessagesPage + ConversationList, ThreadPane,
  ClientPanel, MessageTabs — wire from mock), `features/messages/` (api.ts + types.ts). Attendance
  export button on `pages/attendance/AttendancePage.tsx`; payments export on Cashbox/Finance.
  Reuse `staffRequest`, per-feature query keys, `can()` gating, Sonner toasts.

### Established Patterns
- Modular monolith; staff routes under `/api/v1/...`, client routes under `/api/v1/client/...`.
- RBAC server-side via require_permission (declared BEFORE verify_csrf); OWNER_ONLY → 403.
- CSV routes are StreamingResponse + UTF-8 BOM (no envelope). Backend tests httpx ASGITransport.
- Frontend: TanStack Query per-feature hooks + staffRequest (auto X-CSRF-Token on POST); can()
  gating; semantic tokens; MSK dates.

### Integration Points
- New staff messaging router registered in the v1 API router aggregation.
- New `Resource.MESSAGES` in permissions.py + FE can.ts + registry.ts + both RBAC parity tests
  (backend↔FE parity).
- New `/reports/payments.csv` route + `CSV_PAYMENTS_HEADERS` + payments row generator.
- Possible additive Alembic migration for `staff_last_read_at` (only if deriving unread is unfit).
- FE: `features/messages/api.ts` staff hooks + MessagesPage wiring + export buttons + mock removal.
- OpenAPI regen DEFERRED to Phase 117 — note new routes for the gate.
</code_context>

<specifics>
## Specific Ideas

- SEND is owner-only per success criteria #1 ("reception sees the inbox (read-permitted), owner
  can send") — confirmed over the more-natural "reception also replies" alternative.
- Attendance CSV REUSES the existing /reports/visits.csv — only a new payments CSV is built.
- Staff inbox realtime is refetch-based for v1; live WS deferred.
- New Resource.MESSAGES requires atomic backend↔FE RBAC parity update (parity tests bumped).
- Backend window/CSV/messaging queries tested via httpx ASGITransport incl. RBAC 403 (reception
  cannot send, cannot export), empty inbox, and Cyrillic CSV round-trip (BOM present).
</specifics>

<deferred>
## Deferred Ideas

- Live WebSocket updates for the STAFF inbox — v1 uses refetch.
- Staff-side message attachments — out of scope.
- Multi-thread-per-client / group threads — the model is 1:1 thread-per-client.
- OpenAPI regeneration — Phase 117 milestone gate.
</deferred>
