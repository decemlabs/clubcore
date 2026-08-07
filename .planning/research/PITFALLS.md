# Pitfalls Research: v4.1 Codebase Hardening

**Domain:** Audit-and-fix ("hardening") milestone on an existing, fully-shipped full-stack system — FastAPI modular monolith + two React frontends + locally-validated k3s infra, zero new features.
**Researched:** 2026-07-26
**Confidence:** HIGH (grounded directly in this repo's locked invariants, documented decisions, and its own two-time-repeated defect class — not generic advice)

## Executive framing

This milestone's entire justification is a repeated failure mode already recorded in `PROJECT.md`: mock-based unit tests passed a real schema divergence bug **twice** (v3.0, v3.1), caught only by manual browser UAT. A hardening milestone with no new features has no natural "done" signal — the only thing that stops it from becoming a second uncontrolled rewrite is a fixed, pre-committed contract: a closed-set DEFECT registry, a scope firewall, and an honest ledger of what could not be verified. Every pitfall below is a way that discipline erodes.

---

## Critical Pitfalls

### Pitfall 1: The audit phase never closes (infinite refactor / scope creep)

**What goes wrong:**
The audit finds more defects than the fix phases can close, and each fix phase's own code review surfaces new findings, so the registry grows faster than it shrinks. "While we're in here" upgrades creep in (bumping FastAPI/SQLAlchemy/Pydantic/Zod/TanStack versions, reformatting whole files, "just fixing this one other thing nearby").

**Why it happens:**
This system has ~10K+ LOC backend, ~19K LOC+ frontend across two apps, 9+ milestones of accretion, and an explicit backlog of 32 TODO/FIXME/HACK plus 23 v4.0 operator-pending items. An open-ended "fix everything" goal against that surface area has no natural stopping point; auditors are rewarded (in the moment) for finding more, not for closing the loop.

**How to avoid:**
- The audit phase produces the registry **once**, as a single frozen artifact (id + severity + category + file/screen), before any fix phase starts. Fix phases consume the registry; they do not reopen the "find more issues" activity.
- Any defect discovered *during* a fix phase (code review, contract test failure) gets appended to the SAME registry with a new id and a `discovered-during-fix` tag — it does not silently get fixed inline without being logged, and it does not trigger a new audit sweep.
- Hard rule: no dependency-version bumps in this milestone unless a bump is itself the fix for a specific registered CVE/defect id. Versions are Out of Scope by default (v4.1 is stated to touch zero new business/infra surface).
- Reformatting is confined to files already touched by a registered fix; a repo-wide `ruff format` / `prettier --write` pass (if wanted) is its own single, isolated, reviewable commit — never bundled into a functional fix diff.
- Track two numbers from day one: registry size (should only shrink after audit closes) and "items closed per phase." If registry size grows after the audit phase is declared closed, that is the warning sign to stop and re-scope, not to keep going.

**Warning signs:**
- Registry item count increases week-over-week after the audit phase is marked complete.
- Diffs in "fix" commits touch files with no corresponding registry id.
- A fix PR/commit description contains "while I was in here" or "also upgraded X."
- Git blame on a file changes wholesale (formatting-only diff) mixed with a functional change in the same commit.

**Phase to address:** Audit phase (registry freeze) + a standing rule enforced by every fix phase's plan/commit template.

---

### Pitfall 2: Mass reformatting destroys git blame and review signal

**What goes wrong:**
A well-intentioned "let's finally run ruff format / prettier across everything" pass touches hundreds of files, burying the handful of real functional fixes inside noise. Reviewers (and future `git blame`/`git bisect`) can no longer distinguish "this line changed because of a bug fix" from "this line changed because a formatter moved a comma."

**Why it happens:**
Hardening milestones invite exactly this because tidiness is explicitly in scope ("код-гигиена"). It feels efficient to batch it.

**How to avoid:**
- Formatting-only changes go in their own commit(s), clearly labeled `chore(format): ...`, never mixed with a `fix(...)` commit touching the same file's logic.
- If both are needed in the same file, format FIRST in an isolated commit, THEN apply the functional fix as a second commit — reviewers diff the second commit against clean-formatted code, not against a reformatted+refactored blob.
- Prefer `git blame -w` (ignore whitespace) as the acceptance check that formatting commits didn't hide anything.

**Warning signs:** A single commit's diff stat shows hundreds of files changed with the same one-line functional description.

**Phase to address:** Code-hygiene fix phase; enforced as a commit-hygiene rule for the whole milestone, not just that phase.

---

### Pitfall 3: Deleting code that only "looks" dead (false-positive dead-code removal)

**What goes wrong:**
Static dead-code detection (unused-export scanners, `vulture`, IDE "no references" hints) flags something as unreachable, it gets deleted, and a *runtime-only* reference breaks: a dynamic import, a string-keyed dispatch table, an Alembic migration's inline model snapshot, an ARQ cron entrypoint registered by string path, or a Protocol-slot implementation wired only at the composition root (`app/main.py`).

**Why it happens in THIS codebase specifically:**
- **ARQ cron entrypoints** (`expire_memberships`, `send_expiring_notifications`, `mark_no_show_bookings`, `send_booking_reminders`, `charge_expiring_autopay`, `monitor_stale_fiscal_receipts`, `poll_pending_refunds`, etc.) are referenced by string/module path in ARQ worker settings, not by direct Python import in the "business" module — a static analyzer walking import graphs from `app/main.py` will not see the edge.
- **Protocol-slot registrations** (`ActiveMembershipResolver`, `register_user_loader`, `HandlerContext`, `PayrollClawbackRecorder`, `UserSessionInvalidator`) are wired ONLY at the composition root (`app/main.py`) per this project's explicit cross-module discipline (D-20-MODULE). A grep for the Protocol's usage inside its "home" module will show zero call sites — looking dead — when the real wiring lives in a completely different file.
- **Migration-referenced code**: Alembic revisions (0001–0063+) frequently embed inline copies of ORM shapes or raw SQL as they existed at that revision. A "dead" helper function still referenced from an old migration's `upgrade()`/`downgrade()` will break `alembic downgrade` / a fresh `alembic upgrade head` replay even though nothing in current `app/modules/*` calls it.
- **AST literal-string commit gates**: `LOCKED_AUDIT_EVENTS` (frozenset) and `LOCKED_EMAIL_TEMPLATES` are validated by an AST walker that requires the literal string to appear at every callsite — code that emits these via a variable/lookup (which might look like unreachable/duplicate logic to a naive dedup pass) is intentionally structured that way; "simplifying" it to a lookup table breaks the gate itself, not just runtime behavior.
- **Telegram bot handlers** (`app/workers/telegram_bot.py`) are dispatched by python-telegram-bot's internal handler registry (string command / regex match), not by direct call from the module a static scanner starts from.
- **Frontend**: TanStack Router's file-based route tree (`src/routeTree.gen.ts`, generated) references route files that a component-level "unused export" scanner won't see as imported; a component reachable only via `router.tsx`'s lazy-loaded ComingSoon→real swap is a second, distinct case (see Pitfall 9) that looks identical to actually-dead code from a pure import-graph view.
- **`nav-items.ts`** entries and Zod schemas used only inside `@hookform/resolvers` wiring can look "unused" to naive tools that don't trace through generic type parameters.

**How to prove code is actually dead before deleting (concrete, checkable procedure):**
1. Run TWO independent tools and require agreement: a Python import-graph/usage tool (e.g. `vulture` in low-confidence mode, or `ruff --select F401,F811` plus a manual grep) AND a full-text grep for the symbol name across the ENTIRE repo — not just `app/` — including `alembic/versions/*`, `app/workers/*`, YAML/JSON config (ARQ cron schedule config, k8s manifests, Helm values), and test fixtures.
2. Grep specifically for the symbol as a STRING literal, not just as a Python identifier (`"expire_memberships"`, `'ActiveMembershipResolver'`) — this catches string-referenced/dynamic dispatch that AST-based tools miss.
3. For anything touching `app/main.py` composition-root wiring, Protocol slots, or `app/workers/`: treat "no direct call site in its home module" as INSUFFICIENT evidence of deadness — explicitly check `app/main.py` wiring and ARQ registration config before deleting.
4. For anything under `alembic/versions/`: never delete migration-referenced helper code; migrations are immutable historical artifacts (mirrors this project's own `.planning/HISTORICAL_NOTE.md` / D-62-09 precedent of "forward-only, never rewrite history"). If a helper only exists for a migration, leave it in place or move it inline into that migration file — do not delete it from the shared module.
5. Delete in a dedicated commit, run the FULL test suite subset that touches the deleted area (see Pitfall 4 for how to do this despite the broken suite) plus `alembic upgrade head` from a fresh DB and `alembic downgrade -1` at least one step, plus a k3d cron smoke-trigger for any ARQ job touched.
6. For frontend: after deletion, run `tsc -b` (catches import breaks) AND grep `routeTree.gen.ts` + `nav-items.ts` + all `.test.tsx` snapshot/mock fixtures for the symbol name as a string.
7. Never delete based on a single tool's confidence score alone — this codebase's dispatch patterns (string-keyed, Protocol-slot, AST-gated) are specifically the patterns that fool single-tool dead-code detection.

**Warning signs:**
- A "dead code removal" commit touches only one file with no corresponding test run of the ARQ scheduler, migration replay, or composition root.
- The removed symbol's name matches an ARQ cron function, anything under `app/integrations/`, anything with `Protocol` in a nearby docstring, or anything mentioned in `LOCKED_AUDIT_EVENTS`/`LOCKED_EMAIL_TEMPLATES`.
- CI's import-linter or mypy passes but a k3d cron smoke check or `alembic downgrade` fails post-merge.

**Phase to address:** Static-audit phase should PRE-FLAG these categories (any symbol touching ARQ workers, Protocol slots, AST-gated frozensets, or `alembic/versions/`) as "requires manual grep + composition-root check" rather than routing them through automated dead-code tooling at all. The dead-code fix phase should treat this list as a standing checklist per deletion, not a one-time review.

---

### Pitfall 4: Treating the pre-existing broken test suite as either "fix it all first" or "ignore it entirely"

**What goes wrong:**
Two failure modes, both real risks for this milestone:
(a) **Rabbit-holing**: the team decides the fixture deadlock (`permissive_booking_config` × `working_hours_config` autouse fixtures) must be fixed before any hardening work can be trusted, and burns the whole milestone on test-suite archaeology instead of closing DEFECT-registry items.
(b) **Unverified shipping**: the team declares the suite "known broken, not our problem" and ships functional fixes with no proof they didn't regress anything, because "the tests don't run anyway."

**Why it happens:**
The project's own history shows this exact suite has carried flakes across MULTIPLE milestones already (`test_freeze_race`, promo F821, `test_alembic_clean` — explicitly noted as "NOT v2.4 regressions" back in that milestone, and still present at v4.1 open). It's tempting to treat "fixing the test infra" as satisfying, high-value work — it is neither bounded nor the actual goal — or conversely to treat it as someone else's problem forever.

**How to avoid (disciplined middle path):**
1. **Triage the broken suite as its OWN registry items in the audit phase**, each with an id, not as ambient background noise. Classify each: (i) the fixture-ordering deadlock (structural, likely a single root-cause fix — a shared/ordered fixture scope), (ii) `test_freeze_race` flake, (iii) promo F821 (a lint-level bug, probably trivial), (iv) `test_alembic_clean`.
2. **Fix ONLY the items that block running the suite at all** (the deadlock) as a bounded, capped-effort fix — because it is the actual verification tool for every other fix in this milestone. This is not optional: if pytest cannot complete a run, no other fix in this milestone can be proven, which defeats the milestone's own done-bar ("fixed+verified").
3. **Time-box the deadlock fix.** If root-causing the autouse fixture interaction exceeds a fixed budget (e.g., one phase), the fallback is NOT "give up on verification" — it is to isolate: run the affected test modules in fixture-scoped subprocess isolation (`pytest -p no:randomly --dist=no` per-module, or explicit `-k` module segmentation) as a documented workaround, and defer the *root cause* fix as its own registry item with `deferred` status and a reason.
4. **The other pre-existing flakes (F821, `test_alembic_clean`) get fixed opportunistically but are NOT gates** for closing this milestone's functional-fix items — they were pre-existing before v4.1, are logged as their own registry entries, and can legitimately be marked `deferred` with reason "pre-existing, not a regression, tracked independently" if time runs out — but only if explicitly recorded, never silently dropped.
5. **Every functional fix in this milestone must show a passing, targeted test run** (not "the whole suite is green" — that may never be fully achievable given item 3's workaround) as its proof: a contract test against real backend response (per the v3.0/v3.1 lesson already baked into this project's convention) plus the specific unit/integration tests for the touched module, run in isolation if the global suite can't complete.
6. Never let "pytest exits with the deadlock" become an excuse to skip running ANY tests for a fix — the isolation workaround in item 3 exists precisely so this never happens.

**Warning signs:**
- A phase's entire time budget goes to test-infra work with zero DEFECT-registry items closed.
- A fix's "proof" section says "tests aren't running right now" instead of a scoped, isolated test run's actual output.
- The same flaky test names recur in phase-close notes across MULTIPLE hardening phases with no registry id attached.

**Phase to address:** Audit phase registers all pre-existing test-suite defects with ids and severities. A dedicated early fix phase (before or parallel to the first functional-fix phase) resolves ONLY the fixture-deadlock (verification-blocking) item, time-boxed, with a documented isolation fallback if it can't be root-caused in budget. All later fix phases depend on this phase's isolation/fix being in place as their verification tool.

---

### Pitfall 5: Regressing a LOCKED invariant while "just cleaning up"

**What goes wrong:**
A refactor pass — renaming a constant, "simplifying" an enum, deduplicating what looks like repeated code, reordering an import to satisfy a linter — silently breaks one of this system's byte-parity or AST-gated invariants:
- RBAC byte-parity between backend `Resource`/`Action`/`OWNER_ONLY` StrEnums and frontend `can.ts`/`registry.ts` (CISO-01, 41 entries).
- The `LOCKED_AUDIT_EVENTS` frozenset + the AST literal-string commit gate on `audit.emit` callsites (currently 34+ entries and growing across milestones; SVC001 gate on `auth/service.py`).
- The `LOCKED_EMAIL_TEMPLATES` frozenset + AST gate on `get_email_dispatcher()` callsites.
- Byte-stable `apps/backend/openapi.json` → `packages/api-client/src/schema.d.ts` drift gate.
- The 3 import-linter contracts on backend layers (raw-SQL cross-module reads / Protocol-slot cross-module writes discipline, D-20-MODULE).
- ESLint `import/no-restricted-paths` layer boundaries + `VITE_API_MODE` chokepoint rule + raw-Tailwind-palette ban, each with negative-test fixtures that themselves must still fail correctly.

**Why it happens:**
These invariants are enforced by gates that are easy to satisfy ACCIDENTALLY-WRONG during a refactor: e.g. moving a `Resource.X` enum member to a different file can keep mypy/ruff green while breaking the byte-parity test if the frontend mirror isn't touched in the same commit; renaming a variable that happens to hold a `template_id` literal turns a compliant call into a non-literal one that the AST walker should reject — but only if the walker itself wasn't also "simplified" in the same pass, in which case it silently stops catching anything.

**How to avoid:**
- Before touching ANY file in `app/shared/rbac* ` / `can.ts` / `registry.ts` / anything importing `LOCKED_AUDIT_EVENTS` or `LOCKED_EMAIL_TEMPLATES` / `openapi.json` / `schema.d.ts` / `.importlinter` / `eslint.config.js`'s restricted-paths rules: run the FULL corresponding gate BEFORE and AFTER the change, not just at milestone-end. These are cheap, fast, local checks per this project's own tooling constraint ("архитектурные правила должны быть выполнимы локально") — there is no excuse to defer running them per-commit.
- Any change to a LOCKED enum/frozenset/contract requires a corresponding same-commit update to its parity mirror (frontend `can.ts` for RBAC, `schema.d.ts` regen for OpenAPI) — never split across commits, because a partial state is exactly what a later "cleanup" pass might misinterpret as the new steady state.
- Negative-test fixtures (the illegal-import / API-mode-leak / raw-palette / RBAC-drift fixtures) must be re-run after ANY change to the gate/rule code itself, to prove the gate STILL fails on the bad input — "the linter passes" is not proof the linter still works if the linter itself was touched.
- Treat every one of these gates as a phase-exit checklist item, not just a CI checkbox: a human (or reviewing agent) explicitly confirms "I ran gate X against before/after" for any phase that touched adjacent code, even if the diff looks unrelated.

**Warning signs:**
- A diff touches an enum, frozenset, or `can.ts`/`registry.ts` file but the corresponding parity/drift/AST-gate test file has zero changes in the same commit.
- CI green but the specific negative-test fixture (`raw-palette.tsx`, `api-mode-leak.ts`, `features/illegal-mock-import.ts`) wasn't re-verified to still trip its rule after a lint-config touch.
- A "simplification" of an AST-walking gate (e.g., "let's make this walker also accept f-strings for convenience") — treat any change to the gate's own logic as maximally high-risk, requiring its own dedicated review.

**Phase to address:** Every fix/hygiene phase that touches RBAC, audit events, email templates, the OpenAPI contract, import-linter config, or ESLint config must run the specific named gate + its negative fixtures as an explicit phase-exit criterion — this is not delegable to "the milestone's final gate run."

---

### Pitfall 6: Verification-honesty erosion — fabricated, assumed, or silently-skipped evidence

**What goes wrong:**
Under time pressure, a "verified" registry item was actually just re-read (not re-run); an operator-pending item quietly gets marked `done`; browser UAT covers only the happy path and the registry item gets closed anyway; a k3d-local check stands in for something that was supposed to be operator-verified in a real cluster.

**Why it happens:**
This is a genuinely hard discipline to maintain across dozens of registry items, and this project has ALREADY needed an explicit decision to prevent it (D-V40-LOCAL-VALIDATE, "no fabricated evidence," directly following the D-67-03 precedent). The milestone inherits that discipline by design — but inheriting a decision is not the same as an enforced mechanism; without a mechanism it degrades under registry-item volume and phase-count pressure exactly like it would have without the decision at all.

**How to keep the registry honest (concrete, checkable):**
- **Every registry item's `fixed+verified` status must cite the EXACT evidence**: a command that was run + its actual output (or output file path), not a prose claim. "Verified via browser UAT" is not sufficient; "browser UAT screenshot at `.planning/evidence/DEFECT-041.png`, chrome-devtools console clean, checked with client `X` who has membership status=`frozen`" is.
- **Distinguish three states explicitly, never collapse them**: `fixed+verified` (evidence attached and re-checkable), `fixed+unverified` (code changed, but proof is missing/incomplete — NOT allowed to be the milestone's final state for any item that isn't explicitly deferred), and `deferred` (not fixed, with an explicit reason — hardware/credentials/out-of-scope). A registry item cannot silently move from "operator-pending" to "done" — that transition requires the SAME evidence bar as any other `fixed+verified` item, and if the blocking factor (hardware/creds) is unchanged, the transition is illegitimate and should be flagged by review.
- **Carry forward the v4.0 operator-pending boundary as an immutable list**: the 23 items (including the two HARD GATES — SEC-02 off-node sealed-secrets RSA-key backup, BAK-03 verified restore round-trip) do not get silently resolved by a k3d-only re-run in v4.1. If v4.1's k3d work touches BAK-03 (verified restore round-trip IN k3d), it must be recorded as a DISTINCT, narrower claim ("k3d-local restore round-trip verified") — not as closing the original v4.0 item, which specifically required real infrastructure. See Pitfall 12.
- **Items that require unavailable hardware/credentials are recorded, never dropped**: each such item stays in the registry with status `deferred: operator-pending`, an explicit trigger condition for re-evaluation (mirroring this project's own `N/A-until-production` pattern used repeatedly for ЮKassa-live-leg and RU email deliverability), and a pointer to exactly what would need to change (real node/hardware, live YooKassa production credentials, RSA off-node storage target) for it to become actionable. It is never silently removed from the registry, and it is never marked `fixed` because the surrounding code was touched.
- **Browser UAT explicitly must NOT be happy-path-only** — see Pitfall 8 for the concrete data-state matrix this requires; a registry item closed on UAT evidence must record which specific data states were exercised, not just "clicked through and it worked."
- **A second-pass spot-audit**: before the milestone's final gate, sample a subset of `fixed+verified` items and independently re-run their cited evidence command; any that fail to reproduce get reopened. This catches drift between "evidence was true when written" and "evidence quietly stopped being true."

**Warning signs:**
- A registry item's evidence field is prose without a command/output/screenshot reference.
- An operator-pending item flips to `done` without any new capability (hardware/creds) having become available.
- Multiple registry items closed in a short window all cite the identical generic evidence line (copy-paste "verified in browser").
- No registry items are in the `deferred` state at milestone close — for a system with 23 pre-existing operator-pending items plus real hardware/credential gaps, an all-`fixed+verified` result is itself a red flag, not a success signal.

**Phase to address:** The audit phase defines the registry schema (including the mandatory evidence field and the three-state model) before any fix phase starts. Every fix phase is gated on filling that field correctly, and the closing phase runs the spot-audit re-run before declaring done-bar met.

---

## Domain-Specific Deep Dives

### Pitfall 7: Missing Zod-vs-wire divergence instances because the hunt used well-formed test data

**What goes wrong:**
The team re-runs the exact bug class that bit this project twice (v3.0/v3.1) but still misses instances of it, because the "live backend" they tested against was seeded with clean, complete, non-edge-case data — the same blind spot that let mock-based unit tests pass before.

**Why this specifically happens here, concretely:**
- **Seeded data is well-formed by construction.** This project's seeds (`faker.seed(42)`, migration-seeded fixtures like `FIT15`, plan seeds, referral bonus seed values) were written to demonstrate the happy path, not to stress schema edges. A client with every optional field populated, a membership mid-lifecycle with no freeze history, a trainer with a bio/photo already set — none of these will surface a `nullable` field the FE Zod schema declared as required, because the field is never actually null in the seed.
- **Nullable-only-in-production fields**: fields that are `Optional[X] = None` in the SQLAlchemy model but were always populated during backend development/testing (e.g., a trainer never given a bio in dev, `previous_membership_id` only null for a membership with no renewal chain, `actor_user_id` intentionally NULL for bot-created bookings/audit rows per D-40-05) will pass a naive smoke test and only break for a REAL member who happens to lack that field.
- **Empty-state vs populated-state**: a client with zero visits, zero bookings, zero notifications, zero loyalty-ledger entries, an EMPTY promo/referral history — screens that branch on "empty" vs "has items" (dashboards, history tabs, the newbie-vs-active Home state) are exactly where an FE Zod schema's assumption about array-vs-null, or a computed aggregate's assumption about "at least one row," breaks. This project's own `membershipState: active|newbie|lapsed` branching is a documented example of a state that must be independently exercised.
- **Pagination envelopes**: this project's own convention is `{ items, total, page, pageSize }` for every list endpoint — but the FIRST page of a small seeded dataset, or a dataset with exactly one page, will never exercise `total > pageSize`, an empty subsequent page, or a `page` beyond `total/pageSize`. A Zod schema for the envelope that's subtly wrong (e.g., assumes `total` is always ≥ `items.length`) won't be caught without a dataset large enough to force multi-page traversal.
- **Error-shape divergence**: this project's error envelope is `DomainError { code, message, fields? }` server-side, and a `RequestValidationError` handler was specifically built (v1.11 Phase 64 WR-02) to normalize 422s into that shape — but 403/404/409/500 paths, rate-limit responses, and anti-oracle constant-time-floor responses (deliberately identical-looking across branches, e.g. OTP/password-reset) are all DIFFERENT code paths that each need their OWN Zod-vs-wire check; testing only the 200-success shape (or only one error family) leaves the others unchecked. Reception-403 enumeration is a documented existing pattern (121/121 test count referenced in v1.9) — the hunt for THIS milestone should reuse that discipline for the client-side error paths too, which don't have the same enumeration history.
- **Money/date edge values**: kopecks at zero, at a DST-boundary date (Europe/Moscow spring/fall transition), a membership `end_date` inclusive-boundary edge, a freeze period still open (`ended_at IS NULL`) — these are exactly the values this project's own domain conventions flag as hazardous (see CLAUDE.md "Never `new Date(dateOnlyString)`"), and exactly the values absent from a clean demo dataset.

**Test-data conditions that must be arranged for the hunt to be meaningful (concrete, checkable):**
1. A seeded dataset that includes, for EVERY entity the FE renders: at least one row with each nullable field actually NULL, at least one row with each optional field populated, and at least one row at each documented lifecycle state (membership: active/frozen/expired/renewed-chain; booking: confirmed/cancelled/no_show/completed; payment: succeeded/canceled/refunded-partial/refunded-full; fiscal receipt: sent/succeeded/failed).
2. At least one client with EMPTY history for every list-typed resource (zero visits, zero bookings, zero payments, zero notifications, zero loyalty entries, zero referrals) AND at least one client with enough rows to force pagination past page 1.
3. At least one trainer/plan/entity with every OPTIONAL/additive field (bio, specialization, photo_url, freeze_days_limit, autopay fields, notif_prefs) left unset, to catch a Zod schema that wrongly assumes presence.
4. At least one request per domain that deliberately triggers each error family (422 validation, 403 RBAC, 404 not-found/IDOR-collapse, 409 conflict/race, 429 rate-limit, and the anti-oracle-constant-response paths) — checked against the FE's error-parsing code, not just the success path.
5. At least one date/money edge case per domain: a membership with `end_date` on today (inclusive-boundary), an event timestamp crossing the Europe/Moscow DST transition, a zero-kopeck discount, a fully-redeemed loyalty balance.
6. This dataset must be run through BOTH admin and client frontends against the REAL backend (not mocks) — per this project's own established lesson, only browser UAT against live data catches this class; a re-run of existing seeded demo data is not new evidence, since it already passed before with the same blind spots.

**Warning signs:**
- The UAT dataset used for this milestone is the SAME seed used in previous milestones' demo/dev environments (i.e., no new edge-case seed was authored).
- Registry items for "Zod↔wire divergence" cluster only around domains that were recently built (v2.4+) and none are found in older, more mature domains — suggests the hunt didn't cover the full surface, or the newer domains are being over-scrutinized while older ones (which have had MORE time to drift from backend changes) are under-scrutinized.
- No registry items reference pagination, empty-state, or error-shape at all — a hunt that only found "wrong field name" bugs and none of these categories likely didn't construct the right data conditions.

**Phase to address:** Audit phase — specifically, before browser UAT begins, an explicit "seed the edge-case dataset" task must exist and be checked off, separate from and prior to the UAT walkthrough itself. This is the single highest-leverage prevention: it must happen BEFORE the hunt, not be discovered as a gap during it.

---

### Pitfall 8: Missing route-reachability bugs (wired-but-unreachable screens)

**What goes wrong:**
A screen is fully wired to the real backend, has passing unit tests, yet a real user can never reach it because `router.tsx` still renders the `ComingSoon` placeholder for that route and/or `nav-items.ts` has no entry pointing to it — the exact documented FND-04 lesson from this project's own history (bit multiple prior milestones: v2.4's D-71-09 placeholder-graduation lesson recurred across phases 86/87/88 despite being "caught" the first time).

**Why it happens:**
Wiring a screen (hooks, API calls, Zod schema, component tree) and making it REACHABLE (router entry + nav entry) are two distinct, decoupled steps, and only the first one has automated test coverage (component tests render the screen directly, bypassing the router). It is easy to verify "the screen works" in isolation and never verify "a user can navigate to it."

**How to avoid (concrete, checkable):**
- Every registry item of the form "wire screen X" must have TWO separate acceptance checks: (a) component/contract test passes, (b) an explicit reachability check — starting from the app's root nav, click/navigate through the real UI (not a direct URL hit) and confirm the screen renders, for BOTH `apps/admin` and `apps/client`.
- A dedicated, mechanical reachability SWEEP (not spot-checks) as its own audit-phase task: enumerate every route in `router.tsx` and every entry in `nav-items.ts` for both frontends, cross-reference them, and flag: (i) any route still pointing at `ComingSoon`/lazy-placeholder that has a real backend endpoint wired behind it, (ii) any route with no nav entry at all, (iii) any nav entry pointing at a route that doesn't exist or errors.
- Treat this sweep as a GREP-able, scriptable check (diff route list vs nav list vs "has real API calls" list) rather than a manual click-through alone — manual UAT should CONFIRM the sweep's findings in the browser, not be the only method of finding them, since manual click-through is exactly what missed this class of bug repeatedly before.

**Warning signs:**
- A registry item's evidence is "component test passes" with no navigation-from-root screenshot/log.
- `router.tsx` and `nav-items.ts` are not both listed as reviewed files in the audit phase's file list.
- Any screen graduated in v2.4+ is not re-checked in this sweep (this project's own history shows the SAME class of bug recurring across MULTIPLE already-graduated screens, so "it was fixed once" is not sufficient evidence it's still fixed after intervening changes).

**Phase to address:** Audit phase (mechanical reachability sweep as a standing, scripted check, separate from the Zod/wire browser-UAT pass) — should run BEFORE or alongside the schema-divergence hunt, since both need the same "walk the real app from nav" discipline.

---

### Pitfall 9: k3d-local infra verification is mistaken for production-equivalent proof

**What goes wrong:**
A "verified restore round-trip in k3d" or "k3d apply succeeded" gets treated, implicitly or explicitly, as equivalent to the still-open v4.0 HARD GATES (SEC-02 off-node key backup, BAK-03 verified restore round-trip) — even though those gates were specifically scoped to REAL hardware and were left open BY DESIGN (D-V40-LOCAL-VALIDATE).

**What k3d does NOT prove, specifically:**
- **Node failure / hardware loss**: k3d runs all "nodes" as containers on ONE host's Docker daemon. It cannot demonstrate what happens when an actual physical/VM node is lost, rebooted with different kernel/cgroup config, or has disk pressure independent from the host machine's disk. A "restore round-trip" in k3d proves the BACKUP JOB LOGIC and the RESTORE JOB LOGIC are correct — it does NOT prove the backup is retrievable when the ORIGINAL cluster (and the host machine's Docker state) is gone, which is the actual disaster scenario BAK-03 exists to cover.
- **Off-node secret custody (SEC-02)**: the entire point of "off-node" is that the sealed-secrets RSA private key is stored somewhere OTHER than the cluster/host that could be destroyed together. A k3d environment, by construction, has no real "off-node" — any storage target reachable from the same dev machine is not an independent failure domain. Local validation can prove "the backup command runs and produces a file"; it cannot prove "that file is actually recoverable when this laptop/host is unavailable."
- **Network topology and real ingress**: Traefik/cert-manager/NetworkPolicies behavior in k3d (single-host, often host-networking or simplified CNI) does not exercise multi-node pod-to-pod network policy enforcement, real DNS resolution, real TLS cert issuance against a public ACME endpoint (only staging/self-signed locally), or real firewall/router rules between nodes.
- **Storage durability**: SeaweedFS/CNPG/Redis persistence in k3d typically sits on the same physical disk as the host — it does not prove durability against physical disk failure, real replication across separate physical storage, or performance/IO characteristics of the intended production storage medium.
- **Scale/load characteristics**: resource limits, HPA behavior, and realistic CPU/memory contention under actual traffic are not exercised by a single-host k3d smoke test.
- **Time/clock and long-running behavior**: cron reliability across REAL node reboots, kubelet restarts, or multi-day uptime is not exercised by a short-lived k3d session.

**What must be EXPLICITLY recorded as still-unproven (not silently implied as covered):**
- Any v4.1 registry item that closes a k3d-local check must be labeled with the narrower claim it actually supports, e.g. "BAK-03 (k3d-scope): restore round-trip verified in k3d — does NOT satisfy the original v4.0 BAK-03 hard gate, which requires a real-node round-trip." The original v4.0 gate stays open in the registry, unchanged, referencing the SAME evidence bar it always had.
- SEC-02 (off-node RSA key backup) cannot be meaningfully advanced by k3d work at all if there is no genuinely separate storage target being exercised — if v4.1 does attempt a "test storage" off-node backup, the registry item should specify exactly what "test storage" means (is it actually a separate physical/account boundary, or just a different directory on the same machine?) and flag the latter as insufficient evidence for the real gate.
- The v4.0 23-item operator-pending boundary (`infra/runbooks/production.md`) must be carried into v4.1's DEFECT registry as an explicit, unmodified reference — v4.1 should ADD narrower k3d-scoped findings alongside it, never edit/close the original items based on k3d evidence alone.

**Warning signs:**
- Milestone-close language says "BAK-03 verified" or "SEC-02 closed" without a `(k3d-scope)` / `(local-only)` qualifier.
- The "off-node" storage target used for a SEC-02 test is on the same host/account as the cluster being backed up.
- Any claim that k3d work "resolves" or "closes" a HARD GATE from v4.0, rather than "advances local-provable groundwork for" it.

**Phase to address:** The locally-provable-infra fix phase (k3d apply, BAK-03/SEC-02 local legs) — every deliverable from this phase must be registered with an explicit scope qualifier, and the phase's own definition of done must include "the original v4.0 registry items remain open, unedited, with the new k3d findings referenced alongside them, not replacing them."

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|-----------------|-----------------|
| Marking a flaky pre-existing test `xfail`/skip instead of fixing the fixture deadlock | Unblocks the suite quickly | Hides future real regressions in that area permanently | Only for the NON-blocking flakes (F821, `test_alembic_clean`) — never for the fixture-deadlock itself, which blocks verification of everything else |
| Closing a Zod-vs-wire fix with only the happy-path contract test | Fast to write, quick registry close | Same defect class recurs (this is literally the v3.0/v3.1 failure) | Never — always pair with at least one edge-case data condition per Pitfall 7 |
| Deleting a Protocol-slot registration because its "home" module shows no call sites | Shrinks LOC, feels like progress | Silent runtime break at composition root, only caught in k3d/prod | Never without checking `app/main.py` wiring first |
| Bundling a dependency bump into a hardening fix "since we're touching this file anyway" | Saves a future separate effort | Reintroduces unbounded scope, breaks byte-stable/AST gates unexpectedly | Never in this milestone — explicitly out of scope |
| Treating a k3d-green check as satisfying a v4.0 HARD GATE | Feels like real progress on a hard blocker | Fabricates evidence-adjacent confidence about production readiness | Never — always scope-qualify as `(k3d-local)` |

## "Looks Done But Isn't" Checklist

- [ ] **Zod↔wire fix:** Often missing the edge-case data condition that would have caught the ORIGINAL bug (null field, empty list, error shape) — verify the contract test actually exercises a non-happy-path value, not just a re-run of the same seed that already passed before.
- [ ] **Dead-code removal:** Often missing a composition-root/ARQ/migration reference check — verify via full-repo string grep (not just import-graph) before merging the deletion.
- [ ] **Reachability fix:** Often missing the `nav-items.ts` entry even after `router.tsx` is flipped from ComingSoon — verify by navigating from the root nav in the browser, not by hitting the URL directly.
- [ ] **RBAC/audit/email-template touch:** Often missing the same-commit frontend mirror update or AST-gate negative-fixture re-run — verify the specific gate test file changed in the same commit as the enum/frozenset.
- [ ] **k3d infra check:** Often silently implying production-equivalence — verify the registry entry has an explicit `(k3d-scope)` qualifier and the original v4.0 item is untouched.
- [ ] **"Fixed+verified" registry item:** Often has prose evidence instead of a re-runnable command/output — verify the evidence field names an actual artifact (log, screenshot path, test name) that a reviewer could independently re-check.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|-----------------|
| Registry keeps growing past audit-close | MEDIUM | Freeze the registry NOW as-is; any newly found item becomes v4.2 backlog unless it blocks a HARD GATE or an already-registered fix; re-communicate the scope firewall |
| A "dead" symbol turned out to be Protocol-wired/ARQ-referenced and broke prod/k3d | MEDIUM | Revert the deletion commit specifically (isolated commits make this cheap per Pitfall 2); re-add with a comment noting the wiring location found; add the wiring location to the audit-phase checklist for future deletions |
| Test-suite deadlock fix ballooned past budget | LOW–MEDIUM | Fall back to the documented per-module isolation workaround (Pitfall 4 item 3); log the root-cause fix as `deferred` with reason; do not let it block functional-fix phases further |
| A registry item was marked `fixed+verified` but evidence doesn't reproduce on spot-audit | LOW | Reopen the item; do not silently re-close without NEW evidence; note the false-positive pattern so the spot-audit sampling rate increases for that category |
| A k3d claim was mistakenly recorded as closing a v4.0 HARD GATE | LOW | Add the scope qualifier retroactively; reopen the original v4.0 registry item if it was incorrectly marked closed; this is a documentation fix, not a code fix |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|-------------------|--------------|
| 1. Infinite refactor / scope creep | Audit phase (registry freeze) + standing rule all phases | Registry size only shrinks post-audit-close; no commit lacks a registry id |
| 2. Mass reformatting destroys blame | Code-hygiene fix phase + commit-hygiene rule | `git blame -w` shows no mixed format+logic commits |
| 3. Dead-code false positives | Static-audit phase (pre-flag categories) + dead-code fix phase (checklist per deletion) | Full-repo string grep + composition-root check + `alembic downgrade` + k3d cron smoke pass per deletion |
| 4. Broken test suite trap | Early fix phase (deadlock-only, time-boxed) before/parallel to functional fixes | Suite runs to completion (or documented isolation workaround in place) before any fix is marked `fixed+verified` |
| 5. LOCKED invariant regression | Every phase touching RBAC/audit-events/email-templates/OpenAPI/import-linter/ESLint config | Named gate + its negative-test fixture re-run, same commit as the enum/frozenset change |
| 6. Verification-honesty erosion | Audit phase (registry schema/evidence field design) + milestone-close spot-audit | Every `fixed+verified` item has a re-runnable evidence artifact; sample re-run passes |
| 7. Zod↔wire hunt misses instances | Audit phase, BEFORE browser UAT begins (edge-case seed authoring) | Seed dataset covers null/empty/pagination/error-shape/date-money-edge matrix, verified against a checklist |
| 8. Route-reachability misses | Audit phase (mechanical router/nav sweep, scripted) | Scripted diff of routes vs nav entries vs "has real API" list, confirmed by root-nav browser walkthrough |
| 9. k3d mistaken for production proof | Locally-provable-infra fix phase | Every k3d-derived registry item carries an explicit scope qualifier; original v4.0 HARD GATE items remain open and unedited |

## Sources

- `.planning/PROJECT.md` — this project's own milestone history, explicitly documenting: the two-time (v3.0/v3.1) mock-vs-real schema-divergence miss caught only by browser UAT; the D-71-09/FND-04 reachability lesson recurring across v2.4 phases 86-89; the pre-existing test flakes (`test_freeze_race`, promo F821, `test_alembic_clean`) carried since at least v2.4; D-V40-LOCAL-VALIDATE and the "no fabricated evidence" precedent (D-67-03, D-72-06); the v4.0 23-item operator-pending boundary with two HARD GATES (SEC-02, BAK-03); D-62-09/D-10-HISTORY-IMMUTABLE (forward-only history, never rewrite migrations/audit trail) as precedent for treating migration-referenced code as untouchable.
- `CLAUDE.md` — locked architectural constraints: RBAC byte-parity (CISO-01), import-linter contracts, `VITE_API_MODE` chokepoint + ESLint restricted-paths with negative-test fixtures, money/date domain conventions (DST hazard), Protocol-slot composition-root wiring discipline.
- Direct domain reasoning from this codebase's own documented architecture (no external ecosystem research was needed or applicable — this is a project-specific pitfalls analysis, not a general technology survey).

---
*Pitfalls research for: v4.1 Codebase Hardening milestone (clubcore)*
*Researched: 2026-07-26*
