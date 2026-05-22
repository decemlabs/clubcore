"""Online payments permissions placeholder (Phase 49 D-49-01 / D-49-24).

EMPTY by design. PAY endpoints reuse existing (CREATE, MEMBERSHIPS) and
(CREATE, PT_PACKAGES) permission pairs from app.core.permissions — neither
is in OWNER_ONLY (both are reception+owner). No local can-checks needed.

Phase 52 NOTIFY-xx may add notification-channel can-checks here.
"""
