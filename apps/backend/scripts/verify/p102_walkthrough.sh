#!/usr/bin/env bash
# P102 Live-HTTP Walkthrough — Bookings + Payroll lifecycle against a running uvicorn.
#
# Purpose: Captured runnable live-HTTP command sequence that closes the v3.0
# data-setup-blocked root cause (Phase 110 criterion #4). Run this after seeding:
#
#   cd apps/backend
#   uv run python -m scripts.seed_demo_data
#   uv run python -m scripts.seed_p102_walkthrough   # prints entity IDs
#   uvicorn app.main:app --host 0.0.0.0 --port 8000 &
#   bash scripts/verify/p102_walkthrough.sh
#
# Required env vars (export before running):
#   SEED_OWNER_EMAIL       — owner login email (same as used by seed_demo_data)
#   SEED_OWNER_PASSWORD    — owner password (>= 12 chars)
#   TRAINER_ID             — trainer_id printed by seed_p102_walkthrough
#   SLOT_ID                — slot_id printed by seed_p102_walkthrough
#   CLIENT_ID              — client_id printed by seed_p102_walkthrough
#   PT_PACKAGE_ID          — pt_package_id printed by seed_p102_walkthrough
#   ACCRUAL_PERIOD_START   — payroll period start (default: 2026-04-01)
#   ACCRUAL_PERIOD_END     — payroll period end   (default: 2026-04-30)
#
# Cookie discipline (v3.0 / correct names — NOT the old sz_* scheme):
#   cc_access     — HTTP-only access JWT (auth, set by /api/v1/auth/login)
#   cc_refresh    — HTTP-only refresh token (set by /api/v1/auth/login)
#   clubcore_csrf — non-HttpOnly CSRF token; value used as X-CSRF-Token header
#
# Idempotency-Key is required on all mutating POST requests that create
# bookings or pt-sessions (deduplication guard at DB level via the partial
# UNIQUE indexes).
#
# NOTE: The authoritative repeatable verification is the integration test suite
# (Plans 02 and 03 in Phase 110). This script is the captured live-HTTP
# confirmation. If uvicorn cannot be started headlessly during execution, the
# script is captured and the literal-HTTP confirmation is deferred as a UAT
# item (per 110-CONTEXT.md deferred-ideas).

set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
PERIOD_START="${ACCRUAL_PERIOD_START:-2026-04-01}"
PERIOD_END="${ACCRUAL_PERIOD_END:-2026-04-30}"

# --- Validate required env vars -------------------------------------------
: "${SEED_OWNER_EMAIL:?SEED_OWNER_EMAIL must be exported}"
: "${SEED_OWNER_PASSWORD:?SEED_OWNER_PASSWORD must be exported}"
: "${TRAINER_ID:?TRAINER_ID must be exported (copy from seed_p102_walkthrough output)}"
: "${SLOT_ID:?SLOT_ID must be exported (copy from seed_p102_walkthrough output)}"
: "${CLIENT_ID:?CLIENT_ID must be exported (copy from seed_p102_walkthrough output)}"
: "${PT_PACKAGE_ID:?PT_PACKAGE_ID must be exported (copy from seed_p102_walkthrough output)}"

COOKIE_JAR="$(mktemp -t p102-verify-XXXX.cookies)"
trap 'rm -f "$COOKIE_JAR"' EXIT

CSRF_TOKEN=""
BOOKING_ID=""
ACCRUAL_ID=""

echo "=== P102 Walkthrough — $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "BASE_URL: $BASE_URL"
echo "Period:   $PERIOD_START .. $PERIOD_END"
echo ""

# --------------------------------------------------------------------------
# Step 1: dev-login
# POST /api/v1/auth/login — CSRF-exempt endpoint.
# Sets cc_access + cc_refresh + clubcore_csrf cookies in the jar.
# Extract the clubcore_csrf cookie value for use as X-CSRF-Token header.
# --------------------------------------------------------------------------
echo "--- Step 1: dev-login ---"
# Build JSON via Python so special characters in email/password are correctly
# escaped (CR-02: raw shell interpolation produces malformed JSON on " or \).
LOGIN_BODY=$(python3 -c "
import json, os
print(json.dumps({
    'email': os.environ['SEED_OWNER_EMAIL'],
    'password': os.environ['SEED_OWNER_PASSWORD'],
}))")
LOGIN_RESPONSE=$(curl -si -X POST "$BASE_URL/api/v1/auth/login" \
  -H 'Content-Type: application/json' \
  -c "$COOKIE_JAR" \
  -d "$LOGIN_BODY")

LOGIN_STATUS=$(echo "$LOGIN_RESPONSE" | head -1 | awk '{print $2}')
# Extract clubcore_csrf from Netscape cookie-jar file (column 6 = name, column 7 = value)
CSRF_TOKEN="$(awk '$6=="clubcore_csrf"{print $7}' "$COOKIE_JAR")"

if [ "$LOGIN_STATUS" = "200" ] && [ -n "$CSRF_TOKEN" ]; then
  echo "PASS: login returned $LOGIN_STATUS, CSRF token extracted"
else
  echo "FAIL: login returned $LOGIN_STATUS or CSRF token empty (got: '$CSRF_TOKEN')"
  echo "      Response: $(echo "$LOGIN_RESPONSE" | tail -5)"
  exit 1
fi

# --------------------------------------------------------------------------
# Step 2: create booking
# POST /api/v1/bookings — requires X-CSRF-Token + Idempotency-Key.
# Payload (camelCase wire): slotId, clientId, ptPackageId.
# Expects 201 Created; capture booking id from response body.
# --------------------------------------------------------------------------
echo ""
echo "--- Step 2: create booking ---"
BOOKING_IDEM="$(uuidgen || python3 -c 'import uuid; print(uuid.uuid4())')"
CREATE_RESP=$(curl -si -X POST "$BASE_URL/api/v1/bookings" \
  -H 'Content-Type: application/json' \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -H "Idempotency-Key: $BOOKING_IDEM" \
  -b "$COOKIE_JAR" -c "$COOKIE_JAR" \
  -d "{\"slotId\":\"$SLOT_ID\",\"clientId\":\"$CLIENT_ID\",\"ptPackageId\":\"$PT_PACKAGE_ID\"}")

CREATE_STATUS=$(echo "$CREATE_RESP" | head -1 | awk '{print $2}')
CREATE_BODY=$(echo "$CREATE_RESP" | awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}')
BOOKING_ID=$(echo "$CREATE_BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id',''))" 2>/dev/null || echo "")

if [ "$CREATE_STATUS" = "201" ] && [ -n "$BOOKING_ID" ]; then
  echo "PASS: booking created, id=$BOOKING_ID"
else
  echo "FAIL: expected 201, got $CREATE_STATUS"
  echo "      Body: $CREATE_BODY"
  exit 1
fi

# --------------------------------------------------------------------------
# Step 3: cancel booking
# POST /api/v1/bookings/{id}/cancel — requires X-CSRF-Token.
# Expects 200 OK; booking status flips confirmed → cancelled.
# --------------------------------------------------------------------------
echo ""
echo "--- Step 3: cancel booking ($BOOKING_ID) ---"
CANCEL_RESP=$(curl -si -X POST "$BASE_URL/api/v1/bookings/$BOOKING_ID/cancel" \
  -H 'Content-Type: application/json' \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -b "$COOKIE_JAR" -c "$COOKIE_JAR" \
  -d '{}')

CANCEL_STATUS=$(echo "$CANCEL_RESP" | head -1 | awk '{print $2}')
if [ "$CANCEL_STATUS" = "200" ]; then
  echo "PASS: booking cancelled, status=$CANCEL_STATUS"
else
  echo "FAIL: expected 200, got $CANCEL_STATUS"
  echo "      Body: $(echo "$CANCEL_RESP" | awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}')"
  exit 1
fi

# --------------------------------------------------------------------------
# Step 4: record a completing PT-session (via a fresh booking)
# The slot was cancelled in step 3. To complete the lifecycle:
#   4a. Re-create a second booking on the same slot (the slot flips back to
#       'active' on cancel per the booking FSM).
#   4b. Record a PT-session with booking_id pointing at the new booking,
#       which flips it to 'completed'.
#
# NOTE: Plan 02 (VER-01) structures the cancel and complete on separate
# bookings; this script mirrors that by re-booking before completing.
# The cancel leg (step 3) is the "cancel" lifecycle; the complete leg (step 4)
# is the "complete-via-pt-session" lifecycle.
# --------------------------------------------------------------------------
echo ""
echo "--- Step 4a: re-create booking for complete leg ---"
BOOK2_IDEM="$(uuidgen || python3 -c 'import uuid; print(uuid.uuid4())')"
CREATE2_RESP=$(curl -si -X POST "$BASE_URL/api/v1/bookings" \
  -H 'Content-Type: application/json' \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -H "Idempotency-Key: $BOOK2_IDEM" \
  -b "$COOKIE_JAR" -c "$COOKIE_JAR" \
  -d "{\"slotId\":\"$SLOT_ID\",\"clientId\":\"$CLIENT_ID\",\"ptPackageId\":\"$PT_PACKAGE_ID\"}")

CREATE2_STATUS=$(echo "$CREATE2_RESP" | head -1 | awk '{print $2}')
CREATE2_BODY=$(echo "$CREATE2_RESP" | awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}')
BOOKING2_ID=$(echo "$CREATE2_BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id',''))" 2>/dev/null || echo "")

if [ "$CREATE2_STATUS" = "201" ] && [ -n "$BOOKING2_ID" ]; then
  echo "PASS: second booking created, id=$BOOKING2_ID"
else
  # IN-02: fail hard — if the slot was not restored to 'active' after cancel
  # the complete-via-pt-session leg is never tested, masking an FSM regression.
  echo "FAIL: slot not restored to 'active' after cancel (got $CREATE2_STATUS) — FSM regression"
  echo "      Body: $CREATE2_BODY"
  exit 1
fi

echo ""
echo "--- Step 4b: record completing PT-session ---"
SESS_IDEM="$(uuidgen || python3 -c 'import uuid; print(uuid.uuid4())')"
# performedAt within the payroll period (2026-04-15 matches the Payment row's received_at)
if [ -n "$BOOKING2_ID" ]; then
  SESS_BODY="{\"ptPackageId\":\"$PT_PACKAGE_ID\",\"performedAt\":\"2026-04-15T10:00:00Z\",\"bookingId\":\"$BOOKING2_ID\"}"
else
  SESS_BODY="{\"ptPackageId\":\"$PT_PACKAGE_ID\",\"performedAt\":\"2026-04-15T10:00:00Z\"}"
fi

SESS_RESP=$(curl -si -X POST "$BASE_URL/api/v1/pt-sessions" \
  -H 'Content-Type: application/json' \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -H "Idempotency-Key: $SESS_IDEM" \
  -b "$COOKIE_JAR" -c "$COOKIE_JAR" \
  -d "$SESS_BODY")

SESS_STATUS=$(echo "$SESS_RESP" | head -1 | awk '{print $2}')
SESS_BODY_RESP=$(echo "$SESS_RESP" | awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}')

if [ "$SESS_STATUS" = "201" ]; then
  echo "PASS: pt-session recorded, status=$SESS_STATUS"
else
  echo "FAIL: expected 201, got $SESS_STATUS"
  echo "      Body: $SESS_BODY_RESP"
  exit 1
fi

# --------------------------------------------------------------------------
# Step 5: payroll preview
# GET /api/v1/payroll/preview?trainerId=...&periodStart=...&periodEnd=...
# CSRF-exempt (GET). Expects 200; response shows revenue + sessions.
# The seeded Payment (received_at=2026-04-15) falls within 2026-04-01..2026-04-30.
# --------------------------------------------------------------------------
echo ""
echo "--- Step 5: payroll preview ---"
PREVIEW_RESP=$(curl -si -X GET \
  "$BASE_URL/api/v1/payroll/preview?trainerId=$TRAINER_ID&periodStart=$PERIOD_START&periodEnd=$PERIOD_END" \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -b "$COOKIE_JAR" -c "$COOKIE_JAR")

PREVIEW_STATUS=$(echo "$PREVIEW_RESP" | head -1 | awk '{print $2}')
PREVIEW_BODY=$(echo "$PREVIEW_RESP" | awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}')

if [ "$PREVIEW_STATUS" = "200" ]; then
  echo "PASS: payroll preview returned $PREVIEW_STATUS"
  echo "      Preview: $(echo "$PREVIEW_BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'revenue={d.get(\"revenueKopecks\",\"?\")}, sessions={d.get(\"sessionsCount\",\"?\")}' )" 2>/dev/null || echo "$PREVIEW_BODY")"
else
  echo "FAIL: expected 200, got $PREVIEW_STATUS"
  echo "      Body: $PREVIEW_BODY"
  exit 1
fi

# --------------------------------------------------------------------------
# Step 6: run accrual
# POST /api/v1/payroll/accruals {trainerId, periodStart, periodEnd}
# Requires X-CSRF-Token + Idempotency-Key. Expects 201; capture accrual id.
# Duplicate-period guard (uq_trainer_payroll_accruals_period_alive) → 409 if
# accrual already exists for this period.
# --------------------------------------------------------------------------
echo ""
echo "--- Step 6: run payroll accrual ---"
ACCRUAL_IDEM="$(uuidgen || python3 -c 'import uuid; print(uuid.uuid4())')"
ACCRUAL_RESP=$(curl -si -X POST "$BASE_URL/api/v1/payroll/accruals" \
  -H 'Content-Type: application/json' \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -H "Idempotency-Key: $ACCRUAL_IDEM" \
  -b "$COOKIE_JAR" -c "$COOKIE_JAR" \
  -d "{\"trainerId\":\"$TRAINER_ID\",\"periodStart\":\"$PERIOD_START\",\"periodEnd\":\"$PERIOD_END\"}")

ACCRUAL_STATUS=$(echo "$ACCRUAL_RESP" | head -1 | awk '{print $2}')
ACCRUAL_BODY=$(echo "$ACCRUAL_RESP" | awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}')
ACCRUAL_ID=$(echo "$ACCRUAL_BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id',''))" 2>/dev/null || echo "")

if [ "$ACCRUAL_STATUS" = "201" ] && [ -n "$ACCRUAL_ID" ]; then
  ACCRUAL_ACCRUAL_STATUS=$(echo "$ACCRUAL_BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','?'))" 2>/dev/null || echo "?")
  echo "PASS: accrual created, id=$ACCRUAL_ID, status=$ACCRUAL_ACCRUAL_STATUS"
elif [ "$ACCRUAL_STATUS" = "409" ]; then
  # Idempotent: accrual for this period already exists (prior walkthrough run).
  # Fetch it by listing accruals.
  echo "INFO: 409 — accrual for period already exists; fetching existing accrual id..."
  LIST_RESP=$(curl -si -X GET "$BASE_URL/api/v1/payroll/accruals?trainerId=$TRAINER_ID" \
    -H "X-CSRF-Token: $CSRF_TOKEN" \
    -b "$COOKIE_JAR" -c "$COOKIE_JAR")
  LIST_BODY=$(echo "$LIST_RESP" | awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}')
  ACCRUAL_ID=$(echo "$LIST_BODY" | python3 -c "
import sys, json
d = json.load(sys.stdin)
items = d.get('items', d) if isinstance(d, dict) else d
for item in (items if isinstance(items, list) else []):
    if item.get('status') in ('pending', 'paid'):
        print(item.get('id', ''))
        break
" 2>/dev/null || echo "")
  if [ -n "$ACCRUAL_ID" ]; then
    echo "PASS: existing accrual id=$ACCRUAL_ID"
  else
    echo "FAIL: could not retrieve existing accrual"
    exit 1
  fi
else
  echo "FAIL: expected 201 or 409, got $ACCRUAL_STATUS"
  echo "      Body: $ACCRUAL_BODY"
  exit 1
fi

# --------------------------------------------------------------------------
# Step 7: mark-paid
# POST /api/v1/payroll/accruals/{id}/mark-paid — requires X-CSRF-Token.
# Expects 200; status transitions pending → paid (terminal, single-direction).
# If accrual is already 'paid' from a prior walkthrough run, the endpoint
# should return 409 (already paid guard) — both 200 and 409 are acceptable here.
# --------------------------------------------------------------------------
echo ""
echo "--- Step 7: mark accrual paid ($ACCRUAL_ID) ---"
PAID_RESP=$(curl -si -X POST "$BASE_URL/api/v1/payroll/accruals/$ACCRUAL_ID/mark-paid" \
  -H 'Content-Type: application/json' \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -b "$COOKIE_JAR" -c "$COOKIE_JAR" \
  -d '{}')

PAID_STATUS=$(echo "$PAID_RESP" | head -1 | awk '{print $2}')
PAID_BODY=$(echo "$PAID_RESP" | awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}')

if [ "$PAID_STATUS" = "200" ]; then
  PAID_ACCRUAL_STATUS=$(echo "$PAID_BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','?'))" 2>/dev/null || echo "?")
  echo "PASS: accrual marked paid, status=$PAID_ACCRUAL_STATUS"
elif [ "$PAID_STATUS" = "409" ]; then
  echo "PASS: accrual already paid (409 — prior walkthrough run), status=paid"
else
  echo "FAIL: expected 200 or 409, got $PAID_STATUS"
  echo "      Body: $PAID_BODY"
  exit 1
fi

echo ""
echo "=== P102 Walkthrough COMPLETE (all steps PASS) ==="
echo ""
echo "Summary:"
echo "  booking_id  = ${BOOKING_ID:-n/a}"
echo "  booking2_id = ${BOOKING2_ID:-n/a}"
echo "  accrual_id  = ${ACCRUAL_ID:-n/a}"
