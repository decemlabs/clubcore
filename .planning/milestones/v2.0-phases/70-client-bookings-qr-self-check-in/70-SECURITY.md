---
phase: 70-client-bookings-qr-self-check-in
security_retro_at: 2026-06-16T00:00:00Z
retro_runner: executor/119-03
source_findings: 70-REVIEW.md (CR-02, IN-01, IN-02 — deferred by 70-REVIEW-FIX.md)
items: 3
items_verified_closed: 0
items_operator_pending: 1
items_still_open: 2
status: partial — 2 items still-open in code, 1 operator-pending
formal_skill_run: pending — /gsd:secure-phase 70 to be run by orchestrator for 70-SECURITY.md update
---

# Phase 70: Security Retro (SEC-06 Preliminary — Inline Verification)

**Retro runner:** Phase 119 plan 03 executor (inline verification per task handling instructions)
**Source:** `70-REVIEW.md` findings CR-02, IN-01, IN-02 (deferred by `70-REVIEW-FIX.md` iteration 1)
**Date:** 2026-06-16
**Note:** This is a PRELIMINARY inline retro. The formal `/gsd:secure-phase 70` skill run
(which would authorise update of this file with full test evidence) is an orchestrator-level
action. Findings below are code-verified (grep/read), not runtime-verified.

---

## Item 1: CR-02 — Proxy rate-limit bucket shared "unknown" key

**Original finding:** `70-REVIEW.md CR-02`
**Disposition in REVIEW-FIX:** Explicitly deferred (not in scope of fix iteration 1).
**Description:** Both `_enforce_qr_token_rate_limit` and `_enforce_check_in_rate_limit` use
`request.client.host if request.client is not None else "unknown"`. When `request.client`
is None (proxy strips peer address), all requests fall into a single shared
`ratelimit:check_in:ip:unknown` bucket — enabling DoS of legitimate clients and a bypass
for scanner farms.

**Current code state (verified 2026-06-16):**
```python
# apps/backend/app/modules/client_portal/router.py:598
ip = request.client.host if request.client is not None else "unknown"
# apps/backend/app/modules/client_portal/router.py:643
ip = request.client.host if request.client is not None else "unknown"
```

**Status: STILL OPEN (code-verified)**

The `"unknown"` fallback is unchanged from the review finding. CR-01 (INCR atomicity fix)
was applied in commit `72bae911`, but CR-02 was not.

**Assessment:** In the v4.0 k3s/Traefik deployment (Phase 119 NET-01), Traefik is configured
as the ingress proxy. Whether `request.client` will be None depends on whether `proxyHeader`
/ `trustedIPs` is configured for the Traefik ingress. With the Phase 119 IngressRoute, the
upstream pod receives the proxied connection — `request.client` should reflect the pod's view
of the connection origin. Until the Traefik proxy trust configuration is verified against the
actual deployment topology, this remains operator-pending (behavior under load or behind
a stripping proxy cannot be proven without live infra).

**Verdict: OPERATOR-PENDING** — Requires live Traefik + k3s deployment to verify proxy
header trust. Fix available in `70-REVIEW.md CR-02` (fail-closed on None peer address).
The fix is safe to apply code-side now; the verification is operator-pending.

---

## Item 2: IN-01 — QR post-decode client existence check

**Original finding:** `70-REVIEW.md IN-01`
**Disposition in REVIEW-FIX:** Explicitly deferred ("optional"; D-70-09 accepted risk).
**Description:** `check_in_via_qr` calls `decode_qr_token(token)` then immediately passes
`client_id` to `create_visit_client_qr` without verifying the client still exists (is active,
not soft-deleted). A soft-deleted client can still check in within the 60s QR TTL.

**Current code state (verified 2026-06-16):**
```python
# apps/backend/app/modules/client_portal/service.py:627-632
claims = decode_qr_token(token)
try:
    client_id = UUID(claims.sub)  # sole authoritative source (D-70-10)
except ValueError as exc:
    raise InvalidSession("invalid_session") from exc
result = await create_visit_client_qr(session, client_id)
```

WR-02 fix (UUID parse error → 401) was applied (commit `97a85992`). No client-alive check exists.

**Status: STILL OPEN (code-verified; accepted risk per D-70-09)**

The review classified this as Info (not Critical/Warning), and the fix was marked optional.
The accepted risk rationale: 60s TTL makes the race extremely tight, and `ON DELETE RESTRICT`
FK prevents hard corruption. The visit for a soft-deleted client is the documented edge case.

**Verdict: STILL OPEN — Accepted risk (D-70-09). Not a regression; documented design decision.
If the gym ops team reports confusion (QR check-in succeeds for deactivated clients), apply
the optional fix from `70-REVIEW.md IN-01`.**

---

## Item 3: IN-02 — Cancel endpoint idempotency

**Original finding:** `70-REVIEW.md IN-02`
**Disposition in REVIEW-FIX:** Explicitly deferred ("by design per D-70-02").
**Description:** `client_cancel_booking` (POST `/client/booking/{id}/cancel`) has no
`Idempotency-Key` requirement. Network retry of a cancel will get 409 `invalid_transition`
(already-cancelled FSM guard) rather than idempotent 200.

**Current code state (verified 2026-06-16):**
```python
# apps/backend/app/modules/client_portal/router.py:437-461
async def client_cancel_booking(
    booking_id: UUID,
    client: Annotated[ClientPrincipal, Depends(require_client())],
    _csrf: Annotated[None, Depends(verify_client_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[ClientBookingResponse]:
    ...
```
No `verify_client_idempotency` dependency. The create-booking endpoint at line 380 does have it.

**Status: STILL OPEN (code-verified; accepted risk per D-70-02)**

The design decision D-70-02 explicitly scoped idempotency to booking CREATION only. Cancel
is terminal FSM state — a duplicate 409 on retry is handled PWA-side as implicit success.

**Verdict: STILL OPEN — Accepted by design (D-70-02). PWA must handle 409 `invalid_transition`
on cancel retry as implicit success. Not a security issue (cancel is idempotent at the DB level
— the state is already 'cancelled'); it is a UX reliability concern.**

---

## Summary Table

| Item | Source Finding | Description | Current Status | Verdict |
|------|---------------|-------------|----------------|---------|
| 1 | CR-02 | Proxy rate-limit shared "unknown" bucket | Still open in code | OPERATOR-PENDING (live infra needed to verify) |
| 2 | IN-01 | QR post-decode client existence check | Still open; accepted risk | STILL OPEN — accepted risk D-70-09 |
| 3 | IN-02 | Cancel endpoint idempotency | Still open; by design | STILL OPEN — by design D-70-02 |

---

## Next Steps

- **CR-02 fix** (code-side, safe to apply): Replace `"unknown"` fallback with fail-closed
  `raise RateLimited("rate_limited")` per `70-REVIEW.md CR-02`. Apply as a targeted fix in
  a future quick-task or Phase 119 follow-up. Verification (proxy trust behavior under Traefik)
  is operator-pending and requires live k3s deployment.
- **IN-01**: No action required. Documented accepted risk (D-70-09). Mark closed.
- **IN-02**: No action required. By design (D-70-02). Mark closed. PWA retry guide sufficient.
- **Formal `/gsd:secure-phase 70`** skill run: The orchestrator should run this to update
  this file with full gate evidence (ruff/mypy/pytest) and a formal close/defer decision
  per the skill workflow.

---

_Preliminary retro: 2026-06-16_
_Verifier: Phase 119 plan 03 executor (inline code verification)_
_Formal skill run: pending orchestrator action_
