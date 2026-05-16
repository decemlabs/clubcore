#!/usr/bin/env bash
# Phase 36 scenario 03 — refund of FROZEN membership rejected with 409 must_unfreeze_first
# Negative case — exercises B-08 refund guard (apps/backend/app/modules/memberships/service.py:743).
#
# Flow:
#   1. reception logs in.
#   2. Sell membership for verify_smoke (fresh client allocation; cleaned up first via psql).
#   3. Freeze it → 200, status=frozen.
#   4. Attempt refund → MUST 409 + error.code=must_unfreeze_first.
#   5. Cleanup (idempotent for re-runs): unfreeze to leave a clean state.
#
# NOTE: this scenario uses verify_smoke client. Scenario 08 (cross-phase smoke) also
# uses verify_smoke; both run from a fresh state by deleting prior memberships first.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"

EVIDENCE=".planning/milestones/v1.4-verification-evidence/03_refund_frozen_409.txt"
mkdir -p "$(dirname "$EVIDENCE")"
exec > >(tee "$EVIDENCE") 2>&1

echo "=== scenario 03_refund_frozen_409 ==="
echo "started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

CLIENT_EMAIL="verify_smoke@fixture.local"
CLIENT_ID="$(psql "postgresql://app:app@localhost:5432/sportzal" -tA -c "SELECT id FROM clients WHERE email='${CLIENT_EMAIL}'")"
PLAN_ID="$(psql "postgresql://app:app@localhost:5432/sportzal" -tA -c "SELECT id FROM membership_plans WHERE name='Verify Long 90d'")"

echo "+ cleanup prior verify_smoke memberships/payments"
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
[ "$(head -1 "$SALE_BODY" | awk '{print $2}')" = "201" ] || { echo "result: FAIL — sale not 201"; exit 1; }
MEMBERSHIP_ID="$(awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}' "$SALE_BODY" | jq -r '.data.id')"
echo "MEMBERSHIP_ID=$MEMBERSHIP_ID"

echo "+ mut POST /api/v1/memberships/$MEMBERSHIP_ID/freeze"
FRZ_BODY="$(mktemp)"
mut POST "/api/v1/memberships/$MEMBERSHIP_ID/freeze" "{}" > "$FRZ_BODY"
cat "$FRZ_BODY"
[ "$(head -1 "$FRZ_BODY" | awk '{print $2}')" = "200" ] || { echo "result: FAIL — freeze not 200"; exit 1; }
FRZ_STATUS="$(awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}' "$FRZ_BODY" | jq -r '.data.status')"
[ "$FRZ_STATUS" = "frozen" ] || { echo "result: FAIL — expected frozen, got $FRZ_STATUS"; exit 1; }

echo "+ mut POST /api/v1/memberships/$MEMBERSHIP_ID/refund (must be rejected)"
REF_BODY="$(mktemp)"
mut POST "/api/v1/memberships/$MEMBERSHIP_ID/refund" "{\"reason\":\"should-be-rejected\"}" > "$REF_BODY"
cat "$REF_BODY"
REF_STATUS="$(head -1 "$REF_BODY" | awk '{print $2}')"
if [ "$REF_STATUS" != "409" ]; then echo "result: FAIL — expected 409, got $REF_STATUS"; exit 1; fi
REF_CODE="$(awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}' "$REF_BODY" | jq -r '.code // .error.code // .detail // "unknown"')"
if [ "$REF_CODE" != "must_unfreeze_first" ]; then
  echo "result: FAIL — expected code=must_unfreeze_first, got '$REF_CODE'"; exit 1
fi

# Cleanup — unfreeze so the membership is in a re-runnable state.
echo "+ cleanup: mut POST /api/v1/memberships/$MEMBERSHIP_ID/unfreeze"
UNF_BODY="$(mktemp)"
mut POST "/api/v1/memberships/$MEMBERSHIP_ID/unfreeze" "{}" > "$UNF_BODY"
cat "$UNF_BODY"

rm -f "$SALE_BODY" "$FRZ_BODY" "$REF_BODY" "$UNF_BODY"

echo "ended: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "result: PASS — frozen membership refund rejected with HTTP 409 + error.code=must_unfreeze_first (B-08)"
