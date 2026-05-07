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

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v1.0 Phase A | 3 | 17 | Skeleton-only; `import-linter` and quality tooling shipped before any business code |
| v1.1 Auth + Clients | 11 (incl. 3 gap-closure) | 63 | Gap-closure phases (12/13/14) introduced; OpenAPI drift gate; Protocol-based cross-module callbacks; SAVEPOINT test isolation |

### Cumulative Quality

| Milestone | Backend LOC | TS LOC | REQ Satisfied | Tests |
|-----------|-------------|--------|---------------|-------|
| v1.0 | ~46 files | unchanged | 47/47 | 3 |
| v1.1 | ~52 files (~4.4K LOC) | ~12.8K LOC | 70/70 | 132 unit + integration suites for auth/RBAC/clients/persistence/search |

### Top Lessons (Verified Across Milestones)

1. **`import-linter` from Phase A is non-negotiable** — saved real time in v1.1 by catching cross-module imports during Phase 4 + Phase 7. Keep enforcing.
2. **Pin contract primitives before the first business migration** — v1.1 Phase 4 doing this proactively meant zero retrofit work in Phases 5/8. Apply to every future contract surface (e.g. multi-tenancy ContextVar, if it ever enters scope).
3. **Verification artifacts gate milestone closure, not phase closure.** The audit-driven `/gsd-complete-milestone` workflow correctly forced the v1.1 close to wait for Phase 14 + the 70/70 REQ coverage instead of declaring done at Phase 11.
