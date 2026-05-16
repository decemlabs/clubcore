# Phase 36 Verification Scripts

Operator recipe for the v1.4 backend-only milestone verification sweep.

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

## Notes

- Each scenario is hermetic (own cookie jar per `_lib.sh`).
- Mid-scenario psql time-travel allowed per D-36-05; log in scenario comment + `notes:` field in VERIFICATION-LOG.md.
- If `apps/backend/.env` is mutated mid-sweep: `docker compose up -d --force-recreate --no-deps backend` (plain `restart` does NOT reload env_file — v1.3 5d lesson).
- Inline regression fix protocol (D-36-15..17): reproduce → fix as own commit `fix(36-NN): REG-36-XX <desc>` → re-run → log in VERIFICATION-LOG.md `overrides:`. Hard cap: 5.
