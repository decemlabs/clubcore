"""Internal ЮKassa webhook router — payment lifecycle events (Phase 50 WH-01 / D-50-01).

Anonymous-by-design (IP allowlist only — no auth, no CSRF). Mounted as the
second /_internal/* inhabitant (after /_internal/email). See module
docstring on router.py for the full discipline.
"""
