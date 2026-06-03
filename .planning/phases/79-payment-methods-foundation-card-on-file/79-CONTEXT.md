# Phase 79: Payment Methods Foundation + Card-on-File - Context

**Gathered:** 2026-06-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Client can save a payment card during checkout and manage it through new client-portal
endpoints. Scope: migration 0052 (`client_payment_methods` + `save_payment_method` intent
column on `online_payments`), a new `app/modules/payment_methods/` module, a webhook
save-step that captures the YooKassa token from `payment.succeeded` (never from the sync
`create_payment` response), and four IDOR-safe client endpoints (GET/DELETE/PATCH-autopay).
Autopay is **UI-only** (token + preference + ФЗ-376 consent stored; NO recurring charges —
`charge_expiring_autopay` cron defers to v2.3). Staff contract frozen; everything under
`require_client()`. PWA flag flips + CardSheet wiring are Phase 81, not this phase.

</domain>

<decisions>
## Implementation Decisions

### Data Model — `client_payment_methods` (migration 0052)
- Display columns: `last4` (text), `brand` (text), `expiry_month` (int), `expiry_year` (int) — render "•••• 4821" with optional expiry.
- Single active card per client: partial unique index on `client_id WHERE unlinked_at IS NULL`. Saving a new card upserts/replaces the active row.
- Token `yookassa_method_id` stored plaintext (consistent with existing YooKassa-id handling; no app-level crypto layer exists), **never** serialized to the client.
- Autopay/consent columns: `autopay_enabled` (bool, default false), `consent_recorded_at` (timestamptz, null), `unlinked_at` (timestamptz, null) for soft-delete.

### Endpoint Contracts & Behavior
- `GET /client/payment-method` → `200` with `null` body when no active card (per PAYM-02). `yookassa_method_id` never in response.
- `DELETE /client/payment-method` → `204 No Content`; soft-delete sets `unlinked_at` + `autopay_enabled=false`; deleting an absent/already-unlinked card is an idempotent `204` no-op; **no YooKassa API call** (no DELETE API exists).
- `PATCH /client/payment-method/autopay` enable requires consent in the same request → server stamps `consent_recorded_at=now()`. Enable with no active card OR no consent → `409`. Disable needs no consent and clears `autopay_enabled` without touching consent timestamp.
- ФЗ-376 consent payload: client sends `{enabled:true, consent_acknowledged:true}`; server records `consent_recorded_at`. The disclosure text (amount / periodicity / cancellation method) lives in the PWA UI (Phase 81), not stored server-side.
- All four endpoints IDOR-safe: `client_id` from principal only; 404-collapse on a non-owned `client_id`.

### Checkout Integration & Webhook Save-Step
- Add `save_payment_method: bool = false` to client checkout request bodies (membership + PT package); persist the intent as a column on the `online_payments` row (added in migration 0052) so the webhook can read it.
- Send `save_payment_method=true` to YooKassa `create_payment` so the saved token returns in `payment.succeeded`. Extend `YooKassaPaymentResult` + the webhook parse to surface `payment_method{id, last4, card_type, expiry}`.
- Token save = raw-SQL upsert inside `handle_payment_succeeded` step 8.5 (locked D-decision), zero new `ignore_imports`. `app/modules/payment_methods/` added to the `.importlinter` `modules-independent` contract.
- Fold the pre-existing `ruff I001` fix in `client_portal/router.py` into this phase (the file is touched anyway).

### Claude's Discretion
- Exact Pydantic schema field naming, repository function signatures, and test file organization, following existing `client_portal/` + `online_payments/` conventions.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/modules/client_portal/` (router/service/repository/schemas) — pattern for `require_client()` endpoints, raw-SQL reads (D-54-08), Protocol-slot writes. New endpoints land here (router) with the data module under `payment_methods/`.
- `app/api/v1/_internal/yookassa/handlers.py::handle_payment_succeeded` — the D-50-18 8-step atomic UoW; step 8.5 save-step hooks here.
- `app/integrations/yookassa/types.py::YooKassaPaymentResult` — needs a `payment_method` field added for token/card surfacing.
- `app/modules/online_payments/` — checkout `sell_membership`/`sell_pt_package` flow + `online_payments` table; checkout schemas live in `client_portal/schemas.py` + `online_payments/`.
- Migration sequence: latest is `0051_seed_fit15_promo.py`; this phase adds `0052`.

### Established Patterns
- IDOR-safe client endpoints: `client_id` from `require_client()` principal, 404-collapse on non-owned rows (D-20-IDOR).
- Webhook-locked state changes: only `payment.succeeded` mutates (D-06 / D-50-18).
- `.importlinter` `modules-independent` contract gates new modules; cross-module edges declared explicitly via `ignore_imports`.

### Integration Points
- Checkout endpoints: `client_checkout_membership` / `client_checkout_pt_package` in `client_portal/router.py`.
- Webhook intake: `app/api/v1/_internal/yookassa/router.py` → `handlers.py`.
- New router endpoints registered through `client_portal/router.py` (URL space) per the established `online_payments` precedent.

</code_context>

<specifics>
## Specific Ideas

- `GET` empty case must be `200`/`null` (PAYM-02), not 404 — explicit requirement.
- `DELETE` is a local soft-delete via `unlinked_at` (PAYM-03) — YooKassa has no DELETE API.
- Autopay enable is hard-gated on `consent_recorded_at` (ФЗ-376, PAYM-04); disable is ungated.
- PAN/CVV are NEVER stored — only token + display fields (PAYM-01).

</specifics>

<deferred>
## Deferred Ideas

- PWA `linkedCard` flag flip + `CardSheet` real-endpoint wiring + per-booking "Авто-оплата тренировок" toggle removal → Phase 81 (PAYM-05).
- `charge_expiring_autopay` ARQ cron (real recurring charges) → v2.3 (APAY-01..03).
- Zero-amount card-binding via `payment_method.active` webhook → rejected (save-during-payment is simpler and sufficient).

</deferred>
