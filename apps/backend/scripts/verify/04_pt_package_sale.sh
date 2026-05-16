#!/usr/bin/env bash
# Phase 36 scenario 04 — PT-package sale (Phase 33 surface)
# POST /api/v1/pt-packages requires {clientId, planId, amountKopecks} per D-33-09.
# amount_kopecks MUST match plan.price_kopecks (snapshot symmetry — 422 amount_mismatch).
#
# Flow:
#   1. reception logs in.
#   2. Sell PT-5 package for verify_pt → 201, sessionsRemaining=5, status=active.
#   3. GET /payments/by-client/{id} → entry with positive amount.
#
# Hermetic re-run: psql DELETE prior pt_packages for verify_pt (active partial unique).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"

EVIDENCE=".planning/milestones/v1.4-verification-evidence/04_pt_package_sale.txt"
mkdir -p "$(dirname "$EVIDENCE")"
exec > >(tee "$EVIDENCE") 2>&1

echo "=== scenario 04_pt_package_sale ==="
echo "started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

CLIENT_EMAIL="verify_pt@fixture.local"
CLIENT_ID="$(psql "postgresql://app:app@localhost:5432/sportzal" -tA -c "SELECT id FROM clients WHERE email='${CLIENT_EMAIL}'")"
PLAN_ID="$(psql "postgresql://app:app@localhost:5432/sportzal" -tA -c "SELECT id FROM pt_package_plans WHERE name='Verify PT-5'")"
PLAN_PRICE="$(psql "postgresql://app:app@localhost:5432/sportzal" -tA -c "SELECT price_kopecks FROM pt_package_plans WHERE name='Verify PT-5'")"

echo "+ cleanup prior verify_pt pt_packages/pt_sessions/payments"
psql "postgresql://app:app@localhost:5432/sportzal" -c "
DELETE FROM pt_sessions WHERE pt_package_id IN (SELECT id FROM pt_packages WHERE client_id='${CLIENT_ID}');
DELETE FROM payments WHERE subject_id IN (SELECT id FROM pt_packages WHERE client_id='${CLIENT_ID}');
DELETE FROM pt_packages WHERE client_id='${CLIENT_ID}';
"

echo "CLIENT_ID=$CLIENT_ID PLAN_ID=$PLAN_ID PLAN_PRICE=$PLAN_PRICE"

echo "+ login_as reception"
login_as reception

echo "+ mut POST /api/v1/pt-packages (sale)"
SALE_BODY="$(mktemp)"
mut POST /api/v1/pt-packages "{\"clientId\":\"$CLIENT_ID\",\"planId\":\"$PLAN_ID\",\"amountKopecks\":$PLAN_PRICE}" > "$SALE_BODY"
cat "$SALE_BODY"
[ "$(head -1 "$SALE_BODY" | awk '{print $2}')" = "201" ] || { echo "result: FAIL — sale expected 201"; exit 1; }
SALE_JSON="$(awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}' "$SALE_BODY")"
PKG_ID="$(echo "$SALE_JSON" | jq -r '.data.id')"
PKG_STATUS="$(echo "$SALE_JSON" | jq -r '.data.status')"
PKG_REMAINING="$(echo "$SALE_JSON" | jq -r '.data.sessionsRemaining')"
[ "$PKG_STATUS" = "active" ] || { echo "result: FAIL — expected active, got $PKG_STATUS"; exit 1; }
[ "$PKG_REMAINING" = "5" ] || { echo "result: FAIL — expected sessionsRemaining=5, got $PKG_REMAINING"; exit 1; }
echo "PKG_ID=$PKG_ID PKG_STATUS=$PKG_STATUS PKG_REMAINING=$PKG_REMAINING"

# NOTE: /api/v1/payments/by-client/{id} only returns membership payments + their
# refunds (apps/backend/app/modules/payments/repository.py:207-262). PT-package
# payment rows are not surfaced by that endpoint. Verify payment row directly via
# psql (subject_kind='pt_package' AND subject_id=$PKG_ID).
echo "+ psql verify payment row for pt_package $PKG_ID"
PT_PAYMENT_AMT="$(psql "postgresql://app:app@localhost:5432/sportzal" -tA -c "SELECT amount_kopecks FROM payments WHERE subject_kind='pt_package' AND subject_id='${PKG_ID}'")"
echo "PT_PAYMENT_AMT=$PT_PAYMENT_AMT"
if [ -z "$PT_PAYMENT_AMT" ]; then
  echo "result: FAIL — no payment row found for pt_package $PKG_ID"; exit 1
fi
if [ "$PT_PAYMENT_AMT" != "$PLAN_PRICE" ]; then
  echo "result: FAIL — PT-package payment amount $PT_PAYMENT_AMT != plan price $PLAN_PRICE"; exit 1
fi

rm -f "$SALE_BODY"

echo "ended: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "result: PASS — PT-package $PKG_ID created (201, status=active, sessionsRemaining=5); payment row recorded at $PT_PAYMENT_AMT kopecks"
