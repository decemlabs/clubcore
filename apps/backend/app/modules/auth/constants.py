"""Phase 44 auth module constants.

PASSWORD_RESET_TOKEN_TTL (D-44-05 / RESET-03): 1-hour password-reset window
(OWASP 2025 floor). Read at token-row INSERT time
(expires_at = now() + PASSWORD_RESET_TOKEN_TTL) and at SELECT-time predicate
(expires_at > now() in the atomic-consume WHERE clause).

Mirrors users/constants.py:INVITATION_TOKEN_TTL shape (Phase 43 D-43-12).
"""
from __future__ import annotations

from datetime import timedelta
from typing import Final

# D-44-05 — Password-reset token TTL = 1 hour (OWASP 2025 floor).
# Read at INSERT time (expires_at = now() + TTL) and at SELECT-time
# predicate (expires_at > now() in the atomic-consume WHERE clause).
# Mirrors users/constants.py:INVITATION_TOKEN_TTL shape (Phase 43 D-43-12).
PASSWORD_RESET_TOKEN_TTL: Final[timedelta] = timedelta(hours=1)
