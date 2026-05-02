"""Audit event emission (D-21).

Phase 5 — pure structlog passthrough. Phase 8 (INFRA-04 / AUDIT-01..03) will
swap the body of `emit()` to ALSO write a row to the `audit_log` table, without
changing any call site. This is the contract: locked `event=` names per D-20.

Locked event names (do NOT invent new ones — Phase 8 contract):
  - login_success                       {user_id, email, ip}
  - login_failed                        {email, reason, ip}
  - session_revoked                     {user_id, family_id}
  - session_revoked_all                 {user_id, family_count}
  - family_reuse_detected               {user_id, family_id, presented_token_hash_prefix}
  - password_changed_revokes_sessions   {user_id, family_count}
  - (Phase 7 will add otp_issued / otp_consumed)

Architectural boundary: app.core.audit MUST NOT import from app.modules.*
(importlinter `core-not-depend-on-modules` contract).
"""

from typing import Any

import structlog

_logger = structlog.get_logger("audit")


def emit(event: str, **fields: Any) -> None:
    """Emit an audit event. Phase 5: structlog INFO. Phase 8: structlog INFO + DB INSERT.

    `event` becomes the structlog message; all `fields` become structured kwargs
    carried under `request_id` from RequestIdMiddleware (already bound to contextvars).
    """
    _logger.info(event, **fields)
