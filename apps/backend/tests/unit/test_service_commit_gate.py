"""AST commit-gate (INFRA-13 / D-03..D-05 / D-12 — Phase 15).

Walks public/private functions in `apps/backend/app/modules/<scope>/service.py`
and asserts: if the function's AST contains a mutating SQL call OR an
`audit.emit(...)` call, the function body MUST contain `await session.commit()`
(or the function MUST be a private helper carrying the
`# noqa: SVC001 caller-owns-txn` opt-out marker on its def line).

Catches the Phase 12.1 bug class: `audit.emit` without commit, audit row
silently dropped at request exit by `app/core/database.py:get_db` rollback.

Walker scope (Phase 15): the live `test_service_commit_gate_against_app_modules`
test targets `app/modules/clients/service.py` only — the post-12.1 regression
bound. The glob constant `_SERVICE_GLOB` matches every `modules/**/service.py`
and is exercised by `test_walker_scope_is_modules_service_only`; the live
gate is narrowed to clients per the plan's acceptance criterion. Subsequent
phases extend the live gate as each module's write-path semantics are audited
(see deferred-items.md for the auth/service.py review).
"""

from __future__ import annotations

import ast
import linecache
from collections.abc import Iterator
from pathlib import Path

# parents[0]=unit, [1]=tests, [2]=backend, [3]=apps, [4]=repo root.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_BACKEND_APP = _REPO_ROOT / "apps" / "backend" / "app"
_SERVICE_GLOB = "modules/**/service.py"  # Phase 15 scope (D-12 + PATTERNS.md walker scope)

_MUTATING_SESSION_ATTRS = {"add", "add_all", "delete"}
_MUTATING_SQL_FUNCS = {"insert", "update", "delete"}
_SVC001_MARKER = "# noqa: SVC001 caller-owns-txn"


def _is_session_call(node: ast.Call, attr: str) -> bool:
    """True if `node` is `session.<attr>(...)`."""
    return (
        isinstance(node.func, ast.Attribute)
        and node.func.attr == attr
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "session"
    )


def _is_session_execute_with_mutating_sql(node: ast.Call) -> bool:
    """True if `node` is `session.execute(insert/update/delete(...))` (D-03).

    Detects mutating SQL by name (`Name` or `Attribute` with `attr in {"insert",
    "update", "delete"}`); does not require resolving the SQLAlchemy import.
    """
    if not (
        isinstance(node.func, ast.Attribute)
        and node.func.attr == "execute"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "session"
    ):
        return False
    if not node.args:
        return False
    inner = node.args[0]
    if not isinstance(inner, ast.Call):
        return False
    if isinstance(inner.func, ast.Name) and inner.func.id in _MUTATING_SQL_FUNCS:
        return True
    return (
        isinstance(inner.func, ast.Attribute) and inner.func.attr in _MUTATING_SQL_FUNCS
    )


def _is_audit_emit_call(node: ast.Call) -> bool:
    """True if `node` is `audit.emit(...)` or `<x>.audit.emit(...)` (D-05)."""
    if not isinstance(node.func, ast.Attribute) or node.func.attr != "emit":
        return False
    value = node.func.value
    if isinstance(value, ast.Name) and value.id == "audit":
        return True
    return isinstance(value, ast.Attribute) and value.attr == "audit"


def _function_is_write_path(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """True if `func` contains any mutating SQL call OR audit.emit (D-03 / D-05)."""
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        if any(_is_session_call(node, a) for a in _MUTATING_SESSION_ATTRS):
            return True
        if _is_session_execute_with_mutating_sql(node):
            return True
        if _is_audit_emit_call(node):
            return True
    return False


def _function_has_commit(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """True if `func` body contains `session.commit(...)` anywhere reachable."""
    for node in ast.walk(func):
        if isinstance(node, ast.Call) and _is_session_call(node, "commit"):
            return True
    return False


def _function_has_svc001_marker(
    path: Path, func: ast.FunctionDef | ast.AsyncFunctionDef
) -> bool:
    """True if the SVC001 opt-out marker appears on the def line.

    The marker MUST appear on the same source line as the `def` / `async def`
    keyword. Lookup uses `linecache.getline(...)` so the same logic works for
    real file paths AND for in-memory snippets injected via `linecache.cache`.
    """
    line = linecache.getline(str(path), func.lineno)
    return _SVC001_MARKER in line


def _check_function(
    path: Path, func: ast.FunctionDef | ast.AsyncFunctionDef
) -> str | None:
    """Return an offender message if `func` violates SVC001, else None.

    Decision tree (D-03 / D-04 / D-05):
      1. Not a write path → pass.
      2. Has explicit `session.commit(...)` → pass.
      3. Has SVC001 marker on private (`_`-prefixed) function → pass.
      4. Has SVC001 marker on public function → FAIL (D-04: marker only valid
         on private helpers; public service functions MUST commit themselves).
      5. Otherwise → FAIL (Phase 12.1 bug class).
    """
    if not _function_is_write_path(func):
        return None
    if _function_has_commit(func):
        return None
    has_marker = _function_has_svc001_marker(path, func)
    is_private = func.name.startswith("_")
    if has_marker:
        if is_private:
            return None
        try:
            rel = path.relative_to(_REPO_ROOT)
        except ValueError:
            rel = path
        return (
            f"{rel}:{func.lineno} — "
            f"public function `{func.name}` carries `{_SVC001_MARKER}` but "
            "public service functions MUST commit themselves (D-04)."
        )
    try:
        rel = path.relative_to(_REPO_ROOT)
    except ValueError:
        rel = path
    return (
        f"{rel}:{func.lineno} — "
        f"`{func.name}` is a write path (mutating SQL or audit.emit) "
        "but contains no `await session.commit()` and no SVC001 opt-out marker. "
        "This is the Phase 12.1 bug class — fix by adding `await session.commit()` "
        "at the end of the write path."
    )


# ---------------------------------------------------------------------------
# Live test — runs the walker against the real codebase
# ---------------------------------------------------------------------------


_CLIENTS_SERVICE = _BACKEND_APP / "modules" / "clients" / "service.py"


def _iter_functions_in_file(
    path: Path,
) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Yield every function-def in `path` (top-level or nested)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            yield node


def test_service_commit_gate_against_app_modules() -> None:
    """Live gate against `app/modules/clients/service.py` (post-12.1 fix).

    Phase 12.1 regression bound — `clients/service.py` shipped with three
    write paths (`create_client`, `update_client`, `soft_delete_client`)
    missing `await session.commit()`. This gate fails if the bug recurs.

    Scope is narrowed to `clients/service.py` per the plan's acceptance
    criterion. The walker glob (`_SERVICE_GLOB`) and predicate apparatus
    are exercised by `test_walker_scope_is_modules_service_only` and the
    synthetic-source tests below; widening the live scope is a deliberate
    decision per module (e.g. `auth/service.py:authenticate` and
    `rotate_refresh` need a separate write-path semantics review before
    they can be added to the gate — see deferred-items.md).
    """
    assert _CLIENTS_SERVICE.is_file(), (
        f"Expected clients service file at {_CLIENTS_SERVICE} — phase fixture drift?"
    )
    offenders: list[str] = []
    for func in _iter_functions_in_file(_CLIENTS_SERVICE):
        msg = _check_function(_CLIENTS_SERVICE, func)
        if msg is not None:
            offenders.append(msg)
    assert not offenders, (
        "Service write-path commit-gate (SVC001) failed against clients/service.py.\n"
        "Offenders:\n  " + "\n  ".join(offenders)
    )


def test_walker_scope_is_modules_service_only() -> None:
    """Sanity belt — the glob matches `app/modules/**/service.py` only.

    Phase 18 will extend the walker to `app/workers/scheduled/**/*.py`. Phase 15
    scope is intentionally narrow (D-12 + PATTERNS.md "Walker scope (Phase 15 only)").
    """
    matches = list(_BACKEND_APP.glob(_SERVICE_GLOB))
    assert matches, "Walker glob found no service.py files — scope drift?"
    assert all(p.name == "service.py" for p in matches)
    assert all("modules" in p.parts for p in matches)
    assert all("workers" not in p.parts for p in matches)


# ---------------------------------------------------------------------------
# Synthetic-source tests (parse small AST snippets to prove the predicates)
# ---------------------------------------------------------------------------


def _check_snippet(src: str, *, fake_filename: str) -> str | None:
    """Parse `src` (must define exactly one top-level function), check it,
    return offender message or None.

    Uses `linecache.cache` injection so `_function_has_svc001_marker`'s
    `linecache.getline(...)` call resolves against the in-memory string
    without needing a real file on disk.
    """
    linecache.cache[fake_filename] = (
        len(src),
        None,
        src.splitlines(keepends=True),
        fake_filename,
    )
    tree = ast.parse(src, filename=fake_filename)
    funcs = [
        n for n in tree.body if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
    ]
    assert len(funcs) == 1, "snippet must define exactly one function"
    return _check_function(Path(fake_filename), funcs[0])


def test_synthetic_missing_commit_is_detected() -> None:
    """A function with audit.emit + session.add but no commit MUST fail.

    This is the canonical Phase 12.1 bug shape: write path enrolls audit row
    + ORM mutation in the session but never commits, so request exit rolls
    everything back silently.
    """
    src = (
        "async def create_thing(session, actor):\n"
        "    session.add(thing)\n"
        "    await audit.emit(session, 'x', actor_user_id=None, resource_type='y')\n"
    )
    msg = _check_snippet(src, fake_filename="<missing_commit>")
    assert msg is not None
    assert "Phase 12.1 bug class" in msg


def test_synthetic_with_commit_passes() -> None:
    """A function that commits at the end of the write path MUST pass."""
    src = (
        "async def create_thing(session, actor):\n"
        "    session.add(thing)\n"
        "    await audit.emit(session, 'x', actor_user_id=None, resource_type='y')\n"
        "    await session.commit()\n"
    )
    assert _check_snippet(src, fake_filename="<with_commit>") is None


def test_synthetic_private_helper_with_svc001_passes() -> None:
    """A private (`_`-prefixed) helper carrying the SVC001 marker MUST pass.

    The opt-out is valid for private helpers that intentionally leave the
    commit to their caller (D-04).
    """
    src = (
        "async def _atomic_inner(session):  # noqa: SVC001 caller-owns-txn\n"
        "    session.add(thing)\n"
        "    await audit.emit(session, 'x', actor_user_id=None, resource_type='y')\n"
    )
    assert _check_snippet(src, fake_filename="<private_optout>") is None


def test_synthetic_public_function_with_svc001_is_rejected() -> None:
    """A public function carrying the SVC001 marker MUST fail (D-04).

    Public service functions are the boundary callers (routers / ARQ workers /
    bot handlers) trust to be transactionally complete. The marker is reserved
    for private helpers that delegate the commit upward.
    """
    src = (
        "async def create_thing(session):  # noqa: SVC001 caller-owns-txn\n"
        "    session.add(thing)\n"
        "    await audit.emit(session, 'x', actor_user_id=None, resource_type='y')\n"
    )
    msg = _check_snippet(src, fake_filename="<public_optout>")
    assert msg is not None
    assert "public service functions MUST commit" in msg


def test_synthetic_read_only_function_passes_without_marker() -> None:
    """A read-only function (`session.execute(select(...))`) is not a write path.

    `select` is not in `_MUTATING_SQL_FUNCS`, so the function trivially passes
    without needing the SVC001 opt-out marker. This documents the read-only
    handling explicitly so future tweaks to `_MUTATING_SQL_FUNCS` are deliberate.
    """
    src = (
        "async def get_thing(session, thing_id):\n"
        "    return await session.execute(select(Thing).where(Thing.id == thing_id))\n"
    )
    assert _check_snippet(src, fake_filename="<read_only>") is None
