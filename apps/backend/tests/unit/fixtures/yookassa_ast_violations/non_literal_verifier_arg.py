"""Synthetic violation fixture: Depends() wraps a non-canonical verifier name.

The AST gate test_locked_yookassa_constants_ast.py MUST flag the
``Depends(verify_some_alias)`` callsite below.
"""

from fastapi import APIRouter, Depends


async def verify_some_alias() -> None:
    pass


_router = APIRouter()


@_router.post("/fixture", dependencies=[Depends(verify_some_alias)])
async def _fixture_route() -> dict[str, str]:
    return {"ok": "fixture"}
