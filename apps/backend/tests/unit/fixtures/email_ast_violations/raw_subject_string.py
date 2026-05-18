"""Synthetic violation fixture — D-41-13 (non-literal / wrong-arg-shape variant).

Calls get_email_dispatcher() with template_id as a *variable* rather than
a literal. Walker must reject because the gate is literal-only (mirrors
audit.emit literal-only gate from Phase 15).
"""
from typing import Any


def get_email_dispatcher() -> Any:  # pragma: no cover — fixture stub
    raise NotImplementedError


async def emit_dynamic() -> None:
    chosen_id = "EMAIL_OTP_LOGIN"  # even though the value would be valid,
    # the non-literal AST node form must be rejected.
    await get_email_dispatcher()(
        template_id=chosen_id,
        to="x@example.com",
        audit_correlation_id=None,
    )
