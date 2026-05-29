# Phase 67: Operator-Pending Runbook Execution - Pattern Map

**Mapped:** 2026-05-29
**Files analyzed:** 5 (1 code modify, 1 evidence-file create, 3 register/evidence captures)
**Analogs found:** 5 / 5

> **Phase type:** execution + evidence, NOT feature-build. The ONLY source-code change is
> adding a `mailpit` service to `apps/backend/docker-compose.yml` under `profiles: ["dev"]`
> (RUN-06). All other artifacts are Markdown evidence/register documents under `.planning/`.
> Analogs for the docs are captured as **structural skeletons to fill**, not code to copy.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `apps/backend/docker-compose.yml` (modify) | config | service-definition | existing `redis` + `backend` services in same file | exact (same file, sibling service) |
| `.planning/milestones/v1.11-OPERATOR-EVIDENCE.md` (create) | evidence-record | append-only-capture | `.planning/milestones/v1.10-OPERATOR-EVIDENCE.md` | exact |
| RUN-01 ЮKassa evidence capture | evidence-capture | credential-gated-transcript | `.planning/handoff/v1.7-yookassa-sandbox-evidence/README.md` | exact (procedure already authored) |
| RUN-02 RU-email evidence capture | evidence-capture | credential-gated-transcript | `.planning/handoff/v1.7-email-deliverability-evidence/README.md` | exact (procedure already authored) |
| RUN-03 19-template countersign register | register | owner-attestation | `.planning/handoff/v1.6-template-countersign.md` | exact (extend 15 → 19) |

> **Planner note (D-67-12 / Claude's Discretion):** RUN-04 (reports runbook walkthrough) and
> RUN-05 (trainers runbook walkthrough) are *live curl-transcript captures* whose output lands
> as `## RUN-04` / `## RUN-05` sections inside `v1.11-OPERATOR-EVIDENCE.md`. They have no
> separate file analog — they follow the per-item section pattern of the v1.10 evidence file
> (see "Shared Patterns → Per-item evidence section"). RUN-00 (staleness audit) produces a
> revision-log + findings written into the same evidence file (no separate analog).

---

## Pattern Assignments

### `apps/backend/docker-compose.yml` — add `mailpit` service (config, RUN-06)

**Analog:** the existing `redis` and `postgres` services in the same file (closest by shape — image-based, ports-only, no build context). Mirror `backend`'s key ordering for the fuller set.

**Schema / `profiles` support — VERIFIED:**
The file has **NO `version:` key** (confirmed via grep — first non-comment line is `services:` at line 4). This is the modern **Compose Spec** schema, which fully supports the top-level / per-service `profiles:` key. `docker compose version` in this env = `v5.1.4`. No `version:` line should be added.
**No existing service uses `profiles:`** — `mailpit` will be the first profiled service (CONTEXT line 79 confirms).

**House style — key ordering** (from `backend` service, lines 5-20): `build`/`image` → `command` → `env_file` → `environment` → `ports` → `volumes` → `depends_on` → `restart`. For an image-only service follow `redis`/`postgres`.

**Indentation** (2-space, services nested 2 levels):
```yaml
services:
  redis:                 # 2 spaces — service key
    image: redis:7       # 4 spaces — service body
    ports:               # 4 spaces
      - "6379:6379"      # 6 spaces — list item, port quoted "host:container"
```

**Ports declaration pattern** (lines 12-13, 72-73, 79-80) — list of quoted `"host:container"` strings:
```yaml
    ports:
      - "8000:8000"
```

**`restart` pattern** (lines 29, 44) — long-running services use `restart: unless-stopped` (used by `telegram-bot`, `arq-worker`; NOT used by `backend`, `postgres`, `redis`). Mailpit is a dev daemon — `restart: unless-stopped` matches the long-running siblings.

**Volumes wiring** (lines 82-83) — top-level `volumes:` block declares named volumes; `postgres-data` is the only one. Mailpit can run with NO persistent volume (in-memory trap is fine for a dev SMTP sink); if persistence is wanted, declare a named volume here mirroring `postgres-data`.

**Networks** — the file declares NO explicit `networks:` block. Compose auto-creates a default network and attaches all services; `mailpit` needs no `networks:` key to be reachable as host `mailpit` by siblings. Do not introduce a networks block.

**Concrete stanza to add** (per D-67-10: image `axllent/mailpit:latest`, SMTP 1025 + UI 8025, `profiles: ["dev"]` only):
```yaml
  mailpit:
    image: axllent/mailpit:latest
    profiles: ["dev"]
    ports:
      - "1025:1025"
      - "8025:8025"
    restart: unless-stopped
```
- `profiles: ["dev"]` keeps it OUT of default `docker compose up`; only `docker compose --profile dev up` starts it (CONTEXT line 108 — must verify both ways during RUN-06).
- No `depends_on` — Mailpit is a standalone SMTP trap with no dependency on `migrate`/`redis`/`postgres`.
- No `env_file`/`environment` needed for the default trap config.
- Place the stanza alongside the other services (before the top-level `volumes:` block at line 82).

**D-67-11 documentation obligation (runbook text, not compose):** the runbook/evidence file must state Mailpit is a dev-only SMTP trap and that the **current email path is Yandex SES-V2 / aioboto3 and is NOT intercepted by Mailpit** — the profile is forward-wiring for a future SMTP adapter (INFRA-02, deferred).

---

### `.planning/milestones/v1.11-OPERATOR-EVIDENCE.md` (evidence-record, create — RUN-07)

**Analog:** `.planning/milestones/v1.10-OPERATOR-EVIDENCE.md` (exact structural template per D-67-02, Claude's Discretion line 49).

**Frontmatter shape** (v1.10 lines 1-13) — mirror with v1.11 values:
```yaml
---
milestone: v1.11
milestone_name: <v1.11 milestone name>
created: 2026-05-29
convention: append-only — RUN-* walkthrough captures append to this file
items:
  - RUN-00-staleness-audit
  - RUN-01-yookassa-sandbox
  - RUN-02-ru-email-deliverability
  - RUN-03-template-countersign
  - RUN-04-reports-runbook
  - RUN-05-trainers-runbook
  - RUN-06-mailpit-profile
decisions_honored:
  - D-11-RUN-AUDIT
  - D-11-MAILPIT-PROFILE
  - D-67-01
  - D-67-02
  - D-67-03
---
```

**Top-level section skeleton** (v1.10 lines 15-31) — `# <title>` → `## Provenance` → `## Index` → per-item `## RUN-XX` sections → `## Operator`:
```markdown
# v1.11 Operator Evidence — <milestone name>

## Provenance
<what requirements this closes (RUN-00..07), which decisions, "No fabricated evidence">

## Index
- [RUN-00-staleness-audit] — status: ...
- [RUN-01-yookassa-sandbox] — status: PASS | N/A-until-production
- ... one line per RUN item with status + capture timestamp
```

**Cross-link obligation (D-67-02):** add a one-line pointer in `v1.10-OPERATOR-EVIDENCE.md` (the "TO BE APPENDED" / append-slot text at v1.10 lines 192-194) redirecting to the new v1.11 file. This is a small edit to the v1.10 file — the only other Markdown touch.

**`N/A-until-production` row format** — see "Shared Patterns → N/A-until-production row" below (copied from v1.10 RUN-08-dns-dkim).

---

### RUN-01 ЮKassa sandbox capture (evidence-capture, credential-gated)

**Analog / procedure source:** `.planning/handoff/v1.7-yookassa-sandbox-evidence/README.md` (procedure already fully authored — Phase 67 *fills evidence*, does not re-author).

**Execute-vs-defer (D-67-04):** attempt the LIVE sandbox sale + refund walkthrough. **Mandatory first evidence line** = `YOOKASSA_SANDBOX=true` confirmation (PITFALLS #11, CONTEXT line 107 — non-negotiable ordering). If sandbox creds unavailable → `N/A-until-production` row with trigger condition; never fabricate.

**Required env preflight** (README lines 31-37): `YOOKASSA_SHOP_ID`, `YOOKASSA_SECRET_KEY` (`test_` prefix), `YOOKASSA_SANDBOX=true`, `YOOKASSA_RETURN_URL`.

**Walkthrough steps to capture** (README lines 50-127): Step 1 configure env → Step 2 sell → Step 3 pay (sandbox card `4111 1111 1111 1111`) → Step 4 `payment.succeeded` webhook lands on `http://localhost:8000/api/v1/_internal/yookassa/webhook` (expect `200 {"status":"ok"}`) → Step 5 `fiscal_receipts` row `kind='payment', status='sent'` → Step 6 refund → Step 7 `refund.succeeded` → second `fiscal_receipts` row `kind='refund', status='sent'`.

**Capture format** (README lines 146-185): YAML artifacts per capture, **redacted** (`pay_***`, `rec_***`, `ref_***`, `***` for PII; never commit `test_`-less live keys per T-53-09). Evidence rows summarised into the `## RUN-01` section of `v1.11-OPERATOR-EVIDENCE.md`.

> **Staleness watch (RUN-00):** README Step 6 uses cookie name `sz_access` (line 117) — confirm still current against `app/core/security.py` (`sz_access`/`sz_refresh`/`sportzal_csrf` per CONTEXT line 81). README Step 5 uses `docker compose exec db psql` (line 96) but the actual compose service is **`postgres`**, not `db` — this is a RUN-00 staleness finding to log inline.

---

### RUN-02 RU email deliverability capture (evidence-capture, credential-gated)

**Analog / procedure source:** `.planning/handoff/v1.7-email-deliverability-evidence/README.md` (procedure already authored).

**Execute-vs-defer (D-67-05):** **default to `N/A-until-production`** — no production `clubcore.*` domain provisioned, so the live `Authentication-Results` probe (yandex.ru + mail.ru + rambler.ru) cannot run. Document exact trigger condition (matches v1.10 RUN-08 precedent).

**Procedure (for reference / trigger doc)** (README lines 41-129): run `uv run python -m scripts.verify.v1_6_email_probe` with `PROBE_YANDEX_TO` / `PROBE_MAIL_TO` / `PROBE_RAMBLER_TO` + Yandex Postbox SES-V2 creds; capture `Authentication-Results` (`spf=pass`/`dkim=pass`/`dmarc=pass`) per provider, redacted (`***@yandex.ru`).

**Capture format** (README lines 86-129): one YAML per provider.

> **Staleness watch (RUN-00):** README references `EMAIL_FROM_DOMAIN=mail.sportzal.ru` (lines 32, 51) — a `sportzal` brand leftover to flag (CONTEXT line 38 / D-67-09). Document as a structural-staleness note in the evidence file; do NOT rewrite the runbook (D-67-09).

---

### RUN-03 19-template owner countersign register (register, owner-attestation)

**Analog:** `.planning/handoff/v1.6-template-countersign.md` (extend the 15-template pattern to all 19 per D-67-06).

**Execute-vs-defer (D-67-06):** owner-actionable **PASS**, not credential-gated. Owner performs the visual check across all 19 LOCKED templates. Capture per-template PASS/FAIL. **Visual check only — no template content edits** (analog lines 23-26).

**Source of truth — VERIFIED:** `apps/backend/app/core/audit.py` `LOCKED_EMAIL_TEMPLATES` frozenset (lines 436-465) = **19 identifiers** = 15 v1.6 + 4 Phase 52 (v1.7). The v1.6 analog deliberately *excluded* the 4 Phase 52 additions; Phase 67 RUN-03 **includes all 19**. The 4 to add to the analog's 15-row register:
- `EMAIL_ONLINE_PAYMENT_SUCCEEDED`
- `EMAIL_ONLINE_PAYMENT_REFUNDED`
- `EMAIL_ONLINE_PAYMENT_CANCELED` (owner operator alert)
- `EMAIL_FISCAL_RECEIPT_FAILED` (owner operator alert)

**Register table format** (analog lines 44-80) — grouped by phase, numbered rows:
```markdown
| # | Template Identifier | Module / File | signed_off_at | Notes |
|---|--------------------|---------------|---------------|-------|
| 1 | `EMAIL_OTP_LOGIN` | `app/modules/auth/email_templates.py` | TODO | |
```
- `signed_off_at` starts `TODO`, filled with ISO-8601 UTC on owner sign-off.
- Add a `### Phase 52 — Online payment notifications (NOT-02)` group for rows 16-19.
- Summary block (analog lines 84-89): `Total: 19`, `Signed off: 0 / 19`, `Pending: 19`.

**Module-file column for the 4 new rows:** locate via grep of the identifier under `apps/backend/app/` (templates physically live next to owning module per audit.py docstring lines 471-473; online-payment notifications module).

> **Discretion (CONTEXT line 50):** RUN-03 register may be a new file OR an appended section — planner decides. Recommend a fresh `19-template-countersign` register file extending the v1.6 pattern, summarised into a `## RUN-03` row in the evidence file.

---

## Shared Patterns

### Per-item evidence section (used by RUN-00/01/04/05 captures)
**Source:** `.planning/milestones/v1.10-OPERATOR-EVIDENCE.md` RUN-08-local-db-smoke (lines 33-162)
**Apply to:** every executed walkthrough that produces a transcript (RUN-01 sale/refund, RUN-04 reports curl + CSV, RUN-05 trainers 5-scenario).
Structure per item:
```markdown
## RUN-XX-<slug> (<one-line title>)

### Commands executed
```bash
# Executed: <ISO-8601 UTC timestamp>
<verbatim commands>
```

### stdout/stderr capture
```
<verbatim captured output, EXIT=N markers>
```

### Operator sign-off
Executed: <timestamp>
Operator: andre.shipunov@icloud.com
```
Key conventions observed in v1.10: verbatim command + verbatim output blocks; `EXIT=N` markers; inline deviation notes when reality differs from the plan (e.g. v1.10 lines 89-92, 155 — `subscriptions` vs `memberships` table-name fix). RUN-04 must additionally include CSV-export samples + a **Cyrillic-encoding verification** check (D-67-07).

### `N/A-until-production` row
**Source:** v1.10 RUN-08-dns-dkim-DEFERRED (lines 178-189)
**Apply to:** RUN-02 (default), RUN-01 (fallback if no sandbox creds), and any probe lacking live capability (D-67-03 / D-67-05).
```markdown
## RUN-XX-<slug>-DEFERRED (N/A-until-production)

**Status:** N/A-until-production
**Reason:** <why the live capture cannot run now>
**Trigger condition:** <exact condition that fires the capture — e.g. "production clubcore.* domain provisioned AND CLUBCORE_EMAIL_FROM set">
**Evidence destination:** This file, append-only.
**Status update mechanism:** When the trigger fires, replace `Status: N/A-until-production` with `Status: CAPTURED <date>` and inline the captured evidence.
```

### No-fabrication / append-only convention
**Source:** v1.10 Provenance + frontmatter `convention: append-only` (lines 5, 21-23); precedent `RUN-08-dns-dkim-DEFERRED`.
**Apply to:** the whole v1.11 evidence file (D-67-03). Real transcripts only; absent capability → explicit deferral row. The append-only *spirit* is honored within the v1.11 file (D-67-01).

### Scaffolding-vs-operator split (already present in analogs)
**Source:** "Scaffolding Attestation" footers in all three handoff analogs (yookassa README lines 208-222, email README lines 149-161, countersign lines 105-121).
The procedures are already authored. Phase 67 deposits evidence/sign-offs into the existing scaffolds rather than re-writing procedure text (CONTEXT lines 92-93, D-67-09 "do not rewrite runbooks").

---

## No Analog Found

None. Every file maps to an existing analog. RUN-04 / RUN-05 walkthrough transcripts and the RUN-00 staleness-audit findings have no dedicated *file* analog but follow the v1.10 per-item evidence-section pattern (Shared Patterns above).

## Metadata

**Analog search scope:** `apps/backend/docker-compose.yml`, `.planning/milestones/`, `.planning/handoff/`, `apps/backend/app/core/audit.py`
**Files scanned:** 5 read in full + 1 targeted grep (audit.py frozenset) + compose schema/profiles verification
**Pattern extraction date:** 2026-05-29
**Verified facts:** (1) compose file has no `version:` key → modern Compose Spec → `profiles:` supported; (2) `LOCKED_EMAIL_TEMPLATES` = exactly 19 identifiers (15 v1.6 + 4 Phase 52); (3) no existing service uses `profiles:` — mailpit is the first.
