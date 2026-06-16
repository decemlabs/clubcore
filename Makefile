# Makefile — clubcore IAC-03 targets (Phase 120) + CD layer (Phase 121 OPS-01/OPS-02)
#
# Phase 120 scope: Terraform validation/plan targets (tf-validate, tf-plan).
# Phase 121 scope: Full CD layer — build, scan, push, helm-lint, helm-validate,
#                  deploy, smoke, rollback, logs, psql, backup, up, down.
#
# Usage:
#   make help           # list all targets with descriptions
#   make tf-validate    # static validate — both Terraform modules; no cluster needed
#   make tf-plan        # OPERATOR-PENDING — needs a reachable k3d cluster
#   make up             # OPERATOR-PENDING — full pipeline: build→scan→tf-validate→helm-lint→deploy→smoke
#   make smoke          # OPERATOR-PENDING — standalone 8-check smoke against a running cluster
#
# Targets requiring k3d / helm / trivy / terraform are tagged (OPERATOR-PENDING ...)
# in their help string so `make help` surfaces the honesty boundary (D-V40-LOCAL-VALIDATE).

# ── Variable conventions ───────────────────────────────────────────────────────
# TAG is derived from git-short-SHA by build-images.sh / deploy-local.sh internally
# (including the -dirty suffix). The Makefile exposes it for helm-lint / helm-validate
# and push, but MUST NOT override the scripts' internal derivation to keep build↔deploy
# tag in sync (image import tag == build tag per IMG-04). To guarantee the tag a manual
# `make push`/`make helm-lint` references actually exists, this derivation MUST match
# build-images.sh / deploy-local.sh exactly: short-SHA plus a "-dirty" suffix when the
# working tree (unstaged OR staged) is dirty.
TAG        ?= $(shell t=$$(git rev-parse --short HEAD); if ! git diff --quiet || ! git diff --cached --quiet; then t="$$t-dirty"; fi; echo "$$t")
NAMESPACE  ?= default
RELEASE    ?= clubcore
K3D_CLUSTER ?= clubcore
COMPONENT  ?= backend

.PHONY: help tf-validate tf-plan build scan push helm-lint helm-validate deploy smoke rollback logs psql backup up down

# ── Phase 120 targets (preserved verbatim) ────────────────────────────────────

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

tf-validate: ## Validate both Terraform modules (static; no cluster needed)
	terraform -chdir=infra/terraform/host validate
	terraform -chdir=infra/terraform/cluster validate

tf-plan: ## Plan the cluster module against k3d (OPERATOR-PENDING — needs reachable k3d)
	terraform -chdir=infra/terraform/cluster plan

# ── Phase 121 targets (OPS-01) ────────────────────────────────────────────────

build: ## Build all 4 clubcore container images tagged with git short-SHA
	bash infra/scripts/build-images.sh

scan: ## Scan images for HIGH/CRITICAL CVEs (OPERATOR-PENDING — needs trivy; CI: set REQUIRE_TRIVY=1)
	bash infra/scripts/scan-images.sh

push: ## Import SHA-tagged images into local k3d registry (OPERATOR-PENDING — needs k3d)
	k3d image import \
		clubcore/backend:$(TAG) \
		clubcore/admin-app:$(TAG) \
		clubcore/client-pwa:$(TAG) \
		-c $(K3D_CLUSTER)

helm-lint: ## Lint the Helm chart with image.tag set (OPERATOR-PENDING — needs helm)
	helm lint infra/helm/clubcore \
		--set image.tag=$(TAG) \
		--set seaweedfs.enabled=false

helm-validate: ## Template + kubeconform schema validation (OPERATOR-PENDING — needs helm + kubeconform)
	helm template $(RELEASE) infra/helm/clubcore \
		--set image.tag=$(TAG) \
		--set seaweedfs.enabled=false \
		| kubeconform \
			-summary \
			-strict \
			-ignore-missing-schemas \
			-kubernetes-version 1.29.0

deploy: ## Import images + helm upgrade --install + inline smoke (OPERATOR-PENDING — needs k3d + helm)
	bash infra/scripts/deploy-local.sh

smoke: ## Run the 8-check Looks-Done-But-Isn't smoke against a deployed cluster (OPERATOR-PENDING — needs cluster)
	bash infra/scripts/smoke.sh

rollback: ## Roll back the Helm release to the previous revision (OPERATOR-PENDING — needs helm)
	helm rollback $(RELEASE)

logs: ## Tail the last 100 log lines for a workload component (OPERATOR-PENDING — needs kubectl + cluster)
	kubectl logs \
		--selector="app.kubernetes.io/component=$(COMPONENT)" \
		-n $(NAMESPACE) \
		--tail=100

psql: ## Open a psql session on the CNPG primary pod (OPERATOR-PENDING — needs kubectl + cluster)
	kubectl exec -it \
		-n $(NAMESPACE) \
		$$(kubectl get pod \
			-n $(NAMESPACE) \
			-l cnpg.io/cluster=clubcore-postgres,cnpg.io/instanceRole=primary \
			-o jsonpath='{.items[0].metadata.name}') \
		-- psql -U app -d clubcore

backup: ## Run a verified CNPG restore round-trip to a scratch namespace (OPERATOR-PENDING — needs k3d + CNPG + backup.enabled)
	bash infra/scripts/restore-verify.sh

# ── OPS-02: composed pipeline ─────────────────────────────────────────────────
up: build scan tf-validate helm-lint deploy smoke ## Full CD pipeline: build→scan→tf-validate→helm-lint→deploy→smoke (OPERATOR-PENDING — needs k3d/helm/trivy)

down: ## Delete the local k3d cluster (OPERATOR-PENDING — needs k3d)
	k3d cluster delete $(K3D_CLUSTER)
