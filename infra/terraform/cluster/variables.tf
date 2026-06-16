# infra/terraform/cluster/variables.tf — IAC-02: input variables for the cluster module

variable "kubeconfig_path" {
  type        = string
  description = "Path to the kubeconfig file on the operator's machine. Defaults to the standard kubectl location."
  default     = "~/.kube/config"
}

variable "kube_context" {
  type        = string
  description = "kubectl context name to use (e.g. 'k3d-clubcore' for local k3d, or 'clubcore-prod' for bare-metal). Defaults to the active context in kubeconfig."
  default     = "k3d-clubcore"
}

# ── Chart versions ─────────────────────────────────────────────────────────────
# Pin chart versions for reproducibility; update deliberately when upgrading.

variable "kube_prometheus_stack_version" {
  type        = string
  description = "Helm chart version for kube-prometheus-stack (prometheus-community repo). ROADMAP-cited v86.2.3."
  default     = "86.2.3"
}

variable "loki_version" {
  type        = string
  description = "Helm chart version for Loki (grafana repo). v6.x single-binary chart."
  default     = "6.29.0"
}

variable "alloy_version" {
  type        = string
  description = "Helm chart version for Grafana Alloy (grafana repo). Replaces deprecated Promtail."
  default     = "0.12.5"
}

# ── Grafana credentials ────────────────────────────────────────────────────────

variable "grafana_admin_password" {
  type        = string
  description = "Grafana admin password. Must be set via terraform.tfvars (never committed). No default to force explicit supply."
  sensitive   = true
}
