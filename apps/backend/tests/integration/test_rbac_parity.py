"""TEST-06: backend permissions ⇔ frontend can.ts/registry.ts parity (Phase 6 D-13, D-14, D-15).

Three set-equalities (D-13; counts updated through Phase 54 INFRA-42):
  1. OWNER_ONLY pairs (35 entries: 9 v1.1 + 6 v1.2 + 10 v1.4 + 4 v1.5 + 4 v1.6
     + 2 v1.8 Phase 54 INFRA-42 (VIEW|LIST on AUDIT_LOG)) — backend
     frozenset == frontend can.ts array.
  2. Resource StrEnum values — backend == frontend Resource union.
  3. Action StrEnum values — backend == frontend Action union.

Static-file analysis only — no FastAPI app, no DB, no Redis. Locked at
`tests/integration/` top-level (D-16) to signal "doesn't need infra".
"""

from __future__ import annotations

import re
from pathlib import Path

from app.core.permissions import OWNER_ONLY, Action, Resource

# D-14: parents[4] from apps/backend/tests/integration/test_rbac_parity.py is
# the repo root (parents[0]=integration, [1]=tests, [2]=backend, [3]=apps, [4]=repo root).
_REPO_ROOT = Path(__file__).resolve().parents[4]
_CAN_TS = _REPO_ROOT / "apps" / "admin-web" / "src" / "shared" / "session" / "can.ts"
_REGISTRY_TS = _REPO_ROOT / "apps" / "admin-web" / "src" / "shared" / "session" / "registry.ts"

# D-15: regex anchors the file shape; intentional that any reformat that breaks
# the regex is a parity failure (forces a deliberate update on both sides).
_PAIR_RE = re.compile(r"\{\s*action:\s*'([^']+)',\s*resource:\s*'([^']+)'\s*\}")

# Top-level TS declaration prefixes — `_parse_ts_union` stops when it encounters
# any of these AFTER its anchor line, which is the only stable signal that the
# union has ended (a blank line is not enough — see registry.ts:12-14 where
# `| 'owner-area'` is followed by a blank line and then `export type Action = ...`).
_DECL_PREFIXES = (
    "export ",
    "interface ",
    "type ",
    "const ",
    "function ",
    "class ",
)


def _read_text(path: Path) -> str:
    # D-14: a missing parity source is a parity FAILURE, not a silent skip.
    # FileNotFoundError surfaces as a collected-as-error rather than xfail.
    return path.read_text(encoding="utf-8")


def _parse_owner_only_pairs() -> set[tuple[str, str]]:
    return set(_PAIR_RE.findall(_read_text(_CAN_TS)))


def _parse_ts_union(text: str, name: str) -> set[str]:
    """Locate `export type {name} =` and extract every '<value>' literal.

    Handles BOTH:
      - Single-line union: `export type Action = 'view' | 'create' | 'edit' | 'delete' | 'refund'`
      - Multi-line union (registry.ts:1-12 Resource):
        ```
        export type Resource =
          | 'dashboard'
          | 'clients'
          ...
          | 'owner-area'
        ```

    Algorithm: find the line containing `export type {name} =`; from that
    line forward, accumulate string literals; stop on the first line AFTER
    the anchor that begins a new top-level declaration (`export `, `interface `,
    `type `, `const `, `function `, `class `) OR closes the file.

    Rationale: TS union lines either start with `|` or sit on the anchor line
    itself. A blank line followed by another `export type Action = ...` would
    erroneously bleed Action's literals into Resource's set if we used a
    "non-empty + no-pipe + no-quote" heuristic. The "next top-level decl"
    sentinel is the only stable stop signal (D-15).
    """
    lines = text.splitlines()
    try:
        start = next(i for i, ln in enumerate(lines) if f"export type {name} =" in ln)
    except StopIteration as exc:
        raise AssertionError(
            f"Could not locate `export type {name} =` in registry.ts — D-15 regex anchor lost"
        ) from exc

    collected: set[str] = set()
    for offset, ln in enumerate(lines[start:]):
        stripped = ln.lstrip()
        # Stop on the NEXT top-level declaration after our anchor (offset > 0
        # because the anchor line itself starts with `export`).
        if offset > 0 and stripped.startswith(_DECL_PREFIXES):
            break
        for match in re.finditer(r"'([^']+)'", ln):
            collected.add(match.group(1))
    return collected


def test_owner_only_pairs_match() -> None:
    """Set-equality #1 (D-13): the 9 OWNER_ONLY pairs."""
    fe_pairs = _parse_owner_only_pairs()
    be_pairs = {(a.value, r.value) for a, r in OWNER_ONLY}
    assert fe_pairs == be_pairs, (
        f"OWNER_ONLY drift detected.\n"
        f"  BE-only (in app.core.permissions, not in can.ts): {sorted(be_pairs - fe_pairs)}\n"
        f"  FE-only (in can.ts, not in app.core.permissions): {sorted(fe_pairs - be_pairs)}"
    )


def test_resource_values_match() -> None:
    """Set-equality #2 (D-13): all 11 Resource enum values match the FE union.

    Catches the failure mode where someone renames a Resource value that's
    NOT in OWNER_ONLY (e.g., 'schedule' → 'timetable'); pair-only parity
    would stay green but `can()` would return garbage at runtime.
    """
    fe = _parse_ts_union(_read_text(_REGISTRY_TS), "Resource")
    be = {r.value for r in Resource}
    assert fe == be, (
        f"Resource drift detected.\n  BE-only: {sorted(be - fe)}\n  FE-only: {sorted(fe - be)}"
    )


def test_action_values_match() -> None:
    """Set-equality #3 (D-13): all 5 Action enum values match the FE union."""
    fe = _parse_ts_union(_read_text(_REGISTRY_TS), "Action")
    be = {a.value for a in Action}
    assert fe == be, (
        f"Action drift detected.\n  BE-only: {sorted(be - fe)}\n  FE-only: {sorted(fe - be)}"
    )


def test_owner_only_count_is_forty() -> None:
    """Sanity belt — `OWNER_ONLY` is exactly 41 entries.

    Breakdown: 9 v1.1 + 6 v1.2 INFRA-08 + 11 v1.4 INFRA-19 - 1 D-34-09a
    + 4 v1.5 INFRA-27 (CREATE|EDIT|DELETE|CANCEL on SCHEDULE_SLOTS)
    + 4 v1.6 Phase 41 INFRA-37 (CREATE|UPDATE|DELETE|LIST on USERS)
    + 2 v1.8 Phase 54 INFRA-42 (VIEW|LIST on AUDIT_LOG)
    + 5 v1.9 Phase 58 INFRA-15 / D-58-15
      (CREATE|COMPENSATION, CREATE|PAYROLL, EDIT|PAYROLL, REFUND|PAYROLL, LIST|PAYROLL)
    + 1 v2.4 Phase 86 GYM-02 (EDIT on GYM).
    """
    assert len(OWNER_ONLY) == 41
    assert len(_parse_owner_only_pairs()) == 41
