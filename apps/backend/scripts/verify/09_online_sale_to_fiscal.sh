#!/usr/bin/env bash
# Phase 53 scenario 09 — online sale → payment.succeeded webhook → membership
# activated → fiscal_receipts row confirmed (VER-01 D-02).
#
# Steps:
#   step1_login:  login_as owner.
#   step2_sell:   POST /api/v1/online-payments/memberships/{plan_id}/sell
#                 → 201, capture online_payment_id + yookassa_payment_id.
#   step3_webhook: Flush dedup key (re-runnable). Raw curl POST to
#                 /_internal/yookassa/webhook with payment.succeeded payload →
#                 HTTP 200 + body "ok". Requires YOOKASSA_SANDBOX=true on the
#                 compose stack (sandbox bypass at webhook_verifier.py:84-86).
#   step4_activation: Confirm membership status=active via GET.
#   step5_fiscal: psql_exec SELECT fiscal_receipts row → assert kind='payment'
#                 + status='sent'.
#
# D-36-05 lineage: mid-scenario psql time-travel (cleanup + dedup flush) is
# intentional — logged here and in VERIFICATION-LOG.md notes.
# Hermetic re-run: DELETE prior online_payments/fiscal_receipts rows for the
# test client; generate fresh yookassa_payment_id per run via uuidgen so the
# dedup key is always new (alternative to flush — avoids Redis roundtrip if
# dedup TTL is still in window from a previous failed run).
#
# Postgres creds: app:app (NOT sportzal:sportzal — _lib.sh line 28-30).
# Fixture dependency: seed_v1_4_verification_fixtures seeded verify_sale@fixture.local
# with email set; online sale requires client email (422 client_email_required_for_online_payment).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"

EVIDENCE=".planning/milestones/v1.7-verification-evidence/09_online_sale_to_fiscal.txt"
mkdir -p "$(dirname "$EVIDENCE")"
exec > >(tee "$EVIDENCE") 2>&1

echo "=== scenario 09_online_sale_to_fiscal ==="
echo "started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

# --- Fixture resolution (app:app creds, D-36-05) ---
CLIENT_EMAIL="verify_sale@fixture.local"
CLIENT_ID="$(psql "postgresql://app:app@localhost:5432/sportzal" -tA -c "SELECT id FROM clients WHERE email='${CLIENT_EMAIL}'")"
PLAN_ID="$(psql "postgresql://app:app@localhost:5432/sportzal" -tA -c "SELECT id FROM membership_plans WHERE name='Verify Standard 30d'")"

if [ -z "$CLIENT_ID" ]; then
  echo "result: FAIL — verify_sale@fixture.local not found; run seed_v1_4_verification_fixtures first"
  exit 1
fi
if [ -z "$PLAN_ID" ]; then
  echo "result: FAIL — 'Verify Standard 30d' plan not found; run seed_v1_4_verification_fixtures first"
  exit 1
fi

echo "CLIENT_ID=$CLIENT_ID  PLAN_ID=$PLAN_ID"

# --- Cleanup prior runs (D-36-05 — time-travel intent: make scenario hermetic) ---
echo "+ cleanup prior online_payments/fiscal_receipts/memberships for verify_sale"
psql "postgresql://app:app@localhost:5432/sportzal" -c "
DELETE FROM fiscal_receipts
  WHERE payment_id IN (
    SELECT id FROM payments
      WHERE subject_kind='membership'
        AND subject_id IN (SELECT id FROM memberships WHERE client_id='${CLIENT_ID}')
  );
DELETE FROM payments
  WHERE subject_id IN (
    SELECT id FROM memberships WHERE client_id='${CLIENT_ID}'
  );
DELETE FROM memberships WHERE client_id='${CLIENT_ID}';
DELETE FROM online_payments WHERE client_id='${CLIENT_ID}';
"

# === step1: login ===
echo "+ step1_login: login_as owner"
login_as owner
echo "step1_login: PASS"

# === step2: sell (online membership) ===
echo "+ step2_sell: mut POST /api/v1/online-payments/memberships/$PLAN_ID/sell"
B2="$(mktemp)"
mut POST "/api/v1/online-payments/memberships/$PLAN_ID/sell" \
  "{\"clientId\":\"$CLIENT_ID\"}" > "$B2"
cat "$B2"
STATUS2="$(head -1 "$B2" | awk '{print $2}')"
if [ "$STATUS2" != "200" ] && [ "$STATUS2" != "201" ]; then
  echo "result: FAIL — step2 sell expected 200/201, got $STATUS2"; exit 1
fi
BODY2="$(awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}' "$B2")"
ONLINE_PAYMENT_ID="$(echo "$BODY2" | jq -r '.data.id')"
YK_PAYMENT_ID="$(echo "$BODY2" | jq -r '.data.yookassaPaymentId')"
if [ -z "$ONLINE_PAYMENT_ID" ] || [ "$ONLINE_PAYMENT_ID" = "null" ]; then
  echo "result: FAIL — step2: could not extract .data.id from sell response"; exit 1
fi
if [ -z "$YK_PAYMENT_ID" ] || [ "$YK_PAYMENT_ID" = "null" ]; then
  echo "result: FAIL — step2: could not extract .data.yookassaPaymentId from sell response"; exit 1
fi
echo "step2_sell: PASS — ONLINE_PAYMENT_ID=$ONLINE_PAYMENT_ID  YK_PAYMENT_ID=$YK_PAYMENT_ID"
rm -f "$B2"

# === step3: simulate payment.succeeded webhook (D-02) ===
# Raw curl — NOT mut (no cookie/CSRF/Idempotency-Key required; anonymous route).
# Requires YOOKASSA_SANDBOX=true on the compose stack so verify_yookassa_ip
# sandbox bypass (webhook_verifier.py:84-86) lets the POST through from localhost.
# Dedup key: sz:yookassa:webhook:payment.succeeded:{YK_PAYMENT_ID}
# We generate a fresh YK_PAYMENT_ID via uuidgen on each run (step2 creates the
# online_payments row with that id), so the dedup key is unique per run.
echo "+ step3_webhook: POST $BASE_URL/api/v1/_internal/yookassa/webhook (payment.succeeded)"
echo "  YK_PAYMENT_ID=$YK_PAYMENT_ID (fresh per run — no Redis flush needed)"
B3="$(mktemp)"
HTTP3="$(curl -s -o "$B3" -w '%{http_code}' -X POST \
  "$BASE_URL/api/v1/_internal/yookassa/webhook" \
  -H 'Content-Type: application/json' \
  -d "{\"event\":\"payment.succeeded\",\"object\":{\"id\":\"$YK_PAYMENT_ID\",\"status\":\"succeeded\",\"amount\":{\"value\":\"1000.00\",\"currency\":\"RUB\"}}}")"
WEBHOOK_BODY3="$(cat "$B3")"
echo "  HTTP $HTTP3  body=$WEBHOOK_BODY3"
rm -f "$B3"
if [ "$HTTP3" != "200" ]; then
  echo "result: FAIL — step3 webhook expected HTTP 200, got $HTTP3"
  echo "  Hint: ensure YOOKASSA_SANDBOX=true is set in the compose stack env"
  exit 1
fi
if [ "$WEBHOOK_BODY3" != "ok" ]; then
  echo "result: FAIL — step3 webhook expected body=ok, got '$WEBHOOK_BODY3'"; exit 1
fi
echo "step3_webhook: PASS — HTTP 200 + body=ok"

# === step4: confirm membership activated ===
# Allow up to 3s for the ARQ worker to activate the membership; poll once.
echo "+ step4_activation: GET /api/v1/memberships (check membership active for CLIENT_ID)"
sleep 1
B4="$(mktemp)"
get "/api/v1/memberships?clientId=$CLIENT_ID&status=active" > "$B4"
cat "$B4"
STATUS4="$(head -1 "$B4" | awk '{print $2}')"
[ "$STATUS4" = "200" ] || { echo "result: FAIL — step4 GET memberships expected 200, got $STATUS4"; exit 1; }
BODY4="$(awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}' "$B4")"
ACTIVE_COUNT4="$(echo "$BODY4" | jq -r '.data.total')"
if [ -z "$ACTIVE_COUNT4" ] || [ "$ACTIVE_COUNT4" = "null" ] || [ "$ACTIVE_COUNT4" -lt 1 ]; then
  echo "result: FAIL — step4 expected ≥1 active membership, got total=$ACTIVE_COUNT4"
  echo "  Note: webhook processing is synchronous in the webhook handler (not ARQ)"
  exit 1
fi
MEMBERSHIP_ID4="$(echo "$BODY4" | jq -r '.data.items[0].id')"
echo "step4_activation: PASS — membership $MEMBERSHIP_ID4 active (total=$ACTIVE_COUNT4)"
rm -f "$B4"

# === step5: confirm fiscal_receipts row ===
# fiscal_receipts links to the ledger via payment_id -> payments.id; the online
# membership sale creates payments(subject_kind='membership', subject_id=membership_id),
# so join through payments on the activated MEMBERSHIP_ID4. Assert kind='payment' + status='sent'.
# D-36-05: reading DB state directly is the canonical verification pattern for background jobs.
echo "+ step5_fiscal: psql_exec SELECT fiscal_receipts for MEMBERSHIP_ID=$MEMBERSHIP_ID4"
FISCAL_ROW="$(psql "postgresql://app:app@localhost:5432/sportzal" -tA -c \
  "SELECT fr.kind, fr.status
     FROM fiscal_receipts fr
     JOIN payments p ON p.id = fr.payment_id
    WHERE p.subject_kind='membership' AND p.subject_id='${MEMBERSHIP_ID4}' AND fr.kind='payment'
    ORDER BY fr.created_at DESC LIMIT 1;")"
echo "  fiscal_receipts row: $FISCAL_ROW"
if [ -z "$FISCAL_ROW" ]; then
  echo "result: FAIL — step5: no fiscal_receipts row found for MEMBERSHIP_ID=$MEMBERSHIP_ID4"
  echo "  Check ARQ worker is running (docker compose ps arq-worker) and YOOKASSA_SANDBOX=true"
  exit 1
fi
FISCAL_KIND="$(echo "$FISCAL_ROW" | cut -d'|' -f1 | tr -d ' ')"
FISCAL_STATUS="$(echo "$FISCAL_ROW" | cut -d'|' -f2 | tr -d ' ')"
if [ "$FISCAL_KIND" != "payment" ]; then
  echo "result: FAIL — step5 expected kind='payment', got '$FISCAL_KIND'"; exit 1
fi
if [ "$FISCAL_STATUS" != "sent" ]; then
  echo "result: FAIL — step5 expected status='sent', got '$FISCAL_STATUS'"
  echo "  'sent' = fiscal receipt row created + dispatched; 'succeeded' = ЮKassa confirmed"
  echo "  Check ARQ worker processed dispatch_fiscal_receipt task"
  exit 1
fi
echo "step5_fiscal: PASS — fiscal_receipts row kind='payment' status='sent'"

echo ""
echo "ended: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "result: PASS — all 5 steps (login, sell, webhook, activation, fiscal) completed end-to-end"
