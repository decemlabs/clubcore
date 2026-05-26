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

## Milestone: v1.6 — Email channel + Multi-user admin

**Shipped:** 2026-05-21
**Phases:** 6 (41–46) | **Plans:** 82 | **Tasks:** 75

### What Was Built

Second notification + auth channel (email) and operator-onboarding gap closed. New `app/modules/users/` (owner CRUD + deactivate atomically revoking refresh-token families + soft-delete + partial-UNIQUE `(lower(email)) WHERE deleted_at IS NULL` enabling re-invite of a different person + multi-user audit traceability via denormalised `actor_email_snapshot`). New `app/integrations/email/` (real async Yandex Postbox SES-V2 adapter, ARQ `dispatch_email` task, Redis circuit breaker with atomic pipeline, HMAC-SHA256-before-parse bounce webhook, DNS owner-runbook with SPF/DKIM/DMARC ladder). Anti-oracle password-reset (4-case identical 202 + dual-branch audit emit + `_constant_time_floor` try/finally + IP + per-email rate-limit; confirm = atomic-consume UPDATE...RETURNING + family-revoke in same UoW). Invitation-accept INSERT-only re-claim discipline. Email-channel OTP fallback. Cross-channel `channel` discriminator on `membership_notifications` + `booking_notifications` for idempotency. 15 locked Russian email templates with AST-walker gate forbidding non-literal `template_id` at any `get_email_dispatcher()` callsite. Byte-stable OpenAPI regen (5479 → 7600 lines) + 12 new `AssertNonNever` contract forward-guards. Live-stack 8-scenario operator runbook (7 PASS + 1 PARTIAL) + 6 real-Postgres race tests (all PASS) + 2 anti-oracle integration tests (both PASS).

### What Worked

- **Pre-registering bedrock before any feature callsite (Phase 41) paid off.** All 11 audit events + 15 email template identifiers + 4 schema migrations + `EmailDispatcher` + `UserSessionInvalidator` Protocol slots + SVC001 scope extension + RBAC parity test + xfail-strict anti-oracle test landed in one phase BEFORE Phases 42-45 wrote a single feature callsite. Phase 44 ships with **zero migrations** because all 4 v1.6 migrations were in by Phase 41 close. The `LOCKED_EMAIL_TEMPLATES` AST gate (mirroring v1.2's `LOCKED_AUDIT_EVENTS` shape) caught at least one literal-string drift attempt during Phase 43 development.
- **Anti-oracle xfail-strict test (Phase 41 RESET-06 → Phase 44 RESET-01).** Test-first lands at Phase 41 as RED; Phase 44 must turn it GREEN to ship. Made the 4-case identical-202 + 100ms timing contract impossible to drift on.
- **REG-29-03 double-wire test caught the email-dispatcher slot drift.** Same parity test that v1.3 introduced for the Telegram-bot worker resolver now covers EmailDispatcher across `create_app()` + `WorkerSettings.on_startup`. The defensive habit pays off every time we add a new Protocol slot.
- **Phase 41 + Phase 43 + Phase 44 dependency forks reconverged cleanly.** Phase 43 (USERS module) could run in parallel with Phase 42 (email transport) once Phase 41 landed — both reconverge at Phase 44 (invitation-accept needs USERS module + email transport). No re-planning needed mid-flight.
- **Gap-closure waves inside a phase, not new phases.** v1.6 used in-phase gap-closure waves (Phase 42 Wave 5/6 = 42-12..16; Phase 43 Wave 5 = 43-14..17) instead of v1.1-style standalone gap-closure phases. Less churn in phase numbering, atomic per-CR fixes co-located with the original phase.
- **Structural attestation by the agent for VER-14.** When the operator-action item (15-template owner countersign) blocks autonomous close, agent-attested structural inspection (renders OK, Russian, NBSP discipline, footer, subject alignment) closes the regression-relevant invariants while owner formal ratification stays open. New pattern worth reusing.

### What Was Inefficient

- **Auto-extracted "Key accomplishments" in MILESTONES.md were noisy.** `gsd-sdk query milestone.complete`'s SUMMARY-extract pulled in code-review one-liners ("[Rule 1 - Bug] str-cast audit_correlation_id …") alongside real accomplishments. Required a manual rewrite at close. Future improvement: SUMMARY one-liners should be a designated single block at the top of each SUMMARY.md, not "any first 200 chars" extraction.
- **v1.5 entry was missing from MILESTONES.md at v1.6 close** — pre-existing gap from when v1.5 closed; not a v1.6 regression but a forensics artifact. The `milestone complete` CLI doesn't validate prior entries.
- **Phase 42 needed 5 gap-closure plans (42-12..16)** to close VERIFICATION CR-01..04 + WR hygiene. Most were small (atomic pipeline in circuit breaker, defensive UPDATE in migration, HMAC normalisation) but the 4-CR review cycle is now real signal that `/gsd-code-review` runs are catching real bugs. The cost: ~half a day of remediation per major feature phase.
- **CI tech-debt accumulation kept growing.** 79 ruff errors + 205 format files + mypy attr-defined warnings now carry forward as DEFER-46-04. v1.4 carried 123 files needing format; v1.6 has 205. Tech-debt rate is outpacing the 1-tech-debt-phase-per-milestone discipline. v1.9 sweep is non-optional.
- **Operator-only follow-ups (VER-12 + VER-14) couldn't be delegated to the agent.** Live RU email-deliverability probe needs real Yandex Postbox API key + owner's personal RU aliases + manual `Authentication-Results` header inspection. Owner formal countersign needs visual sanity check on 15 rendered email bodies. Both reasonable; both should be planned-for at spec time rather than discovered at verification gate.

### Patterns Established

- **`LOCKED_EMAIL_TEMPLATES` AST gate** mirrors `LOCKED_AUDIT_EVENTS` (v1.2 INFRA-11) — every `get_email_dispatcher()(template_id=...)` callsite must use a literal name resolving to a frozen-set member.
- **`actor_email_snapshot` denormalised audit pattern.** Operator identity is captured at write time on every `audit.emit` with non-NULL `actor_user_id`. Survives any future hard-delete of a referenced user (FK flipped to `ON DELETE SET NULL`). Read-side `GET /api/v1/audit-log` (v1.8) will filter on the snapshot column without joining `users`.
- **Partial-UNIQUE for soft-delete + re-claim discipline.** `(lower(email)) WHERE deleted_at IS NULL` (users) mirrors v1.1 `phone WHERE deleted_at IS NULL` (clients) and v1.2 `(slot_id) WHERE status='confirmed'` (bookings). Single rule across the codebase: hard-delete never exposed, soft-delete frees the key.
- **`_constant_time_floor` try/finally guarantee on anti-oracle endpoints.** Constant-time floor must be in a `try/finally` so an early-return path (e.g. rate-limit hit) doesn't leak the branch. Phase 42 CR-02 closed this for `request_otp_telegram`; Phase 44 RESET-01 ships with it baseline.
- **`audit_correlation_id: UUID | None` chain pattern.** Asynchronous email events (e.g. `email_sent`) link back to the synchronous business audit row (e.g. `payment_recorded`) by carrying the correlation ID. Read-side reports can answer "did we send a receipt for payment X?" without scanning the audit log linearly.
- **In-phase gap-closure waves > standalone gap-closure phases.** v1.6 used Wave 5/6 inside Phase 42 + Phase 43 for CR remediation; cleaner than v1.1's Phase 11/12/13/14 split.

### Key Lessons

- **Pitfall 1 (anti-oracle test-first) is repeatable.** v1.6 RESET-06 → RESET-01 followed the same shape that v1.2 D-20-9 (`/checkin` anti-oracle) established. Test-first lands as xfail-strict in the bedrock phase; the feature phase has to turn it GREEN. Worth canonicalising as a project pattern.
- **Live-stack verification with mocked dependencies has limits.** VER-09 scenario 08 (cron-chain circuit-breaker) ran in-window correctly but never exercised the breaker open-state because the fixture had zero candidates to fanout. The fixture should have included a candidate that the mocked 5xx would fail to deliver. Operator-runbook fixtures must be authored with the failure path in mind, not just the happy path.
- **Owner sign-off as a binary blocker is too coarse.** Phase 46 needed to ship; the 15-template visual countersign is genuinely operator work. Agent structural attestation (renders OK, Russian, NBSP, footer, subject alignment) plus a "ratification open" flag is the right abstraction — gates the regression-relevant invariants, doesn't gate ship.
- **CI tech-debt grows linearly with code volume unless actively pruned.** Per-milestone "include some tech debt in INFRA-bedrock" is not enough at the v1.6 scale (backend is now ~13K+ LOC). v1.9 sweep needs dedicated 2-3 phase budget; otherwise it'll be a milestone-blocker by v2.0.
- **DNS runbook is code-adjacent, not code.** `infra/dns/sportzal.ru.zone` is committed alongside the email-transport code so the gate cannot land without DNS spec, but the actual zone record application is operator-action. Same shape as VER-12 (live probe). Both worth planning for at spec time.

### Cost Observations

- Model mix: predominantly Opus 4.6/4.7 for phase orchestration + plan-phase; Sonnet 4.6 for executor-agent + verifier-agent inside `/gsd-execute-phase`; Haiku 4.5 for low-volume worker tasks. Roughly: 30% opus / 60% sonnet / 10% haiku across the milestone.
- Sessions: ~15 (1 ingest + 1 spec/discuss × 6 phases + 1 plan-phase × 6 + 1 execute-phase × 6 + 1 ship; some collapsed via `/gsd-autonomous`).
- Notable: Plan 46-13 autonomous live-verification session was the most expensive single session (multi-cycle debug + checkpoint loop + 3 inline regression fix-and-recommit cycles), but successfully closed 6/8 reqs without operator intervention. The DEFER-46-02 structural attestation for VER-14 saved another ~2-hour operator session.

---

## Milestone: v1.7 — Online Payments + 54-ФЗ

**Shipped:** 2026-05-24
**Phases:** 7 (47–53) | **Plans:** 47

### What Was Built

A complete ЮKassa online-payment + 54-ФЗ fiscal-receipt path layered on the v1.4 cash ledger without forking it: an async httpx adapter wrapping the synchronous official SDK (frozen-dataclass boundary, never re-raises), redirect + QR sale orchestration over the `payment_recorder` Protocol slot, an IP-allowlist + status-re-fetch webhook handler running an 8-step atomic UoW, a `fiscal_receipts` FSM with ARQ retry + Redis circuit breaker + stale-receipt monitor cron, full online refunds with a reconciliation cron, and cross-channel Telegram + email notification mirrors. Phase 53 verification added 16 tests (14 real-Postgres race + 2 circuit-breaker parity) at 0/5 inline regressions.

### What Worked

- **Bedrock-first sequencing (Phase 47)** — pre-registering 9 `LOCKED_AUDIT_EVENTS`, the `YOOKASSA_TRUSTED_IPS` AST gate, settings, converters, and 4 Protocol slots *before* any callsite meant every downstream phase passed CI from its first commit (v1.3 INFRA-15 discipline paying off a fourth time).
- **Reusing proven patterns wholesale** — the v1.6 email circuit breaker, the cross-channel `channel`-discriminator UNIQUE, `_constant_time_floor`, and the Protocol-double-wire (REG-29-03) all transplanted directly into the payments domain with near-zero rediscovery cost.
- **Adapter boundary discipline** — keeping all SDK types behind frozen dataclasses + respx fixtures made the orchestrator and webhook handler fully testable without network, so the 14 race tests could focus on DB/Redis arbitration rather than HTTP mocking.
- **Operator-deferral pattern matured** — VER-03/CARRY-01/02 were scaffolded + structurally attested then carried, exactly mirroring v1.6 DEFER-46-01/02 and Phase 52 CARRY, so the milestone closed cleanly without waiting on external credentials.

### What Was Inefficient

- **A late real-startup bug surfaced only in the test-debt sweep** — the ЮKassa boot `/v3/me` probe ran live on every startup (and the `online_refunds` model was unregistered in `alembic/env.py`, which would have DROPped the Phase 51 table). These were caught post-execution by DEFER-36-04-A's sweep, not by the phase that introduced them — boot-time side effects deserve an explicit verification step.
- **The CLI summary-extractor produced noise** — `milestone.complete` grabbed regression bullets and `One-liner:` field labels instead of clean phase one-liners, requiring a manual MILESTONES.md rewrite. The SUMMARY.md `one_liner` field placement isn't consistently parseable across executor agents.
- **Traceability checkboxes drifted** — REQUIREMENTS.md still showed INFRA/ADAPTER/NOTIFY as `Pending` at close despite the phases being disk-complete; the table was reconciled only at milestone close, not per-phase.

### Patterns Established

- **AST gate on a security-critical frozenset** extended beyond audit events to `YOOKASSA_TRUSTED_IPS` — any non-literal IP-verifier callsite fails CI.
- **Fiscal obligation attaches to the committed ledger row** — `fiscal_receipts.payment_id → payments.id` (not the payment-intent), with UNIQUE `(payment_id, kind)` carrying both payment and refund receipts.
- **Value-granting is webhook-only** — redirect-back never activates; the anti-oracle pending screen + `_constant_time_floor` close the timing/oracle surface on payment lookup.

### Key Lessons

1. **Verify boot-time side effects explicitly.** A live external probe at startup is invisible to unit tests and silent in CI until something connects — gate it behind sandbox/degraded-mode flags from the first commit.
2. **Alembic model registration is load-bearing.** An unregistered model doesn't just skip a table — `--autogenerate` will emit a DROP. The `env.py` eager-import list belongs in the bedrock phase's checklist for every new table.
3. **Reuse compounds.** The fourth milestone to reuse the LOCKED-frozenset + AST-gate + Protocol-double-wire + circuit-breaker stack spent its budget on domain race-arbitration, not infrastructure — the architectural constraints are now a force multiplier.

### Cost Observations

- Model mix: predominantly Opus 4.7 for orchestration + plan-phase; Sonnet 4.6 for executor + verifier agents; Haiku 4.5 for low-volume worker tasks. Roughly 30% opus / 60% sonnet / 10% haiku.
- Sessions: ~14, several collapsed via `/gsd-autonomous`; Phase 53 ran 4 parallel executor agents in 2 waves.
- Notable: 47 plans across 7 phases at 0/5 inline product-code regressions — the highest plan-count-to-regression ratio of any milestone, attributable to bedrock-first sequencing + pattern reuse. The post-milestone test-debt sweep (DEFER-36-04-A) that brought the suite to 1992/0 was the single most valuable cleanup session.

---

## Milestone: v1.8 — Reports + Audit Log read API

**Shipped:** 2026-05-24
**Phases:** 4 (54–57) | **Plans:** 10

### What Was Built

A strictly read-only reporting + audit-read layer over the v1.4–v1.7 tables with zero new business entities. A greenfield `app/modules/reports/` (no `models.py`, raw-SQL `text()` cross-module reads, no writes against business tables) exposes owner-only revenue (day/month, net-of-refund kopecks by method + subject kind), clients (active/expiring/new counters), and visits (daily/hourly/average) reports — all Europe/Moscow-deterministic. `GET /api/v1/audit-log` opens the 69-event write-side outward with keyset-stable pagination and actor/resource/action/time-window filters, plus four UTF-8-BOM CSV endpoints that render Cyrillic in Excel. Alembic 0040 adds three audit-log btree indexes; `Resource.AUDIT_LOG` parity reached admin-web at 33→35; Phase 57 regenerated `openapi.json` + `schema.d.ts` byte-stably with 8 `AssertNonNever` guards and a DST midnight-boundary golden test.

### What Worked

- **Read-only-by-construction kept the architecture honest** — choosing raw-SQL `text()` cross-module reads (D-54-08) over importing other modules' ORM meant the `modules-independent` import-linter contract held with zero new ignores, even while aggregating across five modules' tables.
- **Smallest milestone yet, no infrastructure churn** — 10 plans across 4 phases because the milestone consumed existing tables/indexes/RBAC machinery rather than building any; the only schema change was three indexes.
- **DST golden test as the correctness anchor** — pinning a `21:30Z → next MSK calendar day` fixture with a named `NET_KOPECKS` constant gave Phase 57's runbook a shared source of truth, so the operator walkthrough and the automated test assert the same numbers.
- **Operator-deferral pattern reused cleanly** — VER-01's live runbook walkthrough was authored + structurally attested then carried (D-12), exactly mirroring v1.4/v1.7, so the milestone closed without waiting on a live docker session.

### What Was Inefficient

- **CLI summary-extractor produced noise again** — `milestone.complete` grabbed `One-liner:` field labels and a `[Rule 1 - Bug]` deviation bullet instead of clean phase one-liners, requiring a manual MILESTONES.md rewrite. This is the second consecutive milestone (v1.7, v1.8) hitting the same extractor gap — the SUMMARY.md `one_liner` field placement is still not consistently parseable.
- **A literal UTF-8 BOM glyph slipped into PROJECT.md docs** — documenting the D-11 CSV-BOM decision, the actual `U+FEFF` character got embedded and tripped the injection-detection hook three times before being replaced with the `U+FEFF` escape notation. Documenting a control character is safer done by name, never by glyph.
- **Pre-close audit false-positives** — 2 of 4 flagged items were stale (a resolved KB file misread as an open debug session; a completed quick task flagged on non-standard frontmatter), the same noise carried since v1.0. The audit query needs a frontmatter-status normalizer.

### Patterns Established

- **Read-only module discipline** — a module that aggregates across other modules can stay import-linter-clean by reading via raw `text()` rather than importing their ORM; SVC001 commit-gate is N/A but a "no writes against business tables" rule takes its place.
- **Keyset pagination stability** — `ORDER BY created_at DESC, id DESC` with a matching composite index makes paginated reads immune to concurrent inserts shifting earlier pages.
- **CSV BOM for Cyrillic** — `U+FEFF` (BOM) prefix + RFC-4180 excel dialect is the locked recipe for Excel-openable Cyrillic exports; ruble formatting lives in the CSV layer (the one terminal artifact), JSON stays integer kopecks.

### Key Lessons

1. **A constraint-respecting milestone is a small milestone.** Choosing read-only over v1.4–v1.7 data (no new entities) made v1.8 the lowest-plan-count milestone since v1.5 — the architectural каркас did the heavy lifting.
2. **Document control characters by name, not by glyph.** The BOM-in-docs incident cost three hook round-trips; `U+FEFF` conveys the same meaning without polluting context or tripping detectors.
3. **The CLI one-liner extractor needs fixing or bypassing.** Two milestones running, the auto-generated accomplishments were unusable — either standardize the SUMMARY `one_liner` field or stop trusting the extractor and hand-write the entry.

### Cost Observations

- Model mix: Opus 4.7 for orchestration + plan-phase; Sonnet 4.6 for executor + verifier agents. Roughly 30% opus / 65% sonnet / 5% haiku — read-only milestone meant less codegen, more spec/contract work.
- Sessions: few; the 10-plan footprint collapsed multiple phases into single sessions.
- Notable: the smallest milestone of the project by plan count (10 plans / 4 phases) delivering 30/30 requirements — proves the read-only/zero-new-entities approach when the data model already supports the feature.

---

## Milestone: v1.9 — Trainers Complete

**Shipped:** 2026-05-26
**Phases:** 4 (58–61) | **Plans:** 22

### What Was Built

The last incomplete business domain — Trainers — moves from catalog-only (v1.4) to ✅. New `app/modules/payroll/` (17th `modules-independent` entry, zero new `ignore_imports`) ships an owner-configurable comp model (commission_pct_bps + session_fee_kopecks, both nullable) plus an append-only `trainer_payroll_accruals` ledger (UNIQUE `(trainer_id, period_start, period_end)` so the DB arbitrates duplicate-period races; `INSERT ... ON CONFLICT DO NOTHING RETURNING` discipline; rate snapshot at run time; pending→paid idempotent; PT-package refund → same-UoW negative clawback row via `PayrollClawbackRecorder` Protocol slot). Rounding ratified mid-milestone (D-PAYROLL-ROUNDING corrected from banker's-rounding to integer `math.ceil` in trainer's favor) — `compute_accrual_components` became the single source of truth shared by preview/accrual/clawback paths. Recurring slot patterns + `trainer_time_off` blocks landed via Alembic 0042; a daily ARQ cron `generate_recurring_slots` (04:00 UTC, `unique=True`) materializes concrete `trainer_availability_slots` over a `RECURRING_SLOT_HORIZON_DAYS` env (default 56), skipping time-off windows and emitting `slot_published` only on real inserts. Time-off creation cascades active-slot cancellation + DM via the existing notification machinery; overlap with booked slots returns 409 unless `?force=true`. The v1.8-deferred Trainer-Usage report shipped with a single 4-CTE raw-SQL `text()` read (session/slot/revenue/payroll aggregates) + UTF-8-BOM CSV — strictly read-only (D-54-07/08 maintained), signed-SUM payroll netted with clawbacks so RPT-04 reflects refund reality. Phase 61 regenerated `openapi.json` + `schema.d.ts` byte-stably with all 14 v1.9 path×method combos, `_v19Checks` `AssertNonNever` tuple with `toHaveLength(14)`, and a fully green milestone-gate (2181/6 pytest, 4/4 RBAC parity, 3/3 route introspection, 121/121 reception-403, lint-imports + drift gates clean).

### What Worked

- **Pre-flight `D-RBAC-VERIFY` saved a phase of churn** — flagging "read `permissions.py` + `can.ts` first to check whether `Resource.PAYROLL/COMPENSATION` already exist" before Phase 58 implementation cut a likely false-start; the discipline of *verifying assumptions about existing scaffolding* on a milestone touching ground covered in v1.4 paid off cleanly.
- **Mid-milestone D-PAYROLL-ROUNDING correction caught the right way** — the CONTEXT D-58-04 conflict (banker's-rounding intent vs. ceil-in-trainer's-favor implementation) surfaced during Phase 58 implementation, was ratified to ceil 2026-05-25, REQUIREMENTS.md L109 updated, and no code change was needed — proving that locked decisions can still be corrected when reality contradicts them, *if* the conflict is surfaced before it ossifies.
- **Single `compute_accrual_components` helper became a real PITFALL preventer** — T-58-23 (PITFALL 1) was caught not by a checklist but by reusing the same function across preview/accrual/clawback. Refactoring to one helper before the second call site existed eliminated the entire class of "preview shows X, accrual writes Y" bugs.
- **`INSERT ... ON CONFLICT DO NOTHING RETURNING` for DB-arbitrated races (D-58-06)** — replaced app-layer "check then insert" with a single statement where the DB decides; pattern reused for the recurring-slot materialization cron and was the cleanest concurrency story in any payroll system the codebase had attempted.
- **Operator-deferral pattern now a well-worn groove** — D-61-12 runbook walkthrough deferral mirrors v1.4 CARRY-01, v1.7 VER-03, v1.8 D-12 exactly; the pattern is now load-bearing and the milestone closed without anyone needing to justify it.

### What Was Inefficient

- **CLI one-liner extractor STILL produces noise (3rd milestone in a row)** — `milestone.complete` again grabbed `One-liner:` literal field labels and Rule-1-Bug deviation bullets instead of phase one-liners; MILESTONES.md required full manual rewrite. v1.7, v1.8, and v1.9 have all hit this. The extractor is no longer worth running for accomplishments; the discipline is now "let it create the entry, then overwrite the body."
- **REQUIREMENTS.md REC-01..04 checkboxes drifted unfixed through Phase 59 close** — the audit caught it (rows 24-27 + traceability 89-92 stale `[ ]` / Pending), but it should have been fixed at Phase 59 verification time, not at milestone close. Phase-close checklists need a "flip REQUIREMENTS.md rows now" step.
- **Pre-close audit-open false-positives persist** — same noise as v1.8: stale debug-session marker, completed-but-flagged quick task, UAT-status normalizer still missing. Three milestones running of the same warnings being acknowledged-then-ignored.
- **Phase 61 had a 2-call milestone.complete (duplicate v1.9 entry in MILESTONES.md)** — the CLI was called twice during this very close-out, producing duplicate sections that needed manual deduplication. Either the CLI should be idempotent on existing-version detection or the orchestrator should check before re-calling.

### Patterns Established

- **Versioned comp-config + snapshot-at-accrual** — config updates INSERT a new row with `is_current=true` (partial UNIQUE arbitrates), past accruals keep their snapshot rate. Mirrors v1.2 mandatory price snapshot but generalized to any rate-bearing config that history should preserve.
- **Cron `function_names ⊆ function_names` invariant** — added a test that recurring-slot cron is registered in both the cron map and the function registry; prevents the v1.3 REG-29-03 / v1.5 REG-40 family of "cron job declared but worker can't find it" runtime failures.
- **Signed-SUM netted aggregates in reports** — RPT-04 net-of-clawback uses `SUM(amount_kopecks)` over signed rows (positive accrual + negative clawback in the same table) so the read query "just works" without subqueries. Pattern transplants v1.4 ledger discipline to the report-aggregation layer.
- **Same-UoW Protocol-slot cascades for cross-module refund effects** — `PayrollClawbackRecorder` extends the v1.4 `payment_recorder` + v1.5 `BookingSlotRestorer` pattern: a refund flow consumes a Protocol slot that lives in another module without importing it, and the cascade row is written in the *same* commit as the refund itself.

### Key Lessons

1. **Stop trusting the auto-extractor for MILESTONES.md.** Three milestones in a row of the same problem. Either fix the source-of-truth (`one_liner` field placement in SUMMARY.md) or commit to hand-writing the entry from phase summaries — running the CLI then rewriting is the worst of both worlds.
2. **Documentation drift is a phase-close concern, not a milestone-close concern.** REC-01..04 checkboxes should have flipped at Phase 59 verification; carrying it to milestone close created audit noise. Phase-completion needs an "update REQUIREMENTS.md rows for this phase's reqs" gate.
3. **Locked decisions remain editable when reality demands.** D-PAYROLL-ROUNDING was "locked" pre-Phase 58 and corrected mid-phase 58 when implementation revealed the conflict with D-58-04. The mechanism (REQUIREMENTS.md edit + audit-log entry noting the correction) worked; the lesson is to not treat "locked" as "frozen" — treat it as "if you change this, document why."
4. **The milestone shipped in 2 days because every pattern was a copy.** v1.9 invented essentially zero new architecture — payroll ledger = v1.4 payments ledger; recurring cron = v1.3 expiring cron + v1.5 booking-reminder cron; trainer report = v1.8 reports module discipline. The каркас's "поэтапно наращивать без переписывания структуры" core value paid off most clearly here.

### Cost Observations

- Model mix: Opus 4.7 for orchestration + plan-phase; Sonnet 4.6 for executor + verifier agents. Roughly 30% opus / 65% sonnet / 5% haiku.
- Sessions: ~6, with Phase 58 doing the heaviest single session (9 plans).
- Notable: 22 plans across 4 phases at 0 inline product-code regressions reported in the milestone audit. The all-business-domains-✅ milestone arrived with under 3 days of wall-clock work — the structural payoff of v1.0–v1.8 bedrock.

### Cost Observations

- Model mix: Opus 4.7 for orchestration + plan-phase; Sonnet 4.6 for executor + verifier agents. Roughly 35% opus / 60% sonnet / 5% haiku — slightly more opus-weighted than v1.7 given the smaller, more judgment-heavy milestone.
- Sessions: few; the milestone's small size (10 plans) meant several phases collapsed into single sessions.
- Notable: the highest value-per-plan ratio of the project — 30 requirements delivered in 10 plans by consuming, not building, infrastructure.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v1.0 Phase A | 3 | 17 | Skeleton-only; `import-linter` and quality tooling shipped before any business code |
| v1.1 Auth + Clients | 11 (incl. 3 gap-closure) | 63 | Gap-closure phases (12/13/14) introduced; OpenAPI drift gate; Protocol-based cross-module callbacks; SAVEPOINT test isolation |
| v1.2 Memberships + Visits | 9 | 36 | DB-level race-proof constraints (`GENERATED STORED` + composite UNIQUE); first real ARQ scheduled cron; second + third Protocol-based cross-module slots; locked code-constant copy for security-sensitive bot DMs; inline UAT issue fixing |
| v1.3 Memberships Extras + Tech-Debt | 6 | 33 | `LOCKED_AUDIT_EVENTS` pre-registration discipline; milestone-verification-as-phase replacing standalone audit doc; second ARQ scheduled cron with ordered buffer; per-client anti-oracle hash-bit variant for locked copy; inline regression fixes during verification phase |
| v1.4 Cash Sales + PT Packages | 7 | 22 | Append-only `payments` ledger with AST walker forbidding UPDATE/DELETE/on_conflict; signed-amount/subject CHECK; `payment_row_hash` SHA-256 traceability; pivot to backend-complete + API handoff (frontend descoped to v2.0); inline regression-cap discipline (≤5 hard cap) |
| v1.5 Schedule + Bookings (PT slots) | 4 | 20 | Race-safe partial UNIQUE `(slot_id) WHERE status='confirmed'`; bot `/book` self-service via `create_booking_via_bot` (NULL actor + `actor_role` Literal); 23:10 no-show cron + 06:35 reminder cron with `booking_notifications` idempotency; module-scope locked DM copy (D-39-02); DEFER pattern for runbook-scaffolding gaps |
| v1.6 Email channel + Multi-user admin | 6 | 82 | `LOCKED_EMAIL_TEMPLATES` AST gate (parallel to `LOCKED_AUDIT_EVENTS`); INSERT-only re-claim discipline on partial-UNIQUE soft-delete; `actor_email_snapshot` denormalised audit; `_constant_time_floor` try/finally; in-phase gap-closure waves; agent structural attestation for owner-sign-off items; second Protocol-double-wire pattern (EmailDispatcher); 11 Alembic migrations in one milestone |
| v1.7 Online Payments + 54-ФЗ | 7 | 47 | Async adapter wrapping a synchronous SDK behind frozen-dataclass boundary + respx fixtures; AST gate on `YOOKASSA_TRUSTED_IPS`; webhook security = IP allowlist + status re-fetch (no HMAC) with value-granting locked to the verified webhook; fiscal obligation FK'd to the committed ledger row; circuit-breaker + cross-channel discriminator transplanted from v1.6; 0/5 inline regressions across 47 plans (best ratio yet); operator-deferral pattern for credential-gated verification |
| v1.8 Reports + Audit Log read API | 4 | 10 | Read-only module discipline (D-54-07/08: no `models.py`, raw-SQL `text()` cross-module reads, zero writes against business tables, SVC001 N/A); UTF-8 BOM + RFC-4180 excel CSV for Cyrillic-safe export (D-11); keyset pagination `ORDER BY created_at DESC, id DESC` with composite btree index for stable concurrent reads; DST golden-test as correctness anchor shared between automated test + operator runbook; smallest-milestone-ever (10 plans / 4 phases) by consuming existing tables instead of building |
| v1.9 Trainers Complete | 4 | 22 | Versioned comp-config with snapshot-at-accrual rate (generalization of v1.2 price snapshot to any rate-bearing config); `INSERT ... ON CONFLICT DO NOTHING RETURNING` for DB-arbitrated races (D-58-06) reused in payroll accrual + recurring-slot materialization cron; `cron_function_names ⊆ function_names` invariant test preventing v1.3/v1.5-class registration-drift failures; signed-SUM netted aggregates in reports (positive accrual + negative clawback in one table → no subqueries); locked-decision-correction discipline (D-PAYROLL-ROUNDING ratified mid-Phase 58 when CONTEXT D-58-04 conflict surfaced) — all 8 business domains ✅ |
| v1.10 clubcore Rebrand (in progress) | 1 (Phase 62) | 7 | Single-phase milestone narrowed per D-10-SPLIT; project rename `sportzal → clubcore` across pnpm packages, localStorage (Zustand `version: 1 → 2` copy-on-read+delete), Redis namespace (operator FLUSHDB), Postgres DB (operator pg_dump/restore), `CLUBCORE_EMAIL_FROM → SPORTZAL_EMAIL_FROM (legacy)` fallback chain, `CLUB_BRAND` constant extraction (placeholder value retained per D-62-02); forward-only `.planning/` rewrite + `HISTORICAL_NOTE.md` audit-trail boundary (D-62-09 / D-10-HISTORY-IMMUTABLE) — historical `phases/47-61/*` + `audits/*` intentionally immutable |

### Cumulative Quality

| Milestone | Backend LOC | TS LOC | REQ Satisfied | Tests |
|-----------|-------------|--------|---------------|-------|
| v1.0 | ~46 files | unchanged | 47/47 | 3 |
| v1.1 | ~52 files (~4.4K LOC) | ~12.8K LOC | 70/70 | 132 unit + integration suites for auth/RBAC/clients/persistence/search |
| v1.2 | ~8.1K LOC backend | ~16.8K LOC | 63/63 (2 accepted-deviations) | 569+ backend (incl. VIS-TEST-01 concurrent race + ARQ-TEST-01/02 cron correctness/idempotency) + 184+ admin-web |
| v1.3 | ~9.9K LOC backend | ~18.8K LOC | 44/44 (1 mock-mode UX deferred) | 729 backend (incl. 16-cell freeze state-machine matrix + expiring-soon idempotency + renewal date strategy) + 233 admin-web |
| v1.4 | ~12K LOC backend (+2.1K) | unchanged (frontend descoped) | 61/61 in-scope (FE-11..18 to v2.0) | 1027 passing / 44 carry-over failures → DEFER-36-04-A; 20/20 race tests across 7 files |
| v1.5 | ~12.6K LOC backend | unchanged | 57/57 mapped (1 runbook deferred) | 1100+ backend (incl. 4 new locked DM templates + booking_notifications idempotency + 2 cron jobs) |
| v1.6 | ~14K+ LOC backend (new `users/`, `integrations/email/`) | unchanged | 48/48 (VER-12 + VER-14 deferred to v1.7) | 1100+ backend + 76 OpenAPI forward-guards (65 → 76) + 6 real-Postgres race tests + 2 anti-oracle integration tests + 2 AST gates green |
| v1.7 | ~37.7K LOC backend (new `online_payments/`, `online_refunds/`, `fiscal_receipts/`, `integrations/yookassa/`; Alembic at 0039) | unchanged (frozen mock reference) | 48/51 delivered (CARRY-01/02 + VER-03 operator-deferred) | 1992 passed / 0 failed after test-debt sweep; +16 Phase 53 tests (14 real-Postgres race + 2 circuit-breaker parity); 0/5 inline regressions; DEFER-46-03 + DEFER-36-04-A both CLOSED |
| v1.8 | ~37.7K LOC backend (new read-only `app/modules/reports/`; Alembic at 0040, +3 audit-log indexes) | unchanged (frozen mock reference) | 30/30 (VER-01 live runbook operator-pending per D-12) | 2181-ish backend + 68 reports tests + 8 `_v18Checks` AssertNonNever forward-guards + `toHaveLength(8)` runtime + DST golden test |
| v1.9 | new `app/modules/payroll/` + extended `app/modules/schedule/` (recurring + time-off) + new `reports/trainers` endpoint; Alembic at 0042 (0041 payroll + 0042 recurring/time-off) | unchanged (frozen mock reference) | 15/15 (D-61-12 live runbook operator-pending) | 2181 backend passed, 6 skipped + 121 reception-403 + 4 RBAC parity + 3 route-introspection + 14 `_v19Checks` forward-guards + `toHaveLength(14)` runtime; lint-imports 3 kept / 0 broken; drift gates clean |

### Top Lessons (Verified Across Milestones)

1. **`import-linter` from Phase A is non-negotiable** — saved real time in v1.1 by catching cross-module imports during Phase 4 + Phase 7. Keep enforcing.
2. **Pin contract primitives before the first business migration** — v1.1 Phase 4 doing this proactively meant zero retrofit work in Phases 5/8. Apply to every future contract surface (e.g. multi-tenancy ContextVar, if it ever enters scope).
3. **Verification artifacts gate milestone closure, not phase closure.** The audit-driven `/gsd-complete-milestone` workflow correctly forced the v1.1 close to wait for Phase 14 + the 70/70 REQ coverage instead of declaring done at Phase 11.
