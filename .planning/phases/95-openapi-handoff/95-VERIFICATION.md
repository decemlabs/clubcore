---
phase: 95-openapi-handoff
verified: 2026-06-08
status: passed
score: 3/3
requirement_ids: [HND-01]
---

# Phase 95: OpenAPI Handoff + Milestone Verification — Verification Report

**Phase Goal:** All v2.5 endpoints frozen in byte-stable `openapi.json` + `schema.d.ts`; WS endpoint manually documented; milestone gate green; staff contract byte-for-byte vs the latest frozen baseline.

**Verified:** 2026-06-08 (from the executed full milestone gate + artifact inspection)

## Goal Achievement — 3/3 success criteria met

| # | Criterion | Verdict | Evidence |
|---|-----------|---------|----------|
| 1 | `openapi.json` byte-stable with v2.5 Messaging REST paths under the `Messaging` tag + WS manually documented in `_customize_openapi()` + Redocly clean | PASS | `Messaging` tag added to `OPENAPI_TAGS` (after `Client-Portal`, D-64-TAG-ORDER); 5 messaging REST routes retagged from `Client-Portal` (3 sites → grep 0); WS `/api/v1/client/ws/messages` hand-injected as a `get`/101 op, `cookieAuth`-only, `Messaging` tag (main.py `_customize_openapi`); regenerate→`git diff --exit-code` empty (byte-stable); Redocly lint exit 0 (one expected advisory: WS 101 vs 2xx). |
| 2 | `schema.d.ts` byte-stable + `_v25Checks` AssertNonNever[7] + `toHaveLength(7)` + staff-path drift gate empty | PASS | `pnpm -F @clubcore/api-client codegen` added 6 messaging paths + schemas; `_v25Checks` 7-tuple (GET/PATCH/POST messages, POST body, POST attachments, GET serve, GET ws) added inside the `schema.contract` describe with `toHaveLength(7)`; consecutive codegen runs identical (byte-stable); staff (non-`/api/v1/client`) paths diff-empty vs the Phase 89 frozen baseline. |
| 3 | Full milestone gate green | PASS | `uv run mypy --strict app` (267 files, 0 issues); `uv run lint-imports` (3 contracts, 0 broken; `app.modules.messaging` in modules-independent); CISO-01 byte-parity PASS; `pnpm -F @clubcore/api-client test` (20 tests); Redocly lint 0 errors; `git diff --exit-code` on openapi.json+schema.d.ts empty. |

## Requirement Traceability
- **HND-01** — Complete. All 21 v2.5 requirement IDs (MSG/RT/RCPT/ATT/BRDG/PWA/HND) now `[x]` in REQUIREMENTS.md.

## Deviations
- **Staff-drift baseline:** the plan referenced the `contract-freeze-v1.11.0` tag (Phase 64), but that tag predates phases 86–89 which legitimately added GYM/notifications/trainer staff paths. The drift gate was run against the most-recent frozen baseline (Phase 89, openapi.json) instead — correctly proving v2.5 adds ONLY client messaging surface with zero staff drift. Spirit of the requirement fully satisfied.
- **Rule-1 fixes (Phase 93 latent failures):** the full milestone gate surfaced 6 pre-existing test fixtures broken by Phase 93's HandlerContext `messaging_service` field + the new `forward_to_staff` ARQ registration + 4 new LOCKED_AUDIT_EVENTS (test_sender, test_worker_settings count 14→15, test_audit_taxonomy + test_phase51_audit_chain_invariants count 105→109, test_handler_start + test_freeze_resolver HandlerContext ctor). Fixed in commit `0d8548db` — these were latent in the global suite (phase-93 messaging-scoped runs passed) and are now green.

## Carried-Forward Deferred (pre-existing, not introduced by v2.5)
- Known-flaky: test_freeze_race; promo F821 ruff debt; test_alembic_clean (tracked since v2.4 close).

## Human Verification
- Phase 94 HUMAN-UAT (pixel-perfect parity, live WS round-trip, photo flow on device) remains deferred — see `.planning/phases/94-pwa-chatscreen-wiring/94-HUMAN-UAT.md`.

## Status: PASSED
