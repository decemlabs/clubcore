"""Auth-module integration test fixtures.

Provides:
  - ``_reset_auth_service_logger_cache`` — autouse fixture that clears the
    cached structlog BoundLogger on the module-level ``_log`` proxy in
    ``app.modules.auth.service``.

    Background: ``configure_logging`` calls ``structlog.configure(
    cache_logger_on_first_use=True)``.  Once ``_log`` is first invoked, the
    ``BoundLoggerLazyProxy`` caches a reference to the processor list that
    was active *at that moment*.  When a later test wraps its HTTP call in
    ``structlog.testing.capture_logs()``, that context manager swaps the
    *current* config's processor list — but the cached logger still points
    at the old list, so ``capture_logs`` misses the emission.

    Fix (identical to ``tests/integration/workers/conftest.py``): delete the
    ``bind`` attribute from the proxy's ``__dict__`` before each test so the
    lazy proxy re-resolves processors from the *current* config on the next
    call — which is the list ``capture_logs`` has already replaced.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset_auth_service_logger_cache() -> None:
    """Clear the cached structlog BoundLogger in auth.service before each test."""
    from app.modules.auth import service as service_mod

    if "bind" in service_mod._log.__dict__:
        del service_mod._log.__dict__["bind"]
