---
phase: 84-real-autopay-charge
verified: 2026-06-05T23:00:00Z
status: passed
score: 7/7 must-haves verified
overrides_applied: 0
---

# Phase 84: Real Autopay Charge Verification Report

**Phase Goal:** Cron charge_expiring_autopay реально списывает с сохранённой карты off-session для истекающих абонементов с autopay_enabled=true + consent_recorded_at; списание идёт в charge-ledger, активация продления locked на webhook, исход аудируется и клиент уведомляется.
**Verified:** 2026-06-05T23:00:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth                                                                                                                                   | Status     | Evidence                                                                                                                                                                   |
|----|-----------------------------------------------------------------------------------------------------------------------------------------|------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1  | charge_expiring_autopay cron exists, registered in WorkerSettings with unique=True at a distinct hour, eligibility JOIN enforces consent | VERIFIED   | `app/workers/scheduled/charge_expiring_autopay.py` + `app/workers/__init__.py:309` cron(hour=2, minute=0, unique=True); `service.py:162` `cpm.consent_recorded_at IS NOT NULL` |
| 2  | YooKassa adapter supports off-session charge via payment_method_id; no confirmation block; existing path byte-identical                  | VERIFIED   | `app/integrations/yookassa/client.py:167,213-228`: `payment_method_id: str | None = None`; off-session body has no confirmation key, existing redirect/QR path in `else:` branch |
| 3  | Charge-ledger (payments.Payment) method='autopay'; activation locked to payment.succeeded webhook (never in cron)                       | VERIFIED   | `handlers.py:457,466`: `is_autopay = row.confirmation_type == "autopay"` → `method="autopay" if is_autopay else "online"`; cron never creates memberships                  |
| 4  | Idempotency: DB claim ON CONFLICT DO NOTHING + deterministic sha256 key; duplicate tick or restart produces no double-charge             | VERIFIED   | `service.py:210-216`: INSERT ON CONFLICT (membership_id, period_end) DO NOTHING RETURNING id; `service.py:73-84`: sha256 hex of `{membership_id}:{period_end}`              |
| 5  | Skip matrix: no consent, autopay off, no card, already-renewed, out-of-window → zero charge; ФЗ-376 consent gate explicit               | VERIFIED   | `service.py:160-177` eligibility JOIN filters + NOT EXISTS already-renewed guard; 6 skip tests in `test_autopay_skip_matrix.py`                                             |
| 6  | Outcome audited: autopay_charge_initiated + autopay_charge_failed LOCKED events (count-lock 105), payload schemas registered            | VERIFIED   | `audit.py:471-472`; `audit_payloads.py:1320,1335,1452-1453`; both count-lock assertions == 105 (`test_audit_taxonomy.py:237`, `test_phase51_audit_chain_invariants.py:57`) |
| 7  | Client notified: success via dispatch_payment_notification(kind='autopay_charge_succeeded'); failure via dispatch_autopay_failure_notification(autopay_charge_id); both channel-idempotent and best-effort | VERIFIED | Success: `tasks.py:319,554-559`; Failure: `autopay_charges/tasks.py:157,202-265`; claim stores: PaymentNotification (success) + AutopayChargeNotification (failure); best-effort try/except per-channel |

**Score:** 7/7 truths verified

### Required Artifacts

| Artifact                                                          | Expected                                                          | Status     | Details                                                                                  |
|-------------------------------------------------------------------|-------------------------------------------------------------------|------------|------------------------------------------------------------------------------------------|
| `app/modules/autopay_charges/models.py`                           | AutopayCharge + AutopayChargeNotification ORM models              | VERIFIED   | Both classes present; AutopayCharge has UNIQUE(membership_id,period_end) + status CHECK + online_payment_id; AutopayChargeNotification has UNIQUE(autopay_charge_id,kind,channel) |
| `alembic/versions/0056_autopay_charges.py`                        | autopay_charges + autopay_charge_notifications + CHECK widening   | VERIFIED   | Both tables created; `uq_autopay_charges_membership_period` present; online_payment_id column present; confirmation_type widened via op.execute raw DDL |
| `alembic/versions/0057_payment_notifications_widen_kind.py`       | payment_notifications.kind CHECK widened for autopay_charge_succeeded | VERIFIED | Revision 0057, down_revision 0056; adds 'autopay_charge_succeeded' to 5-kind predicate |
| `app/core/audit.py`                                               | autopay_charge_initiated + autopay_charge_failed in LOCKED_AUDIT_EVENTS | VERIFIED | Lines 471-472; pre-registered before Plan 02 callsites                             |
| `app/core/audit_payloads.py`                                      | AutopayChargeInitiatedPayload + AutopayChargeFailedPayload + registry | VERIFIED | Lines 1320-1348; AUDIT_PAYLOAD_SCHEMAS entries at lines 1452-1453                    |
| `app/modules/autopay_charges/service.py`                          | _charge_expiring_autopay_memberships caller-owns-txn helper        | VERIFIED   | noqa: SVC001; no session.commit(); returns (count, declined_charge_ids)                 |
| `app/workers/scheduled/charge_expiring_autopay.py`                | ARQ cron entry with post-commit failure-notification enqueue       | VERIFIED   | Commits after helper; enqueues dispatch_autopay_failure_notification post-commit for each declined claim; uses autopay_charge_id (not online_payment_id) |
| `app/workers/__init__.py`                                         | charge_expiring_autopay + dispatch_autopay_failure_notification in functions; AutopayCharge eager-import; cron(unique=True, hour=2) | VERIFIED | Lines 98-101, 172, 177, 309; both callable registered; cron at hour=2, minute=0, unique=True |
| `app/api/v1/_internal/yookassa/handlers.py`                       | is_autopay discriminator: method='autopay' + kind='autopay_charge_succeeded' | VERIFIED | Lines 457, 466, 682, 685; local variable captures with literal string if/else |
| `app/modules/autopay_charges/notifications.py`                    | render_autopay_charge_succeeded_dm + render_autopay_charge_failed_dm | VERIFIED | Both functions present; owner-signed Russian copy; str.format with KeyError guard |
| `app/modules/autopay_charges/repository.py`                       | claim_autopay_failure_notification (fresh session, UNIQUE catch, never re-raises) | VERIFIED | Fresh session + begin(); catches IntegrityError; returns False on conflict; never re-raises |
| `app/modules/autopay_charges/tasks.py`                            | dispatch_autopay_failure_notification ARQ task (autopay_charge_id-keyed) | VERIFIED | Channel loop ("telegram","email"); claim-before-send per channel; per-channel try/except; never re-raises |
| `app/modules/online_payments/email_templates.py`                  | EMAIL_AUTOPAY_CHARGE_SUCCEEDED + EMAIL_AUTOPAY_CHARGE_FAILED templates | VERIFIED | Lines 59-60, 158, 175; both Final[str] constants and EmailTemplate records in TEMPLATES dict |
| `app/modules/online_payments/tasks.py`                            | autopay_charge_succeeded branch in dispatch_payment_notification   | VERIFIED   | Lines 319, 399, 554-559; resolves client via online_payments.client_id; uses string literal template_id; renders autopay DM |
| `app/core/audit.py` (LOCKED_EMAIL_TEMPLATES)                     | EMAIL_AUTOPAY_CHARGE_SUCCEEDED + EMAIL_AUTOPAY_CHARGE_FAILED locked | VERIFIED   | Lines 506-507 in LOCKED_EMAIL_TEMPLATES frozenset                                       |

### Key Link Verification

| From                                            | To                                              | Via                                             | Status   | Details                                                                                    |
|-------------------------------------------------|-------------------------------------------------|-------------------------------------------------|----------|--------------------------------------------------------------------------------------------|
| service.py                                      | autopay_charges table                           | INSERT ON CONFLICT (membership_id, period_end) DO NOTHING | VERIFIED | `service.py:210-216`                                                                |
| service.py                                      | yookassa_client.create_payment                  | payment_method_id= + sha256-hex idempotency_key | VERIFIED | `service.py:251-259`                                                                       |
| service.py (ok path)                            | online_payments row                             | INSERT raw SQL confirmation_type='autopay'       | VERIFIED | `service.py:288-313`                                                                       |
| charge_expiring_autopay.py (post-commit)        | dispatch_autopay_failure_notification            | arq_pool.enqueue_job with autopay_charge_id      | VERIFIED | `charge_expiring_autopay.py:65-73`                                                         |
| online_payments/tasks.py dispatch_payment_notification | autopay_charge_succeeded success copy     | kind == 'autopay_charge_succeeded' branch        | VERIFIED | `online_payments/tasks.py:319, 399, 554-559`                                               |
| autopay_charges/tasks.py                        | autopay_charge_notifications claim table        | claim_autopay_failure_notification(autopay_charge_id=..., kind='autopay_charge_failed', channel) | VERIFIED | `tasks.py:227-231`; `repository.py:64-78` |
| handlers.py                                     | payments.Payment method='autopay'               | is_autopay discriminator → get_payment_recorder(method=...) | VERIFIED | `handlers.py:457, 466`                                                            |
| alembic/env.py                                  | app.modules.autopay_charges.models              | eager import line 45                             | VERIFIED | `import app.modules.autopay_charges.models  # Phase 84 APAY-03/APAY-04 / 0056`            |

### Data-Flow Trace (Level 4)

| Artifact                                   | Data Variable          | Source                                          | Produces Real Data | Status    |
|--------------------------------------------|------------------------|-------------------------------------------------|--------------------|-----------|
| service.py eligible rows                   | rows from eligibility_sql | raw SQL JOIN memberships→membership_plans→clients→client_payment_methods | Yes — live DB | FLOWING |
| charge_expiring_autopay.py count           | count, declined_charge_ids | _charge_expiring_autopay_memberships return value | Yes — from DB rows | FLOWING |
| handlers.py method/kind labels             | is_autopay             | row.confirmation_type from DB SELECT FOR UPDATE  | Yes — live DB      | FLOWING   |
| dispatch_payment_notification (autopay success) | client_first_name, amount_rub, autopay_end_date | online_payments + clients metadata tables | Yes | FLOWING |
| dispatch_autopay_failure_notification      | client_first_name, amount_rub | autopay_charges→memberships→clients via metadata tables | Yes | FLOWING |

### Behavioral Spot-Checks

Step 7b: SKIPPED — requires a running ARQ worker and live YooKassa connection. The orchestrator confirmed the full test suite (2592 passed, including 34 autopay tests and webhook discriminator tests) as behaviorally equivalent to spot-checks.

### Probe Execution

No probe-*.sh scripts declared for this phase. The orchestrator confirmed: ruff clean (autopay APP source), mypy --strict clean (242 files), lint-imports 3 kept/0 broken, alembic-clean green, full backend suite 2592 passed, autopay suite 34 + webhook suite green.

### Requirements Coverage

| Requirement | Source Plan | Description                                                                                          | Status    | Evidence                                                                                                                    |
|-------------|-------------|------------------------------------------------------------------------------------------------------|-----------|-----------------------------------------------------------------------------------------------------------------------------|
| APAY-01     | 84-02       | Cron charge_expiring_autopay списывает с сохранённой карты off-session для абонементов с autopay+consent | VERIFIED | charge_expiring_autopay.py + service.py eligibility JOIN with consent_recorded_at IS NOT NULL gate; WorkerSettings.cron_jobs registration |
| APAY-02     | 84-01, 84-02 | YooKassa off-session charge по payment_method_id; в charge-ledger; активация locked на webhook       | VERIFIED  | client.py:167 payment_method_id param; handlers.py:466 method="autopay"; D-06 activation path unchanged; migration 0056 widens confirmation_type CHECK |
| APAY-03     | 84-01, 84-02 | Идемпотентно (нет двойного charge); пропускает неподходящих                                          | VERIFIED  | service.py ON CONFLICT DO NOTHING + sha256 idempotency_key; 6 skip conditions in test_autopay_skip_matrix.py; 4 idempotency tests |
| APAY-04     | 84-01, 84-03 | Исход аудируется LOCKED events (INFRA-15); клиент уведомляется Telegram+email, channel-idempotent    | VERIFIED  | audit.py:471-472 pre-registered; audit_payloads.py schemas; notifications.py renderers; autopay_charge_notifications claim table; 3 notification idempotency tests |

### Anti-Patterns Found

| File                                                        | Line | Pattern     | Severity | Impact                              |
|-------------------------------------------------------------|------|-------------|----------|-------------------------------------|
| `app/modules/autopay_charges/notifications.py:13`           | 13   | "placeholder" in docstring | Info | False positive — refers to str.format placeholder substitution discipline, not a code stub |

No TBD, FIXME, or XXX debt markers found in any Phase 84 files. No stub implementations (empty returns, hardcoded empty arrays/dicts passed to renderers). No unreferenced or orphaned artifacts.

### Human Verification Required

None. All observable truths are verifiable from code structure and test coverage. This is a pure-backend phase with no visual UI components.

### Gaps Summary

No gaps. All 7 truths from the ROADMAP Success Criteria are verified with direct codebase evidence:

1. **APAY-01 (Cron):** `charge_expiring_autopay` is a real ARQ cron function registered with `unique=True` at `hour=2, minute=0`, calling a service helper that queries live DB rows via a JOIN that enforces `consent_recorded_at IS NOT NULL`, `autopay_enabled=true`, and `unlinked_at IS NULL`.

2. **APAY-02 (YooKassa + ledger + webhook-locked activation):** `create_payment` accepts `payment_method_id` and builds an off-session body without a confirmation block. The webhook handler reads `row.confirmation_type == "autopay"` to label the ledger row `method="autopay"` and enqueue `kind="autopay_charge_succeeded"`. The cron never creates memberships.

3. **APAY-03 (Idempotency + skip matrix):** `INSERT ... ON CONFLICT (membership_id, period_end) DO NOTHING RETURNING id` guards double-charge at the DB level. The sha256 deterministic key guards crash-between-claim-and-provider at the provider level. Six distinct skip conditions are tested in `test_autopay_skip_matrix.py`.

4. **APAY-04 (Audit + notifications):** Two LOCKED audit events (`autopay_charge_initiated`, `autopay_charge_failed`) with payload schemas are pre-registered (count-lock 105). Success notifications are channel-idempotent via `PaymentNotification UNIQUE(online_payment_id, kind, channel)`. Failure notifications are channel-idempotent via `AutopayChargeNotification UNIQUE(autopay_charge_id, kind, channel)`. A declined charge creates no `online_payments` row — the failure path correctly keys on `autopay_charges.id`. Both channels use best-effort try/except so one channel failure never blocks the other.

Note on CR-01 (SUMMARY acknowledged fix): The success notification correctly passes `op_row_id` (online_payments.id) rather than `ledger_payment_id` (payments.id) to `dispatch_payment_notification` — confirmed at `handlers.py:683`. This is the correct semantics since `dispatch_payment_notification` for `autopay_charge_succeeded` resolves via `online_payments.client_id`.

Note on CR-02 (SUMMARY acknowledged fix): Transient errors (`transient_error` classification) DELETE the claim row so the next cron tick can retry — confirmed at `service.py:368-390`. This is correct behavior: the deterministic idempotency key ensures the provider deduplicates a duplicate call if the original actually succeeded.

---

_Verified: 2026-06-05T23:00:00Z_
_Verifier: Claude (gsd-verifier)_
