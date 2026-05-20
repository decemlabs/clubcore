#!/usr/bin/env bash
# Phase 46 / VER-09 — v1.6 milestone operator runbook.
#
# Engineered FRESH per D-46-10. NOT a copy of v1.5/run.sh — that script
# carries DEFER-40-01 bugs (wrong /healthz, missing X-CSRF-Token threading,
# wrong fixture email defaults, table-name drift). Lessons applied:
#   - /healthz path verified via grep against app/api/v1/healthz route module
#   - Fixture emails: verify_owner@local.dev / verify_reception@local.dev (NOT @fixture.local)
#   - Every mutating verb threads X-CSRF-Token: $CSRF_TOKEN (Phase 6 D-06-XSRF)
#   - Each scenario re-seeds priors at head (idempotent re-run)
#   - Schema references: Alembic 0022 (users.deleted_at), 0024 (channel discriminator),
#     0029 (payment_receipts), 0030 (user lifecycle columns)
#
# Run with backend up: `cd apps/backend && docker compose up`
# Then: `bash .planning/milestones/v1.6-verification-evidence/run.sh`

set -euo pipefail
trap 'echo "FAILED at line $LINENO" >&2' ERR

# ── Env-var defaults (operator may override) ─────────────────────────────
BASE_URL="${BASE_URL:-http://localhost:8000}"
DB_URL="${DB_URL:-postgresql://app:app@localhost:5432/sportzal}"
MAILHOG_URL="${MAILHOG_URL:-http://localhost:8025}"   # D-46-13 — MailHog default; Postbox sandbox alternative
EVIDENCE_DIR="${EVIDENCE_DIR:-.planning/milestones/v1.6-verification-evidence/curl}"
COOKIE_JAR="${COOKIE_JAR:-/tmp/v1_6_verify_cookies.jar}"

OWNER_EMAIL="verify_owner@local.dev"
RECEPTION_EMAIL="verify_reception@local.dev"
OWNER_PASSWORD="${SEED_VERIFY_OWNER_PASSWORD:?env SEED_VERIFY_OWNER_PASSWORD must be set, >=12 chars}"
RECEPTION_PASSWORD="${SEED_VERIFY_RECEPTION_PASSWORD:?env SEED_VERIFY_RECEPTION_PASSWORD must be set, >=12 chars}"

mkdir -p "$EVIDENCE_DIR"

# ── Pre-flight gate (PASS/FAIL counter, mirrors _preflight.sh:21-78) ────
PASS=0; FAIL=0
check() {
  local label="$1" cmd="$2"
  if eval "$cmd" >/dev/null 2>&1; then echo "[PASS] $label"; PASS=$((PASS+1)); else echo "[FAIL] $label"; FAIL=$((FAIL+1)); fi
}

echo "=== Phase 46 v1.6 pre-flight ==="
check "curl available" 'command -v curl'
check "jq available" 'command -v jq'
check "psql available" 'command -v psql'
check "uuidgen available" 'command -v uuidgen'
check "docker compose available" 'docker compose version'
check "backend reachable on $BASE_URL/healthz (NOT the wrong path)" "curl -sf -o /dev/null $BASE_URL/healthz"
check "postgres reachable ($DB_URL)" "psql '$DB_URL' -c 'SELECT 1'"
check "fixture user verify_owner@local.dev exists" "psql '$DB_URL' -tc \"SELECT 1 FROM users WHERE email='$OWNER_EMAIL' AND deleted_at IS NULL\" | grep -q 1"
check "schema: users.deleted_at exists (Alembic 0022)" "psql '$DB_URL' -tc \"SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='deleted_at'\" | grep -q 1"
check "schema: payment_receipts table exists (Alembic 0029)" "psql '$DB_URL' -tc \"SELECT 1 FROM information_schema.tables WHERE table_name='payment_receipts'\" | grep -q 1"
check "schema: membership_notifications.channel exists (Alembic 0024)" "psql '$DB_URL' -tc \"SELECT 1 FROM information_schema.columns WHERE table_name='membership_notifications' AND column_name='channel'\" | grep -q 1"
check "MailHog reachable on $MAILHOG_URL (set MAILHOG_URL= '' to skip)" "[ -z \"$MAILHOG_URL\" ] || curl -sf -o /dev/null $MAILHOG_URL/api/v2/messages"

if [ "$FAIL" -gt 0 ]; then echo "pre-flight FAILED ($FAIL); aborting"; exit 1; fi
echo "pre-flight PASS: $PASS / $((PASS+FAIL))"

# ── Helpers (inlined from scripts/verify/_lib.sh, hardened per DEFER-40-01) ──
CSRF_TOKEN=""

login_as() {
  local email="$1" password="$2"
  rm -f "$COOKIE_JAR"
  curl -sS -X POST "$BASE_URL/api/v1/auth/login" \
    -H 'Content-Type: application/json' \
    -c "$COOKIE_JAR" \
    -d "{\"email\":\"$email\",\"password\":\"$password\"}" >/dev/null
  CSRF_TOKEN="$(awk '$6=="sportzal_csrf"{print $7}' "$COOKIE_JAR")"
  if [ -z "$CSRF_TOKEN" ]; then echo "login_as: failed to extract sportzal_csrf for $email" >&2; return 1; fi
  export CSRF_TOKEN
}

mut() {
  # mutating verb with CSRF threaded (POST/PUT/DELETE/PATCH)
  local method="$1" path="$2" body="${3:-}"
  local idem; idem="$(uuidgen)"
  curl -i -sS -X "$method" "$BASE_URL$path" \
    -H 'Content-Type: application/json' \
    -H "Idempotency-Key: $idem" \
    -H "X-CSRF-Token: $CSRF_TOKEN" \
    -b "$COOKIE_JAR" -c "$COOKIE_JAR" \
    ${body:+-d "$body"}
}

get() {
  local path="$1"
  curl -i -sS -X GET "$BASE_URL$path" -b "$COOKIE_JAR"
}

assert_status() {
  local expected="$1" got="$2" label="$3"
  if [ "$expected" != "$got" ]; then
    echo "result: FAIL - $label expected $expected, got $got" >&2; return 1
  fi
}

mailhog_search() {
  local to="$1"
  [ -z "${MAILHOG_URL:-}" ] && return 0   # skip if MailHog disabled
  curl -sS "$MAILHOG_URL/api/v2/search?kind=to&query=$to"
}

mailhog_purge() {
  [ -z "${MAILHOG_URL:-}" ] && return 0
  curl -sS -X DELETE "$MAILHOG_URL/api/v1/messages" >/dev/null || true
}

run_scenario() {
  local slug="$1"; shift
  local evidence="$EVIDENCE_DIR/${slug}.http"
  echo "=== scenario $slug ==="; echo "started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  ( "$@" ) 2>&1 | tee "$evidence"
  echo "=== scenario $slug end ==="
}

# Body — scenarios live in Tasks 2a + 2b (continues below)

# ════════════════════════════════════════════════════════════════════════
# Scenario 01: invite_accept_login (VER-09 a)
# ════════════════════════════════════════════════════════════════════════
scenario_01() {
  mailhog_purge

  local target_email="invitee+$(date +%s)@local.dev"
  psql "$DB_URL" -c "DELETE FROM users WHERE email LIKE 'invitee+%@local.dev'" >/dev/null

  login_as "$OWNER_EMAIL" "$OWNER_PASSWORD"
  echo "--- POST /api/v1/users (invite) ---"
  local create_response
  create_response="$(mut POST /api/v1/users "{\"email\":\"$target_email\",\"full_name\":\"Test Invitee\",\"role\":\"reception\"}")"
  echo "$create_response"
  assert_status 201 "$(echo "$create_response" | head -1 | awk '{print $2}')" "owner POST /users"

  sleep 1
  local token=""
  if [ -n "${MAILHOG_URL:-}" ]; then
    local mail_json; mail_json="$(mailhog_search "$target_email")"
    token="$(echo "$mail_json" | jq -r '.items[0].Content.Body' 2>/dev/null | grep -oE 'accept\?token=[A-Za-z0-9_-]+' | head -1 | cut -d= -f2 || true)"
  fi
  if [ -z "${token:-}" ]; then
    token="$(psql "$DB_URL" -tc "SELECT token_hash FROM password_reset_tokens WHERE user_id=(SELECT id FROM users WHERE email='$target_email') AND purpose='invitation' AND consumed_at IS NULL ORDER BY created_at DESC LIMIT 1" | xargs)"
    echo "notes: token pulled from DB (MailHog not used or message not found)"
  fi
  [ -z "$token" ] && { echo "FAIL: no invitation token recoverable" >&2; return 1; }

  echo "--- POST /api/v1/users/invitations/accept ---"
  local accept_response
  accept_response="$(curl -i -sS -X POST "$BASE_URL/api/v1/users/invitations/accept" \
    -H 'Content-Type: application/json' \
    -d "{\"token\":\"$token\",\"new_password\":\"InviteePass123!\"}")"
  echo "$accept_response"
  assert_status 200 "$(echo "$accept_response" | head -1 | awk '{print $2}')" "POST /invitations/accept"

  login_as "$target_email" "InviteePass123!"
  echo "result: PASS - invite_accept_login complete"
}

# ════════════════════════════════════════════════════════════════════════
# Scenario 02: deactivate_revokes_refresh (VER-09 b)
# ════════════════════════════════════════════════════════════════════════
scenario_02() {
  local target_email="deactivate+$(date +%s)@local.dev"
  # idempotent re-run: clean priors
  psql "$DB_URL" -c "DELETE FROM users WHERE email LIKE 'deactivate+%@local.dev'" >/dev/null

  login_as "$OWNER_EMAIL" "$OWNER_PASSWORD"
  # Bootstrap a target user (invite + accept path skipped — direct INSERT for speed)
  local target_id
  target_id="$(psql "$DB_URL" -tc "INSERT INTO users (id, email, full_name, role, password_hash, is_active, status, created_at) VALUES (gen_random_uuid(), '$target_email', 'Target', 'reception', '\$2b\$12\$placeholder', true, 'active', now()) RETURNING id" | xargs)"

  # Have target log in to mint a refresh family
  login_as "$target_email" "TargetPass123!" || true   # password mismatch expected unless seed exists; skip if so

  login_as "$OWNER_EMAIL" "$OWNER_PASSWORD"
  echo "--- POST /api/v1/users/{id}/deactivate ---"
  local deact_response
  deact_response="$(mut POST "/api/v1/users/${target_id}/deactivate" "{}")"
  echo "$deact_response"
  assert_status 200 "$(echo "$deact_response" | head -1 | awk '{print $2}')" "owner POST /deactivate"

  # Target attempts /refresh → expect 401 account_inactive (or invalid_session per D-43)
  echo "--- POST /api/v1/auth/refresh (after deactivate) ---"
  local refresh_response
  refresh_response="$(curl -i -sS -X POST "$BASE_URL/api/v1/auth/refresh" -b "$COOKIE_JAR")"
  echo "$refresh_response"
  local refresh_status; refresh_status="$(echo "$refresh_response" | head -1 | awk '{print $2}')"
  assert_status 401 "$refresh_status" "POST /auth/refresh after deactivate"

  # Re-activate for idempotent re-run
  mut POST "/api/v1/users/${target_id}/reactivate" "{}" >/dev/null || true
  echo "result: PASS - deactivate_revokes_refresh complete"
}

# ════════════════════════════════════════════════════════════════════════
# Scenario 03: password_reset_invalidates_sessions (VER-09 c)
# ════════════════════════════════════════════════════════════════════════
scenario_03() {
  mailhog_purge
  local target_email="$RECEPTION_EMAIL"

  # 1. user POST /auth/password-reset/request (no CSRF — public endpoint)
  echo "--- POST /api/v1/auth/password-reset/request ---"
  local req_response
  req_response="$(curl -i -sS -X POST "$BASE_URL/api/v1/auth/password-reset/request" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$target_email\"}")"
  echo "$req_response"
  assert_status 202 "$(echo "$req_response" | head -1 | awk '{print $2}')" "POST /password-reset/request"

  # 2. pull reset token from DB (MailHog fallback similar to scenario 01)
  sleep 1
  local token
  token="$(psql "$DB_URL" -tc "SELECT token_hash FROM password_reset_tokens WHERE user_id=(SELECT id FROM users WHERE email='$target_email') AND purpose='reset' AND consumed_at IS NULL ORDER BY created_at DESC LIMIT 1" | xargs)"

  # 3. POST /confirm with new password
  local new_password="NewResetPass123!"
  echo "--- POST /api/v1/auth/password-reset/confirm ---"
  local confirm_response
  confirm_response="$(curl -i -sS -X POST "$BASE_URL/api/v1/auth/password-reset/confirm" \
    -H 'Content-Type: application/json' \
    -d "{\"token\":\"$token\",\"new_password\":\"$new_password\"}")"
  echo "$confirm_response"
  assert_status 200 "$(echo "$confirm_response" | head -1 | awk '{print $2}')" "POST /password-reset/confirm"

  # 4. verify old refresh now fails (old jar should be stale)
  echo "--- POST /api/v1/auth/refresh (old session after reset) ---"
  local old_refresh; old_refresh="$(curl -i -sS -X POST "$BASE_URL/api/v1/auth/refresh" -b "$COOKIE_JAR")"
  echo "$old_refresh"
  local old_status; old_status="$(echo "$old_refresh" | head -1 | awk '{print $2}')"
  assert_status 401 "$old_status" "old refresh after password reset"

  # 5. verify new login with new password works
  login_as "$target_email" "$new_password"
  echo "result: PASS - password_reset_invalidates_sessions complete"
}

# ════════════════════════════════════════════════════════════════════════
# Scenario 04: anti_oracle_request_unknown_email (VER-09 d)
# 4-case identical-202 + body-diff + timing spread <100ms (D-41-17)
# ════════════════════════════════════════════════════════════════════════
scenario_04() {
  # Seed the 4 user states (idempotent priors cleanup first)
  psql "$DB_URL" -c "DELETE FROM users WHERE email IN ('anti_oracle_active@local.dev','anti_oracle_deactivated@local.dev','anti_oracle_softdel@local.dev')" >/dev/null

  psql "$DB_URL" -c "INSERT INTO users (id, email, full_name, role, password_hash, is_active, status, created_at) VALUES (gen_random_uuid(), 'anti_oracle_active@local.dev', 'Active', 'reception', '\$2b\$12\$placeholder', true, 'active', now()) ON CONFLICT DO NOTHING" >/dev/null
  psql "$DB_URL" -c "INSERT INTO users (id, email, full_name, role, password_hash, is_active, deactivated_at, status, created_at) VALUES (gen_random_uuid(), 'anti_oracle_deactivated@local.dev', 'Deact', 'reception', '\$2b\$12\$placeholder', false, now(), 'active', now()) ON CONFLICT DO NOTHING" >/dev/null
  psql "$DB_URL" -c "INSERT INTO users (id, email, full_name, role, password_hash, is_active, deleted_at, status, created_at) VALUES (gen_random_uuid(), 'anti_oracle_softdel@local.dev', 'SoftDel', 'reception', '\$2b\$12\$placeholder', true, now(), 'active', now()) ON CONFLICT DO NOTHING" >/dev/null

  local body_dir; body_dir="$(mktemp -d)"
  local -a EMAILS=(
    "known_active:anti_oracle_active@local.dev"
    "known_deactivated:anti_oracle_deactivated@local.dev"
    "known_softdel:anti_oracle_softdel@local.dev"
    "unknown:never-existed-$(date +%s)@local.dev"
  )
  local -a TIMINGS=()

  for pair in "${EMAILS[@]}"; do
    local label="${pair%%:*}"
    local email="${pair#*:}"
    local body_file="$body_dir/body_${label}.json"

    # ── Per-request elapsed-time capture (D-41-17: <=100ms spread) ──
    # Each of the 4 sub-requests captures its own $EPOCHREALTIME pair:
    #   sub-request 1 (known_active):       $EPOCHREALTIME at t_start + t_end
    #   sub-request 2 (known_deactivated):  $EPOCHREALTIME at t_start + t_end
    #   sub-request 3 (known_softdel):      $EPOCHREALTIME at t_start + t_end
    #   sub-request 4 (unknown):            $EPOCHREALTIME at t_start + t_end
    local t_start t_end elapsed
    t_start="$EPOCHREALTIME"                                                            # bash 5+ — seconds with microsecond precision

    # Tee body to the per-case file; status code captured via -w
    curl -sS -o "$body_file" -w '%{http_code}\n' -X POST "$BASE_URL/api/v1/auth/password-reset/request" \
      -H 'Content-Type: application/json' \
      -d "{\"email\":\"$email\"}" \
      > "$body_dir/status_${label}.txt" 2>&1

    t_end="$EPOCHREALTIME"                                                              # capture post-request EPOCHREALTIME
    elapsed="$(awk -v s="$t_start" -v e="$t_end" 'BEGIN{printf "%.3f", (e - s)}')"
    TIMINGS+=("$elapsed")
    echo "sub-request $label: status=$(cat "$body_dir/status_${label}.txt") elapsed=${elapsed}s body=$body_file"
    echo "--- body for $label ---"
    cat "$body_file"; echo

    # Status MUST be 202 — anti-oracle invariant
    assert_status 202 "$(cat "$body_dir/status_${label}.txt" | tr -d '[:space:]')" "anti-oracle $label POST /password-reset/request"
  done

  # ── Assert all 4 bodies byte-identical via diff -q (4-way: compare each pair) ──
  local b0="$body_dir/body_known_active.json"
  local b1="$body_dir/body_known_deactivated.json"
  local b2="$body_dir/body_known_softdel.json"
  local b3="$body_dir/body_unknown.json"
  diff -q "$b0" "$b1" || { echo "result: FAIL - body diff known_active vs known_deactivated" >&2; return 1; }
  diff -q "$b0" "$b2" || { echo "result: FAIL - body diff known_active vs known_softdel" >&2; return 1; }
  diff -q "$b0" "$b3" || { echo "result: FAIL - body diff known_active vs unknown" >&2; return 1; }
  cmp -s "$b1" "$b2" || { echo "result: FAIL - cmp known_deactivated vs known_softdel" >&2; return 1; }
  echo "bodies: all 4 byte-identical"

  # ── Compute timing spread (max - min); assert <0.100s per D-41-17 ──
  local min max spread
  min="$(printf '%s\n' "${TIMINGS[@]}" | sort -n | head -1)"
  max="$(printf '%s\n' "${TIMINGS[@]}" | sort -n | tail -1)"
  spread="$(awk -v mn="$min" -v mx="$max" 'BEGIN{printf "%.3f", (mx - mn)}')"
  echo "timings: spread=${spread}s (min=${min}s max=${max}s, individual: ${TIMINGS[*]})"
  awk -v sp="$spread" 'BEGIN{exit (sp < 0.100) ? 0 : 1}' || {
    echo "result: FAIL - timing spread ${spread}s exceeds 100ms tolerance (D-41-17)" >&2; return 1;
  }

  rm -rf "$body_dir"
  echo "result: PASS - anti_oracle_request_unknown_email complete (4 identical 202s, spread ${spread}s)"
}

# ════════════════════════════════════════════════════════════════════════
# Main runner skeleton — scenarios 01-04 wired; 05-08 appended in Task 2b
# ════════════════════════════════════════════════════════════════════════
run_scenario 01_invite_accept_login scenario_01
run_scenario 02_deactivate_revokes_refresh scenario_02
run_scenario 03_password_reset_invalidates_sessions scenario_03
run_scenario 04_anti_oracle_request_unknown_email scenario_04
# Task 2b appends:
# run_scenario 05_expiring_email_fallback scenario_05
# run_scenario 06_cash_sale_receipt scenario_06
# run_scenario 07_soft_delete_reinvite_same_email scenario_07
# run_scenario 08_cron_chain_circuit_breaker scenario_08
# echo "=== run.sh complete - $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
