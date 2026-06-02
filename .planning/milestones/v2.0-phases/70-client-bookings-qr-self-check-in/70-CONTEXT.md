# Phase 70: Client Bookings + QR Self Check-In - Context

**Gathered:** 2026-05-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Three client-facing capabilities on top of the Phase 68–69 client foundation, all consuming **machinery that already exists** (booking partial-UNIQUE arbiter, booking FSM + cancel window, `_create_visit_with_anti_fraud()`, client JWT signing). The work is **exposing and binding** that machinery safely under `ClientPrincipal`, not reinventing it.

1. **Client self-booking** (CBOOK-01..04) — a client browses available trainer slots and self-books one against their **active PT-package**. Race-safe (existing `uq_bookings_slot_confirmed` partial-UNIQUE → 409 on the loser) and idempotent. A client with no active PT-package is steered to Plans/Checkout.
2. **Booking cancellation** (CBOOK-05) — a client cancels their own confirmed booking within a policy window; cancelling another client's booking 404-collapses (anti-oracle, D-20-IDOR).
3. **QR self check-in** (CCHK-01..03) — a client gets a short-lived (~60s) **signed JWT** QR token; scanning it creates a visit through the existing `_create_visit_with_anti_fraud()` path, recording `visits.channel = 'client_qr'` (Alembic migration extends the CHECK constraint). Expired-token replay is rejected and cross-client check-in is structurally impossible.

**In scope:** CBOOK-01..05, CCHK-01..03. Client booking write + cancel + available-slot read; QR token issuance + token-bound scan/check-in; the `visits.channel` Alembic migration.

**Out of scope:**
- Client checkout / ЮKassa (CPAY) and full PWA screen wiring (PWA-05) → **Phase 71** (note: Phase 71's 71-06 plan *consumes* this phase's Book/QR endpoints).
- PT-session recording / completion flow and PT-credit consumption — bookings do **not** consume PT-package credits (credit is consumed only at `pt_sessions.record_pt_session`, D-38-13); unchanged here.
- Staff-side booking/visit endpoints (frozen staff contract, byte-identical).
- `Client-Portal` OpenAPI tag freeze, `_v20Checks` guards, CI gates, live E2E → **Phase 72**.
- PWA screen wiring for Book/QR — this phase delivers the **backend endpoints**; the screens are wired in 71-06.

</domain>

<decisions>
## Implementation Decisions

### Booking Write Path (CBOOK-01..04)
- **D-70-01:** **Extract the actor-agnostic core of `create_booking()`.** Pull the shared orchestration (slot resolve + raw `active→booked` UPDATE, PT-package active/not-exhausted/not-expired + trainer-match validation, INSERT, `uq_bookings_slot_confirmed` IntegrityError → 409 translation, audit emit, commit) into a helper that BOTH the staff `bookings` service AND a new `client_portal` checkout-style write-slot call — actor identity parameterized. `client_portal` invokes it via a **composition-root Protocol slot** (D-20-MODULE; zero new `ignore_imports`), passing `created_by_user_id = NULL` (column already nullable, self-service precedent D-40-05) and the `ClientPrincipal` (client_id) as the audit actor. Keeps the staff path byte-identical (`contract-freeze-v1.11.0` / drift gate green), no logic duplication. **Directly mirrors Phase 71's D-71-01** `_sell_subject` extraction. Reference body: `apps/backend/app/modules/bookings/service.py:510-859` (`create_booking`).
- **D-70-02:** **Client-supplied `Idempotency-Key` header.** The PWA generates a UUID per booking *intent*, reuses it only on retry; same key replays the same booking. Mirrors the existing staff `POST /bookings` Idempotency-Key handling and Phase 71's PT-package key approach (D-71-04). A genuinely new attempt on an already-confirmed slot still hits the `uq_bookings_slot_confirmed` 409 (`slot_already_booked`).
- **D-70-03:** **No-active-PT-package → 422 + typed code.** Return HTTP **422** with a machine-matchable code (e.g. `no_active_pt_package`) so the PWA routes the client to Plans/Checkout (CBOOK-04 — "not a cryptic error"). Mirrors Phase 71's `client_email_required_for_online_payment` 422 gate. Distinct from the 409 `slot_already_booked` race conflict — precondition-missing ≠ race-lost.
- **D-70-04:** **Available-slots read pre-filtered to bookable slots (CBOOK-02).** A client-scoped read (e.g. `GET /client/slots`) returns only `'active'` future slots the client could actually book: if their active PT-package pins a trainer, only that trainer's slots; otherwise all active trainers' slots. **Client-safe projection** (trainer name/specialization, start/end times) per the D-69-05 catalog-projection discipline — no owner-only economics. Reduces dead-end booking attempts. Reuses `create_booking()`'s trainer-match rule as the filter predicate.

### Booking Cancellation (CBOOK-05)
- **D-70-05:** **New `CANCEL_WINDOW_HOURS_CLIENT` constant, default 24h, measured against `slot.start_time`** (D-38-16). Existing `CANCEL_WINDOW_HOURS_RECEPTION = 24` is reception-only (owner = anytime); the client gets its own explicit, independently-tunable constant (starts identical for predictable behavior). Inside the window → reject with a typed code (mirror `cancel_window_expired`). Cancelling another client's booking 404-collapses (D-20-IDOR anti-oracle).
- **D-70-06:** **No PT-credit action on cancel — slot restore only.** Verified against code: a confirmed booking does **not** consume a PT-package session credit (`sessions_remaining` is decremented only at `pt_sessions.record_pt_session`, `pt_sessions/repository.py:62`; `cancel_booking()` only calls `restore_booking_slot()` and never touches `sessions_remaining`). Client cancel reuses the existing `cancel_booking()` slot-restore behavior verbatim (`booked→active`); the active PT-package is simply free to book again. The wr-06 / Phase 999.1 "restore PT session credit on owner force cancel" work is a **different flow** (cancelling a recorded PT-session), not booking cancel.

### QR Token Design (CCHK-01, CCHK-03)
- **D-70-07:** **Stateless ~60s signed JWT; TTL + daily-UNIQUE as the replay guard.** Mint a short-lived JWT (claims: `sub = client_id`, `exp`/`iat`, plus the discriminators below) mirroring the `encode_client_token`/`decode_client_token` HS256 structure (`apps/backend/app/core/security.py:300-379`) with a new `settings.qr_token_ttl_seconds ≈ 60`. **No Redis/jti store** — expired tokens are rejected by `exp`, and a *successful* same-day double check-in is blocked by the existing unconditional `uq_visits_client_id_gym_date` UNIQUE (a replay within the window collapses to `duplicate_checkin` via the anti-fraud chain). Stateless, leans on existing guards.
- **D-70-08:** **Distinct `typ` + `aud` — non-interchangeable with access/refresh tokens.** QR token uses `typ='qr_checkin'` and a distinct `aud='qr'`; a dedicated `decode_qr_token()` asserts both. A leaked QR token cannot authenticate `require_client()` API calls, and an access/refresh token presented at the scan endpoint is rejected. Mirrors the Phase 68 `aud`/`typ` isolation discipline (staff vs client).

### QR Issuance + Scan (CCHK-01, CCHK-02, CCHK-03)
- **D-70-09:** **Issue freely, gate at scan.** `GET /client/qr-token` (behind `require_client()`) mints a fresh ~60s token on demand with **no membership pre-check**. All gating (gym-hours → active-membership → 1/day-per-`gym_date`) stays in `_create_visit_with_anti_fraud()` at scan time — single source of truth, no duplicated rules. The PWA QR screen refreshes the token as it nears expiry.
- **D-70-10:** **Token-bound scan: `client_id` derived strictly from the verified `sub` claim.** The scan/check-in endpoint takes `client_id` **only** from the QR token's verified `sub` — never from a request body, path param, or the scanner's identity. Whoever scans, the visit is created for the token's owner against THEIR membership; there is no parameter to target another client, making cross-client check-in structurally impossible (success criterion #5).
- **D-70-11:** **Token-as-credential scan endpoint, `checked_in_by = NULL`.** A new `POST` under `/api/v1/client` (e.g. `/client/check-in`) is **NOT** behind `require_client()` — the signed QR token is itself the credential (the caller is a gym scanner/turnstile, not the client's logged-in session). The endpoint validates the token (signature/`exp`/`aud`/`typ`), then calls `_create_visit_with_anti_fraud()` with `channel='client_qr'`, `checked_in_by=NULL` (self-service, mirroring the `telegram_bot` path), and `client_id` from `sub`. An **Alembic migration** extends the `ck_visits_channel` CHECK constraint to include `'client_qr'`.

### Claude's Discretion (planner/researcher decides)
- Whether `audit.emit(...)` already supports a client-as-actor or needs a small client-aware actor field for the booking/visit audit events (same open question as Phase 71's D-71-02 — investigate `app/core/audit.py`). Do NOT invent a fake staff user.
- Exact endpoint paths/operationIds within `client_portal` (booking POST, cancel, slots read, qr-token, check-in) and where the extracted booking core lives (helper module vs in-place refactor of `bookings/service.py`), consistent with D-20-MODULE Protocol-slot writes and the `client_` operationId prefix.
- Available-slots query filter granularity, pagination shape (`{items,total,page,pageSize}`), and ordering (likely `start_time ASC`).
- QR token refresh cadence in the PWA and the QR-screen UX (these are consumed/wired in Phase 71's 71-06; backend just needs the issue endpoint).
- Rate-limiting / abuse controls on the unauthenticated scan endpoint (`/client/check-in`) and the qr-token issuance endpoint.
- Whether the no-active-PT-package 422 and cancel-window-expired errors reuse existing `DomainError` envelope shapes or add new codes — must be machine-matchable for the PWA.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap
- `.planning/ROADMAP.md` § Phase 70 — goal + 5 success criteria (verification anchor: #1 concurrent-booking 409 via partial-UNIQUE, #2 no-PT-package → Plans/Checkout, #3 cancel-window + 404 anti-oracle, #4 ~60s signed QR → `_create_visit_with_anti_fraud()` + `channel='client_qr'` migration, #5 expired-replay rejected + cross-client impossible).
- `.planning/REQUIREMENTS.md` — CBOOK-01..05, CCHK-01..03 (locked requirement IDs for this phase).
- `.planning/phases/69-client-read-endpoints-pwa-stack-alignment/69-CONTEXT.md` — the client read-surface foundation (`require_client()` reads, client-safe projections D-69-05, `client_scoped_bookings_router` upcoming-bookings query the Book screen reuses, `GET /client/bookings?upcoming=1`).
- `.planning/phases/68-client-auth-foundation/68-CONTEXT.md` — `ClientPrincipal`, `require_client()`, `cc_client_*` cookies, `aud:"client"`/`typ` token isolation, `/api/v1/client` mount.
- `.planning/phases/71-client-checkout-full-pwa-screen-wiring/71-CONTEXT.md` — **downstream consumer**: 71-06 wires the Book/QR screens to this phase's endpoints; D-71-01 (actor-agnostic core extraction) is the direct precedent for D-70-01.

### v2.0 locked decisions (carry-forward — DO NOT re-litigate)
- **D-20-IDOR** — every owned endpoint (booking cancel, any get-by-id): mandatory `client_id` param + `assert_owns()` → 404-collapse (anti-oracle); parametrized IDOR sweep covers bookings.
- **D-20-MODULE** — `app/modules/client_portal/` aggregator; raw-SQL cross-module reads; **Protocol-slot writes** (the client booking write-slot delegates into the extracted `bookings` core); zero new `ignore_imports`.
- **D-20-OPENAPI** — single `openapi.json` extended additively: `Client-Portal` tag + `client_` operationId prefix; staff paths byte-identical to `contract-freeze-v1.11.0`.
- **D-38-16** — cancellation window measured against `slot.start_time`, not `created_at`.
- **D-38-13 / D-40-05** — booking credit consumed at PT-session recording (not booking); `created_by_user_id` nullable for self-service.

### Existing backend code to reuse / extract (full paths)
- `apps/backend/app/modules/bookings/service.py` (L510-859 `create_booking`; L1264-1404 `cancel_booking`; L271-282 `_is_slot_confirmed_conflict` constraint discriminator) — booking core to extract per D-70-01; cancel path to reuse per D-70-05/06.
- `apps/backend/app/modules/bookings/models.py` (L50-172) — `Booking`: `slot_id`, `client_id`, `pt_package_id`, `status`, `created_by_user_id` **nullable**; the `uq_bookings_slot_confirmed` partial-UNIQUE.
- `apps/backend/alembic/versions/0017_bookings.py` (L130-136) — `op.create_index("uq_bookings_slot_confirmed", "bookings", ["slot_id"], unique=True, postgresql_where=text("status = 'confirmed'"))` — the race-safe arbiter (criterion #1).
- `apps/backend/app/modules/bookings/constants.py` (L26-33 FSM `confirmed→{cancelled,no_show,completed}`; L41 `CANCEL_WINDOW_HOURS_RECEPTION=24`) — add `CANCEL_WINDOW_HOURS_CLIENT` here per D-70-05.
- `apps/backend/app/modules/visits/service.py` (L106-212 `_create_visit_with_anti_fraud()`; L66-77 `_is_duplicate_visit_conflict`; public wrappers `create_visit_reception` / `create_visit_self_checkin`) — the anti-fraud path the scan endpoint calls with `channel='client_qr'`, `checked_in_by=None`.
- `apps/backend/app/modules/visits/models.py` (L85 `channel String(16)`; L97-101 `ck_visits_channel` CHECK `IN ('reception','telegram_bot')`; L102-107 `uq_visits_client_id_gym_date`) — the CHECK to extend with `'client_qr'` (Alembic) + the daily-UNIQUE replay guard.
- `apps/backend/alembic/versions/0006_visits.py` (L101-108) — original `channel` CHECK + visits UNIQUE migration; the new migration mirrors this to add `'client_qr'`.
- `apps/backend/app/core/security.py` (L300-379 `ClientAccessTokenClaims` / `encode_client_token` / `decode_client_token`, HS256, `settings.secret_key`, `settings.jwt_clock_leeway_seconds`) — mirror for `encode_qr_token`/`decode_qr_token` (D-70-07/08); also L185-196 short-token helpers for reference.
- `apps/backend/app/core/dependencies.py` (L147-198 `get_active_pt_package()` Protocol resolver + `ActivePtPackage` Protocol; `require_client()` + `ClientPrincipal`) — active-PT-package gate for booking (D-70-03) and auth gate for `GET /client/qr-token` (D-70-09).
- `apps/backend/app/modules/client_portal/` (`router.py` / `service.py` / `repository.py` / `schemas.py`) — Phase-69 module; new booking write-slot, cancel, slots read, qr-token issue, and check-in endpoints slot in here.
- `apps/backend/app/api/v1/router.py` (L101-103 `v1.include_router(client_portal_router, prefix="/client")`) — mount point for the new endpoints (booking/cancel/slots/qr-token behind `require_client()`; `/client/check-in` token-as-credential, NOT behind `require_client()` per D-70-11).
- `apps/backend/app/modules/pt_sessions/repository.py` (L62 `sessions_remaining - 1`; L281 `+ 1`) — **evidence** that credit is consumed/restored at PT-session level, not booking (basis for D-70-06).
- `apps/backend/tests/conftest.py` (L58-106 SAVEPOINT `db_session`; L109-140 `async_client` over ASGITransport) + `apps/backend/tests/integration/bookings/test_booking_race.py` (L54-101 `db_session_real_commit` + 2-parallel-POST → [201,409] `slot_already_booked` race pattern) — the harness for the concurrency (criterion #1) and IDOR (criterion #3) tests; the QR replay/cross-client tests (criterion #5) follow the same patterns.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`create_booking()` core** — already does slot-lock, PT-package validation (active/not-exhausted/not-expired/trainer-match), partial-UNIQUE 409 translation, and audit. CBOOK-01/03 are ~90% solved server-side; the work is exposing it under `ClientPrincipal` via the extracted core (D-70-01), not reimplementing.
- **`cancel_booking()`** — already does FSM guard (`confirmed→cancelled`), window check, slot restore, and audit. Client cancel reuses it with a client window constant (D-70-05); no credit logic needed (D-70-06).
- **`_create_visit_with_anti_fraud()`** — already enforces gym-hours → active-membership → 1/day-per-`gym_date` and is the single source of truth for check-in gating; the QR scan endpoint just supplies `channel='client_qr'` + `client_id` from the token (D-70-09/11). The existing `create_visit_self_checkin` (channel=`telegram_bot`, `checked_in_by=None`) is the direct shape precedent.
- **`encode_client_token`/`decode_client_token`** — HS256 + `aud`/`typ` discriminator pattern to mirror for the 60s QR token (D-70-07/08).
- **`get_active_pt_package()` Protocol resolver** — booking's active-PT-package gate; also drives the available-slots trainer filter (D-70-04) and the CBOOK-04 422 (D-70-03).
- **`client_portal` module + `/api/v1/client` mount** — router/service/repository scaffolding from Phase 69; new write/read endpoints slot in alongside.
- **SAVEPOINT + `db_session_real_commit` race harness** — directly supports the criterion #1 concurrency test and the criterion #5 QR replay/cross-client tests.

### Established Patterns
- **Protocol-slot writes (D-20-MODULE)** — `client_portal` must not import `bookings`/`visits` internals directly; the extracted booking core and the anti-fraud path are invoked via composition-root Protocol slots. Zero new `ignore_imports`.
- **`aud`/`typ` token isolation (Phase 68)** — staff vs client tokens already separated; the QR token extends this with `aud='qr'`/`typ='qr_checkin'` (D-70-08).
- **Anti-oracle 404-collapse (D-20-IDOR)** — booking cancel on a non-owned booking returns 404, never reveals existence.
- **Self-service nullable attribution (D-40-05)** — `created_by_user_id=NULL` (booking) and `checked_in_by=NULL` (visit) for client-initiated actions; audit records the client as actor.
- **Constraint-name IntegrityError discrimination** — `_is_slot_confirmed_conflict` / `_is_duplicate_visit_conflict` match on literal constraint names; the new channel migration keeps `ck_visits_channel` discoverable.

### Integration Points
- New client booking/cancel/slots/qr-token routes mount under `/api/v1/client` (behind `require_client()`); the `/client/check-in` scan route mounts there too but is token-as-credential (not `require_client()`-gated).
- The extracted booking core is shared by the staff `bookings` service (byte-identical staff contract) and the new client write-slot.
- Alembic migration extends `ck_visits_channel` to `('reception','telegram_bot','client_qr')`.
- `schema.d.ts` regen picks up the new client paths (additive; formal `_v20Checks`/freeze is Phase 72).
- Phase 71's 71-06 plan wires the PWA Book/QR screens to these endpoints — keep response shapes PWA-friendly.

</code_context>

<specifics>
## Specific Ideas

- QR token TTL ≈ 60s; the PWA QR screen refreshes the token client-side as it nears expiry.
- Scan endpoint is the gym-side credential check: `client_id` comes only from the verified token `sub` — there is deliberately no body/path param to target a client.
- No-active-PT-package booking response carries a machine code (`no_active_pt_package`) so the PWA redirects to Plans/Checkout rather than showing a raw error.
- Client cancel window starts at 24h (identical to reception) but is a separate `CANCEL_WINDOW_HOURS_CLIENT` constant so it can diverge later without touching staff policy.
- `client_qr` is added to the existing `ck_visits_channel` CHECK constraint, not a new column — the `channel` column already exists as `String(16)`.

</specifics>

<deferred>
## Deferred Ideas

- **PWA Book/QR screen wiring** — Phase 71 (71-06) consumes these endpoints; backend-only here.
- **Client checkout / ЮKassa (CPAY)** — Phase 71.
- **`Client-Portal` tag freeze, `_v20Checks` guards, client-pwa CI gates, live E2E runbook** — Phase 72.
- **jti/Redis single-use QR tokens** — considered and rejected for this phase (D-70-07: TTL + daily-UNIQUE suffice); revisit only if a stricter one-shot guarantee is ever required.
- **Membership pre-check on QR issuance** — considered and rejected (D-70-09: anti-fraud at scan is the single source of truth); could add for UX later if desired.
- **PT-session recording / credit-consumption flow** — separate from booking; unchanged here. wr-06 (Phase 999.1) handles PT-session credit restore.

None of the discussion strayed outside phase scope beyond the above noted-for-later items.

</deferred>

---

*Phase: 70-client-bookings-qr-self-check-in*
*Context gathered: 2026-05-30*
