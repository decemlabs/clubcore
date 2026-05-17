# Phase 39: Notifications + Cron - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `39-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-05-17
**Phase:** 39-notifications-cron
**Mode:** `--auto` (no AskUserQuestion calls; Claude auto-selected recommended defaults for every gray area; user may audit and override any D-39-NN before `/gsd-plan-phase 39` consumes the CONTEXT file)
**Areas discussed:** Module & Plan Structure, Telegram DM Templates, Cron Patterns, Synchronous Send Pattern, Idempotency & Constraint Naming, Audit & Compliance, Cron Worker Wiring, Test Discipline

---

## Module & Plan Structure

| Option | Description | Selected |
|--------|-------------|----------|
| A — 3 plans (templates / both crons / send-wiring) | Combine no-show + reminder crons into one plan | |
| B — 4 plans (templates / send-wiring / no-show / reminder) | Split crons by transaction-mode (single-session vs multi-session) | ✓ |
| C — 5 plans (templates / send-on-create / send-on-cancel / no-show / reminder) | Split send-wiring by event type | |

**Auto-selected:** B. **Rationale:** the two crons share no code beyond `WorkerSettings` registration; single-session DB-only cron and multi-session DM-send cron have different review surfaces. Splitting send-on-create from send-on-cancel is over-fragmentation (~30 LoC each). Matches v1.3 Phase 27 plan rhythm.

**Recorded as:** D-39-01.

---

## Telegram DM Templates — file location

| Option | Description | Selected |
|--------|-------------|----------|
| A — `app/modules/bookings/notifications.py` | Templates owned by bookings module | ✓ |
| B — `app/integrations/telegram/copy.py` (mirror v1.3) | Templates owned by Telegram integration layer | |

**Auto-selected:** A. **Rationale:** REQUIREMENTS NOTIFY-01 explicitly locks the path. Deviates from v1.3 deliberately — booking copy is owned by the bookings module's business semantics.

**Recorded as:** D-39-02.

---

## Telegram DM Templates — A/B variants

| Option | Description | Selected |
|--------|-------------|----------|
| A — No variants (single template per kind) | 4 strings, simpler owner copy-lock review | ✓ |
| B — A/B variants (mirror v1.3 pick_variant) | 8 strings, anti-oracle send-pattern protection | |

**Auto-selected:** A. **Rationale:** NOTIFY-01 specifies exactly 4 templates (not 8). Booking DMs are one-shot per discrete client-initiated action; fingerprinting threat model from v1.3 (recurring expiring DMs) does not apply.

**Recorded as:** D-39-04.

---

## Cancel-template selection logic

| Option | Description | Selected |
|--------|-------------|----------|
| A — Discriminate by `actor.role` | owner→OWNER_DM, reception→CLIENT_DM | ✓ |
| B — Discriminate by `cancel_reason` text | Parse the free-text reason string | |
| C — Always send same template | Ignore who cancelled | |

**Auto-selected:** A. **Rationale:** NOTIFY-04 phrasing maps roles to templates explicitly. `cancel_reason` is free text and unreliable.

**Recorded as:** D-39-05.

---

## Cron transaction-mode per cron type

| Option | Description | Selected (no-show) | Selected (reminder) |
|--------|-------------|--------------------|--------------------|
| A — Single-session (mirror `expire_memberships`) | One session, one transaction, one commit | ✓ | |
| B — Multi-session per-send (mirror `send_expiring_notifications`) | New session per row | | ✓ |

**Auto-selected:** A for `mark_no_show_bookings` (DB-only batch UPDATE, no I/O); B for `send_booking_reminders` (network I/O per row). **Rationale:** holding one DB connection across N Telegram round-trips wastes the pool; v1.3 Phase 27 D-27-07 pattern.

**Recorded as:** D-39-06.

---

## No-show cron locking discipline

| Option | Description | Selected |
|--------|-------------|----------|
| A — `SELECT FOR UPDATE` of booking rows | Locks booking; cooperates with D-38-19 record_pt_session lock | ✓ |
| B — Optimistic concurrency (no lock; expect IntegrityError) | Simpler but races with record_pt_session completion | |
| C — Lock booking + slot | Heavier; no extra correctness benefit | |

**Auto-selected:** A. **Rationale:** Phase 38 D-38-19 already established the partner-side lock in record_pt_session; Phase 39 honours the same lock domain. CRON-01 explicitly requires `SELECT FOR UPDATE`.

**Recorded as:** D-39-07.

---

## Sync vs async DM dispatch on create/cancel

| Option | Description | Selected |
|--------|-------------|----------|
| A — Synchronous in-request, fire-and-forget | ~+400ms p99; no new ARQ function | ✓ |
| B — ARQ-enqueue on commit, async send | +5ms; needs new function + per-DM idempotency | |

**Auto-selected:** A. **Rationale:** NOTIFY-03 phrasing "Failures (403/blocked) logged WARNING + no row" is fire-and-forget by definition. Single-zal MVP scale makes the latency cost invisible. ARQ migration path is clean if it ever matters.

**Recorded as:** D-39-09.

---

## `_dispatch_booking_dm` placement — Protocol slot or private helper

| Option | Description | Selected |
|--------|-------------|----------|
| A — Private function in `bookings/service.py` | No new abstraction; direct import of integrations | ✓ |
| B — Protocol slot via `app/core/dependencies.py` | Same shape as v1.4 cross-module slots | |

**Auto-selected:** A. **Rationale:** the helper only depends on `bookings.notifications` (same module) + `app.integrations.telegram.*` (integrations layer is always reachable from modules). No `modules-independent` contract pressure → no Protocol slot needed.

**Recorded as:** D-39-10.

---

## `booking_notifications` table — `telegram_chat_id` snapshot column

| Option | Description | Selected |
|--------|-------------|----------|
| A — No snapshot column (4 cols: id, booking_id, kind, sent_at) | Matches NOTIFY-05 literal spec | ✓ |
| B — Add `telegram_chat_id BIGINT` (mirror v1.3 line 304) | Audit-trail snapshot for support questions | |

**Auto-selected:** A. **Rationale:** NOTIFY-05 specifies exactly 4 columns. Re-resolving chat_id at send time gives current routing (more useful than snapshot). v1.5.1 backfill is trivial if needed.

**Recorded as:** D-39-03.

---

## FK ON-DELETE behavior

| Option | Description | Selected |
|--------|-------------|----------|
| A — `ON DELETE RESTRICT` | Mirrors Phase 38 bookings FK direction | ✓ |
| B — `ON DELETE CASCADE` (mirror v1.3 line 293) | Drops history with parent | |

**Auto-selected:** A. **Rationale:** Phase 38 D-38-04 / D-38-09 establish that bookings are never hard-deleted; CASCADE would mask any accidental DELETE. Consistent with `bookings.pt_package_id` / `bookings.slot_id` direction.

**Recorded as:** D-39-13.

---

## Real-Postgres race test for cron vs record_pt_session

| Option | Description | Selected |
|--------|-------------|----------|
| A — No race test in Phase 39 | Unit-level grep for FOR UPDATE; trust Postgres | ✓ |
| B — `BOOK-TEST-01`-style `asyncio.gather` against real DB | End-to-end race proof | |

**Auto-selected:** A. **Rationale:** D-38-19 + D-39-07 establish the lock at both sides; FOR UPDATE serialization is a Postgres guarantee not requiring Python assertion. Phase 40 VER-07 runs the one-shot runner against the live stack — that IS the integration proof. Documented so plan-checker doesn't flag the omission.

**Recorded as:** D-39-18.

---

## DM-send test fixture — stub vs mock

| Option | Description | Selected |
|--------|-------------|----------|
| A — Stub sender module (record calls into a list) | Matches v1.3 Phase 27 pattern; no aiohttp cost | ✓ |
| B — Mock `Bot` with `unittest.mock` | Higher fidelity but more boilerplate | |

**Auto-selected:** A. **Rationale:** v1.3 precedent works; bot=None acceptable because the stub does not use it.

**Recorded as:** D-39-19.

---

## Cron schedule ordering / interactions

Discussed without alternatives — REQUIREMENTS CRON-02 explicitly states "ordered AFTER `expire_pt_packages` 06:25". Implementation just appends the two new entries at the end of `WorkerSettings.cron_jobs` in the order: `send_booking_reminders` (06:35 MSK) → `mark_no_show_bookings` (23:10 MSK). Documented for plan-checker reference.

**Recorded as:** D-39-16.

---

## Claude's Discretion

None — `--auto` mode picked every default with rationale logged in `39-CONTEXT.md`. The user can audit and override any D-39-NN before `/gsd-plan-phase 39` consumes CONTEXT.md.

---

## Deferred Ideas

Captured in `39-CONTEXT.md` `<deferred>` section. Major buckets:

- **Phase 40** — bot `/book` flow + OpenAPI regen + milestone verification (locked scope per ROADMAP)
- **v1.5.1** — manual no-show endpoint, telegram_chat_id snapshot, A/B booking variants, ARQ-enqueue migration for create/cancel DMs
- **v1.6+** — reverse no_show transition, trainer-side DMs, multi-language, configurable schedule
