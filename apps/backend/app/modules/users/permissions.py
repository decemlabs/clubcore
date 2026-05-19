"""Phase 43 USERS resource marker (D-43-11 — grep-locality only).

Re-exports `Resource.USERS` so callsites can use the local idiom
`from app.modules.users.permissions import USERS_RESOURCE` instead
of dragging the full enum import into router/service.

No new Action verbs (D-41-22 — reuses CREATE/UPDATE/DELETE/LIST).
"""
from __future__ import annotations

from app.core.permissions import Resource

USERS_RESOURCE = Resource.USERS
