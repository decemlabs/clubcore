# v1.7 ЮKassa Sandbox Evidence — VER-03 Operator Capture Procedure

**Phase:** 53-milestone-verification
**Requirement:** VER-03 (closes D-04 / operator-pending classification per 53-CONTEXT.md line 34)
**Decision refs:** D-04, T-53-09
**Evidence path (locked):** `.planning/handoff/v1.7-yookassa-sandbox-evidence/`

---

## Purpose

This directory holds the operator-captured evidence from the live ЮKassa sandbox
sale + refund walkthrough. The walkthrough initiates a membership sale in the ЮKassa
sandbox, pays it, confirms the `payment.succeeded` callback lands on the local webhook
endpoint, verifies the resulting `fiscal_receipts` row, then repeats with a refund session.

**The AI agent ships this scaffolding. The operator runs the live sandbox session with
real ЮKassa sandbox credentials and saves the captured evidence here. This closes VER-03.**

This mirrors the Phase 52 CARRY-01/02 operator-pending pattern (D-04): technical
criteria (VER-01, VER-02, VER-04, VER-05) are verified automatically in-phase; VER-03
is marked operator-pending in 53-VERIFICATION.md and is NOT a blocking criterion for the
phase's technical close.

---

## Required Environment Variables

Set ALL of the following before running the sandbox walkthrough:

| Variable | Description | Required |
|----------|-------------|----------|
| `YOOKASSA_SHOP_ID` | ЮKassa sandbox shop ID (from yookassa.ru → Integration → Stores → Test store) | YES |
| `YOOKASSA_SECRET_KEY` | ЮKassa **sandbox** secret key (prefix `test_` on sandbox keys) | YES |
| `YOOKASSA_SANDBOX` | Must be set to `true` to enable sandbox bypass in `webhook_verifier.py` | YES |
| `YOOKASSA_RETURN_URL` | Redirect URL after payment confirmation in the ЮKassa widget (e.g. `http://localhost:8000/return`) | YES |

**Security (T-53-09):** Never commit real ЮKassa secret keys, live payment IDs, or
personal PII to this directory. All captured evidence files must use redacted values
(e.g. `test_****` for secret keys, `***` for account data). Real ЮKassa live (production)
credentials — those without `test_` prefix — must never appear here under any circumstances.

---

## Walkthrough — Sale + Webhook + Fiscal Receipt

Perform the following steps against a locally running `docker compose up` stack
(backend + Postgres 16 + Redis 7 + ARQ worker + Alembic migrations current):

### Step 1 — Configure environment

```bash
cd apps/backend
export YOOKASSA_SHOP_ID=<your-sandbox-shop-id>
export YOOKASSA_SECRET_KEY=test_<your-sandbox-secret-key>
export YOOKASSA_SANDBOX=true
export YOOKASSA_RETURN_URL=http://localhost:8000/return
docker compose up -d
docker compose exec migrate alembic upgrade head
```

### Step 2 — Initiate a membership sale

In the ЮKassa sandbox dashboard (https://yookassa.ru/my/):

1. Log in to the sandbox account associated with `YOOKASSA_SHOP_ID`.
2. Navigate to **Тест → Платёжная форма** (or use the backend `/api/v1/online-payments/memberships/{plan_id}/sell` endpoint via the admin-web UI or Postman).
3. Issue a membership `sell` request for a seeded client that has an `email` set
   (required by the ЮKassa API — use `verify_sale@fixture.local` from `seed_v1_4_verification_fixtures`).
4. Capture the `yookassaPaymentId` from the sell response body.

### Step 3 — Pay in the ЮKassa sandbox

1. Open the `confirmation_url` returned by the sell response in a browser.
2. Use the ЮKassa sandbox test card (Visa `4111 1111 1111 1111` / any future expiry / any CVC).
3. Complete the payment flow. The sandbox should redirect to `YOOKASSA_RETURN_URL`.

### Step 4 — Confirm the callback lands on the local webhook

The ЮKassa sandbox sends a `payment.succeeded` webhook to the URL configured in your
sandbox shop's webhook settings. Ensure the webhook URL is set to:

```
http://localhost:8000/api/v1/_internal/yookassa/webhook
```

(or the publicly accessible tunnel URL if using ngrok/localtunnel during the sandbox session.)

Confirm:
- HTTP response is `200 {"status": "ok"}`.
- Check the backend logs for `payment.succeeded` processing.

### Step 5 — Observe fiscal_receipts row

```bash
docker compose exec db psql -U app app -c \
  "SELECT id, kind, status, yookassa_receipt_id, succeeded_at \
   FROM fiscal_receipts \
   WHERE online_payment_id = (SELECT id FROM online_payments WHERE yookassa_payment_id = '<captured-id>' LIMIT 1);"
```

Expected: one row with `kind='payment'`, `status='sent'` (or `'pending'` if ARQ worker is still processing — wait up to 30 seconds and re-query).

---

## Walkthrough — Refund Session

### Step 6 — Initiate refund

```bash
# Find the membership_id activated in Step 4
docker compose exec db psql -U app app -c \
  "SELECT id FROM memberships WHERE client_id = (SELECT id FROM clients WHERE email = 'verify_sale@fixture.local') AND status = 'active' LIMIT 1;"

# Issue the refund
curl -s -X POST http://localhost:8000/api/v1/online-payments/memberships/<membership_id>/refund \
  -H "Cookie: $(cat /tmp/verify_owner_cookies.txt | grep sz_access | awk '{print "sz_access="$NF}')" \
  -H "Content-Type: application/json" | jq .
```

Expected: HTTP 202.

### Step 7 — Confirm refund.succeeded webhook

The ЮKassa sandbox will send a `refund.succeeded` callback. Confirm:
- Backend logs show `refund.succeeded` processing.
- `fiscal_receipts` gains a second row with `kind='refund'`, `status='sent'`.

---

## What to Capture

After a successful walkthrough (both sale and refund sessions complete):

1. **Screenshot or session log** of the ЮKassa sandbox payment confirmation screen showing the payment reaching `succeeded` status.
2. **Screenshot or CLI output** of the `fiscal_receipts` SELECT showing the `kind='payment'` + `status='sent'` row.
3. **Screenshot or CLI output** of the `fiscal_receipts` SELECT showing the `kind='refund'` + `status='sent'` row after the refund walkthrough.
4. **Backend log excerpt** (or `docker compose logs backend | grep yookassa`) confirming both webhook callbacks were received and processed.

All captures must be **redacted** — replace real ЮKassa payment IDs with `pay_***`,
fiscal receipt IDs with `rec_***`, and any personal account data with `***`.

---

## Evidence File Format

Save one YAML file per capture artifact. Recommended filenames:

### `sale_payment_confirmed.yaml`

```yaml
artifact: sale_payment_confirmed
yookassa_payment_id: "pay_***"          # redacted
fiscal_receipt_id: "rec_***"            # redacted
timestamp: ""                           # ISO-8601 UTC, e.g. 2026-05-23T18:00:00Z
fiscal_receipts_row: |
  # Paste verbatim psql SELECT output (redacted)
  # Expected: kind='payment', status='sent'
notes: ""
```

### `refund_confirmed.yaml`

```yaml
artifact: refund_confirmed
yookassa_refund_id: "ref_***"           # redacted
fiscal_receipt_id: "rec_***"            # redacted
timestamp: ""                           # ISO-8601 UTC, e.g. 2026-05-23T18:05:00Z
fiscal_receipts_row: |
  # Paste verbatim psql SELECT output (redacted)
  # Expected: kind='refund', status='sent'
notes: ""
```

### `webhook_log_excerpt.yaml`

```yaml
artifact: webhook_log_excerpt
timestamp: ""
payment_succeeded_log: |
  # Paste redacted backend log lines for payment.succeeded processing
refund_succeeded_log: |
  # Paste redacted backend log lines for refund.succeeded processing
notes: ""
```

---

## Acceptance Criteria for VER-03 Closure

DEFER-46-03 context: VER-03 is operator-pending per D-04 — NOT a blocking criterion for
the phase's technical close. VER-03 is closed when the operator deposits the following:

- [ ] ЮKassa sandbox sale initiated and payment completed (sandbox test card used)
- [ ] `payment.succeeded` webhook callback received and processed (HTTP 200 / `ok`)
- [ ] `fiscal_receipts` row with `kind='payment'` + `status='sent'` observed and captured
- [ ] ЮKassa sandbox refund initiated and `refund.succeeded` callback processed
- [ ] `fiscal_receipts` row with `kind='refund'` + `status='sent'` observed and captured
- [ ] At least one YAML evidence file saved to this directory with redacted values
- [ ] No real ЮKassa live keys, real payment IDs, or personal PII committed

Per D-46-22 (email parity): a partial sandbox result (e.g. fiscal receipt pending but
payment confirmed) is NOT a milestone-close blocker. Document the partial result in
the `notes:` field of the relevant YAML file.

---

## Scaffolding Attestation

The AI agent (Phase 53, Plan 53-04) attests:

- The local webhook simulation path (`/_internal/yookassa/webhook` with `YOOKASSA_SANDBOX=true`)
  is the approach used by the automated VER-01 runbook (`v1_7_runbook.sh`) — the VER-03
  sandbox walkthrough extends this with a real ЮKassa sandbox session and real callback.
- The `YOOKASSA_SANDBOX=true` env var enables `verify_yookassa_ip` sandbox bypass (D-02)
  so localhost webhook POSTs are treated as trusted; production deployments must NEVER use this flag.
- Evidence files are operator-deposited under the T-53-09 redaction contract.
- The live sandbox session and evidence capture are **operator deliverables** (D-04).
- This directory (`v1.7-yookassa-sandbox-evidence/`) is the locked evidence path per
  53-CONTEXT.md line 102.

*Scaffolding ready. Awaiting operator execution.*
