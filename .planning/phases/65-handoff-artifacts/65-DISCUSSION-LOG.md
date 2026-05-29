# Phase 65: Handoff Artifacts - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-29
**Phase:** 65-handoff-artifacts
**Mode:** `--auto` (all gray areas auto-resolved with recommended defaults; no interactive prompts)
**Areas discussed:** Postman generation+augmentation pipeline, Newman smoke credentials/seed, Newman smoke scope, Auth runbook structure+language, Tooling entry point, Doc-site privacy enforcement

---

## Postman generation + augmentation pipeline (HND-01/02/03)

| Option | Description | Selected |
|--------|-------------|----------|
| `openapi-to-postmanv2@6.0.1` base + committed Node augment script | Generate with the HND-01-pinned npm tool (native `folderStrategy=Tags`); inject auth/CSRF scripts + assertions via a re-runnable Node script | ✓ |
| Extend existing stdlib `export_postman.py` (Phase 46) | Reuse the Python generator that produced v1.6-postman.json | |
| Generate once, hand-edit the JSON | Simplest, but not regenerate-safe | |

**Choice:** npm tool + scriptable augmentation (D-65-GEN-NPM, D-65-AUGMENT).
**Notes:** HND-01 pins the tool by name/version. The frozen spec still drifts (Phase 66 IdempotencyKey param); hand-edits would be lost. Reuse `export_postman.py`'s `_internal`-tag exclusion so webhooks don't leak.

---

## Newman smoke credentials / seed (HND-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Seeded fixture email committed, password via `--env-var` at runtime | `verify_owner@local.dev` from `seed_verification_fixtures.py`; password from `SEED_VERIFY_OWNER_PASSWORD` | ✓ |
| Commit a full dev credential | Simpler but violates "no real credentials committed" | |
| Operator passes all login vars at runtime | Most explicit, least convenient | |

**Choice:** fixture email committed, password runtime-sourced (D-65-NEWMAN-CREDS).
**Notes:** Mirrors the existing seed script's env-sourced-password discipline. Newman env file is separate from the placeholder-only Postman GUI environment.

---

## Newman smoke scope (HND-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Curated happy-path subset | login → CSRF → 1 safe request/domain → idempotency replay; excludes destructive/financial mutations | ✓ |
| Run the entire collection | Full surface; fails on missing fixtures against a bare compose DB | |

**Choice:** curated subset (D-65-SMOKE-SCOPE).
**Notes:** "Smoke" = auth + CSRF + representative reachability. `--bail` then gates on real breakage, not fixture gaps. Documented coverage, no silent truncation.

---

## Auth runbook structure + language (HND-05)

| Option | Description | Selected |
|--------|-------------|----------|
| Extend v1.4 structure, RU prose + EN commands | Follow `v1.4-auth-runbook.md` precedent under clubcore name; add Idempotency-Key + sportzal_csrf sections | ✓ |
| New from-scratch structure | More design freedom, breaks precedent continuity | |

**Choice:** extend v1.4 precedent (D-65-RUNBOOK-EXTEND).
**Notes:** HND-05 says "extends v1.4 precedent". Sections: login → refresh → CSRF → Telegram OTP → email OTP → logout-all → Idempotency-Key (new) → sportzal_csrf carry-over. Curl paired with Postman request IDs.

---

## Tooling entry point (HND-04/06)

| Option | Description | Selected |
|--------|-------------|----------|
| Private repo-root `package.json` | Holds `docs` + `newman` scripts + handoff devDeps; `pnpm docs`/`pnpm newman run` resolve at root | ✓ |
| Add `tools/*` to workspace globs + `tools/newman` package | Workspace package; doesn't give root-level `pnpm docs` cleanly | |

**Choice:** private root package.json (D-65-ROOT-PKG).
**Notes:** No root package.json exists today; `tools/` is outside workspace globs. Root pkg matches the literal `pnpm docs`/`pnpm newman run` phrasing and is the conventional pnpm-workspace root.

---

## Doc-site privacy enforcement (HND-06)

| Option | Description | Selected |
|--------|-------------|----------|
| `preview-docs` only (port 8080), `.docs-site/` gitignored | Live local server; no static publishable build, no PDF, no deploy path | ✓ |
| `preview-docs` + static `build`/`bundle` step | Convenient offline browsing but creates a publishable artifact | |

**Choice:** preview-docs only (D-65-DOCS-PRIVATE).
**Notes:** D-11-DOCS-PRIVATE — structurally prevent an accidental publish path. `.docs-site/` added to `.gitignore`.

---

## Claude's Discretion

- Smoke subset as a collection folder (`--folder smoke`) vs a separate trimmed collection.
- Augment-script shape (single `.mjs` vs `gen`→`augment` pipeline); scripted vs hand-edited per-domain `pm.test()` bodies (auth/CSRF wiring stays scripted).
- Optional `make docs` alias alongside `pnpm docs`.
- Representative per-domain request chosen for HND-03 assertions and the smoke.

## Deferred Ideas

- Newman as a blocking CI gate → v2.0 (D-11-NEWMAN-LOCAL).
- `sportzal_csrf` → `clubcore_csrf` rename → v2.0 (D-11-CSRF-DEFER).
- Public-hosted API docs → never (D-11-DOCS-PRIVATE).
- Retiring the stdlib `export_postman.py` generator → future cleanup, not this phase.
- Mailpit profile + operator walkthroughs → Phase 67 (RUN-*).
