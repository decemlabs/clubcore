# Roadmap: clubcore

## Milestones

- ✅ **v1.0 Phase A: Skeleton** — Phases 1-3 (shipped 2026-05-01) — see [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- ✅ **v1.1 Auth + Clients** — Phases 4-14 (shipped 2026-05-07) — see [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)
- ✅ **v1.2 Memberships + Visits** — Phases 15-23 (shipped 2026-05-08) — see [milestones/v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md)
- ✅ **v1.3 Memberships Extras + Tech-Debt** — Phases 24-29 (shipped 2026-05-14) — see [milestones/v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md)
- ✅ **v1.4 Cash Sales + PT Packages** — Phases 30-36 (shipped 2026-05-16) — see [milestones/v1.4-ROADMAP.md](milestones/v1.4-ROADMAP.md)
- ✅ **v1.5 Schedule + Bookings (PT slots)** — Phases 37-40 (shipped 2026-05-18) — see [milestones/v1.5-ROADMAP.md](milestones/v1.5-ROADMAP.md)
- ✅ **v1.6 Email channel + Multi-user admin** — Phases 41-46 (shipped 2026-05-21) — see [milestones/v1.6-ROADMAP.md](milestones/v1.6-ROADMAP.md)
- ✅ **v1.7 Online Payments + 54-ФЗ** — Phases 47-53 (shipped 2026-05-24) — see [milestones/v1.7-ROADMAP.md](milestones/v1.7-ROADMAP.md)
- ✅ **v1.8 Reports + Audit Log read API** — Phases 54-57 (shipped 2026-05-24) — see [milestones/v1.8-ROADMAP.md](milestones/v1.8-ROADMAP.md)
- ✅ **v1.9 Trainers Complete** — Phases 58-61 (shipped 2026-05-26) — see [milestones/v1.9-ROADMAP.md](milestones/v1.9-ROADMAP.md)
- ✅ **v1.10 clubcore Rebrand** — Phases 62 + 62.1 (shipped 2026-05-26) — see [milestones/v1.10-ROADMAP.md](milestones/v1.10-ROADMAP.md)
- ✅ **v1.11 API Handoff + Production Hardening** — Phases 63-67 (shipped 2026-05-29) — see [milestones/v1.11-ROADMAP.md](milestones/v1.11-ROADMAP.md)

## Phases

<details>
<summary>✅ v1.0 — v1.10 SHIPPED (Phases 1-62.1)</summary>

All shipped milestones detailed in per-milestone ROADMAP archives above.

</details>

<details>
<summary>✅ v1.11 API Handoff + Production Hardening (Phases 63-67) — SHIPPED 2026-05-29</summary>

**Execution order: 63 → 64 → 66 → 65 → 67** (non-monotonic — Phase 65 handoff artifacts derive from the post-Phase-66 frozen spec including `components.parameters.IdempotencyKey`). Full phase details in [milestones/v1.11-ROADMAP.md](milestones/v1.11-ROADMAP.md).

- [x] **Phase 63: Tech-Debt Sweep** — ruff format + ruff safe-fix + mypy strict all exit 0 on the clean clubcore tree; v1.5 `run.sh` hardened; all 6 backend CI gates green (DEBT-01..05) — completed 2026-05-26
- [x] **Phase 64: Contract Freeze — OpenAPI Curation** — curated spec under clubcore name (info/servers/securitySchemes, cleaned operation IDs, 12-domain tags, shared error responses); Redocly lint as 7th CI gate; `contract-freeze-v1.11.0` baseline tag (FRZ-01..08) — completed 2026-05-28
- [x] **Phase 66: Idempotency Hardening** — user-scoped `verify_idempotency` (cross-user replay fix); 86400s TTL; single `idempotent_execute` orchestrator; `components.parameters.IdempotencyKey` $ref on all 22 category-A ops; 48 double-submit integration tests (IDM-01..07) — completed 2026-05-29
- [x] **Phase 65: Handoff Artifacts** — Postman v2.1 collection + Newman smoke harness + `clubcore-auth-runbook.md` + private Redocly doc-site from the post-Phase-66 frozen spec (HND-01..06) — completed 2026-05-29
- [x] **Phase 67: Operator-Pending Runbook Execution** — 4 accumulated walkthroughs executed with real evidence; Mailpit `--profile dev`; `v1.11-OPERATOR-EVIDENCE.md` populated (RUN-00..07) — completed 2026-05-29

</details>

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1-3. Phase A: Skeleton | v1.0 | 17/17 | Complete | 2026-05-01 |
| 4-14. Auth + Clients | v1.1 | 63/63 | Complete | 2026-05-07 |
| 15-23. Memberships + Visits | v1.2 | — | Complete | 2026-05-08 |
| 24-29. Memberships Extras + Tech-Debt | v1.3 | — | Complete | 2026-05-14 |
| 30-36. Cash Sales + PT Packages | v1.4 | — | Complete | 2026-05-16 |
| 37-40. Schedule + Bookings | v1.5 | 20/20 | Complete | 2026-05-18 |
| 41-46. Email + Multi-user admin | v1.6 | 82/82 | Complete | 2026-05-21 |
| 47-53. Online Payments + 54-ФЗ | v1.7 | 47/47 | Complete | 2026-05-24 |
| 54-57. Reports + Audit Log read API | v1.8 | 10/10 | Complete | 2026-05-24 |
| 58-61. Trainers Complete | v1.9 | 22/22 | Complete | 2026-05-26 |
| 62 + 62.1. clubcore Rebrand | v1.10 | 16/16 | Complete | 2026-05-26 |
| 63-67. API Handoff + Production Hardening | v1.11 | 26/26 | Complete | 2026-05-29 |

---

*Roadmap last updated: 2026-05-29 — v1.11 API Handoff + Production Hardening shipped (5 phases 63-67, 26 plans, 34/34 requirements; execution order 63 → 64 → 66 → 65 → 67). Milestone archived to `milestones/v1.11-ROADMAP.md`. 3 Phase-65 live-stack handoff confirmations acknowledged as deferred verification debt at close.*

## Backlog

### Phase 999.1: WR-06 restore PT session credit on owner force-cancel (✅ DONE 2026-05-29 — quick task 260529-ny2)

**Closure note (2026-05-29):** Implemented as a **consumption-keyed** restore, not a blind +1. FSM analysis during planning showed `sessions_remaining` is decremented only at check-in (`record_pt_session` → booking `confirmed → completed`), and the owner-cancel cascades only touch `confirmed` (un-consumed) bookings — so a literal "+1 per cancel" would over-credit. The fix restores +1 **only when a live consumed `pt_session` exists for the booking** (flips it cancelled + increments, idempotent/race-safe), emits the new `pt_session_credit_restored` audit event, and removes the NOTE WR-06 block. 5/5 verified; 56 schedule integration tests green. (For a confirmed booking with no consumed session, restore is a correct no-op.)

**Goal:** Restore `pt_packages.sessions_remaining` when an owner-initiated cancellation voids a confirmed PT booking — in both code paths: `POST /time-off?force=true` (Phase 59, `schedule/service.py:925`) and `cancel_slot` booked-cascade (`schedule/service.py:~471-504`). Closes the pre-v1.9 WR-06 documented limitation.

**Product decision (locked 2026-05-26):** Option B — always restore on owner-initiated cancellation. Rationale: client must never lose a prepaid PT session due to gym-side cancellation (industry norm; alternative leaks support burden and invites disputes).

**Requirements:** TBD (target ~3 reqs: restore-on-time-off-force, restore-on-cancel-slot-cascade, audit-event emission)

**Plans:** 0 plans

Plans:

- [ ] TBD — cross-module raw `sa.text()` UPDATE on `pt_packages.sessions_remaining` (pattern D-38-11), same UoW as booking cascade, in both schedule paths
- [ ] TBD — register `pt_session_credit_restored` in `LOCKED_AUDIT_EVENTS` with payload `{client_id, pt_package_id, booking_id, cancel_reason, sessions_remaining_before/after}`
- [ ] TBD — regression tests pinning new behavior in `tests/integration/schedule/test_time_off.py::test_create_time_off_force_cascades_booking_and_dispatches_dm` + equivalent for `cancel_slot` cascade
- [ ] TBD — remove `NOTE WR-06` block at `schedule/service.py:937` once behavior is fixed

**Source:** Phase 59 UAT WR-06 pending item; product decision recorded in this conversation 2026-05-26. Promote with `/gsd:review-backlog` when v1.12+ milestone opens.

### Phase 999.2: Wire online-payment EMAIL templates into the dispatcher (BACKLOG)

**Goal:** Close the email-wiring gap found in Phase 67 RUN-03 (Finding RUN-03-F1). The 4 Phase-52 `EMAIL_ONLINE_PAYMENT_SUCCEEDED/REFUNDED/CANCELED` + `EMAIL_FISCAL_RECEIPT_FAILED` identifiers have no rendered email copy and are not resolvable by the email dispatcher — so the email channel for online-payment notifications silently no-ops (only the Telegram DM is delivered).

**Problem:** `app/modules/online_payments/email_templates.py` contains only `Final[str]` identifier constants (no `TEMPLATES` dict). `app/integrations/email/dispatcher.py:_resolve_template` (lines 82-91) walks auth/users/memberships/bookings/payments registries but NOT `online_payments`. `_dispatch_email` (`online_payments/tasks.py:256-291`) therefore raises `KeyError`, which is swallowed by the best-effort `try/except … continue` at `tasks.py:477`.

**Requirements:** TBD (~3 reqs: author 4 locked Russian `EmailTemplate` records mirroring the DM copy in `online_payments/notifications.py`; add the `online_payments` registry branch to `_resolve_template` + the `.importlinter` ignore; integration test proving the email channel actually sends for all 4 kinds — no silent KeyError).

**Plans:** 0 plans

**Source:** Phase 67 RUN-03 owner countersign — Finding RUN-03-F1 (`.planning/handoff/v1.11-19-template-countersign.md` + `.planning/milestones/v1.11-OPERATOR-EVIDENCE.md`). Logged, not fixed (Phase 67 is execution-only). Promote with `/gsd:review-backlog`.
