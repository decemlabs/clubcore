---
phase: 62-clubcore-rebrand
verified: 2026-05-26T00:00:00Z
status: passed
score: 8/8 must-haves verified
overrides_applied: 0
---

# Phase 62: clubcore Rebrand — Verification Report

**Phase Goal:** `sportzal → clubcore` code identifier rename across workspace packages + admin-web localStorage + backend Redis prefixes + operator-tier renames (Postgres DB rename + `CLUBCORE_EMAIL_FROM` env with deprecated-warning fallback + DNS/DKIM checklist + `CLUB_BRAND` constant extraction); smoke gates green; forward-only `.planning/` rewrite preserving historical-immutability boundary.

**Verified:** 2026-05-26
**Status:** PASSED (VERIFIED)
**Re-verification:** No — initial verification

---

## Goal Achievement Summary

| # | Requirement | Status | Evidence |
|---|-------------|--------|----------|
| REB-01 | pnpm packages `@sportzal/*` → `@clubcore/*` (api-client + ui + admin-web app) | VERIFIED | `packages/api-client/package.json`, `packages/ui/package.json`, `apps/admin-web/package.json` (`"name": "clubcore-adminka"`); `pnpm-lock.yaml` regenerated stable; G7-B `pnpm --filter @clubcore/api-client test` 16/16 pass; G7-C `clubcore-adminka` tc/lint/test all clean (282/282 tests). Orchestrator caught and closed 62-01 silent-defer of 12 admin-web/src/* imports via commit `2cc1d690`. |
| REB-02 | localStorage `sportzal:*:v1` → `clubcore:*:v2` (Zustand persist version 1→2 + copy-on-read + delete-old shim) | VERIFIED | `apps/admin-web/src/shared/session/store.ts:5` (`STORAGE_KEY = 'clubcore:session:v2'`, `version: 2`); same shape applied to `uiPrefsStore.ts` + `_db.ts`; `main.tsx` STORE_MIGRATIONS block + theme-bootstrap legacy fallback in `index.html:16`; guard tests `main.migrator.test.ts` + `theme-bootstrap.test.ts` cover shim. |
| REB-03 | Redis prefixes `sz:*` → `cc:*` (idempotency, telegram dedup, yookassa/email circuit breakers, webhook dedup) | VERIFIED | All 5 primary surfaces flipped in single atomic commit `6ec1115b`; 8 additional lockstep docstring updates in `app/*`; 11 test files updated. G7-I `grep -rn '"sz:\\|''sz:' apps/backend/app apps/backend/tests` → 0 matches. Verified independently: `grep -rn 'sz:' apps/backend/app` → 0 matches. |
| REB-04 | env vars without `SPORTZAL_*` prefix; new `CLUBCORE_EMAIL_FROM` with deprecated-warning fallback chain | VERIFIED | `apps/backend/app/core/config.py:128-159` — `clubcore_email_from` (canonical) + `sportzal_email_from` (legacy, structlog warning emit) + hardcoded default `"noreply@mail.sportzal.ru"` per D-62-03; `.env.example:5-7` documents the env. Removal tagged with `TODO Phase 67 / RUN-07`. |
| REB-05 | Forward-only `.planning/` rewrite + `HISTORICAL_NOTE.md` explaining immutability boundary | VERIFIED | `.planning/HISTORICAL_NOTE.md` exists (28 lines, lists boundary table); `.planning/PROJECT.md`, `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`, `.planning/MILESTONES.md`, `.planning/STATE.md`, `.planning/RETROSPECTIVE.md` all updated. Historical immutability holds (see Anti-Pattern table). |
| REB-06 | `import-linter` + ESLint `no-restricted-paths` updated under new package names | VERIFIED | `apps/admin-web/eslint.config.js:120` lint message updated to `@clubcore/api-client`. `.importlinter` had no `@sportzal/*` refs (Python-side only) — confirmed. G7-D `uv run lint-imports` → 3 kept, 0 broken. Gap-closure commit `c8b9757d` swept residual `apps/admin-web/scripts/eslint.fixtures.config.js:68`. |
| REB-07 | CI workflow + Docker compose under new names | VERIFIED | `.github/workflows/ci.yml` `pnpm -F @clubcore/api-client` invocations renamed (lines 102-106 per 62-01-SUMMARY); `apps/backend/docker-compose.yml` — all 6 sites (4 DATABASE_URL + POSTGRES_DB + healthcheck) flipped to `clubcore`. G7-F `docker compose config` exit 0. |
| REB-08 | backend pytest + admin-web tc/lint/test green; openapi/schema regen byte-stable; CI drift-gate clean | VERIFIED | G7-A: 2185 passed, 6 skipped (≥ 2181 baseline, +4); G7-B: 16/16; G7-C: 282/282 + tc + lint clean; G7-D: 3 kept, 0 broken; G7-E: byte-stable across 3 regens, drift vs HEAD closed by gap-closure commit `c8b9757d`; G7-F: docker compose config exit 0. |

**Score:** 8/8 requirements verified.

---

## Locked-Decision Honor Table (D-62-01 … D-62-11)

| Decision | Honored | Evidence |
|----------|---------|----------|
| D-62-01 / D-10-BRAND-DISTINCTION — `clubcore` = product name, NOT gym brand | YES | `CLUB_BRAND` placeholder retained as `"Sportzal"`; email FROM literal `noreply@mail.sportzal.ru` preserved unchanged. |
| D-62-02 / CLUB_BRAND-EXTRACTION — single source in `app/core/branding.py`, zero behaviour change | YES | `apps/backend/app/core/branding.py` exists (12 lines, `CLUB_BRAND: Final[str] = "Sportzal"`); imported by all 5 email_templates.py modules (auth/users/memberships/bookings/payments). RBAC parity tests + 2185 pytest green confirm zero behaviour change. |
| D-62-03 / CLUBCORE_EMAIL_FROM — env-driven with fallback chain | YES | `app/core/config.py` Settings field + `@model_validator` resolver with structlog deprecated-warning emit on `SPORTZAL_EMAIL_FROM` read; default literal preserved. |
| D-62-04 / DB-RENAME — operator runbook (NOT Alembic) | YES | `.planning/handoff/clubcore-db-rename-runbook.md` exists; `.env.example` + `docker-compose.yml` flipped to `clubcore`. Plan 62-03 SUMMARY documents operator-tier `ALTER DATABASE sportzal RENAME TO clubcore` precedent for the local dev container. |
| D-62-05 / DNS-CHECKLIST — operator runbook only, no domain switch | YES | DNS/DKIM checklist in `clubcore-db-rename-runbook.md`; sending domain `mail.sportzal.ru` not changed in code. |
| D-62-06 / localStorage copy-on-read + delete-old | YES | `main.tsx` STORE_MIGRATIONS + `index.html` legacy fallback; Zustand `version: 1 → 2` + pass-through `migrate` callback in 3 stores. |
| D-62-07 / Redis FLUSHDB at deploy, no runtime fallback | YES | Single atomic commit flip (`6ec1115b`); code reads/writes only `cc:*` (G7-I 0 matches); FLUSHDB step documented in operator runbook. |
| D-62-08 / env vars — REB-04 was a no-op precondition check | YES | Only new env `CLUBCORE_EMAIL_FROM` introduced; `SPORTZAL_EMAIL_FROM` exists solely as deprecated-warning legacy reader. |
| D-62-09 / FORWARD-ONLY — historical phases/audits/v1.4..1.9 handoffs immutable | YES | `git diff 2cc1d690^..HEAD --stat -- .planning/phases/47..61 .planning/audits .planning/handoff/v1.[4-9]-*` returns empty; zero historical artefacts touched within the phase 62 commit range (29 commits). |
| D-62-10 / HISTORICAL_NOTE.md authored | YES | `.planning/HISTORICAL_NOTE.md` committed (28 lines, under-30-line target met); explains immutability boundary + cites D-62-09 / D-10-HISTORY-IMMUTABLE. |
| D-62-11 / ATOMIC-PACKAGE-RENAME — single-commit groups G-1 … G-6 | YES | Each G-N group landed atomically: G-1 = `4493941c`, G-2 = `dd721bac`, G-3 = `6080413d`, G-4 = `5267832f`, G-5 = `531f5932`, G-6 = `fe94e95f`. Smoke runs between waves confirm green at each commit boundary. |

**Decision honor:** 11/11 locked decisions verified.

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/app/core/branding.py` | NEW — `CLUB_BRAND: Final[str] = "Sportzal"` | VERIFIED | File tracked in git; 12 lines; imported by 5 email_templates.py modules. |
| `.planning/HISTORICAL_NOTE.md` | NEW — under 30 lines, immutability boundary | VERIFIED | 28 lines; documents boundary + lineage. |
| `.planning/handoff/clubcore-db-rename-runbook.md` | NEW — operator pg_dump/restore + DNS checklist | VERIFIED | File tracked in git (G7-L pass). |
| `apps/backend/.env.example` | `DATABASE_URL=.../clubcore` + `CLUBCORE_EMAIL_FROM` doc | VERIFIED | Line 2 + lines 5-7. |
| `apps/backend/docker-compose.yml` | 6 sites flipped to `clubcore` | VERIFIED | DATABASE_URL ×4 + POSTGRES_DB + healthcheck all `clubcore`. |
| `apps/admin-web/src/shared/session/store.ts` | `STORAGE_KEY = 'clubcore:session:v2'`, `version: 2` | VERIFIED | Confirmed. |
| `apps/admin-web/src/shared/theme/uiPrefsStore.ts` | renamed + version bump + migrate added | VERIFIED | Per 62-02 SUMMARY. |
| `apps/admin-web/src/shared/api/services/mock/_db.ts` | `clubcore:mock:v2` | VERIFIED | Per 62-02 SUMMARY. |
| `apps/admin-web/index.html` | theme-bootstrap with legacy fallback + RUN-07 TODO | VERIFIED | Line 16 fallback present. |
| `apps/admin-web/src/app/main.tsx` | STORE_MIGRATIONS pre-rehydrate block + RUN-07 TODO | VERIFIED | Line 16 TODO present. |
| `apps/backend/app/core/idempotency.py` | `cc:idem:` prefix | VERIFIED | G7-I 0 `sz:` matches. |
| `apps/backend/app/integrations/telegram/handlers.py` | `cc:bot:update:` | VERIFIED | G7-I 0 `sz:` matches. |
| `apps/backend/app/integrations/yookassa/circuit_breaker.py` | `cc:yookassa:circuit:*` | VERIFIED | G7-I 0 `sz:` matches. |
| `apps/backend/app/integrations/email/circuit_breaker.py` | `cc:email:circuit:*` | VERIFIED | G7-I 0 `sz:` matches. |
| `apps/backend/app/api/v1/_internal/yookassa/router.py` | `cc:yookassa:webhook:` | VERIFIED | G7-I 0 `sz:` matches. |
| `apps/backend/app/core/config.py` | CLUBCORE_EMAIL_FROM resolver + structlog warning | VERIFIED | Lines 122-159. |
| `apps/backend/app/modules/{auth,users,memberships,bookings,payments}/email_templates.py` | import `CLUB_BRAND`; literals interpolated | VERIFIED | All 5 modules import + interpolate. |
| `.github/workflows/ci.yml` | `pnpm -F @clubcore/api-client` filters | VERIFIED | Per 62-01 SUMMARY. |

---

## Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| `email_templates.py` (×5) | `branding.py:CLUB_BRAND` | `from app.core.branding import CLUB_BRAND` + f-string interp | WIRED |
| `Settings` (config.py) | `EmailProviderSettings.from_address` | `@model_validator(mode="after") _resolve_email_from` with object.setattr | WIRED |
| `Settings` legacy fallback | `structlog.get_logger(__name__).warning("env_fallback_used", …)` | direct call in fallback branch | WIRED |
| `main.tsx` STORE_MIGRATIONS | three Zustand stores | pre-rehydrate side effect before `persist.rehydrate()` | WIRED (covered by `main.migrator.test.ts`) |
| `apps/admin-web/package.json` predev | `@clubcore/api-client codegen` | pnpm filter | WIRED |
| `docker-compose.yml` DATABASE_URL | `POSTGRES_DB: clubcore` | 4 services match healthcheck `-d clubcore` | WIRED |
| Smoke gauntlet G7-E regen | committed `openapi.json` + `schema.d.ts` | gap-closure commit `c8b9757d` regenerated 2-line drift | WIRED (drift-gate clean post-closure) |

---

## Anti-Pattern Checks

| Check | Result | Notes |
|-------|--------|-------|
| `@sportzal/` residue in active code | CLEAN | `grep -rln '@sportzal/' apps packages .github --include='*.{ts,tsx,js,json,yml,yaml,py}'` → 0 matches. |
| `sz:` Redis prefix residue | CLEAN | `grep -rn 'sz:' apps/backend/app` → 0 matches; G7-I also 0 in `tests`. |
| `sportzal:*:v1` localStorage outside shim | DOCUMENTED-SHIM-ONLY | Matches confined to `apps/admin-web/src/app/main.tsx` (migrator), `index.html` (bootstrap fallback), `main.migrator.test.ts`, `theme-bootstrap.test.ts` — all tagged with `TODO Phase 67 / RUN-07`. |
| Historical-immutability boundary | HONORED | `git diff` across phase 62 commit range (29 commits) for `.planning/phases/47-61`, `.planning/audits`, `.planning/handoff/v1.[4-9]-*` is empty. |
| Debt markers (TBD/FIXME/XXX) in phase-touched files | CLEAN | `branding.py`, `config.py`, `HISTORICAL_NOTE.md`, `clubcore-db-rename-runbook.md` — no TBD/FIXME/XXX. |
| Unreferenced TODOs in shim code | NONE | All 4 TODO markers reference formal follow-up `Phase 67 / RUN-07`. |
| Silent deferral to non-existent G-N plans | CAUGHT-AND-CLOSED | 62-01 initial executor deferred 12 admin-web/src/* imports under "G-2..G-6"; orchestrator caught the orphan-set and closed via commit `2cc1d690`. Documented in 62-01-SUMMARY § Deviations. No remaining silent deferrals. |
| Drift-gate (OpenAPI + schema.d.ts) | CLEAN | Gap-closure commit `c8b9757d` regenerated stale 2-line pt_packages docstring drift (Phase 62 `sz:idem` → `cc:idem` propagated to openapi.json + schema.d.ts). |

---

## Smoke Baseline Summary

Combined evidence: G7 gauntlet at `fe94e95f` + gap-closure commit `c8b9757d` + orchestrator re-verification.

| Gate | Pre-closure | Post-closure |
|------|-------------|--------------|
| G7-A backend pytest | PASS (2185/6 skipped) | PASS (unchanged) |
| G7-B @clubcore/api-client tc + test | PASS (16/16) | PASS |
| G7-C clubcore-adminka tc + lint + test | PASS (282/282) | PASS |
| G7-D import-linter | PASS (3 kept, 0 broken) | PASS |
| G7-E OpenAPI regen drift-gate | FAIL (byte-stable; 2-line drift vs HEAD) | PASS (drift closed; openapi.json + schema.d.ts regen committed) |
| G7-F docker compose config | PASS (exit 0) | PASS |
| G7-G RBAC parity no-edit guard | PASS (permissions.py / can.ts / registry.ts unchanged) | PASS |
| G7-H residual @sportzal | FAIL (2 real misses: api-client/src/index.ts JSDoc + admin-web/scripts/eslint.fixtures.config.js) | PASS (both swept in `c8b9757d`) |
| G7-I residual sz: Redis prefix | PASS (0) | PASS |
| G7-J Phase 67 / RUN-07 shim sites | PASS (4 annotations / 3 documented sites) | PASS |
| G7-K HISTORICAL_NOTE.md | PASS (exists) | PASS |
| G7-L clubcore-db-rename-runbook.md | PASS (exists) | PASS |

**Overall smoke verdict (post-closure):** 12/12 gates PASS.

---

## Notable Observations

1. **62-01 orphan-defer defect — CAUGHT + CLOSED.** Initial executor of plan 62-01 followed a Task 2 STOP directive and left 12 `apps/admin-web/src/*` files still importing `@sportzal/api-client`. The deferral was rationalised as "downstream plans G-2..G-6 will handle it" — but the orchestrator confirmed no downstream plan owned that surface (62-PATTERNS.md G-1..G-6 tables did not enumerate the imports; `files_modified` of plans 62-02..07 did not include them). This is a classic silent-deferral anti-pattern; mitigated by orchestrator commit `2cc1d690` (mechanical rename) and documented in 62-01-SUMMARY § Deviations. This is the kind of defect goal-backward verification is designed to catch — and it WAS caught at the orchestrator boundary, not at goal verification. Honored.

2. **62-03 dev-DB cwd / infra-drift incident.** The executor of plan 62-03 ran pytest against a local Postgres container that still held a stale `sportzal` database (D-62-04 operator rename had been applied in code but not on the dev container). Mitigation: `ALTER DATABASE sportzal RENAME TO clubcore` performed as out-of-scope infra step; documented in 62-03-SUMMARY § Deviations. No application code touched. This is a dev-infra concern, not a code-correctness concern, and does not affect any of REB-01..08 evidence.

3. **62-07 smoke gauntlet correctly surfaced 2 gates as FAIL.** Per the executor's scope-boundary rule ("if any gate fails, the plan FAILS — do NOT silently fix; report and let gap-closure handle it"), the smoke executor did not auto-fix G7-E and G7-H. The orchestrator correctly created the gap-closure commit `c8b9757d` (4 lines across 4 files). Re-verification confirmed clean. This is healthy executor/orchestrator separation.

4. **`mail.sportzal.ru` email FROM default preserved.** Per D-62-01 and CONTEXT specifics line 172, the hardcoded fallback default literal `"noreply@mail.sportzal.ru"` was deliberately NOT switched to `mail.clubcore.ru`. Switching would have silently broken email delivery on greenfield deployments where DNS for the new domain is not yet configured. Operator-controlled domain migration is a future phase concern. Verified preserved across all 5 email_templates.py modules.

5. **Test-fixture `*.sportzal.local` retention is intentional.** 14 of 16 `@sportzal` matches in G7-H were `owner@sportzal.local` / `operator@sportzal.local` test placeholders in `tests/unit/test_actor_context.py` and `app/core/audit.py:536` docstring. These are deliberately retained per D-62-03 — the `sportzal` domain is the historical brand identifier used in test data, distinct from the product-name rename. G7-H FAIL was on the 2 npm-scope misses only; intent-aware verdict was PARTIAL, and the strict verdict was closed via gap-closure.

6. **CLUB_BRAND value preserved as `"Sportzal"` placeholder.** Pure refactor — zero behaviour change. Confirmed by 2185 pytest passing (≥ 2181 baseline + 4) and the locked-template AST gate not tripping. Per-club configurable branding remains deferred to a future phase.

---

## Human Verification

None required. All 8 requirements have observable, programmatically-verified evidence in the codebase tip and the post-closure smoke gauntlet is 12/12 PASS.

---

## Recommendation

**Phase 62 is COMPLETE and ready for milestone close (v1.10).**

All 8 REB requirements verified. All 11 locked decisions (D-62-01..11) honored. Historical immutability boundary preserved. Smoke gauntlet 12/12 green after gap-closure. No blockers, no unreferenced debt markers, no orphaned requirements.

Recommended next step: `/gsd:complete-milestone v1.10` to close v1.10 and open v1.11 (Phases 63-67) per D-10-SPLIT.

---

*Verified: 2026-05-26*
*Verifier: Claude (gsd-verifier, goal-backward mode)*
