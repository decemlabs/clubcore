---
phase: 52-cross-channel-notifications-v1-6-carry-out
plan: "03"
subsystem: email-deliverability
tags: [carry-out, operator-gated, email-probe, template-countersign, defer-46-01, defer-46-02]
dependency_graph:
  requires: []
  provides: [CARRY-01-scaffolding, CARRY-02-scaffolding]
  affects: [v1.7-email-deliverability-evidence, v1.6-template-countersign]
tech_stack:
  added: []
  patterns: [operator-gated-scaffolding, defer-discipline, d-52-13, d-52-14]
key_files:
  created:
    - .planning/handoff/v1.7-email-deliverability-evidence/README.md
    - .planning/handoff/v1.6-template-countersign.md
  modified:
    - apps/backend/scripts/verify/v1_6_email_probe.py
decisions:
  - "AI ships scaffolding + structural attestation; live probe run + owner countersign are operator deliverables (D-52-14)"
  - "Evidence captured to v1.7-email-deliverability-evidence/ (updated from v1.6-VERIFICATION-LOG.md reference per D-52-13)"
  - "CARRY-02 countersign register scoped to exactly the original 15 v1.6 templates; 4 Phase 52 additions excluded"
metrics:
  duration_seconds: 196
  completed_date: "2026-05-23"
  tasks_completed: 2
  tasks_pending_operator: 1
  files_created: 2
  files_modified: 1
---

# Phase 52 Plan 03: CARRY-01/02 Operator-Gated Scaffolding Summary

**One-liner:** Scaffolding for v1.6 operator deferrals: probe script references v1.7 evidence dir + README, 15-template countersign register with signed_off_at placeholders; live run and sign-off are operator deliverables.

## Shipped Deliverables (Autonomous — COMPLETE)

### Task 1: CARRY-01 Probe Script + Evidence-Dir README

**Commit:** `1f5b3f0`

**What shipped:**

- `apps/backend/scripts/verify/v1_6_email_probe.py` — docstring and summary output block updated to reference `.planning/handoff/v1.7-email-deliverability-evidence/` instead of the old `v1.6-VERIFICATION-LOG.md`. No structural send-logic change (yandex.ru + mail.ru + rambler.ru providers already covered via `PROBE_YANDEX_TO`/`PROBE_MAIL_TO`/`PROBE_RAMBLER_TO` env vars). Threat note T-52-08 added inline.

- `.planning/handoff/v1.7-email-deliverability-evidence/README.md` — Full operator capture procedure:
  - Required env vars table (all 7 variables with security note)
  - Run command (copy-paste ready)
  - Step-by-step `Authentication-Results` capture instructions per provider
  - Per-provider YAML evidence file templates (`yandex_ru.yaml`, `mail_ru.yaml`, `rambler_ru.yaml`)
  - CARRY-01 closure acceptance checklist
  - AI scaffolding attestation

**Verification:** `grep -c "v1.7-email-deliverability-evidence" probe_script` → 5 matches. README exists. PROBE_* env vars intact (7 matches).

### Task 2: CARRY-02 15-Template Countersign Register

**Commit:** `ac53235`

**What shipped:**

- `.planning/handoff/v1.6-template-countersign.md` — Countersign register enumerating exactly the **15 original v1.6 `LOCKED_EMAIL_TEMPLATES`** identifiers:
  - Phase 42: `EMAIL_OTP_LOGIN` (1)
  - Phase 44: `USER_INVITATION_EMAIL`, `PASSWORD_RESET_EMAIL` (2)
  - Phase 45 expiry: 6 `EMAIL_EXPIRING_*` variants (6)
  - Phase 45 bookings: `EMAIL_BOOKING_CONFIRMED`, `EMAIL_BOOKING_CANCELLED_BY_CLIENT`, `EMAIL_BOOKING_CANCELLED_BY_OWNER`, `EMAIL_BOOKING_REMINDER_24H` (4)
  - Phase 45 payments: `EMAIL_PAYMENT_RECEIPT_SALE`, `EMAIL_PAYMENT_RECEIPT_REFUND` (2)
  - **Total: 15**

  Each row has `signed_off_at: TODO` placeholder. The 4 Phase 52 additions (`EMAIL_ONLINE_PAYMENT_SUCCEEDED`, `EMAIL_ONLINE_PAYMENT_REFUNDED`, `EMAIL_ONLINE_PAYMENT_CANCELED`, `EMAIL_FISCAL_RECEIPT_FAILED`) are excluded per CARRY-02 scope (D-52-13/D-52-07). Operator instructions, verification checklist, and AI attestation included.

**Verification:** `grep -c "signed_off_at"` → 9 matches. Numbered table rows: exactly 15.

---

## Operator-Pending Deliverables (Task 3 — Checkpoint: human-action)

The following deliverables require operator action and cannot be performed by the AI agent:

### CARRY-01: Live RU Email Probe Run (DEFER-46-01)

- **What:** Run `apps/backend/scripts/verify/v1_6_email_probe.py` with real Yandex Postbox credentials and owner-owned RU mailbox aliases
- **Requires:** Real `EMAIL_PROVIDER_API_KEY` + `AWS_ACCESS_KEY_ID` (Yandex Postbox), owner yandex.ru / mail.ru / rambler.ru aliases
- **Captures:** Per-provider `Authentication-Results` headers (SPF/DKIM/DMARC pass confirmation)
- **Saves to:** `.planning/handoff/v1.7-email-deliverability-evidence/` (see README for file format)
- **Closes:** DEFER-46-01

### CARRY-02: Owner Visual Countersign (DEFER-46-02)

- **What:** Open `.planning/handoff/v1.6-template-countersign.md`, visually check each of the 15 v1.6 email template files, record `signed_off_at:` timestamp in each row
- **Requires:** Owner visual review (no content edits — visual check only)
- **Closes:** DEFER-46-02

---

## Deviations from Plan

None — plan executed exactly as written. The probe script already targeted all 3 required providers; only the docstring/output reference was updated per plan action. The 15 template count was confirmed against the live `LOCKED_EMAIL_TEMPLATES` frozenset.

## Threat Surface Scan

No new network endpoints, auth paths, or trust boundaries introduced. The evidence README explicitly documents T-52-08 (credential + recipient-address redaction) and T-52-09 (repudiation mitigation via operator timestamp). No new threat flags beyond what is registered in the plan's threat model.

## Self-Check

- [x] `.planning/handoff/v1.7-email-deliverability-evidence/README.md` exists — FOUND
- [x] `.planning/handoff/v1.6-template-countersign.md` exists — FOUND
- [x] Probe script references `v1.7-email-deliverability-evidence` — 5 occurrences
- [x] Probe script env vars `PROBE_YANDEX_TO`, `PROBE_MAIL_TO`, `PROBE_RAMBLER_TO` intact — 7 occurrences
- [x] Countersign register has `signed_off_at` placeholders — 9 occurrences
- [x] Countersign register has exactly 15 numbered template rows
- [x] Task 1 commit `1f5b3f0` exists
- [x] Task 2 commit `ac53235` exists

## Self-Check: PASSED
