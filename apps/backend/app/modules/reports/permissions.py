"""Reports module permissions (Phase 54 INFRA-41 scaffold).

REPORTS is owner-only via ``(Action.VIEW, Resource.REPORTS)`` in ``OWNER_ONLY``
(D-54-03). The router uses the plain ``require_permission(Action.VIEW,
Resource.REPORTS)`` chokepoint — no custom factory is needed in Phase 54.

If a scoped reception-admitting factory is desired later, the pattern
is in ``app/modules/payments/permissions.py`` (``require_payments_view_for_subject``).
"""
