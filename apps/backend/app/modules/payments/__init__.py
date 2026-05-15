"""Payments module — Phase 32 PAY-01..10 + REF-01..08.

Append-only ledger (B-01 INFRA-22). Caller-owns-txn discipline for
record_payment + issue_refund — sale orchestrator (Plan 32-02) and refund
orchestrator (Plan 32-03) own the UoW.

Protocol slots PaymentRecorder + PaymentRefunder wired exclusively from
app.main.create_app() (NOT in app.workers.telegram_bot). Defensive-raise
accessors get_payment_recorder() / get_payment_refunder() in
app.core.dependencies surface 'slot not registered' as RuntimeError.

Admin-web UI deferred to Phase 35 (D-32-26).
"""
