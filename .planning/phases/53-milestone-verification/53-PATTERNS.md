# Phase 53: Milestone Verification - Pattern Map

**Mapped:** 2026-05-23
**Files analyzed:** 5 file groups (orchestrator, scenario scripts, race tests, cron-runner, evidence scaffold)
**Analogs found:** 5 / 5 (all groups have strong existing analogs)

This is a **verification phase** — it produces operator scripts, race tests, and
evidence scaffolding, NOT product modules. Every artifact has a precise existing
analog the executor should copy. There is **no "new analog" gap**: the existing
`scripts/verify/` harness, the `db_session_real_commit` integration race pattern,
the one-shot cron runner, and the Phase 52 CARRY evidence dir cover all five
CONTEXT decisions (D-01..D-05).

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `apps/backend/scripts/verify/v1_7_runbook.sh` | operator-orchestrator | request-response (curl/psql) | `scripts/verify/README.md` sweep loop + `08_cross_phase_smoke.sh` | role-match (new top-level orchestrator; harness has only a README loop today) |
| `apps/backend/scripts/verify/NN_*.sh` (09+ VER-01 walkthrough) | operator-scenario | request-response + webhook-POST + psql | `scripts/verify/08_cross_phase_smoke.sh`, `01_sale_with_payment.sh` | exact |
| `apps/backend/tests/integration/online_payments/test_*_race.py` (VER-02 a–d) | integration race test | event-driven / concurrent-write | `tests/integration/payments/test_payments_refund_race.py`, `test_concurrent_expiring_cron_double_pings_race.py` | exact |
| DEFER-46-03 re-run runner (scenario-08 cron-chain circuit-breaker, FISCAL-05 parity) | one-shot operator cron-runner | batch/event-driven | `apps/backend/scripts/run_expiring_cron_once.py` | role-match (different cron target: fiscal dispatch vs expiring notifications) |
| `.planning/handoff/v1.7-yookassa-sandbox-evidence/README.md` | evidence scaffold | doc/operator-handoff | `.planning/handoff/v1.7-email-deliverability-evidence/README.md` | exact |

---

## Shared Patterns

These cut across all new bash scenarios and race tests. Apply them everywhere.

### S1. Hermetic bash scenario skeleton (`_lib.sh` sourcing + cookie jar)
**Source:** `apps/backend/scripts/verify/_lib.sh` (whole file), header of every `NN_*.sh`.
**Apply to:** `v1_7_runbook.sh` and every new `NN_*.sh`.

Every scenario starts identically — source `_lib.sh`, tee evidence, then use the
`login_as` / `mut` / `get` / `psql_exec` helpers. **Do not re-implement curl/auth.**

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"

EVIDENCE=".planning/milestones/v1.7-verification-evidence/NN_<name>.txt"
mkdir -p "$(dirname "$EVIDENCE")"
exec > >(tee "$EVIDENCE") 2>&1
echo "=== scenario NN_<name> ==="
echo "started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

Helpers provided by `_lib.sh` (`_lib.sh:55-120`):
- `login_as <owner|reception>` — POSTs `/api/v1/auth/login`, writes cookie jar, exports `CSRF_TOKEN`.
- `mut <METHOD> <PATH> <JSON_BODY>` — auto-attaches `Idempotency-Key: $(uuidgen)` + `X-CSRF-Token` + reuses cookie jar. **This is the idempotency-key-replay seam for VER-01** — to replay a key, capture the `uuidgen` value rather than letting `mut` mint a fresh one (see N1).
- `get <PATH>` — read-only GET.
- `psql_exec <SQL>` — `psql "postgresql://app:app@localhost:5432/sportzal"`.
- `assert_status <code>` / `assert_body_jq <expr> <value>` — pipe-friendly assertions.

**Locked credential fact (`_lib.sh:28-30`, `_preflight.sh:67-70`):** Postgres creds
are `app:app` (NOT `sportzal:sportzal`). CONTEXT text elsewhere may say otherwise —
PATTERNS is authoritative here.

### S2. HTTP-response parsing idiom (status line + body split)
**Source:** `08_cross_phase_smoke.sh:46-50`, `01_sale_with_payment.sh:50-59`.
**Apply to:** every assertion in new scenarios.

```bash
B1="$(mktemp)"
mut POST /api/v1/memberships "{\"clientId\":\"$CLIENT_ID\",\"planId\":\"$PLAN_ID\"}" > "$B1"
cat "$B1"
[ "$(head -1 "$B1" | awk '{print $2}')" = "201" ] || { echo "result: FAIL — expected 201"; exit 1; }
# strip headers (everything up to and incl. first blank line), then jq the body:
ID="$(awk 'BEGIN{p=0} /^\r?$/{p=1; next} p{print}' "$B1" | jq -r '.data.id')"
```

### S3. DB-constraint-as-arbiter race assertion (the canonical VER-02 shape)
**Source:** `tests/integration/payments/test_payments_refund_race.py:139-205`.
**Apply to:** all four VER-02 race tests.

The race contract is always: fire N concurrent requests with `asyncio.gather`,
assert **exactly `1×200 + (N-1)×409`** and **exactly 1 surviving DB row** —
proving the DB UNIQUE (not app-layer guards) serialised the race. App-layer
SELECT-then-WRITE is TOCTOU and cannot win.

```python
n_concurrent = 5
responses = await asyncio.gather(*[_post(i) for i in range(n_concurrent)])
statuses = sorted(r.status_code for r in responses)
assert statuses == [200] + [409] * (n_concurrent - 1)
# DB invariant: exactly 1 surviving row on the partial/full UNIQUE
count = await db_session_real_commit.scalar(
    select(func.count()).select_from(Payment).where(Payment.refund_of == sale_payment.id)
)
assert count == 1
```

---

## Pattern Assignments

### `apps/backend/scripts/verify/v1_7_runbook.sh` (operator-orchestrator, request-response)

**Analog:** `scripts/verify/README.md:14-26` (sweep loop) — but the runbook is a
top-level orchestrator script that reuses `_preflight.sh` + iterates the new `NN_*.sh`.

The harness today has **no orchestrator script** — the operator runs a `for` loop
manually from the README. D-01 promotes that loop into `v1_7_runbook.sh`. Mirror
the README recipe, gating on `_preflight.sh` first.

**Orchestrator skeleton (adapt from `README.md:16-26`):**
```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$SCRIPT_DIR/_preflight.sh"   # 10-check readiness gate; aborts RED
for s in "$SCRIPT_DIR"/09_*.sh "$SCRIPT_DIR"/1[0-9]_*.sh; do  # new v1.7 scenarios past 08
  echo "--- $s ---"
  bash "$s" || { echo "FAILED: $s — see evidence file"; exit 1; }
done
```

**Preflight extension note (`_preflight.sh:34-78`):** `_preflight.sh` is labelled
"Phase 36 pre-flight". If the runbook needs a new readiness check (e.g. ARQ worker
up, Redis reachable for dedup), add a `check "..." '...'` line following the
existing `check()` pattern (`_preflight.sh:23-32`). The Postgres-reachable check at
`:67-70` already uses the correct `app:app` creds.

---

### `apps/backend/scripts/verify/NN_*.sh` — VER-01 walkthrough (operator-scenario)

**Analog:** `08_cross_phase_smoke.sh` (multi-step single-evidence-file scenario) +
`01_sale_with_payment.sh` (sale → payments-by-membership assertion).

The VER-01 order is fixed (CONTEXT line 100): **sell → `payment.succeeded`
webhook → membership activated → `fiscal_receipts` row → refund → idempotency-key
replay returns idempotent 200.** Build it as a stepped scenario in the
`08_cross_phase_smoke.sh` mold (numbered `stepN_<name>` echo headers,
`mktemp` per step, hard `exit 1` on mismatch).

**Step structure to copy (`08_cross_phase_smoke.sh:41-103`):** each step does
`mut/get → cat → head -1 assert → awk-body jq assert → echo PASS`.

**Webhook step — D-02 trusted-IP `payment.succeeded` POST (the load-bearing new part):**
The runbook POSTs the webhook payload directly to our own intake endpoint
`POST /api/v1/_internal/yookassa/webhook` (router: `app/api/v1/_internal/yookassa/router.py:62-66`,
mounted at that prefix per `app/api/v1/router.py:90-95`). Body shape (verbatim
from `tests/integration/fiscal_receipts/test_e2e_fiscal_receipt_full_cycle.py:271-281`):

```json
{
  "event": "payment.succeeded",
  "object": { "id": "<yk_payment_id>", "status": "succeeded",
              "amount": {"value": "1000.00", "currency": "RUB"} }
}
```

The endpoint is anonymous (no cookie/CSRF) but **gated by `verify_yookassa_ip`**
(`app/integrations/yookassa/webhook_verifier.py:64-110`). The verifier reads
`request.client.host` and short-circuits when `settings.sandbox` is True
(`webhook_verifier.py:84-86`). For the runbook against the compose stack, the
trusted-IP path means either: (a) run with `YOOKASSA_SANDBOX=true` (sandbox bypass,
mirrors how integration tests pass — `webhook_yookassa/conftest.py:603-604`), or
(b) ensure the curl origin is in `YOOKASSA_TRUSTED_IPS`. Sandbox bypass is the
deterministic operator choice. Webhook curl shape (raw curl, NOT `mut` — no
cookie/CSRF/idempotency header):

```bash
curl -i -s -X POST "$BASE_URL/api/v1/_internal/yookassa/webhook" \
  -H 'Content-Type: application/json' \
  -d "{\"event\":\"payment.succeeded\",\"object\":{\"id\":\"$YK_PAYMENT_ID\",\"status\":\"succeeded\",\"amount\":{\"value\":\"1000.00\",\"currency\":\"RUB\"}}}"
# expect: HTTP 200, body "ok" (text/plain) — see router.py:154
```

**`fiscal_receipts` row confirmation step:** after the webhook, the
`handle_payment_succeeded` handler inserts a `FiscalReceipt(status='sent')` row
synchronously (`router.py:115-124`; confirmed by E2E test
`test_e2e_fiscal_receipt_full_cycle.py:285-300`). Confirm via `psql_exec`:
```bash
psql_exec "SELECT id, kind, status FROM fiscal_receipts ORDER BY id DESC LIMIT 1;"
```
Note: webhook dedup uses `SET NX EX 86400` on `sz:yookassa:webhook:{event}:{object_id}`
(`router.py:105-113`). For a re-runnable hermetic scenario, flush that Redis key (or
use a fresh `object_id` per run) — same concern the E2E suite handles via
`_flush_webhook_dedup_keys` (`test_e2e_fiscal_receipt_full_cycle.py:230`).

**Refund + idempotency-replay step:** use `mut POST /api/v1/online-payments/.../refund`
(refund endpoints live appended to `app/modules/online_payments/router.py:402-475`,
return 202; completion awaits the `refund.succeeded` webhook). For the
idempotency-replay assertion, capture the `Idempotency-Key` once and replay the
SAME key — expect an idempotent 200/2xx with no second side-effect (see N1).

---

### VER-02 race tests `tests/integration/online_payments/test_*_race.py` (integration race test, concurrent-write)

**Analogs:**
- `tests/integration/payments/test_payments_refund_race.py` (partial-UNIQUE-on-`refund_of`; full file is the template).
- `tests/integration/test_concurrent_expiring_cron_double_pings_race.py` (in-process `asyncio.gather` of the same helper + standalone real-commit engine + Redis flush).
- `tests/integration/memberships/conftest.py:306-341` (the `db_session_real_commit` fixture definition).

**Fixture acquisition (D-03 — NO new dependency):** Use `db_session_real_commit`.
For tests under `online_payments/`, either depend on a conftest that re-exports the
fixture (the payments suite does this — `tests/integration/payments/conftest.py:27`
imports it) OR build a standalone real-commit engine inline (the cron-double-pings
test does this — `test_concurrent_expiring_cron_double_pings_race.py:51-91`). The
inline-engine variant is preferred when the test seeds tables outside the fixture's
TRUNCATE set. Both patterns: `create_async_engine(str(settings.database_url),
pool_pre_ping=True)` + `async_sessionmaker(engine, expire_on_commit=False)`, then
TRUNCATE-CASCADE at teardown. The cron test also defensively `pytest.skip`s on
unreachable Postgres (`:70-78`) — copy that guard.

**Why real-commit (rationale to preserve in the docstring):** SAVEPOINT-isolated
`db_session` composes nested transactions; concurrent INSERTs cannot race against a
UNIQUE inside a single outer SAVEPOINT, and savepoint rollback masks the loser's
`IntegrityError` (`test_payments_refund_race.py:6-13`, `memberships/conftest.py:308-319`).

**ASGITransport authed-client helper (`test_payments_refund_race.py:42-54`):**
```python
async def _build_authed_client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://testserver")
    r = await client.post("/api/v1/auth/login", json={"email": ..., "password": ...})
    assert r.status_code == 200
    return client
# csrf for mutating verbs: csrf = authed.cookies.get("sportzal_csrf"); headers={"X-CSRF-Token": csrf}
```

**`asyncio.gather` race body (`test_payments_refund_race.py:139-162`):** flush Redis
first (`await app.state.redis.flushdb()` — `:139`) so dedup/idempotency keys don't
bleed; gather N posts; assert `[200] + [409]*(N-1)`; assert exactly 1 surviving
row. See Shared Pattern S3.

**The four VER-02 scenarios and their constraint arbiters:**

| Scenario | Concurrency surface | DB arbiter / proof |
|----------|---------------------|--------------------|
| (a) concurrent `payment.succeeded` double-delivery | gather N webhook POSTs to `/_internal/yookassa/webhook`, same `object.id` | Redis dedup `SET NX EX` (`router.py:106`) **AND** DB UNIQUE on online_payment status/idempotency. Prove BOTH: assert dedup short-circuits (1 handler run) AND one fiscal_receipts row. |
| (b) webhook after Redis restart | flush the dedup key (`sz:yookassa:webhook:...`) between deliveries to simulate the restart gap, re-deliver same `object.id` | the DB UNIQUE is the **sole** catcher (CONTEXT line 101) — assert second delivery does not double-insert. |
| (c) concurrent refund webhook + manual refund command | gather a `refund.succeeded` webhook against a concurrent manual refund | partial UNIQUE `uq_payments_refund_of_alive` on `(refund_of) WHERE refund_of IS NOT NULL` arbitrates (`test_payments_refund_race.py:5-13,170-182`); exactly 1 refund row. |
| (d) concurrent kopecks↔rubles edge values | parallel sells/webhooks with Decimal-edge amounts | assert Decimal precision via the yookassa `_money` conversion (`app/integrations/yookassa/_money.py`); no rounding drift across kopecks↔rubles. |

**Redis dedup key shape to flush (scenario b):** `sz:yookassa:webhook:{event_type}:{object_id}`,
prefix `WEBHOOK_DEDUP_KEY_PREFIX` (`router.py:56`).

---

### DEFER-46-03 re-run — scenario-08 cron-chain circuit-breaker (FISCAL-05 parity) (one-shot cron-runner)

**Analog:** `apps/backend/scripts/run_expiring_cron_once.py` (one-shot in-process
`async def` cron invocation against the live stack, bypassing ARQ scheduling).

**What to re-run (D-05 / VER-05):** the v1.6 VER-09 scenario-08 cron-chain
circuit-breaker open-state fixture, now exercising the **FISCAL-05 circuit breaker**
in `app/modules/fiscal_receipts/tasks.py` (the dispatch task) backed by
`app/integrations/yookassa/circuit_breaker.py`. Assert parity with the v1.6
expectation that the v1.6 run recorded only as PARTIAL.

**Circuit-breaker contract to assert against (`circuit_breaker.py:1-60`, locked D-51-14):**
- Threshold: **5 failures / 60s → open**; open TTL **300s**; provider `"receipts"` → key `sz:yookassa:circuit:receipts`.
- `is_circuit_open(redis, provider)` is an O(1) `EXISTS` at the head of `dispatch_fiscal_receipt` (`fiscal_receipts/tasks.py:274-277`).
- `record_failure` ZADDs into the sliding window and SETs the open-marker when threshold crossed (`tasks.py:346` + `circuit_breaker.py` ZADD/ZREMRANGEBYSCORE/ZCARD).

**One-shot runner pattern to copy (`run_expiring_cron_once.py:67-105`):**
- Local-DB safety gate (refuse non-`localhost`/`postgres:5432` `DATABASE_URL`) — `:69-76`.
- Build ARQ ctx manually: `redis_pool = await create_pool(WorkerSettings.redis_settings)`; `ctx = {"redis": redis_pool}`; `await WorkerSettings.on_startup(ctx)` — `:93-98`. **Do NOT re-implement the DB lifespan inline** (MH-29-05) — call the staticmethod.
- `try/finally: await WorkerSettings.on_shutdown(ctx); await redis_pool.aclose()` — `:99-104`.
- Eager-import the FK-target model modules touched by the task before the session opens (`run_expiring_cron_once.py:49-62` does this for the expiring cron) — the fiscal variant must eager-import `fiscal_receipts.models` + `online_payments.models` + audit FK targets.

This may equivalently be expressed as an integration test that pre-opens the
breaker (5 `record_failure` calls or directly SET the marker) then asserts
`dispatch_fiscal_receipt` short-circuits with a Retry/no-POST — see the existing
unit test `tests/unit/test_yookassa_circuit_breaker.py` for the breaker primitive
assertions to mirror. The planner picks runner-script vs test per the VER-05 phrasing.

---

### `.planning/handoff/v1.7-yookassa-sandbox-evidence/README.md` (evidence scaffold, operator-handoff)

**Analog:** `.planning/handoff/v1.7-email-deliverability-evidence/README.md` (whole
file — the Phase 52 CARRY-01 operator-pending template).

D-04 makes VER-03 operator-pending, modeled exactly on CARRY-01/02. Ship ONLY the
directory + README; the owner runs the real ЮKassa sandbox session. Copy the
README section structure verbatim from the email-deliverability README:

1. **Title + frontmatter** — Phase, Requirement (VER-03), Decision refs (`README.md:1-7`).
2. **Purpose** — agent ships scaffolding, operator runs live session (`:9-18`).
3. **Required Environment Variables** — table of ЮKassa sandbox creds (shop ID, secret key) (`:21-33`).
4. **Security note** — never commit real creds; redact (`:35-37`).
5. **Run Command / Walkthrough** — the sandbox dashboard steps (sell → pay in sandbox → confirm callback) (`:41-58`).
6. **What to Capture** — screenshots/session log of the sandbox payment + the resulting local webhook/fiscal state (`:62-77`).
7. **Evidence File Format** — one file per artifact; redacted (`:81-129`).
8. **Acceptance Criteria for VER-03 closure** — checklist (`:133-145`).
9. **Scaffolding Attestation** — agent attests scaffolding ready, operator deliverable (`:149-161`).

Evidence path is **locked** (CONTEXT line 102): `.planning/handoff/v1.7-yookassa-sandbox-evidence/`.

---

## No Analog Found

None. Every artifact maps to a concrete existing analog. The only "new" construct
is the `v1_7_runbook.sh` *orchestrator file* itself, but its body is a direct
promotion of the `README.md:16-26` sweep loop + `_preflight.sh` gate.

---

## Notes for the Planner (N)

**N1 — Idempotency-key replay seam (VER-01 final step).** `_lib.sh:94-104` `mut()`
mints a fresh `uuidgen` per call. To prove idempotent replay you must hold the key
constant across two calls. Either add a runbook-local helper that accepts an
explicit key, or inline the curl with a captured `IDEM="$(uuidgen)"` reused on both
the first and replay POST. The replay must return an idempotent 2xx with no second
DB side-effect. The online-payments sell endpoints already wrap an
`_outer_idempotency_replay_or_run` (`online_payments/router.py:319-324`) — that is
the server-side seam the replay exercises.

**N2 — psql time-travel is sanctioned (D-36-05 lineage).** Mid-scenario `psql`
mutation (cleanup, time-travel) is allowed; log intent in the scenario comment AND
in VERIFICATION-LOG.md `notes:` (`_lib.sh:114-120`). The existing scenarios use
psql `DELETE` cleanup at the top for hermetic re-runs (`01_sale_with_payment.sh:30-35`).

**N3 — Inline-regression hard cap = 5 (D-05 / D-36-15..17).** Any failure →
reproduce → fix as own commit `fix(53-NN): REG-53-XX <desc>` → re-run → log in
VERIFICATION-LOG.md `overrides:`. At >5, block and roll excess to v1.8 DEFER
(`_lib.sh:149-153`, `README.md:33`).

**N4 — Evidence output dir.** Existing scenarios tee to
`.planning/milestones/v1.4-verification-evidence/`. New v1.7 scenarios should tee to
a v1.7 sibling (e.g. `.planning/milestones/v1.7-verification-evidence/`) — planner
decides exact name; keep the `exec > >(tee "$EVIDENCE") 2>&1` idiom
(`08_cross_phase_smoke.sh:18-20`).

---

## Metadata

**Analog search scope:** `apps/backend/scripts/verify/`, `apps/backend/tests/integration/{payments,memberships,online_payments,webhook_yookassa,fiscal_receipts}/`, `apps/backend/app/{api/v1/_internal/yookassa,modules/online_payments,modules/fiscal_receipts,integrations/yookassa}/`, `apps/backend/scripts/`, `.planning/handoff/`.
**Files scanned:** ~20 (read in full or targeted ranges).
**Pattern extraction date:** 2026-05-23
