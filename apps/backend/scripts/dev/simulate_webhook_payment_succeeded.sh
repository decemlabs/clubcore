#!/usr/bin/env bash
# Local DX helper — confirm a stuck online payment by simulating ЮKassa's
# `payment.succeeded` webhook.
#
# WHY THIS EXISTS
#   In local dev, ЮKassa's servers cannot POST webhooks to your localhost, so an
#   `online_payments` row never transitions `pending -> succeeded` and the client
#   PWA "Ожидаем подтверждение" screen polls forever. Payment status is 100%
#   webhook-authoritative by design (D-10 anti-oracle; there is NO poll_pending_payments
#   cron — only poll_pending_refunds exists). This script delivers the webhook for you.
#
#   It only works because the webhook IP allowlist has a sandbox bypass
#   (`verify_yookassa_ip`: `if _settings.sandbox: return`), so a localhost POST is
#   accepted when YOOKASSA_SANDBOX=true. The handler then re-fetches the payment from
#   the ЮKassa sandbox (the webhook body is NOT trusted), which returns `succeeded`.
#
#   Mirrors the step3_webhook pattern in
#   apps/backend/scripts/verify/09_online_sale_to_fiscal.sh.
#
# USAGE
#   apps/backend/scripts/dev/simulate_webhook_payment_succeeded.sh <online_payment_id>
#
#   <online_payment_id> is the INTERNAL online_payments UUID — the same value the
#   client PWA carries in the return URL: /payment/return?payment_id=<online_payment_id>.
#
# PREREQUISITES
#   - Backend compose stack up (docker compose ps: backend, postgres, redis).
#   - YOOKASSA_SANDBOX=true on the stack (apps/backend/.env). Without it the POST 403s.
#
# OVERRIDES (env vars, sensible defaults for the standard local stack)
#   BASE_URL      default http://localhost:8000
#   COMPOSE_FILE  default <repo>/apps/backend/docker-compose.yml
#   PG_DB         default clubcore     PG_USER default app
#   PG_SERVICE    default postgres     REDIS_SERVICE default redis
set -euo pipefail

ONLINE_PAYMENT_ID="${1:-}"
if [ -z "$ONLINE_PAYMENT_ID" ]; then
  echo "usage: $(basename "$0") <online_payment_id>" >&2
  echo "  <online_payment_id> = internal online_payments UUID (the payment_id in /payment/return?payment_id=...)" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_URL="${BASE_URL:-http://localhost:8000}"
COMPOSE_FILE="${COMPOSE_FILE:-$SCRIPT_DIR/../../docker-compose.yml}"
PG_DB="${PG_DB:-clubcore}"
PG_USER="${PG_USER:-app}"
PG_SERVICE="${PG_SERVICE:-postgres}"
REDIS_SERVICE="${REDIS_SERVICE:-redis}"

# Webhook dedup key prefix — authoritative source: WEBHOOK_DEDUP_KEY_PREFIX in
# app/api/v1/_internal/yookassa/router.py. Keep in sync if that constant changes.
DEDUP_PREFIX="cc:yookassa:webhook:"

dc() { docker compose -f "$COMPOSE_FILE" "$@"; }
psql_q() { dc exec -T "$PG_SERVICE" psql -U "$PG_USER" -d "$PG_DB" -tA -c "$1"; }

# --- 1. Look up the ЮKassa payment id + current status ---
ROW="$(psql_q "SELECT yookassa_payment_id, status, amount_kopecks FROM online_payments WHERE id = '${ONLINE_PAYMENT_ID}'")"
if [ -z "$ROW" ]; then
  echo "FAIL: no online_payments row for id=${ONLINE_PAYMENT_ID}" >&2
  echo "  (check the id, and that the compose stack / DB '${PG_DB}' is the one the PWA hit)" >&2
  exit 1
fi

YK_ID="$(echo "$ROW" | cut -d'|' -f1)"
STATUS="$(echo "$ROW" | cut -d'|' -f2)"
AMOUNT_KOPECKS="$(echo "$ROW" | cut -d'|' -f3)"

echo "online_payment_id : ${ONLINE_PAYMENT_ID}"
echo "yookassa_payment_id: ${YK_ID}"
echo "current status     : ${STATUS}"

if [ "$STATUS" = "succeeded" ]; then
  echo "Already succeeded — nothing to do. (The PWA should already show 'Готово!'.)"
  exit 0
fi
if [ "$STATUS" != "pending" ]; then
  echo "FAIL: status is '${STATUS}', not 'pending' — refusing to force a non-pending payment." >&2
  echo "  (canceled/other states are terminal; this helper only confirms pending payments.)" >&2
  exit 1
fi

# Format amount as RUB string for the (informational) webhook body.
AMOUNT_RUB="$(awk -v k="${AMOUNT_KOPECKS:-0}" 'BEGIN{ printf "%.2f", k/100 }')"

# --- 2. Flush the Redis dedup key so the delivery is re-runnable ---
# SET NX EX 86400 short-circuits duplicate deliveries; flushing lets you re-fire.
# Also clear the legacy 'sz:' prefix in case an old build set it.
DEDUP_KEY="${DEDUP_PREFIX}payment.succeeded:${YK_ID}"
dc exec -T "$REDIS_SERVICE" redis-cli DEL "$DEDUP_KEY" >/dev/null 2>&1 || true
dc exec -T "$REDIS_SERVICE" redis-cli DEL "sz:yookassa:webhook:payment.succeeded:${YK_ID}" >/dev/null 2>&1 || true
echo "flushed dedup key  : ${DEDUP_KEY}"

# --- 3. Deliver the simulated payment.succeeded webhook ---
echo "+ POST ${BASE_URL}/api/v1/_internal/yookassa/webhook (payment.succeeded)"
BODY_FILE="$(mktemp)"
HTTP="$(curl -s -o "$BODY_FILE" -w '%{http_code}' -X POST \
  "${BASE_URL}/api/v1/_internal/yookassa/webhook" \
  -H 'Content-Type: application/json' \
  -d "{\"event\":\"payment.succeeded\",\"object\":{\"id\":\"${YK_ID}\",\"status\":\"succeeded\",\"amount\":{\"value\":\"${AMOUNT_RUB}\",\"currency\":\"RUB\"}}}")"
WEBHOOK_BODY="$(cat "$BODY_FILE")"; rm -f "$BODY_FILE"
echo "  HTTP ${HTTP}  body=${WEBHOOK_BODY}"

if [ "$HTTP" = "403" ]; then
  echo "FAIL: 403 forbidden_ip — the sandbox bypass is off." >&2
  echo "  Set YOOKASSA_SANDBOX=true in apps/backend/.env and restart the stack." >&2
  exit 1
fi
if [ "$HTTP" != "200" ] || [ "$WEBHOOK_BODY" != "ok" ]; then
  echo "FAIL: expected HTTP 200 + body 'ok', got HTTP ${HTTP} body '${WEBHOOK_BODY}'." >&2
  exit 1
fi

# --- 4. Confirm the transition landed (handler is synchronous) ---
NEW_STATUS="$(psql_q "SELECT status FROM online_payments WHERE id = '${ONLINE_PAYMENT_ID}'")"
echo "new status         : ${NEW_STATUS}"
if [ "$NEW_STATUS" != "succeeded" ]; then
  echo "WARN: webhook accepted (200 ok) but status is '${NEW_STATUS}', not 'succeeded'." >&2
  echo "  The handler re-fetches from the ЮKassa sandbox and trusts that status — the" >&2
  echo "  sandbox may not consider this payment succeeded. Check backend logs:" >&2
  echo "    docker compose -f \"$COMPOSE_FILE\" logs --tail=50 backend" >&2
  exit 1
fi

echo "✓ Payment ${ONLINE_PAYMENT_ID} confirmed (succeeded). The PWA poll will show 'Готово!' within ~3s."
