---
phase: 42-email-transport-layer-email-otp-fallback
verified: 2026-05-19T12:00:00Z
status: passed
score: 6/6 success criteria verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 4/6
  gaps_closed:
    - "SC#1 / CR-01: audit.emit kwargs flattened in dispatch_email.py (both ok + failure branches); integration test exercises real audit.emit + queries audit_log"
    - "SC#2 / CR-02: _constant_time_floor applied in try/finally wrapper inside request_otp_telegram; case B included in 4-case body+timing parity assertion; misleading 'body shape diverges' comment removed"
    - "SC#4 / CR-03: record_failure Redis sequence replaced with atomic redis.pipeline(transaction=True) MULTI/EXEC block; concurrency test added under asyncio.gather"
    - "SC#1 / CR-04: defensive UPDATE pass added to migration 0027 before partial-UNIQUE creation; regression test seeds colliding rows and verifies clean migration"
    - "WR-01: bounce_type CHECK constraint added in migration 0029"
    - "WR-02: webhook 202-on-unknown messageId event name unified to email_webhook_orphan_message_id"
    - "WR-03: email_lower (not user.email) passed to dispatcher in request_otp_email"
    - "WR-04: dispatch_email writes status='circuit_open' on breaker-short path (not 'rejected'); CHECK constraint extended in migration 0029"
    - "WR-06: HMAC signature normalised with .strip().lower() before compare_digest"
  gaps_remaining: []
  regressions: []
closed_gaps:
  - gap: "CR-01 audit.emit shape crash in dispatch_email"
    closed_by:
      - plan: 42-12
        commits:
          - "886eda1 test(42-12): add integration test for real audit.emit + audit_log query"
          - "d8e93ac test(42-12): rewrite unit tests to assert flattened audit.emit kwargs"
          - recovered_via: "ca8d256 (worktree-merge recovery)"
    sc: "SC#1, EMAIL-03"
  - gap: "CR-02 request_otp_telegram missing _constant_time_floor; case B excluded from parity test"
    closed_by:
      - plan: 42-13
        commits:
          - "6566cd7 test(42-13): include case B in 4-case body+timing parity assertion"
          - recovered_via: "ca8d256 (worktree-merge recovery)"
    sc: "SC#2, AUTH-EM-02, AUTH-EM-04"
  - gap: "CR-03 non-pipelined Redis sequence in circuit_breaker.record_failure"
    closed_by:
      - plan: 42-14
        commits:
          - "394b37e test(42-14): add concurrency tests for record_failure at threshold boundary"
          - recovered_via: "ca8d256 (worktree-merge recovery)"
    sc: "SC#4, EMAIL-06"
  - gap: "CR-04 migration 0027 no defensive UPDATE pass before partial-UNIQUE"
    closed_by:
      - plan: 42-15
        commits:
          - "d99ee34 fix(42-15): add CR-04 defensive UPDATE pass to migration 0027"
          - "04dfe7e test(42-15): add CR-04 regression test for migration 0027 colliding rows"
          - "9a7e20c fix(42-15): repair CR-04 regression test FK violation + stale head assertion"
    sc: "SC#1 (deploy safety), AUTH-EM-01"
  - gap: "WR-01/02/03/04/06 hygiene bundle (bounce_type CHECK, orphan event name, email_lower, circuit_open status, HMAC normalisation)"
    closed_by:
      - plan: 42-16
        commits:
          - "4583766 feat(42-16): add migration 0029 with bounce_type CHECK and circuit_open status"
          - "a1befb3 fix(42-16): use status='circuit_open' on breaker shorts in dispatch_email"
          - "94514f1 fix(42-16): normalise HMAC signature and unify orphan webhook event name"
          - "33a26b4 fix(42-16): pass email_lower to dispatcher in request_otp_email"
    sc: "EMAIL-03/06/07, AUTH-EM-02"
recovery_note: |
  Plans 42-12, 42-13, and 42-14 (CR-01, CR-02, CR-03 gap-closure fixes) were executed in
  parallel worktrees but their commits were lost from master during worktree merge due to a
  merge-conflict resolution error that discarded the worktree HEAD refs. Recovery procedure:
  (1) git log --all showed the commits still present as dangling objects (3 separate worktree
  HEADs: worktree-agent-afaa84e750fd9d0d0, worktree-agent-a0c09df84c3781a65, and the 42-12
  worktree); (2) each was cherry-picked back to master in chronological wave order; (3) the
  aggregate recovery was recorded in commit ca8d256 "chore(42): recover lost fix commits for
  42-12, 42-13, 42-14 worktrees". A subsequent FK-violation and stale head-assertion in the
  CR-04 regression test was repaired in commit 9a7e20c. Verification of reachability confirmed
  via: git merge-base --is-ancestor 688ae24 HEAD (CR-01), f171b06 HEAD (CR-02), e4628f4 HEAD
  (CR-03) — all return exit code 0.
remaining_gaps: []
human_verification:
  - test: "docker compose up → real Yandex Cloud Postbox sandbox send → confirm 6-digit code arrives in sandbox inbox"
    expected: "Sandbox inbox receives the locked EMAIL_OTP_LOGIN template with a 6-digit code"
    why_human: "Requires running services and a Yandex Cloud Postbox sandbox credential. Cannot be verified statically. After the CR-01 fix the dispatch_email worker no longer crashes at the audit.emit step, so the full end-to-end path (SES call + audit row + EmailSendLog commit) is now operational in code."
  - test: "Run alembic upgrade head against a pre-v1.6 database that has prior otp_codes rows"
    expected: "Migration 0027 defensive UPDATE pass cleans duplicate same-(user_id, channel) consumed_at IS NULL rows without error; partial-UNIQUE created clean"
    why_human: "The regression test (test_migration_0027_cleanup.py) validates the defensive UPDATE logic in isolation; full round-trip against a production-like dataset with real prior Telegram OTP rows requires a real Postgres instance."
  - test: "Apply infra/dns/sportzal.ru.zone at Reg.ru — substitute the real Postbox-issued DKIM public key for the placeholder"
    expected: "SPF passes, DKIM signs with the real p= value, DMARC reports route to dmarc-reports@sportzal.ru"
    why_human: "Zone file ships with DKIM p=<2048-bit-public-key-placeholder> (IN-03). Operator must obtain the real public key from Yandex Cloud Postbox and substitute before registrar push."
  - test: "Force 5 consecutive 5xx responses from provider → observe circuit opens within 60s window → subsequent jobs return circuit_open result"
    expected: "Circuit-open marker set at sz:email:circuit:yandex_postbox with 5min TTL; dispatch_email returns classification='transient_error' with status='circuit_open' without calling SES"
    why_human: "Requires a controllable 5xx-injection harness or mock SES server in an actual running ARQ worker environment. The unit + concurrency tests exercise the breaker primitive; the full dispatch_email integration path under a real ARQ worker requires a running stack."
---

# Phase 42: Email Transport Layer + Email OTP Fallback Verification Report

**Phase Goal:** Sportzal can send a transactional email asynchronously through a verified РФ-domiciled provider end-to-end, with circuit-breaker protection, bounce-webhook intake, and an immediate consumer (email-channel OTP fallback for `/auth/otp/request`) proving the slot wiring works.

**Verified:** 2026-05-19T12:00:00Z
**Status:** PASSED
**Re-verification:** Yes — after gap closure (CR-01..CR-04 + WR hygiene bundle)
**Score:** 6/6 success criteria verified

---

## Re-verification Summary

Previous verification (initial, 2026-05-19T00:00:00Z) found:

- SC#1 FAILED (CR-01): `audit.emit(... payload=<Model>)` kwarg shape caused `ValidationError` on every `dispatch_email` invocation
- SC#2 PARTIAL (CR-02): `request_otp_telegram` missing `_constant_time_floor`; case B excluded from parity assertion with misleading comment
- SC#4 WARNING (CR-03): non-pipelined Redis sequence in `record_failure` had concurrency race at threshold boundary
- CR-04 WARNING: migration 0027 lacked defensive UPDATE before partial-UNIQUE creation

All four gaps were closed in plans 42-12..42-16. Plans 42-12/13/14 commits were lost from master via a worktree-merge error and recovered via commit `ca8d256`. A subsequent FK violation in the CR-04 regression test was repaired in `9a7e20c`. All 55 phase-42 tests now pass; ruff is clean on all modified files.

---

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Operator triggers `/auth/otp/request {channel:'email'}` and observes (a) `email_sent` audit row with `audit_correlation_id`, (b) 6-digit code in sandbox inbox via `EMAIL_OTP_LOGIN` template, (c) successful `/auth/otp/verify` completion | VERIFIED | CR-01 fix confirmed: `dispatch_email.py:170-183/184-198` now passes flattened kwargs (`audit_correlation_id=str(envelope.audit_correlation_id)`, `template_id=...`, `to_email=...`, `provider_message_id=...`) matching the `**payload: Any` contract. `test_dispatch_email_audit_integration.py` exercises real `audit.emit` + queries `audit_log` table and passes. No `payload=<Model>` pattern exists in the file (`grep "payload=EmailSentPayload|payload=EmailSendFailedPayload"` returns 0). Human verification required for real inbox arrival (see human_verification). |
| 2 | User with no Telegram + verified email AND user without verified email both receive same anti-oracle 202 from `POST /auth/otp/request {channel:'email'}`; `test_otp_email_anti_oracle.py` passes with all 4 cases (incl. case B) in timing parity | VERIFIED | CR-02 fix confirmed: `request_otp_telegram` (service.py:1001-1016) now wraps `telegram_service.start_deep_link` in `try/finally` with `await _constant_time_floor(t_start)`. `grep "await _constant_time_floor(t_start)"` returns 3 occurrences (lines 900, 972, 1016). Misleading "body shape diverges" comment is gone (`grep "body shape diverges"` returns 0). Case B included in 4-case parity loop (test:123). Integration test: 55 passed. |
| 3 | `EmailDispatcher` Protocol slot double-wired in `app/main.py:create_app()` AND `app/workers/__init__.py:WorkerSettings.on_startup`; ARQ task `dispatch_email` registered with `max_tries=2, timeout=20` | VERIFIED | Unchanged from initial verification. `register_email_dispatcher(enqueue_email_dispatch)` at main.py:250 AND workers/__init__.py:248. `_max_tries=2, _expires=20` per-enqueue at dispatcher.py:199-200. Parity test in test_app_wiring.py:147-176 asserts both call sites. |
| 4 | 5 consecutive 5xx → Redis circuit opens (`sz:email:circuit:{provider}` TTL 5m); subsequent jobs short-circuit to `EmailSendResult.transient_error` without touching provider | VERIFIED | CR-03 fix confirmed: `circuit_breaker.py:89-94` uses `async with redis.pipeline(transaction=True) as pipe:` MULTI/EXEC block (ZADD + ZREMRANGEBYSCORE + EXPIRE + ZCARD in a single atomic round-trip). Docstring explicitly cites "closes CR-03". Status on breaker-short is now `'circuit_open'` (not `'rejected'`) per WR-04 fix and migration 0029 CHECK extension. |
| 5 | `infra/dns/sportzal.ru.zone` documents SPF/DKIM/DMARC (p=none); `EmailProviderSettings` validator fails fast on empty `from_domain`; boot-time `/domains` probe asserts verification | VERIFIED | Unchanged from initial verification. Zone file exists with SPF, DKIM (placeholder p= per IN-03 — operator action required), DMARC p=none + rua. Validator at config.py:32-43 raises ValueError. /domains probe at factory.py:83-99 fails fast. |
| 6 | `POST /api/v1/_internal/email/webhook` rejects unsigned bodies in O(1) via `hmac.compare_digest` BEFORE body parse; valid signed bounce/complaint appends to `email_send_log` with classification | VERIFIED | WR-06 fix confirmed: `router.py:87` now normalises presented signature via `.strip().lower()` before `hmac.compare_digest`. Orphan event name unified to `email_webhook_orphan_message_id` (WR-02: `grep "email_webhook_orphan_message_id"` returns 2 hits; `grep "email_webhook_missing_message_id|email_webhook_unknown_message_id"` returns 0). HMAC-before-parse structure unchanged. |

**Score:** 6/6 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/app/integrations/email/types.py` | `EmailEnvelope` + `EmailSendResult` dataclasses | VERIFIED | Frozen with locked fields |
| `apps/backend/app/integrations/email/models.py` | `EmailSendLog` ORM | VERIFIED | WR-01 closed: `bounce_type` CHECK constraint now enforced in migration 0029 |
| `apps/backend/alembic/versions/0026_email_send_log.py` | Migration | VERIFIED | Round-trip clean |
| `apps/backend/alembic/versions/0027_otp_codes_channel_discriminator.py` | `otp_codes.channel` + partial-UNIQUE | VERIFIED | CR-04 closed: defensive `UPDATE otp_codes SET consumed_at = now()` pass at lines 95-107 runs before partial-UNIQUE creation. Regression test `test_migration_0027_cleanup.py` passes. |
| `apps/backend/alembic/versions/0028_users_email_verified.py` | `users.email_verified` | VERIFIED | Column with FALSE default |
| `apps/backend/alembic/versions/0029_email_send_log_hygiene.py` | `bounce_type` CHECK + `circuit_open` status | VERIFIED | File exists and correct; WR-01 + WR-04 |
| `apps/backend/app/integrations/email/client.py` | `aioboto3` SESv2 adapter | VERIFIED | `EmailClient` + `SandboxEmailClient` |
| `apps/backend/app/integrations/email/factory.py` | `build_email_client` + /domains probe | VERIFIED | Async factory + domain verification |
| `apps/backend/app/integrations/email/dispatcher.py` | `enqueue_email_dispatch` (EmailDispatcher impl) | VERIFIED | Renders templates at enqueue time |
| `apps/backend/app/integrations/email/circuit_breaker.py` | Sliding-window breaker | VERIFIED | CR-03 closed: atomic MULTI/EXEC pipeline |
| `apps/backend/app/workers/tasks/dispatch_email.py` | ARQ task | VERIFIED | CR-01 closed: flattened audit.emit kwargs in both ok + failure branches; `grep "payload=EmailSentPayload\|payload=EmailSendFailedPayload"` returns 0 |
| `apps/backend/app/modules/auth/email_templates.py` | `EMAIL_OTP_LOGIN` template | VERIFIED | `SandboxedEnvironment`, locked subject |
| `apps/backend/app/api/v1/_internal/email/router.py` | Webhook HMAC handler | VERIFIED | WR-02/WR-06 closed: unified orphan event name + `.strip().lower()` normalisation |
| `apps/backend/infra/dns/sportzal.ru.zone` | DNS runbook | VERIFIED (operator action pending) | DKIM `p=` is placeholder (IN-03) — operator must substitute real key before registrar push |
| `apps/backend/tests/integration/email/test_dispatch_email_audit_integration.py` | Real audit.emit integration test | VERIFIED | Exercises real `EmailSentPayload.model_validate`; queries `audit_log` table; no `monkeypatch.setattr` of audit.emit |
| `apps/backend/tests/integration/alembic/test_migration_0027_cleanup.py` | CR-04 regression test | VERIFIED | Exists; seeds colliding rows; asserts clean migration |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `app/main.py create_app` | EmailDispatcher slot | `register_email_dispatcher(enqueue_email_dispatch)` | WIRED | main.py:250 |
| `app/workers/__init__.py on_startup` | EmailDispatcher slot | `register_email_dispatcher(enqueue_email_dispatch)` | WIRED | workers/__init__.py:248 |
| `dispatcher` | ARQ pool | `register_arq_pool(pool)` | WIRED | Both main.py and workers/__init__.py |
| `request_otp_email` | `get_email_dispatcher()` | service.py:964 — `to=email_lower` (WR-03 fixed) | WIRED | Lowercased boundary for forensic index |
| `dispatch_email` | `audit.emit` | Flattened kwargs: `audit_correlation_id=str(...)`, `template_id=...`, `to_email=...` | WIRED | CR-01 closed; lines 171-183 (ok) / 186-198 (failure) |
| `dispatch_email` | `EmailSendLog INSERT` | `session.add(log_row)` + `session.flush()` + `session.commit()` | WIRED | Flush before audit.emit surfaces FK/CHECK errors synchronously; commit at line 199 is now reachable |
| `/api/v1/_internal/email/webhook` | `EmailSendLog UPDATE` | `session.execute(update(...))` | WIRED | router.py:169+ |
| `OtpRequestBody.channel` | router dispatch | router.py:401-410 | WIRED | Discriminator on channel='email' vs default |
| `request_otp_telegram` | `_constant_time_floor` | `try/finally` wrapper at service.py:1011-1016 | WIRED | CR-02 closed |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| `dispatch_email` worker | `audit_log` row | `audit.emit` with flattened kwargs | Yes — `EmailSentPayload.model_validate` succeeds | FLOWING |
| `dispatch_email` worker | `email_send_log` row | `session.flush()` + `session.commit()` after audit.emit | Yes — commit now reachable | FLOWING |
| `dispatch_email` worker | SES send | `email_client.send_email(envelope)` | Yes — real call | FLOWING |
| `/auth/otp/request` email branch | `OtpCode` row | service.py:926 | Yes — inserted + committed | FLOWING |
| `/auth/otp/request` email branch | enqueue dispatch | `enqueue_email_dispatch` | Yes — enqueues to ARQ; downstream worker now operates cleanly | FLOWING |
| `/auth/otp/request` telegram branch | `_constant_time_floor` | `try/finally` at service.py:1011-1016 | Yes — floor applied unconditionally | FLOWING |
| Webhook handler | `email_send_log` UPDATE | router.py:169+ | Yes — real UPDATE | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| No `payload=<Model>` kwarg pattern in dispatch_email | `grep "payload=EmailSentPayload\|payload=EmailSendFailedPayload" dispatch_email.py` | 0 matches | PASS |
| Flattened audit_correlation_id present in dispatch_email (both branches) | `grep "audit_correlation_id=str(envelope.audit_correlation_id)" dispatch_email.py` | Lines 179, 193 | PASS |
| `_constant_time_floor` at 3 call sites in service.py | `grep "await _constant_time_floor(t_start)" service.py` | Lines 900, 972, 1016 | PASS |
| `to=email_lower` in dispatcher call (not `user.email`) | `grep "to=email_lower" service.py` | Line 966 | PASS |
| `grep "to=user.email" service.py` returns 0 | ditto | 0 matches | PASS |
| Atomic Redis pipeline in circuit_breaker | `grep "pipeline(transaction=True)" circuit_breaker.py` | Lines 70 (docstring), 89 (code) | PASS |
| Migration 0027 defensive UPDATE | `grep "UPDATE otp_codes" alembic/versions/0027*.py` | Line 100 | PASS |
| Migration 0029 exists | `ls alembic/versions/0029_email_send_log_hygiene.py` | EXISTS | PASS |
| Orphan webhook event name unified | `grep "email_webhook_orphan_message_id" router.py` | Lines 126, 137 | PASS |
| Old event names absent | `grep "email_webhook_missing_message_id\|email_webhook_unknown_message_id" router.py` | 0 matches | PASS |
| HMAC `.strip().lower()` normalisation | `grep ".strip().lower()" router.py` | Lines 87, 96 | PASS |
| Misleading "body shape diverges" comment absent | `grep "body shape diverges" test_otp_email_anti_oracle.py` | 0 matches | PASS |
| Case B in timing parity loop | `grep "case_b" test_otp_email_anti_oracle.py` | Lines 15, 24, 76, 95, 99, 123 | PASS |
| Integration test does not monkeypatch audit.emit | `grep -c "monkeypatch.setattr.*audit.emit" test_dispatch_email_audit_integration.py` (non-comment) | Comment only at line 116 | PASS |
| 55 phase-42 tests passing | `uv run pytest ... -q --tb=short` | 55 passed in 5.97s | PASS |
| Ruff clean on all modified files | `uv run ruff check ...` | All checks passed | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| EMAIL-01 | 42-01, 42-07 | `EmailClient` adapter + `EmailEnvelope`/`EmailSendResult` types | SATISFIED | client.py + factory.py + types.py |
| EMAIL-02 | 42-02, 42-07 | `EmailProviderSettings` + fail-fast validator + `/domains` probe | SATISFIED | config.py:32-43 + factory.py:83-99 |
| EMAIL-03 | 42-08, 42-09, 42-11, 42-12 | ARQ `dispatch_email` + real `audit.emit` row | SATISFIED | CR-01 closed; integration test confirms `email_sent` row lands in `audit_log` |
| EMAIL-04 | 42-09, 42-11 | REG-29-03 double-wire of `EmailDispatcher` slot | SATISFIED | main.py:250 + workers/__init__.py:248 + parity test |
| EMAIL-05 | 42-06 | DNS owner runbook (SPF/DKIM/DMARC p=none) | SATISFIED (operator action for DKIM p=) | Zone file + IN-03 note |
| EMAIL-06 | 42-08, 42-14 | Semaphore + Redis circuit breaker | SATISFIED | CR-03 closed: atomic MULTI/EXEC; WR-04 closed: `circuit_open` status |
| EMAIL-07 | 42-01, 42-10, 42-16 | Webhook HMAC-before-parse + `email_send_log` writes | SATISFIED | WR-02/WR-06 closed; router.py HMAC + normalisation |
| AUTH-EM-01 | 42-03, 42-15 | `otp_codes.channel` discriminator + partial-UNIQUE | SATISFIED | CR-04 closed: defensive UPDATE pass + regression test |
| AUTH-EM-02 | 42-04, 42-09, 42-13, 42-16 | `/auth/otp/request` channel discriminator + email branch + anti-oracle + 60s cooldown + `email_lower` | SATISFIED | CR-02 + WR-03 closed; broader IP/email bucket rate-limiting deferred — see deferred section |
| AUTH-EM-03 | 42-05, 42-09 | `EMAIL_OTP_LOGIN` template in `email_templates.py` | SATISFIED | `SandboxedEnvironment`, locked subject |
| AUTH-EM-04 | 42-11, 42-13 | `test_otp_email_anti_oracle.py` 4-case identical 202 + body + timing | SATISFIED | CR-02 closed: case B now in parity loop; misleading comment removed; 55 tests pass |

**Orphaned requirements:** None.

### Anti-Patterns Found

All CR-tier blockers from the initial verification have been resolved. Remaining items are operator-action notes (IN-03) and deferred items already tracked.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `apps/backend/infra/dns/sportzal.ru.zone` | 28 | DKIM `p=<2048-bit-public-key-placeholder>` | Info | IN-03 (operator action): substitute real Postbox-issued DKIM public key before registrar push |

No `TBD`, `FIXME`, `XXX`, `HACK` debt markers found in modified files.

### Human Verification Required

See `human_verification:` in frontmatter. Summary:

1. **Real Yandex sandbox send end-to-end** — requires running services + Postbox sandbox credentials. After the CR-01 fix the `dispatch_email` worker no longer crashes. This is gated on docker compose + real provider, not a code defect.
2. **Migration 0027 against real otp_codes data** — the regression test (`test_migration_0027_cleanup.py`) validates the defensive UPDATE logic in isolation; a full round-trip against production-like data requires a real Postgres instance.
3. **DNS application at Reg.ru** — DKIM p= placeholder must be substituted with the real Postbox-issued public key (IN-03).
4. **Forced 5xx breaker drill under real ARQ worker** — requires controllable provider mock in a running worker environment.

---

## Prior Verification (gaps_found)

The initial verification report (status: `gaps_found`, score: `4/6`, verified: `2026-05-19T00:00:00Z`) is preserved below for audit traceability.

---

### Prior Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Operator triggers /auth/otp/request {channel:'email'} and observes (a) email_sent audit row with audit_correlation_id, (b) 6-digit code in sandbox inbox, (c) /auth/otp/verify completion | FAILED | CR-01: `audit.emit(... payload=EmailSentPayload(...))` produced `{'payload': <Model>}` failing `EmailSentPayload.model_validate` with `extra='forbid' + 4 missing required fields`. Every `dispatch_email` worker job raised ValidationError. |
| 2 | Anti-oracle 202 for both email-channel cases; test_otp_email_anti_oracle.py passes | PARTIAL | Email-channel cases A/C/D anti-oracle confirmed. BUT: `request_otp_telegram` (case B) had no `_constant_time_floor`; test excluded case B with misleading "body shape diverges" comment. |
| 3 | EmailDispatcher slot double-wired; dispatch_email max_tries=2 timeout=20 | VERIFIED | main.py:250 + workers/__init__.py:248 |
| 4 | Redis circuit breaker opens on 5 consecutive 5xx | VERIFIED (quality concern) | Functional in serial-failure scenario; non-pipelined Redis sequence was CR-03 quality concern. |
| 5 | DNS zone + fail-fast validator + /domains probe | VERIFIED | Zone file + config.py + factory.py |
| 6 | Webhook HMAC-before-parse + email_send_log writes | VERIFIED | router.py:85-100 |

**Prior score:** 4/6 truths verified, 1 partial (SC#2), 1 failed (SC#1)

**Prior gaps** (from frontmatter, preserved verbatim):

CR-01: `dispatch_email.py` lines 160-172/175-188 used `payload=<Model>` kwarg pattern causing `ValidationError` on every production invocation. Unit tests monkey-patched `audit.emit` so the bug never surfaced in CI.

CR-02: `request_otp_telegram` had no `_constant_time_floor`. Test comment "body shape diverges" was incorrect — `router.py:411` returns identical `envelope(None)` for both channels.

CR-03: `record_failure` in `circuit_breaker.py` executed 5 sequential awaits without pipeline/MULTI — concurrent-worker burst at threshold boundary could miss-open.

CR-04: Migration 0027 created partial-UNIQUE without a prior defensive UPDATE pass to clean duplicate `consumed_at IS NULL` rows with the same `(user_id, channel)`.

---

_Verified: 2026-05-19T12:00:00Z_
_Verifier: Claude (gsd-verifier)_
_Re-verification after gap closure (CR-01..CR-04 + WR-01..04,06)_
