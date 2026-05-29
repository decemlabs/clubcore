---
phase: 67-operator-pending-runbook-execution
plan: 05
status: complete
completed: 2026-05-29
requirements: [RUN-04, RUN-05]
---

# Plan 67-05 Summary — Reports (RUN-04) + Trainers (RUN-05) Live Walkthroughs

## Outcome

Both walkthroughs executed against a **live `docker compose` stack** with real, redacted transcripts (D-67-03, no fabrication). RUN-04 fully PASS (5/5 scenarios); RUN-05 PASS for trainer surface + report + CSV + RBAC, with the PT-booking→payroll-accrual scenario deferred (documented deviation).

## Environment brought up autonomously

- Rebuilt the stale backend image (baked `.venv` predated `jinja2`); DB already at head `0042` (migrate not needed).
- Backend live on `:8000` (`/healthz` 200 — runbook's `/api/v1/health` is stale, RUN-00-class note).
- Seeded via documented operator path: `scripts.seed_demo_data` (bootstrap owner) → membership plan via API → `scripts.seed_verification_fixtures` (verify_owner + verify_reception + 5 clients/memberships) → one owner cash sale (250 000 коп). Dev passwords set inline (so logins are genuine), never committed.

## RUN-04 — Reports (5/5 PASS)

1. **bring-up** — `/healthz` 200.
2. **revenue golden-path** — owner sale 250 000 коп → `reports/revenue` net **250 000 коп / 2 500,00 ₽** (matches runbook golden amount).
3. **audit-log** — `reports`/`audit-log` 200, real `login_success` event.
4. **reception-403** — reception → `reports/revenue` HTTP 403 `forbidden:view:reports`.
5. **CSV + Excel Cyrillic** — `revenue.csv` + `audit-log.csv` HTTP 200 with UTF-8 BOM (`ef bb bf`); Cyrillic round-trips (plan name "Стандарт 1 месяц").

## RUN-05 — Trainers (PASS + deferred sub-scenario)

- `GET /api/v1/trainers` 200 ("Тренер Тестов"); `reports/trainers` 200 (payroll/utilization columns); `reports/trainers.csv` 200 with BOM + Cyrillic.
- RBAC split: reception 403 on `reports/trainers`, 200 on operational `trainers` list.
- **Deviation (deferred):** the PT-booking → session-accrual → payroll chain not exercised end-to-end (needs slot/booking/PT-package seed); report columns are zeroed. Endpoints verified live; accrual-population scenario explicitly deferred.

## Incidental RUN-00-class findings (recorded in evidence)

- runbook health path `/api/v1/health` stale → `/healthz`.
- Idempotency-Key min length 16 (Phase 66 `{16,128}`) — a 15-char key returns 422 `idempotency_key_invalid_format` (confirms IDM hardening live).

## Key files

- modified: `.planning/milestones/v1.11-OPERATOR-EVIDENCE.md` (RUN-04 + RUN-05 sections + index)

## Commits

- `a257ee9e` — docs(67-05): RUN-04 reports + RUN-05 trainers walkthroughs (live)

## Decisions honored

- D-67-07 (live `docker compose` execution), D-67-03 (real evidence, deviations noted not fabricated), D-67-09 (stale identifiers documented).

## Self-Check: PASSED

- RUN-04 + RUN-05 sections present with real transcripts. ✓
- Revenue golden amount (2500₽) reproduced live. ✓
- CSV BOM + Cyrillic verified. ✓
- RBAC 403/200 split verified. ✓
- Deferred sub-scenario disclosed, not faked. ✓
