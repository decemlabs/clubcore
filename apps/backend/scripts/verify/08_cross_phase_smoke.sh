#!/usr/bin/env bash
# Phase 36 scenario 08 — cross-phase smoke (5-step) per D-36-03.
#
# Steps:
#   step1_sell:    POST /memberships for verify_smoke client → 201, status=active.
#   step2_freeze:  POST /memberships/{id}/freeze → 200, status=frozen.
#   step3_refund409: POST /memberships/{id}/refund → 409 must_unfreeze_first (B-08).
#   step4_unfreeze: POST /memberships/{id}/unfreeze → 200, status=active.
#   step5_refund:  POST /memberships/{id}/refund → 200, status=cancelled, paired refund row.
#
# All 5 steps in single evidence file; each step writes a step header for greppability.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"

EVIDENCE=".planning/milestones/v1.4-verification-evidence/08_cross_phase_smoke.txt"
mkdir -p "$(dirname "$EVIDENCE")"
exec > >(tee "$EVIDENCE") 2>&1

echo "=== scenario 08_cross_phase_smoke ==="
echo "started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

CLIENT_EMAIL="verify_smoke@fixture.local"
CLIENT_ID="$(psql "postgresql://app:app@localhost:5432/sportzal" -tA -c "SELECT id FROM clients WHERE email='${CLIENT_EMAIL}'")"
PLAN_ID="$(psql "postgresql://app:app@localhost:5432/sportzal" -tA -c "SELECT id FROM membership_plans WHERE name='Verify Standard 30d'")"

echo "+ cleanup prior verify_smoke memberships/payments"
psql "postgresql://app:app@localhost:5432/sportzal" -c "
DELETE FROM membership_freeze_periods WHERE membership_id IN (SELECT id FROM memberships WHERE client_id='${CLIENT_ID}');
DELETE FROM payments WHERE subject_id IN (SELECT id FROM memberships WHERE client_id='${CLIENT_ID}');
DELETE FROM memberships WHERE client_id='${CLIENT_ID}';
"

echo "CLIENT_ID=$CLIENT_ID PLAN_ID=$PLAN_ID"

echo "+ login_as reception"
login_as reception

# === step1: sell ===
echo "+ step1_sell: mut POST /api/v1/memberships"
B1="$(mktemp)"
mut POST /api/v1/memberships "{\"clientId\":\"$CLIENT_ID\",\"planId\":\"$PLAN_ID\"}" > "$B1"
cat "$B1"
[ "$(head -1 "$B1" | awk '{print $2}')" = "201" ] || { echo "result: FAIL — step1 sale expected 201"; exit 1; }
MEMBERSHIP_ID="$(awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}' "$B1" | jq -r '.data.id')"
S1="$(awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}' "$B1" | jq -r '.data.status')"
[ "$S1" = "active" ] || { echo "result: FAIL — step1 expected status=active, got $S1"; exit 1; }
echo "step1_sell: PASS — MEMBERSHIP_ID=$MEMBERSHIP_ID status=active"

# === step2: freeze ===
echo "+ step2_freeze: mut POST /api/v1/memberships/$MEMBERSHIP_ID/freeze"
B2="$(mktemp)"
mut POST "/api/v1/memberships/$MEMBERSHIP_ID/freeze" "{}" > "$B2"
cat "$B2"
[ "$(head -1 "$B2" | awk '{print $2}')" = "200" ] || { echo "result: FAIL — step2 freeze expected 200"; exit 1; }
S2="$(awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}' "$B2" | jq -r '.data.status')"
[ "$S2" = "frozen" ] || { echo "result: FAIL — step2 expected status=frozen, got $S2"; exit 1; }
echo "step2_freeze: PASS — status=frozen"

# === step3: refund-attempt → 409 ===
echo "+ step3_refund409: mut POST /api/v1/memberships/$MEMBERSHIP_ID/refund (must be rejected)"
B3="$(mktemp)"
mut POST "/api/v1/memberships/$MEMBERSHIP_ID/refund" "{\"reason\":\"step3 must reject\"}" > "$B3"
cat "$B3"
RC3="$(head -1 "$B3" | awk '{print $2}')"
[ "$RC3" = "409" ] || { echo "result: FAIL — step3 expected 409, got $RC3"; exit 1; }
EC3="$(awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}' "$B3" | jq -r '.code // .error.code // "unknown"')"
[ "$EC3" = "must_unfreeze_first" ] || { echo "result: FAIL — step3 expected code=must_unfreeze_first, got $EC3"; exit 1; }
echo "step3_refund409: PASS — HTTP 409 + error.code=must_unfreeze_first (B-08)"

# === step4: unfreeze ===
echo "+ step4_unfreeze: mut POST /api/v1/memberships/$MEMBERSHIP_ID/unfreeze"
B4="$(mktemp)"
mut POST "/api/v1/memberships/$MEMBERSHIP_ID/unfreeze" "{}" > "$B4"
cat "$B4"
[ "$(head -1 "$B4" | awk '{print $2}')" = "200" ] || { echo "result: FAIL — step4 unfreeze expected 200"; exit 1; }
S4="$(awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}' "$B4" | jq -r '.data.status')"
[ "$S4" = "active" ] || { echo "result: FAIL — step4 expected status=active, got $S4"; exit 1; }
echo "step4_unfreeze: PASS — status=active"

# === step5: refund (success) + paired payment row ===
echo "+ step5_refund: mut POST /api/v1/memberships/$MEMBERSHIP_ID/refund"
B5="$(mktemp)"
mut POST "/api/v1/memberships/$MEMBERSHIP_ID/refund" "{\"reason\":\"step5 refund after unfreeze\"}" > "$B5"
cat "$B5"
[ "$(head -1 "$B5" | awk '{print $2}')" = "200" ] || { echo "result: FAIL — step5 refund expected 200"; exit 1; }
S5="$(awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}' "$B5" | jq -r '.data.status')"
CR5="$(awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}' "$B5" | jq -r '.data.cancellationReason')"
[ "$S5" = "cancelled" ] || { echo "result: FAIL — step5 expected status=cancelled, got $S5"; exit 1; }
[ "$CR5" = "refunded" ] || { echo "result: FAIL — step5 expected cancellationReason=refunded, got $CR5"; exit 1; }

echo "+ step5_refund: verify paired payment rows via /api/v1/payments/by-membership"
B5P="$(mktemp)"
get "/api/v1/payments/by-membership/$MEMBERSHIP_ID" > "$B5P"
cat "$B5P"
P5J="$(awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}' "$B5P")"
P5T="$(echo "$P5J" | jq -r '.data.total')"
P5R="$(echo "$P5J" | jq '[.data.items[] | select(.refundOf != null)] | length')"
[ "$P5T" -ge 2 ] || { echo "result: FAIL — step5 expected ≥2 payment rows, got $P5T"; exit 1; }
[ "$P5R" -ge 1 ] || { echo "result: FAIL — step5 expected ≥1 refund row, got $P5R"; exit 1; }
echo "step5_refund: PASS — status=cancelled, cancellationReason=refunded, $P5T payment rows ($P5R refund row(s))"

rm -f "$B1" "$B2" "$B3" "$B4" "$B5" "$B5P"

echo "ended: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "result: PASS — all 5 steps (step1_sell, step2_freeze, step3_refund409, step4_unfreeze, step5_refund) completed end-to-end"
