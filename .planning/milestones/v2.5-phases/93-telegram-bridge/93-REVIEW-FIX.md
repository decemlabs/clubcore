---
phase: 93-telegram-bridge
fixed_at: 2026-06-08T00:00:00Z
review_path: .planning/phases/93-telegram-bridge/93-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 93: Code Review Fix Report

**Fixed at:** 2026-06-08T00:00:00Z
**Source review:** .planning/phases/93-telegram-bridge/93-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 5 (Critical: 0, Warning: 5; Info findings out of scope)
- Fixed: 5
- Skipped: 0

All verification gates stayed green after the fixes:
- `ruff check` on the modified app source files: clean
- `mypy` (strict) on the modified app source files: clean
- `lint-imports`: 3 contracts kept, 0 broken
- `pytest tests/integration/telegram_bot tests/messaging`: 175 passed (baseline 168 + 7 new test cases)

## Fixed Issues

### WR-01 / WR-02: Telegram transport-limit truncation in `forward_to_staff`

**Files modified:** `apps/backend/app/workers/tasks/forward_to_staff.py`, `apps/backend/tests/integration/telegram_bot/test_forward_to_staff.py`
**Commit:** 927601b5
**Applied fix:** Added `_TG_TEXT_LIMIT (4096)`, `_TG_CAPTION_LIMIT (1024)`, and a `_truncate()` helper. The photo path now sends a caption truncated to 1024 chars and, when the full rendered DM is longer, delivers the complete DM as a follow-up `send_text_dm` (truncated to 4096) so no content is silently dropped. The text-only path truncates the rendered DM to 4096 chars. Previously an over-limit body produced a `BadRequest` that `send_photo`/`send_text_dm` classified as a transient failure, causing `forward_to_staff` to return `"failed"`, write no anchor, retry, then drop permanently — a silent delivery hole for a message the client had already been told was delivered. Added three tests: text truncation, photo-caption truncation with follow-up text, and a short-caption no-follow-up case.

These two findings were committed together because they share the same truncation logic and edit region in `forward_to_staff.py`.

### WR-04: Run staff-chat guard before `update_id` dedup

**Files modified:** `apps/backend/app/integrations/telegram/handlers.py`
**Commit:** 420cd2e7
**Applied fix:** Moved the side-effect-free staff-chat-id check above the `_dedupe_update_id` SET-NX call so the dedup key is only written for updates actually destined for the staff routing path. Restores the intended cheap-guard-first ordering and avoids burning a dedup key (and emitting the "wrong chat" debug log) for updates that slip past the `MessageHandler` chat filter.

### WR-03: Graceful corrupt/partial-anchor degradation

**Files modified:** `apps/backend/app/integrations/telegram/handlers.py`, `apps/backend/tests/integration/telegram_bot/test_staff_reply_handler.py`
**Commit:** 5612311b (committed together with WR-05 — see note)
**Applied fix:** Wrapped `json.loads(raw_anchor)` + `UUID(anchor["client_id"])` in `try/except (ValueError, KeyError, TypeError)`. On any parse failure the handler now logs `staff_reply_anchor_corrupt` and sends the documented stale-anchor hint DM, instead of letting the exception escape to `_global_error_handler` (which left staff with no feedback while the `update_id` was already consumed by the dedup SET-NX). Added a parametrized regression test covering bad-JSON, missing `client_id`, non-UUID value, and a `null` anchor.

### WR-05: Document group-chat trust model + audit traceability

**Files modified:** `apps/backend/app/integrations/telegram/handlers.py`
**Commit:** 5612311b (committed together with WR-03 — see note)
**Applied fix:** Added an explicit TRUST MODEL comment at the handler stating that every non-bot member of the staff chat is trusted as authoritative staff (no per-user allowlist when the staff chat is a group), and recorded `telegram_user_id=effective_user.id` in the `chat_staff_reply_sent` audit payload so any impersonation is forensically traceable. Took the documentation-plus-audit-trace option (a/c from the review) rather than introducing an allowlist, matching the single-gym trust assumption.

**Note on the combined WR-03 + WR-05 commit:** these two fixes are physically interleaved in the same reply-routing block of `handlers.py` — the WR-05 trust-model comment sits directly between the WR-03 `try/except` and the persistence block — so they were committed atomically together rather than split with a fragile partial-hunk patch.

## Skipped Issues

None — all in-scope (Warning) findings were fixed.

Info-tier findings (IN-01 through IN-04) were out of scope (`fix_scope: critical_warning`) and were not addressed. Note that IN-03 (fakeredis bytes vs prod str parity) is partially de-risked by the new WR-03 corrupt-anchor test, which exercises the parse path with `bytes` anchors.

---

_Fixed: 2026-06-08T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
