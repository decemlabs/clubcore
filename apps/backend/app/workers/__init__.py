"""Background workers namespace (ARQ).

Workers consume tasks from Redis and may call app.integrations.* (D-03).
They MUST NOT import app.modules.* directly — events bus pattern lands in Phase B+.
"""
