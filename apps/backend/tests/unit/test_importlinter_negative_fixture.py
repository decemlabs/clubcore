"""Phase 37 INFRA-28 — importlinter `modules-independent` contract negative-fixture test.

Two assertions:
  1. Positive — `uv run lint-imports` exits 0 against the unmodified
     `apps/backend/.importlinter` on HEAD. The contract already enumerates
     `app.modules.schedule` and `app.modules.bookings` (verified by the
     pattern-mapper); the negative-fixture file at
     `app/modules/bookings/_negative_importlinter_fixture.py` is gated by
     `if False:` so importlinter does not observe it as a real import.
  2. Negative — a synthesised tmp-path package + tmp `.importlinter`
     config that mirrors the `independence` contract type rejects a
     cross-module import. Proves the contract pattern has teeth so any
     future PR that adds `from app.modules.schedule import ...` to
     `app.modules.bookings` (or vice-versa) will go red on CI.

The negative test uses Strategy A from the plan (tmp_path mirror) rather
than mutating the real `apps/backend/.importlinter` — keeps the test
hermetic, no `finally:` restore dance required.

Pattern reference: 37-PATTERNS.md §6 (canonical negative-fixture pattern)
+ apps/admin-web/scripts/assert-eslint-fixtures.mjs (frontend analog) +
v1.4 INFRA-21 SVC001 negative-fixture (backend analog).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


def test_importlinter_modules_independent_contract_green_on_head() -> None:
    """`uv run lint-imports` from apps/backend/ exits 0 on the unmodified contract.

    Confirms (a) the contract on HEAD is satisfied and (b) the
    `_negative_importlinter_fixture.py` `if False:` gate is honoured —
    importlinter does NOT observe the gated import as a real dependency.
    """
    # Intentional blocking subprocess; partial path needed (S607). Mirrors
    # tests/integration/test_alembic_clean.py.
    result = subprocess.run(
        ["uv", "run", "lint-imports"],  # noqa: S607
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        "Expected `uv run lint-imports` to exit 0 on HEAD "
        "(modules-independent contract is satisfied + negative fixture is gated).\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_modules_independent_contract_rejects_bookings_schedule_cross_import(
    tmp_path: Path,
) -> None:
    """Synthesised independence contract goes red when one module imports another.

    Strategy A from the 37-05 plan: build a minimal tmp package +
    tmp `.importlinter` config that uses the same `type = independence`
    pattern as `apps/backend/.importlinter`, then write a forbidden
    cross-module import and assert `lint-imports` exits non-zero with the
    offending modules mentioned.

    This proves the contract pattern itself (and therefore the real
    contract enumerating `app.modules.schedule` + `app.modules.bookings`)
    will reject any future cross-module import between bookings and
    schedule, mirroring the SVC001 INFRA-21 negative-fixture proof from
    Phase 30 + the admin-web ESLint negative-fixture pattern at
    apps/admin-web/scripts/assert-eslint-fixtures.mjs. The synthesised
    `pkg.mod_a` / `pkg.mod_b` modules stand in for any pair of
    `app.modules.*` siblings (bookings + schedule canonically) — the
    `independence` contract treats every enumerated pair symmetrically.
    """
    pkg_dir = tmp_path / "pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    # mod_a deliberately imports mod_b — forbidden under independence.
    (pkg_dir / "mod_a.py").write_text(
        "from pkg.mod_b import sentinel  # noqa: F401\n",
        encoding="utf-8",
    )
    (pkg_dir / "mod_b.py").write_text(
        "sentinel = 1\n",
        encoding="utf-8",
    )

    config = tmp_path / "setup.cfg"
    config.write_text(
        (
            "[importlinter]\n"
            "root_packages =\n"
            "    pkg\n"
            "\n"
            "[importlinter:contract:pkg-modules-independent]\n"
            "name = pkg modules cannot import each other\n"
            "type = independence\n"
            "modules =\n"
            "    pkg.mod_a\n"
            "    pkg.mod_b\n"
        ),
        encoding="utf-8",
    )

    # `lint-imports --config <path>` analyses the configured root_packages
    # discoverable from cwd. We invoke from tmp_path so `pkg` is on
    # importlinter's import path. Use `uv run --project <BACKEND_DIR>` to
    # reuse the backend venv (importlinter is in its dev-deps) without
    # requiring a separate `uv sync` inside tmp_path.
    # Intentional blocking subprocess with partial path (S607); argv built
    # from trusted tmp_path / BACKEND_DIR — S603 acceptable.
    result = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "uv",
            "run",
            "--project",
            str(BACKEND_DIR),
            "lint-imports",
            "--config",
            str(config),
        ],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0, (
        "Expected synthesised independence contract to BREAK on "
        "cross-module import (pkg.mod_a -> pkg.mod_b). Got returncode 0.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    # The broken contract output mentions the offending module names.
    combined = (result.stdout + result.stderr).lower()
    assert "mod_a" in combined or "mod_b" in combined, (
        "Expected importlinter output to name the offending modules "
        "(pkg.mod_a / pkg.mod_b). Got:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
