"""AST walker for audit.emit callsites — TESTS-09 / D-11 / D-12 (Phase 15).

Static analysis: walks every `audit.emit(...)` call in apps/backend/app/**/*.py
and asserts (1) both `event` and `resource_type` args are literal strings,
(2) the (event, resource_type) pair is in `LOCKED_AUDIT_EVENTS`.

Catches typos (`memberhsip_created`) and dynamic event names BEFORE they reach
a runtime path. Pure unit-level — no DB.

The walker recognises three callsite shapes:
  - `audit.emit(session, "event", ..., resource_type="x")`            (Name(audit))
  - `<x>.audit.emit(session, "event", ..., resource_type="x")`        (Attribute.audit)
  - `audit_emit(session, "event", ..., resource_type="x")`            (rebound name)

The third form is used by `app/integrations/telegram/handlers.py` which imports
`from app.core.audit import emit as audit_emit` (the only rebinding in the
codebase as of Phase 15).
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.core.audit import LOCKED_AUDIT_EVENTS

# parents[0]=unit, [1]=tests, [2]=backend, [3]=apps, [4]=repo root.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_BACKEND_APP = _REPO_ROOT / "apps" / "backend" / "app"


def _is_audit_emit_call(node: ast.Call) -> bool:
    """True if `node` is `audit.emit(...)`, `<x>.audit.emit(...)`, or `audit_emit(...)`."""
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr == "emit":
        value = func.value
        if isinstance(value, ast.Name) and value.id == "audit":
            return True
        return isinstance(value, ast.Attribute) and value.attr == "audit"
    # Rebound import: `from app.core.audit import emit as audit_emit`
    return isinstance(func, ast.Name) and func.id == "audit_emit"


def _resolve_str_literal(node: ast.expr | None) -> str | None:
    """Return the literal str value if `node` is `ast.Constant(str)`, else None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _extract_event_and_resource_type(
    call: ast.Call,
) -> tuple[ast.expr | None, ast.expr | None]:
    """Return (event_arg, resource_type_arg) AST nodes — None if not present.

    Signature: `emit(session, event, *, actor_user_id, resource_type, ...)`.
    `event` is positional[1] (positional[0] is `session`) or kw `event`.
    `resource_type` is keyword-only.
    """
    event_node: ast.expr | None = None
    if len(call.args) >= 2:
        event_node = call.args[1]
    for kw in call.keywords:
        if kw.arg == "event":
            event_node = kw.value
    resource_type_node: ast.expr | None = None
    for kw in call.keywords:
        if kw.arg == "resource_type":
            resource_type_node = kw.value
    return event_node, resource_type_node


def _iter_audit_emit_calls(
    module_root: Path,
) -> Iterator[tuple[Path, int, ast.expr | None, ast.expr | None]]:
    """Yield (file, lineno, event_arg, resource_type_arg) for every audit.emit
    callsite under module_root.

    The audit module itself (`app/core/audit.py`) is excluded — that is where
    `LOCKED_AUDIT_EVENTS` lives, and any forward references to event names in
    its docstring or guard error message would be false positives.
    """
    audit_module = module_root / "core" / "audit.py"
    for py in sorted(module_root.rglob("*.py")):
        if py.resolve() == audit_module.resolve():
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        except SyntaxError as exc:  # pragma: no cover — defensive
            pytest.fail(f"Could not parse {py}: {exc}")
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not _is_audit_emit_call(node):
                continue
            event_node, resource_type_node = _extract_event_and_resource_type(node)
            yield py, node.lineno, event_node, resource_type_node


def test_every_audit_emit_uses_literal_strings() -> None:
    """D-11 step 3: f-strings / variables are forbidden for `event` and `resource_type`.

    The static gate cannot prove staticness if the args are dynamic, so the
    contract requires literals at every callsite. Helpers that wrap `audit.emit`
    with computed names are not permitted.
    """
    offenders: list[str] = []
    for path, lineno, event_node, resource_type_node in _iter_audit_emit_calls(_BACKEND_APP):
        if event_node is None:
            offenders.append(
                f"{path.relative_to(_REPO_ROOT)}:{lineno} — missing `event` arg"
            )
            continue
        if resource_type_node is None:
            offenders.append(
                f"{path.relative_to(_REPO_ROOT)}:{lineno} — missing `resource_type` kwarg"
            )
            continue
        if _resolve_str_literal(event_node) is None:
            offenders.append(
                f"{path.relative_to(_REPO_ROOT)}:{lineno} — `event` is not a literal str "
                f"(got {ast.dump(event_node)})"
            )
        if _resolve_str_literal(resource_type_node) is None:
            offenders.append(
                f"{path.relative_to(_REPO_ROOT)}:{lineno} — `resource_type` is not a literal str "
                f"(got {ast.dump(resource_type_node)})"
            )
    assert not offenders, (
        "audit.emit() must be called with literal `event` and `resource_type` strings.\n"
        "Offenders:\n  " + "\n  ".join(offenders)
    )


def test_every_audit_emit_pair_is_in_locked_set() -> None:
    """D-11 step 4: every (event, resource_type) pair MUST be in LOCKED_AUDIT_EVENTS.

    Catches the Phase 17 typo case `audit.emit("memberhsip_created", ...)` BEFORE
    the bug reaches a runtime path.
    """
    unlocked: list[str] = []
    for path, lineno, event_node, resource_type_node in _iter_audit_emit_calls(_BACKEND_APP):
        event = _resolve_str_literal(event_node)
        resource_type = _resolve_str_literal(resource_type_node)
        if event is None or resource_type is None:
            # Covered by the literal-only test above; skip here to avoid double-reporting.
            continue
        if (event, resource_type) not in LOCKED_AUDIT_EVENTS:
            unlocked.append(
                f"{path.relative_to(_REPO_ROOT)}:{lineno} — "
                f"({event!r}, {resource_type!r}) not in LOCKED_AUDIT_EVENTS"
            )
    assert not unlocked, (
        "audit.emit() called with (event, resource_type) pair NOT in LOCKED_AUDIT_EVENTS.\n"
        "Either fix the typo at the callsite or extend `LOCKED_AUDIT_EVENTS` "
        "in apps/backend/app/core/audit.py.\n"
        "Offenders:\n  " + "\n  ".join(unlocked)
    )


def test_locked_audit_events_has_expected_count() -> None:
    """Sanity belt — 18 v1.1 + 10 v1.2 = 28 locked pairs (Phase 15 lock).

    Original Plan 15-03 expected 16 v1.1 + 10 v1.2 = 26. Plan executor verified
    against actual callsites and added 2 v1.1 events the docstring had omitted:
    `(rbac_forbidden, 'rbac')` and `(csrf_mismatch, 'csrf')` (both Phase 6).
    See 15-03-SUMMARY.md "Deviations" for details.
    """
    assert len(LOCKED_AUDIT_EVENTS) == 28, (
        f"LOCKED_AUDIT_EVENTS size drifted: expected 28 (18 v1.1 + 10 v1.2), "
        f"got {len(LOCKED_AUDIT_EVENTS)}"
    )
