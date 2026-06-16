# Makefile — clubcore IAC-03 targets (Phase 120)
#
# Scope: ONLY the two Terraform validation/plan targets required by IAC-03.
# The FULL Makefile (build, scan, deploy, smoke, up, down, push, etc.) is
# authored in Phase 121 (OPS-01) — do NOT add those targets here.
#
# Usage:
#   make tf-validate    # static validate — both modules; no cluster needed
#   make tf-plan        # OPERATOR-PENDING — needs a reachable k3d cluster

.PHONY: tf-validate tf-plan help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

tf-validate: ## Validate both Terraform modules (static; no cluster needed)
	terraform -chdir=infra/terraform/host validate
	terraform -chdir=infra/terraform/cluster validate

tf-plan: ## Plan the cluster module against k3d (OPERATOR-PENDING — needs reachable k3d)
	terraform -chdir=infra/terraform/cluster plan
