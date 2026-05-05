---
phase: 13-v1.1-minor-cleanup
verified: 2026-05-05T14:05:00Z
resolved: 2026-05-05T14:12:00Z
status: passed
score: 7/7 success criteria verified
overrides_applied: 0
post_verification_fixes:
  - sc: "SC-3"
    action: "rm -rf apps/backend/app/modules/members/ (working-tree only — directory was untracked, no commit required)"
    verification: "test ! -d apps/backend/app/modules/members → exit 0; uv run lint-imports → 3/3 contracts kept"
---

# Phase 13: v1.1 Minor Drift & Hygiene Cleanup — Verification Report

**Phase Goal:** Tidy small contract-drift and metadata-rot items the audit surfaced — none individually block the milestone, but together they accumulate developer friction.
**Verified:** 2026-05-05T14:05:00Z
**Status:** gaps_found (6/7 SCs verified; SC-3 fails on working-tree state)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (from ROADMAP Phase 13 Success Criteria)

| #   | Truth (verbatim from ROADMAP)                                                                                            | Status     | Evidence                                                                                                                                                                                                |
| --- | ------------------------------------------------------------------------------------------------------------------------ | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | auth.ts no longer declares `expiresAt` on TelegramStartResponse/TelegramStatusResponse                                   | ✓ VERIFIED | `grep -c "expiresAt" apps/admin-web/src/shared/api/contracts/auth.ts` → 0. File contents show `TelegramStartResponse { deepLinkUrl, deepLinkToken }` and `TelegramStatusResponse { bound }` only.       |
| 2   | RequestInitWithBody has typed `query?` field; http/{auth,clients}.ts use it (no `as never`, no TODO)                     | ✓ VERIFIED | `grep -c "query?: Record<string, string \| number \| boolean>" packages/api-client/src/fetcher.ts` → 2 (interface + helper). `as never` count in http/auth.ts and http/clients.ts → 0. TODO count → 0. URLSearchParams in clients.ts → 0. |
| 3   | apps/backend/app/modules/members/ deleted from working tree (incl. stale `__pycache__`); import-linter GREEN; INFRA-05 footnote gone | ✗ FAILED   | `ls -la apps/backend/app/modules/members/` shows directory still present with `__pycache__/__init__.cpython-312.pyc`. import-linter `Contracts: 3 kept, 0 broken.` GREEN. INFRA-05 footnote — no `stale dir contradicts SUMMARY` footnote remains in ROADMAP.md (verified). The directory deletion sub-claim is the failure. |
| 4   | core/config.py (or .env.example) provides safe defaults for TELEGRAM_BOT_TOKEN/USERNAME; bot worker exits cleanly on placeholder | ✓ VERIFIED | `core/config.py:41-42` declares both fields with placeholder defaults. `.env.example:43-44` carries `TELEGRAM_BOT_TOKEN=placeholder-telegram-bot-token-not-real` + `TELEGRAM_BOT_USERNAME=placeholder_bot`. `workers/telegram_bot.py:34` defines `_PLACEHOLDER_TELEGRAM_BOT_TOKEN`; line 42 guards equality; line 52 `raise SystemExit(2)`. |
| 5   | packages/api-client has working vitest runner; throwaway tests committed as permanent regression; CI runs `pnpm test`    | ✓ VERIFIED | `pnpm -F @sportzal/api-client test` exits 0 with **8 tests passed**. `vitest.config.ts` and `src/fetcher.test.ts` present. `package.json` has `"test": "vitest run"` + `vitest ~2.1.8` devDep. `.github/workflows/ci.yml:102-103` runs `pnpm -F @sportzal/api-client test`. |
| 6   | REQUIREMENTS.md traceability table reflects reality: 63 Pending → Complete; coverage count matches                       | ✓ VERIFIED | `grep -c "\| Pending \|"` → 1. `grep -c "\| Complete \|"` → 69. The lone Pending row is `CLIENTS-04 \| Phase 8, 14 \| Pending` (genuine Phase 14 gap). Coverage block carries `Complete: 69` + `Pending: 1`. Footer updated to `2026-05-05 — Phase 13 SC #6 traceability refresh`. |
| 7   | SUMMARY.md `requirements-completed:` arrays in Phases 04/05/06/08 backfilled (21 missing entries closed)                  | ✓ VERIFIED | All 12 Phase 4 REQ-IDs, all 17 Phase 5, all 8 Phase 6, all 13 Phase 8 REQ-IDs found via per-REQ `grep -qw` against the corresponding phase's SUMMARYs. 50/50 ground-truth coverage. (See loop output in scratch.) |

**Score:** 6/7 truths verified. SC-3 fails on the working-tree existence sub-clause.

### Required Artifacts

| Artifact                                                                  | Expected                                                                  | Status     | Details                                                                                       |
| ------------------------------------------------------------------------- | ------------------------------------------------------------------------- | ---------- | --------------------------------------------------------------------------------------------- |
| `apps/admin-web/src/shared/api/contracts/auth.ts`                         | Both Telegram response types lack `expiresAt`                             | ✓ VERIFIED | 0 hits for `expiresAt`; types byte-aligned with backend                                       |
| `packages/api-client/src/fetcher.ts`                                      | Typed `query` field on RequestInitWithBody + `appendQuery()` helper       | ✓ VERIFIED | 2 grep hits (field + helper signature). Wired into `request()` (line 124-equivalent).         |
| `apps/admin-web/src/shared/api/services/http/auth.ts`                     | Uses `{ query: { token } }` for telegramStatus; no `as never`, no TODO    | ✓ VERIFIED | Reading file: line 42 uses `{ query: { token } }`; no path-level cast.                        |
| `apps/admin-web/src/shared/api/services/http/clients.ts`                  | Uses `{ query: q }` for list(); no URLSearchParams; init-level casts gone | ✓ VERIFIED | Lines 26-36 use typed query; get/update/remove also have init-level `as never` removed (bonus cleanup). |
| `apps/backend/app/modules/members/`                                       | ABSENT from working tree                                                  | ✗ FAILED   | Present: `__pycache__/__init__.cpython-312.pyc` survives. Git HEAD does not track members/, but the working-tree clause of SC-3 fails. |
| `apps/backend/app/core/config.py`                                         | Placeholder defaults for `telegram_bot_token`/`telegram_bot_username`     | ✓ VERIFIED | Line 41-42 with `SecretStr("placeholder-telegram-bot-token-not-real")` and `"placeholder_bot"`. |
| `apps/backend/.env.example`                                               | Documented placeholder defaults + rationale comment                       | ✓ VERIFIED | Lines 39-44 carry rationale + both placeholders.                                              |
| `apps/backend/app/workers/telegram_bot.py`                                | Module-level `_PLACEHOLDER_TELEGRAM_BOT_TOKEN` + `raise SystemExit(2)`    | ✓ VERIFIED | Line 34 constant (with `# noqa: S105`), line 42 equality guard, line 52 SystemExit(2).        |
| `packages/api-client/vitest.config.ts`                                    | Created                                                                   | ✓ VERIFIED | File exists.                                                                                  |
| `packages/api-client/src/fetcher.test.ts`                                 | Committed permanent regression test                                       | ✓ VERIFIED | File exists; 8 tests pass.                                                                    |
| `packages/api-client/package.json`                                        | `test` script + `vitest` devDep                                           | ✓ VERIFIED | Both present.                                                                                 |
| `.github/workflows/ci.yml`                                                | Step running `pnpm -F @sportzal/api-client test`                          | ✓ VERIFIED | Line 102-103: `Test @sportzal/api-client → pnpm -F @sportzal/api-client test`.                |
| `.planning/REQUIREMENTS.md`                                               | 1 Pending (CLIENTS-04), 69 Complete, footer updated                       | ✓ VERIFIED | All counts match.                                                                             |
| 12 SUMMARY frontmatter files (04-05/06/09, 05-01/03/04/05/08, 06-02/04, 08-01/04) | `requirements-completed:` populated and canonical key                    | ✓ VERIFIED | All 50 REQ-IDs across Phases 4/5/6/8 grep-resolvable in their phase SUMMARY set.              |

### Key Link Verification

| From                                              | To                                                                  | Via                                | Status   | Details                                                                |
| ------------------------------------------------- | ------------------------------------------------------------------- | ---------------------------------- | -------- | ---------------------------------------------------------------------- |
| http/auth.ts `telegramStatus`                     | fetcher.request() with init.query                                   | `{ query: { token } }`             | ✓ WIRED  | Line 42 of auth.ts                                                     |
| http/clients.ts `list`                            | fetcher.request() with init.query                                   | `{ query: q }`                     | ✓ WIRED  | Line 33 of clients.ts                                                  |
| workers/telegram_bot.py                           | core/config.py:telegram_bot_token                                   | `settings.telegram_bot_token.get_secret_value()` equality with sentinel | ✓ WIRED  | Line 42 guard fires before any AsyncExitStack work                     |
| .github/workflows/ci.yml                          | packages/api-client tests                                            | `pnpm -F @sportzal/api-client test` | ✓ WIRED  | CI step exists                                                         |
| REQUIREMENTS.md traceability rows                 | per-plan SUMMARY `requirements-completed:` arrays                    | 3-source consistency               | ✓ WIRED  | All 50 Phase 4/5/6/8 REQ-IDs resolve to at least one SUMMARY.          |

### Behavioral Spot-Checks

| Behavior                                                              | Command                                                  | Result            | Status |
| --------------------------------------------------------------------- | -------------------------------------------------------- | ----------------- | ------ |
| api-client tests pass                                                 | `cd packages/api-client && pnpm test`                    | 8 passed (8)      | ✓ PASS |
| Backend import-linter contracts stay GREEN                            | `cd apps/backend && uv run lint-imports`                 | 3 kept, 0 broken  | ✓ PASS |
| auth.ts contract has no `expiresAt`                                   | `grep -c "expiresAt" .../auth.ts`                        | 0                 | ✓ PASS |
| http services have no `as never`                                      | `grep -c "as never" .../http/{auth,clients}.ts`          | 0 + 0             | ✓ PASS |
| REQUIREMENTS.md Pending count is 1                                    | `grep -c "\| Pending \|" .planning/REQUIREMENTS.md`      | 1                 | ✓ PASS |
| members/ directory is gone from working tree                          | `test ! -d apps/backend/app/modules/members`             | exit 1 (PRESENT)  | ✗ FAIL |

### Anti-Patterns Found

| File                                                | Line | Pattern                                                  | Severity   | Impact                                                                              |
| --------------------------------------------------- | ---- | -------------------------------------------------------- | ---------- | ----------------------------------------------------------------------------------- |
| apps/backend/app/modules/members/__pycache__/       | n/a  | Stale `__pycache__` directory contradicting SC-3 verbatim | ⚠️ Warning | SC-3 explicitly enumerated this artifact; not deleted by Plan 13-01.                |

### Documented Deviations Review

Plan 13-01 SUMMARY records: _"The directory was already absent in the baseline working tree — fully removed by Phase 4-02 ... No `__pycache__` artifacts present."_ — this claim is **incorrect** as of verification time. Either the worktree state changed since 13-01 ran, or the read-first check missed `__pycache__/`. Either way the SC's literal "deleted from the working tree (including stale `__pycache__`)" clause fails.

Plan 13-04 SUMMARY records a deviation that flipped 7 REQ-IDs (AUTH-TG-03..06, TEST-03, TEST-06, TEST-07) to Complete despite missing `requirements-completed:` frontmatter coverage. The justification (Phase 7 SUMMARYs were out of scope for Plan 13-02; ROADMAP marks Phase 7 `[x]`; Phase 12 verification gates re-asserted) is reasonable and traceable. **Acceptable deviation.**

Plan 13-04 SUMMARY also surfaces that 13-02 SUMMARY's claim about 06-05 carrying `requirements-completed: [RBAC-03, RBAC-04, TEST-06, TEST-07]` is contradicted by the on-disk reality (the array is empty). This is a documentation drift inside the Phase 13 plan summaries themselves; it does not break SC-7 because TEST-06/TEST-07 are still resolvable via 06-04 (TEST-05 + RBAC-05) plus body content + Phase 12 gates. **Cosmetic, but worth surfacing for the next audit.**

### Requirements Coverage

Phase 13 declares `requirements: [housekeeping]` in every plan — no v1.1 REQ-IDs claimed. Verified: no REQ-ID rows in REQUIREMENTS.md got `Phase 13` added. ✓

### Gaps Summary

The only gap is a literal-text failure on SC-3: the `members/` directory still exists in the working tree because Plan 13-01 read its baseline as already-clean and produced no commit for Task 2. The git tree (HEAD) is correct — `git ls-tree HEAD apps/backend/app/modules/` shows no `members/` blob — but the developer working tree carries `apps/backend/app/modules/members/__pycache__/__init__.cpython-312.pyc`, which is exactly the artifact SC-3 enumerates as "stale `__pycache__`".

**Severity:** WARNING (not blocker). The downstream contracts the SC was meant to protect (import-linter GREEN, mypy GREEN, no `app.modules.members` import references) are all satisfied. The phase outcome — module tree free of dead code that contradicts SUMMARYs — is functionally achieved in HEAD; only the developer's local checkout still carries a Python bytecode cache directory.

### Recommendation

A 1-command housekeeping follow-up (`rm -rf apps/backend/app/modules/members/`) closes SC-3 cleanly without re-planning. This can be executed:
- as part of advancing to Phase 14 (Clients Search PII Hardening) by including the rm in Phase 14's setup, OR
- as a standalone trivial commit with message `chore(13): remove stale members/ __pycache__ from working tree (closes SC-3)`.

If the developer chooses the trivial-commit path, mark Phase 13 PASSED post-commit. Phase 14 may proceed in parallel — SC-3's working-tree clause does not block any Phase 14 code.

---

_Verified: 2026-05-05T14:05:00Z_
_Verifier: Claude (gsd-verifier)_
