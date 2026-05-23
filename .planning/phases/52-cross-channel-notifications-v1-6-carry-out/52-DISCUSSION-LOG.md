# Phase 52: Cross-Channel Notifications + v1.6 Carry-out - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-23
**Phase:** 52-cross-channel-notifications-v1-6-carry-out
**Mode:** `--auto` (all gray areas auto-selected; recommended defaults applied without interactive prompts)
**Areas discussed:** Dispatch architecture, payment_notifications table, Locked templates + LOCKED_EMAIL_TEMPLATES, Owner-alert recipient config, Seam fill points, NOTIFY-05 scope, CARRY-01/02 execution model

---

## Notification dispatch architecture

| Option | Description | Selected |
|--------|-------------|----------|
| Single fan-out ARQ task (`dispatch_payment_notification`) | One task per `(payment_id, kind)` attempts both channels, each independently guarded | ✓ |
| Per-channel ARQ tasks | Separate `dispatch_telegram` / `dispatch_email` enqueues from the seam | |
| Inline send in webhook UoW | Send before commit | |

**Auto-selection:** Single fan-out task — `[auto] Selected: single dispatch_payment_notification task (recommended; matches v1.6 send_booking_reminders dual-channel precedent).`
**Notes:** Best-effort per-channel; claim-then-send idempotency; never blocks the financial commit.

---

## payment_notifications table

| Option | Description | Selected |
|--------|-------------|----------|
| New table UNIQUE `(payment_id, kind, channel)` | Mirror v1.6 booking/membership channel discriminator | ✓ |
| Extend an existing notifications table | Reuse booking/membership table | |

**Auto-selection:** `[auto] Selected: new payment_notifications table, Alembic 0039, keyed on payments.id (recommended; NOTIFY-03 prescribes the shape).`
**Notes:** Keyed on the ledger `payments.id` so sale + refund rows dedup independently.

---

## Locked templates + LOCKED_EMAIL_TEMPLATES

| Option | Description | Selected |
|--------|-------------|----------|
| 4 Telegram + 4 email in online_payments module (D-39-02) | Module-scope locked copy; LOCKED_EMAIL_TEMPLATES 15→19 | ✓ |
| Shared telegram/copy.py location | Centralize all DM copy | |

**Auto-selection:** `[auto] Selected: module-scope locked copy in online_payments/ (recommended; D-39-02 ownership pattern).`
**Notes:** Canceled + fiscal-failed templates are owner-only operator alerts.

---

## Owner-alert recipient config (NOTIFY-04)

| Option | Description | Selected |
|--------|-------------|----------|
| New optional settings `OWNER_ALERT_TELEGRAM_CHAT_ID` + `OWNER_ALERT_EMAIL` | Default None → log-only if unset | ✓ |
| Hardcode / reuse first owner user record | Resolve owner dynamically from users table | |

**Auto-selection:** `[auto] Selected: new optional settings, default None, log-only fallback (recommended; no existing owner-contact config found in codebase).`
**Notes:** Genuine gap — no owner-alert contact exists today. Documented for Phase 53 deployment runbook.

---

## Seam fill points

| Option | Description | Selected |
|--------|-------------|----------|
| Enqueue from all 5 post-commit points + lockstep AST gate update | succeeded / refund / canceled / fiscal-fail (task + cron) | ✓ |
| Single central enqueue | One site, dispatch on kind | |

**Auto-selection:** `[auto] Selected: enqueue from each event's post-commit point; update test_post_commit_seam.py in lockstep (recommended; D-51-15 precedent).`

---

## NOTIFY-05 scope

| Option | Description | Selected |
|--------|-------------|----------|
| Confirm Phase 50 already emits cancellation fields; add owner alert + regression test | No re-implementation | ✓ |
| Re-implement cancellation audit payload | | |

**Auto-selection:** `[auto] Selected: confirm-and-test (recommended; Phase 50 handle_payment_canceled already emits cancellation_party + cancellation_reason).`
**Notes:** No client DM on cancel — owner operator alert only.

---

## CARRY-01 / CARRY-02 execution model

| Option | Description | Selected |
|--------|-------------|----------|
| AI ships scaffolding (probe script + evidence dir + countersign register); operator runs/signs | Operator-gated discharge | ✓ |
| AI attempts live probe with stub credentials | | |

**Auto-selection:** `[auto] Selected: AI scaffolding + operator-gated live run/countersign (recommended; requires real Yandex Postbox key + owner judgment; mirrors Phase 46 DEFER discipline).`

---

## Claude's Discretion

- ARQ `max_tries`/`_expires` mirroring `dispatch_fiscal_receipt`; claim-before-send timing; recipient sources (`client.telegram_user_id` / `client.email`); owner-alert dedup basis; logger names; template kind↔id mapping; no new LOCKED_AUDIT_EVENTS (idempotency table is the trail).

## Deferred Ideas

- `payment_notification_sent` audit event (deliberately omitted, mirror v1.6).
- Partial-refund (B-02) notification copy (v1.8+).
- Cancellation visibility in reports/UI (v1.8 Reports + Audit Log read API).
