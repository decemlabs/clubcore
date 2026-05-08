# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.1 — Auth + Clients

**Shipped:** 2026-05-07
**Phases:** 11 (4–14, including 3 gap-closure phases 12/13/14 + inline Phase 12.1) | **Plans:** 63 | **Tasks:** 101
**Timeline:** 2026-05-02 → 2026-05-07 (5 days, 341 commits, 74 feat)
**Requirements:** 70/70 satisfied
**Code shipped:** ~4.4K LOC backend Python, ~12.8K LOC TypeScript

### What Was Built
- Two-channel auth (email/password + Telegram OTP), JWT HS256 + Argon2id, refresh-rotation family with reuse-window race tolerance, Redis-mirrored sessions, CSRF on every mutating route
- Server-side RBAC at byte-parity with admin-web `can.ts` (route-introspection guard + three-way parity test)
- Telegram bot worker as a separate `python -m app.workers.telegram_bot` process (4th docker-compose service)
- Clients module with full CRUD, soft-delete partial unique index, `pg_trgm` ILIKE search, audit log writes from both auth and clients flows; LIKE-escape hardening (Phase 14) closes the `?q=%` PII over-exposure
- OpenAPI drift gate end-to-end: byte-stable `openapi.json` + committed `schema.d.ts` + CI `git diff --exit-code` on both sides
- admin-web `/login` (two tabs) and `/clients/*` fully wired through `VITE_API_MODE=http` swap-seam; other domains stay on mocks (zero regression)

### What Worked
- **`import-linter` pinned from Phase A onward** — architectural constraints (`core ⊥ modules`, `modules independent`, `integrations ⊥ modules`) caught real cross-module imports during Phase 4 + Phase 7 work, before they became habits.
- **Pagination contract + camelCase wire format flipped before the first business migration** — Phase 4 doing this work first meant Phase 5/8 never had to retrofit `snake_case` JSON or `limit/offset`. Zero churn for the FE consumer.
- **Cross-module callbacks via Protocol + `app/main.py` registration** — `core` stays free of `app.modules` imports (D-24 loader pattern); auth↔telegram-bot communication doesn't violate `modules-independent`. This pattern will scale to next domains.
- **Three gap-closure phases (12/13/14) instead of patching the originals** — keeping each phase's commit chain clean preserved the audit trail. Phase 12 specifically was a verification-only phase that closed `human_needed` flags from earlier audits.
- **SAVEPOINT-based per-test isolation against real Postgres** — paid off in Phase 8 when integration tests reused the same UNIQUE email/phone across cases without IntegrityError.
- **Audit-driven completion** — `/gsd-audit-milestone` re-run after Phase 14 surfaced exactly the right items (the lone REQUIREMENTS.md `Pending` row for CLIENTS-04, the F-06 stale dir, the F-03/F-04 contract drift) and gated the close on REQ-coverage rather than vibes.

### What Was Inefficient
- **Phase 12.1 was discovered late** — the `clients/service.py` write paths weren't calling `await session.commit()`, so `get_db` auto-rolled-back at request exit. The bug was masked because audit events still went to structlog. Caught only when Phase 11 SC #4 live-runbook failed. Future business modules should derive from a `service` template that includes the commit invariant.
- **63 stale `Pending` rows in REQUIREMENTS.md traceability table** survived until Phase 13 SC #6 — automatic propagation from VERIFICATION.md status into REQUIREMENTS.md table would have eliminated the bookkeeping debt.
- **Phase 7 (Telegram OTP)** flagged as "needs deeper research at planning time" in PROJECT.md before discuss-phase, but the research was still done inline rather than as a separate spike. ptb 22 deep-link API and error class hierarchy ate plan-time budget.
- **`expiresAt` drift on TelegramStartResponse** (F-03) — both backend and FE had it; the contract was never enforced by a parity test until Phase 13 cleaned it up. The OpenAPI drift gate (Phase 9) only catches backend-internal drift, not legacy-handwritten FE contract files.
- **Phase 10 P05** lost a half-day on the ReUI Tabs primitive (404 from base-nova registry) — fell back to standard shadcn Tabs. Registry availability should be probed during research, not during execution.
- **MILESTONES.md auto-generated entry was unusable** — the `gsd-sdk query milestone.complete` CLI dumped raw `requirements-completed:` lines from each plan SUMMARY frontmatter, including ruff-fix headers and "One-liner:" placeholders. Required manual rewrite. Worth a follow-up: extract `## Outcome` or `## Highlights` from SUMMARY.md instead of grep-greedy frontmatter.

### Patterns Established
- **Layered import boundary** as a first-class architectural test (`import-linter` contracts), not a code-review nicety.
- **Protocol-based cross-module wiring** via composition root (`app/main.py:register_user_loader`, `HandlerContext`).
- **OpenAPI drift gate as the FE↔BE contract enforcer** — one source of truth (`openapi.json`), CI fails the PR if either side drifted.
- **Camel/snake boundary at Pydantic** (`alias_generator=to_camel` + `populate_by_name=True`); Python identifiers stay snake_case, wire format is camelCase. No middleware translation, no manual mapping.
- **SAVEPOINT-based per-test isolation** for integration tests against real Postgres (no schema drop-recreate).
- **Repository helpers `list_alive`/`get_alive` as the sole owner of `select(Model)`** — soft-delete filter cannot be forgotten by the service layer.
- **Gap-closure phases instead of phase amendments** — keeps the audit trail clean and lets each phase own a coherent commit chain.
- **`VITE_API_MODE=http` swap-seam scoped per-domain** — phased rollout makes regression risk in untouched domains exactly zero.

### Key Lessons
1. **Pin contract primitives (pagination shape, wire format, naming convention) BEFORE the first business migration.** Once a migration ships, retrofitting the contract becomes data-migration work, not refactor work.
2. **Architectural tests > convention.** `import-linter` + route-introspection + RBAC parity test caught more drift than every code review combined. Lint contracts at the boundaries that matter.
3. **Verify-on-the-wire, not verify-by-types.** Phase 11 caught two BLOCKER shape mismatches (F-01, F-02) that types passed. The OpenAPI drift gate caught backend changes; the contract adapter caught FE legacy types. The Phase 12.1 commit bug got past unit tests because audit events were correct — only the live-runbook revealed it. Always run a real E2E walkthrough before declaring a phase done.
4. **Soft-delete with partial unique index is the durable pattern.** Hard-delete + audit log is fragile; soft-delete with `WHERE deleted_at IS NULL` lets phone numbers be reused without exposing the DB to reception's read-paths.
5. **NIST 800-63B 2024 is the right baseline for password policy.** No complexity rules, no rotation, no lockout — rate-limit + 12-char min only. This was contentious in Phase 5 discussion; the doc reference closed it cleanly.
6. **CR-01 (LIKE-escape) was a real PII bug, not a theoretical advisory.** The Phase 8 review correctly flagged it; deferring to Phase 14 (gap-closure phase) was the right call rather than blocking Phase 8 closure. But the deferral period should be measured (it was 3 days here — fine).
7. **Workspace tooling (worktree dependency installation) breaks twice in a row before being noticed.** Phase 12 plans 1 + 2 both lost time on missing `pnpm install` in worktree. Worth a script or a hook.
8. **Backend wire format = camelCase via Pydantic aliasing was net-zero work** but eliminated a whole class of FE-side adapter bugs. The cost was low; the leverage was high.

### Cost Observations
- Model mix: not tracked
- Sessions: not tracked
- Notable: 11 phases / 5 days = ~2.2 phases/day blended velocity (including 3 gap-closure phases). Phase 4 (foundations) was the densest at 9 plans; Phase 9 (OpenAPI) was the smallest at 3 plans but with the highest leverage (every later FE↔BE change is now drift-gated).

---

## Milestone: v1.2 — Memberships + Visits

**Shipped:** 2026-05-08
**Phases:** 9 (15–23) | **Plans:** 36 | **Tasks:** 60
**Requirements:** 63/63 satisfied (2 accepted-at-planning deviations carried forward)
**Code:** ~8.1K LOC backend Python, ~16.8K LOC TS (admin-web + api-client)
**Timeline:** 2026-05-07 → 2026-05-08 (rapid follow-on after v1.1 close), 166 commits (37 feat), 404 files changed (+39,142 / −1,173)
**Audit:** passed — re-audited 2026-05-08T16:30 after closing the two procedural gaps (Phase 22 stale verification + Phase 18 ARQ-03 prose decision)

### What Was Built

- **RBAC + audit + service-write commit gate (Phase 15)** — `OWNER_ONLY` extended 6 entries; `LOCKED_AUDIT_EVENTS` 28-entry frozenset with `audit.emit` literal-string AST gate; `BackendSchemaBase` (Pydantic 2.11 canonical pair); SVC001 commit-gate AST walker.
- **Memberships catalog + instances + resolver (Phases 16–17)** — `membership_plans` partial-unique table; `memberships` with mandatory snapshot pricing + ON DELETE RESTRICT FK; **inclusive `end_date`**; `resolve_active_membership_by_client` Protocol slot in `core/dependencies.py`.
- **ARQ scheduled `expire_memberships` (Phase 18)** — first real ARQ cron (06:05 Europe/Moscow daily); idempotent SQL `UPDATE ... RETURNING`; structlog `job_id`/`job_name` contextvars (Pitfall 14); 5th `arq-worker` compose service.
- **Visits — DB-level race-proof 1/day (Phases 19–20)** — `gym_date GENERATED STORED` + `UNIQUE (client_id, gym_date)` (Postgres wins, not app-layer); reception + Telegram bot `/checkin` with 4 owner-locked Russian DM strings (no oracle leak); Redis dedup at `sz:bot:update:{id}`.
- **OpenAPI drift gate refresh + admin-web wiring (Phases 21–22)** — byte-stable openapi.json + regenerated schema.d.ts; admin-web ships `/membership-plans`, `/memberships`, `/visits`, `/clients/$clientId` Pattern α, `/profile` SessionsList; cheap-win differentiators D-2/D-3/D-5.
- **Auth hygiene + active sessions backend (Phase 23)** — HYG-01/02 fix 500 → 401 on Argon2 verify-error and tampered cookie; HYG-03 ships `/auth/sessions` + per-family revoke.

### What Worked

1. **Two independent cross-module Protocol slots in one milestone landed cleanly** (`ActiveMembershipResolver` for memberships → visits, `HandlerContext.visits_service` for telegram bot → visits). The v1.1 pattern (`register_user_loader` for auth → clients) generalized perfectly without modifying `import-linter` contracts. This is now a confirmed durable pattern, not a v1.1 one-off.
2. **DB-level enforcement over app-level enforcement.** `gym_date GENERATED STORED` + `UNIQUE (client_id, gym_date)` made VIS-TEST-01 (10 parallel POSTs → 1×201 + 9×409) pass first try. The decision to materialize the conversion as a Postgres column rather than computing it in Python eliminated an entire class of TZ/DST bugs and concurrency races at design time.
3. **Locked Russian DM strings as code constants, signed off before merge.** The "no oracle leak" rule (same DM for stranger as for expired-member) was preserved by treating copy as a code-review concern, not an i18n key concern. This wouldn't have worked if the strings lived in a separate ru.ts dictionary that operators could "improve" later.
4. **Inline UAT issue fixing.** Phase 22's UAT found one issue (mock `mock_not_implemented` errors not localized in demo mode) and fixed it inline (commit 4452c28) instead of opening a gap-closure phase. The 10-pass-1-issue UAT closed in a single session.

### What Was Inefficient

1. **Phase 22 verification doc went stale after BLK-* fixes.** The 4 BLK findings (BLK-01..04) were fixed post-verification in commits 18f0977/186f836/704b6e9/00e4bf8 + 0399340 + 0a54fe6, but `22-VERIFICATION.md` was not regenerated. This propagated to the v1.2 milestone audit as `gaps_found` even though the underlying code was clean. Re-verifying mid-stream (or running `/gsd-verify-work` again after `/gsd-code-review-fix`) would have avoided the 30-minute pre-flight refresh during milestone close.
2. **ARQ-03 prose vs code drift caught by milestone audit, not by Phase 18 SUMMARY review.** The ARQ 0.28 rename (`keep_cronjob_progress` → `keep_result`) was visible in 18-03 deviation notes, but REQUIREMENTS.md prose was never updated. A small edit-prose-when-deviation-is-accepted habit would close this.
3. **REQUIREMENTS.md traceability table drifted from Pending → Complete by 28 rows.** Phase verifications passed, but the central table wasn't kept in sync. The CLI handles archival but not row-by-row status flips. Future improvement: have `gsd-sdk query verify` write back to the traceability row on phase completion.

### Patterns Established

- **Protocol-based cross-module callback registered from `app/main.py` composition root** — now confirmed across three slots (auth→clients, memberships→visits, telegram→visits). Use this whenever a module needs to call into another without violating `modules-independent`.
- **DB-level `GENERATED ... STORED` columns + composite UNIQUE for race-proof business rules** — reproducible across future cases (e.g. v1.3 booking conflicts, v1.3 freeze-day counters).
- **Locked code-constant copy for security-sensitive UI text** (anti-oracle Russian DMs) — keep this technique for v1.3+ messages where the failure mode is "operator improves the wording and accidentally leaks information".
- **`/gsd-code-review-fix` → forgotten `/gsd-verify-work` re-run.** Add to local checklist: after auto-fix lands, always re-run `/gsd-verify-work` before milestone audit, or accept that the milestone close will refresh it.

### Key Lessons

1. **Verification staleness is a real cost at milestone close.** v1.1 didn't hit this because phases were closed sequentially with verification immediately after; v1.2 had parallel-eligible Phase 23 + Phase 22 fix loops post-verification. Either re-verify at close or skip ahead and accept the gaps_found audit as procedural.
2. **Owner sign-off on locked copy is a hard gate, not a nice-to-have.** D-22-11 / AUTH-TG-11 owner sign-off on Russian DM strings was the only manual checkpoint that mattered for the security model. Don't merge bot DM strings without it.
3. **Tech-debt acknowledged at planning ≠ tech-debt that disappears.** D-13 (resolver fail-safe) and D-15 (FK 409 deferred to next phase) were both correctly accepted-at-planning. They survive in PROJECT.md as v1.3 carry-forward items because GSD doesn't auto-promote planning deviations into v.next backlog. Add them to v1.3 backlog manually.
4. **The v1.2 "rapid follow-on" pattern (5 days → 1 day per follow-on milestone) only works because v1.1 paid the foundations cost.** Don't expect v1.3 Billing to be 1 day; ЮKassa + 54-ФЗ chequing is its own foundations effort.

### Cost Observations

- Phase 18 was the densest at 6 plans (5 implementation + 1 unit-test backfill); the 11-test unit suite (`tests/unit/workers/`) plus VIS-TEST-01 + ARQ-TEST-01/02 integration tests gave ARQ + Visits combined the highest defect density caught early.
- Phase 22 was the largest by file-touch count (5 plans, 34 files in plan 02 alone, 25 files in plan 03) — and predictably the one where review-fix loops landed (REVIEW-FIX rounds 1 + 2, plus inline UAT fix).
- v1.2 close pre-flight added one unplanned cycle: re-verify Phase 22 (commit 7e57d70) + reconcile ARQ-03 + sweep REQUIREMENTS.md (commit cdee261). About 30 minutes of doc-only work that could have been avoided with mid-milestone discipline.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v1.0 Phase A | 3 | 17 | Skeleton-only; `import-linter` and quality tooling shipped before any business code |
| v1.1 Auth + Clients | 11 (incl. 3 gap-closure) | 63 | Gap-closure phases (12/13/14) introduced; OpenAPI drift gate; Protocol-based cross-module callbacks; SAVEPOINT test isolation |
| v1.2 Memberships + Visits | 9 | 36 | DB-level race-proof constraints (`GENERATED STORED` + composite UNIQUE); first real ARQ scheduled cron; second + third Protocol-based cross-module slots; locked code-constant copy for security-sensitive bot DMs; inline UAT issue fixing |

### Cumulative Quality

| Milestone | Backend LOC | TS LOC | REQ Satisfied | Tests |
|-----------|-------------|--------|---------------|-------|
| v1.0 | ~46 files | unchanged | 47/47 | 3 |
| v1.1 | ~52 files (~4.4K LOC) | ~12.8K LOC | 70/70 | 132 unit + integration suites for auth/RBAC/clients/persistence/search |
| v1.2 | ~8.1K LOC backend | ~16.8K LOC | 63/63 (2 accepted-deviations) | 569+ backend (incl. VIS-TEST-01 concurrent race + ARQ-TEST-01/02 cron correctness/idempotency) + 184+ admin-web |

### Top Lessons (Verified Across Milestones)

1. **`import-linter` from Phase A is non-negotiable** — saved real time in v1.1 by catching cross-module imports during Phase 4 + Phase 7. Keep enforcing.
2. **Pin contract primitives before the first business migration** — v1.1 Phase 4 doing this proactively meant zero retrofit work in Phases 5/8. Apply to every future contract surface (e.g. multi-tenancy ContextVar, if it ever enters scope).
3. **Verification artifacts gate milestone closure, not phase closure.** The audit-driven `/gsd-complete-milestone` workflow correctly forced the v1.1 close to wait for Phase 14 + the 70/70 REQ coverage instead of declaring done at Phase 11.
