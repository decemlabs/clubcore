---
phase: 27-expiring-soon-telegram-notifications
verified: 2026-05-09T00:00:00Z
status: passed
score: 15/15 must-haves verified (after post-verification gap closure)
overrides_applied: 0
gaps: []
human_verification: []
post_verification_fixes:
  - issue: "ROADMAP.md doc-drift (must-have #10)"
    resolution: "Replaced `миграция 0009 идёт после 0008` → `миграция 0010 идёт после 0009` (line 121) and `Миграция 0009_notifications.py` → `Миграция 0010_notifications.py` (line 124). All three doc files (REQUIREMENTS / ROADMAP / milestone roadmap) now consistently reference 0010_notifications.py."
  - issue: "REVIEW.md CR-01 — strippable `assert kind == EXPIRING_KIND_1D` in service.py:1210"
    resolution: "Replaced the strippable `assert` with an explicit `elif kind == EXPIRING_KIND_1D` branch + final `else: raise ValueError(f\"unknown notification kind {kind!r}\")`. Survives `python -O`. All 729 tests still pass post-fix."
---

# Phase 27: Expiring-soon Telegram Notifications — Verification Report

**Phase Goal:** Клиент с привязанным Telegram получает анти-oracle DM за 7/3/1 день до истечения membership; cron идемпотентен, не задваивает после рестарта, не шлёт frozen/cancelled/expired/unlinked.

**Verified:** 2026-05-09
**Status:** gaps_found (1 doc-drift WARNING + 1 quality finding requiring human decision)
**Re-verification:** No — initial verification

## Goal Achievement

The phase goal is **functionally achieved** in the codebase: migration, ORM, repository, service, worker, cron registration, locked Russian copy, owner sign-off, and an 8-test matrix all exist with substantive content; the full backend test suite (729 tests) passes. The only gaps are (a) two stale `0009` references in `.planning/ROADMAP.md` that Plan 27-01 SUMMARY claimed were fixed but were not, and (b) a Plan 27-02 quality issue surfaced by the code review (CR-01) requiring human disposition.

### Observable Truths (must-haves 1–15)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Migration `0010_notifications.py` exists with `down_revision="0009_renewal"`, creates `membership_notifications` table with UNIQUE on (membership_id, kind), single-column index, FK ON DELETE CASCADE | VERIFIED | `/Users/andre/Workspace/Development/clubcore/apps/backend/alembic/versions/0010_notifications.py` lines 31-32 (revision attrs); 39-80 (create_table with FK CASCADE + CHECK); 85-89 (UNIQUE); 92-96 (index) |
| 2 | ORM `MembershipNotification` mirrors migration columns + constraints | VERIFIED | `/Users/andre/Workspace/Development/clubcore/apps/backend/app/modules/memberships/models.py` lines 263-320; FK CASCADE name `fk_membership_notifications_membership_id_memberships`, UNIQUE name `uq_membership_notifications_membership_kind`, CHECK uses NAMING_CONVENTION expansion to `ck_membership_notifications_kind` |
| 3 | Repository helper `find_expiring_candidates(session, *, today)` returns Sequence[ExpiringCandidate]; SELECT joins clients via sa.text() (no app.modules.clients import); correct filter set | VERIFIED | repository.py: ExpiringCandidate frozen dataclass at lines 52-71; helper at 475-557; bound params today_plus_{1,3,7}; NOT EXISTS subquery against membership_notifications; `grep "from app.modules.clients" repository.py` returns 0 lines |
| 4 | Service helper `_send_expiring_notifications` with `# noqa: SVC001 caller-owns-txn`; multi-session pattern; success → INSERT row + audit.emit + commit; failure → structlog.warning, no row; IntegrityError caught + warning + no audit emit; three explicit if/elif/else literal `audit.emit("expiring_notification_sent_{7d,3d,1d}", ...)` callsites | VERIFIED | service.py: `_emit_send_event` lines 1165-1221 (three literal callsites at 1187, 1199, 1213); `_send_expiring_notifications` lines 1224-1334 (read session 1274-1277, per-success write session 1305-1322, IntegrityError catch at 1323-1332, structlog warning on send failure at 1291-1302) |
| 5 | Worker file `send_expiring_notifications.py` exposes `async def send_expiring_notifications(ctx) -> int`; uses `build_bot()`; calls helper; emits `send_expiring_notifications_complete count=N` | VERIFIED | `/Users/andre/Workspace/Development/clubcore/apps/backend/app/workers/scheduled/send_expiring_notifications.py` lines 35 (`from app.integrations.telegram.bot import build_bot`); 41 (signature); 58 (build_bot call); 60-65 (helper call); 67 (final structlog INFO) |
| 6 | `WorkerSettings` registers new function in `functions` AND `cron(send_expiring_notifications, hour=3, minute=15, unique=True, keep_result=60)` AFTER `expire_memberships` | VERIFIED | `apps/backend/app/workers/__init__.py` line 62 (import); 77 (functions list contains both); 88-103 (cron_jobs has both entries; new entry at 96-102 follows expire_memberships at 89-95) |
| 7 | `app/integrations/telegram/copy.py` exists with 6 module-level constants `EXPIRING_{7,3,1}D_VARIANT_{A,B}` (each with `# noqa: RUF001`); `pick_variant(client_id) -> Literal["A","B"]` using `client_id.bytes[0] & 1`; `render_expiring_dm`; `_format_ru_date`; templates contain `{end_date}` | VERIFIED | copy.py: 40-45 (6 constants with `# noqa: E501, RUF001`); 58-67 (pick_variant uses bytes[0] & 1, NOT hash()); 70-84 (render_expiring_dm); 87-90 (_format_ru_date) |
| 8 | `EXPIRING_KIND_7D/3D/1D` constants + `EXPIRING_KINDS` tuple with values "expiring_7d", "expiring_3d", "expiring_1d" | VERIFIED | constants.py: 44-47 (constants + tuple); 49-57 (`__all__` exports all four) |
| 9 | Audit docstring drift closed in `app/core/audit.py` (lines 67-78) | VERIFIED | audit.py: 67-78 — three sketches now read `{client_id, telegram_chat_id, kind, channel}` and reference `resource_id = membership.id`; `channel="telegram"` literal appears 3× |
| 10 | Documentation wording fixes — REQUIREMENTS.md NTF-01, root ROADMAP.md Phase 27 SC #1, milestone v1.3-ROADMAP.md all reference `0010_notifications.py` (no stale 0009/0008) | **PARTIAL** | REQUIREMENTS.md line 54 → `0010_notifications.py` ✓; milestone v1.3-ROADMAP.md line 64 → `0010_notifications.py` ✓ + line 61 "миграция 0010 идёт после 0009" ✓ + line 126 "migration 0010 must come after 0009" ✓. **FAILS:** root ROADMAP.md line 121 still `миграция 0009 идёт после 0008`; line 124 still `Миграция 0009_notifications.py`. Plan 27-01 Task 5 mandated this fix; SUMMARY 27-01 lines 110-114 claimed it was done. |
| 11 | `D-27-OWNER-COPY-LOCK` row exists in `.planning/PROJECT.md` Key Decisions table | VERIFIED | PROJECT.md line 183 — full row with locked-templates description, anti-oracle rationale, and auto-approval timestamp |
| 12 | All 8 tests exist (6 integration + 2 unit) | VERIFIED | `tests/integration/notifications/`: test_expiring_7d_happy_path.py (123 lines), test_frozen_skipped.py (86), test_send_403_retry.py (130), test_select_exclusions.py (109), test_three_kinds_one_run.py (104), test_idempotency_constraint.py (97), conftest.py (329); `tests/unit/integrations/telegram/`: test_copy_variant_selection.py (43), test_copy_render.py (62) |
| 13 | All 10 NTF-* requirement IDs (NTF-01..06, NTF-COPY-01, NTF-TEST-01..03) appear in PLAN frontmatter `requirements:` | VERIFIED | 27-01: NTF-01, NTF-06; 27-02: NTF-02, NTF-04, NTF-05, NTF-06; 27-03: NTF-COPY-01; 27-04: NTF-02, NTF-03, NTF-COPY-01; 27-05: NTF-TEST-01, NTF-TEST-02, NTF-TEST-03 — full coverage |
| 14 | NO new HTTP endpoints / NO MembershipResponse extensions / NO admin-web mock service touched | VERIFIED | `git log 4039190..HEAD --pretty=format:"%H" -- apps/backend/app/modules/memberships/router.py apps/backend/app/modules/memberships/schemas.py apps/admin-web/ frontend/` returns empty — zero commits during Phase 27 modified those paths |
| 15 | Full backend test suite passes | VERIFIED | `cd apps/backend && uv run python -m pytest -x -q` → `729 passed in 46.36s` |

**Score:** 14/15 truths verified (1 partial — doc drift only)

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `apps/backend/alembic/versions/0010_notifications.py` | VERIFIED | 110 lines, all required DDL + revision attrs |
| `apps/backend/app/modules/memberships/models.py` (extended) | VERIFIED | MembershipNotification class lines 263-320 |
| `apps/backend/app/modules/memberships/constants.py` (extended) | VERIFIED | 4 new exports |
| `apps/backend/app/modules/memberships/repository.py` (extended) | VERIFIED | ExpiringCandidate + find_expiring_candidates |
| `apps/backend/app/modules/memberships/service.py` (extended) | VERIFIED | _emit_send_event + _send_expiring_notifications |
| `apps/backend/app/integrations/telegram/copy.py` (new) | VERIFIED | 91 lines, 6 templates + helpers |
| `apps/backend/app/integrations/telegram/bot.py` (extended) | VERIFIED | `def build_bot(*, token: str)` at line 85 |
| `apps/backend/app/workers/scheduled/send_expiring_notifications.py` (new) | VERIFIED | 69 lines, exposes send_expiring_notifications coroutine |
| `apps/backend/app/workers/__init__.py` (extended) | VERIFIED | functions + cron_jobs both updated |
| `apps/backend/app/core/audit.py` (docstring) | VERIFIED | drift closed |
| 8 test files | VERIFIED | all present, non-trivial |
| `.planning/PROJECT.md` (D-27-OWNER-COPY-LOCK row) | VERIFIED | line 183 |
| `.planning/REQUIREMENTS.md` (NTF-01 wording) | VERIFIED | line 54 references 0010 |
| `.planning/milestones/v1.3-ROADMAP.md` (3 wording fixes) | VERIFIED | all three lines (61, 64, 126) corrected |
| `.planning/ROADMAP.md` (1 wording fix) | **FAILED** | lines 121 + 124 still reference `0009` |

### Key Link Verification

| From | To | Via | Status |
|------|----|----|--------|
| service._send_expiring_notifications | repository.find_expiring_candidates | function call inside read session | VERIFIED (service.py:1275) |
| service._emit_send_event | audit.emit literal callsites | if/elif/else dispatch | VERIFIED (service.py:1184-1221) |
| service._send_expiring_notifications | MembershipNotification ORM | session.add | VERIFIED (service.py:1307-1313) |
| worker send_expiring_notifications.py | memberships_service._send_expiring_notifications | module import + call | VERIFIED (send_expiring_notifications.py:36, 60) |
| worker send_expiring_notifications.py | telegram.bot.build_bot | module import + call | VERIFIED (send_expiring_notifications.py:35, 58) |
| WorkerSettings.cron_jobs | send_expiring_notifications coroutine | cron() registration | VERIFIED (workers/__init__.py:96-102) |
| ORM MembershipNotification | membership_notifications table | __tablename__ | VERIFIED (models.py:283) |
| migration 0010_notifications | 0009_renewal head | down_revision attr | VERIFIED (0010_notifications.py:32) |
| copy.render_expiring_dm | pick_variant | internal call | VERIFIED (copy.py:82) |
| copy.render_expiring_dm | _format_ru_date | internal call | VERIFIED (copy.py:84) |

### Data-Flow Trace (Level 4)

| Artifact | Data | Source | Real Data | Status |
|----------|------|--------|-----------|--------|
| service._send_expiring_notifications | `candidates` | repository.find_expiring_candidates → text() SQL against memberships JOIN clients | YES — real SELECT, no static returns | FLOWING |
| worker send_expiring_notifications | `count` | service helper return value | YES — derived from successful sends | FLOWING |
| copy.render_expiring_dm | template | _TEMPLATES dict resolved by (kind, variant) | YES — locked Russian copy | FLOWING |
| audit row payload | client_id, telegram_chat_id, kind, channel | bound at three explicit emit() callsites with literal kwargs | YES | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| ORM importable, table reflects expected columns + constraints | `uv run python -c "from app.modules.memberships.models import MembershipNotification; ..."` | exits 0 (proxied via test suite import) | PASS |
| Constants importable + values stable | `from app.modules.memberships.constants import EXPIRING_KIND_7D` etc. | exits 0 (test_copy_render.py asserts) | PASS |
| Backend test suite green | `cd apps/backend && uv run python -m pytest -x -q` | 729 passed in 46.36s | PASS |
| pick_variant determinism + ~50/50 split | `tests/unit/integrations/telegram/test_copy_variant_selection.py` | passes inside suite | PASS |
| render_expiring_dm output matches templates | `tests/unit/integrations/telegram/test_copy_render.py` | passes inside suite | PASS |
| Idempotency UNIQUE catches duplicate | `tests/integration/notifications/test_idempotency_constraint.py` | passes inside suite | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description (abridged) | Status |
|-------------|-------------|------------------------|--------|
| NTF-01 | 27-01 | migration 0010_notifications.py creates table with UNIQUE on (membership_id, kind) | SATISFIED |
| NTF-02 | 27-02, 27-04 | worker exposes send_expiring_notifications(ctx) → int with full SELECT filter set | SATISFIED |
| NTF-03 | 27-04 | cron(send_expiring_notifications, hour=3, minute=15, unique=True, keep_result=60) after expire_memberships | SATISFIED |
| NTF-04 | 27-02 | frozen/cancelled/expired skipped + telegram_user_id IS NULL skipped + clients.deleted_at IS NULL skipped | SATISFIED (SELECT filters explicit in repository.py:527-530) |
| NTF-05 | 27-02 | send failure → structlog.warning(reason=bot_blocked|transient), no row insert; idempotency table is single source of truth | SATISFIED (service.py:1291-1302) |
| NTF-06 | 27-01, 27-02 | audit.emit per successful send with three literal event names | SATISFIED |
| NTF-COPY-01 | 27-03, 27-04 | 6 locked Russian DM templates with anti-oracle variant + owner sign-off | SATISFIED |
| NTF-TEST-01 | 27-05 | 7d happy + idempotent re-run | SATISFIED (test_expiring_7d_happy_path.py) |
| NTF-TEST-02 | 27-05 | frozen membership not notified | SATISFIED (test_frozen_skipped.py) |
| NTF-TEST-03 | 27-05 | 403 → no row → next tick retry → success | SATISFIED (test_send_403_retry.py) |

All 10 NTF-* requirement IDs accounted for; no orphans.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `apps/backend/app/modules/memberships/service.py` | 1210 | `assert kind == EXPIRING_KIND_1D, f"unknown kind {kind!r}"` used as control-flow guard | Warning (REVIEW CR-01 = CRITICAL) | Under `python -O`, the assert is stripped; an unrecognized `kind` will silently fall through and emit `expiring_notification_sent_1d`. Production currently runs unoptimized Python so impact is theoretical, but the codebase contract is brittle. **Recommendation:** replace assert with explicit `else: raise ValueError(...)` OR guard with `if kind == EXPIRING_KIND_1D: ... else: raise ...`. |
| `.planning/ROADMAP.md` | 121, 124 | Stale `0009` migration references in Phase 27 success criterion #1 + Depends-on line | Warning | Plan 27-01 SUMMARY (lines 110-114) explicitly claimed these lines were fixed. Documentation drift only — does not affect runtime. |

### Human Verification Required

#### 1. CR-01 Disposition — `assert` Used as Runtime Control-Flow Guard

**Test:** Inspect `service.py:1210` — the dispatcher's else-branch is `assert kind == EXPIRING_KIND_1D, f"unknown kind {kind!r}"` followed by an unconditional `expiring_notification_sent_1d` emit. Decide whether to require a fix before phase merge.

**Expected:** One of:
- (a) Replace assert with `if kind == EXPIRING_KIND_1D: ... else: raise ValueError(f"unknown kind {kind!r}")` — restores defense even under `python -O`.
- (b) Defer to a follow-up gap-closure phase with documented risk acceptance — production runs unoptimized Python today; risk is contingent on operator changing deployment posture.

**Why human:** Production deployment posture (presence/absence of `python -O`) is not codebase-observable. Owner/operator must weigh immediate fix vs deferred follow-up.

### Gaps Summary

The phase goal is achieved end-to-end in the codebase. The runtime path (cron → SELECT candidates → render anti-oracle DM → send → INSERT idempotency row + audit emit; failure paths log WARNING without row insert; UNIQUE constraint catches race duplicates) is fully wired and exercised by 8 tests, and the full backend suite (729 tests) is green.

**Two issues remain:**

1. **Doc-drift gap (must-have #10 partial):** `.planning/ROADMAP.md` lines 121 and 124 still contain stale `0009` references for Phase 27 — these were Plan 27-01 Task 5's responsibility and SUMMARY 27-01 falsely reported them done. The other two doc files (`REQUIREMENTS.md`, `milestones/v1.3-ROADMAP.md`) are correct. This is a SUMMARY-vs-codebase divergence — exactly the failure mode goal-backward verification exists to catch.

2. **Code-quality finding (CR-01):** `assert kind == EXPIRING_KIND_1D` in `service.py:1210` is stripped under `python -O`. This is the single CRITICAL flag in the code review report and requires owner/operator disposition before phase closure.

**Recommendation:** treat #1 as a small gap-closure (mechanical 2-line edit to ROADMAP.md) and route #2 through human verification (decide between immediate fix or deferred follow-up phase). Both are tractable; neither blocks the phase goal at the runtime level.

---

_Verified: 2026-05-09_
_Verifier: Claude (gsd-verifier)_
