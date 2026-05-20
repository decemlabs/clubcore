# Phase 46: OpenAPI Handoff + Milestone Verification — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-20
**Phase:** 46-openapi-handoff-milestone-verification
**Mode:** `--auto` (single-pass; Claude auto-selected the recommended option for every gray area without interactive prompts)
**Areas discussed:** OpenAPI regen approach, schema.contract.test.ts shape, runbook scaffolding, race-test scope, deliverability probe, owner sign-off enumeration, inline-regression cap, plan partitioning

---

## OpenAPI regen approach (HANDOFF-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Single atomic commit (backend + frontend in lockstep) | Re-use `scripts/export_openapi.py` + frontend codegen; both files land in one commit, drift gates pass together | ✓ |
| Two separate commits (backend first, then frontend) | Easier to revert individually but breaks the "atomic regen" success criterion | |
| New tooling (e.g. openapi-typescript-codegen wrapper script) | Avoided — Phase 9 export shape is byte-stable already; new tooling = new risk | |

**Auto choice:** Single atomic commit (D-46-01).
**Rationale:** Phase 35 / Phase 40 precedent; CI drift gates are pair-wise + same-PR pattern is established.

---

## `schema.contract.test.ts` block shape (HANDOFF-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Three per-epic banners + three tuples (`_v16UsersChecks`, `_v16ResetChecks`, `_v16EmailChecks`) | Mirrors v1.2 / v1.4 / Phase 23 banner convention; more readable | ✓ |
| Single `_v16Checks` tuple with all 12 entries flat | Less code; harder to read at +12 entries | |
| Inline assertions per-path (no central tuple) | Drifts from the existing pattern | |

**Auto choice:** Three per-epic banners (D-46-05).

---

## Forward-guard count target

| Option | Description | Selected |
|--------|-------------|----------|
| Floor 70 / target 73 / ceiling 76 | Descriptive range — success criterion is "every new v1.6 path + method + body + 2xx", count derives | ✓ |
| Hard-pin to exactly 73 | Brittle — counter-incentivises clean refactoring of existing tuples | |
| No count discipline at all | Loses the spec floor | |

**Auto choice:** Range-based (D-46-06).

---

## Runbook scaffolding (VER-09 — DEFER-40-01 lesson)

| Option | Description | Selected |
|--------|-------------|----------|
| Engineer `run.sh` FRESH against current schema + fixtures BEFORE the verification session, with dedicated `46-09-PLAN.md` wave | Applies DEFER-40-01 lesson upfront; ROADMAP explicitly budgets for this | ✓ |
| Copy-paste v1.5 `run.sh` and fix bugs as they surface during verification | The v1.5 mistake — cost a 4-hotfix cluster + deferred 8 scenarios | |
| Skip the run.sh entirely, do scenarios by-hand interactively | Loses the re-runnable evidence trail; can't gate future regressions | |

**Auto choice:** Fresh `run.sh` with dedicated wave (D-46-10 + D-46-28).

---

## Sandbox-inbox provider for scenarios 01/03/05/06

| Option | Description | Selected |
|--------|-------------|----------|
| MailHog via `docker-compose --profile dev up` | Zero-cost, no external dep, fast spin-up, perfect for the 4 email-arrival scenarios | ✓ |
| Live Yandex Postbox sandbox | Real upstream, exercises circuit breaker, but needs credentials at execute-time | |
| Both, owner's choice at execute-time | Defaulted to MailHog; Postbox-sandbox kept as fallback per D-46-13 | |

**Auto choice:** MailHog default + Postbox-sandbox fallback (D-46-13).

---

## Race test scope (VER-10)

| Option | Description | Selected |
|--------|-------------|----------|
| 6 races shipped (5 new in Phase 46 + 1 from Phase 45 `test_payment_receipt_race.py`) | Meets the ≥6 floor; covers all surfaces from ROADMAP success criterion 4 | ✓ |
| 8+ races (over-deliver) | Diminishing returns; Phase 47 / v1.7 if any survive | |
| 5 races (under spec) | Misses the floor | |

**Auto choice:** 6 races (D-46-14).

---

## Live deliverability probe (VER-12)

| Option | Description | Selected |
|--------|-------------|----------|
| Throwaway Python script + manual header capture by owner | Minimal scope — 3 sends + 3 paste-in Authentication-Results headers | ✓ |
| Automated IMAP fetch of delivered mail | Credential plumbing for 3 different providers; out of scope | |
| Skip live probe, simulate via DKIM-validator service | Doesn't prove real-world delivery alignment | |

**Auto choice:** Throwaway script + manual capture (D-46-19 + D-46-20).

---

## Owner sign-off mechanism (VER-14)

| Option | Description | Selected |
|--------|-------------|----------|
| Per-constant enumeration in `signed_off_templates:` YAML in `v1.6-VERIFICATION-LOG.md` (15 strings verbatim from `LOCKED_EMAIL_TEMPLATES`) | Mirrors D-27-OWNER-COPY-LOCK lineage; explicit + auditable | ✓ |
| Single-line "owner signed off on all v1.6 templates" with no enumeration | Loses traceability; can't catch silent template-id drift | |
| Sign-off committed to a separate `OWNER-SIGN-OFF.md` file | Splinters evidence across multiple files | |

**Auto choice:** Per-constant enumeration in verification log (D-46-25).

---

## Inline-regression cap policy (VER-14)

| Option | Description | Selected |
|--------|-------------|----------|
| ≤5 inline fixes; 6th → DEFER-46-N (Option A default) OR open Phase 47 (Option B for invariant-breaking) | Mirrors v1.4 / v1.5 discipline | ✓ |
| Unlimited inline fixes | Risks open-ended verification session; v1.5 lesson rejects this | |
| Zero inline fixes (all regressions defer) | Too rigid for trivial typo-class fixes | |

**Auto choice:** ≤5 cap + decision-at-the-moment (D-46-26).

---

## Plan partitioning (Claude's discretion)

| Option | Description | Selected |
|--------|-------------|----------|
| 5 waves (regen / contract-test+README+Postman / 6 race tests parallel / run.sh engineering / live verification session) | Logical separation; Waves 1–4 parallelisable, Wave 5 serial | ✓ |
| Single big plan card | Too coarse; can't parallelise; can't track per-surface evidence | |
| Per-endpoint plan card (10+ cards) | Too fine; openapi regen is atomic, not per-endpoint | |

**Auto choice:** 5 waves (D-46-31).

---

## Claude's Discretion

- Exact tuple shape inside `schema.contract.test.ts` (one tuple vs three) — defaulted to three per-epic.
- Postman export script language (Python vs Node) — defaulted to Python (consistency with `export_openapi.py`).
- Whether to delete v1.5 `run.sh` after Phase 46 — kept as DEFER-40-01 reference.
- Whether `pnpm -F admin-web typecheck` re-greening counts as Phase 46 — inline if small, DEFER if invasive.

---

## Deferred Ideas

- `operation_id=` curation → v1.9 (D-35-07 lineage).
- `@sportzal/api-client` npm publish → v1.9.
- Postman v2.1 + Newman CLI + Confluence/Notion publish → v1.9.
- OpenAPI doc-site + versioned spec URL → v1.9.
- Idempotency-Key hardening (CR-01/02/02b) → v1.9.
- Multi-region SPF/DKIM/DMARC probe → v1.9.
- Production-load smoke (k6, locust) → never v1.6.
- Admin-web UI surfaces for any v1.6 endpoint → v2.0 frontend handoff.
- `_internal/email/webhook` Postman inclusion → never (internal-only).
- DEFER-46-N rows → placeholder for >5 inline regressions; roll to v1.7.
- Full v1.5 carry-forward runbook re-execution → v1.9 (DEFER-40-01 backfill).
- Webhook signature HMAC hardening → v1.7 if Postbox offers it.
- CSRF rotation policy review → v1.7 if run.sh threading surfaces a gap.
- Race-test runtime budget tuning → v1.7 testing-hygiene phase.
