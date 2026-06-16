# infra/terraform/host/main.tf — IAC-01: k3s bare-metal install via null_resource + remote-exec
#
# OPERATOR-PENDING: `terraform apply` requires SSH credentials to the real bare-metal node.
# Done-bar for IAC-01: `terraform validate` exits 0 (static check; no node reachable here).
#
# Usage:
#   1. Copy terraform.tfvars.example → terraform.tfvars and fill in real values (never commit it).
#   2. terraform init
#   3. terraform validate       # done-bar in sandbox
#   4. terraform plan           # operator-pending (needs SSH reachable node)
#   5. terraform apply          # operator-pending (SSH creds + real bare-metal node)

terraform {
  required_version = ">= 1.6"

  # backend "local" — state stored on the operator's machine alongside the repo.
  # No remote backend: the project model has no git remote (D-V40-MAKEFILE-CD).
  backend "local" {}

  required_providers {
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
  }
}

# ── k3s install ────────────────────────────────────────────────────────────────
#
# Installs k3s on the bare-metal node over SSH using the official install script.
# Traefik is bundled with k3s (D-V40-ONPREM-K3S) — do NOT pass --disable traefik.
# Triggers a re-provision when the k3s_version or node host changes.

resource "null_resource" "k3s_install" {
  triggers = {
    k3s_version = var.k3s_version
    node_host   = var.ssh_host
  }

  connection {
    type        = "ssh"
    host        = var.ssh_host
    user        = var.ssh_user
    private_key = file(var.ssh_private_key_path)
    timeout     = "5m"
  }

  provisioner "remote-exec" {
    inline = [
      # Download and run the official k3s install script.
      # INSTALL_K3S_VERSION pins the exact version; INSTALL_K3S_EXEC passes server flags.
      # --write-kubeconfig-mode 644 lets the operator read kubeconfig without sudo.
      # Traefik is intentionally kept (D-V40-ONPREM-K3S — ingress = Traefik v3).
      "export INSTALL_K3S_VERSION='${var.k3s_version}'",
      "export INSTALL_K3S_EXEC='server --write-kubeconfig-mode 644'",
      "curl -sfL https://get.k3s.io | sh -",
      # Wait until k3s is Ready before returning control.
      "kubectl wait node --for=condition=Ready --all --timeout=120s",
    ]
  }
}
