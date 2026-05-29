# Phase 67: Operator-Pending Runbook Execution - Context

**Gathered:** 2026-05-29
**Status:** Ready for planning
**Mode:** `--auto` (gray areas auto-resolved with recommended defaults; see DISCUSSION-LOG.md)

<domain>
## Phase Boundary

Execution-and-evidence phase that closes the v1.11 milestone with **zero operator-pending tail**. It executes every accumulated operator-pending walkthrough (deferred since v1.7/v1.8/v1.9), captures the evidence, adds the Mailpit `--profile dev` SMTP-trap to docker-compose for future dev use, and produces `.planning/milestones/v1.11-OPERATOR-EVIDENCE.md` as the complete evidence record.

**No new business code.** The only code change is the Mailpit compose service (RUN-06). Everything else is: (a) running existing runbooks/procedures against a live `docker compose up` stack, (b) capturing curl/DM/CSV transcripts, (c) recording PASS / FAIL / `N/A-until-production` rows.

**In scope:** RUN-00 (staleness audit) → RUN-01 (ЮKassa sandbox) → RUN-02 (RU email deliverability) → RUN-03 (19-template owner countersign) → RUN-04 (reports runbook) → RUN-05 (trainers runbook) → RUN-06 (Mailpit profile) → RUN-07 (evidence file).

**Out of scope:** SMTP adapter (`aiosmtplib`) — deferred to INFRA-02 per D-11-MAILPIT-PROFILE; only the Mailpit profile is wired now. No runbook *rewrites* — only minor inline staleness fixes. No new endpoints, schemas, or migrations.

</domain>

<decisions>
## Implementation Decisions

### Evidence file (RUN-07)
- **D-67-01:** Create a **new** `.planning/milestones/v1.11-OPERATOR-EVIDENCE.md` (NOT append into `v1.10-OPERATOR-EVIDENCE.md`). Rationale: ROADMAP SC#3 + RUN-07 explicitly name the new `v1.11-` path; the more specific/recent instruction wins over the older D-62.1-B2 frontmatter note in the v1.10 file. The append-only *spirit* is honored within the v1.11 file.
- **D-67-02:** New file carries append-only frontmatter mirroring v1.10's convention (`convention: append-only`, `milestone: v1.11`, `items: [...]`, `decisions_honored: [...]`). Each RUN-* row links back to its source artifact (v1.7 / v1.8 / v1.9 phase archives). Cross-link both ways: add a one-line pointer in `v1.10-OPERATOR-EVIDENCE.md`'s "TO BE APPENDED" line redirecting to the new v1.11 file.
- **D-67-03:** No fabricated evidence. Real transcripts only; absent capability → explicit `N/A-until-production` row with documented trigger condition (precedent: `RUN-08-dns-dkim-DEFERRED`).

### Credential-gated execute-vs-defer policy (RUN-01 / RUN-02 / RUN-03)
- **D-67-04 (RUN-01 ЮKassa sandbox):** Attempt the **live** sandbox sale + refund walkthrough. Mandatory pre-flight: `YOOKASSA_SANDBOX=true` confirmed as the **first evidence line** (PITFALLS Pitfall #11). If sandbox credentials are unavailable at execution time → record `N/A-until-production` with the trigger condition; do NOT fabricate. Procedure source: `.planning/handoff/v1.7-yookassa-sandbox-evidence/README.md`.
- **D-67-05 (RUN-02 RU email deliverability):** Default to `N/A-until-production` — no production `clubcore.*` domain is provisioned, so the live `Authentication-Results` probe (yandex.ru + mail.ru + rambler.ru) cannot run. Document the exact trigger condition (matches v1.10 RUN-08 precedent). Procedure source: `.planning/handoff/v1.7-email-deliverability-evidence/README.md`.
- **D-67-06 (RUN-03 19-template countersign):** Treat as **owner-actionable PASS**, not credential-gated. Owner (the user) performs the visual check across all 19 LOCKED templates (15 v1.6 + 4 v1.7) sourced from `app/core/audit.py LOCKED_EMAIL_TEMPLATES`. Capture per-template PASS/FAIL in a countersign register (extend `v1.6-template-countersign.md` pattern to all 19). Visual check only — no template content edits.

### Walkthrough environment (RUN-04 / RUN-05)
- **D-67-07:** Both reports (RUN-04) and trainers (RUN-05) walkthroughs run against a **live `docker compose up`** local stack. Capture curl transcripts per scenario. RUN-04 additionally captures CSV-export samples + a Cyrillic-encoding verification check. RUN-05 captures evidence per scenario of the 513-line / 5-scenario trainers runbook.

### Staleness audit (RUN-00) — the gate
- **D-67-08:** RUN-00 is the **first plan and a hard gate** — no live walkthrough begins until the staleness audit of all runbook/procedure docs completes (D-11-RUN-AUDIT; v1.5 Phase 40 retrospective recorded 4 hotfixes on first execution).
- **D-67-09:** Audit greps each doc for stale identifiers: `sz:` Redis prefix, `SPORTZAL_EMAIL_FROM`, renamed endpoints/tables/ports, `sportzal`/`Sportzal` brand leftovers. **Minor identifier fixes applied inline** as runbook-revision-log entries; **structural staleness documented** in the evidence file with a workaround note (do not rewrite runbooks).

### Mailpit profile (RUN-06)
- **D-67-10:** Add Mailpit to `apps/backend/docker-compose.yml` under `profiles: ["dev"]` only — never starts in the default/production compose. Image `axllent/mailpit:latest` (MailHog archived 2019 per STACK.md). Ports `1025` (SMTP) + `8025` (web UI). `docker compose --profile dev up` must start mailpit alongside existing services (backend / telegram-bot / arq-worker / migrate / postgres / redis).
- **D-67-11:** Do **NOT** add an SMTP adapter (D-11-MAILPIT-PROFILE — adapter is INFRA-02, deferred). Document in the runbook that Mailpit is a dev-only SMTP trap and that the **current email path is Yandex SES-V2 / aioboto3 and is NOT intercepted** by Mailpit; the profile is forward-wiring for a future SMTP adapter only.

### Plan decomposition (hint for planner — final shape is planner's call)
- **D-67-12:** Mirror the atomic-commit discipline of Phases 63/64/66. Suggested ordering: Plan 1 = RUN-00 staleness audit (gate) + RUN-07 evidence-file scaffold; then per-source walkthrough plans (RUN-01, RUN-02, RUN-03, RUN-04, RUN-05); RUN-06 Mailpit is independent infra (no walkthrough dependency, can land early/parallel). Each plan appends its evidence rows to the single v1.11-OPERATOR-EVIDENCE.md.

### Claude's Discretion
- Exact number/grouping of walkthrough plans (planner decides within D-67-12 guidance).
- Precise table/section layout inside `v1.11-OPERATOR-EVIDENCE.md` (follow v1.10 file's structure).
- Whether RUN-02/RUN-03 register files are new files or appended sections.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 67 scope authority
- `.planning/ROADMAP.md` §"Phase 67: Operator-Pending Runbook Execution" — goal, dependencies, 5 success criteria
- `.planning/REQUIREMENTS.md` lines 63–72 (RUN-00..RUN-07) + line 92 (INFRA-02 deferred) + lines 110, 121, 124 (decision table) — authoritative requirement text and the execution-only note

### v1.11 milestone decisions (locked 2026-05-26)
- `.planning/REQUIREMENTS.md` decision table: **D-11-RUN-AUDIT** (staleness audit gate), **D-11-MAILPIT-PROFILE** (profile only, no adapter)
- Append-only convention **D-62.1-B2** and `N/A-until-production` precedent **RUN-08-dns-dkim-DEFERRED** — see `.planning/milestones/v1.10-OPERATOR-EVIDENCE.md` (frontmatter + RUN-08 sections; use as the structural template for the v1.11 file)

### Runbook / procedure docs to audit + execute (RUN-00 inputs)
- `.planning/handoff/v1.7-yookassa-sandbox-evidence/README.md` — ЮKassa sandbox sale+refund procedure (RUN-01)
- `.planning/handoff/v1.7-email-deliverability-evidence/README.md` — RU email deliverability probe procedure (RUN-02)
- `.planning/handoff/v1.6-template-countersign.md` — owner countersign register pattern; extend to all 19 templates (RUN-03)
- `.planning/handoff/v1.8-reports-runbook.md` — reports live walkthrough (RUN-04)
- `.planning/handoff/v1.9-trainers-runbook.md` — 513-line / 5-scenario trainers walkthrough (RUN-05)
- `.planning/handoff/clubcore-auth-runbook.md` — Phase 65 auth runbook (supporting; auth flows used during walkthroughs)

### ⚠ Staleness flag for researcher
- RUN-00 names `.planning/handoff/v1.7-online-payments-runbook.md` and `v1.8-reports-runbook.md`/`v1.9-trainers-runbook.md` as "the 4 runbooks". **`v1.7-online-payments-runbook.md` does NOT exist** — the ЮKassa procedure lives in `v1.7-yookassa-sandbox-evidence/README.md`. This is itself a RUN-00 staleness finding: reconcile the runbook inventory before the live walkthroughs and document the corrected mapping in the evidence file.

### Code anchors (read before planning)
- `apps/backend/docker-compose.yml` — current services: backend, telegram-bot, arq-worker, migrate, postgres:16, redis:7; no `profiles:` key yet (Mailpit adds the first profiled service)
- `apps/backend/app/core/audit.py` — `LOCKED_EMAIL_TEMPLATES` frozenset (source of truth for the 19 templates in RUN-03)
- `apps/backend/app/core/security.py` — cookie/CSRF names (`sz_access`, `sz_refresh`, `sportzal_csrf`) used in walkthrough auth steps

### Pitfalls
- `.planning/research/PITFALLS.md` Pitfall #11 — runbook staleness on first execution (the reason RUN-00 is a gate)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `.planning/milestones/v1.10-OPERATOR-EVIDENCE.md` — exact structural template (frontmatter, Provenance, Index, per-item sections with commands + captured output) for the new v1.11 file.
- `v1.7-*-evidence/README.md` + `v1.6-template-countersign.md` — pre-built operator-capture scaffolds; Phase 67 fills in the captured evidence rather than authoring procedures from scratch.

### Established Patterns
- Append-only milestone evidence files (D-62.1-B2); `N/A-until-production` rows with trigger conditions for credential-gated probes (RUN-08 precedent).
- Atomic-commit-per-plan discipline (Phases 63/64/66); CI tree must stay green at HEAD.

### Integration Points
- `apps/backend/docker-compose.yml` — sole code touch: add profiled `mailpit` service (ports 1025/8025) without disturbing existing 6 services.

</code_context>

<specifics>
## Specific Ideas

- ЮKassa walkthrough's first evidence line MUST be the `YOOKASSA_SANDBOX=true` confirmation (hard pre-flight per Pitfall #11) — non-negotiable ordering.
- Mailpit must be invisible to default `docker compose up` and only appear under `--profile dev` — verify by starting both ways during RUN-06.

</specifics>

<deferred>
## Deferred Ideas

- **SMTP adapter (`aiosmtplib`)** — would activate the Mailpit profile for real local mail interception. Tracked as INFRA-02; explicitly out of v1.11 scope per D-11-MAILPIT-PROFILE.
- **Live RU email deliverability capture** — fires when a production `clubcore.*` domain is provisioned (RUN-02 trigger condition).

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 67-operator-pending-runbook-execution*
*Context gathered: 2026-05-29*
