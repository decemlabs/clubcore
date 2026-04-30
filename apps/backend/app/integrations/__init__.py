"""Outbound integrations namespace.

Each subpackage adapts a single external service. Modules and workers may import
from integrations (D-03), but integrations MUST NOT import from app.modules.* —
enforced by import-linter's `integrations-not-depend-on-modules` contract.
"""
