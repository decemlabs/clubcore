---
gsd_state_version: 1.0
milestone: v2.5
milestone_name: Chat / Messaging — Client↔Gym
status: Awaiting next milestone
stopped_at: "Milestone v2.5 Chat / Messaging COMPLETE + archived (tag v2.5). 6/6 phases, 21/21 requirements, audit tech_debt (0 blockers). Deferred: RCPT-02 typing producer → v2.6; Phase 94 HUMAN-UAT (browser/device); carried flakes."
last_updated: "2026-06-08T09:00:00.000Z"
last_activity: 2026-06-08 — Milestone v2.5 completed and archived
progress:
  total_phases: 6
  completed_phases: 6
  total_plans: 14
  completed_plans: 14
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md

**Core value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.
**Current focus:** Planning next milestone (v2.6 — admin-web chat inbox + first production API-wiring, or v3.0 production deploy). Run `/gsd:new-milestone`.

## Current Position

Phase: Milestone v2.5 complete
Plan: —
Status: Awaiting next milestone
Last activity: 2026-06-08 — Milestone v2.5 completed and archived

## v2.5 Roadmap Summary

| Phase | Goal | Requirements |
|-------|------|--------------|
| 90. Messaging Domain + REST Foundation + WS Scaffold | DB schema + REST + WS + Redis pub/sub fan-out; all six WS invariants locked | MSG-01, MSG-02, MSG-03, MSG-04, RT-01, RT-02, RT-03, RT-04 |
| 91. Read Receipts + Typing Indicators | Per-message read status + typing presence over WS; reply-as-read semantics | RCPT-01, RCPT-02, RCPT-03 |
| 92. Photo Attachments | Authenticated upload + IDOR-safe serve; magic-byte validation; stored-XSS guards | ATT-01, ATT-02, ATT-03 |
| 93. Telegram Bridge | Client→staff DM via ARQ + reply routing via chat_forwarding_log + echo-loop prevention | BRDG-01, BRDG-02, BRDG-03 |
| 94. PWA ChatScreen Wiring | Graduate from D-71-09 ESLint zone; wire REST + WS + attachments; unread badge | PWA-01, PWA-02, PWA-03 |
| 95. OpenAPI Handoff + Milestone Verification | Byte-stable openapi.json + schema.d.ts + _v25Checks + milestone gate green | HND-01 |

**Coverage:** 21/21 v2.5 requirements mapped (zero orphans, zero duplicates). Execution order: 90 → 91 → 92 → 93 → 94 → 95.

<details>
<summary>v2.4 Roadmap Summary (shipped)</summary>

| Phase | Goal | Requirements |
|-------|------|--------------|
| 86. Gym-Info / CMS | Клиент видит gym-info из БД; owner управляет через write-API; baseline засеян | GYM-01, GYM-02, GYM-03 |
| 87. Notification Inbox | In-app лента уведомлений от системных событий; read/mark-all; push-token регистрация; PWA wired | INBOX-01, INBOX-02, INBOX-03, INBOX-04, INBOX-05 |
| 88. Trainer Detail / Bio | Полный профиль тренера (bio/специализация/фото); owner write-API; seed; PWA TrainerDetailSheet wired | TRNR-01, TRNR-02, TRNR-03, TRNR-04 |
| 89. OpenAPI Handoff + Milestone Verification | Byte-stable openapi.json + schema.d.ts regen + `_v24Checks` forward-guards + milestone gate зелёный | HND-01 |

</details>

## Accumulated Context

### Key Phase 95 Decisions

- **D-95-WS-DOC**: WS endpoint `/api/v1/client/ws/messages` documented as `get` (HTTP→WS upgrade handshake) in `_customize_openapi()` post-processor — cookieAuth-only security override; WS handshake cannot carry X-CSRF-Token; matches live endpoint
- **D-95-DRIFT-REF**: Drift gate verified vs Phase 89 baseline (`fedb3e55`) not `contract-freeze-v1.11.0` (Phase 64 tag predates v2.4 GYM/notifications/trainer additions); v2.5 adds exclusively client messaging paths — drift gate green

### Key v2.5 Architecture Decisions (pre-locked by research)

- **WS endpoint location**: `app/modules/messaging/router.py`, mounted at `/client` prefix in `api/v1/router.py` (same pattern as loyalty.router, gym.router, notifications.router) — NOT in client_portal/router.py (would violate modules-independent)
- **WS auth**: httpOnly cookie `cc_client_access` (sent automatically on same-origin WS upgrade); require_client() works unchanged inside @router.websocket(); no URL token; Origin check via verify_ws_origin dependency
- **Open decision**: WS auth — confirm cc_client_access SameSite=Lax/Strict before Phase 90 plan (if SameSite=None, ws-ticket fallback required)
- **Open decision**: Attachment storage — local filesystem adapter (recommended) vs S3-compatible from day one; decide at Phase 92 plan
- **DB-first, pub/sub as notification only**: every message written to Postgres before any Redis publish; WS carries event frames (type + IDs), not full payloads; REST catch-up on reconnect via ?after= cursor
- **Redis pub/sub**: per-WS-connection subscriber (redis.pubsub() creates dedicated connection); channel cc:messaging:client:{client_id} derived from principal ONLY; cleanup with await pubsub.aclose() in finally:
- **Session-per-operation**: WS handler injects session_factory from app.state; opens AsyncSession per message operation (NOT Depends(get_db) which holds connection for connection lifetime)
- **Telegram bridge**: D-06/D-10 worker→modules relaxation; telegram_bot.py imports messaging.service directly; HandlerContext gains messaging_service field appended at END; no .importlinter change for bridge
- **One .importlinter change**: add app.modules.messaging to modules-independent contract; no new ignore_imports for core REST/WS path
- **LOCKED_AUDIT_EVENTS**: pre-register ALL messaging events in Phase 90 (INFRA-15): ("message_sent","message"), ("message_read","message"), ("attachment_uploaded","message"), ("chat_staff_reply_sent","message")
- **Migrations**: 0064=message_threads, 0065=messages, 0066=message_attachments (sequential; FKs ordered accordingly)
- **WS test convention override**: httpx ASGITransport CANNOT do WS upgrade → use starlette.testclient.TestClient.websocket_connect() for ALL WS tests (overrides project default for WS endpoints only)
- **camelCase wire format**: ALL messaging schemas inherit BackendSchemaBase (alias_generator=to_camel); validated with schema unit test
- **Chat is human-only**: role ENUM is 'client' | 'staff'; no system_message type; hard boundary with v2.4 notification inbox
- **Reply-as-read semantics**: "read" = staff replied; when bot stores staff reply, mark prior client messages read_at=now() and publish read_receipt events (Telegram has no per-message read receipt API)
- **Typing is ephemeral**: never stored in Postgres; published to Redis pub/sub only with 5s TTL; PWA auto-dismisses
- **Telegram forwarding via ARQ task**: NOT synchronous in-transaction (avoids 429 rate-limit cascade)
- **chat_forwarding_log**: Redis key cc:messaging:tg_msg:{tg_message_id} → thread_id, TTL 7 days; set when bot sends DM to staff, consumed when reply arrives
- **Staff identity**: v2.5 = anonymous (role='staff') with telegram_user_id/username as nullable audit fields; full identity → v2.6 admin-web inbox
- **STAFF_TELEGRAM_CHAT_ID**: new Settings field (int | None); Telegram bridge disabled if absent

### Key v2.5 Plan 02 Decisions (REST surface)

- **verify_client_idempotency for POST /messages:** Staff dependency `verify_idempotency` (uses `get_current_user`) would 401 on client requests. `verify_client_idempotency` (Phase 70 D-70-02) is the correct client-scoped dependency.
- **idempotent_execute runner commits session internally:** DB-first semantics (P5) require Redis publish after commit. The runner function calls `session.commit()`, serialises response, returns — publish fires inside service before commit, co-transactionally (fire-and-forget post-return).
- **after-cursor composite `(sent_at, id::text)`:** Casting UUID to text for composite comparison avoids asyncpg type coercion issues with row-value syntax.
- **PATCH /messages/read returns 204:** Consistent with notifications read-all analog.
- **record_staff_message internal (no endpoint):** admin-web frozen until v2.6; function exercised by tests + Phase 93 bridge.

### Key v2.4 Milestone Constraints (still active)

- **Staff gate**: owner-only write-API + seeds; apps/admin-web frozen
- **Client-only**: all client read-endpoints under require_client(), IDOR-safe (client_id from principal only)
- **Staff contract**: byte-for-byte with contract-freeze-v1.11.0 — drift gate must be green
- **Module discipline**: D-20-MODULE + D-20-IDOR

### Research Flags (plan-phase guidance)

| Phase | Research Needed | Reason |
|-------|----------------|--------|
| Phase 90 | YES — high priority | 6 simultaneous WS invariants; highest pitfall density; WS test convention change |
| Phase 91 | No | Standard WS event extension; established patterns from Phase 90 |
| Phase 92 | No | OWASP attachment patterns documented; checklist from PITFALLS.md |
| Phase 93 | YES | Telegram bridge routing complexity; echo loop; HandlerContext stability |
| Phase 94 | No | v2.4 graduation pattern proven; D-71-09 lesson documented |
| Phase 95 | No | Standard handoff following Phase 89 pattern |

### Pending Todos

- **Future milestones sequence (post-v2.5)** — v2.6 admin-web chat inbox (расфриз admin-web + боевое API-wiring). See `.planning/todos/pending/2026-06-02-future-milestones-sequence-post-v2-1.md`

### Blockers/Concerns

- None active. (Resolved: cc_client_access SameSite concern — Phase 90 shipped WS auth over the httpOnly cookie successfully; no ws-ticket fallback needed.)

## Deferred Items

Acknowledged + deferred at v2.5 close (2026-06-08):

| Category | Item | Status |
|----------|------|--------|
| v2.6 | RCPT-02 typing indicator producer — PWA consumer + WS fan-out wired, but no production `publish_typing` trigger (Telegram has no typing API; admin-web frozen) | deferred → v2.6 admin-web |
| bug→v2.6 | **Typing indicator does NOT surface in the DOM** despite a CORRECT React render. Console trace (2026-06-08) confirms: WS typing frame → `window.__chatTyping` fires → `setTyping(true)` → component re-renders with `typing=true`, `statusText="печатает…"`, and `renderThreadBody` pushes the `.typing-dots` bubble — yet the dots/«печатает…» never appear in `document.body` (MutationObserver + 30ms poll over 8s see nothing; `chat-root` count = 1). Points to a React commit/instance/timing issue (committed tree not the visible one, or true→false collapses before paint). Dormant in v2.5 — no typing PRODUCER until v2.6 (Telegram has no typing API; admin-web frozen). Needs `/gsd:debug` + React DevTools fiber inspection when the v2.6 producer lands. See 94-HUMAN-UAT.md Gaps. | deferred → v2.6 |
| human-verify | Phase 94 HUMAN-UAT: ✅ browser-verified 2026-06-08 (pixel-perfect parity, photo flow, WS new_message/read_receipt/unread). 2 blocker bugs found + fixed (28c53de7 .sheet collision blanked the chat; 865d412d dev WS connectivity). NOT exercised: dark theme, physical-device camera, full Telegram leg (operator-pending). | mostly done — see 94-HUMAN-UAT.md |
| advisory-ui | Phase 94 UI-review nits (hoist per-mount `<style>` to singleton; thread-bar online-dot has no v2.5 presence backend; day-sep array keys) | deferred — see 94-UI-REVIEW.md |
| contract | Phase 92 WR-01 `MessageItem.body` `""` sentinel for attachment-only messages (null-vs-sentinel) — frozen as-is in v2.5 contract; revisit if PWA needs the distinction | deferred — contract owner decision |
| tracking | 13 stale prior-milestone quick-task artifacts (260529-*/260601-*, status `missing`) | acknowledged stale — pre-v2.5, not v2.5 work |
| smoke | Integration live-smoke recs: PTB22 Bot.send_message standalone in ARQ worker; long photo-caption truncation at scale; OTP→authed→WS-connect path | verify in a live session |

Carrying forward from v2.4 close (see previous STATE.md for full list):

| Category | Item | Status |
|----------|------|--------|
| human-verify | Phase 86/87/88 live docker+browser verification (GymInfoSheet, NotificationsSheet, TrainerDetailSheet) | ✅ VERIFIED in browser 2026-06-06 (see v2.4 STATE.md) |
| advisory-ui | v2.4 UI-review nits (inline fontWeight, icon gaps, no ErrorBoundary) | deferred — see 86/87/88-UI-REVIEW.md |
| tech-debt | Pre-existing: flaky test_freeze_race; promo F821 ruff debt; test_alembic_clean | carried forward |
| production | RUN-01 ЮKassa sandbox sale+refund walkthrough | N/A-until-production |
| production | RUN-02 RU email deliverability probe | N/A-until-production |
| security | Phase 70 CR-02/IN-01/IN-02 (proxy rate-limit, QR post-decode, cancel idempotency) | deferred → /gsd:secure-phase 70 |
| compliance | Phase 81 ФЗ-376 consent wording (concrete ₽ amount vs generic) | needs legal review |
| contract | Phase 92 WR-01: `MessageItem.body: str` uses `""` sentinel for attachment-only messages (asymmetric with request `body: str \| None`). Decide null-vs-sentinel before Phase 95 contract freeze; Phase 94 PWA consumes it | deferred — contract owner decision |
| tech-debt | Phase 92 WR-02: `storage.put()` (S3) before DB `insert_attachment()` → orphaned S3 object on DB failure, no GC path | out of v2.5 scope |
| production | Phase 92 WR-03/WR-04: S3 `ensure_bucket` lacks `CreateBucketConfiguration(LocationConstraint)` for non-us-east-1 (Yandex `ru-central1`) + does not handle `403 AccessDenied` from `head_bucket`. Works on local SeaweedFS; needs hardening before Yandex prod deploy | N/A-until-production |

## Session Continuity

Last session: 2026-06-08 (autonomous run)
Stopped at: Milestone v2.5 Chat / Messaging COMPLETE + archived (tag v2.5; audit tech_debt, 0 blockers; 21/21 requirements). ROADMAP/PROJECT/MILESTONES/RETROSPECTIVE updated; REQUIREMENTS.md archived + removed (fresh for next milestone).
Resume: Start the next milestone — `/gsd:new-milestone` (v2.6 admin-web chat inbox + first production API-wiring, or v3.0 production deploy).

## Operator Next Steps

- Start the next milestone with /gsd-new-milestone
