"""Reports module literal constants (Phase 54 INFRA-41).

Period-grain and metric-key literals will be defined here when Phase 55
endpoint bodies land. The ``__all__`` tuple is pre-declared so import-linter
and tooling can resolve the module cleanly.
"""

# Phase 55 will add period-grain constants (e.g. GRAIN_DAY, GRAIN_MONTH)
# and metric-key constants for revenue / visits / clients report buckets.
__all__: tuple[str, ...] = ()
