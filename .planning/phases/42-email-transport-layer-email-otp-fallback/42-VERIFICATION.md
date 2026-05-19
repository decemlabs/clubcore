---
phase: 42-email-transport-layer-email-otp-fallback
verified: 2026-05-19T00:00:00Z
status: gaps_found
score: 4/6 success criteria verified
overrides_applied: 0
gaps:
  - truth: "SC#1: Operator triggers /auth/otp/request {channel:'email'} and observes (a) an email_sent audit row with audit_correlation_id, (b) the 6-digit code arriving in the sandbox inbox, (c) successful /auth/otp/verify completion"
    status: failed
    reason: "dispatch_email.py:160-172/175-188 calls audit.emit(... payload=EmailSentPayload(...)) as a single kwarg. audit.emit's signature is **payload: Any so collected payload becomes {'payload': <Model>}. EmailSentPayload.model_validate({'payload': <Model>}) raises ValidationError (extra='forbid' + 4 missing required fields). Every dispatch_email job crashes at runtime → no email_sent audit row is ever produced AND the EmailSendLog INSERT rolls back because the audit emit raises before session.commit(). Confirmed empirically by reproducing the validation error against the actual EmailSentPayload schema."
    artifacts:
      - path: apps/backend/app/workers/tasks/dispatch_email.py
        issue: "Lines 160-172 and 175-188 use payload=<Model> kwarg pattern; must flatten kwargs to match the **payload contract used at app/modules/memberships/service.py and app/api/v1/_internal/email/router.py:181-197"
      - path: apps/backend/tests/unit/integrations/email/test_dispatch_email_task.py
        issue: "Lines 167-170 monkey-patch audit.emit with fake_emit that never invokes the real Pydantic validator; the test asserts kwargs['payload'] is the model instance — wrong layer. Tests pass while production crashes."
    missing:
      - "Flatten audit.emit kwargs in both ok and failure branches of dispatch_email.py (audit_correlation_id=str(envelope.audit_correlation_id), template_id=..., to_email=..., provider_message_id=... / reason=..., provider_error_code=...)"
      - "Add integration-tier test that exercises real audit.emit + queries audit_log for the email_sent row"
      - "Fix unit tests to assert flattened kwargs (kwargs['template_id'] etc.) not kwargs['payload'].template_id"
  - truth: "SC#2: A user with no Telegram + a verified email AND a user without verified email both receive the same anti-oracle 202 response shape from POST /auth/otp/request {channel: 'email'}; test_otp_email_anti_oracle.py (AUTH-EM-04) passes"
    status: partial
    reason: "Email-channel branch (cases A/C/D) is anti-oracle protected — _constant_time_floor applied on both success + silent-drop paths in request_otp_email. BUT request_otp_telegram (the channel=default backwards-compat facade reached by case B and any /otp/request call without channel='email') has NO constant-time floor — telegram_service.start_deep_link issues unconditional DB write + audit emit + commit, producing a distinct wall-clock distribution. The integration test explicitly excludes case B from timing-parity assertion with a misleading comment claiming body shape diverges (router.py:411 returns the same envelope(None) for both channels — body IS identical). The phase goal contract reads strictly on email-channel pairs, so SC#2 as written passes; but the broader D-42-22 'anti-oracle uniformity' invariant cited in the CONTEXT decision is violated for cross-channel callers."
    artifacts:
      - path: apps/backend/app/modules/auth/service.py
        issue: "Lines 972-1002 — request_otp_telegram has no _constant_time_floor; start_deep_link writes a row + audit + commits unconditionally, leaking timing"
      - path: apps/backend/tests/integration/auth/test_otp_email_anti_oracle.py
        issue: "Lines 147-154 — case B excluded from timing-parity with a misleading 'body shape diverges' comment; bodies are byte-identical per router.py:411"
    missing:
      - "Apply _constant_time_floor to request_otp_telegram in a try/finally wrapper around telegram_service.start_deep_link"
      - "Extend test_otp_email_anti_oracle.py to include case B in the timing-parity assertion"
      - "Fix misleading comment about diverging body shape"
deferred:
  - truth: "AUTH-EM-02 broader IP/email rate-limit buckets (5/15min IP + 1/min email)"
    addressed_in: "Follow-up plan in Phase 42 (per 42-09-SUMMARY) or Phase 44"
    evidence: "42-09-SUMMARY.md:340 explicitly records this as a 'follow-up if not already wired'. The AUTH-EM-02 REQUIREMENTS.md text does NOT specify the IP/email bucket sizes — those clauses came from D-42-22's reference. The in-phase mitigations (60s row-level cooldown, anti-oracle silent-drop, constant-time floor) are wired and adequate for the SC#1 demo path."
human_verification:
  - test: "Run alembic upgrade head against a copy of any pre-v1.6 database that has executed multiple /auth/telegram/start calls without commit_otp consumption"
    expected: "Migration 0027 partial-UNIQUE creation should succeed without 'duplicate key value violates unique constraint' on uq_otp_codes_user_channel_active"
    why_human: "CR-04 risk depends on real production data state. telegram_service.start_deep_link inserts rows with user_id=NULL (NULLs distinct under UNIQUE so no collision possible for /telegram/start path), but any future writer that issues user_id IS NOT NULL + consumed_at IS NULL pairs across the channel will collide. For a fresh pet-project deployment this is benign; once data exists this is destructive."
  - test: "docker compose up → real Yandex Cloud Postbox sandbox send → confirm 6-digit code arrives in sandbox inbox"
    expected: "Sandbox inbox receives the locked EMAIL_OTP_LOGIN template with a 6-digit code"
    why_human: "Requires running services; cannot be verified statically. NOTE: gated by CR-01 fix — without the audit.emit fix, the dispatch_email worker crashes BEFORE the inbox arrival is forensically recorded (the SES API call succeeds at line 133 then audit emit raises at lines 160-172, rolling back the EmailSendLog INSERT)."
  - test: "Apply infra/dns/sportzal.ru.zone at Reg.ru and verify with mail-tester.com or dig"
    expected: "SPF passes, DKIM signs with the operator-issued p= value, DMARC reports route to dmarc-reports@sportzal.ru"
    why_human: "Zone file ships with placeholder DKIM p=<2048-bit-public-key-placeholder> — operator must substitute the real Postbox-issued public key. Static verification only confirms the file exists and has correct record syntax."
  - test: "Force 5 consecutive 5xx responses from provider → observe circuit opens within 60s window → subsequent jobs return EmailSendResult(error='circuit_open') without touching SES"
    expected: "Circuit-open marker set at sz:email:circuit:yandex_postbox with 5min TTL"
    why_human: "Requires a 5xx-injection harness or a controllable mock SES server; the unit test exercises the breaker primitive in isolation but not the dispatch_email integration path."
---

# Phase 42: Email Transport Layer + Email OTP Fallback Verification Report

**Phase Goal:** Sportzal can send a transactional email asynchronously through a verified РФ-domiciled provider end-to-end, with circuit-breaker protection, bounce-webhook intake, and an immediate consumer (email-channel OTP fallback for `/auth/otp/request`) proving the slot wiring works.

**Verified:** 2026-05-19
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Operator can run docker compose up, trigger /auth/otp/request {channel:'email'}, observe (a) email_sent audit row with audit_correlation_id, (b) 6-digit code in sandbox inbox, (c) /auth/otp/verify completion | ✗ FAILED | CR-01 confirmed empirically: `audit.emit(... payload=EmailSentPayload(...))` produces `{'payload': <Model>}` which fails `EmailSentPayload.model_validate` with `extra='forbid' + 4 missing required fields`. Every `dispatch_email` worker job raises ValidationError → ARQ retries once → fails permanently → no audit row, EmailSendLog INSERT rolls back. The SES call at dispatch_email.py:133 DOES execute (provider receives the request) but the bookkeeping never lands. |
| 2 | Both verified-email-no-tg + unverified-email users receive same anti-oracle 202 from /auth/otp/request {channel:'email'}; test_otp_email_anti_oracle.py passes | ⚠️ PARTIAL | Email-channel anti-oracle (cases A/C/D) confirmed at service.py:900,969 — both branches converge on `_constant_time_floor(t_start)`. AUTH-EM-04 test exercises the contract and passes as written. BUT: cross-channel (case B, default-telegram path) has no floor — `request_otp_telegram` writes unconditionally; the test's "body shape diverges" comment masking case B is incorrect (router.py:411 returns identical `envelope(None)`). SC#2 as literally written for `channel:'email'` is met; the broader D-42-22 invariant is violated. |
| 3 | EmailDispatcher Protocol slot double-wired in app/main.py:create_app() AND app/workers/__init__.py:WorkerSettings.on_startup; ARQ task dispatch_email registered with max_tries=2, timeout=20 | ✓ VERIFIED | `register_email_dispatcher(enqueue_email_dispatch)` called at main.py:250 AND workers/__init__.py:248 with the IDENTICAL symbol reference (both files import from `app.integrations.email.dispatcher`). ARQ `_max_tries=2, _expires=20` set per-enqueue at dispatcher.py:199-200. `dispatch_email` listed in WorkerSettings.functions at workers/__init__.py:124. Parity test at tests/integration/test_app_wiring.py:147-176 asserts both call sites. |
| 4 | 5 consecutive 5xx → Redis circuit opens (sz:email:circuit:{provider} TTL 5m); subsequent jobs short-circuit to EmailSendResult.transient_error without touching provider | ✓ VERIFIED (with quality concern) | `record_failure` at circuit_breaker.py:59-98 implements 5-failure / 60s window threshold + 5min TTL open marker. `is_circuit_open` is O(1) EXISTS. dispatch_email.py:120-126 short-circuits to `EmailSendResult(ok=False, classification='transient_error', error='circuit_open')` BEFORE calling email_client.send_email. **Quality concern (CR-03):** record_failure executes 5 sequential awaits without pipeline/MULTI — under concurrent worker bursts at threshold boundary the ZCARD may read a count one shy of threshold and fail to open. Unit test uses single-threaded fakeredis so the race never surfaces. Functional behavior in serial-failure scenario is correct. |
| 5 | infra/dns/sportzal.ru.zone documents SPF/DKIM/DMARC (p=none); EmailProviderSettings validator fails fast on empty from_domain; boot-time /domains probe asserts verification | ✓ VERIFIED | Zone file exists with SPF (yandexcloud.net include), DKIM (selector sport1._domainkey.mail.sportzal.ru) — **NOTE:** DKIM `p=<2048-bit-public-key-placeholder>` is a placeholder requiring operator substitution before registrar push (IN-03). DMARC p=none + rua=mailto:dmarc-reports@sportzal.ru. EmailProviderSettings validator at config.py:32-43 raises ValueError on empty from_domain / webhook_secret / aws_credentials in non-sandbox mode. /domains probe at factory.py:83-99 fails fast if VerificationStatus != 'Success'. |
| 6 | POST /api/v1/_internal/email/webhook rejects unsigned bodies in O(1) via hmac.compare_digest BEFORE body parse; valid signed bounce/complaint appends to email_send_log | ✓ VERIFIED | router.py:85-100 reads raw_body, computes HMAC-SHA256 of raw bytes, compares via `hmac.compare_digest` BEFORE any json.loads. Mismatch raises 401 without parse. Valid signature path UPDATEs EmailSendLog status to bounced/complained/delivered and emits `email_send_failed` audit with LOCKED Literal `reason='bounce'|'complaint'`. |

**Score:** 4/6 truths verified, 1 partial (SC#2), 1 failed (SC#1)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| apps/backend/app/integrations/email/types.py | EmailEnvelope + EmailSendResult dataclasses | ✓ VERIFIED | EmailEnvelope frozen with 6 locked fields per D-42-16 |
| apps/backend/app/integrations/email/models.py | EmailSendLog ORM | ✓ VERIFIED | EmailSendLog with CHECK on status (WR-01 noted: no CHECK on bounce_type) |
| apps/backend/alembic/versions/0026_email_send_log.py | Migration | ✓ VERIFIED | Round-trip clean (per 42-01-SUMMARY claims; not re-run inline) |
| apps/backend/alembic/versions/0027_otp_codes_channel_discriminator.py | otp_codes.channel | ⚠️ ORPHANED-RISK | Migration body lacks defensive UPDATE pass for stale `consumed_at IS NULL` rows (CR-04). For fresh pet-project deployment safe; for any existing schema with prior /telegram/start placeholder data WITH non-null user_id the partial-UNIQUE creation will fail. Per code inspection, telegram_service.start_deep_link writes user_id=NULL so the immediate risk is bounded. |
| apps/backend/alembic/versions/0028_users_email_verified.py | users.email_verified | ✓ VERIFIED | Column added with FALSE default + bootstrap-runbook comment |
| apps/backend/app/integrations/email/client.py | aioboto3 SESv2 adapter | ✓ VERIFIED | EmailClient + SandboxEmailClient implementations |
| apps/backend/app/integrations/email/factory.py | build_email_client + /domains probe | ✓ VERIFIED | Async factory with boot-time domain verification |
| apps/backend/app/integrations/email/dispatcher.py | enqueue_email_dispatch (EmailDispatcher slot impl) | ✓ VERIFIED | Renders subject/html/text at enqueue time per D-42-07; passes envelope to ARQ |
| apps/backend/app/integrations/email/circuit_breaker.py | sliding-window breaker | ✓ VERIFIED (CR-03 quality concern) | Non-pipelined Redis sequence (see SC#4 details) |
| apps/backend/app/workers/tasks/dispatch_email.py | ARQ task | ✗ STUB-LIKE | File exists, structurally correct, but audit emit shape is broken — every production invocation crashes (CR-01). Functionally non-operational on the success path. |
| apps/backend/app/modules/auth/email_templates.py | EMAIL_OTP_LOGIN template | ✓ VERIFIED | SandboxedEnvironment, autoescape correct, locked subject "Код входа в Sportzal" |
| apps/backend/app/api/v1/_internal/email/router.py | webhook | ✓ VERIFIED | HMAC-before-parse correctly implemented |
| apps/backend/infra/dns/sportzal.ru.zone | DNS runbook | ⚠️ PLACEHOLDER | Real file exists; DKIM `p=` is placeholder per IN-03 (operator action required) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| app/main.py create_app | EmailDispatcher slot | register_email_dispatcher(enqueue_email_dispatch) | ✓ WIRED | main.py:250 |
| app/workers/__init__.py on_startup | EmailDispatcher slot | register_email_dispatcher(enqueue_email_dispatch) | ✓ WIRED | workers/__init__.py:248 |
| dispatcher | ARQ pool | register_arq_pool(pool) | ✓ WIRED | main.py:101 (web) + workers/__init__.py:255 (worker, reuses ctx['redis']) — WR-05 noted re version fragility |
| request_otp_email | get_email_dispatcher() | service.py:963 | ✓ WIRED | Calls the slot with rendered EmailEnvelope kwargs |
| dispatch_email | audit.emit | payload=Model(...) | ✗ NOT_WIRED | CR-01: shape mismatch causes ValidationError; effectively unwired at runtime |
| dispatch_email | EmailSendLog INSERT | session.add(log_row) + commit | ✗ DOWNSTREAM_BLOCKED | INSERT rolls back when audit.emit raises (single session, commit not reached) |
| /api/v1/_internal/email/webhook | EmailSendLog UPDATE | session.execute(update(...)) | ✓ WIRED | router.py:169+ |
| OtpRequestBody.channel | router dispatch | router.py:401-410 | ✓ WIRED | Discriminator on channel='email' vs 'telegram' |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| dispatch_email worker | audit_log row | audit.emit | ✗ Raises before write | ✗ HOLLOW — wired but data crashes on validation |
| dispatch_email worker | email_send_log row | session.add + commit | ✗ Rollback on audit.emit raise | ✗ HOLLOW — INSERT never commits |
| dispatch_email worker | SES send | email_client.send_email(envelope) | ✓ Real call (succeeds) | ✓ FLOWING (the only data path that lands) |
| /auth/otp/request email branch | OtpCode row | service.py:926 | ✓ Inserted + committed | ✓ FLOWING |
| /auth/otp/request email branch | enqueue dispatch | enqueue_email_dispatch | ✓ Enqueues to ARQ | ✓ FLOWING (but downstream worker crashes) |
| webhook handler | email_send_log UPDATE | router.py:169+ | ✓ Real UPDATE | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| EmailSentPayload accepts payload={'payload':<Model>} shape | `python3 -c "EmailSentPayload.model_validate({'payload': EmailSentPayload(...)})"` | ValidationError: 5 validation errors — 4 missing required + extra forbidden | ✗ FAIL (confirms CR-01) |
| email_templates registers EMAIL_OTP_LOGIN | grep TEMPLATES email_templates.py | Present with locked subject | ✓ PASS |
| EmailProviderSettings validator rejects empty from_domain | grep config.py | Validator raises ValueError | ✓ PASS |
| Zone file has SPF/DKIM/DMARC | grep -E "v=spf1\|v=DKIM1\|v=DMARC1" zone | All three present | ✓ PASS |
| ARQ dispatch_email registered in WorkerSettings | grep dispatch_email workers/__init__.py | Listed at line 124 | ✓ PASS |
| Migration round-trip | not executed in this verification pass | — | ? SKIP (claimed clean in 42-01/03/04 SUMMARYs) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| EMAIL-01 | 42-01, 42-07 | EmailClient adapter + EmailEnvelope/EmailSendResult types | ✓ SATISFIED | client.py + factory.py + types.py present |
| EMAIL-02 | 42-02, 42-07 | EmailProviderSettings + fail-fast validator + /domains probe | ✓ SATISFIED | config.py:32-43 + factory.py:83-99 |
| EMAIL-03 | 42-08, 42-09, 42-11 | ARQ dispatch_email + audit.emit | ✗ BLOCKED | Task exists + registered, but audit emit shape causes runtime ValidationError on every invocation (CR-01) |
| EMAIL-04 | 42-09, 42-11 | REG-29-03 double-wire of EmailDispatcher slot | ✓ SATISFIED | main.py:250 + workers/__init__.py:248 + parity test |
| EMAIL-05 | 42-06 | DNS owner runbook (SPF/DKIM/DMARC) | ✓ SATISFIED (with operator action) | zone file with placeholder DKIM p= per D-42-12 |
| EMAIL-06 | 42-08 | Semaphore + Redis circuit breaker | ✓ SATISFIED (with CR-03 quality concern on atomicity) | circuit_breaker.py + dispatch_email.py:66 Semaphore(5) |
| EMAIL-07 | 42-01, 42-10 | Webhook HMAC-before-parse + email_send_log writes | ✓ SATISFIED | router.py:85-100 + 0026 migration |
| AUTH-EM-01 | 42-03 | otp_codes.channel discriminator + partial-UNIQUE | ✓ SATISFIED (deploy-data-risk CR-04 for non-fresh schemas) | 0027 migration + model column |
| AUTH-EM-02 | 42-04, 42-09 | /auth/otp/request channel discriminator + email branch + anti-oracle + 10min TTL + 60s cooldown | ✓ SATISFIED (with broader IP/email rate-limit buckets deferred — see deferred section) | schemas.py:94 + service.py:832 + router.py:382 |
| AUTH-EM-03 | 42-05, 42-09 | EMAIL_OTP_LOGIN template in app/modules/auth/email_templates.py | ✓ SATISFIED | email_templates.py with Jinja2 SandboxedEnvironment |
| AUTH-EM-04 | 42-11 | test_otp_email_anti_oracle.py integration test | ✓ SATISFIED (with case-B exclusion concern noted in SC#2) | Test passes the contract as written; cross-channel timing leak not caught |

**Orphaned requirements:** None — all 11 phase-42 IDs are claimed by at least one plan.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| apps/backend/app/workers/tasks/dispatch_email.py | 160-172, 175-188 | `audit.emit(... payload=<Model>)` — wrong kwarg shape | 🛑 Blocker | CR-01: every production send crashes; no `email_sent` row ever lands |
| apps/backend/app/modules/auth/service.py | 972-1002 | request_otp_telegram missing _constant_time_floor | 🛑 Blocker (per SC#2 broader read) | CR-02: cross-channel timing oracle on /auth/otp/request |
| apps/backend/app/integrations/email/circuit_breaker.py | 59-98 | record_failure non-pipelined sequential awaits | ⚠️ Warning | CR-03: concurrency-race threshold edge can miss-open; rare but pathological |
| apps/backend/alembic/versions/0027_otp_codes_channel_discriminator.py | 61-90 | partial-UNIQUE creation with no data-cleanup pass | ⚠️ Warning | CR-04: safe for fresh deploys + the actual telegram_service.start_deep_link writes user_id=NULL (NULLs distinct); destructive risk bounded |
| apps/backend/infra/dns/sportzal.ru.zone | 28 | DKIM `p=<2048-bit-public-key-placeholder>` | ℹ️ Info | IN-03: operator-action required before registrar push |
| apps/backend/app/integrations/email/models.py | 81 | bounce_type free-form Text (no CHECK) | ℹ️ Info | WR-01 |
| apps/backend/app/api/v1/_internal/email/router.py | 120-136 | 202 on missing/unknown messageId | ℹ️ Info | WR-02: silently swallows non-trivial routing bugs |
| apps/backend/app/modules/auth/service.py | 869, 961-966 | user.email (mixed-case) passed instead of email_lower | ℹ️ Info | WR-03: forensic index inconsistency |
| apps/backend/app/workers/tasks/dispatch_email.py | 119-153 | circuit-open writes EmailSendLog status='rejected' | ℹ️ Info | WR-04: status semantics conflate breaker shorts with provider rejections |
| apps/backend/app/api/v1/_internal/email/router.py | 87-93 | HMAC compare without .strip().lower() normalisation | ℹ️ Info | WR-06: proxy whitespace + hex-case can produce false 401s |

No `TBD`, `FIXME`, `XXX`, `HACK` debt markers found in modified files (skill rule "Debt marker gate" — clean).

### Human Verification Required

See `human_verification:` section in frontmatter. Summary:

1. **Real Yandex sandbox send end-to-end** — gated by CR-01 fix; even after fix requires running services + sandbox credentials.
2. **Migration 0027 against prod-like data** — verify no partial-UNIQUE collision once real otp_codes data exists.
3. **DNS application at Reg.ru** — substitute real DKIM public key for placeholder.
4. **Forced 5xx breaker drill** — requires controllable provider mock.

### Gaps Summary

**Phase 42 ships a structurally complete email transport layer with the right shape — but two of the six roadmap success criteria are not actually achieved in the codebase, and one of them (SC#1) is fully blocked by a single 4-line defect.**

**The headline defect is CR-01.** `app/workers/tasks/dispatch_email.py` invokes `audit.emit(..., payload=EmailSentPayload(...))`, passing the Pydantic model as a single kwarg named `payload`. The `audit.emit` signature is `**payload: Any`, so the collected kwarg dict becomes `{"payload": <Model>}`. The downstream `EmailSentPayload.model_validate({"payload": ...})` raises `ValidationError` (extra=`forbid` + four missing required fields). The failure is empirically reproducible (see Behavioral Spot-Checks). Every production `dispatch_email` invocation crashes; ARQ retries once with `_max_tries=2` and marks the job failed. No `email_sent` audit row is ever persisted; the `EmailSendLog` INSERT rolls back when the audit raises (the `session.commit()` at line 189 is never reached). The SES API call at line 133 DOES succeed — so emails actually arrive at provider — but the bookkeeping never lands, breaking SC#1 (a) outright. The reason this slipped past every unit test in `test_dispatch_email_task.py`: every test monkey-patches `app.workers.tasks.dispatch_email.audit.emit` with a `fake_emit` that records kwargs and never runs the real Pydantic validator. The test correctly asserts on `kwargs["payload"]` — which is the wrong layer.

**The second defect is CR-02.** Strict reading of SC#2 (the anti-oracle pair test on `channel:'email'` users) passes — the test is green, the `_constant_time_floor` is correctly applied in `request_otp_email`. But the unified `/auth/otp/request` endpoint also dispatches to `request_otp_telegram` for any caller with `channel='telegram'` (the default) or no channel set, and the telegram facade has no latency floor. `telegram_service.start_deep_link` writes a row + audit emit + commits unconditionally, producing a distinct wall-clock distribution that an attacker probing the unified endpoint can use as a side-channel signal. The integration test (`tests/integration/auth/test_otp_email_anti_oracle.py:147-154`) explicitly excludes case B from timing-parity assertions with a misleading comment claiming bodies diverge — they do not (`router.py:411` returns identical `envelope(None)`). The broader D-42-22 "anti-oracle uniformity across every sub-case of /auth/otp/request" invariant is violated.

**The remaining issues are quality concerns:** CR-03 (non-pipelined circuit breaker), CR-04 (migration 0027 no data-cleanup — bounded by NULL-distinct UNIQUE semantics in pet-project context), and several WR-tier warnings (bounce_type free-form Text, webhook 202 on unknown messageId, mixed-case email at dispatcher boundary).

**Deferred items:** AUTH-EM-02's broader IP/email rate-limit buckets (5/15min IP + 1/min email) are recorded in 42-09-SUMMARY:340 as "follow-up if not already wired". REQUIREMENTS.md AUTH-EM-02 text mentions "60-second resend cooldown" + "max 5 attempts per code" + single-active discipline — all of which ARE wired. The 5/15min IP + 1/min email buckets come from D-42-22 commentary not REQUIREMENTS.md text. This is acceptable scope for SC#1 demo-path completeness.

**Recommendation:** Block phase close. CR-01 is a 4-line fix (flatten the kwargs to mirror the webhook router's pattern at router.py:181-197). CR-02 is a 5-line fix (apply `_constant_time_floor` in a `try/finally` around `start_deep_link` in `request_otp_telegram`). Both need test updates: the unit test fake_emit pattern is the structural reason CR-01 escaped — at least one integration-tier test that exercises the real `audit.emit` validator + queries `audit_log` for the row is mandatory before re-verify.

---

_Verified: 2026-05-19_
_Verifier: Claude (gsd-verifier)_
