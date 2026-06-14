# Verification Scripts

Operator runbooks for milestone verification sweeps (v1.4 + v1.7 + v3.0 P102).

## v1.4 / v1.7 Sweep Recipe

Required env vars (export before running):

- `SECRET_KEY` — >=48 bytes
- `SEED_VERIFY_OWNER_PASSWORD` — >=12 chars; also export as `VERIFY_OWNER_PASSWORD`
- `SEED_VERIFY_RECEPTION_PASSWORD` — >=12 chars; also export as `VERIFY_RECEPTION_PASSWORD`

Required tools: `curl`, `jq`, `uuidgen`, `psql` (libpq), `docker compose`.

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

```bash
cd apps/backend
export YOOKASSA_SANDBOX=true
export VERIFY_OWNER_PASSWORD="${SEED_VERIFY_OWNER_PASSWORD}"
export VERIFY_RECEPTION_PASSWORD="${SEED_VERIFY_RECEPTION_PASSWORD}"
bash scripts/verify/v1_7_runbook.sh
```

---

## P102 Walkthrough (Bookings + Payroll) — Phase 110

### Purpose

The P102 booking lifecycle (create → cancel → complete-via-pt-session) and trainer
payroll lifecycle (comp-config → preview → run → mark-paid) were `data-setup-blocked`
at v3.0 close because no seed data existed. This script and seed close that blocker
(Phase 110 criterion #4): the walkthrough is now repeatable.

**Authoritative verification:** The integration test suite (Phase 110 Plans 02 and 03)
is the authoritative repeatable verification — it runs against real Postgres via
httpx ASGITransport + real transactions. This script is the captured live-HTTP
confirmation on top of a started uvicorn.

**Deferred:** If uvicorn cannot be started headlessly during execution, the script is
captured here and the literal-HTTP confirmation is deferred as a UAT item (per
110-CONTEXT.md deferred-ideas). The integration test suite in Plans 02/03 remains the
primary verification path.

### Cookie Discipline (v3.0 — use these names, NOT the old sz_* scheme)

| Cookie | Type | Role |
|--------|------|------|
| `cc_access` | HTTP-only | Access JWT — auto-sent by curl via cookie jar |
| `cc_refresh` | HTTP-only | Refresh token |
| `clubcore_csrf` | non-HttpOnly | CSRF token — extract and send as `X-CSRF-Token` header |

### Repeatable Path (end-to-end)

**Step 1: Bring up the dev stack**

```bash
cd apps/backend
docker compose up -d postgres redis
```

**Step 2: Apply migrations**

```bash
docker compose exec migrate alembic upgrade head
# or directly:
uv run alembic upgrade head
```

**Step 3: Seed demo data (creates the bootstrap owner)**

```bash
export SEED_OWNER_EMAIL="owner@example.com"
export SEED_OWNER_PASSWORD="your-password-here"   # >= 12 chars
uv run python -m scripts.seed_demo_data
```

**Step 4: Seed P102 walkthrough prerequisites**

```bash
uv run python -m scripts.seed_p102_walkthrough
```

The script prints the entity IDs:

```
seed_p102_walkthrough: idempotent seed complete.
  trainer_id       = 92c594e9-8ef0-50ea-90fb-723b41b0b020
  slot_id          = deb4d2ee-2f6b-5523-9e43-c95ae4a404e9
  pt_package_plan  = a076ab58-7f39-5ff6-9d8f-021742e70ace
  client_id        = dea9de63-294e-5d34-8156-67eb463c5a7d
  pt_package_id    = 304591f3-0c6d-5709-bc69-ae01971b4fcf
  comp_config_id   = 7357cc11-946d-572e-9f9d-02ce9647f003
  payment_id       = 0e7450c1-67db-5669-81bd-6f3cc7321301
  slot_start (UTC) = 2026-06-15T07:00:00+00:00
```

**Re-running the seed is a no-op** — idempotent by design (uuid5 PKs + ON CONFLICT DO NOTHING).

**Step 5: Start uvicorn**

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Step 6: Run the walkthrough script**

Export the IDs printed by step 4, then run:

```bash
export TRAINER_ID="92c594e9-8ef0-50ea-90fb-723b41b0b020"
export SLOT_ID="deb4d2ee-2f6b-5523-9e43-c95ae4a404e9"
export CLIENT_ID="dea9de63-294e-5d34-8156-67eb463c5a7d"
export PT_PACKAGE_ID="304591f3-0c6d-5709-bc69-ae01971b4fcf"

bash scripts/verify/p102_walkthrough.sh
```

IDs above are the deterministic uuid5 values — they are identical on every fresh DB.

### What the Script Verifies

| Step | Endpoint | Expected |
|------|----------|----------|
| 1 | `POST /api/v1/auth/login` | 200, `clubcore_csrf` cookie set |
| 2 | `POST /api/v1/bookings` | 201, booking id returned |
| 3 | `POST /api/v1/bookings/{id}/cancel` | 200, status confirmed→cancelled |
| 4a | `POST /api/v1/bookings` | 201, second booking for complete leg |
| 4b | `POST /api/v1/pt-sessions` | 201, booking flipped to completed |
| 5 | `GET /api/v1/payroll/preview` | 200, revenue + sessions visible |
| 6 | `POST /api/v1/payroll/accruals` | 201, accrual pending |
| 7 | `POST /api/v1/payroll/accruals/{id}/mark-paid` | 200, status paid |

### Seed Prerequisites Summary

The seed (`seed_p102_walkthrough.py`) creates:

1. **Trainer** — `P102 Walkthrough Trainer`, active
2. **TrainerAvailabilitySlot** — next Monday 10:00 MSK, 1 h, status=active
3. **PtPackagePlan** — `P102 PT 10 Sessions`, 10 sessions, 1 500 RUB (150 000 kopecks), 90-day validity
4. **Client** — `Walkthrough P102`
5. **PtPackage** — trainer-matched (trainer_id set), active, sessions_remaining=5, validity covers the slot
6. **TrainerCompConfig** — 10% commission (1000 bps) + 500 RUB/session (50 000 kopecks), effective 2026-01-01
7. **Payment** — `subject_kind='pt_package'`, positive amount, received_at=2026-04-15 (within payroll period 2026-04-01..2026-04-30)

### Security Notes

- No credentials are hardcoded in this script or README.
- The seed script enforces: DATABASE_URL must contain `localhost` or `postgres:5432` (TM-29-02 guard).
- SEED_OWNER_PASSWORD must be >= 12 chars (NIST 800-63B 2024).
- Only entity IDs are printed; no passwords or hashes are ever echoed.

---

## Notes (General)

- Each v1.x scenario is hermetic (own cookie jar per `_lib.sh`).
- v1.x scripts use the legacy `_lib.sh` with old cookie names (`sz_access`, `sportzal_csrf`).
  The P102 walkthrough script uses the v3.0 cookie names (`cc_access`, `clubcore_csrf`).
- If `apps/backend/.env` is mutated mid-sweep: `docker compose up -d --force-recreate --no-deps backend`.
