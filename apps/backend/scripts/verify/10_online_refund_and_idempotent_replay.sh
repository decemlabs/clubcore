#!/usr/bin/env bash
# Phase 53 scenario 10 — online refund (202) + idempotency-key replay (VER-01).
#
# Steps:
#   step1_setup:  Replay scenario 09 sell+webhook inline to establish a
#                 succeeded online_payment row (D-36-05: psql cleanup first).
#   step2_refund: mut POST /api/v1/online-payments/memberships/{membership_id}/refund
#                 → assert 202.
#   step3_refund_webhook: Raw curl POST refund.succeeded webhook → HTTP 200 + "ok".
#   step4_idem:   Idempotency-key replay (N1): capture $IDEM via uuidgen.
#                 First sell POST with explicit "-H 'Idempotency-Key: $IDEM'" via raw
#                 curl (NOT mut — which mints a fresh key each call). Record DB row
#                 count before.  Replay the SAME $IDEM on a second identical POST;
#                 assert 2xx with NO additional DB side-effect (row count unchanged).
#
# The server seam is _outer_idempotency_replay_or_run in
# app/modules/online_payments/router.py (lines 319-324).
#
# D-36-05 lineage: mid-scenario psql time-travel (cleanup) intentional.
# Postgres creds: app:app (NOT sportzal:sportzal).
# YOOKASSA_SANDBOX=true required (same as scenario 09).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"

EVIDENCE=".planning/milestones/v1.7-verification-evidence/10_online_refund_and_idempotent_replay.txt"
mkdir -p "$(dirname "$EVIDENCE")"
exec > >(tee "$EVIDENCE") 2>&1

echo "=== scenario 10_online_refund_and_idempotent_replay ==="
echo "started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

# --- Fixture resolution ---
CLIENT_EMAIL="verify_refund@fixture.local"
CLIENT_ID="$(psql "postgresql://app:app@localhost:5432/sportzal" -tA -c "SELECT id FROM clients WHERE email='${CLIENT_EMAIL}'")"
PLAN_ID="$(psql "postgresql://app:app@localhost:5432/sportzal" -tA -c "SELECT id FROM membership_plans WHERE name='Verify Standard 30d'")"

if [ -z "$CLIENT_ID" ]; then
  echo "result: FAIL — verify_refund@fixture.local not found; run seed_v1_4_verification_fixtures first"
  exit 1
fi
if [ -z "$PLAN_ID" ]; then
  echo "result: FAIL — 'Verify Standard 30d' plan not found; run seed_v1_4_verification_fixtures first"
  exit 1
fi
echo "CLIENT_ID=$CLIENT_ID  PLAN_ID=$PLAN_ID"

# --- Cleanup prior runs (D-36-05 time-travel intent: hermetic re-run) ---
echo "+ cleanup prior online_payments/fiscal_receipts/memberships for verify_refund"
psql "postgresql://app:app@localhost:5432/sportzal" -c "
DELETE FROM fiscal_receipts
  WHERE online_payment_id IN (
    SELECT id FROM online_payments WHERE client_id='${CLIENT_ID}'
  );
DELETE FROM payments
  WHERE subject_id IN (
    SELECT id FROM memberships WHERE client_id='${CLIENT_ID}'
  );
DELETE FROM memberships WHERE client_id='${CLIENT_ID}';
DELETE FROM online_payments WHERE client_id='${CLIENT_ID}';
"

# === step1: login + sell + payment.succeeded webhook ===
# Inline replica of scenario 09 flow to establish a succeeded online payment.
# Uses a fresh YK_PAYMENT_ID (uuidgen) per run so no Redis dedup collision.
echo "+ step1_setup: login_as owner + sell + payment.succeeded webhook"
login_as owner
echo "  step1a: login_as owner PASS"

B1S="$(mktemp)"
mut POST "/api/v1/online-payments/memberships/$PLAN_ID/sell" \
  "{\"clientId\":\"$CLIENT_ID\"}" > "$B1S"
STATUS1S="$(head -1 "$B1S" | awk '{print $2}')"
if [ "$STATUS1S" != "200" ] && [ "$STATUS1S" != "201" ]; then
  echo "result: FAIL — step1 sell expected 200/201, got $STATUS1S"; exit 1
fi
BODY1S="$(awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}' "$B1S")"
ONLINE_PAYMENT_ID="$(echo "$BODY1S" | jq -r '.data.id')"
YK_PAYMENT_ID="$(echo "$BODY1S" | jq -r '.data.yookassaPaymentId')"
MEMBERSHIP_ID="$(echo "$BODY1S" | jq -r '.data.membershipId // empty')"
rm -f "$B1S"
if [ -z "$ONLINE_PAYMENT_ID" ] || [ "$ONLINE_PAYMENT_ID" = "null" ]; then
  echo "result: FAIL — step1: could not extract .data.id from sell response"; exit 1
fi
if [ -z "$YK_PAYMENT_ID" ] || [ "$YK_PAYMENT_ID" = "null" ]; then
  echo "result: FAIL — step1: could not extract .data.yookassaPaymentId"; exit 1
fi
echo "  step1b: sell PASS — ONLINE_PAYMENT_ID=$ONLINE_PAYMENT_ID YK_PAYMENT_ID=$YK_PAYMENT_ID"

# Simulate payment.succeeded webhook (raw curl, trusted-IP, sandbox bypass)
B1W="$(mktemp)"
HTTP1W="$(curl -s -o "$B1W" -w '%{http_code}' -X POST \
  "$BASE_URL/api/v1/_internal/yookassa/webhook" \
  -H 'Content-Type: application/json' \
  -d "{\"event\":\"payment.succeeded\",\"object\":{\"id\":\"$YK_PAYMENT_ID\",\"status\":\"succeeded\",\"amount\":{\"value\":\"1000.00\",\"currency\":\"RUB\"}}}")"
WEBHOOK_BODY1W="$(cat "$B1W")"
rm -f "$B1W"
if [ "$HTTP1W" != "200" ] || [ "$WEBHOOK_BODY1W" != "ok" ]; then
  echo "result: FAIL — step1 payment.succeeded webhook: HTTP=$HTTP1W body=$WEBHOOK_BODY1W"
  echo "  Hint: ensure YOOKASSA_SANDBOX=true is set in the compose stack env"
  exit 1
fi
echo "  step1c: payment.succeeded webhook PASS — HTTP 200 ok"

# Resolve membership_id if not in sell response (may be in DB after webhook activation)
if [ -z "$MEMBERSHIP_ID" ] || [ "$MEMBERSHIP_ID" = "null" ]; then
  sleep 1
  MEMBERSHIP_ID="$(psql "postgresql://app:app@localhost:5432/sportzal" -tA -c \
    "SELECT id FROM memberships WHERE client_id='${CLIENT_ID}' AND status='active' ORDER BY created_at DESC LIMIT 1;")"
fi
if [ -z "$MEMBERSHIP_ID" ] || [ "$MEMBERSHIP_ID" = "null" ]; then
  echo "result: FAIL — step1: could not find active membership after webhook processing"; exit 1
fi
echo "  step1d: membership activated PASS — MEMBERSHIP_ID=$MEMBERSHIP_ID"
echo "step1_setup: PASS"

# === step2: initiate online refund → 202 ===
echo "+ step2_refund: mut POST /api/v1/online-payments/memberships/$MEMBERSHIP_ID/refund"
B2="$(mktemp)"
REFUND_IDEM="$(uuidgen)"
mut POST "/api/v1/online-payments/memberships/$MEMBERSHIP_ID/refund" \
  "{\"idempotencyKey\":\"$REFUND_IDEM\",\"reason\":\"scenario 10 refund test\"}" > "$B2"
cat "$B2"
STATUS2="$(head -1 "$B2" | awk '{print $2}')"
[ "$STATUS2" = "202" ] || { echo "result: FAIL — step2 refund expected 202, got $STATUS2"; exit 1; }
BODY2="$(awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}' "$B2")"
YK_REFUND_ID="$(echo "$BODY2" | jq -r '.data.yookassaRefundId // empty')"
rm -f "$B2"
echo "step2_refund: PASS — HTTP 202 YK_REFUND_ID=${YK_REFUND_ID:-<not-in-body>}"

# === step3: simulate refund.succeeded webhook ===
# Generate a fresh YK_REFUND_ID for the dedup key if the response didn't return one.
# For the webhook payload, use the yookassaRefundId from the refund initiation.
# If not available (ЮKassa may not return it synchronously in sandbox), use uuidgen.
if [ -z "$YK_REFUND_ID" ]; then
  YK_REFUND_ID="$(uuidgen)"
  echo "  Using generated YK_REFUND_ID=$YK_REFUND_ID for refund.succeeded simulation"
fi
echo "+ step3_refund_webhook: POST /_internal/yookassa/webhook (refund.succeeded)"
B3="$(mktemp)"
HTTP3="$(curl -s -o "$B3" -w '%{http_code}' -X POST \
  "$BASE_URL/api/v1/_internal/yookassa/webhook" \
  -H 'Content-Type: application/json' \
  -d "{\"event\":\"refund.succeeded\",\"object\":{\"id\":\"$YK_REFUND_ID\",\"status\":\"succeeded\",\"payment_id\":\"$YK_PAYMENT_ID\",\"amount\":{\"value\":\"1000.00\",\"currency\":\"RUB\"}}}")"
WEBHOOK_BODY3="$(cat "$B3")"
rm -f "$B3"
echo "  HTTP $HTTP3  body=$WEBHOOK_BODY3"
[ "$HTTP3" = "200" ] || { echo "result: FAIL — step3 refund.succeeded webhook expected HTTP 200, got $HTTP3"; exit 1; }
[ "$WEBHOOK_BODY3" = "ok" ] || { echo "result: FAIL — step3 refund.succeeded expected body=ok, got '$WEBHOOK_BODY3'"; exit 1; }
echo "step3_refund_webhook: PASS — HTTP 200 + body=ok"

# === step4: idempotency-key replay ===
# N1: Capture a single $IDEM, issue a sell POST with that key explicitly (raw curl,
# not mut — mut mints a fresh key each call), record DB row count before, replay
# SAME $IDEM on a second identical POST, assert 2xx + unchanged DB row count.
echo "+ step4_idem: idempotency-key replay test (N1)"

# Use a different client for the idem test so the refund cleanup above doesn't conflict.
# Reuse verify_sale client (has email, no active memberships after scenario 09 cleanup).
IDEM_CLIENT_ID="$(psql "postgresql://app:app@localhost:5432/sportzal" -tA -c \
  "SELECT id FROM clients WHERE email='verify_sale@fixture.local'")"
if [ -z "$IDEM_CLIENT_ID" ]; then
  echo "result: FAIL — step4: verify_sale@fixture.local not found for idempotency test"; exit 1
fi

# Clean up any leftover online_payments for verify_sale (from scenario 09 or prior run)
psql "postgresql://app:app@localhost:5432/sportzal" -c "
DELETE FROM fiscal_receipts
  WHERE online_payment_id IN (
    SELECT id FROM online_payments WHERE client_id='${IDEM_CLIENT_ID}'
  );
DELETE FROM payments
  WHERE subject_id IN (
    SELECT id FROM memberships WHERE client_id='${IDEM_CLIENT_ID}'
  );
DELETE FROM memberships WHERE client_id='${IDEM_CLIENT_ID}';
DELETE FROM online_payments WHERE client_id='${IDEM_CLIENT_ID}';
"

# Row count baseline BEFORE first sell
PRE_COUNT="$(psql "postgresql://app:app@localhost:5432/sportzal" -tA -c \
  "SELECT COUNT(*) FROM online_payments WHERE client_id='${IDEM_CLIENT_ID}'")"
echo "  pre-sell online_payments count=$PRE_COUNT"

# First sell with explicit Idempotency-Key (raw curl, NOT mut)
IDEM="$(uuidgen)"
echo "  IDEM=$IDEM"
BI1="$(mktemp)"
HTTP_I1="$(curl -s -o "$BI1" -w '%{http_code}' -X POST \
  "$BASE_URL/api/v1/online-payments/memberships/$PLAN_ID/sell" \
  -H 'Content-Type: application/json' \
  -H "Idempotency-Key: $IDEM" \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -b "$COOKIE_JAR" -c "$COOKIE_JAR" \
  -d "{\"clientId\":\"$IDEM_CLIENT_ID\"}")"
cat "$BI1"
rm -f "$BI1"
if [ "$HTTP_I1" != "200" ] && [ "$HTTP_I1" != "201" ]; then
  echo "result: FAIL — step4 first sell expected 200/201, got $HTTP_I1"; exit 1
fi
echo "  step4a: first sell PASS — HTTP $HTTP_I1"

# Row count after first sell
POST1_COUNT="$(psql "postgresql://app:app@localhost:5432/sportzal" -tA -c \
  "SELECT COUNT(*) FROM online_payments WHERE client_id='${IDEM_CLIENT_ID}'")"
echo "  after first sell online_payments count=$POST1_COUNT"
if [ "$POST1_COUNT" -le "$PRE_COUNT" ]; then
  echo "result: FAIL — step4: expected row count to increase after first sell, got $POST1_COUNT (was $PRE_COUNT)"
  exit 1
fi

# Replay: second POST with the SAME Idempotency-Key — must return idempotent 2xx
# with NO additional DB side-effect (row count unchanged).
BI2="$(mktemp)"
HTTP_I2="$(curl -s -o "$BI2" -w '%{http_code}' -X POST \
  "$BASE_URL/api/v1/online-payments/memberships/$PLAN_ID/sell" \
  -H 'Content-Type: application/json' \
  -H "Idempotency-Key: $IDEM" \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -b "$COOKIE_JAR" -c "$COOKIE_JAR" \
  -d "{\"clientId\":\"$IDEM_CLIENT_ID\"}")"
echo "  idempotent replay HTTP $HTTP_I2"
cat "$BI2"
rm -f "$BI2"

# Idempotent replay must be 2xx (200 or 201 — server returns the cached envelope).
case "$HTTP_I2" in
  200|201) ;;
  *) echo "result: FAIL — step4 idempotent replay expected 2xx, got $HTTP_I2"; exit 1 ;;
esac

POST2_COUNT="$(psql "postgresql://app:app@localhost:5432/sportzal" -tA -c \
  "SELECT COUNT(*) FROM online_payments WHERE client_id='${IDEM_CLIENT_ID}'")"
echo "  after replay online_payments count=$POST2_COUNT (was $POST1_COUNT)"
if [ "$POST2_COUNT" -ne "$POST1_COUNT" ]; then
  echo "result: FAIL — step4 idempotent replay created an additional DB row (count changed from $POST1_COUNT to $POST2_COUNT)"
  exit 1
fi
echo "step4_idem: PASS — HTTP $HTTP_I2 (2xx) + row count unchanged ($POST1_COUNT → $POST2_COUNT)"

echo ""
echo "ended: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "result: PASS — all 4 steps (setup, refund 202, refund webhook, idempotent replay) completed"
