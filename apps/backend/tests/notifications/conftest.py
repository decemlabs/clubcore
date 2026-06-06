"""Test fixtures for notifications service tests (Phase 87 INBOX-01..04).

Re-exports the make_client and make_user fixtures from the client_portal conftest
so tests in this directory can use the same DB-direct client factory.
"""

from __future__ import annotations

from tests.modules.client_portal.conftest import make_client, make_user

__all__ = ["make_client", "make_user"]
