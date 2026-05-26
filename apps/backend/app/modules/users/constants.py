"""Phase 43 users module constants.

INVITATION_TOKEN_TTL (D-43-12 / D-41-04 / RESET-03): 7-day invitation window.
Used at token-row INSERT time in service.create_user (expires_at=now()+INVITATION_TOKEN_TTL)
and at SELECT-time predicate (expires_at > now()).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Final

INVITATION_TOKEN_TTL: Final[timedelta] = timedelta(days=7)
