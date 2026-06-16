#!/usr/bin/env bash
# Phase 36 verification helper library — sourced by every
# apps/backend/scripts/verify/<NN>_*.sh scenario script.
#
# Exports / provides:
#   - BASE_URL                          (default http://localhost:8000)
#   - COOKIE_JAR                        (per-script mktemp, auto-cleaned on EXIT)
#   - CSRF_TOKEN                        (set by login_as; auto-injected by mut)
#   - login_as <owner|reception>        POST /api/v1/auth/login
#   - mut <METHOD> <PATH> <JSON_BODY>   curl wrapper w/ Idempotency-Key + CSRF
#   - get <PATH>                        read-only GET
#   - psql_exec <SQL>                   local psql against compose postgres
#   - assert_status <expected_code>     pipe-friendly HTTP status assertion
#   - assert_body_jq <jq_expr> <value>  pipe-friendly JSON body assertion
#
# Requires (operator host): curl, jq, uuidgen, psql (libpq).
# Auth contract notes:
#   - /api/v1/auth/login is CSRF-exempt (apps/backend/app/modules/auth/router.py).
#   - Cookies set by issue_session_cookies (app/core/security.py):
#       cc_access       HTTP-only access JWT, Path=/
#       cc_refresh      HTTP-only refresh token, Path=/api/v1/auth
#       clubcore_csrf   non-HttpOnly CSRF token, Path=/, used as X-CSRF-Token
#                       header value on every mutating verb.
#   - Auth flows via the cc_access cookie automatically when curl reuses the
#     cookie jar with -b "$COOKIE_JAR" — there is NO access JWT in the login
#     response body, so no Authorization: Bearer header is added.
#
# psql credentials are app/app/clubcore per apps/backend/docker-compose.yml
# (POSTGRES_DB: clubcore, DATABASE_URL .../clubcore). The database was renamed
# from `sportzal` to `clubcore`; the DSN in psql_exec must use `clubcore` or
# every psql_exec call fails with FATAL: database "sportzal" does not exist.
#
# Keg-only libpq path: macOS Homebrew installs psql under
# /usr/local/opt/libpq/bin; prepended to PATH below so psql_exec works without
# the operator having to manually link libpq into /usr/local/bin.

set -euo pipefail

# Prepend keg-only libpq path if it exists (macOS Homebrew default).
if [ -d "/usr/local/opt/libpq/bin" ]; then
  PATH="/usr/local/opt/libpq/bin:$PATH"
  export PATH
fi

BASE_URL="${BASE_URL:-http://localhost:8000}"
COOKIE_JAR="$(mktemp -t sportzal-verify-XXXX.cookies)"
trap 'rm -f "$COOKIE_JAR"' EXIT

VERIFY_OWNER_EMAIL="${VERIFY_OWNER_EMAIL:-verify_owner@local.dev}"
VERIFY_OWNER_PASSWORD="${VERIFY_OWNER_PASSWORD:?must be exported (seed sets it via SEED_VERIFY_OWNER_PASSWORD)}"
VERIFY_RECEPTION_EMAIL="${VERIFY_RECEPTION_EMAIL:-verify_reception@local.dev}"
VERIFY_RECEPTION_PASSWORD="${VERIFY_RECEPTION_PASSWORD:?must be exported (seed sets it via SEED_VERIFY_RECEPTION_PASSWORD)}"

CSRF_TOKEN=""

# login_as <owner|reception>
# POST /api/v1/auth/login (CSRF-exempt). Writes cookies to $COOKIE_JAR; extracts
# the clubcore_csrf value via awk on the Netscape cookie-jar format (column 6 =
# cookie name, column 7 = cookie value). Exports CSRF_TOKEN for mut().
login_as() {
  local role="$1"
  local email password
  case "$role" in
    owner)
      email="$VERIFY_OWNER_EMAIL"
      password="$VERIFY_OWNER_PASSWORD"
      ;;
    reception)
      email="$VERIFY_RECEPTION_EMAIL"
      password="$VERIFY_RECEPTION_PASSWORD"
      ;;
    *)
      echo "login_as: unknown role '$role' (expected owner|reception)" >&2
      return 2
      ;;
  esac

  curl -i -s -X POST "$BASE_URL/api/v1/auth/login" \
    -H 'Content-Type: application/json' \
    -c "$COOKIE_JAR" \
    -d "{\"email\":\"$email\",\"password\":\"$password\"}"

  CSRF_TOKEN="$(awk '$6=="clubcore_csrf"{print $7}' "$COOKIE_JAR")"
  if [ -z "$CSRF_TOKEN" ]; then
    echo "login_as: failed to extract clubcore_csrf from cookie jar" >&2
    return 1
  fi
  export CSRF_TOKEN
}

# mut <METHOD> <PATH> <JSON_BODY>
# Auto-attaches Idempotency-Key (D-36-04 — every mutating verb), X-CSRF-Token,
# and reuses $COOKIE_JAR (auth via cc_access HTTP-only cookie). Outputs the
# verbatim curl -i transcript (status line + headers + body) for evidence-tee.
mut() {
  local method="$1" path="$2" body="$3"
  local idem
  idem="$(uuidgen)"
  curl -i -s -X "$method" "$BASE_URL$path" \
    -H 'Content-Type: application/json' \
    -H "Idempotency-Key: $idem" \
    -H "X-CSRF-Token: $CSRF_TOKEN" \
    -b "$COOKIE_JAR" -c "$COOKIE_JAR" \
    -d "$body"
}

# get <PATH>
# Read-only GET (CSRF-exempt server-side; no Idempotency-Key needed).
get() {
  local path="$1"
  curl -i -s -X GET "$BASE_URL$path" \
    -b "$COOKIE_JAR" -c "$COOKIE_JAR"
}

# psql_exec <SQL>
# D-36-05 sanctions verification-time DB time-travel; callers MUST log intent
# in a script comment AND in VERIFICATION-LOG.md `notes:` for the scenario.
psql_exec() {
  local sql="$1"
  psql "postgresql://app:app@localhost:5432/clubcore" -c "$sql"
}

# assert_status <expected_code>
# Reads piped HTTP response (curl -i output), extracts status line, compares.
# Status line format: "HTTP/1.1 <code> <reason>"; awk '{print $2}' gives code.
assert_status() {
  local expected="$1"
  local actual
  actual="$(head -1 | awk '{print $2}')"
  if [ "$actual" != "$expected" ]; then
    echo "ASSERTION FAIL: expected status $expected, got $actual" >&2
    exit 1
  fi
}

# assert_body_jq <jq_expr> <expected_value>
# Reads piped HTTP response, strips headers (everything up to and including the
# first blank line), runs jq -r against the body. CRLF line endings from HTTP
# are handled by matching /^\r\?$/.
assert_body_jq() {
  local expr="$1" expected="$2"
  local actual
  actual="$(awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}' | jq -r "$expr")"
  if [ "$actual" != "$expected" ]; then
    echo "ASSERTION FAIL: jq '$expr' returned '$actual', expected '$expected'" >&2
    exit 1
  fi
}

# D-36-15 inline-fix protocol: any scenario failure → reproduce → fix inline as
# own commit `fix(36-NN): REG-36-XX <desc>` → re-run → log in VERIFICATION-LOG.md
# `overrides:` block. Hard cap 5 regressions (D-36-17); beyond that, STOP and
# escalate — suggests Phases 30-35 verification gaps requiring a Phase 36.1
# hot-fix phase or milestone hold.
