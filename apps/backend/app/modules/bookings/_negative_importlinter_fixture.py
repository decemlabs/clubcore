"""Phase 37 INFRA-28 negative-fixture documentation for the importlinter
`modules-independent` contract.

This file documents (NOT executes) the canonical forbidden cross-module
import that the `apps/backend/.importlinter` `modules-independent`
contract MUST reject:

    from app.modules.schedule import service

Importlinter performs **static AST analysis** — every literal `import` /
`from ... import` statement is observed, including those gated under
`if False:`, `if TYPE_CHECKING:`, or any other runtime conditional. There
is therefore no safe way to encode the cross-import inline in production
code without breaking the contract. Instead, the forbidden import is
stored below as a STRING CONSTANT (`_FORBIDDEN_IMPORT_LINE`), and the
negative-fixture proof lives in
`apps/backend/tests/unit/test_importlinter_negative_fixture.py`, which
synthesises an equivalent independence contract in `tmp_path` and asserts
`lint-imports` rejects it (Strategy A from 37-05 plan).

The `if False:` guard below is intentional — it documents the canonical
"gate" pattern (mirroring Phase 30 INFRA-21 SVC001 + the admin-web ESLint
negative-fixture pattern at
`apps/admin-web/scripts/assert-eslint-fixtures.mjs`) without exposing any
real cross-module dependency to importlinter's graph builder.

DO NOT replace the string with a literal `from app.modules.schedule
import ...` statement. Production code MUST NEVER cross-import between
business modules — the `modules-independent` contract is the enforcement.
"""

# Canonical forbidden import — documented as a STRING so importlinter's
# AST walker does NOT observe it as a real dependency. The negative test
# at tests/unit/test_importlinter_negative_fixture.py synthesises an
# equivalent independence contract in tmp_path and asserts the offender
# is reported.
_FORBIDDEN_IMPORT_LINE: str = "from app.modules.schedule import service"

if False:  # pragma: no cover — documents the "gate" pattern; body intentionally inert
    # If you are tempted to write a literal cross-module import here,
    # STOP. Importlinter scans the AST regardless of runtime gating;
    # the import would break the contract on every CI run.
    _gate_marker: str = _FORBIDDEN_IMPORT_LINE

__all__: list[str] = []
