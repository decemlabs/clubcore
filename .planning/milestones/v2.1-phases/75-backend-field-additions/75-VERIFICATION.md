---
phase: 75-backend-field-additions
verified: 2026-06-02T17:00:00Z
status: passed
score: 6/6
overrides_applied: 0
re_verification: false
---

# Phase 75: Backend Field Additions — Verification Report

**Phase Goal:** The client membership response exposes price and auto-renewal status; `/client/me` accepts and persists notification preferences; the FIT15 promo code is seeded and validates via the existing endpoint.
**Verified:** 2026-06-02T17:00:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `GET /client/membership` response includes `priceKopecks` (integer) and `autoRenew` (null) [PMEM-01] | VERIFIED | `ClientMembershipResponse` declares `price_kopecks: int` and `auto_renew: bool \| None`; service constructs with `price_kopecks=int(r["price_kopecks_snapshot"])` and `auto_renew=None`; integration test asserts `isinstance(data["priceKopecks"], int)` and `data["autoRenew"] is None` — passes |
| 2 | `PATCH /client/me` accepts `notifPrefs` with exactly 4 bool keys and persists it; `GET /client/me` returns the persisted value [NOTIF-01] | VERIFIED | `NotifPrefs(BackendSchemaBase)` with `extra="forbid"` defines promo/schedule/trainer/sound; repository `update_client_profile` appends `notif_prefs = CAST(:notif_prefs AS jsonb)` fragment; integration round-trip test passes |
| 3 | `GET /client/me` returns server defaults `{promo:true, schedule:true, trainer:true, sound:false}` when column is NULL [NOTIF-01 D-06] | VERIFIED | `_NOTIF_DEFAULTS` defined in service.py; `get_client_me` applies it when `notif_prefs IS NULL`; integration test asserts `promo=True` and `sound=False` on a fresh client — passes |
| 4 | `PATCH /client/me` with an unknown `notifPrefs` key is rejected with 422 [NOTIF-01 D-04] | VERIFIED | `NotifPrefs` inherits `BackendSchemaBase` (`extra="forbid"`), not `ResponseData` (`extra="ignore"`); integration test sends `{"bogus": true}` and asserts `status_code == 422` — passes |
| 5 | `POST /client/promo/validate` with code `"FIT15"` returns a valid percentage discount response on a clean DB [PROMO-01] | VERIFIED | Migration 0051 inserts FIT15 with `discount_type='percentage'`, `discount_value=1500`, `per_client_limit=1`, `is_active=TRUE`, `applicable_to=NULL`; Test C asserts HTTP 200, `discountType=percentage`, `discountKopecks=15000`, `newAmountKopecks=85000` — passes |
| 6 | FIT15 seed migration is idempotent (re-run is a no-op) [PROMO-01] | VERIFIED | `ON CONFLICT (upper(code)) WHERE deleted_at IS NULL DO NOTHING`; Test B re-executes the SQL and asserts `count(*) == 1` — passes |

**Score:** 6/6 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/app/modules/client_portal/schemas.py` | `class NotifPrefs(BackendSchemaBase)`; `price_kopecks: int` + `auto_renew: bool \| None` on `ClientMembershipResponse`; `notif_prefs` on request+response | VERIFIED | All declared. Docstring updated per D-75-03. |
| `apps/backend/app/modules/clients/models.py` | `notif_prefs: Mapped[dict[str, Any] \| None] = mapped_column(JSONB, nullable=True)` | VERIFIED | Line 129-132 — mirrors `emergency_contact` JSONB pattern exactly. |
| `apps/backend/alembic/versions/0050_clients_notif_prefs.py` | Additive nullable JSONB column; `down_revision = "0049_fiscal_receipts_customer_phone"` | VERIFIED | Revision and down_revision confirmed; upgrade adds column, downgrade drops it. |
| `apps/backend/alembic/versions/0051_seed_fit15_promo.py` | Idempotent FIT15 seed; `down_revision = "0050_clients_notif_prefs"`; soft-delete downgrade | VERIFIED | `ON CONFLICT (upper(code)) WHERE deleted_at IS NULL DO NOTHING`; downgrade `UPDATE ... SET deleted_at = now()`; chain confirmed. |
| `apps/backend/tests/modules/client_portal/test_notif_prefs_service.py` | Service-layer tests for defaults, persist, full-replace, untouched behaviors | VERIFIED | 5 tests; all pass. |
| `apps/backend/tests/integration/client_portal/test_notif_prefs_route.py` | ASGI integration tests: round-trip, defaults, 422, priceKopecks+autoRenew | VERIFIED | 4 tests; all pass. |
| `apps/backend/tests/integration/client_portal/test_fit15_seed.py` | DB presence, idempotency, validate-endpoint 200 | VERIFIED | 3 tests; all pass. |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `service.get_client_membership` | `ClientMembershipResponse.price_kopecks` | `price_kopecks=int(r["price_kopecks_snapshot"])` | WIRED | Line 236; repository SELECT includes `price_kopecks_snapshot` at line 193. |
| `service.get_client_membership` | `ClientMembershipResponse.auto_renew` | `auto_renew=None` | WIRED | Line 237; always None per D-01. |
| `service.get_client_me` | `ClientMeResponse.notif_prefs` | `NotifPrefs(**raw_prefs) if raw_prefs is not None else NotifPrefs(**_NOTIF_DEFAULTS)` | WIRED | Lines 148-149. |
| `repository.update_client_profile` | `clients.notif_prefs` | `CAST(:notif_prefs AS jsonb)` fixed literal SET fragment | WIRED | Lines 603-609; `json.dumps(payload.notif_prefs.model_dump())` bound as string then cast to JSONB. asyncpg-compatible form (avoids `::jsonb` named-param collision). |
| `migration 0051` | `promo_codes` table | `INSERT ... ON CONFLICT (upper(code)) WHERE deleted_at IS NULL DO NOTHING` | WIRED | Explicit partial-index conflict target. |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| `ClientMembershipResponse.price_kopecks` | `r["price_kopecks_snapshot"]` | `memberships.price_kopecks_snapshot` column (existing, populated at membership creation) | Yes — DB column read | FLOWING |
| `ClientMeResponse.notif_prefs` | `r.get("notif_prefs")` | `clients.notif_prefs` JSONB column (new column from migration 0050) | Yes — DB column read + server defaults when NULL | FLOWING |
| FIT15 promo row | `promo_codes` table | Migration 0051 INSERT; `discount_value=1500` DB row | Yes — validated by existing endpoint | FLOWING |

---

## Behavioral Spot-Checks

| Behavior | Command / Evidence | Result | Status |
|----------|--------------------|--------|--------|
| All NOTIF-01 + PMEM-01 tests pass | `uv run pytest tests/modules/client_portal/test_notif_prefs_service.py tests/integration/client_portal/test_notif_prefs_route.py -q` | 9 passed | PASS |
| All PROMO-01 tests pass | `uv run pytest tests/integration/client_portal/test_fit15_seed.py -q` | 3 passed | PASS |
| Full client_portal suite — no regressions | `uv run pytest tests/integration/client_portal/ tests/modules/client_portal/ -q` | 91 passed | PASS |
| Alembic head is 0051 (single head) | `uv run alembic heads` | `0051_seed_fit15_promo (head)` | PASS |
| Database at head | `uv run alembic current` | `0051_seed_fit15_promo (head)` | PASS |

---

## Probe Execution

No probe scripts declared or applicable for this phase.

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| PMEM-01 | 75-01 | `GET /client/membership` exposes `priceKopecks` + `autoRenew` | SATISFIED | Schema, repository, service, integration test all verified. |
| NOTIF-01 | 75-01 | `PATCH /client/me` accepts and persists `notifPrefs` JSONB; `GET` returns defaults when unset | SATISFIED | Schema (`NotifPrefs(BackendSchemaBase)`), migration 0050, service defaults, integration tests all verified. |
| PROMO-01 | 75-02 | FIT15 seeded via idempotent migration; validates through existing endpoint | SATISFIED | Migration 0051, integration tests (existence, idempotency, validate endpoint) all pass. |

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/modules/client_portal/router.py` | 30 | `ruff I001` — import block un-sorted (fixable) | INFO (pre-existing) | `router.py` was last modified in commit `e8259392` (Phase 999.5), before any Phase 75 commit. No Phase 75 commit touched `router.py` (confirmed via `git show --name-only` for all 5 Phase 75 commits: `deae0874`, `ee277095`, `d988f517`, `a44fd56e`, `53f1c6ba`). This is a pre-existing issue, not introduced by Phase 75. All Phase 75 files (`schemas.py`, `service.py`, `repository.py`, `0050_*.py`, `0051_*.py`) pass `ruff check` cleanly. |

No TBD/FIXME/XXX markers found in any Phase 75 files.
No stub return values or placeholder implementations found.

---

## Human Verification Required

None. All success criteria are verifiable programmatically and tests confirm the behaviors end-to-end.

---

## Deferred Items

None.

---

## Gate Results

| Gate | Command | Result | Status |
|------|---------|--------|--------|
| ruff (Phase 75 files only) | `uv run ruff check schemas.py service.py repository.py 0050_*.py 0051_*.py` | All checks passed | PASS |
| mypy | `uv run mypy app/modules/client_portal/ app/modules/clients/models.py` | Success: no issues found in 6 source files | PASS |
| lint-imports | `uv run lint-imports` | 3 contracts kept, 0 broken | PASS |
| alembic heads (single) | `uv run alembic heads` | `0051_seed_fit15_promo (head)` | PASS |
| alembic current | `uv run alembic current` | `0051_seed_fit15_promo (head)` | PASS |
| pytest Phase 75 tests | `uv run pytest tests/modules/client_portal/test_notif_prefs_service.py tests/integration/client_portal/test_notif_prefs_route.py tests/integration/client_portal/test_fit15_seed.py -q` | 12 passed | PASS |
| Full client_portal suite | `uv run pytest tests/integration/client_portal/ tests/modules/client_portal/ -q` | 91 passed | PASS |

---

## Gaps Summary

No gaps. All 6 must-have truths verified. All artifacts exist and are substantive (not stubs). All key links are wired with real data flowing through. All gates pass. No debt markers in Phase 75 files.

The `ruff I001` error in `router.py` is a pre-existing issue from Phase 999.5 that was present before Phase 75 work began and was not introduced or worsened by this phase.

---

_Verified: 2026-06-02T17:00:00Z_
_Verifier: Claude (gsd-verifier)_
