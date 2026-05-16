#!/usr/bin/env bash
# Phase 36 scenario 06 — PT-package exhaustion (5 successful records + 6th rejected with 409 pt_package_exhausted)
# Phase 33 FSM: status='active' → 'exhausted' when sessions_remaining hits 0 (D-33-15).
# Error code from apps/backend/app/modules/pt_sessions/service.py:230 → PtPackageExhaustedError("pt_package_exhausted").
#
# Flow:
#   1. reception logs in.
#   2. Sell fresh PT-5 package for verify_pt (cleanup first) → 201, sessionsRemaining=5.
#   3. Loop 5x: POST /pt-sessions → 201 each.
#   4. GET /pt-packages/{id} → status='exhausted', sessionsRemaining=0.
#   5. 6th POST /pt-sessions → 409, error.code='pt_package_exhausted'.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"

EVIDENCE=".planning/milestones/v1.4-verification-evidence/06_pt_package_exhaustion.txt"
mkdir -p "$(dirname "$EVIDENCE")"
exec > >(tee "$EVIDENCE") 2>&1

echo "=== scenario 06_pt_package_exhaustion ==="
echo "started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

CLIENT_EMAIL="verify_pt@fixture.local"
CLIENT_ID="$(psql "postgresql://app:app@localhost:5432/sportzal" -tA -c "SELECT id FROM clients WHERE email='${CLIENT_EMAIL}'")"
PLAN_ID="$(psql "postgresql://app:app@localhost:5432/sportzal" -tA -c "SELECT id FROM pt_package_plans WHERE name='Verify PT-5'")"
PLAN_PRICE="$(psql "postgresql://app:app@localhost:5432/sportzal" -tA -c "SELECT price_kopecks FROM pt_package_plans WHERE name='Verify PT-5'")"
TRAINER_ID="$(psql "postgresql://app:app@localhost:5432/sportzal" -tA -c "SELECT id FROM trainers WHERE full_name='Trainer Alpha'")"

echo "+ cleanup prior verify_pt pt_packages/pt_sessions/payments"
psql "postgresql://app:app@localhost:5432/sportzal" -c "
DELETE FROM pt_sessions WHERE pt_package_id IN (SELECT id FROM pt_packages WHERE client_id='${CLIENT_ID}');
DELETE FROM payments WHERE subject_id IN (SELECT id FROM pt_packages WHERE client_id='${CLIENT_ID}');
DELETE FROM pt_packages WHERE client_id='${CLIENT_ID}';
"

echo "CLIENT_ID=$CLIENT_ID PLAN_ID=$PLAN_ID PLAN_PRICE=$PLAN_PRICE TRAINER_ID=$TRAINER_ID"

echo "+ login_as reception"
login_as reception

# --- Sell fresh PT-5 package ---
echo "+ mut POST /api/v1/pt-packages (sale)"
SALE_BODY="$(mktemp)"
mut POST /api/v1/pt-packages "{\"clientId\":\"$CLIENT_ID\",\"planId\":\"$PLAN_ID\",\"amountKopecks\":$PLAN_PRICE}" > "$SALE_BODY"
cat "$SALE_BODY"
[ "$(head -1 "$SALE_BODY" | awk '{print $2}')" = "201" ] || { echo "result: FAIL — PT-package sale expected 201"; exit 1; }
PKG_ID="$(awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}' "$SALE_BODY" | jq -r '.data.id')"
echo "PKG_ID=$PKG_ID"

# --- Record 5 sessions (decrement to 0) ---
for i in 1 2 3 4 5; do
  NOW_ISO="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "+ mut POST /api/v1/pt-sessions (record #$i)"
  REC_BODY="$(mktemp)"
  mut POST /api/v1/pt-sessions "{\"ptPackageId\":\"$PKG_ID\",\"trainerId\":\"$TRAINER_ID\",\"performedAt\":\"$NOW_ISO\"}" > "$REC_BODY"
  cat "$REC_BODY"
  RC="$(head -1 "$REC_BODY" | awk '{print $2}')"
  [ "$RC" = "201" ] || { echo "result: FAIL — pt-session #$i expected 201, got $RC"; exit 1; }
  rm -f "$REC_BODY"
  sleep 1   # ensure distinct performedAt timestamps if backend dedups
done

# --- Verify exhausted state ---
echo "+ get /api/v1/pt-packages/$PKG_ID"
PKG_BODY="$(mktemp)"
get "/api/v1/pt-packages/$PKG_ID" > "$PKG_BODY"
cat "$PKG_BODY"
PKG_JSON="$(awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}' "$PKG_BODY")"
PKG_STATUS="$(echo "$PKG_JSON" | jq -r '.data.status')"
PKG_REMAINING="$(echo "$PKG_JSON" | jq -r '.data.sessionsRemaining')"
[ "$PKG_STATUS" = "exhausted" ] || { echo "result: FAIL — expected status=exhausted, got $PKG_STATUS"; exit 1; }
[ "$PKG_REMAINING" = "0" ] || { echo "result: FAIL — expected sessionsRemaining=0, got $PKG_REMAINING"; exit 1; }

# --- 6th attempt must fail ---
NOW_ISO="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "+ mut POST /api/v1/pt-sessions (6th attempt — must be rejected)"
REC_BODY="$(mktemp)"
mut POST /api/v1/pt-sessions "{\"ptPackageId\":\"$PKG_ID\",\"trainerId\":\"$TRAINER_ID\",\"performedAt\":\"$NOW_ISO\"}" > "$REC_BODY"
cat "$REC_BODY"
RC="$(head -1 "$REC_BODY" | awk '{print $2}')"
if [ "$RC" != "409" ]; then echo "result: FAIL — 6th expected 409, got $RC"; exit 1; fi
ERR_CODE="$(awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}' "$REC_BODY" | jq -r '.code // .error.code // "unknown"')"
# Per apps/backend/app/modules/pt_sessions/service.py:230: code is `pt_package_exhausted`.
# Status may also surface as `pt_package_not_active` (409) when status already exhausted (line 102).
if [ "$ERR_CODE" != "pt_package_exhausted" ] && [ "$ERR_CODE" != "pt_package_not_active" ]; then
  echo "result: FAIL — expected code=pt_package_exhausted (or pt_package_not_active), got '$ERR_CODE'"; exit 1
fi

rm -f "$SALE_BODY" "$PKG_BODY" "$REC_BODY"

echo "ended: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "result: PASS — 5 sessions recorded; package exhausted (status=exhausted, sessionsRemaining=0); 6th attempt rejected with 409 error.code=$ERR_CODE"
