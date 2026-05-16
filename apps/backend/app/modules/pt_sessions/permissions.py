"""PT-sessions module permissions stub (Phase 34).

Phase 34 D-34-03 / D-34-09a: ALL permission gating happens inline in
`router.py` via `Depends(require_permission(Action.X, Resource.PT_SESSIONS))`.
This file exists for module-shape parity with `pt_packages/` and `trainers/`
precedent; no exports.

Note: `(Action.CANCEL, Resource.PT_SESSIONS)` is NOT in `OWNER_ONLY`
(Phase 34 D-34-09a removed it). Reception passes the RBAC gate on the
cancel endpoint; the application layer raises `cancel_window_expired` 403
from `pt_sessions.service.cancel_pt_session` when reception attempts to
cancel >24h after `created_at` (B-12).
"""
