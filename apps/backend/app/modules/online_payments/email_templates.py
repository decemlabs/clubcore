"""Online payments email template identifiers (Phase 49 D-49-01, extended Phase 52 NOTIFY-02).

Phase 49 note — this file exists so the import-linter ignore
``app.integrations.email.dispatcher → app.modules.online_payments.email_templates``
(``.importlinter:123``) becomes MATCHED, dropping the ``warn`` for that
one edge.

Phase 52 note (D-52-07) — 4 ``Final[str]`` email template identifier constants
are added below and registered in ``LOCKED_EMAIL_TEMPLATES`` (15 → 19).

IMPORTANT — AST gate constraint (D-52-07):
  The AST gate in ``tests/unit/test_locked_email_templates_ast.py`` requires
  ``template_id=`` arguments at every ``get_email_dispatcher()()`` callsite to be
  **string literals** — NOT variable references. The constants defined here are
  for documentation and import-linter satisfaction ONLY; the ``tasks.py``
  dispatcher calls MUST use the literal strings directly, e.g.::

      await dispatcher(template_id="EMAIL_ONLINE_PAYMENT_SUCCEEDED", ...)

  A variable reference such as ``template_id=EMAIL_ONLINE_PAYMENT_SUCCEEDED``
  would silently bypass the AST gate.
"""

from __future__ import annotations

from typing import Final

# Phase 52 NOTIFY-02 — email template identifiers. All four are registered in
# LOCKED_EMAIL_TEMPLATES (app/core/audit.py). The OWNER-COPY-LOCK lineage
# mirrors the DM template sign-off discipline (D-52-07).
EMAIL_ONLINE_PAYMENT_SUCCEEDED: Final[str] = "EMAIL_ONLINE_PAYMENT_SUCCEEDED"  # OWNER-COPY-LOCK
EMAIL_ONLINE_PAYMENT_REFUNDED: Final[str] = "EMAIL_ONLINE_PAYMENT_REFUNDED"  # OWNER-COPY-LOCK
# owner-alert (NOT-05): routed to owner, never sent to client
EMAIL_ONLINE_PAYMENT_CANCELED: Final[str] = "EMAIL_ONLINE_PAYMENT_CANCELED"  # OWNER-COPY-LOCK
# owner-alert (NOT-04): fiscal-failed operator notification
EMAIL_FISCAL_RECEIPT_FAILED: Final[str] = "EMAIL_FISCAL_RECEIPT_FAILED"  # OWNER-COPY-LOCK
