---
phase: 38-schedule-module-booking-core
verified: 2026-05-17T00:00:00Z
status: gaps_found
score: 4/6 must-haves verified
overrides_applied: 0
gaps:
  - truth: "Slot cancel uses PATCH /api/v1/trainer-slots/{id}/cancel per REQUIREMENTS SLOT-02 / SLOT-07 + ROADMAP Phase 38 SC #2"
    status: failed
    reason: "Implementation ships POST /api/v1/trainer-slots/{slot_id}/cancel — verb deviation undocumented. ROADMAP SC #2 explicitly names PATCH; REQUIREMENTS SLOT-02 and SLOT-07 both lock the PATCH verb. PLAN 38-01 line 205 also specified PATCH; the executor shipped POST without a recorded deviation."
    artifacts:
      - path: "apps/backend/app/modules/schedule/router.py"
        issue: "Line 176: @schedule_router.post(\"/{slot_id}/cancel\", ...) — should be .patch per SLOT-02 / SLOT-07 / SC #2 / PLAN 38-01 line 205"
    missing:
      - "Change @schedule_router.post to @schedule_router.patch on /{slot_id}/cancel"
      - "Update integration tests in tests/integration/schedule/ that call client.post(\"/api/v1/trainer-slots/{id}/cancel\") to client.patch"
      - "Refresh OpenAPI artifact (Phase 40 HANDOFF-01 already requires byte-stable regen — this change must land BEFORE that gate)"
      - "OR: record an explicit D-38-XX or override accepting POST-cancel as a deliberate departure from REQUIREMENTS, and amend SLOT-02 / SLOT-07 + the ROADMAP SC #2 wording to match"
  - truth: "Per-client bookings endpoint is mounted at GET /api/v1/clients/{id}/bookings per REQUIREMENTS BOOK-08 + ROADMAP Phase 38 SC #5"
    status: failed
    reason: "Actual mount is GET /api/v1/bookings/clients/{client_id}/bookings. ROADMAP SC #5 explicitly names /api/v1/clients/{id}/bookings; REQUIREMENTS BOOK-08 locks GET /api/v1/clients/{id}/bookings. Plan 38-03 §Task 2 chose to mount under bookings/router.py to keep clients/ a dependency-leaf module, but the resulting URL path does not match the locked contract. The decision is documented (see 38-03-PLAN truth #33 and SUMMARY §Router-bookings) but the URL re-rooting from /clients/{id}/bookings to /bookings/clients/{client_id}/bookings is a spec deviation that was not flagged in 38-CONTEXT.md as a D-38-XX nor in PROJECT.md."
    artifacts:
      - path: "apps/backend/app/modules/bookings/router.py"
        issue: "Line 277-279: @bookings_router.get(\"/clients/{client_id}/bookings\", ...) — mounted under /bookings prefix yields /api/v1/bookings/clients/{client_id}/bookings, not /api/v1/clients/{id}/bookings per BOOK-08 / SC #5"
      - path: "apps/backend/app/api/v1/router.py"
        issue: "Line 38 mounts clients_router under /clients but no /clients/{id}/bookings sub-route exists there; the per-client bookings endpoint is reached only via /bookings/clients/{client_id}/bookings"
    missing:
      - "Mount the per-client bookings GET handler at GET /api/v1/clients/{client_id}/bookings (could be a thin adapter in clients/router.py that imports bookings.service.list_bookings_for_client — or a top-level path in a separate aggregator)"
      - "OR: amend REQUIREMENTS BOOK-08 + ROADMAP SC #5 to record the URL re-rooting as a deliberate v1.5 decision (mirrors the v1.4 pt-sessions sub-route precedent), with an explicit D-38-XX entry in 38-CONTEXT.md AND a PROJECT.md note before Phase 40 HANDOFF-01 OpenAPI byte-stability gate runs"
      - "Phase 40 HANDOFF-01 success criterion #2 must be updated either way before it runs — currently it lists /clients/{id}/bookings as a v1.5 typed path"
human_verification:
  - test: "Visual API surface review — operator confirms the POST verb on slot-cancel is acceptable v1.5 wire contract, or PATCH must be honoured"
    expected: "Either ship PATCH (low-effort code fix) OR amend REQUIREMENTS + ROADMAP and lock POST as the canonical v1.5 verb via a new D-38-XX"
    why_human: "Verb choice is a deliberate API design decision; the codebase consistently uses POST for cancel across pt-sessions / pt-packages / bookings, so consistency argues for POST; but locked REQUIREMENTS / SC explicitly say PATCH — only a human can resolve the contract precedence"
  - test: "Per-client bookings URL review — operator confirms /bookings/clients/{client_id}/bookings is acceptable, or move to /clients/{client_id}/bookings"
    expected: "Either move the route (requires clients/router.py edit or a top-level aggregator) OR amend BOOK-08 + SC #5 to match the bookings-rooted mount"
    why_human: "Mount-point choice trades architectural cleanliness (clients-leaf-module) against URL contract fidelity — a human must arbitrate"
---

# Phase 38: Schedule Module + Booking Core — Verification Report

**Phase Goal:** Trainer availability slots can be published and listed; clients can be booked into slots with race-safe DB enforcement; PT-package integration (trainer_id column, refund guard, validity-window guard) and all booking read/write endpoints are operational.

**Verified:** 2026-05-17
**Status:** gaps_found
**Re-verification:** No — initial verification

---

## Goal Achievement — 5 ROADMAP Success Criteria + 25 REQ-IDs

### Observable Truths (ROADMAP Success Criteria)

| # | Success Criterion | Status | Evidence |
|---|------|--------|----------|
| 1 | Owner can publish a slot (`POST /api/v1/trainer-slots`) and list it (`GET /api/v1/trainer-slots`); overlap → 409 `slot_overlap`; buffer → 409 `slot_too_close` (SLOT-01..06) | VERIFIED | apps/backend/app/modules/schedule/router.py:54-131 (POST publish wired with RBAC+CSRF+Idempotency); service.py:260-353 publish_slot orchestrator runs overlap (l.303-310) + buffer (l.313-321) checks against repository helpers; alembic 0016 ships table + 2 indexes + status CHECK; integration tests in tests/integration/schedule/ all green |
| 2 | Owner can cancel a slot with outstanding confirmed booking via **`PATCH /api/v1/trainer-slots/{id}/cancel`** — atomic booking cascade + both audit events emitted (SLOT-07/09, BOOK-06) | PARTIAL FAIL | Cascade behaviour fully implemented (schedule.service.py:356-501 — single-commit UoW, cross-module raw SQL with TABLE_REF noqa, dual audit emits, InternalConsistencyError guard); test_slot_cancel_cascade.py passes. **BUT the HTTP verb is POST not PATCH** (router.py:176) — violates locked REQUIREMENTS SLOT-02 / SLOT-07 + SC #2 wording. See Gap #1. |
| 3 | Concurrent `POST /api/v1/bookings` → exactly one 201 + one 409 `slot_already_booked` (BOOK-02/03/10); `sessions_remaining=0` → 409 `pt_package_exhausted` (BOOK-04/05) | VERIFIED | Partial UNIQUE `uq_bookings_slot_confirmed WHERE status='confirmed'` ships in 0017 (l.130-136); discriminator `_is_slot_confirmed_conflict` at service.py:219-230; race test test_booking_race.py::test_concurrent_create_booking_partial_unique_at_db_layer passes; PtPackageExhaustedError raised at service.py:359-360 |
| 4 | `POST /api/v1/pt-packages/{id}/refund` returns 409 `outstanding_bookings_exist` when confirmed booking exists (PKG-03); `POST /api/v1/pt-sessions` with `booking_id` atomically completes booking in same UoW as decrement (PKG-04/05) | VERIFIED | pt_packages/service.py:955 raises OutstandingBookingsExistError; pt_sessions/service.py:339-340 calls `complete_booking_by_pt_session` via Protocol slot inside record_pt_session UoW; SELECT FOR UPDATE confirmed at pt_sessions/repository.py:328 (D-38-19) |
| 5 | All booking and slot list endpoints (`GET /api/v1/bookings`, `GET /api/v1/trainer-slots`, **`GET /api/v1/clients/{id}/bookings`**) return paginated `{items, total, page, pageSize}` envelopes and honour documented query filters (BOOK-07/08/09, SLOT-08) | PARTIAL FAIL | Pagination envelope `{items, total, page, pageSize}` (camelCase via BackendSchemaBase) confirmed at pagination.py:37-43. Query filter schemas implemented (BookingListQuery l.129-149, BookingsForClientListQuery l.152-162, SlotListQuery). Lazy-resolved Moscow ±30d defaults working. **BUT per-client URL is `/api/v1/bookings/clients/{client_id}/bookings` not `/api/v1/clients/{id}/bookings`** per BOOK-08 + SC #5. See Gap #2. |

**Score:** 3 fully VERIFIED + 2 PARTIAL FAIL (cascade/race-safe behaviour fully correct, but URL/verb contracts diverge from locked REQUIREMENTS/ROADMAP)

### Migration Chain Verification

| Revision | Down-Revision | File | Status |
|----------|---------------|------|--------|
| 0016_trainer_availability_slots | 0015_pt_sessions | alembic/versions/0016_trainer_availability_slots.py | VERIFIED — table + CHECK `status IN ('active','booked','cancelled')` + CHECK end>start + 2 indexes (partial active + composite trainer/start) |
| 0017_bookings | 0016_trainer_availability_slots | alembic/versions/0017_bookings.py | VERIFIED — table + named partial UNIQUE `uq_bookings_slot_confirmed` WHERE status='confirmed' (l.130-136) + 2 secondary indexes |
| 0018_pt_packages_trainer_id | 0017_bookings | alembic/versions/0018_pt_packages_trainer_id.py | VERIFIED — nullable trainer_id FK ON DELETE RESTRICT + ix_pt_packages_trainer_id |
| 0019_pt_sessions_booking_id | 0018_pt_packages_trainer_id | alembic/versions/0019_pt_sessions_booking_id.py | VERIFIED — nullable booking_id FK ON DELETE RESTRICT + ix_pt_sessions_booking_id |

Chain integrity: `0015 → 0016 → 0017 → 0018 → 0019` — VERIFIED.

### Error Code Coverage (REQUIREMENTS spec)

| Error Code | Module | Status | Location |
|------------|--------|--------|----------|
| slot_overlap | schedule | VERIFIED | service.py:93-98, 310 |
| slot_too_close | schedule | VERIFIED | service.py:101-107, 321 |
| slot_in_past | schedule | VERIFIED | service.py:86-90, 300 |
| trainer_inactive | schedule | VERIFIED | service.py:79-83, 295 |
| trainer_not_found | schedule | VERIFIED | service.py:72-76, 293 |
| slot_not_found | schedule/bookings | VERIFIED | schedule/service.py:65-69; bookings/service.py:96-100 |
| slot_already_booked | bookings | VERIFIED | service.py:112-119, 400, 426 |
| pt_package_exhausted | bookings | VERIFIED | service.py:132-138, 360 |
| pt_package_not_active | bookings | VERIFIED | service.py:141-148, 352-358 |
| pt_package_expired_before_slot | bookings | VERIFIED | service.py:151-158, 378 (Moscow-TZ guard) |
| slot_not_available | bookings | VERIFIED | service.py:103-109, 339/347/401 |
| trainer_mismatch | bookings | VERIFIED | service.py:122-129, 368 |
| cancel_window_expired | bookings | VERIFIED | service.py:169-182, 519 (compared against slot.start_time per D-38-16) |
| invalid_transition | both | VERIFIED | schedule/service.py:110-118; bookings/service.py:161-166 |
| outstanding_bookings_exist | pt_packages | VERIFIED | pt_packages/service.py:190, 955 (extends v1.4 refund flow) |
| booking_not_confirmed | pt_sessions | VERIFIED | pt_sessions/service.py:171+ |
| booking_mismatch | pt_sessions | VERIFIED | pt_sessions/service.py:283, 289 |

### Audit Event Coverage (LOCKED_AUDIT_EVENTS — Phase 37 INFRA-24)

| Event | Resource Type | Payload Schema | Emitted From |
|-------|---------------|----------------|--------------|
| slot_published | schedule_slot | SlotPublishedPayload (5 keys) | schedule/service.py:335-346 |
| slot_cancelled | schedule_slot | SlotCancelledPayload (5 keys incl. had_booking) | schedule/service.py:466-477 |
| booking_created | booking | BookingCreatedPayload (5 keys) | bookings/service.py:432-443 |
| booking_cancelled | booking | BookingCancelledPayload (4 keys — NO client_id) | bookings/service.py:543-553 + schedule/service.py:483-493 (cascade) |
| pt_session_recorded (extended w/ booking_id) | pt_session | PtSessionRecordedPayload | pt_sessions/service.py:362 (`booking_id=str(...) if not None`) |

All 5 LOCKED events fire literal-string `event` + `resource_type` per INFRA-11 AST gate (test_audit_taxonomy passes).

### D-38-NN Decision Compliance (Spot-Checks)

| Decision | Required Pattern | Status | Evidence |
|----------|-----------------|--------|----------|
| D-38-02 | bookings.pt_package_id NOT NULL FK | VERIFIED | 0017 migration l.61 `nullable=False` |
| D-38-03 | Slot status `active / booked / cancelled` (NOT `available`) | VERIFIED | 0016 CHECK l.89 + constants.SLOT_STATUS_TRANSITIONS |
| D-38-04 | NO soft-delete / deleted_at on slots | VERIFIED | 0016 migration has no deleted_at; models.py inherits TimestampMixin only |
| D-38-08 | NO `*_snapshot` columns on bookings; joinedload | VERIFIED | 0017 migration has no snapshot cols; bookings/repository.py uses joinedload(Booking.slot/pt_package) |
| D-38-11 | Cross-module raw `sa.text()` + `# noqa: TABLE_REF` | VERIFIED | schedule/service.py:430 (slot-cancel cascade), bookings/service.py:262 (complete_booking), pt_packages refund guard |
| D-38-14 | `Depends(verify_idempotency)` on POST /bookings | VERIFIED | bookings/router.py:82 |
| D-38-15 | Named UNIQUE `uq_bookings_slot_confirmed` + constraint-name discriminator | VERIFIED | 0017 l.131 + bookings/service.py:219-230 |
| D-38-16 | `datetime.now(UTC)` (no `datetime.utcnow()` regressions) | VERIFIED | grep confirms no .utcnow() callsites in schedule/bookings; cancel-window compared against `booking.slot.start_time` not `created_at` (service.py:515-519) |
| D-38-19 | SELECT FOR UPDATE in pt_sessions.record_pt_session | VERIFIED | pt_sessions/repository.py:328 |

### Architectural Contracts

| Check | Command | Result | Status |
|-------|---------|--------|--------|
| import-linter contracts | `uv run lint-imports` | 3 kept, 0 broken | VERIFIED |
| Audit taxonomy + payloads + SVC001 walkers | `uv run pytest tests/unit/test_audit_taxonomy.py test_audit_payloads.py test_service_commit_gate.py -q` | 26 passed | VERIFIED |
| modules-independent (no cross-module imports of bookings from schedule/pt_packages/pt_sessions) | `grep -r "from app.modules.bookings"` in those modules | 0 hits (only doc-string mentions) | VERIFIED |
| B-10 visits regression | `uv run pytest tests/integration/visits/ -q` | 34 passed | VERIFIED |
| Full test suite | `uv run pytest tests/ -q` | 1247 passed, 0 failed in 114.62s | VERIFIED (matches SUMMARY claim) |
| Phase 38 integration tests | `uv run pytest tests/integration/{bookings,schedule}/ -q` | 69 passed | VERIFIED |
| Race test (BOOK-TEST-01) | `uv run pytest tests/integration/bookings/test_booking_race.py -v` | 1 passed | VERIFIED |

### Anti-Pattern Scan

| Check | Result |
|-------|--------|
| TBD / FIXME / XXX markers in Phase 38 module files | None |
| `return None` / placeholder stubs in schedule/bookings services | None — all Protocol-slot bodies replaced with real implementations |
| `datetime.utcnow()` callsites | None (only doc-string mentions warning against it) |
| Direct cross-module imports between bookings/schedule/pt_packages/pt_sessions services | None (Protocol slots used; raw `sa.text()` with TABLE_REF noqa for cross-module SQL per D-38-11) |
| Console/log-only stub bodies | None |

### Requirements Coverage (25 IDs)

| REQ-ID | Status | Notes |
|--------|--------|-------|
| SLOT-01 | SATISFIED | 0016 migration; table + 2 indexes + status CHECK + end>start CHECK |
| SLOT-02 | **PARTIAL** | POST/GET/GET endpoints VERIFIED; **PATCH cancel** ships as POST — see Gap #1 |
| SLOT-03 | SATISFIED | Overlap rejection via tstzrange query (find_overlapping_slots_for_update) → 409 slot_overlap |
| SLOT-04 | SATISFIED | 10-min buffer via SLOT_BUFFER_MINUTES + find_buffer_violations → 409 slot_too_close |
| SLOT-05 | SATISFIED | Future-only guard with datetime.now(UTC) → 409 slot_in_past |
| SLOT-06 | SATISFIED | Idempotency-Key + two-phase Redis claim+replay on POST publish |
| SLOT-07 | **PARTIAL** | Atomic booked→cancelled cascade VERIFIED; verb is POST not PATCH — see Gap #1 |
| SLOT-08 | SATISFIED | GET list+detail paginated `{items, total, page, pageSize}`; filter set per spec; default Moscow 14d window |
| SLOT-09 | SATISFIED | slot_published + slot_cancelled audit emits (5-key payloads); had_booking discriminator on cancelled |
| BOOK-01 | SATISFIED | 0017 migration; named partial UNIQUE; 4-state CHECK; ON DELETE RESTRICT FKs |
| BOOK-02 | SATISFIED | 10-step create_booking UoW; Idempotency-Key required |
| BOOK-03 | SATISFIED | DB partial UNIQUE + IntegrityError discriminator → 409 slot_already_booked (race-loser path) |
| BOOK-04 | SATISFIED | Moscow-TZ validity-window guard (D-38-12); end_date < slot.start_time.astimezone(MOSCOW_TZ).date() → 409 |
| BOOK-05 | SATISFIED | sessions_remaining ≤ 0 → 409 pt_package_exhausted |
| BOOK-06 | SATISFIED | POST /bookings/{id}/cancel (matches BOOK-06 wire spec); reception 24h vs owner-anytime gated against slot.start_time per D-38-16 |
| BOOK-07 | SATISFIED | GET /bookings with paginated envelope + filter set (client_id/trainer_id/from_time/to_time/status); Moscow ±30d default |
| BOOK-08 | **PARTIAL** | Logic + filters VERIFIED; **URL is /bookings/clients/{client_id}/bookings not /clients/{id}/bookings** — see Gap #2 |
| BOOK-09 | SATISFIED | GET /bookings/{id} returns BookingDetailResponse with joinedload (N+1 prevention per Pitfall 19 / D-38-08) |
| BOOK-10 | SATISFIED | Partial UNIQUE + constraint-name discriminator + race test passes |
| PKG-01 | SATISFIED | 0018 migration adds nullable trainer_id FK |
| PKG-02 | SATISFIED | TrainerMismatchError raised when pt_package.trainer_id != slot.trainer_id (bookings/service.py:368) |
| PKG-03 | SATISFIED | OutstandingBookingsExistError 409 in pt_packages/service.py:955 (refund flow) |
| PKG-04 | SATISFIED | 0019 migration; record_pt_session accepts + persists booking_id |
| PKG-05 | SATISFIED | Booking confirmed→completed via Protocol slot inside record_pt_session UoW; SELECT FOR UPDATE pre-check (D-38-19) |
| PKG-06 | SATISFIED | FSM `completed → ∅` (no revert path) encoded in BOOKING_STATUS_TRANSITIONS; cancel-session keeps booking 'completed' (D-38-13) |

**Summary: 22 SATISFIED, 3 PARTIAL (SLOT-02, SLOT-07, BOOK-08 — URL/verb deviations only; underlying behaviour fully implemented).**

### Phase 38 Surface Integrity (no Phase 37 stubs remain)

| Phase 37 Stub | Phase 38 Replacement | Status |
|---------------|---------------------|--------|
| schedule.service.resolve_slot_by_id (`return None`) | Real repository delegate (schedule/service.py:169-184) | REPLACED |
| schedule.service.restore_slot_to_active (no-op stub) | Predicate-gated raw UPDATE (schedule/service.py:187-218) | REPLACED |
| bookings.service.complete_booking (no-op stub) | Predicate-gated raw UPDATE inside caller's UoW (bookings/service.py:240-277) | REPLACED |

All Protocol-slot stubs from Phase 37 have been replaced with production bodies.

---

## Gaps Summary

The phase's **behavioural** goal is fully achieved — 1247 tests pass, all 25 requirement IDs have working implementations, race-safety is DB-enforced, audit events fire, modules-independent contract holds, the migration chain links cleanly, and B-10 regression is green.

The **two gaps are both URL/verb contract deviations** between the implementation and the locked REQUIREMENTS / ROADMAP wording:

1. **Slot cancel HTTP verb**: spec says PATCH, code ships POST. Plan 38-01 itself spec'd PATCH (line 205), but the executor's actual file uses POST. 38-PATTERNS.md (l.592) also records POST, so the inconsistency was baked into the patterns reference during plan-phase. No D-38-XX deliberately overrides REQUIREMENTS / SC; this is an undocumented deviation.

2. **Per-client bookings URL**: spec says `/clients/{id}/bookings`, code ships `/bookings/clients/{client_id}/bookings`. Plan 38-03 locked this mount point to keep `clients/` a dependency-leaf module (legitimate architectural reasoning), but the URL change was not surfaced as a contract amendment in REQUIREMENTS / ROADMAP / 38-CONTEXT.md.

Both gaps will collide with **Phase 40 HANDOFF-01** (byte-stable OpenAPI regen) — the artifact published in v1.5 will not match the REQUIREMENTS-locked path/verb wording unless one of the two resolutions in each gap is applied before the milestone closes.

**Recommendation:** Surface to the developer for arbitration. Either:
- (a) Fix the implementation to PATCH + move the route to `/clients/{client_id}/bookings`, OR
- (b) Amend REQUIREMENTS (SLOT-02, SLOT-07, BOOK-08) + ROADMAP (SC #2, SC #5) to record the locked-as-shipped contract, with explicit D-38-XX entries in 38-CONTEXT.md.

Either resolution must land before Phase 40 HANDOFF-01 runs.

---

_Verified: 2026-05-17_
_Verifier: Claude (gsd-verifier)_
