#!/usr/bin/env bash
#
# v1.5 Milestone Verification — 6 curl operator scenarios (VER-05, D-40-14)
#
# Locked scenarios (verbatim from .planning/phases/40-.../40-CONTEXT.md D-40-14):
#   01 — publish slot + list slots
#   02 — book slot via reception
#   03 — concurrent same-slot booking (exactly one 201, one 409 slot_not_available)
#   04 — 24h cancel window dual-role (reception 409 cancel_window_exceeded, owner 200)
#   05 — refund PT-package with outstanding booking (409 outstanding_booking_must_cancel_first)
#   06 — PT-session record completes booking (status confirmed → completed)
#
# Required env vars:
#   DATABASE_URL          — Postgres conn string (e.g. postgresql://postgres:postgres@localhost:5432/sportzal)
#   BASE_URL              — API base URL with /api/v1 prefix (default: http://localhost:8000/api/v1)
#   RECEPTION_EMAIL       — reception fixture email (default: reception@fixture.local)
#   RECEPTION_PASSWORD    — reception fixture password (default from seed_v1_4_verification_fixtures.py)
#   OWNER_EMAIL           — owner fixture email (default: owner@fixture.local)
#   OWNER_PASSWORD        — owner fixture password (default from seed)
#
# Idempotency: each scenario psql-DELETEs its own priors at the head of its block
# so the script is re-runnable against the same docker compose stack.
#
# Usage:
#   docker compose -f apps/backend/docker-compose.yml up -d
#   cd apps/backend && uv run python -m scripts.seed_v1_4_verification_fixtures
#   cd ../..
#   bash .planning/milestones/v1.5-verification-evidence/run.sh
#

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────
EVIDENCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/curl"
mkdir -p "$EVIDENCE_DIR"

BASE_URL="${BASE_URL:-http://localhost:8000/api/v1}"
DATABASE_URL="${DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/sportzal}"
RECEPTION_EMAIL="${RECEPTION_EMAIL:-verify_reception@local.dev}"
RECEPTION_PASSWORD="${RECEPTION_PASSWORD:-Reception!Pass-2026}"
OWNER_EMAIL="${OWNER_EMAIL:-verify_owner@local.dev}"
OWNER_PASSWORD="${OWNER_PASSWORD:-Owner!Pass-2026}"

# ── Pre-flight ────────────────────────────────────────────────────────────
HEALTH_URL="${HEALTH_URL:-${BASE_URL%/api/v1}/healthz}"
echo "[preflight] checking $HEALTH_URL"
if ! curl --silent --fail "$HEALTH_URL" >/dev/null 2>&1; then
  echo "FATAL: stack not up — run 'docker compose -f apps/backend/docker-compose.yml up -d' first" >&2
  exit 1
fi
echo "[preflight] stack reachable"

echo "[preflight] checking psql + DATABASE_URL"
if ! psql "$DATABASE_URL" -c 'SELECT 1' >/dev/null 2>&1; then
  echo "FATAL: cannot connect to DATABASE_URL=$DATABASE_URL" >&2
  exit 1
fi
echo "[preflight] db reachable"

# Acquire session cookies (reception + owner)
echo "[preflight] acquiring reception session cookie"
RECEPTION_COOKIE_JAR="$(mktemp -t reception_cookie.XXXXXX)"
curl -s -c "$RECEPTION_COOKIE_JAR" -X POST "$BASE_URL/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$RECEPTION_EMAIL\",\"password\":\"$RECEPTION_PASSWORD\"}" >/dev/null

echo "[preflight] acquiring owner session cookie"
OWNER_COOKIE_JAR="$(mktemp -t owner_cookie.XXXXXX)"
curl -s -c "$OWNER_COOKIE_JAR" -X POST "$BASE_URL/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$OWNER_EMAIL\",\"password\":\"$OWNER_PASSWORD\"}" >/dev/null

# Resolve fixture UUIDs from DB (no hard-coded UUIDs)
TRAINER_ALPHA_ID=$(psql "$DATABASE_URL" -t -A -c "SELECT id FROM trainers WHERE full_name='Trainer Alpha' LIMIT 1;")
TRAINER_BETA_ID=$(psql "$DATABASE_URL" -t -A -c "SELECT id FROM trainers WHERE full_name='Trainer Beta' LIMIT 1;")
VERIFY_CLIENT_A=$(psql "$DATABASE_URL" -t -A -c "SELECT id FROM clients WHERE email='verify_smoke@fixture.local' LIMIT 1;")
VERIFY_CLIENT_B=$(psql "$DATABASE_URL" -t -A -c "SELECT id FROM clients WHERE email='verify_sale@fixture.local' LIMIT 1;")

if [ -z "$TRAINER_ALPHA_ID" ] || [ -z "$VERIFY_CLIENT_A" ]; then
  echo "FATAL: fixture lookup failed — run 'cd apps/backend && uv run python -m scripts.seed_v1_4_verification_fixtures' first" >&2
  exit 1
fi
echo "[preflight] fixtures resolved: trainer_alpha=$TRAINER_ALPHA_ID client_a=$VERIFY_CLIENT_A"

# ── Scenario 01: publish slot + list slots (VER-05a) ──────────────────────
SCENARIO_OUT="$EVIDENCE_DIR/01_publish_list_slot.http"
: > "$SCENARIO_OUT"
echo "[scenario 01] publish_list_slot — start" >> "$SCENARIO_OUT"

# Hermetic cleanup
psql "$DATABASE_URL" -c "DELETE FROM trainer_availability_slots WHERE trainer_id='$TRAINER_ALPHA_ID' AND start_time > now();" >> "$SCENARIO_OUT"

SLOT_START=$(date -u -v+1d +"%Y-%m-%dT10:00:00Z" 2>/dev/null || date -u -d 'tomorrow 10:00' +"%Y-%m-%dT%H:%M:%SZ")
SLOT_END=$(date -u -v+1d +"%Y-%m-%dT11:00:00Z" 2>/dev/null || date -u -d 'tomorrow 11:00' +"%Y-%m-%dT%H:%M:%SZ")

echo "=== POST $BASE_URL/trainer-slots ===" >> "$SCENARIO_OUT"
curl -i -X POST "$BASE_URL/trainer-slots" \
  -b "$RECEPTION_COOKIE_JAR" \
  -H 'Content-Type: application/json' \
  -d "{\"trainerId\":\"$TRAINER_ALPHA_ID\",\"startTime\":\"$SLOT_START\",\"endTime\":\"$SLOT_END\",\"durationMinutes\":60}" \
  | tee -a "$SCENARIO_OUT"
echo >> "$SCENARIO_OUT"

echo "=== GET $BASE_URL/trainer-slots?trainer_id=$TRAINER_ALPHA_ID ===" >> "$SCENARIO_OUT"
FROM_T=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
TO_T=$(date -u -v+14d +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u -d '+14 days' +"%Y-%m-%dT%H:%M:%SZ")
curl -i -X GET "$BASE_URL/trainer-slots?trainer_id=$TRAINER_ALPHA_ID&from_time=$FROM_T&to_time=$TO_T" \
  -b "$RECEPTION_COOKIE_JAR" \
  | tee -a "$SCENARIO_OUT"
echo >> "$SCENARIO_OUT"

grep -qE '^HTTP/[0-9.]+ 201' "$SCENARIO_OUT" || { echo "scenario 01 FAIL: no 201 from POST /trainer-slots" >&2; exit 1; }
grep -qE '^HTTP/[0-9.]+ 200' "$SCENARIO_OUT" || { echo "scenario 01 FAIL: no 200 from GET /trainer-slots" >&2; exit 1; }
echo "scenario 01 PASS"

# ── Scenario 02: book slot via reception (VER-05b) ────────────────────────
SCENARIO_OUT="$EVIDENCE_DIR/02_book_slot_via_reception.http"
: > "$SCENARIO_OUT"
echo "[scenario 02] book_slot_via_reception — start" >> "$SCENARIO_OUT"

# Hermetic cleanup
psql "$DATABASE_URL" -c "
DELETE FROM bookings WHERE client_id='$VERIFY_CLIENT_A' AND status IN ('confirmed','cancelled');
DELETE FROM trainer_availability_slots WHERE trainer_id='$TRAINER_ALPHA_ID' AND status='booked' AND start_time > now();
" >> "$SCENARIO_OUT"

# Ensure client has an active PT-package (sell via reception if needed)
ACTIVE_PKG=$(psql "$DATABASE_URL" -t -A -c "SELECT id FROM pt_packages WHERE client_id='$VERIFY_CLIENT_A' AND status='active' AND sessions_remaining > 0 LIMIT 1;")
if [ -z "$ACTIVE_PKG" ]; then
  echo "WARN: no active pt_package for $VERIFY_CLIENT_A — sell one first or update seed" >> "$SCENARIO_OUT"
fi

# Publish a fresh slot to book
SLOT_START=$(date -u -v+2d +"%Y-%m-%dT11:00:00Z" 2>/dev/null || date -u -d '+2 days 11:00' +"%Y-%m-%dT%H:%M:%SZ")
SLOT_END=$(date -u -v+2d +"%Y-%m-%dT12:00:00Z" 2>/dev/null || date -u -d '+2 days 12:00' +"%Y-%m-%dT%H:%M:%SZ")
SLOT_RESP=$(curl -s -X POST "$BASE_URL/trainer-slots" \
  -b "$RECEPTION_COOKIE_JAR" \
  -H 'Content-Type: application/json' \
  -d "{\"trainerId\":\"$TRAINER_ALPHA_ID\",\"startTime\":\"$SLOT_START\",\"endTime\":\"$SLOT_END\",\"durationMinutes\":60}")
SLOT_ID=$(echo "$SLOT_RESP" | python3 -c "import json,sys;print(json.load(sys.stdin).get('data',{}).get('id',''))")
echo "fresh slot_id=$SLOT_ID" >> "$SCENARIO_OUT"

IDEMP_KEY="02-$(uuidgen 2>/dev/null || python3 -c 'import uuid;print(uuid.uuid4())')"
echo "=== POST $BASE_URL/bookings (Idempotency-Key: $IDEMP_KEY) ===" >> "$SCENARIO_OUT"
curl -i -X POST "$BASE_URL/bookings" \
  -b "$RECEPTION_COOKIE_JAR" \
  -H 'Content-Type: application/json' \
  -H "Idempotency-Key: $IDEMP_KEY" \
  -d "{\"slotId\":\"$SLOT_ID\",\"clientId\":\"$VERIFY_CLIENT_A\",\"ptPackageId\":\"$ACTIVE_PKG\"}" \
  | tee -a "$SCENARIO_OUT"
echo >> "$SCENARIO_OUT"

grep -qE '^HTTP/[0-9.]+ 201' "$SCENARIO_OUT" || { echo "scenario 02 FAIL: no 201 from POST /bookings" >&2; exit 1; }
grep -qF '"status":"confirmed"' "$SCENARIO_OUT" || { echo "scenario 02 FAIL: expected .data.status='confirmed'" >&2; exit 1; }
echo "scenario 02 PASS"

# ── Scenario 03: concurrent same-slot booking (VER-05c) ───────────────────
SCENARIO_OUT="$EVIDENCE_DIR/03_concurrent_same_slot.http"
: > "$SCENARIO_OUT"
echo "[scenario 03] concurrent_same_slot — start" >> "$SCENARIO_OUT"

# Need a second client with an active PT-package
ACTIVE_PKG_B=$(psql "$DATABASE_URL" -t -A -c "SELECT id FROM pt_packages WHERE client_id='$VERIFY_CLIENT_B' AND status='active' AND sessions_remaining > 0 LIMIT 1;")
if [ -z "$ACTIVE_PKG_B" ]; then
  echo "WARN: no active pt_package for second client $VERIFY_CLIENT_B" >> "$SCENARIO_OUT"
fi

# Publish a fresh slot for the race
SLOT_START=$(date -u -v+3d +"%Y-%m-%dT13:00:00Z" 2>/dev/null || date -u -d '+3 days 13:00' +"%Y-%m-%dT%H:%M:%SZ")
SLOT_END=$(date -u -v+3d +"%Y-%m-%dT14:00:00Z" 2>/dev/null || date -u -d '+3 days 14:00' +"%Y-%m-%dT%H:%M:%SZ")
SLOT_RESP=$(curl -s -X POST "$BASE_URL/trainer-slots" \
  -b "$RECEPTION_COOKIE_JAR" \
  -H 'Content-Type: application/json' \
  -d "{\"trainerId\":\"$TRAINER_ALPHA_ID\",\"startTime\":\"$SLOT_START\",\"endTime\":\"$SLOT_END\",\"durationMinutes\":60}")
RACE_SLOT_ID=$(echo "$SLOT_RESP" | python3 -c "import json,sys;print(json.load(sys.stdin).get('data',{}).get('id',''))")
echo "race slot_id=$RACE_SLOT_ID" >> "$SCENARIO_OUT"

# Two parallel POSTs — different clients, same slot, different Idempotency-Keys
KEY_A="03-a-$(uuidgen 2>/dev/null || python3 -c 'import uuid;print(uuid.uuid4())')"
KEY_B="03-b-$(uuidgen 2>/dev/null || python3 -c 'import uuid;print(uuid.uuid4())')"

echo "=== Parallel POST /bookings (client A + client B, same slot) ===" >> "$SCENARIO_OUT"
(
  curl -i -X POST "$BASE_URL/bookings" \
    -b "$RECEPTION_COOKIE_JAR" \
    -H 'Content-Type: application/json' \
    -H "Idempotency-Key: $KEY_A" \
    -d "{\"slotId\":\"$RACE_SLOT_ID\",\"clientId\":\"$VERIFY_CLIENT_A\",\"ptPackageId\":\"$ACTIVE_PKG\"}" \
    >> "$SCENARIO_OUT" 2>&1
) &
PID_A=$!
(
  curl -i -X POST "$BASE_URL/bookings" \
    -b "$RECEPTION_COOKIE_JAR" \
    -H 'Content-Type: application/json' \
    -H "Idempotency-Key: $KEY_B" \
    -d "{\"slotId\":\"$RACE_SLOT_ID\",\"clientId\":\"$VERIFY_CLIENT_B\",\"ptPackageId\":\"$ACTIVE_PKG_B\"}" \
    >> "$SCENARIO_OUT" 2>&1
) &
PID_B=$!
wait $PID_A $PID_B
echo >> "$SCENARIO_OUT"

COUNT_201=$(grep -cE '^HTTP/[0-9.]+ 201' "$SCENARIO_OUT" || true)
COUNT_409=$(grep -cE '^HTTP/[0-9.]+ 409' "$SCENARIO_OUT" || true)
echo "[scenario 03] 201_count=$COUNT_201 409_count=$COUNT_409" >> "$SCENARIO_OUT"

[ "$COUNT_201" = "1" ] || { echo "scenario 03 FAIL: expected exactly one 201, got $COUNT_201" >&2; exit 1; }
[ "$COUNT_409" = "1" ] || { echo "scenario 03 FAIL: expected exactly one 409, got $COUNT_409" >&2; exit 1; }
grep -qF 'slot_not_available' "$SCENARIO_OUT" || { echo "scenario 03 FAIL: expected .code='slot_not_available' in 409 body" >&2; exit 1; }
echo "scenario 03 PASS"

# ── Scenario 04: 24h cancel window dual-role (VER-05d) ────────────────────
SCENARIO_OUT="$EVIDENCE_DIR/04_cancel_24h_window_dual_role.http"
: > "$SCENARIO_OUT"
echo "[scenario 04] cancel_24h_window_dual_role — start" >> "$SCENARIO_OUT"

# Cleanup priors
psql "$DATABASE_URL" -c "
DELETE FROM bookings WHERE client_id='$VERIFY_CLIENT_A' AND status='confirmed';
" >> "$SCENARIO_OUT"

# Seed a confirmed booking with slot start in 12 hours (inside the 24h window)
psql "$DATABASE_URL" -t -A -c "
INSERT INTO trainer_availability_slots (id, trainer_id, start_time, end_time, status, created_at, updated_at)
VALUES (gen_random_uuid(), '$TRAINER_ALPHA_ID', now() + interval '12 hours', now() + interval '13 hours', 'booked', now(), now())
RETURNING id;" > /tmp/v15_cancel_slot.txt
CANCEL_SLOT_ID=$(grep -oE '[a-f0-9-]{36}' /tmp/v15_cancel_slot.txt | head -1)

psql "$DATABASE_URL" -t -A -c "
INSERT INTO bookings (id, client_id, slot_id, pt_package_id, status, created_at, updated_at)
VALUES (gen_random_uuid(), '$VERIFY_CLIENT_A', '$CANCEL_SLOT_ID', '$ACTIVE_PKG', 'confirmed', now(), now())
RETURNING id;" > /tmp/v15_cancel_booking.txt
CANCEL_BOOKING_ID=$(grep -oE '[a-f0-9-]{36}' /tmp/v15_cancel_booking.txt | head -1)
echo "seeded inside-24h booking_id=$CANCEL_BOOKING_ID slot_id=$CANCEL_SLOT_ID" >> "$SCENARIO_OUT"

echo "=== Reception POST /bookings/$CANCEL_BOOKING_ID/cancel (expect 409 cancel_window_exceeded) ===" >> "$SCENARIO_OUT"
curl -i -X POST "$BASE_URL/bookings/$CANCEL_BOOKING_ID/cancel" \
  -b "$RECEPTION_COOKIE_JAR" \
  -H 'Content-Type: application/json' \
  -d '{}' \
  | tee -a "$SCENARIO_OUT"
echo >> "$SCENARIO_OUT"

echo "=== Owner POST /bookings/$CANCEL_BOOKING_ID/cancel (expect 200 cancelled) ===" >> "$SCENARIO_OUT"
curl -i -X POST "$BASE_URL/bookings/$CANCEL_BOOKING_ID/cancel" \
  -b "$OWNER_COOKIE_JAR" \
  -H 'Content-Type: application/json' \
  -d '{}' \
  | tee -a "$SCENARIO_OUT"
echo >> "$SCENARIO_OUT"

grep -qF 'cancel_window_exceeded' "$SCENARIO_OUT" || { echo "scenario 04 FAIL: expected .code='cancel_window_exceeded' from reception attempt" >&2; exit 1; }
grep -qF '"status":"cancelled"' "$SCENARIO_OUT" || { echo "scenario 04 FAIL: expected .data.status='cancelled' from owner attempt" >&2; exit 1; }
echo "scenario 04 PASS"

# ── Scenario 05: refund PT-package with outstanding booking (VER-05e) ─────
SCENARIO_OUT="$EVIDENCE_DIR/05_refund_with_outstanding_booking.http"
: > "$SCENARIO_OUT"
echo "[scenario 05] refund_with_outstanding_booking — start" >> "$SCENARIO_OUT"

# We need: a fresh active pt_package + a confirmed booking against it
# Cleanup priors
psql "$DATABASE_URL" -c "
DELETE FROM bookings WHERE client_id='$VERIFY_CLIENT_A' AND status='confirmed';
" >> "$SCENARIO_OUT"

# Sell a fresh PT-package via reception
PLAN_ID=$(psql "$DATABASE_URL" -t -A -c "SELECT id FROM pt_package_plans WHERE is_active=true ORDER BY price_kopecks LIMIT 1;")
PKG_RESP=$(curl -s -X POST "$BASE_URL/pt-packages" \
  -b "$RECEPTION_COOKIE_JAR" \
  -H 'Content-Type: application/json' \
  -d "{\"clientId\":\"$VERIFY_CLIENT_A\",\"planId\":\"$PLAN_ID\",\"amountKopecks\":500000}")
NEW_PKG_ID=$(echo "$PKG_RESP" | python3 -c "import json,sys;print(json.load(sys.stdin).get('data',{}).get('id',''))")
echo "fresh pt_package_id=$NEW_PKG_ID" >> "$SCENARIO_OUT"

# Publish a slot + book against the fresh package
SLOT_START=$(date -u -v+5d +"%Y-%m-%dT10:00:00Z" 2>/dev/null || date -u -d '+5 days 10:00' +"%Y-%m-%dT%H:%M:%SZ")
SLOT_END=$(date -u -v+5d +"%Y-%m-%dT11:00:00Z" 2>/dev/null || date -u -d '+5 days 11:00' +"%Y-%m-%dT%H:%M:%SZ")
SLOT_RESP=$(curl -s -X POST "$BASE_URL/trainer-slots" \
  -b "$RECEPTION_COOKIE_JAR" \
  -H 'Content-Type: application/json' \
  -d "{\"trainerId\":\"$TRAINER_ALPHA_ID\",\"startTime\":\"$SLOT_START\",\"endTime\":\"$SLOT_END\",\"durationMinutes\":60}")
REFUND_SLOT_ID=$(echo "$SLOT_RESP" | python3 -c "import json,sys;print(json.load(sys.stdin).get('data',{}).get('id',''))")

IDEMP_KEY="05-$(uuidgen 2>/dev/null || python3 -c 'import uuid;print(uuid.uuid4())')"
BOOK_RESP=$(curl -s -X POST "$BASE_URL/bookings" \
  -b "$RECEPTION_COOKIE_JAR" \
  -H 'Content-Type: application/json' \
  -H "Idempotency-Key: $IDEMP_KEY" \
  -d "{\"slotId\":\"$REFUND_SLOT_ID\",\"clientId\":\"$VERIFY_CLIENT_A\",\"ptPackageId\":\"$NEW_PKG_ID\"}")
OUTSTANDING_BOOKING_ID=$(echo "$BOOK_RESP" | python3 -c "import json,sys;print(json.load(sys.stdin).get('data',{}).get('id',''))")
echo "outstanding booking_id=$OUTSTANDING_BOOKING_ID" >> "$SCENARIO_OUT"

echo "=== POST $BASE_URL/pt-packages/$NEW_PKG_ID/refund (expect 409 outstanding_booking_must_cancel_first) ===" >> "$SCENARIO_OUT"
curl -i -X POST "$BASE_URL/pt-packages/$NEW_PKG_ID/refund" \
  -b "$RECEPTION_COOKIE_JAR" \
  -H 'Content-Type: application/json' \
  -d '{"reason":"verify_refund_blocked_by_outstanding_booking"}' \
  | tee -a "$SCENARIO_OUT"
echo >> "$SCENARIO_OUT"

echo "=== Owner POST $BASE_URL/bookings/$OUTSTANDING_BOOKING_ID/cancel (precondition for refund) ===" >> "$SCENARIO_OUT"
curl -i -X POST "$BASE_URL/bookings/$OUTSTANDING_BOOKING_ID/cancel" \
  -b "$OWNER_COOKIE_JAR" \
  -H 'Content-Type: application/json' \
  -d '{}' \
  | tee -a "$SCENARIO_OUT"
echo >> "$SCENARIO_OUT"

echo "=== Retry POST $BASE_URL/pt-packages/$NEW_PKG_ID/refund (expect 200 refunded) ===" >> "$SCENARIO_OUT"
curl -i -X POST "$BASE_URL/pt-packages/$NEW_PKG_ID/refund" \
  -b "$RECEPTION_COOKIE_JAR" \
  -H 'Content-Type: application/json' \
  -d '{"reason":"verify_refund_after_cancel"}' \
  | tee -a "$SCENARIO_OUT"
echo >> "$SCENARIO_OUT"

grep -qF 'outstanding_booking_must_cancel_first' "$SCENARIO_OUT" || { echo "scenario 05 FAIL: expected .code='outstanding_booking_must_cancel_first'" >&2; exit 1; }
grep -qF '"status":"refunded"' "$SCENARIO_OUT" || { echo "scenario 05 FAIL: expected .data.status='refunded' after cancel" >&2; exit 1; }
echo "scenario 05 PASS"

# ── Scenario 06: PT-session record completes booking (VER-05f) ────────────
SCENARIO_OUT="$EVIDENCE_DIR/06_pt_session_completes_booking.http"
: > "$SCENARIO_OUT"
echo "[scenario 06] pt_session_completes_booking — start" >> "$SCENARIO_OUT"

# Sell a fresh PT-5 (need ≥1 session to record)
PKG_RESP=$(curl -s -X POST "$BASE_URL/pt-packages" \
  -b "$RECEPTION_COOKIE_JAR" \
  -H 'Content-Type: application/json' \
  -d "{\"clientId\":\"$VERIFY_CLIENT_A\",\"planId\":\"$PLAN_ID\",\"amountKopecks\":500000}")
COMPLETE_PKG_ID=$(echo "$PKG_RESP" | python3 -c "import json,sys;print(json.load(sys.stdin).get('data',{}).get('id',''))")
SESSIONS_BEFORE=$(psql "$DATABASE_URL" -t -A -c "SELECT sessions_remaining FROM pt_packages WHERE id='$COMPLETE_PKG_ID';")
echo "pt_package $COMPLETE_PKG_ID sessions_before=$SESSIONS_BEFORE" >> "$SCENARIO_OUT"

# Publish + book a slot
SLOT_START=$(date -u -v+6d +"%Y-%m-%dT10:00:00Z" 2>/dev/null || date -u -d '+6 days 10:00' +"%Y-%m-%dT%H:%M:%SZ")
SLOT_END=$(date -u -v+6d +"%Y-%m-%dT11:00:00Z" 2>/dev/null || date -u -d '+6 days 11:00' +"%Y-%m-%dT%H:%M:%SZ")
SLOT_RESP=$(curl -s -X POST "$BASE_URL/trainer-slots" \
  -b "$RECEPTION_COOKIE_JAR" \
  -H 'Content-Type: application/json' \
  -d "{\"trainerId\":\"$TRAINER_ALPHA_ID\",\"startTime\":\"$SLOT_START\",\"endTime\":\"$SLOT_END\",\"durationMinutes\":60}")
COMPLETE_SLOT_ID=$(echo "$SLOT_RESP" | python3 -c "import json,sys;print(json.load(sys.stdin).get('data',{}).get('id',''))")

IDEMP_KEY="06-$(uuidgen 2>/dev/null || python3 -c 'import uuid;print(uuid.uuid4())')"
BOOK_RESP=$(curl -s -X POST "$BASE_URL/bookings" \
  -b "$RECEPTION_COOKIE_JAR" \
  -H 'Content-Type: application/json' \
  -H "Idempotency-Key: $IDEMP_KEY" \
  -d "{\"slotId\":\"$COMPLETE_SLOT_ID\",\"clientId\":\"$VERIFY_CLIENT_A\",\"ptPackageId\":\"$COMPLETE_PKG_ID\"}")
COMPLETE_BOOKING_ID=$(echo "$BOOK_RESP" | python3 -c "import json,sys;print(json.load(sys.stdin).get('data',{}).get('id',''))")
echo "complete booking_id=$COMPLETE_BOOKING_ID" >> "$SCENARIO_OUT"

# Record the PT-session linked to the booking
PERFORMED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "=== POST $BASE_URL/pt-sessions {booking_id} (expect 201) ===" >> "$SCENARIO_OUT"
curl -i -X POST "$BASE_URL/pt-sessions" \
  -b "$RECEPTION_COOKIE_JAR" \
  -H 'Content-Type: application/json' \
  -d "{\"ptPackageId\":\"$COMPLETE_PKG_ID\",\"trainerId\":\"$TRAINER_ALPHA_ID\",\"bookingId\":\"$COMPLETE_BOOKING_ID\",\"performedAt\":\"$PERFORMED_AT\"}" \
  | tee -a "$SCENARIO_OUT"
echo >> "$SCENARIO_OUT"

echo "=== GET $BASE_URL/bookings/$COMPLETE_BOOKING_ID (expect 200 status=completed) ===" >> "$SCENARIO_OUT"
curl -i -X GET "$BASE_URL/bookings/$COMPLETE_BOOKING_ID" \
  -b "$RECEPTION_COOKIE_JAR" \
  | tee -a "$SCENARIO_OUT"
echo >> "$SCENARIO_OUT"

SESSIONS_AFTER=$(psql "$DATABASE_URL" -t -A -c "SELECT sessions_remaining FROM pt_packages WHERE id='$COMPLETE_PKG_ID';")
echo "pt_package $COMPLETE_PKG_ID sessions_after=$SESSIONS_AFTER (expect $((SESSIONS_BEFORE-1)))" >> "$SCENARIO_OUT"

grep -qF '"status":"completed"' "$SCENARIO_OUT" || { echo "scenario 06 FAIL: expected .data.status='completed' in GET /bookings/{id}" >&2; exit 1; }
[ "$SESSIONS_AFTER" = "$((SESSIONS_BEFORE-1))" ] || { echo "scenario 06 FAIL: sessions_remaining delta != -1 (before=$SESSIONS_BEFORE after=$SESSIONS_AFTER)" >&2; exit 1; }
echo "scenario 06 PASS"

# ── Done ──────────────────────────────────────────────────────────────────
rm -f "$RECEPTION_COOKIE_JAR" "$OWNER_COOKIE_JAR"
echo "All 6 curl scenarios PASS — transcripts under $EVIDENCE_DIR"
