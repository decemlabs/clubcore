"""Background workers namespace (ARQ + standalone long-polling).

Workers consume tasks from Redis and may call app.integrations.* (D-03).
They MUST NOT import app.modules.* directly — events bus pattern lands in v1.2+.

EXCEPTION (Phase 7 D-06): app.workers.telegram_bot is permitted to import
`app.modules.auth.telegram_service` — workers MAY import a single owning
module's service layer (e.g., app.modules.auth.telegram_service) when the
worker IS that module's I/O fanout. Cross-module imports inside workers are
still forbidden (no telegram_bot importing modules.clients, etc.).

This relaxation is documented-only — no importlinter contract change is
required because no current contract enforces `workers ⊥ modules`.
The narrative will surface in Phase 7 PLAN/SUMMARY.
"""
