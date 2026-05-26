---
phase: 62-clubcore-rebrand
plan: 05
subsystem: rebrand-operator-tier
tags: [rebrand, operator, postgres, redis, dns, handoff]
requires: [62-01]
provides:
  - postgres-db-identifier-clubcore
  - clubcore-email-from-env-doc
  - operator-cutover-runbook
affects:
  - apps/backend/.env.example
  - apps/backend/docker-compose.yml
  - .planning/handoff/clubcore-db-rename-runbook.md
tech-stack:
  added: []
  patterns: [operator-tier-rename, atomic-lockstep-config, pg_dump-pg_restore-cutover, redis-flushdb-cutover, dns-checklist]
key-files:
  created:
    - .planning/handoff/clubcore-db-rename-runbook.md
  modified:
    - apps/backend/.env.example
    - apps/backend/docker-compose.yml
decisions:
  - "Postgres rename is operator-tier (pg_dump | pg_restore), not Alembic (D-62-04)"
  - "CLUBCORE_EMAIL_FROM env override documented as commented optional with fallback chain (D-62-03)"
  - "Redis FLUSHDB is the cutover model — no runtime dual-read (D-62-07)"
  - "DNS/DKIM/SPF/DMARC checklist is documentation-only; v1.10 does NOT change the sending domain (D-62-05)"
  - "Live cutover execution is operator-pending; evidence lands in v1.11 / Phase 67 / RUN-08"
metrics:
  duration_minutes: ~10
  completed: 2026-05-26
  tasks: 2
  files_created: 1
  files_modified: 2
  commits: 2
---

# Phase 62 Plan 05: Postgres DB Identifier Rename + Operator Runbook — Summary

Renamed the Postgres DB identifier `sportzal → clubcore` across `.env.example`
and `docker-compose.yml` in lockstep (all 6 surface sites in one commit per the
D-62-11 atomic constraint), documented `CLUBCORE_EMAIL_FROM` as a commented
optional override with the legacy fallback chain, and authored the
`.planning/handoff/clubcore-db-rename-runbook.md` operator-cutover runbook
covering pg_dump/restore, Redis FLUSHDB, DNS/DKIM/SPF/DMARC, post-cutover smoke,
and rollback per the §G-5 outline. The runbook is informational only —
Phase 62 does NOT execute the cutover; the operator runs it once at v1.10 deploy.

## Tasks Completed

| Task | Name | Commit | Files |
| --- | --- | --- | --- |
| 1 | Rename Postgres DB identifier across `.env.example` + `docker-compose.yml` (6 lockstep sites) | `6f0854af` | apps/backend/.env.example, apps/backend/docker-compose.yml |
| 2 | Author `clubcore-db-rename-runbook.md` operator cutover runbook | `e6aa7fa8` | .planning/handoff/clubcore-db-rename-runbook.md |

## docker-compose.yml rename sites (6 lockstep)

All flipped in commit `6f0854af` in a single commit per D-62-11 atomic constraint:

| # | Location (post-rename context) | Surface | Before → After |
| --- | --- | --- | --- |
| 1 | `services.backend.environment.DATABASE_URL` | DATABASE_URL | `postgresql+asyncpg://app:app@postgres:5432/sportzal` → `.../clubcore` |
| 2 | `services.telegram-bot.environment.DATABASE_URL` | DATABASE_URL | `.../sportzal` → `.../clubcore` |
| 3 | `services.arq-worker.environment.DATABASE_URL` | DATABASE_URL | `.../sportzal` → `.../clubcore` |
| 4 | `services.migrate.environment.DATABASE_URL` | DATABASE_URL | `.../sportzal` → `.../clubcore` |
| 5 | `services.postgres.environment.POSTGRES_DB` | POSTGRES_DB | `sportzal` → `clubcore` |
| 6 | `services.postgres.healthcheck.test` | pg_isready -d arg | `pg_isready -U app -d sportzal` → `pg_isready -U app -d clubcore` |

YAML-syntactic validation (`python3 -c 'yaml.safe_load(...)'`) confirms all 4
`DATABASE_URL` entries match `POSTGRES_DB` and the `pg_isready -d` argument.
`docker compose -f apps/backend/docker-compose.yml config` was attempted but
fails because `apps/backend/.env` is absent (pre-existing condition in this
worktree — only `.env.example` ships); this is unrelated to the G-5 rename.
The YAML-syntactic fallback per the executor context overrides cleanly.

## .env.example additions

| Site | Change |
| --- | --- |
| `DATABASE_URL` (line 2) | `…/sportzal` → `…/clubcore` |
| New 4-line comment block (after DATABASE_URL) | Documents `CLUBCORE_EMAIL_FROM` as a commented-out optional override with the D-62-03 fallback chain (`CLUBCORE_EMAIL_FROM → SPORTZAL_EMAIL_FROM (deprecated, v1.11 removal) → noreply@mail.sportzal.ru hardcoded default`). The `CLUBCORE_EMAIL_FROM=` line itself is commented — operator opt-in only. |

Note: the legacy `noreply@mail.sportzal.ru` reference in the comment block is
**intentional** (D-62-03 fallback target); it does not match the gate pattern
`/sportzal\|POSTGRES_DB: sportzal\|-d sportzal` so the zero-residual gate
remains green.

## Runbook line/token coverage

`.planning/handoff/clubcore-db-rename-runbook.md`:

| Gate | Required | Actual |
| --- | --- | --- |
| Line count | 30-80 | **79** |
| `pg_dump` | ≥1 | 1 |
| `pg_restore` | ≥1 | 1 |
| `FLUSHDB` | ≥1 | 3 |
| `DKIM\|SPF\|DMARC` | ≥3 | 5 |
| `pg_isready` | ≥1 | 1 |
| `D-62-04\|D-62-05\|D-62-07` | ≥3 | 6 |
| `Rollback\|rollback` | ≥1 | 3 |
| `## ` section headers | ≥5 | 7 |
| Combined token coverage | ≥7 | 12 |

### Section headers present

1. `## 1. Pre-cutover backup`
2. `## 2. Postgres DB rename via dump/restore (D-62-04, operator-tier)`
3. `## 3. Redis FLUSHDB cutover (D-62-07; cross-references G-3 / plan 62-03)`
4. `## 4. DNS/DKIM/SPF/DMARC checklist for new email FROM domain (D-62-05)`
5. `## 5. Post-cutover smoke`
6. `## 6. Rollback`
7. `## Operator`

The G-3 cross-reference appears in §3 header — operator combining v1.10
cutover sees the Redis FLUSHDB step explicitly tied to plan 62-03's Redis
namespace flip.

## Threat-model coverage

All six threats from the plan's `<threat_model>` are addressed in the runbook:

| Threat | Disposition | Where addressed |
| --- | --- | --- |
| T-62-05-01 (PII in pg_dump artifact) | mitigate | §1 `chmod 600` + 7-day retention window |
| T-62-05-02 (mid-cutover downtime) | accept | §5 documents the planned downtime window |
| T-62-05-03 (compose DB-name mismatch) | mitigate | Task 1 grep gates assert 6-site lockstep at plan tip |
| T-62-05-04 (Redis replay window) | accept | §3 tradeoff table documents TTL bounds + FSM idempotency mitigation |
| T-62-05-05 (DKIM-before-FROM ordering) | mitigate | §4 explicit `THEN set CLUBCORE_EMAIL_FROM` step ordered after DKIM publish |
| T-62-05-06 (cutover evidence capture) | accept | runbook header points operator to v1.11 / Phase 67 / RUN-08 |

## Deviations from Plan

**Runbook line-count trim (Rule 3 — blocking-issue auto-fix during Task 2).**

The first draft of `clubcore-db-rename-runbook.md` was 136 lines (exceeded the
plan's 30-80 acceptance gate). Two compression passes reduced it to 79 lines
without dropping any required token, section, or operator step. Trim removed
inline prose duplication and merged some short paragraphs; all 6 sections,
all required commands, all decision cross-references, and the threat-model
mitigations remained intact. Fix applied inline during Task 2; verified by
re-running the gate grep+wc; counted as "auto-fix while implementing" rather
than a separate commit.

No other deviations.

## Authentication gates encountered

None. Operator-tier work; no API calls or auth flows triggered during this plan.

## Verification summary

- All 6 docker-compose DB-identifier sites flipped to `clubcore` in lockstep ✓
- `.env.example` DATABASE_URL → `/clubcore` + commented `CLUBCORE_EMAIL_FROM` doc ✓
- Zero residual `sportzal` in config files (per gate pattern `/sportzal\|POSTGRES_DB: sportzal\|-d sportzal`) ✓
- New runbook `.planning/handoff/clubcore-db-rename-runbook.md` present, 79 lines, all token gates green ✓
- YAML-syntactic compose validation passes (Python `yaml.safe_load` confirms 4 DATABASE_URL ↔ POSTGRES_DB ↔ pg_isready lockstep) ✓
- `docker compose ... config` skipped due to pre-existing missing `.env` (not introduced by this plan); YAML fallback used per executor context override ✓
- Runbook cross-references all three decisions D-62-04, D-62-05, D-62-07, plus the §3 G-3 / plan 62-03 cross-reference ✓
- Runbook is informational only; live cutover is operator-pending and evidence lands in v1.11 / Phase 67 / RUN-08 ✓

## Operator-pending follow-up

Per CONTEXT line 191 and the runbook header:

- Live `pg_dump | pg_restore` cutover from `sportzal` → `clubcore` on production Postgres
- Live `redis-cli FLUSHDB` (or scoped `sz:*` DEL) on production Redis
- Optional: DNS/DKIM/SPF/DMARC publication if operator migrates email FROM to `mail.clubcore.ru`
- Live post-cutover smoke (`docker compose up`, `pg_isready -d clubcore`, `/api/v1/health`, targeted integration test)

Evidence captured by operator lands in `v1.10-OPERATOR-EVIDENCE.md` under
**v1.11 / Phase 67 / RUN-08**. This plan does NOT execute the cutover; it
ships the renamed config + the checklist.

## Self-Check: PASSED

- `apps/backend/.env.example` present, contains `/clubcore` and `CLUBCORE_EMAIL_FROM` ✓
- `apps/backend/docker-compose.yml` present, contains 4× `/clubcore`, 1× `POSTGRES_DB: clubcore`, 1× `pg_isready -U app -d clubcore` ✓
- `.planning/handoff/clubcore-db-rename-runbook.md` present (79 lines) ✓
- Commit `6f0854af` present in `git log` ✓
- Commit `e6aa7fa8` present in `git log` ✓
- No modifications to `.planning/STATE.md` ✓
- No modifications to `.planning/ROADMAP.md` ✓
