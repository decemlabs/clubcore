#!/usr/bin/env bash
# Phase 36 pre-flight: confirms dev env is ready for the verification sweep.
# Run BEFORE the 8 scenario scripts; aborts on any red signal.
#
# Implements the Wave 1 → Wave 2 readiness gate per CONTEXT.md Task 6:
# SECRET_KEY length, password env vars, CLI tools, gh auth, npx, live
# backend health, postgres reachability with the corrected app:app creds.

# Note: -e is intentionally OFF (we want check() to keep going after a FAIL)
# so we can present the full red/green tally to the operator. -u + -o pipefail
# stay on for safety.
set -uo pipefail

# Prepend keg-only libpq path (macOS Homebrew) so psql is on PATH for the
# `command -v psql` and connectivity checks below.
if [ -d "/usr/local/opt/libpq/bin" ]; then
  PATH="/usr/local/opt/libpq/bin:$PATH"
  export PATH
fi

PASS=0
FAIL=0
check() {
  local label="$1" cmd="$2"
  if eval "$cmd" >/dev/null 2>&1; then
    echo "  PASS  $label"
    PASS=$((PASS+1))
  else
    echo "  FAIL  $label"
    FAIL=$((FAIL+1))
  fi
}

echo "=== Phase 36 pre-flight ==="

# 1. SECRET_KEY length ≥ 48 bytes (v1.3 first-run-failure lesson).
check "SECRET_KEY ≥48 bytes (apps/backend/.env)" \
  '[ -n "${SECRET_KEY:-}" ] && [ ${#SECRET_KEY} -ge 48 ]'

# 2. SEED_VERIFY_OWNER_PASSWORD ≥ 12 chars.
check "SEED_VERIFY_OWNER_PASSWORD set and ≥12 chars" \
  '[ -n "${SEED_VERIFY_OWNER_PASSWORD:-}" ] && [ ${#SEED_VERIFY_OWNER_PASSWORD} -ge 12 ]'

# 3. SEED_VERIFY_RECEPTION_PASSWORD ≥ 12 chars.
check "SEED_VERIFY_RECEPTION_PASSWORD set and ≥12 chars" \
  '[ -n "${SEED_VERIFY_RECEPTION_PASSWORD:-}" ] && [ ${#SEED_VERIFY_RECEPTION_PASSWORD} -ge 12 ]'

# 4. Required CLI tools.
check "curl available" 'command -v curl'
check "jq available" 'command -v jq'
check "uuidgen available" 'command -v uuidgen'
check "psql available (libpq)" 'command -v psql'
check "docker compose available" 'docker compose version'

# 5. gh CLI authenticated (Wave 2/3 — CI URL capture in 36-04 + handoff in 36-05).
check "gh CLI authenticated (for 36-04 GHA cross-link)" 'gh auth status'

# 6. npx available (Wave 3 — Postman generation in 36-05).
check "npx available (for 36-05 openapi-to-postmanv2)" 'command -v npx'

# 7. Backend reachable on :8000 (live stack up).
# NOTE: the actual liveness endpoint is /healthz, NOT /health (Phase 2 D-14
# Kubernetes contract — see app/api/v1/health.py + app/api/router.py:15).
check "backend reachable on http://localhost:8000/healthz" \
  'curl -sf -o /dev/null http://localhost:8000/healthz'

# 8. Postgres reachable with corrected creds (app/app — NOT sportzal/sportzal
# as CONTEXT.md text mistakenly says; PATTERNS.md line 240 is authoritative).
check "postgres reachable (postgresql://app:app@localhost:5432/sportzal)" \
  'psql "postgresql://app:app@localhost:5432/sportzal" -c "SELECT 1" >/dev/null'

# v1.7 readiness checks (appended per 53-01 Task 2 — do not modify checks 1-8 above).

# 9. Redis reachable — required for webhook dedup SET NX EX (WEBHOOK_DEDUP_KEY_PREFIX).
check "Redis reachable on localhost:6379 (webhook dedup SET NX EX)" \
  'redis-cli -h localhost -p 6379 ping | grep -q PONG'

# 10. ARQ worker registered in Redis — required for dispatch_fiscal_receipt task
#     enqueueing after payment.succeeded webhook processing. ARQ registers the
#     worker health key in Redis when the worker is alive.
check "ARQ worker registered in Redis (arq:queues:default)" \
  'redis-cli -h localhost -p 6379 exists "arq:queues:default" | grep -q "^1$"'

# 11. YOOKASSA_SANDBOX=true — required for verify_yookassa_ip sandbox bypass
#     (webhook_verifier.py:84-86) so the webhook simulation (D-02) passes from
#     localhost. Production stacks must NEVER set this flag.
check "YOOKASSA_SANDBOX=true (sandbox bypass for webhook simulation D-02)" \
  '[ "${YOOKASSA_SANDBOX:-}" = "true" ]'

echo ""
echo "Summary: $PASS pass / $FAIL fail"
if [ "$FAIL" -gt 0 ]; then
  echo "RED — fix failing checks before Wave 2 entry."
  exit 1
fi
echo "GREEN — ready for Wave 2 scenarios (36-02), race tests (36-03), CI gates (36-04)."
