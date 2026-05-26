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
- 🔜 **v1.11 API Handoff + Production Hardening** — Phases 63-67 (not yet opened)

## Phases

<details>
<summary>✅ v1.0 — v1.10 SHIPPED (Phases 1-62.1)</summary>

All shipped milestones detailed in per-milestone ROADMAP archives above.

</details>

### 🔜 v1.11 API Handoff + Production Hardening (Phases 63-67, not yet opened)

- [ ] **Phase 63: Tech-Debt Sweep** — Закрыть DEFER-46-04 (ruff/format/mypy) + DEFER-36-04-B + DEFER-40-01 (run.sh hardening) на чистом дереве перед contract-freeze артефактами
- [ ] **Phase 64: Contract Freeze — OpenAPI Curation** — Explicit `operation_id=` + `tags=[...]` + spec hygiene + pre-freeze drift gate; курированный OpenAPI становится источником для всех handoff артефактов
- [ ] **Phase 65: Handoff Artifacts** — Curated Postman v2.1 + Newman CLI smoke; расширенный auth runbook под clubcore-именем; OpenAPI doc-site как приватный артефакт
- [ ] **Phase 66: Idempotency Hardening** — CR-01/02/02b закрыты: audit всех mutating endpoints, стандартизированный `Idempotency-Key` Redis-cache flow, документация в OpenAPI + auth runbook
- [ ] **Phase 67: Operator-Pending Runbook Execution** — Все накопившиеся operator-pending walkthroughs исполнены: v1.7 VER-03 + CARRY-01/02, v1.8 VER-01, v1.9 D-61-12; MailHog `--profile dev`; evidence захвачен

## Phase Details

### Phase 63: Tech-Debt Sweep (v1.11)

**Goal**: Pre-existing tree-wide CI tech-debt + накопившийся runbook tooling приведены в зелёное состояние ДО создания contract-freeze артефактов
**Depends on**: Phase 62 (v1.10 rebrand) + Phase 62.1 (shim removal) — sweep работает на уже-переименованном чистом дереве
**Requirements**: DEBT-01..05 (TBD when v1.11 opens; REQUIREMENTS.md recreated fresh per project convention)
**Plans**: TBD

### Phase 64: Contract Freeze — OpenAPI Curation (v1.11)

**Goal**: OpenAPI spec курирован под explicit `operation_id` + `tags` + `info` гигиену; курированный artefact становится единственным источником истины для всех handoff артефактов; baseline для contract-freeze зафиксирован
**Depends on**: Phase 63 (tech-debt sweep) — curation работает на clean tree чтобы byte-stable regen был достижим
**Requirements**: FRZ-01..05 (TBD when v1.11 opens)
**Plans**: TBD

### Phase 65: Handoff Artifacts (v1.11)

**Goal**: Дизайн-команда получает приватный handoff пакет (Postman + Newman + Auth runbook + OpenAPI doc-site), полностью сгенерированный из курированного OpenAPI под clubcore-именем
**Depends on**: Phase 64 (OpenAPI curation) — все артефакты sourced из курированной spec
**Requirements**: HND-01..04 (TBD when v1.11 opens)
**Plans**: TBD

### Phase 66: Idempotency Hardening (v1.11)

**Goal**: `Idempotency-Key` semantics стандартизирована, документирована и покрыта тестами; CR-01/02/02b carry-over из Phase 33 закрыты до contract-freeze final lock
**Depends on**: Phase 64 (OpenAPI curation) — Idempotency-Key reusable parameter добавляется в курированный spec
**Requirements**: IDM-01..04 (TBD when v1.11 opens)
**Plans**: TBD

### Phase 67: Operator-Pending Runbook Execution (v1.11)

**Goal**: Все накопившиеся operator-credential-gated walkthroughs исполнены оператором с captured evidence; v1.11 milestone закрыт без operator-pending хвостов
**Depends on**: Phases 62-66 (вся кодовая часть завершена) — runbook execution требует stable backend под clubcore-именем + курированный OpenAPI + handoff артефакты ready
**Requirements**: RUN-01..06 (TBD when v1.11 opens; RUN-07/08 уже pulled forward в Phase 62.1 per D-62.1-SCOPE)
**Plans**: TBD

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
| 62. clubcore Rebrand | v1.10 | 7/7 | Complete | 2026-05-26 |
| 62.1. Finalize sportzal → clubcore rename | v1.10 | 9/9 | Complete | 2026-05-26 |
| 63. Tech-Debt Sweep | v1.11 | 0/0 | Not started (milestone not opened) | — |
| 64. Contract Freeze — OpenAPI Curation | v1.11 | 0/0 | Not started (milestone not opened) | — |
| 65. Handoff Artifacts | v1.11 | 0/0 | Not started (milestone not opened) | — |
| 66. Idempotency Hardening | v1.11 | 0/0 | Not started (milestone not opened) | — |
| 67. Operator-Pending Runbook Execution | v1.11 | 0/0 | Not started (milestone not opened) | — |

---

*Roadmap last updated: 2026-05-26 — v1.10 clubcore Rebrand SHIPPED (Phase 62 + closure Phase 62.1, 16 plans, 10/10 REB-* satisfied; tag `v1.10`). Archived to `.planning/milestones/v1.10-ROADMAP.md`. v1.11 API Handoff + Production Hardening (Phases 63-67) not yet opened — REQUIREMENTS.md will be recreated fresh per project convention; 22-requirement snapshot preserved under "Planned for v1.11" in archived `.planning/milestones/v1.10-REQUIREMENTS.md`.*
*v1.0 Coverage: 47/47 v1 requirements validated*
*v1.1 Coverage: 70/70 v1 requirements validated*
*v1.2 Coverage: 63/63 v1 requirements satisfied (2 accepted-at-planning deviations carried forward as v1.3 tech-debt — both closed in Phase 24 DEBT-01/02)*
*v1.3 Coverage: 44/44 v1.3 requirements satisfied (1 mock-mode UX deferred to v1.4 — closed in Phase 30 DEBT-05)*
*v1.4 Coverage: 61/61 v1.4 in-scope requirements satisfied (8 INFRA/DEBT + 8 TRN + 18 PAY/REF + 13 PT-package + 9 PT-session + 1 FE-10 + 4 VER). FE-11..18 (8 reqs) descoped to v2.0.*
*v1.5 Coverage: 57/57 v1.5 requirements mapped.*
*v1.6 Coverage: 48/48 v1.6 requirements satisfied (8 INFRA + 11 EMAIL/AUTH-EM + 7 USERS + 5 RESET + 9 NOTIFY + 8 HANDOFF/VER). VER-12 + VER-14 deferred to v1.7 as DEFER-46-01/02.*
*v1.7 Coverage: 48/51 v1.7 requirements delivered. 3 operator-credential-gated deferred at close (CARRY-01, CARRY-02, VER-03).*
*v1.8 Coverage: 30/30 v1.8 requirements mapped.*
*v1.9 Coverage: 15/15 v1.9 requirements mapped.*
*v1.10 Coverage: 10/10 v1.10 requirements satisfied (8 REB → Phase 62; REB-09 + REB-10 → Phase 62.1) — narrowed scope per D-10-SPLIT 2026-05-26; closure addendum 10/10 PASSED 2026-05-26.*
*v1.11 Planned: 22-requirement snapshot preserved in archived v1.10-REQUIREMENTS.md; REQUIREMENTS.md recreated fresh when milestone opens.*

## Backlog

### Phase 999.1: WR-06 restore PT session credit on owner force-cancel (BACKLOG)

**Goal:** Restore `pt_packages.sessions_remaining` when an owner-initiated cancellation voids a confirmed PT booking — in both code paths: `POST /time-off?force=true` (Phase 59, `schedule/service.py:925`) and `cancel_slot` booked-cascade (`schedule/service.py:~471-504`). Closes the pre-v1.9 WR-06 documented limitation.

**Product decision (locked 2026-05-26):** Option B — always restore on owner-initiated cancellation. Rationale: client must never lose a prepaid PT session due to gym-side cancellation (industry norm; alternative leaks support burden and invites disputes).

**Requirements:** TBD (target ~3 reqs: restore-on-time-off-force, restore-on-cancel-slot-cascade, audit-event emission)

**Plans:** 0 plans

Plans:

- [ ] TBD — cross-module raw `sa.text()` UPDATE on `pt_packages.sessions_remaining` (pattern D-38-11), same UoW as booking cascade, in both schedule paths
- [ ] TBD — register `pt_session_credit_restored` in `LOCKED_AUDIT_EVENTS` with payload `{client_id, pt_package_id, booking_id, cancel_reason, sessions_remaining_before/after}`
- [ ] TBD — regression tests pinning new behavior in `tests/integration/schedule/test_time_off.py::test_create_time_off_force_cascades_booking_and_dispatches_dm` + equivalent for `cancel_slot` cascade
- [ ] TBD — remove `NOTE WR-06` block at `schedule/service.py:937` once behavior is fixed

**Source:** Phase 59 UAT WR-06 pending item; product decision recorded in this conversation 2026-05-26. Promote with `/gsd:review-backlog` when v1.11 milestone opens.
