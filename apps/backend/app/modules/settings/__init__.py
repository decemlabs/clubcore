"""Settings module — three singleton configuration tables (Phase 108 CFG-02/03/04).

Three singletons, each with a deterministic UUID PK, follow the gym_info pattern
(seeded by migration 0071_seed_settings):

  BookingConfig (PK ...0003) — scalar int/bool booking rules (CFG-03).
  WorkingHoursConfig (PK ...0004) — JSONB schedule/breaks/closures (CFG-02).
  NotificationPrefsConfig (PK ...0005) — JSONB notification matrix + quiet hours (CFG-04).

This module is independent per D-20-MODULE / import-linter modules-independent contract.
No FK references to clients, trainers, or other domain modules.
"""
