# Phase 17 — Deferred Items

Out-of-scope discoveries logged during execution. Per the GSD scope-boundary
rule, these are NOT auto-fixed in Phase 17 because they are not directly
caused by Phase 17 changes — they exist in pre-existing Phase 8 / Phase 16
test code.

## Pre-existing mypy strict errors in `tests/` (17 total)

Discovered in Plan 17-05 verification gate (`uv run mypy tests`). All errors
exist in code touched in Phases 8 / 16 / earlier; none are in Phase 17 new
files (verified by stash-and-recheck against the worktree base commit
`fc3cbd8a`).

### Category 1 — `httpx.Cookies.get(...)` returns `str | None`

Files:
- `tests/integration/clients/test_clients_crud.py:28`
- `tests/integration/clients/test_clients_rbac.py:20`
- `tests/integration/clients/test_clients_list.py:18`
- `tests/integration/clients/test_audit_writes.py:26`
- `tests/integration/clients/test_persistence.py:26`
- `tests/integration/memberships/test_plans_crud.py:27`
- `tests/integration/memberships/test_plans_rbac.py:20`
- `tests/integration/memberships/test_plans_list.py:17`
- `tests/integration/memberships/test_audit_writes.py:28`

Pattern (each file):
```python
def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("sportzal_csrf", "")}
                                                                ^^^^
            # mypy: returns str | None even when default ""
```

Phase 17 fix applied locally in new files: use `... or ""` pattern. Full
codebase migration is a Phase X chore.

### Category 2 — `Function does not return a value` on async test fixtures

Files:
- `tests/unit/test_dependencies_verify_csrf.py:52`
- `tests/unit/test_dependencies_verify_csrf.py:58`

Pattern: `assert await verify_csrf(...) is None` — `verify_csrf` returns
None implicitly; mypy's `func-returns-value` flags the assertion shape.
The runtime contract is correct; the assertion is decorative.

### Category 3 — Unused `type: ignore` comments

Files:
- `tests/unit/test_dependencies_require_authenticated.py:45,68,86,97`

mypy version drift: comments were necessary at the time of writing but are
now redundant. Trivial cleanup; no behavioural change.

### Category 4 — StrEnum equality comparison in test_schemas.py

Files:
- `tests/unit/memberships/test_schemas.py:256,257` (Phase 16 baseline lines)

Pattern: `assert MembershipPlanSort.NAME_ASC == "name_asc"`. mypy strict
flags `Literal[Enum] == Literal[str]` as non-overlapping. Runtime works
because StrEnum's `__eq__` falls through to str comparison. Fix: cast or
compare via `.value`.

## Resolution

These errors block the `uv run mypy tests` verification gate documented in
the Plan 17-05 final checkpoint. They existed BEFORE Plan 17-05 (verified
via `git stash && uv run mypy tests`) and are tracked here for a future
test-hygiene chore plan. Phase 17-05 ships green for app/ mypy
(`uv run mypy app` exits 0), green ruff (app + tests), green lint-imports
(3/3 contracts kept), and green pytest (446 total tests).
