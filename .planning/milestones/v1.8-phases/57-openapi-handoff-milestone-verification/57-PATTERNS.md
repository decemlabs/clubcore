# Phase 57: OpenAPI Handoff + Milestone Verification - Pattern Map

**Mapped:** 2026-05-24
**Files analyzed:** 5 targets (2 regenerated artifacts, 1 contract-test extension, 1+ new backend test file, 1 new runbook)
**Analogs found:** 5 / 5 (all exact in-repo)

> This is a close-out / proof phase. The machinery is LOCKED by v1.4–v1.7 precedent.
> Every analog is an exact in-repo file; the executor copies the established idiom verbatim
> and only swaps in the v1.8 surface. No new mechanisms.

---

## CRITICAL UPSTREAM FINDING (affects D-03)

`apps/backend/openapi.json` was last written **May 20 18:41** (before the reports module
was created **May 24 ~20:46**). Grep confirms **zero** `/reports/*` and `/audit-log*` paths
currently present in EITHER `apps/backend/openapi.json` OR `packages/api-client/src/schema.d.ts`.

**Implication:** Contrary to D-03's "may produce no diff," regen **WILL produce a real diff**
adding all 8 v1.8 paths. The plan must:
1. Run regen (HND-01/HND-02) — expect a non-empty diff on both artifacts.
2. Commit it: `chore(57-NN): regen openapi.json + schema.d.ts for v1.8 surface`.
3. Only then will the new `_v18Checks` in `schema.contract.test.ts` typecheck (the types are
   declared against `paths['/api/v1/reports/revenue']` etc., which do not exist in the schema
   until regen lands). **Ordering matters: regen artifacts BEFORE adding the contract guards**,
   or the same plan/wave must do both so `tsc` stays green.

---

## The 8 v1.8 paths (verified against router + mounts)

Routes from `apps/backend/app/modules/reports/router.py` + mounts in
`apps/backend/app/api/v1/router.py:79-80` (`reports_router` → `/reports`,
`audit_log_router` → `/audit-log`):

| # | OpenAPI path | Method | Source decorator |
|---|--------------|--------|------------------|
| 1 | `/api/v1/reports/revenue` | get | `router.py:61` |
| 2 | `/api/v1/reports/clients` | get | `router.py:85` |
| 3 | `/api/v1/reports/visits` | get | `router.py:110` |
| 4 | `/api/v1/reports/revenue.csv` | get | `router.py:143` |
| 5 | `/api/v1/reports/clients.csv` | get | `router.py:168` |
| 6 | `/api/v1/reports/visits.csv` | get | `router.py:191` |
| 7 | `/api/v1/audit-log` | get | `router.py:220` (audit_log_router `""`) |
| 8 | `/api/v1/audit-log.csv` | get | `router.py:254` (audit_log_router `".csv"`) |

Note: the 4 CSV endpoints respond 200 with `text/csv` (not JSON). The forward-guard should
anchor `['responses']['200']` for them (no `requestBody` — they are GETs).

---

## File Classification

| Target File | Role | Data Flow | Closest Analog | Match Quality |
|-------------|------|-----------|----------------|---------------|
| `apps/backend/openapi.json` | config / generated artifact | transform (FastAPI→JSON) | itself + `scripts/export_openapi.py` | exact (regen-in-place) |
| `packages/api-client/src/schema.d.ts` | config / generated artifact | transform (JSON→TS) | itself + `package.json` codegen | exact (regen-in-place) |
| `packages/api-client/src/schema.contract.test.ts` | test (type+runtime) | request-response (type-level) | `_v16UsersChecks` / `_v15Checks` blocks in same file | exact (same file) |
| NEW `apps/backend/tests/integration/reports/test_reports_dst.py` (or merged) | test (integration) | CRUD / transform | `test_reports_revenue.py` + `test_reports_visits.py` | exact (sibling) |
| NEW RBAC-denial + pagination assertions | test (integration) | request-response / event-driven | `test_audit_log.py` `test_reception_forbidden` + `test_pagination_stability_under_concurrent_insert` | exact (sibling) |
| NEW `.planning/handoff/v1.8-reports-runbook.md` | doc / runbook | n/a | `.planning/handoff/v1.4-auth-runbook.md` | exact (template) |

---

## Pattern Assignments

### `apps/backend/openapi.json` (regenerated artifact)

**Analog / generator:** `apps/backend/scripts/export_openapi.py` — **NO EDITS** (D-01).

**Regen command** (run from `apps/backend/`):
```bash
uv run python -m scripts.export_openapi
```

**Byte-stability guarantee** (`export_openapi.py:60-65`) — already correct, do not touch:
```python
payload = json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
target = pathlib.Path(__file__).resolve().parents[1] / "openapi.json"
target.write_text(payload, encoding="utf-8")
```
The script calls `create_app().openapi()` directly (no lifespan → no DB/Redis), so regen runs
in any env (`export_openapi.py:46-51`). CI drift gate `.github/workflows/ci.yml:50-64`
(`git diff --exit-code`, guarded by `git ls-files --error-unmatch`) must end green.

**What to replicate:** Nothing in the script. Just run it, verify the 8 paths now appear
(`grep -c '/api/v1/reports/revenue' apps/backend/openapi.json` ≥ 1), commit the diff.

---

### `packages/api-client/src/schema.d.ts` (regenerated artifact)

**Analog / generator:** `packages/api-client/package.json` `codegen` script — **NO EDITS** (D-02).

**Regen command:**
```bash
pnpm --filter @sportzal/api-client codegen
# → openapi-typescript ../../apps/backend/openapi.json --output src/schema.d.ts
```
Downstream of `openapi.json` — regen `openapi.json` FIRST. CI frontend drift gate
`.github/workflows/ci.yml:105-117` must stay green.

**What to replicate:** Nothing in config. Run, verify v1.8 paths land in the `paths` interface,
commit.

---

### `packages/api-client/src/schema.contract.test.ts` (ADD `_v18Checks` block)

**Analog:** the EXISTING `_v16UsersChecks` block in the SAME file — `schema.contract.test.ts:292-336`
(declaration → tuple) and the runtime block at `:373-375`. The `_v15Checks` 2xx-reachability
anchor at `:268-285` is the template for the CSV `['responses']['200']` guards.

**Type-alias + AssertNonNever idiom** (copy exact shape from `:292-300`):
```typescript
type _UsersListGet = AssertNonNever<paths['/api/v1/users']['get']>
type _UsersDeactivatePatch = AssertNonNever<
  paths['/api/v1/users/{user_id}/deactivate']['patch']
>
```

**Helper already present** (`:15`, `:21`) — reuse, do not redeclare:
```typescript
type AssertNonNever<T> = [T] extends [never] ? false : true
```

**Tuple-of-true idiom** (copy from `_v16UsersChecks` at `:330-336`):
```typescript
const _v16UsersChecks: [
  _UsersListGet,
  _UsersCreatePost,
  _UsersDeactivatePatch,
  _UsersReactivatePatch,
  _UsersDelete,
] = [true, true, true, true, true]
```

**Runtime `it()` block** (copy from `:373-375`, NEW per-surface block — do NOT mutate the
frozen v1.2=10 / v1.4=36 / v1.5=11 / v1.6=5/4/2 blocks at `:354-383`):
```typescript
it('compiles against the regenerated v1.6 USERS surface (Phase 43)', () => {
  expect(_v16UsersChecks).toHaveLength(5)
})
```

**What to replicate for v1.8 (D-04/D-05):** Add 8 `type _v18...= AssertNonNever<paths[...]['get']>`
aliases (one per path in the table above), a `const _v18Checks: [ ...8 aliases ] = [true ×8]`
tuple, and a new `it('compiles against the regenerated v1.8 reports/audit surface (Phases 55-57)', () => { expect(_v18Checks).toHaveLength(8) })`.
For the 4 CSV GETs prefer the 2xx-reachability anchor form (`['get']['responses']['200']`) per the
`_v15Checks` `_TrainerSlotsListOkRealised` example at `:268-270`. Alias casing is Claude's
discretion (D-138). All 8 paths are LANDED post-regen → hard `AssertNonNever`, NO `HasPath<>`
conditional probe.

---

### NEW backend correctness tests — `apps/backend/tests/integration/reports/`

> D-06: REUSE existing infra. Files live in this dir on the SAVEPOINT-per-test conftest.
> Whether the DST test is a new file or merged into `test_reports_revenue.py`/`test_reports_visits.py`
> is Claude's discretion (D-141). Fixtures already exist — do NOT add new factories.

**Fixtures available** (`tests/integration/reports/conftest.py`):
- `authed_client_owner`, `authed_client_reception` (re-exported from memberships conftest, `:18-30`)
- `make_payment_ledger` (`:33-65`) — `received_at: datetime` is explicit/deterministic
- `make_visit` (`:68-99`) — `checked_in_at: datetime`; **gym_date is STORED GENERATED** via
  `(checked_in_at AT TIME ZONE 'Europe/Moscow')::date` — do NOT pass gym_date (`:74-79`)
- `make_audit_log_row` (`:102-140`) — explicit `created_at`
- `make_client`, `make_membership`, `make_plan`, `seeded_owner`

#### (a) DST-boundary golden test (D-07) — analog `test_reports_revenue.py` + `test_reports_visits.py`

The real assertion (RU has no DST since 2014) is **+03:00 MSK offset stability at UTC-midnight
boundaries**: a payment/visit at `23:30Z` must bucket into the **NEXT** MSK day.

**Analog idiom — MSK-day bucketing assertion** (`test_reports_revenue.py:67-91`):
```python
msk_ts = datetime(2026, 5, 15, 10, 0, 0, tzinfo=UTC)  # well within window
await make_payment_ledger(
    subject_id=mem.id, amount_kopecks=250000, method="cash",
    received_at=msk_ts, received_by_user_id=seeded_owner.id,
)
...
buckets = r.json()["data"]["buckets"]
day_bucket = next((b for b in buckets if b["period"] == "2026-05-15"), None)
assert day_bucket is not None
assert day_bucket["netKopecks"] == 0
```

**Analog idiom — the UTC↔MSK offset comment convention** (`test_reports_visits.py:78-81`):
```python
# Both visits on 2026-08-10 MSK (UTC+3 → 07:00 UTC is 10:00 MSK = same MSK day)
msk_day = datetime(2026, 8, 10, 7, 0, 0, tzinfo=UTC)  # 2026-08-10 10:00 MSK
```

**What to replicate:** Insert a payment AND a visit at e.g. `datetime(2026, 1, 1, 21, 30, tzinfo=UTC)`
(21:30Z = 00:30 MSK on 2026-01-02) and assert the revenue `period` / visits `daily[].date` is
`2026-01-02` (next MSK day), not `2026-01-01`. Use known deterministic kopeck amounts net-of-refund.
**These exact amounts/dates MUST equal the runbook's golden-path numbers (D-11 scenario 2)** so the
operator can eyeball-match.

#### (b) Pagination-stability race test (D-08) — analog ALREADY EXISTS

`test_audit_log.py:304-402` `test_pagination_stability_under_concurrent_insert` already covers
the keyset-`created_at DESC, id DESC` no-shift case (inserts an OLDER row mid-pagination, asserts
page-1/page-2 ID sets unchanged). Per D-08, **EXTEND, do not duplicate**. If a NEWER-row insertion
variant is wanted, add an `it`/test alongside it using the same `page1_ids = {item["id"] for ...}`
set-equality idiom (`:339`, `:397-402`).

#### (c) Explicit reception-403 RBAC denial (D-09) — analog ALREADY EXISTS, assert exact shape

Both `test_reports_revenue.py:43-52` and `test_audit_log.py:47-53` already assert reception 403.
The exact idiom to replicate (note the `code == "forbidden"` body assertion):
```python
async def test_reception_forbidden(authed_client_reception: AsyncClient) -> None:
    r = await authed_client_reception.get("/api/v1/audit-log")
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"
```
Roadmap SC#4 wants explicit reception → `GET /api/v1/reports/revenue` 403 AND reception →
`GET /api/v1/audit-log` 403. Both exist; confirm presence and (if gaps) mirror this idiom for any
missing path. RBAC pairs `(VIEW, REPORTS)` + `(LIST, AUDIT_LOG)` are owner-only in
`apps/backend/app/core/permissions.py`.

**Test module conventions** (apply to any new file): module docstring listing coverage + requirement
IDs; `from __future__ import annotations`; `from datetime import UTC, datetime`; `from typing import Any`;
`from httpx import AsyncClient`; async test functions named `test_...`; fixtures typed `: Any` in
signature; `assert r.status_code == 200, r.text`.

---

### NEW `.planning/handoff/v1.8-reports-runbook.md` (operator runbook)

**Analog:** `.planning/handoff/v1.4-auth-runbook.md` (full file, 146 lines).

**Header block to replicate** (`v1.4-auth-runbook.md:1-13`):
```markdown
# Sportzal ... Runbook (v1.8 DRAFT)

> **v1.8 DRAFT** — ...

**Audience:** ...
**Backend version:** v1.8 (commit `<sha>`+ ...).
**Source-of-truth contract:** `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts`.
```

**Sectioned-curl idiom** (`v1.4-auth-runbook.md:15-33`) — numbered `## N. Title`, Russian prose
referencing `file:line`, then a fenced `bash` curl with expected response described after:
```markdown
## 1. Login as owner / reception
... prose referencing apps/backend/app/modules/.../router.py:NN-NN ...
```bash
curl -i -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" -c cookies.txt \
  -d '{"email":"...","password":"..."}'
```
При успехе: `HTTP/1.1 200 OK` + ...
```
Owner/reception token bootstrap reuses §1's `cookies.txt` jar + the
`CSRF=$(awk '/sportzal_csrf/ {print $7}' cookies.txt)` pattern (`:77`, `:123`) for any
reception-token curl (D-09/D-11 scenario 4). Token bootstrap details are Claude's discretion (D-144).

**Operator attestation block** (copy exactly from `v1.4-auth-runbook.md:143-145`):
```markdown
## Operator

andre.shipunov@icloud.com
```

**What to replicate (D-10/D-11):** 5 numbered scenarios — (1) `docker compose up` bring-up
(services in `apps/backend/docker-compose.yml`); (2) revenue golden-path with the SAME deterministic
kopeck amounts/dates as the VER-02 DST/golden test; (3) audit-log filter narrowing
(`?actorUserId=&action=&resourceType=&from=&to=`, see `test_audit_log.py:132-189`);
(4) reception 403 on `/reports/*` + `/audit-log` (reception-token curl); (5) CSV download of all
four `.csv` endpoints + "open in Excel, confirm Cyrillic renders (no mojibake)" — the live
validation of Phase 56 D-13. End with the operator attestation block.

**Operator-pending pattern** (D-12): live `docker compose up` walkthrough is authored now, executed
later — recorded as an operator-pending STATE.md item, not a phase blocker. Precedent:
`.planning/handoff/v1.7-email-deliverability-evidence/README.md`. Optional `v1.8-postman.json`
(v1.4 had one at `.planning/handoff/v1.4-postman.json`) is a deferred nicety — curl-only is sufficient.

---

## Shared Patterns

### SAVEPOINT-per-test isolation
**Source:** `apps/backend/tests/integration/reports/conftest.py` (re-exports from memberships conftest)
**Apply to:** all new backend tests. Fixtures `make_payment_ledger`/`make_visit`/`make_audit_log_row`
commit on the SAVEPOINT-mode `db_session` so teardown rolls back. Use these — never write raw inserts
or add new factories.

### Deterministic UTC→MSK timestamps
**Source:** `test_reports_visits.py:78-81`, `test_reports_revenue.py:67`
**Apply to:** DST golden test + any bucketing assertion.
```python
msk_day = datetime(2026, 8, 10, 7, 0, 0, tzinfo=UTC)  # 2026-08-10 10:00 MSK (UTC+3)
```
Always `tzinfo=UTC` on the input; assert the MSK calendar date in the response. Never pass `gym_date`.

### Byte-stable artifact + CI drift gate
**Source:** `scripts/export_openapi.py:60-65`, `.github/workflows/ci.yml:50-64` (backend), `:105-117` (frontend)
**Apply to:** both regenerated artifacts. Success bar = "regen produces a committed diff, then
`git diff --exit-code` is green." `git ls-files --error-unmatch` guards against gitignore pass-through.

### Additive contract assertions
**Source:** `schema.contract.test.ts:329-383`
**Apply to:** `_v18Checks` only. NEVER mutate the frozen v1.2/v1.4/v1.5/v1.6 count blocks
(10/36/11/5/4/2). Add a new `const _v18Checks` + a new `it()` with `toHaveLength(8)`.

### ResponseEnvelope assertion shape
**Source:** `test_reports_revenue.py:35-40`, `test_audit_log.py:34-44`
**Apply to:** all new integration assertions. JSON GETs return `{"data": {...}}`; list endpoints
return `data` with `items/total/page/pageSize`. Errors carry top-level `code` (`"forbidden"`,
`"report_range_too_large"`, `"audit_filter_invalid"`).

---

## No Analog Found

None. Every target file has an exact in-repo analog (most are regenerated-in-place or sibling tests).

---

## Metadata

**Analog search scope:** `apps/backend/scripts/`, `apps/backend/tests/integration/reports/`,
`apps/backend/app/modules/reports/`, `apps/backend/app/api/v1/`, `packages/api-client/`,
`.planning/handoff/`, `.github/workflows/`
**Key freshness finding:** `openapi.json` (May 20) predates the reports module (May 24) → regen
will diff; verify-then-commit per D-03.
**Pattern extraction date:** 2026-05-24
