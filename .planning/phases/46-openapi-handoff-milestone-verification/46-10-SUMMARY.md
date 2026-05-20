---
phase: 46-openapi-handoff-milestone-verification
plan: 10
subsystem: email-encoding-verification
tags: [verification, rfc2047, email-subject, cyrillic, nbsp, encoded-word, stdlib-only, pure-test]
requires:
  - apps/backend/app/integrations/email/types.py  # EmailEnvelope (Phase 42 D-42-16)
  - apps/backend/app/modules/memberships/email_templates.py  # TEMPLATES["EMAIL_EXPIRING_7D_VARIANT_A"] (Phase 45 D-45-15)
provides:
  - apps/backend/tests/integration/test_rfc2047_cyrillic_subject_roundtrip.py
affects:
  - VER-10 race-test matrix coverage (D-46-14 #6 closed)
tech-stack:
  added: []
  patterns:
    - "stdlib-only MIME serialisation (`email.message.EmailMessage` + `email.header.decode_header` + `make_header`) mirrors the AWS SES SDK encoded-word path"
    - "byte-identical round-trip assertion (`assert decoded == original`) — proves no normalisation, mojibake, or NBSP loss between encode and decode"
    - "explicit `\\u00a0` escape for NBSP literals — keeps source ruff-clean (RUF001) while preserving the U+00A0 contract under test"
    - "RFC 5322 §2.2.3 folded-header rejoin in test helper — handles multi-line `=?utf-8?b?...?=` continuations produced by the policy header encoder"
    - "no DB / no Redis / no network / no fixtures — pure encoding contract test, runs in <100ms"
key-files:
  created:
    - apps/backend/tests/integration/test_rfc2047_cyrillic_subject_roundtrip.py
  modified: []
decisions:
  - "Use stdlib `EmailMessage.as_string()` to emit the wire form (SES does this server-side when given `{Data, Charset:UTF-8}`) — re-walking the same encoder catches regressions without a live SES call (VER-12 covers the live deliverability probe)"
  - "Access the locked template via `TEMPLATES[\"EMAIL_EXPIRING_7D_VARIANT_A\"].subject` rather than a hypothetical `EMAIL_EXPIRING_7D_VARIANT_A` module export — matches the actual D-41-12 registry shape and the dispatcher's lookup pattern"
  - "Two tests, not one: (1) round-trip the locked Phase 45 Cyrillic subject; (2) round-trip a synthetic NBSP-bearing variant. The locked subject has no NBSP, so without the synthetic case the NBSP discipline (D-45-17 / D-42-23) would be untested at the subject layer"
  - "Define NBSP via `\"\\u00a0\"` escape — avoids ambiguous-char RUF001 warnings inside the test source while still asserting against literal U+00A0 in the round-tripped value"
  - "Parse the Subject from `msg.as_string()` output (handling RFC 5322 folded continuation lines) rather than reading `msg[\"Subject\"]` directly — the latter returns the policy's stored string form, not the wire-form encoded-word that gateways actually see"
metrics:
  duration: "~10 minutes"
  completed: "2026-05-20T16:05:00Z"
  tasks_completed: 1
  files_created: 1
  files_modified: 0
  loc_added: 166
  test_count: 2
  test_runtime_ms: 20
---

# Phase 46 Plan 10: RFC 2047 Cyrillic Subject Round-Trip Test — Summary

Closes VER-10 race-test #6 (D-46-14): a pure stdlib-only encoding round-trip test that proves the Phase 45 locked Cyrillic subject (`"Ваш абонемент скоро истекает"` from `EMAIL_EXPIRING_7D_VARIANT_A`) survives the RFC 2047 `=?UTF-8?B?...?=` encoded-word encode→decode cycle byte-identically, plus a synthetic NBSP variant that proves U+00A0 preservation under the same path.

## What Shipped

1. **`apps/backend/tests/integration/test_rfc2047_cyrillic_subject_roundtrip.py`** (166 LOC, 2 tests)
   - `_serialise_subject_via_stdlib(subject)` — helper that builds an `EmailMessage`, assigns the subject, runs `msg.as_string()` (the same RFC 2047 encoded-word path AWS SES SDK uses server-side for `{"Data": s, "Charset": "UTF-8"}`), and extracts the Subject header — including rejoining RFC 5322 §2.2.3 folded continuations.
   - `test_rfc2047_cyrillic_subject_roundtrip` — reads `TEMPLATES["EMAIL_EXPIRING_7D_VARIANT_A"].subject`, constructs an `EmailEnvelope`, serialises, decodes via `decode_header` + `make_header`, asserts wire form is RFC 2047 encoded-word (`=?...?=`), declares UTF-8 charset, and decodes byte-identically.
   - `test_rfc2047_nbsp_in_subject_roundtrip` — synthetic Cyrillic+NBSP subject (using ` ` escapes between tokens), same round-trip path, asserts NBSP survives (Outlook NBSP discipline per D-45-17 / D-42-23).

## VER-10 Closure Note

VER-10 race-test #6 (D-46-14) called for proof that the email subject pipeline preserves Cyrillic + NBSP through the standard-library MIME encoder. This is the single-flow encoding contract — VER-12 separately runs the live AWS SES deliverability probe with a real recipient mailbox. Together they bracket the encoding boundary: this test catches stdlib / template-module regressions; VER-12 catches transport-layer / provider-side regressions.

## Verification

- `uv run pytest apps/backend/tests/integration/test_rfc2047_cyrillic_subject_roundtrip.py -v` → `2 passed in 0.02s` ✓
- `uv run ruff check tests/integration/test_rfc2047_cyrillic_subject_roundtrip.py` → `All checks passed!` ✓
- `uv run mypy tests/integration/test_rfc2047_cyrillic_subject_roundtrip.py` → `Success: no issues found in 1 source file` ✓
- Acceptance grep gates (from PLAN.md):
  - `decode_header|make_header|EmailMessage` → 9 hits (≥1 required) ✓
  - `EMAIL_EXPIRING_7D_VARIANT_A` → 2 hits (≥1 required) ✓
  - `NBSP|u00A0|u00a0|0xA0` → 18 hits (≥1 required) ✓
  - `byte-identical|assert decoded == rendered_subject` → 4 hits (≥1 required) ✓

## Deviations from Plan

### Plan-anticipated adaptations

1. **EmailEnvelope has no `encoded_subject()` helper** — the plan anticipated this (step 4 of the action block). The dispatcher passes `envelope.subject` verbatim into the AWS SES SDK as `{"Data": ..., "Charset": "UTF-8"}` (`app/integrations/email/client.py:93`) and SES handles RFC 2047 encoding server-side. The test re-walks the equivalent stdlib path (`EmailMessage` + `as_string()`) per the plan's fallback instruction.

2. **Template export shape** — plan step 5 anticipated both `EMAIL_EXPIRING_7D_VARIANT_A` as a top-level constant AND as a `TEMPLATES["EMAIL_EXPIRING_7D_VARIANT_A"]` dict lookup. The Phase 45 D-45-15 module uses the dict form; test imports `TEMPLATES` and indexes by literal name.

3. **NBSP coverage via second test** — plan step 6 noted NBSP coverage was a bonus. The locked Phase 45 subject does NOT contain NBSP (only the body does, per D-45-17). To still close the subject-layer NBSP discipline gap, added a second test (`test_rfc2047_nbsp_in_subject_roundtrip`) with a synthetic Cyrillic+NBSP subject. Both tests share the same `_serialise_subject_via_stdlib` helper, so coverage is unified.

### Auto-fixed during execution

1. **[Rule 1 - Bug] Test asserted on wrong serialisation output** — initial draft called `str(msg["Subject"])` which returns the policy's stored string form (the original Cyrillic), not the wire-form encoded-word. The encoded-word assertion `assert "=?" in serialised` failed on first run. Fixed by switching to `msg.as_string()` and parsing the Subject line out of the serialised output (handling RFC 5322 folded continuations). The byte-identical round-trip assertion still passed on the broken path because the original string trivially round-tripped through itself — but that wouldn't catch a real RFC 2047 regression. The fix is what makes the test actually load-bearing.

2. **[Rule 1 - Lint] Ambiguous NBSP/Cyrillic chars in source** — ruff RUF001/RUF002/RUF003 flagged literal U+00A0 NBSP in string and docstring. Fixed by:
   - Defining NBSP as `" "` named constant (escape form, no ambiguous-char warning).
   - Rewriting the docstring to drop the ambiguous Cyrillic `г` (replaced with "Russian year abbreviation").
   - Removing inline NBSP literals in favor of the `NBSP` constant via f-string interpolation.
   Source is now ruff-clean with zero noqa directives needed.

## Test Strategy

This is a single-flow encoding contract test (NOT a race test in the gather sense — no concurrent dispatchers, no DB locking, no FOR UPDATE). It targets the deterministic stdlib encoding path that sits between the application layer (Phase 45 template module) and the network transport (Phase 42 AWS SES client).

The test would fail if:
- A future Python release changed the `email.policy` default encoder behaviour (defence-in-depth).
- Someone edited the Phase 45 locked subject to contain a character outside the BMP (surrogate-pair encoded-word edge case).
- A middleware layer was added that normalised U+00A0 → U+0020 in the subject (Outlook bug regression).
- The dispatcher started doing its own subject encoding instead of passing through to SES (architectural regression — would invalidate the SES SDK's encoded-word contract).

## Known Stubs

None.

## Threat Flags

None — pure encoding test, no new network surface or trust boundary.

## Self-Check: PASSED

- `apps/backend/tests/integration/test_rfc2047_cyrillic_subject_roundtrip.py` — FOUND (166 lines).
- `pytest` → 2 passed.
- ruff/mypy → clean.
- All 4 acceptance grep gates → green.
