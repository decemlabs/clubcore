---
phase: 79-payment-methods-foundation-card-on-file
reviewed: 2026-06-03T00:00:00Z
depth: standard
files_reviewed: 16
files_reviewed_list:
  - apps/backend/alembic/versions/0052_client_payment_methods.py
  - apps/backend/app/api/v1/_internal/yookassa/handlers.py
  - apps/backend/app/integrations/yookassa/client.py
  - apps/backend/app/integrations/yookassa/types.py
  - apps/backend/app/modules/client_portal/router.py
  - apps/backend/app/modules/client_portal/schemas.py
  - apps/backend/app/modules/client_portal/service.py
  - apps/backend/app/modules/online_payments/models.py
  - apps/backend/app/modules/online_payments/service.py
  - apps/backend/app/modules/payment_methods/models.py
  - apps/backend/app/modules/payment_methods/repository.py
  - apps/backend/app/modules/payment_methods/schemas.py
  - apps/backend/app/modules/payment_methods/service.py
  - apps/backend/tests/integration/client_portal/test_idor_sweep.py
  - apps/backend/tests/integration/client_portal/test_payment_method_endpoints.py
  - apps/backend/tests/integration/client_portal/test_payment_method_webhook_save.py
findings:
  critical: 1
  warning: 6
  info: 4
  total: 11
status: issues_found
---

# Phase 79: Code Review Report

**Reviewed:** 2026-06-03
**Depth:** standard
**Files Reviewed:** 16
**Status:** issues_found

## Summary

Phase 79 ships card-on-file: a `client_payment_methods` table, a `save_payment_method`
intent flag on `online_payments`, a webhook-only token-capture step (8.5), and three
client endpoints (GET/DELETE/PATCH autopay). The sensitive-data discipline is mostly
sound — `yookassa_method_id` is never serialized (repository SELECTs omit it, the
response schema omits it, tests assert its absence), PAN/CVV are never stored, and token
capture is webhook-only (the sync `create_payment` response never populates
`payment_method`). IDOR scoping uses the `require_client()` principal everywhere.

However the review surfaces one BLOCKER: the webhook step-8.5 upsert silently **wipes a
client's existing autopay consent** (`autopay_enabled=false`, `consent_recorded_at=NULL`)
whenever the same active card is re-saved by a subsequent payment — an unintended
authorization-state regression on a ФЗ-376-gated flag, with no test coverage and no
documented justification. Several WARNING-level issues concern a false `extra='forbid'`
docstring claim on the consent request schema, a misleading replay-idempotency test that
never exercises the upsert twice, and missing row-locking on the autopay update.

## Critical Issues

### CR-01: Webhook re-save silently resets autopay consent on the active card

**File:** `apps/backend/app/api/v1/_internal/yookassa/handlers.py:535-567`
**Issue:**
The step-8.5 upsert uses `ON CONFLICT (client_id) WHERE unlinked_at IS NULL DO UPDATE`
and unconditionally sets:

```
"  autopay_enabled = false, "
"  consent_recorded_at = NULL, "
```

The `ON CONFLICT` branch fires whenever the client already has an **active** card row
(the partial index only covers `unlinked_at IS NULL`). So any subsequent successful
payment with `save_payment_method=True` — including the same card — overwrites the live
row and **silently disables autopay and erases the recorded ФЗ-376 consent timestamp**.

Concrete sequence:
1. Client saves a card, later enables autopay (`PATCH /autopay` stamps `consent_recorded_at`).
2. Client buys another membership/PT-package with `savePaymentMethod=true` (the PWA sends
   this flag on every checkout per `ClientCheckoutRequest.save_payment_method`).
3. The succeeded webhook UPDATEs the active row → `autopay_enabled=false`,
   `consent_recorded_at=NULL`. The client's autopay is now off without any action or
   notification on their part.

This is a data-correctness/authorization-state defect on a legally-gated flag (consent).
Either it is a real bug (consent for an unchanged card should persist) or, if "new token
⇒ re-consent" is the intended policy, it must (a) only reset when the token actually
changes, and (b) be documented + tested. Currently it resets even when
`EXCLUDED.yookassa_method_id` equals the stored token, and no test asserts the post-resave
autopay/consent state for a client who had previously enabled it
(`test_webhook_save_replay_idempotent` seeds a fresh row whose autopay was already false,
so it cannot catch the regression).

**Fix:** Do not blindly reset consent/autopay on conflict. Only reset when the token
changes, and preserve consent otherwise:

```sql
ON CONFLICT (client_id) WHERE unlinked_at IS NULL
DO UPDATE SET
  yookassa_method_id = EXCLUDED.yookassa_method_id,
  last4 = EXCLUDED.last4,
  brand = EXCLUDED.brand,
  expiry_month = EXCLUDED.expiry_month,
  expiry_year = EXCLUDED.expiry_year,
  unlinked_at = NULL,
  autopay_enabled = CASE
    WHEN client_payment_methods.yookassa_method_id = EXCLUDED.yookassa_method_id
    THEN client_payment_methods.autopay_enabled ELSE false END,
  consent_recorded_at = CASE
    WHEN client_payment_methods.yookassa_method_id = EXCLUDED.yookassa_method_id
    THEN client_payment_methods.consent_recorded_at ELSE NULL END,
  updated_at = now()
```

Add an integration test that enables autopay, replays/re-pays with the same token, and
asserts `autopay_enabled`/`consent_recorded_at` are preserved; and a second test that a
new token resets them.

## Warnings

### WR-01: Consent request schema does not actually forbid extra keys (docstring is false)

**File:** `apps/backend/app/modules/payment_methods/schemas.py:32-41`
**Issue:** `ClientAutopayPatchRequest` is an **inbound request body** but inherits
`ResponseData`, whose base `ContractModel` is configured `extra="ignore"`
(`app/core/schemas.py:32`). The docstring claims `"extra='forbid' (ResponseData base)
rejects unknown keys"` — this is incorrect. Unknown keys on the consent-gated PATCH body
are silently ignored, not rejected. The codebase convention for strict inbound DTOs is
`BackendSchemaBase` (`extra="forbid"`, `app/core/schemas.py:52`). A client typo such as
`{"enabled": true, "consentAcknowleged": true}` (misspelled) would be silently accepted
with `consent_acknowledged` defaulting to `False`, yielding a 409 rather than the
client's intended enable — confusing, and the false docstring will mislead future
maintainers about the security posture of a ФЗ-376 endpoint.
**Fix:** Either change the base to `BackendSchemaBase` for inbound request schemas
(`ClientAutopayPatchRequest`, and ideally the other `client_portal` request DTOs that
share this issue), or correct the docstring to state that extras are ignored. Prefer
`BackendSchemaBase` for the consent body so the wire contract is strict.

### WR-02: Replay-idempotency test never exercises the step-8.5 upsert twice

**File:** `apps/backend/tests/integration/client_portal/test_payment_method_webhook_save.py:309-362`
**Issue:** `test_webhook_save_replay_idempotent` claims to prove "ON CONFLICT ... DO
UPDATE upsert ensures replay is idempotent." But on the second delivery,
`handle_payment_succeeded` re-fetches, sees the row is already `succeeded`, and
`_assert_can_transition(target='succeeded')` raises `InvalidTransitionError` — the
handler returns at `handlers.py:419` **before** reaching step 8.5
(`handlers.py:535`). The upsert therefore runs exactly once across both deliveries, so the
test's "exactly one active row" assertion passes trivially and does **not** validate the
`ON CONFLICT` path at all. The "upsert idempotency" claimed by T-79-09 is untested. The
test docstring (and the comment at `handlers.py:533`) further reference
`ON CONFLICT ON CONSTRAINT uq_client_payment_methods_client_id_alive`, but the index is a
`CREATE INDEX` not a constraint and the actual SQL correctly uses the inference-predicate
form — the docstrings are stale/misleading.
**Fix:** Add a test that drives the upsert path twice directly (e.g. two distinct
succeeded `online_payments` rows for the same client, both with `save=True`, each
delivering a `payment.succeeded` that passes the FSM guard) and assert exactly one active
row after both. Correct the stale `ON CONFLICT ON CONSTRAINT` references in the test and
handler comments.

### WR-03: `set_autopay` UPDATE is not row-locked; PATCH read-modify path can race

**File:** `apps/backend/app/modules/payment_methods/repository.py:82-112`
**Issue:** `patch_autopay` (`service.py:73-94`) does an unlocked
`fetch_active_payment_method` (plain SELECT), checks consent, then calls `set_autopay`
which issues a bare `UPDATE ... WHERE client_id=:client_id AND unlinked_at IS NULL`
without `FOR UPDATE`. `unlink_payment_method` does use `SELECT ... FOR UPDATE`. Two
concurrent client requests (e.g. enable-autopay + delete-card on the same session cookie)
can interleave: the enable can stamp `consent_recorded_at` on a row that the delete is
concurrently unlinking, or two enable/disable calls can clobber each other. The final
defensive re-fetch mitigates the no-op case but not the lost-update case on
`consent_recorded_at`.
**Fix:** Lock the active row inside the same transaction before reading/deciding — e.g.
have `patch_autopay` `SELECT ... FOR UPDATE` the active row (mirroring
`unlink_payment_method`) and perform the consent/autopay decision + UPDATE under that
lock.

### WR-04: `card_type`/`last4` empty-string fallbacks persist meaningless display data

**File:** `apps/backend/app/integrations/yookassa/client.py:364-370`
**Issue:** `get_payment` builds `YooKassaPaymentMethodInfo` with
`last4=str(card.get("last4", ""))` and `card_type=str(card.get("card_type", ""))`. If
ЮKassa returns a `bank_card` payment_method whose `card` object omits `last4`/`card_type`
(or `id`), the webhook upsert (`handlers.py:535` — guarded only on
`result.payment_method is not None`) will INSERT a `client_payment_methods` row with
`last4=""`, `brand=""`, or an empty `yookassa_method_id` token. An empty token is
unusable for any future autopay charge, and empty display fields render as blank cards in
the PWA. `last4`/`brand` are `NOT NULL` in the schema but empty string satisfies that.
**Fix:** Treat missing `id`/`last4`/`card_type` as "no saveable method" — return
`payment_method=None` (or skip the save in step 8.5) when any required field is empty, and
log a warning so the operator can reconcile. Do not persist a card row with an empty
token.

### WR-05: `expiry_year` is stored verbatim with no 2-digit normalization

**File:** `apps/backend/app/integrations/yookassa/client.py:359-363` and
`apps/backend/app/api/v1/_internal/yookassa/handlers.py:565`
**Issue:** `expiry_year` is parsed via `int(raw_year)` and stored as-is. ЮKassa documents
4-digit years, but the code makes no assertion/normalization. If a future provider/test
fixture supplies a 2-digit year (`"27"`), it is stored as `27`, and any downstream
expiry-comparison logic (autopay charge eligibility, planned in a later phase) would treat
the card as long expired. The display test uses 4-digit years so this is latent.
**Fix:** Either validate that `expiry_year` is a plausible 4-digit value (e.g.
`2000 <= year <= 2099`) and drop/normalize otherwise, or document the assumption with a
guard so a malformed value does not silently corrupt expiry semantics.

### WR-06: `save_payment_method` flows through the staff `create_payment` path with no card-save support

**File:** `apps/backend/app/modules/online_payments/service.py:343-353, 414`
**Issue:** `_sell_subject_core` accepts `save_payment_method` and threads it to both
`create_payment` and `insert_online_payment`. The staff wrappers (`sell_membership`,
`sell_pt_package`, lines 482-539) do not pass it (defaults `False`), which is correct
today. But the parameter is now part of the shared core with no guard that staff-initiated
payments cannot accidentally set it. More importantly, the QR replay branch and the
idempotency-collision single-retry branch (`service.py:369-392`) re-issue
`create_payment(..., save_payment_method=save_payment_method)` — fine — but the **replay**
branch (`service.py:262-295`) returns the existing row without re-checking that the
original row's `save_payment_method` matches the current request. A client who first
checks out with `save=false` and then replays the same per-day idempotency key with
`save=true` (membership path, where the key is server-derived per day) gets the original
`save=false` row back, so the card is silently NOT saved despite the second request asking
to save it. No error or signal is returned.
**Fix:** On the redirect-replay path, if the incoming `save_payment_method` differs from
`existing.save_payment_method`, either update the stored intent under lock or document
that the first same-day intent wins (and surface that to the PWA). Add a test for the
save=false-then-save=true same-day replay case.

## Info

### IN-01: Stale `ON CONFLICT ON CONSTRAINT` references in comments/docstrings

**File:** `apps/backend/app/api/v1/_internal/yookassa/handlers.py:544-547` and
`apps/backend/tests/integration/client_portal/test_payment_method_webhook_save.py:8, 316`
**Issue:** Comments/docstrings reference `ON CONFLICT ON CONSTRAINT
uq_client_payment_methods_client_id_alive`, but the index is a partial `CREATE INDEX`, not
a named constraint, and the code correctly uses `ON CONFLICT (client_id) WHERE ...`. The
prose contradicts the code.
**Fix:** Update the comments/docstrings to describe the inference-predicate form.

### IN-02: `_payment_methods_service` imported as a runtime module alias in client_portal.service

**File:** `apps/backend/app/modules/client_portal/service.py:36`
**Issue:** `import app.modules.payment_methods.service as _payment_methods_service` is a
cross-module runtime import; the file relies on an `.importlinter` ignore edge (noted in
the module docstring). The three pass-throughs (`get_payment_method`,
`unlink_payment_method`, `patch_autopay`, lines 945-980) add an indirection layer that
duplicates the payment_methods service signatures verbatim. Not a defect, but the
pass-throughs add maintenance surface with no transformation.
**Fix:** Consider wiring these through the existing composition-root Protocol-slot pattern
used elsewhere in this file (e.g. `invoke_client_checkout_core`) for consistency, or
document why a direct import is preferred here.

### IN-03: `expiry_month`/`expiry_year` nullability not validated against display contract

**File:** `apps/backend/app/modules/payment_methods/schemas.py:26-27`
**Issue:** The response allows `expiry_month`/`expiry_year` to be `None` (documented "may
be absent for some card types"), but the webhook always attempts to populate them from the
card object. There is no test for the absent-expiry display path. Low risk.
**Fix:** Add a fixture/test where the card omits expiry to confirm the GET response
renders `expiryMonth: null` cleanly.

### IN-04: Migration column `yookassa_method_id` lacks a same-token guard / length cap

**File:** `apps/backend/alembic/versions/0052_client_payment_methods.py:44-46`
**Issue:** `yookassa_method_id`, `last4`, and `brand` are `Text NOT NULL` with no
CHECK constraint (e.g. `last4` could be any length). Combined with WR-04, an empty or
malformed token can be persisted. Not exploitable on its own, but a CHECK
(`length(last4)=4`, `length(yookassa_method_id) > 0`) would harden the at-rest invariant.
**Fix:** Consider a CHECK constraint on `last4` length and non-empty token in a follow-up
migration.

---

_Reviewed: 2026-06-03_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
