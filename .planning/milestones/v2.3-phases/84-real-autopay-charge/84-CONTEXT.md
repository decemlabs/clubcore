# Phase 84: Real Autopay Charge - Context

**Gathered:** 2026-06-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver real off-session recurring charges: an ARQ cron `charge_expiring_autopay` that
finds memberships expiring within a window with `autopay_enabled=true` + recorded
`consent_recorded_at` + an active saved card, and initiates an off-session YooKassa
charge against the saved `payment_method_id`. The charge writes to the v1.4 charge-ledger;
renewal activation is locked to the `payment.succeeded` webhook. Charging is idempotent
(no double-charge on repeated ticks / container restarts), skips ineligible memberships,
audits the outcome via new LOCKED events, and notifies the client (Telegram + email mirror).
This is the highest-risk, most-independent v2.3 block (real money movement). Pure backend —
NO UI. Builds on v2.2 card-on-file (`client_payment_methods`).
</domain>

<decisions>
## Implementation Decisions

### Cron Selection & Window (APAY-01)
- New ARQ cron `charge_expiring_autopay`, modeled on `app/workers/scheduled/expire_memberships.py`: caller-owns-txn helper that does NOT commit; the cron fn commits after the helper; SQL-level idempotency (uncommitted = next tick re-picks). Registered in `WorkerSettings.functions` + `cron_jobs` with `cron(..., unique=True)`, daily at a distinct hour (NOT 3:05 — expire_memberships owns that).
- Window: memberships whose `end_date` falls within `[today, today + N]`, **N configurable (default 3 days)** before expiry.
- Eligibility filter (ALL must hold): `autopay_enabled=true` AND `consent_recorded_at IS NOT NULL` AND an active saved card (`client_payment_methods` alive row with a `yookassa_method_id`) exists AND not already charged/renewed for this period (see idempotency). ФЗ-376 consent check is mandatory — never charge without recorded consent.

### Off-Session Charge & Charge-Ledger (APAY-02)
- Extend the YooKassa adapter `create_payment` (`app/integrations/yookassa/client.py`) with an optional `payment_method_id` param: when provided, build an **off-session** body (`payment_method_id` + `capture: true`, NO `confirmation` block — recurring/off-session). When absent, behavior is byte-identical to today (the existing redirect/QR checkout path is untouched).
- The charge is recorded in the v1.4 charge-ledger `app/modules/payments/Payment` (`subject_kind='membership'`, `method='autopay'`, signed positive `amount_kopecks`, status per v1.4 discipline).
- **Renewal activation is locked to the `payment.succeeded` webhook** (D-06). The cron only INITIATES the charge; the existing membership-activation chain on the succeeded webhook creates/extends the renewal membership. The cron NEVER activates synchronously.
- Charge amount = the membership plan's CURRENT `price_kopecks` (renewal at current price).

### Idempotency & Skip Logic (APAY-03) — highest-risk
- New `autopay_charges` claim/ledger table with a **UNIQUE(membership_id, period_end)** constraint. The cron INSERTs a claim row via `on_conflict_do_nothing` BEFORE calling YooKassa — if the insert conflicts (claim already exists), the period is already being/has been charged → skip. This is the DB-level double-charge guard.
- Belt-and-suspenders: the YooKassa call uses a **deterministic `idempotency_key`** derived from `(membership_id, period_end)` so a crash between claim-insert and YooKassa-call cannot double-charge at the provider either.
- Skip conditions (no charge initiated): no consent / autopay off / no active saved card / a renewal membership covering the next period already exists / a charge claim for this period already exists.
- Failure handling: on a sync decline/error, record the failed attempt on the claim row (status='failed') so the next tick does NOT retry-spam the same period; notify the client. No automatic retry/backoff this milestone (manual or next period).
- "Already renewed" detection: skip if a membership covering the next period already exists OR a succeeded autopay charge for this period exists.

### Audit & Notification (APAY-04)
- TWO new LOCKED audit events, registered in `LOCKED_AUDIT_EVENTS` + `audit_payloads` BEFORE any callsite (INFRA-15), count-lock guards bumped **103 → 105** (`test_audit_taxonomy`, `test_phase51_audit_chain_invariants`, + loyalty/autopay audit unit test):
  - `autopay_charge_initiated` — emitted by the cron when a charge is initiated (resource_type e.g. `autopay`/`membership`).
  - `autopay_charge_failed` — emitted on a synchronous decline/error.
  - Success outcome is captured by the existing `payment.succeeded` webhook activation chain (membership renewal events) — no separate success event needed, but if the planner finds the existing chain insufficient to attribute the autopay success, a third `autopay_charge_succeeded` may be added (count-lock adjusted accordingly).
- Notifications: Telegram primary + email mirror, idempotent via the existing `channel` discriminator dispatcher discipline. Success DM on webhook activation ("абонемент продлён автосписанием"); failure DM on sync decline ("автосписание не прошло — обновите карту"). Owner-signed copy following the existing template discipline (email templates mirror the Telegram copy per the 999.2 precedent).

### Claude's Discretion
- Exact `autopay_charges` column set + index/constraint names, the configurable-window setting location (config vs constant), the precise distinct cron hour, migration sequence number (next after 0055), notification template wording (owner-signable), and whether a third `autopay_charge_succeeded` event is warranted — at plan/execute discretion following established conventions.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/workers/scheduled/expire_memberships.py` — the cron analog: caller-owns-txn helper (`# noqa: SVC001`), commit in the cron fn, SQL-level idempotency, locked summary-event shape. `app/workers/__init__.py` `WorkerSettings.functions` + `cron_jobs` (cron(..., unique=True), hour=3 minute=5 for expire_memberships).
- `app/integrations/yookassa/client.py:154` `create_payment` — extend with `payment_method_id` for off-session (currently supports `save_payment_method`, `confirmation_type`, caller-owned `idempotency_key`). `types.py` `YooKassaPaymentResult`.
- `app/modules/payment_methods/models.py` `ClientPaymentMethod` — `yookassa_method_id` (plaintext token, NEVER serialized), `autopay_enabled`, `consent_recorded_at`. repository/service for reads.
- `app/modules/payments/models.py:44` `Payment` — v1.4 charge-ledger (subject_kind/subject_id, signed amount_kopecks, method, status, CHECK sign-matches-subject).
- `app/api/v1/_internal/yookassa/handlers.py` — the `payment.succeeded` UoW (membership activation + charge-ledger + promo/loyalty redemption). The autopay renewal activates through this same path.
- `app/core/audit.py` + `audit_payloads.py` — LOCKED event registration (count currently 103 after Phase 83); INFRA-15 before-callsite discipline; count-lock guard tests.
- Notifications: `app/integrations/email/dispatcher.py` + the Telegram DM path + `channel` discriminator idempotency (999.2 email-template-mirror precedent).
- `app/modules/memberships/models.py` `Membership` — `end_date` is the expiry field used by expire_memberships.

### Established Patterns
- Money = integer kopecks (signed in payments ledger), no float.
- Cron: caller-owns-txn helper + commit in cron fn; `cron(unique=True)`; SQL-level idempotency.
- Activation webhook-locked (D-06); off-session charge initiates, webhook activates.
- Audit events registered before callsites (INFRA-15); count-lock guard tests bumped.
- Cross-channel notifications idempotent via `channel` discriminator.
- New module/table → `.importlinter` modules-independent; migration follows Alembic conventions; register new model in `alembic/env.py` allowlist (Phase 82/83 precedent) to keep `test_alembic_clean` green.
- Backend tests: `httpx ASGITransport` + `pytest-asyncio`; YooKassa mocked via respx; cron tested by invoking the worker fn with a fake ctx/sessionmaker.

### Integration Points
- Cron fn `charge_expiring_autopay` in `app/workers/scheduled/` + `WorkerSettings` registration.
- YooKassa adapter `create_payment` off-session extension.
- New `autopay_charges` table + migration (next after 0055) + env.py allowlist.
- Charge-ledger write via `payments.Payment`.
- Webhook activation reuse (`handlers.py` succeeded UoW) for the renewal.
- Audit registration (`audit.py` + `audit_payloads.py` + count-lock tests).
- Notification dispatch (Telegram + email mirror).

</code_context>

<specifics>
## Specific Ideas

- The DB claim row (`autopay_charges` UNIQUE(membership_id, period_end)) is the PRIMARY double-charge guard; the deterministic YooKassa idempotency_key is the secondary guard against a crash between claim and provider call. Test BOTH: duplicate cron tick (DB conflict → skip) and a simulated restart between claim and charge (idempotency_key → provider dedupe).
- Test the full skip matrix: no consent, autopay off, no active card, already-renewed, already-claimed.
- Test failure path: declined charge → claim row status='failed', failure audit event, failure notification, and the next tick does NOT re-charge the same period.
- ФЗ-376: never initiate a charge without `consent_recorded_at` — assert in a test.

</specifics>

<deferred>
## Deferred Ideas

- Automatic retry/backoff on decline — out of scope this milestone (record failure, no retry).
- Dunning sequences / multiple reminder DMs — out of scope.
- OpenAPI byte-stable freeze + `_v23Checks` guards (autopay has no new client HTTP paths, but any client-visible autopay status fields are frozen) → Phase 85.
- admin-web autopay management UI — frozen, out of scope.

</deferred>
