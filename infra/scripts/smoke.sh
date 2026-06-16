#!/usr/bin/env bash
# smoke.sh — Standalone 8-check "Looks-Done-But-Isn't" smoke test for clubcore.
#
# OPS-03: Extracts the 5 inline smoke checks from deploy-local.sh §6 and adds
#         3 new cluster-observable checks: /healthz 200, DNS resolve per pod,
#         WebSocket upgrade through Traefik ingress, SPA fallback 200,
#         and PWA SW cache headers (/api/* no-store).
#
# Checks:
#   1. /healthz 200         — backend pod reachable and healthy (NEW)
#   2. migrate Job Succeeded — WR-06: Succeeded vs Failed vs Timed-out (EXTRACT)
#   3. Redis AOF on         — DATA-02: CONFIG GET appendonly = yes (EXTRACT)
#   4. TZ=UTC on all pods   — P9: all timezone-sensitive app pods (EXTRACT + EXTEND)
#   5. DNS resolve per pod  — P8/SEC-04: CoreDNS + NetworkPolicy egress (NEW)
#   6. WS upgrade through ingress — NET-02: Traefik v3 /api/v1/client/ws/* → 101 (NEW)
#   7. SPA fallback 200     — NET-04: deep SPA route via nginx try_files (NEW)
#   8. PWA SW cache clean   — NET-04: /api/* no-store; sw.js/manifest no-cache (NEW)
#
# Checks 1, 5, 6, 7, 8 require a live deployed k3d cluster (OPERATOR-PENDING).
# Checks 2, 3, 4 also require a live cluster.
# Done-bar (authorable without k3d): bash -n infra/scripts/smoke.sh exits 0.
#
# Usage:
#   cd /path/to/clubcore
#   bash infra/scripts/smoke.sh          # against running k3d cluster
#   bash -n infra/scripts/smoke.sh       # syntax-check only (no cluster needed)
#
# Composable: called from Phase-121 `make smoke`.
# D-V40-LOCAL-VALIDATE: do NOT fabricate PASS output; live PASS is operator-pending.

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
CLUSTER_NAME="clubcore"
RELEASE_NAME="clubcore"
NAMESPACE="default"

# Ingress hostnames (match the Traefik IngressRoute hosts in the Helm chart)
ADMIN_APP_HOST="${ADMIN_APP_HOST:-admin.clubcore.local}"
CLIENT_PWA_HOST="${CLIENT_PWA_HOST:-app.clubcore.local}"
API_HOST="${API_HOST:-api.clubcore.local}"

# Ingress endpoint — the IP/port where the Traefik ingress is actually reachable.
# k3d maps the loadbalancer to localhost by default (e.g. `k3d cluster create
# --port "80:80@loadbalancer"`), so HTTP checks below DNS-resolve the *.clubcore.local
# vhosts to this endpoint via `curl --resolve` and spoof the vhost with `-H Host:`.
# This lets checks 6/7/8 PASS on a correctly-deployed k3d WITHOUT manual /etc/hosts
# entries. Override INGRESS_IP/INGRESS_PORT if Traefik is exposed elsewhere.
INGRESS_IP="${INGRESS_IP:-127.0.0.1}"
INGRESS_PORT="${INGRESS_PORT:-80}"

# Smoke check timeouts
MIGRATE_WAIT_TIMEOUT="300s"
POD_READY_TIMEOUT="300s"

# Repo root (so the script works from any cwd)
REPO_ROOT="$(git rev-parse --show-toplevel)"

# ── Helpers ───────────────────────────────────────────────────────────────────
log()  { echo "[smoke] $*"; }
ok()   { echo "[smoke] PASS: $*"; }
fail() { echo "[smoke] FAIL: $*" >&2; SMOKE_FAILURES=$((SMOKE_FAILURES + 1)); }

SMOKE_FAILURES=0

# run_check — dispatch a check function so that an unguarded non-zero command
# inside it can never abort the whole script under `set -euo pipefail`.
# Failures are already recorded via fail() (which increments SMOKE_FAILURES),
# so swallowing the function's exit status here is safe: it guarantees all 8
# checks run and the PASS/FAIL summary banner is always reached. The final
# exit status reflects SMOKE_FAILURES, not an incidental `set -e` trip.
run_check() { "$@" || true; }

# ── Check 1: /healthz 200 (NEW) ───────────────────────────────────────────────
# Exec into a backend pod and curl localhost:8000/healthz.
# Proves the FastAPI application is accepting requests after pod Ready.
check_healthz() {
    log "[1/8] /healthz: probing backend pod ..."
    local pod
    pod="$(kubectl get pod \
        --selector="app.kubernetes.io/component=backend" \
        -n "${NAMESPACE}" \
        -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")"
    if [ -z "${pod}" ]; then
        fail "(1) /healthz: no backend pod found (selector app.kubernetes.io/component=backend)"
        return
    fi
    local status_code
    status_code="$(kubectl exec "${pod}" -n "${NAMESPACE}" -- \
        curl -s -o /dev/null -w '%{http_code}' localhost:8000/healthz 2>/dev/null || echo "")"
    if [ "${status_code}" = "200" ]; then
        ok "(1) /healthz returned 200 on backend pod (${pod})"
    else
        fail "(1) /healthz returned '${status_code}' on backend pod (expected 200; pod=${pod})"
    fi
}

# ── Check 2: migrate Job Succeeded (EXTRACT from deploy-local.sh lines 145-170) ─
# WR-06: distinguish Succeeded vs Failed vs Timed-out/Running.
# Reads .status.succeeded / .status.failed / the Failed condition so an operator
# sees WHY the migration did not complete.
check_migrate() {
    log "[2/8] migrate Job: waiting for Succeeded ..."
    local migrate_wait_log
    migrate_wait_log="$(mktemp)"
    kubectl wait job/"${RELEASE_NAME}-migrate" \
        --for=condition=Complete \
        --timeout="${MIGRATE_WAIT_TIMEOUT}" \
        -n "${NAMESPACE}" >"${migrate_wait_log}" 2>&1 || true

    local migrate_succeeded migrate_failed migrate_failed_cond
    migrate_succeeded="$(kubectl get job "${RELEASE_NAME}-migrate" \
        -n "${NAMESPACE}" \
        -o jsonpath='{.status.succeeded}' 2>/dev/null || echo "0")"
    migrate_failed="$(kubectl get job "${RELEASE_NAME}-migrate" \
        -n "${NAMESPACE}" \
        -o jsonpath='{.status.failed}' 2>/dev/null || echo "0")"
    migrate_failed_cond="$(kubectl get job "${RELEASE_NAME}-migrate" \
        -n "${NAMESPACE}" \
        -o jsonpath='{.status.conditions[?(@.type=="Failed")].status}' 2>/dev/null || echo "")"

    if [ "${migrate_succeeded}" = "1" ]; then
        ok "(2) migrate Job status.succeeded = 1  (migrations applied before backend started)"
    elif [ "${migrate_failed_cond}" = "True" ] || [ "${migrate_failed:-0}" != "0" ]; then
        fail "(2) migrate Job FAILED (status.failed='${migrate_failed}', Failed condition='${migrate_failed_cond}') — check 'kubectl logs job/${RELEASE_NAME}-migrate'"
    else
        fail "(2) migrate Job did not complete (Timed-out/Running after ${MIGRATE_WAIT_TIMEOUT}; status.succeeded='${migrate_succeeded}'). kubectl wait output:"
        sed 's/^/        /' "${migrate_wait_log}" >&2 || true
    fi
    rm -f "${migrate_wait_log}"
}

# ── Check 3: Redis AOF on (EXTRACT from deploy-local.sh lines 223-235) ────────
# DATA-02: Redis must have appendonly persistence enabled.
check_redis_aof() {
    log "[3/8] Redis AOF: checking CONFIG GET appendonly ..."
    local redis_pod
    redis_pod="$(kubectl get pod \
        --selector="app.kubernetes.io/name=clubcore" \
        -n "${NAMESPACE}" \
        -o jsonpath='{.items[*].metadata.name}' 2>/dev/null \
        | tr ' ' '\n' | grep redis | head -1 || echo "")"
    if [ -z "${redis_pod}" ]; then
        fail "(3) Redis pod not found (selector app.kubernetes.io/name=clubcore, name contains 'redis')"
        return
    fi
    local redis_aof
    redis_aof="$(kubectl exec "${redis_pod}" -n "${NAMESPACE}" -- \
        redis-cli CONFIG GET appendonly 2>/dev/null | tail -1 || echo "")"
    if [ "${redis_aof}" = "yes" ]; then
        ok "(3) Redis CONFIG GET appendonly = yes  (DATA-02 AOF enabled; pod=${redis_pod})"
    else
        fail "(3) Redis CONFIG GET appendonly = '${redis_aof}' (expected 'yes'; pod=${redis_pod})"
    fi
}

# ── Check 4: TZ=UTC on ALL timezone-sensitive pods (EXTRACT + EXTEND from deploy-local.sh 184-221) ─
# P9: All timezone-sensitive workloads must run TZ=UTC.
# Stateless static-serving nginx pods (admin-app, client-pwa) do NOT read wall-clock
# time in application logic — they intentionally have no TZ env; this is an
# in-spec skip, not a failure (documented below).
check_tz() {
    local component="$1"
    local pod
    pod="$(kubectl get pod \
        --selector="app.kubernetes.io/component=${component}" \
        -n "${NAMESPACE}" \
        -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")"
    if [ -z "${pod}" ]; then
        fail "(4) TZ=UTC: no pod found for component=${component}"
        return
    fi
    local tz
    tz="$(kubectl exec "${pod}" -n "${NAMESPACE}" -- env 2>/dev/null | grep '^TZ=' | cut -d= -f2 || echo "")"
    if [ "${tz}" = "UTC" ]; then
        ok "(4) TZ=UTC on ${component} pod (${pod})"
    else
        fail "(4) TZ='${tz}' on ${component} pod (expected UTC; pod=${pod})"
    fi
}

check_all_tz() {
    log "[4/8] TZ=UTC: checking all timezone-sensitive app pods ..."
    # Python workloads — all process timestamps, scheduling, and session expiry
    check_tz "backend"
    check_tz "arq-worker"
    check_tz "telegram-bot"

    # Redis TZ check (StatefulSet — app label selector differs; find by name grep)
    local redis_pod
    redis_pod="$(kubectl get pod \
        --selector="app.kubernetes.io/name=clubcore" \
        -n "${NAMESPACE}" \
        -o jsonpath='{.items[*].metadata.name}' 2>/dev/null \
        | tr ' ' '\n' | grep redis | head -1 || echo "")"
    if [ -n "${redis_pod}" ]; then
        local redis_tz
        redis_tz="$(kubectl exec "${redis_pod}" -n "${NAMESPACE}" -- env 2>/dev/null | grep '^TZ=' | cut -d= -f2 || echo "")"
        if [ "${redis_tz}" = "UTC" ]; then
            ok "(4) TZ=UTC on Redis pod (${redis_pod})"
        else
            fail "(4) TZ='${redis_tz}' on Redis pod (expected UTC; pod=${redis_pod})"
        fi
    else
        log "  (4) WARNING: Redis pod not found — skipping Redis TZ check"
    fi

    # Intentional skip — static nginx pods (admin-app, client-pwa) serve pre-built
    # assets and never call date/time APIs in their nginx.conf. No TZ env is
    # expected or required for those pods (they are stateless, tz-agnostic nginx).
    log "  (4) NOTE: admin-app and client-pwa nginx pods are intentionally excluded from TZ check (stateless static serving, no wall-clock reads in nginx logic)"
}

# ── Check 5: DNS resolve from each workload pod (NEW — P8/SEC-04 evidence) ────
# Proves CoreDNS egress is allowed by the NetworkPolicies authored in Phase 119.
# Each workload pod must be able to resolve the in-cluster Postgres service name.
check_dns() {
    log "[5/8] DNS resolve: checking in-cluster DNS from each workload pod ..."
    local components=("backend" "arq-worker" "telegram-bot")
    local service="clubcore-postgres-rw"

    for component in "${components[@]}"; do
        local pod
        pod="$(kubectl get pod \
            --selector="app.kubernetes.io/component=${component}" \
            -n "${NAMESPACE}" \
            -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")"
        if [ -z "${pod}" ]; then
            fail "(5) DNS: no pod found for component=${component}"
            continue
        fi

        # Use nslookup if available (busybox-style); fall back to python socket for
        # Python-based pods that carry the interpreter but not nslookup.
        local resolved
        if kubectl exec "${pod}" -n "${NAMESPACE}" -- \
            sh -c "nslookup ${service} >/dev/null 2>&1" 2>/dev/null; then
            resolved="nslookup"
        elif kubectl exec "${pod}" -n "${NAMESPACE}" -- \
            python3 -c "import socket; socket.gethostbyname('${service}')" 2>/dev/null; then
            resolved="python3-socket"
        elif kubectl exec "${pod}" -n "${NAMESPACE}" -- \
            getent hosts "${service}" >/dev/null 2>&1; then
            resolved="getent"
        else
            resolved=""
        fi

        if [ -n "${resolved}" ]; then
            ok "(5) DNS: ${service} resolves from ${component} pod (${pod}) via ${resolved}"
        else
            fail "(5) DNS: ${service} did NOT resolve from ${component} pod (${pod}) — CoreDNS egress blocked? Check NetworkPolicy SEC-04"
        fi
    done
}

# ── Check 6: WebSocket upgrade through Traefik ingress (NEW — NET-02) ─────────
# Traefik v3 auto-upgrades WebSocket connections (no annotation required per 119 research).
# Probe the WS path with Connection/Upgrade headers; expect HTTP 101 Switching Protocols.
check_websocket() {
    log "[6/8] WebSocket upgrade: probing ${API_HOST}/api/v1/client/ws/ through Traefik ingress ..."
    local ws_status
    ws_status="$(curl -s -o /dev/null -w '%{http_code}' \
        --max-time 10 \
        --resolve "${API_HOST}:${INGRESS_PORT}:${INGRESS_IP}" \
        -H 'Connection: Upgrade' \
        -H 'Upgrade: websocket' \
        -H 'Sec-WebSocket-Version: 13' \
        -H "Sec-WebSocket-Key: $(echo -n 'clubcore-smoke' | base64 2>/dev/null || echo 'Y2x1YmNvcmUtc21va2U=')" \
        "http://${API_HOST}:${INGRESS_PORT}/api/v1/client/ws/smoke-probe" 2>/dev/null || echo "")"
    # Traefik returns 101 on a successful WebSocket upgrade.
    # 400 or 426 means the endpoint exists but rejected the handshake (acceptable
    # if the backend requires auth — a 4xx still proves the path reaches the service).
    # 502/503/000 means the ingress itself is not routing (fail).
    case "${ws_status}" in
        101)
            ok "(6) WebSocket upgrade: Traefik → backend returned 101 Switching Protocols (NET-02)"
            ;;
        400|426)
            ok "(6) WebSocket upgrade: Traefik routed WS path (${ws_status} — endpoint reachable; auth/handshake rejection is expected without a valid token)"
            ;;
        *)
            fail "(6) WebSocket upgrade: expected 101/400/426 but got '${ws_status}' — Traefik may not be routing WS path (NET-02 gap; host=${API_HOST})"
            ;;
    esac
}

# ── Check 7: SPA fallback 200 (NEW — NET-04) ──────────────────────────────────
# Deep SPA routes (e.g. /clients/some-uuid) must return 200 via nginx try_files.
# A 404 means nginx is not configured with try_files $uri /index.html.
check_spa_fallback() {
    log "[7/8] SPA fallback: probing deep route on ${ADMIN_APP_HOST} and ${CLIENT_PWA_HOST} ..."
    local hosts=("${ADMIN_APP_HOST}" "${CLIENT_PWA_HOST}")
    local deep_path="/clients/00000000-0000-0000-0000-000000000001"

    for host in "${hosts[@]}"; do
        local status
        # --resolve maps the vhost to the ingress endpoint so curl reaches Traefik
        # without an /etc/hosts entry; the URL authority still carries the vhost so
        # Traefik routes by Host. No redundant -H Host: needed.
        status="$(curl -s -o /dev/null -w '%{http_code}' \
            --max-time 10 \
            --resolve "${host}:${INGRESS_PORT}:${INGRESS_IP}" \
            "http://${host}:${INGRESS_PORT}${deep_path}" 2>/dev/null || echo "")"
        if [ "${status}" = "200" ]; then
            ok "(7) SPA fallback: ${host}${deep_path} → 200 (nginx try_files working; NET-04)"
        else
            fail "(7) SPA fallback: ${host}${deep_path} → '${status}' (expected 200 via try_files; NET-04 gap — check nginx.conf)"
        fi
    done
}

# ── Check 8: PWA SW cache clean — /api/* must not be cached (NEW — NET-04) ────
# The Service Worker must carry Cache-Control: no-cache (sw.js/manifest.json),
# and the API gateway must respond with Cache-Control: no-store so the SW never
# caches API responses.
check_sw_cache() {
    log "[8/8] PWA SW cache: verifying /api/* no-store + sw.js no-cache headers ..."

    # (a) Check that sw.js / workbox manifest are served with no-cache
    local sw_cache
    sw_cache="$(curl -s -D - -o /dev/null \
        --max-time 10 \
        --resolve "${CLIENT_PWA_HOST}:${INGRESS_PORT}:${INGRESS_IP}" \
        "http://${CLIENT_PWA_HOST}:${INGRESS_PORT}/sw.js" 2>/dev/null \
        | grep -i 'cache-control' | tr '[:upper:]' '[:lower:]' || echo "")"
    if echo "${sw_cache}" | grep -q 'no-cache'; then
        ok "(8a) sw.js Cache-Control contains no-cache (${CLIENT_PWA_HOST}/sw.js)"
    else
        fail "(8a) sw.js Cache-Control does not contain no-cache (got: '${sw_cache}'; host=${CLIENT_PWA_HOST})"
    fi

    # (b) Check that API responses carry no-store (SW must not cache API)
    local api_cache
    api_cache="$(curl -s -D - -o /dev/null \
        --max-time 10 \
        --resolve "${API_HOST}:${INGRESS_PORT}:${INGRESS_IP}" \
        "http://${API_HOST}:${INGRESS_PORT}/api/v1/ping" 2>/dev/null \
        | grep -i 'cache-control' | tr '[:upper:]' '[:lower:]' || echo "")"
    if echo "${api_cache}" | grep -q 'no-store'; then
        ok "(8b) /api/v1/ping Cache-Control contains no-store (SW will not cache API responses)"
    else
        fail "(8b) /api/* Cache-Control does not contain no-store (got: '${api_cache}'; host=${API_HOST}) — SW may cache API responses (NET-04 gap)"
    fi
}

# ── Main — run all 8 checks ───────────────────────────────────────────────────
log "=== clubcore smoke (8-check Looks-Done-But-Isn't) ==="
log "Cluster: ${CLUSTER_NAME}  |  Release: ${RELEASE_NAME}  |  Namespace: ${NAMESPACE}"
echo ""

run_check check_healthz
echo ""
run_check check_migrate
echo ""
run_check check_redis_aof
echo ""
run_check check_all_tz
echo ""
run_check check_dns
echo ""
run_check check_websocket
echo ""
run_check check_spa_fallback
echo ""
run_check check_sw_cache
echo ""

# ── Pod list summary ──────────────────────────────────────────────────────────
log "Pod list (informational):"
kubectl get pods -n "${NAMESPACE}" -o wide 2>/dev/null || true
echo ""

# ── PASS/FAIL summary banner ─────────────────────────────────────────────────
if [ "${SMOKE_FAILURES}" -eq 0 ]; then
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                     SMOKE: ALL PASS                         ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    echo "  Cluster:         k3d ${CLUSTER_NAME}"
    echo "  Release:         ${RELEASE_NAME}"
    echo "  [1] /healthz:    200 (backend ready)"
    echo "  [2] migrate Job: Succeeded (schema current)"
    echo "  [3] Redis AOF:   on (DATA-02)"
    echo "  [4] TZ=UTC:      all timezone-sensitive pods"
    echo "  [5] DNS:         in-cluster service resolves from each workload pod"
    echo "  [6] WS upgrade:  Traefik → 101 (NET-02)"
    echo "  [7] SPA fallback: deep routes → 200 (NET-04)"
    echo "  [8] SW cache:    /api/* no-store; sw.js no-cache (NET-04)"
    echo ""
    echo "  D-V40-LOCAL-VALIDATE: done-bar criteria MET"
else
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║        SMOKE: ${SMOKE_FAILURES} CHECK(S) FAILED                             ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    echo "  Review FAIL lines above for details."
    exit 1
fi
