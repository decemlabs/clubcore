# Phase 44: Invitation + Password-Reset Flow - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-19
**Phase:** 44-invitation-password-reset-flow
**Mode:** `--auto` (no AskUserQuestion calls; recommended option auto-selected for every gray area per `workflows/discuss-phase/modes/auto.md`)
**Areas discussed:** Token storage mechanism, Token entropy + URL format, /password-reset/request anti-oracle envelope, Rate-limit topology, /password-reset/confirm atomic-consume, /users/invitations/accept module split, PASSWORD_RESET_EMAIL template content, xfail-strict ungating, Cleanup cron schedule, Test surface, Plan packaging

---

## Token storage mechanism (Open Conflict #2)

| Option | Description | Selected |
|--------|-------------|----------|
| DB-table `password_reset_tokens` with `purpose` column | Atomic-consume via `UPDATE … RETURNING`; revocation = set `consumed_at`; Phase 41 D-41-04 already shipped table + ORM + partial-UNIQUE + hash-lookup index | ✓ |
| itsdangerous-stateless signed tokens | Single-use via `password_changed_at` equality check; requires new `users.password_changed_at` column; signed payload leaks user_id thinly | |

**Auto choice:** DB-table — Phase 41 D-41-04 lock; codebase already aligned (`password_reset_token_model.py`, migration 0025 live).
**Notes:** REQUIREMENTS.md text mentioning `bumps users.password_changed_at` treated as legacy phrasing — D-41-04 + codebase are the locked truth (no such column exists in `users`).

---

## Token entropy + URL format

| Option | Description | Selected |
|--------|-------------|----------|
| `secrets.token_urlsafe(32)` (256 bits) + sha256 storage + URL fragment | OWASP 2025 floor; mirrors v1.1 refresh-token discipline; Phase 43 `_hash_token` precedent | ✓ |
| `secrets.token_urlsafe(16)` (128 bits) + sha256 + URL fragment | Half the entropy; smaller URLs; still above brute-force threshold | |
| HMAC-signed UUID | Compact, but couples to a signing key + revocation requires DB lookup anyway | |

**Auto choice:** `secrets.token_urlsafe(32)` + sha256 + URL fragment `#token=…`.
**Notes:** TTLs locked per RESET-03 — invitation 7d, reset 1h. Both delivered via URL fragment, never URL path (PITFALLS token-leak-via-Referer).

---

## /password-reset/request anti-oracle envelope

| Option | Description | Selected |
|--------|-------------|----------|
| Identical 202 + identical body + 500ms constant-time floor + audit-emit in both branches + email only in known-active branch | Closes RESET-06 contract; matches Phase 41 xfail-strict test; cold path <100ms variance fits under 100ms tolerance window | ✓ |
| 200 OK with different bodies per case | Trivially breaks anti-oracle; rejected | |
| 202 + identical body but no constant-time floor | Leaves timing oracle (Argon2 verify ≠ DB INSERT timing) | |

**Auto choice:** Identical 202 + identical body + 500ms floor + dual-branch audit emit.
**Notes:** Audit emit in unknown-email branch uses `actor_user_id=None`, `target_user_id=None`, `email_hint=<lowercased email>` per D-41-10.

---

## Rate-limit topology

| Option | Description | Selected |
|--------|-------------|----------|
| 3 Redis fixed-window keys (per-IP 5/15min + per-email 1/min + per-email 5/hour) + identical 202 on hit | Reuses `auth/rate_limit.py` shape; anti-oracle preserved by NOT returning 429; structlog WARN for ops visibility | ✓ |
| Sliding-window Redis sorted-set | More precise; not justified for 1-gym tenant traffic levels; more complex to test | |
| Per-IP only | Misses email-targeted abuse | |
| 429 on hit | Leaks rate-limit state; anti-oracle violation | |

**Auto choice:** 3 fixed-window keys + identical 202 + structlog WARN.
**Notes:** Order of checks = IP → email-minute → email-hour, all BEFORE the user lookup (anti-oracle parity for unknown-email path).

---

## /password-reset/confirm atomic-consume

| Option | Description | Selected |
|--------|-------------|----------|
| Single-SQL `UPDATE … RETURNING` keyed by `token_hash` + `purpose='password_reset'` + `consumed_at IS NULL` + `expires_at > NOW()` | Race-tight, zero application-layer state machine, mirrors v1.1 refresh-token rotation | ✓ |
| Multi-statement: SELECT + UPDATE | Race-vulnerable under concurrent confirms | |
| Two-phase commit | Overkill for single-row atomic flip | |

**Auto choice:** Single-SQL atomic consume.
**Notes:** Zero-row return → 410 Gone with generic body (no enumeration). On success: Argon2 rehash + `invalidate_all_families_for_user(reason='password_reset')` + audit emit + commit. No cookie issuance — user must `/auth/login` with new password.

---

## /users/invitations/accept module split

| Option | Description | Selected |
|--------|-------------|----------|
| Router in `users/router.py`, service in `auth/password_reset_service.py` | Atomic-consume is auth-bedrock (SVC001 walker scope); URL groups naturally under `/users/invitations/...`; D-41-28 alignment | ✓ |
| Router + service both in `users/` | Couples users module to atomic-consume SVC001 semantics; SVC001 walker would need scope extension | |
| Router + service both in `auth/` | URL would be `/auth/invitations/accept` — weaker UX/discoverability | |

**Auto choice:** Cross-module split (router in users/, service in auth/).
**Notes:** Mirrors how Phase 43's invitation-revoke service lives in `users/service.py` but the atomic-consume SQL pattern is parameterised in the service layer.

---

## PASSWORD_RESET_EMAIL template content

| Option | Description | Selected |
|--------|-------------|----------|
| Lives in `app/modules/auth/email_templates.py`; variables `{reset_url}` + `{expires_at_human}` only; locked `Final[str]` subject; sandboxed Jinja2 mirroring `EMAIL_OTP_LOGIN` | Per-domain ownership (D-39-02/D-42-06); anti-oracle content discipline (D-42-23 — no `{full_name}`); SandboxedEnvironment + autoescape on HTML | ✓ |
| Include `{full_name}` for personalisation | Defeats stolen-mailbox replay defence (D-42-23) | |
| Move to `app/integrations/email/templates/` | Violates per-domain ownership boundary (D-39-02) | |

**Auto choice:** `auth/email_templates.py` adjacent to `EMAIL_OTP_LOGIN`; subject `"Восстановление пароля Sportzal"`; only `{reset_url}` + `{expires_at_human}` interpolated.
**Notes:** Russian copy drafted by planner, owner sign-off at plan SUMMARY as `D-44-OWNER-COPY-LOCK`.

---

## xfail-strict ungating discipline (RESET-06 → GREEN)

| Option | Description | Selected |
|--------|-------------|----------|
| Remove `@pytest.mark.xfail(strict=True)` marker in the same atomic commit that ships RESET-01; plan 44-08 is the [BLOCKING] checkpoint | D-41-17 explicit handoff; strict=True ensures CI breaks if marker is stripped without endpoint satisfying contract | ✓ |
| Remove marker in a separate later commit | Leaves drift window where suite passes-as-xfail erroneously | |
| Keep xfail-strict and let it pass-as-xfail naturally | strict=True means xfail-pass is itself a CI failure — would block the commit | |

**Auto choice:** Atomic ungate in plan 44-08.
**Notes:** Plan 44-08 also extends the test with the audit-row assertion (closes audit half of RESET-01 per D-41-10).

---

## Cleanup cron schedule

| Option | Description | Selected |
|--------|-------------|----------|
| Daily 03:30 Europe/Moscow ARQ cron; DELETE rows where `expires_at < now() - 30 days` | Off-peak (well away from 06:15/06:35 notification crons); D-41-06 retention window; structlog observability via deleted-row count | ✓ |
| Hourly cron | Wasteful at 1-gym scale (~30 steady-state rows); harder to spot anomalies in logs | |
| On-INSERT cleanup trigger | DB-side complexity; harder to test; obscures the cleanup behaviour | |
| Never delete | Unbounded table growth (slow); blocks future forensic queries with stale rows | |

**Auto choice:** Daily 03:30 cron, 30-day retention.
**Notes:** No audit emit on cleanup (housekeeping, not state change).

---

## Test surface

| Area | Recommended file(s) | Selected |
|------|---------------------|----------|
| Anti-oracle ungate + audit-row extension | `tests/integration/auth/test_password_reset_no_oracle.py` (extend Phase 41) | ✓ |
| Confirm happy path + replay + expired + weak-password | `tests/integration/auth/test_password_reset_confirm.py` | ✓ |
| Rate limit (3 windows + identical 202 on hit) | `tests/integration/auth/test_password_reset_rate_limit.py` | ✓ |
| Invitation-accept happy path + races + full_name update | `tests/integration/auth/test_invitation_accept.py` | ✓ |
| Invite-accept INSERT-only invariant (Pitfall 4) | `tests/integration/auth/test_invitation_accept_insert_only.py` | ✓ |
| Template render snapshot | `tests/unit/auth/test_password_reset_email_render.py` | ✓ |
| AST gate extension | `tests/unit/test_locked_email_templates_ast.py` (one new real-callsite assertion for `PASSWORD_RESET_EMAIL`) | ✓ |
| Cleanup cron behaviour | `tests/integration/workers/test_cleanup_password_reset_tokens.py` | ✓ |

**Auto choice:** Full set per Phase 42 + 43 discipline (Phase 42 CR-01 + Phase 43 D-43-34 carried forward).
**Notes:** Real Postgres via SAVEPOINT per-test; real `audit.emit()` exercised; sandbox email client only.

---

## Plan packaging (wave structure hint)

| Option | Description | Selected |
|--------|-------------|----------|
| 4 waves, ~14 plans; Wave 1 parallel skeleton; Wave 2 service bodies; Wave 3 tests; Wave 4 cron | Mirrors Phase 42 + 43 file-overlap-minimisation discipline | ✓ |
| 2 waves (mega-plans) | Loses parallelism; harder to review | |
| 6+ waves (granular) | Excessive coordination overhead for a 5-requirement phase | |

**Auto choice:** 4-wave structure documented in D-44-38. Planner refines based on actual file-overlap analysis.
**Notes:** Plan 44-08 (xfail ungate) is the [BLOCKING] checkpoint replacing the migration round-trip checkpoint (since Phase 44 ships zero migrations).

---

## Claude's Discretion

- Exact Russian wording of `PASSWORD_RESET_EMAIL` subject/body/text (owner-copy-lock — drafted by planner, owner-signed-off at plan SUMMARY as `D-44-OWNER-COPY-LOCK`).
- Whether `PASSWORD_RESET_TOKEN_TTL` lives in `app/modules/auth/constants.py` (new file — recommended) vs alternative locations.
- Internal helper function naming (`_render_password_reset_email` vs `_make_password_reset_envelope` etc.).
- Whether the rate-limit short-circuit emits a sentinel `audit_correlation_id` for forensic linking (recommend: yes, `uuid4()` for structlog grep correlation).
- Whether `accept_invitation` issues fresh CSRF tokens alongside the session cookie pair (recommend: yes — `issue_session_cookies` handles this transparently in Phase 5; mirrors `/auth/login`).
- Whether to add `audit.emit("invitation_accepted_with_full_name_correction", ...)` for the full-name-update branch (recommend: NO — covered by parent event).

---

## Deferred Ideas

See CONTEXT.md `<deferred>` section — 12 items deferred to v1.7 / v1.8 / v2.0 / Phase 46.

Key deferrals:
- Owner administrative-override password reset → v1.7
- Multi-channel reset (SMS / Telegram-DM) → v1.7+
- Self-service email change → v1.7+
- `?include_reset_link=true` escape hatch → v1.7+ (rejected for v1.6 per D-44-28 — defeats anti-oracle on self-service)
- Forensic audit-read API → v1.8
- Account-lockout after N failed resets → v1.7+
- 2FA on password reset → v1.7+
- OpenAPI schema regen → Phase 46 HANDOFF-03
- Frontend integration → v2.0 design-team handoff

---

## Auto-mode pass log

[--auto] Context exists (none — created fresh). Skipping update prompt.
[--auto] todos matched: 0 (no folding).
[--auto] Gray areas selected: ALL (token storage / entropy / anti-oracle envelope / rate-limit / atomic-consume / module split / template content / xfail ungating / cleanup cron / test surface / plan packaging).
[--auto] CONTEXT.md written in single pass — proceeding to write_context completion and auto_advance per chain.md.
