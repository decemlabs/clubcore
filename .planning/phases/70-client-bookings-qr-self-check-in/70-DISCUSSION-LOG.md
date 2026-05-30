# Phase 70: Client Bookings + QR Self Check-In - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-30
**Phase:** 70-client-bookings-qr-self-check-in
**Areas discussed:** Booking write reuse, Cancel window + credit, QR token + replay, QR scan endpoint

---

## Booking write reuse

### Q1 — How should client_portal create a booking?
| Option | Description | Selected |
|--------|-------------|----------|
| Extract actor-agnostic core | Pull create_booking() body into a helper; client_portal calls via Protocol slot, created_by_user_id=NULL, ClientPrincipal audit actor (mirrors D-71-01) | ✓ |
| Thin client write path | Parallel slim write reusing repo + arbiter, re-implements orchestration | |
| You decide | Planner chooses based on factoring | |

**User's choice:** Extract actor-agnostic core (→ D-70-01)

### Q2 — Booking idempotency strategy?
| Option | Description | Selected |
|--------|-------------|----------|
| Client-supplied Idempotency-Key | PWA generates UUID per intent, reused on retry; mirrors staff POST /bookings | ✓ |
| Server-derived deterministic key | Derive from (client_id, slot_id) | |
| You decide | Planner picks | |

**User's choice:** Client-supplied Idempotency-Key (→ D-70-02)

### Q3 — CBOOK-04 no-active-PT-package response shape?
| Option | Description | Selected |
|--------|-------------|----------|
| 422 + machine code | Typed code (no_active_pt_package); PWA routes to Plans/Checkout (mirrors Phase 71 422 gate) | ✓ |
| 409 conflict code | Group with slot-already-booked conflicts | |
| You decide | Planner picks status/code | |

**User's choice:** 422 + machine code (→ D-70-03)

### Q4 — CBOOK-02 available-slots behavior?
| Option | Description | Selected |
|--------|-------------|----------|
| Pre-filter to bookable slots | Only active future slots; trainer-pinned package → only that trainer; client-safe projection (D-69-05) | ✓ |
| Show all, validate on book | List all, reject mismatch at POST | |
| You decide | Planner decides filter granularity | |

**User's choice:** Pre-filter to bookable slots (→ D-70-04)

---

## Cancel window + credit

### Q1 — Client cancellation window?
| Option | Description | Selected |
|--------|-------------|----------|
| New client window (24h) | Add CANCEL_WINDOW_HOURS_CLIENT=24h, vs slot.start_time; independently tunable | ✓ |
| Reuse reception 24h constant | Couple client policy to staff constant | |
| You decide | Planner picks structure | |

**User's choice:** New client window, 24h default (→ D-70-05)

### Q2 — PT-package credit on cancel? (corrected after code verification)
| Option | Description | Selected |
|--------|-------------|----------|
| Restore credit on cancel | (Initial framing) restore session credit | (superseded) |
| Forfeit credit | Lose session even within window | |

**User's choice (initial):** Restore credit on cancel — **but the premise was wrong.**
**Correction:** Code verification (`pt_sessions/repository.py:62`, `bookings/service.py` cancel path) showed bookings do NOT consume a PT-package credit; credit is consumed only at PT-session recording (D-38-13). `cancel_booking()` only restores the slot. Re-asked:

| Option | Description | Selected |
|--------|-------------|----------|
| No credit action — slot only | Reuse cancel_booking() verbatim; no sessions_remaining change | ✓ |
| Re-examine the credit model | Treat booking as reserving a credit (a model change) | |

**User's choice (corrected):** No credit action — slot only (→ D-70-06)
**Notes:** wr-06 / Phase 999.1 ("restore PT session credit on owner force cancel") is a different flow (PT-session cancel), not booking cancel.

---

## QR token + replay

### Q1 — Anti-replay mechanism within the 60s TTL?
| Option | Description | Selected |
|--------|-------------|----------|
| TTL-only (stateless) | 60s JWT; daily uq_visits_client_id_gym_date + anti-fraud as replay guard; no Redis | ✓ |
| Single-use jti + Redis | Burn jti on first scan (SETNX, 60s) | |
| You decide | Planner picks | |

**User's choice:** TTL-only stateless (→ D-70-07)

### Q2 — QR token distinguishability from access token?
| Option | Description | Selected |
|--------|-------------|----------|
| Distinct typ + aud | typ='qr_checkin', aud='qr'; decode_qr_token() asserts both; non-interchangeable | ✓ |
| Reuse access token shape | Same aud/typ, rely on TTL | |
| You decide | Planner designs claim set | |

**User's choice:** Distinct typ + aud (→ D-70-08)

### Q3 — QR issuance + membership pre-check?
| Option | Description | Selected |
|--------|-------------|----------|
| Issue freely, gate at scan | GET /client/qr-token mints freely; anti-fraud authoritative at scan | ✓ |
| Pre-check membership on issue | 422 no_active_membership on issue | |
| You decide | Planner picks | |

**User's choice:** Issue freely, gate at scan (→ D-70-09)

---

## QR scan endpoint

### Q1 — Scan caller + client binding?
| Option | Description | Selected |
|--------|-------------|----------|
| Token-bound, client_id from token | client_id strictly from verified sub; no param to target another client → cross-client impossible | ✓ |
| Staff-device authenticated | Require staff principal + token | |
| You decide | Planner designs endpoint | |

**User's choice:** Token-bound, client_id from token (→ D-70-10)

### Q2 — Scan endpoint gate + checked_in_by?
| Option | Description | Selected |
|--------|-------------|----------|
| Token-as-credential, checked_in_by=NULL | NOT behind require_client(); token is the credential; channel='client_qr', checked_in_by=NULL; POST /client/check-in | ✓ |
| Behind require_client() | Require a client session too | |
| You decide | Planner picks gate + checked_in_by | |

**User's choice:** Token-as-credential, checked_in_by=NULL (→ D-70-11)

---

## Claude's Discretion

- audit.emit client-as-actor field (shared open question with Phase 71 D-71-02).
- Exact endpoint paths/operationIds and placement of the extracted booking core.
- Available-slots query filter granularity, pagination, ordering.
- QR refresh cadence + QR-screen UX (wired in Phase 71 71-06).
- Rate-limiting on the unauthenticated scan endpoint and qr-token issuance.
- Reuse vs new DomainError codes for the 422 / cancel-window errors.

## Deferred Ideas

- PWA Book/QR screen wiring → Phase 71 (71-06).
- Client checkout / ЮKassa (CPAY) → Phase 71.
- Client-Portal tag freeze, _v20Checks, CI gates, live E2E → Phase 72.
- jti/Redis single-use QR tokens — considered, rejected (TTL + daily-UNIQUE suffice).
- Membership pre-check on QR issuance — considered, rejected (anti-fraud authoritative).
- PT-session recording / credit-consumption flow — separate; wr-06 (Phase 999.1).
