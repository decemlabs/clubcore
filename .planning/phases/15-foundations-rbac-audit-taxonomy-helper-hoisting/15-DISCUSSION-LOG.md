# Phase 15: Foundations — RBAC + audit taxonomy + helper hoisting - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-07
**Phase:** 15-Foundations — RBAC + audit taxonomy + helper hoisting
**Areas discussed:** BusinessService template form, BackendSchemaBase, audit.emit() validation and meta-test organization

---

## Selection of Gray Areas

Phase 15 is heavily pre-specified by REQUIREMENTS.md (INFRA-08…INFRA-14, TESTS-08, TESTS-11). The following gray areas were offered:

| Option | Description | Selected |
|--------|-------------|----------|
| BusinessService template form | Mixin / docstring-only / context-manager / Protocol — affects v1.2 service ergonomics | ✓ |
| INFRA-13 enforcement mechanism | pytest meta-test / standalone script / custom ruff plugin | (folded into BusinessService) |
| BackendSchemaBase interaction with existing code | Rename / add new / refactor; plus retroactive migration of v1.1 schemas | ✓ |
| audit.emit() validation and meta-test organization | hard ValueError / DEBUG-only / runtime + AST walk; test file layout | ✓ |

INFRA-13 was naturally absorbed into the BusinessService discussion (the three follow-up questions there nailed the enforcement mechanism, the noqa policy, and the AST detector).

---

## BusinessService Template Form

### Q1: In what form should BusinessService template be?

| Option | Description | Selected |
|--------|-------------|----------|
| Docstring convention + AST gate (Recommended) | `core/services.py` is a docstring-template module; no inheritance; AST gate enforces invariant. Matches current functional `clients/service.py` style. | ✓ |
| Mixin class with `_commit()` helper | `class BusinessServiceMixin: async def _commit(self, session): ...`. Requires refactoring current free-function services into classes. | |
| Context-manager `business_uow(session)` | `async with business_uow(session): ...` auto-commits. Conflicts with `get_db` lifespan-rollback semantics. | |

**User's choice:** Docstring-only convention + AST gate.

### Q2: What does `core/services.py` look like concretely?

| Option | Description | Selected |
|--------|-------------|----------|
| Docstring-only module (Recommended) | Empty module with large header docstring containing the template + ASCII flowchart. Nothing to import. | ✓ |
| Docstring + sentinel constants | Adds `SVC_NOQA_COMMIT = '# noqa: SVC001'` constant + docstring template string consumed by the AST gate. | |
| Pure README in services/ | Move template to `apps/backend/docs/conventions.md`. Conflicts with INFRA-13 explicit `app/core/services.py` requirement. | |

**User's choice:** Docstring-only module.

### Q3: Rule for `# noqa: SVC001 caller-owns-txn`?

| Option | Description | Selected |
|--------|-------------|----------|
| Only private helper functions (`_`-prefix) (Recommended) | Public `service.py` functions MUST commit. Helpers with `_` prefix may opt out. | ✓ |
| Read-only functions (any visibility) | Auto-skip `get_*`/`list_*`/`resolve_*` by name. | |
| Explicit noqa always | Every function in service.py is checked; explicit comment required to opt out. | |

**User's choice:** Only private helper functions (`_`-prefix).

### Q4: How does the AST gate define "write path"?

| Option | Description | Selected |
|--------|-------------|----------|
| Function contains session.add/.delete/.execute(insert/update/delete) (Recommended) | AST detects mutating SQLAlchemy calls; if found → require commit. | ✓ |
| Function name starts with create_/update_/delete_/cancel_/soft_delete_/checkin_ | Prefix-based detection. Less precise. | |
| Combined: AST mutating call OR audit.emit() called | Treats audit.emit as a mutating call (it adds an `AuditLog` row to the session). | (partially adopted in CONTEXT.md D-05) |

**User's choice:** Mutating SQLAlchemy calls. (CONTEXT.md D-05 promotes `audit.emit` to also count as a mutating call — it adds a session row, and Phase 12.1 was exactly the audit-without-commit bug — so the implementation effectively combines options 1 and 3.)

**Notes:** Folded INFRA-13 enforcement mechanism here — pytest meta-test is the implementation vehicle (no ruff plugin, no standalone script).

---

## BackendSchemaBase

### Q1: How to resolve INFRA-12 vs existing core/schemas.py?

| Option | Description | Selected |
|--------|-------------|----------|
| Rename `RequestContract` → `BackendSchemaBase` (Recommended) | RequestContract already has the right config. Single source of truth. | ✓ |
| Add BackendSchemaBase as alias | `BackendSchemaBase = RequestContract`. Two names for one class. | |
| Add NEW BackendSchemaBase separately | Two parallel hierarchies. Drift signal. | |

**User's choice:** Rename `RequestContract` → `BackendSchemaBase`.

### Q2: Pydantic config flag — `populate_by_name=True` (REQUIREMENTS) vs `validate_by_name=True + validate_by_alias=True` (existing code)?

| Option | Description | Selected |
|--------|-------------|----------|
| Keep validate_by_name + validate_by_alias (Recommended) | Existing code uses Pydantic 2.11+ pair. Update REQUIREMENTS.md INFRA-12 wording. | ✓ |
| Have both flags | Add `populate_by_name=True` additionally. Pydantic DeprecationWarning. | |
| Revert to populate_by_name per requirement text | Strict to REQUIREMENTS but regression. | |

**User's choice:** Keep `validate_by_name + validate_by_alias`.

### Q3: Migration of v1.1 schemas (clients, auth) onto BackendSchemaBase — Phase 15 scope?

| Option | Description | Selected |
|--------|-------------|----------|
| Only v1.2 schemas inherit from BackendSchemaBase (Recommended) | v1.1 stays on RequestContract (now renamed = BackendSchemaBase per Q1). Zero openapi drift. | ✓ |
| Retroactively migrate v1.1 schemas | All schemas inherit from BackendSchemaBase. Risk: openapi.json drift if extra='forbid' tightens any v1.1 surface. | |
| Hybrid: only Request-side migrates | Effectively equivalent to option 1 once we rename. | |

**User's choice:** Only v1.2 schemas inherit from BackendSchemaBase. (Note: because Q1 chose rename, v1.1 schemas already inherit from `BackendSchemaBase` post-rename — the choice here is to NOT touch their import paths in any deeper way.)

---

## audit.emit() Validation and Meta-Test Organization

### Q1: Runtime validation behavior on unknown event pair?

| Option | Description | Selected |
|--------|-------------|----------|
| Hard ValueError always (Recommended) | `if (event, resource_type) not in LOCKED_AUDIT_EVENTS: raise ValueError(...)`. Same in dev/prod. | |
| Hard ValueError + dedicated subclass | Same as Recommended but introduce `AuditEventNotLockedError(ValueError)` for precision. | ✓ |
| DEBUG-only assert + structlog ERROR in prod | `assert ... in LOCKED_AUDIT_EVENTS`. Removed under -O. Graceful degradation. Hides drift. | |

**User's choice:** Hard ValueError + dedicated `AuditEventNotLockedError(ValueError)` subclass.

### Q2: TESTS-09 (audit.emit callsite walk) implementation?

| Option | Description | Selected |
|--------|-------------|----------|
| AST walk of all .py files + static analysis of audit.emit args (Recommended) | pytest meta-test using ast.parse on apps/backend/app/**/*.py. Pure static. | ✓ |
| Runtime check via monkey-patch + integration walk | Monkey-patch audit.emit; rely on integration coverage. Dynamic, may miss. | |
| Runtime check relies on INFRA-11 raise | No separate meta-test. Only catches exercised paths. | |

**User's choice:** Static AST walk.

### Q3: Where do TESTS-08 / TESTS-09 / TESTS-11 live?

| Option | Description | Selected |
|--------|-------------|----------|
| TESTS-08 → extend integration/test_rbac_parity.py; TESTS-09 → new unit/test_audit_taxonomy.py; TESTS-11 → extend unit/clients/test_repository_escape.py + new tests (Recommended) | Each test next to its object. RBAC parity already exists. | ✓ |
| New `tests/meta/` directory for all walks | Group all repo-walk tests. Move existing test_rbac_parity.py. | |
| Everything in unit/ | Existing rbac parity is in integration/. | |

**User's choice:** Per-object placement (Recommended).

---

## Claude's Discretion

- Exact wording of `core/services.py` docstring (template, ASCII flowchart, examples) — CD-01.
- Exact phrasing of the three new v1.2 Key Decisions added to PROJECT.md (INFRA-14) — CD-02. The substance is locked; only wording is at planner discretion.
- Whether to factor out a shared `iter_module_calls()` AST helper between TESTS-09 and the INFRA-13 commit gate — CD-03.

## Deferred Ideas

- Custom ruff plugin for the commit gate — ruled out; pytest meta-test wins.
- Standalone CI script `scripts/check_service_commits.py` — ruled out; pytest meta-test wins.
- Retroactive migration of v1.1 schemas onto BackendSchemaBase (full inheritance refactor, not just rename) — out of scope.
- `# noqa: SVC001 read-only` opt-out for read paths — not needed; AST detection of write paths skips read-only naturally.
- Audit registry that validates payload kwargs (not just the (event, resource_type) pair) — deferred to v1.3+ if/when audit-log read API ships.
- Splitting RBAC parity across more than three layers — out of scope.
