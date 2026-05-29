# Quick Task 260529-ll9: Purge residual sportzal-era technical naming — Context

**Gathered:** 2026-05-29
**Status:** Ready for planning (decisions LOCKED by user — do not revisit)

<domain>
## Task Boundary

Remove residual `sportzal`-era **technical** identifiers now, while it is the cheapest moment — there is NO live production frontend yet (`apps/admin-web` is a frozen mock reference; `apps/client-pwa` has not integrated against the live backend), so the cookie rename needs **no dual-read window**. This is the deferred `NAME-01` / `D-11-CSRF-DEFER` work, brought forward.

Scope is **technical residue only**. The gym **brand** stays "Sportzal" (see locked decisions).
</domain>

<decisions>
## Implementation Decisions (LOCKED by user 2026-05-29)

### 1. Auth cookie rename (the core of this task)
- `sz_access`   → `cc_access`
- `sz_refresh`  → `cc_refresh`
- `sportzal_csrf` → `clubcore_csrf`
- **Only the cookie NAMES change.** All cookie attributes stay byte-identical: `sportzal_csrf`/`clubcore_csrf` remains non-httpOnly (frontend reads it for the `X-CSRF-Token` header); `cc_access`/`cc_refresh` stay httpOnly; `SameSite=lax`, Path, Secure, Max-Age all unchanged.
- **No dual-read / migration window** — there is no live client holding old cookies. A plain rename is correct and intended.

### 2. Email domain → clubcore.ru
- `noreply@mail.sportzal.ru` → `noreply@mail.clubcore.ru` (the `from_address` default in `app/core/config.py` + the domain part of email-template footers).
- In email-template footers `f"{CLUB_BRAND} · noreply@mail.sportzal.ru"`: change **only** the domain → `mail.clubcore.ru`. The `{CLUB_BRAND}` token stays (renders "Sportzal").
- Rename the DNS zone file `apps/backend/infra/dns/sportzal.ru.zone` → `apps/backend/infra/dns/clubcore.ru.zone`; update the apex/origin inside to `clubcore.ru`. DKIM/SPF/DMARC records are **placeholders, N/A-until-production** — do NOT invent real keys; keep the existing placeholder discipline + a note that real records are set when the production domain is provisioned.

### 3. ContextVar + internal residue
- `sportzal_actor_context` → `clubcore_actor_context` (`app/core/actor_context.py`).
- Docstring example addresses `@sportzal.local` / `batch-system@sportzal.local` → `@clubcore.local`.
- YooKassa adapter `User-Agent: "Sportzal/1.7 YooKassa-Adapter"` → `"clubcore/1.11 YooKassa-Adapter"` (this is the **codebase/product** client identity sent to YooKassa, NOT the customer-facing gym brand — renaming is correct).

### 4. Brand — KEEP "Sportzal" (D-62-02 stays in force)
- Do **NOT** change `CLUB_BRAND = "Sportzal"` in `app/core/branding.py`.
- Do **NOT** change the `_DM_STRANGER` Telegram literal "Этот Telegram не привязан к аккаунту Sportzal…" or any other customer-facing **brand** string. "clubcore" = product/codebase namespace; "Sportzal" = gym brand placeholder.

### Claude's Discretion
- Exact naming style for the ContextVar (`clubcore_actor_context` vs `cc_actor_context`) — pick the one matching the surrounding convention.
- Whether to route any remaining hardcoded "Sportzal" brand literals through the `CLUB_BRAND` constant (behaviour-neutral cleanup, optional — only if low-risk and in files already being touched).
</decisions>

<scope_boundaries>
## IN SCOPE (rename here)

**Backend production code (`apps/backend/app/`, 14 files):**
`main.py`, `core/security.py` (cookie issuer/clearer — the source of truth), `core/config.py` (from_address default), `core/actor_context.py`, `core/dependencies.py` (CSRF/cookie reads), `core/exceptions.py`, `integrations/yookassa/factory.py` (User-Agent), `modules/payments/email_templates.py`, `modules/bookings/email_templates.py`, `modules/memberships/email_templates.py`, `modules/auth/email_templates.py`, `modules/auth/service.py`, `modules/auth/schemas.py`, `modules/auth/router.py`.

**DNS zone:** `apps/backend/infra/dns/sportzal.ru.zone` → `clubcore.ru.zone`.

**Tests (`apps/backend/tests/`):** every test asserting the old cookie names / domain (~98 files reference `sportzal_csrf`, ~17 `sz_access`/`sz_refresh`, ~4 `sportzal.ru`). All must be updated so the suite stays green.

**Frontend contract package (`packages/api-client/`):** `src/fetcher.ts` (reads `sportzal_csrf` cookie → must read `clubcore_csrf`), `src/schema.d.ts` (REGEN — do not hand-edit), `CHANGELOG.md` + `README.md` (doc references).

**Tooling + ACTIVE handoff artifacts:**
- `tools/newman/augment-collection.mjs` (extracts `sportzal_csrf` → `csrfToken`)
- `.planning/handoff/clubcore-auth-runbook.md` (ACTIVE current handoff doc)
- `.planning/handoff/v1.11-clubcore.postman_collection.json` (ACTIVE current handoff artifact)

**Regenerated artifacts (MANDATORY — do not hand-edit, regenerate):**
- `apps/backend/openapi.json` — `securitySchemes` references the cookie name (`cookieAuth` = `cc_access`) and the CSRF cookie (`clubcore_csrf`). Regenerate via the project's export command (`uv run python apps/backend/scripts/export_openapi.py` or the documented equivalent). Drift gate must be clean.
- `packages/api-client/src/schema.d.ts` — regenerate via `pnpm --filter @clubcore/api-client codegen`. Drift gate must be clean.

This intentionally shifts the `contract-freeze-v1.11.0` baseline. That is acceptable and expected — it is happening pre-integration, which is exactly why now is the cheapest moment. Note the baseline shift in the SUMMARY.

## OUT OF SCOPE — DO NOT TOUCH (immutable audit trail, D-62-09 / D-10-HISTORY-IMMUTABLE)

Historical/archived `.planning/` documents accurately describe what was true at the time (including "sportzal_csrf retained per D-11-CSRF-DEFER") and are a forward-only immutable audit trail. **Do NOT rewrite:**
- `.planning/phases/**` and `.planning/milestones/v1.*-*` archived ROADMAP/REQUIREMENTS/audit/evidence docs
- Historical handoff runbooks: `.planning/handoff/v1.4-auth-runbook.md`, `.planning/handoff/v1.9-trainers-runbook.md`
- `.planning/MILESTONES.md` historical entries, `.planning/RETROSPECTIVE.md` historical sections
- Any `.claude/worktrees/**` (stale agent worktrees — never touch)

`STATE.md` / `PROJECT.md` are orchestrator-owned; the quick orchestrator updates STATE.md. Do not mass-rewrite them for the rename.
</scope_boundaries>

<verification>
## Done = green gates
- Full backend `pytest` green (updated assertions).
- `ruff check` + `ruff format --check` + `mypy --strict app` + `import-linter` exit 0.
- `openapi.json` + `schema.d.ts` regenerated byte-stably; drift gate (`git diff --exit-code`) clean.
- Redocly lint (7th CI gate) exits 0.
- Zero occurrences of `sz_access` / `sz_refresh` / `sportzal_csrf` / `sportzal.ru` / `sportzal_actor_context` in IN-SCOPE paths (production code, active artifacts, tests). Historical `.planning/` occurrences remain (expected).
- `CLUB_BRAND` still equals "Sportzal"; `_DM_STRANGER` brand literal unchanged.
</verification>

<canonical_refs>
## Canonical References
- `D-11-CSRF-DEFER` / `NAME-01` — the deferral this task closes (see archived `.planning/milestones/v1.11-REQUIREMENTS.md`).
- `D-62-02` — clubcore = product namespace, "Sportzal" = gym brand placeholder (brand stays).
- `D-62-09` / `D-10-HISTORY-IMMUTABLE` — forward-only `.planning/` rewrite; historical docs immutable.
- `app/core/security.py` — the cookie issue/clear source of truth (locked attribute tuple).
</canonical_refs>
