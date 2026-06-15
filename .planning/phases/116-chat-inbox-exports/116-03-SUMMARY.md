---
phase: 116-chat-inbox-exports
plan: "03"
subsystem: frontend-messages-exports
tags: [messaging, csv-export, rbac, inbox, owner-only, frontend]
dependency_graph:
  requires:
    - staff-messaging-rest-endpoints (116-01)
    - GET /api/v1/reports/payments.csv (116-02)
  provides:
    - FE staff inbox wired to real /api/v1/messages endpoints
    - owner-only composer gate (can(role,'create','messages'))
    - owner-gated payments.csv export (Cashbox + Finance)
    - owner-gated visits.csv export (Attendance)
  affects:
    - apps/admin-app/src/features/messages/api.ts
    - apps/admin-app/src/features/messages/types.ts
    - apps/admin-app/src/pages/messages/MessagesPage.tsx
    - apps/admin-app/src/pages/messages/components/ThreadPane.tsx
    - apps/admin-app/src/pages/cashbox/CashboxPage.tsx
    - apps/admin-app/src/pages/cashbox/components/CashboxPageHead.tsx
    - apps/admin-app/src/pages/finance/FinancePage.tsx
    - apps/admin-app/src/pages/attendance/AttendancePage.tsx
    - apps/admin-app/src/pages/attendance/components/AttendancePageHead.tsx
tech_stack:
  added: []
  patterns:
    - "staffRequest + as never cast (D-V31-CONTRACT-ADDITIVE) for non-OpenAPI paths"
    - "Zod ResponseEnvelope parse (.data) matching 116-01 SUMMARY wire shapes"
    - "can(role, action, resource) conditional render (hidden, not disabled) for RBAC"
    - "downloadCsv blob anchor helper reused from @/api/csv"
    - "useMarkThreadRead fire-and-forget on thread select (staff_last_read_at watermark)"
key_files:
  created: []
  modified:
    - apps/admin-app/src/features/messages/api.ts
    - apps/admin-app/src/features/messages/types.ts
    - apps/admin-app/src/pages/messages/MessagesPage.tsx
    - apps/admin-app/src/pages/messages/components/ThreadPane.tsx
    - apps/admin-app/src/pages/cashbox/CashboxPage.tsx
    - apps/admin-app/src/pages/cashbox/components/CashboxPageHead.tsx
    - apps/admin-app/src/pages/finance/FinancePage.tsx
    - apps/admin-app/src/pages/attendance/AttendancePage.tsx
    - apps/admin-app/src/pages/attendance/components/AttendancePageHead.tsx
    - apps/admin-app/src/shared/session/can.test.ts
decisions:
  - "StaffMessage.role typed as string (not union) per 116-01 forward-compat note; Zod uses z.string()"
  - "staffRequest '/api/v1/messages/threads' cast as never (D-V31-CONTRACT-ADDITIVE — not in generated paths type)"
  - "ClientPanelData built as minimal stub from StaffThread (no deep client fields in wire shape — panel shows fallback)"
  - "ConversationList.read Set always empty Set() — local read state removed; unread badge driven by real staffUnreadCount from server"
  - "STATUS_TABS placeholder (no backend tab-count endpoint in v1 scope)"
  - "threadDay: threads older than yesterday map to 'yesterday' group (ConversationList only has two groups)"
metrics:
  duration: "~10 minutes"
  completed: "2026-06-15"
  tasks_completed: 3
  files_modified: 10
---

# Phase 116 Plan 03: FE Staff Inbox Wiring + CSV Exports Summary

Staff chat inbox wired from mock to real `/api/v1/messages` endpoints (useThreads 15s poll,
useThread, useSendReply, useMarkThreadRead). Owner-only composer gate via
`can(role,'create','messages')`. Owner-gated «Экспорт CSV» buttons on Cashbox, Finance
(payments.csv over range), and Attendance (visits.csv over range). Mock data fully removed.

## Tasks Completed

| Task | Commit | Files |
|------|--------|-------|
| 1: Real staff messaging hooks + wire types | c06e51ae | features/messages/api.ts, types.ts |
| 2: Wire MessagesPage + owner-only composer + empty states | 1f74b994 | MessagesPage.tsx, ThreadPane.tsx, can.test.ts |
| 3: Owner-gated CSV export buttons (payments + visits) | c94412d8 | CashboxPage.tsx, CashboxPageHead.tsx, FinancePage.tsx, AttendancePage.tsx, AttendancePageHead.tsx, api.ts, types.ts |

## Wire Shapes Used (from 116-01-SUMMARY)

### GET /api/v1/messages/threads → StaffInboxSchema
- `data.items[].id`, `.clientId`, `.clientName`, `.clientInitials`, `.lastMessageAt` (ISO|null),
  `.lastMessageBody` (string|null), `.lastMessageRole` ('client'|'staff'|null), `.staffUnreadCount` (number)
- `data.total`

### GET /api/v1/messages/threads/{id} → StaffThreadSchema
- `data.threadId`, `data.messages[].id`, `.role` (open string), `.body`, `.sentAt` (ISO)

### POST /api/v1/messages/threads/{id}/reply
- Request: `{ body: string }` (1-4000 chars); CSRF from staffRequest automatic injection

### POST /api/v1/messages/threads/{id}/read → 204 No Content

### CSV endpoints used
- Payments: `GET /api/v1/reports/payments.csv?fromDate=YYYY-MM-DD&toDate=YYYY-MM-DD`
  (query-param convention confirmed from 116-02-SUMMARY — alias_generator=to_camel)
- Visits: `GET /api/v1/reports/visits.csv?fromDate=YYYY-MM-DD&toDate=YYYY-MM-DD`
  (existing route, same convention)

## StaffThread → Conversation Mapping

| Wire field | Conversation field | Transform |
|---|---|---|
| `clientInitials` | `initials` | direct |
| `clientName` | `name` | direct |
| `lastMessageBody` | `last` | fallback `''` |
| `lastMessageRole === 'staff'` | `lastPrefix` | `{text:'Вы:', tone:'note'}` |
| `lastMessageAt` | `time` | `formatRelativeRu()` |
| `staffUnreadCount > 0` | `unread` | count or undefined |
| hardcoded `'client'` | `source` | all threads are client-sourced |
| `'var(--primary)'` | `color` | semantic token |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] StaffMessage.role type conflict between Zod schema and TypeScript interface**
- **Found during:** Task 3 (pnpm build — tsc -b was stricter than tsc --noEmit)
- **Issue:** `StaffMessage.role` in types.ts was typed as `'client' | 'staff'` but the Zod schema in api.ts used `z.string()` (per 116-01 forward-compat note). TypeScript inferred `string` from Zod, which is not assignable to the union type.
- **Fix:** Changed `StaffMessage.role` from `'client' | 'staff'` to `string` in types.ts — consistent with the 116-01 decision ("open string for forward compat").
- **Files modified:** `features/messages/types.ts`
- **Commit:** c94412d8

**2. [Rule 1 - Bug] staffRequest path type error for /api/v1/messages/threads**
- **Found during:** Task 3 (pnpm build)
- **Issue:** The literal path `/api/v1/messages/threads` was not in the generated `paths` OpenAPI type, causing TS2345. The ID-parameterized paths already used `as never` but the base path did not.
- **Fix:** Added `as never` cast (D-V31-CONTRACT-ADDITIVE pattern used throughout the codebase).
- **Files modified:** `features/messages/api.ts`
- **Commit:** c94412d8

**3. [Rule 1 - Bug] can.test.ts OWNER_ONLY count stale at 45 (should be 46)**
- **Found during:** Task 2 test run
- **Issue:** `can.test.ts` asserted `OWNER_ONLY.length === 45` but 116-01 already added the `(create, messages)` pair (count 45→46). Test was failing.
- **Fix:** Updated test description and assertions from 45 to 46 with Phase 116-01 attribution.
- **Files modified:** `shared/session/can.test.ts`
- **Commit:** 1f74b994

### Design Adjustments (not bugs, plan-driven decisions)

**1. ThreadPane signature changed from (conv, seed, draft, quickReplies) → (activeThread, role)**
The original ThreadPane accepted pre-computed mock data. Since it now fetches via `useThread(activeThread?.id)`,
the component's public interface changed. `MessagesPage` passes a `StaffThread | null` instead of
pre-mapped component props. This follows the plan's intent ("wire to real hooks").

**2. ClientPanel receives minimal stub ClientPanelData**
The wire shape has no deep client-detail fields (chips, plan, upcoming). `buildClientPanel()` returns
a minimal struct with name/initials from the active thread; the panel renders in fallback state.
This is consistent with the plan ("reuse verbatim; only data source changes") — the panel renders
correctly, showing client name/initials with no plan/upcoming rows.

**3. ConversationList.read always Set() (server-side unread instead of client-side tracking)**
The original `MessagesPage` maintained a local `read: Set<string>` to suppress badges after clicking.
Since `staffUnreadCount` is now the source of truth (refreshed via 15s poll + mark-read invalidation),
the local Set is always empty — the server's `staffUnreadCount` drives the badge. After the poll fires
following a mark-read call, the badge disappears correctly.

## Deferred Browser UAT (Auto-deferred per operator-pending policy)

Task 4 (checkpoint:human-verify) was auto-deferred. The following UAT steps should be verified
manually against the running local docker stack when available:

1. **Owner — inbox:** Log in as OWNER → open «Сообщения». Inbox lists real client threads with
   unread badges (or empty state «Нет активных диалогов»). Threads refresh every 15s.

2. **Owner — thread + reply:** Open a thread → real history loads; unread badge clears.
   Type a reply, ⌘↵ / Send → message appears in thread. Confirm client PWA receives it.

3. **Reception — read-only inbox:** Log in as RECEPTION → «Сообщения» shows inbox; thread
   history visible; reply composer is **absent** (no send box at all).

4. **Owner — payments export:** «Касса» and «Финансы» → click «Экспорт CSV» → payments CSV
   downloads. Open in Excel/Numbers: Cyrillic client names render correctly (UTF-8 BOM),
   header row = `date,clientName,amountRubles,method,subjectKind,refundOf,operatorEmail`.

5. **Owner — visits export:** «Посещаемость» → click «Экспорт CSV» → visits CSV downloads
   over the current range.

6. **Reception — no export buttons:** «Касса»/«Финансы»/«Посещаемость» → «Экспорт CSV»
   button is **not visible** for reception (hidden, not disabled).

## Known Stubs

**ClientPanel fallback data** — `buildClientPanel()` in MessagesPage.tsx provides empty
chips, plan, and upcoming rows to ClientPanel. The panel renders with client name/initials
only. This is intentional — the wire shape (StaffThread) contains no client-detail fields.
Future wiring: fetch `/api/v1/clients/{clientId}` when a thread is opened (out of v1 scope).

## Threat Flags

None. All threat register entries (T-116-12 through T-116-SC) were addressed:
- T-116-12: `can()` gates applied — composer hidden for reception, export buttons hidden for reception; backend (116-01/116-02) enforces 403 regardless
- T-116-13: staffRequest automatically injects X-CSRF-Token on POST (no manual header needed)
- T-116-14: Mock `messagesData` import fully removed from api.ts; Zod parse validates real shapes
- T-116-15: React text content escaping — no dangerouslySetInnerHTML introduced
- T-116-SC: No new npm packages; Download/Loader2 from existing lucide-react dep

## Self-Check: PASSED
