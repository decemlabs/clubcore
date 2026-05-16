"""PT-sessions module constants (Phase 34 D-34-06 / D-34-07).

NO FSM — single-row mutation only (`cancelled_at` set on cancel). Numeric
window constants live here so service unit tests can import them without
spinning up a DB.

- BACKDATING_WINDOW_DAYS_RECEPTION (B-11): reception may record sessions
  up to 7d in the past; owner is unlimited in the past; both roles reject
  future-dated `performed_at` (422 `performed_at_in_future`).
- CANCEL_WINDOW_HOURS_RECEPTION (B-12): reception may cancel up to 24h
  from `created_at` (NOT `performed_at` — operator-action recency per
  D-34-07); owner anytime.
- MAX_NOTES_CHARS / MAX_CANCEL_REASON_CHARS (D-34-02): defence-in-depth
  mirrors of the DB CHECK constraints from migration 0015_pt_sessions.
"""

BACKDATING_WINDOW_DAYS_RECEPTION = 7  # B-11
CANCEL_WINDOW_HOURS_RECEPTION = 24  # B-12
MAX_NOTES_CHARS = 500  # D-34-02 — mirrors migration CHECK ck_pt_sessions_notes_length
MAX_CANCEL_REASON_CHARS = 200  # D-34-02 — mirrors ck_pt_sessions_cancel_reason_length

__all__ = [
    "BACKDATING_WINDOW_DAYS_RECEPTION",
    "CANCEL_WINDOW_HOURS_RECEPTION",
    "MAX_CANCEL_REASON_CHARS",
    "MAX_NOTES_CHARS",
]
