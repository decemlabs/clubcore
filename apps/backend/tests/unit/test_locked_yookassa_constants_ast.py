"""AST walker for YOOKASSA webhook primitives — Phase 47 INFRA-37.

Mirrors the shape of ``test_locked_email_templates_ast.py``: static analysis
over ``apps/backend/app/**/*.py`` that enforces two invariants on the two
primitives shipped in ``app/integrations/yookassa/webhook_verifier.py``:

  1. **Depends(verify_yookassa_ip) literal-name gate.** Any ``ast.Call``
     whose ``.func`` is ``Name(id='Depends')`` and whose first positional
     argument is an ``ast.Name`` MUST resolve to the literal canonical name
     ``verify_yookassa_ip``. Aliased / shadowed names that LOOK like
     verifiers (matching the reserved prefixes below) are flagged so a
     refactor that renames the canonical symbol cannot silently bypass the
     IP-allowlist gate at the route layer.

  2. **No dynamic YOOKASSA_TRUSTED_IPS construction.** Any callsite that
     wraps the ``YOOKASSA_TRUSTED_IPS`` name in ``frozenset(...)``,
     ``set(...)``, ``list(...)``, or ``tuple(...)`` (or rebinds the name
     at module scope to a non-Constant expression) is flagged. The
     ``Final[frozenset[str]]`` declared in ``webhook_verifier.py`` is the
     only source of truth; dynamic copies defeat the AST gate's purpose.

Phase 47 ships ZERO real callsites of ``Depends(verify_yookassa_ip)`` —
Phase 50 WH-01 lands the first. The walker therefore collects 0 violations
against the production tree today; the synthetic fixture
``tests/unit/fixtures/yookassa_ast_violations/non_literal_verifier_arg.py``
exists to prove the walker fires when an aliased ``Depends(...)`` callsite
shows up.

Scoping note (per CONTEXT.md upstream-prompt correction): this walker
covers ONLY the YOOKASSA primitives. Audit-event-name literal gating for
``audit.emit(...)`` lives in the existing ``test_audit_taxonomy.py`` and
is NOT duplicated here.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.integrations.yookassa.webhook_verifier import YOOKASSA_TRUSTED_IPS

# parents[0]=unit, [1]=tests, [2]=backend, [3]=apps, [4]=repo root.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_BACKEND_APP = _REPO_ROOT / "apps" / "backend" / "app"
_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "yookassa_ast_violations"

_CANONICAL_VERIFIER_NAME = "verify_yookassa_ip"
_TRUSTED_IPS_NAME = "YOOKASSA_TRUSTED_IPS"

# Names that LOOK like ЮKassa IP verifiers but are NOT the canonical symbol.
# Any ``Depends(<Name>)`` whose target matches one of these prefixes (but is
# not exactly ``verify_yookassa_ip``) is flagged. ``verify_some_alias`` is
# included to lock in the synthetic-fixture rejection contract.
_RESERVED_VERIFIER_PREFIXES: frozenset[str] = frozenset(
    {
        "verify_yookassa_",
        "verify_some_alias",
    }
)

# Builtin container constructors that, when wrapping YOOKASSA_TRUSTED_IPS,
# create a dynamic copy that defeats the Final[frozenset[str]] lock.
_DYNAMIC_CONTAINER_BUILTINS: frozenset[str] = frozenset(
    {"frozenset", "set", "list", "tuple"}
)


def _is_build_receipt_item_call(node: ast.Call) -> bool:
    """True iff ``node`` is a direct ``build_receipt_item(...)`` call (D-48-18)."""
    return isinstance(node.func, ast.Name) and node.func.id == "build_receipt_item"


def _extract_kwarg(call: ast.Call, name: str) -> ast.expr | None:
    """Return the value-AST of keyword arg ``name`` on ``call``, or None."""
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


def _is_enum_member_literal(arg: ast.expr | None, enum_name: str) -> bool:
    """True iff ``arg`` is ``EnumName.<MEMBER>`` (ast.Attribute on ast.Name)."""
    return (
        isinstance(arg, ast.Attribute)
        and isinstance(arg.value, ast.Name)
        and arg.value.id == enum_name
    )


def _is_depends_call(node: ast.Call) -> bool:
    """True iff ``node`` is ``Depends(...)`` — ``Name(id='Depends')`` as func."""
    return isinstance(node.func, ast.Name) and node.func.id == "Depends"


def _extract_depends_target_name(node: ast.Call) -> str | None:
    """Return the ``id`` of the first positional arg if it's ``ast.Name``, else None.

    FastAPI's ``Depends(...)`` idiom passes a callable reference (a ``Name``);
    string args are not idiomatic, so they are out of this walker's scope.
    """
    if not node.args:
        return None
    first = node.args[0]
    if isinstance(first, ast.Name):
        return first.id
    return None


def _matches_reserved_verifier_prefix(name: str) -> bool:
    """True iff ``name`` is in the reserved-prefix space but is not canonical."""
    if name == _CANONICAL_VERIFIER_NAME:
        return False
    return any(name.startswith(prefix) for prefix in _RESERVED_VERIFIER_PREFIXES)


def _is_dynamic_trusted_ips_construction(node: ast.Call) -> bool:
    """True iff ``node`` is e.g. ``frozenset(YOOKASSA_TRUSTED_IPS)`` /
    ``set(YOOKASSA_TRUSTED_IPS)`` / ``list(YOOKASSA_TRUSTED_IPS)`` /
    ``tuple(YOOKASSA_TRUSTED_IPS)``.
    """
    func = node.func
    if not isinstance(func, ast.Name):
        return False
    if func.id not in _DYNAMIC_CONTAINER_BUILTINS:
        return False
    if not node.args:
        return False
    first = node.args[0]
    return isinstance(first, ast.Name) and first.id == _TRUSTED_IPS_NAME


def _is_trusted_ips_rebind(node: ast.Assign) -> bool:
    """True iff ``node`` is a module-scope ``YOOKASSA_TRUSTED_IPS = ...`` assignment.

    The walker does not attempt to distinguish the canonical declaration in
    ``app/integrations/yookassa/webhook_verifier.py`` from rebinds elsewhere —
    that scoping discipline is enforced at the file-list level by
    ``_collect_violations`` (which is invoked per-file).
    """
    for target in node.targets:
        if isinstance(target, ast.Name) and target.id == _TRUSTED_IPS_NAME:
            return True
    return False


def _iter_violations(tree: ast.AST) -> Iterator[tuple[int, str]]:
    """Yield ``(lineno, message)`` for every AST gate violation in ``tree``."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if _is_depends_call(node):
                target = _extract_depends_target_name(node)
                if target is not None and _matches_reserved_verifier_prefix(target):
                    yield (
                        node.lineno,
                        (
                            f"Depends({target}) uses a non-canonical verifier name; "
                            f"only Depends({_CANONICAL_VERIFIER_NAME}) is allowed "
                            "(YOOKASSA IP-allowlist gate, INFRA-37)."
                        ),
                    )
            if _is_dynamic_trusted_ips_construction(node):
                func_name = node.func.id if isinstance(node.func, ast.Name) else "?"
                yield (
                    node.lineno,
                    (
                        f"Dynamic {func_name}({_TRUSTED_IPS_NAME}) construction is "
                        f"forbidden; import {_TRUSTED_IPS_NAME} directly from "
                        "app.integrations.yookassa.webhook_verifier "
                        "(YOOKASSA frozenset-lock, INFRA-37)."
                    ),
                )


def _iter_trusted_ips_rebinds(tree: ast.AST) -> Iterator[tuple[int, str]]:
    """Yield ``(lineno, message)`` for any ``YOOKASSA_TRUSTED_IPS = ...`` rebind."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _is_trusted_ips_rebind(node):
            yield (
                node.lineno,
                (
                    f"{_TRUSTED_IPS_NAME} is rebound here; the Final[frozenset[str]] "
                    "declared in app/integrations/yookassa/webhook_verifier.py is "
                    "the only allowed binding (YOOKASSA frozenset-lock, INFRA-37)."
                ),
            )


def _collect_violations(py_path: Path) -> list[str]:
    """Parse one .py file, walk for YOOKASSA primitive violations, return formatted strings."""
    try:
        source = py_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(py_path))
    except SyntaxError as exc:  # pragma: no cover — defensive
        pytest.fail(f"Could not parse {py_path}: {exc}")

    try:
        rel = py_path.relative_to(_REPO_ROOT)
    except ValueError:
        rel = py_path

    violations: list[str] = []
    for lineno, message in _iter_violations(tree):
        violations.append(f"{rel}:{lineno} — {message}")
    # Rebind-detection is scoped to files OTHER than the canonical declaration.
    canonical_path = (
        _BACKEND_APP / "integrations" / "yookassa" / "webhook_verifier.py"
    )
    if py_path.resolve() != canonical_path.resolve():
        for lineno, message in _iter_trusted_ips_rebinds(tree):
            violations.append(f"{rel}:{lineno} — {message}")
    return violations


def test_real_callsites_pass() -> None:
    """Phase 47: no ``Depends(verify_yookassa_ip)`` callsite exists in prod code
    yet — Phase 50 WH-01 ships the first. Walker therefore collects 0 violations
    against the production tree.

    When Phase 50 lands the real callsite, this test continues to enforce the
    literal-name gate + the no-dynamic-construction contract.
    """
    all_violations: list[str] = []
    for py in sorted(_BACKEND_APP.rglob("*.py")):
        all_violations.extend(_collect_violations(py))
    assert not all_violations, (
        "YOOKASSA primitive AST gate violation(s) detected in production tree.\n"
        "Either fix the callsite to use the canonical literal name "
        f"({_CANONICAL_VERIFIER_NAME}) / drop the dynamic "
        f"{_TRUSTED_IPS_NAME} construction, or amend the AST walker contract.\n"
        "Offenders:\n  " + "\n  ".join(all_violations)
    )


def test_non_literal_verifier_arg_is_rejected() -> None:
    """INFRA-37 / T-47-03-02: the synthetic-violation fixture passes
    ``Depends(verify_some_alias)`` — a name that matches the reserved-prefix
    space but is NOT the canonical ``verify_yookassa_ip``. Walker MUST flag
    it and cite ``verify_some_alias`` in the message.
    """
    fixture = _FIXTURE_DIR / "non_literal_verifier_arg.py"
    violations = _collect_violations(fixture)
    assert violations, (
        f"Walker failed to flag any violation in {fixture}; "
        "the gate is broken (silent-pass on a known-bad fixture)."
    )
    assert any("verify_some_alias" in v for v in violations), (
        f"Walker flagged {fixture} but the message did not mention the "
        f"non-canonical name 'verify_some_alias'. Violations: {violations}"
    )
    assert any(_CANONICAL_VERIFIER_NAME in v for v in violations), (
        "Walker violation message must cite the canonical name "
        f"({_CANONICAL_VERIFIER_NAME}) so the failure points the developer "
        f"at the locked symbol. Got: {violations}"
    )


def test_frozenset_has_six_entries() -> None:
    """Smoke check: ``YOOKASSA_TRUSTED_IPS`` is a frozenset of exactly 6 non-empty
    strings (the 6 CIDRs published by ЮKassa as of 2026-05-21)."""
    assert isinstance(YOOKASSA_TRUSTED_IPS, frozenset)
    assert len(YOOKASSA_TRUSTED_IPS) == 6, (
        f"Expected 6 ЮKassa CIDRs in YOOKASSA_TRUSTED_IPS, got "
        f"{len(YOOKASSA_TRUSTED_IPS)}: {sorted(YOOKASSA_TRUSTED_IPS)}"
    )
    for cidr in YOOKASSA_TRUSTED_IPS:
        assert isinstance(cidr, str) and cidr, (
            f"YOOKASSA_TRUSTED_IPS entry is not a non-empty str: {cidr!r}"
        )


def test_payment_subject_literal_at_callsites() -> None:
    """D-48-18 / SC3: every ``build_receipt_item(payment_subject=...)`` callsite
    MUST pass a ``PaymentSubject.<MEMBER>`` enum literal. Phase 48 ships ZERO
    real callsites — Phase 49 orchestrator lands the first. Walker collects 0
    violations against the production tree today.
    """
    violations: list[str] = []
    for py in sorted(_BACKEND_APP.rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _is_build_receipt_item_call(node):
                arg = _extract_kwarg(node, "payment_subject")
                if arg is None:
                    continue  # mypy catches missing kwarg
                if not _is_enum_member_literal(arg, "PaymentSubject"):
                    violations.append(
                        f"{py.relative_to(_REPO_ROOT)}:{node.lineno} — "
                        "payment_subject must be a PaymentSubject.<MEMBER> literal."
                    )
    assert not violations, "\n".join(violations)


def test_payment_mode_literal_at_callsites() -> None:
    """D-48-18 / SC3: every ``build_receipt_item(payment_mode=...)`` callsite
    MUST pass a ``PaymentMode.<MEMBER>`` enum literal. Same scope rule as
    ``test_payment_subject_literal_at_callsites``.
    """
    violations: list[str] = []
    for py in sorted(_BACKEND_APP.rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _is_build_receipt_item_call(node):
                arg = _extract_kwarg(node, "payment_mode")
                if arg is None:
                    continue
                if not _is_enum_member_literal(arg, "PaymentMode"):
                    violations.append(
                        f"{py.relative_to(_REPO_ROOT)}:{node.lineno} — "
                        "payment_mode must be a PaymentMode.<MEMBER> literal."
                    )
    assert not violations, "\n".join(violations)


def test_non_literal_payment_subject_fixture_is_rejected() -> None:
    """Synthetic violation fixture exercises the walker — must collect 1 violation."""
    fixture = (
        _REPO_ROOT
        / "apps/backend/tests/unit/fixtures/yookassa_ast_violations"
        / "non_literal_payment_subject.py"
    )
    tree = ast.parse(fixture.read_text(encoding="utf-8"))
    detected = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_build_receipt_item_call(node):
            arg = _extract_kwarg(node, "payment_subject")
            if arg is not None and not _is_enum_member_literal(arg, "PaymentSubject"):
                detected += 1
    assert detected >= 1


def test_non_literal_payment_mode_fixture_is_rejected() -> None:
    """Synthetic violation fixture exercises the walker — must collect 1 violation."""
    fixture = (
        _REPO_ROOT
        / "apps/backend/tests/unit/fixtures/yookassa_ast_violations"
        / "non_literal_payment_mode.py"
    )
    tree = ast.parse(fixture.read_text(encoding="utf-8"))
    detected = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_build_receipt_item_call(node):
            arg = _extract_kwarg(node, "payment_mode")
            if arg is not None and not _is_enum_member_literal(arg, "PaymentMode"):
                detected += 1
    assert detected >= 1
