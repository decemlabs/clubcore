# Grafana Dashboards (OBS-04)

Four curated dashboards for the clubcore v4.0 observability stack.

## Operator Install Path

Dashboards are delivered as Grafana dashboard JSON files in this directory.
On a running cluster they are loaded via Grafana's ConfigMap sidecar autodiscovery:

```bash
# Create a ConfigMap for each dashboard in the monitoring namespace
for f in fastapi node-exporter cnpg-postgres redis; do
  kubectl create configmap "grafana-dashboard-${f}" \
    --from-file="${f}.json" \
    --namespace monitoring \
    --dry-run=client -o yaml \
  | kubectl apply -f -
  kubectl label configmap "grafana-dashboard-${f}" grafana_dashboard=1 -n monitoring
done
```

The kube-prometheus-stack Grafana sidecar watches ConfigMaps with label
`grafana_dashboard: "1"` in the `monitoring` namespace and auto-imports them.

## Dashboard Inventory

### 1. FastAPI Backend (`fastapi.json`)

**Source:** Custom dashboard (prometheus-fastapi-instrumentator metrics).

**Key metric names** (from `prometheus-fastapi-instrumentator>=7.1`):
- `http_request_duration_seconds` — histogram (latency percentiles p50/p90/p99)
- `http_requests_total` — counter (request rate, grouped by method/path/status)
- `http_requests_created` — gauge (request inflight tracking)

**Panels:**
- Request rate (RPS) by HTTP method and status code
- Latency p50/p90/p99 by path
- Error rate (5xx/4xx percentage)
- Request duration heatmap

**Datasource:** Prometheus (variable: `datasource`)

---

### 2. Node Exporter (`node-exporter.json`)

**Source:** Grafana.com community dashboard  
**Dashboard ID:** 1860 ("Node Exporter Full" by rfmoz)  
**URL:** https://grafana.com/grafana/dashboards/1860

Import instructions (alternative to ConfigMap path):
1. Grafana → Dashboards → Import
2. Enter ID `1860`, select the Prometheus datasource

---

### 3. CNPG PostgreSQL (`cnpg-postgres.json`)

**Source:** Grafana.com community dashboard  
**Dashboard ID:** 20417 ("CloudNativePG" official dashboard)  
**URL:** https://grafana.com/grafana/dashboards/20417

This dashboard uses the CNPG metrics exposed by the `cnpg-collector` sidecar
that is bundled with every CNPG `Cluster` CR. The `cnpg_collector_*` metric
family includes:
- `cnpg_collector_last_available_backup_timestamp` — used by the
  PostgresNoBackupIn25h alert rule in `alertmanager-rules.yaml` (OBS-05/BAK-01)

Import instructions (alternative to ConfigMap path):
1. Grafana → Dashboards → Import
2. Enter ID `20417`, select the Prometheus datasource

---

### 4. Redis (`redis.json`)

**Source:** Grafana.com community dashboard  
**Dashboard ID:** 763 ("Redis Dashboard for Prometheus Redis Exporter" by oliver006)  
**URL:** https://grafana.com/grafana/dashboards/763

**Note:** This dashboard requires a Redis Prometheus exporter sidecar or a
`redis_exporter` deployment. For the clubcore v4.0 stack, deploy
`oliver006/redis_exporter` as a sidecar alongside the Redis StatefulSet, or as
a standalone Deployment pointing at `<release>-redis:6379`.

Import instructions (alternative to ConfigMap path):
1. Grafana → Dashboards → Import
2. Enter ID `763`, select the Prometheus datasource

---

## Notes

- All grafana.com dashboards above are community-maintained and kept up-to-date.
- The JSON files in this directory are **import wrappers** that embed the `gnetId`
  for the grafana.com dashboards, so Grafana can resolve them by ID.
- `fastapi.json` is a custom dashboard (no grafana.com ID) built on
  `prometheus-fastapi-instrumentator` metric names.
- OPERATOR-PENDING: `helm lint`/`helm template` verification (helm absent in sandbox).
