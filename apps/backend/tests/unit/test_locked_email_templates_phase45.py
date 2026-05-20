"""Phase 45 D-45-27 — locked-template enumeration + AST walker scope extension.

Mirrors ``tests/unit/test_locked_email_templates_ast.py`` (Phase 41 INFRA-36 /
D-41-11) shape but for the 12 Phase 45 identifiers and their 14 callsites
across 4 module files:

    - app/modules/memberships/notifications.py  (6 expiring helpers)
    - app/modules/bookings/notifications.py     (4 booking helpers)
    - app/modules/memberships/service.py        (2 receipt fanouts)
    - app/modules/pt_packages/service.py        (2 receipt fanouts)
                                                = 14 callsites total

Closes the Phase 41 INFRA-36 / D-41-11 locked-template gate at the Phase 45
surface — every new callsite passes ``ast.Constant(str)`` ``template_id``
literals; NO f-strings, NO variable interpolation.

Three layers of gate:
  1. Enumeration — every Phase 45 identifier is a member of
     ``LOCKED_EMAIL_TEMPLATES`` (the Phase 41 lock; ``audit.py:264-288``).
  2. Walker — each ``get_email_dispatcher()(template_id=...)`` callsite in
     the 4 Phase 45 source files passes ``ast.Constant(str)`` whose value is
     a member of ``LOCKED_EMAIL_TEMPLATES``.
  3. Counts — per-module callsite counts pin the expected fanout shape so a
     refactor that collapses branches (e.g. swaps a literal for a variable)
     is caught LOUDLY by both layer 2 (non-literal) AND layer 3 (count drift).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.core.audit import LOCKED_EMAIL_TEMPLATES

# parents[0]=unit, [1]=tests, [2]=backend, [3]=apps, [4]=repo root.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_BACKEND_APP = _REPO_ROOT / "apps" / "backend" / "app"


# === 12 Phase 45 template identifiers (verbatim from audit.py:273-286) ===
PHASE_45_TEMPLATE_IDS: frozenset[str] = frozenset(
    {
        # NOTIFY-08 (6) — expiring memberships A/B variants (Phase 27 D-27-10 lineage)
        "EMAIL_EXPIRING_7D_VARIANT_A",
        "EMAIL_EXPIRING_7D_VARIANT_B",
        "EMAIL_EXPIRING_3D_VARIANT_A",
        "EMAIL_EXPIRING_3D_VARIANT_B",
        "EMAIL_EXPIRING_1D_VARIANT_A",
        "EMAIL_EXPIRING_1D_VARIANT_B",
        # NOTIFY-10 (4) — booking lifecycle + reminder (Phase 39 D-39-04 lineage)
        "EMAIL_BOOKING_CONFIRMED",
        "EMAIL_BOOKING_CANCELLED_BY_CLIENT",
        "EMAIL_BOOKING_CANCELLED_BY_OWNER",
        "EMAIL_BOOKING_REMINDER_24H",
        # NOTIFY-12 (2) — payment receipts (sale + refund)
        "EMAIL_PAYMENT_RECEIPT_SALE",
        "EMAIL_PAYMENT_RECEIPT_REFUND",
    }
)

# === 4 Phase 45 source files (relative to apps/backend/) ===
PHASE_45_SOURCE_FILES: tuple[Path, ...] = (
    Path("app/modules/memberships/notifications.py"),
    Path("app/modules/bookings/notifications.py"),
    Path("app/modules/memberships/service.py"),
    Path("app/modules/pt_packages/service.py"),
)

# === Per-module expected callsite counts (literal template_id by prefix) ===
EXPECTED_COUNTS: dict[Path, tuple[int, str]] = {
    Path("app/modules/memberships/notifications.py"): (6, "EMAIL_EXPIRING_"),
    Path("app/modules/bookings/notifications.py"): (4, "EMAIL_BOOKING_"),
    Path("app/modules/memberships/service.py"): (2, "EMAIL_PAYMENT_RECEIPT_"),
    Path("app/modules/pt_packages/service.py"): (2, "EMAIL_PAYMENT_RECEIPT_"),
}


def _iter_template_id_kwargs(
    tree: ast.AST,
) -> list[tuple[int, ast.expr]]:
    """Walk ``tree`` and return ``(lineno, value_node)`` for every Call kwarg
    named ``template_id``.

    Broader than the Phase 41 walker (which requires the outer ``Call`` of a
    ``get_email_dispatcher()(...)`` double-Call shape) — Phase 45 callsites
    sometimes pre-bind ``dispatcher = get_email_dispatcher()`` and then call
    ``dispatcher(template_id=...)`` (see ``memberships/notifications.py``)
    or call the double-Call shape inline (see ``memberships/service.py``).

    Both shapes carry the ``template_id`` keyword argument, so we key off the
    kwarg name. The walker is therefore both more permissive (catches the
    pre-bind shape) and equally strict (still rejects non-Constant values).
    """
    matches: list[tuple[int, ast.expr]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if kw.arg == "template_id":
                matches.append((node.lineno, kw.value))
    return matches


def test_phase45_template_ids_are_locked() -> None:
    """Every Phase 45 identifier is a member of ``LOCKED_EMAIL_TEMPLATES``
    (the Phase 41 INFRA-36 / D-41-12 lock at ``audit.py:264-288``).

    A future change that removes one of the 12 identifiers from the frozenset
    fails LOUDLY here with the missing names listed, pointing the developer
    at ``app/core/audit.py`` for the fix.
    """
    unlocked = PHASE_45_TEMPLATE_IDS - LOCKED_EMAIL_TEMPLATES
    assert not unlocked, (
        f"Phase 45 template_ids not in LOCKED_EMAIL_TEMPLATES: {sorted(unlocked)}. "
        "Add them to audit.py:LOCKED_EMAIL_TEMPLATES or remove them from "
        "PHASE_45_TEMPLATE_IDS here."
    )
    assert len(PHASE_45_TEMPLATE_IDS) == 12, (
        f"Expected 12 Phase 45 template_ids, got {len(PHASE_45_TEMPLATE_IDS)}."
    )


@pytest.mark.parametrize("source_file", PHASE_45_SOURCE_FILES)
def test_phase45_dispatcher_callsites_are_literal(source_file: Path) -> None:
    """Every ``template_id=`` kwarg in the 4 Phase 45 source files passes
    ``ast.Constant(str)`` whose ``.value`` is a member of
    ``LOCKED_EMAIL_TEMPLATES``.

    A future "helpful" refactor that hoists the literal into a module-level
    constant (``template_id=EMAIL_EXPIRING_7D_A_CONST``) fails LOUDLY here
    because the kwarg value would be ``ast.Name`` not ``ast.Constant``.
    Mirrors the Phase 41 D-41-13 anti-weakening discipline (D-43-33 lineage).
    """
    full_path = _BACKEND_APP.parent / source_file
    assert full_path.exists(), f"Phase 45 source file missing: {full_path}"
    tree = ast.parse(full_path.read_text(encoding="utf-8"))

    violations: list[str] = []
    for lineno, value_node in _iter_template_id_kwargs(tree):
        if not isinstance(value_node, ast.Constant) or not isinstance(
            value_node.value, str
        ):
            violations.append(
                f"{source_file}:{lineno} — template_id is not ast.Constant(str): "
                f"{ast.dump(value_node)}"
            )
            continue
        if value_node.value not in LOCKED_EMAIL_TEMPLATES:
            violations.append(
                f"{source_file}:{lineno} — template_id={value_node.value!r} "
                f"is not a member of LOCKED_EMAIL_TEMPLATES"
            )

    assert not violations, (
        f"Phase 45 D-45-27 violation: non-literal or unlocked template_id "
        f"callsite(s) in {source_file}. Fix by reverting to ast.Constant(str) "
        f"or extending LOCKED_EMAIL_TEMPLATES.\nOffenders:\n  "
        + "\n  ".join(violations)
    )


@pytest.mark.parametrize(("source_file", "spec"), list(EXPECTED_COUNTS.items()))
def test_phase45_callsite_counts(
    source_file: Path, spec: tuple[int, str]
) -> None:
    """Per-module literal-callsite counts pin the expected fanout shape.

    A refactor that collapses (e.g.) the 6 expiring branches into a single
    dynamic-template_id call would drop the count from 6 → 0, failing here
    even before the literal-only gate (test 2) reports its own violations.
    Belt-and-suspenders against silent regression of the explicit-branch
    discipline (D-45-22).
    """
    expected_count, prefix = spec
    full_path = _BACKEND_APP.parent / source_file
    tree = ast.parse(full_path.read_text(encoding="utf-8"))

    matching = [
        value_node.value
        for _lineno, value_node in _iter_template_id_kwargs(tree)
        if isinstance(value_node, ast.Constant)
        and isinstance(value_node.value, str)
        and value_node.value.startswith(prefix)
    ]

    assert len(matching) == expected_count, (
        f"{source_file}: expected {expected_count} callsites with literal "
        f"template_id starting with {prefix!r}, found {len(matching)}: "
        f"{matching}. A change to the explicit-branch fanout shape "
        f"(D-45-22) requires updating EXPECTED_COUNTS here AFTER the "
        f"AST literal-only gate (test 2) confirms the new callsites pass."
    )
