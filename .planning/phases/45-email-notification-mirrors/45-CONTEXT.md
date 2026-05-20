# Phase 45: Email Notification Mirrors — Context

**Gathered:** 2026-05-20
**Status:** Ready for planning
**Mode:** `--auto` (recommended defaults auto-selected from REQUIREMENTS.md / ROADMAP.md / Phase 41 + 42 CONTEXT / PROJECT.md constraints)

<domain>
## Phase Boundary

Fan out three existing Telegram-only flows to the email channel using the Phase 42 `EmailDispatcher` slot + the Phase 41 cross-channel `channel` discriminator. Concretely:

1. **Expiring-soon email fallback** at 06:15 Europe/Moscow — when Telegram delivery is blocked (`SendResult.blocked`) and the client has `email IS NOT NULL`, render and dispatch the appropriate `EMAIL_EXPIRING_{7D,3D,1D}_VARIANT_{A,B}` template via `EmailDispatcher`. Insert a `membership_notifications` row with `channel='email'` on successful enqueue. Same `client_id.bytes[0] & 1` anti-oracle A/B variant chooser used today for Telegram (D-27 lineage preserved across channels).
2. **Booking reminders email fallback** at 06:35 Europe/Moscow — same dual-channel pattern as expiring; `booking_notifications` idempotency row inserted with `channel='email'`.
3. **Booking lifecycle email fallback** — on the three FSM transition emissions already producing Telegram DMs (`booking_confirmed` / `booking_cancelled_by_client` / `booking_cancelled_by_owner`), fallback-email on Telegram `SendResult.blocked`. Email-side templates `EMAIL_BOOKING_{CONFIRMED, CANCELLED_BY_CLIENT, CANCELLED_BY_OWNER, REMINDER_24H}` live in `app/modules/bookings/notifications.py` (D-39-02 module ownership preserved).
4. **Payment-receipt email (sale + refund)** — post-commit best-effort hook in `app/modules/payments/service.py:record_payment` (signed-amount positive) and `app/modules/payments/service.py:issue_refund` (signed-amount negative). Enqueues `EMAIL_PAYMENT_RECEIPT_SALE` or `EMAIL_PAYMENT_RECEIPT_REFUND` via `EmailDispatcher`. New `payment_receipts` idempotency table with UNIQUE `(payment_id, channel)` prevents double-receipt across docker-restart races. New `payment_receipt_emailed` audit row carries `audit_correlation_id` linking back to the original `payment_recorded` / `refund_issued` row.

Plus the supporting cast:
- **ORM-level `channel` field** added to `MembershipNotification` and `BookingNotification` SQLAlchemy models (DB column already lives on the table since Alembic 0024 / Phase 41 — see D-45-13). Typed `Literal['telegram','email']`, server_default `'telegram'`, app-mandatory at INSERT time. Repository helpers + existing `_send_expiring_notifications` / `_send_booking_reminders` updated to pass `channel='telegram'` explicitly.
- **Alembic 0029_payment_receipts** — new idempotency table (only new schema migration in Phase 45).
- **12 new locked Russian email templates** (6 expiring + 4 booking + 2 receipt) added to `LOCKED_EMAIL_TEMPLATES` callsites — every identifier already in the Phase 41 frozenset (`app/core/audit.py:264-289`). Owner sign-off auto-recorded per D-27-OWNER-COPY-LOCK lineage (workflow.auto_advance = true).
- **`PaymentReceipt` ORM model** eager-imported in `app/workers/__init__.py` (NOTIFY-14 / REG-29-04 mirror). `EmailSendLog` already eager-imported (Phase 42). `PasswordResetToken` already eager-imported (Phase 44). Phase 45 only adds `PaymentReceipt`.
- **`actor_display_name` formatting helper** — single canonical implementation `app/modules/users/display.py:format_actor_display(full_name)` returning "first-name + space + first-letter-of-last-name + period" (e.g. `"Анна П."`). Computed once at audit-write time; snapshotted into `PaymentReceiptEmailedPayload` AND into the email render context. Reused by any future phase that surfaces operator identity in user-facing copy.
- **No new HTTP routes.** All NOTIFY-* surfaces are worker / cron / post-commit-hook. `payment_receipts` is a backend table, not exposed via API. OpenAPI regen lands in Phase 46.

Requirements in scope: **NOTIFY-06, NOTIFY-07, NOTIFY-08, NOTIFY-09, NOTIFY-10, NOTIFY-11, NOTIFY-12, NOTIFY-13, NOTIFY-14** (9 reqs per `.planning/REQUIREMENTS.md` traceability table). NOTIFY-06 DB-side migration already shipped at Phase 41 / Alembic 0024 — Phase 45 finalises the ORM-side wiring (D-45-13).

**Out of scope (forwarded to later phases or v1.7+):**

- **Aggressive bounce-driven `email_verified=false` flag flipping** — v1.7 (EMAIL-07 explicit defer; mirrored here for receipt-channel bounces).
- **Email re-send / re-try UX (manual operator "resend receipt" endpoint)** — v1.7. Phase 45 ships the cron + post-commit hook; manual replay surface is an owner-dashboard feature, not v1.6.
- **Client opt-in / opt-out toggle for fallback emails** (e.g. `clients.email_notifications_enabled`) — v1.7. v1.6 policy is fallback-only on `SendResult.blocked` AND `client.email IS NOT NULL`; an explicit opt-in flag is not added in Phase 45 (D-45-01 — keeps schema diff to a single new table).
- **SMS / postal / alternate channel slots** — v1.8+. The `channel` column accepts the values `('telegram','email')` only (CHECK constraint at the DB layer per Alembic 0024). Adding a third channel is a follow-up migration + CHECK widening.
- **`payment_receipts` retention / archival cron** — defer. Rows are forensic-relevant (link receipt sends to payment IDs); retain indefinitely in v1.6. `email_send_log` retention deferred to v1.7 alongside bounce-handling.
- **Read-side query for owner ops dashboard** ("did we send a receipt for payment X?") — v1.8 reports phase. NOTIFY-13 audit row makes the question trivially answerable but the dashboard surface lands later.
- **OpenAPI `openapi.json` regeneration** — Phase 46 HANDOFF-03 atomic regen (drift gate refreshes only at handoff per v1.4 lesson). Phase 45 ships zero new HTTP routes, so there is no spec drift to flush.
- **Live deliverability probe to yandex.ru / mail.ru / rambler.ru** — Phase 46 VER-13.
- **Admin-web UI surface for any of these flows** — frontend integration deferred to v2.0 design-team handoff. Phase 45 is backend-only.
- **Receipts for ЮKassa online payments** — v1.7 (whole online-payment milestone). v1.6 receipt path is cash-only (NOTIFY-11 explicit).
- **AI-driven content personalisation in expiring/booking emails** — never in scope (locked Russian copy + owner sign-off discipline forbids it).

</domain>

<decisions>
## Implementation Decisions

### Fan-out policy across all 3 flows (NOTIFY-07 / NOTIFY-09 / booking lifecycle — RESOLVED)

- **D-45-01 (Fallback-only on `SendResult.blocked` AND `client.email IS NOT NULL`; no opt-in column in v1.6):** Telegram remains the primary channel for v1.6 per PROJECT.md constraints. Email enqueue fires ONLY when Telegram returns `SendResult.blocked` (terminal — bot blocked / chat deleted / user deactivated their Telegram) AND `clients.email IS NOT NULL`. `SendResult.transient_error` does NOT trigger fallback — next cron tick retries Telegram first (preserves email quota; transient outages don't burn the budget). No new opt-in / opt-out column added to `clients` in Phase 45 — schema diff stays minimal (one new `payment_receipts` table). Per-client preference UX is a v1.7 follow-up.
- **D-45-02 (Telegram-first ordering — locked):** Same-tick attempt order is Telegram → (if blocked) → email. Both attempts inside the same per-candidate loop iteration; no second cron tick required for the email to fire. Per-candidate UoW boundary mirrors the Phase 27 D-27-07 multi-session pattern — read session closes BEFORE the send loop; each successful send opens its OWN write session for the `*_notifications` INSERT + audit emit + commit. Failures on both channels → no rows, structlog WARN, next tick retries.
- **D-45-03 (Cross-channel idempotency rule — both rows can coexist):** UNIQUE `(subject_id, kind, channel)` (already live since Alembic 0024) allows BOTH `(membership_id, '7d', 'telegram')` AND `(membership_id, '7d', 'email')` to coexist for the same membership. Phase 45 invariant: at most one Telegram send + at most one email send per `(subject, kind)` tuple. A Telegram-side row blocks future Telegram retries for that kind; an email-side row blocks future email retries. If only Telegram succeeded (no email row), tomorrow's tick will NOT email-fallback because the read filter still considers the kind "done for that subject" — the read filter is keyed on `(subject_id, kind)` ANY-channel for "has this kind been sent yet?" semantics (matches v1.3 NTF-05 single-shot rule per kind, irrespective of channel).
- **D-45-04 (`SendResult.blocked` semantics — terminal, no retry):** `app/integrations/telegram/sender.SendResult.blocked` flag (Phase 22 D-20) classifies HTTP 403 from Telegram (`Forbidden: bot was blocked by the user` / `Forbidden: user is deactivated`). These never recover without user action → email fallback is the right next channel. Transient 5xx / network = `blocked=False, ok=False` → no fallback, retry next tick.

### Booking lifecycle emails (NOTIFY-10 — RESOLVED)

- **D-45-05 (Lifecycle emails fire on FSM transitions, NOT a new cron):** The three non-reminder templates (`EMAIL_BOOKING_CONFIRMED`, `EMAIL_BOOKING_CANCELLED_BY_CLIENT`, `EMAIL_BOOKING_CANCELLED_BY_OWNER`) ride on the existing Phase 39 service-layer hooks that already commit `booking_notifications` rows on Telegram DM success. Phase 45 extends the post-Telegram-send block: on `SendResult.blocked` AND `client.email IS NOT NULL`, render the matching email template via the same `_select_booking_template(kind) → EmailTemplate` lookup and enqueue via `EmailDispatcher`. Inline best-effort: failure to enqueue → structlog WARN; FSM transition is NOT rolled back. The booking lifecycle commit is the source of truth; the email is informational only.
- **D-45-06 (Reminder email = same module helper, scheduled-cron entrypoint):** `EMAIL_BOOKING_REMINDER_24H` is reached only from the 06:35 cron path (`send_booking_reminders`). The 3 lifecycle templates are reached only from the FSM transition service paths. Single render-and-dispatch helper `bookings/notifications.py:enqueue_email_via_dispatcher(kind, client, ...)` is reused across all 4 callsites (DRY; each callsite passes its own kind constant).
- **D-45-07 (No reminder fallback for non-PT-package bookings):** Reminder cron candidate selection unchanged from Phase 39 — only `confirmed` bookings 24h before slot start. Fallback policy applies to the candidate list as-is. No new selection predicate.

### Payment-receipt fanout (NOTIFY-11 / NOTIFY-12 / NOTIFY-13 — RESOLVED)

- **D-45-08 (Post-commit best-effort fanout — payment commit never rolled back):** REQUIREMENTS.md NOTIFY-11 verbatim: "failure does NOT roll back the payment commit". Implementation: after `await session.commit()` in `record_payment` / `issue_refund`, open a NEW write session for the receipt fanout block:
  1. Compute `audit_correlation_id = uuid4()` (fresh; links to the just-committed `payment_recorded` / `refund_issued` audit row via stored `audit_correlation_id` column on the audit_log row — INFRA-39 lineage).
  2. INSERT `PaymentReceipt(payment_id, channel='email', audit_correlation_id, to_address=client.email, enqueued_at=now())` — UNIQUE `(payment_id, channel)` makes the INSERT race-tight; docker-restart re-enqueue raises `IntegrityError` → swallow + WARN.
  3. Emit `payment_receipt_emailed` audit row (`PaymentReceiptEmailedPayload` already registered at Phase 41 `audit_payloads.py:651`).
  4. Commit the receipt-fanout write session.
  5. Call `await get_email_dispatcher()(template_id=<SALE|REFUND>, to=client.email, audit_correlation_id=<from step 1>, **vars)` — ARQ enqueue. Failure to enqueue → structlog WARN, no rollback (the receipt row is already committed; rerun via owner manual replay surface in v1.7).
- **D-45-09 (Receipt-kind discriminator on `payment.signed_amount`):** `payment.signed_amount > 0` (cash sale recorded) → `template_id='EMAIL_PAYMENT_RECEIPT_SALE'`. `payment.signed_amount < 0` (refund via `issue_refund`) → `template_id='EMAIL_PAYMENT_RECEIPT_REFUND'`. `PaymentReceiptEmailedPayload.receipt_kind: Literal['sale', 'refund']` mirrors the discriminator (already locked at Phase 41).
- **D-45-10 (Skip fanout when `client.email IS NULL`):** No client email → no `PaymentReceipt` row inserted, no audit emit, no enqueue. Structlog INFO line `payment_receipt_skipped reason=no_email payment_id=...` for ops visibility. The audit lifecycle is intact (`payment_recorded` row still exists); the email simply never fanned out.
- **D-45-11 (`payment_receipts` table schema — minimal idempotency ledger):**
  ```sql
  CREATE TABLE payment_receipts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_id UUID NOT NULL,
    channel TEXT NOT NULL CHECK (channel IN ('telegram','email')),
    audit_correlation_id UUID NOT NULL,
    to_address TEXT NOT NULL,
    enqueued_at TIMESTAMPTZ NOT NULL DEFAULT now()
  );
  CREATE UNIQUE INDEX uq_payment_receipts_payment_channel
    ON payment_receipts (payment_id, channel);
  CREATE INDEX ix_payment_receipts_audit_corr ON payment_receipts (audit_correlation_id);
  -- FK: payment_id REFERENCES payments(id) ON DELETE RESTRICT
  ```
  No `status` / `provider_message_id` / `bounce_type` columns — the send-attempt outcome lives in `email_send_log` keyed by `audit_correlation_id` (Phase 42). The `payment_receipts` row is a pure idempotency ledger: one INSERT = one channel-targeted attempt. Forensic chain reassembles via `audit_correlation_id` joining `payment_receipts ↔ audit_log ↔ email_send_log`.
- **D-45-12 (`actor_display_name` format — "first-name + last-initial."):** Helper `app/modules/users/display.py:format_actor_display(full_name: str) -> str`. Algorithm: split on whitespace; first token kept verbatim; subsequent tokens → first character + `"."`. Example: `"Анна Петрова"` → `"Анна П."` (verbatim from REQUIREMENTS.md NOTIFY-12). Single-token input (`"Иван"`) → `"Иван"` (no surname to abbreviate). Empty input → `"Сотрудник"` (defensive fallback — should never occur because `users.full_name` is NOT NULL). Snapshotted into BOTH the audit payload AND the email render context AT receipt-fanout time (not at template render time) so a future user rename doesn't rewrite history.

### Cross-channel `channel` column wiring (NOTIFY-06 follow-up — RESOLVED)

- **D-45-13 (Add `channel: Mapped[str]` to ORM models — no new migration needed):** Alembic 0024 (Phase 41) already added the `channel` DB column + recreated UNIQUE indexes on `membership_notifications` and `booking_notifications`. The ORM models in `app/modules/memberships/models.py` and `app/modules/bookings/models.py` were left untouched at Phase 41 (D-41-15 — bedrock phase). Phase 45 adds:
  ```python
  channel: Mapped[Literal['telegram', 'email']] = mapped_column(
      Text,
      nullable=False,
      server_default='telegram',
  )
  ```
  to both `MembershipNotification` and `BookingNotification`. ORM-side default `'telegram'` mirrors the DB default; INSERTs across the codebase MUST pass `channel=<literal>` explicitly (no implicit default at the app layer). Update `_send_expiring_notifications` / `_send_booking_reminders` (and the Phase 39 booking-lifecycle hooks) to pass `channel='telegram'` on the success path; the new email-fallback path passes `channel='email'`.
- **D-45-14 (Read predicate for "already sent this kind?" — UNIQUE `(subject_id, kind, channel)`-aware but kind-level shortcut for cron):** Cron candidate selection (`find_expiring_candidates`, `find_booking_reminder_candidates`) filters by `NOT EXISTS (SELECT 1 FROM membership_notifications mn WHERE mn.membership_id = m.id AND mn.kind = :kind)` — i.e. ANY-channel match disqualifies. This preserves the v1.3 NTF-05 single-shot-per-kind invariant across channels: if Telegram already succeeded yesterday and the email fallback is unnecessary, today's tick won't re-attempt either channel. The UNIQUE `(subject_id, kind, channel)` is a race-safety guard at the row INSERT, not the candidate-selection predicate.

### Locked Russian email templates (NOTIFY-08 / NOTIFY-10 / NOTIFY-12 — RESOLVED)

- **D-45-15 (Templates live in their owning module — D-39-02 lineage):** No copy in `integrations/email/`.
  - 6 expiring templates → `app/modules/memberships/email_templates.py` (NEW file; mirror of `app/modules/auth/email_templates.py` Phase 42 shape).
  - 4 booking templates → `app/modules/bookings/email_templates.py` (NEW file).
  - 2 receipt templates → `app/modules/payments/email_templates.py` (NEW file).
  Each file exports a module-level `TEMPLATES: Final[dict[str, EmailTemplate]]` registry keyed by the `LOCKED_EMAIL_TEMPLATES` identifier. `EmailTemplate` shape (re-used from Phase 42 D-42-06):
  ```python
  @dataclass(frozen=True)
  class EmailTemplate:
      subject: str          # may carry `{var}` placeholders (Jinja2-rendered)
      html: jinja2.Template
      text: jinja2.Template
  ```
- **D-45-16 (Variant chooser — same `client_id.bytes[0] & 1` across channels):** Per D-27 lineage. Phase 45 hoists the variant chooser into `app/modules/memberships/notifications.py:select_expiring_variant(client_id: UUID) -> Literal['A', 'B']` (was inlined in Telegram render code at Phase 27). The same helper picks the Telegram DM variant AND the email template variant for the same `(client, kind)` tuple — so a client who got `EXPIRING_3D_VARIANT_A` on Telegram a year ago will get `EMAIL_EXPIRING_3D_VARIANT_A` if the email fallback ever fires (consistent voice).
- **D-45-17 (NBSP discipline — Phase 42 lineage):** `&nbsp;` in HTML body, literal U+00A0 in plain-text body. PITFALLS Outlook-NBSP fix from D-42 inherited verbatim. The 6 expiring templates use NBSP between `{end_date}` digits and `г.` (Russian abbreviation for "год"); the 4 booking templates use NBSP between trainer-name and time-of-day; the 2 receipt templates use NBSP inside `formatMoney`-style amount rendering ("1 200 ₽" with NBSP between digits, NBSP-before-₽).
- **D-45-18 (Owner sign-off mechanism — D-27-OWNER-COPY-LOCK lineage; auto-recorded under workflow.auto_advance):** All 12 template constants enumerated in Phase 45's per-plan SUMMARY files + Phase 46 VERIFICATION-LOG.md (lineage from D-27 / Phase 27). The `LOCKED_EMAIL_TEMPLATES` AST gate already enforces immutability of the IDENTIFIERS (Phase 41 `audit.py:264` frozenset); template body mutation between phases is blocked by the gate's literal-string discipline at every dispatch callsite. Owner sign-off recording is administrative — the gate is structural.
- **D-45-19 (Jinja2 SandboxedEnvironment + autoescape — Phase 42 D-42-05 lineage):** All 12 templates compile via the same Jinja2 `SandboxedEnvironment` instance with `autoescape=True` on the HTML side, plain passthrough on the text side. Subject lines render through Jinja2 only when they carry placeholders (e.g. booking subject `"Запись подтверждена: {{ slot_start_msk }}"`); pure-literal subjects (e.g. receipt `"Чек: оплата"`) are `Final[str]`.

### Eager-import discipline (NOTIFY-14 — RESOLVED)

- **D-45-20 (Phase 45 adds ONLY `PaymentReceipt` to the eager-import block):** `app/workers/__init__.py` already eager-imports `EmailSendLog` (Phase 42 D-42-33) and `PasswordResetToken` (Phase 44 cleanup-cron lineage). Phase 45 adds:
  ```python
  from app.modules.payments.models import (  # noqa: F401
      PaymentReceipt,  # Phase 45 D-45-20 — payment_receipts eager-import (REG-29-04)
  )
  ```
  alongside the existing eager imports. `tests/test_workers_eager_import.py` AST introspection (Phase 41 INFRA-40 / REG-29-04 test) is updated to assert the new model in the eager-import block.
- **D-45-21 (One-shot cron runner verification):** `apps/backend/scripts/run_expiring_cron_once.py` (and any Phase 45 sibling for booking reminders, if added) MUST return non-zero counts on first call against a freshly migrated database (per ROADMAP.md success criterion #5). The existing runner doesn't need rewriting — the eager-import addition is the structural fix; the runner already exercises the relevant table reads.

### Module ownership + import-linter (architectural — RESOLVED)

- **D-45-22 (Three module-owned fanout helpers; NO cross-module "email orchestrator"):** Each fanout helper lives in its owning module:
  - `app/modules/memberships/notifications.py` → `enqueue_expiring_email_fallback(...)` (Phase 45 addition).
  - `app/modules/bookings/notifications.py` → `enqueue_booking_email_fallback(...)` (Phase 45 addition).
  - `app/modules/payments/service.py` → inline post-commit block (no new module file; the fanout is small enough to live next to `record_payment`).
  All three call `get_email_dispatcher()(...)` (the Phase 41 Protocol slot accessor) — no module imports `app.integrations.email.*` directly (preserves import-linter contract 3). All three call `app.modules.users.display.format_actor_display(...)` for receipt-only operator name formatting (D-45-12); the helper module is import-allowed from any module that needs it (no cross-module business call — `display.format_actor_display` is pure-function, no I/O, no DB).
- **D-45-23 (Worker → modules.bookings exception — already documented at Phase 39):** `app/workers/scheduled/send_booking_reminders.py` already imports `app.modules.bookings` (Phase 39 D-39 narrative exception, mirrors Phase 18 D-09 expire_memberships). Phase 45 extends the existing worker code; no new contract addition needed.
- **D-45-24 (No new import-linter contract):** Phase 45 ships ZERO `.importlinter` changes. All new imports fall within existing carve-outs (modules → core; worker → owning module per D-09/D-39).

### Audit + correlation (NOTIFY-13 — RESOLVED)

- **D-45-25 (`payment_receipt_emailed` emitted at fanout time, not at provider-ack time):** Per D-45-08 step 3: `audit.emit("payment_receipt_emailed", ...)` fires when the `PaymentReceipt` row is committed — i.e. when the EMAIL HAS BEEN ENQUEUED, not when it has been DELIVERED. Delivery confirmation lives in `email_send_log.status` (Phase 42 bounce webhook updates it to `'delivered' | 'bounced' | 'complained'`) and is linked back via `audit_correlation_id`. The "did we send a receipt for payment X?" query becomes:
  ```sql
  SELECT pr.*, esl.status, esl.bounce_type
  FROM payment_receipts pr
  LEFT JOIN email_send_log esl USING (audit_correlation_id)
  WHERE pr.payment_id = :payment_id;
  ```
- **D-45-26 (Existing `expiring_notification_sent_*` audit emissions stay one-channel-keyed):** The 3 expiring audit events (`expiring_notification_sent_7d|3d|1d`) already exist (Phase 27 / `LOCKED_AUDIT_EVENTS`). Their payload does NOT currently carry a `channel` discriminator. Phase 45 OPTIONALLY adds `channel: Literal['telegram','email']` to the existing payload schemas (`audit_payloads.py:ExpiringNotificationSentPayload`) so the audit row records which channel actually delivered. If schema mutation is too invasive (existing rows would lack the field), the alternative is to keep payload shape stable and rely on `membership_notifications.channel` for the historical channel record. **Recommended (D-45-26):** ADD `channel: Literal['telegram','email']` to the payload as a non-optional field; existing rows are pre-v1.6 and the JSONB column is permissive. No Alembic migration needed (JSONB).

### Testing posture (cross-cutting — RESOLVED)

- **D-45-27 (Integration tests use `httpx ASGITransport` + per-test SAVEPOINT isolation — project default):** Per CLAUDE.md testing convention. New tests:
  - `tests/integration/test_expiring_email_fallback.py` — Telegram-blocked client with `email IS NOT NULL` → email-fanout asserts (`membership_notifications.channel='email'` row + audit row + ARQ enqueue spy).
  - `tests/integration/test_booking_email_fallback.py` — same shape for booking reminder + 3 lifecycle transitions.
  - `tests/integration/test_payment_receipt_email.py` — sale + refund variants; `payment_receipts` UNIQUE race test; `client.email IS NULL` skip path.
  - `tests/unit/test_actor_display_format.py` — `format_actor_display` algorithm (single token / two tokens / 3+ tokens / Cyrillic / empty).
  - `tests/unit/test_select_expiring_variant.py` — `client_id.bytes[0] & 1` chooser determinism across channels.
  - `tests/unit/test_locked_email_templates_phase45.py` — assert all 12 new constants are members of `LOCKED_EMAIL_TEMPLATES` AND every callsite passes the literal string (extends Phase 41 `test_locked_email_templates_ast.py` walker scope, no new AST gate needed).
- **D-45-28 (One real-Postgres race test for `payment_receipts`):** `tests/integration/test_payment_receipt_race.py` — two concurrent `record_payment` fanout-block invocations for the same `(payment_id, channel='email')` MUST result in exactly one row inserted (UNIQUE catches the second). Mirrors the Phase 22 `VIS-TEST-01` discipline + the Phase 25 freeze-period race test.
- **D-45-29 (ARQ enqueue spy / stub in tests):** Tests register a stub `EmailDispatcher` via `register_email_dispatcher(stub_dispatcher)` in `app/main.py:create_app` hook (Phase 42 lineage; the test fixture already exists). The stub appends to an in-memory list per test; assertions read the list. NO ARQ Redis touched in unit / integration tests.

### Claude's Discretion

- **Exact Russian copy of the 12 templates** — drafted during execution per the locked-template AST gate discipline. Subject lines + body text + footer follow the Phase 42 `EMAIL_OTP_LOGIN` shape (H1 + paragraph + footer "Sportzal · noreply@mail.sportzal.ru"). Owner sign-off recorded by constant-name enumeration in per-plan SUMMARY files.
- **Whether to introduce a `bookings/email_templates.py:_select_booking_template(kind)` helper or inline `if/elif` dispatch** — judgment call at execution time. The helper is cleaner with 4 kinds; inline is OK with 3. Either is acceptable.
- **Whether to extract a shared `_enqueue_email_via_dispatcher(template_id, to, audit_correlation_id, vars)` thin wrapper into a new `app/core/email_dispatch_helpers.py`** — judgment call. The dispatcher accessor is one call; wrapping it may be over-abstraction. Default: NO helper, three callsites each call `get_email_dispatcher()(...)` directly.
- **Phase 45 plan partitioning** — Claude's planner decides wave boundaries. Suggested rough shape: Wave 1 = Alembic 0029 + ORM `channel` field wiring + `PaymentReceipt` model + eager-import; Wave 2 = 12 email template files + locked constants; Wave 3 = expiring fallback + booking lifecycle fallback + booking reminder fallback + payment-receipt fanout (parallel-eligible); Wave 4 = race tests + AST gate scope extension + per-plan SUMMARY.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap + requirements
- `.planning/ROADMAP.md` §"Phase 45: Email Notification Mirrors" (lines 254–264) — phase goal + 5 success criteria + dependencies.
- `.planning/REQUIREMENTS.md` §"NOTIFY-06..14" (lines 71–83) — verbatim requirement text for the 9 reqs in scope.
- `.planning/PROJECT.md` §"Current Milestone: v1.6 Email channel + Multi-user admin" (lines 42–53) — milestone target features + region constraints.

### Prior phase context (v1.6 lineage)
- `.planning/phases/41-infra-bedrock-anti-oracle-scaffold/41-CONTEXT.md` — `LOCKED_AUDIT_EVENTS` frozenset growth (D-41-01..02), `LOCKED_EMAIL_TEMPLATES` AST gate (D-41-11), Alembic 0024 channel discriminator (D-41-15), `EmailDispatcher` Protocol slot (D-41-24), eager-import discipline (D-41-29).
- `.planning/phases/42-email-transport-layer-email-otp-fallback/42-CONTEXT.md` — `EmailDispatcher` double-wire (D-42-25..28), `EmailEnvelope` shape (D-42-16), Jinja2 `SandboxedEnvironment` (D-42-05), NBSP discipline (D-42-23), `email_send_log` schema (D-42-18), bounce webhook (D-42-17).
- `.planning/phases/43-multi-user-admin-module/43-CONTEXT.md` — invitation token hash helper (`apps/backend/app/modules/users/repository.py:42`), `users.full_name` non-null discipline.
- `.planning/phases/44-invitation-password-reset-flow/44-CONTEXT.md` — `password_reset_tokens` cleanup-cron + eager-import precedent (mirrors what Phase 45 does for `PaymentReceipt`).

### Telegram-side precedents (cross-channel parity)
- `apps/backend/app/modules/memberships/service.py:1401-1511` (`_send_expiring_notifications`) — the per-tick fanout that Phase 45 extends with email fallback.
- `apps/backend/app/modules/memberships/repository.py:52-71` (`ExpiringCandidate` dataclass) — augment with `client_email: str | None` field (or fetch alongside the existing JOIN) so the fanout helper can branch on email-availability without a second query.
- `apps/backend/app/modules/bookings/notifications.py` — Telegram-side templates + render helpers; Phase 45 adds the email-side sibling.
- `apps/backend/app/modules/bookings/service.py` (Phase 39 booking FSM transition hooks) — sites where `EMAIL_BOOKING_*` lifecycle emails branch off post-Telegram-send.
- `apps/backend/app/modules/payments/service.py:90-200` (`record_payment` / `issue_refund`) — sites where the receipt fanout block lands post-commit.

### Architectural anchors
- `.planning/codebase/ARCHITECTURE.md` — modular monolith carve-outs (modules ⊥ modules; integrations ⊥ modules).
- `.planning/codebase/CONVENTIONS.md` §testing — `httpx ASGITransport`, `pytest-asyncio`, per-test SAVEPOINT.
- `apps/backend/.importlinter` — contract 3 (`integrations ⊥ modules`) + contract 2 (`modules-independent`); Phase 45 ships zero changes.

### Locked code constants (must read before adding callsites)
- `apps/backend/app/core/audit.py:264-289` (`LOCKED_EMAIL_TEMPLATES` frozenset) — all 12 Phase 45 identifiers are pre-registered.
- `apps/backend/app/core/audit.py` (`LOCKED_AUDIT_EVENTS` frozenset) — `payment_receipt_emailed` already pre-registered; `email_sent` / `email_send_failed` already wired from Phase 42.
- `apps/backend/app/core/audit_payloads.py:651-666` (`PaymentReceiptEmailedPayload`) — payload schema already locked at Phase 41; Phase 45 just emits matching rows.
- `apps/backend/app/core/dependencies.py:609-678` (`EmailDispatcher` Protocol + `register_email_dispatcher` + `get_email_dispatcher`) — Phase 45 consumes the slot at 3 callsites.

### Migrations + ORM
- `apps/backend/alembic/versions/0024_notification_channel_discriminator.py` — DB-side `channel` column already added at Phase 41; Phase 45 adds the ORM-side `Mapped[str]` (D-45-13). No new migration for NOTIFY-06.
- Phase 45 ships ONE new migration: `apps/backend/alembic/versions/0029_payment_receipts.py` (D-45-11 schema).

### Anti-pattern + pitfall references
- `.planning/PITFALLS.md` — Outlook NBSP fix (templates), provider-5xx-storm (already mitigated at Phase 42 circuit breaker), REG-29-04 eager-import lineage.

### Out-of-scope reference (do NOT touch in Phase 45)
- `apps/admin-web/**` — frozen mock-mode contract reference; no UI surface for NOTIFY-* in v1.6 (v2.0 frontend handoff).
- `apps/backend/openapi.json` / `packages/api-client/src/schema.d.ts` — drift-gate regen lives at Phase 46 (HANDOFF-03). Phase 45 ships zero new HTTP routes, so there is no drift to flush.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`get_email_dispatcher()` accessor** (`app/core/dependencies.py:665`) — Phase 42 wired the real impl; Phase 45's 3 fanout callsites consume it directly. Stub registration via `register_email_dispatcher(stub)` in tests follows Phase 42 fixture lineage.
- **`EmailEnvelope` dataclass** (`app/integrations/email/types.py`, Phase 42 D-42-16) — pre-rendered envelope shape; the dispatcher impl handles ARQ enqueue. Phase 45 callsites pass `template_id` + render vars; the dispatcher impl owns rendering.
- **`select_expiring_variant(client_id)` chooser** — currently inlined in Phase 27 Telegram render code; Phase 45 hoists to a module-level helper (D-45-16) for cross-channel reuse.
- **`format_actor_display(full_name)` helper** — NEW in Phase 45 (D-45-12); lives in `app/modules/users/display.py`. Pure function; reusable by any future phase that surfaces operator identity in user-facing copy (e.g. v1.8 reports dashboard).
- **`ExpiringCandidate` dataclass** (`app/modules/memberships/repository.py:52`) — augment with `client_email: str | None` and `client_full_name: str` (the latter may already exist via JOIN; verify at execution). One additional JOIN column avoids a per-candidate second SELECT in the fanout loop.
- **`SendResult` shape** (`app/integrations/telegram/sender.py`) — `ok: bool`, `blocked: bool`, `error: str | None`. Phase 45 branches purely on `result.blocked` for fallback trigger.
- **Phase 42 NBSP discipline** in `EMAIL_OTP_LOGIN` template — copy-paste shape for all 12 Phase 45 templates (H1 + paragraph + footer; HTML uses `&nbsp;`, text uses literal U+00A0).
- **`audit.emit()` + `LOCKED_AUDIT_EVENTS` walker** — Phase 41 AST gate enforces literal-string discipline; Phase 45 just emits the pre-registered `payment_receipt_emailed` event name.

### Established Patterns
- **Multi-session per-cron-tick pattern** (Phase 27 D-27-07): open read session for candidate selection; close; per-candidate open NEW write session for INSERT + audit emit + commit. Race-safe via UNIQUE catch + rollback.
- **Service-owns-txn vs caller-owns-txn discipline** (SVC001 AST walker): the worker / service `_send_*` helpers carry `# noqa: SVC001 caller-owns-txn` because they open per-send write sessions internally. Phase 45 follows the precedent for the email-fallback path additions.
- **Best-effort post-commit fanout** (NEW with Phase 45; precedent = Phase 42 `dispatch_email` task failures don't affect business state). The receipt fanout block in `record_payment` / `issue_refund` opens its own write session after the main transaction commits.
- **Module-owned templates + integrations transport bytes** (D-39-02 + D-42-07): templates live in `app/modules/<module>/`; rendering happens at enqueue time in the calling module's context; the ARQ task never imports `app.modules.*`.
- **`server_default='telegram'` + app-mandatory** (cross-channel discriminator): DB-layer safety net for legacy rows; app-layer always passes the channel explicitly. Mirrors Phase 18 `created_by_user_id NOT NULL` + Phase 40 `NULLABLE` widening pattern.

### Integration Points
- **`record_payment` post-commit fanout** (`app/modules/payments/service.py:~140`) — INSERT block immediately after the existing `await session.commit()` on success branch. Wrap in `try/except` so any fanout failure becomes a structlog WARN, not a 500.
- **`issue_refund` post-commit fanout** (`app/modules/payments/service.py:~210`) — symmetric to `record_payment`. Receipt-kind discriminator: `signed_amount < 0` → REFUND template.
- **`_send_expiring_notifications` per-candidate loop** (`app/modules/memberships/service.py:1457-1509`) — inside the per-candidate `for cand in candidates:` block, after the existing `if not result.ok: log.warning(...); continue` branch, add a `if result.blocked and cand.client_email is not None:` sub-branch that renders + enqueues the email + writes a `channel='email'` row.
- **`_send_booking_reminders` per-candidate loop** (analogous; lives in `bookings` service per Phase 39) — same shape as expiring.
- **Booking FSM transition hooks** (Phase 39 `booking_confirmed` / `booking_cancelled_*` paths) — currently call `notifications.send_booking_dm(...)` post-commit; Phase 45 wraps that call to inspect `SendResult` and email-fallback on `blocked`.
- **`tests/test_workers_eager_import.py`** — AST walker that asserts the list of eager-imported ORM models. Phase 45 extends the asserted list with `PaymentReceipt`.

</code_context>

<specifics>
## Specific Ideas

- **Russian copy aesthetic**: H1 + ≤3 paragraphs + footer "Sportzal · noreply@mail.sportzal.ru" (Phase 42 `EMAIL_OTP_LOGIN` precedent). No marketing copy, no calls-to-action beyond what the business action requires. Mirror the dignified, terse voice of the locked Telegram DM templates (`EXPIRING_*_VARIANT_*`, `BOOKING_CONFIRMED_DM`).
- **Receipt email subject lines**: literal — no interpolation. Suggested: `"Чек: оплата"` for SALE, `"Чек: возврат"` for REFUND. Body interpolates the operator name, amount, plan/package description, timestamp.
- **Expiring email subjects**: short literal — `"Ваш абонемент скоро истекает"` for all 6 (variant differentiation in body voice, not subject).
- **Booking email subjects**: kind-specific literals — `"Запись подтверждена"`, `"Запись отменена (по вашей просьбе)"`, `"Запись отменена"`, `"Напоминание: тренировка завтра"`.
- **NBSP placement in receipts**: between digit groups in amount (`1 200`), between digits and currency sign (`1 200 ₽`), between operator-name tokens (`Анна П.`).
- **Footer link policy**: NO unsubscribe link in v1.6 (no DB toggle to honour it; v1.7 work). NO "сообщить о проблеме" link (no inbox surface). Pure informational emails.
- **From-address**: `noreply@mail.sportzal.ru` with display name `"Sportzal"` — Phase 42 D-42-10 lineage.

</specifics>

<deferred>
## Deferred Ideas

- **Client opt-in / opt-out toggle for fallback emails** — v1.7. Today's policy is fallback-only on Telegram-blocked; users who never want fallback emails can be supported by adding `clients.email_notifications_enabled BOOLEAN DEFAULT TRUE`, but the column + the UX surface to flip it are deferred.
- **Manual operator "resend receipt" endpoint** — v1.7. The `payment_receipts` UNIQUE makes resend a delete-then-replay or an idempotent kick path; either is a small endpoint but lands with the v1.7 owner-dashboard.
- **Aggressive bounce-driven `email_verified=false` flag flipping for clients** (parallel to v1.7 EMAIL-07 deferral for operators) — same v1.7 follow-up.
- **Read-side dashboard query** "did we send a receipt for payment X?" — v1.8 reports phase. The audit + table chain already supports the query.
- **`payment_receipts` retention / archival cron** — defer indefinitely; rows are forensic.
- **SMS / postal channel slots** — v1.8+. Requires CHECK widening on `channel` column + new transport adapter.
- **AI-driven content personalisation in expiring / booking / receipt emails** — never (locked Russian copy + AST gate forbid it).
- **Owner sign-off recording per template constant** in a structured `OWNER-SIGN-OFF.md` — pattern proposed but not adopted; existing per-plan SUMMARY enumeration discipline suffices for v1.6.
- **Telegram-first vs email-first per-client preference** — v1.7. Out-of-scope for v1.6 fallback policy.
- **Live deliverability probe** — Phase 46 VER-13 (already scoped).

</deferred>

---

*Phase: 45-email-notification-mirrors*
*Context gathered: 2026-05-20*
