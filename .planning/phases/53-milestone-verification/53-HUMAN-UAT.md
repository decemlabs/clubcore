---
status: partial
phase: 53-milestone-verification
source: [53-VERIFICATION.md]
started: 2026-05-23T21:00:00Z
updated: 2026-05-23T21:00:00Z
---

## Current Test

[awaiting operator]

## Tests

### UAT-53-01 — Live runbook end-to-end (VER-01)
- **Test:** `bash apps/backend/scripts/verify/v1_7_runbook.sh` against `docker compose up` with `YOOKASSA_SANDBOX=true`, after seeding (`uv run python -m scripts.seed_v1_4_verification_fixtures`).
- **Expected:** runbook prints `ALL SCENARIOS PASS`.
- **Why human:** requires a seeded live stack (backend + Postgres 16 + Redis 7 + ARQ worker + Telegram bot). The `fiscal_receipts.online_payment_id` column defect the verifier flagged is already fixed (commit `f5ce4ec`) and validated against the live schema; this is the live execution confirmation.
- **status:** pending

### UAT-53-02 — ЮKassa sandbox walkthrough (VER-03)
- **Test:** Operator records a live membership sale + refund through the ЮKassa sandbox dashboard and deposits evidence at `.planning/handoff/v1.7-yookassa-sandbox-evidence/` per that dir's README checklist.
- **Expected:** all checklist items satisfied — sale initiated, `payment.succeeded` processed, fiscal_receipts row observed, refund initiated, `refund.succeeded` processed, refund fiscal row observed, ≥1 redacted YAML evidence file saved.
- **Why human:** requires real ЮKassa sandbox credentials + a live session — operator-pending by design (CONTEXT D-04, mirrors Phase 52 CARRY-01/02).
- **status:** pending

## Notes

- Technical criteria VER-02 (16/16 race + parity tests pass against real Postgres+Redis), VER-04 (0/5 product-code regressions), and VER-05 (DEFER-46-03 circuit-breaker parity closed) are VERIFIED — see `53-VERIFICATION.md`.
- Broader backend suite has 12 pre-existing failures + 14 errors unrelated to Phase 53 (`app/` untouched this phase) — DEFER-46-04 / DEFER-36-04-A tree-wide test debt, recommended for a v1.8/v1.9 sweep. See `.planning/milestones/v1.7-VERIFICATION-LOG.md`.
