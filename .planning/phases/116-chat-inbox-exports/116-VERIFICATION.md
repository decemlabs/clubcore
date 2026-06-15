---
phase: 116-chat-inbox-exports
verified: 2026-06-15T16:42:00Z
status: human_needed
score: 7/7 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Owner inbox + reply + CSV exports"
    expected: >
      (1) Owner opens «Сообщения»: inbox lists real client threads with unread badges,
      or empty state "Нет активных диалогов". Opening a thread loads real history;
      unread badge clears immediately (not on next 15 s poll). Typing a reply and
      sending makes it appear inline. (2) Reception opens «Сообщения»: inbox is visible
      and readable; the reply composer is completely absent (no send box). (3) Owner on
      «Касса» and «Финансы» clicks «Экспорт CSV»: payments CSV downloads (BOM-prefixed,
      Cyrillic client names render correctly in Excel/Numbers, header row is
      date,clientName,amountRubles,method,subjectKind,refundOf,operatorEmail).
      (4) Owner on «Посещаемость» clicks «Экспорт CSV»: visits CSV downloads over
      current range. (5) Reception on «Касса»/«Финансы»/«Посещаемость»: NO
      «Экспорт CSV» button is visible.
    why_human: >
      Visual presence/absence of UI elements, real WS delivery to client PWA,
      CSV download triggering a browser file-save, and Cyrillic round-trip in
      Excel cannot be verified programmatically without a running browser session.
      Auto-deferred per operator-pending policy (Telegram/client-PWA leg).
---

# Phase 116: Chat Inbox + Exports Verification Report

**Phase Goal:** Staff can read and reply to client messages from the admin app, and owner can download payments and attendance data as CSV files.
**Verified:** 2026-06-15T16:42:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Owner GET /api/v1/messages/threads returns 200 with all client threads + per-thread staff unread count + last-message preview | ✓ VERIFIED | `staff_router.py:49-69` implements the endpoint; `test_owner_list_threads_200` + `test_empty_inbox_owner` pass |
| 2 | Reception GET /api/v1/messages/threads returns 200 (read allowed for both roles) | ✓ VERIFIED | `(LIST, MESSAGES)` NOT in `OWNER_ONLY`; `test_reception_list_threads_200` passes |
| 3 | Owner POST /threads/{id}/reply persists role='staff' message and triggers publish_new_message + publish_read_receipt post-commit | ✓ VERIFIED | `staff_router.py:96-155`; CR-01 fix commit `5e009a4c` — writes to validated thread_id, reads client_id once, publishes both frames after commit; `test_reply_persists_on_validated_thread_and_marks_client_read` passes |
| 4 | Reception POST /threads/{id}/reply returns 403 | ✓ VERIFIED | `(CREATE, MESSAGES) ∈ OWNER_ONLY`; `test_reception_reply_403` passes (asserts code=="forbidden") |
| 5 | POST /threads/{id}/read returns 204 and resets staff-side unread (both roles) | ✓ VERIFIED | `staff_router.py:158-181`; `test_mark_read_resets_staff_unread` + `test_owner_mark_read_204` + `test_reception_mark_read_204` pass |
| 6 | Owner GET /api/v1/reports/payments.csv returns 200, text/csv, UTF-8 BOM, date-range-filtered rows; reception → 403 | ✓ VERIFIED | Route at `reports/router.py:214-241`; `test_payments_csv_bom_and_content_type` + `test_payments_csv_cyrillic_roundtrip` + `test_payments_csv_reception_forbidden` pass |
| 7 | RBAC parity holds: backend OWNER_ONLY == FE can.ts; count 46 | ✓ VERIFIED | `test_owner_only_pairs_match` + `test_owner_only_count_is_forty_six` pass; FE `can.test.ts` asserts `OWNER_ONLY.length === 46` |

**Score:** 7/7 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/app/modules/messaging/staff_router.py` | 4 staff endpoints | ✓ VERIFIED | 4 routes: GET /threads, GET /threads/{id}, POST /threads/{id}/reply, POST /threads/{id}/read |
| `apps/backend/alembic/versions/0073_message_thread_staff_last_read_at.py` | Additive nullable staff_last_read_at column | ✓ VERIFIED | `op.add_column` + `op.drop_column`; `alembic check` reports no pending changes |
| `apps/backend/app/core/permissions.py` | Resource.MESSAGES + (CREATE, MESSAGES) in OWNER_ONLY | ✓ VERIFIED | Line 64: `MESSAGES = "messages"`; line 162: `(Action.CREATE, Resource.MESSAGES)` |
| `apps/backend/tests/integration/messaging/test_staff_messaging.py` | ASGITransport integration tests | ✓ VERIFIED | 13 test functions covering all scenarios incl. reception-403, mark-read, watermark boundary |
| `apps/backend/app/modules/reports/constants.py` | CSV_PAYMENTS_HEADERS in `__all__` | ✓ VERIFIED | Lines 54-62 + line 120 in `__all__` |
| `apps/backend/app/modules/reports/router.py` | GET /payments.csv StreamingResponse route | ✓ VERIFIED | Route at line 214; `require_permission(Action.VIEW, Resource.REPORTS)` guard |
| `apps/backend/app/modules/reports/service.py` | payments_csv_rows orchestrator | ✓ VERIFIED | Function exists; validates range, formats kopecks, sanitizes free-text cells |
| `apps/backend/app/modules/reports/repository.py` | fetch_payments_for_csv raw-SQL read | ✓ VERIFIED | Function exists with `text()` + `:name` bind params, MSK date expression |
| `apps/admin-app/src/features/messages/api.ts` | Real hooks (mock removed): useThreads, useThread, useSendReply, useMarkThreadRead | ✓ VERIFIED | All 4 hooks present; Zod schemas parse backend shapes; mock imports removed |
| `apps/admin-app/src/features/messages/types.ts` | StaffThread/StaffMessage wire types | ✓ VERIFIED | StaffThread, StaffMessage, StaffInboxData, StaffThreadData present |
| `apps/admin-app/src/pages/messages/MessagesPage.tsx` | Wired to real threads + mark-read on select | ✓ VERIFIED | `useThreads` + `useMarkThreadRead` imports; `markRead.mutate(id)` on onSelect |
| `apps/admin-app/src/pages/messages/components/ThreadPane.tsx` | Owner-only composer via can(role,'create','messages') | ✓ VERIFIED | Line 163: `const canCompose = can(role, 'create', 'messages')`; composer wrapped in `{canCompose && ...}` |
| `apps/admin-app/src/pages/cashbox/components/CashboxPageHead.tsx` | Optional exportButton slot | ✓ VERIFIED | `exportButton?: ReactNode` slot passed to PageHeader actions |
| `apps/admin-app/src/pages/attendance/components/AttendancePageHead.tsx` | Optional exportButton slot | ✓ VERIFIED | `exportButton?: ReactNode` slot in AttendancePageHead |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `staff_router.py` | `service.list_threads` / `send_staff_reply` / `mark_staff_thread_read` | Direct service calls | ✓ WIRED | Lines 68, 92, 135, 179 call service functions |
| `staff_router.py` | `publish_new_message` + `publish_read_receipt` (post-commit) | `service.publish_new_message` / `service.publish_read_receipt` | ✓ WIRED | Lines 141-153; CR-01 fix: resolves client_id once, commits then publishes both frames |
| `apps/backend/app/api/v1/router.py` | `staff_router` | `include_router(staff_messaging_router, prefix="/messages")` | ✓ WIRED | Lines 167-169 |
| `features/messages/api.ts` | `/api/v1/messages/threads` | `staffRequest GET` + Zod parse | ✓ WIRED | `useThreads` line 80: `staffRequest('get', '/api/v1/messages/threads' as never)` |
| `ThreadPane.tsx` | `can(role,'create','messages')` | composer conditional render gate | ✓ WIRED | Line 163: `const canCompose = can(role, 'create', 'messages')`; line 234: `{canCompose && ...}` |
| `CashboxPage.tsx` | `/api/v1/reports/payments.csv` | `downloadCsv` blob anchor | ✓ WIRED | Lines 80-81: `downloadCsv('/api/v1/reports/payments.csv', ...)` |
| `FinancePage.tsx` | `/api/v1/reports/payments.csv` | `downloadCsv` blob anchor | ✓ WIRED | Lines 105-106: `downloadCsv('/api/v1/reports/payments.csv', ...)` |
| `AttendancePage.tsx` | `/api/v1/reports/visits.csv` | `downloadCsv` blob anchor | ✓ WIRED | Lines 96-97: `downloadCsv('/api/v1/reports/visits.csv', ...)` |
| `reports/service.py` | `csv_export.sanitize_csv_text` | free-text cell sanitization | ✓ WIRED | `sanitize_csv_text` called on `clientName` + `operatorEmail` in `payments_csv_rows` |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| `MessagesPage.tsx` | `threads` from `useThreads()` | `GET /api/v1/messages/threads` → `list_all_threads_with_unread` SQL query | Yes — correlated subquery over `message_threads` + `messages` + `clients` | ✓ FLOWING |
| `ThreadPane.tsx` | `thread` from `useThread(id)` | `GET /api/v1/messages/threads/{id}` → `list_thread_history` SQL query | Yes — full message history query | ✓ FLOWING |
| `CashboxPage.tsx` | `exportButton` blob download | `GET /api/v1/reports/payments.csv` → `fetch_payments_for_csv` SQL → StreamingResponse | Yes — raw SQL cross-module read over `payments` + `clients` + `users` | ✓ FLOWING |
| `AttendancePage.tsx` | `exportButton` blob download | `GET /api/v1/reports/visits.csv` (pre-existing) | Yes — pre-existing visits CSV endpoint | ✓ FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Staff router has 4 expected paths | `uv run python3 -c "from app.modules.messaging.staff_router import router; print([r.path for r in router.routes])"` | `['/threads', '/threads/{thread_id}', '/threads/{thread_id}/reply', '/threads/{thread_id}/read']` | ✓ PASS |
| OWNER_ONLY count is 46; (CREATE,MESSAGES) in; (LIST,MESSAGES)+(VIEW,MESSAGES) not in | Python import assertions | All 3 assertions pass | ✓ PASS |
| CSV_PAYMENTS_HEADERS exported in `__all__` | Python import assertion | PASS with tuple `('date', 'clientName', 'amountRubles', 'method', 'subjectKind', 'refundOf', 'operatorEmail')` | ✓ PASS |
| Reception reply → 403 (named test) | `uv run pytest tests/integration/messaging/test_staff_messaging.py::test_reception_reply_403 -q` | 1 passed | ✓ PASS |
| Payments CSV BOM + content-type (named test) | `uv run pytest tests/integration/reports/test_csv_export.py::test_payments_csv_bom_and_content_type -q` | 1 passed | ✓ PASS |
| RBAC parity set-equality + count (named tests) | `uv run pytest tests/integration/test_rbac_parity.py::test_owner_only_pairs_match tests/integration/test_rbac_parity.py::test_owner_only_count_is_forty_six -q` | 2 passed | ✓ PASS |
| Full backend test suite | `uv run pytest tests/integration/messaging/ tests/integration/reports/test_csv_export.py tests/integration/test_rbac_parity.py tests/unit/test_permissions.py -q` | 344 passed in 16.32s | ✓ PASS |
| Frontend test suite | `pnpm exec vitest run` | 30 test files, 405 tests passed | ✓ PASS |
| TypeScript check | `pnpm exec tsc --noEmit` | Exit 0 (no errors) | ✓ PASS |
| ESLint (modified FE files) | `pnpm exec eslint src/features/messages src/pages/messages src/pages/cashbox src/pages/finance src/pages/attendance` | No output (clean) | ✓ PASS |
| mypy --strict (messaging) | `uv run mypy app/modules/messaging --strict` | "Success: no issues found in 8 source files" | ✓ PASS |
| mypy --strict (reports) | `uv run mypy app/modules/reports --strict` | "Success: no issues found in 8 source files" | ✓ PASS |
| alembic migration state | `uv run alembic check` | "No new upgrade operations detected." | ✓ PASS |
| import-linter | `uv run lint-imports` | "Contracts: 3 kept, 0 broken." | ✓ PASS |

---

### Probe Execution

Step 7c: SKIPPED — no probe scripts declared in PLAN.md or SUMMARY.md; no `scripts/*/tests/probe-*.sh` found for this phase.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| MSG-01 | 116-01, 116-03 | Staff sees a chat inbox of client↔gym threads (list + unread), backed by new staff-side REST | ✓ SATISFIED | GET /threads endpoint + FE useThreads hook wired; test_owner_list_threads_200 + test_empty_inbox_owner pass |
| MSG-02 | 116-01, 116-03 | Staff can open a thread and send/reply; messages persist and client PWA receives them | ✓ SATISFIED | POST /reply endpoint persists role='staff', publishes publish_new_message + publish_read_receipt; reception is 403; test_reply_persists_on_validated_thread_and_marks_client_read passes |
| EXP-01 | 116-02, 116-03 | Owner can export payments to CSV (RFC-4180 + BOM) over a date range | ✓ SATISFIED | GET /reports/payments.csv exists; BOM + Cyrillic + reception-403 + inverted-range-422 tests all pass; FE export button wired in CashboxPage + FinancePage |
| EXP-02 | 116-03 | Owner can export attendance/visits to CSV over a date range | ✓ SATISFIED | Pre-existing GET /reports/visits.csv reused; FE export button wired in AttendancePage with `can(role,'view','reports')` gate |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/core/permissions.py` | 159 | E501 line too long (102 > 100) — comment `# Phase 116 — staff chat inbox: reception can LIST/VIEW threads; only owner can CREATE (send).` | ⚠️ Warning | Ruff linting violation in a comment line; no functional impact; tests + logic correct |
| `tests/integration/messaging/test_staff_messaging.py` | 39 | E402 module-level import not at top of file (fixture re-export below `_csrf` helper) | ⚠️ Warning | Non-standard test structure (re-export in test file instead of conftest.py); no functional impact — all 13 test functions pass |
| `tests/integration/messaging/test_staff_messaging.py` | 41–87 | F811 fixture redefinition (14 occurrences) — pytest injects `authed_client_owner`/`authed_client_reception`/`make_client` as function args; ruff misidentifies as unused redefinitions | ⚠️ Warning | False-positive ruff warnings in the pytest fixture injection pattern; tests function correctly (344 pass) |
| `alembic/versions/0073_message_thread_staff_last_read_at.py` | 17 | I001 import block unsorted — pre-existing pattern across ALL migration files in this project | ℹ️ Info | Pre-existing codebase-wide pattern (0072 and earlier migrations have same violation); not introduced by phase 116 |

**Debt marker check:** Zero TBD/FIXME/XXX markers found in any phase-116-modified file. Gate: clear.

**Assessment:** The ruff E501 in permissions.py and the E402+F811 cluster in the test file are real linting violations. However:
- E501 is a 2-char overrun on a comment line with no functional impact
- E402+F811 are structural issues in the test file (re-export placed in the wrong location) but do not affect test correctness — all 344 tests pass and the functional assertions are fully covered
- The I001 in the migration file is a pre-existing project-wide pattern not introduced by this phase

None of these block the phase goal. No unreferenced TBD/FIXME/XXX markers.

---

### REVIEW.md Findings — Post-Fix Status

The code review found 1 BLOCKER + 6 WARNINGs + 4 INFOs. All were addressed in fix commits before this verification:

| Finding | Severity | Fix Commit | Verified |
|---------|----------|-----------|----------|
| CR-01: staff reply re-resolved thread independently + missing read-receipt publish | BLOCKER | `5e009a4c` | ✓ `staff_router.py:135-155` — client_id resolved once; both frames published post-commit |
| WR-01: useMarkThreadRead didn't invalidate inbox | WARNING | `a5ffba22` | ✓ `api.ts:156-158` — `onSettled` invalidates `messagesKeys.threads()` |
| WR-02: note/resolve tabs silently sent plain reply | WARNING | `e8a61c4d` | ✓ `ThreadPane.tsx:236-243` — modes removed; only "Ответ" tab remains |
| WR-03: watermark tradeoff undocumented | WARNING | `8a6a83b8` | ✓ Comments added to repository.py (doc-only fix) |
| WR-04: old threads grouped under "Вчера" | WARNING | `2aa99152` | ✓ `MessagesPage.tsx:33-41` — `threadDay` returns `'earlier'` for old threads |
| WR-05: whitespace-only body passed StaffReplyRequest | WARNING | `ad49b71a` | ✓ `schemas.py:249-252` — `model_validator` rejects whitespace-only body; `test_reply_whitespace_only_body_422` passes |
| WR-06: FE gate used (VIEW,FINANCE) instead of (VIEW,REPORTS) | WARNING | `726dd277` | ✓ `CashboxPage.tsx:95` + `FinancePage.tsx:130` — both gate on `can(role,'view','reports')` |
| IN-01: open thread didn't poll for new messages | Info | `a5ffba22` | ✓ `api.ts:109` — `refetchInterval: 15_000` added to `useThread` |
| IN-02: name ordering inconsistency in payments CSV | Info | `9814ea9f` | ✓ normalized to `last_name first_name` in payments CSV query |
| IN-03: `_make_initials` returns "?" for empty names | Info | (intentional no-op per REVIEW) | Accepted — harmless fallback; flagged for visibility only |
| IN-04: placeholder header action stubs (reassign/snooze/archive/block) | Info | `e8a61c4d` | ✓ Toast-only stubs removed from ThreadPane header |

---

### Human Verification Required

#### 1. Owner inbox + thread + reply + client delivery

**Test:** Log in as OWNER → open «Сообщения». Inbox lists real client threads with unread badges (or empty state "Нет активных диалогов"). Open a thread → real history loads; unread badge clears immediately. Type a reply, ⌘↵ / Send → appears in thread. Confirm client PWA receives via WS/Telegram if available.

**Expected:** Inbox refreshes every 15 s automatically; unread badge disappears on open (mark-read fires); sent message appears immediately (reply invalidates thread query).

**Why human:** Visual badge clearing, WS delivery to client PWA, and real-time message appearance require a running browser session with live backend.

#### 2. Reception read-only inbox (no composer)

**Test:** Log in as RECEPTION → «Сообщения». Inbox is visible; opening a thread shows history.

**Expected:** The reply composer (textarea + Send button) is completely absent — not disabled, not greyed, not hidden behind a toggle. No "note" or "resolve" tabs visible.

**Why human:** Absence of a UI element cannot be verified programmatically without a running browser session.

#### 3. Owner payments CSV download — Cashbox + Finance

**Test:** As OWNER → «Касса» and «Финансы». Click «Экспорт CSV». CSV file downloads.

**Expected:** File opens in Excel/Numbers with: UTF-8 BOM (Cyrillic names render correctly, no mojibake), header row = `date,clientName,amountRubles,method,subjectKind,refundOf,operatorEmail`.

**Why human:** File download + spreadsheet rendering + Cyrillic round-trip requires a browser and spreadsheet application.

#### 4. Owner visits CSV download — Attendance

**Test:** As OWNER → «Посещаемость». Click «Экспорт CSV». CSV file downloads.

**Expected:** Visits CSV downloads over the current date range (existing `/api/v1/reports/visits.csv` endpoint).

**Why human:** Browser file download trigger requires a live browser session.

#### 5. Reception sees no export buttons

**Test:** As RECEPTION → «Касса», «Финансы», «Посещаемость».

**Expected:** «Экспорт CSV» button is not visible on any of these three pages.

**Why human:** Absence of a UI element requires browser inspection.

---

### Deferred Items

| Item | Addressed In | Evidence |
|------|-------------|----------|
| OpenAPI regen for /messages/threads paths (currently `as never` cast) | Phase 117 (HND-01) | REQUIREMENTS.md: "HND-01: OpenAPI (`openapi.json` + `schema.d.ts`) regenerated additively for the new v3.2 routes (refund, role-change, promo CRUD, analytics, exports, staff-messages)" |

---

## Gaps Summary

No functional gaps found. All 7 must-have truths are VERIFIED. All key links are WIRED. All data flows are confirmed real (not stub/static). All REVIEW.md findings (1 BLOCKER + 6 WARNINGs) are resolved in code.

Remaining ruff violations (E501 in permissions.py, E402+F811 in test file) are non-functional linting issues that do not affect correctness or the phase goal. They should be cleaned up but are not blocking.

Status is `human_needed` because Task 4 of plan 116-03 was a `checkpoint:human-verify` step that was auto-deferred per the operator-pending policy. The 5 browser UAT items listed above require a running local dev stack to verify.

---

_Verified: 2026-06-15T16:42:00Z_
_Verifier: Claude (gsd-verifier)_
