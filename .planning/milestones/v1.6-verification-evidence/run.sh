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
