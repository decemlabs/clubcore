# Phase 45: Email Notification Mirrors — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `45-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-05-20
**Phase:** 45-email-notification-mirrors
**Mode:** `--auto` (recommended defaults auto-selected; no interactive questions asked)
**Areas discussed:** Fan-out policy, Booking lifecycle email path, Payment-receipt fanout shape, ORM channel-column wiring, Locked Russian templates, Eager-import scope, Module ownership, Audit + correlation, Testing posture

---

## Fan-out policy across all 3 flows (NOTIFY-07 / NOTIFY-09 + booking lifecycle)

| Option | Description | Selected |
|--------|-------------|----------|
| Fallback-only on `SendResult.blocked` AND `client.email IS NOT NULL`; no opt-in column (recommended) | Telegram remains primary; email fires only when bot is blocked terminally and client has email; preserves email quota; no new schema column in v1.6 | ✓ |
| Dual-channel parallel (every event hits both channels simultaneously) | Both channels every time; uses email quota aggressively; users get duplicate notifications | |
| Per-client opt-in via new `clients.email_notifications_enabled` column | Explicit user preference; adds a column + UX to flip it; scope creep into v1.7 territory | |
| Fallback on ANY non-ok (`blocked` OR `transient_error`) | Email-storms during Telegram outages burn provider quota | |

**Auto-selected:** Fallback-only on `blocked` (D-45-01 / D-45-02 / D-45-04). REQUIREMENTS.md NOTIFY-07 phrasing ("on `SendResult.blocked`") + PROJECT.md Telegram-first constraint + minimal schema diff converge.

**Notes:** `SendResult.transient_error` does NOT trigger fallback — next cron tick retries Telegram first. Both Telegram + email attempts happen in the SAME tick / same per-candidate loop iteration; no second-tick lag for the 1-day-warning case.

---

## Booking lifecycle email path (NOTIFY-10)

| Option | Description | Selected |
|--------|-------------|----------|
| FSM transition service-hook (inline, post-Telegram-send, best-effort) (recommended) | The 3 non-reminder templates ride on existing Phase 39 hooks; same `SendResult.blocked` → email fallback; FSM commit never rolled back | ✓ |
| New dedicated cron `send_booking_lifecycle_emails` | A second 06:35 job scanning for booking-state-changed rows; introduces lag between FSM commit and email; complicates Phase 39 audit trail | |
| Email-only for lifecycle, Telegram-only for reminders | Asymmetric channel rules; confusing for ops + users | |

**Auto-selected:** Service-hook inline (D-45-05 / D-45-06). Reuses Phase 39 audit + post-commit ordering verbatim. Single render-and-dispatch helper `bookings/notifications.py:enqueue_email_via_dispatcher(...)` shared across 4 callsites.

---

## Payment-receipt fanout shape (NOTIFY-11 / NOTIFY-12 / NOTIFY-13)

| Option | Description | Selected |
|--------|-------------|----------|
| Post-commit best-effort fanout; new `payment_receipts(payment_id, channel, audit_correlation_id, to_address, enqueued_at)` UNIQUE `(payment_id, channel)`; receipt-kind from `signed_amount` sign (recommended) | Receipt is informational; failure never rolls back payment; idempotency at the table layer | ✓ |
| Same-UoW fanout (rollback on enqueue failure) | Couples receipt-delivery success to payment commit; rejected by REQUIREMENTS NOTIFY-11 explicitly ("failure does NOT roll back") | |
| Partial-UNIQUE `(payment_id) WHERE channel='email'` only | Future SMS / postal channels need new partial indexes; less symmetric than `(payment_id, channel)` UNIQUE | |
| Include `status` / `provider_message_id` / `bounce_type` columns on `payment_receipts` | Duplicates `email_send_log` data; phase 42 already owns send-attempt outcome storage | |

**Auto-selected:** Post-commit best-effort + UNIQUE `(payment_id, channel)` + minimal columns (D-45-08 / D-45-09 / D-45-10 / D-45-11). Forensic chain reassembles via `audit_correlation_id` JOIN.

---

## `actor_display_name` format (USERS-07 follow-up / NOTIFY-12)

| Option | Description | Selected |
|--------|-------------|----------|
| "First-name + last-initial." — `"Анна П."` (recommended) | Verbatim REQUIREMENTS.md NOTIFY-12 example; privacy-conservative; snapshotted at audit-write time | ✓ |
| Full name (`"Анна Петрова"`) | Less privacy-conservative; surname exposure in customer-facing copy | |
| First name only (`"Анна"`) | Less identifying; can collide between two operators named "Анна" | |
| Pseudonymous handle | Owner UX overhead (manage handles); no value over first+initial | |

**Auto-selected:** First-name + last-initial. (D-45-12). Helper `app/modules/users/display.py:format_actor_display`; pure function; snapshotted at audit-write time so future renames don't rewrite history.

---

## ORM-level `channel` column wiring (NOTIFY-06 follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| Add `channel: Mapped[Literal['telegram','email']]` to `MembershipNotification` + `BookingNotification` ORM (recommended) | DB column already exists since Alembic 0024; ORM wiring finalises type-safe INSERTs; no new migration | ✓ |
| Keep ORM blind to `channel`; rely on `server_default='telegram'` at DB layer + raw SQL for email INSERTs | Bypasses typed mapped columns; fragile; breaks the project's typed SQLAlchemy 2.0 discipline | |
| Use a new sibling ORM class `MembershipEmailNotification` | Two tables, one logical entity; complicates the UNIQUE; rejected immediately | |

**Auto-selected:** Add typed `Mapped` column with `server_default='telegram'` + app-mandatory at INSERT time (D-45-13). Read predicate stays kind-level (D-45-14) — at most one Telegram + one email send per `(subject, kind)`.

---

## Locked Russian email templates (NOTIFY-08 / NOTIFY-10 / NOTIFY-12)

| Option | Description | Selected |
|--------|-------------|----------|
| Module-owned: `memberships/email_templates.py` + `bookings/email_templates.py` + `payments/email_templates.py` (recommended) | D-39-02 module-ownership lineage; matches Phase 42 `auth/email_templates.py` + Phase 43 `users/email_templates.py` shape | ✓ |
| Centralised `integrations/email/templates/` | Violates module-ownership invariant; copy lives in modules, transport in integrations | |
| `Final[str]` f-string templates instead of Jinja2 | Phase 42 D-42-08 rejected this for Russian-locale interpolation edge cases | |

**Auto-selected:** Module-owned + Jinja2 `SandboxedEnvironment` reuse from Phase 42 (D-45-15 / D-45-19). Variant chooser hoisted into `memberships/notifications.py:select_expiring_variant(client_id)` (D-45-16). NBSP discipline mirrors Phase 42 (D-45-17). Owner sign-off auto-recorded under workflow.auto_advance per D-27-OWNER-COPY-LOCK lineage (D-45-18).

---

## Eager-import scope (NOTIFY-14)

| Option | Description | Selected |
|--------|-------------|----------|
| Add ONLY `PaymentReceipt` to `workers/__init__.py` eager-import block (recommended) | `EmailSendLog` already eager-imported (Phase 42); `PasswordResetToken` already eager-imported (Phase 44); only the new table needs adding | ✓ |
| Re-add all three (`EmailSendLog` + `PasswordResetToken` + `PaymentReceipt`) | Duplicates existing imports; clutters the bedrock import block | |
| Skip eager-import; rely on `Base.metadata` autoload | REG-29-04 lineage explicitly forbids autoload-only — boot-time invariant requires explicit import | |

**Auto-selected:** Add `PaymentReceipt` only (D-45-20). `tests/test_workers_eager_import.py` AST introspection list updated to include it.

---

## Module ownership + import-linter posture

| Option | Description | Selected |
|--------|-------------|----------|
| Three module-owned fanout helpers; no cross-module "email orchestrator" (recommended) | Preserves modules-independent invariant; each module renders its own templates; transport via `EmailDispatcher` Protocol slot | ✓ |
| New `app/modules/notifications/` consolidated module that owns ALL email fanout | Forces modules to depend on a new shared business module; cross-module business call; rejected | |
| Move fanout into `app/integrations/email/` | Violates contract 3 (`integrations ⊥ modules`); templates would need to import from modules | |

**Auto-selected:** Three module-owned helpers (D-45-22). Zero new import-linter contracts (D-45-24). Worker → modules.bookings carve-out already documented at Phase 39 (D-45-23).

---

## Audit + correlation (NOTIFY-13)

| Option | Description | Selected |
|--------|-------------|----------|
| `payment_receipt_emailed` emitted at fanout time (when ARQ enqueued), correlation via `audit_correlation_id` to `email_send_log` (recommended) | Decouples "we tried" from "it delivered"; bounce webhook updates `email_send_log.status` later | ✓ |
| Emit only on provider-ack delivery confirmation | Couples audit timing to async webhook delivery; complicates the "did we send a receipt?" query | |
| Emit BOTH at enqueue AND at delivery | Double audit row per receipt; complicates the chain | |

**Auto-selected:** Emit at fanout time (D-45-25). Add `channel: Literal['telegram','email']` to existing `ExpiringNotificationSentPayload` (D-45-26) — JSONB column accepts the schema mutation without migration.

---

## Testing posture

| Option | Description | Selected |
|--------|-------------|----------|
| `httpx ASGITransport` + per-test SAVEPOINT integration tests + ARQ stub dispatcher + one real-Postgres race test for `payment_receipts` UNIQUE (recommended) | Project default + Phase 42 stub-dispatcher lineage + Phase 22 VIS-TEST-01 race discipline | ✓ |
| Integration tests against live ARQ + Redis | Slow; not portable to CI; rejected per project testing constraint | |
| Skip race test (rely on UNIQUE alone) | Bypasses the discipline; race tests are the proof | |

**Auto-selected:** Stub dispatcher + `httpx ASGITransport` + one race test (D-45-27 / D-45-28 / D-45-29). Six new test files enumerated in D-45-27.

---

## Claude's Discretion

- Exact Russian copy of all 12 new templates (drafted during execution; owner sign-off per constant-name enumeration in per-plan SUMMARY).
- Whether to introduce a `_select_booking_template(kind)` helper or inline if/elif dispatch — judgment at execution.
- Whether to extract a shared `_enqueue_email_via_dispatcher` thin wrapper into `app/core/` — default NO (three callsites call the accessor directly).
- Phase 45 plan partitioning (wave structure) — Claude's planner decides during `/gsd-plan-phase`.

## Deferred Ideas

- Client opt-in / opt-out toggle for fallback emails → v1.7.
- Manual operator "resend receipt" endpoint → v1.7.
- Bounce-driven `email_verified=false` flag flipping for clients → v1.7 (mirror of EMAIL-07 deferral).
- Read-side "did we send a receipt for payment X?" dashboard → v1.8 reports.
- `payment_receipts` retention / archival cron → deferred indefinitely (forensic-relevant).
- SMS / postal channel slots → v1.8+ (requires CHECK widening on `channel` column).
- Owner sign-off recording in a structured `OWNER-SIGN-OFF.md` → not adopted; per-plan SUMMARY enumeration suffices.
- Telegram-first vs email-first per-client preference → v1.7.
- Live deliverability probe → Phase 46 VER-13 (already scoped).
- Admin-web UI surface for any NOTIFY-* flow → v2.0 frontend handoff.
