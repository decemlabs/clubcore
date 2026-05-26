"""AST append-only gate (INFRA-22 / B-01 / Phase 30 / D-30-05..08).

Walks every public/private function in `apps/backend/app/modules/<scope>/service.py`
and asserts: NO function body contains `update(Payment)`, `delete(Payment)`,
`session.execute(update(Payment)...)`, `session.execute(delete(Payment)...)`,
`session.delete(<Payment-typed instance>)`, or `on_conflict_do_update(...)`
against `Payment`.

Detects `Payment` by import-tracking (D-30-06): walker resolves any
`from app.modules.payments.models import Payment` (or `... import Payment as X`)
and flags AST nodes referencing the bound name. Avoids the SVC001-era
string-match false-positive class (no docstring/comment false positives).

INSERT-only policy (D-30-08): only `session.add(Payment(...))`,
`session.execute(insert(Payment).values(...))`, and
`session.execute(insert(Payment)...on_conflict_do_nothing())` are allowed.
`on_conflict_do_update()` is forbidden — formally an UPDATE, blocked at the
AST layer (PAY-02 partial UNIQUE handles concurrent-refund via IntegrityError,
not on_conflict).
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants (mirror test_service_commit_gate.py:28-35 / D-30-05)
# ---------------------------------------------------------------------------

# parents[0]=unit, [1]=tests, [2]=backend, [3]=apps, [4]=repo root.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_BACKEND_APP = _REPO_ROOT / "apps" / "backend" / "app"
_SERVICE_GLOB = "modules/**/service.py"
_FIXTURES_DIR = Path(__file__).parent / "fixtures"

_FORBIDDEN_SQL_FUNCS = {"update", "delete"}
_FORBIDDEN_ON_CONFLICT = {"on_conflict_do_update"}


# ---------------------------------------------------------------------------
# AST predicates
# ---------------------------------------------------------------------------


def _resolve_payment_binding(tree: ast.Module) -> set[str]:
    """Walk top-level ImportFrom nodes; return set of names bound to
    `app.modules.payments.models.Payment` (handles `Payment` and
    `Payment as X`). Empty set when module doesn't import Payment → walker
    no-op (D-30-06: import-tracking).
    """
    bound: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.module != "app.modules.payments.models":
            continue
        for alias in node.names:
            if alias.name == "Payment":
                bound.add(alias.asname or alias.name)
    return bound


def _iter_functions_in_file(
    path: Path,
) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Yield every function-def in `path` (top-level or nested)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            yield node


def _call_first_arg_is_payment(call: ast.Call, payment_names: set[str]) -> bool:
    if not call.args:
        return False
    first = call.args[0]
    return isinstance(first, ast.Name) and first.id in payment_names


def _is_forbidden_sql_against_payment(call: ast.Call, payment_names: set[str]) -> bool:
    """Detect `update(Payment)` / `delete(Payment)` — `sqlalchemy.update` /
    `sqlalchemy.delete` called with a Payment-typed first arg.
    """
    func = call.func
    name: str | None = None
    if isinstance(func, ast.Name):
        name = func.id
    elif isinstance(func, ast.Attribute):
        name = func.attr
    if name not in _FORBIDDEN_SQL_FUNCS:
        return False
    return _call_first_arg_is_payment(call, payment_names)


def _is_on_conflict_do_update_against_payment(call: ast.Call, payment_names: set[str]) -> bool:
    """Detect `insert(Payment).on_conflict_do_update(...)` — a chained call
    on an `insert(...)` against Payment.
    """
    func = call.func
    if not isinstance(func, ast.Attribute):
        return False
    if func.attr not in _FORBIDDEN_ON_CONFLICT:
        return False
    # Walk up the chain: func.value should be an ast.Call whose func is
    # `insert` and whose first arg is a Payment-bound name. Handle the
    # common idiom `insert(Payment).values().on_conflict_do_update(...)` by
    # unwrapping intermediate Attribute/Call nodes that target Payment via
    # `insert`.
    cursor: ast.expr = func.value
    while isinstance(cursor, ast.Call):
        inner = cursor
        inner_name: str | None = None
        if isinstance(inner.func, ast.Name):
            inner_name = inner.func.id
        elif isinstance(inner.func, ast.Attribute):
            inner_name = inner.func.attr
        if inner_name == "insert" and _call_first_arg_is_payment(inner, payment_names):
            return True
        # Step into the attribute chain (e.g. `insert(P).values()` →
        # examine `insert(P)` next).
        if isinstance(inner.func, ast.Attribute):
            cursor = inner.func.value
        else:
            break
    return False


def _is_session_delete_of_payment(call: ast.Call, payment_names: set[str]) -> bool:
    """Detect `session.delete(<Payment-typed name>)` — Attribute call where
    `.attr == 'delete'` and the receiver is `session`.

    Limitation: we cannot type-check the runtime instance at static-analysis
    time. Behaviour is conservative — flag any `session.delete(name)` call
    in a file that imports `Payment`. False-positive risk only exists when
    a non-Payment instance lives in a file that ALSO imports Payment —
    acceptable for B-01 defence-in-depth.
    """
    # `payment_names` is unused for now (kept for symmetry with the other
    # predicates and forward-compat with stricter name-resolution).
    del payment_names
    func = call.func
    if not isinstance(func, ast.Attribute):
        return False
    if func.attr != "delete":
        return False
    if not isinstance(func.value, ast.Name) or func.value.id != "session":
        return False
    return bool(call.args)


def _function_violates_appendonly(
    path: Path,
    func: ast.FunctionDef | ast.AsyncFunctionDef,
    payment_names: set[str],
) -> str | None:
    """Return offender message or None per function."""
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        if _is_forbidden_sql_against_payment(node, payment_names):
            return (
                f"{path}::{func.name} contains forbidden UPDATE/DELETE "
                f"against Payment (B-01 violation, line {node.lineno})"
            )
        if _is_on_conflict_do_update_against_payment(node, payment_names):
            return (
                f"{path}::{func.name} contains forbidden "
                f"on_conflict_do_update against Payment (D-30-08 violation, "
                f"line {node.lineno})"
            )
        if _is_session_delete_of_payment(node, payment_names):
            return (
                f"{path}::{func.name} contains forbidden "
                f"session.delete(<Payment>) (B-01 violation, "
                f"line {node.lineno})"
            )
    return None


# ---------------------------------------------------------------------------
# Live test — runs the walker against the real codebase (Phase 30 placeholders)
# ---------------------------------------------------------------------------


def test_payments_appendonly_against_app_modules() -> None:
    """Live gate against every `modules/**/service.py` — forbids UPDATE/DELETE
    against the `payments.Payment` model class. Phase 30 INFRA-22 / B-01.
    """
    offenders: list[str] = []
    for service_path in sorted(_BACKEND_APP.glob(_SERVICE_GLOB)):
        tree = ast.parse(service_path.read_text(encoding="utf-8"), filename=str(service_path))
        payment_names = _resolve_payment_binding(tree)
        if not payment_names:
            continue  # module doesn't reference Payment — no-op (D-30-06)
        for func in _iter_functions_in_file(service_path):
            msg = _function_violates_appendonly(service_path, func, payment_names)
            if msg is not None:
                offenders.append(msg)
    assert not offenders, "Payments append-only gate (B-01) failed.\nOffenders:\n  " + "\n  ".join(
        offenders
    )


def test_appendonly_walker_scope_is_modules_service_only() -> None:
    """Sanity belt — the glob matches `app/modules/**/service.py` only."""
    matches = list(_BACKEND_APP.glob(_SERVICE_GLOB))
    assert matches, "Walker glob found no service.py files — scope drift?"
    assert all(p.name == "service.py" for p in matches)
    assert all("modules" in p.parts for p in matches)


# ---------------------------------------------------------------------------
# Synthetic fixture tests (D-30-07 — on-disk fixtures vs inline strings)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture_filename",
    [
        "payments_violation_update.py",
        "payments_violation_delete.py",
        "payments_violation_on_conflict_update.py",
        "payments_violation_session_delete.py",
    ],
)
def test_walker_catches_violation_fixture(fixture_filename: str) -> None:
    """Walker MUST catch each synthetic violation fixture."""
    path = _FIXTURES_DIR / fixture_filename
    assert path.is_file(), f"Fixture missing: {path}"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    payment_names = _resolve_payment_binding(tree)
    assert payment_names, f"Fixture {fixture_filename} must import Payment"
    offenders: list[str] = []
    for func in _iter_functions_in_file(path):
        msg = _function_violates_appendonly(path, func, payment_names)
        if msg is not None:
            offenders.append(msg)
    assert offenders, f"Walker failed to catch violation in {fixture_filename}"


def test_walker_passes_clean_insert_fixture() -> None:
    """Positive control — INSERT-only fixture MUST NOT trigger the walker."""
    path = _FIXTURES_DIR / "payments_violation_clean_insert.py"
    assert path.is_file()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    payment_names = _resolve_payment_binding(tree)
    assert payment_names
    offenders: list[str] = []
    for func in _iter_functions_in_file(path):
        msg = _function_violates_appendonly(path, func, payment_names)
        if msg is not None:
            offenders.append(msg)
    assert not offenders, f"Walker false-positive on clean insert: {offenders}"
