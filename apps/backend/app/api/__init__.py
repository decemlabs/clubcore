"""HTTP API surface namespace.

Layered as api → v1 → routers. The api package may import from app.modules.* (D-02);
this is the canonical FastAPI router-aggregation pattern, no registry indirection.
"""
