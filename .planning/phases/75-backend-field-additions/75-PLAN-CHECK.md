# Plan Check: Phase 75 — Backend Field Additions

**Checker:** gsd-plan-checker (Revision Gate)
**Date:** 2026-06-02
**Plans verified:** 75-01-PLAN.md, 75-02-PLAN.md
**Phase goal:** The client membership response exposes price and auto-renewal status; `/client/me` accepts and persists notification preferences; the FIT15 promo code is seeded and validates via the existing endpoint.

---

## Overall Verdict: CONCERNS (1 WARNING, no BLOCKERs)

Plans are executable. The single warning is a real risk but does not prevent the phase goal from being achieved. The planner must decide whether to add a guard or accept the risk before execution.

---

## Dimension 1: Requirement Coverage

| Requirement | Plans | Tasks | Status |
|-------------|-------|-------|--------|
| PMEM-01 | 75-01 | Task 1, Task 2, Task 3 | COVERED |
| NOTIF-01 | 75-01 | Task 1, Task 2, Task 3 | COVERED |
| PROMO-01 | 75-02 | Task 1, Task 2 | COVERED |

All three ROADMAP requirement IDs appear in the plans' `requirements` frontmatter fields. The three success criteria map as follows:

1. SC-1 (`priceKopecks` + `autoRenew` on GET /client/membership) → 75-01 Tasks 1-3
2. SC-2 (`notifPrefs` PATCH + GET persists) → 75-01 Tasks 1-3
3. SC-3 (FIT15 validates on clean DB) → 75-02 Tasks 1-2

**Result: PASS**

---

## Dimension 2: Task Completeness

| Plan | Task | files | action | verify (automated) | acceptance_criteria | done | Status |
|------|------|-------|--------|--------------------|---------------------|------|--------|
| 75-01 | 1 | ✅ | ✅ (specific) | ✅ | ✅ | ✅ | PASS |
| 75-01 | 2 | ✅ | ✅ (specific) | ✅ | ✅ | ✅ | PASS |
| 75-01 | 3 | ✅ | ✅ (specific) | ✅ | ✅ | ✅ | PASS |
| 75-02 | 1 | ✅ | ✅ (specific) | ✅ | ✅ | ✅ | PASS |
| 75-02 | 2 | ✅ | ✅ (specific) | ✅ | ✅ | ✅ | PASS |

All tasks have `<read_first>`, `<behavior>`, `<action>`, `<verify><automated>`, `<acceptance_criteria>`, and `<done>`. No subjective language in acceptance criteria — all are binary-testable assertions.

**Result: PASS**

---

## Dimension 3: Dependency Correctness

- 75-01: `depends_on: []`, wave 1 — correct.
- 75-02: `depends_on: ["75-01"]`, wave 2 — correct; Task 1's `down_revision` must be `0050_clients_notif_prefs` which is only valid after 75-01 runs. The plan explicitly states "VERIFY 0050 is head via `alembic heads` first", giving the executor the right guard.

Migration chain: `0049 → 0050 (Plan 01) → 0051 (Plan 02)`. No cycles; references are unidirectional.

**Migration head verification:** PATTERNS.md confirms the real head is `0049_fiscal_receipts_customer_phone` (not 0048 as CONTEXT.md Claude's Discretion note erroneously stated). Both plans correctly use `0049_fiscal_receipts_customer_phone` as the down_revision anchor for `0050`, and `0050_clients_notif_prefs` as the anchor for `0051`. This is consistent with the filesystem (`0049_fiscal_receipts_customer_phone.py` is the last file present).

**Result: PASS**

---

## Dimension 4: Key Links Planned

| Link | Source Artifact | Target | Wiring | Status |
|------|----------------|--------|--------|--------|
| price_kopecks_snapshot → priceKopecks | repository.fetch_client_membership (SELECT extension) | ClientMembershipResponse | explicitly described in Task 2 action | PASS |
| auto_renew=None → autoRenew | service.get_client_membership | ClientMembershipResponse | `auto_renew=None` construction described in Task 2 action | PASS |
| notif_prefs column → GET /client/me | repository.fetch_client_me (SELECT extension) + service defaults | ClientMeResponse | Task 2 action covers both repo and service layers | PASS |
| notif_prefs PATCH → UPDATE SET | repository.update_client_profile (new branch) | clients.notif_prefs column | json.dumps + ::jsonb cast described explicitly | PASS |
| 0051 migration → promo_codes | INSERT ON CONFLICT | uq_promo_codes_code_alive | key_link frontmatter + action both describe the ON CONFLICT clause | PASS |
| FIT15 → POST /client/promo/validate | Test C in 75-02 Task 2 | existing endpoint | full ASGI test described | PASS |

All critical wiring paths are explicitly planned, not merely named as artifacts.

**Result: PASS**

---

## Dimension 5: Scope Sanity

| Plan | Tasks | Files modified | Wave | Status |
|------|-------|---------------|------|--------|
| 75-01 | 3 | 7 | 1 | Within threshold (3 tasks, 7 files) |
| 75-02 | 2 | 2 | 2 | Well within threshold |

**Result: PASS**

---

## Dimension 6: Verification Derivation (must_haves)

**75-01 truths are user-observable and binary-testable:**
- "GET /client/membership returns priceKopecks (integer) and autoRenew (null)" ✅
- "PATCH /client/me accepts a notifPrefs object with exactly four bool keys and persists it" ✅
- "GET /client/me returns notifPrefs with server defaults when column is NULL" ✅
- "PATCH /client/me with an unknown notifPrefs key is rejected (422)" ✅

**75-02 truths are user-observable and binary-testable:**
- FIT15 row existence with correct parameters ✅
- Re-run is a no-op ✅
- POST /client/promo/validate returns valid discount ✅

All artifacts have `provides` and `contains` fields. Key links connect artifacts to functionality.

**Result: PASS**

---

## Dimension 7: Context Compliance

All 9 decisions (D-01 through D-09) are explicitly addressed:

| Decision | Plan | Task | Implementing Element |
|----------|------|------|---------------------|
| D-01 (auto_renew always null) | 75-01 | Task 1+2 | schema field `auto_renew: bool \| None`; service constructs with `auto_renew=None` |
| D-02 (price source = price_kopecks_snapshot) | 75-01 | Task 2 | repo SELECT extended; service uses `int(r["price_kopecks_snapshot"])` |
| D-03 (docstring ban lifted for own price) | 75-01 | Task 1 | explicit docstring edit described in action |
| D-04 (strict 4-key schema, unknown keys rejected) | 75-01 | Task 1+3 | `NotifPrefs(BackendSchemaBase)` with `extra="forbid"`; 422 test present |
| D-05 (full replace on PATCH) | 75-01 | Task 2 | `notif_prefs = :notif_prefs::jsonb` full SET fragment |
| D-06 (server-side defaults when NULL) | 75-01 | Task 2+3 | `_NOTIF_DEFAULTS` constant; `if raw is None else _NOTIF_DEFAULTS` |
| D-07 (FIT15 via Alembic migration, not seed script) | 75-02 | Task 1 | dedicated 0051 migration file |
| D-08 (applicable_to=NULL) | 75-02 | Task 1 | INSERT has `applicable_to=NULL` |
| D-09 (FIT15 parameters) | 75-02 | Task 1 | discount_type='percentage', discount_value=1500, per_client_limit=1, max_uses=NULL, no expiry, is_active=true |

**Deferred ideas (promo admin CRUD, autopay/card-on-file) are absent from all plans.** ✅

No scope reduction language was found — D-01's "always null" is explicitly the design intent (not a deferral), and it is fully implemented in the schema + service.

**Result: PASS**

---

## Dimension 7b: Scope Reduction Detection

Scanned all task actions for reduction language ("v1", "static", "placeholder", "hardcoded", "future enhancement", etc.):

- 75-01 Task 1 action: D-01's `auto_renew=None` is the full intended delivery, not a simplification — the decision explicitly states null IS the correct value because the domain has no autopay concept. No reduction.
- PATTERNS.md contains "v1" references in comments but these trace back to D-01's own framing in CONTEXT.md. The plan delivers D-01 fully.
- No scope reduction language found in any task action, verify, or acceptance_criteria block.

**Result: PASS**

---

## Dimension 7c: Architectural Tier Compliance

No RESEARCH.md with an Architectural Responsibility Map exists for this phase.

**Result: SKIPPED**

---

## Dimension 8: Nyquist Compliance

No VALIDATION.md exists for this phase; no RESEARCH.md with a Validation Architecture section.

**Result: SKIPPED**

---

## Dimension 9: Cross-Plan Data Contracts

Plan 75-01 adds `notif_prefs` to the `clients` table; Plan 75-02 only touches `promo_codes`. There is no shared data entity between the two plans. The migration chain (0050→0051) is strictly additive with no data dependency conflict.

**Result: PASS**

---

## Dimension 10: CLAUDE.md Compliance

Relevant CLAUDE.md directives checked:

| Directive | Plans' compliance |
|-----------|------------------|
| Backend: Python 3.12 + uv + FastAPI + SQLAlchemy async + Pydantic v2 + Alembic async | All modifications are in-kind edits to existing files using the established stack. ✅ |
| Testing: `httpx ASGITransport` (not real network) + `pytest-asyncio` | Task 3 integration tests mirror the existing ASGI harness; plan explicitly references ASGITransport-based test_client_me_route.py. ✅ |
| Tooling: `ruff` + `mypy strict` + `import-linter` mandatory | Task 3 acceptance_criteria explicitly require `uv run ruff check app tests` and `uv run mypy app` to exit 0; plan's `<verification>` block includes `lint-imports`. ✅ |
| No new packages: `packages/ui` + `packages/api-client` are placeholders only | No frontend changes in Phase 75. ✅ |
| Formatting: no semicolons, single quotes | Python backend — not governed by the JS formatting rules. ✅ |

**Result: PASS**

---

## Dimension 11: Research Resolution

No RESEARCH.md exists for this phase.

**Result: SKIPPED**

---

## Dimension 12: Pattern Compliance

PATTERNS.md exists and was verified.

| File | Analog from PATTERNS.md | Plan references analog | Status |
|------|------------------------|----------------------|--------|
| schemas.py | same file (existing ClientMembershipResponse) | Task 1 `<read_first>` lists lines 20-33 | ✅ |
| clients/models.py | emergency_contact JSONB (lines 95-98) | Task 1 `<read_first>` + action explicitly copies this pattern | ✅ |
| 0050 migration | 0048_client_onboarding_fields.py | Task 1 `<read_first>` lists this file | ✅ |
| 0051 migration | scripts/seed_demo_data.py `_seed_promo_codes` lines 88-130 | 75-02 Task 1 `<read_first>` lists this file | ✅ |
| repository.py | same file fetch_client_me / update_client_profile | Task 2 `<read_first>` lists exact line ranges | ✅ |
| service.py | same file validation constants + update_client_profile | Task 2 `<read_first>` lists exact line ranges | ✅ |
| test_notif_prefs_service.py | test_client_me_service.py | Task 3 `<read_first>` | ✅ |
| test_notif_prefs_route.py | test_client_me_route.py | Task 3 `<read_first>` | ✅ |

All shared patterns (camelCase wire, cross-module read discipline, caller-owns-transaction) are referenced in PATTERNS.md shared patterns section and the plan actions are consistent with them.

**Result: PASS**

---

## Issues Found

### WARNING — ON CONFLICT clause may not bind the partial index

```yaml
issue:
  plan: "75-02"
  task: 1
  dimension: key_links_planned
  severity: warning
  description: >
    The 0051 migration uses `ON CONFLICT DO NOTHING` without specifying
    index_elements or the partial predicate. PostgreSQL only guarantees
    that a bare `ON CONFLICT DO NOTHING` fires on ALL unique violations
    (including the partial index uq_promo_codes_code_alive), but the
    SQL standard form that explicitly names the partial index is:
      ON CONFLICT (upper(code)) WHERE deleted_at IS NULL DO NOTHING
    The PATTERNS.md plan excerpt shows the bare form in the upgrade()
    body but acknowledges the explicit form may be needed. Using the bare
    form is safe IF there are no other unique indexes on `promo_codes.code`
    that could absorb the conflict without triggering DO NOTHING on the
    partial index. From 0046_promo_codes.py, the ONLY unique constraint on
    `code` is the partial index uq_promo_codes_code_alive. The bare form
    WILL work in this specific schema. However, if a future migration adds
    a full unique index on code (e.g., for a different reason), the bare
    form could silently succeed against the wrong constraint without
    triggering the partial-index path. The plan's action acknowledges this
    and says "use the explicit form if needed" — but leaves the choice to
    the executor without a concrete verification step that catches wrong
    behavior.
  risk: >
    Low in the current schema. Medium if schema changes between now and
    execution. The idempotency Test B in Task 2 will catch a failure at
    test time, so the risk is caught before production — not silent.
  fix_hint: >
    Prefer the explicit form in the upgrade() body:
      ON CONFLICT (upper(code)) WHERE deleted_at IS NULL DO NOTHING
    This is the form that exactly targets uq_promo_codes_code_alive and
    is immune to schema drift. Change the PATTERNS.md sample and the
    plan's action to mandate the explicit form, not leave it as an
    alternative.
```

---

## Specific Check Results (per verification prompt)

### read_first on every task
All 5 tasks have `<read_first>` blocks with specific files and line ranges. ✅

### Verifiable acceptance_criteria (no subjective language)
All acceptance_criteria use binary assertions: file existence, field presence by name, pytest exit code, `isinstance(...)`, `is None`, `> 0`, specific string values. No subjective language. ✅

### Migration chain correctness
- PATTERNS.md explicitly states: "Latest Alembic revision on disk is `0049_fiscal_receipts_customer_phone`"
- Filesystem confirms: only `0048_client_onboarding_fields.py` and `0049_fiscal_receipts_customer_phone.py` exist under alembic/versions in the 004x-005x range.
- 75-01 Task 1: `down_revision = "0049_fiscal_receipts_customer_phone"` ✅
- 75-02 Task 1: `down_revision = "0050_clients_notif_prefs"` ✅
- Both plans include an `alembic heads` verification step before writing the revision. ✅

### D-04 strict schema — NotifPrefs must inherit BackendSchemaBase
75-01 Task 1's action explicitly states: "Import `BackendSchemaBase` from app.core.schemas and define `class NotifPrefs(BackendSchemaBase)`". The plan's `<interfaces>` block documents the discovery that `ResponseData` inherits `extra="ignore"` (confirmed by reading `app/core/schemas.py` lines 56-57) and `BackendSchemaBase` has `extra="forbid"` (confirmed at lines 36-53). The PATTERNS.md shows the incorrect `NotifPrefs(ResponseData)` form but the PLAN.md correctly overrides this. ✅

**CRITICAL NOTE:** PATTERNS.md (lines 72-86) shows `class NotifPrefs(ResponseData)` with the incorrect claim that `extra='forbid'` is inherited from ResponseData. The PLAN.md action section explicitly corrects this, but the PATTERNS.md artifact itself contains wrong code. The executor must follow the plan's `<interfaces>` correction and `<action>` text, NOT the PATTERNS.md code snippet. The plan's `<context>` block at lines 74-89 calls this out as "CRITICAL CORRECTION TO PATTERNS.md". The acceptance criteria require `NotifPrefs(BackendSchemaBase)` by name, so the executor cannot accidentally follow the PATTERNS.md error without failing acceptance. ✅

### 422-rejection acceptance test
75-01 Task 3's acceptance_criteria explicitly requires:
> "The integration suite contains a PATCH with an unknown notifPrefs key asserting `status_code == 422`."
And the integration test behavior description includes:
> "PATCH with `{"notifPrefs": {...four..., "bogus": true}}` → assert 422"
The service-layer test also covers the strict rejection path via Pydantic ValidationError. ✅

### D-02: price_kopecks from price_kopecks_snapshot
Repository task: "fetch_client_membership SELECT includes `price_kopecks_snapshot`" is an explicit acceptance criterion. Service task: "service.py get_client_membership constructs ClientMembershipResponse with `price_kopecks=int(...)`" is explicit. NOT from catalog price. ✅

### D-01: auto_renew always null
Acceptance criteria: "service.py get_client_membership constructs ClientMembershipResponse with `auto_renew=None`". Integration test: "assert `data["autoRenew"] is None`". ✅

### Idempotency: FIT15 seed uses ON CONFLICT DO NOTHING
Plan 02's key_link frontmatter names `uq_promo_codes_code_alive` and the `ON CONFLICT` pattern. The upgrade() uses `ON CONFLICT DO NOTHING`. The test explicitly re-runs the upgrade SQL and asserts `count(*)=1` (idempotency Test B). ✅ (See WARNING above re explicit vs bare form.)

### mypy strict / ruff / import-linter
- 75-01 Task 3 acceptance_criteria: "`uv run ruff check app tests` and `uv run mypy app` exit 0 (no new lint/type errors from this plan)."
- 75-01 `<verification>` block: includes `uv run lint-imports` (import-linter) with "zero new ignore_imports".
- 75-02 Task 2 acceptance_criteria: "`uv run ruff check tests` and `uv run mypy app` exit 0 (no new errors)."
- 75-02 `<verification>` block: includes `uv run lint-imports`.
No new `# type: ignore` or `ignore_imports` additions are introduced in any task. ✅

### Threat model blocks
Both plans have `<threat_model>` sections with STRIDE tables:
- 75-01: T-75-01 (info disclosure), T-75-02 (tampering/JSONB), T-75-03 (IDOR), T-75-04 (integrity), T-75-SC. No unmitigated high-severity threats. ✅
- 75-02: T-75-05 (idempotency), T-75-06 (enumeration — accepted with rationale), T-75-07 (DoS via max_uses=NULL — accepted with rationale), T-75-SC. T-75-06 and T-75-07 accepted dispositions are justified (per_client_limit=1 caps per-account abuse; enumeration hardening is out of scope per D-09). ✅

---

## Plan Summary

| Plan | Tasks | Files | Wave | Requirements | Status |
|------|-------|-------|------|-------------|--------|
| 75-01 | 3 | 7 | 1 | PMEM-01, NOTIF-01 | READY |
| 75-02 | 2 | 2 | 2 | PROMO-01 | READY (1 warning) |

**Verdict: CONCERNS — 1 WARNING, 0 BLOCKERs**

The plans, if executed exactly as written, will make all three success criteria TRUE. The single warning (bare ON CONFLICT form) is mitigated by the idempotency integration test (Test B), which will catch any misbehavior before production. Execution may proceed; the executor should prefer the explicit `ON CONFLICT (upper(code)) WHERE deleted_at IS NULL DO NOTHING` form when writing 0051.
