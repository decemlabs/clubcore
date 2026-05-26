"""AST walker for `get_email_dispatcher()(template_id=...)` callsites
— Phase 41 INFRA-36 / D-41-11 / D-41-13.

Mirrors `test_audit_taxonomy.py` shape: static analysis over
`apps/backend/app/**/*.py` that asserts every `get_email_dispatcher()(...)`
callsite passes `template_id=<literal str>` resolving to a member of
`LOCKED_EMAIL_TEMPLATES`.

Target callsite shape is a DOUBLE Call:
    get_email_dispatcher()(template_id="EMAIL_OTP_LOGIN", ...)
    └──── inner Call ────┘└──── outer Call (the dispatch invocation) ────┘

That is: an `ast.Call` whose `.func` is itself an `ast.Call` whose `.func`
is `ast.Name(id='get_email_dispatcher')`. The Protocol slot declared in
Phase 41 (D-41-24) makes `template_id` a keyword-only argument; the walker
also accepts the first positional form for forward-compatibility.

Two failure reasons:
  (a) `template_id` is not a literal str (e.g. variable, f-string)
  (b) literal value is not in `LOCKED_EMAIL_TEMPLATES`

Synthetic-violation fixtures under
`tests/unit/fixtures/email_ast_violations/` exercise both reasons.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.core.audit import LOCKED_EMAIL_TEMPLATES

# parents[0]=unit, [1]=tests, [2]=backend, [3]=apps, [4]=repo root.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_BACKEND_APP = _REPO_ROOT / "apps" / "backend" / "app"
_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "email_ast_violations"


def _resolve_str_literal(node: ast.expr | None) -> str | None:
    """Return the literal str value if `node` is `ast.Constant(str)`, else None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _is_get_email_dispatcher_call(node: ast.Call) -> bool:
    """True if `node` is `get_email_dispatcher()(...)` — the outer Call of a
    double-Call shape whose inner func is `Name(id='get_email_dispatcher')`.
    """
    inner = node.func
    if not isinstance(inner, ast.Call):
        return False
    inner_func = inner.func
    return isinstance(inner_func, ast.Name) and inner_func.id == "get_email_dispatcher"


def _extract_template_id_arg(call: ast.Call) -> ast.expr | None:
    """Return the AST node passed as `template_id` to a `get_email_dispatcher()(...)`
    call — either the first positional or the `template_id=` keyword. None if missing.

    Protocol slot declared in Phase 41 (D-41-24) makes `template_id` keyword-only,
    but accepting the positional form as well is a cheap robustness measure that
    matches the docstring contract ("first positional OR keyword `template_id=`").
    """
    for kw in call.keywords:
        if kw.arg == "template_id":
            return kw.value
    if call.args:
        return call.args[0]
    return None


def _iter_dispatcher_calls(tree: ast.AST) -> Iterator[tuple[int, ast.expr | None]]:
    """Yield (lineno, template_id_arg_node | None) for every
    `get_email_dispatcher()(...)` outer-Call in `tree`.
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not _is_get_email_dispatcher_call(node):
            continue
        yield node.lineno, _extract_template_id_arg(node)


def _collect_violations(py_path: Path) -> list[str]:
    """Parse one .py file, walk for `get_email_dispatcher()(...)` callsites,
    return violation messages (each prefixed with `{relpath}:{lineno}`).
    """
    try:
        source = py_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(py_path))
    except SyntaxError as exc:  # pragma: no cover — defensive
        pytest.fail(f"Could not parse {py_path}: {exc}")

    violations: list[str] = []
    try:
        rel = py_path.relative_to(_REPO_ROOT)
    except ValueError:
        rel = py_path
    for lineno, arg_node in _iter_dispatcher_calls(tree):
        prefix = f"{rel}:{lineno} — get_email_dispatcher()(template_id=...)"
        if arg_node is None:
            violations.append(f"{prefix} missing template_id argument")
            continue
        literal_value = _resolve_str_literal(arg_node)
        if literal_value is None:
            violations.append(f"{prefix} is not a literal str (got {ast.dump(arg_node)})")
            continue
        if literal_value not in LOCKED_EMAIL_TEMPLATES:
            violations.append(f"{prefix} value {literal_value!r} is not in LOCKED_EMAIL_TEMPLATES")
    return violations


def test_real_callsites_pass() -> None:
    """Phase 41: no `get_email_dispatcher()(...)` callsite exists in prod code
    yet — Phase 42 ships the first. Walker therefore collects 0 violations
    against the production tree.

    When Phase 42 lands real callsites, this test continues to enforce the
    literal-only + locked-frozenset contract on every one of them.
    """
    all_violations: list[str] = []
    for py in sorted(_BACKEND_APP.rglob("*.py")):
        all_violations.extend(_collect_violations(py))
    assert not all_violations, (
        "get_email_dispatcher()(template_id=...) callsite(s) violate the "
        "LOCKED_EMAIL_TEMPLATES literal-only gate.\n"
        "Either fix the literal at the callsite or extend LOCKED_EMAIL_TEMPLATES "
        "in apps/backend/app/core/audit.py.\n"
        "Offenders:\n  " + "\n  ".join(all_violations)
    )


def test_bogus_template_id_is_rejected() -> None:
    """D-41-13: the synthetic-violation fixture uses literal 'BOGUS_NOT_LOCKED'
    which is NOT in LOCKED_EMAIL_TEMPLATES. Walker MUST report a violation
    that cites the bogus value.
    """
    fixture = _FIXTURE_DIR / "bogus_template_id.py"
    violations = _collect_violations(fixture)
    assert violations, (
        f"Walker failed to flag any violation in {fixture}; "
        "the gate is broken (silent-pass on a known-bad fixture)."
    )
    assert any("BOGUS_NOT_LOCKED" in v for v in violations), (
        f"Walker flagged {fixture} but the message did not mention "
        f"the bogus identifier 'BOGUS_NOT_LOCKED'. Violations: {violations}"
    )
    assert any("LOCKED_EMAIL_TEMPLATES" in v for v in violations), (
        "Walker violation message must cite LOCKED_EMAIL_TEMPLATES so the "
        f"failure points the developer at the frozenset. Got: {violations}"
    )


def test_email_otp_login_real_callsite_present() -> None:
    """Phase 42 D-42-27 — positive-fixture assertion on the first real
    ``LOCKED_EMAIL_TEMPLATES`` callsite.

    Plan 42-09 shipped the first ``get_email_dispatcher()(template_id=...)``
    callsite in production code (``app/modules/auth/service.py``
    inside ``request_otp_email``). The Phase 41 INFRA-36 AST walker
    already scans ``apps/backend/app/**/*.py`` so
    ``test_real_callsites_pass`` indirectly exercises it — but a future
    "helpfully refactored" const-extraction (e.g.
    ``template_id=EMAIL_OTP_LOGIN_CONST``) would silently bypass the gate
    because the walker rejects only NON-Constant nodes that reach a
    dispatcher call. This test pins the contract that the literal
    ``"EMAIL_OTP_LOGIN"`` exists as an ``ast.Constant(str)`` directly at
    a callsite inside ``auth.service``.

    Walker logic mirrored locally (not delegated to ``_iter_dispatcher_calls``)
    so a refactor of the production walker cannot silently weaken this gate.
    """
    service_py = _BACKEND_APP / "modules" / "auth" / "service.py"
    tree = ast.parse(service_py.read_text(encoding="utf-8"))

    found_literal_template_ids: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if (
                kw.arg == "template_id"
                and isinstance(kw.value, ast.Constant)
                and isinstance(kw.value.value, str)
            ):
                found_literal_template_ids.append(kw.value.value)

    assert "EMAIL_OTP_LOGIN" in found_literal_template_ids, (
        "Phase 42 D-42-27 violation: literal EMAIL_OTP_LOGIN template_id "
        "callsite not found in app/modules/auth/service.py. "
        "If you refactored the callsite to read template_id from a constant, "
        "revert -- the AST walker only accepts ast.Constant(str). "
        f"Got literal template_ids: {found_literal_template_ids}"
    )


def test_user_invitation_email_literal_at_users_service_callsite() -> None:
    """Phase 43 D-43-33 / USERS-03 — positive-fixture assertion on the
    ``USER_INVITATION_EMAIL`` real callsite.

    Plan 43-05 shipped the second ``get_email_dispatcher()(template_id=...)``
    callsite in production code (``app/modules/users/service.py`` inside
    ``create_user``). Mirrors the Phase 42 4-11 pattern for
    ``EMAIL_OTP_LOGIN``: a future "helpfully refactored" const-extraction
    (e.g. ``template_id=USER_INVITATION_EMAIL_CONST``) would silently bypass
    ``test_real_callsites_pass`` because the walker rejects only non-Constant
    nodes that reach a dispatcher call. This test pins the contract that the
    literal ``"USER_INVITATION_EMAIL"`` exists as an ``ast.Constant(str)``
    directly at a callsite inside ``users.service``.

    Walker logic mirrored locally (not delegated to ``_iter_dispatcher_calls``)
    so a refactor of the production walker cannot silently weaken this gate.
    """
    service_py = _BACKEND_APP / "modules" / "users" / "service.py"
    tree = ast.parse(service_py.read_text(encoding="utf-8"))

    found_literal_template_ids: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if (
                kw.arg == "template_id"
                and isinstance(kw.value, ast.Constant)
                and isinstance(kw.value.value, str)
            ):
                found_literal_template_ids.append(kw.value.value)

    assert "USER_INVITATION_EMAIL" in found_literal_template_ids, (
        "Phase 43 USERS-03 / D-43-33 violation: literal USER_INVITATION_EMAIL "
        "template_id callsite not found in app/modules/users/service.py. "
        "If you refactored the callsite to read template_id from a constant "
        "or f-string, revert — the AST walker (D-41-11) only accepts "
        "ast.Constant(str). "
        f"Got literal template_ids: {found_literal_template_ids}"
    )


def test_non_literal_template_id_is_rejected() -> None:
    """D-41-13: the synthetic-violation fixture passes `template_id=chosen_id`
    where `chosen_id` is a variable, not a literal `ast.Constant(str)`.
    Walker MUST reject because the gate is literal-only (mirrors the
    audit.emit literal-only gate from Phase 15).
    """
    fixture = _FIXTURE_DIR / "raw_subject_string.py"
    violations = _collect_violations(fixture)
    assert violations, (
        f"Walker failed to flag any violation in {fixture}; "
        "the gate is broken (silent-pass on a non-literal template_id)."
    )
    assert any("not a literal" in v.lower() for v in violations), (
        f"Walker flagged {fixture} but the message did not say "
        f"'not a literal'. Violations: {violations}"
    )


def test_password_reset_email_literal_at_password_reset_service_callsite() -> None:
    """Phase 44 D-44-36 — positive-fixture assertion on the
    ``PASSWORD_RESET_EMAIL`` real callsite.

    Plan 44-04 shipped the third ``get_email_dispatcher()(template_id=...)``
    callsite in production code (``app/modules/auth/password_reset_service.py``
    inside ``request_password_reset``). Mirrors the Phase 42 4-11 +
    Phase 43 plan 13 patterns for ``EMAIL_OTP_LOGIN`` /
    ``USER_INVITATION_EMAIL``: a future "helpfully refactored" const-extraction
    (e.g. ``template_id=PASSWORD_RESET_EMAIL_CONST``) would silently bypass
    ``test_real_callsites_pass`` because the walker rejects only non-Constant
    nodes that reach a dispatcher call. This test pins the contract that the
    literal ``"PASSWORD_RESET_EMAIL"`` exists as an ``ast.Constant(str)``
    directly at a callsite inside ``auth.password_reset_service``.

    Walker logic mirrored locally (not delegated to ``_iter_dispatcher_calls``)
    so a refactor of the production walker cannot silently weaken this gate
    (D-43-33 anti-weakening discipline, applied to PASSWORD_RESET_EMAIL here).
    """
    service_py = _BACKEND_APP / "modules" / "auth" / "password_reset_service.py"
    tree = ast.parse(service_py.read_text(encoding="utf-8"))

    found_literal_template_ids: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if (
                kw.arg == "template_id"
                and isinstance(kw.value, ast.Constant)
                and isinstance(kw.value.value, str)
            ):
                found_literal_template_ids.append(kw.value.value)

    assert "PASSWORD_RESET_EMAIL" in found_literal_template_ids, (
        "Phase 44 RESET-03 / D-44-36 violation: literal PASSWORD_RESET_EMAIL "
        "template_id callsite not found in "
        "app/modules/auth/password_reset_service.py. "
        "If you refactored the callsite to read template_id from a constant "
        "or f-string, revert — the AST walker (D-41-11) only accepts "
        "ast.Constant(str). "
        f"Got literal template_ids: {found_literal_template_ids}"
    )

    # Exactly ONE dispatcher callsite is expected in password_reset_service.py:
    # ``request_password_reset`` enqueues; ``confirm_password_reset`` and
    # ``accept_invitation`` never enqueue (D-44-09 / D-44-20). A future change
    # that adds a second callsite must be reviewed for anti-oracle implications
    # before this assertion is relaxed.
    password_reset_literal_count = sum(
        1 for tid in found_literal_template_ids if tid == "PASSWORD_RESET_EMAIL"
    )
    assert password_reset_literal_count == 1, (
        "Expected exactly 1 PASSWORD_RESET_EMAIL literal callsite in "
        "app/modules/auth/password_reset_service.py "
        f"(found {password_reset_literal_count}). A new dispatcher callsite "
        "requires anti-oracle review (D-44-06 / D-44-09 envelope parity) "
        "before this assertion is updated."
    )


def test_email_online_payment_succeeded_literal_at_tasks_callsite() -> None:
    """Phase 52 D-52-07 — positive-fixture for EMAIL_ONLINE_PAYMENT_SUCCEEDED.

    Plan 52-04 shipped the first ``get_email_dispatcher()(template_id=...)``
    callsite in ``app/modules/online_payments/tasks.py`` inside
    ``_dispatch_email``. This test pins the contract that the literal
    ``"EMAIL_ONLINE_PAYMENT_SUCCEEDED"`` exists as an ``ast.Constant(str)``
    directly at a callsite in ``online_payments/tasks.py``.

    A future refactor that extracts the identifier to a constant reference
    (e.g. ``template_id=EMAIL_ONLINE_PAYMENT_SUCCEEDED_CONST``) would silently
    bypass ``test_real_callsites_pass`` — the global gate rejects only
    non-Constant nodes. This test catches that refactor (D-52-07 anti-weakening
    discipline; mirrors D-43-33 + D-44-36 positive-fixture patterns).

    Walker logic mirrored locally (not delegated to ``_iter_dispatcher_calls``)
    so a refactor of the production walker cannot silently weaken this gate.
    """
    tasks_py = _BACKEND_APP / "modules" / "online_payments" / "tasks.py"
    tree = ast.parse(tasks_py.read_text(encoding="utf-8"))

    found_literal_template_ids: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if (
                kw.arg == "template_id"
                and isinstance(kw.value, ast.Constant)
                and isinstance(kw.value.value, str)
            ):
                found_literal_template_ids.append(kw.value.value)

    assert "EMAIL_ONLINE_PAYMENT_SUCCEEDED" in found_literal_template_ids, (
        "Phase 52 D-52-07 violation: literal EMAIL_ONLINE_PAYMENT_SUCCEEDED "
        "template_id callsite not found in "
        "app/modules/online_payments/tasks.py. "
        "If you refactored the callsite to read template_id from a constant "
        "or f-string, revert — the AST walker (D-41-11) only accepts "
        "ast.Constant(str). "
        f"Got literal template_ids: {found_literal_template_ids}"
    )


def test_email_online_payment_refunded_literal_at_tasks_callsite() -> None:
    """Phase 52 D-52-07 — positive-fixture for EMAIL_ONLINE_PAYMENT_REFUNDED.

    Mirrors ``test_email_online_payment_succeeded_literal_at_tasks_callsite``
    for the refund-succeeded notification kind. The literal
    ``"EMAIL_ONLINE_PAYMENT_REFUNDED"`` must appear as an ``ast.Constant(str)``
    directly at a ``get_email_dispatcher()(template_id=...)`` callsite inside
    ``online_payments/tasks.py``.

    A future refactor extracting this to a constant reference would bypass
    ``test_real_callsites_pass`` — this test catches it (D-52-07 anti-weakening
    discipline; mirrors D-43-33 + D-44-36 positive-fixture patterns).
    """
    tasks_py = _BACKEND_APP / "modules" / "online_payments" / "tasks.py"
    tree = ast.parse(tasks_py.read_text(encoding="utf-8"))

    found_literal_template_ids: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if (
                kw.arg == "template_id"
                and isinstance(kw.value, ast.Constant)
                and isinstance(kw.value.value, str)
            ):
                found_literal_template_ids.append(kw.value.value)

    assert "EMAIL_ONLINE_PAYMENT_REFUNDED" in found_literal_template_ids, (
        "Phase 52 D-52-07 violation: literal EMAIL_ONLINE_PAYMENT_REFUNDED "
        "template_id callsite not found in "
        "app/modules/online_payments/tasks.py. "
        "If you refactored the callsite to read template_id from a constant "
        "or f-string, revert — the AST walker (D-41-11) only accepts "
        "ast.Constant(str). "
        f"Got literal template_ids: {found_literal_template_ids}"
    )


def test_email_online_payment_canceled_literal_at_tasks_callsite() -> None:
    """Phase 52 D-52-07 — positive-fixture for EMAIL_ONLINE_PAYMENT_CANCELED.

    Mirrors the payment_succeeded/refunded fixtures for the owner-alert
    payment_canceled kind. The literal ``"EMAIL_ONLINE_PAYMENT_CANCELED"``
    must appear as an ``ast.Constant(str)`` directly at a callsite inside
    ``online_payments/tasks.py``.

    OWNER-ALERT: this email routes to ``settings.owner_alert_email``, NOT
    to the client (NOT-05 — no client DM on cancellation). A future refactor
    to a constant reference would bypass ``test_real_callsites_pass``; this
    test catches it (D-52-07 anti-weakening discipline).
    """
    tasks_py = _BACKEND_APP / "modules" / "online_payments" / "tasks.py"
    tree = ast.parse(tasks_py.read_text(encoding="utf-8"))

    found_literal_template_ids: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if (
                kw.arg == "template_id"
                and isinstance(kw.value, ast.Constant)
                and isinstance(kw.value.value, str)
            ):
                found_literal_template_ids.append(kw.value.value)

    assert "EMAIL_ONLINE_PAYMENT_CANCELED" in found_literal_template_ids, (
        "Phase 52 D-52-07 violation: literal EMAIL_ONLINE_PAYMENT_CANCELED "
        "template_id callsite not found in "
        "app/modules/online_payments/tasks.py. "
        "If you refactored the callsite to read template_id from a constant "
        "or f-string, revert — the AST walker (D-41-11) only accepts "
        "ast.Constant(str). "
        f"Got literal template_ids: {found_literal_template_ids}"
    )


def test_email_fiscal_receipt_failed_literal_at_tasks_callsite() -> None:
    """Phase 52 D-52-07 — positive-fixture for EMAIL_FISCAL_RECEIPT_FAILED.

    Mirrors the other Phase 52 positive-fixture tests for the owner-alert
    fiscal_failed kind. The literal ``"EMAIL_FISCAL_RECEIPT_FAILED"`` must
    appear as an ``ast.Constant(str)`` directly at a callsite inside
    ``online_payments/tasks.py``.

    OWNER-ALERT: this email routes to ``settings.owner_alert_email`` (NOT-04).
    A future refactor to a constant reference would bypass
    ``test_real_callsites_pass`` — this test catches it (D-52-07 anti-weakening
    discipline; mirrors D-43-33 + D-44-36 positive-fixture patterns).
    """
    tasks_py = _BACKEND_APP / "modules" / "online_payments" / "tasks.py"
    tree = ast.parse(tasks_py.read_text(encoding="utf-8"))

    found_literal_template_ids: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if (
                kw.arg == "template_id"
                and isinstance(kw.value, ast.Constant)
                and isinstance(kw.value.value, str)
            ):
                found_literal_template_ids.append(kw.value.value)

    assert "EMAIL_FISCAL_RECEIPT_FAILED" in found_literal_template_ids, (
        "Phase 52 D-52-07 violation: literal EMAIL_FISCAL_RECEIPT_FAILED "
        "template_id callsite not found in "
        "app/modules/online_payments/tasks.py. "
        "If you refactored the callsite to read template_id from a constant "
        "or f-string, revert — the AST walker (D-41-11) only accepts "
        "ast.Constant(str). "
        f"Got literal template_ids: {found_literal_template_ids}"
    )
