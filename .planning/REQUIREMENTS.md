# Requirements: clubcore v4.0 Production Infrastructure — Self-Hosted k3s

**Defined:** 2026-06-16
**Core Value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.

**Milestone goal:** Сделать clubcore по-настоящему запускаемым — контейнеризировать весь стек, описать инфраструктуру как код (Terraform под on-prem/bare-metal k3s), развернуть в кластере с наблюдаемостью, бэкапами и сетевой безопасностью. **Bar = локальная валидация** (k3d deploy + `terraform validate/plan` + `helm lint` + `make smoke`); боевой apply / живой ЮKassa-leg / RU email-SMS deliverability — operator-pending.

**Research:** `.planning/research/SUMMARY.md` (HIGH confidence, версии проверены 2026-06-16). Чисто инфра/DevOps — бизнес-фичи не трогаем, OpenAPI не меняется (кроме additive NAME-01).

**Scope decisions at definition (2026-06-16):** секреты = **sealed-secrets** (research-resolved; SOPS+age рассмотрен и отклонён — k8s-native проще для no-git-remote, ключ бэкапится off-node); BAK-04 weekly auto restore-verify — **включён** (justified differentiator); SEC-06 ретро secure-phase 70 — **включён** (carry-over из «production launch»).

---

## v4.0 Requirements

Требования для milestone. Каждое маппится на фазу роадмапа (нумерация фаз продолжается со **118**).

### Containerization (IMG)

- [x] **IMG-01**: Production multi-stage Dockerfile для backend — non-root, slim base, no dev-deps, pinned base digest, healthcheck, `.dockerignore`, `tzdata` + `TZ=UTC` подтверждены
- [x] **IMG-02**: Образы для telegram-bot + arq-worker + migrate (общий backend-base, разные entrypoints)
- [x] **IMG-03**: nginx-образы для admin-app + client-pwa (static `dist/`, SPA `try_files` fallback, service worker НЕ кэширует `/api/*`)
- [x] **IMG-04**: git-SHA image tagging + локальный `trivy` scan green (нет HIGH/CRITICAL) как gate; нет `:latest`

### Stateful Services — Helm (DATA)

- [x] **DATA-01**: CloudNativePG operator + `Cluster` CR (`instances: 1`, образы `ghcr.io/cloudnative-pg`, Bitnami отсутствует)
- [x] **DATA-02**: Redis StatefulSet + PVC + AOF (`appendonly yes`, `appendfsync everysec`) + `maxmemory` + `allkeys-lru`
- [x] **DATA-03**: SeaweedFS Helm (standalone S3-режим) — drop-in object-storage, единый для docker-compose и k3s (zero app-code change)
- [x] **DATA-04**: StorageClass `reclaimPolicy: Retain` + Postgres `nodeSelector` pinning (anti data-loss на local-path-provisioner); PVC-bind smoke в k3d

### App Workloads + Migration — Helm (APP)

- [x] **APP-01**: Alembic migrate как Helm `pre-install,pre-upgrade` hook Job (`backoffLimit=0`, `activeDeadlineSeconds: 300`, `hook-weight: -5`) + `alembic check` initContainer на backend (belt-and-suspenders)
- [x] **APP-02**: backend Deployment — `replicas: 1`, startup/liveness/readiness пробы, `resources.requests`+`limits`, `TZ=UTC`
- [x] **APP-03**: arq-worker Deployment — `strategy: Recreate` + `replicas: 1` + `TZ=UTC` (anti cron double-fire; инвариант, не tuning)
- [x] **APP-04**: telegram-bot Deployment — `strategy: Recreate` + `replicas: 1` (anti long-polling double-consume)
- [x] **APP-05**: ConfigMap/Secret separation; маппинг переменных из `.env.example` в ConfigMap + Secret refs

### Networking + Frontends + TLS (NET)

- [x] **NET-01**: Ingress (Traefik v3, bundled с k3s — НЕ ingress-nginx) для 3 хостов (API / admin-app / client-pwa) + HTTP→HTTPS redirect middleware
- [x] **NET-02**: WebSocket-роутинг через ingress для chat (`/api/v1/client/ws/*`, annotation подтверждена для Traefik v3)
- [x] **NET-03**: cert-manager — `selfSigned` ClusterIssuer для local k3d; `letsencrypt-staging` для iterative; LE-prod operator-pending
- [x] **NET-04**: nginx-frontends отдаются + SPA `try_files` fallback + SW cache-headers подтверждены (PWA SW не ломает `/api/*`)

### Security (SEC)

- [x] **SEC-01**: Секреты вне репозитория через sealed-secrets v0.37 (`kubeseal` workflow; `SealedSecret` YAML committed; plaintext никогда не коммитится)
- [x] **SEC-02**: Backup controller RSA-ключа sealed-secrets off-node (рядом с репой на second PC) — **acceptance criterion, не post-hoc** (anti controller-key-loss)
- [x] **SEC-03**: Pod `securityContext` — `runAsNonRoot`, `readOnlyRootFilesystem`, `allowPrivilegeEscalation: false`, drop ALL capabilities
- [x] **SEC-04**: NetworkPolicy default-deny + explicit allow (включая CoreDNS egress UDP/TCP 53 для каждого пода)
- [x] **SEC-05**: NAME-01 — переименование CSRF cookie `sportzal_csrf → clubcore_csrf` (additive `openapi.json`/`schema.d.ts` regen; staff drift-gate ожидает additive-diff)
- [x] **SEC-06**: Ретро `/gsd:secure-phase 70` — verify/close 3 отложенных app-security пункта (proxy rate-limit bucket, QR post-decode existence, cancel idempotency)

### Terraform IaC (IAC)

- [x] **IAC-01**: `infra/terraform/host/` — k3s install на bare-metal node (`null_resource` + `remote-exec`, `terraform.tfvars.example`, local `backend "local"` state); `validate` green (apply operator-pending — нужны SSH-креды)
- [x] **IAC-02**: `infra/terraform/cluster/` — namespaces + `helm_release` (provider v3.2 list-syntax, `tfvars.example`, local state); `validate` + `plan` green против k3d
- [x] **IAC-03**: `make tf-validate` + `make tf-plan` зелёные

### Observability (OBS)

- [x] **OBS-01**: kube-prometheus-stack (single-node resource-tuned, 7d retention) в `monitoring` namespace
- [x] **OBS-02**: Loki community chart (monolithic + Grafana Alloy log shipper, 30d retention) + log shipping со всех подов
- [x] **OBS-03**: FastAPI `/metrics` через `prometheus-fastapi-instrumentator>=7.1,<8` + ServiceMonitor CRD
- [x] **OBS-04**: Grafana dashboards (FastAPI, node-exporter, CNPG Postgres, Redis)
- [x] **OBS-05**: 5–7 critical Alertmanager rules + Telegram receiver (доставка алертов operator-pending — реальный токен в sealed secret)

### Backup & Recovery (BAK)

- [ ] **BAK-01**: CNPG WAL archiving + daily base backup → SeaweedFS S3 (`Cluster.spec.backup.barmanObjectStore`)
- [ ] **BAK-02**: Redis RDB CronJob (weekly → SeaweedFS) + SeaweedFS mirror CronJob (daily → second PVC); retention 7-daily / 4-weekly
- [ ] **BAK-03**: Restore runbook (`infra/runbooks/restore.md`) + **проверенный round-trip restore** (восстановление + row-count check в k3d)
- [ ] **BAK-04**: Weekly automated restore-verification CronJob (реально восстанавливает в scratch + проверяет row-counts; алерт при провале)

### CI/CD Automation + Docs (OPS)

- [ ] **OPS-01**: Root-level `Makefile` — `build`, `scan`, `push`, `tf-validate`, `tf-plan`, `helm-lint`, `helm-validate`, `deploy`, `smoke`, `rollback`, `logs`, `psql`, `backup`, `up`, `down` (без внешнего runner'а/registry — local k3d registry)
- [ ] **OPS-02**: `make up` pipeline green против k3d (build → scan → tf-validate → helm-lint → deploy → smoke)
- [ ] **OPS-03**: `make smoke` проверяет «Looks-Done-But-Isn't» checklist: `/healthz` 200, migrate Job completed, Redis AOF on, `TZ=UTC` на всех подах, DNS-резолв из каждого пода, WebSocket upgrade через ingress, SPA fallback 200, PWA SW Cache clean
- [ ] **OPS-04**: Production runbook (`infra/runbooks/production.md`) — топология, prerequisites, deploy-шаги, операции (backup/restore/rollback/scale), troubleshooting + явный **operator-pending boundary** список

---

## Future Requirements

Подтверждены как ценные, но отложены за пределы v4.0 (deferred-v2+ из research). Не в текущем роадмапе.

### Scaling & HA

- **SCALE-01**: backend `replicas: 2` (WS-safe через Redis pub/sub) + Traefik sticky-session — когда Grafana подтвердит headroom
- **SCALE-02**: HPA / PodDisruptionBudgets / multi-node k3s — при росте за пределы одного зала
- **SCALE-03**: CNPG `instances: 2` (Postgres HA)

### Advanced ops

- **ADVOPS-01**: `prometheus-fastapi-instrumentator` v8 upgrade (требует FastAPI ≥0.133 + Starlette v1 — отдельная задача со своим regression-gate против auth-стека, НЕ привязывать к инфра-фазе)
- **ADVOPS-02**: Distributed tracing (Tempo/Jaeger) — монолит, преждевременно
- **ADVOPS-03**: Image signing (cosign) + SBOM-attestation
- **ADVOPS-04**: PITR / pgBackRest (поверх CNPG WAL) + multi-region backup + backup encryption

---

## Out of Scope

Явно исключено. Зафиксировано чтобы предотвратить scope-creep.

| Feature | Reason |
|---------|--------|
| Managed-cloud (Yandex/AWS Managed K8s) | Выбран on-prem/bare-metal k3s [D-V40-ONPREM-K3S] |
| Боевой `terraform apply` / live deploy на реальный сервер | Нужны SSH-креды + железо; bar = локальная валидация [D-V40-LOCAL-VALIDATE]; apply operator-pending |
| Живой ЮKassa credentialed leg + RU email/SMS deliverability | Operator-credential-gated (прецедент D-72-06 / D-67-03 no-fabricated-evidence) |
| ingress-nginx | Retired + archived March 2026 — нет security-патчей; используем Traefik v3 |
| MinIO | `minio/minio` repo archived April 2026; используем SeaweedFS |
| Bitnami Helm charts (Postgres/Redis) | Образы за Broadcom paywall (`bitnamilegacy`, без обновлений); CNPG + plain Redis StatefulSet |
| GitOps (ArgoCD / FluxCD) + любой инструмент, требующий git remote / external registry | Нет git remote (репа копируется на second PC) [D-V40-MAKEFILE-CD]; Makefile + local k3d registry |
| HashiCorp Vault / external-secrets | Sealed-secrets достаточно для соло no-remote проекта |
| OPA/Gatekeeper | Встроенный PodSecurityAdmission + securityContext достаточно |
| MetalLB / service mesh / Velero / multi-arch builds | Над-инжиниринг для одного узла / одного зала |
| `kind` для локальной валидации | k3d даёт паритет с k3s (Traefik/ServiceLB); kind — другой дистрибутив |
| Новые бизнес-фичи / изменения OpenAPI | Чисто инфра milestone (исключение: additive NAME-01 cookie rename) |
| Мультифилиальность / multi-tenancy / persisted-RBAC / Notifications Hub | Отдельные крупные milestone'ы (backlog) |

### Operator-Pending Boundary (что локальная валидация НЕ ловит)

Не дефекты — честная граница, фиксируется в production runbook (OPS-04):
- Let's Encrypt **prod** TLS (переключение ClusterIssuer на live-сервере)
- Реальная durability диска Postgres + Redis AOF при power-loss (не симулируется в k3d)
- `terraform apply` на реальной VM (нужны SSH-креды)
- ЮKassa webhook reachability + sandbox-платёж
- RU email deliverability (Yandex Postbox SPF/DKIM/DMARC — pre-existing с v1.6)
- Реальные `TELEGRAM_BOT_TOKEN` + Alertmanager Telegram-доставка (sealed secret на live)

---

## Traceability

Какие фазы покрывают какие требования.

| Requirement | Phase | Status |
|-------------|-------|--------|
| IMG-01 | Phase 118 | Complete |
| IMG-02 | Phase 118 | Complete |
| IMG-03 | Phase 118 | Complete |
| IMG-04 | Phase 118 | Complete |
| DATA-01 | Phase 118 | Complete |
| DATA-02 | Phase 118 | Complete |
| DATA-03 | Phase 118 | Complete |
| DATA-04 | Phase 118 | Complete |
| APP-01 | Phase 118 | Complete |
| APP-02 | Phase 118 | Complete |
| APP-03 | Phase 118 | Complete |
| APP-04 | Phase 118 | Complete |
| APP-05 | Phase 118 | Complete |
| NET-01 | Phase 119 | Complete |
| NET-02 | Phase 119 | Complete |
| NET-03 | Phase 119 | Complete |
| NET-04 | Phase 119 | Complete |
| SEC-01 | Phase 119 | Complete |
| SEC-02 | Phase 119 | Complete |
| SEC-03 | Phase 119 | Complete |
| SEC-04 | Phase 119 | Complete |
| SEC-05 | Phase 119 | Complete |
| SEC-06 | Phase 119 | Complete |
| IAC-01 | Phase 120 | Complete |
| IAC-02 | Phase 120 | Complete |
| IAC-03 | Phase 120 | Complete |
| OBS-01 | Phase 120 | Complete |
| OBS-02 | Phase 120 | Complete |
| OBS-03 | Phase 120 | Complete |
| OBS-04 | Phase 120 | Complete |
| OBS-05 | Phase 120 | Complete |
| BAK-01 | Phase 120 | Pending |
| BAK-02 | Phase 120 | Pending |
| BAK-03 | Phase 120 | Pending |
| BAK-04 | Phase 120 | Pending |
| OPS-01 | Phase 121 | Pending |
| OPS-02 | Phase 121 | Pending |
| OPS-03 | Phase 121 | Pending |
| OPS-04 | Phase 121 | Pending |

**Coverage:**
- v4.0 requirements: 39 total (IMG 4 · DATA 4 · APP 5 · NET 4 · SEC 6 · IAC 3 · OBS 5 · BAK 4 · OPS 4)
- Mapped to phases: 39/39 ✓
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-16*
*Last updated: 2026-06-16 — traceability filled after roadmap creation*
