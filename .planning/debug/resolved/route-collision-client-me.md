---
slug: route-collision-client-me
status: resolved
trigger: "Phase 999.5 onboarding profile read/write non-functional over HTTP — duplicate /api/v1/client/me route registration shadows the 999.5 handlers"
phase: 999.5-client-pwa-onboarding-and-receipt-email
created: 2026-06-01
updated: 2026-06-01
---

## Symptoms

- **Expected:** PATCH /api/v1/client/me accepts the Phase 999.5 onboarding body
  `{firstName, goal, heightCm, weightKg, onboardingCompleted}` (finish) and
  `{onboardingCompleted: true}` (skip); GET /api/v1/client/me returns the extended
  profile incl. `goal/heightCm/weightKg/onboardingCompletedAt`.
- **Actual:** PATCH /client/me returns `422 {"code":"validation_error", fields:{firstName:"Extra inputs are not permitted", goal:..., heightCm:..., weightKg:..., onboardingCompleted:...}}`.
  GET /client/me returns only `id,phone,email,first_name,last_name,middle_name,birthday,gender` (no onboarding fields).
- **Error:** HTTP 422 "Extra inputs are not permitted" on every profile field.
- **Timeline:** Surfaced during automated UAT of Phase 999.5 (2026-06-01). Onboarding
  finish AND skip both fail; «Готово!» overlay never appears (shows «Произошла ошибка»).
- **Reproduction:** Login as newbie dev client (+79999999999 / dev OTP 111111) → /onboarding →
  fill steps → «Перейти в «Мой зал»» → 422. Also reproducible via curl:
  `curl -b <jar> -X PATCH localhost:8000/api/v1/client/me -H "x-csrf-token: <csrf>" -d '{"firstName":"X","goal":"lose_weight","heightCm":180,"weightKg":75,"onboardingCompleted":true}'` → 422.

## Root Cause (pre-diagnosed — verify, then fix)

Duplicate route registration. Two routers register the SAME paths under prefix `/api/v1/client`:
- `app/modules/client_auth/router.py`: GET `/me` (returns `ClientMeResponse` = id,phone,email,first_name,last_name,middle_name,birthday,gender) + PATCH `/me` (`ClientMePatchRequest`, email-only, `extra='forbid'`)
- `app/modules/client_portal/router.py` (Phase 999.5): GET `/me` (extended `ClientMeResponse` with goal/height_cm/weight_kg/onboarding_completed_at) + PATCH `/me` (`ClientProfileUpdateRequest`, full profile)

FastAPI/Starlette matches the FIRST-registered route. The `client_auth` /me pair is registered first
(live `app.routes` indices 110 GET / 111 PATCH win) and shadows the `client_portal` /me pair
(indices 130/131 — unreachable/dead). Verified via in-container `create_app()` route introspection:
the live PATCH /me `body_field` annotation is `client_auth.schemas.ClientMePatchRequest` (extra=forbid, fields=['email']).

Consequences:
1. Onboarding profile WRITE (finish + skip) → 422 (client_auth model forbids the fields).
2. Onboarding profile READ → no `onboardingCompletedAt` → HomeScreen auto-redirect gate
   (`!me.onboardingCompletedAt`) is permanently true → newbie loops back to /onboarding forever.

Missed by: `tests/modules/client_portal/test_client_me_service.py` exercises the SERVICE layer
directly (bypasses the ASGI route table); file-scoped code review had no cross-module route-graph view.

## Current Focus

hypothesis: "client_auth /me routes shadow the Phase 999.5 client_portal /me routes due to first-registered-wins ordering under a shared /api/v1/client prefix"
test: "Introspect app.routes for all /api/v1/client/me entries and confirm client_auth precedes client_portal; confirm live PATCH body model is ClientMePatchRequest"
expecting: "Two GET + two PATCH /me routes; client_auth indices < client_portal indices"
next_action: "Confirm root cause, then decide consolidation strategy (extend client_auth /me to own the full 999.5 contract, vs remove client_auth /me and have client_portal own /me incl. email-update + auth/CSRF deps), implement, and add an ASGI-level integration test for GET+PATCH /client/me"
reasoning_checkpoint: "Design decision required: which router should own /client/me. Constraint: the email-update path (receipt-email gate, PATCH /me {email}) currently works via client_auth and must keep working; auth-dep-before-CSRF ordering (T-68-25) must be preserved."

## Evidence

- timestamp: 2026-06-01 — Live curl PATCH /client/me with full onboarding body → 422 "Extra inputs are not permitted" for all 5 fields (reproduced after force-recreate of backend container).
- timestamp: 2026-06-01 — In-container `create_app()` introspection: `/api/v1/client/me` PATCH body model = `app.modules.client_auth.schemas.ClientMePatchRequest` (extra=forbid, fields=['email']); a second dead PATCH binds `client_portal.schemas.ClientProfileUpdateRequest` (extra=ignore, full fields).
- timestamp: 2026-06-01 — Direct `ClientProfileUpdateRequest.model_validate(body)` in-container PASSES (extra=ignore) — proves the 999.5 model itself is correct; only the routing is wrong.
- timestamp: 2026-06-01 — `app.routes` order: 110 GET client_auth.get_client_me, 111 PATCH client_auth.patch_client_me, 130 GET client_portal.client_get_me, 131 PATCH client_portal.client_update_me.

## Eliminated

- hypothesis: "Stale long-running uvicorn worker serving old code" — ELIMINATED: bug persists after `docker compose up -d --force-recreate backend`; reproduced from a clean process tree.
- hypothesis: "ClientProfileUpdateRequest schema wrong (missing fields / extra=forbid)" — ELIMINATED: direct model_validate passes with extra=ignore and all fields present.
- hypothesis: "Frontend sends wrong casing / wrong body" — ELIMINATED: network capture shows correct camelCase body; curl reproduces identically.


## Resolution

root_cause: "Duplicate GET+PATCH /api/v1/client/me registered by BOTH client_auth/router.py and client_portal/router.py under the shared /api/v1/client prefix; FastAPI first-registered-wins bound the client_auth pair (email-only PATCH, extra='forbid'; core-identity GET), shadowing the Phase 999.5 client_portal onboarding handlers."

fix: "Consolidated /me onto client_portal (the superset owner). Removed the duplicate GET+PATCH /me handlers + dead update_client_me service + ClientMePatchRequest/ClientMeResponse schemas from client_auth. Made the 999.5 handler fully cover the old client_auth contract: added id:UUID to client_portal ClientMeResponse (+ SELECT id in repository.fetch_client_me + pass id in service.get_client_me), and mapped the duplicate-email IntegrityError → ConflictError('email_unavailable') (409, non-enumerating) in repository.update_client_profile so the receipt-email path keeps its D-06 behavior. Auth-dep-before-CSRF ordering (T-68-25/T-999.5-08) is preserved by the existing client_portal PATCH (require_client → verify_client_csrf → get_db)."

regression_guard: "Added tests/integration/client_portal/test_client_me_route.py — ASGI-level (httpx ASGITransport, real route table) GET+PATCH /me: onboarding body accepted (NOT 422), onboarding fields exposed on GET, email round-trip works. Complements test_client_me_service.py which bypassed routing. Pre-existing tests/integration/client_auth/test_profile_update.py (email round-trip + 409) now resolves to the consolidated handler and still passes."

verification: "ruff: no new errors (5 pre-existing unchanged). mypy strict: clean (11 files). Targeted suites: 23 passed (new route tests + test_profile_update + test_client_me_service). Full client_auth+client_portal suites: 97 passed. Live in-container app.routes introspection after backend restart: exactly one GET (client_get_me) + one PATCH (client_update_me) at /api/v1/client/me — duplicate eliminated."

## Fix Evidence

- timestamp: 2026-06-01 — Confirmed root cause by reading both routers: client_auth/router.py GET+PATCH /me (lines 171-205) and client_portal/router.py GET+PATCH /me (lines 717-780); v1 router mounts client_auth_router then client_portal_router both at prefix="/client" (api/v1/router.py:95,103).
- timestamp: 2026-06-01 — Found pre-existing tests/integration/client_auth/test_profile_update.py asserts (a) PATCH /me {email} response has data.id, and (b) duplicate-email → 409 code=conflict message=email_unavailable. Fix preserved BOTH: added id to ClientMeResponse; added IntegrityError→ConflictError mapping in client_portal repository.
- timestamp: 2026-06-01 — ruff: 5 errors (== baseline, all pre-existing I001/S608/RUF100, none introduced). mypy: Success, no issues in 11 files.
- timestamp: 2026-06-01 — pytest (host-side): test_client_me_route + test_profile_update + test_client_me_service = 23 passed; full client_auth+client_portal+modules suites = 97 passed.
- timestamp: 2026-06-01 — After `docker compose restart backend`, in-container create_app() route introspection: /api/v1/client/me has exactly ['GET'] client_get_me + ['PATCH'] client_update_me (the client_portal handlers). The shadowing client_auth pair (formerly indices 110/111) is gone.
- timestamp: 2026-06-01 — UAT CONFIRMED (live browser, restarted backend). Finish path: «Перейти в «Мой зал»» pops «Готово, Андрей!» (no error); PATCH /client/me → 200 with id + full profile + onboardingCompletedAt; DB shows goal=gain_mass, height_cm=175, weight_kg=70, onboarding_completed_at set. No re-redirect: reloading /home stays on /home; GET /me exposes onboarding fields. Skip-path PATCH → 200 body {"onboardingCompleted":true}. Live app.routes: exactly one GET + one PATCH /api/v1/client/me (client_portal). Shadowing eliminated. (Re-seed + scripts cp needed after force-recreate wiped DB — environment artifact, not a code issue.)
- timestamp: 2026-06-01 — SEPARATE FINDING (out of scope, NOT part of this fix): skip-path client-side bug — after successful skip PATCH (200, server state correct), navigate('/home') bounces back to /onboarding because HomeScreen reads stale cached /client/me before the invalidated me() refetch lands. Finish path unaffected (overlay delays navigation). Recorded as GAP-2 in .planning/phases/999.5-client-pwa-onboarding-and-receipt-email/999.5-HUMAN-UAT.md for follow-up. (OtpCode Pyright warning in new test is a confirmed false positive; symbol resolves, test passes.)
