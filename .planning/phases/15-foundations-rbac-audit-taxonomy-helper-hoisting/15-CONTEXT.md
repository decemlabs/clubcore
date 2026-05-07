# Phase 15: Foundations — RBAC + audit taxonomy + helper hoisting - Context

**Gathered:** 2026-05-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 15 locks the v1.2 contract surface so phases 16/17/19/22 build on a frozen foundation. It is **infrastructure-only** — no new business endpoints, no new tables, no new modules.

In scope:
- Extend `app/core/permissions.py` with v1.2 `Action` / `Resource` / `OWNER_ONLY` entries; mirror byte-for-byte in `apps/admin-web/src/shared/session/{registry.ts, can.ts}`.
- Hoist `_escape_like_pattern` from `app/modules/clients/repository.py` to a new `app/core/sql.py` (single source for LIKE-escape across modules).
- Lock the v1.2 audit-event taxonomy in `app/core/audit.py` via `LOCKED_AUDIT_EVENTS: frozenset[tuple[str, str]]`; make `audit.emit()` raise on any non-locked pair.
- Introduce `app/core/services.py` documenting the `await session.commit()` invariant for write paths; ship the AST commit-gate that enforces it.
- Introduce `BackendSchemaBase` in `app/core/schemas.py` for v1.2 inbound DTOs (camelCase + `extra='forbid'`).
- Record three v1.2 Key Decisions in `.planning/PROJECT.md` (inclusive `end_date`, `gym_date` definition, accepted residual friend-fraud risk).
- Extend the existing TEST-06 RBAC three-way parity test to cover v1.2 pairs; add the audit-taxonomy meta-test; relocate the `_escape_like_pattern` regression suite to import from `core/sql.py`.

Out of scope (belongs to later phases):
- Any new Alembic migration, ORM model, or business endpoint.
- Retroactive migration of v1.1 schemas (clients, auth) onto `BackendSchemaBase`.
- Any change to ARQ worker, Telegram bot, or admin-web feature wiring.
- The `GET /api/v1/audit-log` read endpoint (deferred to v1.3+).

</domain>

<decisions>
## Implementation Decisions

### BusinessService template form

- **D-01:** `app/core/services.py` is a **docstring-only module** — a developer-facing template, not a runtime construct. No abstract Mixin, no context-manager, no inheritance. The docstring carries the canonical write-path recipe (query → mutate → `audit.emit()` → `await session.commit()`) with code examples; an ASCII flowchart is allowed but optional. Modules continue to be free-functions in `service.py` files (matches current `clients/service.py` style).
- **D-02:** Enforcement runs as a **pytest meta-test** that AST-walks every `apps/backend/app/modules/**/service.py` (and `app/workers/scheduled/**/*.py` once Phase 18 lands — out of scope here). The walk lives in `apps/backend/tests/integration/test_rbac_parity.py` group spirit but in a separate new file (see audit-taxonomy decision below). Per INFRA-13 we wire it as a pytest meta-test, NOT a custom ruff plugin and NOT a standalone CI script.
- **D-03:** **What counts as a "write path":** a function whose AST contains any of:
  - `session.add(...)`, `session.add_all(...)`, `session.delete(...)`,
  - `session.execute(insert(...))`, `session.execute(update(...))`, `session.execute(delete(...))`,
  - any reference to a SQLAlchemy `insert` / `update` / `delete` constructor in an `await session.execute(...)` call.

  Such a function MUST contain a literal `await session.commit()` call at module-AST level (i.e., reachable in the function body or in any `try`/`except`/`async with` branch within it), OR carry the `# noqa: SVC001 caller-owns-txn` opt-out marker on the function `def` line.
- **D-04:** **`# noqa: SVC001 caller-owns-txn` policy:** valid **only on private helper functions** (name starting with `_`). Public functions in `service.py` MUST commit themselves. The AST gate enforces this — a public function with `# noqa: SVC001` is itself a failure. Read-only public helpers (e.g. `resolve_active_membership_by_client`) trivially pass the gate because they contain no mutating call.
- **D-05:** **`audit.emit(...)` is treated like a mutating call** for write-path detection: any function that calls `audit.emit` is required to commit (audit row enrolls in the same transaction; missing the commit is the Phase 12.1 incident exactly). Combined with D-03 above this gives: write path = mutating SQL call OR `audit.emit` call.

### BackendSchemaBase

- **D-06:** **Rename `RequestContract` → `BackendSchemaBase`** (single source of truth, no parallel hierarchy). `RequestContract` already has the requested config (`alias_generator=to_camel`, `extra='forbid'`). All v1.1 imports of `RequestContract` are updated in the same Phase 15 commit (sed-grade refactor; expected in `app/core/pagination.py`, `app/modules/clients/schemas.py`, `app/modules/auth/schemas.py`). `ContractModel` and `ResponseData` keep their names — they are response-side bases with `extra='ignore'` and a different intent.
- **D-07:** **Pydantic config flag:** keep the existing **`validate_by_name=True` + `validate_by_alias=True`** pair (Pydantic 2.11+). REQUIREMENTS-INFRA-12's `populate_by_name=True` is functionally equivalent but is the older, deprecated-in-2.11 spelling. Phase 15 commit updates REQUIREMENTS.md INFRA-12 wording to match the implementation. No new flag is added.
- **D-08:** **No retroactive migration of v1.1 schemas onto `BackendSchemaBase`.** v1.1 request-side DTOs already inherit from what is now `BackendSchemaBase` (because we renamed `RequestContract`). Response-side DTOs continue to inherit from `ContractModel` / `ResponseData` (extra='ignore') unchanged. `openapi.json` byte-stability is preserved — no Phase 21 drift caused by Phase 15.

### audit.emit() validation and meta-test organization

- **D-09:** **Validation behavior:** hard fail. `audit.emit(...)` raises `AuditEventNotLockedError(ValueError)` when the `(event, resource_type)` pair is not in `LOCKED_AUDIT_EVENTS`. Same behavior in dev and prod — no DEBUG-only assert, no graceful degradation. Rationale: an unknown audit pair is a programmer error (stale callsite or unlocked taxonomy), and a structlog-only warning hides drift in production logs. The exception class is exposed from `app.core.audit` so tests can catch it precisely.
- **D-10:** **`LOCKED_AUDIT_EVENTS: frozenset[tuple[str, str]]`** lives in `app/core/audit.py` next to `emit()`. The frozenset is extended in Phase 15 with all 10 v1.2 events upfront (even though Phases 16/17/19/20 will be the ones to actually emit them):
  - Memberships plans (3): `("membership_plan_created", "membership_plan")`, `("membership_plan_updated", "membership_plan")`, `("membership_plan_archived", "membership_plan")`.
  - Memberships instances (3): `("membership_created", "membership")`, `("membership_cancelled", "membership")`, `("membership_expired", "membership")`.
  - Visits (4): `("visit_created", "visit")`, `("visit_rejected_no_membership", "visit")`, `("visit_rejected_duplicate", "visit")`, `("visit_rejected_outside_hours", "visit")`.

  The existing 16 v1.1 events from `audit.py:11-28` are also lifted into the frozenset. `resource_type` strings are the snake_case logical resource (NOT the `Resource` StrEnum value — those are RBAC concepts; audit resources are a separate vocabulary already in use in the docstring mapping).
- **D-11:** **TESTS-09 (callsite walk) implementation:** static AST walk over `apps/backend/app/**/*.py`. The walker:
  1. Collects every `Call` node where `func` is `audit.emit` or attribute-access matching `*.audit.emit`.
  2. For each call, resolves the `event` positional/keyword arg AND the `resource_type` keyword arg as `ast.Constant(str)` literals.
  3. If either is a non-literal (e.g. f-string, variable), the test fails: `audit.emit` MUST be called with literal strings only (otherwise the AST gate cannot prove staticness).
  4. Asserts `(event, resource_type) in LOCKED_AUDIT_EVENTS` for every collected pair.

  No runtime monkey-patching; no reliance on integration tests exercising the path. Pure static analysis.
- **D-12:** **Test file layout:**
  - **TESTS-08** (RBAC three-way parity): extend `apps/backend/tests/integration/test_rbac_parity.py` in place — it already does the v1.1 parity matrix; new pairs slot in.
  - **TESTS-09** (audit taxonomy AST walk): new file `apps/backend/tests/unit/test_audit_taxonomy.py`. Unit (not integration) — pure AST, no DB.
  - **TESTS-11** (escape_like regression): the existing `apps/backend/tests/unit/clients/test_repository_escape.py` is updated to import the helper from `app.core.sql`; no test logic changes. A new lightweight `apps/backend/tests/unit/test_core_sql.py` adds direct tests against `core/sql.py:escape_like_pattern` (so the helper has its own test home, independent of the clients module).
  - **INFRA-13 commit gate** (the AST write-path test): new file `apps/backend/tests/unit/test_service_commit_gate.py`. Unit-level AST walk; reuses the same walker style as TESTS-09.

### Claude's Discretion

- **CD-01:** Exact wording / content of the `core/services.py` docstring template (write-path recipe, ASCII flowchart, examples). Goal: a developer opening `core/services.py` understands the contract in <60 seconds.
- **CD-02:** Exact phrasing of the three new v1.2 Key Decisions added to `PROJECT.md` (INFRA-14). The substance is locked in STATE.md `## Decisions` and the SUMMARY.md "Cross-Research Conflicts" table; planner copies that substance into the Key Decisions table format.
- **CD-03:** Exact name of the AST-walk helper module(s) under `tests/` (e.g. `tests/_meta_helpers/ast_walk.py` if shared between TESTS-09 and the commit gate). Both walkers can share an `iter_module_calls()` helper; up to planner whether to factor it out on day one or duplicate.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project context (read first)
- `.planning/PROJECT.md` — project description, Constraints, Key Decisions table (Phase 15 will append three new rows).
- `.planning/REQUIREMENTS.md` — v1.2 requirements; Phase 15 owns INFRA-08…INFRA-14, TESTS-08, TESTS-11.
- `.planning/ROADMAP.md` §"Phase 15: Foundations — RBAC + audit taxonomy + helper hoisting" — phase goal + Success Criteria 1-5.
- `.planning/STATE.md` §"Decisions" — recent v1.2 decisions already accumulated (inclusive end_date, gym_date, residual fraud risk, RBAC extensions, etc.).

### Research outputs (v1.2)
- `.planning/research/SUMMARY.md` §"Pitfalls (BLOCKER ranks)" #1 — service-write commit discipline (the `BusinessService` rationale).
- `.planning/research/SUMMARY.md` §"Open Decisions for Plan-Phase Authors" — items 1, 3, 6 are resolved by Phase 15.
- `.planning/research/PITFALLS.md` — full catalogue of pitfalls Phase 15 must shut down up-front.
- `.planning/research/ARCHITECTURE.md` — `register_user_loader` precedent that Phase 17 will mirror; D-09/D-10 documented exceptions to import-linter contracts.
- `.planning/research/STACK.md` — confirms zero new runtime deps.

### Backend codebase (touched / extended in Phase 15)
- `apps/backend/app/core/permissions.py` — `Role` / `Action` / `Resource` StrEnums + `OWNER_ONLY` frozenset (extended in Phase 15 per INFRA-08).
- `apps/backend/app/core/audit.py` — `audit.emit()` and the locked event docstring (Phase 15 turns the docstring list into a runtime frozenset per INFRA-11).
- `apps/backend/app/core/audit_models.py` — `AuditLog` ORM model (read-only — Phase 15 does not touch the schema).
- `apps/backend/app/core/schemas.py` — `ContractModel` / `RequestContract` / `ResponseData` / `ResponseEnvelope`; Phase 15 renames `RequestContract` → `BackendSchemaBase` per INFRA-12 / D-06.
- `apps/backend/app/core/dependencies.py` — `register_user_loader` precedent for Phase 17's `register_active_membership_resolver`. Phase 15 does not touch this file but planner / Phase 17 will mirror its pattern.
- `apps/backend/app/modules/clients/repository.py:46-77` — `_escape_like_pattern` helper that Phase 15 hoists to `app/core/sql.py` per INFRA-10.
- `apps/backend/app/modules/clients/service.py` — current free-function `service.py` style; Phase 15's `core/services.py` docstring describes this style as the locked v1.2 pattern.
- `apps/backend/app/modules/clients/schemas.py` — current `RequestContract` consumer; updated to import `BackendSchemaBase` post-rename.
- `apps/backend/app/modules/auth/schemas.py` — same as above (rename touch).
- `apps/backend/app/core/database.py:145` (lifespan rollback semantics) — explains why `await session.commit()` is mandatory in service write paths (`get_db` auto-rolls-back on request exit).
- `apps/backend/.importlinter` — three contracts (`core ⊥ modules`, `modules independent`, `integrations ⊥ modules`); Phase 15 changes do NOT touch import-linter (`core/sql.py` is `core` → modules consume it freely; `core/services.py` is a docstring module imported by no one).

### Frontend codebase (byte-paritetic mirror per INFRA-09)
- `apps/admin-web/src/shared/session/registry.ts` — `Resource` type + sidebar registry; Phase 15 adds `MEMBERSHIPS`, `MEMBERSHIP_PLANS`, `VISITS` entries.
- `apps/admin-web/src/shared/session/can.ts:12-22` — `OWNER_ONLY` array (currently 9 entries; Phase 15 extends with the 6 v1.2 owner-only pairs documented in INFRA-08 / STATE.md `## Decisions`).

### Tests (touched / extended in Phase 15)
- `apps/backend/tests/integration/test_rbac_parity.py` — TEST-06 three-way parity; Phase 15 extends with v1.2 pairs per TESTS-08.
- `apps/backend/tests/unit/clients/test_repository_escape.py` — escape_like regression; Phase 15 updates import path per TESTS-11.
- `apps/backend/tests/unit/test_permissions.py` — direct `can()` unit tests; Phase 15 may extend incidentally as new pairs land.

### Conventions (read for style consistency)
- `.planning/codebase/CONVENTIONS.md` — repo conventions.
- `.planning/codebase/STRUCTURE.md` — module layout.
- `.planning/codebase/TESTING.md` — test fixture patterns.
- `apps/backend/docs/conventions.md` — backend-specific conventions (if planner needs deeper detail than the .planning summary).
- `apps/backend/docs/architecture.md` — modular monolith doc; D-06/D-09/D-10 architectural exceptions.
- `apps/backend/docs/adr/0001-modular-monolith.md` — ADR for the import-linter contracts.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`app/core/permissions.py`** (`Role`, `Action`, `Resource`, `OWNER_ONLY`, `can()`) — extended in place per INFRA-08; shape and idioms (StrEnum + frozenset of tuples + verbatim mirror docstring) are the template for the v1.2 additions. No new file needed.
- **`app/core/audit.py:emit()`** — already async, already takes `session`, already does structlog INFO + co-transactional row. Phase 15 adds a pre-emit validation guard but does NOT change the call signature. All existing callers continue to work; new callers in Phase 16/17/19/20 use the same signature.
- **`app/modules/clients/repository.py:_escape_like_pattern`** — full implementation including backslash-first ordering and CR-01 rationale; Phase 15 moves the function verbatim to `app/core/sql.py:escape_like_pattern` (drops the leading underscore — it becomes a module-public helper) and changes the clients import.
- **`app/core/schemas.py:RequestContract`** — already has the exact config INFRA-12 asks for (`alias_generator=to_camel` + `extra='forbid'`). The Phase 15 work is a rename + import-site updates, not a new class.
- **`app/core/dependencies.py:register_user_loader`** (lines 44-61) + **`app/main.py:88`** — the exact precedent Phase 17 will mirror as `register_active_membership_resolver`. Phase 15 doesn't touch this but planner should read it now so the Phase 17 plan can drop straight in.
- **`apps/backend/tests/integration/test_rbac_parity.py`** — already does the three-way set-equality assertion across backend `permissions.py`, admin-web `can.ts`, and `registry.ts`. TESTS-08 extends the input fixtures, not the assertion logic.

### Established Patterns

- **Module layout (`router.py`, `service.py`, `models.py`, `schemas.py`, optional `repository.py` / `permissions.py`)** — validated on `clients` in v1.1; Phase 15's `core/services.py` template documents this layout as the `BusinessService` template. Phase 16/17/19 modules WILL follow it.
- **Free-function service modules (NOT classes)** — Phase 15 explicitly does NOT introduce a service base class. The docstring template captures the pattern in prose, the AST gate enforces the invariant.
- **`audit.emit()` runs inside the caller's transaction; caller commits** — D-03 from Phase 8. Phase 15 does NOT change this (`audit.emit` still never calls `commit`/`flush`); Phase 15 ADDS the locked-pair guard.
- **Three-way parity tests (backend ↔ admin-web `can.ts` ↔ `registry.ts`)** — established in v1.1 Phase 6; Phase 15 reuses the test as-is, only extending its inputs.
- **`from __future__ import annotations` in repository modules** — required by Pydantic generic-resolution edge case (see `clients/repository.py:18-23`); Phase 15's `core/sql.py` is a leaf helper with no Pydantic types so does NOT need `from __future__ import annotations`.
- **Pagination envelope `{items, total, page, pageSize}`** + `ResponseEnvelope[T]` — locked in v1.1; Phase 15 does not touch this surface, but Phase 16/17/19 will continue to use it.

### Integration Points

- **Backend ↔ admin-web RBAC parity** — extending OWNER_ONLY on the backend without simultaneously extending it on admin-web breaks `test_rbac_parity.py`. Phase 15 plans must change both sides in the same commit (or commit set), not split across commits.
- **`audit.py` ↔ all module services** — adding the runtime guard means any out-of-set call raises at runtime. The plan must update the docstring AND ship the frozenset AND keep all v1.1 callers within the locked set (zero-drift for v1.1 callers).
- **`core/sql.py` ↔ `clients/repository.py`** — moving `_escape_like_pattern` requires changing the import in `clients/repository.py` AND the corresponding test import in `tests/unit/clients/test_repository_escape.py`. Both happen in the same commit.
- **`core/schemas.py` rename ↔ all `RequestContract` callers** — at least 3 modules import it (`pagination`, `clients/schemas`, `auth/schemas` — verified by grep). Rename + import-site update happens in one commit; v1.1 schemas remain functionally identical (same class, new name).
- **OpenAPI byte-stability** — Phase 15 must NOT touch any field or response shape that ends up in `apps/backend/openapi.json`. The rename of `RequestContract` → `BackendSchemaBase` is a Python-internal symbol change with no schema impact (the class config and field list are unchanged); the export script's byte output is unaffected. Plan / executor verifies via `git diff --exit-code apps/backend/openapi.json` after every commit.

</code_context>

<specifics>
## Specific Ideas

- **AST commit gate must catch the Phase 12.1 bug.** `clients/service.py` had `audit.emit` calls without `await session.commit()` and the bug shipped. The gate's pass/fail criterion is: a synthetic mutating-without-commit function MUST fail; the current `clients/service.py` (post-12.1 fix) MUST pass.
- **Audit taxonomy meta-test must catch typos in event names.** Adding `audit.emit("memberhsip_created", ...)` (typo) in Phase 17 must fail the meta-test in CI BEFORE the bug reaches a runtime path. This is why the AST walk requires literal strings (D-11 step 3).
- **Residual friend-fraud risk must land in PROJECT.md NOT in a comment.** Per SUMMARY.md "Gaps to flag for plan-phase" item 4 ("Pitfall 9 (residual friend-fraud risk acceptance) must land in PROJECT.md Key Decisions during Phase 15, not buried in comments"). Phase 15 plan-author makes this an explicit task.
- **Import-linter contract names** — Phase 15's `core/sql.py` and `core/services.py` are `app.core.*` modules. The `core ⊥ modules` contract bans `app.core` from importing `app.modules`; the new files must NOT import any module-level symbol. `core/services.py` is docstring-only so trivially passes; `core/sql.py` takes a `str` and returns a `str`, no module imports.

</specifics>

<deferred>
## Deferred Ideas

- **Custom ruff plugin for the commit gate** — ruled out for Phase 15 (would require setuptools entry-point + plugin discovery + ruff version pinning). If the pytest meta-test proves slow or noisy at v1.3+, revisit.
- **Standalone CI script `scripts/check_service_commits.py`** — ruled out for Phase 15 (adds a CI step + duplication). The pytest meta-test runs in the existing `uv run pytest` CI step, no new step needed.
- **Retroactive migration of v1.1 schemas onto `BackendSchemaBase`** — explicitly out of scope (D-08). Reconsider only if Phase 21 OpenAPI drift gate flags any actual contract drift.
- **`# noqa: SVC001 read-only` opt-out for read paths** — not needed; the AST gate's write-path detection (D-03) doesn't fire on read-only functions, so they trivially pass without a marker.
- **Custom `AuditEventNotLockedError` subclass** — chosen (D-09); but the *additional* idea of a registry of `(event, payload schema)` pairs (i.e. validate not just the pair but the payload kwargs) is deferred. Out of scope for Phase 15; revisit if/when audit log read-side API ships in v1.3+.
- **Splitting RBAC parity across more than three layers** (e.g. permissions docs in admin-web ↔ feature flags in PROJECT.md) — out of scope; current three-way parity is sufficient.

</deferred>

---

*Phase: 15-Foundations — RBAC + audit taxonomy + helper hoisting*
*Context gathered: 2026-05-07*
