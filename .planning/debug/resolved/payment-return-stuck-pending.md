---
status: resolved
trigger: "http://localhost:5174/payment/return?payment_id=ffecee29-4830-4577-90e7-4b2d3a246f1a — paid, then the 'Ожидаем подтверждение' spinner runs indefinitely"
created: 2026-06-01
updated: 2026-06-01
slug: payment-return-stuck-pending
---

# Debug Session: payment-return-stuck-pending

## Symptoms

DATA_START
- **Trigger URL:** `http://localhost:5174/payment/return?payment_id=ffecee29-4830-4577-90e7-4b2d3a246f1a` (client-pwa dev, port 5174)
- **Expected:** After paying, `PaymentReturnScreen` should poll the payment status, see `succeeded`, and show the "Готово!" success state (D-10).
- **Actual:** The "Ожидаем подтверждение / Платёж обрабатывается" pending spinner runs indefinitely; status never flips to `succeeded`.
- **Errors:** None reported by the user (no error screen — just the perpetual pending state).
- **Timeline:** Observed 2026-06-01 while manually testing the newly-restyled checkout flow locally.
- **Reproduction:** Open client-pwa checkout → "Оплатить" → ЮKassa redirect → return to `/payment/return?payment_id=...` → spinner never resolves.
- **Specific payment_id:** `ffecee29-4830-4577-90e7-4b2d3a246f1a` (internal online_payments id from the return URL).
DATA_END

## Scope / NOT the cause (already ruled out by orchestrator)

- **Route is correct:** `apps/client-pwa/src/App.jsx:230` registers `<Route path="/payment/return" ...>` — matches the URL, the screen renders. Not a routing bug.
- **Not caused by the recent checkout restyle (quick task 260601-sxf):** `PaymentReturnScreen.jsx` and the payment-launch path (`launchCheckout` in `CheckoutSheet.jsx`) were NOT modified by that task. Confirmed via git: restyle commits touched only the review-stage JSX + styles.css + PlansSheet.jsx.
- **Client polling is functioning as designed:** `useClientPaymentStatus` (apps/client-pwa/src/lib/clientQueries.ts:470-482) polls `GET /api/v1/client/payments/{payment_id}/status` every 3s while `status === 'pending'`, stops otherwise. `PaymentReturnScreen` shows a "На главную" exit after `PENDING_TIMEOUT_MS` (30s) — the spinner itself is correct behavior.

## Leading hypothesis (orchestrator's prior investigation — verify, don't assume)

Backend payment status only transitions `pending → succeeded` when ЮKassa POSTs a
`payment.succeeded` webhook to `POST /api/v1/_internal/yookassa/webhook`
(`apps/backend/app/api/v1/_internal/yookassa/router.py:62-159`,
handler `handlers.py: handle_payment_succeeded`). The handler re-fetches via
`yookassa_client.get_payment(object_id)` and trusts the re-fetched status (body is
not trusted). Locally, ЮKassa cannot reach `localhost`, so the webhook never
arrives and the row stays `pending` forever.

Webhook IP allowlist (`webhook_verifier.py: verify_yookassa_ip`) has a **sandbox
bypass** (`if _settings.sandbox: return`, ~line 88), so a local curl CAN deliver
the webhook IFF `YOOKASSA_SANDBOX=true` on the backend stack. Existing precedent:
`apps/backend/scripts/verify/09_online_sale_to_fiscal.sh` step 3 simulates the
`payment.succeeded` webhook from localhost.

### Key things to verify (turn hypothesis into evidence)
1. Does an `online_payments` row exist for internal id `ffecee29-4830-4577-90e7-4b2d3a246f1a`? What is its `status` and its `yookassa_payment_id`?
2. Is the backend (`apps/backend`, docker compose) actually running, and is `GET /api/v1/client/payments/ffecee29-.../status` reachable / what does it return?
3. Is `YOOKASSA_SANDBOX=true` set on the running stack? (Determines whether the webhook re-fetch / sandbox client returns `succeeded`.)
4. In sandbox mode, what does `yookassa_client.get_payment(<yk_id>)` return for a payment that was never confirmed in the ЮKassa sandbox? (Affects whether a simulated webhook actually flips the status.)
5. Confirm there is no background ARQ "YooKassa sync" job expected to poll status (phase 999.4-06 mentioned a sync+retry handler) — and if there is, whether the worker is running locally.

## Current Focus

- hypothesis: **CONFIRMED.** The `online_payments` row for `ffecee29-...` sat at `status=pending` with `yookassa_payment_id=31afe4a6-000f-5001-9000-11e2358167a9`. ЮKassa cannot POST to localhost, so the webhook never arrived. The sandbox bypass is active (`YOOKASSA_SANDBOX=true` in both `.env` and the running container). A simulated `payment.succeeded` webhook via curl flipped the row to `succeeded` immediately (HTTP 200, body `ok`). There is no ARQ cron that polls pending *payment* status (only `poll_pending_refunds` exists for refunds). The missing local developer tool is the fix.
- next_action: Propose fix — create a developer helper script (mirroring `09_online_sale_to_fiscal.sh` step 3 pattern) that simulates the webhook for a given payment_id.

## Evidence

- timestamp: 2026-06-01T18:45:00Z
  type: db_query
  finding: >
    `online_payments` row EXISTS for internal id `ffecee29-4830-4577-90e7-4b2d3a246f1a`:
    status=`pending`, yookassa_payment_id=`31afe4a6-000f-5001-9000-11e2358167a9`,
    amount_kopecks=500000 (5000 RUB), initiated_at=2026-06-01T18:35:18Z, succeeded_at=NULL.

- timestamp: 2026-06-01T18:45:10Z
  type: env_check
  finding: >
    Backend docker compose running (backend, postgres, redis, arq-worker, telegram-bot all Up).
    `YOOKASSA_SANDBOX=true` confirmed in both `.env` file and via `docker exec backend-backend-1 env`.
    Status endpoint returned 401 (requires auth cookie) — polling works at the HTTP level;
    the 401 is expected for unauthenticated direct curl, not a bug.

- timestamp: 2026-06-01T18:45:30Z
  type: code_review
  finding: >
    No ARQ cron or scheduled job for polling pending *payments* exists.
    `app/workers/scheduled/` contains: expire_memberships, expire_pt_packages,
    send_expiring_notifications, send_booking_reminders, mark_no_show_bookings,
    monitor_stale_fiscal_receipts, **poll_pending_refunds**, generate_recurring_slots,
    cleanup_password_reset_tokens, send_expiring_notifications.
    `poll_pending_refunds` only handles online_refunds (not online_payments).
    There is NO `poll_pending_payments` cron — status is 100% webhook-driven.

- timestamp: 2026-06-01T18:46:00Z
  type: webhook_simulation
  finding: >
    Flushed Redis dedup key `sz:yookassa:webhook:payment.succeeded:31afe4a6-000f-5001-9000-11e2358167a9`.
    Simulated `payment.succeeded` webhook via curl to `POST http://localhost:8000/api/v1/_internal/yookassa/webhook`
    with `{"event":"payment.succeeded","object":{"id":"31afe4a6-000f-5001-9000-11e2358167a9","status":"succeeded",...}}`.
    Result: HTTP 200, body=`ok`. Subsequent DB check: status=`succeeded`, succeeded_at=2026-06-01T18:50:14Z.
    Confirmed: sandbox bypass works (`YOOKASSA_SANDBOX=true`); the handler re-fetches from ЮKassa sandbox
    and the sandbox returns `succeeded` for this payment.

## Eliminated

- App code bug in PaymentReturnScreen or useClientPaymentStatus — ruled out (pre-confirmed).
- Recent checkout restyle as cause — ruled out (pre-confirmed, no changes to payment status files).
- Backend not running — eliminated; all 5 services up.
- Missing sandbox bypass — eliminated; bypass is `YOOKASSA_SANDBOX=true` and active.
- ARQ sync polling gap — eliminated; no such cron exists by design (webhook-authoritative).

## ROOT CAUSE

**Environment/integration gap: ЮKassa sandbox cannot POST webhooks to localhost.**

The `online_payments` row status only transitions `pending → succeeded` when the
`payment.succeeded` webhook arrives at `POST /api/v1/_internal/yookassa/webhook`.
In local development, ЮKassa's servers cannot reach `localhost:8000`, so the webhook
is never delivered. The sandbox IP-bypass (`YOOKASSA_SANDBOX=true`) is correctly
configured, meaning a manually-delivered curl *can* trigger the transition — but
there is no developer tool to do this conveniently.

**specialist_hint: general**

## Resolution

- root_cause: No local webhook delivery mechanism. ЮKassa cannot reach localhost; the sandbox bypass exists but requires a manual curl command that developers must construct themselves each time.
- immediate_resolution: The specific stuck payment `ffecee29-4830-4577-90e7-4b2d3a246f1a` (yk `31afe4a6-...`) was confirmed during diagnosis (simulated webhook → status `succeeded`).
- fix: >
    APPLIED — created `apps/backend/scripts/dev/simulate_webhook_payment_succeeded.sh`
    (commit 6d879de2). Accepts an internal `online_payment_id`, resolves the
    `yookassa_payment_id` + status via `docker compose exec postgres psql` against DB
    `clubcore`, refuses non-pending rows, flushes the Redis dedup key
    (`cc:yookassa:webhook:payment.succeeded:{yk_id}`, plus legacy `sz:` for safety),
    POSTs the `payment.succeeded` webhook to the sandbox-bypassed endpoint, and
    re-checks that the row flipped to `succeeded`. shellcheck clean; smoke-tested
    against the reported payment (correctly reported "already succeeded").
- verification: >
    shellcheck clean; `simulate_webhook_payment_succeeded.sh ffecee29-...` resolved
    the row and hit the already-succeeded early-exit. Full webhook path mirrors the
    proven `verify/09_online_sale_to_fiscal.sh` step3.
- files_changed: apps/backend/scripts/dev/simulate_webhook_payment_succeeded.sh
- not_changed: >
    Payment-confirmation UX semantics untouched — D-10 anti-oracle and
    webhook-authoritative status preserved (no client-side status faking, no
    poll_pending_payments cron added). The client `PaymentReturnScreen` 30s timeout
    + "На главную" exit already handles abandoned/slow confirmations correctly.
- superseded_proposed_fix: >
    Create `apps/backend/scripts/dev/simulate_webhook_payment_succeeded.sh` — a
    standalone developer helper that accepts an `online_payment_id` (internal UUID),
    looks up `yookassa_payment_id` from the DB, flushes the Redis dedup key, and fires
    the simulated `payment.succeeded` webhook to `localhost:8000`. Mirrors the step3
    pattern from `09_online_sale_to_fiscal.sh`. Document in a comment block in
    `apps/client-pwa/src/screens/PaymentReturnScreen` (or in a dev README) that this
    script is the local test workflow for the payment confirmation loop.
