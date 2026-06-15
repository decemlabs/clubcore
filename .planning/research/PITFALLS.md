# Pitfalls Research

**Domain:** Self-hosted bare-metal k3s — containerizing and deploying an existing full-stack gym CRM (FastAPI + ARQ + Telegram long-polling + Postgres 16 + Redis 7 + SeaweedFS/MinIO + two SPA/PWA frontends)
**Researched:** 2026-06-16
**Confidence:** HIGH

---

## Critical Pitfalls

### Pitfall 1: Postgres data loss on StatefulSet rescheduling (bare-metal k3s, local-path-provisioner)

**What goes wrong:**
k3s ships with `local-path-provisioner` as its default storage class. This creates PVs that are node-affinity-bound — the PV is created in a specific directory on a specific node. If the StatefulSet pod is rescheduled to a different node (node drain, node failure, operator `kubectl delete pod`), the new pod cannot bind the old PV because the path does not exist on the new node. The pod stays Pending forever, or worse — if the PVC is recreated — a fresh empty volume is mounted and the new pod starts with no data.

**Why it happens:**
Developers apply a StatefulSet with a `volumeClaimTemplate` and assume Postgres data persists like a named Docker volume does in `docker compose`. Local-path PVs have no cross-node mobility. On a true single-node bare-metal server this is survivable; it becomes a silent trap when any node maintenance or k3s upgrade causes a pod reschedule.

**How to avoid:**
1. Annotate the PVC with `volumeBindingMode: WaitForFirstConsumer` and verify the pod lands back on the same node via a `nodeSelector` or `nodeName` constraint pinning Postgres to the storage node.
2. Set `terminationGracePeriodSeconds: 60` on the StatefulSet pod so Postgres flushes WAL cleanly before SIGKILL.
3. Label the storage node explicitly (`kubectl label node <name> clubcore/postgres-storage=true`) and use a `nodeSelector` in the StatefulSet spec.
4. Before trusting any PVC, execute a full `pg_dump` → destroy pod → `pg_restore` round-trip in the kind/k3s local validation environment. Document the restore time.
5. Set `reclaimPolicy: Retain` on the StorageClass so a PVC delete does NOT destroy the underlying directory.

**Warning signs:**
- Pod shows `Pending` after a reschedule with event `0/1 nodes are available: 1 node(s) didn't match Pod's node affinity/selector`.
- PVC shows `Lost` binding.
- A second PVC with the same name appears with status `Bound` but different PV.

**Phase to address:**
K8s manifests / Helm phase (StatefulSet authoring); Backup & Recovery phase (restore round-trip test).

---

### Pitfall 2: ARQ cron DOUBLE-FIRE if the worker Deployment scales to replicas > 1 (or during rolling update overlap)

**What goes wrong:**
ARQ `unique=True` on a `cron()` entry uses a Redis `SET NX EX` lock keyed on the job name + scheduled time. If two worker pods are alive simultaneously (replicas=2, or during a RollingUpdate where new pod starts before old pod terminates), BOTH pods race to acquire the lock. The loser gets a cache miss for that tick and silently enqueues a second copy of the same cron job into the queue. A second worker then dequeues and executes it. The SQL-level idempotency gates (`WHERE status='active'`, `ON CONFLICT DO NOTHING`) are the real backstop — but `charge_expiring_autopay` initiates real YooKassa API calls and `dispatch_fiscal_receipt` sends real fiscal receipts; SQL-level dedup only prevents the DB row, it does NOT prevent the external API call from firing twice.

**Why it happens:**
Kubernetes `Deployment` default strategy is `RollingUpdate` with `maxSurge=1`. During a deploy, both old and new pods exist simultaneously. Neither pod knows about the other; the ARQ lock is per-pod-race with a 60-second TTL (`keep_result=60`). If the cron fires during the overlap window, both pods see the lock absent and both attempt enqueue.

**How to avoid:**
1. Set `strategy: type: Recreate` on the ARQ worker Deployment. This ensures the old pod is fully terminated before the new one starts — zero overlap window.
2. Keep `replicas: 1` on the ARQ worker Deployment permanently. There must be exactly one ARQ scheduler instance. Document this as an architectural invariant in the Helm values.
3. Do NOT use a HorizontalPodAutoscaler on the ARQ worker.
4. Set `maxSurge: 0, maxUnavailable: 1` if Recreate strategy seems too strong (but Recreate is preferred — brief unavailability of the scheduler is acceptable; double-fire of autopay is not).
5. The existing `WorkerSettings.on_startup` assertion (`cron_function_names - function_names`) already catches the "cron registered but not in functions" trap at boot. Keep it.

**Warning signs:**
- Two ARQ worker pods running simultaneously (check `kubectl get pods -l app=arq-worker`).
- Duplicate `expire_memberships_complete` log lines within the same minute window in Loki.
- `autopay_charges` table showing two rows for the same `(membership_id, period_end)` pair where the second hit `ON CONFLICT` — the conflict itself is evidence a double-fire occurred.

**Phase to address:**
K8s manifests / Helm phase (Deployment strategy + replicas constraint); documented as an acceptance criterion in the ARQ worker manifest.

---

### Pitfall 3: Telegram long-polling with replicas > 1 (or RollingUpdate overlap) — double-consume

**What goes wrong:**
The Telegram Bot API long-polling model delivers each update ONCE to the poller that calls `getUpdates`. If two `telegram_bot` worker pods are alive simultaneously, both call `getUpdates` to Telegram's API. Telegram will alternate deliveries between the two connections (or drop one). The result is that some updates are processed twice (by both pods racing) and others are dropped (delivered to the pod that did not handle them). `/checkin`, `/book`, and `/start` handlers are idempotent at the DB level but the Telegram bot API does not deduplicate — users receive duplicate confirmation DMs.

**Why it happens:**
Same rolling-update overlap issue as Pitfall 2, but for the Telegram bot there is no Redis lock mechanism at all. The long-polling contract assumes exactly one consumer.

**How to avoid:**
1. Set `strategy: type: Recreate` on the telegram-bot Deployment. This is the only safe strategy for long-polling bots.
2. Set `replicas: 1` permanently. Document this constraint in the Helm values and the runbook.
3. Add a readiness probe that checks the Telegram bot token validity on startup — this prevents the new pod from accepting traffic before it is confirmed healthy, but the critical fix is Recreate strategy.
4. Set `terminationGracePeriodSeconds: 30` so the old pod can drain in-flight `getUpdates` cleanly before SIGKILL.

**Warning signs:**
- Two `telegram-bot` pods showing `Running` simultaneously.
- Users reporting double confirmation DMs for `/checkin` or `/book`.
- Structlog shows the same `update_id` processed in two different pod log streams.

**Phase to address:**
K8s manifests / Helm phase (Deployment strategy + replicas constraint for telegram-bot).

---

### Pitfall 4: Migrate Job races API/worker boot — API starts before Alembic finishes

**What goes wrong:**
The Alembic migrate job (~70 migrations) takes several seconds. If the API Deployment and the migrate Job are created simultaneously by `helm install` or `kubectl apply`, the API pod may pass its readiness probe and start serving requests before the `alembic upgrade head` completes. The first request that touches a new column or table fails with a Postgres `column does not exist` error, surfacing as a 500 to users.

**Why it happens:**
Kubernetes applies all resources in a chart in one pass. Without an explicit ordering gate, pods race. Helm hooks (`pre-upgrade`, `pre-install`) on the Job are the standard fix, but they interact badly with `helm upgrade --atomic` if not configured carefully.

**How to avoid:**
1. Declare the migrate Job as a Helm pre-install + pre-upgrade hook: `"helm.sh/hook": pre-install,pre-upgrade` and `"helm.sh/hook-weight": "-5"`. Helm will wait for the Job to complete before deploying the rest of the chart.
2. Alternatively, use an `initContainer` on the API pod that runs `alembic upgrade head` — but this has a downside: every pod restart re-runs migrations (safe because Alembic is idempotent, but slower startup).
3. Helm hook approach is preferred: single migration execution, clear separation, does not add startup latency to the API on every restart.
4. Add `"helm.sh/hook-delete-policy": before-hook-creation` so the Job is cleaned up before the next deploy creates a new one (avoids Job name collision).
5. Set `activeDeadlineSeconds` on the Job (e.g., 300) so a stuck migration does not block helm forever.
6. In the `alembic.ini` / `env.py`, set `connection_retries` or wrap the `run_migrations_online` in a retry loop for the DB connection (k3s may take a few seconds to provision the Postgres service endpoint on first install).

**Warning signs:**
- API pod logs show `column "X" of relation "Y" does not exist` within the first 30 seconds of deployment.
- Helm upgrade hangs at `Waiting for hook to complete`.
- `kubectl get jobs` shows migrate Job in `Active` state for longer than 60 seconds.

**Phase to address:**
K8s manifests / Helm phase (Job + hook ordering); Containerization phase (Dockerfile CMD does NOT run migrations — migrate is a separate image CMD).

---

### Pitfall 5: Redis data loss on restart — sessions, ARQ queue, WebSocket pub/sub lost

**What goes wrong:**
Redis 7 by default uses RDB snapshots with a save interval (e.g., `save 900 1, save 300 10, save 60 10000`). Between snapshots, data in RAM is not durable. A pod eviction, OOMKill, or node reboot loses up to `save_interval` seconds of data. For clubcore this means: all active JWT sessions logged out, all rate-limit counters reset, all idempotency keys lost (replay window opens), ARQ job queue emptied (in-flight tasks lost, cron locks gone), and the Redis pub/sub channel for WebSocket chat fan-out torn down (connected clients need to reconnect).

**Why it happens:**
Redis defaults are optimized for cache use, not durable queues. In a k8s pod, the PVC for Redis is a separate concern from the in-memory state; if the pod is killed ungracefully (OOMKill), data between the last RDB snapshot and the kill is gone.

**How to avoid:**
1. Enable AOF persistence: `appendonly yes`, `appendfsync everysec` in the Redis ConfigMap. This reduces data loss to ~1 second in the worst case.
2. Mount a PVC for Redis (`/data`). Use `local-path-provisioner` with node affinity (same caution as Postgres — Pitfall 1).
3. Set `maxmemory` in the ConfigMap to ~75% of the pod's memory limit, and `maxmemory-policy: allkeys-lru`. WITHOUT `maxmemory`, Redis will grow until the pod hits its memory limit and is OOMKilled — which triggers the data loss scenario. With `allkeys-lru`, Redis evicts least-recently-used keys under pressure rather than crashing. NOTE: ARQ job queue keys should ideally not be evicted; if the queue is critical, use `maxmemory-policy: volatile-lru` with TTLs only on cache keys, and no TTL on queue keys.
4. Set `save ""` in the ConfigMap to DISABLE RDB snapshots (to avoid a snapshot blocking the event loop) and rely solely on AOF.
5. Set `terminationGracePeriodSeconds: 30` on the Redis pod so it has time to flush AOF on SIGTERM.
6. Set resource limits with enough headroom: if the pod's memory limit equals the Redis dataset size, OOMKill is guaranteed.

**Warning signs:**
- After pod restart, all staff are logged out simultaneously (session keys gone).
- ARQ cron jobs that should have fired at 06:05 MSK did not fire (queue empty after restart).
- WebSocket chat clients all disconnect simultaneously and cannot reconnect immediately (pub/sub channels torn down).
- Redis logs show `BGSAVE` taking >1 second (sign that the dataset is too large for the RDB snapshot interval).

**Phase to address:**
K8s manifests / Helm phase (Redis StatefulSet + ConfigMap + PVC); Monitoring phase (alert on `redis_connected_clients` drop to 0).

---

### Pitfall 6: Sealed Secrets controller key loss with no git remote

**What goes wrong:**
Sealed Secrets encrypts k8s Secrets against the controller's RSA key pair stored in a k8s Secret in the `kube-system` namespace. If the k3s cluster is rebuilt (node reinstalled, cluster reset), the controller generates a NEW key pair. All existing SealedSecret objects in the repo become permanently undecryptable — the controller cannot unseal them with the new key. Since this project has no git remote and no off-node backup of the key, the controller key exists only on the node. Node failure + cluster rebuild = all secrets permanently lost.

**Why it happens:**
Sealed Secrets is designed for GitOps where you push SealedSecrets to a remote repo and the controller key is backed up separately. Without a git remote and without an explicit controller key backup, the key lives only in the cluster's etcd (k3s SQLite/etcd backend), which lives on the node.

**How to avoid:**
1. After installing the Sealed Secrets controller, immediately export the controller key: `kubectl get secret -n kube-system -l sealedsecrets.bitnami.com/sealed-secrets-key -o yaml > .private/sealed-secrets-controller-key.yaml`. Store this file OFF-NODE (external drive, second PC — the existing backup method is copying the repo to another PC; add this file to that backup).
2. Document the restore procedure: `kubectl apply -f .private/sealed-secrets-controller-key.yaml` before reinstalling the controller. If the old key is present at controller startup, it uses it instead of generating a new one.
3. ALTERNATIVE: Use SOPS + age instead of Sealed Secrets. The age private key is a single file that is easier to back up and is independent of the cluster. The age key goes into the same off-node backup. SOPS-encrypted files are decryptable on any machine with the age key, without a running cluster — useful for disaster recovery.
4. NEVER commit the age private key or the Sealed Secrets controller key to the git repo. Put them in `.gitignore` and the off-node backup.
5. Test the full unseal round-trip during local validation: destroy the kind cluster, restore the controller key, re-create the cluster, verify all SealedSecrets decrypt successfully.

**Warning signs:**
- `kubectl get sealedsecrets -A` shows `Error decrypting key` events.
- Application pods crash with missing environment variables (secret mount fails silently or with `CreateContainerConfigError`).
- Sealed Secrets controller logs: `no key could decrypt secret`.

**Phase to address:**
Security phase (secrets management + controller key backup procedure); Documentation phase (runbook must include "before cluster rebuild, backup the controller key").

---

### Pitfall 7: k3s Traefik ingress quirks — WebSocket, TLS cert-manager rate limits, and HTTP-to-HTTPS redirect loops

**What goes wrong (three sub-traps):**

**7a. WebSocket through Traefik requires explicit annotation.**
The FastAPI WebSocket endpoint for chat (`/api/v1/ws/chat/{thread_id}`) requires HTTP Upgrade. Traefik does NOT proxy WebSocket connections by default on IngressRoutes without the proper configuration. Connections silently upgrade then immediately close, appearing as a 400 or 101 followed by 0 bytes.

**7b. Let's Encrypt production rate limits — use staging first.**
If you point cert-manager's ClusterIssuer directly at `acme.lets-encrypt.org` (production), you get 5 failed validation attempts per hostname per hour before a 1-hour lockout, and 50 certificates per registered domain per week. During iterative local validation where you destroy and recreate the cluster repeatedly, you will hit the rate limit on the first real-hostname attempt. A staging cert (`acme-staging-v02.api.letsencrypt.org`) does not have this limit but produces a self-signed-CA cert (not trusted by browsers). For local validation use staging or a self-signed CA; switch to production only on the final live deploy.

**7c. HTTP to HTTPS redirect loops with TLS termination at ingress.**
If the ingress terminates TLS and also has a redirect middleware that redirects HTTP to HTTPS, AND the backend also redirects HTTP to HTTPS (e.g., `FORWARDED_ALLOW_IPS` not set, so FastAPI/uvicorn sees HTTP and redirects again), clients get an infinite redirect loop.

**How to avoid:**
1. For WebSocket: configure the IngressRoute with a dedicated route for `/api/v1/ws/` using the websocket service port. Test with `wscat` through the ingress during local validation.
2. For TLS: use a staging ClusterIssuer for all local and iterative testing. Only switch to production issuer on the operator-pending live deploy step.
3. For redirect loops: set `FORWARDED_ALLOW_IPS=*` (or the cluster CIDR) in the backend ConfigMap so uvicorn respects the `X-Forwarded-Proto: https` header from Traefik and does not issue its own redirect.
4. Know that k3s Traefik is v2.x (not nginx-ingress) — `nginx.ingress.kubernetes.io/*` annotations are silently ignored. All Traefik-specific annotations use the `traefik.ingress.kubernetes.io/*` prefix.

**Warning signs:**
- WebSocket connections drop immediately with `101 Switching Protocols` followed by connection close in browser devtools.
- `kubectl describe certificate` shows `Issuing` state for >5 minutes.
- cert-manager logs: `429 Too Many Requests` from Let's Encrypt.
- Browser shows `ERR_TOO_MANY_REDIRECTS`.

**Phase to address:**
Networking phase (Traefik ingress configuration + WebSocket annotation + TLS staging/production split); Documentation phase (operator-pending: switch to LE production issuer).

---

### Pitfall 8: NetworkPolicy denying CoreDNS — pod DNS resolution fails silently

**What goes wrong:**
When you apply a `deny-all` default NetworkPolicy and then add allow rules for specific traffic, it is easy to forget to allow egress from application pods to CoreDNS (`kube-system` namespace, port 53 UDP/TCP). The result: all DNS lookups inside the pod fail with `NXDOMAIN` or timeout. Python's `asyncpg` and `httpx` and `python-telegram-bot` all use DNS resolution for their connection strings. The application starts, logs no DNS error, but every outbound connection eventually times out because the hostname never resolves. This is particularly insidious because pods APPEAR healthy (liveness probe against `localhost:8000/healthz` passes), but all real traffic fails.

**Why it happens:**
NetworkPolicy is additive-deny: if a policy selects a pod, ALL traffic not explicitly allowed is dropped. CoreDNS lives in `kube-system` and must be explicitly allowed in egress rules. Prometheus scraping requires ingress from the `monitoring` namespace. These are the most commonly forgotten allow rules.

**How to avoid:**
1. Add a standard egress rule to ALL application pod NetworkPolicies: `to: [{namespaceSelector: {matchLabels: {kubernetes.io/metadata.name: kube-system}}, podSelector: {matchLabels: {k8s-app: kube-dns}}}], ports: [{protocol: UDP, port: 53}, {protocol: TCP, port: 53}]`.
2. Add a Prometheus scrape ingress rule: `from: [{namespaceSelector: {matchLabels: {kubernetes.io/metadata.name: monitoring}}}], ports: [{port: 8000}]`.
3. Add inter-pod egress rules: backend to postgres, backend to redis, arq-worker to redis, arq-worker to postgres, telegram-bot to redis, telegram-bot to postgres. Be explicit about namespaces and pod selectors.
4. Test NetworkPolicies with `kubectl exec <pod> -- nslookup postgres-svc` and `kubectl exec <pod> -- curl http://redis-svc:6379` before declaring networking done.
5. Apply NetworkPolicies LAST in the phase, after all services are confirmed reachable without them.

**Warning signs:**
- Pod logs show connection timeouts to Postgres/Redis hostnames (not refused — timeout means DNS failed, not the service).
- `kubectl exec <pod> -- nslookup google.com` hangs.
- Python stack traces show `asyncio.TimeoutError` or `getaddrinfo failed` on DB connection strings.
- Prometheus shows no targets in the scrape pool for clubcore pods.

**Phase to address:**
Networking phase (NetworkPolicy authoring); must include a DNS-resolution smoke test in the local validation checklist.

---

### Pitfall 9: Image pitfalls — non-root + filesystem writes, missing tzdata, uv/venv path, :latest tags

**What goes wrong (four sub-traps):**

**9a. Non-root user + filesystem writes.**
The existing Dockerfile creates a non-root `app` user (UID typically ~999). If any code path writes to a path outside `/app` or `/tmp` (e.g., a temp file written to `/var/`, a log file to `/etc/`), it will fail with `Permission denied` in the container but work fine in `docker compose` where the image ran as root. The migrate job runs `alembic upgrade head` — Alembic writes `alembic/versions/__pycache__` at import time; if the `/app/alembic` directory is owned by root in the builder stage and not re-chowned in the runtime stage, the migrate container will crash.

The current Dockerfile uses `COPY --from=builder --chown=app:app /app /app` which chowns ALL of `/app` including `/app/alembic` — this is correct. Verify this chown is not dropped in a future Dockerfile edit.

**9b. Missing tzdata.**
`python:3.12-slim-bookworm` does NOT include `tzdata`. The cron jobs use `TZ=UTC` container environment and Python's `ZoneInfo("Europe/Moscow")`. `ZoneInfo` on Python 3.9+ with `tzdata` PyPI package works without system `tzdata`. Verify the `pyproject.toml` includes `tzdata` as a dependency, or install it in the Dockerfile. If absent, `ZoneInfo("Europe/Moscow")` raises `ZoneInfoNotFoundError` at runtime — but only when the code path that constructs the zone object is first called, not at import time. This means the bug appears at 03:05 UTC when `expire_memberships` fires for the first time, not at startup.

**9c. uv/venv PATH.**
The existing Dockerfile correctly sets `ENV PATH="/app/.venv/bin:$PATH"`. If this ENV line is missing from the runtime stage (e.g., copied from a different template), `python` and `uvicorn` and `alembic` resolve to the system Python which does not have the project dependencies installed. The pod starts but immediately exits with `ModuleNotFoundError`.

**9d. :latest tags.**
Using `image: clubcore-backend:latest` in Helm values means every `helm upgrade` pulls whatever is currently tagged `latest` in the local image registry. In the no-registry LOCAL setup (Makefile build + `k3s ctr images import`), `:latest` is safe because you control the tag. The risk is using `:latest` in a future registry-backed setup where a different image gets tagged `latest` accidentally. Use explicit version tags (git SHA or semver) from day one.

**How to avoid:**
1. Verify `COPY --from=builder --chown=app:app /app /app` covers all directories the non-root user needs to write to at runtime.
2. Add `tzdata` to `pyproject.toml` dependencies (or verify it is already present).
3. Smoke-test the image with `docker run --user app clubcore-backend python -c "from zoneinfo import ZoneInfo; ZoneInfo('Europe/Moscow')"` before deploying.
4. Use git-SHA tags for all images from day one: `image: clubcore-backend:$(git rev-parse --short HEAD)`.
5. Pin base images by digest in the Dockerfile: `FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim@sha256:<digest> AS builder`.

**Warning signs:**
- Migrate pod exits immediately with `ModuleNotFoundError: No module named 'alembic'`.
- ARQ worker crashes at 03:05 UTC with `ZoneInfoNotFoundError`.
- `kubectl exec <pod> -- id` shows UID 0 (image running as root unexpectedly — means USER directive was dropped).

**Phase to address:**
Containerization phase (Dockerfile hardening + tzdata + chown audit); K8s manifests phase (image tag convention).

---

### Pitfall 10: PWA service worker caching /api/* + nginx SPA fallback missing

**What goes wrong:**
`apps/client-pwa` has a service worker (`gym-v3`) that caches assets. If the nginx serving the PWA sets `Cache-Control: max-age=86400` on ALL paths (a common nginx static-site pattern), and if the service worker's fetch handler does not explicitly exclude `/api/*`, the SW will cache API responses and serve stale data to clients. More concretely: if someone accidentally adds `/api/v1/...` to the precache manifest, users see stale membership data offline. The existing SW comment says "SW (`gym-v3`) never caches `/api/*`" — but this depends on the nginx configuration not sending a Cache-Control header that confuses the SW, AND on the SW code being preserved correctly in the production build.

The nginx SPA fallback pattern `try_files $uri $uri/ /index.html` is required for client-side routing (TanStack Router). Without it, direct navigation to `/plans` returns 404 from nginx.

**How to avoid:**
1. nginx server block for the PWA must include: `location /api/ { proxy_pass http://backend-svc:8000; }` (requests to `/api/*` must be proxied to the backend, not served from static files).
2. nginx config must NOT set `Cache-Control` headers on the service worker file itself (`/sw.js`, `/gym-v3.js`): `location ~* sw\.js$ { add_header Cache-Control "no-cache"; }` for the SW entry point; immutable cache is fine for hashed assets (`/assets/*.js`).
3. The `try_files $uri $uri/ /index.html` rule must be in BOTH the admin-app nginx block AND the client-pwa nginx block.
4. Verify during local validation with a browser `Application > Service Workers > Offline` toggle that `/api/*` requests are NOT served from cache.
5. Add a `Cache-Control: no-store` header on all `/api/*` responses from the FastAPI backend.

**Warning signs:**
- Direct navigation to `/plans` returns 404 instead of the SPA.
- After a deploy, users still see old data (SW served a cached API response).
- Service worker shows `api/v1/...` in `Cache Storage` in devtools.

**Phase to address:**
Containerization phase (nginx config for frontend images); local validation must include a browser smoke test for SPA routing and service worker behavior.

---

### Pitfall 11: Resource limits, OOMKill, and slow-starting pods killed by liveness probes

**What goes wrong (two sub-traps):**

**11a. OOMKill from no memory limit or wrong limit.**
Without `resources.limits.memory`, a pod can grow unboundedly and trigger the node's OOM killer — the entire node may kill processes rather than just the pod. Postgres without `shared_buffers` tuning will try to use 25% of system RAM; in a container with a 512Mi limit and `shared_buffers=128MB`, this is fine; without a limit, Postgres grows to exhaust the node. Redis without `maxmemory` (see Pitfall 5) will OOMKill itself.

**11b. Liveness probes killing pods during slow startup.**
The backend API boots by: importing all Python modules (slow on first start, ~3-5 seconds with ~70 Alembic migrations in metadata), running lifespan managers for Redis and database, registering all protocol slots. If `initialDelaySeconds` on the liveness probe is too short, the probe fires before the app is ready, the pod is killed, restarted, killed again — crash loop. A `startupProbe` with a generous `failureThreshold` (e.g., 30 attempts x 5 second period = 150 seconds) is the correct pattern: the startup probe runs until success, then liveness/readiness take over.

**How to avoid:**
1. Set `resources.requests` and `resources.limits` on every pod. Suggested starting values (tune after observing actual usage via Prometheus):
   - `backend`: requests `cpu: 100m, memory: 256Mi`, limits `cpu: 500m, memory: 512Mi`
   - `arq-worker`: requests `cpu: 50m, memory: 128Mi`, limits `cpu: 300m, memory: 384Mi`
   - `telegram-bot`: requests `cpu: 25m, memory: 128Mi`, limits `cpu: 200m, memory: 256Mi`
   - `postgres`: requests `cpu: 200m, memory: 512Mi`, limits `cpu: 1000m, memory: 1Gi`
   - `redis`: requests `cpu: 50m, memory: 128Mi`, limits `cpu: 200m, memory: 256Mi`
2. Use a `startupProbe` that hits `/healthz`: `initialDelaySeconds: 5, periodSeconds: 5, failureThreshold: 30`. Only after the startup probe passes do liveness and readiness probes engage.
3. Set Postgres `command: ["postgres", "-c", "shared_buffers=256MB", "-c", "max_connections=50"]` in the StatefulSet — the defaults are tuned for large servers, not k8s pods.

**Warning signs:**
- Pod shows `OOMKilled` in `kubectl describe pod`.
- Pod restart count climbing in `kubectl get pods` (CrashLoopBackOff).
- `kubectl logs <pod> --previous` shows the pod was killed mid-startup with no error — the liveness probe killed it before `uvicorn` printed its first request log.
- `kubectl describe pod` shows `Liveness probe failed: connection refused` during the first 30 seconds.

**Phase to address:**
K8s manifests / Helm phase (resource limits + startup/liveness/readiness probes); Monitoring phase (OOMKill alert).

---

### Pitfall 12: UTC/MSK timezone: cron fires at wrong wall-clock time, gym_date STORED column miscomputed

**What goes wrong:**
The ARQ cron jobs use UTC-based `hour=` arguments that are manually offset from MSK (e.g., `hour=3, minute=5` = 06:05 MSK = 03:05 UTC). If the deployment environment sets `TZ=Europe/Moscow` on the ARQ worker container (e.g., by copying a compose env file that has this), the cron fires 3 hours late relative to MSK. The `gym_date STORED` column is computed by Postgres using `AT TIME ZONE 'Europe/Moscow'` — if the Postgres container's timezone is changed from UTC, the STORED generated column value is wrong for rows inserted before the change. All uniqueness constraints on `gym_date` break.

**Why it happens:**
`docker-compose.yml` may have `TZ=Europe/Moscow` on some services for developer convenience. When copying env configs to k8s ConfigMaps/Secrets, TZ values are carried over.

**How to avoid:**
1. All containers MUST run `TZ=UTC`. This is the locked Phase 15 Key Decision. Verify it in every ConfigMap and every Helm values template.
2. Set `timezone = 'UTC'` in the Postgres ConfigMap to ensure the STORED column computation is consistent.
3. The ARQ worker `__init__.py` documents the UTC offset for every cron job. Do NOT change these offsets when deploying — they are correct as-is.
4. Run `SELECT NOW() AT TIME ZONE 'Europe/Moscow'` inside the Postgres pod after deployment to verify the MSK wall-clock is correct.

**Warning signs:**
- `expire_memberships_complete count=0` at 03:05 UTC (correct) but also a second fire at 06:05 UTC (TZ was set to Moscow on the worker).
- `gym_date` uniqueness violations (`duplicate key value violates unique constraint "uq_visits_client_gym_date"`) for visits inserted after a timezone change.

**Phase to address:**
K8s manifests / Helm phase (TZ=UTC in all ConfigMaps); local validation checklist must include `kubectl exec arq-worker -- env | grep TZ`.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| `image: :latest` in Helm values | No version management needed | Uncontrolled rollouts; rollback is `helm rollback` but you don't know what image you're rolling back to | Never — use git SHA from day one |
| Skipping `resources.limits` | Simpler Helm values | Node-level OOMKill; Postgres eats all RAM; k3s becomes unresponsive | Never on stateful pods; only acceptable for one-off debug pods |
| Single ClusterIssuer pointing at LE production | No staging/production distinction | Rate-limit lockout during iterative testing | Never during local validation; production only on final live deploy |
| Skipping NetworkPolicies | Faster initial setup | Any compromised pod can reach Postgres directly | Acceptable in local validation only; must be applied before any external exposure |
| RDB-only Redis (no AOF) | Simpler config | Up to 15 minutes of session/queue data lost on crash | Acceptable in local validation environment only |
| Recreate strategy on ALL Deployments | Simpler than tuning RollingUpdate | Brief downtime on deploy (~10-30 seconds for backend) | Acceptable for pet project — zero-downtime is a future concern; ARQ/bot REQUIRE Recreate regardless |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Traefik (k3s built-in) | Using `nginx.ingress.kubernetes.io/` annotations | Use `traefik.ingress.kubernetes.io/` annotations or IngressRoute CRD |
| cert-manager + Let's Encrypt | Pointing at production ACME immediately | Use staging issuer during all iterative testing; switch to production on final live deploy only |
| Sealed Secrets | Assuming controller key is in etcd backup | Explicitly export and back up the controller key immediately after installation |
| ARQ + Redis | Assuming `unique=True` prevents all double-fires | `unique=True` is a per-tick Redis lock; Recreate strategy + replicas=1 is the real prevention |
| FastAPI + Traefik TLS | uvicorn redirecting HTTP to HTTPS behind an HTTPS ingress | Set `FORWARDED_ALLOW_IPS` to trust Traefik's X-Forwarded-Proto header |
| Alembic in k8s | Running migrations as initContainer on every pod | Use a Helm pre-install/pre-upgrade hook Job; one migration per deploy, not one per pod restart |
| SeaweedFS/MinIO | Assuming the bucket is created on first use | Bucket bootstrap must happen in a Job or the API startup sequence; the existing `ensure_bucket` call in `main.py` handles this — verify it runs before message attachment uploads |

---

## "Looks Done But Isn't" Checklist

- [ ] **Postgres PVC:** `reclaimPolicy: Retain` verified on the StorageClass — a `kubectl delete pvc` should NOT delete the underlying data directory.
- [ ] **Redis AOF:** `kubectl exec redis -- redis-cli config get appendonly` returns `yes`.
- [ ] **Backup restore round-trip:** A `pg_dump` has been taken, the Postgres pod has been deleted and recreated from scratch, and `pg_restore` produced a working database — not just a successful command exit.
- [ ] **Telegram bot replicas:** `kubectl get deployment telegram-bot -o jsonpath='{.spec.replicas}'` returns `1` and `kubectl get deployment telegram-bot -o jsonpath='{.spec.strategy.type}'` returns `Recreate`.
- [ ] **ARQ worker replicas:** Same check as above for `arq-worker`.
- [ ] **Migrate runs before API:** Helm hook ordering verified by `helm template | grep "helm.sh/hook"` — migrate Job shows `pre-install,pre-upgrade`.
- [ ] **DNS resolution:** `kubectl exec backend-pod -- nslookup postgres-svc` succeeds.
- [ ] **WebSocket through ingress:** `wscat -c wss://<hostname>/api/v1/ws/chat/test` establishes connection.
- [ ] **SPA fallback routing:** Direct navigation to `https://<hostname>/plans` (admin-app) and `https://<hostname>/book` (client-pwa) returns 200, not 404.
- [ ] **PWA service worker:** Browser devtools > Application > Cache Storage shows NO `/api/*` entries.
- [ ] **TZ=UTC on all pods:** `kubectl exec <each-pod> -- env | grep TZ` returns `TZ=UTC` for backend, arq-worker, telegram-bot.
- [ ] **Sealed Secrets controller key backed up:** The key YAML file exists on the off-node backup location.
- [ ] **Trivy scan green:** `trivy image clubcore-backend:<tag>` shows no CRITICAL vulnerabilities.

---

## What Local Validation CANNOT Catch (Operator-Pending Boundary)

These items will NOT be caught by kind/k3s local validation and must be explicitly listed as operator-pending in the runbook:

| Item | Why Local Validation Misses It | Operator Action Required |
|------|-------------------------------|--------------------------|
| Let's Encrypt TLS certificate issuance | Local validation uses staging/self-signed; LE production requires a real domain with public DNS | Switch ClusterIssuer to production ACME on live server; verify cert in browser |
| Postgres data durability on real disk failure | kind/k3s uses a loop device or tmpfs; actual bare-metal disk failure is not simulatable | Verify `pg_dumpall` backup CronJob ran and the output file is on a different physical device from the Postgres PV |
| Redis AOF on real power loss | kind containers don't survive real node power cycles | On live server: trust AOF + verify `aof-use-rdb-preamble yes` in the running config |
| YooKassa webhook reachability | Local kind cluster is not internet-accessible; the webhook IP allow-list check cannot be tested end-to-end | Register real webhook URL with YooKassa dashboard; send a test payment in sandbox mode |
| RU email deliverability (Yandex Postbox) | Local stack has no real SMTP credentials or domain | Verify SPF/DKIM/DMARC pass on a real send to yandex.ru + mail.ru (pre-existing operator-pending from v1.6) |
| Telegram bot token in production | `SENTINEL_BOT_TOKEN` check prevents bot from starting with the placeholder token | Set real `TELEGRAM_BOT_TOKEN` in the production Secret before applying |
| Actual node failover (PVC re-bind) | Single-node kind can't simulate node failure | Test by manually draining the node if a second node exists, or document as single-node-only risk |
| `terraform apply` on real VM | `terraform validate` and `plan` run against a mock provider; `apply` contacts the real host | Operator runs `terraform apply` with real SSH credentials to the bare-metal server |
| Prometheus alert delivery (Telegram/webhook) | Local Alertmanager has no real notification channel | Configure Alertmanager routes with real Telegram bot token or webhook before going live |
| `terraform plan` greenness guarantees apply success | Plan validates schema and API calls; it does not simulate race conditions, disk space, or network failures during apply | Operator reviews plan output carefully and applies with `--auto-approve` only after manual inspection |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Postgres node-affinity data loss (P1) | K8s manifests — StatefulSet + PVC + nodeSelector | Restore round-trip test during Backup & Recovery phase |
| ARQ cron double-fire (P2) | K8s manifests — ARQ worker Deployment strategy=Recreate, replicas=1 | `kubectl get deployment arq-worker` shows strategy=Recreate; no duplicate cron logs in Loki |
| Telegram double-consume (P3) | K8s manifests — telegram-bot Deployment strategy=Recreate, replicas=1 | No duplicate `/checkin` DMs in smoke test |
| Migrate race (P4) | K8s manifests / Helm — migrate Job as pre-install hook | `helm template` shows hook annotation; API smoke test completes without `column does not exist` error |
| Redis data loss on restart (P5) | K8s manifests — Redis ConfigMap (AOF) + PVC + maxmemory | `redis-cli config get appendonly` returns `yes` after pod restart |
| Sealed Secrets key loss (P6) | Security phase — controller key backup procedure | Key YAML verified present on off-node backup before declaring security done |
| k3s Traefik quirks (P7) | Networking phase — IngressRoute + WebSocket annotation + staging TLS | `wscat` test through ingress; staging cert shows in browser |
| NetworkPolicy DNS breakage (P8) | Networking phase — CoreDNS egress rule in all pod policies | `nslookup postgres-svc` from each pod succeeds after NetworkPolicies applied |
| Image pitfalls (P9) | Containerization phase — tzdata, chown, explicit tags | `docker run --user app` smoke test; ARQ cron fires at correct MSK time |
| PWA SW caching /api/* (P10) | Containerization phase — nginx config for frontend images | Browser devtools Cache Storage audit; `/plans` direct navigation 200 |
| OOMKill + liveness probes (P11) | K8s manifests / Helm — resource limits + startupProbe | `kubectl describe pod` shows no OOMKilled events; startup completes before liveness probe engages |
| UTC/MSK timezone drift (P12) | K8s manifests — TZ=UTC in all ConfigMaps | `env | grep TZ` on all pods; cron fires at 03:05 UTC not 06:05 UTC |

---

## Sources

- ARQ 0.28 codebase: unique cron lock implementation (`arq/cron.py` — `SET NX EX` dedup per job name + tick time)
- k3s documentation: built-in Traefik v2, local-path-provisioner behavior and node affinity constraints
- Sealed Secrets: backup/restore documentation (bitnami-labs/sealed-secrets)
- cert-manager: Let's Encrypt rate limits documentation
- clubcore codebase: `apps/backend/app/workers/__init__.py` (WorkerSettings, cron_jobs, unique=True, MSK UTC-offset comments, on_startup cron-resolution assertion)
- clubcore codebase: `apps/backend/Dockerfile` (non-root app user, venv PATH, chown coverage)
- clubcore PROJECT.md: v4.0 milestone scope, TZ=UTC locked decision (Phase 15 Key Decision), ARQ cron time offset documentation
- Prior pitfall documentation in codebase: PITFALLS Pitfall 4 (ARQ cron no-op silent trap), PITFALL 14 (structlog contextvars leak across worker runs)

---
*Pitfalls research for: clubcore v4.0 Production Infrastructure — self-hosted bare-metal k3s*
*Researched: 2026-06-16*
