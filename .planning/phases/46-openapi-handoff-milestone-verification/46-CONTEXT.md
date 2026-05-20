# Phase 46: OpenAPI Handoff + Milestone Verification — Context

**Gathered:** 2026-05-20
**Status:** Ready for planning
**Mode:** `--auto` (recommended defaults auto-selected from REQUIREMENTS.md / ROADMAP.md / DEFER-40-01 lesson / Phases 41–45 CONTEXT chain / v1.5 verification-evidence shape)

<domain>
## Phase Boundary

The serialization point + verification gate for v1.6. Two halves, one atomic ship:

**Half A — OpenAPI handoff (HANDOFF-03/04):**

1. Atomic byte-stable regen of `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts` exposing every new v1.6 path that landed in Phases 42–44:
   - `POST /api/v1/users` (USERS-01)
   - `GET /api/v1/users` (USERS-04)
   - `POST /api/v1/users/{id}/deactivate` (USERS-05)
   - `POST /api/v1/users/{id}/reactivate` (USERS-05)
   - `DELETE /api/v1/users/{id}` (USERS-07)
   - `POST /api/v1/users/invitations/accept` (RESET-04)
   - `POST /api/v1/users/invitations/{token_id}/revoke` (RESET-05)
   - `POST /api/v1/auth/password-reset/request` (RESET-01)
   - `POST /api/v1/auth/password-reset/confirm` (RESET-02)
   - `POST /api/v1/_internal/email/webhook` (EMAIL-04 — webhook ingestion)
   - `POST /api/v1/otp/request` updated to surface the `channel` parameter (AUTH-EM-01)
2. Extend `packages/api-client/src/schema.contract.test.ts` `AssertNonNever` forward-guards 61 → ~73, covering path + method + request-body realisation + 2xx-response realisation per new endpoint.
3. `apps/backend/README.md` v1.6 changelog section added documenting every new endpoint (mirrors Phase 35 / Phase 40 changelog cadence).
4. Postman collection `.planning/handoff/v1.6-postman.json` published as a supplementary handoff artifact alongside `v1.4-postman.json` (external design-team consumption).

**Half B — Milestone verification (VER-09..14):**

5. ≥7 curl-based operator runbook scenarios against `docker compose -f apps/backend/docker-compose.yml up`. Verbatim HTTP transcripts captured under `.planning/milestones/v1.6-verification-evidence/curl/`.
6. ≥6 real-Postgres race tests living in `tests/integration/` (token replay, soft-delete + re-invite, deactivate + /refresh, bounce-webhook + active-send, double-pings, RFC 2047 Cyrillic round-trip).
7. Anti-oracle integration tests `tests/integration/test_password_reset_no_oracle.py` + `tests/integration/test_otp_email_anti_oracle.py` MUST pass at the gate — failure blocks milestone close.
8. Live email-deliverability probe — 3 real emails (yandex.ru + mail.ru + rambler.ru) with `Authentication-Results` SPF=pass, DKIM=pass, DMARC=pass alignment captured as headers/screenshots in `.planning/milestones/v1.6-verification-evidence/email-probe/`.
9. 6/6 CI gates green captured as evidence: backend ruff + mypy --strict + pytest + import-linter + OpenAPI drift gate (backend) + frontend codegen drift gate (`packages/api-client/src/schema.d.ts`). Plus the SVC001 AST commit-gate (`users/service.py` + `auth/password_reset_service.py`) green; plus the `LOCKED_EMAIL_TEMPLATES` AST gate green.
10. Owner sign-off recorded in `.planning/milestones/v1.6-VERIFICATION-LOG.md` enumerating every locked Russian email template constant by name (the 15 entries currently in `LOCKED_EMAIL_TEMPLATES` after Phase 45 closes — see D-46-14).
11. **DEFER-40-01 lesson applied:** runbook scaffolding hardened BEFORE the verification session (not discovered mid-run). Concretely: pre-fix the v1.5 `run.sh` regressions (`/healthz`, table-name drift, `verify_*@local.dev` fixture defaults, X-CSRF-Token header threading) by writing the v1.6 `run.sh` against current schema + current fixtures, NOT by copy-pasting the v1.5 script.

Requirements in scope: **HANDOFF-03, HANDOFF-04, VER-09, VER-10, VER-11, VER-12, VER-13, VER-14** (8 reqs per `.planning/REQUIREMENTS.md` traceability table — Phase 46 closes v1.6).

**Out of scope (forwarded to later milestones or v2.0):**

- **Full v1.5 carry-forward operator runbook re-execution (DEFER-40-01 backfill)** — rolls to v1.9 per PROJECT.md milestone roadmap. Phase 46 verifies v1.6 surface only; v1.5 minimal-verification (`scripts/verify_40_create_booking_via_bot.py`) remains the v1.5 close evidence.
- **`operation_id=` curation + OpenAPI tag hygiene** — v1.9 (per D-35-07 lineage — operation-id naming is a v1.9 hygiene topic, not v1.6).
- **`@sportzal/api-client` npm publish + Postman v2.1 + Newman CLI runner** — v1.9 (whole "API Handoff + Production Hardening" milestone scope). Phase 46 ships byte-stable artifacts in-repo; npm publish is operationally separate.
- **OpenAPI doc-site + versioned spec URL** — v1.9.
- **Admin-web UI surfaces for any v1.6 endpoint** (USERS-* CRUD UI, password-reset/accept-invite SPA pages, channel-selector on OTP login form) — v2.0 frontend handoff. Phase 46 is backend-only.
- **`/api/v1/_internal/email/webhook` exposed in the public Postman collection** — internal-only path, marked `tags: ['internal']` in OpenAPI (mirrors Phase 21 `_meta` discipline); design team does NOT consume it. Listed in the spec for completeness but explicitly carved out of the external-design-team Postman handoff.
- **Multi-region SPF/DKIM/DMARC delivery probe** (gmail.com, outlook.com, proton.me) — v1.9. v1.6 probe target is RU-domain receivers only per VER-12 spec; international delivery is a follow-up.
- **Production-load smoke** (k6, locust, real concurrent users) — never in v1.6; load-testing infrastructure lands when the gym actually scales beyond pet-project (PROJECT.md "single zal, pet project").
- **Inline regressions discovered at the gate beyond the ≤5 hard cap** — roll forward as `DEFER-46-N` rows in v1.6-VERIFICATION-LOG.md (mirrors v1.4 / v1.5 discipline). ≤5 inline fixes is the hard ceiling; the 6th regression triggers a milestone-close decision (defer-all or open Phase 47).
- **Owner-managed "resend invitation" / "resend receipt" endpoints** — v1.7 (already deferred in Phase 43 + Phase 45 CONTEXT; reiterated here because runbook scenarios might surface the operational need — capture as DEFER if it does, do not implement inline).
- **Production deployment of the new email transport** — v1.7 operational concern (Phase 42 ships the dev / staging dispatcher; v1.6 close does NOT require prod credentials; VER-12 probe runs from staging Yandex Postbox sandbox or a fresh prod-equivalent project with throwaway DKIM keys, owner's discretion at execute-time).

</domain>

<decisions>
## Implementation Decisions

### HANDOFF-03 — Atomic OpenAPI + schema.d.ts regen (RESOLVED)

- **D-46-01 (Single atomic commit — backend export + frontend codegen in lockstep):** ONE commit lands both `apps/backend/openapi.json` AND `packages/api-client/src/schema.d.ts`. Sequence:
  1. `cd apps/backend && uv run python -m scripts.export_openapi` — regenerates `openapi.json` byte-stable (the existing script is cwd-independent and already enforces `indent=2, sort_keys=True, ensure_ascii=False, trailing newline` per Phase 9 D-04..D-06 lineage).
  2. `pnpm --filter @sportzal/api-client codegen` (or whatever the existing pnpm script alias is — verify at execute-time via `cat packages/api-client/package.json | jq .scripts`) — regenerates `schema.d.ts` from the freshly written `openapi.json`.
  3. `git diff` shows BOTH artifacts changed; commit message `chore(46-01): regen openapi.json + schema.d.ts for v1.6 surface`.
  4. CI `Drift gate — apps/backend/openapi.json` (`.github/workflows/ci.yml:60`) AND `Drift gate — packages/api-client/src/schema.d.ts` (`.github/workflows/ci.yml:114`) both go green in the same CI run.
  No new tooling. No new package. The Phase 9 D-04..D-06 export shape is preserved verbatim.
- **D-46-02 (Pre-flight: enumerate every router-decorator addition since Phase 40):** Before running the export, grep the diff `git log --since=2026-05-18 --diff-filter=A -- 'apps/backend/app/modules/**/router.py'` and `git diff v1.5...HEAD -- 'apps/backend/app/modules/**/router.py'` to confirm the 10 endpoints landed (per Phase 42 / 43 / 44 plan SUMMARY files). If any endpoint is MISSING from the live FastAPI app (forgotten `app.include_router(...)`), the openapi.json regen will silently omit it AND the schema.contract.test.ts `AssertNonNever<paths[...]>` for that path will collapse to `never` — caught by the TypeScript compile but easier to diagnose with the pre-flight check.
- **D-46-03 (`/api/v1/_internal/email/webhook` tagged `['internal']` and `operationId` left auto-generated):** The webhook endpoint is internal-only (provider → backend). Tag-namespacing via FastAPI `APIRouter(tags=['internal'])` keeps it visually segregated in Swagger UI; the Postman handoff filter (D-46-08) excludes it. No operation-id curation in Phase 46 (D-35-07 lineage — operation-id naming is a v1.9 hygiene topic).
- **D-46-04 (No new `openapi.json` ordering rule beyond Phase 9 `sort_keys=True`):** Byte-stability is enforced solely by `json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + '\n'` (per `scripts/export_openapi.py` D-05). No path ordering, no tag ordering, no schema ordering beyond what `sort_keys=True` produces. macOS / Linux produce identical bytes (already verified Phase 9).

### HANDOFF-04 — schema.contract.test.ts forward-guards 61 → ~73 (RESOLVED)

- **D-46-05 (One section per epic — three blocks added to the test file):** Add three clearly-labelled blocks to `packages/api-client/src/schema.contract.test.ts` (mirrors the existing "v1.2 surface" / "v1.4 surface" / "Phase 23 CD-05" comment-banner style):
  ```typescript
  // --- v1.6 surface — Multi-user admin (Phase 43 USERS-*) ---------------
  // --- v1.6 surface — Password reset + invitation accept (Phase 44 RESET-*) ---
  // --- v1.6 surface — Email channel (Phase 42 AUTH-EM-* + EMAIL-*) ----------
  ```
- **D-46-06 (Forward-guard count target: 73 — exact arithmetic from the new surface):** Current count 61 (per ROADMAP.md success criterion 2 + count of `const _*Check: ... = true` lines in `schema.contract.test.ts`). The "+12" delta breaks down as:
  - Path-method assertions: 10 path-method tuples × 1 `AssertNonNever<paths[P][M]>` each = +10.
  - Request-body realisation: 8 POST/DELETE endpoints with non-empty body (excluding `GET /users` and the two empty-body invitation/deactivate paths) × 1 `AssertNonNever<paths[P][M]['requestBody']>` each = +8 (but bundled inside the per-endpoint block per D-46-05).
  - 2xx response realisation: 10 path-method tuples × 1 `AssertNonNever<paths[P][M]['responses']['2xx']>` each = +10.
  - Headcount in the bottom `const _v16Checks: [...]` tuple gets the per-block summary entries = ~12 additions.
  Final total: **73 ± 2** depending on whether the planner bundles body+2xx into single `const` tuples or splits them. Either shape is acceptable; the success criterion floor is "every new v1.6 path + method + request-body realisation + 2xx-response realisation" — count is descriptive, not contractual. Treat **73** as the target, **70** as the floor, **76** as the ceiling.
- **D-46-07 (`/_internal/email/webhook` IS included in the forward-guards):** Internal-only tagging affects Postman filtering, NOT the TypeScript schema contract. The frontend never calls `/_internal/email/webhook`, but the type-system assertion is still meaningful (catches accidental removal in a future phase). Mirrors Phase 22 `/visits/_meta` precedent: internal-but-typed.
- **D-46-08 (Postman handoff filter — exclude `_internal` tag):** `.planning/handoff/v1.6-postman.json` is generated from a filtered subset of `openapi.json` excluding any path whose primary tag is `'internal'`. Generation script lives at `apps/backend/scripts/export_postman.py` (NEW; mirrors `export_openapi.py` shape — lifespan-safe, byte-stable JSON output, single function). Alternative considered: use `postman-to-openapi` reverse converter — REJECTED (extra deps, less control). The script reads the just-regenerated `openapi.json`, walks paths, drops `_internal`-tagged ones, emits Postman v2.1 schema. Two file outputs in HANDOFF-04: in-repo `.planning/handoff/v1.6-postman.json` + the openapi-derived auto-publish (manual upload outside Phase 46 if needed).
- **D-46-09 (`apps/backend/README.md` v1.6 changelog section — single H2 block):** Insert after the existing v1.5 changelog block (or at top of file if no prior changelog — verify at execute-time via `head -50 apps/backend/README.md`). Section title `## v1.6 — Email channel + Multi-user admin (2026-05-20)`. Body: one bullet per new endpoint with the verbatim path + method + one-sentence summary + the requirement code (USERS-01..07 / RESET-01..05 / EMAIL-01..07 / AUTH-EM-01..04 / NOTIFY-06..14). Footer line: `Locked Russian email templates: 15 constants — see app/core/audit.py LOCKED_EMAIL_TEMPLATES.`

### VER-09 — 7+ curl operator scenarios (RESOLVED — DEFER-40-01 lesson applied)

- **D-46-10 (Runbook script lives in `.planning/milestones/v1.6-verification-evidence/run.sh` — fresh, not v1.5 copy-paste):** Mirrors v1.5 location pattern but the v1.5 `run.sh` is treated as REFERENCE only. The v1.6 run.sh is written against current Alembic revision IDs, current schema (e.g. `users.deleted_at` from Alembic 0022, `payment_receipts` from Phase 45 Alembic 0029, `channel` discriminator from Alembic 0024), and current fixture defaults (`verify_*@local.dev` shape, NOT `@fixture.local` shape — the v1.5 `run.sh` discovery bug). Pre-flight at the head of `run.sh` MUST:
  1. `curl -fsSL http://localhost:8000/healthz` (use the correct path — v1.5 `run.sh` shipped with `/health` which 404'd; verify at execute-time which path exists via `grep -rn '@.*get.*healthz\?' apps/backend/app/`).
  2. Assert `apps/backend/scripts/seed_verification_fixtures.py` runs cleanly against the freshly migrated DB (no Alembic revision-id length overflow, no missing tables).
  3. Login the reception + owner fixtures, snapshot their access + refresh cookies AND the CSRF token header into shell vars (the v1.5 run.sh missing-X-CSRF-Token bug). Every subsequent POST/DELETE in the script threads `-H "X-CSRF-Token: $CSRF"` per Phase 6 D-06-XSRF lineage.
- **D-46-11 (8 scenarios shipped — covers the 7 ROADMAP-listed + 1 explicit Telegram-blocked-cash-sale combo):** Verbatim from ROADMAP.md success criterion 3 + slight regrouping for runbook flow:
  - **01 — invite_accept_login** (VER-09 a): owner POST /users → invite arrives in sandbox inbox → user POST /users/invitations/accept → user POST /auth/login → 200 with session cookies. Capture all HTTP transcripts + the rendered email body.
  - **02 — deactivate_revokes_refresh** (VER-09 b): owner POST /users/{id}/deactivate → user POST /auth/refresh → 401 `account_inactive`. Re-activate to restore for re-run idempotency.
  - **03 — password_reset_invalidates_sessions** (VER-09 c): user POST /auth/password-reset/request → email arrives → POST /auth/password-reset/confirm → all prior refresh families revoked → user POST /auth/login with new password → 200.
  - **04 — anti_oracle_request_unknown_email** (VER-09 d): 4× POST /auth/password-reset/request with (known-active / known-deactivated / known-soft-deleted / never-existed) emails — all 4 responses MUST be byte-identical 202 + identical body + bounded timing within 100ms (mirrors the integration test gate). Capture the 4 transcripts side-by-side.
  - **05 — expiring_email_fallback** (VER-09 e): seed a client with `email IS NOT NULL` + Telegram-linked + expiring 7d ahead → mock Telegram return `SendResult.blocked=True` (via env-flag or stub bot fixture) → run `scripts/run_expiring_cron_once.py` → assert `membership_notifications` has row with `channel='email'` AND the dispatched email landed in the sandbox inbox.
  - **06 — cash_sale_receipt** (VER-09 f): owner POST /api/v1/payments (cash sale) → assert post-commit fanout fires → `payment_receipts` row inserted with `channel='email'` AND receipt email lands in sandbox inbox.
  - **07 — soft_delete_reinvite_same_email** (VER-09 g): owner POST /users (email=x) → owner DELETE /users/{first.id} → owner POST /users (email=x again, different `full_name`) → 201, new row visible, partial-UNIQUE `(lower(email)) WHERE deleted_at IS NULL` permits the second INSERT (Alembic 0022 lineage).
  - **08 — cron_chain_circuit_breaker** (VER-09 h): mock email-provider 5xx via the Phase 42 fake-provider stub → run expiring-cron 06:15 + booking-reminders 06:35 in sequence → assert both crons complete within the 10-minute window AND the Phase 42 circuit breaker opens (`email_dispatcher.circuit_state='open'` observable in structlog). The chain stays within budget; emails get queued for next-tick retry per Phase 42 D-42 backoff lineage.
  - **(09 — bonus, optional)** — `/_internal/email/webhook` ingestion: simulate a Yandex Postbox bounce webhook delivery via curl → assert `email_send_log.status='bounced'` updated AND `payment_receipts` (if applicable) has the `audit_correlation_id` chain preserved. Only if time permits in the verification session.
- **D-46-12 (HTTP transcripts captured verbatim — `curl -i -v 2>&1`):** Each scenario writes its full transcript (request line + headers + body + response line + headers + body) to `.planning/milestones/v1.6-verification-evidence/curl/NN_<slug>.http` (mirrors v1.5 evidence shape). Status codes + body snippets are then summarised in `v1.6-VERIFICATION-LOG.md` `human_verification:` YAML rows with `actual:` populated from grep-extracted lines.
- **D-46-13 (Sandbox-inbox provider — owner's Yandex Postbox sandbox or a local catch-all MailHog instance, owner's choice at execute-time):** Sandbox inbox is for scenarios 01, 03, 05, 06 (email arrival assertions). VER-12 separately uses live RU-domain receivers (yandex.ru / mail.ru / rambler.ru) — the sandbox is a different setup. Phase 46 plan should propose both options; owner picks at execute-time depending on what credentials are at hand. Default recommendation: **MailHog via `docker compose --profile dev up`** (zero-cost, no external dependency); fallback to live Postbox sandbox if circuit-breaker behaviour needs a real upstream.

### VER-10 — ≥6 real-Postgres race tests (RESOLVED)

- **D-46-14 (Race tests live in `tests/integration/` per existing convention):** Phase 45 D-45-27 / D-45-28 already wrote `test_payment_receipt_race.py`. Phase 46 adds the remaining 5 (or 6, depending on Phase 45's final count). All real-Postgres (NO mocks), all use the per-test SAVEPOINT isolation pattern from `tests/conftest.py`:
  1. **`test_password_reset_token_replay_race.py`** — two concurrent `POST /password-reset/confirm` with same raw token using `asyncio.gather` → assert exactly one returns 200 + exactly one returns 410 `invalid_or_expired_token` + exactly one `password_reset_completed` audit row. Race-tightness comes from the `UPDATE ... WHERE consumed_at IS NULL RETURNING` SQL (Phase 44 D-44-14).
  2. **`test_soft_delete_reinvite_race.py`** — concurrent `DELETE /users/{old.id}` + `POST /users` with same email via `asyncio.gather` → exactly one new row visible AND old row has `deleted_at IS NOT NULL`. Partial-UNIQUE `(lower(email)) WHERE deleted_at IS NULL` (Alembic 0022) permits the second INSERT.
  3. **`test_deactivate_refresh_race.py`** — concurrent `POST /users/{id}/deactivate` + `POST /auth/refresh` from the same user's refresh-family → refresh race-loses, returns 401 `account_inactive`. Tests SVC001 service-owns-txn boundary in `users/service.deactivate_user` + `auth/service.refresh_session`.
  4. **`test_bounce_webhook_active_send_race.py`** — concurrent `/_internal/email/webhook` POST (bounce notification for `email_send_log.id=X`) + `EmailDispatcher.dispatch(...)` continuing to enqueue a fresh send to the same recipient → bounce update lands; active send is NOT cancelled (best-effort, Phase 42 D-42 backoff handles retry independently); `email_send_log.status` lands as `'bounced'` for the first row, `'sent'` for the second. Audit chain intact.
  5. **`test_concurrent_expiring_cron_double_pings_race.py`** — invoke `scripts/run_expiring_cron_once.py` (or the underlying `_send_expiring_notifications` helper directly) twice concurrently against same membership → exactly one `membership_notifications` row with `channel='email'` inserted (UNIQUE `(subject_id, kind, channel)` from Alembic 0024 + Phase 41 D-41-15 catches the duplicate). Mirrors Phase 27 D-27-07 multi-session-per-tick race-safety.
  6. **`test_rfc2047_cyrillic_subject_roundtrip.py`** — render an email with Cyrillic subject (e.g. `"Ваш абонемент скоро истекает"` from Phase 45 D-45's `EMAIL_EXPIRING_7D_VARIANT_A` template), encode through `EmailEnvelope` → Yandex Postbox sandbox → fetch the delivered mail back via IMAP or webhook payload → assert the subject decodes byte-identically. Catches the RFC 2047 encoded-word `=?UTF-8?B?...?=` round-trip discipline (Phase 42 D-42 NBSP / Unicode lineage).
- **D-46-15 (Race-test naming + co-location with anti-oracle tests):** All 6 sit in `tests/integration/` (NOT `tests/unit/`). The 4 anti-oracle integration tests (Phase 41 / 42 / 44 lineage — `test_password_reset_no_oracle.py`, `test_otp_email_anti_oracle.py`, etc.) sit alongside. Naming convention: `test_<surface>_<race>_race.py` (already established by Phase 45 D-45-28 `test_payment_receipt_race.py`).
- **D-46-16 (Real-Postgres fixture — no mocks):** Uses the existing `pytest-asyncio` + `asyncpg` test fixture chain from `tests/conftest.py`. Per-test SAVEPOINT + rollback isolation already in place (CLAUDE.md testing convention). NO `unittest.mock.AsyncMock`-wrapped Postgres in any of the 6 tests. ARQ enqueue spy is acceptable (in-memory stub per Phase 45 D-45-29 lineage); the Postgres + Alembic-applied-schema layer is REAL.

### VER-11 — Anti-oracle integration tests pass (RESOLVED)

- **D-46-17 (Both tests are ALREADY in the repo by the time Phase 46 starts):** `test_password_reset_no_oracle.py` shipped at Phase 41 (RESET-06 / D-41-17 — initially `@pytest.mark.xfail(strict=True)`); ungated at Phase 44 commit-of-RESET-01 (Phase 44 D-44 lineage). `test_otp_email_anti_oracle.py` shipped at Phase 42 (AUTH-EM-04). Phase 46's job is to **re-run them under the verification CI run** and capture pass evidence; NOT to author new tests. If either is still xfail-marked (regression), Phase 46 BLOCKS and a hotfix lands inline (counts against the ≤5 inline-regression cap).
- **D-46-18 (Bounded-timing tolerance — 100ms per Phase 41 D-41-17):** `test_password_reset_no_oracle.py` asserts the 4 cases (known-active / known-deactivated / known-soft-deleted / never-existed) complete within a 100ms tolerance window of each other. The Phase 44 D-44-07 `asyncio.sleep(max(0.0, 0.5 - elapsed))` constant-time floor at 500ms gives ample headroom. If the test starts flaking at the gate (e.g. CI runner variance pushes some cases >500ms + 100ms tolerance), the fix is to widen the floor to 600ms in `app/modules/auth/router.py:request_password_reset` (one-line change; counts as inline regression).

### VER-12 — Live deliverability probe (RESOLVED)

- **D-46-19 (Probe runs from a throwaway one-shot script — `apps/backend/scripts/verify/v1_6_email_probe.py`):** New script (NOT shell — needs Yandex Postbox API auth + EmailEnvelope construction). Reads target recipients from env vars (`PROBE_YANDEX_TO`, `PROBE_MAIL_TO`, `PROBE_RAMBLER_TO`), sends 3 emails via the production-shape EmailDispatcher (NOT the sandbox stub), captures the `provider_message_id` for each, prints them. Operator then manually pulls the delivered mail headers (via the recipient's own webmail "show original" / "view source") and pastes the `Authentication-Results:` header line into `v1.6-VERIFICATION-LOG.md`. NO automated IMAP fetch — keeps the probe scope tiny + avoids credential plumbing for 3 different mailbox providers.
- **D-46-20 (Recipients = owner's personal accounts, per VER-12 spec):** No new fixture clients. Owner uses their own `andre.shipunov+probe-yandex@yandex.ru` / `+probe-mailru@mail.ru` / `+probe-rambler@rambler.ru` aliases (or equivalent). Evidence is 3 `Authentication-Results:` header strings + 3 timestamps + the 3 `provider_message_id` strings, captured as a fenced code-block in `v1.6-VERIFICATION-LOG.md` under a new `email_deliverability_probe:` YAML block.
- **D-46-21 (Probe template = `EMAIL_OTP_LOGIN` placeholder render — already-locked content):** No new locked template for probing. The probe re-uses `EMAIL_OTP_LOGIN` with a fixture OTP code so the email body is locked Russian copy already on the v1.6 sign-off list. This avoids introducing a "probe-only template" that would never serve real users (anti-pattern: templates exist only to ship).
- **D-46-22 (Failure handling — DEFER if any one of the 3 fails alignment):** If yandex.ru passes but mail.ru fails DMARC alignment, that is a DEFER-46-N row, not a milestone-close blocker. RU-domain provider DMARC quirks (especially mail.ru tightening cycles) are operational, not v1.6-code-surface issues. Owner records the partial result + creates the DEFER row; v1.6 closes anyway. Hard-fail only if ALL THREE providers fail (signals a fundamental DKIM key / SPF record misconfiguration — that IS a v1.6 blocker).

### VER-13 — 6/6 CI gates green + AST gates (RESOLVED)

- **D-46-23 (Single CI run captures all 6+ green gates — screenshot or commit-SHA link in evidence):** The 6 are:
  1. backend `ruff check` (`.github/workflows/ci.yml:39`)
  2. backend `ruff format --check` (`:42`)
  3. backend `mypy` (`:45` — `--strict` per `pyproject.toml` config)
  4. backend `lint-imports` (import-linter — `:48`)
  5. backend OpenAPI drift gate (`:60-64` — `git diff --exit-code apps/backend/openapi.json`)
  6. frontend codegen drift gate (`:114-117` — `git diff --exit-code packages/api-client/src/schema.d.ts`)
  Plus the test-suite gate (`pytest`) — this is implicit in the integration tests passing. Plus the two AST commit-gates (SVC001 + LOCKED_EMAIL_TEMPLATES), which run inside the `pytest` test-suite as `tests/unit/test_*_ast.py` files (already green per Phases 41 / 45 — Phase 46 just snapshots).
  Evidence shape: one commit-SHA + CI-run-URL pair under `ci_evidence:` YAML in `v1.6-VERIFICATION-LOG.md`. The verifying commit is the one that lands `46-01-PLAN.md` (the OpenAPI regen) — that PR-equivalent commit MUST pass all gates.
- **D-46-24 (No new AST gates added in Phase 46):** SVC001 scope already covers `users/service.py` + `auth/password_reset_service.py` per Phase 41 D-41-28 + Phase 43 / 44 extensions. `LOCKED_EMAIL_TEMPLATES` walker scope already covers all 15 v1.6 constants per Phase 41 D-41-12 + Phase 45 D-45's `tests/unit/test_locked_email_templates_phase45.py`. Phase 46 verifies, does NOT extend.

### VER-14 — Owner sign-off + ≤5 inline regression cap (RESOLVED)

- **D-46-25 (Owner sign-off enumerates the 15 v1.6-era constants by literal name in `v1.6-VERIFICATION-LOG.md`):** The sign-off row is a `signed_off_templates:` YAML list containing the exact 15 strings (verbatim from `apps/backend/app/core/audit.py:264-289`):
  ```yaml
  signed_off_templates:
    - EMAIL_OTP_LOGIN                       # Phase 42 AUTH-EM-03
    - USER_INVITATION_EMAIL                 # Phase 44 USERS-03 + RESET-04
    - PASSWORD_RESET_EMAIL                  # Phase 44 RESET-03
    - EMAIL_EXPIRING_7D_VARIANT_A           # Phase 45 NOTIFY-08
    - EMAIL_EXPIRING_7D_VARIANT_B           # Phase 45 NOTIFY-08
    - EMAIL_EXPIRING_3D_VARIANT_A           # Phase 45 NOTIFY-08
    - EMAIL_EXPIRING_3D_VARIANT_B           # Phase 45 NOTIFY-08
    - EMAIL_EXPIRING_1D_VARIANT_A           # Phase 45 NOTIFY-08
    - EMAIL_EXPIRING_1D_VARIANT_B           # Phase 45 NOTIFY-08
    - EMAIL_BOOKING_CONFIRMED               # Phase 45 NOTIFY-10
    - EMAIL_BOOKING_CANCELLED_BY_CLIENT     # Phase 45 NOTIFY-10
    - EMAIL_BOOKING_CANCELLED_BY_OWNER      # Phase 45 NOTIFY-10
    - EMAIL_BOOKING_REMINDER_24H            # Phase 45 NOTIFY-10
    - EMAIL_PAYMENT_RECEIPT_SALE            # Phase 45 NOTIFY-12
    - EMAIL_PAYMENT_RECEIPT_REFUND          # Phase 45 NOTIFY-12
  ```
  Mirrors D-27-OWNER-COPY-LOCK lineage (per-constant enumeration in the verification log). Sign-off date = the date the verification session completes. Auto-recorded under `workflow.auto_advance = true` per the project convention (`.planning/config.json`).
- **D-46-26 (≤5 inline regression cap — DEFER-46-N rows for the 6th+):** Inline regressions discovered AT the gate (not in code-review of earlier phases) are fixed in-place IF the cumulative count stays ≤5. The 6th regression triggers a milestone-close decision:
  - Option A: defer the regression to v1.7 as `DEFER-46-N`, close v1.6 with the carry-forward documented.
  - Option B: open Phase 47 (NOT a v1.7 phase — a Phase-47 carry-out of v1.6 with regression fixes only, mirrors how v1.4 / v1.5 handled their own >5-regression close-outs).
  Owner picks at the moment-of-decision. Default recommendation: **Option A** unless the regression breaks a documented invariant (e.g. anti-oracle leak, RBAC bypass) — those MUST be fixed inline or block the close.
- **D-46-27 (`v1.6-VERIFICATION-LOG.md` shape — mirror of `v1.5-VERIFICATION-LOG.md`):** Same YAML frontmatter shape (`phase: 46-..., milestone: v1.6, verified_started:, verified:, status:, score:, signed_off_by:, signed_off_at:, overrides_applied:, overrides:[]`). Same `human_verification:` list shape (per-scenario row with `test:`, `via:`, `expected:`, `actual:`, `result:`, `evidence:`, `notes:`). NEW blocks: `email_deliverability_probe:` (D-46-20) AND `signed_off_templates:` (D-46-25) AND `race_tests_evidence:` (one row per VER-10 test with the test-file path + commit SHA where it ran).

### DEFER-40-01 lesson budgeting (architectural — RESOLVED)

- **D-46-28 (Explicit runbook scaffolding hardening time in the plan):** ROADMAP.md Phase 46 line explicitly calls out "(DEFER-40-01 lesson — budget runbook scaffolding hardening)". Phase 46 plan partitioning MUST include a dedicated wave / plan card for `run.sh` engineering BEFORE the verification session, not as a "we'll fix bugs as we hit them" mode. Concretely: the planner allocates `46-09-PLAN.md` (or equivalent) as `"Engineer .planning/milestones/v1.6-verification-evidence/run.sh — pre-flight asserts, X-CSRF-Token threading, idempotent scenario blocks, MailHog vs Postbox-sandbox switch, healthz path verification, fixture-default verification."` Owner sign-off on the run.sh shape happens BEFORE the verification session opens (mirrors the v1.5 D-40 mistake — running first, hardening later, cost a hotfix cluster).
- **D-46-29 (Fixture seeding is a plan-level concern, not a "do during verification" concern):** `apps/backend/scripts/seed_verification_fixtures.py` (or a v1.6 sibling `seed_v1_6_verification_fixtures.py`) MUST be the explicit data setup. Each curl scenario in `run.sh` re-seeds its own prerequisites at scenario head (mirrors v1.5 run.sh idempotency discipline). NO ad-hoc DBSHELL hand-seeding during the verification session.
- **D-46-30 (Reference the v1.5 run.sh fixes from commits `ade5d2d` + `cd1049c` as known-anti-patterns):** Planner should read those two commits during research and propagate the lessons (Alembic revision-id 32-char limit, `/healthz` vs `/health`, table name canonicalisation, fixture email defaults) into the v1.6 run.sh on day-zero. Avoids re-discovering them.

### Plan partitioning (architectural — Claude's discretion, with locked structure)

- **D-46-31 (Suggested wave breakdown — concrete shape, planner refines):**
  - **Wave 1:** OpenAPI handoff atomic regen (`46-01-PLAN.md`) — runs `export_openapi.py` + frontend codegen, commits both files atomically. Pre-flight endpoint enumeration per D-46-02. Single PR-equivalent commit.
  - **Wave 2:** schema.contract.test.ts forward-guards extension (`46-02-PLAN.md`) — adds the +12 `AssertNonNever` entries per D-46-05 / D-46-06. README v1.6 changelog section (D-46-09). Postman export script + `.planning/handoff/v1.6-postman.json` generation (D-46-08).
  - **Wave 3:** Race-test authoring — parallelisable across the 5 new tests (`46-03-PLAN.md` token-replay, `46-04-PLAN.md` soft-delete-reinvite, `46-05-PLAN.md` deactivate-refresh, `46-06-PLAN.md` bounce-webhook-active-send, `46-07-PLAN.md` double-pings, `46-08-PLAN.md` RFC2047-cyrillic).
  - **Wave 4:** Runbook engineering — `46-09-PLAN.md` per D-46-28 (run.sh + scenario evidence directory scaffold).
  - **Wave 5:** Live verification session — `46-10-PLAN.md` execution of the 8 scenarios + deliverability probe + capture of CI gate evidence + owner sign-off + DEFER-46-N row triage + write `v1.6-VERIFICATION-LOG.md`. This wave is SERIAL (single live session, not parallelisable).
  - **Optional Wave 6:** Inline regression hotfixes if any surface during Wave 5 (≤5 cap per D-46-26).
- **D-46-32 (Each wave produces an evidence artifact, not just code):** Wave 1 → commit SHA. Wave 2 → diff of `schema.contract.test.ts` + diff of README. Wave 3 → 5 new test files green in pytest. Wave 4 → run.sh + scenario-evidence directory tree. Wave 5 → `v1.6-VERIFICATION-LOG.md` final content. The evidence chain feeds the milestone-close artifact.

### Claude's Discretion

- **Exact diff shape inside `schema.contract.test.ts`** — single `const _v16Checks: [...] = [...]` tuple at the bottom vs three separate `const _v16UsersChecks`, `const _v16ResetChecks`, `const _v16EmailChecks` tuples. Either is acceptable; the latter is more readable for a 12-entry delta. Default recommendation: **three separate tuples per epic** matching the three section comment-banners (D-46-05).
- **Whether to author `apps/backend/scripts/export_postman.py` as a Python script or a Node script** — Python is consistent with `export_openapi.py` (same dir, same shell, same `uv run` entrypoint). Node would let us reuse `openapi-to-postmanv2` npm package directly. Default: **Python**, walks `openapi.json` JSON tree, emits Postman v2.1 schema as JSON. ~150 LOC. Avoids new toolchain.
- **MailHog vs Yandex Postbox sandbox for scenario 01/03/05/06 email-arrival assertions** — owner picks at execute-time per D-46-13. Default: **MailHog under a `--profile dev` docker-compose service** (zero external dep, faster to spin up).
- **Whether to delete `.planning/milestones/v1.5-verification-evidence/run.sh` after Phase 46 lands** — no, keep it as the DEFER-40-01 reference + the lessons-learned source. Future v1.9 carry-forward execution may revive it.
- **Whether to update `apps/admin-web/src/shared/api/services/http/` mock-mode-vs-http stubs after the schema.d.ts regen** — NO (Phase 46 is backend-only per the project's "backend-only milestone" discipline; admin-web HTTP wiring is v2.0). The `schema.d.ts` change MAY surface a TypeScript drift in `apps/admin-web` if it imports from `@sportzal/api-client` — verify at execute-time via `pnpm -F admin-web typecheck`; if it breaks, that's a Phase 46 inline regression (counts against the ≤5 cap).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap + requirements
- `.planning/ROADMAP.md` §"Phase 46: OpenAPI Handoff + Milestone Verification" (lines 289–300) — phase goal + 6 success criteria + dependencies + DEFER-40-01 budget call-out.
- `.planning/REQUIREMENTS.md` §"OpenAPI drift gate refresh — HANDOFF-03..04" (lines 85–90) + §"Milestone verification — VER-09..14" (lines 92–101) — verbatim requirement text for the 8 reqs in scope.
- `.planning/REQUIREMENTS.md` traceability table (lines 180–189) — confirms Phase 46 = 8 reqs.
- `.planning/PROJECT.md` §"Current Milestone: v1.6 Email channel + Multi-user admin" (lines 42–53) — milestone target + region constraints.
- `.planning/PROJECT.md` §"v1.5 milestone verification + DEFER-40-01" (line 23) — verbatim record of the v1.5 run.sh hotfix cluster (Alembic revision-id length, /healthz path, table-name drift, fixture defaults) that Phase 46 must NOT re-discover.

### Prior phase context (v1.6 lineage)
- `.planning/phases/41-infra-bedrock-anti-oracle-scaffold/41-CONTEXT.md` — `LOCKED_AUDIT_EVENTS` + `LOCKED_EMAIL_TEMPLATES` AST gates (D-41-11/12), Alembic 0022 + 0023 + 0024 (deleted_at, password_reset_tokens, channel discriminator), Protocol slots (D-41-24), SVC001 walker scope (D-41-28).
- `.planning/phases/42-email-transport-layer-email-otp-fallback/42-CONTEXT.md` — EmailDispatcher (D-42-25..28), `EmailEnvelope` shape (D-42-16), Jinja2 SandboxedEnvironment (D-42-05), NBSP discipline (D-42-23), `email_send_log` schema (D-42-18), bounce webhook (D-42-17), circuit breaker (Phase 42 backoff).
- `.planning/phases/43-multi-user-admin-module/43-CONTEXT.md` — USERS-* endpoints, `invitation_tokens` (now unified into `password_reset_tokens` via D-41-04), revoke endpoint (D-43-19 already shipped).
- `.planning/phases/44-invitation-password-reset-flow/44-CONTEXT.md` — RESET-* endpoints, anti-oracle envelope (D-44-06..09), constant-time floor (D-44-07), atomic-consume SQL (D-44-14), 410 Gone (D-44-15), bounded-timing test contract (D-44-07 / Phase 41 D-41-17).
- `.planning/phases/45-email-notification-mirrors/45-CONTEXT.md` — NOTIFY-* fanout, `payment_receipts` Alembic 0029 (D-45-11), 12 new locked templates (D-45-15..19), receipt fanout SQL (D-45-08), `payment_receipts` race test (D-45-28).

### Prior milestone verification precedents (handoff + run.sh shape)
- `.planning/milestones/v1.5-VERIFICATION-LOG.md` — YAML frontmatter shape + `human_verification:` list pattern. v1.6 mirrors verbatim with added `email_deliverability_probe:`, `signed_off_templates:`, `race_tests_evidence:` blocks.
- `.planning/milestones/v1.4-VERIFICATION-LOG.md` — multi-scenario verbose-evidence pattern (operator transcripts inline).
- `.planning/milestones/v1.5-verification-evidence/run.sh` — REFERENCE only. Source of the DEFER-40-01 lessons (Alembic id-length, /healthz, table names, fixture emails, CSRF threading). DO NOT copy-paste; engineer v1.6 run.sh fresh per D-46-10.
- `.planning/milestones/v1.4-verification-evidence/` — file naming convention for per-scenario evidence files (`NN_<slug>.{txt,http}`).
- `.planning/handoff/v1.4-postman.json` + `.planning/handoff/v1.4-auth-runbook.md` — precedent for handoff artifact shape; v1.6 ships parallel `v1.6-postman.json`.

### Backend code anchors (must read before regen)
- `apps/backend/scripts/export_openapi.py` — byte-stable JSON export (Phase 9 D-04..D-06 lineage). DO NOT modify; just invoke.
- `apps/backend/app/main.py` (`create_app` + router includes) — verify ALL 10 new endpoints are wired before regen (D-46-02).
- `apps/backend/app/core/audit.py:264-289` (`LOCKED_EMAIL_TEMPLATES` frozenset) — source-of-truth list for the 15 v1.6 constants in the owner sign-off (D-46-25).
- `apps/backend/app/core/audit.py` (`LOCKED_AUDIT_EVENTS` frozenset) — 67-entry list per Phase 41 D-41; all `payment_receipt_emailed`, `email_sent`, `email_send_failed`, `password_reset_*`, `user_*`, `otp_*` events already pre-registered.
- `apps/backend/app/modules/users/router.py` + `apps/backend/app/modules/auth/router.py` — locate the new endpoints from Phases 43/44; sanity-check `tags=` (`_internal` for the webhook per D-46-03).
- `apps/backend/scripts/seed_verification_fixtures.py` (existing) + `apps/backend/scripts/seed_v1_4_verification_fixtures.py` (existing) — fixture-loading precedent; v1.6 needs a parallel `seed_v1_6_verification_fixtures.py` if the existing scripts don't cover the new USERS-* / RESET-* / NOTIFY-* test data shape (verify at execute-time).
- `apps/backend/docker-compose.yml` — the `docker compose up` target per VER-09 spec.

### Frontend code anchors
- `packages/api-client/src/schema.contract.test.ts` (305 lines as of 2026-05-20) — extension target for the +12 forward-guards (D-46-05).
- `packages/api-client/src/schema.d.ts` — auto-generated; regenerated by frontend codegen step per D-46-01.
- `packages/api-client/package.json` `scripts.codegen` — invocation alias for the openapi-typescript regen.
- `apps/backend/README.md` (44 lines) — append v1.6 changelog section per D-46-09.

### CI + drift gate anchors
- `.github/workflows/ci.yml` — full gate suite. Backend drift gate (lines 60-64), frontend drift gate (lines 114-117), ruff/mypy/lint-imports (lines 39-48). Phase 46 evidence captures one green run of this workflow.

### Anti-pattern + pitfall references
- `.planning/PITFALLS.md` — DEFER-40-01 cluster, REG-29-04 eager-import lineage, anti-oracle posture, NBSP discipline.
- `.planning/RETROSPECTIVE.md` — v1.5 verification hotfix cluster lessons-learned.

### Out-of-scope reference (do NOT touch in Phase 46)
- `apps/admin-web/**` — frozen mock-mode contract reference; no UI surface for any v1.6 endpoint (v2.0 frontend handoff). One exception: if `pnpm -F admin-web typecheck` breaks after the `schema.d.ts` regen, that's a Phase 46 inline regression to fix.
- Production deployment configuration (Yandex Cloud LB, real DKIM keys, prod database) — VER-12 probe runs from staging or a throwaway prod-equivalent; full prod cutover is v1.7 ops concern.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`scripts/export_openapi.py`** (Phase 9 D-04..D-06) — byte-stable JSON dumper. Idempotent. cwd-independent. No DB / Redis touched (lifespan-safe). Phase 46 invokes verbatim; no changes.
- **Frontend codegen alias** (`packages/api-client/package.json:scripts.codegen`) — regenerates `schema.d.ts` from `openapi.json` via `openapi-typescript`. Phase 46 invokes; no changes.
- **`schema.contract.test.ts` assertion shape** — `type _Check = AssertNonNever<paths[P][M]>` + `const _check: _Check = true`. Per-block comment banner convention already established for v1.2 / v1.4 / Phase 23 surfaces. Phase 46 adds three v1.6 banner blocks (D-46-05).
- **`AssertNonNever<T>` + `HasPath<P>` type helpers** (`schema.contract.test.ts:12-21`) — re-used verbatim for all new forward-guards.
- **`tests/conftest.py` Postgres + SAVEPOINT fixture** — used by all 6 VER-10 race tests; no new fixture infrastructure needed.
- **`.github/workflows/ci.yml` drift-gate steps** — green-on-pass; Phase 46 just runs against the regen commit.
- **`apps/backend/docker-compose.yml`** — the live-stack target for `docker compose up`. Already in repo. Phase 46 may add a `--profile dev` MailHog service for sandbox-inbox capture (D-46-13) — small, additive change.
- **`apps/backend/scripts/verify/` directory** (8 existing shell scenarios from v1.4/v1.5) — REFERENCE for run.sh scenario block shape (preamble, idempotent reset, curl invocation, response capture, assertion-on-status). v1.6 `run.sh` mirrors the structure, NOT the v1.5 `.planning/milestones/v1.5-verification-evidence/run.sh` which carries the DEFER-40-01 bugs.

### Established Patterns
- **Single atomic regen commit** (Phase 35 / Phase 40 lineage): backend openapi.json + frontend schema.d.ts in one commit; CI drift gates green in the same run.
- **Per-block forward-guard comment banner** in `schema.contract.test.ts`: `// --- <milestone> surface (<phase range>) ----`. Phase 46 adds three v1.6 banners.
- **Byte-stable JSON output** (`json.dumps(..., indent=2, sort_keys=True, ensure_ascii=False) + '\n'`) — Phase 9 standard. Applied to both openapi.json and the new Postman export.
- **Run.sh idempotent scenarios** (v1.4 / v1.5 lineage): each scenario psql-DELETEs its own priors at head; re-runnable against the same stack.
- **Verification-log YAML frontmatter** + `human_verification:` list — established at v1.3-VERIFICATION-LOG.md, evolved through v1.4 / v1.5. v1.6 inherits + adds three new blocks.
- **DEFER-N row discipline** for >5-regression carry-forward (v1.4 / v1.5 lineage) — captured in PROJECT.md milestone roadmap section.

### Integration Points
- **`apps/backend/scripts/export_openapi.py` invocation** — runs in `apps/backend/` cwd via `uv run python -m scripts.export_openapi`. CI does this at `.github/workflows/ci.yml:51`; the regen plan does the same locally.
- **Frontend codegen** — `pnpm --filter @sportzal/api-client codegen` (verify alias at execute-time). CI does this at `.github/workflows/ci.yml:~110` (the step before the schema.d.ts drift gate); the regen plan does the same locally.
- **`apps/backend/docker-compose.yml` profiles** — add `--profile dev` for MailHog (D-46-13) without affecting the default `up` shape used by `tests/` (those use the testcontainers-style ephemeral DB, not docker-compose).
- **`.planning/milestones/v1.6-verification-evidence/` directory** — NEW directory tree (mirrors `v1.5-verification-evidence/`); created by Wave 4 (run.sh + curl/ subdir) and Wave 5 (final transcripts + email-probe/ subdir).
- **Anti-oracle integration tests** — `tests/integration/test_password_reset_no_oracle.py` (RESET-06 / Phase 41 + ungated Phase 44) and `tests/integration/test_otp_email_anti_oracle.py` (AUTH-EM-04 / Phase 42). Phase 46 verifies pass; doesn't author.

</code_context>

<specifics>
## Specific Ideas

- **Wave 5 verification session is SERIAL** — single owner-driven live session. Other waves (1–4) are parallelisable across plan executor agents. Wave 5 is the human-in-the-loop gate.
- **Run.sh authoring uses `set -euo pipefail` + `trap 'echo FAILED at line $LINENO' ERR`** — fail-fast with clear line-number reporting (DEFER-40-01 lesson: the v1.5 run.sh swallowed errors silently in places).
- **Each scenario evidence file MUST contain both the request and the response** — `curl -i -v 2>&1 | tee evidence/NN_slug.http`. Pure response-only captures lose the audit trail of the request headers (X-CSRF-Token presence, cookie threading, Idempotency-Key).
- **Owner sign-off auto-recording cadence** — per `.planning/config.json` `workflow.auto_advance = true`. The 15-template enumeration is the sign-off content; owner email is `andre.shipunov@icloud.com` per the standing project record.
- **`v1.6-VERIFICATION-LOG.md` YAML frontmatter** mirrors v1.5 verbatim with these field changes: `phase: 46-openapi-handoff-milestone-verification`, `milestone: v1.6`, `status: verified` (full close, NOT `partial_minimal_verification`), `score: "8/8 — HANDOFF-03..04 + VER-09..14 all verified"`, plus the three new YAML blocks (`email_deliverability_probe:`, `signed_off_templates:`, `race_tests_evidence:`).
- **Sandbox inbox URL convention** (if MailHog): `http://localhost:8025`. If Yandex Postbox sandbox: the owner's project console URL. Recorded in `run.sh` env-var comments.
- **Race tests run via `pytest tests/integration/test_*_race.py -v --no-cov`** — keep them in the standard test suite (not a separate "race" test target); coverage suppression is to speed up the asyncio.gather-heavy runs.

</specifics>

<deferred>
## Deferred Ideas

- **`operation_id=` curation across all v1.6 endpoints** — v1.9 (D-35-07 lineage). Phase 46 ships auto-generated operation IDs.
- **`@sportzal/api-client` npm publish** — v1.9 (whole "API Handoff + Production Hardening" milestone).
- **Postman v2.1 collection + Newman CLI runner + Postman handoff Confluence/Notion publish** — v1.9. Phase 46 ships the JSON file in-repo only.
- **OpenAPI doc-site + versioned spec URL** (Swagger UI hosted endpoint) — v1.9.
- **Idempotency-Key hardening across all POST endpoints (CR-01/02/02b carry-over)** — v1.9.
- **Multi-region SPF/DKIM/DMARC probe** (gmail.com, outlook.com, proton.me, hotmail.com) — v1.9.
- **Production-load smoke** (k6, locust) — never v1.6.
- **Admin-web UI surfaces for any v1.6 endpoint** — v2.0 frontend handoff.
- **`_internal/email/webhook` Postman-collection inclusion** — never (internal-only path; tag-filtered out per D-46-08).
- **DEFER-46-N rows** — placeholder for inline regressions discovered at the gate beyond the ≤5 cap (D-46-26). Roll to v1.7 by default.
- **Full v1.5 carry-forward operator runbook re-execution (DEFER-40-01 backfill)** — v1.9 per PROJECT.md milestone roadmap.
- **Admin-web `pnpm -F admin-web typecheck` re-greening** — IF the schema.d.ts regen breaks any TypeScript references in `apps/admin-web/src/shared/api/services/http/*` (Phase 46 inline fix if small, DEFER if invasive).
- **Webhook signature verification hardening** (HMAC instead of bearer) for `/_internal/email/webhook` — v1.7 if Postbox starts offering it; v1.6 ships whatever Phase 42 D-42 wired.
- **CSRF rotation policy review** (out-of-band — surfaced if the run.sh CSRF threading reveals a UX gap) — v1.7.
- **Race-test runtime budget** (if any of the 6 takes >5s, optimize) — v1.7 testing-hygiene phase.

</deferred>

---

*Phase: 46-openapi-handoff-milestone-verification*
*Context gathered: 2026-05-20*
