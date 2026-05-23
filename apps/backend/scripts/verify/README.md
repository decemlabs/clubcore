# Verification Scripts

Operator recipes for milestone verification sweeps (v1.4 + v1.7).

## Pre-flight

Required env vars (export before running):
- `SECRET_KEY` — ≥48 bytes (v1.3 first-run-failure lesson under `pyproject.toml` `filterwarnings=["error"]`).
- `SEED_VERIFY_OWNER_PASSWORD` — ≥12 chars; also export the same value as `VERIFY_OWNER_PASSWORD` for the scenario scripts.
- `SEED_VERIFY_RECEPTION_PASSWORD` — ≥12 chars; also export the same value as `VERIFY_RECEPTION_PASSWORD`.

Required tools: `curl`, `jq`, `uuidgen`, `psql` (libpq), `docker compose`.

## Sweep recipe

```bash
cd apps/backend
docker compose up -d
docker compose exec migrate alembic upgrade head  # if not already current
uv run python -m scripts.seed_v1_4_verification_fixtures
bash scripts/verify/_preflight.sh  # 10-check readiness gate
for s in scripts/verify/0*.sh; do
  echo "--- $s ---"
  bash "$s" || { echo "FAILED: $s — see evidence file"; exit 1; }
done
```

## v1.7 Runbook

One-command entry point for the complete v1.7 online-payment-to-fiscal walkthrough (VER-01):

```bash
cd apps/backend
# Additional requirement for v1.7: YOOKASSA_SANDBOX=true in the compose stack env
# (apps/backend/.env or docker-compose.yml YOOKASSA_SANDBOX env var).
# This allows the webhook simulation (D-02) to bypass verify_yookassa_ip from localhost.
export YOOKASSA_SANDBOX=true
export VERIFY_OWNER_PASSWORD="${SEED_VERIFY_OWNER_PASSWORD}"
export VERIFY_RECEPTION_PASSWORD="${SEED_VERIFY_RECEPTION_PASSWORD}"
bash scripts/verify/v1_7_runbook.sh
```

The runbook drives: sell → `payment.succeeded` webhook → membership activated → `fiscal_receipts`
row confirmed → refund (202) → idempotency-key replay returns idempotent 2xx.

**YOOKASSA_SANDBOX requirement:** `YOOKASSA_SANDBOX=true` must be set on the backend service
(in `apps/backend/.env` or as an env var in `docker-compose.yml`). This enables the sandbox
bypass in `webhook_verifier.py` so raw curl POSTs from localhost are treated as trusted.
Production deployments must NEVER set this flag.

**Evidence directory:** `.planning/milestones/v1.7-verification-evidence/`  
Each scenario tees its stdout/stderr to a `.txt` file in that directory.

**Inline-regression hard cap: 5** (D-05). Beyond 5 inline regressions → STOP and roll
excess to v1.8 DEFER. Do not extend this runbook beyond the cap.

## Notes

- Each scenario is hermetic (own cookie jar per `_lib.sh`).
- Mid-scenario psql time-travel allowed per D-36-05; log in scenario comment + `notes:` field in VERIFICATION-LOG.md.
- If `apps/backend/.env` is mutated mid-sweep: `docker compose up -d --force-recreate --no-deps backend` (plain `restart` does NOT reload env_file — v1.3 5d lesson).
- Inline regression fix protocol (D-36-15..17): reproduce → fix as own commit `fix(36-NN): REG-36-XX <desc>` → re-run → log in VERIFICATION-LOG.md `overrides:`. Hard cap: 5.
