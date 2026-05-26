# Phase 62: clubcore Rebrand - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-26
**Phase:** 62-clubcore-rebrand
**Areas discussed:** Brand vs identifier split, Operator-tier renames scope, Back-compat migration mechanics, .planning/ historical rewrite scope, Milestone restructure (mid-discussion)

---

## Area selection

| Option | Description | Selected |
|--------|-------------|----------|
| Brand vs identifier split | Rename user-facing 'Sportzal' strings in email templates too, or keep as product brand and only rename code identifiers? Big scope swing. | ✓ |
| Operator-tier renames scope | Postgres DB name, email domain — defer entirely to operator-runbook, document gaps, or include rename scripts in this phase? | ✓ |
| Back-compat migration mechanics | D-10-BACK-COMPAT locks principle. Open: localStorage 'read-fallback chain' vs 'copy-on-read + delete', and for Redis 'runtime dual-read' vs 'operator flush at deploy'. | ✓ |
| .planning/ historical rewrite scope | REB-05 lists PROJECT.md/MILESTONES.md/ROADMAP.md/future handoff. Open: also rewrite .planning/phases/ (60+ historical phase folders)? | ✓ |

**User's choice:** All 4 areas selected.

---

## Brand vs Identifier Split

### Initial question

| Option | Description | Selected |
|--------|-------------|----------|
| Full rebrand — also rename user-facing copy | Replace 'Sportzal' → 'clubcore' in all email templates, subjects, footers, invitation copy. Email domain in footer changes too. | |
| Code-only rebrand — keep 'Sportzal' as product brand | Only rename code identifiers (@sportzal/*, sz:/sportzal:). Email templates keep 'Sportzal' strings + sportzal.ru domain. Smaller, safer. | |
| Code + email strings, keep domain | Rename code identifiers AND user-facing copy ('clubcore' in subjects/footers), but keep noreply@mail.sportzal.ru FROM-address until DNS work happens later. | |

**User's choice (freeform):** "clubcore это именно название проекта как продукт разработки а не бренд конкретного клуба. Название клуба я должен устанавливать сам под конкретный зал/фитнес клуб."

**Implication:** Major reframe. `clubcore` is the codebase/product name, NOT a gym brand. Per-club brand must be settable per installation. The hardcoded "Sportzal" in email templates is a placeholder for what will eventually be operator-configurable, NOT a brand to be renamed to "clubcore".

### Follow-up: what to do with the placeholder

| Option | Description | Selected |
|--------|-------------|----------|
| Leave 'Sportzal' placeholder as-is | Don't touch email templates. 'Sportzal' stays as hardcoded gym brand stub until future phase introduces per-club configurable branding. Smallest scope. | |
| Replace with neutral placeholder string | Replace 'Sportzal' → 'Ваш клуб' / 'TODO: gym name' so future maintainers know it's a placeholder. | |
| Extract to single CLUB_BRAND constant | Pull 'Sportzal' into one ClubBrand constant for v1.11 to wire to per-club config. Zero runtime change in v1.10 (still 'Sportzal'), just code restructure. Borderline D-10-NO-NEW-BUSINESS. | ✓ |

**User's choice:** Extract to single CLUB_BRAND constant.
**Notes:** Captured as borderline D-10-NO-NEW-BUSINESS — but pure refactor (value unchanged → zero behaviour change). Flagged for planner to verify constant extraction does not introduce config-flag or runtime change.

---

## Operator-Tier Renames Scope

### Initial question

| Option | Description | Selected |
|--------|-------------|----------|
| Defer both to v1.11 operator-runbook | DB stays 'sportzal', email FROM stays mail.sportzal.ru. REB-08 explicitly notes as known carry-overs. Cleanest. | |
| DB rename in v1.10, email domain deferred | Author Alembic-adjacent operator script for DB rename; email FROM stays sportzal.ru. | |
| Both rename in v1.10 with documented operator steps | DB rename + DNS/DKIM checklist; new env CLUBCORE_EMAIL_FROM with fallback. Largest scope. | ✓ |

**User's choice:** Both rename in v1.10 with documented operator steps.

### Follow-up: email FROM mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Env-driven via Settings with deprecated-warning fallback | Add CLUBCORE_EMAIL_FROM to app/core/config.py Settings. Fallback chain: CLUBCORE_EMAIL_FROM → SPORTZAL_EMAIL_FROM (legacy, logs deprecation) → hardcoded default. Removal v1.11. | ✓ |
| Same as CLUB_BRAND: pure constant in app/core/branding.py | Extract email FROM to a constant alongside CLUB_BRAND. No env, no runtime config. | |
| Env-driven, no fallback (operator MUST set) | CLUBCORE_EMAIL_FROM required. Forces clean migration but breaks back-compat principle. | |

**User's choice:** Env-driven via Settings with deprecated-warning fallback.

---

## Back-Compat Migration Mechanics

### localStorage

| Option | Description | Selected |
|--------|-------------|----------|
| Copy-on-read + delete old key | On first v1.10 boot: read clubcore:*; if absent, read sportzal:*, copy to clubcore:*, delete sportzal:*. Single migration event per user. Matches Zustand migrate idiom. | ✓ |
| Read-fallback chain, keep both for one release | Always try clubcore:*; on miss read sportzal:*; writes go only to clubcore:*. Old keys linger until v1.11 explicit cleanup. | |
| Copy-on-read + keep old key with deprecated marker | Copy sportzal:* → clubcore:* on first read but don't delete; set deprecated marker. v1.11 deletes. Most conservative. | |

**User's choice:** Copy-on-read + delete old key.

### Redis

| Option | Description | Selected |
|--------|-------------|----------|
| Operator FLUSHDB at deploy, no runtime fallback | v1.10 code reads/writes only cc:* keys. Operator runbook documents FLUSHDB or SCAN+DEL on sz:*. Lost cache state on cutover. Simplest code. | ✓ |
| Runtime dual-read for one release | Reads try cc:* first, fall back to sz:*; writes only to cc:*. TTLs drain naturally; no operator action. v1.11 strips fallback. Code complexity in 7+ modules. | |
| Hybrid: dual-read only for idempotency, flush rest | Idempotency + webhook dedup get dual-read fallback. Circuit breakers + telegram dedup get operator flush. | |

**User's choice:** Operator FLUSHDB at deploy, no runtime fallback.
**Notes:** Tradeoffs explicitly accepted: brief idempotency replay window, circuit breakers reset, telegram dedup reset, yookassa webhook dedup reset. Documented in CONTEXT.md D-62-07.

---

## .planning/ Historical Rewrite Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Forward-only — historical artifacts immutable | Only rewrite PROJECT.md, MILESTONES.md, ROADMAP.md, REQUIREMENTS.md, RETROSPECTIVE.md, STATE.md, future handoff/. Historical .planning/phases/47-* through 61-* + .planning/audits/* stay with 'sportzal'. Repo grep finds 'sportzal' in history forever. | ✓ |
| Forward-only + add HISTORICAL_NOTE.md | Same as above + .planning/HISTORICAL_NOTE.md explaining the immutability rationale. | |
| Full sweep including history | Rewrite ALL .planning/ to 'clubcore' including historical phase folders + audits. Clean grep. Cost: tens of MB of git diff, audit-trail integrity damaged. | |

**User's choice:** Forward-only — historical artifacts immutable.
**Notes:** During CONTEXT.md write, the HISTORICAL_NOTE.md was added as a complementary deliverable (D-62-10) since the user's "forward-only" selection still left the open question of why grep finds 'sportzal' in repo. Documenting the boundary in HISTORICAL_NOTE.md is a small ergonomic add, NOT a scope expansion.

---

## Milestone Restructure (mid-discussion pivot)

After all 4 areas were captured, the user paused to ask: "может быть всю эту миграцию определить в отдельный milestone?"

| Option | Description | Selected |
|--------|-------------|----------|
| Split: v1.10 = Rebrand only (новый milestone), v1.11 = Handoff + Hardening | Phase 62 becomes only/main phase of v1.10. Phases 63-67 move to v1.11. Cleaner cutover; extra milestone-overhead. | ✓ |
| Оставить в v1.10 с расширенным scope | Accept Phase 62 as heaviest phase in milestone. Continue writing CONTEXT.md with all 4 decisions. Preserves milestone coherence. | |
| Сократить Phase 62 обратно до code-only rename | DB rename + email domain + CLUB_BRAND constant move to Phase 67 / new phase. CONTEXT.md rewritten without Area 2 decisions. | |

**User's choice:** Split: v1.10 = Rebrand only, v1.11 = Handoff + Hardening.
**Notes:** Triggered atomic restructure of 4 planning files (ROADMAP.md, REQUIREMENTS.md, STATE.md, PROJECT.md). Committed as c3e1110a before writing CONTEXT.md. Phases 63-67 retain their global-sequential numbers; v1.11 milestone container is new. Two new requirements added to v1.11 snapshot (RUN-07: v1.10-shim removal, RUN-08: DB-rename + DNS evidence).

### Restructure execution choice

| Option | Description | Selected |
|--------|-------------|----------|
| Я сделаю сейчас (5 файлов, 1 atomic commit) | Claude edits ROADMAP.md / MILESTONES.md / REQUIREMENTS.md / STATE.md / PROJECT.md, then writes CONTEXT.md. | ✓ |
| Сначала покажи diff/draft, я ревью | Prepare diff previews per file before writing. | |
| Я сделаю restructure сам, ты перезапусти /gsd:discuss-phase 62 | User edits manually; restart session loses captured decisions. | |

**User's choice:** Claude executes restructure. Final commit touched 4 files (MILESTONES.md not needed — v1.10 not shipped yet, no historical entry to update).

---

## Claude's Discretion

- **Plan structure** (single large plan vs split by surface) — recommendation logged in CONTEXT.md `<decisions>` "Claude's Discretion" subsection.
- **CLUB_BRAND constant location** (`app/core/branding.py` recommended vs alternatives) — planner's call.
- **DB rename runbook depth** (terse vs full-blown) — recommendation: terse + reference v1.5/v1.8 runbook discipline.
- **Mid-rebrand build stability (D-62-11)** — not explicitly asked but flagged for planner: atomic package rename + consumer updates in single commit boundary.
- **`.planning/HISTORICAL_NOTE.md` exact wording** — outlined in CONTEXT.md `<specifics>`, body to be authored during execution.

---

## Deferred Ideas

- Postman v2.1 + Newman, OpenAPI doc-site, contract freeze, idempotency hardening, tech-debt sweep, operator-pending runbook execution — moved from v1.10 → **v1.11** per D-10-SPLIT (Phases 63-67).
- Per-club configurable gym brand — future phase after v1.11; CLUB_BRAND constant in v1.10 is the foundation.
- Email domain migration (mail.sportzal.ru → other) — operator-controlled DNS work; v1.10 ships env mechanism + checklist, does not change sending domain.
- v1.10 back-compat shim removal — new requirements RUN-07 (sportzal:* localStorage migrate logic strip + SPORTZAL_EMAIL_FROM env fallback strip) and RUN-08 (DB-rename pg_dump/restore evidence + DNS/DKIM Authentication-Results) added to v1.11 snapshot.
