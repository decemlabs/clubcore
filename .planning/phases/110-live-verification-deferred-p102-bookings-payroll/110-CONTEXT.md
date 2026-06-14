# Phase 110: Live Verification — Deferred P102 (Bookings + Payroll) - Context

**Gathered:** 2026-06-14
**Status:** Ready for planning
**Mode:** Smart discuss (autonomous)

<domain>
## Phase Boundary

The P102 booking lifecycle and trainer payroll that were `data-setup-blocked` at v3.0 close are verified working live against the running stack on seeded data, and the seed path is captured so the walkthrough is repeatable.

Two requirements: VER-01 (booking lifecycle create → cancel → complete-via-pt-session, + race conflict) and VER-02 (trainer payroll comp-config → accrual preview → run → pending→paid, + reception RBAC gating).

**In scope:** a committed repeatable seed for the P102 walkthrough; end-to-end verification (integration tests on real seeded Postgres) of both lifecycles; a captured runnable walkthrough; small inline fixes if a flow is found broken.

**Out of scope (deferred):** browser/visual UAT of the admin-app schedule/payroll screens (deferred as UAT); large/architectural fixes if verification uncovers them (escalate, don't silently expand scope); the literal real-uvicorn-HTTP confirmation if it can't be run headlessly (capture the script + defer).

**Key fact established at discuss:** the payroll router IS mounted (`apps/backend/app/api/v1/router.py:61`, `prefix="/payroll"`) — an earlier "deferred to Phase 58-10" code comment was stale. Bookings (`/bookings`) and pt-sessions (`/pt-sessions`) are also mounted. All P102 endpoints are reachable; the only true v3.0 blocker was missing seed data.
</domain>

<decisions>
## Implementation Decisions

### Verification approach & artifacts
- **Primary mechanism = end-to-end integration tests** using httpx ASGITransport against the REAL seeded Postgres (localhost:5432) — the project's established "live" boundary (every existing P102 test uses it). Repeatable + CI-able.
- **Committed repeatable seed** — a dedicated seed script (e.g. `scripts/seed_p102_walkthrough.py`) that creates the full prerequisite set: active trainer, published future availability slot, client, active PT-package (trainer-matched, sessions_remaining>0, validity covers the slot), trainer comp-config, and a payment row for revenue. Reuse the patterns from the existing conftest `make_*` fixtures. Idempotent (uuid5/ON CONFLICT) like the existing seed scripts. This satisfies criterion #4 (repeatable, blocker does not recur).
- **Captured live-HTTP walkthrough** — a runnable script/doc (dev-login via `POST /api/v1/auth/login` → create booking → cancel → record pt-session(completes booking) → payroll preview → run accrual → mark-paid), with exact commands. Execute it against a live uvicorn best-effort during execution; if the running-uvicorn smoke can't be completed headlessly, capture the script and defer the literal-HTTP confirmation as a UAT item.
- **Race conflict** — exercise the slot-already-taken path with real-commit transactions (the existing `tests/integration/bookings/test_booking_race.py` / `db_session_real_commit` pattern, Postgres-only) → assert `409 slot_already_booked` (partial UNIQUE `uq_bookings_slot_confirmed`), a clear state, not a crash.

### Coverage & broken-flow policy
- **Booking lifecycle:** create a booking against a seeded slot → cancel it → complete one via `POST /api/v1/pt-sessions` (booking_id link flips status to `completed`). Each transition asserted on real seeded data. Plus the race conflict.
- **Payroll lifecycle:** set comp-config (`PUT /api/v1/payroll/trainer-configs/{trainer_id}`) → preview accrual (`GET /payroll/preview`) → run (`POST /payroll/accruals`) → mark-paid (`POST /payroll/accruals/{id}/mark-paid`, pending→paid). Assert the accrual snapshot (revenue, sessions, commission/fee) and the single pending→paid transition.
- **RBAC negative:** reception receives `403` on the owner-only payroll endpoints (zero owner-only payroll calls succeed). No RBAC parity change expected (compensation/payroll already in OWNER_ONLY).
- **If a flow is found BROKEN:** fix it inline when the fix is small/clear (closing the deferral means making it actually work; v3.1 permits minimal backend changes). Escalate (surface as a blocker/gap) only if the break is large or architectural — do not silently expand scope.

### Claude's Discretion
- Exact seed-script filename/location and whether the live-HTTP smoke runs against a started uvicorn or is captured-and-deferred — plan-phase + execution discretion based on what runs cleanly headlessly.
- Whether the E2E walkthrough lives as new test files under `tests/integration/` (e.g. a `test_p102_live_walkthrough.py`) reusing existing `make_*` conftest fixtures, vs driven by the seed script — plan-phase decides; reuse existing fixtures/exemplars.
- Money in kopecks; all dates/periods Europe/Moscow.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets / Endpoints (all MOUNTED + reachable)
- **Bookings:** `POST /api/v1/bookings` (`bookings/service.py:1190 create_booking`), `POST /api/v1/bookings/{id}/cancel` (`cancel_booking`), complete via pt-sessions (`bookings/service.py:1145 complete_booking`, registered through `register_booking_completer` in `app.main`). Router `bookings/router.py:52`. FSM `bookings/constants.py:26` (`confirmed → {cancelled,no_show,completed}`).
- **Race path:** predicate-gated slot flip + partial UNIQUE `uq_bookings_slot_confirmed(slot_id) WHERE status='confirmed'` (Alembic 0017); duplicate → `409 slot_already_booked` via `_is_slot_confirmed_conflict()` (`bookings/service.py:528`). Idempotency-Key required on create.
- **PT-sessions:** `POST /api/v1/pt-sessions` (`pt_sessions/service.py:207 record_pt_session`); `booking_id` param → `complete_booking_by_pt_session` (`pt_sessions/service.py:338`) flips the booking to completed in the same UoW.
- **Payroll (MOUNTED):** `PUT /api/v1/payroll/trainer-configs/{trainer_id}` (set_comp_config), `GET /payroll/trainer-configs/{trainer_id}` (get), `GET /payroll/preview` (preview_accrual), `POST /payroll/accruals` (run_payroll_period), `POST /payroll/accruals/{id}/mark-paid` (mark_accrual_paid), `GET /payroll/accruals` (list). Service `payroll/service.py:103/149/224/254/~350`. RBAC: all `(Action.*, Resource.COMPENSATION|PAYROLL) ∈ OWNER_ONLY` → reception 403. Computation single-source `compute_accrual_components()` (`payroll/service.py:166`). Snapshot discipline D-58-03; duplicate-period guard `uq_trainer_payroll_accruals_period_alive` (Alembic 0041) → `409 payroll_period_already_run`. Accrual FSM pending→paid (terminal).
- **Payroll accrual data prerequisites:** trainer + comp-config (commission_pct_bps OR session_fee_kopecks, effective_from ≤ period_end) + completed PT-sessions in period + a `Payment(subject_kind='pt_package', subject_id=pt_package.id, amount_kopecks=...)` for revenue (cross-module raw-SQL read in `payroll/repository.py`).

### Established Patterns / Exemplars to copy
- Booking create E2E: `tests/integration/bookings/test_bookings_create.py:42`. Cancel: `test_bookings_cancel.py`. Race: `test_booking_race.py` (uses `db_session_real_commit`, Postgres-only, parallel asyncio tasks).
- Payroll run/mark-paid: `tests/integration/payroll/test_payroll_accruals.py` (`_seed_pt_data()` helper). Preview: `test_payroll_preview.py`. Comp-config + reception 403: `test_payroll_comp_config.py`.
- Conftest fixtures: `tests/integration/bookings/conftest.py:246` (`make_trainer`, `make_client`, `make_pt_package_plan`, `make_pt_package`, `make_slot`); `tests/integration/payroll/conftest.py:110` (`make_comp_config`, `make_accrual`). Auth helpers `conftest.py:131 _seed_user`, `:150 _login` (POST /auth/login → `cc_access`+`clubcore_csrf` cookies; CSRF header `X-CSRF-Token`).
- Seed scripts: `scripts/seed_demo_data.py` (owner + 1 membership plan + 1 pt-package plan; runnable `uv run python -m scripts.seed_demo_data`, needs SEED_OWNER_EMAIL/PASSWORD ≥12 chars; idempotent). `scripts/seed_verification_fixtures.py` (uuid5-deterministic clients/memberships/operators). **Neither seeds trainers, slots, client PT-packages, comp-config, pt-sessions, or payments** — that is the gap to fill.

### Integration Points
- Dev stack already running this session: Postgres :5432 (clubcore, app/app, migrations 0001..0071), Redis :6379, S3 :8333. Backend app (uvicorn :8000) NOT currently running.
- Contract additive — if any tiny fix touches a route shape, OpenAPI regen + forward-guard happen in Phase 111. No contract change expected from pure verification.
- VER-01/VER-02 are independent — booking-lifecycle and payroll walkthroughs can be built/verified in parallel; the payroll walkthrough needs completed pt-sessions which the booking-complete path produces (or seed them directly).
</code_context>

<specifics>
## Specific Ideas

- Seed must produce: active trainer; published future availability slot; client; active PT-package (trainer-matched, sessions_remaining>0, validity covering the slot); trainer comp-config; a payment row for payroll revenue; optionally completed pt-sessions in a payroll period.
- Reception 403 must be asserted against the owner-only payroll endpoints.
- Race test must use real transactions (not SAVEPOINT) per the existing pattern.
- Capture the exact seed + walkthrough commands in a committed artifact so the v3.0 data-setup blocker cannot recur.
- Cookie discipline: `cc_access`/`cc_refresh` + `clubcore_csrf` → `X-CSRF-Token`; staff login via `POST /api/v1/auth/login`.
</specifics>

<deferred>
## Deferred Ideas

- Browser/visual UAT of the admin-app schedule + payroll screens (separate from API-level verification) — deferred as UAT.
- Literal real-uvicorn-HTTP confirmation if it cannot be completed headlessly — capture the runnable script + defer the manual confirmation.
- Large/architectural fixes if verification surfaces them — escalate as a blocker/follow-up rather than expanding this phase.
</deferred>
