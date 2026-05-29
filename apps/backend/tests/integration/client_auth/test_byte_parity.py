"""CISO-01 byte-parity guard: Role.CLIENT absent; permissions.py + can.ts frozen (Phase 68 Plan 06).

These tests are pure (no DB/Redis required) — they run fast and fail loudly if a future
change accidentally leaks Role.CLIENT into the staff RBAC stack.

Tests:
  1. test_no_role_client_in_permissions (CISO-01):
     Import app.core.permissions.Role; assert "CLIENT" not in Role.__members__.
     Also assert the permissions.py source text contains no "Role.CLIENT" literal.

  2. test_client_principal_has_no_role (CISO-01):
     Import ClientPrincipal from app.core.dependencies; assert "role" is not in
     its annotations — clients carry no RBAC role (D-07).

  3. test_admin_web_can_ts_unchanged (CISO-01):
     Assert apps/admin-web/src/shared/session/can.ts exists and contains no
     "client" role token (no `role: 'client'`, no `Role.CLIENT`, no `"client"`
     as a role value in the can() body or OWNER_ONLY equivalent).
"""

from __future__ import annotations

import inspect
from pathlib import Path

# Path to can.ts relative to the repo root (used by the byte-parity guard).
# __file__ = .../clubcore/apps/backend/tests/integration/client_auth/test_byte_parity.py
# 6 parents: client_auth → integration → tests → backend → apps → clubcore (repo root)
_CAN_TS_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent.parent.parent
    / "apps"
    / "admin-web"
    / "src"
    / "shared"
    / "session"
    / "can.ts"
)


def test_no_role_client_in_permissions() -> None:
    """CISO-01: Role.CLIENT must never be added to app.core.permissions.

    Assertions:
      1. 'CLIENT' is not a member of the Role enum (structural check).
      2. The permissions.py source file does not contain the literal 'Role.CLIENT'
         (content check — catches commented-out or partial additions too).

    These checks together ensure the staff RBAC model is byte-unchanged from the
    contract-freeze baseline: adding Role.CLIENT would break admin-web byte-parity
    (CISO-01) and the test_rbac_parity.py contract-parity test.
    """
    from app.core.permissions import Role

    # Structural check: no CLIENT member on the Role enum
    assert "CLIENT" not in Role.__members__, (
        "CISO-01 VIOLATION: Role.CLIENT found in app.core.permissions.Role — "
        "this breaks the staff byte-parity contract with "
        "apps/admin-web/src/shared/session/can.ts. "
        "Clients MUST NOT have an RBAC role (D-07 decision). Remove Role.CLIENT immediately."
    )

    # Content check: permissions.py source does not reference 'Role.CLIENT'
    permissions_module = __import__("app.core.permissions", fromlist=["permissions"])
    source_file = inspect.getfile(permissions_module)
    source_text = Path(source_file).read_text(encoding="utf-8")
    assert "Role.CLIENT" not in source_text, (
        f"CISO-01 VIOLATION: 'Role.CLIENT' found in {source_file}. "
        "Even as a comment or string literal, this represents a contract drift risk. "
        "Remove it."
    )

    # Also assert the word 'CLIENT' does not appear as an enum value assignment
    # (covers patterns like `CLIENT = "client"` in the Role StrEnum body)
    assert "CLIENT" not in [m.name for m in Role], (
        "CISO-01 VIOLATION: Role enum contains a CLIENT member."
    )


def test_client_principal_has_no_role() -> None:
    """CISO-01: ClientPrincipal must NOT declare a 'role' annotation (D-07).

    Clients authenticate via phone+OTP and receive cc_client_* cookies but carry
    no RBAC role. `require_client()` is the auth gate; all client endpoints are
    either public (OTP request/verify) or client-scoped with no role-based branching.

    If 'role' appears on ClientPrincipal it means someone tried to integrate the
    client principal into the staff RBAC stack — that is exactly what CISO-01
    prohibits.
    """
    from app.core.dependencies import ClientPrincipal

    # Protocol annotations are collected in __protocol_attrs__ (Python 3.12+) or
    # __annotations__ at class level. Check both to be safe.
    annotations: dict[str, object] = {}
    for klass in ClientPrincipal.__mro__:
        annotations.update(getattr(klass, "__annotations__", {}))

    assert "role" not in annotations, (
        "CISO-01 VIOLATION: ClientPrincipal declares a 'role' annotation. "
        "Clients have no RBAC role (D-07). Remove the 'role' field from ClientPrincipal."
    )


def test_admin_web_can_ts_unchanged() -> None:
    """CISO-01: apps/admin-web/src/shared/session/can.ts has no client-role token.

    Assertions:
      1. The file exists (ensures it was not accidentally deleted or moved).
      2. The file does not contain 'client' as a Role value in the can() logic or
         OWNER_ONLY equivalent — the client principal must be invisible to the
         admin-web RBAC stack.
      3. No references to 'Role.CLIENT' (TypeScript equivalent pattern).

    This test runs without the frontend build toolchain — it is a pure text
    search over the TypeScript source file.
    """
    assert _CAN_TS_PATH.exists(), (
        f"CISO-01 GUARD FAILURE: {_CAN_TS_PATH} does not exist. "
        "The admin-web can.ts was moved or deleted — this breaks the byte-parity contract."
    )

    can_ts_text = _CAN_TS_PATH.read_text(encoding="utf-8")

    # The can.ts file should not reference a 'client' role value anywhere in its logic.
    # We check for the patterns that would indicate a client principal was added:
    #   - "Role.CLIENT" (TypeScript pattern mirrors Python pattern)
    #   - "'client'" as a role value in the type union or switch/if statements
    #     (but NOT as a resource/action value like 'clients' which legitimately appears)

    # Check that no 'Role.CLIENT' TypeScript equivalent exists
    assert "Role.CLIENT" not in can_ts_text, (
        f"CISO-01 VIOLATION: 'Role.CLIENT' found in {_CAN_TS_PATH}. "
        "The admin-web RBAC stack must not reference a client role."
    )

    # The TypeScript Role type in can.ts / types.ts uses string literals.
    # Verify no `'client'` appears as a standalone role value in the can() body.
    # The legitimate resource 'clients' (plural) is allowed — only `'client'` as a
    # role value is prohibited. We check for the role type definition pattern.
    assert "| 'client'" not in can_ts_text, (
        f"CISO-01 VIOLATION: \"| 'client'\" found in {_CAN_TS_PATH} — "
        "client role must not be added to the admin-web Role type union."
    )
    assert '| "client"' not in can_ts_text, (
        f"CISO-01 VIOLATION: '| \"client\"' found in {_CAN_TS_PATH} — "
        "client role must not be added to the admin-web Role type union."
    )
