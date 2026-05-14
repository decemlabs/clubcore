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

## Milestone: v1.3 — Memberships Extras + Tech-Debt

**Shipped:** 2026-05-14
**Phases:** 6 (24–29) | **Plans:** 33 | **Tasks:** 29
**Requirements:** 44/44 satisfied (1 mock-mode UX gap deferred to v1.4)
**Code:** ~9.9K LOC backend Python (+1.8K vs v1.2), ~18.8K LOC TS (+2K vs v1.2)
**Timeline:** 2026-05-08 → 2026-05-14 (6 days), 199 commits (45 feat), 204 files changed (+37,353 / −393)
**Verification:** Phase 29 served as the milestone audit — passed (7/7 human-verification scenarios + cross-phase smoke; 3 production-blocker regressions REG-29-01/03/04 found and fixed inline; 1 minor UX gap deferred); `.planning/milestones/v1.3-VERIFICATION-LOG.md`.

### What Was Built

- **Foundations & tech-debt bedrock (Phase 24)** — `LOCKED_AUDIT_EVENTS` extended to 34-entry; status taxonomy with central `_assert_can_transition` + declarative `MEMBERSHIP_STATUS_TRANSITIONS`; resolver defence-in-depth `end_date >= today` filter; backend `?expiring=true&within=N` mock/http parity; SVC001 walker extended to `auth/service.py`. Closes 3 of 4 v1.2 carry-overs (DEBT-01/02/03).
- **Memberships — Freeze (Phase 25)** — `freeze_days_limit` immutable per-plan field; `membership_freeze_periods` table with partial unique `WHERE ended_at IS NULL`; `freeze_membership` / `unfreeze_membership` with ceil-rounded day accounting; resolver rejects `frozen` (anti-oracle DM); 2 new endpoints (`/freeze`, `/unfreeze`); 16-cell state-machine matrix + race tests.
- **Memberships — Renewal (Phase 26)** — self-FK `previous_membership_id`; current-price snapshot on `renew_membership`; resolver tiebreak inverted to `start_date ASC` so running membership stays primary until its `end_date`; expired-source date strategy `start_date = today` with audit-traceable literal; `POST /memberships/{id}/renew`.
- **Expiring-soon Telegram (Phase 27)** — `membership_notifications` UNIQUE `(membership_id, kind)` for idempotency; ARQ cron 06:15 MSK (10-min buffer after `expire_memberships`); 6 locked Russian DM templates with per-client A/B variant (`client_id.bytes[0] & 1`, anti-oracle); insert idempotency row only on successful send.
- **OpenAPI drift gate + admin-web wiring (Phase 28)** — atomic regen of `openapi.json` + `schema.d.ts` (one drift-gate cycle); admin-web freeze/renewal UI: `/memberships/$membershipId` flat detail route with `FreezeSection` + `RenewSection` + `RenewConfirmDialog`; shared `StatusBadge`; «Заморожен» filter pill + «Истекает в течение» selector on list page; 3 mutation hooks (freeze/unfreeze optimistic, renew non-optimistic); 24 locked Russian i18n strings.
- **Milestone verification (Phase 29)** — 7/7 inherited human-verification scenarios against live backend + Telegram sandbox; cross-phase freeze→renewal→expiring-cron smoke; 729 backend + 233 admin-web tests + 6/6 CI gates evidence captured; 3 production-blocker regressions found and fixed inline (REG-29-01 Vite dev-proxy; REG-29-03 bot worker resolver registrations; REG-29-04 cron eager-import); operator sign-off with verbatim DM evidence.

### What Worked

1. **`LOCKED_AUDIT_EVENTS` pre-registration in Phase 24 paid off across Phases 25/26/27.** Adding the 6 v1.3 event pairs to the frozenset *before* their callsites existed meant every later phase passed CI from its first commit — no "add event then add callsite" iteration churn. The AST literal-string gate stayed honest the whole milestone.
2. **Phase 29 as the milestone-verification phase (not a separate audit doc).** Replacing a hand-written `v1.3-MILESTONE-AUDIT.md` with a verification phase that ran 6 plans (live-stack runbook, one-shot cron runner, 6 scenarios, cross-phase smoke, test-suite + CI evidence, finalize log) caught 3 production-blocker regressions (REG-29-01/03/04) that would have shipped silently. Live-stack verification was a real gate, not a check-the-box.
3. **DB-level enforcement habit carried forward.** Freeze period concurrency via partial unique `WHERE ended_at IS NULL` (parallel to v1.2 visits `UNIQUE (client_id, gym_date)`) made MEM-FRZ-TEST-03 (race-on-active-freeze) green first try. Expiring-soon idempotency via UNIQUE `(membership_id, kind)` survived a docker-restart at 06:14 race in Phase 29 cross-phase smoke.
4. **Inline production-blocker fixes during milestone verification.** REG-29-01 (Vite dev-proxy), REG-29-03 (bot worker missing resolver registrations), REG-29-04 (cron runner missing eager imports) — all caught at the gate, fixed without opening gap-closure phases. Verbatim operator confirmations made the gate authoritative.
5. **Resolver tiebreak rule extension survived three touch-points cleanly.** Phase 24 added `end_date >= today`, Phase 25 added `status != frozen`, Phase 26 inverted `ORDER BY` to `start_date ASC` — each phase left the resolver in a green test and the others' assumptions intact. The "resolver touch-points serialized" planning decision (recorded in PROJECT.md) prevented merge conflict between Phases 25 and 26.

### What Was Inefficient

1. **REQUIREMENTS.md traceability table drift again.** Same shape as v1.2: phase verifications passed but the central table stayed Pending for 32 rows until milestone close pre-flight bulk-flipped them. Lesson from v1.2 retrospective wasn't applied — `gsd-sdk query verify` still doesn't write back to the traceability row. Either codify a CLI shim or accept the close-time flip as a recurring 5-minute cost.
2. **STATE.md auto-extracted accomplishments at close were unusable.** `gsd-sdk query milestone.complete` extracted SUMMARY one-liners but many SUMMARY files have weak frontmatter (or none) and the body fallback grabbed text like "None — plan executed exactly as written.", "Before:", or "Task 1 — Status forwarding (FE-11):" Manual rewrite of the MILESTONES.md entry took ~15 minutes of curation. Either tighten SUMMARY one-liner discipline at phase close, or write an LLM-side curator for the entry.
3. **Phase 28 mock-mode `?status=` filter parity gap shipped despite Phase 28 verification.** CONTEXT.md D-28-11 wrongly stated "Mock already accepts status" — the gap was a CONTEXT claim, not a missed implementation. Phase 28 verification *did* catch it as "PARTIAL" but accepted the gap rather than blocking. With hindsight, a CONTEXT-claim audit ("is this claim actually true today, grep history") before any phase plan would have caught this.
4. **`gsd-sdk milestone.complete` doesn't archive the audit when there isn't one.** Phase 29 wrote `v1.3-VERIFICATION-LOG.md` directly to `milestones/`, but the CLI's `milestones/v1.3-MILESTONE-AUDIT.md` path stayed empty. Functionally fine, but breaks the audit-as-file pattern from v1.1/v1.2.

### Patterns Established

- **`LOCKED_AUDIT_EVENTS` extended UP-FRONT, in the bedrock phase of a milestone.** Audit events are the cheap, declarative front-of-house contract; lock them before any callsites land so the AST gate stays meaningful.
- **Milestone-verification-as-phase** (Phase 29 model) — a phase whose plans are "set up live stack + run human scenarios + write evidence" replaces a hand-authored audit doc and runs against the real production stack. Use when the milestone has user-facing behaviour worth eyeballing.
- **Cron ordering with explicit buffer + `unique=True`** (06:05 expire, 06:15 expiring-soon) — 10-minute gap absorbs slow runs, `unique=True` survives docker-restart races. Reusable for every future ARQ chain.
- **Per-client anti-oracle variant via stable hash bit** (`client_id.bytes[0] & 1`) — keeps the security model intact (same DM for the same client every time) while making the message set look organic. Reusable for any future locked-copy expansion.
- **Inline regression fixes during milestone verification, not gap-closure phases** — when the regression is small and the verification phase is already running, fix in the phase's plan rather than spawning a 30.x phase. Cheap and the audit-as-phase model handles it cleanly.

### Key Lessons

1. **A milestone-verification phase against live production stack is worth ~3 production incidents avoided.** REG-29-01/03/04 were all gate-time catches that would have failed in v1.4 production setup; the cost of Phase 29 (1 day) bought 3 days of v1.4 firefighting avoided.
2. **CONTEXT.md claims need a "grep this is still true" gate before each phase plan.** D-28-11's "Mock already accepts status" was wrong at write-time; it survived because nobody re-greped. Add a CONTEXT-claim audit step to `/gsd-plan-phase` (or accept that one mock-parity gap per UI phase is the going rate).
3. **`gsd-sdk milestone.complete` output is a draft, not a final.** Auto-extracted accomplishments need manual curation every milestone close. Plan ~15 minutes of MILESTONES.md rewriting into the close routine.
4. **Defence-in-depth filters in resolvers are cheap and worth it.** DEBT-01's `end_date >= today` resolver filter cost 1 line of SQL + 1 test; it would have caught REG-29 class issues during ARQ-outage scenarios that the test suite doesn't model. Apply same pattern to any future scheduled-job-driven status transitions.
5. **Quick-fixes via /gsd-fast scale.** Three of the v1.3 inline production-blocker fixes (REG-29-01/03/04) used the existing `await session.commit()` + plan-then-commit discipline; no /gsd-fast needed since they landed inside the active Phase 29 plans. Confirms the quick-task lane is for *between-phase* fixes, not *within-phase*.

### Cost Observations

- **Phase 28 was the densest** at 8 plans (vs the 4-6 plan v1.2 average) because the OpenAPI drift gate + admin-web wiring touched 11 file types in one phase. Predictable concentration; would split this differently next time (one phase for backend types/schema regen, one for FE wiring) if the milestone weren't on a 6-day rhythm.
- **Phase 29 was the highest-value-per-LOC** — 6 plans, mostly orchestration scripts (`seed_verification_fixtures.py`, `run_expiring_cron_once.py`) plus markdown evidence — and caught 3 production blockers. Verification phases should always be on the roadmap when the milestone has live-stack-observable behaviour.
- **v1.3 was the fastest milestone** by feature-density (6 days, 33 plans, 44 reqs) but only because Phases 24-27 backend work was tightly scoped + Phase 28 admin-web was atomically regen-able. v1.4 Billing won't share this profile.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v1.0 Phase A | 3 | 17 | Skeleton-only; `import-linter` and quality tooling shipped before any business code |
| v1.1 Auth + Clients | 11 (incl. 3 gap-closure) | 63 | Gap-closure phases (12/13/14) introduced; OpenAPI drift gate; Protocol-based cross-module callbacks; SAVEPOINT test isolation |
| v1.2 Memberships + Visits | 9 | 36 | DB-level race-proof constraints (`GENERATED STORED` + composite UNIQUE); first real ARQ scheduled cron; second + third Protocol-based cross-module slots; locked code-constant copy for security-sensitive bot DMs; inline UAT issue fixing |
| v1.3 Memberships Extras + Tech-Debt | 6 | 33 | `LOCKED_AUDIT_EVENTS` pre-registration discipline; milestone-verification-as-phase replacing standalone audit doc; second ARQ scheduled cron with ordered buffer; per-client anti-oracle hash-bit variant for locked copy; inline regression fixes during verification phase |

### Cumulative Quality

| Milestone | Backend LOC | TS LOC | REQ Satisfied | Tests |
|-----------|-------------|--------|---------------|-------|
| v1.0 | ~46 files | unchanged | 47/47 | 3 |
| v1.1 | ~52 files (~4.4K LOC) | ~12.8K LOC | 70/70 | 132 unit + integration suites for auth/RBAC/clients/persistence/search |
| v1.2 | ~8.1K LOC backend | ~16.8K LOC | 63/63 (2 accepted-deviations) | 569+ backend (incl. VIS-TEST-01 concurrent race + ARQ-TEST-01/02 cron correctness/idempotency) + 184+ admin-web |
| v1.3 | ~9.9K LOC backend | ~18.8K LOC | 44/44 (1 mock-mode UX deferred) | 729 backend (incl. 16-cell freeze state-machine matrix + expiring-soon idempotency + renewal date strategy) + 233 admin-web |

### Top Lessons (Verified Across Milestones)

1. **`import-linter` from Phase A is non-negotiable** — saved real time in v1.1 by catching cross-module imports during Phase 4 + Phase 7. Keep enforcing.
2. **Pin contract primitives before the first business migration** — v1.1 Phase 4 doing this proactively meant zero retrofit work in Phases 5/8. Apply to every future contract surface (e.g. multi-tenancy ContextVar, if it ever enters scope).
3. **Verification artifacts gate milestone closure, not phase closure.** The audit-driven `/gsd-complete-milestone` workflow correctly forced the v1.1 close to wait for Phase 14 + the 70/70 REQ coverage instead of declaring done at Phase 11.
