"""Online payments email templates placeholder (Phase 49 D-49-01).

EMPTY by design — Phase 52 NOTIFY-xx ships template bodies. This file
exists in Phase 49 SOLELY so the import-linter ignore
``app.integrations.email.dispatcher → app.modules.online_payments.email_templates``
(``.importlinter:123``) becomes MATCHED, dropping the ``warn`` for that
one edge.

Importing this module from production code in Phase 49 yields an empty
namespace — there are no template identifiers registered until Phase 52.
"""
