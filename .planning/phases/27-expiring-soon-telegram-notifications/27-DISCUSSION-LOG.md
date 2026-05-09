# Phase 27: Expiring-soon Telegram Notifications - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-09
**Phase:** 27-expiring-soon-telegram-notifications
**Mode:** `--auto` (single-pass, recommended defaults selected by Claude — no interactive AskUserQuestion calls)
**Areas discussed:** Migration numbering, Telegram chat_id sourcing, Worker structure & transaction discipline, DM template module + variant selection, Audit emission shape, Send / failure handling, Cron registration, SELECT helper placement, Test layout

---

## Migration numbering

| Option | Description | Selected |
|--------|-------------|----------|
| `0008_notifications.py` | REQUIREMENTS NTF-01 verbatim wording | |
| `0009_notifications.py` | ROADMAP / milestone-roadmap wording | |
| `0010_notifications.py` | Real chain head: `0007 → 0008_freeze → 0009_renewal → 0010_notifications` | ✓ (recommended) |

**Auto-selected:** `0010_notifications.py` (D-27-01).
**Notes:** REQUIREMENTS / ROADMAP / milestone-roadmap wording all predate Phase 25 D-25-01 (which moved freeze to `0008`) and Phase 26 D-26-01 (which moved renewal to `0009`). The actual head on Phase 27 entry is `0009_renewal.py`. Plan agent must:
- Create revision `0010_notifications.py` with `down_revision = "0009_renewal"`.
- Update REQUIREMENTS NTF-01 wording (`0008` → `0010`).
- Update root ROADMAP § Phase 27 wording (`0009` → `0010`).
- Update milestone roadmap § Phase 27 + § Notes on dependencies wording.
All four wording fixes batch into the same Phase 27 docs commit.

---

## Telegram chat_id sourcing

| Option | Description | Selected |
|--------|-------------|----------|
| Add new `clients.telegram_chat_id` column (literal REQUIREMENTS naming) | Schema migration to introduce the column REQUIREMENTS NTF-01..04 references | |
| Reuse existing `clients.telegram_user_id` (Telegram private DM convention chat_id == user_id) | No schema change; document the wording mismatch in CONTEXT | ✓ (recommended) |

**Auto-selected:** Reuse `clients.telegram_user_id` (D-27-04).
**Notes:** Telegram Bot API documents that for private 1:1 chats `chat_id` equals user's id. `clients.telegram_user_id` is set during the Phase 20 `/checkin` bind flow and is the only client-side Telegram identifier on the schema. Adding a new column would duplicate the same value with no operational benefit. The `membership_notifications.telegram_chat_id BIGINT NOT NULL` snapshot column captures the value used at send time so the audit trail is complete even if the client unbinds later.

---

## Worker file & transaction discipline

| Option | Description | Selected |
|--------|-------------|----------|
| Single session per cron tick, multiple commits | Simpler shape; holds session through Telegram I/O | |
| Multi-session pattern (one session for SELECT, one per successful send) | Decouples DB from Telegram I/O; cleaner reasoning | ✓ (recommended) |
| Helper in new `notifications_service.py` module | Clean topical separation | |
| Helper in existing `service.py` (alongside `_expire_due_memberships`) | Matches Phase 18 / 25 / 26 placement | ✓ (recommended) |

**Auto-selected:** Multi-session pattern (D-27-07 pattern b) + helper in `service.py` (D-27-08).
**Notes:** Multi-session keeps DB connections free during 1-2s of Telegram round-trip. Phase 18 `_expire_due_memberships` set the placement convention; new file would split the pattern unnecessarily. Plan agent can split later if helper grows past ~60 lines.

---

## Audit emission shape

| Option | Description | Selected |
|--------|-------------|----------|
| Single dynamic call `audit.emit(f"expiring_notification_sent_{kind}", ...)` | Concise but FAILS the AST literal-string gate | |
| Three explicit if/elif/else callsites with literal event names | AST gate-compliant, slightly more lines | ✓ (recommended) |

**Auto-selected:** Three explicit callsites (D-27-12).
**Notes:** Phase 15 INFRA-11 AST walker hard-rejects f-string event names. Encapsulate in a `_emit_send_event(...)` helper with explicit branches. Payload includes `client_id`, `telegram_chat_id`, `kind`, `channel="telegram"` (richer than the audit.py docstring sketch — D-27-13 closes that drift at callsite-add time).

---

## DM template module & variant selection

| Option | Description | Selected |
|--------|-------------|----------|
| `hash(str(client_id))` for variant selection | NOT stable across processes (PYTHONHASHSEED salting) — breaks anti-oracle | |
| `client_id.bytes[0] & 1` for variant selection | UUIDv4 first byte cryptographically random ⇒ stable ~50/50 split | ✓ (recommended) |
| Templates inline in worker file | Mixes copy with logic | |
| Templates in `app/integrations/telegram/copy.py` (new file) | Mirrors Phase 20 D-20-9 copy-lock pattern | ✓ (recommended) |

**Auto-selected:** `client_id.bytes[0] & 1` + new `copy.py` (D-27-10).
**Notes:** Plan agent drafts 6 Russian DM strings; owner reviews and signs off; sign-off is recorded as a new row in PROJECT.md Key Decisions table BEFORE Phase 27 merge (mirror of v1.2 D-20-9 / D-5).

---

## Send / failure handling

| Option | Description | Selected |
|--------|-------------|----------|
| Insert idempotency row eagerly, delete on send failure | Two writes per send, partial-rollback risk | |
| Insert idempotency row only on `SendResult.ok=True` | Clean: failures simply don't write — next tick retries via NOT EXISTS | ✓ (recommended) |
| Persistent 403-block flag on row to skip future kinds | Permanent darkening of re-linkable client accounts | |
| Idempotency table is single source of truth; 403 not permanent | Re-linked clients get future window pings naturally | ✓ (recommended) |

**Auto-selected:** Insert-on-success only + idempotency-only marking (D-27-14).
**Notes:** Mirrors REQUIREMENTS NTF-05 verbatim. WARNING log carries `reason="bot_blocked"` vs `reason="transient"` for ops dashboard discrimination.

---

## Cron registration

| Option | Description | Selected |
|--------|-------------|----------|
| Both crons in one entry (combined function) | Couples expire and send into one job | |
| Separate cron entries: 06:05 expire → 06:15 send | 10-min buffer covers expire-job slowdown; clean failure isolation | ✓ (recommended) |

**Auto-selected:** Separate entries (D-27-16).
**Notes:** `unique=True, keep_result=60` matches Phase 18 reconciliation. `on_startup` cron-resolution invariant auto-validates new entry without code change. List-order is documentation; chronological ordering comes from the schedule itself.

---

## SELECT helper placement & cross-module ORM

| Option | Description | Selected |
|--------|-------------|----------|
| Import `Client` model from `clients` module | Violates `modules-independent` import-linter contract | |
| Inline `sa.text()` SQL fragment for the JOIN | Keeps query expressive without ORM cross-module imports | ✓ (recommended) |

**Auto-selected:** Inline `sa.text()` (D-27-19).
**Notes:** `find_expiring_candidates(session, *, today)` lives in `repository.py` and returns a list of `ExpiringCandidate` dataclasses. Plan agent finalises the exact SQL phrasing.

---

## Test layout

| Option | Description | Selected |
|--------|-------------|----------|
| Tests under `tests/integration/memberships/` | Co-locates with existing membership tests | |
| New `tests/integration/notifications/` subdir | Clearer grouping for ~5 new files | ✓ (recommended) |

**Auto-selected:** New `notifications/` subdir (D-27-20).
**Notes:** 6 integration files cover NTF-TEST-01..03 + select-exclusions matrix + three-kinds-one-run + idempotency-constraint check. 2 unit files cover `pick_variant` + `render_expiring_dm`.

---

## Claude's Discretion

Areas left for the planner to finalise:
- Exact filenames for unit/integration tests (D-27-20 — proposals only).
- `find_expiring_candidates` lives in `repository.py` (recommended) or splits to `notifications_repository.py`.
- Bot instantiation: reuse `app/integrations/telegram/bot.py` builder if present, else inline `Bot(token=...)` per cron tick.
- Date-format helper: `babel.dates.format_date(d, locale='ru', format='long')` (recommended) vs manual month-name table.
- `EXPIRING_KIND_*` constants placement: extend `app/modules/memberships/constants.py` (recommended) vs new `notifications_constants.py`.
- Add `tests/unit/test_workers_cron_resolution.py` to assert post-Phase-27 cron registry passes the on_startup invariant — recommended.
- Update audit.py docstring lines 67-71 (`expiring_notification_sent_*` payload shape) at callsite addition (D-27-13) — recommended.
- Whether the `kind` literal canonical form is `"expiring_7d"` (long, REQUIREMENTS verbatim — recommended) vs `"7d"` (short).

---

## Deferred Ideas

See CONTEXT.md `<deferred>` section for the full backlog. Highlights:
- Per-client notification opt-out / unsubscribe.
- Renewal / freeze / unfreeze celebration DMs.
- Notification state surface in admin-web.
- SMS / email fallback channel.
- Distributed lock for multi-instance ARQ deployment.
- Persistent Bot instance via ARQ `ctx`.
- Wider expiry window (30d / 0d).
