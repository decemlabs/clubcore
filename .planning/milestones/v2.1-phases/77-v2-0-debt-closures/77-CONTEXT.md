# Phase 77: v2.0 Debt Closures - Context

**Gathered:** 2026-06-02
**Status:** Ready for planning
**Mode:** Smart discuss (autonomous) — 2 grey areas resolved

<domain>
## Phase Boundary

Close the two deferred v2.0 integration warnings in `apps/client-pwa`. Two independent fixes:

1. **FIX-01 (WARNING-1)** — `BookingManageSheet` "Отменить запись" is wired to the real backend: the final cancel button calls `useCancelBooking().mutateAsync({ bookingId })` (the hook already exists, targets `POST /api/v1/client/booking/{booking_id}/cancel`), the booking is cancelled server-side, and the bookings list updates without a page reload (via the hook's existing `bookings()` invalidation). Today the button is a local-only `setView('done-cancel')` transition that never calls the mutation.
2. **FIX-02 (WARNING-2)** — DOC-ONLY resolution: the `999.5-UI-SPEC §Screen 2 D-09` receipt-destination chip is reconciled by **amending the spec** (not restoring the chip). The success screen stays mockup-faithful (no "ЧЕК ОТПРАВЛЕН НА …" line); the UI-SPEC is amended with an explicit rationale and the current no-chip state is declared the accepted behavior. Satisfies success-criterion #2's second branch.

**NOT in this phase:** no backend changes (the cancel endpoint + receiptEmail/receiptPhone fields already exist); no restyle of the success screen; no new chat/booking features; FIX-01 and FIX-02 are independent of Phase 75/76.

</domain>

<decisions>
## Implementation Decisions

### FIX-01 — cancel-booking wiring (accepted recommended)
- **D-77-01:** Wire the final "Отменить запись" button in `BookingManageSheet.jsx` (the `cancel`-view confirm button, currently `onClick={() => setView('done-cancel')}` ~line 116) to `useCancelBooking().mutateAsync({ bookingId })`. The `bookingId` comes from the booking object the sheet receives as a prop.
- **D-77-02:** Loading state — disable the confirm button and show "Отмена…" while `mutation.isPending`.
- **D-77-03:** Error handling (the hook has only `onSettled`, no `onError`) — wrap `mutateAsync` in try/catch; on failure STAY on the `cancel`-confirm view and show an inline error message. Map the backend `409 cancel_window_expired` to clear Russian copy (e.g. "Окно отмены истекло — обратитесь на ресепшн"); use a generic fallback ("Не удалось отменить запись. Попробуйте ещё раз.") for other errors.
- **D-77-04:** Transition to the `done-cancel` success view ONLY after `mutateAsync` resolves. The hook's existing `onSettled` invalidation of `clientPortalKeys.bookings()` refreshes the list with no page reload — no optimistic `onMutate` needed (D-77 chose the simpler invalidate-on-settle path over optimistic update).

### FIX-02 — receipt-destination display (accepted: amend spec, accept current)
- **D-77-05:** Do NOT restore the receipt-destination chip on `PaymentSucceededView`. Keep the success screen mockup-faithful (the "REVISION 2" removal stands). The existing "Открыть чек" receipt-link row already gives the client access to the fiscal receipt.
- **D-77-06:** Amend `999.5-UI-SPEC.md §Screen 2 D-09` (at `.planning/milestones/v2.0-phases/999.5-client-pwa-onboarding-and-receipt-email/999.5-UI-SPEC.md` ~lines 383-389) with an explicit rationale: the "ЧЕК ОТПРАВЛЕН НА {email|phone}" line is intentionally omitted to match the approved payment mockup; receipt access is provided via the "Открыть чек" link; backend `receiptEmail`/`receiptPhone` remain available for any future reinstatement. Declare the current no-chip `PaymentSucceededView` the **accepted behavior** for this contract item. This is the documented resolution path for success-criterion #2.
- **D-77-07:** FIX-02 is documentation-only — no change to `PaymentReturnScreen.jsx` / `PaymentSucceededView`. (A short cross-reference note may be added near the existing REVISION 2 comment pointing to the amended D-09, but no behavioral code change.)

### Claude's Discretion
- Exact wording of the amended D-09 rationale and the inline error copy strings (within the intent above); whether the FIX-01 inline error is a styled banner vs reusing an existing error affordance in the sheet — follow existing BookingManageSheet/sheet conventions.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase / milestone scope
- `.planning/ROADMAP.md` §"Phase 77: v2.0 Debt Closures" — goal + 2 success criteria.
- `.planning/REQUIREMENTS.md` — FIX-01, FIX-02.
- `.planning/STATE.md` §"Deferred Items" — WARNING-1 / WARNING-2 origin (v2.0 close).

### FIX-01 files
- `apps/client-pwa/src/screens/sheets/BookingManageSheet.jsx` — overview "Отменить бронь" (~339-342 `setView('cancel')`) and the cancel-confirm "Отменить запись" button (~115-124, currently `setView('done-cancel')` — the wiring target).
- `apps/client-pwa/src/lib/clientQueries.ts` — `useCancelBooking()` (~464-479): `mutationFn` → `POST /api/v1/client/booking/{booking_id}/cancel`, `onSettled` invalidates `clientPortalKeys.bookings()`. `useClientBookings()` (~397-409) renders the list off the same key.
- `apps/backend/app/modules/client_portal/router.py` — `POST /booking/{booking_id}/cancel` (~395-430): returns `ResponseEnvelope[ClientBookingResponse]`; `404 booking_not_found` (IDOR anti-oracle), `409 cancel_window_expired` outside the cancel window.

### FIX-02 files
- `.planning/milestones/v2.0-phases/999.5-client-pwa-onboarding-and-receipt-email/999.5-UI-SPEC.md` (~383-389) — the D-09 "Post-payment augmentation" contract to AMEND.
- `apps/client-pwa/src/routes/PaymentReturnScreen.jsx` — `PaymentSucceededView` (~167-380); REVISION 2 note (~19-30) recording the chip removal; receipt-link row (~319-345). (Read-only context; no behavioral change.)
- `apps/backend/app/modules/client_portal/schemas.py` — `ClientPaymentStatusResponse.receipt_email`/`receipt_phone` (~263-275, wire `receiptEmail`/`receiptPhone`) — still available, just not displayed.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `useCancelBooking()` is already implemented and correct — FIX-01 only needs to CALL it from the sheet (loading/error handling added at the call site).
- `BookingManageSheet` already has the `cancel` and `done-cancel` views fully styled — FIX-01 reuses them; only the confirm button handler changes + a loading/error affordance is added.
- `clientPortalKeys.bookings()` invalidation already wired in the hook → list refreshes with no reload.

### Established Patterns
- Mutation call sites elsewhere (e.g. `ProfileExtraSheets` save from Phase 76) use `mutateAsync` in try/catch with an inline toast/error + `isPending` button state — mirror that for FIX-01.
- No global toast lib; inline state-based error (mirror CheckoutSheet/ProfileExtraSheets pattern) if a banner is needed.

### Integration Points
- FIX-01: `BookingManageSheet` confirm button → `useCancelBooking` → backend cancel → `bookings()` invalidation → list refresh.
- FIX-02: pure documentation edit to the archived 999.5-UI-SPEC; no runtime integration.

</code_context>

<specifics>
## Specific Ideas

- The cancel hook deliberately has no optimistic update — invalidate-on-settle is sufficient and avoids rollback complexity (D-77-04).
- FIX-02 is intentionally a doc resolution, not a code change: the user chose mockup fidelity over the D-09 chip; the contract is updated to match reality with a recorded rationale rather than the code being forced to the stale contract.

</specifics>

<deferred>
## Deferred Ideas

- Reinstating the receipt-destination chip (if a future mockup revision wants it) — backend `receiptEmail`/`receiptPhone` already support it; would be a small `PaymentSucceededView` addition per the (now-amended) D-09.
- Optimistic cancel UX (instant list removal + rollback) — deferred; invalidate-on-settle chosen for simplicity.

</deferred>

---

*Phase: 77-v2-0-debt-closures*
*Context gathered: 2026-06-02 via smart discuss (autonomous)*
