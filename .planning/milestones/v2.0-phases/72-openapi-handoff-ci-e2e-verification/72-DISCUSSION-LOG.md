# Phase 72: OpenAPI Handoff + CI + E2E Verification - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-31
**Phase:** 72-openapi-handoff-ci-e2e-verification
**Areas discussed:** Client tag consolidation, client-pwa CI gate placement, Live E2E walkthrough disposition, v2.0 runbook scope

---

## Client tag consolidation

| Option | Description | Selected |
|--------|-------------|----------|
| Unify under Client-Portal | Re-tag Phase-68 auth/profile 'Client' → 'Client-Portal'; one unified tag; literal HND-01 reading | (default) |
| Keep two tags | Keep 'Client' (auth) + 'Client-Portal' (portal); add 'Client-Portal' to ordered list | |
| You decide | Researcher/planner picks; default unify unless drift-gate risk | ✓ |

**User's choice:** You decide → default **unify under Client-Portal** unless re-tagging risks the v1.11 staff drift gate (D-72-01).
**Notes:** Either way `Client-Portal` must be added to the ordered `OPENAPI_TAGS` list.

## Contract forward-guards (`_v20Checks` scope)

| Option | Description | Selected |
|--------|-------------|----------|
| All v2.0 client paths | Cover auth/profile + portal (~24 ops) in one `_v20Checks` tuple | ✓ |
| Portal paths only | Cover only Phase 69-71 portal ops (~18) | |
| You decide | Planner picks; default all-v2.0 | |

**User's choice:** **All v2.0 client paths** (D-72-02).
**Notes:** Matches HND-02's literal "every client path×method"; follows `_v1xChecks` precedent with runtime `toHaveLength`.

## client-pwa CI gate placement

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated parallel job | New `client-pwa` job, no `needs:`, parallel to backend/frontend/redocly | ✓ |
| Keep -r recursion | Rely on existing `pnpm -r` in frontend job | |
| You decide | Default dedicated job | |

**User's choice:** **Dedicated parallel job** (D-72-03); scope the existing `frontend` `-r` steps so gates don't double-run (D-72-05).

## client-pwa build gate

| Option | Description | Selected |
|--------|-------------|----------|
| Add build gate | Run `vite build` + vite-plugin-pwa SW generation too | ✓ |
| Typecheck/lint/test only | Match criterion #3 exactly, no build | |
| You decide | Default add build | |

**User's choice:** **Add build gate** (D-72-04).
**Notes:** SW/manifest generation is a failure surface not covered by `tsc -b --noEmit`.

## Live E2E walkthrough disposition

| Option | Description | Selected |
|--------|-------------|----------|
| Fully live now — hard gate | Full journey incl. ЮKassa live before close | |
| Automated-verified + operator-pending | Automated truths hard gate; whole walkthrough operator-pending (prior pattern) | |
| Hybrid: live read-path, defer payment | login→home→book→QR→history live now; ЮKassa checkout leg operator-pending | ✓ |

**User's choice:** **Hybrid** (D-72-06).
**Notes:** Read-path is the hard gate with captured evidence; payment leg deferred (needs hosted-page test card + manual webhook).

## E2E read-path seed state

| Option | Description | Selected |
|--------|-------------|----------|
| Seed via dev script | `seed_dev_client` + `seed_demo_data` grant active membership + PT-package | (default) |
| Staff-side grant | Use staff endpoints to sell/activate to dev client | |
| You decide | Default dev seed | ✓ |

**User's choice:** You decide → default **dev seed script** (D-72-07).
**Notes:** No external creds; documented local-stack path; book/QR need an active PT-package normally created by checkout.

## v2.0 runbook scope

| Option | Description | Selected |
|--------|-------------|----------|
| Full client journey + auth | Bilingual, curl + PWA, dev-seed/OTP setup, ЮKassa test-card + webhook procedure | ✓ |
| Lean scenario list | Concise checklist, relies on existing auth-runbook | |
| You decide | Default full depth | |

**User's choice:** **Full client journey + auth** (D-72-09).
**Notes:** Mirrors `clubcore-auth-runbook.md` depth; doubles as the operator execution guide for the deferred checkout leg.

---

## Claude's Discretion

- Final tag scheme (unify vs two-tag), gated on drift-gate safety (D-72-01).
- Exact `_v20Checks` operation enumeration + tuple length (D-72-02).
- The `frontend`-job scoping mechanism that prevents double-run (D-72-05).
- Seed-vs-staff-grant for read-path state, default dev seed (D-72-07).
- Runbook filename/location + evidence-file path.

## Deferred Ideas

- Full live ЮKassa checkout walkthrough — operator-pending, before real handoff.
- Wiring net-new client screens to real backends — future milestone.
- admin-web client-domain wiring — separate/future milestone.
- Pinning `@redocly/cli` to an exact version — future maintenance commit.
