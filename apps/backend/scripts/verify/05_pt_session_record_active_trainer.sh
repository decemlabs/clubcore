#!/usr/bin/env bash
# Phase 36 scenario 05 — PT-session recording with active trainer (Phase 34 surface).
# POST /api/v1/pt-sessions takes {ptPackageId, trainerId, performedAt, notes?} per D-34-06.
#
# Flow:
#   1. reception logs in.
#   2. Sell fresh PT-10 package for verify_pt (cleanup first via psql) → 201, sessionsRemaining=10.
#   3. Resolve Trainer Alpha id (active).
#   4. POST /pt-sessions {ptPackageId, trainerId, performedAt=now} → 201, trainerNameSnapshot != "".
#   5. GET /pt-packages/{id} → sessionsRemaining=9 (decremented).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"

EVIDENCE=".planning/milestones/v1.4-verification-evidence/05_pt_session_record_active_trainer.txt"
mkdir -p "$(dirname "$EVIDENCE")"
exec > >(tee "$EVIDENCE") 2>&1

echo "=== scenario 05_pt_session_record_active_trainer ==="
echo "started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

CLIENT_EMAIL="verify_pt@fixture.local"
CLIENT_ID="$(psql "postgresql://app:app@localhost:5432/sportzal" -tA -c "SELECT id FROM clients WHERE email='${CLIENT_EMAIL}'")"
PLAN_ID="$(psql "postgresql://app:app@localhost:5432/sportzal" -tA -c "SELECT id FROM pt_package_plans WHERE name='Verify PT-10'")"
PLAN_PRICE="$(psql "postgresql://app:app@localhost:5432/sportzal" -tA -c "SELECT price_kopecks FROM pt_package_plans WHERE name='Verify PT-10'")"
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

# --- Sell fresh PT-10 package ---
echo "+ mut POST /api/v1/pt-packages (sale)"
SALE_BODY="$(mktemp)"
mut POST /api/v1/pt-packages "{\"clientId\":\"$CLIENT_ID\",\"planId\":\"$PLAN_ID\",\"amountKopecks\":$PLAN_PRICE}" > "$SALE_BODY"
cat "$SALE_BODY"
[ "$(head -1 "$SALE_BODY" | awk '{print $2}')" = "201" ] || { echo "result: FAIL — PT-package sale expected 201"; exit 1; }
PKG_ID="$(awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}' "$SALE_BODY" | jq -r '.data.id')"
echo "PKG_ID=$PKG_ID"

# --- Record PT-session ---
NOW_ISO="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "+ mut POST /api/v1/pt-sessions (record)"
REC_BODY="$(mktemp)"
mut POST /api/v1/pt-sessions "{\"ptPackageId\":\"$PKG_ID\",\"trainerId\":\"$TRAINER_ID\",\"performedAt\":\"$NOW_ISO\"}" > "$REC_BODY"
cat "$REC_BODY"
[ "$(head -1 "$REC_BODY" | awk '{print $2}')" = "201" ] || { echo "result: FAIL — pt-session record expected 201"; exit 1; }
REC_JSON="$(awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}' "$REC_BODY")"
SESSION_ID="$(echo "$REC_JSON" | jq -r '.data.id')"
TRAINER_NAME_SNAP="$(echo "$REC_JSON" | jq -r '.data.trainerNameSnapshot')"
[ -n "$TRAINER_NAME_SNAP" ] && [ "$TRAINER_NAME_SNAP" != "null" ] || { echo "result: FAIL — trainerNameSnapshot empty"; exit 1; }
echo "SESSION_ID=$SESSION_ID TRAINER_NAME_SNAPSHOT=$TRAINER_NAME_SNAP"

# --- Verify package decremented ---
echo "+ get /api/v1/pt-packages/$PKG_ID"
PKG_BODY="$(mktemp)"
get "/api/v1/pt-packages/$PKG_ID" > "$PKG_BODY"
cat "$PKG_BODY"
PKG_JSON="$(awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}' "$PKG_BODY")"
PKG_REMAINING="$(echo "$PKG_JSON" | jq -r '.data.sessionsRemaining')"
[ "$PKG_REMAINING" = "9" ] || { echo "result: FAIL — expected sessionsRemaining=9, got $PKG_REMAINING"; exit 1; }

rm -f "$SALE_BODY" "$REC_BODY" "$PKG_BODY"

echo "ended: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "result: PASS — PT-session $SESSION_ID recorded (201, trainerNameSnapshot=\"$TRAINER_NAME_SNAP\"); package sessionsRemaining decremented 10→9"
