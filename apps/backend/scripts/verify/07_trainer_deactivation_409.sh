#!/usr/bin/env bash
# Phase 36 scenario 07 — trainer deactivation + 422 trainer_inactive on PT-session attempt.
#
# IMPORTANT — code-vs-spec deviation:
# CONTEXT.md mentions "409 trainer_inactive" but the actual code in
# apps/backend/app/modules/pt_sessions/service.py:114-120 declares:
#   class TrainerInactiveError(ValidationAppError): status_code = 422
# So the verified behaviour is HTTP 422 + error.code='trainer_inactive', NOT 409.
# Per the scenario spec ("use the actual code from source if different"), we assert 422.
#
# Trainer used: Trainer Beta (keeping Trainer Alpha available for scenarios 05/06).
# Cleanup at script end: PATCH Trainer Beta back to is_active=true so re-runs work.
#
# Flow:
#   1. owner logs in → PATCH /trainers/{Beta-id} {isActive:false} → 200, isActive=false.
#   2. reception logs in → sell fresh PT-package for verify_pt.
#   3. POST /pt-sessions referencing inactive Trainer Beta → 422 trainer_inactive.
#   4. owner logs in → PATCH /trainers/{Beta-id} {isActive:true} → 200, isActive=true (cleanup).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"

EVIDENCE=".planning/milestones/v1.4-verification-evidence/07_trainer_deactivation_409.txt"
mkdir -p "$(dirname "$EVIDENCE")"
exec > >(tee "$EVIDENCE") 2>&1

echo "=== scenario 07_trainer_deactivation_409 ==="
echo "started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

CLIENT_EMAIL="verify_pt@fixture.local"
CLIENT_ID="$(psql "postgresql://app:app@localhost:5432/sportzal" -tA -c "SELECT id FROM clients WHERE email='${CLIENT_EMAIL}'")"
PLAN_ID="$(psql "postgresql://app:app@localhost:5432/sportzal" -tA -c "SELECT id FROM pt_package_plans WHERE name='Verify PT-5'")"
PLAN_PRICE="$(psql "postgresql://app:app@localhost:5432/sportzal" -tA -c "SELECT price_kopecks FROM pt_package_plans WHERE name='Verify PT-5'")"
TRAINER_BETA_ID="$(psql "postgresql://app:app@localhost:5432/sportzal" -tA -c "SELECT id FROM trainers WHERE full_name='Trainer Beta'")"

echo "+ cleanup prior verify_pt pt_packages/pt_sessions/payments"
psql "postgresql://app:app@localhost:5432/sportzal" -c "
DELETE FROM pt_sessions WHERE pt_package_id IN (SELECT id FROM pt_packages WHERE client_id='${CLIENT_ID}');
DELETE FROM payments WHERE subject_id IN (SELECT id FROM pt_packages WHERE client_id='${CLIENT_ID}');
DELETE FROM pt_packages WHERE client_id='${CLIENT_ID}';
"

echo "CLIENT_ID=$CLIENT_ID PLAN_ID=$PLAN_ID TRAINER_BETA_ID=$TRAINER_BETA_ID"

# --- (a) Deactivate Trainer Beta (owner) ---
echo "+ login_as owner (for PATCH /trainers)"
login_as owner

echo "+ mut PATCH /api/v1/trainers/$TRAINER_BETA_ID (isActive:false)"
DEACT_BODY="$(mktemp)"
mut PATCH "/api/v1/trainers/$TRAINER_BETA_ID" "{\"isActive\":false}" > "$DEACT_BODY"
cat "$DEACT_BODY"
[ "$(head -1 "$DEACT_BODY" | awk '{print $2}')" = "200" ] || { echo "result: FAIL — deactivate expected 200"; exit 1; }
DEACT_STATE="$(awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}' "$DEACT_BODY" | jq -r '.data.isActive')"
[ "$DEACT_STATE" = "false" ] || { echo "result: FAIL — expected isActive=false, got $DEACT_STATE"; exit 1; }

# --- (b) Reception sells PT-package ---
echo "+ login_as reception (for sale + record attempt)"
login_as reception

echo "+ mut POST /api/v1/pt-packages (sale)"
SALE_BODY="$(mktemp)"
mut POST /api/v1/pt-packages "{\"clientId\":\"$CLIENT_ID\",\"planId\":\"$PLAN_ID\",\"amountKopecks\":$PLAN_PRICE}" > "$SALE_BODY"
cat "$SALE_BODY"
[ "$(head -1 "$SALE_BODY" | awk '{print $2}')" = "201" ] || { echo "result: FAIL — PT-package sale expected 201"; exit 1; }
PKG_ID="$(awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}' "$SALE_BODY" | jq -r '.data.id')"

# --- (c) Attempt PT-session with deactivated trainer → 422 trainer_inactive ---
NOW_ISO="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "+ mut POST /api/v1/pt-sessions (must be rejected: inactive trainer)"
REC_BODY="$(mktemp)"
mut POST /api/v1/pt-sessions "{\"ptPackageId\":\"$PKG_ID\",\"trainerId\":\"$TRAINER_BETA_ID\",\"performedAt\":\"$NOW_ISO\"}" > "$REC_BODY"
cat "$REC_BODY"
RC="$(head -1 "$REC_BODY" | awk '{print $2}')"
if [ "$RC" != "422" ]; then echo "result: FAIL — expected 422 (per service.py TrainerInactiveError), got $RC"; exit 1; fi
ERR_CODE="$(awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}' "$REC_BODY" | jq -r '.code // .error.code // "unknown"')"
if [ "$ERR_CODE" != "trainer_inactive" ]; then echo "result: FAIL — expected trainer_inactive, got $ERR_CODE"; exit 1; fi

# --- (d) Cleanup: reactivate Trainer Beta ---
echo "+ login_as owner (for cleanup)"
login_as owner
echo "+ mut PATCH /api/v1/trainers/$TRAINER_BETA_ID (isActive:true — cleanup)"
REACT_BODY="$(mktemp)"
mut PATCH "/api/v1/trainers/$TRAINER_BETA_ID" "{\"isActive\":true}" > "$REACT_BODY"
cat "$REACT_BODY"
[ "$(head -1 "$REACT_BODY" | awk '{print $2}')" = "200" ] || { echo "result: FAIL — cleanup reactivate expected 200"; exit 1; }
REACT_STATE="$(awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}' "$REACT_BODY" | jq -r '.data.isActive')"
[ "$REACT_STATE" = "true" ] || { echo "result: FAIL — cleanup reactivate expected isActive=true, got $REACT_STATE"; exit 1; }

rm -f "$DEACT_BODY" "$SALE_BODY" "$REC_BODY" "$REACT_BODY"

echo "ended: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "result: PASS — Trainer Beta deactivated; PT-session attempt rejected with HTTP 422 + error.code=trainer_inactive; trainer reactivated as cleanup"
echo "NOTE: actual HTTP status is 422 (not 409 as CONTEXT.md preamble suggested) — matches apps/backend/app/modules/pt_sessions/service.py:114-120 TrainerInactiveError(ValidationAppError, status_code=422)"
