---
phase: 52-cross-channel-notifications-v1-6-carry-out
verified: 2026-05-23T00:00:00Z
status: human_needed
score: 4/6 fully verified; 2/6 PARTIAL (operator-gated by design)
overrides_applied: 0
human_verification:
  - test: "CARRY-01 — Run live RU email-deliverability probe"
    expected: |
      Execute: PROBE_YANDEX_TO=you+probe@yandex.ru PROBE_MAIL_TO=you+probe@mail.ru
      PROBE_RAMBLER_TO=you+probe@rambler.ru EMAIL_PROVIDER_API_KEY=<key>
      AWS_ACCESS_KEY_ID=<key> EMAIL_FROM_DOMAIN=mail.sportzal.ru
      uv run python -m scripts.verify.v1_6_email_probe  (from apps/backend/)
      Exit code 0. Capture Authentication-Results headers from each mailbox
      (spf=pass, dkim=pass, dmarc=pass). Save three YAML evidence files to
      .planning/handoff/v1.7-email-deliverability-evidence/ (yandex_ru.yaml,
      mail_ru.yaml, rambler_ru.yaml).
    why_human: >
      Live send to production RU mailboxes requires real Yandex Postbox API
      credentials and operator-owned yandex.ru/mail.ru/rambler.ru aliases.
      Cannot be automated. Scaffolding (probe script + evidence-dir README) is
      complete and ready. D-52-13/D-52-14.
  - test: "CARRY-02 — Owner countersigns 15 v1.6 LOCKED_EMAIL_TEMPLATES"
    expected: |
      Open .planning/handoff/v1.6-template-countersign.md.
      For each of the 15 v1.6 template identifiers: locate the template file,
      visually sanity-check the Russian copy (subject, body, placeholder vars).
      Fill signed_off_at: with an ISO-8601 UTC timestamp in each row.
      All 15 rows must have a timestamp; no TODO placeholders must remain.
      Commit the updated file.
    why_human: >
      Owner visual sign-off on Russian copy requires a human. AI shipped the
      register with all 15 identifiers and placeholder cells. The owner's
      timestamps are the operator deliverable that closes DEFER-46-02.
      D-52-13/D-52-14.
---

# Phase 52: Cross-Channel Notifications + v1.6 Carry-out — Verification Report

**Phase Goal:** Payment and refund outcomes are communicated to clients via Telegram DM and email; two v1.6 operator deferrals (live email probe + template countersign) are formally closed.
**Verified:** 2026-05-23
**Status:** human_needed (4 of 6 success criteria VERIFIED; 2 of 6 PARTIAL — operator-gated by design per D-52-13/D-52-14; automated test suite passes 39/39)
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Success Criterion | Status | Evidence |
|---|-------------------|--------|----------|
| 1 | On `payment.succeeded`, client receives Telegram DM + email; UNIQUE `(payment_id, kind, channel)` prevents duplicate notifications across restarts | VERIFIED | `dispatch_payment_notification` task with per-channel claim-before-send; two partial UNIQUE indexes in Alembic 0039; `test_payment_succeeded_dual_channel_then_restart_no_duplicate` passes (restart produces `skipped`) |
| 2 | On `refund.succeeded`, client receives Telegram DM + email via same idempotency pattern | VERIFIED | `handle_refund_succeeded` calls `_post_commit_enqueue` with `payment_id=settled_locals.refund_payment_id, kind="refund_succeeded"`; `test_refund_succeeded_dual_channel` passes |
| 3 | When `fiscal_receipts.status` → `failed`, owner receives `FISCAL_RECEIPT_FAILED_DM` Telegram + best-effort owner email | VERIFIED | `_terminal_failure` in `fiscal_receipts/tasks.py` enqueues `dispatch_payment_notification(kind='fiscal_failed')` post-commit; `_monitor_stale_fiscal_receipts` in `fiscal_receipts/service.py` does the same; `test_fiscal_failed_routes_owner_alert_and_is_idempotent_across_restart` passes |
| 4 | `LOCKED_EMAIL_TEMPLATES` frozenset extended 15 → 19; AST gate still rejects non-literal `template_id` | VERIFIED | `python -c "from app.core.audit import LOCKED_EMAIL_TEMPLATES; print(len(LOCKED_EMAIL_TEMPLATES))"` → `19`; 10/10 AST gate tests pass including 4 new Phase 52 literal-callsite tests |
| 5 | CARRY-01 closed: live RU email-deliverability probe run; `Authentication-Results` headers captured | PARTIAL | Scaffolding complete: `scripts/verify/v1_6_email_probe.py` targets all 3 providers (yandex.ru, mail.ru, rambler.ru); `.planning/handoff/v1.7-email-deliverability-evidence/README.md` documents capture procedure. **Live run is operator-gated** (real Yandex Postbox credentials + RU aliases required). Evidence YAML files not yet saved. |
| 6 | CARRY-02 closed: owner countersigns all 15 v1.6 `LOCKED_EMAIL_TEMPLATES`; `signed_off_at` recorded | PARTIAL | Scaffolding complete: `.planning/handoff/v1.6-template-countersign.md` lists all 15 v1.6 identifiers with `TODO` placeholder cells and full instructions. **Owner visual sign-off is operator-gated**. No `signed_off_at` timestamps filled yet. |

**Score:** 4/4 technical criteria VERIFIED; 2/2 operator-gated criteria PARTIAL (scaffolding complete, execution pending)

---

### Carried-Forward Operator Deliverables

Per D-52-13 / D-52-14 (mirrors Phase 46 DEFER discipline), the following are human deliverables that the AI cannot execute:

| Item | Scaffolding Status | Operator Action Required |
|------|-------------------|--------------------------|
| CARRY-01 (DEFER-46-01): Live RU email probe | Ready — `apps/backend/scripts/verify/v1_6_email_probe.py` + `README.md` in evidence dir | Run probe with real credentials; save 3 YAML evidence files to `.planning/handoff/v1.7-email-deliverability-evidence/` |
| CARRY-02 (DEFER-46-02): Owner 15-template countersign | Ready — `.planning/handoff/v1.6-template-countersign.md` with all 15 identifiers + placeholder cells | Fill `signed_off_at:` for each of the 15 rows; commit the file |

These are NOT code defects. They represent the intended solo-dev-with-AI operating model where the operator is the human.

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `alembic/versions/0039_payment_notifications.py` | `payment_notifications` table with two partial UNIQUE indexes | VERIFIED | XOR CHECK, two FK columns, kind/channel CHECK constraints, `uq_payment_notifications_payment_kind_channel` (WHERE payment_id IS NOT NULL), `uq_payment_notifications_online_payment_kind_channel` (WHERE online_payment_id IS NOT NULL) |
| `app/modules/online_payments/models.py` | `PaymentNotification` ORM model | VERIFIED | Extends file; polymorphic subject FKs; all CHECKs documented in `__table_args__` |
| `app/modules/online_payments/notifications.py` | 4 locked Russian DM templates with `# OWNER-COPY-LOCK` | VERIFIED | `ONLINE_PAYMENT_SUCCEEDED_DM`, `ONLINE_PAYMENT_REFUNDED_DM`, `ONLINE_PAYMENT_CANCELED_DM` (owner), `FISCAL_RECEIPT_FAILED_DM` (owner); `str.format(**kwargs)` renderers |
| `app/modules/online_payments/email_templates.py` | 4 `EMAIL_*` Final constants | VERIFIED | `EMAIL_ONLINE_PAYMENT_SUCCEEDED`, `EMAIL_ONLINE_PAYMENT_REFUNDED`, `EMAIL_ONLINE_PAYMENT_CANCELED`, `EMAIL_FISCAL_RECEIPT_FAILED` |
| `app/core/audit.py` | `LOCKED_EMAIL_TEMPLATES` 15 → 19 | VERIFIED | Confirmed 19 via runtime check |
| `app/modules/online_payments/tasks.py` | `dispatch_payment_notification` ARQ task | VERIFIED | Substantive implementation: per-channel claim-before-send, 4 kind branches, owner-alert routing, `send_text_dm` + `get_email_dispatcher()` integration, `_MAX_TRIES=3` |
| `app/modules/online_payments/repository.py` | `claim_payment_notification` helper | VERIFIED | XOR assertion, INSERT with `IntegrityError` → `False` path |
| `app/workers/__init__.py` | `dispatch_payment_notification` in `WorkerSettings.functions` | VERIFIED | Line 146: bare callable registration |
| `app/core/config.py` | `owner_alert_telegram_chat_id`, `owner_alert_email` settings | VERIFIED | Both `int | None = None` optional Pydantic fields |
| `scripts/verify/v1_6_email_probe.py` | CARRY-01 probe script targeting yandex/mail/rambler | VERIFIED | All 3 providers via `PROBE_YANDEX_TO`, `PROBE_MAIL_TO`, `PROBE_RAMBLER_TO` env vars; production-shape `EmailClient` |
| `.planning/handoff/v1.7-email-deliverability-evidence/README.md` | Evidence-dir with capture procedure | VERIFIED | Full operator capture procedure documented |
| `.planning/handoff/v1.6-template-countersign.md` | 15 v1.6 templates with `signed_off_at` placeholders | VERIFIED (scaffolding) | All 15 identifiers listed; `TODO` placeholders pending owner |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `handle_payment_succeeded` | `dispatch_payment_notification` | `_post_commit_enqueue(payment_id=ledger_id, kind="payment_succeeded")` | WIRED | `handlers.py:517-525` |
| `handle_refund_succeeded` | `dispatch_payment_notification` | `_post_commit_enqueue(payment_id=settled_locals.refund_payment_id, kind="refund_succeeded")` | WIRED | `handlers.py:836-845` |
| `handle_payment_canceled` | `dispatch_payment_notification` | Direct `arq_pool.enqueue_job("dispatch_payment_notification", _kwargs={..., "kind":"payment_canceled"})` | WIRED | `handlers.py:661-667`; uses `op_row_id_canceled` (online_payments.id, not ledger row) |
| `dispatch_fiscal_receipt` failure paths | `dispatch_payment_notification` | `_terminal_failure(arq_pool=redis)` enqueues `kind="fiscal_failed"` | WIRED | `fiscal_receipts/tasks.py:251-257`; called from transient-max-tries, validation_error, permanent_error branches |
| `monitor_stale_fiscal_receipts` cron | `dispatch_payment_notification` | `_monitor_stale_fiscal_receipts(arq_pool=ctx["redis"])` accumulates then enqueues | WIRED | `fiscal_receipts/service.py:103-110`; `monitor_stale_fiscal_receipts.py:50` threads `arq_pool` |
| `dispatch_payment_notification` task | `claim_payment_notification` | `payment_repo.claim_payment_notification(session_factory, kind=..., channel=..., payment_id/online_payment_id=...)` | WIRED | `tasks.py:410-422`; routes `payment_canceled` to `online_payment_id` branch correctly |
| `dispatch_payment_notification` task | Telegram `send_text_dm` | `build_bot(token=...) + telegram_sender.send_text_dm(bot, chat_id=..., text=...)` | WIRED | `tasks.py:464` |
| `dispatch_payment_notification` task | Email `get_email_dispatcher()` | `_dispatch_email(kind, email_addr, **kwargs)` with literal `template_id=` | WIRED | `tasks.py:486`; AST gate enforces literal template IDs |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `dispatch_payment_notification` (client path) | `client_first_name`, `client_email`, `client_telegram_user_id` | `_resolve_client_row()` → SA query `payments → memberships/pt_packages → clients` | Yes — real DB join resolves contact fields | FLOWING |
| `dispatch_payment_notification` (owner path) | `tg_chat_id`, `owner_email` | `get_settings().owner_alert_telegram_chat_id` / `.owner_alert_email` | Yes — from Pydantic settings (defaults None → log-only per D-52-09) | FLOWING |
| `claim_payment_notification` | idempotency row | `INSERT INTO payment_notifications` with partial-UNIQUE guard | Yes — real DB INSERT; `IntegrityError` → False | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| LOCKED_EMAIL_TEMPLATES has 19 entries | `uv run python -c "from app.core.audit import LOCKED_EMAIL_TEMPLATES; print(len(LOCKED_EMAIL_TEMPLATES))"` | `19` | PASS |
| Full test suite (integration + AST gate) | `uv run pytest tests/integration/online_payments/ tests/unit/test_locked_email_templates_ast.py -q` | `39 passed in 7.02s` | PASS |

---

### Probe Execution

Step 7c: SKIPPED for CARRY-01 — live probe requires real Yandex Postbox credentials and operator-owned RU mailboxes. This is by design (D-52-13). The probe script exists and is verified runnable in dry-run import sense; the live execution is an operator deliverable.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| NOTIFY-01 | 52-01, 52-04 | 4 locked Telegram DM templates; module-scope copy ownership (D-39-02) | SATISFIED | `notifications.py`: 4 `Final[str]` with `# OWNER-COPY-LOCK` + `str.format` renderers |
| NOTIFY-02 | 52-02, 52-04 | 4 email template identifiers; `LOCKED_EMAIL_TEMPLATES` 15 → 19; AST gate continues | SATISFIED | `email_templates.py`: 4 constants; `audit.py`: 19-entry frozenset; 10 AST gate tests pass |
| NOTIFY-03 | 52-01 | `payment_notifications` table with UNIQUE `(payment_id, kind, channel)`; channel ∈ {telegram, email} | SATISFIED | Alembic 0039 with two partial UNIQUE indexes + XOR CHECK; idempotency proven by test |
| NOTIFY-04 | 52-02, 52-04, 52-05 | Owner alert on fiscal failure — FISCAL_RECEIPT_FAILED_DM + owner email; best-effort | SATISFIED | Two enqueue sites: `dispatch_fiscal_receipt._terminal_failure` + `_monitor_stale_fiscal_receipts`; owner-alert routing in task |
| NOTIFY-05 | 52-05, 52-06 | Cancellation audit carries `cancellation_party` + `cancellation_reason`; NO client DM | SATISFIED | `handlers.py:635-636` emits both fields; `test_cancellation_audit_carries_party_and_reason` + `test_cancellation_enqueues_owner_alert_only_no_client_dm` both pass |
| CARRY-01 | 52-03 | DEFER-46-01 closed: live RU email probe run; evidence captured | PARTIAL | Scaffolding ready; live run is operator-gated |
| CARRY-02 | 52-03 | DEFER-46-02 closed: owner countersigns 15 v1.6 templates | PARTIAL | Scaffolding ready; owner sign-off is operator-gated |

---

### Anti-Patterns Found

No blockers or warnings detected in the Phase 52 production files.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | No TBD / FIXME / XXX markers found in any Phase 52 file | — | — |
| — | — | No empty stubs (`return null`, `return {}`, `pass` implementations) in new files | — | — |

**Note on pre-existing tech-debt:** Phase 52 SUMMARY documents pre-existing DEFER-46-04 mypy/ruff debt in `online_refunds/settle.py`, `fiscal_receipts/tasks.py`, `online_payments/router.py`. These are confirmed pre-existing at the phase base commit and are not Phase 52 defects. Not flagged.

---

### Human Verification Required

#### 1. CARRY-01 — Live RU Email Deliverability Probe

**Test:** From `apps/backend/`, set the 6 environment variables documented in `.planning/handoff/v1.7-email-deliverability-evidence/README.md` and run:
```
uv run python -m scripts.verify.v1_6_email_probe
```
**Expected:** Exit code 0; probe prints `provider_message_id` for each of yandex.ru, mail.ru, rambler.ru. Then open each recipient mailbox, select "Show original", locate `Authentication-Results:` header showing `spf=pass dkim=pass dmarc=pass`. Save three YAML files (`yandex_ru.yaml`, `mail_ru.yaml`, `rambler_ru.yaml`) to `.planning/handoff/v1.7-email-deliverability-evidence/`. Commit.
**Why human:** Requires real Yandex Postbox API credentials and operator-owned RU mailbox aliases. Cannot be automated.

#### 2. CARRY-02 — Owner Template Countersign

**Test:** Open `.planning/handoff/v1.6-template-countersign.md`. For each of the 15 rows, locate the template file, visually verify the Russian copy, fill the `signed_off_at:` cell with an ISO-8601 UTC timestamp.
**Expected:** All 15 `signed_off_at:` cells populated; no `TODO` placeholders remain. Commit the file.
**Why human:** Owner's visual judgment on Russian email copy quality is required. No automated check can substitute for this.

---

### Gaps Summary

No code defects were found. All 4 technical success criteria are VERIFIED by codebase inspection and a passing test suite (39/39 tests). The 2 remaining criteria (CARRY-01, CARRY-02) are PARTIAL by design — the AI shipped complete scaffolding and the live execution + owner sign-off are operator deliverables documented in D-52-13/D-52-14.

The phase goal ("Payment and refund outcomes are communicated to clients via Telegram DM and email") is technically achieved in code. The v1.6 carry-outs are scaffolded and ready for operator execution.

---

_Verified: 2026-05-23_
_Verifier: Claude (gsd-verifier)_
