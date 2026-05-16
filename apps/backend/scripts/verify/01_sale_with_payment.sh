#!/usr/bin/env bash
# Phase 36 scenario 01 — sale with payment (golden path)
# Roadmap SC #1 sub-scenario 01. Run AFTER seed_v1_4_verification_fixtures.
#
# Flow:
#   1. reception logs in.
#   2. POST /api/v1/memberships {clientId, planId} → 201 + .data.status="active"
#   3. GET  /api/v1/payments/by-membership/{id} → ≥1 row with subjectKind=membership
#      and amountKopecks == priceKopecksSnapshot from the sale.
#
# Hermetic re-run: clears any prior membership/payment for verify_sale@fixture.local
# via psql before starting (D-36-05 sanctions verification-time DB cleanup).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"

EVIDENCE=".planning/milestones/v1.4-verification-evidence/01_sale_with_payment.txt"
mkdir -p "$(dirname "$EVIDENCE")"
exec > >(tee "$EVIDENCE") 2>&1

echo "=== scenario 01_sale_with_payment ==="
echo "started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

# --- Cleanup prior runs (D-36-05) ---
CLIENT_EMAIL="verify_sale@fixture.local"
CLIENT_ID="$(psql "postgresql://app:app@localhost:5432/sportzal" -tA -c "SELECT id FROM clients WHERE email='${CLIENT_EMAIL}'")"
PLAN_ID="$(psql "postgresql://app:app@localhost:5432/sportzal" -tA -c "SELECT id FROM membership_plans WHERE name='Verify Standard 30d'")"
echo "+ cleanup prior verify_sale memberships/payments"
psql "postgresql://app:app@localhost:5432/sportzal" -c "
DELETE FROM membership_freeze_periods WHERE membership_id IN (SELECT id FROM memberships WHERE client_id='${CLIENT_ID}');
DELETE FROM payments WHERE subject_id IN (SELECT id FROM memberships WHERE client_id='${CLIENT_ID}');
DELETE FROM memberships WHERE client_id='${CLIENT_ID}';
"

echo "CLIENT_ID=$CLIENT_ID"
echo "PLAN_ID=$PLAN_ID"

# --- Login ---
echo "+ login_as reception"
login_as reception

# --- POST /api/v1/memberships ---
echo "+ mut POST /api/v1/memberships"
SALE_BODY="$(mktemp)"
mut POST /api/v1/memberships "{\"clientId\":\"$CLIENT_ID\",\"planId\":\"$PLAN_ID\"}" > "$SALE_BODY"
cat "$SALE_BODY"

STATUS_LINE="$(head -1 "$SALE_BODY" | awk '{print $2}')"
if [ "$STATUS_LINE" != "201" ]; then
  echo "result: FAIL — expected 201, got $STATUS_LINE"; exit 1
fi

BODY="$(awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}' "$SALE_BODY")"
MEMBERSHIP_ID="$(echo "$BODY" | jq -r '.data.id')"
MEMBERSHIP_STATUS="$(echo "$BODY" | jq -r '.data.status')"
MEMBERSHIP_PRICE="$(echo "$BODY" | jq -r '.data.priceKopecksSnapshot')"
END_DATE="$(echo "$BODY" | jq -r '.data.endDate')"

if [ "$MEMBERSHIP_STATUS" != "active" ]; then
  echo "result: FAIL — expected status=active, got $MEMBERSHIP_STATUS"; exit 1
fi
if [ "$END_DATE" = "null" ] || [ -z "$END_DATE" ]; then
  echo "result: FAIL — endDate is null"; exit 1
fi
if [ "$MEMBERSHIP_PRICE" -le 0 ]; then
  echo "result: FAIL — priceKopecksSnapshot not positive ($MEMBERSHIP_PRICE)"; exit 1
fi

echo "MEMBERSHIP_ID=$MEMBERSHIP_ID"
echo "MEMBERSHIP_STATUS=$MEMBERSHIP_STATUS"
echo "MEMBERSHIP_PRICE=$MEMBERSHIP_PRICE"
echo "END_DATE=$END_DATE"

# --- GET /api/v1/payments/by-membership/{id} ---
echo "+ get /api/v1/payments/by-membership/$MEMBERSHIP_ID"
PAY_BODY="$(mktemp)"
get "/api/v1/payments/by-membership/$MEMBERSHIP_ID" > "$PAY_BODY"
cat "$PAY_BODY"

PAY_STATUS="$(head -1 "$PAY_BODY" | awk '{print $2}')"
if [ "$PAY_STATUS" != "200" ]; then
  echo "result: FAIL — expected GET payments 200, got $PAY_STATUS"; exit 1
fi
PAY_JSON="$(awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}' "$PAY_BODY")"
PAY_COUNT="$(echo "$PAY_JSON" | jq -r '.data.total')"
PAY_AMOUNT="$(echo "$PAY_JSON" | jq -r '.data.items[0].amountKopecks // 0')"

if [ "$PAY_COUNT" -lt 1 ]; then
  echo "result: FAIL — no paired payment row found"; exit 1
fi
if [ "$PAY_AMOUNT" != "$MEMBERSHIP_PRICE" ]; then
  echo "result: FAIL — payment amount $PAY_AMOUNT != membership price $MEMBERSHIP_PRICE"; exit 1
fi

rm -f "$SALE_BODY" "$PAY_BODY"

echo "ended: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "result: PASS — membership $MEMBERSHIP_ID created (201, status=active, price=$MEMBERSHIP_PRICE); $PAY_COUNT payment row(s) paired at $PAY_AMOUNT kopecks"
