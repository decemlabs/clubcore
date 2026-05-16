#!/usr/bin/env bash
# Phase 36 scenario 02 — refund of a fresh sale
# Provisions OWN membership inline for hermeticity (D-36-01 "cookie jar per scenario").
#
# Flow:
#   1. reception logs in.
#   2. POST /memberships for verify_refund client → 201
#   3. POST /memberships/{id}/refund {reason} → 200 + status=cancelled, cancellationReason=refunded
#   4. GET  /payments/by-membership/{id} → 2 rows (sale + refund)
#
# Hermetic re-run: psql DELETE prior memberships/payments for verify_refund client.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"

EVIDENCE=".planning/milestones/v1.4-verification-evidence/02_refund_of_fresh_sale.txt"
mkdir -p "$(dirname "$EVIDENCE")"
exec > >(tee "$EVIDENCE") 2>&1

echo "=== scenario 02_refund_of_fresh_sale ==="
echo "started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

CLIENT_EMAIL="verify_refund@fixture.local"
CLIENT_ID="$(psql "postgresql://app:app@localhost:5432/sportzal" -tA -c "SELECT id FROM clients WHERE email='${CLIENT_EMAIL}'")"
PLAN_ID="$(psql "postgresql://app:app@localhost:5432/sportzal" -tA -c "SELECT id FROM membership_plans WHERE name='Verify Standard 30d'")"

echo "+ cleanup prior verify_refund memberships/payments"
psql "postgresql://app:app@localhost:5432/sportzal" -c "
DELETE FROM membership_freeze_periods WHERE membership_id IN (SELECT id FROM memberships WHERE client_id='${CLIENT_ID}');
DELETE FROM payments WHERE subject_id IN (SELECT id FROM memberships WHERE client_id='${CLIENT_ID}');
DELETE FROM memberships WHERE client_id='${CLIENT_ID}';
"

echo "CLIENT_ID=$CLIENT_ID PLAN_ID=$PLAN_ID"

echo "+ login_as reception"
login_as reception

echo "+ mut POST /api/v1/memberships (sale)"
SALE_BODY="$(mktemp)"
mut POST /api/v1/memberships "{\"clientId\":\"$CLIENT_ID\",\"planId\":\"$PLAN_ID\"}" > "$SALE_BODY"
cat "$SALE_BODY"
SALE_STATUS="$(head -1 "$SALE_BODY" | awk '{print $2}')"
if [ "$SALE_STATUS" != "201" ]; then echo "result: FAIL — sale expected 201, got $SALE_STATUS"; exit 1; fi
MEMBERSHIP_ID="$(awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}' "$SALE_BODY" | jq -r '.data.id')"
echo "MEMBERSHIP_ID=$MEMBERSHIP_ID"

echo "+ mut POST /api/v1/memberships/$MEMBERSHIP_ID/refund"
REFUND_BODY="$(mktemp)"
mut POST "/api/v1/memberships/$MEMBERSHIP_ID/refund" "{\"reason\":\"verification test refund\"}" > "$REFUND_BODY"
cat "$REFUND_BODY"
REFUND_STATUS="$(head -1 "$REFUND_BODY" | awk '{print $2}')"
if [ "$REFUND_STATUS" != "200" ]; then echo "result: FAIL — refund expected 200, got $REFUND_STATUS"; exit 1; fi
REFUND_JSON="$(awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}' "$REFUND_BODY")"
REFUND_M_STATUS="$(echo "$REFUND_JSON" | jq -r '.data.status')"
REFUND_REASON="$(echo "$REFUND_JSON" | jq -r '.data.cancellationReason')"
if [ "$REFUND_M_STATUS" != "cancelled" ]; then echo "result: FAIL — expected cancelled, got $REFUND_M_STATUS"; exit 1; fi
if [ "$REFUND_REASON" != "refunded" ]; then echo "result: FAIL — expected cancellationReason=refunded, got $REFUND_REASON"; exit 1; fi

echo "+ get /api/v1/payments/by-membership/$MEMBERSHIP_ID"
PAY_BODY="$(mktemp)"
get "/api/v1/payments/by-membership/$MEMBERSHIP_ID" > "$PAY_BODY"
cat "$PAY_BODY"
PAY_JSON="$(awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}' "$PAY_BODY")"
PAY_COUNT="$(echo "$PAY_JSON" | jq -r '.data.total')"
if [ "$PAY_COUNT" -lt 2 ]; then echo "result: FAIL — expected ≥2 payment rows (sale+refund), got $PAY_COUNT"; exit 1; fi

# Confirm at least one row has refundOf != null (the refund row).
REFUND_ROW_COUNT="$(echo "$PAY_JSON" | jq '[.data.items[] | select(.refundOf != null)] | length')"
if [ "$REFUND_ROW_COUNT" -lt 1 ]; then echo "result: FAIL — no refund row (refundOf != null) found"; exit 1; fi

rm -f "$SALE_BODY" "$REFUND_BODY" "$PAY_BODY"

echo "ended: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "result: PASS — sale 201, refund 200 (status=cancelled, cancellationReason=refunded); $PAY_COUNT payment rows ($REFUND_ROW_COUNT refund row(s))"
