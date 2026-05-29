# Phase 67: Operator-Pending Runbook Execution - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-29
**Phase:** 67-operator-pending-runbook-execution
**Mode:** `--auto` — all gray areas auto-resolved with the recommended default; no interactive prompts.
**Areas discussed:** Evidence-file location, Credential-gated execute-vs-defer policy, Walkthrough environment, Staleness-audit fix handling, Plan decomposition, Mailpit wiring

---

## Evidence-file location (RUN-07)

| Option | Description | Selected |
|--------|-------------|----------|
| New `v1.11-OPERATOR-EVIDENCE.md` | Create a fresh milestone evidence file per ROADMAP SC#3 + RUN-07 explicit path | ✓ |
| Append into `v1.10-OPERATOR-EVIDENCE.md` | Follow the older D-62.1-B2 frontmatter note that v1.11 captures append to the v1.10 file | |

**Selected:** New file. **Notes:** Documented conflict between ROADMAP/RUN-07 (name a new `v1.11-` file) and the v1.10 frontmatter (says append). Resolved toward the more specific/recent instruction; append-only spirit kept inside the new file; cross-link both ways. → D-67-01/02/03.

---

## Credential-gated execute-vs-defer policy (RUN-01 / RUN-02 / RUN-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Attempt live, fall back to N/A | Run each probe live; record `N/A-until-production` only where the capability is genuinely absent | ✓ |
| Defer all to production | Mark every credential-gated item N/A-until-production without attempting | |

**Selected:** Per-item resolution. **Notes:** RUN-01 ЮKassa = attempt live with `YOOKASSA_SANDBOX=true` pre-flight (first evidence line), else N/A. RUN-02 RU email = N/A-until-production (no prod `clubcore.*` domain). RUN-03 templates = owner-actionable PASS (visual check, not credential-gated). → D-67-04/05/06.

---

## Walkthrough environment (RUN-04 / RUN-05)

| Option | Description | Selected |
|--------|-------------|----------|
| Live `docker compose up` | Run walkthroughs against the real local stack, capture curl/CSV/Cyrillic | ✓ |
| ASGITransport / mocked | Run via test transport without a live stack | |

**Selected:** Live stack. **Notes:** SC#3 requires live `docker compose up` execution with CSV-export samples + Cyrillic-encoding verification. → D-67-07.

---

## Staleness-audit fix handling (RUN-00)

| Option | Description | Selected |
|--------|-------------|----------|
| Inline-minor + document-structural | Fix stale identifiers inline as revision-log entries; document structural staleness in evidence with workaround | ✓ |
| Full runbook rewrite | Rewrite runbooks to current state | |

**Selected:** Inline-minor + document-structural. **Notes:** D-11-RUN-AUDIT locked; RUN-00 is a hard gate before any live walkthrough (Pitfall #11). → D-67-08/09.

---

## Plan decomposition

| Option | Description | Selected |
|--------|-------------|----------|
| Audit-gate + per-runbook + independent Mailpit | Plan 1 = RUN-00 gate + evidence scaffold; per-source walkthrough plans; Mailpit independent | ✓ |
| Single monolithic execution plan | One plan runs everything | |

**Selected:** Decomposed. **Notes:** Mirrors 63/64/66 atomic discipline; final grouping is planner's call. → D-67-12.

---

## Mailpit wiring (RUN-06)

| Option | Description | Selected |
|--------|-------------|----------|
| Profile only, no adapter | `axllent/mailpit:latest` under `profiles: ["dev"]`, ports 1025/8025; SES-V2 path untouched | ✓ |
| Profile + SMTP adapter | Also wire `aiosmtplib` so mail is actually intercepted | |

**Selected:** Profile only. **Notes:** D-11-MAILPIT-PROFILE — adapter is INFRA-02, deferred. → D-67-10/11.

## Claude's Discretion

- Exact number/grouping of walkthrough plans (within D-67-12 guidance).
- Internal table/section layout of `v1.11-OPERATOR-EVIDENCE.md` (follow v1.10 structure).
- Whether RUN-02/RUN-03 registers are new files or appended sections.

## Deferred Ideas

- SMTP adapter (`aiosmtplib`) → INFRA-02, out of v1.11 scope.
- Live RU email deliverability capture → fires when a production `clubcore.*` domain is provisioned (RUN-02 trigger).
