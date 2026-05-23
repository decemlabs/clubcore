# Phase 52: Cross-Channel Notifications + v1.6 Carry-out - Context

**Gathered:** 2026-05-23
**Status:** Ready for planning
**Mode:** `--auto` (recommended defaults applied; decisions logged inline)

<domain>
## Phase Boundary

Phase 52 closes the v1.7 online-payment loop's communication layer and discharges two v1.6 operator deferrals. It ships:

1. **Cross-channel client notifications** — on `payment.succeeded` and `refund.succeeded`, the client receives BOTH a Telegram DM and an email, deduplicated across worker restarts by a new `payment_notifications` table with UNIQUE `(payment_id, kind, channel)`. This fills the notification branches of the `_post_commit_enqueue` seam that Phase 50/51 stubbed (the fiscal-dispatch branch is already filled by Phase 51 D-51-15).
2. **Owner operator alerts** — on `fiscal_receipts.status → failed` (from the `dispatch_fiscal_receipt` task OR the `monitor_stale_fiscal_receipts` cron), the owner receives a `FISCAL_RECEIPT_FAILED_DM` Telegram alert + a best-effort owner email (NOT-04). On `payment.canceled`, the owner receives an operator alert (`ONLINE_PAYMENT_CANCELED_DM`) — **no client DM** (NOT-05).
3. **Locked template surface** — 4 Telegram DM templates in `app/modules/online_payments/notifications.py` (NOT-01) + 4 corresponding email identifiers in `app/modules/online_payments/email_templates.py` (NOT-02). `LOCKED_EMAIL_TEMPLATES` grows 15 → 19; the AST gate continues to reject non-literal `template_id`.
4. **v1.6 carry-out** — CARRY-01 (DEFER-46-01 live RU email-deliverability probe) + CARRY-02 (DEFER-46-02 owner 15-template countersign), both operator-gated.

Requirements covered: **NOTIFY-01, NOTIFY-02, NOTIFY-03, NOTIFY-04, NOTIFY-05 + CARRY-01, CARRY-02** (7 reqs). 6 success criteria locked by ROADMAP.md.

**Out of phase (explicit):**
- Partial-refund (B-02) DMs — full-refund only, deferred to v1.8+.
- Reports / audit-log read API for cancellation visibility — v1.8 (NOT-05 only enriches the audit payload, which Phase 50 already does).
- DEFER-46-03 cron-chain circuit-breaker re-run — Phase 53 VER-05.
- ЮKassa sandbox walkthrough + operator runbook — Phase 53 VER-01..03.

**Carry-forward from Phases 47–51:**
- `_post_commit_enqueue(arq_pool, *, online_payment_id, subject_kind, subject_id, fiscal_receipt_id=None)` (`app/api/v1/_internal/yookassa/handlers.py:269`) — Phase 51 added the `fiscal_receipt_id` branch; Phase 52 ADDS the notification-enqueue branch. The AST gate `tests/integration/webhook_yookassa/test_post_commit_seam.py` MUST be updated in lockstep (same discipline as D-51-15).
- `handle_refund_succeeded` settle logic lives in `app/modules/online_refunds/settle.py` (`_settle_online_refund`, shared by webhook + `poll_pending_refunds` cron). Phase 52 enqueues the refund DM from the same post-commit point.
- `handle_payment_canceled` (`handlers.py:~640`) already emits `online_payment_canceled` with `cancellation_party` + `cancellation_reason` — **NOT-05's audit requirement is ALREADY SATISFIED by Phase 50.** Phase 52 only adds the owner operator-alert enqueue + a regression test asserting no client DM.
- `dispatch_email` ARQ task (Phase 42 EMAIL-03) + `get_email_dispatcher()` (`app/core/dependencies.py:676`) — the email-channel send mechanism. Reused, not reinvented.
- `app/integrations/telegram/sender.send_text_dm(...)` + `build_bot(token=...)` — the Telegram send mechanism (Phase 39/45 booking-reminder precedent in `app/workers/scheduled/send_booking_reminders.py`).
- `LOCKED_EMAIL_TEMPLATES` frozenset (`app/core/audit.py:399`, currently 15 entries) + AST gate `tests/unit/test_locked_email_templates_ast.py`.
- v1.6 cross-channel idempotency precedent: `booking_notifications` / `membership_notifications` with `channel` discriminator + UNIQUE per `(subject_id, kind, channel)` (Alembic 0024). `payment_notifications` mirrors this shape exactly.
- D-39-02 module-scope copy ownership (`app/modules/bookings/notifications.py`) — locked Russian DM strings live next to their owning module with `# OWNER-COPY-LOCK` annotations + `str.format(**kwargs)` rendering (KeyError-loud).
- Phase 47 INFRA-35 LOCKED_AUDIT_EVENTS pre-registration discipline + AST gate.
- Latest Alembic revision is `0038_fiscal_receipts_created_at`; Phase 52's `payment_notifications` table → **Alembic 0039**, `down_revision = "0038_fiscal_receipts_created_at"`.

</domain>

<decisions>
## Implementation Decisions

### Notification dispatch architecture (NOTIFY-01..04)

- **D-52-01:** A single new ARQ task `dispatch_payment_notification(ctx, *, payment_id: str, kind: str)` owns cross-channel fan-out. For the given `(payment_id, kind)` it attempts BOTH channels (Telegram + email), each guarded independently. Lives in a new `app/modules/online_payments/tasks.py` (mirrors `app/modules/fiscal_receipts/tasks.py` shape). Registered in `WorkerSettings.functions` in `app/workers/__init__.py` (bare callable, mirroring `dispatch_fiscal_receipt`). Rationale over per-channel tasks: one enqueue from the seam, one place owning the recipient-resolution + idempotency claim per channel; matches v1.6 single-task dual-channel precedent.
- **D-52-02:** **Per-channel claim-then-send** within the task. For each channel ∈ {`telegram`, `email`}: (1) resolve recipient address (Telegram `client.telegram_user_id`; email `client.email`); (2) if address is null → structlog INFO `event="payment_notification_channel_skipped"` and continue, **no idempotency row written** for the absent channel; (3) attempt INSERT of `payment_notifications(payment_id, kind, channel)` — on `IntegrityError` (UNIQUE violation) the channel was already sent → structlog INFO idempotent-replay + skip; (4) on successful INSERT, send via the channel adapter inside the same UoW boundary discipline as v1.6. **Best-effort:** a send failure on one channel never blocks the other and never rolls back the payment/refund commit (mirror v1.6 D-45-08 fire-and-forget).
- **D-52-03:** Email channel reuses the existing `get_email_dispatcher()` → `dispatch_email` ARQ task path (Phase 42); Telegram channel uses `build_bot(token=settings.telegram_bot_token...)` + `telegram_sender.send_text_dm` (Phase 39/45 booking-reminder precedent). No new integration adapters.

### `payment_notifications` table (NOTIFY-03)

- **D-52-04:** New table `payment_notifications` (Alembic 0039, `down_revision = "0038_fiscal_receipts_created_at"`, `op.f()` naming convention, lossless downgrade):
  ```
  id            UUID PK (UUIDv4 app-side default)
  payment_id    UUID FK payments.id ON DELETE RESTRICT   -- the v1.4 ledger row (sale or refund)
  kind          VARCHAR(32) NOT NULL                      -- CHECK in the 4 kinds below
  channel       VARCHAR(16) NOT NULL                      -- CHECK IN ('telegram','email')
  sent_at       TIMESTAMPTZ NOT NULL DEFAULT now()
  created_at / updated_at  (Base + UUIDPkMixin + TimestampMixin, mirroring booking_notifications)
  ```
  UNIQUE `(payment_id, kind, channel)` → `uq_payment_notifications_payment_kind_channel` (NOT-03 idempotency, the cross-restart dedup arbiter). Keyed on `payments.id` (the ledger row) — works for both sale rows (positive amount) and refund rows (negative, `refund_of` set), so refund DMs key on the refund ledger row's id.
  Model lives in `app/modules/online_payments/models.py` (extend) or a sibling `notifications_model.py`; planner picks. CHECK constraint on `kind` enumerates: `payment_succeeded`, `refund_succeeded`, `payment_canceled`, `fiscal_failed`.
- **D-52-05:** Repository helpers in `app/modules/online_payments/repository.py` (or a notifications repo): `claim_payment_notification(session, *, payment_id, kind, channel) -> bool` (INSERT, returns False on IntegrityError = already claimed). The task is the txn owner (`async with session.begin()` per claim or per task; planner refines to keep claim+send atomic-enough that a crash mid-send leaves the row claimed = at-most-once-leaning, accepted per best-effort doctrine).

### Locked templates (NOTIFY-01 / NOTIFY-02)

- **D-52-06:** `app/modules/online_payments/notifications.py` (new) defines 4 `Final[str]` locked Russian Telegram templates with `# OWNER-COPY-LOCK` + `str.format(**kwargs)` renderers (KeyError-loud), per D-39-02:
  - `ONLINE_PAYMENT_SUCCEEDED_DM` → **client** (payment received + membership/PT-package activated confirmation)
  - `ONLINE_PAYMENT_REFUNDED_DM` → **client** (refund processed)
  - `ONLINE_PAYMENT_CANCELED_DM` → **owner-only operator alert** (NOT a client DM — per NOT-01 + NOT-05)
  - `FISCAL_RECEIPT_FAILED_DM` → **owner-only operator alert** (NOT-04)
- **D-52-07:** `app/modules/online_payments/email_templates.py` (currently an empty placeholder by Phase 49 D-49-01) gains 4 email identifiers, added to `LOCKED_EMAIL_TEMPLATES` (15 → 19): `EMAIL_ONLINE_PAYMENT_SUCCEEDED`, `EMAIL_ONLINE_PAYMENT_REFUNDED`, `EMAIL_ONLINE_PAYMENT_CANCELED` (owner), `EMAIL_FISCAL_RECEIPT_FAILED` (owner). The frozenset literal in `app/core/audit.py` is updated; the AST gate `test_locked_email_templates_ast.py` continues to enforce literal `template_id` at every `get_email_dispatcher()` callsite. New entries carry the `# OWNER-COPY-LOCK` lineage and feed CARRY-02's countersign register conceptually (but CARRY-02 only countersigns the original 15 v1.6 templates — see D-52-13).
- **D-52-08:** Owner-facing templates (canceled operator alert, fiscal-failed) are terse operator-actionable Russian copy (include `payment_id` / `yookassa_payment_id` + failure reason so the operator can act). Client-facing templates carry no failure-cause disclosure (anti-oracle hygiene preserved from C-12).

### Owner-alert recipient configuration (NOTIFY-04, gray area — no existing setting)

- **D-52-09:** **No owner-alert contact setting exists in the codebase today.** Add two optional Pydantic settings (likely `app/integrations/telegram/settings.py` + core settings, planner places): `OWNER_ALERT_TELEGRAM_CHAT_ID: int | None = None` and `OWNER_ALERT_EMAIL: str | None = None`. Owner operator alerts (`payment_canceled`, `fiscal_failed`) route here. If a value is unset → structlog ERROR only (best-effort, never raises, never blocks the commit). Document both env vars in the Phase 53 deployment runbook (VER-01 territory) — Phase 52 only consumes + defaults to None.

### Seam fill points (where notifications enqueue)

- **D-52-10:** Enqueue `dispatch_payment_notification` from the post-commit point of each event, AFTER the UoW commits (never inside the txn):
  - `handle_payment_succeeded` → `_post_commit_enqueue` ADDS the notification branch: enqueue `(payment_id=<sale ledger row id>, kind='payment_succeeded')`. (The seam already receives `online_payment_id` + `fiscal_receipt_id`; it must additionally thread the ledger `payment_id` — planner verifies the seam signature gains a `payment_id` param or resolves it.)
  - `_settle_online_refund` (`online_refunds/settle.py`, webhook + cron) → enqueue `(payment_id=<refund ledger row id>, kind='refund_succeeded')` after commit.
  - `handle_payment_canceled` → enqueue owner operator alert `(payment_id=<sale ledger row id or online_payment_id fallback>, kind='payment_canceled')`. Note: a canceled online payment may have no ledger `payments` row (activation is webhook-gated and canceled payments never activate) — planner decides the idempotency key basis (likely key the `payment_notifications` row on the `online_payments.id` for the canceled case via a nullable discriminator, OR use a separate dedup; **recommended: dedup canceled/fiscal-failed owner alerts on a stable id and accept that owner alerts may not have a ledger payment_id**). Planner resolves; the constraint is at-most-once owner alert across restarts.
  - `dispatch_fiscal_receipt` task failure path + `monitor_stale_fiscal_receipts` cron failure path → enqueue `(payment_id=<fiscal receipt's payment_id>, kind='fiscal_failed')`.
- **D-52-11:** **AST gate lockstep.** `_post_commit_enqueue`'s body grows from the Phase 51 shape (one `_log.info` + one guarded fiscal `enqueue_job`) to include the notification `enqueue_job`. `tests/integration/webhook_yookassa/test_post_commit_seam.py` MUST be updated in the SAME commit that grows the body (PATTERNS.md errata #3 discipline). The plan must add this gate update as a discrete task.

### NOTIFY-05 — cancellation differentiator (already largely satisfied)

- **D-52-12:** Phase 50's `handle_payment_canceled` ALREADY emits `online_payment_canceled` with `cancellation_party` + `cancellation_reason` from the webhook body (`handlers.py:~620`). Phase 52's NOT-05 work is therefore: (a) a regression test asserting the audit payload carries both fields AND that **no client DM is enqueued** on cancellation; (b) wire the owner operator alert (`ONLINE_PAYMENT_CANCELED_DM`, D-52-06). No client-facing notification on cancellation, by design.

### CARRY-01 / CARRY-02 — operator-gated discharge

- **D-52-13:** **Both carry-outs require the operator (real Yandex Postbox API key, owner's RU email aliases, owner's visual judgment).** AI agents ship the scaffolding; the operator executes + signs. Concretely:
  - **CARRY-01 (DEFER-46-01):** extend/confirm the probe script `apps/backend/scripts/verify/v1_6_email_probe.py` so it sends to yandex.ru + mail.ru + rambler.ru aliases and captures `Authentication-Results` headers; create the evidence directory `.planning/handoff/v1.7-email-deliverability-evidence/` with a README describing the capture procedure. The live run is operator-gated (requires real credentials) — recorded as an operator step, with structural attestation by the executing agent that the script + scaffolding are ready (mirror Phase 46 DEFER discipline).
  - **CARRY-02 (DEFER-46-02):** create/populate `.planning/handoff/v1.6-template-countersign.md` enumerating all 15 v1.6 `LOCKED_EMAIL_TEMPLATES` identifiers (NOT the 4 new Phase 52 ones — CARRY-02 is scoped to the v1.6 set) with a `signed_off_at:` placeholder. The owner's visual sanity check + timestamp is the operator action. No content edits to the templates.
- **D-52-14:** Phase 52 is **backend + scaffolding complete** when the notification code ships green and the carry-out scaffolding exists; the live probe run + owner countersign are operator deliverables recorded in the verification artifact (Phase 53 may confirm). This matches the solo-dev-with-AI operating model where the user is the operator.

### Claude's Discretion

Downstream agents may settle the following without re-asking:

- **Notification ARQ task `max_tries` / `_expires`:** mirror `dispatch_fiscal_receipt` (D-51 contract: `_max_tries=3`, modest `_expires`). Best-effort send — exhausted retries log ERROR, never crash.
- **Idempotency-row write timing:** claim (INSERT) before send so a crash mid-send leaves the channel claimed (at-most-once-leaning). Accepted per best-effort doctrine; planner may instead write-after-success if the team prefers at-least-once — **recommended: claim-before-send** to avoid duplicate client DMs on retry storms.
- **Telegram chat_id source:** `client.telegram_user_id` (BIGINT, the bot-binding id) is the chat id for `send_text_dm`. Null → skip Telegram channel.
- **Email recipient source:** `client.email` (nullable Text). Null → skip email channel. (Online sales already require email per the fiscal flow, so the sale/refund client path should generally have one.)
- **Owner-alert dedup basis for canceled/fiscal_failed:** planner picks a stable key; at-most-once owner alert across restarts is the only hard requirement.
- **Logger names:** `structlog.get_logger("modules.online_payments.tasks")` / `"modules.online_payments.notifications")` — module-namespace convention.
- **Template kind ↔ notification kind mapping:** `payment_succeeded`→`ONLINE_PAYMENT_SUCCEEDED_DM`/`EMAIL_ONLINE_PAYMENT_SUCCEEDED`; `refund_succeeded`→`ONLINE_PAYMENT_REFUNDED_DM`/`EMAIL_ONLINE_PAYMENT_REFUNDED`; `payment_canceled`→`ONLINE_PAYMENT_CANCELED_DM`/`EMAIL_ONLINE_PAYMENT_CANCELED` (owner); `fiscal_failed`→`FISCAL_RECEIPT_FAILED_DM`/`EMAIL_FISCAL_RECEIPT_FAILED` (owner).
- **No new LOCKED_AUDIT_EVENTS expected** — notifications do not emit audit rows (v1.6 booking/membership notification precedent: idempotency table IS the audit trail, no separate audit event). Confirm against booking_notifications precedent; if the team wants a `payment_notification_sent` audit event, it must be pre-registered per INFRA-35 — **recommended: NO new audit event** (mirror v1.6).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project / milestone scope
- `.planning/PROJECT.md` — milestone v1.7 framing; v1.6 cross-channel email + idempotency-discriminator precedent; RF regional constraints
- `.planning/REQUIREMENTS.md` lines 71–80 — NOTIFY-01..05 + CARRY-01..02 full text
- `.planning/REQUIREMENTS.md` traceability table lines 159–165 — NOTIFY/CARRY → Phase 52 mapping
- `.planning/ROADMAP.md` Phase 52 entry (lines 249–262) — goal + 6 success criteria
- `.planning/STATE.md` — deferred-items table; CARRY-01 = DEFER-46-01, CARRY-02 = DEFER-46-02

### Prior phase context (this milestone)
- `.planning/phases/51-fiscal-fsm-refunds/51-CONTEXT.md` — D-51-15 `_post_commit_enqueue` seam evolution + AST-gate-lockstep discipline; refund settle flow; circuit-breaker pattern
- `.planning/phases/50-webhook-fsm-fiscal-foundation/50-CONTEXT.md` — D-50-19 seam signature; D-50-25 `handle_payment_canceled` with cancellation_party/reason (NOT-05 already-done); fiscal_receipts table
- `.planning/phases/49-online-sales-orchestrator/49-CONTEXT.md` — D-49-01 empty `email_templates.py` placeholder rationale; OnlinePayment XOR shape
- `.planning/phases/47-bedrock/47-CONTEXT.md` — INFRA-35 LOCKED_AUDIT_EVENTS pre-registration discipline + AST gate

### v1.6 cross-channel precedent (the pattern Phase 52 mirrors)
- `.planning/milestones/v1.6-ROADMAP.md` — NOTIFY-08/10/12 cross-channel email mirrors; D-45-05/08/13 fire-and-forget + channel discriminator decisions
- `apps/backend/app/modules/bookings/notifications.py` — D-39-02 module-scope locked-copy pattern (`Final[str]` + `# OWNER-COPY-LOCK` + `str.format` renderers); the template-ownership template for D-52-06
- `apps/backend/app/modules/bookings/models.py:175` — `BookingNotification` model with `channel` discriminator + UNIQUE `(booking_id, kind)` → mirror shape for `payment_notifications` UNIQUE `(payment_id, kind, channel)`
- `apps/backend/app/workers/scheduled/send_booking_reminders.py` — dual-channel dispatch (Telegram `build_bot` + `telegram_sender` AND email) + idempotency-row insert; the dispatch template for D-52-01/02

### Code to extend (integration points)
- `apps/backend/app/api/v1/_internal/yookassa/handlers.py:269` — `_post_commit_enqueue` (add notification branch, D-52-10); `:~620` `handle_payment_canceled` (already emits cancellation fields)
- `apps/backend/app/modules/online_refunds/settle.py` — `_settle_online_refund` shared webhook+cron path (refund DM enqueue point)
- `apps/backend/app/modules/online_payments/email_templates.py` — empty Phase 49 placeholder; gains 4 identifiers (D-52-07)
- `apps/backend/app/core/audit.py:399` — `LOCKED_EMAIL_TEMPLATES` frozenset (15 → 19)
- `apps/backend/app/core/dependencies.py:676` — `get_email_dispatcher()` (email channel)
- `apps/backend/app/integrations/telegram/sender.py:57` — `send_text_dm`; `bot.py` `build_bot` (Telegram channel)
- `apps/backend/app/workers/__init__.py:131,137` — `WorkerSettings.functions` registration (add `dispatch_payment_notification`, bare-callable convention)
- `apps/backend/app/modules/clients/models.py:67,89` — `client.email` (nullable) + `client.telegram_user_id` (BIGINT) recipient sources

### AST gates that MUST update in lockstep
- `apps/backend/tests/integration/webhook_yookassa/test_post_commit_seam.py` — seam body shape (grows with notification enqueue, D-52-11)
- `apps/backend/tests/unit/test_locked_email_templates_ast.py` — literal `template_id` enforcement (4 new identifiers)

### Carry-out scaffolding targets
- `apps/backend/scripts/verify/v1_6_email_probe.py` — CARRY-01 probe script (extend if needed)
- `.planning/handoff/v1.7-email-deliverability-evidence/` — CARRY-01 evidence dir (create)
- `.planning/handoff/v1.6-template-countersign.md` — CARRY-02 countersign register (create with 15 v1.6 template names + `signed_off_at:` placeholder)

### Research (v1.7 milestone)
- `.planning/research/STACK.md` §2 — 54-ФЗ receipt structure (fiscal-failed context)
- `.planning/research/PITFALLS.md` Pitfall 11 — best-effort fire-and-forget + retry boundaries (notification send discipline)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `send_booking_reminders.py`: end-to-end dual-channel (Telegram + email) dispatch with idempotency-row insert — the closest analog; copy-and-adapt for `dispatch_payment_notification`.
- `bookings/notifications.py`: locked-copy module template (D-39-02) — replicate structure for `online_payments/notifications.py`.
- `dispatch_email` ARQ task + `get_email_dispatcher()`: email send already solved; reuse.
- `telegram_sender.send_text_dm` + `build_bot`: Telegram send already solved; reuse.
- `fiscal_receipts/tasks.py`: ARQ task structure + `WorkerSettings.functions` registration template for the new notification task.

### Established Patterns
- **Cross-channel idempotency:** UNIQUE `(subject_id, kind, channel)` on a `*_notifications` table is the cross-restart dedup arbiter (v1.6 Alembic 0024). `payment_notifications` mirrors it.
- **Fire-and-forget best-effort:** notification/alert sends NEVER roll back the financial commit and NEVER raise into the request/webhook path (v1.6 D-45-08).
- **Locked Russian copy:** `Final[str]` + `# OWNER-COPY-LOCK` + `str.format(**kwargs)` (KeyError-loud) + AST literal-template gate (D-39-02 / D-41-11).
- **Post-commit enqueue seam:** `_post_commit_enqueue` is the single fan-out point; AST gate guards its body shape — update in lockstep (D-51-15 precedent).
- **LOCKED set pre-registration:** frozenset is source of truth; AST gate enforces literal references (INFRA-35 / INFRA-36).

### Integration Points
- `_post_commit_enqueue` (sale-succeeded) + `_settle_online_refund` (refund) + `handle_payment_canceled` (owner alert) + `dispatch_fiscal_receipt`/`monitor_stale_fiscal_receipts` failure paths (owner alert) — five enqueue sites feeding one ARQ task.
- New owner-alert settings consumed by the fiscal-failed + canceled branches; default None → log-only.

</code_context>

<specifics>
## Specific Ideas

- NOT-05 audit enrichment is **already shipped** by Phase 50 — Phase 52 must not re-implement it, only test it + add the owner operator alert.
- `ONLINE_PAYMENT_CANCELED_DM` is an **owner** alert, not a client DM (explicit in NOT-01 + NOT-05) — easy to get wrong; the regression test in D-52-12 guards it.
- CARRY-01/02 are operator deliverables — AI ships scaffolding + structural attestation; the user runs the live probe and countersigns, consistent with the solo-dev-with-AI model and Phase 46's DEFER discipline.

</specifics>

<deferred>
## Deferred Ideas

- A `payment_notification_sent` LOCKED audit event — deliberately NOT added (mirror v1.6 where the idempotency table IS the trail). If reporting needs it later, pre-register per INFRA-35 in a future phase.
- Partial-refund (B-02) notification copy — blocked on B-02 itself (v1.8+).
- Cancellation visibility in a UI/reports surface — v1.8 Reports + Audit Log read API.

</deferred>

---

*Phase: 52-cross-channel-notifications-v1-6-carry-out*
*Context gathered: 2026-05-23*
