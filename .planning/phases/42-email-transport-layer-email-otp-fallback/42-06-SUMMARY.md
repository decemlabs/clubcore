---
phase: 42-email-transport-layer-email-otp-fallback
plan: 06
subsystem: infra/dns
tags:
  - infra
  - dns
  - operator-runbook
  - email
requires:
  - EMAIL-05
provides:
  - dns-runbook-sportzal-ru
affects:
  - apps/backend/infra/dns/sportzal.ru.zone
tech-stack:
  added:
    - "BIND zone-file syntax (first DNS artifact in repo)"
  patterns:
    - "operator-runbook discipline (file committed, applied manually at registrar)"
key-files:
  created:
    - apps/backend/infra/dns/sportzal.ru.zone
  modified: []
decisions:
  - "Placed runbook under apps/backend/infra/dns/ (per plan frontmatter files_modified)"
  - "DKIM record uses literal placeholder <2048-bit-public-key-placeholder> — real key issued by Postbox console at domain verification, never committed"
  - "DMARC baseline p=none with rua=mailto:dmarc-reports@sportzal.ru — quarantine flip is operator-action after 7 clean-report days"
metrics:
  duration: "~5 min"
  completed: "2026-05-19"
  tasks_completed: 1
  files_created: 1
---

# Phase 42 Plan 06: DNS Zone Runbook Summary

DNS operator-runbook artifact landed at `apps/backend/infra/dns/sportzal.ru.zone` documenting SPF + DKIM + DMARC records for `mail.sportzal.ru` per D-42-09..12 + EMAIL-05; file is committed alongside backend code so the Phase 42 gate cannot land without the DNS spec, but CI never executes it — the owner applies records manually at the registrar (Reg.ru).

## What Was Built

Single BIND-syntax zone file with the locked Phase 42 record set:

- **SPF**: `mail.sportzal.ru.   TXT   "v=spf1 include:_spf.yandexcloud.net -all"` — Yandex Cloud Postbox include macro (D-42-11).
- **DKIM**: `sport1._domainkey.mail.sportzal.ru.   TXT   "v=DKIM1; k=rsa; p=<2048-bit-public-key-placeholder>"` — selector locked; public-key value is rendered into the placeholder at owner-apply time from the Postbox console output. Private key stays in the Postbox tenant.
- **DMARC**: `_dmarc.mail.sportzal.ru.   TXT   "v=DMARC1; p=none; rua=mailto:dmarc-reports@sportzal.ru; pct=100"` — monitoring baseline (D-42-11).
- **Header** explicitly states: (a) the file is NOT executed by CI; (b) DKIM PRIVATE KEY MUST NOT APPEAR in this file; (c) DMARC ladder is p=none → p=quarantine (operator-action after 7 clean-report days) → p=reject (deferred to v1.7); (d) `mail.sportzal.ru` is the single dedicated subdomain per D-42-09 (future `mktg.sportzal.ru` lives separately for reputation isolation).

## File Path Decision

The plan offered two candidate locations: `apps/backend/infra/dns/sportzal.ru.zone` (per the `files_modified` frontmatter field) or `infra/dns/sportzal.ru.zone` (per CONTEXT.md / PATTERNS.md prose, which use a top-level `infra/` path).

**Chosen: `apps/backend/infra/dns/sportzal.ru.zone`** — rationale:

1. The plan frontmatter `files_modified` is the authoritative single source for the file location contract.
2. Backend is the owner of the outbound email module; the runbook lives with its owning module under `apps/backend/`, mirroring the per-domain ownership discipline used for templates (D-41-11) and the modular-monolith layout convention.
3. Phase 46 VER-12 deliverability probe (live-stack evidence) will consume these records against `yandex.ru` + `mail.ru` + `rambler.ru` recipients and is operated from the backend module surface.

The top-level `infra/` directory (with `docker/` and `nginx/` siblings) is reserved for cross-app deployment infrastructure; DNS for the outbound-email subdomain is a backend-owned concern in this layout.

## Tasks Completed

| Task | Name                                       | Commit  | Files                                          |
| ---- | ------------------------------------------ | ------- | ---------------------------------------------- |
| 1    | Create infra/dns/sportzal.ru.zone runbook  | 708daca | apps/backend/infra/dns/sportzal.ru.zone        |

## Verification

Plan's `<verify><automated>` gate executed and passed (OK). Asserted:

- File exists at one of the two permitted paths.
- Contains `v=spf1 include:_spf.yandexcloud.net`.
- Contains `_dmarc.mail.sportzal.ru` with `p=none` and `rua=mailto:dmarc-reports@sportzal.ru`.
- Contains DKIM record line for `sport1._domainkey.mail.sportzal.ru`.
- Header contains `DKIM PRIVATE KEY MUST NOT APPEAR`.
- No base64-looking string of 100+ chars after `p=` (sanity check against accidental real-key commit).

## Threat-Model Compliance

| Threat ID    | Disposition | Status                                                                                                                                                                                                                  |
| ------------ | ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| T-42-06-01   | mitigate    | DONE — header documents Postbox-tenant private-key sourcing; literal placeholder `<2048-bit-public-key-placeholder>` makes any accidental real-key commit visually obvious during PR review.                            |
| T-42-06-02   | accept      | DONE — p=none documented as monitoring baseline per D-42-11; quarantine flip noted as operator-action (out of code scope).                                                                                              |
| T-42-06-03   | mitigate    | DONE — change is single small text artifact, trivially reviewable; operator-apply gate at registrar means silent push to production DNS is impossible.                                                                  |

## Deviations from Plan

None — plan executed exactly as written. The path-selection branch in the plan was resolved per `files_modified` frontmatter (apps/backend/infra/dns/).

## Downstream Reminders

- **Phase 46 VER-12 deliverability probe** will exercise these records live against `yandex.ru` + `mail.ru` + `rambler.ru` recipients. The probe consumes the zone file as live-stack evidence; do not move the path without updating VER-12.
- **DMARC ladder progression is operator-action, not code.** After 7 clean-report days the owner flips `p=none` → `p=quarantine` at the registrar; `p=reject` is explicitly deferred to v1.7. Phase 42 ships only the p=none baseline.
- **DKIM public-key insertion is an apply-time step.** Before owner-apply at the registrar, the owner triggers domain verification in the Yandex Cloud Postbox console, copies the rendered public-key value, and substitutes for `<2048-bit-public-key-placeholder>` when pasting into Reg.ru. The private key remains in the Postbox tenant and must never appear in this repo.
- **Future subdomains (e.g. `mktg.sportzal.ru` marketing)** go on a separate subdomain per D-42-09 — extend this zone file, do not collapse them onto `mail.sportzal.ru`.

## Self-Check

- File present: `apps/backend/infra/dns/sportzal.ru.zone` — FOUND
- Commit `708daca` — FOUND
- Plan automated verification gate — PASSED (OK)

## Self-Check: PASSED
