"""Synthetic violation fixture — D-41-13.

This file is INTENTIONALLY non-compliant: it passes a template_id literal
string ('BOGUS_NOT_LOCKED') that is NOT in LOCKED_EMAIL_TEMPLATES. The
AST walker at tests/unit/test_locked_email_templates_ast.py MUST reject it.

This file is never imported at runtime — it is parsed by ast.parse() from
the walker test only. If this file's violation goes undetected, the walker
is broken.
"""
from typing import Any


def get_email_dispatcher() -> Any:  # pragma: no cover — fixture stub
    raise NotImplementedError


async def emit_bogus() -> None:
    await get_email_dispatcher()(
        template_id="BOGUS_NOT_LOCKED",
        to="x@example.com",
        audit_correlation_id=None,
    )
