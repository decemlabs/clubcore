# infra/terraform/cluster/main.tf — IAC-02: monitoring namespace + observability helm_releases
#
# OPERATOR-PENDING: `terraform plan` and `apply` require a reachable k3d cluster.
# Done-bar for IAC-02: `terraform validate` exits 0 (static check; no cluster reachable here).
#
# Usage:
#   1. Ensure a k3d cluster is running (bash infra/scripts/k3d-up.sh).
#   2. Copy terraform.tfvars.example → terraform.tfvars with real kubeconfig path/context.
#   3. terraform init
#   4. terraform validate       # done-bar (static, no cluster needed)
#   5. terraform plan           # OPERATOR-PENDING — needs reachable k3d
#   6. terraform apply          # OPERATOR-PENDING — needs reachable k3d + helm
#
# D-V40-TF-PROVIDER: hashicorp/helm provider v3.2.0 — BREAKING from v2.x.
# All helm_release `set` blocks MUST use list-of-objects syntax:
#   set = [{ name = "key.path", value = "val" }]
# NEVER use the v2.x map form for `set` blocks (e.g. the legacy syntax with braces instead of brackets)

terraform {
  required_version = ">= 1.6"

  # backend "local" — state stored on the operator's machine.
  # No remote backend (no git remote — D-V40-MAKEFILE-CD).
  backend "local" {}

  required_providers {
    helm = {
      source  = "hashicorp/helm"
      version = "3.2.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.30"
    }
  }
}

# ── Provider configuration ─────────────────────────────────────────────────────

provider "kubernetes" {
  config_path    = var.kubeconfig_path
  config_context = var.kube_context
}

provider "helm" {
  kubernetes {
    config_path    = var.kubeconfig_path
    config_context = var.kube_context
  }
}

# ── Namespaces ─────────────────────────────────────────────────────────────────

resource "kubernetes_namespace" "monitoring" {
  metadata {
    name = "monitoring"
    labels = {
      "app.kubernetes.io/managed-by" = "terraform"
      "app.kubernetes.io/part-of"    = "clubcore-observability"
    }
  }
}

# ── Observability: kube-prometheus-stack ───────────────────────────────────────
#
# Deploys Prometheus + Alertmanager + Grafana.
# Values file authored in infra/observability/kube-prometheus-stack-values.yaml (Plan 02).

resource "helm_release" "kube_prometheus_stack" {
  name             = "kube-prometheus-stack"
  repository       = "https://prometheus-community.github.io/helm-charts"
  chart            = "kube-prometheus-stack"
  version          = var.kube_prometheus_stack_version
  namespace        = kubernetes_namespace.monitoring.metadata[0].name
  create_namespace = false

  values = [
    file("${path.module}/../../observability/kube-prometheus-stack-values.yaml"),
  ]

  # D-V40-TF-PROVIDER: list-of-objects set syntax (v3.2.0 — never map form).
  # Override a single resource limit to demonstrate the list-set contract.
  set = [
    { name = "prometheus.prometheusSpec.retention", value = "7d" },       # 7-day metrics retention (single node)
    { name = "grafana.adminPassword", value = var.grafana_admin_password }, # override default "prom-operator" password
  ]

  timeout = 600
}

# ── Observability: Loki (single-binary mode, 30d retention) ───────────────────
#
# Grafana Loki v6.x single-binary chart.
# Values file: infra/observability/loki-values.yaml (Plan 02).

resource "helm_release" "loki" {
  name             = "loki"
  repository       = "https://grafana.github.io/helm-charts"
  chart            = "loki"
  version          = var.loki_version
  namespace        = kubernetes_namespace.monitoring.metadata[0].name
  create_namespace = false

  values = [
    file("${path.module}/../../observability/loki-values.yaml"),
  ]

  # D-V40-TF-PROVIDER: list-of-objects set syntax (v3.2.0).
  set = [
    { name = "loki.commonConfig.replication_factor", value = "1" }, # single-node: no replication
  ]

  timeout = 300
}

# ── Observability: Grafana Alloy (log collector / metrics forwarder) ───────────
#
# Grafana Alloy replaces the deprecated Promtail agent.
# Values file: infra/observability/alloy-values.yaml (Plan 02).

resource "helm_release" "alloy" {
  name             = "alloy"
  repository       = "https://grafana.github.io/helm-charts"
  chart            = "alloy"
  version          = var.alloy_version
  namespace        = kubernetes_namespace.monitoring.metadata[0].name
  create_namespace = false

  values = [
    file("${path.module}/../../observability/alloy-values.yaml"),
  ]

  # D-V40-TF-PROVIDER: list-of-objects set syntax (v3.2.0).
  set = [
    { name = "alloy.stabilityLevel", value = "generally-available" }, # use only GA features
  ]

  timeout = 300
}
