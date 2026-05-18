"""Phase 44 RESET-01/02/03 placeholder — service.py created in Phase 41
INFRA-40 to satisfy SVC001 commit-gate target-file existence rule
(D-41-28).

Phase 44 fills this module with password-reset/request,
password-reset/confirm, invitation/accept, invitation/revoke service
logic — all callsites enforce the single-SQL atomic-consume invariant
on the password_reset_tokens table (Phase 41 Plan 09).
"""
