"""Audit event emission (D-21).

Phase 5 — pure structlog passthrough. Phase 8 (INFRA-04 / AUDIT-01..03) will
swap the body of `emit()` to ALSO write a row to the `audit_log` table, without
changing any call site. This is the contract: locked `event=` names per D-20.

Locked event names (do NOT invent new ones — Phase 8 contract):
  - login_success                       {user_id, email?, ip?, channel}
                                        # channel: 'email_password' | 'telegram' (Phase 7 D-14)
  - login_failed                        {email, reason, ip}
  - session_revoked                     {user_id, family_id}
  - session_revoked_all                 {user_id, family_count}
  - family_reuse_detected               {user_id, family_id, presented_token_hash_prefix}
  - password_changed_revokes_sessions   {user_id, family_count}
  - telegram_deep_link_issued           {deep_link_token_hash}                       # Phase 7 D-11
  - otp_issued                          {user_id, chat_id}                            # Phase 7 D-11
  - otp_consumed                        {user_id}                                     # Phase 7 D-14
  - telegram_unknown_start              {username, chat_id, deep_link_token_hash}     # Phase 7 D-04
  - telegram_dm_blocked                 {chat_id}                                     # Phase 7 D-11
  - telegram_dm_failed                  {chat_id, error}                              # Phase 7 D-11
  - telegram_replay_attempt             {deep_link_token_hash}                        # Phase 7 D-20

Architectural boundary: app.core.audit MUST NOT import from app.modules.*
(importlinter `core-not-depend-on-modules` contract).
"""

from typing import Any

import structlog


def emit(event: str, **fields: Any) -> None:
    """Emit an audit event. Phase 5: structlog INFO. Phase 8: structlog INFO + DB INSERT.

    `event` becomes the structlog message; all `fields` become structured kwargs
    carried under `request_id` from RequestIdMiddleware (already bound to contextvars).

    The logger is resolved per-call (not cached at module scope) so
    `structlog.testing.capture_logs()` patches reach this emitter — same pattern
    `RequestIdMiddleware` uses for `request_complete`.
    """
    structlog.get_logger("audit").info(event, **fields)
