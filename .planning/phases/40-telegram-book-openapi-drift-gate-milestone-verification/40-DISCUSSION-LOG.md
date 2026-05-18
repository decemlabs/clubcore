# Phase 40: Telegram /book + OpenAPI Drift Gate + Milestone Verification - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-18
**Phase:** 40-telegram-book-openapi-drift-gate-milestone-verification
**Mode:** `--auto` (Claude auto-selected the recommended default for every gray area; user may override before `/gsd-plan-phase 40` consumes the CONTEXT.md)
**Areas discussed:** Plan breakdown, Bot service entry point, Audit payload for self-service booking, Slot list source, Keyboard layout, Update-id dedup helper, Callback data validation, Anti-oracle error mapping, OpenAPI artifact commit strategy, Forward-guard list, Verification log shape, Curl scenario set, Telegram sandbox approach, Cron operator scenarios, CI evidence scope, Deferred items handling

---

## 1. Plan breakdown (D-40-01)

| Option | Description | Selected |
|---|---|---|
| 3 plans (handlers / handoff / verify) | Collapse 40-02 + 40-03 into one; ships 1 fat handler plan + 1 artifact plan + 1 verification plan | |
| **5 plans (40-01..40-05)** | Split handlers into context-wiring / command-handler / callback-handler; keep 40-04 (handoff) + 40-05 (verify) | ✓ (recommended default) |
| 6 plans (handlers split 4 ways) | Further split + dedicated migration plan | |

**Auto-mode rationale:** Matches v1.2 Phase 20 cadence for bot phases (command + callback are separate plans). 5 plans across 4 waves keeps each plan commit-sized.

---

## 2. Bot service entry point (D-40-04)

| Option | Description | Selected |
|---|---|---|
| Fake `CurrentUser` instance | Construct a synthetic `CurrentUser(id=client_id, role=Role.RECEPTION)` and pass to existing `create_booking` | |
| `actor=None` overload | Make `create_booking`'s actor parameter optional; branch on None internally | |
| **NEW `create_booking_via_bot(session, *, client_id, slot_id, pt_package_id)`** | Parallel self-service entry point mirroring v1.2 D-10 `create_visit_self_checkin` split | ✓ (recommended default) |

**Auto-mode rationale:** Mirrors the locked v1.2 Phase 20 D-10 pattern; keeps the existing HTTP-path `create_booking` signature intact; type-system honest.

---

## 3. Audit payload for self-service booking (D-40-05)

| Option | Description | Selected |
|---|---|---|
| **Relax `BookingCreatedPayload.actor_role` Literal to add `'telegram_bot'`** | Allow `actor_user_id=None` for telegram_bot rows only via Pydantic validator | ✓ (recommended default) |
| New event `booking_self_booked_via_bot` | Expand `LOCKED_AUDIT_EVENTS` 56 → 57; new payload schema | |
| Reuse `actor_role='reception'` with hidden flag | Carry a `via_bot=True` payload field; query-side filters on this | |

**Auto-mode rationale:** Smallest blast radius. Single event source for analytics; the Literal expansion + `actor_user_id` nullability is a 1-line schema relaxation.

---

## 4. Slot list source (D-40-06)

| Option | Description | Selected |
|---|---|---|
| **Direct `schedule_service.list_slots(session, query)`** | Bot calls the same public service entry the HTTP router uses | ✓ (recommended default) |
| New `register_top_active_slots_resolver` Protocol slot | Phase 37-style resolver registration | |
| Inline raw SQL in handler | Skip service layer | |

**Auto-mode rationale:** SLOT-08 REQUIREMENTS explicitly names this endpoint as the bot's discovery surface. No new abstraction needed.

---

## 5. Keyboard layout (D-40-07)

| Option | Description | Selected |
|---|---|---|
| **1 button per row, label `"DD.MM HH:MM — {trainer_name}"`** | Vertical layout, 5 rows max | ✓ (recommended default) |
| 2 buttons per row | Horizontal pairing; shorter labels | |
| Carousel / paginated keyboard | "More slots" button for >5 results | |

**Auto-mode rationale:** Mobile-rendering safe; trainer name visible without truncation; consistent with admin-web confirm-dialog stack pattern.

---

## 6. Update-id dedup helper (D-40-08)

| Option | Description | Selected |
|---|---|---|
| Duplicate inline in `book_handler` + `book_callback_handler` | Copy the existing checkin block | |
| **Extract `_dedupe_update_id(redis, update_id)` module-level helper** | Pure refactor in plan 40-01 before new handlers consume it | ✓ (recommended default) |
| Move to `app/core/redis.py` | Promote to core utility | |

**Auto-mode rationale:** Defeats drift between v1.2 checkin and v1.5 booking dedup behaviour. Keeps the helper in the integrations layer where it belongs.

---

## 7. Callback data shape & validation (D-40-09)

| Option | Description | Selected |
|---|---|---|
| **`BK:{slot_uuid}` (39 bytes); PTB `pattern=` filter + strict regex re-validation** | Stateless; well under 64-byte limit | ✓ (recommended default) |
| `B:{slot_uuid}` (37 bytes) | 2 bytes saved; same semantics | |
| `BK:{slot_uuid}:{nonce}` (~50 bytes) | Reserve nonce for future double-tap dedup | |

**Auto-mode rationale:** BOT-02 explicitly locks `BK:{slot_uuid}`; nonce isn't needed (the partial UNIQUE handles race-loss at DB).

---

## 8. Anti-oracle error mapping (D-40-10)

| Option | Description | Selected |
|---|---|---|
| **All 7 domain errors → `_BOT_BOOK_DENIED_DM` (single string)** | Anti-oracle C-12; discriminating info goes to structlog only | ✓ (recommended default) |
| Distinct DM per error class | Better UX but leaks oracle | |
| Generic DM + retry button | Encourages probing | |

**Auto-mode rationale:** Locked at the milestone level by C-12 / `_BOT_BOOK_DENIED_DM` naming. UX cost is acknowledged and accepted.

---

## 9. OpenAPI artifact commit strategy (D-40-11)

| Option | Description | Selected |
|---|---|---|
| **Single atomic commit: openapi.json + schema.d.ts + schema.contract.test.ts** | Mirror Phase 35 commit `511cbf1` shape | ✓ (recommended default) |
| 2 commits: regen artifacts first, then test additions | Easier review per-file | |
| 3 commits: per-file split | Smallest per-commit diff | |

**Auto-mode rationale:** Both CI drift gates check `git diff --exit-code` — splitting leaves intermediate commits red on one gate.

---

## 10. Forward-guard list (D-40-12)

| Option | Description | Selected |
|---|---|---|
| **+10 `AssertNonNever` assertions (running count 36 → 46)** | Per HANDOFF-02 explicit estimate | ✓ (recommended default) |
| +5 (only path roots, no method-level guards) | Faster to write; weaker forward-guard | |
| +15 (also cover GET /bookings/{id} + 2 PATCH endpoints if they exist) | Maximum coverage | |

**Auto-mode rationale:** Matches HANDOFF-02 estimate exactly. Planner may adjust ±1 based on Phase 38 router introspection findings (`GET /bookings/{booking_id}`).

---

## 11. Verification log shape (D-40-13)

| Option | Description | Selected |
|---|---|---|
| **Byte-for-byte mirror v1.4 `VERIFICATION-LOG.md`** | YAML frontmatter + same sections + `### Final disposition` | ✓ (recommended default) |
| Markdown-only (no YAML frontmatter) | Lighter weight | |
| JSON manifest + companion narrative | Machine-readable | |

**Auto-mode rationale:** v1.4 template is locked; deviations require explicit operator decision. Reuse maximizes auditability across milestones.

---

## 12. Curl scenario set (D-40-14)

| Option | Description | Selected |
|---|---|---|
| **6 scenarios verbatim from VER-05** | Publish+list, book reception, concurrent race, 24h cancel dual-role, refund 409, PT-session completes | ✓ (recommended default) |
| 8 scenarios (add ARQ smoke + audit query) | Wider coverage | |
| 4 scenarios (skip cancel + refund) | Shorter runbook | |

**Auto-mode rationale:** REQUIREMENTS VER-05 names exactly these 6. Adding or removing scenarios requires REQUIREMENTS amendment.

---

## 13. Telegram sandbox approach (D-40-15)

| Option | Description | Selected |
|---|---|---|
| **Real BotFather sandbox bot + real test client; screenshots with chat IDs redacted** | Highest-fidelity verification | ✓ (recommended default) |
| Scripted PTB integration test only | Faster; weaker proof | |
| Hybrid: scripted test + 1 live screenshot | Compromise | |

**Auto-mode rationale:** REQUIREMENTS BOT-VER copy says "Telegram sandbox smoke" — scripted alternative requires explicit deviation note.

---

## 14. Cron operator scenarios (D-40-16)

| Option | Description | Selected |
|---|---|---|
| **Run existing Phase 39 one-shot scripts + capture stdout + DB query proof** | `run_no_show_cron_once.py` + `run_booking_reminders_once.py` | ✓ (recommended default) |
| Trigger via ARQ test runner | More realistic but harder to capture | |
| Skip (cron already proved in Phase 39) | Faster milestone close | |

**Auto-mode rationale:** Operator-facing one-shot runners are exactly the v1.4 pattern; idempotency proof on the second run is the key evidence.

---

## 15. CI evidence scope (D-40-17)

| Option | Description | Selected |
|---|---|---|
| **4 backend gates + 1 frontend codegen drift gate = 5 captures** | Mirror v1.4 + add the schema.d.ts drift gate | ✓ (recommended default) |
| 4 backend gates only (per VER-08 literal) | Smaller capture | |
| All 8+ gates including lint/test frontends | Maximum thoroughness | |

**Auto-mode rationale:** VER-08 names 4 backend; frontend codegen drift gate is the natural twin for HANDOFF-01/02 and lives in the same workflow file.

---

## 16. Deferred items handling (D-40-18)

| Option | Description | Selected |
|---|---|---|
| **Roll DEFER-36-04-A + B forward to v1.9; acknowledge in score line** | No inline sweep unless cheap | ✓ (recommended default) |
| Sweep DEFER-36-04-A inline during 40-04 | 11 failures resolved, 1 extra plan | |
| Re-open as v1.5 closing scope | Block milestone until clean | |

**Auto-mode rationale:** Same disposition as v1.4 → v1.5 (deferred items rolled forward to the next polish milestone, v1.9 API Handoff + Production Hardening).

---

## Claude's Discretion

The following details are left to the planner's research and codebase-mapping phase per CONTEXT.md `Claude's Discretion` block:

- Exact line number for the `_dedupe_update_id` extraction target.
- Whether `GET /api/v1/bookings/{booking_id}` exists (determines +10 vs +11 AssertNonNever count).
- Whether `BookingCreatedPayload.actor_user_id` is currently `str` or `str | None` (Pydantic validator needed or not).
- Whether `register_top_active_slots_resolver` Protocol-slot alternative is preferred over direct service call (only if import-linter conflict surfaces).
- Exact audit-payload field set for `actor_role='telegram_bot'` rows.

## Deferred Ideas

Captured under CONTEXT.md `<deferred>`:

- `POST /api/v1/bookings/{id}/no_show` admin endpoint — out of scope per C-10.
- Reverse `no_show → confirmed` reopen flow — out of scope per Pitfall 9.
- Postman v2.1 collection refresh — v1.9 API Handoff.
- DEFER-36-04-A (11 pytest failures) / DEFER-36-04-B (`ruff format` red on 123 files) — rolled to v1.9.
- Booking email reminders — depends on v1.6 email channel.
- A/B anti-oracle variants for booking DMs — revisit in v1.6+ if fingerprinting concern surfaces.
- `register_top_active_slots_resolver` Protocol-slot alternative — revisit only on import-linter conflict.
- `GET /api/v1/bookings/{booking_id}` single-item read — not in VER-05 scope.
- Trainer payroll / commission per session — out of scope until ≥ v1.8.
- Production frontend admin-web wiring for v1.5 paths — frozen per the 2026-05-15 pivot; design-team integration in v2.0.
