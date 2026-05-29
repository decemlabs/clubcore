"""Integration tests for the client auth module (Phase 68 Plan 06).

Covers:
  - Two-principal isolation (CISO-02): staff↔client cross-rejection
  - Anti-oracle byte-parity (CAUTH-02): identical 202 across ≥4 phone states
  - Parametrized IDOR sweep (CISO-04): /me scoped to cookie principal only
  - Full session lifecycle (CAUTH-04): issue/refresh-rotate/logout/post-logout-401
  - Rate-limit 429 + brute-force block (CAUTH-06)
  - CISO-01 byte-parity guard: Role.CLIENT absent; permissions.py + can.ts frozen
"""
